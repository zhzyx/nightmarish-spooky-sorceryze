/**************************************************************************/
/*  EnvironmentImportance.cpp                                             */
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

#include "engine_next/Rendering/Cook/EnvironmentImportance.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::uint64_t MAX_EXACT_FLOAT_ENTRIES = 1ULL << 24;

double AreaPrimitive(double dU, double dV) noexcept
{
	return std::atan2(dU * dV, std::sqrt(1 + dU * dU + dV * dV));
}

bool Fail(std::string &out_strError, const char *pMessage)
{
	out_strError = pMessage;
	return false;
}

} // namespace

double EnvironmentTexelSolidAngle(std::uint32_t nX, std::uint32_t nY, std::uint32_t nFaceSize) noexcept
{
	if (nFaceSize == 0 || nX >= nFaceSize || nY >= nFaceSize)
	{
		return 0;
	}
	const double dU0 = 2.0 * nX / nFaceSize - 1;
	const double dU1 = 2.0 * (nX + 1) / nFaceSize - 1;
	const double dV0 = 2.0 * nY / nFaceSize - 1;
	const double dV1 = 2.0 * (nY + 1) / nFaceSize - 1;
	return AreaPrimitive(dU1, dV1) - AreaPrimitive(dU0, dV1) - AreaPrimitive(dU1, dV0) + AreaPrimitive(dU0, dV0);
}

bool BuildEnvironmentImportance(const std::array<FloatImage, 6> &arrFaces, EnvironmentImportance &out_stImportance, std::string &out_strError)
{
	const std::uint32_t nSize = arrFaces[0].nWidth;
	const std::uint64_t nFacePixels = static_cast<std::uint64_t>(nSize) * nSize;
	if (nSize == 0 || nFacePixels > MAX_EXACT_FLOAT_ENTRIES / 6)
	{
		return Fail(out_strError, "Cube dimensions exceed exact float alias indexing.");
	}
	for (const FloatImage &stFace : arrFaces)
	{
		if (stFace.nWidth != nSize || stFace.nHeight != nSize || stFace.arrPixels.size() != nFacePixels)
		{
			return Fail(out_strError, "Expected six equal square HDR faces with complete pixels.");
		}
	}
	const std::uint32_t nCount = static_cast<std::uint32_t>(nFacePixels * 6);
	std::vector<double> arrScaled(nCount);
	double dTotal = 0;
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		const std::uint32_t nFace = static_cast<std::uint32_t>(nIndex / nFacePixels);
		const std::uint32_t nPixel = static_cast<std::uint32_t>(nIndex % nFacePixels);
		const std::array<float, 4> &arrPixel = arrFaces[nFace].arrPixels[nPixel];
		for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
		{
			if (!std::isfinite(arrPixel[nChannel]))
			{
				return Fail(out_strError, "Environment RGB channels must be finite.");
			}
		}
		const double dLuminance = 0.2126 * (std::max)(0.0, static_cast<double>(arrPixel[0])) +
				0.7152 * (std::max)(0.0, static_cast<double>(arrPixel[1])) +
				0.0722 * (std::max)(0.0, static_cast<double>(arrPixel[2]));
		const double dWeight = dLuminance * EnvironmentTexelSolidAngle(nPixel % nSize, nPixel / nSize, nSize);
		arrScaled[nIndex] = dWeight;
		dTotal += dWeight;
	}
	EnvironmentImportance stCandidate;
	stCandidate.nFaceSize = nSize;
	stCandidate.dIntegratedLuminance = dTotal;
	stCandidate.bUniformFallback = dTotal == 0;
	stCandidate.arrEntries.resize(nCount);
	const std::uint32_t nMetadata = (nSize << ENVIRONMENT_SIZE_SHIFT) |
			(stCandidate.bUniformFallback ? ENVIRONMENT_UNIFORM_FALLBACK : 0);
	if (stCandidate.bUniformFallback)
	{
		for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
		{
			stCandidate.arrEntries[nIndex] = { 1, nIndex, 1.0F / nCount, nMetadata };
		}
		out_stImportance = std::move(stCandidate);
		out_strError.clear();
		return true;
	}
	std::vector<std::uint32_t> arrSmall;
	std::vector<std::uint32_t> arrLarge;
	arrSmall.reserve(nCount);
	arrLarge.reserve(nCount);
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		arrScaled[nIndex] = arrScaled[nIndex] / dTotal * nCount;
		stCandidate.arrEntries[nIndex].nAlias = nIndex;
		stCandidate.arrEntries[nIndex].nMetadata = nMetadata;
		if (arrScaled[nIndex] < 1)
		{
			arrSmall.push_back(nIndex);
		}
		else
		{
			arrLarge.push_back(nIndex);
		}
	}
	while (!arrSmall.empty() && !arrLarge.empty())
	{
		const std::uint32_t nSmall = arrSmall.back();
		const std::uint32_t nLarge = arrLarge.back();
		arrSmall.pop_back();
		arrLarge.pop_back();
		float fThreshold = static_cast<float>(std::clamp(arrScaled[nSmall], 0.0, 1.0));
		// A threshold that cannot produce a normal stored PMF is zero on the GPU.
		if (static_cast<double>(fThreshold) / nCount < std::numeric_limits<float>::min())
		{
			fThreshold = 0;
		}
		stCandidate.arrEntries[nSmall].fThreshold = fThreshold;
		stCandidate.arrEntries[nSmall].nAlias = nLarge;
		arrScaled[nLarge] = arrScaled[nLarge] + arrScaled[nSmall] - 1;
		if (arrScaled[nLarge] < 1)
		{
			arrSmall.push_back(nLarge);
		}
		else
		{
			arrLarge.push_back(nLarge);
		}
	}
	// Reconstruct the actual marginal distribution after binary32 thresholds.
	std::fill(arrScaled.begin(), arrScaled.end(), 0.0);
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		const EnvironmentAliasEntry &stEntry = stCandidate.arrEntries[nIndex];
		arrScaled[nIndex] += static_cast<double>(stEntry.fThreshold) / nCount;
		arrScaled[stEntry.nAlias] += (1.0 - stEntry.fThreshold) / nCount;
	}
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		stCandidate.arrEntries[nIndex].fPmf = static_cast<float>(arrScaled[nIndex]);
	}
	out_stImportance = std::move(stCandidate);
	out_strError.clear();
	return true;
}

} // namespace EngineNext::Rendering
