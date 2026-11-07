/**************************************************************************/
/*  ai_chat_gonggong.cpp                                                  */
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
#include "editor/docks/ai_chat_host_runtime.h"
#include "editor/docks/ai_chat_issue_guide.h"
#include "editor/docks/ai_chat_requirement_context.h"
#include "editor/docks/ai_chat_resume.h"
#include "editor/docks/gonggong_panel.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/check_box.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"
#include "scene/gui/text_edit.h"
#include "scene/main/timer.h"

bool AIChatDock::_record_gonggong(const String &p_kind, const String &p_phase, const String &p_status) {
	if (consultation_turn) {
		return true;
	}
	if (gonggong_reporting.is_empty()) {
		return false;
	}
	Dictionary event;
	const String id = "godot-event-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec());
	event["schema_version"] = 1;
	event["event_id"] = id;
	event["tenant_id"] = gonggong_reporting["tenant_id"];
	event["request_id"] = gonggong_reporting["request_ref"];
	event["source_ref"] = gonggong_reporting["source_ref"];
	event["agent"] = gonggong_reporting["agent"];
	event["kind"] = p_kind;
	event["occurred_at"] = Time::get_singleton()->get_datetime_string_from_system(true) + "Z";
	event["evidence_refs"] = Array();
	Dictionary payload;
	payload["phase"] = p_phase;
	payload["status"] = p_status;
	payload["binding"] = gonggong_reporting;
	payload["input_tokens"] = Variant();
	payload["output_tokens"] = Variant();
	payload["reason"] = "Host lifecycle metadata only; provider token usage is not measured by this connector";
	if (p_kind == "step") {
		payload["step_key"] = String(gonggong_reporting["request_ref"]) + ":" + p_phase;
		if (p_status != "running" && gonggong_running_steps.has(p_phase)) {
			event["supersedes"] = gonggong_running_steps[p_phase];
		}
	}
	event["payload"] = payload;
	const String folder = gonggong_report_root.path_join(".gonggong-outbox/chat");
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
		_append(TTR("Error"), U"GongGong 事件无法持久保存，后续模型及工具执行已阻止。");
		return false;
	}
	if (p_kind == "step") {
		if (p_status == "running") {
			gonggong_running_steps[p_phase] = id;
		} else {
			gonggong_running_steps.erase(p_phase);
		}
	}
	if (p_kind == "request" || p_kind == "request_end" || p_kind == "step") {
		const Dictionary agent = gonggong_reporting["agent"];
		emit_signal("daqian_work_event", gonggong_report_root, gonggong_reporting, vformat("%s · AI Chat #%d", agent["id"], active_agent), p_kind, p_phase, p_status);
	}
	set_meta("gonggong_reporting", "queued");
	return true;
}

void AIChatDock::_flush_gonggong(const Callable &p_continuation) {
	if (consultation_turn) {
		if (p_continuation.is_valid()) {
			p_continuation.call();
		}
		return;
	}
	gonggong_receipt_continuation = p_continuation;
	gonggong_continuation_generation = session_generation;
	gonggong_receipt_reflush = gonggong_receipt_pid >= 0;
	if (!gonggong_receipt_reflush) {
		_start_gonggong_flush();
	}
}

void AIChatDock::_poll_gonggong_receipt() {
	if (OS::get_singleton()->is_process_running(gonggong_receipt_pid)) {
		return;
	}
	gonggong_receipt_timer->stop();
	gonggong_receipt_pid = -1;
	Variant parsed;
	if (FileAccess::exists(gonggong_receipt_path)) {
		parsed = JSON::parse_string(FileAccess::get_file_as_string(gonggong_receipt_path));
		DirAccess::remove_absolute(gonggong_receipt_path);
	}
	Dictionary result;
	if (parsed.get_type() == Variant::DICTIONARY) {
		result = parsed;
	}
	Callable continuation = gonggong_receipt_continuation;
	gonggong_receipt_continuation = Callable();
	const bool current = busy && gonggong_continuation_generation == session_generation;
	if (gonggong_receipt_reflush) {
		gonggong_receipt_reflush = false;
		// A previous flush cannot acknowledge envelopes queued after it started.
		// Terminal envelopes also require a fresh flush, but never resume work.
		_flush_gonggong(current ? continuation : Callable());
		return;
	}
	const bool ok = result.get("ok", false).get_type() == Variant::BOOL && bool(result.get("ok", false));
	if (gonggong_receipt_generation != session_generation) {
		return;
	}
	set_meta("gonggong_reporting", ok ? "recorded_file" : "pending_retry");
	if (!ok) {
		_append(TTR("Error"), U"GongGong 文件回执失败，队列已保留，后续模型及工具执行已阻止。");
		if (current && continuation.is_valid()) {
			_set_busy(false);
		}
		return;
	}
	if (current && continuation.is_valid()) {
		continuation.call();
	}
}

void AIChatDock::_end_gonggong(const String &p_status) {
	if (consultation_turn) {
		return;
	}
	if (gonggong_reporting.is_empty()) {
		return;
	}
	for (const Variant &phase : gonggong_running_steps.keys()) {
		_record_gonggong("step", phase, p_status == "completed" ? "succeeded" : p_status);
	}
	_record_gonggong("coverage", "native_chat_messages_and_tools", "metadata_only_usage_unavailable");
	_record_gonggong("request_end", "chat", p_status);
	gonggong_reporting.clear();
	gonggong_running_steps.clear();
	_flush_gonggong(Callable());
}

void AIChatDock::_start_gonggong_flush() {
	if (gonggong_receipt_pid >= 0) {
		return;
	}
	String provenance_error;
	if (!_recover_active_provenance(provenance_error)) {
		set_meta("gonggong_reporting", "pending_retry");
		_append(TTR("Error"), provenance_error);
		gonggong_receipt_continuation = Callable();
		_set_busy(false);
		return;
	}
	gonggong_receipt_path = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-receipt-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
	List<String> arguments;
	for (const String &arg : { gonggong_report_root.path_join("tools/gonggong_bridge.py"), String("flush"), String("--workspace"), gonggong_report_root, String("--out"), gonggong_receipt_path }) {
		arguments.push_back(arg);
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(gonggong_report_python, arguments, &pid) != OK) {
		set_meta("gonggong_reporting", "pending_retry");
		if (gonggong_receipt_continuation.is_valid()) {
			gonggong_receipt_continuation = Callable();
			_set_busy(false);
		}
		return;
	}
	gonggong_receipt_pid = pid;
	gonggong_receipt_generation = session_generation;
	if (!gonggong_receipt_timer) {
		gonggong_receipt_timer = memnew(Timer);
		gonggong_receipt_timer->set_wait_time(0.1);
		gonggong_receipt_timer->connect("timeout", callable_mp(this, &AIChatDock::_poll_gonggong_receipt));
		add_child(gonggong_receipt_timer);
	}
	gonggong_receipt_timer->start();
}

void AIChatDock::_clear_gonggong_files() {
	for (const String &path : { gonggong_input_path, gonggong_output_path }) {
		if (!path.is_empty() && FileAccess::exists(path)) {
			DirAccess::remove_absolute(path);
		}
	}
	gonggong_input_path = String();
	gonggong_output_path = String();
}

void AIChatDock::_environment_setup_completed() {
	if (issue_guide_state != "environment_setup") {
		return;
	}
	issue_guide_state = String();
	_begin_reply();
	_set_busy(true);
	_request_completion();
}

static String last_user_content(const Array &p_messages) {
	// A steering message amends the current requirement; it cannot replace the
	// original objective when the host revalidates scope and Issue bindings.
	int start = -1;
	for (int i = p_messages.size() - 1; i >= 0; i--) {
		const Dictionary message = p_messages[i];
		if (String(message.get("role", "")) == "user" && !bool(message.get("steering", false))) {
			start = i;
			break;
		}
	}
	String result;
	for (int i = MAX(start, 0); i < p_messages.size(); i++) {
		const Dictionary message = p_messages[i];
		if (String(message.get("role", "")) == "user") {
			if (!result.is_empty()) {
				result += "\n\nAdditional user instructions:\n";
			}
			result += String(message.get("content", ""));
		}
	}
	return result;
}

bool AIChatDock::_direct_daqian_task() const {
	const Dictionary bindings = EditorSettings::get_singleton()->get_project_metadata("daqian", "bindings", Dictionary());
	const Dictionary entry = bindings.get(conversation_id, Dictionary());
	const String request_id = entry.get("request_id", "");
	const String number = entry.get("issue_number", "");
	const String source = entry.get("issue_url", entry.get("source", ""));
	return request_id.begins_with("daqian-direct-") && AIChatIssueGuide::is_bound(number.to_int(), request_id) && source.ends_with("/issues/" + number);
}

void AIChatDock::_begin_gonggong_context() {
	AIChatHostRuntime::prepare_node(cli_node->get_text());
	const String outcome = last_user_content(messages);
	const String requirement_key = AIChatIssueGuide::requirement_key(conversation_id, snapshot_id, outcome, _work_order_binding("issue_number"), _work_order_binding("request_id"));
	// Scheduled and child Agents never run requirement intake or create Issues;
	// a child inherits the real Issue its parent's finalized design was bound to.
	const bool direct = _direct_daqian_task() && !scheduled_agents.has(active_agent) && !sub_agents.has(active_agent);
	bool amendment = false;
	for (const Variant &entry : messages) {
		const Dictionary message = entry;
		if (bool(message.get("steering", false)) && message.get("steering_snapshot", "") == snapshot_id) {
			amendment = true;
			break;
		}
	}
	const bool needs_intake = (!direct || amendment) && gonggong_recovered_result.is_empty() && !scheduled_agents.has(active_agent) && !sub_agents.has(active_agent) && issue_agent_checked != requirement_key;
	if (gonggong_pid >= 0) {
		if (needs_intake) {
			_emit_daqian_requirement_phase("error");
		}
		_append(TTR("Error"), U"GongGong 上一轮校验尚未结束，请稍后重试。");
		_set_busy(false);
		return;
	}
	if (gonggong_panel && !gonggong_panel->ensure_environment()) {
		issue_guide_state = "environment_setup";
		if (needs_intake) {
			_emit_daqian_requirement_phase("waiting_environment");
		}
		_append(TTR("Editor"), U"已触发本地配置点火器；原需求已保留。请在弹窗内完成本地部署，自检通过后自动继续识别需求与建单。");
		_set_busy(false);
		return;
	}
	gonggong_context = String();
	gonggong_generation = session_generation;
	String candidate_error;
	if (snapshot_state.has("engine_candidate") && (!_validate_engine_candidate(candidate_error) || !_recover_active_provenance(candidate_error))) {
		_append(TTR("Error"), candidate_error);
		_set_busy(false);
		return;
	}
	const String root = _workflow_root();
	const String python = EDITOR_GET("gonggong/python");
	gonggong_report_root = root;
	gonggong_report_python = python;
	const String bridge = gonggong_report_root.path_join("tools/gonggong_bridge.py");
	if (root.is_empty() || !FileAccess::exists(bridge)) {
		issue_guide_outcome = outcome;
		issue_guide_state = "agent_error";
		if (needs_intake) {
			_emit_daqian_requirement_phase("error");
		}
		_append(TTR("Error"), U"GongGong 未配置：请在 GongGong 页设置工作区，并确认引擎 tools/gonggong_bridge.py 已安装。聊天不会绕过框架发送。");
		_set_busy(false);
		return;
	}
	if (python.is_empty() || !FileAccess::exists(python)) {
		Array missing;
		missing.push_back("python");
		if (_start_igniter(missing)) {
			igniter_for_intake = needs_intake;
			if (needs_intake) {
				_emit_daqian_requirement_phase("waiting_environment");
			}
			return; // A missing Python is an environment gap, not a framework block.
		}
		issue_guide_outcome = outcome;
		issue_guide_state = "agent_error";
		if (needs_intake) {
			_emit_daqian_requirement_phase("error");
		}
		_append(TTR("Error"), U"GongGong 未配置：请在 GongGong 页设置 Python 可执行文件路径。聊天不会绕过框架发送。");
		_set_busy(false);
		return;
	}
	if (needs_intake) {
		_cancel_issue_guide(String());
		_begin_issue_agent(outcome);
		return;
	}
	int64_t bound_issue = String(_work_order_binding("issue_number")).to_int();
	String bound_request = String(_work_order_binding("request_id")).strip_edges();
	String authority = "godot-editor:user-chat:" + conversation_id;
	if (sub_agents.has(active_agent)) {
		const Dictionary info = sub_agents[active_agent];
		const int64_t child_issue = info.get("issue_number", 0);
		const String child_request = info.get("request_id", "");
		if (AIChatIssueGuide::is_bound(child_issue, child_request)) {
			bound_issue = child_issue;
			bound_request = child_request;
		}
		authority = "godot-editor:sub-agent:" + itos(int(info.get("parent", -1))) + ":" + conversation_id;
	}
	if (!AIChatIssueGuide::is_bound(bound_issue, bound_request) && _start_issue_guide()) {
		return;
	}
	Dictionary context_input;
	Dictionary host;
	host["id"] = "godot-editor";
	host["kind"] = "engine";
	context_input["protocol_version"] = 1;
	context_input["host"] = host;
	context_input["agent_id"] = direct ? "sinan" : "yanshi";
	context_input["issue_number"] = bound_issue;
	context_input["request_id"] = bound_request;
	const Dictionary bindings = EditorSettings::get_singleton()->get_project_metadata("daqian", "bindings", Dictionary());
	const Dictionary entry = bindings.get(conversation_id, Dictionary());
	if (!String(entry.get("source", "")).is_empty() && entry.get("request_id", "") == bound_request && String(entry.get("issue_number", "")).to_int() == bound_issue) {
		context_input["daqian_bound"] = true;
	}
	context_input["outcome"] = outcome;
	context_input["authority_ref"] = authority;
	context_input["project"] = ProjectSettings::get_singleton()->get_resource_path();
	context_input["tools_enabled"] = allow_tools->is_pressed();
	context_input["file_changes_require_approval"] = !auto_apply_file_changes->is_pressed();
	context_input["execution_requires_approval"] = !auto_execute_commands->is_pressed();
	const String prefix = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-chat-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()));
	gonggong_input_path = prefix + ".request.json";
	gonggong_output_path = prefix + ".result.json";
	Ref<FileAccess> file = FileAccess::open(gonggong_input_path, FileAccess::WRITE);
	if (file.is_null()) {
		_append(TTR("Error"), U"无法保存 GongGong 校验请求，未发送聊天。");
		_set_busy(false);
		return;
	}
	file->store_string(JSON::stringify(context_input));
	file.unref();
	List<String> args;
	for (const String &argument : { bridge, String("chat"), String("--workspace"), root, String("--tenant"), String(EDITOR_GET("gonggong/tenant")), String("--request"), gonggong_input_path, String("--out"), gonggong_output_path }) {
		args.push_back(argument);
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(python, args, &pid) != OK) {
		_clear_gonggong_files();
		_append(TTR("Error"), U"无法启动 GongGong 校验，请检查 Python 路径。");
		_set_busy(false);
		return;
	}
	gonggong_pid = pid;
	if (!gonggong_timer) {
		gonggong_timer = memnew(Timer);
		gonggong_timer->set_wait_time(0.1);
		gonggong_timer->connect("timeout", callable_mp(this, &AIChatDock::_poll_gonggong_context));
		add_child(gonggong_timer);
	}
	_set_activity(U"正在调用 GongGong：校验上游、准入与数据记录");
	gonggong_timer->start();
}

void AIChatDock::_poll_gonggong_context() {
	if (OS::get_singleton()->is_process_running(gonggong_pid)) {
		return;
	}
	gonggong_timer->stop();
	gonggong_pid = -1;
	Variant parsed;
	if (FileAccess::exists(gonggong_output_path)) {
		parsed = JSON::parse_string(FileAccess::get_file_as_string(gonggong_output_path));
	}
	_clear_gonggong_files();
	Dictionary result;
	if (parsed.get_type() == Variant::DICTIONARY) {
		result = parsed;
	}
	const bool cancelled = !busy || gonggong_generation != session_generation;
	if (!gonggong_reporting.is_empty() && result.get("reporting", Variant()).get_type() == Variant::DICTIONARY && gonggong_reporting != Dictionary(result["reporting"])) {
		_append(TTR("Error"), U"GongGong 本轮框架或上报绑定已变化，请结束本轮并重新发送。");
		_set_busy(false);
		return;
	}
	if (result.get("reporting", Variant()).get_type() == Variant::DICTIONARY && gonggong_reporting.is_empty()) {
		gonggong_reporting = result["reporting"];
		const bool started = _record_gonggong("request", "chat", "running") && _record_gonggong("message", "user_message", "received_metadata_only");
		if (cancelled || !started) {
			_end_gonggong(cancelled ? "cancelled" : "failed");
			if (!cancelled) {
				_set_busy(false);
			}
			return;
		}
	}
	if (cancelled) {
		return; // Late accepted context must never resume a cancelled request.
	}
	if (result.get("ok", false).get_type() != Variant::BOOL || !bool(result.get("ok", false)) || String(result.get("context", "")).is_empty() || gonggong_reporting.is_empty()) {
		const String error = result.get("error", U"校验进程没有返回有效上下文。");
		const Array missing = result.get("environment_missing", Array());
		if (missing.size() > 0 && _start_igniter(missing)) {
			return; // Environment gaps enter the local configuration igniter, not "blocked".
		}
		if (issue_guide_state == "retrying") {
			// A guided binding that intake rejects keeps the conversation in the guide.
			set_meta("gonggong_status", "issue_guide");
			issue_guide_state = "await_status";
			_append(TTR("Error"), String(U"GongGong 入口校验未通过：") + error);
			_issue_guide_prompt();
			_set_busy(false);
			return;
		}
		if (!_direct_daqian_task() && AIChatIssueGuide::is_binding_error(error) && _start_issue_guide()) {
			return;
		}
		set_meta("gonggong_status", "blocked");
		_append(TTR("Error"), String(U"GongGong 阻止本次发送：") + error);
		_set_busy(false);
		return;
	}
	if (issue_guide_state == "retrying") {
		issue_guide_state = String();
		issue_guide_fields.clear();
		issue_guide_outcome = String();
	}
	gonggong_context = result["context"];
	set_meta("gonggong_status", "context_ready");
	if (!gonggong_recovered_result.is_empty()) {
		if (!_record_gonggong("step", "restart_result_recovery", "running")) {
			_set_busy(false);
			return;
		}
		_finish_tool(gonggong_recovered_result);
		return;
	}
	gonggong_resume = true;
	_request_completion();
}

static String guide_state_before(const String &p_action) {
	if (p_action == "issue-draft") {
		return "request_id";
	}
	return p_action == "issue-create" ? "confirm" : "await_status";
}

bool AIChatDock::_start_issue_guide() {
	if (scheduled_agents.has(active_agent) || sub_agents.has(active_agent) || !gonggong_recovered_result.is_empty()) {
		return false; // Unattended, child and recovery turns keep the fail-closed rejection.
	}
	const String outcome = last_user_content(messages);
	if (outcome.strip_edges().is_empty()) {
		return false;
	}
	_cancel_issue_guide(String());
	issue_guide_outcome = outcome;
	issue_guide_state = "choose";
	set_meta("gonggong_status", "issue_guide");
	_issue_guide_prompt();
	_set_busy(false);
	return true;
}

void AIChatDock::_set_issue_model_config(Dictionary &r_request) const {
	r_request["endpoint"] = endpoint->get_text().strip_edges();
	r_request["model"] = model->get_text().strip_edges();
	static const char *backend_names[] = { "http", "codebuddy", "codex", "responses" };
	r_request["backend"] = backend_names[backend->get_selected()];
	r_request["cli_node"] = cli_node->get_text().strip_edges();
	r_request["cli_entry"] = (backend->get_selected() == 2 ? codex_entry : cli_entry)->get_text().strip_edges();
	r_request["cli_model"] = (backend->get_selected() == 2 ? codex_model : cli_model)->get_text().strip_edges();
}

static ProcessID launch_issue_model(const String &p_python, const List<String> &p_args, const String &p_api_key) {
	Dictionary process = OS::get_singleton()->execute_with_pipe(p_python, p_args, false);
	ProcessID pid = int64_t(process.get("pid", 0));
	Ref<FileAccess> pipe = process.get("stdio", Variant());
	if (pid <= 0 || pipe.is_null()) {
		if (pid > 0) {
			OS::get_singleton()->kill(pid);
		}
		return -1;
	}
	Dictionary credentials;
	credentials["api_key"] = p_api_key;
	pipe->store_string(JSON::stringify(credentials) + "\n");
	pipe->flush();
	return pid;
}

Dictionary AIChatDock::_launch_daqian_routing(const Dictionary &p_binding, const Dictionary &p_selection) const {
	AIChatHostRuntime::prepare_node(cli_node->get_text());
	Dictionary result;
	String candidate_error;
	if (snapshot_state.has("engine_candidate") && !_validate_engine_candidate(candidate_error)) {
		result["error"] = candidate_error;
		return result;
	}
	const String workspace = _workflow_root();
	const String python = EDITOR_GET("gonggong/python");
	const String bridge = workspace.path_join("tools/gonggong_bridge.py");
	if (workspace.is_empty() || python.is_empty() || !FileAccess::exists(bridge)) {
		result["error"] = U"请配置共工工作区和 Python 后重试判断。";
		return result;
	}
	Dictionary route_request = p_binding.duplicate();
	_set_issue_model_config(route_request);
	if (!p_selection.is_empty()) {
		if (int64_t(p_selection.get("backend", -1)) != backend->get_selected()) {
			result["error"] = U"请切回需求模型所属后端，或重新选择模型。";
			return result;
		}
		const bool cli = backend->get_selected() == 1 || backend->get_selected() == 2;
		route_request[cli ? "cli_model" : "model"] = p_selection.get("id", "");
	}
	if (backend->get_selected() == 2 && !FileAccess::exists(codex_entry->get_text().strip_edges())) {
		result["error"] = U"Codex 可执行文件路径已失效；请在工单对话与模型中更新路径，再选择司南模型重试。";
		return result;
	}
	if ((backend->get_selected() == 1 || backend->get_selected() == 2) && !FileAccess::exists(cli_node->get_text().strip_edges())) {
		result["error"] = U"Node 可执行文件路径已失效；请在工单对话与模型中更新路径后重试。";
		return result;
	}
	const String stem = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-issue-route-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()));
	const String input_path = stem + ".request";
	const String output_path = stem + ".result";
	Ref<FileAccess> file = FileAccess::open(input_path, FileAccess::WRITE);
	if (file.is_null()) {
		result["error"] = U"无法保存工单判断请求。";
		return result;
	}
	file->store_string(JSON::stringify(route_request));
	file.unref();
	List<String> args;
	for (const String &arg : { bridge, String("issue-route"), String("--workspace"), workspace, String("--request"), input_path, String("--out"), output_path }) {
		args.push_back(arg);
	}
	const ProcessID pid = launch_issue_model(python, args, api_key->get_text().strip_edges());
	if (pid <= 0) {
		DirAccess::remove_absolute(input_path);
		result["error"] = U"无法启动共工判断，请检查 Python 配置。";
		return result;
	}
	result["pid"] = int64_t(pid);
	result["input"] = input_path;
	result["output"] = output_path;
	return result;
}

void AIChatDock::_begin_issue_agent(const String &p_outcome, bool p_retry, bool p_clarifying) {
	issue_guide_outcome = p_outcome;
	issue_guide_state = "agent_pending";
	Dictionary input_request;
	input_request["outcome"] = p_outcome;
	// Intake runs before the normal model context. Preserve recent questions and
	// corrections here too, including after an earlier model request failed.
	const Array requirement_context = AIChatRequirementContext::select(transcript);
	if (p_retry && issue_guide_fields.has("conversation_context")) {
		// Reconcile the same journal even after progress/error messages appear.
		input_request["conversation_context"] = issue_guide_fields["conversation_context"];
	} else {
		issue_guide_fields["conversation_context"] = requirement_context;
		input_request["conversation_context"] = requirement_context;
	}
	input_request["conversation_id"] = conversation_id + ":" + snapshot_id;
	issue_guide_fields["initial_issue"] = _work_order_binding("issue_number");
	issue_guide_fields["initial_request"] = _work_order_binding("request_id");
	input_request["issue_number"] = int64_t(String(_work_order_binding("issue_number")).to_int());
	input_request["request_id"] = String(_work_order_binding("request_id"));
	// A correction belongs to this exact task. The requirements model may
	// identify unrelated work, but it cannot publish it or rebind this turn.
	if (AIChatIssueGuide::is_bound(int64_t(input_request["issue_number"]), input_request["request_id"])) {
		for (const Variant &entry : messages) {
			const Dictionary message = entry;
			if (bool(message.get("steering", false)) && String(message.get("steering_snapshot", "")) == snapshot_id) {
				input_request["continuation_only"] = true;
				break;
			}
		}
	}
	_set_issue_model_config(input_request);
	if (snapshot_state.has("daqian_model")) {
		const bool cli = backend->get_selected() == 1 || backend->get_selected() == 2;
		if (p_retry) {
			snapshot_state["daqian_model"] = _active_model_field()->get_text().strip_edges();
		}
		input_request[cli ? "cli_model" : "model"] = snapshot_state["daqian_model"];
	}
	input_request["retry_authorized"] = p_retry;
	input_request["clarifying"] = p_clarifying;
	_issue_guide_run("issue-agent", input_request);
	_emit_daqian_requirement_phase(issue_guide_pid >= 0 ? "analyzing" : "error");
}

void AIChatDock::_issue_guide_prompt() {
	String text;
	if (issue_guide_state == "choose") {
		text = U"GongGong 需要先绑定本仓库的真实工单（GitHub Issue），才会把消息交给模型。这条消息已保留，绑定后会自动继续，无需重发。\n\n"
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
		text = vformat(U"已绑定工单 #%d（`%s`）。门禁要求工单为 `status:in-progress` 或 `status:in-review`，且带 `workspace:gonggong` 标签；新工单默认为 `status:needs-decision`，是否开工需人工决定。\n\n"
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
	if (issue_guide_state == "environment_setup") {
		if (gonggong_panel && gonggong_panel->ensure_environment()) {
			_environment_setup_completed();
		} else {
			_append(TTR("Editor"), U"原需求等待本地配置完成；补充输入保留为草稿，请先完成点火器。");
			input->set_text(p_text);
		}
		return;
	}
	if (issue_guide_state == "agent_questions") {
		_begin_issue_agent(issue_guide_outcome + U"\n用户补充：" + p_text, false, true);
		return;
	}
	if (issue_guide_state == "agent_error") {
		if (AIChatIssueGuide::is_retry(p_text)) {
			if (_direct_daqian_task()) {
				_issue_guide_retry();
				return;
			}
			if (AIChatRequirementContext::mark_transport_retry(transcript, _redact(p_text))) {
				_queue_history_save();
			}
			_begin_issue_agent(issue_guide_outcome, true);
		} else {
			_append(TTR("Editor"), U"请先修复 GongGong 页的环境、需求会话的 HTTP/CLI 模型配置或 GitHub 访问，再回复“重试”；工单尚未完成绑定，不会进入开发执行。");
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
			const String labels = _workflow_root().path_join(".github/labels.json");
			issue_guide_categories = AIChatIssueGuide::categories_from_labels(FileAccess::exists(labels) ? JSON::parse_string(FileAccess::get_file_as_string(labels)) : Variant());
			if (issue_guide_categories.is_empty()) {
				_append(TTR("Error"), U"无法从工作区 `.github/labels.json` 读取任务类别，不能在此新建工单；可回复 `#编号 需求ID` 复用已有工单。");
				return;
			}
			issue_guide_state = "category";
		} else if (AIChatIssueGuide::is_reuse(text)) {
			_append(TTR("Editor"), U"请回复 `#编号 需求ID`。需求 ID 是工单正文中 `<!-- gonggong-request:… -->` 标记或“稳定需求 ID”字段的值。");
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
	String candidate_error;
	if (snapshot_state.has("engine_candidate") && !_validate_engine_candidate(candidate_error)) {
		_append(TTR("Error"), candidate_error);
		_set_busy(false);
		return;
	}
	const String root = _workflow_root();
	const String python = EDITOR_GET("gonggong/python");
	const String bridge = root.path_join("tools/gonggong_bridge.py");
	if (root.is_empty() || python.is_empty() || !FileAccess::exists(bridge)) {
		_append(TTR("Error"), U"GongGong 未配置：请在 GongGong 页设置工作区和 Python。");
		_set_busy(false);
		return;
	}
	const String prefix = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-issue-guide-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()));
	issue_guide_input_path = prefix + ".request.json";
	issue_guide_output_path = prefix + ".result.json";
	Ref<FileAccess> file = FileAccess::open(issue_guide_input_path, FileAccess::WRITE);
	if (file.is_null()) {
		_append(TTR("Error"), U"无法保存工单引导请求。");
		_set_busy(false);
		return;
	}
	file->store_string(JSON::stringify(p_request));
	file.unref();
	List<String> args;
	for (const String &argument : { bridge, p_action, String("--workspace"), root, String("--tenant"), String(EDITOR_GET("gonggong/tenant")), String("--request"), issue_guide_input_path, String("--out"), issue_guide_output_path }) {
		args.push_back(argument);
	}
	ProcessID pid = 0;
	Error process_error = OK;
	if (p_action == "issue-agent") {
		pid = launch_issue_model(python, args, api_key->get_text().strip_edges());
		process_error = pid > 0 ? OK : ERR_CANT_FORK;
	} else {
		process_error = OS::get_singleton()->create_process(python, args, &pid);
	}
	if (process_error != OK) {
		if (pid > 0) {
			OS::get_singleton()->kill(pid);
		}
		_clear_issue_guide_files();
		_append(TTR("Error"), U"无法启动 GongGong 桥接，请检查 Python 路径。");
		_set_busy(false);
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
	if (p_action == "issue-agent") {
		// Requirements intake is part of the active turn. Keeping it busy makes
		// subsequent submissions queue normally and keeps Stop available.
		if (!busy) {
			_begin_reply();
		}
		_set_busy(true);
		_set_activity(U"正在识别需求、整理设计文档并关联 Issue");
	}
	issue_guide_timer->start();
	_append(TTR("Editor"), p_action == "issue-agent" ? String(U"正在由偃师识别需求、整理设计文档并关联 Issue…") : p_action == "issue-draft" ? String(U"正在生成需求文档并预览 Issue…")
					: p_action == "issue-create"																							? String(U"正在 GitHub 创建 Issue…")
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
		if (issue_guide_fields.get("initial_issue", Variant()) != _work_order_binding("issue_number") || issue_guide_fields.get("initial_request", Variant()) != _work_order_binding("request_id")) {
			issue_guide_state = "agent_error";
			_emit_daqian_requirement_phase("error");
			_append(TTR("Editor"), U"处理期间工单绑定已改变，旧结果不会覆盖新绑定。请回复“重试”按当前绑定核对。");
			_set_busy(false);
			return;
		}
		if (!ok) {
			issue_guide_state = "agent_error";
			_emit_daqian_requirement_phase("error");
			if (error == "steering_requires_separate_task") {
				_append(TTR("Editor"), U"这条补充被识别为独立需求，当前任务已暂停；未新建或切换工单。请先停止当前任务，再通过新会话或大千的新需求入口办理。");
				_set_busy(false);
				return;
			}
			_append(TTR("Error"), String(U"Yanshi 需求建单尚未完成，开发执行仍暂停。请先修复环境、模型 API 或 GitHub 权限，再回复“重试”。已发送的远程请求可能已生效，重试会按稳定需求 ID 对账。\n") + error);
			if (error == "gh_unauthenticated") {
				_append(TTR("Editor"), AIChatIssueGuide::gh_login_text(result.get("login_command", ""), U"重试"));
			}
			_set_busy(false);
			return;
		}
		const int64_t number = result.get("issue_number", 0);
		const String request_id = result.get("request_id", "");
		if (!AIChatIssueGuide::is_bound(number, request_id) || result.get("ready", Variant()).get_type() != Variant::BOOL) {
			issue_guide_state = "agent_error";
			_emit_daqian_requirement_phase("error");
			_append(TTR("Error"), U"偃师回执缺少工单绑定或需求状态，请在关联对话中核对后重试。");
			_set_busy(false);
			return;
		}
		_issue_guide_bind(number, request_id);
		_append(TTR("Editor"), String(U"Yanshi / ClarifyFeature 已整理需求并关联真实工单：") + String(result.get("url", "")));
		Dictionary design;
		for (const String &field : { String("scope"), String("acceptance"), String("questions") }) {
			const Variant values = result.get(field, Variant());
			if (values.get_type() == Variant::ARRAY) {
				design[field] = values;
			}
		}
		const bool ready = result["ready"];
		_emit_daqian_requirement_phase(ready ? "ready" : "questions", design);
		if (!ready) {
			issue_guide_state = "agent_questions";
			for (const Variant &question : Array(design.get("questions", Array()))) {
				_append(U"Yanshi", question);
			}
			_set_busy(false);
			return;
		}
		if (last_user_content(messages) != issue_guide_outcome) {
			Dictionary clarified;
			clarified["role"] = "user";
			clarified["content"] = issue_guide_outcome;
			messages.push_back(clarified);
		}
		issue_agent_checked = AIChatIssueGuide::requirement_key(conversation_id, snapshot_id, last_user_content(messages), _work_order_binding("issue_number"), _work_order_binding("request_id"));
		// Continue the same busy turn; toggling idle here pauses already queued
		// requirements and falsely closes the active reply before development.
		issue_guide_state = "retrying";
		_request_completion();
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
			_append(TTR("Editor"), vformat(U"%s Issue #%d：%s ，并已写入 GongGong 页绑定。", found, number, String(result.get("url", ""))));
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
	if ((issue_guide_action == "issue-agent" && issue_guide_pid >= 0) || issue_guide_state == "agent_questions" || issue_guide_state == "environment_setup") {
		_emit_daqian_requirement_phase("cancelled");
	}
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
	set_meta("gonggong_status", "issue_guide_cancelled");
	if (!p_notice.is_empty()) {
		_append(TTR("Editor"), p_notice);
	}
}

void AIChatDock::_issue_guide_bind(int64_t p_number, const String &p_request_id) {
	const Dictionary candidate = snapshot_state.get("engine_candidate", Dictionary());
	if (!candidate.is_empty() && (int64_t(candidate.get("issue", 0)) != p_number || candidate.get("request_id", "") != p_request_id)) {
		// Intake for the new Issue was written here. Preserve that provenance route
		// until the host transfers it to the new Issue's own isolated source tree.
		snapshot_state["requirement_workspace"] = candidate["source_root"];
		snapshot_state.erase("engine_candidate");
	}
	EditorSettings *settings = EditorSettings::get_singleton();
	Dictionary bindings = settings->get_project_metadata("daqian", "bindings", Dictionary());
	Dictionary bound = bindings.get(conversation_id, Dictionary());
	if (String(bound.get("issue_number", "")).to_int() != p_number || bound.get("request_id", "") != p_request_id) {
		bound.erase("issue_url");
	}
	bound["issue_number"] = itos(p_number);
	bound["request_id"] = p_request_id;
	bindings[conversation_id] = bound;
	settings->set_project_metadata("daqian", "bindings", bindings);
	if (sub_agents.has(active_agent)) {
		Dictionary child = sub_agents[active_agent];
		child["issue_number"] = p_number;
		child["request_id"] = p_request_id;
		sub_agents[active_agent] = child;
	}
	issue_guide_fields["issue_number"] = p_number;
	issue_guide_fields["request_id"] = p_request_id;
	if (bound.has("source")) {
		emit_signal("daqian_issue_bound", bound["source"], p_number, p_request_id);
	}
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
	_append(TTR("Editor"), vformat(U"已绑定工单 #%d（`%s`），正在用原消息重新进行 GongGong 入口校验。", int64_t(issue_guide_fields.get("issue_number", 0)), String(issue_guide_fields.get("request_id", ""))));
	// Same paused turn: the original user message is still the last entry in `messages`.
	_begin_reply();
	turn_completed = false;
	tool_rounds = 0;
	turn_model_requests = 0;
	session_generation++;
	_set_busy(true);
	_request_completion();
}

bool AIChatDock::_start_igniter(const Array &p_missing) {
	if (scheduled_agents.has(active_agent) || sub_agents.has(active_agent) || !gonggong_recovered_result.is_empty()) {
		return false; // Unattended, child and recovery turns keep the fail-closed rejection.
	}
	const String outcome = last_user_content(messages);
	if (outcome.strip_edges().is_empty() || p_missing.is_empty()) {
		return false;
	}
	_cancel_igniter(String());
	igniter_outcome = outcome;
	igniter_missing = p_missing;
	igniter_fields.clear();
	igniter_state = "components";
	set_meta("gonggong_status", "igniter");
	_igniter_prompt();
	_set_busy(false);
	return true;
}

void AIChatDock::_igniter_prompt() {
	String text;
	if (igniter_state == "components") {
		String names;
		for (int i = 0; i < igniter_missing.size(); i++) {
			if (i > 0) {
				names += U"、";
			}
			names += String(U"`") + String(igniter_missing[i]) + U"`";
		}
		text = String(U"检测到本地环境配置缺失：") + names + U"。为避免把配置问题误判为系统阻塞，已进入本地配置点火器（编辑器本地处理，不调用模型或工具）。\n\n"
															 U"- 回复要部署的组件（如 `node git`），或回复 `全部`\n"
															 U"- 放弃：回复 `取消`\n\n"
															 U"点火器不会自动安装；部署只会把你已安装或提供的可执行路径固定到所选位置，并记录回退入口。";
	} else if (igniter_state == "python_path") {
		text = U"Python 未配置，点火器无法通过桥接部署它。请回复 Python 可执行文件的绝对路径（例如 `/usr/bin/python3` 或 `/opt/homebrew/bin/python3`），编辑器会把它保存为 GongGong 的 Python 路径；回复 `取消` 放弃。";
	} else if (igniter_state == "location") {
		text = U"选择安装位置：\n1. `project-local`（项目本地，默认）\n2. `user-level`（用户级）\n\n回复 `1`、`2` 或 `默认`；回复 `取消` 放弃。";
	} else if (igniter_state == "confirm") {
		String components;
		for (const Variant &component : Array(igniter_fields.get("components", Array()))) {
			if (!components.is_empty()) {
				components += U"、";
			}
			components += String(U"`") + String(component) + U"`";
		}
		text = vformat(U"将部署：%s\n安装位置：%s\n\n回复 `确认` 授权执行；回复 `取消` 放弃。", components, String(igniter_fields.get("location", "project-local")));
	}
	if (!text.is_empty()) {
		_append(TTR("Editor"), text);
	}
}

void AIChatDock::_igniter_reply(const String &p_text) {
	if (AIChatIssueGuide::is_cancel(p_text)) {
		_cancel_igniter(U"已退出本地配置点火器。原消息仍保留；修复环境后再发送即可继续。");
		return;
	}
	if (igniter_pid >= 0) {
		_append(TTR("Editor"), U"点火器正在处理上一步，请稍候；回复 `取消` 可放弃。");
		return;
	}
	const String text = p_text.strip_edges();
	if (igniter_state == "components") {
		Array selected;
		if (text == U"全部" || text == "all") {
			selected = igniter_missing;
		} else {
			for (const String &token : text.split(" ")) {
				const String name = token.strip_edges();
				if (!name.is_empty() && igniter_missing.has(name) && !selected.has(name)) {
					selected.push_back(name);
				}
			}
		}
		if (selected.is_empty()) {
			_append(TTR("Error"), U"未识别到可部署的组件，请从缺失项中选择。");
			_igniter_prompt();
			return;
		}
		igniter_fields["components"] = selected;
		if (selected.has("python") && String(EDITOR_GET("gonggong/python")).strip_edges().is_empty()) {
			igniter_state = "python_path";
		} else {
			igniter_state = "location";
		}
	} else if (igniter_state == "python_path") {
		if (FileAccess::exists(text)) {
			EditorSettings::get_singleton()->set("gonggong/python", text);
			EditorSettings::get_singleton()->save();
			Array selected = igniter_fields["components"];
			selected.erase("python");
			if (selected.is_empty()) {
				_append(TTR("Editor"), U"Python 已配置，正在用原消息重新进行 GongGong 入口校验…");
				_cancel_igniter(String(), String());
				_igniter_resume();
				return;
			}
			igniter_fields["components"] = selected;
			igniter_state = "location";
		} else {
			_append(TTR("Error"), U"路径不可用，请提供有效的 Python 可执行文件绝对路径。");
		}
	} else if (igniter_state == "location") {
		String location = "project-local";
		if (text == "2" || text == "user-level" || text == U"用户级") {
			location = "user-level";
		}
		igniter_fields["location"] = location;
		igniter_state = "confirm";
	} else if (igniter_state == "confirm") {
		if (AIChatIssueGuide::is_confirm(text)) {
			Dictionary deploy;
			deploy["components"] = igniter_fields["components"];
			deploy["location"] = igniter_fields["location"];
			_igniter_run("environment-deploy", deploy);
			return;
		}
	}
	_igniter_prompt();
}

void AIChatDock::_igniter_run(const String &p_action, const Dictionary &p_request) {
	igniter_state = p_action == "environment-deploy" ? "deploying" : "checking";
	const String root = _workflow_root();
	const String python = EDITOR_GET("gonggong/python");
	const String bridge = root.path_join("tools/gonggong_bridge.py");
	if (root.is_empty() || python.is_empty() || !FileAccess::exists(bridge)) {
		_append(TTR("Error"), U"无法启动点火器：工作区或 Python 未配置，请在 GongGong 页设置后再试。");
		_cancel_igniter(String(), "error");
		return;
	}
	const String prefix = EditorPaths::get_singleton()->get_cache_dir().path_join("gonggong-igniter-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()));
	igniter_input_path = prefix + ".request.json";
	igniter_output_path = prefix + ".result.json";
	Ref<FileAccess> file = FileAccess::open(igniter_input_path, FileAccess::WRITE);
	if (file.is_null()) {
		_append(TTR("Error"), U"无法保存点火器请求。");
		_cancel_igniter(String(), "error");
		return;
	}
	file->store_string(JSON::stringify(p_request));
	file.unref();
	List<String> args;
	for (const String &argument : { bridge, p_action, String("--workspace"), root, String("--tenant"), String(EDITOR_GET("gonggong/tenant")), String("--request"), igniter_input_path, String("--out"), igniter_output_path }) {
		args.push_back(argument);
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(python, args, &pid) != OK) {
		_clear_igniter_files();
		_append(TTR("Error"), U"无法启动点火器，请检查 Python 路径。");
		_cancel_igniter(String(), "error");
		return;
	}
	igniter_pid = pid;
	igniter_action = p_action;
	igniter_run_generation = igniter_generation;
	if (!igniter_timer) {
		igniter_timer = memnew(Timer);
		igniter_timer->set_wait_time(0.1);
		igniter_timer->connect("timeout", callable_mp(this, &AIChatDock::_poll_igniter));
		add_child(igniter_timer);
	}
	igniter_timer->start();
	_append(TTR("Editor"), p_action == "environment-deploy" ? String(U"正在执行本地环境部署…") : String(U"正在重新检测本地环境…"));
}

void AIChatDock::_poll_igniter() {
	if (OS::get_singleton()->is_process_running(igniter_pid)) {
		return;
	}
	igniter_timer->stop();
	igniter_pid = -1;
	Variant parsed;
	if (FileAccess::exists(igniter_output_path)) {
		parsed = JSON::parse_string(FileAccess::get_file_as_string(igniter_output_path));
	}
	_clear_igniter_files();
	if (igniter_run_generation != igniter_generation || igniter_state.is_empty()) {
		return; // A cancelled igniter never applies a late result.
	}
	Dictionary result;
	if (parsed.get_type() == Variant::DICTIONARY) {
		result = parsed;
	}
	const bool ok = result.get("ok", false).get_type() == Variant::BOOL && bool(result.get("ok", false));
	const String error = result.get("error", U"点火器没有返回有效结果。");
	if (igniter_action == "environment-deploy") {
		if (!ok) {
			igniter_state = "components";
			_append(TTR("Error"), String(U"本地环境部署失败：") + error);
			_igniter_prompt();
			return;
		}
		_igniter_run("environment-check", Dictionary());
		return;
	}
	if (igniter_action == "environment-check") {
		const Array missing = result.get("environment_missing", Array());
		if (!ok || missing.size() > 0) {
			igniter_missing = missing;
			igniter_state = "components";
			_append(TTR("Error"), U"部署后仍检测到环境缺失，请重新选择或检查可执行路径。");
			_igniter_prompt();
			return;
		}
		_append(TTR("Editor"), U"本地环境已就绪，正在用原消息重新进行 GongGong 入口校验…");
		_cancel_igniter(String(), String());
		_igniter_resume();
		return;
	}
	_cancel_igniter(String());
}

void AIChatDock::_clear_igniter_files() {
	for (const String &path : { igniter_input_path, igniter_output_path }) {
		if (!path.is_empty() && FileAccess::exists(path)) {
			DirAccess::remove_absolute(path);
		}
	}
	igniter_input_path = String();
	igniter_output_path = String();
}

void AIChatDock::_cancel_igniter(const String &p_notice, const String &p_phase) {
	if (igniter_for_intake && !p_phase.is_empty()) {
		_emit_daqian_requirement_phase(p_phase);
	}
	igniter_for_intake = false;
	const bool active = !igniter_state.is_empty() || igniter_pid >= 0;
	igniter_generation++;
	if (igniter_pid >= 0) {
		if (OS::get_singleton()->is_process_running(igniter_pid)) {
			OS::get_singleton()->kill(igniter_pid);
		}
		igniter_pid = -1;
	}
	if (igniter_timer) {
		igniter_timer->stop();
	}
	_clear_igniter_files();
	igniter_state = String();
	igniter_outcome = String();
	igniter_missing.clear();
	igniter_fields.clear();
	if (!active) {
		return;
	}
	set_meta("gonggong_status", "igniter_cancelled");
	if (!p_notice.is_empty()) {
		_append(TTR("Editor"), p_notice);
	}
}

void AIChatDock::_igniter_resume() {
	if (busy) {
		return;
	}
	if (last_user_content(messages).strip_edges().is_empty()) {
		_cancel_igniter(U"环境已部署，但原消息已不在当前会话中，请重新发送。");
		return;
	}
	// Same paused turn: the original user message is still the last entry in `messages`.
	_begin_reply();
	turn_completed = false;
	tool_rounds = 0;
	turn_model_requests = 0;
	session_generation++;
	_set_busy(true);
	_request_completion();
}
