# Versioned validation corpus

`corpus_v1.json` contains 13 small synthetic cases with authored expected outputs or expected
boundary behavior. Cases cover repeated-entity preservation, nested boolean flags, arithmetic and
grouping, missing fields, threshold boundaries, text identifiers, literal text matching, duplicate
retention, calendar differences, ambiguity, unsupported joins and runtime numeric failures.

These are validation cases. They are not a blind held-out test set and must not be advertised as
general real-world accuracy. Reference workflows check the executor; they do not measure the LLM.
Expected tables are checked independently of model-authored requirement declarations.

## No-network checks

```powershell
.\.venv\Scripts\python.exe -m prompt_compiler.evaluate --local --output outputs/reference-checks.json
```

This executes authored reference plans, verifies nine table outputs and two runtime guards, and
skips the two cases that require model interpretation. It makes zero provider requests.

## Explicit live comparison

```powershell
.\.venv\Scripts\python.exe -m prompt_compiler.evaluate --live --case expense_and --case nested_flag --case grouped_cost --strategy all --retries 1 --max-requests 30 --pause-seconds 35 --output outputs/comparison/report.json
```

All strategies use the same configured model and acceptance review. Standard normally uses two
requests; planning strategies normally use three before corrections. The request budget is checked
before each external call. Pacing is included in wall time and recorded separately, not presented
as model inference latency.

Reports record SHA-256 hashes of the corpus and core implementation. Completed cases are saved
incrementally with workflows and reopened report checks. Existing reports are not overwritten unless
resumption is explicit; corpus and implementation revisions cannot be mixed in the same report.
Rate-limit failures stop the runner. Preserve partial/failed results and disclose incomplete runs.

For research, reserve a separate unseen corpus before further prompt tuning, repeat trials, include
more domains/paraphrases and annotate manual corrections rather than inventing zeros.
