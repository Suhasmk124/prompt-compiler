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

from prompt_compiler.compiler import compile_workflow
from prompt_compiler.demo import DEMOS, sample_files
from prompt_compiler.executor import execute
from prompt_compiler.files import inventory
from prompt_compiler.presentation import PROVIDERS, file_markup, plan_markup, progress_markup
from prompt_compiler.provider import Provider
from prompt_compiler.schema import Workflow
from prompt_compiler.validation import validate_workflow

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Prompt Compiler · Workspace', page_icon='◈', layout='wide')
st.markdown('<style>' + (ROOT / 'assets/style.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


def markup(value):
    st.markdown(value, unsafe_allow_html=True)


def empty_state(title, text, symbol='◇'):
    markup(f'<div class="empty-state"><div class="empty-icon">{escape(symbol)}</div><strong>{escape(title)}</strong><p>{escape(text)}</p></div>')


def section(kicker, title, subtitle=''):
    markup(f'<div class="section-kicker">{escape(kicker)}</div>')
    st.subheader(title)
    if subtitle:
        markup(f'<p class="panel-subtitle">{escape(subtitle)}</p>')


def save_uploads():
    uploads = st.session_state.get('upload_widget') or []
    st.session_state['uploaded_files'] = {f.name: f.getvalue() for f in uploads}
    st.session_state['duplicate_uploads'] = len(st.session_state['uploaded_files']) != len(uploads)


def save_instruction():
    st.session_state['instruction_draft'] = st.session_state['task_instruction']


def save_workflow():
    st.session_state['workflow_draft'] = st.session_state['workflow_editor']


def save_source():
    st.session_state['saved_source'] = st.session_state['input_source']


def pick_preset():
    choice = st.session_state['preset_picker']
    st.session_state['saved_preset'] = choice
    if choice in DEMOS:
        st.session_state['instruction_draft'] = DEMOS[choice]
        st.session_state['task_instruction'] = DEMOS[choice]


def sidebar():
    with st.sidebar:
        markup('<div class="brand"><div class="brand-icon">›_</div><div><strong>Prompt Compiler</strong><small>WORKFLOW AUTOMATION</small></div></div>')
        markup('<div class="nav-label">YOUR WORKSPACE</div>')
        page = st.radio('Navigation', ['Workspace', 'Run history', 'Research'], label_visibility='collapsed')
        st.divider()
        markup('<div class="nav-label">CONNECTION</div>')
        mode = st.selectbox('Execution mode', ['Sample workspace', 'Connected model'], label_visibility='collapsed', key='connection_mode')
        settings = {'mode': mode, 'strategy': 'feedback', 'retries': 2, 'base_url': '', 'model': '', 'key': '', 'structured': True, 'consent': False}
        if mode == 'Sample workspace':
            st.caption('Explore three sample tasks. No API key required.')
        else:
            configured_url = os.getenv('LLM_BASE_URL', '')
            default_provider = 'Custom endpoint' if configured_url and 'api.groq.com' not in configured_url else 'Groq'
            provider_name = st.selectbox('Provider', list(PROVIDERS), index=list(PROVIDERS).index(default_provider), key='provider_choice')
            preset = PROVIDERS[provider_name]
            initial_base = configured_url if configured_url and provider_name == default_provider else preset['base_url']
            initial_model = os.getenv('LLM_MODEL', '') if provider_name == default_provider else ''
            base = st.text_input('API base URL', value=initial_base, key='base_' + provider_name)
            model = st.text_input('Model', value=initial_model or preset['model'], key='model_' + provider_name)
            key = st.text_input('API key', value=os.getenv('LLM_API_KEY', ''), type='password', key='key_' + provider_name)
            strict = st.checkbox('Strict structured output', value=True, key='strict_' + provider_name)
            consent = st.checkbox('Allow instruction and file metadata to be sent to this endpoint', key='consent_' + provider_name)
            st.caption('Document contents stay local. Keys are not saved by the app.')
            if provider_name == 'Groq':
                st.link_button('Get a Groq API key ↗', 'https://console.groq.com/keys', width='stretch')
                st.caption('Free-tier quotas apply. Plan + self-correction is live-tested; Standard uses fewer requests.')
            settings.update(base_url=base, model=model, key=key, structured=strict, consent=consent)
        with st.expander('Workflow preferences'):
            approach = st.selectbox('Planning approach', ['Standard', 'Plan first', 'Plan + self-correction'], index=2,
                                    help='Standard: one model call. Plan first: decomposition then generation. Self-correction: retries invalid workflows.')
            settings['strategy'] = {'Standard': 'one_shot', 'Plan first': 'decompose', 'Plan + self-correction': 'feedback'}[approach]
            settings['retries'] = st.slider('Correction budget', 0, 3, 2, disabled=settings['strategy'] != 'feedback')
        markup('<div class="sidebar-note">Local workspace<br>Documents and spreadsheets<br>TXT · PDF · CSV · XLSX</div>')
    return page, settings


def header(page, settings):
    live = settings['mode'] == 'Connected model'
    connection = settings['model'] if live and settings['model'] else 'Sample workspace'
    markup(f'<div class="topline"><span>Workspace <span style="color:#b7bfcb;margin:0 9px">/</span> <b>{escape(page)}</b></span><span class="connection-tag {"live" if live else ""}">{escape(connection)} · {"Configured" if live else "Offline"}</span></div>')


def audit_payload(compilation, run):
    data = asdict(compilation)
    data['workflow'] = compilation.workflow.model_dump() if compilation.workflow else None
    return {'compilation': data, 'executed_workflow': st.session_state.get('executed_workflow'),
            'trace': run.trace, 'checks': run.checks, 'error': run.error,
            'manual_workflow_edit_present': st.session_state.get('manual_edits', 0)}


def results_panel(compilation, run):
    section('YOUR OUTPUT', 'Report preview', 'Review the result and download your finished files.')
    if not run:
        empty_state('Your report will appear here', 'Once you approve and run the plan, you can preview the result and download your report.', '↧')
        return
    if run.error:
        st.error('The workflow stopped: ' + run.error)
    else:
        file_count = len(run.artifacts)
        markup(f'<div class="report-summary"><div class="report-icon">✓</div><div><strong>Your report is ready</strong><small>{file_count} file{"s" if file_count != 1 else ""} created · export structure verified</small></div></div>')
    if run.tables:
        frame = next(reversed(run.tables.values()))
        seconds = sum(t['seconds'] for t in run.trace)
        markup(f'<div class="stat-strip"><div><b>{len(frame):,}</b><small>OUTPUT ROWS</small></div><div><b>{len(frame.columns)}</b><small>COLUMNS</small></div><div><b>{seconds:.2f}s</b><small>RUN TIME</small></div></div>')
        st.dataframe(frame, hide_index=True, width='stretch', height=280)
        if 'extraction_status' in frame and (frame['extraction_status'] != 'ok').any():
            st.warning('Some invoice fields need review. Missing values have been kept explicit.')
        st.caption('Check the report contents against your request. Successful execution alone does not prove task correctness.')
    for name, content in run.artifacts.items():
        mime = 'text/csv' if name.endswith('.csv') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        st.download_button('Download ' + name, content, file_name=name, mime=mime,
                           type='primary', width='stretch', key='download_' + name)
    with st.expander('Run details and intermediate outputs'):
        st.dataframe(run.trace, hide_index=True, width='stretch')
        if run.tables:
            selected = st.selectbox('Inspect step output', list(run.tables))
            st.dataframe(run.tables[selected], hide_index=True, width='stretch')
        for check in run.checks:
            st.caption(check)
        st.download_button('Download run audit', json.dumps(audit_payload(compilation, run), indent=2, ensure_ascii=False),
                           'run_audit.json', mime='application/json')


def workspace(settings):
    st.title('Workflow workspace')
    markup('<p class="page-intro">Describe what needs doing. Review the plan. Take the finished work with you.</p>')
    request_col, files_col = st.columns([1.8, 1], gap='large')
    manifest, file_error = {}, None
    with files_col:
        with st.container(border=True, key='panel_files'):
            section('INPUTS', 'Your files', 'The source material for this workflow.')
            st.session_state.setdefault('input_source', st.session_state.get('saved_source', 'Sample invoices'))
            source = st.radio('Input source', ['Sample invoices', 'Upload files'], horizontal=True, key='input_source', on_change=save_source)
            use_samples = source == 'Sample invoices'
            if not use_samples:
                st.file_uploader('Add documents or spreadsheets', type=['txt', 'pdf', 'csv', 'xlsx'],
                                 accept_multiple_files=True, key='upload_widget', on_change=save_uploads)
            files = sample_files() if use_samples else st.session_state.get('uploaded_files', {})
            try:
                if not use_samples and st.session_state.get('duplicate_uploads'):
                    raise ValueError('Uploaded filenames must be unique.')
                if files:
                    manifest = inventory(files)
            except Exception as exc:
                file_error = str(exc)
                st.error(file_error)
            if manifest:
                for name, metadata in manifest.items():
                    markup(file_markup(name, metadata))
                with st.expander('File details'):
                    st.json(manifest)
                    if use_samples:
                        buffer = BytesIO()
                        with zipfile.ZipFile(buffer, 'w') as archive:
                            for name, content in files.items():
                                archive.writestr(name, content)
                        st.download_button('Download sample files', buffer.getvalue(), 'sample_invoices.zip')
            elif not file_error:
                empty_state('Add your source files', 'Upload a document or table to give your workflow something to work with.', '+')
            st.caption('Up to 20 files · 10 MB each. PDFs must contain selectable text.')
    with request_col:
        with st.container(border=True, key='panel_request'):
            section('NEW WORKFLOW', 'What would you like to do?', 'Give a clear instruction, including the report you want at the end.')
            choices = ['Write your own task', *DEMOS]
            st.session_state.setdefault('preset_picker', st.session_state.get('saved_preset', 'Invoice review'))
            st.selectbox('Use an example', choices, index=1, key='preset_picker', on_change=pick_preset)
            st.session_state.setdefault('instruction_draft', DEMOS['Invoice review'])
            st.session_state.setdefault('task_instruction', st.session_state['instruction_draft'])
            instruction = st.text_area('Your instruction', key='task_instruction', height=155,
                                       label_visibility='collapsed', on_change=save_instruction,
                                       placeholder='Read these invoices, flag totals above INR 50,000, and create an Excel report…')
            if settings['mode'] == 'Sample workspace':
                st.caption('Sample mode runs the three exact example instructions. Connect a model for your own requests.')
            else:
                st.caption('Supported actions: extract invoice fields, flag, filter, calculate, summarize, sort, and export.')
            fingerprint = hashlib.sha256(json.dumps({'instruction': instruction,
                'files': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
                **{k: v for k, v in settings.items() if k not in {'key', 'consent'}}}, sort_keys=True).encode()).hexdigest()
            if st.session_state.get('fingerprint') != fingerprint:
                for name in ['compilation', 'run', 'workflow_editor', 'workflow_draft', 'validated_editor', 'manual_edits', 'executed_workflow']:
                    st.session_state.pop(name, None)
                st.session_state['fingerprint'] = fingerprint
            connected = settings['mode'] == 'Connected model'
            ready = bool(manifest) and not file_error and bool(instruction.strip()) and (not connected or settings['consent'])
            if st.button('Generate plan  →', type='primary', width='stretch', disabled=not ready):
                for name in ['compilation', 'run', 'validated_editor', 'executed_workflow']:
                    st.session_state.pop(name, None)
                try:
                    provider = Provider(settings['base_url'], settings['model'], settings['key'], settings['structured']) if connected else None
                    with st.spinner('Turning your instruction into a validated plan…'):
                        result = compile_workflow(instruction, manifest, provider, settings['strategy'], settings['retries'])
                    st.session_state['compilation'] = result
                    for name in ['run', 'validated_editor', 'executed_workflow']:
                        st.session_state.pop(name, None)
                    st.session_state['manual_edits'] = 0
                    if result.workflow:
                        st.session_state['workflow_editor'] = result.workflow.model_dump_json(indent=2)
                        st.session_state['workflow_draft'] = st.session_state['workflow_editor']
                    else:
                        st.error(result.error)
                except Exception as exc:
                    st.error(str(exc))

    compilation = st.session_state.get('compilation')
    run = st.session_state.get('run')
    journey = st.empty()
    plan_col, output_col = st.columns([1, 1.35], gap='large')
    with plan_col:
        with st.container(border=True, key='panel_plan'):
            section('WORKFLOW', compilation.workflow.title if compilation and compilation.workflow else 'Your execution plan',
                    'Review each step before running the workflow.')
            current, editor = None, None
            if compilation and compilation.workflow:
                st.session_state.setdefault('workflow_editor', st.session_state.get('workflow_draft', compilation.workflow.model_dump_json(indent=2)))
                with st.expander('Advanced · edit workflow JSON'):
                    editor = st.text_area('Workflow JSON', key='workflow_editor', height=360, on_change=save_workflow)
                    st.download_button('Save workflow', editor, 'workflow.json', mime='application/json')
                try:
                    current = Workflow.model_validate_json(editor)
                    validate_workflow(current, manifest)
                except Exception as exc:
                    current = None
                    st.error(str(exc))
                if st.session_state.get('validated_editor') != editor:
                    st.session_state.pop('run', None)
                    run = None
                execute_clicked = st.button('Run workflow  →', type='primary', width='stretch', disabled=current is None or bool(file_error))
                if execute_clicked:
                    try:
                        with st.spinner('Running your workflow…'):
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
                    except Exception as exc:
                        st.error(str(exc))
                if current:
                    markup(f'<div class="plan-summary">✓ &nbsp; {len(current.steps)} steps · inputs and dependencies checked</div>')
                markup(plan_markup(current or compilation.workflow, run.trace if run else ()))
                with st.expander('How this plan was generated'):
                    st.caption(f'{compilation.seconds:.2f}s · {len(compilation.attempts)} generation attempts · {compilation.prompt_tokens + compilation.completion_tokens:,} reported tokens')
                    if compilation.decomposition:
                        st.text(compilation.decomposition)
                    st.json(compilation.attempts)
            else:
                empty_state('A clear plan, step by step', 'Add your files and describe the task. We’ll turn your instruction into a plan you can inspect before it runs.', '⌘')
                if compilation and compilation.error:
                    st.error(compilation.error)
    with output_col:
        with st.container(border=True, key='panel_output'):
            results_panel(compilation, run)
    journey.markdown(progress_markup(bool(compilation and compilation.workflow), bool(run and not run.error)), unsafe_allow_html=True)
    markup('<div class="workspace-footer"><span>Prompt Compiler · Local workspace</span><span>Your files stay in this session</span></div>')


def research():
    st.title('Research & evaluation')
    markup('<p class="page-intro">The experiment controls behind the workflow. Separate from the everyday workspace.</p>')
    with st.container(border=True):
        section('METHODOLOGY', 'Compare three planning approaches')
        st.dataframe([
            {'Approach': 'Standard', 'Method': 'One-shot structured generation', 'Calls before retries': 1},
            {'Approach': 'Plan first', 'Method': 'Decomposition, then structured generation', 'Calls before retries': 2},
            {'Approach': 'Plan + self-correction', 'Method': 'Decomposition, generation, bounded validation feedback', 'Calls before retries': 2},
        ], hide_index=True, width='stretch')
        st.write('Measure schema validity, workflow correctness, execution success, final-output correctness, automatic retries, human corrections, latency and token usage.')
        st.caption('Use the same held-out tasks and model settings. Offline presets are development checks, not evidence of LLM performance. Human correction counts need explicit recording.')
    with st.container(border=True):
        section('MODEL SETUP', 'Start with Groq · GPT-OSS 20B')
        st.write('A hosted open-weight model with a free API tier and strict structured-output support. Select Connected model → Groq in the sidebar and add your key.')
        st.caption('Published limits checked October 29, 2026: 30 requests/minute, 1,000 requests/day, 8,000 tokens/minute, 200,000 tokens/day. Your account limits are authoritative. A workflow may use several calls.')
        st.link_button('View official Groq limits ↗', 'https://console.groq.com/docs/rate-limits')
    with st.expander('Run the benchmark from your terminal'):
        st.code('.\\.venv\\Scripts\\python.exe -m prompt_compiler.benchmark --offline\n.\\.venv\\Scripts\\python.exe -m prompt_compiler.benchmark --live', language='powershell')
        st.caption('Live mode reads .env and makes provider calls. The initial benchmark contains three development fixtures; expand and split the dataset before drawing research conclusions.')


page, settings = sidebar()
header(page, settings)
if page == 'Workspace':
    workspace(settings)
elif page == 'Run history':
    st.title('Run history')
    markup('<p class="page-intro">A record of workflow runs in this session.</p>')
    history = st.session_state.get('run_history', [])
    with st.container(border=True):
        if history:
            st.dataframe(history, hide_index=True, width='stretch')
            st.caption('Up to 20 recent runs. History contains summaries only; files and reports are available for the current workspace run. Closing the session clears this history.')
        else:
            empty_state('Your work starts here', 'Completed and failed workflow runs will appear here after you run a plan.')
else:
    research()
