/**************************************************************************/
/*  AIWorkflowRuntime.cpp                                                 */
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

#include "AIWorkflowRuntime.h"

#include "core/io/json.h"
#include "core/object/class_db.h"
#include "core/variant/array.h"

#include <cmath>

// Preserve the project Allman convention during formatter migration.
// clang-format off
namespace
{
bool NormalizeData(const Variant &varValue, Variant &out_varData, int nDepth = 0)
{
	if (nDepth > 32)
	{
		return false;
	}
	switch (varValue.get_type())
	{
		case Variant::NIL:
		case Variant::BOOL:
		case Variant::INT:
		case Variant::STRING:
			out_varData = varValue;
			return true;
		case Variant::STRING_NAME:
			out_varData = String(varValue);
			return true;
		case Variant::FLOAT:
			out_varData = varValue;
			return std::isfinite(double(varValue));
		case Variant::ARRAY:
		{
			const Array arrValues = varValue;
			Array arrData;
			for (const Variant &varItem : arrValues)
			{
				Variant varData;
				if (!NormalizeData(varItem, varData, nDepth + 1))
				{
					return false;
				}
				arrData.push_back(varData);
			}
			out_varData = arrData;
			return true;
		}
		case Variant::DICTIONARY:
		{
			const Dictionary dictValues = varValue;
			const Array arrKeys = dictValues.keys();
			Dictionary dictData;
			for (const Variant &varKey : arrKeys)
			{
				if (varKey.get_type() != Variant::STRING && varKey.get_type() != Variant::STRING_NAME)
				{
					return false;
				}
				const String strKey = varKey;
				Variant varData;
				if (dictData.has(strKey) || !NormalizeData(dictValues[varKey], varData, nDepth + 1))
				{
					return false;
				}
				dictData[strKey] = varData;
			}
			out_varData = dictData;
			return true;
		}
		default:
			return false;
	}
}

std::string ToCoreString(const String &strValue)
{
	const CharString strUtf8 = strValue.utf8();
	return std::string(strUtf8.get_data(), strUtf8.length());
}

String StateName(AICore::State eState)
{
	switch (eState)
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
	return String();
}

bool ParseState(const String &strState, AICore::State &out_eState)
{
	for (const AICore::State eState : { AICore::State::Running, AICore::State::WaitingTool,
			 AICore::State::WaitingConfirmation, AICore::State::Reconciling,
			 AICore::State::Succeeded, AICore::State::Failed, AICore::State::Cancelled })
	{
		if (StateName(eState) == strState)
		{
			out_eState = eState;
			return true;
		}
	}
	return false;
}

bool ParseKind(const String &strKind, AICore::EventKind &out_eKind)
{
	static const char *arrNames[] = { "progress", "text_delta", "tool_requested", "artifact_ready", "completed", "failed", "cancelled" };
	for (int nIndex = 0; nIndex < 7; ++nIndex)
	{
		if (strKind == arrNames[nIndex])
		{
			out_eKind = static_cast<AICore::EventKind>(nIndex);
			return true;
		}
	}
	return false;
}
}

AIWorkflowRuntime::AIWorkflowRuntime() :
		stRuntime(ToCoreString("ai/" + uitos(get_instance_id())))
{
}

void AIWorkflowRuntime::_bind_methods()
{
	ClassDB::bind_method(D_METHOD("begin_run", "workflow", "scope", "request_id", "model", "binding"), &AIWorkflowRuntime::BeginRun, DEFVAL(Dictionary()), DEFVAL(Dictionary()));
	ClassDB::bind_method(D_METHOD("publish", "run_id", "generation", "kind", "payload", "state"), &AIWorkflowRuntime::Publish, DEFVAL(Dictionary()), DEFVAL(String()));
	ClassDB::bind_method(D_METHOD("cancel", "run_id"), &AIWorkflowRuntime::Cancel);
	ClassDB::bind_method(D_METHOD("snapshot", "run_id"), &AIWorkflowRuntime::Snapshot);
	ADD_SIGNAL(MethodInfo("event_received", PropertyInfo(Variant::DICTIONARY, "event")));
}

Dictionary AIWorkflowRuntime::BeginRun(const String &strWorkflow, const String &strScope, const String &strRequest,
		const Dictionary &dictModel, const Dictionary &dictBinding)
{
	Variant varModel;
	Variant varBinding;
	if (!NormalizeData(dictModel, varModel) || !NormalizeData(dictBinding, varBinding))
	{
		return Dictionary();
	}
	Dictionary dictInput;
	dictInput["model"] = varModel;
	dictInput["binding"] = varBinding;
	const AICore::Run *pRun = stRuntime.Begin(ToCoreString(strWorkflow), ToCoreString(strScope),
			ToCoreString(strRequest), ToCoreString(JSON::stringify(dictInput, String(), true, true)));
	if (pRun == nullptr)
	{
		return Dictionary();
	}
	const String strRun = String::utf8(pRun->strId.c_str());
	if (mapSnapshots.has(strRun))
	{
		return Snapshot(strRun);
	}
	Dictionary dictSnapshot;
	dictSnapshot["schema_version"] = 1;
	dictSnapshot["workflow"] = strWorkflow;
	dictSnapshot["scope"] = strScope;
	dictSnapshot["run_id"] = strRun;
	dictSnapshot["request_id"] = strRequest;
	dictSnapshot["generation"] = int64_t(pRun->nGeneration);
	dictSnapshot["sequence"] = int64_t(pRun->nSequence);
	dictSnapshot["kind"] = "run_started";
	dictSnapshot["state"] = "running";
	dictSnapshot["model"] = varModel;
	dictSnapshot["binding"] = varBinding;
	dictSnapshot["payload"] = Dictionary();
	dictSnapshot["text"] = String();
	dictSnapshot["artifacts"] = Array();
	dictSnapshot["tool_requests"] = Array();
	mapSnapshots[strRun] = dictSnapshot;
	Ref<AIWorkflowRuntime> refKeepAlive(this);
	emit_signal("event_received", dictSnapshot.duplicate(true));
	return Snapshot(strRun);
}

Dictionary AIWorkflowRuntime::Publish(const String &strRun, int64_t nGeneration, const String &strKind,
		const Dictionary &dictPayload, const String &strState)
{
	const AICore::Run *pRun = stRuntime.Find(ToCoreString(strRun));
	AICore::EventKind eKind;
	Variant varPayload;
	if (pRun == nullptr || nGeneration <= 0 || !ParseKind(strKind, eKind) || !NormalizeData(dictPayload, varPayload))
	{
		return Dictionary();
	}
	const Dictionary dictData = varPayload;
	if (strKind == "text_delta" && dictData.get("text", Variant()).get_type() != Variant::STRING)
	{
		return Dictionary();
	}
	AICore::State eState = pRun->eState;
	if (strKind == "completed")
	{
		eState = AICore::State::Succeeded;
	}
	else if (strKind == "failed")
	{
		eState = AICore::State::Failed;
	}
	else if (strKind == "cancelled")
	{
		eState = AICore::State::Cancelled;
	}
	else if (strKind == "tool_requested")
	{
		eState = AICore::State::WaitingTool;
	}
	if ((!strState.is_empty() && !ParseState(strState, eState)) ||
			!stRuntime.Apply(ToCoreString(strRun), uint64_t(nGeneration), eKind, eState))
	{
		return Dictionary();
	}
	Dictionary &dictSnapshot = mapSnapshots[strRun];
	dictSnapshot["sequence"] = int64_t(pRun->nSequence);
	dictSnapshot["kind"] = strKind;
	dictSnapshot["state"] = StateName(eState);
	dictSnapshot["payload"] = dictData;
	if (strKind == "text_delta")
	{
		dictSnapshot["text"] = String(dictSnapshot["text"]) + String(dictData.get("text", ""));
	}
	else if (strKind == "artifact_ready")
	{
		Array arrArtifacts = dictSnapshot["artifacts"];
		arrArtifacts.push_back(dictData.duplicate(true));
	}
	else if (strKind == "tool_requested")
	{
		Array arrTools = dictSnapshot["tool_requests"];
		arrTools.push_back(dictData.duplicate(true));
	}
	const Dictionary dictEvent = dictSnapshot.duplicate(true);
	Ref<AIWorkflowRuntime> refKeepAlive(this);
	emit_signal("event_received", dictEvent.duplicate(true));
	return dictEvent;
}

Dictionary AIWorkflowRuntime::Cancel(const String &strRun)
{
	const AICore::Run *pRun = stRuntime.Find(ToCoreString(strRun));
	if (pRun == nullptr)
	{
		return Dictionary();
	}
	return Publish(strRun, int64_t(pRun->nGeneration), "cancelled");
}

Dictionary AIWorkflowRuntime::Snapshot(const String &strRun) const
{
	const Dictionary *pSnapshot = mapSnapshots.getptr(strRun);
	return pSnapshot == nullptr ? Dictionary() : pSnapshot->duplicate(true);
}
// clang-format on
