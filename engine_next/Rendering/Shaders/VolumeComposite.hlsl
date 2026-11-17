// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "VolumeCommon.hlsli"
#include "VolumeSampling.hlsli"

Texture2D<float4> SceneColor : register(t0);
Texture2D<float> SceneDepth : register(t1);
Texture3D<float4> IntegratedVolume : register(t2);
Texture3D<float4> FilteredSource : register(t3);
RWTexture2D<float4> FoggedColor : register(u0);

[numthreads(8, 8, 1)]
void CompositeCS(uint3 Pixel : SV_DispatchThreadID)
{
    if (any(Pixel.xy >= uint2(Viewport.xy)))
    {
        return;
    }
    float2 Uv = (float2(Pixel.xy) + 0.5f) / Viewport.xy;
    float Depth = SceneDepth.Load(int3(Pixel.xy, 0));
    float4 World = mul(InverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), Depth, 1));
    float Distance = Depth <= 0 ? DepthRange.y : -mul(View, float4(World.xyz / World.w, 1)).z;
    float4 Fog = SampleIntegratedFog(IntegratedVolume, FilteredSource, Uv, min(Distance, DepthRange.y), Grid.xyz, DepthRange.xy);
    FoggedColor[Pixel.xy] = float4(VolumeColor(Fog.rgb + Fog.a * SceneColor.Load(int3(Pixel.xy, 0)).rgb), 1);
}
