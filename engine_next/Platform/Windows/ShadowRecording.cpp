/**************************************************************************/
/*  ShadowRecording.cpp                                                      */
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

#include "engine_next/Platform/Windows/ShadowRecording.h"

#include <algorithm>
#include <cstdlib>

namespace EngineNext::Rendering
{
namespace
{
std::uint64_t ReadCounter() noexcept
{
	LARGE_INTEGER stValue{};
	QueryPerformanceCounter(&stValue);
	return static_cast<std::uint64_t>(stValue.QuadPart);
}
} //namespace

ShadowRecording::~ShadowRecording()
{
	for (Lane &stLane : arrLanes)
	{
		if (stLane.hThread != nullptr)
		{
			stLane.bStop = true;
			if (!SetEvent(stLane.hStart) || WaitForSingleObject(stLane.hThread, INFINITE) != WAIT_OBJECT_0)
			{
				std::abort();
			}
			CloseHandle(stLane.hThread);
		}
		if (stLane.hStart != nullptr)
		{
			CloseHandle(stLane.hStart);
		}
		if (stLane.hDone != nullptr)
		{
			CloseHandle(stLane.hDone);
		}
	}
}

bool ShadowRecording::EnsureWorker(Lane &stLane)
{
	if (stLane.hThread != nullptr)
	{
		return true;
	}
	stLane.hStart = CreateEventW(nullptr, FALSE, FALSE, nullptr);
	stLane.hDone = CreateEventW(nullptr, FALSE, FALSE, nullptr);
	if (stLane.hStart == nullptr || stLane.hDone == nullptr)
	{
		return false;
	}
	stLane.hThread = CreateThread(nullptr, 0, RunWorker, &stLane, 0, nullptr);
	return stLane.hThread != nullptr;
}

DWORD WINAPI ShadowRecording::RunWorker(void *pContext)
{
	Lane &stLane = *static_cast<Lane *>(pContext);
	while (WaitForSingleObject(stLane.hStart, INFINITE) == WAIT_OBJECT_0)
	{
		if (stLane.bStop)
		{
			return 0;
		}
		RecordLane(stLane);
		if (!SetEvent(stLane.hDone))
		{
			std::abort();
		}
	}
	std::abort();
}

void ShadowRecording::RecordLane(Lane &stLane)
{
	const ShadowRecordingSnapshot &stSnapshot = *stLane.pSnapshot;
	Slot &stSlot = stLane.arrFrames[stLane.nFrame];
	RecordingThreadStatistics &stStats = stLane.stStatistics;
	stStats = {};
	stStats.nThreadId = GetCurrentThreadId();
	stStats.nBeginQpc = ReadCounter();
	stLane.bSucceeded = true;
	for (std::size_t nView = stLane.nIndex; nView < stSnapshot.arrViews.size(); nView += stLane.nStride)
	{
		ID3D12GraphicsCommandList *pList = stSlot.arrLists[nView / stLane.nStride].Get();
		if (FAILED(pList->Reset(stSlot.stAllocator.Get(), nullptr)))
		{
			stLane.bSucceeded = false;
			break;
		}
		const ShadowRecordingView &stView = stSnapshot.arrViews[nView];
		pList->SetDescriptorHeaps(static_cast<UINT>(stSnapshot.arrHeaps.size()), stSnapshot.arrHeaps.data());
		pList->SetGraphicsRootSignature(stSnapshot.pRoot);
		pList->SetGraphicsRootConstantBufferView(1, stView.nConstants);
		pList->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
		pList->IASetVertexBuffers(0, 1, &stSnapshot.stVertices);
		pList->IASetIndexBuffer(&stSnapshot.stIndices);
		for (const ShadowRecordingDraw &stDraw : stSnapshot.arrDraws)
		{
			if (stView.bPage && !IntersectsShadowPage(stDraw.stBounds, stView.arrProjection))
			{
				continue;
			}
			pList->SetPipelineState(stDraw.pPipeline);
			pList->SetGraphicsRootConstantBufferView(0, stDraw.nConstants);
			pList->SetGraphicsRootDescriptorTable(2, stDraw.stMaterial);
			pList->SetGraphicsRootDescriptorTable(3, stDraw.stSampler);
			pList->DrawIndexedInstanced(stDraw.nIndices, 1, stDraw.nFirstIndex, stDraw.nBaseVertex, 0);
			++stStats.nDraws;
		}
		if (FAILED(pList->Close()))
		{
			stLane.bSucceeded = false;
			break;
		}
		++stStats.nLists;
	}
	stStats.nEndQpc = ReadCounter();
}

bool ShadowRecording::Record(ID3D12Device *pDevice, const ShadowRecordingSnapshot &stSnapshot, std::uint32_t nFrame,
							 std::uint32_t nThreads, std::uint64_t nCompletedFence, std::uint64_t nFrameFence, RecordingStatistics &out_stStatistics)
{
	Clear();
	if (pDevice == nullptr || nFrame >= 3 || nCompletedFence == UINT64_MAX || nCompletedFence < nFrameFence ||
		(nThreads != 2 && nThreads != 4))
	{
		return false;
	}
	const std::size_t nViews = stSnapshot.arrViews.size();
	if (nViews < 2 || stSnapshot.arrDraws.empty())
	{
		return true;
	}
	const std::uint32_t nActive = static_cast<std::uint32_t>((std::min)(nViews, static_cast<std::size_t>(nThreads)));
	for (std::uint32_t nLane = 0; nLane < nActive; ++nLane)
	{
		Lane &stLane = arrLanes[nLane];
		if (nLane != 0 && !EnsureWorker(stLane))
		{
			return false;
		}
		Slot &stSlot = stLane.arrFrames[nFrame];
		if (stSlot.stAllocator.Get() == nullptr && FAILED(pDevice->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_BUNDLE, IID_PPV_ARGS(stSlot.stAllocator.Put()))))
		{
			return false;
		}
		if (FAILED(stSlot.stAllocator->Reset()))
		{
			return false;
		}
		for (std::size_t nView = nLane; nView < nViews; nView += nActive)
		{
			const std::size_t nList = nView / nActive;
			if (nList == stSlot.arrLists.size())
			{
				stSlot.arrLists.emplace_back();
				if (FAILED(pDevice->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_BUNDLE, stSlot.stAllocator.Get(), nullptr,
													  IID_PPV_ARGS(stSlot.arrLists.back().Put()))) ||
					FAILED(stSlot.arrLists.back()->Close()))
				{
					return false;
				}
			}
			const std::uint32_t nSlot = stSnapshot.arrViews[nView].nSlot;
			if (arrBundles.size() <= nSlot)
			{
				arrBundles.resize(nSlot + 1, nullptr);
			}
			arrBundles[nSlot] = stSlot.arrLists[nList].Get();
		}
		stLane.nIndex = nLane;
		stLane.nStride = nActive;
		stLane.nFrame = nFrame;
		stLane.pSnapshot = &stSnapshot;
	}
	std::uint32_t nStarted = 1;
	while (nStarted < nActive && SetEvent(arrLanes[nStarted].hStart))
	{
		++nStarted;
	}
	RecordLane(arrLanes[0]);
	bool bSucceeded = nStarted == nActive && arrLanes[0].bSucceeded;
	for (std::uint32_t nLane = 1; nLane < nStarted; ++nLane)
	{
		if (WaitForSingleObject(arrLanes[nLane].hDone, INFINITE) != WAIT_OBJECT_0)
		{
			std::abort();
		}
		bSucceeded = bSucceeded && arrLanes[nLane].bSucceeded;
	}
	out_stStatistics.nThreads = nStarted;
	for (std::uint32_t nLane = 0; nLane < nStarted; ++nLane)
	{
		out_stStatistics.arrThreads[nLane] = arrLanes[nLane].stStatistics;
		arrLanes[nLane].pSnapshot = nullptr;
	}
	if (!bSucceeded)
	{
		Clear();
	}
	return bSucceeded;
}

ID3D12GraphicsCommandList *ShadowRecording::Bundle(std::uint32_t nSlot) const noexcept
{
	return nSlot < arrBundles.size() ? arrBundles[nSlot] : nullptr;
}

void ShadowRecording::Clear() noexcept
{
	arrBundles.clear();
}

} // namespace EngineNext::Rendering
