"""Project a bounded set of known rows from the authenticated editor's last board read."""

import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import ExitStack, closing

import progress
from repository_access import session_path, work_items


def cache_path(nonce):
    return session_path(nonce).with_suffix(".board.sqlite")


def scope_key(args, actor):
    kind = "project" if args.project else "history" if args.personal_history else "personal"
    return (
        kind
        + ":"
        + json.dumps(
            [str(args.repo.resolve()), actor, [] if args.project else sorted(set(args.follow))], sort_keys=True
        )
    )


def stamp(item):
    data = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def seed(args, actor, sources, items):
    """Only rows from a verified full read are eligible for delta queries."""
    scope = scope_key(args, actor)
    try:
        with closing(sqlite3.connect(cache_path(args.editor_session))) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS rows (scope TEXT, number INTEGER, dispatch_revision TEXT, item TEXT, "
                "PRIMARY KEY(scope, number))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS observed_starts (scope TEXT, number INTEGER, marker TEXT, PRIMARY KEY(scope, number))"
            )
            db.execute("DELETE FROM rows WHERE scope LIKE ?", (scope.split(":", 1)[0] + ":%",))
            for item in items:
                item["delta_stamp"] = stamp(item)
                db.execute(
                    "INSERT INTO rows VALUES (?, ?, ?, ?)",
                    (scope, item["number"], sources[item["number"]], json.dumps(item, ensure_ascii=False)),
                )
            db.execute(
                "DELETE FROM observed_starts WHERE NOT EXISTS (SELECT 1 FROM rows r WHERE "
                "r.scope=observed_starts.scope AND r.number=observed_starts.number)"
            )
        return True
    except (OSError, sqlite3.Error):
        # The full authoritative board remains usable when local storage is unavailable.
        for item in items:
            item.pop("delta_stamp", None)
        return False


def remove_cached(cache, row_key, prior, result):
    with cache:
        changed = cache.execute("DELETE FROM rows WHERE scope=? AND number=? AND item=?", (*row_key, prior)).rowcount
    result["removed" if changed else "reconcile"].append(row_key[1])


def direct_member(item, args, actor):
    if item["number"] in args.follow:
        return True
    names = [item["creator"], *item["owners"]]
    return (args.personal_history or not item["closed"]) and any(
        name.casefold() == actor["login"].casefold() for name in names
    )


def start_intent(receipts, item):
    """A legacy watcher sends one key for every journal. Only an exact start intent invalidates GitHub data."""
    request = item["request"]
    if (
        item["closed"]
        or item["status"] != "planned"
        or not item.get("source_sha256")
        or not re.fullmatch(r"daqian-direct-[a-f0-9]{20}", request)
    ):
        return None, ""
    path = receipts / "daqian-direct" / request / "start.json"
    try:
        stat = path.stat()
    except OSError:
        return None, ""
    state = progress.read_object(path)
    # A different collaborator can start the same issue. Their marker only
    # invalidates this row: GitHub is read using this viewer's verified session.
    saved_binding = state.get("binding")
    if (
        not isinstance(saved_binding, dict)
        or not isinstance(saved_binding.get("actor"), str)
        or not re.fullmatch(r"[1-9][0-9]*", saved_binding["actor"])
    ):
        return None, ""
    binding = {
        "actor": saved_binding["actor"],
        "number": item["number"],
        "request_id": request,
        "revision": item["updated"],
        "source_sha256": item["source_sha256"],
        "url": item["url"],
    }
    decision = state.get("result")
    if state.get("binding") != binding or not isinstance(decision, dict) or decision.get("ready") is not True:
        return None, ""
    return path.parent, stamp([binding, stat.st_mtime_ns, stat.st_size])


def read_changes(args, actor):
    import plan_store
    from board import plan_summary, project_row

    with args.delta.open("rb") as file:
        raw = file.read(65537)
    if len(raw) > 65536:
        raise ValueError("增量请求过大")
    request = json.loads(raw)
    mode = request["mode"]
    targets = request["items"]
    if mode not in ("progress", "source") or not isinstance(targets, list) or not 0 < len(targets) <= 64:
        raise ValueError("无效的增量读取范围")
    numbers = set()
    for target in targets:
        number = target["number"]
        if (
            type(number) is not int
            or number <= 0
            or number in numbers
            or not isinstance(target.get("request"), str)
            or not isinstance(target.get("updated"), str)
        ):
            raise ValueError("工单标识无效")
        numbers.add(number)
    result = {
        **{k: actor[k] for k in ("repo", "repo_id", "user_id")},
        "updates": [],
        "removed": [],
        "reconcile": [],
        "source_required": [],
    }
    path = cache_path(args.editor_session)
    scope = scope_key(args, actor)
    if not path.is_file():
        result["reconcile"] = sorted(numbers)
        return result

    receipts = progress.receipt_root(args.repo)
    repo = actor["repo"]
    try:
        with closing(sqlite3.connect(path)) as cache, ExitStack() as stack:
            plans = None
            for target in targets:
                number = target["number"]
                row_key = (scope, number)
                record = cache.execute(
                    "SELECT dispatch_revision, item FROM rows WHERE scope=? AND number=?", row_key
                ).fetchone()
                if record is None:
                    result["reconcile"].append(number)
                    continue
                revision, encoded = record
                previous = json.loads(encoded)
                if previous["request"] != target["request"] or previous["updated"] != target["updated"]:
                    result["reconcile"].append(number)
                    continue
                folder, marker = start_intent(receipts, previous)
                if marker:
                    seen = cache.execute(
                        "SELECT marker FROM observed_starts WHERE scope=? AND number=?", row_key
                    ).fetchone()
                    if seen == (marker,):
                        marker = ""
                if marker and mode == "progress":
                    result["source_required"].append(number)
                if mode == "progress":
                    item = previous.copy()
                    item.pop("judgment_attempt", None)
                    item["routing_receipt"] = progress.route_for_snapshot(args.repo, receipts, actor, item)
                    item["workers"] = progress.workers_for_snapshot(receipts, repo, revision, item)
                else:
                    if marker and (folder / ".flush.lock").is_file() and (folder / ".flush.lock").stat().st_size:
                        # start.json precedes the label mutation; wait for the actual writer's
                        # critical section before reading the authoritative issue.
                        import bridge

                        try:
                            with bridge.outbox_lock(folder, time.monotonic() + 2):
                                pass
                        except ValueError:
                            result["source_required"].append(number)
                            continue
                    endpoint = f"repos/{repo}/issues/{number}"
                    try:
                        source = json.loads(work_items.gh("api", endpoint))
                    except work_items.GitHubCommandError as error:
                        if error.http_status != 404:
                            raise
                        remove_cached(cache, row_key, record[1], result)
                        continue
                    if (
                        source.get("number") != number
                        or "pull_request" in source
                        or source.get("html_url") != f"https://github.com/{repo}/issues/{number}"
                    ):
                        result["reconcile"].append(number)
                        continue
                    item = project_row(args.repo, receipts, actor, source)
                    if args.project and item["closed"]:
                        remove_cached(cache, row_key, record[1], result)
                        continue
                    if (
                        not args.project
                        and direct_member(previous, args, actor)
                        and not direct_member(item, args, actor)
                    ):
                        # The previous root may still be reachable through another issue's dependencies.
                        result["reconcile"].append(number)
                        continue
                    if source.get("issue_dependencies_summary", {}).get("total_blocked_by") != 0:
                        pages = json.loads(
                            work_items.gh(
                                "api", endpoint + "/dependencies/blocked_by?per_page=100", "--paginate", "--slurp"
                            )
                        )
                        item["dependencies"] = [dep["html_url"] for page in pages for dep in page]
                    if not args.project and set(item["dependencies"]) != set(previous["dependencies"]):
                        # A new dependency can add an entire subgraph to the personal board.
                        result["reconcile"].append(number)
                        continue
                if os.environ.get("DAQIAN_PLAN_SSH_HOST"):
                    if item["updated"] != previous["updated"] or item["request"] != previous["request"]:
                        result["reconcile"].append(number)
                        continue
                    for field in (
                        "node_states",
                        "running_titles",
                        "answered_count",
                        "pending_count",
                        "decision",
                        "answers_unverified",
                    ):
                        if field in previous:
                            item[field] = previous[field]
                elif not item["closed"]:
                    if plans is None:
                        plans = stack.enter_context(plan_store.connect(args.repo))
                    item.update(plan_summary(plans, item))
                item.pop("delta_stamp", None)
                item["delta_stamp"] = stamp(item)
                # Recheck the original snapshot when a simultaneous full refresh or delta won the race.
                if mode == "source":
                    with cache:
                        count = cache.execute(
                            "UPDATE rows SET dispatch_revision=?, item=? WHERE scope=? AND number=? AND item=?",
                            (
                                progress.dispatch_revision(source),
                                json.dumps(item, ensure_ascii=False),
                                *row_key,
                                record[1],
                            ),
                        ).rowcount
                        if count == 1 and marker:
                            cache.execute("INSERT OR REPLACE INTO observed_starts VALUES (?, ?, ?)", (*row_key, marker))
                    if count != 1:
                        result["reconcile"].append(number)
                        continue
                if target.get("delta_stamp") != item["delta_stamp"]:
                    result["updates"].append(item)
    except sqlite3.Error:
        result.update(updates=[], removed=[], source_required=[], reconcile=sorted(numbers))
    return result
