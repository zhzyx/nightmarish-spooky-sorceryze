// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_PROBE_PLACEMENT_MATH
#define ENGINE_NEXT_PROBE_PLACEMENT_MATH

static const uint PROBE_PENDING = 0;
static const uint PROBE_ACTIVE = 1;
static const uint PROBE_INACTIVE = 2;
static const uint PROBE_MISS = 0;
static const uint PROBE_FRONT = 1;
static const uint PROBE_BACK = 2;
static const uint PROBE_FRONT_PROXIMITY = 3;
static const uint PROBE_BACK_PROXIMITY = 4;
static const uint PROBE_PROXIMITY_MISS = 5;

struct RelocationSummary
{
	float3 FrontNormal;
	float FrontClearance;
	float3 BackDirection;
	float BackDistance;
	uint Rays;
	uint Backfaces;
	uint Invalid;
	uint BackProximity;
	float TraceDistance;
};

struct RelocationState
{
	float3 Offset;
	float Clearance;
	uint Classification;
	uint SceneRevision;
	uint StableUpdates;
	uint OffsetRevision;
};

struct RelocationParameters
{
	float MinimumClearance;
	float MaximumOffsetFraction;
	float BackfaceThreshold;
	uint MinimumRays;
	uint RequiredStableUpdates;
};

struct RelocationDecision
{
	RelocationState State;
	uint ResetHistory;
	uint Moved;
};

bool RelocationFinite(float3 Value)
{
	return isfinite(Value.x) && isfinite(Value.y) && isfinite(Value.z);
}

float3 RelocationDirection(uint Index, uint Count)
{
	if (Index < 6)
	{
		float Sign = (Index & 1) == 0 ? 1.0f : -1.0f;
		return Index < 2 ? float3(Sign, 0, 0) : (Index < 4 ? float3(0, Sign, 0) : float3(0, 0, Sign));
	}
	float Y = 1 - 2 * (float(Index - 6) + 0.5f) / float(Count - 6);
	float Phi = 2.39996322972865332f * float(Index - 6);
	float Radius = sqrt(max(1 - Y * Y, 0));
	return float3(cos(Phi) * Radius, Y, sin(Phi) * Radius);
}

RelocationSummary RelocationBegin(float TraceDistance)
{
	RelocationSummary Summary;
	Summary.FrontNormal = float3(0, 0, 0);
	Summary.FrontClearance = TraceDistance;
	Summary.BackDirection = float3(0, 0, 0);
	Summary.BackDistance = TraceDistance;
	Summary.Rays = 0;
	Summary.Backfaces = 0;
	Summary.Invalid = 0;
	Summary.BackProximity = 0;
	Summary.TraceDistance = TraceDistance;
	return Summary;
}

// Hit kind remains explicit so a backface hit at exactly t=0 cannot lose its
// classification through floating-point signed-zero handling.
RelocationSummary RelocationObserve(RelocationSummary Summary, float3 Direction, float Distance, float3 Normal, uint Kind)
{
	Summary.Rays += Kind <= PROBE_BACK ? 1 : 0;
	bool Front = Kind == PROBE_FRONT || Kind == PROBE_FRONT_PROXIMITY;
	bool Back = Kind == PROBE_BACK || Kind == PROBE_BACK_PROXIMITY;
	bool Miss = Kind == PROBE_MISS || Kind == PROBE_PROXIMITY_MISS;
	if (!RelocationFinite(Direction) || !isfinite(Distance) || Distance < 0 || Distance > Summary.TraceDistance || Kind > PROBE_PROXIMITY_MISS ||
		abs(dot(Direction, Direction) - 1) > 0.0001f ||
		(!Miss && (!RelocationFinite(Normal) || abs(dot(Normal, Normal) - 1) > 0.0001f)) ||
		(Front && dot(Direction, Normal) >= 0) ||
		(Back && dot(Direction, Normal) <= 0))
	{
		Summary.Invalid += 1;
		return Summary;
	}
	if (Kind == PROBE_PROXIMITY_MISS)
	{
		return Summary;
	}
	if (Front)
	{
		float Clearance = Distance * abs(dot(Direction, Normal));
		if (Clearance < Summary.FrontClearance)
		{
			Summary.FrontClearance = Clearance;
			Summary.FrontNormal = Normal;
		}
	}
	if (Back)
	{
		Summary.Backfaces += Kind == PROBE_BACK ? 1 : 0;
		Summary.BackProximity += Kind == PROBE_BACK_PROXIMITY ? 1 : 0;
		if (Distance < Summary.BackDistance)
		{
			Summary.BackDistance = Distance;
			Summary.BackDirection = Direction;
		}
	}
	return Summary;
}

RelocationDecision RelocationEvaluate(RelocationParameters Parameters, float3 Spacing, RelocationState Previous,
	RelocationSummary Summary, uint SceneRevision)
{
	RelocationDecision Decision;
	Decision.State = Previous;
	Decision.State.SceneRevision = SceneRevision;
	Decision.State.Clearance = Summary.FrontClearance;
	Decision.Moved = 0;
	Decision.ResetHistory = 1;
	if (Summary.Invalid != 0 || Summary.Rays < Parameters.MinimumRays)
	{
		Decision.State.Classification = PROBE_INACTIVE;
		Decision.State.StableUpdates = 0;
		return Decision;
	}
	bool SameScene = Previous.SceneRevision == SceneRevision;
	bool Inside = float(Summary.Backfaces) > float(Summary.Rays) * Parameters.BackfaceThreshold ||
		(Summary.BackProximity != 0 && Summary.BackDistance < Parameters.MinimumClearance);
	bool NearFront = Summary.FrontClearance < Parameters.MinimumClearance;
	float TargetClearance = Parameters.MinimumClearance * 1.001f;
	float3 Delta = float3(0, 0, 0);
	// Prefer a front surface's free half-space at a shared t=0 boundary. An
	// interior point with only backfaces instead advances through its nearest exit.
	if (NearFront && (!Inside || Summary.FrontClearance <= Summary.BackDistance))
	{
		Delta = Summary.FrontNormal * (TargetClearance - Summary.FrontClearance);
	}
	else if (Inside)
	{
		Delta = Summary.BackDirection * (Summary.BackDistance + TargetClearance);
	}
	float3 Target = Previous.Offset + Delta;
	float3 Normalized = float3(Target.x / Spacing.x, Target.y / Spacing.y, Target.z / Spacing.z);
	float Length = sqrt(dot(Normalized, Normalized));
	if (!RelocationFinite(Target) || !isfinite(Length))
	{
		Decision.State.Classification = PROBE_INACTIVE;
		Decision.State.StableUpdates = 0;
		return Decision;
	}
	if (Length > Parameters.MaximumOffsetFraction)
	{
		Target = Target * (Parameters.MaximumOffsetFraction / Length);
	}
	float3 Change = Target - Previous.Offset;
	bool Moved = Change.x != 0 || Change.y != 0 || Change.z != 0;
	if (Inside || NearFront)
	{
		if (Moved && Previous.OffsetRevision == 0xffffffffu)
		{
			Decision.State.Classification = PROBE_INACTIVE;
			Decision.State.StableUpdates = 0;
			return Decision;
		}
		Decision.State.Offset = Target;
		Decision.State.Classification = Moved ? PROBE_PENDING : PROBE_INACTIVE;
		Decision.State.StableUpdates = 0;
		Decision.State.OffsetRevision += Moved ? 1 : 0;
		Decision.Moved = Moved ? 1 : 0;
		return Decision;
	}
	Decision.State.StableUpdates = SameScene ? (Previous.StableUpdates < Parameters.RequiredStableUpdates ? Previous.StableUpdates + 1 : Parameters.RequiredStableUpdates) : 1;
	Decision.State.Classification = Decision.State.StableUpdates >= Parameters.RequiredStableUpdates ? PROBE_ACTIVE : PROBE_PENDING;
	Decision.ResetHistory = !SameScene || Previous.Classification != PROBE_ACTIVE || Decision.State.Classification != PROBE_ACTIVE ? 1 : 0;
	return Decision;
}
#endif
