from pathlib import Path
import sys,json,hashlib
root=Path(sys.argv[1]).resolve();out=Path(__file__).parent/(sys.argv[2] if len(sys.argv)>2 else 'adapters-baseline');out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(root/'runtime'));import adapters as a
tests=[];raw=b'';requests=[]
class Response:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):return raw[:n]
class Opener:
 def open(self,req,timeout):requests.append((req,timeout));return Response()
a.urllib.request.build_opener=lambda *args:Opener()
def test(name,fn):
 try:r=fn();tests.append({'name':name,'pass':True,'detail':r})
 except Exception as e:tests.append({'name':name,'pass':False,'error':type(e).__name__+': '+str(e)})
def eq(x,y):
 assert x==y,(x,y)
 return x
def unknown(fn):
 try:fn()
 except a.TransportUnknown as e:return str(e)
 raise AssertionError('Expected TransportUnknown')
def denied(fn):
 try:fn()
 except ValueError as e:return str(e)
 raise AssertionError('Expected rejection')
def run(protocol,payload,**extra):
 global raw
 raw=json.dumps(payload).encode();return a.call({'protocol':protocol,'endpoint':'http://localhost/model','model':'synthetic',**extra},[{'role':'system','content':'bound'}, {'role':'user','content':'input'}],23)
chat={'id':'x','choices':[{'message':{'content':'synthetic'},'finish_reason':'stop'}],'usage':{'prompt_tokens':10,'completion_tokens':5,'prompt_tokens_details':{'cached_tokens':2},'completion_tokens_details':{'reasoning_tokens':1}}}
test('chat normalization',lambda:eq(run('chat-completions',chat)['usage'],{'input_tokens':10,'output_tokens':5,'cache_read_input_tokens':2,'reasoning_output_tokens':1}))
test('chat output cap parameter',lambda:eq(json.loads(requests[-1][0].data)['max_tokens'],23))
test('ollama normalization',lambda:eq(run('ollama-chat',{'message':{'content':'synthetic'},'done':True,'prompt_eval_count':10,'eval_count':5})['finish_reason'],'stop'))
test('custom normalization',lambda:eq(run('gonggong-json',{'text':'synthetic','finish_reason':'stop','usage':{'input_tokens':10,'output_tokens':5}})['usage'],{'input_tokens':10,'output_tokens':5}))
test('systemless profile preserves tagged instructions',lambda:(run('gonggong-json',{'text':'synthetic','finish_reason':'stop'},system_role=False),eq(json.loads(requests[-1][0].data)['messages'],[{'role':'user','content':'system:\nbound\n\nuser:\ninput'}])))
test('nonlocal HTTP denied',lambda:denied(lambda:a.call({'protocol':'gonggong-json','endpoint':'http://example.invalid/','model':'s'},[],1)))
test('URL credential denied',lambda:denied(lambda:a.call({'protocol':'gonggong-json','endpoint':'https://user:secret@example.invalid/','model':'s'},[],1)))
test('negative usage classified unknown',lambda:unknown(lambda:run('gonggong-json',{'text':'synthetic','finish_reason':'stop','usage':{'input_tokens':-1}})))
test('bad nested message classified unknown',lambda:unknown(lambda:run('chat-completions',{'choices':[{'message':[],'finish_reason':'stop'}]})))
test('bad nested usage classified unknown',lambda:unknown(lambda:run('gonggong-json',{'text':'synthetic','finish_reason':'stop','usage':[1]})))
test('impossible token subset classified unknown before projection',lambda:unknown(lambda:run('gonggong-json',{'text':'synthetic','finish_reason':'stop','usage':{'output_tokens':2,'reasoning_output_tokens':3}})))
result={'scope':'synthetic urllib opener; zero network calls','sha256':hashlib.sha256((root/'runtime/adapters.py').read_bytes()).hexdigest(),'tests':tests};(out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
