"""Explicitly run the model-backed compiler and local executor on the PDF example."""
from dataclasses import asdict
from io import BytesIO
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
import pandas as pd
from prompt_compiler.compiler import compile_workflow
from prompt_compiler.executor import execute
from prompt_compiler.files import inventory
from prompt_compiler.provider import Provider
from prompt_compiler.workspace_tools import compare_tables, remap_inputs, update_parameters


def main():
    load_dotenv(ROOT / '.env')
    source = ROOT / 'examples/pdf/cedar_coast_invoice.pdf'
    files = {source.name: source.read_bytes()}
    manifest = inventory(files)
    provider = Provider(os.getenv('LLM_BASE_URL', ''), os.getenv('LLM_MODEL', ''), os.getenv('LLM_API_KEY', ''),
                        structured=os.getenv('LLM_STRUCTURED', 'true').lower() != 'false')
    instruction = ('Read the attached PDF invoice. Extract the supplier name, invoice total and currency. '
                   'Keep the invoice in the output and flag it for review if its total is greater than INR 70,000. '
                   'Export an Excel report named cedar_review.xlsx.')
    print('Compiling a new PDF workflow with the configured model...', flush=True)
    compilation = compile_workflow(instruction, manifest, provider, 'feedback', max_retries=2)
    out = ROOT / 'outputs/pdf-live-validation'
    out.mkdir(parents=True, exist_ok=True)
    audit = asdict(compilation)
    audit['workflow'] = compilation.workflow.model_dump() if compilation.workflow else None
    (out / 'compilation.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    if compilation.workflow is None:
        raise RuntimeError(compilation.error)
    workflow = compilation.workflow
    run = execute(workflow, files)
    if run.error:
        raise RuntimeError(run.error)
    frame = run.tables[workflow.steps[-1].id]
    flags = [s for s in workflow.steps if s.operation == 'flag' and s.column == 'total'
             and s.comparison == 'gt' and s.value == 70000]
    assert flags and len(frame) == 1, 'Expected a preserving flag operation and one row.'
    flag = flags[0]
    row = frame.iloc[0]
    assert row['vendor'] == 'Cedar & Coast Office Systems'
    assert float(row['total']) == 72924.0, 'Expected tax-inclusive amount due, not subtotal or tax.'
    assert row['currency'] == 'INR' and bool(row[flag.output_column])
    for name, data in run.artifacts.items():
        (out / name).write_bytes(data)
        restored = pd.read_excel(BytesIO(data)) if name.endswith('.xlsx') else pd.read_csv(BytesIO(data))
        assert restored.iloc[0]['vendor'] == row['vendor'] and restored.iloc[0]['total'] == 72924
        assert bool(restored.iloc[0][flag.output_column])
    revised = update_parameters(workflow, {flag.id: {'value': 75000}}, manifest)
    rerun = execute(revised, files)
    assert rerun.error is None
    after = rerun.tables[revised.steps[-1].id]
    assert not bool(after.iloc[0][flag.output_column])
    diff = compare_tables(frame, after)
    assert diff['added_rows'] == 1 and diff['removed_rows'] == 1
    renamed = {'fresh_supplier_invoice.pdf': source.read_bytes()}
    bindings = {s.id: list(renamed) for s in workflow.steps if s.operation == 'read'}
    rebound = remap_inputs(workflow, bindings, inventory(renamed))
    rebound_run = execute(rebound, renamed)
    assert rebound_run.error is None and rebound_run.tables[rebound.steps[-1].id].iloc[0]['total'] == 72924
    summary = {'model': provider.model, 'source': source.name, 'workflow_valid': True, 'execution_success': True,
               'vendor_correct': True, 'total': 72924.0, 'currency': 'INR', 'flag_above_70000': True,
               'export_cells_verified': True, 'local_rule_change_verified': True, 'comparison_verified': True,
               'renamed_pdf_binding_verified': True, 'automatic_retries': len(compilation.attempts)-1,
               'prompt_tokens': compilation.prompt_tokens, 'completion_tokens': compilation.completion_tokens,
               'trace': run.trace, 'notice': 'One synthetic PDF integration check, not a held-out accuracy study.'}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
