/**************************************************************************/
/*  ShadowRecording.h                                                     */
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
#include "engine_next/Rendering/FrameTelemetry.h"

#include <windows.h>
#include <d3d12.h>

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

struct ShadowRecordingDraw
{
	ID3D12PipelineState *pPipeline = nullptr;
	D3D12_GPU_VIRTUAL_ADDRESS nConstants = 0;
	D3D12_GPU_DESCRIPTOR_HANDLE stMaterial{};
	D3D12_GPU_DESCRIPTOR_HANDLE stSampler{};
	UINT nIndices = 0;
	UINT nFirstIndex = 0;
	INT nBaseVertex = 0;
	WorldBounds stBounds;
};

struct ShadowRecordingView
{
	std::uint32_t nSlot = 0;
	D3D12_GPU_VIRTUAL_ADDRESS nConstants = 0;
	bool bPage = false;
	std::array<float, 16> arrProjection{};
};

// All pointed-to resources are owned by the runtime through graphics retirement.
// Workers borrow this snapshot only for the duration of Record().
struct ShadowRecordingSnapshot
{
	ID3D12RootSignature *pRoot = nullptr;
	std::array<ID3D12DescriptorHeap *, 2> arrHeaps{};
	D3D12_VERTEX_BUFFER_VIEW stVertices{};
	D3D12_INDEX_BUFFER_VIEW stIndices{};
	std::vector<ShadowRecordingDraw> arrDraws;
	std::vector<ShadowRecordingView> arrViews;
};

class ShadowRecording final
{
public:
	ShadowRecording() = default;
	~ShadowRecording();
	ShadowRecording(const ShadowRecording &) = delete;
	ShadowRecording &operator=(const ShadowRecording &) = delete;
	bool Record(ID3D12Device *pDevice, const ShadowRecordingSnapshot &stSnapshot, std::uint32_t nFrame,
				std::uint32_t nThreads, std::uint64_t nCompletedFence, std::uint64_t nFrameFence, RecordingStatistics &out_stStatistics);
	ID3D12GraphicsCommandList *Bundle(std::uint32_t nSlot) const noexcept;
	void Clear() noexcept;

private:
	struct Slot
	{
		ComOwner<ID3D12CommandAllocator> stAllocator;
		std::vector<ComOwner<ID3D12GraphicsCommandList>> arrLists;
	};
	struct Lane
	{
		std::array<Slot, 3> arrFrames;
		HANDLE hThread = nullptr;
		HANDLE hStart = nullptr;
		HANDLE hDone = nullptr;
		bool bStop = false;
		const ShadowRecordingSnapshot *pSnapshot = nullptr;
		std::uint32_t nIndex = 0;
		std::uint32_t nFrame = 0;
		std::uint32_t nStride = 0;
		bool bSucceeded = false;
		RecordingThreadStatistics stStatistics;
	};
	static DWORD WINAPI RunWorker(void *pContext);
	static void RecordLane(Lane &stLane);
	static bool EnsureWorker(Lane &stLane);
	std::array<Lane, 4> arrLanes;
	std::vector<ID3D12GraphicsCommandList *> arrBundles;
};

} // namespace EngineNext::Rendering
