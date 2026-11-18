/**************************************************************************/
/*  GpuShadowPages.cpp                                                    */
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

#include "engine_next/Platform/Windows/GpuShadowPages.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::uint64_t CONSTANT_BYTES = 512;
constexpr std::uint64_t PAGE_CONSTANT_STRIDE = 256;

bool Error(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "virtual_shadow_gpu", "$.shadows.virtual_pages", pMessage);
	return false;
}

D3D12_RESOURCE_DESC Buffer(std::uint64_t nBytes, bool bUav = false)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = nBytes;
	stDescription.Height = stDescription.DepthOrArraySize = stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	stDescription.Flags = bUav ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE;
	return stDescription;
}

bool Allocate(ID3D12Device *pDevice, const D3D12_RESOURCE_DESC &stDescription, D3D12_HEAP_TYPE eHeap,
			  const D3D12_CLEAR_VALUE *pClear, std::uint64_t nBudget, std::uint64_t &io_nAllocated, ComOwner<ID3D12Resource> &out_stResource)
{
	const D3D12_RESOURCE_ALLOCATION_INFO stInfo = pDevice->GetResourceAllocationInfo(0, 1, &stDescription);
	if (stInfo.SizeInBytes == 0 || stInfo.SizeInBytes == UINT64_MAX || io_nAllocated > nBudget || stInfo.SizeInBytes > nBudget - io_nAllocated)
	{
		return false;
	}
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eHeap;
	stHeap.CreationNodeMask = stHeap.VisibleNodeMask = 1;
	const D3D12_RESOURCE_STATES eState = eHeap == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ : eHeap == D3D12_HEAP_TYPE_READBACK ? D3D12_RESOURCE_STATE_COPY_DEST
																																				 : D3D12_RESOURCE_STATE_COMMON;
	if (FAILED(pDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, eState, pClear, IID_PPV_ARGS(out_stResource.Put()))))
	{
		return false;
	}
	io_nAllocated += stInfo.SizeInBytes;
	return true;
}

D3D12_CPU_DESCRIPTOR_HANDLE Cpu(const ShadowPageDescriptors &stBlock, std::uint32_t nOffset)
{
	return { stBlock.stCpu.ptr + static_cast<SIZE_T>(nOffset) * stBlock.nStride };
}

D3D12_GPU_DESCRIPTOR_HANDLE Gpu(const ShadowPageDescriptors &stBlock, std::uint32_t nOffset)
{
	return { stBlock.stGpu.ptr + static_cast<UINT64>(nOffset) * stBlock.nStride };
}

bool Pipeline(ID3D12Device *pDevice, const std::filesystem::path &stDirectory,
			  ComOwner<ID3D12RootSignature> &out_stRoot, ComOwner<ID3D12PipelineState> &out_stPipeline)
{
	const std::array<D3D12_DESCRIPTOR_RANGE, 2> arrRanges{ {
			{ D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 2, 0, 0, 0 },
			{ D3D12_DESCRIPTOR_RANGE_TYPE_UAV, 1, 0, 0, 0 },
	} };
	std::array<D3D12_ROOT_PARAMETER, 3> arrParameters{};
	arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrParameters[0].Descriptor.ShaderRegister = 5;
	for (std::uint32_t nRange = 0; nRange < arrRanges.size(); ++nRange)
	{
		arrParameters[nRange + 1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nRange + 1].DescriptorTable = { 1, &arrRanges[nRange] };
	}
	D3D12_ROOT_SIGNATURE_DESC stDescription{};
	stDescription.NumParameters = static_cast<UINT>(arrParameters.size());
	stDescription.pParameters = arrParameters.data();
	ComOwner<ID3DBlob> stBlob;
	ComOwner<ID3DBlob> stErrors;
	if (FAILED(D3D12SerializeRootSignature(&stDescription, D3D_ROOT_SIGNATURE_VERSION_1, stBlob.Put(), stErrors.Put())) ||
		FAILED(pDevice->CreateRootSignature(0, stBlob->GetBufferPointer(), stBlob->GetBufferSize(), IID_PPV_ARGS(out_stRoot.Put()))))
	{
		return false;
	}
	std::ifstream stFile(stDirectory / "ShadowPageFeedback.cs.cso", std::ios::binary | std::ios::ate);
	const std::streamoff nBytes = stFile.tellg();
	if (!stFile || nBytes <= 0 || nBytes > 16 * 1024 * 1024)
	{
		return false;
	}
	std::vector<char> arrBytes(static_cast<std::size_t>(nBytes));
	stFile.seekg(0);
	stFile.read(arrBytes.data(), nBytes);
	D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
	stPipeline.pRootSignature = out_stRoot.Get();
	stPipeline.CS = { arrBytes.data(), arrBytes.size() };
	return stFile && SUCCEEDED(pDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(out_stPipeline.Put())));
}

} // namespace

bool GpuShadowPages::IsOwner() const noexcept
{
	return nOwnerThread == GetCurrentThreadId();
}

bool GpuShadowPages::Initialize(ID3D12Device *pDevice, const VirtualShadowSettings &stInput,
								const std::filesystem::path &stShaderDirectory,
								const std::array<ShadowPageDescriptors, SHADOW_PAGE_FRAME_COUNT> &arrBlocks,
								Assets::Diagnostics &out_arrDiagnostics)
{
	if (bInitialized || pDevice == nullptr || !stInput.bEnabled || !ValidateVirtualShadowSettings(stInput, out_arrDiagnostics))
	{
		return Error(out_arrDiagnostics, "Initialize requires an unused owner and enabled valid settings.");
	}
	GpuShadowPages stCandidate;
	stCandidate.nOwnerThread = GetCurrentThreadId();
	stCandidate.stSettings = stInput;
	stCandidate.arrDescriptors = arrBlocks;
	pDevice->AddRef();
	*stCandidate.stDevice.Put() = pDevice;
	if (!stCandidate.stCache.Initialize(stInput, out_arrDiagnostics))
	{
		return false;
	}
	const std::uint64_t nLogical = stCandidate.stCache.LogicalPages();
	stCandidate.nTableBytes = nLogical * sizeof(ShadowPageTableEntry);
	stCandidate.nFeedbackBytes = (nLogical + 4) * sizeof(std::uint32_t);
	stCandidate.nPageConstantsOffset = CONSTANT_BYTES;
	stCandidate.nTableOffset = CONSTANT_BYTES + stInput.nUpdatesPerFrame * PAGE_CONSTANT_STRIDE;
	stCandidate.nZeroOffset = stCandidate.nTableOffset + stCandidate.nTableBytes;
	stCandidate.nUploadBytes = stCandidate.nZeroOffset + stCandidate.nFeedbackBytes;
	D3D12_RESOURCE_DESC stDepth{};
	stDepth.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
	stDepth.Width = stDepth.Height = SHADOW_PAGE_PHYSICAL_TEXELS;
	stDepth.DepthOrArraySize = static_cast<UINT16>(stInput.nPhysicalPages);
	stDepth.MipLevels = 1;
	stDepth.Format = DXGI_FORMAT_R32_TYPELESS;
	stDepth.SampleDesc.Count = 1;
	stDepth.Flags = D3D12_RESOURCE_FLAG_ALLOW_DEPTH_STENCIL;
	D3D12_CLEAR_VALUE stClear{};
	stClear.Format = DXGI_FORMAT_D32_FLOAT;
	stClear.DepthStencil.Depth = 0;
	if (!Allocate(pDevice, stDepth, D3D12_HEAP_TYPE_DEFAULT, &stClear, stInput.nMemoryBudget, stCandidate.nAllocatedBytes, stCandidate.stPool))
	{
		return Error(out_arrDiagnostics, "Physical page pool allocation exceeded its budget or failed.");
	}
	(void)stCandidate.stPool->SetName(L"VirtualShadowPhysicalPages");
	D3D12_DESCRIPTOR_HEAP_DESC stHeap{};
	stHeap.Type = D3D12_DESCRIPTOR_HEAP_TYPE_DSV;
	stHeap.NumDescriptors = stInput.nPhysicalPages;
	if (FAILED(pDevice->CreateDescriptorHeap(&stHeap, IID_PPV_ARGS(stCandidate.stDsvHeap.Put()))))
	{
		return Error(out_arrDiagnostics, "Page DSV heap allocation failed.");
	}
	for (std::uint32_t nPage = 0; nPage < stInput.nPhysicalPages; ++nPage)
	{
		D3D12_DEPTH_STENCIL_VIEW_DESC stView{};
		stView.Format = DXGI_FORMAT_D32_FLOAT;
		stView.ViewDimension = D3D12_DSV_DIMENSION_TEXTURE2DARRAY;
		stView.Texture2DArray.FirstArraySlice = nPage;
		stView.Texture2DArray.ArraySize = 1;
		pDevice->CreateDepthStencilView(stCandidate.stPool.Get(), &stView, stCandidate.Dsv(nPage));
	}
	for (std::uint32_t nFrame = 0; nFrame < SHADOW_PAGE_FRAME_COUNT; ++nFrame)
	{
		const ShadowPageDescriptors &stBlock = arrBlocks[nFrame];
		Frame &stFrame = stCandidate.arrFrames[nFrame];
		if (stBlock.stCpu.ptr == 0 || stBlock.stGpu.ptr == 0 || stBlock.nStride == 0 ||
			!Allocate(pDevice, Buffer(stCandidate.nTableBytes), D3D12_HEAP_TYPE_DEFAULT, nullptr, stInput.nMemoryBudget, stCandidate.nAllocatedBytes, stFrame.stTable) ||
			!Allocate(pDevice, Buffer(stCandidate.nFeedbackBytes, true), D3D12_HEAP_TYPE_DEFAULT, nullptr, stInput.nMemoryBudget, stCandidate.nAllocatedBytes, stFrame.stFeedback) ||
			!Allocate(pDevice, Buffer(stCandidate.nUploadBytes), D3D12_HEAP_TYPE_UPLOAD, nullptr, stInput.nMemoryBudget, stCandidate.nAllocatedBytes, stFrame.stUpload) ||
			!Allocate(pDevice, Buffer(stCandidate.nFeedbackBytes), D3D12_HEAP_TYPE_READBACK, nullptr, stInput.nMemoryBudget, stCandidate.nAllocatedBytes, stFrame.stReadback))
		{
			return Error(out_arrDiagnostics, "Frame descriptors or page staging allocations failed the shared budget.");
		}
		const std::wstring strSuffix = L"[" + std::to_wstring(nFrame) + L"]";
		(void)stFrame.stTable->SetName((L"VirtualShadowPageTable" + strSuffix).c_str());
		(void)stFrame.stFeedback->SetName((L"VirtualShadowFeedback" + strSuffix).c_str());
		(void)stFrame.stUpload->SetName((L"VirtualShadowUpload" + strSuffix).c_str());
		(void)stFrame.stReadback->SetName((L"VirtualShadowReadback" + strSuffix).c_str());
		D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
		stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
		stSrv.Format = DXGI_FORMAT_R32_FLOAT;
		stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2DARRAY;
		stSrv.Texture2DArray.MipLevels = 1;
		stSrv.Texture2DArray.ArraySize = stInput.nPhysicalPages;
		pDevice->CreateShaderResourceView(stCandidate.stPool.Get(), &stSrv, Cpu(stBlock, 0));
		stSrv = {};
		stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
		stSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
		stSrv.Buffer.NumElements = static_cast<UINT>(nLogical);
		stSrv.Buffer.StructureByteStride = sizeof(ShadowPageTableEntry);
		pDevice->CreateShaderResourceView(stFrame.stTable.Get(), &stSrv, Cpu(stBlock, 1));
		pDevice->CreateShaderResourceView(stFrame.stTable.Get(), &stSrv, Cpu(stBlock, 4));
		D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
		stUav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
		stUav.Buffer.NumElements = static_cast<UINT>(nLogical + 4);
		stUav.Buffer.StructureByteStride = sizeof(std::uint32_t);
		pDevice->CreateUnorderedAccessView(stFrame.stFeedback.Get(), nullptr, &stUav, Cpu(stBlock, 2));
	}
	if (!Pipeline(pDevice, stShaderDirectory, stCandidate.stRoot, stCandidate.stPipeline))
	{
		return Error(out_arrDiagnostics, "Feedback root signature or shader pipeline failed.");
	}
	stCandidate.bInitialized = true;
	*this = std::move(stCandidate);
	return true;
}

bool GpuShadowPages::Collect(std::uint64_t nCompletedFence, std::vector<ShadowPageFeedback> &out_arrFeedback, Assets::Diagnostics &out_arrDiagnostics)
{
	for (Frame &stFrame : arrFrames)
	{
		if (!stFrame.bReadbackPending || stFrame.nFence > nCompletedFence)
		{
			continue;
		}
		const D3D12_RANGE stRead{ 0, static_cast<SIZE_T>(nFeedbackBytes) };
		void *pData = nullptr;
		if (FAILED(stFrame.stReadback->Map(0, &stRead, &pData)))
		{
			return Error(out_arrDiagnostics, "Feedback readback mapping failed.");
		}
		ShadowPageFeedback stFeedback;
		stFeedback.stProjection = stFrame.stProjection;
		stFeedback.arrCoverage.resize(stCache.LogicalPages());
		std::memcpy(arrFeedbackStatistics.data(), pData, sizeof(arrFeedbackStatistics));
		std::memcpy(stFeedback.arrCoverage.data(), static_cast<const std::uint8_t *>(pData) + sizeof(arrFeedbackStatistics),
					stFeedback.arrCoverage.size() * sizeof(std::uint32_t));
		const D3D12_RANGE stNoWrite{ 0, 0 };
		stFrame.stReadback->Unmap(0, &stNoWrite);
		stFrame.bReadbackPending = false;
		out_arrFeedback.push_back(std::move(stFeedback));
	}
	return true;
}

bool GpuShadowPages::Prepare(std::uint32_t nFrame, std::uint64_t nCompletedFence, const ShadowData &stProjection,
							 const std::vector<WorldBounds> &arrCasters, const std::vector<std::uint32_t> &arrChangedDraws,
							 const ShadowPageConstants &stConstants, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame >= SHADOW_PAGE_FRAME_COUNT || nPendingFrame != SHADOW_PAGE_FRAME_COUNT ||
		arrFrames[nFrame].nFence > nCompletedFence || !std::isfinite(stConstants.arrViewport[0]) || !std::isfinite(stConstants.arrViewport[1]) ||
		stConstants.arrViewport[0] < 1 || stConstants.arrViewport[0] > 16384 || stConstants.arrViewport[1] < 1 || stConstants.arrViewport[1] > 16384)
	{
		return Error(out_arrDiagnostics, "Prepare requires a retired owner slot and bounded viewport.");
	}
	std::vector<ShadowPageFeedback> arrFeedback;
	if (!Collect(nCompletedFence, arrFeedback, out_arrDiagnostics) || !stCache.Prepare(stProjection, arrCasters, arrChangedDraws, arrFeedback, out_arrDiagnostics))
	{
		return false;
	}
	Frame &stFrame = arrFrames[nFrame];
	void *pData = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stFrame.stUpload->Map(0, &stNoRead, &pData)))
	{
		stCache.Cancel();
		return Error(out_arrDiagnostics, "Page upload mapping failed.");
	}
	std::uint8_t *pBytes = static_cast<std::uint8_t *>(pData);
	std::memset(pBytes, 0, static_cast<std::size_t>(nUploadBytes));
	ShadowPageConstants stUploadConstants = stConstants;
	stUploadConstants.arrDimensions = { stSettings.nResolution, stSettings.nResolution / SHADOW_PAGE_TEXELS,
										SHADOW_PAGE_PHYSICAL_TEXELS, SHADOW_PAGE_BORDER };
	stUploadConstants.arrViewport[3] = 1;
	std::memcpy(pBytes, &stUploadConstants, sizeof(stUploadConstants));
	const ShadowPagePlan &stPlan = stCache.Plan();
	std::memcpy(pBytes + nTableOffset, stPlan.arrTable.data(), static_cast<std::size_t>(nTableBytes));
	for (std::size_t nUpdate = 0; nUpdate < stPlan.arrRender.size(); ++nUpdate)
	{
		std::memcpy(pBytes + nPageConstantsOffset + nUpdate * PAGE_CONSTANT_STRIDE, stPlan.arrRender[nUpdate].arrViewProjection.data(), 16 * sizeof(float));
	}
	stFrame.stUpload->Unmap(0, nullptr);
	stFrame.stProjection = stProjection;
	nWidth = static_cast<std::uint32_t>(stConstants.arrViewport[0]);
	nHeight = static_cast<std::uint32_t>(stConstants.arrViewport[1]);
	nPreparedFence = nCompletedFence;
	nPendingFrame = nFrame;
	nRecordedStage = 0;
	return true;
}

bool GpuShadowPages::RecordUpload(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame != nPendingFrame || nRecordedStage != 0 || pList == nullptr)
	{
		return Error(out_arrDiagnostics, "Upload requires the first record of the prepared owner frame.");
	}
	pList->CopyBufferRegion(Table(nFrame), 0, Upload(nFrame), nTableOffset, nTableBytes);
	pList->CopyBufferRegion(Feedback(nFrame), 0, Upload(nFrame), nZeroOffset, nFeedbackBytes);
	nRecordedStage = 1;
	return true;
}

bool GpuShadowPages::RecordFeedback(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, ID3D12Resource *pDepth, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame != nPendingFrame || nRecordedStage != 1 || pList == nullptr || pDepth == nullptr)
	{
		return Error(out_arrDiagnostics, "Feedback requires the uploaded owner frame and its depth resource.");
	}
	D3D12_SHADER_RESOURCE_VIEW_DESC stView{};
	stView.Format = DXGI_FORMAT_R32_FLOAT;
	stView.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
	stView.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stView.Texture2D.MipLevels = 1;
	stDevice->CreateShaderResourceView(pDepth, &stView, Cpu(arrDescriptors[nFrame], 3));
	pList->SetComputeRootSignature(stRoot.Get());
	pList->SetPipelineState(stPipeline.Get());
	pList->SetComputeRootConstantBufferView(0, Constants(nFrame));
	pList->SetComputeRootDescriptorTable(1, Gpu(arrDescriptors[nFrame], 3));
	pList->SetComputeRootDescriptorTable(2, Gpu(arrDescriptors[nFrame], 2));
	pList->Dispatch((nWidth + 7) / 8, (nHeight + 7) / 8, 1);
	nRecordedStage = 2;
	return true;
}

bool GpuShadowPages::RecordReadback(std::uint32_t nFrame, ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame != nPendingFrame || nRecordedStage != 2 || pList == nullptr)
	{
		return Error(out_arrDiagnostics, "Readback requires completed feedback recording once.");
	}
	pList->CopyBufferRegion(Readback(nFrame), 0, Feedback(nFrame), 0, nFeedbackBytes);
	nRecordedStage = 3;
	return true;
}

bool GpuShadowPages::Submit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nPendingFrame != nFrame || nRecordedStage != 3 || nFence <= nPreparedFence || !stCache.Commit())
	{
		return Error(out_arrDiagnostics, "Submit requires a prepared complete frame and a new fence.");
	}
	arrFrames[nFrame].nFence = nFence;
	arrFrames[nFrame].bReadbackPending = true;
	nPendingFrame = SHADOW_PAGE_FRAME_COUNT;
	return true;
}

void GpuShadowPages::Cancel() noexcept
{
	stCache.Cancel();
	nPendingFrame = SHADOW_PAGE_FRAME_COUNT;
}

bool GpuShadowPages::Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized)
	{
		return true;
	}
	if (!IsOwner() || nPendingFrame != SHADOW_PAGE_FRAME_COUNT)
	{
		return Error(out_arrDiagnostics, "Release requires the owner thread and no prepared frame.");
	}
	for (const Frame &stFrame : arrFrames)
	{
		if (stFrame.nFence > nCompletedFence)
		{
			return Error(out_arrDiagnostics, "Release cannot discard an in-flight page pool.");
		}
	}
	*this = GpuShadowPages{};
	return true;
}

const ShadowPagePlan &GpuShadowPages::Plan() const noexcept
{
	return stCache.Plan();
}
ID3D12Resource *GpuShadowPages::Pool() const noexcept
{
	return stPool.Get();
}
ID3D12Resource *GpuShadowPages::Table(std::uint32_t nFrame) const noexcept
{
	return arrFrames[nFrame].stTable.Get();
}
ID3D12Resource *GpuShadowPages::Feedback(std::uint32_t nFrame) const noexcept
{
	return arrFrames[nFrame].stFeedback.Get();
}
ID3D12Resource *GpuShadowPages::Upload(std::uint32_t nFrame) const noexcept
{
	return arrFrames[nFrame].stUpload.Get();
}
ID3D12Resource *GpuShadowPages::Readback(std::uint32_t nFrame) const noexcept
{
	return arrFrames[nFrame].stReadback.Get();
}
std::uint64_t GpuShadowPages::AllocatedBytes() const noexcept
{
	return nAllocatedBytes;
}
std::array<std::uint32_t, 4> GpuShadowPages::FeedbackStatistics() const noexcept
{
	return arrFeedbackStatistics;
}
D3D12_GPU_DESCRIPTOR_HANDLE GpuShadowPages::Receiver(std::uint32_t nFrame) const noexcept
{
	return Gpu(arrDescriptors[nFrame], 0);
}
D3D12_GPU_VIRTUAL_ADDRESS GpuShadowPages::Constants(std::uint32_t nFrame) const noexcept
{
	return Upload(nFrame)->GetGPUVirtualAddress();
}
D3D12_GPU_VIRTUAL_ADDRESS GpuShadowPages::PageConstants(std::uint32_t nFrame, std::uint32_t nUpdate) const noexcept
{
	return Constants(nFrame) + nPageConstantsOffset + nUpdate * PAGE_CONSTANT_STRIDE;
}
D3D12_CPU_DESCRIPTOR_HANDLE GpuShadowPages::Dsv(std::uint32_t nPage) const noexcept
{
	D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stDsvHeap->GetCPUDescriptorHandleForHeapStart();
	stHandle.ptr += static_cast<SIZE_T>(nPage) * stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_DSV);
	return stHandle;
}

} // namespace EngineNext::Rendering
