"""Bind model-selected fields to the current schema without fixed domain aliases."""
import re

from .schema import Workflow


def _key(value):
    return re.sub(r'[\W_]+', '', value.casefold())


def resolve_name(value, candidates):
    if value in candidates:
        return value
    matches = [name for name in candidates if _key(name) == _key(value)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f'Ambiguous field reference {value!r}; use one exact uploaded name: {matches}.')
    return value  # The existing validator reports unknown names; never guess a synonym.


def bind_workflow(workflow, manifest, instruction):
    payload = workflow.model_dump()
    schemas = {}
    explicit_case = bool(re.search(r'\bcase[ -]sensitive\b|\bexact letter case\b', instruction, re.I))
    if re.search(r'\b(?:not|never)\s+case[ -]sensitive\b|\bcase[ -]insensitive\b', instruction, re.I):
        explicit_case = False
    for step in payload['steps']:
        operation = step['operation']
        if operation == 'read':
            step['files'] = [resolve_name(name, manifest) for name in step['files']]
            available = list(manifest.get(step['files'][0], {}).get('columns', []))
        else:
            available = list(schemas.get(step['source'], []))
            for field in ('column', 'left', 'start_column', 'end_column'):
                if field in step:
                    step[field] = resolve_name(step[field], available)
            if isinstance(step.get('right'), str):
                step['right'] = resolve_name(step['right'], available)
            for field in ('group_by', 'columns'):
                if field in step:
                    step[field] = [resolve_name(name, available) for name in step[field]]
            if 'case_sensitive' in step and not explicit_case:
                step['case_sensitive'] = False
            for condition in step.get('conditions', []):
                condition['column'] = resolve_name(condition['column'], available)
                if not explicit_case:
                    condition['case_sensitive'] = False
            if operation == 'extract_invoices':
                available = ['source_file', 'vendor', 'total', 'currency', 'extraction_status']
            elif operation == 'select':
                available = step['columns'].copy()
            elif operation == 'aggregate':
                available = step['group_by'] + [step['output_column']]
            elif operation in {'flag', 'flag_rows', 'calculate', 'date_difference'}:
                available.append(step['output_column'])
        schemas[step['id']] = available
    return Workflow.model_validate(payload)
