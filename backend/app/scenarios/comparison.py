from collections import Counter
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import text
from ..queries.analytics import query as analytical_query, serialize
from .contracts import Comparison
from .repository import get_candidate, read_bundle


def changes(c,owner,current_id,candidate_id):
    before=read_bundle(c,owner,current_id);after=read_bundle(c,owner,candidate_id)
    result=[]
    for key in ('industry','page_titles'):
        old=before['manifest'].get('presentation',{}).get(key);new=after['manifest'].get('presentation',{}).get(key)
        if old!=new:result.append(dict(table='dashboard',record_id='presentation',field=key,before=old,after=new))
    for name,rows in before['tables'].items():
        old={r['id']:r for r in rows}
        for row in after['tables'][name]:
            for field in sorted(row):
                if field!='dataset_id' and row[field]!=old[row['id']][field]:
                    result.append(dict(table=name,record_id=row['id'],field=field,before=old[row['id']][field],after=row[field]))
    return serialize(result)


def record_diff(c,owner,candidate_id,cursor=0,page_size=100,table=None):
    if cursor<0 or not 1<=page_size<=100:raise ValueError('Invalid pagination')
    candidate=get_candidate(c,owner,candidate_id)
    if candidate.parent_id is None:return dict(changes=[],total=0,next_cursor=None)
    rows=changes(c,owner,candidate.parent_id,candidate_id)
    if table:
        if table not in {'dashboard','accounts','users','products','opportunities','cases','pricebooks','opportunity_line_items'}:raise ValueError('Unsupported difference table')
        rows=[row for row in rows if row['table']==table]
    end=cursor+page_size
    return dict(changes=rows[cursor:end],total=len(rows),next_cursor=end if end<len(rows) else None)


def industry_review(before, after, operation):
    """Bounded review evidence, calculated from the actual parent and candidate."""
    from .industry import TEXT_FIELDS, IndustryAdaptation, apply_vocabulary
    from copy import deepcopy
    old={t:{r['id']:r for r in rows} for t,rows in before['tables'].items()}
    new={t:{r['id']:r for r in rows} for t,rows in after['tables'].items()}
    identities=all(set(old[t])==set(new[t]) for t in old)
    protected=identities and all(
        r.get(k)==new[t][rid].get(k) for t,rows in old.items() for rid,r in rows.items()
        for k in r if k!='dataset_id' and k not in TEXT_FIELDS.get(t,set()))
    expected=deepcopy(before)
    try:
        apply_vocabulary(expected,IndustryAdaptation.model_validate(operation))
        rules_match=expected['manifest'].get('presentation')==after['manifest'].get('presentation') and all(
            all(row.get(k)==new[t][row['id']].get(k) for k in fields)
            for t,fields in TEXT_FIELDS.items() for row in expected['tables'][t])
    except (ValueError,KeyError):
        rules_match=False
    counts={t:sum(any(r.get(k)!=new[t].get(rid,{}).get(k) for k in fields) for rid,r in old[t].items()) for t,fields in TEXT_FIELDS.items()}
    def pair(t,rid,field):
        return dict(kind=t,id=rid,before=old[t][rid][field],after=new[t][rid][field])
    examples=[]
    for line in sorted(before['tables']['opportunity_line_items'],key=lambda r:r['id']):
        oid=line['opportunity_id']
        if any(e['opportunity_id']==oid for e in examples):continue
        opp=old['opportunities'][oid]; aid=opp['account_id']
        pid=old['pricebook_entries'][line['pricebook_entry_id']]['product_id']
        chain=[pair('accounts',aid,'name'),pair('opportunities',oid,'name'),pair('products',pid,'name')]
        case=next((r for r in before['tables']['cases'] if r['account_id']==aid),None)
        if case:chain.append(pair('cases',case['id'],'subject'))
        examples.append(dict(opportunity_id=oid,chain=chain))
        if len(examples)==3:break
    return dict(industry=operation['industry'],counts=counts,rules=operation,examples=examples,
        checks=[dict(label='Record counts and IDs preserved',passed=identities),
                dict(label='Relationships, numeric facts, dates and other protected fields preserved',passed=protected),
                dict(label='All naming rules and page titles match the stored proposal',passed=rules_match)])


def compare(c,owner,current_id,candidate_id,query,aligned_period=False):
    current=get_candidate(c,owner,current_id); candidate=get_candidate(c,owner,candidate_id)
    before_request=query.model_copy(update={'dataset_id':current_id})
    after_request=query.model_copy(update={'dataset_id':candidate_id})
    offset=(candidate.as_of_date-current.as_of_date).days
    warnings=[]
    if offset:
        warnings.append(f'As-of shifts {offset} UTC days across Sales and Service; identical absolute filters may select different cohorts.')
    if aligned_period:
        if not query.period:raise ValueError('Aligned-period comparison requires a period')
        after_request=after_request.model_copy(update={'period':query.period.model_copy(update={'start':query.period.start+timedelta(days=offset),'end':query.period.end+timedelta(days=offset)})})
        warnings.append('ALIGNED-PERIOD comparison: candidate period shifted; not identical-filter evidence.')
    proposal=c.scalar(text('SELECT proposal FROM studio_candidates WHERE id=:id'),{'id':candidate_id}) or {}
    operation=next((op for op in proposal.get('operations',[]) if op.get('kind')=='adapt_industry'),None)
    if operation and current_id==candidate.parent_id and query.dashboard=='service':
        before_filters=dict(query.filters);after_filters=dict(query.filters)
        for field,key in [('division','divisions'),('type','case_types')]:
            mapping={m['source']:m['target'] for m in operation.get(key,[])}
            values=query.filters.get(field,[])
            if mapping and values:
                if query.dataset_id==candidate_id:
                    inverse={v:k for k,v in mapping.items()}
                    before_filters[field]=[inverse.get(v,v) for v in values]
                else:
                    after_filters[field]=[mapping.get(v,v) for v in values]
                warnings.append('Category filter '+field+' aligned through the reviewed naming mapping; labels differ, membership is preserved.')
        before_request=before_request.model_copy(update={'filters':before_filters})
        after_request=after_request.model_copy(update={'filters':after_filters})
    a=analytical_query(c,before_request)['values']; b=analytical_query(c,after_request)['values']
    deltas={k:dict(before=a[k],after=b[k],delta=str(Decimal(str(b[k]))-Decimal(str(a[k]))) if a[k] is not None and b[k] is not None else None) for k in a}
    counts=Counter(x['table']+'.'+x['field'] for x in changes(c,owner,current_id,candidate_id))
    validation=c.scalar(text('SELECT validation FROM studio_candidates WHERE id=:id'),{'id':candidate_id})
    warnings.extend(validation.get('warnings',[]))
    proposal=c.scalar(text('SELECT proposal FROM studio_candidates WHERE id=:id'),{'id':candidate_id}) or {}
    selection=proposal.get('selection',{})
    summary={'domain':selection.get('dashboard',query.dashboard),'count':len(selection.get('record_ids',[])),'global':any(op.get('kind') in ('refresh_dates','adapt_industry') for op in proposal.get('operations',[]))}
    review=None
    operation=next((op for op in proposal.get('operations',[]) if op.get('kind')=='adapt_industry'),None)
    if operation and candidate.parent_id:
        review=industry_review(read_bundle(c,owner,candidate.parent_id),read_bundle(c,owner,candidate_id),operation)
        review['parent_id']=candidate.parent_id
    return Comparison(review_summary=review,selection_summary=summary,current_id=current_id,candidate_id=candidate_id,metric_deltas=deltas,changed_counts=dict(counts),warnings=warnings)
