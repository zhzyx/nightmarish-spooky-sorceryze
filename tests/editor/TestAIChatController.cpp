/**************************************************************************/
/*  AIChatController                                                      */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                     */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#include "tests/test_macros.h"
TEST_FORCE_LINK(TestAIChatController)

#ifdef TOOLS_ENABLED
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "editor/AIWorkflowRuntime.h"
#include "editor/docks/AIChatController.h"

namespace TestAIChatController
{
Dictionary MakeRequest(const String &strIdentity)
{
	Dictionary mapModel;
	mapModel["id"] = "fixture-model";
	mapModel["reasoning_effort"] = "high";
	Dictionary mapBinding;
	mapBinding["session_id"] = strIdentity;
	Dictionary mapRequest;
	mapRequest["workflow"] = "ai_chat";
	mapRequest["scope"] = strIdentity;
	mapRequest["request_id"] = "turn-1";
	mapRequest["model"] = mapModel;
	mapRequest["binding"] = mapBinding;
	mapRequest["input"] = Dictionary();
	return mapRequest;
}

PackedByteArray ResponseBytes(const String &strJson)
{
	return strJson.to_utf8_buffer();
}

TEST_CASE("[AIChatController] Runs freeze selection and rebuilt observers never resubmit or cancel")
{
	AIWorkflowRuntime stFallbackRuntime;
	Ref<AIChatController> refController;
	refController.instantiate();
	Dictionary mapRequest = MakeRequest("controller-frozen");
	const Dictionary mapStarted = refController->BeginRun(mapRequest);
	REQUIRE(bool(mapStarted["ok"]));
	const Dictionary mapStartedSnapshot = mapStarted["snapshot"];
	Dictionary mapMutableModel = mapRequest["model"];
	mapMutableModel["id"] = "changed-model";
	CHECK(refController->GetFrozenModel()["id"] == "fixture-model");
	{
		Ref<AIChatController> refObserver;
		refObserver.instantiate();
		const Dictionary mapObserved = refObserver->AttachRun(mapStartedSnapshot["run_id"]);
		REQUIRE(bool(mapObserved["ok"]));
		CHECK(Dictionary(mapObserved["snapshot"])["sequence"] == mapStartedSnapshot["sequence"]);
	}
	CHECK(Dictionary(refController->QueryRun()["snapshot"])["state"] == "running");
	CHECK(Dictionary(refController->QueryRun()["snapshot"])["sequence"] == mapStartedSnapshot["sequence"]);
	refController->PublishState("awaiting_tool", "waiting_tool");
	CHECK(Dictionary(refController->QueryRun()["snapshot"])["state"] == "waiting_tool");
	refController->PublishState("approval", "waiting_confirmation");
	CHECK(Dictionary(refController->QueryRun()["snapshot"])["state"] == "waiting_confirmation");
	refController->FinishRun(true);
	CHECK(Dictionary(refController->QueryRun()["snapshot"])["state"] == "succeeded");
}

TEST_CASE("[AIChatController] Cancellation rejects late transport generations and isolates other sessions")
{
	AIWorkflowRuntime stFallbackRuntime;
	Ref<AIChatController> refFirst;
	Ref<AIChatController> refSecond;
	refFirst.instantiate();
	refSecond.instantiate();
	REQUIRE(bool(refFirst->BeginRun(MakeRequest("controller-first"))["ok"]));
	REQUIRE(bool(refSecond->BeginRun(MakeRequest("controller-second"))["ok"]));
	refFirst->GetSession().bBusy = true;
	refFirst->GetSession().nRequestGeneration = 10;
	CHECK(refFirst->Accepts(10));
	refFirst->Cancel();
	CHECK_FALSE(refFirst->Accepts(10));
	CHECK_FALSE(refFirst->GetSession().bBusy);
	CHECK(Dictionary(refFirst->QueryRun()["snapshot"])["state"] == "cancelled");
	CHECK(Dictionary(refSecond->QueryRun()["snapshot"])["state"] == "running");
}

TEST_CASE("[AIChatController] Responses decoding and tool continuation retain IDs and enforce live permission")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	const PackedByteArray arrBody = ResponseBytes(R"({"status":"completed","output":[{"type":"function_call","call_id":"call-1","name":"read_file","arguments":"{\"path\":\"a.txt\"}"}]})");
	const Dictionary mapResponse = refController->DecodeResponse(arrBody, 3, true);
	REQUIRE(bool(mapResponse["ok"]));
	AIChatController::Session &stSession = refController->GetSession();
	stSession.arrToolCalls = mapResponse["tool_calls"];
	stSession.bBusy = true;
	stSession.nSessionGeneration = 7;
	CHECK_FALSE(bool(refController->PrepareTool(6, 0, true, true)["ok"]));
	CHECK_FALSE(bool(refController->PrepareTool(7, 0, false, true)["ok"]));
	const Dictionary mapTool = refController->PrepareTool(7, 0, true, true);
	REQUIRE(bool(mapTool["ok"]));
	CHECK(mapTool["name"] == "read_file");
	CHECK(Dictionary(mapTool["arguments"])["path"] == "a.txt");
	REQUIRE(refController->AppendToolResult("contents", true, 1));
	CHECK(Dictionary(stSession.arrMessages[0])["tool_call_id"] == "call-1");
	CHECK(bool(Dictionary(stSession.arrMessages[0])["godot_file_success"]));
	CHECK_FALSE(refController->AdvanceTool(6));
	CHECK(stSession.nToolIndex == 0);
	CHECK(refController->AdvanceTool(7));
	CHECK(stSession.nToolIndex == 1);
	CHECK_FALSE(refController->AdvanceTool(7));
}

TEST_CASE("[AIChatController] Malformed duplicate and unauthorized tool batches cannot enter execution")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	const PackedByteArray arrDuplicate = ResponseBytes(R"({"choices":[{"message":{"tool_calls":[{"id":"same","type":"function","function":{"name":"read_file","arguments":"{}"}},{"id":"same","type":"function","function":{"name":"read_file","arguments":"{}"}}]}}]})");
	CHECK(refController->DecodeResponse(arrDuplicate, 0, true)["error"] == "malformed_tool_call");
	const PackedByteArray arrCall = ResponseBytes(R"({"choices":[{"message":{"tool_calls":[{"id":"one","type":"function","function":{"name":"write_file","arguments":"{}"}}]}}]})");
	CHECK(refController->DecodeResponse(arrCall, 0, false)["error"] == "tools_disabled");
	const Dictionary mapResponse = refController->DecodeResponse(arrCall, 0, true);
	REQUIRE(bool(mapResponse["ok"]));
	refController->GetSession().arrToolCalls = mapResponse["tool_calls"];
	refController->GetSession().bBusy = true;
	CHECK_FALSE(bool(refController->PrepareTool(0, 0, true, true)["ok"]));
}

TEST_CASE("[AIChatController] CLI request storage survives until explicit release and cleans cancellation")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	REQUIRE(refController->StoreCliRequest("{\"messages\":[]}") == OK);
	const String strPath = refController->GetSession().strCliInputPath;
	CHECK(FileAccess::exists(strPath));
	CHECK(FileAccess::get_file_as_string(strPath) == "{\"messages\":[]}");
	refController->Cancel();
	CHECK_FALSE(FileAccess::exists(strPath));
	CHECK(refController->GetSession().strCliInputPath.is_empty());
}
TEST_CASE("[AIChatController] Checkpoint restore preserves pending cursor without launching or replaying")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	Dictionary mapCheckpoint = JSON::parse_string(R"({"messages":[{"role":"user","content":"read file"},{"role":"assistant","content":"","tool_calls":[{"id":"call-r","type":"function","function":{"name":"read_file","arguments":"{}"}}]}],"tool_calls":[{"id":"call-r","type":"function","function":{"name":"read_file","arguments":"{}"}}],"tool_index":0,"tool_rounds":2})");
	REQUIRE(refController->RestoreCheckpoint(mapCheckpoint));
	CHECK(refController->GetSession().nCliProcessId == -1);
	CHECK_FALSE(refController->GetSession().bBusy);
	CHECK(refController->GetSession().nRequestGeneration == 0);
	CHECK(refController->GetSession().nToolRounds == 2);
	CHECK(refController->GetSession().nToolIndex == 0);
	mapCheckpoint["tool_index"] = 9;
	CHECK_FALSE(refController->RestoreCheckpoint(mapCheckpoint));
	CHECK(refController->GetSession().nToolIndex == 0);
	const Dictionary mapCaptured = refController->CaptureCheckpoint();
	Array(mapCaptured["messages"]).clear();
	CHECK(refController->GetSession().arrMessages.size() == 2);
}

TEST_CASE("[AIChatController] Credentials and native authorization never enter checkpoints or run snapshots")
{
	AIWorkflowRuntime stFallbackRuntime;
	Ref<AIChatController> refController;
	refController.instantiate();
	REQUIRE(bool(refController->BeginRun(MakeRequest("controller-private-state"))["ok"]));
	refController->GetSession().strRequestKey = "private-fixture-credential";
	const String strCheckpoint = JSON::stringify(refController->CaptureCheckpoint());
	const String strSnapshot = JSON::stringify(refController->QueryRun());
	CHECK_FALSE(strCheckpoint.contains("private-fixture-credential"));
	CHECK_FALSE(strSnapshot.contains("private-fixture-credential"));
	CHECK(refController->RedactText("private-fixture-credential current-fixture", "current-fixture") == "[REDACTED] [REDACTED]");
	CHECK(refController->PollReceiptFlush("").is_empty());
	String strError;
	CHECK_FALSE(refController->RecordWorkOrderEvent("step", "fixture", "running", "", "", strError));
	CHECK(strError == "reporting_binding_missing");
}

TEST_CASE("[AIChatController] Request preparation preserves stored images and read-only policy without a View")
{
	AIWorkflowRuntime stFallbackRuntime;
	Ref<AIChatController> refController;
	refController.instantiate();
	REQUIRE(bool(refController->BeginRun(MakeRequest("controller-payload"))["ok"]));
	Dictionary mapImage;
	mapImage["mime_type"] = "image/png";
	mapImage["data"] = "AA==";
	Array arrImages;
	arrImages.push_back(mapImage);
	Dictionary mapMessage = AIChatController::MakeMessage("user", "inspect this image");
	mapMessage["images"] = arrImages;
	mapMessage["consultation_only"] = true;
	mapMessage["steering_snapshot"] = "local-snapshot";
	refController->GetSession().arrMessages.push_back(mapMessage);
	refController->GetSession().bConsultationTurn = true;
	Dictionary mapPolicy;
	mapPolicy["tools_allowed"] = true;
	mapPolicy["auto_apply"] = true;
	mapPolicy["auto_execute"] = true;
	Dictionary mapScope;
	mapScope["project_root"] = "/fixture/project";
	Array arrPrepared;
	Dictionary mapStats;
	REQUIRE(refController->BuildModelMessages(mapScope, mapPolicy, 0, arrPrepared, mapStats));
	CHECK(String(Dictionary(arrPrepared[0])["content"]).contains("read-only code consultant"));
	CHECK(bool(refController->BuildToolPolicy(mapPolicy)["file_changes_require_approval"]));
	CHECK(bool(refController->BuildToolPolicy(mapPolicy)["execution_requires_approval"]));
	Array arrTools;
	for (const String &strName : { String("read_file"), String("write_file"), String("get_parent_context") })
	{
		Dictionary mapFunction;
		mapFunction["name"] = strName;
		Dictionary mapTool;
		mapTool["type"] = "function";
		mapTool["function"] = mapFunction;
		arrTools.push_back(mapTool);
	}
	const Dictionary mapPayload = refController->BuildHttpPayload(arrPrepared, arrTools, mapPolicy, 0);
	CHECK(mapPayload["model"] == "fixture-model");
	CHECK(Array(mapPayload["tools"]).size() == 1);
	const Dictionary mapSentMessage = Array(mapPayload["messages"])[1];
	CHECK(mapSentMessage["content"].get_type() == Variant::ARRAY);
	CHECK_FALSE(mapSentMessage.has("images"));
	CHECK_FALSE(mapSentMessage.has("steering_snapshot"));
	CHECK(Dictionary(refController->GetSession().arrMessages[0]).has("images"));
	CHECK(Dictionary(refController->GetSession().arrMessages[0]).has("steering_snapshot"));
	CHECK(Dictionary(arrPrepared[1]).has("images"));
	const Dictionary mapResponses = refController->BuildHttpPayload(arrPrepared, arrTools, mapPolicy, 3);
	CHECK(mapResponses.has("input"));
	CHECK_FALSE(mapResponses.has("messages"));
	CHECK(Dictionary(mapResponses["reasoning"])["effort"] == "high");
}

TEST_CASE("[AIChatController] Native grants remain ephemeral and bind exact task epoch")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	Dictionary mapScope;
	mapScope["project"] = "/fixture/project";
	mapScope["conversation"] = "fixture-conversation";
	mapScope["issue"] = 1211;
	mapScope["request"] = "fixture-request";
	mapScope["generation"] = 1;
	Dictionary mapPolicy;
	mapPolicy["tools_allowed"] = true;
	Dictionary mapArguments;
	mapArguments["action"] = "scene_create_node";
	REQUIRE(refController->GrantNativeTask(mapScope, mapPolicy));
	CHECK_FALSE(refController->AllowsNativeTask(mapScope, mapPolicy, "editor_action", mapArguments));
	refController->GetSession().nTaskNativeRequestEpoch = refController->GetSession().nTaskNativeEpoch;
	CHECK(refController->AllowsNativeTask(mapScope, mapPolicy, "editor_action", mapArguments));
	mapPolicy["consultation_only"] = true;
	CHECK_FALSE(refController->AllowsNativeTask(mapScope, mapPolicy, "editor_action", mapArguments));
	CHECK_FALSE(refController->GrantNativeTask(mapScope, mapPolicy));
	CHECK_FALSE(refController->GetSession().stTaskNativeGrant.matches(mapScope));
	mapPolicy["consultation_only"] = false;
	REQUIRE(refController->GrantNativeTask(mapScope, mapPolicy));
	refController->GetSession().nTaskNativeRequestEpoch = refController->GetSession().nTaskNativeEpoch;
	mapScope["request"] = "another-request";
	CHECK_FALSE(refController->AllowsNativeTask(mapScope, mapPolicy, "editor_action", mapArguments));
}

TEST_CASE("[AIChatController] Turn submission response and steering execute without a View")
{
	AIWorkflowRuntime stFallbackRuntime;
	Ref<AIChatController> refController;
	refController.instantiate();
	Dictionary mapContext;
	mapContext["workspace"] = "/fixture/project";
	mapContext["model"] = MakeRequest("unused")["model"];
	mapContext["tools_allowed"] = true;
	Dictionary mapMessage = AIChatController::MakeMessage("user", "original task");
	const Dictionary mapStarted = refController->StartTurn(mapMessage, mapContext, String());
	REQUIRE(bool(mapStarted["ok"]));
	CHECK(refController->HasActiveRun());
	CHECK(refController->GetSession().nSessionGeneration == 1);
	CHECK(refController->GetSession().arrMessages.size() == 1);
	const String strRunId = Dictionary(mapStarted["snapshot"])["run_id"];
	CHECK_FALSE(bool(refController->StartTurn(mapMessage, mapContext, String())["ok"]));
	CHECK(Dictionary(refController->QueryRun()["snapshot"])["run_id"] == strRunId);
	Dictionary mapSteering = AIChatController::MakeMessage("user", "additional scope");
	mapSteering["steering"] = true;
	mapSteering["steering_snapshot"] = refController->GetSession().strSnapshotId;
	mapSteering["consultation_only"] = false;
	refController->GetSession().arrQueuedMessages.push_back(mapSteering);
	const PackedByteArray arrBody = ResponseBytes(R"({"choices":[{"message":{"content":"old answer"},"finish_reason":"stop"}]})");
	const uint64_t nGeneration = refController->GetSession().nRequestGeneration;
	const Dictionary mapSuperseded = refController->ConsumeModelResponse(0, 200, arrBody, nGeneration, 0, true, String());
	CHECK(mapSuperseded["action"] == "steering");
	CHECK_FALSE(bool(mapSuperseded["present_content"]));
	CHECK(refController->GetSession().arrMessages.size() == 1);
	CHECK(refController->ApplyPendingSteering(0).size() == 1);
	CHECK(refController->GetSession().arrMessages.size() == 2);
	CHECK_FALSE(refController->HasPendingSteering());
	const Dictionary mapCompleted = refController->ConsumeModelResponse(0, 200, arrBody, nGeneration, 0, true, String());
	CHECK(mapCompleted["action"] == "final");
	CHECK(bool(mapCompleted["complete"]));
	CHECK(refController->GetSession().arrMessages.size() == 3);
	refController->Cancel();
	CHECK(refController->ConsumeModelResponse(0, 200, arrBody, nGeneration, 0, true, String())["action"] == "ignore");
	CHECK(refController->GetSession().arrMessages.size() == 3);
}

TEST_CASE("[AIChatController] Read batching retains cursor until receipt publication")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	refController->GetSession().bBusy = true;
	Array arrCalls;
	for (int nIndex = 0; nIndex < 3; nIndex++)
	{
		Dictionary mapFunction;
		mapFunction["name"] = nIndex < 2 ? "read_file" : "run_command";
		mapFunction["arguments"] = "{}";
		Dictionary mapCall;
		mapCall["id"] = itos(nIndex);
		mapCall["function"] = mapFunction;
		arrCalls.push_back(mapCall);
	}
	refController->BeginToolBatch(arrCalls, String());
	CHECK(refController->PlanNextTool(0) == "read_batch");
	CHECK(refController->GetSession().nReadBatchCount == 2);
	CHECK(refController->GetSession().nToolIndex == 0);
	CHECK(refController->PlanNextTool(1) == "ignore");
	refController->GetSession().bConsultationTurn = true;
	refController->GetSession().nReadBatchCount = 0;
	CHECK(refController->PlanNextTool(0) == "tool");
	refController->Cancel();
	CHECK(refController->PlanNextTool(0) == "ignore");
}

#ifdef UNIX_ENABLED
class CliObserver : public Object
{
public:
	int nCompletions = 0;
	int nExitCode = -999;
	PackedByteArray arrBody;
	bool bTimeout = false;
	bool bTruncated = false;

	void Completed(const PackedByteArray &arrResult, int nCode, bool bTimedOut, bool bOutputTruncated, uint64_t nGeneration)
	{
		(void)nGeneration;
		nCompletions++;
		nExitCode = nCode;
		arrBody = arrResult;
		bTimeout = bTimedOut;
		bTruncated = bOutputTruncated;
	}
};

TEST_CASE("[AIChatController] Standalone CLI worker waits for actual exit and rejects nonzero final status")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	CliObserver stObserver;
	refController->connect("cli_completed", callable_mp(&stObserver, &CliObserver::Completed));
	List<String> arrArguments;
	arrArguments.push_back("-c");
	arrArguments.push_back(R"(printf '%s\n' '{"choices":[{"message":{"content":"fixture"},"finish_reason":"stop"}]}'; sleep 0.02; exit 7)");
	REQUIRE(refController->StartCliProcess("/bin/sh", arrArguments, false, true) == OK);
	refController->GetSession().bBusy = true;
	refController->BeginCliResponse();
	const uint64_t nDeadline = OS::get_singleton()->get_ticks_msec() + 3000;
	while (stObserver.nCompletions == 0 && OS::get_singleton()->get_ticks_msec() < nDeadline)
	{
		refController->PollCli();
		OS::get_singleton()->delay_usec(1000);
	}
	CHECK(stObserver.nCompletions == 1);
	CHECK(stObserver.nExitCode == 7);
	CHECK_FALSE(stObserver.bTimeout);
	CHECK_FALSE(stObserver.bTruncated);
	CHECK(refController->GetSession().nCliProcessId == -1);
	CHECK(String::utf8(reinterpret_cast<const char *>(stObserver.arrBody.ptr()), stObserver.arrBody.size()).contains("fixture"));
}

TEST_CASE("[AIChatController] Standalone CLI cancellation cannot deliver a later completion")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	CliObserver stObserver;
	refController->connect("cli_completed", callable_mp(&stObserver, &CliObserver::Completed));
	List<String> arrArguments;
	arrArguments.push_back("-c");
	arrArguments.push_back("sleep 0.02; printf '{}'");
	REQUIRE(refController->StartCliProcess("/bin/sh", arrArguments, false, true) == OK);
	refController->GetSession().bBusy = true;
	refController->BeginCliResponse();
	const uint64_t nGeneration = refController->GetSession().nCliGeneration;
	refController->Cancel();
	OS::get_singleton()->delay_usec(30000);
	refController->PollCli();
	CHECK(stObserver.nCompletions == 0);
	CHECK_FALSE(refController->Accepts(nGeneration));
	CHECK(refController->GetSession().nCliProcessId == -1);
}
TEST_CASE("[AIChatController] Authorized command transport owns both output streams and actual exit")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	List<String> arrArguments;
	arrArguments.push_back("-c");
	arrArguments.push_back("printf 'fixture-out'; printf 'fixture-error' >&2; exit 3");
	REQUIRE(refController->StartCommand("/bin/sh", arrArguments) == OK);
	Dictionary mapResult;
	const uint64_t nDeadline = OS::get_singleton()->get_ticks_msec() + 3000;
	while (mapResult.is_empty() && OS::get_singleton()->get_ticks_msec() < nDeadline)
	{
		mapResult = refController->PollCommand();
		OS::get_singleton()->delay_usec(1000);
	}
	REQUIRE_FALSE(mapResult.is_empty());
	CHECK(int(mapResult["exit_code"]) == 3);
	CHECK(mapResult["stdout"] == "fixture-out");
	CHECK(mapResult["stderr"] == "fixture-error");
	CHECK_FALSE(bool(mapResult["timed_out"]));
	CHECK(refController->GetSession().nCommandProcessId == -1);
}

#endif

}
#endif
