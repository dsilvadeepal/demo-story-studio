"""Durable execution authority, independent of graph checkpoints."""
from alembic import op
revision='004'
down_revision='003'


def upgrade():
    op.execute('''
    ALTER TABLE studio_runs ADD COLUMN scope jsonb NOT NULL DEFAULT '{}',
      ADD COLUMN lease_until timestamptz, ADD COLUMN result jsonb NOT NULL DEFAULT '{}',
      ADD COLUMN resume_input jsonb, ADD COLUMN interrupt_id text;
    CREATE FUNCTION studio_run(o text,w text,a text,p jsonb) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE r public.studio_runs%ROWTYPE;
    BEGIN
      IF o<>'owner' OR w<>'local' THEN RAISE EXCEPTION 'RUN_UNAVAILABLE'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended('run:'||(p->>'id'),0));
      IF a='start' THEN
        IF NOT EXISTS(SELECT 1 FROM public.studio_candidates WHERE id=p->>'parent_id' AND owner_id=o AND workspace_id=w) THEN RAISE EXCEPTION 'RUN_UNAVAILABLE'; END IF;
        INSERT INTO public.studio_runs(id,owner_id,workspace_id,parent_id,brief,status,scope)
          VALUES(p->>'id',o,w,p->>'parent_id',p->>'brief','queued',p->'scope');
      ELSE
        SELECT * INTO r FROM public.studio_runs WHERE id=p->>'id' AND owner_id=o AND workspace_id=w FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'RUN_UNAVAILABLE'; END IF;
        CASE a
        WHEN 'claim' THEN
          IF r.status NOT IN ('queued','retrying') THEN RETURN to_jsonb(r); END IF;
          UPDATE public.studio_runs SET status='running',version=version+1,lease_until=now()+interval '3 minutes' WHERE id=r.id;
        WHEN 'finish' THEN
          IF r.status='cancelled' THEN RETURN to_jsonb(r); END IF;
          IF r.status<>'running' OR r.version<>(p->>'version')::integer OR p->>'status' NOT IN ('paused','complete','failed','interrupted') THEN RAISE EXCEPTION 'RUN_UNAVAILABLE'; END IF;
          UPDATE public.studio_runs SET status=p->>'status',result=p->'result',interrupt_id=p->>'interrupt_id',lease_until=NULL,resume_input=NULL WHERE id=r.id;
        WHEN 'resume' THEN
          IF r.status='paused' THEN
            IF r.interrupt_id IS DISTINCT FROM p#>>'{input,interrupt_id}' THEN RAISE EXCEPTION 'RUN_UNAVAILABLE'; END IF;
          ELSIF r.status NOT IN ('failed','interrupted') OR p#>>'{input,kind}'<>'retry' THEN RAISE EXCEPTION 'RUN_UNAVAILABLE'; END IF;
          UPDATE public.studio_runs SET status='retrying',resume_input=p->'input' WHERE id=r.id;
        WHEN 'cancel' THEN
          UPDATE public.studio_runs SET status='cancelled',lease_until=NULL WHERE id=r.id AND status<>'complete';
        WHEN 'expire' THEN
          UPDATE public.studio_runs SET status='interrupted',lease_until=NULL WHERE id=r.id AND status='running' AND lease_until<now();
        ELSE RAISE EXCEPTION 'RUN_UNAVAILABLE';
        END CASE;
      END IF;
      SELECT * INTO r FROM public.studio_runs WHERE id=p->>'id';
      RETURN to_jsonb(r);
    END $$;
    REVOKE ALL ON FUNCTION studio_run(text,text,text,jsonb) FROM PUBLIC;
    ''')


def downgrade():raise RuntimeError('Execution audit history is retained')
