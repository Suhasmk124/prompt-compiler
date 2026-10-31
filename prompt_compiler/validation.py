from .schema import Workflow, Read, Extract, Filter, Flag, FilterRows, FlagRows, Calculate, Aggregate, Select, Sort, Deduplicate, DateDifference

INVOICE_COLUMNS = {'source_file', 'vendor', 'total', 'currency', 'extraction_status'}


def validate_workflow(workflow: Workflow, manifest: dict) -> None:
    columns = {}
    for step in workflow.steps:
        def require(names):
            missing = set(names) - available
            if missing:
                raise ValueError(f'{step.id}: unknown columns {sorted(missing)}; available: {sorted(available)}')

        if isinstance(step, Read):
            missing = set(step.files) - manifest.keys()
            if missing:
                raise ValueError(f'{step.id}: files were not uploaded: {sorted(missing)}')
            if len(set(step.files)) != len(step.files):
                raise ValueError('Read files cannot be repeated.')
            schemas = [set(manifest[n]['columns']) for n in step.files]
            if any(s != schemas[0] for s in schemas):
                raise ValueError('Combine files only when their columns match; use separate branches otherwise.')
            available = schemas[0]
        else:
            available = columns[step.source].copy()
            if isinstance(step, Extract):
                require(['text', 'source_file'])
                available = INVOICE_COLUMNS.copy()
            elif isinstance(step, (Filter, Flag, Sort)):
                require([step.column])
            elif isinstance(step, (FilterRows, FlagRows)):
                require([condition.column for condition in step.conditions])
            elif isinstance(step, Deduplicate):
                require(step.columns)
                if len(set(step.columns)) != len(step.columns):
                    raise ValueError('Deduplication columns must be unique.')
            elif isinstance(step, DateDifference):
                require([step.start_column, step.end_column])
            elif isinstance(step, Calculate):
                require([step.left] + ([step.right] if isinstance(step.right, str) else []))
            elif isinstance(step, Aggregate):
                require(step.group_by + [step.column])
                if step.output_column in step.group_by:
                    raise ValueError('Aggregate output cannot overwrite a grouping column.')
                available = set(step.group_by)
            elif isinstance(step, Select):
                require(step.columns)
                if len(set(step.columns)) != len(step.columns):
                    raise ValueError('Selected columns must be unique.')
                available = set(step.columns)
            if isinstance(step, (Flag, FlagRows, Calculate, Aggregate, DateDifference)):
                if not step.output_column.strip() or step.output_column in available:
                    raise ValueError(f'{step.id}: output_column must be a new, non-empty column.')
                available.add(step.output_column)
        if len(available) > 200:
            raise ValueError('Result exceeds 200 columns; select fewer columns first.')
        columns[step.id] = available
