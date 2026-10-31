"""No external calls: independent-review orchestration and filter regression."""
import copy
import json

import pytest

from prompt_compiler.compiler import compile_workflow
from prompt_compiler.executor import execute
from prompt_compiler.files import inventory, read_file
from prompt_compiler.provider import Reply
from prompt_compiler.schema import Workflow
from prompt_compiler.task_coverage import validate_requested_actions


INSTRUCTION = 'Filter vendors from Karnataka and payment type as upi'
FILES = {'data.csv': ('invoice_id,vendor,vendor_state,buyer_state,payment_method\n' +
    ''.join(f'INV-{n},Same Supplier,Karnataka,Goa,UPI\n' for n in range(10)) +
    'OTHER-1,Other Supplier,Goa,Karnataka,UPI\nOTHER-2,Same Supplier,Karnataka,Goa,NEFT\n').encode()}


def workflow(column='vendor_state'):
    return {'version': '1.0', 'title': 'Filter matching invoices', 'steps': [
        {'id': 'read', 'label': 'Read', 'operation': 'read', 'files': ['data.csv']},
        {'id': 'filter', 'label': 'Requested conditions', 'operation': 'filter_rows', 'source': 'read',
         'conditions': [{'column': column, 'comparison': 'eq', 'value': 'karnataka'},
                        {'column': 'payment_method', 'comparison': 'eq', 'value': 'upi'}], 'match': 'all'},
        {'id': 'report', 'label': 'Report', 'operation': 'export', 'source': 'filter', 'filename': 'report.csv'}]}


def generation(plan):
    return json.dumps({'workflow': plan, 'clarification': None, 'requirements': []})


class ReviewProvider:
    structured = True
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []
    def complete(self, messages, schema=None):
        self.calls.append((copy.deepcopy(messages), copy.deepcopy(schema)))
        response = next(self.replies)
        if isinstance(response, Exception):
            raise response
        return Reply(response, 10, 5)


APPROVED = json.dumps({'approved': True, 'issues': [], 'summary': 'Both requested source predicates are applied with AND and rows are preserved.'})
REJECTED = json.dumps({'approved': False, 'issues': ['The filter uses buyer_state instead of vendor_state; the request concerns the vendor location.'], 'summary': 'Wrong location field.'})


def test_ten_matching_invoices_from_one_vendor_remain_ten_rows():
    plan = Workflow.model_validate(workflow())
    validate_requested_actions(plan, INSTRUCTION)
    run = execute(plan, FILES)
    assert run.error is None
    assert len(run.tables['report']) == 10
    assert run.tables['report']['vendor'].nunique() == 1
    trace = next(item for item in run.trace if item['node'] == 'filter')
    assert trace['input_rows'] == 12 and trace['rows'] == 10


@pytest.mark.parametrize('operation', ['deduplicate', 'aggregate', 'select'])
def test_plain_filter_cannot_silently_collapse_or_narrow_matching_records(operation):
    plan = workflow()
    added = {'id': 'extra', 'label': 'Unrequested reduction', 'operation': operation, 'source': 'filter'}
    if operation == 'deduplicate':
        added.update(columns=['vendor'], keep='first')
    elif operation == 'aggregate':
        added.update(group_by=['vendor'], column='invoice_id', function='count', output_column='count')
    else:
        added.update(columns=['vendor'])
    plan['steps'].insert(2, added)
    plan['steps'][-1]['source'] = 'extra'
    with pytest.raises(ValueError, match='preserve|Preserve'):
        validate_requested_actions(Workflow.model_validate(plan), INSTRUCTION)


def test_explicit_unique_vendor_request_allows_deduplication():
    plan = workflow()
    plan['steps'].insert(2, {'id': 'unique', 'label': 'Unique vendors', 'operation': 'deduplicate',
                             'source': 'filter', 'columns': ['vendor'], 'keep': 'first'})
    plan['steps'][-1]['source'] = 'unique'
    parsed = Workflow.model_validate(plan)
    validate_requested_actions(parsed, INSTRUCTION + ', return unique vendors')
    assert len(execute(parsed, FILES).tables['report']) == 1


def test_independent_reviewer_sees_original_request_and_actual_plan():
    provider = ReviewProvider([generation(workflow()), APPROVED])
    result = compile_workflow(INSTRUCTION, inventory(FILES), provider, 'one_shot')
    assert result.workflow is not None and result.api_calls == 2
    assert result.semantic_review['approved']
    assert 'coverage_warning' in result.attempts[0]  # Metadata isn't the acceptance judge.
    context = json.loads(provider.calls[-1][0][1]['content'])
    assert context['original_request'] == INSTRUCTION
    assert context['proposed_workflow']['steps'][1]['conditions'][0]['column'] == 'vendor_state'
    assert 'requirements' not in context
    assert result.prompt_tokens == 20 and result.completion_tokens == 10


def test_wrong_semantics_can_be_rejected_despite_a_valid_graph():
    provider = ReviewProvider([generation(workflow('buyer_state')), REJECTED])
    result = compile_workflow(INSTRUCTION, inventory(FILES), provider, 'one_shot')
    assert result.workflow is None and 'buyer_state' in result.error
    assert result.attempts[0]['schema_valid'] and result.attempts[0]['semantic_valid']
    assert not result.semantic_review['approved']


def test_meaning_feedback_repairs_the_actual_field_within_budget():
    provider = ReviewProvider(['Plan the two conditions', generation(workflow('buyer_state')), REJECTED,
                               generation(workflow()), APPROVED])
    result = compile_workflow(INSTRUCTION, inventory(FILES), provider, 'feedback', 1)
    assert result.workflow is not None and result.api_calls == 5
    assert len(result.attempts) == 2
    feedback = provider.calls[3][0][-1]['content']
    assert 'buyer_state' in feedback
    assert len(execute(result.workflow, FILES).tables['report']) == 10


def test_provider_failure_during_review_does_not_accept_or_retry_unreviewed_plan():
    provider = ReviewProvider(['Plan', generation(workflow()), ValueError('Rate limit reached')])
    result = compile_workflow(INSTRUCTION, inventory(FILES), provider, 'feedback', 2)
    assert result.workflow is None and result.error == 'Rate limit reached'
    assert result.api_calls == 3


def test_invalid_review_does_not_count_as_approval():
    provider = ReviewProvider([generation(workflow()), '{"approved":true,"issues":["wrong"],"summary":"Conflict"}'])
    result = compile_workflow(INSTRUCTION, inventory(FILES), provider, 'one_shot')
    assert result.workflow is None


def test_identifier_text_is_not_destroyed_before_matching():
    frame = read_file('codes.csv', b'code,amount\n001,10\n002,20\n')
    assert frame['code'].tolist() == ['001', '002']
    assert frame['amount'].tolist() == [10, 20]
