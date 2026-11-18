/**************************************************************************/
/*  AmbientOcclusionSettings.cpp                                          */
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

#include "engine_next/include/EngineNext/Rendering/AmbientOcclusionSettings.h"

#include <cmath>
#include <limits>

namespace EngineNext::Rendering
{
namespace
{

double RadicalInverse(std::uint32_t nBits)
{
	nBits = (nBits << 16U) | (nBits >> 16U);
	nBits = ((nBits & 0x55555555U) << 1U) | ((nBits & 0xAAAAAAAAU) >> 1U);
	nBits = ((nBits & 0x33333333U) << 2U) | ((nBits & 0xCCCCCCCCU) >> 2U);
	nBits = ((nBits & 0x0F0F0F0FU) << 4U) | ((nBits & 0xF0F0F0F0U) >> 4U);
	nBits = ((nBits & 0x00FF00FFU) << 8U) | ((nBits & 0xFF00FF00U) >> 8U);
	return static_cast<double>(nBits) * 2.3283064365386962890625e-10;
}

} // namespace

bool ValidateAmbientOcclusionSettings(const AmbientOcclusionSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!std::isfinite(stSettings.dRadius) || stSettings.dRadius < std::numeric_limits<float>::min() || stSettings.dRadius > 100.0 ||
		!std::isfinite(stSettings.dNormalBias) || stSettings.dNormalBias < 0.0 || stSettings.dNormalBias >= stSettings.dRadius ||
		!std::isfinite(stSettings.dIntensity) || stSettings.dIntensity < 0.0 || stSettings.dIntensity > 1.0 ||
		stSettings.nSampleCount < 8 || stSettings.nSampleCount > MAX_OCCLUSION_SAMPLES ||
		(stSettings.nSampleCount & (stSettings.nSampleCount - 1)) != 0)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "ambient_occlusion_settings", "$.ambient_occlusion",
							  "Ambient occlusion requires a positive normal binary32 radius up to 100, bias in [0,radius), intensity in [0,1], and a power-of-two sample count in [8,64].");
		return false;
	}
	return true;
}

bool BuildAmbientOcclusionKernel(const AmbientOcclusionSettings &stSettings, OcclusionKernel &out_arrKernel,
								 Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateAmbientOcclusionSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	constexpr double PI = 3.14159265358979323846;
	OcclusionKernel arrKernel{};
	for (std::uint32_t nSample = 0; nSample < stSettings.nSampleCount; ++nSample)
	{
		const double dFraction = (static_cast<double>(nSample) + 0.5) / stSettings.nSampleCount;
		const double dRadius = std::sqrt(dFraction);
		const double dAngle = 2.0 * PI * RadicalInverse(nSample);
		arrKernel[nSample] = { static_cast<float>(dRadius * std::cos(dAngle)), static_cast<float>(dRadius * std::sin(dAngle)),
							   static_cast<float>(std::sqrt(1.0 - dFraction)), static_cast<float>(0.1 + 0.9 * dFraction * dFraction) };
	}
	out_arrKernel = arrKernel;
	return true;
}

} // namespace EngineNext::Rendering
