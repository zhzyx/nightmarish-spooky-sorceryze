/**************************************************************************/
/*  ColorLut.cpp                                                          */
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

#include "engine_next/include/EngineNext/Rendering/ColorLut.h"

#include "engine_next/include/EngineNext/Rendering/ImageData.h"

#include <cstddef>
#include <utility>

namespace EngineNext::Rendering
{

bool BuildColorLut(const DecodedImage &stImage, ColorLut &out_stLut, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint32_t nSize = stImage.nHeight;
	if (nSize < 2 || nSize > 64 || stImage.nWidth != nSize * nSize ||
		stImage.arrRgba8.size() != static_cast<std::size_t>(nSize) * nSize * nSize * 4)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "color_lut_layout", "$.screen_effects.lut_asset_id", "Color LUT requires an N*N by N RGBA8 image with N in [2,64].");
		return false;
	}
	ColorLut stCandidate;
	stCandidate.nSize = nSize;
	stCandidate.arrRgba8.resize(stImage.arrRgba8.size());
	for (std::uint32_t nBlue = 0; nBlue < nSize; ++nBlue)
	{
		for (std::uint32_t nGreen = 0; nGreen < nSize; ++nGreen)
		{
			for (std::uint32_t nRed = 0; nRed < nSize; ++nRed)
			{
				const std::size_t nSource = (static_cast<std::size_t>(nGreen) * stImage.nWidth + nBlue * nSize + nRed) * 4;
				const std::size_t nTarget = ((static_cast<std::size_t>(nBlue) * nSize + nGreen) * nSize + nRed) * 4;
				for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
				{
					stCandidate.arrRgba8[nTarget + nChannel] = stImage.arrRgba8[nSource + nChannel];
				}
				stCandidate.arrRgba8[nTarget + 3] = 255;
			}
		}
	}
	out_stLut = std::move(stCandidate);
	return true;
}

} // namespace EngineNext::Rendering
