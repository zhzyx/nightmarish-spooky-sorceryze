/**************************************************************************/
/*  GpuRayReflections.h                                                   */
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

#include "engine_next/Platform/Windows/RayTracingScene.h"
#include "engine_next/Platform/Windows/RhiComOwner.h"
#include "engine_next/include/EngineNext/Rendering/ReflectionSettings.h"

#include <array>
#include <cstdint>
#include <filesystem>
#include <vector>

namespace EngineNext::Rendering
{

constexpr std::uint32_t RAY_REFLECTION_VIEWS = 228;
constexpr std::uint32_t RAY_REFLECTION_HISTORY_IMAGES = 7;

struct RayReflectionDescriptors
{
	D3D12_CPU_DESCRIPTOR_HANDLE stCpu{};
	D3D12_GPU_DESCRIPTOR_HANDLE stGpu{};
	std::uint32_t nStride = 0;
};

// External views are recreated from resources; shader-visible descriptors are
// never used as CopyDescriptors sources. Entries follow TraceCS t0..30.
struct RayReflectionBindings
{
	std::array<ID3D12Resource *, 31> arrResources{};
	D3D12_GPU_VIRTUAL_ADDRESS nFrameConstants = 0;
	D3D12_GPU_VIRTUAL_ADDRESS nGiConstants = 0;
	D3D12_GPU_DESCRIPTOR_HANDLE stMaterials{};
	D3D12_GPU_DESCRIPTOR_HANDLE stSamplers{};
};

struct alignas(16) RayReflectionConstants
{
	std::array<float, 4> arrViewport{};
	std::array<float, 4> arrProjection{};
	std::array<float, 4> arrTraceRange{};
	std::array<float, 4> arrSettings{};
	std::array<float, 4> arrHistory{};
	std::array<std::uint32_t, 4> arrCounts{};
	std::array<float, 4> arrFilter{};
	std::array<float, 4> arrJitter{};
};
static_assert(sizeof(RayReflectionConstants) == 128);

enum class RayReflectionPass
{
	BuildScene,
	Prepare,
	Trace,
	Temporal,
	Spatial,
	Composite,
	Readback
};

struct RayReflectionStatistics
{
	std::uint64_t nPrimary = 0;
	std::uint64_t nScreenHits = 0;
	std::uint64_t nSceneHits = 0;
	std::uint64_t nMisses = 0;
	std::uint64_t nInvalid = 0;
	std::uint64_t nShadowRays = 0;
	std::uint64_t nWitnessRays = 0;
};

// Single owner thread, one DIRECT queue/fence domain. Caller owns transitions,
// submission and retirement. A borrowed GI ray scene must outlive this object;
// only its owner records and commits BLAS/TLAS updates. Images are global and
// serialized by the same queue, while uploads/descriptors/readbacks are per slot.
class GpuRayReflections final
{
public:
	GpuRayReflections() = default;
	GpuRayReflections(const GpuRayReflections &) = delete;
	GpuRayReflections &operator=(const GpuRayReflections &) = delete;
	GpuRayReflections(GpuRayReflections &&) noexcept = default;
	GpuRayReflections &operator=(GpuRayReflections &&) noexcept = default;

	[[nodiscard]] bool Initialize(ID3D12Device5 *pDevice, const ReflectionSettings &stSettings,
								  std::uint32_t nWidth, std::uint32_t nHeight, const RenderScene &stSource,
								  const std::vector<std::array<float, 4>> &arrExtensions, const RayTracingScene *pBorrowedScene,
								  const std::filesystem::path &stShaderDirectory,
								  const std::array<RayReflectionDescriptors, RAY_TRACING_FRAME_COUNT> &arrDescriptors,
								  std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool PrepareFrame(std::uint32_t nFrame, const RayReflectionConstants &stConstants,
									const std::vector<std::array<double, 16>> &arrWorlds, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics,
									const DeformationFrame *pDeformation = nullptr);
	[[nodiscard]] bool Record(std::uint32_t nFrame, RayReflectionPass ePass, std::uint32_t nSpatialPass,
							  ID3D12GraphicsCommandList4 *pList, const RayReflectionBindings &stBindings, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Submit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Collect(std::uint32_t nFrame, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	void InvalidateHistory() noexcept;

	ID3D12Resource *Raw(std::uint32_t nImage) const noexcept;
	ID3D12Resource *History(bool bWrite, std::uint32_t nImage) const noexcept;
	ID3D12Resource *Scratch(std::uint32_t nImage) const noexcept;
	ID3D12Resource *Filtered(std::uint32_t nImage) const noexcept;
	ID3D12Resource *Counters(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Upload(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Readback(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Scene(std::uint32_t nFrame) const noexcept;
	const RayTracingScene &RayScene() const noexcept;
	bool OwnsScene() const noexcept;
	const RayReflectionBudget &Budget() const noexcept;
	const RayReflectionStatistics &Statistics() const noexcept;
	std::uint64_t AllocatedBytes() const noexcept;
	std::uint64_t SubmissionEpoch() const noexcept;
	std::uint64_t PeakInvalidCount() const noexcept;

private:
	struct Frame
	{
		ComOwner<ID3D12Resource> stUpload;
		ComOwner<ID3D12Resource> stCounters;
		ComOwner<ID3D12Resource> stReadback;
		std::uint64_t nFence = 0;
		bool bReadbackPending = false;
	};
	bool IsOwner() const noexcept;
	bool WriteDescriptors(std::uint32_t nFrame, std::uint32_t nStage,
						  const RayReflectionBindings &stBindings, Assets::Diagnostics &out_arrDiagnostics);
	bool bInitialized = false;
	DWORD nOwnerThread = 0;
	std::uint32_t nImageWidth = 0;
	std::uint32_t nImageHeight = 0;
	std::uint32_t nPendingFrame = RAY_TRACING_FRAME_COUNT;
	std::uint32_t nReadHistory = 0;
	std::uint32_t nRecorded = 0;
	std::uint32_t nSpatialRecorded = 0;
	std::uint64_t nEpoch = 0;
	std::uint64_t nInvalidation = 1;
	std::uint64_t nCommittedInvalidation = 0;
	std::uint64_t nPreparedInvalidation = 0;
	std::uint64_t nPreparedFence = 0;
	std::uint64_t nAllocatedBytes = 0;
	std::uint64_t nCollectedFence = 0;
	std::uint64_t nLatestFence = 0;
	std::uint64_t nPeakInvalidCount = 0;
	ComOwner<ID3D12Device5> stDevice;
	RayTracingScene stOwnedScene;
	const RayTracingScene *pBorrowedScene = nullptr;
	ReflectionSettings stSettings;
	RayReflectionBudget stBudget;
	RayReflectionStatistics stStatistics;
	std::vector<std::array<double, 16>> arrPendingWorlds;
	std::array<ComOwner<ID3D12Resource>, 3> arrRaw;
	std::array<std::array<ComOwner<ID3D12Resource>, RAY_REFLECTION_HISTORY_IMAGES>, 2> arrHistory;
	std::array<ComOwner<ID3D12Resource>, 2> arrScratch;
	std::array<Frame, RAY_TRACING_FRAME_COUNT> arrFrames;
	std::array<RayReflectionDescriptors, RAY_TRACING_FRAME_COUNT> arrDescriptors;
	ComOwner<ID3D12Resource> stExtensions;
	ComOwner<ID3D12RootSignature> stRoot;
	std::array<ComOwner<ID3D12PipelineState>, 4> arrPipelines;
};

} // namespace EngineNext::Rendering
