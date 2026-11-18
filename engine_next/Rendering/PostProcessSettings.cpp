/**************************************************************************/
/*  PostProcessSettings.cpp                                               */
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

#include "engine_next/include/EngineNext/Rendering/PostProcessSettings.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace EngineNext::Rendering
{
namespace
{

bool InRange(double dValue, double dMinimum, double dMaximum) noexcept
{
	return std::isfinite(dValue) && dValue >= dMinimum && dValue <= dMaximum;
}

bool Fail(const char *pCode, const char *pPath, const char *pMessage, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, pPath, pMessage);
	return false;
}

bool ValidMultiplier(double dValue) noexcept
{
	return InRange(dValue, std::numeric_limits<float>::min(), std::numeric_limits<float>::max());
}

} // namespace

bool ValidateExposureSettings(const ExposureSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stSettings.eMode != ExposureMode::Legacy && stSettings.eMode != ExposureMode::Manual && stSettings.eMode != ExposureMode::Automatic)
	{
		return Fail("exposure_mode", "$.exposure_settings.mode", "Unsupported exposure mode.", out_arrDiagnostics);
	}
	if (!InRange(stSettings.dManualEv100, -16, 24) || !InRange(stSettings.dCompensationEv, -10, 10) ||
		!InRange(stSettings.dMinimumEv100, -16, 24) || !InRange(stSettings.dMaximumEv100, -16, 24) ||
		stSettings.dMinimumEv100 > stSettings.dMaximumEv100)
	{
		return Fail("exposure_ev", "$.exposure_settings", "Exposure EV or compensation is outside its supported range.", out_arrDiagnostics);
	}
	if (!InRange(stSettings.dLowPercentile, 0, 1) || !InRange(stSettings.dHighPercentile, 0, 1) ||
		stSettings.dLowPercentile >= stSettings.dHighPercentile)
	{
		return Fail("exposure_percentile", "$.exposure_settings", "Exposure percentiles require zero <= low < high <= one.", out_arrDiagnostics);
	}
	if (!InRange(stSettings.dLightHalfLife, 0, 10) || !InRange(stSettings.dDarkHalfLife, 0, 10))
	{
		return Fail("exposure_adaptation", "$.exposure_settings", "Exposure half-lives must be finite seconds in [0,10].", out_arrDiagnostics);
	}
	return true;
}

bool ValidateBloomSettings(const BloomSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!InRange(stSettings.dIntensity, 0, 10) || !InRange(stSettings.dThreshold, 0, 65504) || !InRange(stSettings.dSoftKnee, 0, 1) ||
		stSettings.nMipCount < 1 || stSettings.nMipCount > 6)
	{
		return Fail("bloom_range", "$.bloom", "Bloom intensity, threshold, soft knee, or mip count is outside its supported range.", out_arrDiagnostics);
	}
	return true;
}

bool ValidateScreenEffectsSettings(const ScreenEffectsSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!InRange(stSettings.dSharpening, 0, 1) || !InRange(stSettings.dVignetteIntensity, 0, 1) ||
		!InRange(stSettings.dLutIntensity, 0, 1) || !InRange(stSettings.dVignetteInnerRadius, 0, 2) ||
		!InRange(stSettings.dVignetteOuterRadius, 0, 2) || stSettings.dVignetteInnerRadius >= stSettings.dVignetteOuterRadius)
	{
		return Fail("screen_effects_range", "$.screen_effects", "Screen effects require bounded intensities and increasing vignette radii.", out_arrDiagnostics);
	}
	if (!stSettings.strLutAssetId.empty() && !Assets::IsIdentity(stSettings.strLutAssetId))
	{
		return Fail("screen_effects_asset", "$.screen_effects.lut_asset_id", "LUT asset ID is invalid.", out_arrDiagnostics);
	}
	return true;
}

bool ComputeExposureMultiplier(const ExposureSettings &stSettings, double dLegacyMultiplier, double dMeteredLuminance,
							   double &out_dMultiplier, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateExposureSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	double dMultiplier = dLegacyMultiplier;
	if (stSettings.eMode == ExposureMode::Legacy)
	{
		if (!InRange(dMultiplier, 0.001, 1000))
		{
			return Fail("exposure_legacy", "$.exposure", "Legacy exposure multiplier must be in [0.001,1000].", out_arrDiagnostics);
		}
	}
	else
	{
		double dEv = stSettings.dManualEv100 - stSettings.dCompensationEv;
		if (stSettings.eMode == ExposureMode::Automatic)
		{
			if (!std::isfinite(dMeteredLuminance) || dMeteredLuminance < 0)
			{
				return Fail("exposure_luminance", "$.exposure_settings", "Metered luminance must be finite and nonnegative.", out_arrDiagnostics);
			}
			const double dLuminance = (std::max)(dMeteredLuminance, std::exp2(EXPOSURE_LOG_LUMINANCE_MINIMUM));
			dEv = std::log2(dLuminance) - std::log2(0.18 * EXPOSURE_CALIBRATION) - stSettings.dCompensationEv;
			dEv = std::clamp(dEv, stSettings.dMinimumEv100, stSettings.dMaximumEv100);
		}
		dMultiplier = std::exp2(-dEv) / EXPOSURE_CALIBRATION;
	}
	if (!ValidMultiplier(dMultiplier))
	{
		return Fail("exposure_multiplier", "$.exposure_settings", "Exposure multiplier exceeds normal binary32 range.", out_arrDiagnostics);
	}
	out_dMultiplier = dMultiplier;
	return true;
}

bool AdaptExposureMultiplier(const ExposureSettings &stSettings, double dPreviousMultiplier, double dTargetMultiplier,
							 double dDeltaSeconds, double &out_dMultiplier, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateExposureSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	if (!ValidMultiplier(dPreviousMultiplier) || !ValidMultiplier(dTargetMultiplier) || !std::isfinite(dDeltaSeconds) || dDeltaSeconds < 0)
	{
		return Fail("exposure_adaptation", "$.exposure_settings", "Adaptation requires finite positive multipliers and nonnegative time.", out_arrDiagnostics);
	}
	double dMultiplier = dTargetMultiplier;
	if (dDeltaSeconds == 0)
	{
		dMultiplier = dPreviousMultiplier;
	}
	else if (stSettings.eMode == ExposureMode::Automatic)
	{
		const double dHalfLife = dTargetMultiplier < dPreviousMultiplier ? stSettings.dLightHalfLife : stSettings.dDarkHalfLife;
		if (dHalfLife > 0)
		{
			const double dTime = (std::min)(dDeltaSeconds, EXPOSURE_MAX_DELTA_SECONDS);
			const double dAlpha = -std::expm1(-std::log(2.0) * dTime / dHalfLife);
			const double dPreviousLog = std::log2(dPreviousMultiplier);
			const double dTargetLog = std::log2(dTargetMultiplier);
			dMultiplier = std::exp2(dPreviousLog + (dTargetLog - dPreviousLog) * dAlpha);
			dMultiplier = std::clamp(dMultiplier, (std::min)(dPreviousMultiplier, dTargetMultiplier), (std::max)(dPreviousMultiplier, dTargetMultiplier));
		}
	}
	if (!ValidMultiplier(dMultiplier))
	{
		return Fail("exposure_adaptation", "$.exposure_settings", "Adapted exposure exceeds normal binary32 range.", out_arrDiagnostics);
	}
	out_dMultiplier = dMultiplier;
	return true;
}

bool MeterExposureHistogram(const std::array<std::uint32_t, EXPOSURE_HISTOGRAM_BINS> &arrHistogram,
							const ExposureSettings &stSettings, double &out_dLuminance, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateExposureSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	std::uint64_t nTotal = 0;
	for (std::uint32_t nCount : arrHistogram)
	{
		nTotal += nCount;
	}
	if (nTotal == 0)
	{
		return Fail("exposure_histogram", "$.exposure_settings", "Cannot meter an empty histogram.", out_arrDiagnostics);
	}
	const double dLowCount = stSettings.dLowPercentile * static_cast<double>(nTotal);
	const double dHighCount = stSettings.dHighPercentile * static_cast<double>(nTotal);
	// Adjacent valid percentiles can become the same rank after multiplication.
	// The limiting interval has the value of its containing nonempty bucket.
	const bool bCollapsedInterval = dLowCount >= dHighCount;
	double dWeightedLogSum = 0;
	double dWeight = 0;
	double dFallbackLog = EXPOSURE_LOG_LUMINANCE_MINIMUM;
	bool bFoundFallback = false;
	std::uint64_t nBefore = 0;
	for (std::size_t nBin = 0; nBin < arrHistogram.size(); ++nBin)
	{
		const std::uint64_t nAfter = nBefore + arrHistogram[nBin];
		const double dIncluded = (std::max)(0.0, (std::min)(static_cast<double>(nAfter), dHighCount) - (std::max)(static_cast<double>(nBefore), dLowCount));
		const double dLogLuminance = EXPOSURE_LOG_LUMINANCE_MINIMUM +
				(static_cast<double>(nBin) + 0.5) * (EXPOSURE_LOG_LUMINANCE_MAXIMUM - EXPOSURE_LOG_LUMINANCE_MINIMUM) / EXPOSURE_HISTOGRAM_BINS;
		if (arrHistogram[nBin] != 0 && !bFoundFallback)
		{
			dFallbackLog = dLogLuminance;
			bFoundFallback = static_cast<double>(nAfter) > dLowCount;
		}
		dWeightedLogSum += dIncluded * dLogLuminance;
		dWeight += dIncluded;
		nBefore = nAfter;
	}
	if (!bCollapsedInterval && (!(dWeight > 0) || !std::isfinite(dWeightedLogSum)))
	{
		return Fail("exposure_histogram", "$.exposure_settings", "Percentile clipping retained no finite histogram weight.", out_arrDiagnostics);
	}
	const double dLuminance = std::exp2(bCollapsedInterval ? dFallbackLog : dWeightedLogSum / dWeight);
	if (!std::isfinite(dLuminance) || dLuminance <= 0)
	{
		return Fail("exposure_histogram", "$.exposure_settings", "Histogram luminance is not finite and positive.", out_arrDiagnostics);
	}
	out_dLuminance = dLuminance;
	return true;
}

} // namespace EngineNext::Rendering
