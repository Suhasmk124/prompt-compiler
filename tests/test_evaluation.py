import json
from pathlib import Path
import pandas as pd
import pytest
from prompt_compiler.evaluate import check_case, compare_output, summarize, BudgetedProvider
from prompt_compiler.executor import execute
from prompt_compiler.schema import Workflow

CORPUS=json.loads((Path(__file__).resolve().parents[1]/'evaluation/corpus_v1.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case',[case for case in CORPUS['cases'] if case['reference_workflow']],ids=lambda case:case['id'])
def test_authored_reference_outputs_and_runtime_guards(case):
    files={name:text.encode() for name,text in case['files'].items()}
    workflow=Workflow.model_validate(case['reference_workflow'])
    run=execute(workflow,files,case['import_options'])
    assert check_case(case,workflow,run)


def test_gold_comparison_preserves_duplicates_and_column_order():
    expected={'columns':['ID','Value'],'rows':[['A',1],['A',1]]}
    assert compare_output(pd.DataFrame([['A',1],['A',1]],columns=['ID','Value']),expected)
    assert not compare_output(pd.DataFrame([['A',1]],columns=['ID','Value']),expected)
    assert not compare_output(pd.DataFrame([[1,'A'],[1,'A']],columns=['Value','ID']),expected)


def test_reference_skips_are_not_reported_as_failed_model_interpretations():
    summary=summarize([{'expected_kind':'clarification','correct':False,'skipped':'No model called'},
                       {'expected_kind':'table','correct':True}])
    assert summary['clarification']['total']==0 and summary['table']=={'correct':1,'total':1}


def test_exhausted_request_budget_prevents_network_access():
    class NeverCall:
        structured=False
        request_count=0
        def complete(self,*args):raise AssertionError('Unexpected provider call')
    provider=BudgetedProvider(NeverCall(),0,0)
    with pytest.raises(RuntimeError,match='budget exhausted'):provider.complete([])
