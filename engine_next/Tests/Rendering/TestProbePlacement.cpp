/**************************************************************************/
/*  TestProbePlacement.cpp                                                */
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
#include "engine_next/Tests/TestFramework.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace
{
namespace Placement = EngineNext::Rendering;
using Vector = std::array<double, 3>;
using Triangle = std::array<Vector, 3>;

Vector Subtract(const Vector &arrA, const Vector &arrB)
{
	return { arrA[0] - arrB[0], arrA[1] - arrB[1], arrA[2] - arrB[2] };
}
Vector Cross(const Vector &arrA, const Vector &arrB)
{
	return { arrA[1] * arrB[2] - arrA[2] * arrB[1], arrA[2] * arrB[0] - arrA[0] * arrB[2], arrA[0] * arrB[1] - arrA[1] * arrB[0] };
}
double Dot(const Vector &arrA, const Vector &arrB)
{
	return arrA[0] * arrB[0] + arrA[1] * arrB[1] + arrA[2] * arrB[2];
}
void Quad(std::vector<Triangle> &out_arrTriangles, Vector arrA, Vector arrB, Vector arrC, Vector arrD)
{
	out_arrTriangles.push_back({ arrA, arrB, arrC });
	out_arrTriangles.push_back({ arrA, arrC, arrD });
}
std::vector<Triangle> Box(double dRadius)
{
	const double dLo = -dRadius;
	const double dHi = dRadius;
	std::vector<Triangle> arrTriangles;
	Quad(arrTriangles, { dLo, dLo, dHi }, { dHi, dLo, dHi }, { dHi, dHi, dHi }, { dLo, dHi, dHi });
	Quad(arrTriangles, { dHi, dLo, dLo }, { dLo, dLo, dLo }, { dLo, dHi, dLo }, { dHi, dHi, dLo });
	Quad(arrTriangles, { dLo, dLo, dLo }, { dLo, dLo, dHi }, { dLo, dHi, dHi }, { dLo, dHi, dLo });
	Quad(arrTriangles, { dHi, dLo, dHi }, { dHi, dLo, dLo }, { dHi, dHi, dLo }, { dHi, dHi, dHi });
	Quad(arrTriangles, { dLo, dHi, dLo }, { dLo, dHi, dHi }, { dHi, dHi, dHi }, { dHi, dHi, dLo });
	Quad(arrTriangles, { dLo, dLo, dHi }, { dLo, dLo, dLo }, { dHi, dLo, dLo }, { dHi, dLo, dHi });
	return arrTriangles;
}
std::vector<Placement::ProbeCollisionRay> Trace(const std::vector<Triangle> &arrTriangles, const Vector &arrOrigin)
{
	std::vector<std::array<float, 3>> arrDirections;
	ENGINE_NEXT_CHECK(Placement::BuildProbeRelocationDirections(64, arrDirections));
	std::vector<Placement::ProbeCollisionRay> arrCollisionRays;
	for (const std::array<float, 3> &arrInputDirection : arrDirections)
	{
		const Vector arrDirection{ arrInputDirection[0], arrInputDirection[1], arrInputDirection[2] };
		Placement::ProbeCollisionRay stRay;
		stRay.arrDirection = arrInputDirection;
		stRay.fDistance = 24;
		double dNearest = 24;
		for (const Triangle &arrTriangle : arrTriangles)
		{
			const Vector arrEdgeA = Subtract(arrTriangle[1], arrTriangle[0]);
			const Vector arrEdgeB = Subtract(arrTriangle[2], arrTriangle[0]);
			const Vector arrP = Cross(arrDirection, arrEdgeB);
			const double dDet = Dot(arrEdgeA, arrP);
			if (std::abs(dDet) <= 1.0e-12)
			{
				continue;
			}
			const double dInverse = 1 / dDet;
			const Vector arrT = Subtract(arrOrigin, arrTriangle[0]);
			const double dU = Dot(arrT, arrP) * dInverse;
			const Vector arrQ = Cross(arrT, arrEdgeA);
			const double dV = Dot(arrDirection, arrQ) * dInverse;
			const double dDistance = Dot(arrEdgeB, arrQ) * dInverse;
			if (dU < 0 || dV < 0 || dU + dV > 1 || dDistance < 0 || dDistance >= dNearest)
			{
				continue;
			}
			const Vector arrNormal = Cross(arrEdgeA, arrEdgeB);
			const double dLength = std::sqrt(Dot(arrNormal, arrNormal));
			if (dLength == 0)
			{
				continue;
			}
			dNearest = dDistance;
			stRay.fDistance = static_cast<float>(dDistance);
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				stRay.arrNormal[nAxis] = static_cast<float>(arrNormal[nAxis] / dLength);
			}
			stRay.eKind = Dot(arrDirection, arrNormal) < 0 ? Placement::ProbeHitKind::Front : Placement::ProbeHitKind::Back;
		}
		arrCollisionRays.push_back(stRay);
	}
	return arrCollisionRays;
}
std::vector<Placement::ProbeCollisionRay> TraceWithWitnesses(const std::vector<Triangle> &arrTriangles, const Vector &arrOrigin, bool bDropZero = false)
{
	std::vector<Placement::ProbeCollisionRay> arrCollisionRays = Trace(arrTriangles, arrOrigin);
	if (bDropZero)
	{
		for (Placement::ProbeCollisionRay &stRay : arrCollisionRays)
		{
			if (stRay.fDistance <= 1.0e-5F)
			{
				stRay.eKind = Placement::ProbeHitKind::Miss;
				stRay.fDistance = 24;
			}
		}
	}
	constexpr double SEARCH_RADIUS = 0.08;
	for (std::size_t nAxisRay = 0; nAxisRay < 6; ++nAxisRay)
	{
		const Placement::ProbeCollisionRay &stAxis = arrCollisionRays[nAxisRay];
		const Vector arrStart{ arrOrigin[0] - stAxis.arrDirection[0] * SEARCH_RADIUS, arrOrigin[1] - stAxis.arrDirection[1] * SEARCH_RADIUS, arrOrigin[2] - stAxis.arrDirection[2] * SEARCH_RADIUS };
		const Placement::ProbeCollisionRay stHit = Trace(arrTriangles, arrStart)[nAxisRay];
		if (stHit.eKind == Placement::ProbeHitKind::Miss || stHit.fDistance > SEARCH_RADIUS * 2)
		{
			continue;
		}
		const Vector arrPoint{ arrStart[0] + stAxis.arrDirection[0] * stHit.fDistance, arrStart[1] + stAxis.arrDirection[1] * stHit.fDistance, arrStart[2] + stAxis.arrDirection[2] * stHit.fDistance };
		const Vector arrNormal{ stHit.arrNormal[0], stHit.arrNormal[1], stHit.arrNormal[2] };
		const double dSignedDistance = Dot(Subtract(arrOrigin, arrPoint), arrNormal);
		Placement::ProbeCollisionRay stWitness;
		stWitness.arrNormal = stHit.arrNormal;
		stWitness.fDistance = static_cast<float>(std::abs(dSignedDistance));
		stWitness.eKind = dSignedDistance >= 0 ? Placement::ProbeHitKind::FrontProximity : Placement::ProbeHitKind::BackProximity;
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stWitness.arrDirection[nAxis] = stHit.arrNormal[nAxis] * (dSignedDistance >= 0 ? -1.0F : 1.0F);
		}
		arrCollisionRays.push_back(stWitness);
	}
	return arrCollisionRays;
}
Vector Position(const Vector &arrAnchor, const Placement::ProbePlacement &stState)
{
	return { arrAnchor[0] + stState.arrOffset[0], arrAnchor[1] + stState.arrOffset[1], arrAnchor[2] + stState.arrOffset[2] };
}
Placement::ProbePlacement Settle(const std::vector<Triangle> &arrTriangles, const Vector &arrAnchor, const std::array<float, 3> &arrSpacing, Placement::ProbePlacement stState = {})
{
	Placement::ProbeRelocationSettings stSettings;
	for (std::uint32_t nUpdate = 0; nUpdate < 10; ++nUpdate)
	{
		const std::vector<Placement::ProbeCollisionRay> arrCollisionRays = TraceWithWitnesses(arrTriangles, Position(arrAnchor, stState));
		Placement::ProbePlacementCandidate stCandidate;
		ENGINE_NEXT_CHECK(Placement::EvaluateProbeRelocation(stSettings, arrSpacing, stState, arrCollisionRays, 1, stCandidate));
		ENGINE_NEXT_CHECK(Placement::CommitProbeRelocation(stCandidate, 1, stState));
		if (stState.eClassification == Placement::ProbeClassification::Active)
		{
			return stState;
		}
	}
	return stState;
}
} // namespace

ENGINE_NEXT_TEST("Relocation preserves a stable open probe and invalidates geometry revisions")
{
	const std::vector<Triangle> arrEmpty;
	const Vector arrAnchor{};
	Placement::ProbePlacement stState = Settle(arrEmpty, arrAnchor, { 1, 1, 1 });
	ENGINE_NEXT_CHECK(stState.eClassification == Placement::ProbeClassification::Active);
	Placement::ProbePlacementCandidate stCandidate;
	const std::vector<Placement::ProbeCollisionRay> arrCollisionRays = Trace(arrEmpty, arrAnchor);
	ENGINE_NEXT_CHECK(Placement::EvaluateProbeRelocation({}, { 1, 1, 1 }, stState, arrCollisionRays, 1, stCandidate));
	ENGINE_NEXT_CHECK(!stCandidate.bResetHistory && !stCandidate.bMoved);
	ENGINE_NEXT_CHECK(Placement::EvaluateProbeRelocation({}, { 1, 1, 1 }, stState, arrCollisionRays, 2, stCandidate));
	ENGINE_NEXT_CHECK(stCandidate.bResetHistory && stCandidate.stPlacement.eClassification == Placement::ProbeClassification::Pending);
	ENGINE_NEXT_CHECK(!Placement::CommitProbeRelocation(stCandidate, 1, stState));
	ENGINE_NEXT_CHECK(stState.nSceneRevision == 1);
}

ENGINE_NEXT_TEST("Relocation resolves exact front back zero-distance boundaries")
{
	std::vector<Triangle> arrPlane;
	Quad(arrPlane, { -10, 0, -10 }, { -10, 0, 10 }, { 10, 0, 10 }, { 10, 0, -10 });
	const Placement::ProbePlacement stState = Settle(arrPlane, { 0, 0, 0 }, { 1, 1, 1 });
	ENGINE_NEXT_CHECK(stState.eClassification == Placement::ProbeClassification::Active);
	ENGINE_NEXT_CHECK(stState.arrOffset[1] >= 0.08F);
	ENGINE_NEXT_CHECK(stState.arrOffset[0] == 0 && stState.arrOffset[2] == 0);
}

ENGINE_NEXT_TEST("Relocation escapes a thin closed wall and deactivates an inescapable solid")
{
	const Placement::ProbePlacement stThin = Settle(Box(0.12), { 0, 0, 0 }, { 1, 1, 1 });
	ENGINE_NEXT_CHECK(stThin.eClassification == Placement::ProbeClassification::Active);
	const float fMaximum = (std::max)({ std::abs(stThin.arrOffset[0]), std::abs(stThin.arrOffset[1]), std::abs(stThin.arrOffset[2]) });
	ENGINE_NEXT_CHECK(fMaximum > 0.2F && fMaximum <= 0.45F);
	const Placement::ProbePlacement stLarge = Settle(Box(2), { 0, 0, 0 }, { 1, 1, 1 });
	ENGINE_NEXT_CHECK(stLarge.eClassification != Placement::ProbeClassification::Active);
	ENGINE_NEXT_CHECK(std::abs(stLarge.arrOffset[0]) <= 0.45F);
}

ENGINE_NEXT_TEST("Short crossing segments recover a surface even when zero-origin long hits are absent")
{
	std::vector<Triangle> arrPlane;
	Quad(arrPlane, { -10, 0, -10 }, { -10, 0, 10 }, { 10, 0, 10 }, { 10, 0, -10 });
	const std::vector<Placement::ProbeCollisionRay> arrCollisionRays = TraceWithWitnesses(arrPlane, {}, true);
	ENGINE_NEXT_CHECK(arrCollisionRays.size() > 64);
	for (std::size_t nIndex = 0; nIndex < 64; ++nIndex)
	{
		ENGINE_NEXT_CHECK(arrCollisionRays[nIndex].eKind == Placement::ProbeHitKind::Miss);
	}
	Placement::ProbePlacementCandidate stCandidate;
	ENGINE_NEXT_CHECK(Placement::EvaluateProbeRelocation({}, { 1, 1, 1 }, {}, arrCollisionRays, 1, stCandidate));
	ENGINE_NEXT_CHECK(stCandidate.bMoved && stCandidate.bResetHistory);
	ENGINE_NEXT_CHECK(stCandidate.stPlacement.arrOffset[1] >= 0.08F);
	ENGINE_NEXT_CHECK(stCandidate.stPlacement.eClassification == Placement::ProbeClassification::Pending);
}

ENGINE_NEXT_TEST("Moving geometry makes prior lighting ineligible until relocation is checked again")
{
	const Vector arrOrigin{};
	Placement::ProbePlacement stState = Settle({}, arrOrigin, { 1, 1, 1 });
	Placement::ProbePlacementCandidate stCandidate;
	ENGINE_NEXT_CHECK(Placement::EvaluateProbeRelocation({}, { 1, 1, 1 }, stState, Trace(Box(0.12), arrOrigin), 2, stCandidate));
	ENGINE_NEXT_CHECK(stCandidate.bResetHistory && stCandidate.bMoved);
	ENGINE_NEXT_CHECK(stCandidate.stPlacement.eClassification == Placement::ProbeClassification::Pending);
}

ENGINE_NEXT_TEST("Relocation invalid observations preserve the previous candidate")
{
	Placement::ProbePlacementCandidate stCandidate;
	stCandidate.stPlacement.nSceneRevision = 123;
	std::vector<Placement::ProbeCollisionRay> arrCollisionRays = Trace({}, {});
	arrCollisionRays[0].fDistance = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(!Placement::EvaluateProbeRelocation({}, { 1, 1, 1 }, {}, arrCollisionRays, 1, stCandidate));
	ENGINE_NEXT_CHECK(stCandidate.stPlacement.nSceneRevision == 123);
	arrCollisionRays = Trace({}, {});
	ENGINE_NEXT_CHECK(!Placement::EvaluateProbeRelocation({}, { 0, 1, 1 }, {}, arrCollisionRays, 1, stCandidate));
	ENGINE_NEXT_CHECK(stCandidate.stPlacement.nSceneRevision == 123);
	stCandidate.stPlacement.arrOffset[1] = std::numeric_limits<float>::infinity();
	Placement::ProbePlacement stOutput;
	stOutput.nSceneRevision = 44;
	ENGINE_NEXT_CHECK(!Placement::CommitProbeRelocation(stCandidate, 123, stOutput));
	ENGINE_NEXT_CHECK(stOutput.nSceneRevision == 44);
}

ENGINE_NEXT_TEST("Changed geometry invalidates only intersecting placement neighborhoods")
{
	const EngineNext::Rendering::WorldBounds stBounds{ { -0.2, -0.2, -0.2 }, { 0.2, 0.2, 0.2 } };
	bool bAffected = false;
	ENGINE_NEXT_CHECK(Placement::ProbeTouchesChangedGeometry({}, { 0, 0, 0 }, { 1, 1, 1 }, stBounds, bAffected));
	ENGINE_NEXT_CHECK(bAffected);
	ENGINE_NEXT_CHECK(Placement::ProbeTouchesChangedGeometry({}, { 5, 0, 0 }, { 1, 1, 1 }, stBounds, bAffected));
	ENGINE_NEXT_CHECK(!bAffected);
	ENGINE_NEXT_CHECK(Placement::ProbeTouchesChangedGeometry({}, { 0.7F, 0, 0 }, { 1, 1, 1 }, stBounds, bAffected));
	ENGINE_NEXT_CHECK(bAffected);
	ENGINE_NEXT_CHECK(!Placement::ProbeTouchesChangedGeometry({}, { 0, 0, 0 }, { 0, 1, 1 }, stBounds, bAffected));
	ENGINE_NEXT_CHECK(bAffected);
}

ENGINE_NEXT_TEST("Deterministic interior samples escape with bounded offsets and finite states")
{
	const std::vector<Triangle> arrBox = Box(0.12);
	for (std::uint32_t nIndex = 0; nIndex < 125; ++nIndex)
	{
		const Vector arrAnchor{ (static_cast<double>(nIndex % 5) - 2) * 0.04, (static_cast<double>((nIndex / 5) % 5) - 2) * 0.04, (static_cast<double>(nIndex / 25) - 2) * 0.04 };
		const Placement::ProbePlacement stState = Settle(arrBox, arrAnchor, { 1, 1, 1 });
		const Vector arrPosition = Position(arrAnchor, stState);
		ENGINE_NEXT_CHECK(stState.eClassification == Placement::ProbeClassification::Active);
		ENGINE_NEXT_CHECK((std::max)({ std::abs(arrPosition[0]), std::abs(arrPosition[1]), std::abs(arrPosition[2]) }) >= 0.19999);
		double dDistanceSquared = 0;
		for (float fOffset : stState.arrOffset)
		{
			ENGINE_NEXT_CHECK(std::isfinite(fOffset));
			dDistanceSquared += static_cast<double>(fOffset) * fOffset;
		}
		ENGINE_NEXT_CHECK(dDistanceSquared <= 0.45001 * 0.45001);
	}
}

ENGINE_NEXT_TEST("Placement offset revision cannot wrap into a reusable history identity")
{
	std::vector<Triangle> arrPlane;
	Quad(arrPlane, { -10, 0, -10 }, { -10, 0, 10 }, { 10, 0, 10 }, { 10, 0, -10 });
	Placement::ProbePlacement stState;
	stState.nOffsetRevision = std::numeric_limits<std::uint32_t>::max();
	Placement::ProbePlacementCandidate stCandidate;
	ENGINE_NEXT_CHECK(Placement::EvaluateProbeRelocation({}, { 1, 1, 1 }, stState, TraceWithWitnesses(arrPlane, {}), 1, stCandidate));
	ENGINE_NEXT_CHECK(stCandidate.bResetHistory && !stCandidate.bMoved);
	ENGINE_NEXT_CHECK(stCandidate.stPlacement.nOffsetRevision == stState.nOffsetRevision);
	ENGINE_NEXT_CHECK(stCandidate.stPlacement.eClassification == Placement::ProbeClassification::Inactive);
}

ENGINE_NEXT_TEST("Changed geometry covers rounded large-coordinate probe centers")
{
	const float fAnchor = 100000000.0F;
	const float fOffset = 32.0F * 0.45F;
	const float fActualCenter = fAnchor + fOffset;
	ENGINE_NEXT_CHECK_EQ(fActualCenter, 100000016.0F);
	const Placement::WorldBounds stChanged{ { 100000015.9, -0.1, -0.1 }, { 100000016.1, 0.1, 0.1 } };
	bool bAffected = false;
	ENGINE_NEXT_CHECK(Placement::ProbeTouchesChangedGeometry({}, { fAnchor, 0, 0 }, { 32, 1, 1 }, stChanged, bAffected));
	ENGINE_NEXT_CHECK(bAffected);
	const Placement::WorldBounds stFar{ { 100010000, -0.1, -0.1 }, { 100010001, 0.1, 0.1 } };
	ENGINE_NEXT_CHECK(Placement::ProbeTouchesChangedGeometry({}, { fAnchor, 0, 0 }, { 32, 1, 1 }, stFar, bAffected));
	ENGINE_NEXT_CHECK(!bAffected);
}

ENGINE_NEXT_TEST("Changed bounds contain the uploaded binary32 matrix result")
{
	const Placement::WorldBounds stPoint{ { 0, 0, 0 }, { 0, 0, 0 } };
	const std::array<double, 16> arrWorld{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 100000001.0, 0, 0, 1 };
	Placement::WorldBounds stBounds;
	ENGINE_NEXT_CHECK(Placement::TransformProbeGeometryBounds(stPoint, arrWorld, stBounds));
	const double dUploadedTranslation = static_cast<float>(arrWorld[12]);
	ENGINE_NEXT_CHECK(stBounds.arrMinimum[0] <= dUploadedTranslation);
	ENGINE_NEXT_CHECK(stBounds.arrMaximum[0] >= dUploadedTranslation);
}

ENGINE_NEXT_TEST("Probe geometry bounds preserve affine corners and failure output")
{
	const Placement::WorldBounds stLocal{ { -1, -2, -3 }, { 1, 2, 3 } };
	std::array<double, 16> arrWorld{ -2, 0, 0, 0, 0.25, 3, 0, 0, 0, 0, 0, 0, 10, -4, 2, 1 };
	Placement::WorldBounds stBounds;
	ENGINE_NEXT_CHECK(Placement::TransformProbeGeometryBounds(stLocal, arrWorld, stBounds));
	for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		const double dX = (nCorner & 1) != 0 ? 1 : -1;
		const double dY = (nCorner & 2) != 0 ? 2 : -2;
		const std::array<double, 3> arrExpected{ 10 - 2 * dX + 0.25 * dY, -4 + 3 * dY, 2 };
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			ENGINE_NEXT_CHECK(stBounds.arrMinimum[nAxis] <= arrExpected[nAxis]);
			ENGINE_NEXT_CHECK(stBounds.arrMaximum[nAxis] >= arrExpected[nAxis]);
		}
	}
	const Placement::WorldBounds stBefore = stBounds;
	arrWorld[3] = 0.5;
	ENGINE_NEXT_CHECK(!Placement::TransformProbeGeometryBounds(stLocal, arrWorld, stBounds));
	ENGINE_NEXT_CHECK(stBounds.arrMinimum == stBefore.arrMinimum && stBounds.arrMaximum == stBefore.arrMaximum);
	arrWorld[3] = 0;
	arrWorld[1] = std::numeric_limits<double>::infinity();
	ENGINE_NEXT_CHECK(!Placement::TransformProbeGeometryBounds(stLocal, arrWorld, stBounds));
}

ENGINE_NEXT_TEST("Probe placement numeric settings are bounded independently of the feature switch")
{
	Placement::ProbeRelocationSettings stSettings;
	ENGINE_NEXT_CHECK(Placement::ValidateProbeRelocationSettings(stSettings));
	stSettings.nMinimumRays = 1025;
	ENGINE_NEXT_CHECK(!Placement::ValidateProbeRelocationSettings(stSettings));
	stSettings.nMinimumRays = 32;
	stSettings.nRequiredStableUpdates = 65;
	ENGINE_NEXT_CHECK(!Placement::ValidateProbeRelocationSettings(stSettings));
	stSettings.nRequiredStableUpdates = 2;
	stSettings.fMinimumClearance = std::numeric_limits<float>::denorm_min();
	ENGINE_NEXT_CHECK(!Placement::ValidateProbeRelocationSettings(stSettings));
}

ENGINE_NEXT_TEST("Explicit deformation bounds include old and new geometry without a world transform change")
{
	std::vector<Placement::GiGeometryChange> arrChanges{
		{ 0, { { -2, -1, -1 }, { -1, 1, 1 } }, { { 1, -1, -1 }, { 2, 1, 1 } } },
		{ 2, { { 0, -3, 0 }, { 0, -3, 0 } }, { { 0, 3, 0 }, { 0, 3, 0 } } }
	};
	Placement::WorldBounds stBounds;
	ENGINE_NEXT_CHECK(Placement::BuildProbeGeometryChangeBounds(arrChanges, 3, stBounds));
	ENGINE_NEXT_CHECK((stBounds.arrMinimum == std::array<double, 3>{ -2, -3, -1 }));
	ENGINE_NEXT_CHECK((stBounds.arrMaximum == std::array<double, 3>{ 2, 3, 1 }));
	bool bAffected = false;
	ENGINE_NEXT_CHECK(Placement::ProbeTouchesChangedGeometry({}, { 1.5F, 0, 0 }, { 1, 1, 1 }, stBounds, bAffected));
	ENGINE_NEXT_CHECK(bAffected);
	const Placement::WorldBounds stBefore = stBounds;
	ENGINE_NEXT_CHECK(!Placement::BuildProbeGeometryChangeBounds({}, 3, stBounds));
	ENGINE_NEXT_CHECK(!Placement::BuildProbeGeometryChangeBounds(arrChanges, 1, stBounds));
	arrChanges[1].nDraw = 0;
	ENGINE_NEXT_CHECK(!Placement::BuildProbeGeometryChangeBounds(arrChanges, 3, stBounds));
	arrChanges[1].nDraw = 3;
	ENGINE_NEXT_CHECK(!Placement::BuildProbeGeometryChangeBounds(arrChanges, 3, stBounds));
	arrChanges[1].nDraw = 2;
	arrChanges[1].stCurrentWorldBounds.arrMinimum[0] = 1;
	ENGINE_NEXT_CHECK(!Placement::BuildProbeGeometryChangeBounds(arrChanges, 3, stBounds));
	arrChanges[1].stCurrentWorldBounds.arrMinimum[0] = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!Placement::BuildProbeGeometryChangeBounds(arrChanges, 3, stBounds));
	ENGINE_NEXT_CHECK(stBounds.arrMinimum == stBefore.arrMinimum && stBounds.arrMaximum == stBefore.arrMaximum);
}
