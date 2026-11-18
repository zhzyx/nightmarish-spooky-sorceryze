/**************************************************************************/
/*  GeometryLod.cpp                                                       */
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

#include "engine_next/Rendering/Cook/MeshCluster.h"
#include "engine_next/thirdparty/meshoptimizer/meshoptimizer.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
using Position = std::array<double, 3>;
using Triangle = std::array<Position, 3>;
constexpr std::uint64_t MAXIMUM_INPUT_BYTES = 64ULL * 1024 * 1024;

struct EdgeUse
{
	std::uint32_t nCount = 0;
	std::int32_t nOrientation = 0;
};

struct VerificationCell
{
	Triangle arrTriangle;
	std::uint32_t nDepth = 0;
};

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "lod_cook", "$", pMessage);
	return false;
}

Position Add(const Position &arrA, const Position &arrB)
{
	return { arrA[0] + arrB[0], arrA[1] + arrB[1], arrA[2] + arrB[2] };
}

Position Subtract(const Position &arrA, const Position &arrB)
{
	return { arrA[0] - arrB[0], arrA[1] - arrB[1], arrA[2] - arrB[2] };
}

Position Scale(const Position &arrA, double dScale)
{
	return { arrA[0] * dScale, arrA[1] * dScale, arrA[2] * dScale };
}

double Dot(const Position &arrA, const Position &arrB)
{
	return arrA[0] * arrB[0] + arrA[1] * arrB[1] + arrA[2] * arrB[2];
}

double Distance(const Position &arrA, const Position &arrB)
{
	const Position arrDelta = Subtract(arrA, arrB);
	return std::hypot(arrDelta[0], arrDelta[1], arrDelta[2]);
}

Position ReadPosition(const MeshPrimitive &stPrimitive, std::uint32_t nIndex)
{
	const std::array<float, 3> &arrPosition = stPrimitive.arrVertices[nIndex].arrPosition;
	return { arrPosition[0], arrPosition[1], arrPosition[2] };
}

Triangle ReadTriangle(const MeshPrimitive &stPrimitive, const std::vector<std::uint32_t> &arrIndices, std::size_t nIndex)
{
	return { ReadPosition(stPrimitive, arrIndices[nIndex]), ReadPosition(stPrimitive, arrIndices[nIndex + 1]), ReadPosition(stPrimitive, arrIndices[nIndex + 2]) };
}

// Return a convex point on the target triangle. It need not be the mathematically
// closest point for the resulting distance to remain an upper bound.
Position TargetPoint(const Position &arrPoint, const Triangle &arrTriangle)
{
	const Position arrAb = Subtract(arrTriangle[1], arrTriangle[0]);
	const Position arrAc = Subtract(arrTriangle[2], arrTriangle[0]);
	const Position arrAp = Subtract(arrPoint, arrTriangle[0]);
	const double d1 = Dot(arrAb, arrAp);
	const double d2 = Dot(arrAc, arrAp);
	if (d1 <= 0 && d2 <= 0)
	{
		return arrTriangle[0];
	}
	const Position arrBp = Subtract(arrPoint, arrTriangle[1]);
	const double d3 = Dot(arrAb, arrBp);
	const double d4 = Dot(arrAc, arrBp);
	if (d3 >= 0 && d4 <= d3)
	{
		return arrTriangle[1];
	}
	const Position arrCp = Subtract(arrPoint, arrTriangle[2]);
	const double d5 = Dot(arrAb, arrCp);
	const double d6 = Dot(arrAc, arrCp);
	if (d6 >= 0 && d5 <= d6)
	{
		return arrTriangle[2];
	}
	const double dVc = d1 * d4 - d3 * d2;
	const double dVb = d5 * d2 - d1 * d6;
	const double dVa = d3 * d6 - d5 * d4;
	double dV = 0;
	double dW = 0;
	if (dVc <= 0 && d1 >= 0 && d3 <= 0 && d1 != d3)
	{
		dV = d1 / (d1 - d3);
	}
	else if (dVb <= 0 && d2 >= 0 && d6 <= 0 && d2 != d6)
	{
		dW = d2 / (d2 - d6);
	}
	else if (dVa <= 0 && d4 >= d3 && d5 >= d6 && (d4 - d3) + (d5 - d6) > 0)
	{
		dW = (d4 - d3) / ((d4 - d3) + (d5 - d6));
		dV = 1 - dW;
	}
	else
	{
		const double dDenominator = dVa + dVb + dVc;
		if (!(dDenominator > 0) || !std::isfinite(dDenominator))
		{
			return arrTriangle[0];
		}
		dV = dVb / dDenominator;
		dW = dVc / dDenominator;
	}
	dV = std::clamp(dV, 0.0, 1.0);
	dW = std::clamp(dW, 0.0, 1.0);
	if (dV + dW > 1)
	{
		const double dSum = dV + dW;
		dV /= dSum;
		dW /= dSum;
	}
	const double dU = (std::max)(0.0, 1 - dV - dW);
	return Add(Add(Scale(arrTriangle[0], dU), Scale(arrTriangle[1], dV)), Scale(arrTriangle[2], dW));
}

// The acceleration structure changes only which valid target points are
// tested. Every returned candidate remains a convex point on a target triangle;
// pruning can therefore enlarge the certified upper bound, never lower it.
// Large public inputs retain the bounded linear query when scratch would exceed
// 64 MiB. Tree construction is balanced and traversal uses at most 64 entries.
class TargetHierarchy
{
public:
	TargetHierarchy(const MeshPrimitive &in_stPrimitive, const std::vector<std::uint32_t> &in_arrIndices) :
			stPrimitive(in_stPrimitive), arrIndices(in_arrIndices)
	{
		const std::size_t nTriangles = arrIndices.size() / 3;
		const std::size_t nMaximumNodes = 2 * ((nTriangles + 3) / 4) + 1;
		if (nTriangles <= 8 || nTriangles > UINT32_MAX || nTriangles > (64ULL * 1024 * 1024) / sizeof(std::uint32_t) ||
			nMaximumNodes > (64ULL * 1024 * 1024 - nTriangles * sizeof(std::uint32_t)) / sizeof(TargetNode))
		{
			return;
		}
		arrOrder.resize(nTriangles);
		for (std::uint32_t nTriangle = 0; nTriangle < nTriangles; ++nTriangle)
		{
			arrOrder[nTriangle] = nTriangle;
		}
		arrNodes.reserve(nMaximumNodes);
		(void)Build(0, static_cast<std::uint32_t>(nTriangles));
	}
	bool Query(const Position &arrPoint, const LodCookSettings &stSettings, std::uint64_t &out_nTests, double &out_dMinimum) const
	{
		const auto fnTest = [this, &arrPoint, &stSettings, &out_nTests, &out_dMinimum](std::size_t nTriangle)
		{
			if (out_nTests >= stSettings.nMaximumDistanceTests)
			{
				return false;
			}
			++out_nTests;
			const Position arrCandidate = TargetPoint(arrPoint, ReadTriangle(stPrimitive, arrIndices, static_cast<std::size_t>(nTriangle) * 3));
			out_dMinimum = (std::min)(out_dMinimum, Distance(arrPoint, arrCandidate));
			return true;
		};
		if (arrNodes.empty())
		{
			for (std::size_t nTriangle = 0; nTriangle < arrIndices.size() / 3; ++nTriangle)
			{
				if (!fnTest(nTriangle))
				{
					return false;
				}
			}
			return true;
		}
		std::array<std::uint32_t, 64> arrStack{};
		std::size_t nPending = 1;
		while (nPending != 0)
		{
			const TargetNode &stNode = arrNodes[arrStack[--nPending]];
			if (BoxDistance(stNode, arrPoint) >= out_dMinimum)
			{
				continue;
			}
			if (stNode.nCount != 0)
			{
				for (std::uint32_t nIndex = stNode.nFirst; nIndex < stNode.nFirst + stNode.nCount; ++nIndex)
				{
					if (!fnTest(arrOrder[nIndex]))
					{
						return false;
					}
				}
			}
			else
			{
				if (nPending + 2 > arrStack.size())
				{
					return false;
				}
				const double dLeft = BoxDistance(arrNodes[stNode.nLeft], arrPoint);
				const double dRight = BoxDistance(arrNodes[stNode.nRight], arrPoint);
				// LIFO traversal visits the nearer child first; ties are deterministic.
				arrStack[nPending++] = dLeft <= dRight ? stNode.nRight : stNode.nLeft;
				arrStack[nPending++] = dLeft <= dRight ? stNode.nLeft : stNode.nRight;
			}
		}
		return true;
	}

private:
	struct TargetNode
	{
		Position arrMinimum{};
		Position arrMaximum{};
		std::uint32_t nFirst = 0;
		std::uint32_t nCount = 0;
		std::uint32_t nLeft = 0;
		std::uint32_t nRight = 0;
	};
	static double BoxDistance(const TargetNode &stNode, const Position &arrPoint)
	{
		Position arrDelta{};
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrDelta[nAxis] = (std::max)({ 0.0, stNode.arrMinimum[nAxis] - arrPoint[nAxis], arrPoint[nAxis] - stNode.arrMaximum[nAxis] });
		}
		return std::hypot(arrDelta[0], arrDelta[1], arrDelta[2]);
	}
	std::uint32_t Build(std::uint32_t nFirst, std::uint32_t nCount)
	{
		const std::uint32_t nNode = static_cast<std::uint32_t>(arrNodes.size());
		TargetNode stNode;
		stNode.arrMinimum.fill(std::numeric_limits<double>::max());
		stNode.arrMaximum.fill(-std::numeric_limits<double>::max());
		for (std::uint32_t nIndex = nFirst; nIndex < nFirst + nCount; ++nIndex)
		{
			const Triangle arrTriangle = ReadTriangle(stPrimitive, arrIndices, static_cast<std::size_t>(arrOrder[nIndex]) * 3);
			for (const Position &arrPoint : arrTriangle)
			{
				for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
				{
					stNode.arrMinimum[nAxis] = (std::min)(stNode.arrMinimum[nAxis], arrPoint[nAxis]);
					stNode.arrMaximum[nAxis] = (std::max)(stNode.arrMaximum[nAxis], arrPoint[nAxis]);
				}
			}
		}
		stNode.nFirst = nFirst;
		stNode.nCount = nCount;
		arrNodes.push_back(stNode);
		if (nCount > 8)
		{
			std::size_t nAxis = 0;
			for (std::size_t nCandidate = 1; nCandidate < 3; ++nCandidate)
			{
				if (stNode.arrMaximum[nCandidate] - stNode.arrMinimum[nCandidate] > stNode.arrMaximum[nAxis] - stNode.arrMinimum[nAxis])
				{
					nAxis = nCandidate;
				}
			}
			const auto fnCenter = [this, nAxis](std::uint32_t nTriangle)
			{
				const Triangle arrTriangle = ReadTriangle(stPrimitive, arrIndices, static_cast<std::size_t>(nTriangle) * 3);
				return (arrTriangle[0][nAxis] + arrTriangle[1][nAxis] + arrTriangle[2][nAxis]) / 3;
			};
			const std::uint32_t nHalf = nCount / 2;
			std::nth_element(arrOrder.begin() + nFirst, arrOrder.begin() + nFirst + nHalf, arrOrder.begin() + nFirst + nCount,
							 [&fnCenter](std::uint32_t nLeft, std::uint32_t nRight)
							 {
								 const double dLeft = fnCenter(nLeft), dRight = fnCenter(nRight);
								 return dLeft < dRight || (dLeft == dRight && nLeft < nRight);
							 });
			const std::uint32_t nLeft = Build(nFirst, nHalf);
			const std::uint32_t nRight = Build(nFirst + nHalf, nCount - nHalf);
			arrNodes[nNode].nCount = 0;
			arrNodes[nNode].nLeft = nLeft;
			arrNodes[nNode].nRight = nRight;
		}
		return nNode;
	}
	const MeshPrimitive &stPrimitive;
	const std::vector<std::uint32_t> &arrIndices;
	std::vector<std::uint32_t> arrOrder;
	std::vector<TargetNode> arrNodes;
};

bool VerifyDirection(const MeshPrimitive &stPrimitive, const std::vector<std::uint32_t> &arrSource,
					 const std::vector<std::uint32_t> &arrTarget, const LodCookSettings &stSettings,
					 double dRoundoff, std::uint64_t &out_nTests, double &out_dBound)
{
	if (out_nTests >= stSettings.nMaximumDistanceTests)
	{
		return false;
	}
	const TargetHierarchy stTargets(stPrimitive, arrTarget);
	std::vector<VerificationCell> arrStack;
	arrStack.reserve(1 + stSettings.nVerificationDepth * 3);
	for (std::size_t nIndex = 0; nIndex < arrSource.size(); nIndex += 3)
	{
		arrStack.push_back({ ReadTriangle(stPrimitive, arrSource, nIndex), 0 });
		while (!arrStack.empty())
		{
			const VerificationCell stCell = arrStack.back();
			arrStack.pop_back();
			const Position arrCenter = Scale(Add(Add(stCell.arrTriangle[0], stCell.arrTriangle[1]), stCell.arrTriangle[2]), 1.0 / 3);
			const double dRadius = (std::max)({ Distance(arrCenter, stCell.arrTriangle[0]), Distance(arrCenter, stCell.arrTriangle[1]), Distance(arrCenter, stCell.arrTriangle[2]) });
			if (dRadius > stSettings.dVerificationCellRadius && stCell.nDepth < stSettings.nVerificationDepth)
			{
				const Position arrAb = Scale(Add(stCell.arrTriangle[0], stCell.arrTriangle[1]), .5);
				const Position arrBc = Scale(Add(stCell.arrTriangle[1], stCell.arrTriangle[2]), .5);
				const Position arrCa = Scale(Add(stCell.arrTriangle[2], stCell.arrTriangle[0]), .5);
				const std::uint32_t nDepth = stCell.nDepth + 1;
				arrStack.push_back({ { stCell.arrTriangle[0], arrAb, arrCa }, nDepth });
				arrStack.push_back({ { arrAb, stCell.arrTriangle[1], arrBc }, nDepth });
				arrStack.push_back({ { arrCa, arrBc, stCell.arrTriangle[2] }, nDepth });
				arrStack.push_back({ { arrAb, arrBc, arrCa }, nDepth });
				continue;
			}
			double dMinimum = std::numeric_limits<double>::max();
			if (!stTargets.Query(arrCenter, stSettings, out_nTests, dMinimum))
			{
				return false;
			}
			out_dBound = (std::max)(out_dBound, dMinimum + dRadius + dRoundoff);
		}
	}
	return true;
}

bool BuildLocks(const MeshPrimitive &stPrimitive, const std::vector<std::uint32_t> &arrIndices,
				std::vector<std::uint8_t> &out_arrLocks)
{
	std::map<std::array<std::uint32_t, 2>, EdgeUse> mapEdges;
	std::map<std::array<float, 3>, std::uint32_t> mapPositions;
	out_arrLocks.assign(stPrimitive.arrVertices.size(), 0);
	for (std::size_t nIndex = 0; nIndex < arrIndices.size(); nIndex += 3)
	{
		const Triangle arrTriangle = ReadTriangle(stPrimitive, arrIndices, nIndex);
		const Position arrAb = Subtract(arrTriangle[1], arrTriangle[0]);
		const Position arrAc = Subtract(arrTriangle[2], arrTriangle[0]);
		const Position arrCross{ arrAb[1] * arrAc[2] - arrAb[2] * arrAc[1], arrAb[2] * arrAc[0] - arrAb[0] * arrAc[2], arrAb[0] * arrAc[1] - arrAb[1] * arrAc[0] };
		if (Dot(arrCross, arrCross) == 0)
		{
			return false;
		}
		for (std::size_t nCorner = 0; nCorner < 3; ++nCorner)
		{
			const std::uint32_t nA = arrIndices[nIndex + nCorner];
			const std::uint32_t nB = arrIndices[nIndex + (nCorner + 1) % 3];
			const std::array<std::uint32_t, 2> arrEdge{ (std::min)(nA, nB), (std::max)(nA, nB) };
			EdgeUse &stEdge = mapEdges[arrEdge];
			++stEdge.nCount;
			stEdge.nOrientation += nA < nB ? 1 : -1;
			const std::array<float, 3> &arrPosition = stPrimitive.arrVertices[nA].arrPosition;
			const std::pair<std::map<std::array<float, 3>, std::uint32_t>::iterator, bool> stInserted = mapPositions.emplace(arrPosition, nA);
			if (!stInserted.second && stInserted.first->second != nA)
			{
				out_arrLocks[nA] = meshopt_SimplifyVertex_Lock;
				out_arrLocks[stInserted.first->second] = meshopt_SimplifyVertex_Lock;
			}
		}
	}
	for (const std::pair<const std::array<std::uint32_t, 2>, EdgeUse> &stEntry : mapEdges)
	{
		if (stEntry.second.nCount > 2 || (stEntry.second.nCount == 2 && stEntry.second.nOrientation != 0))
		{
			return false;
		}
		if (stEntry.second.nCount == 1)
		{
			out_arrLocks[stEntry.first[0]] = meshopt_SimplifyVertex_Lock;
			out_arrLocks[stEntry.first[1]] = meshopt_SimplifyVertex_Lock;
		}
	}
	return true;
}

bool BuildNormalizedInputs(const MeshPrimitive &stPrimitive, std::vector<std::array<float, 3>> &out_arrPositions,
						   std::vector<std::array<float, 9>> &out_arrAttributes)
{
	std::array<double, 3> arrMinimum{ std::numeric_limits<double>::max(), std::numeric_limits<double>::max(), std::numeric_limits<double>::max() };
	std::array<double, 3> arrMaximum{ -std::numeric_limits<double>::max(), -std::numeric_limits<double>::max(), -std::numeric_limits<double>::max() };
	std::array<double, 9> arrAttributeScales{};
	out_arrPositions.resize(stPrimitive.arrVertices.size());
	out_arrAttributes.resize(stPrimitive.arrVertices.size());
	for (std::size_t nVertex = 0; nVertex < stPrimitive.arrVertices.size(); ++nVertex)
	{
		const MeshVertex &stVertex = stPrimitive.arrVertices[nVertex];
		std::array<float, 9> &arrAttributes = out_arrAttributes[nVertex];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			if (!std::isfinite(stVertex.arrPosition[nAxis]))
			{
				return false;
			}
			arrMinimum[nAxis] = (std::min)(arrMinimum[nAxis], static_cast<double>(stVertex.arrPosition[nAxis]));
			arrMaximum[nAxis] = (std::max)(arrMaximum[nAxis], static_cast<double>(stVertex.arrPosition[nAxis]));
			arrAttributes[nAxis] = stVertex.arrNormal[nAxis];
		}
		for (std::size_t nAxis = 0; nAxis < 4; ++nAxis)
		{
			arrAttributes[nAxis + 3] = stVertex.arrTangent[nAxis];
		}
		arrAttributes[7] = stVertex.arrTexcoord[0];
		arrAttributes[8] = stVertex.arrTexcoord[1];
		for (std::size_t nAttribute = 0; nAttribute < 9; ++nAttribute)
		{
			if (!std::isfinite(arrAttributes[nAttribute]))
			{
				return false;
			}
			arrAttributeScales[nAttribute] = (std::max)(arrAttributeScales[nAttribute], std::abs(static_cast<double>(arrAttributes[nAttribute])));
		}
	}
	const Position arrCenter = Scale(Add(arrMinimum, arrMaximum), .5);
	const double dScale = (std::max)({ arrMaximum[0] - arrMinimum[0], arrMaximum[1] - arrMinimum[1], arrMaximum[2] - arrMinimum[2], std::numeric_limits<double>::min() });
	for (std::size_t nVertex = 0; nVertex < stPrimitive.arrVertices.size(); ++nVertex)
	{
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			out_arrPositions[nVertex][nAxis] = static_cast<float>((stPrimitive.arrVertices[nVertex].arrPosition[nAxis] - arrCenter[nAxis]) / dScale);
		}
		for (std::size_t nAttribute = 0; nAttribute < 9; ++nAttribute)
		{
			if (arrAttributeScales[nAttribute] > 0)
			{
				out_arrAttributes[nVertex][nAttribute] = static_cast<float>(out_arrAttributes[nVertex][nAttribute] / arrAttributeScales[nAttribute]);
			}
		}
	}
	return true;
}

bool AppendNode(const MeshPrimitive &stPrimitive, const LodCookSettings &stSettings, std::uint32_t nFirstTriangle,
				std::uint32_t nTriangleCount, std::uint32_t nFirstChild, std::uint32_t nChildCount,
				const std::vector<std::array<float, 3>> &arrPositions, const std::vector<std::array<float, 9>> &arrAttributes,
				CookedLodHierarchy &out_stHierarchy)
{
	if (out_stHierarchy.arrNodes.size() >= stSettings.nMaximumNodes)
	{
		return false;
	}
	const std::size_t nFirstIndex = static_cast<std::size_t>(nFirstTriangle) * 3;
	const std::size_t nIndexCount = static_cast<std::size_t>(nTriangleCount) * 3;
	LodGeometry stGeometry;
	stGeometry.nFirstSourceTriangle = nFirstTriangle;
	stGeometry.nSourceTriangleCount = nTriangleCount;
	stGeometry.arrIndices.assign(stPrimitive.arrIndices.begin() + nFirstIndex, stPrimitive.arrIndices.begin() + nFirstIndex + nIndexCount);
	LodNode stNode;
	stNode.nFirstChild = nFirstChild;
	stNode.nChildCount = nChildCount;
	stNode.nPage = static_cast<std::uint32_t>(out_stHierarchy.arrNodes.size());
	stNode.arrMinimum = ReadPosition(stPrimitive, stGeometry.arrIndices[0]);
	stNode.arrMaximum = stNode.arrMinimum;
	for (std::uint32_t nIndex : stGeometry.arrIndices)
	{
		const Position arrPosition = ReadPosition(stPrimitive, nIndex);
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stNode.arrMinimum[nAxis] = (std::min)(stNode.arrMinimum[nAxis], arrPosition[nAxis]);
			stNode.arrMaximum[nAxis] = (std::max)(stNode.arrMaximum[nAxis], arrPosition[nAxis]);
		}
	}
	if (nChildCount != 0)
	{
		std::vector<std::uint8_t> arrLocks;
		if (!BuildLocks(stPrimitive, stGeometry.arrIndices, arrLocks))
		{
			++out_stHierarchy.nTopologyFallbacks;
		}
		else
		{
			std::vector<std::uint32_t> arrSimplified(nIndexCount);
			const std::array<float, 9> arrWeights{ 1, 1, 1, 1, 1, 1, 1, 1, 1 };
			const std::size_t nTarget = (std::max)(std::size_t(1), static_cast<std::size_t>(nTriangleCount * stSettings.dTargetTriangleRatio)) * 3;
			const std::size_t nResult = meshopt_simplifyWithAttributes(arrSimplified.data(), stGeometry.arrIndices.data(), nIndexCount,
																	   arrPositions.front().data(), arrPositions.size(), sizeof(arrPositions.front()), arrAttributes.front().data(), sizeof(arrAttributes.front()),
																	   arrWeights.data(), arrWeights.size(), arrLocks.data(), nTarget, 1.0F, meshopt_SimplifyLockBorder | meshopt_SimplifySparse, nullptr);
			if (nResult >= 3 && nResult < nIndexCount && nResult % 3 == 0)
			{
				arrSimplified.resize(nResult);
				double dBound = 0;
				if (ComputeLodDeviationBound(stPrimitive, stGeometry.arrIndices, arrSimplified, stSettings, out_stHierarchy.nDistanceTests, dBound))
				{
					stGeometry.arrIndices = std::move(arrSimplified);
					stNode.dGeometricErrorBound = std::nextafter(dBound, std::numeric_limits<double>::infinity());
					++out_stHierarchy.nSimplifiedNodes;
				}
				else
				{
					++out_stHierarchy.nVerificationFallbacks;
				}
			}
		}
		for (std::uint32_t nChild = nFirstChild; nChild < nFirstChild + nChildCount; ++nChild)
		{
			stNode.dGeometricErrorBound = (std::max)(stNode.dGeometricErrorBound, out_stHierarchy.arrNodes[nChild].dGeometricErrorBound);
		}
	}
	if (stGeometry.arrIndices.size() > stSettings.nMaximumOutputIndices - out_stHierarchy.nOutputIndices)
	{
		return false;
	}
	out_stHierarchy.nOutputIndices += stGeometry.arrIndices.size();
	out_stHierarchy.arrNodes.push_back(stNode);
	out_stHierarchy.arrGeometry.push_back(std::move(stGeometry));
	return true;
}
} // namespace

bool ComputeLodDeviationBound(const MeshPrimitive &stPrimitive,
							  const std::vector<std::uint32_t> &arrSource, const std::vector<std::uint32_t> &arrTarget,
							  const LodCookSettings &stSettings, std::uint64_t &out_nDistanceTests, double &out_dBound)
{
	if (arrSource.empty() || arrTarget.empty() || arrSource.size() % 3 != 0 || arrTarget.size() % 3 != 0 ||
		stSettings.nVerificationDepth > 8 || !std::isfinite(stSettings.dVerificationCellRadius) || stSettings.dVerificationCellRadius <= 0 ||
		out_nDistanceTests > stSettings.nMaximumDistanceTests)
	{
		return false;
	}
	double dMagnitude = 1;
	for (const std::vector<std::uint32_t> *pIndices : { &arrSource, &arrTarget })
	{
		for (std::uint32_t nIndex : *pIndices)
		{
			if (nIndex >= stPrimitive.arrVertices.size())
			{
				return false;
			}
			for (float fValue : stPrimitive.arrVertices[nIndex].arrPosition)
			{
				if (!std::isfinite(fValue))
				{
					return false;
				}
				dMagnitude = (std::max)(dMagnitude, std::abs(static_cast<double>(fValue)));
			}
		}
	}
	if (arrSource == arrTarget)
	{
		out_dBound = 0;
		return true;
	}
	const double dRoundoff = 128 * (stSettings.nVerificationDepth + 1) * std::numeric_limits<double>::epsilon() * dMagnitude;
	double dBound = 0;
	if (!VerifyDirection(stPrimitive, arrSource, arrTarget, stSettings, dRoundoff, out_nDistanceTests, dBound) ||
		!VerifyDirection(stPrimitive, arrTarget, arrSource, stSettings, dRoundoff, out_nDistanceTests, dBound))
	{
		return false;
	}
	out_dBound = std::nextafter(dBound, std::numeric_limits<double>::infinity());
	return true;
}

bool CookLodHierarchy(const MeshPrimitive &stPrimitive, const LodCookSettings &stSettings,
					  CookedLodHierarchy &out_stHierarchy, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stPrimitive.nMaterial < 0 || stPrimitive.arrVertices.size() > MAXIMUM_INPUT_BYTES / sizeof(MeshVertex) ||
		stPrimitive.arrIndices.size() > (MAXIMUM_INPUT_BYTES - stPrimitive.arrVertices.size() * sizeof(MeshVertex)) / sizeof(std::uint32_t) || stSettings.nGroupSize < 2 || stSettings.nGroupSize > 8 ||
		stSettings.nMaximumNodes == 0 || stSettings.nMaximumNodes > 1048576 || stSettings.nVerificationDepth > 8 ||
		stSettings.nMaximumOutputIndices == 0 || stSettings.nMaximumOutputIndices > 64000000 ||
		!std::isfinite(stSettings.dTargetTriangleRatio) || stSettings.dTargetTriangleRatio < .05 || stSettings.dTargetTriangleRatio > 1 ||
		!std::isfinite(stSettings.dVerificationCellRadius) || stSettings.dVerificationCellRadius <= 0)
	{
		return Fail(out_arrDiagnostics, "Invalid primitive or hierarchy Cook resource limits.");
	}
	std::vector<MeshCluster> arrClusters;
	if (!CookMeshClusters(stPrimitive, arrClusters, out_arrDiagnostics))
	{
		return false;
	}
	std::vector<std::array<float, 3>> arrPositions;
	std::vector<std::array<float, 9>> arrAttributes;
	if (!BuildNormalizedInputs(stPrimitive, arrPositions, arrAttributes))
	{
		return Fail(out_arrDiagnostics, "Every source vertex attribute must be finite.");
	}
	CookedLodHierarchy stCandidate;
	std::vector<std::uint32_t> arrLevel;
	std::uint32_t nFirstTriangle = 0;
	for (const MeshCluster &stCluster : arrClusters)
	{
		const std::uint32_t nTriangleCount = static_cast<std::uint32_t>(stCluster.arrTriangleIndices.size() / 3);
		arrLevel.push_back(static_cast<std::uint32_t>(stCandidate.arrNodes.size()));
		if (!AppendNode(stPrimitive, stSettings, nFirstTriangle, nTriangleCount, 0, 0, arrPositions, arrAttributes, stCandidate))
		{
			return Fail(out_arrDiagnostics, "Hierarchy exceeds the configured node or index budget.");
		}
		nFirstTriangle += nTriangleCount;
	}
	while (arrLevel.size() > 1)
	{
		std::vector<std::uint32_t> arrNext;
		for (std::size_t nFirst = 0; nFirst < arrLevel.size(); nFirst += stSettings.nGroupSize)
		{
			const std::uint32_t nChildren = static_cast<std::uint32_t>((std::min)(static_cast<std::size_t>(stSettings.nGroupSize), arrLevel.size() - nFirst));
			const std::uint32_t nFirstChild = arrLevel[nFirst];
			const std::uint32_t nSourceFirst = stCandidate.arrGeometry[nFirstChild].nFirstSourceTriangle;
			std::uint32_t nSourceCount = 0;
			for (std::uint32_t nChild = nFirstChild; nChild < nFirstChild + nChildren; ++nChild)
			{
				nSourceCount += stCandidate.arrGeometry[nChild].nSourceTriangleCount;
			}
			arrNext.push_back(static_cast<std::uint32_t>(stCandidate.arrNodes.size()));
			if (!AppendNode(stPrimitive, stSettings, nSourceFirst, nSourceCount, nFirstChild, nChildren, arrPositions, arrAttributes, stCandidate))
			{
				return Fail(out_arrDiagnostics, "Hierarchy exceeds the configured node or index budget.");
			}
		}
		arrLevel = std::move(arrNext);
	}
	stCandidate.arrRoots = std::move(arrLevel);
	out_stHierarchy = std::move(stCandidate);
	return true;
}
} // namespace EngineNext::Rendering
