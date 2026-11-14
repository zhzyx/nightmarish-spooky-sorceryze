/**************************************************************************/
/*  TestSceneDocument.cpp                                                 */
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
#include "engine_next/include/EngineNext/Assets/SceneDocument.h"

namespace
{

EngineNext::Assets::SceneDocument ValidScene()
{
	EngineNext::Assets::SceneDocument stScene;
	stScene.strSceneId = "m3.test";
	stScene.strSceneRevision = "r1";
	EngineNext::Assets::SceneEntity stEntity;
	stEntity.nEntityId = 101;
	stEntity.strName = "player";
	stEntity.strNodeType = "Node3D";
	stEntity.strGameplayKind = "player_spawn";
	stScene.arrEntities.push_back(stEntity);
	return stScene;
}

bool HasCode(const EngineNext::Assets::Diagnostics &in_arrDiagnostics, const std::string &in_strCode)
{
	for (const EngineNext::Assets::Diagnostic &stDiagnostic : in_arrDiagnostics)
	{
		if (stDiagnostic.strCode == in_strCode)
		{
			return true;
		}
	}
	return false;
}

} // namespace

ENGINE_NEXT_TEST("Scene document roundtrip is canonical and ordered")
{
	EngineNext::Assets::SceneDocument stScene = ValidScene();
	stScene.arrEntities.push_back(stScene.arrEntities.front());
	stScene.arrEntities.back().nEntityId = 205;
	stScene.arrEntities.back().strName = "other";
	stScene.arrEntities.back().stTransform.arrTranslation[0] = 2.0;
	std::string strFirst;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stScene), strFirst));
	EngineNext::Serialization::JsonValue stValue;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(strFirst, stValue, strError));
	EngineNext::Assets::SceneDocument stParsed;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ParseSceneDocument(stValue, stParsed, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stParsed.arrEntities.size(), 2ULL);
	ENGINE_NEXT_CHECK_EQ(stParsed.arrEntities[1].nEntityId, 205);
	std::string strSecond;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stParsed), strSecond));
	ENGINE_NEXT_CHECK_EQ(strFirst, strSecond);
}

ENGINE_NEXT_TEST("Scene rejects identity, parent, transform and gameplay errors")
{
	EngineNext::Assets::SceneDocument stScene = ValidScene();
	stScene.arrEntities.push_back(stScene.arrEntities.front());
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateSceneDocument(stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "duplicate_entity_id"));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "duplicate_entity_name"));

	stScene = ValidScene();
	stScene.arrEntities[0].nParentEntityId = 101;
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateSceneDocument(stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "parent_cycle"));

	stScene = ValidScene();
	stScene.arrEntities[0].stTransform.arrRotation[3] = 2.0;
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateSceneDocument(stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "invalid_rotation"));

	stScene = ValidScene();
	stScene.nFixedStepMsec = 0;
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateSceneDocument(stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "invalid_fixed_step"));
}

ENGINE_NEXT_TEST("Scene parser rejects unknown fields and script payloads")
{
	EngineNext::Serialization::JsonValue stValue = EngineNext::Assets::ToJson(ValidScene());
	stValue.GetObject()->emplace("script", "res://bad.gd");
	EngineNext::Assets::SceneDocument stScene;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ParseSceneDocument(stValue, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "unknown_field"));
}
