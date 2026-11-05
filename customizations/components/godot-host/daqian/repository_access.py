"""Daqian access belongs to authenticated collaborators of the bound Git origin."""
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "issue-workorders"))
import issue_gate
import work_items


class AccessDenied(ValueError):
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
