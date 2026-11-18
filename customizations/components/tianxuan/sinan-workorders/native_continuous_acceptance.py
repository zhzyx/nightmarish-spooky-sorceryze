"""Executable acceptance fixture; run from a fresh named owned probe directory."""

# ruff: noqa: E402, I001
import argparse
import json
import re
import sys
import time
from pathlib import Path


root = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser(description="Real 50-member / 250-producer continuous admission acceptance, no models")
parser.add_argument("--run-name", default="acceptance-" + str(time.time_ns()))
args = parser.parse_args()
if not re.fullmatch(r"[a-zA-Z0-9-]{1,80}", args.run_name):
    parser.error("run-name must be a short filename identifier")
for x in ["sinan-workorders", "duobao", "server"]:
    sys.path.insert(0, str(root / "customizations/components/tianxuan" / x))

from native_candidates import NativeCandidates
from native_integration import NativeIntegration
from test_native_workflow import fixture, reserve

p = root / "work/native-continuous-integration-probes" / args.run_name
p.mkdir(parents=True, exist_ok=False)
g = fixture.__wrapped__(p)
f = next(g)
w, actor, tenant, req, initial, _ = f
members = [actor] + [
    w.domain.add_member(actor, f"member-{n}@example.invalid", "password")["user_id"] for n in range(1, 50)
]
w.principals = lambda a, i, r: (
    a
    if r == "producer"
    else {"integrator": actor, "checker": actor, "reviewer": "reviewer", "publisher": "publisher"}[r]
)
w.worker.intake.authorize = lambda *a: True
w.worker.profiles["local"]["argv"][-1] = (
    "import pathlib,os,json; p=pathlib.Path.cwd(); c=json.loads(pathlib.Path(os.environ['NATIVE_CONTEXT']).read_text(encoding='utf-8')); name=c['title']; (p/'a'/name).write_text(name,encoding='utf-8'); (p.parent/'started-once').write_text(name)"
)
w.runner._registry["check"]["argv"][-1] = (
    "import pathlib,os,json; p=pathlib.Path(os.environ['DUOBAO_INPUT']); assert all(f.read_text(encoding='utf-8')==f.name for f in (p/'a').glob('item-*')); manifests=list(p.glob('integration-*/integration.json')); assert len(manifests)<=1; plans=[json.loads(f.read_text(encoding='utf-8')) for f in manifests]; assert all((p/'a'/o['contract']['source']['definition']['title']).exists() for x in plans for o in x['originals'])"
)
w.runner._registry["check"]["argv"][-1] += (
    "\nfor plan in plans:\n for ref in plan.get('continuation',{}).get('required_history',[]):\n  record=json.loads((pathlib.Path(os.environ['DUOBAO_HISTORY'])/(ref+'.json')).read_text(encoding='utf-8')); old=record['plan']; assert record['selection']['id']==ref\n  if old:\n   assert all((p/'a'/o['contract']['source']['definition']['title']).exists() for o in old['originals'])"
)
w.runner.cache.policies["stable"] = dict(version="1", reads={"a": ["output"]}, max_age_seconds=3600)
w.runner._registry["stable"] = {
    **w.runner._registry["check"],
    "argv": [
        w.runner._registry["check"]["argv"][0],
        "-c",
        "import pathlib,os; assert (pathlib.Path(os.environ['DUOBAO_INPUT'])/'a'/'output').read_text()=='initial'; assert 'DUOBAO_HISTORY' not in os.environ",
    ],
}
policy = dict(
    tenant=tenant,
    coordinator=actor,
    product="joint",
    channel="stable",
    base={"a": initial["a"]},
    checks=["check", "stable"],
    max_batch=7,
    history_refs=["first", "predecessor"],
    request_id="native-continuous-integration-20261118",
    issue_url="https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1488",
)
i = NativeIntegration(
    w, NativeCandidates(w.worker.store, lambda *a: True), lambda *a: None, installed_continuous=lambda a: [policy]
)
w.release.configure(
    tenant,
    "publisher",
    "joint",
    dict(checks={c: w.runner.context(c, "0" * 64) for c in ["check", "stable"]}, review_max_age_seconds=3600),
)
keys: list[str] = []
terminals: dict[str, str] = {}
times: list[dict[str, object]] = []
arrivals: list[dict[str, object]] = []
reviews: list[str] = []


def produce(n):
    name = f"item-{n:03d}"
    member = members[n % 50]
    issue = w.domain.create_issue(member, name, requirement_id=req["id"], acceptance=name + " present")
    key = w.authorize_task(
        member,
        issue["id"],
        selected={"a": initial["a"]},
        writes={"a": [name]},
        dependencies={},
        profile="local",
        product="joint",
        checks=["check", "stable"],
        mandate="continuous-proof",
        delivery_mode="contribution",
    )
    reserve((w, member, tenant, req, initial, p), key)
    start = time.time()
    w.execute(member, key)
    done = time.time()
    i.check_contribution(member, key)
    keys.append(key)
    terminals[key] = w.status(actor, key)["terminal"]
    times.append(dict(task=key, start=start, finish=done))
    return key


produced_in_review = False


def review(a, plan, result):
    global produced_in_review
    reviews.append(result["candidate"])
    if not produced_in_review:
        produced_in_review = True
        start = time.time()
        produce(16)
        arrivals.append(dict(start=start, finish=time.time(), during_plan=plan["group"]))
    return True


w.review_candidate = review
for n in range(16):
    produce(n)
lane = i.continuous.ready(actor)[0]["key"]
receipts = []
receipts.append(i.continue_lane(actor, lane))
for n in range(17, 250):
    produce(n)
    if n % 7 == 0:
        receipts.append(i.continue_lane(actor, lane))
while i.continuous.ready(actor):
    r = i.continue_lane(actor, lane)
    receipts.append(r)
    if r["state"] not in ("accepted", "successor_ready"):
        raise AssertionError(r)
selected = w.release.selected(tenant, actor, "joint", "stable")
objects = w.worker.store.revision(tenant, "a", selected["modules"]["a"])["objects"]
assert len([x for x in objects if x.startswith("item-")]) == 250
assert all(w.status(actor, k)["state"] == "accepted" and w.status(actor, k)["terminal"] == terminals[k] for k in keys)
assert len(set(reviews)) == len(reviews) > 1
assert len(list((p / "workers").rglob("started-once"))) == 250
batches = [dict(r) for r in w.domain.db.execute("SELECT * FROM native_continuous_batches")]
for b in batches:
    assert b["state"] == "accepted"
timings = [dict(r) for r in w.domain.db.execute("SELECT * FROM native_integration_timings")]
with w.worker.store._connection() as db:
    checks = [json.loads(r[0]) for r in db.execute("SELECT payload FROM native_check_runs")]
out = dict(
    real_members=members,
    stage_timings=timings,
    check_runs=checks,
    request_id=policy["request_id"],
    issue_url=policy["issue_url"],
    producers=250,
    producer_launch_markers=250,
    originals_preserved=True,
    actual_publications=len(batches),
    batch_sizes=[len(json.loads(b["tasks"])) for b in batches],
    arrival_during_review=arrivals,
    batches=batches,
    producer_times=times,
    selected=selected,
    failures=[],
    remaining=["Independent source review and root delivery"],
)
(root / "data-collection/native-continuous-integration-1488.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({k: out[k] for k in ["producers", "actual_publications", "batch_sizes"]}))
g.close()
