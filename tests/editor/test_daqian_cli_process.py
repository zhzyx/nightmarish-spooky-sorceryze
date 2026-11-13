"""Real owned process trees, without a model account or remote inference."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))

# isort: split
import local_models  # noqa: E402

FIXTURE = r"""
import json, os, signal, subprocess, sys, time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
record = Path(sys.argv[1])
if sys.argv[2] == 'child':
    grandchild = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    record.write_text(json.dumps([os.getppid(), os.getpid(), grandchild.pid]))
    time.sleep(60)
else:
    subprocess.Popen([sys.executable, __file__, str(record), 'child'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while not record.exists(): time.sleep(.01)
    if sys.argv[2] == 'success':
        print(json.dumps({'models': [{'id': 'fixture'}]}), flush=True)
    elif sys.argv[2] == 'error':
        print(json.dumps({'error': {'code': 'AUTH_REQUIRED', 'message': 'private-marker'}}), flush=True)
    elif sys.argv[2] == 'malformed':
        print('private-marker', flush=True)
    elif sys.argv[2] == 'flood':
        sys.stdout.write('x' * 8_100_000); sys.stdout.flush()
    sys.stdin.read()
"""


def running(pid):
    if os.name == "nt":
        # Windows runtime acceptance is a separate CI responsibility below.
        raise NotImplementedError
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False)
    return result.returncode == 0 and result.stdout.strip() and not result.stdout.lstrip().startswith("Z")


@unittest.skipIf(os.name == "nt", "POSIX process-group runtime; Windows uses the shared WindowsJob tests")
class OwnedProcessTrees(unittest.TestCase):
    def test_terminal_timeout_and_invalid_output_reclaim_only_owned_tree(self):
        with tempfile.TemporaryDirectory(prefix="daqian-cli-boundary-") as temporary:
            root = Path(temporary)
            fixture = root / "fixture.py"
            fixture.write_text(FIXTURE)
            unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            try:
                for mode in ("success", "timeout", "error", "malformed", "flood"):
                    with self.subTest(mode=mode):
                        receipt = root / (mode + ".json")
                        start = time.monotonic()
                        try:
                            if mode == "success":
                                value = local_models.run_json([sys.executable, str(fixture), str(receipt), mode], 2)
                                self.assertEqual(value, {"models": [{"id": "fixture"}]})
                            else:
                                with self.assertRaises(ValueError) as caught:
                                    local_models.run_json([sys.executable, str(fixture), str(receipt), mode], 2)
                                self.assertNotIn("private-marker", str(caught.exception))
                                if mode == "timeout":
                                    self.assertIn("超时", str(caught.exception))
                                if mode == "error":
                                    self.assertIn("AUTH_REQUIRED", str(caught.exception))
                            self.assertLess(time.monotonic() - start, 5)
                            self.assertIsNone(unrelated.poll())
                            self.assertTrue(receipt.exists(), "fixture must actually start its descendants")
                            pids = json.loads(receipt.read_text())
                            deadline = time.monotonic() + 2
                            while any(running(pid) for pid in pids) and time.monotonic() < deadline:
                                time.sleep(0.02)
                            self.assertFalse([pid for pid in pids if running(pid)], "owned descendants survived")
                        finally:
                            if receipt.exists():
                                for pid in json.loads(receipt.read_text()):
                                    if running(pid):
                                        os.kill(pid, 9)
            finally:
                unrelated.kill()
                unrelated.wait(timeout=5)


CLI_FIXTURE = r"""
const fs=require('node:fs'), {spawn}=require('node:child_process');
const descendant=spawn(process.execPath,['-e',"process.on('SIGTERM',()=>{});setInterval(()=>{},1000)"],{stdio:'ignore'});
fs.writeFileSync(process.env.FIXTURE_PIDS,JSON.stringify([process.ppid,process.pid,descendant.pid]));
const mode=process.env.FIXTURE_MODE, command=process.env.FIXTURE_COMMAND, backend=process.env.FIXTURE_BACKEND;
if(mode==='timeout'){process.on('SIGTERM',()=>{});setInterval(()=>{},1000);}
else if(command==='models'){
 require('node:readline').createInterface({input:process.stdin}).on('line',line=>{
  const p=JSON.parse(line);
  if(backend==='codex'){
   if(p.method==='initialize') console.log(JSON.stringify({id:p.id,result:{}}));
   if(p.method==='model/list') console.log(JSON.stringify(mode==='error'?{id:p.id,error:{message:'private-marker'}}:{id:p.id,result:{data:[{id:'fixture',model:'fixture'}],nextCursor:null}}));
  }else console.log(JSON.stringify({type:'control_response',response:{request_id:p.request_id,subtype:mode==='error'?'error':'success',response:{models:[{id:'fixture'}]}}}));
 });
}else{
 if(mode==='error'){console.error('authentication required private-marker');process.exit(1);}
 if(backend==='codex'){
  console.log(JSON.stringify({type:'item.completed',item:{type:'agent_message',text:JSON.stringify({content:'fixture reply',actions:[]})}}));
  console.log(JSON.stringify({type:'turn.completed'}));
 }else console.log(JSON.stringify({type:'result',subtype:'success',result:JSON.stringify({content:'fixture reply',actions:[]})}));
 process.exit(0);
}
"""


@unittest.skipIf(os.name == "nt", "Actual POSIX bridges; WindowsJob needs its own Windows runtime acceptance")
class RealBridges(unittest.TestCase):
    def test_models_and_chat_return_or_timeout_without_leaking_descendants(self):
        node = os.environ.get("GONGGONG_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node is required for real bridge protocol tests")
        with tempfile.TemporaryDirectory(prefix="daqian-real-bridges-") as temporary:
            root = Path(temporary)
            cli = root / "cli.js"
            cli.write_text(CLI_FIXTURE)
            request = root / "request.json"
            request.write_text(
                json.dumps({
                    "model": "fixture",
                    "messages": [{"role": "user", "content": "fixture"}],
                    "available_tools": [],
                })
            )
            for backend in ("codex", "codebuddy"):
                for command in ("models", "chat"):
                    for mode in ("success", "error", "timeout"):
                        with self.subTest(backend=backend, command=command, mode=mode):
                            receipt = root / (backend + command + mode + ".json")
                            env = {
                                **os.environ,
                                "FIXTURE_PIDS": str(receipt),
                                "FIXTURE_BACKEND": backend,
                                "FIXTURE_COMMAND": command,
                                "FIXTURE_MODE": mode,
                            }
                            args = [node, local_models.BRIDGES[backend], command, cli]
                            if command == "chat":
                                args.append(request)
                            try:
                                if mode == "success":
                                    result = local_models.run_json(args, 3, env)
                                    if command == "models":
                                        self.assertEqual(result["models"][0]["id"], "fixture")
                                    else:
                                        self.assertEqual(result["choices"][0]["message"]["content"], "fixture reply")
                                else:
                                    with self.assertRaises(ValueError) as caught:
                                        local_models.run_json(args, 1 if mode == "timeout" else 3, env)
                                    self.assertNotIn("private-marker", str(caught.exception))
                                    if mode == "timeout":
                                        self.assertIn("超时", str(caught.exception))
                                    else:
                                        self.assertNotIn("超时", str(caught.exception))
                                self.assertTrue(receipt.exists(), "real bridge must have started the fake CLI")
                                pids = json.loads(receipt.read_text())
                                deadline = time.monotonic() + 2
                                while any(running(pid) for pid in pids) and time.monotonic() < deadline:
                                    time.sleep(0.02)
                                self.assertFalse([pid for pid in pids if running(pid)])
                            finally:
                                if receipt.exists():
                                    for pid in json.loads(receipt.read_text()):
                                        if running(pid):
                                            os.kill(pid, 9)


if __name__ == "__main__":
    unittest.main()
