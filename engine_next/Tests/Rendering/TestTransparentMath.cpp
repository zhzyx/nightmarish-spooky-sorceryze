/**************************************************************************/
/*  TestTransparentMath.cpp                                               */
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
#include <limits>

namespace
{

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
};
struct Float4
{
	Float3 rgb;
	float w;
	Float4(Float3 stColor, float fAlpha) : rgb(stColor), w(fAlpha)
	{
	}
};
struct Bool3
{
	bool x;
	bool y;
	bool z;
};
Float3 operator*(Float3 stValue, float fScale)
{
	return { stValue.x * fScale, stValue.y * fScale, stValue.z * fScale };
}
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
Bool3 isfinite(Float3 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y), std::isfinite(stValue.z) };
}
bool all(Bool3 stValue)
{
	return stValue.x && stValue.y && stValue.z;
}
float saturate(float fValue)
{
	return std::clamp(fValue, 0.0F, 1.0F);
}
Float3 clamp(Float3 stValue, float fMinimum, float fMaximum)
{
	return { std::clamp(stValue.x, fMinimum, fMaximum), std::clamp(stValue.y, fMinimum, fMaximum), std::clamp(stValue.z, fMinimum, fMaximum) };
}
using float2 = Float2;
using float3 = Float3;
using float4 = Float4;
#include "engine_next/Rendering/Shaders/TransparentMath.hlsli"

float DeviceDepth(float fDistance)
{
	return .1F * (100 - fDistance) / (fDistance * 99.9F);
}
void Near(float fActual, float fExpected, float fTolerance = .00001F)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(fActual - fExpected) <= fTolerance * (std::max)(1.0F, std::abs(fExpected)));
}

} // namespace

ENGINE_NEXT_TEST("Transparent depth reconstruction preserves reverse Z endpoints")
{
	Near(TransparentLinearDepth(1, { .1F, 100 }), .1F);
	Near(TransparentLinearDepth(0, { .1F, 100 }), 100);
	for (float fDistance : { .1F, 1.0F, 10.0F, 99.0F, 100.0F })
	{
		Near(TransparentLinearDepth(DeviceDepth(fDistance), { .1F, 100 }), fDistance);
	}
}

ENGINE_NEXT_TEST("Transparent soft intersections use linear depth gap and leave sky visible")
{
	Near(TransparentDepthFade(DeviceDepth(5), DeviceDepth(4), { .1F, 100 }, 2, true), .5F);
	Near(TransparentDepthFade(DeviceDepth(5), DeviceDepth(5), { .1F, 100 }, 2, true), 0);
	Near(TransparentDepthFade(DeviceDepth(4), DeviceDepth(5), { .1F, 100 }, 2, true), 0);
	Near(TransparentDepthFade(DeviceDepth(8), DeviceDepth(5), { .1F, 100 }, 2, true), 1);
	Near(TransparentDepthFade(0, DeviceDepth(4), { .1F, 100 }, 2, true), 1);
	Near(TransparentDepthFade(DeviceDepth(4), DeviceDepth(5), { .1F, 100 }, 0, true), 1);
	Near(TransparentDepthFade(DeviceDepth(4), DeviceDepth(5), { .1F, 100 }, 1, false), 1);
	Near(TransparentDepthFade(DeviceDepth(4.001F), DeviceDepth(4), { .1F, 100 }, .01F, true), .1F, .0001F);
}

ENGINE_NEXT_TEST("Transparent premultiplication and reactive alpha share the faded coverage")
{
	const Float3 stColor(8, 4, 2);
	for (float fAlpha : { 0.0F, .25F, 1.0F })
	{
		const float fCoverage = TransparentEffectiveAlpha(fAlpha, .5F);
		const Float4 stResult = TransparentPremultiply(stColor, fCoverage);
		Near(stResult.w, fAlpha * .5F);
		Near(stResult.rgb.x, 8 * stResult.w);
		Near(stResult.rgb.y, 4 * stResult.w);
		Near(stResult.rgb.z, 2 * stResult.w);
	}
	Near(TransparentEffectiveAlpha(2, 2), 1);
	Near(TransparentEffectiveAlpha(-1, .5F), 0);
	const Float4 stClamped = TransparentPremultiply({ 1.0e30F, -1, 2 }, .5F);
	Near(stClamped.rgb.x, 32752);
	Near(stClamped.rgb.y, 0);
}

ENGINE_NEXT_TEST("Transparent helpers reject nonfinite and unsupported parameters")
{
	for (float fInvalid : { std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity(), -1.0F })
	{
		Near(TransparentDepthFade(fInvalid, .5F, { .1F, 100 }, 1, true), 0);
		Near(TransparentDepthFade(.5F, fInvalid, { .1F, 100 }, 1, true), 0);
		Near(TransparentDepthFade(.5F, .5F, { .1F, 100 }, fInvalid, true), 0);
	}
	Near(TransparentDepthFade(.5F, .5F, { 0, 100 }, 1, true), 0);
	Near(TransparentDepthFade(.5F, .5F, { 1, 1 }, 1, true), 0);
	Near(TransparentDepthFade(1.1F, .5F, { .1F, 100 }, 1, true), 0);
	Near(TransparentEffectiveAlpha(std::numeric_limits<float>::quiet_NaN(), 1), 0);
	Near(TransparentEffectiveAlpha(1, std::numeric_limits<float>::infinity()), 0);
	const Float4 stInvalid = TransparentPremultiply({ std::numeric_limits<float>::infinity(), 1, 1 }, .5F);
	Near(stInvalid.rgb.x, 0);
	Near(stInvalid.rgb.y, 0);
	Near(stInvalid.rgb.z, 0);
	Near(stInvalid.w, .5F);
}
