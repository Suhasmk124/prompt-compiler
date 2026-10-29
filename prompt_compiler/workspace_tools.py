"""Local-only workspace features; no model or network calls."""
from __future__ import annotations

from io import BytesIO
import json
import zipfile
import pandas as pd
from .schema import Workflow
from .validation import validate_workflow


def import_workflow(content: bytes, manifest: dict) -> Workflow:
    if len(content) > 200_000:
        raise ValueError('Workflow JSON must be under 200 KB.')
    workflow = Workflow.model_validate_json(content.decode('utf-8-sig'))
    validate_workflow(workflow, manifest)
    return workflow


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
