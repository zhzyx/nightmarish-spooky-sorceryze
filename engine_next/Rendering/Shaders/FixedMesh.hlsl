// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
cbuffer FrameConstants : register(b0)
{
    float Time;
    float Aspect;
    float CameraX;
    float CameraY;
};

#if defined(COMPUTE_STAGE)
RWStructuredBuffer<float4> OutputTint : register(u0);

[numthreads(1, 1, 1)]
void CSMain(uint3 DispatchId : SV_DispatchThreadID)
{
    OutputTint[0] = float4(0.88 + 0.12 * sin(Time), 0.90, 1.0, 1.0);
}

[numthreads(1, 1, 1)]
void AssetDirectionalTintCS()
{
    OutputTint[0] = float4(1.0, 1.0, 1.0, 1.0);
}
#else
StructuredBuffer<float4> Tint : register(t0);

struct VertexInput
{
    float3 Position : POSITION;
    float3 Normal : NORMAL;
    float3 Color : COLOR;
};

struct VertexOutput
{
    float4 Position : SV_POSITION;
    float3 Normal : NORMAL;
    float3 Color : COLOR;
};

VertexOutput VSMain(VertexInput Input)
{
    VertexOutput Output;
    float Angle = 0.35 + Time * 0.22;
    float Cosine = cos(Angle);
    float Sine = sin(Angle);
    float3 Position = float3(Cosine * Input.Position.x + Sine * Input.Position.z,
        Input.Position.y, -Sine * Input.Position.x + Cosine * Input.Position.z);
    Position += float3(CameraX, CameraY - 0.1, -4.5);
    float Scale = 2.1445069;
    Output.Position = float4(Position.x * Scale / Aspect, Position.y * Scale, 0.05, -Position.z);
    Output.Normal = float3(Cosine * Input.Normal.x + Sine * Input.Normal.z,
        Input.Normal.y, -Sine * Input.Normal.x + Cosine * Input.Normal.z);
    Output.Color = Input.Color;
    return Output;
}

float4 PSMain(VertexOutput Input) : SV_TARGET
{
    float Diffuse = saturate(dot(normalize(Input.Normal), normalize(float3(-0.5, 0.8, 0.6))));
    return float4(Input.Color * Tint[0].rgb * (0.18 + 0.82 * Diffuse), 1.0);
}
#endif
