/**************************************************************************/
/*  GpuRayReflections.cpp                                                 */
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

#include "engine_next/Platform/Windows/GpuRayReflections.h"

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
constexpr std::uint32_t STAGE_VIEWS = 38;
constexpr std::uint32_t SRV_COUNT = 31;
constexpr std::uint64_t CONSTANT_STRIDE = 256;
constexpr std::uint64_t ZERO_OFFSET = 6 * CONSTANT_STRIDE;
constexpr std::uint64_t UPLOAD_BYTES = ZERO_OFFSET + 256;
constexpr std::uint32_t PREPARED = 1;
constexpr std::uint32_t TRACED = 2;
constexpr std::uint32_t TEMPORAL = 4;
constexpr std::uint32_t COMPOSITED = 8;
constexpr std::uint32_t READ_BACK = 16;
constexpr std::uint32_t BUILT = 32;
constexpr std::array<DXGI_FORMAT, 7> HISTORY_FORMATS{ DXGI_FORMAT_R32G32B32A32_FLOAT, DXGI_FORMAT_R32G32B32A32_FLOAT,
													  DXGI_FORMAT_R32G32B32A32_FLOAT, DXGI_FORMAT_R16G16B16A16_FLOAT, DXGI_FORMAT_R32G32_FLOAT, DXGI_FORMAT_R32_UINT, DXGI_FORMAT_R32G32B32A32_UINT };

bool Error(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "ray_reflections", "$.reflections.ray_tracing", pMessage);
	return false;
}

D3D12_CPU_DESCRIPTOR_HANDLE CpuView(const RayReflectionDescriptors &stBlock, std::uint32_t nIndex)
{
	return { stBlock.stCpu.ptr + static_cast<SIZE_T>(nIndex) * stBlock.nStride };
}

D3D12_GPU_DESCRIPTOR_HANDLE GpuView(const RayReflectionDescriptors &stBlock, std::uint32_t nIndex)
{
	return { stBlock.stGpu.ptr + static_cast<UINT64>(nIndex) * stBlock.nStride };
}

bool CreateResource(ID3D12Device5 *pDevice, const D3D12_RESOURCE_DESC &stDescription, D3D12_HEAP_TYPE eHeap,
					std::uint64_t nLimit, std::uint64_t &io_nAllocated, ComOwner<ID3D12Resource> &out_stResource)
{
	const D3D12_RESOURCE_ALLOCATION_INFO stAllocation = pDevice->GetResourceAllocationInfo(0, 1, &stDescription);
	if (stAllocation.SizeInBytes == UINT64_MAX || stAllocation.SizeInBytes == 0 ||
		io_nAllocated > nLimit || stAllocation.SizeInBytes > nLimit - io_nAllocated)
	{
		return false;
	}
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eHeap;
	stHeap.CreationNodeMask = stHeap.VisibleNodeMask = 1;
	const D3D12_RESOURCE_STATES eInitial = eHeap == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ : eHeap == D3D12_HEAP_TYPE_READBACK ? D3D12_RESOURCE_STATE_COPY_DEST
																																				   : D3D12_RESOURCE_STATE_COMMON;
	if (FAILED(pDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, eInitial, nullptr, IID_PPV_ARGS(out_stResource.Put()))))
	{
		return false;
	}
	io_nAllocated += stAllocation.SizeInBytes;
	return true;
}

D3D12_RESOURCE_DESC Buffer(std::uint64_t nBytes, bool bUav)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = std::max<std::uint64_t>(nBytes, 16);
	stDescription.Height = stDescription.DepthOrArraySize = stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	stDescription.Flags = bUav ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE;
	return stDescription;
}

D3D12_RESOURCE_DESC Image(std::uint32_t nWidth, std::uint32_t nHeight, DXGI_FORMAT eFormat)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
	stDescription.Width = nWidth;
	stDescription.Height = nHeight;
	stDescription.DepthOrArraySize = stDescription.MipLevels = 1;
	stDescription.Format = eFormat;
	stDescription.SampleDesc.Count = 1;
	stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
	return stDescription;
}

bool Fill(ID3D12Resource *pResource, const void *pData, std::size_t nBytes)
{
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(pResource->Map(0, &stNoRead, &pMapped)))
	{
		return false;
	}
	std::memset(pMapped, 0, static_cast<std::size_t>(pResource->GetDesc().Width));
	if (nBytes != 0)
	{
		std::memcpy(pMapped, pData, nBytes);
	}
	pResource->Unmap(0, nullptr);
	return true;
}

void Srv(ID3D12Device5 *pDevice, ID3D12Resource *pResource, D3D12_CPU_DESCRIPTOR_HANDLE stHandle,
		 std::uint32_t nStride = 0, bool bCube = false, D3D12_GPU_VIRTUAL_ADDRESS nAcceleration = 0)
{
	D3D12_SHADER_RESOURCE_VIEW_DESC stView{};
	stView.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	if (nAcceleration != 0)
	{
		stView.ViewDimension = D3D12_SRV_DIMENSION_RAYTRACING_ACCELERATION_STRUCTURE;
		stView.RaytracingAccelerationStructure.Location = nAcceleration;
		pDevice->CreateShaderResourceView(nullptr, &stView, stHandle);
		return;
	}
	if (nStride != 0)
	{
		stView.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
		stView.Buffer.StructureByteStride = nStride;
		stView.Buffer.NumElements = pResource == nullptr ? 1 : static_cast<UINT>(pResource->GetDesc().Width / nStride);
	}
	else
	{
		stView.Format = pResource == nullptr ? DXGI_FORMAT_R32G32B32A32_FLOAT : pResource->GetDesc().Format;
		if (stView.Format == DXGI_FORMAT_D32_FLOAT || stView.Format == DXGI_FORMAT_R32_TYPELESS)
		{
			stView.Format = DXGI_FORMAT_R32_FLOAT;
		}
		stView.ViewDimension = bCube ? D3D12_SRV_DIMENSION_TEXTURECUBE : D3D12_SRV_DIMENSION_TEXTURE2D;
		if (bCube)
		{
			stView.TextureCube.MipLevels = pResource->GetDesc().MipLevels;
		}
		else
		{
			stView.Texture2D.MipLevels = 1;
		}
	}
	pDevice->CreateShaderResourceView(pResource, &stView, stHandle);
}

void Uav(ID3D12Device5 *pDevice, ID3D12Resource *pResource, D3D12_CPU_DESCRIPTOR_HANDLE stHandle, bool bBuffer = false)
{
	D3D12_UNORDERED_ACCESS_VIEW_DESC stView{};
	stView.ViewDimension = bBuffer ? D3D12_UAV_DIMENSION_BUFFER : D3D12_UAV_DIMENSION_TEXTURE2D;
	stView.Format = bBuffer ? DXGI_FORMAT_UNKNOWN : pResource == nullptr ? DXGI_FORMAT_R32G32B32A32_FLOAT
																		 : pResource->GetDesc().Format;
	if (bBuffer)
	{
		stView.Buffer.StructureByteStride = 4;
		stView.Buffer.NumElements = static_cast<UINT>(pResource->GetDesc().Width / 4);
	}
	pDevice->CreateUnorderedAccessView(pResource, nullptr, &stView, stHandle);
}

bool Pipelines(ID3D12Device5 *pDevice, const std::filesystem::path &stDirectory, ComOwner<ID3D12RootSignature> &out_stRoot,
			   std::array<ComOwner<ID3D12PipelineState>, 4> &out_arrPipelines)
{
	std::array<D3D12_DESCRIPTOR_RANGE, 4> arrDescriptorRanges{ { { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, SRV_COUNT, 0, 0, 0 },
																 { D3D12_DESCRIPTOR_RANGE_TYPE_UAV, 7, 0, 0, 0 },
																 { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 2045, 0, 1, 0 },
																 { D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER, 2045, 0, 1, 0 } } };
	std::array<D3D12_ROOT_PARAMETER, 7> arrParameters{};
	for (std::uint32_t nIndex = 0; nIndex < 3; ++nIndex)
	{
		arrParameters[nIndex].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
		arrParameters[nIndex].Descriptor.ShaderRegister = nIndex == 2 ? 4 : nIndex;
	}
	for (std::uint32_t nIndex = 0; nIndex < arrDescriptorRanges.size(); ++nIndex)
	{
		arrParameters[nIndex + 3].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nIndex + 3].DescriptorTable = { 1, &arrDescriptorRanges[nIndex] };
	}
	D3D12_STATIC_SAMPLER_DESC stSampler{};
	stSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
	stSampler.AddressU = stSampler.AddressV = stSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
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
	const std::array<const char *, 4> arrNames{ "RayReflectionTrace.cs.cso", "RayReflectionTemporal.cs.cso", "RayReflectionSpatial.cs.cso", "RayReflectionComposite.cs.cso" };
	for (std::size_t nIndex = 0; nIndex < arrNames.size(); ++nIndex)
	{
		std::ifstream stFile(stDirectory / arrNames[nIndex], std::ios::binary | std::ios::ate);
		const std::streamoff nBytes = stFile.tellg();
		if (!stFile || nBytes <= 0 || static_cast<std::uint64_t>(nBytes) > 16 * 1024 * 1024)
		{
			return false;
		}
		std::vector<char> arrBytes(static_cast<std::size_t>(nBytes));
		stFile.seekg(0);
		stFile.read(arrBytes.data(), nBytes);
		D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
		stPipeline.pRootSignature = out_stRoot.Get();
		stPipeline.CS = { arrBytes.data(), arrBytes.size() };
		if (!stFile || FAILED(pDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(out_arrPipelines[nIndex].Put()))))
		{
			return false;
		}
	}
	return true;
}
} // namespace

bool GpuRayReflections::IsOwner() const noexcept
{
	return nOwnerThread == GetCurrentThreadId();
}

bool GpuRayReflections::Initialize(ID3D12Device5 *pDevice, const ReflectionSettings &stInput, std::uint32_t nWidth, std::uint32_t nHeight,
								   const RenderScene &stSource, const std::vector<std::array<float, 4>> &arrExtensions, const RayTracingScene *pBorrowed,
								   const std::filesystem::path &stShaderDirectory, const std::array<RayReflectionDescriptors, RAY_TRACING_FRAME_COUNT> &arrBlocks,
								   std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (bInitialized || pDevice == nullptr || nCompletedFence == UINT64_MAX || !stInput.bEnabled || !stInput.stRayTracing.bEnabled ||
		!ValidateReflectionSettings(stInput, out_arrDiagnostics) || !RayTracingScene::CheckCapabilities(pDevice, out_arrDiagnostics))
	{
		return Error(out_arrDiagnostics, "Initialization requires an unused owner and enabled DXR settings.");
	}
	GpuRayReflections stCandidate;
	stCandidate.nOwnerThread = GetCurrentThreadId();
	stCandidate.nImageWidth = nWidth;
	stCandidate.nImageHeight = nHeight;
	stCandidate.stSettings = stInput;
	stCandidate.arrDescriptors = arrBlocks;
	stCandidate.pBorrowedScene = pBorrowed;
	pDevice->AddRef();
	*stCandidate.stDevice.Put() = pDevice;
	if (!BuildRayReflectionBudget(stInput.stRayTracing, nWidth, nHeight, stCandidate.stBudget, out_arrDiagnostics))
	{
		return false;
	}
	for (const RayReflectionDescriptors &stBlock : arrBlocks)
	{
		if (stBlock.stCpu.ptr == 0 || stBlock.stGpu.ptr == 0 || stBlock.nStride == 0)
		{
			return Error(out_arrDiagnostics, "Every frame requires its reserved descriptor block.");
		}
	}
	if (pBorrowed == nullptr)
	{
		if (!stCandidate.stOwnedScene.Prepare(pDevice, stSource, {}, nCompletedFence, out_arrDiagnostics))
		{
			return false;
		}
		const RayTracingMemory &stMemory = stCandidate.stOwnedScene.Memory();
		stCandidate.nAllocatedBytes = stMemory.nResidentBytes + stMemory.nScratchBytes + stMemory.nUploadBytes;
	}
	const RayTracingScene &stRayScene = stCandidate.RayScene();
	if (arrExtensions.size() != stRayScene.SourceMaterials().size() || arrExtensions.size() > 409)
	{
		return Error(out_arrDiagnostics, "Material extensions must match the ray-scene material order.");
	}
	for (const std::array<float, 4> &arrExtension : arrExtensions)
	{
		for (float fValue : arrExtension)
		{
			if (!std::isfinite(fValue))
			{
				return Error(out_arrDiagnostics, "Nonfinite ray-scene material extension.");
			}
		}
	}
	const std::uint64_t nLimit = stInput.stRayTracing.nMaxGpuBytes;
	const RayReflectionBudget &stSize = stCandidate.stBudget;
	for (std::uint32_t nIndex = 0; nIndex < 3; ++nIndex)
	{
		if (!CreateResource(pDevice, Image(stSize.nWidth, stSize.nHeight, nIndex == 2 ? DXGI_FORMAT_R32G32B32A32_UINT : DXGI_FORMAT_R32G32B32A32_FLOAT),
							D3D12_HEAP_TYPE_DEFAULT, nLimit, stCandidate.nAllocatedBytes, stCandidate.arrRaw[nIndex]))
		{
			return Error(out_arrDiagnostics, "Raw reflection allocation exceeds the budget or failed.");
		}
	}
	for (std::uint32_t nGroup = 0; nGroup < 2; ++nGroup)
	{
		for (std::uint32_t nImage = 0; nImage < HISTORY_FORMATS.size(); ++nImage)
		{
			if (!CreateResource(pDevice, Image(stSize.nWidth, stSize.nHeight, HISTORY_FORMATS[nImage]),
								D3D12_HEAP_TYPE_DEFAULT, nLimit, stCandidate.nAllocatedBytes, stCandidate.arrHistory[nGroup][nImage]))
			{
				return Error(out_arrDiagnostics, "History allocation exceeds the budget or failed.");
			}
		}
		if (!CreateResource(pDevice, Image(stSize.nWidth, stSize.nHeight, DXGI_FORMAT_R32G32B32A32_FLOAT),
							D3D12_HEAP_TYPE_DEFAULT, nLimit, stCandidate.nAllocatedBytes, stCandidate.arrScratch[nGroup]))
		{
			return Error(out_arrDiagnostics, "Spatial allocation exceeds the budget or failed.");
		}
	}
	for (Frame &stFrame : stCandidate.arrFrames)
	{
		if (!CreateResource(pDevice, Buffer(UPLOAD_BYTES, false), D3D12_HEAP_TYPE_UPLOAD, nLimit, stCandidate.nAllocatedBytes, stFrame.stUpload) ||
			!CreateResource(pDevice, Buffer(64, true), D3D12_HEAP_TYPE_DEFAULT, nLimit, stCandidate.nAllocatedBytes, stFrame.stCounters) ||
			!CreateResource(pDevice, Buffer(64, false), D3D12_HEAP_TYPE_READBACK, nLimit, stCandidate.nAllocatedBytes, stFrame.stReadback))
		{
			return Error(out_arrDiagnostics, "Per-frame allocation exceeds the budget or failed.");
		}
	}
	if (!CreateResource(pDevice, Buffer(std::max<std::size_t>(arrExtensions.size(), 1) * 16, false), D3D12_HEAP_TYPE_UPLOAD,
						nLimit, stCandidate.nAllocatedBytes, stCandidate.stExtensions) ||
		!Fill(stCandidate.stExtensions.Get(), arrExtensions.data(), arrExtensions.size() * 16) ||
		!Pipelines(pDevice, stShaderDirectory, stCandidate.stRoot, stCandidate.arrPipelines))
	{
		return Error(out_arrDiagnostics, "Ray-reflection material upload or compute pipelines failed.");
	}
	stCandidate.bInitialized = true;
	*this = std::move(stCandidate);
	return true;
}

bool GpuRayReflections::PrepareFrame(std::uint32_t nFrame, const RayReflectionConstants &stInput,
									 const std::vector<std::array<double, 16>> &arrWorlds, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics,
									 const DeformationFrame *pDeformation)
{
	if (!bInitialized || !IsOwner() || nFrame >= arrFrames.size() || nCompletedFence == UINT64_MAX || nPendingFrame != RAY_TRACING_FRAME_COUNT ||
		arrFrames[nFrame].nFence > nCompletedFence || arrWorlds.size() != RayScene().Identities().size())
	{
		return Error(out_arrDiagnostics, "Prepare requires one retired frame and matching draw identities.");
	}
	RayReflectionStatistics stRetired;
	if (!Collect(nFrame, nCompletedFence, stRetired, out_arrDiagnostics))
	{
		return false;
	}
	const std::array<const std::array<float, 4> *, 7> arrFields{ &stInput.arrViewport, &stInput.arrProjection, &stInput.arrTraceRange,
																 &stInput.arrSettings, &stInput.arrHistory, &stInput.arrFilter, &stInput.arrJitter };
	for (const std::array<float, 4> *pField : arrFields)
	{
		for (float fValue : *pField)
		{
			if (!std::isfinite(fValue))
			{
				return Error(out_arrDiagnostics, "Nonfinite frame constants.");
			}
		}
	}
	RayReflectionConstants stConstants = stInput;
	stConstants.arrViewport[0] = static_cast<float>(nImageWidth);
	stConstants.arrViewport[1] = static_cast<float>(nImageHeight);
	stConstants.arrViewport[2] = static_cast<float>(stBudget.nWidth);
	stConstants.arrViewport[3] = static_cast<float>(stBudget.nHeight);
	stConstants.arrTraceRange[2] = static_cast<float>(stSettings.dMaxDistance);
	stConstants.arrTraceRange[3] = static_cast<float>(stSettings.dNormalBias);
	stConstants.arrSettings[0] = static_cast<float>(stSettings.stRayTracing.nSamplesPerLobe);
	stConstants.arrSettings[1] = static_cast<float>(nEpoch % 16777216);
	stConstants.arrSettings[2] = nEpoch > 0 && nCommittedInvalidation == nInvalidation ? 1.0F : 0.0F;
	stConstants.arrHistory = { static_cast<float>(stSettings.stRayTracing.dHistoryWeight), static_cast<float>(stSettings.stRayTracing.dDepthThreshold),
							   static_cast<float>(stSettings.stRayTracing.dNormalThreshold), static_cast<float>(stSettings.stRayTracing.dRoughnessThreshold) };
	stConstants.arrCounts = { static_cast<std::uint32_t>(RayScene().Identities().size()), static_cast<std::uint32_t>(RayScene().SourceMaterials().size()),
							  static_cast<std::uint32_t>(RayScene().SourceMaterials().size() * 5), stSettings.stRayTracing.nMaxHistory };
	stConstants.arrFilter[2] = static_cast<float>(stSettings.dMaxRoughness);
	stConstants.arrFilter[3] = static_cast<float>(stSettings.nMaxSteps);
	stConstants.arrJitter[2] = static_cast<float>(stSettings.dThickness);
	std::array<std::uint8_t, UPLOAD_BYTES> arrUpload{};
	for (std::uint32_t nStage = 0; nStage < 6; ++nStage)
	{
		stConstants.arrFilter[0] = nStage >= 2 && nStage <= 4 ? static_cast<float>(1U << (nStage - 2)) : 1.0F;
		std::memcpy(arrUpload.data() + nStage * CONSTANT_STRIDE, &stConstants, sizeof(stConstants));
	}
	if (!Fill(arrFrames[nFrame].stUpload.Get(), arrUpload.data(), arrUpload.size()))
	{
		return Error(out_arrDiagnostics, "Frame constant upload failed.");
	}
	if (OwnsScene() && pDeformation != nullptr && !stOwnedScene.PrepareDeformation(nFrame, *pDeformation, nCompletedFence, out_arrDiagnostics))
	{
		return false;
	}
	arrPendingWorlds = arrWorlds;
	nPreparedFence = nCompletedFence;
	nPreparedInvalidation = nInvalidation;
	nPendingFrame = nFrame;
	nRecorded = nSpatialRecorded = 0;
	return true;
}

bool GpuRayReflections::WriteDescriptors(std::uint32_t nFrame, std::uint32_t nStage, const RayReflectionBindings &stBindings, Assets::Diagnostics &out_arrDiagnostics)
{
	std::array<ID3D12Resource *, SRV_COUNT> arrInputs{};
	std::array<ID3D12Resource *, 7> arrOutputs{};
	if (nStage == 0)
	{
		arrInputs = stBindings.arrResources;
		arrInputs[1] = RayScene().VertexBuffer();
		arrInputs[2] = RayScene().IndexBuffer();
		arrInputs[3] = RayScene().DrawBuffer();
		arrInputs[4] = RayScene().MaterialBuffer();
		arrInputs[21] = stExtensions.Get();
		arrOutputs = { Raw(0), Raw(1), Raw(2), Counters(nFrame), nullptr, nullptr, nullptr };
	}
	else if (nStage == 1)
	{
		for (std::uint32_t nIndex = 0; nIndex < 3; ++nIndex)
		{
			arrInputs[nIndex] = Raw(nIndex);
		}
		for (std::uint32_t nIndex = 0; nIndex < 7; ++nIndex)
		{
			arrInputs[nIndex + 3] = History(false, nIndex);
			arrOutputs[nIndex] = History(true, nIndex);
		}
		arrInputs[10] = stBindings.arrResources[6];
		arrInputs[11] = stBindings.arrResources[7];
		arrInputs[12] = stBindings.arrResources[8];
		arrInputs[13] = stBindings.arrResources[9];
		arrInputs[14] = stBindings.arrResources[10];
		arrInputs[15] = stBindings.arrResources[11];
	}
	else if (nStage < 5)
	{
		const std::uint32_t nPass = nStage - 2;
		arrInputs[0] = nPass == 0 ? History(true, 0) : nPass == 1 ? Scratch(0)
																  : Raw(0);
		arrInputs[1] = nPass == 0 ? History(true, 1) : nPass == 1 ? Scratch(1)
																  : Raw(1);
		for (std::uint32_t nIndex = 2; nIndex < 7; ++nIndex)
		{
			arrInputs[nIndex] = History(true, nIndex);
		}
		arrOutputs[0] = nPass == 1 ? Raw(0) : Scratch(0);
		arrOutputs[1] = nPass == 1 ? Raw(1) : Scratch(1);
	}
	else
	{
		arrInputs[0] = stBindings.arrResources[24];
		arrInputs[1] = stBindings.arrResources[25];
		arrInputs[2] = Filtered(0);
		arrInputs[3] = Filtered(1);
		arrInputs[4] = History(true, 3);
		arrInputs[5] = History(true, 4);
		arrInputs[6] = History(true, 5);
		arrInputs[7] = stBindings.arrResources[6];
		arrInputs[8] = stBindings.arrResources[8];
		arrInputs[9] = stBindings.arrResources[10];
		arrInputs[10] = stBindings.arrResources[22];
		arrOutputs[0] = stBindings.arrResources[23];
	}
	const RayReflectionDescriptors &stBlock = arrDescriptors[nFrame];
	for (std::uint32_t nIndex = 0; nIndex < arrInputs.size(); ++nIndex)
	{
		std::uint32_t nStride = 0;
		if (nStage == 0)
		{
			if (nIndex >= 1 && nIndex <= 4)
			{
				nStride = nIndex == 1 ? 48 : nIndex == 2 ? 4
						: nIndex == 3					 ? 16
														 : 64;
			}
			else if (nIndex == 15 || nIndex == 16 || nIndex == 18 || nIndex == 21 || nIndex == 22 || nIndex == 30)
			{
				nStride = 16;
			}
			else if (nIndex == 17)
			{
				nStride = 8;
			}
		}
		else if (nStage == 5 && nIndex == 10)
		{
			nStride = 16;
		}
		Srv(stDevice.Get(), arrInputs[nIndex], CpuView(stBlock, nStage * STAGE_VIEWS + nIndex), nStride,
			nStage == 0 && (nIndex == 13 || nIndex == 14), nStage == 0 && nIndex == 0 ? RayScene().TlasAddress(nFrame) : 0);
	}
	for (std::uint32_t nIndex = 0; nIndex < arrOutputs.size(); ++nIndex)
	{
		Uav(stDevice.Get(), arrOutputs[nIndex], CpuView(stBlock, nStage * STAGE_VIEWS + SRV_COUNT + nIndex), nStage == 0 && nIndex == 3);
	}
	if (nStage == 0 && (stBindings.nFrameConstants == 0 || stBindings.stMaterials.ptr == 0 || stBindings.stSamplers.ptr == 0 || RayScene().TlasAddress(nFrame) == 0))
	{
		return Error(out_arrDiagnostics, "Trace requires complete frame/material/scene bindings.");
	}
	return true;
}

bool GpuRayReflections::Record(std::uint32_t nFrame, RayReflectionPass ePass, std::uint32_t nSpatialPass,
							   ID3D12GraphicsCommandList4 *pList, const RayReflectionBindings &stBindings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame >= arrFrames.size() || nFrame != nPendingFrame || pList == nullptr)
	{
		return Error(out_arrDiagnostics, "Recording requires the prepared owner frame.");
	}
	if (ePass == RayReflectionPass::BuildScene)
	{
		if (!OwnsScene() || nRecorded != 0 || !stOwnedScene.RecordBuildOrUpdate(nFrame, pList, arrPendingWorlds, nPreparedFence, out_arrDiagnostics))
		{
			return Error(out_arrDiagnostics, "Invalid owned acceleration build order.");
		}
		nRecorded |= BUILT;
		return true;
	}
	if (ePass == RayReflectionPass::Prepare)
	{
		if ((nRecorded & PREPARED) != 0 || (OwnsScene() && (nRecorded & BUILT) == 0))
		{
			return Error(out_arrDiagnostics, "Counter initialization must follow scene preparation once.");
		}
		pList->CopyBufferRegion(Counters(nFrame), 0, Upload(nFrame), ZERO_OFFSET, 64);
		nRecorded |= PREPARED;
		return true;
	}
	if (ePass == RayReflectionPass::Readback)
	{
		if ((nRecorded & COMPOSITED) == 0 || (nRecorded & READ_BACK) != 0)
		{
			return Error(out_arrDiagnostics, "Readback must follow composition once.");
		}
		pList->CopyBufferRegion(Readback(nFrame), 0, Counters(nFrame), 0, 64);
		if (OwnsScene() && !stOwnedScene.FinishDeformationReads(nFrame, pList, out_arrDiagnostics))
		{
			return false;
		}
		nRecorded |= READ_BACK;
		return true;
	}
	std::uint32_t nStage = 0;
	std::uint32_t nPipeline = 0;
	if (ePass == RayReflectionPass::Trace)
	{
		if ((nRecorded & PREPARED) == 0 || (nRecorded & TRACED) != 0)
		{
			return Error(out_arrDiagnostics, "Trace must follow counter initialization once.");
		}
	}
	else if (ePass == RayReflectionPass::Temporal)
	{
		if ((nRecorded & TRACED) == 0 || (nRecorded & TEMPORAL) != 0)
		{
			return Error(out_arrDiagnostics, "Temporal reconstruction must follow tracing once.");
		}
		nStage = nPipeline = 1;
	}
	else if (ePass == RayReflectionPass::Spatial)
	{
		if ((nRecorded & TEMPORAL) == 0 || nSpatialPass != nSpatialRecorded || nSpatialPass >= stSettings.stRayTracing.nSpatialPasses)
		{
			return Error(out_arrDiagnostics, "Spatial passes must run in configured order.");
		}
		nStage = nSpatialPass + 2;
		nPipeline = 2;
	}
	else if (ePass == RayReflectionPass::Composite)
	{
		if ((nRecorded & TEMPORAL) == 0 || (nRecorded & COMPOSITED) != 0 || nSpatialRecorded != stSettings.stRayTracing.nSpatialPasses)
		{
			return Error(out_arrDiagnostics, "Composition requires all configured filters once.");
		}
		nStage = 5;
		nPipeline = 3;
	}
	else
	{
		return Error(out_arrDiagnostics, "Unknown ray-reflection pass.");
	}
	if (!WriteDescriptors(nFrame, nStage, stBindings, out_arrDiagnostics))
	{
		return false;
	}
	pList->SetComputeRootSignature(stRoot.Get());
	pList->SetPipelineState(arrPipelines[nPipeline].Get());
	pList->SetComputeRootConstantBufferView(0, Upload(nFrame)->GetGPUVirtualAddress() + nStage * CONSTANT_STRIDE);
	pList->SetComputeRootConstantBufferView(1, stBindings.nFrameConstants);
	pList->SetComputeRootConstantBufferView(2, stBindings.nGiConstants != 0 ? stBindings.nGiConstants : Upload(nFrame)->GetGPUVirtualAddress() + ZERO_OFFSET);
	pList->SetComputeRootDescriptorTable(3, GpuView(arrDescriptors[nFrame], nStage * STAGE_VIEWS));
	pList->SetComputeRootDescriptorTable(4, GpuView(arrDescriptors[nFrame], nStage * STAGE_VIEWS + SRV_COUNT));
	pList->SetComputeRootDescriptorTable(5, stBindings.stMaterials);
	pList->SetComputeRootDescriptorTable(6, stBindings.stSamplers);
	const std::uint32_t nWidth = nStage == 5 ? nImageWidth : stBudget.nWidth;
	const std::uint32_t nHeight = nStage == 5 ? nImageHeight : stBudget.nHeight;
	pList->Dispatch((nWidth + 7) / 8, (nHeight + 7) / 8, 1);
	if (ePass == RayReflectionPass::Trace)
	{
		nRecorded |= TRACED;
	}
	if (ePass == RayReflectionPass::Temporal)
	{
		nRecorded |= TEMPORAL;
	}
	if (ePass == RayReflectionPass::Spatial)
	{
		++nSpatialRecorded;
	}
	if (ePass == RayReflectionPass::Composite)
	{
		nRecorded |= COMPOSITED;
	}
	return true;
}

bool GpuRayReflections::Submit(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame >= arrFrames.size() || nFrame != nPendingFrame || nFence == UINT64_MAX ||
		nFence <= nPreparedFence || nFence <= nLatestFence || (nRecorded & READ_BACK) == 0 ||
		(OwnsScene() && !stOwnedScene.CommitSubmission(nFrame, nFence, out_arrDiagnostics)))
	{
		return Error(out_arrDiagnostics, "Commit requires a complete submitted frame and a new fence.");
	}
	arrFrames[nFrame].nFence = nFence;
	nLatestFence = nFence;
	arrFrames[nFrame].bReadbackPending = true;
	nReadHistory = 1 - nReadHistory;
	nCommittedInvalidation = nPreparedInvalidation;
	++nEpoch;
	nPendingFrame = RAY_TRACING_FRAME_COUNT;
	arrPendingWorlds.clear();
	return true;
}

bool GpuRayReflections::Discard(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame >= arrFrames.size() || nFrame != nPendingFrame)
	{
		return Error(out_arrDiagnostics, "Discard requires the pending unsubmitted frame.");
	}
	if (OwnsScene() && (nRecorded & BUILT) != 0 && !stOwnedScene.CancelRecorded(nFrame, out_arrDiagnostics))
	{
		return false;
	}
	nPendingFrame = RAY_TRACING_FRAME_COUNT;
	arrPendingWorlds.clear();
	return true;
}

bool GpuRayReflections::Collect(std::uint32_t nFrame, std::uint64_t nCompletedFence, RayReflectionStatistics &out_stStatistics, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || !IsOwner() || nFrame >= arrFrames.size() || nCompletedFence == UINT64_MAX || arrFrames[nFrame].nFence > nCompletedFence)
	{
		return Error(out_arrDiagnostics, "Counter collection requires a retired owner slot.");
	}
	Frame &stFrame = arrFrames[nFrame];
	out_stStatistics = {};
	if (!stFrame.bReadbackPending)
	{
		return true;
	}
	const D3D12_RANGE stRead{ 0, 28 };
	void *pMapped = nullptr;
	if (FAILED(stFrame.stReadback->Map(0, &stRead, &pMapped)))
	{
		return Error(out_arrDiagnostics, "Counter readback map failed.");
	}
	std::array<std::uint32_t, 7> arrValues{};
	std::memcpy(arrValues.data(), pMapped, sizeof(arrValues));
	const D3D12_RANGE stNoWrite{ 0, 0 };
	stFrame.stReadback->Unmap(0, &stNoWrite);
	out_stStatistics = { arrValues[0], arrValues[1], arrValues[2], arrValues[3], arrValues[4], arrValues[5], arrValues[6] };
	if (stFrame.nFence >= nCollectedFence)
	{
		stStatistics = out_stStatistics;
		nCollectedFence = stFrame.nFence;
	}
	nPeakInvalidCount = std::max(nPeakInvalidCount, static_cast<std::uint64_t>(arrValues[4]));
	stFrame.bReadbackPending = false;
	return !OwnsScene() || stOwnedScene.Retire(nCompletedFence, out_arrDiagnostics);
}

bool GpuRayReflections::Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized)
	{
		return true;
	}
	if (!IsOwner() || nCompletedFence == UINT64_MAX || nPendingFrame != RAY_TRACING_FRAME_COUNT)
	{
		return Error(out_arrDiagnostics, "Release requires no unsubmitted work.");
	}
	for (std::uint32_t nFrame = 0; nFrame < arrFrames.size(); ++nFrame)
	{
		RayReflectionStatistics stRetired;
		if (!Collect(nFrame, nCompletedFence, stRetired, out_arrDiagnostics))
		{
			return false;
		}
	}
	if (OwnsScene() && !stOwnedScene.Release(nCompletedFence, out_arrDiagnostics))
	{
		return false;
	}
	*this = GpuRayReflections{};
	return true;
}

void GpuRayReflections::InvalidateHistory() noexcept
{
	++nInvalidation;
}
ID3D12Resource *GpuRayReflections::Raw(std::uint32_t nImage) const noexcept
{
	return nImage < arrRaw.size() ? arrRaw[nImage].Get() : nullptr;
}
ID3D12Resource *GpuRayReflections::History(bool bWrite, std::uint32_t nImage) const noexcept
{
	return nImage < 7 ? arrHistory[bWrite ? 1 - nReadHistory : nReadHistory][nImage].Get() : nullptr;
}
ID3D12Resource *GpuRayReflections::Scratch(std::uint32_t nImage) const noexcept
{
	return nImage < arrScratch.size() ? arrScratch[nImage].Get() : nullptr;
}
ID3D12Resource *GpuRayReflections::Filtered(std::uint32_t nImage) const noexcept
{
	return stSettings.stRayTracing.nSpatialPasses == 0 ? History(true, nImage) : stSettings.stRayTracing.nSpatialPasses % 2 != 0 ? Scratch(nImage)
																																 : Raw(nImage);
}
ID3D12Resource *GpuRayReflections::Counters(std::uint32_t nFrame) const noexcept
{
	return nFrame < arrFrames.size() ? arrFrames[nFrame].stCounters.Get() : nullptr;
}
ID3D12Resource *GpuRayReflections::Upload(std::uint32_t nFrame) const noexcept
{
	return nFrame < arrFrames.size() ? arrFrames[nFrame].stUpload.Get() : nullptr;
}
ID3D12Resource *GpuRayReflections::Readback(std::uint32_t nFrame) const noexcept
{
	return nFrame < arrFrames.size() ? arrFrames[nFrame].stReadback.Get() : nullptr;
}
ID3D12Resource *GpuRayReflections::Scene(std::uint32_t nFrame) const noexcept
{
	return RayScene().TlasResource(nFrame);
}
const RayTracingScene &GpuRayReflections::RayScene() const noexcept
{
	return pBorrowedScene != nullptr ? *pBorrowedScene : stOwnedScene;
}
bool GpuRayReflections::OwnsScene() const noexcept
{
	return pBorrowedScene == nullptr;
}
const RayReflectionBudget &GpuRayReflections::Budget() const noexcept
{
	return stBudget;
}
const RayReflectionStatistics &GpuRayReflections::Statistics() const noexcept
{
	return stStatistics;
}
std::uint64_t GpuRayReflections::AllocatedBytes() const noexcept
{
	return nAllocatedBytes;
}
std::uint64_t GpuRayReflections::SubmissionEpoch() const noexcept
{
	return nEpoch;
}

std::uint64_t GpuRayReflections::PeakInvalidCount() const noexcept
{
	return nPeakInvalidCount;
}

} // namespace EngineNext::Rendering
