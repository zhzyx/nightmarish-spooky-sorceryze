// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
cbuffer Display : register(b2)
{
    uint2 Extent;
    uint Candidates;
    uint Reserved;
};

#if VIEW == 14
Texture2DArray<float> Source : register(t0);
#elif VIEW == 18
Texture3D<float4> Source : register(t0);
#elif (VIEW >= 10 && VIEW <= 16) || VIEW == 19
ByteAddressBuffer Source : register(t0);
#else
Texture2D<float4> Source : register(t0);
#endif

float3 IdColor(uint Id)
{
    uint Hash = Id * 2654435761u;
    return float3(Hash & 255, (Hash >> 8) & 255, (Hash >> 16) & 255) / 255.0;
}

uint GridIndex(float2 Uv, uint Count)
{
    uint Columns = max(1u, (uint)ceil(sqrt((float)Count)));
    uint Rows = max(1u, (Count + Columns - 1) / Columns);
    uint2 Cell = min(uint2(Uv * uint2(Columns, Rows)), uint2(Columns - 1, Rows - 1));
    return Cell.y * Columns + Cell.x;
}

float4 DiagnosticPS(float4 Position : SV_Position) : SV_Target
{
    float2 Uv = Position.xy / Extent;
    float3 Color = 0;
#if VIEW == 14
    uint W, H, Layers;
    Source.GetDimensions(W, H, Layers);
    float2 Tile = Uv * 2;
    uint Layer = (uint)Tile.x + 2 * (uint)Tile.y;
    if (Layer < Layers)
        Color = Source.Load(int4(uint2(frac(Tile) * uint2(W, H)), Layer, 0)).xxx;
#elif VIEW == 18
    uint W, H, D;
    Source.GetDimensions(W, H, D);
    float4 Integral = Source.Load(int4(uint2(Uv * uint2(W, H)), D - 1, 0));
    Color = Integral.rgb / (1 + abs(Integral.rgb)) + (1 - saturate(Integral.a)) * 0.25;
#elif VIEW == 10
    // Per-bucket emitted command counts after color culling, plus overflow and invalid input.
    uint Bytes;
    Source.GetDimensions(Bytes);
    uint Index = GridIndex(Uv, Bytes / 4);
    if (Index < Bytes / 4)
        Color = (log2(1.0 + Source.Load(Index * 4)) / 16).xxx;
#elif VIEW >= 11 && VIEW <= 13
    uint Index = GridIndex(Uv, Candidates);
    if (Index < Candidates)
    {
        uint4 Metadata = Source.Load4(Index * 64 + 48);
#if VIEW == 11
        // One tile per uploaded cluster, colored by its draw and material bucket.
        uint Draw = Source.Load(Index * 64 + 44);
        uint IndexCount = Source.Load(Index * 64 + 32);
        Color = IdColor(1 + Draw * 257u + Metadata.x) * saturate(log2(1 + (float)IndexCount) / 8);
#elif VIEW == 12
        Color = Metadata.z == 0 ? 0 : (Metadata.w == 0 ? float3(0, 0.8, 0.2) : float3(1, 0.4, 0));
#else
        Color = IdColor(1 + Metadata.y);
#endif
    }
#elif VIEW == 15
    uint Bytes;
    Source.GetDimensions(Bytes);
    uint Index = GridIndex(Uv, Bytes / 32);
    if (Index < Bytes / 32)
    {
        uint PhysicalPlusOne = Source.Load(Index * 32);
        Color = PhysicalPlusOne == 0 ? 0 : IdColor(PhysicalPlusOne);
    }
#elif VIEW == 16
    uint Bytes;
    Source.GetDimensions(Bytes);
    uint Index = GridIndex(Uv, Bytes / 144);
    if (Index < Bytes / 144)
    {
        float3 Dc = max(asfloat(Source.Load3(Index * 144)), 0);
        Color = Dc / (1 + Dc);
    }
#elif VIEW == 19
    float4 State = asfloat(Source.Load4(0));
    uint Channel = min(3u, (uint)(Uv.x * 4));
    float Stops = Channel < 2 ? log2(max(State[Channel], 0.000001)) : State[Channel];
    Color = Uv.y > 1 - saturate(0.5 + Stops / 32) ? float3(0.7, 0.85, 1) : 0;
#else
    uint W, H;
    Source.GetDimensions(W, H);
    float4 Value = Source.Load(int3(uint2(Uv * uint2(W, H)), 0));
#if VIEW == 2
    Color = Value.xyz * 0.5 + 0.5;
#elif VIEW == 3 || VIEW == 8
    Color = Value.rrr;
#elif VIEW == 4
    Color = Value.ggg;
#elif VIEW == 5
    Color = Value.bbb;
#elif VIEW == 7
    Color = float3(0.5 + Value.xy * 8, Value.w);
#elif VIEW == 6 || VIEW == 17
    Color = Value.rgb / (1 + abs(Value.rgb));
#else
    Color = Value.rgb;
#endif
#endif
    return float4(saturate(Color), 1);
}
