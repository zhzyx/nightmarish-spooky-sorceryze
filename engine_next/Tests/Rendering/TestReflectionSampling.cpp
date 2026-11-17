/**************************************************************************/
/*  TestReflectionSampling.cpp                                            */
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

// The adapters execute the production HLSLI with checked texture reads. Shader
// spelling is retained at this language boundary.
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
	float x;
	float y;
	float z;
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
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
	float w;
	Float3 rgb;
	Float4() : Float4(0, 0, 0, 0)
	{
	}
	Float4(float fX, float fY, float fZ, float fW) : w(fW), rgb(fX, fY, fZ)
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

Float2 operator*(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x * stRight.x, stLeft.y * stRight.y };
}
Float2 operator-(Float2 stLeft, float fRight)
{
	return { stLeft.x - fRight, stLeft.y - fRight };
}
Float3 operator+(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y, stLeft.z + stRight.z };
}
Float3 operator+(Float3 stLeft, float fRight)
{
	return { stLeft.x + fRight, stLeft.y + fRight, stLeft.z + fRight };
}
Float3 operator-(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x - stRight.x, stLeft.y - stRight.y, stLeft.z - stRight.z };
}
Float3 operator*(Float3 stLeft, float fRight)
{
	return { stLeft.x * fRight, stLeft.y * fRight, stLeft.z * fRight };
}
Float3 operator/(Float3 stLeft, float fRight)
{
	return { stLeft.x / fRight, stLeft.y / fRight, stLeft.z / fRight };
}
Int2 operator*(Int2 stLeft, int nRight)
{
	return { stLeft.x * nRight, stLeft.y * nRight };
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
	return { stValue.x - std::floor(stValue.x), stValue.y - std::floor(stValue.y) };
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
float abs(float fValue)
{
	return std::abs(fValue);
}
float sqrt(float fValue)
{
	return std::sqrt(fValue);
}
float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}
float min(float fLeft, float fRight)
{
	return (std::min)(fLeft, fRight);
}
float saturate(float fValue)
{
	return std::clamp(fValue, 0.0F, 1.0F);
}
float clamp(float fValue, float fMinimum, float fMaximum)
{
	return std::clamp(fValue, fMinimum, fMaximum);
}
Float2 clamp(Float2 stValue, float fMinimum, float fMaximum)
{
	return { clamp(stValue.x, fMinimum, fMaximum), clamp(stValue.y, fMinimum, fMaximum) };
}
Float3 clamp(Float3 stValue, float fMinimum, float fMaximum)
{
	return { clamp(stValue.x, fMinimum, fMaximum), clamp(stValue.y, fMinimum, fMaximum), clamp(stValue.z, fMinimum, fMaximum) };
}
Int2 clamp(Int2 stValue, Int2 stMinimum, Int2 stMaximum)
{
	return { std::clamp(stValue.x, stMinimum.x, stMaximum.x), std::clamp(stValue.y, stMinimum.y, stMaximum.y) };
}
Float3 lerp(Float3 stLeft, Float3 stRight, float fWeight)
{
	return stLeft + (stRight - stLeft) * fWeight;
}
float smoothstep(float fMinimum, float fMaximum, float fValue)
{
	const float fWeight = saturate((fValue - fMinimum) / (fMaximum - fMinimum));
	return fWeight * fWeight * (3 - 2 * fWeight);
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
		const bool bValid = stPixel.x >= 0 && stPixel.y >= 0 &&
				static_cast<std::uint32_t>(stPixel.x) < nWidth && static_cast<std::uint32_t>(stPixel.y) < nHeight && stPixel.z == 0;
		ENGINE_NEXT_CHECK(bValid);
		return bValid ? arrValues[static_cast<std::size_t>(stPixel.y) * nWidth + stPixel.x] : Value{};
	}
};

using uint = std::uint32_t;
using float2 = Float2;
using float3 = Float3;
using float4 = Float4;
using int2 = Int2;
using int3 = Int3;

#include "engine_next/Rendering/Shaders/ReflectionSampling.hlsli"

void CheckNear(float fActual, float fExpected, float fTolerance = 0.00001F)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(fActual - fExpected) <= fTolerance * (std::max)(1.0F, std::abs(fExpected)));
}

void CheckColor(Float3 stActual, Float3 stExpected)
{
	CheckNear(stActual.x, stExpected.x);
	CheckNear(stActual.y, stExpected.y);
	CheckNear(stActual.z, stExpected.z);
}

} // namespace

ENGINE_NEXT_TEST("Reflection replacement preserves fallback and replaces only environment specular")
{
	const Float3 stBase(8, 5, 3);
	const Float3 stEnvironment(2, 1, 0.5F);
	CheckColor(CompositeReflection(stBase, stEnvironment, Float4(4, 3, 2, 0)), Float3(10, 6, 3.5F));
	CheckColor(CompositeReflection(stBase, stEnvironment, Float4(4, 3, 2, 1)), Float3(12, 8, 5));
	CheckColor(CompositeReflection(stBase, stEnvironment, Float4(4, 3, 2, 0.5F)), Float3(11, 7, 4.25F));
	CheckColor(CompositeReflection(stBase, stEnvironment, Float4(2, 1, 0.5F, 1)), Float3(10, 6, 3.5F));
	CheckColor(CompositeReflection(stBase, stEnvironment, Float4(0, 0, 0, 1)), stBase);
	CheckColor(CompositeReflection(stBase, stEnvironment, Float4(65504, 65504, 65504, 2)), Float3(65504, 65504, 65504));
	CheckColor(CombineReflectionRadiance(stBase, stEnvironment), Float3(10, 6, 3.5F));
	CheckColor(CombineReflectionRadiance(Float3(65504, 65504, 65504), stEnvironment), Float3(65504, 65504, 65504));
}

ENGINE_NEXT_TEST("Reflection split sum weighting is finite bounded and retains material occlusion")
{
	CheckColor(ReflectionBrdfWeight(Float3(1, 0.5F, 0), 0, 1, Float2(0.75F, 0.1F)), Float3(0.13F, 0.13F, 0.13F));
	CheckColor(ReflectionBrdfWeight(Float3(1, 0.5F, 0), 1, 0.5F, Float2(0.75F, 0.1F)), Float3(0.425F, 0.2375F, 0.05F));
	CheckColor(ReflectionBrdfWeight(Float3(1, 1, 1), 1, 0, Float2(1, 1)), Float3(0, 0, 0));
	for (float fInvalid : { std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity() })
	{
		CheckColor(ReflectionBrdfWeight(Float3(1, 1, 1), fInvalid, 1, Float2(1, 0)), Float3(0, 0, 0));
		CheckColor(ReflectionBrdfWeight(Float3(1, 1, 1), 1, 1, Float2(fInvalid, 0)), Float3(0, 0, 0));
		CheckColor(CompositeReflection(Float3(1, 2, 3), Float3(1, 1, 1), Float4(1, 1, 1, fInvalid)), Float3(2, 3, 4));
		CheckColor(CompositeReflection(Float3(1, 2, 3), Float3(1, 1, 1), Float4(fInvalid, 1, 1, 1)), Float3(2, 3, 4));
	}
}

ENGINE_NEXT_TEST("Reflection roughness selects monotonic mip and smoothly reaches fallback")
{
	float fPreviousMip = 0;
	float fPreviousConfidence = 1;
	for (int nStep = 0; nStep <= 100; ++nStep)
	{
		const float fRoughness = static_cast<float>(nStep) / 100;
		const float fMip = ReflectionMipLevel(fRoughness, 5);
		const float fConfidence = ReflectionRoughnessConfidence(fRoughness, 0.8F);
		ENGINE_NEXT_CHECK(fMip >= fPreviousMip && fMip <= 5);
		ENGINE_NEXT_CHECK(fConfidence <= fPreviousConfidence && fConfidence >= 0);
		fPreviousMip = fMip;
		fPreviousConfidence = fConfidence;
	}
	CheckNear(ReflectionMipLevel(0.3F, 5), 1.5F);
	CheckNear(ReflectionMipLevel(1, 0), 0);
	CheckNear(ReflectionMipLevel(1, 30), 5);
	CheckNear(ReflectionRoughnessConfidence(0.64F, 0.8F), 1);
	CheckNear(ReflectionRoughnessConfidence(0.72F, 0.8F), 0.5F);
	CheckNear(ReflectionRoughnessConfidence(0.8F, 0.8F), 0);
	CheckNear(ReflectionRoughnessConfidence(0, 0), 0);
	const float fMinimum = std::numeric_limits<float>::min();
	CheckNear(ReflectionRoughnessConfidence(0, fMinimum), 1);
	CheckNear(ReflectionRoughnessConfidence(fMinimum, fMinimum), 0);
	CheckNear(ReflectionRoughnessConfidence(1, fMinimum), 0);
}

ENGINE_NEXT_TEST("Reflection hit normals reject back facing missing and nonfinite geometry")
{
	CheckNear(ReflectionHitConfidence(Float3(0, 0, 1), Float3(0, 0, -1)), 1);
	CheckNear(ReflectionHitConfidence(Float3(0, 0, 1), Float3(0, 0, 1)), 0);
	CheckNear(ReflectionHitConfidence(Float3(0, 0, 1), Float3(1, 0, 0)), 0);
	CheckNear(ReflectionHitConfidence(Float3(0, 0, 0), Float3(0, 0, -1)), 0);
	CheckNear(ReflectionHitConfidence(Float3(std::numeric_limits<float>::quiet_NaN(), 0, 1), Float3(0, 0, -1)), 0);
	const Float3 stDirection = ReflectionUnitDirection(Float3(1.0e38F, 1.0e38F, 1.0e38F));
	CheckNear(dot(stDirection, stDirection), 1);
	const Float3 stTiny = ReflectionUnitDirection(Float3(1.0e-38F, 0, 0));
	CheckColor(stTiny, Float3(1, 0, 0));
}

ENGINE_NEXT_TEST("Reflection ceil half mip covers odd boundary texels and retains constant radiance")
{
	for (std::uint32_t nWidth : { 1U, 3U, 8U, 17U })
	{
		for (std::uint32_t nHeight : { 1U, 5U, 8U })
		{
			Texture2D<Float4> stTexture;
			stTexture.Reset(nWidth, nHeight, Float4(65504, 8, 0.5F, 1));
			for (std::uint32_t nY = 0; nY < (nHeight + 1) / 2; ++nY)
			{
				for (std::uint32_t nX = 0; nX < (nWidth + 1) / 2; ++nX)
				{
					CheckColor(DownsampleReflection(stTexture, Int2(nX, nY)), Float3(65504, 8, 0.5F));
				}
			}
		}
	}
	Texture2D<Float4> stOdd;
	stOdd.Reset(3, 3, Float4(0, 0, 0, 1));
	stOdd.arrValues[8] = Float4(16, 8, 4, 1);
	CheckColor(DownsampleReflection(stOdd, Int2(1, 1)), Float3(16, 8, 4));
	CheckColor(DownsampleReflection(stOdd, Int2(0, 0)), Float3(0, 0, 0));
}

ENGINE_NEXT_TEST("Reflection bilinear radiance clamps reads and sanitizes individual texels")
{
	Texture2D<Float4> stTexture;
	stTexture.Reset(2, 2, Float4(0, 0, 0, 1));
	stTexture.arrValues[0] = Float4(16, 8, 4, 1);
	CheckColor(SampleReflectionColor(stTexture, Float2(0.5F, 0.5F)), Float3(4, 2, 1));
	CheckColor(SampleReflectionColor(stTexture, Float2(-1, -1)), Float3(16, 8, 4));
	CheckColor(SampleReflectionColor(stTexture, Float2(2, 2)), Float3(0, 0, 0));
	stTexture.arrValues[3] = Float4(std::numeric_limits<float>::quiet_NaN(), 1, 1, 1);
	CheckColor(SampleReflectionColor(stTexture, Float2(0.5F, 0.5F)), Float3(4, 2, 1));
	CheckColor(SampleReflectionColor(stTexture, Float2(std::numeric_limits<float>::infinity(), 0)), Float3(0, 0, 0));
	stTexture.Reset(1, 1, Float4(4, 8, 12, 1));
	CheckColor(SampleReflectionColor(stTexture, Float2(0.37F, 0.61F)), Float3(4, 8, 12));
}
