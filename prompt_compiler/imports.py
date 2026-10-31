"""Explicit, reproducible import rules. Raw uploads remain untouched."""
from datetime import date, datetime
import numpy as np
import pandas as pd

TYPE_LABELS = {'auto': 'Auto', 'text': 'Text / identifier', 'number': 'Number', 'boolean': 'Yes / no',
               'date_iso': 'Date · YYYY-MM-DD', 'date_dmy': 'Date · DD/MM/YYYY', 'date_mdy': 'Date · MM/DD/YYYY'}
DATE_FORMATS = {'date_iso': '%Y-%m-%d', 'date_dmy': '%d/%m/%Y', 'date_mdy': '%m/%d/%Y'}


def validate_options(options, columns):
    options = options or {}
    if not isinstance(options, dict) or set(options) - {'column_types', 'missing_values'}:
        raise ValueError('Import settings must contain column_types and/or missing_values only.')
    types = options.get('column_types', {})
    markers = options.get('missing_values', [])
    if not isinstance(types, dict) or set(types) - set(columns) or any(kind not in TYPE_LABELS for kind in types.values()):
        raise ValueError('Import types must name existing columns and supported types.')
    if not isinstance(markers, list) or len(markers) > 20 or any(not isinstance(v, str) or len(v) > 60 for v in markers):
        raise ValueError('Provide at most 20 missing-value text markers, each at most 60 characters.')
    return types, markers


def apply_import_options(frame, raw, options):
    types, markers = validate_options(options, frame.columns)
    result = frame.copy()
    original = raw.copy()
    original.columns = [str(column) for column in original]
    for column in original:
        if markers:
            mask = original[column].map(lambda v: isinstance(v, str) and v in markers)
            original.loc[mask, column] = pd.NA
            result.loc[mask, column] = pd.NA
        kind = types.get(column, 'auto')
        values = original[column]
        if kind == 'auto':
            continue
        if kind == 'text':
            result[column] = values.astype('string')
        elif kind == 'number':
            numeric = pd.to_numeric(values, errors='coerce')
            if (values.notna() & numeric.isna()).any() or np.isinf(numeric.dropna().astype(float)).any():
                raise ValueError(f'{column}: contains values that cannot be imported as numbers.')
            result[column] = numeric
        elif kind == 'boolean':
            def boolean(value):
                if pd.isna(value): return pd.NA
                if isinstance(value, (bool, np.bool_)): return bool(value)
                if isinstance(value, (int, float)) and value in (0, 1): return bool(value)
                text = str(value).strip().casefold()
                if text in {'true', 'yes', '1'}: return True
                if text in {'false', 'no', '0'}: return False
                raise ValueError(f'{column}: yes/no columns accept true/false, yes/no or 1/0.')
            result[column] = values.map(boolean).astype('boolean')
        else:
            fmt = DATE_FORMATS[kind]
            text = values.map(lambda v: v.strftime(fmt) if isinstance(v, (date, datetime)) else v).astype('string')
            dates = pd.to_datetime(text, format=fmt, errors='coerce', exact=True)
            if (values.notna() & dates.isna()).any():
                raise ValueError(f'{column}: contains invalid dates for {TYPE_LABELS[kind]}.')
            result[column] = dates
    return result
