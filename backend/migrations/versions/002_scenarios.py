"""Protected revision metadata; privileged functions are granted explicitly at setup."""
from alembic import op
revision = '002'
down_revision = '001'


def upgrade():
    op.execute('''
    CREATE TABLE studio_candidates (
      id text PRIMARY KEY REFERENCES datasets(id), owner_id text NOT NULL, workspace_id text NOT NULL,
      parent_id text REFERENCES studio_candidates(id), revision integer NOT NULL CHECK(revision > 0),
      content_hash text NOT NULL, status text NOT NULL CHECK(status IN ('baseline','preview','rejected','applied')),
      proposal jsonb NOT NULL DEFAULT '{}', validation jsonb NOT NULL DEFAULT '{}',
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(owner_id,workspace_id,parent_id,revision), UNIQUE(owner_id,workspace_id,id)
    );
    CREATE TABLE studio_active (
      owner_id text NOT NULL, workspace_id text NOT NULL, dataset_id text NOT NULL,
      PRIMARY KEY(owner_id,workspace_id),
      FOREIGN KEY(owner_id,workspace_id,dataset_id) REFERENCES studio_candidates(owner_id,workspace_id,id)
    );
    CREATE TABLE studio_runs (
      id text PRIMARY KEY, owner_id text NOT NULL, workspace_id text NOT NULL,
      parent_id text NOT NULL REFERENCES datasets(id), brief text NOT NULL,
      status text NOT NULL, version integer NOT NULL DEFAULT 1,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE studio_reviews (
      id text PRIMARY KEY, candidate_id text NOT NULL REFERENCES studio_candidates(id),
      owner_id text NOT NULL, kind text NOT NULL, actor text NOT NULL,
      target text NOT NULL, reason text NOT NULL DEFAULT '', content_hash text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE studio_approvals (
      id text PRIMARY KEY, candidate_id text NOT NULL REFERENCES studio_candidates(id),
      owner_id text NOT NULL, workspace_id text NOT NULL, content_hash text NOT NULL,
      expected_active_id text NOT NULL REFERENCES datasets(id), semantic_version text NOT NULL,
      valid boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE studio_activations (
      id text PRIMARY KEY, owner_id text NOT NULL, workspace_id text NOT NULL,
      active_id text NOT NULL REFERENCES datasets(id), prior_id text NOT NULL REFERENCES datasets(id),
      approval_id text REFERENCES studio_approvals(id), recovery boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE studio_receipts (
      owner_id text NOT NULL, workspace_id text NOT NULL, action text NOT NULL,
      key text NOT NULL, request_hash text NOT NULL, result jsonb NOT NULL,
      PRIMARY KEY(owner_id,workspace_id,action,key)
    );
    REVOKE ALL ON studio_candidates, studio_active, studio_runs, studio_reviews,
      studio_approvals, studio_activations, studio_receipts FROM PUBLIC;
    CREATE FUNCTION studio_initialize(p_owner text, p_workspace text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    DECLARE base public.datasets%ROWTYPE;
    BEGIN
      IF p_owner <> 'owner' OR p_workspace <> 'local' THEN
        RAISE EXCEPTION 'Unsupported local owner/workspace';
      END IF;
      SELECT * INTO STRICT base FROM public.datasets WHERE id='baseline-v1-42-2026-10-21';
      INSERT INTO public.studio_candidates(id,owner_id,workspace_id,parent_id,revision,content_hash,status)
        VALUES(base.id,p_owner,p_workspace,NULL,1,md5(base.checksums::text),'baseline')
        ON CONFLICT(id) DO NOTHING;
      INSERT INTO public.studio_active VALUES(p_owner,p_workspace,base.id)
        ON CONFLICT(owner_id,workspace_id) DO NOTHING;
    END $$;
    REVOKE ALL ON FUNCTION studio_initialize(text,text) FROM PUBLIC;
    ''')

    op.execute('''
    CREATE FUNCTION studio_publish(p_owner text,p_workspace text,p_bundle jsonb,p_hash text,
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
            IF operation->>'kind'='refresh_dates' THEN
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

    op.execute('''
    CREATE FUNCTION studio_lifecycle(p_owner text,p_workspace text,p_action text,p jsonb) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE current_id text; s public.studio_candidates%ROWTYPE; a public.studio_approvals%ROWTYPE;
      result jsonb; receipt public.studio_receipts%ROWTYPE; target text; expected text; request_hash text;
    BEGIN
      IF p_owner<>'owner' OR p_workspace<>'local' THEN RAISE EXCEPTION 'INVALID_SCOPE'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(p_owner || ':' || p_workspace,0));
      SELECT dataset_id INTO STRICT current_id FROM public.studio_active WHERE owner_id=p_owner AND workspace_id=p_workspace FOR UPDATE;
      IF p_action IN ('approve','review') THEN
        SELECT * INTO s FROM public.studio_candidates WHERE id=p->>'candidate_id' AND owner_id=p_owner AND workspace_id=p_workspace;
        IF NOT FOUND THEN RAISE EXCEPTION 'INVALID_SCOPE'; END IF;
      END IF;
      IF p_action='review' THEN
        IF p->'event'->>'actor'<>p_owner OR p->'event'->>'kind' NOT IN ('reject','edit','annotate','override','clarify','retry') THEN RAISE EXCEPTION 'INVALID_SCOPE'; END IF;
        IF p->'event'->>'kind'='override' AND length(trim(p->'event'->>'reason'))=0 THEN RAISE EXCEPTION 'VALIDATION_FAILED'; END IF;
        INSERT INTO public.studio_reviews(id,candidate_id,owner_id,kind,actor,target,reason,content_hash)
          VALUES(p->>'id',s.id,p_owner,p->'event'->>'kind',p_owner,p->'event'->>'target',p->'event'->>'reason',s.content_hash);
        IF p->'event'->>'kind' IN ('reject','edit') OR (p->'event'->>'changes_requested')::boolean THEN
          UPDATE public.studio_approvals SET valid=false WHERE candidate_id=s.id;
        END IF;
        IF p->'event'->>'kind'='reject' AND s.status='preview' THEN UPDATE public.studio_candidates SET status='rejected' WHERE id=s.id; END IF;
        RETURN jsonb_build_object('id',p->>'id','candidate_id',s.id,'kind',p->'event'->>'kind');
      ELSIF p_action='approve' THEN
        IF current_id<>p->>'expected_active_id' OR s.content_hash<>p->>'content_hash' THEN RAISE EXCEPTION 'STALE_VERSION'; END IF;
        IF s.status<>'preview' OR jsonb_array_length(s.validation->'hard_errors')<>0 OR s.validation->'hard_errors' IS NULL THEN RAISE EXCEPTION 'VALIDATION_FAILED'; END IF;
        IF jsonb_array_length(s.validation->'warnings')>0 AND NOT EXISTS(SELECT 1 FROM public.studio_reviews r WHERE r.candidate_id=s.id AND r.kind='override' AND r.target='warnings' AND length(trim(r.reason))>0) THEN RAISE EXCEPTION 'VALIDATION_FAILED'; END IF;
        INSERT INTO public.studio_approvals(id,candidate_id,owner_id,workspace_id,content_hash,expected_active_id,semantic_version)
          SELECT p->>'id',s.id,p_owner,p_workspace,s.content_hash,current_id,semantic_version FROM public.datasets WHERE id=s.id;
        RETURN jsonb_build_object('id',p->>'id','candidate_id',s.id,'content_hash',s.content_hash,'expected_active_id',current_id);
      ELSIF p_action IN ('apply','recover') THEN
        IF length(p->>'key') NOT BETWEEN 1 AND 200 OR p->>'key' IS NULL THEN RAISE EXCEPTION 'INVALID_SCOPE'; END IF;
        request_hash := CASE WHEN p_action='apply' THEN p->>'approval_id' ELSE (p->>'target_id') || ':' || (p->>'expected_active_id') END;
        SELECT * INTO receipt FROM public.studio_receipts WHERE owner_id=p_owner AND workspace_id=p_workspace AND action=p_action AND key=p->>'key';
        IF FOUND THEN
          IF receipt.request_hash<>request_hash THEN RAISE EXCEPTION 'INVALID_SCOPE'; END IF;
          RETURN receipt.result;
        END IF;
        IF p_action='apply' THEN
          SELECT * INTO a FROM public.studio_approvals WHERE id=p->>'approval_id' AND owner_id=p_owner AND workspace_id=p_workspace;
          IF NOT FOUND OR NOT a.valid THEN RAISE EXCEPTION 'APPROVAL_REQUIRED'; END IF;
          SELECT * INTO STRICT s FROM public.studio_candidates WHERE id=a.candidate_id;
          IF a.content_hash<>s.content_hash OR (SELECT semantic_version FROM public.datasets WHERE id=s.id)<>a.semantic_version OR s.status<>'preview' OR jsonb_array_length(s.validation->'hard_errors')<>0 THEN RAISE EXCEPTION 'VALIDATION_FAILED'; END IF;
          target:=s.id;expected:=a.expected_active_id;
        ELSE
          target:=p->>'target_id';expected:=p->>'expected_active_id';
          IF NOT EXISTS(SELECT 1 FROM public.studio_candidates WHERE id=target AND owner_id=p_owner AND workspace_id=p_workspace AND (status='baseline' OR EXISTS(SELECT 1 FROM public.studio_activations WHERE active_id=target AND owner_id=p_owner AND workspace_id=p_workspace))) THEN RAISE EXCEPTION 'INVALID_SCOPE'; END IF;
        END IF;
        IF current_id<>expected THEN RAISE EXCEPTION 'STALE_VERSION'; END IF;
        UPDATE public.studio_active SET dataset_id=target WHERE owner_id=p_owner AND workspace_id=p_workspace AND dataset_id=expected;
        IF p_action='apply' THEN
          UPDATE public.studio_candidates SET status='applied' WHERE id=target;
          UPDATE public.studio_approvals SET valid=false WHERE id=a.id;
        END IF;
        INSERT INTO public.studio_activations(id,owner_id,workspace_id,active_id,prior_id,approval_id,recovery)
          VALUES(p->>'id',p_owner,p_workspace,target,current_id,CASE WHEN p_action='apply' THEN a.id ELSE NULL END,p_action='recover');
        result:=jsonb_build_object('id',p->>'id','active_id',target,'prior_id',current_id);
        INSERT INTO public.studio_receipts VALUES(p_owner,p_workspace,p_action,p->>'key',request_hash,result);
        RETURN result;
      END IF;
      RAISE EXCEPTION 'UNSUPPORTED_OPERATION';
    END $$;
    REVOKE ALL ON FUNCTION studio_lifecycle(text,text,text,jsonb) FROM PUBLIC;
    ''')


def downgrade():
    raise RuntimeError('Scenario history requires an explicit retention decision; automatic downgrade disabled')
