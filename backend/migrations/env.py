from alembic import context
from app.db import engine,metadata
with engine(admin=True).connect() as connection:
    context.configure(connection=connection,target_metadata=metadata)
    with context.begin_transaction(): context.run_migrations()
