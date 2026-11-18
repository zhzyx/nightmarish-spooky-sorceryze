/**************************************************************************/
/*  GeometryScene.cpp                                                     */
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

#include "engine_next/include/EngineNext/Rendering/GeometryScene.h"
#include "engine_next/Rendering/Cook/MeshCluster.h"

#include <cmath>
#include <limits>
#include <map>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
struct PrimitiveClusters
{
	std::vector<GpuClusterInput> arrClusters;
	std::uint32_t nMaterial = 0;
	std::uint32_t nTriangleCount = 0;
	bool bBlend = false;
	bool bDoubleSided = false;
};

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "geometry_source", "$.geometry_culling", pMessage);
	return false;
}

bool BuildPrimitive(const MeshPrimitive &stPrimitive, std::uint32_t nFirstIndex, std::int32_t nBaseVertex,
					PrimitiveClusters &out_stPrimitive, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::vector<MeshCluster> *pClusters = &stPrimitive.arrClusters;
	std::vector<MeshCluster> arrCooked;
	if (pClusters->empty())
	{
		if (!CookMeshClusters(stPrimitive, arrCooked, out_arrDiagnostics))
		{
			return false;
		}
		pClusters = &arrCooked;
	}
	const std::array<double, 16> arrIdentity{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	std::uint32_t nLocalFirst = 0;
	for (const MeshCluster &stCluster : *pClusters)
	{
		const std::size_t nCount = stCluster.arrTriangleIndices.size();
		if (nLocalFirst > stPrimitive.arrIndices.size() || nCount > stPrimitive.arrIndices.size() - nLocalFirst)
		{
			return Fail(out_arrDiagnostics, "Cluster ranges exceed the primitive index buffer.");
		}
		for (std::size_t nIndex = 0; nIndex < nCount; ++nIndex)
		{
			const std::uint8_t nLocal = stCluster.arrTriangleIndices[nIndex];
			if (nLocal >= stCluster.arrVertexIndices.size() || stCluster.arrVertexIndices[nLocal] >= stPrimitive.arrVertices.size() ||
				stCluster.arrVertexIndices[nLocal] != stPrimitive.arrIndices[nLocalFirst + nIndex])
			{
				return Fail(out_arrDiagnostics, "Cluster topology differs from its source primitive.");
			}
		}
		GpuClusterInput stInput;
		if (!BuildClusterInput(stCluster, arrIdentity, nFirstIndex + nLocalFirst, nBaseVertex, 0, stInput, out_arrDiagnostics))
		{
			return false;
		}
		out_stPrimitive.arrClusters.push_back(stInput);
		nLocalFirst += static_cast<std::uint32_t>(nCount);
	}
	if (nLocalFirst != stPrimitive.arrIndices.size())
	{
		return Fail(out_arrDiagnostics, "Clusters do not cover every primitive triangle.");
	}
	out_stPrimitive.nTriangleCount = nLocalFirst / 3;
	return true;
}
} //namespace

bool BuildGeometryClusterSet(const RenderScene &stScene, const GeometrySettings &stSettings,
							 GeometryClusterSet &out_stClusters, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateGeometrySettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	GeometryClusterSet stCandidate;
	if (stScene.arrInstances.size() > std::numeric_limits<std::uint32_t>::max())
	{
		return Fail(out_arrDiagnostics, "Draw count exceeds uint32.");
	}
	stCandidate.nDrawCount = static_cast<std::uint32_t>(stScene.arrInstances.size());
	std::vector<std::vector<PrimitiveClusters>> arrAssets(stScene.arrAssets.size());
	std::uint64_t nVertices = 0;
	std::uint64_t nIndices = 0;
	std::uint64_t nMaterials = 0;
	for (std::size_t nAsset = 0; nAsset < stScene.arrAssets.size(); ++nAsset)
	{
		const DecodedMesh &stMesh = stScene.arrAssets[nAsset].stMesh;
		arrAssets[nAsset].resize(stMesh.arrPrimitives.size());
		if (nMaterials + stMesh.arrMaterials.size() > std::numeric_limits<std::uint32_t>::max())
		{
			return Fail(out_arrDiagnostics, "Material offsets exceed uint32.");
		}
		for (std::size_t nPrimitive = 0; nPrimitive < stMesh.arrPrimitives.size(); ++nPrimitive)
		{
			const MeshPrimitive &stPrimitive = stMesh.arrPrimitives[nPrimitive];
			if (stPrimitive.nMaterial < 0 || static_cast<std::size_t>(stPrimitive.nMaterial) >= stMesh.arrMaterials.size() ||
				nVertices + stPrimitive.arrVertices.size() > static_cast<std::uint64_t>(std::numeric_limits<std::int32_t>::max()) ||
				nIndices + stPrimitive.arrIndices.size() > std::numeric_limits<std::uint32_t>::max())
			{
				return Fail(out_arrDiagnostics, "Primitive material or buffer offsets are invalid.");
			}
			PrimitiveClusters &stClusters = arrAssets[nAsset][nPrimitive];
			const MaterialData &stMaterial = stMesh.arrMaterials[stPrimitive.nMaterial];
			stClusters.nMaterial = static_cast<std::uint32_t>(nMaterials + stPrimitive.nMaterial);
			stClusters.bBlend = stMaterial.eAlphaMode == AlphaMode::Blend;
			stClusters.bDoubleSided = stMaterial.bDoubleSided;
			if (!BuildPrimitive(stPrimitive, static_cast<std::uint32_t>(nIndices), static_cast<std::int32_t>(nVertices), stClusters, out_arrDiagnostics))
			{
				return false;
			}
			nVertices += stPrimitive.arrVertices.size();
			nIndices += stPrimitive.arrIndices.size();
		}
		nMaterials += stMesh.arrMaterials.size();
	}
	std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint32_t> mapBuckets;
	std::vector<std::uint32_t> arrDrawBuckets(stScene.arrInstances.size(), std::numeric_limits<std::uint32_t>::max());
	for (std::size_t nDraw = 0; nDraw < stScene.arrInstances.size(); ++nDraw)
	{
		const RenderInstance &stInstance = stScene.arrInstances[nDraw];
		if (stInstance.nAsset >= arrAssets.size() || stInstance.nPrimitive >= arrAssets[stInstance.nAsset].size())
		{
			return Fail(out_arrDiagnostics, "Draw references a missing source primitive.");
		}
		const PrimitiveClusters &stPrimitive = arrAssets[stInstance.nAsset][stInstance.nPrimitive];
		stCandidate.nTriangleCount += stPrimitive.nTriangleCount;
		if (stPrimitive.bBlend)
		{
			continue;
		}
		const std::array<double, 16> &arrWorld = stInstance.arrTransform;
		for (double dValue : arrWorld)
		{
			if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
			{
				return Fail(out_arrDiagnostics, "Instance transforms must fit finite binary32.");
			}
		}
		if (arrWorld[3] != 0 || arrWorld[7] != 0 || arrWorld[11] != 0 || arrWorld[15] != 1)
		{
			return Fail(out_arrDiagnostics, "Instance transforms must be affine.");
		}
		const double dDeterminant = arrWorld[0] * (arrWorld[5] * arrWorld[10] - arrWorld[6] * arrWorld[9]) -
				arrWorld[4] * (arrWorld[1] * arrWorld[10] - arrWorld[2] * arrWorld[9]) + arrWorld[8] * (arrWorld[1] * arrWorld[6] - arrWorld[2] * arrWorld[5]);
		const std::uint32_t nFlags = (dDeterminant < 0 ? 1U : 0U) | (stPrimitive.bDoubleSided ? 2U : 0U);
		const std::pair<std::uint32_t, std::uint32_t> stKey{ stPrimitive.nMaterial, nFlags };
		std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint32_t>::iterator itBucket = mapBuckets.find(stKey);
		if (itBucket == mapBuckets.end())
		{
			const std::uint32_t nBucket = static_cast<std::uint32_t>(stCandidate.arrBuckets.size());
			itBucket = mapBuckets.emplace(stKey, nBucket).first;
			stCandidate.arrBuckets.push_back({ stPrimitive.nMaterial, nFlags, 0, 0 });
		}
		arrDrawBuckets[nDraw] = itBucket->second;
		const std::uint64_t nCount = stPrimitive.arrClusters.size();
		stCandidate.nCandidateCount += nCount;
		if (stCandidate.nCandidateCount <= stSettings.nMaxCommands)
		{
			stCandidate.arrBuckets[itBucket->second].nCommandCapacity += static_cast<std::uint32_t>(nCount);
		}
	}
	if (stCandidate.nCandidateCount > stSettings.nMaxCommands || stScene.arrInstances.size() > std::numeric_limits<std::uint32_t>::max())
	{
		stCandidate.bCapacityFallback = true;
		stCandidate.arrBuckets.clear();
		out_stClusters = std::move(stCandidate);
		return true;
	}
	std::uint32_t nFirst = 0;
	std::vector<std::uint32_t> arrWriteOffsets;
	for (GeometryBucket &stBucket : stCandidate.arrBuckets)
	{
		stBucket.nFirstCommand = nFirst;
		arrWriteOffsets.push_back(nFirst);
		nFirst += stBucket.nCommandCapacity;
	}
	stCandidate.arrClusters.resize(static_cast<std::size_t>(stCandidate.nCandidateCount));
	for (std::size_t nDraw = 0; nDraw < stScene.arrInstances.size(); ++nDraw)
	{
		const std::uint32_t nBucket = arrDrawBuckets[nDraw];
		if (nBucket == std::numeric_limits<std::uint32_t>::max())
		{
			continue;
		}
		const RenderInstance &stInstance = stScene.arrInstances[nDraw];
		for (const GpuClusterInput &stInput : arrAssets[stInstance.nAsset][stInstance.nPrimitive].arrClusters)
		{
			GeometryCluster &stOutput = stCandidate.arrClusters[arrWriteOffsets[nBucket]++];
			stOutput.stInput = stInput;
			stOutput.stInput.arrDraw[3] = static_cast<std::uint32_t>(nDraw);
			stOutput.arrMetadata[0] = nBucket;
		}
	}
	out_stClusters = std::move(stCandidate);
	return true;
}
} // namespace EngineNext::Rendering
