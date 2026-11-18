// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
float3 UnitDirection(float3 Direction, float3 Fallback)
{
    float Maximum = max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z)));
    float3 Scaled = Direction / max(Maximum, 1.0e-38);
    return Maximum > 0 ? Scaled * rsqrt(max(dot(Scaled, Scaled), 1.0e-38)) : Fallback;
}
#include "ShadowSampling.hlsli"
#if defined(VIRTUAL_SHADOW_STAGE)
#include "ShadowPageReceiver.hlsli"
#endif
#if defined(MATERIAL_EXTENSION_STAGE)
#include "MaterialEnvironmentLighting.hlsli"
#endif
#if defined(ENGINE_NEXT_GI)
#include "GiReceiver.hlsli"
#endif
struct LocalLightConstants
{
    float4 PositionRange;
    float4 ColorIntensity;
    float4 DirectionType;
    float4 ConeShadow;
    float4 ShadowParameters;
};
cbuffer FrameConstants : register(b1)
{
    column_major float4x4 ViewProjection;
    column_major float4x4 InverseViewProjection;
    float4 Camera;
    float4 Lighting;
    column_major float4x4 View;
    column_major float4x4 ShadowViewProjection[4];
    float4 CascadeSplits;
    float4 LightDirection;
    float4 LightColor;
    float4 ShadowParameters;
    column_major float4x4 LocalShadowMatrices[28];
    LocalLightConstants LocalLights[8];
    float4 LocalCounts;
    column_major float4x4 UnjitteredViewProjection;
    column_major float4x4 PreviousViewProjection;
};
StructuredBuffer<float4> ExposureState : register(t11);
#if defined(AMBIENT_OCCLUSION_STAGE)
Texture2D<float> AmbientVisibility : register(t31);
#endif
#if defined(GEOMETRY_STAGE)
cbuffer DrawConstants : register(b0)
{
    column_major float4x4 World;
    column_major float4x4 NormalWorld;
    float4 BaseColor;
    float4 EmissiveMetallic;
    float4 Surface;
    float4 Flags;
    column_major float4x4 PreviousWorld;
    uint4 TemporalMetadata;
    float4 MaterialParameters;
};
Texture2D<float4> BaseTexture : register(t0);
Texture2D<float4> MrTexture : register(t1);
Texture2D<float4> NormalTexture : register(t2);
Texture2D<float4> AoTexture : register(t3);
Texture2D<float4> EmissiveTexture : register(t4);
SamplerState BaseSampler : register(s0);
SamplerState MrSampler : register(s1);
SamplerState NormalSampler : register(s2);
SamplerState AoSampler : register(s3);
SamplerState EmissiveSampler : register(s4);
struct VertexInput
{
    float3 Position : POSITION;
    float3 Normal : NORMAL;
    float4 Tangent : TANGENT;
    float2 Texcoord : TEXCOORD;
#if defined(ANIMATION_STAGE)
    float3 PreviousPosition : PREVPOSITION;
#endif
};
struct VertexOutput
{
    float4 Position : SV_POSITION;
    float3 Normal : NORMAL;
    float4 Tangent : TANGENT;
    float2 Texcoord : TEXCOORD;
    float4 CurrentClip : TEXCOORD1;
    float4 PreviousClip : TEXCOORD2;
};
VertexOutput VSMain(VertexInput Input)
{
    VertexOutput Output;
    float4 Position = mul(World, float4(Input.Position, 1));
    Output.Position = mul(ViewProjection, Position);
    Output.CurrentClip = mul(UnjitteredViewProjection, Position);
#if defined(ANIMATION_STAGE)
    Output.PreviousClip = mul(PreviousViewProjection, mul(PreviousWorld, float4(Input.PreviousPosition, 1)));
#else
    Output.PreviousClip = mul(PreviousViewProjection, mul(PreviousWorld, float4(Input.Position, 1)));
#endif
    Output.Normal = UnitDirection(mul((float3x3)NormalWorld, Input.Normal), float3(0, 0, 1));
    Output.Tangent = float4(UnitDirection(mul((float3x3)World, Input.Tangent.xyz), float3(1, 0, 0)), Input.Tangent.w * Flags.y);
    Output.Texcoord = Input.Texcoord;
    return Output;
}
struct GBufferOutput
{
    float4 Base : SV_TARGET0;
    float4 Normal : SV_TARGET1;
    float4 Surface : SV_TARGET2;
    float4 Emissive : SV_TARGET3;
    float4 Motion : SV_TARGET4;
    uint ObjectId : SV_TARGET5;
#if defined(MATERIAL_EXTENSION_STAGE)
    float4 Material : SV_TARGET6;
    float4 Tangent : SV_TARGET7;
#endif
};
GBufferOutput PSMain(VertexOutput Input, bool Front : SV_IsFrontFace)
{
    GBufferOutput Output;
    float4 Color = BaseTexture.Sample(BaseSampler, Input.Texcoord) * BaseColor;
    if (Flags.x > 0.5)
    {
        clip(Color.a - Surface.w);
    }
    float3 Normal = UnitDirection(Input.Normal, float3(0, 0, 1)) * (Front ? 1 : -1);
    float3 TangentVector = Input.Tangent.xyz - Normal * dot(Input.Tangent.xyz, Normal);
    float3 TangentAxis = abs(Normal.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0);
    float3 Tangent = dot(TangentVector, TangentVector) > 0.00000001 ? normalize(TangentVector) : normalize(cross(TangentAxis, Normal));
    float3 Bitangent = normalize(cross(Normal, Tangent)) * Input.Tangent.w;
    float3 Mapped = Flags.z > 0.5 ? NormalTexture.Sample(NormalSampler, Input.Texcoord).xyz * 2 - 1 : float3(0, 0, 1);
    float NormalScale = max(abs(Surface.y), 1);
    Mapped = float3(Mapped.xy * (Surface.y / NormalScale), Mapped.z / NormalScale);
    Mapped = UnitDirection(Mapped, float3(0, 0, 1));
    float3 MappedWorld = Tangent * Mapped.x + Bitangent * Mapped.y + Normal * Mapped.z;
    Normal = UnitDirection(MappedWorld, Normal);
    float4 Mr = MrTexture.Sample(MrSampler, Input.Texcoord);
    float Ao = lerp(1, AoTexture.Sample(AoSampler, Input.Texcoord).r, Surface.z);
    Output.Motion = 0;
    if (TemporalMetadata.y != 0 && Input.CurrentClip.w > 0 && Input.PreviousClip.w > 0 &&
        all(isfinite(Input.CurrentClip)) && all(isfinite(Input.PreviousClip)))
    {
        float2 CurrentUv = Input.CurrentClip.xy / Input.CurrentClip.w * float2(0.5, -0.5) + 0.5;
        float2 PreviousUv = Input.PreviousClip.xy / Input.PreviousClip.w * float2(0.5, -0.5) + 0.5;
        Output.Motion = float4(PreviousUv - CurrentUv, Input.PreviousClip.w, 1);
    }
    Output.ObjectId = TemporalMetadata.x;
#if defined(MATERIAL_EXTENSION_STAGE)
    Output.Material = MaterialParameters;
    Output.Tangent = Input.Tangent;
#endif
    Output.Base = Color;
    Output.Normal = float4(Normal, 1);
    Output.Surface = float4(saturate(Mr.g * Surface.x), saturate(Mr.b * EmissiveMetallic.w), saturate(Ao), 1);
    float3 Emissive = EmissiveTexture.Sample(EmissiveSampler, Input.Texcoord).rgb * EmissiveMetallic.xyz * ExposureState[0].x;
    Output.Emissive = float4(all(isfinite(Emissive)) ? clamp(Emissive, 0, 65504) : float3(0, 0, 0), 1);
    return Output;
}
#else
#if defined(TONEMAP_STAGE)
Texture2D<float4> HdrBuffer : register(t0);
Texture2D<float4> BloomBuffer : register(t1);
StructuredBuffer<float4> PreviousExposure : register(t2);
StructuredBuffer<float4> CurrentExposure : register(t3);
SamplerState BloomSampler : register(s0);
#else
Texture2D<float4> BaseBuffer : register(t0);
Texture2D<float4> NormalBuffer : register(t1);
Texture2D<float4> SurfaceBuffer : register(t2);
Texture2D<float4> EmissiveBuffer : register(t3);
Texture2D<float> DepthBuffer : register(t4);
StructuredBuffer<float4> Tint : register(t5);
TextureCube<float4> Irradiance : register(t6);
TextureCube<float4> PrefilteredEnvironment : register(t7);
Texture2D<float4> BrdfLut : register(t8);
Texture2DArray<float> DirectionalShadow : register(t9);
Texture2DArray<float> LocalShadow : register(t10);
#if defined(MATERIAL_EXTENSION_STAGE)
Texture2D<float4> MaterialBuffer : register(t12);
Texture2D<float4> TangentBuffer : register(t13);
#endif
SamplerState EnvironmentSampler : register(s0);
#endif
struct FullscreenOutput
{
    float4 Position : SV_POSITION;
    float2 Texcoord : TEXCOORD;
};
FullscreenOutput FullscreenVS(uint Id : SV_VertexID)
{
    FullscreenOutput Output;
    Output.Texcoord = float2((Id << 1) & 2, Id & 2);
    Output.Position = float4(Output.Texcoord * float2(2, -2) + float2(-1, 1), 0, 1);
    return Output;
}
#if defined(TONEMAP_STAGE)
float4 ToneMapPS(FullscreenOutput Input) : SV_TARGET
{
    float3 Color = HdrBuffer.Load(int3(int2(Input.Position.xy), 0)).rgb;
    [branch] if (Lighting.w > 0)
    {
        Color += BloomBuffer.SampleLevel(BloomSampler, Input.Texcoord, 0).rgb * Lighting.w;
    }
    float Ratio = CurrentExposure[0].x / max(PreviousExposure[0].x, 1.175494351e-38);
    Color = 1 - exp(-max(Color, 0) * Ratio);
    return float4(pow(saturate(Color), 1.0 / 2.2), 1);
}
#else
float3 SafeDirection(float3 Direction)
{
    return UnitDirection(Direction, float3(0, 0, 1));
}
float3 Fresnel(float Cosine, float3 F0)
{
    return F0 + (1 - F0) * pow(saturate(1 - Cosine), 5);
}
float3 EvaluateLight(float3 Base, float Metallic, float Roughness, float3 N, float3 V, float3 L, float3 Radiance)
{
    float3 H = SafeDirection(V + L);
    float NoL = saturate(dot(N, L));
    float NoV = max(saturate(dot(N, V)), 0.001);
    float NoH = saturate(dot(N, H));
    float VoH = saturate(dot(V, H));
    float Alpha = max(Roughness * Roughness, 0.0025);
    float A2 = Alpha * Alpha;
    float D = A2 / max(3.14159265 * pow(NoH * NoH * (A2 - 1) + 1, 2), 0.00001);
    float K = pow(Roughness + 1, 2) / 8;
    float G = NoV / (NoV * (1 - K) + K) * NoL / max(NoL * (1 - K) + K, 0.0001);
    float3 F = Fresnel(VoH, lerp(0.04, Base, Metallic));
    float3 Specular = D * G * F / max(4 * NoV * NoL, 0.0001);
    return ((1 - F) * (1 - Metallic) * Base / 3.14159265 + Specular) * Radiance * NoL;
}
float SampleCascadeShadow(float3 Position, float3 N, float3 GeometricNormal, uint Cascade)
{
#if defined(VIRTUAL_SHADOW_STAGE)
    float PageVisibility;
    if (SampleVirtualShadow(Position, N, GeometricNormal, Cascade, ShadowParameters.w, ShadowParameters.z, PageVisibility))
    {
        return PageVisibility;
    }
#endif
    float4 ShadowPosition = mul(ShadowViewProjection[Cascade], float4(Position + N * ShadowParameters.w, 1));
    float3 Projected = ShadowPosition.xyz / ShadowPosition.w;
    float2 Gradient = ShadowReceiverGradient(ShadowViewProjection[Cascade][0].xyz,
        ShadowViewProjection[Cascade][1].xyz, ShadowViewProjection[Cascade][2].xyz, GeometricNormal);
    return SampleShadowMap(DirectionalShadow, Projected, Cascade, round(1 / ShadowParameters.y),
        ShadowParameters.z, 0, float2(0, 0), true, false, 6, float3(0, 0, 0), Gradient);
}
float DirectionalVisibility(float3 Position, float3 N, float3 GeometricNormal)
{
    float Distance = -mul(View, float4(Position, 1)).z;
    if (ShadowParameters.x < 0.5 || Distance > CascadeSplits.w)
    {
        return 1;
    }
    uint Cascade = Distance > CascadeSplits.x ? 1 : 0;
    Cascade = Distance > CascadeSplits.y ? 2 : Cascade;
    Cascade = Distance > CascadeSplits.z ? 3 : Cascade;
    float Visibility = SampleCascadeShadow(Position, N, GeometricNormal, Cascade);
    if (Cascade < 3)
    {
        float Start = Cascade == 0 ? 0 : CascadeSplits[Cascade - 1];
        float Width = (CascadeSplits[Cascade] - Start) * Lighting.z;
        float Blend = saturate((Distance - (CascadeSplits[Cascade] - Width)) / max(Width, 0.001));
        if (Blend > 0)
        {
            Visibility = lerp(Visibility, SampleCascadeShadow(Position, N, GeometricNormal, Cascade + 1), Blend);
        }
    }
    return Visibility;
}
float LocalVisibility(LocalLightConstants Light, float3 Position, float3 N, float3 GeometricNormal)
{
    if (ShadowParameters.x < 0.5 || Light.ConeShadow.z < 0)
    {
        return 1;
    }
    float3 BiasedPosition = Position + N * ShadowParameters.w;
    uint Slice = (uint)Light.ConeShadow.z;
    uint Face = 6;
    if (Light.DirectionType.w < 0.5)
    {
        Face = ShadowCubeFace(BiasedPosition - Light.PositionRange.xyz);
        Slice += Face;
    }
    float4 ShadowPosition = mul(LocalShadowMatrices[Slice], float4(BiasedPosition, 1));
    if (ShadowPosition.w <= 0)
    {
        return 1;
    }
    return SampleShadowMap(LocalShadow, ShadowPosition.xyz / ShadowPosition.w, Slice,
        LocalCounts.z, ShadowParameters.z, Light.ShadowParameters.z,
        Light.ShadowParameters.xy, false, LocalCounts.w > 0.5, Face, GeometricNormal);
}
#if defined(REFLECTION_STAGE)
struct LightingOutput
{
    float4 Base : SV_TARGET0;
    float4 EnvironmentSpecular : SV_TARGET1;
};
LightingOutput LightingPS(FullscreenOutput Input)
#else
float4 LightingPS(FullscreenOutput Input) : SV_TARGET
#endif
{
    int2 Pixel = int2(Input.Position.xy);
    float Depth = DepthBuffer.Load(int3(Pixel, 0));
    float2 Ndc = Input.Texcoord * float2(2, -2) + float2(-1, 1);
    float4 WorldPosition = mul(InverseViewProjection, float4(Ndc, Depth, 1));
    float3 Position = WorldPosition.xyz / WorldPosition.w;
    float3 PlaneNormal = cross(ddx(Position), ddy(Position));
    if (Depth <= 0)
    {
        float4 FarPosition = mul(InverseViewProjection, float4(Ndc, 0, 1));
        float3 Direction = normalize(FarPosition.xyz - Camera.xyz * FarPosition.w);
        float3 Sky = PrefilteredEnvironment.SampleLevel(EnvironmentSampler, Direction, 0).rgb;
        Sky *= ExposureState[0].x;
#if defined(REFLECTION_STAGE)
        LightingOutput Output;
        Output.Base = float4(all(isfinite(Sky)) ? clamp(Sky, 0, 65504) : float3(0, 0, 0), 1);
        Output.EnvironmentSpecular = 0;
        return Output;
#else
        return float4(all(isfinite(Sky)) ? clamp(Sky, 0, 65504) : float3(0, 0, 0), 1);
#endif
    }
    float3 Base = BaseBuffer.Load(int3(Pixel, 0)).rgb;
    float3 N = normalize(NormalBuffer.Load(int3(Pixel, 0)).xyz);
    float3 Material = SurfaceBuffer.Load(int3(Pixel, 0)).rgb;
    float3 Emissive = EmissiveBuffer.Load(int3(Pixel, 0)).rgb;
    float3 GeometricNormal = UnitDirection(PlaneNormal, N);
    float3 V = SafeDirection(Camera.xyz - Position);
#if defined(MATERIAL_EXTENSION_STAGE)
    float4 Extension = MaterialBuffer.Load(int3(Pixel, 0));
    float4 Tangent = TangentBuffer.Load(int3(Pixel, 0));
    MaterialFrame Frame = MaterialBuildFrame(N, Tangent.xyz, Tangent.w, Extension.w);
    float3 Color = MaterialShadeLight(Base, Material.y, Material.x, Extension.z, Extension.x, Extension.y,
        true, Frame, V, LightDirection.xyz, LightColor.rgb * Tint[0].rgb) * DirectionalVisibility(Position, N, GeometricNormal);
#else
    float3 Color = EvaluateLight(Base, Material.y, Material.x, N, V, LightDirection.xyz, LightColor.rgb * Tint[0].rgb) * DirectionalVisibility(Position, N, GeometricNormal);
#endif
    [loop] for (uint LightIndex = 0; LightIndex < (uint)LocalCounts.x; ++LightIndex)
    {
        LocalLightConstants Light = LocalLights[LightIndex];
        float3 LightVector = Light.PositionRange.xyz - Position;
        float Distance2 = dot(LightVector, LightVector);
        float Distance = sqrt(max(Distance2, 0));
        if (Distance >= Light.PositionRange.w)
        {
            continue;
        }
        float3 Direction = SafeDirection(LightVector);
        float Attenuation = pow(saturate(1 - pow(Distance / Light.PositionRange.w, 4)), 2) / max(Distance2, 0.0001);
        if (Light.DirectionType.w > 0.5)
        {
            float3 ConeOffset = -Direction - Light.DirectionType.xyz;
            float ChordSquared = dot(ConeOffset, ConeOffset);
            Attenuation *= 1 - smoothstep(Light.ConeShadow.x, Light.ConeShadow.y, ChordSquared);
        }
        float Visibility = LocalVisibility(Light, Position, N, GeometricNormal);
        float3 Radiance = min(Light.ColorIntensity.rgb, 1.0e20) * Attenuation;
#if defined(MATERIAL_EXTENSION_STAGE)
        Color += MaterialShadeLight(Base, Material.y, Material.x, Extension.z, Extension.x, Extension.y,
            true, Frame, V, Direction, Radiance) * Visibility;
#else
        Color += EvaluateLight(Base, Material.y, Material.x, N, V, Direction, Radiance) * Visibility;
#endif
    }
    float NoV = saturate(dot(N, V));
    float3 F0 = lerp(0.04, Base, Material.y);
    float3 F = F0 + (max(1 - Material.x, F0) - F0) * pow(1 - NoV, 5);
    float3 Diffuse = Irradiance.SampleLevel(EnvironmentSampler, N, 0).rgb * Base / 3.14159265;
    float3 Reflection = reflect(-V, N);
    float3 Prefiltered = PrefilteredEnvironment.SampleLevel(EnvironmentSampler, Reflection, Material.x * Lighting.y).rgb;
    float2 Brdf = BrdfLut.SampleLevel(EnvironmentSampler, float2(NoV, Material.x), 0).rg;
    float3 DiffuseEnvironment = (1 - F) * (1 - Material.y) * Diffuse;
    float3 SpecularEnvironment = Prefiltered * (F0 * Brdf.x + Brdf.y);
#if defined(MATERIAL_EXTENSION_STAGE)
    [branch] if (!MaterialEnvironmentUsesLegacy(true, Extension.z, Extension.x))
    {
        MaterialEnvironmentLighting Environment = SampleMaterialEnvironment(PrefilteredEnvironment, EnvironmentSampler,
            Base, Material.y, Material.x, Extension, Frame, V);
        DiffuseEnvironment = Environment.Diffuse;
        SpecularEnvironment = Environment.BaseSpecular + Environment.CoatSpecular;
    }
#endif
#if defined(ENGINE_NEXT_GI)
#if defined(MATERIAL_EXTENSION_STAGE)
    DiffuseEnvironment = GiReceiverDiffuse(DiffuseEnvironment, Position, N, V, Base, Material.y, Material.x, Extension, true);
#else
    DiffuseEnvironment = GiReceiverDiffuse(DiffuseEnvironment, Position, N, V, Base, Material.y, Material.x, float4(0, 0, 0, 0), false);
#endif
#endif
#if defined(AMBIENT_OCCLUSION_STAGE)
    DiffuseEnvironment *= saturate(AmbientVisibility.Load(int3(Pixel, 0)));
#endif
#if defined(REFLECTION_STAGE)
    Color += DiffuseEnvironment * Material.z;
    float3 EnvironmentSpecular = SpecularEnvironment * Material.z * ExposureState[0].x;
    Color = Color * ExposureState[0].x + Emissive;
    LightingOutput Output;
    Output.Base = float4(all(isfinite(Color)) ? clamp(Color, 0, 65504) : float3(0, 0, 0), 1);
    Output.EnvironmentSpecular = float4(all(isfinite(EnvironmentSpecular)) ? clamp(EnvironmentSpecular, 0, 65504) : float3(0, 0, 0), 1);
    return Output;
#else
    Color += (DiffuseEnvironment + SpecularEnvironment) * Material.z;
    Color = Color * ExposureState[0].x + Emissive;
    return float4(all(isfinite(Color)) ? clamp(Color, 0, 65504) : float3(0, 0, 0), 1);
#endif
}
#endif

#endif
