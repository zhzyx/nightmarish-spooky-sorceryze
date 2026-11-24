/**************************************************************************/
/*  BlockTextureCodec.h                                                   */
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

#include "engine_next/include/EngineNext/Rendering/TextureData.h"
#include "engine_next/include/EngineNext/Assets/Types.h"

#include <cstddef>
#include <cstdint>

namespace EngineNext::Rendering
{

struct TextureMipLayout
{
	std::uint32_t nBlockWidth = 0;
	std::uint32_t nBlockHeight = 0;
	std::uint32_t nBytesPerBlock = 0;
	std::uint32_t nRowBytes = 0;
	std::uint32_t nRows = 0;
	std::uint64_t nBytes = 0;
};

// Pure bounded layout calculation, including partial edge blocks and tiny mips.
// Dimensions are in texels; rows are block rows, never necessarily texel rows.
[[nodiscard]] bool ComputeTextureMipLayout(std::uint32_t nWidth, std::uint32_t nHeight,
										   TextureFormat eFormat, TextureMipLayout &out_stLayout) noexcept;

// Stable recipe identifier includes the exact upstream revision and settings.
// Encoder tables are initialized once before concurrent callers enter them.
[[nodiscard]] const char *BlockTextureRecipe() noexcept;

// Consumes a complete validated semantic RGBA8 chain and returns a distinct
// encoded chain. The caller retains the input; output is unchanged on failure.
// Unsupported BC base dimensions retain RGBA8 without resizing source content.
[[nodiscard]] bool EncodeTextureMips(const CookedTextureVariant &stSource,
									 CookedTextureVariant &out_stEncoded, Assets::Diagnostics &out_arrDiagnostics,
									 std::size_t nByteBudget = 512ULL * 1024 * 1024);

// CPU decoder for verification/tools; it does not perform sRGB transfer or
// premultiply alpha. PositiveZ reconstructs the stored tangent-space normal.
[[nodiscard]] bool DecodeTextureMip(const EncodedTextureMip &stMip,
									TextureNormalEncoding eNormalEncoding, DecodedImage &out_stImage,
									Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
