from alembic import op
from app.db import metadata
revision='001'
down_revision=None

def upgrade():
    metadata.create_all(op.get_bind())
    for table,fields in {'opportunities':['account_id','owner_id','created_at','close_date'],'cases':['account_id','owner_id','created_at','closed_date'],'opportunity_line_items':['opportunity_id','pricebook_entry_id']}.items():
        for field in fields: op.create_index(f'ix_{table}_{field}',table,['dataset_id',field])
def downgrade(): metadata.drop_all(op.get_bind())
