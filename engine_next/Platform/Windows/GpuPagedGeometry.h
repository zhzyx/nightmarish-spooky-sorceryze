/**************************************************************************/
/*  GpuPagedGeometry.h                                                    */
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
#include "engine_next/Platform/Windows/GpuGeometry.h"
#include "engine_next/include/EngineNext/Rendering/PagedGeometry.h"
#include "engine_next/include/EngineNext/Rendering/PageResidency.h"
#include <array>
#include <cstdint>
#include <string>
#include <vector>
namespace EngineNext::Rendering
{
// Single owner thread and the host's single DIRECT queue/fence domain. Page
// buffers are real physical resources. The host expands each logical pool
// transition to every handle returned by Resources(), including pending copies.
// Source scene and fallback IA views remain alive until Release succeeds.
class GpuPagedGeometry final
{
public:
	GpuPagedGeometry() = default;
	GpuPagedGeometry(const GpuPagedGeometry &) = delete;
	GpuPagedGeometry &operator=(const GpuPagedGeometry &) = delete;
	[[nodiscard]] bool Initialize(ID3D12Device *pDevice, const RenderScene &stSource, const GpuPageIndex &stIndex,
								  const GeometryClusterSet &stFallback, const GeometryPageView &stFallbackView,
								  const GeometrySettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Prepare(std::uint32_t nFrame, const std::vector<std::array<float, 16>> &arrWorlds,
							   const LodView &stView, std::uint64_t nCompletedFence, std::uint64_t nTick,
							   Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool RecordUploads(ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Commit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	// Host must first reset the unsubmitted command list if uploads were
	// recorded.
	[[nodiscard]] bool Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] const GeometryClusterSet &ActiveGeometry() const noexcept;
	[[nodiscard]] const std::vector<ID3D12Resource *> &Resources() const noexcept;
	[[nodiscard]] std::uint64_t PageViews(std::uint32_t nFrame) const noexcept;
	[[nodiscard]] std::uint32_t PageViewCount() const noexcept;
	[[nodiscard]] bool UsesLod() const noexcept;
	[[nodiscard]] const std::vector<std::uint32_t> &ChangedDraws() const noexcept;
	[[nodiscard]] const ResidencyTelemetry &Telemetry() const noexcept;
	[[nodiscard]] const GpuPageReadStats &IoStatistics() const noexcept;
	[[nodiscard]] std::uint64_t OverheadBytes() const noexcept;
	[[nodiscard]] std::uint64_t PendingUploadBytes() const noexcept;
	[[nodiscard]] std::uint64_t BudgetStalls() const noexcept;
	[[nodiscard]] std::uint64_t ActiveReuses() const noexcept;
	// Reuse decisions within preparation attempts, including later discards.
	[[nodiscard]] std::uint64_t SelectionReuses() const noexcept;
	[[nodiscard]] const PagedWorldCache &WorldCache() const noexcept;
	[[nodiscard]] const std::string &LastPageError() const noexcept;

private:
	struct Slot
	{
		std::uint32_t nPage = 0;
		std::uint64_t nBufferBytes = 0;
		PageLoadTicket stTicket;
		ComOwner<ID3D12Resource> stGpu;
		ComOwner<ID3D12Resource> stUpload;
		GeometryPageView stView;
		std::vector<GpuClusterInput> arrClusters;
	};
	struct Frame
	{
		ComOwner<ID3D12Resource> stViews;
		std::uint64_t nFence = 0;
	};
	bool Load(std::uint32_t nSlot, Assets::Diagnostics &out_arrDiagnostics);
	bool BuildActive(const PagedFrameSelection &stSelection, Assets::Diagnostics &out_arrDiagnostics);
	bool IsOwner() const noexcept;
	void Sweep();
	void Swap(GpuPagedGeometry &stOther) noexcept;
	DWORD nOwner = 0;
	ID3D12Device *pDevice = nullptr;
	const RenderScene *pSource = nullptr;
	GpuPageIndex stIndex;
	GeometrySettings stSettings;
	GeometryClusterSet stFallback;
	GeometryPageView stFallbackView;
	PageResidency stResidency;
	PagedWorldCache stWorldCache;
	GpuPageReadStats stIo;
	std::vector<Slot> arrSlots;
	std::vector<std::uint32_t> arrPageSlots;
	std::vector<std::uint32_t> arrDrawBuckets;
	std::array<Frame, GEOMETRY_FRAME_COUNT> arrFrames;
	std::vector<std::uint32_t> arrPrepared;
	std::vector<std::uint32_t> arrUsed;
	std::vector<std::uint32_t> arrActiveSlots;
	std::vector<std::uint64_t> arrActiveGenerations;
	std::vector<std::uint32_t> arrChangedDraws;
	std::vector<ID3D12Resource *> arrResources;
	PagedFrameSelection stPrevious;
	PagedFrameSelection stPending;
	GeometryClusterSet stActive;
	std::uint32_t nPendingFrame = GEOMETRY_FRAME_COUNT;
	std::uint64_t nTick = 0;
	std::uint64_t nLastFence = 0;
	std::uint64_t nOverhead = 0;
	std::uint64_t nCompleted = 0;
	std::uint64_t nBudgetStalls = 0;
	std::uint64_t nActiveReuses = 0;
	std::uint64_t nSelectionReuses = 0;
	std::string strLastPageError;
	bool bRecorded = false;
	bool bUsesLod = false;
	bool bActiveCommitted = false;
};
} // namespace EngineNext::Rendering
