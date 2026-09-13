// Pulse Stage 1 fixture application "System B: lookup tool".
// See PulseFixtureAppA.cs for the full rationale/build notes.
using System;
using System.Drawing;
using System.Windows.Forms;

public class FixtureAppB : Form
{
    public FixtureAppB()
    {
        Text = "System B - Lookup Tool";
        Name = "FixtureAppB_MainWindow";
        StartPosition = FormStartPosition.Manual;
        Location = new Point(650, 100);
        ClientSize = new Size(480, 320);
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;

        var lblSearch = new Label
        {
            Name = "lblSearch",
            Text = "Search:",
            Location = new Point(20, 20),
            Size = new Size(80, 23),
        };

        var txtSearch = new TextBox
        {
            Name = "txtSearch",
            Location = new Point(110, 20),
            Size = new Size(250, 23),
        };

        var btnSearch = new Button
        {
            Name = "btnSearch",
            Text = "Search",
            Location = new Point(370, 20),
            Size = new Size(90, 23),
        };

        var lstResults = new ListBox
        {
            Name = "lstResults",
            Location = new Point(20, 60),
            Size = new Size(430, 170),
        };

        var btnOpenDocument = new Button
        {
            Name = "btnOpenDocument",
            Text = "Open Document",
            Location = new Point(20, 250),
            Size = new Size(140, 32),
        };

        btnSearch.Click += (s, e) =>
        {
            lstResults.Items.Clear();
            lstResults.Items.Add("Income statement: $84,000");
            lstResults.Items.Add("Employment verification: on file");
        };

        Controls.Add(lblSearch);
        Controls.Add(txtSearch);
        Controls.Add(btnSearch);
        Controls.Add(lstResults);
        Controls.Add(btnOpenDocument);
    }

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.Run(new FixtureAppB());
    }
}
