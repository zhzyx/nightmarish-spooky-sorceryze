"""天璇 HTTP 适配层的请求模型。

只描述传输格式与必填项；业务校验（例如注册字段非空、文档版本冲突、
工单状态机）仍由 tianxuan_core 负责，本层不复制领域规则。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class DocCreateRequest(BaseModel):
    """创建文曲 Markdown 文档。"""

    title: str
    body_md: str = ""
    lang: str = "zh"
    kind: str = "doc"
    request_id: str | None = None


class DocUpdateRequest(BaseModel):
    """按版本号更新文档正文；版本不匹配由领域层抛 VersionConflict。"""

    body_md: str
    expected_version: int
    title: str | None = None
    status: str | None = None


class RequirementCreateRequest(BaseModel):
    """创建偃师需求文档。"""

    request_id: str
    title: str
    outcome: str
    scope: str
    acceptance: str


class TicketSpec(BaseModel):
    """需求下的一张工单。"""

    title: str
    acceptance: str = ""
    type: str = "task"
    priority: str = "normal"


class TicketsRequest(BaseModel):
    """从需求文档拆分工单。"""

    tickets: list[TicketSpec] = Field(default_factory=list)


class IssueTransitionRequest(BaseModel):
    """司南工单状态迁移。"""

    to_status: str
