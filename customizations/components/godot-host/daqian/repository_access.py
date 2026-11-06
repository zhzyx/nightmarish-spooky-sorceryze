"""Daqian access belongs to authenticated collaborators of the bound Git origin."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "issue-workorders"))
import issue_gate
import work_items


class AccessDenied(ValueError):
    pass


class SessionChanged(AccessDenied):
    pass


if not os.environ.get("GONGGONG_GH") and not shutil.which("gh"):
    if os.name == "nt":
        candidates = [Path(os.environ.get("ProgramFiles","C:/Program Files"))/"GitHub CLI"/"gh.exe"]
    else:
        candidates = [Path.home()/".local/bin/gh",Path("/opt/homebrew/bin/gh"),Path("/usr/local/bin/gh")]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate,os.X_OK):
            os.environ["GONGGONG_GH"]=str(candidate)
            break


def configured_login():
    # Local-only offline cache selection. Environment tokens override this config;
    # their identity cannot be established offline.
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return ""
    try:
        return work_items.gh("config","get","user","--host","github.com").strip()
    except work_items.GitHubCommandError:
        return ""


def refresh_collaborator(root):
    """Read the viewer and their explicit repository affiliations in one response per page."""
    repo = work_items.config(root)[0]["repository"]
    issue_gate.check_repository(root, repo)
    query = """query($cursor:String) {
      viewer { login databaseId repositories(first:100, after:$cursor,
        affiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER],
        ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]) {
        nodes { nameWithOwner databaseId } pageInfo { endCursor hasNextPage }
      } }
    }"""
    cursor_args = []
    first_user = None
    seen = set()
    while True:
        try:
            response = json.loads(work_items.gh("api", "graphql", "-f", "query=" + query, *cursor_args))
        except work_items.GitHubCommandError as error:
            # Some installations grant a token REST access only.
            if error.http_status in (403, 404):
                return collaborator(root)
            raise
        viewer = response["data"]["viewer"]
        user_id = viewer["databaseId"]
        if type(user_id) is not int or not isinstance(viewer["login"], str) or not viewer["login"]:
            raise AccessDenied("无法核实当前 GitHub 账号")
        if first_user is not None and first_user != user_id:
            raise AccessDenied("核验期间 GitHub 账号已切换")
        first_user = user_id
        repos = viewer["repositories"]
        for row in repos["nodes"]:
            if row["nameWithOwner"].casefold() == repo.casefold() and type(row["databaseId"]) is int:
                return {"login": viewer["login"], "user_id": str(user_id), "repo": repo, "repo_id": str(row["databaseId"])}
        page = repos["pageInfo"]
        if not page["hasNextPage"]:
            raise AccessDenied("当前账号未获此仓库的协作资格")
        cursor = page["endCursor"]
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise AccessDenied("无法核实当前仓库的协作资格")
        seen.add(cursor)
        cursor_args = ["-f", "cursor=" + cursor]


def session_path(nonce):
    if not re.fullmatch(r"[a-f0-9]{32}", nonce):
        raise AccessDenied("编辑器会话无效")
    # Local user-owned state, outside the repository. A fresh capability is minted
    # in memory by each editor. Only its direct children share the same receipt.
    cache = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "gonggong" / "editor-sessions"
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    return cache / f"{os.getppid()}-{nonce}.json"


def session_actor(root, nonce, *, allow_login=False):
    if not nonce:
        return collaborator(root)
    root = Path(root).resolve()
    repo = work_items.config(root)[0]["repository"]
    issue_gate.check_repository(root, repo)
    path = session_path(nonce)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    local = hashlib.sha256(token.encode()).hexdigest() if token else configured_login()
    # The binding is process-local in scope. No GitHub credential is saved.
    binding = hashlib.sha256(json.dumps([nonce, str(root), repo, local]).encode()).hexdigest()
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        prior = {}
    if local and prior.get("binding") == binding:
        return prior["actor"]
    if not allow_login:
        raise SessionChanged("编辑器登录账号或工作区已切换，请刷新工单")
    actor = refresh_collaborator(root)
    if not token and local and local.casefold() != actor["login"].casefold():
        raise AccessDenied("核验期间 GitHub 账号已切换")
    actor["verified_at_unix"] = time.time()
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, encoding="utf-8") as stream:
        json.dump({"binding":binding,"actor":actor}, stream)
    os.replace(stream.name, path)
    return actor


def collaborator(root):
    root=Path(root).resolve()
    repo=work_items.config(root)[0]["repository"]
    issue_gate.check_repository(root,repo)
    user=json.loads(work_items.gh("api","user"))
    if not isinstance(user.get("login"),str) or not user["login"] or type(user.get("id")) is not int:
        raise AccessDenied("无法核实当前 GitHub 账号")
    # /user/repos enumerates explicitly accessible repos including inherited team
    # membership. Public read access, watchers and prior authorship do not grant entry.
    # Unlike checking /collaborators/:username this works for read-only collaborators.
    query='.[] | select((.full_name | ascii_downcase) == '+json.dumps(repo.lower())+') | .id'
    matched=work_items.gh("api","user/repos?affiliation=owner,collaborator,organization_member&per_page=100",
                          "--paginate","--jq",query)
    ids=[json.loads(line) for line in matched.splitlines() if line.strip()]
    if not isinstance(ids,list) or len(ids)!=1 or type(ids[0]) is not int:
        raise AccessDenied("当前账号未获此仓库的协作资格")
    if work_items.gh("api","user","--jq",".id").strip()!=str(user["id"]):
        raise AccessDenied("核验期间 GitHub 账号已切换")
    return {"login":user["login"],"user_id":str(user["id"]),"repo":repo,"repo_id":str(ids[0])}
