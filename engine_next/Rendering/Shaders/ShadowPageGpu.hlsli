// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_SHADOW_PAGE_GPU_HLSLI
#define ENGINE_NEXT_SHADOW_PAGE_GPU_HLSLI

cbuffer ShadowPageConstants : register(b5)
{
    column_major float4x4 PageInverseViewProjection;
    column_major float4x4 PageView;
    column_major float4x4 PageShadowProjection[4];
    float4 PageSplits;
    uint4 PageDimensions;
    float4 PageViewport;
};

struct ShadowPageEntry
{
    uint PhysicalPlusOne;
    uint3 Reserved;
    float4 DepthPlane;
};

#endif
