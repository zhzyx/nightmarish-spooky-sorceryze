/**************************************************************************/
/*  LodSelection.cpp                                                      */
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

#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::size_t MAX_METADATA_ITEMS = 1U << 20;
bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "lod_selection", "$", pMessage);
	return false;
}
struct Choice
{
	double dError = 0;
	std::uint32_t nNode = 0;
};
struct LowerPriority
{
	bool operator()(const Choice &stLeft, const Choice &stRight) const noexcept
	{
		if (stLeft.dError != stRight.dError)
		{
			return stLeft.dError < stRight.dError;
		}
		return stLeft.nNode > stRight.nNode;
	}
};
double ProjectedError(const LodNode &stNode, const LodView &stView)
{
	if (stNode.dGeometricErrorBound == 0)
	{
		return 0;
	}
	std::array<double, 3> arrDelta{};
	std::array<double, 3> arrHalf{};
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		arrHalf[nAxis] = stNode.arrMaximum[nAxis] * .5 - stNode.arrMinimum[nAxis] * .5;
		arrDelta[nAxis] = stNode.arrMaximum[nAxis] * .5 + stNode.arrMinimum[nAxis] * .5 - stView.arrPosition[nAxis];
	}
	const double dRadius = std::hypot(arrHalf[0], arrHalf[1], arrHalf[2]);
	const double dDepth = arrDelta[0] * stView.arrForward[0] + arrDelta[1] * stView.arrForward[1] + arrDelta[2] * stView.arrForward[2];
	const double dDistance = dDepth - dRadius - stNode.dGeometricErrorBound;
	if (dDistance <= stView.dNearDistance)
	{
		return std::numeric_limits<double>::max();
	}
	// Bound both lateral motion and the denominator change of perspective
	// division over the entire original and approximated bounding spheres.
	const double dRadial = std::hypot(arrDelta[0], arrDelta[1], arrDelta[2]) + dRadius + stNode.dGeometricErrorBound;
	const double dPerspectiveFactor = 1 + dRadial / dDistance;
	if (!std::isfinite(dPerspectiveFactor))
	{
		return std::numeric_limits<double>::max();
	}
	int nErrorExponent = 0;
	int nProjectionExponent = 0;
	int nPerspectiveExponent = 0;
	int nDistanceExponent = 0;
	const double dFraction = std::frexp(stNode.dGeometricErrorBound, &nErrorExponent) *
			std::frexp(stView.dProjectionPixels, &nProjectionExponent) * std::frexp(dPerspectiveFactor, &nPerspectiveExponent) /
			std::frexp(dDistance, &nDistanceExponent);
	const double dError = std::scalbn(dFraction, nErrorExponent + nProjectionExponent + nPerspectiveExponent - nDistanceExponent);
	return std::isfinite(dError) ? dError : std::numeric_limits<double>::max();
}
bool Validate(const std::vector<LodNode> &arrNodes, const std::vector<std::uint32_t> &arrRoots,
			  const std::vector<std::uint8_t> &arrResident, const LodView &stView, std::uint32_t nMaximumSelected,
			  Assets::Diagnostics &out_arrDiagnostics)
{
	if (arrNodes.empty() || arrNodes.size() > MAX_METADATA_ITEMS || arrResident.empty() || arrResident.size() > MAX_METADATA_ITEMS ||
		arrRoots.empty() || arrRoots.size() > nMaximumSelected || nMaximumSelected > MAX_METADATA_ITEMS)
	{
		return Fail(out_arrDiagnostics, "Invalid hierarchy, page count or selection capacity.");
	}
	for (double dValue : stView.arrPosition)
	{
		if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
		{
			return Fail(out_arrDiagnostics, "Camera position exceeds finite GPU coordinates.");
		}
	}
	if (!std::isfinite(stView.dProjectionPixels) || stView.dProjectionPixels <= 0 || !std::isfinite(stView.dNearDistance) || stView.dNearDistance <= 0 ||
		!std::isfinite(stView.dMaximumErrorPixels) || stView.dMaximumErrorPixels <= 0)
	{
		return Fail(out_arrDiagnostics, "Projection, near distance and pixel error must be finite and positive.");
	}
	for (std::uint8_t nResident : arrResident)
	{
		if (nResident > 1)
		{
			return Fail(out_arrDiagnostics, "Residency snapshot is not binary.");
		}
	}
	std::vector<std::uint8_t> arrParents(arrNodes.size(), 0);
	for (const LodNode &stNode : arrNodes)
	{
		if (stNode.nPage >= arrResident.size() || !std::isfinite(stNode.dGeometricErrorBound) || stNode.dGeometricErrorBound < 0 ||
			stNode.nFirstChild > arrNodes.size() || stNode.nChildCount > arrNodes.size() - stNode.nFirstChild)
		{
			return Fail(out_arrDiagnostics, "Node page, error or child range is invalid.");
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			if (!std::isfinite(stNode.arrMinimum[nAxis]) || !std::isfinite(stNode.arrMaximum[nAxis]) ||
				stNode.arrMinimum[nAxis] > stNode.arrMaximum[nAxis] || std::abs(stNode.arrMinimum[nAxis]) > std::numeric_limits<float>::max() ||
				std::abs(stNode.arrMaximum[nAxis]) > std::numeric_limits<float>::max())
			{
				return Fail(out_arrDiagnostics, "Node bounds must be ordered finite GPU coordinates.");
			}
		}
		for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
		{
			const LodNode &stChild = arrNodes[nChild];
			if (arrParents[nChild] != 0 || stNode.dGeometricErrorBound < stChild.dGeometricErrorBound)
			{
				return Fail(out_arrDiagnostics, "Hierarchy needs unique parents and nondecreasing ancestor error bounds.");
			}
			arrParents[nChild] = 1;
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				if (stNode.arrMinimum[nAxis] > stChild.arrMinimum[nAxis] || stNode.arrMaximum[nAxis] < stChild.arrMaximum[nAxis])
				{
					return Fail(out_arrDiagnostics, "Ancestor bounds must include every child.");
				}
			}
		}
	}
	std::vector<std::uint32_t> arrQueue;
	arrQueue.reserve(arrNodes.size());
	for (std::uint32_t nRoot : arrRoots)
	{
		if (nRoot >= arrNodes.size() || arrParents[nRoot] != 0 || arrResident[arrNodes[nRoot].nPage] == 0)
		{
			return Fail(out_arrDiagnostics, "Every unique root must be parentless and resident.");
		}
		arrParents[nRoot] = 1;
		arrQueue.push_back(nRoot);
	}
	for (std::size_t nIndex = 0; nIndex < arrQueue.size(); ++nIndex)
	{
		const LodNode &stNode = arrNodes[arrQueue[nIndex]];
		for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
		{
			arrQueue.push_back(nChild);
		}
	}
	return arrQueue.size() == arrNodes.size() || Fail(out_arrDiagnostics, "Hierarchy must be an acyclic complete forest.");
}
bool PreviousRefinement(const std::vector<LodNode> &arrNodes, const std::vector<std::uint32_t> &arrRoots,
						const std::vector<std::uint32_t> &arrPrevious, std::vector<std::uint8_t> &out_arrRefined)
{
	out_arrRefined.assign(arrNodes.size(), 0);
	if (arrPrevious.empty())
	{
		return true;
	}
	std::vector<std::uint8_t> arrSelected(arrNodes.size(), 0);
	for (std::uint32_t nNode : arrPrevious)
	{
		if (nNode >= arrNodes.size() || arrSelected[nNode] != 0)
		{
			return false;
		}
		arrSelected[nNode] = 1;
	}
	std::vector<std::uint32_t> arrOrder = arrRoots;
	std::vector<std::uint8_t> arrCovered(arrNodes.size(), 0);
	for (std::size_t nIndex = 0; nIndex < arrOrder.size(); ++nIndex)
	{
		const std::uint32_t nNode = arrOrder[nIndex];
		if (arrCovered[nNode] != 0 && arrSelected[nNode] != 0)
		{
			return false;
		}
		arrCovered[nNode] |= arrSelected[nNode];
		const LodNode &stNode = arrNodes[nNode];
		if (stNode.nChildCount == 0 && arrCovered[nNode] == 0)
		{
			return false;
		}
		for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
		{
			arrCovered[nChild] = arrCovered[nNode];
			arrOrder.push_back(nChild);
		}
	}
	std::vector<std::uint8_t> arrDescendant = arrSelected;
	for (std::size_t nIndex = arrOrder.size(); nIndex > 0; --nIndex)
	{
		const std::uint32_t nNode = arrOrder[nIndex - 1];
		const LodNode &stNode = arrNodes[nNode];
		for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
		{
			arrDescendant[nNode] |= arrDescendant[nChild];
		}
		out_arrRefined[nNode] = arrDescendant[nNode] != 0 && arrSelected[nNode] == 0 ? 1 : 0;
	}
	return true;
}
} //namespace
bool SelectLodCutWithHistory(const std::vector<LodNode> &arrNodes, const std::vector<std::uint32_t> &arrRoots,
							 const std::vector<std::uint8_t> &arrResident, const LodView &stView, std::uint32_t nMaximumSelected,
							 const std::vector<std::uint32_t> &arrPrevious, double dHysteresis,
							 LodSelection &out_stSelection, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!Validate(arrNodes, arrRoots, arrResident, stView, nMaximumSelected, out_arrDiagnostics))
	{
		return false;
	}
	std::vector<std::uint8_t> arrPreviousRefined;
	if (!std::isfinite(dHysteresis) || dHysteresis < 0 || dHysteresis >= 1 ||
		!PreviousRefinement(arrNodes, arrRoots, arrPrevious, arrPreviousRefined))
	{
		return Fail(out_arrDiagnostics, "Invalid committed previous cut or hysteresis fraction.");
	}
	LodView stNormalizedView = stView;
	double dMaximumForward = 0;
	for (double dValue : stNormalizedView.arrForward)
	{
		if (!std::isfinite(dValue))
		{
			return Fail(out_arrDiagnostics, "Camera forward must be finite and nonzero.");
		}
		dMaximumForward = std::max(dMaximumForward, std::abs(dValue));
	}
	if (dMaximumForward == 0)
	{
		return Fail(out_arrDiagnostics, "Camera forward must be finite and nonzero.");
	}
	for (double &dValue : stNormalizedView.arrForward)
	{
		dValue /= dMaximumForward;
	}
	const double dForwardLength = std::hypot(stNormalizedView.arrForward[0], stNormalizedView.arrForward[1], stNormalizedView.arrForward[2]);
	for (double &dValue : stNormalizedView.arrForward)
	{
		dValue /= dForwardLength;
	}
	LodSelection stCandidate;
	std::vector<std::uint8_t> arrSelected(arrNodes.size(), 0);
	std::vector<std::uint8_t> arrRequested(arrResident.size(), 0);
	std::priority_queue<Choice, std::vector<Choice>, LowerPriority> stQueue;
	for (std::uint32_t nRoot : arrRoots)
	{
		arrSelected[nRoot] = 1;
		stQueue.push({ ProjectedError(arrNodes[nRoot], stNormalizedView), nRoot });
	}
	std::uint32_t nSelected = static_cast<std::uint32_t>(arrRoots.size());
	while (!stQueue.empty())
	{
		const Choice stChoice = stQueue.top();
		stQueue.pop();
		const LodNode &stNode = arrNodes[stChoice.nNode];
		const double dFactor = arrPrevious.empty() ? 1 : arrPreviousRefined[stChoice.nNode] != 0 ? 1 - dHysteresis
																								 : 1 + dHysteresis;
		const double dThreshold = stView.dMaximumErrorPixels <= std::numeric_limits<double>::max() / dFactor ? stView.dMaximumErrorPixels * dFactor : std::numeric_limits<double>::max();
		if (stChoice.dError <= dThreshold || stNode.nChildCount == 0)
		{
			continue;
		}
		bool bResident = true;
		for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
		{
			const std::uint32_t nPage = arrNodes[nChild].nPage;
			if (arrResident[nPage] == 0)
			{
				arrRequested[nPage] = 1;
				bResident = false;
			}
		}
		if (!bResident)
		{
			stCandidate.bResidencyLimited = true;
			continue;
		}
		if (stNode.nChildCount - 1 > nMaximumSelected - nSelected)
		{
			stCandidate.bCapacityLimited = true;
			continue;
		}
		arrSelected[stChoice.nNode] = 0;
		nSelected += stNode.nChildCount - 1;
		for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
		{
			arrSelected[nChild] = 1;
			stQueue.push({ ProjectedError(arrNodes[nChild], stNormalizedView), nChild });
		}
	}
	for (std::uint32_t nNode = 0; nNode < arrNodes.size(); ++nNode)
	{
		if (arrSelected[nNode] != 0)
		{
			stCandidate.arrNodes.push_back(nNode);
			stCandidate.dMaximumSelectedErrorPixels = std::max(stCandidate.dMaximumSelectedErrorPixels, ProjectedError(arrNodes[nNode], stNormalizedView));
		}
	}
	for (std::uint32_t nPage = 0; nPage < arrRequested.size(); ++nPage)
	{
		if (arrRequested[nPage] != 0)
		{
			stCandidate.arrRequestedPages.push_back(nPage);
		}
	}
	out_stSelection = std::move(stCandidate);
	return true;
}
bool SelectLodCut(const std::vector<LodNode> &arrNodes, const std::vector<std::uint32_t> &arrRoots,
				  const std::vector<std::uint8_t> &arrResident, const LodView &stView, std::uint32_t nMaximumSelected,
				  LodSelection &out_stSelection, Assets::Diagnostics &out_arrDiagnostics)
{
	return SelectLodCutWithHistory(arrNodes, arrRoots, arrResident, stView, nMaximumSelected, {}, 0, out_stSelection, out_arrDiagnostics);
}
} //namespace EngineNext::Rendering
