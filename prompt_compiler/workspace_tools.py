"""Local-only workspace features; no model or network calls."""
from __future__ import annotations

from io import BytesIO
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import json
import math
import numbers
from uuid import uuid4
import zipfile
import pandas as pd
from .schema import Workflow
from .validation import validate_workflow


def parse_workflow(content: bytes) -> Workflow:
    if len(content) > 200_000:
        raise ValueError('Workflow JSON must be under 200 KB.')
    return Workflow.model_validate_json(content.decode('utf-8-sig'))


def import_workflow(content: bytes, manifest: dict) -> Workflow:
    workflow = parse_workflow(content)
    validate_workflow(workflow, manifest)
    return workflow


def remap_inputs(workflow: Workflow, bindings: dict[str, list[str]], manifest: dict) -> Workflow:
    """Explicitly bind read nodes to current uploads, without mutating the saved plan."""
    payload = workflow.model_dump()
    read_ids = {s.id for s in workflow.steps if s.operation == 'read'}
    if set(bindings) - read_ids:
        raise ValueError('File bindings must name existing read steps.')
    for step in payload['steps']:
        if step['id'] in bindings:
            step['files'] = bindings[step['id']]
    revised = Workflow.model_validate(payload)
    validate_workflow(revised, manifest)
    return revised


def update_parameters(workflow: Workflow, updates: dict[str, dict], manifest: dict) -> Workflow:
    allowed = {'filter': {'comparison', 'value'}, 'flag': {'comparison', 'value'}, 'export': {'filename'}}
    payload = workflow.model_dump()
    nodes = {s['id']: s for s in payload['steps']}
    for node_id, changes in updates.items():
        if node_id not in nodes:
            raise ValueError('Parameter update refers to an unknown step.')
        node = nodes[node_id]
        if set(changes) - allowed.get(node['operation'], set()):
            raise ValueError('Only rule comparisons, rule values and export names can be changed here.')
        if 'value' in changes and isinstance(changes['value'], numbers.Real) and not math.isfinite(changes['value']):
            raise ValueError('Rule values must be finite.')
        node.update(changes)
    revised = Workflow.model_validate(payload)
    validate_workflow(revised, manifest)
    return revised


def _cell(value):
    if pd.isna(value):
        return ('null', '')
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, bool):
        return ('bool', str(value))
    if isinstance(value, numbers.Real):
        return ('number', Decimal(str(value)))
    return (type(value).__name__, str(value))


def compare_tables(before: pd.DataFrame, after: pd.DataFrame) -> dict:
    added_columns = [c for c in after.columns if c not in before.columns]
    removed_columns = [c for c in before.columns if c not in after.columns]
    result = {'before_rows': len(before), 'after_rows': len(after), 'added_columns': added_columns,
              'removed_columns': removed_columns, 'comparable': not (added_columns or removed_columns)}
    if not result['comparable']:
        return result
    after = after.loc[:, before.columns]
    def keys(frame):
        return [tuple(_cell(v) for v in row) for row in frame.itertuples(index=False, name=None)]
    old_keys, new_keys = keys(before), keys(after)
    old_counts, new_counts = Counter(old_keys), Counter(new_keys)
    added, removed = new_counts - old_counts, old_counts - new_counts
    def collect(frame, row_keys, counts):
        indexes = []
        for i, row_key in enumerate(row_keys):
            if counts[row_key] > 0:
                indexes.append(i)
                counts[row_key] -= 1
                if len(indexes) == 100:
                    break
        return frame.iloc[indexes].copy()
    result.update(added_rows=sum(added.values()), removed_rows=sum(removed.values()),
                  unchanged_rows=sum((old_counts & new_counts).values()),
                  added_preview=collect(after, new_keys, added.copy()),
                  removed_preview=collect(before, old_keys, removed.copy()))
    return result


@dataclass
class Snapshot:
    id: str
    title: str
    timestamp: str
    frame: pd.DataFrame
    workflow: dict
    input_fingerprint: str
    size_bytes: int


def retain_snapshot(previous, workflow, run, timestamp, input_fingerprint, budget_bytes=20_000_000):
    if run.error:
        return previous, None
    frame = run.tables[workflow.steps[-1].id]
    size = int(frame.memory_usage(index=True, deep=True).sum())
    if size > min(4_000_000, budget_bytes):
        return previous, None
    snapshot = Snapshot(uuid4().hex, workflow.title, timestamp, frame.copy(deep=True), workflow.model_dump(), input_fingerprint, size)
    kept, used = [snapshot], size
    for old in previous:
        if len(kept) < 5 and used + old.size_bytes <= budget_bytes:
            kept.append(old)
            used += old.size_bytes
    return kept, snapshot


def search_table(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    query = query.strip()
    if not query:
        return frame.copy()
    mask = frame.astype('string').apply(lambda column: column.str.contains(query, case=False, regex=False, na=False)).any(axis=1)
    return frame.loc[mask].copy()


def build_bundle(artifacts: dict[str, bytes], workflow: Workflow, audit: dict) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('workflow.json', workflow.model_dump_json(indent=2))
        archive.writestr('audit.json', json.dumps(audit, indent=2, ensure_ascii=False))
        for name, content in artifacts.items():
            if '/' in name or '\\' in name or name in {'.', '..'}:
                raise ValueError('Report filenames must be basenames.')
            archive.writestr('reports/' + name, content)
    return buffer.getvalue()
