/**************************************************************************/
/*  TestEncodedGpuPackage.cpp                                             */
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
#include "engine_next/Rendering/Cook/BlockTextureCodec.h"

#include <cstdio>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

namespace
{
namespace fs = std::filesystem;
using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::CookEncodedGpuPackage;
using EngineNext::Rendering::CookGpuPackage;
using EngineNext::Rendering::CookPagedGpuPackage;
using EngineNext::Rendering::EncodedTextureMip;
using EngineNext::Rendering::GpuCookConfig;
using EngineNext::Rendering::GpuPageDescription;
using EngineNext::Rendering::GpuPageIndex;
using EngineNext::Rendering::GpuPageKind;
using EngineNext::Rendering::GpuPageReadStats;
using EngineNext::Rendering::LoadGpuPageIndex;
using EngineNext::Rendering::LoadRenderScene;
using EngineNext::Rendering::LoadVerifiedEncodedGpuPackage;
using EngineNext::Rendering::LoadVerifiedGpuPackage;
using EngineNext::Rendering::ReadGpuTextureMip;
using EngineNext::Rendering::RenderScene;
using EngineNext::Rendering::TextureFormat;
using EngineNext::Rendering::VerifyPagedScene;
using EngineNext::Serialization::JsonValue;
using EngineNext::Tests::Rendering::AppendLittle32;
using EngineNext::Tests::Rendering::PackageFixture;

bool RequirePackageStep(bool bSucceeded, const Diagnostics &arrDiagnostics, const char *pStep, int nLine)
{
	EngineNext::Tests::Check(bSucceeded, pStep, __FILE__, nLine);
	if (!bSucceeded)
	{
		for (const EngineNext::Assets::Diagnostic &stDiagnostic : arrDiagnostics)
		{
			std::fprintf(stderr, "%s: %s %s: %s\n", pStep, stDiagnostic.strCode.c_str(), stDiagnostic.strPath.c_str(), stDiagnostic.strMessage.c_str());
		}
	}
	return bSucceeded;
}

std::vector<std::uint8_t> BlockTexturedGlb()
{
	const std::vector<std::uint8_t> arrPng{ 137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 4, 0, 0, 0, 4, 8, 6, 0, 0, 0, 169, 241, 158, 126, 0, 0, 0, 18, 73, 68, 65, 84, 120, 156, 99, 104, 104, 248, 255, 31, 25, 51, 144, 46, 0, 0, 76, 126, 47, 225, 116, 220, 218, 124, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130 };
	const std::vector<std::uint8_t> arrSource = EngineNext::Tests::Rendering::TexturedGlb();
	const std::uint32_t nJsonBytes = static_cast<std::uint32_t>(arrSource[12]) | (static_cast<std::uint32_t>(arrSource[13]) << 8) |
			(static_cast<std::uint32_t>(arrSource[14]) << 16) | (static_cast<std::uint32_t>(arrSource[15]) << 24);
	JsonValue stRoot;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(std::string(arrSource.begin() + 20, arrSource.begin() + 20 + nJsonBytes), stRoot, strError));
	std::vector<std::uint8_t> arrBinary(arrSource.begin() + 28 + nJsonBytes, arrSource.end());
	JsonValue::Object &mapRoot = *stRoot.GetObject();
	JsonValue::Object &mapImage = *mapRoot["bufferViews"].GetList()->at(3).GetObject();
	mapImage["byteOffset"] = static_cast<std::int64_t>(arrBinary.size());
	mapImage["byteLength"] = static_cast<std::int64_t>(arrPng.size());
	arrBinary.insert(arrBinary.end(), arrPng.begin(), arrPng.end());
	mapRoot["materials"].GetList()->at(0).GetObject()->emplace("normalTexture", JsonValue::Object{ { "index", std::int64_t{ 0 } } });
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

std::string Text(const fs::path &stPath)
{
	std::ifstream stFile(stPath, std::ios::binary);
	return { std::istreambuf_iterator<char>(stFile), std::istreambuf_iterator<char>() };
}

void WriteText(const fs::path &stPath, const std::string &strText)
{
	std::ofstream stFile(stPath, std::ios::binary);
	stFile.write(strText.data(), static_cast<std::streamsize>(strText.size()));
	stFile.close();
	ENGINE_NEXT_CHECK(stFile.good());
}
} // namespace

ENGINE_NEXT_TEST("Encoded v4 package reads real BC7 BC5 pages and keeps M3 identity")
{
	PackageFixture stFixture(BlockTexturedGlb());
	ENGINE_NEXT_CHECK(stFixture.bReady);
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	RenderScene stSource;
	if (!RequirePackageStep(LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics), arrDiagnostics, "LoadRenderScene", __LINE__))
	{
		return;
	}
	const std::string strTarget = (stFixture.stRoot / "encoded.engpu").string();
	if (!RequirePackageStep(CookEncodedGpuPackage((stFixture.stRoot / "source.enpak").string(), strTarget, {}, {}, arrDiagnostics), arrDiagnostics, "CookEncodedGpuPackage", __LINE__))
	{
		return;
	}
	if (!RequirePackageStep(CookEncodedGpuPackage((stFixture.stRoot / "source.enpak").string(), strTarget, {}, {}, arrDiagnostics), arrDiagnostics, "CookEncodedGpuPackage", __LINE__))
	{
		return;
	}
	GpuPageIndex stIndex;
	if (!RequirePackageStep(LoadGpuPageIndex(strTarget, stSource.strPackageDigest, {}, stIndex, arrDiagnostics), arrDiagnostics, "LoadGpuPageIndex", __LINE__))
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stIndex.Metadata().nGpuFormatVersion, 4U);
	if (!RequirePackageStep(VerifyPagedScene(stSource, stIndex, arrDiagnostics), arrDiagnostics, "VerifyPagedScene", __LINE__))
	{
		return;
	}
	bool bBc7 = false;
	bool bBc5 = false;
	GpuPageReadStats stStats;
	for (std::uint32_t nPage = 0; nPage < stIndex.Pages().size(); ++nPage)
	{
		if (stIndex.Pages()[nPage].eKind != GpuPageKind::BlockTextureMip)
		{
			continue;
		}
		EncodedTextureMip stMip;
		ENGINE_NEXT_CHECK(ReadGpuTextureMip(stIndex, nPage, stMip, stStats, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stMip.arrBytes.size(), 16U);
		bBc7 = bBc7 || stMip.eFormat == TextureFormat::Bc7;
		bBc5 = bBc5 || stMip.eFormat == TextureFormat::Bc5;
	}
	ENGINE_NEXT_CHECK(bBc7 && bBc5);
	ENGINE_NEXT_CHECK_EQ(stStats.nVerifiedPages, 6U);
	RenderScene stDecoded;
	if (!RequirePackageStep(LoadVerifiedEncodedGpuPackage(strTarget, stSource, {}, stDecoded, stStats, arrDiagnostics), arrDiagnostics, "LoadVerifiedEncodedGpuPackage", __LINE__))
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stDecoded.strPackageDigest, stSource.strPackageDigest);
	ENGINE_NEXT_CHECK_EQ(stDecoded.arrAssets[0].stIdentity.strContentSha256, stSource.arrAssets[0].stIdentity.strContentSha256);
	ENGINE_NEXT_CHECK(stDecoded.arrAssets[0].stTextureCook.arrVariants[0].arrMips.empty());
	ENGINE_NEXT_CHECK_EQ(stDecoded.arrAssets[0].stTextureCook.arrVariants[0].arrEncodedMips.size(), 3U);
	GpuPageReadStats stStreamingStats;
	GpuPageIndex stStreamingIndex;
	RenderScene stStreamingScene;
	if (!RequirePackageStep(EngineNext::Rendering::LoadTextureStreamingPackage(strTarget, stSource, {}, stStreamingScene, stStreamingStats, stStreamingIndex, arrDiagnostics), arrDiagnostics, "LoadTextureStreamingPackage", __LINE__))
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(stStreamingScene.strPackageDigest, stSource.strPackageDigest);
	ENGINE_NEXT_CHECK_EQ(stStreamingIndex.Pages().size(), stIndex.Pages().size());
	for (const EngineNext::Rendering::CookedTextureVariant &stVariant : stStreamingScene.arrAssets[0].stTextureCook.arrVariants)
	{
		ENGINE_NEXT_CHECK(stVariant.arrEncodedMips.front().arrBytes.empty());
		ENGINE_NEXT_CHECK(stVariant.arrEncodedMips[1].arrBytes.empty());
		ENGINE_NEXT_CHECK(stVariant.arrEncodedMips.back().arrBytes.empty());
	}
	std::vector<std::uint32_t> arrMipPages(3);
	for (std::uint32_t nPage = 0; nPage < stIndex.Pages().size(); ++nPage)
	{
		const EngineNext::Rendering::GpuPageDescription &stPage = stIndex.Pages()[nPage];
		if (stPage.eKind == GpuPageKind::BlockTextureMip && stPage.nAsset == 0 && stPage.nItem == 0)
		{
			arrMipPages[stPage.nLevel] = nPage;
		}
	}
	GpuPageReadStats stSuffixStats;
	std::vector<EncodedTextureMip> arrLevels;
	if (!RequirePackageStep(EngineNext::Rendering::ReadGpuTextureSuffix(stStreamingIndex, arrMipPages, 1, arrLevels, stSuffixStats, arrDiagnostics), arrDiagnostics, "ReadGpuTextureSuffix", __LINE__))
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(arrLevels.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stSuffixStats.nReadRequests, 2U);
	ENGINE_NEXT_CHECK_EQ(stSuffixStats.nBytesRead, 32U);
	ENGINE_NEXT_CHECK(arrLevels[0].arrBytes == stDecoded.arrAssets[0].stTextureCook.arrVariants[0].arrEncodedMips[1].arrBytes);
	arrMipPages[2] = arrMipPages[1];
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ReadGpuTextureSuffix(stStreamingIndex, arrMipPages, 2, arrLevels, stSuffixStats, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrLevels.size(), 2U);
	RenderScene stSentinel;
	stSentinel.strSceneId = "preserved";
	ENGINE_NEXT_CHECK(!LoadVerifiedGpuPackage(strTarget, stSource, {}, stSentinel, stStats, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSentinel.strSceneId, std::string("preserved"));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("gpu_texture_unsupported"));
}

ENGINE_NEXT_TEST("Encoded reader preserves legacy v1 v2 v3 and exact tiny RGBA v4")
{
	PackageFixture stFixture(true);
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	RenderScene stSource;
	if (!RequirePackageStep(LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics), arrDiagnostics, "LoadRenderScene", __LINE__))
	{
		return;
	}
	for (std::uint32_t nVersion = 1; nVersion <= 4; ++nVersion)
	{
		const std::string strTarget = (stFixture.stRoot / ("format" + std::to_string(nVersion))).string();
		bool bCooked = false;
		if (nVersion < 3)
		{
			GpuCookConfig stConfig;
			stConfig.bPrepareGpuData = nVersion == 2;
			bCooked = CookGpuPackage((stFixture.stRoot / "source.enpak").string(), strTarget, stConfig, arrDiagnostics);
		}
		else if (nVersion == 3)
		{
			bCooked = CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), strTarget, {}, {}, arrDiagnostics);
		}
		else
		{
			bCooked = CookEncodedGpuPackage((stFixture.stRoot / "source.enpak").string(), strTarget, {}, {}, arrDiagnostics);
		}
		if (!RequirePackageStep(bCooked, arrDiagnostics, "Cook GPU package", __LINE__))
		{
			return;
		}
		RenderScene stDecoded;
		GpuPageReadStats stStats;
		if (!RequirePackageStep(LoadVerifiedEncodedGpuPackage(strTarget, stSource, {}, stDecoded, stStats, arrDiagnostics), arrDiagnostics, "LoadVerifiedEncodedGpuPackage", __LINE__))
		{
			return;
		}
		ENGINE_NEXT_CHECK_EQ(stDecoded.nGpuFormatVersion, nVersion);
		if (nVersion == 4)
		{
			ENGINE_NEXT_CHECK_EQ(stDecoded.arrAssets[0].stTextureCook.arrVariants[0].arrEncodedMips[0].eFormat, TextureFormat::Rgba8);
		}
	}
}

ENGINE_NEXT_TEST("Encoded recipe and payload tampering are rejected transactionally")
{
	PackageFixture stFixture(BlockTexturedGlb());
	if (!stFixture.bReady)
	{
		return;
	}
	Diagnostics arrDiagnostics;
	RenderScene stSource;
	if (!RequirePackageStep(LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics), arrDiagnostics, "LoadRenderScene", __LINE__))
	{
		return;
	}
	const fs::path stTarget = stFixture.stRoot / "encoded.engpu";
	if (!RequirePackageStep(CookEncodedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics), arrDiagnostics, "CookEncodedGpuPackage", __LINE__))
	{
		return;
	}
	const std::string strOriginal = Text(stTarget / "GpuManifest.json");
	JsonValue stManifest;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(strOriginal, stManifest, strError));
	stManifest.GetObject()->at("texture_recipe") = "unverified";
	std::string strChanged;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stManifest, strChanged));
	WriteText(stTarget / "GpuManifest.json", strChanged);
	GpuPageIndex stIndex;
	ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, {}, stIndex, arrDiagnostics));
	WriteText(stTarget / "GpuManifest.json", strOriginal);
	if (!RequirePackageStep(LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, {}, stIndex, arrDiagnostics), arrDiagnostics, "LoadGpuPageIndex", __LINE__))
	{
		return;
	}
	if (!RequirePackageStep(VerifyPagedScene(stSource, stIndex, arrDiagnostics), arrDiagnostics, "VerifyPagedScene", __LINE__))
	{
		return;
	}
	RenderScene stAltered = stSource;
	stAltered.arrAssets[0].stMesh.arrMaterials[0].fRoughness = .11F;
	ENGINE_NEXT_CHECK(!VerifyPagedScene(stAltered, stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(!LoadGpuPageIndex(stTarget.string(), std::string(64, '0'), {}, stIndex, arrDiagnostics));
	if (!RequirePackageStep(LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, {}, stIndex, arrDiagnostics), arrDiagnostics, "LoadGpuPageIndex", __LINE__))
	{
		return;
	}
	const fs::path stBlob = stTarget / "blobs" / *stManifest.GetObject()->at("payload_sha256").GetString();
	std::string strBlob = Text(stBlob);
	strBlob[static_cast<std::size_t>(stIndex.Pages()[1].nOffset)] ^= 1;
	WriteText(stBlob, strBlob);
	EncodedTextureMip stSentinel;
	stSentinel.nWidth = 99;
	GpuPageReadStats stStats;
	ENGINE_NEXT_CHECK(!ReadGpuTextureMip(stIndex, 1, stSentinel, stStats, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSentinel.nWidth, 99U);
	// Rehash both the changed page and complete payload: the foreign package
	// is internally consistent but must still fail canonical source validation.
	const std::string strNewPayloadDigest = EngineNext::Serialization::Sha256Hex(strBlob);
	JsonValue::List &arrPages = *stManifest.GetObject()->at("pages").GetList();
	const GpuPageDescription &stPage = stIndex.Pages()[1];
	arrPages[1].GetObject()->at("sha256") = EngineNext::Serialization::Sha256Hex(strBlob.data() + stPage.nOffset, static_cast<std::size_t>(stPage.nBytes));
	stManifest.GetObject()->at("texture_recipe") = EngineNext::Rendering::BlockTextureRecipe();
	stManifest.GetObject()->at("payload_sha256") = strNewPayloadDigest;
	std::error_code stError;
	fs::rename(stBlob, stTarget / "blobs" / strNewPayloadDigest, stError);
	ENGINE_NEXT_CHECK(!stError);
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stManifest, strChanged));
	WriteText(stTarget / "GpuManifest.json", strChanged);
	if (!RequirePackageStep(LoadGpuPageIndex(stTarget.string(), stSource.strPackageDigest, {}, stIndex, arrDiagnostics), arrDiagnostics, "LoadGpuPageIndex", __LINE__))
	{
		return;
	}
	ENGINE_NEXT_CHECK(!VerifyPagedScene(stSource, stIndex, arrDiagnostics));
}
