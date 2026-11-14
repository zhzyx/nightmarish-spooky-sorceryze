/**************************************************************************/
/*  TestAIWorkflowRuntime.cpp                                             */
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

#include "tests/test_macros.h"
TEST_FORCE_LINK(TestAIWorkflowRuntime)

#ifdef TOOLS_ENABLED
#include "core/object/callable_mp.h"
#include "core/string/string_name.h"
#include "core/variant/array.h"

#include "modules/ai_core/AIWorkflowRuntime.h"

// Preserve the project Allman convention during formatter migration.
// clang-format off
namespace TestAIWorkflowRuntime
{
class ReentrantObserver : public RefCounted
{
public:
	AIWorkflowRuntime *pRuntime = nullptr;
	Ref<AIWorkflowRuntime> *pExternalReference = nullptr;
	bool bCancelStarted = false;

	void OnEvent(Dictionary dictEvent)
	{
		if (bCancelStarted && dictEvent["kind"] == "run_started")
		{
			pRuntime->Cancel(dictEvent["run_id"]);
		}
		Dictionary dictPayload = dictEvent["payload"];
		dictPayload["text"] = "listener mutation";
		if (pExternalReference != nullptr)
		{
			pExternalReference->unref();
		}
	}
};

TEST_CASE("[AIChat][AICore] Run identity freezes model and source binding")
{
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	Dictionary dictModel;
	dictModel["model"] = "model-a";
	Dictionary dictBinding;
	dictBinding["revision"] = "revision-a";
	const Dictionary dictRun = refRuntime->BeginRun("chat", "session-a", "request-a", dictModel, dictBinding);
	REQUIRE_FALSE(dictRun.is_empty());
	CHECK(int64_t(dictRun["schema_version"]) == 1);
	CHECK(int64_t(dictRun["sequence"]) == 1);
	CHECK(refRuntime->BeginRun("chat", "session-a", "request-a", dictModel, dictBinding) == dictRun);
	dictModel["model"] = "model-b";
	CHECK(refRuntime->BeginRun("chat", "session-a", "request-a", dictModel, dictBinding).is_empty());
	const Dictionary dictSnapshot = refRuntime->Snapshot(dictRun["run_id"]);
	CHECK(Dictionary(dictSnapshot["model"])["model"] == "model-a");
	CHECK_FALSE(refRuntime->BeginRun("chat", "session-b", "request-a", dictModel, dictBinding).is_empty());
}

TEST_CASE("[AIChat][AICore] Cancellation rejects late data and preserves other runs")
{
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	const Dictionary dictFirst = refRuntime->BeginRun("chat", "a", "request");
	const Dictionary dictSecond = refRuntime->BeginRun("maliang", "b", "request");
	Dictionary dictDelta;
	dictDelta["text"] = "first";
	CHECK_FALSE(refRuntime->Publish(dictFirst["run_id"], dictFirst["generation"], "text_delta", dictDelta).is_empty());
	CHECK(refRuntime->Cancel(dictFirst["run_id"])["state"] == "cancelled");
	CHECK(refRuntime->Publish(dictFirst["run_id"], dictFirst["generation"], "completed").is_empty());
	CHECK(refRuntime->Publish(dictFirst["run_id"], dictFirst["generation"], "text_delta", dictDelta).is_empty());
	CHECK(refRuntime->Cancel(dictFirst["run_id"]).is_empty());
	CHECK(refRuntime->Snapshot(dictFirst["run_id"])["text"] == "first");
	CHECK(refRuntime->Snapshot(dictSecond["run_id"])["state"] == "running");
	CHECK_FALSE(refRuntime->Publish(dictSecond["run_id"], dictSecond["generation"], "completed").is_empty());
}

TEST_CASE("[AIChat][AICore] Tool waiting and completion follow one sequenced runtime")
{
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	const Dictionary dictRun = refRuntime->BeginRun("tianshu", "issue-1", "turn-1");
	const String strRun = dictRun["run_id"];
	const int64_t nGeneration = dictRun["generation"];
	CHECK(refRuntime->Publish(strRun, nGeneration, "unknown").is_empty());
	CHECK(int64_t(refRuntime->Snapshot(strRun)["sequence"]) == 1);
	CHECK(refRuntime->Publish(strRun, nGeneration + 1, "progress").is_empty());
	CHECK(refRuntime->Publish(strRun, nGeneration, "progress", Dictionary(), "succeeded").is_empty());
	Dictionary dictTool;
	dictTool["name"] = "inspect";
	CHECK(refRuntime->Publish(strRun, nGeneration, "tool_requested", dictTool)["state"] == "waiting_tool");
	CHECK(int64_t(refRuntime->Publish(strRun, nGeneration, "progress", Dictionary(), "running")["sequence"]) == 3);
	Dictionary dictArtifact;
	dictArtifact["id"] = "result";
	dictArtifact["revision"] = "r1";
	CHECK(int64_t(refRuntime->Publish(strRun, nGeneration, "artifact_ready", dictArtifact)["sequence"]) == 4);
	CHECK(refRuntime->Publish(strRun, nGeneration, "completed")["state"] == "succeeded");
	CHECK(refRuntime->Publish(strRun, nGeneration, "completed").is_empty());
	const Dictionary dictSnapshot = refRuntime->Snapshot(strRun);
	CHECK(Array(dictSnapshot["artifacts"]).size() == 1);
	CHECK(Array(dictSnapshot["tool_requests"]).size() == 1);
}

TEST_CASE("[AIChat][AICore] Snapshots accept portable data and isolate mutable readers")
{
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	Dictionary dictInvalid;
	dictInvalid["object"] = refRuntime;
	CHECK(refRuntime->BeginRun("chat", "a", "bad", dictInvalid).is_empty());
	Dictionary dictModel;
	dictModel["model"] = "a";
	Dictionary dictRun = refRuntime->BeginRun("chat", "a", "good", dictModel);
	Dictionary dictViewModel = dictRun["model"];
	dictViewModel["model"] = "view mutation";
	CHECK(Dictionary(refRuntime->Snapshot(dictRun["run_id"])["model"])["model"] == "a");
	CHECK(refRuntime->Publish(dictRun["run_id"], dictRun["generation"], "progress", dictInvalid).is_empty());
	CHECK(refRuntime->Publish(dictRun["run_id"], dictRun["generation"], "text_delta").is_empty());
	CHECK(int64_t(refRuntime->Snapshot(dictRun["run_id"])["sequence"]) == 1);
}

TEST_CASE("[AIChat][AICore] Synchronous observers cannot corrupt returned events")
{
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	Ref<ReentrantObserver> refObserver;
	refObserver.instantiate();
	refObserver->pRuntime = refRuntime.ptr();
	const Callable fnObserver = callable_mp(refObserver.ptr(), &ReentrantObserver::OnEvent);
	refRuntime->connect("event_received", fnObserver);
	const Dictionary dictRun = refRuntime->BeginRun("chat", "a", "first");
	Dictionary dictPayload;
	dictPayload["text"] = "original";
	const Dictionary dictEvent = refRuntime->Publish(dictRun["run_id"], dictRun["generation"], "text_delta", dictPayload);
	CHECK(Dictionary(dictEvent["payload"])["text"] == "original");
	CHECK(refRuntime->Snapshot(dictRun["run_id"])["text"] == "original");
	refObserver->bCancelStarted = true;
	const Dictionary dictCancelled = refRuntime->BeginRun("chat", "a", "second");
	CHECK(dictCancelled["state"] == "cancelled");
	CHECK(refRuntime->Snapshot(dictCancelled["run_id"])["state"] == "cancelled");
	refRuntime->disconnect("event_received", fnObserver);
}

TEST_CASE("[AIChat][AICore] Godot names normalize to portable strings")
{
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	Dictionary dictModel;
	dictModel[StringName("model")] = StringName("named-model");
	Dictionary dictBinding;
	dictBinding[StringName("parameters")] = dictModel;
	const Dictionary dictRun = refRuntime->BeginRun("chat", "names", "request", dictModel, dictBinding);
	REQUIRE_FALSE(dictRun.is_empty());
	const Dictionary dictNormalizedModel = dictRun["model"];
	CHECK(dictNormalizedModel.keys()[0].get_type() == Variant::STRING);
	CHECK(dictNormalizedModel["model"].get_type() == Variant::STRING);
	CHECK(String(dictNormalizedModel["model"]) == "named-model");
	Dictionary dictPayload;
	dictPayload[StringName("detail")] = StringName("ready");
	const Dictionary dictEvent = refRuntime->Publish(dictRun["run_id"], dictRun["generation"], "progress", dictPayload);
	CHECK(Dictionary(dictEvent["payload"])["detail"].get_type() == Variant::STRING);
}

TEST_CASE("[AIChat][AICore] Frozen numeric inputs retain double precision")
{
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	Dictionary dictBinding;
	dictBinding["parameter"] = 1.000000000000001;
	const Dictionary dictRun = refRuntime->BeginRun("chat", "precision", "request", Dictionary(), dictBinding);
	REQUIRE_FALSE(dictRun.is_empty());
	dictBinding["parameter"] = 1.000000000000002;
	CHECK(refRuntime->BeginRun("chat", "precision", "request", Dictionary(), dictBinding).is_empty());
}

TEST_CASE("[AIChat][AICore] Runtime survives synchronous release of its last external reference")
{
	Ref<ReentrantObserver> refObserver;
	refObserver.instantiate();
	Ref<AIWorkflowRuntime> refRuntime;
	refRuntime.instantiate();
	const Dictionary dictRun = refRuntime->BeginRun("chat", "lifetime", "publish");
	refObserver->pExternalReference = &refRuntime;
	const Callable fnObserver = callable_mp(refObserver.ptr(), &ReentrantObserver::OnEvent);
	refRuntime->connect("event_received", fnObserver);
	const Dictionary dictEvent = refRuntime->Publish(dictRun["run_id"], dictRun["generation"], "progress");
	CHECK(refRuntime.is_null());
	CHECK_FALSE(dictEvent.is_empty());
	refRuntime.instantiate();
	refRuntime->connect("event_received", fnObserver);
	const Dictionary dictStarted = refRuntime->BeginRun("chat", "lifetime", "begin");
	CHECK(refRuntime.is_null());
	CHECK(dictStarted["state"] == "running");
}
}
#endif
// clang-format on
