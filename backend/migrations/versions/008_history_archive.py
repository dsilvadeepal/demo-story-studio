"""Reversible preview history cleanup; business data and audit trails are retained."""
from alembic import op
revision='008'
down_revision='007'


def upgrade():
    op.execute('''
    ALTER TABLE studio_candidates ADD COLUMN archived_at timestamptz;
    CREATE FUNCTION studio_archive_history(o text,w text,action text,keep_id text) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE n integer;
    BEGIN
      IF o<>'owner' OR w<>'local' THEN RAISE EXCEPTION 'HISTORY_UNAVAILABLE'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(o || ':' || w,0));
      IF action='restore' THEN
        IF (SELECT count(*) FROM public.studio_candidates WHERE owner_id=o AND workspace_id=w AND archived_at IS NULL)>=20 THEN RAISE EXCEPTION 'LIMIT_REACHED: clean up history before restoring'; END IF;
        UPDATE public.studio_candidates SET archived_at=NULL WHERE id=keep_id AND owner_id=o AND workspace_id=w AND archived_at IS NOT NULL;
      ELSIF action='archive' THEN
        UPDATE public.studio_candidates c SET archived_at=now()
        WHERE c.owner_id=o AND c.workspace_id=w AND c.archived_at IS NULL
          AND c.status IN ('preview','rejected') AND c.id IS DISTINCT FROM keep_id
          AND c.id NOT IN (SELECT id FROM public.studio_candidates WHERE owner_id=o AND workspace_id=w AND archived_at IS NULL AND status IN ('preview','rejected') ORDER BY revision DESC LIMIT 3)
          AND NOT EXISTS (SELECT 1 FROM public.studio_active a WHERE a.dataset_id=c.id)
          AND NOT EXISTS (SELECT 1 FROM public.studio_approvals a WHERE a.candidate_id=c.id AND a.valid)
          AND NOT EXISTS (SELECT 1 FROM public.studio_candidates child WHERE child.parent_id=c.id AND child.archived_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM public.studio_runs r WHERE r.owner_id=o AND r.workspace_id=w AND r.status IN ('queued','running','retrying','paused','interrupted') AND (r.parent_id=c.id OR r.result->>'candidate_id'=c.id OR r.result->'review_state'->'candidate'->>'id'=c.id));
      ELSE RAISE EXCEPTION 'HISTORY_UNAVAILABLE'; END IF;
      GET DIAGNOSTICS n=ROW_COUNT;
      RETURN n;
    END $$;
    REVOKE ALL ON FUNCTION studio_archive_history(text,text,text,text) FROM PUBLIC;
    ''')


def downgrade():
    op.execute('DROP FUNCTION studio_archive_history(text,text,text,text); ALTER TABLE studio_candidates DROP COLUMN archived_at')
