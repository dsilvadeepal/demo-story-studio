"""Create only this project's local PostgreSQL + credentials. Requires Docker and backend venv."""
import json,os,secrets,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local';LOCAL.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'backend'));os.environ['STUDIO_LOCAL']='1'
from app.auth import hash_password
from app.db import engine
from sqlalchemy import text

def private_file(name,value):
    p=LOCAL/name
    p.write_text(value);p.chmod(0o600)

def configure_scenario_access(c, reader_role='studio_reader', writer_role='studio_writer'):
    """Provision only the local single-owner control namespace; no runtime DDL."""
    quote = c.dialect.identifier_preparer.quote
    reader, writer = quote(reader_role), quote(writer_role)
    c.execute(text(f'GRANT USAGE ON SCHEMA public TO {reader}, {writer}'))
    c.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {reader}, {writer}'))
    c.execute(text(f'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM {writer}'))
    c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_reserve(text,text,text,jsonb),studio_settle(text,jsonb),studio_memory(text,text,text,jsonb),studio_run(text,text,text,jsonb),studio_ignore_memory(text,text,text,jsonb),studio_interrupt_queued(text,text,text) TO {writer}'))
    c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_archive_history(text,text,text,text) TO {writer}'))
    c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_lifecycle(text,text,text,jsonb) TO {writer}'))
    c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_publish(text,text,jsonb,text,text,jsonb,text,jsonb) TO {writer}'))
    c.execute(text("SELECT studio_initialize('owner','local')"))


def main():
    if not (LOCAL/'admin-url').exists():
        password=secrets.token_hex(24)
        private_file('postgres.env',f'POSTGRES_PASSWORD={password}\nPOSTGRES_DB=studio\n')
        private_file('admin-url',f'postgresql+psycopg://postgres:{password}@127.0.0.1:55439/studio')
    exists=subprocess.run(['docker','container','inspect','demo-story-studio-db'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if not exists:subprocess.run(['docker','run','-d','--name','demo-story-studio-db','--env-file',str(LOCAL/'postgres.env'),'-p','127.0.0.1:55439:5432','-v','demo-story-studio-pg:/var/lib/postgresql/data','postgres:17'],check=True,stdout=subprocess.DEVNULL)
    else:subprocess.run(['docker','start','demo-story-studio-db'],check=True,stdout=subprocess.DEVNULL)
    for attempt in range(30):
        try:
            with engine(admin=True).connect() as c:c.execute(text('SELECT 1'))
            break
        except Exception:
            if attempt==29:raise
            time.sleep(1)
    subprocess.run([str(ROOT/'backend/.venv/bin/alembic'),'upgrade','head'],cwd=ROOT/'backend',check=True)
    if not (LOCAL/'runtime-url').exists():
        password=secrets.token_hex(24)
        with engine(admin=True).begin() as c:
            c.execute(text("CREATE ROLE studio_reader LOGIN PASSWORD '"+password+"'"))
            c.execute(text('GRANT CONNECT ON DATABASE studio TO studio_reader'))
            c.execute(text('GRANT USAGE ON SCHEMA public TO studio_reader'))
            c.execute(text('GRANT SELECT ON ALL TABLES IN SCHEMA public TO studio_reader'))
            c.execute(text('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO studio_reader'))
        private_file('runtime-url',f'postgresql+psycopg://studio_reader:{password}@127.0.0.1:55439/studio')
    if not (LOCAL/'auth.json').exists():
        password=secrets.token_urlsafe(18);private_file('owner-password',password)
        private_file('auth.json',json.dumps({'OWNER_PASSWORD_HASH':hash_password(password),'SESSION_SECRET':secrets.token_hex(32)}))
    subprocess.run([str(ROOT/'backend/.venv/bin/python'),'-m','app.seed'],cwd=ROOT/'backend',check=True)
    if not (LOCAL/'writer-url').exists():
        password=secrets.token_hex(24)
        with engine(admin=True).begin() as c:
            if not c.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='studio_writer'")):
                c.execute(text("CREATE ROLE studio_writer LOGIN PASSWORD '"+password+"'"))
            else:
                raise RuntimeError('studio_writer exists without local credentials; reconcile explicitly')
        private_file('writer-url',f'postgresql+psycopg://studio_writer:{password}@127.0.0.1:55439/studio')
    with engine(admin=True).begin() as c:
        configure_scenario_access(c)
    from app.agent.runner import setup_checkpoints
    setup_checkpoints(engine(admin=True),"studio_writer")
    subprocess.run([str(ROOT/'backend/.venv/bin/python'),'-m','app.validate_seed'],cwd=ROOT/'backend',check=True)
    print('Local baseline ready. Owner password: .local/owner-password (never commit).')
if __name__=='__main__':main()
