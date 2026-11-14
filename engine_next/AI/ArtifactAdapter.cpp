/**************************************************************************/
/*  ArtifactAdapter.cpp                                                   */
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

#include "engine_next/include/EngineNext/AI/ArtifactAdapter.h"

#include "engine_next/Assets/AssetValidation.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <filesystem>
#include <fstream>
#include <set>

namespace EngineNext::AI
{
namespace
{

const Serialization::JsonValue *Member(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapObject.find(in_strName);
	return it == in_mapObject.end() ? nullptr : &it->second;
}

const Serialization::JsonValue::Object *ObjectMember(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName)
{
	const Serialization::JsonValue *pValue = Member(in_mapObject, in_strName);
	return pValue == nullptr ? nullptr : pValue->GetObject();
}

const Serialization::JsonValue::List *ListMember(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName)
{
	const Serialization::JsonValue *pValue = Member(in_mapObject, in_strName);
	return pValue == nullptr ? nullptr : pValue->GetList();
}

bool TextMember(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName, std::string &out_strValue)
{
	const Serialization::JsonValue *pValue = Member(in_mapObject, in_strName);
	const std::string *pText = pValue == nullptr ? nullptr : pValue->GetString();
	if (pText == nullptr)
	{
		return false;
	}
	out_strValue = *pText;
	return true;
}

bool Forbidden(const Serialization::JsonValue &in_stValue)
{
	static const std::vector<std::string> arrFragments = {
		"token",
		"secret",
		"password",
		"passwd",
		"credential",
		"authorization",
		"api_key",
		"apikey",
		"private_key",
		"access_key",
		"session_key",
		"cookie",
		"factory",
		"python",
	};
	if (const Serialization::JsonValue::Object *pObject = in_stValue.GetObject())
	{
		for (const std::pair<const std::string, Serialization::JsonValue> &stEntry : *pObject)
		{
			std::string strLower = stEntry.first;
			for (char &nCharacter : strLower)
			{
				if (nCharacter >= 'A' && nCharacter <= 'Z')
				{
					nCharacter = static_cast<char>(nCharacter - 'A' + 'a');
				}
			}
			bool bSensitive = false;
			for (const std::string &strFragment : arrFragments)
			{
				bSensitive = bSensitive || strLower.find(strFragment) != std::string::npos;
			}
			if (bSensitive || Forbidden(stEntry.second))
			{
				return true;
			}
		}
	}
	if (const Serialization::JsonValue::List *pList = in_stValue.GetList())
	{
		for (const Serialization::JsonValue &stItem : *pList)
		{
			if (Forbidden(stItem))
			{
				return true;
			}
		}
	}
	return false;
}

bool DecodeBase64(const std::string &in_strInput, std::vector<std::uint8_t> &out_arrBytes)
{
	static const std::string strAlphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	out_arrBytes.clear();
	if (in_strInput.empty() || in_strInput.size() % 4 != 0)
	{
		return false;
	}
	std::size_t nPadding = 0;
	if (in_strInput.back() == '=')
	{
		nPadding = 1;
		if (in_strInput.size() >= 2 && in_strInput[in_strInput.size() - 2] == '=')
		{
			nPadding = 2;
		}
	}
	if (nPadding == 2 && in_strInput.size() < 4)
	{
		return false;
	}
	for (std::size_t nIndex = 0; nIndex < in_strInput.size() - nPadding; ++nIndex)
	{
		if (strAlphabet.find(in_strInput[nIndex]) == std::string::npos)
		{
			return false;
		}
	}
	for (std::size_t nIndex = in_strInput.size() - nPadding; nIndex < in_strInput.size(); ++nIndex)
	{
		if (in_strInput[nIndex] != '=')
		{
			return false;
		}
	}
	std::uint32_t nAccumulator = 0;
	int nBits = 0;
	for (std::size_t nIndex = 0; nIndex < in_strInput.size() - nPadding; ++nIndex)
	{
		nAccumulator = (nAccumulator << 6U) | static_cast<std::uint32_t>(strAlphabet.find(in_strInput[nIndex]));
		nBits += 6;
		if (nBits >= 8)
		{
			nBits -= 8;
			out_arrBytes.push_back(static_cast<std::uint8_t>((nAccumulator >> nBits) & 0xFFU));
		}
	}
	const std::size_t nExpected = in_strInput.size() / 4 * 3 - nPadding;
	if (out_arrBytes.size() != nExpected || (nPadding != 0 && (nAccumulator & ((1U << (nPadding * 2)) - 1U)) != 0))
	{
		out_arrBytes.clear();
		return false;
	}
	return true;
}

const Serialization::JsonValue *ArtifactByRef(const Serialization::JsonValue &in_stExport, const Serialization::JsonValue &in_stRef)
{
	const Serialization::JsonValue::Object *pRef = in_stRef.GetObject();
	if (pRef == nullptr)
	{
		return nullptr;
	}
	std::string strId;
	std::string strRevision;
	if (!TextMember(*pRef, "id", strId) || !TextMember(*pRef, "revision", strRevision))
	{
		return nullptr;
	}
	const Serialization::JsonValue::Object *pExport = in_stExport.GetObject();
	const Serialization::JsonValue::Object *pManifest = pExport == nullptr ? nullptr : ObjectMember(*pExport, "manifest");
	const Serialization::JsonValue::List *pArtifacts = pManifest == nullptr ? nullptr : ListMember(*pManifest, "artifacts");
	if (pArtifacts == nullptr)
	{
		return nullptr;
	}
	for (const Serialization::JsonValue &stArtifact : *pArtifacts)
	{
		const Serialization::JsonValue::Object *pArtifact = stArtifact.GetObject();
		if (pArtifact == nullptr)
		{
			continue;
		}
		std::string strCandidateId;
		std::string strCandidateRevision;
		if (TextMember(*pArtifact, "id", strCandidateId) && TextMember(*pArtifact, "revision", strCandidateRevision) &&
				strCandidateId == strId && strCandidateRevision == strRevision)
		{
			return &stArtifact;
		}
	}
	return nullptr;
}

bool CacheBlob(const std::string &in_strStateDirectory, const std::vector<std::uint8_t> &in_arrBytes, std::string &out_strDigest, Assets::Diagnostics &out_arrDiagnostics)
{
	namespace fs = std::filesystem;
	out_strDigest = Serialization::Sha256Hex(in_arrBytes.data(), in_arrBytes.size());
	const fs::path stRoot = fs::path(in_strStateDirectory) / "blob-cache";
	std::error_code stError;
	fs::create_directories(stRoot, stError);
	if (stError || !Assets::NoLinkedComponents(stRoot))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "cache_path", "$", "invalid or linked blob cache");
		return false;
	}
	const fs::path stPath = stRoot / out_strDigest;
	if (fs::exists(stPath, stError))
	{
		if (stError)
		{
			return false;
		}
		std::ifstream stExisting(stPath, std::ios::binary | std::ios::ate);
		if (!stExisting)
		{
			return false;
		}
		const std::streamoff nSize = stExisting.tellg();
		if (nSize != static_cast<std::streamoff>(in_arrBytes.size()))
		{
			return false;
		}
		std::vector<std::uint8_t> arrExisting(in_arrBytes.size());
		stExisting.seekg(0);
		if (!arrExisting.empty())
		{
			stExisting.read(reinterpret_cast<char *>(arrExisting.data()), nSize);
		}
		return stExisting.good() && arrExisting == in_arrBytes;
	}
	std::ofstream stStream(stPath, std::ios::binary | std::ios::out);
	if (!stStream)
	{
		return false;
	}
	if (!in_arrBytes.empty())
	{
		stStream.write(reinterpret_cast<const char *>(in_arrBytes.data()), static_cast<std::streamsize>(in_arrBytes.size()));
	}
	stStream.close();
	return stStream.good();
}

} // namespace

bool ParseAiAssetRequest(const Serialization::JsonValue &in_stValue, AiAssetRequest &out_stRequest, Assets::Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_stRequest = AiAssetRequest{};
	const Serialization::JsonValue::Object *pObject = Assets::Object(in_stValue, "$", out_arrDiagnostics);
	if (pObject == nullptr)
	{
		return false;
	}
	Assets::Fields(*pObject, { "schema_version", "request_id", "model", "graph", "manifest", "scene_template", "asset_bindings" }, "$", out_arrDiagnostics);
	std::int64_t nSchema = 0;
	(void)Assets::Integer(*pObject, "schema_version", "$", nSchema, out_arrDiagnostics);
	if (nSchema != 1)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "unsupported_schema", "$.schema_version", "expected schema 1");
	}
	(void)Assets::String(*pObject, "request_id", "$", out_stRequest.strRequestId, out_arrDiagnostics);
	if (!Assets::IsIdentity(out_stRequest.strRequestId))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "invalid_request", "$.request_id", "invalid request identity");
	}
	const Serialization::JsonValue *pModel = Member(*pObject, "model");
	const Serialization::JsonValue *pGraph = Member(*pObject, "graph");
	const Serialization::JsonValue *pManifest = Member(*pObject, "manifest");
	out_stRequest.stModel = pModel == nullptr ? Serialization::JsonValue() : *pModel;
	out_stRequest.stGraph = pGraph == nullptr ? Serialization::JsonValue() : *pGraph;
	out_stRequest.stManifest = pManifest == nullptr ? Serialization::JsonValue() : *pManifest;
	if (!out_stRequest.stModel.IsObject() || !out_stRequest.stGraph.IsList() || !out_stRequest.stManifest.IsObject() || Forbidden(in_stValue))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "unsafe_request", "$", "invalid model/graph/manifest or forbidden credential field");
	}
	const Serialization::JsonValue *pScene = Member(*pObject, "scene_template");
	if (pScene != nullptr)
	{
		(void)Assets::ParseSceneDocument(*pScene, out_stRequest.stSceneTemplate, out_arrDiagnostics);
	}
	const Serialization::JsonValue::List *pBindings = ListMember(*pObject, "asset_bindings");
	if (pBindings == nullptr)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "type", "$.asset_bindings", "expected array");
	}
	else
	{
		for (std::size_t nIndex = 0; nIndex < pBindings->size(); ++nIndex)
		{
			const std::string strPath = "$.asset_bindings[" + std::to_string(nIndex) + "]";
			const Serialization::JsonValue::Object *pBinding = Assets::Object((*pBindings)[nIndex], strPath, out_arrDiagnostics);
			if (pBinding == nullptr)
			{
				continue;
			}
			(void)Assets::Fields(*pBinding, { "asset_id", "role", "output" }, strPath, out_arrDiagnostics);
			AssetBinding stBinding;
			(void)Assets::String(*pBinding, "asset_id", strPath, stBinding.strAssetId, out_arrDiagnostics);
			(void)Assets::String(*pBinding, "role", strPath, stBinding.strRole, out_arrDiagnostics);
			const Serialization::JsonValue::Object *pOutput = ObjectMember(*pBinding, "output");
			if (pOutput != nullptr)
			{
				(void)Assets::Fields(*pOutput, { "node", "port" }, strPath + ".output", out_arrDiagnostics);
				(void)Assets::String(*pOutput, "node", strPath + ".output", stBinding.strNode, out_arrDiagnostics);
				(void)Assets::String(*pOutput, "port", strPath + ".output", stBinding.strPort, out_arrDiagnostics);
			}
			out_stRequest.arrBindings.push_back(std::move(stBinding));
		}
	}
	Assets::SortDiagnostics(out_arrDiagnostics);
	return out_arrDiagnostics.empty();
}

bool AdaptArtifacts(const AiAssetRequest &in_stRequest, const Serialization::JsonValue &in_stExport,
		const std::string &in_strStateDirectory, Assets::PackageData &out_stPackage,
		std::vector<Serialization::JsonValue> &out_arrArtifactEvents, Assets::Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_arrArtifactEvents.clear();
	if (Forbidden(in_stExport))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "credential_in_artifact", "$", "Executor result contains a forbidden credential field");
		return false;
	}
	Assets::BuildRequest stBuild;
	stBuild.stScene = in_stRequest.stSceneTemplate;
	std::set<std::string> setBindings;
	for (const AssetBinding &stBinding : in_stRequest.arrBindings)
	{
		if (!setBindings.insert(stBinding.strAssetId).second)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "duplicate_binding", "$.asset_bindings", "duplicate asset binding");
			return false;
		}
		const Serialization::JsonValue::Object *pExport = in_stExport.GetObject();
		const Serialization::JsonValue::Object *pOutputs = pExport == nullptr ? nullptr : ObjectMember(*pExport, "outputs");
		const Serialization::JsonValue::Object *pNode = pOutputs == nullptr ? nullptr : ObjectMember(*pOutputs, stBinding.strNode);
		const Serialization::JsonValue *pRef = pNode == nullptr ? nullptr : Member(*pNode, stBinding.strPort);
		const Serialization::JsonValue *pArtifact = pRef == nullptr ? nullptr : ArtifactByRef(in_stExport, *pRef);
		if (pArtifact == nullptr)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "missing_artifact_output", "$.asset_bindings", "bound Executor output is missing");
			return false;
		}
		const Serialization::JsonValue::Object *pArtifactObject = pArtifact->GetObject();
		const Serialization::JsonValue::Object *pPayload = pArtifactObject == nullptr ? nullptr : ObjectMember(*pArtifactObject, "payload");
		if (pPayload == nullptr)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "invalid_artifact_content", "$.asset_bindings", "artifact payload must be an object");
			return false;
		}
		std::string strEncoded;
		std::string strDeclaredDigest;
		std::string strExtension;
		std::string strId;
		std::string strRevision;
		std::string strType;
		if (!TextMember(*pPayload, "content_base64", strEncoded) || !TextMember(*pPayload, "content_sha256", strDeclaredDigest) ||
				!TextMember(*pPayload, "extension", strExtension) || !TextMember(*pArtifactObject, "id", strId) ||
				!TextMember(*pArtifactObject, "revision", strRevision) || !TextMember(*pArtifactObject, "type", strType))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "invalid_artifact_content", "$.asset_bindings", "artifact requires immutable inline content");
			return false;
		}
		constexpr std::size_t MAX_ENCODED_BYTES = 4ULL * ((64ULL * 1024ULL * 1024ULL + 2ULL) / 3ULL);
		if (strEncoded.size() > MAX_ENCODED_BYTES)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "input_budget", "$.asset_bindings", "encoded artifact exceeds the per-file budget");
			return false;
		}
		std::vector<std::uint8_t> arrBytes;
		if (!DecodeBase64(strEncoded, arrBytes) || arrBytes.size() > 64ULL * 1024ULL * 1024ULL ||
				Serialization::Sha256Hex(arrBytes.data(), arrBytes.size()) != strDeclaredDigest)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "digest_mismatch", "$.asset_bindings", "artifact content digest mismatch");
			return false;
		}
		std::string strDigest;
		if (!CacheBlob(in_strStateDirectory, arrBytes, strDigest, out_arrDiagnostics))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "cache_write", "$", "unable to write verified blob cache");
			return false;
		}
		Assets::AssetInput stInput;
		stInput.strPath = strDigest;
		stInput.stAsset.strAssetId = stBinding.strAssetId;
		stInput.stAsset.strRevision = strRevision;
		stInput.stAsset.strType = strType;
		if (strType == "mesh" && strExtension == ".glb")
		{
			stInput.stAsset.strMediaType = "model/gltf-binary";
		}
		else if (strType == "image" && strExtension == ".png")
		{
			stInput.stAsset.strMediaType = "image/png";
		}
		else if (strType == "image" && (strExtension == ".jpg" || strExtension == ".jpeg"))
		{
			stInput.stAsset.strMediaType = "image/jpeg";
		}
		else
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "unsupported_artifact", "$.asset_bindings", "unsupported artifact type or extension");
			return false;
		}
		stInput.stAsset.stSource.strKind = "executor_artifact";
		stInput.stAsset.stSource.strArtifactId = strId;
		stInput.stAsset.stSource.strArtifactRevision = strRevision;
		stBuild.arrAssets.push_back(stInput);
		bool bReferenced = false;
		for (Assets::SceneEntity &stEntity : stBuild.stScene.arrEntities)
		{
			for (Assets::SceneAssetRef &stRef : stEntity.arrAssets)
			{
				if (stRef.stAsset.strAssetId == stBinding.strAssetId && stRef.strRole == stBinding.strRole)
				{
					stRef.stAsset.strRevision = strRevision;
					stRef.stAsset.strContentSha256 = strDigest;
					bReferenced = true;
				}
			}
		}
		if (!bReferenced)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "missing_scene_binding", "$.scene_template", "asset binding is not referenced by the scene");
			return false;
		}
		out_arrArtifactEvents.emplace_back(Serialization::JsonValue::Object{
				{ "artifact", *pArtifact },
				{ "asset_id", stBinding.strAssetId },
				{ "content_sha256", strDigest },
				{ "revision", strRevision },
				{ "scene_id", stBuild.stScene.strSceneId },
				{ "scene_revision", stBuild.stScene.strSceneRevision },
		});
	}
	if (!Assets::CompilePackage(in_strStateDirectory + "/blob-cache", stBuild, out_stPackage, out_arrDiagnostics))
	{
		return false;
	}
	for (Serialization::JsonValue &stEvent : out_arrArtifactEvents)
	{
		Serialization::JsonValue::Object *pEvent = stEvent.GetObject();
		(*pEvent)["package_digest"] = out_stPackage.strPackageDigest;
		(*pEvent)["scene_content_sha256"] = out_stPackage.stManifest.strSceneContentSha256;
	}
	return true;
}

} // namespace EngineNext::AI
