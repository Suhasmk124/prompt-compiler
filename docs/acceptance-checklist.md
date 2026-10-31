# Owner acceptance checklist — studio release

Browser testing remains with the owner. Backend checks and live evaluation are recorded separately.
Restart the app with `.\.venv\Scripts\python.exe run_app.py` before checking native theme changes.

## Appearance and interaction

- Check the white landing page, centered serif heading, pastel workflow illustration and real top navigation.
- Start a workflow using the landing link; it should move to the task area smoothly.
- Check hover, pressed and keyboard-focus states on buttons and downloads.
- At a narrow window, verify navigation, form controls and report tables remain usable.
- With reduced motion enabled in the operating system, animations and smooth scrolling should stop.
- Confirm that decorative example cards are not being presented as your actual results.

## Imports and generation

- Upload the invoice stress CSV. Preview a file and download the original; its contents should be unchanged.
- Set an identifier column to Text and verify leading zeros. Save the import-settings JSON.
- Choose Number on a genuinely nonnumeric column: see a clear error, then correct it in the same editor.
- Verify literal NA/N/A/NULL stays text until explicitly selected as a missing-value marker.
- Generate a plan. The interface should stay responsive and show real phase labels rather than fake percentages.
- Cancel generation. No subsequent model requests or accepted plan should appear; an already sent request may finish.
- Start a new workspace during a job. Its obsolete result must not replace the new workspace.
- A temporary rate limit should preserve the task and show a bounded, cancelable wait or a clear quota outcome.

## Execution and reuse

- Ask for Karnataka + UPI filtering on our invoice CSV: expect 10 invoice rows and all 78 source columns.
- Ask for unique matching vendors explicitly: that is a different task and may return one vendor.
- Run a nested boolean flag. Confirm original columns and only the requested final flag are exported.
- Edit a rule locally and rerun; no new generation/review request should occur for that edit alone.
- Import a saved plan, rebind its files, and run. Check selected import rules are appropriate for those files.
- For workflows with multiple exports, switch the report selector and verify each preview/download.
- Compare reports from earlier runs and check report names and source-input warnings.
- Verify failed execution does not present an intermediate table as a completed downloadable report.

## Final academic acceptance

Confirm faculty-specific deadlines, team/student details and the IEEE submission template. The report
draft and pilot validation are supporting materials, not a completed final submission or held-out accuracy claim.
