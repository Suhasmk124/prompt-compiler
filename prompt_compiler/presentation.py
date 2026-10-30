"""Presentation helpers. Dynamic content is escaped before entering markup."""
from html import escape

PROVIDERS = {
    'Groq': {'base_url': 'https://api.groq.com/openai/v1', 'model': 'openai/gpt-oss-20b'},
    'Custom endpoint': {'base_url': 'http://localhost:11434/v1', 'model': ''},
}

OP_NAMES = {'read': 'Read inputs', 'extract_invoices': 'Extract invoice fields', 'filter': 'Filter records',
            'flag_rows': 'Flag matching records', 'filter_rows': 'Filter matching records',
            'flag': 'Flag records', 'calculate': 'Calculate values', 'aggregate': 'Summarize records',
            'select': 'Choose columns', 'sort': 'Sort records', 'export': 'Create report'}
COMPARISONS = {'gt': 'greater than', 'gte': 'at least', 'lt': 'less than', 'lte': 'at most', 'eq': 'equal to', 'ne': 'not equal to'}
COMPARISONS.update({'contains': 'contains text', 'not_contains': 'does not contain text',
                    'starts_with': 'starts with', 'ends_with': 'ends with',
                    'is_null': 'is missing', 'not_null': 'is not missing'})


def describe_step(step):
    op = step.operation
    if op == 'read':
        return f"Load {len(step.files)} file{'s' if len(step.files) != 1 else ''} into the workflow."
    if op == 'extract_invoices':
        return 'Find vendor names, totals and currencies in labeled invoices.'
    if op in {'filter_rows', 'flag_rows'}:
        joiner = ' AND ' if step.match == 'all' else ' OR '
        return joiner.join(f'{c.column} {COMPARISONS[c.comparison]} {c.value}' for c in step.conditions)
    if op in {'filter', 'flag'}:
        value = f'{step.value:,.2f}'.rstrip('0').rstrip('.') if isinstance(step.value, float) else str(step.value)
        action = 'Mark rows where' if op == 'flag' else 'Keep rows where'
        return f'{action} {step.column} is {COMPARISONS[step.comparison]} {value}.'
    if op == 'calculate':
        symbols = {'add': '+', 'subtract': '−', 'multiply': '×', 'divide': '÷'}
        return f'{step.output_column} = {step.left} {symbols[step.arithmetic]} {step.right}'
    if op == 'aggregate':
        group = ', '.join(step.group_by) if step.group_by else 'all records'
        return f'{step.function.capitalize()} of {step.column}, grouped by {group}.'
    if op == 'select':
        return 'Keep ' + ', '.join(step.columns) + '.'
    if op == 'sort':
        return f"Order by {step.column}, {'highest first' if step.descending else 'lowest first'}."
    return f'Export the result as {step.filename}.'


def plan_markup(workflow, trace=()):
    statuses = {row['node']: row['status'] for row in trace}
    cards = []
    for index, step in enumerate(workflow.steps, 1):
        status = statuses.get(step.id, 'ready')
        badge = {'success': 'Complete', 'failed': 'Needs attention', 'ready': 'Ready'}[status]
        cards.append(f'''<div class="flow-node {status}" style="--step-index:{index}">
          <div class="node-index">{index:02d}</div>
          <div class="node-copy"><div class="node-heading">{escape(OP_NAMES[step.operation])}<span class="node-state {status}" title="{badge}" aria-label="{badge}"></span></div>
          </div></div>''')
    return '<div class="flow-list">' + ''.join(cards) + '</div>'


def file_markup(name, metadata):
    extension = name.rsplit('.', 1)[-1].upper()
    detail = 'Text document' if metadata['kind'] == 'document' else f"{metadata['rows']:,} rows · {len(metadata['columns'])} columns"
    return f'<div class="file-row"><span class="file-type">{escape(extension)}</span><div><strong>{escape(name)}</strong><small>{escape(detail)}</small></div><span class="file-check">✓</span></div>'


def progress_markup(compiled=False, finished=False):
    labels = ['Describe your task', 'Review the plan', 'Get your report']
    active = 2 if finished else 1 if compiled else 0
    return '<div class="journey">' + ''.join(
        f'<div class="journey-step {"done" if i < active else "active" if i == active else ""}"><span>{"✓" if i < active else f"0{i+1}"}</span>{label}</div>'
        for i, label in enumerate(labels)) + '</div>'
