/**************************************************************************/
/*  ai_chat_olympus.cpp                                                   */
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
#include "core/io/dir_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/ai_chat_issue_guide.h"
#include "editor/docks/ai_chat_resume.h"
#include "editor/docks/olympus_panel.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/check_box.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"
#include "scene/main/timer.h"

bool AIChatDock::_record_olympus(const String &p_kind, const String &p_phase, const String &p_status) {
	if (consultation_turn) {
		return true;
	}
	if (olympus_reporting.is_empty()) {
		return false;
	}
	Dictionary event;
	const String id = "godot-event-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec());
	event["schema_version"] = 1;
	event["event_id"] = id;
	event["tenant_id"] = olympus_reporting["tenant_id"];
	event["request_id"] = olympus_reporting["request_ref"];
	event["source_ref"] = olympus_reporting["source_ref"];
	event["agent"] = olympus_reporting["agent"];
	event["kind"] = p_kind;
	event["occurred_at"] = Time::get_singleton()->get_datetime_string_from_system(true) + "Z";
	event["evidence_refs"] = Array();
	Dictionary payload;
	payload["phase"] = p_phase;
	payload["status"] = p_status;
	payload["binding"] = olympus_reporting;
	payload["input_tokens"] = Variant();
	payload["output_tokens"] = Variant();
	payload["reason"] = "Host lifecycle metadata only; provider token usage is not measured by this connector";
	if (p_kind == "step") {
		payload["step_key"] = String(olympus_reporting["request_ref"]) + ":" + p_phase;
		if (p_status != "running" && olympus_running_steps.has(p_phase)) {
			event["supersedes"] = olympus_running_steps[p_phase];
		}
	}
	event["payload"] = payload;
	const String folder = olympus_report_root.path_join(".olympus-outbox/chat");
	const String pending = folder.path_join(id + ".json");
	bool stored = DirAccess::make_dir_recursive_absolute(folder) == OK;
	if (stored) {
		Ref<FileAccess> file = FileAccess::open(pending + ".tmp", FileAccess::WRITE);
		stored = file.is_valid() && file->store_string(JSON::stringify(event));
		if (file.is_valid()) {
			file->flush();
			stored = stored && file->get_error() == OK;
			file.unref();
		}
		stored = stored && DirAccess::rename_absolute(pending + ".tmp", pending) == OK;
	}
	if (!stored) {
		_append(TTR("Error"), U"Olympus 事件无法持久保存，后续模型及工具执行已阻止。");
		return false;
	}
	if (p_kind == "step") {
		if (p_status == "running") {
			olympus_running_steps[p_phase] = id;
		} else {
			olympus_running_steps.erase(p_phase);
		}
	}
	set_meta("olympus_reporting", "queued");
	return true;
}

void AIChatDock::_flush_olympus(const Callable &p_continuation) {
	if (consultation_turn) {
		if (p_continuation.is_valid()) {
			p_continuation.call();
		}
		return;
	}
	olympus_receipt_continuation = p_continuation;
	olympus_continuation_generation = session_generation;
	olympus_receipt_reflush = olympus_receipt_pid >= 0;
	if (!olympus_receipt_reflush) {
		_start_olympus_flush();
	}
}

void AIChatDock::_poll_olympus_receipt() {
	if (OS::get_singleton()->is_process_running(olympus_receipt_pid)) {
		return;
	}
	olympus_receipt_timer->stop();
	olympus_receipt_pid = -1;
	Variant parsed;
	if (FileAccess::exists(olympus_receipt_path)) {
		parsed = JSON::parse_string(FileAccess::get_file_as_string(olympus_receipt_path));
		DirAccess::remove_absolute(olympus_receipt_path);
	}
	Dictionary result;
	if (parsed.get_type() == Variant::DICTIONARY) {
		result = parsed;
	}
	Callable continuation = olympus_receipt_continuation;
	olympus_receipt_continuation = Callable();
	const bool current = busy && olympus_continuation_generation == session_generation;
	if (olympus_receipt_reflush) {
		olympus_receipt_reflush = false;
		// A previous flush cannot acknowledge envelopes queued after it started.
		// Terminal envelopes also require a fresh flush, but never resume work.
		_flush_olympus(current ? continuation : Callable());
		return;
	}
	const bool ok = result.get("ok", false).get_type() == Variant::BOOL && bool(result.get("ok", false));
	if (olympus_receipt_generation != session_generation) {
		return;
	}
	set_meta("olympus_reporting", ok ? "recorded_file" : "pending_retry");
	if (!ok) {
		_append(TTR("Error"), U"Olympus 文件回执失败，队列已保留，后续模型及工具执行已阻止。");
		if (current && continuation.is_valid()) {
			_set_busy(false);
		}
		return;
	}
	if (current && continuation.is_valid()) {
		continuation.call();
	}
}

void AIChatDock::_end_olympus(const String &p_status) {
	if (consultation_turn) {
		return;
	}
	if (olympus_reporting.is_empty()) {
		return;
	}
	for (const Variant &phase : olympus_running_steps.keys()) {
		_record_olympus("step", phase, p_status == "completed" ? "succeeded" : p_status);
	}
	_record_olympus("coverage", "native_chat_messages_and_tools", "metadata_only_usage_unavailable");
	_record_olympus("request_end", "chat", p_status);
	olympus_reporting.clear();
	olympus_running_steps.clear();
	_flush_olympus(Callable());
}

void AIChatDock::_start_olympus_flush() {
	if (olympus_receipt_pid >= 0) {
		return;
	}
	olympus_receipt_path = EditorPaths::get_singleton()->get_cache_dir().path_join("olympus-receipt-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
	List<String> arguments;
	for (const String &arg : { olympus_report_root.path_join("tools/olympus_bridge.py"), String("flush"), String("--workspace"), olympus_report_root, String("--out"), olympus_receipt_path }) {
		arguments.push_back(arg);
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(olympus_report_python, arguments, &pid) != OK) {
		set_meta("olympus_reporting", "pending_retry");
		if (olympus_receipt_continuation.is_valid()) {
			olympus_receipt_continuation = Callable();
			_set_busy(false);
		}
		return;
	}
	olympus_receipt_pid = pid;
	olympus_receipt_generation = session_generation;
	if (!olympus_receipt_timer) {
		olympus_receipt_timer = memnew(Timer);
		olympus_receipt_timer->set_wait_time(0.1);
		olympus_receipt_timer->connect("timeout", callable_mp(this, &AIChatDock::_poll_olympus_receipt));
		add_child(olympus_receipt_timer);
	}
	olympus_receipt_timer->start();
}

void AIChatDock::_clear_olympus_files() {
	for (const String &path : { olympus_input_path, olympus_output_path }) {
		if (!path.is_empty() && FileAccess::exists(path)) {
			DirAccess::remove_absolute(path);
		}
	}
	olympus_input_path = String();
	olympus_output_path = String();
}

void AIChatDock::_begin_olympus_context() {
	if (olympus_pid >= 0) {
		_append(TTR("Error"), U"Olympus 上一轮校验尚未结束，请稍后重试。");
		_set_busy(false);
		return;
	}
	olympus_context = String();
	olympus_generation = session_generation;
	const String root = EDITOR_GET("olympus/workspace");
	const String python = EDITOR_GET("olympus/python");
	olympus_report_root = root;
	olympus_report_python = python;
	const String bridge = olympus_report_root.path_join("tools/olympus_bridge.py");
	if (root.is_empty() || python.is_empty() || !FileAccess::exists(bridge)) {
		for (int i = messages.size() - 1; i >= 0; i--) {
			Dictionary message = messages[i];
			if (String(message.get("role", "")) == "user") {
				issue_guide_outcome = message.get("content", "");
				break;
			}
		}
		issue_guide_state = "agent_error";
		_append(TTR("Error"), U"Olympus 未配置：请在 Olympus 页设置工作区和 Python。聊天不会绕过框架发送。");
		_set_busy(false);
		return;
	}
	String outcome;
	for (int i = messages.size() - 1; i >= 0; i--) {
		Dictionary message = messages[i];
		if (String(message.get("role", "")) == "user") {
			outcome = message.get("content", "");
			break;
		}
	}
	const String requirement_key = AIChatIssueGuide::requirement_key(conversation_id, snapshot_id, outcome, EDITOR_GET("olympus/issue_number"), EDITOR_GET("olympus/request_id"));
	if (tool_rounds == 0 && olympus_recovered_result.is_empty() && !scheduled_agents.has(active_agent) && issue_agent_checked != requirement_key) {
		_cancel_issue_guide(String());
		_begin_issue_agent(outcome);
		return;
	}
	const int64_t bound_issue = String(EDITOR_GET("olympus/issue_number")).to_int();
	const String bound_request = String(EDITOR_GET("olympus/request_id")).strip_edges();
	if (!AIChatIssueGuide::is_bound(bound_issue, bound_request) && _start_issue_guide()) {
		return;
	}
	Dictionary context_input;
	Dictionary host;
	host["id"] = "godot-editor";
	host["kind"] = "engine";
	context_input["protocol_version"] = 1;
	context_input["host"] = host;
	context_input["agent_id"] = "athena";
	context_input["issue_number"] = int64_t(String(EDITOR_GET("olympus/issue_number")).to_int());
	context_input["request_id"] = String(EDITOR_GET("olympus/request_id")).strip_edges();
	context_input["outcome"] = outcome;
	context_input["authority_ref"] = "godot-editor:user-chat:" + conversation_id;
	context_input["project"] = ProjectSettings::get_singleton()->get_resource_path();
	context_input["tools_enabled"] = allow_tools->is_pressed();
	context_input["file_changes_require_approval"] = !auto_apply_file_changes->is_pressed();
	context_input["execution_requires_approval"] = !auto_execute_commands->is_pressed();
	const String prefix = EditorPaths::get_singleton()->get_cache_dir().path_join("olympus-chat-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()));
	olympus_input_path = prefix + ".request.json";
	olympus_output_path = prefix + ".result.json";
	Ref<FileAccess> file = FileAccess::open(olympus_input_path, FileAccess::WRITE);
	if (file.is_null()) {
		_append(TTR("Error"), U"无法保存 Olympus 校验请求，未发送聊天。");
		_set_busy(false);
		return;
	}
	file->store_string(JSON::stringify(context_input));
	file.unref();
	List<String> args;
	for (const String &argument : { bridge, String("chat"), String("--workspace"), root, String("--tenant"), String(EDITOR_GET("olympus/tenant")), String("--request"), olympus_input_path, String("--out"), olympus_output_path }) {
		args.push_back(argument);
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(python, args, &pid) != OK) {
		_clear_olympus_files();
		_append(TTR("Error"), U"无法启动 Olympus 校验，请检查 Python 路径。");
		_set_busy(false);
		return;
	}
	olympus_pid = pid;
	if (!olympus_timer) {
		olympus_timer = memnew(Timer);
		olympus_timer->set_wait_time(0.1);
		olympus_timer->connect("timeout", callable_mp(this, &AIChatDock::_poll_olympus_context));
		add_child(olympus_timer);
	}
	_set_activity(U"正在调用 Olympus：校验上游、准入与数据记录");
	olympus_timer->start();
}

void AIChatDock::_poll_olympus_context() {
	if (OS::get_singleton()->is_process_running(olympus_pid)) {
		return;
	}
	olympus_timer->stop();
	olympus_pid = -1;
	Variant parsed;
	if (FileAccess::exists(olympus_output_path)) {
		parsed = JSON::parse_string(FileAccess::get_file_as_string(olympus_output_path));
	}
	_clear_olympus_files();
	Dictionary result;
	if (parsed.get_type() == Variant::DICTIONARY) {
		result = parsed;
	}
	const bool cancelled = !busy || olympus_generation != session_generation;
	if (!olympus_reporting.is_empty() && result.get("reporting", Variant()).get_type() == Variant::DICTIONARY && olympus_reporting != Dictionary(result["reporting"])) {
		_append(TTR("Error"), U"Olympus 本轮框架或上报绑定已变化，请结束本轮并重新发送。");
		_set_busy(false);
		return;
	}
	if (result.get("reporting", Variant()).get_type() == Variant::DICTIONARY && olympus_reporting.is_empty()) {
		olympus_reporting = result["reporting"];
		const bool started = _record_olympus("request", "chat", "running") && _record_olympus("message", "user_message", "received_metadata_only");
		if (cancelled || !started) {
			_end_olympus(cancelled ? "cancelled" : "failed");
			if (!cancelled) {
				_set_busy(false);
			}
			return;
		}
	}
	if (cancelled) {
		return; // Late accepted context must never resume a cancelled request.
	}
	if (result.get("ok", false).get_type() != Variant::BOOL || !bool(result.get("ok", false)) || String(result.get("context", "")).is_empty() || olympus_reporting.is_empty()) {
		const String error = result.get("error", U"校验进程没有返回有效上下文。");
		if (issue_guide_state == "retrying") {
			// A guided binding that intake rejects keeps the conversation in the guide.
			set_meta("olympus_status", "issue_guide");
			issue_guide_state = "await_status";
			_append(TTR("Error"), String(U"Olympus 入口校验未通过：") + error);
			_issue_guide_prompt();
			_set_busy(false);
			return;
		}
		if (AIChatIssueGuide::is_binding_error(error) && _start_issue_guide()) {
			return;
		}
		set_meta("olympus_status", "blocked");
		_append(TTR("Error"), String(U"Olympus 阻止本次发送：") + error);
		_set_busy(false);
		return;
	}
	if (issue_guide_state == "retrying") {
		issue_guide_state = String();
		issue_guide_fields.clear();
		issue_guide_outcome = String();
	}
	olympus_context = result["context"];
	set_meta("olympus_status", "context_ready");
	if (!olympus_recovered_result.is_empty()) {
		if (!_record_olympus("step", "restart_result_recovery", "running")) {
			_set_busy(false);
			return;
		}
		_finish_tool(olympus_recovered_result);
		return;
	}
	olympus_resume = true;
	_request_completion();
}

static String last_user_content(const Array &p_messages) {
	for (int i = p_messages.size() - 1; i >= 0; i--) {
		const Dictionary message = p_messages[i];
		if (String(message.get("role", "")) == "user") {
			return message.get("content", "");
		}
	}
	return String();
}

static String guide_state_before(const String &p_action) {
	if (p_action == "issue-draft") {
		return "request_id";
	}
	return p_action == "issue-create" ? "confirm" : "await_status";
}

bool AIChatDock::_start_issue_guide() {
	if (scheduled_agents.has(active_agent) || !olympus_recovered_result.is_empty()) {
		return false; // Unattended and recovery turns keep the fail-closed rejection.
	}
	const String outcome = last_user_content(messages);
	if (outcome.strip_edges().is_empty()) {
		return false;
	}
	_cancel_issue_guide(String());
	issue_guide_outcome = outcome;
	issue_guide_state = "choose";
	set_meta("olympus_status", "issue_guide");
	_issue_guide_prompt();
	_set_busy(false);
	return true;
}

void AIChatDock::_begin_issue_agent(const String &p_outcome, bool p_retry, bool p_clarifying) {
	issue_guide_outcome = p_outcome;
	issue_guide_state = "agent_pending";
	_set_busy(false);
	Dictionary input_request;
	input_request["outcome"] = p_outcome;
	input_request["conversation_id"] = conversation_id + ":" + snapshot_id;
	issue_guide_fields["initial_issue"] = EDITOR_GET("olympus/issue_number");
	issue_guide_fields["initial_request"] = EDITOR_GET("olympus/request_id");
	input_request["issue_number"] = int64_t(String(EDITOR_GET("olympus/issue_number")).to_int());
	input_request["request_id"] = String(EDITOR_GET("olympus/request_id"));
	input_request["endpoint"] = endpoint->get_text().strip_edges();
	input_request["model"] = model->get_text().strip_edges();
	input_request["backend"] = backend->get_selected() == 1 ? "codebuddy" : "http";
	input_request["cli_node"] = cli_node->get_text().strip_edges();
	input_request["cli_entry"] = cli_entry->get_text().strip_edges();
	input_request["cli_model"] = cli_model->get_text().strip_edges();
	input_request["retry_authorized"] = p_retry;
	input_request["clarifying"] = p_clarifying;
	_issue_guide_run("issue-agent", input_request);
}

void AIChatDock::_issue_guide_prompt() {
	String text;
	if (issue_guide_state == "choose") {
		text = U"Olympus 需要先绑定本仓库的真实工单（GitHub Issue），才会把消息交给模型。这条消息已保留，绑定后会自动继续，无需重发。\n\n"
			   U"- 复用已有工单：回复 `#编号 需求ID`，例如 `#22 godot-chat-issue-guide-20261103`\n"
			   U"- 新建工单：回复 `新建`\n"
			   U"- 放弃：回复 `取消`\n\n"
			   U"工单引导由编辑器本地处理，不调用模型或工具。";
	} else if (issue_guide_state == "category") {
		text = U"新建工单 1/3 · 选择类别（回复序号或名称）：";
		for (int i = 0; i < issue_guide_categories.size(); i++) {
			const Dictionary category = issue_guide_categories[i];
			text += vformat(U"\n%d. `%s` %s", i + 1, String(category["name"]), String(category.get("description", "")));
		}
	} else if (issue_guide_state == "title") {
		text = String(U"新建工单 2/3 · 回复 Issue 标题（单行，最长 120 字），或回复 `默认` 使用：\n\n> ") + String(issue_guide_fields["title_suggestion"]);
	} else if (issue_guide_state == "request_id") {
		text = String(U"新建工单 3/3 · 回复稳定需求 ID（小写字母、数字和连字符，最长 80），或回复 `默认` 使用：`") + String(issue_guide_fields["request_id_suggestion"]) + "`";
	} else if (issue_guide_state == "confirm") {
		PackedStringArray labels;
		for (const Variant &label : Array(issue_guide_fields.get("labels", Array()))) {
			labels.push_back("`" + String(label) + "`");
		}
		text = vformat(U"已生成需求文档 `%s`，其中包含本次消息原文，请先审查并脱敏；它需要随实现一起提交。\n\n将在 `%s` 创建 Issue：\n- 标题：%s\n- 标签：%s\n\n回复 `确认` 创建；回复 `取消` 放弃（需求文档保留在本地，可手动删除）。",
				String(issue_guide_fields["document"]), String(issue_guide_fields["repository"]), String(issue_guide_fields["title"]), String(U"、").join(labels));
		if (!bool(issue_guide_fields.get("gh_available", false))) {
			text += U"\n\n注意：本机未找到 GitHub CLI（gh），确认后会给出可在其他环境执行的创建命令。";
		} else if (!bool(issue_guide_fields.get("gh_authenticated", false))) {
			text += "\n\n" + AIChatIssueGuide::gh_login_text(issue_guide_fields.get("gh_login_command", ""), U"确认");
		}
	} else if (issue_guide_state == "await_status") {
		text = vformat(U"已绑定工单 #%d（`%s`）。门禁要求工单为 `status:in-progress` 或 `status:in-review`，且带 `workspace:olympus` 标签；新工单默认为 `status:needs-decision`，是否开工需人工决定。\n\n"
					   U"- 确认开工：回复 `开始`，编辑器将把状态从待判断/计划中改为 `status:in-progress`，再用原消息继续\n"
					   U"- 已在 GitHub 修改：回复 `已更新`\n"
					   U"- 改绑其他工单：回复 `#编号 需求ID`\n"
					   U"- 放弃：回复 `取消`",
				int64_t(issue_guide_fields.get("issue_number", 0)), String(issue_guide_fields.get("request_id", "")));
	}
	if (!text.is_empty()) {
		_append(TTR("Editor"), text);
	}
}

void AIChatDock::_issue_guide_reply(const String &p_text) {
	if (AIChatIssueGuide::is_cancel(p_text)) {
		_cancel_issue_guide(U"已退出工单引导。原消息仍保留在会话里；绑定工单后再发送消息即可继续。");
		return;
	}
	if (issue_guide_pid >= 0) {
		_append(TTR("Editor"), U"工单引导正在处理上一步，请稍候；回复 `取消` 可放弃。");
		return;
	}
	if (issue_guide_state == "agent_questions") {
		_begin_issue_agent(issue_guide_outcome + "\n用户补充：" + p_text, false, true);
		return;
	}
	if (issue_guide_state == "agent_error") {
		if (AIChatIssueGuide::is_retry(p_text)) {
			_begin_issue_agent(issue_guide_outcome, true);
		} else {
			_append(TTR("Editor"), U"请先修复 Olympus 页的环境、需求 Agent 的 HTTP/CLI 模型配置或 GitHub 访问，再回复“重试”；工单尚未完成绑定，不会进入开发执行。");
		}
		return;
	}
	if (issue_guide_state == "retrying") {
		issue_guide_state = "await_status"; // The retry ended before reaching intake.
	}
	int64_t number = 0;
	String request_id;
	if (AIChatIssueGuide::parse_binding(p_text, number, request_id)) {
		_issue_guide_bind(number, request_id);
		_issue_guide_retry();
		return;
	}
	const String text = p_text.strip_edges();
	if (issue_guide_state == "choose") {
		if (AIChatIssueGuide::is_create(text)) {
			const String labels = String(EDITOR_GET("olympus/workspace")).path_join(".github/labels.json");
			issue_guide_categories = AIChatIssueGuide::categories_from_labels(FileAccess::exists(labels) ? JSON::parse_string(FileAccess::get_file_as_string(labels)) : Variant());
			if (issue_guide_categories.is_empty()) {
				_append(TTR("Error"), U"无法从工作区 `.github/labels.json` 读取任务类别，不能在此新建工单；可回复 `#编号 需求ID` 复用已有工单。");
				return;
			}
			issue_guide_state = "category";
		} else if (AIChatIssueGuide::is_reuse(text)) {
			_append(TTR("Editor"), U"请回复 `#编号 需求ID`。需求 ID 是工单正文中 `<!-- olympus-request:… -->` 标记或“稳定需求 ID”字段的值。");
			return;
		}
	} else if (issue_guide_state == "category") {
		const String category = AIChatIssueGuide::category_from_reply(text, issue_guide_categories);
		if (category.is_empty()) {
			_append(TTR("Error"), U"未识别的类别。");
		} else {
			issue_guide_fields["category"] = category;
			issue_guide_fields["title_suggestion"] = AIChatIssueGuide::suggest_title(issue_guide_outcome);
			issue_guide_state = "title";
		}
	} else if (issue_guide_state == "title") {
		const String guide_title = AIChatIssueGuide::is_default(text) ? String(issue_guide_fields["title_suggestion"]) : text;
		if (guide_title.contains("\n") || guide_title.contains("\r") || guide_title.length() > AIChatIssueGuide::MAX_TITLE) {
			_append(TTR("Error"), U"标题需为单行，且不超过 120 字。");
		} else {
			issue_guide_fields["title"] = guide_title;
			const String stamp = Time::get_singleton()->get_datetime_string_from_system().replace("-", "").replace(":", "").replace("T", "-");
			issue_guide_fields["request_id_suggestion"] = AIChatIssueGuide::suggest_request_id(guide_title, stamp);
			issue_guide_state = "request_id";
		}
	} else if (issue_guide_state == "request_id") {
		const String id = AIChatIssueGuide::is_default(text) ? String(issue_guide_fields["request_id_suggestion"]) : text;
		if (!AIChatIssueGuide::is_request_id(id)) {
			_append(TTR("Error"), U"需求 ID 只能包含小写字母、数字和单个连字符，且不能以连字符开头或结尾。");
		} else {
			issue_guide_fields["request_id"] = id;
			Dictionary draft;
			draft["request_id"] = id;
			draft["title"] = issue_guide_fields["title"];
			draft["category"] = issue_guide_fields["category"];
			draft["outcome"] = issue_guide_outcome;
			_issue_guide_run("issue-draft", draft);
			return;
		}
	} else if (issue_guide_state == "confirm") {
		if (AIChatIssueGuide::is_confirm(text)) {
			Dictionary create;
			create["request_id"] = issue_guide_fields["request_id"];
			create["title"] = issue_guide_fields["title"];
			create["category"] = issue_guide_fields["category"];
			create["outcome"] = issue_guide_outcome;
			_issue_guide_run("issue-create", create);
			return;
		}
	} else if (issue_guide_state == "await_status") {
		if (AIChatIssueGuide::is_start(text)) {
			Dictionary start;
			start["issue_number"] = issue_guide_fields.get("issue_number", 0);
			start["request_id"] = issue_guide_fields.get("request_id", "");
			_issue_guide_run("issue-start", start);
			return;
		}
		if (AIChatIssueGuide::is_retry(text)) {
			_issue_guide_retry();
			return;
		}
	}
	_issue_guide_prompt();
}

void AIChatDock::_issue_guide_run(const String &p_action, const Dictionary &p_request) {
	if (p_action == "issue-agent") {
		issue_guide_state = "agent_error"; // All early configuration/start failures remain retryable.
	}
	const String root = EDITOR_GET("olympus/workspace");
	const String python = EDITOR_GET("olympus/python");
	const String bridge = root.path_join("tools/olympus_bridge.py");
	if (root.is_empty() || python.is_empty() || !FileAccess::exists(bridge)) {
		_append(TTR("Error"), U"Olympus 未配置：请在 Olympus 页设置工作区和 Python。");
		return;
	}
	const String prefix = EditorPaths::get_singleton()->get_cache_dir().path_join("olympus-issue-guide-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()));
	issue_guide_input_path = prefix + ".request.json";
	issue_guide_output_path = prefix + ".result.json";
	Ref<FileAccess> file = FileAccess::open(issue_guide_input_path, FileAccess::WRITE);
	if (file.is_null()) {
		_append(TTR("Error"), U"无法保存工单引导请求。");
		return;
	}
	file->store_string(JSON::stringify(p_request));
	file.unref();
	List<String> args;
	for (const String &argument : { bridge, p_action, String("--workspace"), root, String("--tenant"), String(EDITOR_GET("olympus/tenant")), String("--request"), issue_guide_input_path, String("--out"), issue_guide_output_path }) {
		args.push_back(argument);
	}
	ProcessID pid = 0;
	Error process_error = OK;
	if (p_action == "issue-agent") {
		Dictionary process = OS::get_singleton()->execute_with_pipe(python, args, false);
		pid = int64_t(process.get("pid", 0));
		Ref<FileAccess> pipe = process.get("stdio", Variant());
		if (pid <= 0 || pipe.is_null()) {
			process_error = ERR_CANT_FORK;
		} else {
			Dictionary credentials;
			credentials["api_key"] = api_key->get_text().strip_edges();
			pipe->store_string(JSON::stringify(credentials) + "\n");
			pipe->flush();
		}
	} else {
		process_error = OS::get_singleton()->create_process(python, args, &pid);
	}
	if (process_error != OK) {
		if (pid > 0) {
			OS::get_singleton()->kill(pid);
		}
		_clear_issue_guide_files();
		_append(TTR("Error"), U"无法启动 Olympus 桥接，请检查 Python 路径。");
		return;
	}
	issue_guide_pid = pid;
	issue_guide_action = p_action;
	issue_guide_run_generation = issue_guide_generation;
	issue_guide_state = p_action == "issue-draft" ? "drafting" : p_action == "issue-create" ? "creating"
																							: "starting";
	if (!issue_guide_timer) {
		issue_guide_timer = memnew(Timer);
		issue_guide_timer->set_wait_time(0.1);
		issue_guide_timer->connect("timeout", callable_mp(this, &AIChatDock::_poll_issue_guide));
		add_child(issue_guide_timer);
	}
	issue_guide_timer->start();
	_append(TTR("Editor"), p_action == "issue-draft" ? String(U"正在生成需求文档并预览 Issue…") : p_action == "issue-create" ? String(U"正在 GitHub 创建 Issue…")
																															 : String(U"正在更新工单状态…"));
}

void AIChatDock::_poll_issue_guide() {
	if (OS::get_singleton()->is_process_running(issue_guide_pid)) {
		return;
	}
	issue_guide_timer->stop();
	issue_guide_pid = -1;
	Variant parsed;
	if (FileAccess::exists(issue_guide_output_path)) {
		parsed = JSON::parse_string(FileAccess::get_file_as_string(issue_guide_output_path));
	}
	_clear_issue_guide_files();
	if (issue_guide_run_generation != issue_guide_generation || issue_guide_state.is_empty()) {
		return; // A cancelled guide never applies a late result.
	}
	Dictionary result;
	if (parsed.get_type() == Variant::DICTIONARY) {
		result = parsed;
	}
	const bool ok = result.get("ok", false).get_type() == Variant::BOOL && bool(result.get("ok", false));
	const String error = result.get("error", U"桥接进程没有返回有效结果。");
	if (issue_guide_action == "issue-agent") {
		if (issue_guide_fields.get("initial_issue", Variant()) != EDITOR_GET("olympus/issue_number") || issue_guide_fields.get("initial_request", Variant()) != EDITOR_GET("olympus/request_id")) {
			issue_guide_state = "agent_error";
			_append(TTR("Editor"), U"处理期间工单绑定已改变，旧结果不会覆盖新绑定。请回复“重试”按当前绑定核对。");
			return;
		}
		if (!ok) {
			issue_guide_state = "agent_error";
			_append(TTR("Error"), String(U"Athena 需求建单尚未完成，开发执行仍暂停。请先修复环境、模型 API 或 GitHub 权限，再回复“重试”。已发送的远程请求可能已生效，重试会按稳定需求 ID 对账。\n") + error);
			if (error == "gh_unauthenticated") {
				_append(TTR("Editor"), AIChatIssueGuide::gh_login_text(result.get("login_command", ""), U"重试"));
			}
			return;
		}
		_issue_guide_bind(int64_t(result.get("issue_number", 0)), String(result.get("request_id", "")));
		_append(TTR("Editor"), String(U"Athena / Metis 已整理需求并关联真实工单：") + String(result.get("url", "")));
		if (!bool(result.get("ready", false))) {
			issue_guide_state = "agent_questions";
			for (const Variant &question : Array(result.get("questions", Array()))) {
				_append(U"Athena", question);
			}
			return;
		}
		if (last_user_content(messages) != issue_guide_outcome) {
			Dictionary clarified;
			clarified["role"] = "user";
			clarified["content"] = issue_guide_outcome;
			messages.push_back(clarified);
		}
		issue_agent_checked = AIChatIssueGuide::requirement_key(conversation_id, snapshot_id, last_user_content(messages), EDITOR_GET("olympus/issue_number"), EDITOR_GET("olympus/request_id"));
		_issue_guide_retry();
		return;
	}
	issue_guide_state = guide_state_before(issue_guide_action);
	if (issue_guide_action == "issue-draft") {
		if (!ok) {
			_append(TTR("Error"), String(U"需求文档生成失败：") + error);
		} else {
			for (const String &key : { String("document"), String("repository"), String("labels"), String("gh_available"), String("gh_authenticated"), String("gh_login_command") }) {
				issue_guide_fields[key] = result.get(key, Variant());
			}
			issue_guide_state = "confirm";
		}
		_issue_guide_prompt();
	} else if (issue_guide_action == "issue-create") {
		const int64_t number = ok ? int64_t(result.get("number", 0)) : 0;
		if (ok && number >= 1) {
			_issue_guide_bind(number, issue_guide_fields["request_id"]);
			const String found = String(result.get("state", "")) == "existing" ? String(U"找到同一需求 ID 的已有") : String(U"已创建");
			_append(TTR("Editor"), vformat(U"%s Issue #%d：%s ，并已写入 Olympus 页绑定。", found, number, String(result.get("url", ""))));
			issue_guide_state = "await_status";
			_issue_guide_prompt();
		} else if (error == "gh_unavailable") {
			_append(TTR("Error"), String(U"本机未找到 GitHub CLI（gh），未创建远程 Issue。可在有仓库写权限的环境中于工作区根目录执行：\n\n```\n") + String(result.get("command", "")) + "\n```\n\n" + vformat(U"创建后回复 `#编号 %s` 绑定；或安装并登录 gh 后回复 `确认` 重试。", String(issue_guide_fields["request_id"])));
		} else if (error == "gh_unauthenticated") {
			issue_guide_fields["gh_authenticated"] = false;
			issue_guide_fields["gh_login_command"] = result.get("login_command", "");
			_append(TTR("Error"), String(U"未创建远程 Issue。") + AIChatIssueGuide::gh_login_text(result.get("login_command", ""), U"确认") + vformat(U"\n\n也可在其他已登录环境于工作区根目录执行下列命令，创建后回复 `#编号 %s` 绑定：\n\n```\n", String(issue_guide_fields["request_id"])) + String(result.get("command", "")) + "\n```");
		} else {
			_append(TTR("Error"), String(U"创建 Issue 失败，未绑定：") + error);
			_issue_guide_prompt();
		}
	} else {
		if (ok) {
			_append(TTR("Editor"), vformat(U"工单 #%d 状态为 `%s`。", int64_t(issue_guide_fields.get("issue_number", 0)), String(result.get("status", ""))));
			_issue_guide_retry();
		} else if (error == "gh_unauthenticated") {
			_append(TTR("Error"), String(U"未更新工单状态。") + AIChatIssueGuide::gh_login_text(result.get("login_command", ""), U"开始") + U"\n\n也可在 GitHub 网页上修改状态后回复 `已更新`。");
		} else {
			_append(TTR("Error"), String(U"更新工单状态失败：") + (error == "gh_unavailable" ? String(U"本机未找到 GitHub CLI（gh），请在 GitHub 上修改后回复 `已更新`。") : error));
			_issue_guide_prompt();
		}
	}
}

void AIChatDock::_clear_issue_guide_files() {
	for (const String &path : { issue_guide_input_path, issue_guide_output_path }) {
		if (!path.is_empty() && FileAccess::exists(path)) {
			DirAccess::remove_absolute(path);
		}
	}
	issue_guide_input_path = String();
	issue_guide_output_path = String();
}

void AIChatDock::_cancel_issue_guide(const String &p_notice) {
	const bool active = !issue_guide_state.is_empty() || issue_guide_pid >= 0;
	if (issue_guide_action == "issue-agent" && issue_guide_pid >= 0) {
		_append(TTR("Editor"), U"已取消本地需求流程。已发送的远程请求无法撤回；再次处理相同需求时会先核对原请求，不会直接重复建单。");
	}
	issue_guide_generation++;
	if (issue_guide_pid >= 0) {
		if (OS::get_singleton()->is_process_running(issue_guide_pid)) {
			OS::get_singleton()->kill(issue_guide_pid);
		}
		issue_guide_pid = -1;
	}
	if (issue_guide_timer) {
		issue_guide_timer->stop();
	}
	_clear_issue_guide_files();
	issue_guide_state = String();
	issue_guide_fields.clear();
	issue_guide_outcome = String();
	issue_guide_categories.clear();
	if (!active) {
		return;
	}
	set_meta("olympus_status", "issue_guide_cancelled");
	if (!p_notice.is_empty()) {
		_append(TTR("Editor"), p_notice);
	}
}

void AIChatDock::_issue_guide_bind(int64_t p_number, const String &p_request_id) {
	EditorSettings::get_singleton()->set("olympus/issue_number", itos(p_number));
	EditorSettings::get_singleton()->set("olympus/request_id", p_request_id);
	EditorSettings::save();
	if (olympus_panel) {
		olympus_panel->reload_issue_binding();
	}
	issue_guide_fields["issue_number"] = p_number;
	issue_guide_fields["request_id"] = p_request_id;
}

void AIChatDock::_issue_guide_retry() {
	if (busy) {
		return;
	}
	if (last_user_content(messages).strip_edges().is_empty()) {
		_cancel_issue_guide(U"工单已绑定，但原消息已不在当前会话中，请重新发送。");
		return;
	}
	issue_guide_state = "retrying";
	_append(TTR("Editor"), vformat(U"已绑定工单 #%d（`%s`），正在用原消息重新进行 Olympus 入口校验。", int64_t(issue_guide_fields.get("issue_number", 0)), String(issue_guide_fields.get("request_id", ""))));
	// Same paused turn: the original user message is still the last entry in `messages`.
	_begin_reply();
	turn_completed = false;
	tool_rounds = 0;
	turn_model_requests = 0;
	session_generation++;
	_set_busy(true);
	_request_completion();
}
