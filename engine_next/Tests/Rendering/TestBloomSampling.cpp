/**************************************************************************/
/*  TestBloomSampling.cpp                                                 */
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
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace
{

// The adapters preserve shader spelling and execute the production HLSLI.
// Texture reads check their actual bounds, including one-pixel and odd sizes.
struct Float2
{
	float x;
	float y;

	Float2(float fX, float fY) : x(fX), y(fY) {}
};

struct Float3
{
	float x;
	float y;
	float z;

	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ) {}
	Float3 &operator+=(Float3 stOther)
	{
		x += stOther.x;
		y += stOther.y;
		z += stOther.z;
		return *this;
	}
};

struct Float4
{
	float x;
	float y;
	float z;
	float w;
	Float3 rgb;
	Float2 zw;

	Float4() : Float4(0, 0, 0, 0) {}
	Float4(float fX, float fY, float fZ, float fW) : x(fX), y(fY), z(fZ), w(fW), rgb(fX, fY, fZ), zw(fZ, fW) {}
};

struct Int2
{
	int x;
	int y;

	Int2(int nX, int nY) : x(nX), y(nY) {}
	explicit Int2(Float2 stValue) : x(static_cast<int>(stValue.x)), y(static_cast<int>(stValue.y)) {}
};

struct Int3
{
	int x;
	int y;
	int z;

	Int3(Int2 stPixel, int nMip) : x(stPixel.x), y(stPixel.y), z(nMip) {}
};

struct Bool3
{
	bool x;
	bool y;
	bool z;
};

Float2 operator*(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x * stRight.x, stLeft.y * stRight.y };
}

Float2 operator+(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y };
}

Float2 operator-(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x - stRight.x, stLeft.y - stRight.y };
}

Float2 operator-(Float2 stLeft, float fRight)
{
	return { stLeft.x - fRight, stLeft.y - fRight };
}

Float2 operator/(float fLeft, Float2 stRight)
{
	return { fLeft / stRight.x, fLeft / stRight.y };
}

Float3 operator*(Float3 stLeft, float fRight)
{
	return { stLeft.x * fRight, stLeft.y * fRight, stLeft.z * fRight };
}

Int2 operator+(Int2 stLeft, Int2 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y };
}

Int2 operator-(Int2 stLeft, int nRight)
{
	return { stLeft.x - nRight, stLeft.y - nRight };
}

Float2 floor(Float2 stValue)
{
	return { std::floor(stValue.x), std::floor(stValue.y) };
}

Float2 frac(Float2 stValue)
{
	return stValue - floor(stValue);
}

float dot(Float3 stLeft, Float3 stRight)
{
	return stLeft.x * stRight.x + stLeft.y * stRight.y + stLeft.z * stRight.z;
}

Bool3 isfinite(Float3 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y), std::isfinite(stValue.z) };
}

bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}

bool all(Bool3 stValue)
{
	return stValue.x && stValue.y && stValue.z;
}

Float3 clamp(Float3 stValue, float fMinimum, float fMaximum)
{
	return { std::clamp(stValue.x, fMinimum, fMaximum), std::clamp(stValue.y, fMinimum, fMaximum), std::clamp(stValue.z, fMinimum, fMaximum) };
}

float clamp(float fValue, float fMinimum, float fMaximum)
{
	return std::clamp(fValue, fMinimum, fMaximum);
}

Int2 clamp(Int2 stValue, Int2 stMinimum, Int2 stMaximum)
{
	return { std::clamp(stValue.x, stMinimum.x, stMaximum.x), std::clamp(stValue.y, stMinimum.y, stMaximum.y) };
}

float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}

float saturate(float fValue)
{
	return std::clamp(fValue, 0.0F, 1.0F);
}

Float3 lerp(Float3 stLeft, Float3 stRight, float fWeight)
{
	return { stLeft.x + (stRight.x - stLeft.x) * fWeight, stLeft.y + (stRight.y - stLeft.y) * fWeight, stLeft.z + (stRight.z - stLeft.z) * fWeight };
}

template <class Value>
struct Texture2D
{
	std::uint32_t nWidth = 1;
	std::uint32_t nHeight = 1;
	std::vector<Value> arrValues{ Value{} };

	void Reset(std::uint32_t nNewWidth, std::uint32_t nNewHeight, Value stValue)
	{
		nWidth = nNewWidth;
		nHeight = nNewHeight;
		arrValues.assign(static_cast<std::size_t>(nWidth) * nHeight, stValue);
	}

	void GetDimensions(std::uint32_t &out_nWidth, std::uint32_t &out_nHeight) const
	{
		out_nWidth = nWidth;
		out_nHeight = nHeight;
	}

	Value Load(Int3 stPixel) const
	{
		const bool bValid = stPixel.x >= 0 && stPixel.y >= 0 && static_cast<std::uint32_t>(stPixel.x) < nWidth && static_cast<std::uint32_t>(stPixel.y) < nHeight && stPixel.z == 0;
		ENGINE_NEXT_CHECK(bValid);
		if (!bValid)
		{
			return {};
		}
		return arrValues[static_cast<std::size_t>(stPixel.y) * nWidth + stPixel.x];
	}
};

using uint = std::uint32_t;
using float2 = Float2;
using float3 = Float3;
using float4 = Float4;
using int2 = Int2;
using int3 = Int3;

Float4 Source(1, 1, 1, 1);
Float4 Parameters(0.1F, 1, 0.5F, 0.5F);
Float4 Modes(0, 0, 0, 0);
std::array<Float4, 1> ExposureRead{ Float4(1, 1, 0, 0) };
std::array<Float4, 1> ExposureWrite{ Float4(1, 1, 0, 0) };
Texture2D<Float4> SourceColor;
Texture2D<Float4> LowerColor;

#include "engine_next/Rendering/Shaders/BloomSampling.hlsli"

void ResetBloom(std::uint32_t nWidth = 3, std::uint32_t nHeight = 3)
{
	Source = Float4(static_cast<float>(nWidth), static_cast<float>(nHeight), 1.0F / nWidth, 1.0F / nHeight);
	Parameters = Float4(0.1F, 1, 0.5F, 0.5F);
	Modes = Float4(0, 0, 0, 0);
	ExposureRead[0] = Float4(1, 1, 0, 0);
	ExposureWrite[0] = Float4(1, 1, 0, 0);
	SourceColor.Reset(nWidth, nHeight, Float4(0, 0, 0, 0));
	LowerColor.Reset(1, 1, Float4(0, 0, 0, 0));
}

void CheckNear(float fActual, float fExpected, float fTolerance = 0.00001F)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(fActual - fExpected) <= fTolerance * (std::max)(1.0F, std::abs(fExpected)));
}

void CheckColor(Float3 stActual, Float3 stExpected, float fTolerance = 0.00001F)
{
	CheckNear(stActual.x, stExpected.x, fTolerance);
	CheckNear(stActual.y, stExpected.y, fTolerance);
	CheckNear(stActual.z, stExpected.z, fTolerance);
}

} // namespace

ENGINE_NEXT_TEST("Bloom soft knee is continuous and bounded in display exposure units")
{
	ResetBloom();
	Parameters = Float4(0.1F, 2, 0.5F, 0.5F);
	CheckColor(ExtractBloom(Float3(1, 1, 1)), Float3(0, 0, 0));
	CheckColor(ExtractBloom(Float3(2, 2, 2)), Float3(0.25F, 0.25F, 0.25F));
	CheckColor(ExtractBloom(Float3(3, 3, 3)), Float3(1, 1, 1));
	for (float fBoundary : { 1.0F, 3.0F })
	{
		const float fBelow = ExtractBloom(Float3(fBoundary - 0.0001F, fBoundary - 0.0001F, fBoundary - 0.0001F)).x;
		const float fAbove = ExtractBloom(Float3(fBoundary + 0.0001F, fBoundary + 0.0001F, fBoundary + 0.0001F)).x;
		ENGINE_NEXT_CHECK(std::abs(fAbove - fBelow) < 0.0003F);
	}
	float fPrevious = 0;
	for (std::uint32_t nStep = 0; nStep < 101; ++nStep)
	{
		const float fValue = static_cast<float>(nStep) * 0.1F;
		const Float3 stResult = ExtractBloom(Float3(fValue, fValue, fValue));
		ENGINE_NEXT_CHECK(stResult.x >= fPrevious && stResult.x <= fValue);
		fPrevious = stResult.x;
	}
	ExposureRead[0] = Float4(2, 2, 0, 0);
	CheckColor(ExtractBloom(Float3(4, 4, 4)), Float3(0.5F, 0.5F, 0.5F));
}

ENGINE_NEXT_TEST("Bloom rejects nonfinite exposure and color without amplifying finite HDR")
{
	ResetBloom();
	CheckColor(SanitizeBloom(Float3(-1, 80000, 2)), Float3(0, 65504, 2));
	for (float fInvalid : { 0.0F, -1.0F, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity() })
	{
		ExposureRead[0] = Float4(fInvalid, 1, 0, 0);
		CheckColor(ExtractBloom(Float3(8, 8, 8)), Float3(0, 0, 0));
		ExposureRead[0] = Float4(1, 1, 0, 0);
		ExposureWrite[0] = Float4(fInvalid, 1, 0, 0);
		CheckColor(ExtractBloom(Float3(8, 8, 8)), Float3(0, 0, 0));
		ExposureWrite[0] = Float4(1, 1, 0, 0);
	}
	CheckColor(ExtractBloom(Float3(std::numeric_limits<float>::quiet_NaN(), 8, 8)), Float3(0, 0, 0));
	Parameters = Float4(1, 65504, 1, 0.5F);
	const Float3 stMaximum = ExtractBloom(Float3(65504, 65504, 65504));
	CheckColor(stMaximum, Float3(16376, 16376, 16376));
	Parameters = Float4(1, 0, 0, 0.5F);
	CheckColor(ExtractBloom(Float3(4, 6, 8)), Float3(4, 6, 8));
}

ENGINE_NEXT_TEST("Bloom first downsample extracts subpixel highlights before filtering")
{
	ResetBloom(2, 2);
	Parameters = Float4(0.1F, 3, 0, 0.5F);
	SourceColor.arrValues[0] = Float4(8, 8, 8, 0);
	CheckColor(SampleBloom(SourceColor, Float2(0.5F, 0.5F), true), Float3(1.25F, 1.25F, 1.25F));
	// Filtering first would reduce this isolated highlight below the hard threshold.
	CheckColor(ExtractBloom(SampleBloom(SourceColor, Float2(0.5F, 0.5F), false)), Float3(0, 0, 0));
	Modes = Float4(1, 0, 0, 0);
	CheckColor(DownsampleBloom(Float2(0.5F, 0.5F)), Float3(1.25F, 1.25F, 1.25F));
}

ENGINE_NEXT_TEST("Bloom normalized tent preserves constant colors at odd and clamped extents")
{
	for (const std::array<std::uint32_t, 2> arrSize : { std::array<std::uint32_t, 2>{ 1, 1 }, { 3, 5 }, { 8, 7 } })
	{
		ResetBloom(arrSize[0], arrSize[1]);
		SourceColor.Reset(arrSize[0], arrSize[1], Float4(4, 2, 1, 0));
		for (const Float2 stUv : { Float2(0, 0), Float2(0.37F, 0.61F), Float2(1, 1) })
		{
			CheckColor(DownsampleBloom(stUv), Float3(4, 2, 1));
		}
	}
}

ENGINE_NEXT_TEST("Bloom interior impulse preserves area weighted energy across downsample")
{
	ResetBloom(8, 8);
	SourceColor.arrValues[3 * 8 + 3] = Float4(16, 8, 4, 0);
	Float3 stTotal(0, 0, 0);
	for (std::uint32_t nY = 0; nY < 4; ++nY)
	{
		for (std::uint32_t nX = 0; nX < 4; ++nX)
		{
			stTotal += DownsampleBloom(Float2((nX + 0.5F) / 4, (nY + 0.5F) / 4));
		}
	}
	CheckColor(stTotal * 4, Float3(16, 8, 4));
}

ENGINE_NEXT_TEST("Bloom upsample blends normalized coarse energy with the local mip")
{
	ResetBloom(5, 3);
	SourceColor.Reset(5, 3, Float4(4, 2, 1, 0));
	LowerColor.Reset(3, 2, Float4(8, 6, 3, 0));
	for (float fScatter : { 0.0F, 0.5F, 1.0F })
	{
		Parameters = Float4(0.1F, 1, 0.5F, fScatter);
		CheckColor(UpsampleBloom(Int2(0, 0), Float2(0, 0)), lerp(Float3(4, 2, 1), Float3(8, 6, 3), fScatter));
		CheckColor(UpsampleBloom(Int2(4, 2), Float2(1, 1)), lerp(Float3(4, 2, 1), Float3(8, 6, 3), fScatter));
	}
	LowerColor.Reset(3, 2, Float4(4, 2, 1, 0));
	CheckColor(UpsampleBloom(Int2(2, 1), Float2(0.5F, 0.5F)), Float3(4, 2, 1));
}
