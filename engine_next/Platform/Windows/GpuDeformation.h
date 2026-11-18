/**************************************************************************/
/*  GpuDeformation.h                                                      */
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
#include "engine_next/include/EngineNext/Rendering/DeformationFrame.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <d3d12.h>

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{
struct DeformationRange
{
	std::uint32_t nDraw = 0;
	std::uint32_t nFirstVertex = 0;
	std::uint32_t nVertexCount = 0;
};

// One owner thread, one DIRECT queue and three retired upload slots. The host
// owns the current-position VB and all queue submissions. Resource lifetimes
// extend through the final fence; initialization is recorded before first use.
class GpuDeformation final
{
public:
	GpuDeformation() = default;
	GpuDeformation(const GpuDeformation &) = delete;
	GpuDeformation &operator=(const GpuDeformation &) = delete;
	GpuDeformation(GpuDeformation &&) noexcept = default;
	GpuDeformation &operator=(GpuDeformation &&) noexcept = default;

	[[nodiscard]] bool Initialize(ID3D12Device *pDevice, const std::vector<MeshVertex> &arrVertices,
								  const std::vector<DeformationRange> &arrRanges, Assets::Diagnostics &out_arrDiagnostics);
	void RecordInitialization(ID3D12GraphicsCommandList *pList) const;
	[[nodiscard]] bool PrepareFrame(std::uint32_t nFrame, const DeformationFrame &stCurrent, const DeformationFrame *pPrevious,
									bool bHistoryValid, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Record(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, ID3D12Resource *pVertices,
							  Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Commit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Cancel(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics);

	ID3D12Resource *PreviousPositions() const noexcept;
	ID3D12Resource *Upload(std::uint32_t nFrame) const noexcept;
	std::uint64_t MemoryBytes() const noexcept;
	double MaxLocalMotion() const noexcept;

private:
	static constexpr std::uint32_t FRAME_COUNT = 3;
	struct Frame
	{
		ComOwner<ID3D12Resource> stUpload;
		std::uint64_t nFence = 0;
	};
	std::array<Frame, FRAME_COUNT> arrFrames;
	ComOwner<ID3D12Resource> stPrevious;
	ComOwner<ID3D12Resource> stInitialUpload;
	std::vector<DeformationRange> arrRanges;
	std::uint64_t nPreviousBytes = 0;
	std::uint64_t nUploadBytes = 0;
	std::uint64_t nResidentBytes = 0;
	std::uint64_t nLatestFence = 0;
	std::uint32_t nPendingFrame = FRAME_COUNT;
	bool bRecorded = false;
	DWORD nOwnerThread = 0;
	double dMaxLocalMotion = 0;
};
} // namespace EngineNext::Rendering
