/**************************************************************************/
/*  RayTracingScene.cpp                                                   */
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

#include "engine_next/Platform/Windows/RayTracingScene.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::uint64_t AS_ALIGNMENT = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BYTE_ALIGNMENT;
constexpr D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAGS BUILD_FLAGS = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_PREFER_FAST_TRACE;

bool Error(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "ray_tracing_scene", "$", pMessage);
	return false;
}

std::uint64_t Align(std::uint64_t nValue)
{
	return (nValue + AS_ALIGNMENT - 1) & ~(AS_ALIGNMENT - 1);
}

D3D12_RESOURCE_DESC BufferDescription(std::uint64_t nBytes, D3D12_RESOURCE_FLAGS eFlags)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = nBytes;
	stDescription.Height = 1;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	stDescription.Flags = eFlags;
	return stDescription;
}

bool Account(ID3D12Device5 *pDevice, std::uint64_t nBytes, D3D12_RESOURCE_FLAGS eFlags, std::uint64_t nLimit, std::uint64_t &out_nTotal, std::uint64_t *out_pAllocation = nullptr)
{
	const D3D12_RESOURCE_DESC stDescription = BufferDescription(nBytes, eFlags);
	const D3D12_RESOURCE_ALLOCATION_INFO stAllocation = pDevice->GetResourceAllocationInfo(0, 1, &stDescription);
	if (stAllocation.SizeInBytes == UINT64_MAX || out_nTotal > nLimit || stAllocation.SizeInBytes > nLimit - out_nTotal)
	{
		return false;
	}
	out_nTotal += stAllocation.SizeInBytes;
	if (out_pAllocation != nullptr)
	{
		*out_pAllocation = stAllocation.SizeInBytes;
	}
	return true;
}

bool CreateBuffer(ID3D12Device5 *pDevice, std::uint64_t nBytes, D3D12_HEAP_TYPE eHeap, D3D12_RESOURCE_FLAGS eFlags, D3D12_RESOURCE_STATES eState, ComOwner<ID3D12Resource> &out_stResource)
{
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eHeap;
	const D3D12_RESOURCE_DESC stDescription = BufferDescription(nBytes, eFlags);
	return SUCCEEDED(pDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, eState, nullptr, IID_PPV_ARGS(out_stResource.Put())));
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

void UavBarrier(ID3D12GraphicsCommandList4 *pList, ID3D12Resource *pResource)
{
	D3D12_RESOURCE_BARRIER stBarrier{};
	stBarrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
	stBarrier.UAV.pResource = pResource;
	pList->ResourceBarrier(1, &stBarrier);
}

void Transition(ID3D12GraphicsCommandList4 *pList, ID3D12Resource *pResource, D3D12_RESOURCE_STATES eBefore, D3D12_RESOURCE_STATES eAfter)
{
	D3D12_RESOURCE_BARRIER stBarrier{};
	stBarrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
	stBarrier.Transition.pResource = pResource;
	stBarrier.Transition.StateBefore = eBefore;
	stBarrier.Transition.StateAfter = eAfter;
	stBarrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
	pList->ResourceBarrier(1, &stBarrier);
}

bool WorldTransform(const std::array<double, 16> &arrWorld, D3D12_RAYTRACING_INSTANCE_DESC &out_stInstance)
{
	for (double dValue : arrWorld)
	{
		if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
		{
			return false;
		}
	}
	if (arrWorld[3] != 0 || arrWorld[7] != 0 || arrWorld[11] != 0 || arrWorld[15] != 1)
	{
		return false;
	}
	for (std::size_t nRow = 0; nRow < 3; ++nRow)
	{
		for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
		{
			out_stInstance.Transform[nRow][nColumn] = static_cast<float>(arrWorld[nColumn * 4 + nRow]);
		}
	}
	return true;
}
} // namespace

RayTracingScene::RayTracingScene(RayTracingScene &&stOther) noexcept
{
	*this = std::move(stOther);
}

RayTracingScene &RayTracingScene::operator=(RayTracingScene &&stOther) noexcept
{
	if (this == &stOther)
	{
		return *this;
	}
	arrGeometry = std::move(stOther.arrGeometry);
	arrIdentities = std::move(stOther.arrIdentities);
	arrTextures = std::move(stOther.arrTextures);
	arrSourceMaterials = std::move(stOther.arrSourceMaterials);
	arrInstances = std::move(stOther.arrInstances);
	stVertices = std::move(stOther.stVertices);
	stIndices = std::move(stOther.stIndices);
	stDraws = std::move(stOther.stDraws);
	stMaterials = std::move(stOther.stMaterials);
	stBlas = std::move(stOther.stBlas);
	stBlasScratch = std::move(stOther.stBlasScratch);
	stGeometryUpload = std::move(stOther.stGeometryUpload);
	for (std::size_t nIndex = 0; nIndex < RAY_TRACING_FRAME_COUNT; ++nIndex)
	{
		Frame &stDestination = arrFrames[nIndex];
		Frame &stSource = stOther.arrFrames[nIndex];
		stDestination.stTlas = std::move(stSource.stTlas);
		stDestination.stScratch = std::move(stSource.stScratch);
		stDestination.stInstances = std::move(stSource.stInstances);
		stDestination.nFence = std::exchange(stSource.nFence, 0);
		stDestination.bBuilt = std::exchange(stSource.bBuilt, false);
	}
	nOwnerThread = std::exchange(stOther.nOwnerThread, 0);
	nVertexBytes = std::exchange(stOther.nVertexBytes, 0);
	nIndexBytes = std::exchange(stOther.nIndexBytes, 0);
	nIndexUploadOffset = std::exchange(stOther.nIndexUploadOffset, 0);
	nStaticBuildFence = std::exchange(stOther.nStaticBuildFence, 0);
	nLatestFence = std::exchange(stOther.nLatestFence, 0);
	nBlasScratchAllocation = std::exchange(stOther.nBlasScratchAllocation, 0);
	nGeometryUploadAllocation = std::exchange(stOther.nGeometryUploadAllocation, 0);
	nPendingFrame = std::exchange(stOther.nPendingFrame, NO_RAY_TRACING_FRAME);
	bPendingStaticBuild = std::exchange(stOther.bPendingStaticBuild, false);
	bStaticBuilt = std::exchange(stOther.bStaticBuilt, false);
	bPrepared = std::exchange(stOther.bPrepared, false);
	stMemory = std::exchange(stOther.stMemory, RayTracingMemory{});
	return *this;
}

bool RayTracingScene::CheckCapabilities(ID3D12Device *pDevice, Assets::Diagnostics &out_arrDiagnostics)
{
	if (pDevice == nullptr)
	{
		return Error(out_arrDiagnostics, "A D3D12 device is required.");
	}
	D3D12_FEATURE_DATA_D3D12_OPTIONS5 stOptions{};
	D3D12_FEATURE_DATA_SHADER_MODEL stModel{ D3D_SHADER_MODEL_6_5 };
	if (FAILED(pDevice->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS5, &stOptions, sizeof(stOptions))) || stOptions.RaytracingTier < D3D12_RAYTRACING_TIER_1_1 || FAILED(pDevice->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL, &stModel, sizeof(stModel))) || stModel.HighestShaderModel < D3D_SHADER_MODEL_6_5)
	{
		return Error(out_arrDiagnostics, "Inline ray queries require DXR tier 1.1 and shader model 6.5.");
	}
	return true;
}

bool RayTracingScene::IsOwner() const noexcept
{
	return nOwnerThread == 0 || nOwnerThread == GetCurrentThreadId();
}

bool RayTracingScene::CanRelease(std::uint64_t nCompletedFence) const noexcept
{
	if (nCompletedFence == UINT64_MAX || nPendingFrame != NO_RAY_TRACING_FRAME || nCompletedFence < nStaticBuildFence)
	{
		return false;
	}
	for (const Frame &stFrame : arrFrames)
	{
		if (nCompletedFence < stFrame.nFence)
		{
			return false;
		}
	}
	return true;
}

bool RayTracingScene::Prepare(ID3D12Device5 *pDevice, const RenderScene &stSource, const RayTracingLimits &stLimits, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || !CanRelease(nCompletedFence))
	{
		return Error(out_arrDiagnostics, "The prior scene must be retired on its owner thread before replacement.");
	}
	if (!CheckCapabilities(pDevice, out_arrDiagnostics) || stLimits.nMaxInstances == 0 || stLimits.nMaxInstances > 0xFFFFFF || stLimits.nMaxGeometries == 0 || stLimits.nMaxResidentBytes == 0 || stLimits.nMaxScratchBytes == 0 || stLimits.nMaxUploadBytes == 0 || stSource.arrInstances.size() > stLimits.nMaxInstances)
	{
		return Error(out_arrDiagnostics, "Invalid ray tracing limits or instance count.");
	}
	RayTracingScene stCandidate;
	std::vector<MeshVertex> arrVertices;
	std::vector<std::uint32_t> arrIndices;
	std::vector<RayTracingDraw> arrDraws;
	std::vector<RayTracingMaterial> arrMaterials;
	std::vector<std::uint32_t> arrMaterialBase;
	std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint32_t> mapGeometry;
	std::vector<RayTracingDraw> arrGeometryDraws;
	std::uint64_t nBlasBytes = 0;
	std::uint64_t nScratchBytes = 0;
	for (std::size_t nAsset = 0; nAsset < stSource.arrAssets.size(); ++nAsset)
	{
		const DecodedMesh &stMesh = stSource.arrAssets[nAsset].stMesh;
		if (arrMaterials.size() + stMesh.arrMaterials.size() > UINT32_MAX || stCandidate.arrTextures.size() + stMesh.arrTextures.size() > UINT32_MAX || (arrMaterials.size() + stMesh.arrMaterials.size()) * sizeof(RayTracingMaterial) > stLimits.nMaxUploadBytes)
		{
			return Error(out_arrDiagnostics, "Material or texture mapping exceeds its index/upload budget.");
		}
		arrMaterialBase.push_back(static_cast<std::uint32_t>(arrMaterials.size()));
		const std::uint32_t nTextureBase = static_cast<std::uint32_t>(stCandidate.arrTextures.size());
		for (std::uint32_t nTexture = 0; nTexture < stMesh.arrTextures.size(); ++nTexture)
		{
			stCandidate.arrTextures.push_back({ static_cast<std::uint32_t>(nAsset), nTexture, stMesh.arrTextures[nTexture] });
		}
		for (const MaterialData &stMaterial : stMesh.arrMaterials)
		{
			stCandidate.arrSourceMaterials.push_back({ static_cast<std::uint32_t>(nAsset), static_cast<std::uint32_t>(arrMaterials.size() - arrMaterialBase.back()), stMaterial });
			RayTracingMaterial stGpu;
			for (std::size_t nChannel = 0; nChannel < 4; ++nChannel)
			{
				if (!std::isfinite(stMaterial.arrBaseColor[nChannel]) || stMaterial.arrBaseColor[nChannel] < 0 || (nChannel == 3 && stMaterial.arrBaseColor[nChannel] > 1))
				{
					return Error(out_arrDiagnostics, "Invalid material base color.");
				}
				stGpu.arrBaseColor[nChannel] = stMaterial.arrBaseColor[nChannel];
			}
			for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
			{
				if (!std::isfinite(stMaterial.arrEmissive[nChannel]) || stMaterial.arrEmissive[nChannel] < 0)
				{
					return Error(out_arrDiagnostics, "Invalid material emissive value.");
				}
				stGpu.arrEmissive[nChannel] = stMaterial.arrEmissive[nChannel];
			}
			if (!std::isfinite(stMaterial.fRoughness) || stMaterial.fRoughness < 0 || stMaterial.fRoughness > 1 || !std::isfinite(stMaterial.fMetallic) || stMaterial.fMetallic < 0 || stMaterial.fMetallic > 1 || !std::isfinite(stMaterial.fNormalScale) || !std::isfinite(stMaterial.fOcclusionStrength) || stMaterial.fOcclusionStrength < 0 || stMaterial.fOcclusionStrength > 1)
			{
				return Error(out_arrDiagnostics, "Invalid material surface parameters.");
			}
			stGpu.arrSurface = { stMaterial.fRoughness, stMaterial.fMetallic, stMaterial.nNormalTexture >= 0 ? stMaterial.fNormalScale : 0, stMaterial.fOcclusionStrength };
			if (!std::isfinite(stMaterial.fAlphaCutoff) || stMaterial.fAlphaCutoff < 0 || stMaterial.fAlphaCutoff > 1 || static_cast<unsigned>(stMaterial.eAlphaMode) > 2 || stMaterial.nBaseColorTexture < -1 || (stMaterial.nBaseColorTexture >= 0 && static_cast<std::size_t>(stMaterial.nBaseColorTexture) >= stMesh.arrTextures.size()))
			{
				return Error(out_arrDiagnostics, "Invalid alpha mode, cutoff or base texture mapping.");
			}
			stGpu.nAlphaMode = static_cast<std::uint32_t>(stMaterial.eAlphaMode);
			stGpu.fAlphaCutoff = stMaterial.fAlphaCutoff;
			if (stMaterial.nBaseColorTexture >= 0)
			{
				stGpu.nBaseTexture = nTextureBase + static_cast<std::uint32_t>(stMaterial.nBaseColorTexture);
				stGpu.nBaseSampler = stGpu.nBaseTexture;
			}
			arrMaterials.push_back(stGpu);
		}
	}
	for (const RenderInstance &stInstance : stSource.arrInstances)
	{
		if (stInstance.nAsset >= stSource.arrAssets.size())
		{
			return Error(out_arrDiagnostics, "Instance asset index is outside the source scene.");
		}
		const DecodedMesh &stMesh = stSource.arrAssets[stInstance.nAsset].stMesh;
		if (stInstance.nPrimitive >= stMesh.arrPrimitives.size())
		{
			return Error(out_arrDiagnostics, "Instance primitive index is outside the source asset.");
		}
		const MeshPrimitive &stPrimitive = stMesh.arrPrimitives[stInstance.nPrimitive];
		if (stPrimitive.nMaterial < 0 || static_cast<std::size_t>(stPrimitive.nMaterial) >= stMesh.arrMaterials.size() || stPrimitive.arrIndices.empty() || stPrimitive.arrIndices.size() % 3 != 0 || stPrimitive.arrVertices.empty())
		{
			return Error(out_arrDiagnostics, "Referenced geometry needs triangles, vertices and a valid material.");
		}
		D3D12_RAYTRACING_INSTANCE_DESC stGpuInstance{};
		if (!WorldTransform(stInstance.arrTransform, stGpuInstance))
		{
			return Error(out_arrDiagnostics, "Instance transform must be finite binary32 and affine.");
		}
		const std::pair<std::uint32_t, std::uint32_t> stKey{ stInstance.nAsset, stInstance.nPrimitive };
		std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint32_t>::iterator it = mapGeometry.find(stKey);
		if (it == mapGeometry.end())
		{
			if (stCandidate.arrGeometry.size() >= stLimits.nMaxGeometries || arrVertices.size() + stPrimitive.arrVertices.size() > UINT32_MAX || arrIndices.size() + stPrimitive.arrIndices.size() > UINT32_MAX || (arrVertices.size() + stPrimitive.arrVertices.size()) * sizeof(MeshVertex) + (arrIndices.size() + stPrimitive.arrIndices.size()) * sizeof(std::uint32_t) > stLimits.nMaxResidentBytes)
			{
				return Error(out_arrDiagnostics, "Geometry exceeds the configured count or resident budget.");
			}
			for (const MeshVertex &stVertex : stPrimitive.arrVertices)
			{
				for (float fValue : stVertex.arrPosition)
				{
					if (!std::isfinite(fValue))
					{
						return Error(out_arrDiagnostics, "Ray tracing positions must be finite.");
					}
				}
				for (float fValue : stVertex.arrTexcoord)
				{
					if (!std::isfinite(fValue))
					{
						return Error(out_arrDiagnostics, "Ray tracing texture coordinates must be finite.");
					}
				}
			}
			for (std::uint32_t nIndex : stPrimitive.arrIndices)
			{
				if (nIndex >= stPrimitive.arrVertices.size())
				{
					return Error(out_arrDiagnostics, "Triangle index is outside its primitive.");
				}
			}
			Geometry stGeometry;
			stGeometry.stDescription.Type = D3D12_RAYTRACING_GEOMETRY_TYPE_TRIANGLES;
			stGeometry.stDescription.Flags = stMesh.arrMaterials[stPrimitive.nMaterial].eAlphaMode == AlphaMode::Opaque ? D3D12_RAYTRACING_GEOMETRY_FLAG_OPAQUE : D3D12_RAYTRACING_GEOMETRY_FLAG_NONE;
			D3D12_RAYTRACING_GEOMETRY_TRIANGLES_DESC &stTriangles = stGeometry.stDescription.Triangles;
			stTriangles.VertexFormat = DXGI_FORMAT_R32G32B32_FLOAT;
			stTriangles.VertexCount = static_cast<UINT>(stPrimitive.arrVertices.size());
			stTriangles.VertexBuffer.StrideInBytes = sizeof(MeshVertex);
			// Prebuild may distinguish null from non-null GPU addresses. The
			// actual buffers are allocated after the complete size/budget plan.
			stTriangles.VertexBuffer.StartAddress = AS_ALIGNMENT;
			stTriangles.IndexFormat = DXGI_FORMAT_R32_UINT;
			stTriangles.IndexBuffer = AS_ALIGNMENT;
			stTriangles.IndexCount = static_cast<UINT>(stPrimitive.arrIndices.size());
			D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_INPUTS stInputs{};
			stInputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL;
			stInputs.Flags = BUILD_FLAGS;
			stInputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
			stInputs.NumDescs = 1;
			stInputs.pGeometryDescs = &stGeometry.stDescription;
			D3D12_RAYTRACING_ACCELERATION_STRUCTURE_PREBUILD_INFO stInfo{};
			pDevice->GetRaytracingAccelerationStructurePrebuildInfo(&stInputs, &stInfo);
			if (stInfo.ResultDataMaxSizeInBytes == 0 || stInfo.ResultDataMaxSizeInBytes > stLimits.nMaxResidentBytes || stInfo.ScratchDataSizeInBytes > stLimits.nMaxScratchBytes || nBlasBytes > stLimits.nMaxResidentBytes - Align(stInfo.ResultDataMaxSizeInBytes))
			{
				return Error(out_arrDiagnostics, "Invalid BLAS prebuild size or budget overflow.");
			}
			stGeometry.nResultOffset = nBlasBytes;
			nBlasBytes += Align(stInfo.ResultDataMaxSizeInBytes);
			nScratchBytes = std::max(nScratchBytes, Align(stInfo.ScratchDataSizeInBytes));
			const RayTracingDraw stDraw{ static_cast<std::uint32_t>(arrIndices.size()), static_cast<std::uint32_t>(arrVertices.size()), arrMaterialBase[stInstance.nAsset] + static_cast<std::uint32_t>(stPrimitive.nMaterial), static_cast<std::uint32_t>(stPrimitive.arrIndices.size()) };
			const std::uint32_t nGeometry = static_cast<std::uint32_t>(stCandidate.arrGeometry.size());
			it = mapGeometry.emplace(stKey, nGeometry).first;
			stCandidate.arrGeometry.push_back(stGeometry);
			arrGeometryDraws.push_back(stDraw);
			arrVertices.insert(arrVertices.end(), stPrimitive.arrVertices.begin(), stPrimitive.arrVertices.end());
			arrIndices.insert(arrIndices.end(), stPrimitive.arrIndices.begin(), stPrimitive.arrIndices.end());
		}
		const std::uint32_t nGeometry = it->second;
		const std::uint32_t nInstance = static_cast<std::uint32_t>(stCandidate.arrInstances.size());
		stGpuInstance.InstanceID = nInstance;
		stGpuInstance.InstanceMask = 0xFF;
		// DXR specifies winding in a left-handed object space. Its default
		// therefore matches glTF's right-handed CCW front face. Instance
		// transforms preserve this classification, even when mirrored.
		stGpuInstance.Flags = D3D12_RAYTRACING_INSTANCE_FLAG_NONE;
		if (stMesh.arrMaterials[stPrimitive.nMaterial].bDoubleSided)
		{
			stGpuInstance.Flags |= D3D12_RAYTRACING_INSTANCE_FLAG_TRIANGLE_CULL_DISABLE;
		}
		stCandidate.arrInstances.push_back(stGpuInstance);
		stCandidate.arrIdentities.push_back({ stInstance.nEntityId, stInstance.nAsset, stInstance.nPrimitive, stInstance.nNode, nGeometry });
		arrDraws.push_back(arrGeometryDraws[nGeometry]);
	}
	stCandidate.nVertexBytes = std::max<std::uint64_t>(sizeof(MeshVertex), arrVertices.size() * sizeof(MeshVertex));
	stCandidate.nIndexBytes = std::max<std::uint64_t>(4, arrIndices.size() * sizeof(std::uint32_t));
	stCandidate.nIndexUploadOffset = Align(stCandidate.nVertexBytes);
	const std::uint64_t nGeometryUploadBytes = stCandidate.nIndexUploadOffset + stCandidate.nIndexBytes;
	const std::uint64_t nDrawBytes = std::max<std::uint64_t>(sizeof(RayTracingDraw), arrDraws.size() * sizeof(RayTracingDraw));
	const std::uint64_t nMaterialBytes = std::max<std::uint64_t>(sizeof(RayTracingMaterial), arrMaterials.size() * sizeof(RayTracingMaterial));
	const std::uint64_t nInstanceBytes = std::max<std::uint64_t>(sizeof(D3D12_RAYTRACING_INSTANCE_DESC), stCandidate.arrInstances.size() * sizeof(D3D12_RAYTRACING_INSTANCE_DESC));
	D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_INPUTS stTlasInputs{};
	stTlasInputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL;
	stTlasInputs.Flags = BUILD_FLAGS | D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_ALLOW_UPDATE;
	stTlasInputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
	stTlasInputs.NumDescs = static_cast<UINT>(stCandidate.arrInstances.size());
	stTlasInputs.InstanceDescs = stCandidate.arrInstances.empty() ? 0 : AS_ALIGNMENT;
	D3D12_RAYTRACING_ACCELERATION_STRUCTURE_PREBUILD_INFO stTlasInfo{};
	pDevice->GetRaytracingAccelerationStructurePrebuildInfo(&stTlasInputs, &stTlasInfo);
	const std::uint64_t nTlasBytes = Align(std::max<std::uint64_t>(AS_ALIGNMENT, stTlasInfo.ResultDataMaxSizeInBytes));
	const std::uint64_t nTlasScratchBytes = Align(std::max<std::uint64_t>(AS_ALIGNMENT, std::max(stTlasInfo.ScratchDataSizeInBytes, stTlasInfo.UpdateScratchDataSizeInBytes)));
	RayTracingMemory &stPlannedMemory = stCandidate.stMemory;
	if (!Account(pDevice, stCandidate.nVertexBytes, D3D12_RESOURCE_FLAG_NONE, stLimits.nMaxResidentBytes, stPlannedMemory.nResidentBytes) || !Account(pDevice, stCandidate.nIndexBytes, D3D12_RESOURCE_FLAG_NONE, stLimits.nMaxResidentBytes, stPlannedMemory.nResidentBytes) || (nBlasBytes > 0 && !Account(pDevice, nBlasBytes, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, stLimits.nMaxResidentBytes, stPlannedMemory.nResidentBytes)) || (nScratchBytes > 0 && !Account(pDevice, nScratchBytes, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, stLimits.nMaxScratchBytes, stPlannedMemory.nScratchBytes, &stCandidate.nBlasScratchAllocation)) || !Account(pDevice, nGeometryUploadBytes, D3D12_RESOURCE_FLAG_NONE, stLimits.nMaxUploadBytes, stPlannedMemory.nUploadBytes, &stCandidate.nGeometryUploadAllocation) || !Account(pDevice, nDrawBytes, D3D12_RESOURCE_FLAG_NONE, stLimits.nMaxUploadBytes, stPlannedMemory.nUploadBytes) || !Account(pDevice, nMaterialBytes, D3D12_RESOURCE_FLAG_NONE, stLimits.nMaxUploadBytes, stPlannedMemory.nUploadBytes))
	{
		return Error(out_arrDiagnostics, "Geometry and mapping allocation budgets are exhausted.");
	}
	for (std::uint32_t nFrame = 0; nFrame < RAY_TRACING_FRAME_COUNT; ++nFrame)
	{
		if (!Account(pDevice, nTlasBytes, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, stLimits.nMaxResidentBytes, stPlannedMemory.nResidentBytes) || !Account(pDevice, nTlasScratchBytes, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, stLimits.nMaxScratchBytes, stPlannedMemory.nScratchBytes) || !Account(pDevice, nInstanceBytes, D3D12_RESOURCE_FLAG_NONE, stLimits.nMaxUploadBytes, stPlannedMemory.nUploadBytes))
		{
			return Error(out_arrDiagnostics, "TLAS frame allocations exceed the explicit budget.");
		}
	}
	// No GPU allocations or externally visible changes precede the complete plan.
	if (!CreateBuffer(pDevice, stCandidate.nVertexBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_NONE, D3D12_RESOURCE_STATE_COMMON, stCandidate.stVertices) || !CreateBuffer(pDevice, stCandidate.nIndexBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_NONE, D3D12_RESOURCE_STATE_COMMON, stCandidate.stIndices) || !CreateBuffer(pDevice, nGeometryUploadBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, D3D12_RESOURCE_STATE_GENERIC_READ, stCandidate.stGeometryUpload) || !CreateBuffer(pDevice, nDrawBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, D3D12_RESOURCE_STATE_GENERIC_READ, stCandidate.stDraws) || !CreateBuffer(pDevice, nMaterialBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, D3D12_RESOURCE_STATE_GENERIC_READ, stCandidate.stMaterials) || (nBlasBytes > 0 && !CreateBuffer(pDevice, nBlasBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_RAYTRACING_ACCELERATION_STRUCTURE, stCandidate.stBlas)) || (nScratchBytes > 0 && !CreateBuffer(pDevice, nScratchBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COMMON, stCandidate.stBlasScratch)))
	{
		return Error(out_arrDiagnostics, "D3D12 geometry allocation failed.");
	}
	std::vector<std::uint8_t> arrUpload(static_cast<std::size_t>(nGeometryUploadBytes));
	if (!arrVertices.empty())
	{
		std::memcpy(arrUpload.data(), arrVertices.data(), arrVertices.size() * sizeof(MeshVertex));
		std::memcpy(arrUpload.data() + stCandidate.nIndexUploadOffset, arrIndices.data(), arrIndices.size() * sizeof(std::uint32_t));
	}
	if (!Fill(stCandidate.stGeometryUpload.Get(), arrUpload.data(), arrUpload.size()) || !Fill(stCandidate.stDraws.Get(), arrDraws.data(), arrDraws.size() * sizeof(RayTracingDraw)) || !Fill(stCandidate.stMaterials.Get(), arrMaterials.data(), arrMaterials.size() * sizeof(RayTracingMaterial)))
	{
		return Error(out_arrDiagnostics, "Mapping ray tracing upload resources failed.");
	}
	for (std::uint32_t nGeometry = 0; nGeometry < stCandidate.arrGeometry.size(); ++nGeometry)
	{
		D3D12_RAYTRACING_GEOMETRY_TRIANGLES_DESC &stTriangles = stCandidate.arrGeometry[nGeometry].stDescription.Triangles;
		stTriangles.VertexBuffer.StartAddress = stCandidate.stVertices->GetGPUVirtualAddress() + static_cast<std::uint64_t>(arrGeometryDraws[nGeometry].nBaseVertex) * sizeof(MeshVertex);
		stTriangles.IndexBuffer = stCandidate.stIndices->GetGPUVirtualAddress() + static_cast<std::uint64_t>(arrGeometryDraws[nGeometry].nFirstIndex) * sizeof(std::uint32_t);
	}
	for (std::size_t nInstance = 0; nInstance < stCandidate.arrInstances.size(); ++nInstance)
	{
		stCandidate.arrInstances[nInstance].AccelerationStructure = stCandidate.stBlas->GetGPUVirtualAddress() + stCandidate.arrGeometry[stCandidate.arrIdentities[nInstance].nGeometry].nResultOffset;
	}
	for (Frame &stFrame : stCandidate.arrFrames)
	{
		if (!CreateBuffer(pDevice, nTlasBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_RAYTRACING_ACCELERATION_STRUCTURE, stFrame.stTlas) || !CreateBuffer(pDevice, nTlasScratchBytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COMMON, stFrame.stScratch) || !CreateBuffer(pDevice, nInstanceBytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_FLAG_NONE, D3D12_RESOURCE_STATE_GENERIC_READ, stFrame.stInstances))
		{
			return Error(out_arrDiagnostics, "D3D12 TLAS frame allocation failed.");
		}
	}
	stPlannedMemory.nGeometryPayloadBytes = arrVertices.size() * sizeof(MeshVertex) + arrIndices.size() * sizeof(std::uint32_t);
	stPlannedMemory.nAccelerationPayloadBytes = nBlasBytes + RAY_TRACING_FRAME_COUNT * nTlasBytes;
	stCandidate.nOwnerThread = GetCurrentThreadId();
	stCandidate.bPrepared = true;
	*this = std::move(stCandidate);
	return true;
}

bool RayTracingScene::RecordBuildOrUpdate(std::uint32_t nFrame, ID3D12GraphicsCommandList4 *pList, const std::vector<std::array<double, 16>> &arrWorlds, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || !bPrepared || pList == nullptr || pList->GetType() != D3D12_COMMAND_LIST_TYPE_DIRECT || nFrame >= RAY_TRACING_FRAME_COUNT || nPendingFrame != NO_RAY_TRACING_FRAME || nCompletedFence == UINT64_MAX || nCompletedFence < arrFrames[nFrame].nFence || arrWorlds.size() != arrInstances.size())
	{
		return Error(out_arrDiagnostics, "Recording requires an idle retired frame slot on the owner graphics queue.");
	}
	std::vector<D3D12_RAYTRACING_INSTANCE_DESC> arrCandidate = arrInstances;
	for (std::size_t nInstance = 0; nInstance < arrWorlds.size(); ++nInstance)
	{
		if (!WorldTransform(arrWorlds[nInstance], arrCandidate[nInstance]))
		{
			return Error(out_arrDiagnostics, "Updated instance transforms must be finite binary32 and affine.");
		}
	}
	Frame &stFrame = arrFrames[nFrame];
	if (!Fill(stFrame.stInstances.Get(), arrCandidate.data(), arrCandidate.size() * sizeof(D3D12_RAYTRACING_INSTANCE_DESC)))
	{
		return Error(out_arrDiagnostics, "Mapping the retired instance upload failed.");
	}
	if (!bStaticBuilt)
	{
		Transition(pList, stVertices.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST);
		Transition(pList, stIndices.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST);
		pList->CopyBufferRegion(stVertices.Get(), 0, stGeometryUpload.Get(), 0, nVertexBytes);
		pList->CopyBufferRegion(stIndices.Get(), 0, stGeometryUpload.Get(), nIndexUploadOffset, nIndexBytes);
		D3D12_RESOURCE_BARRIER arrBarriers[2]{};
		for (std::uint32_t nIndex = 0; nIndex < 2; ++nIndex)
		{
			arrBarriers[nIndex].Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
			arrBarriers[nIndex].Transition.pResource = nIndex == 0 ? stVertices.Get() : stIndices.Get();
			arrBarriers[nIndex].Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
			arrBarriers[nIndex].Transition.StateAfter = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
			arrBarriers[nIndex].Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
		}
		pList->ResourceBarrier(2, arrBarriers);
		if (stBlasScratch.Get() != nullptr)
		{
			Transition(pList, stBlasScratch.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
		}
		for (const Geometry &stGeometry : arrGeometry)
		{
			D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_DESC stBuild{};
			stBuild.Inputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL;
			stBuild.Inputs.Flags = BUILD_FLAGS;
			stBuild.Inputs.NumDescs = 1;
			stBuild.Inputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
			stBuild.Inputs.pGeometryDescs = &stGeometry.stDescription;
			stBuild.DestAccelerationStructureData = stBlas->GetGPUVirtualAddress() + stGeometry.nResultOffset;
			stBuild.ScratchAccelerationStructureData = stBlasScratch->GetGPUVirtualAddress();
			pList->BuildRaytracingAccelerationStructure(&stBuild, 0, nullptr);
			UavBarrier(pList, stBlas.Get());
			UavBarrier(pList, stBlasScratch.Get());
		}
	}
	// Scratch is a buffer and decays to COMMON across ExecuteCommandLists.
	Transition(pList, stFrame.stScratch.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
	D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_DESC stBuild{};
	stBuild.Inputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL;
	stBuild.Inputs.Flags = BUILD_FLAGS | D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_ALLOW_UPDATE;
	stBuild.Inputs.NumDescs = static_cast<UINT>(arrCandidate.size());
	stBuild.Inputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
	stBuild.Inputs.InstanceDescs = arrCandidate.empty() ? 0 : stFrame.stInstances->GetGPUVirtualAddress();
	stBuild.DestAccelerationStructureData = stFrame.stTlas->GetGPUVirtualAddress();
	stBuild.ScratchAccelerationStructureData = stFrame.stScratch->GetGPUVirtualAddress();
	if (stFrame.bBuilt)
	{
		stBuild.Inputs.Flags |= D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_PERFORM_UPDATE;
		stBuild.SourceAccelerationStructureData = stBuild.DestAccelerationStructureData;
	}
	pList->BuildRaytracingAccelerationStructure(&stBuild, 0, nullptr);
	UavBarrier(pList, stFrame.stTlas.Get());
	nPendingFrame = nFrame;
	bPendingStaticBuild = !bStaticBuilt;
	return true;
}

bool RayTracingScene::CommitSubmission(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nFrame >= RAY_TRACING_FRAME_COUNT || nPendingFrame != nFrame || nFence == 0 || nFence == UINT64_MAX || nFence < nLatestFence)
	{
		return Error(out_arrDiagnostics, "Commit needs the recorded frame and a monotonic graphics fence.");
	}
	arrFrames[nFrame].bBuilt = true;
	arrFrames[nFrame].nFence = nFence;
	nLatestFence = nFence;
	if (bPendingStaticBuild)
	{
		bStaticBuilt = true;
		nStaticBuildFence = nFence;
	}
	nPendingFrame = NO_RAY_TRACING_FRAME;
	bPendingStaticBuild = false;
	return true;
}

bool RayTracingScene::CancelRecorded(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nPendingFrame != nFrame || nFrame >= RAY_TRACING_FRAME_COUNT)
	{
		return Error(out_arrDiagnostics, "Only the current unsubmitted recording can be cancelled.");
	}
	nPendingFrame = NO_RAY_TRACING_FRAME;
	bPendingStaticBuild = false;
	return true;
}

bool RayTracingScene::MarkUsed(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nFrame >= RAY_TRACING_FRAME_COUNT || !arrFrames[nFrame].bBuilt || nPendingFrame != NO_RAY_TRACING_FRAME || nFence == 0 || nFence == UINT64_MAX || nFence < nLatestFence)
	{
		return Error(out_arrDiagnostics, "Usage requires a built TLAS and a monotonic graphics fence.");
	}
	arrFrames[nFrame].nFence = nFence;
	nLatestFence = nFence;
	return true;
}

bool RayTracingScene::Retire(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || nCompletedFence == UINT64_MAX)
	{
		return Error(out_arrDiagnostics, "Retirement requires a valid completed graphics fence on the owner thread.");
	}
	if (bStaticBuilt && nCompletedFence >= nStaticBuildFence)
	{
		if (stGeometryUpload.Get() != nullptr)
		{
			stGeometryUpload.Reset();
			stMemory.nUploadBytes -= nGeometryUploadAllocation;
			stMemory.nRetiredUploadBytes += nGeometryUploadAllocation;
		}
		if (stBlasScratch.Get() != nullptr)
		{
			stBlasScratch.Reset();
			stMemory.nScratchBytes -= nBlasScratchAllocation;
			stMemory.nRetiredScratchBytes += nBlasScratchAllocation;
		}
	}
	return true;
}

bool RayTracingScene::Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!IsOwner() || !CanRelease(nCompletedFence))
	{
		return Error(out_arrDiagnostics, "Resources are still recorded or referenced by an unretired graphics fence.");
	}
	*this = RayTracingScene{};
	return true;
}

D3D12_GPU_VIRTUAL_ADDRESS RayTracingScene::TlasAddress(std::uint32_t nFrame) const noexcept
{
	return nFrame < RAY_TRACING_FRAME_COUNT && (arrFrames[nFrame].bBuilt || nPendingFrame == nFrame) ? arrFrames[nFrame].stTlas->GetGPUVirtualAddress() : 0;
}
ID3D12Resource *RayTracingScene::TlasResource(std::uint32_t nFrame) const noexcept
{
	return bPrepared && nFrame < RAY_TRACING_FRAME_COUNT ? arrFrames[nFrame].stTlas.Get() : nullptr;
}
ID3D12Resource *RayTracingScene::VertexBuffer() const noexcept
{
	return stVertices.Get();
}
ID3D12Resource *RayTracingScene::IndexBuffer() const noexcept
{
	return stIndices.Get();
}
ID3D12Resource *RayTracingScene::DrawBuffer() const noexcept
{
	return stDraws.Get();
}
ID3D12Resource *RayTracingScene::MaterialBuffer() const noexcept
{
	return stMaterials.Get();
}
const std::vector<RayTracingIdentity> &RayTracingScene::Identities() const noexcept
{
	return arrIdentities;
}
const std::vector<RayTracingTextureBinding> &RayTracingScene::TextureBindings() const noexcept
{
	return arrTextures;
}
const std::vector<RayTracingSourceMaterial> &RayTracingScene::SourceMaterials() const noexcept
{
	return arrSourceMaterials;
}
const RayTracingMemory &RayTracingScene::Memory() const noexcept
{
	return stMemory;
}

} // namespace EngineNext::Rendering
