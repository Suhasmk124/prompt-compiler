import json
from prompt_compiler.compiler import compile_workflow
from prompt_compiler.files import inventory
from prompt_compiler.provider import Reply

FILES={'scores.csv':b'ID,Score\nA,1\nB,8\n'}
PLAN={'title':'Requested rows','steps':[
    {'id':'read','label':'Read','operation':'read','files':['scores.csv']},
    {'id':'filter','label':'Filter','operation':'filter','source':'read','column':'Score','comparison':'gt','value':3},
    {'id':'report','label':'Report','operation':'export','source':'filter','filename':'report.csv'}],'clarification':None}
DECLINED={'title':None,'steps':[],'clarification':'Filtering cannot be implemented with the available operations.'}
APPROVED={'approved':True,'issues':[],'summary':'The proposed outcome matches the request.'}
REJECTED={'approved':False,'issues':['The requested filtering is supported; compile the predicate rather than refuse.'],'summary':'False capability limitation.'}


class Stub:
    structured=False
    def __init__(self,values):self.values=iter(values);self.calls=[]
    def complete(self,messages,schema=None):
        self.calls.append((messages.copy(),schema))
        return Reply(json.dumps(next(self.values)))


def test_automatic_repairs_false_capability_refusal_without_a_planning_call():
    provider=Stub([DECLINED,REJECTED,PLAN,APPROVED])
    result=compile_workflow('Filter Score above 3 and export CSV',inventory(FILES),provider,'automatic',1)
    assert result.workflow is not None and result.api_calls==4 and len(result.attempts)==2
    assert all(schema is not None for _,schema in provider.calls)
    review=json.loads(provider.calls[1][0][1]['content'])
    assert review['proposed_workflow'] is None
    assert review['proposed_clarification']==DECLINED['clarification']


def test_real_missing_intent_question_is_reviewed_and_not_retried():
    clarification={'title':None,'steps':[],'clarification':'What Score threshold should I use?'}
    provider=Stub([clarification,APPROVED])
    result=compile_workflow('Filter records by Score',inventory(FILES),provider,'automatic',3)
    assert result.workflow is None and result.error_kind=='clarification' and result.api_calls==2


def test_automatic_has_two_calls_when_the_first_plan_is_correct():
    provider=Stub([PLAN,APPROVED])
    result=compile_workflow('Filter Score above 3 and export CSV',inventory(FILES),provider,'automatic',1)
    assert result.workflow is not None and result.api_calls==2 and len(result.attempts)==1


def test_standard_does_not_silently_retry_a_reviewed_false_refusal():
    provider=Stub([DECLINED,REJECTED])
    result=compile_workflow('Filter Score above 3 and export CSV',inventory(FILES),provider,'one_shot',3)
    assert result.workflow is None and result.error_kind=='invalid_plan' and result.api_calls==2
