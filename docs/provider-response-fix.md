# Provider response fix — 31 October 2026

## Failure identified

An authorized live diagnostic of the failing Karnataka/UPI request received HTTP 400 with
`json_validate_failed`. The provider supplied a rejected 2,035-character generation that was
not syntactically valid JSON (parser stopped at character 486). No raw provider response or
credentials were displayed. An identical request could also succeed, demonstrating intermittent
response generation, not a deterministic failure of the row predicate.

The strict-schema route still rejected a request after response simplification. Groq documents
strict structured output as supported by this model, so this evidence does not establish a general
lack of model support. It establishes that this application's observed strict requests were unreliable.

## Active fix

- Set the local `LLM_STRUCTURED=false`, preserving the model and API key. This uses JSON-object
  output and full local validation instead of the failing provider-side complex-schema route.
- Generate only `title`, `steps`, `clarification`. Adapt the compact response locally to versioned
  workflow JSON. Redundant generated requirement bookkeeping is removed from the wire response.
- Keep complete local type, bounds, pattern, graph, column and row-preservation checks. Transport
  constraints are simpler, but local validation is not weakened. Reject partial or malformed output.
- Keep the independent meaning review against the original request and actual workflow.
- For Groq GPT-OSS only, use low reasoning effort and default to a 2,048-token completion budget.
  Explicit server configuration can override the completion budget. Other providers do not receive
  the Groq-specific reasoning field.
- Default the UI to Standard generation plus meaning review. Planning and self-correction remain
  available, and their extra requests are counted.
- If strict mode is explicitly selected and generation is rejected, feedback can switch to a JSON
  repair request within the existing retry budget. No hidden request is made in one-shot mode.

No model change, paid upgrade, generated-code execution, handwritten replacement workflow or
special Karnataka/UPI field mapping was introduced.

## Live evidence

Both final checks used the active JSON route and low reasoning setting. The verification script
paced requests to respect the free-tier token window. Durations include that wait and should not
be reported as model latency. The browser was not used.

| Check | Requests | Correction retries | Verified output |
| --- | --- | --- | --- |
| Filter vendors from Karnataka and payment type UPI, using the 244-row/78-column CSV | 2: generation + review | 0 | Exactly 10 matching invoice IDs; all 78 original columns; XLSX reopened and checked |
| Calculate quantity × unit cost, sum by division, sort descending, export CSV | 2: generation + review | 0 | North=90, South=40; two rows/two columns; CSV reopened and checked |

The invoice filter's 10 matching rows belong to one vendor. A plain filter preserves those 10 rows;
an explicitly requested distinct-vendor result would instead contain one vendor.

Local evidence folders, ignored by Git:

- `outputs/critical-provider-fix-20261031/verified-one_shot-json-1793432730022171200/`
- `outputs/critical-provider-fix-20261031/verified-summary-one_shot-json-1793432839281142200/`

Each contains the actual generated workflow, compilation/review evidence, summary and report.
The invoice run reported 5,667 prompt + 332 completion tokens; the calculation run reported
4,467 prompt + 358 completion tokens. Diagnostics and failed requests are additional usage and
may not report tokens; these numbers are not a complete billing total.

Two passing live checks are smoke tests, not a held-out accuracy measure or a guarantee about
future wording, quota availability, or model outputs. Broader evaluation remains separate work.

References: [Groq structured output](https://console.groq.com/docs/structured-outputs) and
[Groq reasoning effort](https://console.groq.com/docs/reasoning).
