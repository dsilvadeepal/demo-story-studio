"""Explicit interruption of orphaned queued work; never replay automatically."""
from alembic import op
revision='006'
down_revision='005'
def upgrade():
    op.execute('''CREATE FUNCTION studio_interrupt_queued(o text,w text,r text) RETURNS void
    LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      UPDATE public.studio_runs SET status='interrupted',lease_until=NULL
      WHERE id=r AND owner_id=o AND workspace_id=w AND status IN ('queued','retrying');
    $$;
    REVOKE ALL ON FUNCTION studio_interrupt_queued(text,text,text) FROM PUBLIC;''')
def downgrade():raise RuntimeError('Run audit history is retained')
