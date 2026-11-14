/**************************************************************************/
/*  AssetManifest.cpp                                                     */
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

#include "engine_next/include/EngineNext/Assets/AssetManifest.h"

#include "engine_next/Assets/AssetValidation.h"

#include <algorithm>
#include <map>
#include <set>
#include <utility>

namespace EngineNext::Assets
{
namespace
{

Serialization::JsonValue SourceJson(const AssetSource &in_stSource)
{
	Serialization::JsonValue::Object mapSource{ { "kind", in_stSource.strKind } };
	if (in_stSource.strKind == "executor_artifact")
	{
		mapSource["artifact_id"] = in_stSource.strArtifactId;
		mapSource["artifact_revision"] = in_stSource.strArtifactRevision;
	}
	else
	{
		mapSource["importer_version"] = in_stSource.strImporterVersion;
	}
	return Serialization::JsonValue(std::move(mapSource));
}

} // namespace

bool ParseAssetManifest(const Serialization::JsonValue &in_stValue, AssetManifest &out_stManifest, Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_stManifest = AssetManifest{};
	const Serialization::JsonValue::Object *pObject = Object(in_stValue, "$", out_arrDiagnostics);
	if (pObject == nullptr)
	{
		return false;
	}
	Fields(*pObject, { "schema_version", "scene", "assets" }, "$", out_arrDiagnostics);
	std::int64_t nSchema = 0;
	Integer(*pObject, "schema_version", "$", nSchema, out_arrDiagnostics);
	if (nSchema != 1)
	{
		AddDiagnostic(out_arrDiagnostics, "unsupported_schema", "$.schema_version", "expected schema 1");
	}
	const Serialization::JsonValue::Object::const_iterator itScene = pObject->find("scene");
	if (itScene != pObject->end())
	{
		const Serialization::JsonValue::Object *pScene = Object(itScene->second, "$.scene", out_arrDiagnostics);
		if (pScene != nullptr)
		{
			Fields(*pScene, { "scene_id", "scene_revision", "content_sha256" }, "$.scene", out_arrDiagnostics);
			String(*pScene, "scene_id", "$.scene", out_stManifest.strSceneId, out_arrDiagnostics);
			String(*pScene, "scene_revision", "$.scene", out_stManifest.strSceneRevision, out_arrDiagnostics);
			String(*pScene, "content_sha256", "$.scene", out_stManifest.strSceneContentSha256, out_arrDiagnostics);
		}
	}
	const Serialization::JsonValue::Object::const_iterator itAssets = pObject->find("assets");
	const Serialization::JsonValue::List *pAssets = itAssets == pObject->end() ? nullptr : itAssets->second.GetList();
	if (pAssets == nullptr)
	{
		AddDiagnostic(out_arrDiagnostics, "type", "$.assets", "expected array");
	}
	else
	{
		for (std::size_t nIndex = 0; nIndex < pAssets->size(); ++nIndex)
		{
			const std::string strPath = "$.assets[" + std::to_string(nIndex) + "]";
			const Serialization::JsonValue::Object *pAsset = Object((*pAssets)[nIndex], strPath, out_arrDiagnostics);
			if (pAsset == nullptr)
			{
				continue;
			}
			AssetEntry stAsset;
			Fields(*pAsset, { "asset_id", "revision", "type", "media_type", "content_sha256", "byte_size", "dependencies", "source" }, strPath, out_arrDiagnostics);
			String(*pAsset, "asset_id", strPath, stAsset.strAssetId, out_arrDiagnostics);
			String(*pAsset, "revision", strPath, stAsset.strRevision, out_arrDiagnostics);
			String(*pAsset, "type", strPath, stAsset.strType, out_arrDiagnostics);
			String(*pAsset, "media_type", strPath, stAsset.strMediaType, out_arrDiagnostics);
			String(*pAsset, "content_sha256", strPath, stAsset.strContentSha256, out_arrDiagnostics);
			std::int64_t nBytes = 0;
			Integer(*pAsset, "byte_size", strPath, nBytes, out_arrDiagnostics);
			if (nBytes > 0)
			{
				stAsset.nByteSize = static_cast<std::uint64_t>(nBytes);
			}
			const Serialization::JsonValue::Object::const_iterator itDependencies = pAsset->find("dependencies");
			const Serialization::JsonValue::List *pDependencies = itDependencies == pAsset->end() ? nullptr : itDependencies->second.GetList();
			if (pDependencies == nullptr)
			{
				AddDiagnostic(out_arrDiagnostics, "type", strPath + ".dependencies", "expected array");
			}
			else
			{
				for (std::size_t nDependency = 0; nDependency < pDependencies->size(); ++nDependency)
				{
					AssetRef stRef;
					ParseRef((*pDependencies)[nDependency], strPath + ".dependencies[" + std::to_string(nDependency) + "]", stRef, out_arrDiagnostics);
					stAsset.arrDependencies.push_back(std::move(stRef));
				}
			}
			const Serialization::JsonValue::Object::const_iterator itSource = pAsset->find("source");
			if (itSource != pAsset->end())
			{
				const Serialization::JsonValue::Object *pSource = Object(itSource->second, strPath + ".source", out_arrDiagnostics);
				if (pSource != nullptr)
				{
					String(*pSource, "kind", strPath + ".source", stAsset.stSource.strKind, out_arrDiagnostics);
					if (stAsset.stSource.strKind == "executor_artifact")
					{
						Fields(*pSource, { "kind", "artifact_id", "artifact_revision" }, strPath + ".source", out_arrDiagnostics);
						String(*pSource, "artifact_id", strPath + ".source", stAsset.stSource.strArtifactId, out_arrDiagnostics);
						String(*pSource, "artifact_revision", strPath + ".source", stAsset.stSource.strArtifactRevision, out_arrDiagnostics);
					}
					else if (stAsset.stSource.strKind == "godot_whitelist_import")
					{
						Fields(*pSource, { "kind", "importer_version" }, strPath + ".source", out_arrDiagnostics);
						String(*pSource, "importer_version", strPath + ".source", stAsset.stSource.strImporterVersion, out_arrDiagnostics);
					}
					else
					{
						AddDiagnostic(out_arrDiagnostics, "unknown_source", strPath + ".source.kind", "asset provenance is required");
					}
				}
			}
			out_stManifest.arrAssets.push_back(std::move(stAsset));
		}
	}
	SortDiagnostics(out_arrDiagnostics);
	return out_arrDiagnostics.empty();
}

Serialization::JsonValue ToJson(const AssetManifest &in_stManifest)
{
	std::vector<AssetEntry> arrAssets = in_stManifest.arrAssets;
	std::sort(arrAssets.begin(), arrAssets.end(), [](const AssetEntry &in_stLeft, const AssetEntry &in_stRight)
			  { return in_stLeft.strAssetId < in_stRight.strAssetId; });
	Serialization::JsonValue::List arrJsonAssets;
	for (const AssetEntry &stAsset : arrAssets)
	{
		std::vector<AssetRef> arrDependencies = stAsset.arrDependencies;
		std::sort(arrDependencies.begin(), arrDependencies.end(), [](const AssetRef &in_stLeft, const AssetRef &in_stRight)
				  {
			if (in_stLeft.strAssetId != in_stRight.strAssetId)
			{
				return in_stLeft.strAssetId < in_stRight.strAssetId;
			}
			if (in_stLeft.strRevision != in_stRight.strRevision)
			{
				return in_stLeft.strRevision < in_stRight.strRevision;
			}
			return in_stLeft.strContentSha256 < in_stRight.strContentSha256; });
		Serialization::JsonValue::List arrJsonDependencies;
		for (const AssetRef &stRef : arrDependencies)
		{
			arrJsonDependencies.push_back(RefJson(stRef));
		}
		arrJsonAssets.emplace_back(Serialization::JsonValue::Object{
				{ "asset_id", stAsset.strAssetId },
				{ "byte_size", static_cast<std::int64_t>(stAsset.nByteSize) },
				{ "content_sha256", stAsset.strContentSha256 },
				{ "dependencies", std::move(arrJsonDependencies) },
				{ "media_type", stAsset.strMediaType },
				{ "revision", stAsset.strRevision },
				{ "source", SourceJson(stAsset.stSource) },
				{ "type", stAsset.strType },
		});
	}
	return Serialization::JsonValue::Object{
		{ "assets", std::move(arrJsonAssets) },
		{ "scene", Serialization::JsonValue::Object{
						   { "content_sha256", in_stManifest.strSceneContentSha256 },
						   { "scene_id", in_stManifest.strSceneId },
						   { "scene_revision", in_stManifest.strSceneRevision },
				   } },
		{ "schema_version", std::int64_t(1) },
	};
}

bool ValidateAssetManifest(const AssetManifest &in_stManifest, const SceneDocument &in_stScene, Diagnostics &out_arrDiagnostics)
{
	if (!IsIdentity(in_stManifest.strSceneId) || in_stManifest.strSceneId != in_stScene.strSceneId)
	{
		AddDiagnostic(out_arrDiagnostics, "scene_identity", "$.scene.scene_id", "manifest and scene identities differ");
	}
	if (!IsRevision(in_stManifest.strSceneRevision) || in_stManifest.strSceneRevision != in_stScene.strSceneRevision)
	{
		AddDiagnostic(out_arrDiagnostics, "scene_revision", "$.scene.scene_revision", "manifest and scene revisions differ");
	}
	if (!IsSha256(in_stManifest.strSceneContentSha256))
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_digest", "$.scene.content_sha256", "expected scene SHA-256");
	}
	if (in_stManifest.arrAssets.size() > 1024)
	{
		AddDiagnostic(out_arrDiagnostics, "asset_budget", "$.assets", "too many assets");
	}
	std::map<std::string, const AssetEntry *> mapAssets;
	for (std::size_t nIndex = 0; nIndex < in_stManifest.arrAssets.size(); ++nIndex)
	{
		const AssetEntry &stAsset = in_stManifest.arrAssets[nIndex];
		const std::string strPath = "$.assets[" + std::to_string(nIndex) + "]";
		if (!IsIdentity(stAsset.strAssetId) || !mapAssets.emplace(stAsset.strAssetId, &stAsset).second)
		{
			AddDiagnostic(out_arrDiagnostics, "duplicate_asset_id", strPath + ".asset_id", "asset IDs must be valid and unique");
		}
		if (!IsRevision(stAsset.strRevision))
		{
			AddDiagnostic(out_arrDiagnostics, "invalid_revision", strPath + ".revision", "invalid asset revision");
		}
		const bool bImage = stAsset.strType == "image";
		const bool bMesh = stAsset.strType == "mesh";
		if ((!bImage && !bMesh) ||
			(bImage && stAsset.strMediaType != "image/png" && stAsset.strMediaType != "image/jpeg") ||
			(bMesh && stAsset.strMediaType != "model/gltf-binary"))
		{
			AddDiagnostic(out_arrDiagnostics, "unsupported_asset_type", strPath, "asset type and media type are inconsistent or unsupported");
		}
		if (!IsSha256(stAsset.strContentSha256) || stAsset.nByteSize == 0 || stAsset.nByteSize > 64ULL * 1024ULL * 1024ULL)
		{
			AddDiagnostic(out_arrDiagnostics, "invalid_blob", strPath, "invalid digest or byte budget");
		}
		if (stAsset.arrDependencies.size() > 256)
		{
			AddDiagnostic(out_arrDiagnostics, "dependency_budget", strPath + ".dependencies", "too many dependencies");
		}
		std::set<std::string> setDependencies;
		for (const AssetRef &stRef : stAsset.arrDependencies)
		{
			if (stRef.strAssetId == stAsset.strAssetId || !setDependencies.insert(stRef.strAssetId).second)
			{
				AddDiagnostic(out_arrDiagnostics, "duplicate_dependency", strPath + ".dependencies", "self and duplicate dependencies are forbidden");
			}
		}
		const bool bArtifact = stAsset.stSource.strKind == "executor_artifact" && IsIdentity(stAsset.stSource.strArtifactId) && IsRevision(stAsset.stSource.strArtifactRevision);
		const bool bImport = stAsset.stSource.strKind == "godot_whitelist_import" && stAsset.stSource.strImporterVersion == "1";
		if (!bArtifact && !bImport)
		{
			AddDiagnostic(out_arrDiagnostics, "unknown_source", strPath + ".source", "asset provenance is missing or invalid");
		}
	}
	for (const AssetEntry &stAsset : in_stManifest.arrAssets)
	{
		for (const AssetRef &stRef : stAsset.arrDependencies)
		{
			const std::map<std::string, const AssetEntry *>::const_iterator itDependency = mapAssets.find(stRef.strAssetId);
			if (itDependency == mapAssets.end() || stRef.strRevision != itDependency->second->strRevision || stRef.strContentSha256 != itDependency->second->strContentSha256)
			{
				AddDiagnostic(out_arrDiagnostics, "dangling_dependency", "$.assets", "dependency reference is unresolved");
			}
		}
	}
	std::map<std::string, std::size_t> mapRemaining;
	std::map<std::string, std::vector<std::string>> mapDependents;
	std::set<std::string> setReady;
	for (const std::pair<const std::string, const AssetEntry *> &stEntry : mapAssets)
	{
		std::size_t nDependencies = 0;
		for (const AssetRef &stRef : stEntry.second->arrDependencies)
		{
			if (mapAssets.find(stRef.strAssetId) != mapAssets.end())
			{
				++nDependencies;
				mapDependents[stRef.strAssetId].push_back(stEntry.first);
			}
		}
		mapRemaining[stEntry.first] = nDependencies;
		if (nDependencies == 0)
		{
			setReady.insert(stEntry.first);
		}
	}
	std::size_t nVisited = 0;
	while (!setReady.empty())
	{
		const std::string strCurrent = *setReady.begin();
		setReady.erase(setReady.begin());
		++nVisited;
		for (const std::string &strDependent : mapDependents[strCurrent])
		{
			std::size_t &nRemaining = mapRemaining[strDependent];
			if (nRemaining > 0 && --nRemaining == 0)
			{
				setReady.insert(strDependent);
			}
		}
	}
	if (nVisited != mapAssets.size())
	{
		AddDiagnostic(out_arrDiagnostics, "dependency_cycle", "$.assets", "asset dependency cycle");
	}
	std::set<std::string> setRequired;
	for (const SceneEntity &stEntity : in_stScene.arrEntities)
	{
		for (const SceneAssetRef &stRef : stEntity.arrAssets)
		{
			const std::map<std::string, const AssetEntry *>::const_iterator itAsset = mapAssets.find(stRef.stAsset.strAssetId);
			if (itAsset == mapAssets.end() || stRef.stAsset.strRevision != itAsset->second->strRevision ||
				stRef.stAsset.strContentSha256 != itAsset->second->strContentSha256)
			{
				AddDiagnostic(out_arrDiagnostics, "dangling_scene_reference", "$.entities", "scene asset reference is unresolved");
				continue;
			}
			setRequired.insert(stRef.stAsset.strAssetId);
			if (stRef.strRole == "mesh" && itAsset->second->strType != "mesh")
			{
				AddDiagnostic(out_arrDiagnostics, "asset_type_mismatch", "$.entities", "mesh role requires a mesh asset");
			}
			if (stRef.strRole == "texture" && itAsset->second->strType != "image")
			{
				AddDiagnostic(out_arrDiagnostics, "asset_type_mismatch", "$.entities", "texture role requires an image asset");
			}
		}
	}
	bool bChanged = true;
	while (bChanged)
	{
		bChanged = false;
		for (const AssetEntry &stAsset : in_stManifest.arrAssets)
		{
			if (setRequired.find(stAsset.strAssetId) == setRequired.end())
			{
				continue;
			}
			for (const AssetRef &stRef : stAsset.arrDependencies)
			{
				bChanged = setRequired.insert(stRef.strAssetId).second || bChanged;
			}
		}
	}
	if (setRequired.size() != mapAssets.size())
	{
		AddDiagnostic(out_arrDiagnostics, "unreferenced_asset", "$.assets", "manifest contains assets outside the scene dependency closure");
	}
	SortDiagnostics(out_arrDiagnostics);
	return out_arrDiagnostics.empty();
}

} // namespace EngineNext::Assets
