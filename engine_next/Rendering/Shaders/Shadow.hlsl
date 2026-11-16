// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
cbuffer DrawConstants : register(b0)
{
    column_major float4x4 World;
    column_major float4x4 NormalWorld;
    float4 BaseColor;
    float4 EmissiveMetallic;
    float4 Surface;
    float4 Flags;
};
cbuffer ShadowConstants : register(b2)
{
    column_major float4x4 ShadowViewProjection;
};
Texture2D<float4> BaseTexture : register(t0);
SamplerState BaseSampler : register(s0);
struct ShadowVertexInput
{
    float3 Position : POSITION;
    float2 Texcoord : TEXCOORD;
};
struct ShadowVertexOutput
{
    float4 Position : SV_POSITION;
    float2 Texcoord : TEXCOORD;
};
ShadowVertexOutput ShadowVS(ShadowVertexInput Input)
{
    ShadowVertexOutput Output;
    Output.Position = mul(ShadowViewProjection, mul(World, float4(Input.Position, 1)));
    Output.Texcoord = Input.Texcoord;
    return Output;
}
void ShadowPS(ShadowVertexOutput Input)
{
    if (Flags.x > 0.5)
    {
        float Alpha = BaseTexture.Sample(BaseSampler, Input.Texcoord).a * BaseColor.a;
        clip(Alpha - Surface.w);
    }
}
