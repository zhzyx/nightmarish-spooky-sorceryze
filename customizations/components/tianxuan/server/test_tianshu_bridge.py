"""天枢互通桥 CLI 测试：请求路径、身份头、信封与错误处理。"""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from email.message import Message
from typing import Literal
from urllib.request import Request

import pytest
import tianshu_bridge


@pytest.fixture
def gonggong_project(tmp_path, monkeypatch):
    monkeypatch.delenv("TIANXUAN_API", raising=False)
    monkeypatch.delenv("TIANXUAN_GIT_REPO", raising=False)
    monkeypatch.delenv("TIANXUAN_IDENTITY_PROVIDER", raising=False)
    root = tmp_path / "source"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:zhzyx/nightmarish-spooky-sorceryze.git"],
        check=True,
    )
    project = root / "nested"
    project.mkdir()
    return project


def test_project_route_is_local_readback(gonggong_project, monkeypatch, capsys):
    monkeypatch.setattr(tianshu_bridge, "urlopen", lambda *_a, **_kw: pytest.fail("unexpected network access"))
    monkeypatch.setenv("TIANXUAN_IDENTITY_PROVIDER", "fixture")

    def read_route():
        assert tianshu_bridge.main(["--workspace", str(gonggong_project), "duobao-route"]) == 0
        return json.loads(capsys.readouterr().out)["data"]

    assert read_route() == {"api": tianshu_bridge.GONGGONG_API, "repository": "gonggong.git"}
    monkeypatch.setenv("TIANXUAN_API", "http://127.0.0.1:8128")
    assert read_route() == {"api": "configured", "repository": ""}
    monkeypatch.setenv("TIANXUAN_GIT_REPO", "local.git")
    assert read_route() == {"api": "configured", "repository": "local.git"}
    monkeypatch.delenv("TIANXUAN_API")
    assert read_route() == {"api": tianshu_bridge.LOCAL_API, "repository": "local.git"}
    monkeypatch.delenv("TIANXUAN_GIT_REPO")
    # A materialized project inside the checkout owns its own source identity.
    marker = gonggong_project / ".duobao-source.json"
    marker.write_text("{}", encoding="utf-8")
    assert read_route() == {"api": tianshu_bridge.LOCAL_API, "repository": ""}
    marker.unlink()
    subprocess.run(
        [
            "git",
            "-C",
            str(gonggong_project),
            "remote",
            "set-url",
            "origin",
            "https://elsewhere.invalid/zhzyx/nightmarish-spooky-sorceryze.git",
        ],
        check=True,
    )
    (gonggong_project / "work-items.json").write_text('{"repository":"zhzyx/nightmarish-spooky-sorceryze"}')
    assert read_route() == {"api": tianshu_bridge.LOCAL_API, "repository": ""}


def test_release_snapshot_requires_a_real_checkout(gonggong_project, monkeypatch, capsys):
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(gonggong_project), *arguments], text=True).strip()

    git("remote", "remove", "origin")
    git(
        "-c",
        "user.name=Release fixture",
        "-c",
        "user.email=release@example.invalid",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "Import verified GongGong release snapshot",
    )
    git("config", "--local", "gonggong.releaseSnapshot", git("rev-parse", "HEAD"))
    monkeypatch.setattr(tianshu_bridge, "urlopen", lambda *_a, **_kw: pytest.fail("unexpected network access"))
    for command in (
        ["duobao-route"],
        ["branch-tip", "--branch", "main"],
        ["workcopy-diff", "--project", str(gonggong_project)],
    ):
        assert tianshu_bridge.main(["--workspace", str(gonggong_project), *command]) == 1
        assert "真实共工 Git 工作副本" in json.loads(capsys.readouterr().out)["error"]
    monkeypatch.setenv("TIANXUAN_API", tianshu_bridge.GONGGONG_API)
    monkeypatch.setenv("TIANXUAN_GIT_REPO", "gonggong.git")
    assert tianshu_bridge.main(["--workspace", str(gonggong_project), "duobao-route"]) == 1
    assert "真实共工 Git 工作副本" in json.loads(capsys.readouterr().out)["error"]


def test_project_branch_readback_uses_the_bound_repository(gonggong_project, monkeypatch, capsys):
    calls = []

    def read_tip(request, timeout):
        calls.append(request.full_url)
        return _Response({"branch": "main", "sha": "a" * 40})

    monkeypatch.setattr(tianshu_bridge, "urlopen", read_tip)
    command = ["--workspace", str(gonggong_project), "branch-tip", "--branch", "main"]
    assert tianshu_bridge.main(command) == 0
    assert calls == [tianshu_bridge.GONGGONG_API + "/api/v1/git/repos/gonggong.git/branch-tip?branch=main"]
    capsys.readouterr()
    assert tianshu_bridge.main(command + ["--repo-name", "other.git"]) == 1
    assert len(calls) == 1 and "gonggong.git" in json.loads(capsys.readouterr().out)["error"]


def test_automatic_public_route_uses_only_origin_bound_identity(gonggong_project, monkeypatch, tmp_path, capsys):
    calls = []

    def read_tip(api, method, path, *, actor, token, **kwargs):
        calls.append((api, method, bool(actor), token))
        return {"branch": "main", "sha": "a" * 40}

    monkeypatch.setattr(tianshu_bridge, "_request", read_tip)
    monkeypatch.setenv("TIANXUAN_TOKEN_CACHE", str(tmp_path / "private-cache"))
    monkeypatch.setenv("TIANXUAN_TOKEN", "fixture-loopback")
    command = ["--workspace", str(gonggong_project), "branch-tip", "--branch", "main"]
    assert tianshu_bridge.main(command) == 1 and not calls
    assert "未绑定" in json.loads(capsys.readouterr().out)["error"]
    monkeypatch.delenv("TIANXUAN_TOKEN")
    monkeypatch.setenv("TIANXUAN_IDENTITY_PROVIDER", "fixture")
    monkeypatch.setenv("TIANXUAN_IDENTITY_SUBJECT", "fixture-user")
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "fixture-local-only")
    tianshu_bridge._write_cached_token(tianshu_bridge.LOCAL_API, "fixture", "fixture-user", "fixture-old-cache")
    assert tianshu_bridge.main(command) == 1 and not calls
    assert "未绑定" in json.loads(capsys.readouterr().out)["error"]
    assert tianshu_bridge.main(["--token", "fixture-explicit", *command]) == 0
    assert calls[-1] == (tianshu_bridge.GONGGONG_API, "GET", False, "fixture-explicit")
    tianshu_bridge._write_cached_token(tianshu_bridge.GONGGONG_API, "fixture", "fixture-user", "fixture-public-cache")
    assert tianshu_bridge.main(command) == 0
    assert calls[-1] == (tianshu_bridge.GONGGONG_API, "GET", False, "fixture-public-cache")
    monkeypatch.setenv("TIANXUAN_API", tianshu_bridge.GONGGONG_API)
    monkeypatch.setenv("TIANXUAN_TOKEN", "fixture-bound-launcher")
    assert tianshu_bridge.main(command) == 0
    assert calls[-1] == (tianshu_bridge.GONGGONG_API, "GET", False, "fixture-bound-launcher")
    for name in ("TIANXUAN_API", "TIANXUAN_TOKEN", "TIANXUAN_IDENTITY_PROVIDER", "TIANXUAN_IDENTITY_SECRET"):
        monkeypatch.delenv(name)
    monkeypatch.setenv("TIANXUAN_ACTOR", "fixture-local-actor")
    assert tianshu_bridge.main(command) == 0
    assert calls[-1] == (tianshu_bridge.GONGGONG_API, "GET", False, "")


def test_commit_review_and_delivery_share_project_route(gonggong_project, monkeypatch):
    import selected_commit

    request_id = "mr_" + "a" * 64
    paths = []

    def service(api, method, path, **kwargs):
        assert api == tianshu_bridge.GONGGONG_API and method == "POST"
        paths.append(path)
        return {"id": request_id}

    def submit(project, target, body, publish, lookup):
        assert project == gonggong_project and target[:2] == [tianshu_bridge.GONGGONG_API, "gonggong.git"]
        return publish(body)

    monkeypatch.setattr(tianshu_bridge, "_request", service)
    monkeypatch.setattr(selected_commit, "submit", submit)
    request = gonggong_project / "selection.json"
    request.write_text('{"repo":""}', encoding="utf-8")
    assert tianshu_bridge.main(["workcopy-submit", "--project", str(gonggong_project), "--request", str(request)]) == 0
    for action, extra in (("merge-review", ["--decision", "APPROVED"]), ("merge-deliver", [])):
        assert (
            tianshu_bridge.main(["--workspace", str(gonggong_project), action, "--request-id", request_id, *extra]) == 0
        )
    root = "/api/v1/git/repos/gonggong.git/"
    assert paths == [
        root + "selected-commits",
        root + f"merge-requests/{request_id}/review",
        root + f"merge-requests/{request_id}/deliver",
    ]
    request.write_text('{"repo":"elsewhere.git"}', encoding="utf-8")
    assert tianshu_bridge.main(["workcopy-submit", "--project", str(gonggong_project), "--request", str(request)]) == 1
    assert len(paths) == 3


class _Response:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> Literal[False]:
        return False

    def read(self) -> bytes:
        return self._body


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[Request]:
    calls: list[Request] = []

    def fake(request: Request, timeout: int) -> _Response:
        calls.append(request)
        return _Response({"system": "tianshu", "external_id": "issue/1", "documents": []})

    monkeypatch.setattr(tianshu_bridge, "urlopen", fake)
    return calls


def test_context_sends_actor_and_query(monkeypatch, capsys) -> None:
    calls = _capture(monkeypatch)
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--actor",
        "usr_1",
        "context",
        "--external-id",
        "https://github.com/o/r/issues/1",
    ])
    assert code == 0
    assert len(calls) == 1
    request = calls[0]
    assert request.get_method() == "GET"
    assert "external_id=https%3A%2F%2Fgithub.com%2Fo%2Fr%2Fissues%2F1" in request.full_url
    assert request.headers["X-actor"] == "usr_1"
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"]["external_id"] == "issue/1"


def test_publish_posts_requirement_and_tickets(monkeypatch, capsys) -> None:
    calls = _capture(monkeypatch)
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--actor",
        "usr_1",
        "publish",
        "--external-id",
        "https://github.com/o/r/issues/1",
        "--request-id",
        "req-1",
        "--title",
        "需求",
        "--outcome",
        "目标",
        "--scope",
        "范围",
        "--acceptance",
        "验收",
        "--ticket",
        "任务甲",
        "--ticket",
        "任务乙",
    ])
    assert code == 0
    request = calls[0]
    assert request.get_method() == "POST"
    assert request.full_url.endswith("/api/v1/requirements/from-external")
    payload = request.data
    assert isinstance(payload, bytes)
    body = json.loads(payload.decode("utf-8"))
    assert body["external_id"] == "https://github.com/o/r/issues/1"
    assert [ticket["title"] for ticket in body["tickets"]] == ["任务甲", "任务乙"]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_error_is_reported_and_result_written(monkeypatch, tmp_path, capsys) -> None:
    def failing(request: Request, timeout: int) -> _Response:
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            hdrs=Message(),
            fp=io.BytesIO(b'{"detail":"actor is required"}'),
        )

    monkeypatch.setattr(tianshu_bridge, "urlopen", failing)
    result = tmp_path / "result.json"
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--result",
        str(result),
        "context",
        "--external-id",
        "issue/1",
    ])
    assert code == 1
    envelope = json.loads(result.read_text(encoding="utf-8"))
    assert envelope["ok"] is False
    assert "403" in envelope["error"]
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_sync_advances_ticket_to_done(monkeypatch, capsys) -> None:
    calls: list[Request] = []
    seen: list[str] = []

    def fake(request: Request, timeout: int) -> _Response:
        calls.append(request)
        if "/external-context" in request.full_url:
            return _Response({
                "issues": [
                    {
                        "id": "iss_1",
                        "title": "任务甲",
                        "status": "backlog",
                        "parent_id": "iss_parent",
                    }
                ]
            })
        payload = request.data
        assert isinstance(payload, bytes)
        body = json.loads(payload.decode("utf-8"))
        seen.append(body["to_status"])
        return _Response({
            "id": "iss_1",
            "title": "任务甲",
            "status": body["to_status"],
            "parent_id": "iss_parent",
        })

    monkeypatch.setattr(tianshu_bridge, "urlopen", fake)
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--actor",
        "usr_1",
        "sync",
        "--external-id",
        "issue/1",
        "--done",
        "任务甲",
    ])
    assert code == 0
    assert seen == ["planned", "in-progress", "in-review", "done"]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"]["updated"][0]["status"] == "done"


def test_identity_resolves_token_before_command(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TIANXUAN_TOKEN_CACHE", "off")
    calls: list[Request] = []

    def fake(request: Request, timeout: int) -> _Response:
        calls.append(request)
        if request.full_url.endswith("/api/v1/identity/resolve"):
            return _Response({"token": "session-token", "user_id": "usr_1"})
        return _Response({"documents": []})

    monkeypatch.setattr(tianshu_bridge, "urlopen", fake)
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--identity-provider",
        "tianshu",
        "--identity-subject",
        "gh_1",
        "--identity-secret",
        "shared",
        "context",
        "--external-id",
        "issue/1",
    ])
    assert code == 0
    payload = calls[0].data
    assert isinstance(payload, bytes)
    body = json.loads(payload.decode("utf-8"))
    assert body == {"provider": "tianshu", "subject": "gh_1", "secret": "shared"}
    assert calls[1].headers["Authorization"] == "Bearer session-token"
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_sync_reports_ambiguous_titles(monkeypatch, capsys) -> None:
    calls: list[Request] = []

    def fake(request: Request, timeout: int) -> _Response:
        calls.append(request)
        return _Response({
            "issues": [
                {"id": "iss_1", "title": "重复", "status": "backlog", "parent_id": "p"},
                {"id": "iss_2", "title": "重复", "status": "backlog", "parent_id": "p"},
            ]
        })

    monkeypatch.setattr(tianshu_bridge, "urlopen", fake)
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--actor",
        "usr_1",
        "sync",
        "--external-id",
        "issue/1",
        "--done",
        "重复",
    ])
    assert code == 0
    assert len(calls) == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["updated"] == []
    assert "ambiguous" in envelope["data"]["missing"][0]


def test_identity_token_is_cached(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("TIANXUAN_TOKEN_CACHE", str(tmp_path / "cache"))
    resolve_calls = 0

    def fake(request: Request, timeout: int) -> _Response:
        nonlocal resolve_calls
        if request.full_url.endswith("/api/v1/identity/resolve"):
            resolve_calls += 1
            return _Response({"token": "cached-token"})
        return _Response({"documents": []})

    monkeypatch.setattr(tianshu_bridge, "urlopen", fake)
    args = [
        "--api",
        "http://api.example",
        "--identity-provider",
        "tianshu",
        "--identity-subject",
        "gh_cache",
        "--identity-secret",
        "shared",
        "context",
        "--external-id",
        "issue/1",
    ]
    assert tianshu_bridge.main(args) == 0
    assert tianshu_bridge.main(args) == 0
    assert resolve_calls == 1
    capsys.readouterr()


def test_historical_issue_reads_exact_source_and_pins_body_pages(monkeypatch, capsys):
    from urllib.parse import parse_qs, urlsplit

    requests = []
    revision = "e" * 64
    sid = "github:team/repo/issue/89"

    def fake(request: Request, timeout: int) -> _Response:
        address = urlsplit(request.full_url)
        query = parse_qs(address.query, strict_parsing=True)
        assert query["source_id"] == [sid] and query["project"] == ["example"]
        assert request.get_method() == "GET" and request.headers["Authorization"] == "Bearer bearer"
        requests.append(address.path)
        if address.path.endswith("/detail"):
            return _Response({
                "revision": revision,
                "record": {
                    "source_id": sid,
                    "kind": "issue",
                    "truncated": True,
                    "content": {"state": "closed", "title": "Old"},
                },
            })
        assert query["revision"] == [revision]
        offset = int(query["offset"][0])
        return _Response({"text": "完整" if offset == 0 else "正文", "next_offset": 2 if offset == 0 else None})

    monkeypatch.setattr(tianshu_bridge, "urlopen", fake)
    assert (
        tianshu_bridge.main([
            "--token",
            "bearer",
            "historical-issue",
            "--project",
            "example",
            "--source-id",
            "https://github.com/team/repo/issues/89",
        ])
        == 0
    )
    data = json.loads(capsys.readouterr().out)["data"]
    assert data == {"source_id": sid, "title": "Old", "state": "closed", "body": "完整正文", "revision": revision}
    assert requests == ["/api/v1/migration/history/" + name for name in ("detail", "body", "body")]


def test_historical_issue_rejects_non_issue(monkeypatch, capsys):
    sid = "github:team/repo/comment/89"
    monkeypatch.setattr(
        tianshu_bridge,
        "urlopen",
        lambda request, timeout: _Response({
            "record": {"source_id": sid, "kind": "comment", "content": {"body": "comment"}},
        }),
    )
    assert tianshu_bridge.main(["historical-issue", "--project", "example", "--source-id", sid]) == 1
    assert "未指向历史工单" in json.loads(capsys.readouterr().out)["error"]
