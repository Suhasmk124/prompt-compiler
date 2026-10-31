from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile
import re
import pandas as pd
from pypdf import PdfReader
from .imports import apply_import_options

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


def validate_header(raw_header):
    """Validate source headers before pandas can silently rename duplicates/blanks."""
    if raw_header.empty:
        raise ValueError('Table must contain a header row.')
    names = [str(value) for value in raw_header.iloc[0]]
    if any(not name.strip() for name in names):
        raise ValueError('Column names must be non-empty; name every column in the input.')
    if len(names) != len(set(names)):
        raise ValueError('Column names must be unique; rename duplicate headers in the input.')


def preserve_identifier_text(frame, raw):
    """Avoid destructive inference of leading-zero or long numeric identifiers."""
    raw.columns = [str(column) for column in raw.columns]
    for column in frame.columns:
        values = raw[column].dropna()
        sensitive = any(isinstance(value, str) and (
            re.fullmatch(r'[+-]?0\d+', value.strip()) or
            re.fullmatch(r'[+-]?\d{16,}', value.strip())) for value in values)
        if sensitive:
            frame[column] = raw[column].astype('string')
    return frame


def read_file(name: str, content: bytes, options=None) -> pd.DataFrame:
    suffix = Path(name).suffix.lower()
    if suffix in {'.txt', '.pdf'}:
        if options:
            raise ValueError('Column import settings apply to CSV/XLSX files only.')
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
        raw_header = pd.read_excel(BytesIO(content), header=None, nrows=1, dtype=str, keep_default_na=False)
        validate_header(raw_header)
        frame = pd.read_excel(BytesIO(content), nrows=MAX_ROWS + 1, keep_default_na=False, na_values=[''])
        raw = pd.read_excel(BytesIO(content), nrows=MAX_ROWS + 1, dtype=object, keep_default_na=False, na_values=[''])
    elif suffix == '.csv':
        raw_header = pd.read_csv(BytesIO(content), header=None, nrows=1, dtype=str, keep_default_na=False)
        validate_header(raw_header)
        frame = pd.read_csv(BytesIO(content), nrows=MAX_ROWS + 1, keep_default_na=False, na_values=[''])
        raw = pd.read_csv(BytesIO(content), nrows=MAX_ROWS + 1, dtype=str, keep_default_na=False, na_values=[''])
    else:
        raise ValueError(f'Unsupported input: {name}')
    if len(frame) > MAX_ROWS or len(frame.columns) > 200:
        raise ValueError('Table exceeds 100,000 rows or 200 columns.')
    frame.columns = [str(c) for c in frame.columns]
    if not frame.columns.is_unique:
        raise ValueError('Column names must be unique.')
    frame = preserve_identifier_text(frame, raw)
    return apply_import_options(frame, raw, options)


def inventory(files, import_options=None):
    validate_uploads(files)
    import_options = import_options or {}
    if not isinstance(import_options, dict) or set(import_options) - set(files):
        raise ValueError('Import settings reference files that were not uploaded.')
    result = {}
    for name, content in files.items():
        frame = read_file(name, content, import_options.get(name))
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
