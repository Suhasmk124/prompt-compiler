# Studio release — 31 October 2026

## What changed

- A white editorial landing page inspired by the owner's reference: centered serif headline,
  black pill actions, pastel cards and an original CSS workflow illustration.
- Real top navigation, anchored start action, press/hover/focus feedback, responsive styling and
  reduced-motion handling. Browser acceptance remains with the owner.
- Background plan generation, real phase status and cancellation. A late-cancellation guard prevents
  a just-completed or obsolete plan from being installed. Workers do not access Streamlit state.
- Explicit per-column text/number/boolean/date imports, optional missing-value markers and original
  file download. Preview, model metadata, execution and CLI reuse share those rules.
- Bounded Retry-After handling, cancellation during waits and physical provider-attempt counting.
- An Automatic policy: generation and meaning review, with up to two corrections by default and
  no obligatory separate planning call. Genuine questions remain questions; false capability refusals
  can be reviewed and corrected.
- Deterministic rejection of unrequested internal flag columns, independent of model approval.
- Explicit selection of multiple reports and report-named snapshots/comparisons.
- Session-local metadata/preview caching; no automatic persistence of private uploads.
- A 13-case versioned validation corpus, reference checks, budgeted/resumable live runner and
  incremental artifact saving. Research reports retain implementation/corpus hashes.
- Updated CI configuration, owner checklist, literature review and research-report draft.

## Evidence and version separation

The frozen three-case/three-strategy pilot completed nine runs: seven passed and two failed.
Standard leaked an internal flag (the review rejected it); the feedback route incorrectly declared
nested logic unsupported. These failures remain in `outputs/studio-release/live-comparison.json`.
The report records 23 API attempts and is not a blind held-out accuracy benchmark.

A subsequent Automatic validation run found a case where the reviewer approved a leaked helper.
That partial report and its incorrect export are preserved in `automatic-validation.json`. It was
stopped before modifying implementation code. The extra deterministic guard was then added and
covered by local regression tests. Its corrected-build results are recorded separately in
`automatic-validation-v2.json`; consult that report for the final case counts and resource totals.
Do not combine these versions into one accuracy percentage or erase the negative findings.

The second Automatic run completed seven correct table cases, then failed the duplicate-retention
case after exhausting two corrections. A subsequent date-case request hit the provider rate/quota
limit. Thus the saved report has seven passing cases, one interpretation/recovery failure and one
service failure; four other planned cases were not attempted. It used 24 API attempts, 54,305 reported
prompt tokens and 4,382 completion tokens. All successful saved exports used the requested CSV format.

The final patch clarifies last-occurrence deduplication before report sorting, includes the latest
rejected plan in correction feedback, and treats an omitted cosmetic review summary separately from
the mandatory verdict/issues consistency checks. Evaluation now saves individual attempts and checks
export format. These final changes passed local regression checks but have NOT been verified with
the live model. The owner stopped further API checks; the queued follow-up was rejected before starting.

Across the three live reports above, 57 provider attempts were made before that instruction,
with 122,985 reported prompt tokens and 13,009 completion tokens. No additional live model checks
were made afterward. The interrupted first Automatic report is intentionally preserved as partial.

Local verification passed 212 tests, including the localhost adapter, import rules, retry/cancellation,
late-result acceptance, Automatic repair, false-refusal review, helper-column export guards and gold
output checks, review-summary recovery and per-export snapshots. Authored references verified nine tables and two runtime guards without model calls;
the two language-interpretation boundaries are deliberately skipped by reference execution.

## Still requires acceptance or further research

- The owner must run the browser checklist. No agent browser/UI automation or visual verification was performed.
- A separate truly held-out corpus, repeated trials, review ablations and larger domain coverage remain research work.
- The model/reviewer can still misunderstand requests; deterministic checks are intentionally limited.
- Joins, OCR, general document extraction, combined multi-measure summaries and advanced date operations remain unsupported.
- Team details, faculty dates/template, final IEEE formatting and the presentation remain academic submission work.
- GitHub Actions is configured, but its remote execution must be checked after publication.

## Restart

```powershell
cd "C:\Sauce\PEGAI\Prompt Compiler"
.\.venv\Scripts\python.exe run_app.py
```

Generate a fresh plan after restarting. The private key/model remain unchanged; the verified local
provider route uses JSON output with local validation. No API request starts merely by opening the app.
