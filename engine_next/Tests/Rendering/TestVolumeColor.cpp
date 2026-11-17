/**************************************************************************/
/*  TestVolumeColor.cpp                                                   */
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

struct Float3
{
	float x;
	float y;
	float z;
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
};
using float3 = Float3;
bool isnan(float fValue)
{
	return std::isnan(fValue);
}
float clamp(float fValue, float fMinimum, float fMaximum)
{
	return std::clamp(fValue, fMinimum, fMaximum);
}

#include "engine_next/Rendering/Shaders/VolumeColor.hlsli"

} // namespace

ENGINE_NEXT_TEST("Volume color preserves finite weak values and clamps overflow per channel")
{
	const Float3 stWeak = VolumeColor({ 1.0e-9F, 12, 65504 });
	ENGINE_NEXT_CHECK_EQ(stWeak.x, 1.0e-9F);
	ENGINE_NEXT_CHECK_EQ(stWeak.y, 12);
	ENGINE_NEXT_CHECK_EQ(stWeak.z, 65504);
	const Float3 stOverflow = VolumeColor({ std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(), 8 });
	ENGINE_NEXT_CHECK_EQ(stOverflow.x, 65504);
	ENGINE_NEXT_CHECK_EQ(stOverflow.y, 0);
	ENGINE_NEXT_CHECK_EQ(stOverflow.z, 8);
	const Float3 stInvalid = VolumeColor({ std::numeric_limits<float>::quiet_NaN(), 4, 1.0e30F });
	ENGINE_NEXT_CHECK_EQ(stInvalid.x, 0);
	ENGINE_NEXT_CHECK_EQ(stInvalid.y, 4);
	ENGINE_NEXT_CHECK_EQ(stInvalid.z, 65504);
}

ENGINE_NEXT_TEST("Volume final source saturation retains bright weak-density lighting")
{
	volatile float fIncoming = 6.2e9F;
	volatile float fDensity = 1.0e-9F;
	const Float3 stThin = VolumeColor({ fIncoming * fDensity, 0, 0 });
	ENGINE_NEXT_CHECK(std::abs(stThin.x - 6.2F) < 0.00001F);
	volatile float fBrightIncoming = 2.5e26F;
	volatile float fDense = 65504;
	volatile float fExposure = 5.6e7F;
	const Float3 stBright = VolumeColor({ fBrightIncoming * fDense * fExposure, 2, 3 });
	ENGINE_NEXT_CHECK_EQ(stBright.x, 65504);
	ENGINE_NEXT_CHECK_EQ(stBright.y, 2);
	ENGINE_NEXT_CHECK_EQ(stBright.z, 3);
}
