/**************************************************************************/
/*  RenderScene.h                                                         */
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

#include "engine_next/include/EngineNext/Assets/AssetPackage.h"
#include "engine_next/include/EngineNext/Rendering/AnimationData.h"
#include "engine_next/include/EngineNext/Rendering/MeshData.h"
#include "engine_next/include/EngineNext/Rendering/TextureData.h"

#include <array>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

struct RenderAsset
{
	Assets::AssetRef stIdentity;
	DecodedMesh stMesh;
	MeshTextureCook stTextureCook;
	AnimationData stAnimation{};
	bool bAnimated = false;
};

struct RenderInstance
{
	std::uint64_t nEntityId = 0;
	std::uint32_t nAsset = 0;
	std::uint32_t nPrimitive = 0;
	std::uint32_t nNode = 0;
	std::array<double, 16> arrTransform{};
	std::array<double, 3> arrEntityOrigin{};
	// Source entity world transform, before applying the glTF mesh node.
	std::array<double, 16> arrEntityTransform{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	std::uint32_t nMeshInstance = UINT32_MAX;
};

struct RenderScene
{
	// Zero for source scenes, one for legacy layout, two for prepared GPU data.
	// Three identifies paged metadata whose geometry/image/mip bytes are external.
	// Four retains paging and stores explicitly encoded texture mip payloads.
	std::uint32_t nGpuFormatVersion = 0;
	std::string strSceneId;
	std::string strSceneRevision;
	std::string strSceneDigest;
	std::string strPackageDigest;
	std::vector<RenderAsset> arrAssets;
	std::vector<RenderInstance> arrInstances;
};

// Resolves every source entity, including non-renderable parents, into a
// column-major world transform using the scene hierarchy. Pure CPU operation
// with immutable input; matrices must be finite and fit binary32. Validation
// diagnostics are appended and failure preserves the previous output map.
[[nodiscard]] bool BuildSceneEntityTransforms(const Assets::SceneDocument &stScene, std::map<std::uint64_t, std::array<double, 16>> &out_mapTransforms,
											  Assets::Diagnostics &out_arrDiagnostics);

// CPU-only and transactional. Original package bytes and M3 identities are read-only.
[[nodiscard]] bool BuildRenderScene(const Assets::PackageData &stPackage, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool LoadRenderScene(const std::string &strPath, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics);

// Explicit rendering entry for source GLB animation and deformation. Source
// package identities and the static loader's behavior are preserved. Animation
// data is owned by each RenderAsset and shares the scene's decoded-data budget.
[[nodiscard]] bool BuildAnimatedRenderScene(const Assets::PackageData &stPackage, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool LoadAnimatedRenderScene(const std::string &strPath, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
