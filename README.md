# Prompt Compiler

## Natural Language to Validated Executable Workflows

A local prompt-engineering application that compiles instructions into typed workflows, validates their dependencies, executes predefined document and spreadsheet operations, and produces downloadable reports with an execution trace.

**Current status:** Runnable local application with sample tasks, a model-backed compiler, workflow import/editing, file previews, searchable reports and ZIP exports. Three live development tasks previously passed; broader evaluation remains pending. UI acceptance belongs to the project owner.

## Run on Windows

From this project folder:

```powershell
.\start.ps1
```

The launcher creates a local `.venv` and installs `requirements.txt` if needed, then starts Streamlit at its printed local address. No activation or PowerShell execution-policy changes are needed when running the equivalent commands below:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_app.py
```

If your machine blocks PowerShell scripts, use those commands directly. For an existing environment, skip its creation and dependency installation.

## Try the offline demo

1. Keep **Sample mode** enabled and click **Try sample invoices** if needed.
2. Choose an example, describe the task, and click **Generate plan**.
3. Inspect the compact workflow steps and click **Run workflow**.
4. Review the report beside the plan and download the Excel or CSV file.

The main workspace focuses on the task, source files, plan and final report. JSON editing and run traces are available in expanders. Session run summaries and research methodology have separate sidebar pages.

Upload directly into the drop zone; uploads replace the sample pack. Preview documents or the first 100 table rows locally. Search filters the report preview only; matching rows can be downloaded separately. Download everything packages the executed plan, audit and reports into one ZIP. Saved workflow JSON can be imported and run without model calls when its filenames and columns match the inputs.

Three exact preset instructions are supported offline: flag high-value invoices, filter high-value invoices, and sum totals by vendor. This mode uses fixed workflow templates and deterministic extraction; it does not pretend to understand arbitrary instructions.

## Connect an LLM

Configure your model in the local `.env` file, then turn **Sample mode** off. Credentials, endpoints and model configuration are not rendered as UI fields. See `docs/model-setup.md`. Prior live smoke-test results are in `docs/live-validation.md`; they are not general accuracy claims.

Copy `.env.example` to `.env` only if no local `.env` exists. Set the endpoint, model and key there. Use a Chat Completions-compatible provider with JSON Schema support; set `LLM_STRUCTURED=false` for JSON mode only. Model compatibility varies, including support for `temperature=0`.

Generating a plan with Sample mode off sends the instruction, filenames, table column names and row counts to the locally configured provider. The UI explains this beside the generation button. Uploaded document contents stay local. No web search or arbitrary generated-code execution is available. Keys are not logged, written or displayed by the UI.

Model calls use your provider plan. No live API requests were made during the latest UI/local-feature changes. The latest offline checks also exclude the mock HTTP test, making no HTTP requests at all.

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

## Windows startup

Use `run_app.py` or `start.ps1` rather than invoking Streamlit directly. The launcher selects a Windows socket event-loop policy to avoid the Proactor shutdown callback involved in the reported WinError 10054. This is a targeted mitigation, not suppression of errors. See `docs/troubleshooting.md`. The preset warning is separately fixed by initializing the select box from state without a competing explicit default.

## Project materials

- `docs/project-plan.md`: architecture, experiments, milestones, and review mapping.
- `docs/manual-testing.md`: UI acceptance checklist for the project owner.
- `docs/report-outline.md`: proposed 10-page IEEE report structure.
- `docs/references.md`: official implementation references and literature-search topics.
- `tests/test_engine.py`: execution, validation, export and compiler regression tests.

Team names and experimental findings have not been invented. Keep real invoices, personal data, API keys and local logs out of this public repository.
