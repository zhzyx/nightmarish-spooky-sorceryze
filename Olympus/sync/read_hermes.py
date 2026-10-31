"""Export a tenant snapshot for Gonggong analysis without modifying Hermes data."""
import argparse, hashlib, json, sqlite3
from pathlib import Path
from contextlib import closing
from datetime import datetime, timezone

def export(db, tenant, out):
    db=Path(db).resolve();out=Path(out).resolve()
    if not tenant.strip() or not db.is_file(): raise ValueError('Existing database and tenant required')
    if out.exists(): raise ValueError('Export destination must be new')
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)) as cx:
        cx.execute('PRAGMA query_only=ON');cx.execute('BEGIN')
        if cx.execute('PRAGMA user_version').fetchone()[0]!=2: raise ValueError('Expected Hermes v2 ledger')
        rows=cx.execute('SELECT id,kind,digest,document FROM records WHERE tenant=? ORDER BY id',(tenant,)).fetchall()
        records=[]
        for rid,kind,digest,document in rows:
            parsed=json.loads(document)
            canonical=json.dumps(parsed,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
            if hashlib.sha256(canonical.encode()).hexdigest()!=digest: raise ValueError('Record checksum mismatch: '+rid)
            if parsed['tenant_id']!=tenant or parsed['record_id']!=rid or parsed['kind']!=kind: raise ValueError('Record identity mismatch')
            records.append({'id':rid,'kind':kind,'sha256':digest,'document':parsed})
        edges=[{'child':c,'parent':p} for c,p in cx.execute('SELECT child,parent FROM evidence WHERE tenant=? ORDER BY child,parent',(tenant,))]
        ids={r['id'] for r in records}
        if any(e['child'] not in ids or e['parent'] not in ids for e in edges): raise ValueError('Incomplete tenant evidence graph')
        cx.rollback()
    payload={'origin_framework':'olympus','consumer_framework':'gonggong','purpose':'optimization_analysis','tenant':tenant,'records':records,'evidence':edges}
    digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result={**payload,'snapshot_sha256':digest,'exported_at':datetime.now(timezone.utc).isoformat(),'coverage':'unknown','source_access':'read_only','host_identity_authenticated':False}
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    return {'records':len(records),'snapshot_sha256':digest,'source_modified':False,'output':str(out)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--tenant',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    try:print(json.dumps(export(a.db,a.tenant,a.out),ensure_ascii=False))
    except (ValueError,OSError,sqlite3.Error,KeyError) as e:p.exit(1,str(e)+'\n')
