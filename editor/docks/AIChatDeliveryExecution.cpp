/**************************************************************************/
/*  AIChatDeliveryExecution.cpp                                                  */
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

#include "AIChatDeliveryExecution.h"

#include "core/crypto/crypto_core.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_delivery_receipt.h"

namespace
{
Dictionary Failure(const String &strError)
{
	Dictionary mapResult;
	mapResult["ok"] = false;
	mapResult["error"] = strError;
	return mapResult;
}

Dictionary Success()
{
	Dictionary mapResult;
	mapResult["ok"] = true;
	return mapResult;
}

bool IsTrue(const Dictionary &mapValue, const String &strKey)
{
	return mapValue.get(strKey, Variant()).get_type() == Variant::BOOL && bool(mapValue[strKey]);
}

bool IsNumberEqual(const Variant &varValue, const Variant &varExpected)
{
	const bool bValueNumber = varValue.get_type() == Variant::INT || varValue.get_type() == Variant::FLOAT;
	const bool bExpectedNumber = varExpected.get_type() == Variant::INT || varExpected.get_type() == Variant::FLOAT;
	return bValueNumber && bExpectedNumber && Math::is_finite(double(varValue)) && Math::is_finite(double(varExpected)) && double(varValue) == Math::floor(double(varValue)) && double(varValue) == double(varExpected);
}

String RedactDiagnostic(const Callable &callRedact, const String &strValue)
{
	const Variant varValue = strValue;
	const Variant *arrArguments[] = { &varValue };
	Variant varResult;
	Callable::CallError stError;
	callRedact.callp(arrArguments, 1, varResult, stError);
	return stError.error == Callable::CallError::CALL_OK && varResult.get_type() == Variant::STRING ? String(varResult) : String();
}

bool IsSha(const String &strValue)
{
	return strValue.length() == 40 && strValue.is_valid_hex_number(false);
}

Variant ParseJson(const String &strText)
{
	Ref<JSON> refJson;
	refJson.instantiate();
	return refJson->parse(strText) == OK ? refJson->get_data() : Variant();
}

Dictionary ReadDictionary(const String &strPath)
{
	Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::READ);
	if (refFile.is_null() || refFile->get_length() > 256 * 1024)
	{
		return Dictionary();
	}
	const Variant varParsed = ParseJson(refFile->get_as_text());
	return varParsed.get_type() == Variant::DICTIONARY ? Dictionary(varParsed) : Dictionary();
}
}

void AIChatDeliveryExecution::_bind_methods()
{
}

AIChatDeliveryExecution::State &AIChatDeliveryExecution::GetState()
{
	return stState;
}

const AIChatDeliveryExecution::State &AIChatDeliveryExecution::GetState() const
{
	return stState;
}

Dictionary AIChatDeliveryExecution::ReadBinding(const Dictionary &mapScopeSnapshot) const
{
	const Dictionary mapValidation = mapScopeSnapshot.get("candidate_validation", Dictionary());
	const Dictionary mapBinding = mapScopeSnapshot.get("engine_candidate", Dictionary());
	if (!IsTrue(mapValidation, "ok") || mapBinding.is_empty() || String(mapScopeSnapshot.get("owner", "")).is_empty() || String(mapScopeSnapshot.get("snapshot_id", "")).is_empty() || mapScopeSnapshot.get("generation", Variant()).get_type() != Variant::INT || String(mapScopeSnapshot.get("source_root", "")).is_empty())
	{
		return Dictionary();
	}
	const String strPath = mapBinding.get("binding_path", "");
	Dictionary mapRecorded = ReadDictionary(strPath);
	if (mapRecorded.is_empty())
	{
		return Dictionary();
	}
	for (const String &strKey : { String("owner"), String("issue"), String("request_id"), String("source_root"), String("branch"), String("base_sha"), String("common_dir"), String("repository") })
	{
		if (!mapBinding.has(strKey) || !mapRecorded.has(strKey) || (strKey == "issue" ? !IsNumberEqual(mapBinding[strKey], mapRecorded[strKey]) : mapBinding[strKey] != mapRecorded[strKey]))
		{
			return Dictionary();
		}
	}
	if (mapBinding.get("source_root", "") != mapScopeSnapshot["source_root"])
	{
		return Dictionary();
	}
	// JSON stores numbers as floats; fixed workers require integer identities.
	mapRecorded["version"] = int64_t(mapRecorded.get("version", 0));
	mapRecorded["issue"] = int64_t(mapRecorded.get("issue", 0));
	mapRecorded["binding_path"] = strPath;
	return mapRecorded;
}

Dictionary AIChatDeliveryExecution::CreateRequest(const Dictionary &mapScopeSnapshot, const Dictionary &mapBinding) const
{
	uint8_t arrNonce[16];
	if (CryptoCore::generate_random(arrNonce, sizeof(arrNonce)) != OK)
	{
		return Dictionary();
	}
	Dictionary mapRequest;
	mapRequest["schema_version"] = 1;
	for (const String &strKey : { String("owner"), String("snapshot_id"), String("generation"), String("source_root") })
	{
		mapRequest[strKey] = mapScopeSnapshot[strKey];
	}
	mapRequest["nonce"] = String::hex_encode_buffer(arrNonce, sizeof(arrNonce));
	mapRequest["binding"] = mapBinding.duplicate(true);
	return mapRequest;
}

Dictionary AIChatDeliveryExecution::PrepareDelivery(const Dictionary &mapArguments, const Dictionary &mapScopeSnapshot)
{
	if (bool(mapScopeSnapshot.get("consultation_turn", true)) || bool(mapScopeSnapshot.get("consultation_only", true)) || bool(mapScopeSnapshot.get("is_child", true)) || bool(mapScopeSnapshot.get("is_scheduled", true)))
	{
		return Failure("Only the current authorized parent may complete its host-bound work order.");
	}
	const bool bMappedParent = bool(mapScopeSnapshot.get("mapped_parent", false));
	const Dictionary mapGuard = mapScopeSnapshot.get("parent_completion_guard", Dictionary());
	Variant varChecklist = mapArguments.get("acceptance_items", Variant());
	if (bMappedParent)
	{
		if (mapGuard.is_empty() || mapGuard.get("live_decisions", Variant()).get_type() != Variant::ARRAY || Array(mapGuard["live_decisions"]).is_empty())
		{
			return Failure("Live independent delivery acceptance is unavailable.");
		}
		varChecklist = mapScopeSnapshot.get("verified_acceptance_items", Variant());
	}
	const Variant varPr = mapArguments.get("pr", Variant());
	const String strCandidate = mapArguments.get("candidate", "");
	const String strSignedCommit = mapArguments.get("signed_commit", "");
	if ((varPr.get_type() != Variant::INT && varPr.get_type() != Variant::FLOAT) || !Math::is_finite(double(varPr)) || double(varPr) < 1 || double(varPr) > INT_MAX || double(varPr) != Math::floor(double(varPr)) || varChecklist.get_type() != Variant::ARRAY || Array(varChecklist).is_empty() || Array(varChecklist).size() > 64 || JSON::stringify(varChecklist).utf8().length() > 48 * 1024 || !IsSha(strCandidate) || !IsSha(strSignedCommit))
	{
		return Failure("A positive PR, exact candidate/signed SHAs and a complete bounded acceptance checklist are required.");
	}
	const Dictionary mapRecorded = ReadBinding(mapScopeSnapshot);
	if (mapRecorded.is_empty())
	{
		return Failure("The live engine candidate binding changed or cannot be read.");
	}
	Dictionary mapBinding;
	for (const String &strKey : { String("version"), String("owner"), String("issue"), String("request_id"), String("source_root"), String("branch"), String("base_sha"), String("common_dir"), String("repository"), String("origin"), String("binding_path") })
	{
		mapBinding[strKey] = mapRecorded.get(strKey, Variant());
	}
	Dictionary mapRequest = CreateRequest(mapScopeSnapshot, mapBinding);
	if (mapRequest.is_empty())
	{
		return Failure("Cannot create delivery request identity.");
	}
	mapRequest["pr"] = int64_t(varPr);
	mapRequest["expected_candidate"] = strCandidate;
	mapRequest["expected_signed_commit"] = strSignedCommit;
	mapRequest["acceptance_items"] = varChecklist.duplicate(true);
	if (bMappedParent)
	{
		mapRequest["parent_completion_guard"] = mapGuard.duplicate(true);
	}
	ClearFiles();
	stState.mapPendingRequest = mapRequest;
	stState.mapRetryRoute.clear();
	stState.mapReceipt.clear();
	stState.bExecutionStarted = false;
	stState.bQueuePaused = false;
	return Success();
}

Dictionary AIChatDeliveryExecution::PendingRetry(const Dictionary &mapScopeSnapshot) const
{
	const Dictionary mapBinding = mapScopeSnapshot.get("engine_candidate", Dictionary());
	const String strFolder = String(mapBinding.get("common_dir", "")).path_join("gonggong-delivery-finalization");
	const Ref<DirAccess> refDirectory = DirAccess::open(strFolder);
	if (refDirectory.is_null())
	{
		return Failure("pending_delivery_journal_unavailable");
	}
	const PackedStringArray arrFiles = refDirectory->get_files();
	if (arrFiles.size() > 1024)
	{
		return Failure("pending_delivery_ambiguous");
	}
	Dictionary mapResult;
	int nMatches = 0;
	for (const String &strName : arrFiles)
	{
		if (!strName.ends_with(".json"))
		{
			continue;
		}
		const String strPath = strFolder.path_join(strName);
		const Dictionary mapSaved = refDirectory->is_link(strName) ? Dictionary() : ReadDictionary(strPath);
		if (mapSaved.is_empty())
		{
			return Failure("pending_delivery_journal_invalid");
		}
		const Dictionary mapScope = mapSaved.get("scope", Dictionary());
		if (mapScope.get("owner", "") != mapScopeSnapshot.get("owner", "") || mapScope.get("source_root", "") != mapScopeSnapshot.get("source_root", "") || !IsNumberEqual(mapScope.get("issue", Variant()), mapBinding.get("issue", Variant())) || mapScope.get("request_id", "") != mapBinding.get("request_id", ""))
		{
			continue;
		}
		const Dictionary mapReceipt = mapSaved.get("last_receipt", Dictionary());
		if (mapReceipt.get("snapshot_id", "") != mapScopeSnapshot.get("snapshot_id", ""))
		{
			continue;
		}
		if (!IsTrue(mapReceipt, "completion_verified") || mapReceipt.get("ok", Variant()).get_type() != Variant::BOOL || bool(mapReceipt["ok"]) || mapReceipt.get("stage", "") != "activation_pending")
		{
			return Failure("terminal_state_requires_readback");
		}
		const Dictionary mapFacts = mapReceipt.get("host_facts", Dictionary());
		const String strPrefix = "https://github.com/" + String(mapBinding.get("repository", "")) + "/pull/";
		const String strUrl = mapFacts.get("pull_request", "");
		const String strNumber = strUrl.trim_prefix(strPrefix);
		const String strCandidate = mapScope.get("candidate", "");
		const String strSignedCommit = mapScope.get("signed_commit", "");
		if (!strUrl.begins_with(strPrefix) || !strNumber.is_valid_int() || strNumber.to_int() <= 0 || strNumber.to_int() > INT_MAX || strNumber != itos(strNumber.to_int()) || !IsSha(strCandidate) || !IsSha(strSignedCommit))
		{
			return Failure("pending_delivery_journal_invalid");
		}
		nMatches++;
		mapResult["pr"] = strNumber.to_int();
		mapResult["expected_candidate"] = strCandidate;
		mapResult["expected_signed_commit"] = strSignedCommit;
		mapResult["original_journal_sha256"] = FileAccess::get_sha256(strPath);
	}
	if (nMatches != 1)
	{
		return Failure(nMatches == 0 ? "pending_delivery_not_found" : "pending_delivery_ambiguous");
	}
	mapResult["ok"] = true;
	return mapResult;
}

Dictionary AIChatDeliveryExecution::PrepareRetry(const Dictionary &mapArguments, const Dictionary &mapScopeSnapshot)
{
	if (mapScopeSnapshot.get("retry_blocked_reason", Variant()).get_type() != Variant::STRING || !String(mapScopeSnapshot["retry_blocked_reason"]).is_empty())
	{
		return Failure(mapScopeSnapshot.get("retry_blocked_reason", "permission_denied"));
	}
	if (!stState.mapReceipt.is_empty() && (!IsTrue(stState.mapReceipt, "completion_verified") || stState.mapReceipt.get("stage", "") != "activation_pending" || stState.mapReceipt.get("ok", Variant()).get_type() != Variant::BOOL || bool(stState.mapReceipt["ok"])))
	{
		return Failure("terminal_state_requires_readback");
	}
	const Dictionary mapRecorded = ReadBinding(mapScopeSnapshot);
	if (mapRecorded.is_empty() || stState.strRetryInstance.is_empty() || String(mapArguments.get("host_action_request_id", "")).is_empty())
	{
		return Failure("known_work_order_owner_required");
	}
	const Dictionary mapSelected = PendingRetry(mapScopeSnapshot);
	if (!IsTrue(mapSelected, "ok"))
	{
		return mapSelected;
	}
	Dictionary mapRequest = CreateRequest(mapScopeSnapshot, mapRecorded);
	if (mapRequest.is_empty())
	{
		return Failure("delivery_retry_nonce_unavailable");
	}
	mapRequest["kind"] = "native_delivery_retry";
	mapRequest["engine_pid"] = int64_t(OS::get_singleton()->get_process_id());
	mapRequest["host_instance_id"] = stState.strRetryInstance;
	for (const String &strKey : { String("pr"), String("expected_candidate"), String("expected_signed_commit"), String("original_journal_sha256") })
	{
		mapRequest[strKey] = mapSelected[strKey];
	}
	mapRequest["host_action_request_id"] = mapArguments["host_action_request_id"];
	ClearFiles();
	stState.mapPendingRequest = mapRequest;
	stState.mapReceipt.clear();
	stState.mapRetryRoute.clear();
	stState.mapRetryRoute["request_id"] = mapArguments["host_action_request_id"];
	stState.bExecutionStarted = false;
	stState.bQueuePaused = true;
	Dictionary mapResult = Success();
	mapResult["delivery_retry_started"] = true;
	mapResult["business_completed"] = false;
	return mapResult;
}

bool AIChatDeliveryExecution::MatchesScope(const Dictionary &mapScopeSnapshot) const
{
	if (stState.mapPendingRequest.is_empty())
	{
		return false;
	}
	for (const String &strKey : { String("owner"), String("snapshot_id"), String("generation"), String("source_root") })
	{
		if (!mapScopeSnapshot.has(strKey) || stState.mapPendingRequest.get(strKey, Variant()) != mapScopeSnapshot[strKey])
		{
			return false;
		}
	}
	return true;
}

Dictionary AIChatDeliveryExecution::BuildProcessArguments(const Dictionary &mapHostSnapshot, String &out_strExecutable, List<String> &out_arrArguments)
{
	out_strExecutable = String();
	out_arrArguments.clear();
	const Dictionary mapScope = mapHostSnapshot.get("scope", Dictionary());
	const Dictionary mapBinding = ReadBinding(mapScope);
	if (!IsTrue(mapHostSnapshot, "busy") || !MatchesScope(mapScope) || mapBinding.is_empty() || stState.bExecutionStarted)
	{
		return Failure("Delivery owner, generation or candidate changed before execution.");
	}
	const Dictionary mapExpectedBinding = stState.mapPendingRequest["binding"];
	for (const Variant &varKey : mapExpectedBinding.keys())
	{
		if (mapBinding.get(varKey, Variant()) != mapExpectedBinding[varKey])
		{
			return Failure("Delivery candidate binding changed before execution.");
		}
	}
	const bool bRetry = !stState.mapRetryRoute.is_empty();
	if (bRetry)
	{
		const Dictionary mapRoute = mapHostSnapshot.get("retry_route_status", Dictionary());
		if (!IsTrue(mapRoute, "delivery_retry_started") || bool(mapRoute.get("receipt_persistence_failed", false)))
		{
			return Failure("The terminal retry host-action receipt was not persisted.");
		}
		// The controller performs the original permission checks again immediately
		// before this call. The busy state is expected during the deferred effect.
		if (!IsTrue(mapScope, "allow_tools") || !IsTrue(mapScope, "auto_execute_commands") || bool(mapScope.get("consultation_only", true)) || bool(mapScope.get("is_child", true)) || bool(mapScope.get("is_scheduled", true)))
		{
			return Failure("Terminal retry permission changed before execution.");
		}
		const Dictionary mapSelected = PendingRetry(mapScope);
		if (!IsTrue(mapSelected, "ok") || mapSelected.get("original_journal_sha256", "") != stState.mapPendingRequest.get("original_journal_sha256", ""))
		{
			return Failure("The terminal retry journal changed before execution.");
		}
	}
	const String strExecutable = mapHostSnapshot.get("workflow_python", "");
	const String strEngineRoot = mapHostSnapshot.get("engine_root", "");
	const bool bMappedParent = stState.mapPendingRequest.has("parent_completion_guard");
	const String strWorker = strEngineRoot.path_join(bMappedParent ? "tools/gonggong_bridge.py" : (bRetry ? "tools/editor_delivery_retry.py" : "tools/editor_delivery_finalize.py"));
	const String strCache = mapHostSnapshot.get("cache_dir", "");
	if (strExecutable.is_empty() || !FileAccess::exists(strExecutable) || !FileAccess::exists(strWorker) || strCache.is_empty() || !DirAccess::dir_exists_absolute(strCache))
	{
		return Failure("The installed delivery worker, workflow Python or cache directory is missing.");
	}
	const String strPrefix = strCache.path_join("delivery-finalize-" + itos(OS::get_singleton()->get_process_id()) + "-" + String(stState.mapPendingRequest["nonce"]));
	stState.strRequestPath = strPrefix + ".request.json";
	stState.strResultPath = strPrefix + ".result.json";
	if (bMappedParent)
	{
		stState.mapPendingRequest["active"] = true;
		stState.mapPendingRequest["request_nonce"] = stState.mapPendingRequest["nonce"];
		Dictionary mapGuard = stState.mapPendingRequest["parent_completion_guard"];
		mapGuard["host_liveness_path"] = stState.strRequestPath;
		mapGuard["request_nonce"] = stState.mapPendingRequest["nonce"];
	}
	Ref<FileAccess> refFile = FileAccess::open(stState.strRequestPath, FileAccess::WRITE);
	if (refFile.is_null() || !refFile->store_string(JSON::stringify(stState.mapPendingRequest)))
	{
		refFile.unref();
		ClearFiles();
		return Failure("Cannot persist the delivery request.");
	}
	refFile->flush();
	const Error eWriteError = refFile->get_error();
	refFile.unref();
	if (eWriteError != OK || (bMappedParent && DirAccess::copy_absolute(stState.strRequestPath, stState.strRequestPath + ".original.json") != OK))
	{
		ClearFiles();
		return Failure("Cannot flush or retain the original delivery request for readback.");
	}
	out_strExecutable = strExecutable;
	out_arrArguments.push_back("-I");
	out_arrArguments.push_back(strWorker);
	if (bMappedParent)
	{
		out_arrArguments.push_back("parent-delivery");
	}
	out_arrArguments.push_back(bMappedParent ? "--workspace" : "--source-root");
	out_arrArguments.push_back(mapScope["source_root"]);
	out_arrArguments.push_back("--request");
	out_arrArguments.push_back(stState.strRequestPath);
	out_arrArguments.push_back("--out");
	out_arrArguments.push_back(stState.strResultPath);
	stState.bExecutionStarted = true;
	return Success();
}

Dictionary AIChatDeliveryExecution::CaptureResult(const Dictionary &mapProcessResult, const Callable &callRedact)
{
	Dictionary mapProcess = mapProcessResult.duplicate(true);
	mapProcess.erase("delivery_scope");
	mapProcess.erase("busy");
	mapProcess["ok"] = false;
	mapProcess.erase("delivery_finalization");
	mapProcess.erase("delivery_worker_result_sha256");
	if (!IsTrue(mapProcessResult, "busy") || !MatchesScope(mapProcessResult.get("delivery_scope", Dictionary())))
	{
		ClearFiles();
		return mapProcess;
	}
	Ref<FileAccess> refFile = FileAccess::open(stState.strResultPath, FileAccess::READ);
	const int64_t nBytes = refFile.is_valid() ? int64_t(refFile->get_length()) : -1;
	const Variant varParsed = refFile.is_valid() && nBytes <= 256 * 1024 ? ParseJson(refFile->get_as_text()) : Variant();
	refFile.unref();
	if (!stState.mapRetryRoute.is_empty() && nBytes >= 0 && nBytes <= 256 * 1024)
	{
		mapProcess["delivery_worker_result_sha256"] = FileAccess::get_sha256(stState.strResultPath);
	}
	Dictionary mapResult = varParsed.get_type() == Variant::DICTIONARY ? Dictionary(varParsed) : Dictionary();
	const Dictionary mapGuard = mapProcess.get("provenance_guard", Dictionary());
	const bool bProcessOk = int(mapProcess.get("exit_code", -1)) == 0 && !bool(mapProcess.get("timed_out", true)) && !bool(mapProcess.get("cancelled", false)) && IsTrue(mapGuard, "ok");
	const bool bMatched = AIChatDeliveryReceipt::matches(mapResult, stState.mapPendingRequest);
	const bool bCompleted = bMatched && bProcessOk && AIChatDeliveryReceipt::completed(mapResult, stState.mapPendingRequest);
	Dictionary mapDiagnostic;
	if ((!bCompleted || !IsTrue(mapResult, "ok")) && nBytes >= 0)
	{
		mapDiagnostic["bytes"] = nBytes;
		mapDiagnostic["sha256"] = nBytes <= 256 * 1024 ? FileAccess::get_sha256(stState.strResultPath) : String();
		const String strRetained = stState.strResultPath + ".retained.json";
		if (!FileAccess::exists(strRetained) && DirAccess::rename_absolute(stState.strResultPath, strRetained) == OK)
		{
			mapDiagnostic["path"] = strRetained;
			stState.strResultPath = String();
		}
	}
	ClearFiles();
	if (bMatched && !mapDiagnostic.is_empty())
	{
		mapResult["private_worker_diagnostic"] = mapDiagnostic;
	}
	if (bMatched && !bool(mapResult["completion_verified"]) && !bool(mapResult["mutations_may_have_started"]) && mapResult.get("stage", "") == "validation" && IsTrue(mapGuard, "ok"))
	{
		mapProcess["delivery_finalization"] = mapResult;
		return mapProcess;
	}
	if (!bCompleted)
	{
		Dictionary mapUnknown = Failure("delivery_readback_unknown; reconcile existing state before any retry");
		mapUnknown["completion_verified"] = false;
		mapUnknown["private_worker_diagnostic"] = mapDiagnostic;
		// The optional callback only sanitizes presentation text; it cannot approve
		// a receipt or perform delivery. Without it, raw diagnostics stay private.
		if (bMatched && callRedact.is_valid())
		{
			mapUnknown["worker_stage"] = RedactDiagnostic(callRedact, String(mapResult.get("stage", "unknown"))).left(128);
			mapUnknown["worker_error"] = RedactDiagnostic(callRedact, String(mapResult.get("error", ""))).left(1000);
			mapUnknown["private_diagnostic_ref"] = String(mapResult.get("private_diagnostic_ref", ""));
		}
		mapResult = mapUnknown;
	}
	stState.mapReceipt = mapResult.duplicate(true);
	stState.bQueuePaused = true;
	mapProcess["queue_paused"] = true;
	mapProcess["ok"] = bCompleted && IsTrue(mapResult, "ok");
	mapProcess["delivery_finalization"] = mapResult;
	return mapProcess;
}

void AIChatDeliveryExecution::ClearFiles()
{
	for (const String &strPath : { stState.strRequestPath, stState.strResultPath })
	{
		if (!strPath.is_empty() && FileAccess::exists(strPath))
		{
			DirAccess::remove_absolute(strPath);
		}
	}
	stState.strRequestPath = String();
	stState.strResultPath = String();
}
