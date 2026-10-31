# Filter preservation and light theme — 30 October 2026

## Reported problem

The owner requested vendors from Karnataka with payment type UPI and saw one result despite
expecting multiple invoice rows. In the synthetic 244-record CSV created in this chat, those two
predicates match **10 invoice rows belonging to one distinct vendor**. Returning unique vendor
names would therefore explain the one-row result. The specific failed generated workflow was not
provided, so this is a strong diagnostic lead, not a confirmed reconstruction of that run.

The saved system-review runs show real provider requests. Earlier failures included quota limits,
provider-rejected JSON and the compiler rejecting the generator's coverage metadata. Later saved
plans did execute and produce checked outputs. These historical results do not prove that the
owner's new prompt was interpreted correctly.

## Changes

- Restore the previously accepted light stylesheet and Streamlit light configuration. Preserve
  the other chat's backend additions, including deduplication, calendar date differences, source
  header checks, literal NA handling and provider-response fixes.
- A plain filter must preserve every matching input row, including repeated entities, and original
  columns. Naming vendors/customers/products does not request distinct names, a summary, or only
  that entity's name column. Explicit unique/deduplication, aggregation or column-selection requests
  remain supported.
- Add an independent model review of the original request, uploaded schema and actual candidate
  workflow. Review source-field meaning, predicates, values, AND/OR grouping, row reduction and
  output selection. The reviewer does not receive the generator's coverage declarations as proof.
- Reject unrequested deduplication/aggregation/column narrowing in a plain filter locally. Broader
  semantic mismatches rejected by the reviewer are fed back within the configured correction budget.
- When independent review is enabled, malformed generator-authored coverage metadata becomes a
  diagnostic warning rather than overriding a correctly reviewed executable plan. Structural checks,
  local action guards and the independent meaning review still gate acceptance.
- Do not accept an unreviewed plan if the review fails, is malformed or hits a provider/quota error.
  Provider failures during review stop further requests instead of silently continuing or retrying
  generation against an exhausted quota.
- Show model request counts and review status in Plan. Show input/output row counts for filters and
  deduplication in Result and the execution trace.
- Preserve leading-zero and long numeric identifiers during CSV/XLSX import rather than converting
  them destructively before matching. Full per-column import-type controls remain future work.

## Role of the LLM

The LLM interprets the instruction and chooses source fields, operators, values, boolean relationships
and workflow steps. A separate model request checks that interpretation. Local code applies the
reviewed predicates to the actual records and writes the report. The model is not asked to manually
list or copy every matching row, and complete document contents/cell samples are not sent.

This remains a model-based interpretation, not a guarantee that every possible wording is understood.
The reviewer can also make mistakes. Broad independent expected-output evaluation is still required.

## API accounting and testing

No live provider calls were made while implementing these changes. The owner retains live-model
and browser acceptance testing.

Normal product generation now includes a separate semantic-review request: Standard normally uses
two provider requests, and planning strategies normally use three before corrections. Each corrected
valid candidate may need another review. All attempted calls and returned token usage are counted;
provider-rejected calls may omit usage. More requests consume more of the provider's quota. There is
no paid upgrade, silent alternate model, automatic startup request or fallback to preset results.

The internal `verify_semantics=False` option isolates legacy structural fixtures; it is not exposed as
an offline product mode. The UI uses independent review by default. Imported saved workflows are
explicit local execution and do not automatically receive a new model review.

Local validation: 148 tests passed, with the localhost HTTP-adapter test excluded. These include
independent-review orchestration using synthetic in-memory replies (no network), a ten-invoice/one-vendor
regression, explicit unique-vendor behavior, wrong-field rejection, bounded correction, review failure
handling and identifier preservation. Existing local engine tests also passed. This is not a live-model
quality result and no browser acceptance is claimed.

Restart the server using `run_app.py` to reload the native light theme, then generate a fresh plan.
Prior saved/model-tested workflows remain on disk; other chat changes were not discarded.
