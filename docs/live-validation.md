# Live integration check October 29 2026

Provider: Groq. Model: `openai/gpt-oss-20b`. Mode: strict structured outputs. Strategy: decomposition with bounded validation feedback (`feedback`). Dataset: the three synthetic invoice development fixtures, not a held-out research benchmark.

| Task | Valid workflow | Execution | Reference output | Automatic retries |
| --- | --- | --- | --- | --- |
| Invoice review | Pass | Pass | Four rows, flags false / true / false / true | 0 |
| High-value invoices | Pass | Pass | Only totals 50,001 and 75,000, with correct vendors | 0 |
| Vendor summary | Pass | Pass | Acme Supplies 100,001; Delta Labs 87,500 | 0 |

Two API calls per task (decomposition and generation); no human edits to the generated workflows. This is an integration smoke test, not a general accuracy or robustness claim. No browser/UI tests were performed.

## Issues found and corrected

- The default Python user-agent was rejected by the provider edge service with HTTP 403 / code 1010. An explicit PromptCompiler user-agent succeeded.
- Initial prompts did not clearly distinguish source-document labels from extracted output column names. The compiler now specifies exact lowercase output columns.
- The model asked for invoice currency confirmation even though the executor already enforces currency preconditions. The prompt now separates runtime validation from missing user intent.
- Reference checks now accept equivalent generated flag/aggregate column names and unspecified row ordering, while still checking actual values and required export format.

Earlier one-shot development runs had failures; they are not included in the success table above. Standard/one-shot is an experimental baseline, not implied to achieve these feedback-mode results. A broader held-out comparison remains future work.

## Local evidence

Full live run details are in ignored `outputs/live-feedback.json`. Re-executing the saved live-generated workflows produced Excel/CSV files under ignored `outputs/live-verified-reports/`. These artifacts and the real `.env` are excluded from Git. No credentials are included in this document.

The non-browser regression suite contains 28 passing tests, including the HTTP client contract, bounded correction, threshold boundaries, and equivalent-output evaluation.
