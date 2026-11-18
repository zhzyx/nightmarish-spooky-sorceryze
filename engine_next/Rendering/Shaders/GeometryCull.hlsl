// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "GeometryVisibility.hlsli"

cbuffer GeometryConstants : register(b0)
{
    column_major float4x4 ViewProjection;
    float4 FrustumPlanes[6];
    uint4 Viewport;
    uint4 Counts;
    float4 Parameters;
};
struct GeometryCluster
{
    float4 Minimum;
    float4 Maximum;
    uint4 Draw;
    uint4 Metadata;
};
struct GeometryInstance
{
    column_major float4x4 World;
    uint2 Constants;
    uint2 Padding;
};
struct GeometryBucket
{
    uint Material;
    uint Flags;
    uint FirstCommand;
    uint CommandCapacity;
};
struct GeometryCommand
{
    uint2 Constants;
#ifdef PAGED_GEOMETRY_STAGE
    uint2 VertexAddress;
    uint VertexBytes;
    uint VertexStride;
    uint2 IndexAddress;
    uint IndexBytes;
    uint IndexFormat;
#endif
    uint IndexCount;
    uint InstanceCount;
    uint StartIndex;
    int BaseVertex;
    uint StartInstance;
    uint Padding;
};
#ifdef PAGED_GEOMETRY_STAGE
struct GeometryPageView
{
    uint2 VertexAddress;
    uint VertexBytes;
    uint VertexStride;
    uint2 IndexAddress;
    uint IndexBytes;
    uint IndexFormat;
};
StructuredBuffer<GeometryPageView> PageViews : register(t4);
#endif
StructuredBuffer<GeometryCluster> Clusters : register(t0);
StructuredBuffer<GeometryInstance> Instances : register(t1);
Texture2D<float> HiZ : register(t2);
StructuredBuffer<GeometryBucket> Buckets : register(t3);
RWStructuredBuffer<GeometryCommand> Commands : register(u0);
// Requested commands, overflow, invalid input, emitted triangles, bucket counts.
RWBuffer<uint> Counters : register(u1);

[numthreads(64, 1, 1)]
void CullCS(uint3 Thread : SV_DispatchThreadID)
{
    uint Index = Thread.x + Thread.y * 4194240u;
    if (Index >= Counts.x)
    {
        return;
    }
    GeometryCluster Cluster = Clusters[Index];
    uint InstanceCount, InstanceStride, BucketCount, BucketStride;
    Instances.GetDimensions(InstanceCount, InstanceStride);
    Buckets.GetDimensions(BucketCount, BucketStride);
    uint BucketIndex = Cluster.Metadata.x;
    if (Cluster.Draw.w >= InstanceCount || BucketIndex >= min(Counts.y, BucketCount) ||
        !ClusterBoundsValid(Cluster.Minimum.xyz, Cluster.Maximum.xyz))
    {
        InterlockedAdd(Counters[2], 1);
        return;
    }
    GeometryInstance Instance = Instances[Cluster.Draw.w];
    float3 Minimum = float3(3.402823466e38, 3.402823466e38, 3.402823466e38);
    float3 Maximum = -Minimum;
    float3 AbsoluteTerms = 0;
    bool Finite = true;
    [unroll] for (uint Corner = 0; Corner < 8; ++Corner)
    {
        float3 Local = float3((Corner & 1) != 0 ? Cluster.Maximum.x : Cluster.Minimum.x,
            (Corner & 2) != 0 ? Cluster.Maximum.y : Cluster.Minimum.y,
            (Corner & 4) != 0 ? Cluster.Maximum.z : Cluster.Minimum.z);
        float3 World = mul(Instance.World, float4(Local, 1)).xyz;
        AbsoluteTerms = max(AbsoluteTerms, mul(abs(Instance.World), float4(abs(Local), 1)).xyz);
        Finite = Finite && all(isfinite(World));
        Minimum = min(Minimum, World);
        Maximum = max(Maximum, World);
    }
    // Cover accumulated binary32 transform roundoff before any rejection.
    float3 Padding = AbsoluteTerms * 0.000000476837158203125;
    Minimum -= Padding;
    Maximum += Padding;
    Finite = Finite && all(isfinite(Minimum)) && all(isfinite(Maximum));
    if (Finite && !ClusterInFrustum(Minimum, Maximum, FrustumPlanes))
    {
        return;
    }
    if (Finite && Counts.w != 0)
    {
        float4 Corners[8];
        [unroll] for (uint Corner = 0; Corner < 8; ++Corner)
        {
            float3 World = float3((Corner & 1) != 0 ? Maximum.x : Minimum.x,
                (Corner & 2) != 0 ? Maximum.y : Minimum.y,
                (Corner & 4) != 0 ? Maximum.z : Minimum.z);
            Corners[Corner] = mul(ViewProjection, float4(World, 1));
        }
        ClusterScreenBounds Bounds = (ClusterScreenBounds)0;
        ClusterHiZFootprint Footprint = (ClusterHiZFootprint)0;
        if (ClusterProjectBounds(Corners, Viewport.x, Viewport.y, Bounds) && ClusterChooseHiZ(Bounds, Counts.z, Footprint))
        {
            float A = HiZ.Load(int3(Footprint.MinimumX, Footprint.MinimumY, Footprint.Mip));
            float B = HiZ.Load(int3(Footprint.MaximumX, Footprint.MinimumY, Footprint.Mip));
            float C = HiZ.Load(int3(Footprint.MinimumX, Footprint.MaximumY, Footprint.Mip));
            float D = HiZ.Load(int3(Footprint.MaximumX, Footprint.MaximumY, Footprint.Mip));
            if (ClusterDepthOccluded(Bounds.ClosestDepth, ClusterReduceReverseDepth(A, B, C, D), Parameters.x))
            {
                return;
            }
        }
    }
#ifdef PAGED_GEOMETRY_STAGE
    if (Cluster.Metadata.y >= Viewport.z)
    {
        InterlockedAdd(Counters[2], 1);
        return;
    }
    GeometryPageView Page = PageViews[Cluster.Metadata.y];
    if ((Page.VertexAddress.x | Page.VertexAddress.y) == 0 ||
        (Page.IndexAddress.x | Page.IndexAddress.y) == 0 || Page.VertexStride != 48 || Page.IndexFormat != 42 ||
        Cluster.Draw.y > Page.IndexBytes / 4 || Cluster.Draw.x > Page.IndexBytes / 4 - Cluster.Draw.y)
    {
        InterlockedAdd(Counters[2], 1);
        return;
    }
#endif
    InterlockedAdd(Counters[0], 1);
    GeometryBucket Bucket = Buckets[BucketIndex];
    uint Slot;
    InterlockedAdd(Counters[4 + BucketIndex], 1, Slot);
    uint CommandCount, CommandStride;
    Commands.GetDimensions(CommandCount, CommandStride);
    if (Slot >= Bucket.CommandCapacity || Bucket.FirstCommand >= CommandCount || Slot >= CommandCount - Bucket.FirstCommand)
    {
        InterlockedAdd(Counters[1], 1);
        return;
    }
    GeometryCommand Command;
    Command.Constants = Instance.Constants;
#ifdef PAGED_GEOMETRY_STAGE
    Command.VertexAddress = Page.VertexAddress;
    Command.VertexBytes = Page.VertexBytes;
    Command.VertexStride = Page.VertexStride;
    Command.IndexAddress = Page.IndexAddress;
    Command.IndexBytes = Page.IndexBytes;
    Command.IndexFormat = Page.IndexFormat;
#endif
    Command.IndexCount = Cluster.Draw.x;
    Command.InstanceCount = 1;
    Command.StartIndex = Cluster.Draw.y;
    Command.BaseVertex = asint(Cluster.Draw.z);
    Command.StartInstance = 0;
    Command.Padding = 0;
    Commands[Bucket.FirstCommand + Slot] = Command;
    InterlockedAdd(Counters[3], Cluster.Draw.x / 3);
}
