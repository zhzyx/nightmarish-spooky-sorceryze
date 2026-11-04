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
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/docks/gonggong_host_paths.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/button.h"
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
	output = memnew(TextEdit);
	output->set_name("GongGongOutput");
	output->set_editable(false);
	output->set_v_size_flags(SIZE_EXPAND_FILL);
	add_child(output);
	timer = memnew(Timer);
	timer->set_wait_time(0.25);
	timer->connect("timeout", callable_mp(this, &GongGongPanel::poll));
	add_child(timer);
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
	if (FileAccess::exists(result_path)) {
		output->set_text(FileAccess::get_file_as_string(result_path));
		DirAccess::remove_absolute(result_path);
	} else {
		output->set_text(U"检查进程未返回结果，请检查 Python 和工作区配置。");
	}
}
