from __future__ import annotations

import hashlib
import html
import json
import os
from dataclasses import asdict
from io import BytesIO
import zipfile
import streamlit as st
from dotenv import load_dotenv
from prompt_compiler.compiler import compile_workflow
from prompt_compiler.demo import DEMOS, sample_files
from prompt_compiler.files import inventory
from prompt_compiler.schema import Workflow
from prompt_compiler.validation import validate_workflow
from prompt_compiler.executor import execute
from prompt_compiler.provider import Provider

load_dotenv()
st.set_page_config(page_title='Prompt Compiler', page_icon='◈', layout='wide')
st.markdown('''<style>
.block-container {max-width:1200px;padding-top:2.5rem}
h1 {letter-spacing:-1.8px;font-weight:750!important}
[data-testid="stMetric"] {background:white;border:1px solid #E0E8EF;border-radius:12px;padding:16px}
.eyebrow {color:#087F8C;font-size:12px;font-weight:700;letter-spacing:2px}
.node {background:white;border:1px solid #DAE5ED;border-left:4px solid #087F8C;border-radius:10px;padding:16px;margin:10px 0}
.node small {color:#657889}.node b{font-size:16px}
</style>''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('### ◈ Prompt Compiler')
    st.caption('Describe it. Compile it. Run it.')
    st.divider()
    mode = st.radio('Compiler', ['Offline demo', 'Connected LLM'])
    strategy_label = st.selectbox('Prompt strategy', ['Decomposition + feedback', 'Decomposition', 'One-shot'])
    strategy = {'Decomposition + feedback': 'feedback', 'Decomposition': 'decompose', 'One-shot': 'one_shot'}[strategy_label]
    retries = st.slider('Maximum correction retries', 0, 3, 2, disabled=strategy != 'feedback')
    base_url = model = key = ''
    structured = True
    consent = False
    if mode == 'Connected LLM':
        base_url = st.text_input('API base URL', value=os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1'))
        model = st.text_input('Model ID', value=os.getenv('LLM_MODEL', ''), placeholder='Your provider’s model identifier')
        key = st.text_input('API key', value=os.getenv('LLM_API_KEY', ''), type='password')
        structured = st.checkbox('Provider supports strict JSON Schema', value=True)
        consent = st.checkbox('Send my instruction and file metadata to this endpoint')
        st.caption('Only instruction, filenames, column names and row counts are sent. File contents are processed locally. Calls may incur provider charges.')
    else:
        st.info('Three preset invoice examples. No model calls. This is not an LLM benchmark.')
    st.divider()
    st.caption('Supported: TXT, text-based PDF, CSV, XLSX. One invoice per document. No scanned PDF OCR.')

st.markdown('<div class="eyebrow">NATURAL LANGUAGE → EXECUTABLE WORKFLOW</div>', unsafe_allow_html=True)
st.title('Make your instructions work.')
st.write('Turn a document or spreadsheet task into a validated workflow, then follow every step to the final report.')

build, workflow_tab, results_tab, experiments = st.tabs(['01  Describe', '02  Workflow', '03  Results', '04  Experiments'])

with build:
    left, right = st.columns([1.65, 1], gap='large')
    with left:
        st.subheader('What would you like to automate?')
        preset = st.selectbox('Start with an example', list(DEMOS))
        instruction = st.text_area('Task instruction', value=DEMOS[preset], key='instruction_' + preset, height=155)
        use_samples = st.toggle('Use synthetic sample invoices', value=True)
        uploads = st.file_uploader('Or upload your files', type=['txt', 'pdf', 'csv', 'xlsx'], accept_multiple_files=True, disabled=use_samples)
        files = sample_files() if use_samples else {f.name: f.getvalue() for f in uploads or []}
        duplicate_uploads = not use_samples and len(files) != len(uploads or [])
        manifest = {}
        file_error = None
        try:
            if duplicate_uploads:
                raise ValueError('Uploaded filenames must be unique.')
            if files:
                manifest = inventory(files)
        except Exception as exc:
            file_error = str(exc)
            st.error(file_error)
        # A changed instruction, file, or compiler setting invalidates the previous result.
        fingerprint = hashlib.sha256(json.dumps({'instruction': instruction, 'files': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
                                                'mode': mode, 'strategy': strategy, 'retries': retries, 'base': base_url, 'model': model,
                                                'structured': structured}, sort_keys=True).encode()).hexdigest()
        if st.session_state.get('fingerprint') != fingerprint:
            for name in ['compilation', 'run', 'workflow_editor', 'validated_editor', 'manual_edits']:
                st.session_state.pop(name, None)
            st.session_state['fingerprint'] = fingerprint
        if st.button('Compile workflow →', type='primary', disabled=not manifest or bool(file_error) or (mode == 'Connected LLM' and not consent)):
            try:
                provider = Provider(base_url, model, key, structured) if mode == 'Connected LLM' else None
                with st.spinner('Compiling and validating your workflow…'):
                    compilation = compile_workflow(instruction, manifest, provider, strategy, retries)
                st.session_state['compilation'] = compilation
                st.session_state.pop('run', None)
                st.session_state.pop('validated_editor', None)
                st.session_state['manual_edits'] = 0
                if compilation.workflow:
                    st.session_state['workflow_editor'] = compilation.workflow.model_dump_json(indent=2)
                    st.success('Workflow compiled. Open “02 Workflow” to inspect and execute it.')
                else:
                    st.error(compilation.error)
            except Exception as exc:
                st.error(str(exc))
    with right:
        st.subheader('Your workspace')
        if manifest:
            st.dataframe([{'File': n, 'Type': m['kind'], 'Rows': m['rows']} for n, m in manifest.items()], hide_index=True, width='stretch')
            with st.expander('Available columns'):
                st.json(manifest)
        else:
            st.info('Add files or enable the sample invoices to begin.')
        st.markdown('**From request to report**\n\n1. Compile a structured plan\n2. Validate inputs and dependencies\n3. Review and execute\n4. Download verified exports')
        if use_samples:
            buffer = BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                for name, data in files.items():
                    archive.writestr(name, data)
            st.download_button('Download sample invoices', buffer.getvalue(), 'sample_invoices.zip')

compilation = st.session_state.get('compilation')
with workflow_tab:
    if not compilation:
        st.info('Compile a task in the Describe tab first.')
    else:
        cols = st.columns(4)
        cols[0].metric('Compile time', f'{compilation.seconds:.2f}s')
        cols[1].metric('Generation attempts', len(compilation.attempts))
        cols[2].metric('Tokens reported', compilation.prompt_tokens + compilation.completion_tokens)
        cols[3].metric('Mode', 'Offline preset' if compilation.mode == 'offline_demo' else 'LLM')
        if compilation.error:
            st.error(compilation.error)
        if compilation.workflow:
            graph_col, editor_col = st.columns([1, 1.35], gap='large')
            with editor_col:
                st.subheader('Editable workflow')
                editor = st.text_area('Workflow JSON', key='workflow_editor', height=460)
                current = None
                try:
                    current = Workflow.model_validate_json(editor)
                    validate_workflow(current, manifest)
                    st.success('Schema and dependency validation passed.')
                except Exception as exc:
                    st.error(str(exc))
                if st.session_state.get('validated_editor') != editor:
                    st.session_state.pop('run', None)
                if st.button('Execute workflow →', type='primary', disabled=current is None or bool(file_error)):
                    try:
                        with st.spinner('Executing supported operations…'):
                            run = execute(current, files)
                        st.session_state['run'] = run
                        st.session_state['validated_editor'] = editor
                        st.session_state['manual_edits'] = int(editor != compilation.workflow.model_dump_json(indent=2))
                        if run.error:
                            st.error(run.error)
                        else:
                            st.success('Execution complete. Open “03 Results” for your report.')
                    except Exception as exc:
                        st.error(str(exc))
                st.download_button('Download workflow JSON', editor, 'workflow.json', mime='application/json')
            with graph_col:
                st.subheader('Execution plan')
                for step in (current or compilation.workflow).steps:
                    source = getattr(step, 'source', 'uploaded files')
                    st.markdown(f'<div class="node"><small>{html.escape(step.id)} · {html.escape(step.operation)}</small><br><b>{html.escape(step.label)}</b><br><small>Input: {html.escape(source)}</small></div>', unsafe_allow_html=True)
        with st.expander('Compilation attempts and validation feedback'):
            if compilation.decomposition:
                st.text(compilation.decomposition)
            st.json(compilation.attempts)

with results_tab:
    run = st.session_state.get('run')
    if not run:
        st.info('Execute a validated workflow to see the trace and downloadable reports.')
    else:
        if run.error:
            st.error(run.error)
        else:
            st.success('All nodes completed. Export structure checked; inspect report contents to confirm task correctness.')
        st.subheader('Execution trace')
        st.dataframe(run.trace, hide_index=True, width='stretch')
        for name, data in run.artifacts.items():
            st.download_button('Download ' + name, data, file_name=name,
                               mime='text/csv' if name.endswith('.csv') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='artifact_' + name)
        for check in run.checks:
            st.caption('✓ ' + check)
        if run.tables:
            selected = st.selectbox('Inspect node output', list(run.tables), index=len(run.tables) - 1)
            st.dataframe(run.tables[selected], hide_index=True, width='stretch')
            if 'extraction_status' in run.tables[selected] and (run.tables[selected]['extraction_status'] != 'ok').any():
                st.warning('Some invoices need review. Missing values have not been silently converted to zero.')
        audit = {'compilation': asdict(compilation) if compilation else None, 'trace': run.trace,
                 'checks': run.checks, 'error': run.error, 'manual_workflow_edit_present': st.session_state.get('manual_edits', 0)}
        if audit['compilation']:
            audit['compilation']['workflow'] = compilation.workflow.model_dump() if compilation.workflow else None
        st.download_button('Download run audit', json.dumps(audit, indent=2, ensure_ascii=False), 'run_audit.json', mime='application/json')

with experiments:
    st.subheader('Measure the compiler, not just the demo')
    st.write('Compare one-shot generation, decomposition, and decomposition with bounded validation feedback on identical tasks.')
    st.dataframe([
        {'Metric': 'Schema validity', 'Meaning': 'Generated envelope conforms to the typed contract'},
        {'Metric': 'Workflow correctness', 'Meaning': 'Expected operations, ordering and parameters match the task'},
        {'Metric': 'Execution success', 'Meaning': 'Every node executes without error'},
        {'Metric': 'Output correctness', 'Meaning': 'Results match manually specified reference tables'},
        {'Metric': 'Corrections', 'Meaning': 'Automatic retries; human edits recorded separately'},
    ], hide_index=True, width='stretch')
    st.code('python -m prompt_compiler.benchmark --offline\npython -m prompt_compiler.benchmark --live', language='powershell')
    st.caption('The starter benchmark is a small development suite, not held-out research evidence. Live mode uses your .env configuration and makes chargeable calls. No benchmark runs automatically from this page.')
