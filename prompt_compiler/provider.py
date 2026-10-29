"""Small Chat Completions adapter; no keys or raw provider responses are logged."""
from dataclasses import dataclass
import json
import urllib.request
import urllib.error
from urllib.parse import urlparse


@dataclass
class Reply:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Provider:
    def __init__(self, base_url, model, api_key='', structured=True):
        parsed = urlparse(base_url)
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
            raise ValueError('Use HTTPS for remote providers or HTTP for localhost only.')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Provider URL must not contain credentials, query parameters, or fragments.')
        if not model.strip():
            raise ValueError('Enter a model identifier supported by your provider.')
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.model, self.key, self.structured = model, api_key, structured

    def complete(self, messages, schema=None):
        body = {'model': self.model, 'messages': messages, 'temperature': 0}
        if schema is not None:
            body['response_format'] = ({'type': 'json_schema', 'json_schema': {'name': 'workflow', 'schema': schema, 'strict': True}}
                                       if self.structured else {'type': 'json_object'})
        headers = {'Content-Type': 'application/json'}
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
            with urllib.request.build_opener(*handlers).open(request, timeout=90) as response:
                payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError('Provider response exceeds 2 MB.')
            result = json.loads(payload)
            message = result['choices'][0]['message']
            if message.get('refusal'):
                raise ValueError('Provider declined this request.')
            if not isinstance(message.get('content'), str):
                raise ValueError('Provider returned no text content.')
            usage = result.get('usage', {})
            return Reply(message['content'], usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))
        except urllib.error.HTTPError as exc:
            raise ValueError(f'Provider HTTP {exc.code}. Check endpoint, key, model, and structured-output support. Provider response omitted to protect credentials.') from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError('Provider connection failed or timed out. Check endpoint and connectivity.') from None


def strict_schema(schema):
    """Make all object properties required for strict structured-output providers."""
    if isinstance(schema, dict):
        schema = {k: strict_schema(v) for k, v in schema.items() if k not in {'discriminator', 'default'}}
        if schema.get('type') == 'object':
            schema['additionalProperties'] = False
            schema['required'] = list(schema.get('properties', {}))
        if 'oneOf' in schema:
            schema['anyOf'] = schema.pop('oneOf')
    elif isinstance(schema, list):
        schema = [strict_schema(v) for v in schema]
    return schema
