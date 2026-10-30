"""Local, bounded checks on model-declared coverage; not a proof of all semantics."""
import re

from .schema import Read, Extract, Select, Aggregate, Flag, FlagRows, Calculate, Export


def action_for(step):
    return {'flag_rows': 'flag', 'filter_rows': 'filter'}.get(step.operation, step.operation)


def output_schemas(workflow, manifest):
    schemas = {}
    for step in workflow.steps:
        if isinstance(step, Read):
            columns = set(manifest[step.files[0]]['columns'])
        else:
            columns = schemas[step.source].copy()
            if isinstance(step, Extract):
                columns = {'source_file', 'vendor', 'total', 'currency', 'extraction_status'}
            elif isinstance(step, Select):
                columns = set(step.columns)
            elif isinstance(step, Aggregate):
                columns = set(step.group_by) | {step.output_column}
            elif isinstance(step, (Flag, FlagRows, Calculate)):
                columns.add(step.output_column)
        schemas[step.id] = columns
    return schemas


def _normalize(text):
    return ' '.join(text.casefold().split())


def validate_task_coverage(workflow, requirements, instruction, manifest):
    if not requirements:
        raise ValueError('Missing task coverage: list the requested actions and link each exact request excerpt to workflow step_ids. Do not return an unchecked copy of the input.')
    nodes = {step.id: step for step in workflow.steps}
    exports = [step for step in workflow.steps if isinstance(step, Export)]
    paths = {}
    for step in workflow.steps:
        paths[step.id] = paths.get(getattr(step, 'source', None), set()) | {step.id}
    schemas = output_schemas(workflow, manifest)
    covered = set()
    for requirement in requirements:
        if not _normalize(requirement.request_excerpt) or _normalize(requirement.request_excerpt) not in _normalize(instruction):
            raise ValueError('Coverage excerpts must quote the original user request. Do not invent or paraphrase requirements.')
        for node_id in requirement.step_ids:
            if node_id not in nodes:
                raise ValueError(f'Coverage references unknown step {node_id}.')
            if action_for(nodes[node_id]) != requirement.action:
                raise ValueError(f'Coverage action {requirement.action} does not match step {node_id}.')
        if requirement.output_columns:
            relevant = [step for step in exports if set(requirement.step_ids) <= paths[step.id]]
            required = set(requirement.output_columns)
            if not any(required <= schemas[step.id] for step in relevant):
                raise ValueError(f'Required output columns {sorted(required)} are absent from an export downstream of their requirement steps.')
        covered.update(requirement.step_ids)
    missing = [step.id for step in workflow.steps if step.operation not in {'read', 'export'} and step.id not in covered]
    if missing:
        raise ValueError(f'Transformations lack links to user requirements: {missing}. Explain their original-request basis or remove them.')
    validate_requested_actions(workflow, instruction)


def validate_requested_actions(workflow, instruction):
    """Conservative action-word guard, independent of field names and domains."""
    text = instruction.casefold()
    # Ignore explicit negative commands instead of requiring the forbidden action.
    text = re.sub(r"\b(?:do not|don't|without|no)\s+(?:add\s+)?(?:flag\w*|filter\w*|sort\w*|calculat\w*|aggregat\w*)\b", '', text)
    patterns = {
        'flag': r'\bflag(?:s|ged|ging)?\b|\b(?:highlight|mark)\s+(?:the\s+)?(?:rows|records|invoices)\b',
        'filter': r'\bfilter(?:ed|ing)?\b|\b(?:keep|retain|show|include|return)\s+only\s+(?:rows|records|entries|items|invoices)\b',
        'calculate': r'\b(?:calculate|compute|derive)\b',
        'aggregate': r'\bgroup\s+by\b|\b(?:sum|average|count)\s+(?:all\s+)?(?:the\s+)?(?:rows|records|invoices)\b',
        'sort': r'\bsort(?:ed|ing)?\b|\border\s+by\b',
        'select': r'\bselect\s+(?:only\s+)?(?:the\s+)?(?:columns|fields)\b',
    }
    actions = {action_for(step) for step in workflow.steps}
    for action, pattern in patterns.items():
        if re.search(pattern, text) and action not in actions:
            raise ValueError(f'The request includes {action}, but the exported workflow omits that action. Implement the original request rather than only reading and exporting.')
    if 'flag' not in actions or not re.search(patterns['flag'], text):
        return
    # Preserve a requested row flag unless the request instead summarizes it.
    if 'aggregate' in actions:
        return
    visible_flags = {}
    for step in workflow.steps:
        flags = visible_flags.get(getattr(step, 'source', None), set()).copy()
        if isinstance(step, (Flag, FlagRows)):
            flags.add(step.output_column)
        elif isinstance(step, Select):
            flags.intersection_update(step.columns)
        visible_flags[step.id] = flags
    if not any(visible_flags[step.id] for step in workflow.steps if isinstance(step, Export)):
        raise ValueError('The instruction requests flagging, but no exported report contains a generated flag column. Export the flag rather than an unchanged input branch.')
