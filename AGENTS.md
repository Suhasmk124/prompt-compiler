# Project working instructions

- The project owner performs browser and UI acceptance testing manually. Do not open a browser or run browser/UI automation tests unless they later request it.
- Run meaningful non-browser checks for backend changes, including workflow validation, execution, exports, and compiler correction behavior.
- Use official documentation and trusted package registries for implementation research. Notify the owner before accessing unfamiliar or potentially unsafe websites.
- Keep offline preset behavior clearly labeled. Do not present deterministic sample results as LLM benchmark results.
- Never commit credentials, uploaded invoices, personal data, local environments, or generated run logs.
- Preserve separation between schema validity, semantic workflow checks, execution success, and final-output correctness.
- Keep provider configuration and credentials exclusively in the local `.env`; do not display key, endpoint or model entry fields in the UI.
- Make live model/API requests only when explicitly authorized for the current task. The owner authorized the new PDF integration check; this does not permit automatic startup requests or live calls from regression tests.
- The product has no offline compiler mode. New plans use the configured model; imported plans and local parameter edits do not require regeneration. Keep deterministic test fixtures isolated from product behavior.
