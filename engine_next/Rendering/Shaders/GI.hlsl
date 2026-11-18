// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "GISampling.hlsli"
#include "RayTracingScene.hlsli"
#include "GILighting.hlsli"
#include "GiMaterialSampling.hlsli"
#include "ProbePlacementMath.hlsli"

cbuffer GiConstants : register(b0)
{
	GiGridParameters Grid;
	float4 PlacementLimits;
	uint4 PlacementInfo;
}
struct GiVertex
{
	float3 Position;
	float3 Normal;
	float4 Tangent;
	float2 Texcoord;
};
RaytracingAccelerationStructure Scene : register(t0);
StructuredBuffer<GiVertex> Vertices : register(t1);
StructuredBuffer<uint> Indices : register(t2);
StructuredBuffer<RayTracingDraw> Draws : register(t3);
StructuredBuffer<RayTracingMaterial> Materials : register(t4);
StructuredBuffer<float4> ProbePositions : register(t5);
StructuredBuffer<uint> UpdateIndices : register(t6);
StructuredBuffer<float4> ReadSh : register(t7);
StructuredBuffer<float2> ReadMoments : register(t8);
StructuredBuffer<uint4> ReadState : register(t9);
TextureCube<float4> Environment : register(t10);
StructuredBuffer<uint> RemapIndices : register(t11);
Texture2DArray<float> DirectionalShadow : register(t12);
Texture2DArray<float> LocalShadow : register(t13);
StructuredBuffer<float4> RayResults : register(t14);
StructuredBuffer<uint4> RayStatus : register(t15);
StructuredBuffer<float4> MaterialExtensions : register(t16);
StructuredBuffer<float4> DirectionalTint : register(t17);
StructuredBuffer<uint> PlacementRevisions : register(t18);
RWStructuredBuffer<float4> WriteRayResults : register(u0);
RWStructuredBuffer<uint4> WriteRayStatus : register(u1);
RWStructuredBuffer<float4> WriteSh : register(u2);
RWStructuredBuffer<float2> WriteMoments : register(u3);
RWStructuredBuffer<uint4> WriteState : register(u4);
Texture2D<float4> MaterialTextures[2045] : register(t0, space1);
SamplerState MaterialSamplers[2045] : register(s0, space1);
SamplerState EnvironmentSampler : register(s0);

[numthreads(64, 1, 1)] void PrepareCS(uint3 Thread : SV_DispatchThreadID)
{
	uint Probe = Thread.x;
	if (Probe >= Grid.WorkInfo.x)
	{
		return;
	}
	uint Old = RemapIndices[Probe];
	uint Destination = GiStateIndex(Probe, Grid);
	uint Source = GiStateIndex(Old, Grid);
	bool Valid = false;
	if (Grid.History.z > 0.5 && Old < Grid.WorkInfo.x)
	{
		Valid = ReadState[Source].x != 0;
		if (Grid.Counts.w != 0)
		{
			Valid = Valid && ReadState[Source + 2].x == PROBE_ACTIVE && ReadState[Source + 2].y == PlacementRevisions[Probe];
		}
	}
	[unroll] for (uint Term = 0; Term < 9; ++Term)
	{
		WriteSh[Probe * 9 + Term] = Valid ? ReadSh[Old * 9 + Term] : float4(0, 0, 0, 0);
	}
	[loop] for (uint Texel = 0; Texel < 64; ++Texel)
	{
		WriteMoments[Probe * 64 + Texel] = Valid ? ReadMoments[Old * 64 + Texel] : float2(0, 0);
	}
	WriteState[Destination] = Valid ? ReadState[Source] : uint4(0, 0, 0, 0);
	if (Grid.Counts.w != 0)
	{
		bool HasPlacement = Grid.History.z > 0.5 && Old < Grid.WorkInfo.x;
		WriteState[Destination + 1] = HasPlacement ? ReadState[Source + 1] : uint4(0, 0, 0, 0);
		WriteState[Destination + 2] = HasPlacement ? ReadState[Source + 2] : uint4(0, 0, 0, 0);
	}
}

float4 GiTexture(uint Material, uint Slot, float2 Uv)
{
	uint Index = Material * 5 + Slot;
	if (Index >= Grid.Counts.x || Index >= 2045)
	{
		return Slot == 2 ? float4(0.5, 0.5, 1, 1) : float4(1, 1, 1, 1);
	}
	uint Descriptor = NonUniformResourceIndex(Index);
	return MaterialTextures[Descriptor].SampleLevel(MaterialSamplers[Descriptor], Uv, 0);
}
bool GiTriangle(uint Instance, uint Triangle, out RayTracingDraw Draw, out uint3 Vertex)
{
	Draw = (RayTracingDraw)0;
	Vertex = 0;
	uint DrawCount, DrawStride, VertexCount, VertexStride, IndexCount, IndexStride;
	Draws.GetDimensions(DrawCount, DrawStride);
	Vertices.GetDimensions(VertexCount, VertexStride);
	Indices.GetDimensions(IndexCount, IndexStride);
	if (Instance >= DrawCount)
	{
		return false;
	}
	Draw = Draws[Instance];
	if (Draw.Material >= Grid.Counts.y || Triangle >= Draw.IndexCount / 3 || Draw.FirstIndex > IndexCount || Draw.IndexCount > IndexCount - Draw.FirstIndex)
	{
		return false;
	}
	uint First = Draw.FirstIndex + Triangle * 3;
	Vertex = uint3(Indices[First], Indices[First + 1], Indices[First + 2]);
	if (Draw.BaseVertex >= VertexCount || any(Vertex >= VertexCount - Draw.BaseVertex))
	{
		return false;
	}
	Vertex += Draw.BaseVertex;
	return true;
}
float2 GiTriangleUv(uint3 Vertex, float2 Bary)
{
	return Vertices[Vertex.x].Texcoord * (1 - Bary.x - Bary.y) + Vertices[Vertex.y].Texcoord * Bary.x + Vertices[Vertex.z].Texcoord * Bary.y;
}

RelocationSummary ObservePlacementRay(RelocationSummary Summary, float3 Center, uint Index)
{
	bool Proximity = Index >= PlacementInfo.x;
	float3 Direction = RelocationDirection(Proximity ? Index - PlacementInfo.x : Index, PlacementInfo.x);
	RayDesc Ray;
	Ray.Origin = Center - (Proximity ? Direction * PlacementLimits.x : 0);
	Ray.Direction = Direction;
	Ray.TMin = 0;
	Ray.TMax = Proximity ? 2 * PlacementLimits.x : Grid.Sampling.x;
	RayQuery<RAY_FLAG_FORCE_NON_OPAQUE | RAY_FLAG_SKIP_PROCEDURAL_PRIMITIVES> Query;
	Query.TraceRayInline(Scene, RAY_FLAG_NONE, 255, Ray);
	uint Candidates = 0;
	[loop] while (Query.Proceed())
	{
		if (++Candidates > 4096)
		{
			Query.Abort();
			Summary.Invalid += 1;
			return Summary;
		}
		if (Query.CandidateType() == CANDIDATE_NON_OPAQUE_TRIANGLE)
		{
			RayTracingDraw Draw;
			uint3 Vertex;
			if (!GiTriangle(Query.CandidateInstanceID(), Query.CandidatePrimitiveIndex(), Draw, Vertex))
			{
				Query.Abort();
				Summary.Invalid += 1;
				return Summary;
			}
			float2 Uv = GiTriangleUv(Vertex, Query.CandidateTriangleBarycentrics());
			if (RayTracingAlphaAccept(Materials[Draw.Material], GiTexture(Draw.Material, 0, Uv).a))
			{
				Query.CommitNonOpaqueTriangleHit();
			}
		}
	}
	float Distance = Grid.Sampling.x;
	float3 Normal = 0;
	uint Kind = Proximity ? PROBE_PROXIMITY_MISS : PROBE_MISS;
	if (Query.CommittedStatus() == COMMITTED_TRIANGLE_HIT)
	{
		RayTracingDraw Draw;
		uint3 Vertex;
		if (!GiTriangle(Query.CommittedInstanceID(), Query.CommittedPrimitiveIndex(), Draw, Vertex))
		{
			Summary.Invalid += 1;
			return Summary;
		}
		float3 ObjectNormal = cross(Vertices[Vertex.y].Position - Vertices[Vertex.x].Position,
			Vertices[Vertex.z].Position - Vertices[Vertex.x].Position);
		Normal = GiDirection(mul(ObjectNormal, (float3x3)Query.CommittedWorldToObject3x4()));
		Distance = Query.CommittedRayT();
		if (Proximity)
		{
			float3 Hit = Ray.Origin + Direction * Distance;
			float SignedDistance = dot(Center - Hit, Normal);
			Direction = Normal * (SignedDistance >= 0 ? -1 : 1);
			Distance = abs(SignedDistance);
			Kind = SignedDistance >= 0 ? PROBE_FRONT_PROXIMITY : PROBE_BACK_PROXIMITY;
		}
		else
		{
			Kind = dot(Direction, Normal) < 0 ? PROBE_FRONT : PROBE_BACK;
		}
	}
	return RelocationObserve(Summary, Direction, Distance, Normal, Kind);
}

[numthreads(64, 1, 1)] void RelocateCS(uint3 Thread : SV_DispatchThreadID)
{
	if (Grid.Counts.w == 0 || Thread.x >= Grid.WorkInfo.y)
	{
		return;
	}
	uint Probe = UpdateIndices[Thread.x];
	if (Probe >= Grid.WorkInfo.x)
	{
		return;
	}
	uint State = GiStateIndex(Probe, Grid);
	float4 Offset = asfloat(WriteState[State + 1]);
	uint4 Metadata = WriteState[State + 2];
	RelocationState Previous = { Offset.xyz, Offset.w, Metadata.x, Metadata.y, Metadata.z, Metadata.w };
	RelocationSummary Summary = RelocationBegin(Grid.Sampling.x);
	float3 Center = ProbePositions[Probe].xyz + Previous.Offset;
	[loop] for (uint Ray = 0; Ray < PlacementInfo.x + 6; ++Ray)
	{
		Summary = ObservePlacementRay(Summary, Center, Ray);
	}
	uint Level = min(uint(ProbePositions[Probe].w), Grid.GridInfo.w - 1);
	float3 Spacing = 1 / Grid.InverseSpacing[Level].xyz;
	RelocationParameters Settings = { PlacementLimits.x, PlacementLimits.y, PlacementLimits.z, PlacementInfo.x, PlacementInfo.y };
	RelocationDecision Decision = RelocationEvaluate(Settings, Spacing, Previous, Summary, PlacementRevisions[Probe]);
	WriteState[State + 1] = asuint(float4(Decision.State.Offset, Decision.State.Clearance));
	WriteState[State + 2] = uint4(Decision.State.Classification, Decision.State.SceneRevision, Decision.State.StableUpdates, Decision.State.OffsetRevision);
	if (Decision.ResetHistory != 0)
	{
		WriteState[State] = Summary.Invalid != 0 ? uint4(0, Grid.WorkInfo.w, Grid.WorkInfo.z, 1) : uint4(0, 0, 0, 0);
		[unroll] for (uint Term = 0; Term < 9; ++Term)
		{
			WriteSh[Probe * 9 + Term] = 0;
		}
		[loop] for (uint Texel = 0; Texel < 64; ++Texel)
		{
			WriteMoments[Probe * 64 + Texel] = 0;
		}
	}
}

[numthreads(64, 1, 1)] void TraceCS(uint3 Thread : SV_DispatchThreadID)
{
	uint RayIndex = GiRayLinearIndex(Thread.x, Thread.y, Grid.Counts.z);
	if (RayIndex >= Grid.WorkInfo.y * Grid.WorkInfo.z)
	{
		return;
	}
	uint Update = RayIndex / Grid.WorkInfo.z;
	uint Probe = UpdateIndices[Update];
	if (Probe >= Grid.WorkInfo.x)
	{
		WriteRayResults[RayIndex] = 0;
		WriteRayStatus[RayIndex] = uint4(2, 0, 0, 0);
		return;
	}
	if (Grid.Counts.w != 0 && ReadState[GiStateIndex(Probe, Grid) + 2].x != PROBE_ACTIVE)
	{
		WriteRayResults[RayIndex] = 0;
		WriteRayStatus[RayIndex] = uint4(1, 0xffffffffu, 0, 0);
		return;
	}
	float3 Direction = GiRayDirection(RayIndex % Grid.WorkInfo.z, Grid.WorkInfo.z, Probe, Grid.WorkInfo.w);
	RayDesc Ray;
	Ray.Origin = ProbePositions[Probe].xyz + GiPlacementOffset(Probe, Grid, ReadState);
	Ray.Direction = Direction;
	Ray.TMin = 0;
	Ray.TMax = Grid.Sampling.x;
	RayQuery<RAY_FLAG_SKIP_PROCEDURAL_PRIMITIVES | RAY_FLAG_CULL_BACK_FACING_TRIANGLES> Query;
	Query.TraceRayInline(Scene, RAY_FLAG_NONE, 255, Ray);
	uint Candidates = 0;
	bool Valid = true;
	[loop] while (Query.Proceed())
	{
		if (++Candidates > 4096)
		{
			Valid = false;
			Query.Abort();
			break;
		}
		if (Query.CandidateType() == CANDIDATE_NON_OPAQUE_TRIANGLE)
		{
			RayTracingDraw Draw;
			uint3 Vertex;
			if (!GiTriangle(Query.CandidateInstanceID(), Query.CandidatePrimitiveIndex(), Draw, Vertex))
			{
				Valid = false;
				Query.Abort();
				break;
			}
			float2 Uv = GiTriangleUv(Vertex, Query.CandidateTriangleBarycentrics());
			if (RayTracingAlphaAccept(Materials[Draw.Material], GiTexture(Draw.Material, 0, Uv).a))
			{
				Query.CommitNonOpaqueTriangleHit();
			}
		}
	}
	float3 Radiance = 0;
	float Distance = 1;
	uint Instance = 0xffffffffu;
	if (Valid && Query.CommittedStatus() == COMMITTED_TRIANGLE_HIT)
	{
		Instance = Query.CommittedInstanceID();
		RayTracingDraw Draw;
		uint3 Vertex;
		Valid = GiTriangle(Instance, Query.CommittedPrimitiveIndex(), Draw, Vertex);
		if (Valid)
		{
			float2 Bary = Query.CommittedTriangleBarycentrics();
			float3 Weights = float3(1 - Bary.x - Bary.y, Bary.x, Bary.y);
			GiVertex A = Vertices[Vertex.x];
			GiVertex B = Vertices[Vertex.y];
			GiVertex C = Vertices[Vertex.z];
			float2 Uv = A.Texcoord * Weights.x + B.Texcoord * Weights.y + C.Texcoord * Weights.z;
			float3 ObjectNormal = A.Normal * Weights.x + B.Normal * Weights.y + C.Normal * Weights.z;
			float4 ObjectTangent = A.Tangent * Weights.x + B.Tangent * Weights.y + C.Tangent * Weights.z;
			float3x3 WorldToObject = (float3x3)Query.CommittedWorldToObject3x4();
			float3x3 ObjectToWorld = (float3x3)Query.CommittedObjectToWorld3x4();
			float3 Geometric = GiDirection(mul(cross(B.Position - A.Position, C.Position - A.Position), WorldToObject));
			float3 N = GiDirection(mul(ObjectNormal, WorldToObject));
			float Face = Query.CommittedTriangleFrontFace() ? 1 : -1;
			N *= Face;
			Geometric *= Face;
			float3 T = mul(ObjectToWorld, ObjectTangent.xyz);
			T = UnitDirection(T - N * dot(T, N), GiDirection(cross(abs(N.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0), N)));
			float3x3 NormalizedWorld = float3x3(GiDirection(ObjectToWorld[0]), GiDirection(ObjectToWorld[1]), GiDirection(ObjectToWorld[2]));
			float Handedness = determinant(NormalizedWorld) < 0 ? -1 : 1;
			float3 Bitangent = GiDirection(cross(N, T)) * ObjectTangent.w * Handedness;
			RayTracingMaterial Material = Materials[Draw.Material];
			float3 Mapped = GiTexture(Draw.Material, 2, Uv).xyz * 2 - 1;
			float NormalScale = max(abs(Material.Surface.z), 1);
			Mapped = GiDirection(float3(Mapped.xy * (Material.Surface.z / NormalScale), Mapped.z / NormalScale));
			N = GiDirection(T * Mapped.x + Bitangent * Mapped.y + N * Mapped.z);
			float3 Base = saturate(Material.BaseColor.rgb * GiTexture(Draw.Material, 0, Uv).rgb);
			float4 Mr = GiTexture(Draw.Material, 1, Uv);
			float Roughness = saturate(Material.Surface.x * Mr.g);
			float Metallic = saturate(Material.Surface.y * Mr.b);
			float Ao = lerp(1, GiTexture(Draw.Material, 3, Uv).r, Material.Surface.w);
			float3 Emissive = Material.Emissive.rgb * GiTexture(Draw.Material, 4, Uv).rgb;
			float3 Position = Ray.Origin + Direction * Query.CommittedRayT();
			float4 Extension = MaterialExtensions[Draw.Material];
			Radiance = GiDirectLighting(Base, Metallic, Roughness, Position, N, -Direction, Geometric, T, ObjectTangent.w * Handedness, Extension, DirectionalShadow, LocalShadow, DirectionalTint[0].rgb);
			float NoV = saturate(dot(N, -Direction));
			float3 Bands = float3(GI_PI, 2 * GI_PI / 3, GI_PI / 4);
			float3 F0 = lerp(float3(0.04, 0.04, 0.04), Base, Metallic);
			float3 F = F0 + (max(1 - Roughness, F0) - F0) * pow(1 - NoV, 5);
			float3 Factor = (1 - F) * (1 - Metallic) * Base / GI_PI;
			if (Extension.x != 0 || Extension.z != 0)
			{
				Bands = GiMaterialDiffuseBands(Extension.x);
				Factor = GiMaterialDiffuseFactor(Base, Metallic, Extension.x, NoV);
			}
			float4 Indirect = GiSampleIrradianceBands(Position, N, -Direction, Grid, ReadSh, ReadMoments, ReadState, Bands);
			float3 Bounce = Indirect.rgb * Factor * Indirect.a * saturate(Ao) * Grid.History.x;
			Radiance = float3(GiFiniteSum(Radiance.x, Bounce.x), GiFiniteSum(Radiance.y, Bounce.y), GiFiniteSum(Radiance.z, Bounce.z));
			Radiance = float3(GiFiniteSum(Radiance.x, Emissive.x), GiFiniteSum(Radiance.y, Emissive.y), GiFiniteSum(Radiance.z, Emissive.z));
			Distance = saturate(Query.CommittedRayT() / Grid.Sampling.x);
		}
	}
	else if (Valid)
	{
		Radiance = Environment.SampleLevel(EnvironmentSampler, Direction, 0).rgb;
	}
	Valid = Valid && GiFinite(Radiance);
	WriteRayResults[RayIndex] = Valid ? float4(max(Radiance, 0), Distance) : float4(0, 0, 0, 0);
	WriteRayStatus[RayIndex] = uint4(Valid ? 1 : 2, Instance, Candidates, 0);
}

		[numthreads(64, 1, 1)] void UpdateCS(uint3 Thread : SV_DispatchThreadID)
{
	uint Update = Thread.x;
	if (Update >= Grid.WorkInfo.y)
	{
		return;
	}
	uint Probe = UpdateIndices[Update];
	if (Probe >= Grid.WorkInfo.x)
	{
		return;
	}
	uint RayCount = Grid.WorkInfo.z;
	uint State = GiStateIndex(Probe, Grid);
	if (Grid.Counts.w != 0 && WriteState[State + 2].x != PROBE_ACTIVE)
	{
		return;
	}
	GiSh9 Current = GiZeroSh();
	bool Valid = true;
	[loop] for (uint Ray = 0; Ray < RayCount; ++Ray)
	{
		uint Index = Update * RayCount + Ray;
		float4 Sample = RayResults[Index];
		Valid = Valid && RayStatus[Index].x == 1 && GiFinite(Sample.rgb) && isfinite(Sample.w);
		Current = GiAccumulateRay(Current, GiRayDirection(Ray, RayCount, Probe, Grid.WorkInfo.w), Sample.rgb, 4 * GI_PI / RayCount);
	}
	if (!Valid)
	{
		WriteState[State] = uint4(0, Grid.WorkInfo.w, RayCount, 1);
		return;
	}
	uint Old = RemapIndices[Probe];
	bool HistoryValid = false;
	if (Grid.History.z > 0.5 && Old < Grid.WorkInfo.x)
	{
		uint PriorState = GiStateIndex(Old, Grid);
		HistoryValid = ReadState[PriorState].x != 0;
		if (Grid.Counts.w != 0)
		{
			uint4 PreviousPlacement = ReadState[PriorState + 2];
			uint4 CurrentPlacement = WriteState[State + 2];
			HistoryValid = HistoryValid && PreviousPlacement.x == PROBE_ACTIVE &&
				PreviousPlacement.y == CurrentPlacement.y && PreviousPlacement.w == CurrentPlacement.w;
		}
	}
	GiSh9 Previous = GiZeroSh();
	if (HistoryValid)
	{
		[unroll] for (uint Term = 0; Term < 9; ++Term)
		{
			Previous.Coefficients[Term] = ReadSh[Old * 9 + Term].rgb;
		}
	}
	float3 Luma = float3(0.2126, 0.7152, 0.0722);
	float OldLuminance = max(dot(Previous.Coefficients[0], Luma), 0);
	float NewLuminance = max(dot(Current.Coefficients[0], Luma), 0);
	float Weight = GiHistoryWeight(OldLuminance, NewLuminance, Grid.Sampling.y, Grid.History.y, HistoryValid);
	GiSh9 Blended = GiBlendSh(Previous, Current, Weight);
	[unroll] for (uint Term = 0; Term < 9; ++Term)
	{
		WriteSh[Probe * 9 + Term] = float4(Blended.Coefficients[Term], 0);
	}
	[loop] for (uint Texel = 0; Texel < 64; ++Texel)
	{
		float3 Direction = GiOctDecode((float2(Texel % 8, Texel / 8) + 0.5) / 8);
		float2 Sum = 0;
		float Total = 0;
		[loop] for (uint Ray = 0; Ray < RayCount; ++Ray)
		{
			float DirectionWeight = GiDistanceWeight(GiRayDirection(Ray, RayCount, Probe, Grid.WorkInfo.w), Direction);
			float Distance = saturate(RayResults[Update * RayCount + Ray].w);
			Sum += float2(Distance, Distance * Distance) * DirectionWeight;
			Total += DirectionWeight;
		}
		float2 Moments = Total > 0 ? Sum / Total : float2(1, 1);
		if (HistoryValid)
		{
			float2 Prior = ReadMoments[Old * 64 + Texel];
			Moments = float2(GiBlendScalar(Prior.x, Moments.x, Weight), GiBlendScalar(Prior.y, Moments.y, Weight));
		}
		WriteMoments[Probe * 64 + Texel] = Moments;
	}
	WriteState[State] = uint4(1, Grid.WorkInfo.w, RayCount, 0);
}
