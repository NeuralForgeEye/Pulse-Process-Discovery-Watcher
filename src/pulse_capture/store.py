"""Phase 1.1 local event store.

SQLite in WAL mode, per plans/stage-1-blueprint.md Phase 1.1 step 5: one
`events` table with the scalar fields as columns and the nested objects as
JSON columns, indexed on (t_mono_ns), (session_id, t_mono_ns), (event_type).

Why SQLite over JSONL (from the blueprint, restated here so the reasoning
travels with the code): crash-safe under a hard kill (WAL + synchronous=
NORMAL), readable concurrently while still being written, queryable without
loading everything into memory, present everywhere with no extra service.

`EventStore` is the port (plans/platform-architecture.md §4.1);
`SQLiteEventStore` is the local adapter. Desktop-capture code should type
against `EventStore`, not `SQLiteEventStore`, so a future adapter (the
internal Wells Fargo database, per platform-architecture.md) is a
composition-root swap, not a rewrite.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pulse_capture.schema import SUPPORTED_SCHEMA_VERSION, EventValidationError, validate_event

_NESTED_FIELDS = (
    "app",
    "window",
    "element",
    "content",
    "sensor",
    "context",
    "link_hint",
    "capture_meta",
)
_SCALAR_FIELDS = (
    "event_id",
    "schema_version",
    "producer",
    "t_wall_utc",
    "t_mono_ns",
    "session_id",
    "actor_id",
    "event_type",
)


class StoreSchemaVersionError(RuntimeError):
    """The store's on-disk schema_version doesn't match what this code
    supports, or an incoming event's schema_version doesn't match the
    store's. Either way: refuse rather than silently misinterpreting data.
    """


class EventStore(ABC):
    """The port. See module docstring."""

    @abstractmethod
    def append(self, event: dict[str, Any]) -> None:
        """Validate and write one event. Raises EventValidationError or
        StoreSchemaVersionError and writes NOTHING if invalid."""

    @abstractmethod
    def append_batch(
        self, events: Sequence[dict[str, Any]]
    ) -> list[tuple[dict[str, Any], str]]:
        """Validate and write many events in one transaction.

        Valid events are written; invalid ones are not. Returns the list of
        (event, error_message) pairs for whatever was rejected, so a caller
        (e.g. the async writer) can log/count without the whole batch
        failing because one event was malformed.
        """

    @abstractmethod
    def read_range(self, t0_mono_ns: int, t1_mono_ns: int) -> list[dict[str, Any]]:
        """Return events with t_mono_ns in [t0, t1], ordered by t_mono_ns.
        Nested JSON columns are reconstructed back into nested dict keys;
        fields that were never set on write are simply absent, not null.
        """

    @abstractmethod
    def export_parquet(self, path: Path) -> int:
        """Export the full store to a Parquet file. Returns row count."""

    @abstractmethod
    def export_jsonl(self, path: Path) -> int:
        """Export the full store to newline-delimited JSON (one
        reconstructed nested-object event per line). Returns row count."""

    @abstractmethod
    def integrity_check(self) -> str:
        """Run the store's integrity check and return its raw result
        (e.g. SQLite's PRAGMA integrity_check -> "ok" or a list of
        problems). Used by the crash-safety validation checkpoint."""

    @abstractmethod
    def close(self) -> None:
        """Flush and close. Safe to call more than once."""

    def __enter__(self) -> EventStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SQLiteEventStore(EventStore):
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._closed = False
        self._write_lock = threading.Lock()
        self._conn = self._new_connection()
        self._init_schema()

    # -- connection / schema setup -----------------------------------------

    def _new_connection(self) -> sqlite3.Connection:
        # check_same_thread=False: this connection (self._conn) is created
        # here on whichever thread constructs the store, but real usage
        # (Phase 1.2's EventWriter) writes from a dedicated background
        # writer thread instead. That is safe ONLY because every access to
        # self._conn -- append(), append_batch(), close() -- is already
        # serialized through self._write_lock; sqlite3's default
        # check_same_thread=True guard is a same-thread-only convenience
        # check, not a substitute for that lock, and it's the lock (not
        # this flag) that actually makes concurrent-thread use safe here.
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=OFF;")
        return conn

    def _init_schema(self) -> None:
        with self._write_lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    producer TEXT NOT NULL,
                    t_wall_utc INTEGER NOT NULL,
                    t_mono_ns INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    app_json TEXT,
                    window_json TEXT,
                    element_json TEXT,
                    content_json TEXT,
                    sensor_json TEXT,
                    context_json TEXT,
                    link_hint_json TEXT,
                    capture_meta_json TEXT
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_t_mono ON events(t_mono_ns)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session_t_mono "
                "ON events(session_id, t_mono_ns)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
            )

            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                    (str(SUPPORTED_SCHEMA_VERSION),),
                )
            else:
                on_disk = int(row[0])
                if on_disk != SUPPORTED_SCHEMA_VERSION:
                    raise StoreSchemaVersionError(
                        f"{self.db_path} was created with schema_version={on_disk}, "
                        f"but this code supports schema_version={SUPPORTED_SCHEMA_VERSION}. "
                        "Refusing to open — a migration path is not yet implemented."
                    )

    # -- validation ----------------------------------------------------------

    def _validate_for_store(self, event: dict[str, Any]) -> None:
        """Schema validation PLUS the store-level version check. An event
        can be structurally valid per the JSON Schema (schema_version is
        just "some positive integer") and still be rejected here because
        it doesn't match what *this store* was created with — the
        "future schema_version" malformed case from the checkpoint.
        """
        version = event.get("schema_version")
        if version != SUPPORTED_SCHEMA_VERSION:
            raise EventValidationError(
                f"event schema_version={version!r} is not supported by this store "
                f"(supports {SUPPORTED_SCHEMA_VERSION})",
                errors=[f"schema_version: unsupported value {version!r}"],
            )
        validate_event(event)

    # -- writes ----------------------------------------------------------

    def append(self, event: dict[str, Any]) -> None:
        self._validate_for_store(event)
        row = _event_to_row(event)
        with self._write_lock, self._conn:
            self._conn.execute(_INSERT_SQL, row)

    def append_batch(
        self, events: Sequence[dict[str, Any]]
    ) -> list[tuple[dict[str, Any], str]]:
        rejected: list[tuple[dict[str, Any], str]] = []
        rows: list[tuple[Any, ...]] = []
        for event in events:
            try:
                self._validate_for_store(event)
            except EventValidationError as exc:
                rejected.append((event, str(exc)))
                continue
            rows.append(_event_to_row(event))

        if rows:
            with self._write_lock, self._conn:
                self._conn.executemany(_INSERT_SQL, rows)
        return rejected

    # -- reads -------------------------------------------------------------

    def read_range(self, t0_mono_ns: int, t1_mono_ns: int) -> list[dict[str, Any]]:
        # A fresh, read-only connection per call: WAL allows concurrent
        # readers alongside the single writer connection without any
        # cross-thread sharing of sqlite3.Connection objects.
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                f"SELECT {_ALL_COLUMNS} FROM events "
                "WHERE t_mono_ns >= ? AND t_mono_ns <= ? "
                "ORDER BY t_mono_ns ASC",
                (t0_mono_ns, t1_mono_ns),
            )
            return [_row_to_event(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def _read_all_rows(self) -> Iterable[sqlite3.Row]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield from conn.execute(
                f"SELECT {_ALL_COLUMNS} FROM events ORDER BY t_mono_ns ASC"
            ).fetchall()
        finally:
            conn.close()

    # -- exports -------------------------------------------------------------

    def export_parquet(self, path: Path) -> int:
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = list(self._read_all_rows())
        columns: dict[str, list[Any]] = {c: [] for c in _SCALAR_FIELDS}
        for field in _NESTED_FIELDS:
            columns[f"{field}_json"] = []
        for r in rows:
            for c in _SCALAR_FIELDS:
                columns[c].append(r[c])
            for field in _NESTED_FIELDS:
                columns[f"{field}_json"].append(r[f"{field}_json"])
        table = pa.table(columns)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, str(path))
        return len(rows)

    def export_jsonl(self, path: Path) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with path.open("w", encoding="utf-8") as f:
            for r in self._read_all_rows():
                f.write(json.dumps(_row_to_event(r), ensure_ascii=False))
                f.write("\n")
                count += 1
        return count

    # -- maintenance -------------------------------------------------------

    def integrity_check(self) -> str:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        try:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
            return "; ".join(r[0] for r in rows)
        finally:
            conn.close()

    def row_count(self) -> int:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        finally:
            conn.close()

    def close(self) -> None:
        if self._closed:
            return
        with self._write_lock:
            with contextlib.suppress(sqlite3.Error):  # best-effort; closing anyway
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.close()
        self._closed = True


_ALL_COLUMNS = ", ".join(
    list(_SCALAR_FIELDS) + [f"{f}_json" for f in _NESTED_FIELDS]
)
_INSERT_SQL = (
    "INSERT INTO events (" + _ALL_COLUMNS + ") VALUES ("
    + ", ".join(["?"] * (len(_SCALAR_FIELDS) + len(_NESTED_FIELDS)))
    + ")"
)


def _event_to_row(event: dict[str, Any]) -> tuple[Any, ...]:
    scalars = tuple(event[f] for f in _SCALAR_FIELDS)
    nested = tuple(
        json.dumps(event[f], ensure_ascii=False, sort_keys=True) if f in event else None
        for f in _NESTED_FIELDS
    )
    return scalars + nested


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event: dict[str, Any] = {f: row[f] for f in _SCALAR_FIELDS}
    for f in _NESTED_FIELDS:
        raw = row[f"{f}_json"]
        if raw is not None:
            event[f] = json.loads(raw)
    return event
