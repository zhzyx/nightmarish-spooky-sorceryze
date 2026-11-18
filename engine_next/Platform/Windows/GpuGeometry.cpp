/**************************************************************************/
/*  GpuGeometry.cpp                                                       */
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

#include "engine_next/Platform/Windows/GpuGeometry.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::uint64_t INSTANCE_OFFSET = 560;
constexpr std::uint32_t COUNTER_HEADER = 4;
constexpr std::uint32_t MAX_GROUPS = 65535;
constexpr std::uint32_t HIZ_VIEW_START = 9;

bool Error(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage, const char *pCode = "gpu_geometry")
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, "$.geometry_culling", pMessage);
	return false;
}
D3D12_CPU_DESCRIPTOR_HANDLE Cpu(const GeometryDescriptorBlock &stBlock, std::uint32_t nIndex)
{
	return { stBlock.stCpu.ptr + static_cast<SIZE_T>(nIndex) * stBlock.nStride };
}
D3D12_GPU_DESCRIPTOR_HANDLE Gpu(const GeometryDescriptorBlock &stBlock, std::uint32_t nIndex)
{
	return { stBlock.stGpu.ptr + static_cast<UINT64>(nIndex) * stBlock.nStride };
}
bool Allocate(ID3D12Device *pDevice, const D3D12_RESOURCE_DESC &stDescription, D3D12_HEAP_TYPE eHeap,
			  std::uint64_t nBudget, std::uint64_t &out_nBytes, ComOwner<ID3D12Resource> &out_stResource)
{
	const D3D12_RESOURCE_ALLOCATION_INFO stSize = pDevice->GetResourceAllocationInfo(0, 1, &stDescription);
	if (stSize.SizeInBytes == UINT64_MAX || out_nBytes > nBudget || stSize.SizeInBytes > nBudget - out_nBytes)
	{
		return false;
	}
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eHeap;
	stHeap.CreationNodeMask = 1;
	stHeap.VisibleNodeMask = 1;
	const D3D12_RESOURCE_STATES eState = eHeap == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ : (eHeap == D3D12_HEAP_TYPE_READBACK ? D3D12_RESOURCE_STATE_COPY_DEST : D3D12_RESOURCE_STATE_COMMON);
	if (FAILED(pDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, eState, nullptr, IID_PPV_ARGS(out_stResource.Put()))))
	{
		return false;
	}
	out_nBytes += stSize.SizeInBytes;
	return true;
}
bool Buffer(ID3D12Device *pDevice, std::uint64_t nSize, D3D12_HEAP_TYPE eHeap, D3D12_RESOURCE_FLAGS eFlags,
			std::uint64_t nBudget, std::uint64_t &out_nBytes, ComOwner<ID3D12Resource> &out_stResource)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = std::max<std::uint64_t>(nSize, 16);
	stDescription.Height = 1;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	stDescription.Flags = eFlags;
	return Allocate(pDevice, stDescription, eHeap, nBudget, out_nBytes, out_stResource);
}
bool Fill(ID3D12Resource *pBuffer, const void *pData, std::size_t nSize)
{
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(pBuffer->Map(0, &stNoRead, &pMapped)))
	{
		return false;
	}
	std::memset(pMapped, 0, static_cast<std::size_t>(pBuffer->GetDesc().Width));
	if (nSize != 0)
	{
		std::memcpy(pMapped, pData, nSize);
	}
	pBuffer->Unmap(0, nullptr);
	return true;
}
void StructuredSrv(ID3D12Device *pDevice, ID3D12Resource *pResource, std::uint32_t nCount, std::uint32_t nStride,
				   D3D12_CPU_DESCRIPTOR_HANDLE stHandle, std::uint64_t nFirst = 0)
{
	D3D12_SHADER_RESOURCE_VIEW_DESC stView{};
	stView.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
	stView.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stView.Buffer.FirstElement = nFirst;
	stView.Buffer.NumElements = nCount;
	stView.Buffer.StructureByteStride = nStride;
	pDevice->CreateShaderResourceView(pResource, &stView, stHandle);
}
void CounterUav(ID3D12Device *pDevice, ID3D12Resource *pResource, std::uint32_t nCount, D3D12_CPU_DESCRIPTOR_HANDLE stHandle)
{
	D3D12_UNORDERED_ACCESS_VIEW_DESC stView{};
	stView.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
	stView.Format = DXGI_FORMAT_R32_UINT;
	stView.Buffer.NumElements = nCount;
	pDevice->CreateUnorderedAccessView(pResource, nullptr, &stView, stHandle);
}
bool ReadShader(const std::filesystem::path &stFile, std::vector<std::uint8_t> &out_arrBytes)
{
	std::ifstream stStream(stFile, std::ios::binary | std::ios::ate);
	const std::streamoff nSize = stStream.tellg();
	if (!stStream || nSize <= 0 || static_cast<std::uint64_t>(nSize) > std::numeric_limits<std::size_t>::max())
	{
		return false;
	}
	out_arrBytes.resize(static_cast<std::size_t>(nSize));
	stStream.seekg(0);
	stStream.read(reinterpret_cast<char *>(out_arrBytes.data()), nSize);
	return static_cast<bool>(stStream);
}
bool Root(ID3D12Device *pDevice, const D3D12_ROOT_SIGNATURE_DESC &stDescription, ComOwner<ID3D12RootSignature> &out_stRoot)
{
	ComOwner<ID3DBlob> stBytes;
	ComOwner<ID3DBlob> stError;
	return SUCCEEDED(D3D12SerializeRootSignature(&stDescription, D3D_ROOT_SIGNATURE_VERSION_1, stBytes.Put(), stError.Put())) &&
			SUCCEEDED(pDevice->CreateRootSignature(0, stBytes->GetBufferPointer(), stBytes->GetBufferSize(), IID_PPV_ARGS(out_stRoot.Put())));
}
bool Pipelines(ID3D12Device *pDevice, const GeometryGpuConfig &stConfig, ComOwner<ID3D12RootSignature> &out_stCull,
			   ComOwner<ID3D12RootSignature> &out_stHiZ, ComOwner<ID3D12CommandSignature> &out_stCommands,
			   std::array<ComOwner<ID3D12PipelineState>, 3> &out_arrPipelines)
{
	std::array<D3D12_DESCRIPTOR_RANGE, 2> arrRanges{};
	arrRanges[0] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 4, 0, 0, 0 };
	arrRanges[1] = { D3D12_DESCRIPTOR_RANGE_TYPE_UAV, 2, 0, 0, 0 };
	std::array<D3D12_ROOT_PARAMETER, 4> arrParameters{};
	arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrParameters[0].Descriptor.ShaderRegister = 0;
	for (std::size_t nIndex = 0; nIndex < 2; ++nIndex)
	{
		arrParameters[nIndex + 1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nIndex + 1].DescriptorTable = { 1, &arrRanges[nIndex] };
	}
	D3D12_ROOT_SIGNATURE_DESC stDescription{};
	arrParameters[3].ParameterType = D3D12_ROOT_PARAMETER_TYPE_SRV;
	arrParameters[3].Descriptor.ShaderRegister = 4;
	stDescription.NumParameters = stConfig.bPaged ? 4 : 3;
	stDescription.pParameters = arrParameters.data();
	if (!Root(pDevice, stDescription, out_stCull))
	{
		return false;
	}
	arrRanges[0].NumDescriptors = 1;
	arrRanges[1].NumDescriptors = 1;
	stDescription.NumParameters = 2;
	stDescription.pParameters = &arrParameters[1];
	if (!Root(pDevice, stDescription, out_stHiZ))
	{
		return false;
	}
	std::array<D3D12_INDIRECT_ARGUMENT_DESC, 4> arrArguments{};
	arrArguments[0].Type = D3D12_INDIRECT_ARGUMENT_TYPE_CONSTANT_BUFFER_VIEW;
	arrArguments[0].ConstantBufferView.RootParameterIndex = 0;
	if (stConfig.bPaged)
	{
		arrArguments[1].Type = D3D12_INDIRECT_ARGUMENT_TYPE_VERTEX_BUFFER_VIEW;
		arrArguments[1].VertexBuffer.Slot = 0;
		arrArguments[2].Type = D3D12_INDIRECT_ARGUMENT_TYPE_INDEX_BUFFER_VIEW;
		arrArguments[3].Type = D3D12_INDIRECT_ARGUMENT_TYPE_DRAW_INDEXED;
	}
	else
	{
		arrArguments[1].Type = D3D12_INDIRECT_ARGUMENT_TYPE_DRAW_INDEXED;
	}
	D3D12_COMMAND_SIGNATURE_DESC stCommands{};
	stCommands.ByteStride = stConfig.bPaged ? sizeof(GeometryPagedIndirectCommand) : sizeof(GeometryIndirectCommand);
	stCommands.NumArgumentDescs = stConfig.bPaged ? 4 : 2;
	stCommands.pArgumentDescs = arrArguments.data();
	if (FAILED(pDevice->CreateCommandSignature(&stCommands, stConfig.pDrawRoot, IID_PPV_ARGS(out_stCommands.Put()))))
	{
		return false;
	}
	const std::array<const char *, 3> arrNames{ stConfig.bPaged ? "GeometryPagedCull.cs.cso" : "GeometryCull.cs.cso", "GeometryHiZCopy.cs.cso", "GeometryHiZReduce.cs.cso" };
	for (std::size_t nIndex = 0; nIndex < arrNames.size(); ++nIndex)
	{
		std::vector<std::uint8_t> arrBytes;
		if (!ReadShader(stConfig.stShaderDirectory / arrNames[nIndex], arrBytes))
		{
			return false;
		}
		D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
		stPipeline.pRootSignature = nIndex == 0 ? out_stCull.Get() : out_stHiZ.Get();
		stPipeline.CS = { arrBytes.data(), arrBytes.size() };
		if (FAILED(pDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(out_arrPipelines[nIndex].Put()))))
		{
			return false;
		}
	}
	return true;
}
} //namespace

bool GpuGeometry::IsOwner() const noexcept
{
	return nOwnerThread == 0 || nOwnerThread == GetCurrentThreadId();
}

bool GpuGeometry::Initialize(ID3D12Device *pDevice, const GeometryClusterSet &stSource,
							 const GeometryGpuConfig &stConfig, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nPendingFrame != GEOMETRY_FRAME_COUNT || pDevice == nullptr || stConfig.pDrawRoot == nullptr ||
		stConfig.nWidth == 0 || stConfig.nHeight == 0 || stConfig.nWidth > 16384 || stConfig.nHeight > 16384 ||
		stSource.nCandidateCount > UINT32_MAX || stSource.arrBuckets.size() > UINT32_MAX - COUNTER_HEADER ||
		stSource.bCapacityFallback || stSource.arrClusters.empty() || stSource.arrBuckets.empty() || stSource.nDrawCount == 0 || stSource.nCandidateCount != stSource.arrClusters.size())
	{
		return Error(out_arrDiagnostics, "Geometry initialization requires valid source data, viewport and draw root.");
	}
	for (const Frame &stFrame : arrFrames)
	{
		if (stFrame.nFence != 0)
		{
			return Error(out_arrDiagnostics, "Release retired geometry resources before initialization.");
		}
	}
	const UINT nStride = pDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
	for (std::size_t nFrame = 0; nFrame < GEOMETRY_FRAME_COUNT; ++nFrame)
	{
		if (stConfig.arrDepth[nFrame] == nullptr || stConfig.arrDescriptors[nFrame].stCpu.ptr == 0 || stConfig.arrDescriptors[nFrame].stGpu.ptr == 0 || stConfig.arrDescriptors[nFrame].nStride != nStride)
		{
			return Error(out_arrDiagnostics, "Geometry frame descriptors and depth resources are required.");
		}
	}
	GpuGeometry stCandidate;
	stCandidate.nOwnerThread = GetCurrentThreadId();
	stCandidate.nWidth = stConfig.nWidth;
	stCandidate.nHeight = stConfig.nHeight;
	stCandidate.nDrawCount = stSource.nDrawCount;
	stCandidate.bPaged = stConfig.bPaged;
	stCandidate.nCandidateCount = stConfig.bPaged ? stConfig.nMaximumCandidates : static_cast<std::uint32_t>(stSource.nCandidateCount);
	if (stCandidate.nCandidateCount < stSource.nCandidateCount || stCandidate.nCandidateCount == 0)
	{
		return Error(out_arrDiagnostics, "Paged geometry capacity cannot fit its complete fallback.");
	}
	stCandidate.nCommandStride = stConfig.bPaged ? sizeof(GeometryPagedIndirectCommand) : sizeof(GeometryIndirectCommand);
	stCandidate.nClusterUploadOffset = (INSTANCE_OFFSET + static_cast<std::uint64_t>(stCandidate.nDrawCount) * sizeof(GeometryGpuInstance) + 63) & ~std::uint64_t{ 63 };
	stCandidate.nBucketUploadOffset = stCandidate.nClusterUploadOffset + static_cast<std::uint64_t>(stCandidate.nCandidateCount) * sizeof(GeometryCluster);
	stCandidate.arrBuckets = stSource.arrBuckets;
	stCandidate.nCounterCount = COUNTER_HEADER + static_cast<std::uint32_t>(stSource.arrBuckets.size());
	stCandidate.arrDescriptors = stConfig.arrDescriptors;
	std::uint32_t nPaddedWidth = 1;
	std::uint32_t nPaddedHeight = 1;
	while (nPaddedWidth < stConfig.nWidth)
	{
		nPaddedWidth *= 2;
	}
	while (nPaddedHeight < stConfig.nHeight)
	{
		nPaddedHeight *= 2;
	}
	stCandidate.nMipCount = 1;
	for (std::uint32_t nSize = std::max(nPaddedWidth, nPaddedHeight); nSize > 1; nSize /= 2)
	{
		++stCandidate.nMipCount;
	}
	if (HIZ_VIEW_START + stCandidate.nMipCount * 2 > GEOMETRY_VIEW_COUNT || !Pipelines(pDevice, stConfig, stCandidate.stCullRoot, stCandidate.stHiZRoot, stCandidate.stCommands, stCandidate.arrPipelines))
	{
		return Error(out_arrDiagnostics, "Geometry pipelines or Hi-Z descriptor capacity failed.");
	}
	const std::uint64_t nClusterBytes = stSource.arrClusters.size() * sizeof(GeometryCluster);
	const std::uint64_t nBucketBytes = stSource.arrBuckets.size() * sizeof(GeometryBucket);
	if (!stConfig.bPaged)
	{
		if (!Buffer(pDevice, nClusterBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_NONE, stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stCandidate.stClusters) ||
			!Buffer(pDevice, nClusterBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stCandidate.stClusterUpload) ||
			!Buffer(pDevice, nBucketBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stCandidate.stBucketUpload) ||
			!Fill(stCandidate.stClusterUpload.Get(), stSource.arrClusters.data(), static_cast<std::size_t>(nClusterBytes)) ||
			!Fill(stCandidate.stBucketUpload.Get(), stSource.arrBuckets.data(), static_cast<std::size_t>(nBucketBytes)))
		{
			return Error(out_arrDiagnostics, "Geometry static allocation exceeded its memory budget.", "geometry_allocation");
		}
	}
	D3D12_DESCRIPTOR_HEAP_DESC stClearDescription{};
	stClearDescription.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
	stClearDescription.NumDescriptors = GEOMETRY_FRAME_COUNT * 2;
	if (FAILED(pDevice->CreateDescriptorHeap(&stClearDescription, IID_PPV_ARGS(stCandidate.stClearHeap.Put()))))
	{
		return Error(out_arrDiagnostics, "Could not allocate geometry CPU clear descriptors.", "geometry_allocation");
	}
	for (std::uint32_t nFrame = 0; nFrame < GEOMETRY_FRAME_COUNT; ++nFrame)
	{
		Frame &stFrame = stCandidate.arrFrames[nFrame];
		const GeometryDescriptorBlock &stBlock = stCandidate.arrDescriptors[nFrame];
		const std::uint64_t nUploadBytes = stConfig.bPaged ? stCandidate.nBucketUploadOffset + nBucketBytes : INSTANCE_OFFSET + static_cast<std::uint64_t>(stCandidate.nDrawCount) * sizeof(GeometryGpuInstance);
		if (!Buffer(pDevice, nUploadBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stFrame.stUpload) ||
			!Buffer(pDevice, static_cast<std::uint64_t>(stCandidate.nCounterCount) * 8, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_FLAG_NONE, stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stFrame.stReadback))
		{
			return Error(out_arrDiagnostics, "Geometry frame upload or readback allocation failed.", "geometry_allocation");
		}
		if (stConfig.bPaged && !Buffer(pDevice, static_cast<std::uint64_t>(stCandidate.nCandidateCount) * sizeof(GeometryCluster), D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_NONE, stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stFrame.stClusters))
		{
			return Error(out_arrDiagnostics, "Paged cluster frame allocation exceeds its memory budget.", "geometry_allocation");
		}
		for (std::uint32_t nPhase = 0; nPhase < 2; ++nPhase)
		{
			if (!Buffer(pDevice, static_cast<std::uint64_t>(stCandidate.nCandidateCount) * stCandidate.nCommandStride, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS,
						stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stFrame.arrArguments[nPhase]) ||
				!Buffer(pDevice, static_cast<std::uint64_t>(stCandidate.nCounterCount) * 4, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS,
						stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stFrame.arrCounters[nPhase]))
			{
				return Error(out_arrDiagnostics, "Geometry indirect allocation failed or exceeded its budget.", "geometry_allocation");
			}
			D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
			stUav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
			stUav.Buffer.NumElements = stCandidate.nCandidateCount;
			stUav.Buffer.StructureByteStride = stCandidate.nCommandStride;
			pDevice->CreateUnorderedAccessView(stFrame.arrArguments[nPhase].Get(), nullptr, &stUav, Cpu(stBlock, 4 + nPhase * 2));
			CounterUav(pDevice, stFrame.arrCounters[nPhase].Get(), stCandidate.nCounterCount, Cpu(stBlock, 5 + nPhase * 2));
			D3D12_CPU_DESCRIPTOR_HANDLE stClear = stCandidate.stClearHeap->GetCPUDescriptorHandleForHeapStart();
			stClear.ptr += static_cast<SIZE_T>(nFrame * 2 + nPhase) * nStride;
			CounterUav(pDevice, stFrame.arrCounters[nPhase].Get(), stCandidate.nCounterCount, stClear);
		}
		D3D12_RESOURCE_DESC stHiZ{};
		stHiZ.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
		stHiZ.Width = nPaddedWidth;
		stHiZ.Height = nPaddedHeight;
		stHiZ.DepthOrArraySize = 1;
		stHiZ.MipLevels = static_cast<UINT16>(stCandidate.nMipCount);
		stHiZ.Format = DXGI_FORMAT_R32_FLOAT;
		stHiZ.SampleDesc.Count = 1;
		stHiZ.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
		if (!Allocate(pDevice, stHiZ, D3D12_HEAP_TYPE_DEFAULT, stConfig.nMaxBytes, stCandidate.nAllocatedBytes, stFrame.stHiZ))
		{
			return Error(out_arrDiagnostics, "Hi-Z texture allocation failed or exceeded its budget.", "geometry_allocation");
		}
		StructuredSrv(pDevice, stConfig.bPaged ? stFrame.stClusters.Get() : stCandidate.stClusters.Get(), stCandidate.nCandidateCount, sizeof(GeometryCluster), Cpu(stBlock, 0));
		StructuredSrv(pDevice, stFrame.stUpload.Get(), stCandidate.nDrawCount, sizeof(GeometryGpuInstance), Cpu(stBlock, 1), INSTANCE_OFFSET / sizeof(GeometryGpuInstance));
		StructuredSrv(pDevice, stConfig.bPaged ? stFrame.stUpload.Get() : stCandidate.stBucketUpload.Get(),
					  static_cast<std::uint32_t>(stCandidate.arrBuckets.size()), sizeof(GeometryBucket), Cpu(stBlock, 3),
					  stConfig.bPaged ? stCandidate.nBucketUploadOffset / sizeof(GeometryBucket) : 0);
		D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
		stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
		stSrv.Format = DXGI_FORMAT_R32_FLOAT;
		stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
		stSrv.Texture2D.MipLevels = stCandidate.nMipCount;
		pDevice->CreateShaderResourceView(stFrame.stHiZ.Get(), &stSrv, Cpu(stBlock, 2));
		for (std::uint32_t nMip = 0; nMip < stCandidate.nMipCount; ++nMip)
		{
			stSrv.Texture2D.MipLevels = 1;
			stSrv.Texture2D.MostDetailedMip = nMip == 0 ? 0 : nMip - 1;
			pDevice->CreateShaderResourceView(nMip == 0 ? stConfig.arrDepth[nFrame] : stFrame.stHiZ.Get(), &stSrv, Cpu(stBlock, HIZ_VIEW_START + nMip * 2));
			D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
			stUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
			stUav.Format = DXGI_FORMAT_R32_FLOAT;
			stUav.Texture2D.MipSlice = nMip;
			pDevice->CreateUnorderedAccessView(stFrame.stHiZ.Get(), nullptr, &stUav, Cpu(stBlock, HIZ_VIEW_START + nMip * 2 + 1));
		}
	}
	Swap(stCandidate);
	return true;
}

bool GpuGeometry::PrepareFrame(std::uint32_t nFrame, const std::vector<std::array<float, 16>> &arrWorlds,
							   const std::array<float, 16> &arrViewProjection, std::uint64_t nDrawConstants, std::uint64_t nDrawStride,
							   bool bOcclusion, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics,
							   const GeometryClusterSet *pDynamic, std::uint64_t nPageViews, std::uint32_t nPageViewCount)
{
	if (!IsOwner() || nCandidateCount == 0 || nFrame >= GEOMETRY_FRAME_COUNT || nPendingFrame != GEOMETRY_FRAME_COUNT ||
		arrWorlds.size() != nDrawCount || nCompletedFence == UINT64_MAX || arrFrames[nFrame].nFence > nCompletedFence ||
		nDrawConstants == 0 || nDrawConstants % 256 != 0 || nDrawStride == 0 || nDrawStride % 256 != 0)
	{
		return Error(out_arrDiagnostics, "Prepare requires a retired frame and aligned draw constant addresses.");
	}
	if (nDrawCount > 1 && (nDrawStride > UINT64_MAX / (nDrawCount - 1) || nDrawConstants > UINT64_MAX - nDrawStride * (nDrawCount - 1)))
	{
		return Error(out_arrDiagnostics, "Draw constant address range overflows.");
	}
	if (bPaged && (pDynamic == nullptr || pDynamic->nDrawCount != nDrawCount || pDynamic->bCapacityFallback || pDynamic->arrClusters.empty() || pDynamic->arrClusters.size() != pDynamic->nCandidateCount || pDynamic->arrClusters.size() > nCandidateCount || pDynamic->arrBuckets.size() != arrBuckets.size() || nPageViews == 0 || nPageViewCount == 0))
	{
		return Error(out_arrDiagnostics, "Paged geometry requires a complete bounded active cut and page views.");
	}
	const std::uint32_t nActiveCount = bPaged ? static_cast<std::uint32_t>(pDynamic->arrClusters.size()) : nCandidateCount;
	if (bPaged)
	{
		for (std::size_t nBucket = 0; nBucket < arrBuckets.size(); ++nBucket)
		{
			const GeometryBucket &stBucket = pDynamic->arrBuckets[nBucket];
			if (stBucket.nMaterial != arrBuckets[nBucket].nMaterial || stBucket.nFlags != arrBuckets[nBucket].nFlags ||
				stBucket.nFirstCommand > nActiveCount || stBucket.nCommandCapacity > nActiveCount - stBucket.nFirstCommand)
			{
				return Error(out_arrDiagnostics, "Paged material buckets changed identity or exceed the active command range.");
			}
		}
	}
	std::vector<GeometryGpuInstance> arrInstances(nDrawCount);
	for (std::uint32_t nDraw = 0; nDraw < nDrawCount; ++nDraw)
	{
		for (float fValue : arrWorlds[nDraw])
		{
			if (!std::isfinite(fValue))
			{
				return Error(out_arrDiagnostics, "World matrices must be finite.");
			}
		}
		if (arrWorlds[nDraw][3] != 0 || arrWorlds[nDraw][7] != 0 || arrWorlds[nDraw][11] != 0 || arrWorlds[nDraw][15] != 1)
		{
			return Error(out_arrDiagnostics, "World matrices must be affine.");
		}
		arrInstances[nDraw].arrWorld = arrWorlds[nDraw];
		const std::uint64_t nAddress = nDrawConstants + nDraw * nDrawStride;
		arrInstances[nDraw].arrConstants = { static_cast<std::uint32_t>(nAddress), static_cast<std::uint32_t>(nAddress >> 32) };
	}
	GpuCullingConstants stConstants;
	stConstants.arrViewProjection = arrViewProjection;
	if (!BuildCullingFrustum(arrViewProjection, stConstants.arrPlanes, out_arrDiagnostics))
	{
		return false;
	}
	stConstants.arrViewport = { nWidth, nHeight, bPaged ? nPageViewCount : 0, 0 };
	stConstants.arrCounts = { nActiveCount, static_cast<std::uint32_t>(arrBuckets.size()), nMipCount, 0 };
	stConstants.arrParameters = { 0.00001F, 0, 0, 0 };
	Frame &stFrame = arrFrames[nFrame];
	if (!Collect(nFrame, nCompletedFence, out_arrDiagnostics))
	{
		return false;
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stFrame.stUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Error(out_arrDiagnostics, "Could not map retired geometry parameters.");
	}
	std::uint8_t *pBytes = static_cast<std::uint8_t *>(pMapped);
	std::memset(pBytes, 0, INSTANCE_OFFSET);
	std::memcpy(pBytes, &stConstants, sizeof(stConstants));
	stConstants.arrCounts[3] = bOcclusion ? 1U : 0U;
	std::memcpy(pBytes + 256, &stConstants, sizeof(stConstants));
	std::memcpy(pBytes + INSTANCE_OFFSET, arrInstances.data(), arrInstances.size() * sizeof(GeometryGpuInstance));
	if (bPaged)
	{
		std::memcpy(pBytes + nClusterUploadOffset, pDynamic->arrClusters.data(), pDynamic->arrClusters.size() * sizeof(GeometryCluster));
		std::memcpy(pBytes + nBucketUploadOffset, pDynamic->arrBuckets.data(), pDynamic->arrBuckets.size() * sizeof(GeometryBucket));
	}
	stFrame.stUpload->Unmap(0, nullptr);
	stFrame.nActiveCount = nActiveCount;
	stFrame.nPageViews = nPageViews;
	stFrame.arrBuckets = bPaged ? pDynamic->arrBuckets : arrBuckets;
	stFrame.bOcclusion = bOcclusion;
	stFrame.nWorkMask = 0;
	stFrame.nNextMip = 0;
	nPendingFrame = nFrame;
	return true;
}

bool GpuGeometry::Record(std::uint32_t nFrame, GeometryWork eWork, std::uint32_t nMip,
						 ID3D12GraphicsCommandList *pList, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nCandidateCount == 0 || nFrame >= GEOMETRY_FRAME_COUNT || nPendingFrame != nFrame || pList == nullptr || pList->GetType() != D3D12_COMMAND_LIST_TYPE_DIRECT)
	{
		return Error(out_arrDiagnostics, "Record requires the prepared frame and DIRECT list.");
	}
	const std::uint32_t nWork = static_cast<std::uint32_t>(eWork);
	if (nWork > static_cast<std::uint32_t>(GeometryWork::Readback))
	{
		return Error(out_arrDiagnostics, "Unknown geometry pass.");
	}
	Frame &stFrame = arrFrames[nFrame];
	const std::uint32_t nBit = 1U << nWork;
	if (eWork != GeometryWork::HiZ && (stFrame.nWorkMask & nBit) != 0)
	{
		return Error(out_arrDiagnostics, "Geometry pass was already recorded.");
	}
	const GeometryDescriptorBlock &stBlock = arrDescriptors[nFrame];
	if (eWork == GeometryWork::Upload)
	{
		if (bPaged)
		{
			pList->CopyBufferRegion(stFrame.stClusters.Get(), 0, stFrame.stUpload.Get(), nClusterUploadOffset,
									static_cast<std::uint64_t>(stFrame.nActiveCount) * sizeof(GeometryCluster));
		}
		else if (!bUploaded)
		{
			pList->CopyBufferRegion(stClusters.Get(), 0, stClusterUpload.Get(), 0, static_cast<std::uint64_t>(nCandidateCount) * sizeof(GeometryCluster));
		}
	}
	else if (eWork == GeometryWork::ClearDepth || eWork == GeometryWork::ClearColor)
	{
		const std::uint32_t nPhase = eWork == GeometryWork::ClearDepth ? 0 : 1;

		D3D12_CPU_DESCRIPTOR_HANDLE stCpu = stClearHeap->GetCPUDescriptorHandleForHeapStart();
		stCpu.ptr += static_cast<SIZE_T>(nFrame * 2 + nPhase) * stBlock.nStride;
		const UINT arrZero[4]{};
		pList->ClearUnorderedAccessViewUint(Gpu(stBlock, 5 + nPhase * 2), stCpu, stFrame.arrCounters[nPhase].Get(), arrZero, 0, nullptr);
	}
	else if (eWork == GeometryWork::CullDepth || eWork == GeometryWork::CullColor)
	{
		const std::uint32_t nPhase = eWork == GeometryWork::CullDepth ? 0 : 1;
		const GeometryWork eRequired = nPhase == 0 ? GeometryWork::ClearDepth : GeometryWork::ClearColor;
		if ((stFrame.nWorkMask & (1U << static_cast<std::uint32_t>(eRequired))) == 0 ||
			(stFrame.nWorkMask & (1U << static_cast<std::uint32_t>(GeometryWork::Upload))) == 0 ||
			(nPhase == 1 && stFrame.bOcclusion && stFrame.nNextMip != nMipCount))
		{
			return Error(out_arrDiagnostics, "Cull producers are incomplete.");
		}
		pList->SetComputeRootSignature(stCullRoot.Get());
		pList->SetPipelineState(arrPipelines[0].Get());
		pList->SetComputeRootConstantBufferView(0, stFrame.stUpload->GetGPUVirtualAddress() + nPhase * 256);
		pList->SetComputeRootDescriptorTable(1, Gpu(stBlock, 0));
		pList->SetComputeRootDescriptorTable(2, Gpu(stBlock, 4 + nPhase * 2));
		if (bPaged)
		{
			pList->SetComputeRootShaderResourceView(3, stFrame.nPageViews);
		}
		const std::uint32_t nGroups = (stFrame.nActiveCount + 63) / 64;
		pList->Dispatch(std::min(nGroups, MAX_GROUPS), (nGroups + MAX_GROUPS - 1) / MAX_GROUPS, 1);
	}
	else if (eWork == GeometryWork::HiZ)
	{
		if (!stFrame.bOcclusion || nMip != stFrame.nNextMip || nMip >= nMipCount ||
			(stFrame.nWorkMask & (1U << static_cast<std::uint32_t>(GeometryWork::CullDepth))) == 0)
		{
			return Error(out_arrDiagnostics, "Hi-Z levels must follow depth in order.");
		}
		pList->SetComputeRootSignature(stHiZRoot.Get());
		pList->SetPipelineState(arrPipelines[nMip == 0 ? 1 : 2].Get());
		pList->SetComputeRootDescriptorTable(0, Gpu(stBlock, HIZ_VIEW_START + nMip * 2));
		pList->SetComputeRootDescriptorTable(1, Gpu(stBlock, HIZ_VIEW_START + nMip * 2 + 1));
		const D3D12_RESOURCE_DESC stDescription = stFrame.stHiZ->GetDesc();
		const std::uint32_t nMipWidth = std::max(1U, static_cast<std::uint32_t>(stDescription.Width >> nMip));
		const std::uint32_t nMipHeight = std::max(1U, stDescription.Height >> nMip);
		pList->Dispatch((nMipWidth + 7) / 8, (nMipHeight + 7) / 8, 1);
		++stFrame.nNextMip;
	}
	else
	{
		if ((stFrame.nWorkMask & (1U << static_cast<std::uint32_t>(GeometryWork::CullColor))) == 0)
		{
			return Error(out_arrDiagnostics, "Color culling must precede readback.");
		}
		for (std::uint32_t nPhase = 0; nPhase < 2; ++nPhase)
		{
			pList->CopyBufferRegion(stFrame.stReadback.Get(), static_cast<std::uint64_t>(nPhase) * nCounterCount * 4,
									stFrame.arrCounters[nPhase].Get(), 0, static_cast<std::uint64_t>(nCounterCount) * 4);
		}
	}
	stFrame.nWorkMask |= nBit;
	return true;
}

void GpuGeometry::Execute(std::uint32_t nFrame, std::uint32_t nPhase, std::uint32_t nBucket, ID3D12GraphicsCommandList *pList) const
{
	const GeometryBucket &stBucket = arrFrames[nFrame].arrBuckets[nBucket];
	pList->ExecuteIndirect(stCommands.Get(), stBucket.nCommandCapacity, arrFrames[nFrame].arrArguments[nPhase].Get(),
						   static_cast<std::uint64_t>(stBucket.nFirstCommand) * nCommandStride, arrFrames[nFrame].arrCounters[nPhase].Get(),
						   static_cast<std::uint64_t>(COUNTER_HEADER + nBucket) * sizeof(std::uint32_t));
}

bool GpuGeometry::Commit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nFrame >= GEOMETRY_FRAME_COUNT || nPendingFrame != nFrame || nFence == 0 || nFence == UINT64_MAX ||
		(arrFrames[nFrame].nWorkMask & (1U << static_cast<std::uint32_t>(GeometryWork::Readback))) == 0)
	{
		return Error(out_arrDiagnostics, "Commit requires the fully recorded frame and successful signal.");
	}
	for (const Frame &stFrame : arrFrames)
	{
		if (nFence <= stFrame.nFence)
		{
			return Error(out_arrDiagnostics, "Geometry fences must increase.");
		}
	}
	arrFrames[nFrame].nFence = nFence;
	arrFrames[nFrame].bReadbackPending = true;
	bUploaded = true;
	nPendingFrame = GEOMETRY_FRAME_COUNT;
	return true;
}

bool GpuGeometry::Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nFrame >= GEOMETRY_FRAME_COUNT || nPendingFrame != nFrame)
	{
		return Error(out_arrDiagnostics, "Discard needs the current unsubmitted frame.");
	}
	nPendingFrame = GEOMETRY_FRAME_COUNT;
	return true;
}

bool GpuGeometry::Collect(std::uint32_t nFrame, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nFrame >= GEOMETRY_FRAME_COUNT || nCompletedFence == UINT64_MAX)
	{
		return Error(out_arrDiagnostics, "Invalid geometry collection context.");
	}
	Frame &stFrame = arrFrames[nFrame];
	if (!stFrame.bReadbackPending || stFrame.nFence > nCompletedFence)
	{
		return true;
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stRead{ 0, static_cast<SIZE_T>(nCounterCount) * 8 };
	if (FAILED(stFrame.stReadback->Map(0, &stRead, &pMapped)))
	{
		return Error(out_arrDiagnostics, "Could not map retired geometry counters.");
	}
	const std::uint32_t *pValues = static_cast<const std::uint32_t *>(pMapped);
	GeometryGpuStatistics stNext;
	stNext.nDepthCommands = pValues[0];
	stNext.nDepthTriangles = pValues[3];
	stNext.nVisibleCommands = pValues[nCounterCount];
	stNext.nVisibleTriangles = pValues[nCounterCount + 3];
	stNext.nOverflow = pValues[1] + pValues[nCounterCount + 1];
	stNext.nInvalid = pValues[2] + pValues[nCounterCount + 2];
	bool bValid = stNext.nDepthCommands <= stFrame.nActiveCount && stNext.nVisibleCommands <= stNext.nDepthCommands;
	for (std::uint32_t nPhase = 0; nPhase < 2; ++nPhase)
	{
		std::uint64_t nSum = 0;
		for (std::size_t nBucket = 0; nBucket < stFrame.arrBuckets.size(); ++nBucket)
		{
			const std::uint32_t nValue = pValues[nPhase * nCounterCount + COUNTER_HEADER + nBucket];
			bValid = bValid && nValue <= stFrame.arrBuckets[nBucket].nCommandCapacity;
			nSum += nValue;
		}
		bValid = bValid && nSum == pValues[nPhase * nCounterCount];
	}
	const D3D12_RANGE stNoWrite{ 0, 0 };
	stFrame.stReadback->Unmap(0, &stNoWrite);
	stFrame.bReadbackPending = false;
	if (stFrame.nFence >= nCollectedFence)
	{
		stStatistics = stNext;
		nCollectedFence = stFrame.nFence;
	}
	return (bValid && stNext.nOverflow == 0 && stNext.nInvalid == 0) || Error(out_arrDiagnostics, "Geometry GPU counts are invalid or overflowed.");
}

bool GpuGeometry::Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nPendingFrame != GEOMETRY_FRAME_COUNT || nCompletedFence == UINT64_MAX)
	{
		return Error(out_arrDiagnostics, "Geometry release requires the owner and no pending frame.");
	}
	for (const Frame &stFrame : arrFrames)
	{
		if (stFrame.nFence > nCompletedFence)
		{
			return Error(out_arrDiagnostics, "Geometry resources remain in flight.");
		}
	}
	GpuGeometry stEmpty;
	Swap(stEmpty);
	return true;
}

ID3D12Resource *GpuGeometry::Clusters() const noexcept
{
	return stClusters.Get();
}
ID3D12Resource *GpuGeometry::Clusters(std::uint32_t nFrame) const noexcept
{
	return bPaged && nFrame < GEOMETRY_FRAME_COUNT ? arrFrames[nFrame].stClusters.Get() : stClusters.Get();
}
ID3D12Resource *GpuGeometry::Arguments(std::uint32_t nFrame, std::uint32_t nPhase) const noexcept
{
	return nFrame < GEOMETRY_FRAME_COUNT && nPhase < 2 ? arrFrames[nFrame].arrArguments[nPhase].Get() : nullptr;
}
ID3D12Resource *GpuGeometry::Counters(std::uint32_t nFrame, std::uint32_t nPhase) const noexcept
{
	return nFrame < GEOMETRY_FRAME_COUNT && nPhase < 2 ? arrFrames[nFrame].arrCounters[nPhase].Get() : nullptr;
}
ID3D12Resource *GpuGeometry::HiZ(std::uint32_t nFrame) const noexcept
{
	return nFrame < GEOMETRY_FRAME_COUNT ? arrFrames[nFrame].stHiZ.Get() : nullptr;
}
ID3D12Resource *GpuGeometry::Readback(std::uint32_t nFrame) const noexcept
{
	return nFrame < GEOMETRY_FRAME_COUNT ? arrFrames[nFrame].stReadback.Get() : nullptr;
}
std::uint32_t GpuGeometry::MipCount() const noexcept
{
	return nMipCount;
}
std::uint64_t GpuGeometry::AllocatedBytes() const noexcept
{
	return nAllocatedBytes;
}
const GeometryGpuStatistics &GpuGeometry::Statistics() const noexcept
{
	return stStatistics;
}
const std::vector<GeometryBucket> &GpuGeometry::Buckets() const noexcept
{
	return arrBuckets;
}

const std::vector<GeometryBucket> &GpuGeometry::Buckets(std::uint32_t nFrame) const noexcept
{
	return nFrame < GEOMETRY_FRAME_COUNT ? arrFrames[nFrame].arrBuckets : arrBuckets;
}

void GpuGeometry::Swap(GpuGeometry &stOther) noexcept
{
	using std::swap;
	swap(nOwnerThread, stOther.nOwnerThread);
	swap(nPendingFrame, stOther.nPendingFrame);
	swap(bUploaded, stOther.bUploaded);
	swap(bPaged, stOther.bPaged);
	swap(nCommandStride, stOther.nCommandStride);
	swap(nClusterUploadOffset, stOther.nClusterUploadOffset);
	swap(nBucketUploadOffset, stOther.nBucketUploadOffset);
	swap(nMipCount, stOther.nMipCount);
	swap(nWidth, stOther.nWidth);
	swap(nHeight, stOther.nHeight);
	swap(nDrawCount, stOther.nDrawCount);
	swap(nCandidateCount, stOther.nCandidateCount);
	swap(nCounterCount, stOther.nCounterCount);
	swap(nAllocatedBytes, stOther.nAllocatedBytes);
	swap(nCollectedFence, stOther.nCollectedFence);
	swap(arrBuckets, stOther.arrBuckets);
	swap(arrFrames, stOther.arrFrames);
	swap(arrDescriptors, stOther.arrDescriptors);
	swap(stClusters, stOther.stClusters);
	swap(stClusterUpload, stOther.stClusterUpload);
	swap(stBucketUpload, stOther.stBucketUpload);
	swap(stCullRoot, stOther.stCullRoot);
	swap(stHiZRoot, stOther.stHiZRoot);
	swap(stCommands, stOther.stCommands);
	swap(stClearHeap, stOther.stClearHeap);
	swap(arrPipelines, stOther.arrPipelines);
	swap(stStatistics, stOther.stStatistics);
}
} // namespace EngineNext::Rendering
