"""Local, bounded checks on model-declared coverage; not a proof of all semantics."""
import re

from .schema import Read, Extract, Select, Aggregate, Flag, FlagRows, Calculate, DateDifference, Export


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
            elif isinstance(step, (Flag, FlagRows, Calculate, DateDifference)):
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
            if action_for(nodes[node_id]) != {'flag_rows': 'flag', 'filter_rows': 'filter'}.get(requirement.action, requirement.action):
                raise ValueError(f'Coverage action {requirement.action} does not match step {node_id}.')
        if requirement.output_columns:
            relevant = [step for step in exports if set(requirement.step_ids) <= paths[step.id]]
            required = set(requirement.output_columns)
            if not any(required <= schemas[step.id] for step in relevant):
                raise ValueError(f'Required output columns {sorted(required)} are absent from an export downstream of their requirement steps. The model declared these as final-output requirements; this is not a new user requirement. Recheck the quoted request: output_columns lists only fields explicitly needed in the final report, not all source or intermediate fields. Use [] for intermediate requirements. Preserve the requested final selection and aggregation; correct the coverage declaration if it overstates the request.')
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
    # Duplicate groups are retention keys, not an instruction to aggregate rows.
    text = re.sub(r'\bduplicat(?:e|ed)\s+groups?\s+by\b', 'duplicate keys', text)
    patterns = {
        'flag': r'\bflag(?:s|ged|ging)?\b|\b(?:highlight|mark)\s+(?:the\s+)?(?:rows|records|invoices)\b',
        'filter': r'\bfilter(?:ed|ing)?\b|\b(?:keep|retain|show|include|return)\s+only\s+(?:rows|records|entries|items|invoices)\b',
        'calculate': r'\b(?:calculate|compute|derive)\b',
        'aggregate': r'\bgroup\s+by\b|\b(?:sum|average|count)\s+(?:all\s+)?(?:the\s+)?(?:rows|records|invoices)\b',
        'sort': r'\bsort(?:ed|ing)?\b|\border\s+by\b',
        'select': r'\bselect\s+(?:only\s+)?(?:the\s+)?(?:columns|fields)\b',
    }
    actions = {action_for(step) for step in workflow.steps}
    if re.search(patterns['filter'], text):
        unique_intent = re.search(r'\b(?:deduplicat\w*|duplicat\w*|unique|distinct)\b|\bone\s+(?:row|record|entry)\s+per\b', text)
        summary_intent = re.search(r'\b(?:aggregat\w*|summari[sz]\w*|sum|average|count|minimum|maximum)\b|\bgroup\s+by\b', text)
        selection_intent = re.search(r'\bselect\b|\b(?:columns?|fields?)\b|\b(?:return|show|export|keep)\s+only\b', text)
        if 'deduplicate' in actions and not unique_intent:
            raise ValueError('Filtering must preserve every matching input row. The request does not ask for unique/distinct entities or deduplication; remove the unrequested deduplicate step.')
        if 'aggregate' in actions and not summary_intent:
            raise ValueError('Filtering does not request aggregation. Preserve matching input records instead of replacing them with one summary per entity.')
        if 'select' in actions and not selection_intent:
            raise ValueError('A plain filter must preserve original columns. Naming an entity does not request selecting only its name; remove the unrequested select step.')
    if 'date_difference' in actions:
        actions.add('calculate')
    for action, pattern in patterns.items():
        if re.search(pattern, text) and action not in actions:
            raise ValueError(f'The request includes {action}, but the exported workflow omits that action. Implement the original request rather than only reading and exporting.')
    if 'flag' not in actions:
        return
    visible_flags, aggregate_paths = {}, {}
    internal_flags = set()
    for step in workflow.steps:
        source = getattr(step, 'source', None)
        flags = visible_flags.get(source, set()).copy()
        aggregated = aggregate_paths.get(source, False)
        if isinstance(step, (Flag, FlagRows)):
            conditions = step.conditions if isinstance(step, FlagRows) else [step]
            internal_flags.update(condition.column for condition in conditions if condition.column in flags)
            flags.add(step.output_column)
        elif isinstance(step, Select):
            flags.intersection_update(step.columns)
        elif isinstance(step, Aggregate):
            flags.intersection_update(step.group_by)
            aggregated = True
        visible_flags[step.id] = flags
        aggregate_paths[step.id] = aggregated
    # Intermediate booleans are implementation details, unless the user actually
    # requests them. Never rely on an LLM approval to decide whether they leaked.
    positive = re.sub(r"\b(?:do not|don't|never)\s+(?:show|include|retain|keep|export|return)\s+(?:all\s+)?(?:intermediate|helper|individual|separate|both|all)\s+(?:flags|columns)\b", '', text)
    wants_helpers = re.search(r'\b(?:show|include|retain|keep|export|return)\s+(?:all\s+)?(?:intermediate|helper|individual|separate|both|all)\s+(?:flags|columns)\b|\b(?:flag|mark)\s+(?:each|every)\s+condition\b', positive)
    if not wants_helpers:
        unnamed = {name for name in internal_flags if not re.search(r'(?<!\w)' + re.escape(name.casefold()) + r'(?!\w)', text)}
        for step in workflow.steps:
            if isinstance(step, Export) and not aggregate_paths[step.id]:
                leaked = visible_flags[step.id] & unnamed
                if leaked:
                    raise ValueError(f'Internal helper flags {sorted(leaked)} leak into the report but were not requested. Add a select step before this export to keep the original columns and requested final flags only. Do not change the conditions or remove matching rows.')
    if 'aggregate' in actions or not re.search(patterns['flag'], text):
        return
    if not any(visible_flags[step.id] for step in workflow.steps if isinstance(step, Export)):
        raise ValueError('The instruction requests flagging, but no exported report contains a generated flag column. Export the flag rather than an unchanged input branch.')
