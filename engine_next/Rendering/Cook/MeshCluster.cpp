/**************************************************************************/
/*  MeshCluster.cpp                                                       */
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

#include "engine_next/Rendering/Cook/MeshCluster.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace EngineNext::Rendering
{

namespace
{

constexpr std::size_t MAX_INPUT_BYTES = 256ULL * 1024ULL * 1024ULL;
constexpr std::size_t MAX_CLUSTER_COUNT = 65536;

bool IsDegenerate(const MeshPrimitive &stPrimitive, std::size_t nOffset)
{
	const std::array<float, 3> &arrFirst = stPrimitive.arrVertices[stPrimitive.arrIndices[nOffset]].arrPosition;
	const std::array<float, 3> &arrSecond = stPrimitive.arrVertices[stPrimitive.arrIndices[nOffset + 1]].arrPosition;
	const std::array<float, 3> &arrThird = stPrimitive.arrVertices[stPrimitive.arrIndices[nOffset + 2]].arrPosition;
	std::array<double, 3> arrFirstEdge{};
	std::array<double, 3> arrSecondEdge{};
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		arrFirstEdge[nAxis] = static_cast<double>(arrSecond[nAxis]) - arrFirst[nAxis];
		arrSecondEdge[nAxis] = static_cast<double>(arrThird[nAxis]) - arrFirst[nAxis];
	}
	return arrFirstEdge[1] * arrSecondEdge[2] == arrFirstEdge[2] * arrSecondEdge[1] &&
			arrFirstEdge[2] * arrSecondEdge[0] == arrFirstEdge[0] * arrSecondEdge[2] &&
			arrFirstEdge[0] * arrSecondEdge[1] == arrFirstEdge[1] * arrSecondEdge[0];
}

bool FinishCluster(const MeshPrimitive &stPrimitive, MeshCluster &stCluster, std::vector<MeshCluster> &out_arrClusters, Assets::Diagnostics &out_arrDiagnostics)
{
	if (out_arrClusters.size() >= MAX_CLUSTER_COUNT)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "mesh_cluster_budget", "$.mesh.clusters", "Mesh cluster count exceeds the cook budget.");
		return false;
	}
	stCluster.arrBoundsMinimum = stPrimitive.arrVertices[stCluster.arrVertexIndices[0]].arrPosition;
	stCluster.arrBoundsMaximum = stCluster.arrBoundsMinimum;
	for (std::uint32_t nVertex : stCluster.arrVertexIndices)
	{
		const std::array<float, 3> &arrPosition = stPrimitive.arrVertices[nVertex].arrPosition;
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stCluster.arrBoundsMinimum[nAxis] = (std::min)(stCluster.arrBoundsMinimum[nAxis], arrPosition[nAxis]);
			stCluster.arrBoundsMaximum[nAxis] = (std::max)(stCluster.arrBoundsMaximum[nAxis], arrPosition[nAxis]);
		}
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		const double dCenter = (static_cast<double>(stCluster.arrBoundsMinimum[nAxis]) + stCluster.arrBoundsMaximum[nAxis]) * 0.5;
		stCluster.arrSphereCenter[nAxis] = static_cast<float>(dCenter);
	}
	double dRadiusSquared = 0.0;
	for (std::uint32_t nVertex : stCluster.arrVertexIndices)
	{
		const std::array<float, 3> &arrPosition = stPrimitive.arrVertices[nVertex].arrPosition;
		double dDistanceSquared = 0.0;
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			const double dOffset = static_cast<double>(arrPosition[nAxis]) - stCluster.arrSphereCenter[nAxis];
			dDistanceSquared += dOffset * dOffset;
		}
		dRadiusSquared = (std::max)(dRadiusSquared, dDistanceSquared);
	}
	const double dRadius = std::sqrt(dRadiusSquared);
	if (dRadius > std::numeric_limits<float>::max())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "mesh_cluster_bounds", "$.mesh.clusters", "Cluster sphere radius exceeds the finite binary32 range.");
		return false;
	}
	stCluster.fSphereRadius = static_cast<float>(dRadius);
	if (stCluster.fSphereRadius > 0.0F && stCluster.fSphereRadius < std::numeric_limits<float>::max())
	{
		stCluster.fSphereRadius = std::nextafter(stCluster.fSphereRadius, std::numeric_limits<float>::infinity());
	}
	out_arrClusters.push_back(std::move(stCluster));
	return true;
}

} // namespace

bool CookMeshClusters(const MeshPrimitive &stPrimitive, std::vector<MeshCluster> &out_arrClusters, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::size_t nVertexCount = stPrimitive.arrVertices.size();
	const std::size_t nIndexCount = stPrimitive.arrIndices.size();
	if (nVertexCount == 0 || nIndexCount == 0 || nIndexCount % 3 != 0)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "mesh_cluster_geometry", "$.mesh", "A nonempty indexed triangle primitive is required.");
		return false;
	}
	if (nVertexCount > MAX_INPUT_BYTES / sizeof(MeshVertex) || nIndexCount > (MAX_INPUT_BYTES - nVertexCount * sizeof(MeshVertex)) / sizeof(std::uint32_t) ||
		nIndexCount / 3 > MAX_CLUSTER_COUNT * MAX_MESH_CLUSTER_TRIANGLES)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "mesh_cluster_budget", "$.mesh", "Mesh input exceeds the byte or triangle cook budget.");
		return false;
	}
	for (std::size_t nVertex = 0; nVertex < nVertexCount; ++nVertex)
	{
		for (float fPosition : stPrimitive.arrVertices[nVertex].arrPosition)
		{
			if (!std::isfinite(fPosition))
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "mesh_cluster_geometry", "$.mesh.vertices[" + std::to_string(nVertex) + "]", "Vertex positions must be finite.");
				return false;
			}
		}
	}
	for (std::size_t nIndex = 0; nIndex < nIndexCount; ++nIndex)
	{
		if (stPrimitive.arrIndices[nIndex] >= nVertexCount)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "mesh_cluster_geometry", "$.mesh.indices[" + std::to_string(nIndex) + "]", "Triangle vertex index is out of range.");
			return false;
		}
	}

	std::vector<MeshCluster> arrClusters;
	MeshCluster stCluster;
	stCluster.arrVertexIndices.reserve(MAX_MESH_CLUSTER_VERTICES);
	stCluster.arrTriangleIndices.reserve(MAX_MESH_CLUSTER_TRIANGLES * 3);
	for (std::size_t nOffset = 0; nOffset < nIndexCount; nOffset += 3)
	{
		const std::uint32_t *pTriangle = stPrimitive.arrIndices.data() + nOffset;
		std::size_t nAdditionalVertices = 0;
		for (std::size_t nCorner = 0; nCorner < 3; ++nCorner)
		{
			const std::uint32_t nVertex = pTriangle[nCorner];
			const bool bInCluster = std::find(stCluster.arrVertexIndices.begin(), stCluster.arrVertexIndices.end(), nVertex) != stCluster.arrVertexIndices.end();
			const bool bInTriangle = std::find(pTriangle, pTriangle + nCorner, nVertex) != pTriangle + nCorner;
			if (!bInCluster && !bInTriangle)
			{
				++nAdditionalVertices;
			}
		}
		if (stCluster.arrVertexIndices.size() + nAdditionalVertices > MAX_MESH_CLUSTER_VERTICES || stCluster.arrTriangleIndices.size() == MAX_MESH_CLUSTER_TRIANGLES * 3)
		{
			if (!FinishCluster(stPrimitive, stCluster, arrClusters, out_arrDiagnostics))
			{
				return false;
			}
			stCluster = MeshCluster{};
			stCluster.arrVertexIndices.reserve(MAX_MESH_CLUSTER_VERTICES);
			stCluster.arrTriangleIndices.reserve(MAX_MESH_CLUSTER_TRIANGLES * 3);
		}
		for (std::size_t nCorner = 0; nCorner < 3; ++nCorner)
		{
			const std::uint32_t nVertex = pTriangle[nCorner];
			const std::vector<std::uint32_t>::const_iterator itVertex = std::find(stCluster.arrVertexIndices.cbegin(), stCluster.arrVertexIndices.cend(), nVertex);
			const std::uint8_t nLocalVertex = static_cast<std::uint8_t>(itVertex - stCluster.arrVertexIndices.cbegin());
			if (itVertex == stCluster.arrVertexIndices.cend())
			{
				stCluster.arrVertexIndices.push_back(nVertex);
			}
			stCluster.arrTriangleIndices.push_back(nLocalVertex);
		}
		if (IsDegenerate(stPrimitive, nOffset))
		{
			++stCluster.nDegenerateTriangleCount;
		}
	}
	if (!FinishCluster(stPrimitive, stCluster, arrClusters, out_arrDiagnostics))
	{
		return false;
	}
	out_arrClusters = std::move(arrClusters);
	return true;
}

} // namespace EngineNext::Rendering
