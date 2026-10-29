from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
from html import escape
from io import BytesIO
import json
import os
from pathlib import Path
import zipfile
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import streamlit as st

from prompt_compiler.compiler import Compilation, compile_workflow
from prompt_compiler.demo import DEMOS, sample_files
from prompt_compiler.executor import execute, export_table
from prompt_compiler.files import inventory, read_file
from prompt_compiler.presentation import plan_markup, progress_markup
from prompt_compiler.provider import Provider
from prompt_compiler.schema import Workflow
from prompt_compiler.validation import validate_workflow
from prompt_compiler.workspace_tools import build_bundle, import_workflow, search_table

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


PLAN_STATE = ['compilation', 'run', 'workflow_editor', 'workflow_draft', 'validated_editor', 'manual_edits', 'executed_workflow', 'report_search']


def clear_plan():
    for name in PLAN_STATE:
        st.session_state.pop(name, None)


def new_workspace():
    clear_plan()
    st.session_state['navigation'] = 'Workspace'
    st.session_state['instruction_draft'] = ''
    st.session_state['task_instruction'] = ''
    st.session_state['preset_picker'] = 'Write your own task'
    st.session_state['saved_preset'] = 'Write your own task'
    st.session_state['active_files'] = {}
    st.session_state['sample_pack'] = False
    st.session_state['duplicate_uploads'] = False
    st.session_state['upload_epoch'] = st.session_state.get('upload_epoch', 0) + 1


def use_sample_pack():
    st.session_state['active_files'] = sample_files()
    st.session_state['sample_pack'] = True
    st.session_state['duplicate_uploads'] = False
    st.session_state['upload_epoch'] = st.session_state.get('upload_epoch', 0) + 1


def clear_files():
    st.session_state['active_files'] = {}
    st.session_state['sample_pack'] = False
    st.session_state['duplicate_uploads'] = False
    st.session_state['upload_epoch'] = st.session_state.get('upload_epoch', 0) + 1


def save_uploads(widget_key):
    uploads = st.session_state.get(widget_key) or []
    st.session_state['active_files'] = {f.name: f.getvalue() for f in uploads}
    st.session_state['duplicate_uploads'] = len(st.session_state['active_files']) != len(uploads)
    st.session_state['sample_pack'] = False


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
        sample_mode = st.toggle('Sample mode', value=True, help='Try the three built-in tasks without any model requests.')
        base = os.getenv('LLM_BASE_URL', '').strip()
        model = os.getenv('LLM_MODEL', '').strip()
        key = os.getenv('LLM_API_KEY', '').strip()
        settings = {'mode': 'Sample workspace' if sample_mode else 'Connected model', 'strategy': 'feedback', 'retries': 2,
                    'base_url': base, 'model': model, 'key': key, 'structured': os.getenv('LLM_STRUCTURED', 'true').lower() != 'false'}
        configured = bool(base and model and (key or base.startswith(('http://localhost:', 'http://127.0.0.1:'))))
        settings['configured'] = configured
        if sample_mode:
            st.caption('Three ready-to-run examples. No model calls.')
        elif configured:
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
    sample = settings['mode'] == 'Sample workspace'
    status = 'Sample mode' if sample else 'Engine ready' if settings['configured'] else 'Setup needed'
    markup(f'<div class="topline"><span>Studio <span style="color:#b7bfcb;margin:0 9px">/</span><b>{escape(page)}</b></span><span class="connection-tag {"live" if not sample and settings["configured"] else ""}">{status}</span></div>')


def audit_payload(compilation, run):
    data = asdict(compilation)
    data['workflow'] = compilation.workflow.model_dump() if compilation.workflow else None
    return {'compilation': data, 'executed_workflow': st.session_state.get('executed_workflow'),
            'trace': run.trace, 'checks': run.checks, 'error': run.error,
            'manual_workflow_edit_present': st.session_state.get('manual_edits', 0)}


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
    st.session_state.setdefault('active_files', sample_files())
    st.session_state.setdefault('sample_pack', True)
    epoch = st.session_state.get('upload_epoch', 0)
    widget_key = f'upload_widget_{epoch}'
    st.file_uploader('Drop documents or spreadsheets here', type=['txt', 'pdf', 'csv', 'xlsx'],
                     accept_multiple_files=True, key=widget_key, on_change=save_uploads, args=(widget_key,))
    first, second = st.columns([1.5, 1])
    first.button('Try sample invoices', on_click=use_sample_pack, width='stretch')
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
        label = 'Sample pack' if st.session_state.get('sample_pack') else 'Your uploads'
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
        if st.session_state.get('sample_pack'):
            with st.expander('Download sample pack'):
                buffer = BytesIO()
                with zipfile.ZipFile(buffer, 'w') as archive:
                    for name, content in files.items():
                        archive.writestr(name, content)
                st.download_button('Get sample files', buffer.getvalue(), 'sample_invoices.zip')
    st.caption('TXT, PDF, CSV, XLSX · 10 MB per file · text-based PDFs')
    return files, manifest, error


def workspace(settings):
    markup('<div class="studio-hero"><div><span class="hero-kicker">LESS BUSYWORK. MORE POSSIBILITY.</span><h1>What are we making today?</h1><p>Your task, a clear plan, and something worth downloading.</p></div><div class="hero-art" aria-hidden="true"><i class="orbit one"></i><i class="orbit two"></i><span class="art-tile violet">✦</span><span class="art-tile mint">↗</span><span class="art-tile peach">✓</span></div></div>')
    request_col, files_col = st.columns([1.8, 1], gap='large')
    with files_col:
        with st.container(border=True, key='panel_files'):
            files, manifest, file_error = inputs_panel()
    with request_col:
        with st.container(border=True, key='panel_request'):
            section('START WITH AN IDEA', 'Tell us what needs doing')
            choices = ['Write your own task', *DEMOS]
            st.session_state.setdefault('preset_picker', st.session_state.get('saved_preset', 'Invoice review'))
            # Session state supplies the initial value; index=None avoids competing defaults.
            st.selectbox('Quick start', choices, index=None, key='preset_picker', on_change=pick_preset)
            st.session_state.setdefault('instruction_draft', DEMOS['Invoice review'])
            st.session_state.setdefault('task_instruction', st.session_state['instruction_draft'])
            instruction = st.text_area('Your instruction', key='task_instruction', height=155, label_visibility='collapsed',
                on_change=save_instruction, placeholder='Read these invoices, flag totals above INR 50,000, and create an Excel report…')
            sample_mode = settings['mode'] == 'Sample workspace'
            st.caption('Sample mode: choose one of the three quick starts.' if sample_mode else 'New plans send your instruction and file names/columns to the configured model. File contents stay local.')
            fingerprint = hashlib.sha256(json.dumps({'instruction': instruction,
                'files': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
                **{k: v for k, v in settings.items() if k != 'key'}}, sort_keys=True).encode()).hexdigest()
            if st.session_state.get('fingerprint') != fingerprint:
                clear_plan()
                st.session_state['fingerprint'] = fingerprint
            ready = bool(manifest) and not file_error and bool(instruction.strip()) and (sample_mode or settings['configured'])
            if st.button('✦ Generate plan', type='primary', width='stretch', disabled=not ready):
                clear_plan()
                try:
                    provider = None if sample_mode else Provider(settings['base_url'], settings['model'], settings['key'], settings['structured'])
                    with st.spinner('Putting your plan together…'):
                        result = compile_workflow(instruction, manifest, provider, settings['strategy'], settings['retries'])
                    st.session_state['compilation'] = result
                    if result.workflow:
                        st.session_state['workflow_editor'] = result.workflow.model_dump_json(indent=2)
                        st.session_state['workflow_draft'] = st.session_state['workflow_editor']
                    else:
                        st.error(result.error)
                except Exception as exc:
                    st.error(str(exc))
            with st.expander('Have a saved workflow?'):
                imported = st.file_uploader('Load workflow JSON', type=['json'], key='import_json')
                if st.button('Load plan · no model call', disabled=imported is None or not manifest or bool(file_error)):
                    try:
                        saved = import_workflow(imported.getvalue(), manifest)
                        clear_plan()
                        st.session_state['compilation'] = Compilation(workflow=saved, mode='imported')
                        st.session_state['workflow_editor'] = saved.model_dump_json(indent=2)
                        st.session_state['workflow_draft'] = st.session_state['workflow_editor']
                    except Exception as exc:
                        st.error(str(exc))

    compilation = st.session_state.get('compilation')
    run = st.session_state.get('run')
    journey = st.empty()
    plan_col, output_col = st.columns([1, 1.35], gap='large')
    with plan_col:
        with st.container(border=True, key='panel_plan'):
            section('THE PLAN', compilation.workflow.title if compilation and compilation.workflow else 'Ready, set, workflow')
            current, editor = None, None
            if compilation and compilation.workflow:
                if compilation.mode == 'imported':
                    st.caption('Saved plan · runs locally without model calls')
                st.session_state.setdefault('workflow_editor', st.session_state.get('workflow_draft', compilation.workflow.model_dump_json(indent=2)))
                with st.expander('Edit or save plan'):
                    editor = st.text_area('Workflow JSON', key='workflow_editor', height=360, on_change=save_workflow)
                    st.download_button('Save plan · JSON', editor, 'workflow.json', mime='application/json')
                try:
                    current = Workflow.model_validate_json(editor)
                    validate_workflow(current, manifest)
                except Exception as exc:
                    current = None
                    st.error(str(exc))
                if st.session_state.get('validated_editor') != editor:
                    st.session_state.pop('run', None)
                    run = None
                if st.button('Run workflow  →', type='primary', width='stretch', disabled=current is None or bool(file_error)):
                    try:
                        with st.spinner('Making it happen…'):
                            run = execute(current, files)
                        st.session_state['run'] = run
                        st.session_state['validated_editor'] = editor
                        st.session_state['executed_workflow'] = current.model_dump()
                        st.session_state['manual_edits'] = int(editor != compilation.workflow.model_dump_json(indent=2))
                        history = st.session_state.setdefault('run_history', [])
                        history.insert(0, {'Workflow': current.title, 'Status': 'Needs attention' if run.error else 'Completed',
                            'Time': datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%H:%M:%S IST'), 'Files created': len(run.artifacts),
                            'Steps completed': sum(t['status'] == 'success' for t in run.trace)})
                        del history[20:]
                        st.session_state.pop('report_search', None)
                    except Exception as exc:
                        st.error(str(exc))
                markup(plan_markup(current or compilation.workflow, run.trace if run else ()))
                with st.expander('Technical details'):
                    st.caption('Imported workflow' if compilation.mode == 'imported' else f'{compilation.seconds:.2f}s · {len(compilation.attempts)} attempts · {compilation.prompt_tokens + compilation.completion_tokens:,} reported tokens')
                    if compilation.decomposition:
                        st.text(compilation.decomposition)
                    st.json(compilation.attempts)
            else:
                empty_state('A plan for your next big little task', 'Start with your files and an instruction.', '⌘')
                if compilation and compilation.error:
                    st.error(compilation.error)
    with output_col:
        with st.container(border=True, key='panel_output'):
            results_panel(compilation, run)
    journey.markdown(progress_markup(bool(compilation and compilation.workflow), bool(run and not run.error)), unsafe_allow_html=True)
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
        st.caption('Use identical held-out tasks and model settings. Offline presets are development checks, not model performance evidence.')
    with st.expander('Run benchmarks from your terminal'):
        st.code('.\\.venv\\Scripts\\python.exe -m prompt_compiler.benchmark --offline\n.\\.venv\\Scripts\\python.exe -m prompt_compiler.benchmark --live', language='powershell')
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
