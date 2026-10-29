# Prompt Compiler

## Natural Language to Validated Executable Workflows

A prompt-engineering mini project that translates plain-English instructions into structured workflows, validates their steps and dependencies, executes supported operations, and checks the final output.

**Status:** Project planning and repository setup. The compiler and executor are not implemented yet.

## Example

> Read these invoices, extract vendor names and totals, flag invoices above INR 50,000, and produce an Excel report.

Planned workflow: read documents -> extract structured records -> flag totals above the threshold -> export an Excel report -> validate output.

## Initial scope

Focus on document and spreadsheet workflows with a small registry of supported operations: read files, extract fields, filter or flag records, calculate values, and export reports. Unsupported or ambiguous requests should produce a clarification or validation error.

## Planned architecture

1. Interpret the instruction and identify required operations.
2. Generate a workflow in a constrained JSON format.
3. Validate operation names, parameters, field types, references, and dependency order.
4. Use validation feedback to revise invalid workflows within a fixed retry budget.
5. Execute validated nodes through predefined functions.
6. Check outputs and display the workflow, execution trace, and downloadable result.

The model produces a workflow specification. The executor runs predefined operations rather than arbitrary generated code.

## Prompt engineering experiments

Compare one-shot workflow generation, decomposition followed by generation, and decomposition with validation feedback. Hold the model, supported operations, task set, and inference settings constant; report retry budgets and costs separately.

Measure schema validity, workflow correctness, execution success, final-output correctness, correction attempts, manual interventions, latency, and token cost. Separate simple tasks from multi-step tasks and reserve held-out tasks before tuning prompts.

## Proposed stack

Python, Pydantic or JSON Schema for validation, pandas and openpyxl for tabular processing, a configurable LLM provider, and Streamlit for the demo. Confirm and pin compatible dependencies during implementation.

## First milestones

- Define the workflow schema and operation registry.
- Create synthetic invoice examples and reference outputs.
- Implement a deterministic executor and output checks.
- Add the baseline prompt and validation-feedback loop.
- Build the demo and run controlled experiments.

## Repository contents

- `docs/project-plan.md`: implementation and evaluation plan.
- `examples/invoice-task.md`: target demo and acceptance criteria.

No experimental results are claimed yet. Keep credentials, real invoices, and personal data out of this public repository.
