/**************************************************************************/
/*  AssetCompiler.cpp                                                     */
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

#include "engine_next/include/EngineNext/Assets/AssetCompiler.h"

#include "engine_next/Assets/AssetValidation.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <filesystem>
#include <fstream>
#include <limits>

namespace EngineNext::Assets
{
namespace
{

bool ReadFile(const std::string &in_strRoot, const std::string &in_strRelative, std::vector<std::uint8_t> &out_arrBytes, Diagnostics &out_arrDiagnostics)
{
	namespace fs = std::filesystem;
	if (!SafeAssetRelativePath(in_strRelative))
	{
		AddDiagnostic(out_arrDiagnostics, "path_escape", in_strRelative, "input must be a canonical relative path");
		return false;
	}
	const fs::path stRoot(in_strRoot);
	const fs::path stPath = stRoot / in_strRelative;
	if (!NoLinkedComponents(stRoot) || !NoLinkedComponents(stPath))
	{
		AddDiagnostic(out_arrDiagnostics, "symbolic_link", in_strRelative, "source path cannot contain symbolic links");
		return false;
	}
	std::error_code stError;
	const fs::file_status stStatus = fs::symlink_status(stPath, stError);
	if (stError || fs::is_symlink(stStatus) || !fs::is_regular_file(stStatus))
	{
		AddDiagnostic(out_arrDiagnostics, "input_type", in_strRelative, "input must be a regular file without symbolic links");
		return false;
	}
	std::ifstream stStream(stPath, std::ios::binary | std::ios::ate);
	if (!stStream)
	{
		AddDiagnostic(out_arrDiagnostics, "read_failed", in_strRelative, "unable to open input");
		return false;
	}
	const std::streamoff nSize = stStream.tellg();
	if (nSize <= 0 || nSize > 64 * 1024 * 1024)
	{
		AddDiagnostic(out_arrDiagnostics, "input_budget", in_strRelative, "input exceeds blob budget");
		return false;
	}
	out_arrBytes.resize(static_cast<std::size_t>(nSize));
	stStream.seekg(0);
	stStream.read(reinterpret_cast<char *>(out_arrBytes.data()), nSize);
	if (!stStream)
	{
		AddDiagnostic(out_arrDiagnostics, "read_failed", in_strRelative, "input read was incomplete");
		return false;
	}
	return true;
}

bool ParseSource(const Serialization::JsonValue &in_stValue, const std::string &in_strPath, AssetSource &out_stSource, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pSource = Object(in_stValue, in_strPath, out_arrDiagnostics);
	if (pSource == nullptr)
	{
		return false;
	}
	String(*pSource, "kind", in_strPath, out_stSource.strKind, out_arrDiagnostics);
	if (out_stSource.strKind == "executor_artifact")
	{
		Fields(*pSource, { "kind", "artifact_id", "artifact_revision" }, in_strPath, out_arrDiagnostics);
		String(*pSource, "artifact_id", in_strPath, out_stSource.strArtifactId, out_arrDiagnostics);
		String(*pSource, "artifact_revision", in_strPath, out_stSource.strArtifactRevision, out_arrDiagnostics);
	}
	else if (out_stSource.strKind == "godot_whitelist_import")
	{
		Fields(*pSource, { "kind", "importer_version" }, in_strPath, out_arrDiagnostics);
		String(*pSource, "importer_version", in_strPath, out_stSource.strImporterVersion, out_arrDiagnostics);
	}
	else
	{
		AddDiagnostic(out_arrDiagnostics, "unknown_source", in_strPath + ".kind", "unsupported asset provenance");
	}
	return true;
}

} // namespace

bool ParseBuildRequest(const Serialization::JsonValue &in_stValue, BuildRequest &out_stRequest, Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_stRequest = BuildRequest{};
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
		(void)ParseSceneDocument(itScene->second, out_stRequest.stScene, out_arrDiagnostics);
	}
	const Serialization::JsonValue::Object::const_iterator itAssets = pObject->find("assets");
	const Serialization::JsonValue::List *pAssets = itAssets == pObject->end() ? nullptr : itAssets->second.GetList();
	if (pAssets == nullptr)
	{
		AddDiagnostic(out_arrDiagnostics, "type", "$.assets", "expected array");
		return false;
	}
	for (std::size_t nIndex = 0; nIndex < pAssets->size(); ++nIndex)
	{
		const std::string strPath = "$.assets[" + std::to_string(nIndex) + "]";
		const Serialization::JsonValue::Object *pAsset = Object((*pAssets)[nIndex], strPath, out_arrDiagnostics);
		if (pAsset == nullptr)
		{
			continue;
		}
		Fields(*pAsset, { "asset_id", "revision", "type", "media_type", "dependencies", "source", "path" }, strPath, out_arrDiagnostics);
		AssetInput stInput;
		String(*pAsset, "asset_id", strPath, stInput.stAsset.strAssetId, out_arrDiagnostics);
		String(*pAsset, "revision", strPath, stInput.stAsset.strRevision, out_arrDiagnostics);
		String(*pAsset, "type", strPath, stInput.stAsset.strType, out_arrDiagnostics);
		String(*pAsset, "media_type", strPath, stInput.stAsset.strMediaType, out_arrDiagnostics);
		String(*pAsset, "path", strPath, stInput.strPath, out_arrDiagnostics);
		const Serialization::JsonValue::Object::const_iterator itSource = pAsset->find("source");
		if (itSource != pAsset->end())
		{
			(void)ParseSource(itSource->second, strPath + ".source", stInput.stAsset.stSource, out_arrDiagnostics);
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
				(void)ParseRef((*pDependencies)[nDependency], strPath + ".dependencies[" + std::to_string(nDependency) + "]", stRef, out_arrDiagnostics);
				stInput.stAsset.arrDependencies.push_back(std::move(stRef));
			}
		}
		out_stRequest.arrAssets.push_back(std::move(stInput));
	}
	SortDiagnostics(out_arrDiagnostics);
	return out_arrDiagnostics.empty();
}

bool CompilePackage(const std::string &in_strSourceRoot, const BuildRequest &in_stRequest, PackageData &out_stPackage, Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_stPackage = PackageData{};
	out_stPackage.stScene = in_stRequest.stScene;
	out_stPackage.stManifest.strSceneId = in_stRequest.stScene.strSceneId;
	out_stPackage.stManifest.strSceneRevision = in_stRequest.stScene.strSceneRevision;
	std::uint64_t nTotalBytes = 0;
	for (const AssetInput &stInput : in_stRequest.arrAssets)
	{
		AssetEntry stAsset = stInput.stAsset;
		std::vector<std::uint8_t> arrBytes;
		if (!ReadFile(in_strSourceRoot, stInput.strPath, arrBytes, out_arrDiagnostics))
		{
			continue;
		}
		BlobInfo stInfo;
		if (!ValidateBlob(stAsset.strMediaType, arrBytes, stInfo, out_arrDiagnostics))
		{
			continue;
		}
		stAsset.nByteSize = arrBytes.size();
		stAsset.strContentSha256 = Serialization::Sha256Hex(arrBytes.data(), arrBytes.size());
		nTotalBytes += arrBytes.size();
		out_stPackage.mapBlobs.emplace(stAsset.strContentSha256, std::move(arrBytes));
		out_stPackage.stManifest.arrAssets.push_back(std::move(stAsset));
	}
	if (nTotalBytes > 256ULL * 1024ULL * 1024ULL)
	{
		AddDiagnostic(out_arrDiagnostics, "package_budget", "$", "total blob budget exceeded");
	}
	if (!out_arrDiagnostics.empty())
	{
		return false;
	}
	if (!Serialization::CanonicalJson(ToJson(out_stPackage.stScene), out_stPackage.strSceneJson))
	{
		AddDiagnostic(out_arrDiagnostics, "scene_serialization", "$", "unable to serialize scene");
		return false;
	}
	out_stPackage.stManifest.strSceneContentSha256 = Serialization::Sha256Hex(out_stPackage.strSceneJson);
	if (!ValidateAssetManifest(out_stPackage.stManifest, out_stPackage.stScene, out_arrDiagnostics))
	{
		return false;
	}
	if (!Serialization::CanonicalJson(ToJson(out_stPackage.stManifest), out_stPackage.strManifestJson))
	{
		AddDiagnostic(out_arrDiagnostics, "manifest_serialization", "$", "unable to serialize manifest");
		return false;
	}
	out_stPackage.strManifestSha256 = Serialization::Sha256Hex(out_stPackage.strManifestJson);
	return ComputePackageDigest(out_stPackage, out_arrDiagnostics);
}

} // namespace EngineNext::Assets
