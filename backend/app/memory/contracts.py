import re
from typing import Literal
from pydantic import Field, model_validator
from ..scenarios.contracts import Contract


class MemoryScope(Contract):
    owner_id: str = Field(min_length=1,max_length=100)
    workspace_id: str = Field(min_length=1,max_length=100)
    domain: Literal['sales','service']
    audience: str = Field(min_length=1,max_length=80)
    intent: str = Field(min_length=1,max_length=120)


class MemoryDraft(Contract):
    kind: Literal['preference','recipe']
    text: str = Field(min_length=10,max_length=600)
    scope: MemoryScope
    source_run_id: str | None = Field(default=None,max_length=100)
    source_revision_id: str | None = Field(default=None,max_length=100)

    @model_validator(mode='after')
    def reusable_only(self):
        # Reusable qualitative instructions only; never historical facts or authority.
        combined=' '.join((self.text,self.scope.audience,self.scope.intent))
        if re.search(r'\d|[$€£]|api.?key|bearer|password|secret|approv|authoriz|ignore previous|system prompt|https?://|@',combined,re.I):
            raise ValueError('Memory must contain qualitative reusable guidance, without records, totals, credentials or approvals')
        if self.kind=='recipe' and not self.source_revision_id:
            raise ValueError('Recipe requires an applied source revision')
        return self


class MemoryItem(Contract):
    id: str
    provider_id: str | None
    draft: MemoryDraft
    content_hash: str
    correlation: str
    status: Literal['proposed','confirmed','saving','saved','failed','unknown','deletion-pending','deleted']
