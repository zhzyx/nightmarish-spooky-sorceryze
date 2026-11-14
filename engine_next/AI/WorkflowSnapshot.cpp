/**************************************************************************/
/*  WorkflowSnapshot.cpp                                                  */
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

#include "engine_next/include/EngineNext/AI/WorkflowSnapshot.h"

#include <utility>

namespace EngineNext::AI
{
namespace
{

const char *StateName(AICore::State in_eState)
{
	switch (in_eState)
	{
		case AICore::State::Running:
			return "running";
		case AICore::State::WaitingTool:
			return "waiting_tool";
		case AICore::State::WaitingConfirmation:
			return "waiting_confirmation";
		case AICore::State::Reconciling:
			return "reconciling";
		case AICore::State::Succeeded:
			return "succeeded";
		case AICore::State::Failed:
			return "failed";
		case AICore::State::Cancelled:
			return "cancelled";
	}
	return "";
}

bool ParseState(const std::string &in_strName, AICore::State &out_eState)
{
	for (const AICore::State eState : { AICore::State::Running, AICore::State::WaitingTool, AICore::State::WaitingConfirmation,
										AICore::State::Reconciling, AICore::State::Succeeded, AICore::State::Failed, AICore::State::Cancelled })
	{
		if (in_strName == StateName(eState))
		{
			out_eState = eState;
			return true;
		}
	}
	return false;
}

bool ParseKind(const std::string &in_strName, AICore::EventKind &out_eKind)
{
	static const char *arrNames[] = { "progress", "text_delta", "tool_requested", "artifact_ready", "completed", "failed", "cancelled" };
	for (std::size_t nIndex = 0; nIndex < 7; ++nIndex)
	{
		if (in_strName == arrNames[nIndex])
		{
			out_eKind = static_cast<AICore::EventKind>(nIndex);
			return true;
		}
	}
	return false;
}

Serialization::JsonValue ArrayJson(const std::vector<Serialization::JsonValue> &in_arrValues)
{
	return Serialization::JsonValue(Serialization::JsonValue::List(in_arrValues.begin(), in_arrValues.end()));
}

} // namespace

WorkflowSnapshot::WorkflowSnapshot(const std::string &in_strIdentity) :
		stRuntime(in_strIdentity)
{
}

const RunSnapshot *WorkflowSnapshot::Begin(const std::string &in_strWorkflow, const std::string &in_strScope,
										   const std::string &in_strRequest, const Serialization::JsonValue &in_stModel, const Serialization::JsonValue &in_stBinding)
{
	if (!in_stModel.IsObject() || !in_stBinding.IsObject())
	{
		return nullptr;
	}
	const Serialization::JsonValue stInput(Serialization::JsonValue::Object{ { "binding", in_stBinding }, { "model", in_stModel } });
	std::string strCanonical;
	if (!Serialization::CanonicalJson(stInput, strCanonical))
	{
		return nullptr;
	}
	const AICore::Run *pRun = stRuntime.Begin(in_strWorkflow, in_strScope, in_strRequest, strCanonical);
	if (pRun == nullptr)
	{
		return nullptr;
	}
	const std::map<std::string, RunSnapshot>::const_iterator itExisting = mapSnapshots.find(pRun->strId);
	if (itExisting != mapSnapshots.end())
	{
		return &itExisting->second;
	}
	RunSnapshot stSnapshot;
	stSnapshot.strWorkflow = in_strWorkflow;
	stSnapshot.strScope = in_strScope;
	stSnapshot.strRunId = pRun->strId;
	stSnapshot.strRequestId = in_strRequest;
	stSnapshot.nGeneration = pRun->nGeneration;
	stSnapshot.nSequence = pRun->nSequence;
	stSnapshot.strKind = "run_started";
	stSnapshot.strState = "running";
	stSnapshot.stModel = in_stModel;
	stSnapshot.stBinding = in_stBinding;
	return &mapSnapshots.emplace(pRun->strId, std::move(stSnapshot)).first->second;
}

const RunSnapshot *WorkflowSnapshot::Publish(const std::string &in_strRun, std::uint64_t in_nGeneration,
											 const std::string &in_strKind, const Serialization::JsonValue &in_stPayload, const std::string &in_strState)
{
	const AICore::Run *pRun = stRuntime.Find(in_strRun);
	AICore::EventKind eKind = AICore::EventKind::Progress;
	if (pRun == nullptr || in_nGeneration == 0 || !in_stPayload.IsObject() || !ParseKind(in_strKind, eKind))
	{
		return nullptr;
	}
	if (in_strKind == "text_delta")
	{
		const Serialization::JsonValue::Object *pPayload = in_stPayload.GetObject();
		const Serialization::JsonValue::Object::const_iterator itText = pPayload->find("text");
		if (itText == pPayload->end() || itText->second.GetString() == nullptr)
		{
			return nullptr;
		}
	}
	AICore::State eState = pRun->eState;
	if (in_strKind == "completed")
	{
		eState = AICore::State::Succeeded;
	}
	else if (in_strKind == "failed")
	{
		eState = AICore::State::Failed;
	}
	else if (in_strKind == "cancelled")
	{
		eState = AICore::State::Cancelled;
	}
	else if (in_strKind == "tool_requested")
	{
		eState = AICore::State::WaitingTool;
	}
	if ((!in_strState.empty() && !ParseState(in_strState, eState)) || !stRuntime.Apply(in_strRun, in_nGeneration, eKind, eState))
	{
		return nullptr;
	}
	RunSnapshot &stSnapshot = mapSnapshots[in_strRun];
	stSnapshot.nSequence = pRun->nSequence;
	stSnapshot.strKind = in_strKind;
	stSnapshot.strState = StateName(eState);
	stSnapshot.stPayload = in_stPayload;
	if (in_strKind == "text_delta")
	{
		stSnapshot.strText += *in_stPayload.GetObject()->at("text").GetString();
	}
	else if (in_strKind == "artifact_ready")
	{
		stSnapshot.arrArtifacts.push_back(in_stPayload);
	}
	else if (in_strKind == "tool_requested")
	{
		stSnapshot.arrToolRequests.push_back(in_stPayload);
	}
	return &stSnapshot;
}

const RunSnapshot *WorkflowSnapshot::Cancel(const std::string &in_strRun)
{
	const AICore::Run *pRun = stRuntime.Find(in_strRun);
	if (pRun == nullptr)
	{
		return nullptr;
	}
	return Publish(in_strRun, pRun->nGeneration, "cancelled", Serialization::JsonValue::Object{});
}

const RunSnapshot *WorkflowSnapshot::Find(const std::string &in_strRun) const noexcept
{
	const std::map<std::string, RunSnapshot>::const_iterator itSnapshot = mapSnapshots.find(in_strRun);
	return itSnapshot == mapSnapshots.end() ? nullptr : &itSnapshot->second;
}

Serialization::JsonValue WorkflowSnapshot::ToJson(const RunSnapshot &in_stSnapshot)
{
	return Serialization::JsonValue::Object{
		{ "artifacts", ArrayJson(in_stSnapshot.arrArtifacts) },
		{ "binding", in_stSnapshot.stBinding },
		{ "generation", static_cast<std::int64_t>(in_stSnapshot.nGeneration) },
		{ "kind", in_stSnapshot.strKind },
		{ "model", in_stSnapshot.stModel },
		{ "payload", in_stSnapshot.stPayload },
		{ "request_id", in_stSnapshot.strRequestId },
		{ "run_id", in_stSnapshot.strRunId },
		{ "schema_version", std::int64_t(1) },
		{ "scope", in_stSnapshot.strScope },
		{ "sequence", static_cast<std::int64_t>(in_stSnapshot.nSequence) },
		{ "state", in_stSnapshot.strState },
		{ "text", in_stSnapshot.strText },
		{ "tool_requests", ArrayJson(in_stSnapshot.arrToolRequests) },
		{ "workflow", in_stSnapshot.strWorkflow },
	};
}

} // namespace EngineNext::AI
