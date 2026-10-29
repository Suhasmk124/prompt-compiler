# Project plan

## Research question

Does task decomposition with schema validation and bounded correction feedback improve workflow and output correctness over one-shot generation on held-out tasks?

## Architecture

Instruction + uploaded-file inventory -> optional operation decomposition -> schema-constrained generation -> graph and column validation -> bounded feedback correction -> user inspection -> deterministic execution -> export verification and audit.

The typed workflow is the intermediate representation. Read nodes bind input names; transform nodes consume earlier node outputs; export nodes are terminal. The compiler never generates arbitrary executable code. Validation and execution are separate so the same workflow can be inspected, edited, saved and rerun.

## Implemented first milestone

- Discriminated node schemas, graph validation and schema propagation.
- CSV/XLSX/document reading; labeled invoice extraction; predicates, arithmetic, grouping, selection and sorting.
- Memory-based Excel/CSV exports and per-node execution traces.
- Offline preset mode and configurable LLM compilation with three strategies.
- Editable workflow UI and explicit execution.
- Controlled compiler tests and deterministic development benchmarks.

## Remaining research work

1. Conduct and document a literature survey on natural-language planning, structured generation and feedback-guided correction.
2. Expand beyond the three development fixtures to a manually verified task corpus. Include simple tasks, multi-step tasks, ambiguous requests, unsupported requests, and failure cases.
3. Split by instruction template before prompt tuning. Keep test tasks and gold outputs separate from development feedback.
4. Fix a model, sampling configuration, schema, retry budget, and prompt versions. Run each strategy on identical tasks and repeat when evaluating variability.
5. Measure first-attempt validity, final validity, operation/parameter correctness, execution success, reference output correctness, automatic retries, actual human edits, latency and cost.
6. Inspect failures and report negative findings. No guaranteed improvement is assumed.

The starter benchmark checks key operations and parameters but does not establish general semantic equivalence. Its output gold checks must be expanded to the full selected task scope before making final research claims.

## Review mapping

The supplied UE24AM343AB5 guidelines specify four-person teams, three reviews, and a 10-page IEEE-format report.

| Review | Guideline focus | Project evidence |
| --- | --- | --- |
| R1 | Idea and literature survey | Problem, scope, research question, reviewed sources |
| R2 | High-level design and data collection | Schema, compiler/executor architecture, dataset manifest and baseline |
| R3 | Final demo | UI acceptance, live-model experiments, comparisons, limitations |

The document lists September 21–28, October 19–25 and November 16–21, without a year. Confirm the applicable dates with faculty; do not assume a fresh 12-week window.

## Suggested four-person ownership

1. Workflow schema, compiler, prompt variants and correction loop.
2. Operation executor, input adapters and output checks.
3. Task dataset, reference outputs, evaluation and error analysis.
4. UI acceptance, documentation, presentation and report integration.

## Completion criteria

The initial runnable app is not the final academic submission. Completion requires owner-run UI verification, configured live-model trials, a held-out benchmark, actual measured results, literature survey, presentation and the IEEE report.
