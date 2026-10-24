"""Credit authority and confirmed memory metadata (no business records)."""
from alembic import op
revision='003'
down_revision='002'


def upgrade():
    op.execute('''
    CREATE TABLE studio_credit (
      provider text PRIMARY KEY CHECK(provider IN ('nebius','fireworks')),
      model text NOT NULL, balance numeric(20,10) NOT NULL CHECK(balance>=0),
      credit_only boolean NOT NULL DEFAULT false, verified_until timestamptz NOT NULL,
      input_rate numeric(20,10) NOT NULL CHECK(input_rate>=0),
      output_rate numeric(20,10) NOT NULL CHECK(output_rate>=0)
    );
    CREATE TABLE studio_reservations (
      id text PRIMARY KEY, owner_id text NOT NULL, workspace_id text NOT NULL, run_id text NOT NULL,
      provider text NOT NULL REFERENCES studio_credit(provider), model text NOT NULL,
      input_tokens integer NOT NULL, output_tokens integer NOT NULL,
      input_rate numeric(20,10) NOT NULL, output_rate numeric(20,10) NOT NULL,
      reserved numeric(20,10) NOT NULL, actual numeric(20,10), usage jsonb,
      status text NOT NULL DEFAULT 'reserved', created_at timestamptz NOT NULL DEFAULT now()
    );
    REVOKE ALL ON studio_credit,studio_reservations FROM PUBLIC;
    CREATE FUNCTION studio_reserve(p_owner text,p_workspace text,p_run text,p jsonb) RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE credit public.studio_credit%ROWTYPE; amount numeric; spent numeric; n integer;
    BEGIN
      IF p_owner<>'owner' OR p_workspace<>'local' THEN RAISE EXCEPTION 'BUDGET_UNAVAILABLE'; END IF;
      PERFORM pg_advisory_xact_lock(61820261022);
      SELECT * INTO credit FROM public.studio_credit WHERE provider=p->>'provider' FOR UPDATE;
      IF NOT FOUND OR NOT credit.credit_only OR credit.verified_until<=now() OR credit.model<>p->>'model' THEN RAISE EXCEPTION 'BUDGET_UNAVAILABLE'; END IF;
      IF (p->>'input_tokens')::integer NOT BETWEEN 1 AND 8000 OR (p->>'output_tokens')::integer NOT BETWEEN 1 AND 1000 THEN RAISE EXCEPTION 'LIMIT_REACHED'; END IF;
      SELECT count(*) INTO n FROM public.studio_reservations WHERE owner_id=p_owner AND workspace_id=p_workspace AND run_id=p_run;
      IF n>=6 THEN RAISE EXCEPTION 'LIMIT_REACHED'; END IF;
      amount:=((p->>'input_tokens')::integer*credit.input_rate+(p->>'output_tokens')::integer*credit.output_rate)/1000000;
      IF credit.balance<=0 OR amount>credit.balance THEN RAISE EXCEPTION 'BUDGET_UNAVAILABLE'; END IF;
      -- Owner-authorized cumulative project ceiling; credit refreshes never reset spend.
      SELECT coalesce(sum(CASE WHEN status='settled' THEN actual ELSE reserved END),0)
        INTO spent FROM public.studio_reservations
        WHERE owner_id=p_owner AND workspace_id=p_workspace AND provider=credit.provider;
      IF credit.provider='nebius' AND spent+amount>10 THEN RAISE EXCEPTION 'LIMIT_REACHED'; END IF;
      UPDATE public.studio_credit SET balance=balance-amount WHERE provider=credit.provider;
      INSERT INTO public.studio_reservations(id,owner_id,workspace_id,run_id,provider,model,input_tokens,output_tokens,input_rate,output_rate,reserved)
        VALUES(p->>'id',p_owner,p_workspace,p_run,credit.provider,credit.model,(p->>'input_tokens')::integer,(p->>'output_tokens')::integer,credit.input_rate,credit.output_rate,amount);
      RETURN p->>'id';
    END $$;
    REVOKE ALL ON FUNCTION studio_reserve(text,text,text,jsonb) FROM PUBLIC;
    CREATE FUNCTION studio_settle(p_id text,p_usage jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE r public.studio_reservations%ROWTYPE; amount numeric;
    BEGIN
      PERFORM pg_advisory_xact_lock(61820261022);
      SELECT * INTO STRICT r FROM public.studio_reservations WHERE id=p_id FOR UPDATE;
      IF r.status='settled' THEN RETURN; END IF;
      IF p_usage IS NULL THEN UPDATE public.studio_reservations SET status='unknown' WHERE id=p_id; RETURN; END IF;
      IF (p_usage->>'input_tokens')::integer<0 OR (p_usage->>'output_tokens')::integer<0 THEN RAISE EXCEPTION 'Invalid usage'; END IF;
      amount:=((p_usage->>'input_tokens')::integer*r.input_rate+(p_usage->>'output_tokens')::integer*r.output_rate)/1000000;
      IF amount IS NULL THEN RAISE EXCEPTION 'Invalid usage'; END IF;
      UPDATE public.studio_credit SET balance=greatest(0,balance+r.reserved-amount),
        credit_only=credit_only AND amount<=r.reserved WHERE provider=r.provider;
      UPDATE public.studio_reservations SET actual=amount,usage=p_usage,status='settled' WHERE id=p_id;
    END $$;
    REVOKE ALL ON FUNCTION studio_settle(text,jsonb) FROM PUBLIC;
    CREATE TABLE studio_memories (
      id text PRIMARY KEY,owner_id text NOT NULL,workspace_id text NOT NULL,draft jsonb NOT NULL,
      content_hash text NOT NULL,correlation text NOT NULL UNIQUE,provider_id text,
      status text NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE studio_outcomes (
      owner_id text NOT NULL,workspace_id text NOT NULL,revision_id text NOT NULL REFERENCES studio_candidates(id),
      successful boolean NOT NULL,PRIMARY KEY(owner_id,workspace_id,revision_id)
    );
    CREATE TABLE studio_memory_allowance (
      id integer PRIMARY KEY CHECK(id=1),writes integer NOT NULL CHECK(writes>=0),reads integer NOT NULL CHECK(reads>=0),
      credit_only boolean NOT NULL DEFAULT false,verified_until timestamptz NOT NULL
    );
    REVOKE ALL ON studio_memories,studio_outcomes,studio_memory_allowance FROM PUBLIC;
    CREATE FUNCTION studio_memory(o text,w text,a text,p jsonb) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE m public.studio_memories%ROWTYPE; allowance public.studio_memory_allowance%ROWTYPE;
    BEGIN
      IF o<>'owner' OR w<>'local' THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
      PERFORM pg_advisory_xact_lock(61820261024);
      IF a='quota' THEN
        SELECT * INTO allowance FROM public.studio_memory_allowance WHERE id=1 FOR UPDATE;
        IF NOT FOUND OR NOT allowance.credit_only OR allowance.verified_until<=now() THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
        IF p->>'kind'='read' AND allowance.reads>0 THEN
          UPDATE public.studio_memory_allowance SET reads=reads-1 WHERE id=1;
        ELSIF p->>'kind'='write' AND allowance.writes>0 THEN
          UPDATE public.studio_memory_allowance SET writes=writes-1 WHERE id=1;
        ELSE RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
        RETURN '{}'::jsonb;
      END IF;
      IF a='outcome' THEN
        IF NOT EXISTS(SELECT 1 FROM public.studio_candidates WHERE id=p->>'revision' AND owner_id=o AND workspace_id=w AND status='applied') THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
        INSERT INTO public.studio_outcomes VALUES(o,w,p->>'revision',(p->>'successful')::boolean)
          ON CONFLICT(owner_id,workspace_id,revision_id) DO UPDATE SET successful=excluded.successful;
        RETURN '{}'::jsonb;
      END IF;
      IF a IN ('propose','update') THEN
        IF p#>>'{draft,scope,owner_id}'<>o OR p#>>'{draft,scope,workspace_id}'<>w THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
        IF p#>>'{draft,kind}'='recipe' AND NOT EXISTS(SELECT 1 FROM public.studio_outcomes x JOIN public.studio_candidates c ON c.id=x.revision_id WHERE x.owner_id=o AND x.workspace_id=w AND x.revision_id=p#>>'{draft,source_revision_id}' AND x.successful AND c.status='applied') THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
      END IF;
      IF a='propose' THEN
        INSERT INTO public.studio_memories(id,owner_id,workspace_id,draft,content_hash,correlation,status)
          VALUES(p->>'id',o,w,p->'draft',p->>'hash',p->>'correlation','proposed');
      ELSE
        SELECT * INTO m FROM public.studio_memories WHERE id=p->>'id' AND owner_id=o AND workspace_id=w FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
        CASE a
        WHEN 'update' THEN
          IF m.status NOT IN ('proposed','confirmed','saved','failed') THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
          UPDATE public.studio_memories SET draft=p->'draft',content_hash=p->>'hash',correlation=p->>'correlation',status='proposed' WHERE id=m.id;
        WHEN 'confirm' THEN
          IF m.content_hash<>p->>'hash' OR m.status NOT IN ('proposed','confirmed') THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
          UPDATE public.studio_memories SET status='confirmed' WHERE id=m.id;
        WHEN 'saving' THEN
          IF m.status<>'confirmed' THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
          UPDATE public.studio_memories SET status='saving' WHERE id=m.id;
        WHEN 'result' THEN
          IF m.correlation<>p->>'correlation' OR m.status NOT IN ('saving','unknown','deletion-pending') OR p->>'status' NOT IN ('saved','unknown','failed') THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
          UPDATE public.studio_memories SET status=CASE WHEN m.status='deletion-pending' THEN m.status ELSE p->>'status' END,provider_id=coalesce(p->>'provider_id',provider_id) WHERE id=m.id;
        WHEN 'forget' THEN
          UPDATE public.studio_memories SET status=CASE WHEN status='deleted' OR (status IN ('proposed','confirmed') AND provider_id IS NULL) THEN 'deleted' ELSE 'deletion-pending' END WHERE id=m.id;
        WHEN 'deleted' THEN
          IF m.status<>'deletion-pending' THEN RAISE EXCEPTION 'MEMORY_UNAVAILABLE'; END IF;
          UPDATE public.studio_memories SET status='deleted' WHERE id=m.id;
        ELSE RAISE EXCEPTION 'MEMORY_UNAVAILABLE';
        END CASE;
      END IF;
      SELECT * INTO m FROM public.studio_memories WHERE id=p->>'id';
      RETURN jsonb_build_object('id',m.id,'provider_id',m.provider_id,'draft',m.draft,'content_hash',m.content_hash,'correlation',m.correlation,'status',m.status);
    END $$;
    REVOKE ALL ON FUNCTION studio_memory(text,text,text,jsonb) FROM PUBLIC;
    ''')


def downgrade():
    raise RuntimeError('Do not discard credit or memory audit history automatically')
