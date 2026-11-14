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
	if (busy || process_id >= 0 || candidate_pid >= 0 || engine_build_pid >= 0 || engine_restart_requested || engine_restart_armed || !delivery_retry_route.is_empty()) {
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
	return refChatController->GetDeliveryExecution().PendingRetry(GetDeliveryScope());
}

Dictionary AIChatDock::_run_delivery_retry(const Dictionary &p_args) {
	Dictionary mapScope = GetDeliveryScope();
	mapScope["retry_blocked_reason"] = _delivery_retry_blocked_reason();
	Dictionary result = refChatController->GetDeliveryExecution().PrepareRetry(p_args, mapScope);
	if (!bool(result.get("ok", false))) {
		return result;
	}
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
