# Fresh PDF integration validation

On October 29, 2026, a new fictional one-page invoice was generated and visually inspected. It contains a supplier header, buyer, item table, subtotal, GST and amount due; it is not one of the original text fixtures.

- Source: `examples/pdf/cedar_coast_invoice.pdf`.
- Supplier: Cedar & Coast Office Systems.
- Subtotal: INR 61,800.00.
- GST at 18 percent: INR 11,124.00.
- Amount due: INR 72,924.00.

## Gap found before the live run

The parser initially returned a missing total because it did not recognize Amount due. The extractor was extended to recognize that standard label. Conflicting Total and Amount due values still produce needs_review rather than a silently chosen amount. Regression tests cover both cases.

## Live check

The configured Groq `openai/gpt-oss-20b` model compiled a new instruction to extract fields, preserve the invoice, flag totals above INR 70,000 and export an Excel workbook. The planning-and-feedback strategy required no correction retries.

The generated workflow validated and executed. The exported workbook was reopened and checked: supplier, INR currency, 72,924 total and true review flag all matched the PDF. The subtotal and tax were not mistaken for the final amount.

The same generated plan was then reused without further model calls:

1. Changing the threshold to 75,000 produced a false flag.
2. Report comparison identified one added row version and one removed row version.
3. Rebinding the read step to a renamed PDF preserved the correct extraction and execution.

The compile reported 2,956 prompt tokens and 2,540 completion tokens across decomposition and generation. Full traces, workflow and workbook are under ignored `outputs/pdf-live-validation/`. No key is recorded there or in this document. No browser tests were performed.

This is one synthetic integration check, not a held-out benchmark or evidence of universal invoice understanding. Text-based PDF extraction remains deterministic and supports labeled invoices; scanned PDFs and arbitrary invoice layouts are outside current scope.

## Reproduce explicitly

```powershell
.\.venv\Scripts\python.exe scripts/validate_pdf_live.py
```

This command makes model requests using the local `.env`. It is not run by tests or at app startup. Regenerating the example PDF uses `scripts/create_example_invoice.py` and requires reportlab as an authoring dependency, not an app dependency.
