import type { Metadata } from "next";
import Link from "next/link";
import { Icon, type IconName } from "@/components/Icon";
import { IdentityBindings } from "@/components/IdentityBindings";
import { fetchGiteaStatus, fetchHealth, type ApiGiteaStatus } from "@/lib/api";

export const metadata: Metadata = {
  title: "设置",
};

export const dynamic = "force-dynamic";

const settingsNav: { href: string; label: string; icon: IconName }[] = [
  { href: "#profile", label: "个人资料", icon: "users" },
  { href: "#appearance", label: "外观", icon: "eye" },
  { href: "#workspace", label: "工作区", icon: "home" },
  { href: "#ai", label: "AI 与模型", icon: "sparkles" },
  { href: "#notifications", label: "通知", icon: "bell" },
  { href: "#members", label: "成员与权限", icon: "lock" },
  { href: "#security", label: "安全与数据", icon: "alert" },
];

const members = [
  { name: "Sail", handle: "sail", role: "管理员", tone: "jade", status: "在线" },
  { name: "文曲", handle: "wenqu", role: "Agent · 文档", tone: "jade", status: "运行中" },
  { name: "偃师", handle: "yanshi", role: "Agent · 需求", tone: "gold", status: "运行中" },
  { name: "司南", handle: "sinan", role: "Agent · 工单", tone: "cinnabar", status: "运行中" },
  { name: "多宝", handle: "duobao", role: "Agent · 仓库", tone: "gold", status: "空闲" },
];

export default async function SettingsPage() {
  const actor = process.env.TIANXUAN_ACTOR ?? "";
  let apiOnline = false;
  let gitea: ApiGiteaStatus | null = null;
  try {
    await fetchHealth();
    apiOnline = true;
  } catch {
    apiOnline = false;
  }
  try {
    gitea = await fetchGiteaStatus();
  } catch {
    gitea = null;
  }

  return (
    <div className="page-stack settings-page">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            ORGANIZATION · SETTINGS
          </p>
          <h1>
            设置<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            只在这里放真正需要决定的选项：如何称呼彼此、如何呈现内容，以及哪些动作必须等一个人说“可以”。
          </p>
        </div>
        <div className="page-actions">
          <span className="settings-prototype">
            <span className="live-dot" aria-hidden="true" />
            原型模式 · 不写回服务
          </span>
          <Link className="btn btn-ghost" href="/docs/onboarding">
            <Icon name="docs" size={16} />
            协作指南
          </Link>
        </div>
      </header>

      <section className="panel" aria-labelledby="system-status-title">
        <div className="section-heading">
          <div>
            <p className="section-kicker">SYSTEM · STATUS</p>
            <h2 id="system-status-title">系统状态</h2>
          </div>
          <span className="section-note">服务端实时读取</span>
        </div>
        <div className="reading-list live-list">
          <div className="reading-item">
            <span className="reading-index">API</span>
            <span className="reading-copy">
              <strong>{apiOnline ? "已连接" : "不可达"}</strong>
              <span>/api/v1/health</span>
            </span>
          </div>
          <div className="reading-item">
            <span className="reading-index">Git</span>
            <span className="reading-copy">
              <strong>{gitea?.configured ? "Gitea 已配置" : "Gitea 未配置"}</strong>
              <span>{gitea?.owner ? `owner: ${gitea.owner}` : "设置 TIANXUAN_GITEA_URL / TOKEN"}</span>
            </span>
          </div>
          <div className="reading-item">
            <span className="reading-index">Actor</span>
            <span className="reading-copy">
              <strong>{actor || "未配置"}</strong>
              <span>TIANXUAN_ACTOR</span>
            </span>
          </div>
        </div>
      </section>

      <IdentityBindings />

      <div className="settings-layout">
        <nav aria-label="设置分类" className="settings-nav">
          <p className="sidebar-label">个人与工作区</p>
          {settingsNav.map((item, index) => (
            <a className={index === 0 ? "is-active" : ""} href={item.href} key={item.href}>
              <Icon name={item.icon} size={16} />
              {item.label}
            </a>
          ))}
          <div className="settings-nav-note">
            <span className="settings-nav-seal" aria-hidden="true">
              静
            </span>
            <p>少一点选项，多一点确认。</p>
            <small>天璇 · 产品原则</small>
          </div>
        </nav>

        <div className="settings-content">
          <section className="panel settings-card" id="profile" aria-labelledby="profile-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">IDENTITY</p>
                <h2 id="profile-title">个人资料</h2>
                <p>这些信息会出现在文档署名、工单与活动回执里。</p>
              </div>
              <Icon className="panel-head-icon" name="users" size={19} />
            </header>

            <div className="profile-edit-row">
              <span className="avatar avatar-xl avatar-jade">S</span>
              <div className="profile-edit-copy">
                <strong>头像使用令牌色块占位</strong>
                <span>不加载外部图片，也不上传到演示环境。</span>
              </div>
              <span className="role-pill">管理员</span>
            </div>

            <div className="settings-form-grid">
              <label className="settings-field">
                <span>显示名称</span>
                <input defaultValue="Sail" />
              </label>
              <label className="settings-field">
                <span>工作区标识</span>
                <input defaultValue="sail" spellCheck={false} />
              </label>
              <label className="settings-field settings-field-wide">
                <span>自我介绍</span>
                <input defaultValue="把复杂留在系统里，把清晰留给下一位协作者。" />
              </label>
            </div>
          </section>

          <section className="panel settings-card" id="appearance" aria-labelledby="appearance-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">APPEARANCE</p>
                <h2 id="appearance-title">外观</h2>
                <p>深色优先，宣纸白只用于需要被看见的文字。</p>
              </div>
              <span className="settings-tag">深色优先</span>
            </header>

            <div className="theme-options">
              <label className="theme-option is-selected">
                <input defaultChecked name="theme" type="radio" value="ink" />
                <span className="theme-preview theme-preview-dark">
                  <span className="theme-preview-side" />
                  <span className="theme-preview-main">
                    <span />
                    <span />
                    <span />
                  </span>
                </span>
                <span className="theme-option-copy">
                  <strong>墨夜</strong>
                  <small>当前 · 默认主题</small>
                </span>
                <span className="theme-check">
                  <Icon name="check" size={12} />
                </span>
              </label>

              <label className="theme-option">
                <input name="theme" type="radio" value="warm" />
                <span className="theme-preview theme-preview-warm">
                  <span className="theme-preview-side" />
                  <span className="theme-preview-main">
                    <span />
                    <span />
                    <span />
                  </span>
                </span>
                <span className="theme-option-copy">
                  <strong>暖墨</strong>
                  <small>低对比 · 仅设计预览</small>
                </span>
              </label>

              <label className="theme-option is-disabled">
                <input disabled name="theme" type="radio" value="paper" />
                <span className="theme-preview theme-preview-paper">
                  <span className="theme-preview-side" />
                  <span className="theme-preview-main">
                    <span />
                    <span />
                    <span />
                  </span>
                </span>
                <span className="theme-option-copy">
                  <strong>宣纸</strong>
                  <small>浅色主题 · 待开放</small>
                </span>
                <span className="theme-lock">
                  <Icon name="lock" size={12} />
                </span>
              </label>
            </div>

            <div className="accent-row">
              <span className="settings-label">纹样与点睛</span>
              <span className="accent-swatch accent-ink" title="墨 Ink #0B0E11" />
              <span className="accent-swatch accent-paper" title="纸 Paper #F5F2EA" />
              <span className="accent-swatch accent-cinnabar" title="朱砂 Cinnabar #C8402F" />
              <span className="accent-swatch accent-jade" title="青玉 Jade #3E8E7E" />
              <span className="accent-swatch accent-gold" title="鎏金 Gold #C9A227" />
              <span className="accent-caption">扁平中国风 · 毛玻璃</span>
            </div>
          </section>

          <section className="panel settings-card" id="workspace" aria-labelledby="workspace-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">WORKSPACE</p>
                <h2 id="workspace-title">工作区</h2>
                <p>单组织首版。空间与成员共享这一处的语言和时区。</p>
              </div>
              <Icon className="panel-head-icon" name="home" size={19} />
            </header>

            <div className="settings-form-grid">
              <label className="settings-field">
                <span>工作区名称</span>
                <input defaultValue="共工工坊" />
              </label>
              <label className="settings-field">
                <span>标识</span>
                <input defaultValue="gonggong" spellCheck={false} />
              </label>
              <label className="settings-field">
                <span>语言</span>
                <select defaultValue="zh-CN">
                  <option value="zh-CN">简体中文</option>
                  <option value="en">English</option>
                </select>
              </label>
              <label className="settings-field">
                <span>时区</span>
                <select defaultValue="Asia/Shanghai">
                  <option value="Asia/Shanghai">Asia / Shanghai</option>
                  <option value="UTC">UTC</option>
                </select>
              </label>
            </div>
          </section>

          <section className="panel settings-card settings-ai-card" id="ai" aria-labelledby="ai-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">AI &amp; MODELS</p>
                <h2 id="ai-title">AI 与模型</h2>
                <p>页面只展示托管状态与用量。凭据由服务端保险库持有，永不回显。</p>
              </div>
              <span className="settings-tag settings-tag-muted">未连接</span>
            </header>

            <div className="ai-provider">
              <span className="ai-provider-icon">
                <Icon name="sparkles" size={18} />
              </span>
              <span className="ai-provider-copy">
                <strong>共工模型网关</strong>
                <small>组织托管 · 自动路由 · 可审计</small>
              </span>
              <span className="ai-provider-state">
                <span className="status-dot" aria-hidden="true" />
                原型未连接
              </span>
            </div>

            <div className="settings-meta-grid">
              <div className="settings-meta">
                <span>默认模型</span>
                <strong>天璇路由器 · 自动选择</strong>
                <small>由任务类型与服务范围决定</small>
              </div>
              <div className="settings-meta">
                <span>凭据</span>
                <strong>服务端保险库托管</strong>
                <small>页面不读取、不显示、不保存密钥</small>
              </div>
              <div className="settings-meta settings-meta-usage">
                <span>本月用量</span>
                <strong>34%</strong>
                <span className="meter" aria-hidden="true">
                  <span style={{ width: "34%" }} />
                </span>
                <small>演示数据，不代表真实计量</small>
              </div>
            </div>

            <div className="toggle-list">
              <label className="toggle-row">
                <span>
                  <strong>允许 AI 在文档中起草</strong>
                  <small>生成内容始终以草稿形式出现，并标注来源。</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>写入司南工单前需要人工确认</strong>
                  <small>这是默认边界，优先于效率。</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>记录所有模型调用审计</strong>
                  <small>记录来源范围、路由与结果，不记录凭据。</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
            </div>
          </section>

          <section className="panel settings-card" id="notifications" aria-labelledby="notifications-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">NOTIFICATIONS</p>
                <h2 id="notifications-title">通知</h2>
                <p>只保留需要人做决定的时刻，不把进度变成噪音。</p>
              </div>
              <Icon className="panel-head-icon" name="bell" size={19} />
            </header>
            <div className="toggle-list">
              <label className="toggle-row">
                <span>
                  <strong>工单等待我的判断</strong>
                  <small>评审、阻塞与验收回读。</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>文档被 AI 更新</strong>
                  <small>附带更新的块与来源引用。</small>
                </span>
                <span className="switch">
                  <input type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>每日工作区摘要</strong>
                  <small>每天 09:00 汇总，无内容时不发送。</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
            </div>
          </section>

          <section className="panel settings-card" id="members" aria-labelledby="members-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">MEMBERS &amp; ACCESS</p>
                <h2 id="members-title">成员与权限</h2>
                <p>人类与 Agent 使用同一份成员名单，操作都留下可回读的身份。</p>
              </div>
              <span className="settings-tag">10 人上限</span>
            </header>

            <div className="member-table">
              <div className="member-table-head" aria-hidden="true">
                <span>成员</span>
                <span>角色</span>
                <span>状态</span>
              </div>
              {members.map((member) => (
                <div className="member-row" key={member.handle}>
                  <span className="member-identity">
                    <span className={`avatar avatar-sm avatar-${member.tone}`} aria-hidden="true">
                      {member.name.slice(0, 1)}
                    </span>
                    <span>
                      <strong>{member.name}</strong>
                      <small>@{member.handle}</small>
                    </span>
                  </span>
                  <span className="member-role">{member.role}</span>
                  <span className="member-status">
                    <span className="live-dot" aria-hidden="true" />
                    {member.status}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel settings-card settings-security" id="security" aria-labelledby="security-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">SECURITY &amp; DATA</p>
                <h2 id="security-title">安全与数据</h2>
                <p>关键操作需要再次确认；本原型不执行任何导出或删除。</p>
              </div>
              <Icon className="panel-head-icon" name="lock" size={19} />
            </header>

            <div className="security-rows">
              <div className="security-row">
                <span>
                  <strong>当前会话</strong>
                  <small>此设备 · 浏览器原型 · 无凭据</small>
                </span>
                <span className="security-state">仅预览</span>
              </div>
              <div className="security-row">
                <span>
                  <strong>工作区数据导出</strong>
                  <small>审计完成后由管理员发起，只从权威来源读取。</small>
                </span>
                <button className="btn btn-ghost btn-sm" disabled type="button">
                  导出
                </button>
              </div>
              <div className="security-row security-row-danger">
                <span>
                  <strong>归档工作区</strong>
                  <small>会保留只读回读入口；本演示环境不可执行。</small>
                </span>
                <button className="btn btn-danger btn-sm" disabled type="button">
                  归档
                </button>
              </div>
            </div>
          </section>

          <p className="settings-footnote">
            <Icon name="lock" size={13} />
            本页不包含真实 API Key、访问令牌或外部服务地址。所有演示配置仅保留在浏览器输入中。
          </p>
        </div>
      </div>
    </div>
  );
}
