"""Actual runner/ledger fixture support; only worker model and GitHub are isolated."""

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
folder = None
returns: list[str] = []


def prepare(env, manual_config=True):
    global folder
    folder = Path(env["DESIGN_BATCH_ROOT"]).parent
    original = Path(env["DESIGN_BATCH_ROOT"])
    subprocess.run(["git", "-C", str(original), "config", "core.autocrlf", "false"], check=True)
    for name in (
        "framework",
        "customizations/components/issue-workorders",
        "customizations/platforms/work-management/github/git-issue",
        "customizations/platforms/development/git",
    ):
        shutil.copytree(
            ROOT / name,
            original / name,
            ignore=shutil.ignore_patterns("node_modules", "__pycache__"),
            dirs_exist_ok=True,
        )
    shutil.copyfile(ROOT / "CURRENT_FRAMEWORK.json", original / "CURRENT_FRAMEWORK.json")
    (original / "integrations/gonggong").mkdir(parents=True)
    shutil.copyfile(
        ROOT / "integrations/gonggong/frozen-distribution.json",
        original / "integrations/gonggong/frozen-distribution.json",
    )
    subprocess.run(
        ["git", "-C", str(original), "add", "framework", "customizations", "integrations", "CURRENT_FRAMEWORK.json"],
        check=True,
        capture_output=True,
    )
    if env.get("NATIVE_ACCEPTANCE_SCENARIO") == "parallel-integration":
        subprocess.run(["git", "-C", str(original), "add", "samples/project"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(original), "commit", "-m", "isolated actual framework inputs"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(original), "push", "origin", "HEAD:main"], check=True, capture_output=True)
    env["PATH"] = str(Path(env["DESIGN_BATCH_NODE"]).parent) + os.pathsep + env["PATH"]
    if manual_config:
        env["NATIVE_PARALLEL_CONFIG"] = str(folder / "parallel-config.json")
        (folder / "parallel-config.json").write_text("{}", encoding="utf8")


def setup(scenario="parallel"):
    if (folder / "parallel-setup.done").exists():
        return
    original = folder / "original"
    binding = next((original / ".git/gonggong-engine-candidates").glob("*.json"))
    parent = Path(json.loads(binding.read_text(encoding="utf8"))["source_root"])
    worker = folder / "fixture-worker.mjs"
    worker.write_text(
        """import fs from 'node:fs';import path from 'node:path';
let prompt='';for await(const chunk of process.stdin)prompt+=chunk;
if(!prompt.includes('Issue #441'))throw Error('Missing actual mandate');
const name=path.basename(process.cwd()).slice(-1);
fs.writeFileSync('received-prompt.txt',prompt);
if(name==='C') {
  const upstream=JSON.parse(prompt.split('HOST_ACCEPTED_UPSTREAM=')[1].split('\\n')[0]);
  if(upstream.length!==2||upstream.some(s=>!fs.existsSync(s.root)||!fs.existsSync(s.decision_path)||!s.criteria.length))throw Error('Missing accepted upstream');
  if(upstream.some(s=>s.decision||s.verified_response||!s.candidate_check))throw Error('Prompt must contain compact check references, not private manifests');
  for(const source of upstream)for(const criterion of source.criteria)for(const evidence of criterion.evidence) {
    if(!fs.readFileSync(path.join(source.root,evidence.path),'utf8').includes('UNTRUSTED_FIXTURE_FILE') && evidence.path==='fixture-input.txt')throw Error('Upstream bytes missing');
  }
}
const event=phase=>fs.appendFileSync(new URL('./worker-events.jsonl',import.meta.url),JSON.stringify({name,phase,pid:process.pid,time:Date.now()})+'\\n');
event('start');await new Promise(r=>setTimeout(r,1200));
fs.writeFileSync('fixture-input.txt','UNTRUSTED_FIXTURE_FILE actual external '+name+' execution\\n');
if((prompt.includes('Bound failed review data')||prompt.includes('Bound missing execution evidence')))fs.writeFileSync('repair-evidence.txt','actual repaired execution');
event('finish');console.log('Actual fixture worker completed '+name);
""",
        encoding="utf8",
    )
    if scenario == "parallel-integration":
        game_script = 'extends SceneTree\nfunc _initialize():\n\tprint("NATIVE_INTEGRATION_EXECUTED:" + FileAccess.get_file_as_string("res://production-output.txt"))\n\tquit()\n'
        worker.write_text(
            worker.read_text(encoding="utf8").replace(
                "event('finish');",
                "if(name==='C'){fs.writeFileSync('samples/project/production-output.txt','ACCEPTED_NATIVE_PROJECT_OUTPUT');"
                + "fs.writeFileSync('samples/project/production-output.gd',"
                + json.dumps(game_script)
                + ");}\nevent('finish');",
            ),
            encoding="utf8",
        )
    roots = []
    owners = ["4" if scenario == "parallel-self-review" and name == "A" else "external-" + name for name in "ABC"]
    for name in ("A", "B", "C"):
        target = folder / ("external-" + name)
        subprocess.run(
            ["git", "-C", str(parent), "worktree", "add", "-b", "fixture-external-" + name, str(target), "HEAD"],
            check=True,
            capture_output=True,
        )
        (target / "design-docs").mkdir(exist_ok=True)
        shutil.copyfile(parent / "design-docs/design-batch-fixture.md", target / "design-docs/design-batch-fixture.md")
        roots.append(str(target))
    module = ROOT / "customizations/platforms/document-management/git-markdown/yanshi-legacy/runtime/src/production.mjs"
    script = folder / "setup-ledgers.mjs"
    script.write_text(
        'import fs from "node:fs";import {Production} from '
        + json.dumps(module.as_uri())
        + ";\n"
        + "const roots="
        + json.dumps(roots)
        + ";const owners="
        + json.dumps(owners)
        + ";const keys=[];\n"
        + """
for(let i=0;i<roots.length;i++) {const p=new Production(roots[i]);p.init({checkpointEvery:1000});
const name='ABC'[i];const task=p.create({title:name,goal:'Actual native external acceptance',stage:'integration',acceptance:[name],independentReview:true});
p.start(task.id,{owner:owners[i],capability:'code',authority:'https://github.com/example/design-batch/issues/441',nextAction:'Run actual registered worker'});
keys.push(p.read().ledgerId+'::'+task.id);}
fs.writeFileSync(new URL('./ledger-keys.json',import.meta.url),JSON.stringify(keys));
""",
        encoding="utf8",
    )
    node = os.environ["NATIVE_PARALLEL_NODE"]
    subprocess.run([node, str(script)], check=True, capture_output=True)
    keys = json.loads((folder / "ledger-keys.json").read_text())
    registry = folder / "registry.json"
    registry.write_text(
        json.dumps({"sources": [{"id": name, "root": root} for name, root in zip("ABC", roots)]}), encoding="utf8"
    )
    config = {
        "nativeWorkspaceWrite": True,
        "authorityRef": "https://github.com/example/design-batch/issues/441",
        "capacity": 2,
        "python": os.environ["NATIVE_PARALLEL_PYTHON"],
        "workerCommand": {"executable": node, "args": [str(worker), "{model}"]},
        "registry": str(registry),
        "models": [{"id": "isolated-command", "available": True, "targets": ["agent"], "capabilities": ["code"]}],
        "jobs": [
            {
                "order": i + 1,
                "worktree": root,
                "workerId": owners[i],
                "capabilities": ["code"],
                "acceptanceTicket": keys[i],
                "dependsOn": keys[:2] if i == 2 else [],
            }
            for i, (name, root) in enumerate(zip("ABC", roots))
        ],
    }
    (folder / "parallel-config.json").write_text(json.dumps(config), encoding="utf8")
    (folder / "parallel-setup.done").touch()


def diagnostics():
    result = []
    if folder is None:
        return result
    for path in folder.glob("external-*/.yuanheng/state.json"):
        result.append({"path": path.relative_to(folder).as_posix(), "body": path.read_text(encoding="utf8")})
    for path in folder.glob("godot-candidate-*/data-collection/outbox/parallel-*"):
        if path.is_file() and path.suffix == ".json":
            result.append({"path": str(path.relative_to(folder)), "body": path.read_text(encoding="utf8")})
    # Worktree executions share the original repository's common directory;
    # their durable ticket lineage is stored beside that directory.
    for path in (folder / "original/data-collection/outbox").glob("parallel-ticket-*.json"):
        result.append({"path": str(path.relative_to(folder)), "body": path.read_text(encoding="utf8")})
    path = folder / "worker-events.jsonl"
    if path.exists():
        result.append({"path": "worker-events", "body": path.read_text(encoding="utf8")})
    return result
