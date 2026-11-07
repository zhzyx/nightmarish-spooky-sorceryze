/**************************************************************************/
/*  ai_chat_delivery.cpp                                                  */
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

#include "core/crypto/crypto_core.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/docks/ai_chat_delivery_receipt.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/gonggong_runtime_config.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/check_box.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/text_edit.h"

void AIChatDock::_clear_delivery_files() {
	for (const String &path : { delivery_request_path, delivery_result_path }) {
		if (!path.is_empty() && FileAccess::exists(path)) {
			DirAccess::remove_absolute(path);
		}
	}
	delivery_request_path = String();
	delivery_result_path = String();
}

void AIChatDock::_run_delivery_tool(const Dictionary &p_arguments) {
	const Variant pr = p_arguments.get("pr", Variant());
	const Variant checklist = p_arguments.get("acceptance_items", Variant());
	const String candidate = p_arguments.get("candidate", "");
	const String signed_commit = p_arguments.get("signed_commit", "");
	if (consultation_turn || consultation_only->is_pressed() || sub_agents.has(active_agent) || scheduled_agents.has(active_agent) || !snapshot_state.has("engine_candidate")) {
		_finish_tool("Error: Only the current authorized parent may complete its host-bound work order.");
		return;
	}
	if ((pr.get_type() != Variant::INT && pr.get_type() != Variant::FLOAT) || !Math::is_finite(double(pr)) || double(pr) < 1 || double(pr) > INT_MAX || double(pr) != Math::floor(double(pr)) || checklist.get_type() != Variant::ARRAY || Array(checklist).is_empty() || Array(checklist).size() > 64 || JSON::stringify(checklist).utf8().length() > 48 * 1024 || candidate.length() != 40 || !candidate.is_valid_hex_number(false) || signed_commit.length() != 40 || !signed_commit.is_valid_hex_number(false)) {
		_finish_tool("Error: A positive PR, exact candidate/signed SHAs and a complete bounded acceptance checklist are required.");
		return;
	}
	String error;
	if (!_validate_engine_candidate(error)) {
		_finish_tool("Error: " + error);
		return;
	}
	const Dictionary binding = snapshot_state["engine_candidate"];
	Dictionary selected_binding;
	for (const String &key : { String("version"), String("owner"), String("issue"), String("request_id"), String("source_root"), String("branch"), String("base_sha"), String("common_dir"), String("repository"), String("origin"), String("binding_path") }) {
		selected_binding[key] = binding.get(key, Variant());
	}
	// JSON-parsed numbers are floats in Variant; the worker requires integer identities.
	// Older preparation receipts omit version/origin; use the original journal,
	// which the fixed worker independently checks against the actual repository.
	const Dictionary recorded = JSON::parse_string(FileAccess::get_file_as_string(binding.get("binding_path", "")));
	selected_binding["version"] = int64_t(recorded.get("version", 0));
	selected_binding["origin"] = recorded.get("origin", Variant());
	selected_binding["issue"] = int64_t(binding.get("issue", 0));
	uint8_t bytes[16];
	if (CryptoCore::generate_random(bytes, sizeof(bytes)) != OK) {
		_finish_tool("Error: Cannot create delivery request identity.");
		return;
	}
	_clear_delivery_files();
	pending_delivery_request.clear();
	pending_delivery_request["schema_version"] = 1;
	pending_delivery_request["owner"] = conversation_id;
	pending_delivery_request["snapshot_id"] = snapshot_id;
	pending_delivery_request["generation"] = int64_t(session_generation);
	pending_delivery_request["nonce"] = String::hex_encode_buffer(bytes, sizeof(bytes));
	pending_delivery_request["source_root"] = _candidate_root();
	pending_delivery_request["binding"] = selected_binding;
	pending_delivery_request["pr"] = int64_t(pr);
	pending_delivery_request["expected_candidate"] = candidate;
	pending_delivery_request["expected_signed_commit"] = signed_commit;
	pending_delivery_request["acceptance_items"] = checklist;
	pending_action = "complete_delivery";
	process_timeout_seconds = 600;
	if (auto_execute_commands->is_pressed()) {
		_confirm_action();
	} else {
		confirmation->set_title(TTR("Approve Delivery Completion"));
		preview->set_text(vformat(U"核对 PR #%d、主线与 CI，按执行 Agent 的完整验收声明关闭当前工单 #%d，并核验启动入口。未完成或未知结果会暂停后续执行。", int(pr), int(binding["issue"])));
		_show_confirmation();
	}
}

bool AIChatDock::_delivery_process_arguments(String &r_executable, List<String> &r_arguments, const Dictionary &p_runtime) {
	String error;
	if (pending_delivery_request.is_empty() || !busy || pending_delivery_request.get("owner", "") != conversation_id || pending_delivery_request.get("snapshot_id", "") != snapshot_id || int64_t(pending_delivery_request["generation"]) != int64_t(session_generation) || pending_delivery_request.get("source_root", "") != _candidate_root() || !_validate_engine_candidate(error)) {
		_finish_tool("Error: Delivery owner, generation or candidate changed before execution. " + error);
		return false;
	}
	r_executable = GongGongRuntimeConfig::path(p_runtime, "workflow_python");
	const String worker = _engine_root().path_join("tools/editor_delivery_finalize.py");
	if (r_executable.is_empty() || !FileAccess::exists(r_executable) || !FileAccess::exists(worker)) {
		_finish_tool("Error: The installed delivery worker or workflow Python is missing.");
		return false;
	}
	const String prefix = EditorPaths::get_singleton()->get_cache_dir().path_join("delivery-finalize-" + itos(OS::get_singleton()->get_process_id()) + "-" + String(pending_delivery_request["nonce"]));
	delivery_request_path = prefix + ".request.json";
	delivery_result_path = prefix + ".result.json";
	Ref<FileAccess> file = FileAccess::open(delivery_request_path, FileAccess::WRITE);
	if (file.is_null() || !file->store_string(JSON::stringify(pending_delivery_request))) {
		_finish_tool("Error: Cannot persist the delivery request.");
		_clear_delivery_files();
		return false;
	}
	file->flush();
	if (file->get_error() != OK) {
		_finish_tool("Error: Cannot flush the delivery request.");
		_clear_delivery_files();
		return false;
	}
	file.unref();
	for (const String &argument : { String("-I"), worker, String("--source-root"), _candidate_root(), String("--request"), delivery_request_path, String("--out"), delivery_result_path }) {
		r_arguments.push_back(argument);
	}
	return true;
}

void AIChatDock::_capture_delivery_result(Dictionary &r_process_result) {
	r_process_result["ok"] = false;
	if (!busy || pending_delivery_request.is_empty() || pending_delivery_request.get("owner", "") != conversation_id || pending_delivery_request.get("snapshot_id", "") != snapshot_id || int64_t(pending_delivery_request["generation"]) != int64_t(session_generation)) {
		_clear_delivery_files();
		return;
	}
	Ref<FileAccess> file = FileAccess::open(delivery_result_path, FileAccess::READ);
	const int64_t bytes = file.is_valid() ? int64_t(file->get_length()) : -1;
	const Variant parsed = file.is_valid() && bytes <= 256 * 1024 ? JSON::parse_string(file->get_as_text()) : Variant();
	file.unref();
	Dictionary result = parsed.get_type() == Variant::DICTIONARY ? Dictionary(parsed) : Dictionary();
	const Dictionary guard = r_process_result.get("provenance_guard", Dictionary());
	const bool process_ok = int(r_process_result.get("exit_code", -1)) == 0 && !bool(r_process_result.get("timed_out", true)) && guard.get("ok", Variant()).get_type() == Variant::BOOL && bool(guard["ok"]);
	const bool matched = AIChatDeliveryReceipt::matches(result, pending_delivery_request);
	const bool completed = matched && process_ok && AIChatDeliveryReceipt::completed(result, pending_delivery_request);
	Dictionary diagnostic;
	if (!completed || result.get("ok", Variant()).get_type() != Variant::BOOL || !bool(result["ok"])) {
		if (bytes >= 0) {
			diagnostic["bytes"] = bytes;
			diagnostic["sha256"] = bytes <= 256 * 1024 ? FileAccess::get_sha256(delivery_result_path) : String();
			const String retained = delivery_result_path + ".retained.json";
			if (!FileAccess::exists(retained) && DirAccess::rename_absolute(delivery_result_path, retained) == OK) {
				diagnostic["path"] = retained;
				delivery_result_path = String();
			}
		}
	}
	_clear_delivery_files();
	if (matched && !diagnostic.is_empty()) {
		result["private_worker_diagnostic"] = diagnostic;
	}
	if (matched && !bool(result["completion_verified"]) && !bool(result["mutations_may_have_started"]) && result.get("stage", "") == "validation" && guard.get("ok", Variant()).get_type() == Variant::BOOL && bool(guard["ok"])) {
		r_process_result["delivery_finalization"] = result;
		return; // A pre-mutation rejection can still be corrected in active intake.
	}
	if (!completed) {
		Dictionary unknown;
		unknown["ok"] = false;
		unknown["completion_verified"] = false;
		unknown["error"] = "delivery_readback_unknown; reconcile existing state before any retry";
		unknown["private_worker_diagnostic"] = diagnostic;
		if (matched) {
			unknown["worker_stage"] = _redact(String(result.get("stage", "unknown"))).left(128);
			unknown["worker_error"] = _redact(String(result.get("error", ""))).left(1000);
			unknown["private_diagnostic_ref"] = String(result.get("private_diagnostic_ref", ""));
		}
		result = unknown;
	}
	delivery_receipt = result.duplicate(true);
	queue_paused = true; // A receipt flush failure must not dispatch queued work.
	r_process_result["ok"] = completed && result.get("ok", Variant()).get_type() == Variant::BOOL && bool(result["ok"]);
	r_process_result["delivery_finalization"] = result;
}

void AIChatDock::_finish_delivery() {
	// This path is reachable only after the fixed worker and tool-result flush.
	// Neither arbitrary command output nor restored history sets this dictionary.
	if (pending_delivery_request.get("owner", "") != conversation_id || pending_delivery_request.get("snapshot_id", "") != snapshot_id || int64_t(pending_delivery_request.get("generation", -1)) != int64_t(session_generation)) {
		delivery_receipt.clear();
		pending_delivery_request.clear();
		_request_completion();
		return;
	}
	queue_paused = true;
	_cancel_design_batch(active_agent);
	tool_calls.clear();
	_clear_resume();
	_cancel_cli();
	String text;
	const bool verified = delivery_receipt.get("completion_verified", Variant()).get_type() == Variant::BOOL && bool(delivery_receipt["completion_verified"]);
	turn_completed = verified && delivery_receipt.get("ok", Variant()).get_type() == Variant::BOOL && bool(delivery_receipt["ok"]);
	if (verified) {
		const Dictionary facts = delivery_receipt["host_facts"];
		text = vformat(U"交付已回读：PR #%d 已合入主线 %s，工单 #%d 已以 completed 关闭。业务验收依据为执行 Agent 提交的完整声明与证据。", int(pending_delivery_request["pr"]), String(facts["current_main"]).left(12), int(facts["issue"]));
		const Dictionary activation = delivery_receipt.get("engine_launch_activation", Dictionary());
		if (activation.get("state", "") == "activated") {
			text += U"启动入口已核验更新。";
		} else if (activation.get("state", "") == "not_applicable") {
			text += U"本次没有适用的启动入口更新。";
		} else {
			text += String(U"启动入口更新仍待核实：") + _redact(String(activation.get("error", activation.get("state", "unknown")))) + U"。保留当前状态，重试前先回读。";
		}
	} else {
		text = U"交付收尾未得到完整回执，已暂停后续工具和队列。部分操作可能已完成；重试前须先回读现有状态。";
	}
	Dictionary message;
	message["role"] = "assistant";
	message["content"] = text;
	messages.push_back(message);
	_append(U"编辑器", text);
	set_meta("gonggong_status", turn_completed ? "delivery_completed" : "delivery_pending");
	_set_busy(false);
	_queue_history_save();
	_save_history();
}
