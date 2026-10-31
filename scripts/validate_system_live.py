"""Explicit live acceptance runner; synthetic data only, never runs on import."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import time
import pandas as pd
from dotenv import load_dotenv


def cases(root):
    table = {'work.csv': b'ID,Region,Units,Price,Status,Opened,Closed\nA,North,3,10,Ready,2024-02-28,2024-03-01\nB,south,5,8,Hold,2024-03-01,2024-02-28\nC,NORTH,1,50,Ready,2024-03-01,\nD,West,2,20,Ready,2024-03-02,2024-03-03\n'}
    return [
        ('dedup_dates', {'table_tools.csv': (root/'examples/table_tools.csv').read_bytes()},
         'Remove duplicates by Record ID keeping the last occurrence. Calculate calendar days from Opened to Closed as Duration; both use YYYY-MM-DD. Preserve original columns, sort Record ID ascending, export report.xlsx.',
         {'Record ID':['A','B','C'],'Opened':['2024-02-28','2024-03-01','2024-03-01'],'Closed':['2024-03-01','2024-02-28',None],'Notes':['revised','negative interval','missing close date'],'Duration':[2,-2,None]}),
        ('compound_flag',table,'Flag rows where (Region is north OR Units is at least 5) AND Status is ready. Call the flag Review, preserve all original columns, and export report.csv.',
         {'ID':['A','B','C','D'],'Review':[True,False,True,False]}),
        ('calculation_summary',table,'Calculate Revenue as Units times Price, group by Status and sum Revenue as TotalRevenue, select only Status and TotalRevenue, sort TotalRevenue descending, export report.xlsx.',
         {'Status':['Ready','Hold'],'TotalRevenue':[120,40]}),
        ('missing_filter',table,'Keep only rows where Closed is missing, select only ID and Closed, export report.csv.',{'ID':['C'],'Closed':[None]}),
        ('duplicate_none',{'names.csv':b'Name,Value\nAda,1\nADA,2\nBo,3\nCy,4\n'},'Remove every duplicated group by Name, ignoring case. Keep only names occurring once, preserve the original columns, export report.xlsx.',{'Name':['Bo','Cy'],'Value':[3,4]}),
        ('unsupported_join',{'a.csv':b'ID,Name\n1,A\n','b.csv':b'ID,Score\n1,8\n'},'Join a.csv and b.csv on ID and export Name and Score to report.xlsx.',None),
        ('ambiguous_column',{'data.csv':b'Gross Amount,Net Amount\n100,80\n'},'Flag rows where amount is above 90 and export XLSX. Ask me which amount column if ambiguous.',None),
        ('pdf_flag',{'invoice.pdf':(root/'examples/pdf/cedar_coast_invoice.pdf').read_bytes()},'Extract the invoice, flag total above INR 70000 as Review, select vendor, total, currency, Review in that order, export report.xlsx.',{'vendor':['Cedar & Coast Office Systems'],'total':[72924],'currency':['INR'],'Review':[True]}),
    ]


def compare(frame, expected, subset=False):
    reference = pd.DataFrame(expected)
    if not subset:
        assert list(frame.columns) == list(reference.columns), f'Columns differ: {list(frame.columns)}'
    actual = frame[list(reference.columns)].reset_index(drop=True).astype(object)
    reference = reference.astype(object)
    pd.testing.assert_frame_equal(actual.where(actual.notna(), None), reference.where(reference.notna(), None), check_dtype=False, check_exact=False, atol=1e-9)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true',required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append')
    parser.add_argument('--json-mode',action='store_true')
    parser.add_argument('--retries',type=int,default=1)
    parser.add_argument('--strategy',choices=['one_shot','decompose','feedback'],default='feedback')
    args=parser.parse_args()
    sys.path.insert(0,str(args.root))
    from prompt_compiler.compiler import compile_workflow
    from prompt_compiler.executor import execute
    from prompt_compiler.files import inventory
    from prompt_compiler.provider import Provider
    load_dotenv(args.root/'.env', override=True)
    provider=Provider(os.environ['LLM_BASE_URL'],os.environ['LLM_MODEL'],os.environ['LLM_API_KEY'],structured=not args.json_mode and os.getenv('LLM_STRUCTURED','true').lower()=='true')
    class PacedProvider:
        structured = provider.structured
        last_call = 0.0
        def complete(self, messages, schema=None):
            delay = max(0, 65 - (time.monotonic() - self.last_call))
            if delay:
                print('Pacing provider requests', flush=True)
                while delay > 0:
                    chunk = min(delay, 30)
                    time.sleep(chunk)
                    delay -= chunk
            self.last_call = time.monotonic()
            return provider.complete(messages, schema)
    paced = PacedProvider()
    # Diagnostic summaries only: do not expose raw provider bodies or generated content.
    import prompt_compiler.provider as adapter
    original_error = adapter.provider_http_error
    def diagnostic_error(exc):
        body = exc.read(64001)
        exc.read = BytesIO(body).read
        try:
            error = json.loads(body).get('error', {})
            generated = error.get('failed_generation')
            diagnostic = {'code':error.get('code'), 'param':error.get('param'), 'retry_after':exc.headers.get('retry-after'), 'remaining_tokens':exc.headers.get('x-ratelimit-remaining-tokens'), 'reset_tokens':exc.headers.get('x-ratelimit-reset-tokens')}
            if isinstance(generated, str):
                try:
                    parsed = json.loads(generated)
                    from prompt_compiler.schema import CompilerResponse
                    try:
                        CompilerResponse.model_validate(parsed)
                        diagnostic['local_envelope_valid'] = True
                    except Exception as invalid:
                        diagnostic['schema_errors'] = [{'path':list(e['loc']), 'message':e['msg']} for e in invalid.errors()]
                except json.JSONDecodeError as invalid:
                    diagnostic['json_error'] = invalid.msg
            print('PROVIDER_DIAGNOSTIC '+json.dumps(diagnostic),flush=True)
        except Exception:
            pass
        return original_error(exc)
    adapter.provider_http_error = diagnostic_error
    args.output.mkdir(parents=True,exist_ok=True)
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'notice':'Synthetic live acceptance cases, not a held-out benchmark. No UI tests.','strategy':args.strategy,'structured':provider.structured,'max_completion_tokens':provider.max_completion_tokens,'model':provider.model,'max_retries':args.retries,'runs':[]}
    selected_cases = cases(args.root)
    unknown = set(args.case or []) - {case[0] for case in selected_cases}
    if unknown:
        parser.error('Unknown cases: ' + ', '.join(sorted(unknown)))
    for name,files,instruction,expected in selected_cases:
        if args.case and name not in args.case: continue
        print('START '+name,flush=True)
        result=compile_workflow(instruction,inventory(files),paced,args.strategy,max_retries=args.retries)
        row={'case':name,'instruction':instruction,'compilation':asdict(result),'output_correct':False,'export_correct':False,'expected_clarification':expected is None}
        if result.workflow:
            row['compilation']['workflow']=result.workflow.model_dump()
            try:
                assert expected is not None,'Unsupported/ambiguous task returned a workflow'
                run=execute(result.workflow,files)
                row['execution_error']=run.error
                assert not run.error,run.error
                exports=[s for s in result.workflow.steps if s.operation=='export']
                assert len(exports)==1,'Expected one report'
                step=exports[0]
                assert step.filename==('report.csv' if name in {'compound_flag','missing_filter'} else 'report.xlsx'), 'Unexpected filename or format'
                compare(run.tables[step.id],expected,subset=name=='compound_flag')
                if name=='compound_flag':
                    assert list(run.tables[step.id].columns)==list(inventory(files)['work.csv']['columns'])+['Review'],'Original columns or helper flags differ'
                row['output_correct']=True
                content=run.artifacts[step.filename]
                restored=pd.read_csv(BytesIO(content)) if step.filename.endswith('.csv') else pd.read_excel(BytesIO(content))
                compare(restored,expected,subset=name=='compound_flag')
                row['export_correct']=True
                case_dir=args.output/name;case_dir.mkdir(exist_ok=True)
                (case_dir/step.filename).write_bytes(content)
                row['trace']=run.trace
            except Exception as exc:
                row['check_error']=str(exc)
        elif expected is None and result.error and result.error.startswith('Clarification needed:'):
            row['output_correct']=True
            row['export_correct']=True
        report['runs'].append(row)
        (args.output/'report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
        print(json.dumps({'case':name,'passed':row['output_correct'] and row['export_correct'],'api_calls':result.api_calls,'error':row.get('check_error') or result.error}),flush=True)
        if result.error and ('rate limit' in result.error or 'denied access' in result.error):
            print('STOP provider limit/access issue',flush=True);break
        time.sleep(2)
    print('REPORT '+str(args.output/'report.json'),flush=True)
    return 0 if report['runs'] and all(r['output_correct'] and r['export_correct'] for r in report['runs']) else 1

if __name__=='__main__':raise SystemExit(main())
