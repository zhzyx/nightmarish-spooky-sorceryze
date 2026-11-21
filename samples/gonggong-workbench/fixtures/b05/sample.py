"""B05 disposable two-user Tianxuan / Duobao fixture. Run with Python 3.11+."""

import hashlib
import json
import secrets
import sys
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
COMPONENT = ROOT / "customizations/components/tianxuan"
sys.path[:0] = [str(COMPONENT / "server"), str(COMPONENT / "duobao")]

from native_store import NativeStore  # noqa: E402
from tianxuan_core import PermissionDenied, Tianxuan  # noqa: E402


@contextmanager
def sample():
    """Yield open isolated stores and the logical-to-current identity map."""
    spec = json.loads((HERE / "sample.json").read_text(encoding="utf-8"))
    asset = spec["asset"]
    model = (ROOT / asset["repo_source"]).read_bytes()
    if hashlib.sha256(model).hexdigest() != asset["sha256"]:
        raise ValueError("The shared model differs from the B05 manifest")

    with TemporaryDirectory(prefix="gonggong-b05-") as directory:
        path = Path(directory)
        domain = Tianxuan(str(path / "work.sqlite"))
        with closing(domain.db):
            native = NativeStore(path / "native.sqlite")
            owner = domain.register("B05", "movement@example.invalid", secrets.token_urlsafe())
            tenant = owner["tenant_id"]
            teammate = domain.add_member(owner["user_id"], "animation@example.invalid", secrets.token_urlsafe())
            users = {"movement": owner["user_id"], "animation": teammate["user_id"]}

            def publish(actor, module, edits, dependencies):
                change = dict(module=module, base=None, reads=[], edits=edits, dependencies=dependencies)
                receipt = native.submit(tenant, actor, "seed-" + module, [change])
                return receipt["revisions"][module]

            asset_revision = publish(users["movement"], asset["module"], {asset["path"]: model}, {})
            modules = {}
            for item in spec["modules"]:
                key, actor = item["id"], users[item["actor"]]
                req = domain.create_requirement(actor, key, item["title"], item["title"], key, spec["issue_title"])
                domain.set_visibility(actor, req["id"], "private")
                issue = domain.create_issue(actor, spec["issue_title"], requirement_id=req["id"])
                settings = json.dumps(item["settings"], sort_keys=True).encode()
                revision = publish(actor, key, {"settings.json": settings}, {asset["module"]: asset_revision})
                modules[key] = dict(
                    actor=actor, requirement=req["id"], issue=issue["id"], number=issue["number"], revision=revision
                )
            yield domain, native, dict(tenant=tenant, users=users, modules=modules, asset_revision=asset_revision)


def verify():
    """Exercise both consumers, change state, then recreate the baseline twice."""
    spec = json.loads((HERE / "sample.json").read_text(encoding="utf-8"))
    asset = spec["asset"]
    runs = []
    for _ in range(3):
        with sample() as (domain, native, state):
            tenant, users, modules = state["tenant"], state["users"], state["modules"]
            assert len(set(users.values())) == len(domain.list_members(users["movement"])) == 2
            assert len({row["issue"] for row in modules.values()}) == 2
            assert len({row["requirement"] for row in modules.values()}) == 2
            assert {row["number"] for row in modules.values()} == {1, 2}
            consumers = {}
            for item in spec["modules"]:
                key, actor = item["id"], users[item["actor"]]
                row = modules[key]
                (issue,) = domain.list_issues(actor, row["requirement"])
                assert (issue["id"], issue["number"], issue["title"], issue["created_by"]) == (
                    row["issue"],
                    row["number"],
                    spec["issue_title"],
                    actor,
                )
                assert domain.list_issue_comments(actor, issue["id"]) == []
                doc = domain.get_doc_shared(actor, row["requirement"])
                assert (doc["request_id"], doc["title"]) == (key, item["title"])
                composition = native.compose(tenant, {key: row["revision"]})
                assert composition["modules"] == {key: row["revision"], asset["module"]: state["asset_revision"]}
                settings = native.read(tenant, key, row["revision"], "settings.json")
                assert json.loads(settings) == item["settings"]
                pinned = composition["modules"][asset["module"]]
                content = native.read(tenant, asset["module"], pinned, asset["path"])
                consumers[key] = hashlib.sha256(content).hexdigest()
                assert consumers[key] == asset["sha256"]

            move, anim = modules["character-movement"], modules["character-animation"]
            assert [i["id"] for i in domain.list_issues(users["animation"])] == [anim["issue"]]
            try:
                domain.issue_snapshot(users["animation"], move["issue"])
            except PermissionDenied:
                pass
            else:
                raise AssertionError("The animation editor could open the private movement issue")
            domain.add_issue_comment(users["animation"], anim["issue"], "重置前的临时批注")
            assert len(domain.list_issue_comments(users["animation"], anim["issue"])) == 1
            assert domain.list_issue_comments(users["movement"], move["issue"]) == []
            runs.append(dict(**state, shared_model_reads=consumers))

    for first, second in zip(runs, runs[1:], strict=False):
        assert first["tenant"] != second["tenant"]
        assert set(first["users"].values()).isdisjoint(second["users"].values())
        assert first["asset_revision"] == second["asset_revision"]
        for module, previous in first["modules"].items():
            current = second["modules"][module]
            assert (previous["number"], previous["revision"]) == (current["number"], current["revision"])
            assert previous["issue"] != current["issue"]
    return runs


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("Run without -O to enable acceptance assertions")
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
