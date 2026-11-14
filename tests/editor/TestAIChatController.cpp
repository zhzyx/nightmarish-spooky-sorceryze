/**************************************************************************/
/*  TestAIChatController.cpp                                              */
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

// Preserve CPP_CODING_STANDARD.md v1.1 Allman style during formatter transition.
// clang-format off
#include "tests/test_macros.h"
TEST_FORCE_LINK(TestAIChatController)

#ifdef TOOLS_ENABLED
#include "editor/docks/AIChatController.h"

namespace TestAIChatController
{
TEST_CASE("[AIChat][AICore] Controller freezes model and binding per run")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	Dictionary mapModel;
	mapModel["id"] = "initial-model";
	Dictionary mapBinding;
	mapBinding["issue"] = 1086;
	refController->BeginRun("conversation", "request", mapModel, mapBinding);
	REQUIRE(refController->IsRunning());
	mapModel["id"] = "changed-model";
	mapBinding["issue"] = 0;
	const Dictionary mapSnapshot = refController->GetSnapshot();
	CHECK(Dictionary(mapSnapshot["model"])["id"] == "initial-model");
	CHECK(int(Dictionary(mapSnapshot["binding"])["issue"]) == 1086);
	refController->Publish("tool_requested");
	CHECK(refController->GetSnapshot()["state"] == "waiting_tool");
	refController->Publish("progress", Dictionary(), "running");
	CHECK(refController->GetSnapshot()["state"] == "running");
	refController->FinishRun(true);
	CHECK_FALSE(refController->IsRunning());
	CHECK(refController->GetSnapshot()["state"] == "succeeded");
}

TEST_CASE("[AIChat][AICore] Controller cancellation rejects stale request generations")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	refController->BeginRun("conversation", "request", Dictionary(), Dictionary());
	const uint64_t nFirst = refController->AdvanceRequestGeneration();
	REQUIRE(refController->IsCurrentRequest(nFirst));
	refController->RequestCancel();
	CHECK_FALSE(refController->IsCurrentRequest(nFirst));
	// Domain cleanup observes the active run until it commits the terminal event.
	CHECK(refController->IsRunning());
	refController->FinishRun(false);
	CHECK(refController->GetSnapshot()["state"] == "cancelled");
	CHECK(refController->Publish("progress").is_empty());
	refController->BeginRun("conversation", "request", Dictionary(), Dictionary());
	CHECK(refController->IsRunning());
	CHECK_FALSE(refController->IsCurrentRequest(nFirst));
	CHECK(refController->GetSnapshot()["run_id"] != String());
}

TEST_CASE("[AIChat][AICore] Controllers isolate session data and run state")
{
	Ref<AIChatController> refFirst;
	Ref<AIChatController> refSecond;
	refFirst.instantiate();
	refSecond.instantiate();
	refFirst->BeginRun("conversation", "request", Dictionary(), Dictionary());
	refSecond->BeginRun("conversation", "request", Dictionary(), Dictionary());
	refFirst->GetSession().arrMessages.push_back("first history");
	refFirst->GetTurn().nToolIndex = 2;
	CHECK(refSecond->GetSession().arrMessages.is_empty());
	CHECK(refSecond->GetTurn().nToolIndex == 0);
	CHECK(refFirst->GetSnapshot()["run_id"] != refSecond->GetSnapshot()["run_id"]);
	refFirst->CancelRun();
	CHECK_FALSE(refFirst->IsRunning());
	CHECK(refSecond->IsRunning());
}

TEST_CASE("[AIChat][AICore] Active session input snapshots are detached")
{
	Ref<AIChatController> refController;
	refController.instantiate();
	AIChatSessionData &stSession = refController->GetSession();
	stSession.strModel = "api-model";
	stSession.strCliModel = "cli-model";
	stSession.strCodexModel = "codex-model";
	stSession.nBackend = 2;
	stSession.strDraft = "pending message";
	stSession.mapReasoningPreferences["2:codex-model"] = "high";
	Dictionary mapSnapshot = refController->GetSessionSnapshot();
	CHECK(String(mapSnapshot["model"]) == "api-model");
	CHECK(String(mapSnapshot["cli_model"]) == "cli-model");
	CHECK(String(mapSnapshot["codex_model"]) == "codex-model");
	CHECK(int(mapSnapshot["backend"]) == 2);
	CHECK(String(mapSnapshot["draft"]) == "pending message");
	Dictionary mapPreferences = mapSnapshot["reasoning_preferences"];
	mapPreferences["2:codex-model"] = "low";
	CHECK(String(stSession.mapReasoningPreferences["2:codex-model"]) == "high");
}
}
#endif
// clang-format on
