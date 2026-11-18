/**************************************************************************/
/*  TestPagedGeometry.cpp                                                 */
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

#include "engine_next/include/EngineNext/Rendering/PagedGeometry.h"
#include "engine_next/Tests/Rendering/GpuPackageFixture.h"
#include "engine_next/Tests/TestFramework.h"
#include <limits>
#include <cstdint>
#include <string>
#include <cmath>
#include <algorithm>
namespace
{
std::array<float, 16> Identity()
{
	return { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
}
} // namespace
ENGINE_NEXT_TEST("Paged LOD transforms bounds with float rounding and mirrored worlds")
{
	EngineNext::Rendering::GpuLodTree stTree;
	stTree.arrNodes.resize(1);
	stTree.arrNodes[0].arrMinimum = { -1, -2, -3 };
	stTree.arrNodes[0].arrMaximum = { 1, 2, 3 };
	stTree.arrNodes[0].dGeometricErrorBound = 1;
	std::array<float, 16> arrWorld = Identity();
	arrWorld[0] = -2;
	arrWorld[5] = 3;
	arrWorld[10] = .5F;
	arrWorld[12] = 100000000;
	std::vector<EngineNext::Rendering::LodNode> arrNodes;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::TransformLodTree(stTree, arrWorld, arrNodes, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrNodes[0].arrMinimum[0] < 99999998.0);
	ENGINE_NEXT_CHECK(arrNodes[0].arrMaximum[0] > 100000002.0);
	ENGINE_NEXT_CHECK(arrNodes[0].dGeometricErrorBound >= 3);
	const std::vector<EngineNext::Rendering::LodNode> arrBefore = arrNodes;
	arrWorld[0] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::TransformLodTree(stTree, arrWorld, arrNodes, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrNodes[0].arrMinimum, arrBefore[0].arrMinimum);
}
ENGINE_NEXT_TEST("Paged frame selection requests roots before returning complete draw cuts")
{
	EngineNext::Tests::Rendering::PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const std::filesystem::path stTarget = stFixture.stRoot / "selection.engpu";
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(), stTarget.string(), {}, {}, arrDiagnostics));
	EngineNext::Rendering::GpuPageIndex stIndex;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadGpuPageIndex(stTarget.string(), stFixture.stPackage.strPackageDigest, {}, stIndex, arrDiagnostics));
	EngineNext::Rendering::RenderScene stSource;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadRenderScene((stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics));
	std::vector<std::array<float, 16>> arrWorlds(stSource.arrInstances.size(), Identity());
	std::vector<std::uint8_t> arrResident(stIndex.Pages().size(), 0);
	EngineNext::Rendering::PagedFrameSelection stSelection;
	EngineNext::Rendering::GeometrySettings stSettings;
	EngineNext::Rendering::LodView stView;
	stView.arrPosition = { 0, 0, 10 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildPagedFrameSelection(stIndex, stSource, arrWorlds, arrResident, stView, stSettings, {}, stSelection, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stSelection.bRootsReady);
	ENGINE_NEXT_CHECK_EQ(stSelection.arrRequestedPages.size(), 1U);
	arrResident[stSelection.arrRequestedPages[0]] = 1;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildPagedFrameSelection(stIndex, stSource, arrWorlds, arrResident, stView, stSettings, {}, stSelection, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSelection.bRootsReady);
	ENGINE_NEXT_CHECK_EQ(stSelection.arrDraws[0].stCut.arrNodes.size(), 1U);
}

namespace
{
std::vector<std::uint8_t> CacheGridGlb()
{
	constexpr std::uint32_t SIZE = 12;
	std::vector<std::uint8_t> arrBinary;
	float fMinZ = 0, fMaxZ = 0;
	for (std::uint32_t nY = 0; nY <= SIZE; ++nY)
	{
		for (std::uint32_t nX = 0; nX <= SIZE; ++nX)
		{
			EngineNext::Tests::Rendering::AppendFloat(arrBinary,
													  static_cast<float>(nX));
			EngineNext::Tests::Rendering::AppendFloat(arrBinary,
													  static_cast<float>(nY));
			const float fZ = .15F * std::sin(static_cast<float>(nX) * .3F) *
					std::cos(static_cast<float>(nY) * .3F);
			fMinZ = (std::min)(fMinZ, fZ);
			fMaxZ = (std::max)(fMaxZ, fZ);
			EngineNext::Tests::Rendering::AppendFloat(arrBinary, fZ);
		}
	}
	const std::uint32_t nVertexBytes =
			static_cast<std::uint32_t>(arrBinary.size());
	for (std::uint32_t nVertex = 0; nVertex < 169; ++nVertex)
	{
		EngineNext::Tests::Rendering::AppendFloat(arrBinary, 0);
		EngineNext::Tests::Rendering::AppendFloat(arrBinary, 0);
		EngineNext::Tests::Rendering::AppendFloat(arrBinary, 1);
	}
	for (std::uint32_t nY = 0; nY < SIZE; ++nY)
	{
		for (std::uint32_t nX = 0; nX < SIZE; ++nX)
		{
			const std::uint32_t nA = nY * (SIZE + 1) + nX;
			for (std::uint32_t nIndex :
				 { nA, nA + 1, nA + SIZE + 1, nA + 1, nA + SIZE + 2, nA + SIZE + 1 })
			{
				EngineNext::Tests::Rendering::AppendLittle32(arrBinary, nIndex);
			}
		}
	}
	std::string strJson =
			"{\"asset\":{\"version\":\"2.0\"},\"buffers\":[{\"byteLength\":" +
			std::to_string(arrBinary.size()) +
			"}],\"bufferViews\":[{\"buffer\":0,\"byteOffset\":0,\"byteLength\":" +
			std::to_string(nVertexBytes) +
			"},{\"buffer\":0,\"byteOffset\":" + std::to_string(nVertexBytes) +
			",\"byteLength\":" + std::to_string(arrBinary.size() - nVertexBytes) +
			"}],\"accessors\":[{\"bufferView\":0,\"componentType\":5126,\"count\":"
			"169,\"type\":\"VEC3\",\"min\":[0,0,0],\"max\":[12,12,0]},"
			"{\"bufferView\":1,\"componentType\":5125,\"count\":864,\"type\":"
			"\"SCALAR\"}],\"materials\":[{}],\"meshes\":[{\"primitives\":[{"
			"\"attributes\":{\"POSITION\":0},\"indices\":1,\"material\":0}]}],"
			"\"nodes\":[{\"mesh\":0}],\"scenes\":[{\"nodes\":[0]}],\"scene\":0}";
	EngineNext::Serialization::JsonValue stJson;
	std::string strError;
	ENGINE_NEXT_CHECK(
			EngineNext::Serialization::ParseJson(strJson, stJson, strError));
	EngineNext::Serialization::JsonValue::List &arrViews =
			*stJson.GetObject()->at("bufferViews").GetList();
	(*arrViews[1].GetObject())["byteOffset"] =
			EngineNext::Serialization::JsonValue(
					static_cast<std::int64_t>(2 * nVertexBytes));
	(*arrViews[1].GetObject())["byteLength"] =
			EngineNext::Serialization::JsonValue(
					static_cast<std::int64_t>(arrBinary.size() - 2 * nVertexBytes));
	arrViews.emplace_back(EngineNext::Serialization::JsonValue::Object{
			{ "buffer", EngineNext::Serialization::JsonValue(std::int64_t{ 0 }) },
			{ "byteOffset", EngineNext::Serialization::JsonValue(static_cast<std::int64_t>(nVertexBytes)) },
			{ "byteLength", EngineNext::Serialization::JsonValue(static_cast<std::int64_t>(nVertexBytes)) } });
	stJson.GetObject()
			->at("accessors")
			.GetList()
			->emplace_back(EngineNext::Serialization::JsonValue::Object{
					{ "bufferView", EngineNext::Serialization::JsonValue(std::int64_t{ 2 }) },
					{ "componentType",
					  EngineNext::Serialization::JsonValue(std::int64_t{ 5126 }) },
					{ "count", EngineNext::Serialization::JsonValue(std::int64_t{ 169 }) },
					{ "type", EngineNext::Serialization::JsonValue("VEC3") } });
	(*stJson.GetObject()
			  ->at("meshes")
			  .GetList()
			  ->at(0)
			  .GetObject()
			  ->at("primitives")
			  .GetList()
			  ->at(0)
			  .GetObject()
			  ->at("attributes")
			  .GetObject())["NORMAL"] =
			EngineNext::Serialization::JsonValue(std::int64_t{ 2 });

	EngineNext::Serialization::JsonValue::Object &mapAccessor =
			*stJson.GetObject()->at("accessors").GetList()->at(0).GetObject();
	mapAccessor["min"] = EngineNext::Serialization::JsonValue::List{
		0.0, 0.0, static_cast<double>(fMinZ)
	};
	mapAccessor["max"] = EngineNext::Serialization::JsonValue::List{
		12.0, 12.0, static_cast<double>(fMaxZ)
	};
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stJson, strJson));
	while (strJson.size() % 4 != 0)
	{
		strJson.push_back(' ');
	}
	std::vector<std::uint8_t> arrGlb;
	for (std::uint32_t nWord :
		 { 0x46546C67U, 2U,
		   static_cast<std::uint32_t>(28 + strJson.size() + arrBinary.size()),
		   static_cast<std::uint32_t>(strJson.size()), 0x4E4F534AU })
	{
		EngineNext::Tests::Rendering::AppendLittle32(arrGlb, nWord);
	}
	arrGlb.insert(arrGlb.end(), strJson.begin(), strJson.end());
	EngineNext::Tests::Rendering::AppendLittle32(
			arrGlb, static_cast<std::uint32_t>(arrBinary.size()));
	EngineNext::Tests::Rendering::AppendLittle32(arrGlb, 0x004E4942U);
	arrGlb.insert(arrGlb.end(), arrBinary.begin(), arrBinary.end());
	return arrGlb;
}
} // namespace
ENGINE_NEXT_TEST("Paged world cache follows moving cameras and bitwise equals "
				 "uncached LOD selection")
{
	using namespace EngineNext::Rendering;
	EngineNext::Tests::Rendering::PackageFixture stFixture(CacheGridGlb());
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	GpuPageIndex stIndex;
	RenderScene stSource;
	ENGINE_NEXT_CHECK(CookPagedGpuPackage(
			(stFixture.stRoot / "source.enpak").string(),
			(stFixture.stRoot / "grid.engpu").string(), {}, {}, arrDiagnostics));
	ENGINE_NEXT_CHECK(LoadGpuPageIndex((stFixture.stRoot / "grid.engpu").string(),
									   stFixture.stPackage.strPackageDigest, {},
									   stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(LoadRenderScene(
			(stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics));
	std::vector<std::array<float, 16>> arrWorlds(stSource.arrInstances.size(),
												 Identity());
	std::vector<std::uint8_t> arrResident(stIndex.Pages().size(), 1);
	PagedWorldCache stCache;
	PagedFrameSelection stPrevious;
	GeometrySettings stSettings;
	LodView stView;
	stView.dProjectionPixels = 500;
	std::size_t nNear = 0, nFar = 0;
	for (std::uint32_t nStep = 0; nStep < 16; ++nStep)
	{
		stView.arrPosition = { 6, 6, 5 + static_cast<double>(nStep) * 200 };
		PagedFrameSelection stReference, stCached;
		ENGINE_NEXT_CHECK(BuildPagedFrameSelection(
				stIndex, stSource, arrWorlds, arrResident, stView, stSettings,
				stPrevious, stReference, arrDiagnostics));
		ENGINE_NEXT_CHECK(BuildPagedFrameSelection(
				stIndex, stSource, arrWorlds, arrResident, stView, stSettings,
				stPrevious, stCached, arrDiagnostics, &stCache));
		ENGINE_NEXT_CHECK_EQ(stCached.arrDraws[0].stCut.arrNodes,
							 stReference.arrDraws[0].stCut.arrNodes);
		ENGINE_NEXT_CHECK_EQ(
				stCached.arrDraws[0].stCut.dMaximumSelectedErrorPixels,
				stReference.arrDraws[0].stCut.dMaximumSelectedErrorPixels);
		if (nStep == 0)
		{
			nNear = stCached.arrDraws[0].stCut.arrNodes.size();
		}
		nFar = stCached.arrDraws[0].stCut.arrNodes.size();
		stPrevious = std::move(stReference);
	}
	ENGINE_NEXT_CHECK(nNear > nFar);
	ENGINE_NEXT_CHECK(stCache.Hits() >= 15);
	ENGINE_NEXT_CHECK_EQ(stCache.Misses(), 1ULL);
}

ENGINE_NEXT_TEST("Paged world cache retains exact transform results and "
				 "rejects changed invalid input")
{
	using namespace EngineNext::Rendering;
	EngineNext::Tests::Rendering::PackageFixture stFixture;
	if (!stFixture.bReady)
	{
		return;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const std::filesystem::path stTarget = stFixture.stRoot / "cache.engpu";
	ENGINE_NEXT_CHECK(
			CookPagedGpuPackage((stFixture.stRoot / "source.enpak").string(),
								stTarget.string(), {}, {}, arrDiagnostics));
	GpuPageIndex stIndex;
	RenderScene stSource;
	ENGINE_NEXT_CHECK(LoadGpuPageIndex(stTarget.string(),
									   stFixture.stPackage.strPackageDigest, {},
									   stIndex, arrDiagnostics));
	ENGINE_NEXT_CHECK(LoadRenderScene(
			(stFixture.stRoot / "source.enpak").string(), stSource, arrDiagnostics));
	std::vector<std::array<float, 16>> arrWorlds(stSource.arrInstances.size(),
												 Identity());
	std::vector<std::uint8_t> arrResident(stIndex.Pages().size(), 1);
	PagedFrameSelection stExpected, stActual;
	GeometrySettings stSettings;
	LodView stView;
	stView.arrPosition = { 0, 0, 10 };
	PagedWorldCache stCache;
	for (float fTranslation : { 0.0F, -0.0F, 1.0F, 100000000.0F })
	{
		arrWorlds[0][12] = fTranslation;
		ENGINE_NEXT_CHECK(BuildPagedFrameSelection(stIndex, stSource, arrWorlds,
												   arrResident, stView, stSettings,
												   {}, stExpected, arrDiagnostics));
		const std::uint64_t nMisses = stCache.Misses();
		ENGINE_NEXT_CHECK(BuildPagedFrameSelection(
				stIndex, stSource, arrWorlds, arrResident, stView, stSettings, {},
				stActual, arrDiagnostics, &stCache));
		ENGINE_NEXT_CHECK_EQ(stCache.Misses(), nMisses + 1);
		ENGINE_NEXT_CHECK_EQ(stActual.arrDraws[0].stCut.arrNodes,
							 stExpected.arrDraws[0].stCut.arrNodes);
		const std::uint64_t nHits = stCache.Hits();
		stView.arrPosition[0] += 1;
		ENGINE_NEXT_CHECK(BuildPagedFrameSelection(
				stIndex, stSource, arrWorlds, arrResident, stView, stSettings, {},
				stActual, arrDiagnostics, &stCache));
		ENGINE_NEXT_CHECK_EQ(stCache.Hits(), nHits + 1);
		ENGINE_NEXT_CHECK(stCache.CachedBytes() <= 64ULL * 1024 * 1024);
	}
	const PagedFrameSelection stBefore = stActual;
	arrWorlds[0][0] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(!BuildPagedFrameSelection(
			stIndex, stSource, arrWorlds, arrResident, stView, stSettings, {},
			stActual, arrDiagnostics, &stCache));
	ENGINE_NEXT_CHECK_EQ(stActual.arrDraws[0].stCut.arrNodes,
						 stBefore.arrDraws[0].stCut.arrNodes);
}
