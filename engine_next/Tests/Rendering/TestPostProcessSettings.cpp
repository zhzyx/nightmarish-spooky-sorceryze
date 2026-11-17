/**************************************************************************/
/*  TestPostProcessSettings.cpp                                           */
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
#include "engine_next/include/EngineNext/Rendering/PostProcessSettings.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>

namespace
{

using EngineNext::Rendering::AdaptExposureMultiplier;
using EngineNext::Rendering::BloomSettings;
using EngineNext::Rendering::ComputeExposureMultiplier;
using EngineNext::Rendering::ExposureMode;
using EngineNext::Rendering::ExposureSettings;
using EngineNext::Rendering::MeterExposureHistogram;
using Histogram = std::array<std::uint32_t, EngineNext::Rendering::EXPOSURE_HISTOGRAM_BINS>;

void CheckNear(double dActual, double dExpected)
{
	ENGINE_NEXT_CHECK(std::isfinite(dActual));
	ENGINE_NEXT_CHECK(std::abs(dActual - dExpected) <= 1e-11 * std::abs(dExpected));
}

bool Exposure(const ExposureSettings &stSettings, double dLegacy, double dLuminance, double &out_dExposure)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return ComputeExposureMultiplier(stSettings, dLegacy, dLuminance, out_dExposure, arrDiagnostics);
}

bool Adapt(const ExposureSettings &stSettings, double dPrevious, double dTarget, double dSeconds, double &out_dExposure)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return AdaptExposureMultiplier(stSettings, dPrevious, dTarget, dSeconds, out_dExposure, arrDiagnostics);
}

double BinLog(std::size_t nBin)
{
	return -16 + (static_cast<double>(nBin) + 0.5) * 40 / 256;
}

} // namespace

ENGINE_NEXT_TEST("Post-process defaults retain legacy exposure and disabled bloom")
{
	ExposureSettings stExposure;
	BloomSettings stBloom;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateExposureSettings(stExposure, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateBloomSettings(stBloom, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stExposure.eMode, ExposureMode::Legacy);
	ENGINE_NEXT_CHECK(!stBloom.bEnabled);
	double dMultiplier = 0;
	ENGINE_NEXT_CHECK(Exposure(stExposure, 321, std::numeric_limits<double>::quiet_NaN(), dMultiplier));
	ENGINE_NEXT_CHECK_EQ(dMultiplier, 321);
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Manual exposure maps EV100 and compensation with calibrated gray")
{
	ExposureSettings stSettings;
	stSettings.eMode = ExposureMode::Manual;
	double dMultiplier = 0;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0, dMultiplier));
	CheckNear(dMultiplier, 1 / (1.2 * 1024));
	CheckNear((0.18 * 1.2 * 1024) * dMultiplier, 0.18);
	stSettings.dCompensationEv = 1;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0, dMultiplier));
	CheckNear(dMultiplier, 2 / (1.2 * 1024));
	stSettings.dCompensationEv = -1;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0, dMultiplier));
	CheckNear(dMultiplier, 0.5 / (1.2 * 1024));
	stSettings.dManualEv100 = -16;
	stSettings.dCompensationEv = 10;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0, dMultiplier));
	CheckNear(dMultiplier, std::exp2(26) / 1.2);
	stSettings.dManualEv100 = 24;
	stSettings.dCompensationEv = -10;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0, dMultiplier));
	CheckNear(dMultiplier, std::exp2(-34) / 1.2);
}

ENGINE_NEXT_TEST("Automatic exposure meters gray and clamps compensated target EV")
{
	ExposureSettings stSettings;
	stSettings.eMode = ExposureMode::Automatic;
	double dMultiplier = 0;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0.18, dMultiplier));
	CheckNear(dMultiplier, 1);
	stSettings.dCompensationEv = 1;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0.18, dMultiplier));
	CheckNear(dMultiplier, 2);
	stSettings.dMinimumEv100 = 0;
	stSettings.dMaximumEv100 = 5;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0, dMultiplier));
	CheckNear(dMultiplier, 1 / 1.2);
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, std::numeric_limits<double>::max(), dMultiplier));
	CheckNear(dMultiplier, std::exp2(-5) / 1.2);
	stSettings.dMinimumEv100 = 3;
	stSettings.dMaximumEv100 = 3;
	ENGINE_NEXT_CHECK(Exposure(stSettings, 0, 0.18, dMultiplier));
	CheckNear(dMultiplier, std::exp2(-3) / 1.2);
}

ENGINE_NEXT_TEST("Exposure adaptation uses EV half-life and bounded elapsed time")
{
	ExposureSettings stSettings;
	stSettings.eMode = ExposureMode::Automatic;
	stSettings.dLightHalfLife = 0.1;
	stSettings.dDarkHalfLife = 0.2;
	double dMultiplier = 0;
	ENGINE_NEXT_CHECK(Adapt(stSettings, 1, 0.25, 0.1, dMultiplier));
	CheckNear(dMultiplier, 0.5);
	ENGINE_NEXT_CHECK(Adapt(stSettings, 1, 0.25, 1000, dMultiplier));
	CheckNear(dMultiplier, 0.5);
	ENGINE_NEXT_CHECK(Adapt(stSettings, 0.25, 1, 0.1, dMultiplier));
	const double dExpectedLog = -2 + 2 * (1 - std::sqrt(0.5));
	CheckNear(dMultiplier, std::exp2(dExpectedLog));
	ENGINE_NEXT_CHECK(Adapt(stSettings, 0.25, 1, 0, dMultiplier));
	ENGINE_NEXT_CHECK_EQ(dMultiplier, 0.25);
	stSettings.dDarkHalfLife = 0;
	ENGINE_NEXT_CHECK(Adapt(stSettings, 0.25, 1, 0.1, dMultiplier));
	ENGINE_NEXT_CHECK_EQ(dMultiplier, 1);
	stSettings.eMode = ExposureMode::Manual;
	ENGINE_NEXT_CHECK(Adapt(stSettings, 0.25, 1, 0.01, dMultiplier));
	ENGINE_NEXT_CHECK_EQ(dMultiplier, 1);
}

ENGINE_NEXT_TEST("Exposure adaptation remains monotonic for all supported half-lives")
{
	ExposureSettings stSettings;
	stSettings.eMode = ExposureMode::Automatic;
	for (double dHalfLife : { 0.0, std::numeric_limits<double>::min(), 0.001, 0.25, 10.0 })
	{
		stSettings.dLightHalfLife = dHalfLife;
		stSettings.dDarkHalfLife = dHalfLife;
		for (double dTarget : { 0.001, 1.0, 1000.0 })
		{
			double dPrevious = 1;
			for (std::uint32_t nStep = 0; nStep < 10; ++nStep)
			{
				double dCurrent = 0;
				ENGINE_NEXT_CHECK(Adapt(stSettings, dPrevious, dTarget, 0.1, dCurrent));
				ENGINE_NEXT_CHECK(std::isfinite(dCurrent));
				ENGINE_NEXT_CHECK(dCurrent >= (std::min)(dPrevious, dTarget));
				ENGINE_NEXT_CHECK(dCurrent <= (std::max)(dPrevious, dTarget));
				dPrevious = dCurrent;
			}
		}
	}
}

ENGINE_NEXT_TEST("Exposure adaptation handles binary32 endpoints without overflow")
{
	ExposureSettings stSettings;
	stSettings.eMode = ExposureMode::Automatic;
	stSettings.dLightHalfLife = 0.1;
	stSettings.dDarkHalfLife = 0.1;
	const double dMinimum = std::numeric_limits<float>::min();
	const double dMaximum = std::numeric_limits<float>::max();
	double dMultiplier = 0;
	ENGINE_NEXT_CHECK(Adapt(stSettings, dMinimum, dMaximum, 0.1, dMultiplier));
	CheckNear(dMultiplier, std::sqrt(dMinimum) * std::sqrt(dMaximum));
	ENGINE_NEXT_CHECK(Adapt(stSettings, dMaximum, dMinimum, 0.1, dMultiplier));
	CheckNear(dMultiplier, std::sqrt(dMinimum) * std::sqrt(dMaximum));
	ENGINE_NEXT_CHECK(Adapt(stSettings, dMaximum, dMaximum, 0.1, dMultiplier));
	ENGINE_NEXT_CHECK_EQ(dMultiplier, dMaximum);
	for (double dInvalid : { std::numeric_limits<double>::min(), std::nextafter(dMaximum, std::numeric_limits<double>::infinity()) })
	{
		dMultiplier = 42;
		ENGINE_NEXT_CHECK(!Adapt(stSettings, dInvalid, 1, 0.1, dMultiplier));
		ENGINE_NEXT_CHECK_EQ(dMultiplier, 42);
		ENGINE_NEXT_CHECK(!Adapt(stSettings, 1, dInvalid, 0.1, dMultiplier));
		ENGINE_NEXT_CHECK_EQ(dMultiplier, 42);
	}
}

ENGINE_NEXT_TEST("Histogram metering clips fractional percentile buckets in log luminance")
{
	ExposureSettings stSettings;
	Histogram arrHistogram{};
	EngineNext::Assets::Diagnostics arrDiagnostics;
	double dLuminance = 0;
	arrHistogram[42] = 100;
	ENGINE_NEXT_CHECK(MeterExposureHistogram(arrHistogram, stSettings, dLuminance, arrDiagnostics));
	CheckNear(dLuminance, std::exp2(BinLog(42)));
	arrHistogram.fill(0);
	arrHistogram[0] = 25;
	arrHistogram[128] = 50;
	arrHistogram[255] = 25;
	stSettings.dLowPercentile = 0.2;
	stSettings.dHighPercentile = 0.6;
	ENGINE_NEXT_CHECK(MeterExposureHistogram(arrHistogram, stSettings, dLuminance, arrDiagnostics));
	CheckNear(dLuminance, std::exp2((5 * BinLog(0) + 35 * BinLog(128)) / 40));
	stSettings.dLowPercentile = 0;
	stSettings.dHighPercentile = 1;
	arrHistogram.fill(std::numeric_limits<std::uint32_t>::max());
	ENGINE_NEXT_CHECK(MeterExposureHistogram(arrHistogram, stSettings, dLuminance, arrDiagnostics));
	CheckNear(dLuminance, std::exp2(4));
}

ENGINE_NEXT_TEST("Invalid exposure inputs preserve previous result and report diagnostics")
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	double dOutput = 42;
	ExposureSettings stSettings;
	ENGINE_NEXT_CHECK(!ComputeExposureMultiplier(stSettings, 0, 0, dOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(dOutput, 42);
	stSettings.eMode = ExposureMode::Automatic;
	for (double dInvalid : { -1.0, std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
	{
		ENGINE_NEXT_CHECK(!ComputeExposureMultiplier(stSettings, 1, dInvalid, dOutput, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(dOutput, 42);
		ENGINE_NEXT_CHECK(!AdaptExposureMultiplier(stSettings, 1, 2, dInvalid, dOutput, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(dOutput, 42);
	}
	ENGINE_NEXT_CHECK(!AdaptExposureMultiplier(stSettings, 0, 1, 0.1, dOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(dOutput, 42);
	Histogram arrEmpty{};
	ENGINE_NEXT_CHECK(!MeterExposureHistogram(arrEmpty, stSettings, dOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(dOutput, 42);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Exposure and bloom reject unsupported settings including inactive fields")
{
	ExposureSettings stSettings;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	stSettings.eMode = static_cast<ExposureMode>(255);
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateExposureSettings(stSettings, arrDiagnostics));
	stSettings = ExposureSettings{};
	stSettings.dLowPercentile = stSettings.dHighPercentile;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateExposureSettings(stSettings, arrDiagnostics));
	stSettings = ExposureSettings{};
	stSettings.dMinimumEv100 = 20;
	stSettings.dMaximumEv100 = 10;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateExposureSettings(stSettings, arrDiagnostics));
	stSettings = ExposureSettings{};
	stSettings.dLightHalfLife = -1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateExposureSettings(stSettings, arrDiagnostics));
	BloomSettings stBloom;
	stBloom.dIntensity = 11;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateBloomSettings(stBloom, arrDiagnostics));
	stBloom = BloomSettings{};
	stBloom.dThreshold = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateBloomSettings(stBloom, arrDiagnostics));
	stBloom = BloomSettings{};
	stBloom.dSoftKnee = 1.1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateBloomSettings(stBloom, arrDiagnostics));
	stBloom = BloomSettings{};
	stBloom.nMipCount = 0;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateBloomSettings(stBloom, arrDiagnostics));
}

ENGINE_NEXT_TEST("Histogram metering retains a legal percentile interval after rank rounding")
{
	Histogram arrHistogram{};
	arrHistogram[17] = 1;
	arrHistogram[93] = 1;
	arrHistogram[200] = 1;
	ExposureSettings stSettings;
	stSettings.dLowPercentile = 0.7087874219010951;
	stSettings.dHighPercentile = 0.7087874219010952;
	ENGINE_NEXT_CHECK(stSettings.dLowPercentile < stSettings.dHighPercentile);
	ENGINE_NEXT_CHECK_EQ(stSettings.dLowPercentile * 3, stSettings.dHighPercentile * 3);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	double dLuminance = 0;
	ENGINE_NEXT_CHECK(MeterExposureHistogram(arrHistogram, stSettings, dLuminance, arrDiagnostics));
	CheckNear(dLuminance, std::exp2(BinLog(200)));
}
