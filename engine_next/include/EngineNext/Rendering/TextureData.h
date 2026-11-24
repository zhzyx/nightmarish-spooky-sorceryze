/**************************************************************************/
/*  TextureData.h                                                         */
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

#include "engine_next/include/EngineNext/Rendering/ImageData.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

enum class TextureAlphaPolicy : std::uint8_t
{
	Preserve = 0,
	Ignore = 1,
};

// Serialized v4 formats. Color space remains the variant's ImageSemantic;
// compressed payloads must never be interpreted as DecodedImage::arrRgba8.
enum class TextureFormat : std::uint8_t
{
	Rgba8 = 0,
	Bc7 = 1,
	Bc5 = 2,
};

enum class TextureNormalEncoding : std::uint8_t
{
	Cartesian = 0,
	PositiveZ = 1,
};

struct EncodedTextureMip
{
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	TextureFormat eFormat = TextureFormat::Rgba8;
	std::vector<std::uint8_t> arrBytes;
};

struct CookedTextureVariant
{
	std::uint32_t nImage = 0;
	ImageSemantic eSemantic = ImageSemantic::Linear;
	TextureAlphaPolicy eAlphaPolicy = TextureAlphaPolicy::Preserve;
	std::vector<MipLevel> arrMips;
	// v1-v3 use arrMips; v4 uses only arrEncodedMips. PositiveZ denotes BC5
	// tangent-space XY with sqrt(max(0, 1-dot(XY, XY))) reconstruction.
	TextureNormalEncoding eNormalEncoding = TextureNormalEncoding::Cartesian;
	std::vector<EncodedTextureMip> arrEncodedMips;
};

struct CookedMaterialTextures
{
	// Base color, metallic/roughness, normal, occlusion, emissive. A missing
	// source texture uses -1 and the renderer's existing constant fallback.
	std::array<std::int32_t, 5> arrVariants{ -1, -1, -1, -1, -1 };
};

struct MeshTextureCook
{
	std::vector<CookedTextureVariant> arrVariants;
	std::vector<CookedMaterialTextures> arrMaterials;
};

} // namespace EngineNext::Rendering
