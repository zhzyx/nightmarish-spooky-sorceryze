/**************************************************************************/
/*  TestAIWorkflowRuntime.cpp                                            */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#include "tests/test_macros.h"
TEST_FORCE_LINK(TestAIWorkflowRuntime)

#ifdef TOOLS_ENABLED

#include "editor/AIWorkflowRuntime.h"
#include "core/os/memory.h"
#include "core/object/callable_mp.h"
#include "core/variant/array.h"
#include "tests/test_macros.h"

#include <thread>

namespace TestAIWorkflowRuntime
{
Dictionary MakeRequest()
{
	Dictionary mapRequest;
	mapRequest["workflow"] = "test";
	mapRequest["scope"] = "session";
	mapRequest["request_id"] = "one";
	Dictionary mapModel;
	mapModel["model"] = "initial";
	mapRequest["model"] = mapModel;
	Dictionary mapInput;
	mapInput["b"] = 2;
	mapInput["a"] = 1;
	mapRequest["input"] = mapInput;
	return mapRequest;
}

TEST_CASE("[Editor][AIWorkflowRuntime] Normalization freezing reattachment and terminal protection")
{
	AIWorkflowRuntime *pRuntime = memnew(AIWorkflowRuntime);
	Dictionary mapRequest = MakeRequest();
	Dictionary mapBegin = pRuntime->begin_run(mapRequest);
	CHECK(bool(mapBegin["ok"]));
	Dictionary mapSnapshot = mapBegin["snapshot"];
	CHECK(int64_t(mapSnapshot["sequence"]) == 1);
	CHECK_FALSE(mapSnapshot.has("input"));
	Dictionary mapReorderedInput;
	mapReorderedInput["a"] = 1;
	mapReorderedInput["b"] = 2;
	mapRequest["input"] = mapReorderedInput;
	CHECK(String(pRuntime->begin_run(mapRequest)["code"]) == "idempotent");
	Dictionary mapModel = mapRequest["model"];
	mapModel["model"] = "changed";
	CHECK(String(pRuntime->begin_run(mapRequest)["code"]) == "request_conflict");
	Dictionary mapReattached = pRuntime->snapshot(mapSnapshot["run_id"])["snapshot"];
	CHECK(String(Dictionary(mapReattached["model"])["model"]) == "initial");
	CHECK(int64_t(mapReattached["sequence"]) == 1);
	Dictionary mapCancelled = pRuntime->cancel(mapSnapshot["run_id"], mapSnapshot["generation"]);
	CHECK(bool(mapCancelled["ok"]));
	Dictionary mapLate;
	mapLate["run_id"] = mapSnapshot["run_id"];
	mapLate["generation"] = mapSnapshot["generation"];
	mapLate["event_id"] = "late";
	mapLate["kind"] = "completed";
	Dictionary mapRejected = pRuntime->publish(mapLate);
	CHECK(String(mapRejected["code"]) == "terminal");
	CHECK(String(Dictionary(mapRejected["snapshot"])["state"]) == "cancelled");
	memdelete(pRuntime);
}

TEST_CASE("[Editor][AIWorkflowRuntime] Node models public metadata and thread boundary")
{
	AIWorkflowRuntime *pOriginalSingleton = AIWorkflowRuntime::get_singleton();
	AIWorkflowRuntime *pRuntime = memnew(AIWorkflowRuntime);
	AIWorkflowRuntime *pSecond = memnew(AIWorkflowRuntime);
	CHECK(AIWorkflowRuntime::get_singleton() == (pOriginalSingleton == nullptr ? pRuntime : pOriginalSingleton));
	memdelete(pSecond);
	Dictionary mapRequest = MakeRequest();
	Dictionary mapNode;
	mapNode["node_id"] = "sculpt";
	mapNode["model"] = "node-choice";
	mapNode["image_model"] = "auxiliary-image-choice";
	Array arrNodes;
	arrNodes.push_back(mapNode);
	Dictionary mapModel = mapRequest["model"];
	mapModel["nodes"] = arrNodes;
	const Dictionary mapBegin = pRuntime->begin_run(mapRequest);
	CHECK(bool(mapBegin["ok"]));
	mapNode["model"] = "changed-after-start";
	const Dictionary mapSnapshot = mapBegin["snapshot"];
	const Dictionary mapFrozenModel = mapSnapshot["model"];
	const Array arrFrozenNodes = mapFrozenModel["nodes"];
	CHECK(String(Dictionary(arrFrozenNodes[0])["model"]) == "node-choice");
	CHECK(String(Dictionary(arrFrozenNodes[0])["image_model"]) == "auxiliary-image-choice");
	mapRequest["request_id"] = "unsafe";
	mapNode["api_key"] = "test-only";
	CHECK(String(pRuntime->begin_run(mapRequest)["code"]) == "private_metadata");
	mapNode.erase("api_key");
	mapNode["endpoint"] = "https://example.invalid";
	CHECK(String(pRuntime->begin_run(mapRequest)["code"]) == "private_metadata");
	String strWorkerCode;
	std::thread threadWorker([pRuntime, &strWorkerCode]()
	{
		strWorkerCode = pRuntime->snapshot("unused")["code"];
	});
	threadWorker.join();
	CHECK(strWorkerCode == "wrong_thread");
	memdelete(pRuntime);
	CHECK(AIWorkflowRuntime::get_singleton() == pOriginalSingleton);
}

class SignalObserver : public Object
{
public:
	int nEvents = 0;
	void OnEvent(Dictionary mapEvent)
	{
		++nEvents;
		Dictionary mapModel = mapEvent["model"];
		mapModel["model"] = "subscriber-mutated";
	}
};

TEST_CASE("[Editor][AIWorkflowRuntime] Signals only describe mutations and cannot mutate snapshots")
{
	AIWorkflowRuntime *pRuntime = memnew(AIWorkflowRuntime);
	SignalObserver *pObserver = memnew(SignalObserver);
	pRuntime->connect("run_event", callable_mp(pObserver, &SignalObserver::OnEvent));
	const Dictionary mapBegin = pRuntime->begin_run(MakeRequest());
	CHECK(pObserver->nEvents == 1);
	const Dictionary mapSnapshot = mapBegin["snapshot"];
	CHECK(String(Dictionary(mapSnapshot["model"])["model"]) == "initial");
	pRuntime->begin_run(MakeRequest());
	pRuntime->snapshot(mapSnapshot["run_id"]);
	CHECK(pObserver->nEvents == 1);
	pRuntime->cancel(mapSnapshot["run_id"], mapSnapshot["generation"]);
	pRuntime->cancel(mapSnapshot["run_id"], mapSnapshot["generation"]);
	CHECK(pObserver->nEvents == 2);
	memdelete(pObserver);
	memdelete(pRuntime);
}
}

#endif // TOOLS_ENABLED
