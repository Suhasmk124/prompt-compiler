# Invoice demo acceptance criteria

Instruction: Read these invoices, extract vendor names and totals, flag invoices above INR 50,000, and produce an Excel report.

Use synthetic invoices only. Expected report fields: source file, vendor, total, currency, review flag, and extraction status.

- Exactly INR 50,000 is not above the threshold.
- INR 50,001 is flagged.
- A flagged row remains in the report; flagging is not filtering.
- Missing or ambiguous totals are reported explicitly rather than silently treated as zero.
- Non-INR amounts require a defined policy or clarification; do not silently compare different currencies.
- The exported report matches the expected rows, values, and flags.

This is a planned demo specification, not an implemented example.
