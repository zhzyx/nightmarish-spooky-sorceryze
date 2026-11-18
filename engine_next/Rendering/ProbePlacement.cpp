/**************************************************************************/
/*  ProbePlacement.cpp                                                    */
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

#include "engine_next/include/EngineNext/Rendering/ProbePlacement.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
namespace Shared
{
struct Float3
{
	float x;
	float y;
	float z;
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
	Float3() : x(0), y(0), z(0)
	{
	}
};
Float3 operator+(Float3 stA, Float3 stB)
{
	return { stA.x + stB.x, stA.y + stB.y, stA.z + stB.z };
}
Float3 operator-(Float3 stA, Float3 stB)
{
	return { stA.x - stB.x, stA.y - stB.y, stA.z - stB.z };
}
Float3 operator*(Float3 stA, float fB)
{
	return { stA.x * fB, stA.y * fB, stA.z * fB };
}
float dot(Float3 stA, Float3 stB)
{
	return stA.x * stB.x + stA.y * stB.y + stA.z * stB.z;
}
float abs(float fValue)
{
	return std::abs(fValue);
}
float max(float fA, float fB)
{
	return (std::max)(fA, fB);
}
float sqrt(float fValue)
{
	return std::sqrt(fValue);
}
float sin(float fValue)
{
	return std::sin(fValue);
}
float cos(float fValue)
{
	return std::cos(fValue);
}
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
using float3 = Float3;
using uint = std::uint32_t;
#include "engine_next/Rendering/Shaders/ProbePlacementMath.hlsli"
} // namespace Shared
Shared::Float3 Vector(const std::array<float, 3> &arrValue)
{
	return { arrValue[0], arrValue[1], arrValue[2] };
}
bool Unit(const std::array<float, 3> &arrValue)
{
	const Shared::Float3 stValue = Vector(arrValue);
	return Shared::RelocationFinite(stValue) && std::abs(Shared::dot(stValue, stValue) - 1) <= 0.0001F;
}
} // namespace

bool ValidateProbeRelocationSettings(const ProbeRelocationSettings &stSettings)
{
	return std::isnormal(stSettings.fMinimumClearance) && stSettings.fMinimumClearance > 0 &&
			std::isnormal(stSettings.fMaximumOffsetFraction) && stSettings.fMaximumOffsetFraction > 0 && stSettings.fMaximumOffsetFraction < 0.5F &&
			std::isfinite(stSettings.fBackfaceThreshold) && stSettings.fBackfaceThreshold >= 0 && stSettings.fBackfaceThreshold < 1 &&
			stSettings.nMinimumRays >= 6 && stSettings.nMinimumRays <= 1024 &&
			stSettings.nRequiredStableUpdates > 0 && stSettings.nRequiredStableUpdates <= 64;
}

bool BuildProbeGeometryChangeBounds(const std::vector<GiGeometryChange> &arrChanges, std::uint32_t nDrawCount, WorldBounds &out_stBounds)
{
	if (arrChanges.empty() || arrChanges.size() > nDrawCount)
	{
		return false;
	}
	WorldBounds stResult;
	stResult.arrMinimum.fill(std::numeric_limits<double>::infinity());
	stResult.arrMaximum.fill(-std::numeric_limits<double>::infinity());
	std::vector<std::uint32_t> arrDraws;
	arrDraws.reserve(arrChanges.size());
	for (const GiGeometryChange &stChange : arrChanges)
	{
		if (stChange.nDraw >= nDrawCount)
		{
			return false;
		}
		arrDraws.push_back(stChange.nDraw);
		for (const WorldBounds *pBounds : { &stChange.stPreviousWorldBounds, &stChange.stCurrentWorldBounds })
		{
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				if (!std::isfinite(pBounds->arrMinimum[nAxis]) || !std::isfinite(pBounds->arrMaximum[nAxis]) ||
					pBounds->arrMinimum[nAxis] > pBounds->arrMaximum[nAxis])
				{
					return false;
				}
				stResult.arrMinimum[nAxis] = std::min(stResult.arrMinimum[nAxis], pBounds->arrMinimum[nAxis]);
				stResult.arrMaximum[nAxis] = std::max(stResult.arrMaximum[nAxis], pBounds->arrMaximum[nAxis]);
			}
		}
	}
	std::sort(arrDraws.begin(), arrDraws.end());
	if (std::adjacent_find(arrDraws.begin(), arrDraws.end()) != arrDraws.end())
	{
		return false;
	}
	out_stBounds = stResult;
	return true;
}

bool TransformProbeGeometryBounds(const WorldBounds &stLocal, const std::array<double, 16> &arrWorld, WorldBounds &out_stBounds)
{
	std::array<double, 16> arrGpuWorld;
	std::size_t nElement = 0;
	for (double dValue : arrWorld)
	{
		if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
		{
			return false;
		}
		arrGpuWorld[nElement++] = static_cast<float>(dValue);
	}
	if (arrWorld[3] != 0 || arrWorld[7] != 0 || arrWorld[11] != 0 || arrWorld[15] != 1)
	{
		return false;
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!std::isfinite(stLocal.arrMinimum[nAxis]) || !std::isfinite(stLocal.arrMaximum[nAxis]) ||
			stLocal.arrMinimum[nAxis] > stLocal.arrMaximum[nAxis])
		{
			return false;
		}
	}
	WorldBounds stResult;
	stResult.arrMinimum.fill(std::numeric_limits<double>::infinity());
	stResult.arrMaximum.fill(-std::numeric_limits<double>::infinity());
	for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		const std::array<double, 3> arrPoint{
			(nCorner & 1) != 0 ? stLocal.arrMaximum[0] : stLocal.arrMinimum[0],
			(nCorner & 2) != 0 ? stLocal.arrMaximum[1] : stLocal.arrMinimum[1],
			(nCorner & 4) != 0 ? stLocal.arrMaximum[2] : stLocal.arrMinimum[2]
		};
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			double dLower = arrGpuWorld[12 + nAxis];
			double dUpper = dLower;
			double dMagnitude = std::abs(dLower);
			for (std::size_t nTerm = 0; nTerm < 3; ++nTerm)
			{
				const double dProduct = arrGpuWorld[nTerm * 4 + nAxis] * arrPoint[nTerm];
				dMagnitude += std::abs(dProduct);
				dLower = std::nextafter(dLower + std::nextafter(dProduct, -std::numeric_limits<double>::infinity()), -std::numeric_limits<double>::infinity());
				dUpper = std::nextafter(dUpper + std::nextafter(dProduct, std::numeric_limits<double>::infinity()), std::numeric_limits<double>::infinity());
			}
			// Eight epsilons bound the three products and additions even without
			// fused operations. Absolute terms retain the bound under cancellation.
			const double dRoundoff = dMagnitude * (8 * std::numeric_limits<float>::epsilon());
			dLower = std::nextafter(dLower - dRoundoff, -std::numeric_limits<double>::infinity());
			dUpper = std::nextafter(dUpper + dRoundoff, std::numeric_limits<double>::infinity());
			if (!std::isfinite(dLower) || !std::isfinite(dUpper))
			{
				return false;
			}
			stResult.arrMinimum[nAxis] = std::min(stResult.arrMinimum[nAxis], dLower);
			stResult.arrMaximum[nAxis] = std::max(stResult.arrMaximum[nAxis], dUpper);
		}
	}
	out_stBounds = stResult;
	return true;
}

bool EvaluateProbeRelocation(const ProbeRelocationSettings &stSettings, const std::array<float, 3> &arrSpacing,
							 const ProbePlacement &stPrevious, const std::vector<ProbeCollisionRay> &arrCollisionRays, std::uint32_t nSceneRevision,
							 ProbePlacementCandidate &out_stCandidate, float fTraceDistance)
{
	if (!ValidateProbeRelocationSettings(stSettings) || !std::isnormal(fTraceDistance) || fTraceDistance < stSettings.fMinimumClearance ||
		static_cast<double>(fTraceDistance) * fTraceDistance > std::numeric_limits<float>::max() ||
		arrCollisionRays.size() < stSettings.nMinimumRays || arrCollisionRays.size() > 1030 || stPrevious.nStableUpdates > stSettings.nRequiredStableUpdates || static_cast<std::uint32_t>(stPrevious.eClassification) > 2)
	{
		return false;
	}
	double dSquaredOffset = 0;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!std::isnormal(arrSpacing[nAxis]) || arrSpacing[nAxis] <= 0 || !std::isfinite(stPrevious.arrOffset[nAxis]))
		{
			return false;
		}
		const double dRatio = static_cast<double>(stPrevious.arrOffset[nAxis]) / arrSpacing[nAxis];
		dSquaredOffset += dRatio * dRatio;
	}
	if (dSquaredOffset > static_cast<double>(stSettings.fMaximumOffsetFraction) * stSettings.fMaximumOffsetFraction * 1.00001)
	{
		return false;
	}
	Shared::RelocationSummary stSummary = Shared::RelocationBegin(fTraceDistance);
	for (const ProbeCollisionRay &stRay : arrCollisionRays)
	{
		const bool bProximityMiss = stRay.eKind == ProbeHitKind::ProximityMiss;
		if (!Unit(stRay.arrDirection) || !std::isfinite(stRay.fDistance) || stRay.fDistance < 0 || stRay.fDistance > fTraceDistance || static_cast<std::uint32_t>(stRay.eKind) > 5 || (stRay.eKind != ProbeHitKind::Miss && !bProximityMiss && !Unit(stRay.arrNormal)))
		{
			return false;
		}
		const float fFacing = Shared::dot(Vector(stRay.arrDirection), Vector(stRay.arrNormal));
		if (((stRay.eKind == ProbeHitKind::Front || stRay.eKind == ProbeHitKind::FrontProximity) && fFacing >= 0) || ((stRay.eKind == ProbeHitKind::Back || stRay.eKind == ProbeHitKind::BackProximity) && fFacing <= 0))
		{
			return false;
		}
		stSummary = Shared::RelocationObserve(stSummary, Vector(stRay.arrDirection), stRay.fDistance, Vector(stRay.arrNormal), static_cast<std::uint32_t>(stRay.eKind));
	}
	const Shared::RelocationParameters stParameters{ stSettings.fMinimumClearance, stSettings.fMaximumOffsetFraction, stSettings.fBackfaceThreshold, stSettings.nMinimumRays, stSettings.nRequiredStableUpdates };
	const Shared::RelocationState stState{ Vector(stPrevious.arrOffset), stPrevious.fClearance, static_cast<std::uint32_t>(stPrevious.eClassification), stPrevious.nSceneRevision, stPrevious.nStableUpdates, stPrevious.nOffsetRevision };
	const Shared::RelocationDecision stDecision = Shared::RelocationEvaluate(stParameters, Vector(arrSpacing), stState, stSummary, nSceneRevision);
	ProbePlacementCandidate stCandidate;
	stCandidate.stPlacement = { { stDecision.State.Offset.x, stDecision.State.Offset.y, stDecision.State.Offset.z }, stDecision.State.Clearance, static_cast<ProbeClassification>(stDecision.State.Classification), stDecision.State.SceneRevision, stDecision.State.StableUpdates, stDecision.State.OffsetRevision };
	stCandidate.bMoved = stDecision.Moved != 0;
	stCandidate.bResetHistory = stDecision.ResetHistory != 0;
	out_stCandidate = stCandidate;
	return true;
}

bool CommitProbeRelocation(const ProbePlacementCandidate &stCandidate, std::uint32_t nCurrentSceneRevision, ProbePlacement &out_stPlacement)
{
	if (stCandidate.stPlacement.nSceneRevision != nCurrentSceneRevision || !std::isfinite(stCandidate.stPlacement.fClearance) || stCandidate.stPlacement.fClearance < 0 || static_cast<std::uint32_t>(stCandidate.stPlacement.eClassification) > 2)
	{
		return false;
	}
	for (float fOffset : stCandidate.stPlacement.arrOffset)
	{
		if (!std::isfinite(fOffset))
		{
			return false;
		}
	}
	out_stPlacement = stCandidate.stPlacement;
	return true;
}

bool BuildProbeRelocationDirections(std::uint32_t nCount, std::vector<std::array<float, 3>> &out_arrDirections)
{
	if (nCount < 6 || nCount > 1024)
	{
		return false;
	}
	std::vector<std::array<float, 3>> arrDirections(nCount);
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		const Shared::Float3 stDirection = Shared::RelocationDirection(nIndex, nCount);
		arrDirections[nIndex] = { stDirection.x, stDirection.y, stDirection.z };
	}
	out_arrDirections = std::move(arrDirections);
	return true;
}

bool ProbeTouchesChangedGeometry(const ProbeRelocationSettings &stSettings, const std::array<float, 3> &arrAnchor,
								 const std::array<float, 3> &arrSpacing, const WorldBounds &stChangedBounds, bool &out_bAffected)
{
	if (!std::isnormal(stSettings.fMinimumClearance) || stSettings.fMinimumClearance <= 0 || !std::isnormal(stSettings.fMaximumOffsetFraction) || stSettings.fMaximumOffsetFraction <= 0 || stSettings.fMaximumOffsetFraction >= 0.5F)
	{
		return false;
	}
	bool bAffected = true;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!std::isfinite(arrAnchor[nAxis]) || !std::isnormal(arrSpacing[nAxis]) || arrSpacing[nAxis] <= 0 || !std::isfinite(stChangedBounds.arrMinimum[nAxis]) || !std::isfinite(stChangedBounds.arrMaximum[nAxis]) || stChangedBounds.arrMinimum[nAxis] > stChangedBounds.arrMaximum[nAxis])
		{
			return false;
		}
		const double dAnchor = arrAnchor[nAxis];
		// Cover reconstruction of spacing from its GPU reciprocal and the final
		// binary32 addition of offset to a large world-space anchor.
		const double dRoundoff = (std::abs(dAnchor) + arrSpacing[nAxis]) * (4 * std::numeric_limits<float>::epsilon());
		const double dExpansion = static_cast<double>(arrSpacing[nAxis]) * stSettings.fMaximumOffsetFraction + stSettings.fMinimumClearance + dRoundoff;
		bAffected = bAffected && dAnchor + dExpansion >= stChangedBounds.arrMinimum[nAxis] && dAnchor - dExpansion <= stChangedBounds.arrMaximum[nAxis];
	}
	out_bAffected = bAffected;
	return true;
}
} // namespace EngineNext::Rendering
