# Project plan

## Research question

Does task decomposition with schema validation and bounded correction feedback improve held-out workflow and output correctness over one-shot generation?

## Build order

1. Specify node IDs, operation names, typed parameters, input references, and outputs. Reject cycles, missing references, invalid fields, and unsupported operations.
2. Implement predefined operations and validate their inputs and outputs. Keep file access within the selected input and output directories.
3. Create synthetic fixtures and manually verified expected outputs. Include threshold boundaries, missing fields, malformed values, empty inputs, and ambiguous instructions.
4. Add structured workflow generation and record baseline results.
5. Add decomposition and validation feedback with bounded retries. Preserve prompt versions and execution traces.
6. Add a visual workflow, node status display, and downloadable reports.
7. Evaluate on held-out tasks and assemble the presentation and report.

## Evaluation design

Split by instruction template before prompt tuning to reduce leakage. Compare the same tasks across all conditions. A valid JSON workflow can still be semantically wrong; a successful execution can still produce an incorrect report. Measure each separately.

Use deterministic reference checks for filters, calculations, flags, and exported cells. Define manual correction as a human edit to the generated workflow or instruction needed to complete the task; distinguish this from automatic retries. Report ambiguity and unsupported-task handling separately.

## Deliverables

Problem statement and literature survey; workflow schema and architecture; synthetic benchmark and reference outputs; baseline and correction pipelines; interactive demo; reproducible evaluation; final report.

## Scope boundaries

Start with text-based documents and CSV/XLSX inputs. Scanned-image OCR, arbitrary web automation, external account integrations, and general-purpose code execution are stretch goals outside the first version.
