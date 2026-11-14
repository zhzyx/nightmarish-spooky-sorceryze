/**************************************************************************/
/*  WorkflowRuntime.cpp                                                   */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                     */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#include "WorkflowRuntime.h"

#include <limits>
#include <set>

namespace AICore
{
namespace
{
Result MakeResult(bool bOk, bool bChanged, const std::string &strCode, const std::string &strReason, const RunSnapshot &stSnapshot = RunSnapshot())
{
	return { bOk, bChanged, strCode, strReason, stSnapshot };
}

bool IsSameRequest(const BeginRequest &stLeft, const BeginRequest &stRight)
{
	return stLeft.mapModel == stRight.mapModel && stLeft.mapBinding == stRight.mapBinding && stLeft.strNormalizedInput == stRight.strNormalizedInput && stLeft.strInitialState == stRight.strInitialState;
}

bool IsSameEvent(const PublishRequest &stLeft, const PublishRequest &stRight)
{
	return stLeft.nGeneration == stRight.nGeneration && stLeft.nExpectedSequence == stRight.nExpectedSequence && stLeft.strKind == stRight.strKind && stLeft.strState == stRight.strState && stLeft.strPayload == stRight.strPayload;
}

bool IsActive(const std::string &strState)
{
	return strState == "running" || strState == "waiting_tool" || strState == "waiting_confirmation" || strState == "reconciling";
}
}

bool WorkflowRuntime::IsTerminal(const std::string &strState)
{
	return strState == "succeeded" || strState == "failed" || strState == "cancelled";
}

bool WorkflowRuntime::IsPublicMetadataKey(const std::string &strKey, bool bModel)
{
	static const std::set<std::string> setModel = { "id", "model", "model_id", "name", "label", "provider", "provider_id", "backend", "backend_id", "connection_id", "revision", "catalog_revision", "source", "source_revision", "capabilities", "reasoning_effort", "selection_revision", "protocol", "variant", "connection_revision", "source_id", "effort", "strength", "nodes", "node_id", "image_model" };
	static const std::set<std::string> setBinding = { "id", "workflow", "scope", "project_id", "session_id", "node_id", "issue_number", "request_id", "repository", "source", "source_revision", "plan_id", "task_id", "run_id", "domain_run_id", "revision", "selection_epoch", "controller", "operation", "route", "workspace_id", "parent_run_id", "actor_id", "tenant_id", "binding_id" };
	return bModel ? setModel.count(strKey) != 0 : setBinding.count(strKey) != 0;
}

Result WorkflowRuntime::BeginRun(const BeginRequest &stRequest)
{
	std::lock_guard<std::mutex> lockRuns(mtxRuns);
	if (stRequest.strWorkflow.empty() || stRequest.strScope.empty() || stRequest.strRequestId.empty() || (stRequest.strInitialState != "running" && stRequest.strInitialState != "reconciling"))
	{
		return MakeResult(false, false, "invalid_request", "Identity and a valid initial state are required.");
	}
	const Identity stIdentity(stRequest.strWorkflow, stRequest.strScope, stRequest.strRequestId);
	const auto itIdentity = mapIdentities.find(stIdentity);
	if (itIdentity != mapIdentities.end())
	{
		const Run &stExisting = mapRuns.at(itIdentity->second);
		const bool bSame = IsSameRequest(stExisting.stRequest, stRequest);
		return MakeResult(bSame, false, bSame ? "idempotent" : "request_conflict", bSame ? "" : "The request identity is already bound to different content.", stExisting.stSnapshot);
	}
	for (const Metadata::value_type &stEntry : stRequest.mapModel)
	{
		if (!IsPublicMetadataKey(stEntry.first, true))
		{
			return MakeResult(false, false, "private_metadata", "Model metadata contains a non-public field.");
		}
	}
	for (const Metadata::value_type &stEntry : stRequest.mapBinding)
	{
		if (!IsPublicMetadataKey(stEntry.first, false))
		{
			return MakeResult(false, false, "private_metadata", "Binding metadata contains a non-public field.");
		}
	}
	if (nNextGeneration == std::numeric_limits<std::uint64_t>::max())
	{
		return MakeResult(false, false, "capacity", "Run generation space exhausted.");
	}
	Run stRun;
	stRun.stRequest = stRequest;
	RunSnapshot &stSnapshot = stRun.stSnapshot;
	stSnapshot.strWorkflow = stRequest.strWorkflow;
	stSnapshot.strScope = stRequest.strScope;
	stSnapshot.strRequestId = stRequest.strRequestId;
	stSnapshot.nGeneration = nNextGeneration++;
	stSnapshot.strRunId = "run-" + std::to_string(stSnapshot.nGeneration);
	stSnapshot.nSequence = 1;
	stSnapshot.strKind = "run_started";
	stSnapshot.strState = stRequest.strInitialState;
	stSnapshot.mapModel = stRequest.mapModel;
	stSnapshot.mapBinding = stRequest.mapBinding;
	mapIdentities.emplace(stIdentity, stSnapshot.strRunId);
	mapRuns.emplace(stSnapshot.strRunId, stRun);
	return MakeResult(true, true, "ok", "", stSnapshot);
}

Result WorkflowRuntime::Publish(const PublishRequest &stRequest)
{
	std::lock_guard<std::mutex> lockRuns(mtxRuns);
	const auto itRun = mapRuns.find(stRequest.strRunId);
	if (itRun == mapRuns.end())
	{
		return MakeResult(false, false, "not_found", "Run does not exist in this runtime.");
	}
	Run &stRun = itRun->second;
	RunSnapshot &stSnapshot = stRun.stSnapshot;
	if (stRequest.nGeneration != stSnapshot.nGeneration)
	{
		return MakeResult(false, false, "stale_generation", "Event belongs to another run generation.", stSnapshot);
	}
	if (stRequest.strEventId.empty())
	{
		return MakeResult(false, false, "invalid_event", "A stable event_id is required.", stSnapshot);
	}
	const auto itEvent = stRun.mapEvents.find(stRequest.strEventId);
	if (itEvent != stRun.mapEvents.end())
	{
		const bool bSame = IsSameEvent(itEvent->second, stRequest);
		return MakeResult(bSame, false, bSame ? "duplicate" : "event_conflict", bSame ? "" : "The event_id is already bound to different content.", stSnapshot);
	}
	if (IsTerminal(stSnapshot.strState))
	{
		return MakeResult(false, false, "terminal", "A terminal run cannot accept new events.", stSnapshot);
	}
	if (stRequest.nExpectedSequence != 0 && stRequest.nExpectedSequence != stSnapshot.nSequence)
	{
		return MakeResult(false, false, "stale_sequence", "Event was produced from an outdated snapshot.", stSnapshot);
	}
	std::string strNextState = stRequest.strState.empty() ? stSnapshot.strState : stRequest.strState;
	std::string strRequiredState;
	if (stRequest.strKind == "completed")
	{
		strRequiredState = "succeeded";
	}
	else if (stRequest.strKind == "failed" || stRequest.strKind == "cancelled")
	{
		strRequiredState = stRequest.strKind;
	}
	else if (stRequest.strKind == "tool_requested")
	{
		strRequiredState = "waiting_tool";
	}
	else if (stRequest.strKind != "progress" && stRequest.strKind != "text_delta" && stRequest.strKind != "artifact_ready")
	{
		return MakeResult(false, false, "invalid_kind", "Unknown or reserved event kind.", stSnapshot);
	}
	if (!strRequiredState.empty())
	{
		if (!stRequest.strState.empty() && stRequest.strState != strRequiredState)
		{
			return MakeResult(false, false, "invalid_state", "Event kind and state disagree.", stSnapshot);
		}
		strNextState = strRequiredState;
	}
	else if (!IsActive(strNextState))
	{
		return MakeResult(false, false, "invalid_state", "Terminal states require a terminal event.", stSnapshot);
	}
	if (stSnapshot.nSequence == std::numeric_limits<std::uint64_t>::max())
	{
		return MakeResult(false, false, "capacity", "Run sequence space exhausted.", stSnapshot);
	}
	stRun.mapEvents.emplace(stRequest.strEventId, stRequest);
	++stSnapshot.nSequence;
	stSnapshot.strKind = stRequest.strKind;
	stSnapshot.strState = strNextState;
	stSnapshot.strPayload = stRequest.strPayload;
	return MakeResult(true, true, "ok", "", stSnapshot);
}

Result WorkflowRuntime::Cancel(const std::string &strRunId, std::uint64_t nGeneration, const std::string &strEventId)
{
	PublishRequest stRequest;
	stRequest.strRunId = strRunId;
	stRequest.nGeneration = nGeneration;
	stRequest.strEventId = strEventId;
	stRequest.strKind = "cancelled";
	return Publish(stRequest);
}

Result WorkflowRuntime::Snapshot(const std::string &strRunId) const
{
	std::lock_guard<std::mutex> lockRuns(mtxRuns);
	const auto itRun = mapRuns.find(strRunId);
	if (itRun == mapRuns.end())
	{
		return MakeResult(false, false, "not_found", "Run does not exist in this runtime.");
	}
	return MakeResult(true, false, "ok", "", itRun->second.stSnapshot);
}
}
