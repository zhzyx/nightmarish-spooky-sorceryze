/**************************************************************************/
/*  TestEnvironmentImportance.cpp                                         */
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

#include "engine_next/Rendering/Cook/EnvironmentImportance.h"
#include "engine_next/Tests/TestFramework.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <string>
#include <vector>

namespace EnvironmentShader
{
// Minimal HLSL value adapters. The formulas under test are included unchanged.
struct Float2
{
	Float2() : x(0), y(0) {}
	float x;
	float y;
	Float2(float fX, float fY) : x(fX), y(fY)
	{
	}
};

struct Float3
{
	float x;
	float y;
	float z;
	Float3() : x(0), y(0), z(0)
	{
	}
	Float3(float fValue) : x(fValue), y(fValue), z(fValue)
	{
	}
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
};

Float3 operator+(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y, stLeft.z + stRight.z };
}
Float3 operator-(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x - stRight.x, stLeft.y - stRight.y, stLeft.z - stRight.z };
}
Float3 operator*(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x * stRight.x, stLeft.y * stRight.y, stLeft.z * stRight.z };
}
Float3 operator*(Float3 stLeft, float fRight)
{
	return { stLeft.x * fRight, stLeft.y * fRight, stLeft.z * fRight };
}
Float3 operator*(float fLeft, Float3 stRight)
{
	return stRight * fLeft;
}
Float3 operator/(Float3 stLeft, float fRight)
{
	return { stLeft.x / fRight, stLeft.y / fRight, stLeft.z / fRight };
}
float dot(Float3 stLeft, Float3 stRight)
{
	return stLeft.x * stRight.x + stLeft.y * stRight.y + stLeft.z * stRight.z;
}
Float3 cross(Float3 stLeft, Float3 stRight)
{
	return { stLeft.y * stRight.z - stLeft.z * stRight.y, stLeft.z * stRight.x - stLeft.x * stRight.z, stLeft.x * stRight.y - stLeft.y * stRight.x };
}
float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}
Float3 max(Float3 stLeft, Float3 stRight)
{
	return { max(stLeft.x, stRight.x), max(stLeft.y, stRight.y), max(stLeft.z, stRight.z) };
}
float abs(float fValue)
{
	return std::abs(fValue);
}
float sqrt(float fValue)
{
	return std::sqrt(fValue);
}
float rsqrt(float fValue)
{
	return 1 / std::sqrt(fValue);
}
float sin(float fValue)
{
	return std::sin(fValue);
}
float cos(float fValue)
{
	return std::cos(fValue);
}
float pow(float fValue, float fPower)
{
	return std::pow(fValue, fPower);
}
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
float clamp(float fValue, float fMinimum, float fMaximum)
{
	return std::clamp(fValue, fMinimum, fMaximum);
}
float saturate(float fValue)
{
	return clamp(fValue, 0, 1);
}
Float3 saturate(Float3 stValue)
{
	return { saturate(stValue.x), saturate(stValue.y), saturate(stValue.z) };
}
Float3 lerp(Float3 stLeft, Float3 stRight, float fFactor)
{
	return stLeft * (1 - fFactor) + stRight * fFactor;
}

using float2 = Float2;
using float3 = Float3;
using uint = std::uint32_t;

float min(float fLeft, float fRight)
{
	return (std::min)(fLeft, fRight);
}
uint max(uint nLeft, uint nRight)
{
	return (std::max)(nLeft, nRight);
}
uint min(uint nLeft, uint nRight)
{
	return (std::min)(nLeft, nRight);
}
template <typename Value>
struct StructuredBuffer
{
	const std::vector<Value> *pValues;
	const Value &operator[](uint nIndex) const { return (*pValues)[nIndex]; }
	void GetDimensions(uint &out_nCount, uint &out_nStride) const
	{
		out_nCount = static_cast<uint>(pValues->size());
		out_nStride = sizeof(Value);
	}
};
using EnvironmentAliasEntry = EngineNext::Rendering::EnvironmentAliasEntry;
#define ENVIRONMENT_ALIAS_ENTRY_DEFINED
#include "engine_next/Rendering/Shaders/EnvironmentImportance.hlsli"

} //namespace EnvironmentShader

namespace
{
using namespace EnvironmentShader;
using EngineNext::Rendering::EnvironmentImportance;
using EngineNext::Rendering::FloatImage;
constexpr double PI = 3.14159265358979323846;

std::array<FloatImage, 6> MakeFaces(uint nSize, float fValue)
{
	std::array<FloatImage, 6> arrFaces;
	for (FloatImage &stFace : arrFaces)
	{
		stFace.nWidth = nSize;
		stFace.nHeight = nSize;
		stFace.arrPixels.resize(static_cast<std::size_t>(nSize) * nSize, { fValue, fValue, fValue, 1 });
	}
	return arrFaces;
}

EnvironmentImportance MakeImportance(const std::array<FloatImage, 6> &arrFaces)
{
	EnvironmentImportance stResult;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildEnvironmentImportance(arrFaces, stResult, strError));
	ENGINE_NEXT_CHECK(strError.empty());
	return stResult;
}

StructuredBuffer<EnvironmentAliasEntry> Buffer(const EnvironmentImportance &stImportance)
{
	return { &stImportance.arrEntries };
}

float Uniform(std::mt19937 &stGenerator)
{
	// The high 24 bits give an exact binary32 value in [0,1).
	return static_cast<float>(stGenerator() >> 8) * (1.0F / 16777216.0F);
}

Float3 Random3(std::mt19937 &stGenerator)
{
	return { Uniform(stGenerator), Uniform(stGenerator), Uniform(stGenerator) };
}

Float3 Lookup(const std::array<FloatImage, 6> &arrFaces, Float3 vDirection)
{
	const EnvironmentCubeAddress stAddress = EnvironmentAddress(vDirection);
	const uint nSize = arrFaces[0].nWidth;
	const uint nIndex = EnvironmentTexelIndex(stAddress, nSize);
	const std::array<float, 4> &arrPixel = arrFaces[nIndex / (nSize * nSize)].arrPixels[nIndex % (nSize * nSize)];
	return { arrPixel[0], arrPixel[1], arrPixel[2] };
}

struct MaterialCase
{
	Float3 vBase{ .7F, .4F, .2F };
	float fMetallic = .35F;
	float fRoughness = .35F;
	float fAnisotropy = .6F;
	float fCoat = 1;
	float fCoatRoughness = .25F;
	MaterialFrame stFrame = MaterialBuildFrame({ 0, 0, 1 }, { 1, 0, 0 }, 1, .4F);
	Float3 vView{ 0, 0, 1 };
};

MaterialEnvironmentSample BrdfSample(const MaterialCase &stMaterial, uint nLobe, Float2 vXi)
{
	if (nLobe == 0)
	{
		return MaterialEnvironmentBaseSample(stMaterial.vBase, stMaterial.fMetallic, stMaterial.fRoughness, stMaterial.fAnisotropy,
											 stMaterial.fCoat, stMaterial.fCoatRoughness, stMaterial.stFrame, stMaterial.vView, vXi);
	}
	if (nLobe == 1)
	{
		return MaterialEnvironmentCoatSample(stMaterial.vBase, stMaterial.fMetallic, stMaterial.fRoughness, stMaterial.fAnisotropy,
											 stMaterial.fCoat, stMaterial.fCoatRoughness, stMaterial.stFrame, stMaterial.vView, vXi);
	}
	return MaterialEnvironmentDiffuseSample(stMaterial.vBase, stMaterial.fMetallic, stMaterial.fRoughness, stMaterial.fAnisotropy,
											stMaterial.fCoat, stMaterial.fCoatRoughness, stMaterial.stFrame, stMaterial.vView, vXi);
}

MaterialMisWeights Weights(const MaterialCase &stMaterial, Float3 vDirection, float fEnvironmentPdf, MaterialMisCounts stCounts)
{
	return MaterialImportanceWeights(stMaterial.vBase, stMaterial.fMetallic, stMaterial.fRoughness, stMaterial.fAnisotropy,
									 stMaterial.fCoat, stMaterial.fCoatRoughness, stMaterial.stFrame, stMaterial.vView, vDirection, fEnvironmentPdf, stCounts);
}

Float3 SelectLobe(MaterialMisWeights stWeights, uint nLobe)
{
	return nLobe == 0 ? stWeights.Base : nLobe == 1 ? stWeights.Coat
													: stWeights.Diffuse;
}

std::array<double, 3> Estimate(const std::array<FloatImage, 6> &arrFaces, const EnvironmentImportance &stImportance,
							   const MaterialCase &stMaterial, MaterialMisCounts stCounts, std::mt19937 &stGenerator)
{
	std::array<double, 3> arrResult{};
	const uint arrCounts[] = { stCounts.Base, stCounts.Coat, stCounts.Diffuse };
	for (uint nLobe = 0; nLobe < 3; ++nLobe)
	{
		for (uint nSample = 0; nSample < arrCounts[nLobe]; ++nSample)
		{
			const Float2 vXi(Uniform(stGenerator), Uniform(stGenerator));
			const MaterialEnvironmentSample stSample = BrdfSample(stMaterial, nLobe, vXi);
			if (stSample.Pdf == 0)
			{
				continue;
			}
			const float fEnvironmentPdf = EnvironmentDirectionPdf(Buffer(stImportance), stImportance.nFaceSize, stImportance.bUniformFallback, stSample.Direction);
			const Float3 vValue = SelectLobe(Weights(stMaterial, stSample.Direction, fEnvironmentPdf, stCounts), nLobe) * Lookup(arrFaces, stSample.Direction);
			arrResult[0] += vValue.x;
			arrResult[1] += vValue.y;
			arrResult[2] += vValue.z;
		}
	}
	for (uint nSample = 0; nSample < stCounts.Environment; ++nSample)
	{
		const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stImportance), stImportance.nFaceSize, stImportance.bUniformFallback, Random3(stGenerator));
		const MaterialMisWeights stWeights = Weights(stMaterial, stSample.Direction, stSample.Pdf, stCounts);
		const Float3 vValue = (stWeights.Base + stWeights.Coat + stWeights.Diffuse) * Lookup(arrFaces, stSample.Direction);
		arrResult[0] += vValue.x;
		arrResult[1] += vValue.y;
		arrResult[2] += vValue.z;
	}
	return arrResult;
}

std::array<double, 3> Integrate(const std::array<FloatImage, 6> &arrFaces, const MaterialCase &stMaterial, uint nSubdivisions)
{
	std::array<double, 3> arrResult{};
	const uint nSize = arrFaces[0].nWidth;
	const uint nFullSize = nSize * nSubdivisions;
	for (uint nFace = 0; nFace < 6; ++nFace)
	{
		for (uint nY = 0; nY < nFullSize; ++nY)
		{
			for (uint nX = 0; nX < nFullSize; ++nX)
			{
				const float fU = 2 * (nX + .5F) / nFullSize - 1;
				const float fV = 2 * (nY + .5F) / nFullSize - 1;
				const Float3 vL = EnvironmentCubeDirection(nFace, { fU, fV });
				const MaterialLobes stLobes = MaterialEvaluateLobes(stMaterial.vBase, stMaterial.fMetallic, stMaterial.fRoughness, stMaterial.fAnisotropy,
																	stMaterial.fCoat, stMaterial.fCoatRoughness, stMaterial.stFrame, stMaterial.vView, vL);
				const Float3 vValue = (stLobes.Diffuse + stLobes.Specular + stLobes.Clearcoat) * saturate(dot(stMaterial.stFrame.Normal, vL)) * Lookup(arrFaces, vL);
				const double dSolidAngle = EngineNext::Rendering::EnvironmentTexelSolidAngle(nX, nY, nFullSize);
				arrResult[0] += vValue.x * dSolidAngle;
				arrResult[1] += vValue.y * dSolidAngle;
				arrResult[2] += vValue.z * dSolidAngle;
			}
		}
	}
	return arrResult;
}

ENGINE_NEXT_TEST("Environment solid angles and alias probabilities are normalized")
{
	for (uint nSize : { 1U, 2U, 4U, 16U, 64U })
	{
		double dSum = 0;
		for (uint nY = 0; nY < nSize; ++nY)
		{
			for (uint nX = 0; nX < nSize; ++nX)
			{
				const double dArea = EngineNext::Rendering::EnvironmentTexelSolidAngle(nX, nY, nSize);
				ENGINE_NEXT_CHECK(dArea > 0 && std::isfinite(dArea));
				dSum += 6 * dArea;
			}
		}
		ENGINE_NEXT_CHECK(std::abs(dSum - 4 * PI) < 1e-11);
	}
	std::array<FloatImage, 6> arrFaces = MakeFaces(16, 1);
	arrFaces[4].arrPixels[133] = { 9000, 5000, 2000, 1 };
	arrFaces[2].arrPixels[0] = { 0, 0, 0, 1 };
	const EnvironmentImportance stTable = MakeImportance(arrFaces);
	const EnvironmentImportance stAgain = MakeImportance(arrFaces);
	ENGINE_NEXT_CHECK(std::memcmp(stTable.arrEntries.data(), stAgain.arrEntries.data(), stTable.arrEntries.size() * sizeof(EnvironmentAliasEntry)) == 0);
	std::vector<double> arrActual(stTable.arrEntries.size(), 0);
	const double dCount = static_cast<double>(arrActual.size());
	for (std::size_t nIndex = 0; nIndex < arrActual.size(); ++nIndex)
	{
		const EnvironmentAliasEntry &stEntry = stTable.arrEntries[nIndex];
		ENGINE_NEXT_CHECK(stEntry.fThreshold >= 0 && stEntry.fThreshold <= 1 && stEntry.nAlias < arrActual.size());
		arrActual[nIndex] += stEntry.fThreshold / dCount;
		arrActual[stEntry.nAlias] += (1.0 - stEntry.fThreshold) / dCount;
	}
	double dPmfSum = 0;
	for (std::size_t nIndex = 0; nIndex < arrActual.size(); ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stTable.arrEntries[nIndex].fPmf, static_cast<float>(arrActual[nIndex]));
		ENGINE_NEXT_CHECK_EQ(stTable.arrEntries[nIndex].nMetadata, 32U);
		dPmfSum += stTable.arrEntries[nIndex].fPmf;
	}
	ENGINE_NEXT_CHECK(std::abs(dPmfSum - 1) < 1e-7);
}

ENGINE_NEXT_TEST("Environment validation is transactional and black uses sphere fallback")
{
	std::array<FloatImage, 6> arrFaces = MakeFaces(2, 0);
	const EnvironmentImportance stBlack = MakeImportance(arrFaces);
	ENGINE_NEXT_CHECK(stBlack.bUniformFallback);
	EnvironmentImportance stOutput = stBlack;
	std::string strError;
	arrFaces[0].nHeight = 1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildEnvironmentImportance(arrFaces, stOutput, strError));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrEntries.size(), stBlack.arrEntries.size());
	ENGINE_NEXT_CHECK(stOutput.bUniformFallback);
	arrFaces = MakeFaces(2, 1);
	arrFaces[1].arrPixels[1][0] = std::numeric_limits<float>::infinity();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildEnvironmentImportance(arrFaces, stOutput, strError));
	arrFaces = MakeFaces(2, std::numeric_limits<float>::max());
	arrFaces[0].arrPixels[0][3] = std::numeric_limits<float>::quiet_NaN();
	stOutput = MakeImportance(arrFaces);
	ENGINE_NEXT_CHECK(std::isfinite(stOutput.dIntegratedLuminance));
	arrFaces = MakeFaces(2, -1);
	ENGINE_NEXT_CHECK(MakeImportance(arrFaces).bUniformFallback);
	std::mt19937 stGenerator(17);
	Float3 vMean{};
	for (uint nIndex = 0; nIndex < 10000; ++nIndex)
	{
		const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stBlack), 2, true, Random3(stGenerator));
		ENGINE_NEXT_CHECK(std::abs(stSample.Pdf - 1 / (4 * PI)) < 1e-8);
		ENGINE_NEXT_CHECK(std::abs(dot(stSample.Direction, stSample.Direction) - 1) < 1e-5);
		vMean = vMean + stSample.Direction;
	}
	ENGINE_NEXT_CHECK(std::abs(vMean.x / 10000) < .02F && std::abs(vMean.y / 10000) < .02F && std::abs(vMean.z / 10000) < .02F);
	ENGINE_NEXT_CHECK_EQ(EnvironmentDirectionPdf(Buffer(stBlack), 2, true, { 0, 0, 0 }), 0.0F);
	ENGINE_NEXT_CHECK_EQ(EnvironmentDirectionPdf(Buffer(stBlack), 2, true, { std::numeric_limits<float>::infinity(), 0, 1 }), 0.0F);
	const EnvironmentDirectionSample stInvalid = SampleEnvironmentDirection(Buffer(stBlack), 2, true, { std::numeric_limits<float>::quiet_NaN(), 0, 0 });
	ENGINE_NEXT_CHECK_EQ(stInvalid.Pdf, 0.0F);
	arrFaces[0].nWidth = std::numeric_limits<uint>::max();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildEnvironmentImportance(arrFaces, stOutput, strError));
}

ENGINE_NEXT_TEST("Environment metadata is validated before table sampling")
{
	EnvironmentImportance stTable = MakeImportance(MakeFaces(64, 1));
	EnvironmentTableInfo stInfo = ReadEnvironmentTableInfo(Buffer(stTable));
	ENGINE_NEXT_CHECK(stInfo.Valid);
	ENGINE_NEXT_CHECK_EQ(stInfo.FaceSize, 64U);
	ENGINE_NEXT_CHECK(!stInfo.UniformFallback);
	stTable = MakeImportance(MakeFaces(4, 0));
	stInfo = ReadEnvironmentTableInfo(Buffer(stTable));
	ENGINE_NEXT_CHECK(stInfo.Valid && stInfo.UniformFallback && stInfo.FaceSize == 4);
	for (uint nInvalid : { 0U, 1U, 2U, 3346U, std::numeric_limits<uint>::max() })
	{
		stTable.arrEntries[0].nMetadata = nInvalid;
		stInfo = ReadEnvironmentTableInfo(Buffer(stTable));
		ENGINE_NEXT_CHECK(!stInfo.Valid);
		ENGINE_NEXT_CHECK_EQ(stInfo.FaceSize, 0U);
	}
	stTable.arrEntries.clear();
	ENGINE_NEXT_CHECK(!ReadEnvironmentTableInfo(Buffer(stTable)).Valid);
	const Float3 vFirst = MaterialEnvironmentCoordinates(0, 24);
	const Float3 vSecond = MaterialEnvironmentCoordinates(1, 24);
	ENGINE_NEXT_CHECK(vFirst.x >= 0 && vFirst.x < 1.0F / 24);
	ENGINE_NEXT_CHECK_EQ(vFirst.z, 0.0F);
	ENGINE_NEXT_CHECK_EQ(vSecond.z, 1.0F / 3.0F);
}

ENGINE_NEXT_TEST("Environment alias sequence avoids the table and sample count lattice")
{
	uint nOldZeroCoins = 0;
	uint nNewZeroCoins = 0;
	for (uint nIndex = 0; nIndex < 24; ++nIndex)
	{
		const float fOld = MaterialHammersley(nIndex, 24).x * 24576;
		const Float3 vCoordinate = MaterialEnvironmentCoordinates(nIndex, 24);
		const float fNew = vCoordinate.x * 24576;
		nOldZeroCoins += fOld == std::floor(fOld) ? 1U : 0U;
		nNewZeroCoins += fNew == std::floor(fNew) ? 1U : 0U;
		ENGINE_NEXT_CHECK(vCoordinate.x >= static_cast<float>(nIndex) / 24);
		ENGINE_NEXT_CHECK(vCoordinate.x < static_cast<float>(nIndex + 1) / 24);
		ENGINE_NEXT_CHECK_EQ(vCoordinate.x, MaterialEnvironmentCoordinates(nIndex, 24).x);
	}
	ENGINE_NEXT_CHECK_EQ(nOldZeroCoins, 24U);
	ENGINE_NEXT_CHECK(nNewZeroCoins < 4);
	std::array<FloatImage, 6> arrFaces = MakeFaces(4, 1);
	arrFaces[4].arrPixels[3] = { 300, 300, 300, 1 };
	const EnvironmentImportance stTable = MakeImportance(arrFaces);
	std::vector<uint> arrCounts(stTable.arrEntries.size(), 0);
	for (uint nSeed = 0; nSeed < 4096; ++nSeed)
	{
		for (uint nIndex = 0; nIndex < 24; ++nIndex)
		{
			const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stTable), 4, false,
																				   MaterialEnvironmentCoordinates(nIndex, 24, nSeed));
			++arrCounts[stSample.Texel];
		}
	}
	double dChiSquared = 0;
	for (std::size_t nIndex = 0; nIndex < arrCounts.size(); ++nIndex)
	{
		const double dExpected = stTable.arrEntries[nIndex].fPmf * (4096.0 * 24);
		const double dDelta = arrCounts[nIndex] - dExpected;
		dChiSquared += dDelta * dDelta / dExpected;
	}
	ENGINE_NEXT_CHECK(dChiSquared < 2 * arrCounts.size());
	std::cout << "STRATIFIED_ALIAS chi_squared=" << dChiSquared << " old_zero_coins=" << nOldZeroCoins << " new_zero_coins=" << nNewZeroCoins << '\n';
}

ENGINE_NEXT_TEST("Environment direction mapping and Jacobian PDF agree")
{
	std::array<FloatImage, 6> arrFaces = MakeFaces(16, 1);
	for (uint nFace = 0; nFace < 6; ++nFace)
	{
		arrFaces[nFace].arrPixels[nFace * 11][0] = static_cast<float>(nFace + 1) * 123;
	}
	const EnvironmentImportance stTable = MakeImportance(arrFaces);
	const Float3 arrReferenceDirections[] = { { 1, .5F, -.25F }, { -1, .5F, .25F }, { .25F, 1, -.5F }, { .25F, -1, .5F }, { .25F, .5F, 1 }, { -.25F, .5F, -1 } };
	double dIntegral = 0;
	for (uint nFace = 0; nFace < 6; ++nFace)
	{
		ENGINE_NEXT_CHECK(dot(EnvironmentCubeDirection(nFace, { .25F, -.5F }), MaterialDirection(arrReferenceDirections[nFace], { 0, 0, 1 })) > .999999F);
		for (uint nY = 0; nY < 16; ++nY)
		{
			for (uint nX = 0; nX < 16; ++nX)
			{
				const float fU = 2 * (nX + .5F) / 16 - 1;
				const float fV = 2 * (nY + .5F) / 16 - 1;
				const Float3 vDirection = EnvironmentCubeDirection(nFace, { fU, fV });
				const EnvironmentCubeAddress stAddress = EnvironmentAddress(vDirection);
				ENGINE_NEXT_CHECK_EQ(EnvironmentTexelIndex(stAddress, 16), (nFace * 16 + nY) * 16 + nX);
				const double dJacobian = std::pow(1.0 + fU * fU + fV * fV, -1.5);
				dIntegral += EnvironmentDirectionPdf(Buffer(stTable), 16, false, vDirection) * dJacobian * 4 / (16 * 16);
			}
		}
		for (float fU : { -1.0F, -.99999F, 0.0F, .99999F, 1.0F })
		{
			for (float fV : { -1.0F, -.99999F, 0.0F, .99999F, 1.0F })
			{
				const Float3 vDirection = EnvironmentCubeDirection(nFace, { fU, fV });
				const EnvironmentCubeAddress stAddress = EnvironmentAddress(vDirection);
				ENGINE_NEXT_CHECK(stAddress.Valid && stAddress.Face < 6);
				const Float3 vRoundtrip = EnvironmentCubeDirection(stAddress.Face, stAddress.Coordinate);
				ENGINE_NEXT_CHECK(dot(vDirection, vRoundtrip) > .999999F);
			}
		}
	}
	ENGINE_NEXT_CHECK(std::abs(dIntegral - 1) < 2e-7);
	std::mt19937 stGenerator(22);
	for (uint nIndex = 0; nIndex < 100000; ++nIndex)
	{
		const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stTable), 16, false, Random3(stGenerator));
		ENGINE_NEXT_CHECK(stSample.Pdf > 0 && MaterialFinite(stSample.Direction));
		ENGINE_NEXT_CHECK_EQ(stSample.Pdf, EnvironmentDirectionPdf(Buffer(stTable), 16, false, stSample.Direction));
	}
	for (float fX : { 0.0F, .5F, 1.0F })
	{
		for (float fY : { 0.0F, 1.0F })
		{
			const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stTable), 16, false, { fX, fY, fY });
			ENGINE_NEXT_CHECK(stSample.Texel < stTable.arrEntries.size());
			ENGINE_NEXT_CHECK_EQ(stSample.Pdf, EnvironmentDirectionPdf(Buffer(stTable), 16, false, stSample.Direction));
		}
	}
}

ENGINE_NEXT_TEST("MIS count denominator matches mixture normalization and production PDFs")
{
	const MaterialFrame stFrame = MaterialBuildFrame({ 0, 0, 1 }, { 1, 0, 0 }, -1, .7F);
	const Float3 vView = MaterialDirection({ .3F, .2F, 1 }, stFrame.Normal);
	for (float fAnisotropy : { -1.0F, 0.0F, 1.0F })
	{
		for (uint nIndex = 0; nIndex < 1024; ++nIndex)
		{
			const MaterialEnvironmentSample stSample = MaterialEnvironmentBaseSample({ 1, 1, 1 }, .4F, .5F, fAnisotropy, 1, .3F, stFrame, vView, MaterialHammersley(nIndex, 1024));
			if (stSample.Pdf > 0)
			{
				const float fPdf = MaterialGgxDirectionPdf(vView, stSample.Direction, stFrame, .5F, fAnisotropy);
				ENGINE_NEXT_CHECK(std::abs(fPdf - stSample.Pdf) <= .00003F * (std::max)(1.0F, stSample.Pdf));
			}
		}
	}
	for (float fBrdf : { 0.0F, .01F, .7F, 100.0F })
	{
		for (float fEnv : { .0001F, .3F, 17.0F })
		{
			const float fDirect = MaterialBalanceFactor(.7F, 16, fBrdf, 24, fEnv);
			const double dMixture = .7 / ((16.0 / 40) * fBrdf + (24.0 / 40) * fEnv) / 40;
			ENGINE_NEXT_CHECK(std::abs(fDirect - dMixture) <= std::abs(dMixture) * 2e-7);
		}
	}
	ENGINE_NEXT_CHECK_EQ(MaterialBalanceFactor(1, 0, 0, 0, 0), 0.0F);
	ENGINE_NEXT_CHECK(MaterialEnvironmentUsesLegacy(true, 0, 0));
	const Float3 vLegacy = MaterialShadeLight({ .5F, .2F, .1F }, 0, .5F, 0, 0, .1F, true, stFrame, vView, { 0, 0, 1 }, { 1, 1, 1 });
	ENGINE_NEXT_CHECK(MaterialFinite(vLegacy));
}

ENGINE_NEXT_TEST("Sparse environment boundaries keep sampled cells and quantized frequencies")
{
	std::array<FloatImage, 6> arrSparse = MakeFaces(4, 0);
	arrSparse[5].arrPixels[0] = { 1, 1, 1, 1 };
	const EnvironmentImportance stSparse = MakeImportance(arrSparse);
	for (float fX : { 0.0F, .01F, .7F, 1.0F })
	{
		for (float fY : { 0.0F, .5F, 1.0F })
		{
			for (float fZ : { 0.0F, .5F, 1.0F })
			{
				const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stSparse), 4, false, { fX, fY, fZ });
				ENGINE_NEXT_CHECK_EQ(stSample.Texel, 80U);
				ENGINE_NEXT_CHECK(stSample.Pdf > 0 && std::isfinite(stSample.Pdf));
			}
		}
	}
	std::array<FloatImage, 6> arrFaces = MakeFaces(4, 1);
	for (uint nFace = 0; nFace < 6; ++nFace)
	{
		for (uint nPixel = 0; nPixel < 16; ++nPixel)
		{
			arrFaces[nFace].arrPixels[nPixel] = { static_cast<float>(nFace + 1), static_cast<float>(nPixel + 1), .1F, 1 };
		}
	}
	const EnvironmentImportance stTable = MakeImportance(arrFaces);
	std::vector<uint> arrFrequency(stTable.arrEntries.size(), 0);
	std::mt19937 stGenerator(86593);
	constexpr uint COUNT = 200000;
	for (uint nIndex = 0; nIndex < COUNT; ++nIndex)
	{
		const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stTable), 4, false, Random3(stGenerator));
		++arrFrequency[stSample.Texel];
	}
	double dChiSquared = 0;
	for (std::size_t nIndex = 0; nIndex < arrFrequency.size(); ++nIndex)
	{
		const double dExpected = stTable.arrEntries[nIndex].fPmf * static_cast<double>(COUNT);
		const double dDifference = arrFrequency[nIndex] - dExpected;
		dChiSquared += dDifference * dDifference / dExpected;
	}
	ENGINE_NEXT_CHECK(dChiSquared < 2 * arrFrequency.size());
	std::cout << "FREQUENCY chi_squared=" << dChiSquared << " bins=" << arrFrequency.size() << '\n';
	arrFaces = MakeFaces(4, std::numeric_limits<float>::min());
	arrFaces[0].arrPixels[0] = { std::numeric_limits<float>::max(), std::numeric_limits<float>::max(), std::numeric_limits<float>::max(), 1 };
	const EnvironmentImportance stExtreme = MakeImportance(arrFaces);
	ENGINE_NEXT_CHECK_EQ(stExtreme.arrEntries[0].fPmf, 1.0F);
	for (const EnvironmentAliasEntry &stEntry : stExtreme.arrEntries)
	{
		ENGINE_NEXT_CHECK(std::isfinite(stEntry.fPmf) && stEntry.fPmf >= 0 && stEntry.fPmf <= 1);
	}
}

ENGINE_NEXT_TEST("Importance lobes remain finite at grazing views and mirrored poles")
{
	const EnvironmentImportance stTable = MakeImportance(MakeFaces(8, 1));
	for (float fSign : { -1.0F, 1.0F })
	{
		const MaterialFrame stFrame = MaterialBuildFrame({ 0, 0, 1 }, { 1, 0, 0 }, fSign, 1.4F);
		for (float fRoughness : { 0.0F, .5F, 1.0F })
		{
			for (float fAnisotropy : { -1.0F, 0.0F, 1.0F })
			{
				for (float fViewZ : { .0001F, .3F, 1.0F })
				{
					const Float3 vView = MaterialDirection({ std::sqrt(1 - fViewZ * fViewZ), 0, fViewZ }, stFrame.Normal);
					for (uint nSample = 0; nSample < 128; ++nSample)
					{
						const Float2 vXi = MaterialHammersley(nSample, 128);
						const EnvironmentDirectionSample stSample = SampleEnvironmentDirection(Buffer(stTable), 8, false, { vXi.x, vXi.y, .5F });
						const MaterialMisWeights stWeights = MaterialImportanceWeights({ 1, 1, 1 }, .5F, fRoughness, fAnisotropy, 1, fRoughness,
																					   stFrame, vView, stSample.Direction, stSample.Pdf, { 16, 8, 8, 24 });
						ENGINE_NEXT_CHECK(MaterialFinite(stWeights.Base) && MaterialFinite(stWeights.Coat) && MaterialFinite(stWeights.Diffuse));
						ENGINE_NEXT_CHECK(stWeights.Base.x >= 0 && stWeights.Coat.x >= 0 && stWeights.Diffuse.x >= 0);
					}
				}
			}
		}
	}
}

ENGINE_NEXT_TEST("MIS white furnace matches quadrature and conserves energy")
{
	const std::array<FloatImage, 6> arrFaces = MakeFaces(16, 1);
	const EnvironmentImportance stTable = MakeImportance(arrFaces);
	std::mt19937 stGenerator(9123);
	for (float fAnisotropy : { -.7F, .7F })
	{
		for (float fCoat : { 0.0F, 1.0F })
		{
			MaterialCase stMaterial;
			stMaterial.vBase = { 1, 1, 1 };
			stMaterial.fAnisotropy = fAnisotropy;
			stMaterial.fCoat = fCoat;
			stMaterial.stFrame = MaterialBuildFrame({ 0, 0, 1 }, { 1, 0, 0 }, -1, .7F);
			stMaterial.fRoughness = .5F;
			stMaterial.fCoatRoughness = .4F;
			const std::array<double, 3> arrReference = Integrate(arrFaces, stMaterial, 16);
			const std::array<double, 3> arrEstimate = Estimate(arrFaces, stTable, stMaterial, { 65536, fCoat > 0 ? 65536U : 0U, 65536, 65536 }, stGenerator);
			for (uint nChannel = 0; nChannel < 3; ++nChannel)
			{
				ENGINE_NEXT_CHECK(arrEstimate[nChannel] >= 0 && arrEstimate[nChannel] <= 1.005);
				ENGINE_NEXT_CHECK(std::abs(arrEstimate[nChannel] - arrReference[nChannel]) < .008);
			}
			std::cout << "WHITE " << fAnisotropy << ' ' << fCoat << ' ' << arrReference[0] << ' ' << arrEstimate[0] << '\n';
		}
	}
}

ENGINE_NEXT_TEST("Equal budget MIS reduces small sun variance")
{
	std::array<FloatImage, 6> arrFaces = MakeFaces(64, .05F);
	arrFaces[4].arrPixels[27 * 64 + 35] = { 1000, 750, 500, 1 };
	const EnvironmentImportance stTable = MakeImportance(arrFaces);
	const MaterialCase stMaterial;
	const std::array<double, 3> arrReference = Integrate(arrFaces, stMaterial, 8);
	constexpr uint TRIALS = 32768;
	std::array<double, 2> arrSum{};
	std::array<double, 2> arrSquaredError{};
	std::mt19937 stGenerator(123444);
	for (uint nTrial = 0; nTrial < TRIALS; ++nTrial)
	{
		const std::array<double, 3> arrBaseline = Estimate(arrFaces, stTable, stMaterial, { 32, 16, 8, 0 }, stGenerator);
		const std::array<double, 3> arrMis = Estimate(arrFaces, stTable, stMaterial, { 16, 8, 8, 24 }, stGenerator);
		const double arrValues[] = { arrBaseline[0], arrMis[0] };
		for (uint nMode = 0; nMode < 2; ++nMode)
		{
			arrSum[nMode] += arrValues[nMode];
			arrSquaredError[nMode] += (arrValues[nMode] - arrReference[0]) * (arrValues[nMode] - arrReference[0]);
		}
	}
	const double dBaselineMean = arrSum[0] / TRIALS;
	const double dMisMean = arrSum[1] / TRIALS;
	const double dBaselineMse = arrSquaredError[0] / TRIALS;
	const double dMisMse = arrSquaredError[1] / TRIALS;
	const double dBaselineVariance = dBaselineMse - (dBaselineMean - arrReference[0]) * (dBaselineMean - arrReference[0]);
	const double dMisVariance = dMisMse - (dMisMean - arrReference[0]) * (dMisMean - arrReference[0]);
	const double dMisStandardError = std::sqrt(dMisVariance / TRIALS);
	ENGINE_NEXT_CHECK(std::abs(dMisMean - arrReference[0]) < .02 * arrReference[0]);
	ENGINE_NEXT_CHECK(std::abs(dMisMean - arrReference[0]) < 5 * dMisStandardError);
	ENGINE_NEXT_CHECK(dMisMse < dBaselineMse * .2);
	std::cout << std::setprecision(12) << "SUN reference=" << arrReference[0] << " baseline_mean=" << dBaselineMean << " mis_mean=" << dMisMean
			  << " baseline_mse=" << dBaselineMse << " mis_mse=" << dMisMse << " ratio=" << dMisMse / dBaselineMse
			  << " baseline_variance=" << dBaselineVariance << " mis_variance=" << dMisVariance << " mis_standard_error=" << dMisStandardError << '\n';
}

} // namespace
