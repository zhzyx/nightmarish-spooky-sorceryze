from pathlib import Path
import sys,json,os,hashlib,time,shutil,importlib,sqlite3,copy,runpy,subprocess
SOURCE=Path(sys.argv[1]).resolve();W=Path(__file__).parent/(sys.argv[2] if len(sys.argv)>2 else 'baseline');W.mkdir(parents=True,exist_ok=True);root=W/'framework';shutil.copytree(SOURCE,root,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
sys.path.insert(0,str(root/'runtime'));import runner,diting,adapters
os.environ['GONGGONG_HOST_KEY']='synthetic-review-key-not-a-real-secret-0123456789'
tests=[]
def test(name,fn):
 try:r=fn();tests.append({'name':name,'pass':True,'detail':r})
 except Exception as e:tests.append({'name':name,'pass':False,'error':type(e).__name__+': '+str(e)})
def eq(a,b):
 assert a==b,(a,b)
 return a
def reject(fn):
 try:fn()
 except Exception as e:return type(e).__name__+': '+str(e)
 raise AssertionError('Unexpected acceptance')
def lockcheck(state):
 with runner.worker_lock(state):
  def second():
   with runner.worker_lock(state):pass
  return reject(second)
def profile(pid='p1',types=['document']):
 p={'id':pid,'protocol':'gonggong-json','endpoint':'http://127.0.0.1:1','model':'synthetic','max_context_bytes':100000,'timeout_seconds':1}
 report={'profile_digest':runner.digest(p),'scope':'synthetic','passed_task_types':types};f=W/('evaluation-'+pid+'.json');f.write_text(json.dumps(report),encoding='utf8')
 p['evaluation']={**report,'evidence_ref':str(f.resolve()),'evidence_sha256':hashlib.sha256(f.read_bytes()).hexdigest()};return p
def plan(tid='t1',mode='single',profiles=None):return {'task':{'id':tid,'tenant_id':'synthetic','project_id':'review','agent_id':'yanshi','outcome':'synthetic only','authority_ref':'synthetic','retention':'temporary','validation_only':True,'mode':mode,'work_items':[{'id':'test','kind':'review','relation':'validates','certainty':'confirmed'}],'steps':[{'id':'s1','kind':'document','instruction':'return candidate','output':'text','tools':[]}]},'limits':{'max_calls':3,'max_output_tokens':40},'profiles':profiles or [profile()]}
def grant(p,state):
 payload={**copy.deepcopy(p),'state_dir':str(state.resolve()),'authority_ref':'synthetic','expires_at':time.time()+3600,'framework_sha256':hashlib.sha256((root/'framework-manifest.json').read_bytes()).hexdigest()};return {'payload':payload,'signature':runner.signature(payload)}
received={'text':json.dumps({'action':'final','value':'synthetic candidate'}),'finish_reason':'stop','usage':{'input_tokens':10,'output_tokens':5},'provider_request_id':'synthetic'}
calls=[];responses=[]
def fake(model,messages,limit):
 calls.append({'model':model['id'],'messages':copy.deepcopy(messages),'limit':limit})
 response=responses.pop(0) if responses else received
 if isinstance(response,Exception):raise response
 return copy.deepcopy(response)
runner.call=fake
# Admission/context execution is tested independently; this seam isolates runtime and projection tests while candidate passes do not yet exist.
runner.context=lambda root,t:'Synthetic admitted context for isolated runtime test'
state=W/'initial';g=grant(plan(),state)
test('unmodified projection accepts registered Agent',lambda:eq(runner.run(g,root,state)['status'],'completed'))
patch= (root/'runtime/diting.py').read_text(encoding='utf8');patched="'origin':'existing'" in patch
if patched:
 (root/'runtime/diting.py').write_text(patch.replace("'origin':'existing'","'origin':'registered'"),encoding='utf8');importlib.reload(diting)
state=W/'success';g=grant(plan(),state)
test('valid result commits with real Diting receipt',lambda:eq(runner.run(g,root,state)['status'],'completed'))
n=len(calls);test('completed replay does not call provider',lambda:(eq(runner.run(g,root,state)['replayed'],True),eq(len(calls),n)))
test('second task same tenant state can execute',lambda:eq(runner.run(grant(plan('t2'),state),root,state)['status'],'completed'))
L=runpy.run_path(str(root/'agents/diting/scripts/ledger.py'))
test('completed request termination projected',lambda:eq(len(L['query'](state/'diting.sqlite','synthetic',kind='request_end')),2))
bad=copy.deepcopy(g);bad['payload']['limits']['max_calls']=99
test('tampered grant denied',lambda:reject(lambda:runner.run(bad,root,state)))
test('different state denied',lambda:reject(lambda:runner.run(g,root,W/'wrong-state')))
expired=copy.deepcopy(g);expired['payload']['expires_at']=0;expired['signature']=runner.signature(expired['payload'])
test('expired grant denied',lambda:reject(lambda:runner.run(expired,root,state)))
p=plan();p['task']['validation_only']=False
test('synthetic capability cannot authorize production',lambda:reject(lambda:runner.validate_plan(p)))
state=W/'route';p=plan(profiles=[profile('wrong',['code']),profile('right')]);g=grant(p,state);n=len(calls)
test('only evaluated task capability routes',lambda:(eq(runner.run(g,root,state)['status'],'completed'),eq([c['model'] for c in calls[n:]],['right'])))
state=W/'unknown';g=grant(plan(),state);responses[:]=[adapters.TransportUnknown('synthetic unknown')];n=len(calls)
test('unknown dispatch stops without auto fallback',lambda:(eq(runner.run(g,root,state)['status'],'needs_reconciliation'),eq(len(calls),n+1)))
test('unknown replay blocked before explicit decision',lambda:reject(lambda:runner.run(g,root,state)))
test('operator retry retains call budget',lambda:(eq(runner.recover(g,root,state,'retry')['budget_reset'],False),eq(runner.run(g,root,state)['result']['calls'],2)))
state=W/'bad-output';g=grant(plan(),state);responses[:]=[{**received,'text':'bad json'}]
test('bad output rejected',lambda:eq(runner.run(g,root,state)['status'],'needs_attention'))
test('bad output quality evidence projected',lambda:eq(len(L['query'](state/'diting.sqlite','synthetic',kind='quality_issue')),1))
state=W/'tool';p=plan(mode='autonomous');p['task']['resources']={'ok':'synthetic untrusted reference'};p['task']['steps'][0]['tools']=['lookup_resource'];g=grant(p,state);responses[:]=[{**received,'text':json.dumps({'action':'tool','name':'lookup_resource','arguments':{'key':'ok'}})},received]
test('authorized lookup only returns host resource',lambda:(eq(runner.run(g,root,state)['status'],'completed'),eq(calls[-1]['messages'][-1]['content'],adapters.canonical({'tool_result':'synthetic untrusted reference','untrusted_data':True}))))
state=W/'unauthorized-tool';g=grant(plan(),state);responses[:]=[{**received,'text':json.dumps({'action':'tool','name':'shell','arguments':{'key':'no'}})}]
test('unauthorized tool rejected',lambda:eq(runner.run(g,root,state)['status'],'needs_attention'))
state=W/'bounded';p=plan(mode='autonomous');p['limits']['max_calls']=2;p['task']['resources']={'ok':'x'};p['task']['steps'][0]['tools']=['lookup_resource'];g=grant(p,state);responses[:]=[{**received,'text':json.dumps({'action':'tool','name':'lookup_resource','arguments':{'key':'ok'}})}]*2;n=len(calls)
test('autonomous tool loop budget bounded',lambda:(eq(runner.run(g,root,state)['status'],'needs_attention'),eq(len(calls),n+2)))
state=W/'crash-received';g=grant(plan(),state);original_emit=runner.emit
def interrupted(cx,jid,kind,data):
 result=original_emit(cx,jid,kind,data)
 if kind=='call_end' and data['status']=='received':raise KeyboardInterrupt('synthetic crash after persisted received')
 return result
runner.emit=interrupted
try:runner.run(g,root,state)
except KeyboardInterrupt:pass
finally:runner.emit=original_emit
test('received crash recovery retains measured usage',lambda:(runner.recover(g,root,state,'retry'),runner.run(g,root,state),eq(sum(r['record']['payload']['usage']['input_tokens']['value'] or 0 for r in L['query'](state/'diting.sqlite','synthetic',kind='step')),20)))
state=W/'cancel';g=grant(plan(),state);responses[:]=[adapters.TransportUnknown('synthetic unknown')];runner.run(g,root,state)
test('operator cancellation projected',lambda:(eq(runner.recover(g,root,state,'cancel')['status'],'cancelled'),eq([r['record']['payload']['status'] for r in L['query'](state/'diting.sqlite','synthetic',kind='request_end')],['cancelled'])))
test('worker lock rejects a second worker',lambda: lockcheck(W/'locked'))
state=W/'skill';p=plan();p['task']['steps'][0]['skill']='clarify-feature';g=grant(p,state)
test('registered skill steps meter exactly once',lambda:(eq(runner.run(g,root,state)['status'],'completed'),eq(len(L['query'](state/'diting.sqlite','synthetic',kind='step')),1),eq(L['query'](state/'diting.sqlite','synthetic',kind='step')[0]['record']['payload']['reporting_component']['id'],'clarify-feature')))
state=W/'fallback';p=plan(profiles=[profile('first'),profile('second')]);g=grant(p,state);responses[:]=[{**received,'text':'bad json'},received]
test('rejected output fallback records one rework',lambda:(eq(runner.run(g,root,state)['status'],'completed'),eq(len(L['query'](state/'diting.sqlite','synthetic',kind='quality_issue')),1),eq(len(L['query'](state/'diting.sqlite','synthetic',kind='rework')),1)))
state=W/'expired-recovery';g=grant(plan(),state);responses[:]=[adapters.TransportUnknown('synthetic unknown')];runner.run(g,root,state)
renewed=copy.deepcopy(g);renewed['payload']['expires_at']+=3600;renewed['payload']['replaces_grant']=runner.digest(g);renewed['payload']['limits']['max_calls']=99;renewed['signature']=runner.signature(renewed['payload'])
test('renewal cannot increase original budget',lambda:reject(lambda:runner.recover(renewed,root,state,'retry')))
prior=W/'prior-grant.json';prior.write_text(json.dumps(g),encoding='utf8');newfile=W/'renewed-grant.json'
def renew_cli():
 r=subprocess.run([sys.executable,str(root/'runtime/runner.py'),'--root',str(root),'renew','--grant',str(prior),'--out',str(newfile)],capture_output=True,text=True)
 eq(r.returncode,0);return json.loads(newfile.read_text(encoding='utf8'))
test('same-scope authorized renewal can recover old job',lambda:eq(runner.recover(renew_cli(),root,state,'retry')['status'],'ready'))
state=W/'crash-completed';g=grant(plan(),state)
def interrupted_complete(cx,jid,kind,data):
 result=original_emit(cx,jid,kind,data)
 if kind=='completed':raise KeyboardInterrupt('synthetic crash after persistent completion')
 return result
runner.emit=interrupted_complete
try:runner.run(g,root,state)
except KeyboardInterrupt:pass
finally:runner.emit=original_emit
def consistent_cancel():
 try:decision=runner.recover(g,root,state,'cancel')
 except ValueError:return 'cancel rejected after durable completion'
 ended=[r['record']['payload']['status'] for r in L['query'](state/'diting.sqlite','synthetic',kind='request_end')]
 return eq(ended,[decision['status']])
test('cancel cannot contradict durable completion',consistent_cancel)
n=len(calls);test('durable completion recovery makes no new call',lambda:(eq(runner.recover(g,root,state,'retry')['status'],'completed'),eq(len(calls),n)))
state=W/'crash-cancel';g=grant(plan(),state);responses[:]=[adapters.TransportUnknown('synthetic unknown')];runner.run(g,root,state);original_export=runner.export
def fail_projection(*args):raise RuntimeError('synthetic temporary projection failure')
runner.export=fail_projection
try:runner.recover(g,root,state,'cancel')
except RuntimeError:pass
finally:runner.export=original_export
test('durable cancellation cannot resume after delivery failure',lambda:reject(lambda:runner.recover(g,root,state,'retry')))
test('durable cancellation retries delivery consistently',lambda:(eq(runner.recover(g,root,state,'cancel')['status'],'cancelled'),eq([r['record']['payload']['status'] for r in L['query'](state/'diting.sqlite','synthetic',kind='request_end')],['cancelled'])))
result={'source':str(SOURCE),'scope':'local synthetic tests; admission context seam stubbed explicitly; no real network or model','isolated_origin_patch_for_deeper_tests':patched,'tests':tests,'sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['framework-manifest.json','runtime/runner.py','runtime/adapters.py','runtime/diting.py']}}
(W/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
