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
#include "editor/docks/ai_chat_editor_control.h"
#include "editor/docks/gonggong_runtime_config.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/check_box.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/text_edit.h"

Dictionary AIChatDock::GetDeliveryScope() const
{
	Dictionary mapScope;
	mapScope["owner"] = conversation_id;
	mapScope["snapshot_id"] = snapshot_id;
	mapScope["generation"] = int64_t(session_generation);
	mapScope["source_root"] = _candidate_root();
	mapScope["engine_candidate"] = snapshot_state.get("engine_candidate", Dictionary());
	Dictionary mapValidation;
	String strError;
	mapValidation["ok"] = _validate_engine_candidate(strError);
	mapValidation["error"] = strError;
	mapScope["candidate_validation"] = mapValidation;
	mapScope["consultation_turn"] = consultation_turn;
	mapScope["consultation_only"] = consultation_only->is_pressed();
	mapScope["is_child"] = sub_agents.has(active_agent);
	mapScope["is_scheduled"] = scheduled_agents.has(active_agent);
	mapScope["allow_tools"] = allow_tools->is_pressed();
	mapScope["auto_execute_commands"] = auto_execute_commands->is_pressed();
	return mapScope;
}

void AIChatDock::_clear_delivery_files() {
	refChatController->GetDeliveryExecution().ClearFiles();
}

void AIChatDock::_run_delivery_tool(const Dictionary &p_arguments) {
	const bool mapped_parent = design_batches.has(active_agent) && design_batches[active_agent].has("parent_contract");
	if (mapped_parent && !parent_delivery_reentry) {
		parent_delivery_arguments = p_arguments.duplicate(true);
		if (!_gate_parent_completion()) {
			parent_delivery_arguments.clear();
			_finish_tool("Error: Live original-task completion owner unavailable. No delivery finalization was started.");
		}
		return;
	}
	const Variant pr = p_arguments.get("pr", Variant());
	Variant checklist = p_arguments.get("acceptance_items", Variant());
	Dictionary completion_guard;
	if (mapped_parent) {
		const Dictionary batch = design_batches[active_agent];
		completion_guard = batch.get("parent_authorized_request", Dictionary());
		Array verified_items;
		Array decisions;
		for (const Variant &id : Array(batch["order"])) {
			const Dictionary info = sub_agents[int(id)];
			const Dictionary acceptance = info.get("acceptance", Dictionary());
			const int reviewer = String(acceptance.get("reviewer", "-1")).to_int();
			if (!acceptance_reviews.has(reviewer) || !acceptance_reviews[reviewer].has("verified_decision")) {
				_finish_tool("Error: Independent delivery acceptance owner changed.");
				return;
			}
			Dictionary proof;
			proof["number"] = info["number"];
			proof["decision_json"] = JSON::stringify(acceptance_reviews[reviewer]["verified_decision"]);
			proof["decision_sha256"] = acceptance["decision_sha256"];
			decisions.push_back(proof);
			const Dictionary contract = Dictionary(batch["parent_contract"])["contract"];
			for (const Variant &value : Array(contract["criteria"])) {
				const Dictionary criterion = value;
				if (int(criterion["order"]) != int(info["number"])) {
					continue;
				}
				Dictionary item;
				item["id"] = criterion["id"];
				item["module"] = "registered-order-" + itos(int(info["number"]));
				item["acceptance"] = criterion["requirement"];
				item["state"] = "done";
				item["evidence"] = String(acceptance["evidence"]) + " sha256:" + String(acceptance["decision_file_sha256"]);
				verified_items.push_back(item);
			}
		}
		completion_guard["live_decisions"] = decisions;
		checklist = verified_items; // Producer declarations never replace these proofs.
	}
	Dictionary mapScope = GetDeliveryScope();
	mapScope["mapped_parent"] = mapped_parent;
	if (mapped_parent) {
		mapScope["parent_completion_guard"] = completion_guard;
		mapScope["verified_acceptance_items"] = checklist;
	}
	const Dictionary mapPrepared = refChatController->GetDeliveryExecution().PrepareDelivery(p_arguments, mapScope);
	if (!bool(mapPrepared.get("ok", false))) {
		_finish_tool("Error: " + String(mapPrepared.get("error", "Delivery request preparation failed.")));
		return;
	}
	const Dictionary binding = snapshot_state["engine_candidate"];
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
	Dictionary mapHost;
	mapHost["scope"] = GetDeliveryScope();
	mapHost["busy"] = busy;
	mapHost["workflow_python"] = GongGongRuntimeConfig::path(p_runtime, "workflow_python");
	mapHost["engine_root"] = _engine_root();
	mapHost["cache_dir"] = EditorPaths::get_singleton()->get_cache_dir();
	if (!delivery_retry_route.is_empty()) {
		mapHost["retry_route_status"] = _get_editor_control()->route_status(delivery_retry_route["request_id"], "desktop.codex");
	}
	const Dictionary mapPrepared = refChatController->GetDeliveryExecution().BuildProcessArguments(mapHost, r_executable, r_arguments);
	if (!bool(mapPrepared.get("ok", false))) {
		_finish_tool("Error: " + String(mapPrepared.get("error", "Delivery request launch failed.")));
		return false;
	}
	return true;
}

void AIChatDock::_capture_delivery_result(Dictionary &r_process_result) {
	r_process_result = refChatController->CaptureDeliveryResult(r_process_result, GetDeliveryScope(), api_key->get_text());
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
	if (pending_delivery_request.has("parent_completion_guard")) {
		set_meta("parent_business_accepted", turn_completed);
		set_meta("parent_completion_state", turn_completed ? "complete" : "readback_required");
	}
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
