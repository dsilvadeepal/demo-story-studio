"""Versioned industry presentation and strict text-only publication fields."""
from alembic import op
revision='007'
down_revision='006'
def upgrade():
    op.execute("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS presentation json NOT NULL DEFAULT '{}'::json")
    op.execute('''
    CREATE OR REPLACE FUNCTION studio_publish(p_owner text,p_workspace text,p_bundle jsonb,p_hash text,
      p_request_hash text,p_proposal jsonb,p_key text,p_validation jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE ds text := p_bundle->'manifest'->>'id'; parent text := p_proposal->>'parent_id';
      tab text; actual integer; expected integer; item jsonb; old_row jsonb; new_row jsonb; operation jsonb; allowed text[]; eligible boolean;
    BEGIN
      PERFORM pg_advisory_xact_lock(hashtextextended(p_owner || ':' || p_workspace,0));
      IF p_owner <> 'owner' OR p_workspace <> 'local' OR ds !~ '^candidate-[0-9a-f-]{36}$'
        OR length(p_hash)<>64 OR length(p_key) NOT BETWEEN 1 AND 200 THEN
        RAISE EXCEPTION 'INVALID_SCOPE';
      END IF;
      IF NOT EXISTS(SELECT 1 FROM public.studio_candidates WHERE id=parent AND owner_id=p_owner AND workspace_id=p_workspace) THEN
        RAISE EXCEPTION 'INVALID_SCOPE';
      END IF;
      IF (SELECT count(*) FROM public.studio_candidates WHERE owner_id=p_owner AND workspace_id=p_workspace)>=20 THEN
        RAISE EXCEPTION 'LIMIT_REACHED';
      END IF;
      IF jsonb_array_length(p_validation->'hard_errors')<>0 OR p_validation->'hard_errors' IS NULL THEN
        RAISE EXCEPTION 'VALIDATION_FAILED';
      END IF;
      IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_proposal->'operations') o WHERE o->>'kind'='adapt_industry') THEN
        IF jsonb_array_length(p_proposal->'operations')<>1 OR jsonb_array_length(p_proposal->'selection'->'record_ids')<>0
           OR COALESCE(p_proposal->'selection'->'filters','{}'::jsonb)<>'{}'::jsonb OR p_proposal->'selection'->>'top_n' IS NOT NULL THEN RAISE EXCEPTION 'INVALID_SCOPE'; END IF;
        IF p_bundle->'manifest'->'presentation' IS DISTINCT FROM jsonb_build_object('industry',p_proposal->'operations'->0->'industry','page_titles',p_proposal->'operations'->0->'page_titles') THEN RAISE EXCEPTION 'Unauthorized presentation'; END IF;
      ELSE
        IF p_bundle->'manifest'->'presentation' IS DISTINCT FROM (SELECT presentation::jsonb FROM public.datasets WHERE id=parent) THEN RAISE EXCEPTION 'Unauthorized presentation'; END IF;
      END IF;
      INSERT INTO public.datasets SELECT * FROM jsonb_populate_record(NULL::public.datasets,p_bundle->'manifest');
      FOREACH tab IN ARRAY ARRAY['accounts','users','contacts','products','pricebooks','pricebook_entries','opportunities','opportunity_line_items','cases'] LOOP
        expected := jsonb_array_length(p_bundle->'tables'->tab);
        EXECUTE format('SELECT count(*) FROM public.%I WHERE dataset_id=$1',tab) INTO actual USING parent;
        IF expected IS NULL OR expected<>actual THEN RAISE EXCEPTION 'Row count changed'; END IF;
        FOR item IN SELECT value FROM jsonb_array_elements(p_bundle->'tables'->tab) LOOP
          IF item->>'dataset_id' IS DISTINCT FROM ds THEN RAISE EXCEPTION 'Wrong dataset'; END IF;
          EXECUTE format('SELECT count(*) FROM public.%I WHERE dataset_id=$1 AND id=$2',tab) INTO actual USING parent,item->>'id';
          IF actual<>1 THEN RAISE EXCEPTION 'Unknown business record'; END IF;
          EXECUTE format('SELECT to_jsonb(t) FROM public.%I t WHERE dataset_id=$1 AND id=$2',tab) INTO old_row USING parent,item->>'id';
          EXECUTE format('SELECT to_jsonb(t) FROM jsonb_populate_record(NULL::public.%I,$1) t',tab) INTO new_row USING item;
          allowed := ARRAY['dataset_id'];
          eligible := (p_proposal->'selection'->'record_ids') ? (CASE WHEN tab='opportunity_line_items' THEN item->>'opportunity_id' ELSE item->>'id' END);
          FOR operation IN SELECT value FROM jsonb_array_elements(p_proposal->'operations') LOOP
            IF operation->>'kind'='adapt_industry' THEN
              IF tab='accounts' THEN allowed := allowed || ARRAY['name','industry']; END IF;
              IF tab='products' THEN allowed := allowed || ARRAY['name','family']; END IF;
              IF tab='opportunities' THEN allowed := allowed || ARRAY['name']; END IF;
              IF tab='cases' THEN allowed := allowed || ARRAY['subject']; END IF;
              IF tab='pricebooks' THEN allowed := allowed || ARRAY['name','description']; END IF;
            ELSIF operation->>'kind'='refresh_dates' THEN
              IF tab='opportunities' THEN allowed := allowed || ARRAY['created_at','close_date']; END IF;
              IF tab='cases' THEN allowed := allowed || ARRAY['created_at','closed_date']; END IF;
            ELSIF eligible THEN
              IF operation->>'kind'='scale_line_prices' AND tab='opportunity_line_items' THEN allowed := allowed || ARRAY['unit_price']; END IF;
              IF operation->>'kind'='set_stage' AND tab='opportunities' THEN allowed := allowed || ARRAY['stage','probability','close_date']; END IF;
              IF operation->>'kind'='set_expected_close' AND tab='opportunities' THEN allowed := allowed || ARRAY['close_date']; END IF;
              IF operation->>'kind'='adjust_resolution' AND tab='cases' THEN allowed := allowed || ARRAY['closed_date']; END IF;
            END IF;
          END LOOP;
          IF (old_row - allowed) IS DISTINCT FROM (new_row - allowed) THEN RAISE EXCEPTION 'Unauthorized field change'; END IF;
        END LOOP;
        EXECUTE format('INSERT INTO public.%I SELECT * FROM jsonb_populate_recordset(NULL::public.%I,$1)',tab,tab)
          USING p_bundle->'tables'->tab;
      END LOOP;
      INSERT INTO public.studio_candidates(id,owner_id,workspace_id,parent_id,revision,content_hash,status,proposal,validation)
        VALUES(ds,p_owner,p_workspace,parent,(p_bundle->'manifest'->>'revision')::integer,p_hash,'preview',p_proposal,p_validation);
      UPDATE public.studio_approvals SET valid=false WHERE owner_id=p_owner AND workspace_id=p_workspace AND valid;
      INSERT INTO public.studio_receipts VALUES(p_owner,p_workspace,'candidate',p_key,p_request_hash,jsonb_build_object('id',ds));
    END $$;
    REVOKE ALL ON FUNCTION studio_publish(text,text,jsonb,text,text,jsonb,text,jsonb) FROM PUBLIC;
    ''')
def downgrade():raise RuntimeError('Industry revision history is retained')
