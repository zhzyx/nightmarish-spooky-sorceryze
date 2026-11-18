// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
float3 UnitDirection(float3 Direction, float3 Fallback)
{
    float Maximum = max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z)));
    float3 Scaled = Direction / max(Maximum, 1.0e-38);
    return Maximum > 0 ? Scaled * rsqrt(max(dot(Scaled, Scaled), 1.0e-38)) : Fallback;
}
#include "ShadowSampling.hlsli"
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

cbuffer TransparencyConstants : register(b2)
{
    // near, far, soft-intersection distance in world units, soft fade enabled.
    float4 Transparency;
};
cbuffer TransparentVolumeConstants : register(b3)
{
    float4 FogGrid;
    float4 FogDepthRange;
    float4 FogViewport;
    float4 FogParameters;
};
Texture2D<float> OpaqueDepth : register(t5);
TextureCube<float4> Irradiance : register(t6);
TextureCube<float4> PrefilteredEnvironment : register(t7);
Texture2D<float4> BrdfLut : register(t8);
Texture2DArray<float> DirectionalShadow : register(t9);
Texture2DArray<float> LocalShadow : register(t10);
SamplerState EnvironmentSampler : register(s5);
Texture3D<float4> FogIntegrated : register(t13);
Texture3D<float4> FogSource : register(t14);
StructuredBuffer<float4> Tint : register(t12);
#include "VolumeSampling.hlsli"

struct VertexInput
{
    float3 Position : POSITION;
    float3 Normal : NORMAL;
    float4 Tangent : TANGENT;
    float2 Texcoord : TEXCOORD;
};
struct VertexOutput
{
    float4 Position : SV_POSITION;
    float3 WorldPosition : TEXCOORD0;
    float3 Normal : TEXCOORD1;
    float4 Tangent : TEXCOORD2;
    float2 Texcoord : TEXCOORD3;
};
VertexOutput VSMain(VertexInput Input)
{
    VertexOutput Output;
    float4 Position = mul(World, float4(Input.Position, 1));
    Output.Position = mul(ViewProjection, Position);
    Output.WorldPosition = Position.xyz;
    Output.Normal = UnitDirection(mul((float3x3)NormalWorld, Input.Normal), float3(0, 0, 1));
    Output.Tangent = float4(UnitDirection(mul((float3x3)World, Input.Tangent.xyz), float3(1, 0, 0)), Input.Tangent.w * Flags.y);
    Output.Texcoord = Input.Texcoord;
    return Output;
}
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
float SampleCascadeShadow(float3 Position, float3 N, uint Cascade)
{
    float4 ShadowPosition = mul(ShadowViewProjection[Cascade], float4(Position + N * ShadowParameters.w, 1));
    float3 Projected = ShadowPosition.xyz / ShadowPosition.w;
    float2 Uv = Projected.xy * float2(0.5, -0.5) + 0.5;
    if (any(Uv < 0) || any(Uv > 1) || Projected.z < 0 || Projected.z > 1)
    {
        return 1;
    }
    int Resolution = (int)round(1 / ShadowParameters.y);
    int2 Center = int2(Uv * Resolution);
    float Visibility = 0;
    [unroll] for (int Y = -1; Y <= 1; ++Y)
    {
        [unroll] for (int X = -1; X <= 1; ++X)
        {
            int2 Pixel = clamp(Center + int2(X, Y), 0, Resolution - 1);
            float Depth = DirectionalShadow.Load(int4(Pixel, Cascade, 0));
            Visibility += Projected.z + ShadowParameters.z >= Depth ? 1 : 0;
        }
    }
    return Visibility / 9;
}
float DirectionalVisibility(float3 Position, float3 N)
{
    float Distance = -mul(View, float4(Position, 1)).z;
    if (ShadowParameters.x < 0.5 || Distance > CascadeSplits.w)
    {
        return 1;
    }
    uint Cascade = Distance > CascadeSplits.x ? 1 : 0;
    Cascade = Distance > CascadeSplits.y ? 2 : Cascade;
    Cascade = Distance > CascadeSplits.z ? 3 : Cascade;
    float Visibility = SampleCascadeShadow(Position, N, Cascade);
    if (Cascade < 3)
    {
        float Start = Cascade == 0 ? 0 : CascadeSplits[Cascade - 1];
        float Width = (CascadeSplits[Cascade] - Start) * Lighting.z;
        float Blend = saturate((Distance - (CascadeSplits[Cascade] - Width)) / max(Width, 0.001));
        if (Blend > 0)
        {
            Visibility = lerp(Visibility, SampleCascadeShadow(Position, N, Cascade + 1), Blend);
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

#include "TransparentMath.hlsli"

float TransparentSoftFade(float2 Pixel, float DeviceDepth)
{
    uint Width;
    uint Height;
    OpaqueDepth.GetDimensions(Width, Height);
    int2 Coordinate = clamp(int2(Pixel), int2(0, 0), int2(Width, Height) - 1);
    float SceneDepth = OpaqueDepth.Load(int3(Coordinate, 0));
    return TransparentDepthFade(SceneDepth, DeviceDepth, Transparency.xy, Transparency.z, Transparency.w > 0.5f);
}

struct TransparentOutput
{
    float4 Color : SV_TARGET0;
    float Reactive : SV_TARGET1;
};
TransparentOutput PSMain(VertexOutput Input, bool Front : SV_IsFrontFace)
{
    float3 PlaneNormal = UnitDirection(cross(ddx(Input.WorldPosition), ddy(Input.WorldPosition)), Input.Normal);
    float4 Base = BaseTexture.Sample(BaseSampler, Input.Texcoord) * BaseColor;
    if (Flags.x > 0.5f)
    {
        clip(Base.a - Surface.w);
    }
    float Alpha = TransparentEffectiveAlpha(Base.a, TransparentSoftFade(Input.Position.xy, Input.Position.z));
    float3 N = UnitDirection(Input.Normal, float3(0, 0, 1)) * (Front ? 1 : -1);
    float3 TangentVector = Input.Tangent.xyz - N * dot(Input.Tangent.xyz, N);
    float3 TangentAxis = abs(N.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0);
    float3 Tangent = dot(TangentVector, TangentVector) > 0.00000001 ? normalize(TangentVector) : normalize(cross(TangentAxis, N));
    float3 Bitangent = normalize(cross(N, Tangent)) * Input.Tangent.w;
    float3 Mapped = Flags.z > 0.5 ? NormalTexture.Sample(NormalSampler, Input.Texcoord).xyz * 2 - 1 : float3(0, 0, 1);
    float NormalScale = max(abs(Surface.y), 1);
    Mapped = UnitDirection(float3(Mapped.xy * (Surface.y / NormalScale), Mapped.z / NormalScale), float3(0, 0, 1));
    N = UnitDirection(Tangent * Mapped.x + Bitangent * Mapped.y + N * Mapped.z, N);
    float4 Mr = MrTexture.Sample(MrSampler, Input.Texcoord);
    float Roughness = saturate(Mr.g * Surface.x);
    float Metallic = saturate(Mr.b * EmissiveMetallic.w);
    float Ao = saturate(lerp(1, AoTexture.Sample(AoSampler, Input.Texcoord).r, Surface.z));
    float3 V = SafeDirection(Camera.xyz - Input.WorldPosition);
#if defined(MATERIAL_EXTENSION_STAGE)
    MaterialFrame Frame = MaterialBuildFrame(N, Input.Tangent.xyz, Input.Tangent.w, MaterialParameters.w);
    float3 Color = MaterialShadeLight(Base.rgb, Metallic, Roughness, MaterialParameters.z, MaterialParameters.x, MaterialParameters.y,
        true, Frame, V, LightDirection.xyz, LightColor.rgb * Tint[0].rgb) * DirectionalVisibility(Input.WorldPosition, N);
#else
    float3 Color = EvaluateLight(Base.rgb, Metallic, Roughness, N, V, LightDirection.xyz, LightColor.rgb * Tint[0].rgb) * DirectionalVisibility(Input.WorldPosition, N);
#endif
    for (uint Index = 0; Index < min(uint(LocalCounts.x), 8u); ++Index)
    {
        LocalLightConstants Light = LocalLights[Index];
        float3 ToLight = Light.PositionRange.xyz - Input.WorldPosition;
        float DistanceSquared = dot(ToLight, ToLight);
        float Distance = sqrt(max(DistanceSquared, 0));
        if (Distance >= Light.PositionRange.w)
        {
            continue;
        }
        ToLight = SafeDirection(ToLight);
        float Attenuation = pow(saturate(1 - pow(Distance / Light.PositionRange.w, 4)), 2) / max(DistanceSquared, 0.0001f);
        if (Light.DirectionType.w > 0.5)
        {
            float3 ConeOffset = -ToLight - Light.DirectionType.xyz;
            Attenuation *= 1 - smoothstep(Light.ConeShadow.x, Light.ConeShadow.y, dot(ConeOffset, ConeOffset));
        }
#if defined(MATERIAL_EXTENSION_STAGE)
        Color += MaterialShadeLight(Base.rgb, Metallic, Roughness, MaterialParameters.z, MaterialParameters.x, MaterialParameters.y,
            true, Frame, V, ToLight, min(Light.ColorIntensity.rgb, 1.0e20) * Attenuation) * LocalVisibility(Light, Input.WorldPosition, N, PlaneNormal);
#else
        Color += EvaluateLight(Base.rgb, Metallic, Roughness, N, V, ToLight, min(Light.ColorIntensity.rgb, 1.0e20) * Attenuation) * LocalVisibility(Light, Input.WorldPosition, N, PlaneNormal);
#endif
    }
    float NoV = saturate(dot(N, V));
    float3 F0 = lerp(0.04, Base.rgb, Metallic);
    float3 F = F0 + (max(1 - Roughness, F0) - F0) * pow(1 - NoV, 5);
    float3 Diffuse = Irradiance.SampleLevel(EnvironmentSampler, N, 0).rgb * Base.rgb / 3.14159265;
    float3 Prefiltered = PrefilteredEnvironment.SampleLevel(EnvironmentSampler, reflect(-V, N), Roughness * Lighting.y).rgb;
    float2 Brdf = BrdfLut.SampleLevel(EnvironmentSampler, float2(NoV, Roughness), 0).rg;
#if defined(ENGINE_NEXT_GI)
    float3 DiffuseEnvironment = (1 - F) * (1 - Metallic) * Diffuse;
    float3 SpecularEnvironment = Prefiltered * (F0 * Brdf.x + Brdf.y);
#else
    float3 EnvironmentLighting = (1 - F) * (1 - Metallic) * Diffuse + Prefiltered * (F0 * Brdf.x + Brdf.y);
#endif
#if defined(MATERIAL_EXTENSION_STAGE)
    [branch] if (!MaterialEnvironmentUsesLegacy(true, MaterialParameters.z, MaterialParameters.x))
    {
        MaterialEnvironmentLighting Environment = SampleMaterialEnvironment(PrefilteredEnvironment, EnvironmentSampler,
            Base.rgb, Metallic, Roughness, MaterialParameters, Frame, V);
#if defined(ENGINE_NEXT_GI)
        DiffuseEnvironment = Environment.Diffuse;
        SpecularEnvironment = Environment.BaseSpecular + Environment.CoatSpecular;
#else
        EnvironmentLighting = Environment.Diffuse + Environment.BaseSpecular + Environment.CoatSpecular;
#endif
    }
#endif
#if defined(ENGINE_NEXT_GI)
#if defined(MATERIAL_EXTENSION_STAGE)
    DiffuseEnvironment = GiReceiverDiffuse(DiffuseEnvironment, Input.WorldPosition, N, V, Base.rgb, Metallic, Roughness, MaterialParameters, true);
#else
    DiffuseEnvironment = GiReceiverDiffuse(DiffuseEnvironment, Input.WorldPosition, N, V, Base.rgb, Metallic, Roughness, float4(0, 0, 0, 0), false);
#endif
    Color += (DiffuseEnvironment + SpecularEnvironment) * Ao;
#else
    Color += EnvironmentLighting * Ao;
#endif
    Color = (Color + EmissiveTexture.Sample(EmissiveSampler, Input.Texcoord).rgb * EmissiveMetallic.xyz) * ExposureState[0].x;
    Color = all(isfinite(Color)) ? clamp(Color, 0, 65504) : float3(0, 0, 0);
    if (FogParameters.w > 0.5f)
    {
        float Distance = -mul(View, float4(Input.WorldPosition, 1)).z;
        float4 Fog = SampleIntegratedFog(FogIntegrated, FogSource, Input.Position.xy / FogViewport.xy,
            min(Distance, FogDepthRange.y), FogGrid.xyz, FogDepthRange.xy);
        Color = Fog.rgb + Fog.a * Color;
    }
    Alpha = isfinite(Alpha) ? Alpha : 0;
    TransparentOutput Output;
    Output.Color = TransparentPremultiply(Color, Alpha);
    Output.Reactive = Alpha;
    return Output;
}
