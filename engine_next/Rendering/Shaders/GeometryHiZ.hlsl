// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
Texture2D<float> SourceDepth : register(t0);
RWTexture2D<float> DestinationDepth : register(u0);

[numthreads(8, 8, 1)]
void CopyDepthCS(uint3 Thread : SV_DispatchThreadID)
{
    uint Width, Height, SourceWidth, SourceHeight;
    DestinationDepth.GetDimensions(Width, Height);
    SourceDepth.GetDimensions(SourceWidth, SourceHeight);
    if (Thread.x >= Width || Thread.y >= Height)
    {
        return;
    }
    DestinationDepth[Thread.xy] = Thread.x < SourceWidth && Thread.y < SourceHeight ?
        SourceDepth.Load(int3(Thread.xy, 0)) : 0;
}

[numthreads(8, 8, 1)]
void ReduceDepthCS(uint3 Thread : SV_DispatchThreadID)
{
    uint Width, Height, SourceWidth, SourceHeight;
    DestinationDepth.GetDimensions(Width, Height);
    SourceDepth.GetDimensions(SourceWidth, SourceHeight);
    if (Thread.x >= Width || Thread.y >= Height)
    {
        return;
    }
    uint2 First = Thread.xy * 2;
    uint2 Last = uint2(SourceWidth, SourceHeight) - 1;
    float A = SourceDepth.Load(int3(min(First, Last), 0));
    float B = SourceDepth.Load(int3(min(First + uint2(1, 0), Last), 0));
    float C = SourceDepth.Load(int3(min(First + uint2(0, 1), Last), 0));
    float D = SourceDepth.Load(int3(min(First + uint2(1, 1), Last), 0));
    DestinationDepth[Thread.xy] = min(min(A, B), min(C, D));
}
