"""Phase 1.1 event schema — the Python side of the normative contract.

The *normative* definition of a Pulse event lives at
``schema/pulse-event.v1.schema.json`` (repo root), per
plans/stage-1-blueprint.md Phase 1.1 step 4: "Write the schema as a
versioned artifact, not as code comments... a JSON Schema is the only
artifact both [producers] can validate against."

This module does three things:
  1. Loads that JSON Schema once and compiles a validator from it.
  2. Derives the allowed ``event_type`` / ``producer`` enums FROM the JSON
     Schema (never hand-duplicated), so the two can't drift apart.
  3. Provides small builder/utility functions (``uuid7``, ``new_event``,
     ``validate_event``) used by every producer and by the store.

Ordering note (also documented in the schema file itself): ``t_mono_ns`` is
only valid for ordering events *within one session_id*. Reconciling clocks
across sessions/producers is Phase 1.7's job, not implemented here.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SUPPORTED_SCHEMA_VERSION = 1

# Resolved relative to the repo root, matching the path the blueprint's
# "Expected output" names explicitly: schema/pulse-event.v1.schema.json.
# This repo is run from source (uv-managed venv), not installed as a wheel
# elsewhere, so this relative resolution is acceptable for now — flagged
# here rather than silently fragile.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schema" / "pulse-event.v1.schema.json"


def _load_schema() -> dict[str, Any]:
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Normative event schema not found at {_SCHEMA_PATH}. "
            "This module resolves it relative to the repo root; if the "
            "package is ever installed standalone (outside this repo "
            "checkout), this path resolution needs revisiting."
        )
    with _SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


_SCHEMA: dict[str, Any] = _load_schema()
_VALIDATOR = Draft202012Validator(_SCHEMA)

# Derived from the schema, not hand-duplicated, so they cannot drift.
EVENT_TYPES: frozenset[str] = frozenset(_SCHEMA["properties"]["event_type"]["enum"])
PRODUCERS: frozenset[str] = frozenset(_SCHEMA["properties"]["producer"]["enum"])
SENSOR_TIERS: frozenset[str] = frozenset(_SCHEMA["properties"]["sensor"]["properties"]["tier"]["enum"])


class EventValidationError(ValueError):
    """Raised when an event fails schema validation or a store-level rule.

    Carries every individual jsonschema error (not just the first one) so
    a caller — including the Phase 1.1 schema-enforcement test — can see
    *exactly* why an event was rejected, per the blueprint's "reject at
    write time... with a specific error" requirement.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or [message]


def validate_event(event: dict[str, Any]) -> None:
    """Validate ``event`` against the normative JSON Schema.

    Raises EventValidationError with every violation listed if invalid.
    Does nothing (returns None) if valid. This function does NOT check
    schema_version against what a particular store supports — the JSON
    Schema only requires schema_version to be a positive integer, since
    the schema itself doesn't know which store it's about to be written
    into. Store-level "is this a version I support" enforcement lives in
    store.py, layered on top of this.
    """
    errors = sorted(_VALIDATOR.iter_errors(event), key=lambda e: list(e.absolute_path))
    if errors:
        messages = [_format_error(e) for e in errors]
        raise EventValidationError(
            f"event failed schema validation ({len(messages)} error(s)): {messages[0]}",
            errors=messages,
        )


def _format_error(e: ValidationError) -> str:
    path = "/".join(str(p) for p in e.absolute_path) or "<root>"
    return f"{path}: {e.message}"


def is_valid_event(event: dict[str, Any]) -> tuple[bool, list[str]]:
    """Non-raising variant of validate_event — returns (ok, error_messages)."""
    errors = sorted(_VALIDATOR.iter_errors(event), key=lambda e: list(e.absolute_path))
    if not errors:
        return True, []
    return False, [_format_error(e) for e in errors]


# --------------------------------------------------------------------------
# UUIDv7 (RFC 9562) — stdlib only. Python 3.13's uuid module does not yet
# provide uuid7(), so this is hand-rolled: 48-bit big-endian ms timestamp,
# version nibble 7, RFC 4122 variant bits, and 74 bits of randomness — the
# "rand_a || rand_b" layout, no counter (monotonicity within the same
# millisecond falls back to random ordering, which is acceptable here since
# t_mono_ns — not event_id — is the actual ordering key; event_id only needs
# to be *roughly* time-ordered for readability, per the schema's own
# description of the field).
# --------------------------------------------------------------------------
def uuid7() -> str:
    unix_ms = time.time_ns() // 1_000_000
    rand = os.urandom(10)  # 80 bits; we'll mask down to the 74 we need

    time_bytes = unix_ms.to_bytes(6, byteorder="big")

    rand_a = int.from_bytes(rand[0:2], "big") & 0x0FFF  # 12 bits
    rand_b = int.from_bytes(rand[2:10], "big") & 0x3FFFFFFFFFFFFFFF  # 62 bits

    version_and_rand_a = (0x7 << 12) | rand_a  # version 7 in top nibble
    variant_and_rand_b = (0b10 << 62) | rand_b  # RFC 4122 variant (10xx)

    as_int = (
        int.from_bytes(time_bytes, "big") << 80
        | version_and_rand_a << 64
        | variant_and_rand_b
    )
    return str(uuid.UUID(int=as_int))


def monotonic_ns() -> int:
    return time.monotonic_ns()


def wall_utc_micros() -> int:
    return time.time_ns() // 1_000


def new_session_id() -> str:
    return str(uuid.uuid4())


def new_event(
    *,
    producer: str,
    event_type: str,
    session_id: str,
    actor_id: str,
    t_mono_ns: int | None = None,
    t_wall_utc: int | None = None,
    schema_version: int = SUPPORTED_SCHEMA_VERSION,
    app: dict[str, Any] | None = None,
    window: dict[str, Any] | None = None,
    element: dict[str, Any] | None = None,
    content: dict[str, Any] | None = None,
    sensor: dict[str, Any] | None = None,
    context: list[dict[str, Any]] | None = None,
    link_hint: dict[str, Any] | None = None,
    capture_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one event dict. Does NOT validate — call validate_event()
    (or let store.append() do it) before it is persisted anywhere.

    Optional fields that are None are OMITTED from the resulting dict
    entirely rather than written as an explicit null — this keeps the
    stored/round-tripped shape exactly matching "the fields that were
    actually set", which is what the Phase 1.1 round-trip checkpoint
    compares against.
    """
    event: dict[str, Any] = {
        "event_id": uuid7(),
        "schema_version": schema_version,
        "producer": producer,
        "t_wall_utc": t_wall_utc if t_wall_utc is not None else wall_utc_micros(),
        "t_mono_ns": t_mono_ns if t_mono_ns is not None else monotonic_ns(),
        "session_id": session_id,
        "actor_id": actor_id,
        "event_type": event_type,
    }
    optional = {
        "app": app,
        "window": window,
        "element": element,
        "content": content,
        "sensor": sensor,
        "context": context,
        "link_hint": link_hint,
        "capture_meta": capture_meta,
    }
    for key, value in optional.items():
        if value is not None:
            event[key] = value
    return event
