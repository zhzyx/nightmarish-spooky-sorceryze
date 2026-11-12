/**************************************************************************/
/*  gonggong_panel.cpp                                                    */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "gonggong_panel.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/docks/gonggong_host_paths.h"
#include "editor/docks/gonggong_runtime_config.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/button.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/label.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/text_edit.h"
#include "scene/main/timer.h"
#include "servers/display/display_server.h"

GongGongPanel::GongGongPanel(bool p_check_environment) {
	set_name("GongGongPage");
	const String workspace_default = GongGongHostPaths::workspace();
	EDITOR_DEF("gonggong/workspace", workspace_default);
	const Dictionary runtime = GongGongRuntimeConfig::read_effective();
	const Dictionary runtime_paths = runtime.get("paths", Dictionary());
	EDITOR_DEF("gonggong/gh", "");
	EDITOR_DEF("gonggong/tenant", "gonggong-workspace");
	EDITOR_DEF("gonggong/issue_number", "");
	EDITOR_DEF("gonggong/request_id", "");
	Label *notice = memnew(Label);
	notice->set_text(U"GongGong · 框架与谛听数据\n接入检查不代表 Agent 已获准启用。配置保存于本机，执行程序路径由统一运行配置管理。");
	notice->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	add_child(notice);
	environment_settings_control = memnew(VBoxContainer);
	environment_settings_control->set_name("GongGongEnvironmentSettings");
	environment_settings_control->set_meta("ai_control_page_only", true);
	environment_settings_control->hide();
	add_child(environment_settings_control);
	Label *environment_title = memnew(Label);
	environment_title->set_text(U"共工 · 宿主环境与运行库");
	environment_settings_control->add_child(environment_title);
	auto add_environment_label = [this](const String &p_text) {
		Label *label = memnew(Label);
		label->set_text(p_text);
		label->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
		environment_settings_control->add_child(label);
	};
	add_environment_label(U"共工工作区根目录");
	workspace = memnew(LineEdit);
	workspace->set_name("GongGongWorkspace");
	workspace->set_placeholder(U"GongGong 工作区根目录");
	workspace->set_text(EDITOR_GET("gonggong/workspace"));
	environment_settings_control->add_child(workspace);
	add_environment_label(U"共工框架 Python（桥接与数据校验，与 SCons / 模型推理 Python 独立）");
	python = memnew(LineEdit);
	python->set_name("GongGongPython");
	python->set_placeholder(U"Python 可执行文件路径");
	python->set_text(runtime_paths.get("workflow_python", ""));
	environment_settings_control->add_child(python);
	add_environment_label(U"共工数据租户");
	python->connect("text_changed", callable_mp(this, &GongGongPanel::runtime_python_changed));
	tenant = memnew(LineEdit);
	tenant->set_name("GongGongTenant");
	tenant->set_placeholder(U"数据租户");
	tenant->set_text(EDITOR_GET("gonggong/tenant"));
	environment_settings_control->add_child(tenant);
	Button *save_environment = memnew(Button);
	save_environment->set_name("SaveGongGongEnvironment");
	save_environment->set_text(U"保存共工环境设置");
	save_environment->connect("pressed", callable_mp(this, &GongGongPanel::save_environment_settings));
	environment_settings_control->add_child(save_environment);
	Button *environment_button = memnew(Button);
	environment_button->set_name("GongGongEnvironmentSettingsButton");
	environment_button->set_text(U"环境设置");
	environment_button->connect("pressed", callable_mp(this, &GongGongPanel::request_environment_settings));
	add_child(environment_button);
	issue_number = memnew(LineEdit);
	issue_number->set_placeholder(U"开发工单 Issue 编号（先创建或复用真实工单）");
	issue_number->set_text(EDITOR_GET("gonggong/issue_number"));
	add_child(issue_number);
	request_id = memnew(LineEdit);
	request_id->set_placeholder(U"工单中的稳定需求 ID");
	request_id->set_text(EDITOR_GET("gonggong/request_id"));
	add_child(request_id);
	issue_number->connect("text_changed", callable_mp(this, &GongGongPanel::save_issue_binding));
	request_id->connect("text_changed", callable_mp(this, &GongGongPanel::save_issue_binding));
	const char *actions[] = { "status", "doctor", "check", "validate", "analyze", "environment-rollback" };
	const String labels[] = { U"读取框架状态", U"诊断生产聊天阻断原因", U"核对上游及候选完整性", U"校验谛听数据", U"分析当前租户记录", U"回退点火器部署" };
	for (int i = 0; i < 6; i++) {
		Button *button = memnew(Button);
		button->set_text(labels[i]);
		button->connect("pressed", callable_mp(this, &GongGongPanel::run_action).bind(String(actions[i])));
		(i == 5 ? environment_settings_control : this)->add_child(button);
	}
	Button *setup_button = memnew(Button);
	setup_button->set_name("GongGongEnvironmentSetup");
	setup_button->set_text(U"AI 自动配置本地运行环境");
	setup_button->connect("pressed", callable_mp(this, &GongGongPanel::open_setup));
	environment_settings_control->add_child(setup_button);
	setup_rollback = memnew(Button);
	setup_rollback->set_text(U"回退本次运行库部署");
	setup_rollback->set_disabled(true);
	setup_rollback->connect("pressed", callable_mp(this, &GongGongPanel::rollback_setup));
	environment_settings_control->add_child(setup_rollback);
	setup_dialog = memnew(ConfirmationDialog);
	setup_dialog->set_name("GongGongRuntimeSetup");
	// Keep configuration available alongside independent editor approvals.
	setup_dialog->set_exclusive(false);
	setup_dialog->set_title(U"运行环境配置");
	setup_dialog->set_force_native(true);
	setup_dialog->set_min_size(Size2i(760, 480));
	setup_dialog->set_ok_button_text(U"重新配置运行环境");
	setup_dialog->get_cancel_button()->hide();
	VBoxContainer *setup_fields = memnew(VBoxContainer);
	setup_dialog->add_child(setup_fields);
	Label *setup_notice = memnew(Label);
	setup_notice->set_text(U"AI 自动配置 Python、Node.js、Git 与 GitHub CLI；缺失的 GitHub CLI 会从官方校验包安装到当前工作区。\n配置完成后检查 GitHub 登录和仓库访问，需要账号授权时打开官方网页登录；通过后继续原需求。");
	setup_notice->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	setup_fields->add_child(setup_notice);
	setup_missing = memnew(Label);
	setup_missing->set_name("GongGongMissingComponents");
	setup_fields->add_child(setup_missing);
	setup_progress = memnew(TextEdit);
	setup_progress->set_name("GongGongSetupProgress");
	setup_progress->set_editable(false);
	setup_progress->set_line_wrapping_mode(TextEdit::LINE_WRAPPING_BOUNDARY);
	setup_progress->set_custom_minimum_size(Size2(720, 280));
	setup_progress->set_v_size_flags(SIZE_EXPAND_FILL);
	setup_fields->add_child(setup_progress);
	setup_github_login = memnew(Button);
	setup_github_login->set_name("GongGongGitHubLogin");
	setup_github_login->set_text(U"登录 GitHub 并继续原需求");
	setup_github_login->connect("pressed", callable_mp(this, &GongGongPanel::login_github));
	setup_github_login->hide();
	setup_fields->add_child(setup_github_login);
	setup_dialog->connect("confirmed", callable_mp(this, &GongGongPanel::start_setup));
	add_child(setup_dialog);
	output = memnew(TextEdit);
	output->set_name("GongGongOutput");
	output->set_editable(false);
	output->set_v_size_flags(SIZE_EXPAND_FILL);
	add_child(output);
	timer = memnew(Timer);
	timer->set_wait_time(0.25);
	timer->connect("timeout", callable_mp(this, &GongGongPanel::poll));
	add_child(timer);
	if (p_check_environment) {
		callable_mp(this, &GongGongPanel::ensure_environment).call_deferred();
	}
}

static String gonggong_runtime_path(const String &p_root, const String &p_environment, const String &p_relative, const String &p_command) {
	const String configured = OS::get_singleton()->get_environment(p_environment);
	if (!configured.is_empty() && FileAccess::exists(configured)) {
		return configured;
	}
	const String bundled = p_root.path_join(p_relative);
	if (FileAccess::exists(bundled)) {
		return bundled;
	}
	for (const String &directory : OS::get_singleton()->get_environment("PATH").split(OS::get_singleton()->get_name() == "Windows" ? ";" : ":")) {
		const String candidate = directory.path_join(p_command);
		if (FileAccess::exists(candidate)) {
			return candidate;
		}
	}
	return String();
}

bool GongGongPanel::ensure_environment() {
	return ensure_environment_with_snapshot(GongGongRuntimeConfig::read_effective());
}

bool GongGongPanel::ensure_environment_with_snapshot(const Dictionary &runtime) {
	GongGongRuntimeConfig::prepare_child_environment(runtime);
	if (OS::get_singleton()->get_name() != "Windows") {
		return true;
	}
	const String root = EDITOR_GET("gonggong/workspace");
	const String current_python = GongGongRuntimeConfig::path(runtime, "workflow_python");
	const String node = GongGongRuntimeConfig::path(runtime, "node");
	const String git = gonggong_runtime_path(root, "GONGGONG_GIT", "project/runtime/git/cmd/git.exe", "git.exe");
	String gh = EDITOR_GET("gonggong/gh");
	if (!FileAccess::exists(gh)) {
		gh = gonggong_runtime_path(root, "GONGGONG_GH", "project/runtime/gh/bin/gh.exe", "gh.exe");
	}
	if (gh.is_empty()) {
		for (const String &candidate : { OS::get_singleton()->get_environment("ProgramFiles").path_join("GitHub CLI/gh.exe"), OS::get_singleton()->get_environment("LOCALAPPDATA").path_join("Microsoft/WinGet/Links/gh.exe") }) {
			if (FileAccess::exists(candidate)) {
				gh = candidate;
				break;
			}
		}
	}
	const bool ready = !root.is_empty() && FileAccess::exists(root.path_join("tools/gonggong_bridge.py")) && FileAccess::exists(current_python) && !node.is_empty() && !git.is_empty() && !gh.is_empty();
	if (ready) {
		OS::get_singleton()->set_environment("GONGGONG_GIT", git);
		OS::get_singleton()->set_environment("GONGGONG_GH", gh);
		return true;
	}
	PackedStringArray missing;
	if (!FileAccess::exists(current_python)) {
		missing.push_back("Python");
	}
	if (node.is_empty()) {
		missing.push_back("Node.js");
	}
	if (git.is_empty()) {
		missing.push_back("Git");
	}
	if (gh.is_empty()) {
		missing.push_back("GitHub CLI (gh)");
	}
	if (root.is_empty() || !FileAccess::exists(root.path_join("tools/gonggong_bridge.py"))) {
		missing.push_back(U"共工工作区");
	}
	setup_missing->set_text(String(U"缺失配置：") + String(", ").join(missing));
	workspace->set_text(root);
	refresh_runtime_controls(runtime);
	set_setup_status(U"准备启动：检测到本地运行环境缺失。\n原需求已保留；配置完成后会自动继续。");
	if (is_inside_tree() && worker < 0) {
		setup_dialog->popup_centered(Size2i(760, 480));
		if (!setup_attempted) {
			setup_attempted = true;
			callable_mp(this, &GongGongPanel::start_setup).call_deferred();
		}
	}
	return false;
}

void GongGongPanel::request_environment_settings() {
	if (settings_requested.is_valid()) {
		settings_requested.call(String("environment"));
	}
}

void GongGongPanel::save_environment_settings() {
	if (worker >= 0 || task_locked) {
		return;
	}
	apply_environment_settings(workspace->get_text().strip_edges(), tenant->get_text().strip_edges());
	EditorSettings::save();
}

bool GongGongPanel::set_environment_python(const String &p_python) {
	return set_runtime_field("workflow_python", p_python).is_empty();
}

String GongGongPanel::set_runtime_field(const String &p_field, const String &p_value) {
	if (worker >= 0 || task_locked) {
		return "runtime_environment_locked";
	}
	const Dictionary previous = GongGongRuntimeConfig::read_effective();
	const Dictionary sources = previous.get("sources", Dictionary());
	const Dictionary paths = previous.get("paths", Dictionary());
	if (p_field == "workflow_python" && sources.get(p_field, "") != Variant("environment") && String(paths.get(p_field, "")) != p_value.strip_edges() && environment_changing.is_valid()) {
		// Cleanup still reads the old effective Python and workspace here.
		environment_changing.call();
	}
	String error;
	if (GongGongRuntimeConfig::update_field(p_field, p_value, error) != OK) {
		return error;
	}
	if (p_field == "workflow_python") {
		python->set_text(p_value.strip_edges());
	}
	if (runtime_changed.is_valid()) {
		runtime_changed.call();
	}
	return String();
}

void GongGongPanel::refresh_runtime_controls(const Dictionary &p_runtime) {
	const Dictionary paths = p_runtime.get("paths", Dictionary());
	const bool blocked = python->is_blocking_signals();
	python->set_block_signals(true);
	python->set_text(paths.get("workflow_python", ""));
	python->set_block_signals(blocked);
}

bool GongGongPanel::apply_environment_settings(const String &p_workspace, const String &p_tenant) {
	if (task_locked) {
		return false;
	}
	EditorSettings *settings = EditorSettings::get_singleton();
	const bool changed = String(settings->get_setting("gonggong/workspace")) != p_workspace || String(settings->get_setting("gonggong/tenant")) != p_tenant;
	if (changed && environment_changing.is_valid()) {
		// Actor/watch cleanup must still see the old workspace and Python here.
		environment_changing.call();
	}
	settings->set("gonggong/workspace", p_workspace);
	settings->set("gonggong/tenant", p_tenant);
	return true;
}

void GongGongPanel::set_task_locked(bool p_locked) {
	task_locked = p_locked;
	update_environment_controls();
}

void GongGongPanel::update_environment_controls() {
	const bool idle = worker < 0 && !task_locked;
	workspace->set_editable(idle);
	python->set_editable(idle);
	tenant->set_editable(idle);
	for (const Variant &value : environment_settings_control->find_children("*", "Button", true, false)) {
		Object::cast_to<Button>(static_cast<Object *>(value))->set_disabled(!idle);
	}
	setup_rollback->set_disabled(!idle || setup_receipt.is_empty());
}

bool GongGongPanel::start_ai_setup(const Array &p_missing) {
	if (OS::get_singleton()->get_name() != "Windows" || p_missing.is_empty() || task_locked) {
		return false;
	}
	PackedStringArray names;
	for (const Variant &component : p_missing) {
		const String name = String(component).to_lower();
		names.push_back(name == "python" ? "Python" : name == "node" ? "Node.js"
						: name == "gh"								 ? "GitHub CLI (gh)"
						: name == "github_auth"						 ? String(U"GitHub 登录")
																	 : name.capitalize());
	}
	setup_missing->set_text(String(U"缺失配置：") + String(", ").join(names));
	set_setup_status(U"准备启动：引擎内对话已暂停并保留。\n配置完成后会自动恢复这条请求。");
	setup_dialog->popup_centered(Size2i(760, 480));
	if (worker < 0) {
		setup_attempted = true;
		start_setup();
	}
	return true;
}

void GongGongPanel::open_setup() {
	if (worker < 0 && !task_locked) {
		setup_missing->set_text(U"复检：Python、Node.js、Git、GitHub CLI 与 GitHub 访问");
		set_setup_status(U"准备启动：将重新检查当前工作区的完整运行环境。");
		setup_dialog->popup_centered(Size2i(760, 480));
		start_setup();
	}
}

void GongGongPanel::set_setup_status(const String &p_status) {
	const String context = String(U"上下文\n工作区：") + workspace->get_text().strip_edges() + "\n" + setup_missing->get_text() +
			U"\n执行通道：宿主确定性配置（无需模型账号，保留治理校验）\n原需求：已保留，配置成功后自动继续\n\n实时进度\n" + p_status;
	if (setup_progress) {
		setup_progress->set_text(context);
	}
	if (output) {
		output->set_text(p_status);
	}
}

void GongGongPanel::refresh_setup_progress() {
	if (setup_progress_path.is_empty() || !FileAccess::exists(setup_progress_path)) {
		return;
	}
	const Variant parsed = JSON::parse_string(FileAccess::get_file_as_string(setup_progress_path));
	if (parsed.get_type() != Variant::DICTIONARY) {
		return;
	}
	const Dictionary progress = parsed;
	const String stage = progress.get("stage", String());
	const String message = progress.get("message", String());
	String stage_label = stage;
	if (stage == "context") {
		stage_label = U"1/5 检查上下文";
	} else if (stage == "discovery") {
		stage_label = U"2/5 发现运行库";
	} else if (stage == "selection") {
		stage_label = U"3/5 Agent 选择";
	} else if (stage == "validation") {
		stage_label = U"4/5 安全校验";
	} else if (stage == "self_check") {
		stage_label = U"5/5 本地自检";
	} else if (stage == "github_install") {
		stage_label = U"安装 GitHub CLI";
	} else if (stage == "github_action_required") {
		stage_label = U"等待 GitHub 授权或权限修复";
	} else if (stage == "completed") {
		stage_label = U"完成";
	} else if (stage == "failed") {
		stage_label = U"失败";
	}
	const String status = (stage_label.is_empty() ? String() : "[" + stage_label + "] ") + message;
	if (!status.is_empty() && status != setup_last_progress) {
		setup_last_progress = status;
		set_setup_status(status);
	}
}

void GongGongPanel::start_setup() {
	run_setup(false);
}

void GongGongPanel::rollback_setup() {
	run_setup(true);
}

void GongGongPanel::login_github() {
	if (worker >= 0 || task_locked || !FileAccess::exists(setup_github_path)) {
		return;
	}
	const String root = workspace->get_text().strip_edges();
	const String host_root = GongGongHostPaths::engine_source();
	const String script = host_root.path_join("tools/check_gonggong_github.ps1");
	if (!host_root.is_absolute_path() || !FileAccess::exists(script)) {
		set_setup_status(U"缺少 GitHub 登录检查脚本，原需求继续保留。");
		return;
	}
	const String shell = OS::get_singleton()->get_environment("SystemRoot").path_join("System32/WindowsPowerShell/v1.0/powershell.exe");
	result_path = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-github-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
	List<String> args;
	for (const String &arg : { String("-NoProfile"), String("-ExecutionPolicy"), String("RemoteSigned"), String("-File"), script, String("-Workspace"), root, String("-Gh"), setup_github_path, String("-Out"), result_path, String("-Login") }) {
		args.push_back(arg);
	}
	ProcessID pid = 0;
	const bool interactive = DisplayServer::get_singleton()->get_name() != "headless";
	if (OS::get_singleton()->create_process(shell, args, &pid, interactive) != OK) {
		set_setup_status(U"无法打开 GitHub 登录窗口，请点击登录按钮重试。");
		return;
	}
	worker = pid;
	setup_running = true;
	setup_github_authenticating = true;
	setup_progress_path.clear();
	setup_github_login->set_disabled(true);
	setup_dialog->get_ok_button()->set_disabled(true);
	set_setup_status(String(U"[等待 GitHub 登录] 已打开官方登录终端。按终端提示在浏览器完成账号授权；窗口关闭后将自动复检仓库访问并继续原需求。") + setup_agent_details);
	timer->start();
}

void GongGongPanel::finish_setup_github(const Dictionary &p_github) {
	setup_github_login->set_disabled(false);
	if (!bool(p_github.get("ok", false))) {
		setup_github_login->show();
		const String error = p_github.get("error", String("github_check_failed"));
		set_setup_status(String(U"[等待 GitHub 访问] 本地运行库已配置，原需求继续保留。\n") + (error == "gh_unauthenticated" ? String(U"需要完成 GitHub 账号登录，授权后会自动继续。") : String(U"请确认当前账号可以访问工作区仓库，且仓库已启用 Issues。")) + "\n" + error + setup_agent_details);
		return;
	}
	setup_github_login->hide();
	set_setup_status(String(U"[完成] 本地运行库、GitHub 登录和仓库读取检查均已通过。正在恢复原需求。\n仓库：") + String(p_github.get("repository", String())) + setup_agent_details);
	if (setup_completed.is_valid()) {
		setup_completed.call_deferred();
	}
}

void GongGongPanel::run_setup(bool p_rollback) {
	if (worker >= 0 || task_locked) {
		return;
	}
	const Dictionary current_runtime = GongGongRuntimeConfig::read_effective();
	GongGongRuntimeConfig::prepare_child_environment(current_runtime);
	const String root = workspace->get_text().strip_edges();
	const String host_root = GongGongHostPaths::engine_source();
	const String script = host_root.path_join(p_rollback ? "tools/configure_gonggong_runtime.ps1" : "tools/run_gonggong_config_agent.ps1");
	if (!host_root.is_absolute_path() || !FileAccess::exists(script)) {
		set_setup_status(p_rollback ? U"失败：当前工作区缺少运行库回退脚本。" : U"失败：当前工作区缺少运行环境配置启动脚本。");
		return;
	}
	const String shell = OS::get_singleton()->get_environment("SystemRoot").path_join("System32/WindowsPowerShell/v1.0/powershell.exe");
	result_path = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-setup-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
	setup_progress_path = result_path.get_basename() + ".progress.json";
	setup_last_progress.clear();
	setup_github_authenticating = false;
	setup_github_login->hide();
	List<String> args;
	for (const String &arg : { String("-NoProfile"), String("-NonInteractive"), String("-ExecutionPolicy"), String("RemoteSigned"), String("-File"), script, String("-Workspace"), root, String("-Out"), result_path }) {
		args.push_back(arg);
	}
	if (p_rollback) {
		args.push_back("-Rollback");
		args.push_back(setup_receipt);
	} else {
		args.push_back("-Progress");
		args.push_back(setup_progress_path);
		setup_previous["workspace"] = EDITOR_GET("gonggong/workspace");
		const Dictionary configured = current_runtime.get("configured", Dictionary());
		setup_previous["python"] = configured.get("workflow_python", "");
		setup_previous["node"] = configured.get("node", "");
		setup_previous["runtime_components"] = PackedStringArray({ "python", "node", "git", "gh" });
		setup_previous["gh"] = EDITOR_GET("gonggong/gh");
		for (const String &name : { String("GONGGONG_PYTHON"), String("GONGGONG_NODE"), String("GONGGONG_GIT"), String("GONGGONG_GH"), String("PATH") }) {
			setup_previous[name] = OS::get_singleton()->get_environment(name);
		}
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(shell, args, &pid, false) != OK) {
		set_setup_status(U"失败：无法启动本机 PowerShell 配置点火器。原需求与环境未变更。");
		return;
	}
	worker = pid;
	setup_running = true;
	setup_rolling_back = p_rollback;
	update_environment_controls();
	setup_dialog->get_ok_button()->set_disabled(true);
	set_setup_status(p_rollback ? U"正在回退本次运行库部署…" : U"[启动] 独立 Agent 进程已创建，正在读取本机上下文…");
	timer->start();
}

void GongGongPanel::reload_issue_binding() {
	issue_number->set_text(EDITOR_GET("gonggong/issue_number"));
	request_id->set_text(EDITOR_GET("gonggong/request_id"));
}

void GongGongPanel::save_issue_binding(const String &p_text) {
	EditorSettings::get_singleton()->set("gonggong/issue_number", issue_number->get_text().strip_edges());
	EditorSettings::get_singleton()->set("gonggong/request_id", request_id->get_text().strip_edges());
	EditorSettings::save();
}

void GongGongPanel::run_action(const String &p_action) {
	if (worker >= 0 || task_locked) {
		return;
	}
	const Dictionary runtime = GongGongRuntimeConfig::read_effective();
	GongGongRuntimeConfig::prepare_child_environment(runtime);
	const String workflow_python = GongGongRuntimeConfig::path(runtime, "workflow_python");
	const String script = workspace->get_text().path_join("tools/gonggong_bridge.py");
	if (workspace->get_text().is_empty() || workflow_python.is_empty() || !FileAccess::exists(script)) {
		output->set_text(U"请填写工作区、Python 路径，并确认引擎 tools/gonggong_bridge.py 已安装。");
		return;
	}
	apply_environment_settings(workspace->get_text(), tenant->get_text());
	EditorSettings::save();
	result_path = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
	List<String> args;
	args.push_back(script);
	args.push_back(p_action);
	args.push_back("--workspace");
	args.push_back(workspace->get_text());
	args.push_back("--tenant");
	args.push_back(tenant->get_text());
	args.push_back("--out");
	args.push_back(result_path);
	ProcessID pid = 0;
	Error error = OS::get_singleton()->create_process(workflow_python, args, &pid);
	if (error != OK) {
		output->set_text(U"启动失败，请检查 Python 路径。");
		return;
	}
	worker = pid;
	update_environment_controls();
	output->set_text(U"正在执行检查…");
	timer->start();
}

void GongGongPanel::poll() {
	// A deployment may finish after a new chat turn has acquired the task lock.
	// Keep its result and configuration pending until that turn releases it.
	if (OS::get_singleton()->is_process_running(worker) || task_locked) {
		if (setup_running) {
			refresh_setup_progress();
		}
		return;
	}
	timer->stop();
	worker = -1;
	update_environment_controls();
	if (setup_running) {
		refresh_setup_progress();
		setup_running = false;
		setup_dialog->get_ok_button()->set_disabled(false);
		Dictionary result;
		if (FileAccess::exists(result_path)) {
			const Variant parsed = JSON::parse_string(FileAccess::get_file_as_string(result_path));
			if (parsed.get_type() == Variant::DICTIONARY) {
				result = parsed;
			}
		}
		if (setup_github_authenticating) {
			setup_github_authenticating = false;
			finish_setup_github(result);
			return;
		}
		if (!bool(result.get("ok", false))) {
			const String last_stage = setup_last_progress.is_empty() ? String() : String(U"\n最后阶段：") + setup_last_progress;
			set_setup_status(String(U"[失败] 运行环境配置尚未完成，原需求仍保留。\n") + String(result.get("error", U"配置程序未返回结果")) + last_stage + U"\n结果：" + result_path + U"\n进度记录：" + setup_progress_path);
			return;
		}
		if (setup_rolling_back) {
			apply_environment_settings(setup_previous.get("workspace", String()), EDITOR_GET("gonggong/tenant"));
			String save_error;
			const PackedStringArray selected_components = setup_previous.get("runtime_components", PackedStringArray());
			if (selected_components.has("python")) {
				save_error = set_runtime_field("workflow_python", setup_previous.get("python", String()));
			}
			if (save_error.is_empty() && selected_components.has("node")) {
				save_error = set_runtime_field("node", setup_previous.get("node", String()));
			}
			if (!save_error.is_empty()) {
				output->set_text(String(U"部署已回退，但运行路径未保存：") + save_error);
				return;
			}
			EditorSettings::get_singleton()->set("gonggong/gh", setup_previous.get("gh", String()));
			for (const String &name : { String("GONGGONG_PYTHON"), String("GONGGONG_NODE"), String("GONGGONG_GIT"), String("GONGGONG_GH"), String("PATH") }) {
				OS::get_singleton()->set_environment(name, setup_previous.get(name, String()));
			}
			const Dictionary runtime = GongGongRuntimeConfig::read_effective();
			GongGongRuntimeConfig::prepare_child_environment(runtime);
			refresh_runtime_controls(runtime);
			setup_rollback->set_disabled(true);
			EditorSettings::save();
			set_setup_status(String(U"[完成] 已回退本次部署并恢复编辑器会话环境；日志和文件恢复副本保留。\n结果：") + result_path);
			return;
		}
		// Physical deployment can succeed even when canonical configuration cannot
		// be saved. Keep its rollback receipt before any later validation or write.
		setup_receipt = result.get("receipt", String());
		setup_rollback->set_disabled(setup_receipt.is_empty());
		const String deployed_python = result.get("python", String());
		const String deployed_node = result.get("node", String());
		const String deployed_git = result.get("git", String());
		const String deployed_gh = result.get("gh", String());
		if (!FileAccess::exists(deployed_python) || !FileAccess::exists(deployed_node) || !FileAccess::exists(deployed_git) || !FileAccess::exists(deployed_gh)) {
			set_setup_status(U"[失败] 点火器返回的运行库路径无效，原需求继续保留。");
			return;
		}
		apply_environment_settings(workspace->get_text().strip_edges(), EDITOR_GET("gonggong/tenant"));
		String save_error;
		const PackedStringArray selected_components = setup_previous.get("runtime_components", PackedStringArray());
		if (selected_components.has("python")) {
			save_error = set_runtime_field("workflow_python", deployed_python);
		}
		if (save_error.is_empty() && selected_components.has("node")) {
			save_error = set_runtime_field("node", deployed_node);
		}
		if (!save_error.is_empty()) {
			output->set_text(String(U"运行库已部署，但路径未保存：") + save_error);
			return;
		}
		const Dictionary runtime = GongGongRuntimeConfig::read_effective();
		GongGongRuntimeConfig::prepare_child_environment(runtime);
		String child_path = setup_previous.get("PATH", String());
		if (selected_components.has("node")) {
			child_path = deployed_node.get_base_dir() + ";" + child_path;
		}
		if (selected_components.has("git")) {
			OS::get_singleton()->set_environment("GONGGONG_GIT", deployed_git);
			child_path = deployed_git.get_base_dir() + ";" + child_path;
		}
		OS::get_singleton()->set_environment("PATH", child_path);
		refresh_runtime_controls(runtime);
		EditorSettings::get_singleton()->set("gonggong/gh", deployed_gh);
		OS::get_singleton()->set_environment("GONGGONG_GH", deployed_gh);
		setup_github_path = deployed_gh;
		EditorSettings::save();
		const Dictionary agent = result.get("agent", Dictionary());
		setup_agent_details = String(U"\nAgent 摘要：") + String(agent.get("summary", U"已选择完整运行环境")) + U"\nAgent 日志：" + String(agent.get("log", String())) + U"\n配置结果：" + result_path;
		const Dictionary github = result.get("github", Dictionary());
		finish_setup_github(github);
		if (String(github.get("error", String())) == "gh_unauthenticated" && DisplayServer::get_singleton()->get_name() != "headless") {
			callable_mp(this, &GongGongPanel::login_github).call_deferred();
		}
		return;
	}
	if (FileAccess::exists(result_path)) {
		output->set_text(FileAccess::get_file_as_string(result_path));
		DirAccess::remove_absolute(result_path);
	} else {
		output->set_text(U"检查进程未返回结果，请检查 Python 和工作区配置。");
	}
}

void GongGongPanel::runtime_python_changed(const String &p_value) {
	const String error = set_runtime_field("workflow_python", p_value);
	if (!error.is_empty() && output) {
		output->set_text(String(U"运行路径未保存：") + error);
	}
}
