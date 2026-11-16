/**************************************************************************/
/*  TestMeshCluster.cpp                                                   */
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
#include "engine_next/Rendering/Cook/MeshCluster.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace
{

using EngineNext::Rendering::MeshCluster;
using EngineNext::Rendering::MeshPrimitive;
using EngineNext::Rendering::MeshVertex;

MeshPrimitive Triangle()
{
	MeshPrimitive stPrimitive;
	stPrimitive.arrVertices.resize(3);
	stPrimitive.arrVertices[0].arrPosition = { -2.0F, -3.0F, 1.0F };
	stPrimitive.arrVertices[1].arrPosition = { 4.0F, -3.0F, 1.0F };
	stPrimitive.arrVertices[2].arrPosition = { -2.0F, 5.0F, 1.0F };
	stPrimitive.arrIndices = { 0, 1, 2 };
	return stPrimitive;
}

bool EqualClusters(const std::vector<MeshCluster> &arrFirst, const std::vector<MeshCluster> &arrSecond)
{
	if (arrFirst.size() != arrSecond.size())
	{
		return false;
	}
	for (std::size_t nCluster = 0; nCluster < arrFirst.size(); ++nCluster)
	{
		const MeshCluster &stFirst = arrFirst[nCluster];
		const MeshCluster &stSecond = arrSecond[nCluster];
		if (stFirst.arrVertexIndices != stSecond.arrVertexIndices || stFirst.arrTriangleIndices != stSecond.arrTriangleIndices ||
			stFirst.arrBoundsMinimum != stSecond.arrBoundsMinimum || stFirst.arrBoundsMaximum != stSecond.arrBoundsMaximum ||
			stFirst.arrSphereCenter != stSecond.arrSphereCenter || stFirst.fSphereRadius != stSecond.fSphereRadius ||
			stFirst.nDegenerateTriangleCount != stSecond.nDegenerateTriangleCount)
		{
			return false;
		}
	}
	return true;
}

bool PreservesGeometry(const MeshPrimitive &stPrimitive, const std::vector<MeshCluster> &arrClusters)
{
	std::vector<std::uint32_t> arrReconstructed;
	for (const MeshCluster &stCluster : arrClusters)
	{
		if (stCluster.arrVertexIndices.empty() || stCluster.arrVertexIndices.size() > EngineNext::Rendering::MAX_MESH_CLUSTER_VERTICES ||
			stCluster.arrTriangleIndices.empty() || stCluster.arrTriangleIndices.size() > EngineNext::Rendering::MAX_MESH_CLUSTER_TRIANGLES * 3 ||
			stCluster.arrTriangleIndices.size() % 3 != 0 || !std::isfinite(stCluster.fSphereRadius) || stCluster.fSphereRadius < 0.0F)
		{
			return false;
		}
		std::vector<std::uint32_t> arrUnique = stCluster.arrVertexIndices;
		std::sort(arrUnique.begin(), arrUnique.end());
		if (std::adjacent_find(arrUnique.begin(), arrUnique.end()) != arrUnique.end())
		{
			return false;
		}
		for (std::uint8_t nLocalVertex : stCluster.arrTriangleIndices)
		{
			if (nLocalVertex >= stCluster.arrVertexIndices.size())
			{
				return false;
			}
			arrReconstructed.push_back(stCluster.arrVertexIndices[nLocalVertex]);
		}
		for (std::uint32_t nVertex : stCluster.arrVertexIndices)
		{
			if (nVertex >= stPrimitive.arrVertices.size())
			{
				return false;
			}
			double dDistanceSquared = 0.0;
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				const float fPosition = stPrimitive.arrVertices[nVertex].arrPosition[nAxis];
				if (fPosition < stCluster.arrBoundsMinimum[nAxis] || fPosition > stCluster.arrBoundsMaximum[nAxis])
				{
					return false;
				}
				const double dOffset = static_cast<double>(fPosition) - stCluster.arrSphereCenter[nAxis];
				dDistanceSquared += dOffset * dOffset;
			}
			if (dDistanceSquared > static_cast<double>(stCluster.fSphereRadius) * stCluster.fSphereRadius)
			{
				return false;
			}
		}
	}
	return arrReconstructed == stPrimitive.arrIndices;
}

bool Cook(const MeshPrimitive &stPrimitive, std::vector<MeshCluster> &out_arrClusters)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return EngineNext::Rendering::CookMeshClusters(stPrimitive, out_arrClusters, arrDiagnostics);
}

} // namespace

ENGINE_NEXT_TEST("Mesh clusters preserve twenty thousand ordered triangles and shared vertices")
{
	MeshPrimitive stPrimitive;
	for (std::uint32_t nY = 0; nY <= 100; ++nY)
	{
		for (std::uint32_t nX = 0; nX <= 100; ++nX)
		{
			MeshVertex stVertex;
			stVertex.arrPosition = { static_cast<float>(nX), static_cast<float>(nY), 0.0F };
			stPrimitive.arrVertices.push_back(stVertex);
		}
	}
	for (std::uint32_t nY = 0; nY < 100; ++nY)
	{
		for (std::uint32_t nX = 0; nX < 100; ++nX)
		{
			const std::uint32_t nVertex = nY * 101 + nX;
			stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { nVertex, nVertex + 1, nVertex + 101, nVertex + 1, nVertex + 102, nVertex + 101 });
		}
	}
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK(arrClusters.size() > 1);
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
	std::size_t nTriangleCount = 0;
	std::size_t nDegenerateCount = 0;
	for (const MeshCluster &stCluster : arrClusters)
	{
		nTriangleCount += stCluster.arrTriangleIndices.size() / 3;
		nDegenerateCount += stCluster.nDegenerateTriangleCount;
	}
	ENGINE_NEXT_CHECK_EQ(nTriangleCount, 20000U);
	ENGINE_NEXT_CHECK_EQ(nDegenerateCount, 0U);
	std::vector<MeshCluster> arrRepeated;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrRepeated));
	ENGINE_NEXT_CHECK(EqualClusters(arrClusters, arrRepeated));
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookMeshClusters(stPrimitive, stPrimitive.arrClusters, arrDiagnostics));
	ENGINE_NEXT_CHECK(EqualClusters(arrClusters, stPrimitive.arrClusters));
}

ENGINE_NEXT_TEST("Mesh clusters split exactly at sixty four unique vertices")
{
	MeshPrimitive stPrimitive;
	for (std::uint32_t nVertex = 0; nVertex < 65; ++nVertex)
	{
		MeshVertex stVertex;
		stVertex.arrPosition = { static_cast<float>(nVertex), static_cast<float>(nVertex * nVertex), 0.0F };
		stPrimitive.arrVertices.push_back(stVertex);
	}
	for (std::uint32_t nVertex = 1; nVertex < 64; ++nVertex)
	{
		stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { 0, nVertex, nVertex + 1 });
	}
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK_EQ(arrClusters.size(), 2U);
	if (arrClusters.size() != 2)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrVertexIndices.size(), 64U);
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrTriangleIndices.size(), 62U * 3U);
	ENGINE_NEXT_CHECK_EQ(arrClusters[1].arrVertexIndices, (std::vector<std::uint32_t>{ 0, 63, 64 }));
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
}

ENGINE_NEXT_TEST("Mesh clusters split at one hundred twenty six triangles")
{
	MeshPrimitive stPrimitive = Triangle();
	stPrimitive.arrIndices.clear();
	for (std::size_t nTriangle = 0; nTriangle < 127; ++nTriangle)
	{
		stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { 2, 0, 1 });
	}
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK_EQ(arrClusters.size(), 2U);
	if (arrClusters.size() != 2)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrTriangleIndices.size(), 378U);
	ENGINE_NEXT_CHECK_EQ(arrClusters[1].arrTriangleIndices.size(), 3U);
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrVertexIndices, (std::vector<std::uint32_t>{ 2, 0, 1 }));
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
}

ENGINE_NEXT_TEST("Mesh clusters retain duplicate and collinear degenerate triangles")
{
	MeshPrimitive stPrimitive = Triangle();
	MeshVertex stVertex;
	stVertex.arrPosition = { 1.0F, -3.0F, 1.0F };
	stPrimitive.arrVertices.push_back(stVertex);
	stPrimitive.arrIndices = { 0, 1, 2, 0, 0, 1, 0, 3, 1, 2, 2, 2 };
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK_EQ(arrClusters.size(), 1U);
	if (arrClusters.size() != 1)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].nDegenerateTriangleCount, 3U);
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
	stPrimitive.arrIndices = { 2, 2, 2 };
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrVertexIndices.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].fSphereRadius, 0.0F);
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
}

ENGINE_NEXT_TEST("Mesh cluster bounds exclude unused vertices and enclose referenced coordinates")
{
	MeshPrimitive stPrimitive = Triangle();
	MeshVertex stUnused;
	stUnused.arrPosition = { 1000.0F, 1000.0F, 1000.0F };
	stPrimitive.arrVertices.push_back(stUnused);
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	if (arrClusters.empty())
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrBoundsMinimum, (std::array<float, 3>{ -2.0F, -3.0F, 1.0F }));
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrBoundsMaximum, (std::array<float, 3>{ 4.0F, 5.0F, 1.0F }));
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrSphereCenter, (std::array<float, 3>{ 1.0F, 1.0F, 1.0F }));
	ENGINE_NEXT_CHECK(arrClusters[0].fSphereRadius >= 5.0F);
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
	const float fSmall = std::numeric_limits<float>::denorm_min();
	stPrimitive = Triangle();
	stPrimitive.arrVertices[0].arrPosition = { 0.0F, 0.0F, 0.0F };
	stPrimitive.arrVertices[1].arrPosition = { fSmall, 0.0F, 0.0F };
	stPrimitive.arrVertices[2].arrPosition = { 0.0F, fSmall, 0.0F };
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].nDegenerateTriangleCount, 0U);
}

ENGINE_NEXT_TEST("Mesh cluster validation rejects malformed geometry without replacing output")
{
	const MeshPrimitive stValid = Triangle();
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stValid, arrClusters));
	const std::vector<MeshCluster> arrOriginal = arrClusters;
	MeshPrimitive stInvalid = stValid;
	stInvalid.arrIndices = { 0, 1, 3 };
	ENGINE_NEXT_CHECK(!Cook(stInvalid, arrClusters));
	ENGINE_NEXT_CHECK(EqualClusters(arrClusters, arrOriginal));
	stInvalid.arrIndices = { 0, 1 };
	ENGINE_NEXT_CHECK(!Cook(stInvalid, arrClusters));
	stInvalid.arrIndices.clear();
	ENGINE_NEXT_CHECK(!Cook(stInvalid, arrClusters));
	stInvalid = stValid;
	stInvalid.arrVertices.clear();
	ENGINE_NEXT_CHECK(!Cook(stInvalid, arrClusters));
	for (float fInvalid : { std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN() })
	{
		stInvalid = stValid;
		stInvalid.arrVertices[1].arrPosition[0] = fInvalid;
		ENGINE_NEXT_CHECK(!Cook(stInvalid, arrClusters));
		ENGINE_NEXT_CHECK(EqualClusters(arrClusters, arrOriginal));
	}
	stInvalid = stValid;
	const float fMaximum = std::numeric_limits<float>::max();
	stInvalid.arrVertices[0].arrPosition = { -fMaximum, -fMaximum, -fMaximum };
	stInvalid.arrVertices[1].arrPosition = { fMaximum, fMaximum, fMaximum };
	stInvalid.arrVertices[2].arrPosition = { fMaximum, -fMaximum, fMaximum };
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshClusters(stInvalid, arrClusters, arrDiagnostics));
	ENGINE_NEXT_CHECK(EqualClusters(arrClusters, arrOriginal));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, "mesh_cluster_bounds");
}

ENGINE_NEXT_TEST("Mesh cluster cook enforces the bounded cluster count transactionally")
{
	MeshPrimitive stPrimitive = Triangle();
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	const std::vector<MeshCluster> arrOriginal = arrClusters;
	stPrimitive.arrIndices.assign((65536U * EngineNext::Rendering::MAX_MESH_CLUSTER_TRIANGLES + 1U) * 3U, 0);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshClusters(stPrimitive, arrClusters, arrDiagnostics));
	ENGINE_NEXT_CHECK(EqualClusters(arrClusters, arrOriginal));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, "mesh_cluster_budget");
}

ENGINE_NEXT_TEST("Mesh clusters count newly referenced duplicate corners once at the vertex boundary")
{
	MeshPrimitive stPrimitive;
	stPrimitive.arrVertices.resize(65);
	for (std::uint32_t nVertex = 0; nVertex < 65; ++nVertex)
	{
		stPrimitive.arrVertices[nVertex].arrPosition = { static_cast<float>(nVertex), 0.0F, 0.0F };
	}
	for (std::uint32_t nVertex = 0; nVertex < 63; nVertex += 3)
	{
		stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { nVertex, nVertex + 1, nVertex + 2 });
	}
	stPrimitive.arrIndices.insert(stPrimitive.arrIndices.end(), { 63, 63, 0, 64, 64, 64 });
	std::vector<MeshCluster> arrClusters;
	ENGINE_NEXT_CHECK(Cook(stPrimitive, arrClusters));
	ENGINE_NEXT_CHECK_EQ(arrClusters.size(), 2U);
	if (arrClusters.size() != 2)
	{
		return;
	}
	ENGINE_NEXT_CHECK_EQ(arrClusters[0].arrVertexIndices.size(), 64U);
	ENGINE_NEXT_CHECK_EQ(arrClusters[1].arrVertexIndices.size(), 1U);
	ENGINE_NEXT_CHECK(PreservesGeometry(stPrimitive, arrClusters));
}
