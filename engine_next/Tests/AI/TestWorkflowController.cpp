/**************************************************************************/
/*  TestWorkflowController.cpp                                            */
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

#include "engine_next/Tests/TestFramework.h"
#include "engine_next/include/EngineNext/AI/ProcessTransport.h"
#include "engine_next/include/EngineNext/AI/WorkflowController.h"

#include <atomic>
#include <chrono>
#include <filesystem>
#include <thread>

namespace
{

using EngineNext::Serialization::JsonValue;

JsonValue Request()
{
	JsonValue::Object stEntity{
		{ "assets", JsonValue::List{} },
		{ "entity_id", std::int64_t(1) },
		{ "gameplay", JsonValue::Object{ { "kind", "static" } } },
		{ "name", "root" },
		{ "node_type", "Node3D" },
		{ "parent_entity_id", std::int64_t(0) },
		{ "transform", JsonValue::Object{
							   { "rotation_xyzw", JsonValue::List{ 0.0, 0.0, 0.0, 1.0 } },
							   { "scale", JsonValue::List{ 1.0, 1.0, 1.0 } },
							   { "translation", JsonValue::List{ 0.0, 0.0, 0.0 } },
					   } },
	};
	return JsonValue::Object{
		{ "asset_bindings", JsonValue::List{} },
		{ "graph", JsonValue::List{} },
		{ "manifest", JsonValue::Object{ { "artifacts", JsonValue::List{} }, { "schema_version", std::int64_t(1) } } },
		{ "model", JsonValue::Object{
						   { "model", "LOCAL IMPORT / COPY - NOT AI" },
						   { "model_version", "1" },
						   { "provider", "local-copy" },
						   { "provider_version", "1" },
				   } },
		{ "request_id", "cancel-test" },
		{ "scene_template", JsonValue::Object{
									{ "entities", JsonValue::List{ stEntity } },
									{ "scene_id", "cancel.scene" },
									{ "scene_revision", "r1" },
									{ "schema_version", std::int64_t(1) },
									{ "simulation", JsonValue::Object{ { "fixed_step_ms", std::int64_t(16) }, { "max_speed", 8.0 } } },
							} },
		{ "schema_version", std::int64_t(1) },
	};
}

class FakeTransport final : public EngineNext::AI::IProcessTransport
{
public:
	EngineNext::AI::WorkflowController *pController = nullptr;
	std::string strCancelOn;
	bool bCancelled = false;
	bool bCancelCommand = false;
	int nCreateCalls = 0;
	std::string strStepState = "succeeded";
	std::string strStatusState = "reconcile";

	bool Run(const EngineNext::AI::ProcessSpec &in_stSpec, EngineNext::AI::ProcessResult &out_stResult) override
	{
		std::string strCommand;
		for (const std::string &strArgument : in_stSpec.arrArguments)
		{
			if (strArgument == "create" || strArgument == "step" || strArgument == "status" || strArgument == "export" || strArgument == "cancel")
			{
				strCommand = strArgument;
			}
		}
		bCancelCommand = bCancelCommand || strCommand == "cancel";
		JsonValue stResult;
		if (strCommand == "create")
		{
			++nCreateCalls;
			stResult = JsonValue::Object{ { "run_id", "executor-run" } };
		}
		else if (strCommand == "status")
		{
			stResult = JsonValue::Object{
				{ "nodes", JsonValue::Object{ { "copy", JsonValue::Object{ { "provider_manifest", JsonValue::Object{
																										  { "id", "local-copy" },
																										  { "version", "1" },
																										  { "model", "LOCAL IMPORT / COPY - NOT AI" },
																										  { "model_version", "1" },
																								  } } } } } },
				{ "state", strStatusState },
			};
		}
		else if (strCommand == "step")
		{
			stResult = JsonValue::Object{
				{ "nodes", JsonValue::Object{ { "copy", JsonValue::Object{ { "provider_manifest", JsonValue::Object{
																										  { "id", "local-copy" },
																										  { "version", "1" },
																										  { "model", "LOCAL IMPORT / COPY - NOT AI" },
																										  { "model_version", "1" },
																								  } } } } } },
				{ "state", strStepState },
			};
		}
		else if (strCommand == "export")
		{
			stResult = JsonValue::Object{ { "manifest", JsonValue::Object{ { "artifacts", JsonValue::List{} } } }, { "outputs", JsonValue::Object{} } };
		}
		else
		{
			stResult = JsonValue::Object{ { "state", "cancelled" } };
		}
		out_stResult.bStarted = true;
		out_stResult.bExited = true;
		out_stResult.nExitCode = 0;
		(void)EngineNext::Serialization::CanonicalJson(JsonValue::Object{ { "ok", true }, { "result", stResult } }, out_stResult.strOutput);
		if (strCommand == strCancelOn)
		{
			pController->Cancel();
		}
		return true;
	}

	void Cancel() noexcept override
	{
		bCancelled = true;
	}
};

void CancelCase(const std::string &in_strTrigger)
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / ("M3Cancel-" + in_strTrigger);
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	FakeTransport stTransport;
	EngineNext::AI::WorkflowController stController(stTransport);
	stTransport.pController = &stController;
	stTransport.strCancelOn = in_strTrigger;
	EngineNext::AI::HostConfig stConfig;
	stConfig.strPython = "python";
	stConfig.strExecutorScript = "executor_cli.py";
	stConfig.strDatabase = (stRoot / "executor.sqlite").string();
	stConfig.strStatePath = (stRoot / "state.json").string();
	stConfig.strOutput = (stRoot / "scene.enpak").string();
	EngineNext::AI::ControllerResult stResult;
	ENGINE_NEXT_CHECK(!stController.Run(Request(), stConfig, stResult));
	ENGINE_NEXT_CHECK(stTransport.bCancelled);
	ENGINE_NEXT_CHECK(stTransport.bCancelCommand);
	ENGINE_NEXT_CHECK(stResult.bHasSnapshot);
	ENGINE_NEXT_CHECK(stResult.stSnapshot.GetObject()->at("state").GetString() != nullptr);
	ENGINE_NEXT_CHECK_EQ(*stResult.stSnapshot.GetObject()->at("state").GetString(), std::string("cancelled"));
	ENGINE_NEXT_CHECK(!fs::exists(stConfig.strOutput));
	fs::remove_all(stRoot);
}

} // namespace

ENGINE_NEXT_TEST("Workflow controller rejects late create and export after cancellation")
{
	CancelCase("create");
	CancelCase("export");
}

ENGINE_NEXT_TEST("Process transport reports a missing host without starting")
{
	EngineNext::AI::ProcessTransport stTransport;
	EngineNext::AI::ProcessSpec stSpec;
	stSpec.strExecutable = "/definitely/missing/m3-python";
	stSpec.nTimeoutMsec = 100;
	EngineNext::AI::ProcessResult stResult;
	ENGINE_NEXT_CHECK(!stTransport.Run(stSpec, stResult));
	ENGINE_NEXT_CHECK(!stResult.bStarted);
}

namespace
{

class AsyncTransport final : public EngineNext::AI::IProcessTransport
{
public:
	std::atomic<bool> bEntered{ false };
	std::atomic<bool> bCancelled{ false };

	bool Run(const EngineNext::AI::ProcessSpec &, EngineNext::AI::ProcessResult &out_stResult) override
	{
		bEntered = true;
		while (!bCancelled)
		{
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		}
		const JsonValue stResult = JsonValue::Object{ { "run_id", "executor-run" } };
		(void)EngineNext::Serialization::CanonicalJson(JsonValue::Object{ { "ok", true }, { "result", stResult } }, out_stResult.strOutput);
		out_stResult.bStarted = true;
		out_stResult.bExited = true;
		out_stResult.nExitCode = 0;
		return true;
	}

	void Cancel() noexcept override
	{
		bCancelled = true;
	}
};

} // namespace

ENGINE_NEXT_TEST("Workflow controller supports cancellation from another thread")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3AsyncCancel";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	AsyncTransport stTransport;
	EngineNext::AI::WorkflowController stController(stTransport);
	EngineNext::AI::HostConfig stConfig;
	stConfig.strPython = "python";
	stConfig.strExecutorScript = "executor_cli.py";
	stConfig.strDatabase = (stRoot / "executor.sqlite").string();
	stConfig.strStatePath = (stRoot / "state.json").string();
	stConfig.strOutput = (stRoot / "scene.enpak").string();
	EngineNext::AI::ControllerResult stResult;
	std::thread stThread([&]()
						 { (void)stController.Run(Request(), stConfig, stResult); });
	while (!stTransport.bEntered)
	{
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	stController.Cancel();
	stThread.join();
	ENGINE_NEXT_CHECK(stResult.bHasSnapshot);
	ENGINE_NEXT_CHECK_EQ(*stResult.stSnapshot.GetObject()->at("state").GetString(), std::string("cancelled"));
	ENGINE_NEXT_CHECK(!fs::exists(stConfig.strOutput));
	fs::remove_all(stRoot);
}

ENGINE_NEXT_TEST("Workflow resume rejects a changed model bound to the same request")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3TamperResume";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	FakeTransport stTransport;
	stTransport.strStepState = "running";
	EngineNext::AI::WorkflowController stController(stTransport);
	EngineNext::AI::HostConfig stConfig;
	stConfig.strPython = "python";
	stConfig.strExecutorScript = "executor_cli.py";
	stConfig.strDatabase = (stRoot / "executor.sqlite").string();
	stConfig.strStatePath = (stRoot / "state.json").string();
	stConfig.strOutput = (stRoot / "scene.enpak").string();
	stConfig.nMaxSteps = 1;
	JsonValue stRequest = Request();
	EngineNext::AI::ControllerResult stResult;
	ENGINE_NEXT_CHECK(!stController.Run(stRequest, stConfig, stResult));
	ENGINE_NEXT_CHECK_EQ(stTransport.nCreateCalls, 1);
	stRequest.GetObject()->at("model").GetObject()->at("model") = "changed-model";
	stConfig.bResume = true;
	stConfig.nMaxSteps = 0;
	ENGINE_NEXT_CHECK(!stController.Run(stRequest, stConfig, stResult));
	ENGINE_NEXT_CHECK_EQ(stTransport.nCreateCalls, 1);
	bool bIdentityFailure = false;
	for (const EngineNext::Assets::Diagnostic &stDiagnostic : stResult.arrDiagnostics)
	{
		bIdentityFailure = bIdentityFailure || stDiagnostic.strCode == "state_identity";
	}
	ENGINE_NEXT_CHECK(bIdentityFailure);
	ENGINE_NEXT_CHECK(!fs::exists(stConfig.strOutput));
	fs::remove_all(stRoot);
}

ENGINE_NEXT_TEST("Workflow resume accepts reconcile followed by immediate success")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3ReconcileSuccess";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	FakeTransport stTransport;
	stTransport.strStepState = "running";
	EngineNext::AI::WorkflowController stController(stTransport);
	EngineNext::AI::HostConfig stConfig;
	stConfig.strPython = "python";
	stConfig.strExecutorScript = "executor_cli.py";
	stConfig.strDatabase = (stRoot / "executor.sqlite").string();
	stConfig.strStatePath = (stRoot / "state.json").string();
	stConfig.strOutput = (stRoot / "scene.enpak").string();
	stConfig.nMaxSteps = 1;
	EngineNext::AI::ControllerResult stResult;
	ENGINE_NEXT_CHECK(!stController.Run(Request(), stConfig, stResult));
	stTransport.strStepState = "succeeded";
	stConfig.bResume = true;
	stConfig.nMaxSteps = 0;
	ENGINE_NEXT_CHECK(stController.Run(Request(), stConfig, stResult));
	ENGINE_NEXT_CHECK(stResult.bHasSnapshot);
	ENGINE_NEXT_CHECK_EQ(*stResult.stSnapshot.GetObject()->at("state").GetString(), std::string("succeeded"));
	ENGINE_NEXT_CHECK(fs::exists(stConfig.strOutput));
	fs::remove_all(stRoot);
}
