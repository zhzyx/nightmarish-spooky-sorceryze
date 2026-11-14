/**************************************************************************/
/*  WorkflowRuntimeTest.cpp                                               */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#include "ai_core/WorkflowRuntime.h"

#include <atomic>
#include <cstdlib>
#include <iostream>
#include <thread>
#include <vector>

namespace
{
void Check(bool bCondition, const char *pMessage)
{
	if (!bCondition)
	{
		std::cerr << "FAIL: " << pMessage << '\n';
		std::exit(1);
	}
}

AICore::BeginRequest Request()
{
	AICore::BeginRequest stRequest;
	stRequest.strWorkflow = "chat";
	stRequest.strScope = "session-a";
	stRequest.strRequestId = "request-a";
	stRequest.mapModel["model"] = "\"model-a\"";
	stRequest.mapBinding["session_id"] = "\"session-a\"";
	stRequest.strNormalizedInput = "{\"prompt\":\"hello\"}";
	return stRequest;
}

AICore::PublishRequest Event(const AICore::RunSnapshot &stSnapshot, const std::string &strId, const std::string &strKind)
{
	AICore::PublishRequest stEvent;
	stEvent.strRunId = stSnapshot.strRunId;
	stEvent.nGeneration = stSnapshot.nGeneration;
	stEvent.strEventId = strId;
	stEvent.strKind = strKind;
	return stEvent;
}
}

int main()
{
	AICore::WorkflowRuntime stRuntime;
	AICore::BeginRequest stRequest = Request();
	const AICore::Result stBegin = stRuntime.BeginRun(stRequest);
	Check(stBegin.bOk && stBegin.bChanged && stBegin.stSnapshot.nSequence == 1, "begin owns sequence");
	Check(stRuntime.BeginRun(stRequest).strCode == "idempotent", "same content reuses run");
	stRequest.mapModel["model"] = "\"model-b\"";
	Check(stRuntime.BeginRun(stRequest).strCode == "request_conflict", "conflicting model rejected");
	Check(stRuntime.Snapshot(stBegin.stSnapshot.strRunId).stSnapshot.mapModel.at("model") == "\"model-a\"", "model frozen");
	stRequest = Request();
	stRequest.strNormalizedInput = "{\"prompt\":\"changed\"}";
	Check(stRuntime.BeginRun(stRequest).strCode == "request_conflict", "conflicting input rejected");
	stRequest = Request();
	stRequest.strScope = "session-b";
	const AICore::Result stOtherScope = stRuntime.BeginRun(stRequest);
	stRequest.strWorkflow = "maliang";
	const AICore::Result stOtherWorkflow = stRuntime.BeginRun(stRequest);
	Check(stOtherScope.bOk && stOtherWorkflow.bOk && stOtherScope.stSnapshot.strRunId != stOtherWorkflow.stSnapshot.strRunId && stOtherScope.stSnapshot.nGeneration != stBegin.stSnapshot.nGeneration, "workflow and scope isolation");
	stRequest = Request();
	stRequest.strRequestId = "unsafe";
	stRequest.mapModel["api_key"] = "\"not-a-key\"";
	Check(stRuntime.BeginRun(stRequest).strCode == "private_metadata", "private metadata rejected");

	AICore::PublishRequest stEvent = Event(stBegin.stSnapshot, "text-1", "text_delta");
	stEvent.strPayload = "{\"text\":\"hello\"}";
	stEvent.nExpectedSequence = 1;
	Check(stRuntime.Publish(stEvent).stSnapshot.nSequence == 2, "core increments sequence");
	Check(stRuntime.Publish(stEvent).strCode == "duplicate", "exact duplicate does not advance");
	stEvent.strPayload = "{\"text\":\"different\"}";
	Check(stRuntime.Publish(stEvent).strCode == "event_conflict", "duplicate identity changed payload rejected");
	stEvent.strEventId = "late";
	Check(stRuntime.Publish(stEvent).strCode == "stale_sequence", "out-of-order sequence rejected");
	stEvent.nGeneration += 100;
	Check(stRuntime.Publish(stEvent).strCode == "stale_generation", "wrong generation rejected");
	stEvent = Event(stBegin.stSnapshot, "tool", "tool_requested");
	Check(stRuntime.Publish(stEvent).stSnapshot.strState == "waiting_tool", "tool wait");
	stEvent = Event(stBegin.stSnapshot, "confirm", "progress");
	stEvent.strState = "waiting_confirmation";
	Check(stRuntime.Publish(stEvent).bOk, "confirmation wait");
	stEvent.strEventId = "reconcile";
	stEvent.strState = "reconciling";
	Check(stRuntime.Publish(stEvent).bOk, "reconcile domain receipt");
	stEvent.strEventId = "bad-terminal";
	stEvent.strState = "succeeded";
	Check(stRuntime.Publish(stEvent).strCode == "invalid_state", "progress cannot fake terminal");
	stEvent = Event(stBegin.stSnapshot, "done", "completed");
	Check(stRuntime.Publish(stEvent).stSnapshot.strState == "succeeded", "success transition");
	const AICore::RunSnapshot stTerminal = stRuntime.Snapshot(stBegin.stSnapshot.strRunId).stSnapshot;
	Check(stRuntime.Publish(stEvent).strCode == "duplicate", "terminal replay deduplicated");
	Check(stRuntime.Cancel(stBegin.stSnapshot.strRunId, stBegin.stSnapshot.nGeneration).strCode == "terminal", "cancel cannot reverse success");
	AICore::RunSnapshot stCopy = stTerminal;
	stCopy.mapBinding["session_id"] = "\"mutated\"";
	Check(stRuntime.Snapshot(stBegin.stSnapshot.strRunId).stSnapshot.mapBinding != stCopy.mapBinding, "snapshot is independent value");
	Check(stRuntime.Snapshot(stBegin.stSnapshot.strRunId).stSnapshot.nSequence == stTerminal.nSequence, "snapshot has no side effects");
	Check(stRuntime.Cancel(stOtherScope.stSnapshot.strRunId, stOtherScope.stSnapshot.nGeneration).bOk, "cancel active run");
	Check(stRuntime.Cancel(stOtherScope.stSnapshot.strRunId, stOtherScope.stSnapshot.nGeneration).strCode == "duplicate", "cancel duplicate");
	Check(stRuntime.Publish(Event(stOtherScope.stSnapshot, "late-completion", "completed")).strCode == "terminal", "late result after cancellation rejected");
	Check(stRuntime.Publish(Event(stOtherWorkflow.stSnapshot, "failure", "failed")).stSnapshot.strState == "failed", "failure transition");

	stRequest = Request();
	stRequest.strRequestId = "recovered";
	stRequest.strInitialState = "reconciling";
	Check(stRuntime.BeginRun(stRequest).stSnapshot.strState == "reconciling", "recovery starts reconciling");
	AICore::WorkflowRuntime stRestarted;
	Check(stRestarted.Snapshot(stBegin.stSnapshot.strRunId).strCode == "not_found", "memory is not persistence");

	// Concurrent callers race the same identity and event. Exactly one mutation wins.
	AICore::WorkflowRuntime stConcurrent;
	std::atomic<int> nStarts{ 0 };
	std::atomic<int> nEvents{ 0 };
	std::atomic<int> nFailures{ 0 };
	std::vector<std::thread> arrThreads;
	for (int nIndex = 0; nIndex < 12; ++nIndex)
	{
		arrThreads.emplace_back([&stConcurrent, &nStarts, &nEvents, &nFailures]()
		{
			const AICore::Result stStart = stConcurrent.BeginRun(Request());
			nStarts += stStart.bChanged ? 1 : 0;
			const AICore::Result stPublished = stConcurrent.Publish(Event(stStart.stSnapshot, "same-event", "progress"));
			nEvents += stPublished.bChanged ? 1 : 0;
			nFailures += (!stStart.bOk || !stPublished.bOk) ? 1 : 0;
		});
	}
	for (std::thread &threadWorker : arrThreads)
	{
		threadWorker.join();
	}
	Check(nStarts == 1 && nEvents == 1 && nFailures == 0, "concurrent begin and duplicate linearize");
	Check(stConcurrent.BeginRun(Request()).stSnapshot.nSequence == 2, "concurrency preserves sequence");
	std::cout << "PASS: identity, idempotency, isolation, state transitions, cancellation, late events, deduplication, frozen snapshots, recovery boundary, 12-thread linearization\n";
	return 0;
}
