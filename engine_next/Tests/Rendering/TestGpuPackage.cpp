/**************************************************************************/
/*  TestGpuPackage.cpp                                                    */
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
#include "engine_next/Tests/Assets/FixtureSupport.h"
#include "engine_next/Rendering/Cook/GpuPackage.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace
{

namespace fs = std::filesystem;
using EngineNext::Serialization::JsonValue;

struct PackageFixture
{
	PackageFixture()
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
		const std::vector<std::uint8_t> arrBytes = EngineNext::Tests::Assets::ReadFixture("valid.glb");
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

std::vector<std::uint8_t> ReadBytes(const fs::path &stPath)
{
	std::ifstream stFile(stPath, std::ios::binary | std::ios::ate);
	if (!stFile || stFile.tellg() < 0)
	{
		return {};
	}
	std::vector<std::uint8_t> arrBytes(static_cast<std::size_t>(stFile.tellg()));
	stFile.seekg(0);
	stFile.read(reinterpret_cast<char *>(arrBytes.data()), static_cast<std::streamsize>(arrBytes.size()));
	return arrBytes;
}

bool ReadManifest(const fs::path &stPath, JsonValue &out_stValue)
{
	const std::vector<std::uint8_t> arrBytes = ReadBytes(stPath);
	std::string strError;
	const bool bParsed = EngineNext::Serialization::ParseJson(std::string(arrBytes.begin(), arrBytes.end()), out_stValue, strError);
	ENGINE_NEXT_CHECK(bParsed);
	if (!bParsed)
	{
		return false;
	}
	const JsonValue::Object *pManifest = out_stValue.GetObject();
	ENGINE_NEXT_CHECK(pManifest != nullptr);
	if (pManifest == nullptr)
	{
		return false;
	}
	const JsonValue::Object::const_iterator itPage = pManifest->find("page_sha256");
	const bool bHasPage = itPage != pManifest->end() && itPage->second.IsString();
	ENGINE_NEXT_CHECK(bHasPage);
	return bHasPage;
}

void WriteManifest(const fs::path &stPath, const JsonValue &stValue)
{
	std::string strJson;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stValue, strJson));
	std::ofstream stFile(stPath, std::ios::binary);
	stFile << strJson;
	stFile.close();
	ENGINE_NEXT_CHECK(stFile.good());
}

void ReplacePage(const fs::path &stPackage, const std::vector<std::uint8_t> &arrPage, JsonValue &stManifest)
{
	const std::string strOldPage = *stManifest.GetObject()->at("page_sha256").GetString();
	const std::string strNewPage = EngineNext::Serialization::Sha256Hex(arrPage.data(), arrPage.size());
	std::ofstream stPage(stPackage / "blobs" / strNewPage, std::ios::binary);
	stPage.write(reinterpret_cast<const char *>(arrPage.data()), static_cast<std::streamsize>(arrPage.size()));
	stPage.close();
	ENGINE_NEXT_CHECK(stPage.good());
	std::error_code stError;
	ENGINE_NEXT_CHECK(fs::remove(stPackage / "blobs" / strOldPage, stError));
	stManifest.GetObject()->at("page_sha256") = strNewPage;
	stManifest.GetObject()->at("page_bytes") = static_cast<std::int64_t>(arrPage.size());
	WriteManifest(stPackage / "GpuManifest.json", stManifest);
}

void AppendFloat(std::vector<std::uint8_t> &out_arrBytes, float fValue)
{
	std::uint32_t nBits = 0;
	std::memcpy(&nBits, &fValue, sizeof(nBits));
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(nBits >> (nByte * 8U)));
	}
}

} // namespace

ENGINE_NEXT_TEST("GPU cook produces identical pages in separate output directories")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const fs::path stFirst = stFixture.stRoot / "first.engpu";
	const fs::path stSecond = stFixture.stRoot / "second.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stFirst.string(), arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stSecond.string(), arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(ReadBytes(stFirst / "GpuManifest.json"), ReadBytes(stSecond / "GpuManifest.json"));
	JsonValue stManifest;
	if (!ReadManifest(stFirst / "GpuManifest.json", stManifest))
	{
		return;
	}
	const std::string strPage = *stManifest.GetObject()->at("page_sha256").GetString();
	ENGINE_NEXT_CHECK_EQ(ReadBytes(stFirst / "blobs" / strPage), ReadBytes(stSecond / "blobs" / strPage));
	EngineNext::Rendering::RenderScene stLoaded;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadGpuPackage(stFirst.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stLoaded.strSceneId, "m42.gpu-test");
	ENGINE_NEXT_CHECK_EQ(stLoaded.strPackageDigest, stFixture.stPackage.strPackageDigest);
	ENGINE_NEXT_CHECK_EQ(stLoaded.arrAssets[0].stIdentity.strContentSha256, stFixture.stPackage.stManifest.arrAssets[0].strContentSha256);
	ENGINE_NEXT_CHECK_EQ(stLoaded.arrInstances[0].nEntityId, 7U);
	ENGINE_NEXT_CHECK_EQ(stLoaded.arrInstances[0].arrEntityOrigin[1], 3.0);
	ENGINE_NEXT_CHECK_EQ(stLoaded.arrInstances[0].arrTransform[12], 2.0);
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stFirst.string(), arrDiagnostics));
}

ENGINE_NEXT_TEST("GPU package rejects a different source digest and corrupted page transactionally")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const fs::path stOutput = stFixture.stRoot / "target.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stOutput.string(), arrDiagnostics));
	EngineNext::Rendering::RenderScene stLoaded;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadGpuPackage(stOutput.string(), std::string(64, 'a'), stLoaded, arrDiagnostics));
	JsonValue stManifest;
	if (!ReadManifest(stOutput / "GpuManifest.json", stManifest))
	{
		return;
	}
	const std::string strPage = *stManifest.GetObject()->at("page_sha256").GetString();
	std::ofstream stPage(stOutput / "blobs" / strPage, std::ios::binary | std::ios::trunc);
	stPage << "short";
	stPage.close();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stLoaded.arrInstances[0].nEntityId, 7U);
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stOutput.string(), arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(ReadBytes(stOutput / "blobs" / strPage).size(), 5U);
}

ENGINE_NEXT_TEST("GPU package rejects manifest traversal and undeclared content")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const fs::path stOutput = stFixture.stRoot / "target.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stOutput.string(), arrDiagnostics));
	EngineNext::Rendering::RenderScene stLoaded;
	JsonValue stManifest;
	if (!ReadManifest(stOutput / "GpuManifest.json", stManifest))
	{
		return;
	}
	stManifest.GetObject()->at("page_sha256") = "../escape";
	WriteManifest(stOutput / "GpuManifest.json", stManifest);
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	const fs::path stSecond = stFixture.stRoot / "second.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stSecond.string(), arrDiagnostics));
	std::ofstream(stSecond / "extra.txt") << "undeclared";
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadGpuPackage(stSecond.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), (stFixture.stRoot / "source.enpak/nested.engpu").string(), arrDiagnostics));
}

ENGINE_NEXT_TEST("GPU package checks decoded page structure even with a matching digest")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const fs::path stOutput = stFixture.stRoot / "target.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stOutput.string(), arrDiagnostics));
	JsonValue stManifest;
	if (!ReadManifest(stOutput / "GpuManifest.json", stManifest))
	{
		return;
	}
	const std::string strOldPage = *stManifest.GetObject()->at("page_sha256").GetString();
	std::vector<std::uint8_t> arrPage = ReadBytes(stOutput / "blobs" / strOldPage);
	arrPage.push_back(0);
	const std::string strNewPage = EngineNext::Serialization::Sha256Hex(arrPage.data(), arrPage.size());
	std::ofstream stPage(stOutput / "blobs" / strNewPage, std::ios::binary);
	stPage.write(reinterpret_cast<const char *>(arrPage.data()), static_cast<std::streamsize>(arrPage.size()));
	stPage.close();
	std::error_code stError;
	ENGINE_NEXT_CHECK(fs::remove(stOutput / "blobs" / strOldPage, stError));
	stManifest.GetObject()->at("page_sha256") = strNewPage;
	stManifest.GetObject()->at("page_bytes") = static_cast<std::int64_t>(arrPage.size());
	WriteManifest(stOutput / "GpuManifest.json", stManifest);
	EngineNext::Rendering::RenderScene stLoaded;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
}

ENGINE_NEXT_TEST("GPU source verification rejects a rehashed encoded scene identity")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const fs::path stOutput = stFixture.stRoot / "target.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stOutput.string(), arrDiagnostics));
	EngineNext::Rendering::RenderScene stSource;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildRenderScene(stFixture.stPackage, stSource, arrDiagnostics));
	EngineNext::Rendering::RenderScene stLoaded;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::VerifyCookedScene(stSource, stLoaded, arrDiagnostics));
	JsonValue stManifest;
	if (!ReadManifest(stOutput / "GpuManifest.json", stManifest))
	{
		return;
	}
	std::vector<std::uint8_t> arrPage = ReadBytes(stOutput / "blobs" / *stManifest.GetObject()->at("page_sha256").GetString());
	const std::string strOriginal = stSource.strSceneId;
	const std::vector<std::uint8_t>::iterator itIdentity = std::search(arrPage.begin(), arrPage.end(), strOriginal.begin(), strOriginal.end());
	ENGINE_NEXT_CHECK(itIdentity != arrPage.end());
	if (itIdentity == arrPage.end())
	{
		return;
	}
	*itIdentity = 'x';
	stManifest.GetObject()->at("scene_id") = "x42.gpu-test";
	ReplacePage(stOutput, arrPage, stManifest);
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::VerifyCookedScene(stSource, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSource.strSceneId, "m42.gpu-test");
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, "gpu_source_mismatch");
}

ENGINE_NEXT_TEST("GPU source verification rejects rehashed valid geometry changes")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const fs::path stOutput = stFixture.stRoot / "target.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stOutput.string(), arrDiagnostics));
	EngineNext::Rendering::RenderScene stSource;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildRenderScene(stFixture.stPackage, stSource, arrDiagnostics));
	JsonValue stManifest;
	if (!ReadManifest(stOutput / "GpuManifest.json", stManifest))
	{
		return;
	}
	std::vector<std::uint8_t> arrPage = ReadBytes(stOutput / "blobs" / *stManifest.GetObject()->at("page_sha256").GetString());
	const EngineNext::Rendering::MeshVertex &stVertex = stSource.arrAssets[0].stMesh.arrPrimitives[0].arrVertices[0];
	std::vector<std::uint8_t> arrVertex;
	for (float fValue : stVertex.arrPosition)
	{
		AppendFloat(arrVertex, fValue);
	}
	for (float fValue : stVertex.arrNormal)
	{
		AppendFloat(arrVertex, fValue);
	}
	for (float fValue : stVertex.arrTangent)
	{
		AppendFloat(arrVertex, fValue);
	}
	for (float fValue : stVertex.arrTexcoord)
	{
		AppendFloat(arrVertex, fValue);
	}
	const std::vector<std::uint8_t>::iterator itVertex = std::search(arrPage.begin(), arrPage.end(), arrVertex.begin(), arrVertex.end());
	ENGINE_NEXT_CHECK(itVertex != arrPage.end());
	if (itVertex == arrPage.end())
	{
		return;
	}
	std::vector<std::uint8_t> arrNewPosition;
	AppendFloat(arrNewPosition, stVertex.arrPosition[0] + 0.25F);
	std::copy(arrNewPosition.begin(), arrNewPosition.end(), itVertex);
	ReplacePage(stOutput, arrPage, stManifest);
	EngineNext::Rendering::RenderScene stLoaded;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::VerifyCookedScene(stSource, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSource.arrAssets[0].stMesh.arrPrimitives[0].arrVertices[0].arrPosition[0], stVertex.arrPosition[0]);
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, "gpu_source_mismatch");
}

ENGINE_NEXT_TEST("GPU package preserves small nonsingular source entity transforms")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	stFixture.stPackage.stScene.arrEntities[0].stTransform.arrScale = { 1.0e-8, 1.0e-8, 1.0e-8 };
	stFixture.stPackage.strSceneJson.clear();
	stFixture.stPackage.strManifestJson.clear();
	std::string strScene;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stFixture.stPackage.stScene), strScene));
	stFixture.stPackage.stManifest.strSceneContentSha256 = EngineNext::Serialization::Sha256Hex(strScene);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ComputePackageDigest(stFixture.stPackage, arrDiagnostics));
	EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
	const fs::path stSource = stFixture.stRoot / "small.enpak";
	ENGINE_NEXT_CHECK(EngineNext::Assets::PublishPackage(stFixture.stPackage, stSource.string(), eResult, arrDiagnostics));
	const fs::path stOutput = stFixture.stRoot / "small.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookGpuPackage(stSource.string(), stOutput.string(), arrDiagnostics));
	EngineNext::Rendering::RenderScene stLoaded;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadGpuPackage(stOutput.string(), stFixture.stPackage.strPackageDigest, stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stLoaded.arrInstances[0].arrTransform[0], 1.0e-8);
}
