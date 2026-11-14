/**************************************************************************/
/*  WorkflowSnapshot.h                                                    */
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

#include "ai_core/Runtime.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace EngineNext::AI
{

struct RunSnapshot
{
	std::string strWorkflow;
	std::string strScope;
	std::string strRunId;
	std::string strRequestId;
	std::uint64_t nGeneration = 0;
	std::uint64_t nSequence = 0;
	std::string strKind;
	std::string strState;
	Serialization::JsonValue stModel;
	Serialization::JsonValue stBinding;
	Serialization::JsonValue stPayload;
	std::string strText;
	std::vector<Serialization::JsonValue> arrArtifacts;
	std::vector<Serialization::JsonValue> arrToolRequests;
};

class WorkflowSnapshot final
{
	AICore::Runtime stRuntime;
	std::map<std::string, RunSnapshot> mapSnapshots;

public:
	explicit WorkflowSnapshot(const std::string &in_strIdentity);
	[[nodiscard]] const RunSnapshot *Begin(const std::string &in_strWorkflow, const std::string &in_strScope,
										   const std::string &in_strRequest, const Serialization::JsonValue &in_stModel, const Serialization::JsonValue &in_stBinding);
	[[nodiscard]] const RunSnapshot *Publish(const std::string &in_strRun, std::uint64_t in_nGeneration,
											 const std::string &in_strKind, const Serialization::JsonValue &in_stPayload, const std::string &in_strState = std::string());
	[[nodiscard]] const RunSnapshot *Cancel(const std::string &in_strRun);
	[[nodiscard]] const RunSnapshot *Find(const std::string &in_strRun) const noexcept;
	[[nodiscard]] static Serialization::JsonValue ToJson(const RunSnapshot &in_stSnapshot);
};

} // namespace EngineNext::AI
