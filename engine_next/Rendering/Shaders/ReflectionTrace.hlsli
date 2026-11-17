// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_REFLECTION_TRACE_HLSLI
#define ENGINE_NEXT_REFLECTION_TRACE_HLSLI

#ifdef __cplusplus
#define SSR_INOUT(Type, Name) Type &Name
#else
#define SSR_INOUT(Type, Name) inout Type Name
#endif

static const uint SSR_INVALID = 0;
static const uint SSR_CLIPPED = 1;
static const uint SSR_MISS = 2;
static const uint SSR_HIT = 3;
static const uint SSR_BUDGET = 4;

struct SsrTraceParameters
{
    float2 Viewport;
    // Clip = (scaleX*x + offsetX*depth, scaleY*y + offsetY*depth, Z, depth).
    // The offset is NDC; the Y viewport mapping changes its sign to screen-down.
    float4 Projection;
    float2 NearFar;
    float MaxDistance;
    float Thickness;
    float MinDistance;
    float EdgeFadePixels;
    uint MaxSteps;
};

struct SsrTraceResult
{
    float2 Uv;
    float2 ProjectedUv;
    float RayDistance;
    float ViewDepth;
    int2 Pixel;
    float Confidence;
    uint Steps;
    uint Reason;
};

bool SsrFinite3(float3 Value)
{
    return isfinite(Value.x) && isfinite(Value.y) && isfinite(Value.z);
}

// Clip a unit-direction ray against Constant + Slope*t >= 0.
bool SsrClipPlane(float Constant, float Slope, SSR_INOUT(float, First), SSR_INOUT(float, Last))
{
    if (!isfinite(Constant) || !isfinite(Slope))
    {
        return false;
    }
    if (Slope == 0)
    {
        return Constant >= 0;
    }
    float Time = -Constant / Slope;
    if (Slope > 0)
    {
        First = max(First, Time);
    }
    else
    {
        Last = min(Last, Time);
    }
    return First <= Last;
}

float SsrViewDepth(float DeviceDepth, float2 NearFar)
{
    return NearFar.x / (DeviceDepth + (NearFar.x / NearFar.y) * (1 - DeviceDepth));
}

float2 SsrProjectPixel(float3 ViewPosition, SsrTraceParameters Parameters)
{
    float Depth = -ViewPosition.z;
    float NdcX = ViewPosition.x * Parameters.Projection.x / Depth + Parameters.Projection.z;
    float NdcY = ViewPosition.y * Parameters.Projection.y / Depth + Parameters.Projection.w;
    return float2((NdcX * 0.5f + 0.5f) * Parameters.Viewport.x,
        (0.5f - NdcY * 0.5f) * Parameters.Viewport.y);
}

// Mip-zero reference traversal. Input positions use RH view space, forward -Z.
// Returns a depth-slab candidate; the caller must reject a back-facing hit normal
// before using radiance. Depth must match the supplied projection and viewport.
SsrTraceResult TraceScreenRay(Texture2D<float> SceneDepth, float3 Origin, float3 Direction, SsrTraceParameters Parameters)
{
    SsrTraceResult Result;
    Result.Uv = float2(0, 0);
    Result.ProjectedUv = float2(0, 0);
    Result.RayDistance = 0;
    Result.ViewDepth = 0;
    Result.Pixel = int2(-1, -1);
    Result.Confidence = 0;
    Result.Steps = 0;
    Result.Reason = SSR_INVALID;
    if (!SsrFinite3(Origin) || !SsrFinite3(Direction) ||
        !isfinite(Parameters.Viewport.x) || !isfinite(Parameters.Viewport.y) ||
        Parameters.Viewport.x < 1 || Parameters.Viewport.y < 1 ||
        Parameters.Viewport.x > 16384 || Parameters.Viewport.y > 16384 ||
        !isfinite(Parameters.Projection.x) || !isfinite(Parameters.Projection.y) ||
        !isfinite(Parameters.Projection.z) || !isfinite(Parameters.Projection.w) ||
        Parameters.Projection.x <= 0 || Parameters.Projection.y <= 0 ||
        !isfinite(Parameters.NearFar.x) || !isfinite(Parameters.NearFar.y) ||
        Parameters.NearFar.x < 0.001f || Parameters.NearFar.y > 1.0e7f || Parameters.NearFar.y <= Parameters.NearFar.x ||
        !isfinite(Parameters.MaxDistance) || Parameters.MaxDistance <= 0 || Parameters.MaxDistance > 1000 ||
        !isfinite(Parameters.MinDistance) || Parameters.MinDistance < 0 || Parameters.MinDistance >= Parameters.MaxDistance ||
        !isfinite(Parameters.Thickness) || Parameters.Thickness < 0 || Parameters.Thickness > 10 ||
        !isfinite(Parameters.EdgeFadePixels) || Parameters.EdgeFadePixels < 0 ||
        Parameters.MaxSteps == 0 || Parameters.MaxSteps > 256)
    {
        return Result;
    }
    uint Width;
    uint Height;
    SceneDepth.GetDimensions(Width, Height);
    if (float(Width) != Parameters.Viewport.x || float(Height) != Parameters.Viewport.y)
    {
        return Result;
    }
    float DirectionScale = max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z)));
    if (DirectionScale <= 0)
    {
        return Result;
    }
    Direction = Direction / DirectionScale;
    float DirectionLength = sqrt(Direction.x * Direction.x + Direction.y * Direction.y + Direction.z * Direction.z);
    Direction = Direction / DirectionLength;
    float First = Parameters.MinDistance;
    float Last = Parameters.MaxDistance;
    float Depth = -Origin.z;
    float DepthSlope = -Direction.z;
    float4 P = Parameters.Projection;
    Result.Reason = SSR_CLIPPED;
    if (!SsrClipPlane(Depth - Parameters.NearFar.x, DepthSlope, First, Last) ||
        !SsrClipPlane(Parameters.NearFar.y - Depth, -DepthSlope, First, Last) ||
        !SsrClipPlane(P.x * Origin.x + (P.z + 1) * Depth, P.x * Direction.x + (P.z + 1) * DepthSlope, First, Last) ||
        !SsrClipPlane(-P.x * Origin.x + (1 - P.z) * Depth, -P.x * Direction.x + (1 - P.z) * DepthSlope, First, Last) ||
        !SsrClipPlane(P.y * Origin.y + (P.w + 1) * Depth, P.y * Direction.y + (P.w + 1) * DepthSlope, First, Last) ||
        !SsrClipPlane(-P.y * Origin.y + (1 - P.w) * Depth, -P.y * Direction.y + (1 - P.w) * DepthSlope, First, Last) ||
        !isfinite(First) || !isfinite(Last) || Last <= First)
    {
        return Result;
    }
    float3 StartView = Origin + Direction * First;
    float3 EndView = Origin + Direction * Last;
    float2 Start = SsrProjectPixel(StartView, Parameters);
    float2 End = SsrProjectPixel(EndView, Parameters);
    if (!isfinite(Start.x) || !isfinite(Start.y) || !isfinite(End.x) || !isfinite(End.y) ||
        StartView.z >= 0 || EndView.z >= 0)
    {
        return Result;
    }
    float InverseStartDepth = -1 / StartView.z;
    float InverseEndDepth = -1 / EndView.z;
    float2 Delta = End - Start;
    int StepX = Delta.x > 0 ? 1 : (Delta.x < 0 ? -1 : 0);
    int StepY = Delta.y > 0 ? 1 : (Delta.y < 0 ? -1 : 0);
    // Pick the cell entered by the ray exactly, including a viewport boundary.
    // Fixed pixel epsilons disappear at 4K and can skip near-boundary cells.
    int2 Pixel = int2(StepX < 0 ? ceil(Start.x) - 1 : floor(Start.x),
        StepY < 0 ? ceil(Start.y) - 1 : floor(Start.y));
    int2 SourcePixel = int2(-1, -1);
    if (Depth > 0)
    {
        float2 ProjectedOrigin = SsrProjectPixel(Origin, Parameters);
        if (isfinite(ProjectedOrigin.x) && isfinite(ProjectedOrigin.y) &&
            ProjectedOrigin.x >= 0 && ProjectedOrigin.x < float(Width) &&
            ProjectedOrigin.y >= 0 && ProjectedOrigin.y < float(Height))
        {
            SourcePixel = int2(floor(ProjectedOrigin.x), floor(ProjectedOrigin.y));
        }
    }
    float Entry = 0;
    for (uint Iteration = 0; Iteration < Parameters.MaxSteps; ++Iteration)
    {
        if (Pixel.x < 0 || Pixel.y < 0 || Pixel.x >= int(Width) || Pixel.y >= int(Height))
        {
            Result.Reason = SSR_MISS;
            return Result;
        }
        Result.Steps = Iteration + 1;
        float NextX = StepX == 0 ? 2.0f : (float(Pixel.x + (StepX > 0 ? 1 : 0)) - Start.x) / Delta.x;
        float NextY = StepY == 0 ? 2.0f : (float(Pixel.y + (StepY > 0 ? 1 : 0)) - Start.y) / Delta.y;
        float Exit = max(Entry, min(1.0f, min(NextX, NextY)));
        float DeviceDepth = SceneDepth.Load(int3(Pixel.x, Pixel.y, 0));
        if ((Pixel.x != SourcePixel.x || Pixel.y != SourcePixel.y) && isfinite(DeviceDepth) && DeviceDepth > 0 && DeviceDepth <= 1)
        {
            float SurfaceDepth = SsrViewDepth(DeviceDepth, Parameters.NearFar);
            float EntryDepth = 1 / lerp(InverseStartDepth, InverseEndDepth, Entry);
            float ExitDepth = 1 / lerp(InverseStartDepth, InverseEndDepth, Exit);
            float MinimumDepth = min(EntryDepth, ExitDepth);
            float MaximumDepth = max(EntryDepth, ExitDepth);
            float SlabEnd = SurfaceDepth + Parameters.Thickness;
            if (isfinite(SurfaceDepth) && MinimumDepth <= SlabEnd && MaximumDepth >= SurfaceDepth)
            {
                float CandidateDepth = clamp(SurfaceDepth, MinimumDepth, MaximumDepth);
                float InverseDifference = InverseEndDepth - InverseStartDepth;
                float Candidate = InverseDifference == 0 ? Entry :
                    clamp((1 / CandidateDepth - InverseStartDepth) / InverseDifference, Entry, Exit);
                float InverseDepth = lerp(InverseStartDepth, InverseEndDepth, Candidate);
                if (!isfinite(InverseDepth) || InverseDepth <= 0)
                {
                    Result.Reason = SSR_INVALID;
                    return Result;
                }
                Result.RayDistance = lerp(First * InverseStartDepth, Last * InverseEndDepth, Candidate) / InverseDepth;
                Result.ViewDepth = 1 / InverseDepth;
                float2 HitPixel = Start + Delta * Candidate;
                // The texel-center UV and integer Pixel identify the tested surface.
                // ProjectedUv retains the geometric intersection for debug output.
                Result.Pixel = Pixel;
                Result.Uv = float2((float(Pixel.x) + 0.5f) / float(Width), (float(Pixel.y) + 0.5f) / float(Height));
                Result.ProjectedUv = float2(HitPixel.x / float(Width), HitPixel.y / float(Height));
                float EdgeDistance = min(min(HitPixel.x, float(Width) - HitPixel.x), min(HitPixel.y, float(Height) - HitPixel.y));
                float EdgeConfidence = Parameters.EdgeFadePixels > 0 ? saturate(EdgeDistance / Parameters.EdgeFadePixels) : 1.0f;
                // Thickness determines acceptance. The sampled cell depth is
                // quantized spatially and cannot provide a continuous hit weight.
                Result.Confidence = EdgeConfidence;
                Result.Reason = SSR_HIT;
                return Result;
            }
        }
        if (Exit >= 1)
        {
            Result.Reason = SSR_MISS;
            return Result;
        }
        if (NextX <= NextY)
        {
            Pixel.x += StepX;
        }
        if (NextY <= NextX)
        {
            Pixel.y += StepY;
        }
        Entry = Exit;
    }
    Result.Reason = SSR_BUDGET;
    return Result;
}

#undef SSR_INOUT
#endif
