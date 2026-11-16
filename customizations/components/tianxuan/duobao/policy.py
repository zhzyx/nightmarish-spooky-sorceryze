"""多宝仓库策略：保护分支、角色授权与合入路径判定。

这是一个纯函数模块：不导入 Git、HTTP 或数据库依赖，因此合入队列、Gitea 合并入口、
CLI 与测试可以共用同一套判定，并在调用方执行前给出可回读的结果。

判定约定：

- 角色沿用租户角色 ``admin`` / ``editor`` / ``viewer``，viewer 只读；
- 受保护分支只能经多宝合入队列写入，``direct`` 路径（包括绕过队列的外部合并）
  一律拒绝；
- 创建或删除受保护分支只允许 ``admin``；
- 未配置保护模式时行为保持兼容：editor/admin 可直接合入普通分支。
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable, Mapping, Sequence

ROLES = ("admin", "editor", "viewer")
"""已知租户角色，权限从高到低。"""

MERGE_ROLES = frozenset({"admin", "editor"})
"""可以发起合入的角色；viewer 只读。"""

BRANCH_MUTATION_ROLES = frozenset({"admin", "editor"})
"""可以创建或删除普通分支的角色。"""

MERGE_PATHS = frozenset({"direct", "queue"})
"""``direct`` 为绕过合入队列的直接合入；``queue`` 为多宝合入队列。"""

BRANCH_OPERATIONS = frozenset({"create", "delete"})
"""分支变更操作，用于区分普通分支与受保护分支的授权。"""

MAX_PATTERN_LENGTH = 200
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class PolicyError(ValueError):
    """策略输入不合法。"""


class ProtectedBranchError(PolicyError):
    """目标分支受保护，当前路径或角色不允许写入。"""


class RoleDenied(PolicyError):
    """当前角色没有该操作权限。"""


class ReviewRequired(PolicyError):
    """合入所需的独立批准数量不足。"""


class ChecksRequired(PolicyError):
    """合入所需的提交检查未全部通过。"""


def approved_reviewers(reviews: Sequence[Mapping[str, object]]) -> frozenset[str]:
    """返回最后一次评审状态为 APPROVED 的评审者集合。

    Gitea 的评审列表按时间顺序返回；同一评审者以最后一次状态为准（例如先
    REQUEST_CHANGES 后 APPROVED 视为通过）。用户名大小写不敏感，空用户名或
    非法状态被忽略，不把未知数据当作批准。
    """
    latest: dict[str, str] = {}
    for review in reviews:
        if not isinstance(review, Mapping):
            raise PolicyError(f"review entry must be a mapping: {review!r}")
        user = review.get("user")
        state = review.get("state")
        if not isinstance(user, str) or not user.strip() or not isinstance(state, str):
            continue
        latest[user.strip().casefold()] = state.strip().upper()
    return frozenset(user for user, state in latest.items() if state == "APPROVED")


def parse_protected_branches(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """把配置解析为保护分支模式元组。

    ``value`` 可以是逗号分隔的环境变量字符串，也可以是模式序列；支持
    :func:`fnmatch.fnmatchcase` 通配符（例如 ``release/*``）。空项被忽略，重复模式
    按首次出现保序去重。非法模式在启用任何保护前就拒绝，避免把拼写错误当成
    “没有保护”。
    """
    if value is None:
        return ()
    if isinstance(value, str):
        raw_items: Iterable[object] = value.split(",")
    elif isinstance(value, Iterable):
        raw_items = value
    else:
        raise PolicyError(f"protected branch patterns must be a string or iterable: {value!r}")
    patterns: list[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            raise PolicyError(f"protected branch pattern must be a string: {item!r}")
        pattern = item.strip()
        if not pattern:
            continue
        if len(pattern) > MAX_PATTERN_LENGTH:
            raise PolicyError(f"protected branch pattern is too long: {pattern!r}")
        if _CONTROL_CHARACTERS.search(pattern):
            raise PolicyError(f"protected branch pattern contains control characters: {pattern!r}")
        if pattern.startswith("/") or pattern.endswith("/"):
            raise PolicyError(f"protected branch pattern must not start or end with '/': {pattern!r}")
        if ".." in pattern:
            raise PolicyError(f"protected branch pattern must not contain '..': {pattern!r}")
        if pattern not in patterns:
            patterns.append(pattern)
    return tuple(patterns)


def is_protected(branch: str, patterns: Sequence[str]) -> bool:
    """判断分支是否命中任一保护模式；大小写敏感，与 Git ref 语义一致。"""
    if not isinstance(branch, str) or not branch:
        raise PolicyError(f"branch must be a non-empty string: {branch!r}")
    return any(fnmatch.fnmatchcase(branch, pattern) for pattern in patterns)


def ensure_merge_allowed(
    target: str,
    patterns: Sequence[str],
    *,
    actor_role: str,
    path: str = "direct",
) -> dict[str, object]:
    """校验一次合入并返回可回读的策略判定。

    - 角色必须是已知角色，且不能是 viewer；
    - ``path=direct`` 不得写入受保护分支，受保护分支只能经合入队列；
    - ``path=queue`` 允许 editor/admin 合入受保护分支。
    """
    if actor_role not in ROLES:
        raise PolicyError(f"unknown role: {actor_role!r}; expected one of {', '.join(ROLES)}")
    if path not in MERGE_PATHS:
        raise PolicyError(f"unknown merge path: {path!r}; expected one of {', '.join(sorted(MERGE_PATHS))}")
    protected = is_protected(target, patterns)
    if actor_role not in MERGE_ROLES:
        raise RoleDenied(f"role {actor_role!r} cannot merge into {target!r}")
    if protected and path == "direct":
        raise ProtectedBranchError(
            f"branch {target!r} is protected; merge through the Duobao queue instead of a direct merge"
        )
    return {"target": target, "protected": protected, "path": path, "actor_role": actor_role}


def ensure_pr_merge_allowed(
    target: str,
    patterns: Sequence[str],
    *,
    actor_role: str,
    approvals: Sequence[str] | frozenset[str],
    required_approvals: int,
    path: str = "direct",
) -> dict[str, object]:
    """在合入校验上追加独立批准数量要求，并通过返回可回读的判定。

    ``approvals`` 是评审者标识集合（通常来自 :func:`approved_reviewers`）；
    ``required_approvals`` 默认可为 0，表示未启用评审门禁。
    """
    decision = ensure_merge_allowed(target, patterns, actor_role=actor_role, path=path)
    if isinstance(required_approvals, bool) or not isinstance(required_approvals, int) or required_approvals < 0:
        raise PolicyError(f"required approvals must be a non-negative integer: {required_approvals!r}")
    approved = len(set(approvals))
    if approved < required_approvals:
        raise ReviewRequired(f"merge into {target!r} requires {required_approvals} approving review(s); got {approved}")
    return {**decision, "required_approvals": required_approvals, "approvals": approved}


def ensure_checks_passed(
    statuses: Sequence[Mapping[str, object]],
    required_checks: Sequence[str],
) -> dict[str, object]:
    """按 context 取最后一次提交状态，要求每个必需检查均为 ``success``。

    缺少检查、检查失败或处于 pending 均拒绝；``required_checks`` 为空时只返回
    空摘要，保持未启用检查门禁的部署兼容。
    """
    latest: dict[str, str] = {}
    for status in statuses:
        if not isinstance(status, Mapping):
            raise PolicyError(f"commit status entry must be a mapping: {status!r}")
        context = status.get("context")
        state = status.get("state")
        if isinstance(context, str) and context.strip() and isinstance(state, str):
            latest[context.strip()] = state.strip().lower()
    missing: list[str] = []
    failing: list[str] = []
    for context in required_checks:
        if not isinstance(context, str) or not context.strip():
            raise PolicyError(f"required check names must be non-empty strings: {context!r}")
        state = latest.get(context.strip())
        if state is None:
            missing.append(context.strip())
        elif state != "success":
            failing.append(f"{context.strip()}={state}")
    if missing or failing:
        raise ChecksRequired(f"required checks are not satisfied: missing={missing}, failing={failing}")
    return {
        "required_checks": [context.strip() for context in required_checks],
        "contexts": {context.strip(): latest[context.strip()] for context in required_checks},
    }


def ensure_branch_mutation_allowed(
    branch: str,
    patterns: Sequence[str],
    *,
    actor_role: str,
    operation: str,
) -> dict[str, object]:
    """校验分支创建或删除，并返回可回读的策略判定。

    普通分支允许 editor/admin；受保护分支只允许 admin。viewer 与未知角色一律拒绝。
    """
    if actor_role not in ROLES:
        raise PolicyError(f"unknown role: {actor_role!r}; expected one of {', '.join(ROLES)}")
    if operation not in BRANCH_OPERATIONS:
        raise PolicyError(
            f"unknown branch operation: {operation!r}; expected one of {', '.join(sorted(BRANCH_OPERATIONS))}"
        )
    protected = is_protected(branch, patterns)
    if actor_role not in BRANCH_MUTATION_ROLES:
        raise RoleDenied(f"role {actor_role!r} cannot {operation} branch {branch!r}")
    if protected and actor_role != "admin":
        raise ProtectedBranchError(f"branch {branch!r} is protected; only an admin can {operation} it")
    return {"branch": branch, "protected": protected, "operation": operation, "actor_role": actor_role}
