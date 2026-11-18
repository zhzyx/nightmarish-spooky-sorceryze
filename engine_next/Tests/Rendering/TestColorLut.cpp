/**************************************************************************/
/*  TestColorLut.cpp                                                      */
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
#include "engine_next/include/EngineNext/Rendering/ColorLut.h"
#include "engine_next/include/EngineNext/Rendering/ImageData.h"
#include "engine_next/include/EngineNext/Rendering/PostProcessSettings.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>
#include <initializer_list>

namespace
{
using EngineNext::Rendering::ColorLut;
using EngineNext::Rendering::DecodedImage;
using EngineNext::Rendering::ScreenEffectsSettings;
} //namespace

ENGINE_NEXT_TEST("Color LUT reorders horizontal blue tiles without changing RGB samples")
{
	for (std::uint32_t nSize : { 2U, 3U, 16U, 64U })
	{
		DecodedImage stImage;
		stImage.nWidth = nSize * nSize;
		stImage.nHeight = nSize;
		stImage.arrRgba8.resize(static_cast<std::size_t>(nSize) * nSize * nSize * 4);
		for (std::size_t nIndex = 0; nIndex < stImage.arrRgba8.size(); ++nIndex)
		{
			stImage.arrRgba8[nIndex] = static_cast<std::uint8_t>(nIndex * 73 + nIndex / 4);
		}
		const std::vector<std::uint8_t> arrOriginal = stImage.arrRgba8;
		ColorLut stLut;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildColorLut(stImage, stLut, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stLut.nSize, nSize);
		ENGINE_NEXT_CHECK(stImage.arrRgba8 == arrOriginal);
		for (std::uint32_t nBlue = 0; nBlue < nSize; ++nBlue)
		{
			for (std::uint32_t nGreen = 0; nGreen < nSize; ++nGreen)
			{
				for (std::uint32_t nRed = 0; nRed < nSize; ++nRed)
				{
					const std::size_t nSource = (static_cast<std::size_t>(nGreen) * stImage.nWidth + nBlue * nSize + nRed) * 4;
					const std::size_t nTarget = ((static_cast<std::size_t>(nBlue) * nSize + nGreen) * nSize + nRed) * 4;
					ENGINE_NEXT_CHECK_EQ(stLut.arrRgba8[nTarget], arrOriginal[nSource]);
					ENGINE_NEXT_CHECK_EQ(stLut.arrRgba8[nTarget + 1], arrOriginal[nSource + 1]);
					ENGINE_NEXT_CHECK_EQ(stLut.arrRgba8[nTarget + 2], arrOriginal[nSource + 2]);
					ENGINE_NEXT_CHECK_EQ(stLut.arrRgba8[nTarget + 3], 255);
				}
			}
		}
	}
}

ENGINE_NEXT_TEST("Color LUT rejects malformed sizes and preserves the previous output")
{
	for (const std::array<std::uint32_t, 2> &arrSize : { std::array<std::uint32_t, 2>{ 1, 1 }, { 4225, 65 }, { 5, 2 }, { 4, 0 }, { 4, 2 } })
	{
		DecodedImage stImage;
		stImage.nWidth = arrSize[0];
		stImage.nHeight = arrSize[1];
		ColorLut stLut{ 3, { 7, 8, 9 } };
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildColorLut(stImage, stLut, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stLut.nSize, 3U);
		ENGINE_NEXT_CHECK(stLut.arrRgba8 == std::vector<std::uint8_t>({ 7, 8, 9 }));
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	}
}

ENGINE_NEXT_TEST("Screen effects validate inactive settings and require ordered vignette radii")
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ScreenEffectsSettings stSettings;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateScreenEffectsSettings(stSettings, arrDiagnostics));
	stSettings.dSharpening = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateScreenEffectsSettings(stSettings, arrDiagnostics));
	stSettings = ScreenEffectsSettings{};
	stSettings.dVignetteInnerRadius = stSettings.dVignetteOuterRadius;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateScreenEffectsSettings(stSettings, arrDiagnostics));
	stSettings = ScreenEffectsSettings{};
	stSettings.dLutIntensity = -0.01;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateScreenEffectsSettings(stSettings, arrDiagnostics));
	stSettings = ScreenEffectsSettings{};
	stSettings.strLutAssetId = "not an asset ID";
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateScreenEffectsSettings(stSettings, arrDiagnostics));
}
