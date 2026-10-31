from dataclasses import dataclass, field
import json
import time
from .schema import Workflow, CompilerResponse, PlanResponse
from .provider import strict_schema, GenerationRejected, RequestCancelled, RateLimitedError
from .validation import validate_workflow
from .demo import demo_workflow

from .capabilities import SYSTEM, PLANNING_SYSTEM
from .binding import bind_workflow, resolve_name
from .task_coverage import validate_requested_actions, validate_task_coverage, output_schemas
from .semantic_review import SemanticReview, review_messages


@dataclass
class Compilation:
    workflow: Workflow | None = None
    attempts: list[dict] = field(default_factory=list)
    decomposition: str = ''
    requirements: list[dict] = field(default_factory=list)
    semantic_review: dict = field(default_factory=dict)
    api_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0
    error: str | None = None
    error_kind: str | None = None
    mode: str = ''


def compile_workflow(instruction, manifest, provider=None, strategy='feedback', max_retries=2, verify_semantics=True, on_progress=None, cancel_event=None):
    if strategy not in {'one_shot', 'decompose', 'feedback', 'automatic'}:
        raise ValueError('Unknown compilation strategy.')
    if not instruction.strip() or len(instruction) > 12_000:
        raise ValueError('Instruction must contain between 1 and 12,000 characters.')
    if not 0 <= max_retries <= 3:
        raise ValueError('Retry budget must be between 0 and 3.')
    start = time.perf_counter()
    result = Compilation(mode='llm' if provider else 'offline_demo')
    def invoke(method, messages, schema=None, stage='generation'):
        if cancel_event is not None and cancel_event.is_set():
            raise RequestCancelled('Generation cancelled. Your task is preserved.')
        if on_progress:
            on_progress({'stage': stage, 'message': {'planning': 'Breaking down your request…', 'generation': 'Creating your workflow…', 'review': 'Checking the plan against your request…'}[stage], 'api_calls': result.api_calls})
        before = getattr(provider, 'request_count', None)
        try:
            reply = method(messages, schema) if schema is not None else method(messages)
            if cancel_event is not None and cancel_event.is_set():
                raise RequestCancelled('Generation cancelled. The returned plan was discarded.')
            return reply
        finally:
            after = getattr(provider, 'request_count', None)
            result.api_calls += max(0, after - before) if isinstance(before, int) and isinstance(after, int) else 1
    def review_candidate(workflow, clarification, attempt, json_mode):
        review_schema = strict_schema(SemanticReview.model_json_schema())
        request = review_messages(instruction, manifest, workflow, clarification)
        if json_mode or not getattr(provider, 'structured', False):
            request[0]['content'] += '\nJSON schema:\n' + json.dumps(review_schema, separators=(',', ':'))
        try:
            method = provider.complete_json if json_mode else provider.complete
            reply = invoke(method, request, review_schema, 'review')
        except GenerationRejected:
            raise ValueError('The independent meaning review returned invalid or truncated output. No unreviewed outcome was accepted.') from None
        except Exception as exc:
            result.error_kind = 'cancelled' if isinstance(exc, RequestCancelled) else 'rate_limit' if isinstance(exc, RateLimitedError) else 'provider'
            attempt['errors'] = [str(exc)]
            result.attempts.append(attempt)
            raise RuntimeError(str(exc)) from None
        result.prompt_tokens += reply.prompt_tokens
        result.completion_tokens += reply.completion_tokens
        review = SemanticReview.model_validate_json(reply.text)
        attempt['semantic_review'] = review.model_dump()
        result.semantic_review = review.model_dump()
        if not review.approved:
            raise ValueError('Independent intent review rejected the proposal: ' + '; '.join(review.issues))
        return review
    try:
        if provider is None:
            result.workflow = demo_workflow(instruction, manifest)
            validate_workflow(result.workflow, manifest)
            result.attempts.append({'attempt': 1, 'schema_valid': True, 'semantic_valid': True, 'errors': []})
        else:
            schema = strict_schema(PlanResponse.model_json_schema())
            context = json.dumps({'instruction': instruction, 'uploaded_files': manifest}, ensure_ascii=False, separators=(',', ':'))
            # Strict providers already receive the schema in response_format. Avoid paying
            # for a duplicate copy in the system message on every generation and retry.
            schema_hint = '' if getattr(provider, 'structured', False) else '\nJSON schema:\n' + json.dumps(schema, separators=(',', ':'))
            messages = [{'role': 'system', 'content': SYSTEM + schema_hint},
                        {'role': 'user', 'content': context}]
            if strategy in {'decompose', 'feedback'}:
                reply = invoke(provider.complete, [{'role': 'system', 'content': PLANNING_SYSTEM},
                                           {'role': 'user', 'content': context}], stage='planning')
                result.decomposition = reply.text
                result.prompt_tokens += reply.prompt_tokens
                result.completion_tokens += reply.completion_tokens
                messages.append({'role': 'user', 'content': 'Proposed operation plan (validate against original request):\n' + reply.text})
            budget = max_retries if strategy in {'feedback', 'automatic'} else 0
            use_json_fallback = False
            for index in range(budget + 1):
                try:
                    generate = provider.complete_json if use_json_fallback else provider.complete
                    reply = invoke(generate, messages, schema)
                except GenerationRejected as exc:
                    result.attempts.append({'attempt': index + 1, 'schema_valid': False,
                                            'semantic_valid': False, 'errors': [str(exc)],
                                            'provider_rejected': True, 'json_mode_fallback': use_json_fallback})
                    if index < budget and getattr(provider, 'structured', False) and callable(getattr(provider, 'complete_json', None)):
                        use_json_fallback = True
                        messages = messages[:2]
                        if 'JSON schema:' not in messages[0]['content']:
                            messages[0] = dict(messages[0], content=messages[0]['content'] + '\nJSON schema:\n' + json.dumps(schema, separators=(',', ':')))
                    if index < budget:
                        messages.append({'role': 'user', 'content': 'The provider rejected the previous generation. Return only valid JSON matching the supplied schema, with all required properties. Preserve the original task.'})
                    continue
                result.prompt_tokens += reply.prompt_tokens
                result.completion_tokens += reply.completion_tokens
                attempt = {'attempt': index + 1, 'schema_valid': False, 'semantic_valid': False, 'task_coverage_valid': False, 'errors': [], 'raw': reply.text, 'json_mode_fallback': use_json_fallback}
                try:
                    payload = json.loads(reply.text)
                    compact_response = isinstance(payload, dict) and 'workflow' not in payload
                    envelope = (PlanResponse.model_validate(payload).envelope() if compact_response
                                else CompilerResponse.model_validate(payload))
                    attempt['schema_valid'] = True
                    if envelope.clarification:
                        if verify_semantics:
                            review_candidate(None, envelope.clarification, attempt, use_json_fallback)
                        attempt['errors'] = ['Clarification needed: ' + envelope.clarification]
                        result.attempts.append(attempt)
                        result.error = attempt['errors'][0]
                        result.error_kind = 'clarification'
                        break
                    workflow = bind_workflow(envelope.workflow, manifest, instruction)
                    validate_workflow(workflow, manifest)
                    attempt['semantic_valid'] = True
                    # Resolve final-column case/spelling using current output schemas as
                    # well, without changing quoted user intent or inventing columns.
                    schemas = output_schemas(workflow, manifest)
                    final_columns = set().union(*(schemas[step.id] for step in workflow.steps if step.operation == 'export'))
                    requirements = [requirement.model_copy(update={'output_columns': [resolve_name(name, final_columns) for name in requirement.output_columns]}) for requirement in envelope.requirements]
                    validate_requested_actions(workflow, instruction)
                    try:
                        if not compact_response:
                            validate_task_coverage(workflow, requirements, instruction, manifest)
                        attempt['task_coverage_valid'] = None if compact_response else True
                    except ValueError as coverage_error:
                        if not verify_semantics:
                            raise
                        # Metadata authored by the generator is diagnostic, not an
                        # independent verdict about whether the actual plan is correct.
                        attempt['coverage_warning'] = str(coverage_error)
                    if verify_semantics:
                        review_candidate(workflow, None, attempt, use_json_fallback)
                    result.requirements = [requirement.model_dump() for requirement in requirements]
                    result.workflow = workflow
                except (ValueError, TypeError) as exc:
                    attempt['errors'] = [str(exc)]
                result.attempts.append(attempt)
                if result.workflow:
                    break
                # Regenerate from original intent plus the latest errors. Repeating every
                # rejected JSON/checklist grows requests until provider token limits reject them.
                messages = messages[:2] + [{'role': 'user', 'content': 'Validation failed. Repair the latest proposed plan below using these errors and the original task. A mistaken model declaration is not missing user intent: do not ask the user to resolve your generated metadata errors. Preserve explicitly requested final columns. Return the complete corrected JSON.\nErrors:\n' + '\n'.join(attempt['errors']) + '\nLatest proposal (untrusted; correct its errors):\n' + reply.text}]
            if result.workflow is None:
                result.error = result.attempts[-1]['errors'][0]
    except Exception as exc:
        result.workflow = None
        result.error = str(exc)
        if result.error_kind is None:
            result.error_kind = 'cancelled' if isinstance(exc, RequestCancelled) else 'rate_limit' if isinstance(exc, RateLimitedError) else 'provider'
    if cancel_event is not None and cancel_event.is_set():
        result.workflow = None
        result.error = 'Generation cancelled. Your task and inputs are preserved.'
        result.error_kind = 'cancelled'
    if result.error and result.error_kind is None:
        result.error_kind = 'invalid_plan'
    result.seconds = round(time.perf_counter() - start, 4)
    return result
