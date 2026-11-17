/**************************************************************************/
/*  TestVolumeTemporalMath.cpp                                            */
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
#include <initializer_list>
#include <limits>

namespace
{

struct Bool3
{
	bool x;
	bool y;
	bool z;
};
struct Float3
{
	float x;
	float y;
	float z;
};
Float3 operator/(Float3 stValue, float fScale)
{
	return { stValue.x / fScale, stValue.y / fScale, stValue.z / fScale };
}
Float3 operator-(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x - stRight.x, stLeft.y - stRight.y, stLeft.z - stRight.z };
}
Bool3 operator<(Float3 stValue, float fMinimum)
{
	return { stValue.x < fMinimum, stValue.y < fMinimum, stValue.z < fMinimum };
}
bool all(Bool3 stValue)
{
	return stValue.x && stValue.y && stValue.z;
}
bool any(Bool3 stValue)
{
	return stValue.x || stValue.y || stValue.z;
}
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
Bool3 isfinite(Float3 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y), std::isfinite(stValue.z) };
}
float abs(float fValue)
{
	return std::abs(fValue);
}
float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}
float length(Float3 stValue)
{
	return std::sqrt(stValue.x * stValue.x + stValue.y * stValue.y + stValue.z * stValue.z);
}
using float3 = Float3;

#include "engine_next/Rendering/Shaders/VolumeTemporalMath.hlsli"

} // namespace

ENGINE_NEXT_TEST("Volume density history rejects disappeared thin media")
{
	ENGINE_NEXT_CHECK(VolumeDensityMatches(0, 0, .1f));
	ENGINE_NEXT_CHECK(!VolumeDensityMatches(0, 1e-6f, .1f));
	ENGINE_NEXT_CHECK(!VolumeDensityMatches(1e-6f, 0, .1f));
	for (float fScale : { 1e-30f, 1e-6f, 1.0f, 65504.0f })
	{
		ENGINE_NEXT_CHECK(VolumeDensityMatches(fScale, fScale * .99f, .02f));
		ENGINE_NEXT_CHECK(!VolumeDensityMatches(fScale, fScale * .5f, .02f));
	}
}

ENGINE_NEXT_TEST("Volume density helper rejects invalid coefficients and thresholds")
{
	for (float fInvalid : { -1.0f, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN() })
	{
		ENGINE_NEXT_CHECK(!VolumeDensityMatches(fInvalid, 1, .1f));
		ENGINE_NEXT_CHECK(!VolumeDensityMatches(1, fInvalid, .1f));
		ENGINE_NEXT_CHECK(!VolumeDensityMatches(1, 1, fInvalid));
	}
	ENGINE_NEXT_CHECK(!VolumeDensityMatches(1, 1, 1.01f));
	ENGINE_NEXT_CHECK(!VolumeDensityMatches(std::numeric_limits<float>::denorm_min(), 1, .1f));
	ENGINE_NEXT_CHECK(VolumeDensityMatches(std::numeric_limits<float>::min(), std::numeric_limits<float>::min(), 0));
	ENGINE_NEXT_CHECK(VolumeDensityMatches(4, 3, .25f));
	ENGINE_NEXT_CHECK(!VolumeDensityMatches(4, 3, std::nextafter(.25f, 0.0f)));
}

ENGINE_NEXT_TEST("Volume relative signal change is independent of scene brightness")
{
	for (float fScale : { std::numeric_limits<float>::min(), 1e-25f, 1e-6f, 1.0f, 65504.0f, std::numeric_limits<float>::max() / 2 })
	{
		const Float3 stCurrent{ fScale, fScale, fScale };
		ENGINE_NEXT_CHECK_EQ(VolumeRelativeSignalDifference(stCurrent, stCurrent), 0);
		ENGINE_NEXT_CHECK_EQ(VolumeRelativeSignalDifference(stCurrent, { 0, 0, 0 }), 1);
		ENGINE_NEXT_CHECK_EQ(VolumeRelativeSignalDifference({ 0, 0, 0 }, stCurrent), 1);
		if (fScale >= 1e-25f)
		{
			const Float3 stPrevious{ fScale * .5f, fScale * .5f, fScale * .5f };
			ENGINE_NEXT_CHECK(std::abs(VolumeRelativeSignalDifference(stCurrent, stPrevious) - .5f) < 1e-6f);
		}
	}
	ENGINE_NEXT_CHECK_EQ(VolumeRelativeSignalDifference({ 0, 0, 0 }, { 0, 0, 0 }), 0);
}

ENGINE_NEXT_TEST("Volume raw history detects a uniform jump before neighborhood clipping")
{
	const Float3 stCurrent{ 1e-6f, 1e-6f, 1e-6f };
	const Float3 stOldHistory{ 0, 0, 0 };
	const float fDifference = VolumeRelativeSignalDifference(stCurrent, stOldHistory);
	ENGINE_NEXT_CHECK_EQ(fDifference, 1);
	// A uniform neighborhood would clamp old history to current and erase
	// this difference, so the production call must precede that clamp.
	ENGINE_NEXT_CHECK_EQ(VolumeRelativeSignalDifference(stCurrent, stCurrent), 0);
}

ENGINE_NEXT_TEST("Volume signal differences reject invalid radiance without NaN")
{
	for (float fInvalid : { -1.0f, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN() })
	{
		ENGINE_NEXT_CHECK_EQ(VolumeRelativeSignalDifference({ fInvalid, 0, 0 }, { 0, 0, 0 }), 1);
		ENGINE_NEXT_CHECK_EQ(VolumeRelativeSignalDifference({ 0, 0, 0 }, { fInvalid, 0, 0 }), 1);
	}
	const float fMaximum = std::numeric_limits<float>::max();
	ENGINE_NEXT_CHECK(std::isfinite(VolumeRelativeSignalDifference({ fMaximum, 0, 0 }, { 0, fMaximum, 0 })));
}
