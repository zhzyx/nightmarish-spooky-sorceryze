// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_MATERIAL_ENVIRONMENT_LIGHTING
#define ENGINE_NEXT_MATERIAL_ENVIRONMENT_LIGHTING

#include "MaterialEnvironment.hlsli"
#if defined(ENVIRONMENT_IMPORTANCE_STAGE)
#include "EnvironmentImportance.hlsli"
StructuredBuffer<EnvironmentAliasEntry> EnvironmentAlias : register(t15);
#endif

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
#if defined(ENVIRONMENT_IMPORTANCE_STAGE)
    EnvironmentTableInfo Table = ReadEnvironmentTableInfo(EnvironmentAlias);
    MaterialMisCounts Counts;
    Counts.Base = 16;
    Counts.Coat = Extension.x > 0 ? 8 : 0;
    Counts.Diffuse = Metallic < 1 ? 8 : 0;
    Counts.Environment = Table.Valid ? 24 : 0;
    [loop] for (uint Index = 0; Index < Counts.Base; ++Index)
    {
        MaterialEnvironmentSample Sample = MaterialEnvironmentBaseSample(Base, Metallic, Roughness,
            Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, Counts.Base));
        if (Sample.Pdf > 0)
        {
            float Pdf = EnvironmentDirectionPdf(EnvironmentAlias, Table.FaceSize, Table.UniformFallback, Sample.Direction);
            MaterialMisWeights Weights = MaterialImportanceWeights(Base, Metallic, Roughness, Extension.z, Extension.x,
                Extension.y, Frame, V, Sample.Direction, Pdf, Counts);
            Result.BaseSpecular += Environment.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb * Weights.Base;
        }
    }
    [loop] for (uint Index = 0; Index < Counts.Coat; ++Index)
    {
        MaterialEnvironmentSample Sample = MaterialEnvironmentCoatSample(Base, Metallic, Roughness,
            Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, Counts.Coat));
        if (Sample.Pdf > 0)
        {
            float Pdf = EnvironmentDirectionPdf(EnvironmentAlias, Table.FaceSize, Table.UniformFallback, Sample.Direction);
            MaterialMisWeights Weights = MaterialImportanceWeights(Base, Metallic, Roughness, Extension.z, Extension.x,
                Extension.y, Frame, V, Sample.Direction, Pdf, Counts);
            Result.CoatSpecular += Environment.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb * Weights.Coat;
        }
    }
    [loop] for (uint Index = 0; Index < Counts.Diffuse; ++Index)
    {
        MaterialEnvironmentSample Sample = MaterialEnvironmentDiffuseSample(Base, Metallic, Roughness,
            Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, Counts.Diffuse));
        float Pdf = EnvironmentDirectionPdf(EnvironmentAlias, Table.FaceSize, Table.UniformFallback, Sample.Direction);
        MaterialMisWeights Weights = MaterialImportanceWeights(Base, Metallic, Roughness, Extension.z, Extension.x,
            Extension.y, Frame, V, Sample.Direction, Pdf, Counts);
        Result.Diffuse += Environment.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb * Weights.Diffuse;
    }
    [loop] for (uint Index = 0; Index < Counts.Environment; ++Index)
    {
        EnvironmentDirectionSample Sample = SampleEnvironmentDirection(EnvironmentAlias, Table.FaceSize, Table.UniformFallback,
            MaterialEnvironmentCoordinates(Index, Counts.Environment));
        MaterialMisWeights Weights = MaterialImportanceWeights(Base, Metallic, Roughness, Extension.z, Extension.x,
            Extension.y, Frame, V, Sample.Direction, Sample.Pdf, Counts);
        float3 Radiance = Environment.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb;
        Result.BaseSpecular += Radiance * Weights.Base;
        Result.CoatSpecular += Radiance * Weights.Coat;
        Result.Diffuse += Radiance * Weights.Diffuse;
    }
#else
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
#endif
    return Result;
}

#endif
