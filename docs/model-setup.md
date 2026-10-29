# Free model setup

Recommendation for initial development: GPT-OSS 20B on Groq, model ID `openai/gpt-oss-20b`.

It is a hosted open-weight model with a free API plan and strict structured-output support. This is a suitability recommendation based on the API contract, not a claim of measured accuracy on our task dataset. Live-model evaluation is still required.

## Configure

1. Create an API key in your own Groq account: https://console.groq.com/keys
2. In Prompt Compiler, select **Connected model**, then **Groq** in the sidebar.
3. Leave the default endpoint `https://api.groq.com/openai/v1` and model `openai/gpt-oss-20b`.
4. Enter your key in the password field, keep strict structured output enabled, and acknowledge sending your instruction and file metadata.
5. Start with **Workflow preferences → Standard**. This uses one model request per compilation; Plan first uses two, and self-correction can use additional requests.

Alternatively copy `.env.example` to `.env` locally and fill in `LLM_API_KEY`. Never commit the real `.env`. The UI does not save entered keys to disk. No Groq account, key, billing plan, or paid upgrade is created automatically by this app.

## Limits checked October 29, 2026

Groq's published free-plan table lists 30 requests/minute, 1,000 requests/day, 8,000 tokens/minute and 200,000 tokens/day for this model. Account-specific limits can differ. Tokens include sizeable schemas and outputs, so 1,000 requests/day does not mean 1,000 complete workflows/day. Expect to pace bulk experiments and check your actual remaining quota.

Strict-mode calls send the schema once through response_format. JSON-mode calls include it in the prompt. Both still undergo local validation. HTTP 429 errors are surfaced as quota/rate-limit messages rather than hidden paid fallbacks.

## Alternative

Gemini 3.1 Flash-Lite also has a free API tier. Google directs developers to AI Studio for active project-specific quotas, so do not rely on old requests-per-day numbers. Its free tier may use submitted content to improve Google's products. Use synthetic data for project evaluation. Switching providers requires an appropriate compatible endpoint and testing their supported schema subset.

## Official references

- Groq limits: https://console.groq.com/docs/rate-limits
- Groq structured output models: https://console.groq.com/docs/structured-outputs
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini limits: https://ai.google.dev/gemini-api/docs/rate-limits
