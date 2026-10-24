"""Sparse, request-grounded edits to an already reviewed adaptation."""
import re
from copy import deepcopy
from typing import Literal
from pydantic import Field
from ..scenarios.industry import Contract, IndustryAdaptation

class RuleEdit(Contract):
    field: Literal['company_descriptor','industry','opportunity_template','families','case_subjects','divisions','case_types','page_titles']
    source: str | None = None
    value: str = Field(min_length=1,max_length=100)
    request_quote: str = Field(min_length=3,max_length=500,description='Exact affirmative instruction from current user request authorizing this field and value. Never quote a keep/preserve instruction.')

class AdaptationPatch(Contract):
    edits: list[RuleEdit] = Field(min_length=1,max_length=20)

ALIASES={'company_descriptor':r'compan|customer|descriptor','industry':r'industr',
'opportunity_template':r'opportunit|deal|template','families':r'product|famil',
'case_subjects':r'subject','divisions':r'region|division','case_types':r'case type|categor',
'page_titles':r'title|heading'}

def normalized(value):return ' '.join(value.casefold().split())

def merge_patch(base,patch,request):
    """Do not let a model regenerate or delete unspecified rules."""
    merged=deepcopy(base); op=merged['operations'][0]
    if len(merged['operations'])!=1 or op.get('kind')!='adapt_industry':raise ValueError('Industry refinement requires one adaptation')
    seen=set()
    for edit in patch.edits:
        quote=normalized(edit.request_quote)
        if quote not in normalized(request) or re.search(r'\b(keep|preserve|unchanged|retain|not|except)\b',quote):raise ValueError('Quote an affirmative change instruction, not a preservation instruction')
        if not re.search(ALIASES[edit.field],quote):raise ValueError('The request must explicitly identify the field to change')
        value=normalized(edit.value)
        literal=value.replace('{family}','').replace('{number}','').strip() if edit.field=='opportunity_template' else value
        if not literal or literal not in quote:raise ValueError('The replacement wording must occur in the quoted instruction')
        key=(edit.field,edit.source)
        if key in seen:raise ValueError('Duplicate patch target')
        seen.add(key)
        if edit.field in ('families','case_subjects','divisions','case_types'):
            entries=op.get(edit.field,[])
            matches=[x for x in entries if edit.source in (x['source'],x['target'])]
            if len(matches)!=1:raise ValueError('Specify one existing source or current label')
            entry=matches[0]
            if not any(normalized(x) in quote for x in (entry['source'],entry['target'])):raise ValueError('Name the existing category in the change instruction')
            entry['target']=edit.value
        elif edit.field=='page_titles':
            if edit.source not in op['page_titles']:raise ValueError('Unknown page key')
            # The current page title or canonical key must be identified explicitly.
            if normalized(edit.source) not in quote and normalized(op['page_titles'][edit.source]) not in quote:raise ValueError('Name the existing page title or page key')
            op['page_titles'][edit.source]=edit.value
        else:
            if edit.source is not None:raise ValueError('Scalar rule does not accept a source')
            op[edit.field]=edit.value
    merged['operations'][0]=IndustryAdaptation.model_validate(op).model_dump(mode='json')
    return merged
