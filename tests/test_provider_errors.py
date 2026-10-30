import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from prompt_compiler.provider import Provider, GenerationRejected, Reply
from prompt_compiler.compiler import compile_workflow
from prompt_compiler.demo import DEMOS, sample_files, demo_workflow
from prompt_compiler.files import inventory


def rejected(code, error):
    return HTTPError('https://example.invalid/v1', code, 'Rejected', {},
                     BytesIO(json.dumps({'error': error}).encode()))


@pytest.mark.parametrize('status,error,expected', [
    (400, {'code': 'json_validate_failed'}, 'generated output'),
    (400, {'param': 'response_format'}, 'LLM_STRUCTURED=false'),
    (400, {'code': 'invalid_json_schema'}, 'structured-output'),
    (401, {}, 'denied access'),
    (404, {}, 'endpoint or model'),
    (429, {}, 'rate limit'),
    (400, {}, 'No recognized error category'),
])
def test_http_errors_are_classified_without_exposing_provider_text(monkeypatch, status, error, expected):
    error['message'] = 'SECRET_KEY and confidential prompt'
    error['failed_generation'] = 'SECRET_KEY'
    class Opener:
        def open(self, *args, **kwargs):
            raise rejected(status, error)
    monkeypatch.setattr('urllib.request.build_opener', lambda *args: Opener())
    with pytest.raises(ValueError) as caught:
        Provider('https://example.invalid/v1', 'test', 'SECRET_KEY').complete([])
    assert expected in str(caught.value)
    assert 'SECRET_KEY' not in str(caught.value)
    assert 'confidential' not in str(caught.value)


@pytest.mark.parametrize('strategy,budget,expected_calls', [
    ('feedback', 2, 3), ('feedback', 0, 1), ('one_shot', 2, 1),
])
def test_provider_rejections_use_existing_retry_budget(strategy, budget, expected_calls):
    class RejectedProvider:
        calls = 0
        def complete(self, messages, schema=None):
            if schema is None:
                return Reply('read, extract, export')
            self.calls += 1
            raise GenerationRejected('Invalid structured response')
    provider = RejectedProvider()
    result = compile_workflow('task', inventory(sample_files()), provider, strategy, budget)
    assert result.workflow is None
    assert result.error == 'Invalid structured response'
    assert provider.calls == expected_calls
    assert len(result.attempts) == expected_calls


def test_rejected_generation_can_be_repaired():
    manifest = inventory(sample_files())
    workflow = demo_workflow(DEMOS['Invoice review'], manifest)
    class RepairProvider:
        calls = 0
        def complete(self, messages, schema=None):
            if schema is None:
                return Reply('read, extract, flag, export')
            self.calls += 1
            if self.calls == 1:
                raise GenerationRejected('Invalid structured response')
            assert 'provider rejected' in messages[-1]['content']
            return Reply(json.dumps({'workflow': workflow.model_dump(), 'clarification': None,
                                     'requirements': [{'request_excerpt': DEMOS['Invoice review'],
                                                       'action': step.operation, 'step_ids': [step.id], 'output_columns': []}
                                                      for step in workflow.steps if step.operation not in {'read', 'export'}]}))
    result = compile_workflow(DEMOS['Invoice review'], manifest, RepairProvider())
    assert result.workflow is not None
    assert len(result.attempts) == 2
    assert result.attempts[0]['provider_rejected']
    assert result.attempts[1]['semantic_valid']
