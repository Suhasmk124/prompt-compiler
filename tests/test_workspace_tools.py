from io import BytesIO
import asyncio
import json
import sys
import zipfile
import pandas as pd
import pytest

from prompt_compiler.demo import DEMOS, sample_files, demo_workflow
from prompt_compiler.files import inventory
from prompt_compiler.executor import execute
from prompt_compiler.workspace_tools import build_bundle, import_workflow, search_table
from prompt_compiler.workspace_tools import compare_tables, remap_inputs, retain_snapshot, update_parameters


def test_import_validates_inputs_and_executes_without_provider():
    files = sample_files()
    manifest = inventory(files)
    original = demo_workflow(DEMOS['Invoice review'], manifest)
    imported = import_workflow(original.model_dump_json().encode(), manifest)
    run = execute(imported, files)
    assert run.error is None
    assert run.tables['report']['needs_review'].tolist() == [False, True, False, True]
    with pytest.raises(ValueError, match='not uploaded'):
        import_workflow(original.model_dump_json().encode(), {})


def test_import_rejects_oversized_and_invalid_json():
    with pytest.raises(ValueError, match='200 KB'):
        import_workflow(b' ' * 200_001, {})
    with pytest.raises(ValueError):
        import_workflow(b'{invalid}', {})


def test_search_is_literal_case_insensitive_and_leaves_original_unchanged():
    frame = pd.DataFrame({'vendor': ['Acme [UK]', 'Delta', None], 'total': [10, 20, 30]})
    assert search_table(frame, 'ACME')['total'].tolist() == [10]
    assert search_table(frame, '[')['total'].tolist() == [10]
    assert search_table(frame, '30')['total'].tolist() == [30]
    assert search_table(frame, 'missing').empty
    assert search_table(frame, '').equals(frame)
    assert len(frame) == 3


def test_bundle_contains_reports_exact_executed_workflow_and_audit():
    files = sample_files()
    workflow = demo_workflow(DEMOS['Invoice review'], inventory(files))
    run = execute(workflow, files)
    payload = build_bundle(run.artifacts, workflow, {'manual_workflow_edit_present': 0})
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {'workflow.json', 'audit.json', 'reports/invoice_report.xlsx'}
        assert json.loads(archive.read('workflow.json')) == workflow.model_dump()
        assert archive.read('reports/invoice_report.xlsx') == run.artifacts['invoice_report.xlsx']
    with pytest.raises(ValueError, match='basenames'):
        build_bundle({'../bad.xlsx': b''}, workflow, {})


def test_windows_launcher_selects_socket_loop_without_starting_app():
    from run_app import configure_event_loop
    before = asyncio.get_event_loop_policy()
    try:
        configure_event_loop()
        if sys.platform == 'win32':
            assert isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsSelectorEventLoopPolicy)
        else:
            assert asyncio.get_event_loop_policy() is before
    finally:
        asyncio.set_event_loop_policy(before)


def sample_plan():
    files = sample_files()
    return demo_workflow(DEMOS['Invoice review'], inventory(files))


def test_rebind_saved_plan_to_new_filenames_without_mutating_original():
    original = sample_plan()
    files = {'new-invoice.txt': b'Vendor: New\nCurrency: INR\nTotal: 60000\n'}
    revised = remap_inputs(original, {'read': ['new-invoice.txt']}, inventory(files))
    run = execute(revised, files)
    assert run.error is None
    assert run.tables['report']['vendor'].tolist() == ['New']
    assert run.tables['report']['needs_review'].tolist() == [True]
    assert original.steps[0].files == list(sample_files())


@pytest.mark.parametrize('bindings', [{'extract': ['invoice_001.txt']}, {'read': []}, {'read': ['missing.txt']}, {'read': ['invoice_001.txt', 'invoice_001.txt']}])
def test_invalid_bindings_are_rejected(bindings):
    with pytest.raises(ValueError):
        remap_inputs(sample_plan(), bindings, inventory(sample_files()))


def test_rebinding_incompatible_schemas_is_rejected():
    manifest = inventory({'a.csv': b'a\n1\n', 'b.csv': b'b\n2\n'})
    with pytest.raises(ValueError, match='columns match'):
        remap_inputs(sample_plan(), {'read': ['a.csv', 'b.csv']}, manifest)


def test_change_threshold_comparison_and_export_name_locally():
    original = sample_plan()
    manifest = inventory(sample_files())
    revised = update_parameters(original, {'transform': {'comparison': 'gte', 'value': 50000},
                                            'report': {'filename': 'revised.csv'}}, manifest)
    run = execute(revised, sample_files())
    assert run.error is None
    assert run.tables['report']['needs_review'].tolist() == [True, True, False, True]
    assert set(run.artifacts) == {'revised.csv'}
    assert original.steps[2].comparison == 'gt'
    assert original.steps[-1].filename == 'invoice_report.xlsx'


@pytest.mark.parametrize('updates', [
    {'missing': {'value': 1}}, {'read': {'files': []}}, {'report': {'filename': '../escape.xlsx'}},
    {'transform': {'comparison': 'invalid'}}, {'transform': {'value': float('nan')}},
    {'transform': {'value': float('inf')}}, {'transform': {'column': 'vendor'}},
])
def test_parameter_edits_reject_invalid_or_unapproved_changes(updates):
    with pytest.raises(ValueError):
        update_parameters(sample_plan(), updates, inventory(sample_files()))


def test_compare_ignores_order_and_numeric_dtype_but_counts_duplicate_rows():
    before = pd.DataFrame({'value': [1, 1, 2], 'label': ['a', 'a', 'b']})
    after = pd.DataFrame({'label': ['b', 'a', 'c'], 'value': [2.0, 1.0, 3.0]})
    diff = compare_tables(before, after)
    assert diff['comparable']
    assert (diff['unchanged_rows'], diff['added_rows'], diff['removed_rows']) == (2, 1, 1)
    assert diff['removed_preview'].to_dict('records') == [{'value': 1, 'label': 'a'}]
    assert diff['added_preview'].to_dict('records') == [{'value': 3.0, 'label': 'c'}]


def test_compare_threshold_runs_identifies_changed_row_versions():
    original = sample_plan()
    revised = update_parameters(original, {'transform': {'value': 60000}}, inventory(sample_files()))
    before = execute(original, sample_files()).tables['report']
    after = execute(revised, sample_files()).tables['report']
    diff = compare_tables(before, after)
    assert (diff['unchanged_rows'], diff['added_rows'], diff['removed_rows']) == (3, 1, 1)
    assert diff['added_preview']['total'].tolist() == [50001]


def test_compare_handles_nulls_empty_reports_and_schema_changes():
    before = pd.DataFrame({'value': [None, 2.0]})
    after = pd.DataFrame({'value': [pd.NA, 2]})
    assert compare_tables(before, after)['unchanged_rows'] == 2
    assert compare_tables(before, before.iloc[:0])['removed_rows'] == 2
    mismatch = compare_tables(before, pd.DataFrame({'other': [1]}))
    assert not mismatch['comparable']
    assert mismatch['added_columns'] == ['other'] and mismatch['removed_columns'] == ['value']


def test_compare_keeps_boolean_distinct_from_numeric_one_and_caps_preview():
    assert compare_tables(pd.DataFrame({'x': [True]}), pd.DataFrame({'x': [1]}))['added_rows'] == 1
    diff = compare_tables(pd.DataFrame({'x': []}), pd.DataFrame({'x': range(150)}))
    assert diff['added_rows'] == 150 and len(diff['added_preview']) == 100


def test_compare_does_not_round_large_integers_into_equal_values():
    before = pd.DataFrame({'x': [10**30 + 1]}, dtype=object)
    after = pd.DataFrame({'x': [10**30 + 2]}, dtype=object)
    diff = compare_tables(before, after)
    assert diff['unchanged_rows'] == 0 and diff['added_rows'] == 1 and diff['removed_rows'] == 1


def test_snapshots_are_independent_bounded_and_skip_failed_or_large_results():
    workflow = sample_plan()
    run = execute(workflow, sample_files())
    snapshots = []
    for index in range(7):
        snapshots, latest = retain_snapshot(snapshots, workflow, run, str(index), 'same-inputs')
    assert len(snapshots) == 5
    assert [s.timestamp for s in snapshots] == ['6', '5', '4', '3', '2']
    before = latest.frame.copy()
    run.tables['report'].loc[0, 'vendor'] = 'Edited after capture'
    assert latest.frame.equals(before)
    preserved, skipped = retain_snapshot(snapshots, workflow, run, 'large', 'same', budget_bytes=1)
    assert preserved is snapshots and skipped is None
    run.error = 'failure'
    preserved, skipped = retain_snapshot(snapshots, workflow, run, 'failed', 'same')
    assert preserved is snapshots and skipped is None
