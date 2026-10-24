"""Independent structural/integrity checks; no model judgment is authoritative."""
from decimal import Decimal
from .contracts import ValidationReport
from .operations import FIELDS, check_operations
from ..seed import STAGES


def validate_candidate(parent: dict, candidate: dict, proposal) -> ValidationReport:
    errors, warnings = [], []
    try:
        check_operations(proposal)
    except ValueError as error:
        errors.append(str(error))
    for key in ('semantic_version','seed','generator_version','counts'):
        if parent['manifest'][key] != candidate['manifest'].get(key):
            errors.append('Unauthorized manifest change: '+key)
    original, changed = parent['tables'], candidate['tables']
    if set(original) != set(changed):
        return ValidationReport(hard_errors=['Business tables changed'])
    refresh = any(op.kind in ('refresh_dates','adapt_industry') for op in proposal.operations)
    allowed = {}
    for op in proposal.operations:
        for table, fields in FIELDS[op.kind].items():
            allowed.setdefault(table,set()).update(fields)
        if op.kind == 'scale_line_prices' and not Decimal('.75') <= op.factor <= Decimal('1.25'):
            warnings.append('Price factor outside 0.75–1.25; review synthetic realism')
        if op.kind == 'set_stage' and len(proposal.selection.record_ids) > len(original['opportunities'])/4:
            warnings.append('Stage change affects more than 25% of opportunities')
    adaptations=[op for op in proposal.operations if op.kind=='adapt_industry']
    expected_presentation=parent['manifest'].get('presentation',{})
    if adaptations:
        from copy import deepcopy
        from .industry import apply_vocabulary, TEXT_FIELDS
        expected=deepcopy(parent)
        try:
            apply_vocabulary(expected,adaptations[0])
            expected_presentation=expected['manifest']['presentation']
            for table,fields in TEXT_FIELDS.items():
                expected_rows={r['id']:r for r in expected['tables'][table]}
                for row in changed[table]:
                    if row['id'] not in expected_rows or any(row.get(f)!=expected_rows[row['id']][f] for f in fields):
                        errors.append('Industry wording differs from approved vocabulary')
        except (ValueError,KeyError):errors.append('Invalid industry vocabulary')
        warnings.append('Review industry wording for realism. Labels do not redefine metrics; named filters may select different records after renaming.')
    if candidate['manifest'].get('presentation',{})!=expected_presentation:errors.append('Unauthorized presentation change')
    ids = set(proposal.selection.record_ids)
    as_of = candidate['manifest']['as_of_date']
    expected_as_of = parent['manifest']['as_of_date']
    from datetime import timedelta
    for op in proposal.operations:
        if op.kind == 'refresh_dates': expected_as_of += timedelta(days=op.day_offset)
    if as_of != expected_as_of: errors.append('Unexpected as-of date')
    for name, rows in original.items():
        old = {r['id']:r for r in rows}; new = {r['id']:r for r in changed[name]}
        if old.keys() != new.keys() or len(rows) != len(changed[name]) or len(new) != len(changed[name]):
            errors.append(name+': ID set or count changed');continue
        for id,row in new.items():
            before = old[id]
            eligible = refresh or (row.get('opportunity_id') if name=='opportunity_line_items' else id) in ids
            permitted = allowed.get(name,set()) if eligible else set()
            if row.keys() != before.keys() or any(row[k] != before[k] for k in row if k not in permitted and k != 'dataset_id'):
                errors.append(name+': unauthorized field change');break
        for row in new.values():
            if name in ('opportunities','cases'):
                close = row['close_date'] if name=='opportunities' else row['closed_date']
                if row['created_at'].date() > as_of or (close and close < row['created_at']): errors.append(name+': invalid date order')
                if name=='opportunities':
                    stage,p = row['stage'],row['probability']
                    if stage not in STAGES or not 0<=p<=100 or (stage=='Closed Won' and p!=100) or (stage=='Closed Lost' and p!=0): errors.append('Invalid stage/probability')
                    if stage.startswith('Closed') and close.date()>as_of: errors.append('Closed opportunity exceeds as-of')
                else:
                    if (row['status']=='Closed') != (close is not None) or (close and close.date()>as_of): errors.append('Invalid case closure')
            if name in ('opportunity_line_items','pricebook_entries'):
                if row['unit_price']<0 or row['unit_price']>=Decimal('10000000000000000'): errors.append('Invalid price')
                if name=='opportunity_line_items' and row['quantity']<=0: errors.append('Invalid quantity')
    return ValidationReport(hard_errors=sorted(set(errors)), warnings=warnings)
