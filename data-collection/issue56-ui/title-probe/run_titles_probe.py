import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate-root',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--visible',action='store_true');a=p.parse_args()
 e=json.loads(a.evidence.read_text(encoding='utf-8-sig'));a.out.mkdir(parents=True,exist_ok=True)
 exe=a.candidate_root/'bin/godot.windows.editor.x86_64.console.exe';engine=exe.with_name(exe.name.replace('.console.exe','.exe'))
 sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
 def verify():
  assert sha(exe)==e['binary_sha256'] and sha(engine)==e['engine_sha256']
  assert all(sha(a.candidate_root/n)==v for n,v in e['source_sha256'].items())
 verify();results=[]
 with tempfile.TemporaryDirectory(prefix='title-probe-',dir=a.out.resolve()) as folder:
  t=Path(folder);project=t/'project';project.mkdir()
  (project/'project.godot').write_bytes(b'config_version=5\n[application]\nconfig/name="Unicode title probe"\n')
  script=Path(__file__).with_name('titles_probe.gd');shutil.copyfile(script,project/'probe.gd')
  env=os.environ.copy();env.update(APPDATA=str(t/'appdata'),LOCALAPPDATA=str(t/'localappdata'),GODOT_AI_API_KEY='')
  config=t/'appdata/Godot';config.mkdir(parents=True)
  (config/'editor_settings-4.8.tres').write_bytes(b'[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/backend = 0\ninterface/editor/appearance/display_scale = 4\n')
  for stage in ['seed','restore']:
   result=(a.out/f'title-{stage}.json').resolve();env.update(AI_TITLE_STAGE=stage,AI_TITLE_RESULT=str(result),AI_TITLE_SCREENSHOT='1' if a.visible else '0')
   with (a.out/f'title-{stage}.log').open('w',encoding='utf-8') as log:
    run=subprocess.run([str(exe),*([] if a.visible else ['--headless']),'--editor','--path',str(project),'--script','res://probe.gd'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=30)
   results.append({'stage':stage,'exit_code':run.returncode,'result_present':result.is_file()})
 verify()
 summary={'candidate':e,'probe_sha256':sha(script),'results':results,'passed':all(r['exit_code']==0 and r['result_present'] for r in results),'scope':'Unicode default/new/recreate-last titles, parent caption,640x900@150% active title bounds and second-process persistence; no layout matrix rerun','mode':'native' if a.visible else 'headless_geometry'}
 (a.out/'summary.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps(summary,ensure_ascii=False,indent=2));return 0 if summary['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
