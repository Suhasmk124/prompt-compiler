"""Schema/coverage/execution checks only; no model, HTTP, or browser calls."""
import json

import pandas as pd
import pytest

from prompt_compiler.binding import bind_workflow
from prompt_compiler.capabilities import SYSTEM, CAPABILITIES
from prompt_compiler.executor import execute
from prompt_compiler.files import inventory
from prompt_compiler.schema import Workflow, TaskRequirement, CompilerResponse
from prompt_compiler.provider import strict_schema
from prompt_compiler.task_coverage import validate_task_coverage, validate_requested_actions
from prompt_compiler.validation import validate_workflow


FILES = {'staff.csv': b'Person,Team,Hours,Hourly Rate,Comments,Contact\nA,Engineering,10,250,Sensor [X] repair,a@example.invalid\nB,ENGINEERING,5,200,Calibration,\nC,Sales,20,150,Sensor Y repair,c@example.invalid\n'}
REQUEST = 'Keep only Engineering staff, calculate cost from hours and hourly rate, group by team and sum cost, sort spend descending, and export the result.'


def payload():
    return {'version': '1.0', 'title': 'Staff costs', 'steps': [
        {'id': 'read', 'label': 'Read', 'operation': 'read', 'files': ['STAFF.CSV']},
        {'id': 'filter', 'label': 'Engineering', 'operation': 'filter', 'source': 'read',
         'column': 'team', 'comparison': 'eq', 'value': 'engineering', 'case_sensitive': True},
        {'id': 'cost', 'label': 'Cost', 'operation': 'calculate', 'source': 'filter',
         'left': 'HOURS', 'right': 'hourly_rate', 'arithmetic': 'multiply', 'output_column': 'cost'},
        {'id': 'summary', 'label': 'Team spend', 'operation': 'aggregate', 'source': 'cost',
         'group_by': ['TEAM'], 'column': 'cost', 'function': 'sum', 'output_column': 'spend'},
        {'id': 'sort', 'label': 'Sort', 'operation': 'sort', 'source': 'summary', 'column': 'SPEND', 'descending': True},
        {'id': 'report', 'label': 'Report', 'operation': 'export', 'source': 'sort', 'filename': 'staff_costs.csv'}]}


def requirements():
    return [TaskRequirement(request_excerpt=REQUEST, action=action, step_ids=[node_id], output_columns=[])
            for action, node_id in [('filter', 'filter'), ('calculate', 'cost'), ('aggregate', 'summary'), ('sort', 'sort')]]


def test_arbitrary_schema_binds_and_executes_a_multi_action_workflow():
    manifest = inventory(FILES)
    plan = bind_workflow(Workflow.model_validate(payload()), manifest, REQUEST)
    validate_workflow(plan, manifest)
    validate_task_coverage(plan, requirements(), REQUEST, manifest)
    run = execute(plan, FILES)
    assert run.error is None
    assert run.tables['cost']['cost'].tolist() == [2500, 1000]
    # Matching ignores case; grouping preserves the distinct original Team cells.
    assert run.tables['report']['spend'].tolist() == [2500, 1000]
    assert plan.steps[1].case_sensitive is False
    assert plan.steps[2].right == 'Hourly Rate'
    assert list(run.tables['report']) == ['Team', 'spend']


def test_metadata_sends_types_without_sample_cells():
    meta = inventory(FILES)['staff.csv']
    assert meta['column_types']['Hours'] == 'number'
    assert meta['column_types']['Team'] == 'text'
    serialized = json.dumps(meta)
    assert 'Engineering' not in serialized and 'example.invalid' not in serialized


def test_case_sensitive_matching_requires_explicit_user_intent():
    manifest = inventory(FILES)
    plan = bind_workflow(Workflow.model_validate(payload()), manifest, REQUEST + ' Match case-sensitive.')
    assert plan.steps[1].case_sensitive is True
    plan = bind_workflow(Workflow.model_validate(payload()), manifest, REQUEST + ' Never case sensitive.')
    assert plan.steps[1].case_sensitive is False


def test_ambiguous_normalized_source_name_is_not_guessed():
    manifest = inventory({'staff.csv': b'Team Name,team_name,Hours,Hourly Rate\nA,B,1,2\n'})
    data = payload()
    data['steps'][1]['column'] = 'TEAM NAME'
    with pytest.raises(ValueError, match='Ambiguous'):
        bind_workflow(Workflow.model_validate(data), manifest, REQUEST)


@pytest.mark.parametrize('mutation', ['empty', 'invented_excerpt', 'unknown_node', 'wrong_action', 'uncovered_step', 'lost_column'])
def test_bad_coverage_is_rejected(mutation):
    manifest = inventory(FILES)
    plan = bind_workflow(Workflow.model_validate(payload()), manifest, REQUEST)
    reqs = requirements()
    if mutation == 'empty':
        reqs = []
    elif mutation == 'invented_excerpt':
        reqs[0] = reqs[0].model_copy(update={'request_excerpt': 'An invented task'})
    elif mutation == 'unknown_node':
        reqs[0] = reqs[0].model_copy(update={'step_ids': ['not_a_step']})
    elif mutation == 'wrong_action':
        reqs[0] = reqs[0].model_copy(update={'action': 'flag'})
    elif mutation == 'uncovered_step':
        reqs.pop(1)
    else:
        reqs[1] = reqs[1].model_copy(update={'output_columns': ['cost']})
    with pytest.raises(ValueError):
        validate_task_coverage(plan, reqs, REQUEST, manifest)


@pytest.mark.parametrize('instruction_text', ['Flag matching rows', 'Filter the rows', 'Calculate a new value',
                                      'Group by team', 'Sort by hours', 'Select only the columns Person and Team'])
def test_copy_plan_cannot_claim_supported_actions(instruction_text):
    plan = Workflow.model_validate({'version': '1.0', 'title': 'Copy', 'steps': [
        {'id': 'read', 'label': 'Read', 'operation': 'read', 'files': ['staff.csv']},
        {'id': 'report', 'label': 'Export', 'operation': 'export', 'source': 'read', 'filename': 'copy.csv'}]})
    with pytest.raises(ValueError, match='omits that action'):
        validate_requested_actions(plan, instruction_text)


@pytest.mark.parametrize('comparison,value,expected', [
    ('contains', '[x]', [True, False, False]),
    ('not_contains', '[x]', [False, True, True]),
    ('starts_with', 'sensor', [True, False, True]),
    ('ends_with', 'REPAIR', [True, False, True]),
    ('is_null', None, [False, False, False]),
])
def test_generic_text_predicates_are_literal_and_case_insensitive(comparison, value, expected):
    data = payload()
    data['steps'] = [data['steps'][0], {'id': 'flag', 'label': 'Match comments', 'operation': 'flag',
                    'source': 'read', 'column': 'comments', 'comparison': comparison, 'value': value,
                    'case_sensitive': True, 'output_column': 'matched'},
                    {'id': 'report', 'label': 'Report', 'operation': 'export', 'source': 'flag', 'filename': 'comments.csv'}]
    plan = bind_workflow(Workflow.model_validate(data), inventory(FILES), 'Flag the requested comments')
    run = execute(plan, FILES)
    assert run.error is None
    assert run.tables['report']['matched'].tolist() == expected


def test_missing_contact_can_be_flagged_without_unknown_results():
    data = payload()
    data['steps'] = [data['steps'][0], {'id': 'flag', 'label': 'Missing contacts', 'operation': 'flag',
                    'source': 'read', 'column': 'contact', 'comparison': 'is_null', 'value': None,
                    'output_column': 'missing_contact'},
                    {'id': 'report', 'label': 'Report', 'operation': 'export', 'source': 'flag', 'filename': 'contacts.csv'}]
    run = execute(bind_workflow(Workflow.model_validate(data), inventory(FILES), 'Flag missing contacts'), FILES)
    assert run.error is None
    assert run.tables['report']['missing_contact'].tolist() == [False, True, False]


def test_capability_catalog_and_response_schema_are_consistent():
    schema = strict_schema(CompilerResponse.model_json_schema())
    operations = {definition['properties']['operation']['enum'][0]
                  for definition in schema['$defs'].values() if 'operation' in definition.get('properties', {})}
    assert operations == set(CAPABILITIES)
    assert set(schema['required']) == {'workflow', 'clarification', 'requirements'}
    assert all(field not in SYSTEM for field in ['payment_method', 'delivery_city', 'Hyderabad', 'UPI'])
