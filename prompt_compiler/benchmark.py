"""Small development benchmark. Live runs are explicit and may incur API costs."""
import argparse
import json
import os
from pathlib import Path
import platform
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from .compiler import compile_workflow
from .demo import DEMOS, sample_files
from .files import inventory
from .executor import execute
from .provider import Provider


def check_output(case, workflow, run):
    if run.error:
        return False
    table = run.tables[workflow.steps[-1].id]
    try:
        if case == 'Invoice review':
            flags = [s.output_column for s in workflow.steps if s.operation in {'flag', 'flag_rows'}]
            return any(sorted(table[['vendor', 'total', name]].itertuples(index=False, name=None)) == [
                ('Acme Supplies', 50000, False), ('Acme Supplies', 50001, True),
                ('Delta Labs', 12500, False), ('Delta Labs', 75000, True)] for name in flags if name in table)
        if case == 'High-value invoices':
            return sorted(table[['vendor', 'total']].itertuples(index=False, name=None)) == [
                ('Acme Supplies', 50001), ('Delta Labs', 75000)]
        outputs = [s.output_column for s in workflow.steps if s.operation == 'aggregate']
        return any(len(table) == 2 and table.set_index('vendor')[name].to_dict() == {
            'Acme Supplies': 100001, 'Delta Labs': 87500} for name in outputs if name in table)
    except (KeyError, TypeError, ValueError):
        return False


def check_plan(case, workflow):
    steps = workflow.steps
    expected = {'Invoice review': 'flag', 'High-value invoices': 'filter', 'Vendor summary': 'aggregate'}[case]
    ops = [{'flag_rows': 'flag', 'filter_rows': 'filter'}.get(s.operation, s.operation) for s in steps]
    if not all(op in ops for op in ['read', 'extract_invoices', expected, 'export']):
        return False
    suffix = '.csv' if case == 'High-value invoices' else '.xlsx'
    if not any(s.operation == 'export' and s.filename.endswith(suffix) for s in steps):
        return False
    if expected in {'flag', 'filter'}:
        transforms = [s for s in steps if {'flag_rows':'flag','filter_rows':'filter'}.get(s.operation,s.operation) == expected]
        return any(any(c.column == 'total' and c.comparison == 'gt' and c.value == 50000
                       for c in (s.conditions if hasattr(s, 'conditions') else [s])) for s in transforms)
    return any(s.operation == 'aggregate' and 'vendor' in s.group_by and set(s.group_by) <= {'vendor', 'currency'}
               and s.column == 'total' and s.function == 'sum' for s in steps)


def run_suite(provider=None, strategy=None, pause_seconds=0, progress=None):
    files = sample_files()
    manifest = inventory(files)
    rows = []
    if strategy not in {None, 'one_shot', 'decompose', 'feedback'}:
        raise ValueError('Unknown benchmark strategy.')
    if not 0 <= pause_seconds <= 60:
        raise ValueError('Pause must be between 0 and 60 seconds.')
    strategies = ([strategy] if strategy else ['one_shot', 'decompose', 'feedback']) if provider else ['offline_preset']
    for strategy in strategies:
        for case, instruction in DEMOS.items():
            if rows and provider and pause_seconds:
                time.sleep(pause_seconds)
            if progress:
                progress(f'Running {strategy}: {case}')
            start = time.perf_counter()
            result = compile_workflow(instruction, manifest, provider, strategy if provider else 'one_shot')
            row = {'case': case, 'split': 'development', 'strategy': strategy, 'mode': result.mode,
                   'first_attempt_schema_valid': bool(result.attempts and result.attempts[0]['schema_valid']),
                   'final_workflow_valid': result.workflow is not None, 'workflow_correct': False,
                   'execution_success': False, 'output_correct': False,
                   'automatic_retries': max(0, len(result.attempts) - 1), 'manual_corrections': None,
                   'prompt_tokens': result.prompt_tokens, 'completion_tokens': result.completion_tokens,
                   'compile_seconds': result.seconds, 'api_calls': result.api_calls, 'error_kind': result.error_kind, 'error': result.error, 'attempts': result.attempts}
            if result.workflow:
                row['workflow'] = result.workflow.model_dump()
                row['workflow_correct'] = check_plan(case, result.workflow)
                try:
                    run = execute(result.workflow, files)
                    row['execution_success'] = run.error is None
                    row['output_correct'] = check_output(case, result.workflow, run)
                    row['error'] = run.error
                    row['trace'] = run.trace
                except Exception as exc:
                    row['error'] = str(exc)
            row['total_seconds'] = round(time.perf_counter() - start, 4)
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--offline', action='store_true')
    mode.add_argument('--live', action='store_true')
    parser.add_argument('--output', default='outputs/benchmark.json')
    parser.add_argument('--json-mode', action='store_true', help='Use JSON mode instead of strict schema with compatible providers.')
    parser.add_argument('--strategy', choices=['one_shot', 'decompose', 'feedback'], help='Run one strategy; omitted runs all three.')
    parser.add_argument('--pause-seconds', type=float, default=0, help='Pause between live tasks to respect free-tier quotas (0–60).')
    args = parser.parse_args()
    load_dotenv()
    provider = Provider(os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1'), os.getenv('LLM_MODEL', ''),
                        os.getenv('LLM_API_KEY', ''), structured=not args.json_mode and os.getenv('LLM_STRUCTURED', 'false').lower() != 'false') if args.live else None
    rows = run_suite(provider, args.strategy, args.pause_seconds, progress=lambda message: print(message, flush=True))
    summary = {metric: sum(bool(r[metric]) for r in rows) / len(rows) for metric in
               ['first_attempt_schema_valid', 'final_workflow_valid', 'workflow_correct', 'execution_success', 'output_correct']}
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'model': provider.model if provider else None, 'dataset': 'synthetic_invoice_development_v1',
              'notice': 'Development fixtures only; offline results are deterministic preset checks, not LLM performance.',
              'summary': summary, 'runs': rows}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print(f'Report saved to {destination}')
    return 0 if all(r['output_correct'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
