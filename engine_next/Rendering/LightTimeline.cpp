/**************************************************************************/
/*  LightTimeline.cpp                                                     */
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

#include "engine_next/include/EngineNext/Rendering/LightTimeline.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <iterator>

namespace EngineNext::Rendering
{
namespace
{

bool Fail(const char *pMessage, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "light_animation", "$.light_animation", pMessage);
	return false;
}

} // namespace

bool ValidateLightAnimation(const LightAnimationSettings &stSettings, double dBaseIlluminance,
							Assets::Diagnostics &out_arrDiagnostics)
{
	if (!std::isfinite(dBaseIlluminance) || dBaseIlluminance < 0 || dBaseIlluminance > 1e6)
	{
		return Fail("Base directional illuminance must be finite and in [0,1e6].", out_arrDiagnostics);
	}
	if (stSettings.eInterpolation != LightInterpolation::Linear && stSettings.eInterpolation != LightInterpolation::Step)
	{
		return Fail("Unsupported light interpolation.", out_arrDiagnostics);
	}
	if (stSettings.arrKeyframes.size() > MAX_LIGHT_KEYFRAMES)
	{
		return Fail("Light animation exceeds 256 keyframes.", out_arrDiagnostics);
	}
	double dPreviousTime = -1;
	for (std::size_t nKey = 0; nKey < stSettings.arrKeyframes.size(); ++nKey)
	{
		const LightKeyframe &stKey = stSettings.arrKeyframes[nKey];
		if (!std::isfinite(stKey.dSeconds) || stKey.dSeconds < 0 || stKey.dSeconds <= dPreviousTime ||
			(nKey == 0 && stKey.dSeconds != 0))
		{
			return Fail("Light keys must start at zero and have strictly increasing finite times.", out_arrDiagnostics);
		}
		if (!std::isfinite(stKey.dMultiplier) || stKey.dMultiplier < 0)
		{
			return Fail("Light multipliers must be finite and nonnegative.", out_arrDiagnostics);
		}
		// Multiplication handles base zero without a division-by-zero restriction.
		const double dIlluminance = dBaseIlluminance * stKey.dMultiplier;
		if (!std::isfinite(dIlluminance) || dIlluminance > 1e6)
		{
			return Fail("Animated directional illuminance exceeds [0,1e6].", out_arrDiagnostics);
		}
		dPreviousTime = stKey.dSeconds;
	}
	if (stSettings.bLoop && !stSettings.arrKeyframes.empty() && stSettings.arrKeyframes.back().dSeconds <= 0)
	{
		return Fail("A nonempty looping track needs a positive final key time.", out_arrDiagnostics);
	}
	return true;
}

bool EvaluateLightAnimation(const LightAnimationSettings &stSettings, double dBaseIlluminance,
							double dSeconds, double &out_dIlluminance, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateLightAnimation(stSettings, dBaseIlluminance, out_arrDiagnostics))
	{
		return false;
	}
	if (!std::isfinite(dSeconds) || dSeconds < 0)
	{
		return Fail("Light animation evaluation time must be finite and nonnegative.", out_arrDiagnostics);
	}
	if (stSettings.arrKeyframes.empty())
	{
		out_dIlluminance = dBaseIlluminance;
		return true;
	}
	const double dTime = stSettings.bLoop ? std::fmod(dSeconds, stSettings.arrKeyframes.back().dSeconds) : dSeconds;
	const std::vector<LightKeyframe>::const_iterator itNext = std::upper_bound(stSettings.arrKeyframes.begin(), stSettings.arrKeyframes.end(), dTime,
																			   [](double dTimeValue, const LightKeyframe &stKey)
																			   {
																				   return dTimeValue < stKey.dSeconds;
																			   });
	const LightKeyframe &stPrevious = *std::prev(itNext);
	double dIlluminance = dBaseIlluminance * stPrevious.dMultiplier;
	if (stSettings.eInterpolation == LightInterpolation::Linear && itNext != stSettings.arrKeyframes.end())
	{
		const double dNextIlluminance = dBaseIlluminance * itNext->dMultiplier;
		const double dFraction = (dTime - stPrevious.dSeconds) / (itNext->dSeconds - stPrevious.dSeconds);
		dIlluminance += (dNextIlluminance - dIlluminance) * dFraction;
		dIlluminance = std::clamp(dIlluminance, (std::min)(dBaseIlluminance * stPrevious.dMultiplier, dNextIlluminance),
								  (std::max)(dBaseIlluminance * stPrevious.dMultiplier, dNextIlluminance));
	}
	out_dIlluminance = dIlluminance;
	return true;
}

} // namespace EngineNext::Rendering
