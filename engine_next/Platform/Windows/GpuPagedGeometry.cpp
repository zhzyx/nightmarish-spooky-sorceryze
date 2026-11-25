/**************************************************************************/
/*  GpuPagedGeometry.cpp                                                  */
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

#include "engine_next/Platform/Windows/GpuPagedGeometry.h"
#include "engine_next/Rendering/Cook/MeshCluster.h"
#include <algorithm>
#include <cstddef>
#include <cstring>
#include <limits>
#include <utility>
namespace EngineNext::Rendering
{
namespace
{
bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage, const char *pCode = "paged_gpu_geometry")
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, "$.geometry_culling", pMessage);
	return false;
}
D3D12_RESOURCE_DESC BufferDescription(std::uint64_t nBytes)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = (std::max)(std::uint64_t{ 1 }, nBytes);
	stDescription.Height = 1;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	return stDescription;
}
bool CreateBuffer(ID3D12Device *pDevice, std::uint64_t nBytes, D3D12_HEAP_TYPE eType, ComOwner<ID3D12Resource> &out_stResource)
{
	const D3D12_RESOURCE_DESC stDescription = BufferDescription(nBytes);
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eType;
	stHeap.CreationNodeMask = 1;
	stHeap.VisibleNodeMask = 1;
	return SUCCEEDED(pDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription,
													  eType == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ : D3D12_RESOURCE_STATE_COMMON,
													  nullptr, IID_PPV_ARGS(out_stResource.Put())));
}
} // namespace
bool GpuPagedGeometry::IsOwner() const noexcept
{
	return nOwner == 0 || nOwner == GetCurrentThreadId();
}
bool GpuPagedGeometry::Initialize(ID3D12Device *in_pDevice, const RenderScene &stSource, const GpuPageIndex &in_stIndex,
								  const GeometryClusterSet &in_stFallback, const GeometryPageView &in_stFallbackView,
								  const GeometrySettings &in_stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || pDevice != nullptr || in_pDevice == nullptr || in_stFallback.arrClusters.empty() ||
		in_stFallback.bCapacityFallback || !ValidateGeometrySettings(in_stSettings, out_arrDiagnostics) ||
		!VerifyPagedScene(stSource, in_stIndex, out_arrDiagnostics))
	{
		return Fail(out_arrDiagnostics, "Paged geometry requires a fresh owner, "
										"verified source and complete fallback.");
	}
	GpuPagedGeometry stCandidate;
	stCandidate.nOwner = GetCurrentThreadId();
	stCandidate.pDevice = in_pDevice;
	stCandidate.pSource = &stSource;
	stCandidate.stIndex = in_stIndex;
	stCandidate.stSettings = in_stSettings;
	stCandidate.stFallback = in_stFallback;
	stCandidate.stFallbackView = in_stFallbackView;
	stCandidate.arrPageSlots.assign(in_stIndex.Pages().size(), UINT32_MAX);
	std::vector<PageDescription> arrDescriptions;
	for (std::uint32_t nPage = 0; nPage < in_stIndex.Pages().size(); ++nPage)
	{
		const GpuPageDescription &stPage = in_stIndex.Pages()[nPage];
		if (stPage.eKind != GpuPageKind::MeshGeometry)
		{
			continue;
		}
		const D3D12_RESOURCE_DESC stDescription = BufferDescription(stPage.nBytes);
		const D3D12_RESOURCE_ALLOCATION_INFO stAllocation = in_pDevice->GetResourceAllocationInfo(0, 1, &stDescription);
		if (stAllocation.SizeInBytes == 0 || stAllocation.SizeInBytes == UINT64_MAX)
		{
			return Fail(out_arrDiagnostics, "Device rejected a mesh page allocation.", "geometry_allocation");
		}
		Slot stSlot;
		stSlot.nPage = nPage;
		stSlot.nBufferBytes = stPage.nBytes;
		stCandidate.arrPageSlots[nPage] = static_cast<std::uint32_t>(stCandidate.arrSlots.size());
		stCandidate.arrSlots.push_back(std::move(stSlot));
		arrDescriptions.push_back({ static_cast<std::uint64_t>(nPage) + 1, stAllocation.SizeInBytes, stAllocation.SizeInBytes, stPage.bPinned });
	}
	const std::uint64_t nViewBytes = (stCandidate.arrSlots.size() + 1) * sizeof(GeometryPageView);
	const D3D12_RESOURCE_DESC stViewDescription = BufferDescription(nViewBytes);
	const D3D12_RESOURCE_ALLOCATION_INFO stViewAllocation = in_pDevice->GetResourceAllocationInfo(0, 1, &stViewDescription);
	if (stViewAllocation.SizeInBytes == UINT64_MAX || stViewAllocation.SizeInBytes > in_stSettings.nPageStagingBytes / GEOMETRY_FRAME_COUNT)
	{
		return Fail(out_arrDiagnostics, "Page view tables exceed the staging budget.", "geometry_allocation");
	}
	stCandidate.nOverhead = stViewAllocation.SizeInBytes * GEOMETRY_FRAME_COUNT;
	if (stCandidate.nOverhead >= in_stSettings.nPageStagingBytes ||
		!stCandidate.stResidency.Initialize({ in_stSettings.nPageGpuBytes, in_stSettings.nPageStagingBytes - stCandidate.nOverhead, 2 }, arrDescriptions, out_arrDiagnostics))
	{
		return Fail(out_arrDiagnostics, "Pinned page and staging allocations exceed their budgets.", "geometry_allocation");
	}
	for (Frame &stFrame : stCandidate.arrFrames)
	{
		if (!CreateBuffer(in_pDevice, nViewBytes, D3D12_HEAP_TYPE_UPLOAD, stFrame.stViews))
		{
			return Fail(out_arrDiagnostics, "Could not create page view upload tables.", "geometry_allocation");
		}
	}
	stCandidate.arrDrawBuckets.assign(stSource.arrInstances.size(), UINT32_MAX);
	for (const GeometryCluster &stCluster : in_stFallback.arrClusters)
	{
		if (stCluster.stInput.arrDraw[3] >= stCandidate.arrDrawBuckets.size() || stCluster.arrMetadata[0] >= in_stFallback.arrBuckets.size())
		{
			return Fail(out_arrDiagnostics, "Fallback draw identity is invalid.");
		}
		stCandidate.arrDrawBuckets[stCluster.stInput.arrDraw[3]] = stCluster.arrMetadata[0];
	}
	Swap(stCandidate);
	return true;
}
void GpuPagedGeometry::Sweep()
{
	arrResources.clear();
	for (Slot &stSlot : arrSlots)
	{
		const PageRecord *pRecord = stResidency.Find(static_cast<std::uint64_t>(stSlot.nPage) + 1);
		if (pRecord->eState == PageState::Missing || pRecord->eState == PageState::RetryDelay || pRecord->eState == PageState::Queued)
		{
			stSlot.stGpu.Reset();
			stSlot.stUpload.Reset();
			stSlot.arrClusters.clear();
		}
		else if (pRecord->eState == PageState::Resident)
		{
			stSlot.stUpload.Reset();
		}
		if (stSlot.stGpu.Get() != nullptr)
		{
			arrResources.push_back(stSlot.stGpu.Get());
		}
	}
}
bool GpuPagedGeometry::Load(std::uint32_t nSlot, Assets::Diagnostics &out_arrDiagnostics)
{
	Slot &stSlot = arrSlots[nSlot];
	GpuMeshPage stPage;
	if (!ReadGpuMeshPage(stIndex, stSlot.nPage, stPage, stIo, out_arrDiagnostics))
	{
		return false;
	}
	MeshPrimitive stPrimitive;
	stPrimitive.arrVertices = std::move(stPage.arrVertices);
	stPrimitive.arrIndices = std::move(stPage.arrIndices);
	if (!CookMeshClusters(stPrimitive, stPrimitive.arrClusters, out_arrDiagnostics))
	{
		return false;
	}
	std::vector<GpuClusterInput> arrClusters;
	const std::array<double, 16> arrIdentity{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	std::uint32_t nFirstIndex = 0;
	for (const MeshCluster &stCluster : stPrimitive.arrClusters)
	{
		GpuClusterInput stInput;
		if (!BuildClusterInput(stCluster, arrIdentity, nFirstIndex, 0, 0, stInput, out_arrDiagnostics))
		{
			return false;
		}
		nFirstIndex += static_cast<std::uint32_t>(stCluster.arrTriangleIndices.size());
		arrClusters.push_back(stInput);
	}
	const std::uint64_t nVertexBytes = stPrimitive.arrVertices.size() * sizeof(MeshVertex);
	const std::uint64_t nIndexOffset = (nVertexBytes + 15) & ~std::uint64_t{ 15 };
	const std::uint64_t nIndexBytes = stPrimitive.arrIndices.size() * sizeof(std::uint32_t);
	if (nIndexOffset > stSlot.nBufferBytes || nIndexBytes > stSlot.nBufferBytes - nIndexOffset ||
		!CreateBuffer(pDevice, stSlot.nBufferBytes, D3D12_HEAP_TYPE_DEFAULT, stSlot.stGpu) ||
		!CreateBuffer(pDevice, stSlot.nBufferBytes, D3D12_HEAP_TYPE_UPLOAD, stSlot.stUpload))
	{
		return Fail(out_arrDiagnostics, "Could not allocate mesh page upload buffers.", "geometry_allocation");
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stSlot.stUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail(out_arrDiagnostics, "Could not map a mesh page upload.");
	}
	std::memset(pMapped, 0, static_cast<std::size_t>(stSlot.nBufferBytes));
	std::memcpy(pMapped, stPrimitive.arrVertices.data(), static_cast<std::size_t>(nVertexBytes));
	std::memcpy(static_cast<std::uint8_t *>(pMapped) + nIndexOffset, stPrimitive.arrIndices.data(), static_cast<std::size_t>(nIndexBytes));
	stSlot.stUpload->Unmap(0, nullptr);
	const std::uint64_t nAddress = stSlot.stGpu->GetGPUVirtualAddress();
	stSlot.stView.stVertex = { nAddress, static_cast<UINT>(nVertexBytes), sizeof(MeshVertex) };
	stSlot.stView.stIndex = { nAddress + nIndexOffset, static_cast<UINT>(nIndexBytes), DXGI_FORMAT_R32_UINT };
	stSlot.arrClusters = std::move(arrClusters);
	return true;
}
bool GpuPagedGeometry::BuildActive(const PagedFrameSelection &stSelection, Assets::Diagnostics &out_arrDiagnostics)
{
	bool bSame = bActiveCommitted &&
			stActive.arrBuckets.size() == stFallback.arrBuckets.size() &&
			stActive.nDrawCount == stFallback.nDrawCount;
	if (bUsesLod)
	{
		bSame = bSame && stSelection.bRootsReady &&
				stSelection.arrDraws.size() == stPrevious.arrDraws.size();
		for (std::size_t nDraw = 0; bSame && nDraw < stSelection.arrDraws.size();
			 ++nDraw)
		{
			bSame = stSelection.arrDraws[nDraw].nTree ==
							stPrevious.arrDraws[nDraw].nTree &&
					stSelection.arrDraws[nDraw].stCut.arrNodes ==
							stPrevious.arrDraws[nDraw].stCut.arrNodes;
		}
	}
	else
	{
		bSame = bSame && !stSelection.bRootsReady;
	}
	bSame = bSame && arrActiveSlots.size() == arrActiveGenerations.size();
	for (std::size_t nIndex = 0; bSame && nIndex < arrActiveSlots.size(); ++nIndex)
	{
		const Slot &stSlot = arrSlots[arrActiveSlots[nIndex]];
		const PageRecord *pRecord = stResidency.Find(stSlot.stTicket.nPageId);
		bSame = pRecord != nullptr && pRecord->eState == PageState::Resident &&
				pRecord->nGeneration == arrActiveGenerations[nIndex];
	}
	for (std::size_t nBucket = 0; bSame && nBucket < stActive.arrBuckets.size();
		 ++nBucket)
	{
		bSame = stActive.arrBuckets[nBucket].nMaterial ==
						stFallback.arrBuckets[nBucket].nMaterial &&
				stActive.arrBuckets[nBucket].nFlags ==
						stFallback.arrBuckets[nBucket].nFlags;
	}
	if (bSame)
	{
		arrUsed = arrActiveSlots;
		if (nActiveReuses != UINT64_MAX)
		{
			++nActiveReuses;
		}
		return true;
	}
	bActiveCommitted = false;
	stActive = stFallback;
	bUsesLod = false;
	arrUsed.clear();
	arrActiveSlots.clear();
	arrActiveGenerations.clear();
	const std::uint32_t nFallbackSlot = static_cast<std::uint32_t>(arrSlots.size());
	for (GeometryCluster &stCluster : stActive.arrClusters)
	{
		stCluster.arrMetadata[1] = nFallbackSlot;
	}
	if (!stSelection.bRootsReady)
	{
		return true;
	}
	std::vector<std::vector<GeometryCluster>> arrBucketClusters(stFallback.arrBuckets.size());
	std::vector<std::uint8_t> arrUsedSlots(arrSlots.size(), 0);
	std::size_t nTotal = 0;
	for (std::uint32_t nDraw = 0; nDraw < stSelection.arrDraws.size(); ++nDraw)
	{
		const PagedDrawSelection &stDraw = stSelection.arrDraws[nDraw];
		if (stDraw.nTree == UINT32_MAX)
		{
			continue;
		}
		const std::uint32_t nBucket = arrDrawBuckets[nDraw];
		if (nBucket >= arrBucketClusters.size())
		{
			return Fail(out_arrDiagnostics, "Paged draw has no original material bucket.");
		}
		const GpuLodTree &stTree = stIndex.Trees()[stDraw.nTree];
		for (std::uint32_t nNode : stDraw.stCut.arrNodes)
		{
			const std::uint32_t nSlot = arrPageSlots[stTree.arrNodes[nNode].nPage];
			if (nSlot >= arrSlots.size() || arrSlots[nSlot].stGpu.Get() == nullptr)
			{
				return Fail(out_arrDiagnostics, "Selected page has no resident physical buffer.");
			}
			arrUsedSlots[nSlot] = 1;
			for (const GpuClusterInput &stInput : arrSlots[nSlot].arrClusters)
			{
				if (++nTotal > stSettings.nMaxCommands)
				{
					return true;
				}
				GeometryCluster stCluster;
				stCluster.stInput = stInput;
				stCluster.stInput.arrDraw[3] = nDraw;
				stCluster.arrMetadata = { nBucket, nSlot, nNode + 1, stTree.arrNodes[nNode].nChildCount };
				arrBucketClusters[nBucket].push_back(stCluster);
			}
		}
	}
	GeometryClusterSet stCandidate;
	stCandidate.nDrawCount = stFallback.nDrawCount;
	stCandidate.arrBuckets = stFallback.arrBuckets;
	for (std::size_t nBucket = 0; nBucket < arrBucketClusters.size(); ++nBucket)
	{
		GeometryBucket &stBucket = stCandidate.arrBuckets[nBucket];
		stBucket.nFirstCommand = static_cast<std::uint32_t>(stCandidate.arrClusters.size());
		stBucket.nCommandCapacity = static_cast<std::uint32_t>(arrBucketClusters[nBucket].size());
		for (const GeometryCluster &stCluster : arrBucketClusters[nBucket])
		{
			stCandidate.nTriangleCount += stCluster.stInput.arrDraw[0] / 3;
		}
		stCandidate.arrClusters.insert(stCandidate.arrClusters.end(), arrBucketClusters[nBucket].begin(), arrBucketClusters[nBucket].end());
	}
	stCandidate.nCandidateCount = stCandidate.arrClusters.size();
	for (std::uint32_t nSlot = 0; nSlot < arrUsedSlots.size(); ++nSlot)
	{
		if (arrUsedSlots[nSlot] != 0)
		{
			arrUsed.push_back(nSlot);
			arrActiveSlots.push_back(nSlot);
			arrActiveGenerations.push_back(arrSlots[nSlot].stTicket.nGeneration);
		}
	}
	stActive = std::move(stCandidate);
	bUsesLod = true;
	return true;
}

bool GpuPagedGeometry::Prepare(std::uint32_t nFrame, const std::vector<std::array<float, 16>> &arrWorlds,
							   const LodView &stView, std::uint64_t nCompletedFence, std::uint64_t in_nTick,
							   Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || pDevice == nullptr || nPendingFrame != GEOMETRY_FRAME_COUNT || nFrame >= GEOMETRY_FRAME_COUNT ||
		arrFrames[nFrame].nFence > nCompletedFence || nCompletedFence == UINT64_MAX || in_nTick < nTick)
	{
		return Fail(out_arrDiagnostics, "Page preparation requires a retired frame and monotonic owner time.");
	}
	if (!stResidency.AdvanceFences(nCompletedFence, nCompletedFence, in_nTick, out_arrDiagnostics))
	{
		return false;
	}
	nTick = in_nTick;
	nCompleted = nCompletedFence;
	Sweep();
	const auto fnSnapshot = [this]()
	{
		std::vector<std::uint8_t> arrResident(stIndex.Pages().size(), 0);
		for (const Slot &stSlot : arrSlots)
		{
			const PageRecord *pRecord = stResidency.Find(static_cast<std::uint64_t>(stSlot.nPage) + 1);
			arrResident[stSlot.nPage] = pRecord->eState == PageState::Resident ? 1 : 0;
		}
		return arrResident;
	};
	const std::vector<std::uint8_t> arrRequestResident = fnSnapshot();
	PagedFrameSelection stRequests;
	if (!BuildPagedFrameSelection(stIndex, *pSource, arrWorlds, arrRequestResident, stView, stSettings, stPrevious, stRequests, out_arrDiagnostics, &stWorldCache))
	{
		return false;
	}
	nPendingFrame = nFrame;
	bRecorded = false;
	arrPrepared.clear();
	std::uint32_t nAttempts = 0;
	for (std::uint32_t nPage : stRequests.arrRequestedPages)
	{
		if (nAttempts >= stSettings.nMaxPageLoads)
		{
			break;
		}
		PageRequestResult eResult = PageRequestResult::Pending;
		Assets::Diagnostics arrPageDiagnostics;
		const std::uint64_t nId = static_cast<std::uint64_t>(nPage) + 1;
		if (!stResidency.Request(nId, nTick, eResult, arrPageDiagnostics))
		{
			(void)Discard(nFrame, out_arrDiagnostics);
			return Fail(out_arrDiagnostics, "Page request state failed.");
		}
		const PageRecord *pRecord = stResidency.Find(nId);
		if (pRecord->eState != PageState::Queued)
		{
			continue;
		}
		++nAttempts;
		const std::uint32_t nSlot = arrPageSlots[nPage];
		if (!stResidency.BeginLoad(nId, nTick, arrSlots[nSlot].stTicket, arrPageDiagnostics))
		{
			if (nBudgetStalls != UINT64_MAX)
			{
				++nBudgetStalls;
			}
			continue;
		}
		Sweep();
		const bool bPageReady = Load(nSlot, arrPageDiagnostics);
		if (!stResidency.FinishLoad(arrSlots[nSlot].stTicket, bPageReady, nTick, out_arrDiagnostics))
		{
			(void)Discard(nFrame, out_arrDiagnostics);
			return false;
		}
		if (bPageReady)
		{
			arrPrepared.push_back(nSlot);
		}
		else if (!arrPageDiagnostics.empty())
		{
			strLastPageError = arrPageDiagnostics.back().strMessage;
		}
	}
	Sweep();
	const std::vector<std::uint8_t> arrFinalResident = fnSnapshot();
	if (arrFinalResident == arrRequestResident)
	{
		// Only reuse within this owner-thread preparation. World/view/settings and
		// committed previous cut are unchanged; upload-ready pages remain absent.
		stPending = std::move(stRequests);
		if (nSelectionReuses != UINT64_MAX)
		{
			++nSelectionReuses;
		}
	}
	else if (!BuildPagedFrameSelection(stIndex, *pSource, arrWorlds, arrFinalResident, stView, stSettings, stPrevious, stPending, out_arrDiagnostics, &stWorldCache))
	{
		(void)Discard(nFrame, out_arrDiagnostics);
		return false;
	}
	if (!BuildActive(stPending, out_arrDiagnostics))
	{
		(void)Discard(nFrame, out_arrDiagnostics);
		return false;
	}
	arrChangedDraws.clear();
	for (std::uint32_t nDraw = 0; nDraw < arrDrawBuckets.size(); ++nDraw)
	{
		if (arrDrawBuckets[nDraw] == UINT32_MAX)
		{
			continue;
		}
		const PagedDrawSelection *pBefore = stPrevious.arrDraws.empty() ? nullptr : &stPrevious.arrDraws[nDraw];
		const PagedDrawSelection *pAfter = bUsesLod ? &stPending.arrDraws[nDraw] : nullptr;
		if ((pBefore == nullptr) != (pAfter == nullptr) || (pBefore != nullptr && pAfter != nullptr && (pBefore->nTree != pAfter->nTree || pBefore->stCut.arrNodes != pAfter->stCut.arrNodes)))
		{
			arrChangedDraws.push_back(nDraw);
		}
	}
	std::vector<GeometryPageView> arrViews(arrSlots.size() + 1);
	for (std::uint32_t nSlot = 0; nSlot < arrSlots.size(); ++nSlot)
	{
		const Slot &stSlot = arrSlots[nSlot];
		if (stResidency.Find(static_cast<std::uint64_t>(stSlot.nPage) + 1)->eState == PageState::Resident)
		{
			arrViews[nSlot] = stSlot.stView;
		}
	}
	arrViews.back() = stFallbackView;
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(arrFrames[nFrame].stViews->Map(0, &stNoRead, &pMapped)))
	{
		(void)Discard(nFrame, out_arrDiagnostics);
		return Fail(out_arrDiagnostics, "Cannot map retired page view table.");
	}
	std::memcpy(pMapped, arrViews.data(), arrViews.size() * sizeof(GeometryPageView));
	arrFrames[nFrame].stViews->Unmap(0, nullptr);
	return true;
}
std::uint64_t GpuPagedGeometry::PendingUploadBytes() const noexcept
{
	std::uint64_t nBytes = 0;
	for (std::uint32_t nSlot : arrPrepared)
	{
		nBytes += arrSlots[nSlot].nBufferBytes;
	}
	return nBytes;
}

bool GpuPagedGeometry::RecordUploads(ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nPendingFrame >= GEOMETRY_FRAME_COUNT || bRecorded || pList == nullptr || pList->GetType() != D3D12_COMMAND_LIST_TYPE_DIRECT)
	{
		return Fail(out_arrDiagnostics, "Page upload recording requires the pending DIRECT frame.");
	}
	for (std::uint32_t nSlot : arrPrepared)
	{
		const Slot &stSlot = arrSlots[nSlot];
		pList->CopyBufferRegion(stSlot.stGpu.Get(), 0, stSlot.stUpload.Get(), 0, stSlot.nBufferBytes);
	}
	bRecorded = true;
	return true;
}
bool GpuPagedGeometry::Commit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nPendingFrame != nFrame || !bRecorded || nFrame >= GEOMETRY_FRAME_COUNT ||
		nFence == UINT64_MAX || nFence <= nCompleted || nFence <= nLastFence)
	{
		return Fail(out_arrDiagnostics, "Page commit requires submitted commands and a future fence.");
	}
	for (std::uint32_t nSlot : arrPrepared)
	{
		const Slot &stSlot = arrSlots[nSlot];
		const PageRecord *pRecord = stResidency.Find(stSlot.stTicket.nPageId);
		if (pRecord == nullptr || pRecord->eState != PageState::UploadReady || pRecord->nGeneration != stSlot.stTicket.nGeneration)
		{
			return Fail(out_arrDiagnostics, "Prepared page ticket changed before submission.");
		}
	}
	for (std::uint32_t nSlot : arrUsed)
	{
		const Slot &stSlot = arrSlots[nSlot];
		const PageRecord *pRecord = stResidency.Find(stSlot.stTicket.nPageId);
		if (pRecord == nullptr || pRecord->eState != PageState::Resident || pRecord->nGeneration != stSlot.stTicket.nGeneration)
		{
			return Fail(out_arrDiagnostics, "Selected page generation is not resident.");
		}
	}
	for (std::uint32_t nSlot : arrPrepared)
	{
		if (!stResidency.SubmitUpload(arrSlots[nSlot].stTicket, nFence, out_arrDiagnostics))
		{
			return false;
		}
	}
	for (std::uint32_t nSlot : arrUsed)
	{
		if (!stResidency.MarkUsed(arrSlots[nSlot].stTicket, nFence, nTick, out_arrDiagnostics))
		{
			return false;
		}
	}
	arrFrames[nFrame].nFence = nFence;
	nLastFence = nFence;
	stPrevious = bUsesLod ? stPending : PagedFrameSelection{};
	bActiveCommitted = true;
	arrPrepared.clear();
	arrUsed.clear();
	nPendingFrame = GEOMETRY_FRAME_COUNT;
	return true;
}
bool GpuPagedGeometry::Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nPendingFrame != nFrame || nFrame >= GEOMETRY_FRAME_COUNT)
	{
		return Fail(out_arrDiagnostics, "Page discard requires the current unsubmitted frame.");
	}
	for (std::uint32_t nSlot : arrPrepared)
	{
		if (!stResidency.CancelPrepared(arrSlots[nSlot].stTicket, nTick, out_arrDiagnostics))
		{
			return false;
		}
	}
	arrPrepared.clear();
	arrUsed.clear();
	nPendingFrame = GEOMETRY_FRAME_COUNT;
	bRecorded = false;
	bActiveCommitted = false;
	Sweep();
	return true;
}
bool GpuPagedGeometry::Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nPendingFrame != GEOMETRY_FRAME_COUNT || nCompletedFence < nLastFence)
	{
		return Fail(out_arrDiagnostics, "Page resources remain pending or in flight.");
	}
	GpuPagedGeometry stEmpty;
	Swap(stEmpty);
	return true;
}
const GeometryClusterSet &GpuPagedGeometry::ActiveGeometry() const noexcept
{
	return stActive;
}
const std::vector<ID3D12Resource *> &GpuPagedGeometry::Resources() const noexcept
{
	return arrResources;
}
std::uint64_t GpuPagedGeometry::PageViews(std::uint32_t nFrame) const noexcept
{
	return nFrame < GEOMETRY_FRAME_COUNT && arrFrames[nFrame].stViews.Get() != nullptr ? arrFrames[nFrame].stViews->GetGPUVirtualAddress() : 0;
}
std::uint32_t GpuPagedGeometry::PageViewCount() const noexcept
{
	return static_cast<std::uint32_t>(arrSlots.size() + 1);
}
bool GpuPagedGeometry::UsesLod() const noexcept
{
	return bUsesLod;
}
const std::vector<std::uint32_t> &GpuPagedGeometry::ChangedDraws() const noexcept
{
	return arrChangedDraws;
}
const ResidencyTelemetry &GpuPagedGeometry::Telemetry() const noexcept
{
	return stResidency.GetTelemetry();
}
const GpuPageReadStats &GpuPagedGeometry::IoStatistics() const noexcept
{
	return stIo;
}
std::uint64_t GpuPagedGeometry::OverheadBytes() const noexcept
{
	return nOverhead;
}
std::uint64_t GpuPagedGeometry::BudgetStalls() const noexcept
{
	return nBudgetStalls;
}
std::uint64_t GpuPagedGeometry::ActiveReuses() const noexcept
{
	return nActiveReuses;
}
std::uint64_t GpuPagedGeometry::SelectionReuses() const noexcept
{
	return nSelectionReuses;
}
const PagedWorldCache &GpuPagedGeometry::WorldCache() const noexcept
{
	return stWorldCache;
}
const std::string &GpuPagedGeometry::LastPageError() const noexcept
{
	return strLastPageError;
}
void GpuPagedGeometry::Swap(GpuPagedGeometry &stOther) noexcept
{
	using std::swap;
	swap(nOwner, stOther.nOwner);
	swap(pDevice, stOther.pDevice);
	swap(pSource, stOther.pSource);
	swap(stIndex, stOther.stIndex);
	swap(stSettings, stOther.stSettings);
	swap(stFallback, stOther.stFallback);
	swap(stFallbackView, stOther.stFallbackView);
	swap(stResidency, stOther.stResidency);
	swap(stWorldCache, stOther.stWorldCache);
	swap(stIo, stOther.stIo);
	swap(arrSlots, stOther.arrSlots);
	swap(arrPageSlots, stOther.arrPageSlots);
	swap(arrDrawBuckets, stOther.arrDrawBuckets);
	swap(arrFrames, stOther.arrFrames);
	swap(arrPrepared, stOther.arrPrepared);
	swap(arrUsed, stOther.arrUsed);
	swap(arrActiveSlots, stOther.arrActiveSlots);
	swap(arrActiveGenerations, stOther.arrActiveGenerations);
	swap(arrChangedDraws, stOther.arrChangedDraws);
	swap(arrResources, stOther.arrResources);
	swap(stPrevious, stOther.stPrevious);
	swap(stPending, stOther.stPending);
	swap(stActive, stOther.stActive);
	swap(nPendingFrame, stOther.nPendingFrame);
	swap(nTick, stOther.nTick);
	swap(nLastFence, stOther.nLastFence);
	swap(nOverhead, stOther.nOverhead);
	swap(nCompleted, stOther.nCompleted);
	swap(nBudgetStalls, stOther.nBudgetStalls);
	swap(nActiveReuses, stOther.nActiveReuses);
	swap(nSelectionReuses, stOther.nSelectionReuses);
	swap(strLastPageError, stOther.strLastPageError);
	swap(bRecorded, stOther.bRecorded);
	swap(bUsesLod, stOther.bUsesLod);
	swap(bActiveCommitted, stOther.bActiveCommitted);
}
} // namespace EngineNext::Rendering
