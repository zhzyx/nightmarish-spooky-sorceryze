import unittest,tempfile,json,runpy,sqlite3,sys
from pathlib import Path
from contextlib import closing

HERE=Path(__file__).resolve()
TOOL=HERE.with_name('diting-host.py')
if not TOOL.exists():TOOL=HERE.parents[1]/'tools/diting-host.py'
api=runpy.run_path(str(TOOL))
WORK=next(p for p in HERE.parents if (p/'CURRENT_FRAMEWORK.json').is_file());ROOT=WORK/'framework'

class HostTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
  (self.root/'data-collection').mkdir();(self.root/'authority.json').write_text('{}')
  # Link only the real, immutable reporter dependencies into the isolated workspace.
  import shutil
  shutil.copytree(ROOT,self.root/'framework',ignore=shutil.ignore_patterns('__pycache__'))
  self.file=self.root/'data-collection/catalog.json';self.c={'path_base':'project_root','project_root':'..','tenant_id':'test','framework':'framework','ledger':'data-collection/data.sqlite','outbox':'data-collection/outbox.sqlite','inbox':'data-collection/inbox','receipts':'data-collection/receipts','reporting_skill':'data-collect','sources':[{'path':'data-collection/data.sqlite'}]}
  self.save();api['initialize'](self.file)
  ctx={'request_ref':'request','primary_agent_ref':'agent','related_agent_refs':[],'work_items':[{'id':'test#1','kind':'task','relation':'fixture','certainty':'confirmed'}],'linkage_state':'partial','linkage_note':'isolated test fixture'}
  def rec(rid,kind,payload):
   r={'schema_version':2,'record_id':rid,'tenant_id':'test','kind':kind,'created_at':'2026-11-03T00:00:00+00:00','evidence_refs':[] if kind=='source' else ['source'],'payload':payload}
   if kind not in ('source','agent_snapshot'):r['context']=ctx
   return r
  def event(rid,kind,payload):return rec(rid,kind,{'source_key':'fixture','event_key':rid,'source_revision':'1',**payload})
  records=[rec('source','source',{'source_key':'fixture','authority_ref':'authority.json','purpose':'test','retention':'temporary fixture','allowed_fields':['test']}),rec('agent','agent_snapshot',{'agent_id':'test-agent','version':'1','definition_digest':'a'*64,'definition_ref':'authority.json','origin':'external','role_kind':'governance'}),event('request','request',{'request_key':'fixture','project_id':'test','initiated_at':'2026-11-03T00:00:00+00:00','intent':'test'}),event('message','message',{'conversation_id':'test','message_id':'m1','turn_id':'t1','role':'user','visibility':'user_visible','content_ref':'authority.json','step_ref':None,'occurred_at':'2026-11-03T00:00:00+00:00'}),event('coverage','coverage',{'category':'steps','state':'unavailable','observed':None,'expected':None,'reason':'isolated fixture','window_start':'2026-11-03T00:00:00+00:00','window_end':'2026-11-03T00:00:00+00:00'})]
  self.env={'tenant_id':'test','batch_key':'fixture-begin','source_ref':'source','agent_snapshot_ref':'agent','request_ref':'request','authority_ref':'authority.json','records':records}
 def save(self):self.file.write_text(json.dumps(self.c),encoding='utf-8')
 def submit(self):return api['submit'](self.file,self.env)
 def test_delivery_replay_and_conflicting_identity(self):
  self.assertTrue(self.submit()['delivered']);self.assertTrue(self.submit()['delivered'])
  self.assertEqual(sum(api['query'](self.file,'test')['current_counts'].values()),5)
  self.env['records'][0]['payload']['purpose']='different'
  with self.assertRaisesRegex(ValueError,'identity reused'):self.submit()
 def test_sink_failure_keeps_envelope_and_recovers(self):
  db=self.root/self.c['ledger'];db.rename(db.with_suffix('.saved'))
  r=self.submit();self.assertTrue(r['recorded']);self.assertTrue(r['queued']);self.assertFalse(r['delivered'])
  db.with_suffix('.saved').rename(db);self.assertTrue(self.submit()['delivered'])
 def test_missing_source_partial_and_duplicate_source_dedup(self):
  self.submit();self.c['sources'] += [{'path':'missing.sqlite'},self.c['sources'][0]];self.save()
  r=api['query'](self.file,'test');self.assertEqual(r['outcome'],'partial');self.assertEqual(len(r['records']),5)
 def test_tenant_and_write_boundary(self):
  with self.assertRaises(ValueError):api['query'](self.file,'other')
  self.c['receipts']='../outside';self.save()
  with self.assertRaises(ValueError):self.submit()
 def test_run_records_failure_and_never_repeats_command(self):
  self.submit();start=self.env['records'][2]
  session={k:self.env[k] for k in ('tenant_id','source_ref','agent_snapshot_ref','request_ref','authority_ref')}
  session.update(source_key=start['payload']['source_key'],context=start['context'])
  file=self.root/'session.json';file.write_text(json.dumps(session))
  r=api['run_command'](self.file,file,'failing-command',[sys.executable,'-c','raise SystemExit(3)'])
  self.assertEqual(r['exit_code'],3);self.assertTrue(r['end_delivered'])
  with self.assertRaises(FileExistsError):api['run_command'](self.file,file,'failing-command',[sys.executable,'-c','pass'])
  q=api['query'](self.file,'test',kind='step');self.assertEqual(q['current_counts']['step'],1)
  self.assertEqual(sum(v['state']=='superseded' for v in q['records']),1)

if __name__=='__main__':unittest.main()
