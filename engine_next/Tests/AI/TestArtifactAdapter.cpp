/**************************************************************************/
/*  TestArtifactAdapter.cpp                                               */
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
#include "engine_next/include/EngineNext/AI/ArtifactAdapter.h"

ENGINE_NEXT_TEST("Artifact adapter reports missing content without terminating")
{
	EngineNext::AI::AiAssetRequest stRequest;
	stRequest.stSceneTemplate.strSceneId = "artifact.test";
	stRequest.stSceneTemplate.strSceneRevision = "r1";
	EngineNext::Assets::SceneEntity stEntity;
	stEntity.nEntityId = 1;
	stEntity.strName = "mesh";
	stEntity.strNodeType = "MeshInstance3D";
	stEntity.strGameplayKind = "static";
	stEntity.arrAssets.push_back(EngineNext::Assets::SceneAssetRef{ "mesh", { "mesh", "pending", std::string(64, '0') } });
	stRequest.stSceneTemplate.arrEntities.push_back(stEntity);
	stRequest.arrBindings.push_back(EngineNext::AI::AssetBinding{ "mesh", "mesh", "copy", "result" });
	const EngineNext::Serialization::JsonValue stArtifact(EngineNext::Serialization::JsonValue::Object{
			{ "id", "output" },
			{ "revision", "r1" },
			{ "type", "mesh" },
			{ "payload", EngineNext::Serialization::JsonValue::Object{} },
	});
	const EngineNext::Serialization::JsonValue stExport(EngineNext::Serialization::JsonValue::Object{
			{ "manifest", EngineNext::Serialization::JsonValue::Object{ { "artifacts", EngineNext::Serialization::JsonValue::List{ stArtifact } } } },
			{ "outputs", EngineNext::Serialization::JsonValue::Object{ { "copy", EngineNext::Serialization::JsonValue::Object{
																						 { "result", EngineNext::Serialization::JsonValue::Object{ { "id", "output" }, { "revision", "r1" } } },
																				 } } } },
	});
	EngineNext::Assets::PackageData stPackage;
	std::vector<EngineNext::Serialization::JsonValue> arrEvents;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::AI::AdaptArtifacts(stRequest, stExport, "", stPackage, arrEvents, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Artifact adapter rejects credentials in exported extension payloads")
{
	EngineNext::AI::AiAssetRequest stRequest;
	const EngineNext::Serialization::JsonValue stExport(EngineNext::Serialization::JsonValue::Object{
			{ "extension", EngineNext::Serialization::JsonValue::Object{ { "access_token", "forbidden" } } },
	});
	EngineNext::Assets::PackageData stPackage;
	std::vector<EngineNext::Serialization::JsonValue> arrEvents;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::AI::AdaptArtifacts(stRequest, stExport, "", stPackage, arrEvents, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}
