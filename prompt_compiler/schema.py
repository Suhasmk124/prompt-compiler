from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Node(StrictModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=120)


class Read(Node):
    operation: Literal['read']
    files: list[str] = Field(min_length=1, max_length=20)


class Transform(Node):
    source: str


class Extract(Transform):
    operation: Literal['extract_invoices']


class Condition(StrictModel):
    column: str
    comparison: Literal['gt', 'gte', 'lt', 'lte', 'eq', 'ne', 'contains', 'not_contains', 'starts_with', 'ends_with', 'is_null', 'not_null']
    value: Union[float, str, bool, None]
    case_sensitive: bool = False

    @model_validator(mode='after')
    def comparison_value(self):
        if self.comparison in {'is_null', 'not_null'}:
            if self.value is not None:
                raise ValueError('Missing-value checks require value=null.')
        elif self.value is None:
            raise ValueError('This comparison requires a value; use is_null/not_null to check missing cells.')
        elif self.comparison in {'contains', 'not_contains', 'starts_with', 'ends_with'} and not isinstance(self.value, str):
            raise ValueError('Text comparisons require a string value.')
        return self


class Predicate(Transform, Condition):
    pass


class Filter(Predicate):
    operation: Literal['filter']


class Flag(Predicate):
    operation: Literal['flag']
    output_column: str


class CompoundPredicate(Transform):
    conditions: list[Condition] = Field(min_length=1, max_length=12)
    match: Literal['all', 'any']


class FilterRows(CompoundPredicate):
    operation: Literal['filter_rows']


class FlagRows(CompoundPredicate):
    operation: Literal['flag_rows']
    output_column: str


class Calculate(Transform):
    operation: Literal['calculate']
    left: str
    right: Union[float, str]
    arithmetic: Literal['add', 'subtract', 'multiply', 'divide']
    output_column: str


class Aggregate(Transform):
    operation: Literal['aggregate']
    group_by: list[str]
    column: str
    function: Literal['sum', 'mean', 'count', 'min', 'max']
    output_column: str


class Deduplicate(Transform):
    operation: Literal['deduplicate']
    columns: list[str] = Field(max_length=200)
    keep: Literal['first', 'last', 'none']
    case_sensitive: bool = False


class DateDifference(Transform):
    operation: Literal['date_difference']
    start_column: str
    end_column: str
    start_format: Literal['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    end_format: Literal['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    output_column: str


class Select(Transform):
    operation: Literal['select']
    columns: list[str] = Field(min_length=1)


class Sort(Transform):
    operation: Literal['sort']
    column: str
    descending: bool


class Export(Transform):
    operation: Literal['export']
    filename: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,60}\.(xlsx|csv)$')


Step = Annotated[Union[Read, Extract, Filter, Flag, FilterRows, FlagRows, Calculate, Aggregate, Deduplicate, DateDifference, Select, Sort, Export], Field(discriminator='operation')]


class Workflow(StrictModel):
    version: Literal['1.0']
    title: str = Field(min_length=1, max_length=120)
    steps: list[Step] = Field(min_length=2, max_length=30)

    @model_validator(mode='after')
    def graph(self):
        seen = {}
        for step in self.steps:
            if step.id in seen:
                raise ValueError(f'Duplicate node ID: {step.id}')
            if hasattr(step, 'source'):
                if step.source not in seen:
                    raise ValueError(f'{step.id}: source must reference an earlier node (no cycles).')
                if isinstance(seen[step.source], Export):
                    raise ValueError('Export nodes cannot be used as inputs.')
            seen[step.id] = step
        exports = [s for s in self.steps if isinstance(s, Export)]
        if not exports:
            raise ValueError('At least one export node is required.')
        if len({s.filename.casefold() for s in exports}) != len(exports):
            raise ValueError('Export filenames must be unique, ignoring letter case.')
        reachable = set()
        def visit(node_id):
            reachable.add(node_id)
            node = seen[node_id]
            if hasattr(node, 'source'):
                visit(node.source)
        for node in exports:
            visit(node.id)
        if len(reachable) != len(seen):
            raise ValueError('Every node must contribute to an exported result.')
        return self


class TaskRequirement(StrictModel):
    request_excerpt: str = Field(min_length=1, max_length=12000)
    action: Literal['read', 'extract_invoices', 'filter', 'filter_rows', 'flag', 'flag_rows', 'calculate', 'aggregate', 'select', 'sort', 'deduplicate', 'date_difference', 'export']
    step_ids: list[str] = Field(min_length=1, max_length=30, description='IDs only of steps whose operation matches this requirement action (compound flag/filter aliases allowed). Do not include upstream read or downstream export IDs unless that is the declared action.')
    output_columns: list[str] = Field(max_length=200, description='Only columns explicitly required in the FINAL exported report for this requirement. Not the columns available at this step. Use [] for intermediate inputs/calculations consumed by later steps.')


class CompilerResponse(StrictModel):
    workflow: Workflow | None
    clarification: str | None
    requirements: list[TaskRequirement] = Field(default_factory=list, max_length=60)

    @model_validator(mode='after')
    def exclusive(self):
        if (self.workflow is None) == (not self.clarification):
            raise ValueError('Return either a workflow or a non-empty clarification, never both.')
        return self


class PlanResponse(StrictModel):
    """Compact provider response; requirement bookkeeping is not generated."""
    title: str | None
    steps: list[Step] = Field(max_length=30)
    clarification: str | None

    @model_validator(mode='after')
    def valid_outcome(self):
        if self.clarification:
            if self.steps:
                raise ValueError('A clarification must not include a partial executable plan.')
        elif not self.title or not self.steps:
            raise ValueError('A supported task needs a title and executable steps.')
        return self

    def envelope(self):
        return CompilerResponse(workflow=None if self.clarification else
            Workflow(version='1.0', title=self.title, steps=self.steps),
            clarification=self.clarification, requirements=[])
