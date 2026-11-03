from pathlib import Path
import sys,json,shutil,tempfile,threading,hashlib,time,os,runpy,subprocess
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];BASE=Path.cwd();(BASE/'work').mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'runtime'))
import runner,adapters,evaluate
checks=[];requests=[];answers=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
        answer=answers.pop(0) if answers else {'action':'final','value':'ok'}
        text=answer if isinstance(answer,str) else json.dumps(answer)
        if self.path=='/chat':data={'choices':[{'message':{'content':text},'finish_reason':'stop'}],'usage':{'prompt_tokens':10,'completion_tokens':5}}
        elif self.path=='/ollama':data={'message':{'content':text},'done':True,'done_reason':'stop','prompt_eval_count':10,'eval_count':5}
        else:data={'text':text,'finish_reason':'stop','usage':{'input_tokens':10,'output_tokens':5}}
        raw=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
os.environ['OLYMPUS_HOST_KEY']='isolated-test-key-not-a-production-secret'
try:
 with tempfile.TemporaryDirectory(dir=BASE/'work',prefix='model-integration-') as tmp:
    temp=Path(tmp);root=temp/'framework';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('__pycache__'))
    manifest=runner.read(root/'framework-manifest.json');(root/'reviews/local-admission').mkdir(parents=True,exist_ok=True);(root/'reviews/local-admission/fixture.txt').write_text('Synthetic test only; not production approval.')
    fp=runpy.run_path(str(root/'tools/verify_framework.py'))['fingerprint']
    for a in manifest['agents']:
        p=runner.read(root/'templates/review-pass.json');d,files=fp(root,a['candidate_files']);assert d==a['candidate_digest']
        p.update(template=False,status='approved',event='agent_definition_change',phase='local_definition_release')
        p['subject']={'id':a['id'],'version_or_digest':{'version':a['version'],'candidate_digest':d,'files':files},'scope':['local_agent_definition_only']}
        p['review']={'olympus_framework':'pass','concision':{'status':'pass'},'applicable_validation':'pass','independence':'independent_subagent_review','evaluator_id':'synthetic-reviewer','zeus':{k:'pass' for k in ['purpose','truth','economy','authority','adaptation','continuity']},'evidence_refs':['reviews/local-admission/fixture.txt']}
        p['approval']={'approver_id':'synthetic-approver','authority_ref':'test-only','decision_evidence_ref':'reviews/local-admission/fixture.txt','approved_at':runner.now(),'valid_until_or_task_end':'bound_candidate_only','expires_at':None}
        (root/a['admission_pass']).write_text(json.dumps(p),encoding='utf-8')
    def profile(protocol,path,ident):
        p={'id':ident,'protocol':protocol,'endpoint':f'http://127.0.0.1:{server.server_port}/{path}','model':'synthetic-'+ident,'max_context_bytes':100000,'system_role':False if path=='ollama' else True}
        report=evaluate.evaluate(p,[{'id':'summary','task_type':'summary','messages':[{'role':'user','content':'return ok'}],'schema':{'type':'string'},'expected':'ok'}],'synthetic')
        assert report['passed_task_types']==['summary'];f=temp/(ident+'-eval.json');f.write_text(json.dumps(report),encoding='utf-8')
        p['evaluation']={**{k:report[k] for k in ['profile_digest','scope','passed_task_types']},'evidence_ref':str(f),'evidence_sha256':hashlib.sha256(f.read_bytes()).hexdigest()};return p
    profiles=[profile('chat-completions','chat','chat'),profile('ollama-chat','ollama','ollama'),profile('olympus-json','bridge','bridge')]
    def plan(name,agent='athena',models=None,mode='single'):
        return {'task':{'id':name,'tenant_id':'synthetic','project_id':'test','agent_id':agent,'outcome':'test summary','authority_ref':'isolated test','retention':'temporary test','mode':mode,'validation_only':True,'work_items':[{'id':'test','kind':'feature','relation':'tests','certainty':'confirmed'}],'steps':[{'id':'summary','kind':'summary','instruction':'return ok','output':'text'}]},'profiles':models or profiles,'limits':{'max_calls':5,'max_output_tokens':128}}
    def grant(p,state):
        payload={**p,'state_dir':str(state),'expires_at':time.time()+600,'authority_ref':'synthetic-only','framework_sha256':hashlib.sha256((root/'framework-manifest.json').read_bytes()).hexdigest()}
        return {'payload':payload,'signature':runner.signature(payload)}
    def ok(name):checks.append({'name':name,'pass':True})
    for p in profiles:
        state=temp/p['id'];g=grant(plan('protocol-'+p['id'],models=[p]),state);r=runner.run(g,root,state);assert r['status']=='completed';assert r['result']['calls']==1
        n=len(requests);assert runner.run(g,root,state)['replayed'];assert len(requests)==n;ok(p['protocol']+' HTTP + actual admission + telemetry + idempotent replay')
    for agent in ['themis','hermes']:
        state=temp/agent;assert runner.run(grant(plan(agent,agent),state),root,state)['status']=='completed';ok(agent+' admitted context to local telemetry')
    state=temp/'fallback';p=plan('fallback');p['task']['steps'][0]['skill']='metis';p['task']['steps'][0]['references']=['agents/athena/references/understanding.md'];answers.extend(['bad json',{'action':'final','value':'ok'}]);r=runner.run(grant(p,state),root,state);assert r['status']=='completed' and r['result']['calls']==2
    ledger=runpy.run_path(str(root/'agents/hermes/scripts/ledger.py'));records=[x['record'] for x in ledger['query'](state/'hermes.sqlite','synthetic')]
    assert sum(x['kind']=='quality_issue' for x in records)==1 and sum(x['kind']=='rework' for x in records)==1
    steps=[x for x in records if x['kind']=='step'];assert len(steps)==2 and all(x['payload']['reporting_component']['id']=='metis' for x in steps);ok('rejected output fallback, quality/rework and once-only skill attribution')
    state=temp/'autonomous';p=plan('autonomous',mode='autonomous');p['task']['resources']={'brief':'approved facts'};p['task']['steps'][0]['tools']=['lookup_resource'];answers.extend([{'action':'tool','name':'lookup_resource','arguments':{'key':'brief'}},{'action':'final','value':'ok'}]);assert runner.run(grant(p,state),root,state)['result']['calls']==2;ok('bounded autonomous resource read')
    state=temp/'workflow';p=plan('workflow',mode='workflow');p['task']['steps'].append({'id':'second','kind':'summary','instruction':'use previous','output':'text'});assert runner.run(grant(p,state),root,state)['result']['calls']==2;assert 'previous_results' in requests[-1]['messages'][-1]['content'];ok('host planned multi-step workflow')
    state=temp/'context';p=plan('context');p['profiles']=[dict(profiles[0])];p['profiles'][0]['max_context_bytes']=1
    # Changed model config must invalidate evaluation before dispatch.
    before=len(requests)
    try:runner.run(grant(p,state),root,state);raise AssertionError('stale evaluation accepted')
    except ValueError as e:assert 'stale' in str(e)
    assert len(requests)==before;ok('changed profile rejected before network')
    # Actual CLI signing / running uses a separate process, not Python test-only call injection.
    state=temp/'cli';p=plan('cli');f=temp/'plan.json';f.write_text(json.dumps(p));g=temp/'cli-grant.json'
    for args in [['authorize','--plan',str(f),'--state',str(state),'--authority-ref','synthetic-test','--out',str(g)],['run','--grant',str(g),'--state',str(state)]]:
        out=subprocess.run([sys.executable,str(root/'runtime/runner.py'),'--root',str(root),*args],capture_output=True,text=True);assert out.returncode==0,out.stderr
    ok('standalone CLI authorization and execution without Codex SDK')
finally:server.shutdown();server.server_close()
out=BASE/'work/model-integration-results.json';out.write_text(json.dumps({'synthetic_only':True,'checks':checks,'passed':len(checks),'real_models_tested':False},indent=2),encoding='utf-8');print(out.read_text())
