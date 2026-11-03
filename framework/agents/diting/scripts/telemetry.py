"""Diting v2 event validation, relational projections and measured-only summaries."""
from datetime import datetime, timezone
import math
import re

EVENT_FIELDS = {
 'agent_snapshot': 'agent_id version definition_digest definition_ref origin role_kind',
 'request': 'request_key project_id initiated_at intent source_key event_key source_revision',
 'request_end': 'status occurred_at source_key event_key source_revision',
 'step': 'step_key phase started_at ended_at duration_ms status attempt trace_id span_id parent_step_ref usage source_key event_key source_revision',
 'message': 'conversation_id message_id turn_id role visibility content_ref step_ref occurred_at source_key event_key source_revision',
 'direction_error': 'error_id expected actual issue_ref step_ref occurred_at source_key event_key source_revision',
 'correction': 'error_ref action resolution step_ref occurred_at source_key event_key source_revision',
 'quality_issue': 'issue_id issue_ref severity step_ref occurred_at source_key event_key source_revision',
 'rework': 'issue_ref action step_ref occurred_at source_key event_key source_revision',
 'handoff': 'from_agent_ref to_agent_ref communication_ref step_ref occurred_at source_key event_key source_revision',
 'coverage': 'category state observed expected reason window_start window_end source_key event_key source_revision',
}
TOKENS = ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens','reasoning_output_tokens')
NULLABLE = {'ended_at','duration_ms','parent_step_ref','step_ref','expected','observed'}
LAYERS = {'feature','project','module','agent','framework','yuanheng','unknown'}
DDL = '''
ALTER TABLE records ADD COLUMN ingested_at TEXT;
CREATE TABLE agent_catalog (tenant TEXT NOT NULL,ref TEXT NOT NULL,agent_id TEXT NOT NULL,
 version TEXT NOT NULL,digest TEXT NOT NULL,origin TEXT NOT NULL,role_kind TEXT NOT NULL,
 PRIMARY KEY(tenant,ref), FOREIGN KEY(tenant,ref) REFERENCES records(tenant,id));
CREATE INDEX by_agent_version ON agent_catalog(tenant,agent_id,version);
CREATE TABLE dimensions (
 tenant TEXT NOT NULL, id TEXT NOT NULL, request_ref TEXT NOT NULL,
 project_id TEXT NOT NULL, primary_agent_ref TEXT NOT NULL, step_ref TEXT, step_key TEXT,
 occurred_at TEXT NOT NULL, kind TEXT NOT NULL,
 PRIMARY KEY(tenant,id), FOREIGN KEY(tenant,id) REFERENCES records(tenant,id),
 FOREIGN KEY(tenant,request_ref) REFERENCES records(tenant,id),
 FOREIGN KEY(tenant,primary_agent_ref) REFERENCES records(tenant,id),
 FOREIGN KEY(tenant,step_ref) REFERENCES records(tenant,id));
CREATE TABLE agent_links (tenant TEXT NOT NULL,id TEXT NOT NULL,agent_ref TEXT NOT NULL,
 PRIMARY KEY(tenant,id,agent_ref), FOREIGN KEY(tenant,id) REFERENCES records(tenant,id),
 FOREIGN KEY(tenant,agent_ref) REFERENCES records(tenant,id));
CREATE TABLE work_links (tenant TEXT NOT NULL,id TEXT NOT NULL,work_id TEXT NOT NULL,
 work_kind TEXT NOT NULL,relation TEXT NOT NULL,certainty TEXT NOT NULL,
 PRIMARY KEY(tenant,id,work_id,relation), FOREIGN KEY(tenant,id) REFERENCES records(tenant,id));
CREATE TABLE labels (tenant TEXT NOT NULL,id TEXT NOT NULL,name TEXT NOT NULL,value TEXT NOT NULL,
 PRIMARY KEY(tenant,id,name,value), FOREIGN KEY(tenant,id) REFERENCES records(tenant,id));
CREATE TABLE logical_keys (tenant TEXT NOT NULL,kind TEXT NOT NULL,key TEXT NOT NULL,id TEXT NOT NULL,
 PRIMARY KEY(tenant,kind,key), FOREIGN KEY(tenant,id) REFERENCES records(tenant,id));
CREATE INDEX by_request ON dimensions(tenant,request_ref,occurred_at);
CREATE INDEX by_project ON dimensions(tenant,project_id,occurred_at);
CREATE INDEX by_agent ON agent_links(tenant,agent_ref,id);
CREATE INDEX by_work ON work_links(tenant,work_id,certainty,id);
CREATE INDEX by_label ON labels(tenant,name,value,id);
CREATE INDEX by_step ON dimensions(tenant,step_ref,occurred_at);
CREATE INDEX by_logical_step ON dimensions(tenant,step_key,occurred_at);
CREATE INDEX by_kind_time ON dimensions(tenant,kind,occurred_at);
'''

def nonempty(value, name):
    if not isinstance(value,str) or not value.strip():raise ValueError('Nonempty string required: '+name)

def utc(value):
    if not isinstance(value,str):raise ValueError('Timestamp must be text')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Timezone required')
    return dt.astimezone(timezone.utc).isoformat(timespec='microseconds')

def number(value, name, integer=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (integer and not isinstance(value,int)):
        raise ValueError('Invalid nonnegative number: '+name)

def typed(cx,tenant,rid,kinds,load):
    nonempty(rid,'reference');record=load(cx,tenant,rid)
    if record['kind'] not in kinds:raise ValueError('Wrong reference kind: '+rid)
    return record

def measurement(value,integer=False):
    if not isinstance(value,dict) or not {'value','status','reason','method'}<=value.keys():raise ValueError('Measurement envelope missing')
    if value['status'] not in {'measured','estimated','unavailable','not_applicable'}:raise ValueError('Invalid measurement status')
    if value['status'] in {'unavailable','not_applicable'}:
        if value['value'] is not None:raise ValueError('Unknown/not-applicable value must be null')
        nonempty(value['reason'],'measurement reason')
    else:
        number(value['value'],'measurement',integer)
        nonempty(value['method'],'measurement method')

def keys(record):
    p=record['payload'];kind=record['kind'];out=[]
    if kind=='agent_snapshot':out=[('snapshot',p['agent_id']+'@'+p['version']+'#'+p['definition_digest'])]
    if kind=='request':out=[('request',p['request_key'])]
    if kind=='step':out=[('step',p['step_key']),('usage',p['usage']['usage_key'])]
    if kind=='message':out=[('message',p['conversation_id']+'\0'+p['message_id'])]
    if kind=='request_end':out=[('request_end',record['context']['request_ref'])]
    if kind=='direction_error':out=[('direction_error',p['error_id'])]
    if kind=='quality_issue':out=[('quality_issue',p['issue_id'])]
    return out

def validate(cx,tenant,r,load):
    if r.get('schema_version')!=2:raise ValueError('New records require schema_version=2; legacy requires explicit migration')
    kind,p=r['kind'],r['payload']
    if kind in EVENT_FIELDS:
        for field in EVENT_FIELDS[kind].split():
            if field not in p:raise ValueError('Missing event field: '+field)
            if p[field] is None and field not in NULLABLE:raise ValueError('Null required field: '+field)
    if kind=='agent_snapshot':
        for k in ('agent_id','version','definition_ref'):nonempty(p[k],k)
        if not re.fullmatch('[a-f0-9]{64}',p['definition_digest']):raise ValueError('Invalid Agent digest')
        if p['origin'] not in {'registered','generated','external'} or p['role_kind'] not in {'subagent','framework','governance'}:raise ValueError('Invalid Agent snapshot origin/role')
        if not r['evidence_refs']:raise ValueError('Agent snapshot needs source evidence')
    if kind in {'source','agent_snapshot'}:
        if 'context' in r:raise ValueError('Source/snapshot are dimensions, not request facts')
    else:
        c=r.get('context')
        if not isinstance(c,dict) or not {'request_ref','primary_agent_ref','related_agent_refs','work_items','linkage_state','linkage_note'}<=c.keys():raise ValueError('Complete work context required')
        for k in ('request_ref','primary_agent_ref','linkage_note'):nonempty(c[k],k)
        if c['linkage_state'] not in {'complete','partial','unknown'}:raise ValueError('Invalid linkage state')
        related=c['related_agent_refs']
        if not isinstance(related,list) or any(not isinstance(x,str) for x in related) or len(set(related))!=len(related) or c['primary_agent_ref'] in related:raise ValueError('Invalid related Agent refs')
        for ref in [c['primary_agent_ref'],*related]:typed(cx,tenant,ref,{'agent_snapshot'},load)
        if kind=='request':
            if c['request_ref']!=r['record_id']:raise ValueError('Request context must point to itself')
            for k in ('request_key','project_id','intent'):nonempty(p[k],k)
            utc(p['initiated_at'])
            if r.get('supersedes'):raise ValueError('Request identity is immutable; record subsequent changes as events')
        else:typed(cx,tenant,c['request_ref'],{'request'},load)
        if kind=='request_end' and utc(p['occurred_at'])<utc(load(cx,tenant,c['request_ref'])['payload']['initiated_at']):raise ValueError('Request end before initiation')
        if not isinstance(c['work_items'],list):raise ValueError('Work items must be list')
        if not c['work_items'] and c['linkage_state']=='complete':raise ValueError('No work links cannot be complete')
        workkeys=[]
        for w in c['work_items']:
            if not isinstance(w,dict) or not {'id','kind','relation','certainty'}<=w.keys():raise ValueError('Work link fields missing')
            for k in ('id','kind','relation'):nonempty(w[k],k)
            if w['certainty'] not in {'confirmed','possible','unknown'}:raise ValueError('Invalid link certainty')
            workkeys.append((w['id'],w['relation']))
        if len(workkeys)!=len(set(workkeys)):raise ValueError('Duplicate work link')
        if kind in EVENT_FIELDS:
            for k in ('source_key','event_key','source_revision'):nonempty(p[k],k)
            sources=[load(cx,tenant,x) for x in r['evidence_refs'] if load(cx,tenant,x)['kind']=='source']
            if not any(s['payload']['source_key']==p['source_key'] for s in sources):raise ValueError('Event source evidence missing')
        if 'occurred_at' in p:utc(p['occurred_at'])
        refs=[]
        if p.get('step_ref'):refs.append((p['step_ref'],{'step'}))
        if kind=='step' and p.get('parent_step_ref'):refs.append((p['parent_step_ref'],{'step'}))
        if kind=='correction':refs.append((p['error_ref'],{'direction_error'}))
        if kind=='rework':refs.append((p['issue_ref'],{'quality_issue'}))
        for ref,kinds in refs:
            linked=typed(cx,tenant,ref,kinds,load)
            if linked['context']['request_ref']!=c['request_ref']:raise ValueError('Cross-request event relation; use explicit handoff reference')
            if ref not in r['evidence_refs']:raise ValueError('Event relation missing in evidence_refs')
    if kind=='step':
        if 'reporting_component' in p:
            component=p['reporting_component']
            if not isinstance(component,dict) or component.get('kind') not in {'agent','skill'}:raise ValueError('Invalid reporting component')
            for field in ('id','version','entry'):nonempty(component.get(field),field)
            if not re.fullmatch('[a-f0-9]{64}',component.get('entry_sha256','')):raise ValueError('Invalid reporting component hash')
        if p['status'] not in {'running','succeeded','failed','cancelled'}:raise ValueError('Invalid step status')
        number(p['attempt'],'attempt',True)
        if p['attempt']<1:raise ValueError('Attempt starts at 1')
        for k in ('step_key','phase'):nonempty(p[k],k)
        start=utc(p['started_at'])
        if p['status']=='running':
            if p['ended_at'] is not None or p['duration_ms'] is not None:raise ValueError('Running step has no terminal time')
        else:
            end=utc(p['ended_at']);number(p['duration_ms'],'duration_ms')
            if end<start:raise ValueError('Step ends before start')
            expected=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()*1000
            if abs(expected-p['duration_ms'])>1:raise ValueError('Duration disagrees with timestamps')
        if not re.fullmatch('[a-f0-9]{32}',p['trace_id']) or int(p['trace_id'],16)==0 or not re.fullmatch('[a-f0-9]{16}',p['span_id']) or int(p['span_id'],16)==0:raise ValueError('Invalid trace/span ID')
        u=p['usage']
        if not isinstance(u,dict) or not {'scope','usage_key','provider','model','metering_ref','equivalents',*TOKENS}<=u.keys():raise ValueError('Usage fields missing')
        if u['scope']!='exclusive':raise ValueError('Inclusive parent usage would double-count children')
        for k in ('usage_key','provider','model','metering_ref'):nonempty(u[k],k)
        for k in TOKENS:measurement(u[k],True)
        for sub,total in [('cache_read_input_tokens','input_tokens'),('cache_creation_input_tokens','input_tokens'),('reasoning_output_tokens','output_tokens')]:
            if u[sub]['status']==u[total]['status']=='measured' and u[sub]['value']>u[total]['value']:raise ValueError('Token subset exceeds total')
        if not isinstance(u['equivalents'],list):raise ValueError('Equivalents must be a list')
        units=[]
        for eq in u['equivalents']:
            measurement(eq)
            for k in ('unit','formula_ref','formula_version','raw_unit'):nonempty(eq.get(k),k)
            if eq['value'] is not None:number(eq.get('raw_value'),'raw equivalent input')
            units.append((eq['unit'],eq['formula_ref'],eq['formula_version']))
        if len(units)!=len(set(units)):raise ValueError('Duplicate equivalent metric')
    if kind=='message':
        for k in ('conversation_id','message_id','turn_id','content_ref'):nonempty(p[k],k)
        if p['role'] not in {'user','assistant','tool','system'} or p['visibility'] not in {'user_visible','internal'}:raise ValueError('Invalid message category')
    if kind=='request_end' and p['status'] not in {'completed','cancelled','failed'}:raise ValueError('Invalid request end status')
    if kind in {'direction_error','correction','quality_issue','rework'}:
        for k in EVENT_FIELDS[kind].split():
            if k!='step_ref':nonempty(p[k],k)
    if kind=='handoff':
        for k in ('from_agent_ref','to_agent_ref'):typed(cx,tenant,p[k],{'agent_snapshot'},load)
        if p['from_agent_ref']==p['to_agent_ref']:raise ValueError('Handoff needs distinct Agents')
        if not {p['from_agent_ref'],p['to_agent_ref']} <= {r['context']['primary_agent_ref'],*r['context']['related_agent_refs']}:raise ValueError('Handoff Agents must appear in work context')
        nonempty(p['communication_ref'],'communication_ref')
    if kind=='coverage':
        if p['category'] not in {'messages','steps','directions','quality','usage'} or p['state'] not in {'complete','partial','unavailable'}:raise ValueError('Invalid coverage category/state')
        for k in ('observed','expected'):
            if p[k] is not None:number(p[k],k,True)
        nonempty(p['reason'],'coverage reason')
        if utc(p['window_end'])<utc(p['window_start']):raise ValueError('Invalid coverage window')
        if p['state']=='complete' and (p['observed'] is None or p['expected'] is None or p['observed']!=p['expected']):raise ValueError('Complete coverage requires reconciled counts')
    if kind in {'classification','reference','optimization','analysis'}:
        target=p.get('target')
        if not isinstance(target,dict) or not {'scope','agent_ref'}<=target.keys() or target['scope'] not in LAYERS:raise ValueError('Explicit target scope and Agent required')
        agent=typed(cx,tenant,target['agent_ref'],{'agent_snapshot'},load)
        if target['agent_ref'] not in {r['context']['primary_agent_ref'],*r['context']['related_agent_refs']}:raise ValueError('Target missing from work context')
        layer=p.get('candidate_layer',p.get('target_layer',target['scope']))
        if layer!=target['scope']:raise ValueError('Layer and target disagree')
        if kind=='optimization' and (layer in {'framework','yuanheng','unknown'} or agent['payload']['role_kind']!='subagent' or agent['payload']['agent_id'] in {'yuanheng','gonggong'}):raise ValueError('Framework/Yuanheng data is reference-only; separate user instruction required outside Diting')
        if layer=='framework':
            if not r['context']['related_agent_refs']:raise ValueError('Framework relevance needs cross-Agent association')
            cross=p.get('cross_agent_evidence',[])
            if not isinstance(cross,list):raise ValueError('Cross Agent evidence must be reference IDs')
            cross = list(cross)+[x for x in r['evidence_refs'] if load(cx,tenant,x)['kind']=='handoff']
            agents=set()
            for ref in cross:
                if ref not in r['evidence_refs']:raise ValueError('Cross Agent evidence not in evidence_refs')
                ctx=load(cx,tenant,ref).get('context',{})
                if ctx.get('primary_agent_ref'):agents.add(ctx['primary_agent_ref'])
                agents.update(ctx.get('related_agent_refs',[]))
            if len(agents)<2:raise ValueError('Framework relevance needs explicit cross-Agent evidence')
    if r.get('supersedes'):
        prior=load(cx,tenant,r['supersedes'])
        if prior.get('schema_version')==2:
            if keys(prior)!=keys(r):raise ValueError('Correction changes stable identity')
            if r.get('context',{}).get('request_ref')!=prior.get('context',{}).get('request_ref'):raise ValueError('Correction changes request')
    for k,value in keys(r):
        row=cx.execute('SELECT id FROM logical_keys WHERE tenant=? AND kind=? AND key=?',(tenant,k,value)).fetchone()
        if row and row[0]!=r.get('supersedes'):raise ValueError('Duplicate logical event/usage; correct the current version')

def project(cx,tenant,r,load):
    rid=r['record_id'];p=r['payload'];kind=r['kind']
    for k,value in keys(r):cx.execute('INSERT INTO logical_keys VALUES(?,?,?,?) ON CONFLICT(tenant,kind,key) DO UPDATE SET id=excluded.id',(tenant,k,value,rid))
    if kind=='agent_snapshot':
        cx.execute('INSERT INTO agent_catalog VALUES(?,?,?,?,?,?,?)',(tenant,rid,p['agent_id'],p['version'],p['definition_digest'],p['origin'],p['role_kind']))
    if kind in {'source','agent_snapshot'}:return
    c=r['context'];req=r if kind=='request' else load(cx,tenant,c['request_ref'])
    at=p.get('occurred_at',p.get('started_at',p.get('initiated_at',r['created_at'])))
    step=rid if kind=='step' else p.get('step_ref')
    step_key=(p['step_key'] if kind=='step' else load(cx,tenant,step)['payload']['step_key']) if step else None
    cx.execute('INSERT INTO dimensions VALUES(?,?,?,?,?,?,?,?,?)',(tenant,rid,c['request_ref'],req['payload']['project_id'],c['primary_agent_ref'],step,step_key,utc(at),kind))
    cx.executemany('INSERT INTO agent_links VALUES(?,?,?)',[(tenant,rid,a) for a in [c['primary_agent_ref'],*c['related_agent_refs']]])
    cx.executemany('INSERT INTO work_links VALUES(?,?,?,?,?,?)',[(tenant,rid,w['id'],w['kind'],w['relation'],w['certainty']) for w in c['work_items']])
    labels=[]
    if kind=='annotation':labels=[(x['name'],str(x['value'])) for x in p['labels']]
    if kind=='classification':labels=[('category',str(x)) for x in p['categories']]+[('layer',p['candidate_layer'])]
    if kind=='step' and p.get('reporting_component'):
        emitter=p['reporting_component']
        labels += [('component_kind',emitter['kind']),('component_id',emitter['id']),('component_version',emitter['version'])]
    cx.executemany('INSERT OR IGNORE INTO labels VALUES(?,?,?,?)',[(tenant,rid,k,v) for k,v in labels])

def summarize(items,group_by):
    groups={}; excluded={'superseded':0,'stale':0,'legacy_unmapped':0}
    for item in items:
        state=item['evidence_state'];r=item['record'];p=r['payload'];kind=r['kind']
        if state in excluded:excluded[state]+=1;continue
        if 'context' not in r:continue
        c=r['context']
        key={'agent':c['primary_agent_ref'],'request':c['request_ref'],'project':item.get('dimensions',{}).get('project_id'),'step':item.get('dimensions',{}).get('step_key'),'day':utc(p.get('occurred_at',p.get('started_at',p.get('initiated_at',r['created_at']))))[:10]}.get(group_by)
        if key is None:key='unassigned'
        g=groups.setdefault(key,{'records':0,'requests':set(),'steps':0,'step_duration_ms':0,'unfinished_steps':0,'messages':{},'turns':set(),'direction_errors':0,'corrections':0,'quality_issues':0,'reworks':0,'handoffs':0,'tokens':{k:{'measured':0,'estimated':0,'unavailable':0,'not_applicable':0} for k in TOKENS},'equivalents':{},'coverage':[],'request_started_at':None,'request_ended_at':None,'per_observed_step_tokens_complete':True})
        g['records']+=1;g['requests'].add(c['request_ref'])
        if kind=='request':g['request_started_at']=utc(p['initiated_at'])
        if kind=='request_end':g['request_ended_at']=utc(p['occurred_at'])
        if kind=='step':
            g['steps']+=1
            if p['duration_ms'] is None:g['unfinished_steps']+=1
            else:g['step_duration_ms']+=p['duration_ms']
            for k in TOKENS:
                value=p['usage'][k];g['tokens'][k][value['status']]+=value['value'] if value['value'] is not None else 1
            if any(p['usage'][k]['status'] not in {'measured','not_applicable'} for k in ('input_tokens','output_tokens')):g['per_observed_step_tokens_complete']=False
            for eq in p['usage']['equivalents']:
                ek='|'.join([eq['unit'],eq['formula_ref'],eq['formula_version'],eq['status']])
                e=g['equivalents'].setdefault(ek,{'value':0,'missing':0})
                if eq['value'] is None:e['missing']+=1
                else:e['value']+=eq['value']
        if kind=='message':
            mk=p['visibility']+':'+p['role'];g['messages'][mk]=g['messages'].get(mk,0)+1
            if p['visibility']=='user_visible' and p['role']=='user':g['turns'].add((p['conversation_id'],p['turn_id']))
        counters={'direction_error':'direction_errors','correction':'corrections','quality_issue':'quality_issues','rework':'reworks','handoff':'handoffs'}
        if kind in counters:g[counters[kind]]+=1
        if kind=='coverage':g['coverage'].append({'record_id':r['record_id'],**p})
    for g in groups.values():
        g['request_count']=len(g.pop('requests'));g['dialogue_rounds']=len(g.pop('turns'))
        g['known_measured_tokens']=g['tokens']['input_tokens']['measured']+g['tokens']['output_tokens']['measured']
        g['per_observed_step_tokens_complete']=bool(g['steps']) and g['per_observed_step_tokens_complete']
        g['request_wall_ms']=None
        if group_by=='request' and g['request_started_at'] and g['request_ended_at']:
            g['request_wall_ms']=(datetime.fromisoformat(g['request_ended_at'])-datetime.fromisoformat(g['request_started_at'])).total_seconds()*1000
        g['observed_only']=True
    return {'group_by':group_by,'groups':groups,'excluded':excluded,'metric_version':'diting-2','limits':'Counts are observed facts, not completeness claims. Step durations overlap; do not interpret their sum as request wall time. Token subsets and equivalents are not added to total tokens.'}
