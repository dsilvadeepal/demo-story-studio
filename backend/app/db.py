"""PostgreSQL schema. Runtime engines never receive migration credentials."""
import os
from functools import lru_cache
from pathlib import Path
from sqlalchemy import (MetaData, Table, Column, String, Integer, Numeric, Date, DateTime, JSON, ForeignKeyConstraint, CheckConstraint, UniqueConstraint, create_engine)
ROOT=Path(__file__).resolve().parents[2]
metadata=MetaData(); tables={}
manifest=Table('datasets',metadata,Column('id',String,primary_key=True),Column('revision',Integer,nullable=False),Column('semantic_version',String,nullable=False),Column('as_of_date',Date,nullable=False),Column('seed',Integer,nullable=False),Column('generator_version',Integer,nullable=False),Column('counts',JSON,nullable=False),Column('checksums',JSON,nullable=False),Column('presentation',JSON,nullable=False,server_default='{}'))
def col(name,typ=String,nullable=False): return Column(name,typ,nullable=nullable)
def fk(field,target): return ForeignKeyConstraint(['dataset_id',field],[f'{target}.dataset_id',f'{target}.id'])
def table(name,*fields):
    t=Table(name,metadata,Column('dataset_id',String,primary_key=True),Column('id',String,primary_key=True),ForeignKeyConstraint(['dataset_id'],['datasets.id']),*fields)
    tables[name]=t
    return t
accounts=table('accounts',col('name'),col('type'),col('industry'))
users=table('users',col('first_name'),col('last_name'),col('department'),col('division'))
contacts=table('contacts',col('account_id'),col('first_name'),col('last_name'),col('title'),fk('account_id','accounts'),UniqueConstraint('dataset_id','id','account_id'))
products=table('products',col('name'),col('code'),col('family'))
pricebooks=table('pricebooks',col('name'),col('description'))
entries=table('pricebook_entries',col('product_id'),col('pricebook_id'),col('unit_price',Numeric(18,2)),fk('product_id','products'),fk('pricebook_id','pricebooks'),CheckConstraint('unit_price >= 0'))
opportunities=table('opportunities',col('name'),col('account_id'),col('owner_id'),col('type'),col('stage'),col('probability',Numeric(5,2)),col('created_at',DateTime(timezone=True)),col('close_date',DateTime(timezone=True)),fk('account_id','accounts'),fk('owner_id','users'),CheckConstraint('probability BETWEEN 0 AND 100'),CheckConstraint('close_date >= created_at'))
lines=table('opportunity_line_items',col('opportunity_id'),col('pricebook_entry_id'),col('unit_price',Numeric(18,2)),col('quantity',Numeric(12,2)),fk('opportunity_id','opportunities'),fk('pricebook_entry_id','pricebook_entries'),CheckConstraint('unit_price >= 0 AND quantity > 0'))
cases=table('cases',col('subject'),col('account_id',nullable=True),col('contact_id',nullable=True),col('owner_id'),col('priority'),col('status'),col('type'),col('origin'),col('created_at',DateTime(timezone=True)),col('closed_date',DateTime(timezone=True),nullable=True),fk('account_id','accounts'),fk('contact_id','contacts'),fk('owner_id','users'),ForeignKeyConstraint(['dataset_id','contact_id','account_id'],['contacts.dataset_id','contacts.id','contacts.account_id']),CheckConstraint('contact_id IS NULL OR account_id IS NOT NULL'),CheckConstraint('closed_date IS NULL OR closed_date >= created_at'),CheckConstraint("(status = 'Closed') = (closed_date IS NOT NULL)"))
@lru_cache
def engine(admin=False):
    key='MIGRATION_DATABASE_URL' if admin else 'APP_DATABASE_URL'
    url=os.getenv(key)
    if not url and os.getenv('STUDIO_LOCAL')=='1':
        path=ROOT/'.local'/('admin-url' if admin else 'runtime-url')
        if path.exists(): url=path.read_text().strip()
    if not url: raise RuntimeError(f'{key} must be configured')
    return create_engine(url,pool_pre_ping=True,pool_size=5,max_overflow=2,connect_args={'options':'-c statement_timeout=5000'})

@lru_cache
def writer_engine():
    """Runtime writer is explicit and never inherits migration credentials."""
    url = os.getenv('STUDIO_WRITER_DATABASE_URL')
    if not url:
        raise RuntimeError('STUDIO_WRITER_DATABASE_URL must be configured')
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=0,
                         hide_parameters=True, connect_args={'options': '-c statement_timeout=5000'})
