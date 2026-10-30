from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
from html import escape
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import streamlit as st

from prompt_compiler.compiler import Compilation, compile_workflow
from prompt_compiler.demo import DEMOS
from prompt_compiler.journey import resolve_stage
from prompt_compiler.executor import execute, export_table
from prompt_compiler.files import inventory, read_file
from prompt_compiler.presentation import COMPARISONS, plan_markup, progress_markup
from prompt_compiler.provider import Provider
from prompt_compiler.schema import Workflow
from prompt_compiler.validation import validate_workflow
from prompt_compiler.workspace_tools import (build_bundle, compare_tables, parse_workflow, remap_inputs,
                                            retain_snapshot, search_table, update_parameters)

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Prompt Compiler · Workspace', page_icon='✦', layout='wide')
st.markdown('<style>' + (ROOT / 'assets/style.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


def markup(value):
    st.markdown(value, unsafe_allow_html=True)


def empty_state(title, text='', symbol='✦'):
    markup(f'<div class="empty-state"><div class="empty-icon">{escape(symbol)}</div><strong>{escape(title)}</strong><p>{escape(text)}</p></div>')


def section(kicker, title):
    markup(f'<div class="section-kicker">{escape(kicker)}</div>')
    st.subheader(title)


PLAN_STATE = ['compilation', 'run', 'workflow_editor', 'workflow_draft', 'validated_editor', 'manual_edits', 'executed_workflow', 'report_search', 'active_run_id', 'snapshot_notice']


def clear_plan():
    for name in PLAN_STATE:
        st.session_state.pop(name, None)
    st.session_state['flow_stage'] = 'describe'


def go_to_stage(stage):
    st.session_state['flow_stage'] = stage


def new_workspace():
    clear_plan()
    st.session_state['navigation'] = 'Workspace'
    st.session_state['instruction_draft'] = ''
    st.session_state['task_instruction'] = ''
    st.session_state['preset_picker'] = 'Write your own task'
    st.session_state['saved_preset'] = 'Write your own task'
    st.session_state['active_files'] = {}
    st.session_state['example_pack'] = False
    st.session_state['duplicate_uploads'] = False
    st.session_state['upload_epoch'] = st.session_state.get('upload_epoch', 0) + 1


def use_example_pdf():
    path = ROOT / 'examples/pdf/cedar_coast_invoice.pdf'
    st.session_state['active_files'] = {path.name: path.read_bytes()}
    st.session_state['example_pack'] = True
    st.session_state['duplicate_uploads'] = False
    st.session_state['upload_epoch'] = st.session_state.get('upload_epoch', 0) + 1


def clear_files():
    st.session_state['active_files'] = {}
    st.session_state['example_pack'] = False
    st.session_state['duplicate_uploads'] = False
    st.session_state['upload_epoch'] = st.session_state.get('upload_epoch', 0) + 1


def save_uploads(widget_key):
    uploads = st.session_state.get(widget_key) or []
    st.session_state['active_files'] = {f.name: f.getvalue() for f in uploads}
    st.session_state['duplicate_uploads'] = len(st.session_state['active_files']) != len(uploads)
    st.session_state['example_pack'] = False


def save_instruction():
    st.session_state['instruction_draft'] = st.session_state['task_instruction']


def save_workflow():
    st.session_state['workflow_draft'] = st.session_state['workflow_editor']


def pick_preset():
    choice = st.session_state['preset_picker']
    st.session_state['saved_preset'] = choice
    if choice in DEMOS:
        st.session_state['instruction_draft'] = DEMOS[choice]
        st.session_state['task_instruction'] = DEMOS[choice]


def sidebar():
    # Credentials are read server-side only. Never create a browser widget with a key.
    for old_key in list(st.session_state):
        if old_key.startswith(('key_', 'base_', 'model_', 'strict_', 'consent_')):
            st.session_state.pop(old_key, None)
    with st.sidebar:
        markup('<div class="brand"><div class="brand-icon">✦</div><div><strong>Prompt Compiler</strong><small>YOUR AUTOMATION STUDIO</small></div></div>')
        st.button('＋ New workflow', on_click=new_workspace, width='stretch')
        markup('<div class="nav-label">EXPLORE</div>')
        st.session_state.setdefault('navigation', 'Workspace')
        page = st.radio('Navigation', ['Workspace', 'Run history', 'Research'], index=None, key='navigation', label_visibility='collapsed')
        st.divider()
        base = os.getenv('LLM_BASE_URL', '').strip()
        model = os.getenv('LLM_MODEL', '').strip()
        key = os.getenv('LLM_API_KEY', '').strip()
        settings = {'mode': 'Connected model', 'strategy': 'feedback', 'retries': 2,
                    'base_url': base, 'model': model, 'key': key, 'structured': os.getenv('LLM_STRUCTURED', 'true').lower() != 'false'}
        configured = bool(base and model and (key or base.startswith(('http://localhost:', 'http://127.0.0.1:'))))
        settings['configured'] = configured
        if configured:
            st.caption('Task engine configured locally.')
        else:
            st.warning('Set up the task engine in the local .env file, then restart.')
        with st.expander('Planning preferences'):
            approach = st.selectbox('Approach', ['Standard', 'Plan first', 'Plan + self-correction'], index=2)
            settings['strategy'] = {'Standard': 'one_shot', 'Plan first': 'decompose', 'Plan + self-correction': 'feedback'}[approach]
            settings['retries'] = st.slider('Correction budget', 0, 3, 2, disabled=settings['strategy'] != 'feedback')
        markup('<div class="sidebar-note"><span class="privacy-dot"></span> Files processed locally<br><span class="sidebar-small">Built for the work between idea and done.</span></div>')
    return page, settings


def header(page, settings):
    status = 'Engine ready' if settings['configured'] else 'Setup needed'
    markup(f'<div class="topline"><span>Studio <span style="color:#b7bfcb;margin:0 9px">/</span><b>{escape(page)}</b></span><span class="connection-tag {"live" if settings["configured"] else ""}">{status}</span></div>')


def audit_payload(compilation, run):
    data = asdict(compilation)
    data['workflow'] = compilation.workflow.model_dump() if compilation.workflow else None
    return {'compilation': data, 'executed_workflow': st.session_state.get('executed_workflow'),
            'trace': run.trace, 'checks': run.checks, 'error': run.error,
            'manual_workflow_edit_present': st.session_state.get('manual_edits', 0)}


def comparison_panel(run):
    if run.error:
        return
    previous = [s for s in st.session_state.get('snapshots', []) if s.id != st.session_state.get('active_run_id')]
    if not previous:
        if st.session_state.get('snapshot_notice'):
            st.caption('Report is too large for session comparison; your downloads are still available.')
        return
    with st.expander('Compare with an earlier run'):
        by_id = {snapshot.id: snapshot for snapshot in previous}
        selected = st.selectbox('Earlier result', list(by_id), format_func=lambda sid: f'{by_id[sid].title} · {by_id[sid].timestamp} · {sid[:4]}')
        old = by_id[selected]
        frame = next(reversed(run.tables.values()))
        diff = compare_tables(old.frame, frame)
        if old.input_fingerprint != st.session_state.get('current_input_fingerprint'):
            st.caption('These runs used different inputs; differences may come from the data as well as the plan.')
        if not diff['comparable']:
            st.info('The report columns differ. Row comparison is unavailable.')
            st.write({'Added columns': diff['added_columns'], 'Removed columns': diff['removed_columns']})
        else:
            columns = st.columns(3)
            columns[0].metric('Unchanged', diff['unchanged_rows'])
            columns[1].metric('Added', diff['added_rows'])
            columns[2].metric('Removed', diff['removed_rows'])
            st.caption('A changed row counts as one removal and one addition. Row order is ignored; duplicates count separately.')
            added_tab, removed_tab = st.tabs(['Added rows', 'Removed rows'])
            with added_tab:
                st.dataframe(diff['added_preview'], hide_index=True, width='stretch')
            with removed_tab:
                st.dataframe(diff['removed_preview'], hide_index=True, width='stretch')
            st.caption('Up to 100 rows shown per side. Comparison uses the final report table.')
        summary = {name: value for name, value in diff.items() if not name.endswith('_preview')}
        st.download_button('Save comparison · JSON', json.dumps(summary, indent=2), 'comparison.json', mime='application/json')


def condition_controls(condition, prefix):
    comparison = st.selectbox('Comparison · ' + condition.column, list(COMPARISONS),
        index=list(COMPARISONS).index(condition.comparison), format_func=lambda item: COMPARISONS[item], key=prefix + '_comparison')
    if comparison in {'is_null', 'not_null'}:
        value = None
    elif isinstance(condition.value, bool):
        value = st.checkbox('Match value', value=condition.value, key=prefix + '_value')
    elif isinstance(condition.value, (int, float)):
        value = st.number_input('Threshold · ' + condition.column, value=float(condition.value), step=1.0, key=prefix + '_value')
    else:
        value = st.text_input('Match value · ' + condition.column, value=condition.value or '', key=prefix + '_value')
    case_sensitive = condition.case_sensitive
    if isinstance(condition.value, str):
        case_sensitive = st.checkbox('Case-sensitive · ' + condition.column, value=case_sensitive, key=prefix + '_case')
    return {'comparison': comparison, 'value': value, 'case_sensitive': case_sensitive}


def rule_controls(manifest):
    try:
        workflow = Workflow.model_validate_json(st.session_state.get('workflow_editor') or st.session_state['workflow_draft'])
    except ValueError:
        return
    digest = hashlib.sha256(workflow.model_dump_json().encode()).hexdigest()[:10]
    with st.expander('Adjust rules & output names'):
        with st.form('parameters_' + digest):
            updates = {}
            for step in workflow.steps:
                prefix = digest + '_' + step.id
                if step.operation in {'flag', 'filter'}:
                    st.text(step.label)
                    updates[step.id] = condition_controls(step, prefix)
                elif step.operation in {'flag_rows', 'filter_rows'}:
                    st.text(step.label)
                    match = st.selectbox('Combine conditions', ['all', 'any'], index=0 if step.match == 'all' else 1,
                        format_func=lambda value: 'AND · all conditions' if value == 'all' else 'OR · any condition', key=prefix + '_match')
                    conditions = []
                    for index, condition in enumerate(step.conditions):
                        changes = condition_controls(condition, prefix + '_' + str(index))
                        conditions.append({'column': condition.column, **changes})
                    updates[step.id] = {'match': match, 'conditions': conditions}
                elif step.operation == 'export':
                    filename = st.text_input('Report filename', value=step.filename, key=prefix + '_filename')
                    updates[step.id] = {'filename': filename}
            if st.form_submit_button('Apply changes · no model call', width='stretch'):
                try:
                    revised = update_parameters(workflow, updates, manifest)
                    st.session_state['workflow_editor'] = revised.model_dump_json(indent=2)
                    st.session_state['workflow_draft'] = st.session_state['workflow_editor']
                    for name in ['run', 'validated_editor', 'executed_workflow', 'active_run_id', 'report_search']:
                        st.session_state.pop(name, None)
                    st.success('Plan updated. Run it to create a new report.')
                except ValueError as exc:
                    st.error(str(exc))


def results_panel(compilation, run):
    section('THE GOOD STUFF', 'Your report')
    if not run:
        empty_state('A fresh report is on the way', 'Run your plan to see the result here.', '↧')
        return
    if run.error:
        st.error('The workflow stopped: ' + run.error)
    else:
        markup(f'<div class="report-summary"><div class="report-icon">✓</div><div><strong>Done. Ready when you are.</strong><small>{len(run.artifacts)} report file(s) created</small></div></div>')
    if run.tables:
        frame = next(reversed(run.tables.values()))
        seconds = sum(t['seconds'] for t in run.trace)
        markup(f'<div class="stat-strip"><div><b>{len(frame):,}</b><small>ROWS</small></div><div><b>{len(frame.columns)}</b><small>COLUMNS</small></div><div><b>{seconds:.2f}s</b><small>RUN TIME</small></div></div>')
        query = st.text_input('Search report', placeholder='Find a vendor, amount, or any value…', key='report_search')
        visible = search_table(frame, query)
        executed = Workflow.model_validate(st.session_state.get('executed_workflow') or compilation.workflow.model_dump())
        flag_columns = list(dict.fromkeys(step.output_column for step in executed.steps
            if step.operation in {'flag', 'flag_rows'} and step.output_column in frame.columns))
        for column in flag_columns:
            matched = int(frame[column].eq(True).sum())
            unknown = int(frame[column].isna().sum())
            st.caption(f'{column} · {matched:,} flagged · {len(frame) - matched - unknown:,} not flagged' + (f' · {unknown:,} unknown' if unknown else ''))
        if flag_columns:
            visible = visible[flag_columns + [name for name in visible.columns if name not in flag_columns]]
        st.dataframe(visible, hide_index=True, width='stretch', height=280)
        if query.strip():
            st.caption(f'{len(visible):,} of {len(frame):,} rows shown. Original reports are unchanged.')
            st.download_button('Download matching rows · CSV', export_table(visible, 'matching_rows.csv'), 'matching_rows.csv', mime='text/csv')
        if 'extraction_status' in frame and (frame['extraction_status'] != 'ok').any():
            st.warning('Some fields need review. Missing values have been kept explicit.')
    for name, content in run.artifacts.items():
        mime = 'text/csv' if name.endswith('.csv') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        st.download_button('↓ ' + name, content, file_name=name, mime=mime, type='primary', width='stretch', key='download_' + name)
    if run.artifacts and st.session_state.get('executed_workflow'):
        saved = Workflow.model_validate(st.session_state['executed_workflow'])
        bundle = build_bundle(run.artifacts, saved, audit_payload(compilation, run))
        st.download_button('Download everything · ZIP', bundle, 'workflow_run.zip', mime='application/zip', width='stretch')
    comparison_panel(run)
    with st.expander('Run details'):
        st.dataframe(run.trace, hide_index=True, width='stretch')
        if run.tables:
            selected = st.selectbox('Inspect step output', list(run.tables))
            st.dataframe(run.tables[selected], hide_index=True, width='stretch')
        for check in run.checks:
            st.caption(check)
        st.caption('Export checks verify file structure. Check report contents against your task before relying on them.')
        st.download_button('Download audit', json.dumps(audit_payload(compilation, run), indent=2, ensure_ascii=False), 'run_audit.json', mime='application/json')


def inputs_panel():
    section('DROP IT IN', 'Source files')
    st.session_state.setdefault('active_files', {})
    epoch = st.session_state.get('upload_epoch', 0)
    widget_key = f'upload_widget_{epoch}'
    st.file_uploader('Drop documents or spreadsheets here', type=['txt', 'pdf', 'csv', 'xlsx'],
                     accept_multiple_files=True, key=widget_key, on_change=save_uploads, args=(widget_key,))
    first, second = st.columns([1.5, 1])
    first.button('Try example PDF', on_click=use_example_pdf, width='stretch', disabled=not (ROOT / 'examples/pdf/cedar_coast_invoice.pdf').exists())
    second.button('Clear files', on_click=clear_files, width='stretch', disabled=not st.session_state['active_files'])
    files = st.session_state['active_files']
    manifest, error = {}, None
    try:
        if st.session_state.get('duplicate_uploads'):
            raise ValueError('Uploaded filenames must be unique.')
        if files:
            manifest = inventory(files)
    except Exception as exc:
        error = str(exc)
        st.error(error)
    if manifest:
        label = 'Example PDF' if st.session_state.get('example_pack') else 'Your uploads'
        total_kb = sum(len(content) for content in files.values()) / 1024
        markup(f'<div class="input-summary"><span class="input-dot"></span><b>{label}</b><span>{len(files)} files · {total_kb:.1f} KB</span></div>')
        chips = ''.join(f'<span class="file-chip">{escape(name)}</span>' for name in list(manifest)[:3])
        if len(manifest) > 3:
            chips += f'<span class="file-chip more">+{len(manifest)-3} more</span>'
        markup('<div class="file-chips">' + chips + '</div>')
        with st.expander('Preview files'):
            name = st.selectbox('File', list(manifest), key='preview_file')
            frame = read_file(name, files[name])
            if manifest[name]['kind'] == 'document':
                st.text(str(frame.iloc[0]['text'])[:5000])
                st.caption('First 5,000 characters. Preview stays local.')
            else:
                st.dataframe(frame.head(100), hide_index=True, width='stretch')
                st.caption(f'{len(frame):,} rows · first 100 shown')
        if st.session_state.get('example_pack'):
            name = next(iter(files))
            st.download_button('Download example PDF', files[name], name, mime='application/pdf')
    st.caption('TXT, PDF, CSV, XLSX · 10 MB per file · text-based PDFs')
    return files, manifest, error


def install_plan(result):
    st.session_state['compilation'] = result
    st.session_state['workflow_editor'] = result.workflow.model_dump_json(indent=2)
    st.session_state['workflow_draft'] = st.session_state['workflow_editor']
    st.session_state['flow_stage'] = 'plan'


def describe_stage(settings, manifest, file_error):
    markup('<div class="studio-hero"><div><span class="hero-kicker">LESS BUSYWORK. MORE POSSIBILITY.</span><h1>What are we making today?</h1><p>Start with a task and the files it needs.</p></div><div class="hero-art" aria-hidden="true"><i class="orbit one"></i><i class="orbit two"></i><span class="art-tile violet">✦</span><span class="art-tile mint">↗</span><span class="art-tile peach">✓</span></div></div>')
    request_col, files_col = st.columns([1.8, 1], gap='large')
    with files_col:
        with st.container(border=True, key='panel_files'):
            inputs_panel()
    with request_col:
        with st.container(border=True, key='panel_request'):
            section('01 · YOUR TASK', 'Tell us what needs doing')
            choices = ['Write your own task', *DEMOS]
            st.session_state.setdefault('preset_picker', st.session_state.get('saved_preset', 'Write your own task'))
            st.selectbox('Quick start', choices, index=None, key='preset_picker', on_change=pick_preset)
            st.session_state.setdefault('task_instruction', st.session_state['instruction_draft'])
            instruction = st.text_area('Your instruction', key='task_instruction', height=155, label_visibility='collapsed',
                on_change=save_instruction, placeholder='Describe the filters, flags, calculations, grouping or report you need…')
            st.caption('Generating a plan sends your instruction and file names, column names/types to the configured model. File contents stay local.')
            ready = bool(manifest) and not file_error and bool(instruction.strip()) and settings['configured']
            if st.button('✦ Generate plan', type='primary', width='stretch', disabled=not ready):
                clear_plan()
                try:
                    provider = Provider(settings['base_url'], settings['model'], settings['key'], settings['structured'])
                    with st.spinner('Building and validating your plan…'):
                        result = compile_workflow(instruction, manifest, provider, settings['strategy'], settings['retries'])
                    st.session_state['compilation'] = result
                    if result.workflow:
                        install_plan(result)
                        st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            result = st.session_state.get('compilation')
            if result and result.error:
                st.error(result.error)
            with st.expander('Have a saved workflow?'):
                imported = st.file_uploader('Load workflow JSON', type=['json'], key='import_json')
                saved, bindings = None, {}
                if imported is not None:
                    try:
                        saved = parse_workflow(imported.getvalue())
                        signature = hashlib.sha256(imported.getvalue() + json.dumps(sorted(manifest)).encode()).hexdigest()[:10]
                        for step in saved.steps:
                            if step.operation == 'read':
                                bindings[step.id] = st.multiselect('Files for ' + step.label, list(manifest),
                                    default=[name for name in step.files if name in manifest], key='binding_' + signature + '_' + step.id)
                    except ValueError as exc:
                        st.error(str(exc))
                if st.button('Load plan · no model call', disabled=saved is None or not manifest or bool(file_error)):
                    try:
                        saved = remap_inputs(saved, bindings, manifest)
                        clear_plan()
                        install_plan(Compilation(workflow=saved, mode='imported'))
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            if result and result.workflow:
                st.button('Continue with current plan →', on_click=go_to_stage, args=('plan',))


def record_execution(current, run, files, editor):
    st.session_state['run'] = run
    st.session_state['validated_editor'] = editor
    st.session_state['executed_workflow'] = current.model_dump()
    original = st.session_state['compilation'].workflow
    st.session_state['manual_edits'] = int(editor != original.model_dump_json(indent=2))
    timestamp = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%H:%M:%S IST')
    input_fingerprint = hashlib.sha256(json.dumps({n: hashlib.sha256(b).hexdigest() for n, b in files.items()}, sort_keys=True).encode()).hexdigest()
    st.session_state['current_input_fingerprint'] = input_fingerprint
    snapshots, snapshot = retain_snapshot(st.session_state.get('snapshots', []), current, run, timestamp, input_fingerprint)
    st.session_state['snapshots'] = snapshots
    st.session_state['active_run_id'] = snapshot.id if snapshot else None
    st.session_state['snapshot_notice'] = run.error is None and snapshot is None
    history = st.session_state.setdefault('run_history', [])
    history.insert(0, {'Workflow': current.title, 'Status': 'Needs attention' if run.error else 'Completed',
        'Time': timestamp, 'Files created': len(run.artifacts), 'Steps completed': sum(t['status'] == 'success' for t in run.trace)})
    del history[20:]
    st.session_state.pop('report_search', None)


def plan_stage(files, manifest, file_error):
    st.button('← Edit task & files', on_click=go_to_stage, args=('describe',))
    compilation = st.session_state['compilation']
    with st.container(border=True, key='panel_plan'):
        section('02 · REVIEW', compilation.workflow.title)
        st.session_state.setdefault('workflow_editor', st.session_state.get('workflow_draft', compilation.workflow.model_dump_json(indent=2)))
        rule_controls(manifest)
        with st.expander('Edit or save plan'):
            editor = st.text_area('Workflow JSON', key='workflow_editor', height=360, on_change=save_workflow)
            st.download_button('Save plan · JSON', editor, 'workflow.json', mime='application/json')
        current = None
        try:
            current = Workflow.model_validate_json(editor)
            validate_workflow(current, manifest)
        except ValueError as exc:
            st.error(str(exc))
        if file_error:
            st.error(file_error)
        if st.session_state.get('validated_editor') != editor:
            st.session_state.pop('run', None)
        run = st.session_state.get('run')
        markup(plan_markup(current or compilation.workflow, run.trace if run else ()))
        if st.button('Run workflow →', type='primary', width='stretch', disabled=current is None or bool(file_error)):
            try:
                with st.spinner('Running your plan…'):
                    run = execute(current, files)
                record_execution(current, run, files, editor)
                if run.error is None:
                    st.session_state['flow_stage'] = 'result'
                    st.rerun()
            except Exception as exc:
                st.error(str(exc))
        run = st.session_state.get('run')
        if run and run.error:
            st.error('Execution stopped: ' + run.error)
        elif run:
            st.button('View current report →', on_click=go_to_stage, args=('result',))
        with st.expander('Technical details'):
            st.caption('Imported workflow' if compilation.mode == 'imported' else f'{compilation.seconds:.2f}s · {compilation.api_calls} API request attempts · {len(compilation.attempts)} generation attempts · {compilation.prompt_tokens + compilation.completion_tokens:,} reported tokens')
            if compilation.requirements:
                st.json({'request_coverage': compilation.requirements})
            if compilation.decomposition:
                st.text(compilation.decomposition)
            st.json(compilation.attempts)
            if run:
                st.dataframe(run.trace, hide_index=True, width='stretch')


def workspace(settings):
    # Migrate old sessions away from preloaded preset inputs without making a request.
    if st.session_state.get('guided_flow_version') != 1:
        clear_plan()
        st.session_state['active_files'] = {}
        st.session_state['guided_flow_version'] = 1
    files = st.session_state.setdefault('active_files', {})
    st.session_state.setdefault('instruction_draft', '')
    manifest, file_error = {}, None
    try:
        if st.session_state.get('duplicate_uploads'):
            raise ValueError('Uploaded filenames must be unique.')
        if files:
            manifest = inventory(files)
    except Exception as exc:
        file_error = str(exc)
    fingerprint = hashlib.sha256(json.dumps({'compiler_revision': 'schema-aware-coverage-v2', 'instruction': st.session_state['instruction_draft'],
        'files': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
        **{k: v for k, v in settings.items() if k != 'key'}}, sort_keys=True).encode()).hexdigest()
    if st.session_state.get('fingerprint') != fingerprint:
        clear_plan()
        st.session_state['fingerprint'] = fingerprint
    compilation = st.session_state.get('compilation')
    run = st.session_state.get('run')
    stage = resolve_stage(st.session_state.get('flow_stage', 'describe'), bool(compilation and compilation.workflow), bool(run and not run.error))
    st.session_state['flow_stage'] = stage
    markup(progress_markup(compiled=stage != 'describe', finished=stage == 'result'))
    with st.container(key='stage_' + stage):
        if stage == 'describe':
            describe_stage(settings, manifest, file_error)
        elif stage == 'plan':
            plan_stage(files, manifest, file_error)
        else:
            st.button('← Adjust plan', on_click=go_to_stage, args=('plan',))
            with st.container(border=True, key='panel_output'):
                results_panel(compilation, run)
    markup('<div class="workspace-footer"><span>✦ Prompt Compiler</span><span>Made for a little less manual work.</span></div>')


def research():
    st.title('Research & evaluation')
    with st.container(border=True):
        section('METHODOLOGY', 'Three approaches. One fair comparison.')
        st.dataframe([
            {'Approach': 'Standard', 'Method': 'One-shot structured generation', 'Initial calls': 1},
            {'Approach': 'Plan first', 'Method': 'Decomposition, then generation', 'Initial calls': 2},
            {'Approach': 'Plan + self-correction', 'Method': 'Decomposition, generation, validation feedback', 'Initial calls': 2},
        ], hide_index=True, width='stretch')
        st.write('Measure schema validity, workflow correctness, execution success, output correctness, retries, human edits, latency and token usage.')
        st.caption('Use identical held-out tasks and model settings. Local executor checks are separate from model performance evidence.')
    with st.expander('Run benchmarks from your terminal'):
        st.code('.\\.venv\\Scripts\\python.exe -m pytest -q\n.\\.venv\\Scripts\\python.exe -m prompt_compiler.benchmark --live', language='powershell')
        st.caption('Live mode reads the server-side .env and makes provider calls only when you explicitly run that command.')


page, settings = sidebar()
header(page, settings)
if page == 'Workspace':
    workspace(settings)
elif page == 'Run history':
    st.title('A little history of getting things done')
    history = st.session_state.get('run_history', [])
    with st.container(border=True):
        if history:
            st.dataframe(history, hide_index=True, width='stretch')
            st.caption('Last 20 runs in this session. Reports remain available for the current workflow only.')
        else:
            empty_state('Your first run belongs here', 'Run a workflow to start your session history.')
else:
    research()
