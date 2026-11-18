/**************************************************************************/
/*  PagedGeometry.cpp                                                     */
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
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <limits>
#include <map>
#include <utility>
namespace EngineNext::Rendering
{
namespace
{
bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "paged_geometry", "$", pMessage);
	return false;
}
} // namespace
std::uint64_t PagedWorldCache::CachedBytes() const noexcept
{
	return nBytes;
}
std::uint64_t PagedWorldCache::Hits() const noexcept
{
	return nHits;
}
std::uint64_t PagedWorldCache::Misses() const noexcept
{
	return nMisses;
}
bool TransformLodTree(const GpuLodTree &stTree, const std::array<float, 16> &arrWorld,
					  std::vector<LodNode> &out_arrNodes, Assets::Diagnostics &out_arrDiagnostics)
{
	if (arrWorld[3] != 0 || arrWorld[7] != 0 || arrWorld[11] != 0 || arrWorld[15] != 1)
	{
		return Fail(out_arrDiagnostics, "LOD world matrix must be affine.");
	}
	for (float fValue : arrWorld)
	{
		if (!std::isfinite(fValue))
		{
			return Fail(out_arrDiagnostics, "LOD world matrix must be finite.");
		}
	}
	double dNormOne = 0;
	double dNormInf = 0;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		double dColumn = 0;
		double dRow = 0;
		for (std::size_t nInner = 0; nInner < 3; ++nInner)
		{
			dColumn += std::abs(static_cast<double>(arrWorld[nAxis * 4 + nInner]));
			dRow += std::abs(static_cast<double>(arrWorld[nInner * 4 + nAxis]));
		}
		dNormOne = (std::max)(dNormOne, dColumn);
		dNormInf = (std::max)(dNormInf, dRow);
	}
	const double dScale = std::sqrt(dNormOne * dNormInf);
	std::vector<LodNode> arrNodes = stTree.arrNodes;
	for (LodNode &stNode : arrNodes)
	{
		if (!std::isfinite(stNode.dGeometricErrorBound) || stNode.dGeometricErrorBound < 0)
		{
			return Fail(out_arrDiagnostics, "LOD error must be finite and nonnegative.");
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			if (!std::isfinite(stNode.arrMinimum[nAxis]) || !std::isfinite(stNode.arrMaximum[nAxis]) || stNode.arrMinimum[nAxis] > stNode.arrMaximum[nAxis])
			{
				return Fail(out_arrDiagnostics, "LOD local bounds must be ordered and finite.");
			}
		}
		std::array<double, 3> arrMinimum{};
		std::array<double, 3> arrMaximum{};
		arrMinimum.fill(std::numeric_limits<double>::max());
		arrMaximum.fill(-std::numeric_limits<double>::max());
		double dMaximumRoundoff = 0;
		for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
		{
			std::array<double, 3> arrPosition{};
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrPosition[nAxis] = (nCorner & (1U << nAxis)) != 0 ? stNode.arrMaximum[nAxis] : stNode.arrMinimum[nAxis];
				if (!std::isfinite(arrPosition[nAxis]))
				{
					return Fail(out_arrDiagnostics, "LOD local bounds must be finite.");
				}
			}
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				double dValue = arrWorld[12 + nAxis];
				double dMagnitude = std::abs(dValue);
				for (std::size_t nInner = 0; nInner < 3; ++nInner)
				{
					const double dTerm = static_cast<double>(arrWorld[nInner * 4 + nAxis]) * arrPosition[nInner];
					dValue += dTerm;
					dMagnitude += std::abs(dTerm);
				}
				const double dRoundoff = 8 * std::numeric_limits<float>::epsilon() * dMagnitude;
				if (!std::isfinite(dValue) || std::abs(dValue) + dRoundoff > std::numeric_limits<float>::max())
				{
					return Fail(out_arrDiagnostics, "LOD world bounds exceed binary32 range.");
				}
				arrMinimum[nAxis] = (std::min)(arrMinimum[nAxis], dValue - dRoundoff);
				arrMaximum[nAxis] = (std::max)(arrMaximum[nAxis], dValue + dRoundoff);
				dMaximumRoundoff = (std::max)(dMaximumRoundoff, dRoundoff);
			}
		}
		stNode.arrMinimum = arrMinimum;
		stNode.arrMaximum = arrMaximum;
		if (stNode.dGeometricErrorBound != 0)
		{
			stNode.dGeometricErrorBound = stNode.dGeometricErrorBound * dScale + 2 * std::sqrt(3.0) * dMaximumRoundoff;
		}
	}
	out_arrNodes = std::move(arrNodes);
	return true;
}
bool BuildPagedFrameSelection(const GpuPageIndex &stIndex, const RenderScene &stSource,
							  const std::vector<std::array<float, 16>> &arrWorlds,
							  const std::vector<std::uint8_t> &arrResident, const LodView &stView,
							  const GeometrySettings &stSettings, const PagedFrameSelection &stPrevious,
							  PagedFrameSelection &out_stSelection, Assets::Diagnostics &out_arrDiagnostics, PagedWorldCache *pCache)
{
	if (!ValidateGeometrySettings(stSettings, out_arrDiagnostics) || arrWorlds.size() != stSource.arrInstances.size() ||
		arrResident.size() != stIndex.Pages().size() || (!stPrevious.arrDraws.empty() && stPrevious.arrDraws.size() != arrWorlds.size()))
	{
		return Fail(out_arrDiagnostics, "Paged draw, residency or previous frame dimensions differ.");
	}
	for (std::uint8_t nResident : arrResident)
	{
		if (nResident > 1)
		{
			return Fail(out_arrDiagnostics, "Paged residency must be binary.");
		}
	}
	constexpr std::uint64_t MAX_CACHE_BYTES = 64ULL * 1024 * 1024;
	if (pCache != nullptr &&
		(pCache->strIdentity != stIndex.DescriptionDigest() ||
		 pCache->arrEntries.size() != arrWorlds.size()))
	{
		*pCache = PagedWorldCache{};
		pCache->strIdentity = stIndex.DescriptionDigest();
		if (arrWorlds.size() <= MAX_CACHE_BYTES / sizeof(PagedWorldCache::Entry))
		{
			pCache->arrEntries.resize(arrWorlds.size());
			pCache->nBytes =
					pCache->arrEntries.capacity() * sizeof(PagedWorldCache::Entry);
		}
	}
	std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint32_t> mapTrees;
	for (std::uint32_t nTree = 0; nTree < stIndex.Trees().size(); ++nTree)
	{
		const GpuLodTree &stTree = stIndex.Trees()[nTree];
		mapTrees.emplace(std::make_pair(stTree.nAsset, stTree.nPrimitive), nTree);
	}
	PagedFrameSelection stCandidate;
	stCandidate.arrDraws.resize(arrWorlds.size());
	stCandidate.bRootsReady = true;
	std::vector<std::uint8_t> arrRequests(arrResident.size(), 0);
	for (std::uint32_t nDraw = 0; nDraw < stSource.arrInstances.size(); ++nDraw)
	{
		const RenderInstance &stInstance = stSource.arrInstances[nDraw];
		if (stInstance.nAsset >= stSource.arrAssets.size() || stInstance.nPrimitive >= stSource.arrAssets[stInstance.nAsset].stMesh.arrPrimitives.size())
		{
			return Fail(out_arrDiagnostics, "Paged draw references a missing primitive.");
		}
		const RenderAsset &stAsset = stSource.arrAssets[stInstance.nAsset];
		const MeshPrimitive &stPrimitive = stAsset.stMesh.arrPrimitives[stInstance.nPrimitive];
		if (stPrimitive.nMaterial < 0 || static_cast<std::size_t>(stPrimitive.nMaterial) >= stAsset.stMesh.arrMaterials.size())
		{
			return Fail(out_arrDiagnostics, "Paged primitive references a missing material.");
		}
		if (stAsset.stMesh.arrMaterials[stPrimitive.nMaterial].eAlphaMode == AlphaMode::Blend)
		{
			continue;
		}
		const std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint32_t>::const_iterator it = mapTrees.find({ stInstance.nAsset, stInstance.nPrimitive });
		if (it == mapTrees.end())
		{
			return Fail(out_arrDiagnostics, "Paged draw has no matching source hierarchy.");
		}
		PagedDrawSelection &stDraw = stCandidate.arrDraws[nDraw];
		stDraw.nTree = it->second;
		const GpuLodTree &stTree = stIndex.Trees()[stDraw.nTree];
		bool bRootsReady = true;
		for (std::uint32_t nRoot : stTree.arrRoots)
		{
			const std::uint32_t nPage = stTree.arrNodes[nRoot].nPage;
			if (arrResident[nPage] == 0)
			{
				arrRequests[nPage] = 1;
				bRootsReady = false;
				stCandidate.bRootsReady = false;
			}
		}
		if (!bRootsReady)
		{
			continue;
		}
		std::vector<LodNode> arrUncachedNodes;
		const std::vector<LodNode> *pWorldNodes = &arrUncachedNodes;
		PagedWorldCache::Entry *pEntry =
				pCache != nullptr && nDraw < pCache->arrEntries.size()
				? &pCache->arrEntries[nDraw]
				: nullptr;
		if (pEntry != nullptr && pEntry->nTree == stDraw.nTree &&
			std::memcmp(pEntry->arrWorld.data(), arrWorlds[nDraw].data(),
						sizeof(pEntry->arrWorld)) == 0)
		{
			pWorldNodes = &pEntry->arrNodes;
			if (pCache->nHits != UINT64_MAX)
			{
				++pCache->nHits;
			}
		}
		else
		{
			if (!TransformLodTree(stTree, arrWorlds[nDraw], arrUncachedNodes, out_arrDiagnostics))
			{
				return false;
			}
			if (pCache != nullptr && pCache->nMisses != UINT64_MAX)
			{
				++pCache->nMisses;
			}
			if (pEntry != nullptr)
			{
				const std::uint64_t nPrevious =
						pEntry->arrNodes.capacity() * sizeof(LodNode);
				const std::uint64_t nNext =
						arrUncachedNodes.capacity() * sizeof(LodNode);
				if (nNext <= MAX_CACHE_BYTES - (pCache->nBytes - nPrevious))
				{
					pCache->nBytes = pCache->nBytes - nPrevious + nNext;
					pEntry->arrWorld = arrWorlds[nDraw];
					pEntry->nTree = stDraw.nTree;
					pEntry->arrNodes = std::move(arrUncachedNodes);
					pWorldNodes = &pEntry->arrNodes;
				}
			}
		}
		LodView stDrawView = stView;
		stDrawView.dMaximumErrorPixels = stSettings.dPixelError;
		const std::vector<std::uint32_t> arrEmpty;
		const std::vector<std::uint32_t> &arrPrevious = !stPrevious.arrDraws.empty() && stPrevious.arrDraws[nDraw].nTree == stDraw.nTree ? stPrevious.arrDraws[nDraw].stCut.arrNodes : arrEmpty;
		if (!SelectLodCutWithHistory(
					*pWorldNodes, stTree.arrRoots, arrResident, stDrawView, (std::min)(stSettings.nMaxCommands, 1U << 20),
					arrPrevious, stSettings.dLodHysteresis, stDraw.stCut, out_arrDiagnostics))
		{
			return false;
		}
		for (std::uint32_t nPage : stDraw.stCut.arrRequestedPages)
		{
			arrRequests[nPage] = 1;
		}
	}
	for (std::uint32_t nPage = 0; nPage < arrRequests.size(); ++nPage)
	{
		if (arrRequests[nPage] != 0)
		{
			stCandidate.arrRequestedPages.push_back(nPage);
		}
	}
	out_stSelection = std::move(stCandidate);
	return true;
}
} // namespace EngineNext::Rendering
