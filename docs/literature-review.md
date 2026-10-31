# Literature review and project positioning

Prepared 31 October 2026. The sources below are primary papers. This is a focused related-work
review, not a claim that this educational implementation reproduces their full experiments.

| Work | Relevant finding or method | Connection to Prompt Compiler | Important distinction |
| --- | --- | --- | --- |
| Madaan et al., *Self-Refine: Iterative Refinement with Self-Feedback* (2023) | Uses model-generated feedback and iterative revision without additional training | Motivates a bounded generate/check/correct loop | Our corrections also include deterministic validator errors; the paper's reported gains are not our results. [Paper](https://arxiv.org/abs/2303.17651) |
| Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* (2022/2023) | Combines reasoning and actions in interactive environments | Motivates inspectable planning and explicit tool/operation interfaces | Our pipeline compiles before execution; it is not a ReAct agent interacting with external tools during each reasoning step. [Paper](https://arxiv.org/abs/2210.03629) |
| Geng et al., *Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning* (2023; revised 2024) | Formal constraints control structured output; grammars may depend on the input | Supports separating structural validity from downstream task correctness | We do not implement their decoding algorithm. The active integration uses JSON output plus local typed validation. [Paper](https://arxiv.org/abs/2305.13971) |
| Patil et al., *Gorilla: Large Language Model Connected with Massive APIs* (2023) | Studies selecting APIs and generating accurate arguments, including retrieval of API descriptions | Supports providing an explicit current operation catalog rather than assuming tool knowledge | We neither fine-tune a Gorilla model nor evaluate on APIBench. Our operation registry is much smaller and locally executed. [Paper](https://arxiv.org/abs/2305.15334) |
| Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet* (2023/2024) | Reports limits of intrinsic reasoning correction without external feedback, including possible degradation | Motivates independent expected-output tests rather than trusting a model approval alone | The result concerns the paper's studied settings. It does not establish universal failure of all correction methods or predict this project's accuracy. [Paper](https://arxiv.org/abs/2310.01798) |

## Research gap addressed by the project

The project examines whether natural-language instructions can be translated into a small typed
workflow over uploaded tabular data, and whether decomposition and bounded feedback help that
translation. It prioritizes correct operation arguments, source-column binding, boolean conditions,
record preservation and actual exported results. A syntactically valid workflow is insufficient.

The practical contribution is the integration of a schema-aware compiler, local execution registry,
independent acceptance review, import controls, an inspectable workflow UI and an output-based
validation harness. These are engineering contributions to a mini-project, not a claim to invent
decomposition, constrained generation or iterative correction.

## Experimental implications

1. Hold the provider, model, prompts, schema, import rules and correction limit fixed within a report.
2. Apply the same acceptance review to all three strategies in the current comparison. Standard
   therefore means one generation plus review, not a single total API request.
3. Measure actual final tables and reopened exports against independent expected data.
4. Report runtime-guard and clarification cases separately from successful table-output cases.
5. Preserve failures. Do not tune on evaluation failures and continue calling the same cases held out.
6. Repeat trials and expand the corpus before making statistical or generalization claims.
7. A future ablation should compare review enabled/disabled separately; the current three-strategy
   pilot does not isolate the review's causal effect.

## Source scope

This review relies on the papers' primary abstracts and bibliographic records for the descriptions
above. Detailed experimental reproduction and a full university-formatted bibliography remain part
of final report preparation. No performance percentages from these papers are transferred to this app.
