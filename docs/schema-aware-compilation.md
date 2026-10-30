# Compiling changing user requests

The application generates workflows from the current instruction and current uploaded schema.
It has no fixed payment/city workflow, column-alias table, or matching prompt-to-preset fallback
in the product. The same registered operations can act on different table domains and fields.

## Compilation stages

1. Build metadata locally: file names, column names, inferred column types, row counts and input kind.
   Do not send cell samples or document text. All-blank or mixed-type data may have imperfect inferred
   types; these are hints, not a guarantee of input quality.
2. Send the user request, metadata and the general operation catalog to the configured model.
   Standard uses one generation request. Planning strategies first request a public task checklist.
3. Generate `workflow`, `clarification` and `requirements`. Each requirement quotes the original
   request and links its action to one or more workflow steps. Explicit final fields are recorded
   as `output_columns`; intermediate calculations may leave this list empty.
4. Bind generated input references to the actual schema. Case and separator differences can resolve
   unambiguously, such as a column written with spaces versus underscores. Semantic synonyms remain
   the model's responsibility. Ambiguous names and unknown source columns are never guessed locally.
5. Validate shape, graph, files, columns and output collisions, then the declared task coverage.
   Check request excerpts, step/action links, uncovered transforms and required exported columns.
   Conservative action-word checks catch obvious ignored filters, flags, calculations, grouping,
   sorting and explicit column selection. These checks do not select a workflow from prompt keywords.
6. In feedback mode, validation errors return to the model within the existing bounded retry budget.
   No automatic model switch or unvalidated fallback occurs. A supported workflow advances to review;
   missing intent or unsupported work produces a specific clarification or limitation.
7. Running a reviewed workflow executes registered operations locally. It makes no new model request.

Task coverage is a consistency check on the model's declared interpretation, not a second model judge
or a proof that every possible wording was understood. A mistaken interpretation can still pass these
checks. Broad live evaluation across unseen requests remains necessary.

## General conditions

Conditions work on arbitrary available columns, including derived columns:

- Numeric comparisons: greater/less than, inclusive boundaries, equality and inequality.
- Text equality/inequality and literal contains/not-contains/starts-with/ends-with.
- Missing/present cell checks with `is_null`/`not_null`, using JSON null as the operand.
- AND/OR combinations. Nested expressions can use intermediate boolean flags and later combine them.
- Text matches ignore case and surrounding whitespace by default, preserving original source text.
  A model-generated case-sensitive predicate is reset unless the user explicitly requested sensitivity.
- Null comparisons are explicit; ordinary comparisons with missing cells can produce unknown flags.

The operation catalog also includes chained numeric arithmetic, grouping/aggregates, column selection,
stable sorting and CSV/XLSX exports. Stable chained sorts allow multiple sort keys. Aggregations can
produce separate report branches; combining incompatible schemas or joining measures is unsupported.

## Boundaries and API visibility

Supporting changing prompts does not mean executing arbitrary tasks. Joins, deduplication, OCR,
email, general PDF extraction, date arithmetic, arbitrary code and unregistered operations remain
unsupported. PDF/TXT extraction remains the specialized labeled-invoice extractor. These limitations
are explicit in the model instructions.

The app never calls a provider at startup. New plan generation uses the configured provider; feedback
may make additional calls up to the user's retry limit. API request attempts are counted in the run's
technical details and audit, including failed attempts. Imported workflows and local rule edits use
zero model calls. Keys and endpoint/model configuration stay in the server-side .env.

The implementation checks for this change used local schema, binding, coverage and execution fixtures,
not model/API requests or browser tests. No live-model reliability result is claimed for this revision.
Restart the application and generate a fresh plan to try the updated compiler.
