from dataclasses import dataclass, field
import json
import time
from .schema import Workflow, CompilerResponse
from .provider import strict_schema, GenerationRejected
from .validation import validate_workflow
from .demo import demo_workflow

from .capabilities import SYSTEM, PLANNING_SYSTEM
from .binding import bind_workflow, resolve_name
from .task_coverage import validate_requested_actions, validate_task_coverage, output_schemas


@dataclass
class Compilation:
    workflow: Workflow | None = None
    attempts: list[dict] = field(default_factory=list)
    decomposition: str = ''
    requirements: list[dict] = field(default_factory=list)
    api_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0
    error: str | None = None
    mode: str = ''


def compile_workflow(instruction, manifest, provider=None, strategy='feedback', max_retries=2):
    if strategy not in {'one_shot', 'decompose', 'feedback'}:
        raise ValueError('Unknown compilation strategy.')
    if not instruction.strip() or len(instruction) > 12_000:
        raise ValueError('Instruction must contain between 1 and 12,000 characters.')
    if not 0 <= max_retries <= 3:
        raise ValueError('Retry budget must be between 0 and 3.')
    start = time.perf_counter()
    result = Compilation(mode='llm' if provider else 'offline_demo')
    try:
        if provider is None:
            result.workflow = demo_workflow(instruction, manifest)
            validate_workflow(result.workflow, manifest)
            result.attempts.append({'attempt': 1, 'schema_valid': True, 'semantic_valid': True, 'errors': []})
        else:
            schema = strict_schema(CompilerResponse.model_json_schema())
            context = json.dumps({'instruction': instruction, 'uploaded_files': manifest}, ensure_ascii=False, separators=(',', ':'))
            # Strict providers already receive the schema in response_format. Avoid paying
            # for a duplicate copy in the system message on every generation and retry.
            schema_hint = '' if getattr(provider, 'structured', False) else '\nJSON schema:\n' + json.dumps(schema, separators=(',', ':'))
            messages = [{'role': 'system', 'content': SYSTEM + schema_hint},
                        {'role': 'user', 'content': context}]
            if strategy != 'one_shot':
                result.api_calls += 1
                reply = provider.complete([{'role': 'system', 'content': PLANNING_SYSTEM},
                                           {'role': 'user', 'content': context}])
                result.decomposition = reply.text
                result.prompt_tokens += reply.prompt_tokens
                result.completion_tokens += reply.completion_tokens
                messages.append({'role': 'user', 'content': 'Proposed operation plan (validate against original request):\n' + reply.text})
            budget = max_retries if strategy == 'feedback' else 0
            for index in range(budget + 1):
                try:
                    result.api_calls += 1
                    reply = provider.complete(messages, schema)
                except GenerationRejected as exc:
                    result.attempts.append({'attempt': index + 1, 'schema_valid': False,
                                            'semantic_valid': False, 'errors': [str(exc)],
                                            'provider_rejected': True})
                    if index < budget:
                        messages.append({'role': 'user', 'content': 'The provider rejected the previous generation. Return only valid JSON matching the supplied schema, with all required properties. Preserve the original task.'})
                    continue
                result.prompt_tokens += reply.prompt_tokens
                result.completion_tokens += reply.completion_tokens
                attempt = {'attempt': index + 1, 'schema_valid': False, 'semantic_valid': False, 'task_coverage_valid': False, 'errors': [], 'raw': reply.text}
                try:
                    payload = json.loads(reply.text)
                    envelope = CompilerResponse.model_validate(payload)
                    attempt['schema_valid'] = True
                    if envelope.clarification:
                        attempt['errors'] = ['Clarification needed: ' + envelope.clarification]
                        result.attempts.append(attempt)
                        result.error = attempt['errors'][0]
                        break
                    workflow = bind_workflow(envelope.workflow, manifest, instruction)
                    validate_workflow(workflow, manifest)
                    attempt['semantic_valid'] = True
                    # Resolve final-column case/spelling using current output schemas as
                    # well, without changing quoted user intent or inventing columns.
                    schemas = output_schemas(workflow, manifest)
                    final_columns = set().union(*(schemas[step.id] for step in workflow.steps if step.operation == 'export'))
                    requirements = [requirement.model_copy(update={'output_columns': [resolve_name(name, final_columns) for name in requirement.output_columns]}) for requirement in envelope.requirements]
                    validate_task_coverage(workflow, requirements, instruction, manifest)
                    result.requirements = [requirement.model_dump() for requirement in requirements]
                    attempt['task_coverage_valid'] = True
                    result.workflow = workflow
                except (ValueError, TypeError) as exc:
                    attempt['errors'] = [str(exc)]
                result.attempts.append(attempt)
                if result.workflow:
                    break
                messages.extend([{'role': 'assistant', 'content': reply.text},
                                 {'role': 'user', 'content': 'Validation failed. Correct the entire workflow without changing the task:\n' + '\n'.join(attempt['errors'])}])
            if result.workflow is None:
                result.error = result.attempts[-1]['errors'][0]
    except Exception as exc:
        result.workflow = None
        result.error = str(exc)
    result.seconds = round(time.perf_counter() - start, 4)
    return result
