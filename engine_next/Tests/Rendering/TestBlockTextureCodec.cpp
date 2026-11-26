/**************************************************************************/
/*  TestBlockTextureCodec.cpp                                             */
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
#include "engine_next/Rendering/Cook/BlockTextureCodec.h"
#include "engine_next/Rendering/Cook/ImageDecoder.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <thread>

namespace
{
using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::BuildMipChain;
using EngineNext::Rendering::ComputeTextureMipLayout;
using EngineNext::Rendering::CookedTextureVariant;
using EngineNext::Rendering::DecodedImage;
using EngineNext::Rendering::DecodeTextureMip;
using EngineNext::Rendering::EncodedTextureMip;
using EngineNext::Rendering::EncodeTextureMips;
using EngineNext::Rendering::ImageSemantic;
using EngineNext::Rendering::TextureAlphaPolicy;
using EngineNext::Rendering::TextureFormat;
using EngineNext::Rendering::TextureMipLayout;
using EngineNext::Rendering::TextureNormalEncoding;

CookedTextureVariant Source(ImageSemantic eSemantic, std::uint32_t nWidth = 16, std::uint32_t nHeight = 16, bool bAlpha = false)
{
	DecodedImage stImage;
	stImage.nWidth = nWidth;
	stImage.nHeight = nHeight;
	for (std::uint32_t nY = 0; nY < nHeight; ++nY)
	{
		for (std::uint32_t nX = 0; nX < nWidth; ++nX)
		{
			if (eSemantic == ImageSemantic::Normal)
			{
				stImage.arrRgba8.insert(stImage.arrRgba8.end(), { 128, 128, 255, 255 });
			}
			else
			{
				stImage.arrRgba8.insert(stImage.arrRgba8.end(), { static_cast<std::uint8_t>(nX * 255 / nWidth), static_cast<std::uint8_t>(nY * 255 / nHeight), static_cast<std::uint8_t>((nX + nY) * 127 / (nWidth + nHeight)), static_cast<std::uint8_t>(bAlpha ? nX * 255 / nWidth : 255) });
			}
		}
	}
	CookedTextureVariant stSource;
	stSource.eSemantic = eSemantic;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildMipChain(stImage, eSemantic, stSource.arrMips, arrDiagnostics));
	return stSource;
}
} // namespace

ENGINE_NEXT_TEST("Block texture encoding initializes safely for concurrent deterministic callers")
{
	const CookedTextureVariant stSource = Source(ImageSemantic::Srgb);
	std::array<CookedTextureVariant, 8> arrResults;
	std::array<bool, 8> arrSuccess{};
	std::array<std::thread, 8> arrThreads;
	for (std::size_t nIndex = 0; nIndex < arrThreads.size(); ++nIndex)
	{
		arrThreads[nIndex] = std::thread([&stSource, &arrResults, &arrSuccess, nIndex]()
										 {
			Diagnostics arrDiagnostics;
			arrSuccess[nIndex] = EncodeTextureMips(stSource, arrResults[nIndex], arrDiagnostics); });
	}
	for (std::thread &stThread : arrThreads)
	{
		stThread.join();
	}
	for (std::size_t nIndex = 0; nIndex < arrResults.size(); ++nIndex)
	{
		ENGINE_NEXT_CHECK(arrSuccess[nIndex]);
		ENGINE_NEXT_CHECK(arrResults[nIndex].arrMips.empty());
		ENGINE_NEXT_CHECK_EQ(arrResults[nIndex].arrEncodedMips.size(), 5U);
		for (std::size_t nMip = 0; nMip < 5; ++nMip)
		{
			ENGINE_NEXT_CHECK_EQ(arrResults[nIndex].arrEncodedMips[nMip].arrBytes, arrResults[0].arrEncodedMips[nMip].arrBytes);
		}
	}
}

ENGINE_NEXT_TEST("Block mip layouts account for edge blocks tiny levels and bounds")
{
	for (std::uint32_t nWidth : { 1U, 2U, 3U, 4U, 5U, 7U, 8U, 8192U })
	{
		for (std::uint32_t nHeight : { 1U, 3U, 4U, 9U, 8192U })
		{
			for (TextureFormat eFormat : { TextureFormat::Bc7, TextureFormat::Bc5, TextureFormat::Rgba8 })
			{
				TextureMipLayout stLayout;
				ENGINE_NEXT_CHECK(ComputeTextureMipLayout(nWidth, nHeight, eFormat, stLayout));
				const bool bBlock = eFormat != TextureFormat::Rgba8;
				ENGINE_NEXT_CHECK_EQ(stLayout.nRowBytes, bBlock ? ((nWidth + 3) / 4) * 16 : nWidth * 4);
				ENGINE_NEXT_CHECK_EQ(stLayout.nRows, bBlock ? (nHeight + 3) / 4 : nHeight);
				ENGINE_NEXT_CHECK_EQ(stLayout.nBytes, static_cast<std::uint64_t>(stLayout.nRowBytes) * stLayout.nRows);
			}
		}
	}
	TextureMipLayout stSentinel;
	stSentinel.nBytes = 7;
	ENGINE_NEXT_CHECK(!ComputeTextureMipLayout(0, 4, TextureFormat::Bc7, stSentinel));
	ENGINE_NEXT_CHECK(!ComputeTextureMipLayout(UINT32_MAX, 4, TextureFormat::Bc7, stSentinel));
	ENGINE_NEXT_CHECK(!ComputeTextureMipLayout(4, 8193, TextureFormat::Bc7, stSentinel));
	ENGINE_NEXT_CHECK(!ComputeTextureMipLayout(4, 4, static_cast<TextureFormat>(99), stSentinel));
	ENGINE_NEXT_CHECK_EQ(stSentinel.nBytes, 7U);
}

ENGINE_NEXT_TEST("BC7 preserves semantic mip bytes within measured color alpha error")
{
	for (ImageSemantic eSemantic : { ImageSemantic::Srgb, ImageSemantic::Linear })
	{
		for (bool bAlpha : { false, true })
		{
			const CookedTextureVariant stSource = Source(eSemantic, 16, 16, bAlpha);
			CookedTextureVariant stEncoded;
			Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(EncodeTextureMips(stSource, stEncoded, arrDiagnostics));
			ENGINE_NEXT_CHECK_EQ(stEncoded.eSemantic, eSemantic);
			std::size_t nSourceBytes = 0;
			std::size_t nEncodedBytes = 0;
			for (std::size_t nMip = 0; nMip < stEncoded.arrEncodedMips.size(); ++nMip)
			{
				const EncodedTextureMip &stMip = stEncoded.arrEncodedMips[nMip];
				ENGINE_NEXT_CHECK_EQ(stMip.eFormat, TextureFormat::Bc7);
				DecodedImage stDecoded;
				ENGINE_NEXT_CHECK(DecodeTextureMip(stMip, stEncoded.eNormalEncoding, stDecoded, arrDiagnostics));
				const std::vector<std::uint8_t> &arrExpected = stSource.arrMips[nMip].arrRgba8;
				ENGINE_NEXT_CHECK_EQ(stDecoded.arrRgba8.size(), arrExpected.size());
				double dError = 0;
				std::uint32_t nMaximumError = 0;
				for (std::size_t nByte = 0; nByte < arrExpected.size(); ++nByte)
				{
					const int nDifference = static_cast<int>(arrExpected[nByte]) - stDecoded.arrRgba8[nByte];
					dError += nDifference * nDifference;
					nMaximumError = (std::max)(nMaximumError, static_cast<std::uint32_t>(std::abs(nDifference)));
				}
				// This synthetic 2D ramp spans the complete range inside one
				// coarse 4x4 block. Keep the measured lossy bound explicit;
				// it is not a general visual-quality acceptance threshold.
				ENGINE_NEXT_CHECK(std::sqrt(dError / arrExpected.size()) <= (nMip == 0 ? 6.1 : 24.0));
				ENGINE_NEXT_CHECK(nMaximumError <= 40);
				nSourceBytes += arrExpected.size();
				nEncodedBytes += stMip.arrBytes.size();
			}
			ENGINE_NEXT_CHECK(nEncodedBytes < nSourceBytes / 3);
		}
	}
}

ENGINE_NEXT_TEST("BC5 requires positive Z unit normals and retains tangent channel orientation")
{
	CookedTextureVariant stSource = Source(ImageSemantic::Normal);
	CookedTextureVariant stEncoded;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EncodeTextureMips(stSource, stEncoded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stEncoded.eNormalEncoding, TextureNormalEncoding::PositiveZ);
	for (const EncodedTextureMip &stMip : stEncoded.arrEncodedMips)
	{
		ENGINE_NEXT_CHECK_EQ(stMip.eFormat, TextureFormat::Bc5);
		DecodedImage stDecoded;
		ENGINE_NEXT_CHECK(DecodeTextureMip(stMip, stEncoded.eNormalEncoding, stDecoded, arrDiagnostics));
		for (std::size_t nByte = 0; nByte < stDecoded.arrRgba8.size(); nByte += 4)
		{
			ENGINE_NEXT_CHECK_EQ(stDecoded.arrRgba8[nByte], 128U);
			ENGINE_NEXT_CHECK_EQ(stDecoded.arrRgba8[nByte + 1], 128U);
			ENGINE_NEXT_CHECK_EQ(stDecoded.arrRgba8[nByte + 2], 255U);
			ENGINE_NEXT_CHECK_EQ(stDecoded.arrRgba8[nByte + 3], 255U);
		}
	}
	for (std::array<std::uint8_t, 4> arrPixel : { std::array<std::uint8_t, 4>{ 128, 128, 0, 255 }, { 128, 128, 128, 255 }, { 128, 128, 255, 0 } })
	{
		for (std::size_t nByte = 0; nByte < 4; ++nByte)
		{
			stSource.arrMips[0].arrRgba8[nByte] = arrPixel[nByte];
		}
		ENGINE_NEXT_CHECK(EncodeTextureMips(stSource, stEncoded, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stEncoded.eNormalEncoding, TextureNormalEncoding::Cartesian);
		ENGINE_NEXT_CHECK_EQ(stEncoded.arrEncodedMips[0].eFormat, TextureFormat::Bc7);
	}
}

ENGINE_NEXT_TEST("BC5 varying normals preserve XY orientation and bounded angular error")
{
	DecodedImage stImage;
	stImage.nWidth = 16;
	stImage.nHeight = 16;
	for (std::uint32_t nY = 0; nY < 16; ++nY)
	{
		for (std::uint32_t nX = 0; nX < 16; ++nX)
		{
			const double dX = -.45 + .9 * nX / 15;
			const double dY = -.30 + .6 * nY / 15;
			const double dZ = std::sqrt(1 - dX * dX - dY * dY);
			for (double dChannel : { dX, dY, dZ })
			{
				stImage.arrRgba8.push_back(static_cast<std::uint8_t>(std::floor((dChannel + 1) * 127.5 + .5)));
			}
			stImage.arrRgba8.push_back(255);
		}
	}
	CookedTextureVariant stSource;
	stSource.eSemantic = ImageSemantic::Normal;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildMipChain(stImage, ImageSemantic::Normal, stSource.arrMips, arrDiagnostics));
	CookedTextureVariant stEncoded;
	ENGINE_NEXT_CHECK(EncodeTextureMips(stSource, stEncoded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stEncoded.eNormalEncoding, TextureNormalEncoding::PositiveZ);
	for (std::size_t nMip = 0; nMip < stSource.arrMips.size(); ++nMip)
	{
		DecodedImage stDecoded;
		ENGINE_NEXT_CHECK(DecodeTextureMip(stEncoded.arrEncodedMips[nMip], stEncoded.eNormalEncoding, stDecoded, arrDiagnostics));
		for (std::size_t nPixel = 0; nPixel < stDecoded.arrRgba8.size(); nPixel += 4)
		{
			double dDot = 0;
			double dLengthA = 0;
			double dLengthB = 0;
			for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
			{
				const double dA = stSource.arrMips[nMip].arrRgba8[nPixel + nChannel] * (2.0 / 255.0) - 1;
				const double dB = stDecoded.arrRgba8[nPixel + nChannel] * (2.0 / 255.0) - 1;
				dDot += dA * dB;
				dLengthA += dA * dA;
				dLengthB += dB * dB;
			}
			ENGINE_NEXT_CHECK(dDot / std::sqrt(dLengthA * dLengthB) >= .99939); // Two degrees.
		}
	}
}

ENGINE_NEXT_TEST("Tiny and nonblock base dimensions keep exact RGBA fallback throughout the chain")
{
	for (std::array<std::uint32_t, 2> arrSize : { std::array<std::uint32_t, 2>{ 1, 1 }, { 2, 2 }, { 5, 7 }, { 8, 5 } })
	{
		const CookedTextureVariant stSource = Source(ImageSemantic::Srgb, arrSize[0], arrSize[1], true);
		CookedTextureVariant stEncoded;
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(EncodeTextureMips(stSource, stEncoded, arrDiagnostics));
		for (std::size_t nMip = 0; nMip < stSource.arrMips.size(); ++nMip)
		{
			ENGINE_NEXT_CHECK_EQ(stEncoded.arrEncodedMips[nMip].eFormat, TextureFormat::Rgba8);
			ENGINE_NEXT_CHECK_EQ(stEncoded.arrEncodedMips[nMip].arrBytes, stSource.arrMips[nMip].arrRgba8);
		}
	}
}

ENGINE_NEXT_TEST("Malformed texture chains and encoded payloads leave outputs unchanged")
{
	const CookedTextureVariant stOriginal = Source(ImageSemantic::Linear);
	CookedTextureVariant stSentinel;
	stSentinel.nImage = 99;
	Diagnostics arrDiagnostics;
	for (std::uint32_t nCase = 0; nCase < 6; ++nCase)
	{
		CookedTextureVariant stBad = stOriginal;
		if (nCase == 0)
		{
			stBad.arrMips[0].arrRgba8.pop_back();
		}
		if (nCase == 1)
		{
			stBad.arrMips[1].nWidth = 3;
		}
		if (nCase == 2)
		{
			stBad.arrMips.pop_back();
		}
		if (nCase == 3)
		{
			stBad.arrMips.push_back(stBad.arrMips.back());
		}
		if (nCase == 4)
		{
			stBad.eSemantic = static_cast<ImageSemantic>(99);
		}
		if (nCase == 5)
		{
			stBad.eAlphaPolicy = static_cast<TextureAlphaPolicy>(99);
		}
		ENGINE_NEXT_CHECK(!EncodeTextureMips(stBad, stSentinel, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stSentinel.nImage, 99U);
	}
	ENGINE_NEXT_CHECK(!EncodeTextureMips(stOriginal, stSentinel, arrDiagnostics, 1));
	ENGINE_NEXT_CHECK_EQ(stSentinel.nImage, 99U);
	CookedTextureVariant stEncoded;
	ENGINE_NEXT_CHECK(EncodeTextureMips(stOriginal, stEncoded, arrDiagnostics));
	DecodedImage stOutput;
	stOutput.nWidth = 99;
	EncodedTextureMip stBad = stEncoded.arrEncodedMips[0];
	stBad.arrBytes.pop_back();
	ENGINE_NEXT_CHECK(!DecodeTextureMip(stBad, TextureNormalEncoding::Cartesian, stOutput, arrDiagnostics));
	stBad = stEncoded.arrEncodedMips[0];
	stBad.arrBytes.assign(stBad.arrBytes.size(), 0);
	ENGINE_NEXT_CHECK(!DecodeTextureMip(stBad, TextureNormalEncoding::Cartesian, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.nWidth, 99U);
}
