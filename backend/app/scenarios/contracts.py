from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class OwnerContext(Contract):
    owner_id: str = Field(min_length=1, max_length=100)
    workspace_id: str = Field(min_length=1, max_length=100)


from ..contracts import Period

class Selection(Contract):
    period: Period | None = Field(default=None,exclude=True)
    dashboard: Literal['sales', 'service']
    filters: dict[str, list[str]] = Field(default_factory=dict)
    record_ids: list[str] = Field(default_factory=list, max_length=3600)
    top_n: int | None = Field(default=None, ge=1, le=1200)
    sort: Literal['amount', 'id'] = 'amount'
    descending: bool = True


class ScaleLinePrices(Contract):
    kind: Literal['scale_line_prices']
    factor: Decimal = Field(gt=0, allow_inf_nan=False)


class SetStage(Contract):
    kind: Literal['set_stage']
    stage: str
    probability: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    close_date: Date | None = None


class SetExpectedClose(Contract):
    kind: Literal['set_expected_close']
    date: Date | None = None
    day_offset: int | None = None

    @model_validator(mode='after')
    def one_value(self):
        if (self.date is None) == (self.day_offset is None):
            raise ValueError('Specify date or day_offset')
        return self


class AdjustResolution(Contract):
    kind: Literal['adjust_resolution']
    factor: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    target_days: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def one_value(self):
        if (self.factor is None) == (self.target_days is None):
            raise ValueError('Specify factor or target_days')
        return self


class RefreshDates(Contract):
    kind: Literal['refresh_dates']
    day_offset: int = Field(ge=-36500, le=36500)


from .industry import IndustryAdaptation

NumericOperation = Annotated[ScaleLinePrices | SetStage | SetExpectedClose | AdjustResolution | RefreshDates, Field(discriminator='kind')]

Operation = Annotated[ScaleLinePrices | SetStage | SetExpectedClose | AdjustResolution | RefreshDates | IndustryAdaptation, Field(discriminator="kind")]

class Proposal(Contract):
    parent_id: str
    semantic_version: Literal['1.0.0'] = '1.0.0'
    selection: Selection
    operations: list[Operation] = Field(min_length=1, max_length=5)


class Candidate(Contract):
    id: str
    parent_id: str | None
    revision: int
    content_hash: str
    as_of_date: Date
    status: Literal['baseline', 'preview', 'rejected', 'applied']


class ValidationReport(Contract):
    hard_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Comparison(Contract):
    review_summary: dict | None = None
    selection_summary: dict = Field(default_factory=dict)
    current_id: str
    candidate_id: str
    metric_deltas: dict = Field(default_factory=dict)
    changed_counts: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class Approval(Contract):
    id: str
    candidate_id: str
    content_hash: str
    expected_active_id: str


class Activation(Contract):
    id: str
    active_id: str
    prior_id: str


class ReviewEvent(Contract):
    kind: Literal['approve', 'reject', 'edit', 'annotate', 'override', 'clarify', 'retry']
    actor: str
    target: str
    reason: str = Field(default='', max_length=2000)
    changes_requested: bool = False
