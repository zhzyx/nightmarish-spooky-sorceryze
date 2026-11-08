/**************************************************************************/
/*  ai_chat_delivery_retry.cpp                                            */
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
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/ai_chat_editor_control.h"
#include "scene/gui/check_box.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/text_edit.h"

String AIChatDock::_delivery_retry_blocked_reason() const {
	if (!input || !allow_tools || !auto_execute_commands || !consultation_only || !allow_tools->is_pressed() || !auto_execute_commands->is_pressed() || consultation_only->is_pressed()) {
		return "permission_denied";
	}
	if (sub_agents.has(active_agent) || scheduled_agents.has(active_agent)) {
		return "parent_session_required";
	}
	if (busy || process_id >= 0 || candidate_pid >= 0 || models_loading || engine_build_pid >= 0 || engine_restart_requested || engine_restart_armed || !delivery_retry_route.is_empty()) {
		return "editor_busy";
	}
	if (history_restoring || !history_writable || snapshot_restoring || snapshot_transaction_failed || !gonggong_recovered_result.is_empty()) {
		return "snapshot_unavailable";
	}
	if (!pending_external_editor_message.is_empty() || !issue_guide_state.is_empty() || !igniter_state.is_empty() || daqian_chat_host.is_valid() || (agent_close_confirmation && agent_close_confirmation->is_visible()) || confirmation->is_visible() || engine_approval->is_visible()) {
		return "host_action_pending";
	}
	if (!input->get_text().is_empty() || input->has_ime_text() || !draft_images.is_empty()) {
		return "draft_not_empty";
	}
	if (conversation_id.is_empty() || snapshot_id.is_empty() || delivery_retry_instance.is_empty() || !snapshot_state.has("engine_candidate")) {
		return "known_work_order_owner_required";
	}
	String error;
	if (!_validate_engine_candidate(error)) {
		return "known_work_order_owner_required";
	}
	if (!delivery_receipt.is_empty() && (delivery_receipt.get("completion_verified", Variant()).get_type() != Variant::BOOL || !bool(delivery_receipt["completion_verified"]) || delivery_receipt.get("stage", "") != "activation_pending" || bool(delivery_receipt.get("ok", true)))) {
		return "terminal_state_requires_readback";
	}
	const Dictionary pending = _pending_delivery_retry();
	return bool(pending.get("ok", false)) ? String() : String(pending.get("error", "pending_delivery_unavailable"));
}

Dictionary AIChatDock::_pending_delivery_retry() const {
	Dictionary result;
	result["ok"] = false;
	const Dictionary binding = snapshot_state.get("engine_candidate", Dictionary());
	const String folder = String(binding.get("common_dir", "")).path_join("gonggong-delivery-finalization");
	const Ref<DirAccess> directory = DirAccess::open(folder);
	if (directory.is_null()) {
		result["error"] = "pending_delivery_journal_unavailable";
		return result;
	}
	const PackedStringArray files = directory->get_files();
	if (files.size() > 1024) {
		result["error"] = "pending_delivery_ambiguous";
		return result;
	}
	int matches = 0;
	for (const String &name : files) {
		if (!name.ends_with(".json")) {
			continue;
		}
		const String path = folder.path_join(name);
		Ref<FileAccess> file = FileAccess::open(path, FileAccess::READ);
		if (directory->is_link(name) || file.is_null() || file->get_length() > 256 * 1024) {
			result["error"] = "pending_delivery_journal_invalid";
			return result;
		}
		const Variant parsed = JSON::parse_string(file->get_as_text());
		file.unref();
		if (parsed.get_type() != Variant::DICTIONARY) {
			result["error"] = "pending_delivery_journal_invalid";
			return result;
		}
		const Dictionary saved = parsed;
		const Dictionary scope = saved.get("scope", Dictionary());
		if (scope.get("owner", "") != conversation_id || scope.get("source_root", "") != _candidate_root() || scope.get("issue", Variant()) != binding.get("issue", Variant()) || scope.get("request_id", "") != binding.get("request_id", "")) {
			continue;
		}
		const Dictionary receipt = saved.get("last_receipt", Dictionary());
		if (receipt.get("snapshot_id", "") != snapshot_id) {
			continue;
		}
		if (receipt.get("completion_verified", Variant()).get_type() != Variant::BOOL || !bool(receipt["completion_verified"]) || receipt.get("ok", Variant()).get_type() != Variant::BOOL || bool(receipt["ok"]) || receipt.get("stage", "") != "activation_pending") {
			result["error"] = "terminal_state_requires_readback";
			return result;
		}
		const Dictionary facts = receipt.get("host_facts", Dictionary());
		const String prefix = "https://github.com/" + String(binding.get("repository", "")) + "/pull/";
		const String url = facts.get("pull_request", "");
		const String number = url.trim_prefix(prefix);
		const String candidate = scope.get("candidate", ""), signed_commit = scope.get("signed_commit", "");
		if (!url.begins_with(prefix) || !number.is_valid_int() || number.to_int() <= 0 || number.to_int() > INT_MAX || number != itos(number.to_int()) || candidate.length() != 40 || !candidate.is_valid_hex_number(false) || signed_commit.length() != 40 || !signed_commit.is_valid_hex_number(false)) {
			result["error"] = "pending_delivery_journal_invalid";
			return result;
		}
		matches++;
		result["pr"] = number.to_int();
		result["expected_candidate"] = candidate;
		result["expected_signed_commit"] = signed_commit;
		result["original_journal_sha256"] = FileAccess::get_sha256(path);
	}
	result["ok"] = matches == 1;
	if (matches != 1) {
		result["error"] = matches == 0 ? "pending_delivery_not_found" : "pending_delivery_ambiguous";
	}
	return result;
}

Dictionary AIChatDock::_run_delivery_retry(const Dictionary &p_args) {
	Dictionary result;
	result["ok"] = false;
	String error = _delivery_retry_blocked_reason();
	if (!error.is_empty()) {
		result["error"] = error;
		return result;
	}
	const Dictionary selected = _pending_delivery_retry();
	if (!bool(selected.get("ok", false))) {
		return selected;
	}
	uint8_t nonce[16];
	if (CryptoCore::generate_random(nonce, sizeof(nonce)) != OK) {
		result["error"] = "delivery_retry_nonce_unavailable";
		return result;
	}
	const Dictionary binding = snapshot_state["engine_candidate"];
	Dictionary recorded = JSON::parse_string(FileAccess::get_file_as_string(binding.get("binding_path", "")));
	// Preserve the recorded integer identities independently of Variant JSON floats.
	recorded["version"] = int64_t(recorded.get("version", 0));
	recorded["issue"] = int64_t(recorded.get("issue", 0));
	recorded["binding_path"] = binding.get("binding_path", "");
	_clear_delivery_files();
	delivery_receipt.clear();
	pending_delivery_request.clear();
	pending_delivery_request["schema_version"] = 1;
	pending_delivery_request["kind"] = "native_delivery_retry";
	pending_delivery_request["engine_pid"] = int64_t(OS::get_singleton()->get_process_id());
	pending_delivery_request["host_instance_id"] = delivery_retry_instance;
	pending_delivery_request["owner"] = conversation_id;
	pending_delivery_request["snapshot_id"] = snapshot_id;
	pending_delivery_request["generation"] = int64_t(session_generation);
	pending_delivery_request["nonce"] = String::hex_encode_buffer(nonce, sizeof(nonce));
	pending_delivery_request["source_root"] = _candidate_root();
	pending_delivery_request["binding"] = recorded;
	for (const String &key : { String("pr"), String("expected_candidate"), String("expected_signed_commit"), String("original_journal_sha256") }) {
		pending_delivery_request[key] = selected[key];
	}
	pending_delivery_request["host_action_request_id"] = p_args["host_action_request_id"];
	delivery_retry_route["request_id"] = p_args["host_action_request_id"];
	pending_action = "complete_delivery";
	process_timeout_seconds = 600;
	queue_paused = true;
	consultation_turn = false;
	turn_completed = false;
	_set_busy(true);
	// The route's durable started receipt is stored before this deferred effect.
	callable_mp(this, &AIChatDock::_begin_delivery_retry).call_deferred();
	result["ok"] = true;
	result["delivery_retry_started"] = true;
	result["business_completed"] = false;
	return result;
}

void AIChatDock::_begin_delivery_retry() {
	if (!delivery_retry_route.is_empty() && busy && pending_action == "complete_delivery") {
		if (!allow_tools->is_pressed() || !auto_execute_commands->is_pressed() || consultation_only->is_pressed() || sub_agents.has(active_agent) || scheduled_agents.has(active_agent)) {
			_finish_tool("Error: Terminal retry permission changed before execution.");
			return;
		}
		_start_process();
	}
}

void AIChatDock::_finish_delivery_retry(const String &p_process_result) {
	pending_action = String();
	const Variant parsed = JSON::parse_string(p_process_result);
	const Dictionary process = parsed.get_type() == Variant::DICTIONARY ? Dictionary(parsed) : Dictionary();
	const Dictionary actual = process.get("delivery_finalization", Dictionary());
	Dictionary receipt;
	receipt["ok"] = !actual.is_empty() && bool(process.get("ok", false)) && bool(actual.get("ok", false));
	receipt["completion_verified"] = actual.get("completion_verified", false);
	receipt["business_completed"] = receipt["ok"];
	receipt["delivery_stage"] = actual.get("stage", "unknown");
	receipt["worker_receipt_sha256"] = process.get("delivery_worker_result_sha256", "");
	if (!bool(receipt["ok"])) {
		receipt["error"] = "delivery_retry_pending_or_unknown";
	}
	const bool persisted = _get_editor_control()->finish_delivery_retry_route(delivery_retry_route, receipt);
	if (actual.is_empty() || !persisted) {
		delivery_receipt.clear();
		delivery_receipt["ok"] = false;
		delivery_receipt["completion_verified"] = false;
		delivery_receipt["error"] = persisted ? "delivery_retry_result_unknown" : "delivery_retry_receipt_not_persisted";
	}
	_finish_delivery();
	delivery_retry_route.clear();
}
