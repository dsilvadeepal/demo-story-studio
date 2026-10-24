from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from ..scenarios.repository import canonical
from ..scenarios.lifecycle import ScenarioError


def reserve_call(c,owner,run_id,request):
    payload=dict(request.model_dump(),id=str(uuid4()))
    try:
        with c.begin_nested():
            return c.scalar(text('SELECT studio_reserve(:owner,:workspace,:run,CAST(:request AS jsonb))'),
                dict(owner=owner.owner_id,workspace=owner.workspace_id,run=run_id,request=canonical(payload)))
    except DBAPIError as error:
        code='LIMIT_REACHED' if 'LIMIT_REACHED' in str(error.orig) else 'BUDGET_UNAVAILABLE'
        raise ScenarioError(code) from None


def settle_call(c,reservation_id,usage):
    c.execute(text('SELECT studio_settle(:id,CAST(:usage AS jsonb))'),dict(id=reservation_id,usage=canonical(usage.model_dump()) if usage is not None else None))
