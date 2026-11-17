// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_VOLUME_MATH_HLSLI
#define ENGINE_NEXT_VOLUME_MATH_HLSLI

#ifdef __cplusplus
#define VOLUME_INOUT(Type, Name) Type &Name
#else
#define VOLUME_INOUT(Type, Name) inout Type Name
#endif

static const float VOLUME_HALF_MAX = 65504.0f;
static const float VOLUME_PI = 3.14159265358979323846f;

struct VolumeIntegral
{
    float Scatter;
    float Transmittance;
};

bool VolumeGpuCoefficient(float Value)
{
    return isfinite(Value) && Value >= 0 && Value <= VOLUME_HALF_MAX &&
        (Value == 0 || Value >= 1.175494351e-38f);
}

bool VolumeHenyeyGreenstein(float G, float Mu, VOLUME_INOUT(float, Value))
{
    if (!isfinite(G) || !isfinite(Mu) || abs(G) > 0.95f || abs(Mu) > 1)
    {
        return false;
    }
    float Denominator = 1 + G * G - 2 * G * Mu;
    Value = (1 - G * G) / (4 * VOLUME_PI * Denominator * sqrt(Denominator));
    return true;
}

// Source is radiance per world unit for one channel. Explicit RGBA16F
// saturation applies to scattered radiance; extinction and transmittance
// remain physical coefficients and are never multiplied by pre-exposure.
bool VolumeIntegrateSegment(float Source, float Extinction, float Distance, VOLUME_INOUT(VolumeIntegral, Value))
{
    if (!VolumeGpuCoefficient(Source) || !VolumeGpuCoefficient(Extinction) || !isfinite(Distance) || Distance < 0)
    {
        return false;
    }
    float OpticalDepth = Extinction * Distance;
    float Weight;
    VolumeIntegral Candidate;
    if (Extinction == 0 || OpticalDepth < 0.001f)
    {
        // Stable limit of (1-exp(-sigma*d))/sigma, including sigma==0.
        float Squared = OpticalDepth * OpticalDepth;
        Weight = Distance * (1 - OpticalDepth * 0.5f + Squared / 6 - Squared * OpticalDepth / 24);
        Candidate.Transmittance = 1 - OpticalDepth + Squared * 0.5f - Squared * OpticalDepth / 6;
    }
    else
    {
        Candidate.Transmittance = OpticalDepth >= 80 ? 0 : exp(-OpticalDepth);
        Weight = (1 - Candidate.Transmittance) / Extinction;
    }
    Candidate.Scatter = min(VOLUME_HALF_MAX, Source * Weight);
    Value = Candidate;
    return true;
}

bool VolumeAccumulate(VolumeIntegral Previous, VolumeIntegral Segment, VOLUME_INOUT(VolumeIntegral, Value))
{
    if (!isfinite(Previous.Scatter) || !isfinite(Segment.Scatter) ||
        !isfinite(Previous.Transmittance) || !isfinite(Segment.Transmittance) ||
        Previous.Scatter < 0 || Segment.Scatter < 0 ||
        Previous.Scatter > VOLUME_HALF_MAX || Segment.Scatter > VOLUME_HALF_MAX ||
        Previous.Transmittance < 0 || Previous.Transmittance > 1 || Segment.Transmittance < 0 || Segment.Transmittance > 1)
    {
        return false;
    }
    Value.Scatter = min(VOLUME_HALF_MAX, Previous.Scatter + Previous.Transmittance * Segment.Scatter);
    Value.Transmittance = Previous.Transmittance * Segment.Transmittance;
    return true;
}

bool VolumeHeightDensity(float Density, float WorldY, float Height, float Falloff, VOLUME_INOUT(float, Value))
{
    if (!VolumeGpuCoefficient(Density) || !VolumeGpuCoefficient(Falloff) || !isfinite(WorldY) || !isfinite(Height))
    {
        return false;
    }
    if (Density == 0 || Falloff == 0)
    {
        Value = Density;
        return true;
    }
    // Preserve cancellation in nearby world coordinates. Only an overflowing
    // difference needs distributed multiplication for sub-unit falloff.
    float HeightDifference = WorldY - Height;
    float HeightTerm = !isfinite(HeightDifference) && Falloff <= 1 ?
        WorldY * Falloff - Height * Falloff : HeightDifference * Falloff;
    float LogDensity = log(Density) - HeightTerm;
    Value = LogDensity < log(1.175494351e-38f) ? 0 : exp(min(LogDensity, log(VOLUME_HALF_MAX)));
    Value = min(Value, VOLUME_HALF_MAX);
    Value = Value < 1.175494351e-38f ? 0 : Value;
    return true;
}

// Shape 0 is a box, shape 1 a sphere. Sphere extents contain equal radii.
// A local medium is bounded before any divisions or squared distance terms.
bool VolumeLocalWeight(uint Shape, float3 Position, float3 Center, float3 Extent, float EdgeFraction, VOLUME_INOUT(float, Value))
{
    if (Shape > 1 || !all(isfinite(Position)) || !all(isfinite(Center)) || !all(isfinite(Extent)) ||
        any(Extent < 1.175494351e-38f) || !isfinite(EdgeFraction) || EdgeFraction < 0 || EdgeFraction > 1 ||
        (Shape == 1 && (Extent.x != Extent.y || Extent.x != Extent.z)))
    {
        return false;
    }
    float3 Delta = abs(Position - Center);
    if (any(Delta > Extent))
    {
        Value = 0;
        return true;
    }
    float3 Local = Delta / Extent;
    float Radius = Shape == 0 ? max(Local.x, max(Local.y, Local.z)) : sqrt(dot(Local, Local));
    Value = Radius > 1 ? 0 : (EdgeFraction == 0 ? 1 : saturate((1 - Radius) / EdgeFraction));
    return true;
}

float VolumeLogRatio(float Numerator, float Denominator)
{
    float Delta = (Numerator - Denominator) / Denominator;
    // Preserve closely spaced clipping planes without subtracting two logs
    // or rounding 1 + Delta before the logarithm.
    return Delta < 0.001f ? Delta * (1 - Delta * 0.5f + Delta * Delta / 3) : log(Numerator / Denominator);
}

bool VolumeDepthAtSlice(float Near, float Far, uint Slices, float Boundary, VOLUME_INOUT(float, Value))
{
    if (!isfinite(Near) || !isfinite(Far) || Near < 0.001f || Near > 100 || Far > 1.0e7f || Far <= Near || Slices == 0 || Slices > 128 ||
        !isfinite(Boundary) || Boundary < 0 || Boundary > float(Slices))
    {
        return false;
    }
    if (Boundary == 0 || Boundary == float(Slices))
    {
        Value = Boundary == 0 ? Near : Far;
        return true;
    }
    float LogDepth = VolumeLogRatio(Far, Near) * (Boundary / float(Slices));
    float RelativeDepth = LogDepth < 0.001f ? LogDepth * (1 + LogDepth * 0.5f + LogDepth * LogDepth / 6) : exp(LogDepth) - 1;
    Value = Near + Near * RelativeDepth;
    return true;
}

bool VolumeSliceAtDepth(float Near, float Far, uint Slices, float Depth, VOLUME_INOUT(float, Value))
{
    if (!isfinite(Near) || !isfinite(Far) || Near < 0.001f || Near > 100 || Far > 1.0e7f || Far <= Near || Slices == 0 || Slices > 128 ||
        !isfinite(Depth) || Depth < 0)
    {
        return false;
    }
    if (Depth <= Near || Depth >= Far)
    {
        Value = Depth <= Near ? 0 : float(Slices);
        return true;
    }
    Value = saturate(VolumeLogRatio(Depth, Near) / VolumeLogRatio(Far, Near)) * float(Slices);
    return true;
}

// Positive view-depth interval converted to physical distance along one ray.
// Invalid inputs return zero so callers can retain a neutral partial integral.
float VolumePartialSegmentLength(float Distance, float Begin, float End, float RayScale)
{
    if (!isfinite(Distance) || !isfinite(Begin) || !isfinite(End) || !isfinite(RayScale) ||
        Distance < 0 || Begin < 0 || End < Begin || RayScale < 0)
    {
        return 0;
    }
    float Result = max(0, min(Distance, End) - Begin) * RayScale;
    return isfinite(Result) ? Result : 0;
}

#undef VOLUME_INOUT
#endif
