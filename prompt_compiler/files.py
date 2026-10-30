from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile
import pandas as pd
from pypdf import PdfReader

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_TEXT = 250_000
ALLOWED = {'.txt', '.pdf', '.csv', '.xlsx'}


def validate_uploads(files: dict[str, bytes]):
    if not files or len(files) > 20:
        raise ValueError('Provide between 1 and 20 files.')
    if sum(len(b) for b in files.values()) > 30 * 1024 * 1024:
        raise ValueError('Combined uploads exceed 30 MB.')
    for name, content in files.items():
        if '/' in name or '\\' in name or Path(name).suffix.lower() not in ALLOWED:
            raise ValueError(f'Unsupported filename: {name}')
        if len(content) > MAX_FILE_BYTES:
            raise ValueError(f'{name}: exceeds 10 MB.')


def read_file(name: str, content: bytes) -> pd.DataFrame:
    suffix = Path(name).suffix.lower()
    if suffix in {'.txt', '.pdf'}:
        if suffix == '.pdf':
            reader = PdfReader(BytesIO(content))
            if len(reader.pages) > 100:
                raise ValueError('PDF exceeds 100 pages.')
            text = '\n'.join(p.extract_text() or '' for p in reader.pages)
        else:
            text = content.decode('utf-8-sig')
        if not text.strip():
            raise ValueError(f'{name}: no readable text; scanned PDF OCR is not supported.')
        if len(text) > MAX_TEXT:
            raise ValueError(f'{name}: extracted text exceeds 250,000 characters.')
        return pd.DataFrame([{'source_file': name, 'text': text}])
    if suffix == '.xlsx':
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError('Expanded workbook exceeds 50 MB.')
        frame = pd.read_excel(BytesIO(content), nrows=MAX_ROWS + 1)
    elif suffix == '.csv':
        frame = pd.read_csv(BytesIO(content), nrows=MAX_ROWS + 1)
    else:
        raise ValueError(f'Unsupported input: {name}')
    if len(frame) > MAX_ROWS or len(frame.columns) > 200:
        raise ValueError('Table exceeds 100,000 rows or 200 columns.')
    frame.columns = [str(c) for c in frame.columns]
    if not frame.columns.is_unique:
        raise ValueError('Column names must be unique.')
    return frame


def inventory(files):
    validate_uploads(files)
    result = {}
    for name, content in files.items():
        frame = read_file(name, content)
        column_types = {}
        for column in frame.columns:
            dtype = frame[column].dtype
            if pd.api.types.is_bool_dtype(dtype):
                kind = 'boolean'
            elif pd.api.types.is_numeric_dtype(dtype):
                kind = 'number'
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                kind = 'datetime'
            else:
                kind = 'text'
            column_types[column] = kind
        result[name] = {'columns': list(frame.columns), 'column_types': column_types, 'rows': len(frame),
                        'kind': 'document' if 'text' in frame and Path(name).suffix.lower() in {'.txt', '.pdf'} else 'table'}
    return result
