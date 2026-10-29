# Manual UI acceptance

Browser testing belongs to the project owner. The coding agent has not performed these checks.

## Guided stages

1. Launch `.\.venv\Scripts\python.exe run_app.py` with the existing local .env.
2. Initially see only the task/files stage and slim progress indicator. There should be no plan/report placeholder boxes or offline-mode toggle.
3. Select Try example PDF, preview/download it, and enter a task. Generation must remain disabled if the engine is not configured.
4. Generate a plan deliberately; this makes model calls. The task/files view should be replaced by Review after success.
5. Review shows compact steps, local rule editing and advanced JSON, with no report box yet.
6. Run the workflow. Success should advance to Report, replacing Review. Failure should remain on Review with a useful error and trace.
7. Adjust plan should return to Review without a model call. Edit task & files should return to the first stage, preserving the draft and inputs.
8. An unchanged request can continue to the existing plan without regenerating. Changed task/files invalidate the old plan and output.
9. Check stage transitions, staggered step entrance, floating decorative tiles and reduced-motion behavior. Verify these animations do not imply fake execution progress.
10. Verify no key, model, endpoint or provider entry fields appear anywhere.

## Reuse and reports

1. Save plan JSON and import it with new compatible file bindings. Loading and execution should work without model calls.
2. Adjust a flag threshold/comparison or output filename and apply. The previous report must invalidate; rerun locally to get a new report.
3. Compare two successful runs, including a changed threshold and different schemas. Changed row versions count as additions/removals; schema differences should block row comparison.
4. Search the report, download matching rows, and verify original reports remain unfiltered.
5. Download everything as ZIP and verify it includes the executed workflow, audit and reports.
6. Try invalid JSON, missing file bindings, incompatible schemas and an unsafe export name. Execution should be blocked.
7. Visit Run history and Research, then return. The current stage, plan edits and report should persist.
8. New workflow should return to the first stage and clear current task/files/output while retaining bounded comparison snapshots and run history.
9. Refresh/reconnect and check startup warnings/Windows connection cleanup. Report any remaining traceback.

The backend PDF smoke check is documented separately in docs/pdf-validation.md. It does not replace visual acceptance.
