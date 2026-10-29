# Manual UI acceptance

Browser testing is reserved for the project owner. These checks have not been performed by the coding agent.

## Offline first run

1. Launch the app and verify the four tabs and sidebar are readable.
2. Compile the default Invoice review example using synthetic samples.
3. Inspect the four workflow nodes. Execute and open Results.
4. Verify four rows with flags false, true, false, true. Exactly 50,000 is not flagged; 50,001 is flagged.
5. Download the workbook, open it in Excel, and check vendor names, totals and flags.
6. Try High-value invoices: expect only 50,001 and 75,000 in the CSV.
7. Try Vendor summary: expect Acme Supplies = 100,001 and Delta Labs = 87,500.

## Editing and errors

1. Change `gt` to `gte` in workflow JSON and execute. The 50,000 row should now be flagged.
2. Change the input column to a nonexistent column. Execution must be disabled and validation must explain the problem.
3. Make a source reference point to a later node. Expect validation failure.
4. Change instruction, files, strategy or provider settings. Old reports must disappear.
5. Enter a custom instruction in Offline demo. Expect an explicit unsupported-preset message.
6. Upload a labeled invoice with a missing total: flag output should be blank/unknown and extraction_status should be needs_review.
7. Upload a USD invoice for the INR threshold task. Expect an explicit execution error, no downloadable partial report.
8. Download workflow and audit JSON; inspect their contents.

## Connected model

1. Configure a supported model and provider. Verify that compile stays disabled until endpoint acknowledgment.
2. Try a custom CSV task using actual uploaded columns, such as multiplying quantity by price then grouping revenue by vendor.
3. Inspect the workflow rather than assuming generation is correct. Execute and check the resulting cells.
4. Try an ambiguous or unsupported task and verify a clarification or limitation is shown.
5. Try a wrong key/model/URL and confirm a useful error without displaying credentials.
6. Compare strategies; inspect attempts and token usage. Some providers do not report token usage.

Record any human edits explicitly if used in the final experiment. The UI edit indicator is only a boolean, not a scientific count of corrections.
