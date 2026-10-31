# Prompt Compiler

Turn natural-language instructions into reviewed, executable workflows over your files.
A local Streamlit application for a prompt-engineering mini-project: schema-aware planning,
validation, bounded correction, deterministic execution and output-based evaluation.

## Run

```powershell
cd "C:\Sauce\PEGAI\Prompt Compiler"
.\.venv\Scripts\python.exe run_app.py
```

For first-time setup, `start.ps1` creates the environment and installs `requirements.txt`.
Use the launcher rather than invoking Streamlit directly on Windows. Stop an old server with
Ctrl+C before restarting. Provider settings stay in the local `.env`; never commit its key.

## Workspace

The white studio landing page opens into a progressive Describe → Plan → Result flow.
Navigation, keyboard focus, button press states and reduced-motion behavior are supported.
The interface is inspired by the owner's landing-page reference, with a code-built workflow
illustration; it uses no external fonts, images, trackers or fabricated performance statistics.
Browser acceptance remains with the owner.

1. Upload CSV, XLSX, TXT or a selectable-text PDF and describe the desired outcome.
2. Optionally configure each table column as text, number, boolean or an explicit date format.
   Preview, model metadata and execution use the same import rules. Original bytes are preserved.
3. Generate a plan. The interface stays responsive with real phase updates and a cancel control.
4. Review or edit the plan, run it locally, then search/download/compare its reports.

A plain filter keeps every matching source record. Asking for vendors/customers/products does
not by itself request deduplication. Flagging preserves rows and adds a boolean column.
Text comparisons are case-insensitive by default; the original cell values stay unchanged.

## Generation and provider behavior

New plans use the actual configured model. There is no product offline mode or preset fallback.
The model receives instructions and file metadata, not raw rows or document contents. It chooses
fields, predicates, boolean relationships and operations. Local code applies that plan to all rows.

The default Automatic approach generates a compact plan, independently reviews its meaning, including proposed clarifications, and
allows up to two bounded corrections if rejected. A normal successful plan uses two provider requests;
corrections and explicit rate-limit retries can add calls. Standard, Plan first and Plan +
self-correction remain available. API attempts and reported tokens appear in the audit.

The local tested configuration is Groq GPT-OSS 20B with `LLM_STRUCTURED=false` (JSON output).
Full local schema/graph/column checks remain enabled. See [model setup](docs/model-setup.md).
The provider has bounded, cancelable Retry-After handling in the interactive application.
Cancellation cannot undo a request already sent; it prevents later calls and discards the result.

## Operations and boundaries

- Read files and concatenate compatible schemas.
- Filter or flag with single/compound conditions; numeric comparisons, literal text matching,
  missing-value checks, AND/OR and composed nested conditions.
- Add/subtract/multiply/divide numeric fields, group and aggregate one measure per operation.
- Select columns, stable sort, deduplicate with explicit retention and calculate calendar-day differences.
- Extract labeled invoice fields from one invoice per TXT/text PDF document.
- Export formula-escaped CSV/XLSX; save/import/rebind workflow JSON; adjust rules locally.
- Search results, download ZIP/audit bundles and compare session snapshots, including duplicate counts.
- Select among multiple exported reports; preview and comparison are tied to that report.

Not implemented: joins, OCR, general document extraction, multi-invoice PDFs, combined multi-measure
summaries, timezone/business-day arithmetic, charts or external actions. No generated Python/eval/shell
execution exists. Unsupported tasks must produce a specific limitation rather than a fake result.

Limits include 20 files, 10 MB each, 30 MB total, 100 PDF pages, 100,000 rows per table/result and
200 columns. This is a local educational tool, not a hardened public multi-user service.

## Tests and evaluation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m prompt_compiler.evaluate --local --output outputs/reference-checks.json
```

The versioned [validation corpus](evaluation/README.md) includes 13 cases, authored gold tables,
runtime guards and clarification boundaries. Reference checks make no model calls. Explicit live
runs compare real outputs/reopened exports, count requests/tokens and save corpus/implementation hashes.
The live pilot is development validation, not held-out accuracy. See the release results notes.
GitHub Actions is configured for backend tests and reference checks; a remote run must be confirmed
separately after publication.

The older three-invoice benchmark remains a development fixture harness, not the final research dataset.
Model-authored declarations or a model review alone do not prove correctness.

## Saved-plan CLI

```powershell
.\.venv\Scripts\python.exe -m prompt_compiler workflow.json --inputs inputs --output outputs --import-settings import_settings.json
```

`--import-settings` is optional. Existing reports are not overwritten.

## Documentation

- [Import rules and recovery](docs/import-and-recovery.md)
- [Owner acceptance checklist](docs/acceptance-checklist.md)
- [Literature review](docs/literature-review.md)
- [Project plan](docs/project-plan.md) and [IEEE report outline](docs/report-outline.md)
- [Provider response fix and prior evidence](docs/provider-response-fix.md)
- [Workflow reuse](docs/reusing-workflows.md)

Academic completion still requires broader/repeated independent evaluation, owner UI acceptance,
team-specific details, presentation and the faculty-formatted IEEE report. Do not invent measured
accuracy, manual corrections, cost or research improvements. Keep private inputs and run logs out of Git.
