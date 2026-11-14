/**************************************************************************/
/*  ProductionControl.cpp                                                 */
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

#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/production/ParentGate.h"
#include "scene/gui/check_box.h"

// Main-thread parent task entry. Context is data; all mutations first obtain a
// fresh host currentness receipt and preserve the original producer terminal.
String AIChatDock::ProductionEligibility(int nProducer) const
{
	if (!sub_agents.has(nProducer))
	{
		return "unknown_producer";
	}
	const Dictionary mapProducer = sub_agents[nProducer];
	if (int(mapProducer.get("parent", -1)) != active_agent || mapProducer.get("source", "") != "design" || mapProducer.get("request_id", "") != _work_order_binding("request_id") || int64_t(mapProducer.get("issue_number", 0)) != _work_order_binding("issue_number").to_int())
	{
		return "foreign_producer";
	}
	const Dictionary mapBatch = design_batches.has(active_agent) ? design_batches[active_agent] : Dictionary();
	const String strParentBlock = ProductionParentGate::GetBlockReason(
			bool(_read_design(active_agent).get("parent_completion_requested", false)),
			!Dictionary(mapBatch.get("parent_contract", Dictionary())).is_empty(),
			mapBatch.get("state", ""),
			!parent_completion_job.is_empty() && int(parent_completion_job.get("parent", -1)) == active_agent);
	if (!strParentBlock.is_empty())
	{
		return strParentBlock;
	}
	if (!bool(mapProducer.get("parallel_external", false)) || mapProducer.get("state", "") != "review" || mapProducer.has("acceptance") || (String(Dictionary(mapProducer.get("terminal_receipt", Dictionary())).get("file_sha256", "")).is_empty() || FileAccess::get_sha256(Dictionary(mapProducer.get("terminal_receipt", Dictionary())).get("path", "")) != String(Dictionary(mapProducer.get("terminal_receipt", Dictionary())).get("file_sha256", ""))) || !_design_child_ready(nProducer))
	{
		return "producer_not_known_unaccepted_terminal";
	}
	for (const KeyValue<int, Dictionary> &stReview : acceptance_reviews)
	{
		if (int(stReview.value.get("producer", -1)) != nProducer || bool(stReview.value.get("superseded", false)))
		{
			continue;
		}
		const Dictionary mapChild = Dictionary(stReview.value.get("children", Dictionary())).get(stReview.key, Dictionary());
		const Dictionary mapReceipt = mapChild.get("receipt_ref", Dictionary());
		const Ref<FileAccess> refReceipt = FileAccess::open(mapReceipt.get("path", ""), FileAccess::READ);
		if (mapChild.get("state", "") != "completed" || !bool(mapChild.get("transport_completed", false)) || !bool(mapReceipt.get("available", false)) || refReceipt.is_null() || refReceipt->get_length() > 16 * 1024 * 1024 || acceptance_bridge_jobs.has(stReview.key))
		{
			return "review_running_or_unknown";
		}
		const Variant varEnvelope = JSON::parse_string(refReceipt->get_as_utf8_string());
		if (varEnvelope.get_type() != Variant::DICTIONARY)
		{
			return "review_terminal_changed";
		}
		const Dictionary mapEnvelope = varEnvelope;
		const String strPayload = mapEnvelope.get("payload", "");
		if (strPayload.is_empty() || strPayload.sha256_text() != String(mapReceipt.get("sha256", "")) || mapEnvelope.get("sha256", "") != mapReceipt.get("sha256", Variant()))
		{
			return "review_terminal_changed";
		}
	}
	return String();
}

String AIChatDock::ProductionControl(const Dictionary &mapArguments)
{
	if (!IsAiBusy() || !allow_tools->is_pressed() || consultation_turn || consultation_only->is_pressed() || _is_review_child() || sub_agents.has(active_agent) || scheduled_agents.has(active_agent) || !history_writable || snapshot_transaction_failed || snapshot_restoring || GetAiSession().bQueuePaused)
	{
		return "Error: Current authorized production parent required.";
	}
	if (JSON::stringify(mapArguments).utf8().length() > 12288)
	{
		return "Error: Production request exceeds the bounded input budget.";
	}
	for (const Variant &varKey : mapArguments.keys())
	{
		const String strKey = varKey;
		if (strKey != "action" && strKey != "operation_id" && strKey != "execution_id" && strKey != "candidate_sha256" && strKey != "context" && strKey != "producer_id")
		{
			return "Error: Unknown production request field.";
		}
		const Variant varValue = mapArguments[varKey];
		const bool bProducerNumber = (varValue.get_type() == Variant::INT || varValue.get_type() == Variant::FLOAT) && double(varValue) >= 0 && double(varValue) <= 2147483647.0 && double(varValue) == double(int64_t(varValue));
		if (strKey == "producer_id" ? !bProducerNumber : varValue.get_type() != Variant::STRING)
		{
			return "Error: Invalid production request field type.";
		}
	}
	const String strAction = mapArguments.get("action", "");
	if (strAction == "status")
	{
		Array arrItems;
		for (int nId : _sub_agent_children(active_agent, true, _work_order_binding("request_id")))
		{
			const Dictionary mapProducer = sub_agents[nId];
			Dictionary mapItem;
			mapItem["producer_id"] = nId;
			mapItem["work_order"] = mapProducer.get("work_order", 0);
			mapItem["state"] = mapProducer.get("state", "unknown");
			mapItem["accepted"] = mapProducer.has("acceptance");
			mapItem["execution_id"] = Dictionary(mapProducer.get("terminal_receipt", Dictionary())).get("execution_id", "");
			mapItem["candidate_sha256"] = Dictionary(mapProducer.get("produced_candidate", Dictionary())).get("files_sha256", "");
			mapItem["blocked_reason"] = !GetAiSession().arrQueuedMessages.is_empty() ? String("parent_return_pending") : mapProducer.has("pending_parent_operation") ? String("continuation_pending")
																																									 : ProductionEligibility(nId);
			Array arrReceipts;
			for (const Variant &varOperation : Array(mapProducer.get("parent_operations", Array())))
			{
				const Dictionary mapOperation = varOperation;
				Dictionary mapReceipt;
				for (const String &strKey : { String("operation_id"), String("action"), String("state"), String("reason"), String("currentness_receipt") })
				{
					mapReceipt[strKey] = mapOperation.get(strKey, Variant());
				}
				arrReceipts.push_back(mapReceipt);
			}
			mapItem["operations"] = arrReceipts;
			Array arrActions;
			if (String(mapItem["blocked_reason"]).is_empty())
			{
				arrActions.push_back("supplement");
				arrActions.push_back("review");
				for (const KeyValue<int, Dictionary> &stReview : acceptance_reviews)
				{
					if (int(stReview.value.get("producer", -1)) == nId && !bool(stReview.value.get("superseded", false)) && stReview.value.has("eligible_repair") && int(mapProducer.get("parent_repairs", 0)) < 3)
					{
						arrActions.push_back("repair");
					}
				}
			}
			mapItem["eligible_actions"] = arrActions;
			mapItem["automatic_repairs"] = mapProducer.get("acceptance_repairs", 0);
			mapItem["parent_repairs"] = mapProducer.get("parent_repairs", 0);
			arrItems.push_back(mapItem);
		}
		Dictionary mapResult;
		mapResult["ok"] = true;
		mapResult["items"] = arrItems;
		return JSON::stringify(mapResult);
	}
	if (!GetAiSession().arrQueuedMessages.is_empty())
	{
		return "Error: Finish the current parent reply to receive the pending production result before another mutation.";
	}
	if (strAction != "supplement" && strAction != "review" && strAction != "repair")
	{
		return "Error: Expected status, supplement, review or repair.";
	}
	const int nProducer = mapArguments.get("producer_id", -1);
	const String strBlocked = ProductionEligibility(nProducer);
	if (!strBlocked.is_empty())
	{
		return "Error: " + strBlocked;
	}
	Dictionary mapProducer = sub_agents[nProducer];
	const String strOperation = mapArguments.get("operation_id", "");
	const String strContext = mapArguments.get("context", "");
	const Dictionary mapCandidate = mapProducer.get("produced_candidate", Dictionary());
	const Dictionary mapTerminal = mapProducer.get("terminal_receipt", Dictionary());
	Array arrOperations = mapProducer.get("parent_operations", Array());
	if (strOperation.is_empty() || strOperation.length() > 128 || !strOperation.replace("-", "").is_valid_ascii_identifier() || arrOperations.size() >= 32 || strContext.utf8().length() > 8192 || (strAction == "supplement" && strContext.strip_edges().is_empty()) || (strAction != "supplement" && !strContext.is_empty()) || String(mapArguments.get("execution_id", "")).is_empty() || mapArguments.get("execution_id", "") != mapTerminal.get("execution_id", Variant()) || mapArguments.get("candidate_sha256", "") != mapCandidate.get("files_sha256", Variant()))
	{
		return "Error: Invalid or stale bounded continuation arguments.";
	}
	if (strAction == "supplement")
	{
		Array arrProspective = Array(mapProducer.get("supplemental_inputs", Array())).duplicate(true);
		Dictionary mapInput;
		mapInput["operation_id"] = strOperation;
		mapInput["execution_id"] = mapArguments["execution_id"];
		mapInput["context"] = strContext;
		mapInput["sha256"] = strContext.sha256_text();
		arrProspective.push_back(mapInput);
		if (JSON::stringify(arrProspective).utf8().length() > 32768)
		{
			return "Error: Supplemental context serialization exceeds 32768 UTF-8 bytes.";
		}
	}
	for (const Variant &varOperation : arrOperations)
	{
		const Dictionary mapPrevious = varOperation;
		if (mapPrevious.get("operation_id", "") == strOperation || mapPrevious.get("state", "") == "pending")
		{
			return "Error: Replayed operation or current operation still pending.";
		}
	}
	int nReviewer = -1;
	for (const KeyValue<int, Dictionary> &stReview : acceptance_reviews)
	{
		if (int(stReview.value.get("producer", -1)) == nProducer && !bool(stReview.value.get("superseded", false)))
		{
			nReviewer = stReview.key;
		}
	}
	if (strAction == "repair" && (nReviewer < 0 || !acceptance_reviews[nReviewer].has("eligible_repair") || int(mapProducer.get("parent_repairs", 0)) >= 3))
	{
		return "Error: A current eligible independent review and remaining parent continuation budget are required.";
	}
	if (!design_batches.has(active_agent))
	{
		_register_design_batch(active_agent, _work_order_binding("request_id"), _work_order_binding("issue_number").to_int(), -1, true);
		// Registration may start or hold the complete-task parent gate. Its
		// state belongs to that gate, never to an individual producer operation.
		if (design_batches.has(active_agent) && !bool(_read_design(active_agent).get("parent_completion_requested", false)) && !String(design_batches[active_agent].get("state", "")).begins_with("parent_"))
		{
			design_batches[active_agent]["state"] = "continuation_idle";
		}
	}
	const String strRegistrationBlock = ProductionEligibility(nProducer);
	if (!strRegistrationBlock.is_empty())
	{
		return "Error: " + strRegistrationBlock;
	}
	if (!design_batches.has(active_agent) || !_design_parent_matches(active_agent, design_batches[active_agent]) || bool(design_batches[active_agent].get("reporting_blocked", false)) || acceptance_bridge_jobs.has(nProducer))
	{
		return "Error: Production batch unavailable or busy.";
	}
	Dictionary mapOperation = mapArguments.duplicate(true);
	mapOperation["state"] = "pending";
	mapOperation["ok"] = true;
	mapOperation["reviewer"] = nReviewer;
	mapOperation["terminal"] = mapTerminal.duplicate(true);
	mapOperation["binding"] = _read_design(active_agent).get("binding", Dictionary());
	mapOperation["token"] = design_batches[active_agent]["token"];
	Dictionary mapAuthority;
	for (const String &strKey : { String("token"), String("conversation_id"), String("snapshot_id"), String("workspace"), String("request_id"), String("issue_number") })
	{
		mapAuthority[strKey] = design_batches[active_agent].get(strKey, Variant());
	}
	mapOperation["authority"] = mapAuthority;
	arrOperations.push_back(mapOperation);
	mapProducer["parent_operations"] = arrOperations;
	mapProducer["pending_parent_operation"] = arrOperations.size() - 1;
	acceptance_bridge_results.erase(nProducer);
	Dictionary mapCheck;
	mapCheck["candidate"] = mapCandidate;
	_acceptance_bridge("acceptance-current", mapCheck, mapCandidate.get("root", ""), nProducer);
	if (!acceptance_bridge_jobs.has(nProducer))
	{
		mapOperation["state"] = "rejected";
		mapOperation["reason"] = "currentness_not_started";
		mapOperation["ok"] = false;
		mapProducer.erase("pending_parent_operation");
	}
	_queue_history_save();
	Dictionary mapReceipt;
	for (const String &strKey : { String("ok"), String("operation_id"), String("action"), String("state"), String("reason") })
	{
		mapReceipt[strKey] = mapOperation.get(strKey, Variant());
	}
	return JSON::stringify(mapReceipt);
}

void AIChatDock::CompleteProductionControl(int nProducer)
{
	if (!sub_agents.has(nProducer) || !sub_agents[nProducer].has("pending_parent_operation"))
	{
		return;
	}
	Dictionary mapProducer = sub_agents[nProducer];
	Array arrOperations = mapProducer["parent_operations"];
	Dictionary mapOperation = arrOperations[int(mapProducer["pending_parent_operation"])];
	mapProducer.erase("pending_parent_operation");
	mapOperation["state"] = "rejected";
	mapOperation["reason"] = "authority_candidate_or_terminal_changed";
	mapOperation["ok"] = false;
	const int nParent = mapProducer.get("parent", -1);
	if (active_agent != nParent || !allow_tools->is_pressed() || consultation_turn || consultation_only->is_pressed() || GetAiSession().bQueuePaused || !history_writable || snapshot_transaction_failed || snapshot_restoring || !ProductionEligibility(nProducer).is_empty() || !design_batches.has(nParent) || design_batches[nParent].get("token", "") != mapOperation["token"] || !_design_parent_matches(nParent, design_batches[nParent]) || _read_design(nParent).get("binding", Dictionary()) != mapOperation["binding"] || mapProducer.get("terminal_receipt", Variant()) != mapOperation["terminal"] || Dictionary(acceptance_bridge_results[nProducer].get("response", Dictionary())).is_empty())
	{
		_queue_history_save();
		return;
	}
	mapOperation["currentness_receipt"] = acceptance_bridge_results[nProducer].get("provenance", Dictionary());
	const String strAction = mapOperation["action"];
	if (strAction == "supplement")
	{
		Array arrInputs = mapProducer.get("supplemental_inputs", Array());
		Dictionary mapInput;
		mapInput["operation_id"] = mapOperation["operation_id"];
		mapInput["execution_id"] = mapOperation["execution_id"];
		mapInput["context"] = mapOperation["context"];
		mapInput["sha256"] = String(mapOperation["context"]).sha256_text();
		arrInputs.push_back(mapInput);
		mapProducer["supplemental_inputs"] = arrInputs;
		mapOperation["state"] = "context_recorded";
	}
	else if (strAction == "review")
	{
		for (KeyValue<int, Dictionary> &stReview : acceptance_reviews)
		{
			if (int(stReview.value.get("producer", -1)) == nProducer)
			{
				if (!bool(stReview.value.get("superseded", false)))
				{
					Array arrArchive = mapProducer.get("review_history", Array());
					arrArchive.push_back(stReview.value.duplicate(true));
					mapProducer["review_history"] = arrArchive;
				}
				stReview.value["superseded"] = true;
			}
		}
		design_batches[nParent]["state"] = "running";
		mapOperation["state"] = _start_acceptance_review(nProducer) ? "review_requested" : "review_not_started";
	}
	else
	{
		const int nReviewer = mapOperation["reviewer"];
		if (acceptance_reviews.has(nReviewer) && acceptance_reviews[nReviewer].has("eligible_repair") && int(mapProducer.get("parent_repairs", 0)) < 3)
		{
			acceptance_reviews[nReviewer]["parent_continuation"] = mapOperation.duplicate(true);
			acceptance_reviews[nReviewer]["parent_failure_reported"] = false;
			acceptance_bridge_results.erase(nReviewer);
			design_batches[nParent]["state"] = "running";
			mapOperation["state"] = "validating_repair";
			_finish_acceptance_review(nReviewer, acceptance_reviews[nReviewer].get("completion_history", Array()));
		}
	}
	if (mapOperation["state"] != Variant("rejected"))
	{
		mapOperation.erase("reason");
		mapOperation["ok"] = mapOperation["state"] != Variant("review_not_started");
	}
	_queue_history_save();
	callable_mp(this, &AIChatDock::_sub_agent_dispatch).call_deferred();
}

void AIChatDock::UpdateProductionOperation(int nProducer, const Dictionary &mapContext, const String &strState, const String &strReason)
{
	if (!sub_agents.has(nProducer) || !mapContext.has("parent_continuation"))
	{
		return;
	}
	const String strOperation = Dictionary(mapContext["parent_continuation"]).get("operation_id", "");
	for (const Variant &varOperation : Array(sub_agents[nProducer].get("parent_operations", Array())))
	{
		Dictionary mapOperation = varOperation;
		if (mapOperation.get("operation_id", "") == strOperation)
		{
			if (strState == "cancelled" && mapOperation.get("state", "") != "pending" && mapOperation.get("state", "") != "validating_repair")
			{
				return;
			}
			mapOperation["state"] = strState;
			mapOperation["reason"] = strReason;
			mapOperation["ok"] = strState == "repair_queued";
			_queue_history_save();
			return;
		}
	}
}
