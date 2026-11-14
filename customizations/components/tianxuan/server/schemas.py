"""天璇 HTTP 适配层的请求模型。

只描述传输格式与必填项；业务校验（例如注册字段非空、文档版本冲突、
工单状态机）仍由 tianxuan_core 负责，本层不复制领域规则。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """注册组织与首个用户。"""

    tenant_name: str
    email: str
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    """邮箱密码登录。"""

    email: str
    password: str


class MemberCreateRequest(BaseModel):
    """管理员在租户内添加成员。"""

    email: str
    password: str
    name: str = ""
    role: str = "editor"


class RoleUpdateRequest(BaseModel):
    """修改成员角色。"""

    role: str


class InviteCreateRequest(BaseModel):
    """管理员创建邀请。"""

    email: str
    role: str = "editor"


class InviteAcceptRequest(BaseModel):
    """受邀者凭邀请码加入租户。"""

    code: str
    password: str
    name: str = ""


class RepoCreateRequest(BaseModel):
    """在 Gitea 中创建仓库。"""

    name: str
    private: bool = True
    default_branch: str = "main"


class PullRequestCreateRequest(BaseModel):
    """在 Gitea 仓库内创建 Pull Request。"""

    title: str
    head: str
    base: str
    body: str = ""


class PullRequestMergeRequest(BaseModel):
    """合并 Pull Request 的方式。"""

    method: str = "merge"


class MergeQueueCreateRequest(BaseModel):
    """多宝合入队列候选。"""

    repo: str
    source: str
    target: str
    title: str = ""
    priority: int = 0


class DocCreateRequest(BaseModel):
    """创建文曲 Markdown 文档。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    body_md: str = ""
    lang: str = "zh"
    kind: str = "doc"
    request_id: str | None = None

    call_id: str | None = Field(default=None, min_length=1, max_length=256)


class DocUpdateRequest(BaseModel):
    """按版本号更新文档正文；版本不匹配由领域层抛 VersionConflict。"""

    model_config = ConfigDict(extra="forbid")

    body_md: str
    expected_version: int
    title: str | None = None
    status: str | None = None

    call_id: str | None = Field(default=None, min_length=1, max_length=256)


class DocMergeRequest(BaseModel):
    """离线草稿三方合并：base 为编辑起点，local 为本地草稿。"""

    base_md: str
    local_md: str
    expected_version: int


class DocPatchOperation(BaseModel):
    """单次唯一匹配的文本替换。"""

    find: str
    replace: str


class DocPatchRequest(BaseModel):
    """按版本号对文档做结构化补丁，供 AI 以最小 token 编辑。"""

    expected_version: int
    patches: list[DocPatchOperation]


class DocVisibilityRequest(BaseModel):
    """切换文档可见性：tenant 或 private。"""

    visibility: str


class DocShareRequest(BaseModel):
    """把私有文档共享给同租户成员。"""

    user_id: str
    permission: str = "read"


class RequirementCreateRequest(BaseModel):
    """创建偃师需求文档。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    title: str
    outcome: str
    scope: str
    acceptance: str
    lang: str = "zh"

    call_id: str | None = Field(default=None, min_length=1, max_length=256)


class RequirementCommitRequest(BaseModel):
    """把需求 Markdown 提交到受控本地 Git 仓库。"""

    repo: str
    branch: str = "main"
    message: str | None = None
    author_name: str = "Tianxuan"
    author_email: str = "tianxuan@example.invalid"


class TicketSpec(BaseModel):
    """需求下的一张工单。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    acceptance: str = ""
    type: str = "task"
    priority: str = "normal"
    body_md: str = ""


class TicketsRequest(BaseModel):
    """从需求文档拆分工单。"""

    model_config = ConfigDict(extra="forbid")

    tickets: list[TicketSpec] = Field(default_factory=list)

    call_id: str | None = Field(default=None, min_length=1, max_length=256)


class ExternalLinkRequest(BaseModel):
    """把天枢/外部工单绑定到天璇目标。"""

    model_config = ConfigDict(extra="forbid")

    system: str
    external_id: str
    target_type: str
    target_id: str


class ExternalRequirementRequest(BaseModel):
    """从天枢工单创建天璇需求与工单树。"""

    model_config = ConfigDict(extra="forbid")

    system: str
    external_id: str
    request_id: str
    title: str
    outcome: str
    scope: str
    acceptance: str
    tickets: list[TicketSpec] = Field(default_factory=list)


class IdentityLinkRequest(BaseModel):
    """管理员绑定外部身份到本地用户。"""

    model_config = ConfigDict(extra="forbid")

    provider: str
    subject: str
    user_id: str


class IdentityResolveRequest(BaseModel):
    """按适配器校验外部身份并换取天璇会话。"""

    model_config = ConfigDict(extra="forbid")

    provider: str
    subject: str
    secret: str = ""


class IssueTransitionRequest(BaseModel):
    """司南工单状态迁移。"""

    model_config = ConfigDict(extra="forbid")

    to_status: str

    call_id: str | None = Field(default=None, min_length=1, max_length=256)


class IssueCommentCreateRequest(BaseModel):
    """司南工单评论；正文非空由领域层校验。"""

    body: str


class CommentCreateRequest(BaseModel):
    """文曲文档评论。"""

    body: str
    parent_id: str | None = None


class CommentResolveRequest(BaseModel):
    """标记评论已解决或重新打开。"""

    resolved: bool = True
