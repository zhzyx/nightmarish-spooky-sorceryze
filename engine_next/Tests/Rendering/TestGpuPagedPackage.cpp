/**************************************************************************/
/*  TestGpuPagedPackage.cpp                                               */
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
#include "engine_next/Tests/Rendering/GpuPackageFixture.h"
#include "engine_next/Rendering/Cook/GpuPackage.h"
#include "engine_next/Rendering/Cook/GpuPagedPackage.h"

#include <atomic>
#include <fstream>
#include <thread>

namespace
{
namespace fs = std::filesystem;
using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::CookPagedGpuPackage;
using EngineNext::Rendering::GpuPageIndex;
using EngineNext::Rendering::GpuPageKind;
using EngineNext::Rendering::GpuPageLimits;
using EngineNext::Rendering::GpuPageReadStats;
using EngineNext::Rendering::LoadGpuPageIndex;
using EngineNext::Rendering::ReadGpuPage;
using EngineNext::Serialization::JsonValue;
using EngineNext::Tests::Rendering::PackageFixture;

std::vector<std::uint8_t> Bytes(const fs::path &stPath)
{
	std::ifstream stStream(stPath, std::ios::binary | std::ios::ate);
	if (!stStream || stStream.tellg() < 0)
	{
		return {};
	}
	std::vector<std::uint8_t> arrBytes(static_cast<std::size_t>(stStream.tellg()));
	stStream.seekg(0);
	stStream.read(reinterpret_cast<char *>(arrBytes.data()), static_cast<std::streamsize>(arrBytes.size()));
	return arrBytes;
}

bool ReadManifest(const fs::path &stPackage, JsonValue &out_stValue)
{
	const std::vector<std::uint8_t> arrBytes = Bytes(stPackage / "GpuManifest.json");
	std::string strError;
	const bool bParsed = EngineNext::Serialization::ParseJson(std::string(arrBytes.begin(), arrBytes.end()), out_stValue, strError);
	ENGINE_NEXT_CHECK(bParsed);
	if (!bParsed)
	{
		return false;
	}
	const JsonValue::Object *pRoot = out_stValue.GetObject();
	const bool bRootValid = pRoot != nullptr && pRoot->count("payload_sha256") != 0 && pRoot->at("payload_sha256").IsString() && pRoot->count("pages") != 0 && pRoot->at("pages").IsList() && !pRoot->at("pages").GetList()->empty();
	ENGINE_NEXT_CHECK(bRootValid);
	if (!bRootValid)
	{
		return false;
	}
	return true;
}

void WriteManifest(const fs::path &stPackage, const JsonValue &stValue)
{
	std::string strBytes;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stValue, strBytes));
	std::ofstream stStream(stPackage / "GpuManifest.json", std::ios::binary);
	stStream.write(strBytes.data(), static_cast<std::streamsize>(strBytes.size()));
	stStream.close();
	ENGINE_NEXT_CHECK(stStream.good());
}

std::vector<std::uint8_t> GridGlb(bool bSmooth = false)
{
	using EngineNext::Tests::Rendering::AppendFloat;
	using EngineNext::Tests::Rendering::AppendLittle32;
	std::vector<std::uint8_t> arrBinary;
	for (std::uint32_t nY = 0; nY <= 20; ++nY)
	{
		for (std::uint32_t nX = 0; nX <= 20; ++nX)
		{
			AppendFloat(arrBinary, static_cast<float>(nX));
			AppendFloat(arrBinary, static_cast<float>(nY));
			AppendFloat(arrBinary, 0);
		}
	}
	const std::size_t nIndexOffset = arrBinary.size();
	for (std::uint32_t nY = 0; nY < 20; ++nY)
	{
		for (std::uint32_t nX = 0; nX < 20; ++nX)
		{
			const std::uint32_t nA = nY * 21 + nX;
			for (std::uint32_t nIndex : { nA, nA + 1, nA + 21, nA + 1, nA + 22, nA + 21 })
			{
				AppendLittle32(arrBinary, nIndex);
			}
		}
	}
	const std::size_t nIndexEnd = arrBinary.size();
	if (bSmooth)
	{
		for (std::uint32_t nVertex = 0; nVertex < 441; ++nVertex)
		{
			AppendFloat(arrBinary, 0);
			AppendFloat(arrBinary, 0);
			AppendFloat(arrBinary, 1);
		}
	}
	JsonValue stRoot(JsonValue::Object{
			{ "asset", JsonValue::Object{ { "version", "2.0" } } },
			{ "buffers", JsonValue::List{ JsonValue::Object{ { "byteLength", static_cast<std::int64_t>(arrBinary.size()) } } } },
			{ "bufferViews", JsonValue::List{ JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", std::int64_t{ 0 } }, { "byteLength", static_cast<std::int64_t>(nIndexOffset) } }, JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", static_cast<std::int64_t>(nIndexOffset) }, { "byteLength", static_cast<std::int64_t>(nIndexEnd - nIndexOffset) } } } },
			{ "accessors", JsonValue::List{ JsonValue::Object{ { "bufferView", std::int64_t{ 0 } }, { "componentType", std::int64_t{ 5126 } }, { "count", std::int64_t{ 441 } }, { "type", "VEC3" } }, JsonValue::Object{ { "bufferView", std::int64_t{ 1 } }, { "componentType", std::int64_t{ 5125 } }, { "count", std::int64_t{ 2400 } }, { "type", "SCALAR" } } } },
			{ "meshes", JsonValue::List{ JsonValue::Object{ { "primitives", JsonValue::List{ JsonValue::Object{ { "attributes", JsonValue::Object{ { "POSITION", std::int64_t{ 0 } } } }, { "indices", std::int64_t{ 1 } } } } } } } },
			{ "nodes", JsonValue::List{ JsonValue::Object{ { "mesh", std::int64_t{ 0 } } } } },
			{ "scenes", JsonValue::List{ JsonValue::Object{ { "nodes", JsonValue::List{ JsonValue(std::int64_t{ 0 }) } } } } },
			{ "scene", std::int64_t{ 0 } } });
	if (bSmooth)
	{
		JsonValue::Object &mapRoot = *stRoot.GetObject();
		mapRoot.at("bufferViews").GetList()->emplace_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", static_cast<std::int64_t>(nIndexEnd) }, { "byteLength", static_cast<std::int64_t>(arrBinary.size() - nIndexEnd) } });
		mapRoot.at("accessors").GetList()->emplace_back(JsonValue::Object{ { "bufferView", std::int64_t{ 2 } }, { "componentType", std::int64_t{ 5126 } }, { "count", std::int64_t{ 441 } }, { "type", "VEC3" } });
		mapRoot.at("meshes").GetList()->at(0).GetObject()->at("primitives").GetList()->at(0).GetObject()->at("attributes").GetObject()->emplace("NORMAL", std::int64_t{ 2 });
	}
	std::string strJson;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stRoot, strJson));
	strJson.append((4 - strJson.size() % 4) % 4, ' ');
	std::vector<std::uint8_t> arrResult;
	AppendLittle32(arrResult, 0x46546c67);
	AppendLittle32(arrResult, 2);
	AppendLittle32(arrResult, static_cast<std::uint32_t>(28 + strJson.size() + arrBinary.size()));
	AppendLittle32(arrResult, static_cast<std::uint32_t>(strJson.size()));
	AppendLittle32(arrResult, 0x4e4f534a);
	arrResult.insert(arrResult.end(), strJson.begin(), strJson.end());
	AppendLittle32(arrResult, static_cast<std::uint32_t>(arrBinary.size()));
	AppendLittle32(arrResult, 0x004e4942);
	arrResult.insert(arrResult.end(), arrBinary.begin(), arrBinary.end());
	return arrResult;
}
} // namespace

ENGINE_NEXT_TEST("Paged GPU serializes a generated multilevel hierarchy and complete source coverage")
{
	PackageFixture stFixture(GridGlb());
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	const fs::path stTarget = stFixture.stRoot / "grid.engpu";
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stIndex.Trees().size(), std::size_t(1));
	if (stIndex.Trees().empty())
	{
		return;
	}
	const EngineNext::Rendering::GpuLodTree &stTree = stIndex.Trees()[0];
	ENGINE_NEXT_CHECK(stTree.arrNodes.size() > 5);
	ENGINE_NEXT_CHECK_EQ(stTree.nSourceTriangles, 800U);
	EngineNext::Rendering::RenderScene stSource;
	const bool bSourceLoaded = EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics);
	ENGINE_NEXT_CHECK(bSourceLoaded);
	if (!bSourceLoaded)
	{
		return;
	}
	const bool bSourceReady = !stSource.arrAssets.empty() && !stSource.arrAssets[0].stMesh.arrPrimitives.empty();
	ENGINE_NEXT_CHECK(bSourceReady);
	if (!bSourceReady)
	{
		return;
	}
	// Canonical glTF decoding may expand vertices when generating flat normals.
	ENGINE_NEXT_CHECK_EQ(stTree.nSourceVertices, static_cast<std::uint32_t>(stSource.arrAssets[0].stMesh.arrPrimitives[0].arrVertices.size()));
	std::vector<std::uint8_t> arrBytes;
	GpuPageReadStats stStats;
	for (std::uint32_t nPage = 0; nPage < stIndex.Pages().size(); ++nPage)
	{
		ENGINE_NEXT_CHECK(ReadGpuPage(stIndex, nPage, arrBytes, stStats, arrDiagnostics));
	}
	EngineNext::Rendering::LodSelection stCut;
	EngineNext::Rendering::LodView stView;
	stView.arrPosition = { 10, 10, 3 };
	stView.dMaximumErrorPixels = .001;
	const bool bCutSelected = EngineNext::Rendering::SelectLodCut(stTree.arrNodes, stTree.arrRoots, std::vector<std::uint8_t>(stIndex.Pages().size(), 1), stView, 100, stCut, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCutSelected);
	if (!bCutSelected)
	{
		return;
	}
	std::vector<std::uint32_t> arrCoverage(800, 0);
	for (std::uint32_t nNode : stCut.arrNodes)
	{
		const std::array<std::uint32_t, 2> &arrSourceInterval = stTree.arrSourceRanges[nNode];
		for (std::uint32_t nTriangle = arrSourceInterval[0]; nTriangle < arrSourceInterval[0] + arrSourceInterval[1]; ++nTriangle)
		{
			++arrCoverage[nTriangle];
		}
	}
	for (std::uint32_t nCoverage : arrCoverage)
	{
		ENGINE_NEXT_CHECK_EQ(nCoverage, 1U);
	}
}

ENGINE_NEXT_TEST("Paged GPU Cook roundtrips metadata and reads only the requested mip")
{
	PackageFixture stFixture(true);
	if (!stFixture.bReady)
	{
		return;
	}
	const fs::path stTarget = stFixture.stRoot / "paged.engpu";
	Diagnostics arrDiagnostics;
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stIndex.Metadata().nGpuFormatVersion, 3U);
	ENGINE_NEXT_CHECK_EQ(stIndex.Metadata().arrAssets.size(), std::size_t(1));
	ENGINE_NEXT_CHECK_EQ(stIndex.Metadata().arrInstances.size(), std::size_t(1));
	const bool bMetadataReady = !stIndex.Metadata().arrInstances.empty() && !stIndex.Metadata().arrAssets.empty();
	ENGINE_NEXT_CHECK(bMetadataReady);
	if (!bMetadataReady)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stIndex.Metadata().arrInstances[0].nEntityId, 7ULL);
	const EngineNext::Rendering::RenderAsset &stAsset = stIndex.Metadata().arrAssets[0];
	const bool bAssetReady = !stAsset.stMesh.arrPrimitives.empty() && !stAsset.stMesh.arrImages.empty() && !stAsset.stMesh.arrMaterials.empty() && !stAsset.stTextureCook.arrVariants.empty() && !stAsset.stTextureCook.arrVariants[0].arrMips.empty();
	ENGINE_NEXT_CHECK(bAssetReady);
	if (!bAssetReady)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stAsset.stIdentity.strAssetId, std::string("triangle"));
	ENGINE_NEXT_CHECK(stAsset.stMesh.arrPrimitives[0].arrVertices.empty());
	ENGINE_NEXT_CHECK(stAsset.stMesh.arrImages[0].arrBytes.empty());
	ENGINE_NEXT_CHECK(stAsset.stTextureCook.arrVariants[0].arrMips[0].arrRgba8.empty());
	ENGINE_NEXT_CHECK_EQ(stAsset.stMesh.arrMaterials[0].nBaseColorTexture, 0);
	ENGINE_NEXT_CHECK_EQ(stIndex.Trees().size(), std::size_t(1));
	ENGINE_NEXT_CHECK(stIndex.PinnedBytes() > 0 && stIndex.IndexBytesRead() > 0);
	GpuPageReadStats stStats;
	std::vector<std::uint8_t> arrMip;
	bool bFound = false;
	for (std::uint32_t nPage = 0; nPage < stIndex.Pages().size(); ++nPage)
	{
		const EngineNext::Rendering::GpuPageDescription &stPage = stIndex.Pages()[nPage];
		if (stPage.eKind == GpuPageKind::TextureMip && stPage.nLevel == 1)
		{
			ENGINE_NEXT_CHECK(ReadGpuPage(stIndex, nPage, arrMip, stStats, arrDiagnostics));
			ENGINE_NEXT_CHECK_EQ(arrMip.size(), std::size_t(4));
			ENGINE_NEXT_CHECK_EQ(stStats.nReadRequests, 1ULL);
			ENGINE_NEXT_CHECK_EQ(stStats.nBytesRead, 4ULL);
			ENGINE_NEXT_CHECK_EQ(stStats.nVerifiedPages, 1ULL);
			bFound = true;
			break;
		}
	}
	ENGINE_NEXT_CHECK(bFound);
	for (std::uint32_t nPage = 0; nPage < stIndex.Pages().size(); ++nPage)
	{
		ENGINE_NEXT_CHECK(ReadGpuPage(stIndex, nPage, arrMip, stStats, arrDiagnostics));
	}
	ENGINE_NEXT_CHECK(CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics));
}

ENGINE_NEXT_TEST("Paged GPU directory rejects gaps overlaps duplicates and invalid references transactionally")
{
	PackageFixture stFixture(GridGlb());
	if (!stFixture.bReady)
	{
		return;
	}
	const fs::path stTarget = stFixture.stRoot / "paged.engpu";
	Diagnostics arrDiagnostics;
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	JsonValue stOriginal;
	if (!ReadManifest(stTarget, stOriginal))
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	const std::size_t nPages = stIndex.Pages().size();
	ENGINE_NEXT_CHECK(nPages >= 2);
	if (nPages < 2)
	{
		return;
	}
	for (std::uint32_t nCase = 0; nCase < 9; ++nCase)
	{
		JsonValue stBad = stOriginal;
		JsonValue::Object &mapRoot = *stBad.GetObject();
		JsonValue::List &arrPages = *mapRoot["pages"].GetList();
		ENGINE_NEXT_CHECK(arrPages[0].IsObject() && arrPages[1].IsObject());
		if (!arrPages[0].IsObject() || !arrPages[1].IsObject())
		{
			return;
		}
		JsonValue::Object &mapPage = *arrPages[0].GetObject();
		if (nCase == 0)
		{
			mapPage["offset"] = std::int64_t{ 1 };
		}
		if (nCase == 1)
		{
			arrPages[1].GetObject()->at("offset") = std::int64_t{ 0 };
		}
		if (nCase == 2)
		{
			arrPages.push_back(arrPages[0]);
		}
		if (nCase == 3)
		{
			mapPage["bytes"] = std::int64_t{ 2147483647 };
		}
		if (nCase == 4)
		{
			mapPage["kind"] = std::int64_t{ 99 };
		}
		if (nCase == 5)
		{
			mapPage["asset"] = std::int64_t{ 99 };
		}
		if (nCase == 6)
		{
			mapRoot.erase("trees");
		}
		if (nCase == 7)
		{
			mapRoot["payload_sha256"] = "../outside";
		}
		if (nCase == 8)
		{
			mapRoot["trees"].GetList()->at(0).GetObject()->at("nodes").GetList()->at(0).GetObject()->at("page") = std::int64_t{ 99999 };
		}
		WriteManifest(stTarget, stBad);
		ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stIndex.Pages().size(), nPages);
		WriteManifest(stTarget, stOriginal);
	}
}

ENGINE_NEXT_TEST("Paged GPU reader rejects changed payload while preserving output and recording actual reads")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	const fs::path stTarget = stFixture.stRoot / "paged.engpu";
	Diagnostics arrDiagnostics;
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	JsonValue stManifest;
	if (!ReadManifest(stTarget, stManifest))
	{
		return;
	}
	const fs::path stPayload = stTarget / "blobs" / *stManifest.GetObject()->at("payload_sha256").GetString();
	std::fstream stFile(stPayload, std::ios::binary | std::ios::in | std::ios::out);
	const char nByte = 0;
	stFile.write(&nByte, 1);
	stFile.close();
	std::vector<std::uint8_t> arrOutput{ 17, 23 };
	GpuPageReadStats stStats;
	ENGINE_NEXT_CHECK(!ReadGpuPage(stIndex, 0, arrOutput, stStats, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrOutput, (std::vector<std::uint8_t>{ 17, 23 }));
	ENGINE_NEXT_CHECK_EQ(stStats.nReadRequests, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stStats.nBytesRead, stIndex.Pages()[0].nBytes);
	ENGINE_NEXT_CHECK_EQ(stStats.nVerifiedPages, 0ULL);
}

ENGINE_NEXT_TEST("Paged GPU reader validates mesh indices after successful page hash verification")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	const fs::path stTarget = stFixture.stRoot / "paged.engpu";
	Diagnostics arrDiagnostics;
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	JsonValue stManifest;
	if (!ReadManifest(stTarget, stManifest))
	{
		return;
	}
	JsonValue::Object &mapManifest = *stManifest.GetObject();
	const std::string strOldDigest = *mapManifest.at("payload_sha256").GetString();
	std::vector<std::uint8_t> arrPayload = Bytes(stTarget / "blobs" / strOldDigest);
	ENGINE_NEXT_CHECK(arrPayload.size() > 4);
	if (arrPayload.size() <= 4)
	{
		return;
	}
	for (std::size_t nByte = arrPayload.size() - 4; nByte < arrPayload.size(); ++nByte)
	{
		arrPayload[nByte] = 0xff;
	}
	const std::string strDigest = EngineNext::Serialization::Sha256Hex(arrPayload.data(), arrPayload.size());
	std::ofstream stFile(stTarget / "blobs" / strDigest, std::ios::binary);
	stFile.write(reinterpret_cast<const char *>(arrPayload.data()), static_cast<std::streamsize>(arrPayload.size()));
	stFile.close();
	std::error_code stError;
	ENGINE_NEXT_CHECK(fs::remove(stTarget / "blobs" / strOldDigest, stError));
	mapManifest["payload_sha256"] = strDigest;
	mapManifest["pages"].GetList()->at(0).GetObject()->at("sha256") = strDigest;
	WriteManifest(stTarget, stManifest);
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	std::vector<std::uint8_t> arrOutput{ 17 };
	GpuPageReadStats stStats;
	ENGINE_NEXT_CHECK(!ReadGpuPage(stIndex, 0, arrOutput, stStats, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrOutput, (std::vector<std::uint8_t>{ 17 }));
	ENGINE_NEXT_CHECK_EQ(stStats.nVerifiedPages, 0ULL);
}

ENGINE_NEXT_TEST("Paged GPU budget failures preserve opened index and existing package")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	const fs::path stTarget = stFixture.stRoot / "paged.engpu";
	Diagnostics arrDiagnostics;
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	const std::vector<std::uint8_t> arrOriginal = Bytes(stTarget / "GpuManifest.json");
	GpuPageLimits stLimits;
	stLimits.nMaximumPinnedBytes = 1;
	ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, stLimits, stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(!CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, stLimits, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stIndex.Pages().empty());
	ENGINE_NEXT_CHECK_EQ(Bytes(stTarget / "GpuManifest.json"), arrOriginal);
	stLimits = {};
	stLimits.nMaximumPageBytes = 512ULL * 1024 * 1024;
	ENGINE_NEXT_CHECK(LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, stLimits, stIndex, arrDiagnostics));
	stLimits.nMaximumIndexBytes = 10;
	ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, stLimits, stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), std::string(64, 'f'), {}, stIndex, arrDiagnostics));
	std::ofstream(stTarget / "unexpected.bin", std::ios::binary) << "extra";
	ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics));
}

ENGINE_NEXT_TEST("Paged GPU codec keeps legacy and prepared package entry points compatible")
{
	PackageFixture stFixture(true);
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	EngineNext::Rendering::RenderScene stSource;
	const bool bSourceLoaded = EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics);
	ENGINE_NEXT_CHECK(bSourceLoaded);
	if (!bSourceLoaded)
	{
		return;
	}
	for (std::uint32_t nVersion : { 1U, 2U })
	{
		const fs::path stTarget = stFixture.stRoot / ("old-" + std::to_string(nVersion));
		if (nVersion == 1)
		{
			const bool bLegacyCooked = EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), arrDiagnostics);
			ENGINE_NEXT_CHECK(bLegacyCooked);
			if (!bLegacyCooked)
			{
				return;
			}
		}
		else
		{
			const bool bLegacyCooked2 = EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), { true }, arrDiagnostics);
			ENGINE_NEXT_CHECK(bLegacyCooked2);
			if (!bLegacyCooked2)
			{
				return;
			}
		}
		EngineNext::Rendering::RenderScene stRestored;
		const bool bLegacyLoaded = EngineNext::Rendering::LoadGpuPackage(stTarget.string(), stFixture.stPackage.strPackageDigest, stRestored, arrDiagnostics);
		ENGINE_NEXT_CHECK(bLegacyLoaded);
		if (!bLegacyLoaded)
		{
			return;
		}
		ENGINE_NEXT_CHECK_EQ(stRestored.nGpuFormatVersion, nVersion);
		ENGINE_NEXT_CHECK(EngineNext::Rendering::VerifyCookedScene(stSource, stRestored, arrDiagnostics));
		GpuPageIndex stIndex;
		ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics));
	}
}

ENGINE_NEXT_TEST("Paged GPU concurrent publication is atomic and interrupted staging is invisible")
{
	PackageFixture stFixture(GridGlb());
	if (!stFixture.bReady)
	{
		return;
	}
	const fs::path stTarget = stFixture.stRoot / "paged.engpu";
	std::array<bool, 2> arrResults{};
	std::atomic<unsigned> nDone{ 0 };
	std::array<std::thread, 2> arrWriters;
	for (std::size_t nIndex = 0; nIndex < arrWriters.size(); ++nIndex)
	{
		arrWriters[nIndex] = std::thread([&stFixture, &stTarget, &arrResults, &nDone, nIndex]()
										 {
			Diagnostics arrDiagnostics;
			arrResults[nIndex] = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
			nDone.fetch_add(1); });
	}
	bool bInvalidVisible = false;
	while (nDone.load() < 2)
	{
		GpuPageIndex stIndex;
		Diagnostics arrDiagnostics;
		if (LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics))
		{
			for (std::uint32_t nPage = 0; nPage < stIndex.Pages().size(); ++nPage)
			{
				std::vector<std::uint8_t> arrBytes;
				GpuPageReadStats stStats;
				bInvalidVisible = bInvalidVisible || !ReadGpuPage(stIndex, nPage, arrBytes, stStats, arrDiagnostics);
			}
		}
		std::this_thread::yield();
	}
	for (std::thread &stThread : arrWriters)
	{
		stThread.join();
	}
	ENGINE_NEXT_CHECK(arrResults[0] && arrResults[1] && !bInvalidVisible);
	if (!arrResults[0] || !arrResults[1])
	{
		return;
	}
	const std::vector<std::uint8_t> arrOriginal = Bytes(stTarget / "GpuManifest.json");
	std::error_code stError;
	const fs::path stInterrupted = stFixture.stRoot / "paged.engpu.staging.interrupted";
	ENGINE_NEXT_CHECK(fs::create_directory(stInterrupted, stError));
	std::ofstream(stInterrupted / "incomplete.payload", std::ios::binary) << "partial";
	GpuPageIndex stIndex;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stInterrupted.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics));
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(Bytes(stTarget / "GpuManifest.json"), arrOriginal);
	PackageFixture stDifferent;
	ENGINE_NEXT_CHECK(stDifferent.bReady);
	if (!stDifferent.bReady)
	{
		return;
	}
	ENGINE_NEXT_CHECK(!CookPagedGpuPackage((stDifferent.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(Bytes(stTarget / "GpuManifest.json"), arrOriginal);
}

ENGINE_NEXT_TEST("Paged normal entry verifies canonical source and preserves legacy loading")
{
	PackageFixture stFixture(true);
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	EngineNext::Rendering::RenderScene stSource;
	const bool bSourceLoaded = EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics);
	ENGINE_NEXT_CHECK(bSourceLoaded);
	if (!bSourceLoaded)
	{
		return;
	}
	for (std::uint32_t nVersion : { 1U, 2U, 3U })
	{
		const fs::path stTarget = stFixture.stRoot / ("normal-" + std::to_string(nVersion));
		if (nVersion == 3)
		{
			const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
			ENGINE_NEXT_CHECK(bCooked);
			if (!bCooked)
			{
				return;
			}
		}
		else
		{
			const bool bLegacyCooked = EngineNext::Rendering::CookGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), { nVersion == 2 }, arrDiagnostics);
			ENGINE_NEXT_CHECK(bLegacyCooked);
			if (!bLegacyCooked)
			{
				return;
			}
		}
		EngineNext::Rendering::RenderScene stLoaded;
		GpuPageReadStats stStats;
		const bool bPackageLoaded = EngineNext::Rendering::LoadVerifiedGpuPackage(stTarget.string(), stSource, {}, stLoaded, stStats, arrDiagnostics);
		ENGINE_NEXT_CHECK(bPackageLoaded);
		if (!bPackageLoaded)
		{
			return;
		}
		ENGINE_NEXT_CHECK_EQ(stLoaded.nGpuFormatVersion, nVersion);
		if (nVersion == 3)
		{
			ENGINE_NEXT_CHECK(stStats.nVerifiedPages > 0);
			stLoaded.nGpuFormatVersion = 2;
		}
		else
		{
			ENGINE_NEXT_CHECK_EQ(stStats.nReadRequests, 0ULL);
		}
		ENGINE_NEXT_CHECK(EngineNext::Rendering::VerifyCookedScene(stSource, stLoaded, arrDiagnostics));
	}
}

ENGINE_NEXT_TEST("Paged source verification rejects self-consistent foreign hierarchy without payload reads")
{
	PackageFixture stFixture(GridGlb());
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	const fs::path stTarget = stFixture.stRoot / "bound.engpu";
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	EngineNext::Rendering::RenderScene stSource;
	const bool bSourceLoaded = EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics);
	ENGINE_NEXT_CHECK(bSourceLoaded);
	if (!bSourceLoaded)
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	ENGINE_NEXT_CHECK(EngineNext::Rendering::VerifyPagedScene(stSource, stIndex, arrDiagnostics));
	JsonValue stManifest;
	if (!ReadManifest(stTarget, stManifest))
	{
		return;
	}
	JsonValue::List &arrNodes = *stManifest.GetObject()->at("trees").GetList()->at(0).GetObject()->at("nodes").GetList();
	ENGINE_NEXT_CHECK(!arrNodes.empty());
	if (arrNodes.empty())
	{
		return;
	}
	// Raising the root error remains structurally conservative but is not the
	// exact certified hierarchy produced from the supplied source and settings.
	arrNodes.back().GetObject()->at("error") = 1000.0;
	WriteManifest(stTarget, stManifest);
	ENGINE_NEXT_CHECK(LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, {}, stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::VerifyPagedScene(stSource, stIndex, arrDiagnostics));
	EngineNext::Rendering::RenderScene stOutput;
	stOutput.strSceneId = "preserved";
	GpuPageReadStats stStats;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadVerifiedGpuPackage(stTarget.string(), stSource, {}, stOutput, stStats, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.strSceneId, std::string("preserved"));
	ENGINE_NEXT_CHECK_EQ(stStats.nReadRequests, 0ULL);
}

ENGINE_NEXT_TEST("Paged initial render reads complete leaves and no redundant parent geometry")
{
	PackageFixture stFixture(GridGlb());
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	const fs::path stTarget = stFixture.stRoot / "leaves.engpu";
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	EngineNext::Rendering::RenderScene stSource;
	const bool bSourceLoaded = EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics);
	ENGINE_NEXT_CHECK(bSourceLoaded);
	if (!bSourceLoaded)
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	std::uint64_t nLeaves = 0;
	for (const EngineNext::Rendering::GpuLodTree &stTree : stIndex.Trees())
	{
		for (const EngineNext::Rendering::LodNode &stNode : stTree.arrNodes)
		{
			nLeaves += stNode.nChildCount == 0 ? 1 : 0;
		}
	}
	EngineNext::Rendering::RenderScene stLoaded;
	GpuPageReadStats stStats;
	const bool bPackageLoaded = EngineNext::Rendering::LoadVerifiedGpuPackage(stTarget.string(), stSource, {}, stLoaded, stStats, arrDiagnostics);
	ENGINE_NEXT_CHECK(bPackageLoaded);
	if (!bPackageLoaded)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stStats.nReadRequests, nLeaves);
	ENGINE_NEXT_CHECK(stStats.nReadRequests < stIndex.Pages().size());
	const bool bMeshesReady = !stLoaded.arrAssets.empty() && !stLoaded.arrAssets[0].stMesh.arrPrimitives.empty() && !stSource.arrAssets.empty() && !stSource.arrAssets[0].stMesh.arrPrimitives.empty();
	ENGINE_NEXT_CHECK(bMeshesReady);
	if (!bMeshesReady)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stLoaded.arrAssets[0].stMesh.arrPrimitives[0].arrIndices, stSource.arrAssets[0].stMesh.arrPrimitives[0].arrIndices);
}

ENGINE_NEXT_TEST("Paged source verification bounds recomputation without trusting manifest work limits")
{
	PackageFixture stFixture(GridGlb(true));
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	const fs::path stTarget = stFixture.stRoot / "work-budget.engpu";
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	EngineNext::Rendering::RenderScene stSource;
	const bool bSourceLoaded = EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics);
	ENGINE_NEXT_CHECK(bSourceLoaded);
	if (!bSourceLoaded)
	{
		return;
	}
	GpuPageLimits stLimits;
	stLimits.nMaximumSourceDistanceTests = 0;
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, stLimits, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::VerifyPagedScene(stSource, stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	if (!arrDiagnostics.empty())
	{
		ENGINE_NEXT_CHECK(arrDiagnostics.back().strMessage.find("budget") != std::string::npos);
	}
	stLimits.nMaximumSourceDistanceTests = 4000000;
	ENGINE_NEXT_CHECK(LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, stLimits, stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::VerifyPagedScene(stSource, stIndex, arrDiagnostics));
}

ENGINE_NEXT_TEST("Paged mesh decoding strips source IDs from compact GPU vertex data")
{
	PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	const fs::path stTarget = stFixture.stRoot / "decoded.engpu";
	const bool bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCooked);
	if (!bCooked)
	{
		return;
	}
	GpuPageIndex stIndex;
	const bool bIndexLoaded = LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics);
	ENGINE_NEXT_CHECK(bIndexLoaded);
	if (!bIndexLoaded)
	{
		return;
	}
	EngineNext::Rendering::RenderScene stSource;
	const bool bSourceLoaded = EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics);
	ENGINE_NEXT_CHECK(bSourceLoaded);
	if (!bSourceLoaded)
	{
		return;
	}
	ENGINE_NEXT_CHECK(EngineNext::Rendering::VerifyPagedScene(stSource, stIndex, arrDiagnostics));
	EngineNext::Rendering::GpuMeshPage stPage;
	GpuPageReadStats stStats;
	const bool bPageRead = EngineNext::Rendering::ReadGpuMeshPage(stIndex, 0, stPage, stStats, arrDiagnostics);
	ENGINE_NEXT_CHECK(bPageRead);
	if (!bPageRead)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(sizeof(EngineNext::Rendering::MeshVertex), 48U);
	ENGINE_NEXT_CHECK_EQ(stPage.arrVertices.size(), stPage.arrSourceVertices.size());
	const bool bMeshReady = stPage.arrVertices.size() == stPage.arrSourceVertices.size() && !stSource.arrAssets.empty() && !stSource.arrAssets[0].stMesh.arrPrimitives.empty();
	ENGINE_NEXT_CHECK(bMeshReady);
	if (!bMeshReady)
	{
		return;
	}
	for (std::size_t nVertex = 0; nVertex < stPage.arrVertices.size(); ++nVertex)
	{
		const std::uint32_t nSourceVertex = stPage.arrSourceVertices[nVertex];
		ENGINE_NEXT_CHECK(nSourceVertex < stSource.arrAssets[0].stMesh.arrPrimitives[0].arrVertices.size());
		if (nSourceVertex >= stSource.arrAssets[0].stMesh.arrPrimitives[0].arrVertices.size())
		{
			return;
		}
		ENGINE_NEXT_CHECK_EQ(stPage.arrVertices[nVertex].arrPosition, stSource.arrAssets[0].stMesh.arrPrimitives[0].arrVertices[nSourceVertex].arrPosition);
	}
	const std::vector<EngineNext::Rendering::MeshVertex> arrBefore = stPage.arrVertices;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ReadGpuMeshPage(stIndex, 99999, stPage, stStats, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stPage.arrVertices.size(), arrBefore.size());
}
