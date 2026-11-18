// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
cbuffer ScreenEffectsConstants : register(b2)
{
    float4 ScreenViewport;
    float4 ScreenSettings;
};
Texture3D<float4> ColorGradingLut : register(t4);

float3 SharpenHdr(float2 Position, float3 Center)
{
    if (ScreenSettings.x <= 0)
    {
        return Center;
    }
    int2 Pixel = int2(Position);
    int2 Maximum = int2(ScreenViewport.xy) - 1;
    float3 Left = HdrBuffer.Load(int3(clamp(Pixel + int2(-1, 0), 0, Maximum), 0)).rgb;
    float3 Right = HdrBuffer.Load(int3(clamp(Pixel + int2(1, 0), 0, Maximum), 0)).rgb;
    float3 Up = HdrBuffer.Load(int3(clamp(Pixel + int2(0, -1), 0, Maximum), 0)).rgb;
    float3 Down = HdrBuffer.Load(int3(clamp(Pixel + int2(0, 1), 0, Maximum), 0)).rgb;
    float3 Low = min(Center, min(min(Left, Right), min(Up, Down)));
    float3 High = max(Center, max(max(Left, Right), max(Up, Down)));
    float3 Range = High - Low;
    float3 Result = Center + ScreenSettings.x * (Center - (Left + Right + Up + Down) * 0.25);
    return clamp(Result, max(Low - Range * 0.25, 0), min(High + Range * 0.25, 65504));
}

float3 GradeAndVignette(float3 Color, float2 Position)
{
    if (ScreenViewport.w > 0)
    {
        float Size = ScreenViewport.z;
        float3 Coordinate = (saturate(Color) * (Size - 1) + 0.5) / Size;
        float3 Graded = ColorGradingLut.SampleLevel(BloomSampler, Coordinate, 0).rgb;
        Color = lerp(Color, Graded, ScreenViewport.w);
    }
    if (ScreenSettings.y > 0)
    {
        float2 Offset = (Position - ScreenViewport.xy * 0.5) * 2 / min(ScreenViewport.x, ScreenViewport.y);
        float T = saturate((length(Offset) - ScreenSettings.z) / max(ScreenSettings.w - ScreenSettings.z, 1e-6));
        Color *= 1 - ScreenSettings.y * T * T * (3 - 2 * T);
    }
    return Color;
}
