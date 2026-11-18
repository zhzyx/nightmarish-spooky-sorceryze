/**************************************************************************/
/*  PostProcessSettings.h                                                 */
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

#pragma once

#include "engine_next/include/EngineNext/Assets/Types.h"

#include <array>
#include <cstdint>
#include <string>

namespace EngineNext::Rendering
{

constexpr std::uint32_t EXPOSURE_HISTOGRAM_BINS = 256;
constexpr double EXPOSURE_LOG_LUMINANCE_MINIMUM = -16;
constexpr double EXPOSURE_LOG_LUMINANCE_MAXIMUM = 24;
constexpr double EXPOSURE_CALIBRATION = 1.2;
constexpr double EXPOSURE_MAX_DELTA_SECONDS = 0.1;

enum class ExposureMode : std::uint8_t
{
	Legacy = 0,
	Manual = 1,
	Automatic = 2,
};

struct ExposureSettings
{
	ExposureMode eMode = ExposureMode::Legacy;
	double dManualEv100 = 10;
	double dCompensationEv = 0;
	double dMinimumEv100 = -16;
	double dMaximumEv100 = 24;
	double dLowPercentile = 0.1;
	double dHighPercentile = 0.9;
	double dLightHalfLife = 0.25;
	double dDarkHalfLife = 0.75;
};

struct BloomSettings
{
	bool bEnabled = false;
	double dIntensity = 0.04;
	double dThreshold = 1;
	double dSoftKnee = 0.5;
	std::uint32_t nMipCount = 6;
};

struct ScreenEffectsSettings
{
	bool bEnabled = false;
	double dSharpening = 0;
	double dVignetteIntensity = 0;
	double dVignetteInnerRadius = 0.4;
	double dVignetteOuterRadius = 0.8;
	std::string strLutAssetId;
	double dLutIntensity = 1;
};

// Pure CPU calculations, callable on any thread with exclusive output access.
// EV100 and auto limits are [-16,24], compensation is [-10,10], percentiles
// satisfy 0 <= low < high <= 1, and half-lives are seconds in [0,10].
// All fields are validated even when their mode is inactive.
[[nodiscard]] bool ValidateExposureSettings(const ExposureSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);
// Intensity is [0,10], threshold is linear exposed luminance in [0,65504],
// soft knee is a fraction [0,1], and mip count is [1,6].
[[nodiscard]] bool ValidateBloomSettings(const BloomSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);
// Sharpening, vignette intensity and LUT intensity are fractions in [0,1].
// Vignette radii use half the shorter viewport edge as one unit and satisfy
// 0 <= inner < outer <= 2. An empty LUT asset uses identity color grading.
[[nodiscard]] bool ValidateScreenEffectsSettings(const ScreenEffectsSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);
// Legacy preserves the supplied multiplier [0.001,1000]. Manual uses
// exp2(compensationEV - manualEV100) / 1.2, with no extra EV clipping.
// Automatic meters 18% gray, applies compensation to the target EV, then
// clamps that target to the configured auto EV range. Black is metered at
// 2^-16. Only automatic mode consumes dMeteredLuminance.
// Multipliers must be finite positive normal binary32 values. This bounds the
// exposure representation; actual HDR products still require GPU range handling.
[[nodiscard]] bool ComputeExposureMultiplier(const ExposureSettings &stSettings, double dLegacyMultiplier, double dMeteredLuminance,
											 double &out_dMultiplier, Assets::Diagnostics &out_arrDiagnostics);
// Adapts in log2 exposure space without overshoot. Lower target multiplier uses
// light half-life, higher uses dark half-life. dt must be finite and nonnegative,
// is bounded to 0.1 seconds, and dt=0 always preserves the previous multiplier.
[[nodiscard]] bool AdaptExposureMultiplier(const ExposureSettings &stSettings, double dPreviousMultiplier, double dTargetMultiplier,
										   double dDeltaSeconds, double &out_dMultiplier, Assets::Diagnostics &out_arrDiagnostics);
// Histogram endpoints saturate to the first/last bucket. Reduction averages
// bucket-center log2 luminance after partial-bucket percentile clipping. Counts
// are unweighted pixels; the fixed 256-bin sum is accumulated in uint64.
// If adjacent percentiles round to the same rank, use that rank's bucket value.
// An empty histogram fails, preserving prior output for caller fallback.
[[nodiscard]] bool MeterExposureHistogram(const std::array<std::uint32_t, EXPOSURE_HISTOGRAM_BINS> &arrHistogram,
										  const ExposureSettings &stSettings, double &out_dLuminance, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
