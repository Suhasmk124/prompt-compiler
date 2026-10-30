# Free model setup

Recommendation for initial development: GPT-OSS 20B on Groq, model ID `openai/gpt-oss-20b`.

It is a hosted open-weight model with a free API plan and strict structured-output support. Three development tasks previously passed with planning and correction enabled; broader held-out evaluation is still required.

## Configure

1. Create an API key in your own Groq account: https://console.groq.com/keys
2. If no `.env` exists, copy `.env.example` to `.env` locally. Configure `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` there.
3. For Groq use `https://api.groq.com/openai/v1`, `openai/gpt-oss-20b` and `LLM_STRUCTURED=true`.
4. Restart with `.\.venv\Scripts\python.exe run_app.py`. New plan generation always uses your configured model. The app shows configuration status, not credentials or setup fields; no offline-mode toggle exists.
5. Use **Planning preferences → Plan + self-correction**, the live-tested default. Standard uses fewer requests but reliability can differ.

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
