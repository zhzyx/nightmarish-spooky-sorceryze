/**************************************************************************/
/*  AIWorkflowRuntime.cpp                                               */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                     */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#include "AIWorkflowRuntime.h"

#include "core/io/json.h"
#include "core/object/class_db.h"
#include "core/os/thread.h"
#include "core/variant/array.h"

#include <cmath>

AIWorkflowRuntime *AIWorkflowRuntime::pSingleton = nullptr;

namespace
{
std::string ToStandardString(const String &strValue)
{
	const CharString strUTF8 = strValue.utf8();
	return std::string(strUTF8.get_data(), strUTF8.length());
}

String ToGodotString(const std::string &strValue)
{
	return String::utf8(strValue.c_str(), strValue.size());
}

bool IsString(const Dictionary &mapValue, const char *pKey)
{
	return mapValue.has(pKey) && mapValue[pKey].get_type() == Variant::STRING;
}

Dictionary DecodeMetadata(const AICore::Metadata &mapValue)
{
	Dictionary mapResult;
	for (const AICore::Metadata::value_type &stEntry : mapValue)
	{
		mapResult[ToGodotString(stEntry.first)] = JSON::parse_string(ToGodotString(stEntry.second));
	}
	return mapResult;
}
}

AIWorkflowRuntime::AIWorkflowRuntime()
{
	// Tests can own independent instances without replacing the editor service.
	if (pSingleton == nullptr)
	{
		pSingleton = this;
	}
}

AIWorkflowRuntime::~AIWorkflowRuntime()
{
	if (pSingleton == this)
	{
		pSingleton = nullptr;
	}
}

AIWorkflowRuntime *AIWorkflowRuntime::get_singleton()
{
	return pSingleton;
}

void AIWorkflowRuntime::_bind_methods()
{
	ClassDB::bind_method(D_METHOD("begin_run", "request"), &AIWorkflowRuntime::begin_run);
	ClassDB::bind_method(D_METHOD("publish", "event"), &AIWorkflowRuntime::publish);
	ClassDB::bind_method(D_METHOD("cancel", "run_id", "generation", "event_id"), &AIWorkflowRuntime::cancel, DEFVAL("cancel"));
	ClassDB::bind_method(D_METHOD("snapshot", "run_id"), &AIWorkflowRuntime::snapshot);
	ADD_SIGNAL(MethodInfo("run_event", PropertyInfo(Variant::DICTIONARY, "event")));
}

Dictionary AIWorkflowRuntime::ErrorResult(const String &strCode, const String &strReason)
{
	Dictionary mapResult;
	mapResult["ok"] = false;
	mapResult["changed"] = false;
	mapResult["code"] = strCode;
	mapResult["reason"] = strReason;
	mapResult["snapshot"] = Dictionary();
	return mapResult;
}

bool AIWorkflowRuntime::ValidateJSON(const Variant &varValue, int nDepth)
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
			return true;
		case Variant::FLOAT:
			return std::isfinite(static_cast<double>(varValue));
		case Variant::ARRAY:
		{
			const Array arrValue = varValue;
			for (int nIndex = 0; nIndex < arrValue.size(); ++nIndex)
			{
				if (!ValidateJSON(arrValue[nIndex], nDepth + 1))
				{
					return false;
				}
			}
			return true;
		}
		case Variant::DICTIONARY:
		{
			const Dictionary mapValue = varValue;
			const Array arrKeys = mapValue.keys();
			for (int nIndex = 0; nIndex < arrKeys.size(); ++nIndex)
			{
				if (arrKeys[nIndex].get_type() != Variant::STRING)
				{
					return false;
				}
				const String strKey = String(arrKeys[nIndex]).to_lower().replace("-", "_");
				if (strKey.contains("password") || strKey.contains("secret") || strKey.contains("credential") || strKey == "api_key" || strKey == "apikey" || strKey == "access_token" || strKey == "refresh_token" || strKey == "authorization" || strKey == "headers")
				{
					return false;
				}
				if (!ValidateJSON(mapValue[arrKeys[nIndex]], nDepth + 1))
				{
					return false;
				}
			}
			return true;
		}
		default:
			return false;
	}
}

bool AIWorkflowRuntime::ReadMetadata(const Dictionary &mapValue, bool bModel, AICore::Metadata &out_mapValue)
{
	if (!ValidateJSON(mapValue))
	{
		return false;
	}
	const Array arrKeys = mapValue.keys();
	for (int nIndex = 0; nIndex < arrKeys.size(); ++nIndex)
	{
		const String strKey = arrKeys[nIndex];
		const Variant varValue = mapValue[strKey];
		if (!AICore::WorkflowRuntime::IsPublicMetadataKey(ToStandardString(strKey), bModel))
		{
			return false;
		}
		if (bModel && strKey == "nodes")
		{
			if (varValue.get_type() != Variant::ARRAY)
			{
				return false;
			}
			const Array arrNodes = varValue;
			for (int nNode = 0; nNode < arrNodes.size(); ++nNode)
			{
				if (arrNodes[nNode].get_type() != Variant::DICTIONARY)
				{
					return false;
				}
				const Dictionary mapNode = arrNodes[nNode];
				AICore::Metadata mapNodeMetadata;
				if (mapNode.has("nodes") || !IsString(mapNode, "node_id") || String(mapNode["node_id"]).is_empty() || !ReadMetadata(mapNode, true, mapNodeMetadata))
				{
					return false;
				}
			}
		}
		else if (bModel && strKey == "capabilities")
		{
			if (varValue.get_type() != Variant::ARRAY)
			{
				return false;
			}
			const Array arrCapabilities = varValue;
			for (int nCapability = 0; nCapability < arrCapabilities.size(); ++nCapability)
			{
				if (arrCapabilities[nCapability].get_type() != Variant::STRING)
				{
					return false;
				}
			}
		}
		else if (varValue.get_type() != Variant::STRING && varValue.get_type() != Variant::INT && varValue.get_type() != Variant::BOOL)
		{
			return false;
		}
		out_mapValue[ToStandardString(strKey)] = ToStandardString(JSON::stringify(varValue, "", true, true));
	}
	return true;
}

Dictionary AIWorkflowRuntime::ConvertResult(const AICore::Result &stResult)
{
	Dictionary mapResult = ErrorResult(ToGodotString(stResult.strCode), ToGodotString(stResult.strReason));
	mapResult["ok"] = stResult.bOk;
	mapResult["changed"] = stResult.bChanged;
	const AICore::RunSnapshot &stSnapshot = stResult.stSnapshot;
	if (!stSnapshot.strRunId.empty())
	{
		Dictionary mapSnapshot;
		mapSnapshot["schema_version"] = stSnapshot.nSchemaVersion;
		mapSnapshot["workflow"] = ToGodotString(stSnapshot.strWorkflow);
		mapSnapshot["scope"] = ToGodotString(stSnapshot.strScope);
		mapSnapshot["run_id"] = ToGodotString(stSnapshot.strRunId);
		mapSnapshot["request_id"] = ToGodotString(stSnapshot.strRequestId);
		mapSnapshot["generation"] = stSnapshot.nGeneration;
		mapSnapshot["sequence"] = stSnapshot.nSequence;
		mapSnapshot["kind"] = ToGodotString(stSnapshot.strKind);
		mapSnapshot["state"] = ToGodotString(stSnapshot.strState);
		mapSnapshot["model"] = DecodeMetadata(stSnapshot.mapModel);
		mapSnapshot["binding"] = DecodeMetadata(stSnapshot.mapBinding);
		mapSnapshot["payload"] = JSON::parse_string(ToGodotString(stSnapshot.strPayload));
		mapResult["snapshot"] = mapSnapshot;
	}
	return mapResult;
}

Dictionary AIWorkflowRuntime::EmitResult(const AICore::Result &stResult)
{
	Dictionary mapResult = ConvertResult(stResult);
	if (stResult.bChanged)
	{
		const Dictionary mapSnapshot = mapResult["snapshot"];
		arrPendingEvents.push_back(mapSnapshot.duplicate(true));
	}
	if (!bEmittingEvents)
	{
		// Reentrant subscribers may publish again. Finish delivering the current
		// sequence to every subscriber before delivering their new event.
		bEmittingEvents = true;
		for (int nIndex = 0; nIndex < arrPendingEvents.size(); ++nIndex)
		{
			const Dictionary mapEvent = arrPendingEvents[nIndex];
			emit_signal(SNAME("run_event"), mapEvent);
		}
		arrPendingEvents.clear();
		bEmittingEvents = false;
	}
	return mapResult;
}

Dictionary AIWorkflowRuntime::begin_run(const Dictionary &mapRequest)
{
	if (!Thread::is_main_thread())
	{
		return ErrorResult("wrong_thread", "Godot runtime methods require the main thread.");
	}
	if (!IsString(mapRequest, "workflow") || !IsString(mapRequest, "scope") || !IsString(mapRequest, "request_id"))
	{
		return ErrorResult("invalid_request", "workflow, scope and request_id must be strings.");
	}
	for (const char *pKey : { "model", "binding", "input" })
	{
		if (mapRequest.has(pKey) && mapRequest[pKey].get_type() != Variant::DICTIONARY)
		{
			return ErrorResult("invalid_request", "model, binding and input must be dictionaries.");
		}
	}
	if (mapRequest.has("initial_state") && !IsString(mapRequest, "initial_state"))
	{
		return ErrorResult("invalid_request", "initial_state must be a string.");
	}
	AICore::BeginRequest stRequest;
	stRequest.strWorkflow = ToStandardString(mapRequest["workflow"]);
	stRequest.strScope = ToStandardString(mapRequest["scope"]);
	stRequest.strRequestId = ToStandardString(mapRequest["request_id"]);
	stRequest.strInitialState = ToStandardString(mapRequest.get("initial_state", "running"));
	if (!ReadMetadata(mapRequest.get("model", Dictionary()), true, stRequest.mapModel) || !ReadMetadata(mapRequest.get("binding", Dictionary()), false, stRequest.mapBinding))
	{
		return ErrorResult("private_metadata", "Model or binding contains an unsupported or private field.");
	}
	const Dictionary mapInput = mapRequest.get("input", Dictionary());
	if (!ValidateJSON(mapInput))
	{
		return ErrorResult("invalid_input", "Input must contain finite public JSON data.");
	}
	stRequest.strNormalizedInput = ToStandardString(JSON::stringify(mapInput, "", true, true));
	return EmitResult(stRuntime.BeginRun(stRequest));
}

Dictionary AIWorkflowRuntime::publish(const Dictionary &mapEvent)
{
	if (!Thread::is_main_thread())
	{
		return ErrorResult("wrong_thread", "Godot runtime methods require the main thread.");
	}
	if (!IsString(mapEvent, "run_id") || !IsString(mapEvent, "event_id") || !IsString(mapEvent, "kind") || !mapEvent.has("generation") || mapEvent["generation"].get_type() != Variant::INT || int64_t(mapEvent["generation"]) <= 0)
	{
		return ErrorResult("invalid_event", "Event requires run_id, positive generation, event_id and kind.");
	}
	if ((mapEvent.has("state") && !IsString(mapEvent, "state")) || (mapEvent.has("expected_sequence") && (mapEvent["expected_sequence"].get_type() != Variant::INT || int64_t(mapEvent["expected_sequence"]) <= 0)) || (mapEvent.has("payload") && mapEvent["payload"].get_type() != Variant::DICTIONARY))
	{
		return ErrorResult("invalid_event", "Invalid state, expected_sequence or payload type.");
	}
	const Dictionary mapPayload = mapEvent.get("payload", Dictionary());
	if (!ValidateJSON(mapPayload))
	{
		return ErrorResult("invalid_payload", "Payload must contain finite public JSON data.");
	}
	AICore::PublishRequest stRequest;
	stRequest.strRunId = ToStandardString(mapEvent["run_id"]);
	stRequest.nGeneration = int64_t(mapEvent["generation"]);
	stRequest.strEventId = ToStandardString(mapEvent["event_id"]);
	stRequest.nExpectedSequence = int64_t(mapEvent.get("expected_sequence", 0));
	stRequest.strKind = ToStandardString(mapEvent["kind"]);
	stRequest.strState = ToStandardString(mapEvent.get("state", ""));
	stRequest.strPayload = ToStandardString(JSON::stringify(mapPayload, "", true, true));
	return EmitResult(stRuntime.Publish(stRequest));
}

Dictionary AIWorkflowRuntime::cancel(const String &strRunId, int64_t nGeneration, const String &strEventId)
{
	if (!Thread::is_main_thread())
	{
		return ErrorResult("wrong_thread", "Godot runtime methods require the main thread.");
	}
	if (nGeneration <= 0)
	{
		return ErrorResult("invalid_event", "Generation must be positive.");
	}
	return EmitResult(stRuntime.Cancel(ToStandardString(strRunId), nGeneration, ToStandardString(strEventId)));
}

Dictionary AIWorkflowRuntime::snapshot(const String &strRunId) const
{
	if (!Thread::is_main_thread())
	{
		return ErrorResult("wrong_thread", "Godot runtime methods require the main thread.");
	}
	return ConvertResult(stRuntime.Snapshot(ToStandardString(strRunId)));
}
