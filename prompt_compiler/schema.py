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
    comparison: Literal['gt', 'gte', 'lt', 'lte', 'eq', 'ne']
    value: Union[float, str, bool]
    case_sensitive: bool = False


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


Step = Annotated[Union[Read, Extract, Filter, Flag, FilterRows, FlagRows, Calculate, Aggregate, Select, Sort, Export], Field(discriminator='operation')]


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
        if len({s.filename for s in exports}) != len(exports):
            raise ValueError('Export filenames must be unique.')
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


class CompilerResponse(StrictModel):
    workflow: Workflow | None
    clarification: str | None

    @model_validator(mode='after')
    def exclusive(self):
        if (self.workflow is None) == (not self.clarification):
            raise ValueError('Return either a workflow or a non-empty clarification, never both.')
        return self
