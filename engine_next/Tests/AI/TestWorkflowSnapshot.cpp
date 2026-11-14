/**************************************************************************/
/*  TestWorkflowSnapshot.cpp                                              */
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
#include "engine_next/include/EngineNext/AI/WorkflowSnapshot.h"

ENGINE_NEXT_TEST("Neutral workflow freezes input and isolates concurrent runs")
{
	EngineNext::AI::WorkflowSnapshot stRuntime("m3-test");
	EngineNext::Serialization::JsonValue stModel(EngineNext::Serialization::JsonValue::Object{ { "model", "synthetic" } });
	EngineNext::Serialization::JsonValue stBinding(EngineNext::Serialization::JsonValue::Object{ { "revision", "r1" } });
	const EngineNext::AI::RunSnapshot *pFirst = stRuntime.Begin("m3", "scene-a", "request", stModel, stBinding);
	ENGINE_NEXT_CHECK(pFirst != nullptr);
	ENGINE_NEXT_CHECK_EQ(pFirst->nSequence, 1ULL);
	ENGINE_NEXT_CHECK_EQ(pFirst->strState, std::string("running"));
	ENGINE_NEXT_CHECK(stRuntime.Begin("m3", "scene-a", "request", stModel, stBinding) == pFirst);
	EngineNext::Serialization::JsonValue stOtherModel(EngineNext::Serialization::JsonValue::Object{ { "model", "other" } });
	ENGINE_NEXT_CHECK(stRuntime.Begin("m3", "scene-a", "request", stOtherModel, stBinding) == nullptr);
	const EngineNext::AI::RunSnapshot *pSecond = stRuntime.Begin("m3", "scene-b", "request", stModel, stBinding);
	ENGINE_NEXT_CHECK(pSecond != nullptr);
	ENGINE_NEXT_CHECK(pSecond->nGeneration > pFirst->nGeneration);
	ENGINE_NEXT_CHECK(stRuntime.Publish(pFirst->strRunId, pFirst->nGeneration + 1, "progress", EngineNext::Serialization::JsonValue::Object{}) == nullptr);
	ENGINE_NEXT_CHECK(stRuntime.Publish(pSecond->strRunId, pSecond->nGeneration, "completed", EngineNext::Serialization::JsonValue::Object{}) != nullptr);
	ENGINE_NEXT_CHECK_EQ(stRuntime.Find(pFirst->strRunId)->strState, std::string("running"));
}

ENGINE_NEXT_TEST("Neutral workflow publishes artifacts once per accepted event and rejects late data")
{
	EngineNext::AI::WorkflowSnapshot stRuntime("m3-test");
	const EngineNext::AI::RunSnapshot *pRun = stRuntime.Begin("m3", "scene", "request",
															  EngineNext::Serialization::JsonValue::Object{}, EngineNext::Serialization::JsonValue::Object{});
	ENGINE_NEXT_CHECK(pRun != nullptr);
	const EngineNext::Serialization::JsonValue stArtifact(EngineNext::Serialization::JsonValue::Object{
			{ "asset_id", "mesh" },
			{ "revision", "r1" },
			{ "content_sha256", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" },
			{ "extension", EngineNext::Serialization::JsonValue::Object{
								   { "future_payload", EngineNext::Serialization::JsonValue::List{ std::int64_t(7), "opaque" } },
						   } },
	});
	const EngineNext::AI::RunSnapshot *pReady = stRuntime.Publish(pRun->strRunId, pRun->nGeneration, "artifact_ready", stArtifact);
	ENGINE_NEXT_CHECK(pReady != nullptr);
	ENGINE_NEXT_CHECK_EQ(pReady->arrArtifacts.size(), 1ULL);
	ENGINE_NEXT_CHECK(stRuntime.Cancel(pRun->strRunId) != nullptr);
	ENGINE_NEXT_CHECK(stRuntime.Publish(pRun->strRunId, pRun->nGeneration, "artifact_ready", stArtifact) == nullptr);
	ENGINE_NEXT_CHECK(stRuntime.Cancel(pRun->strRunId) == nullptr);
	ENGINE_NEXT_CHECK_EQ(stRuntime.Find(pRun->strRunId)->arrArtifacts.size(), 1ULL);
	std::string strJson;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::AI::WorkflowSnapshot::ToJson(*stRuntime.Find(pRun->strRunId)), strJson));
	ENGINE_NEXT_CHECK(strJson.find("\"state\":\"cancelled\"") != std::string::npos);
	ENGINE_NEXT_CHECK(strJson.find("\"future_payload\":[7,\"opaque\"]") != std::string::npos);
}
