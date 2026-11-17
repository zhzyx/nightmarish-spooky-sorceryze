/**************************************************************************/
/*  TestTemporalSampling.cpp                                              */
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
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>

namespace
{

// Shader spelling is preserved at this boundary so these tests directly include
// the production HLSLI functions. The adapters provide only vector intrinsics
// and bounded two-by-two texture reads.
struct Float2
{
	float x;
	float y;

	Float2(float fX, float fY) : x(fX), y(fY)
	{
	}
};

struct Float3
{
	float x = 0;
	float y = 0;
	float z = 0;
	float r = 0;
	float b = 0;

	Float3() = default;
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ), r(fX), b(fZ)
	{
	}
};

struct Float4
{
	float x = 0;
	float y = 0;
	float z = 0;
	float w = 0;
	float a = 0;
	Float3 rgb;
	Float3 xyz;
	Float2 xy;

	Float4() : xy(0, 0)
	{
	}
	Float4(float fX, float fY, float fZ, float fW) :
			x(fX), y(fY), z(fZ), w(fW), a(fW), rgb(fX, fY, fZ), xyz(fX, fY, fZ), xy(fX, fY)
	{
	}
	Float4(Float3 stRgb, float fAlpha) : Float4(stRgb.x, stRgb.y, stRgb.z, fAlpha)
	{
	}
};

struct Int2
{
	int x;
	int y;

	Int2(int nX, int nY) : x(nX), y(nY)
	{
	}
	explicit Int2(Float2 stValue) : x(static_cast<int>(stValue.x)), y(static_cast<int>(stValue.y))
	{
	}
};

struct Int3
{
	int x;
	int y;
	int z;

	Int3(Int2 stPixel, int nMip) : x(stPixel.x), y(stPixel.y), z(nMip)
	{
	}
};

struct Bool3
{
	bool x;
	bool y;
	bool z;
};

struct Bool4
{
	bool x;
	bool y;
	bool z;
	bool w;
};

Float3 operator*(Float3 stVector, float fScale)
{
	return { stVector.x * fScale, stVector.y * fScale, stVector.z * fScale };
}

Float2 operator*(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x * stRight.x, stLeft.y * stRight.y };
}

Float2 operator-(Float2 stLeft, float fRight)
{
	return { stLeft.x - fRight, stLeft.y - fRight };
}

Int2 operator-(Int2 stLeft, int nRight)
{
	return { stLeft.x - nRight, stLeft.y - nRight };
}

Int2 operator+(Int2 stLeft, Int2 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y };
}

Float2 floor(Float2 stValue)
{
	return { std::floor(stValue.x), std::floor(stValue.y) };
}

Float2 frac(Float2 stValue)
{
	return { stValue.x - std::floor(stValue.x), stValue.y - std::floor(stValue.y) };
}

Int2 clamp(Int2 stValue, Int2 stMinimum, Int2 stMaximum)
{
	return { std::clamp(stValue.x, stMinimum.x, stMaximum.x), std::clamp(stValue.y, stMinimum.y, stMaximum.y) };
}

Float4 &operator+=(Float4 &out_stLeft, const Float4 &stRight)
{
	out_stLeft = Float4(out_stLeft.x + stRight.x, out_stLeft.y + stRight.y, out_stLeft.z + stRight.z, out_stLeft.w + stRight.w);
	return out_stLeft;
}

Float3 operator/(Float3 stVector, float fScale)
{
	return { stVector.x / fScale, stVector.y / fScale, stVector.z / fScale };
}

float dot(Float3 stLeft, Float3 stRight)
{
	return stLeft.x * stRight.x + stLeft.y * stRight.y + stLeft.z * stRight.z;
}

Float3 normalize(Float3 stVector)
{
	return stVector / std::sqrt(dot(stVector, stVector));
}

Bool3 isfinite(Float3 stVector)
{
	return { std::isfinite(stVector.x), std::isfinite(stVector.y), std::isfinite(stVector.z) };
}

Bool4 isfinite(Float4 stVector)
{
	return { std::isfinite(stVector.x), std::isfinite(stVector.y), std::isfinite(stVector.z), std::isfinite(stVector.w) };
}

bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}

bool all(Bool3 stVector)
{
	return stVector.x && stVector.y && stVector.z;
}

bool all(Bool4 stVector)
{
	return stVector.x && stVector.y && stVector.z && stVector.w;
}

Float3 clamp(Float3 stVector, float fMinimum, float fMaximum)
{
	return { std::clamp(stVector.x, fMinimum, fMaximum), std::clamp(stVector.y, fMinimum, fMaximum), std::clamp(stVector.z, fMinimum, fMaximum) };
}

float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}

float max(float fLeft, double dRight)
{
	return (std::max)(fLeft, static_cast<float>(dRight));
}

float abs(float fValue)
{
	return std::abs(fValue);
}

float saturate(float fValue)
{
	return std::clamp(fValue, 0.0F, 1.0F);
}

template <class Value>
struct Texture2D
{
	std::array<Value, 4> arrValues{};

	Value Load(Int3 stPosition) const
	{
		const bool bInside = stPosition.x >= 0 && stPosition.x < 2 && stPosition.y >= 0 && stPosition.y < 2 && stPosition.z == 0;
		ENGINE_NEXT_CHECK(bInside);
		if (!bInside)
		{
			return {};
		}
		return arrValues[static_cast<std::size_t>(stPosition.y * 2 + stPosition.x)];
	}
};

using uint = std::uint32_t;
using float2 = Float2;
using float3 = Float3;
using float4 = Float4;
using int2 = Int2;
using int3 = Int3;

Float4 Settings(1, 0.9F, 0.01F, 0);
Float4 Planes(0.05F, 1000, 0, 0);
Float4 Viewport(2, 2, 0.5F, 0.5F);
Texture2D<Float4> CurrentHdr;
Texture2D<float> CurrentDepth;
Texture2D<Float4> CurrentNormal;
Texture2D<std::uint32_t> CurrentObjectId;
Texture2D<Float4> HistoryColor;
Texture2D<float> HistoryDepth;
Texture2D<Float4> HistoryNormal;
Texture2D<std::uint32_t> HistoryObjectId;
struct ExposureBuffer
{
	Float4 stValue{ 1, 1, 0, 0 };
	Float4 operator[](std::size_t) const
	{
		return stValue;
	}
};
ExposureBuffer ExposureState;

#include "engine_next/Rendering/Shaders/TemporalSampling.hlsli"

void ResetTextures()
{
	ExposureState.stValue = Float4(1, 1, 0, 0);
	Settings = Float4(1, 0.9F, 0.01F, 0);
	Planes = Float4(0.05F, 1000, 0, 0);
	CurrentHdr.arrValues.fill(Float4(1, 0, 0, 1));
	CurrentDepth.arrValues.fill(1);
	CurrentNormal.arrValues.fill(Float4(0, 0, 1, 0));
	CurrentObjectId.arrValues.fill(1);
	HistoryColor.arrValues.fill(Float4(1, 0, 0, 1));
	HistoryDepth.arrValues.fill(0.05F);
	HistoryNormal.arrValues.fill(Float4(0, 0, 1, 0));
	HistoryObjectId.arrValues.fill(1);
}

void CheckNear(float fActual, float fExpected, float fTolerance = 0.00001F)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(fActual - fExpected) <= fTolerance * (std::max)(1.0F, std::abs(fExpected)));
}

} // namespace

ENGINE_NEXT_TEST("Temporal sampling sanitizes color and preserves YCoCg round trips")
{
	for (const Float3 stColor : { Float3(0, 0, 0), Float3(1, 2, 3), Float3(65504, 0, 65504), Float3(25, 300, 7) })
	{
		const Float3 stResult = FromYCoCg(ToYCoCg(stColor));
		CheckNear(stResult.x, stColor.x);
		CheckNear(stResult.y, stColor.y);
		CheckNear(stResult.z, stColor.z);
	}
	const Float3 stClamped = FiniteColor(Float3(-1, 80000, 0.5F));
	ENGINE_NEXT_CHECK_EQ(stClamped.x, 0);
	ENGINE_NEXT_CHECK_EQ(stClamped.y, 65504);
	ENGINE_NEXT_CHECK_EQ(stClamped.z, 0.5F);
	for (float fInvalid : { std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN() })
	{
		const Float3 stColor = FiniteColor(Float3(1, fInvalid, 3));
		ENGINE_NEXT_CHECK_EQ(stColor.x, 0);
		ENGINE_NEXT_CHECK_EQ(stColor.y, 0);
		ENGINE_NEXT_CHECK_EQ(stColor.z, 0);
	}
	ENGINE_NEXT_CHECK(!ValidNormal(Float3(0, 0, 0)));
	ENGINE_NEXT_CHECK(!ValidNormal(Float3(0, 0, std::numeric_limits<float>::infinity())));
}

ENGINE_NEXT_TEST("Temporal sampling reconstructs positive reverse view depth")
{
	ResetTextures();
	CheckNear(ViewDepth(1), Planes.x);
	CheckNear(ViewDepth(0), Planes.y);
	for (float fDistance : { 0.1F, 1.0F, 20.0F, 500.0F })
	{
		const float fDepth = (Planes.x / fDistance - Planes.x / Planes.y) / (1 - Planes.x / Planes.y);
		CheckNear(ViewDepth(fDepth), fDistance);
	}
}

ENGINE_NEXT_TEST("Temporal current tap reports surface coverage without rejecting legal edge color")
{
	ResetTextures();
	CurrentHdr.arrValues[1] = Float4(0, 0, 1, 1);
	CurrentObjectId.arrValues[1] = 2;
	const Float4 stForeground = CurrentColorTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.625F);
	const Float4 stBackground = CurrentColorTap(Int2(1, 0), 1, 0.05F, Float3(0, 0, 1), 0.375F);
	CheckNear(stForeground.w + stBackground.w, 0.625F);
	// The main resolve combines all finite current colors independently of this
	// same-surface fraction, preserving the red/blue coverage blend.
	const Float4 stBlend = ReconstructCurrentColor(Float2(0.4375F, 0.25F), Int2(0, 0), 1, 0.05F, Float3(0, 0, 1));
	CheckNear(stBlend.x, 0.625F);
	CheckNear(stBlend.z, 0.375F);
	CheckNear(stBlend.a, 0.625F);
	CurrentObjectId.arrValues[1] = 1;
	const Float4 stSame = CurrentColorTap(Int2(1, 0), 1, 0.05F, Float3(0, 0, 1), 0.375F);
	CheckNear(stForeground.w + stSame.w, 1);
	CheckNear(stSame.z, 0.375F);
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0).w, 0);
}

ENGINE_NEXT_TEST("Temporal current surface matching rejects depth normal ID and invalid color mismatches")
{
	ResetTextures();
	CurrentDepth.arrValues[0] = 0.5F;
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 1).w, 0);
	CurrentDepth.arrValues[0] = 1;
	CurrentNormal.arrValues[0] = Float4(0, 0, -1, 0);
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 1).w, 0);
	CurrentNormal.arrValues[0] = Float4(0, 0, 0, 0);
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 1).w, 0);
	CurrentNormal.arrValues[0] = Float4(0, 0, 1, 0);
	CurrentObjectId.arrValues[0] = std::numeric_limits<std::uint32_t>::max();
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 1).w, 0);
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), std::numeric_limits<std::uint32_t>::max(), 0.05F, Float3(0, 0, 1), 1).w, 1);
	CurrentHdr.arrValues[0] = Float4(std::numeric_limits<float>::quiet_NaN(), 0, 0, 1);
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), std::numeric_limits<std::uint32_t>::max(), 0.05F, Float3(0, 0, 1), 1).w, 0);
}

ENGINE_NEXT_TEST("Temporal current reconstruction normalizes valid taps and preserves finite fallback")
{
	ResetTextures();
	CurrentHdr.arrValues[1] = Float4(0, 0, 1, 1);
	Float4 stResult = ReconstructCurrentColor(Float2(0.4375F, 0.25F), Int2(0, 0), 1, 0.05F, Float3(0, 0, 1));
	CheckNear(stResult.a, 1);
	CurrentDepth.arrValues[1] = 0.5F;
	stResult = ReconstructCurrentColor(Float2(0.4375F, 0.25F), Int2(0, 0), 1, 0.05F, Float3(0, 0, 1));
	CheckNear(stResult.a, 0.625F);
	CheckNear(stResult.z, 0.375F);
	CurrentHdr.arrValues[1] = Float4(std::numeric_limits<float>::infinity(), 0, 0, 1);
	stResult = ReconstructCurrentColor(Float2(0.4375F, 0.25F), Int2(0, 0), 1, 0.05F, Float3(0, 0, 1));
	CheckNear(stResult.x, 1);
	CheckNear(stResult.z, 0);
	CheckNear(stResult.a, 1);
	CurrentHdr.arrValues.fill(Float4(std::numeric_limits<float>::quiet_NaN(), 0, 0, 1));
	stResult = ReconstructCurrentColor(Float2(0.4375F, 0.25F), Int2(0, 0), 1, 0.05F, Float3(0, 0, 1));
	CheckNear(stResult.x, 0);
	CheckNear(stResult.a, 0);
}

ENGINE_NEXT_TEST("Temporal sky coverage accepts only zero ID background samples")
{
	ResetTextures();
	CurrentObjectId.arrValues[0] = 0;
	CurrentDepth.arrValues[0] = 0;
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 0, 0, Float3(0, 0, 0), 1).w, 1);
	CurrentDepth.arrValues[0] = 0.5F;
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 0, 0, Float3(0, 0, 0), 1).w, 0);
	CurrentDepth.arrValues[0] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 0, 0, Float3(0, 0, 0), 1).w, 0);
	CurrentObjectId.arrValues[0] = 1;
	CurrentDepth.arrValues[0] = 0;
	ENGINE_NEXT_CHECK_EQ(CurrentColorTap(Int2(0, 0), 0, 0, Float3(0, 0, 0), 1).w, 0);
}

ENGINE_NEXT_TEST("Temporal history retains only matching finite surface and coverage samples")
{
	ResetTextures();
	HistoryColor.arrValues[0] = Float4(2, 4, 6, 0.625F);
	const Float4 stMatch = ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.625F, 0.75F);
	CheckNear(stMatch.w, 0.75F);
	CheckNear(stMatch.y / stMatch.w, 4);
	ENGINE_NEXT_CHECK_EQ(ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.375F, 1).w, 0);
	CheckNear(ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.5F, 1).w, 0.5F);
	HistoryDepth.arrValues[0] = 0.1F;
	ENGINE_NEXT_CHECK_EQ(ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.625F, 1).w, 0);
	HistoryDepth.arrValues[0] = 0.05F;
	HistoryNormal.arrValues[0] = Float4(0, 0, -1, 0);
	ENGINE_NEXT_CHECK_EQ(ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.625F, 1).w, 0);
	HistoryNormal.arrValues[0] = Float4(0, 0, 1, 0);
	HistoryObjectId.arrValues[0] = 2;
	ENGINE_NEXT_CHECK_EQ(ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.625F, 1).w, 0);
	HistoryObjectId.arrValues[0] = 1;
	for (float fInvalid : { std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity() })
	{
		HistoryColor.arrValues[0] = Float4(2, 4, 6, fInvalid);
		ENGINE_NEXT_CHECK_EQ(ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.625F, 1).w, 0);
	}
}

ENGINE_NEXT_TEST("Temporal history confidence survives color normalization and limits feedback")
{
	ResetTextures();
	HistoryColor.arrValues[0] = Float4(2, 0, 0, 0.625F);
	HistoryColor.arrValues[1] = Float4(0, 0, 2, 0.625F);
	const Float4 stLeft = ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 0.5F, 0.75F);
	const Float4 stRight = ValidHistoryTap(Int2(1, 0), 1, 0.05F, Float3(0, 0, 1), 0.5F, 0.25F);
	const float fValidWeight = stLeft.w + stRight.w;
	CheckNear(fValidWeight, 0.5F);
	CheckNear((stLeft.x + stRight.x) / fValidWeight, 1.5F);
	CheckNear((stLeft.z + stRight.z) / fValidWeight, 0.5F);
	CheckNear(ResolveHistoryWeight(0.9F, 0.5F, fValidWeight), 0.225F);
	CheckNear(ResolveHistoryWeight(0.9F, 1, 1), 0.9F);
	ENGINE_NEXT_CHECK_EQ(ResolveHistoryWeight(0.9F, 1, 0), 0);
	ENGINE_NEXT_CHECK_EQ(ResolveHistoryWeight(-1, 1, 1), 0);
	ENGINE_NEXT_CHECK_EQ(ResolveHistoryWeight(2, 1, 1), 1);
}

ENGINE_NEXT_TEST("Temporal history adjusts previous pre-exposure before color feedback")
{
	ResetTextures();
	ExposureState.stValue = Float4(2, 1, 0, 0);
	const Float4 stTap = ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 1, 1);
	CheckNear(stTap.x, 2);
	CheckNear(stTap.w, 1);
	ExposureState.stValue = Float4(2, 0, 0, 0);
	ENGINE_NEXT_CHECK_EQ(ValidHistoryTap(Int2(0, 0), 1, 0.05F, Float3(0, 0, 1), 1, 1).w, 0);
}
