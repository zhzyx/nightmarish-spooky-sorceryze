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
cbuffer FrameConstants : register(b1)
{
    column_major float4x4 ViewProjection;
};
Texture2D<float4> BaseTexture : register(t0);
SamplerState BaseSampler : register(s0);
struct DepthInput
{
    float3 Position : POSITION;
    float2 Texcoord : TEXCOORD;
};
struct DepthOutput
{
    float4 Position : SV_Position;
    float2 Texcoord : TEXCOORD;
};
DepthOutput DepthVS(DepthInput Input)
{
    DepthOutput Output;
    Output.Position = mul(ViewProjection, mul(World, float4(Input.Position, 1)));
    Output.Texcoord = Input.Texcoord;
    return Output;
}
void DepthPS(DepthOutput Input)
{
    if (Flags.x > 0.5)
    {
        clip(BaseTexture.Sample(BaseSampler, Input.Texcoord).a * BaseColor.a - Surface.w);
    }
}
