/**************************************************************************/
/*  TestGeometryLod.cpp                                                   */
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

#include "engine_next/include/EngineNext/Rendering/GeometryLod.h"
#include "engine_next/Tests/TestFramework.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <iostream>
#include <map>
#include <vector>

namespace
{
using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::ComputeLodDeviationBound;
using EngineNext::Rendering::CookedLodHierarchy;
using EngineNext::Rendering::CookLodHierarchy;
using EngineNext::Rendering::LodCookSettings;
using EngineNext::Rendering::LodGeometry;
using EngineNext::Rendering::LodNode;
using EngineNext::Rendering::LodSelection;
using EngineNext::Rendering::LodView;
using EngineNext::Rendering::MeshPrimitive;
using EngineNext::Rendering::MeshVertex;
using EngineNext::Rendering::SelectLodCut;

MeshPrimitive Grid(std::uint32_t nSize)
{
	MeshPrimitive stPrimitive;
	for (std::uint32_t nY = 0; nY <= nSize; ++nY)
	{
		for (std::uint32_t nX = 0; nX <= nSize; ++nX)
		{
			MeshVertex stVertex;
			stVertex.arrPosition = { static_cast<float>(nX), static_cast<float>(nY), .15F * std::sin(static_cast<float>(nX) * .3F) * std::cos(static_cast<float>(nY) * .3F) };
			stVertex.arrTexcoord = { static_cast<float>(nX) / nSize, static_cast<float>(nY) / nSize };
			stPrimitive.arrVertices.push_back(stVertex);
		}
	}
	for (std::uint32_t nY = 0; nY < nSize; ++nY)
	{
		for (std::uint32_t nX = 0; nX < nSize; ++nX)
		{
			const std::uint32_t nA = nY * (nSize + 1) + nX;
			const std::uint32_t nB = nA + 1;
			const std::uint32_t nC = nA + nSize + 1;
			const std::uint32_t nD = nC + 1;
			stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { nA, nB, nC, nB, nD, nC });
		}
	}
	return stPrimitive;
}

void CheckBoundary(const MeshPrimitive &stPrimitive, const LodGeometry &stGeometry)
{
	std::map<std::array<std::uint32_t, 2>, std::uint32_t> mapSource;
	std::map<std::array<std::uint32_t, 2>, std::uint32_t> mapOutput;
	const std::size_t nFirst = static_cast<std::size_t>(stGeometry.nFirstSourceTriangle) * 3;
	const std::size_t nCount = static_cast<std::size_t>(stGeometry.nSourceTriangleCount) * 3;
	for (std::size_t nIndex = nFirst; nIndex < nFirst + nCount; nIndex += 3)
	{
		for (std::size_t nEdge = 0; nEdge < 3; ++nEdge)
		{
			const std::uint32_t nA = stPrimitive.arrIndices[nIndex + nEdge];
			const std::uint32_t nB = stPrimitive.arrIndices[nIndex + (nEdge + 1) % 3];
			++mapSource[{ (std::min)(nA, nB), (std::max)(nA, nB) }];
		}
	}
	for (std::size_t nIndex = 0; nIndex < stGeometry.arrIndices.size(); nIndex += 3)
	{
		for (std::size_t nEdge = 0; nEdge < 3; ++nEdge)
		{
			const std::uint32_t nA = stGeometry.arrIndices[nIndex + nEdge];
			const std::uint32_t nB = stGeometry.arrIndices[nIndex + (nEdge + 1) % 3];
			++mapOutput[{ (std::min)(nA, nB), (std::max)(nA, nB) }];
		}
	}
	for (const std::pair<const std::array<std::uint32_t, 2>, std::uint32_t> &stEdge : mapSource)
	{
		if (stEdge.second == 1)
		{
			ENGINE_NEXT_CHECK(mapOutput[stEdge.first] == 1);
		}
	}
}
} // namespace

ENGINE_NEXT_TEST("LOD Cook produces actual simplified levels with complete source intervals")
{
	const MeshPrimitive stPrimitive = Grid(20);
	LodCookSettings stSettings;
	stSettings.nMaximumDistanceTests = 20000000;
	CookedLodHierarchy stHierarchy;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, stSettings, stHierarchy, arrDiagnostics));
	ENGINE_NEXT_CHECK(stHierarchy.nSimplifiedNodes > 0);
	ENGINE_NEXT_CHECK(stHierarchy.arrNodes.size() > 5);
	ENGINE_NEXT_CHECK_EQ(stHierarchy.arrRoots.size(), std::size_t(1));
	const std::uint32_t nRoot = stHierarchy.arrRoots[0];
	ENGINE_NEXT_CHECK_EQ(stHierarchy.arrGeometry[nRoot].nSourceTriangleCount, 800U);
	ENGINE_NEXT_CHECK(stHierarchy.arrGeometry[nRoot].arrIndices.size() < stPrimitive.arrIndices.size());
	std::cout << "LOD_COOK nodes=" << stHierarchy.arrNodes.size() << " simplified=" << stHierarchy.nSimplifiedNodes
			  << " original_triangles=" << stPrimitive.arrIndices.size() / 3 << " root_triangles=" << stHierarchy.arrGeometry[nRoot].arrIndices.size() / 3
			  << " error_bound=" << stHierarchy.arrNodes[nRoot].dGeometricErrorBound << " distance_tests=" << stHierarchy.nDistanceTests << '\n';
	for (std::size_t nNode = 0; nNode < stHierarchy.arrNodes.size(); ++nNode)
	{
		const LodNode &stNode = stHierarchy.arrNodes[nNode];
		const LodGeometry &stGeometry = stHierarchy.arrGeometry[nNode];
		ENGINE_NEXT_CHECK(std::isfinite(stNode.dGeometricErrorBound));
		CheckBoundary(stPrimitive, stGeometry);
		std::uint32_t nExpectedFirst = stGeometry.nFirstSourceTriangle;
		for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
		{
			ENGINE_NEXT_CHECK_EQ(stHierarchy.arrGeometry[nChild].nFirstSourceTriangle, nExpectedFirst);
			nExpectedFirst += stHierarchy.arrGeometry[nChild].nSourceTriangleCount;
			ENGINE_NEXT_CHECK(stNode.dGeometricErrorBound >= stHierarchy.arrNodes[nChild].dGeometricErrorBound);
		}
		if (stNode.nChildCount != 0)
		{
			ENGINE_NEXT_CHECK_EQ(nExpectedFirst, stGeometry.nFirstSourceTriangle + stGeometry.nSourceTriangleCount);
		}
		for (std::uint32_t nIndex : stGeometry.arrIndices)
		{
			ENGINE_NEXT_CHECK(nIndex < stPrimitive.arrVertices.size());
		}
	}
	LodView stView;
	stView.arrPosition = { 10, 10, 100 };
	stView.dProjectionPixels = 1000;
	stView.dMaximumErrorPixels = .001;
	LodSelection stSelection;
	std::vector<std::uint8_t> arrResident(stHierarchy.arrNodes.size(), 1);
	ENGINE_NEXT_CHECK(SelectLodCut(stHierarchy.arrNodes, stHierarchy.arrRoots, arrResident, stView, 65536, stSelection, arrDiagnostics));
	std::vector<std::uint32_t> arrCoverage(800, 0);
	for (std::uint32_t nNode : stSelection.arrNodes)
	{
		const LodGeometry &stGeometry = stHierarchy.arrGeometry[nNode];
		for (std::uint32_t nTriangle = stGeometry.nFirstSourceTriangle; nTriangle < stGeometry.nFirstSourceTriangle + stGeometry.nSourceTriangleCount; ++nTriangle)
		{
			++arrCoverage[nTriangle];
		}
	}
	for (std::uint32_t nCount : arrCoverage)
	{
		ENGINE_NEXT_CHECK_EQ(nCount, 1U);
	}
}

ENGINE_NEXT_TEST("LOD Cook generated cuts preserve coverage during residency and adjacent level changes")
{
	const MeshPrimitive stPrimitive = Grid(16);
	CookedLodHierarchy stHierarchy;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, {}, stHierarchy, arrDiagnostics));
	LodView stView;
	stView.arrPosition = { 4, 4, 10 };
	stView.dProjectionPixels = 200;
	for (std::uint32_t nResidency = 0; nResidency < 8; ++nResidency)
	{
		std::vector<std::uint8_t> arrResident(stHierarchy.arrNodes.size(), 1);
		for (std::size_t nNode = 0; nNode < arrResident.size(); ++nNode)
		{
			arrResident[nNode] = static_cast<std::uint8_t>(((nNode + nResidency) % 8) != 0);
		}
		arrResident[stHierarchy.arrRoots[0]] = 1;
		for (std::uint32_t nCapacity : { 1U, 3U, 6U, 100U })
		{
			LodSelection stSelection;
			ENGINE_NEXT_CHECK(SelectLodCut(stHierarchy.arrNodes, stHierarchy.arrRoots, arrResident, stView, nCapacity, stSelection, arrDiagnostics));
			std::vector<std::uint32_t> arrCoverage(stPrimitive.arrIndices.size() / 3, 0);
			for (std::uint32_t nNode : stSelection.arrNodes)
			{
				const LodGeometry &stGeometry = stHierarchy.arrGeometry[nNode];
				for (std::uint32_t nTriangle = stGeometry.nFirstSourceTriangle; nTriangle < stGeometry.nFirstSourceTriangle + stGeometry.nSourceTriangleCount; ++nTriangle)
				{
					++arrCoverage[nTriangle];
				}
				CheckBoundary(stPrimitive, stGeometry);
			}
			for (std::uint32_t nCount : arrCoverage)
			{
				ENGINE_NEXT_CHECK_EQ(nCount, 1U);
			}
		}
	}
}

ENGINE_NEXT_TEST("LOD Cook normalized scratch handles tiny and large finite geometry")
{
	for (float fScale : { 1.0e-25F, 1.0e25F })
	{
		MeshPrimitive stPrimitive = Grid(8);
		for (MeshVertex &stVertex : stPrimitive.arrVertices)
		{
			for (float &fValue : stVertex.arrPosition)
			{
				fValue *= fScale;
			}
			stVertex.arrTexcoord[0] = std::numeric_limits<float>::max();
		}
		CookedLodHierarchy stHierarchy;
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, {}, stHierarchy, arrDiagnostics));
		for (const LodNode &stNode : stHierarchy.arrNodes)
		{
			ENGINE_NEXT_CHECK(std::isfinite(stNode.dGeometricErrorBound));
		}
	}
}

ENGINE_NEXT_TEST("LOD deviation handles degenerate targets and invalid bounds transactionally")
{
	MeshPrimitive stPrimitive;
	MeshVertex stFirst, stSecond;
	stSecond.arrPosition = { 0, 0, 2 };
	stPrimitive.arrVertices = { stFirst, stSecond };
	LodCookSettings stSettings;
	std::uint64_t nTests = 0;
	double dBound = 99;
	ENGINE_NEXT_CHECK(ComputeLodDeviationBound(stPrimitive, { 0, 0, 0 }, { 1, 1, 1 }, stSettings, nTests, dBound));
	ENGINE_NEXT_CHECK(dBound >= 2 && dBound < 2.00001);
	const double dPrevious = dBound;
	ENGINE_NEXT_CHECK(!ComputeLodDeviationBound(stPrimitive, { 0, 0, 0 }, { 1, 1, 99 }, stSettings, nTests, dBound));
	ENGINE_NEXT_CHECK_EQ(dBound, dPrevious);
	stSettings.nVerificationDepth = 9;
	ENGINE_NEXT_CHECK(!ComputeLodDeviationBound(stPrimitive, { 0, 0, 0 }, { 1, 1, 1 }, stSettings, nTests, dBound));
	ENGINE_NEXT_CHECK_EQ(dBound, dPrevious);
}

ENGINE_NEXT_TEST("LOD verification bounds displaced triangles in both directions")
{
	MeshPrimitive stPrimitive;
	for (const std::array<float, 3> &arrPosition : { std::array<float, 3>{ 0, 0, 0 }, { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 }, { 1, 0, 1 }, { 0, 1, 1 } })
	{
		MeshVertex stVertex;
		stVertex.arrPosition = arrPosition;
		stPrimitive.arrVertices.push_back(stVertex);
	}
	LodCookSettings stSettings;
	stSettings.nVerificationDepth = 3;
	stSettings.dVerificationCellRadius = .001;
	std::uint64_t nTests = 0;
	double dBound = -1;
	ENGINE_NEXT_CHECK(ComputeLodDeviationBound(stPrimitive, { 0, 1, 2 }, { 3, 4, 5 }, stSettings, nTests, dBound));
	ENGINE_NEXT_CHECK(dBound >= 1 && dBound < 1.1);
	ENGINE_NEXT_CHECK_EQ(nTests, 128ULL);
	const double dFineBound = dBound;
	stSettings.nVerificationDepth = 0;
	nTests = 0;
	ENGINE_NEXT_CHECK(ComputeLodDeviationBound(stPrimitive, { 3, 4, 5 }, { 0, 1, 2 }, stSettings, nTests, dBound));
	ENGINE_NEXT_CHECK(dBound > dFineBound && dBound >= 1);
	stSettings.nMaximumDistanceTests = 0;
	nTests = 0;
	dBound = 123;
	ENGINE_NEXT_CHECK(!ComputeLodDeviationBound(stPrimitive, { 0, 1, 2 }, { 3, 4, 5 }, stSettings, nTests, dBound));
	ENGINE_NEXT_CHECK_EQ(dBound, 123.0);
}

ENGINE_NEXT_TEST("LOD Cook verification exhaustion retains full parent geometry")
{
	const MeshPrimitive stPrimitive = Grid(12);
	LodCookSettings stSettings;
	stSettings.nMaximumDistanceTests = 0;
	CookedLodHierarchy stHierarchy;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, stSettings, stHierarchy, arrDiagnostics));
	ENGINE_NEXT_CHECK(stHierarchy.nVerificationFallbacks > 0);
	ENGINE_NEXT_CHECK_EQ(stHierarchy.nSimplifiedNodes, 0U);
	ENGINE_NEXT_CHECK_EQ(stHierarchy.nDistanceTests, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stHierarchy.arrGeometry[stHierarchy.arrRoots[0]].arrIndices, stPrimitive.arrIndices);
	for (const LodNode &stNode : stHierarchy.arrNodes)
	{
		ENGINE_NEXT_CHECK_EQ(stNode.dGeometricErrorBound, 0.0);
	}
}

ENGINE_NEXT_TEST("LOD Cook preserves degenerate and nonmanifold source triangles")
{
	for (bool bDegenerate : { false, true })
	{
		MeshPrimitive stPrimitive = Grid(12);
		if (bDegenerate)
		{
			stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { 0, 0, 0 });
		}
		else
		{
			stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { 0, 1, 13 });
		}
		CookedLodHierarchy stHierarchy;
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, {}, stHierarchy, arrDiagnostics));
		ENGINE_NEXT_CHECK(stHierarchy.nTopologyFallbacks > 0);
		ENGINE_NEXT_CHECK_EQ(stHierarchy.arrGeometry[stHierarchy.arrRoots[0]].arrIndices, stPrimitive.arrIndices);
	}
}

ENGINE_NEXT_TEST("LOD Cook preserves duplicated position UV and hard normal seams")
{
	MeshPrimitive stPrimitive = Grid(12);
	for (std::size_t nIndex = 0; nIndex < stPrimitive.arrIndices.size(); ++nIndex)
	{
		const std::uint32_t nOriginal = stPrimitive.arrIndices[nIndex];
		if (nOriginal % 13 != 6 || nIndex % 6 < 3)
		{
			continue;
		}
		MeshVertex stVertex = stPrimitive.arrVertices[nOriginal];
		stVertex.arrNormal = { 0, 1, 0 };
		stVertex.arrTexcoord[0] = 10;
		stPrimitive.arrIndices[nIndex] = static_cast<std::uint32_t>(stPrimitive.arrVertices.size());
		stPrimitive.arrVertices.push_back(stVertex);
	}
	const std::vector<MeshVertex> arrOriginal = stPrimitive.arrVertices;
	CookedLodHierarchy stHierarchy;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, {}, stHierarchy, arrDiagnostics));
	for (const LodGeometry &stGeometry : stHierarchy.arrGeometry)
	{
		CheckBoundary(stPrimitive, stGeometry);
	}
	ENGINE_NEXT_CHECK_EQ(stPrimitive.arrVertices.size(), arrOriginal.size());
	for (std::size_t nIndex = 0; nIndex < arrOriginal.size(); ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stPrimitive.arrVertices[nIndex].arrPosition, arrOriginal[nIndex].arrPosition);
		ENGINE_NEXT_CHECK_EQ(stPrimitive.arrVertices[nIndex].arrNormal, arrOriginal[nIndex].arrNormal);
		ENGINE_NEXT_CHECK_EQ(stPrimitive.arrVertices[nIndex].arrTexcoord, arrOriginal[nIndex].arrTexcoord);
	}
}

ENGINE_NEXT_TEST("LOD Cook deterministic output and invalid inputs are transactional")
{
	const MeshPrimitive stPrimitive = Grid(8);
	CookedLodHierarchy stFirst, stSecond;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, {}, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(CookLodHierarchy(stPrimitive, {}, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFirst.arrGeometry.size(), stSecond.arrGeometry.size());
	for (std::size_t nNode = 0; nNode < stFirst.arrGeometry.size(); ++nNode)
	{
		ENGINE_NEXT_CHECK_EQ(stFirst.arrGeometry[nNode].arrIndices, stSecond.arrGeometry[nNode].arrIndices);
		ENGINE_NEXT_CHECK_EQ(stFirst.arrNodes[nNode].dGeometricErrorBound, stSecond.arrNodes[nNode].dGeometricErrorBound);
	}
	LodCookSettings stSettings;
	stSettings.nMaximumNodes = 1;
	stSecond.arrRoots = { 999 };
	ENGINE_NEXT_CHECK(!CookLodHierarchy(stPrimitive, stSettings, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSecond.arrRoots, (std::vector<std::uint32_t>{ 999 }));
	stSettings = {};
	stSettings.nMaximumOutputIndices = 1;
	ENGINE_NEXT_CHECK(!CookLodHierarchy(stPrimitive, stSettings, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSecond.arrRoots, (std::vector<std::uint32_t>{ 999 }));
	MeshPrimitive stBad = stPrimitive;
	stBad.arrVertices[0].arrTexcoord[0] = std::numeric_limits<float>::infinity();
	ENGINE_NEXT_CHECK(!CookLodHierarchy(stBad, {}, stSecond, arrDiagnostics));
	stBad = stPrimitive;
	stBad.arrIndices[0] = 999999;
	ENGINE_NEXT_CHECK(!CookLodHierarchy(stBad, {}, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSecond.arrRoots, (std::vector<std::uint32_t>{ 999 }));
}

ENGINE_NEXT_TEST("LOD target hierarchy bounds analytic point clouds within the original query budget")
{
	for (float fScale : { 1.0F, 1.0e25F, 1.0e-25F })
	{
		MeshPrimitive stPrimitive;
		std::vector<std::uint32_t> arrSource, arrTarget;
		constexpr std::uint32_t POINTS = 1024;
		for (std::uint32_t nLayer = 0; nLayer < 2; ++nLayer)
		{
			for (std::uint32_t nPoint = 0; nPoint < POINTS; ++nPoint)
			{
				MeshVertex stVertex;
				stVertex.arrPosition = { static_cast<float>(nPoint % 32) * 10 * fScale, static_cast<float>(nPoint / 32) * 10 * fScale, static_cast<float>(nLayer) * 2 * fScale };
				const std::uint32_t nIndex = static_cast<std::uint32_t>(stPrimitive.arrVertices.size());
				stPrimitive.arrVertices.push_back(stVertex);
				std::vector<std::uint32_t> &arrIndices = nLayer == 0 ? arrSource : arrTarget;
				arrIndices.insert(arrIndices.end(), { nIndex, nIndex, nIndex });
			}
		}
		LodCookSettings stSettings;
		stSettings.nMaximumDistanceTests = 32768;
		std::uint64_t nTests = 0;
		double dBound = -1;
		ENGINE_NEXT_CHECK(ComputeLodDeviationBound(stPrimitive, arrSource, arrTarget, stSettings, nTests, dBound));
		const double dExact = 2 * static_cast<double>(fScale);
		ENGINE_NEXT_CHECK(dBound >= dExact);
		ENGINE_NEXT_CHECK(std::isfinite(dBound));
		ENGINE_NEXT_CHECK(nTests < stSettings.nMaximumDistanceTests);
		if (fScale >= 1)
		{
			ENGINE_NEXT_CHECK(dBound < dExact * 1.00001);
		}
		std::reverse(arrTarget.begin(), arrTarget.end());
		nTests = 0;
		double dReverseBound = -1;
		ENGINE_NEXT_CHECK(ComputeLodDeviationBound(stPrimitive, arrTarget, arrSource, stSettings, nTests, dReverseBound));
		ENGINE_NEXT_CHECK_EQ(dReverseBound, dBound);
		stSettings.nMaximumDistanceTests = 1;
		nTests = 0;
		dBound = 123;
		ENGINE_NEXT_CHECK(!ComputeLodDeviationBound(stPrimitive, arrSource, arrTarget, stSettings, nTests, dBound));
		ENGINE_NEXT_CHECK_EQ(nTests, 1ULL);
		ENGINE_NEXT_CHECK_EQ(dBound, 123.0);
		stPrimitive.arrVertices[arrTarget[0]].arrPosition[0] = std::numeric_limits<float>::quiet_NaN();
		nTests = 0;
		ENGINE_NEXT_CHECK(!ComputeLodDeviationBound(stPrimitive, arrSource, arrTarget, stSettings, nTests, dBound));
		ENGINE_NEXT_CHECK_EQ(nTests, 0ULL);
		ENGINE_NEXT_CHECK_EQ(dBound, 123.0);
	}
}
