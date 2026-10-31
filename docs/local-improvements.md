# Local acceptance — 30 October 2026

These changes await owner acceptance. No commit or push is part of this update.

## Restart

Stop the existing server, then run from the Prompt Compiler folder:

```powershell
.\.venv\Scripts\python.exe run_app.py
```

The compiler revision changed, so generate a fresh plan. Provider credentials remain in the existing
`.env`. No live model calls or browser automation were used during implementation.

## Manual checks

1. Check Describe, Plan and Result in the dark theme, including upload, dropdowns, tables, error
   messages and keyboard focus. Check a narrow window and your system's reduced-motion preference.
2. Upload `examples/table_tools.csv`. Request: "Remove duplicates by Record ID, keep the last
   occurrence, calculate calendar days from Opened to Closed as Duration, preserve the original
   columns and export XLSX. Dates use YYYY-MM-DD."
3. Review the plan. It should use deduplicate followed by date_difference, with Duration exported.
   Expected result: three rows, Record IDs A/B/C, Duration 2/-2/blank. The retained A row says revised.
4. In Adjust rules & output names, switch to keeping the first occurrence. Apply and run locally:
   A should say original. No additional model call is needed for this edit.
5. Switch duplicate handling to remove every duplicated group. The result should contain only B/C.
6. Try an invalid date (for example 2024-02-30). Execution should fail with a date-format message,
   and no report should be offered for that failed run.
7. Try an unsupported join or scanned PDF task. Expect a specific limitation, not a partial report.
8. Check your existing workflows and downloads before approving any GitHub push.

## Validation evidence

121 local tests passed: 120 backend tests plus the HTTP-adapter test against a local stub server.
The stub test required permission to access localhost in this environment. No external provider was
called. Tests cover case/null duplicate keys, retention modes, original cell preservation, empty
reports, leap dates, negative and missing date differences, invalid dates, schema binding, request
coverage, local edits, XLSX reopening, overflow and derived-column limits.

UI appearance and live model quality have not been tested by the agent. These are owner acceptance
steps. Request-coverage declarations remain a useful check, not a proof of semantic correctness.

## Remaining scope

Joins, OCR, multiple invoices in one document, arbitrary document extraction, charts, currency
conversion, business-day/month/timezone arithmetic and external actions remain unsupported.
Academic evaluation, literature review and final report still require separate work and actual evidence.
