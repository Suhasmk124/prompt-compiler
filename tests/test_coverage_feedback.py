"""Regression from a synthetic live case; replayed without any network calls."""
import copy
import json
from pathlib import Path
from prompt_compiler.compiler import compile_workflow as _compile_workflow
from functools import partial
# Existing fixtures isolate structural compilation; semantic-review requests
# have their own explicit, local-only fixtures in test_semantic_review.py.
compile_workflow = partial(_compile_workflow, verify_semantics=False)
from prompt_compiler.provider import Reply
from prompt_compiler.files import inventory
from prompt_compiler.executor import execute


def test_feedback_repairs_overdeclared_intermediate_columns():
    fixture=json.loads((Path(__file__).parent/'fixtures/summary_coverage.json').read_text())
    bad=fixture['response'];good=copy.deepcopy(bad)
    for requirement in good['requirements']:
        if requirement['action'] in {'read','calculate'}:
            requirement['output_columns']=[]
    class Stub:
        structured=True
        def __init__(self):
            self.replies=iter(['Calculate, summarize, select, sort, export',json.dumps(bad),json.dumps(good)])
            self.calls=[]
        def complete(self,messages,schema=None):
            self.calls.append(copy.deepcopy(messages))
            return Reply(next(self.replies))
    provider=Stub()
    files={'work.csv':b'ID,Region,Units,Price,Status,Opened,Closed\nA,North,3,10,Ready,2024-02-28,2024-03-01\nB,south,5,8,Hold,2024-03-01,2024-02-28\n'}
    result=compile_workflow(fixture['instruction'],inventory(files),provider,max_retries=1)
    assert result.workflow is not None
    assert result.api_calls==3
    assert len(provider.calls[-1]) == 3
    assert not any(message['role'] == 'assistant' for message in provider.calls[-1])
    feedback=provider.calls[-1][-1]['content']
    assert 'not a new user requirement' in feedback
    assert 'not missing user intent' in feedback
    run=execute(result.workflow,files)
    assert run.error is None
    export=next(s for s in result.workflow.steps if s.operation=='export')
    assert run.tables[export.id].to_dict('records')==[{'Status':'Hold','TotalRevenue':40},{'Status':'Ready','TotalRevenue':30}]


def test_duplicate_group_wording_does_not_require_aggregation():
    from prompt_compiler.task_coverage import validate_requested_actions
    from prompt_compiler.schema import Workflow
    workflow=Workflow.model_validate({'version':'1.0','title':'Unique names','steps':[
        {'id':'read','label':'Read','operation':'read','files':['names.csv']},
        {'id':'unique','label':'Unique','operation':'deduplicate','source':'read','columns':['Name'],'keep':'none'},
        {'id':'report','label':'Report','operation':'export','source':'unique','filename':'report.xlsx'}]})
    validate_requested_actions(workflow,'Remove every duplicated group by Name, ignoring case. Keep only names occurring once.')
    import pytest
    with pytest.raises(ValueError,match='aggregate'):
        validate_requested_actions(workflow,'Remove duplicate groups by Name, then group by Region and sum Value.')


def test_compound_requirement_operation_names_are_accepted_and_checked():
    from prompt_compiler.schema import Workflow, TaskRequirement
    from prompt_compiler.task_coverage import validate_task_coverage
    files={'data.csv':b'Value\n1\n2\n'}
    workflow=Workflow.model_validate({'version':'1.0','title':'Flag','steps':[
        {'id':'read','label':'Read','operation':'read','files':['data.csv']},
        {'id':'flag','label':'Flag','operation':'flag_rows','source':'read','conditions':[{'column':'Value','comparison':'gt','value':1}], 'match':'all','output_column':'Match'},
        {'id':'report','label':'Report','operation':'export','source':'flag','filename':'report.xlsx'}]})
    for action in ['flag','flag_rows']:
        req=TaskRequirement(request_excerpt='Flag matching rows',action=action,step_ids=['flag'],output_columns=['Match'])
        validate_task_coverage(workflow,[req],'Flag matching rows',inventory(files))
    import pytest
    with pytest.raises(ValueError,match='does not match'):
        wrong=TaskRequirement(request_excerpt='Flag matching rows',action='filter_rows',step_ids=['flag'],output_columns=[])
        validate_task_coverage(workflow,[wrong],'Flag matching rows',inventory(files))
