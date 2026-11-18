/**************************************************************************/
/*  GpuProbeGrid.h                                                        */
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
#include "engine_next/include/EngineNext/Rendering/ProbeGrid.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <vector>

namespace EngineNext::Rendering
{

struct GiDescriptorBlock
{
	D3D12_CPU_DESCRIPTOR_HANDLE stCpu{};
	D3D12_GPU_DESCRIPTOR_HANDLE stGpu{};
	std::uint32_t nStride = 0;
};

struct GiBindings
{
	D3D12_GPU_VIRTUAL_ADDRESS nFrameConstants = 0;
	D3D12_GPU_DESCRIPTOR_HANDLE stEnvironment{};
	D3D12_GPU_DESCRIPTOR_HANDLE stDirectionalShadow{};
	D3D12_GPU_DESCRIPTOR_HANDLE stLocalShadow{};
	D3D12_GPU_DESCRIPTOR_HANDLE stMaterials{};
	D3D12_GPU_DESCRIPTOR_HANDLE stSamplers{};
	D3D12_GPU_DESCRIPTOR_HANDLE stTint{};
};

enum class GiPass
{
	BuildScene,
	Upload,
	InitializeHistory,
	Remap,
	Relocate,
	Trace,
	Update,
	Readback
};

enum class GiHistoryKind : std::uint32_t
{
	Sh,
	Moments,
	State
};

struct alignas(16) GiGridParameters
{
	std::array<std::array<float, 4>, 3> arrMinimum{};
	std::array<std::array<float, 4>, 3> arrInverseSpacing{};
	std::array<std::uint32_t, 4> arrGridInfo{};
	std::array<std::uint32_t, 4> arrWorkInfo{};
	std::array<float, 4> arrSampling{};
	std::array<float, 4> arrHistory{};
	std::array<std::uint32_t, 4> arrCounts{};
};
static_assert(sizeof(GiGridParameters) == 176);
static_assert(offsetof(GiGridParameters, arrGridInfo) == 96);
static_assert(offsetof(GiGridParameters, arrCounts) == 160);

struct GpuProbeMemory
{
	std::uint64_t nDefaultBytes = 0;
	std::uint64_t nUploadBytes = 0;
	std::uint64_t nReadbackBytes = 0;
	std::uint64_t nTotalBytes = 0;
	RayTracingMemory stRayTracing;
};

// One owner thread and one DIRECT queue/fence domain. The host submits lists,
// supplies resource transitions and retires the final fence before Release.
class GpuProbeGrid final
{
public:
	GpuProbeGrid() = default;
	GpuProbeGrid(const GpuProbeGrid &) = delete;
	GpuProbeGrid &operator=(const GpuProbeGrid &) = delete;

	[[nodiscard]] bool Initialize(ID3D12Device5 *pDevice, const GlobalIlluminationSettings &stSettings,
								  const RenderScene &stScene, const std::vector<std::array<float, 4>> &arrMaterialExtensions,
								  const std::filesystem::path &stShaderDirectory,
								  const std::array<GiDescriptorBlock, GI_PENDING_FRAMES> &arrDescriptors,
								  std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool PrepareFrame(std::uint32_t nFrame, const std::array<double, 3> &arrCenter,
									const std::vector<std::array<double, 16>> &arrWorlds, std::uint64_t nCompletedFence,
									Assets::Diagnostics &out_arrDiagnostics, const std::vector<GiGeometryChange> &arrGeometryChanges = {});
	[[nodiscard]] bool Record(std::uint32_t nFrame, GiPass ePass, ID3D12GraphicsCommandList4 *pList,
							  const GiBindings &stBindings, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Submit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Collect(std::uint32_t nFrame, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	void InvalidateHistory() noexcept;

	ID3D12Resource *Scene(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Positions() const noexcept;
	ID3D12Resource *Rays(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *RayStatus(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Readback(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Upload(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *History(bool bWrite, GiHistoryKind eKind) const noexcept;
	D3D12_GPU_DESCRIPTOR_HANDLE ReceiverGpu(std::uint32_t nFrame) const noexcept;
	D3D12_GPU_VIRTUAL_ADDRESS ConstantsGpu(std::uint32_t nFrame) const noexcept;
	std::uint32_t ProbeCount() const noexcept;
	std::uint32_t UpdatedCount() const noexcept;
	std::uint32_t ValidCount() const noexcept;
	std::uint32_t InvalidCount() const noexcept;
	std::uint32_t PeakInvalidCount() const noexcept;
	std::uint32_t PlacementActiveCount() const noexcept;
	std::uint32_t PlacementPendingCount() const noexcept;
	std::uint32_t PlacementInactiveCount() const noexcept;
	std::uint32_t RelocatedCount() const noexcept;
	std::uint64_t SubmissionEpoch() const noexcept;
	const GpuProbeMemory &Memory() const noexcept;
	const std::vector<RayTracingIdentity> &Identities() const noexcept;

private:
	struct Frame
	{
		ComOwner<ID3D12Resource> stRays;
		ComOwner<ID3D12Resource> stRayStatus;
		ComOwner<ID3D12Resource> stUpload;
		ComOwner<ID3D12Resource> stReadback;
		std::uint64_t nFence = 0;
		bool bReadbackPending = false;
	};
	struct HistoryResources
	{
		std::array<ComOwner<ID3D12Resource>, 3> arrBuffers;
	};
	bool IsOwner() const noexcept;
	bool CanRelease(std::uint64_t nCompletedFence) const noexcept;
	void Swap(GpuProbeGrid &stOther) noexcept;
	void WriteDescriptors(std::uint32_t nFrame);

	DWORD nOwnerThread = 0;
	bool bInitialized = false;
	bool bHasSubmitted = false;
	std::uint32_t nReadHistory = 0;
	std::uint32_t nPendingFrame = GI_PENDING_FRAMES;
	std::uint32_t nRecordedPasses = 0;
	std::uint32_t nUpdatedCount = 0;
	std::uint32_t nValidCount = 0;
	std::uint32_t nInvalidCount = 0;
	std::uint32_t nPeakInvalidCount = 0;
	std::uint32_t nPlacementActiveCount = 0;
	std::uint32_t nPlacementPendingCount = 0;
	std::uint32_t nPlacementInactiveCount = 0;
	std::uint32_t nRelocatedCount = 0;
	std::uint32_t nGeometrySerial = 1;
	std::uint32_t nPendingGeometrySerial = 1;
	bool bPendingHistoryValid = false;
	std::uint64_t nEpoch = 0;
	std::uint64_t nInvalidationSerial = 1;
	std::uint64_t nCommittedInvalidation = 0;
	std::uint64_t nPendingInvalidation = 0;
	std::uint64_t nPreparedCompletedFence = 0;
	std::uint64_t nCollectedFence = 0;
	std::uint64_t nPositionOffset = 0;
	std::uint64_t nRemapOffset = 0;
	std::uint64_t nUpdateOffset = 0;
	std::uint64_t nRevisionOffset = 0;
	std::uint32_t nMaterialCount = 0;
	ComOwner<ID3D12Device5> stDevice;
	RayTracingScene stScene;
	GlobalIlluminationSettings stSettings;
	ProbeGrid stGrid;
	ProbeGrid stPendingGrid;
	std::vector<std::uint8_t> arrNeedsUpdate;
	std::vector<std::uint8_t> arrPendingNeedsUpdate;
	std::vector<std::uint32_t> arrPendingUpdates;
	std::vector<std::array<double, 16>> arrPendingWorlds;
	std::vector<std::array<double, 16>> arrCommittedWorlds;
	std::vector<WorldBounds> arrLocalBounds;
	std::vector<std::uint32_t> arrGeometryRevisions;
	std::vector<std::uint32_t> arrPendingGeometryRevisions;
	std::array<Frame, GI_PENDING_FRAMES> arrFrames;
	std::array<HistoryResources, 2> arrHistory;
	std::array<GiDescriptorBlock, GI_PENDING_FRAMES> arrDescriptors;
	ComOwner<ID3D12Resource> stPositions;
	ComOwner<ID3D12Resource> stMaterialExtensions;
	ComOwner<ID3D12RootSignature> stRoot;
	ComOwner<ID3D12DescriptorHeap> stClearHeap;
	std::array<ComOwner<ID3D12PipelineState>, 4> arrPipelines;
	GpuProbeMemory stMemory;
};

} // namespace EngineNext::Rendering
