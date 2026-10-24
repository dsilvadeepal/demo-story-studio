"""Model-selected vocabulary, deterministically expanded across a synthetic dataset."""
import re
from string import Formatter
from pydantic import Field, model_validator
from pydantic import BaseModel, ConfigDict

class Contract(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
from typing import Literal

TEXT_FIELDS = {'accounts': {'name', 'industry'}, 'products': {'name', 'family'},
               'opportunities': {'name'}, 'cases': {'subject', 'type'}, 'users': {'division'}, 'pricebooks': {'name', 'description'}}
PAGE_KEYS = ('executive', 'pipeline', 'detail', 'trend', 'breakdown')

class Vocabulary(Contract):
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=80)

class IndustryAdaptation(Contract):
    kind: Literal['adapt_industry'] = 'adapt_industry'
    industry: str = Field(min_length=2, max_length=80)
    company_descriptor: str = Field(min_length=2, max_length=60)
    families: list[Vocabulary] = Field(min_length=1, max_length=20)
    case_subjects: list[Vocabulary] = Field(min_length=1, max_length=20)
    divisions: list[Vocabulary] = Field(default_factory=list, max_length=20, description='Optional complete distinct division/region mapping; empty preserves.')
    case_types: list[Vocabulary] = Field(default_factory=list, max_length=20, description='Optional complete distinct case-type mapping; empty preserves.')
    opportunity_template: str = Field(min_length=5, max_length=100)
    page_titles: dict[str, str] = Field(description="Five industry titles: executive Sales Overview, pipeline Sales Pipeline, detail Deal Details, trend Service Trends, breakdown Service Workload. Preserve meanings.")

    @model_validator(mode='after')
    def bounded_text(self):
        values=[self.industry,self.company_descriptor,self.opportunity_template]
        for mappings in (self.families,self.case_subjects,self.divisions,self.case_types):
            if len({m.source for m in mappings})!=len(mappings):raise ValueError('Duplicate source vocabulary')
            if len({m.target.casefold() for m in mappings})!=len(mappings):raise ValueError('Distinct categories need distinct target labels')
            values.extend(v for m in mappings for v in (m.source,m.target))
        if set(self.page_titles)!=set(PAGE_KEYS):raise ValueError('Supply all five page titles')
        if any(not 2<=len(t)<=80 for t in self.page_titles.values()):raise ValueError('Invalid page title length')
        values.extend(self.page_titles.values())
        if any(v!=v.strip() or any(ord(c)<32 or c in '<>' for c in v) for v in values):raise ValueError('Use plain text without markup or control characters')
        parts=list(Formatter().parse(self.opportunity_template))
        fields=[field for _,field,_,_ in parts if field is not None]
        if not self.opportunity_template.startswith('{family}') or not self.opportunity_template.endswith('{number}') or set(fields)!={'family','number'} or any(spec or conversion for _,_,spec,conversion in parts):
            raise ValueError('Opportunity template requires only {family} and {number}')
        anchors={'executive':('sales',('overview','summary')),'pipeline':('sales',('pipeline',)),
                 'detail':('deal',('details','detail')),'trend':('service',('trends','trend')),
                 'breakdown':('service',('breakdown','workload'))}
        for key,(domain,topics) in anchors.items():
            title=self.page_titles[key].casefold()
            if title in ('sales overview','executive summary','sales pipeline','pipeline analysis','deal details','detail analysis','service trends','service workload','trend analysis','breakdown'):
                raise ValueError('Use industry-specific page titles, not generic page names')
            if domain not in title or not any(title.endswith(topic) for topic in topics):
                raise ValueError('Page titles must retain canonical Sales/Service meaning')
        return self

def subject_stem(subject):
    return re.sub(r' #\d+$','',subject)

def adaptation_context(bundle):
    t=bundle['tables']
    return dict(industry=bundle['manifest'].get('presentation',{}).get('industry','Mixed synthetic industries'),
        families=sorted({r['family'] for r in t['products']}),
        divisions=sorted({r['division'] for r in t['users']}),case_types=sorted({r['type'] for r in t['cases']}),
        case_subjects=sorted({subject_stem(r['subject']) for r in t['cases']}),
        examples={name:[{k:v for k,v in row.items() if k in fields} for row in t[name][:1]] for name,fields in TEXT_FIELDS.items() if name in ('accounts',)},
        page_keys=list(PAGE_KEYS),preserved='IDs, relationships, quantities, prices, dates, stages, metric definitions',
        scope='Entire dataset across Sales and Service; shared products and accounts',
        opportunity_template_example='{family} supply agreement {number}',
        naming_rule='Cover all sources with distinct targets. Divisions relabel owners, not assignments. Case types must fit all subjects. Company descriptor follows existing brand. Template starts {family}, ends {number}. Keep page meanings.',
        page_meanings={'executive':'Sales overview','pipeline':'Sales pipeline','detail':'Deal details','trend':'Service trends','breakdown':'Service workload'})

def apply_vocabulary(bundle, op):
    t=bundle['tables']; families={m.source:m.target for m in op.families}; subjects={m.source:m.target for m in op.case_subjects}
    if set(families)!={r['family'] for r in t['products']} or set(subjects)!={subject_stem(r['subject']) for r in t['cases']}:
        raise ValueError('Inspect current vocabulary and cover every source category exactly')
    for field,table,mappings in [('division','users',op.divisions),('type','cases',op.case_types)]:
        if mappings:
            mapping={m.source:m.target for m in mappings}
            if set(mapping)!={r[field] for r in t[table]}:raise ValueError('Cover every current '+field+' category exactly')
            for row in t[table]:row[field]=mapping[row[field]]
    for i,row in enumerate(sorted(t['accounts'],key=lambda r:r['id']),1):
        stem=row['name'].split()[0]
        row.update(name=f'{stem} {op.company_descriptor} {i:03d}',industry=op.industry)
    for i,row in enumerate(sorted(t['products'],key=lambda r:r['id']),1):
        row['family']=families[row['family']];row['name']=f"{row['family']} model {i:03d}"
    products={r['id']:r for r in t['products']}; entries={r['id']:r for r in t['pricebook_entries']}
    first={}
    for line in sorted(t['opportunity_line_items'],key=lambda r:r['id']):
        first.setdefault(line['opportunity_id'],products[entries[line['pricebook_entry_id']]['product_id']]['family'])
    for i,row in enumerate(sorted(t['opportunities'],key=lambda r:r['id']),1):
        row['name']=op.opportunity_template.format(family=first[row['id']],number=f'{i:04d}')
    for i,row in enumerate(sorted(t['cases'],key=lambda r:r['id']),1):row['subject']=f"{subjects[subject_stem(row['subject'])]} #{i}"
    for i,row in enumerate(sorted(t['pricebooks'],key=lambda r:r['id']),1):
        row.update(name=f'{op.industry} pricebook {i}',description=f'Synthetic USD pricing for {op.industry}')
    bundle['manifest']['presentation']={'industry':op.industry,'page_titles':dict(op.page_titles)}
