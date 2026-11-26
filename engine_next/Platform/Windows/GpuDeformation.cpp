/**************************************************************************/
/*  GpuDeformation.cpp                                                    */
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

#include "engine_next/Platform/Windows/GpuDeformation.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::uint64_t MAX_BYTES = 256ULL * 1024 * 1024;

std::uint64_t AllocationBytes(ID3D12Device *pDevice, std::uint64_t nBytes)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = nBytes;
	stDescription.Height = 1;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	return pDevice->GetResourceAllocationInfo(0, 1, &stDescription).SizeInBytes;
}

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "gpu_deformation", "$", pMessage);
	return false;
}

bool CreateBuffer(ID3D12Device *pDevice, std::uint64_t nBytes, D3D12_HEAP_TYPE eHeap, D3D12_RESOURCE_STATES eState,
				  ComOwner<ID3D12Resource> &out_stResource)
{
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eHeap;
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = nBytes;
	stDescription.Height = 1;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	return SUCCEEDED(pDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, eState, nullptr, IID_PPV_ARGS(out_stResource.Put())));
}
} // namespace

bool GpuDeformation::Initialize(ID3D12Device *pDevice, const std::vector<MeshVertex> &arrVertices,
								const std::vector<DeformationRange> &in_arrRanges, Assets::Diagnostics &out_arrDiagnostics)
{
	if (pDevice == nullptr || stPrevious.Get() != nullptr || arrVertices.empty() || in_arrRanges.empty() || arrVertices.size() > UINT32_MAX)
	{
		return Fail(out_arrDiagnostics, "Initialization needs a new owner and nonempty bounded vertex ranges.");
	}
	GpuDeformation stCandidate;
	stCandidate.nOwnerThread = GetCurrentThreadId();
	stCandidate.nPreviousBytes = arrVertices.size() * sizeof(std::array<float, 3>);
	std::uint64_t nPreviousEnd = 0;
	for (const DeformationRange &stRange : in_arrRanges)
	{
		const std::uint64_t nEnd = static_cast<std::uint64_t>(stRange.nFirstVertex) + stRange.nVertexCount;
		if (stRange.nVertexCount == 0 || stRange.nFirstVertex < nPreviousEnd || nEnd > arrVertices.size() ||
			stRange.nVertexCount > (MAX_BYTES - stCandidate.nUploadBytes) / (sizeof(MeshVertex) + sizeof(std::array<float, 3>)))
		{
			return Fail(out_arrDiagnostics, "Deformation ranges overlap, exceed vertices or exhaust the upload budget.");
		}
		nPreviousEnd = nEnd;
		stCandidate.nUploadBytes += stRange.nVertexCount * (sizeof(MeshVertex) + sizeof(std::array<float, 3>));
	}
	if (stCandidate.nPreviousBytes > MAX_BYTES || stCandidate.nUploadBytes > MAX_BYTES / FRAME_COUNT ||
		stCandidate.nPreviousBytes * 2 + stCandidate.nUploadBytes * FRAME_COUNT > MAX_BYTES)
	{
		return Fail(out_arrDiagnostics, "Deformation resident and staging data exceed the GPU budget.");
	}
	const std::uint64_t nPreviousAllocation = AllocationBytes(pDevice, stCandidate.nPreviousBytes);
	const std::uint64_t nUploadAllocation = AllocationBytes(pDevice, stCandidate.nUploadBytes);
	if (nPreviousAllocation > MAX_BYTES / 2 || nUploadAllocation > MAX_BYTES / FRAME_COUNT ||
		nPreviousAllocation * 2 > MAX_BYTES - nUploadAllocation * FRAME_COUNT)
	{
		return Fail(out_arrDiagnostics, "Aligned deformation allocations exceed the GPU budget.");
	}
	stCandidate.nResidentBytes = nPreviousAllocation * 2 + nUploadAllocation * FRAME_COUNT;
	stCandidate.arrRanges = in_arrRanges;
	if (!CreateBuffer(pDevice, stCandidate.nPreviousBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON, stCandidate.stPrevious) ||
		!CreateBuffer(pDevice, stCandidate.nPreviousBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ, stCandidate.stInitialUpload))
	{
		return Fail(out_arrDiagnostics, "Could not allocate previous-position resources.");
	}
	for (Frame &stFrame : stCandidate.arrFrames)
	{
		if (!CreateBuffer(pDevice, stCandidate.nUploadBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ, stFrame.stUpload))
		{
			return Fail(out_arrDiagnostics, "Could not allocate retired deformation upload slots.");
		}
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stCandidate.stInitialUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail(out_arrDiagnostics, "Could not map initial previous positions.");
	}
	for (std::size_t nVertex = 0; nVertex < arrVertices.size(); ++nVertex)
	{
		std::memcpy(static_cast<std::uint8_t *>(pMapped) + nVertex * sizeof(std::array<float, 3>), arrVertices[nVertex].arrPosition.data(), sizeof(std::array<float, 3>));
	}
	stCandidate.stInitialUpload->Unmap(0, nullptr);
	(void)stCandidate.stPrevious->SetName(L"EngineNext.PreviousDeformedPositions");
	*this = std::move(stCandidate);
	return true;
}

void GpuDeformation::RecordInitialization(ID3D12GraphicsCommandList *pList) const
{
	D3D12_RESOURCE_BARRIER stBarrier{};
	stBarrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
	stBarrier.Transition.pResource = stPrevious.Get();
	stBarrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COMMON;
	stBarrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_DEST;
	stBarrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
	pList->ResourceBarrier(1, &stBarrier);
	pList->CopyBufferRegion(stPrevious.Get(), 0, stInitialUpload.Get(), 0, nPreviousBytes);
	stBarrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
	stBarrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COMMON;
	pList->ResourceBarrier(1, &stBarrier);
}

bool GpuDeformation::PrepareFrame(std::uint32_t nFrame, const DeformationFrame &stCurrent, const DeformationFrame *pPrevious,
								  bool bHistoryValid, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (GetCurrentThreadId() != nOwnerThread || nFrame >= FRAME_COUNT || nPendingFrame != FRAME_COUNT ||
		nCompletedFence == UINT64_MAX || arrFrames[nFrame].nFence > nCompletedFence || stCurrent.arrDraws.size() != arrRanges.size())
	{
		return Fail(out_arrDiagnostics, "Deformation upload requires the owner and a retired frame slot.");
	}
	for (std::size_t nRange = 0; nRange < arrRanges.size(); ++nRange)
	{
		if (stCurrent.arrDraws[nRange].nDraw != arrRanges[nRange].nDraw || stCurrent.arrDraws[nRange].arrVertices.size() != arrRanges[nRange].nVertexCount ||
			(bHistoryValid && (pPrevious == nullptr || pPrevious->arrDraws.size() != arrRanges.size() || pPrevious->arrDraws[nRange].nDraw != arrRanges[nRange].nDraw || pPrevious->arrDraws[nRange].arrVertices.size() != arrRanges[nRange].nVertexCount)))
		{
			return Fail(out_arrDiagnostics, "Current or previous deformation does not match the stable GPU layout.");
		}
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(arrFrames[nFrame].stUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail(out_arrDiagnostics, "Could not map the retired deformation slot.");
	}
	std::uint64_t nOffset = 0;
	dMaxLocalMotion = 0;
	for (std::size_t nRange = 0; nRange < arrRanges.size(); ++nRange)
	{
		const std::vector<MeshVertex> &arrCurrent = stCurrent.arrDraws[nRange].arrVertices;
		const std::vector<MeshVertex> &arrPrevious = bHistoryValid ? pPrevious->arrDraws[nRange].arrVertices : arrCurrent;
		const std::uint64_t nVertexBytes = arrCurrent.size() * sizeof(MeshVertex);
		std::memcpy(static_cast<std::uint8_t *>(pMapped) + nOffset, arrCurrent.data(), static_cast<std::size_t>(nVertexBytes));
		nOffset += nVertexBytes;
		for (std::size_t nVertex = 0; nVertex < arrCurrent.size(); ++nVertex)
		{
			std::memcpy(static_cast<std::uint8_t *>(pMapped) + nOffset, arrPrevious[nVertex].arrPosition.data(), sizeof(std::array<float, 3>));
			nOffset += sizeof(std::array<float, 3>);
			double dSquared = 0;
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				const double dDelta = static_cast<double>(arrCurrent[nVertex].arrPosition[nAxis]) - arrPrevious[nVertex].arrPosition[nAxis];
				dSquared += dDelta * dDelta;
			}
			dMaxLocalMotion = (std::max)(dMaxLocalMotion, std::sqrt(dSquared));
		}
	}
	arrFrames[nFrame].stUpload->Unmap(0, nullptr);
	nPendingFrame = nFrame;
	return true;
}

bool GpuDeformation::Record(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, ID3D12Resource *pVertices, Assets::Diagnostics &out_arrDiagnostics)
{
	if (GetCurrentThreadId() != nOwnerThread || nPendingFrame != nFrame || nFrame >= FRAME_COUNT || bRecorded ||
		pList == nullptr || pList->GetType() != D3D12_COMMAND_LIST_TYPE_DIRECT || pVertices == nullptr ||
		pVertices->GetDesc().Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||
		pVertices->GetDesc().Width < nPreviousBytes / sizeof(std::array<float, 3>) * sizeof(MeshVertex))
	{
		return Fail(out_arrDiagnostics, "Deformation copy does not match the prepared frame.");
	}
	std::uint64_t nOffset = 0;
	for (const DeformationRange &stRange : arrRanges)
	{
		const std::uint64_t nVertexBytes = static_cast<std::uint64_t>(stRange.nVertexCount) * sizeof(MeshVertex);
		const std::uint64_t nPositionBytes = static_cast<std::uint64_t>(stRange.nVertexCount) * sizeof(std::array<float, 3>);
		pList->CopyBufferRegion(pVertices, static_cast<std::uint64_t>(stRange.nFirstVertex) * sizeof(MeshVertex), arrFrames[nFrame].stUpload.Get(), nOffset, nVertexBytes);
		nOffset += nVertexBytes;
		pList->CopyBufferRegion(stPrevious.Get(), static_cast<std::uint64_t>(stRange.nFirstVertex) * sizeof(std::array<float, 3>), arrFrames[nFrame].stUpload.Get(), nOffset, nPositionBytes);
		nOffset += nPositionBytes;
	}
	bRecorded = true;
	return true;
}

bool GpuDeformation::Commit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (GetCurrentThreadId() != nOwnerThread || nPendingFrame != nFrame || nFrame >= FRAME_COUNT || !bRecorded ||
		nFence == 0 || nFence == UINT64_MAX || nFence <= nLatestFence)
	{
		return Fail(out_arrDiagnostics, "Only the prepared deformation frame can be committed.");
	}
	arrFrames[nFrame].nFence = nFence;
	nLatestFence = nFence;
	nPendingFrame = FRAME_COUNT;
	bRecorded = false;
	return true;
}

bool GpuDeformation::Cancel(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	if (GetCurrentThreadId() != nOwnerThread || nPendingFrame != nFrame)
	{
		return Fail(out_arrDiagnostics, "Only an unsubmitted deformation frame can be canceled.");
	}
	nPendingFrame = FRAME_COUNT;
	bRecorded = false;
	return true;
}

ID3D12Resource *GpuDeformation::PreviousPositions() const noexcept
{
	return stPrevious.Get();
}

ID3D12Resource *GpuDeformation::Upload(std::uint32_t nFrame) const noexcept
{
	return nFrame < FRAME_COUNT ? arrFrames[nFrame].stUpload.Get() : nullptr;
}

std::uint64_t GpuDeformation::MemoryBytes() const noexcept
{
	return nResidentBytes;
}

double GpuDeformation::MaxLocalMotion() const noexcept
{
	return dMaxLocalMotion;
}
std::uint64_t GpuDeformation::UploadBytes() const noexcept
{
	return nUploadBytes;
}

} // namespace EngineNext::Rendering
