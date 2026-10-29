# Manual UI acceptance

Browser verification belongs to the project owner. The coding agent has not performed these UI checks.

## Startup and privacy

1. Stop the old server and launch `.\.venv\Scripts\python.exe run_app.py`.
2. Verify there is no preset_picker default/session-state warning.
3. Verify no key, endpoint, provider or model entry field appears on any page.
4. Turn Sample mode off to check configuration status, but do not generate a live plan unless a model call is intended.
5. Refresh/reconnect normally and check for the reported Proactor shutdown error. Report any remaining traceback.

## Files and sample tasks

1. Verify the drop zone, Try sample invoices and Clear files controls.
2. Check compact file chips and local previews; no long vertical source list should appear.
3. Upload CSV/XLSX files. They should replace samples; preview shows the first 100 rows.
4. Clear files: generation disables. Restore samples and generate Invoice review in Sample mode.
5. Compact workflow steps should have no descriptive paragraphs or FROM lines. Run the plan.
6. Verify four rows and flags false, true, false, true; exactly 50,000 is not flagged.
7. Test High-value invoices (50,001 and 75,000) and Vendor summary (100,001 and 87,500).

## Local features

1. Search the report for Acme, then an absent value. Check match counts and empty results.
2. Download matching rows as CSV; original report downloads must stay unfiltered.
3. Download everything as ZIP; verify workflow.json, audit.json and reports/ contents.
4. Save workflow JSON. Start a new workflow, restore samples, then load that JSON and run without model calls.
5. Import an invalid plan or one referencing missing files. Expect validation errors.
6. Edit gt to gte in the plan and run. The 50,000 row should be flagged.
7. Verify workflow.json in the ZIP matches the edited plan that actually executed.
8. Visit Run history and Research, then return. Current task, files, edits and result should persist.
9. New workflow clears current files, task and output while retaining session history.
10. Check narrow-window layout, readable contrast, compact cards, focus visibility and the decorative header.
