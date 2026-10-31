# Free model setup

Recommendation for initial development: GPT-OSS 20B on Groq, model ID `openai/gpt-oss-20b`.

It is a hosted open-weight model with a free API plan and strict structured-output support. Three development tasks previously passed with planning and correction enabled; broader held-out evaluation is still required.

## Configure

1. Create an API key in your own Groq account: https://console.groq.com/keys
2. If no `.env` exists, copy `.env.example` to `.env` locally. Configure `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` there.
3. For Groq use `https://api.groq.com/openai/v1`, `openai/gpt-oss-20b` and `LLM_STRUCTURED=false` for the live-verified JSON-output route. Full workflow validation still runs locally.
4. Restart with `.\.venv\Scripts\python.exe run_app.py`. New plan generation always uses your configured model. The app shows configuration status, not credentials or setup fields; no offline-mode toggle exists.
5. Use **Planning preferences → Automatic**, the default. It generates a compact plan, reviews plans and proposed clarifications, and permits up to two bounded corrections. Standard is the no-correction research baseline; planning variants remain available.

Never commit the real `.env` or paste keys into workflow instructions. Credentials are never rendered as browser widgets. No account, key, billing plan or paid upgrade is created automatically.

## Limits checked October 29, 2026

Groq's published free-plan table lists 30 requests/minute, 1,000 requests/day, 8,000 tokens/minute and 200,000 tokens/day for this model. Account-specific limits can differ. Tokens include sizeable schemas and outputs, so 1,000 requests/day does not mean 1,000 complete workflows/day. Expect to pace bulk experiments and check your actual remaining quota.

Strict-mode calls send the schema once through response_format. JSON-mode calls include it in the prompt. Both still undergo local validation. HTTP 429 errors are surfaced as quota/rate-limit messages rather than hidden paid fallbacks.

For a small live smoke test with pacing:

```powershell
.\.venv\Scripts\python.exe -m prompt_compiler.benchmark --live --strategy one_shot --pause-seconds 40 --output outputs/live-one-shot.json
```

This runs the three development fixtures with one-shot prompting. Omit `--strategy` to compare all three approaches. Pauses reduce quota bursts but do not guarantee staying within every account's limits. The API client identifies itself as PromptCompiler rather than using the default Python user-agent, which was rejected by Groq's edge service during initial integration.

## Alternative

Gemini 3.1 Flash-Lite also has a free API tier. Google directs developers to AI Studio for active project-specific quotas, so do not rely on old requests-per-day numbers. Its free tier may use submitted content to improve Google's products. Use synthetic data for project evaluation. Switching providers requires an appropriate compatible endpoint and testing their supported schema subset.

## Official references

- Groq limits: https://console.groq.com/docs/rate-limits
- Groq structured output models: https://console.groq.com/docs/structured-outputs
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini limits: https://ai.google.dev/gemini-api/docs/rate-limits

## Provider HTTP 400 troubleshooting

The adapter classifies known provider error codes without displaying raw response bodies or failed generations. A `json_validate_failed` rejection means the provider rejected the model's generated structured response; it does not by itself mean the API key is wrong. Plan + self-correction can repair these rejections within the existing retry budget. Standard does not retry. Usage reported for rejected generations is unavailable and is not included in local token totals.

A rejected `response_format` or `invalid_json_schema` gets a separate configuration message. If strict schemas are unsupported, set `LLM_STRUCTURED=false` in the local `.env` and restart. This uses JSON mode with the schema in the prompt; local schema and semantic validation still run. The app does not silently switch formats or models. Unrecognized errors remain generic; no arbitrary provider error text is shown.

These error paths are regression-tested with mocked responses, without HTTP requests. A live retry is needed to classify an earlier generic error; its cause cannot be recovered from the old message alone.


## Response budgets and incomplete responses (30 October 2026)

The adapter now sends `max_completion_tokens=4096` explicitly by default. Override it using the
server-side `LLM_MAX_COMPLETION_TOKENS` setting (256–32768). The local `.env` is not changed by the
application. A `finish_reason=length` response or empty content is rejected rather than treated as a
complete planning checklist or executable plan. Larger budgets can increase token usage and quota
pressure; they do not guarantee better interpretation.

Live testing found empty planning outputs with exactly 2,048 reported completion tokens on difficult
requests, alongside provider-rejected structured generations. These observations motivated explicit
budgets; they do not prove that all earlier HTTP 400 errors had the same cause.

Groq documents the response-budget parameter in its [API reference](https://console.groq.com/docs/api-reference)
and retry headers in its [rate-limit guide](https://console.groq.com/docs/rate-limits).

## Provider-format fix — 31 October 2026

Live diagnostics reproduced malformed JSON inside a Groq `json_validate_failed` rejection, while an
identical request could also succeed. This was a response-generation failure before row filtering.
Strict mode is documented as supported by GPT-OSS; do not infer that the model lacks the feature.
The observed issue concerns this application's actual requests.

The active local configuration now uses JSON object output (`LLM_STRUCTURED=false`). Generated
responses contain only title, steps and clarification; version and redundant requirement bookkeeping
are handled locally. Full Pydantic, graph, column, preservation and independent meaning checks remain.
The provider schema is limited to basic structure/enums; local validation still enforces patterns and
bounds. No arbitrary JSON repair or fabricated replacement workflow is used.

Groq GPT-OSS defaults to low reasoning effort and a 2048-token completion budget to reduce overhead.
An explicit LLM_MAX_COMPLETION_TOKENS overrides that budget. Other providers do not receive the
Groq-specific reasoning option. Budget selection does not guarantee staying inside every quota.

If strict mode is deliberately enabled and generation is rejected, feedback mode can use a JSON-mode
repair on a later attempt within the existing correction budget. The request is counted and the format
change recorded. One-shot never makes a hidden repair request. Provider/quota failures remain explicit.

Official references: [Structured outputs](https://console.groq.com/docs/structured-outputs),
[reasoning effort](https://console.groq.com/docs/reasoning).
