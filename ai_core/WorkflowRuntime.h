/**************************************************************************/
/*  WorkflowRuntime.h                                                     */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                     */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#pragma once

#include <cstdint>
#include <map>
#include <mutex>
#include <string>
#include <tuple>

namespace AICore
{
// Metadata values and payloads are canonical JSON supplied by the host boundary.
using Metadata = std::map<std::string, std::string>;

struct BeginRequest
{
	std::string strWorkflow;
	std::string strScope;
	std::string strRequestId;
	Metadata mapModel;
	Metadata mapBinding;
	std::string strNormalizedInput = "{}";
	std::string strInitialState = "running";
};

struct RunSnapshot
{
	std::uint32_t nSchemaVersion = 1;
	std::string strWorkflow;
	std::string strScope;
	std::string strRunId;
	std::string strRequestId;
	std::uint64_t nGeneration = 0;
	std::uint64_t nSequence = 0;
	std::string strKind;
	std::string strState;
	Metadata mapModel;
	Metadata mapBinding;
	std::string strPayload = "{}";
};

struct PublishRequest
{
	std::string strRunId;
	std::uint64_t nGeneration = 0;
	std::string strEventId;
	// Zero disables the optional compare-and-swap check; sequences start at one.
	std::uint64_t nExpectedSequence = 0;
	std::string strKind;
	std::string strState;
	std::string strPayload = "{}";
};

struct Result
{
	bool bOk = false;
	bool bChanged = false;
	std::string strCode;
	std::string strReason;
	RunSnapshot stSnapshot;
};

// Owns in-process runs. All methods are thread-safe; no callbacks run under locks.
// Destruction requires the owner to join its callers. No persistence is implied.
class WorkflowRuntime final
{
public:
	Result BeginRun(const BeginRequest &stRequest);
	Result Publish(const PublishRequest &stRequest);
	Result Cancel(const std::string &strRunId, std::uint64_t nGeneration, const std::string &strEventId = "cancel");
	Result Snapshot(const std::string &strRunId) const;
	static bool IsTerminal(const std::string &strState);
	static bool IsPublicMetadataKey(const std::string &strKey, bool bModel);

private:
	struct Run
	{
		BeginRequest stRequest;
		RunSnapshot stSnapshot;
		std::map<std::string, PublishRequest> mapEvents;
	};
	using Identity = std::tuple<std::string, std::string, std::string>;
	mutable std::mutex mtxRuns;
	std::uint64_t nNextGeneration = 1;
	std::map<Identity, std::string> mapIdentities;
	std::map<std::string, Run> mapRuns;
};
}
