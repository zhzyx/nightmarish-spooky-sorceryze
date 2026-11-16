/**************************************************************************/
/*  TestEnvironmentLighting.cpp                                           */
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
#include "engine_next/Rendering/Cook/EnvironmentLighting.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>

namespace
{

EngineNext::Rendering::EnvironmentConfig SmallConfig()
{
	EngineNext::Rendering::EnvironmentConfig stConfig;
	stConfig.nEnvironmentSize = 8;
	stConfig.nIrradianceSize = 4;
	stConfig.nBrdfSize = 8;
	stConfig.nSampleCount = 32;
	return stConfig;
}

bool IsFinite(const EngineNext::Rendering::FloatImage &stImage)
{
	if (stImage.arrPixels.size() != static_cast<std::size_t>(stImage.nWidth) * stImage.nHeight)
	{
		return false;
	}
	for (const std::array<float, 4> &arrPixel : stImage.arrPixels)
	{
		for (float fValue : arrPixel)
		{
			if (!std::isfinite(fValue) || fValue < 0)
			{
				return false;
			}
		}
	}
	return true;
}

} // namespace

ENGINE_NEXT_TEST("Environment preprocessing produces finite HDR cubes and complete roughness mips")
{
	EngineNext::Rendering::EnvironmentLighting stLighting;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::GenerateEnvironmentLighting(SmallConfig(), stLighting, strError));
	ENGINE_NEXT_CHECK(strError.empty());
	ENGINE_NEXT_CHECK_EQ(stLighting.arrPrefilteredMips.size(), 4U);
	float fMaximum = 0;
	for (std::size_t nFace = 0; nFace < 6; ++nFace)
	{
		ENGINE_NEXT_CHECK(IsFinite(stLighting.arrEnvironment[nFace]));
		ENGINE_NEXT_CHECK(IsFinite(stLighting.arrIrradiance[nFace]));
		ENGINE_NEXT_CHECK_EQ(stLighting.arrEnvironment[nFace].nWidth, 8U);
		ENGINE_NEXT_CHECK_EQ(stLighting.arrIrradiance[nFace].nWidth, 4U);
		for (const std::array<float, 4> &arrPixel : stLighting.arrEnvironment[nFace].arrPixels)
		{
			fMaximum = (std::max)(fMaximum, arrPixel[2]);
		}
		for (std::size_t nMip = 0; nMip < stLighting.arrPrefilteredMips.size(); ++nMip)
		{
			ENGINE_NEXT_CHECK(IsFinite(stLighting.arrPrefilteredMips[nMip][nFace]));
			ENGINE_NEXT_CHECK_EQ(stLighting.arrPrefilteredMips[nMip][nFace].nWidth, 8U >> nMip);
		}
	}
	ENGINE_NEXT_CHECK(fMaximum > 1.0F);
	ENGINE_NEXT_CHECK(IsFinite(stLighting.stBrdfLut));
	ENGINE_NEXT_CHECK_EQ(stLighting.stBrdfLut.nWidth, 8U);
}

ENGINE_NEXT_TEST("Environment preprocessing preserves constant radiance and Lambert energy")
{
	EngineNext::Rendering::EnvironmentConfig stConfig = SmallConfig();
	stConfig.arrSkyZenith = { 2, 2, 2 };
	stConfig.arrSkyHorizon = { 2, 2, 2 };
	stConfig.arrGround = { 2, 2, 2 };
	stConfig.arrSunRadiance = { 0, 0, 0 };
	EngineNext::Rendering::EnvironmentLighting stLighting;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stLighting, strError));
	for (std::size_t nFace = 0; nFace < 6; ++nFace)
	{
		for (const std::array<float, 4> &arrPixel : stLighting.arrIrradiance[nFace].arrPixels)
		{
			ENGINE_NEXT_CHECK(std::abs(arrPixel[0] - 6.283185307F) < 0.00001F);
		}
		for (const std::array<EngineNext::Rendering::FloatImage, 6> &arrMip : stLighting.arrPrefilteredMips)
		{
			for (const std::array<float, 4> &arrPixel : arrMip[nFace].arrPixels)
			{
				ENGINE_NEXT_CHECK(std::abs(arrPixel[0] - 2.0F) < 0.00001F);
			}
		}
	}
}

ENGINE_NEXT_TEST("Environment preprocessing is deterministic and roughness changes the convolution")
{
	EngineNext::Rendering::EnvironmentLighting stFirst;
	EngineNext::Rendering::EnvironmentLighting stSecond;
	std::string strError;
	const EngineNext::Rendering::EnvironmentConfig stConfig = SmallConfig();
	ENGINE_NEXT_CHECK(EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stFirst, strError));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stSecond, strError));
	for (std::size_t nFace = 0; nFace < 6; ++nFace)
	{
		ENGINE_NEXT_CHECK_EQ(stFirst.arrEnvironment[nFace].arrPixels, stSecond.arrEnvironment[nFace].arrPixels);
		ENGINE_NEXT_CHECK_EQ(stFirst.arrIrradiance[nFace].arrPixels, stSecond.arrIrradiance[nFace].arrPixels);
		for (std::size_t nMip = 0; nMip < stFirst.arrPrefilteredMips.size(); ++nMip)
		{
			ENGINE_NEXT_CHECK_EQ(stFirst.arrPrefilteredMips[nMip][nFace].arrPixels, stSecond.arrPrefilteredMips[nMip][nFace].arrPixels);
		}
	}
	ENGINE_NEXT_CHECK_EQ(stFirst.stBrdfLut.arrPixels, stSecond.stBrdfLut.arrPixels);
	const float fMirrorUp = stFirst.arrPrefilteredMips.front()[2].arrPixels[36][0];
	const float fRoughUp = stFirst.arrPrefilteredMips.back()[2].arrPixels[0][0];
	ENGINE_NEXT_CHECK(std::abs(fMirrorUp - fRoughUp) > 0.01F);
	ENGINE_NEXT_CHECK(stFirst.stBrdfLut.arrPixels[0] != stFirst.stBrdfLut.arrPixels[63]);
}

ENGINE_NEXT_TEST("Environment preprocessing rejects invalid sizes and numeric data transactionally")
{
	EngineNext::Rendering::EnvironmentLighting stLighting;
	std::string strError;
	EngineNext::Rendering::EnvironmentConfig stConfig = SmallConfig();
	ENGINE_NEXT_CHECK(EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stLighting, strError));
	const std::array<float, 4> arrAccepted = stLighting.stBrdfLut.arrPixels[0];
	stConfig.nEnvironmentSize = 7;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stLighting, strError));
	ENGINE_NEXT_CHECK(!strError.empty());
	stConfig = SmallConfig();
	stConfig.arrSunDirection = { 0, 0, 0 };
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stLighting, strError));
	stConfig = SmallConfig();
	stConfig.arrSkyZenith[0] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stLighting, strError));
	stConfig = SmallConfig();
	stConfig.nSampleCount = 1025;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stLighting, strError));
	stConfig = SmallConfig();
	stConfig.arrSunRadiance[0] = 65504;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::GenerateEnvironmentLighting(stConfig, stLighting, strError));
	ENGINE_NEXT_CHECK_EQ(stLighting.stBrdfLut.arrPixels[0], arrAccepted);
}
