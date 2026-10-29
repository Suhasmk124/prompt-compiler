# Reuse and compare workflows locally

All features on this page run without model or API requests. The app never regenerates a workflow merely because a rule or file binding changes.

## Apply a saved plan to new files

1. Upload the new inputs in Source files.
2. Open Have a saved workflow and upload the saved workflow JSON.
3. For each read step, select which current files it should read. Exact existing filenames are preselected; unmatched names are not guessed.
4. Load the plan and run it.

The original JSON is not modified. The revised plan is validated before loading: missing files, empty bindings, repeated files and incompatible input schemas are rejected. A read step may use a different number of compatible files than the original batch. Downstream column validation still applies.

## Tune a rule

Open Adjust rules & output names. Change a filter/flag comparison or value, or change the report basename and its `.xlsx`/`.csv` extension. Apply changes, then run the plan again.

The editor validates the entire revised plan and only commits valid changes. It never silently overwrites a current report. Arbitrary operation/column changes remain in the advanced JSON editor and are subject to the same schema and semantic validation.

Example: run Invoice review with `total > 50,000`, then change the comparison to `at least` (`gte`) and rerun. The invoice exactly equal to 50,000 should change from false to true.

## Compare results

Successful runs capture a session-only snapshot of the final report table and executed workflow. After another run, open Compare with an earlier run and choose a previous snapshot.

- Row order and column order do not affect equality.
- Numeric `1` and `1.0` compare equally; boolean true remains distinct from numeric 1.
- Missing values compare consistently, and duplicate rows retain their multiplicity.
- A modified row counts as a removal of the old version plus an addition of the new version. This is a row multiset comparison, not a primary-key change tracker.
- Different column sets are reported as schema changes; row counts are not misleadingly compared across incompatible schemas.
- At most 100 added/removed rows are previewed; full counts remain available.
- The UI notes when input hashes differ, so changes are not attributed solely to edited rules.

Snapshots contain user data in session memory. Up to five final report tables are retained, approximately 20 MB total, with a 4 MB per-report limit. Failed or oversized results are not captured. New workflow retains the snapshots for comparison; ending the session/server clears them. Snapshot tables are independent copies, so subsequent edits do not rewrite history.

Multiple-export workflows can still download every report. The comparison feature currently uses only the final export table.
