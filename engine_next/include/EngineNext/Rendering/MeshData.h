/**************************************************************************/
/*  MeshData.h                                                            */
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

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

enum class AlphaMode : std::uint8_t
{
	Opaque = 0,
	Mask = 1,
	Blend = 2,
};

struct MeshVertex
{
	std::array<float, 3> arrPosition{};
	std::array<float, 3> arrNormal{ 0.0F, 0.0F, 1.0F };
	std::array<float, 4> arrTangent{ 1.0F, 0.0F, 0.0F, 1.0F };
	std::array<float, 2> arrTexcoord{};
};

struct MaterialData
{
	std::array<float, 4> arrBaseColor{ 1.0F, 1.0F, 1.0F, 1.0F };
	float fMetallic = 1.0F;
	float fRoughness = 1.0F;
	std::array<float, 3> arrEmissive{};
	float fNormalScale = 1.0F;
	float fOcclusionStrength = 1.0F;
	float fAlphaCutoff = 0.5F;
	bool bDoubleSided = false;
	AlphaMode eAlphaMode = AlphaMode::Opaque;
	std::int32_t nBaseColorTexture = -1;
	std::int32_t nMetallicRoughnessTexture = -1;
	std::int32_t nNormalTexture = -1;
	std::int32_t nOcclusionTexture = -1;
	std::int32_t nEmissiveTexture = -1;
};

struct EncodedImage
{
	std::string strMimeType;
	std::vector<std::uint8_t> arrBytes;
};

struct TextureData
{
	std::uint32_t nImage = 0;
	// Values use the glTF sampler constants. Zero filter selects renderer default.
	std::int32_t nMagFilter = 0;
	std::int32_t nMinFilter = 0;
	std::int32_t nWrapS = 10497;
	std::int32_t nWrapT = 10497;
};

struct MeshPrimitive
{
	std::vector<MeshVertex> arrVertices;
	std::vector<std::uint32_t> arrIndices;
	std::int32_t nMaterial = 0;
};

struct MeshInstance
{
	std::uint32_t nPrimitive = 0;
	std::uint32_t nNode = 0;
	// Column-major glTF right-handed Y-up world transform, in meters.
	std::array<double, 16> arrTransform{ 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0 };
};

struct DecodedMesh
{
	std::vector<MeshPrimitive> arrPrimitives;
	std::vector<MaterialData> arrMaterials;
	std::vector<EncodedImage> arrImages;
	std::vector<TextureData> arrTextures;
	std::vector<MeshInstance> arrInstances;
};

} // namespace EngineNext::Rendering
