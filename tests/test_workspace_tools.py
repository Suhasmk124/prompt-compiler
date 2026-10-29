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
