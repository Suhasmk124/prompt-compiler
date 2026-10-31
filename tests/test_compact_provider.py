"""Provider request fixtures only; no network."""
from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from prompt_compiler.compiler import compile_workflow
from prompt_compiler.provider import Provider, strict_schema
from prompt_compiler.schema import PlanResponse
from prompt_compiler.files import inventory
from prompt_compiler.executor import execute


FILES = {'data.csv': b'code,amount\nA,10\nB,30\n'}
INSTRUCTION = 'Filter rows where amount is above 20 and export CSV'
def compact():
    return {'title': 'Amount filter', 'steps': [
        {'id': 'read', 'label': 'Read', 'operation': 'read', 'files': ['data.csv']},
        {'id': 'filter', 'label': 'Above threshold', 'operation': 'filter', 'source': 'read',
         'column': 'amount', 'comparison': 'gt', 'value': 20, 'case_sensitive': False},
        {'id': 'report', 'label': 'Report', 'operation': 'export', 'source': 'filter', 'filename': 'result.csv'}],
        'clarification': None}


def response(content):
    return BytesIO(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}).encode())


@pytest.mark.parametrize('structured',[True,False])
def test_rejection_uses_a_budgeted_json_repair_without_hidden_calls(monkeypatch,structured):
    requests = []
    class Opener:
        def open(self, request, **kwargs):
            body = json.loads(request.data); requests.append(body)
            if 'response_format' not in body:
                return response('Read, filter, export')
            if body['response_format']['type'] == 'json_schema' or (not structured and len(requests) == 2):
                raise HTTPError('https://example.invalid/v1', 400, 'Rejected', {},
                    BytesIO(b'{"error":{"code":"json_validate_failed"}}'))
            return response(json.dumps(compact()))
    monkeypatch.setattr('urllib.request.build_opener', lambda *args: Opener())
    result = compile_workflow(INSTRUCTION, inventory(FILES), Provider('https://example.invalid/v1', 'model', structured=structured),
                              'feedback', 1, verify_semantics=False)
    assert result.workflow is not None and result.api_calls == 3
    assert len(requests) == 3
    assert requests[1]['response_format']['type'] == ('json_schema' if structured else 'json_object')
    assert requests[2]['response_format'] == {'type': 'json_object'}
    assert 'JSON schema:' in requests[2]['messages'][0]['content']
    assert result.attempts[-1]['json_mode_fallback'] is structured
    assert execute(result.workflow, FILES).tables['report']['code'].tolist() == ['B']


def test_one_shot_rejection_does_not_hide_an_extra_provider_call(monkeypatch):
    requests = []
    class Opener:
        def open(self, request, **kwargs):
            requests.append(request)
            raise HTTPError('https://example.invalid/v1',400,'Rejected',{},BytesIO(b'{"error":{"code":"json_validate_failed"}}'))
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    result=compile_workflow(INSTRUCTION,inventory(FILES),Provider('https://example.invalid/v1','model'),
                            'one_shot',3,verify_semantics=False)
    assert result.workflow is None and result.api_calls == 1 and len(requests)==1


def test_compact_transport_does_not_generate_requirements():
    schema=strict_schema(PlanResponse.model_json_schema())
    assert set(schema['properties'])=={'title','steps','clarification'}
    assert 'TaskRequirement' not in schema['$defs']
    assert 'pattern' not in schema['$defs']['Read']['properties']['id']


@pytest.mark.parametrize('mutation',['id','unknown_column','too_many_conditions'])
def test_local_validation_still_rejects_invalid_plans_despite_simple_transport(monkeypatch,mutation):
    plan=compact()
    if mutation=='id':
        plan['steps'][1]['id']='INVALID ID'
        plan['steps'][-1]['source']='INVALID ID'
    elif mutation=='unknown_column':plan['steps'][1]['column']='invented'
    else:
        plan['steps'][1]={'id':'filter','label':'Filter','operation':'filter_rows','source':'read','match':'all',
                          'conditions':[{'column':'amount','comparison':'gt','value':20}]*13}
    class Opener:
        def open(self,*args,**kwargs):return response(json.dumps(plan))
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    result=compile_workflow(INSTRUCTION,inventory(FILES),Provider('https://example.invalid/v1','model'),
                            'one_shot',0,verify_semantics=False)
    assert result.workflow is None and result.error


def test_groq_budget_and_reasoning_are_provider_specific(monkeypatch):
    requests=[]
    class Opener:
        def open(self,request,**kwargs):
            requests.append(json.loads(request.data));return response('{}')
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    monkeypatch.delenv('LLM_MAX_COMPLETION_TOKENS',raising=False)
    Provider('https://api.groq.com/openai/v1','openai/gpt-oss-20b').complete([])
    Provider('https://example.invalid/v1','other').complete([])
    assert requests[0]['max_completion_tokens']==2048 and requests[0]['reasoning_effort']=='low'
    assert requests[1]['max_completion_tokens']==4096 and 'reasoning_effort' not in requests[1]


def test_compact_clarification_has_no_partial_workflow():
    assert PlanResponse(title=None,steps=[],clarification='Which amount column?').envelope().workflow is None
    with pytest.raises(ValueError):
        PlanResponse(title='Partial',steps=compact()['steps'],clarification='Which amount?')
