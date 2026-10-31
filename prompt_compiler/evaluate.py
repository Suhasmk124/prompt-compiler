"""Versioned reference checks or explicitly authorized live validation. No calls on import."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import time

import pandas as pd
from dotenv import load_dotenv

from .compiler import compile_workflow
from .executor import execute
from .files import inventory
from .provider import Provider
from .schema import Workflow
from .workspace_tools import compare_tables


ROOT = Path(__file__).resolve().parent.parent
CORE_FILES = ['compiler.py', 'provider.py', 'schema.py', 'capabilities.py', 'semantic_review.py',
              'binding.py', 'task_coverage.py', 'workspace_tools.py', 'validation.py', 'executor.py', 'files.py', 'imports.py', 'evaluate.py']


def code_fingerprint():
    return sha256(b''.join((name + '\n').encode() + (ROOT / 'prompt_compiler' / name).read_bytes() for name in CORE_FILES)).hexdigest()


def compare_output(frame, expected):
    if list(frame.columns) != expected['columns']:
        return False
    reference = pd.DataFrame(expected['rows'], columns=expected['columns'])
    if expected.get('order_sensitive'):
        try:
            pd.testing.assert_frame_equal(frame.reset_index(drop=True).astype(object), reference.astype(object),
                                          check_dtype=False, check_exact=False, atol=1e-9)
            return True
        except AssertionError:
            return False
    comparison = compare_tables(reference, frame)
    return comparison['comparable'] and comparison['added_rows'] == 0 and comparison['removed_rows'] == 0


def check_case(case, workflow, run):
    expected = case['expected']
    if expected['kind'] == 'execution_error':
        return bool(run.error and expected['error_contains'].casefold() in run.error.casefold() and not run.artifacts)
    if run.error:
        return False
    if any(step.operation in expected.get('forbidden_operations', []) for step in workflow.steps):
        return False
    exports = [step for step in workflow.steps if step.operation == 'export']
    requested_formats = {Path(step['filename']).suffix.lower() for step in (case.get('reference_workflow') or {}).get('steps', []) if step['operation'] == 'export'}
    return (len(exports) == 1 and
            (not requested_formats or Path(exports[0].filename).suffix.lower() in requested_formats) and
            compare_output(run.tables[exports[0].id], expected))


def reopen_report(content, filename, frame):
    # Preserve literal NA and textual identifiers according to the expected output types.
    text_columns = {column: str for column in frame if pd.api.types.is_string_dtype(frame[column].dtype)}
    options = dict(keep_default_na=False, na_values=[''], dtype=text_columns)
    return pd.read_csv(BytesIO(content), **options) if filename.endswith('.csv') else pd.read_excel(BytesIO(content), **options)


class BudgetedProvider:
    def __init__(self, provider, limit, pause_seconds):
        self.provider = provider
        self.structured = provider.structured
        self.limit = limit
        self.pause_seconds = pause_seconds
        self.last_call = None
        self.wait_seconds = 0.0
        self.label = ''

    @property
    def request_count(self):
        return self.provider.request_count

    def _call(self, messages, schema, json_mode=False):
        if self.request_count >= self.limit:
            raise RuntimeError('Evaluation request budget exhausted. No additional provider call made.')
        if self.last_call is not None:
            delay = max(0, self.pause_seconds - (time.monotonic() - self.last_call))
            start = time.monotonic()
            while delay > 0:
                time.sleep(min(15, delay))
                delay = max(0, self.pause_seconds - (time.monotonic() - self.last_call))
            self.wait_seconds += time.monotonic() - start
        self.last_call = time.monotonic()
        stage = 'planning' if schema is None else 'review' if 'approved' in schema.get('properties', {}) else 'generation'
        print(f'{self.label}: API request {self.request_count + 1}/{self.limit} · {stage}', flush=True)
        return (self.provider.complete_json if json_mode else self.provider.complete)(messages, schema)

    def complete(self, messages, schema=None):
        return self._call(messages, schema)

    def complete_json(self, messages, schema=None):
        return self._call(messages, schema, True)


def summarize(rows):
    output = {}
    for kind in ['table', 'clarification', 'execution_error']:
        selected = [row for row in rows if row['expected_kind'] == kind and not row.get('skipped')]
        output[kind] = {'correct': sum(bool(row['correct']) for row in selected), 'total': len(selected)}
    output['request_attempts'] = sum(row.get('api_calls', 0) for row in rows)
    output['reported_prompt_tokens'] = sum(row.get('prompt_tokens', 0) for row in rows)
    output['reported_completion_tokens'] = sum(row.get('completion_tokens', 0) for row in rows)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--local', action='store_true', help='Check authored reference plans only; no model accuracy claim')
    mode.add_argument('--live', action='store_true', help='Make real model requests')
    parser.add_argument('--corpus', type=Path, default=ROOT / 'evaluation/corpus_v1.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/evaluation/report.json')
    parser.add_argument('--case', action='append')
    parser.add_argument('--strategy', choices=['all', 'automatic', 'one_shot', 'decompose', 'feedback'], default='all')
    parser.add_argument('--retries', type=int, choices=range(4), default=1)
    parser.add_argument('--repeat', type=int, choices=range(1, 6), default=1)
    parser.add_argument('--max-requests', type=int, default=30)
    parser.add_argument('--pause-seconds', type=float, default=35)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.max_requests <= 200 or not 0 <= args.pause_seconds <= 120:
        parser.error('Use 1–200 requests and 0–120 seconds pacing.')
    raw = args.corpus.read_bytes()
    corpus = json.loads(raw)
    corpus_hash, implementation_hash = sha256(raw).hexdigest(), code_fingerprint()
    cases = corpus['cases']
    unknown = set(args.case or []) - {case['id'] for case in cases}
    if unknown:
        parser.error('Unknown case IDs: ' + ', '.join(sorted(unknown)))
    if args.case:
        cases = [case for case in cases if case['id'] in args.case]
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'corpus_version': corpus['version'],
              'corpus_sha256': corpus_hash, 'implementation_sha256': implementation_hash,
              'mode': 'live_validation' if args.live else 'authored_reference_checks',
              'notice': corpus['notice'], 'settings': {'strategy': args.strategy, 'retries': args.retries,
              'repeat': args.repeat, 'pause_seconds': args.pause_seconds, 'max_requests': args.max_requests}, 'runs': []}
    if args.output.exists():
        if not args.resume:
            parser.error('Report already exists. Choose a new output path or explicitly --resume.')
        report = json.loads(args.output.read_text(encoding='utf-8'))
        if report['corpus_sha256'] != corpus_hash or report['implementation_sha256'] != implementation_hash:
            parser.error('Cannot mix corpus or implementation revisions in one report.')
        if report['mode'] != ('live_validation' if args.live else 'authored_reference_checks'):
            parser.error('Cannot mix reference checks and live evaluation.')
    provider = None
    if args.live:
        load_dotenv(ROOT / '.env')
        actual = Provider(os.getenv('LLM_BASE_URL', ''), os.getenv('LLM_MODEL', ''), os.getenv('LLM_API_KEY', ''),
                          structured=os.getenv('LLM_STRUCTURED', 'false').lower() != 'false')
        provider = BudgetedProvider(actual, args.max_requests, args.pause_seconds)
        if report.get('model') not in {None, actual.model}:
            parser.error('Cannot mix models in one report.')
        report['model'] = actual.model
        report['output_mode'] = 'strict_schema' if actual.structured else 'json_object'
    strategies = (['one_shot', 'decompose', 'feedback'] if args.strategy == 'all' else [args.strategy]) if args.live else ['reference']
    completed = {(r['case'], r['strategy'], r['repeat']) for r in report['runs']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        report['summary'] = summarize(report['runs'])
        temporary = args.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(args.output)
    report['planned_runs'] = len(cases) * len(strategies) * args.repeat
    stop = False
    try:
        for case in cases:
            for strategy in strategies:
                for repeat in range(1, args.repeat + 1):
                    if (case['id'], strategy, repeat) in completed:
                        continue
                    if provider and provider.request_count >= args.max_requests:
                        stop = True; break
                    files = {name: content.encode('utf-8') for name, content in case['files'].items()}
                    manifest = inventory(files, case.get('import_options'))
                    row = {'case': case['id'], 'strategy': strategy, 'repeat': repeat,
                           'expected_kind': case['expected']['kind'], 'correct': False, 'api_calls': 0}
                    workflow = None
                    if provider:
                        provider.label = case['id'] + '/' + strategy
                        pacing_before = provider.wait_seconds
                        compilation = compile_workflow(case['instruction'], manifest, provider, strategy, args.retries)
                        workflow = compilation.workflow
                        row.update(api_calls=compilation.api_calls, prompt_tokens=compilation.prompt_tokens,
                                   completion_tokens=compilation.completion_tokens, error=compilation.error,
                                   error_kind=compilation.error_kind, seconds=compilation.seconds,
                                   pacing_seconds=provider.wait_seconds - pacing_before,
                                   corrections=max(0, len(compilation.attempts) - 1))
                        row['attempts'] = compilation.attempts
                        if case['expected']['kind'] == 'clarification':
                            row['correct'] = not workflow and compilation.error_kind == 'clarification' and all(
                                word.casefold() in (compilation.error or '').casefold() for word in case['expected']['keywords'])
                    elif case['reference_workflow']:
                        workflow = Workflow.model_validate(case['reference_workflow'])
                    else:
                        row['skipped'] = 'Boundary requires a model interpretation; no authored executable reference.'
                    if workflow:
                        run = execute(workflow, files, case.get('import_options'))
                        row['execution_error'] = run.error
                        row['correct'] = check_case(case, workflow, run)
                        folder = args.output.parent / 'artifacts' / f"{case['id']}-{strategy}-{time.time_ns()}"
                        folder.mkdir(parents=True)
                        (folder / 'workflow.json').write_text(workflow.model_dump_json(indent=2), encoding='utf-8')
                        if not run.error and case['expected']['kind'] == 'table':
                            for step in workflow.steps:
                                if step.operation == 'export':
                                    content = run.artifacts[step.filename]
                                    (folder / step.filename).write_bytes(content)
                                    restored = reopen_report(content, step.filename, run.tables[step.id])
                                    row['reopened_correct'] = compare_output(restored, case['expected'])
                                    row['correct'] = row['correct'] and row['reopened_correct']
                        row['artifact_folder'] = str(folder)
                    report['runs'].append(row); save()
                    print(json.dumps({k: v for k, v in row.items() if k in {'case', 'strategy', 'correct', 'error', 'execution_error', 'api_calls'}}), flush=True)
                    if provider and row.get('error_kind') == 'rate_limit':
                        stop = True; break
                if stop: break
            if stop: break
    finally:
        report['complete'] = not stop and len(report['runs']) >= report['planned_runs']
        save()
    measured = [row for row in report['runs'] if not row.get('skipped')]
    print(json.dumps(report['summary'], indent=2), flush=True)
    return 0 if report['complete'] and measured and all(row['correct'] for row in measured) else 1


if __name__ == '__main__':
    raise SystemExit(main())
