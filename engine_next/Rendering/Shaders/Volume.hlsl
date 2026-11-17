// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "VolumeCommon.hlsli"

#if defined(VOLUME_INJECT_STAGE)
struct GlobalMedium
{
    float4 DensityHeightFalloff;
    float4 Albedo;
    float4 Emission;
};
struct LocalMedium
{
    float4 CenterShape;
    float4 ExtentEdge;
    float4 AlbedoDensity;
    float4 Emission;
};
StructuredBuffer<GlobalMedium> GlobalMedia : register(t0);
StructuredBuffer<LocalMedium> LocalMedia : register(t1);
RWTexture3D<float4> OutputMedium : register(u0);
RWTexture3D<float4> OutputEmission : register(u1);

[numthreads(4, 4, 4)]
void InjectCS(uint3 Cell : SV_DispatchThreadID)
{
    if (any(Cell >= uint3(Grid.xyz)))
    {
        return;
    }
    float3 Position = VolumeWorldPosition(float2(Cell.xy), float(Cell.z) + 0.5f);
    GlobalMedium Global = GlobalMedia[0];
    float Density = 0;
    VolumeHeightDensity(Global.DensityHeightFalloff.x, Position.y,
        Global.DensityHeightFalloff.y, Global.DensityHeightFalloff.z, Density);
    float3 Scattering = VolumeColor(Global.Albedo.rgb * Density);
    float3 Emission = VolumeColor(Global.Emission.rgb);
    for (uint Index = 0; Index < min(uint(Grid.w), 16u); ++Index)
    {
        LocalMedium Local = LocalMedia[Index];
        float Weight = 0;
        if (VolumeLocalWeight(uint(Local.CenterShape.w), Position, Local.CenterShape.xyz,
            Local.ExtentEdge.xyz, Local.ExtentEdge.w, Weight))
        {
            float LocalDensity = Local.AlbedoDensity.w * Weight;
            Density = min(Density + LocalDensity, VOLUME_HALF_MAX);
            Scattering = VolumeColor(Scattering + Local.AlbedoDensity.rgb * LocalDensity);
            Emission = VolumeColor(Emission + Local.Emission.rgb * Weight);
        }
    }
    OutputMedium[Cell] = float4(Scattering, Density);
    OutputEmission[Cell] = float4(Emission, 0);
}

#elif defined(VOLUME_LIGHT_STAGE)
#include "ShadowSampling.hlsli"
Texture3D<float4> Medium : register(t0);
Texture3D<float4> Emission : register(t1);
Texture2DArray<float> DirectionalShadow : register(t2);
Texture2DArray<float> LocalShadow : register(t3);
StructuredBuffer<float4> ExposureState : register(t4);
RWTexture3D<float4> OutputSource : register(u0);

float VolumeCascadeVisibility(float3 Position, uint Cascade)
{
    float4 Clip = mul(ShadowViewProjection[Cascade], float4(Position, 1));
    if (!all(isfinite(Clip)) || Clip.w <= 0)
    {
        return 1;
    }
    return SampleShadowMap(DirectionalShadow, Clip.xyz / Clip.w, Cascade,
        round(1 / ShadowParameters.y), ShadowParameters.z, 0, float2(0, 1), true, false);
}

float VolumeDirectionalVisibility(float3 Position)
{
    float ViewDistance = -mul(View, float4(Position, 1)).z;
    if (ShadowParameters.x < 0.5f || ViewDistance > CascadeSplits.w)
    {
        return 1;
    }
    uint Cascade = ViewDistance > CascadeSplits.x ? 1 : 0;
    Cascade = ViewDistance > CascadeSplits.y ? 2 : Cascade;
    Cascade = ViewDistance > CascadeSplits.z ? 3 : Cascade;
    float Visibility = VolumeCascadeVisibility(Position, Cascade);
    if (Cascade < 3)
    {
        float Start = Cascade == 0 ? 0 : CascadeSplits[Cascade - 1];
        float Width = (CascadeSplits[Cascade] - Start) * Lighting.z;
        float Blend = saturate((ViewDistance - CascadeSplits[Cascade] + Width) / max(Width, 0.001f));
        if (Blend > 0)
        {
            Visibility = lerp(Visibility, VolumeCascadeVisibility(Position, Cascade + 1), Blend);
        }
    }
    return Visibility;
}

float VolumeLocalVisibility(LocalLightConstants Light, float3 Position)
{
    if (ShadowParameters.x < 0.5f || Light.ConeShadow.z < 0)
    {
        return 1;
    }
    uint Slice = uint(Light.ConeShadow.z);
    uint Face = 6;
    if (Light.DirectionType.w < 0.5f)
    {
        Face = ShadowCubeFace(Position - Light.PositionRange.xyz);
        Slice += Face;
    }
    float4 Clip = mul(LocalShadowMatrices[Slice], float4(Position, 1));
    if (!all(isfinite(Clip)) || Clip.w <= 0)
    {
        return 1;
    }
    // A medium sample has no receiver surface. Use radial comparison without
    // the surface-normal offset or receiver-plane intersection correction.
    return SampleShadowMap(LocalShadow, Clip.xyz / Clip.w, Slice, LocalCounts.z,
        ShadowParameters.z, Light.ShadowParameters.z, Light.ShadowParameters.xy,
        false, LocalCounts.w > 0.5f, Face, float3(0, 0, 0));
}

float VolumePhase(float3 ToLight, float3 ToCamera)
{
    float Phase = 0;
    VolumeHenyeyGreenstein(Parameters.x, clamp(dot(-ToLight, ToCamera), -1, 1), Phase);
    return Phase;
}

[numthreads(4, 4, 4)]
void LightCS(uint3 Cell : SV_DispatchThreadID)
{
    if (any(Cell >= uint3(Grid.xyz)))
    {
        return;
    }
    float3 Position = VolumeWorldPosition(float2(Cell.xy), float(Cell.z) + 0.5f);
    float3 ToCamera = VolumeSafeDirection(Camera.xyz - Position);
    float4 Coefficients = Medium.Load(int4(Cell, 0));
    float3 Incoming = LightColor.rgb * VolumePhase(VolumeSafeDirection(LightDirection.xyz), ToCamera) *
        VolumeDirectionalVisibility(Position);
    for (uint Index = 0; Index < min(uint(LocalCounts.x), 8u); ++Index)
    {
        LocalLightConstants Light = LocalLights[Index];
        float3 ToLight = Light.PositionRange.xyz - Position;
        float DistanceSquared = dot(ToLight, ToLight);
        float Distance = sqrt(max(DistanceSquared, 0));
        if (Distance >= Light.PositionRange.w)
        {
            continue;
        }
        ToLight = VolumeSafeDirection(ToLight);
        float Attenuation = pow(saturate(1 - pow(Distance / Light.PositionRange.w, 4)), 2) / max(DistanceSquared, 0.0001f);
        if (Light.DirectionType.w > 0.5f)
        {
            float3 ConeOffset = -ToLight - Light.DirectionType.xyz;
            Attenuation *= 1 - smoothstep(Light.ConeShadow.x, Light.ConeShadow.y, dot(ConeOffset, ConeOffset));
        }
        // Incoming radiance remains binary32 until the medium coefficient is
        // applied. Bright lights can still produce a small source in thin fog.
        Incoming += min(Light.ColorIntensity.rgb, 1.0e20) * Attenuation * VolumePhase(ToLight, ToCamera) *
            VolumeLocalVisibility(Light, Position);
    }
    float3 Source = VolumeColor((Coefficients.rgb * Incoming + Emission.Load(int4(Cell, 0)).rgb) * ExposureState[0].x);
    OutputSource[Cell] = float4(Source, Coefficients.a);
}

#elif defined(VOLUME_INTEGRATE_STAGE)
Texture3D<float4> Source : register(t0);
RWTexture3D<float4> OutputIntegral : register(u0);

[numthreads(8, 8, 1)]
void IntegrateCS(uint3 Thread : SV_DispatchThreadID)
{
    if (Thread.x >= uint(Grid.x) || Thread.y >= uint(Grid.y))
    {
        return;
    }
    float3 Accumulated = float3(0, 0, 0);
    float Transmittance = 1;
    // Extend the first froxel's coefficients to the camera so the near clip
    // plane does not remove the intervening optical path.
    float3 Previous = Camera.xyz;
    for (uint Slice = 0; Slice < uint(Grid.z); ++Slice)
    {
        float3 Next = VolumeWorldPosition(float2(Thread.xy), float(Slice + 1));
        // Optical length is measured along the oblique world-space camera ray.
        float Distance = length(Next - Previous);
        float4 Coefficients = Source.Load(int4(Thread.xy, Slice, 0));
        VolumeIntegral R;
        VolumeIntegral G;
        VolumeIntegral B;
        R.Scatter = G.Scatter = B.Scatter = 0;
        R.Transmittance = G.Transmittance = B.Transmittance = 1;
        VolumeIntegrateSegment(Coefficients.r, Coefficients.a, Distance, R);
        VolumeIntegrateSegment(Coefficients.g, Coefficients.a, Distance, G);
        VolumeIntegrateSegment(Coefficients.b, Coefficients.a, Distance, B);
        Accumulated = VolumeColor(Accumulated + Transmittance * float3(R.Scatter, G.Scatter, B.Scatter));
        Transmittance *= R.Transmittance;
        OutputIntegral[uint3(Thread.xy, Slice)] = float4(Accumulated, Transmittance);
        Previous = Next;
    }
}
#endif
