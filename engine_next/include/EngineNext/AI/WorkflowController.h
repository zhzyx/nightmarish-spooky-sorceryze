/**************************************************************************/
/*  WorkflowController.h                                                  */
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

#pragma once

#include "engine_next/include/EngineNext/AI/ArtifactAdapter.h"
#include "engine_next/include/EngineNext/AI/IProcessTransport.h"
#include "engine_next/include/EngineNext/AI/WorkflowSnapshot.h"

#include <atomic>
#include <cstddef>
#include <mutex>
#include <set>
#include <string>

namespace EngineNext::AI
{

struct HostConfig
{
	std::string strPython;
	std::string strExecutorScript;
	std::string strFactory = "editor_demo:factory";
	std::string strDatabase;
	std::string strStatePath;
	std::string strOutput;
	std::uint32_t nTimeoutMsec = 60000;
	std::size_t nOutputLimit = 384ULL * 1024ULL * 1024ULL;
	std::uint32_t nMaxSteps = 0;
	bool bResume = false;
};

struct ControllerResult
{
	bool bHasSnapshot = false;
	Serialization::JsonValue stSnapshot;
	std::string strExecutorRunId;
	std::string strPackageDigest;
	Assets::Diagnostics arrDiagnostics;
};

class WorkflowController final
{
	IProcessTransport *pTransport;
	WorkflowSnapshot stRuntime;
	std::mutex stMutex;
	std::atomic<bool> bCancelRequested{ false };
	std::string strRunId;
	std::string strExecutorRunId;
	std::set<std::string> setPublishedArtifacts;

	bool Execute(const HostConfig &in_stConfig, const std::string &in_strCommand,
			const Serialization::JsonValue &in_stInput, Serialization::JsonValue &out_stResult, Assets::Diagnostics &out_arrDiagnostics);
	bool SaveState(const HostConfig &in_stConfig, const std::string &in_strRequest, const std::string &in_strRequestDigest, bool in_bPublished,
			const std::string &in_strDigest, Assets::Diagnostics &out_arrDiagnostics);
	bool ReadState(const HostConfig &in_stConfig, const std::string &in_strRequest, const std::string &in_strRequestDigest, Assets::Diagnostics &out_arrDiagnostics);
	bool BeginRun(const AiAssetRequest &in_stRequest, const Serialization::JsonValue &in_stOriginalRequest, const std::string &in_strInputDigest);
	bool PublishEvent(const std::string &in_strKind, const Serialization::JsonValue &in_stPayload, const std::string &in_strState = std::string());
	bool IsCancellationRequested() const noexcept;
	std::string CurrentState();
	Serialization::JsonValue CurrentSnapshot();
	void CancelExecutor(const HostConfig &in_stConfig);
	bool ValidateProviderModel(const Serialization::JsonValue &in_stStatus, const Serialization::JsonValue &in_stModel);
	bool Fail(const std::string &in_strCode, const std::string &in_strMessage, ControllerResult &out_stResult);

public:
	explicit WorkflowController(IProcessTransport &in_stTransport);
	[[nodiscard]] bool Run(const Serialization::JsonValue &in_stRequest, const HostConfig &in_stConfig, ControllerResult &out_stResult);
	void Cancel() noexcept;
};

} // namespace EngineNext::AI
