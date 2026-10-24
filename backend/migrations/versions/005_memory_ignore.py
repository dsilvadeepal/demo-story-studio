"""Owner-controlled per-run memory exclusions invalidate pending approval."""
from alembic import op
revision='005'
down_revision='004'


def upgrade():
    op.execute('''
    CREATE FUNCTION studio_memory_invalidate_approvals() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF OLD.content_hash IS DISTINCT FROM NEW.content_hash OR
         (OLD.status='saved' AND NEW.status<>'saved') THEN
        UPDATE public.studio_approvals SET valid=false
          WHERE owner_id=NEW.owner_id AND workspace_id=NEW.workspace_id AND valid;
      END IF;
      RETURN NEW;
    END $$;
    REVOKE ALL ON FUNCTION studio_memory_invalidate_approvals() FROM PUBLIC;
    CREATE TRIGGER memory_approval_invalidation AFTER UPDATE ON studio_memories
      FOR EACH ROW EXECUTE FUNCTION studio_memory_invalidate_approvals();
    CREATE FUNCTION studio_ignore_memory(o text,w text,r_id text,ids jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE r public.studio_runs%ROWTYPE; ignored jsonb;
    BEGIN
      SELECT * INTO r FROM public.studio_runs WHERE id=r_id AND owner_id=o AND workspace_id=w FOR UPDATE;
      IF NOT FOUND OR jsonb_typeof(ids)<>'array' OR jsonb_array_length(ids)>5 THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
      IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(ids) x WHERE NOT EXISTS(SELECT 1 FROM public.studio_memories m WHERE m.id=x AND m.owner_id=o AND m.workspace_id=w)) THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
      SELECT coalesce(jsonb_agg(id),'[]'::jsonb) INTO ignored FROM (SELECT DISTINCT value id FROM jsonb_array_elements(coalesce(r.scope->'ignored_memory_ids','[]'::jsonb)||ids)) x;
      IF jsonb_array_length(ignored)>5 THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
      UPDATE public.studio_runs SET scope=jsonb_set(scope,'{ignored_memory_ids}',ignored),
        result=jsonb_set(result,'{memory_ids}',coalesce((SELECT jsonb_agg(value) FROM jsonb_array_elements(coalesce(result->'memory_ids','[]'::jsonb)) WHERE NOT ignored @> jsonb_build_array(value)),'[]'::jsonb)) WHERE id=r_id;
      UPDATE public.studio_approvals SET valid=false WHERE owner_id=o AND workspace_id=w AND candidate_id=r.result#>>'{review_state,candidate,id}';
    END $$;
    REVOKE ALL ON FUNCTION studio_ignore_memory(text,text,text,jsonb) FROM PUBLIC;
    ''')


def downgrade():raise RuntimeError('Memory exclusions are retained')
