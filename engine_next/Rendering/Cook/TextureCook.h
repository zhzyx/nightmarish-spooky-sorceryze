/**************************************************************************/
/*  TextureCook.h                                                         */
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

#include "engine_next/include/EngineNext/Assets/Types.h"
#include "engine_next/include/EngineNext/Rendering/MeshData.h"
#include "engine_next/include/EngineNext/Rendering/TextureData.h"

#include <cstddef>

namespace EngineNext::Rendering
{

// Synchronous CPU cook. The source remains unchanged and output is replaced
// only on success. Variants share pixels by image, color space and alpha policy;
// samplers retain their original per-texture identity in DecodedMesh.
// nByteBudget limits the sum of tightly packed RGBA8 bytes for all mip levels.
// Windows uses the validated OS image decode path. Other hosts return its
// explicit platform diagnostic for image-backed materials.
[[nodiscard]] bool CookMeshTextures(const DecodedMesh &stMesh, MeshTextureCook &out_stCook, Assets::Diagnostics &out_arrDiagnostics,
									std::size_t nByteBudget = 512ULL * 1024ULL * 1024ULL);

// Recreates the deterministic cook and compares variant keys, all mip bytes
// and every material binding. It uses the same image-decoder platform support.
[[nodiscard]] bool ValidateMeshTextureCook(const DecodedMesh &stMesh, const MeshTextureCook &stCook, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
