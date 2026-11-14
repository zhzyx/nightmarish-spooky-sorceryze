/**************************************************************************/
/*  TestAssetManifest.cpp                                                 */
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
#include "engine_next/include/EngineNext/Assets/AssetManifest.h"

#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <utility>

namespace
{

const char *DIGEST = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

EngineNext::Assets::AssetEntry ValidAsset(const std::string &in_strId)
{
	EngineNext::Assets::AssetEntry stAsset;
	stAsset.strAssetId = in_strId;
	stAsset.strRevision = "r1";
	stAsset.strType = "mesh";
	stAsset.strMediaType = "model/gltf-binary";
	stAsset.strContentSha256 = DIGEST;
	stAsset.nByteSize = 100;
	stAsset.stSource.strKind = "executor_artifact";
	stAsset.stSource.strArtifactId = "output";
	stAsset.stSource.strArtifactRevision = "a1";
	return stAsset;
}

EngineNext::Assets::SceneDocument SceneWithAsset(EngineNext::Assets::AssetRef in_stRef)
{
	EngineNext::Assets::SceneDocument stScene;
	stScene.strSceneId = "m3.test";
	stScene.strSceneRevision = "r2";
	EngineNext::Assets::SceneEntity stEntity;
	stEntity.nEntityId = 1;
	stEntity.strName = "mesh";
	stEntity.strNodeType = "MeshInstance3D";
	stEntity.strGameplayKind = "static";
	stEntity.arrAssets.push_back(EngineNext::Assets::SceneAssetRef{ "mesh", in_stRef });
	stScene.arrEntities.push_back(stEntity);
	return stScene;
}

EngineNext::Assets::AssetManifest ValidManifest(EngineNext::Assets::AssetEntry in_stAsset)
{
	EngineNext::Assets::AssetManifest stManifest;
	stManifest.strSceneId = "m3.test";
	stManifest.strSceneRevision = "r2";
	stManifest.strSceneContentSha256 = DIGEST;
	stManifest.arrAssets.push_back(std::move(in_stAsset));
	return stManifest;
}

void BindScene(EngineNext::Assets::AssetManifest &out_stManifest, const EngineNext::Assets::SceneDocument &in_stScene)
{
	std::string strBytes;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(in_stScene), strBytes));
	out_stManifest.strSceneContentSha256 = EngineNext::Serialization::Sha256Hex(strBytes);
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

ENGINE_NEXT_TEST("Asset manifest roundtrip and scene closure are stable")
{
	EngineNext::Assets::AssetManifest stManifest = ValidManifest(ValidAsset("mesh"));
	EngineNext::Assets::SceneDocument stScene = SceneWithAsset(EngineNext::Assets::AssetRef{ "mesh", "r1", DIGEST });
	EngineNext::Assets::Diagnostics arrDiagnostics;
	BindScene(stManifest, stScene);
	ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateAssetManifest(stManifest, stScene, arrDiagnostics));
	std::string strFirst;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stManifest), strFirst));
	EngineNext::Serialization::JsonValue stValue;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(strFirst, stValue, strError));
	EngineNext::Assets::AssetManifest stParsed;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ParseAssetManifest(stValue, stParsed, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateAssetManifest(stParsed, stScene, arrDiagnostics));
	std::string strSecond;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stParsed), strSecond));
	ENGINE_NEXT_CHECK_EQ(strFirst, strSecond);
}

ENGINE_NEXT_TEST("Asset manifest rejects duplicate, dangling and unreferenced assets")
{
	EngineNext::Assets::AssetManifest stManifest = ValidManifest(ValidAsset("mesh"));
	stManifest.arrAssets.push_back(ValidAsset("mesh"));
	EngineNext::Assets::SceneDocument stScene = SceneWithAsset(EngineNext::Assets::AssetRef{ "mesh", "r1", DIGEST });
	EngineNext::Assets::Diagnostics arrDiagnostics;
	BindScene(stManifest, stScene);
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateAssetManifest(stManifest, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "duplicate_asset_id"));

	stManifest = ValidManifest(ValidAsset("mesh"));
	stManifest.arrAssets.push_back(ValidAsset("unused"));
	arrDiagnostics.clear();
	BindScene(stManifest, stScene);
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateAssetManifest(stManifest, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "unreferenced_asset"));

	stManifest = ValidManifest(ValidAsset("mesh"));
	stManifest.arrAssets[0].arrDependencies.push_back(EngineNext::Assets::AssetRef{ "missing", "r1", DIGEST });
	arrDiagnostics.clear();
	BindScene(stManifest, stScene);
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateAssetManifest(stManifest, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "dangling_dependency"));
}

ENGINE_NEXT_TEST("Asset manifest detects cycles independent of input order")
{
	EngineNext::Assets::AssetEntry stFirst = ValidAsset("first");
	EngineNext::Assets::AssetEntry stSecond = ValidAsset("second");
	stFirst.arrDependencies.push_back(EngineNext::Assets::AssetRef{ "second", "r1", DIGEST });
	stSecond.arrDependencies.push_back(EngineNext::Assets::AssetRef{ "first", "r1", DIGEST });
	EngineNext::Assets::AssetManifest stManifest = ValidManifest(stFirst);
	stManifest.arrAssets.push_back(stSecond);
	EngineNext::Assets::SceneDocument stScene = SceneWithAsset(EngineNext::Assets::AssetRef{ "first", "r1", DIGEST });
	EngineNext::Assets::Diagnostics arrDiagnostics;
	BindScene(stManifest, stScene);
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateAssetManifest(stManifest, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "dependency_cycle"));
}

ENGINE_NEXT_TEST("Asset manifest binds the exact canonical scene digest")
{
	EngineNext::Assets::AssetManifest stManifest = ValidManifest(ValidAsset("mesh"));
	EngineNext::Assets::SceneDocument stScene = SceneWithAsset(EngineNext::Assets::AssetRef{ "mesh", "r1", DIGEST });
	BindScene(stManifest, stScene);
	stScene.arrEntities[0].stTransform.arrTranslation[0] = 3.0;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateAssetManifest(stManifest, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK(HasCode(arrDiagnostics, "scene_digest_mismatch"));
}
