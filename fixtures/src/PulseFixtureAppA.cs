// Pulse Stage 1 fixture application "System A: record viewer".
//
// A small, real WinForms app with a known, stable control tree
// (AutomationId on every control, via WinForms' built-in mapping of
// Control.Name -> UIA AutomationId). Used as ground truth across Phase
// 1.2 (app/window attribution) and Phase 1.3+ (element resolution).
//
// Compiled with the in-box .NET Framework compiler (csc.exe) -- no .NET
// SDK is installed in this environment (confirmed absent; `dotnet` is not
// on PATH), but csc.exe has shipped with every Windows install since
// .NET Framework 4, which is enough for a plain WinForms fixture.
//
// Positioned at a fixed screen location with fixed control positions, so
// a driver script can click deterministically by absolute screen
// coordinates without needing UI Automation to find controls (that's
// Phase 1.3's job) -- for Phase 1.2 we only need "a click happened in
// this specific app", not "in this specific control".
using System;
using System.Drawing;
using System.Windows.Forms;

public class FixtureAppA : Form
{
    public FixtureAppA()
    {
        Text = "System A - Record Viewer";
        Name = "FixtureAppA_MainWindow";
        StartPosition = FormStartPosition.Manual;
        Location = new Point(100, 100);
        ClientSize = new Size(480, 520);
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;

        var lblLoanId = new Label
        {
            Name = "lblLoanId",
            Text = "Loan ID:",
            Location = new Point(20, 20),
            Size = new Size(80, 23),
        };

        var txtLoanId = new TextBox
        {
            Name = "txtLoanId",
            Text = "LN-48213",
            Location = new Point(110, 20),
            Size = new Size(200, 23),
        };

        var lblIncome = new Label
        {
            Name = "lblIncome",
            Text = "Declared income:",
            Location = new Point(20, 60),
            Size = new Size(120, 23),
        };

        var txtIncome = new TextBox
        {
            Name = "txtIncome",
            Text = "92000",
            Location = new Point(150, 60),
            Size = new Size(160, 23),
        };

        // Phase 1.3 content-correctness checkpoint needs five fields with
        // known, distinct sentinel values that the test asserts appear in
        // an UNRELATED click's context snapshot -- proving on-screen
        // content is captured even when the user never touched that field.
        var lblBorrower = new Label
        {
            Name = "lblBorrower",
            Text = "Borrower:",
            Location = new Point(20, 100),
            Size = new Size(80, 23),
        };
        var txtBorrower = new TextBox
        {
            Name = "txtBorrower",
            Text = "PULSESENTINEL-BORROWER-Jordan-Casewright",
            Location = new Point(110, 100),
            Size = new Size(340, 23),
        };

        var lblAddress = new Label
        {
            Name = "lblAddress",
            Text = "Property address:",
            Location = new Point(20, 140),
            Size = new Size(120, 23),
        };
        var txtAddress = new TextBox
        {
            Name = "txtAddress",
            Text = "PULSESENTINEL-ADDRESS-742-Evergreen-Terrace",
            Location = new Point(150, 140),
            Size = new Size(300, 23),
        };

        var lblNotes = new Label
        {
            Name = "lblNotes",
            Text = "Notes:",
            Location = new Point(20, 180),
            Size = new Size(80, 23),
        };
        var txtNotes = new TextBox
        {
            Name = "txtNotes",
            Text = "PULSESENTINEL-NOTES-flagged-for-second-review",
            Location = new Point(110, 180),
            Size = new Size(340, 23),
        };

        // Phase 1.3 build step 6 / password guardrail checkpoint: a real
        // password-masked control (UseSystemPasswordChar), so the capture
        // host's "never read the value of a password field" rule has
        // something real to be tested against.
        var lblPassword = new Label
        {
            Name = "lblPassword",
            Text = "Vault password:",
            Location = new Point(20, 220),
            Size = new Size(110, 23),
        };
        var txtPassword = new TextBox
        {
            Name = "txtPassword",
            UseSystemPasswordChar = true,
            Location = new Point(150, 220),
            Size = new Size(200, 23),
        };

        var btnApprove = new Button
        {
            Name = "btnApprove",
            Text = "Approve",
            Location = new Point(20, 450),
            Size = new Size(100, 32),
        };

        var btnReject = new Button
        {
            Name = "btnReject",
            Text = "Reject",
            Location = new Point(130, 450),
            Size = new Size(100, 32),
        };

        var lstHistory = new ListBox
        {
            Name = "lstHistory",
            Location = new Point(20, 260),
            Size = new Size(430, 180),
        };
        lstHistory.Items.Add("Case opened");
        lstHistory.Items.Add("Documents attached");

        Controls.Add(lblLoanId);
        Controls.Add(txtLoanId);
        Controls.Add(lblIncome);
        Controls.Add(txtIncome);
        Controls.Add(lblBorrower);
        Controls.Add(txtBorrower);
        Controls.Add(lblAddress);
        Controls.Add(txtAddress);
        Controls.Add(lblNotes);
        Controls.Add(txtNotes);
        Controls.Add(lblPassword);
        Controls.Add(txtPassword);
        Controls.Add(btnApprove);
        Controls.Add(btnReject);
        Controls.Add(lstHistory);
    }

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.Run(new FixtureAppA());
    }
}
