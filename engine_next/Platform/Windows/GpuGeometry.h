/**************************************************************************/
/*  GpuGeometry.h                                                         */
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

#include "engine_next/Platform/Windows/RhiComOwner.h"
#include "engine_next/include/EngineNext/Rendering/GeometryScene.h"
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <d3d12.h>
#include <array>
#include <filesystem>
#include <vector>

namespace EngineNext::Rendering
{
inline constexpr std::uint32_t GEOMETRY_FRAME_COUNT = 3;
inline constexpr std::uint32_t GEOMETRY_VIEW_COUNT = 40;

struct GeometryDescriptorBlock
{
	D3D12_CPU_DESCRIPTOR_HANDLE stCpu{};
	D3D12_GPU_DESCRIPTOR_HANDLE stGpu{};
	std::uint32_t nStride = 0;
};
struct GeometryGpuConfig
{
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint64_t nMaxBytes = 512ULL * 1024 * 1024;
	std::filesystem::path stShaderDirectory;
	std::array<GeometryDescriptorBlock, GEOMETRY_FRAME_COUNT> arrDescriptors;
	std::array<ID3D12Resource *, GEOMETRY_FRAME_COUNT> arrDepth{};
	ID3D12RootSignature *pDrawRoot = nullptr;
	bool bPaged = false;
	std::uint32_t nMaximumCandidates = 0;
};
struct alignas(16) GeometryGpuInstance
{
	std::array<float, 16> arrWorld{};
	std::array<std::uint32_t, 2> arrConstants{};
	std::array<std::uint32_t, 2> arrPadding{};
};
struct alignas(16) GeometryIndirectCommand
{
	std::uint64_t nConstants = 0;
	D3D12_DRAW_INDEXED_ARGUMENTS stDraw{};
	std::uint32_t nPadding = 0;
};
struct GeometryPageView
{
	D3D12_VERTEX_BUFFER_VIEW stVertex{};
	D3D12_INDEX_BUFFER_VIEW stIndex{};
};
struct alignas(8) GeometryPagedIndirectCommand
{
	std::uint64_t nConstants = 0;
	D3D12_VERTEX_BUFFER_VIEW stVertex{};
	D3D12_INDEX_BUFFER_VIEW stIndex{};
	D3D12_DRAW_INDEXED_ARGUMENTS stDraw{};
	std::uint32_t nPadding = 0;
};
static_assert(sizeof(GeometryPageView) == 32);
static_assert(sizeof(GeometryPagedIndirectCommand) == 64);
static_assert(offsetof(GeometryPagedIndirectCommand, stVertex) == 8);
static_assert(offsetof(GeometryPagedIndirectCommand, stIndex) == 24);
static_assert(offsetof(GeometryPagedIndirectCommand, stDraw) == 40);
static_assert(sizeof(GeometryGpuInstance) == 80);
static_assert(sizeof(GeometryIndirectCommand) == 32);
static_assert(offsetof(GeometryIndirectCommand, stDraw) == 8);

struct GeometryGpuStatistics
{
	std::uint32_t nDepthCommands = 0;
	std::uint32_t nDepthTriangles = 0;
	std::uint32_t nVisibleCommands = 0;
	std::uint32_t nVisibleTriangles = 0;
	std::uint32_t nOverflow = 0;
	std::uint32_t nInvalid = 0;
};

enum class GeometryWork : std::uint8_t
{
	Upload,
	ClearDepth,
	CullDepth,
	HiZ,
	ClearColor,
	CullColor,
	Readback,
};

// Owner-thread D3D12 helper. A single DIRECT queue owns all commands and fences.
// Source data is copied at initialization. Depth resources, descriptor ranges
// and the draw root signature belong to the host until the final fence retires.
class GpuGeometry final
{
public:
	GpuGeometry() = default;
	GpuGeometry(const GpuGeometry &) = delete;
	GpuGeometry &operator=(const GpuGeometry &) = delete;
	[[nodiscard]] bool Initialize(ID3D12Device *pDevice, const GeometryClusterSet &stSource, const GeometryGpuConfig &stConfig, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool PrepareFrame(std::uint32_t nFrame, const std::vector<std::array<float, 16>> &arrWorlds,
									const std::array<float, 16> &arrViewProjection, std::uint64_t nDrawConstants, std::uint64_t nDrawStride,
									bool bOcclusion, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics,
									const GeometryClusterSet *pDynamic = nullptr, std::uint64_t nPageViews = 0, std::uint32_t nPageViewCount = 0);
	[[nodiscard]] bool Record(std::uint32_t nFrame, GeometryWork eWork, std::uint32_t nMip, ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics);
	void Execute(std::uint32_t nFrame, std::uint32_t nPhase, std::uint32_t nBucket, ID3D12GraphicsCommandList *pList) const;
	[[nodiscard]] bool Commit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Collect(std::uint32_t nFrame, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics, GeometryGpuStatistics *out_pRetired = nullptr);
	[[nodiscard]] bool Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	ID3D12Resource *Clusters() const noexcept;
	ID3D12Resource *Clusters(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Arguments(std::uint32_t nFrame, std::uint32_t nPhase) const noexcept;
	ID3D12Resource *Counters(std::uint32_t nFrame, std::uint32_t nPhase) const noexcept;
	ID3D12Resource *HiZ(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Readback(std::uint32_t nFrame) const noexcept;
	std::uint32_t MipCount() const noexcept;
	std::uint64_t AllocatedBytes() const noexcept;
	const GeometryGpuStatistics &Statistics() const noexcept;
	const std::vector<GeometryBucket> &Buckets() const noexcept;
	const std::vector<GeometryBucket> &Buckets(std::uint32_t nFrame) const noexcept;

private:
	struct Frame
	{
		std::array<ComOwner<ID3D12Resource>, 2> arrArguments;
		std::array<ComOwner<ID3D12Resource>, 2> arrCounters;
		ComOwner<ID3D12Resource> stUpload;
		ComOwner<ID3D12Resource> stClusters;
		std::vector<GeometryBucket> arrBuckets;
		std::uint32_t nActiveCount = 0;
		std::uint64_t nPageViews = 0;
		ComOwner<ID3D12Resource> stHiZ;
		ComOwner<ID3D12Resource> stReadback;
		std::uint64_t nFence = 0;
		bool bOcclusion = false;
		bool bReadbackPending = false;
		std::uint32_t nWorkMask = 0;
		std::uint32_t nNextMip = 0;
	};
	bool IsOwner() const noexcept;
	void Swap(GpuGeometry &stOther) noexcept;
	DWORD nOwnerThread = 0;
	std::uint32_t nPendingFrame = GEOMETRY_FRAME_COUNT;
	bool bUploaded = false;
	bool bPaged = false;
	std::uint32_t nCommandStride = sizeof(GeometryIndirectCommand);
	std::uint64_t nClusterUploadOffset = 0;
	std::uint64_t nBucketUploadOffset = 0;
	std::uint32_t nMipCount = 0;
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint32_t nDrawCount = 0;
	std::uint32_t nCandidateCount = 0;
	std::uint32_t nCounterCount = 0;
	std::uint64_t nAllocatedBytes = 0;
	std::uint64_t nCollectedFence = 0;
	std::vector<GeometryBucket> arrBuckets;
	std::array<Frame, GEOMETRY_FRAME_COUNT> arrFrames;
	std::array<GeometryDescriptorBlock, GEOMETRY_FRAME_COUNT> arrDescriptors;
	ComOwner<ID3D12Resource> stClusters;
	ComOwner<ID3D12Resource> stClusterUpload;
	ComOwner<ID3D12Resource> stBucketUpload;
	ComOwner<ID3D12RootSignature> stCullRoot;
	ComOwner<ID3D12RootSignature> stHiZRoot;
	ComOwner<ID3D12CommandSignature> stCommands;
	ComOwner<ID3D12DescriptorHeap> stClearHeap;
	std::array<ComOwner<ID3D12PipelineState>, 3> arrPipelines;
	GeometryGpuStatistics stStatistics;
};
} // namespace EngineNext::Rendering
