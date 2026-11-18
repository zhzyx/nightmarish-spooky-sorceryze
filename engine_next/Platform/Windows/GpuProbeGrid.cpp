/**************************************************************************/
/*  GpuProbeGrid.cpp                                                      */
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

#include "engine_next/Platform/Windows/GpuProbeGrid.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <limits>
#include <map>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::uint32_t NEW_HISTORY_VIEW = 17;
constexpr std::uint32_t WRITE_VIEW = 20;
constexpr std::uint32_t CLEAR_VIEW = 25;
constexpr std::uint32_t MATERIAL_TEXTURE_LIMIT = 2045;
constexpr std::uint32_t GROUP_WIDTH = 64;
constexpr std::uint32_t MAX_DISPATCH_GROUPS = D3D12_CS_DISPATCH_MAX_THREAD_GROUPS_PER_DIMENSION;

bool Error(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "gpu_probe_grid", "$.global_illumination", pMessage);
	return false;
}

std::uint64_t Align(std::uint64_t nValue, std::uint64_t nAlignment)
{
	return (nValue + nAlignment - 1) & ~(nAlignment - 1);
}

D3D12_CPU_DESCRIPTOR_HANDLE CpuView(const GiDescriptorBlock &stBlock, std::uint32_t nIndex)
{
	return { stBlock.stCpu.ptr + static_cast<SIZE_T>(nIndex) * stBlock.nStride };
}

D3D12_GPU_DESCRIPTOR_HANDLE GpuView(const GiDescriptorBlock &stBlock, std::uint32_t nIndex)
{
	return { stBlock.stGpu.ptr + static_cast<UINT64>(nIndex) * stBlock.nStride };
}

bool CreateBuffer(ID3D12Device5 *pDevice, std::uint64_t nBytes, D3D12_HEAP_TYPE eHeap,
				  D3D12_RESOURCE_FLAGS eFlags, std::uint64_t nLimit, GpuProbeMemory &out_stMemory,
				  ComOwner<ID3D12Resource> &out_stResource)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = std::max<std::uint64_t>(nBytes, 16);
	stDescription.Height = 1;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	stDescription.Flags = eFlags;
	const D3D12_RESOURCE_ALLOCATION_INFO stAllocation = pDevice->GetResourceAllocationInfo(0, 1, &stDescription);
	if (stAllocation.SizeInBytes == UINT64_MAX || stAllocation.SizeInBytes == 0 ||
		out_stMemory.nTotalBytes > nLimit || stAllocation.SizeInBytes > nLimit - out_stMemory.nTotalBytes)
	{
		return false;
	}
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eHeap;
	stHeap.CreationNodeMask = 1;
	stHeap.VisibleNodeMask = 1;
	D3D12_RESOURCE_STATES eState = D3D12_RESOURCE_STATE_COMMON;
	if (eHeap == D3D12_HEAP_TYPE_UPLOAD)
	{
		eState = D3D12_RESOURCE_STATE_GENERIC_READ;
	}
	else if (eHeap == D3D12_HEAP_TYPE_READBACK)
	{
		eState = D3D12_RESOURCE_STATE_COPY_DEST;
	}
	if (FAILED(pDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription,
												eState, nullptr, IID_PPV_ARGS(out_stResource.Put()))))
	{
		return false;
	}
	out_stMemory.nTotalBytes += stAllocation.SizeInBytes;
	if (eHeap == D3D12_HEAP_TYPE_UPLOAD)
	{
		out_stMemory.nUploadBytes += stAllocation.SizeInBytes;
	}
	else if (eHeap == D3D12_HEAP_TYPE_READBACK)
	{
		out_stMemory.nReadbackBytes += stAllocation.SizeInBytes;
	}
	else
	{
		out_stMemory.nDefaultBytes += stAllocation.SizeInBytes;
	}
	return true;
}

void CreateSrv(ID3D12Device5 *pDevice, ID3D12Resource *pBuffer, std::uint64_t nFirst,
			   std::uint32_t nCount, std::uint32_t nStride, D3D12_CPU_DESCRIPTOR_HANDLE stHandle)
{
	D3D12_SHADER_RESOURCE_VIEW_DESC stDescription{};
	stDescription.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
	stDescription.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stDescription.Buffer.FirstElement = nFirst;
	stDescription.Buffer.NumElements = std::max(nCount, 1U);
	stDescription.Buffer.StructureByteStride = nStride;
	pDevice->CreateShaderResourceView(pBuffer, &stDescription, stHandle);
}

void CreateUav(ID3D12Device5 *pDevice, ID3D12Resource *pBuffer, std::uint32_t nCount,
			   std::uint32_t nStride, D3D12_CPU_DESCRIPTOR_HANDLE stHandle)
{
	D3D12_UNORDERED_ACCESS_VIEW_DESC stDescription{};
	stDescription.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
	stDescription.Buffer.NumElements = std::max(nCount, 1U);
	stDescription.Buffer.StructureByteStride = nStride;
	pDevice->CreateUnorderedAccessView(pBuffer, nullptr, &stDescription, stHandle);
}

void CreateClearUav(ID3D12Device5 *pDevice, ID3D12Resource *pBuffer, D3D12_CPU_DESCRIPTOR_HANDLE stHandle)
{
	D3D12_UNORDERED_ACCESS_VIEW_DESC stDescription{};
	stDescription.Format = DXGI_FORMAT_R32_UINT;
	stDescription.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
	stDescription.Buffer.NumElements = static_cast<UINT>(pBuffer->GetDesc().Width / sizeof(std::uint32_t));
	pDevice->CreateUnorderedAccessView(pBuffer, nullptr, &stDescription, stHandle);
}

bool Fill(ID3D12Resource *pBuffer, const void *pData, std::size_t nBytes)
{
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(pBuffer->Map(0, &stNoRead, &pMapped)))
	{
		return false;
	}
	std::memset(pMapped, 0, static_cast<std::size_t>(pBuffer->GetDesc().Width));
	if (nBytes > 0)
	{
		std::memcpy(pMapped, pData, nBytes);
	}
	pBuffer->Unmap(0, nullptr);
	return true;
}

bool ReadShader(const std::filesystem::path &stPath, std::vector<std::uint8_t> &out_arrBytes)
{
	std::ifstream stStream(stPath, std::ios::binary | std::ios::ate);
	const std::streamoff nBytes = stStream.tellg();
	if (!stStream || nBytes <= 0 || static_cast<std::uint64_t>(nBytes) > std::numeric_limits<std::size_t>::max())
	{
		return false;
	}
	out_arrBytes.resize(static_cast<std::size_t>(nBytes));
	stStream.seekg(0);
	stStream.read(reinterpret_cast<char *>(out_arrBytes.data()), nBytes);
	return static_cast<bool>(stStream);
}

bool CreatePipelines(ID3D12Device5 *pDevice, const std::filesystem::path &stDirectory,
					 ComOwner<ID3D12RootSignature> &out_stRoot,
					 std::array<ComOwner<ID3D12PipelineState>, 3> &out_arrPipelines)
{
	std::array<D3D12_DESCRIPTOR_RANGE, 11> arrDescriptorRanges{};
	arrDescriptorRanges[0] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 7, 0, 0, 0 };
	arrDescriptorRanges[1] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 11, 0, 11 };
	arrDescriptorRanges[2] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 3, 14, 0, 14 };
	arrDescriptorRanges[3] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 3, 7, 0, 0 };
	arrDescriptorRanges[4] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 10, 0, 0 };
	arrDescriptorRanges[5] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 12, 0, 0 };
	arrDescriptorRanges[6] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 13, 0, 0 };
	arrDescriptorRanges[7] = { D3D12_DESCRIPTOR_RANGE_TYPE_UAV, 5, 0, 0, 0 };
	arrDescriptorRanges[8] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, MATERIAL_TEXTURE_LIMIT, 0, 1, 0 };
	arrDescriptorRanges[9] = { D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER, MATERIAL_TEXTURE_LIMIT, 0, 1, 0 };
	arrDescriptorRanges[10] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 17, 0, 0 };
	std::array<D3D12_ROOT_PARAMETER, 11> arrParameters{};
	arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrParameters[0].Descriptor.ShaderRegister = 0;
	arrParameters[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrParameters[1].Descriptor.ShaderRegister = 1;
	arrParameters[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
	arrParameters[2].DescriptorTable = { 3, arrDescriptorRanges.data() };
	for (std::size_t nIndex = 3; nIndex < arrParameters.size(); ++nIndex)
	{
		arrParameters[nIndex].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nIndex].DescriptorTable = { 1, &arrDescriptorRanges[nIndex] };
	}
	D3D12_STATIC_SAMPLER_DESC stSampler{};
	stSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
	stSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
	stSampler.MaxAnisotropy = 1;
	stSampler.MaxLOD = D3D12_FLOAT32_MAX;
	D3D12_ROOT_SIGNATURE_DESC stDescription{};
	stDescription.NumParameters = static_cast<UINT>(arrParameters.size());
	stDescription.pParameters = arrParameters.data();
	stDescription.NumStaticSamplers = 1;
	stDescription.pStaticSamplers = &stSampler;
	ComOwner<ID3DBlob> stBlob;
	ComOwner<ID3DBlob> stError;
	if (FAILED(D3D12SerializeRootSignature(&stDescription, D3D_ROOT_SIGNATURE_VERSION_1, stBlob.Put(), stError.Put())) ||
		FAILED(pDevice->CreateRootSignature(0, stBlob->GetBufferPointer(), stBlob->GetBufferSize(), IID_PPV_ARGS(out_stRoot.Put()))))
	{
		return false;
	}
	const std::array<const char *, 3> arrNames{ "GiPrepare.cs.cso", "GiTrace.cs.cso", "GiIntegrate.cs.cso" };
	for (std::size_t nIndex = 0; nIndex < arrNames.size(); ++nIndex)
	{
		std::vector<std::uint8_t> arrBytes;
		if (!ReadShader(stDirectory / arrNames[nIndex], arrBytes))
		{
			return false;
		}
		D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
		stPipeline.pRootSignature = out_stRoot.Get();
		stPipeline.CS = { arrBytes.data(), arrBytes.size() };
		if (FAILED(pDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(out_arrPipelines[nIndex].Put()))))
		{
			return false;
		}
	}
	return true;
}
} // namespace

bool GpuProbeGrid::IsOwner() const noexcept
{
	return nOwnerThread == 0 || nOwnerThread == GetCurrentThreadId();
}

bool GpuProbeGrid::CanRelease(std::uint64_t nCompletedFence) const noexcept
{
	if (nCompletedFence == UINT64_MAX || nPendingFrame != GI_PENDING_FRAMES)
	{
		return false;
	}
	for (const Frame &stFrame : arrFrames)
	{
		if (stFrame.nFence > nCompletedFence)
		{
			return false;
		}
	}
	return true;
}

bool GpuProbeGrid::Initialize(ID3D12Device5 *pDevice, const GlobalIlluminationSettings &stInputSettings,
							  const RenderScene &stSource, const std::vector<std::array<float, 4>> &arrMaterialExtensions,
							  const std::filesystem::path &stShaderDirectory,
							  const std::array<GiDescriptorBlock, GI_PENDING_FRAMES> &arrInputDescriptors,
							  std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || !CanRelease(nCompletedFence) || pDevice == nullptr)
	{
		return Error(out_arrDiagnostics, "Initialization requires an owner-thread device and retired resources.");
	}
	const UINT nStride = pDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
	for (const GiDescriptorBlock &stBlock : arrInputDescriptors)
	{
		if (stBlock.stCpu.ptr == 0 || stBlock.stGpu.ptr == 0 || stBlock.nStride != nStride)
		{
			return Error(out_arrDiagnostics, "Each frame needs 32 shader-visible resource descriptors with the device stride.");
		}
	}
	GpuProbeGrid stCandidate;
	stCandidate.nOwnerThread = GetCurrentThreadId();
	stCandidate.stSettings = stInputSettings;
	stCandidate.arrDescriptors = arrInputDescriptors;
	if (!BuildProbeGrid(stInputSettings, stCandidate.stGrid, out_arrDiagnostics) ||
		!stCandidate.stScene.Prepare(pDevice, stSource, RayTracingLimits{}, nCompletedFence, out_arrDiagnostics))
	{
		return false;
	}
	const std::vector<RayTracingIdentity> &arrIdentities = stCandidate.stScene.Identities();
	if (arrIdentities.size() != stSource.arrInstances.size())
	{
		return Error(out_arrDiagnostics, "Ray-tracing identities must follow every render-scene instance.");
	}
	for (std::size_t nIndex = 0; nIndex < arrIdentities.size(); ++nIndex)
	{
		const RayTracingIdentity &stIdentity = arrIdentities[nIndex];
		const RenderInstance &stInstance = stSource.arrInstances[nIndex];
		if (stIdentity.nEntityId != stInstance.nEntityId || stIdentity.nAsset != stInstance.nAsset ||
			stIdentity.nPrimitive != stInstance.nPrimitive || stIdentity.nNode != stInstance.nNode)
		{
			return Error(out_arrDiagnostics, "Ray-tracing identity order differs from the render-scene draw order.");
		}
	}
	if (arrMaterialExtensions.size() != stCandidate.stScene.SourceMaterials().size() ||
		arrMaterialExtensions.size() > MATERIAL_TEXTURE_LIMIT / 5)
	{
		return Error(out_arrDiagnostics, "Material extension order must match the ray-tracing materials and texture-table capacity.");
	}
	for (const std::array<float, 4> &arrExtension : arrMaterialExtensions)
	{
		for (float fValue : arrExtension)
		{
			if (!std::isfinite(fValue))
			{
				return Error(out_arrDiagnostics, "Material extensions must contain finite binary32 values.");
			}
		}
	}
	stCandidate.nMaterialCount = static_cast<std::uint32_t>(arrMaterialExtensions.size());
	pDevice->AddRef();
	*stCandidate.stDevice.Put() = pDevice;
	if (!CreatePipelines(pDevice, stShaderDirectory, stCandidate.stRoot, stCandidate.arrPipelines))
	{
		return Error(out_arrDiagnostics, "Could not load the GI shader bundle or create compute pipelines.");
	}
	const GlobalIlluminationBudget &stBudget = stCandidate.stGrid.stBudget;
	const std::uint64_t nLimit = stInputSettings.nMaxGpuBytes;
	const std::array<std::uint64_t, 3> arrHistoryBytes{
		static_cast<std::uint64_t>(stBudget.nProbeCount) * GI_SH_STRIDE,
		static_cast<std::uint64_t>(stBudget.nProbeCount) * 64 * GI_MOMENTS_STRIDE,
		static_cast<std::uint64_t>(stBudget.nProbeCount) * GI_STATE_STRIDE
	};
	for (HistoryResources &stHistory : stCandidate.arrHistory)
	{
		for (std::size_t nIndex = 0; nIndex < stHistory.arrBuffers.size(); ++nIndex)
		{
			if (!CreateBuffer(pDevice, arrHistoryBytes[nIndex], D3D12_HEAP_TYPE_DEFAULT,
							  D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, nLimit, stCandidate.stMemory, stHistory.arrBuffers[nIndex]))
			{
				return Error(out_arrDiagnostics, "GI history allocation exceeds the resident budget or failed.");
			}
		}
	}
	stCandidate.nPositionOffset = D3D12_CONSTANT_BUFFER_DATA_PLACEMENT_ALIGNMENT;
	stCandidate.nRemapOffset = Align(stCandidate.nPositionOffset + stBudget.nPositionBytes, 16);
	stCandidate.nUpdateOffset = Align(stCandidate.nRemapOffset + static_cast<std::uint64_t>(stBudget.nProbeCount) * 4, 16);
	const std::uint64_t nUploadBytes = Align(stCandidate.nUpdateOffset + static_cast<std::uint64_t>(stBudget.nUpdateCount) * 4, 256);
	if (!CreateBuffer(pDevice, stBudget.nPositionBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_NONE,
					  nLimit, stCandidate.stMemory, stCandidate.stPositions) ||
		!CreateBuffer(pDevice, arrMaterialExtensions.size() * sizeof(std::array<float, 4>),
					  D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, nLimit, stCandidate.stMemory, stCandidate.stMaterialExtensions) ||
		!Fill(stCandidate.stMaterialExtensions.Get(), arrMaterialExtensions.data(), arrMaterialExtensions.size() * sizeof(std::array<float, 4>)))
	{
		return Error(out_arrDiagnostics, "GI position or material-extension allocation failed or exceeded the budget.");
	}
	for (Frame &stFrame : stCandidate.arrFrames)
	{
		if (!CreateBuffer(pDevice, static_cast<std::uint64_t>(stBudget.nRayCount) * GI_RAY_RESULT_STRIDE,
						  D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, nLimit, stCandidate.stMemory, stFrame.stRays) ||
			!CreateBuffer(pDevice, static_cast<std::uint64_t>(stBudget.nRayCount) * GI_RAY_STATUS_STRIDE,
						  D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, nLimit, stCandidate.stMemory, stFrame.stRayStatus) ||
			!CreateBuffer(pDevice, nUploadBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE,
						  nLimit, stCandidate.stMemory, stFrame.stUpload) ||
			!CreateBuffer(pDevice, arrHistoryBytes[2], D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_FLAG_NONE,
						  nLimit, stCandidate.stMemory, stFrame.stReadback))
		{
			return Error(out_arrDiagnostics, "GI frame allocation failed or exceeded the actual aligned budget.");
		}
	}
	stCandidate.arrNeedsUpdate.assign(stBudget.nProbeCount, 1);
	D3D12_DESCRIPTOR_HEAP_DESC stClearDescription{};
	stClearDescription.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
	stClearDescription.NumDescriptors = 6;
	if (FAILED(pDevice->CreateDescriptorHeap(&stClearDescription, IID_PPV_ARGS(stCandidate.stClearHeap.Put()))))
	{
		return Error(out_arrDiagnostics, "Could not create CPU-only GI clear descriptors.");
	}
	const D3D12_CPU_DESCRIPTOR_HANDLE stClearStart = stCandidate.stClearHeap->GetCPUDescriptorHandleForHeapStart();
	for (std::uint32_t nHistory = 0; nHistory < 2; ++nHistory)
	{
		for (std::uint32_t nKind = 0; nKind < 3; ++nKind)
		{
			D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stClearStart;
			stHandle.ptr += static_cast<SIZE_T>(nHistory * 3 + nKind) * nStride;
			CreateClearUav(pDevice, stCandidate.arrHistory[nHistory].arrBuffers[nKind].Get(), stHandle);
		}
	}
	stCandidate.stMemory.stRayTracing = stCandidate.stScene.Memory();
	stCandidate.bInitialized = true;
	for (std::uint32_t nFrame = 0; nFrame < GI_PENDING_FRAMES; ++nFrame)
	{
		stCandidate.WriteDescriptors(nFrame);
	}
	if (!Release(nCompletedFence, out_arrDiagnostics))
	{
		return false;
	}
	Swap(stCandidate);
	return true;
}

void GpuProbeGrid::WriteDescriptors(std::uint32_t nFrame)
{
	ID3D12Device5 *pDevice = stDevice.Get();
	const GiDescriptorBlock &stBlock = arrDescriptors[nFrame];
	const Frame &stFrame = arrFrames[nFrame];
	const std::uint32_t nCount = stGrid.stBudget.nProbeCount;
	const std::uint32_t nRays = stGrid.stBudget.nRayCount;
	D3D12_SHADER_RESOURCE_VIEW_DESC stSceneView{};
	stSceneView.ViewDimension = D3D12_SRV_DIMENSION_RAYTRACING_ACCELERATION_STRUCTURE;
	stSceneView.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSceneView.RaytracingAccelerationStructure.Location = stScene.TlasResource(nFrame)->GetGPUVirtualAddress();
	pDevice->CreateShaderResourceView(nullptr, &stSceneView, CpuView(stBlock, 0));
	CreateSrv(pDevice, stScene.VertexBuffer(), 0, static_cast<std::uint32_t>(stScene.VertexBuffer()->GetDesc().Width / sizeof(MeshVertex)), sizeof(MeshVertex), CpuView(stBlock, 1));
	CreateSrv(pDevice, stScene.IndexBuffer(), 0, static_cast<std::uint32_t>(stScene.IndexBuffer()->GetDesc().Width / sizeof(std::uint32_t)), sizeof(std::uint32_t), CpuView(stBlock, 2));
	CreateSrv(pDevice, stScene.DrawBuffer(), 0, static_cast<std::uint32_t>(stScene.Identities().size()), sizeof(RayTracingDraw), CpuView(stBlock, 3));
	CreateSrv(pDevice, stScene.MaterialBuffer(), 0, nMaterialCount, sizeof(RayTracingMaterial), CpuView(stBlock, 4));
	CreateSrv(pDevice, stPositions.Get(), 0, nCount, GI_POSITION_STRIDE, CpuView(stBlock, 5));
	CreateSrv(pDevice, stFrame.stUpload.Get(), nUpdateOffset / sizeof(std::uint32_t), stGrid.stBudget.nUpdateCount, sizeof(std::uint32_t), CpuView(stBlock, 6));
	const std::array<std::uint32_t, 3> arrCounts{ nCount * 9, nCount * 64, nCount };
	const std::array<std::uint32_t, 3> arrStrides{ 16, GI_MOMENTS_STRIDE, GI_STATE_STRIDE };
	for (std::uint32_t nIndex = 0; nIndex < 3; ++nIndex)
	{
		CreateSrv(pDevice, arrHistory[nReadHistory].arrBuffers[nIndex].Get(), 0, arrCounts[nIndex], arrStrides[nIndex], CpuView(stBlock, 7 + nIndex));
		CreateSrv(pDevice, arrHistory[1 - nReadHistory].arrBuffers[nIndex].Get(), 0, arrCounts[nIndex], arrStrides[nIndex], CpuView(stBlock, NEW_HISTORY_VIEW + nIndex));
		CreateUav(pDevice, arrHistory[1 - nReadHistory].arrBuffers[nIndex].Get(), arrCounts[nIndex], arrStrides[nIndex], CpuView(stBlock, WRITE_VIEW + 2 + nIndex));
		CreateClearUav(pDevice, arrHistory[nReadHistory].arrBuffers[nIndex].Get(), CpuView(stBlock, CLEAR_VIEW + nIndex));
	}
	CreateSrv(pDevice, stFrame.stUpload.Get(), nRemapOffset / sizeof(std::uint32_t), nCount, sizeof(std::uint32_t), CpuView(stBlock, 11));
	CreateSrv(pDevice, stFrame.stRays.Get(), 0, nRays, GI_RAY_RESULT_STRIDE, CpuView(stBlock, 14));
	CreateSrv(pDevice, stFrame.stRayStatus.Get(), 0, nRays, GI_RAY_STATUS_STRIDE, CpuView(stBlock, 15));
	CreateSrv(pDevice, stMaterialExtensions.Get(), 0, nMaterialCount, 16, CpuView(stBlock, 16));
	CreateUav(pDevice, stFrame.stRays.Get(), nRays, GI_RAY_RESULT_STRIDE, CpuView(stBlock, WRITE_VIEW));
	CreateUav(pDevice, stFrame.stRayStatus.Get(), nRays, GI_RAY_STATUS_STRIDE, CpuView(stBlock, WRITE_VIEW + 1));
}

bool GpuProbeGrid::PrepareFrame(std::uint32_t nFrame, const std::array<double, 3> &arrCenter,
								const std::vector<std::array<double, 16>> &arrWorlds, std::uint64_t nCompletedFence,
								Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || !bInitialized || nFrame >= GI_PENDING_FRAMES || nPendingFrame != GI_PENDING_FRAMES ||
		nCompletedFence == UINT64_MAX || arrFrames[nFrame].nFence > nCompletedFence || arrWorlds.size() != stScene.Identities().size())
	{
		return Error(out_arrDiagnostics, "Prepare needs a retired frame slot and one world matrix per scene identity.");
	}
	ProbeGrid stNext;
	if (!SnapProbeGrid(stSettings, arrCenter, stNext, out_arrDiagnostics))
	{
		return false;
	}
	const std::uint32_t nCount = stNext.stBudget.nProbeCount;
	const std::uint32_t nUpdates = stNext.stBudget.nUpdateCount;
	const bool bHistoryValid = bHasSubmitted && nCommittedInvalidation == nInvalidationSerial;
	std::vector<std::uint32_t> arrRemap(nCount, UINT32_MAX);
	std::vector<std::uint8_t> arrNextNeeds(nCount, 1);
	if (bHistoryValid)
	{
		std::map<std::array<float, 4>, std::uint32_t> mapOldPositions;
		for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
		{
			mapOldPositions.emplace(stGrid.arrPositions[nIndex], nIndex);
		}
		for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
		{
			const std::map<std::array<float, 4>, std::uint32_t>::const_iterator itOld = mapOldPositions.find(stNext.arrPositions[nIndex]);
			if (itOld != mapOldPositions.end())
			{
				arrRemap[nIndex] = itOld->second;
				arrNextNeeds[nIndex] = arrNeedsUpdate[itOld->second];
			}
		}
	}
	std::vector<std::uint32_t> arrUpdates;
	arrUpdates.reserve(nUpdates);
	std::vector<std::uint8_t> arrSelected(nCount, 0);
	for (std::uint32_t nIndex = 0; nIndex < nCount && arrUpdates.size() < nUpdates; ++nIndex)
	{
		if (arrNextNeeds[nIndex] != 0)
		{
			arrUpdates.push_back(nIndex);
			arrSelected[nIndex] = 1;
		}
	}
	std::vector<std::uint32_t> arrRolling;
	if (!BuildProbeUpdateIndices(stNext, nEpoch, arrRolling, out_arrDiagnostics))
	{
		return false;
	}
	for (std::uint32_t nIndex : arrRolling)
	{
		if (arrUpdates.size() == nUpdates)
		{
			break;
		}
		if (arrSelected[nIndex] == 0)
		{
			arrUpdates.push_back(nIndex);
			arrSelected[nIndex] = 1;
		}
	}
	GiGridParameters stParameters;
	for (std::uint32_t nLevel = 0; nLevel < stNext.nLevelCount; ++nLevel)
	{
		for (std::uint32_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stParameters.arrMinimum[nLevel][nAxis] = static_cast<float>(stNext.arrLevels[nLevel].arrMinimum[nAxis]);
			const float fInverse = 1.0F / static_cast<float>(stNext.arrLevels[nLevel].arrSpacing[nAxis]);
			if (!std::isnormal(fInverse) || fInverse <= 0)
			{
				return Error(out_arrDiagnostics, "Inverse probe spacing must remain positive normal binary32 on the GPU.");
			}
			stParameters.arrInverseSpacing[nLevel][nAxis] = fInverse;
		}
	}
	stParameters.arrGridInfo = { stNext.arrCounts[0], stNext.arrCounts[1], stNext.arrCounts[2], stNext.nLevelCount };
	stParameters.arrWorkInfo = { nCount, nUpdates, stSettings.nRaysPerProbe, static_cast<std::uint32_t>(nEpoch) };
	stParameters.arrSampling = { static_cast<float>(stSettings.dTraceDistance), static_cast<float>(stSettings.dHysteresis), static_cast<float>(stSettings.dNormalBias), static_cast<float>(stSettings.dViewBias) };
	stParameters.arrHistory = { static_cast<float>(stSettings.dBounceStrength), static_cast<float>(stSettings.dHistoryChangeThreshold), bHistoryValid ? 1.0F : 0.0F, static_cast<float>(GI_DISTANCE_RESOLUTION) };
	stParameters.arrCounts = { nMaterialCount * 5, nMaterialCount, MAX_DISPATCH_GROUPS * GROUP_WIDTH, 0 };
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(arrFrames[nFrame].stUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Error(out_arrDiagnostics, "Could not map the retired GI upload buffer.");
	}
	std::uint8_t *pBytes = static_cast<std::uint8_t *>(pMapped);
	std::memset(pBytes, 0, static_cast<std::size_t>(arrFrames[nFrame].stUpload->GetDesc().Width));
	std::memcpy(pBytes, &stParameters, sizeof(stParameters));
	std::memcpy(pBytes + nPositionOffset, stNext.arrPositions.data(), stNext.arrPositions.size() * sizeof(std::array<float, 4>));
	std::memcpy(pBytes + nRemapOffset, arrRemap.data(), arrRemap.size() * sizeof(std::uint32_t));
	std::memcpy(pBytes + nUpdateOffset, arrUpdates.data(), arrUpdates.size() * sizeof(std::uint32_t));
	arrFrames[nFrame].stUpload->Unmap(0, nullptr);
	for (std::uint32_t nIndex : arrUpdates)
	{
		arrNextNeeds[nIndex] = 0;
	}
	stPendingGrid = std::move(stNext);
	arrPendingNeedsUpdate = std::move(arrNextNeeds);
	arrPendingUpdates = std::move(arrUpdates);
	arrPendingWorlds = arrWorlds;
	nPendingFrame = nFrame;
	nPendingInvalidation = nInvalidationSerial;
	bPendingHistoryValid = bHistoryValid;
	nPreparedCompletedFence = nCompletedFence;
	nRecordedPasses = 0;
	WriteDescriptors(nFrame);
	return true;
}

bool GpuProbeGrid::Record(std::uint32_t nFrame, GiPass ePass, ID3D12GraphicsCommandList4 *pList,
						  const GiBindings &stBindings, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint32_t nPass = static_cast<std::uint32_t>(ePass);
	if (!IsOwner() || !bInitialized || nFrame >= GI_PENDING_FRAMES || nPendingFrame != nFrame ||
		pList == nullptr || pList->GetType() != D3D12_COMMAND_LIST_TYPE_DIRECT || nPass > static_cast<std::uint32_t>(GiPass::Readback))
	{
		return Error(out_arrDiagnostics, "Record needs the prepared frame and a DIRECT command list.");
	}
	const std::uint32_t nBit = 1U << nPass;
	if ((nRecordedPasses & ~(nBit - 1)) != 0)
	{
		return Error(out_arrDiagnostics, "GI passes must be recorded once in dependency order.");
	}
	std::uint32_t nRequired = nPass == 0 ? 0 : 1U << (nPass - 1);
	if (ePass == GiPass::Remap)
	{
		nRequired = 1U << static_cast<std::uint32_t>(GiPass::Upload);
		if (!bPendingHistoryValid)
		{
			nRequired |= 1U << static_cast<std::uint32_t>(GiPass::InitializeHistory);
		}
	}
	if ((nRecordedPasses & nRequired) != nRequired)
	{
		return Error(out_arrDiagnostics, "A required GI producer pass has not been recorded.");
	}
	if (ePass == GiPass::BuildScene)
	{
		if (!stScene.RecordBuildOrUpdate(nFrame, pList, arrPendingWorlds, nPreparedCompletedFence, out_arrDiagnostics))
		{
			return false;
		}
	}
	else if (ePass == GiPass::Upload)
	{
		pList->CopyBufferRegion(stPositions.Get(), 0, arrFrames[nFrame].stUpload.Get(), nPositionOffset, stPendingGrid.stBudget.nPositionBytes);
	}
	else if (ePass == GiPass::InitializeHistory)
	{
		if (!bPendingHistoryValid)
		{
			const std::array<UINT, 4> arrZero{};
			for (std::uint32_t nIndex = 0; nIndex < 3; ++nIndex)
			{
				D3D12_CPU_DESCRIPTOR_HANDLE stCpuClear = stClearHeap->GetCPUDescriptorHandleForHeapStart();
				stCpuClear.ptr += static_cast<SIZE_T>(nReadHistory * 3 + nIndex) * arrDescriptors[nFrame].nStride;
				pList->ClearUnorderedAccessViewUint(GpuView(arrDescriptors[nFrame], CLEAR_VIEW + nIndex),
													stCpuClear, arrHistory[nReadHistory].arrBuffers[nIndex].Get(), arrZero.data(), 0, nullptr);
			}
		}
	}
	else if (ePass == GiPass::Readback)
	{
		pList->CopyBufferRegion(arrFrames[nFrame].stReadback.Get(), 0, arrHistory[1 - nReadHistory].arrBuffers[2].Get(), 0,
								static_cast<std::uint64_t>(stPendingGrid.stBudget.nProbeCount) * GI_STATE_STRIDE);
	}
	else
	{
		if (stBindings.nFrameConstants == 0 || stBindings.stEnvironment.ptr == 0 ||
			stBindings.stDirectionalShadow.ptr == 0 || stBindings.stLocalShadow.ptr == 0 ||
			stBindings.stMaterials.ptr == 0 || stBindings.stSamplers.ptr == 0 || stBindings.stTint.ptr == 0)
		{
			return Error(out_arrDiagnostics, "GI compute descriptors and frame constants must be bound.");
		}
		const std::uint32_t nPipeline = ePass == GiPass::Remap ? 0 : (ePass == GiPass::Trace ? 1 : 2);
		const GiDescriptorBlock &stBlock = arrDescriptors[nFrame];
		pList->SetComputeRootSignature(stRoot.Get());
		pList->SetPipelineState(arrPipelines[nPipeline].Get());
		pList->SetComputeRootConstantBufferView(0, ConstantsGpu(nFrame));
		pList->SetComputeRootConstantBufferView(1, stBindings.nFrameConstants);
		pList->SetComputeRootDescriptorTable(2, GpuView(stBlock, 0));
		pList->SetComputeRootDescriptorTable(3, GpuView(stBlock, ePass == GiPass::Trace ? NEW_HISTORY_VIEW : 7));
		pList->SetComputeRootDescriptorTable(4, stBindings.stEnvironment);
		pList->SetComputeRootDescriptorTable(5, stBindings.stDirectionalShadow);
		pList->SetComputeRootDescriptorTable(6, stBindings.stLocalShadow);
		pList->SetComputeRootDescriptorTable(7, GpuView(stBlock, WRITE_VIEW));
		pList->SetComputeRootDescriptorTable(8, stBindings.stMaterials);
		pList->SetComputeRootDescriptorTable(9, stBindings.stSamplers);
		pList->SetComputeRootDescriptorTable(10, stBindings.stTint);
		std::uint32_t nThreads = stPendingGrid.stBudget.nUpdateCount;
		if (ePass == GiPass::Remap)
		{
			nThreads = stPendingGrid.stBudget.nProbeCount;
		}
		else if (ePass == GiPass::Trace)
		{
			nThreads = stPendingGrid.stBudget.nRayCount;
		}
		const std::uint32_t nGroups = (nThreads + GROUP_WIDTH - 1) / GROUP_WIDTH;
		pList->Dispatch(std::min(nGroups, MAX_DISPATCH_GROUPS), (nGroups + MAX_DISPATCH_GROUPS - 1) / MAX_DISPATCH_GROUPS, 1);
	}
	nRecordedPasses |= nBit;
	return true;
}

bool GpuProbeGrid::Submit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint32_t nUpdateBit = 1U << static_cast<std::uint32_t>(GiPass::Update);
	if (!IsOwner() || nFrame >= GI_PENDING_FRAMES || nPendingFrame != nFrame ||
		nFence == 0 || nFence == UINT64_MAX || (nRecordedPasses & nUpdateBit) == 0)
	{
		return Error(out_arrDiagnostics, "Submit needs a fully recorded prepared frame and a valid signal fence.");
	}
	for (const Frame &stFrame : arrFrames)
	{
		if (nFence <= stFrame.nFence)
		{
			return Error(out_arrDiagnostics, "Every GI submission requires a newer DIRECT queue fence.");
		}
	}
	if (!stScene.CommitSubmission(nFrame, nFence, out_arrDiagnostics))
	{
		return false;
	}
	arrFrames[nFrame].nFence = nFence;
	arrFrames[nFrame].bReadbackPending = (nRecordedPasses & (1U << static_cast<std::uint32_t>(GiPass::Readback))) != 0;
	stGrid = std::move(stPendingGrid);
	arrNeedsUpdate = std::move(arrPendingNeedsUpdate);
	nUpdatedCount = static_cast<std::uint32_t>(arrPendingUpdates.size());
	arrPendingUpdates.clear();
	arrPendingWorlds.clear();
	nReadHistory = 1 - nReadHistory;
	nCommittedInvalidation = nPendingInvalidation;
	bHasSubmitted = true;
	++nEpoch;
	nPendingFrame = GI_PENDING_FRAMES;
	nRecordedPasses = 0;
	stMemory.stRayTracing = stScene.Memory();
	return true;
}

bool GpuProbeGrid::Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nFrame >= GI_PENDING_FRAMES || nPendingFrame != nFrame)
	{
		return Error(out_arrDiagnostics, "Discard requires the current unsubmitted frame.");
	}
	if ((nRecordedPasses & (1U << static_cast<std::uint32_t>(GiPass::BuildScene))) != 0 &&
		!stScene.CancelRecorded(nFrame, out_arrDiagnostics))
	{
		return false;
	}
	stPendingGrid = ProbeGrid{};
	arrPendingNeedsUpdate.clear();
	arrPendingUpdates.clear();
	arrPendingWorlds.clear();
	nPendingFrame = GI_PENDING_FRAMES;
	nRecordedPasses = 0;
	return true;
}

bool GpuProbeGrid::Collect(std::uint32_t nFrame, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || !bInitialized || nFrame >= GI_PENDING_FRAMES || nCompletedFence == UINT64_MAX)
	{
		return Error(out_arrDiagnostics, "Collect requires an initialized owner-thread frame and completed fence.");
	}
	if (!stScene.Retire(nCompletedFence, out_arrDiagnostics))
	{
		return false;
	}
	stMemory.stRayTracing = stScene.Memory();
	Frame &stFrame = arrFrames[nFrame];
	if (!stFrame.bReadbackPending || stFrame.nFence > nCompletedFence)
	{
		return true;
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stRange{ 0, static_cast<SIZE_T>(stGrid.stBudget.nProbeCount) * GI_STATE_STRIDE };
	if (FAILED(stFrame.stReadback->Map(0, &stRange, &pMapped)))
	{
		return Error(out_arrDiagnostics, "Could not map the retired probe state readback.");
	}
	const ProbeGpuState *pStates = static_cast<const ProbeGpuState *>(pMapped);
	std::uint32_t nValid = 0;
	std::uint32_t nInvalid = 0;
	bool bMalformed = false;
	for (std::uint32_t nIndex = 0; nIndex < stGrid.stBudget.nProbeCount; ++nIndex)
	{
		const std::array<std::uint32_t, 4> &arrState = pStates[nIndex].arrValues;
		if (arrState[0] > 1 || arrState[3] > 1 || (arrState[0] != 0 && arrState[3] != 0) ||
			(arrState[0] == 0 && arrState[3] == 0 && arrState[2] != 0) ||
			((arrState[0] != 0 || arrState[3] != 0) && arrState[2] != stSettings.nRaysPerProbe))
		{
			bMalformed = true;
			break;
		}
		nValid += arrState[0] != 0 ? 1U : 0U;
		nInvalid += arrState[3] != 0 ? 1U : 0U;
	}
	const D3D12_RANGE stNoWrite{ 0, 0 };
	stFrame.stReadback->Unmap(0, &stNoWrite);
	if (bMalformed)
	{
		return Error(out_arrDiagnostics, "Probe state readback contains an invalid state or ray count.");
	}
	nPeakInvalidCount = std::max(nPeakInvalidCount, nInvalid);
	if (stFrame.nFence >= nCollectedFence)
	{
		nCollectedFence = stFrame.nFence;
		nValidCount = nValid;
		nInvalidCount = nInvalid;
	}
	stFrame.bReadbackPending = false;
	return true;
}

bool GpuProbeGrid::Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || !CanRelease(nCompletedFence) || !stScene.Release(nCompletedFence, out_arrDiagnostics))
	{
		return Error(out_arrDiagnostics, "GI resources require an owner-thread completed fence and no pending recording.");
	}
	GpuProbeGrid stEmpty;
	Swap(stEmpty);
	return true;
}

void GpuProbeGrid::InvalidateHistory() noexcept
{
	if (IsOwner())
	{
		++nInvalidationSerial;
		if (nInvalidationSerial == nCommittedInvalidation)
		{
			++nInvalidationSerial;
		}
	}
}

ID3D12Resource *GpuProbeGrid::Scene(std::uint32_t nFrame) const noexcept
{
	return stScene.TlasResource(nFrame);
}

ID3D12Resource *GpuProbeGrid::Positions() const noexcept
{
	return stPositions.Get();
}

ID3D12Resource *GpuProbeGrid::Rays(std::uint32_t nFrame) const noexcept
{
	return nFrame < GI_PENDING_FRAMES ? arrFrames[nFrame].stRays.Get() : nullptr;
}

ID3D12Resource *GpuProbeGrid::RayStatus(std::uint32_t nFrame) const noexcept
{
	return nFrame < GI_PENDING_FRAMES ? arrFrames[nFrame].stRayStatus.Get() : nullptr;
}

ID3D12Resource *GpuProbeGrid::Readback(std::uint32_t nFrame) const noexcept
{
	return nFrame < GI_PENDING_FRAMES ? arrFrames[nFrame].stReadback.Get() : nullptr;
}

ID3D12Resource *GpuProbeGrid::Upload(std::uint32_t nFrame) const noexcept
{
	return nFrame < GI_PENDING_FRAMES ? arrFrames[nFrame].stUpload.Get() : nullptr;
}

ID3D12Resource *GpuProbeGrid::History(bool bWrite, GiHistoryKind eKind) const noexcept
{
	const std::uint32_t nKind = static_cast<std::uint32_t>(eKind);
	return nKind < 3 ? arrHistory[bWrite ? 1 - nReadHistory : nReadHistory].arrBuffers[nKind].Get() : nullptr;
}

D3D12_GPU_DESCRIPTOR_HANDLE GpuProbeGrid::ReceiverGpu(std::uint32_t nFrame) const noexcept
{
	return nFrame < GI_PENDING_FRAMES && bInitialized ? GpuView(arrDescriptors[nFrame], NEW_HISTORY_VIEW) : D3D12_GPU_DESCRIPTOR_HANDLE{};
}

D3D12_GPU_VIRTUAL_ADDRESS GpuProbeGrid::ConstantsGpu(std::uint32_t nFrame) const noexcept
{
	return nFrame < GI_PENDING_FRAMES && bInitialized ? arrFrames[nFrame].stUpload->GetGPUVirtualAddress() : 0;
}

std::uint32_t GpuProbeGrid::ProbeCount() const noexcept
{
	return stGrid.stBudget.nProbeCount;
}

std::uint32_t GpuProbeGrid::UpdatedCount() const noexcept
{
	return nPendingFrame < GI_PENDING_FRAMES ? static_cast<std::uint32_t>(arrPendingUpdates.size()) : nUpdatedCount;
}

std::uint32_t GpuProbeGrid::ValidCount() const noexcept
{
	return nValidCount;
}

std::uint32_t GpuProbeGrid::InvalidCount() const noexcept
{
	return nInvalidCount;
}

std::uint32_t GpuProbeGrid::PeakInvalidCount() const noexcept
{
	return nPeakInvalidCount;
}

std::uint64_t GpuProbeGrid::SubmissionEpoch() const noexcept
{
	return nEpoch;
}

const GpuProbeMemory &GpuProbeGrid::Memory() const noexcept
{
	return stMemory;
}

const std::vector<RayTracingIdentity> &GpuProbeGrid::Identities() const noexcept
{
	return stScene.Identities();
}

void GpuProbeGrid::Swap(GpuProbeGrid &stOther) noexcept
{
	using std::swap;
	swap(nOwnerThread, stOther.nOwnerThread);
	swap(bInitialized, stOther.bInitialized);
	swap(bHasSubmitted, stOther.bHasSubmitted);
	swap(nReadHistory, stOther.nReadHistory);
	swap(nPendingFrame, stOther.nPendingFrame);
	swap(nRecordedPasses, stOther.nRecordedPasses);
	swap(nUpdatedCount, stOther.nUpdatedCount);
	swap(nValidCount, stOther.nValidCount);
	swap(nInvalidCount, stOther.nInvalidCount);
	swap(nPeakInvalidCount, stOther.nPeakInvalidCount);
	swap(bPendingHistoryValid, stOther.bPendingHistoryValid);
	swap(nEpoch, stOther.nEpoch);
	swap(nInvalidationSerial, stOther.nInvalidationSerial);
	swap(nCommittedInvalidation, stOther.nCommittedInvalidation);
	swap(nPendingInvalidation, stOther.nPendingInvalidation);
	swap(nPreparedCompletedFence, stOther.nPreparedCompletedFence);
	swap(nCollectedFence, stOther.nCollectedFence);
	swap(nPositionOffset, stOther.nPositionOffset);
	swap(nRemapOffset, stOther.nRemapOffset);
	swap(nUpdateOffset, stOther.nUpdateOffset);
	swap(nMaterialCount, stOther.nMaterialCount);
	swap(stDevice, stOther.stDevice);
	swap(stScene, stOther.stScene);
	swap(stSettings, stOther.stSettings);
	swap(stGrid, stOther.stGrid);
	swap(stPendingGrid, stOther.stPendingGrid);
	swap(arrNeedsUpdate, stOther.arrNeedsUpdate);
	swap(arrPendingNeedsUpdate, stOther.arrPendingNeedsUpdate);
	swap(arrPendingUpdates, stOther.arrPendingUpdates);
	swap(arrPendingWorlds, stOther.arrPendingWorlds);
	swap(arrFrames, stOther.arrFrames);
	swap(arrHistory, stOther.arrHistory);
	swap(arrDescriptors, stOther.arrDescriptors);
	swap(stPositions, stOther.stPositions);
	swap(stMaterialExtensions, stOther.stMaterialExtensions);
	swap(stRoot, stOther.stRoot);
	swap(stClearHeap, stOther.stClearHeap);
	swap(arrPipelines, stOther.arrPipelines);
	swap(stMemory, stOther.stMemory);
}

} // namespace EngineNext::Rendering
