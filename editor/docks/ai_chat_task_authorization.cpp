/**************************************************************************/
/*  ai_chat_task_authorization.cpp                                        */
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

#include "core/config/project_settings.h"
#include "editor/docks/ai_chat_dock.h"
#include "scene/gui/check_box.h"
#include "scene/gui/label.h"

Dictionary AIChatDock::_native_task_scope() const {
	Dictionary scope;
	scope["project"] = ProjectSettings::get_singleton()->get_resource_path();
	scope["issue"] = _work_order_binding("issue_number").to_int();
	scope["request"] = _work_order_binding("request_id");
	scope["conversation"] = conversation_id;
	scope["generation"] = int64_t(session_generation);
	return scope;
}

void AIChatDock::_revoke_native_task() {
	task_native_epoch++;
	task_native_grant.revoke();
	if (task_native_authorization) {
		task_native_authorization->set_pressed_no_signal(false);
	}
	if (task_native_scope) {
		task_native_scope->set_text(U"当前任务未授权原生编辑操作");
	}
}

void AIChatDock::_native_task_toggled(bool p_enabled) {
	_revoke_native_task();
	if (!p_enabled) {
		return;
	}
	const Dictionary scope = _native_task_scope();
	if (!allow_tools->is_pressed() || consultation_only->is_pressed() || (busy && consultation_turn) || _is_review_child() || snapshot_state.get("read_only_review_return", false) || !task_native_grant.grant(scope)) {
		task_native_scope->set_text(U"请先绑定当前工单和需求，并在开发模式开启本地工具后授权。");
		return;
	}
	task_native_authorization->set_pressed_no_signal(true);
	task_native_scope->set_text(vformat(U"已授权项目：%s\n工单 #%s · %s\n当前会话：%s", scope["project"], scope["issue"], scope["request"], scope["conversation"]));
}

bool AIChatDock::_native_task_allows(const String &p_tool, const Dictionary &p_arguments) {
	const Dictionary scope = _native_task_scope();
	if (!task_native_grant.matches(scope)) {
		_revoke_native_task();
		return false;
	}
	if (p_tool != "editor_action" && p_tool != "route_engine_message") {
		return false;
	}
	const Dictionary operation = p_tool == "route_engine_message" ? Dictionary(p_arguments.get("operation", Dictionary())) : p_arguments;
	return task_native_request_epoch == task_native_epoch && allow_tools->is_pressed() && task_native_grant.allows(scope, operation.get("action", ""), consultation_turn || consultation_only->is_pressed() || _is_review_child() || bool(snapshot_state.get("read_only_review_return", false)));
}
