// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_MATERIAL_ENVIRONMENT_LIGHTING
#define ENGINE_NEXT_MATERIAL_ENVIRONMENT_LIGHTING

#include "MaterialEnvironment.hlsli"

struct MaterialEnvironmentLighting
{
    float3 Diffuse;
    float3 BaseSpecular;
    float3 CoatSpecular;
};

MaterialEnvironmentLighting SampleMaterialEnvironment(TextureCube<float4> Environment, SamplerState EnvironmentSampler,
    float3 Base, float Metallic, float Roughness, float4 Extension, MaterialFrame Frame, float3 V)
{
    MaterialEnvironmentLighting Result;
    Result.Diffuse = 0;
    Result.BaseSpecular = 0;
    Result.CoatSpecular = 0;
    [loop] for (uint Index = 0; Index < 32; ++Index)
    {
        MaterialEnvironmentSample Sample = MaterialEnvironmentBaseSample(Base, Metallic, Roughness,
            Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, 32));
        Result.BaseSpecular += Environment.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb * Sample.Weight / 32;
    }
    [branch] if (Extension.x > 0)
    {
        [loop] for (uint Index = 0; Index < 16; ++Index)
        {
            MaterialEnvironmentSample Sample = MaterialEnvironmentCoatSample(Base, Metallic, Roughness,
                Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, 16));
            Result.CoatSpecular += Environment.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb * Sample.Weight / 16;
        }
    }
    [branch] if (Metallic < 1)
    {
        [loop] for (uint Index = 0; Index < 8; ++Index)
        {
            MaterialEnvironmentSample Sample = MaterialEnvironmentDiffuseSample(Base, Metallic, Roughness,
                Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, 8));
            Result.Diffuse += Environment.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb * Sample.Weight / 8;
        }
    }
    return Result;
}

#endif
