# Live system review â€” 30 October 2026

This review uses the configured provider with explicit owner authorization, synthetic inputs, and
local expected-output checks. It is a development acceptance run, not a held-out accuracy benchmark.
Browser/UI testing remains with the owner. No commit or GitHub push is authorized by this review.

## Fixes prompted by testing

- Validate original CSV/XLSX headers before the parser silently renames duplicates or blank headings.
- Reject export filenames that collide ignoring case, preventing Windows output collisions.
- Preserve literal NA, N/A and NULL input text. Empty cells still represent missing values.
- Clarify that requirement output_columns lists final requested fields, not source/intermediate schemas.
  Correction feedback now explains model-declared metadata errors rather than presenting them as new
  requirements for the user to resolve.
- Accept compound operation names (`flag_rows`, `filter_rows`) in requirement links, with the same action validation as their simple aliases.
- Reject truncated/empty provider responses and make the output-token budget explicit (default 4096).
- Regenerate corrections from the original request plus the latest errors rather than accumulating rejected JSON; classify HTTP 413 separately.
- Distinguish duplicate-group retention wording from an actual request for aggregation.

## Next improvements, in priority order

1. **Explicit import types and previews.** Automatic inference still turns a CSV identifier such as
   001 into numeric 1. Allow text/number/date choices per column before compilation, preserve the raw
   source, and make missing-value rules visible. This is a data-correctness issue, not just appearance.
2. **Provider resilience and clear outcomes.** Respect Retry-After with bounded, cancelable retries;
   distinguish rate limits, unsupported requests, missing user intent and invalid generated plans.
   Avoid making users re-enter a task because the provider temporarily refused a request.
3. **Independent semantic evaluation.** Build a versioned, held-out corpus with exact expected outputs
   across domains. Check requested predicates, AND/OR relationships, selection and sort direction;
   model-authored coverage declarations alone do not prove correct interpretation. Repeat cases to
   measure variability and compare strategies at fixed model/retry settings.
4. **Continuous regression checks.** Replace the placeholder CI workflow with real local-only tests.
   Keep paid/live tests explicit and separate, with request/token budgets and secret-safe results.
5. **Broader table functionality.** Add joins with explicit keys/cardinality checks and output-size
   limits, multiple summary measures, and richer date operations. Test these end to end before
   expanding the advertised capabilities. OCR/general document extraction remains a separate effort.

## Other backend checks

A saved live-generated plan was imported, rebound to a renamed input, executed with equivalent
results, and bundled into a valid ZIP. CLI execution created the report and a repeat run refused to
overwrite it without changing the existing file. These checks made no additional model calls.

## Reproduce explicitly

```powershell
.\.venv\Scripts\python.exe scripts/validate_system_live.py --live --root . --output outputs/system-review --retries 1
```

This command makes real model calls. It uses synthetic cases, checks actual tables and reopened
exports, waits 65 seconds between provider requests, saves each completed case, and stops on a
quota/access failure. It never runs on app startup. Compilation durations include deliberate pacing;
they are not pure model-latency measurements. Failed provider generations may not report token usage.

The final live outcomes and local test counts are recorded below.


## Observed results

These are the latest observations per scenario across several development revisions and settings,
not a single fixed-version benchmark or a reliability percentage. A passing supported task required
matching the expected table and reopening the exported CSV/XLSX. The two boundary cases required
a specific, appropriate clarification. No browser checks were performed.

| Scenario | Latest outcome | Strategy / correction budget |
| --- | --- | --- |
| Deduplication + date differences | Pass | feedback / 1 |
| Nested AND/OR flags | Pass | feedback / 0 |
| Calculation + grouped summary | Pass | one_shot / 0 |
| Missing-date filter + selected columns | Pass | feedback / 0 |
| Remove every duplicate group | Pass | feedback / 0 |
| Unsupported join | Pass | feedback / 1 |
| Ambiguous amount column | Pass | feedback / 1 |
| PDF extraction + threshold flag | Pass | one_shot / 0 |

The planning-mode summary attempt was rejected by the provider; Standard (one-shot) subsequently
produced the expected Ready=120 and Hold=40 totals. Do not infer that either strategy is universally
better from one comparison. The latest planning-mode retests used zero corrections to bound usage;
the full default correction budget has not been re-evaluated across all cases after the final fixes.

138 local tests passed, including provider/error mocks and the localhost HTTP adapter test. Syntax
and patch checks passed. Local tests are separate from these model-driven output checks.

Saved reports account for 51 request attempts, 86,575 reported prompt tokens and 44,119 reported completion tokens. These exclude an interrupted run and token usage unavailable for rejected responses; they are not a complete billing total. No cost claim is made.

The reproducible evidence and successful saved workflows/reports are in `outputs/system-review-20261030/`. Earlier failures are preserved alongside later results. No changes have been committed or pushed.
