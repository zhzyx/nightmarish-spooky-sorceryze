"""Local JSONL/SQLite evidence ledger. No network, host authentication or approval service."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetry as tel

FIELDS = {
    'source': 'source_key authority_ref purpose retention allowed_fields',
    'feedback': 'source_key external_id source_revision occurred_at collected_at batch_id content original_ref context',
    'annotation': 'labels schema_version method reviewer uncertainty',
    'classification': 'taxonomy_version categories candidate_layer reason event_cluster',
    'analysis': 'question method sample findings counterevidence limitations target',
    'optimization': 'target_layer target problem proposed_change metrics validation_plan rollback owner_ref status',
    'reference': 'title statement applicability limitations review_after status',
}
PARENTS = {'feedback': {'source'}, 'annotation': {'feedback'},
           'classification': {'feedback', 'annotation'},
           'analysis': {'feedback', 'annotation', 'classification'},
           'optimization': {'analysis'}, 'reference': {'analysis'}}
FIELDS.update(tel.EVENT_FIELDS)
PARENTS['agent_snapshot']={'source'}
PARENTS['annotation'] |= set(tel.EVENT_FIELDS)-{'agent_snapshot'}
PARENTS['analysis'] |= {'step','message','direction_error','correction','quality_issue','rework','handoff','coverage'}
LAYERS = tel.LAYERS


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be a string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires a timezone')


def connect(db):
    # Existing DB only; init is explicit. SQLite URI quoting is avoided for Windows paths.
    if not Path(db).is_file():
        raise ValueError('Database missing; run init first')
    cx = sqlite3.connect(db, timeout=10)
    cx.execute('PRAGMA foreign_keys=ON')
    if cx.execute('PRAGMA user_version').fetchone()[0] != 2:
        cx.close()
        raise ValueError('Unsupported database schema')
    return cx


def initialize(db):
    if Path(db).exists():
        raise ValueError('Refusing to replace existing path')
    with closing(sqlite3.connect(db)) as cx:
        cx.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE records (
          tenant TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL,
          digest TEXT NOT NULL, document TEXT NOT NULL,
          source_key TEXT, external_id TEXT, source_revision TEXT, supersedes TEXT,
          PRIMARY KEY(tenant,id),
          UNIQUE(tenant,source_key,external_id,source_revision),
          UNIQUE(tenant,supersedes),
          FOREIGN KEY(tenant,supersedes) REFERENCES records(tenant,id)
        );
        CREATE TABLE evidence (
          tenant TEXT NOT NULL, child TEXT NOT NULL, parent TEXT NOT NULL,
          PRIMARY KEY(tenant,child,parent),
          FOREIGN KEY(tenant,child) REFERENCES records(tenant,id),
          FOREIGN KEY(tenant,parent) REFERENCES records(tenant,id)
        );
        CREATE INDEX evidence_parent ON evidence(tenant,parent);
        ''')
        cx.executescript(tel.DDL+'PRAGMA user_version=2;')
    return {'schema': 2, 'initialized': True, 'runtime_authority_granted': False}


def load_record(cx, tenant, rid):
    row = cx.execute('SELECT document FROM records WHERE tenant=? AND id=?', (tenant, rid)).fetchone()
    if not row:
        raise ValueError('Evidence or predecessor missing in this tenant: ' + rid)
    return json.loads(row[0])


def evidence_state(cx, tenant, rid, seen=None):
    seen = set() if seen is None else seen
    if rid in seen:
        return 'current'
    seen.add(rid)
    if cx.execute('SELECT 1 FROM records WHERE tenant=? AND supersedes=?', (tenant, rid)).fetchone():
        return 'superseded'
    doc=load_record(cx,tenant,rid)
    if doc.get('schema_version')==2 and doc['kind'] not in {'annotation','classification','analysis','optimization','reference'}:
        return 'current'
    for (parent,) in cx.execute('SELECT parent FROM evidence WHERE tenant=? AND child=?', (tenant, rid)):
        if evidence_state(cx, tenant, parent, seen) != 'current':
            return 'stale'
    return 'current'


def validate(cx, tenant, record):
    if not isinstance(record, dict):
        raise ValueError('Record must be an object')
    required = {'schema_version','record_id', 'tenant_id', 'kind', 'created_at', 'evidence_refs', 'payload'}
    if not required <= record.keys() or set(record) - required - {'supersedes','context'}:
        raise ValueError('Invalid record envelope')
    for field in ('record_id', 'tenant_id', 'kind'):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError('Invalid identifier: ' + field)
    if record['tenant_id'] != tenant:
        raise ValueError('Tenant mismatch')
    kind, payload = record['kind'], record['payload']
    if kind not in FIELDS or not isinstance(payload, dict):
        raise ValueError('Invalid kind or payload')
    for key in FIELDS[kind].split():
        if key not in payload or (payload[key] is None and key not in tel.NULLABLE) or payload[key] == '':
            raise ValueError('Missing payload field: ' + key)
    timestamp(record['created_at'])
    refs = record['evidence_refs']
    if not isinstance(refs, list) or any(not isinstance(r, str) or not r for r in refs) or len(refs) != len(set(refs)):
        raise ValueError('Evidence refs must be unique strings')
    parents = [load_record(cx, tenant, rid) for rid in refs]
    if kind in {'annotation','classification','analysis','optimization','reference'} and any(evidence_state(cx, tenant, rid) != 'current' for rid in refs):
        raise ValueError('New result uses superseded or stale evidence')
    if kind in PARENTS and not ({p['kind'] for p in parents} & PARENTS[kind]):
        raise ValueError('Required evidence kind missing')
    if kind == 'feedback':
        for key in ('source_key', 'external_id', 'source_revision'):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ValueError('Source identity must be a nonempty string')
        sources = [p for p in parents if p['kind'] == 'source']
        if len(sources) != 1 or sources[0]['payload']['source_key'] != payload['source_key']:
            raise ValueError('Feedback source mismatch')
        timestamp(payload['occurred_at']); timestamp(payload['collected_at'])
        if not isinstance(payload['context'], dict):
            raise ValueError('Context must be an object; retain unknowns explicitly')
    for key in ('labels', 'categories', 'allowed_fields'):
        if key in FIELDS[kind].split() and (not isinstance(payload[key], list) or not payload[key]):
            raise ValueError('Expected nonempty list: ' + key)
    if kind == 'annotation':
        for label in payload['labels']:
            if not isinstance(label, dict) or not {'name', 'value', 'evidence_span'} <= label.keys():
                raise ValueError('Label needs name, value and evidence_span')
    if kind in ('classification', 'optimization'):
        if payload['candidate_layer' if kind == 'classification' else 'target_layer'] not in LAYERS:
            raise ValueError('Unknown optimization layer')
    if kind in ('optimization', 'reference') and payload['status'] != 'proposed':
        raise ValueError('This ledger stores proposals, not adoption approvals')
    if kind == 'reference':
        datetime.strptime(payload['review_after'], '%Y-%m-%d')
    predecessor = record.get('supersedes')
    if predecessor is not None:
        if not isinstance(predecessor, str) or not predecessor:
            raise ValueError('Invalid predecessor')
        prior = load_record(cx, tenant, predecessor)
        if prior['kind'] != kind or evidence_state(cx, tenant, predecessor) == 'superseded':
            raise ValueError('Predecessor must be latest version of same kind')
    tel.validate(cx,tenant,record,load_record)


def ingest(db, tenant, records):
    cx = connect(db)
    inserted = repeated = 0
    try:
        cx.execute('BEGIN IMMEDIATE')
        for record in records:
            if not isinstance(record, dict) or record.get('tenant_id') != tenant:
                raise ValueError('Tenant mismatch or malformed record')
            doc = canonical(record)
            digest = hashlib.sha256(doc.encode()).hexdigest()
            previous = cx.execute('SELECT digest FROM records WHERE tenant=? AND id=?',
                                  (tenant, record.get('record_id'))).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError('Record ID conflict; append a correction instead')
                repeated += 1
                continue
            validate(cx, tenant, record)
            payload = record['payload']
            if record['kind']=='feedback':identity=[payload[k] for k in ('source_key','external_id','source_revision')]
            elif record['kind'] in tel.EVENT_FIELDS and record['kind']!='agent_snapshot':identity=[payload[k] for k in ('source_key','event_key','source_revision')]
            else:identity=[None]*3
            cx.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (tenant, record['record_id'], record['kind'], digest, doc, *identity, record.get('supersedes'),datetime.now(timezone.utc).isoformat()))
            cx.executemany('INSERT INTO evidence VALUES (?,?,?)',
                           [(tenant, record['record_id'], parent) for parent in record['evidence_refs']])
            tel.project(cx,tenant,record,load_record)
            inserted += 1
        cx.commit()
    except Exception:
        cx.rollback()
        raise
    finally:
        cx.close()
    return {'tenant_id': tenant, 'inserted': inserted, 'replayed': repeated, 'committed': True}


def query(db, tenant, kind=None, **filters):
    cx = connect(db)
    try:
        cx.execute('BEGIN')
        sql = 'SELECT r.id,r.document,r.ingested_at FROM records r WHERE r.tenant=?'
        args = [tenant]
        if kind:
            sql += ' AND r.kind=?'; args.append(kind)
        filters=dict(filters)
        if filters.get('step') is not None:
            step=load_record(cx,tenant,filters.pop('step'))
            if step['kind']!='step':raise ValueError('Step filter must reference a step record')
            if filters.get('step_key') is not None and filters['step_key']!=step['payload']['step_key']:raise ValueError('Conflicting step filters')
            filters['step_key']=step['payload']['step_key']
        else:filters.pop('step',None)
        agent_id,agent_version=filters.pop('agent_id',None),filters.pop('agent_version',None)
        if agent_id is not None or agent_version is not None:
            sql+=' AND EXISTS(SELECT 1 FROM agent_links a JOIN agent_catalog c ON c.tenant=a.tenant AND c.ref=a.agent_ref WHERE a.tenant=r.tenant AND a.id=r.id'
            for col,value in [('agent_id',agent_id),('version',agent_version)]:
                if value is not None:sql+=' AND c.'+col+'=?';args.append(value)
            sql+=')'
        for key,value in filters.items():
            if value is None:continue
            if key in {'request','project','step_key','since','until'}:
                column={'request':'request_ref','project':'project_id','step_key':'step_key','since':'occurred_at','until':'occurred_at'}[key]
                op='>=' if key=='since' else '<' if key=='until' else '='
                sql+=f' AND EXISTS(SELECT 1 FROM dimensions d WHERE d.tenant=r.tenant AND d.id=r.id AND d.{column}{op}?)'
                args.append(tel.utc(value) if key in {'since','until'} else value)
            elif key=='agent':
                sql+=' AND EXISTS(SELECT 1 FROM agent_links a WHERE a.tenant=r.tenant AND a.id=r.id AND a.agent_ref=?)';args.append(value)
            elif key=='work':
                sql+=' AND EXISTS(SELECT 1 FROM work_links w WHERE w.tenant=r.tenant AND w.id=r.id AND w.work_id=?)';args.append(value)
            elif key=='label':
                name,sep,val=value.partition('=')
                if not sep:raise ValueError('Label filter is name=value')
                sql+=' AND EXISTS(SELECT 1 FROM labels l WHERE l.tenant=r.tenant AND l.id=r.id AND l.name=? AND l.value=?)';args.extend([name,val])
            else:raise ValueError('Unsupported filter: '+key)
        rows = cx.execute(sql + ' ORDER BY r.rowid', args).fetchall()
        result=[]
        for rid,doc,ingested_at in rows:
            record=json.loads(doc)
            state=evidence_state(cx,tenant,rid)
            if state=='current' and record.get('schema_version')!=2:state='legacy_unmapped'
            d=cx.execute('SELECT project_id,request_ref,primary_agent_ref,step_ref,step_key,occurred_at FROM dimensions WHERE tenant=? AND id=?',(tenant,rid)).fetchone()
            result.append({'record':record,'evidence_state':state,'ingested_at':ingested_at,'dimensions':dict(zip(('project_id','request_ref','primary_agent_ref','step_ref','step_key','occurred_at'),d)) if d else {}})
        return result
    finally:
        cx.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    migrate=sub.add_parser('migrate');migrate.add_argument('--source-v1',required=True)
    imp = sub.add_parser('import'); imp.add_argument('--tenant', required=True); imp.add_argument('--input', required=True)
    for command in ('list','stats'):
        get=sub.add_parser(command);get.add_argument('--tenant',required=True);get.add_argument('--kind',choices=FIELDS)
        for field in ('request','project','step','step-key','agent','agent-id','agent-version','work','label','since','until'):get.add_argument('--'+field)
        if command=='stats':get.add_argument('--group-by',choices=['agent','request','project','step','day'],default='request')
    args = parser.parse_args()
    if args.command not in {'init','migrate'} and not args.tenant.strip():
        raise ValueError('Tenant required')
    if args.command == 'init':
        result = initialize(args.db)
    elif args.command=='migrate':
        result=migrate_v1(args.source_v1,args.db)
    elif args.command == 'import':
        def no_duplicates(pairs):
            obj = {}
            for k, v in pairs:
                if k in obj: raise ValueError('Duplicate JSON key: ' + k)
                obj[k] = v
            return obj
        with open(args.input, encoding='utf-8-sig') as stream:
            records = [json.loads(line, object_pairs_hook=no_duplicates) for line in stream if line.strip()]
        if not records: raise ValueError('Empty batch is not a collection receipt')
        result = ingest(args.db, args.tenant, records)
    else:
        filters={k:getattr(args,k) for k in ('request','project','step','step_key','agent','agent_id','agent_version','work','label','since','until')}
        result = query(args.db,args.tenant,args.kind,**filters)
        if args.command=='stats':
            snapshot=[{'record_id':i['record']['record_id'],'sha256':hashlib.sha256(canonical(i['record']).encode()).hexdigest(),'state':i['evidence_state']} for i in result]
            result=tel.summarize(result,args.group_by)
            result['query']={'tenant':args.tenant,'kind':args.kind,**filters}
            result['snapshot_at']=datetime.now().astimezone().isoformat()
            result['data_snapshot']={'sha256':hashlib.sha256(canonical(snapshot).encode()).hexdigest(),'records':snapshot}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


def migrate_v1(source,destination):
    if Path(destination).exists():raise ValueError('Migration destination must be new')
    src=Path(source).resolve()
    cx=sqlite3.connect(src.as_uri()+'?mode=ro',uri=True)
    target=None
    try:
        if cx.execute('PRAGMA user_version').fetchone()[0]!=1:raise ValueError('Expected v1 database')
        target=sqlite3.connect(destination);cx.backup(target)
        target.executescript(tel.DDL+'PRAGMA user_version=2;')
        count=target.execute('SELECT COUNT(*) FROM records').fetchone()[0]
        return {'schema':2,'legacy_unmapped':count,'source_unchanged':True,'automatic_attribution':False}
    finally:
        cx.close()
        if target is not None:target.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
