/**************************************************************************/
/*  TestShadowSampling.cpp                                                */
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

#include "engine_next/Tests/TestFramework.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace
{

// These small adapters preserve HLSL type, component, and intrinsic spellings.
// The sampling algorithm is included directly from the production shader.
struct Float2
{
	float x;
	float y;

	Float2(float fX, float fY) : x(fX), y(fY) {}
	Float2(int nX, int nY) : Float2(static_cast<float>(nX), static_cast<float>(nY)) {}
	Float2(double dX, double dY) : Float2(static_cast<float>(dX), static_cast<float>(dY)) {}
};

struct Float3
{
	float x;
	float y;
	float z;
	Float2 xy;

	Float3() : Float3(0, 0, 0) {}
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ), xy(fX, fY) {}
};

struct Bool2
{
	bool x;
	bool y;
};

struct Bool3
{
	bool x;
	bool y;
	bool z;
};

struct Int2
{
	int x;
	int y;

	Int2(int nX, int nY) : x(nX), y(nY) {}
	Int2(std::uint32_t nX, std::uint32_t nY) : Int2(static_cast<int>(nX), static_cast<int>(nY)) {}
	explicit Int2(Float2 stValue) : Int2(static_cast<int>(stValue.x), static_cast<int>(stValue.y)) {}
};

struct Int4
{
	Int2 stPixel;
	std::uint32_t nSlice;

	Int4(Int2 stPosition, std::uint32_t nLayer, int) : stPixel(stPosition), nSlice(nLayer) {}
};

Float2 operator*(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x * stRight.x, stLeft.y * stRight.y };
}

Float2 operator*(Float2 stLeft, float fRight)
{
	return { stLeft.x * fRight, stLeft.y * fRight };
}

Float2 operator*(Float2 stLeft, double dRight)
{
	return stLeft * static_cast<float>(dRight);
}

Float2 operator*(Float2 stLeft, int nRight)
{
	return stLeft * static_cast<float>(nRight);
}

Float2 operator+(Float2 stLeft, float fRight)
{
	return { stLeft.x + fRight, stLeft.y + fRight };
}

Float2 operator+(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y };
}

Float2 operator-(Float2 stLeft, int nRight)
{
	return { stLeft.x - static_cast<float>(nRight), stLeft.y - static_cast<float>(nRight) };
}

Float2 operator/(Float2 stLeft, float fRight)
{
	return { stLeft.x / fRight, stLeft.y / fRight };
}

Float3 operator+(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y, stLeft.z + stRight.z };
}

Float3 operator*(Float3 stLeft, float fRight)
{
	return { stLeft.x * fRight, stLeft.y * fRight, stLeft.z * fRight };
}

Float3 operator*(Float3 stLeft, double dRight)
{
	return stLeft * static_cast<float>(dRight);
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
	return { stLeft.y * stRight.z - stLeft.z * stRight.y,
			 stLeft.z * stRight.x - stLeft.x * stRight.z,
			 stLeft.x * stRight.y - stLeft.y * stRight.x };
}

float length(Float3 stValue)
{
	return std::sqrt(dot(stValue, stValue));
}

Int2 operator+(Int2 stLeft, Int2 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y };
}

Bool2 operator>(Float2 stLeft, float fRight)
{
	return { stLeft.x > fRight, stLeft.y > fRight };
}

Float2 abs(Float2 stValue)
{
	return { std::abs(stValue.x), std::abs(stValue.y) };
}

Float3 abs(Float3 stValue)
{
	return { std::abs(stValue.x), std::abs(stValue.y), std::abs(stValue.z) };
}

float abs(float fValue)
{
	return std::abs(fValue);
}

Bool2 isfinite(Float2 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y) };
}

Bool3 isfinite(Float3 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y), std::isfinite(stValue.z) };
}

bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}

bool all(Bool2 stValue)
{
	return stValue.x && stValue.y;
}

bool all(Bool3 stValue)
{
	return stValue.x && stValue.y && stValue.z;
}

bool any(Bool2 stValue)
{
	return stValue.x || stValue.y;
}

float max(float fLeft, int nRight)
{
	return (std::max)(fLeft, static_cast<float>(nRight));
}

float clamp(float fValue, int nMinimum, int nMaximum)
{
	return std::clamp(fValue, static_cast<float>(nMinimum), static_cast<float>(nMaximum));
}

float clamp(float fValue, float fMinimum, float fMaximum)
{
	return std::clamp(fValue, fMinimum, fMaximum);
}

float saturate(float fValue)
{
	return std::clamp(fValue, 0.0F, 1.0F);
}

Int2 clamp(Int2 stValue, Int2 stMinimum, Int2 stMaximum)
{
	return { std::clamp(stValue.x, stMinimum.x, stMaximum.x), std::clamp(stValue.y, stMinimum.y, stMaximum.y) };
}

Float2 round(Float2 stValue)
{
	return { std::round(stValue.x), std::round(stValue.y) };
}

struct TextureData
{
	std::uint32_t nWidth = 256;
	std::uint32_t nHeight = 256;
	std::uint32_t nLayers = 1;
	float fDepth = 0;
	bool bHalfPlane = false;
	bool bSplitBlockers = false;
	float fSecondDepth = 0;
	bool bRadialSphere = false;
	float fSphereRadius = 5;
	bool bPlane = false;
	bool bOrthographicPlane = false;
	Float2 stPlaneGradient{ 0, 0 };
	float fPlaneConstant = 0.5F;
	float fBlockerDepthOffset = 0;
	std::vector<Int4> arrReads;
};

template <class Value>
struct Texture2DArray
{
	TextureData *pData;

	void GetDimensions(std::uint32_t &out_nWidth, std::uint32_t &out_nHeight, std::uint32_t &out_nLayers) const
	{
		out_nWidth = pData->nWidth;
		out_nHeight = pData->nHeight;
		out_nLayers = pData->nLayers;
	}

	Value Load(Int4 stPosition) const
	{
		pData->arrReads.push_back(stPosition);
		const bool bInside = stPosition.stPixel.x >= 0 && stPosition.stPixel.y >= 0 &&
				stPosition.stPixel.x < static_cast<int>(pData->nWidth) && stPosition.stPixel.y < static_cast<int>(pData->nHeight) &&
				stPosition.nSlice < pData->nLayers;
		ENGINE_NEXT_CHECK(bInside);
		if (!bInside)
		{
			return 0;
		}
		if (pData->bOrthographicPlane)
		{
			const float fClipX = (static_cast<float>(stPosition.stPixel.x) + 0.5F) * 2 / pData->nWidth - 1;
			const float fClipY = 1 - (static_cast<float>(stPosition.stPixel.y) + 0.5F) * 2 / pData->nHeight;
			if (pData->bHalfPlane && stPosition.stPixel.x >= static_cast<int>(pData->nWidth / 2))
			{
				return 0;
			}
			return pData->fPlaneConstant + pData->stPlaneGradient.x * fClipX +
					pData->stPlaneGradient.y * fClipY + pData->fBlockerDepthOffset;
		}
		if (pData->bPlane)
		{
			const float fY = 1 - (static_cast<float>(stPosition.stPixel.y) + 0.5F) * 2 / pData->nHeight;
			const float fRayY = stPosition.nSlice == 2 ? 1 : (stPosition.nSlice == 3 ? -1 : fY);
			const float fAxisDistance = -3.6F / fRayY;
			if (fAxisDistance <= 0.05F || fAxisDistance >= 20)
			{
				return 0;
			}
			return (0.05F / fAxisDistance - 0.05F / 20) / (1 - 0.05F / 20);
		}
		if (pData->bRadialSphere)
		{
			const float fX = (static_cast<float>(stPosition.stPixel.x) + 0.5F) * 2 / pData->nWidth - 1;
			const float fY = (static_cast<float>(stPosition.stPixel.y) + 0.5F) * 2 / pData->nHeight - 1;
			const float fAxisDistance = pData->fSphereRadius / std::sqrt(1 + fX * fX + fY * fY);
			return (1 / fAxisDistance - 1.0F / 101) / (1 - 1.0F / 101);
		}
		const bool bRightHalf = stPosition.stPixel.x >= static_cast<int>(pData->nWidth / 2);
		if (pData->bSplitBlockers && bRightHalf)
		{
			return pData->fSecondDepth;
		}
		return pData->bHalfPlane && bRightHalf ? 0 : pData->fDepth;
	}
};

using uint = std::uint32_t;
using float2 = Float2;
using float3 = Float3;
using int2 = Int2;
using int4 = Int4;
#include "engine_next/Rendering/Shaders/ShadowSampling.hlsli"

void CheckNear(float fActual, float fExpected)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(fActual - fExpected) <= 2.0e-5F * (std::max)(1.0F, std::abs(fExpected)));
}

float ProjectDepth(float fDistance, Float2 stPlanes)
{
	return (stPlanes.x / fDistance - stPlanes.x / stPlanes.y) / (1 - stPlanes.x / stPlanes.y);
}

int FilterRadius(const TextureData &stData)
{
	int nRadius = 0;
	// PCSS performs 25 blocker reads before the 25 filter reads.
	for (std::size_t nIndex = 25; nIndex < stData.arrReads.size(); ++nIndex)
	{
		nRadius = (std::max)(nRadius, std::abs(stData.arrReads[nIndex].stPixel.x - 128));
	}
	return nRadius;
}

} // namespace

ENGINE_NEXT_TEST("Directional receiver plane handles scaled reflected and rotated shadow axes")
{
	const Float3 stNormal(1, 2, 4);
	const Float2 stGradient = ShadowReceiverGradient(Float3(2, 0, 0), Float3(0, -3, 0), Float3(0, 0, -4), stNormal);
	CheckNear(stGradient.x, 0.5F);
	CheckNear(stGradient.y, -2.0F / 3);
	const Float2 stFlipped = ShadowReceiverGradient(Float3(2, 0, 0), Float3(0, -3, 0), Float3(0, 0, -4), stNormal * -1.0F);
	CheckNear(stFlipped.x, stGradient.x);
	CheckNear(stFlipped.y, stGradient.y);
	const Float2 stRotated = ShadowReceiverGradient(Float3(0, 2, 0), Float3(-3, 0, 0), Float3(0, 0, -4), stNormal);
	CheckNear(stRotated.x, 1);
	CheckNear(stRotated.y, -1.0F / 3);
}

ENGINE_NEXT_TEST("Directional receiver plane falls back for singular and grazing geometry")
{
	const Float3 stX(1, 0, 0);
	const Float3 stY(0, 1, 0);
	const Float3 stZ(0, 0, 1);
	const float fNan = std::numeric_limits<float>::quiet_NaN();
	for (const Float3 &stNormal : { Float3(0, 0, 0), Float3(1, 0, 0), Float3(1, 0, 1.0e-8F), Float3(fNan, 0, 1) })
	{
		const Float2 stGradient = ShadowReceiverGradient(stX, stY, stZ, stNormal);
		ENGINE_NEXT_CHECK_EQ(stGradient.x, 0);
		ENGINE_NEXT_CHECK_EQ(stGradient.y, 0);
	}
	const Float2 stSingular = ShadowReceiverGradient(stX, stY, stX, stZ);
	ENGINE_NEXT_CHECK_EQ(stSingular.x, 0);
	ENGINE_NEXT_CHECK_EQ(stSingular.y, 0);
	const Float2 stInvalid = ShadowReceiverGradient(Float3(fNan, 0, 0), stY, stZ, stZ);
	ENGINE_NEXT_CHECK_EQ(stInvalid.x, 0);
	ENGINE_NEXT_CHECK_EQ(stInvalid.y, 0);
	CheckNear(ShadowReceiverDepth(Float3(0, 0, 0.5F), Float2(0.1F, 0.1F), Float2(fNan, 0.0F), 0.001F), 0.501F);
}

ENGINE_NEXT_TEST("Directional PCF uses actual clamped texel centers on the receiver plane")
{
	TextureData stData;
	stData.bOrthographicPlane = true;
	stData.nWidth = 64;
	stData.nHeight = 64;
	stData.stPlaneGradient = Float2(0.15F, -0.2F);
	Texture2DArray<float> stTexture{ &stData };
	const Float2 stGradient = ShadowReceiverGradient(Float3(1, 0, 0), Float3(0, 1, 0), Float3(0, 0, 1), Float3(-0.15F, 0.2F, 1));
	for (float fX : { -1.0F, -0.999F, -0.01F, 0.0F, 0.013F, 0.99F, 1.0F })
	{
		for (float fY : { -1.0F, -0.71F, 0.0F, 0.123F, 1.0F })
		{
			const Float3 stReceiver(fX, fY, stData.fPlaneConstant + stGradient.x * fX + stGradient.y * fY);
			CheckNear(SampleShadowMap(stTexture, stReceiver, 0, 64, 1.0e-6F, 0, Float2(0, 0), true, false, 6, Float3(0, 0, 0), stGradient), 1);
		}
	}
	const Float3 stCenter(0.013F, 0.123F, stData.fPlaneConstant + stGradient.x * 0.013F + stGradient.y * 0.123F);
	ENGINE_NEXT_CHECK(SampleShadowMap(stTexture, stCenter, 0, 64, 1.0e-6F, 0, Float2(0, 0), true, false) < 1);
	stData.fBlockerDepthOffset = 0.0005F;
	CheckNear(SampleShadowMap(stTexture, stCenter, 0, 64, 1.0e-6F, 0, Float2(0, 0), true, false, 6, Float3(0, 0, 0), stGradient), 0);
	stData.bHalfPlane = true;
	const Float3 stBoundary(0, 0, stData.fPlaneConstant);
	CheckNear(SampleShadowMap(stTexture, stBoundary, 0, 64, 1.0e-6F, 0, Float2(0, 0), true, false, 6, Float3(0, 0, 0), stGradient), 2.0F / 3);
}

ENGINE_NEXT_TEST("Shadow sampling reconstructs perspective and orthographic reverse depth")
{
	const Float2 stPlanes(1, 101);
	ENGINE_NEXT_CHECK_EQ(ShadowViewDistance(1, stPlanes, false), 1);
	ENGINE_NEXT_CHECK_EQ(ShadowViewDistance(0, stPlanes, false), 101);
	for (float fDistance : { 1.0F, 2.0F, 5.0F, 20.0F, 100.0F })
	{
		CheckNear(ShadowViewDistance(ProjectDepth(fDistance, stPlanes), stPlanes, false), fDistance);
	}
	ENGINE_NEXT_CHECK_EQ(ShadowViewDistance(0.5F, stPlanes, true), 51);
}

ENGINE_NEXT_TEST("Shadow PCF uses reverse comparisons positive bias and clamped edge taps")
{
	const Float2 stPlanes(1, 101);
	TextureData stData;
	Texture2DArray<float> stTexture{ &stData };
	const Float3 stReceiver(0, 0, ProjectDepth(20, stPlanes));
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, stPlanes, false, false), 1);
	ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 9U);
	stData.arrReads.clear();
	stData.fDepth = ProjectDepth(5, stPlanes);
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, stPlanes, false, false), 0);
	ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 9U);
	stData.arrReads.clear();
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0.2F, 80, stPlanes, false, false), 1);
	stData.bHalfPlane = true;
	CheckNear(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, stPlanes, false, false), 2.0F / 3.0F);
	stData.arrReads.clear();
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(1, 0, stReceiver.z), 0, 256, 0, 80, stPlanes, false, false), 1);
	ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 9U);
}

ENGINE_NEXT_TEST("Shadow PCSS reconstructs blockers and bounds perspective penumbra taps")
{
	const Float2 stPlanes(1, 101);
	TextureData stData;
	Texture2DArray<float> stTexture{ &stData };
	const Float3 stReceiver(0, 0, ProjectDepth(20, stPlanes));
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, stPlanes, false, true), 1);
	ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 25U);
	stData.fDepth = ProjectDepth(5, stPlanes);
	for (float fDistance : { 6.0F, 10.0F, 20.0F })
	{
		stData.arrReads.clear();
		ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(0, 0, ProjectDepth(fDistance, stPlanes)), 0, 256, 0, 80, stPlanes, false, true), 0);
		ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 50U);
		const int nExpectedRadius = static_cast<int>(std::round(80 * (1 - 5 / fDistance) / 5));
		ENGINE_NEXT_CHECK_EQ(FilterRadius(stData), nExpectedRadius);
	}
	stData.arrReads.clear();
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 1.0e20F, stPlanes, false, true), 0);
	ENGINE_NEXT_CHECK_EQ(FilterRadius(stData), 32);
	stData.arrReads.clear();
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 0, stPlanes, false, true), 0);
	ENGINE_NEXT_CHECK_EQ(FilterRadius(stData), 1);
}

ENGINE_NEXT_TEST("Shadow PCSS averages linear blocker distance and samples visibility")
{
	const Float2 stPlanes(1, 101);
	TextureData stData;
	stData.fDepth = ProjectDepth(5, stPlanes);
	stData.fSecondDepth = ProjectDepth(10, stPlanes);
	stData.bSplitBlockers = true;
	Texture2DArray<float> stTexture{ &stData };
	const Float3 stReceiver(0, 0, ProjectDepth(20, stPlanes));
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, stPlanes, false, true), 0);
	ENGINE_NEXT_CHECK_EQ(FilterRadius(stData), 6);
	stData.bSplitBlockers = false;
	stData.bHalfPlane = true;
	stData.arrReads.clear();
	CheckNear(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, stPlanes, false, true), 0.6F);
	stData.bHalfPlane = false;
	stData.arrReads.clear();
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(-1, 1, stReceiver.z), 0, 256, 0, 80, stPlanes, false, true), 0);
	ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 50U);
	stData.fDepth = 0.75F;
	stData.arrReads.clear();
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(0, 0, 0.5F), 0, 256, 0, 1, stPlanes, true, true), 0);
	ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 50U);
	ENGINE_NEXT_CHECK_EQ(FilterRadius(stData), 1);
}

ENGINE_NEXT_TEST("Shadow sampling rejects invalid coordinates resources and PCSS parameters before texture reads")
{
	const Float2 stPlanes(1, 101);
	TextureData stData;
	Texture2DArray<float> stTexture{ &stData };
	for (const Float3 stPosition : { Float3(2, 0, 0.5F), Float3(0, 2, 0.5F), Float3(0, 0, -0.1F), Float3(0, 0, 1.1F), Float3(0, 0, std::numeric_limits<float>::quiet_NaN()) })
	{
		ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stPosition, 0, 256, 0, 80, stPlanes, false, true), 1);
		ENGINE_NEXT_CHECK(stData.arrReads.empty());
	}
	const Float3 stReceiver(0, 0, ProjectDepth(20, stPlanes));
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 1, 256, 0, 80, stPlanes, false, true), 1);
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 128, 0, 80, stPlanes, false, true), 1);
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, Float2(0, 101), false, true), 1);
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, 80, Float2(101, 1), false, true), 1);
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, stReceiver, 0, 256, 0, -1, stPlanes, false, true), 1);
	ENGINE_NEXT_CHECK(stData.arrReads.empty());
}

ENGINE_NEXT_TEST("Point shadow filters preserve sphere occlusion at all face boundaries")
{
	const Float2 stPlanes(1, 101);
	TextureData stData;
	stData.nLayers = 6;
	stData.bRadialSphere = true;
	Texture2DArray<float> stTexture{ &stData };
	const Float2 arrEdges[]{ { -1, 0 }, { 1, 0 }, { 0, -1 }, { 0, 1 }, { -1, -1 }, { -1, 1 }, { 1, -1 }, { 1, 1 } };
	for (std::uint32_t nFace = 0; nFace < 6; ++nFace)
	{
		for (const Float2 stEdge : arrEdges)
		{
			for (bool bPcss : { false, true })
			{
				ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(stEdge.x, stEdge.y, ProjectDepth(2, stPlanes)), nFace, 256, 0, 8, stPlanes, false, bPcss, nFace), 1);
				ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(stEdge.x, stEdge.y, ProjectDepth(8, stPlanes)), nFace, 256, 0, 8, stPlanes, false, bPcss, nFace), 0);
			}
		}
	}
	stData.arrReads.clear();
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(0, 0, 0.5F), 0, 256, 0, 8, stPlanes, false, true, 1), 1);
	ENGINE_NEXT_CHECK(stData.arrReads.empty());
	stData.nLayers = 5;
	ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(0, 0, 0.5F), 0, 256, 0, 8, stPlanes, false, true, 0), 1);
	ENGINE_NEXT_CHECK(stData.arrReads.empty());
}

ENGINE_NEXT_TEST("Point shadow receiver plane stays lit across cube face transitions")
{
	TextureData stData;
	stData.bPlane = true;
	stData.nLayers = 6;
	Texture2DArray<float> stTexture{ &stData };
	const Float2 stPlanes(0.05F, 20.0F);
	// The light is at the origin, the plane at y=-3.6, and normal bias
	// places the receiver at y=-3.59. Sweep both sides of four cube edges.
	for (float fSign : { -1.0F, 1.0F })
	{
		for (float fAcross : { 3.58F, 3.60F })
		{
			for (bool bZAxis : { false, true })
			{
				const Float3 stVector(bZAxis ? 0 : fSign * fAcross, -3.59F, bZAxis ? fSign * fAcross : 0);
				const std::uint32_t nFace = ShadowCubeFace(stVector);
				const Float2 stProjected = ShadowCubeProjection(stVector, nFace);
				const float fAxisDistance = (std::max)(fAcross, 3.59F);
				const Float3 stPosition(stProjected.x, stProjected.y, ProjectDepth(fAxisDistance, stPlanes));
				for (bool bPcss : { false, true })
				{
					CheckNear(SampleShadowMap(stTexture, stPosition, nFace, 256, 0.0005F, 7680, stPlanes, false, bPcss, nFace, Float3(0, 1, 0)), 1);
				}
			}
		}
	}
}

ENGINE_NEXT_TEST("Point shadow kernel stays bounded near both Z poles")
{
	TextureData stData;
	stData.nLayers = 6;
	Texture2DArray<float> stTexture{ &stData };
	for (std::uint32_t nFace : { 4U, 5U })
	{
		for (float fOffset : { -0.0006F, -0.0005F, 0.0F, 0.0005F, 0.0006F })
		{
			stData.arrReads.clear();
			ENGINE_NEXT_CHECK_EQ(SampleShadowMap(stTexture, Float3(fOffset, 0, 0.5F), nFace, 256, 0, 0, Float2(1, 101), false, false, nFace), 1);
			ENGINE_NEXT_CHECK_EQ(stData.arrReads.size(), 9U);
			int nMinimumX = 256;
			int nMaximumX = 0;
			int nMinimumY = 256;
			int nMaximumY = 0;
			for (const Int4 stRead : stData.arrReads)
			{
				nMinimumX = (std::min)(nMinimumX, stRead.stPixel.x);
				nMaximumX = (std::max)(nMaximumX, stRead.stPixel.x);
				nMinimumY = (std::min)(nMinimumY, stRead.stPixel.y);
				nMaximumY = (std::max)(nMaximumY, stRead.stPixel.y);
			}
			ENGINE_NEXT_CHECK(nMaximumX - nMinimumX <= 3);
			ENGINE_NEXT_CHECK(nMaximumY - nMinimumY <= 3);
		}
	}
}
