/**************************************************************************/
/*  TestLightTimeline.cpp                                                 */
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
#include "engine_next/include/EngineNext/Rendering/LightTimeline.h"

#include <cmath>
#include <cstdint>
#include <initializer_list>
#include <limits>
#include <vector>

namespace
{
using EngineNext::Rendering::EvaluateLightAnimation;
using EngineNext::Rendering::LightAnimationSettings;
using EngineNext::Rendering::LightInterpolation;
using EngineNext::Rendering::LightKeyframe;

void CheckValue(const LightAnimationSettings &stSettings, double dBase, double dTime, double dExpected)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	double dResult = -1;
	ENGINE_NEXT_CHECK(EvaluateLightAnimation(stSettings, dBase, dTime, dResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
	ENGINE_NEXT_CHECK(std::isfinite(dResult));
	ENGINE_NEXT_CHECK(std::abs(dResult - dExpected) <= 1e-12 * (1 + std::abs(dExpected)));
}

void CheckInvalid(const LightAnimationSettings &stSettings, double dBase = 3, double dTime = 0)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	double dResult = 42;
	ENGINE_NEXT_CHECK(!EvaluateLightAnimation(stSettings, dBase, dTime, dResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK_EQ(dResult, 42);
}
} // namespace

ENGINE_NEXT_TEST("Light timeline defaults to an identity track and supports empty loops")
{
	LightAnimationSettings stSettings;
	ENGINE_NEXT_CHECK_EQ(stSettings.eInterpolation, LightInterpolation::Linear);
	ENGINE_NEXT_CHECK(!stSettings.bLoop);
	for (bool bLoop : { false, true })
	{
		stSettings.bLoop = bLoop;
		CheckValue(stSettings, 3, 0, 3);
		CheckValue(stSettings, 1e6, 1e100, 1e6);
	}
}

ENGINE_NEXT_TEST("Light timeline interpolates linear endpoints and holds the final value")
{
	LightAnimationSettings stSettings;
	stSettings.arrKeyframes = { { 0, 0.5 }, { 2, 4 }, { 3, 2 } };
	CheckValue(stSettings, 10, 0, 5);
	CheckValue(stSettings, 10, 1, 22.5);
	CheckValue(stSettings, 10, 2, 40);
	CheckValue(stSettings, 10, 2.5, 30);
	CheckValue(stSettings, 10, 3, 20);
	CheckValue(stSettings, 10, std::numeric_limits<double>::max(), 20);
	stSettings.arrKeyframes = { { 0, 2 } };
	CheckValue(stSettings, 10, 0, 20);
	CheckValue(stSettings, 10, 3, 20);
}

ENGINE_NEXT_TEST("Light timeline step transitions occur exactly at key times")
{
	LightAnimationSettings stSettings;
	stSettings.eInterpolation = LightInterpolation::Step;
	stSettings.arrKeyframes = { { 0, 1 }, { 1, 100 }, { 2, 1 } };
	CheckValue(stSettings, 3, std::nextafter(1.0, 0.0), 3);
	CheckValue(stSettings, 3, 1, 300);
	CheckValue(stSettings, 3, std::nextafter(2.0, 0.0), 300);
	CheckValue(stSettings, 3, 2, 3);
	CheckValue(stSettings, 3, 100, 3);
}

ENGINE_NEXT_TEST("Light timeline loops at the last time and permits an explicit wrap jump")
{
	LightAnimationSettings stSettings;
	stSettings.bLoop = true;
	stSettings.arrKeyframes = { { 0, 1 }, { 2, 3 }, { 4, 5 } };
	CheckValue(stSettings, 3, 3, 12);
	CheckValue(stSettings, 3, 4, 3);
	CheckValue(stSettings, 3, 5, 6);
	CheckValue(stSettings, 3, 1e100, 3);
	stSettings.eInterpolation = LightInterpolation::Step;
	CheckValue(stSettings, 3, 3.5, 9);
	CheckValue(stSettings, 3, 4, 3);
	CheckValue(stSettings, 3, 6, 9);
}

ENGINE_NEXT_TEST("Light timeline evaluates out of order without playback state")
{
	LightAnimationSettings stSettings;
	stSettings.arrKeyframes = { { 0, 0 }, { 1, 1 }, { 2, 0 } };
	for (double dTime : { 1.5, 0.25, 2.0, 1.0, 0.0, 0.25 })
	{
		const double dExpected = dTime <= 1 ? dTime * 4 : (2 - dTime) * 4;
		CheckValue(stSettings, 4, dTime, dExpected);
	}
}

ENGINE_NEXT_TEST("Light timeline bounds the resulting illuminance without rejecting zero base")
{
	LightAnimationSettings stSettings;
	stSettings.arrKeyframes = { { 0, std::numeric_limits<double>::max() }, { 1, 0 } };
	CheckValue(stSettings, 0, 0.5, 0);
	CheckInvalid(stSettings, 3);
	stSettings.arrKeyframes = { { 0, 0 }, { 1, 1e6 } };
	CheckValue(stSettings, 1, 0.5, 5e5);
	CheckValue(stSettings, 1, 1, 1e6);
	CheckInvalid(stSettings, std::nextafter(1.0, 2.0));
	stSettings.arrKeyframes = { { 0, 1 }, { std::numeric_limits<double>::denorm_min(), 0 } };
	CheckValue(stSettings, 3, 0, 3);
	CheckValue(stSettings, 3, std::numeric_limits<double>::denorm_min(), 0);
}

ENGINE_NEXT_TEST("Light timeline rejects malformed keys transactionally")
{
	LightAnimationSettings stSettings;
	for (const std::vector<LightKeyframe> &arrKeys : {
				 std::vector<LightKeyframe>{ { 1, 1 } }, { { 0, 1 }, { 0, 2 } }, { { 0, 1 }, { -1, 2 } }, { { 0, -1 } }, { { 0, std::numeric_limits<double>::infinity() } }, { { 0, std::numeric_limits<double>::quiet_NaN() } }, { { 0, 1 }, { std::numeric_limits<double>::infinity(), 2 } } })
	{
		stSettings.arrKeyframes = arrKeys;
		CheckInvalid(stSettings);
	}
	stSettings.arrKeyframes.clear();
	stSettings.eInterpolation = static_cast<LightInterpolation>(255);
	CheckInvalid(stSettings);
	stSettings.eInterpolation = LightInterpolation::Linear;
	stSettings.bLoop = true;
	stSettings.arrKeyframes = { { 0, 1 } };
	CheckInvalid(stSettings);
}

ENGINE_NEXT_TEST("Light timeline validates its key budget and evaluation inputs")
{
	LightAnimationSettings stSettings;
	for (std::uint32_t nKey = 0; nKey < EngineNext::Rendering::MAX_LIGHT_KEYFRAMES; ++nKey)
	{
		stSettings.arrKeyframes.push_back({ static_cast<double>(nKey), 1 });
	}
	CheckValue(stSettings, 3, 200.5, 3);
	stSettings.arrKeyframes.push_back({ 256, 1 });
	CheckInvalid(stSettings);
	stSettings.arrKeyframes.clear();
	for (double dInvalid : { -1.0, std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
	{
		CheckInvalid(stSettings, dInvalid, 0);
		CheckInvalid(stSettings, 3, dInvalid);
	}
	CheckInvalid(stSettings, 1000001, 0);
}
