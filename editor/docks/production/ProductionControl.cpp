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

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/templates/hash_set.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/gonggong_runtime_config.h"
#include "editor/docks/production/ParentGate.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/check_box.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"

namespace
{
Dictionary ReadProductionRecord(const String &strPath, Dictionary &out_mapReference)
{
	const Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::READ);
	if (!strPath.is_absolute_path() || refFile.is_null() || refFile->get_length() > 32 * 1024 * 1024)
	{
		return Dictionary();
	}
	const String strBytes = refFile->get_as_utf8_string();
	const Variant varValue = JSON::parse_string(strBytes);
	if (varValue.get_type() != Variant::DICTIONARY || strBytes.sha256_text() != FileAccess::get_sha256(strPath))
	{
		return Dictionary();
	}
	out_mapReference["path"] = strPath;
	out_mapReference["sha256"] = strBytes.sha256_text();
	return varValue;
}

Dictionary ReadBoundProductionRecord(const Dictionary &mapReference)
{
	Dictionary mapActual;
	const Dictionary mapValue = ReadProductionRecord(mapReference.get("path", ""), mapActual);
	return mapActual == mapReference ? mapValue : Dictionary();
}

String ValidateLegacyPendingRepair(const Dictionary &mapProducer, int nId, int nParent, const String &strConversation, const Dictionary &mapBinding)
{
	const Dictionary mapRepair = mapProducer.get("repair_of", Dictionary());
	const Dictionary mapTerminal = ReadBoundProductionRecord(mapRepair.get("terminal_receipt", Dictionary()));
	const Dictionary mapReview = ReadBoundProductionRecord(mapRepair.get("review", Dictionary()));
	const Dictionary mapRegistration = ReadBoundProductionRecord(mapTerminal.get("registration", Dictionary()));
	const Dictionary mapDispatch = ReadBoundProductionRecord(mapRegistration.get("dispatch_request", Dictionary()));
	const Dictionary mapReviewer = mapReview.get("reviewer", Dictionary());
	const Dictionary mapReceipt = mapProducer.get("parallel_receipt", Dictionary());
	const String strOutput = mapProducer.get("parallel_output", "");
	Dictionary mapOutputRef;
	const Dictionary mapOutput = ReadProductionRecord(strOutput, mapOutputRef);
	if (mapRepair.is_empty() || int(mapProducer.get("acceptance_repairs", 0)) != 1 || FileAccess::exists(strOutput + ".running") || mapOutput.is_empty() || mapOutputRef.get("sha256", "") != mapProducer.get("parallel_output_sha256", Variant()) || mapTerminal.is_empty() || mapReview.is_empty() || mapRegistration.is_empty() || mapDispatch.is_empty() || ReadBoundProductionRecord(mapReviewer.get("receipt", Dictionary())).is_empty())
	{
		return "legacy_repair_source_unavailable";
	}
	const Dictionary mapReviewProducer = mapReview.get("producer", Dictionary());
	const bool bMissing = mapRepair.get("mode", "") == "missing_execution_evidence";
	if (mapTerminal.get("execution_id", "") != mapRepair.get("execution_id", Variant()) || mapTerminal.get("state", "") != "review" || !bool(mapTerminal.get("transport_completed", false)) || int(mapTerminal.get("exit_code", -1)) != 0 || bool(mapTerminal.get("cancel_requested", true)) || !bool(Dictionary(mapTerminal.get("reporting", Dictionary())).get("ok", false)) || Dictionary(mapTerminal.get("reporting", Dictionary())).get("state", "") != "recorded_file" || mapTerminal.get("request_id", "") != mapBinding.get("request_id", Variant()) || int(mapTerminal.get("issue_number", -1)) != String(mapBinding.get("issue_number", "")).to_int() || mapReviewProducer.get("execution_id", "") != mapRepair.get("execution_id", Variant()) || mapReviewProducer.get("receipt", Variant()) != mapRepair.get("terminal_receipt", Variant()) || mapReviewProducer.get("worker_id", "") != mapTerminal.get("worker_id", Variant()) || mapReviewer.get("worker_id", "") == mapReviewProducer.get("worker_id", Variant()) || mapReview.get("design_sha256", "") != mapBinding.get("sha256", Variant()) || (bMissing ? mapReview.get("verdict", "") != "unknown" || mapReview.get("unknown_kind", "") != "missing_execution_evidence" : mapReview.get("verdict", "") != "fail"))
	{
		return "legacy_repair_terminal_or_review_changed";
	}
	bool bReceipt = false;
	for (const Variant &varValue : Array(mapOutput.get("workers", Array())))
	{
		bReceipt = bReceipt || (varValue.get_type() == Variant::DICTIONARY && Dictionary(varValue) == mapReceipt && int(mapReceipt.get("id", -1)) == nId && mapReceipt.get("execution_id", "") == mapRepair.get("execution_id", Variant()));
	}
	bool bWorker = false;
	for (const Variant &varValue : Array(mapDispatch.get("workers", Array())))
	{
		const Dictionary mapWorker = varValue;
		bWorker = bWorker || (int(mapWorker.get("id", -1)) == nId && int(mapWorker.get("order", -1)) == int(mapProducer.get("number", -1)) && mapWorker.get("designSha256", "") == mapBinding.get("sha256", Variant()));
	}
	if (!bReceipt || !bWorker || int(mapRegistration.get("editor_worker_id", -1)) != nId || int(mapRegistration.get("order", -1)) != int(mapProducer.get("number", -1)) || mapRegistration.get("execution_id", "") != mapRepair.get("execution_id", Variant()) || mapRegistration.get("design_sha256", "") != mapBinding.get("sha256", Variant()) || mapDispatch.get("requestId", "") != mapBinding.get("request_id", Variant()) || int(mapDispatch.get("issue", -1)) != String(mapBinding.get("issue_number", "")).to_int() || mapDispatch.get("workspace", "") != mapBinding.get("workspace", Variant()))
	{
		return "legacy_repair_original_dispatch_changed";
	}
	bool bQueued = false;
	for (const Variant &varValue : Array(mapProducer.get("review_history", Array())))
	{
		const Dictionary mapHistory = varValue;
		bQueued = bQueued || (bool(mapHistory.get("repair_queued", false)) && int(mapHistory.get("parent", -1)) == nParent && int(mapHistory.get("producer", -1)) == nId && mapHistory.get("conversation_id", "") == Variant(strConversation) && mapHistory.get("binding", Variant()) == Variant(mapBinding) && mapHistory.get("producer_execution_id", "") == mapRepair.get("execution_id", Variant()) && mapHistory.get("eligible_repair", Variant()) == Variant(mapReview));
	}
	if (!bQueued)
	{
		return "legacy_repair_parent_review_missing";
	}
	// Old hosts did not persist preparation attempts. Absence of their new field
	// is not evidence that a later dispatch or preparation finished.
	const Ref<DirAccess> refDirectory = DirAccess::open(strOutput.get_base_dir());
	if (refDirectory.is_null() || refDirectory->get_files().size() > 4096)
	{
		return "legacy_repair_dispatch_scan_unavailable";
	}
	for (const String &strName : refDirectory->get_files())
	{
		const bool bSetup = strName.begins_with("setup-") && strName.ends_with(".json") && !strName.ends_with(".result.json");
		const bool bDispatch = strName.begins_with("parallel-" + String(mapBinding.get("request_id", "")) + "-") && strName.ends_with(".json") && !strName.contains(".result.");
		if (!bSetup && !bDispatch)
		{
			continue;
		}
		Dictionary mapReference;
		const String strPath = refDirectory->get_current_dir().path_join(strName);
		const Dictionary mapRequest = ReadProductionRecord(strPath, mapReference);
		if (mapRequest.is_empty())
		{
			return "legacy_repair_dispatch_unknown";
		}
		if (mapRequest.get("requestId", "") != mapBinding.get("request_id", Variant()))
		{
			continue;
		}
		if (bSetup)
		{
			const Dictionary mapResult = ReadProductionRecord(strPath + ".result.json", mapReference);
			if (mapResult.get("state", "") != "ready" && mapResult.get("state", "") != "blocked")
			{
				return "legacy_repair_preparation_unknown";
			}
		}
		for (const Variant &varWorker : Array(mapRequest.get("workers", Array())))
		{
			if (Dictionary(Dictionary(varWorker).get("repairOf", Dictionary())).get("execution_id", "") == mapRepair.get("execution_id", Variant()))
			{
				return "legacy_repair_dispatch_requires_reconciliation";
			}
		}
	}
	return String();
}
} // namespace

String AIChatDock::CollectPreparedProductionJobs(int nParent, const Vector<int> &arrRepairs, const String &strActor, Dictionary &out_mapJobs) const
{
	if (arrRepairs.is_empty())
	{
		return String();
	}
	bool bPendingJob = false;
	for (int nId : _sub_agent_children(nParent, true, _work_order_binding("request_id", nParent)))
	{
		const String strState = sub_agents[nId].get("state", "");
		bPendingJob = bPendingJob || (!arrRepairs.has(nId) && strState != "review" && strState != "completed");
	}
	if (!bPendingJob)
	{
		return String();
	}
	Array arrWorkers;
	for (int nId : arrRepairs)
	{
		if (!sub_agents[nId].has("repair_of"))
		{
			return String(); // Initial preparation retries have no predecessor configuration.
		}
		Dictionary mapWorker;
		mapWorker["id"] = nId;
		mapWorker["order"] = sub_agents[nId]["number"];
		mapWorker["repairOf"] = sub_agents[nId]["repair_of"];
		arrWorkers.push_back(mapWorker);
	}
	String strConfig = EDITOR_GET("ai_chat/parallel_work_orders_config");
	const String strError = ProductionRepairConfiguration(arrWorkers, strConfig);
	if (!strError.is_empty())
	{
		return strError;
	}
	Dictionary mapConfigRef;
	const Dictionary mapConfig = ReadProductionRecord(strConfig, mapConfigRef);
	const Dictionary mapApproval = sub_agents[arrRepairs[0]].get("design_approval", Dictionary());
	const Dictionary mapBinding = mapApproval.get("binding", Dictionary());
	const Dictionary mapDocument = _read_design(nParent);
	const Array arrOrders = mapDocument.get("orders", Array());
	if (mapConfig.is_empty() || mapApproval.get("operator", "") != Variant(strActor) || mapDocument.get("binding", Variant()) != Variant(mapBinding))
	{
		return "prepared_job_authority_changed";
	}
	Dictionary mapLedgerRef;
	const Dictionary mapLedger = ReadProductionRecord(strConfig.get_base_dir().path_join("receipt.json"), mapLedgerRef);
	if (mapLedger.get("designSha256", "") != mapBinding.get("sha256", Variant()) || String(mapLedger.get("snapshot", "")).is_empty())
	{
		return "prepared_job_ledger_missing";
	}
	Array arrAnchors;
	for (int nId : arrRepairs)
	{
		const Dictionary mapProducer = sub_agents[nId];
		const Dictionary mapAssignment = mapProducer.get("parallel_assignment", Dictionary());
		const Dictionary mapTerminalRef = Dictionary(mapProducer["repair_of"])["terminal_receipt"];
		const Dictionary mapTerminal = ReadBoundProductionRecord(mapTerminalRef);
		const Dictionary mapRegistrationRef = mapTerminal.get("registration", Dictionary());
		const Dictionary mapRegistration = ReadBoundProductionRecord(mapRegistrationRef);
		const Dictionary mapDispatchRef = mapRegistration.get("dispatch_request", Dictionary());
		const Dictionary mapDispatch = ReadBoundProductionRecord(mapDispatchRef);
		const Dictionary mapCandidate = mapRegistration.get("candidate", Dictionary());
		bool bWorker = false;
		for (const Variant &varWorker : Array(mapDispatch.get("workers", Array())))
		{
			const Dictionary mapWorker = varWorker;
			bWorker = bWorker || (int(mapWorker.get("id", -1)) == nId && int(mapWorker.get("order", -1)) == int(mapProducer["number"]) && mapWorker.get("designSha256", "") == mapBinding.get("sha256", Variant()));
		}
		if (!bWorker || mapProducer.get("design_approval", Variant()) != Variant(mapApproval) || mapConfigRef.get("sha256", "") != mapAssignment.get("config_sha256", Variant()) || mapDispatch.get("config", "") != Variant(strConfig) || mapDispatch.get("requestId", "") != mapBinding.get("request_id", Variant()) || int(mapDispatch.get("issue", -1)) != String(mapBinding["issue_number"]).to_int() || mapDispatch.get("workspace", "") != mapBinding.get("workspace", Variant()) || int(mapRegistration.get("editor_worker_id", -1)) != nId || int(mapRegistration.get("order", -1)) != int(mapProducer["number"]) || mapRegistration.get("design_sha256", "") != mapBinding.get("sha256", Variant()) || mapRegistration.get("execution_id", "") != mapTerminal.get("execution_id", Variant()) || mapCandidate.get("base_sha", "") != mapLedger.get("snapshot", Variant()) || mapCandidate.get("root", "") != mapAssignment.get("worktree", Variant()))
		{
			return "prepared_job_predecessor_changed";
		}
		arrAnchors.push_back(mapTerminalRef);
		arrAnchors.push_back(mapRegistrationRef);
		arrAnchors.push_back(mapDispatchRef);
	}
	Dictionary mapSetup;
	Dictionary mapSetupRef;
	Dictionary mapResultRef;
	const Ref<DirAccess> refDirectory = DirAccess::open(String(mapBinding["workspace"]).path_join("data-collection/outbox"));
	if (refDirectory.is_null())
	{
		return "prepared_job_setup_unavailable";
	}
	const Vector<String> arrFiles = refDirectory->get_files();
	if (arrFiles.size() > 4096)
	{
		return "prepared_job_setup_scan_limit";
	}
	for (const String &strName : arrFiles)
	{
		if (!strName.begins_with("setup-") || !strName.ends_with(".json.result.json"))
		{
			continue;
		}
		Dictionary mapReference;
		const String strPath = refDirectory->get_current_dir().path_join(strName);
		const Dictionary mapResult = ReadProductionRecord(strPath, mapReference);
		if (mapResult.get("state", "") != "ready" || mapResult.get("config", "") != Variant(strConfig) || String(mapResult.get("receipt", "")).replace("\\", "/").simplify_path() != String(mapLedgerRef.get("path", "")).replace("\\", "/").simplify_path())
		{
			continue;
		}
		Dictionary mapRequestRef;
		const Dictionary mapRequest = ReadProductionRecord(strPath.trim_suffix(".result.json"), mapRequestRef);
		if (mapRequest.get("requestId", "") != mapBinding.get("request_id", Variant()) || mapRequest.get("workspace", "") != mapBinding.get("workspace", Variant()) || int(mapRequest.get("issue", -1)) != String(mapBinding["issue_number"]).to_int() || mapRequest.get("designSha256", "") != mapBinding.get("sha256", Variant()) || mapRequest.get("authorityRef", "") != mapConfig.get("authorityRef", Variant()))
		{
			continue;
		}
		mapSetup = mapRequest;
		if (!mapSetupRef.is_empty())
		{
			return "prepared_job_setup_ambiguous";
		}
		mapSetupRef = mapRequestRef;
		mapResultRef = mapReference;
		mapLedgerRef["path"] = mapResult["receipt"];
	}
	if (mapSetup.is_empty())
	{
		return "prepared_job_setup_binding_missing";
	}
	HashSet<int> setOrders;
	for (int nId : _sub_agent_children(nParent, true, mapBinding["request_id"]))
	{
		const Dictionary mapProducer = sub_agents[nId];
		const int nOrderNumber = mapProducer.get("number", -1);
		if (setOrders.has(nOrderNumber))
		{
			return "prepared_job_duplicate_producer";
		}
		setOrders.insert(nOrderNumber);
		if (arrRepairs.has(nId) || mapProducer.get("state", "") == "review" || mapProducer.get("state", "") == "completed")
		{
			continue;
		}
		const String strState = mapProducer.get("state", "");
		const int nIndex = int(mapProducer.get("work_order", 0)) - 1;
		if (int(mapProducer.get("parent", -1)) != nParent || int(mapProducer.get("issue_number", -1)) != String(mapBinding["issue_number"]).to_int())
		{
			return "prepared_job_parent_changed";
		}
		if ((strState != "waiting" && (strState != "interrupted" || mapProducer.get("state_before_restore", "") != "waiting")) || mapProducer.get("design_approval", Variant()) != Variant(mapApproval) || String(mapProducer.get("scope_sha256", "")).is_empty() || nIndex < 0 || nIndex >= arrOrders.size() || int(Dictionary(arrOrders[nIndex]).get("number", -1)) != nOrderNumber || Dictionary(arrOrders[nIndex]).get("title", "") != mapProducer.get("title", Variant()))
		{
			return "prepared_job_original_producer_changed";
		}
		for (const String &strKey : { String("parallel_assignment"), String("terminal_receipt"), String("execution_id"), String("parallel_receipt"), String("parallel_output"), String("external_candidate"), String("produced_candidate"), String("repair_of") })
		{
			if (mapProducer.has(strKey))
			{
				return "prepared_job_execution_unknown";
			}
		}
		int nRequested = 0;
		for (const Variant &varOrder : Array(mapSetup.get("orders", Array())))
		{
			nRequested += int(varOrder) == nOrderNumber ? 1 : 0;
		}
		Dictionary mapJob;
		int nMatches = 0;
		for (const Variant &varJob : Array(mapLedger.get("jobs", Array())))
		{
			const Dictionary mapCandidateJob = varJob;
			if (int(mapCandidateJob.get("order", -1)) == nOrderNumber)
			{
				mapJob = mapCandidateJob;
				nMatches++;
			}
		}
		Dictionary mapExpected = mapJob.duplicate(true);
		for (const String &strKey : { String("state"), String("branch"), String("common"), String("snapshot"), String("owner") })
		{
			mapExpected.erase(strKey);
		}
		int nConfigured = 0;
		for (const Variant &varJob : Array(mapConfig.get("jobs", Array())))
		{
			nConfigured += Dictionary(varJob) == mapExpected ? 1 : 0;
		}
		const String strDirectory = strConfig.replace("\\", "/").get_base_dir();
		if (nRequested != 1 || nMatches != 1 || nConfigured != 1 || mapJob.get("state", "") != "ready" || mapJob.get("snapshot", "") != mapLedger.get("snapshot", Variant()) || !strDirectory.get_file().begins_with("production-setup-") || mapJob.get("branch", "") != Variant("codex/production-" + strDirectory.get_file().trim_prefix("production-setup-") + "-" + itos(nOrderNumber)) || String(mapJob.get("worktree", "")).replace("\\", "/").simplify_path() != strDirectory.path_join("order-" + itos(nOrderNumber)) || String(mapJob.get("common", "")).is_empty())
		{
			return "prepared_job_missing_or_changed";
		}
		Dictionary mapReference;
		mapReference["parent"] = nParent;
		mapReference["producer"] = nId;
		mapReference["parent_conversation"] = nParent == active_agent ? GetAiSession().strConversation : agent_sessions[nParent].stData.strConversation;
		mapReference["approval"] = mapApproval;
		mapReference["scope_sha256"] = mapProducer["scope_sha256"];
		mapReference["config"] = mapConfigRef;
		mapReference["setup_request"] = mapSetupRef;
		mapReference["setup_result"] = mapResultRef;
		mapReference["setup_receipt"] = mapLedgerRef;
		mapReference["anchors"] = arrAnchors;
		mapReference["job"] = mapJob;
		out_mapJobs[nId] = mapReference;
	}
	return String();
}

String AIChatDock::ProductionPreparedConfiguration(const Array &arrWorkers, const String &strActor, String &strConfig) const
{
	for (const Variant &varWorker : arrWorkers)
	{
		const Dictionary mapWorker = varWorker;
		const Dictionary mapProducer = sub_agents[int(mapWorker["id"])];
		const Dictionary mapReference = mapProducer.get("prepared_job_reference", Dictionary());
		if (mapReference.is_empty())
		{
			continue;
		}
		const int nParent = mapProducer["parent"];
		const Dictionary mapApproval = mapProducer.get("design_approval", Dictionary());
		if (mapApproval.get("operator", "") != Variant(strActor))
		{
			return "prepared_job_actor_changed";
		}
		const Dictionary mapConfigRef = mapReference.get("config", Dictionary());
		const Dictionary mapConfig = ReadBoundProductionRecord(mapConfigRef);
		const Dictionary mapRuntime = GongGongRuntimeConfig::read_effective();
		const Array arrModels = mapConfig.get("models", Array());
		const Dictionary mapCommand = mapConfig.get("workerCommand", Dictionary());
		const Array arrArguments = mapCommand.get("args", Array());
		const bool bBackend = backend->get_selected() == 2 ? mapConfig.get("codex", "") == Variant(GongGongRuntimeConfig::path(mapRuntime, "codex")) : backend->get_selected() == 1 && mapCommand.get("executable", "") == Variant(GongGongRuntimeConfig::path(mapRuntime, "node")) && !arrArguments.is_empty() && arrArguments[0] == Variant(cli_entry->get_text().strip_edges());
		if (mapWorker.has("repairOf") || int(mapReference.get("parent", -1)) != nParent || int(mapReference.get("producer", -1)) != int(mapWorker["id"]) || mapReference.get("parent_conversation", "") != Variant(nParent == active_agent ? GetAiSession().strConversation : agent_sessions[nParent].stData.strConversation) || mapReference.get("approval", Variant()) != Variant(mapApproval) || mapReference.get("scope_sha256", "") != mapProducer.get("scope_sha256", Variant()) || _read_design(nParent).get("binding", Variant()) != mapApproval.get("binding", Variant()) || int(Dictionary(mapReference.get("job", Dictionary())).get("order", -1)) != int(mapWorker["order"]) || (!strConfig.is_empty() && mapConfigRef.get("path", "") != Variant(strConfig)) || !bBackend || int(mapConfig.get("capacity", 0)) != production_capacity->get_text().to_int() || mapConfig.get("python", "") != Variant(GongGongRuntimeConfig::path(mapRuntime, "workflow_python")) || arrModels.size() != 1 || arrModels[0].get_type() != Variant::DICTIONARY || Dictionary(arrModels[0]).get("id", "") != Variant(_active_model_field()->get_text()))
		{
			return "prepared_job_binding_or_runtime_changed";
		}
		Array arrReferences = Array(mapReference.get("anchors", Array())).duplicate();
		for (const String &strKey : { String("setup_request"), String("setup_result"), String("setup_receipt") })
		{
			arrReferences.push_back(mapReference.get(strKey, Dictionary()));
		}
		for (const Variant &varReference : arrReferences)
		{
			if (ReadBoundProductionRecord(varReference).is_empty())
			{
				return "prepared_job_source_changed";
			}
		}
		strConfig = mapConfigRef["path"];
	}
	return String();
}

Dictionary AIChatDock::RecordProductionPreparation(int nParent, const Array &arrWorkers, Dictionary mapAttempt, const String &strState, const String &strReason)
{
	const bool bExisting = mapAttempt.has("attempt_id");
	if (!mapAttempt.has("attempt_id"))
	{
		if (!mapAttempt.has("launch_state"))
		{
			mapAttempt["launch_state"] = "not_started";
		}
		mapAttempt["attempt_id"] = itos(OS::get_singleton()->get_process_id()) + "-" + itos(OS::get_singleton()->get_ticks_usec());
		mapAttempt["parent"] = nParent;
		mapAttempt["parent_conversation"] = nParent == active_agent ? GetAiSession().strConversation : agent_sessions.has(nParent) ? agent_sessions[nParent].stData.strConversation
																																   : String();
		mapAttempt["request_id"] = _work_order_binding("request_id", nParent);
		mapAttempt["issue_number"] = _work_order_binding("issue_number", nParent);
		mapAttempt["binding"] = _read_design(nParent).get("binding", Dictionary());
		mapAttempt["batch_token"] = design_batches.has(nParent) ? design_batches[nParent].get("token", "") : Variant("");
		mapAttempt["editor_pid"] = OS::get_singleton()->get_process_id();
		Array arrParticipants;
		Dictionary mapOwners;
		for (const Variant &varWorker : arrWorkers)
		{
			const int nId = Dictionary(varWorker)["id"];
			arrParticipants.push_back(nId);
			Dictionary mapOwner;
			for (const String &strKey : { String("design_approval"), String("terminal_receipt"), String("parallel_assignment"), String("repair_of") })
			{
				const Variant varValue = sub_agents[nId].get(strKey, Dictionary());
				mapOwner[strKey] = JSON::stringify(JSON::parse_string(JSON::stringify(varValue))).sha256_text();
			}
			mapOwners[itos(nId)] = mapOwner;
		}
		mapAttempt["participants"] = arrParticipants;
		mapAttempt["owners"] = mapOwners;
	}
	mapAttempt["state"] = strState;
	mapAttempt["reason"] = strReason.left(1024);
	for (const Variant &varId : Array(mapAttempt["participants"]))
	{
		const int nId = varId;
		if (sub_agents.has(nId) && int(sub_agents[nId].get("parent", -1)) == nParent && (!bExisting || Dictionary(sub_agents[nId].get("production_preparation", Dictionary())).get("attempt_id", "") == mapAttempt["attempt_id"]))
		{
			if (!bExisting && sub_agents[nId].has("production_preparation"))
			{
				Array arrHistory = sub_agents[nId].get("production_preparation_history", Array());
				arrHistory.push_back(sub_agents[nId]["production_preparation"]);
				sub_agents[nId]["production_preparation_history"] = arrHistory;
			}
			sub_agents[nId]["production_preparation"] = mapAttempt.duplicate(true);
		}
	}
	if (design_batches.has(nParent) && design_batches[nParent].get("token", "") == mapAttempt.get("batch_token", Variant()))
	{
		design_batches[nParent]["production_preparation"] = mapAttempt.duplicate(true);
	}
	_queue_history_save();
	_save_history();
	return mapAttempt;
}

bool AIChatDock::ProductionPreparationPersisted(const Dictionary &mapAttempt) const
{
	if (history_save_job || history_dirty || history_save_error)
	{
		return false;
	}
	const Ref<FileAccess> refHistory = FileAccess::open(_history_path(), FileAccess::READ);
	if (refHistory.is_null() || refHistory->get_length() > 64 * 1024 * 1024)
	{
		return false;
	}
	const Variant varHistory = JSON::parse_string(refHistory->get_as_utf8_string());
	if (varHistory.get_type() != Variant::DICTIONARY)
	{
		return false;
	}
	const String strExpected = JSON::stringify(JSON::parse_string(JSON::stringify(mapAttempt)));
	for (const Variant &varId : Array(mapAttempt.get("participants", Array())))
	{
		int nMatches = 0;
		for (const Variant &varAgent : Array(Dictionary(varHistory).get("agents", Array())))
		{
			const Dictionary mapAgent = varAgent;
			if (int(mapAgent.get("id", -1)) == int(varId))
			{
				const Dictionary mapProducer = mapAgent.get("sub_agent", Dictionary());
				if (JSON::stringify(mapProducer.get("production_preparation", Dictionary())) != strExpected)
				{
					return false;
				}
				nMatches++;
			}
		}
		if (nMatches != 1)
		{
			return false;
		}
	}
	return !Array(mapAttempt.get("participants", Array())).is_empty();
}

String AIChatDock::ValidateProductionPreparationResume(int nParent, const String &strRequest, const String &strActor, Vector<int> &arrProducers) const
{
	const String strConversation = nParent == active_agent ? GetAiSession().strConversation : agent_sessions.has(nParent) ? agent_sessions[nParent].stData.strConversation
																														  : String();
	for (int nId : _sub_agent_children(nParent, true, strRequest))
	{
		const Dictionary mapProducer = sub_agents[nId];
		const bool bLegacy = !mapProducer.has("production_preparation") && mapProducer.has("repair_of") && Dictionary(mapProducer.get("parallel_receipt", Dictionary())).get("execution_id", "") == Dictionary(mapProducer["repair_of"]).get("execution_id", Variant());
		if (!mapProducer.has("production_preparation") && !bLegacy)
		{
			continue;
		}
		const Dictionary mapAttempt = mapProducer.get("production_preparation", Dictionary());
		const String strState = mapAttempt.get("state", "");
		if (strState == "ready")
		{
			continue;
		}
		if (!production_setup->is_pressed() && String(EDITOR_GET("ai_chat/parallel_work_orders_config")).is_empty())
		{
			return "preparation_authorization_missing";
		}
		const Dictionary mapBatch = design_batches.has(nParent) ? design_batches[nParent] : Dictionary();
		const String strGate = ProductionParentGate::GetBlockReason(bool(_read_design(nParent).get("parent_completion_requested", false)), !Dictionary(mapBatch.get("parent_contract", Dictionary())).is_empty(), mapBatch.get("state", ""), !parent_completion_job.is_empty() && int(parent_completion_job.get("parent", -1)) == nParent);
		if (!strGate.is_empty())
		{
			return strGate;
		}
		if (strActor.is_empty() || Dictionary(mapProducer.get("design_approval", Dictionary())).get("operator", "") != Variant(strActor))
		{
			return "preparation_operator_changed";
		}
		const String strCurrentState = mapProducer.get("state", "");
		if (nParent != active_agent || strConversation.is_empty() || (!bLegacy && (mapAttempt.get("parent_conversation", "") != Variant(strConversation) || int(mapAttempt.get("parent", -1)) != nParent || mapAttempt.get("request_id", "") != Variant(strRequest) || mapAttempt.get("issue_number", "") != Variant(_work_order_binding("issue_number", nParent)) || JSON::stringify(mapAttempt.get("binding", Dictionary())) != JSON::stringify(_read_design(nParent).get("binding", Dictionary())))) || !_design_child_ready(nId) || mapProducer.has("acceptance") || (strCurrentState != "waiting" && !(strCurrentState == "interrupted" && mapProducer.get("state_before_restore", "") == "waiting")))
		{
			return "preparation_parent_or_producer_changed";
		}
		if (bLegacy)
		{
			const String strError = ValidateLegacyPendingRepair(mapProducer, nId, nParent, strConversation, _read_design(nParent).get("binding", Dictionary()));
			if (!strError.is_empty())
			{
				return strError;
			}
			Dictionary mapWorker;
			mapWorker["id"] = nId;
			mapWorker["order"] = mapProducer["number"];
			mapWorker["repairOf"] = mapProducer["repair_of"];
			Array arrWorkers;
			arrWorkers.push_back(mapWorker);
			String strConfig = EDITOR_GET("ai_chat/parallel_work_orders_config");
			const String strConfigError = ProductionRepairConfiguration(arrWorkers, strConfig);
			if (!strConfigError.is_empty())
			{
				return strConfigError;
			}
			arrProducers.push_back(nId);
			continue;
		}
		const Dictionary mapOwners = mapAttempt.get("owners", Dictionary());
		const Dictionary mapOwner = mapOwners.get(itos(nId), Dictionary());
		for (const String &strKey : { String("design_approval"), String("terminal_receipt"), String("parallel_assignment"), String("repair_of") })
		{
			const Variant varValue = mapProducer.get(strKey, Dictionary());
			if (mapOwner.get(strKey, "") != Variant(JSON::stringify(JSON::parse_string(JSON::stringify(varValue))).sha256_text()))
			{
				return "preparation_predecessor_changed";
			}
		}
		if (int64_t(mapAttempt.get("process_id", -1)) > 0 && OS::get_singleton()->is_process_running(int64_t(mapAttempt["process_id"])))
		{
			return "preparation_process_still_running";
		}
		const String strLaunch = mapAttempt.get("launch_state", "unknown");
		if (strLaunch != "not_started" && (strLaunch != "completed" || Dictionary(mapAttempt.get("result", Dictionary())).is_empty()))
		{
			return "preparation_launch_outcome_unknown";
		}
		for (const String &strKey : { String("request"), String("result") })
		{
			const Dictionary mapRef = mapAttempt.get(strKey, Dictionary());
			if (!mapRef.is_empty() && (String(mapRef.get("sha256", "")).is_empty() || FileAccess::get_sha256(mapRef.get("path", "")) != String(mapRef["sha256"])))
			{
				return "preparation_receipt_changed";
			}
		}
		const Array arrParticipants = mapAttempt.get("participants", Array());
		HashSet<int> setParticipants;
		for (const Variant &varId : arrParticipants)
		{
			if (!varId.is_num() || setParticipants.has(int(varId)))
			{
				return "preparation_participant_changed";
			}
			const int nOther = varId;
			setParticipants.insert(nOther);
			if (!sub_agents.has(nOther) || int(sub_agents[nOther].get("parent", -1)) != nParent || sub_agents[nOther].get("source", "") != "design" || sub_agents[nOther].get("request_id", "") != Variant(strRequest) || Dictionary(sub_agents[nOther].get("production_preparation", Dictionary())).get("attempt_id", "") != mapAttempt.get("attempt_id", Variant()))
			{
				return "preparation_participant_changed";
			}
		}
		if (!setParticipants.has(nId) || int(setParticipants.size()) != mapOwners.size())
		{
			return "preparation_participant_changed";
		}
		arrProducers.push_back(nId);
	}
	return String();
}

String AIChatDock::ProductionRepairConfiguration(const Array &arrWorkers, String &strConfig) const
{
	bool bRepair = false;
	for (const Variant &varWorker : arrWorkers)
	{
		bRepair = bRepair || Dictionary(varWorker).has("repairOf");
	}
	if (!bRepair)
	{
		return String();
	}
	String strRecorded;
	String strRecordedHash;
	Dictionary mapConfig;
	for (const Variant &varWorker : arrWorkers)
	{
		const Dictionary mapWorker = varWorker;
		const Dictionary mapProducer = sub_agents[int(mapWorker["id"])];
		const Dictionary mapRepair = mapProducer.get("repair_of", Dictionary());
		const Dictionary mapAssignment = mapProducer.get("parallel_assignment", Dictionary());
		const Dictionary mapTerminal = mapProducer.get("terminal_receipt", Dictionary());
		const Dictionary mapRef = mapRepair.get("terminal_receipt", Dictionary());
		const Dictionary mapReview = mapRepair.get("review", Dictionary());
		const String strPath = mapAssignment.get("config_path", "");
		const String strHash = mapAssignment.get("config_sha256", "");
		if (!mapWorker.has("repairOf") || mapRepair.is_empty() || mapRepair != Dictionary(mapWorker["repairOf"]) || String(mapRepair.get("continuation_id", "")).is_empty() || mapRepair.get("execution_id", "") != mapTerminal.get("execution_id", Variant()) || mapRef.get("path", "") != mapTerminal.get("path", Variant()) || mapRef.get("sha256", "") != mapTerminal.get("file_sha256", Variant()) || String(mapRef.get("sha256", "")).is_empty() || FileAccess::get_sha256(mapRef.get("path", "")) != String(mapRef["sha256"]) || String(mapReview.get("sha256", "")).is_empty() || FileAccess::get_sha256(mapReview.get("path", "")) != String(mapReview["sha256"]) || !strPath.is_absolute_path() || strHash.is_empty() || FileAccess::get_sha256(strPath) != strHash || (!strConfig.is_empty() && strConfig != strPath))
		{
			return "repair_configuration_or_predecessor_changed";
		}
		if (strRecorded.is_empty())
		{
			strRecorded = strPath;
			strRecordedHash = strHash;
			const Ref<FileAccess> refConfig = FileAccess::open(strPath, FileAccess::READ);
			if (refConfig.is_null() || refConfig->get_length() > 1024 * 1024)
			{
				return "repair_configuration_unavailable";
			}
			const Variant varConfig = JSON::parse_string(refConfig->get_as_utf8_string());
			if (varConfig.get_type() != Variant::DICTIONARY)
			{
				return "repair_configuration_invalid";
			}
			mapConfig = varConfig;
		}
		if (strRecorded != strPath || strRecordedHash != strHash || mapConfig.get("jobs", Variant()).get_type() != Variant::ARRAY)
		{
			return "repair_configuration_mixed";
		}
		Dictionary mapExpected = mapAssignment.duplicate(true);
		mapExpected.erase("config_path");
		mapExpected.erase("config_sha256");
		int nMatches = 0;
		for (const Variant &varJob : Array(mapConfig["jobs"]))
		{
			if (varJob.get_type() != Variant::DICTIONARY)
			{
				return "repair_assignment_invalid";
			}
			const Dictionary mapJob = varJob;
			if (int(mapJob.get("order", -1)) == int(mapWorker["order"]))
			{
				if (mapJob != mapExpected)
				{
					return "repair_assignment_changed";
				}
				nMatches++;
			}
		}
		if (nMatches != 1)
		{
			return "repair_assignment_missing_or_duplicate";
		}
	}
	if (strConfig.is_empty())
	{
		const Dictionary mapRuntime = GongGongRuntimeConfig::read_effective();
		const Array arrModels = mapConfig.get("models", Array());
		const Dictionary mapCommand = mapConfig.get("workerCommand", Dictionary());
		const Array arrArguments = mapCommand.get("args", Array());
		const bool bBackend = backend->get_selected() == 2 ? mapConfig.get("codex", "") == Variant(GongGongRuntimeConfig::path(mapRuntime, "codex")) : backend->get_selected() == 1 && mapCommand.get("executable", "") == Variant(GongGongRuntimeConfig::path(mapRuntime, "node")) && !arrArguments.is_empty() && arrArguments[0] == Variant(cli_entry->get_text().strip_edges());
		if (!production_setup->is_pressed() || !bBackend || mapConfig.get("authorityRef", "") != Variant("editor-production-authorization:" + _work_order_binding("request_id", _sub_agent_root(active_agent))) || int(mapConfig.get("capacity", 0)) != production_capacity->get_text().to_int() || mapConfig.get("python", "") != Variant(GongGongRuntimeConfig::path(mapRuntime, "workflow_python")) || arrModels.size() != 1 || arrModels[0].get_type() != Variant::DICTIONARY || Dictionary(arrModels[0]).get("id", "") != Variant(_active_model_field()->get_text()))
		{
			return "repair_runtime_selection_changed";
		}
	}
	strConfig = strRecorded;
	return String();
}

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
	const Dictionary mapPreparation = mapProducer.get("production_preparation", Dictionary());
	if (!mapPreparation.is_empty() && mapPreparation.get("state", "") != "ready")
	{
		return "production_preparation_blocked";
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
	if (!design_batches.has(active_agent) && !production_setup->is_pressed() && String(EDITOR_GET("ai_chat/parallel_work_orders_config")).is_empty())
	{
		return "parallel_production_setup_required";
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
			if (mapItem["blocked_reason"] == Variant("parallel_production_setup_required"))
			{
				mapItem["recovery_hint"] = "Enable 'Authorize automatic parallel production setup' (ProductionSetup) in AI Chat settings for this editor session, then query status again. Enabling this option alone does not start work.";
			}
			else if (mapItem["blocked_reason"] == Variant("production_preparation_blocked"))
			{
				mapItem["recovery_hint"] = "Preparation is blocked or its launch outcome is unknown. Preserve its receipts and reconcile the reported cause, then explicitly use Continue Production (SpawnWorkOrderAgents) on this original parent for one checked attempt. Status, input, settings and restart do not retry preparation.";
			}
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
