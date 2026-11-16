// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
float3 UnitDirection(float3 Direction, float3 Fallback)
{
    float Maximum = max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z)));
    float3 Scaled = Direction / max(Maximum, 1.0e-38);
    return Maximum > 0 ? Scaled * rsqrt(max(dot(Scaled, Scaled), 1.0e-38)) : Fallback;
}
cbuffer FrameConstants : register(b1)
{
    column_major float4x4 ViewProjection;
    column_major float4x4 InverseViewProjection;
    float4 Camera;
    float4 Lighting;
};
#if defined(GEOMETRY_STAGE)
cbuffer DrawConstants : register(b0)
{
    column_major float4x4 World;
    column_major float4x4 NormalWorld;
    float4 BaseColor;
    float4 EmissiveMetallic;
    float4 Surface;
    float4 Flags;
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
};
struct VertexOutput
{
    float4 Position : SV_POSITION;
    float3 Normal : NORMAL;
    float4 Tangent : TANGENT;
    float2 Texcoord : TEXCOORD;
};
VertexOutput VSMain(VertexInput Input)
{
    VertexOutput Output;
    float4 Position = mul(World, float4(Input.Position, 1));
    Output.Position = mul(ViewProjection, Position);
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
    Output.Base = Color;
    Output.Normal = float4(Normal, 1);
    Output.Surface = float4(saturate(Mr.g * Surface.x), saturate(Mr.b * EmissiveMetallic.w), saturate(Ao), 1);
    Output.Emissive = float4(EmissiveTexture.Sample(EmissiveSampler, Input.Texcoord).rgb * EmissiveMetallic.xyz, 1);
    return Output;
}
#else
#if defined(TONEMAP_STAGE)
Texture2D<float4> HdrBuffer : register(t0);
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
    Color = 1 - exp(-max(Color, 0) * Lighting.x);
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
float4 LightingPS(FullscreenOutput Input) : SV_TARGET
{
    int2 Pixel = int2(Input.Position.xy);
    float Depth = DepthBuffer.Load(int3(Pixel, 0));
    float2 Ndc = Input.Texcoord * float2(2, -2) + float2(-1, 1);
    if (Depth <= 0)
    {
        float4 FarPosition = mul(InverseViewProjection, float4(Ndc, 0, 1));
        float3 Direction = normalize(FarPosition.xyz - Camera.xyz * FarPosition.w);
        float3 Sky = PrefilteredEnvironment.SampleLevel(EnvironmentSampler, Direction, 0).rgb;
        return float4(max(Sky, 0), 1);
    }
    float3 Base = BaseBuffer.Load(int3(Pixel, 0)).rgb;
    float3 N = normalize(NormalBuffer.Load(int3(Pixel, 0)).xyz);
    float3 Material = SurfaceBuffer.Load(int3(Pixel, 0)).rgb;
    float3 Emissive = EmissiveBuffer.Load(int3(Pixel, 0)).rgb;
    float4 WorldPosition = mul(InverseViewProjection, float4(Ndc, Depth, 1));
    float3 Position = WorldPosition.xyz / WorldPosition.w;
    float3 V = SafeDirection(Camera.xyz - Position);
    float3 Color = EvaluateLight(Base, Material.y, Material.x, N, V, normalize(float3(-0.5, 0.8, 0.6)), float3(3, 2.9, 2.7) * Tint[0].rgb);
    float3 PointVector = float3(2, 3, 2) - Position;
    float Distance2 = max(dot(PointVector, PointVector), 0.01);
    Color += EvaluateLight(Base, Material.y, Material.x, N, V, SafeDirection(PointVector), float3(18, 12, 8) / Distance2);
    float NoV = saturate(dot(N, V));
    float3 F0 = lerp(0.04, Base, Material.y);
    float3 F = F0 + (max(1 - Material.x, F0) - F0) * pow(1 - NoV, 5);
    float3 Diffuse = Irradiance.SampleLevel(EnvironmentSampler, N, 0).rgb * Base / 3.14159265;
    float3 Reflection = reflect(-V, N);
    float3 Prefiltered = PrefilteredEnvironment.SampleLevel(EnvironmentSampler, Reflection, Material.x * Lighting.y).rgb;
    float2 Brdf = BrdfLut.SampleLevel(EnvironmentSampler, float2(NoV, Material.x), 0).rg;
    Color += ((1 - F) * (1 - Material.y) * Diffuse + Prefiltered * (F0 * Brdf.x + Brdf.y)) * Material.z;
    Color += Emissive;
    return float4(max(Color, 0), 1);
}
#endif

#endif
