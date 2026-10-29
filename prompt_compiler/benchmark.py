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
    if case == 'Invoice review':
        return (list(table['vendor']) == ['Acme Supplies', 'Acme Supplies', 'Delta Labs', 'Delta Labs']
                and list(table['total']) == [50000, 50001, 12500, 75000]
                and list(table['needs_review']) == [False, True, False, True])
    if case == 'High-value invoices':
        return sorted(table['total'].tolist()) == [50001, 75000] and len(table) == 2
    return table.set_index('vendor')['vendor_total'].to_dict() == {'Acme Supplies': 100001, 'Delta Labs': 87500}


def check_plan(case, workflow):
    steps = workflow.steps
    expected = {'Invoice review': 'flag', 'High-value invoices': 'filter', 'Vendor summary': 'aggregate'}[case]
    ops = [s.operation for s in steps]
    if not all(op in ops for op in ['read', 'extract_invoices', expected, 'export']):
        return False
    if expected in {'flag', 'filter'}:
        transforms = [s for s in steps if s.operation == expected]
        return any(s.column == 'total' and s.comparison == 'gt' and s.value == 50000 for s in transforms)
    return any(s.operation == 'aggregate' and s.group_by == ['vendor'] and s.column == 'total' and s.function == 'sum' for s in steps)


def run_suite(provider=None):
    files = sample_files()
    manifest = inventory(files)
    rows = []
    strategies = ['one_shot', 'decompose', 'feedback'] if provider else ['offline_preset']
    for strategy in strategies:
        for case, instruction in DEMOS.items():
            start = time.perf_counter()
            result = compile_workflow(instruction, manifest, provider, strategy if provider else 'one_shot')
            row = {'case': case, 'split': 'development', 'strategy': strategy, 'mode': result.mode,
                   'first_attempt_schema_valid': bool(result.attempts and result.attempts[0]['schema_valid']),
                   'final_workflow_valid': result.workflow is not None, 'workflow_correct': False,
                   'execution_success': False, 'output_correct': False,
                   'automatic_retries': max(0, len(result.attempts) - 1), 'manual_corrections': None,
                   'prompt_tokens': result.prompt_tokens, 'completion_tokens': result.completion_tokens,
                   'compile_seconds': result.seconds, 'error': result.error, 'attempts': result.attempts}
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
    args = parser.parse_args()
    load_dotenv()
    provider = Provider(os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1'), os.getenv('LLM_MODEL', ''),
                        os.getenv('LLM_API_KEY', ''), structured=not args.json_mode) if args.live else None
    rows = run_suite(provider)
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
