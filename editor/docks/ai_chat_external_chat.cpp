/**************************************************************************/
/*  ai_chat_external_chat.cpp                                             */
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

#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/ai_chat_editor_control.h"
#include "editor/docks/ai_chat_issue_guide.h"
#include "scene/gui/check_box.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/text_edit.h"

namespace {
bool expected_context_matches(const Dictionary &p_expected, const Dictionary &p_current) {
	if (p_expected.size() != p_current.size()) {
		return false;
	}
	for (const Variant &key : p_current.keys()) {
		if (!p_expected.has(key)) {
			return false;
		}
		const Variant current = p_current[key];
		const Variant expected = p_expected[key];
		if (current.get_type() == Variant::INT) {
			// JSON numbers arrive as FLOAT; retain exact integral state and
			// reject booleans, strings, fractions and unsafe magnitudes.
			if (!expected.is_num() || !Math::is_finite(double(expected)) || Math::floor(double(expected)) != double(expected) || Math::abs(double(current)) > 9007199254740991.0 || Math::abs(double(expected)) > 9007199254740991.0 || double(expected) != double(current)) {
				return false;
			}
		} else if (expected != current) {
			return false;
		}
	}
	return true;
}
} // namespace

Dictionary AIChatDock::_chat_instruction_context() const {
	Dictionary context;
	const Dictionary candidate = GetAiSession().mapSnapshot.get("engine_candidate", Dictionary());
	context["version"] = 1;
	context["engine_pid"] = OS::get_singleton()->get_process_id();
	context["host_instance_id"] = delivery_retry_instance;
	context["conversation_id"] = GetAiSession().strConversation;
	context["generation"] = int64_t(GetAiSessionGeneration());
	context["snapshot_id"] = GetAiSession().strSnapshot;
	context["owner"] = candidate.get("owner", "");
	context["issue_number"] = _work_order_binding("issue_number").to_int();
	context["work_order_request_id"] = _work_order_binding("request_id");
	context["active_agent"] = active_agent;
	context["top_level_parent"] = !sub_agents.has(active_agent) && !scheduled_agents.has(active_agent);
	context["draft_hash"] = input ? input->get_text().sha256_text() : String();
	context["draft_empty"] = input && input->get_text().is_empty();
	context["ime_composing"] = input && input->has_ime_text();
	context["draft_images_hash"] = JSON::stringify(GetAiSession().arrDraftImages).sha256_text();
	context["queue_hash"] = JSON::stringify(GetAiSession().arrQueuedMessages).sha256_text();
	context["queue_count"] = GetAiSession().arrQueuedMessages.size();
	context["queue_paused"] = GetAiSession().bQueuePaused;
	context["busy"] = IsAiBusy();
	context["tools_allowed"] = allow_tools && allow_tools->is_pressed();
	context["automatic_execution"] = auto_execute_commands && auto_execute_commands->is_pressed();
	context["consultation"] = !consultation_only || consultation_only->is_pressed() || (IsAiBusy() && consultation_turn);
	const String blocked = _chat_instruction_blocked_reason();
	context["instruction_available"] = blocked.is_empty();
	context["blocked_reason"] = blocked;
	const String consultation_blocked = _chat_instruction_blocked_reason(true);
	context["consultation_instruction_available"] = consultation_blocked.is_empty();
	context["consultation_blocked_reason"] = consultation_blocked;
	const String retry_blocked = _delivery_retry_blocked_reason();
	context["delivery_retry_available"] = retry_blocked.is_empty();
	context["delivery_retry_blocked_reason"] = retry_blocked;
	return context;
}

String AIChatDock::_chat_instruction_blocked_reason(bool p_force_consultation) const {
	if (!input || !allow_tools || !auto_execute_commands || !consultation_only || !auto_execute_commands->is_pressed()) {
		return "permission_denied";
	}
	const bool consultation = p_force_consultation || consultation_only->is_pressed();
	if (!consultation && (!allow_tools->is_pressed() || (IsAiBusy() && consultation_turn))) {
		return "permission_denied";
	}
	if (sub_agents.has(active_agent) || scheduled_agents.has(active_agent)) {
		return "parent_session_required";
	}
	if (consultation) {
		// A selected consultation is a new read-only turn, never steering or
		// permission to resume an older queued production message.
		if (IsAiBusy()) {
			return "consultation_busy";
		}
		if (GetAiSession().bQueuePaused || !GetAiSession().arrQueuedMessages.is_empty()) {
			return "consultation_queue_pending";
		}
		if (GetAiSession().strConversation.is_empty()) {
			return "chat_input_unavailable";
		}
	} else {
		const Dictionary candidate = GetAiSession().mapSnapshot.get("engine_candidate", Dictionary());
		if (GetAiSession().strConversation.is_empty() || GetAiSession().strSnapshot.is_empty() || String(candidate.get("owner", "")).is_empty() || !AIChatIssueGuide::is_bound(_work_order_binding("issue_number").to_int(), _work_order_binding("request_id"))) {
			return "known_work_order_owner_required";
		}
		String owner_error;
		if (!_validate_engine_candidate(owner_error)) {
			return "known_work_order_owner_required";
		}
	}
	if (history_restoring || !history_writable) {
		return "history_unavailable";
	}
	if (agent_close_confirmation && agent_close_confirmation->is_visible() && pending_close_agent == active_agent) {
		return "parent_close_pending";
	}
	if (snapshot_restoring || snapshot_transaction_failed) {
		return "snapshot_unavailable";
	}
	if (engine_restart_requested || (engine_build_pid >= 0 && !IsAiBusy())) {
		return "engine_update_pending";
	}
	if (!gonggong_recovered_result.is_empty()) {
		return "result_recovery_pending";
	}
	if (!pending_external_editor_message.is_empty()) {
		return "external_confirmation_pending";
	}
	if (!issue_guide_state.is_empty() || !igniter_state.is_empty()) {
		return "work_order_setup_pending";
	}
	if (daqian_chat_host.is_valid()) {
		return "host_chat_mounted";
	}
	if (!delivery_retry_route.is_empty()) {
		return "terminal_retry_in_progress";
	}
	if (!delivery_receipt.is_empty()) {
		return "work_order_complete";
	}
	if (!send_button || send_button->is_disabled()) {
		return "chat_input_unavailable";
	}
	if (!input->get_text().is_empty() || input->has_ime_text()) {
		return "draft_not_empty";
	}
	if (!GetAiSession().arrDraftImages.is_empty()) {
		return "draft_images_present";
	}
	if (GetAiSession().arrQueuedMessages.size() >= 32) {
		return "queue_full";
	}
	return String();
}

Dictionary AIChatDock::_chat_instruction_action(const Dictionary &p_args) {
	if (p_args.get("action", "") == "retry_pending_delivery") {
		const Variant value = p_args.get("value", Variant());
		if (value.get_type() != Variant::DICTIONARY || Dictionary(value).size() != 1 || Dictionary(value).get("expected", Variant()).get_type() != Variant::DICTIONARY || !expected_context_matches(Dictionary(value)["expected"], _chat_instruction_context())) {
			Dictionary rejected;
			rejected["ok"] = false;
			rejected["error"] = "chat_instruction_state_changed";
			return rejected;
		}
		return _run_delivery_retry(p_args);
	}
	Dictionary result;
	result["ok"] = false;
	const Dictionary context = _chat_instruction_context();
	const Variant value = p_args.get("value", Variant());
	if (value.get_type() != Variant::DICTIONARY) {
		result["error"] = "invalid_instruction_value";
		return result;
	}
	const Dictionary instruction = value;
	const bool force_consultation = instruction.has("consultation_only");
	if (instruction.size() != (force_consultation ? 3 : 2) || (force_consultation && (instruction["consultation_only"].get_type() != Variant::BOOL || !bool(instruction["consultation_only"]))) || instruction.get("text", Variant()).get_type() != Variant::STRING || instruction.get("expected", Variant()).get_type() != Variant::DICTIONARY) {
		result["error"] = "invalid_instruction_value";
		return result;
	}
	const String blocked = _chat_instruction_blocked_reason(force_consultation);
	if (!blocked.is_empty() && blocked != "draft_not_empty") {
		result["error"] = blocked;
		return result;
	}
	const String text = instruction["text"];
	if (text.strip_edges().is_empty() || text.utf8().length() > 8192 || text.contains_char(0)) {
		result["error"] = "invalid_instruction_text";
		return result;
	}
	if (!expected_context_matches(instruction["expected"], context)) {
		result["error"] = "chat_instruction_state_changed";
		return result;
	}
	if (!blocked.is_empty()) {
		result["error"] = blocked;
		return result;
	}
	// The route journal has already persisted execution uncertainty. This is a
	// regular user instruction: _send owns queueing, steering and work-order intake.
	// No confirmation is manufactured, and no history is written by the caller.
	const String previous_draft = input->get_text();
	SetAiDraft(text);
	_send_with_mode(force_consultation);
	if (!input->get_text().is_empty()) {
		if (input->get_text() == text) {
			SetAiDraft(previous_draft);
		}
		result["error"] = "chat_send_not_accepted";
		return result;
	}
	result["ok"] = true;
	result["instruction_submitted"] = true;
	result["business_completed"] = false;
	result["queue_count"] = GetAiSession().arrQueuedMessages.size();
	result["queue_paused"] = GetAiSession().bQueuePaused;
	result["busy"] = IsAiBusy();
	return result;
}

Dictionary AIChatDock::_chat_instruction_request(const Dictionary &p_message) {
	Dictionary result;
	result["ok"] = false;
#ifndef MACOS_ENABLED
	(void)p_message;
	result["error"] = "trusted_instruction_unsupported";
	return result;
#else
	const Variant version = p_message.get("protocol_version", Variant());
	if (!version.is_num() || double(version) != 1.0 || p_message.get("kind", Variant()).get_type() != Variant::STRING) {
		result["error"] = "invalid_instruction_message";
		return result;
	}
	const String kind = p_message["kind"];
	if (kind == "context") {
		if (p_message.size() != 2) {
			result["error"] = "invalid_instruction_message";
			return result;
		}
		result["ok"] = true;
		result["context"] = _chat_instruction_context();
		return result;
	}
	AIChatEditorControl *control = _get_editor_control();
	if (kind == "status") {
		return control->route_status(p_message.get("request_id", ""), "desktop.codex");
	}
	const bool retry = kind == "retry-delivery";
	const bool force_consultation = !retry && p_message.has("consultation_only");
	if ((!retry && (kind != "submit" || p_message.size() != (force_consultation ? 6 : 5) || !p_message.has("text") || (force_consultation && (p_message["consultation_only"].get_type() != Variant::BOOL || !bool(p_message["consultation_only"]))))) || (retry && p_message.size() != 4) || !p_message.has("expected")) {
		result["error"] = "invalid_instruction_message";
		return result;
	}
	Dictionary value;
	if (!retry) {
		value["text"] = p_message["text"];
		if (force_consultation) {
			value["consultation_only"] = true;
		}
	}
	value["expected"] = p_message["expected"];
	Dictionary operation;
	operation["action"] = retry ? "retry_pending_delivery" : "chat_submit_instruction";
	if (retry) {
		operation["host_action_request_id"] = p_message.get("request_id", Variant());
	}
	operation["value"] = value;
	Dictionary message;
	message["intent"] = "engine_operation";
	message["request_id"] = p_message.get("request_id", Variant());
	message["source"] = "desktop.codex";
	message["operation"] = operation;
	return control->route_message(message, true, false, false, true, true);
#endif
}
