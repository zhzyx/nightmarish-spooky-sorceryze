/**************************************************************************/
/*  GpuPackageFixture.h                                                   */
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
#include "engine_next/Tests/TestFramework.h"
#include "engine_next/Tests/Assets/FixtureSupport.h"
#include "engine_next/include/EngineNext/Assets/AssetPackage.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"
#include <atomic>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>
namespace EngineNext::Tests::Rendering
{
namespace fs = std::filesystem;
using Serialization::JsonValue;
inline void AppendFloat(std::vector<std::uint8_t> &out_arrBytes, float fValue)
{
	std::uint32_t nBits = 0;
	std::memcpy(&nBits, &fValue, sizeof(nBits));
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(nBits >> (nByte * 8U)));
	}
}

inline void AppendLittle32(std::vector<std::uint8_t> &out_arrBytes, std::uint32_t nValue)
{
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> (nByte * 8U)));
	}
}

inline std::vector<std::uint8_t> TexturedGlb()
{
	const std::vector<std::uint8_t> arrSource = EngineNext::Tests::Assets::ReadFixture("valid.glb");
	const std::uint32_t nJsonBytes = static_cast<std::uint32_t>(arrSource[12]) | (static_cast<std::uint32_t>(arrSource[13]) << 8U) |
			(static_cast<std::uint32_t>(arrSource[14]) << 16U) | (static_cast<std::uint32_t>(arrSource[15]) << 24U);
	JsonValue stRoot;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(std::string(arrSource.begin() + 20, arrSource.begin() + 20 + nJsonBytes), stRoot, strError));
	std::vector<std::uint8_t> arrBinary(arrSource.begin() + 28 + nJsonBytes, arrSource.end());
	const std::size_t nUvOffset = arrBinary.size();
	for (float fValue : { 0.0F, 0.0F, 1.0F, 0.0F, 0.0F, 1.0F })
	{
		AppendFloat(arrBinary, fValue);
	}
	const std::vector<std::uint8_t> arrImage{ 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x02, 0x08, 0x06, 0x00, 0x00, 0x00, 0x72, 0xB6, 0x0D, 0x24, 0x00, 0x00, 0x00, 0x10, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x60, 0x60, 0x60, 0xF8, 0x0F, 0xC5, 0x10, 0x06, 0x00, 0x1D, 0xF4, 0x03, 0xFD, 0xC8, 0xE1, 0xF6, 0xA8, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82 };
	const std::size_t nImageOffset = arrBinary.size();
	arrBinary.insert(arrBinary.end(), arrImage.begin(), arrImage.end());
	JsonValue::Object &mapRoot = *stRoot.GetObject();
	mapRoot["bufferViews"].GetList()->push_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", static_cast<std::int64_t>(nUvOffset) }, { "byteLength", std::int64_t{ 24 } } });
	mapRoot["bufferViews"].GetList()->push_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", static_cast<std::int64_t>(nImageOffset) }, { "byteLength", static_cast<std::int64_t>(arrImage.size()) } });
	mapRoot["accessors"].GetList()->push_back(JsonValue::Object{ { "bufferView", std::int64_t{ 2 } }, { "componentType", std::int64_t{ 5126 } }, { "count", std::int64_t{ 3 } }, { "type", "VEC2" } });
	mapRoot["images"] = JsonValue::List{ JsonValue::Object{ { "bufferView", std::int64_t{ 3 } }, { "mimeType", "image/png" } } };
	mapRoot["textures"] = JsonValue::List{ JsonValue::Object{ { "source", std::int64_t{ 0 } } } };
	mapRoot["materials"] = JsonValue::List{ JsonValue::Object{ { "pbrMetallicRoughness", JsonValue::Object{ { "baseColorTexture", JsonValue::Object{ { "index", std::int64_t{ 0 } } } } } } } };
	JsonValue::Object &mapPrimitive = *mapRoot["meshes"].GetList()->at(0).GetObject()->at("primitives").GetList()->at(0).GetObject();
	mapPrimitive["material"] = std::int64_t{ 0 };
	mapPrimitive["attributes"].GetObject()->emplace("TEXCOORD_0", std::int64_t{ 2 });
	mapRoot["buffers"].GetList()->at(0).GetObject()->at("byteLength") = static_cast<std::int64_t>(arrBinary.size());
	std::string strJson;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stRoot, strJson));
	strJson.append((4 - strJson.size() % 4) % 4, ' ');
	arrBinary.resize((arrBinary.size() + 3) & ~std::size_t{ 3 });
	std::vector<std::uint8_t> arrResult;
	AppendLittle32(arrResult, 0x46546C67U);
	AppendLittle32(arrResult, 2);
	AppendLittle32(arrResult, static_cast<std::uint32_t>(28 + strJson.size() + arrBinary.size()));
	AppendLittle32(arrResult, static_cast<std::uint32_t>(strJson.size()));
	AppendLittle32(arrResult, 0x4E4F534AU);
	arrResult.insert(arrResult.end(), strJson.begin(), strJson.end());
	AppendLittle32(arrResult, static_cast<std::uint32_t>(arrBinary.size()));
	AppendLittle32(arrResult, 0x004E4942U);
	arrResult.insert(arrResult.end(), arrBinary.begin(), arrBinary.end());
	return arrResult;
}

struct PackageFixture
{
	explicit PackageFixture(bool bTextured = false) :
			PackageFixture(bTextured ? TexturedGlb() : EngineNext::Tests::Assets::ReadFixture("valid.glb"))
	{
	}
	explicit PackageFixture(const std::vector<std::uint8_t> &arrBytes)
	{
		static std::atomic<std::uint64_t> nSequence{ 0 };
		const std::uint64_t nStamp = static_cast<std::uint64_t>(std::chrono::steady_clock::now().time_since_epoch().count());
		std::error_code stError;
		fs::path stTemporaryDirectory = fs::temp_directory_path(stError);
		ENGINE_NEXT_CHECK(!stError);
		if (stError)
		{
			return;
		}
		stTemporaryDirectory = fs::canonical(stTemporaryDirectory, stError);
		ENGINE_NEXT_CHECK(!stError);
		if (stError)
		{
			return;
		}
		stRoot = stTemporaryDirectory / ("engine-next-gpu-package-" + std::to_string(nStamp) + "-" + std::to_string(nSequence.fetch_add(1)));
		const bool bCreated = fs::create_directory(stRoot, stError);
		ENGINE_NEXT_CHECK(bCreated && !stError);
		if (!bCreated || stError)
		{
			return;
		}
		const std::string strDigest = EngineNext::Serialization::Sha256Hex(arrBytes.data(), arrBytes.size());
		stPackage.stScene.strSceneId = "m42.gpu-test";
		stPackage.stScene.strSceneRevision = "r1";
		EngineNext::Assets::SceneEntity stEntity;
		stEntity.nEntityId = 7;
		stEntity.strName = "Triangle";
		stEntity.strNodeType = "MeshInstance3D";
		stEntity.strGameplayKind = "static";
		stEntity.stTransform.arrTranslation = { 2, 3, 4 };
		stEntity.arrAssets.push_back({ "mesh", { "triangle", "r1", strDigest } });
		stPackage.stScene.arrEntities.push_back(stEntity);
		std::string strScene;
		ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stPackage.stScene), strScene));
		stPackage.stManifest.strSceneId = stPackage.stScene.strSceneId;
		stPackage.stManifest.strSceneRevision = stPackage.stScene.strSceneRevision;
		stPackage.stManifest.strSceneContentSha256 = EngineNext::Serialization::Sha256Hex(strScene);
		EngineNext::Assets::AssetEntry stAsset;
		stAsset.strAssetId = "triangle";
		stAsset.strRevision = "r1";
		stAsset.strContentSha256 = strDigest;
		stAsset.strType = "mesh";
		stAsset.strMediaType = "model/gltf-binary";
		stAsset.nByteSize = arrBytes.size();
		stAsset.stSource.strKind = "godot_whitelist_import";
		stAsset.stSource.strImporterVersion = "1";
		stPackage.stManifest.arrAssets.push_back(stAsset);
		stPackage.mapBlobs[strDigest] = arrBytes;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(EngineNext::Assets::ComputePackageDigest(stPackage, arrDiagnostics));
		EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
		bReady = EngineNext::Assets::PublishPackage(stPackage, (stRoot / "source.enpak").string(), eResult, arrDiagnostics);
		ENGINE_NEXT_CHECK(bReady);
	}
	~PackageFixture()
	{
		std::error_code stError;
		fs::remove_all(stRoot, stError);
	}
	fs::path stRoot;
	EngineNext::Assets::PackageData stPackage;
	bool bReady = false;
};

} // namespace EngineNext::Tests::Rendering
