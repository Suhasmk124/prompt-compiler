"""Small Chat Completions adapter; no keys or raw provider responses are logged."""
from dataclasses import dataclass
import json
import os
import urllib.request
import urllib.error
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Event
from urllib.parse import urlparse


class GenerationRejected(ValueError):
    """Provider rejected generated JSON; eligible for the compiler's bounded repair."""


class RequestCancelled(RuntimeError):
    pass


class RateLimitedError(ValueError):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def retry_after_seconds(value):
    if value is None:
        return None
    try:
        seconds = float(value)
        return max(0.0, seconds) if math.isfinite(seconds) else None
    except (TypeError, ValueError):
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def provider_http_error(exc):
    # Read a bounded body solely to classify known errors. Never surface arbitrary
    # provider messages, failed generations, headers, URLs, or credentials.
    code, param = None, None
    try:
        payload = exc.read(64_001)
        if len(payload) <= 64_000:
            error = json.loads(payload).get('error', {})
            if isinstance(error, dict):
                code, param = error.get('code'), error.get('param')
    except Exception:
        pass
    if exc.code == 400 and code == 'json_validate_failed':
        return GenerationRejected('The model generated output that the provider rejected as invalid JSON or an invalid structured response. Try Plan + self-correction or simplify the instruction.')
    if exc.code == 400 and (param == 'response_format' or code in ('unsupported_response_format', 'invalid_json_schema')):
        return ValueError('The provider rejected the structured-output format or schema. Check model support; if strict schemas are unsupported, set LLM_STRUCTURED=false in the local .env and restart. Local workflow validation remains enabled.')
    if exc.code in (401, 403):
        return ValueError('The provider denied access. Check the server-side API key and account permissions in your local .env.')
    if exc.code == 404 or (exc.code == 400 and code in ('model_not_found', 'model_decommissioned')):
        return ValueError('The provider could not find the endpoint or model. Check LLM_BASE_URL and LLM_MODEL in your local .env.')
    if exc.code == 413:
        return ValueError('The provider rejected the request as too large for its request or token limit. Reduce task size or LLM_MAX_COMPLETION_TOKENS; no partial plan was accepted.')
    if exc.code == 429:
        delay = retry_after_seconds(((exc.headers or {}).get('Retry-After') or (exc.headers or {}).get('retry-after')))
        return RateLimitedError('The provider’s free-tier or rate limit was reached. Your task is preserved; wait before retrying or check your remaining quota.', delay)
    return ValueError(f'Provider HTTP {exc.code}: the request was rejected. No recognized error category was supplied. Check the endpoint, model and structured-output settings in your local .env. Raw response hidden to protect credentials.')


@dataclass
class Reply:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Provider:
    def __init__(self, base_url, model, api_key='', structured=True, max_completion_tokens=None, *,
                 max_rate_retries=0, cancel_event=None, on_progress=None, max_retry_wait=90, timeout_seconds=45):
        parsed = urlparse(base_url)
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
            raise ValueError('Use HTTPS for remote providers or HTTP for localhost only.')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Provider URL must not contain credentials, query parameters, or fragments.')
        if not model.strip():
            raise ValueError('Enter a model identifier supported by your provider.')
        groq_oss = parsed.hostname == 'api.groq.com' and model in {'openai/gpt-oss-20b', 'openai/gpt-oss-120b'}
        self.reasoning_effort = 'low' if groq_oss else None
        try:
            self.max_completion_tokens = int(max_completion_tokens if max_completion_tokens is not None else os.getenv('LLM_MAX_COMPLETION_TOKENS', '2048' if groq_oss else '4096'))
        except (TypeError, ValueError):
            raise ValueError('LLM_MAX_COMPLETION_TOKENS must be an integer between 256 and 32768.') from None
        if not 256 <= self.max_completion_tokens <= 32768:
            raise ValueError('LLM_MAX_COMPLETION_TOKENS must be between 256 and 32768.')
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.model, self.key, self.structured = model, api_key, structured
        if not 0 <= max_rate_retries <= 2 or not 0 <= max_retry_wait <= 120 or not 1 <= timeout_seconds <= 120:
            raise ValueError('Provider retry or timeout limits are invalid.')
        self.max_rate_retries, self.max_retry_wait = max_rate_retries, max_retry_wait
        self.timeout_seconds = timeout_seconds
        self.cancel_event = cancel_event if cancel_event is not None else Event()
        self.on_progress = on_progress
        self.request_count = 0

    def complete(self, messages, schema=None):
        return self._complete(messages, schema, self.structured)

    def complete_json(self, messages, schema=None):
        """Explicit JSON-mode repair request; the compiler counts/budgets it."""
        return self._complete(messages, schema, False)

    def _complete(self, messages, schema, structured):
        for attempt in range(self.max_rate_retries + 1):
            if self.cancel_event.is_set():
                raise RequestCancelled('Generation cancelled. Your task and inputs are preserved.')
            try:
                reply = self._request_once(messages, schema, structured)
            except RateLimitedError as exc:
                delay = exc.retry_after if exc.retry_after is not None else 5.0
                if attempt >= self.max_rate_retries or delay > self.max_retry_wait:
                    raise
                if self.on_progress:
                    self.on_progress({'stage': 'retry_wait', 'message': f'Provider is busy. Retrying in {math.ceil(delay)} seconds…',
                                      'retry_after': delay, 'api_calls': self.request_count})
                if self.cancel_event.wait(delay):
                    raise RequestCancelled('Generation cancelled during provider wait.') from None
                continue
            if self.cancel_event.is_set():
                raise RequestCancelled('Generation cancelled. The returned plan was discarded.')
            return reply

    def _request_once(self, messages, schema, structured):
        body = {'model': self.model, 'messages': messages, 'temperature': 0,
                'max_completion_tokens': self.max_completion_tokens}
        if self.reasoning_effort:
            body['reasoning_effort'] = self.reasoning_effort
        if schema is not None:
            body['response_format'] = ({'type': 'json_schema', 'json_schema': {'name': 'workflow', 'schema': schema, 'strict': True}}
                                       if structured else {'type': 'json_object'})
        headers = {'Content-Type': 'application/json',
                   'User-Agent': 'PromptCompiler/0.1 (+https://github.com/Suhasmk124/prompt-compiler)'}
        if self.key:
            headers['Authorization'] = 'Bearer ' + self.key
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers)
        # Do not follow redirects carrying a credential to another host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            handlers = [NoRedirect]
            if urlparse(self.url).hostname in {'localhost', '127.0.0.1', '::1'}:
                handlers.append(urllib.request.ProxyHandler({}))
            self.request_count += 1
            with urllib.request.build_opener(*handlers).open(request, timeout=self.timeout_seconds) as response:
                payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError('Provider response exceeds 2 MB.')
            result = json.loads(payload)
            choice = result['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise GenerationRejected('The model response reached its output-token limit. Increase LLM_MAX_COMPLETION_TOKENS in the server-side .env or simplify the task; no partial plan was accepted.')
            message = choice['message']
            if message.get('refusal'):
                raise ValueError('Provider declined this request.')
            if not isinstance(message.get('content'), str) or not message['content'].strip():
                raise ValueError('Provider returned no text content.')
            usage = result.get('usage', {})
            return Reply(message['content'], usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))
        except urllib.error.HTTPError as exc:
            raise provider_http_error(exc) from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError('Provider connection failed or timed out. Check endpoint and connectivity.') from None


def strict_schema(schema):
    """Build a simple provider schema; full bounds/patterns remain enforced locally."""
    if isinstance(schema, dict):
        schema = {k: strict_schema(v) for k, v in schema.items()
                  if k not in {'discriminator', 'default', 'pattern', 'minLength', 'maxLength', 'minItems', 'maxItems'} and not (k == 'title' and isinstance(v, str))}
        if 'const' in schema:
            schema['enum'] = [schema.pop('const')]
        if schema.get('type') == 'object':
            schema['additionalProperties'] = False
            schema['required'] = list(schema.get('properties', {}))
        if 'oneOf' in schema:
            schema['anyOf'] = schema.pop('oneOf')
    elif isinstance(schema, list):
        schema = [strict_schema(v) for v in schema]
    return schema
