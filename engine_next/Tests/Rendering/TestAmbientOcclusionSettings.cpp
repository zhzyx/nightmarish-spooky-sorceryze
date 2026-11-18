/**************************************************************************/
/*  TestAmbientOcclusionSettings.cpp                                      */
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
#include "engine_next/include/EngineNext/Rendering/AmbientOcclusionSettings.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

using EngineNext::Rendering::AmbientOcclusionSettings;
using EngineNext::Rendering::BuildAmbientOcclusionKernel;
using EngineNext::Rendering::MAX_OCCLUSION_SAMPLES;
using EngineNext::Rendering::OcclusionKernel;
using EngineNext::Rendering::ValidateAmbientOcclusionSettings;

namespace
{
// Retain shader intrinsic spelling while compiling the production HLSLI.
float max(float fLeft, float fRight)
{
	return std::max(fLeft, fRight);
}

float saturate(float fValue)
{
	return std::clamp(fValue, 0.0F, 1.0F);
}

#include "engine_next/Rendering/Shaders/AmbientOcclusionMath.hlsli"
} // namespace

ENGINE_NEXT_TEST("Ambient occlusion kernel is deterministic and cosine weighted")
{
	for (std::uint32_t nSamples : { 8U, 16U, 32U, 64U })
	{
		AmbientOcclusionSettings stSettings;
		stSettings.nSampleCount = nSamples;
		OcclusionKernel arrKernel;
		OcclusionKernel arrSecond;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(BuildAmbientOcclusionKernel(stSettings, arrKernel, arrDiagnostics));
		ENGINE_NEXT_CHECK(BuildAmbientOcclusionKernel(stSettings, arrSecond, arrDiagnostics));
		ENGINE_NEXT_CHECK(arrKernel == arrSecond);
		double dMeanCosine = 0.0;
		for (std::uint32_t nIndex = 0; nIndex < MAX_OCCLUSION_SAMPLES; ++nIndex)
		{
			const std::array<float, 4> &arrSample = arrKernel[nIndex];
			if (nIndex >= nSamples)
			{
				ENGINE_NEXT_CHECK((arrSample == std::array<float, 4>{}));
				continue;
			}
			const double dLength = static_cast<double>(arrSample[0]) * arrSample[0] + static_cast<double>(arrSample[1]) * arrSample[1] + static_cast<double>(arrSample[2]) * arrSample[2];
			ENGINE_NEXT_CHECK(std::abs(dLength - 1.0) < 0.000001);
			ENGINE_NEXT_CHECK(arrSample[2] > 0.0F);
			ENGINE_NEXT_CHECK(arrSample[3] > 0.1F && arrSample[3] < 1.0F);
			dMeanCosine += arrSample[2] / nSamples;
		}
		ENGINE_NEXT_CHECK(std::abs(dMeanCosine - 2.0 / 3.0) < 0.01);
	}
}

ENGINE_NEXT_TEST("Ambient occlusion validates inactive settings and preserves an invalid kernel")
{
	AmbientOcclusionSettings stSettings;
	OcclusionKernel arrKernel{};
	arrKernel[0][0] = 42;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	stSettings.dRadius = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!BuildAmbientOcclusionKernel(stSettings, arrKernel, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrKernel[0][0], 42.0F);
	stSettings = {};
	stSettings.nSampleCount = 7;
	ENGINE_NEXT_CHECK(!ValidateAmbientOcclusionSettings(stSettings, arrDiagnostics));
	stSettings.nSampleCount = 12;
	ENGINE_NEXT_CHECK(!ValidateAmbientOcclusionSettings(stSettings, arrDiagnostics));
	stSettings.nSampleCount = 128;
	ENGINE_NEXT_CHECK(!ValidateAmbientOcclusionSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.dNormalBias = stSettings.dRadius;
	ENGINE_NEXT_CHECK(!ValidateAmbientOcclusionSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.dIntensity = 1.01;
	ENGINE_NEXT_CHECK(!ValidateAmbientOcclusionSettings(stSettings, arrDiagnostics));
	stSettings.dIntensity = 0;
	ENGINE_NEXT_CHECK(ValidateAmbientOcclusionSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Ambient occlusion filter preserves visible neighborhoods and weighted visibility")
{
	const std::array<float, 5> arrWeights{ 0.013F, 0.246F, 1.0F, 0.371F, 0.072F };
	const std::array<float, 5> arrVisibility{ 0.0F, 0.2F, 0.5F, 0.9F, 1.0F };
	float fTotalWeight = 0.0F;
	float fVisibleOcclusion = 0.0F;
	float fBlockedOcclusion = 0.0F;
	float fMixedOcclusion = 0.0F;
	double dExpectedVisibility = 0.0;
	for (std::size_t nSample = 0; nSample < arrWeights.size(); ++nSample)
	{
		fTotalWeight += arrWeights[nSample];
		fVisibleOcclusion += AmbientOccludedWeight(1.0F, arrWeights[nSample]);
		fBlockedOcclusion += AmbientOccludedWeight(0.0F, arrWeights[nSample]);
		fMixedOcclusion += AmbientOccludedWeight(arrVisibility[nSample], arrWeights[nSample]);
		dExpectedVisibility += static_cast<double>(arrVisibility[nSample]) * arrWeights[nSample];
	}
	ENGINE_NEXT_CHECK_EQ(AmbientFilteredVisibility(fVisibleOcclusion, fTotalWeight), 1.0F);
	ENGINE_NEXT_CHECK_EQ(AmbientFilteredVisibility(fBlockedOcclusion, fTotalWeight), 0.0F);
	ENGINE_NEXT_CHECK_EQ(AmbientFilteredVisibility(0.0F, 0.0F), 1.0F);
	const float fMixedVisibility = AmbientFilteredVisibility(fMixedOcclusion, fTotalWeight);
	ENGINE_NEXT_CHECK(std::abs(fMixedVisibility - dExpectedVisibility / fTotalWeight) < 0.000001);
	ENGINE_NEXT_CHECK(fMixedVisibility >= 0.0F && fMixedVisibility <= 1.0F);
}
