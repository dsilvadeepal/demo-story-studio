import json
from sqlalchemy import select
from .db import engine,manifest,tables
from .seed import checksum

def validate(connection,dataset_id):
    m=connection.execute(select(manifest).where(manifest.c.id==dataset_id)).mappings().one(); errors=[]
    for name,t in tables.items():
        rows=[dict(r) for r in connection.execute(select(t).where(t.c.dataset_id==dataset_id)).mappings()]
        if len(rows)!=m['counts'][name]: errors.append(name+': count differs')
        # Normalize exact decimals to two places, same as PostgreSQL storage.
        if checksum(rows)!=m['checksums'][name]: errors.append(name+': checksum differs')
    return {'dataset_id':dataset_id,'valid':not errors,'errors':errors}
if __name__=='__main__':
    with engine().connect() as c:
        ds=c.execute(select(manifest.c.id)).scalars().first(); result=validate(c,ds)
    print(json.dumps(result)); raise SystemExit(0 if result['valid'] else 1)
