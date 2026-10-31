"""Local regression cases for new table operations; no provider calls."""
from io import BytesIO
import pandas as pd
import pytest
from prompt_compiler.schema import Workflow, TaskRequirement
from prompt_compiler.binding import bind_workflow
from prompt_compiler.executor import execute
from prompt_compiler.files import inventory
from prompt_compiler.validation import validate_workflow
from prompt_compiler.task_coverage import validate_task_coverage
from prompt_compiler.workspace_tools import update_parameters
from prompt_compiler.presentation import describe_step


def plan(operation, **options):
    return Workflow.model_validate({'version': '1.0', 'title': 'Table tools', 'steps': [
        {'id': 'input', 'label': 'Input', 'operation': 'read', 'files': ['data.csv']},
        {'id': 'transform', 'label': 'Transform', 'source': 'input', 'operation': operation, **options},
        {'id': 'report', 'label': 'Report', 'source': 'transform', 'operation': 'export', 'filename': 'report.xlsx'}]})


@pytest.mark.parametrize('keep,expected', [('first', [1, 3, 4]), ('last', [2, 3, 5]), ('none', [3])])
def test_dedup_keys_nulls_and_original_text(keep, expected):
    files = {'data.csv': b'ID,Name\n1, ALPHA \n2,alpha\n3,Beta\n4,\n5,\n'}
    workflow = plan('deduplicate', columns=['Name'], keep=keep)
    run = execute(workflow, files)
    assert run.error is None
    assert run.tables['report']['ID'].tolist() == expected
    if keep == 'first':
        assert run.tables['report']['Name'].iloc[0] == ' ALPHA '
    restored = pd.read_excel(BytesIO(run.artifacts['report.xlsx']))
    assert restored['ID'].tolist() == expected
    assert 'Deduplicate' in describe_step(workflow.steps[1])


def test_dedup_case_sensitive_and_all_columns():
    files = {'data.csv': b'Name,Value\nA,1\na,1\nA,1\nA,2\n'}
    run = execute(plan('deduplicate', columns=[], keep='first', case_sensitive=True), files)
    assert run.error is None
    assert run.tables['report'].values.tolist() == [['A', 1], ['a', 1], ['A', 2]]


@pytest.mark.parametrize('columns', [['Unknown'], ['Name', 'Name']])
def test_invalid_dedup_keys(columns):
    with pytest.raises(ValueError):
        validate_workflow(plan('deduplicate', columns=columns, keep='first'), inventory({'data.csv': b'Name\nA\n'}))


def date_plan(**changes):
    return plan('date_difference', **dict({'start_column': 'Start', 'end_column': 'End',
        'start_format': '%Y-%m-%d', 'end_format': '%Y-%m-%d', 'output_column': 'Days'}, **changes))


def test_date_difference_leap_negative_missing_and_export():
    files = {'data.csv': b'Start,End\n2024-02-28,2024-03-01\n2024-03-01,2024-02-28\n,2024-03-01\n'}
    workflow = date_plan()
    run = execute(workflow, files)
    assert run.error is None
    values = run.tables['report']['Days']
    assert values.iloc[:2].tolist() == [2, -2]
    assert pd.isna(values.iloc[2])
    assert pd.read_excel(BytesIO(run.artifacts['report.xlsx']))['Days'].iloc[:2].tolist() == [2, -2]
    req = TaskRequirement(request_excerpt='Calculate days', action='date_difference', step_ids=['transform'], output_columns=['Days'])
    validate_task_coverage(workflow, [req], 'Calculate days', inventory(files))


@pytest.mark.parametrize('bad', ['2024-02-30', '03/04/2024', 'banana'])
def test_invalid_dates_fail_without_artifacts(bad):
    files = {'data.csv': f'Start,End\n{bad},2024-04-05\n'.encode()}
    run = execute(date_plan(), files)
    assert 'invalid dates' in run.error
    assert not run.artifacts


def test_explicit_date_formats_and_local_edits():
    files = {'data.csv': b'Start,End\n03/04/2024,04/05/2024\n'}
    workflow = update_parameters(date_plan(), {'transform': {'start_format': '%d/%m/%Y', 'end_format': '%m/%d/%Y'}}, inventory(files))
    run = execute(workflow, files)
    assert run.error is None
    assert run.tables['report']['Days'].tolist() == [2]


def test_new_fields_bind_and_output_collision_rejected():
    files = {'data.csv': b'Start,End\n2024-01-01,2024-01-02\n'}
    bound = bind_workflow(date_plan(start_column='START', end_column='end'), inventory(files), 'Calculate days')
    assert bound.steps[1].start_column == 'Start'
    with pytest.raises(ValueError, match='new, non-empty'):
        validate_workflow(date_plan(output_column='Start'), inventory(files))


def test_dedup_coverage_and_local_keep_edit():
    files = {'data.csv': b'Name\nA\nA\n'}
    workflow = plan('deduplicate', columns=['Name'], keep='first')
    req = TaskRequirement(request_excerpt='Remove duplicates', action='deduplicate', step_ids=['transform'], output_columns=['Name'])
    validate_task_coverage(workflow, [req], 'Remove duplicates', inventory(files))
    changed = update_parameters(workflow, {'transform': {'keep': 'none'}}, inventory(files))
    run = execute(changed, files)
    assert run.error is None
    assert run.tables['report'].empty


def test_calculation_overflow_does_not_export_infinity():
    files = {'data.csv': b'Value\n1e308\n'}
    run = execute(plan('calculate', left='Value', right=1e308, arithmetic='multiply', output_column='Result'), files)
    assert 'infinite' in run.error
    assert not run.artifacts


def test_derived_column_limit():
    files = {'data.csv': (','.join(f'C{i}' for i in range(200)) + '\n' + ','.join('1' for _ in range(200))).encode()}
    with pytest.raises(ValueError, match='200 columns'):
        validate_workflow(plan('calculate', left='C0', right=1, arithmetic='add', output_column='Extra'), inventory(files))
