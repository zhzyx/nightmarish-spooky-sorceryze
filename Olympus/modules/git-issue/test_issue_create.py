import unittest,tempfile,json
from pathlib import Path
import issue_create as m
class Fake:
 def __init__(self):self.issues=[];self.creates=0;self.fail=False
 def actor(self):return 'tester'
 def find(self,p):return self.issues
 def create(self,p,body):
  self.creates+=1
  if self.fail:raise RuntimeError('unknown network result')
  self.issues=[{'html_url':'https://github.com/a/b/issues/1','number':1,'body':body,'user':{'login':'tester'},'updated_at':'2026-11-03T00:00:00Z'}];return self.issues[0]['html_url']
 def get(self,p,url):return self.issues[0]
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'authority.json').write_text('{}')
  self.p=m.plan({'request_id':'sample-task','title':'test','body':'intent','type':'development','owner':'host','acceptance':'proof','authority_ref':'authority.json'},{'repository':'a/b','workspace_id':'olympus','workspace_label':'workspace:olympus'})
  self.api=Fake();self.settings={'enabled':True,'approved_plan_sha256':self.p['plan_sha256']}
 def test_disabled(self):
  self.settings['enabled']=False
  with self.assertRaises(ValueError):m.execute(self.p,self.settings,self.root,self.api,lambda e:True)
  self.assertEqual(self.api.creates,0)
 def test_create_reuse_actor(self):
  a=m.execute(self.p,self.settings,self.root,self.api,lambda e:True);b=m.execute(self.p,self.settings,self.root,self.api,lambda e:True)
  self.assertEqual((a['action'],b['action'],self.api.creates),('created','reused',1));self.assertIn('host-git-account:tester',self.api.issues[0]['body'])
 def test_unknown_no_retry(self):
  self.api.fail=True
  with self.assertRaises(RuntimeError):m.execute(self.p,self.settings,self.root,self.api,lambda e:True)
  with self.assertRaises(ValueError):m.execute(self.p,self.settings,self.root,self.api,lambda e:True)
  self.assertEqual(self.api.creates,1)
 def test_reporting_failure_no_create(self):
  with self.assertRaises(ValueError):m.execute(self.p,self.settings,self.root,self.api,lambda e:False)
  self.assertEqual(self.api.creates,0)
 def test_tampered_plan(self):
  self.p['title']='changed'
  with self.assertRaises(ValueError):m.execute(self.p,self.settings,self.root,self.api,lambda e:True)
 def test_duplicate_remote(self):
  self.api.issues=[{},{}]
  with self.assertRaises(ValueError):m.execute(self.p,self.settings,self.root,self.api,lambda e:True)
 def test_embedded_marker_not_reused(self):
  self.api.issues=[{'html_url':'https://github.com/a/b/issues/1','number':1,'body':'unrelated\n'+self.p['marker']}]
  with self.assertRaisesRegex(ValueError,'identity mismatch'):m.execute(self.p,self.settings,self.root,self.api,lambda e:True)
 def test_all_body_fields_reject_markers(self):
  for field in ('owner','acceptance','authority_ref'):
   request={'request_id':'sample-task','title':'test','body':'intent','type':'development','owner':'host','acceptance':'proof','authority_ref':'authority.json'}
   request[field]='<!-- olympus-request:other -->'
   with self.assertRaises(ValueError):m.plan(request,{'repository':'a/b','workspace_id':'olympus','workspace_label':'workspace:olympus'})
if __name__=='__main__':unittest.main()
