/**************************************************************************/
/*  EnvironmentImportance.hlsli                                           */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#ifndef ENVIRONMENT_IMPORTANCE_MATH
#define ENVIRONMENT_IMPORTANCE_MATH

#include "MaterialEnvironment.hlsli"

#ifndef ENVIRONMENT_ALIAS_ENTRY_DEFINED
struct EnvironmentAliasEntry
{
	float fThreshold;
	uint nAlias;
	float fPmf;
	uint nMetadata;
};
#endif

struct EnvironmentCubeAddress
{
	float2 Coordinate;
	uint Face;
	bool Valid;
};

struct EnvironmentDirectionSample
{
	float3 Direction;
	float Pdf;
	uint Texel;
};

struct EnvironmentTableInfo
{
	uint FaceSize;
	bool UniformFallback;
	bool Valid;
};

EnvironmentTableInfo ReadEnvironmentTableInfo(StructuredBuffer<EnvironmentAliasEntry> Table)
{
	EnvironmentTableInfo Result;
	Result.FaceSize = 0;
	Result.UniformFallback = true;
	Result.Valid = false;
	uint Count;
	uint Stride;
	Table.GetDimensions(Count, Stride);
	if (Count == 0 || Stride != 16)
	{
		return Result;
	}
	uint Metadata = Table[0].nMetadata;
	uint Size = Metadata >> 1;
	if (Size == 0 || Size > 1672 || Count % 6 != 0 || Count / 6 != Size * Size)
	{
		return Result;
	}
	Result.FaceSize = Size;
	Result.UniformFallback = (Metadata & 1) != 0;
	Result.Valid = true;
	return Result;
}

uint EnvironmentSequenceHash(uint Value)
{
	Value ^= Value >> 16;
	Value *= 0x7feb352du;
	Value ^= Value >> 15;
	Value *= 0x846ca68bu;
	return Value ^ (Value >> 16);
}

// Jitter the alias stratum independently. A fixed midpoint aliases to a zero
// coin whenever the table size is divisible by the sample count.
float3 MaterialEnvironmentCoordinates(uint Index, uint Count, uint Seed)
{
	float2 First = MaterialHammersley(Index, Count);
	uint Bits = EnvironmentSequenceHash(Index ^ EnvironmentSequenceHash(Seed + 0x9e3779b9u));
	float Jitter = float(Bits >> 8) * (1.0f / 16777216.0f);
	First.x = (float(Index) + Jitter) / float(max(Count, 1u));
	float Third = 0;
	float Place = 1.0f / 3.0f;
	uint Digits = Index;
	while (Digits != 0)
	{
		Third += float(Digits % 3) * Place;
		Digits /= 3;
		Place /= 3;
	}
	return float3(First.x, First.y, Third);
}

float3 MaterialEnvironmentCoordinates(uint Index, uint Count)
{
	return MaterialEnvironmentCoordinates(Index, Count, 0);
}

float3 EnvironmentCubeDirection(uint Face, float2 Coordinate)
{
	float3 Direction;
	if (Face == 0)
	{
		Direction = float3(1, -Coordinate.y, -Coordinate.x);
	}
	else if (Face == 1)
	{
		Direction = float3(-1, -Coordinate.y, Coordinate.x);
	}
	else if (Face == 2)
	{
		Direction = float3(Coordinate.x, 1, Coordinate.y);
	}
	else if (Face == 3)
	{
		Direction = float3(Coordinate.x, -1, -Coordinate.y);
	}
	else if (Face == 4)
	{
		Direction = float3(Coordinate.x, -Coordinate.y, 1);
	}
	else
	{
		Direction = float3(-Coordinate.x, -Coordinate.y, -1);
	}
	return MaterialDirection(Direction, float3(0, 0, 1));
}

EnvironmentCubeAddress EnvironmentAddress(float3 Direction)
{
	EnvironmentCubeAddress Result;
	Result.Face = 0;
	Result.Coordinate = float2(0, 0);
	Result.Valid = MaterialFinite(Direction) && max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z))) > 0;
	if (!Result.Valid)
	{
		return Result;
	}
	float X = abs(Direction.x);
	float Y = abs(Direction.y);
	float Z = abs(Direction.z);
	if (X >= Y && X >= Z)
	{
		Result.Face = Direction.x >= 0 ? 0 : 1;
		Result.Coordinate = float2(Direction.x >= 0 ? -Direction.z / X : Direction.z / X, -Direction.y / X);
	}
	else if (Y >= Z)
	{
		Result.Face = Direction.y >= 0 ? 2 : 3;
		Result.Coordinate = float2(Direction.x / Y, Direction.y >= 0 ? Direction.z / Y : -Direction.z / Y);
	}
	else
	{
		Result.Face = Direction.z >= 0 ? 4 : 5;
		Result.Coordinate = float2(Direction.z >= 0 ? Direction.x / Z : -Direction.x / Z, -Direction.y / Z);
	}
	return Result;
}

uint EnvironmentTexelIndex(EnvironmentCubeAddress Address, uint FaceSize)
{
	uint X = min(uint(saturate(Address.Coordinate.x * 0.5f + 0.5f) * FaceSize), FaceSize - 1);
	uint Y = min(uint(saturate(Address.Coordinate.y * 0.5f + 0.5f) * FaceSize), FaceSize - 1);
	return (Address.Face * FaceSize + Y) * FaceSize + X;
}

float EnvironmentDirectionPdf(StructuredBuffer<EnvironmentAliasEntry> Table, uint FaceSize, bool UniformFallback, float3 Direction)
{
	EnvironmentCubeAddress Address = EnvironmentAddress(Direction);
	if (!Address.Valid || FaceSize == 0)
	{
		return 0;
	}
	if (UniformFallback)
	{
		return 1 / (4 * MATERIAL_PI);
	}
	float RadiusSquared = 1 + Address.Coordinate.x * Address.Coordinate.x + Address.Coordinate.y * Address.Coordinate.y;
	float InverseJacobian = RadiusSquared * sqrt(RadiusSquared);
	float Pmf = Table[EnvironmentTexelIndex(Address, FaceSize)].fPmf;
	return Pmf * (FaceSize * FaceSize * 0.25f) * InverseJacobian;
}

EnvironmentDirectionSample SampleEnvironmentDirection(StructuredBuffer<EnvironmentAliasEntry> Table, uint FaceSize, bool UniformFallback, float3 Xi)
{
	EnvironmentDirectionSample Result;
	Result.Direction = float3(0, 0, 1);
	Result.Pdf = 0;
	Result.Texel = 0;
	if (FaceSize == 0 || !MaterialFinite(Xi))
	{
		return Result;
	}
	Xi = saturate(Xi);
	if (UniformFallback)
	{
		float Z = 1 - 2 * Xi.y;
		float Radius = sqrt(max(0, 1 - Z * Z));
		float Phi = 2 * MATERIAL_PI * Xi.z;
		Result.Direction = float3(Radius * cos(Phi), Radius * sin(Phi), Z);
	}
	else
	{
		uint Count = 6 * FaceSize * FaceSize;
		float Coordinate = min(Xi.x, 0.9999999403953552f) * Count;
		uint Column = min(uint(Coordinate), Count - 1);
		EnvironmentAliasEntry Entry = Table[Column];
		uint Index = Coordinate - Column < Entry.fThreshold ? Column : Entry.nAlias;
		uint Face = Index / (FaceSize * FaceSize);
		uint Local = Index % (FaceSize * FaceSize);
		float U = 2 * ((Local % FaceSize + Xi.y) / FaceSize) - 1;
		float V = 2 * ((Local / FaceSize + Xi.z) / FaceSize) - 1;
		Result.Direction = EnvironmentCubeDirection(Face, float2(U, V));
		// Endpoints and binary32 rounding can land exactly on a neighboring
		// cell or face. Resolve only those boundary cases to this cell's center.
		// This defines the finite endpoint convention without shrinking every cell.
		if (EnvironmentTexelIndex(EnvironmentAddress(Result.Direction), FaceSize) != Index)
		{
			U = 2 * ((Local % FaceSize + 0.5f) / FaceSize) - 1;
			V = 2 * ((Local / FaceSize + 0.5f) / FaceSize) - 1;
			Result.Direction = EnvironmentCubeDirection(Face, float2(U, V));
		}
	}
	EnvironmentCubeAddress Address = EnvironmentAddress(Result.Direction);
	Result.Texel = EnvironmentTexelIndex(Address, FaceSize);
	Result.Pdf = EnvironmentDirectionPdf(Table, FaceSize, UniformFallback, Result.Direction);
	return Result;
}

struct MaterialMisCounts
{
	uint Base;
	uint Coat;
	uint Diffuse;
	uint Environment;
};

struct MaterialMisWeights
{
	float3 Base;
	float3 Coat;
	float3 Diffuse;
};

float MaterialGgxDirectionPdf(float3 V, float3 L, MaterialFrame Frame, float Roughness, float Anisotropy)
{
	if (!MaterialFinite(V) || !MaterialFinite(L) || dot(V, V) == 0 || dot(L, L) == 0)
	{
		return 0;
	}
	V = MaterialDirection(V, Frame.Normal);
	L = MaterialDirection(L, Frame.Normal);
	if (dot(Frame.Normal, V) <= 0 || dot(Frame.Normal, L) <= 0)
	{
		return 0;
	}
	float3 H = MaterialDirection(V + L, Frame.Normal);
	float VoH = dot(V, H);
	float NoH = dot(Frame.Normal, H);
	if (VoH <= 0 || NoH <= 0)
	{
		return 0;
	}
	float Pdf = MaterialGGXD(H, Frame, MaterialRoughnessAxes(Roughness, Anisotropy)) * NoH / (4 * VoH);
	return isfinite(Pdf) ? Pdf : 0;
}

float MaterialCosineDirectionPdf(float3 L, MaterialFrame Frame)
{
	if (!MaterialFinite(L) || dot(L, L) == 0)
	{
		return 0;
	}
	return saturate(dot(Frame.Normal, MaterialDirection(L, Frame.Normal))) / MATERIAL_PI;
}

float MaterialBalanceFactor(float NoL, uint BrdfCount, float BrdfPdf, uint EnvironmentCount, float EnvironmentPdf)
{
	float Denominator = BrdfCount * BrdfPdf + EnvironmentCount * EnvironmentPdf;
	return isfinite(Denominator) && Denominator > 0 ? NoL / Denominator : 0;
}

// Each technique accumulates its corresponding weights directly. No final
// division follows this sum; the sample counts are already in the denominator.
MaterialMisWeights MaterialImportanceWeights(float3 Base, float Metallic, float Roughness, float Anisotropy,
		float Clearcoat, float CoatRoughness, MaterialFrame Frame, float3 V, float3 L, float EnvironmentPdf, MaterialMisCounts Counts)
{
	MaterialLobes Lobes = MaterialEvaluateLobes(Base, Metallic, Roughness, Anisotropy, Clearcoat, CoatRoughness, Frame, V, L);
	float NoL = saturate(dot(Frame.Normal, MaterialDirection(L, Frame.Normal)));
	MaterialMisWeights Result;
	Result.Base = Lobes.Specular * MaterialBalanceFactor(NoL, Counts.Base, MaterialGgxDirectionPdf(V, L, Frame, Roughness, Anisotropy), Counts.Environment, EnvironmentPdf);
	Result.Coat = Lobes.Clearcoat * MaterialBalanceFactor(NoL, Counts.Coat, MaterialGgxDirectionPdf(V, L, Frame, CoatRoughness, 0), Counts.Environment, EnvironmentPdf);
	Result.Diffuse = Lobes.Diffuse * MaterialBalanceFactor(NoL, Counts.Diffuse, MaterialCosineDirectionPdf(L, Frame), Counts.Environment, EnvironmentPdf);
	return Result;
}

#endif
