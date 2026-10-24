"""Bounded pure transformations. All record selections are resolved before writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from ..contracts import QueryRequest
from ..queries.analytics import read_facts, filtered
from ..seed import STAGES, checksum
from .contracts import Proposal

from .industry import TEXT_FIELDS, apply_vocabulary

FIELDS = {
    'adapt_industry': TEXT_FIELDS,
    'scale_line_prices': {'opportunity_line_items': {'unit_price'}},
    'set_stage': {'opportunities': {'stage','probability','close_date'}},
    'set_expected_close': {'opportunities': {'close_date'}},
    'adjust_resolution': {'cases': {'closed_date'}},
    'refresh_dates': {'opportunities': {'created_at','close_date'}, 'cases': {'created_at','closed_date'}},
}


def resolve_selection(c, proposal: Proposal) -> list[str]:
    selection = proposal.selection
    if any(op.kind in ('refresh_dates','adapt_industry') for op in proposal.operations):
        if selection.record_ids or selection.filters or selection.top_n or selection.period:
            raise ValueError('Global adaptation or date refresh requires the entire dataset')
        return []
    request = QueryRequest(dataset_id=proposal.parent_id, dashboard=selection.dashboard, filters=selection.filters,period=selection.period)
    rows, _ = read_facts(c, request)
    rows = filtered(rows, request)
    available = {row['id'] for row in rows}
    if selection.record_ids:
        if not set(selection.record_ids) <= available:
            raise ValueError('Selection contains unknown or out-of-scope records')
        rows = [row for row in rows if row['id'] in selection.record_ids]
    elif not selection.top_n:
        raise ValueError('Confirm explicit record IDs or top-N scope')
    if selection.top_n:
        if selection.dashboard != 'sales' or selection.sort != 'amount' or not selection.descending:
            raise ValueError('Top-N requires opportunities ordered by descending amount')
        rows.sort(key=lambda row: (-row['amount'], row['id']))
        rows = rows[:selection.top_n]
    else:
        rows.sort(key=lambda row: row['id'])
    if not rows:
        raise ValueError('Selection is empty')
    return [row['id'] for row in rows]


def check_operations(proposal):
    seen = set()
    if any(op.kind in ("refresh_dates", "adapt_industry") for op in proposal.operations) and len(proposal.operations) != 1:
        raise ValueError("Global refresh and scoped edits require separate revisions")
    if not 1 <= len(proposal.operations) <= 5:
        raise ValueError('One to five operations required')
    for op in proposal.operations:
        fields = {(table,field) for table,fields in FIELDS[op.kind].items() for field in fields}
        if fields & seen:
            raise ValueError('Conflicting operations affect the same field')
        seen |= fields
        if op.kind in ('scale_line_prices','set_stage','set_expected_close') and proposal.selection.dashboard != 'sales':
            raise ValueError('Sales operation outside Sales scope')
        if op.kind == 'adjust_resolution' and proposal.selection.dashboard != 'service':
            raise ValueError('Service operation outside Service scope')
        if op.kind == 'set_stage':
            if op.stage not in STAGES or (op.stage == 'Closed Won' and op.probability != 100) or (op.stage == 'Closed Lost' and op.probability != 0):
                raise ValueError('Invalid stage/probability')


def transform(bundle: dict, proposal: Proposal) -> dict:
    check_operations(proposal)
    if proposal.parent_id != bundle['manifest']['id'] or proposal.semantic_version != bundle['manifest']['semantic_version']:
        raise ValueError('Parent/semantic version mismatch')
    refresh = any(op.kind in ('refresh_dates','adapt_industry') for op in proposal.operations)
    selection = proposal.selection
    if refresh and (selection.record_ids or selection.top_n or selection.filters or selection.period):
        raise ValueError('Global adaptation or date refresh requires the entire dataset')
    if not refresh and (not selection.record_ids or selection.top_n or selection.filters or selection.period or selection.period):
        raise ValueError('Resolve selection to explicit IDs first')
    domain = 'opportunities' if selection.dashboard == 'sales' else 'cases'
    ids = set(selection.record_ids)
    if len(ids) != len(selection.record_ids) or not ids <= {r['id'] for r in bundle['tables'][domain]}:
        raise ValueError('Invalid record IDs')
    result = deepcopy(bundle)
    for op in proposal.operations:
        if op.kind == 'adapt_industry':
            apply_vocabulary(result,op)
        elif op.kind == 'refresh_dates':
            delta = timedelta(days=op.day_offset)
            result['manifest']['as_of_date'] += delta
            for name, fields in FIELDS[op.kind].items():
                for row in result['tables'][name]:
                    for field in fields:
                        if row[field] is not None:
                            row[field] += delta
        elif op.kind == 'scale_line_prices':
            for row in result['tables']['opportunity_line_items']:
                if row['opportunity_id'] in ids:
                    value = row['unit_price'] * op.factor
                    if not value.is_finite() or value >= Decimal('10000000000000000'):
                        raise ValueError('Price exceeds database precision')
                    row['unit_price'] = value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        else:
            for row in result['tables'][domain]:
                if row['id'] not in ids:
                    continue
                if op.kind == 'set_stage':
                    if op.stage.startswith('Closed') and not row['stage'].startswith('Closed') and op.close_date is None:
                        raise ValueError('Closing an open deal requires an explicit close date')
                    row['stage'], row['probability'] = op.stage, op.probability
                    if op.close_date:
                        row['close_date'] = datetime.combine(op.close_date, row['created_at'].timetz())
                elif op.kind == 'set_expected_close':
                    if row['stage'].startswith('Closed'):
                        raise ValueError('Expected close applies only to open opportunities')
                    row['close_date'] = datetime.combine(op.date, row['created_at'].timetz()) if op.date else row['close_date'] + timedelta(days=op.day_offset)
                elif op.kind == 'adjust_resolution':
                    if row['closed_date'] is None:
                        raise ValueError('Resolution changes require already closed cases')
                    duration = Decimal((row['closed_date'].astimezone(timezone.utc).date()-row['created_at'].astimezone(timezone.utc).date()).days)
                    days = (op.target_days if op.target_days is not None else duration*op.factor).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
                    if days > 36500:
                        raise ValueError('Resolution duration exceeds bound')
                    row['closed_date'] = row['created_at'] + timedelta(days=int(days))
    from .validation import validate_candidate
    report = validate_candidate(bundle,result,proposal)
    if report.hard_errors:
        raise ValueError('; '.join(report.hard_errors))
    result['manifest']['checksums'] = {name:checksum(rows) for name,rows in result['tables'].items()}
    return result
