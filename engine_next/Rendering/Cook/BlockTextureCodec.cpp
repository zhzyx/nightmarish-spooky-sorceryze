/**************************************************************************/
/*  BlockTextureCodec.cpp                                                 */
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

#include "engine_next/Rendering/Cook/BlockTextureCodec.h"

// Preserve the upstream anonymous color unions; suppress their extension
// diagnostics only while including these third-party declarations.
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wgnu-anonymous-struct"
#pragma clang diagnostic ignored "-Wnested-anon-types"
#pragma clang diagnostic ignored "-Wmicrosoft-enum-value"
#endif
#include "engine_next/thirdparty/bc7enc/bc7enc.h"
#include "engine_next/thirdparty/bc7enc/bc7decomp.h"
#include "engine_next/thirdparty/bc7enc/rgbcx.h"
#if defined(__clang__)
#pragma clang diagnostic pop
#endif

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <mutex>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::uint32_t MAX_DIMENSION = 8192;
constexpr std::size_t MAX_BYTES = 512ULL * 1024 * 1024;
constexpr std::size_t MAX_LEVELS = 14;
std::once_flag stEncoderInitialization;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "texture_encoding", "$", pMessage);
	return false;
}

void InitializeEncoder()
{
	bc7enc_compress_block_init();
	rgbcx::init();
}

bool PositiveZNormals(const std::vector<MipLevel> &arrMips)
{
	for (const MipLevel &stMip : arrMips)
	{
		for (std::size_t nPixel = 0; nPixel < stMip.arrRgba8.size(); nPixel += 4)
		{
			const double dX = stMip.arrRgba8[nPixel] * (2.0 / 255.0) - 1;
			const double dY = stMip.arrRgba8[nPixel + 1] * (2.0 / 255.0) - 1;
			const double dZ = stMip.arrRgba8[nPixel + 2] * (2.0 / 255.0) - 1;
			const double dReconstructedZ = std::sqrt((std::max)(0.0, 1 - dX * dX - dY * dY));
			// A non-unit source or a negative hemisphere cannot discard its Z.
			// Two UNORM code values cover quantization of an otherwise unit vector.
			if (dZ < 0 || std::abs(dZ - dReconstructedZ) > 2.0 / 255.0 || stMip.arrRgba8[nPixel + 3] != 255)
			{
				return false;
			}
		}
	}
	return true;
}

void ReadBlock(const MipLevel &stMip, std::uint32_t nBlockX, std::uint32_t nBlockY,
			   std::array<color_rgba, 16> &out_arrPixels)
{
	for (std::uint32_t nY = 0; nY < 4; ++nY)
	{
		for (std::uint32_t nX = 0; nX < 4; ++nX)
		{
			const std::uint32_t nSourceX = (std::min)(nBlockX * 4 + nX, stMip.nWidth - 1);
			const std::uint32_t nSourceY = (std::min)(nBlockY * 4 + nY, stMip.nHeight - 1);
			const std::size_t nOffset = (static_cast<std::size_t>(nSourceY) * stMip.nWidth + nSourceX) * 4;
			std::memcpy(out_arrPixels[nY * 4 + nX].m_c, stMip.arrRgba8.data() + nOffset, 4);
		}
	}
}

void CompressMip(const MipLevel &stSource, ImageSemantic eSemantic, EncodedTextureMip &out_stMip,
				 const TextureMipLayout &stLayout)
{
	out_stMip.arrBytes.resize(static_cast<std::size_t>(stLayout.nBytes));
	bc7enc_compress_block_params stParameters{};
	bc7enc_compress_block_params_init(&stParameters);
	stParameters.m_uber_level = 4;
	if (eSemantic != ImageSemantic::Srgb)
	{
		bc7enc_compress_block_params_init_linear_weights(&stParameters);
	}
	for (std::uint32_t nY = 0; nY < stLayout.nRows; ++nY)
	{
		for (std::uint32_t nX = 0; nX < stLayout.nRowBytes / 16; ++nX)
		{
			std::array<color_rgba, 16> arrPixels{};
			ReadBlock(stSource, nX, nY, arrPixels);
			std::uint8_t *pBlock = out_stMip.arrBytes.data() + static_cast<std::size_t>(nY) * stLayout.nRowBytes + nX * 16;
			if (out_stMip.eFormat == TextureFormat::Bc5)
			{
				rgbcx::encode_bc5_hq(pBlock, arrPixels.data()->m_c, 0, 1, 4, 3, rgbcx::BC4_USE_ALL_MODES);
			}
			else
			{
				// The return value reports source transparency; it is not an error.
				(void)bc7enc_compress_block(pBlock, arrPixels.data(), &stParameters);
			}
		}
	}
}
} // namespace

bool ComputeTextureMipLayout(std::uint32_t nWidth, std::uint32_t nHeight,
							 TextureFormat eFormat, TextureMipLayout &out_stLayout) noexcept
{
	if (nWidth == 0 || nHeight == 0 || nWidth > MAX_DIMENSION || nHeight > MAX_DIMENSION ||
		(eFormat != TextureFormat::Rgba8 && eFormat != TextureFormat::Bc7 && eFormat != TextureFormat::Bc5))
	{
		return false;
	}
	TextureMipLayout stLayout;
	stLayout.nBlockWidth = eFormat == TextureFormat::Rgba8 ? 1 : 4;
	stLayout.nBlockHeight = stLayout.nBlockWidth;
	stLayout.nBytesPerBlock = eFormat == TextureFormat::Rgba8 ? 4 : 16;
	stLayout.nRowBytes = ((nWidth + stLayout.nBlockWidth - 1) / stLayout.nBlockWidth) * stLayout.nBytesPerBlock;
	stLayout.nRows = (nHeight + stLayout.nBlockHeight - 1) / stLayout.nBlockHeight;
	stLayout.nBytes = static_cast<std::uint64_t>(stLayout.nRowBytes) * stLayout.nRows;
	out_stLayout = stLayout;
	return true;
}

const char *BlockTextureRecipe() noexcept
{
	return "bc7enc-b9438627eef73a1157e84201b6fa6eb2ffd6d9f0-u4-bc5hq3-semantic-v1";
}

bool EncodeTextureMips(const CookedTextureVariant &stSource, CookedTextureVariant &out_stEncoded,
					   Assets::Diagnostics &out_arrDiagnostics, std::size_t nByteBudget)
{
	if (stSource.arrMips.empty() || stSource.arrMips.size() > MAX_LEVELS || !stSource.arrEncodedMips.empty() ||
		stSource.eNormalEncoding != TextureNormalEncoding::Cartesian || nByteBudget > MAX_BYTES ||
		(stSource.eSemantic != ImageSemantic::Linear && stSource.eSemantic != ImageSemantic::Srgb && stSource.eSemantic != ImageSemantic::Normal) ||
		(stSource.eAlphaPolicy != TextureAlphaPolicy::Preserve && stSource.eAlphaPolicy != TextureAlphaPolicy::Ignore))
	{
		return Fail(out_arrDiagnostics, "Invalid semantic chain, encoding state or byte budget.");
	}
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	for (const MipLevel &stMip : stSource.arrMips)
	{
		TextureMipLayout stLayout;
		if (!ComputeTextureMipLayout(stMip.nWidth, stMip.nHeight, TextureFormat::Rgba8, stLayout) || stMip.arrRgba8.size() != stLayout.nBytes ||
			(nWidth != 0 && (stMip.nWidth != (std::max)(1U, nWidth / 2) || stMip.nHeight != (std::max)(1U, nHeight / 2) || (nWidth == 1 && nHeight == 1))))
		{
			return Fail(out_arrDiagnostics, "RGBA8 mip dimensions, bytes or halving order are invalid.");
		}
		nWidth = stMip.nWidth;
		nHeight = stMip.nHeight;
	}
	if (nWidth != 1 || nHeight != 1)
	{
		return Fail(out_arrDiagnostics, "Texture chain must terminate in a single 1x1 mip.");
	}
	const bool bBlockCompatible = stSource.arrMips[0].nWidth % 4 == 0 && stSource.arrMips[0].nHeight % 4 == 0;
	const bool bPositiveZ = bBlockCompatible && stSource.eSemantic == ImageSemantic::Normal && PositiveZNormals(stSource.arrMips);
	const TextureFormat eFormat = !bBlockCompatible ? TextureFormat::Rgba8 : (bPositiveZ ? TextureFormat::Bc5 : TextureFormat::Bc7);
	CookedTextureVariant stEncoded;
	stEncoded.nImage = stSource.nImage;
	stEncoded.eSemantic = stSource.eSemantic;
	stEncoded.eAlphaPolicy = stSource.eAlphaPolicy;
	stEncoded.eNormalEncoding = bPositiveZ ? TextureNormalEncoding::PositiveZ : TextureNormalEncoding::Cartesian;
	std::size_t nBytes = 0;
	// Validate the entire allocation before initializing or entering the encoder.
	for (const MipLevel &stMip : stSource.arrMips)
	{
		TextureMipLayout stLayout;
		if (!ComputeTextureMipLayout(stMip.nWidth, stMip.nHeight, eFormat, stLayout) || stLayout.nBytes > nByteBudget - nBytes)
		{
			return Fail(out_arrDiagnostics, "Encoded mip chain exceeds the remaining byte budget.");
		}
		nBytes += static_cast<std::size_t>(stLayout.nBytes);
	}
	if (eFormat != TextureFormat::Rgba8)
	{
		std::call_once(stEncoderInitialization, InitializeEncoder);
	}
	for (const MipLevel &stMip : stSource.arrMips)
	{
		EncodedTextureMip stLevel;
		stLevel.nWidth = stMip.nWidth;
		stLevel.nHeight = stMip.nHeight;
		stLevel.eFormat = eFormat;
		if (eFormat == TextureFormat::Rgba8)
		{
			stLevel.arrBytes = stMip.arrRgba8;
		}
		else
		{
			TextureMipLayout stLayout;
			(void)ComputeTextureMipLayout(stMip.nWidth, stMip.nHeight, eFormat, stLayout);
			CompressMip(stMip, stSource.eSemantic, stLevel, stLayout);
		}
		stEncoded.arrEncodedMips.push_back(std::move(stLevel));
	}
	out_stEncoded = std::move(stEncoded);
	return true;
}

bool DecodeTextureMip(const EncodedTextureMip &stMip, TextureNormalEncoding eNormalEncoding,
					  DecodedImage &out_stImage, Assets::Diagnostics &out_arrDiagnostics)
{
	TextureMipLayout stLayout;
	if (!ComputeTextureMipLayout(stMip.nWidth, stMip.nHeight, stMip.eFormat, stLayout) || stMip.arrBytes.size() != stLayout.nBytes ||
		(stMip.eFormat == TextureFormat::Bc5 ? eNormalEncoding != TextureNormalEncoding::PositiveZ : eNormalEncoding != TextureNormalEncoding::Cartesian))
	{
		return Fail(out_arrDiagnostics, "Encoded mip bytes, dimensions or normal reconstruction are invalid.");
	}
	DecodedImage stDecoded;
	stDecoded.nWidth = stMip.nWidth;
	stDecoded.nHeight = stMip.nHeight;
	if (stMip.eFormat == TextureFormat::Rgba8)
	{
		stDecoded.arrRgba8 = stMip.arrBytes;
	}
	else
	{
		std::call_once(stEncoderInitialization, InitializeEncoder);
		stDecoded.arrRgba8.resize(static_cast<std::size_t>(stMip.nWidth) * stMip.nHeight * 4);
		for (std::uint32_t nY = 0; nY < stLayout.nRows; ++nY)
		{
			for (std::uint32_t nX = 0; nX < stLayout.nRowBytes / 16; ++nX)
			{
				std::array<bc7decomp::color_rgba, 16> arrPixels{};
				const std::uint8_t *pBlock = stMip.arrBytes.data() + static_cast<std::size_t>(nY) * stLayout.nRowBytes + nX * 16;
				if (stMip.eFormat == TextureFormat::Bc7)
				{
					if (!bc7decomp::unpack_bc7(pBlock, arrPixels.data()))
					{
						return Fail(out_arrDiagnostics, "Invalid BC7 block mode.");
					}
				}
				else
				{
					rgbcx::unpack_bc5(pBlock, arrPixels.data(), 0, 1, 4);
					for (bc7decomp::color_rgba &stPixel : arrPixels)
					{
						const double dX = stPixel.r * (2.0 / 255.0) - 1;
						const double dY = stPixel.g * (2.0 / 255.0) - 1;
						const double dZ = std::sqrt((std::max)(0.0, 1 - dX * dX - dY * dY));
						stPixel.b = static_cast<std::uint8_t>(std::floor((dZ + 1) * 127.5 + .5));
						stPixel.a = 255;
					}
				}
				for (std::uint32_t nRow = 0; nRow < 4 && nY * 4 + nRow < stMip.nHeight; ++nRow)
				{
					for (std::uint32_t nColumn = 0; nColumn < 4 && nX * 4 + nColumn < stMip.nWidth; ++nColumn)
					{
						const std::size_t nOffset = (static_cast<std::size_t>(nY * 4 + nRow) * stMip.nWidth + nX * 4 + nColumn) * 4;
						std::memcpy(stDecoded.arrRgba8.data() + nOffset, arrPixels[nRow * 4 + nColumn].m_comps, 4);
					}
				}
			}
		}
	}
	out_stImage = std::move(stDecoded);
	return true;
}
} // namespace EngineNext::Rendering
