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
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/button.h"
#include "scene/gui/check_box.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/file_dialog.h"
#include "scene/gui/label.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/text_edit.h"
#include "scene/main/timer.h"

GongGongPanel::GongGongPanel() {
	set_name("GongGongPage");
	const String workspace_default = GongGongHostPaths::workspace();
	EDITOR_DEF("gonggong/workspace", workspace_default);
	String python_default = OS::get_singleton()->get_environment("GONGGONG_PYTHON");
	if (python_default.is_empty() && FileAccess::exists(workspace_default.path_join("project/runtime/python/python.exe"))) {
		python_default = workspace_default.path_join("project/runtime/python/python.exe");
	}
	EDITOR_DEF("gonggong/python", python_default);
	const String saved_python = EDITOR_GET("gonggong/python");
	const bool explicit_runtime = !OS::get_singleton()->get_environment("GONGGONG_PYTHON").is_empty();
	if (!python_default.is_empty() && (explicit_runtime || saved_python.is_empty() || !FileAccess::exists(saved_python))) {
		EditorSettings::get_singleton()->set("gonggong/python", python_default);
	}
	EDITOR_DEF("gonggong/tenant", "gonggong-workspace");
	EDITOR_DEF("gonggong/issue_number", "");
	EDITOR_DEF("gonggong/request_id", "");
	Label *notice = memnew(Label);
	notice->set_text(U"GongGong · 框架与谛听数据\n接入检查不代表 Agent 已获准启用。配置保存于本机编辑器设置。");
	notice->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	add_child(notice);
	workspace = memnew(LineEdit);
	workspace->set_placeholder(U"GongGong 工作区根目录");
	workspace->set_text(EDITOR_GET("gonggong/workspace"));
	add_child(workspace);
	python = memnew(LineEdit);
	python->set_placeholder(U"Python 可执行文件路径");
	python->set_text(EDITOR_GET("gonggong/python"));
	add_child(python);
	tenant = memnew(LineEdit);
	tenant->set_placeholder(U"数据租户");
	tenant->set_text(EDITOR_GET("gonggong/tenant"));
	add_child(tenant);
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
		add_child(button);
	}
	Button *setup_button = memnew(Button);
	setup_button->set_name("GongGongEnvironmentSetup");
	setup_button->set_text(U"本地配置点火器（Python / Node / Git）");
	setup_button->connect("pressed", callable_mp(this, &GongGongPanel::open_setup));
	add_child(setup_button);
	setup_rollback = memnew(Button);
	setup_rollback->set_text(U"回退本次运行库部署");
	setup_rollback->set_disabled(true);
	setup_rollback->connect("pressed", callable_mp(this, &GongGongPanel::rollback_setup));
	add_child(setup_rollback);
	setup_dialog = memnew(ConfirmationDialog);
	setup_dialog->set_name("GongGongRuntimeSetup");
	// Keep configuration available alongside independent editor approvals.
	setup_dialog->set_exclusive(false);
	setup_dialog->set_title(U"共工本地配置点火器");
	setup_dialog->set_ok_button_text(U"部署并自检，完成后继续原需求");
	VBoxContainer *setup_fields = memnew(VBoxContainer);
	setup_dialog->add_child(setup_fields);
	Label *setup_notice = memnew(Label);
	setup_notice->set_text(U"选择需要部署的组件。优先复用本机已有运行库；缺失时可从已解压的共工完整包选择 project/runtime 目录。\n部署仅写当前工作区，不修改系统环境变量；失败保留日志并回退本次文件变更。");
	setup_notice->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	setup_fields->add_child(setup_notice);
	setup_missing = memnew(Label);
	setup_missing->set_name("GongGongMissingComponents");
	setup_fields->add_child(setup_missing);
	for (int i = 0; i < 3; i++) {
		setup_components[i] = memnew(CheckBox);
		setup_components[i]->set_text(i == 0 ? "Python" : i == 1 ? "Node.js"
																 : "Git");
		setup_components[i]->set_pressed(true);
		setup_fields->add_child(setup_components[i]);
	}
	setup_source = memnew(LineEdit);
	setup_source->set_name("GongGongRuntimeSource");
	setup_source->set_placeholder(U"可选：完整包中的 project/runtime 目录");
	setup_fields->add_child(setup_source);
	Button *source_button = memnew(Button);
	source_button->set_text(U"选择运行库来源目录…");
	source_button->connect("pressed", callable_mp(this, &GongGongPanel::open_setup_source));
	setup_fields->add_child(source_button);
	setup_source_dialog = memnew(FileDialog);
	setup_source_dialog->set_access(FileDialog::ACCESS_FILESYSTEM);
	setup_source_dialog->set_file_mode(FileDialog::FILE_MODE_OPEN_DIR);
	setup_source_dialog->connect("dir_selected", callable_mp(this, &GongGongPanel::choose_setup_source));
	setup_dialog->add_child(setup_source_dialog);
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
	callable_mp(this, &GongGongPanel::ensure_environment).call_deferred();
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
	if (OS::get_singleton()->get_name() != "Windows") {
		return true;
	}
	const String root = EDITOR_GET("gonggong/workspace");
	const String current_python = EDITOR_GET("gonggong/python");
	const String node = gonggong_runtime_path(root, "GONGGONG_NODE", "project/runtime/node/node.exe", "node.exe");
	const String git = gonggong_runtime_path(root, "GONGGONG_GIT", "project/runtime/git/cmd/git.exe", "git.exe");
	const bool ready = !root.is_empty() && FileAccess::exists(root.path_join("tools/gonggong_bridge.py")) && FileAccess::exists(current_python) && !node.is_empty() && !git.is_empty();
	if (ready) {
		OS::get_singleton()->set_environment("GONGGONG_NODE", node);
		OS::get_singleton()->set_environment("GONGGONG_GIT", git);
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
	if (root.is_empty() || !FileAccess::exists(root.path_join("tools/gonggong_bridge.py"))) {
		missing.push_back(U"共工工作区");
	}
	setup_missing->set_text(String(U"缺失配置：") + String(", ").join(missing));
	workspace->set_text(root);
	python->set_text(current_python);
	if (output) {
		output->set_text(U"检测到本地运行环境缺失，已打开配置点火器。原需求保留，完成部署与自检后继续；取消不会安装任何组件。");
	}
	if (is_inside_tree() && worker < 0) {
		setup_dialog->popup_centered(Size2i(640, 360));
	}
	return false;
}

void GongGongPanel::open_setup() {
	if (worker < 0) {
		setup_dialog->popup_centered(Size2i(640, 360));
	}
}

void GongGongPanel::open_setup_source() {
	setup_source_dialog->popup_centered_ratio();
}

void GongGongPanel::choose_setup_source(const String &p_directory) {
	setup_source->set_text(p_directory);
}

void GongGongPanel::start_setup() {
	run_setup(false);
}

void GongGongPanel::rollback_setup() {
	run_setup(true);
}

void GongGongPanel::run_setup(bool p_rollback) {
	if (worker >= 0) {
		return;
	}
	const String root = workspace->get_text().strip_edges();
	const String script = root.path_join("tools/configure_gonggong_runtime.ps1");
	if (!FileAccess::exists(script)) {
		output->set_text(U"当前工作区缺少配置点火器脚本，请选择包含 tools/configure_gonggong_runtime.ps1 的完整共工工作区。");
		return;
	}
	const String shell = OS::get_singleton()->get_environment("SystemRoot").path_join("System32/WindowsPowerShell/v1.0/powershell.exe");
	result_path = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-setup-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
	List<String> args;
	for (const String &arg : { String("-NoProfile"), String("-NonInteractive"), String("-ExecutionPolicy"), String("RemoteSigned"), String("-File"), script, String("-Workspace"), root, String("-Out"), result_path }) {
		args.push_back(arg);
	}
	if (p_rollback) {
		args.push_back("-Rollback");
		args.push_back(setup_receipt);
	} else {
		PackedStringArray components;
		for (int i = 0; i < 3; i++) {
			if (setup_components[i]->is_pressed()) {
				components.push_back(i == 0 ? "python" : i == 1 ? "node"
																: "git");
			}
		}
		if (components.is_empty()) {
			output->set_text(U"请至少选择一个需要部署的组件。");
			return;
		}
		args.push_back("-Components");
		args.push_back(String(",").join(components));
		if (!setup_source->get_text().strip_edges().is_empty()) {
			args.push_back("-SourceRuntime");
			args.push_back(setup_source->get_text().strip_edges());
		}
		setup_previous["workspace"] = EDITOR_GET("gonggong/workspace");
		setup_previous["python"] = EDITOR_GET("gonggong/python");
		for (const String &name : { String("GONGGONG_PYTHON"), String("GONGGONG_NODE"), String("GONGGONG_GIT"), String("PATH") }) {
			setup_previous[name] = OS::get_singleton()->get_environment(name);
		}
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(shell, args, &pid, false) != OK) {
		output->set_text(U"无法启动本机 PowerShell 配置点火器。原需求与环境未变更。");
		return;
	}
	worker = pid;
	setup_running = true;
	setup_rolling_back = p_rollback;
	output->set_text(p_rollback ? U"正在回退本次运行库部署…" : U"正在部署选定的本地运行库并执行共工自检…");
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
	if (worker >= 0) {
		return;
	}
	const String script = workspace->get_text().path_join("tools/gonggong_bridge.py");
	if (workspace->get_text().is_empty() || python->get_text().is_empty() || !FileAccess::exists(script)) {
		output->set_text(U"请填写工作区、Python 路径，并确认引擎 tools/gonggong_bridge.py 已安装。");
		return;
	}
	EditorSettings::get_singleton()->set("gonggong/workspace", workspace->get_text());
	EditorSettings::get_singleton()->set("gonggong/python", python->get_text());
	EditorSettings::get_singleton()->set("gonggong/tenant", tenant->get_text());
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
	Error error = OS::get_singleton()->create_process(python->get_text(), args, &pid);
	if (error != OK) {
		output->set_text(U"启动失败，请检查 Python 路径。");
		return;
	}
	worker = pid;
	output->set_text(U"正在执行检查…");
	timer->start();
}

void GongGongPanel::poll() {
	if (OS::get_singleton()->is_process_running(worker)) {
		return;
	}
	timer->stop();
	worker = -1;
	if (setup_running) {
		setup_running = false;
		Dictionary result;
		if (FileAccess::exists(result_path)) {
			const Variant parsed = JSON::parse_string(FileAccess::get_file_as_string(result_path));
			if (parsed.get_type() == Variant::DICTIONARY) {
				result = parsed;
			}
		}
		if (!bool(result.get("ok", false))) {
			output->set_text(String(U"本地环境部署尚未完成，原需求保留。可修复后重试。\n") + String(result.get("error", U"点火器未返回结果")) + "\n" + result_path);
			return;
		}
		if (setup_rolling_back) {
			EditorSettings::get_singleton()->set("gonggong/workspace", setup_previous.get("workspace", String()));
			EditorSettings::get_singleton()->set("gonggong/python", setup_previous.get("python", String()));
			for (const String &name : { String("GONGGONG_PYTHON"), String("GONGGONG_NODE"), String("GONGGONG_GIT"), String("PATH") }) {
				OS::get_singleton()->set_environment(name, setup_previous.get(name, String()));
			}
			python->set_text(EDITOR_GET("gonggong/python"));
			setup_rollback->set_disabled(true);
			EditorSettings::save();
			output->set_text(String(U"已回退本次部署并恢复编辑器会话环境；日志和文件恢复副本保留。\n") + result_path);
			return;
		}
		const String deployed_python = result.get("python", String());
		const String deployed_node = result.get("node", String());
		const String deployed_git = result.get("git", String());
		if (!FileAccess::exists(deployed_python) || !FileAccess::exists(deployed_node) || !FileAccess::exists(deployed_git)) {
			output->set_text(U"点火器返回的运行库路径无效，未恢复原需求。");
			return;
		}
		EditorSettings::get_singleton()->set("gonggong/workspace", workspace->get_text().strip_edges());
		EditorSettings::get_singleton()->set("gonggong/python", deployed_python);
		OS::get_singleton()->set_environment("GONGGONG_PYTHON", deployed_python);
		OS::get_singleton()->set_environment("GONGGONG_NODE", deployed_node);
		OS::get_singleton()->set_environment("GONGGONG_GIT", deployed_git);
		OS::get_singleton()->set_environment("PATH", deployed_node.get_base_dir() + ";" + deployed_git.get_base_dir() + ";" + String(setup_previous.get("PATH", String())));
		python->set_text(deployed_python);
		setup_receipt = result.get("receipt", String());
		setup_rollback->set_disabled(setup_receipt.is_empty());
		EditorSettings::save();
		output->set_text(String(U"本地运行库与共工自检通过。正在恢复原需求；模型连接与 GitHub 登录仍由实际请求验证。\n") + result_path);
		if (setup_completed.is_valid()) {
			setup_completed.call_deferred();
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
