/**************************************************************************/
/*  GpuShadowPages.h                                                      */
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
#include "engine_next/Rendering/ShadowPageCache.h"

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

inline constexpr std::uint32_t SHADOW_PAGE_FRAME_COUNT = 3;
inline constexpr std::uint32_t SHADOW_PAGE_VIEW_COUNT = 8;

struct ShadowPageDescriptors
{
	D3D12_CPU_DESCRIPTOR_HANDLE stCpu{};
	D3D12_GPU_DESCRIPTOR_HANDLE stGpu{};
	std::uint32_t nStride = 0;
};

struct alignas(16) ShadowPageConstants
{
	std::array<float, 16> arrInverseViewProjection{};
	std::array<float, 16> arrView{};
	std::array<std::array<float, 16>, 4> arrShadowProjection{};
	std::array<float, 4> arrSplits{};
	// Virtual resolution, pages per axis, physical page width, raster border.
	std::array<std::uint32_t, 4> arrDimensions{};
	// Full width/height, cascade blend fraction, enabled.
	std::array<float, 4> arrViewport{};
};
static_assert(sizeof(ShadowPageConstants) == 432);

// One caller thread and one DIRECT queue/fence domain. Caller declares all
// transitions and executes Upload -> Render -> Feedback -> Readback before
// Submit. Physical pages persist; upload/descriptors/readback are slot owned.
class GpuShadowPages final
{
public:
	[[nodiscard]] bool Initialize(ID3D12Device *pDevice, const VirtualShadowSettings &stSettings,
								  const std::filesystem::path &stShaderDirectory,
								  const std::array<ShadowPageDescriptors, SHADOW_PAGE_FRAME_COUNT> &arrDescriptors,
								  Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Prepare(std::uint32_t nFrame, std::uint64_t nCompletedFence, const ShadowData &stProjection,
							   const std::vector<WorldBounds> &arrCasters, const std::vector<std::uint32_t> &arrChangedDraws,
							   const ShadowPageConstants &stConstants, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool RecordUpload(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool RecordFeedback(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, ID3D12Resource *pDepth, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool RecordReadback(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Submit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	void Cancel() noexcept;
	[[nodiscard]] bool Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);

	const ShadowPagePlan &Plan() const noexcept;
	ID3D12Resource *Pool() const noexcept;
	ID3D12Resource *Table(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Feedback(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Upload(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *Readback(std::uint32_t nFrame) const noexcept;
	D3D12_CPU_DESCRIPTOR_HANDLE Dsv(std::uint32_t nPage) const noexcept;
	D3D12_GPU_DESCRIPTOR_HANDLE Receiver(std::uint32_t nFrame) const noexcept;
	D3D12_GPU_VIRTUAL_ADDRESS Constants(std::uint32_t nFrame) const noexcept;
	D3D12_GPU_VIRTUAL_ADDRESS PageConstants(std::uint32_t nFrame, std::uint32_t nUpdate) const noexcept;
	std::uint64_t AllocatedBytes() const noexcept;
	std::array<std::uint32_t, 4> FeedbackStatistics() const noexcept;

private:
	struct Frame
	{
		ComOwner<ID3D12Resource> stTable;
		ComOwner<ID3D12Resource> stFeedback;
		ComOwner<ID3D12Resource> stUpload;
		ComOwner<ID3D12Resource> stReadback;
		ShadowData stProjection;
		std::uint64_t nFence = 0;
		bool bReadbackPending = false;
	};
	bool IsOwner() const noexcept;
	[[nodiscard]] bool Collect(std::uint64_t nCompletedFence, std::vector<ShadowPageFeedback> &out_arrFeedback, Assets::Diagnostics &out_arrDiagnostics);
	ComOwner<ID3D12Device> stDevice;
	ComOwner<ID3D12Resource> stPool;
	ComOwner<ID3D12DescriptorHeap> stDsvHeap;
	ComOwner<ID3D12RootSignature> stRoot;
	ComOwner<ID3D12PipelineState> stPipeline;
	std::array<Frame, SHADOW_PAGE_FRAME_COUNT> arrFrames;
	std::array<ShadowPageDescriptors, SHADOW_PAGE_FRAME_COUNT> arrDescriptors{};
	std::array<std::uint32_t, 4> arrFeedbackStatistics{};
	ShadowPageCache stCache;
	VirtualShadowSettings stSettings;
	std::uint64_t nTableBytes = 0;
	std::uint64_t nFeedbackBytes = 0;
	std::uint64_t nPageConstantsOffset = 0;
	std::uint64_t nTableOffset = 0;
	std::uint64_t nZeroOffset = 0;
	std::uint64_t nUploadBytes = 0;
	std::uint64_t nAllocatedBytes = 0;
	std::uint64_t nPreparedFence = 0;
	std::uint32_t nPendingFrame = SHADOW_PAGE_FRAME_COUNT;
	std::uint32_t nRecordedStage = 0;
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	DWORD nOwnerThread = 0;
	bool bInitialized = false;
};

} // namespace EngineNext::Rendering
