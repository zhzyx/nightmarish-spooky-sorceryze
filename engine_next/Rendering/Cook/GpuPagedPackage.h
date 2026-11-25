/**************************************************************************/
/*  GpuPagedPackage.h                                                     */
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

#include "engine_next/include/EngineNext/Rendering/GeometryLod.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

enum class GpuPageKind : std::uint32_t
{
	MeshGeometry = 1,
	EncodedImage = 2,
	TextureMip = 3,
	BlockTextureMip = 4,
};

struct GpuPageDescription
{
	GpuPageKind eKind = GpuPageKind::MeshGeometry;
	std::uint32_t nAsset = 0;
	std::uint32_t nItem = 0;
	std::uint32_t nLevel = 0;
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint64_t nOffset = 0;
	std::uint64_t nBytes = 0;
	std::string strDigest;
	bool bPinned = false;
};

struct GpuLodTree
{
	std::uint32_t nAsset = 0;
	std::uint32_t nPrimitive = 0;
	std::uint32_t nSourceVertices = 0;
	std::uint32_t nSourceTriangles = 0;
	std::vector<LodNode> arrNodes;
	std::vector<std::array<std::uint32_t, 2>> arrSourceRanges;
	std::vector<std::uint32_t> arrRoots;
};

struct GpuPageLimits
{
	std::uint64_t nMaximumIndexBytes = 32ULL * 1024 * 1024;
	std::uint64_t nMaximumPageBytes = 64ULL * 1024 * 1024;
	std::uint64_t nMaximumPayloadBytes = 1024ULL * 1024 * 1024;
	std::uint64_t nMaximumPinnedBytes = 128ULL * 1024 * 1024;
	std::uint32_t nMaximumPages = 262144;
	// Total distance queries allowed while verifying a foreign Cook against source.
	std::uint64_t nMaximumSourceDistanceTests = 16000000;
};

struct GpuMeshPage
{
	std::uint32_t nAsset = 0;
	std::uint32_t nPrimitive = 0;
	std::uint32_t nNode = 0;
	std::vector<MeshVertex> arrVertices;
	std::vector<std::uint32_t> arrSourceVertices;
	std::vector<std::uint32_t> arrIndices;
};

struct GpuPageReadStats
{
	std::uint64_t nReadRequests = 0;
	std::uint64_t nBytesRead = 0;
	std::uint64_t nVerifiedPages = 0;
};

class GpuPageIndex final
{
public:
	// Descriptive scene records. Geometry, encoded images and mip byte arrays
	// are empty and must be requested through this index's page descriptions.
	[[nodiscard]] const RenderScene &Metadata() const noexcept;
	[[nodiscard]] const std::vector<GpuPageDescription> &Pages() const noexcept;
	[[nodiscard]] const std::vector<GpuLodTree> &Trees() const noexcept;
	[[nodiscard]] std::uint64_t PinnedBytes() const noexcept;
	[[nodiscard]] std::uint64_t IndexBytesRead() const noexcept;
	[[nodiscard]] const LodCookSettings &CookSettings() const noexcept;
	[[nodiscard]] const std::string &DescriptionDigest() const noexcept;
	[[nodiscard]] std::uint64_t SourceDistanceBudget() const noexcept;

private:
	friend bool LoadGpuPageIndex(const std::string &, const std::string &, const GpuPageLimits &, GpuPageIndex &, Assets::Diagnostics &);
	friend bool ReadGpuPage(const GpuPageIndex &, std::uint32_t, std::vector<std::uint8_t> &, GpuPageReadStats &, Assets::Diagnostics &);
	RenderScene stMetadata;
	LodCookSettings stCookSettings;
	std::string strDescriptionDigest;
	std::vector<GpuPageDescription> arrPages;
	std::vector<GpuLodTree> arrTrees;
	std::string strPayloadPath;
	std::uint64_t nPayloadBytes = 0;
	std::uint64_t nPinnedBytes = 0;
	std::uint64_t nIndexBytesRead = 0;
	std::uint64_t nSourceDistanceBudget = 0;
};

// Index opening reads bounded metadata and the directory, and checks payload
// size without reading its pages. Source digest is supplied by the validated
// M3 package owner. Root geometry is pinned; texture bytes remain requestable.
[[nodiscard]] bool LoadGpuPageIndex(const std::string &strPackage, const std::string &strExpectedSourceDigest,
									const GpuPageLimits &stLimits, GpuPageIndex &out_stIndex, Assets::Diagnostics &out_arrDiagnostics);

// Performs a real seek/read and validates the selected page against the opened
// index snapshot. On failure the output bytes stay unchanged. IO stats include
// completed reads even when their content fails validation.
[[nodiscard]] bool ReadGpuPage(const GpuPageIndex &stIndex, std::uint32_t nPage,
							   std::vector<std::uint8_t> &out_arrBytes, GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics);

// Converts a verified mesh payload to compact 48-byte GPU vertices and local
// indices. Source vertex IDs remain CPU metadata and are never vertex bytes.
[[nodiscard]] bool ReadGpuMeshPage(const GpuPageIndex &stIndex, std::uint32_t nPage, GpuMeshPage &out_stPage,
								   GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics);

// Recomputes the exact metadata, hierarchy and every page digest from validated
// M3 source. It does not read page payloads or trust their declared source digest.
[[nodiscard]] bool VerifyPagedScene(const RenderScene &stSource, const GpuPageIndex &stIndex, Assets::Diagnostics &out_arrDiagnostics);

// Normal-entry compatibility loader. v1/v2 retain their original codec and source
// comparison. v3 verifies its derived directory, then reads original leaf geometry
// and image/mip pages; parent LOD pages remain unloaded. Output is transactional.
[[nodiscard]] bool LoadVerifiedGpuPackage(const std::string &strPackage, const RenderScene &stSource,
										  const GpuPageLimits &stLimits, RenderScene &out_stScene,
										  GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics);

// Deterministic v3 Cook with immutable no-replace publication. Repeating an
// identical Cook reconciles the existing target; conflicting output is kept.
[[nodiscard]] bool CookPagedGpuPackage(const std::string &strSourcePackage, const std::string &strTargetPackage,
									   const LodCookSettings &stLodSettings, const GpuPageLimits &stLimits, Assets::Diagnostics &out_arrDiagnostics);

// CPU v4 entry: preserves encoded bytes and source verification. The original
// runtime loader explicitly rejects v4 until its BC upload path is integrated.
[[nodiscard]] bool LoadVerifiedEncodedGpuPackage(const std::string &strPackage, const RenderScene &stSource,
												 const GpuPageLimits &stLimits, RenderScene &out_stScene,
												 GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics);

// Retains the verified v4 index and defers texture payload IO to the residency owner.
[[nodiscard]] bool LoadTextureStreamingPackage(const std::string &strPackage, const RenderScene &stSource, const GpuPageLimits &stLimits,
											   RenderScene &out_stScene, GpuPageReadStats &out_stStats, GpuPageIndex &out_stIndex, Assets::Diagnostics &out_arrDiagnostics);

// Same no-replace paged publication as v3, with a fixed BC7/BC5 recipe.
[[nodiscard]] bool CookEncodedGpuPackage(const std::string &strSourcePackage, const std::string &strTargetPackage,
										 const LodCookSettings &stLodSettings, const GpuPageLimits &stLimits, Assets::Diagnostics &out_arrDiagnostics);

[[nodiscard]] bool ReadGpuTextureMip(const GpuPageIndex &stIndex, std::uint32_t nPage, EncodedTextureMip &out_stMip,
									 GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics);

[[nodiscard]] bool ReadGpuTextureSuffix(const GpuPageIndex &stIndex, const std::vector<std::uint32_t> &arrMipPages,
										std::uint32_t nFirstMip, std::vector<EncodedTextureMip> &out_arrLevels,
										GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
