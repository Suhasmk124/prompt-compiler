# Prompt Compiler

## Natural Language to Validated Executable Workflows

A local prompt-engineering application that compiles instructions into typed workflows, validates their dependencies, executes predefined document and spreadsheet operations, and produces downloadable reports with an execution trace.

**Current status:** Working first implementation with an offline invoice demo, an optional Chat Completions-compatible LLM adapter, workflow editing, a deterministic executor, and a development benchmark. Browser/UI acceptance and live-model evaluation are pending.

## Run on Windows

From this project folder:

```powershell
.\start.ps1
```

The launcher creates a local `.venv` and installs `requirements.txt` if needed, then starts Streamlit at its printed local address. No activation or PowerShell execution-policy changes are needed when running the equivalent commands below:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If your machine blocks PowerShell scripts, use those commands directly. For an existing environment, skip its creation and dependency installation.

## Try the offline demo

1. Keep **Offline demo** selected and **Use synthetic sample invoices** enabled.
2. Choose an example and click **Compile workflow**.
3. Open **Workflow**, inspect the steps and JSON, then click **Execute workflow**.
4. Open **Results**, inspect the trace and table, and download the Excel or CSV report.

Three exact preset instructions are supported offline: flag high-value invoices, filter high-value invoices, and sum totals by vendor. This mode uses fixed workflow templates and deterministic extraction; it does not pretend to understand arbitrary instructions.

## Connect an LLM

Copy `.env.example` to `.env` and set your provider base URL, model identifier, and API key, or enter them in the sidebar. Choose **Connected LLM**. Use a Chat Completions-compatible provider with JSON Schema support; switch off strict schema mode if it supports JSON mode only. Model compatibility varies, including support for `temperature=0`.

The UI requires you to acknowledge the configured destination before sending a request. Compilation sends the instruction, filenames, table column names and row counts. It does **not** send uploaded document contents. Document extraction and execution happen locally. No web search or arbitrary generated-code execution is available. Remote providers require HTTPS; localhost HTTP is supported. Keys are not logged or written by the UI.

LLM calls may incur charges. No live API calls were used to validate this implementation; the provider interface and correction loop are tested using controlled responses.

## Supported operations

| Operation | Behavior |
| --- | --- |
| `read` | Read TXT, text-based PDF, CSV, or the first XLSX worksheet; concatenate matching schemas |
| `extract_invoices` | Extract labeled vendor, total, and currency from one invoice per document |
| `filter` | Keep matching rows; fail explicitly if a comparison value is missing |
| `flag` | Preserve rows and add a nullable boolean flag |
| `calculate` | Add, subtract, multiply, or divide numeric columns/constants |
| `aggregate` | Sum, mean, count non-null values, min, or max, with optional grouping |
| `select` / `sort` | Choose columns or order rows |
| `export` | Produce a formula-escaped Excel or CSV report |

Invoice extraction recognizes explicit `Vendor:` or `Supplier:`, `Total:` / `Grand Total:` / `Invoice Total:`, and INR/USD/EUR markers. It is a conservative labeled-field parser, not general invoice intelligence. Missing/ambiguous fields are marked `needs_review`. Invoice threshold comparisons require INR. Currency conversion, scanned PDFs, multi-invoice documents, and unconstrained extraction are not implemented.

## Validation and output checks

Pydantic validates shape and allowed operations; a semantic pass checks files, columns, dependencies, output collisions and graph reachability. Execution uses a fixed registry rather than `eval`, shell commands, or generated Python. Exports use basename-only filenames and neutralize formula-like strings. Export checks verify serialization/dimensions and absence of formulas; they do not prove that the workflow matches every nuance of the instruction.

Inputs are limited to 20 files, 10 MB per file, 30 MB combined, 100 PDF pages, and 100,000 rows per table/result. Files are processed in the app session, not committed or automatically persisted. This is a local educational application, not a hardened multi-user document-processing service.

## Non-browser checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m prompt_compiler.benchmark --offline
```

To explicitly run the three prompt strategies with your configured model:

```powershell
.\.venv\Scripts\python.exe -m prompt_compiler.benchmark --live
```

Reports are saved to ignored `outputs/benchmark.json`, including prompts' responses, validation errors, model identifier, timestamp, token usage, retries, reference checks and traces. The benchmark is a small **development suite**, not a held-out research dataset. Manual correction counts are left unmeasured (`null`), not reported as zero. The UI audit records whether the executed workflow differs from its generated version, not a count of human editing actions. Monetary cost requires applying the provider's actual prices to recorded token usage.

## Command-line execution

Save a workflow from the UI and place inputs in a directory:

```powershell
.\.venv\Scripts\python.exe -m prompt_compiler workflow.json --inputs inputs --output outputs
```

Existing output files are not overwritten. Workflow generation is available in the UI; this command executes an already compiled workflow.

## Project materials

- `docs/project-plan.md`: architecture, experiments, milestones, and review mapping.
- `docs/manual-testing.md`: UI acceptance checklist for the project owner.
- `docs/report-outline.md`: proposed 10-page IEEE report structure.
- `docs/references.md`: official implementation references and literature-search topics.
- `tests/test_engine.py`: execution, validation, export and compiler regression tests.

Team names and experimental findings have not been invented. Keep real invoices, personal data, API keys and local logs out of this public repository.
