/**************************************************************************/
/*  ai_chat_olympus.cpp                                                  */
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

#include "ai_chat_dock.h"
#include "ai_chat_resume.h"

#include "core/config/project_settings.h"
#include "core/io/dir_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/check_box.h"
#include "scene/main/timer.h"

bool AIChatDock::_record_olympus(const String &p_kind, const String &p_phase, const String &p_status, bool p_flush) {
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
	if (!p_flush) {
		return true;
	}
	List<String> arguments;
	for (const String &arg : { _engine_root().path_join("tools/olympus_bridge.py"), String("flush"), String("--workspace"), olympus_report_root }) {
		arguments.push_back(arg);
	}
	String output;
	int exit_code = -1;
	const Error error = OS::get_singleton()->execute(olympus_report_python, arguments, &output, &exit_code, true);
	if (error != OK || exit_code != 0) {
		set_meta("olympus_reporting", "pending_retry");
		_append(TTR("Error"), U"Olympus 文件回执失败；事件保留在 outbox，下一次发送会先重试，尚未记为已交付。");
		return false;
	}
	set_meta("olympus_reporting", "recorded_file");
	return true;
}

void AIChatDock::_poll_olympus_receipt() {
	if (OS::get_singleton()->is_process_running(olympus_receipt_pid)) {
		return;
	}
	olympus_receipt_timer->stop();
	olympus_receipt_pid = -1;
	Variant parsed = JSON::parse_string(FileAccess::get_file_as_string(olympus_receipt_path));
	DirAccess::remove_absolute(olympus_receipt_path);
	Dictionary result;
	if (parsed.get_type() == Variant::DICTIONARY) {
		result = parsed;
	}
	const bool ok = result.get("ok", false).get_type() == Variant::BOOL && bool(result.get("ok", false));
	if (olympus_receipt_generation == session_generation) {
		set_meta("olympus_reporting", ok ? "recorded_file" : "pending_retry");
	}
	if (!ok) {
		_append(TTR("Error"), U"Olympus 结束事件暂未获得文件回执，已保留队列，下次发送前重试。");
	}
}

void AIChatDock::_end_olympus(const String &p_status) {
	if (olympus_reporting.is_empty()) {
		return;
	}
	for (const Variant &phase : olympus_running_steps.keys()) {
		_record_olympus("step", phase, p_status == "completed" ? "succeeded" : p_status, false);
	}
	_record_olympus("coverage", "native_chat_messages_and_tools", "metadata_only_usage_unavailable", false);
	_record_olympus("request_end", "chat", p_status, false);
	olympus_reporting.clear();
	olympus_running_steps.clear();
	// Execution has already stopped. Terminal delivery must never hold up Stop.
	if (olympus_receipt_pid >= 0) {
		return; // Retained envelopes are retried by the next context preflight.
	}
	olympus_receipt_path = EditorPaths::get_singleton()->get_cache_dir().path_join("olympus-receipt-" + itos(OS::get_singleton()->get_process_id()) + ".json");
	List<String> arguments;
	for (const String &arg : { _engine_root().path_join("tools/olympus_bridge.py"), String("flush"), String("--workspace"), olympus_report_root, String("--out"), olympus_receipt_path }) {
		arguments.push_back(arg);
	}
	ProcessID pid = 0;
	if (OS::get_singleton()->create_process(olympus_report_python, arguments, &pid) != OK) {
		set_meta("olympus_reporting", "pending_retry");
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
	const String bridge = _engine_root().path_join("tools/olympus_bridge.py");
	if (root.is_empty() || python.is_empty() || !FileAccess::exists(bridge)) {
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
	Dictionary input;
	input["request_id"] = "godot-" + snapshot_id;
	input["outcome"] = outcome;
	input["authority_ref"] = "godot-editor:user-chat:" + conversation_id;
	input["project"] = ProjectSettings::get_singleton()->get_resource_path();
	input["tools_enabled"] = allow_tools->is_pressed();
	input["file_changes_require_approval"] = !auto_apply_file_changes->is_pressed();
	input["execution_requires_approval"] = !auto_execute_commands->is_pressed();
	const String prefix = EditorPaths::get_singleton()->get_cache_dir().path_join("olympus-chat-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()));
	olympus_input_path = prefix + ".request.json";
	olympus_output_path = prefix + ".result.json";
	Ref<FileAccess> file = FileAccess::open(olympus_input_path, FileAccess::WRITE);
	if (file.is_null()) {
		_append(TTR("Error"), U"无法保存 Olympus 校验请求，未发送聊天。");
		_set_busy(false);
		return;
	}
	file->store_string(JSON::stringify(input));
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
		set_meta("olympus_status", "blocked");
		_append(TTR("Error"), String(U"Olympus 阻止本次发送：") + String(result.get("error", U"校验进程没有返回有效上下文。")));
		_set_busy(false);
		return;
	}
	olympus_context = result["context"];
	set_meta("olympus_status", "context_ready");
	if (!olympus_recovered_result.is_empty()) {
		if (!_record_olympus("step", "restart_result_recovery", "running")) {
			_set_busy(false);
			return;
		}
		const int previous_tool = tool_index;
		_finish_tool(olympus_recovered_result);
		if (tool_index == previous_tool) {
			return; // Durable restart journal is still available for a later attempt.
		}
		_record_olympus("step", "restart_result_recovery", "result_restored");
		olympus_recovered_result = String();
		AIChatResume::clear_journal();
		AIChatResume::clear_report();
		_queue_history_save();
		if (!olympus_recovery_can_send) {
			_end_olympus("paused");
			_set_busy(false);
		}
		return;
	}
	olympus_resume = true;
	_request_completion();
}
