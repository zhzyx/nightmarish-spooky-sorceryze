/**************************************************************************/
/*  VisualRuntime.cpp                                                     */
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

#include "engine_next/include/EngineNext/Rendering/VisualRuntime.h"
#include "engine_next/include/EngineNext/Rendering/FrameGraph.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"
#include "engine_next/Platform/Windows/Window.h"
#include "engine_next/Client/ClientSession.h"
#include "engine_next/include/EngineNext/Runtime/Clock.h"
#include "engine_next/include/EngineNext/Runtime/RuntimeConfig.h"
#include "engine_next/include/EngineNext/Gameplay/Vector3.h"
#include "engine_next/include/EngineNext/Assets/AssetPackage.h"
#include "engine_next/include/EngineNext/Assets/SceneDocument.h"
#include "engine_next/Rendering/Cook/ImageDecoder.h"
#include "engine_next/Rendering/Cook/EnvironmentLighting.h"
#include "engine_next/Rendering/Cook/EnvironmentImportance.h"
#include "engine_next/Rendering/Cook/GpuPackage.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"
#include "engine_next/include/EngineNext/Rendering/TextureData.h"
#include "engine_next/include/EngineNext/Rendering/CameraMatrices.h"
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"
#include "engine_next/Rendering/RenderPipeline.h"
#include "engine_next/include/EngineNext/Rendering/ShadowData.h"
#include "engine_next/Rendering/ShadowBounds.h"
#include "engine_next/include/EngineNext/Rendering/LocalShadowData.h"
#include "engine_next/include/EngineNext/Rendering/TemporalState.h"
#include "engine_next/include/EngineNext/Rendering/LightTimeline.h"
#include "engine_next/include/EngineNext/Rendering/VolumeGrid.h"
#include "engine_next/include/EngineNext/Rendering/ParticleState.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <d3d12.h>
#include <d3d12sdklayers.h>
#include <dxgi1_6.h>
#include <pix.h>

#include <array>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::uint32_t FRAME_COUNT = 3;
constexpr std::uint32_t FRAME_VIEW_COUNT = 152;
constexpr std::uint32_t VOLUME_MEDIUM_VIEW = 120;
constexpr std::uint32_t VOLUME_EMISSION_VIEW = 122;
constexpr std::uint32_t VOLUME_SOURCE_VIEW = 124;
constexpr std::uint32_t VOLUME_INTEGRAL_VIEW = 126;
constexpr std::uint32_t VOLUME_HISTORY_READ_VIEW = 128;
constexpr std::uint32_t VOLUME_HISTORY_WRITE_VIEW = 130;
constexpr std::uint32_t VOLUME_GLOBAL_VIEW = 132;
constexpr std::uint64_t VOLUME_GLOBAL_BYTE_OFFSET = 240;
constexpr std::uint64_t VOLUME_LOCAL_BYTE_OFFSET = 512;
constexpr std::uint32_t VOLUME_LOCAL_VIEW = 133;
constexpr std::uint32_t FORWARD_HDR_VIEW = 134;
constexpr std::uint32_t REACTIVE_MASK_VIEW = 136;
constexpr std::uint32_t MATERIAL_PARAMETERS_VIEW = 138;
constexpr std::uint32_t REFLECTION_MIP_COUNT = 6;
constexpr std::uint32_t REFLECTION_MIP_VIEW = 104;
constexpr std::uint32_t REFLECTION_ENV_VIEW = 114;
constexpr std::uint32_t REFLECTION_RESULT_VIEW = 115;
constexpr std::uint32_t REFLECTION_OUTPUT_VIEW = 117;
constexpr std::uint32_t HISTORY_VIEW_START = FRAME_COUNT * FRAME_VIEW_COUNT;
constexpr std::uint32_t HISTORY_VIEW_COUNT = 16;
constexpr std::uint32_t MAX_LOCAL_SHADOW_VIEWS = 28;
constexpr std::uint32_t MATERIAL_TEXTURE_COUNT = 5;
constexpr std::uint32_t MAX_MATERIALS = D3D12_MAX_SHADER_VISIBLE_SAMPLER_HEAP_SIZE / MATERIAL_TEXTURE_COUNT;
constexpr std::uint32_t MATERIAL_VIEW_START = HISTORY_VIEW_START + HISTORY_VIEW_COUNT;
constexpr std::uint32_t ENVIRONMENT_VIEW_START = MATERIAL_VIEW_START + MAX_MATERIALS * MATERIAL_TEXTURE_COUNT;
constexpr std::uint32_t ENVIRONMENT_ALIAS_VIEW = ENVIRONMENT_VIEW_START + 3;
constexpr std::uint64_t MAX_TEXTURE_UPLOAD_BYTES = 512ULL * 1024ULL * 1024ULL;
constexpr DXGI_FORMAT COLOR_FORMAT = DXGI_FORMAT_R8G8B8A8_UNORM;
constexpr DXGI_FORMAT HDR_FORMAT = DXGI_FORMAT_R16G16B16A16_FLOAT;
constexpr std::uint64_t CONSTANT_BUFFER_ALIGNMENT = 256;
constexpr std::size_t MAX_TIMING_SAMPLES = 65536;

// COM references stay in the backend and are retired only after queue fences.
template <typename Interface>
class ComOwner final
{
public:
	ComOwner() = default;
	~ComOwner()
	{
		Reset();
	}
	ComOwner(const ComOwner &) = delete;
	ComOwner &operator=(const ComOwner &) = delete;
	ComOwner(ComOwner &&stOther) noexcept : pValue(stOther.pValue)
	{
		stOther.pValue = nullptr;
	}
	ComOwner &operator=(ComOwner &&stOther) noexcept
	{
		if (this != &stOther)
		{
			Reset();
			pValue = stOther.pValue;
			stOther.pValue = nullptr;
		}
		return *this;
	}
	Interface *Get() const noexcept
	{
		return pValue;
	}
	Interface **Put() noexcept
	{
		Reset();
		return &pValue;
	}
	Interface *operator->() const noexcept
	{
		return pValue;
	}
	void Reset() noexcept
	{
		if (pValue != nullptr)
		{
			pValue->Release();
			pValue = nullptr;
		}
	}

private:
	Interface *pValue = nullptr;
};

class EventOwner final
{
public:
	~EventOwner()
	{
		if (hValue != nullptr)
		{
			CloseHandle(hValue);
		}
	}
	HANDLE hValue = nullptr;
};

struct GpuQueue
{
	ComOwner<ID3D12CommandQueue> stQueue;
	ComOwner<ID3D12Fence> stFence;
	EventOwner stEvent;
	std::uint64_t nNextFence = 1;
	std::uint64_t nFrequency = 0;

	bool Initialize(ID3D12Device *pDevice, D3D12_COMMAND_LIST_TYPE eType)
	{
		D3D12_COMMAND_QUEUE_DESC stDescription{};
		stDescription.Type = eType;
		if (FAILED(pDevice->CreateCommandQueue(&stDescription, IID_PPV_ARGS(stQueue.Put()))) ||
			FAILED(pDevice->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(stFence.Put()))))
		{
			return false;
		}
		stEvent.hValue = CreateEventW(nullptr, FALSE, FALSE, nullptr);
		return stEvent.hValue != nullptr && SUCCEEDED(stQueue->GetTimestampFrequency(&nFrequency));
	}

	bool Wait(std::uint64_t nValue)
	{
		if (stFence.Get() == nullptr || stEvent.hValue == nullptr)
		{
			return false;
		}
		const std::uint64_t nCompleted = stFence->GetCompletedValue();
		if (nCompleted == UINT64_MAX)
		{
			return false;
		}
		if (nCompleted >= nValue)
		{
			return true;
		}
		if (FAILED(stFence->SetEventOnCompletion(nValue, stEvent.hValue)))
		{
			return false;
		}
		if (WaitForSingleObject(stEvent.hValue, 30000) != WAIT_OBJECT_0)
		{
			return false;
		}
		const std::uint64_t nAfterWait = stFence->GetCompletedValue();
		return nAfterWait != UINT64_MAX && nAfterWait >= nValue;
	}

	bool Signal(std::uint64_t &out_nValue)
	{
		if (stQueue.Get() == nullptr || stFence.Get() == nullptr || nNextFence == UINT64_MAX)
		{
			return false;
		}
		out_nValue = nNextFence++;
		return SUCCEEDED(stQueue->Signal(stFence.Get(), out_nValue));
	}

	bool Flush()
	{
		if (stQueue.Get() == nullptr || stFence.Get() == nullptr || stEvent.hValue == nullptr)
		{
			return false;
		}
		std::uint64_t nValue = 0;
		return Signal(nValue) && Wait(nValue);
	}
};

struct Vertex
{
	float arrPosition[3];
	float arrNormal[3];
	float arrColor[3];
};

struct FrameContext
{
	ComOwner<ID3D12CommandAllocator> stGraphicsAllocator;
	ComOwner<ID3D12CommandAllocator> stComputeAllocator;
	ComOwner<ID3D12GraphicsCommandList> stGraphicsList;
	ComOwner<ID3D12GraphicsCommandList> stComputeList;
	ComOwner<ID3D12Resource> stColor;
	ComOwner<ID3D12Resource> stHdr;
	ComOwner<ID3D12Resource> stEnvironmentSpecular;
	ComOwner<ID3D12Resource> stReflection;
	ComOwner<ID3D12Resource> stReflectedHdr;
	std::array<ComOwner<ID3D12Resource>, 4> arrVolume;
	ComOwner<ID3D12Resource> stVolumeParameters;
	ComOwner<ID3D12Resource> stForwardHdr;
	ComOwner<ID3D12Resource> stReactiveMask;
	std::array<ComOwner<ID3D12Resource>, REFLECTION_MIP_COUNT - 1> arrReflectionMips;
	ComOwner<ID3D12Resource> stDepth;
	ComOwner<ID3D12Resource> stTint;
	std::array<ComOwner<ID3D12Resource>, 4> arrGbuffer;
	std::array<ComOwner<ID3D12Resource>, 2> arrMaterialBuffers;
	ComOwner<ID3D12Resource> stMotion;
	ComOwner<ID3D12Resource> stObjectId;
	ComOwner<ID3D12Resource> stHistogram;
	std::array<ComOwner<ID3D12Resource>, 6> arrBloomDown;
	std::array<ComOwner<ID3D12Resource>, 6> arrBloomUp;
	ComOwner<ID3D12Resource> stPostReadback;
	ComOwner<ID3D12Resource> stQueries;
	ComOwner<ID3D12Resource> stConstants;
	ComOwner<ID3D12Resource> stDirectionalShadow;
	ComOwner<ID3D12Resource> stLocalShadow;
	ComOwner<ID3D12Resource> stShadowConstants;
	std::uint64_t nGraphicsFence = 0;
	std::uint64_t nComputeFence = 0;
	std::uint32_t nTimingFrame = 0;
	bool bTimingPending = false;
};

struct FrameTiming
{
	std::uint32_t nFrame = 0;
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint64_t nGraphicsFence = 0;
	std::uint64_t nComputeFence = 0;
	std::uint64_t nTemporalEpoch = 0;
	std::uint32_t nTemporalSample = 0;
	std::uint32_t nTemporalRead = 0;
	std::array<double, 2> arrTemporalJitter{};
	std::array<float, 4> arrExposure{};
	std::uint32_t nMeterFinite = 0;
	std::uint32_t nMeterInvalid = 0;
	bool bPostReady = false;
	double dLightingSeconds = 0;
	double dDirectionalIlluminance = 0;
	bool bTemporalHistoryValid = false;
	bool bVolumeHistoryValid = false;
	std::uint32_t nVolumeHistoryRead = 0;
	std::uint32_t nParticles = 0;
	double dCpuMsec = 0.0;
	double dGraphicsMsec = 0.0;
	double dComputeMsec = 0.0;
	std::vector<double> arrPassMsec;
	bool bGpuReady = false;
};

struct GpuPrimitive
{
	std::uint32_t nFirstIndex = 0;
	std::uint32_t nIndexCount = 0;
	std::int32_t nBaseVertex = 0;
	std::uint32_t nMaterial = 0;
};

struct GpuDraw
{
	GpuPrimitive stPrimitive;
	std::array<double, 16> arrTransform{};
	std::array<float, 16> arrNormal{};
	std::uint64_t nEntityId = 0;
	std::uint64_t nSimulationEntityId = 0;
	std::array<double, 3> arrSimulationOrigin{};
	std::array<double, 9> arrSimulationParent{ 1, 0, 0, 0, 1, 0, 0, 0, 1 };
	bool bMirrored = false;
	std::uint32_t nSourceAsset = 0;
	std::uint32_t nSourcePrimitive = 0;
	std::uint32_t nSourceNode = 0;
};

struct GpuMaterial
{
	MaterialData stData;
	std::uint32_t nViewStart = 0;
	std::array<float, 4> arrLobes{ 0, 0.1F, 0, 0 };
};

struct DrawConstants
{
	std::array<float, 16> arrWorld{};
	std::array<float, 16> arrNormal{};
	std::array<float, 4> arrBaseColor{};
	std::array<float, 4> arrEmissiveMetallic{};
	std::array<float, 4> arrSurface{};
	std::array<float, 4> arrFlags{};
	std::array<float, 16> arrPreviousWorld{};
	std::array<std::uint32_t, 4> arrTemporal{};
	std::array<float, 4> arrMaterialLobes{};
};

struct LocalLightConstants
{
	std::array<float, 4> arrPositionRange{};
	std::array<float, 4> arrColorIntensity{};
	std::array<float, 4> arrDirectionType{};
	std::array<float, 4> arrConeShadow{};
	std::array<float, 4> arrShadowParameters{};
};

struct FrameConstants
{
	std::array<float, 16> arrViewProjection{};
	std::array<float, 16> arrInverseViewProjection{};
	std::array<float, 4> arrCamera{};
	std::array<float, 4> arrLighting{};
	std::array<float, 16> arrView{};
	std::array<std::array<float, 16>, 4> arrShadowViewProjection{};
	std::array<float, 4> arrCascadeSplits{};
	std::array<float, 4> arrLightDirection{};
	std::array<float, 4> arrLightColor{};
	std::array<float, 4> arrShadowParameters{};
	std::array<std::array<float, 16>, MAX_LOCAL_SHADOW_VIEWS> arrLocalShadowMatrices{};
	std::array<LocalLightConstants, 8> arrLocalLights{};
	std::array<float, 4> arrLocalCounts{};
	std::array<float, 16> arrUnjitteredViewProjection{};
	std::array<float, 16> arrPreviousViewProjection{};
};

struct VolumeHistoryConstants
{
	std::array<float, 16> arrPreviousView{};
	std::array<float, 16> arrPreviousViewProjection{};
	std::array<float, 4> arrPreviousGrid{};
	std::array<float, 4> arrPreviousDepth{};
	std::array<float, 4> arrSettings{};
};

struct GlobalVolumeConstants
{
	std::array<float, 4> arrDensityHeightFalloff{};
	std::array<float, 4> arrAlbedo{};
	std::array<float, 4> arrEmission{};
};

struct LocalVolumeConstants
{
	std::array<float, 4> arrCenterShape{};
	std::array<float, 4> arrExtentEdge{};
	std::array<float, 4> arrAlbedoDensity{};
	std::array<float, 4> arrEmission{};
};

static_assert(sizeof(VolumeHistoryConstants) == 176);
static_assert(sizeof(GlobalVolumeConstants) == 48);
static_assert(sizeof(LocalVolumeConstants) == 64);
static_assert(REACTIVE_MASK_VIEW < FRAME_VIEW_COUNT);
static_assert(MATERIAL_PARAMETERS_VIEW + 1 < FRAME_VIEW_COUNT);

static_assert(sizeof(DrawConstants) == 288);
static_assert(offsetof(DrawConstants, arrMaterialLobes) == 272);
static_assert(offsetof(DrawConstants, arrPreviousWorld) == 192);
static_assert(offsetof(DrawConstants, arrTemporal) == 256);
static_assert(sizeof(LocalLightConstants) == 80);
static_assert(sizeof(FrameConstants) == 3120);
static_assert(REFLECTION_OUTPUT_VIEW + 2 <= FRAME_VIEW_COUNT);
static_assert(offsetof(FrameConstants, arrUnjitteredViewProjection) == 2992);
static_assert(offsetof(FrameConstants, arrPreviousViewProjection) == 3056);
static_assert(offsetof(FrameConstants, arrLocalShadowMatrices) == 544);
static_assert(offsetof(FrameConstants, arrLocalLights) == 2336);
static_assert(offsetof(FrameConstants, arrLocalCounts) == 2976);
static_assert(offsetof(DrawConstants, arrFlags) == 176);
static_assert(offsetof(FrameConstants, arrCamera) == 128);
static_assert(offsetof(FrameConstants, arrLighting) == 144);
static_assert(offsetof(FrameConstants, arrView) == 160);
static_assert(offsetof(FrameConstants, arrShadowViewProjection) == 224);
static_assert(offsetof(FrameConstants, arrCascadeSplits) == 480);
static_assert(offsetof(FrameConstants, arrShadowParameters) == 528);
constexpr std::uint64_t DRAW_CONSTANT_BYTES = (sizeof(DrawConstants) + CONSTANT_BUFFER_ALIGNMENT - 1) & ~(CONSTANT_BUFFER_ALIGNMENT - 1);
constexpr std::uint64_t FRAME_CONSTANT_BYTES = (sizeof(FrameConstants) + CONSTANT_BUFFER_ALIGNMENT - 1) & ~(CONSTANT_BUFFER_ALIGNMENT - 1);

D3D12_HEAP_PROPERTIES HeapProperties(D3D12_HEAP_TYPE eType)
{
	D3D12_HEAP_PROPERTIES stHeap{};
	stHeap.Type = eType;
	stHeap.CreationNodeMask = 1;
	stHeap.VisibleNodeMask = 1;
	return stHeap;
}

D3D12_RESOURCE_DESC BufferDescription(std::uint64_t nSize)
{
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
	stDescription.Width = nSize;
	stDescription.Height = 1;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = 1;
	stDescription.SampleDesc.Count = 1;
	stDescription.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
	return stDescription;
}

std::vector<std::uint8_t> ReadShader(const std::string &strDirectory, const char *pName)
{
	std::ifstream stFile(std::filesystem::u8path(strDirectory) / pName, std::ios::binary | std::ios::ate);
	if (!stFile)
	{
		return {};
	}
	const std::streamoff nSize = stFile.tellg();
	if (nSize <= 0 || nSize > 16 * 1024 * 1024)
	{
		return {};
	}
	std::vector<std::uint8_t> arrBytes(static_cast<std::size_t>(nSize));
	stFile.seekg(0);
	stFile.read(reinterpret_cast<char *>(arrBytes.data()), nSize);
	return stFile ? arrBytes : std::vector<std::uint8_t>{};
}

D3D12_RESOURCE_STATES NativeState(ResourceState eState)
{
	switch (eState)
	{
		case ResourceState::CopySource:
			return D3D12_RESOURCE_STATE_COPY_SOURCE;
		case ResourceState::CopyDestination:
			return D3D12_RESOURCE_STATE_COPY_DEST;
		case ResourceState::RenderTarget:
			return D3D12_RESOURCE_STATE_RENDER_TARGET;
		case ResourceState::DepthWrite:
			return D3D12_RESOURCE_STATE_DEPTH_WRITE;
		case ResourceState::DepthRead:
			return D3D12_RESOURCE_STATE_DEPTH_READ | D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE | D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
		case ResourceState::ShaderRead:
			return D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE | D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
		case ResourceState::NonPixelShaderRead:
			return D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
		case ResourceState::UnorderedAccess:
			return D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
		default:
			return D3D12_RESOURCE_STATE_COMMON;
	}
}

const char *QueueName(QueueType eQueue)
{
	switch (eQueue)
	{
		case QueueType::Graphics:
			return "graphics";
		case QueueType::Compute:
			return "compute";
		case QueueType::Copy:
			return "copy";
	}
	return "unknown";
}

const char *StateName(ResourceState eState)
{
	switch (eState)
	{
		case ResourceState::Undefined:
			return "undefined";
		case ResourceState::Common:
			return "common";
		case ResourceState::CopySource:
			return "copy_source";
		case ResourceState::CopyDestination:
			return "copy_destination";
		case ResourceState::RenderTarget:
			return "render_target";
		case ResourceState::DepthWrite:
			return "depth_write";
		case ResourceState::DepthRead:
			return "depth_read";
		case ResourceState::ShaderRead:
			return "shader_read";
		case ResourceState::NonPixelShaderRead:
			return "non_pixel_shader_read";
		case ResourceState::UnorderedAccess:
			return "unordered_access";
		case ResourceState::Present:
			return "present";
	}
	return "unknown";
}

Serialization::JsonValue DescribeBarriers(const std::vector<ResourceBarrier> &arrBarriers)
{
	using Serialization::JsonValue;
	JsonValue::List arrResult;
	for (const ResourceBarrier &stBarrier : arrBarriers)
	{
		JsonValue::Object mapBarrier;
		mapBarrier["kind"] = JsonValue(stBarrier.eKind == BarrierKind::Transition ? "transition" : "uav");
		mapBarrier["resource_id"] = JsonValue(static_cast<std::int64_t>(stBarrier.nResource));
		mapBarrier["subresource"] = JsonValue(static_cast<std::int64_t>(stBarrier.nSubresource));
		mapBarrier["before"] = JsonValue(StateName(stBarrier.eBefore));
		mapBarrier["after"] = JsonValue(StateName(stBarrier.eAfter));
		arrResult.emplace_back(std::move(mapBarrier));
	}
	return JsonValue(std::move(arrResult));
}

std::string DebugName(const char *pName, const wchar_t *pWideName)
{
	constexpr std::size_t MAX_NAME_LENGTH = 256;
	if (pWideName != nullptr)
	{
		std::size_t nLength = 0;
		while (nLength < MAX_NAME_LENGTH && pWideName[nLength] != L'\0')
		{
			++nLength;
		}
		const int nSize = WideCharToMultiByte(CP_UTF8, 0, pWideName, static_cast<int>(nLength), nullptr, 0, nullptr, nullptr);
		if (nSize > 0)
		{
			std::string strName(static_cast<std::size_t>(nSize), '\0');
			(void)WideCharToMultiByte(CP_UTF8, 0, pWideName, static_cast<int>(nLength), strName.data(), nSize, nullptr, nullptr);
			return strName;
		}
	}
	std::size_t nLength = 0;
	if (pName != nullptr)
	{
		while (nLength < MAX_NAME_LENGTH && pName[nLength] != '\0')
		{
			++nLength;
		}
	}
	return pName != nullptr ? std::string(pName, nLength) : std::string{};
}

Serialization::JsonValue DescribeAllocations(const D3D12_DRED_ALLOCATION_NODE *pHead)
{
	using Serialization::JsonValue;
	JsonValue::List arrAllocations;
	const D3D12_DRED_ALLOCATION_NODE *pNode = pHead;
	constexpr std::uint32_t MAX_NODES = 256;
	for (std::uint32_t nIndex = 0; pNode != nullptr && nIndex < MAX_NODES; ++nIndex)
	{
		JsonValue::Object mapAllocation;
		mapAllocation["name"] = JsonValue(DebugName(pNode->ObjectNameA, pNode->ObjectNameW));
		mapAllocation["allocation_type"] = JsonValue(static_cast<std::int64_t>(pNode->AllocationType));
		arrAllocations.emplace_back(std::move(mapAllocation));
		pNode = pNode->pNext;
	}
	JsonValue::Object mapResult;
	mapResult["nodes"] = JsonValue(std::move(arrAllocations));
	mapResult["truncated"] = JsonValue(pNode != nullptr);
	return JsonValue(std::move(mapResult));
}

class VisualRuntime final
{
public:
	explicit VisualRuntime(const VisualConfig &in_stConfig) :
			stConfig(in_stConfig) {}
	~VisualRuntime()
	{
		for (GpuQueue *pQueue : { &stGraphics, &stCompute, &stCopy })
		{
			if (pQueue->stQueue.Get() != nullptr && pQueue->stFence.Get() != nullptr && pQueue->stEvent.hValue != nullptr &&
				!pQueue->Flush() && stDevice.Get() != nullptr && SUCCEEDED(stDevice->GetDeviceRemovedReason()))
			{
				// A live GPU may still reference every allocation. Process teardown
				// is the only safe terminal outcome after retirement has failed.
				std::cerr << "Fatal GPU retirement failure; live resources retained until process teardown\n";
				std::abort();
			}
		}
	}
	bool Initialize();
	bool Run();
	bool WriteReport(bool bSuccess);

private:
	bool Fail(const std::string &strMessage, HRESULT nResult = E_FAIL);
	bool CreatePipeline();
	bool CreateMesh();
	bool LoadScene();
	bool CreateSceneMesh();
	bool ResolveNetworkBindings();
	bool CreateDeferredPipeline();
	bool CreateShadowPipeline();
	bool CreatePostProcessPipeline();
	bool CreatePostProcessTargets();
	bool PreparePostProcess(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame);
	void DrawPostProcess(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame, PassWork eWork, std::uint32_t nMip, double dSeconds);
	bool CreateTransparencyPipeline();
	void DrawTransparency(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame);
	bool CreateParticleMesh();
	bool UpdateParticleBuffers(std::uint32_t nFrame, double dSeconds);
	ComOwner<ID3D12RootSignature> stTransparencyRoot;
	std::array<ComOwner<ID3D12PipelineState>, 4> arrTransparencyPipelines;
	std::vector<std::array<double, 3>> arrTransparentCenters;
	std::vector<std::size_t> arrTransparentOrder;
	struct ForwardDrawItem
	{
		bool bParticle = false;
		std::size_t nIndex = 0;
		double dDepth = 0;
	};
	std::vector<ForwardDrawItem> arrForwardDraws;
	std::vector<BillboardInstance> arrParticleInstances;
	std::unique_ptr<ParticleFrame> pParticleScratch;
	std::array<ComOwner<ID3D12Resource>, FRAME_COUNT> arrParticleVertices;
	std::array<ComOwner<ID3D12Resource>, FRAME_COUNT> arrParticleConstants;
	std::array<D3D12_VERTEX_BUFFER_VIEW, FRAME_COUNT> arrParticleVertexViews{};
	ComOwner<ID3D12Resource> stParticleIndices;
	D3D12_INDEX_BUFFER_VIEW stParticleIndexView{};
	std::uint32_t nParticleMaterial = 0;
	std::uint64_t nParticleUploadBytes = 0;
	std::uint32_t nPeakParticles = 0;
	bool CreateReflectionTargets();
	bool CreateReflectionPipeline();
	void DrawReflections(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame, PassWork eWork, std::uint32_t nMip);
	bool CreateForwardTargets();
	bool CreateVolumeTargets();
	bool CreateVolumePipeline();
	bool UpdateVolumeParameters(std::uint32_t nFrame);
	std::array<float, 16> BuildVolumeConstants() const;
	void DrawVolume(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame, PassWork eWork);
	ID3D12Resource *CurrentHdrResource(std::uint32_t nFrame) const;
	std::uint32_t CurrentHdrView() const;
	bool UpdateEffectTransforms();
	bool ResolveEffectOrigin(const std::optional<std::uint64_t> &nEntity, std::array<double, 3> &out_arrOrigin);
	bool CreateTemporalPipeline();
	bool CreateHistoryTargets();
	bool ResetTemporalHistory();
	void ResolveTemporal(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame);
	void DrawShadows(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame, bool bLocal);
	bool UploadTexture(const std::vector<MipLevel> &arrLevels, bool bSrgb, std::uint32_t nView);
	bool UploadFloatTexture(const std::vector<const FloatImage *> &arrImages, std::uint32_t nMips, std::uint32_t nView);
	bool UploadEnvironmentImportance(const EnvironmentImportance &stImportance);
	bool CreateEnvironment();
	void DrawScene(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame);
	void DrawLighting(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame);
	void DrawToneMap(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame);
	bool CreateConstantBuffers();
	bool UpdateConstantBuffer(FrameContext &stFrame);
	void RecordNetworkSample(const Gameplay::Vector3 &vInput);
	std::array<float, 16> DrawTransform(const GpuDraw &stDraw) const;
	std::uint32_t GraphicsPassCount() const noexcept;
	std::uint32_t TotalQueryCount() const noexcept;
	bool CreateTargets();
	bool CreateFrameContexts();
	bool Resize();
	bool BuildGraph();
	bool RenderFrame(double dSeconds, bool bCapture);
	bool CollectTiming(FrameContext &stFrame);
	void RecordPostProcessReadback(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame);
	bool CollectPostProcess(FrameContext &stFrame, FrameTiming &stTiming);
	bool ReadCapture();
	bool CheckValidation();
	FrameTiming &Timing(std::uint32_t nFrame);
	Serialization::JsonValue DescribeGraph() const;
	Serialization::JsonValue ReadDred() const;
	void ApplyBarriers(ID3D12GraphicsCommandList *pList, const std::vector<ResourceBarrier> &arrBarriers, const std::vector<ID3D12Resource *> &arrResources);
	D3D12_CPU_DESCRIPTOR_HANDLE Rtv(std::uint32_t nIndex) const;
	D3D12_CPU_DESCRIPTOR_HANDLE Dsv(std::uint32_t nIndex) const;
	D3D12_CPU_DESCRIPTOR_HANDLE View(std::uint32_t nIndex) const;
	D3D12_GPU_DESCRIPTOR_HANDLE GpuView(std::uint32_t nIndex) const;

	VisualConfig stConfig;
	Platform::Windows::Window stWindow;
	ComOwner<IDXGIFactory6> stFactory;
	ComOwner<IDXGIAdapter3> stAdapter;
	ComOwner<ID3D12Device> stDevice;
	ComOwner<ID3D12InfoQueue> stInfo;
	GpuQueue stGraphics;
	GpuQueue stCompute;
	GpuQueue stCopy;
	ComOwner<IDXGISwapChain3> stSwapchain;
	ComOwner<ID3D12DescriptorHeap> stRtvHeap;
	ComOwner<ID3D12DescriptorHeap> stDsvHeap;
	ComOwner<ID3D12DescriptorHeap> stViewHeap;
	ComOwner<ID3D12RootSignature> stGraphicsRoot;
	ComOwner<ID3D12RootSignature> stComputeRoot;
	ComOwner<ID3D12RootSignature> stDeferredRoot;
	ComOwner<ID3D12RootSignature> stLightingRoot;
	ComOwner<ID3D12RootSignature> stToneMapRoot;
	ComOwner<ID3D12PipelineState> stGraphicsPipeline;
	ComOwner<ID3D12PipelineState> stComputePipeline;
	ComOwner<ID3D12PipelineState> stDeferredPipeline;
	ComOwner<ID3D12PipelineState> stDoubleSidedPipeline;
	ComOwner<ID3D12PipelineState> stMirroredDoubleSidedPipeline;
	ComOwner<ID3D12PipelineState> stMirroredPipeline;
	ComOwner<ID3D12PipelineState> stLightingPipeline;
	ComOwner<ID3D12PipelineState> stToneMapPipeline;
	ComOwner<ID3D12DescriptorHeap> stPostCpuHeap;
	ComOwner<ID3D12RootSignature> stExposureRoot;
	ComOwner<ID3D12RootSignature> stBloomRoot;
	ComOwner<ID3D12PipelineState> stHistogramPipeline;
	ComOwner<ID3D12PipelineState> stExposurePipeline;
	ComOwner<ID3D12PipelineState> stBloomDownPipeline;
	ComOwner<ID3D12PipelineState> stBloomUpPipeline;
	ComOwner<ID3D12RootSignature> stReflectionRoot;
	std::array<ComOwner<ID3D12PipelineState>, 4> arrReflectionPipelines;
	std::uint64_t nReflectionBytes = 0;
	ForwardEffects stForwardEffects;
	VolumeGrid stVolumeGrid;
	ComOwner<ID3D12RootSignature> stVolumeRoot;
	std::array<ComOwner<ID3D12PipelineState>, 5> arrVolumePipelines;
	std::array<ComOwner<ID3D12Resource>, 2> arrVolumeHistory;
	ComOwner<ID3D12DescriptorHeap> stVolumeClearHeap;
	CameraMatrices stPreviousVolumeCamera;
	std::map<std::uint64_t, std::array<double, 16>> mapEffectTransforms;
	std::uint32_t nVolumeRead = 0;
	bool bVolumeHistoryReady = false;
	std::uint64_t nVolumeBytes = 0;
	std::uint64_t nForwardBytes = 0;
	std::array<ComOwner<ID3D12Resource>, 2> arrExposure;
	std::uint32_t nExposureRead = 0;
	bool bExposureReady = false;
	double dManualExposure = 1;
	double dLastPostSeconds = 0;
	DirectionalLightSettings stFrameLight;
	ComOwner<ID3D12DescriptorHeap> stHistoryCpuHeap;
	ComOwner<ID3D12RootSignature> stTemporalRoot;
	ComOwner<ID3D12PipelineState> stTemporalPipeline;
	std::array<std::array<ComOwner<ID3D12Resource>, 4>, 2> arrHistory;
	TemporalState stTemporalState;
	TemporalFrame stTemporalFrame;
	std::uint32_t nHistoryRead = 0;
	bool bHistoryReady = false;
	bool bWasMinimized = false;
	std::uint64_t nHistoryGeneration = 0;
	std::uint64_t nHistoryResets = 0;
	ComOwner<ID3D12RootSignature> stShadowRoot;
	std::array<ComOwner<ID3D12PipelineState>, 4> arrShadowPipelines;
	ComOwner<ID3D12DescriptorHeap> stSamplerHeap;
	std::vector<ComOwner<ID3D12Resource>> arrTextures;
	std::vector<ComOwner<ID3D12Resource>> arrTextureUploads;
	std::vector<GpuDraw> arrDraws;
	std::vector<GpuMaterial> arrMaterials;
	std::vector<RuntimeMaterialAsset> arrResolvedMaterials;
	bool bMaterialExtensions = false;
	std::uint64_t nMaterialBytes = 0;
	RenderScene stRenderScene;
	RenderConfiguration stRenderConfiguration;
	CameraMatrices stCameraMatrices;
	ShadowData stShadowData;
	LocalShadowData stLocalShadowData;
	Assets::SceneDocument stNetworkScene;
	Runtime::ClientSession stClient;
	Runtime::ClientSnapshot stClientSnapshot;
	Serialization::JsonValue::List arrNetworkSamples;
	std::uint64_t nNetworkInputFrames = 0;
	std::uint64_t nReconnectRequests = 0;
	std::uint64_t nObservedGeneration = 0;
	bool bNetworkStartedAfterGpuWarmup = false;
	bool bSceneMode = false;
	std::uint64_t nSceneTriangles = 0;
	std::uint64_t nTextureUploadBytes = 0;
	std::uint32_t nEnvironmentMips = 0;
	std::uint32_t nEnvironmentAliasEntries = 0;
	std::uint64_t nEnvironmentAliasBytes = 0;
	ComOwner<ID3D12Resource> stEnvironmentAlias;
	double dEnvironmentBuildMsec = 0;
	ComOwner<ID3D12Resource> stVertices;
	ComOwner<ID3D12Resource> stIndices;
	ComOwner<ID3D12Resource> stMeshUpload;
	ComOwner<ID3D12QueryHeap> stGraphicsQueries;
	ComOwner<ID3D12QueryHeap> stComputeQueries;
	ComOwner<ID3D12Resource> stCapture;
	std::array<ComOwner<ID3D12Resource>, FRAME_COUNT> arrBackbuffers;
	std::array<FrameContext, FRAME_COUNT> arrFrames;
	D3D12_VERTEX_BUFFER_VIEW stVertexView{};
	D3D12_INDEX_BUFFER_VIEW stIndexView{};
	D3D12_PLACED_SUBRESOURCE_FOOTPRINT stCaptureFootprint{};
	DXGI_ADAPTER_DESC2 stAdapterDescription{};
	RenderPipeline stRenderPipeline;
	std::vector<std::uint32_t> arrQueryOffsets;
	std::size_t nComputePassIndex = 0;
	CompiledGraph &stCompiled = stRenderPipeline.stGraph;
	std::vector<FrameTiming> arrTiming = std::vector<FrameTiming>(MAX_TIMING_SAMPLES);
	std::vector<std::string> arrMessages;
	std::string strFailure;
	std::uint32_t nRtvStride = 0;
	std::uint32_t nDsvStride = 0;
	std::uint32_t nViewStride = 0;
	std::uint32_t nFrames = 0;
	std::uint32_t nResizes = 0;
	std::uint32_t nValidationErrors = 0;
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint32_t nShaderModel = 0;
	std::uint32_t nRaytracingTier = 0;
	std::uint64_t nCaptureBytes = 0;
	std::uint64_t nPeakLocalMemory = 0;
	float fCameraX = 0.0F;
	float fCameraY = 0.0F;
	bool bTearing = false;
	bool bCaptureWritten = false;
};

bool VisualRuntime::Fail(const std::string &strMessage, HRESULT nResult)
{
	strFailure = strMessage + " (HRESULT " + std::to_string(static_cast<std::int64_t>(nResult)) + ")";
	std::cerr << strFailure << '\n';
	return false;
}

D3D12_CPU_DESCRIPTOR_HANDLE VisualRuntime::Rtv(std::uint32_t nIndex) const
{
	D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stRtvHeap->GetCPUDescriptorHandleForHeapStart();
	stHandle.ptr += static_cast<SIZE_T>(nRtvStride) * nIndex;
	return stHandle;
}

D3D12_CPU_DESCRIPTOR_HANDLE VisualRuntime::Dsv(std::uint32_t nIndex) const
{
	D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stDsvHeap->GetCPUDescriptorHandleForHeapStart();
	stHandle.ptr += static_cast<SIZE_T>(nDsvStride) * nIndex;
	return stHandle;
}

D3D12_CPU_DESCRIPTOR_HANDLE VisualRuntime::View(std::uint32_t nIndex) const
{
	D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stViewHeap->GetCPUDescriptorHandleForHeapStart();
	stHandle.ptr += static_cast<SIZE_T>(nViewStride) * nIndex;
	return stHandle;
}

D3D12_GPU_DESCRIPTOR_HANDLE VisualRuntime::GpuView(std::uint32_t nIndex) const
{
	D3D12_GPU_DESCRIPTOR_HANDLE stHandle = stViewHeap->GetGPUDescriptorHandleForHeapStart();
	stHandle.ptr += static_cast<UINT64>(nViewStride) * nIndex;
	return stHandle;
}

bool VisualRuntime::Initialize()
{
	std::string strWindowError;
	if (!stWindow.Initialize(L"Engine Next - independent D3D12 runtime", stConfig.nWidth, stConfig.nHeight, stConfig.bHidden, strWindowError))
	{
		return Fail(strWindowError);
	}
	UINT nFactoryFlags = 0;
	if (stConfig.bValidation)
	{
		ComOwner<ID3D12Debug1> stDebug;
		const HRESULT nResult = D3D12GetDebugInterface(IID_PPV_ARGS(stDebug.Put()));
		if (FAILED(nResult))
		{
			return Fail("GPU validation requested but Graphics Tools debug layer is unavailable", nResult);
		}
		stDebug->EnableDebugLayer();
		stDebug->SetEnableGPUBasedValidation(TRUE);
		nFactoryFlags = DXGI_CREATE_FACTORY_DEBUG;
	}
	ComOwner<ID3D12DeviceRemovedExtendedDataSettings> stDredSettings;
	if (SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(stDredSettings.Put()))))
	{
		stDredSettings->SetAutoBreadcrumbsEnablement(D3D12_DRED_ENABLEMENT_FORCED_ON);
		stDredSettings->SetPageFaultEnablement(D3D12_DRED_ENABLEMENT_FORCED_ON);
	}
	HRESULT nResult = CreateDXGIFactory2(nFactoryFlags, IID_PPV_ARGS(stFactory.Put()));
	if (FAILED(nResult))
	{
		return Fail("CreateDXGIFactory2", nResult);
	}
	for (UINT nIndex = 0;; ++nIndex)
	{
		ComOwner<IDXGIAdapter1> stCandidate;
		if (stFactory->EnumAdapterByGpuPreference(nIndex, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, IID_PPV_ARGS(stCandidate.Put())) == DXGI_ERROR_NOT_FOUND)
		{
			break;
		}
		DXGI_ADAPTER_DESC1 stDescription{};
		if (stCandidate.Get() == nullptr || FAILED(stCandidate->GetDesc1(&stDescription)) || (stDescription.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) != 0)
		{
			continue;
		}
		if (SUCCEEDED(D3D12CreateDevice(stCandidate.Get(), D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(stDevice.Put()))))
		{
			(void)stCandidate->QueryInterface(IID_PPV_ARGS(stAdapter.Put()));
			break;
		}
	}
	if (stDevice.Get() == nullptr || stAdapter.Get() == nullptr)
	{
		return Fail("No hardware D3D12 feature-level 12.0 adapter");
	}
	(void)stAdapter->GetDesc2(&stAdapterDescription);
	(void)stDevice->SetName(L"EngineNext.Device");
	if (stConfig.bValidation && FAILED(stDevice->QueryInterface(IID_PPV_ARGS(stInfo.Put()))))
	{
		return Fail("Debug info queue unavailable");
	}
	D3D12_FEATURE_DATA_SHADER_MODEL stShaderModel{ D3D_SHADER_MODEL_6_5 };
	if (FAILED(stDevice->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL, &stShaderModel, sizeof(stShaderModel))))
	{
		stShaderModel.HighestShaderModel = D3D_SHADER_MODEL_6_0;
		if (FAILED(stDevice->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL, &stShaderModel, sizeof(stShaderModel))))
		{
			return Fail("Shader model 6.0 required");
		}
	}
	nShaderModel = static_cast<std::uint32_t>(stShaderModel.HighestShaderModel);
	D3D12_FEATURE_DATA_D3D12_OPTIONS5 stOptions{};
	if (SUCCEEDED(stDevice->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS5, &stOptions, sizeof(stOptions))))
	{
		nRaytracingTier = static_cast<std::uint32_t>(stOptions.RaytracingTier);
	}
	BOOL bAllowTearing = FALSE;
	bTearing = SUCCEEDED(stFactory->CheckFeatureSupport(DXGI_FEATURE_PRESENT_ALLOW_TEARING, &bAllowTearing, sizeof(bAllowTearing))) && bAllowTearing != FALSE;
	if (!stGraphics.Initialize(stDevice.Get(), D3D12_COMMAND_LIST_TYPE_DIRECT) || !stCompute.Initialize(stDevice.Get(), D3D12_COMMAND_LIST_TYPE_COMPUTE) || !stCopy.Initialize(stDevice.Get(), D3D12_COMMAND_LIST_TYPE_COPY))
	{
		return Fail("Create queues and fences");
	}
	(void)stGraphics.stQueue->SetName(L"EngineNext.Graphics");
	(void)stCompute.stQueue->SetName(L"EngineNext.Compute");
	(void)stCopy.stQueue->SetName(L"EngineNext.Copy");
	nWidth = stWindow.GetWidth();
	nHeight = stWindow.GetHeight();
	DXGI_SWAP_CHAIN_DESC1 stSwapDescription{};
	stSwapDescription.Width = nWidth;
	stSwapDescription.Height = nHeight;
	stSwapDescription.Format = COLOR_FORMAT;
	stSwapDescription.SampleDesc.Count = 1;
	stSwapDescription.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
	stSwapDescription.BufferCount = FRAME_COUNT;
	stSwapDescription.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
	stSwapDescription.Flags = bTearing ? DXGI_SWAP_CHAIN_FLAG_ALLOW_TEARING : 0;
	ComOwner<IDXGISwapChain1> stSwap;
	nResult = stFactory->CreateSwapChainForHwnd(stGraphics.stQueue.Get(), static_cast<HWND>(stWindow.GetNativeHandle()), &stSwapDescription, nullptr, nullptr, stSwap.Put());
	if (FAILED(nResult) || FAILED(stSwap->QueryInterface(IID_PPV_ARGS(stSwapchain.Put()))))
	{
		return Fail("Create swapchain", nResult);
	}
	(void)stFactory->MakeWindowAssociation(static_cast<HWND>(stWindow.GetNativeHandle()), DXGI_MWA_NO_ALT_ENTER);
	(void)stSwapchain->SetColorSpace1(DXGI_COLOR_SPACE_RGB_FULL_G22_NONE_P709);
	D3D12_DESCRIPTOR_HEAP_DESC stHeap{};
	stHeap.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
	stHeap.NumDescriptors = FRAME_COUNT * 14;
	if (FAILED(stDevice->CreateDescriptorHeap(&stHeap, IID_PPV_ARGS(stRtvHeap.Put()))))
	{
		return Fail("Create RTV heap");
	}
	stHeap.Type = D3D12_DESCRIPTOR_HEAP_TYPE_DSV;
	stHeap.NumDescriptors = FRAME_COUNT * (6 + MAX_LOCAL_SHADOW_VIEWS);
	if (FAILED(stDevice->CreateDescriptorHeap(&stHeap, IID_PPV_ARGS(stDsvHeap.Put()))))
	{
		return Fail("Create DSV heap");
	}
	stHeap.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
	stHeap.NumDescriptors = ENVIRONMENT_VIEW_START + 4;
	stHeap.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
	if (FAILED(stDevice->CreateDescriptorHeap(&stHeap, IID_PPV_ARGS(stViewHeap.Put()))))
	{
		return Fail("Create shader-visible view heap");
	}
	nRtvStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
	nDsvStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_DSV);
	nViewStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
	return LoadScene() && BuildGraph() && CreateFrameContexts() && CreateTargets() && CreatePipeline() &&
			(!bSceneMode || (CreateDeferredPipeline() && CreateShadowPipeline() && CreateTemporalPipeline() && CreatePostProcessPipeline() && CreateReflectionPipeline() && CreateVolumePipeline())) && (bSceneMode ? (CreateSceneMesh() && CreateParticleMesh() && (!stForwardEffects.bTransparency || CreateTransparencyPipeline())) : CreateMesh()) && CreateConstantBuffers();
}

bool VisualRuntime::CreateFrameContexts()
{
	const D3D12_HEAP_PROPERTIES stDefault = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	const D3D12_HEAP_PROPERTIES stReadback = HeapProperties(D3D12_HEAP_TYPE_READBACK);
	for (std::uint32_t nIndex = 0; nIndex < FRAME_COUNT; ++nIndex)
	{
		FrameContext &stFrame = arrFrames[nIndex];
		if (FAILED(stDevice->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(stFrame.stGraphicsAllocator.Put()))) ||
			FAILED(stDevice->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_COMPUTE, IID_PPV_ARGS(stFrame.stComputeAllocator.Put()))) ||
			FAILED(stDevice->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, stFrame.stGraphicsAllocator.Get(), nullptr, IID_PPV_ARGS(stFrame.stGraphicsList.Put()))) ||
			FAILED(stDevice->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_COMPUTE, stFrame.stComputeAllocator.Get(), nullptr, IID_PPV_ARGS(stFrame.stComputeList.Put()))))
		{
			return Fail("Create frame command allocators/lists");
		}
		if (FAILED(stFrame.stGraphicsList->Close()) || FAILED(stFrame.stComputeList->Close()))
		{
			return Fail("Close initial command lists");
		}
		D3D12_RESOURCE_DESC stBuffer = BufferDescription(16);
		stBuffer.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
		if (FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stBuffer, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(stFrame.stTint.Put()))))
		{
			return Fail("Create compute tint buffer");
		}
		stBuffer = BufferDescription(TotalQueryCount() * sizeof(std::uint64_t));
		if (FAILED(stDevice->CreateCommittedResource(&stReadback, D3D12_HEAP_FLAG_NONE, &stBuffer, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stFrame.stQueries.Put()))))
		{
			return Fail("Create timestamp readback");
		}
		D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
		stSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
		stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
		stSrv.Buffer.NumElements = 1;
		stSrv.Buffer.StructureByteStride = 16;
		stDevice->CreateShaderResourceView(stFrame.stTint.Get(), &stSrv, View(nIndex * FRAME_VIEW_COUNT));
		D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
		stUav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
		stUav.Buffer.NumElements = 1;
		stUav.Buffer.StructureByteStride = 16;
		stDevice->CreateUnorderedAccessView(stFrame.stTint.Get(), nullptr, &stUav, View(nIndex * FRAME_VIEW_COUNT + 1));
		(void)stFrame.stTint->SetName(L"EngineNext.ComputeTint");
	}
	D3D12_QUERY_HEAP_DESC stQuery{};
	stQuery.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP;
	stQuery.Count = FRAME_COUNT * GraphicsPassCount() * 2;
	if (FAILED(stDevice->CreateQueryHeap(&stQuery, IID_PPV_ARGS(stGraphicsQueries.Put()))))
	{
		return Fail("Create graphics timestamp heap");
	}
	stQuery.Count = FRAME_COUNT * 2;
	return SUCCEEDED(stDevice->CreateQueryHeap(&stQuery, IID_PPV_ARGS(stComputeQueries.Put()))) || Fail("Create compute timestamp heap");
}

bool VisualRuntime::CreateTargets()
{
	nMaterialBytes = 0;
	const D3D12_HEAP_PROPERTIES stHeap = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	D3D12_RESOURCE_DESC stTexture{};
	stTexture.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
	stTexture.Width = nWidth;
	stTexture.Height = nHeight;
	stTexture.DepthOrArraySize = 1;
	stTexture.MipLevels = 1;
	stTexture.SampleDesc.Count = 1;
	stTexture.Format = COLOR_FORMAT;
	stTexture.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
	D3D12_CLEAR_VALUE stClear{};
	stClear.Format = COLOR_FORMAT;
	stClear.Color[0] = 0.025F;
	stClear.Color[1] = 0.035F;
	stClear.Color[2] = 0.055F;
	stClear.Color[3] = 1.0F;
	for (std::uint32_t nIndex = 0; nIndex < FRAME_COUNT; ++nIndex)
	{
		FrameContext &stFrame = arrFrames[nIndex];
		if (FAILED(stSwapchain->GetBuffer(nIndex, IID_PPV_ARGS(arrBackbuffers[nIndex].Put()))) ||
			FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stTexture, D3D12_RESOURCE_STATE_COMMON, &stClear, IID_PPV_ARGS(stFrame.stColor.Put()))))
		{
			return Fail("Create color targets");
		}
		stDevice->CreateRenderTargetView(arrBackbuffers[nIndex].Get(), nullptr, Rtv(nIndex));
		stDevice->CreateRenderTargetView(stFrame.stColor.Get(), nullptr, Rtv(nIndex + FRAME_COUNT));
		D3D12_RESOURCE_DESC stDepthDescription = stTexture;
		stDepthDescription.Format = bSceneMode ? DXGI_FORMAT_R32_TYPELESS : DXGI_FORMAT_D32_FLOAT;
		stDepthDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_DEPTH_STENCIL;
		D3D12_CLEAR_VALUE stDepthClear{};
		stDepthClear.Format = DXGI_FORMAT_D32_FLOAT;
		stDepthClear.DepthStencil.Depth = 0.0F;
		if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDepthDescription, D3D12_RESOURCE_STATE_DEPTH_WRITE, &stDepthClear, IID_PPV_ARGS(stFrame.stDepth.Put()))))
		{
			return Fail("Create depth target");
		}
		D3D12_DEPTH_STENCIL_VIEW_DESC stDsv{};
		stDsv.Format = DXGI_FORMAT_D32_FLOAT;
		stDsv.ViewDimension = D3D12_DSV_DIMENSION_TEXTURE2D;
		stDevice->CreateDepthStencilView(stFrame.stDepth.Get(), &stDsv, Dsv(nIndex));
		stDsv.Flags = D3D12_DSV_FLAG_READ_ONLY_DEPTH;
		stDevice->CreateDepthStencilView(stFrame.stDepth.Get(), &stDsv, Dsv(FRAME_COUNT * (5 + MAX_LOCAL_SHADOW_VIEWS) + nIndex));
		if (bSceneMode)
		{
			D3D12_RESOURCE_DESC stHdrDescription = stTexture;
			stHdrDescription.Format = HDR_FORMAT;
			D3D12_CLEAR_VALUE stHdrClear{};
			stHdrClear.Format = HDR_FORMAT;
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stHdrDescription, D3D12_RESOURCE_STATE_COMMON, &stHdrClear, IID_PPV_ARGS(stFrame.stHdr.Put()))))
			{
				return Fail("Create linear HDR target");
			}
			stDevice->CreateRenderTargetView(stFrame.stHdr.Get(), nullptr, Rtv(FRAME_COUNT * 6 + nIndex));
			D3D12_SHADER_RESOURCE_VIEW_DESC stHdrSrv{};
			stHdrSrv.Format = HDR_FORMAT;
			stHdrSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
			stHdrSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stHdrSrv.Texture2D.MipLevels = 1;
			stDevice->CreateShaderResourceView(stFrame.stHdr.Get(), &stHdrSrv, View(nIndex * FRAME_VIEW_COUNT + 7));
			(void)stFrame.stHdr->SetName(L"EngineNext.LinearHdr");
			D3D12_RESOURCE_DESC stShadowDescription = stTexture;
			stShadowDescription.Width = stRenderConfiguration.stShadows.nResolution;
			stShadowDescription.Height = stRenderConfiguration.stShadows.nResolution;
			stShadowDescription.DepthOrArraySize = 4;
			stShadowDescription.Format = DXGI_FORMAT_R32_TYPELESS;
			stShadowDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_DEPTH_STENCIL;
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stShadowDescription, D3D12_RESOURCE_STATE_DEPTH_WRITE, &stDepthClear, IID_PPV_ARGS(stFrame.stDirectionalShadow.Put()))))
			{
				return Fail("Create cascade shadow depth array");
			}
			for (std::uint32_t nCascade = 0; nCascade < 4; ++nCascade)
			{
				D3D12_DEPTH_STENCIL_VIEW_DESC stShadowDsv{};
				stShadowDsv.Format = DXGI_FORMAT_D32_FLOAT;
				stShadowDsv.ViewDimension = D3D12_DSV_DIMENSION_TEXTURE2DARRAY;
				stShadowDsv.Texture2DArray.ArraySize = 1;
				stShadowDsv.Texture2DArray.FirstArraySlice = nCascade;
				stDevice->CreateDepthStencilView(stFrame.stDirectionalShadow.Get(), &stShadowDsv, Dsv(FRAME_COUNT + nIndex * 4 + nCascade));
			}
			D3D12_SHADER_RESOURCE_VIEW_DESC stShadowSrv{};
			stShadowSrv.Format = DXGI_FORMAT_R32_FLOAT;
			stShadowSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2DARRAY;
			stShadowSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stShadowSrv.Texture2DArray.ArraySize = 4;
			stShadowSrv.Texture2DArray.MipLevels = 1;
			stDevice->CreateShaderResourceView(stFrame.stDirectionalShadow.Get(), &stShadowSrv, View(nIndex * FRAME_VIEW_COUNT + 8));
			(void)stFrame.stDirectionalShadow->SetName(L"EngineNext.DirectionalShadow");
			D3D12_RESOURCE_DESC stLocalDescription = stShadowDescription;
			stLocalDescription.Width = stRenderConfiguration.stShadows.nLocalResolution;
			stLocalDescription.Height = stRenderConfiguration.stShadows.nLocalResolution;
			const std::uint32_t nViews = (std::max)(1U, static_cast<std::uint32_t>(stLocalShadowData.arrViews.size()));
			stLocalDescription.DepthOrArraySize = static_cast<UINT16>(nViews);
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stLocalDescription, D3D12_RESOURCE_STATE_DEPTH_WRITE, &stDepthClear, IID_PPV_ARGS(stFrame.stLocalShadow.Put()))))
			{
				return Fail("Create local shadow array");
			}
			for (std::uint32_t nView = 0; nView < nViews; ++nView)
			{
				D3D12_DEPTH_STENCIL_VIEW_DESC stLocalDsv{};
				stLocalDsv.Format = DXGI_FORMAT_D32_FLOAT;
				stLocalDsv.ViewDimension = D3D12_DSV_DIMENSION_TEXTURE2DARRAY;
				stLocalDsv.Texture2DArray.ArraySize = 1;
				stLocalDsv.Texture2DArray.FirstArraySlice = nView;
				stDevice->CreateDepthStencilView(stFrame.stLocalShadow.Get(), &stLocalDsv, Dsv(FRAME_COUNT * 5 + nIndex * MAX_LOCAL_SHADOW_VIEWS + nView));
			}
			stShadowSrv.Texture2DArray.ArraySize = nViews;
			stDevice->CreateShaderResourceView(stFrame.stLocalShadow.Get(), &stShadowSrv, View(nIndex * FRAME_VIEW_COUNT + 9));
			(void)stFrame.stLocalShadow->SetName(L"EngineNext.LocalShadow");
			const std::array<DXGI_FORMAT, 4> arrFormats{ DXGI_FORMAT_R8G8B8A8_UNORM_SRGB, DXGI_FORMAT_R16G16B16A16_FLOAT, DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_FORMAT_R16G16B16A16_FLOAT };
			for (std::uint32_t nTarget = 0; nTarget < arrFormats.size(); ++nTarget)
			{
				D3D12_RESOURCE_DESC stGbuffer = stTexture;
				stGbuffer.Format = arrFormats[nTarget];
				D3D12_CLEAR_VALUE stGbufferClear{};
				stGbufferClear.Format = arrFormats[nTarget];
				if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stGbuffer, D3D12_RESOURCE_STATE_COMMON, &stGbufferClear, IID_PPV_ARGS(stFrame.arrGbuffer[nTarget].Put()))))
				{
					return Fail("Create GBuffer");
				}
				stDevice->CreateRenderTargetView(stFrame.arrGbuffer[nTarget].Get(), nullptr, Rtv(FRAME_COUNT * 2 + nIndex * 4 + nTarget));
				const std::wstring strName = L"EngineNext.GBuffer." + std::to_wstring(nIndex) + L"." + std::to_wstring(nTarget);
				(void)stFrame.arrGbuffer[nTarget]->SetName(strName.c_str());
				D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
				stSrv.Format = arrFormats[nTarget];
				stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
				stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
				stSrv.Texture2D.MipLevels = 1;
				stDevice->CreateShaderResourceView(stFrame.arrGbuffer[nTarget].Get(), &stSrv, View(nIndex * FRAME_VIEW_COUNT + 2 + nTarget));
			}
			if (bMaterialExtensions)
			{
				for (std::uint32_t nTarget = 0; nTarget < stFrame.arrMaterialBuffers.size(); ++nTarget)
				{
					D3D12_RESOURCE_DESC stMaterial = stTexture;
					stMaterial.Format = nTarget == 0 ? DXGI_FORMAT_R32G32B32A32_FLOAT : DXGI_FORMAT_R16G16B16A16_FLOAT;
					D3D12_CLEAR_VALUE stMaterialClear{};
					stMaterialClear.Format = stMaterial.Format;
					if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stMaterial, D3D12_RESOURCE_STATE_COMMON, &stMaterialClear, IID_PPV_ARGS(stFrame.arrMaterialBuffers[nTarget].Put()))))
					{
						return Fail("Create material extension targets");
					}
					const std::wstring strName = L"EngineNext.Material." + std::to_wstring(nIndex) + L"." + std::to_wstring(nTarget);
					nMaterialBytes += stDevice->GetResourceAllocationInfo(0, 1, &stMaterial).SizeInBytes;
					(void)stFrame.arrMaterialBuffers[nTarget]->SetName(strName.c_str());
					stDevice->CreateRenderTargetView(stFrame.arrMaterialBuffers[nTarget].Get(), nullptr, Rtv(FRAME_COUNT * 12 + nIndex * 2 + nTarget));
					D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
					stSrv.Format = stMaterial.Format;
					stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
					stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
					stSrv.Texture2D.MipLevels = 1;
					stDevice->CreateShaderResourceView(stFrame.arrMaterialBuffers[nTarget].Get(), &stSrv, View(nIndex * FRAME_VIEW_COUNT + MATERIAL_PARAMETERS_VIEW + nTarget));
				}
			}
			const std::array<DXGI_FORMAT, 2> arrTemporalFormats{ DXGI_FORMAT_R32G32B32A32_FLOAT, DXGI_FORMAT_R32_UINT };
			for (std::uint32_t nTarget = 0; nTarget < 2; ++nTarget)
			{
				D3D12_RESOURCE_DESC stDescription = stTexture;
				stDescription.Format = arrTemporalFormats[nTarget];
				D3D12_CLEAR_VALUE stTemporalClear{};
				stTemporalClear.Format = stDescription.Format;
				ComOwner<ID3D12Resource> &stResource = nTarget == 0 ? stFrame.stMotion : stFrame.stObjectId;
				if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON, &stTemporalClear, IID_PPV_ARGS(stResource.Put()))))
				{
					return Fail("Create motion and identity targets");
				}
				stDevice->CreateRenderTargetView(stResource.Get(), nullptr, Rtv(FRAME_COUNT * (7 + nTarget) + nIndex));
				D3D12_SHADER_RESOURCE_VIEW_DESC stTemporalSrv{};
				stTemporalSrv.Format = stDescription.Format;
				stTemporalSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
				stTemporalSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
				stTemporalSrv.Texture2D.MipLevels = 1;
				stDevice->CreateShaderResourceView(stResource.Get(), &stTemporalSrv, View(nIndex * FRAME_VIEW_COUNT + 10 + nTarget));
				const std::wstring strName = (nTarget == 0 ? L"EngineNext.Motion." : L"EngineNext.ObjectId.") + std::to_wstring(nIndex);
				(void)stResource->SetName(strName.c_str());
			}
			D3D12_SHADER_RESOURCE_VIEW_DESC stDepthSrv{};
			stDepthSrv.Format = DXGI_FORMAT_R32_FLOAT;
			stDepthSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stDepthSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
			stDepthSrv.Texture2D.MipLevels = 1;
			stDevice->CreateShaderResourceView(stFrame.stDepth.Get(), &stDepthSrv, View(nIndex * FRAME_VIEW_COUNT + 6));
		}
		(void)stFrame.stColor->SetName(L"EngineNext.FrameColor");
		(void)stFrame.stDepth->SetName(L"EngineNext.ReverseDepth");
		(void)arrBackbuffers[nIndex]->SetName(L"EngineNext.Backbuffer");
	}
	if (bSceneMode && stRenderConfiguration.stTemporal.bEnabled && !CreateHistoryTargets())
	{
		return false;
	}
	if (!CreatePostProcessTargets() || !CreateReflectionTargets() || !CreateForwardTargets() || !CreateVolumeTargets())
	{
		return false;
	}
	stDevice->GetCopyableFootprints(&stTexture, 0, 1, 0, &stCaptureFootprint, nullptr, nullptr, &nCaptureBytes);
	const D3D12_HEAP_PROPERTIES stReadback = HeapProperties(D3D12_HEAP_TYPE_READBACK);
	const D3D12_RESOURCE_DESC stCaptureDescription = BufferDescription(nCaptureBytes);
	if (FAILED(stDevice->CreateCommittedResource(&stReadback, D3D12_HEAP_FLAG_NONE, &stCaptureDescription, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stCapture.Put()))))
	{
		return Fail("Create image readback");
	}
	return true;
}

bool VisualRuntime::CreatePipeline()
{
	const std::vector<std::uint8_t> arrVertex = ReadShader(stConfig.strShaderDirectory, "FixedMesh.vs.cso");
	const std::vector<std::uint8_t> arrPixel = ReadShader(stConfig.strShaderDirectory, "FixedMesh.ps.cso");
	const std::vector<std::uint8_t> arrCompute = ReadShader(stConfig.strShaderDirectory, "FixedMesh.cs.cso");
	if (arrVertex.empty() || arrPixel.empty() || arrCompute.empty())
	{
		return Fail("Missing or empty offline shader package");
	}
	for (std::uint32_t nPipeline = 0; nPipeline < 2; ++nPipeline)
	{
		D3D12_DESCRIPTOR_RANGE stRange{};
		stRange.RangeType = nPipeline == 0 ? D3D12_DESCRIPTOR_RANGE_TYPE_SRV : D3D12_DESCRIPTOR_RANGE_TYPE_UAV;
		stRange.NumDescriptors = 1;
		std::array<D3D12_ROOT_PARAMETER, 2> arrParameters{};
		arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
		arrParameters[0].Constants.Num32BitValues = 4;
		arrParameters[0].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
		arrParameters[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[1].DescriptorTable.NumDescriptorRanges = 1;
		arrParameters[1].DescriptorTable.pDescriptorRanges = &stRange;
		arrParameters[1].ShaderVisibility = nPipeline == 0 ? D3D12_SHADER_VISIBILITY_PIXEL : D3D12_SHADER_VISIBILITY_ALL;
		D3D12_ROOT_SIGNATURE_DESC stRoot{};
		stRoot.NumParameters = static_cast<UINT>(arrParameters.size());
		stRoot.pParameters = arrParameters.data();
		stRoot.Flags = nPipeline == 0 ? D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT : D3D12_ROOT_SIGNATURE_FLAG_NONE;
		ComOwner<ID3DBlob> stSerialized;
		ComOwner<ID3DBlob> stErrors;
		HRESULT nResult = D3D12SerializeRootSignature(&stRoot, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put());
		if (FAILED(nResult))
		{
			return Fail("Serialize root signature", nResult);
		}
		ComOwner<ID3D12RootSignature> &stDestination = nPipeline == 0 ? stGraphicsRoot : stComputeRoot;
		if (FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stDestination.Put()))))
		{
			return Fail("Create root signature");
		}
	}
	const std::array<D3D12_INPUT_ELEMENT_DESC, 3> arrLayout = { {
			{ "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "NORMAL", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 12, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "COLOR", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 24, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
	} };
	D3D12_GRAPHICS_PIPELINE_STATE_DESC stPipeline{};
	stPipeline.pRootSignature = stGraphicsRoot.Get();
	stPipeline.VS = { arrVertex.data(), arrVertex.size() };
	stPipeline.PS = { arrPixel.data(), arrPixel.size() };
	stPipeline.InputLayout = { arrLayout.data(), static_cast<UINT>(arrLayout.size()) };
	stPipeline.SampleMask = UINT_MAX;
	stPipeline.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
	stPipeline.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
	stPipeline.RasterizerState.DepthClipEnable = TRUE;
	stPipeline.BlendState.RenderTarget[0].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
	stPipeline.DepthStencilState.DepthEnable = TRUE;
	stPipeline.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ALL;
	stPipeline.DepthStencilState.DepthFunc = D3D12_COMPARISON_FUNC_GREATER_EQUAL;
	stPipeline.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
	stPipeline.NumRenderTargets = 1;
	stPipeline.RTVFormats[0] = COLOR_FORMAT;
	stPipeline.DSVFormat = DXGI_FORMAT_D32_FLOAT;
	stPipeline.SampleDesc.Count = 1;
	HRESULT nResult = stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(stGraphicsPipeline.Put()));
	if (FAILED(nResult))
	{
		return Fail("Create graphics PSO", nResult);
	}
	D3D12_COMPUTE_PIPELINE_STATE_DESC stComputeDescription{};
	stComputeDescription.pRootSignature = stComputeRoot.Get();
	stComputeDescription.CS = { arrCompute.data(), arrCompute.size() };
	nResult = stDevice->CreateComputePipelineState(&stComputeDescription, IID_PPV_ARGS(stComputePipeline.Put()));
	return SUCCEEDED(nResult) || Fail("Create compute PSO", nResult);
}

bool VisualRuntime::CreateMesh()
{
	std::vector<Vertex> arrVertices;
	std::vector<std::uint16_t> arrIndices;
	const std::array<std::array<float, 3>, 6> arrNormals = { { { 0, 0, 1 }, { 0, 0, -1 }, { 1, 0, 0 }, { -1, 0, 0 }, { 0, 1, 0 }, { 0, -1, 0 } } };
	const std::array<std::array<float, 3>, 6> arrColors = { { { 0.90F, 0.30F, 0.12F }, { 0.10F, 0.60F, 0.90F }, { 0.15F, 0.75F, 0.40F }, { 0.70F, 0.25F, 0.80F }, { 0.90F, 0.75F, 0.20F }, { 0.25F, 0.45F, 0.70F } } };
	for (std::uint16_t nFace = 0; nFace < 6; ++nFace)
	{
		for (std::uint16_t nCorner = 0; nCorner < 4; ++nCorner)
		{
			Vertex stVertex{};
			const float fU = (nCorner == 0 || nCorner == 3) ? -1.0F : 1.0F;
			const float fV = nCorner < 2 ? -1.0F : 1.0F;
			const std::uint16_t nAxis = nFace / 2;
			stVertex.arrPosition[(nAxis + 2) % 3] = (nFace % 2 == 0) ? 1.0F : -1.0F;
			stVertex.arrPosition[nAxis] = fU;
			stVertex.arrPosition[(nAxis + 1) % 3] = fV;
			const std::uint16_t nNormalFace = nAxis == 0 ? nFace : static_cast<std::uint16_t>((nAxis == 1 ? 4 : 2) + nFace % 2);
			std::memcpy(stVertex.arrNormal, arrNormals[nNormalFace].data(), sizeof(stVertex.arrNormal));
			std::memcpy(stVertex.arrColor, arrColors[nFace].data(), sizeof(stVertex.arrColor));
			arrVertices.push_back(stVertex);
		}
		const std::uint16_t nBase = static_cast<std::uint16_t>(nFace * 4);
		const std::array<std::uint16_t, 6> arrOffsets{ 0, 1, 2, 0, 2, 3 };
		for (const std::uint16_t nOffset : arrOffsets)
		{
			arrIndices.push_back(static_cast<std::uint16_t>(nBase + nOffset));
		}
	}
	const std::uint64_t nVertexBytes = arrVertices.size() * sizeof(Vertex);
	const std::uint64_t nIndexBytes = arrIndices.size() * sizeof(std::uint16_t);
	const D3D12_HEAP_PROPERTIES stDefault = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	const D3D12_HEAP_PROPERTIES stUploadHeap = HeapProperties(D3D12_HEAP_TYPE_UPLOAD);
	const D3D12_RESOURCE_DESC stVertexDescription = BufferDescription(nVertexBytes);
	const D3D12_RESOURCE_DESC stIndexDescription = BufferDescription(nIndexBytes);
	const D3D12_RESOURCE_DESC stUploadDescription = BufferDescription(nVertexBytes + nIndexBytes);
	if (FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stVertexDescription, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stVertices.Put()))) ||
		FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stIndexDescription, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stIndices.Put()))) ||
		FAILED(stDevice->CreateCommittedResource(&stUploadHeap, D3D12_HEAP_FLAG_NONE, &stUploadDescription, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stMeshUpload.Put()))))
	{
		return Fail("Create mesh buffers");
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stMeshUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map mesh upload");
	}
	std::memcpy(pMapped, arrVertices.data(), static_cast<std::size_t>(nVertexBytes));
	std::memcpy(static_cast<std::uint8_t *>(pMapped) + nVertexBytes, arrIndices.data(), static_cast<std::size_t>(nIndexBytes));
	stMeshUpload->Unmap(0, nullptr);
	FrameContext &stFrame = arrFrames[0];
	if (FAILED(stFrame.stGraphicsAllocator->Reset()) || FAILED(stFrame.stGraphicsList->Reset(stFrame.stGraphicsAllocator.Get(), nullptr)))
	{
		return Fail("Reset mesh upload command list");
	}
	stFrame.stGraphicsList->CopyBufferRegion(stVertices.Get(), 0, stMeshUpload.Get(), 0, nVertexBytes);
	stFrame.stGraphicsList->CopyBufferRegion(stIndices.Get(), 0, stMeshUpload.Get(), nVertexBytes, nIndexBytes);
	std::array<D3D12_RESOURCE_BARRIER, 2> arrBarriers{};
	for (std::size_t nIndex = 0; nIndex < arrBarriers.size(); ++nIndex)
	{
		arrBarriers[nIndex].Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
		arrBarriers[nIndex].Transition.pResource = nIndex == 0 ? stVertices.Get() : stIndices.Get();
		arrBarriers[nIndex].Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
		arrBarriers[nIndex].Transition.StateAfter = nIndex == 0 ? D3D12_RESOURCE_STATE_VERTEX_AND_CONSTANT_BUFFER : D3D12_RESOURCE_STATE_INDEX_BUFFER;
		arrBarriers[nIndex].Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
	}
	stFrame.stGraphicsList->ResourceBarrier(static_cast<UINT>(arrBarriers.size()), arrBarriers.data());
	if (FAILED(stFrame.stGraphicsList->Close()))
	{
		return Fail("Close mesh upload list");
	}
	ID3D12CommandList *pUploadList = stFrame.stGraphicsList.Get();
	stGraphics.stQueue->ExecuteCommandLists(1, &pUploadList);
	if (!stGraphics.Flush())
	{
		return Fail("Wait mesh upload retirement");
	}
	stMeshUpload.Reset();
	stVertexView = { stVertices->GetGPUVirtualAddress(), static_cast<UINT>(nVertexBytes), sizeof(Vertex) };
	stIndexView = { stIndices->GetGPUVirtualAddress(), static_cast<UINT>(nIndexBytes), DXGI_FORMAT_R16_UINT };
	(void)stVertices->SetName(L"EngineNext.CubeVertices");
	(void)stIndices->SetName(L"EngineNext.CubeIndices");
	return true;
}

bool VisualRuntime::LoadScene()
{
	if (stConfig.strAssetPackagePath.empty())
	{
		return (stConfig.strGpuPackagePath.empty() && stConfig.strRenderConfigPath.empty()) || Fail("GPU package and render configuration require a source asset package");
	}
	Assets::Diagnostics arrDiagnostics;
	if (!LoadRenderScene(stConfig.strAssetPackagePath, stRenderScene, arrDiagnostics))
	{
		return Fail(arrDiagnostics.empty() ? "Load render scene" : arrDiagnostics.front().strMessage);
	}
	if (!stConfig.strGpuPackagePath.empty())
	{
		RenderScene stCooked;
		if (!LoadGpuPackage(stConfig.strGpuPackagePath, stRenderScene.strPackageDigest, stCooked, arrDiagnostics))
		{
			return Fail(arrDiagnostics.empty() ? "Load GPU package" : arrDiagnostics.front().strMessage);
		}
		if (!VerifyCookedScene(stRenderScene, stCooked, arrDiagnostics))
		{
			return Fail(arrDiagnostics.empty() ? "Verify GPU source binding" : arrDiagnostics.front().strMessage);
		}
		stRenderScene = std::move(stCooked);
	}
	if (!stConfig.strRenderConfigPath.empty() && !LoadRenderConfiguration(std::filesystem::u8path(stConfig.strRenderConfigPath), stRenderScene.strPackageDigest, stRenderConfiguration, arrDiagnostics))
	{
		return Fail(arrDiagnostics.empty() ? "Load rendering configuration" : arrDiagnostics.front().strMessage);
	}
	if (!ResolveMaterialSettings(stRenderConfiguration.stMaterials, stRenderScene, arrResolvedMaterials, arrDiagnostics))
	{
		return Fail(arrDiagnostics.empty() ? "Resolve rendering materials" : arrDiagnostics.front().strMessage);
	}
	for (const RuntimeMaterialAsset &stAsset : arrResolvedMaterials)
	{
		for (const RuntimeMaterial &stMaterial : stAsset.arrMaterials)
		{
			bMaterialExtensions = bMaterialExtensions || stMaterial.fClearcoatFactor > 0 || stMaterial.fAnisotropyStrength != 0;
		}
	}
	if (stRenderConfiguration.stExposure.eMode != ExposureMode::Automatic &&
		!ComputeExposureMultiplier(stRenderConfiguration.stExposure, stRenderConfiguration.dExposure, 0, dManualExposure, arrDiagnostics))
	{
		return Fail("Compute manual exposure");
	}
	if (!BuildLocalShadows(stRenderConfiguration.arrPointLights, stRenderConfiguration.arrSpotLights, stLocalShadowData, arrDiagnostics))
	{
		return Fail(arrDiagnostics.empty() ? "Build local shadow views" : arrDiagnostics.back().strMessage);
	}
	bSceneMode = true;
	if (stConfig.bConnect || stRenderConfiguration.stVolume.bEnabled || !stRenderConfiguration.arrParticles.empty())
	{
		Assets::PackageData stPackage;
		if (!Assets::LoadPackage(stConfig.strAssetPackagePath, stPackage, arrDiagnostics))
		{
			return Fail("Reload simulation scene bindings");
		}
		if (stPackage.strPackageDigest != stRenderScene.strPackageDigest)
		{
			return Fail("Simulation scene package changed during initialization");
		}
		stNetworkScene = std::move(stPackage.stScene);
	}
	return true;
}

bool VisualRuntime::UploadTexture(const std::vector<MipLevel> &arrLevels, bool bSrgb, std::uint32_t nView)
{
	if (arrLevels.empty() || arrLevels.size() > 16)
	{
		return Fail("Invalid texture mip chain");
	}
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
	stDescription.Width = arrLevels[0].nWidth;
	stDescription.Height = arrLevels[0].nHeight;
	stDescription.DepthOrArraySize = 1;
	stDescription.MipLevels = static_cast<UINT16>(arrLevels.size());
	stDescription.Format = DXGI_FORMAT_R8G8B8A8_TYPELESS;
	stDescription.SampleDesc.Count = 1;
	const D3D12_HEAP_PROPERTIES stDefault = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	ComOwner<ID3D12Resource> stTexture;
	if (FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stTexture.Put()))))
	{
		return Fail("Create material texture");
	}
	std::vector<D3D12_PLACED_SUBRESOURCE_FOOTPRINT> arrFootprints(arrLevels.size());
	std::vector<UINT> arrRows(arrLevels.size());
	std::vector<UINT64> arrRowBytes(arrLevels.size());
	UINT64 nTotalBytes = 0;
	stDevice->GetCopyableFootprints(&stDescription, 0, static_cast<UINT>(arrLevels.size()), 0, arrFootprints.data(), arrRows.data(), arrRowBytes.data(), &nTotalBytes);
	if (nTotalBytes > MAX_TEXTURE_UPLOAD_BYTES - nTextureUploadBytes)
	{
		return Fail("Material texture upload budget exceeded");
	}
	nTextureUploadBytes += nTotalBytes;
	const D3D12_RESOURCE_DESC stUploadDescription = BufferDescription(nTotalBytes);
	const D3D12_HEAP_PROPERTIES stUploadHeap = HeapProperties(D3D12_HEAP_TYPE_UPLOAD);
	ComOwner<ID3D12Resource> stUpload;
	if (FAILED(stDevice->CreateCommittedResource(&stUploadHeap, D3D12_HEAP_FLAG_NONE, &stUploadDescription, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stUpload.Put()))))
	{
		return Fail("Create texture upload");
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map texture upload");
	}
	ID3D12GraphicsCommandList *pList = arrFrames[0].stGraphicsList.Get();
	for (std::uint32_t nMip = 0; nMip < arrLevels.size(); ++nMip)
	{
		const MipLevel &stLevel = arrLevels[nMip];
		for (std::uint32_t nRow = 0; nRow < stLevel.nHeight; ++nRow)
		{
			std::memcpy(static_cast<std::uint8_t *>(pMapped) + arrFootprints[nMip].Offset + static_cast<std::size_t>(nRow) * arrFootprints[nMip].Footprint.RowPitch,
						stLevel.arrRgba8.data() + static_cast<std::size_t>(nRow) * stLevel.nWidth * 4, static_cast<std::size_t>(stLevel.nWidth) * 4);
		}
		D3D12_TEXTURE_COPY_LOCATION stTarget{};
		stTarget.pResource = stTexture.Get();
		stTarget.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
		stTarget.SubresourceIndex = nMip;
		D3D12_TEXTURE_COPY_LOCATION stSource{};
		stSource.pResource = stUpload.Get();
		stSource.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
		stSource.PlacedFootprint = arrFootprints[nMip];
		pList->CopyTextureRegion(&stTarget, 0, 0, 0, &stSource, nullptr);
	}
	stUpload->Unmap(0, nullptr);
	D3D12_RESOURCE_BARRIER stBarrier{};
	stBarrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
	stBarrier.Transition.pResource = stTexture.Get();
	stBarrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
	stBarrier.Transition.StateAfter = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
	stBarrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
	pList->ResourceBarrier(1, &stBarrier);
	D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
	stSrv.Format = bSrgb ? DXGI_FORMAT_R8G8B8A8_UNORM_SRGB : DXGI_FORMAT_R8G8B8A8_UNORM;
	stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
	stSrv.Texture2D.MipLevels = static_cast<UINT>(arrLevels.size());
	stDevice->CreateShaderResourceView(stTexture.Get(), &stSrv, View(nView));
	const std::wstring strName = L"EngineNext.Texture." + std::to_wstring(nView);
	(void)stTexture->SetName(strName.c_str());
	arrTextures.push_back(std::move(stTexture));
	arrTextureUploads.push_back(std::move(stUpload));
	return true;
}

bool VisualRuntime::UploadFloatTexture(const std::vector<const FloatImage *> &arrImages, std::uint32_t nMips, std::uint32_t nView)
{
	if (nMips == 0 || arrImages.empty() || (arrImages.size() != nMips && arrImages.size() != nMips * 6))
	{
		return Fail("Invalid environment subresources");
	}
	const std::uint32_t nFaces = static_cast<std::uint32_t>(arrImages.size()) / nMips;
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
	stDescription.Width = arrImages[0]->nWidth;
	stDescription.Height = arrImages[0]->nHeight;
	stDescription.DepthOrArraySize = static_cast<UINT16>(nFaces);
	stDescription.MipLevels = static_cast<UINT16>(nMips);
	stDescription.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
	stDescription.SampleDesc.Count = 1;
	const D3D12_HEAP_PROPERTIES stDefault = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	ComOwner<ID3D12Resource> stTexture;
	if (FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stTexture.Put()))))
	{
		return Fail("Create HDR environment texture");
	}
	std::vector<D3D12_PLACED_SUBRESOURCE_FOOTPRINT> arrFootprints(arrImages.size());
	UINT64 nTotalBytes = 0;
	stDevice->GetCopyableFootprints(&stDescription, 0, static_cast<UINT>(arrImages.size()), 0, arrFootprints.data(), nullptr, nullptr, &nTotalBytes);
	if (nTotalBytes > MAX_TEXTURE_UPLOAD_BYTES - nTextureUploadBytes)
	{
		return Fail("Environment upload budget exceeded");
	}
	nTextureUploadBytes += nTotalBytes;
	const D3D12_RESOURCE_DESC stUploadDescription = BufferDescription(nTotalBytes);
	const D3D12_HEAP_PROPERTIES stUploadHeap = HeapProperties(D3D12_HEAP_TYPE_UPLOAD);
	ComOwner<ID3D12Resource> stUpload;
	if (FAILED(stDevice->CreateCommittedResource(&stUploadHeap, D3D12_HEAP_FLAG_NONE, &stUploadDescription, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stUpload.Put()))))
	{
		return Fail("Create HDR texture upload");
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map HDR texture upload");
	}
	ID3D12GraphicsCommandList *pList = arrFrames[0].stGraphicsList.Get();
	for (std::uint32_t nSubresource = 0; nSubresource < arrImages.size(); ++nSubresource)
	{
		const FloatImage &stImage = *arrImages[nSubresource];
		for (std::uint32_t nRow = 0; nRow < stImage.nHeight; ++nRow)
		{
			std::memcpy(static_cast<std::uint8_t *>(pMapped) + arrFootprints[nSubresource].Offset + static_cast<std::size_t>(nRow) * arrFootprints[nSubresource].Footprint.RowPitch,
						stImage.arrPixels.data() + static_cast<std::size_t>(nRow) * stImage.nWidth, static_cast<std::size_t>(stImage.nWidth) * sizeof(stImage.arrPixels[0]));
		}
		D3D12_TEXTURE_COPY_LOCATION stTarget{};
		stTarget.pResource = stTexture.Get();
		stTarget.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
		stTarget.SubresourceIndex = nSubresource;
		D3D12_TEXTURE_COPY_LOCATION stSource{};
		stSource.pResource = stUpload.Get();
		stSource.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
		stSource.PlacedFootprint = arrFootprints[nSubresource];
		pList->CopyTextureRegion(&stTarget, 0, 0, 0, &stSource, nullptr);
	}
	stUpload->Unmap(0, nullptr);
	D3D12_RESOURCE_BARRIER stBarrier{};
	stBarrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
	stBarrier.Transition.pResource = stTexture.Get();
	stBarrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
	stBarrier.Transition.StateAfter = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE | D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
	stBarrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
	pList->ResourceBarrier(1, &stBarrier);
	D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
	stSrv.Format = stDescription.Format;
	stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSrv.ViewDimension = nFaces == 6 ? D3D12_SRV_DIMENSION_TEXTURECUBE : D3D12_SRV_DIMENSION_TEXTURE2D;
	if (nFaces == 6)
	{
		stSrv.TextureCube.MipLevels = nMips;
	}
	else
	{
		stSrv.Texture2D.MipLevels = nMips;
	}
	stDevice->CreateShaderResourceView(stTexture.Get(), &stSrv, View(nView));
	const std::wstring strName = L"EngineNext.Texture." + std::to_wstring(nView);
	(void)stTexture->SetName(strName.c_str());
	arrTextures.push_back(std::move(stTexture));
	arrTextureUploads.push_back(std::move(stUpload));
	return true;
}

bool VisualRuntime::UploadEnvironmentImportance(const EnvironmentImportance &stImportance)
{
	const std::uint64_t nBytes = stImportance.arrEntries.size() * sizeof(EnvironmentAliasEntry);
	if (stImportance.arrEntries.empty() || nBytes > MAX_TEXTURE_UPLOAD_BYTES - nTextureUploadBytes)
	{
		return Fail("Environment importance upload budget exceeded");
	}
	const D3D12_RESOURCE_DESC stDescription = BufferDescription(nBytes);
	const D3D12_HEAP_PROPERTIES stDefault = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	const D3D12_HEAP_PROPERTIES stUploadHeap = HeapProperties(D3D12_HEAP_TYPE_UPLOAD);
	ComOwner<ID3D12Resource> stUpload;
	if (FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stDescription,
												 D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(stEnvironmentAlias.Put()))) ||
		FAILED(stDevice->CreateCommittedResource(&stUploadHeap, D3D12_HEAP_FLAG_NONE, &stDescription,
												 D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stUpload.Put()))))
	{
		return Fail("Create environment importance buffers");
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map environment importance upload");
	}
	std::memcpy(pMapped, stImportance.arrEntries.data(), static_cast<std::size_t>(nBytes));
	stUpload->Unmap(0, nullptr);
	ID3D12GraphicsCommandList *pList = arrFrames[0].stGraphicsList.Get();
	D3D12_RESOURCE_BARRIER stBarrier{};
	stBarrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
	stBarrier.Transition.pResource = stEnvironmentAlias.Get();
	stBarrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COMMON;
	stBarrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_DEST;
	stBarrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
	pList->ResourceBarrier(1, &stBarrier);
	pList->CopyBufferRegion(stEnvironmentAlias.Get(), 0, stUpload.Get(), 0, nBytes);
	stBarrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
	stBarrier.Transition.StateAfter = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE | D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
	pList->ResourceBarrier(1, &stBarrier);
	D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
	stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
	stSrv.Buffer.NumElements = static_cast<UINT>(stImportance.arrEntries.size());
	stSrv.Buffer.StructureByteStride = sizeof(EnvironmentAliasEntry);
	stDevice->CreateShaderResourceView(stEnvironmentAlias.Get(), &stSrv, View(ENVIRONMENT_ALIAS_VIEW));
	(void)stEnvironmentAlias->SetName(L"EngineNext.EnvironmentImportance");
	nEnvironmentAliasEntries = stSrv.Buffer.NumElements;
	nEnvironmentAliasBytes = nBytes;
	nTextureUploadBytes += nBytes;
	arrTextureUploads.push_back(std::move(stUpload));
	return true;
}

bool VisualRuntime::CreateEnvironment()
{
	const std::chrono::steady_clock::time_point stStart = std::chrono::steady_clock::now();
	EnvironmentLighting stEnvironment;
	std::string strError;
	if (!GenerateEnvironmentLighting(EnvironmentConfig{}, stEnvironment, strError))
	{
		return Fail(strError);
	}
	nEnvironmentMips = static_cast<std::uint32_t>(stEnvironment.arrPrefilteredMips.size());
	std::vector<const FloatImage *> arrIrradiance;
	std::vector<const FloatImage *> arrPrefiltered;
	for (std::uint32_t nFace = 0; nFace < 6; ++nFace)
	{
		arrIrradiance.push_back(&stEnvironment.arrIrradiance[nFace]);
		for (std::uint32_t nMip = 0; nMip < nEnvironmentMips; ++nMip)
		{
			arrPrefiltered.push_back(&stEnvironment.arrPrefilteredMips[nMip][nFace]);
		}
	}
	if (!UploadFloatTexture(arrIrradiance, 1, ENVIRONMENT_VIEW_START) ||
		!UploadFloatTexture(arrPrefiltered, nEnvironmentMips, ENVIRONMENT_VIEW_START + 1) ||
		!UploadFloatTexture({ &stEnvironment.stBrdfLut }, 1, ENVIRONMENT_VIEW_START + 2))
	{
		return false;
	}
	if (bMaterialExtensions)
	{
		EnvironmentImportance stImportance;
		if (!BuildEnvironmentImportance(stEnvironment.arrPrefilteredMips[0], stImportance, strError))
		{
			return Fail(strError);
		}
		if (!UploadEnvironmentImportance(stImportance))
		{
			return false;
		}
	}
	dEnvironmentBuildMsec = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - stStart).count();
	return true;
}

bool VisualRuntime::ResolveNetworkBindings()
{
	if (!stConfig.bConnect)
	{
		return true;
	}
	std::map<std::uint64_t, const Assets::SceneEntity *> mapEntities;
	for (const Assets::SceneEntity &stEntity : stNetworkScene.arrEntities)
	{
		mapEntities.emplace(static_cast<std::uint64_t>(stEntity.nEntityId), &stEntity);
	}
	for (GpuDraw &stDraw : arrDraws)
	{
		std::map<std::uint64_t, const Assets::SceneEntity *>::const_iterator itEntity = mapEntities.find(stDraw.nEntityId);
		if (itEntity == mapEntities.end())
		{
			return Fail("Draw entity is missing from simulation scene");
		}
		const Assets::SceneEntity *pEntity = itEntity->second;
		while (pEntity->strGameplayKind != "player_spawn" && pEntity->nParentEntityId != 0)
		{
			itEntity = mapEntities.find(static_cast<std::uint64_t>(pEntity->nParentEntityId));
			if (itEntity == mapEntities.end())
			{
				return Fail("Simulation ancestor is missing");
			}
			pEntity = itEntity->second;
		}
		if (pEntity->strGameplayKind != "player_spawn")
		{
			continue;
		}
		stDraw.nSimulationEntityId = static_cast<std::uint64_t>(pEntity->nEntityId);
		stDraw.arrSimulationOrigin = pEntity->stTransform.arrTranslation;
		while (pEntity->nParentEntityId != 0)
		{
			itEntity = mapEntities.find(static_cast<std::uint64_t>(pEntity->nParentEntityId));
			if (itEntity == mapEntities.end())
			{
				return Fail("Simulation ancestor is missing");
			}
			pEntity = itEntity->second;
			const Assets::Transform &stTransform = pEntity->stTransform;
			const double dX = stTransform.arrRotation[0];
			const double dY = stTransform.arrRotation[1];
			const double dZ = stTransform.arrRotation[2];
			const double dW = stTransform.arrRotation[3];
			std::array<double, 9> arrParent{
				1 - 2 * (dY * dY + dZ * dZ), 2 * (dX * dY + dW * dZ), 2 * (dX * dZ - dW * dY),
				2 * (dX * dY - dW * dZ), 1 - 2 * (dX * dX + dZ * dZ), 2 * (dY * dZ + dW * dX),
				2 * (dX * dZ + dW * dY), 2 * (dY * dZ - dW * dX), 1 - 2 * (dX * dX + dY * dY)
			};
			for (std::size_t nColumn = 0; nColumn < 3; ++nColumn)
			{
				for (std::size_t nRow = 0; nRow < 3; ++nRow)
				{
					arrParent[nColumn * 3 + nRow] *= stTransform.arrScale[nColumn];
				}
			}
			std::array<double, 9> arrCombined{};
			for (std::size_t nColumn = 0; nColumn < 3; ++nColumn)
			{
				for (std::size_t nRow = 0; nRow < 3; ++nRow)
				{
					for (std::size_t nInner = 0; nInner < 3; ++nInner)
					{
						arrCombined[nColumn * 3 + nRow] += arrParent[nInner * 3 + nRow] * stDraw.arrSimulationParent[nColumn * 3 + nInner];
					}
				}
			}
			for (double dComponent : arrCombined)
			{
				if (!std::isfinite(dComponent) || !std::isfinite(static_cast<float>(dComponent)))
				{
					return Fail("Simulation parent transform exceeds binary32 range");
				}
			}
			stDraw.arrSimulationParent = arrCombined;
		}
	}
	return true;
}

bool VisualRuntime::CreateSceneMesh()
{
	std::vector<MeshVertex> arrVertices;
	std::vector<std::uint32_t> arrIndices;
	std::vector<std::vector<GpuPrimitive>> arrPrimitiveLookup;
	FrameContext &stFrame = arrFrames[0];
	if (FAILED(stFrame.stGraphicsAllocator->Reset()) || FAILED(stFrame.stGraphicsList->Reset(stFrame.stGraphicsAllocator.Get(), nullptr)))
	{
		return Fail("Reset scene upload list");
	}
	D3D12_DESCRIPTOR_HEAP_DESC stSamplerDescription{};
	stSamplerDescription.Type = D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER;
	stSamplerDescription.NumDescriptors = MAX_MATERIALS * MATERIAL_TEXTURE_COUNT;
	stSamplerDescription.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
	if (FAILED(stDevice->CreateDescriptorHeap(&stSamplerDescription, IID_PPV_ARGS(stSamplerHeap.Put()))))
	{
		return Fail("Create material sampler heap");
	}
	const UINT nSamplerStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
	for (std::size_t nAssetIndex = 0; nAssetIndex < stRenderScene.arrAssets.size(); ++nAssetIndex)
	{
		const RenderAsset &stAsset = stRenderScene.arrAssets[nAssetIndex];
		const std::uint32_t nMaterialBase = static_cast<std::uint32_t>(arrMaterials.size());
		if (stRenderScene.nGpuFormatVersion == 2 && stAsset.stTextureCook.arrMaterials.size() != stAsset.stMesh.arrMaterials.size())
		{
			return Fail("Cooked material texture bindings do not match source materials");
		}
		if (stAsset.stMesh.arrMaterials.size() > MAX_MATERIALS - arrMaterials.size())
		{
			return Fail("Material descriptor budget exceeded");
		}
		for (const MaterialData &stMaterial : stAsset.stMesh.arrMaterials)
		{
			const std::uint32_t nMaterial = static_cast<std::uint32_t>(arrMaterials.size());
			const std::uint32_t nSourceMaterial = nMaterial - nMaterialBase;
			const std::uint32_t nViewStart = MATERIAL_VIEW_START + nMaterial * MATERIAL_TEXTURE_COUNT;
			const std::array<std::int32_t, 5> arrTextureIds{ stMaterial.nBaseColorTexture, stMaterial.nMetallicRoughnessTexture, stMaterial.nNormalTexture, stMaterial.nOcclusionTexture, stMaterial.nEmissiveTexture };
			for (std::uint32_t nSlot = 0; nSlot < MATERIAL_TEXTURE_COUNT; ++nSlot)
			{
				const std::int32_t nTexture = arrTextureIds[nSlot];
				std::vector<MipLevel> arrMips;
				const std::vector<MipLevel> *pUploadMips = &arrMips;
				Assets::Diagnostics arrDiagnostics;
				const bool bSrgb = nSlot == 0 || nSlot == 4;
				D3D12_SAMPLER_DESC stSampler{};
				stSampler.Filter = D3D12_FILTER_ANISOTROPIC;
				stSampler.MaxAnisotropy = 16;
				stSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_WRAP;
				stSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_WRAP;
				stSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_WRAP;
				stSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
				stSampler.MaxLOD = D3D12_FLOAT32_MAX;
				if (nTexture >= 0)
				{
					const TextureData &stTexture = stAsset.stMesh.arrTextures[static_cast<std::size_t>(nTexture)];
					if (stRenderScene.nGpuFormatVersion == 2)
					{
						const std::int32_t nVariant = stAsset.stTextureCook.arrMaterials[nSourceMaterial].arrVariants[nSlot];
						if (nVariant < 0 || static_cast<std::size_t>(nVariant) >= stAsset.stTextureCook.arrVariants.size())
						{
							return Fail("Cooked texture variant index is invalid");
						}
						const CookedTextureVariant &stVariant = stAsset.stTextureCook.arrVariants[static_cast<std::size_t>(nVariant)];
						const ImageSemantic eExpectedSemantic = nSlot == 2 ? ImageSemantic::Normal : (bSrgb ? ImageSemantic::Srgb : ImageSemantic::Linear);
						const TextureAlphaPolicy eExpectedAlpha = nSlot == 4 || (nSlot == 0 && stMaterial.eAlphaMode == AlphaMode::Opaque) ? TextureAlphaPolicy::Ignore : TextureAlphaPolicy::Preserve;
						if (stVariant.nImage != stTexture.nImage || stVariant.eSemantic != eExpectedSemantic || stVariant.eAlphaPolicy != eExpectedAlpha || stVariant.arrMips.empty())
						{
							return Fail("Cooked texture variant semantics differ from its material slot");
						}
						pUploadMips = &stVariant.arrMips;
					}
					else
					{
						const EncodedImage &stImage = stAsset.stMesh.arrImages[stTexture.nImage];
						DecodedImage stDecoded;
						if (!DecodeImage(stImage.arrBytes, stImage.strMimeType, stDecoded, arrDiagnostics))
						{
							return Fail(arrDiagnostics.empty() ? "Decode material texture" : arrDiagnostics.front().strMessage);
						}
						if (nSlot == 4 || (nSlot == 0 && stMaterial.eAlphaMode == AlphaMode::Opaque))
						{
							for (std::size_t nAlpha = 3; nAlpha < stDecoded.arrRgba8.size(); nAlpha += 4)
							{
								stDecoded.arrRgba8[nAlpha] = 255;
							}
						}
						if (!BuildMipChain(stDecoded, nSlot == 2 ? ImageSemantic::Normal : (bSrgb ? ImageSemantic::Srgb : ImageSemantic::Linear), arrMips, arrDiagnostics))
						{
							return Fail(arrDiagnostics.empty() ? "Decode material texture" : arrDiagnostics.front().strMessage);
						}
					}
					stSampler.AddressU = stTexture.nWrapS == 33071 ? D3D12_TEXTURE_ADDRESS_MODE_CLAMP : (stTexture.nWrapS == 33648 ? D3D12_TEXTURE_ADDRESS_MODE_MIRROR : D3D12_TEXTURE_ADDRESS_MODE_WRAP);
					stSampler.AddressV = stTexture.nWrapT == 33071 ? D3D12_TEXTURE_ADDRESS_MODE_CLAMP : (stTexture.nWrapT == 33648 ? D3D12_TEXTURE_ADDRESS_MODE_MIRROR : D3D12_TEXTURE_ADDRESS_MODE_WRAP);
					const bool bPointMin = stTexture.nMinFilter == 9728 || stTexture.nMinFilter == 9984 || stTexture.nMinFilter == 9986;
					const bool bPointMag = stTexture.nMagFilter == 9728;
					const bool bPointMip = stTexture.nMinFilter == 9984 || stTexture.nMinFilter == 9985;
					stSampler.Filter = D3D12_ENCODE_BASIC_FILTER(bPointMin ? D3D12_FILTER_TYPE_POINT : D3D12_FILTER_TYPE_LINEAR, bPointMag ? D3D12_FILTER_TYPE_POINT : D3D12_FILTER_TYPE_LINEAR, bPointMip ? D3D12_FILTER_TYPE_POINT : D3D12_FILTER_TYPE_LINEAR, D3D12_FILTER_REDUCTION_TYPE_STANDARD);
					if (stTexture.nMinFilter == 9728 || stTexture.nMinFilter == 9729)
					{
						stSampler.MaxLOD = 0;
					}
				}
				else
				{
					DecodedImage stPixel;
					stPixel.nWidth = 1;
					stPixel.nHeight = 1;
					stPixel.arrRgba8 = nSlot == 2 ? std::vector<std::uint8_t>{ 128, 128, 255, 255 } : std::vector<std::uint8_t>{ 255, 255, 255, 255 };
					arrMips.push_back(std::move(stPixel));
				}
				if (!UploadTexture(*pUploadMips, bSrgb, nViewStart + nSlot))
				{
					return false;
				}
				D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stSamplerHeap->GetCPUDescriptorHandleForHeapStart();
				stHandle.ptr += static_cast<SIZE_T>(nSamplerStride) * (nMaterial * MATERIAL_TEXTURE_COUNT + nSlot);
				stDevice->CreateSampler(&stSampler, stHandle);
			}
			const RuntimeMaterial &stResolved = arrResolvedMaterials[nAssetIndex].arrMaterials[nSourceMaterial];
			arrMaterials.push_back({ stMaterial, nViewStart, { stResolved.fClearcoatFactor, stResolved.fClearcoatRoughness, stResolved.fAnisotropyStrength, stResolved.fAnisotropyRotationRadians } });
		}
		std::vector<GpuPrimitive> arrPrimitives;
		for (const MeshPrimitive &stPrimitive : stAsset.stMesh.arrPrimitives)
		{
			GpuPrimitive stGpu;
			stGpu.nFirstIndex = static_cast<std::uint32_t>(arrIndices.size());
			stGpu.nIndexCount = static_cast<std::uint32_t>(stPrimitive.arrIndices.size());
			stGpu.nBaseVertex = static_cast<std::int32_t>(arrVertices.size());
			stGpu.nMaterial = nMaterialBase + static_cast<std::uint32_t>(stPrimitive.nMaterial);
			arrVertices.insert(arrVertices.end(), stPrimitive.arrVertices.begin(), stPrimitive.arrVertices.end());
			arrIndices.insert(arrIndices.end(), stPrimitive.arrIndices.begin(), stPrimitive.arrIndices.end());
			arrPrimitives.push_back(stGpu);
		}
		arrPrimitiveLookup.push_back(std::move(arrPrimitives));
	}
	for (const RenderInstance &stInstance : stRenderScene.arrInstances)
	{
		const GpuPrimitive &stPrimitive = arrPrimitiveLookup[stInstance.nAsset][stInstance.nPrimitive];
		GpuDraw stDraw;
		stDraw.stPrimitive = stPrimitive;
		stDraw.arrTransform = stInstance.arrTransform;
		stDraw.nEntityId = stInstance.nEntityId;
		stDraw.nSourceAsset = stInstance.nAsset;
		stDraw.nSourcePrimitive = stInstance.nPrimitive;
		stDraw.nSourceNode = stInstance.nNode;
		const std::array<double, 16> &arrWorld = stDraw.arrTransform;
		const double dDeterminant = arrWorld[0] * (arrWorld[5] * arrWorld[10] - arrWorld[9] * arrWorld[6]) - arrWorld[4] * (arrWorld[1] * arrWorld[10] - arrWorld[9] * arrWorld[2]) + arrWorld[8] * (arrWorld[1] * arrWorld[6] - arrWorld[5] * arrWorld[2]);
		if (!std::isfinite(dDeterminant) || dDeterminant == 0)
		{
			return Fail("Render instance has a singular normal transform");
		}
		stDraw.bMirrored = dDeterminant < 0;
		stDraw.arrNormal[0] = static_cast<float>((arrWorld[5] * arrWorld[10] - arrWorld[9] * arrWorld[6]) / dDeterminant);
		stDraw.arrNormal[1] = static_cast<float>((arrWorld[8] * arrWorld[6] - arrWorld[4] * arrWorld[10]) / dDeterminant);
		stDraw.arrNormal[2] = static_cast<float>((arrWorld[4] * arrWorld[9] - arrWorld[8] * arrWorld[5]) / dDeterminant);
		stDraw.arrNormal[4] = static_cast<float>((arrWorld[9] * arrWorld[2] - arrWorld[1] * arrWorld[10]) / dDeterminant);
		stDraw.arrNormal[5] = static_cast<float>((arrWorld[0] * arrWorld[10] - arrWorld[8] * arrWorld[2]) / dDeterminant);
		stDraw.arrNormal[6] = static_cast<float>((arrWorld[8] * arrWorld[1] - arrWorld[0] * arrWorld[9]) / dDeterminant);
		stDraw.arrNormal[8] = static_cast<float>((arrWorld[1] * arrWorld[6] - arrWorld[5] * arrWorld[2]) / dDeterminant);
		stDraw.arrNormal[9] = static_cast<float>((arrWorld[4] * arrWorld[2] - arrWorld[0] * arrWorld[6]) / dDeterminant);
		stDraw.arrNormal[10] = static_cast<float>((arrWorld[0] * arrWorld[5] - arrWorld[4] * arrWorld[1]) / dDeterminant);
		stDraw.arrNormal[15] = 1;
		for (float fComponent : stDraw.arrNormal)
		{
			if (!std::isfinite(fComponent))
			{
				return Fail("Render normal transform exceeds binary32 range");
			}
		}
		arrDraws.push_back(stDraw);
		nSceneTriangles += stPrimitive.nIndexCount / 3;
	}
	if (!ResolveNetworkBindings())
	{
		return false;
	}
	const std::uint64_t nVertexBytes = arrVertices.size() * sizeof(MeshVertex);
	const std::uint64_t nIndexBytes = arrIndices.size() * sizeof(std::uint32_t);
	const D3D12_HEAP_PROPERTIES stDefault = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	const D3D12_HEAP_PROPERTIES stUpload = HeapProperties(D3D12_HEAP_TYPE_UPLOAD);
	const D3D12_RESOURCE_DESC stVertexDesc = BufferDescription(nVertexBytes);
	const D3D12_RESOURCE_DESC stIndexDesc = BufferDescription(nIndexBytes);
	const D3D12_RESOURCE_DESC stUploadDesc = BufferDescription(nVertexBytes + nIndexBytes);
	if (FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stVertexDesc, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stVertices.Put()))) ||
		FAILED(stDevice->CreateCommittedResource(&stDefault, D3D12_HEAP_FLAG_NONE, &stIndexDesc, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stIndices.Put()))) ||
		FAILED(stDevice->CreateCommittedResource(&stUpload, D3D12_HEAP_FLAG_NONE, &stUploadDesc, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stMeshUpload.Put()))))
	{
		return Fail("Create scene geometry buffers");
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stMeshUpload->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map scene geometry upload");
	}
	std::memcpy(pMapped, arrVertices.data(), static_cast<std::size_t>(nVertexBytes));
	std::memcpy(static_cast<std::uint8_t *>(pMapped) + nVertexBytes, arrIndices.data(), static_cast<std::size_t>(nIndexBytes));
	stMeshUpload->Unmap(0, nullptr);
	ID3D12GraphicsCommandList *pList = stFrame.stGraphicsList.Get();
	pList->CopyBufferRegion(stVertices.Get(), 0, stMeshUpload.Get(), 0, nVertexBytes);
	pList->CopyBufferRegion(stIndices.Get(), 0, stMeshUpload.Get(), nVertexBytes, nIndexBytes);
	std::array<D3D12_RESOURCE_BARRIER, 2> arrBarriers{};
	for (std::size_t nIndex = 0; nIndex < arrBarriers.size(); ++nIndex)
	{
		arrBarriers[nIndex].Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
		arrBarriers[nIndex].Transition.pResource = nIndex == 0 ? stVertices.Get() : stIndices.Get();
		arrBarriers[nIndex].Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
		arrBarriers[nIndex].Transition.StateAfter = nIndex == 0 ? D3D12_RESOURCE_STATE_VERTEX_AND_CONSTANT_BUFFER : D3D12_RESOURCE_STATE_INDEX_BUFFER;
		arrBarriers[nIndex].Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
	}
	pList->ResourceBarrier(2, arrBarriers.data());
	if (!CreateEnvironment())
	{
		return false;
	}
	if (FAILED(pList->Close()))
	{
		return Fail("Close scene upload list");
	}
	ID3D12CommandList *pUpload = pList;
	stGraphics.stQueue->ExecuteCommandLists(1, &pUpload);
	if (!stGraphics.Flush())
	{
		return Fail("Wait scene upload completion");
	}
	arrTextureUploads.clear();
	stMeshUpload.Reset();
	stVertexView = { stVertices->GetGPUVirtualAddress(), static_cast<UINT>(nVertexBytes), sizeof(MeshVertex) };
	stIndexView = { stIndices->GetGPUVirtualAddress(), static_cast<UINT>(nIndexBytes), DXGI_FORMAT_R32_UINT };
	(void)stVertices->SetName(L"EngineNext.SceneVertices");
	(void)stIndices->SetName(L"EngineNext.SceneIndices");
	return true;
}

bool VisualRuntime::CreateDeferredPipeline()
{
	const std::vector<std::uint8_t> arrVertex = ReadShader(stConfig.strShaderDirectory, "Deferred.vs.cso");
	const std::vector<std::uint8_t> arrPixel = ReadShader(stConfig.strShaderDirectory, bMaterialExtensions ? "MaterialDeferred.ps.cso" : "Deferred.ps.cso");
	const std::vector<std::uint8_t> arrFullscreen = ReadShader(stConfig.strShaderDirectory, "Lighting.vs.cso");
	const char *pLightingShader = stRenderConfiguration.stReflections.bEnabled ? "ReflectionLighting.ps.cso" : "Lighting.ps.cso";
	if (bMaterialExtensions)
	{
		pLightingShader = stRenderConfiguration.stReflections.bEnabled ? "MaterialReflectionLighting.ps.cso" : "MaterialLighting.ps.cso";
	}
	const std::vector<std::uint8_t> arrLighting = ReadShader(stConfig.strShaderDirectory, pLightingShader);
	const std::vector<std::uint8_t> arrToneMap = ReadShader(stConfig.strShaderDirectory, "ToneMap.ps.cso");
	if (arrVertex.empty() || arrPixel.empty() || arrFullscreen.empty() || arrLighting.empty() || arrToneMap.empty())
	{
		return Fail("Missing deferred shader bundle");
	}
	for (std::uint32_t nPipeline = 0; nPipeline < 2; ++nPipeline)
	{
		std::array<D3D12_DESCRIPTOR_RANGE, 8> arrDescriptorRanges{};
		arrDescriptorRanges[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrDescriptorRanges[0].NumDescriptors = 5;
		arrDescriptorRanges[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER;
		arrDescriptorRanges[1].NumDescriptors = 5;
		arrDescriptorRanges[2].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrDescriptorRanges[2].NumDescriptors = 1;
		arrDescriptorRanges[2].BaseShaderRegister = 5;
		arrDescriptorRanges[3].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrDescriptorRanges[3].NumDescriptors = 3;
		arrDescriptorRanges[3].BaseShaderRegister = 6;
		arrDescriptorRanges[4].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrDescriptorRanges[4].NumDescriptors = 2;
		arrDescriptorRanges[4].BaseShaderRegister = 9;
		arrDescriptorRanges[5].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrDescriptorRanges[5].NumDescriptors = 1;
		arrDescriptorRanges[5].BaseShaderRegister = 11;
		arrDescriptorRanges[6].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrDescriptorRanges[6].NumDescriptors = 2;
		arrDescriptorRanges[6].BaseShaderRegister = 12;
		arrDescriptorRanges[7].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrDescriptorRanges[7].NumDescriptors = 1;
		arrDescriptorRanges[7].BaseShaderRegister = 15;
		std::array<D3D12_ROOT_PARAMETER, 8> arrParameters{};
		arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
		arrParameters[0].Descriptor.ShaderRegister = nPipeline == 0 ? 0 : 1;
		arrParameters[0].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
		for (std::uint32_t nRange = 0; nRange < 2; ++nRange)
		{
			arrParameters[nRange + 1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
			arrParameters[nRange + 1].DescriptorTable.NumDescriptorRanges = 1;
			arrParameters[nRange + 1].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[nRange];
			arrParameters[nRange + 1].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
		}
		D3D12_ROOT_SIGNATURE_DESC stRoot{};
		stRoot.NumParameters = 3;
		if (nPipeline == 1)
		{
			arrParameters[2].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[2];
			arrParameters[3] = arrParameters[2];
			arrParameters[3].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[3];
			arrParameters[4] = arrParameters[2];
			arrParameters[4].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[4];
			arrParameters[5] = arrParameters[2];
			arrParameters[5].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[5];
			stRoot.NumParameters = 6;
			if (bMaterialExtensions)
			{
				arrParameters[6] = arrParameters[2];
				arrParameters[6].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[6];
				arrParameters[7] = arrParameters[2];
				arrParameters[7].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[7];
				stRoot.NumParameters = 8;
			}
		}
		else
		{
			arrParameters[3].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
			arrParameters[3].Descriptor.ShaderRegister = 1;
			arrParameters[3].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
			arrParameters[4] = arrParameters[1];
			arrParameters[4].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[5];
			stRoot.NumParameters = 5;
		}
		D3D12_STATIC_SAMPLER_DESC stEnvironmentSampler{};
		stEnvironmentSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
		stEnvironmentSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stEnvironmentSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stEnvironmentSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stEnvironmentSampler.MaxLOD = D3D12_FLOAT32_MAX;
		stEnvironmentSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
		stEnvironmentSampler.ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
		if (nPipeline == 1)
		{
			stRoot.NumStaticSamplers = 1;
			stRoot.pStaticSamplers = &stEnvironmentSampler;
		}
		stRoot.pParameters = arrParameters.data();
		stRoot.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
		ComOwner<ID3DBlob> stSerialized;
		ComOwner<ID3DBlob> stErrors;
		const HRESULT nResult = D3D12SerializeRootSignature(&stRoot, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put());
		if (FAILED(nResult))
		{
			return Fail("Serialize deferred root signature", nResult);
		}
		ComOwner<ID3D12RootSignature> &stDestination = nPipeline == 0 ? stDeferredRoot : stLightingRoot;
		if (FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stDestination.Put()))))
		{
			return Fail("Create deferred root signature");
		}
	}
	const std::array<D3D12_INPUT_ELEMENT_DESC, 4> arrLayout{ {
			{ "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "NORMAL", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 12, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "TANGENT", 0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 24, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 40, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
	} };
	D3D12_GRAPHICS_PIPELINE_STATE_DESC stPipeline{};
	stPipeline.pRootSignature = stDeferredRoot.Get();
	stPipeline.VS = { arrVertex.data(), arrVertex.size() };
	stPipeline.PS = { arrPixel.data(), arrPixel.size() };
	stPipeline.InputLayout = { arrLayout.data(), static_cast<UINT>(arrLayout.size()) };
	stPipeline.SampleMask = UINT_MAX;
	stPipeline.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
	stPipeline.RasterizerState.CullMode = D3D12_CULL_MODE_BACK;
	stPipeline.RasterizerState.FrontCounterClockwise = TRUE;
	stPipeline.RasterizerState.DepthClipEnable = TRUE;
	stPipeline.DepthStencilState.DepthEnable = TRUE;
	stPipeline.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ALL;
	stPipeline.DepthStencilState.DepthFunc = D3D12_COMPARISON_FUNC_GREATER_EQUAL;
	stPipeline.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
	stPipeline.NumRenderTargets = bMaterialExtensions ? 8U : 6U;
	stPipeline.RTVFormats[0] = DXGI_FORMAT_R8G8B8A8_UNORM_SRGB;
	stPipeline.RTVFormats[1] = DXGI_FORMAT_R16G16B16A16_FLOAT;
	stPipeline.RTVFormats[2] = DXGI_FORMAT_R8G8B8A8_UNORM;
	stPipeline.RTVFormats[3] = DXGI_FORMAT_R16G16B16A16_FLOAT;
	stPipeline.RTVFormats[4] = DXGI_FORMAT_R32G32B32A32_FLOAT;
	stPipeline.RTVFormats[5] = DXGI_FORMAT_R32_UINT;
	stPipeline.RTVFormats[6] = bMaterialExtensions ? DXGI_FORMAT_R32G32B32A32_FLOAT : DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[7] = bMaterialExtensions ? DXGI_FORMAT_R16G16B16A16_FLOAT : DXGI_FORMAT_UNKNOWN;
	for (std::uint32_t nTarget = 0; nTarget < stPipeline.NumRenderTargets; ++nTarget)
	{
		stPipeline.BlendState.RenderTarget[nTarget].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
	}
	stPipeline.DSVFormat = DXGI_FORMAT_D32_FLOAT;
	stPipeline.SampleDesc.Count = 1;
	if (FAILED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(stDeferredPipeline.Put()))))
	{
		return Fail("Create deferred geometry PSO");
	}
	stPipeline.RasterizerState.FrontCounterClockwise = FALSE;
	if (FAILED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(stMirroredPipeline.Put()))))
	{
		return Fail("Create mirrored geometry PSO");
	}
	stPipeline.RasterizerState.FrontCounterClockwise = TRUE;
	stPipeline.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
	if (FAILED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(stDoubleSidedPipeline.Put()))))
	{
		return Fail("Create double-sided PSO");
	}
	stPipeline.RasterizerState.FrontCounterClockwise = FALSE;
	if (FAILED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(stMirroredDoubleSidedPipeline.Put()))))
	{
		return Fail("Create mirrored double-sided PSO");
	}
	stPipeline.RasterizerState.FrontCounterClockwise = TRUE;
	stPipeline.pRootSignature = stLightingRoot.Get();
	stPipeline.VS = { arrFullscreen.data(), arrFullscreen.size() };
	stPipeline.PS = { arrLighting.data(), arrLighting.size() };
	stPipeline.InputLayout = {};
	stPipeline.DepthStencilState.DepthEnable = FALSE;
	stPipeline.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ZERO;
	stPipeline.NumRenderTargets = stRenderConfiguration.stReflections.bEnabled ? 2U : 1U;
	stPipeline.RTVFormats[0] = HDR_FORMAT;
	stPipeline.RTVFormats[1] = stRenderConfiguration.stReflections.bEnabled ? HDR_FORMAT : DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[2] = DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[3] = DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[4] = DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[5] = DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[6] = DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[7] = DXGI_FORMAT_UNKNOWN;
	stPipeline.DSVFormat = DXGI_FORMAT_UNKNOWN;
	if (FAILED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(stLightingPipeline.Put()))))
	{
		return Fail("Create lighting PSO");
	}
	std::array<D3D12_DESCRIPTOR_RANGE, 4> arrToneRanges{};
	std::array<D3D12_ROOT_PARAMETER, 5> arrToneParameters{};
	arrToneParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrToneParameters[0].Descriptor.ShaderRegister = 1;
	for (std::uint32_t nRange = 0; nRange < 4; ++nRange)
	{
		arrToneRanges[nRange].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		arrToneRanges[nRange].NumDescriptors = 1;
		arrToneRanges[nRange].BaseShaderRegister = nRange;
		arrToneParameters[nRange + 1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrToneParameters[nRange + 1].DescriptorTable.NumDescriptorRanges = 1;
		arrToneParameters[nRange + 1].DescriptorTable.pDescriptorRanges = &arrToneRanges[nRange];
	}
	D3D12_STATIC_SAMPLER_DESC stToneSampler{};
	stToneSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
	stToneSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stToneSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stToneSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stToneSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
	stToneSampler.MaxLOD = D3D12_FLOAT32_MAX;
	D3D12_ROOT_SIGNATURE_DESC stToneRoot{};
	stToneRoot.NumParameters = static_cast<UINT>(arrToneParameters.size());
	stToneRoot.pParameters = arrToneParameters.data();
	stToneRoot.NumStaticSamplers = 1;
	stToneRoot.pStaticSamplers = &stToneSampler;
	ComOwner<ID3DBlob> stToneSerialized;
	ComOwner<ID3DBlob> stToneErrors;
	if (FAILED(D3D12SerializeRootSignature(&stToneRoot, D3D_ROOT_SIGNATURE_VERSION_1, stToneSerialized.Put(), stToneErrors.Put())) ||
		FAILED(stDevice->CreateRootSignature(0, stToneSerialized->GetBufferPointer(), stToneSerialized->GetBufferSize(), IID_PPV_ARGS(stToneMapRoot.Put()))))
	{
		return Fail("Create post-process tone mapping root");
	}
	stPipeline.pRootSignature = stToneMapRoot.Get();
	stPipeline.PS = { arrToneMap.data(), arrToneMap.size() };
	stPipeline.NumRenderTargets = 1;
	stPipeline.RTVFormats[1] = DXGI_FORMAT_UNKNOWN;
	stPipeline.RTVFormats[0] = COLOR_FORMAT;
	return SUCCEEDED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(stToneMapPipeline.Put()))) || Fail("Create tone mapping PSO");
}

ID3D12Resource *VisualRuntime::CurrentHdrResource(std::uint32_t nFrame) const
{
	if (stForwardEffects.bVolume || stForwardEffects.bTransparency)
	{
		return arrFrames[nFrame].stForwardHdr.Get();
	}
	return stRenderConfiguration.stReflections.bEnabled ? arrFrames[nFrame].stReflectedHdr.Get() : arrFrames[nFrame].stHdr.Get();
}

std::uint32_t VisualRuntime::CurrentHdrView() const
{
	if (stForwardEffects.bVolume || stForwardEffects.bTransparency)
	{
		return FORWARD_HDR_VIEW;
	}
	return stRenderConfiguration.stReflections.bEnabled ? REFLECTION_OUTPUT_VIEW : 7U;
}

bool VisualRuntime::CreateForwardTargets()
{
	nForwardBytes = 0;
	if (!bSceneMode || (!stForwardEffects.bVolume && !stForwardEffects.bTransparency))
	{
		return true;
	}
	const D3D12_HEAP_PROPERTIES stHeap = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	for (std::uint32_t nFrame = 0; nFrame < FRAME_COUNT; ++nFrame)
	{
		if (!stForwardEffects.bVolume)
		{
			D3D12_SHADER_RESOURCE_VIEW_DESC stNullVolume{};
			stNullVolume.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
			stNullVolume.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE3D;
			stNullVolume.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stNullVolume.Texture3D.MipLevels = 1;
			stDevice->CreateShaderResourceView(nullptr, &stNullVolume, View(nFrame * FRAME_VIEW_COUNT + VOLUME_INTEGRAL_VIEW));
			stDevice->CreateShaderResourceView(nullptr, &stNullVolume, View(nFrame * FRAME_VIEW_COUNT + VOLUME_HISTORY_WRITE_VIEW));
		}
		for (std::uint32_t nTarget = 0; nTarget < (stForwardEffects.bTransparency ? 2U : 1U); ++nTarget)
		{
			D3D12_RESOURCE_DESC stDescription{};
			stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
			stDescription.Width = nWidth;
			stDescription.Height = nHeight;
			stDescription.DepthOrArraySize = 1;
			stDescription.MipLevels = 1;
			stDescription.SampleDesc.Count = 1;
			stDescription.Format = nTarget == 0 ? HDR_FORMAT : DXGI_FORMAT_R8_UNORM;
			stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
			if (nTarget == 0)
			{
				stDescription.Flags |= D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
			}
			ComOwner<ID3D12Resource> &stTarget = nTarget == 0 ? arrFrames[nFrame].stForwardHdr : arrFrames[nFrame].stReactiveMask;
			D3D12_CLEAR_VALUE stClear{};
			stClear.Format = stDescription.Format;
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON, &stClear, IID_PPV_ARGS(stTarget.Put()))))
			{
				return Fail("Create forward HDR or reactive target");
			}
			nForwardBytes += stDevice->GetResourceAllocationInfo(0, 1, &stDescription).SizeInBytes;
			const std::wstring strName = (nTarget == 0 ? L"EngineNext.ForwardHdr." : L"EngineNext.ReactiveMask.") + std::to_wstring(nFrame);
			(void)stTarget->SetName(strName.c_str());
			stDevice->CreateRenderTargetView(stTarget.Get(), nullptr, Rtv(FRAME_COUNT * (10 + nTarget) + nFrame));
			D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
			stSrv.Format = stDescription.Format;
			stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
			stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stSrv.Texture2D.MipLevels = 1;
			const std::uint32_t nView = nFrame * FRAME_VIEW_COUNT + (nTarget == 0 ? FORWARD_HDR_VIEW : REACTIVE_MASK_VIEW);
			stDevice->CreateShaderResourceView(stTarget.Get(), &stSrv, View(nView));
			if (nTarget == 0)
			{
				D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
				stUav.Format = stDescription.Format;
				stUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
				stDevice->CreateUnorderedAccessView(stTarget.Get(), nullptr, &stUav, View(nView + 1));
			}
		}
	}
	return true;
}

bool VisualRuntime::CreateVolumeTargets()
{
	nVolumeBytes = 0;
	if (!bSceneMode || !stForwardEffects.bVolume)
	{
		return true;
	}
	Assets::Diagnostics arrDiagnostics;
	if (!BuildVolumeGrid(stRenderConfiguration.stCamera, nWidth, nHeight, stRenderConfiguration.stVolume, stVolumeGrid, arrDiagnostics))
	{
		return Fail(arrDiagnostics.empty() ? "Build volume grid" : arrDiagnostics.back().strMessage);
	}
	const D3D12_HEAP_PROPERTIES stHeap = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	D3D12_RESOURCE_DESC stDescription{};
	stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE3D;
	stDescription.Width = stVolumeGrid.nWidth;
	stDescription.Height = stVolumeGrid.nHeight;
	stDescription.DepthOrArraySize = static_cast<UINT16>(stVolumeGrid.nDepth);
	stDescription.MipLevels = 1;
	stDescription.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
	stDescription.SampleDesc.Count = 1;
	stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
	D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
	stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE3D;
	stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSrv.Texture3D.MipLevels = 1;
	D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
	stUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE3D;
	stUav.Texture3D.WSize = stVolumeGrid.nDepth;
	for (std::uint32_t nFrame = 0; nFrame < FRAME_COUNT; ++nFrame)
	{
		for (std::uint32_t nTarget = 0; nTarget < 4; ++nTarget)
		{
			stDescription.Format = nTarget == 3 ? HDR_FORMAT : DXGI_FORMAT_R32G32B32A32_FLOAT;
			ComOwner<ID3D12Resource> &stTarget = arrFrames[nFrame].arrVolume[nTarget];
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(stTarget.Put()))))
			{
				return Fail("Create froxel texture");
			}
			nVolumeBytes += stDevice->GetResourceAllocationInfo(0, 1, &stDescription).SizeInBytes;
			const std::wstring strName = L"EngineNext.Volume." + std::to_wstring(nFrame) + L"." + std::to_wstring(nTarget);
			(void)stTarget->SetName(strName.c_str());
			stSrv.Format = stDescription.Format;
			stUav.Format = stDescription.Format;
			const std::uint32_t nView = nFrame * FRAME_VIEW_COUNT + VOLUME_MEDIUM_VIEW + nTarget * 2;
			stDevice->CreateShaderResourceView(stTarget.Get(), &stSrv, View(nView));
			stDevice->CreateUnorderedAccessView(stTarget.Get(), nullptr, &stUav, View(nView + 1));
		}
	}
	D3D12_DESCRIPTOR_HEAP_DESC stClearDescription{};
	stClearDescription.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
	stClearDescription.NumDescriptors = 2;
	if (FAILED(stDevice->CreateDescriptorHeap(&stClearDescription, IID_PPV_ARGS(stVolumeClearHeap.Put()))))
	{
		return Fail("Create volume history clear views");
	}
	stDescription.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
	stUav.Format = stDescription.Format;
	for (std::uint32_t nHistory = 0; nHistory < 2; ++nHistory)
	{
		if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(arrVolumeHistory[nHistory].Put()))))
		{
			return Fail("Create froxel history texture");
		}
		nVolumeBytes += stDevice->GetResourceAllocationInfo(0, 1, &stDescription).SizeInBytes;
		const std::wstring strName = L"EngineNext.VolumeHistory." + std::to_wstring(nHistory);
		(void)arrVolumeHistory[nHistory]->SetName(strName.c_str());
		D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stVolumeClearHeap->GetCPUDescriptorHandleForHeapStart();
		stHandle.ptr += static_cast<SIZE_T>(nHistory) * nViewStride;
		stDevice->CreateUnorderedAccessView(arrVolumeHistory[nHistory].Get(), nullptr, &stUav, stHandle);
	}
	nVolumeRead = 0;
	bVolumeHistoryReady = false;
	return true;
}

bool VisualRuntime::CreateVolumePipeline()
{
	if (!stForwardEffects.bVolume)
	{
		return true;
	}
	std::array<D3D12_DESCRIPTOR_RANGE, 7> arrDescriptorRanges{};
	std::array<D3D12_ROOT_PARAMETER, 10> arrParameters{};
	arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
	arrParameters[0].Constants.Num32BitValues = 16;
	for (std::uint32_t nBuffer = 1; nBuffer < 3; ++nBuffer)
	{
		arrParameters[nBuffer].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
		arrParameters[nBuffer].Descriptor.ShaderRegister = nBuffer;
	}
	for (std::uint32_t nRange = 0; nRange < arrDescriptorRanges.size(); ++nRange)
	{
		D3D12_DESCRIPTOR_RANGE &stRange = arrDescriptorRanges[nRange];
		stRange.RangeType = nRange < 5 ? D3D12_DESCRIPTOR_RANGE_TYPE_SRV : D3D12_DESCRIPTOR_RANGE_TYPE_UAV;
		stRange.NumDescriptors = 1;
		stRange.BaseShaderRegister = nRange < 5 ? nRange : nRange - 5;
		arrParameters[nRange + 3].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nRange + 3].DescriptorTable.NumDescriptorRanges = 1;
		arrParameters[nRange + 3].DescriptorTable.pDescriptorRanges = &stRange;
	}
	D3D12_STATIC_SAMPLER_DESC stSampler{};
	stSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
	stSampler.AddressU = stSampler.AddressV = stSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
	stSampler.MaxLOD = D3D12_FLOAT32_MAX;
	D3D12_ROOT_SIGNATURE_DESC stDescription{};
	stDescription.NumParameters = static_cast<UINT>(arrParameters.size());
	stDescription.pParameters = arrParameters.data();
	stDescription.NumStaticSamplers = 1;
	stDescription.pStaticSamplers = &stSampler;
	ComOwner<ID3DBlob> stSerialized;
	ComOwner<ID3DBlob> stErrors;
	if (FAILED(D3D12SerializeRootSignature(&stDescription, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put())) ||
		FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stVolumeRoot.Put()))))
	{
		return Fail("Create volume root signature");
	}
	const std::array<const char *, 5> arrNames{ "VolumeInject.cs.cso", "VolumeLight.cs.cso", "VolumeTemporal.cs.cso", "VolumeIntegrate.cs.cso", "VolumeComposite.cs.cso" };
	for (std::size_t nPipeline = 0; nPipeline < arrNames.size(); ++nPipeline)
	{
		const std::vector<std::uint8_t> arrShader = ReadShader(stConfig.strShaderDirectory, arrNames[nPipeline]);
		if (arrShader.empty())
		{
			return Fail("Missing volume shader");
		}
		D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
		stPipeline.pRootSignature = stVolumeRoot.Get();
		stPipeline.CS = { arrShader.data(), arrShader.size() };
		if (FAILED(stDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(arrVolumePipelines[nPipeline].Put()))))
		{
			return Fail("Create volume compute pipeline");
		}
	}
	return true;
}

bool VisualRuntime::UpdateEffectTransforms()
{
	if (!stForwardEffects.bVolume && stRenderConfiguration.arrParticles.empty())
	{
		return true;
	}
	Assets::SceneDocument stScene = stNetworkScene;
	for (Assets::SceneEntity &stEntity : stScene.arrEntities)
	{
		for (const Runtime::ClientEntitySnapshot &stSnapshot : stClientSnapshot.arrEntities)
		{
			if (stSnapshot.stEntityId.nValue == static_cast<std::uint64_t>(stEntity.nEntityId))
			{
				stEntity.stTransform.arrTranslation = { stSnapshot.stState.vPosition.fX, stSnapshot.stState.vPosition.fY, stSnapshot.stState.vPosition.fZ };
				break;
			}
		}
	}
	Assets::Diagnostics arrDiagnostics;
	return BuildSceneEntityTransforms(stScene, mapEffectTransforms, arrDiagnostics) ||
			Fail(arrDiagnostics.empty() ? "Resolve effect entity transforms" : arrDiagnostics.back().strMessage);
}

bool VisualRuntime::ResolveEffectOrigin(const std::optional<std::uint64_t> &nEntity, std::array<double, 3> &out_arrOrigin)
{
	out_arrOrigin = {};
	if (!nEntity.has_value())
	{
		return true;
	}
	const std::map<std::uint64_t, std::array<double, 16>>::const_iterator itTransform = mapEffectTransforms.find(*nEntity);
	if (itTransform == mapEffectTransforms.end())
	{
		return Fail("Effect references an entity absent from the scene");
	}
	const std::array<double, 16> &arrWorld = itTransform->second;
	out_arrOrigin = { arrWorld[12], arrWorld[13], arrWorld[14] };
	return true;
}

bool VisualRuntime::UpdateVolumeParameters(std::uint32_t nFrame)
{
	if (!stForwardEffects.bVolume)
	{
		return true;
	}
	FrameContext &stFrame = arrFrames[nFrame];
	const VolumeSettings &stSettings = stRenderConfiguration.stVolume;
	VolumeSettings stResolved = stSettings;
	std::array<LocalVolumeConstants, MAX_LOCAL_VOLUMES> arrLocal{};
	for (std::uint32_t nLocal = 0; nLocal < stSettings.nLocalVolumeCount; ++nLocal)
	{
		LocalVolumeSettings &stVolume = stResolved.arrLocalVolumes[nLocal];
		std::array<double, 3> arrOrigin{};
		if (!ResolveEffectOrigin(stVolume.nEntityId, arrOrigin))
		{
			return false;
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stVolume.arrCenter[nAxis] += arrOrigin[nAxis];
		}
	}
	Assets::Diagnostics arrDiagnostics;
	if (!ValidateVolumeSettings(stResolved, arrDiagnostics))
	{
		return Fail(arrDiagnostics.empty() ? "Resolved volume bounds exceed GPU precision" : arrDiagnostics.back().strMessage);
	}
	for (std::uint32_t nLocal = 0; nLocal < stResolved.nLocalVolumeCount; ++nLocal)
	{
		const LocalVolumeSettings &stVolume = stResolved.arrLocalVolumes[nLocal];
		LocalVolumeConstants &stLocal = arrLocal[nLocal];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stLocal.arrCenterShape[nAxis] = static_cast<float>(stVolume.arrCenter[nAxis]);
			stLocal.arrExtentEdge[nAxis] = static_cast<float>(stVolume.arrExtent[nAxis]);
			stLocal.arrAlbedoDensity[nAxis] = static_cast<float>(stVolume.arrAlbedo[nAxis]);
			stLocal.arrEmission[nAxis] = static_cast<float>(stVolume.arrEmission[nAxis]);
		}
		stLocal.arrCenterShape[3] = static_cast<float>(stVolume.eShape);
		stLocal.arrExtentEdge[3] = static_cast<float>(stVolume.dEdgeFraction);
		stLocal.arrAlbedoDensity[3] = static_cast<float>(stVolume.dDensity);
	}
	VolumeHistoryConstants stHistory;
	for (std::size_t nElement = 0; nElement < 16; ++nElement)
	{
		stHistory.arrPreviousView[nElement] = static_cast<float>(stPreviousVolumeCamera.arrView[nElement]);
		stHistory.arrPreviousViewProjection[nElement] = static_cast<float>(stPreviousVolumeCamera.arrViewProjection[nElement]);
	}
	stHistory.arrPreviousGrid = { static_cast<float>(stVolumeGrid.nWidth), static_cast<float>(stVolumeGrid.nHeight), static_cast<float>(stVolumeGrid.nDepth), 0 };
	stHistory.arrPreviousDepth = { static_cast<float>(stVolumeGrid.dNear), static_cast<float>(stVolumeGrid.dFar), 0, 0 };
	stHistory.arrSettings = { static_cast<float>(stSettings.dHistoryWeight), 1, bVolumeHistoryReady && stTemporalFrame.bHistoryValid ? 1.0F : 0.0F, 0.1F };
	GlobalVolumeConstants stGlobal;
	stGlobal.arrDensityHeightFalloff = { static_cast<float>(stSettings.dDensity), static_cast<float>(stSettings.dHeight), static_cast<float>(stSettings.dHeightFalloff), 0 };
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		stGlobal.arrAlbedo[nAxis] = static_cast<float>(stSettings.arrAlbedo[nAxis]);
		stGlobal.arrEmission[nAxis] = static_cast<float>(stSettings.arrEmission[nAxis]);
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stFrame.stVolumeParameters->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map retired volume parameters");
	}
	std::uint8_t *pBytes = static_cast<std::uint8_t *>(pMapped);
	std::memcpy(pBytes, &stHistory, sizeof(stHistory));
	std::memcpy(pBytes + VOLUME_GLOBAL_BYTE_OFFSET, &stGlobal, sizeof(stGlobal));
	std::memcpy(pBytes + VOLUME_LOCAL_BYTE_OFFSET, arrLocal.data(), sizeof(arrLocal));
	stFrame.stVolumeParameters->Unmap(0, nullptr);
	D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
	stSrv.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
	stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE3D;
	stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSrv.Texture3D.MipLevels = 1;
	D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
	stUav.Format = stSrv.Format;
	stUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE3D;
	stUav.Texture3D.WSize = stVolumeGrid.nDepth;
	for (std::uint32_t nHistory = 0; nHistory < 2; ++nHistory)
	{
		ID3D12Resource *pHistory = arrVolumeHistory[nHistory == 0 ? nVolumeRead : 1 - nVolumeRead].Get();
		const std::uint32_t nView = nFrame * FRAME_VIEW_COUNT + VOLUME_HISTORY_READ_VIEW + nHistory * 2;
		stDevice->CreateShaderResourceView(pHistory, &stSrv, View(nView));
		stDevice->CreateUnorderedAccessView(pHistory, nullptr, &stUav, View(nView + 1));
	}
	return true;
}

std::array<float, 16> VisualRuntime::BuildVolumeConstants() const
{
	return {
		static_cast<float>(stVolumeGrid.nWidth), static_cast<float>(stVolumeGrid.nHeight), static_cast<float>(stVolumeGrid.nDepth), static_cast<float>(stRenderConfiguration.stVolume.nLocalVolumeCount),
		static_cast<float>(stVolumeGrid.dNear), static_cast<float>(stVolumeGrid.dFar), static_cast<float>(stVolumeGrid.dLogDepthRatio), static_cast<float>(stVolumeGrid.dInverseLogDepthRatio),
		static_cast<float>(nWidth), static_cast<float>(nHeight), 1.0F / nWidth, 1.0F / nHeight,
		static_cast<float>(stRenderConfiguration.stVolume.dPhaseG), 1, 0, stForwardEffects.bVolume ? 1.0F : 0.0F
	};
}

void VisualRuntime::DrawVolume(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame, PassWork eWork)
{
	const std::uint32_t nStart = nFrame * FRAME_VIEW_COUNT;
	if (eWork == PassWork::VolumePrepare)
	{
		if (!bVolumeHistoryReady)
		{
			D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stVolumeClearHeap->GetCPUDescriptorHandleForHeapStart();
			stHandle.ptr += static_cast<SIZE_T>(nVolumeRead) * nViewStride;
			const std::array<float, 4> arrZero{};
			pList->ClearUnorderedAccessViewFloat(GpuView(nStart + VOLUME_HISTORY_READ_VIEW + 1), stHandle, arrVolumeHistory[nVolumeRead].Get(), arrZero.data(), 0, nullptr);
		}
		return;
	}
	const std::array<float, 16> arrConstants = BuildVolumeConstants();
	pList->SetComputeRootSignature(stVolumeRoot.Get());
	pList->SetComputeRoot32BitConstants(0, 16, arrConstants.data(), 0);
	pList->SetComputeRootConstantBufferView(1, arrFrames[nFrame].stConstants->GetGPUVirtualAddress());
	pList->SetComputeRootConstantBufferView(2, arrFrames[nFrame].stVolumeParameters->GetGPUVirtualAddress());
	std::array<std::uint32_t, 5> arrSources{ VOLUME_SOURCE_VIEW, VOLUME_HISTORY_READ_VIEW, VOLUME_INTEGRAL_VIEW, VOLUME_HISTORY_WRITE_VIEW, 26 };
	std::uint32_t nDestination = VOLUME_HISTORY_WRITE_VIEW + 1;
	std::uint32_t nPipeline = 2;
	UINT nGroupsX = (stVolumeGrid.nWidth + 3) / 4;
	UINT nGroupsY = (stVolumeGrid.nHeight + 3) / 4;
	UINT nGroupsZ = (stVolumeGrid.nDepth + 3) / 4;
	if (eWork == PassWork::VolumeInject)
	{
		nPipeline = 0;
		arrSources[0] = VOLUME_GLOBAL_VIEW;
		arrSources[1] = VOLUME_LOCAL_VIEW;
		nDestination = VOLUME_MEDIUM_VIEW + 1;
		pList->SetComputeRootDescriptorTable(9, GpuView(nStart + VOLUME_EMISSION_VIEW + 1));
	}
	else if (eWork == PassWork::VolumeLight)
	{
		nPipeline = 1;
		arrSources = { VOLUME_MEDIUM_VIEW, VOLUME_EMISSION_VIEW, 8, 9, 26 };
		nDestination = VOLUME_SOURCE_VIEW + 1;
	}
	else if (eWork == PassWork::VolumeIntegrate)
	{
		nPipeline = 3;
		arrSources[0] = VOLUME_HISTORY_WRITE_VIEW;
		nDestination = VOLUME_INTEGRAL_VIEW + 1;
		nGroupsX = (stVolumeGrid.nWidth + 7) / 8;
		nGroupsY = (stVolumeGrid.nHeight + 7) / 8;
		nGroupsZ = 1;
	}
	else if (eWork == PassWork::VolumeComposite)
	{
		nPipeline = 4;
		arrSources[0] = stRenderConfiguration.stReflections.bEnabled ? REFLECTION_OUTPUT_VIEW : 7U;
		arrSources[1] = 6;
		nDestination = FORWARD_HDR_VIEW + 1;
		nGroupsX = (nWidth + 7) / 8;
		nGroupsY = (nHeight + 7) / 8;
		nGroupsZ = 1;
	}
	pList->SetPipelineState(arrVolumePipelines[nPipeline].Get());
	for (std::uint32_t nSource = 0; nSource < arrSources.size(); ++nSource)
	{
		pList->SetComputeRootDescriptorTable(nSource + 3, GpuView(nStart + arrSources[nSource]));
	}
	pList->SetComputeRootDescriptorTable(8, GpuView(nStart + nDestination));
	pList->Dispatch(nGroupsX, nGroupsY, nGroupsZ);
}

bool VisualRuntime::CreateTransparencyPipeline()
{
	const std::vector<std::uint8_t> arrVertex = ReadShader(stConfig.strShaderDirectory, "Transparent.vs.cso");
	const std::vector<std::uint8_t> arrPixel = ReadShader(stConfig.strShaderDirectory, bMaterialExtensions ? "MaterialTransparent.ps.cso" : "Transparent.ps.cso");
	if (arrVertex.empty() || arrPixel.empty())
	{
		return Fail("Missing transparent shader bundle");
	}
	std::array<D3D12_DESCRIPTOR_RANGE, 10> arrDescriptorRanges{};
	arrDescriptorRanges[0] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 5, 0, 0, 0 };
	arrDescriptorRanges[1] = { D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER, 5, 0, 0, 0 };
	arrDescriptorRanges[2] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 5, 0, 0 };
	arrDescriptorRanges[3] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 3, 6, 0, 0 };
	arrDescriptorRanges[4] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 2, 9, 0, 0 };
	arrDescriptorRanges[5] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 11, 0, 0 };
	arrDescriptorRanges[6] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 12, 0, 0 };
	arrDescriptorRanges[7] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 13, 0, 0 };
	arrDescriptorRanges[8] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 14, 0, 0 };
	arrDescriptorRanges[9] = { D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 15, 0, 0 };
	std::array<D3D12_ROOT_PARAMETER, 14> arrParameters{};
	for (std::uint32_t nIndex = 0; nIndex < 2; ++nIndex)
	{
		arrParameters[nIndex].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
		arrParameters[nIndex].Descriptor.ShaderRegister = nIndex;
		arrParameters[nIndex].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
	}
	arrParameters[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
	arrParameters[2].Constants.ShaderRegister = 2;
	arrParameters[2].Constants.Num32BitValues = 4;
	arrParameters[2].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
	arrParameters[3].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
	arrParameters[3].Constants.ShaderRegister = 3;
	arrParameters[3].Constants.Num32BitValues = 16;
	arrParameters[3].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
	for (std::uint32_t nIndex = 0; nIndex < arrDescriptorRanges.size(); ++nIndex)
	{
		arrParameters[nIndex + 4].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nIndex + 4].DescriptorTable.NumDescriptorRanges = 1;
		arrParameters[nIndex + 4].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[nIndex];
		arrParameters[nIndex + 4].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
	}
	D3D12_STATIC_SAMPLER_DESC stEnvironmentSampler{};
	stEnvironmentSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
	stEnvironmentSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stEnvironmentSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stEnvironmentSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stEnvironmentSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
	stEnvironmentSampler.MaxLOD = D3D12_FLOAT32_MAX;
	stEnvironmentSampler.ShaderRegister = 5;
	stEnvironmentSampler.ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
	D3D12_ROOT_SIGNATURE_DESC stRoot{};
	stRoot.NumParameters = bMaterialExtensions ? 14U : 13U;
	stRoot.pParameters = arrParameters.data();
	stRoot.NumStaticSamplers = 1;
	stRoot.pStaticSamplers = &stEnvironmentSampler;
	stRoot.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
	ComOwner<ID3DBlob> stSerialized;
	ComOwner<ID3DBlob> stErrors;
	if (FAILED(D3D12SerializeRootSignature(&stRoot, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put())) ||
		FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stTransparencyRoot.Put()))))
	{
		return Fail("Create transparent root signature");
	}
	const std::array<D3D12_INPUT_ELEMENT_DESC, 4> arrLayout{ {
			{ "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "NORMAL", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 12, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "TANGENT", 0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 24, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 40, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
	} };
	D3D12_GRAPHICS_PIPELINE_STATE_DESC stPipeline{};
	stPipeline.pRootSignature = stTransparencyRoot.Get();
	stPipeline.VS = { arrVertex.data(), arrVertex.size() };
	stPipeline.PS = { arrPixel.data(), arrPixel.size() };
	stPipeline.InputLayout = { arrLayout.data(), static_cast<UINT>(arrLayout.size()) };
	stPipeline.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
	stPipeline.RasterizerState.DepthClipEnable = TRUE;
	stPipeline.DepthStencilState.DepthEnable = TRUE;
	stPipeline.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ZERO;
	stPipeline.DepthStencilState.DepthFunc = D3D12_COMPARISON_FUNC_GREATER_EQUAL;
	stPipeline.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
	stPipeline.SampleMask = UINT_MAX;
	stPipeline.SampleDesc.Count = 1;
	stPipeline.NumRenderTargets = 2;
	stPipeline.RTVFormats[0] = HDR_FORMAT;
	stPipeline.RTVFormats[1] = DXGI_FORMAT_R8_UNORM;
	stPipeline.DSVFormat = DXGI_FORMAT_D32_FLOAT;
	stPipeline.BlendState.IndependentBlendEnable = TRUE;
	D3D12_RENDER_TARGET_BLEND_DESC &stColorBlend = stPipeline.BlendState.RenderTarget[0];
	stColorBlend.BlendEnable = TRUE;
	stColorBlend.SrcBlend = D3D12_BLEND_ONE;
	stColorBlend.DestBlend = D3D12_BLEND_INV_SRC_ALPHA;
	stColorBlend.BlendOp = D3D12_BLEND_OP_ADD;
	stColorBlend.SrcBlendAlpha = D3D12_BLEND_ONE;
	stColorBlend.DestBlendAlpha = D3D12_BLEND_INV_SRC_ALPHA;
	stColorBlend.BlendOpAlpha = D3D12_BLEND_OP_ADD;
	stColorBlend.RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
	D3D12_RENDER_TARGET_BLEND_DESC &stReactiveBlend = stPipeline.BlendState.RenderTarget[1];
	stReactiveBlend.BlendEnable = TRUE;
	stReactiveBlend.SrcBlend = D3D12_BLEND_ONE;
	stReactiveBlend.DestBlend = D3D12_BLEND_ONE;
	stReactiveBlend.BlendOp = D3D12_BLEND_OP_MAX;
	stReactiveBlend.SrcBlendAlpha = D3D12_BLEND_ONE;
	stReactiveBlend.DestBlendAlpha = D3D12_BLEND_ONE;
	stReactiveBlend.BlendOpAlpha = D3D12_BLEND_OP_MAX;
	stReactiveBlend.RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_RED;
	for (std::uint32_t nIndex = 0; nIndex < arrTransparencyPipelines.size(); ++nIndex)
	{
		stPipeline.RasterizerState.FrontCounterClockwise = (nIndex & 1U) == 0;
		stPipeline.RasterizerState.CullMode = (nIndex & 2U) != 0 ? D3D12_CULL_MODE_NONE : D3D12_CULL_MODE_BACK;
		if (FAILED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(arrTransparencyPipelines[nIndex].Put()))))
		{
			return Fail("Create transparent PSO");
		}
	}
	arrTransparentCenters.assign(arrDraws.size(), {});
	arrTransparentOrder.clear();
	for (std::size_t nDraw = 0; nDraw < arrDraws.size(); ++nDraw)
	{
		const GpuDraw &stDraw = arrDraws[nDraw];
		if (arrMaterials[stDraw.stPrimitive.nMaterial].stData.eAlphaMode != AlphaMode::Blend)
		{
			continue;
		}
		const MeshPrimitive &stPrimitive = stRenderScene.arrAssets[stDraw.nSourceAsset].stMesh.arrPrimitives[stDraw.nSourcePrimitive];
		if (stPrimitive.arrVertices.empty())
		{
			return Fail("Transparent primitive has no vertices");
		}
		std::array<double, 3> arrMinimum{ stPrimitive.arrVertices[0].arrPosition[0], stPrimitive.arrVertices[0].arrPosition[1], stPrimitive.arrVertices[0].arrPosition[2] };
		std::array<double, 3> arrMaximum = arrMinimum;
		for (const MeshVertex &stVertex : stPrimitive.arrVertices)
		{
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrMinimum[nAxis] = (std::min)(arrMinimum[nAxis], static_cast<double>(stVertex.arrPosition[nAxis]));
				arrMaximum[nAxis] = (std::max)(arrMaximum[nAxis], static_cast<double>(stVertex.arrPosition[nAxis]));
			}
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrTransparentCenters[nDraw][nAxis] = arrMinimum[nAxis] * 0.5 + arrMaximum[nAxis] * 0.5;
		}
		arrTransparentOrder.push_back(nDraw);
	}
	return true;
}

bool VisualRuntime::CreateParticleMesh()
{
	if (stRenderConfiguration.arrParticles.empty())
	{
		return true;
	}
	if (arrMaterials.size() >= MAX_MATERIALS)
	{
		return Fail("Particle fallback material exceeds material descriptor budget");
	}
	FrameContext &stFrame = arrFrames[0];
	if (FAILED(stFrame.stGraphicsAllocator->Reset()) || FAILED(stFrame.stGraphicsList->Reset(stFrame.stGraphicsAllocator.Get(), nullptr)))
	{
		return Fail("Reset particle upload list");
	}
	nParticleMaterial = static_cast<std::uint32_t>(arrMaterials.size());
	const std::uint32_t nViewStart = MATERIAL_VIEW_START + nParticleMaterial * MATERIAL_TEXTURE_COUNT;
	const UINT nSamplerStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
	for (std::uint32_t nSlot = 0; nSlot < MATERIAL_TEXTURE_COUNT; ++nSlot)
	{
		DecodedImage stPixel;
		stPixel.nWidth = 1;
		stPixel.nHeight = 1;
		stPixel.arrRgba8 = nSlot == 2 ? std::vector<std::uint8_t>{ 128, 128, 255, 255 } : std::vector<std::uint8_t>{ 255, 255, 255, 255 };
		const std::vector<MipLevel> arrLevels{ stPixel };
		if (!UploadTexture(arrLevels, nSlot == 0 || nSlot == 4, nViewStart + nSlot))
		{
			return false;
		}
		D3D12_SAMPLER_DESC stSampler{};
		stSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
		stSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stSampler.MaxLOD = D3D12_FLOAT32_MAX;
		stSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
		D3D12_CPU_DESCRIPTOR_HANDLE stHandle = stSamplerHeap->GetCPUDescriptorHandleForHeapStart();
		stHandle.ptr += static_cast<SIZE_T>(nSamplerStride) * (nParticleMaterial * MATERIAL_TEXTURE_COUNT + nSlot);
		stDevice->CreateSampler(&stSampler, stHandle);
	}
	MaterialData stMaterial;
	stMaterial.eAlphaMode = AlphaMode::Blend;
	stMaterial.bDoubleSided = true;
	stMaterial.fMetallic = 0;
	stMaterial.fRoughness = 1;
	arrMaterials.push_back({ stMaterial, nViewStart });
	if (FAILED(stFrame.stGraphicsList->Close()))
	{
		return Fail("Close particle upload list");
	}
	ID3D12CommandList *pUploadList = stFrame.stGraphicsList.Get();
	stGraphics.stQueue->ExecuteCommandLists(1, &pUploadList);
	if (!stGraphics.Flush())
	{
		return Fail("Wait particle texture upload");
	}
	arrTextureUploads.clear();
	const D3D12_HEAP_PROPERTIES stUpload = HeapProperties(D3D12_HEAP_TYPE_UPLOAD);
	const std::array<std::uint16_t, 6> arrIndices{ 0, 1, 2, 0, 2, 3 };
	const D3D12_RESOURCE_DESC stIndexDescription = BufferDescription(sizeof(arrIndices));
	if (FAILED(stDevice->CreateCommittedResource(&stUpload, D3D12_HEAP_FLAG_NONE, &stIndexDescription,
												 D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stParticleIndices.Put()))))
	{
		return Fail("Create particle index buffer");
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stParticleIndices->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map particle index buffer");
	}
	std::memcpy(pMapped, arrIndices.data(), sizeof(arrIndices));
	stParticleIndices->Unmap(0, nullptr);
	stParticleIndexView = { stParticleIndices->GetGPUVirtualAddress(), sizeof(arrIndices), DXGI_FORMAT_R16_UINT };
	const D3D12_RESOURCE_DESC stVertexDescription = BufferDescription(static_cast<std::uint64_t>(MAX_PARTICLES) * 4 * sizeof(MeshVertex));
	const D3D12_RESOURCE_DESC stConstantDescription = BufferDescription(static_cast<std::uint64_t>(MAX_PARTICLES) * DRAW_CONSTANT_BYTES);
	for (std::uint32_t nFrame = 0; nFrame < FRAME_COUNT; ++nFrame)
	{
		if (FAILED(stDevice->CreateCommittedResource(&stUpload, D3D12_HEAP_FLAG_NONE, &stVertexDescription,
													 D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(arrParticleVertices[nFrame].Put()))) ||
			FAILED(stDevice->CreateCommittedResource(&stUpload, D3D12_HEAP_FLAG_NONE, &stConstantDescription,
													 D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(arrParticleConstants[nFrame].Put()))))
		{
			return Fail("Create retired-frame particle upload buffers");
		}
		arrParticleVertexViews[nFrame] = { arrParticleVertices[nFrame]->GetGPUVirtualAddress(), static_cast<UINT>(stVertexDescription.Width), sizeof(MeshVertex) };
		nParticleUploadBytes += stDevice->GetResourceAllocationInfo(0, 1, &stVertexDescription).SizeInBytes;
		nParticleUploadBytes += stDevice->GetResourceAllocationInfo(0, 1, &stConstantDescription).SizeInBytes;
	}
	nParticleUploadBytes += stDevice->GetResourceAllocationInfo(0, 1, &stIndexDescription).SizeInBytes;
	arrParticleInstances.reserve(MAX_PARTICLES);
	pParticleScratch = std::make_unique<ParticleFrame>();
	return true;
}

bool VisualRuntime::UpdateParticleBuffers(std::uint32_t nFrame, double dSeconds)
{
	arrParticleInstances.clear();
	Assets::Diagnostics arrDiagnostics;
	for (const ParticleSettings &stEmitter : stRenderConfiguration.arrParticles)
	{
		std::array<double, 3> arrOrigin{};
		if (!ResolveEffectOrigin(stEmitter.nSourceEntityId, arrOrigin) || !EvaluateParticles(stEmitter, dSeconds, arrOrigin, *pParticleScratch, arrDiagnostics))
		{
			return Fail(arrDiagnostics.empty() ? "Resolve particle emitter origin" : arrDiagnostics.front().strMessage);
		}
		if (pParticleScratch->nCount > MAX_PARTICLES - arrParticleInstances.size())
		{
			return Fail("Combined particle frame exceeds shared 4096-instance budget");
		}
		arrParticleInstances.insert(arrParticleInstances.end(), pParticleScratch->arrInstances.begin(), pParticleScratch->arrInstances.begin() + pParticleScratch->nCount);
	}
	if (arrParticleInstances.empty())
	{
		return true;
	}
	nPeakParticles = (std::max)(nPeakParticles, static_cast<std::uint32_t>(arrParticleInstances.size()));
	void *pVertexBytes = nullptr;
	void *pConstantBytes = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(arrParticleVertices[nFrame]->Map(0, &stNoRead, &pVertexBytes)))
	{
		return Fail("Map retired particle vertices");
	}
	if (FAILED(arrParticleConstants[nFrame]->Map(0, &stNoRead, &pConstantBytes)))
	{
		arrParticleVertices[nFrame]->Unmap(0, nullptr);
		return Fail("Map retired particle constants");
	}
	const std::array<double, 16> &arrView = stCameraMatrices.arrView;
	const std::array<float, 3> arrRight{ static_cast<float>(arrView[0]), static_cast<float>(arrView[4]), static_cast<float>(arrView[8]) };
	const std::array<float, 3> arrUp{ static_cast<float>(arrView[1]), static_cast<float>(arrView[5]), static_cast<float>(arrView[9]) };
	const std::array<float, 3> arrNormal{ static_cast<float>(arrView[2]), static_cast<float>(arrView[6]), static_cast<float>(arrView[10]) };
	const std::array<std::array<float, 2>, 4> arrCorners{ { { -1, -1 }, { 1, -1 }, { 1, 1 }, { -1, 1 } } };
	MeshVertex *pVertices = static_cast<MeshVertex *>(pVertexBytes);
	for (std::size_t nIndex = 0; nIndex < arrParticleInstances.size(); ++nIndex)
	{
		const BillboardInstance &stInstance = arrParticleInstances[nIndex];
		const float fHalfSize = static_cast<float>(stInstance.dSize * 0.5);
		for (std::size_t nCorner = 0; nCorner < 4; ++nCorner)
		{
			MeshVertex &stVertex = pVertices[nIndex * 4 + nCorner];
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				stVertex.arrPosition[nAxis] = static_cast<float>(stInstance.arrCenter[nAxis]) +
						fHalfSize * (arrRight[nAxis] * arrCorners[nCorner][0] + arrUp[nAxis] * arrCorners[nCorner][1]);
			}
			stVertex.arrNormal = arrNormal;
			stVertex.arrTangent = { arrRight[0], arrRight[1], arrRight[2], 1 };
			stVertex.arrTexcoord = { arrCorners[nCorner][0] * 0.5F + 0.5F, 0.5F - arrCorners[nCorner][1] * 0.5F };
		}
		DrawConstants stConstants;
		for (std::size_t nDiagonal = 0; nDiagonal < 4; ++nDiagonal)
		{
			stConstants.arrWorld[nDiagonal * 5] = 1;
			stConstants.arrNormal[nDiagonal * 5] = 1;
			stConstants.arrPreviousWorld[nDiagonal * 5] = 1;
			stConstants.arrBaseColor[nDiagonal] = static_cast<float>(stInstance.arrColor[nDiagonal]);
		}
		stConstants.arrSurface = { 1, 1, 1, 0 };
		stConstants.arrFlags = { 0, 1, 0, 0 };
		std::memcpy(static_cast<std::uint8_t *>(pConstantBytes) + nIndex * DRAW_CONSTANT_BYTES, &stConstants, sizeof(stConstants));
	}
	arrParticleVertices[nFrame]->Unmap(0, nullptr);
	arrParticleConstants[nFrame]->Unmap(0, nullptr);
	return true;
}

void VisualRuntime::DrawTransparency(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame)
{
	const auto fnDepth = [this](const std::array<double, 3> &arrPosition)
	{
		const std::array<double, 16> &arrView = stCameraMatrices.arrView;
		return -(arrView[2] * arrPosition[0] + arrView[6] * arrPosition[1] + arrView[10] * arrPosition[2] + arrView[14]);
	};
	arrForwardDraws.clear();
	arrForwardDraws.reserve(arrTransparentOrder.size() + arrParticleInstances.size());
	for (std::size_t nDraw : arrTransparentOrder)
	{
		const std::array<double, 16> &arrWorld = stTemporalFrame.arrDraws[nDraw].arrCurrentWorld;
		const std::array<double, 3> &arrCenter = arrTransparentCenters[nDraw];
		std::array<double, 3> arrPosition{};
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrPosition[nAxis] = arrWorld[nAxis] * arrCenter[0] + arrWorld[4 + nAxis] * arrCenter[1] + arrWorld[8 + nAxis] * arrCenter[2] + arrWorld[12 + nAxis];
		}
		arrForwardDraws.push_back({ false, nDraw, fnDepth(arrPosition) });
	}
	for (std::size_t nParticle = 0; nParticle < arrParticleInstances.size(); ++nParticle)
	{
		arrForwardDraws.push_back({ true, nParticle, fnDepth(arrParticleInstances[nParticle].arrCenter) });
	}
	std::sort(arrForwardDraws.begin(), arrForwardDraws.end(), [this](const ForwardDrawItem &stLeft, const ForwardDrawItem &stRight)
			  {
		if (stLeft.dDepth != stRight.dDepth)
		{
			return stLeft.dDepth > stRight.dDepth;
		}
		if (stLeft.bParticle != stRight.bParticle)
		{
			return !stLeft.bParticle;
		}
		if (stLeft.bParticle)
		{
			const ParticleId &stLeftId = arrParticleInstances[stLeft.nIndex].stId;
			const ParticleId &stRightId = arrParticleInstances[stRight.nIndex].stId;
			return std::tie(stLeftId.nEmitterId, stLeftId.nSeed, stLeftId.nSpawnIndex) < std::tie(stRightId.nEmitterId, stRightId.nSeed, stRightId.nSpawnIndex);
		}
		const GpuDraw &stLeftDraw = arrDraws[stLeft.nIndex];
		const GpuDraw &stRightDraw = arrDraws[stRight.nIndex];
		return std::tie(stLeftDraw.nEntityId, stLeftDraw.nSourceAsset, stLeftDraw.nSourcePrimitive, stLeftDraw.nSourceNode) <
			std::tie(stRightDraw.nEntityId, stRightDraw.nSourceAsset, stRightDraw.nSourcePrimitive, stRightDraw.nSourceNode); });
	if (arrForwardDraws.empty())
	{
		return;
	}
	const D3D12_VIEWPORT stViewport{ 0, 0, static_cast<float>(nWidth), static_cast<float>(nHeight), 0, 1 };
	const D3D12_RECT stScissor{ 0, 0, static_cast<LONG>(nWidth), static_cast<LONG>(nHeight) };
	pList->RSSetViewports(1, &stViewport);
	pList->RSSetScissorRects(1, &stScissor);
	const std::array<D3D12_CPU_DESCRIPTOR_HANDLE, 2> arrTargets{ Rtv(FRAME_COUNT * 10 + nFrame), Rtv(FRAME_COUNT * 11 + nFrame) };
	const D3D12_CPU_DESCRIPTOR_HANDLE stDepth = Dsv(FRAME_COUNT * (5 + MAX_LOCAL_SHADOW_VIEWS) + nFrame);
	pList->OMSetRenderTargets(2, arrTargets.data(), FALSE, &stDepth);
	pList->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
	ID3D12DescriptorHeap *arrHeaps[]{ stViewHeap.Get(), stSamplerHeap.Get() };
	pList->SetDescriptorHeaps(2, arrHeaps);
	pList->SetGraphicsRootSignature(stTransparencyRoot.Get());
	pList->SetGraphicsRootConstantBufferView(1, arrFrames[nFrame].stConstants->GetGPUVirtualAddress());
	const std::array<float, 16> arrFogConstants = BuildVolumeConstants();
	pList->SetGraphicsRoot32BitConstants(3, 16, arrFogConstants.data(), 0);
	pList->SetGraphicsRootDescriptorTable(6, GpuView(nFrame * FRAME_VIEW_COUNT + 6));
	pList->SetGraphicsRootDescriptorTable(7, GpuView(ENVIRONMENT_VIEW_START));
	pList->SetGraphicsRootDescriptorTable(8, GpuView(nFrame * FRAME_VIEW_COUNT + 8));
	pList->SetGraphicsRootDescriptorTable(9, GpuView(nFrame * FRAME_VIEW_COUNT + 26));
	pList->SetGraphicsRootDescriptorTable(10, GpuView(nFrame * FRAME_VIEW_COUNT));
	pList->SetGraphicsRootDescriptorTable(11, GpuView(nFrame * FRAME_VIEW_COUNT + VOLUME_INTEGRAL_VIEW));
	pList->SetGraphicsRootDescriptorTable(12, GpuView(nFrame * FRAME_VIEW_COUNT + VOLUME_HISTORY_WRITE_VIEW));
	if (bMaterialExtensions)
	{
		pList->SetGraphicsRootDescriptorTable(13, GpuView(ENVIRONMENT_ALIAS_VIEW));
	}
	const UINT nSamplerStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
	for (const ForwardDrawItem &stItem : arrForwardDraws)
	{
		std::uint32_t nMaterial = nParticleMaterial;
		std::uint32_t nPipeline = 2;
		D3D12_GPU_VIRTUAL_ADDRESS nConstants = 0;
		if (stItem.bParticle)
		{
			pList->IASetVertexBuffers(0, 1, &arrParticleVertexViews[nFrame]);
			pList->IASetIndexBuffer(&stParticleIndexView);
			nConstants = arrParticleConstants[nFrame]->GetGPUVirtualAddress() + stItem.nIndex * DRAW_CONSTANT_BYTES;
		}
		else
		{
			const GpuDraw &stDraw = arrDraws[stItem.nIndex];
			nMaterial = stDraw.stPrimitive.nMaterial;
			nPipeline = (stDraw.bMirrored ? 1U : 0U) + (arrMaterials[nMaterial].stData.bDoubleSided ? 2U : 0U);
			pList->IASetVertexBuffers(0, 1, &stVertexView);
			pList->IASetIndexBuffer(&stIndexView);
			nConstants = arrFrames[nFrame].stConstants->GetGPUVirtualAddress() + FRAME_CONSTANT_BYTES + stItem.nIndex * DRAW_CONSTANT_BYTES;
		}
		const std::array<float, 4> arrSoft{ static_cast<float>(stRenderConfiguration.stCamera.dNearPlane), static_cast<float>(stRenderConfiguration.stCamera.dFarPlane), stItem.bParticle ? 0.1F : 0.0F, stItem.bParticle ? 1.0F : 0.0F };
		pList->SetGraphicsRoot32BitConstants(2, 4, arrSoft.data(), 0);
		pList->SetPipelineState(arrTransparencyPipelines[nPipeline].Get());
		pList->SetGraphicsRootConstantBufferView(0, nConstants);
		pList->SetGraphicsRootDescriptorTable(4, GpuView(arrMaterials[nMaterial].nViewStart));
		D3D12_GPU_DESCRIPTOR_HANDLE stSampler = stSamplerHeap->GetGPUDescriptorHandleForHeapStart();
		stSampler.ptr += static_cast<UINT64>(nSamplerStride) * nMaterial * MATERIAL_TEXTURE_COUNT;
		pList->SetGraphicsRootDescriptorTable(5, stSampler);
		if (stItem.bParticle)
		{
			pList->DrawIndexedInstanced(6, 1, 0, static_cast<INT>(stItem.nIndex * 4), 0);
		}
		else
		{
			const GpuPrimitive &stPrimitive = arrDraws[stItem.nIndex].stPrimitive;
			pList->DrawIndexedInstanced(stPrimitive.nIndexCount, 1, stPrimitive.nFirstIndex, stPrimitive.nBaseVertex, 0);
		}
	}
}

bool VisualRuntime::CreateReflectionTargets()
{
	nReflectionBytes = 0;
	if (!bSceneMode || !stRenderConfiguration.stReflections.bEnabled)
	{
		return true;
	}
	const D3D12_HEAP_PROPERTIES stHeap = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	for (std::uint32_t nFrame = 0; nFrame < FRAME_COUNT; ++nFrame)
	{
		FrameContext &stFrame = arrFrames[nFrame];
		std::uint32_t nMipWidth = nWidth;
		std::uint32_t nMipHeight = nHeight;
		for (std::uint32_t nTarget = 0; nTarget < REFLECTION_MIP_COUNT + 2; ++nTarget)
		{
			ComOwner<ID3D12Resource> *pTarget = nullptr;
			std::uint32_t nView = 0;
			D3D12_RESOURCE_DESC stDescription{};
			stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
			stDescription.Width = nWidth;
			stDescription.Height = nHeight;
			stDescription.DepthOrArraySize = 1;
			stDescription.MipLevels = 1;
			stDescription.Format = HDR_FORMAT;
			stDescription.SampleDesc.Count = 1;
			stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
			if (nTarget == 0)
			{
				pTarget = &stFrame.stEnvironmentSpecular;
				nView = REFLECTION_ENV_VIEW;
				stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
			}
			else if (nTarget == 1)
			{
				pTarget = &stFrame.stReflection;
				nView = REFLECTION_RESULT_VIEW;
			}
			else if (nTarget == 2)
			{
				pTarget = &stFrame.stReflectedHdr;
				nView = REFLECTION_OUTPUT_VIEW;
			}
			else
			{
				nMipWidth = (nMipWidth + 1) / 2;
				nMipHeight = (nMipHeight + 1) / 2;
				stDescription.Width = nMipWidth;
				stDescription.Height = nMipHeight;
				pTarget = &stFrame.arrReflectionMips[nTarget - 3];
				nView = REFLECTION_MIP_VIEW + (nTarget - 3) * 2;
			}
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(pTarget->Put()))))
			{
				return Fail("Create reflection texture");
			}
			const std::wstring strName = L"EngineNext.Reflection." + std::to_wstring(nFrame) + L"." + std::to_wstring(nTarget);
			(void)(*pTarget)->SetName(strName.c_str());
			nReflectionBytes += stDevice->GetResourceAllocationInfo(0, 1, &stDescription).SizeInBytes;
			D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
			stSrv.Format = HDR_FORMAT;
			stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
			stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stSrv.Texture2D.MipLevels = 1;
			stDevice->CreateShaderResourceView(pTarget->Get(), &stSrv, View(nFrame * FRAME_VIEW_COUNT + nView));
			if (nTarget == 0)
			{
				stDevice->CreateRenderTargetView(pTarget->Get(), nullptr, Rtv(FRAME_COUNT * 9 + nFrame));
			}
			else
			{
				D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
				stUav.Format = HDR_FORMAT;
				stUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
				stDevice->CreateUnorderedAccessView(pTarget->Get(), nullptr, &stUav, View(nFrame * FRAME_VIEW_COUNT + nView + 1));
			}
		}
	}
	return true;
}

bool VisualRuntime::CreateReflectionPipeline()
{
	if (!stRenderConfiguration.stReflections.bEnabled)
	{
		return true;
	}
	std::array<D3D12_DESCRIPTOR_RANGE, 17> arrDescriptorRanges{};
	std::array<D3D12_ROOT_PARAMETER, 19> arrParameters{};
	arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
	arrParameters[0].Constants.Num32BitValues = 16;
	arrParameters[0].Constants.ShaderRegister = 0;
	arrParameters[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrParameters[1].Descriptor.ShaderRegister = 1;
	const std::uint32_t nRangeCount = bMaterialExtensions ? 17U : 12U;
	for (std::uint32_t nRange = 0; nRange < nRangeCount; ++nRange)
	{
		D3D12_DESCRIPTOR_RANGE &stRange = arrDescriptorRanges[nRange];
		stRange.RangeType = nRange == 11 ? D3D12_DESCRIPTOR_RANGE_TYPE_UAV : D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
		stRange.NumDescriptors = 1;
		stRange.BaseShaderRegister = nRange == 11 ? 0 : (nRange > 11 ? nRange - 1 : nRange);
		arrParameters[nRange + 2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nRange + 2].DescriptorTable.NumDescriptorRanges = 1;
		arrParameters[nRange + 2].DescriptorTable.pDescriptorRanges = &stRange;
	}
	D3D12_ROOT_SIGNATURE_DESC stRoot{};
	stRoot.NumParameters = nRangeCount + 2;
	stRoot.pParameters = arrParameters.data();
	D3D12_STATIC_SAMPLER_DESC stSampler{};
	stSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
	stSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
	stSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
	stSampler.MaxLOD = D3D12_FLOAT32_MAX;
	stRoot.NumStaticSamplers = 1;
	stRoot.pStaticSamplers = &stSampler;
	ComOwner<ID3DBlob> stSerialized;
	ComOwner<ID3DBlob> stErrors;
	if (FAILED(D3D12SerializeRootSignature(&stRoot, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put())) ||
		FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stReflectionRoot.Put()))))
	{
		return Fail("Create reflection root signature");
	}
	const std::array<const char *, 4> arrNames{ "ReflectionColor.cs.cso", bMaterialExtensions ? "MaterialReflectionTrace.cs.cso" : "ReflectionTrace.cs.cso", "ReflectionComposite.cs.cso", "ReflectionRadiance.cs.cso" };
	for (std::size_t nShader = 0; nShader < arrNames.size(); ++nShader)
	{
		const std::vector<std::uint8_t> arrShader = ReadShader(stConfig.strShaderDirectory, arrNames[nShader]);
		if (arrShader.empty())
		{
			return Fail(std::string("Missing reflection shader ") + arrNames[nShader]);
		}
		D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
		stPipeline.pRootSignature = stReflectionRoot.Get();
		stPipeline.CS = { arrShader.data(), arrShader.size() };
		if (FAILED(stDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(arrReflectionPipelines[nShader].Put()))))
		{
			return Fail(std::string("Create reflection PSO ") + arrNames[nShader]);
		}
	}
	return true;
}

bool VisualRuntime::ResetTemporalHistory()
{
	Assets::Diagnostics arrDiagnostics;
	if (!stTemporalState.Reset(arrDiagnostics))
	{
		return Fail("Reset temporal state");
	}
	bHistoryReady = false;
	bExposureReady = false;
	bVolumeHistoryReady = false;
	++nHistoryResets;
	return true;
}

bool VisualRuntime::CreateHistoryTargets()
{
	const D3D12_HEAP_PROPERTIES stHeap = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	const std::array<DXGI_FORMAT, 4> arrFormats{ HDR_FORMAT, DXGI_FORMAT_R32_FLOAT, HDR_FORMAT, DXGI_FORMAT_R32_UINT };
	D3D12_DESCRIPTOR_HEAP_DESC stCpuHeap{};
	stCpuHeap.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
	stCpuHeap.NumDescriptors = 8;
	if (FAILED(stDevice->CreateDescriptorHeap(&stCpuHeap, IID_PPV_ARGS(stHistoryCpuHeap.Put()))))
	{
		return Fail("Create CPU history descriptor heap");
	}
	for (std::uint32_t nSet = 0; nSet < 2; ++nSet)
	{
		for (std::uint32_t nTarget = 0; nTarget < 4; ++nTarget)
		{
			D3D12_RESOURCE_DESC stDescription{};
			stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
			stDescription.Width = nWidth;
			stDescription.Height = nHeight;
			stDescription.DepthOrArraySize = 1;
			stDescription.MipLevels = 1;
			stDescription.Format = arrFormats[nTarget];
			stDescription.SampleDesc.Count = 1;
			stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(arrHistory[nSet][nTarget].Put()))))
			{
				return Fail("Create temporal history texture");
			}
			D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
			stSrv.Format = stDescription.Format;
			stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
			stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stSrv.Texture2D.MipLevels = 1;
			stDevice->CreateShaderResourceView(arrHistory[nSet][nTarget].Get(), &stSrv, View(HISTORY_VIEW_START + nSet * 8 + nTarget));
			D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
			stUav.Format = stDescription.Format;
			stUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
			stDevice->CreateUnorderedAccessView(arrHistory[nSet][nTarget].Get(), nullptr, &stUav, View(HISTORY_VIEW_START + nSet * 8 + 4 + nTarget));
			D3D12_CPU_DESCRIPTOR_HANDLE stCpuHandle = stHistoryCpuHeap->GetCPUDescriptorHandleForHeapStart();
			stCpuHandle.ptr += static_cast<SIZE_T>(nSet * 4 + nTarget) * nViewStride;
			stDevice->CreateUnorderedAccessView(arrHistory[nSet][nTarget].Get(), nullptr, &stUav, stCpuHandle);
			const std::wstring strName = L"EngineNext.History." + std::to_wstring(nSet) + L"." + std::to_wstring(nTarget);
			(void)arrHistory[nSet][nTarget]->SetName(strName.c_str());
		}
	}
	nHistoryRead = 0;
	bHistoryReady = false;
	return true;
}

bool VisualRuntime::CreatePostProcessPipeline()
{
	const std::array<const char *, 4> arrNames{ "Histogram.cs.cso", "Exposure.cs.cso", "BloomDown.cs.cso", "BloomUp.cs.cso" };
	const std::array<ComOwner<ID3D12PipelineState> *, 4> arrPipelines{
		&stHistogramPipeline, &stExposurePipeline, &stBloomDownPipeline, &stBloomUpPipeline
	};
	for (std::uint32_t nKind = 0; nKind < 2; ++nKind)
	{
		const std::uint32_t nSrvCount = nKind == 0 ? 2U : 4U;
		std::array<D3D12_DESCRIPTOR_RANGE, 5> arrDescriptorRanges{};
		std::array<D3D12_ROOT_PARAMETER, 6> arrParameters{};
		arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
		arrParameters[0].Constants.Num32BitValues = 16;
		arrParameters[0].Constants.ShaderRegister = 0;
		for (std::uint32_t nRange = 0; nRange <= nSrvCount; ++nRange)
		{
			D3D12_DESCRIPTOR_RANGE &stRange = arrDescriptorRanges[nRange];
			stRange.RangeType = nRange == nSrvCount ? D3D12_DESCRIPTOR_RANGE_TYPE_UAV : D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
			stRange.NumDescriptors = 1;
			stRange.BaseShaderRegister = nRange == nSrvCount ? 0 : nRange;
			D3D12_ROOT_PARAMETER &stParameter = arrParameters[nRange + 1];
			stParameter.ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
			stParameter.DescriptorTable.NumDescriptorRanges = 1;
			stParameter.DescriptorTable.pDescriptorRanges = &stRange;
		}
		D3D12_STATIC_SAMPLER_DESC stSampler{};
		stSampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
		stSampler.AddressU = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stSampler.AddressV = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stSampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
		stSampler.MaxAnisotropy = 1;
		stSampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
		stSampler.MaxLOD = D3D12_FLOAT32_MAX;
		stSampler.ShaderRegister = 0;
		D3D12_ROOT_SIGNATURE_DESC stRoot{};
		stRoot.NumParameters = nSrvCount + 2;
		stRoot.pParameters = arrParameters.data();
		stRoot.NumStaticSamplers = nKind == 0 ? 0U : 1U;
		stRoot.pStaticSamplers = nKind == 0 ? nullptr : &stSampler;
		ComOwner<ID3DBlob> stSerialized;
		ComOwner<ID3DBlob> stErrors;
		ComOwner<ID3D12RootSignature> &stRootOwner = nKind == 0 ? stExposureRoot : stBloomRoot;
		if (FAILED(D3D12SerializeRootSignature(&stRoot, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put())) ||
			FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stRootOwner.Put()))))
		{
			return Fail(nKind == 0 ? "Create exposure root signature" : "Create Bloom root signature");
		}
		for (std::uint32_t nShader = nKind * 2; nShader < nKind * 2 + 2; ++nShader)
		{
			const std::vector<std::uint8_t> arrShader = ReadShader(stConfig.strShaderDirectory, arrNames[nShader]);
			if (arrShader.empty())
			{
				return Fail(std::string("Missing post-process shader ") + arrNames[nShader]);
			}
			D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
			stPipeline.pRootSignature = stRootOwner.Get();
			stPipeline.CS = { arrShader.data(), arrShader.size() };
			if (FAILED(stDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(arrPipelines[nShader]->Put()))))
			{
				return Fail(std::string("Create post-process PSO ") + arrNames[nShader]);
			}
		}
	}
	return true;
}

bool VisualRuntime::CreatePostProcessTargets()
{
	if (!bSceneMode)
	{
		return true;
	}
	if (nWidth == 0 || nHeight == 0 || static_cast<std::uint64_t>(nWidth) * nHeight > std::numeric_limits<std::uint32_t>::max())
	{
		return Fail("Post-process viewport exceeds histogram counter range");
	}
	if (stPostCpuHeap.Get() == nullptr)
	{
		D3D12_DESCRIPTOR_HEAP_DESC stDescription{};
		stDescription.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
		stDescription.NumDescriptors = 2 + FRAME_COUNT;
		if (FAILED(stDevice->CreateDescriptorHeap(&stDescription, IID_PPV_ARGS(stPostCpuHeap.Put()))))
		{
			return Fail("Create CPU post-process descriptor heap");
		}
	}
	const D3D12_HEAP_PROPERTIES stHeap = HeapProperties(D3D12_HEAP_TYPE_DEFAULT);
	for (std::uint32_t nSet = 0; nSet < arrExposure.size(); ++nSet)
	{
		if (arrExposure[nSet].Get() == nullptr)
		{
			D3D12_RESOURCE_DESC stDescription = BufferDescription(16);
			stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON,
														 nullptr, IID_PPV_ARGS(arrExposure[nSet].Put()))))
			{
				return Fail("Create exposure record");
			}
			const std::wstring strName = L"EngineNext.Exposure." + std::to_wstring(nSet);
			(void)arrExposure[nSet]->SetName(strName.c_str());
		}
		// A typed float4 alias gives the clear four distinct channel values.
		D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
		stUav.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
		stUav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
		stUav.Buffer.NumElements = 1;
		D3D12_CPU_DESCRIPTOR_HANDLE stCpu = stPostCpuHeap->GetCPUDescriptorHandleForHeapStart();
		stCpu.ptr += static_cast<SIZE_T>(nSet) * nViewStride;
		stDevice->CreateUnorderedAccessView(arrExposure[nSet].Get(), nullptr, &stUav, stCpu);
	}
	for (std::uint32_t nFrame = 0; nFrame < FRAME_COUNT; ++nFrame)
	{
		FrameContext &stFrame = arrFrames[nFrame];
		if (stFrame.stHistogram.Get() == nullptr)
		{
			D3D12_RESOURCE_DESC stDescription = BufferDescription(258 * sizeof(std::uint32_t));
			stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON,
														 nullptr, IID_PPV_ARGS(stFrame.stHistogram.Put()))))
			{
				return Fail("Create exposure histogram");
			}
			const std::wstring strName = L"EngineNext.Histogram." + std::to_wstring(nFrame);
			(void)stFrame.stHistogram->SetName(strName.c_str());
		}
		if (stFrame.stPostReadback.Get() == nullptr)
		{
			const D3D12_HEAP_PROPERTIES stReadbackHeap = HeapProperties(D3D12_HEAP_TYPE_READBACK);
			const D3D12_RESOURCE_DESC stReadbackDescription = BufferDescription(16 + 258 * sizeof(std::uint32_t));
			if (FAILED(stDevice->CreateCommittedResource(&stReadbackHeap, D3D12_HEAP_FLAG_NONE, &stReadbackDescription,
														 D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stFrame.stPostReadback.Put()))))
			{
				return Fail("Create post-process diagnostic readback");
			}
			const std::wstring strName = L"EngineNext.PostProcessReadback." + std::to_wstring(nFrame);
			(void)stFrame.stPostReadback->SetName(strName.c_str());
		}

		D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
		stSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
		stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
		stSrv.Buffer.NumElements = 258;
		stSrv.Buffer.StructureByteStride = sizeof(std::uint32_t);
		stDevice->CreateShaderResourceView(stFrame.stHistogram.Get(), &stSrv, View(nFrame * FRAME_VIEW_COUNT + 28));
		D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
		stUav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
		stUav.Buffer.NumElements = 258;
		stUav.Buffer.StructureByteStride = sizeof(std::uint32_t);
		stDevice->CreateUnorderedAccessView(stFrame.stHistogram.Get(), nullptr, &stUav, View(nFrame * FRAME_VIEW_COUNT + 29));
		D3D12_CPU_DESCRIPTOR_HANDLE stCpu = stPostCpuHeap->GetCPUDescriptorHandleForHeapStart();
		stCpu.ptr += static_cast<SIZE_T>(2 + nFrame) * nViewStride;
		stUav.Format = DXGI_FORMAT_R32_UINT;
		stUav.Buffer.StructureByteStride = 0;
		stDevice->CreateUnorderedAccessView(stFrame.stHistogram.Get(), nullptr, &stUav, View(nFrame * FRAME_VIEW_COUNT + 97));
		stDevice->CreateUnorderedAccessView(stFrame.stHistogram.Get(), nullptr, &stUav, stCpu);
		std::uint32_t nMipWidth = nWidth;
		std::uint32_t nMipHeight = nHeight;
		for (std::uint32_t nMip = 0; nMip < stFrame.arrBloomDown.size(); ++nMip)
		{
			nMipWidth = (std::max)(1U, (nMipWidth + 1) / 2);
			nMipHeight = (std::max)(1U, (nMipHeight + 1) / 2);
			for (std::uint32_t nKind = 0; nKind < 2; ++nKind)
			{
				ComOwner<ID3D12Resource> &stTarget = nKind == 0 ? stFrame.arrBloomDown[nMip] : stFrame.arrBloomUp[nMip];
				const bool bUsed = nKind == 0 ? nMip < stRenderPipeline.arrBloomDown.size() : nMip < stRenderPipeline.arrBloomUp.size();
				if (!bUsed)
				{
					stTarget.Reset();
					continue;
				}
				if (stTarget.Get() != nullptr)
				{
					const D3D12_RESOURCE_DESC stCurrent = stTarget->GetDesc();
					if (stCurrent.Width == nMipWidth && stCurrent.Height == nMipHeight)
					{
						continue;
					}
				}
				D3D12_RESOURCE_DESC stDescription{};
				stDescription.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
				stDescription.Width = nMipWidth;
				stDescription.Height = nMipHeight;
				stDescription.DepthOrArraySize = 1;
				stDescription.MipLevels = 1;
				stDescription.Format = HDR_FORMAT;
				stDescription.SampleDesc.Count = 1;
				stDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
				if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_COMMON,
															 nullptr, IID_PPV_ARGS(stTarget.Put()))))
				{
					return Fail("Create Bloom mip target");
				}
				const std::wstring strName = L"EngineNext.Bloom." + std::to_wstring(nFrame) + L"." +
						std::to_wstring(nKind) + L"." + std::to_wstring(nMip);
				(void)stTarget->SetName(strName.c_str());
			}
		}
	}
	return true;
}

bool VisualRuntime::PreparePostProcess(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame)
{
	if (nFrame >= FRAME_COUNT || nExposureRead >= arrExposure.size() || pList == nullptr || stPostCpuHeap.Get() == nullptr)
	{
		return Fail("Invalid post-process frame preparation");
	}
	const std::uint32_t nStart = nFrame * FRAME_VIEW_COUNT;
	D3D12_SHADER_RESOURCE_VIEW_DESC stTextureSrv{};
	stTextureSrv.Format = HDR_FORMAT;
	stTextureSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
	stTextureSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stTextureSrv.Texture2D.MipLevels = 1;
	D3D12_UNORDERED_ACCESS_VIEW_DESC stTextureUav{};
	stTextureUav.Format = HDR_FORMAT;
	stTextureUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
	FrameContext &stFrame = arrFrames[nFrame];
	for (std::uint32_t nMip = 0; nMip < stRenderPipeline.arrBloomDown.size(); ++nMip)
	{
		stDevice->CreateShaderResourceView(stFrame.arrBloomDown[nMip].Get(), &stTextureSrv, View(nStart + 48 + 2 * nMip));
		stDevice->CreateUnorderedAccessView(stFrame.arrBloomDown[nMip].Get(), nullptr, &stTextureUav, View(nStart + 49 + 2 * nMip));
	}
	for (std::uint32_t nMip = 0; nMip < stRenderPipeline.arrBloomUp.size(); ++nMip)
	{
		stDevice->CreateShaderResourceView(stFrame.arrBloomUp[nMip].Get(), &stTextureSrv, View(nStart + 60 + 2 * nMip));
		stDevice->CreateUnorderedAccessView(stFrame.arrBloomUp[nMip].Get(), nullptr, &stTextureUav, View(nStart + 61 + 2 * nMip));
	}
	ID3D12Resource *pCurrentHdr = CurrentHdrResource(nFrame);
	ID3D12Resource *pBloom = stRenderConfiguration.stTemporal.bEnabled ? arrHistory[1 - nHistoryRead][0].Get() : pCurrentHdr;
	if (!stRenderPipeline.arrBloomDown.empty())
	{
		pBloom = stRenderPipeline.arrBloomUp.empty() ? stFrame.arrBloomDown[0].Get() : stFrame.arrBloomUp[0].Get();
	}
	stDevice->CreateShaderResourceView(pBloom, &stTextureSrv, View(nStart + 96));

	D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
	stSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
	stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSrv.Buffer.NumElements = 1;
	stSrv.Buffer.StructureByteStride = 16;
	stDevice->CreateShaderResourceView(arrExposure[nExposureRead].Get(), &stSrv, View(nStart + 26));
	stDevice->CreateShaderResourceView(arrExposure[1 - nExposureRead].Get(), &stSrv, View(nStart + 27));
	D3D12_UNORDERED_ACCESS_VIEW_DESC stClear{};
	stClear.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
	stClear.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
	stClear.Buffer.NumElements = 1;
	stDevice->CreateUnorderedAccessView(arrExposure[nExposureRead].Get(), nullptr, &stClear, View(nStart + 30));
	D3D12_UNORDERED_ACCESS_VIEW_DESC stWrite{};
	stWrite.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
	stWrite.Buffer.NumElements = 1;
	stWrite.Buffer.StructureByteStride = 16;
	stDevice->CreateUnorderedAccessView(arrExposure[1 - nExposureRead].Get(), nullptr, &stWrite, View(nStart + 31));
	if (!bExposureReady)
	{
		double dSeed = 1;
		if (stRenderConfiguration.stExposure.eMode != ExposureMode::Automatic)
		{
			Assets::Diagnostics arrDiagnostics;
			if (!ComputeExposureMultiplier(stRenderConfiguration.stExposure, stRenderConfiguration.dExposure, 0, dSeed, arrDiagnostics))
			{
				return Fail(arrDiagnostics.empty() ? "Compute exposure seed" : arrDiagnostics.back().strMessage);
			}
		}
		const float fSeed = static_cast<float>(dSeed);
		const std::array<float, 4> arrSeed{ fSeed, fSeed, 0, 0 };
		D3D12_CPU_DESCRIPTOR_HANDLE stCpu = stPostCpuHeap->GetCPUDescriptorHandleForHeapStart();
		stCpu.ptr += static_cast<SIZE_T>(nExposureRead) * nViewStride;
		pList->ClearUnorderedAccessViewFloat(GpuView(nStart + 30), stCpu, arrExposure[nExposureRead].Get(), arrSeed.data(), 0, nullptr);
	}
	D3D12_CPU_DESCRIPTOR_HANDLE stCpu = stPostCpuHeap->GetCPUDescriptorHandleForHeapStart();
	stCpu.ptr += static_cast<SIZE_T>(2 + nFrame) * nViewStride;
	const std::array<UINT, 4> arrZero{};
	pList->ClearUnorderedAccessViewUint(GpuView(nStart + 97), stCpu, arrFrames[nFrame].stHistogram.Get(), arrZero.data(), 0, nullptr);
	return true;
}

bool VisualRuntime::CreateTemporalPipeline()
{
	const std::vector<std::uint8_t> arrShader = ReadShader(stConfig.strShaderDirectory, "Temporal.cs.cso");
	if (arrShader.empty())
	{
		return Fail("Missing temporal resolve shader");
	}
	std::array<D3D12_DESCRIPTOR_RANGE, 3> arrTemporalRanges{};
	arrTemporalRanges[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
	arrTemporalRanges[0].NumDescriptors = 10;
	arrTemporalRanges[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_UAV;
	arrTemporalRanges[1].NumDescriptors = 4;
	arrTemporalRanges[2].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
	arrTemporalRanges[2].NumDescriptors = 1;
	arrTemporalRanges[2].BaseShaderRegister = 10;
	std::array<D3D12_ROOT_PARAMETER, 4> arrParameters{};
	arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
	arrParameters[0].Constants.Num32BitValues = 16;
	arrParameters[0].Constants.ShaderRegister = 0;
	for (std::uint32_t nIndex = 0; nIndex < arrTemporalRanges.size(); ++nIndex)
	{
		arrParameters[nIndex + 1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nIndex + 1].DescriptorTable.NumDescriptorRanges = 1;
		arrParameters[nIndex + 1].DescriptorTable.pDescriptorRanges = &arrTemporalRanges[nIndex];
	}
	D3D12_ROOT_SIGNATURE_DESC stRoot{};
	stRoot.NumParameters = static_cast<UINT>(arrParameters.size());
	stRoot.pParameters = arrParameters.data();
	ComOwner<ID3DBlob> stSerialized;
	ComOwner<ID3DBlob> stErrors;
	if (FAILED(D3D12SerializeRootSignature(&stRoot, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put())) ||
		FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stTemporalRoot.Put()))))
	{
		return Fail("Create temporal resolve root signature");
	}
	D3D12_COMPUTE_PIPELINE_STATE_DESC stPipeline{};
	stPipeline.pRootSignature = stTemporalRoot.Get();
	stPipeline.CS = { arrShader.data(), arrShader.size() };
	return SUCCEEDED(stDevice->CreateComputePipelineState(&stPipeline, IID_PPV_ARGS(stTemporalPipeline.Put()))) || Fail("Create temporal resolve PSO");
}

void VisualRuntime::ResolveTemporal(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame)
{
	const std::uint32_t nStart = nFrame * FRAME_VIEW_COUNT;
	FrameContext &stFrame = arrFrames[nFrame];
	const std::array<DXGI_FORMAT, 4> arrHistoryFormats{ HDR_FORMAT, DXGI_FORMAT_R32_FLOAT, HDR_FORMAT, DXGI_FORMAT_R32_UINT };
	ID3D12Resource *pCurrentHdr = CurrentHdrResource(nFrame);
	const std::array<ID3D12Resource *, 5> arrCurrent{ pCurrentHdr, stFrame.stDepth.Get(), stFrame.arrGbuffer[1].Get(), stFrame.stMotion.Get(), stFrame.stObjectId.Get() };
	const std::array<DXGI_FORMAT, 5> arrCurrentFormats{ HDR_FORMAT, DXGI_FORMAT_R32_FLOAT, HDR_FORMAT, DXGI_FORMAT_R32G32B32A32_FLOAT, DXGI_FORMAT_R32_UINT };
	D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
	stSrv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
	stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stSrv.Texture2D.MipLevels = 1;
	for (std::uint32_t nIndex = 0; nIndex < arrCurrent.size(); ++nIndex)
	{
		stSrv.Format = arrCurrentFormats[nIndex];
		stDevice->CreateShaderResourceView(arrCurrent[nIndex], &stSrv, View(nStart + 32 + nIndex));
	}
	for (std::uint32_t nTarget = 0; nTarget < 4; ++nTarget)
	{
		stSrv.Format = arrHistoryFormats[nTarget];
		stDevice->CreateShaderResourceView(arrHistory[nHistoryRead][nTarget].Get(), &stSrv, View(nStart + 37 + nTarget));
		D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
		stUav.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
		stUav.Format = arrHistoryFormats[nTarget];
		stDevice->CreateUnorderedAccessView(arrHistory[1 - nHistoryRead][nTarget].Get(), nullptr, &stUav, View(nStart + 42 + nTarget));
	}
	stSrv.Format = HDR_FORMAT;
	stDevice->CreateShaderResourceView(arrHistory[1 - nHistoryRead][0].Get(), &stSrv, View(nStart + 46));
	D3D12_SHADER_RESOURCE_VIEW_DESC stExposureSrv{};
	stExposureSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
	stExposureSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
	stExposureSrv.Buffer.NumElements = 1;
	stExposureSrv.Buffer.StructureByteStride = 16;
	stDevice->CreateShaderResourceView(arrExposure[nExposureRead].Get(), &stExposureSrv, View(nStart + 41));
	stSrv.Format = DXGI_FORMAT_R8_UNORM;
	stDevice->CreateShaderResourceView(stFrame.stReactiveMask.Get(), &stSrv, View(nStart + REACTIVE_MASK_VIEW));
	if (!bHistoryReady)
	{
		// Every resource is initialized before the first possible history read.
		for (std::uint32_t nTarget = 0; nTarget < 4; ++nTarget)
		{
			ID3D12Resource *pHistory = arrHistory[nHistoryRead][nTarget].Get();
			D3D12_RESOURCE_BARRIER stBarrier{};
			stBarrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
			stBarrier.Transition.pResource = pHistory;
			stBarrier.Transition.StateBefore = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
			stBarrier.Transition.StateAfter = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
			stBarrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
			pList->ResourceBarrier(1, &stBarrier);
			const std::array<UINT, 4> arrZero{};
			const std::uint32_t nView = HISTORY_VIEW_START + nHistoryRead * 8 + 4 + nTarget;
			D3D12_CPU_DESCRIPTOR_HANDLE stCpuHandle = stHistoryCpuHeap->GetCPUDescriptorHandleForHeapStart();
			stCpuHandle.ptr += static_cast<SIZE_T>(nHistoryRead * 4 + nTarget) * nViewStride;
			if (nTarget == 3)
			{
				pList->ClearUnorderedAccessViewUint(GpuView(nView), stCpuHandle, pHistory, arrZero.data(), 0, nullptr);
			}
			else
			{
				const std::array<float, 4> arrFloatZero{};
				pList->ClearUnorderedAccessViewFloat(GpuView(nView), stCpuHandle, pHistory, arrFloatZero.data(), 0, nullptr);
			}
			std::swap(stBarrier.Transition.StateBefore, stBarrier.Transition.StateAfter);
			pList->ResourceBarrier(1, &stBarrier);
		}
	}
	const std::array<float, 16> arrConstants{ static_cast<float>(nWidth), static_cast<float>(nHeight), 1.0F / nWidth, 1.0F / nHeight,
											  static_cast<float>(stTemporalFrame.arrJitterPixels[0]), static_cast<float>(stTemporalFrame.arrJitterPixels[1]), 0, 0,
											  bHistoryReady && stTemporalFrame.bHistoryValid ? 1.0F : 0.0F, static_cast<float>(stRenderConfiguration.stTemporal.dHistoryWeight), static_cast<float>(stRenderConfiguration.stTemporal.dDepthThreshold), stForwardEffects.bTransparency ? 1.0F : 0.0F,
											  static_cast<float>(stRenderConfiguration.stCamera.dNearPlane), static_cast<float>(stRenderConfiguration.stCamera.dFarPlane), 0, 0 };
	pList->SetPipelineState(stTemporalPipeline.Get());
	pList->SetComputeRootSignature(stTemporalRoot.Get());
	pList->SetComputeRoot32BitConstants(0, 16, arrConstants.data(), 0);
	pList->SetComputeRootDescriptorTable(1, GpuView(nStart + 32));
	pList->SetComputeRootDescriptorTable(2, GpuView(nStart + 42));
	pList->SetComputeRootDescriptorTable(3, GpuView(nStart + REACTIVE_MASK_VIEW));
	pList->Dispatch((nWidth + 7) / 8, (nHeight + 7) / 8, 1);
}

bool VisualRuntime::CreateShadowPipeline()
{
	const std::vector<std::uint8_t> arrVertex = ReadShader(stConfig.strShaderDirectory, "Shadow.vs.cso");
	const std::vector<std::uint8_t> arrPixel = ReadShader(stConfig.strShaderDirectory, "Shadow.ps.cso");
	if (arrVertex.empty() || arrPixel.empty())
	{
		return Fail("Missing shadow shaders");
	}
	std::array<D3D12_DESCRIPTOR_RANGE, 2> arrDescriptorRanges{};
	arrDescriptorRanges[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
	arrDescriptorRanges[0].NumDescriptors = 1;
	arrDescriptorRanges[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER;
	arrDescriptorRanges[1].NumDescriptors = 1;
	std::array<D3D12_ROOT_PARAMETER, 4> arrParameters{};
	arrParameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrParameters[0].Descriptor.ShaderRegister = 0;
	arrParameters[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
	arrParameters[1].Descriptor.ShaderRegister = 2;
	for (std::size_t nIndex = 0; nIndex < arrDescriptorRanges.size(); ++nIndex)
	{
		arrParameters[nIndex + 2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
		arrParameters[nIndex + 2].DescriptorTable.NumDescriptorRanges = 1;
		arrParameters[nIndex + 2].DescriptorTable.pDescriptorRanges = &arrDescriptorRanges[nIndex];
		arrParameters[nIndex + 2].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
	}
	D3D12_ROOT_SIGNATURE_DESC stRoot{};
	stRoot.NumParameters = static_cast<UINT>(arrParameters.size());
	stRoot.pParameters = arrParameters.data();
	stRoot.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
	ComOwner<ID3DBlob> stSerialized;
	ComOwner<ID3DBlob> stErrors;
	if (FAILED(D3D12SerializeRootSignature(&stRoot, D3D_ROOT_SIGNATURE_VERSION_1, stSerialized.Put(), stErrors.Put())) ||
		FAILED(stDevice->CreateRootSignature(0, stSerialized->GetBufferPointer(), stSerialized->GetBufferSize(), IID_PPV_ARGS(stShadowRoot.Put()))))
	{
		return Fail("Create shadow root signature");
	}
	const std::array<D3D12_INPUT_ELEMENT_DESC, 2> arrLayout{ {
			{ "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
			{ "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 40, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 },
	} };
	D3D12_GRAPHICS_PIPELINE_STATE_DESC stPipeline{};
	stPipeline.pRootSignature = stShadowRoot.Get();
	stPipeline.VS = { arrVertex.data(), arrVertex.size() };
	stPipeline.PS = { arrPixel.data(), arrPixel.size() };
	stPipeline.InputLayout = { arrLayout.data(), static_cast<UINT>(arrLayout.size()) };
	stPipeline.SampleMask = UINT_MAX;
	stPipeline.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
	stPipeline.RasterizerState.DepthClipEnable = TRUE;
	stPipeline.DepthStencilState.DepthEnable = TRUE;
	stPipeline.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ALL;
	stPipeline.DepthStencilState.DepthFunc = D3D12_COMPARISON_FUNC_GREATER_EQUAL;
	stPipeline.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
	stPipeline.DSVFormat = DXGI_FORMAT_D32_FLOAT;
	stPipeline.SampleDesc.Count = 1;
	for (std::size_t nIndex = 0; nIndex < arrShadowPipelines.size(); ++nIndex)
	{
		stPipeline.RasterizerState.CullMode = nIndex >= 2 ? D3D12_CULL_MODE_NONE : D3D12_CULL_MODE_BACK;
		stPipeline.RasterizerState.FrontCounterClockwise = nIndex % 2 == 0;
		if (FAILED(stDevice->CreateGraphicsPipelineState(&stPipeline, IID_PPV_ARGS(arrShadowPipelines[nIndex].Put()))))
		{
			return Fail("Create shadow depth PSO");
		}
	}
	return true;
}

void VisualRuntime::DrawShadows(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame, bool bLocal)
{
	const float fResolution = static_cast<float>(bLocal ? stRenderConfiguration.stShadows.nLocalResolution : stRenderConfiguration.stShadows.nResolution);
	const D3D12_VIEWPORT stViewport{ 0, 0, fResolution, fResolution, 0, 1 };
	const D3D12_RECT stScissor{ 0, 0, static_cast<LONG>(fResolution), static_cast<LONG>(fResolution) };
	pList->RSSetViewports(1, &stViewport);
	pList->RSSetScissorRects(1, &stScissor);
	pList->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
	pList->IASetVertexBuffers(0, 1, &stVertexView);
	pList->IASetIndexBuffer(&stIndexView);
	ID3D12DescriptorHeap *arrHeaps[]{ stViewHeap.Get(), stSamplerHeap.Get() };
	pList->SetDescriptorHeaps(2, arrHeaps);
	pList->SetGraphicsRootSignature(stShadowRoot.Get());
	const UINT nSamplerStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
	const std::uint32_t nViewCount = bLocal ? (std::max)(1U, static_cast<std::uint32_t>(stLocalShadowData.arrViews.size())) : 4;
	for (std::uint32_t nView = 0; nView < nViewCount; ++nView)
	{
		const std::uint32_t nDsv = bLocal ? FRAME_COUNT * 5 + nFrame * MAX_LOCAL_SHADOW_VIEWS + nView : FRAME_COUNT + nFrame * 4 + nView;
		const D3D12_CPU_DESCRIPTOR_HANDLE stDepth = Dsv(nDsv);
		pList->ClearDepthStencilView(stDepth, D3D12_CLEAR_FLAG_DEPTH, 0, 0, 0, nullptr);
		if (!stRenderConfiguration.stShadows.bEnabled || (bLocal && stLocalShadowData.arrViews.empty()))
		{
			continue;
		}
		pList->OMSetRenderTargets(0, nullptr, FALSE, &stDepth);
		pList->SetGraphicsRootConstantBufferView(1, arrFrames[nFrame].stShadowConstants->GetGPUVirtualAddress() + (bLocal ? nView + 4 : nView) * CONSTANT_BUFFER_ALIGNMENT);
		for (std::size_t nDraw = 0; nDraw < arrDraws.size(); ++nDraw)
		{
			const GpuDraw &stDraw = arrDraws[nDraw];
			const GpuMaterial &stMaterial = arrMaterials[stDraw.stPrimitive.nMaterial];
			if (stMaterial.stData.eAlphaMode == AlphaMode::Blend)
			{
				continue;
			}
			const std::size_t nPipeline = (stDraw.bMirrored ? 1 : 0) + (stMaterial.stData.bDoubleSided ? 2 : 0);
			pList->SetPipelineState(arrShadowPipelines[nPipeline].Get());
			pList->SetGraphicsRootConstantBufferView(0, arrFrames[nFrame].stConstants->GetGPUVirtualAddress() + FRAME_CONSTANT_BYTES + nDraw * DRAW_CONSTANT_BYTES);
			pList->SetGraphicsRootDescriptorTable(2, GpuView(stMaterial.nViewStart));
			D3D12_GPU_DESCRIPTOR_HANDLE stSampler = stSamplerHeap->GetGPUDescriptorHandleForHeapStart();
			stSampler.ptr += static_cast<UINT64>(nSamplerStride) * stDraw.stPrimitive.nMaterial * MATERIAL_TEXTURE_COUNT;
			pList->SetGraphicsRootDescriptorTable(3, stSampler);
			pList->DrawIndexedInstanced(stDraw.stPrimitive.nIndexCount, 1, stDraw.stPrimitive.nFirstIndex, stDraw.stPrimitive.nBaseVertex, 0);
		}
	}
}

bool VisualRuntime::CreateConstantBuffers()
{
	if (!bSceneMode)
	{
		return true;
	}
	const std::uint64_t nBytes = FRAME_CONSTANT_BYTES + arrDraws.size() * DRAW_CONSTANT_BYTES;
	const D3D12_RESOURCE_DESC stDescription = BufferDescription(nBytes);
	const D3D12_HEAP_PROPERTIES stHeap = HeapProperties(D3D12_HEAP_TYPE_UPLOAD);
	for (FrameContext &stFrame : arrFrames)
	{
		if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDescription, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stFrame.stConstants.Put()))))
		{
			return Fail("Create frame-owned constant upload buffer");
		}
		(void)stFrame.stConstants->SetName(L"EngineNext.FrameConstants");
		if (stForwardEffects.bVolume)
		{
			const D3D12_RESOURCE_DESC stVolumeDescription = BufferDescription(512 + MAX_LOCAL_VOLUMES * sizeof(LocalVolumeConstants));
			if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stVolumeDescription, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stFrame.stVolumeParameters.Put()))))
			{
				return Fail("Create frame-owned volume parameter upload");
			}
			const std::uint32_t nFrame = static_cast<std::uint32_t>(&stFrame - arrFrames.data());
			D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
			stSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
			stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
			stSrv.Buffer.FirstElement = VOLUME_GLOBAL_BYTE_OFFSET / sizeof(GlobalVolumeConstants);
			stSrv.Buffer.NumElements = 1;
			stSrv.Buffer.StructureByteStride = sizeof(GlobalVolumeConstants);
			stDevice->CreateShaderResourceView(stFrame.stVolumeParameters.Get(), &stSrv, View(nFrame * FRAME_VIEW_COUNT + VOLUME_GLOBAL_VIEW));
			stSrv.Buffer.FirstElement = VOLUME_LOCAL_BYTE_OFFSET / sizeof(LocalVolumeConstants);
			stSrv.Buffer.NumElements = MAX_LOCAL_VOLUMES;
			stSrv.Buffer.StructureByteStride = sizeof(LocalVolumeConstants);
			stDevice->CreateShaderResourceView(stFrame.stVolumeParameters.Get(), &stSrv, View(nFrame * FRAME_VIEW_COUNT + VOLUME_LOCAL_VIEW));
		}
		const D3D12_RESOURCE_DESC stShadowDescription = BufferDescription((4 + MAX_LOCAL_SHADOW_VIEWS) * CONSTANT_BUFFER_ALIGNMENT);
		if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stShadowDescription, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(stFrame.stShadowConstants.Put()))))
		{
			return Fail("Create shadow constant upload buffer");
		}
	}
	return true;
}

bool VisualRuntime::UpdateConstantBuffer(FrameContext &stFrame)
{
	CameraSettings stCamera = stRenderConfiguration.stCamera;
	stCamera.arrPosition[0] += fCameraX;
	stCamera.arrPosition[1] += fCameraY;
	stCamera.arrTarget[0] += fCameraX;
	stCamera.arrTarget[1] += fCameraY;
	Assets::Diagnostics arrDiagnostics;
	std::vector<TemporalDrawInput> arrTemporalDraws;
	arrTemporalDraws.reserve(arrDraws.size());
	for (const GpuDraw &stDraw : arrDraws)
	{
		TemporalDrawInput stInput;
		stInput.stKey = { stDraw.nEntityId, stDraw.nSourceAsset, stDraw.nSourcePrimitive, stDraw.nSourceNode };
		const std::array<float, 16> arrWorld = DrawTransform(stDraw);
		for (std::size_t nIndex = 0; nIndex < 16; ++nIndex)
		{
			stInput.arrWorld[nIndex] = arrWorld[nIndex];
		}
		arrTemporalDraws.push_back(stInput);
	}
	if (!stTemporalState.PrepareFrame(stCamera, nWidth, nHeight, arrTemporalDraws, stTemporalFrame, arrDiagnostics))
	{
		return Fail(arrDiagnostics.empty() ? "Prepare temporal frame" : arrDiagnostics.back().strMessage);
	}
	stCameraMatrices = stTemporalFrame.stCurrentUnjitteredCamera;
	if (stRenderConfiguration.stTemporal.bEnabled)
	{
		stCameraMatrices = stTemporalFrame.stCurrentCamera;
	}
	FrameConstants stConstants;
	for (std::size_t nIndex = 0; nIndex < 16; ++nIndex)
	{
		stConstants.arrViewProjection[nIndex] = static_cast<float>(stCameraMatrices.arrViewProjection[nIndex]);
		stConstants.arrInverseViewProjection[nIndex] = static_cast<float>(stCameraMatrices.arrInverseViewProjection[nIndex]);
		stConstants.arrUnjitteredViewProjection[nIndex] = static_cast<float>(stTemporalFrame.stCurrentUnjitteredCamera.arrViewProjection[nIndex]);
		stConstants.arrPreviousViewProjection[nIndex] = static_cast<float>(stTemporalFrame.stPreviousUnjitteredCamera.arrViewProjection[nIndex]);
	}
	for (std::size_t nIndex = 0; nIndex < 3; ++nIndex)
	{
		if (!std::isfinite(stCamera.arrPosition[nIndex]) || std::abs(stCamera.arrPosition[nIndex]) > std::numeric_limits<float>::max())
		{
			return Fail("Camera origin exceeds GPU constant range");
		}
		stConstants.arrCamera[nIndex] = static_cast<float>(stCamera.arrPosition[nIndex]);
	}
	stConstants.arrCamera[3] = 1;
	stConstants.arrLighting = { static_cast<float>(stRenderConfiguration.dExposure), static_cast<float>(nEnvironmentMips - 1), static_cast<float>(SHADOW_CASCADE_BLEND_FRACTION), stRenderConfiguration.stBloom.bEnabled ? static_cast<float>(stRenderConfiguration.stBloom.dIntensity) : 0.0F };
	stShadowData = ShadowData{};
	if (stRenderConfiguration.stShadows.bEnabled)
	{
		std::vector<WorldBounds> arrCasterBounds;
		arrCasterBounds.reserve(arrDraws.size());
		for (std::size_t nDraw = 0; nDraw < arrDraws.size(); ++nDraw)
		{
			const GpuDraw &stDraw = arrDraws[nDraw];
			if (arrMaterials[stDraw.stPrimitive.nMaterial].stData.eAlphaMode == AlphaMode::Blend)
			{
				continue;
			}
			const std::array<double, 16> &arrWorld = stTemporalFrame.arrDraws[nDraw].arrCurrentWorld;
			WorldBounds stBounds;
			if (!TransformShadowBounds(stRenderScene.arrAssets[stDraw.nSourceAsset].stMesh.arrPrimitives[stDraw.nSourcePrimitive], arrWorld, stBounds, arrDiagnostics))
			{
				return Fail("Compute shadow caster bounds");
			}
			arrCasterBounds.push_back(stBounds);
		}
		if (!BuildDirectionalShadows(stCamera, nWidth, nHeight, stFrameLight, stRenderConfiguration.stShadows, arrCasterBounds, stShadowData, arrDiagnostics))
		{
			return Fail(arrDiagnostics.empty() ? "Build shadow cascades" : arrDiagnostics.back().strMessage);
		}
	}
	for (std::size_t nIndex = 0; nIndex < 16; ++nIndex)
	{
		stConstants.arrView[nIndex] = static_cast<float>(stCameraMatrices.arrView[nIndex]);
		for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
		{
			stConstants.arrShadowViewProjection[nCascade][nIndex] = static_cast<float>(stShadowData.arrCascades[nCascade].arrViewProjection[nIndex]);
		}
	}
	const DirectionalLightSettings &stLight = stFrameLight;
	const double dMaximum = (std::max)({ std::abs(stLight.arrDirection[0]), std::abs(stLight.arrDirection[1]), std::abs(stLight.arrDirection[2]) });
	const std::array<double, 3> arrDirection{ stLight.arrDirection[0] / dMaximum, stLight.arrDirection[1] / dMaximum, stLight.arrDirection[2] / dMaximum };
	const double dLength = std::sqrt(arrDirection[0] * arrDirection[0] + arrDirection[1] * arrDirection[1] + arrDirection[2] * arrDirection[2]);
	for (std::size_t nIndex = 0; nIndex < 3; ++nIndex)
	{
		stConstants.arrLightDirection[nIndex] = static_cast<float>(-arrDirection[nIndex] / dLength);
		stConstants.arrLightColor[nIndex] = static_cast<float>(stLight.arrColor[nIndex] * stLight.dIlluminance);
	}
	for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		stConstants.arrCascadeSplits[nCascade] = static_cast<float>(stShadowData.arrCascades[nCascade].dSplitFar);
	}
	stConstants.arrShadowParameters = { stRenderConfiguration.stShadows.bEnabled ? 1.0F : 0.0F, 1.0F / static_cast<float>(stRenderConfiguration.stShadows.nResolution), static_cast<float>(stRenderConfiguration.stShadows.dDepthBias), static_cast<float>(stRenderConfiguration.stShadows.dNormalBias) };
	for (std::size_t nView = 0; nView < stLocalShadowData.arrViews.size(); ++nView)
	{
		for (std::size_t nElement = 0; nElement < 16; ++nElement)
		{
			stConstants.arrLocalShadowMatrices[nView][nElement] = static_cast<float>(stLocalShadowData.arrViews[nView].arrViewProjection[nElement]);
		}
	}
	std::size_t nLightIndex = 0;
	for (const PointLightSettings &stPoint : stRenderConfiguration.arrPointLights)
	{
		LocalLightConstants &stOutput = stConstants.arrLocalLights[nLightIndex++];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stOutput.arrPositionRange[nAxis] = static_cast<float>(stPoint.arrPosition[nAxis]);
			stOutput.arrColorIntensity[nAxis] = static_cast<float>(stPoint.arrColor[nAxis] * stPoint.dLumens / (4 * 3.141592653589793));
		}
		stOutput.arrPositionRange[3] = static_cast<float>(stPoint.dRange);
		stOutput.arrConeShadow[2] = -1;
		for (std::size_t nView = 0; nView < stLocalShadowData.arrViews.size(); ++nView)
		{
			if (stLocalShadowData.arrViews[nView].nLightId == stPoint.nId)
			{
				stOutput.arrConeShadow[2] = static_cast<float>(nView);
				break;
			}
		}
		const double dNear = (std::min)(0.05, stPoint.dRange * 0.01);
		stOutput.arrShadowParameters = { static_cast<float>(dNear), static_cast<float>(stPoint.dRange), static_cast<float>(stRenderConfiguration.stShadows.dLightRadius * 0.5 * stRenderConfiguration.stShadows.nLocalResolution / dNear), 0 };
	}
	for (const SpotLightSettings &stSpot : stRenderConfiguration.arrSpotLights)
	{
		LocalLightConstants &stOutput = stConstants.arrLocalLights[nLightIndex++];
		const double dOuter = stSpot.dOuterAngleDegrees * 3.141592653589793 / 180;
		const double dInner = stSpot.dInnerAngleDegrees * 3.141592653589793 / 180;
		const double dOuterChordSquared = 4 * std::pow(std::sin(dOuter * 0.5), 2);
		const double dInnerChordSquared = 4 * std::pow(std::sin(dInner * 0.5), 2);
		if (static_cast<float>(dOuterChordSquared) - static_cast<float>(dInnerChordSquared) < std::numeric_limits<float>::min())
		{
			return Fail("Spot cone exceeds GPU angular precision");
		}
		double dSolidAngle = 0;
		if (!ComputeSpotSolidAngle(stSpot.dInnerAngleDegrees, stSpot.dOuterAngleDegrees, dSolidAngle))
		{
			return Fail("Spot angular falloff has no finite solid angle");
		}
		const double dSpotMaximum = (std::max)({ std::abs(stSpot.arrDirection[0]), std::abs(stSpot.arrDirection[1]), std::abs(stSpot.arrDirection[2]) });
		const std::array<double, 3> arrSpotDirection{ stSpot.arrDirection[0] / dSpotMaximum, stSpot.arrDirection[1] / dSpotMaximum, stSpot.arrDirection[2] / dSpotMaximum };
		const double dSpotLength = std::sqrt(arrSpotDirection[0] * arrSpotDirection[0] + arrSpotDirection[1] * arrSpotDirection[1] + arrSpotDirection[2] * arrSpotDirection[2]);
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stOutput.arrPositionRange[nAxis] = static_cast<float>(stSpot.arrPosition[nAxis]);
			const double dIntensity = stSpot.arrColor[nAxis] * stSpot.dLumens / dSolidAngle;
			if (!std::isfinite(dIntensity) || dIntensity > std::numeric_limits<float>::max())
			{
				return Fail("Spot radiance exceeds finite GPU precision");
			}
			stOutput.arrColorIntensity[nAxis] = static_cast<float>(dIntensity);
			stOutput.arrDirectionType[nAxis] = static_cast<float>(arrSpotDirection[nAxis] / dSpotLength);
		}
		stOutput.arrPositionRange[3] = static_cast<float>(stSpot.dRange);
		stOutput.arrDirectionType[3] = 1;
		stOutput.arrConeShadow = { static_cast<float>(dInnerChordSquared), static_cast<float>(dOuterChordSquared), -1, 0 };
		for (std::size_t nView = 0; nView < stLocalShadowData.arrViews.size(); ++nView)
		{
			if (stLocalShadowData.arrViews[nView].nLightId == stSpot.nId)
			{
				stOutput.arrConeShadow[2] = static_cast<float>(nView);
				break;
			}
		}
		const double dNear = (std::min)(0.05, stSpot.dRange * 0.01);
		const double dProjectedRadius = stRenderConfiguration.stShadows.dLightRadius * 0.5 / std::tan(dOuter) * stRenderConfiguration.stShadows.nLocalResolution / dNear;
		if (!std::isfinite(dProjectedRadius) || dProjectedRadius > std::numeric_limits<float>::max())
		{
			return Fail("Spot source radius exceeds finite GPU precision");
		}
		stOutput.arrShadowParameters = { static_cast<float>(dNear), static_cast<float>(stSpot.dRange), static_cast<float>(dProjectedRadius), 0 };
	}
	for (std::size_t nIndex = 0; nIndex < nLightIndex; ++nIndex)
	{
		const LocalLightConstants &stLocal = stConstants.arrLocalLights[nIndex];
		for (const std::array<float, 4> *pValues : { &stLocal.arrPositionRange, &stLocal.arrColorIntensity, &stLocal.arrDirectionType, &stLocal.arrConeShadow, &stLocal.arrShadowParameters })
		{
			for (float fValue : *pValues)
			{
				if (!std::isfinite(fValue))
				{
					return Fail("Local light parameters exceed finite GPU precision");
				}
			}
		}
	}
	stConstants.arrLocalCounts = { static_cast<float>(nLightIndex), static_cast<float>(stLocalShadowData.arrViews.size()), static_cast<float>(stRenderConfiguration.stShadows.nLocalResolution), stRenderConfiguration.stShadows.eFilter == ShadowFilter::Pcss ? 1.0F : 0.0F };
	void *pMapped = nullptr;
	const D3D12_RANGE stNoRead{ 0, 0 };
	if (FAILED(stFrame.stConstants->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map retired frame constants");
	}
	std::uint8_t *pBytes = static_cast<std::uint8_t *>(pMapped);
	std::memcpy(pBytes, &stConstants, sizeof(stConstants));
	for (std::size_t nDraw = 0; nDraw < arrDraws.size(); ++nDraw)
	{
		const GpuDraw &stDraw = arrDraws[nDraw];
		const MaterialData &stMaterial = arrMaterials[stDraw.stPrimitive.nMaterial].stData;
		DrawConstants stDrawConstants;
		for (std::size_t nElement = 0; nElement < 16; ++nElement)
		{
			stDrawConstants.arrWorld[nElement] = static_cast<float>(stTemporalFrame.arrDraws[nDraw].arrCurrentWorld[nElement]);
			stDrawConstants.arrPreviousWorld[nElement] = static_cast<float>(stTemporalFrame.arrDraws[nDraw].arrPreviousWorld[nElement]);
		}
		stDrawConstants.arrTemporal = { static_cast<std::uint32_t>(nDraw + 1), stTemporalFrame.arrDraws[nDraw].bHistoryValid ? 1U : 0U, 0, 0 };
		stDrawConstants.arrNormal = stDraw.arrNormal;
		stDrawConstants.arrBaseColor = stMaterial.arrBaseColor;
		stDrawConstants.arrEmissiveMetallic = { stMaterial.arrEmissive[0], stMaterial.arrEmissive[1], stMaterial.arrEmissive[2], stMaterial.fMetallic };
		stDrawConstants.arrSurface = { stMaterial.fRoughness, stMaterial.fNormalScale, stMaterial.fOcclusionStrength, stMaterial.fAlphaCutoff };
		stDrawConstants.arrFlags = { stMaterial.eAlphaMode == AlphaMode::Mask ? 1.0F : 0.0F, stDraw.bMirrored ? -1.0F : 1.0F, stMaterial.nNormalTexture >= 0 ? 1.0F : 0.0F, 0 };
		stDrawConstants.arrMaterialLobes = arrMaterials[stDraw.stPrimitive.nMaterial].arrLobes;
		std::memcpy(pBytes + FRAME_CONSTANT_BYTES + nDraw * DRAW_CONSTANT_BYTES, &stDrawConstants, sizeof(stDrawConstants));
	}
	stFrame.stConstants->Unmap(0, nullptr);
	if (FAILED(stFrame.stShadowConstants->Map(0, &stNoRead, &pMapped)))
	{
		return Fail("Map shadow constants");
	}
	pBytes = static_cast<std::uint8_t *>(pMapped);
	for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		std::memcpy(pBytes + nCascade * CONSTANT_BUFFER_ALIGNMENT, stConstants.arrShadowViewProjection[nCascade].data(), 16 * sizeof(float));
	}
	for (std::size_t nView = 0; nView < stLocalShadowData.arrViews.size(); ++nView)
	{
		std::memcpy(pBytes + (nView + 4) * CONSTANT_BUFFER_ALIGNMENT, stConstants.arrLocalShadowMatrices[nView].data(), 16 * sizeof(float));
	}
	stFrame.stShadowConstants->Unmap(0, nullptr);
	return true;
}

std::array<float, 16> VisualRuntime::DrawTransform(const GpuDraw &stDraw) const
{
	std::array<float, 16> arrWorld{};
	for (std::size_t nIndex = 0; nIndex < 16; ++nIndex)
	{
		arrWorld[nIndex] = static_cast<float>(stDraw.arrTransform[nIndex]);
	}
	for (const Runtime::ClientEntitySnapshot &stEntity : stClientSnapshot.arrEntities)
	{
		if (stEntity.stEntityId.nValue == stDraw.nSimulationEntityId)
		{
			const std::array<double, 3> arrDelta{
				static_cast<double>(stEntity.stState.vPosition.fX) - stDraw.arrSimulationOrigin[0],
				static_cast<double>(stEntity.stState.vPosition.fY) - stDraw.arrSimulationOrigin[1],
				static_cast<double>(stEntity.stState.vPosition.fZ) - stDraw.arrSimulationOrigin[2]
			};
			for (std::size_t nRow = 0; nRow < 3; ++nRow)
			{
				const double dWorldDelta = stDraw.arrSimulationParent[nRow] * arrDelta[0] + stDraw.arrSimulationParent[3 + nRow] * arrDelta[1] + stDraw.arrSimulationParent[6 + nRow] * arrDelta[2];
				arrWorld[12 + nRow] += static_cast<float>(dWorldDelta);
			}
			break;
		}
	}
	return arrWorld;
}

void VisualRuntime::DrawScene(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame)
{
	const D3D12_VIEWPORT stViewport{ 0, 0, static_cast<float>(nWidth), static_cast<float>(nHeight), 0, 1 };
	const D3D12_RECT stScissor{ 0, 0, static_cast<LONG>(nWidth), static_cast<LONG>(nHeight) };
	pList->RSSetViewports(1, &stViewport);
	pList->RSSetScissorRects(1, &stScissor);
	pList->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
	pList->IASetVertexBuffers(0, 1, &stVertexView);
	pList->IASetIndexBuffer(&stIndexView);
	ID3D12DescriptorHeap *arrHeaps[]{ stViewHeap.Get(), stSamplerHeap.Get() };
	pList->SetDescriptorHeaps(2, arrHeaps);
	pList->SetGraphicsRootSignature(stDeferredRoot.Get());
	const UINT nSamplerStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
	pList->SetGraphicsRootConstantBufferView(3, arrFrames[nFrame].stConstants->GetGPUVirtualAddress());
	pList->SetGraphicsRootDescriptorTable(4, GpuView(nFrame * FRAME_VIEW_COUNT + 26));
	for (std::size_t nDraw = 0; nDraw < arrDraws.size(); ++nDraw)
	{
		const GpuDraw &stDraw = arrDraws[nDraw];
		const GpuMaterial &stMaterial = arrMaterials[stDraw.stPrimitive.nMaterial];
		if (stMaterial.stData.eAlphaMode == AlphaMode::Blend)
		{
			continue;
		}
		ID3D12PipelineState *pPipeline = stDraw.bMirrored ? stMirroredPipeline.Get() : stDeferredPipeline.Get();
		if (stMaterial.stData.bDoubleSided)
		{
			pPipeline = stDraw.bMirrored ? stMirroredDoubleSidedPipeline.Get() : stDoubleSidedPipeline.Get();
		}
		pList->SetPipelineState(pPipeline);
		pList->SetGraphicsRootConstantBufferView(0, arrFrames[nFrame].stConstants->GetGPUVirtualAddress() + FRAME_CONSTANT_BYTES + nDraw * DRAW_CONSTANT_BYTES);
		pList->SetGraphicsRootDescriptorTable(1, GpuView(stMaterial.nViewStart));
		D3D12_GPU_DESCRIPTOR_HANDLE stSampler = stSamplerHeap->GetGPUDescriptorHandleForHeapStart();
		stSampler.ptr += static_cast<UINT64>(nSamplerStride) * stDraw.stPrimitive.nMaterial * MATERIAL_TEXTURE_COUNT;
		pList->SetGraphicsRootDescriptorTable(2, stSampler);
		pList->DrawIndexedInstanced(stDraw.stPrimitive.nIndexCount, 1, stDraw.stPrimitive.nFirstIndex, stDraw.stPrimitive.nBaseVertex, 0);
	}
}

void VisualRuntime::DrawLighting(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame)
{
	const std::array<D3D12_CPU_DESCRIPTOR_HANDLE, 2> arrColors{ Rtv(nFrame + FRAME_COUNT * 6), Rtv(nFrame + FRAME_COUNT * 9) };
	pList->OMSetRenderTargets(stRenderConfiguration.stReflections.bEnabled ? 2U : 1U, arrColors.data(), FALSE, nullptr);
	pList->SetPipelineState(stLightingPipeline.Get());
	pList->SetGraphicsRootSignature(stLightingRoot.Get());
	pList->SetGraphicsRootConstantBufferView(0, arrFrames[nFrame].stConstants->GetGPUVirtualAddress());
	pList->SetGraphicsRootDescriptorTable(1, GpuView(nFrame * FRAME_VIEW_COUNT + 2));
	pList->SetGraphicsRootDescriptorTable(2, GpuView(nFrame * FRAME_VIEW_COUNT));
	pList->SetGraphicsRootDescriptorTable(3, GpuView(ENVIRONMENT_VIEW_START));
	pList->SetGraphicsRootDescriptorTable(4, GpuView(nFrame * FRAME_VIEW_COUNT + 8));
	pList->SetGraphicsRootDescriptorTable(5, GpuView(nFrame * FRAME_VIEW_COUNT + 26));
	if (bMaterialExtensions)
	{
		pList->SetGraphicsRootDescriptorTable(6, GpuView(nFrame * FRAME_VIEW_COUNT + MATERIAL_PARAMETERS_VIEW));
		pList->SetGraphicsRootDescriptorTable(7, GpuView(ENVIRONMENT_ALIAS_VIEW));
	}
	pList->DrawInstanced(3, 1, 0, 0);
}

void VisualRuntime::DrawPostProcess(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame,
									PassWork eWork, std::uint32_t nMip, double dSeconds)
{
	const std::uint32_t nStart = nFrame * FRAME_VIEW_COUNT;
	if (eWork == PassWork::HistogramBuild || eWork == PassWork::ExposureAdapt)
	{
		const ExposureSettings &stExposure = stRenderConfiguration.stExposure;
		const double dElapsed = bExposureReady && std::isfinite(dSeconds) && std::isfinite(dLastPostSeconds) ? (std::max)(0.0, dSeconds - dLastPostSeconds) : 0;
		const float fDelta = static_cast<float>((std::min)(dElapsed, EXPOSURE_MAX_DELTA_SECONDS));
		const std::array<float, 16> arrConstants{
			static_cast<float>(nWidth), static_cast<float>(nHeight), 1.0F / nWidth, 1.0F / nHeight,
			fDelta, static_cast<float>(stExposure.dLightHalfLife), static_cast<float>(stExposure.dDarkHalfLife), bExposureReady ? 0.0F : 1.0F,
			static_cast<float>(stExposure.dLowPercentile), static_cast<float>(stExposure.dHighPercentile),
			static_cast<float>(stExposure.dMinimumEv100), static_cast<float>(stExposure.dMaximumEv100),
			static_cast<float>(stExposure.eMode), static_cast<float>(dManualExposure), static_cast<float>(stExposure.dCompensationEv), 1
		};
		const bool bHistogram = eWork == PassWork::HistogramBuild;
		const std::uint32_t nSource = bHistogram ? (stRenderConfiguration.stTemporal.bEnabled ? 46U : CurrentHdrView()) : 28U;
		pList->SetPipelineState(bHistogram ? stHistogramPipeline.Get() : stExposurePipeline.Get());
		pList->SetComputeRootSignature(stExposureRoot.Get());
		pList->SetComputeRoot32BitConstants(0, 16, arrConstants.data(), 0);
		pList->SetComputeRootDescriptorTable(1, GpuView(nStart + nSource));
		pList->SetComputeRootDescriptorTable(2, GpuView(nStart + 26));
		pList->SetComputeRootDescriptorTable(3, GpuView(nStart + (bHistogram ? 29U : 31U)));
		pList->Dispatch(bHistogram ? (nWidth + 15) / 16 : 1U, bHistogram ? (nHeight + 15) / 16 : 1U, 1);
		return;
	}
	const bool bDownsample = eWork == PassWork::BloomDownsample;
	FrameContext &stFrame = arrFrames[nFrame];
	ID3D12Resource *pDestination = bDownsample ? stFrame.arrBloomDown[nMip].Get() : stFrame.arrBloomUp[nMip].Get();
	ID3D12Resource *pCurrentHdr = CurrentHdrResource(nFrame);
	ID3D12Resource *pSource = bDownsample ? (nMip == 0 ? (stRenderConfiguration.stTemporal.bEnabled ? arrHistory[1 - nHistoryRead][0].Get() : pCurrentHdr) : stFrame.arrBloomDown[nMip - 1].Get()) : stFrame.arrBloomDown[nMip].Get();
	const D3D12_RESOURCE_DESC stDestination = pDestination->GetDesc();
	const D3D12_RESOURCE_DESC stSource = pSource->GetDesc();
	const float fDestinationWidth = static_cast<float>(stDestination.Width);
	const float fDestinationHeight = static_cast<float>(stDestination.Height);
	const float fSourceWidth = static_cast<float>(stSource.Width);
	const float fSourceHeight = static_cast<float>(stSource.Height);
	const BloomSettings &stBloom = stRenderConfiguration.stBloom;
	const std::array<float, 16> arrConstants{
		fDestinationWidth, fDestinationHeight, 1.0F / fDestinationWidth, 1.0F / fDestinationHeight,
		fSourceWidth, fSourceHeight, 1.0F / fSourceWidth, 1.0F / fSourceHeight,
		static_cast<float>(stBloom.dIntensity), static_cast<float>(stBloom.dThreshold), static_cast<float>(stBloom.dSoftKnee), 0.5F,
		bDownsample && nMip == 0 ? 1.0F : 0.0F, 0, 0, 0
	};
	const std::uint32_t nSourceView = bDownsample ? (nMip == 0 ? (stRenderConfiguration.stTemporal.bEnabled ? 46U : CurrentHdrView()) : 48U + 2 * (nMip - 1)) : 48U + 2 * nMip;
	std::uint32_t nLowerView = nSourceView;
	if (!bDownsample)
	{
		const std::uint32_t nLowerMip = nMip + 1;
		nLowerView = nLowerMip + 1 == stRenderPipeline.arrBloomDown.size() ? 48U + 2 * nLowerMip : 60U + 2 * nLowerMip;
	}
	const std::uint32_t nDestinationView = (bDownsample ? 49U : 61U) + 2 * nMip;
	pList->SetPipelineState(bDownsample ? stBloomDownPipeline.Get() : stBloomUpPipeline.Get());
	pList->SetComputeRootSignature(stBloomRoot.Get());
	pList->SetComputeRoot32BitConstants(0, 16, arrConstants.data(), 0);
	pList->SetComputeRootDescriptorTable(1, GpuView(nStart + nSourceView));
	pList->SetComputeRootDescriptorTable(2, GpuView(nStart + nLowerView));
	pList->SetComputeRootDescriptorTable(3, GpuView(nStart + 26));
	pList->SetComputeRootDescriptorTable(4, GpuView(nStart + 27));
	pList->SetComputeRootDescriptorTable(5, GpuView(nStart + nDestinationView));
	pList->Dispatch((static_cast<std::uint32_t>(stDestination.Width) + 7) / 8, (stDestination.Height + 7) / 8, 1);
}

void VisualRuntime::DrawToneMap(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame)
{
	const D3D12_CPU_DESCRIPTOR_HANDLE stColor = Rtv(nFrame + FRAME_COUNT);
	pList->OMSetRenderTargets(1, &stColor, FALSE, nullptr);
	pList->SetPipelineState(stToneMapPipeline.Get());
	pList->SetGraphicsRootSignature(stToneMapRoot.Get());
	pList->SetGraphicsRootConstantBufferView(0, arrFrames[nFrame].stConstants->GetGPUVirtualAddress());
	pList->SetGraphicsRootDescriptorTable(1, GpuView(nFrame * FRAME_VIEW_COUNT + (stRenderConfiguration.stTemporal.bEnabled ? 46 : CurrentHdrView())));
	pList->SetGraphicsRootDescriptorTable(2, GpuView(nFrame * FRAME_VIEW_COUNT + 96));
	pList->SetGraphicsRootDescriptorTable(3, GpuView(nFrame * FRAME_VIEW_COUNT + 26));
	pList->SetGraphicsRootDescriptorTable(4, GpuView(nFrame * FRAME_VIEW_COUNT + 27));
	pList->DrawInstanced(3, 1, 0, 0);
}

void VisualRuntime::DrawReflections(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame, PassWork eWork, std::uint32_t nMip)
{
	const std::uint32_t nStart = nFrame * FRAME_VIEW_COUNT;
	const FrameContext &stFrame = arrFrames[nFrame];
	const ReflectionSettings &stSettings = stRenderConfiguration.stReflections;
	std::array<float, 16> arrConstants{
		static_cast<float>(nWidth), static_cast<float>(nHeight), 0, 0,
		static_cast<float>(stCameraMatrices.arrProjection[0]), static_cast<float>(stCameraMatrices.arrProjection[5]),
		static_cast<float>(-stCameraMatrices.arrProjection[8]), static_cast<float>(-stCameraMatrices.arrProjection[9]),
		static_cast<float>(stRenderConfiguration.stCamera.dNearPlane), static_cast<float>(stRenderConfiguration.stCamera.dFarPlane),
		static_cast<float>(stSettings.dMaxDistance), static_cast<float>(stSettings.dThickness),
		static_cast<float>(stSettings.dNormalBias), static_cast<float>(stSettings.nMaxSteps),
		static_cast<float>(stSettings.dMaxRoughness), static_cast<float>(REFLECTION_MIP_COUNT - 1)
	};
	pList->SetComputeRootSignature(stReflectionRoot.Get());
	pList->SetComputeRootConstantBufferView(1, stFrame.stConstants->GetGPUVirtualAddress());
	std::uint32_t nWidthDispatch = nWidth;
	std::uint32_t nHeightDispatch = nHeight;
	if (eWork == PassWork::ReflectionRadiance)
	{
		pList->SetPipelineState(arrReflectionPipelines[3].Get());
		pList->SetComputeRootDescriptorTable(2, GpuView(nStart + 7));
		pList->SetComputeRootDescriptorTable(3, GpuView(nStart + REFLECTION_ENV_VIEW));
		pList->SetComputeRootDescriptorTable(13, GpuView(nStart + REFLECTION_OUTPUT_VIEW + 1));
	}
	else if (eWork == PassWork::ReflectionColorMip)
	{
		const D3D12_RESOURCE_DESC stDestination = stFrame.arrReflectionMips[nMip - 1]->GetDesc();
		ID3D12Resource *pSource = nMip == 1 ? stFrame.stReflectedHdr.Get() : stFrame.arrReflectionMips[nMip - 2].Get();
		const D3D12_RESOURCE_DESC stSource = pSource->GetDesc();
		nWidthDispatch = static_cast<std::uint32_t>(stDestination.Width);
		nHeightDispatch = stDestination.Height;
		arrConstants[0] = static_cast<float>(nWidthDispatch);
		arrConstants[1] = static_cast<float>(nHeightDispatch);
		arrConstants[4] = static_cast<float>(stSource.Width);
		arrConstants[5] = static_cast<float>(stSource.Height);
		const std::uint32_t nSourceView = nMip == 1 ? REFLECTION_OUTPUT_VIEW : REFLECTION_MIP_VIEW + (nMip - 2) * 2;
		pList->SetPipelineState(arrReflectionPipelines[0].Get());
		pList->SetComputeRootDescriptorTable(2, GpuView(nStart + nSourceView));
		pList->SetComputeRootDescriptorTable(13, GpuView(nStart + REFLECTION_MIP_VIEW + (nMip - 1) * 2 + 1));
	}
	else if (eWork == PassWork::ReflectionTrace)
	{
		pList->SetPipelineState(arrReflectionPipelines[1].Get());
		pList->SetComputeRootDescriptorTable(2, GpuView(nStart + 2));
		pList->SetComputeRootDescriptorTable(3, GpuView(nStart + 3));
		pList->SetComputeRootDescriptorTable(4, GpuView(nStart + 4));
		pList->SetComputeRootDescriptorTable(5, GpuView(nStart + 6));
		pList->SetComputeRootDescriptorTable(6, GpuView(nStart + REFLECTION_OUTPUT_VIEW));
		for (std::uint32_t nLevel = 1; nLevel < REFLECTION_MIP_COUNT; ++nLevel)
		{
			pList->SetComputeRootDescriptorTable(6 + nLevel, GpuView(nStart + REFLECTION_MIP_VIEW + (nLevel - 1) * 2));
		}
		pList->SetComputeRootDescriptorTable(12, GpuView(ENVIRONMENT_VIEW_START + 2));
		pList->SetComputeRootDescriptorTable(13, GpuView(nStart + REFLECTION_RESULT_VIEW + 1));
		if (bMaterialExtensions)
		{
			pList->SetComputeRootDescriptorTable(14, GpuView(nStart + MATERIAL_PARAMETERS_VIEW));
			pList->SetComputeRootDescriptorTable(15, GpuView(nStart + MATERIAL_PARAMETERS_VIEW + 1));
			pList->SetComputeRootDescriptorTable(16, GpuView(ENVIRONMENT_VIEW_START + 1));
			pList->SetComputeRootDescriptorTable(17, GpuView(nStart + 26));
			pList->SetComputeRootDescriptorTable(18, GpuView(ENVIRONMENT_ALIAS_VIEW));
		}
	}
	else
	{
		pList->SetPipelineState(arrReflectionPipelines[2].Get());
		pList->SetComputeRootDescriptorTable(2, GpuView(nStart + 7));
		pList->SetComputeRootDescriptorTable(3, GpuView(nStart + REFLECTION_ENV_VIEW));
		pList->SetComputeRootDescriptorTable(4, GpuView(nStart + REFLECTION_RESULT_VIEW));
		pList->SetComputeRootDescriptorTable(13, GpuView(nStart + REFLECTION_OUTPUT_VIEW + 1));
	}
	pList->SetComputeRoot32BitConstants(0, static_cast<UINT>(arrConstants.size()), arrConstants.data(), 0);
	pList->Dispatch((nWidthDispatch + 7) / 8, (nHeightDispatch + 7) / 8, 1);
}

std::uint32_t VisualRuntime::GraphicsPassCount() const noexcept
{
	return stRenderPipeline.nGraphicsPassCount;
}

std::uint32_t VisualRuntime::TotalQueryCount() const noexcept
{
	return static_cast<std::uint32_t>(stCompiled.arrPasses.size()) * 2;
}

bool VisualRuntime::BuildGraph()
{
	stForwardEffects.bVolume = bSceneMode && stRenderConfiguration.stVolume.bEnabled;
	stForwardEffects.bTransparency = bSceneMode && !stRenderConfiguration.arrParticles.empty();
	for (const RenderAsset &stAsset : stRenderScene.arrAssets)
	{
		for (const MaterialData &stMaterial : stAsset.stMesh.arrMaterials)
		{
			stForwardEffects.bTransparency = stForwardEffects.bTransparency || stMaterial.eAlphaMode == AlphaMode::Blend;
		}
	}
	GraphDiagnostic stDiagnostic;
	if (!BuildRenderPipeline(bSceneMode, stRenderPipeline, stDiagnostic, static_cast<std::uint32_t>(stLocalShadowData.arrViews.size()), stRenderConfiguration.stTemporal.bEnabled, true, stRenderConfiguration.stBloom.bEnabled ? stRenderConfiguration.stBloom.nMipCount : 0,
							 stRenderConfiguration.stReflections.bEnabled ? REFLECTION_MIP_COUNT : 0, stForwardEffects, bMaterialExtensions))
	{
		return Fail("FrameGraph compilation failed: " + stDiagnostic.strMessage);
	}
	if (stRenderPipeline.nComputePassCount != 1)
	{
		return Fail("Tint pipeline requires one compute submission");
	}
	arrQueryOffsets.resize(stCompiled.arrPasses.size());
	std::uint32_t nGraphicsOffset = 2;
	for (std::size_t nIndex = 0; nIndex < stCompiled.arrPasses.size(); ++nIndex)
	{
		const CompiledPass &stPass = stCompiled.arrPasses[nIndex];
		if (stPass.eQueue == QueueType::Compute)
		{
			nComputePassIndex = nIndex;
			arrQueryOffsets[nIndex] = 0;
		}
		else
		{
			arrQueryOffsets[nIndex] = nGraphicsOffset;
			nGraphicsOffset += 2;
		}
	}
	return true;
}

void VisualRuntime::ApplyBarriers(ID3D12GraphicsCommandList *pList, const std::vector<ResourceBarrier> &arrBarriers, const std::vector<ID3D12Resource *> &arrResources)
{
	for (const ResourceBarrier &stBarrier : arrBarriers)
	{
		D3D12_RESOURCE_BARRIER stNative{};
		stNative.Type = stBarrier.eKind == BarrierKind::Uav ? D3D12_RESOURCE_BARRIER_TYPE_UAV : D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
		if (stNative.Type == D3D12_RESOURCE_BARRIER_TYPE_UAV)
		{
			stNative.UAV.pResource = arrResources[stBarrier.nResource];
		}
		else
		{
			stNative.Transition.pResource = arrResources[stBarrier.nResource];
			stNative.Transition.StateBefore = NativeState(stBarrier.eBefore);
			stNative.Transition.StateAfter = NativeState(stBarrier.eAfter);
			stNative.Transition.Subresource = stBarrier.nSubresource;
		}
		pList->ResourceBarrier(1, &stNative);
	}
}

void VisualRuntime::RecordPostProcessReadback(ID3D12GraphicsCommandList *pList, std::uint32_t nFrame)
{
	FrameContext &stFrame = arrFrames[nFrame];
	const std::array<ID3D12Resource *, 2> arrSources{ arrExposure[1 - nExposureRead].Get(), stFrame.stHistogram.Get() };
	pList->CopyBufferRegion(stFrame.stPostReadback.Get(), 0, arrSources[0], 0, 16);
	pList->CopyBufferRegion(stFrame.stPostReadback.Get(), 16, arrSources[1], 0, 258 * sizeof(std::uint32_t));
}

bool VisualRuntime::CollectPostProcess(FrameContext &stFrame, FrameTiming &stTiming)
{
	if (stFrame.stPostReadback.Get() == nullptr)
	{
		return Fail("Missing post-process diagnostic readback");
	}
	const D3D12_RANGE stReadRange{ 0, 16 + 258 * sizeof(std::uint32_t) };
	void *pMapped = nullptr;
	if (FAILED(stFrame.stPostReadback->Map(0, &stReadRange, &pMapped)))
	{
		return Fail("Map retired post-process diagnostics");
	}
	std::array<float, 4> arrExposureValues{};
	std::array<std::uint32_t, 258> arrHistogram{};
	const std::uint8_t *pBytes = static_cast<const std::uint8_t *>(pMapped);
	std::memcpy(arrExposureValues.data(), pBytes, sizeof(arrExposureValues));
	std::memcpy(arrHistogram.data(), pBytes + sizeof(arrExposureValues), sizeof(arrHistogram));
	const D3D12_RANGE stNoWrite{ 0, 0 };
	stFrame.stPostReadback->Unmap(0, &stNoWrite);
	for (float fValue : arrExposureValues)
	{
		if (!std::isfinite(fValue))
		{
			return Fail("Nonfinite GPU exposure diagnostic");
		}
	}
	if (arrExposureValues[0] < std::numeric_limits<float>::min() || arrExposureValues[1] < std::numeric_limits<float>::min() ||
		arrExposureValues[3] < 0)
	{
		return Fail("GPU exposure diagnostic outside supported range");
	}
	std::uint64_t nBinnedPixels = 0;
	for (std::size_t nBin = 0; nBin < EXPOSURE_HISTOGRAM_BINS; ++nBin)
	{
		nBinnedPixels += arrHistogram[nBin];
	}
	const std::uint64_t nFinite = arrHistogram[EXPOSURE_HISTOGRAM_BINS + 1];
	const std::uint64_t nInvalid = arrHistogram[EXPOSURE_HISTOGRAM_BINS];
	const std::uint64_t nExpectedPixels = static_cast<std::uint64_t>(stTiming.nWidth) * stTiming.nHeight;
	if (nBinnedPixels != nFinite || nFinite + nInvalid != nExpectedPixels)
	{
		return Fail("GPU histogram counters do not match the submitted viewport");
	}
	stTiming.arrExposure = arrExposureValues;
	stTiming.nMeterFinite = static_cast<std::uint32_t>(nFinite);
	stTiming.nMeterInvalid = static_cast<std::uint32_t>(nInvalid);
	stTiming.bPostReady = true;
	return true;
}

bool VisualRuntime::CollectTiming(FrameContext &stFrame)
{
	if (!stFrame.bTimingPending)
	{
		return true;
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stReadRange{ 0, TotalQueryCount() * sizeof(std::uint64_t) };
	if (FAILED(stFrame.stQueries->Map(0, &stReadRange, &pMapped)))
	{
		return Fail("Map timestamp queries");
	}
	std::vector<std::uint64_t> arrTimes(TotalQueryCount());
	std::memcpy(arrTimes.data(), pMapped, arrTimes.size() * sizeof(std::uint64_t));
	const D3D12_RANGE stNoWrite{ 0, 0 };
	stFrame.stQueries->Unmap(0, &stNoWrite);
	if (stCompute.nFrequency == 0 || stGraphics.nFrequency == 0 || arrTimes[1] < arrTimes[0] || arrTimes[stCompiled.arrPasses.size() * 2 - 1] < arrTimes[2])
	{
		return Fail("Invalid completed GPU timestamps");
	}
	FrameTiming &stTiming = Timing(stFrame.nTimingFrame);
	stTiming.dComputeMsec = 1000.0 * static_cast<double>(arrTimes[1] - arrTimes[0]) / static_cast<double>(stCompute.nFrequency);
	stTiming.dGraphicsMsec = 1000.0 * static_cast<double>(arrTimes[stCompiled.arrPasses.size() * 2 - 1] - arrTimes[2]) / static_cast<double>(stGraphics.nFrequency);
	stTiming.arrPassMsec.resize(stCompiled.arrPasses.size());
	for (std::size_t nPassIndex = 0; nPassIndex < stCompiled.arrPasses.size(); ++nPassIndex)
	{
		const std::size_t nTimeIndex = arrQueryOffsets[nPassIndex];
		if (arrTimes[nTimeIndex + 1] < arrTimes[nTimeIndex])
		{
			return Fail("Invalid completed pass timestamps");
		}
		const std::uint64_t nFrequency = stCompiled.arrPasses[nPassIndex].eQueue == QueueType::Compute ? stCompute.nFrequency : stGraphics.nFrequency;
		stTiming.arrPassMsec[nPassIndex] = 1000.0 * static_cast<double>(arrTimes[nTimeIndex + 1] - arrTimes[nTimeIndex]) / static_cast<double>(nFrequency);
	}
	if (bSceneMode && !CollectPostProcess(stFrame, stTiming))
	{
		return false;
	}
	stTiming.bGpuReady = true;
	stFrame.bTimingPending = false;
	return true;
}

FrameTiming &VisualRuntime::Timing(std::uint32_t nFrame)
{
	return arrTiming[static_cast<std::size_t>(nFrame) % MAX_TIMING_SAMPLES];
}

bool VisualRuntime::RenderFrame(double dSeconds, bool bCapture)
{
	const std::uint32_t nIndex = stSwapchain->GetCurrentBackBufferIndex();
	FrameContext &stFrame = arrFrames[nIndex];
	if (!stGraphics.Wait(stFrame.nGraphicsFence) || !stCompute.Wait(stFrame.nComputeFence) || !CollectTiming(stFrame))
	{
		return Fail("Wait frame retirement");
	}
	if (FAILED(stFrame.stGraphicsAllocator->Reset()) || FAILED(stFrame.stComputeAllocator->Reset()) ||
		FAILED(stFrame.stGraphicsList->Reset(stFrame.stGraphicsAllocator.Get(), stGraphicsPipeline.Get())) ||
		FAILED(stFrame.stComputeList->Reset(stFrame.stComputeAllocator.Get(), stComputePipeline.Get())))
	{
		return Fail("Reset frame command lists");
	}
	FrameTiming &stTiming = Timing(nFrames);
	stTiming = FrameTiming{};
	stTiming.nFrame = nFrames;
	stTiming.nWidth = nWidth;
	stTiming.nHeight = nHeight;
	std::vector<ID3D12Resource *> arrResources(stCompiled.arrResources.size());
	arrResources[stRenderPipeline.nTint] = stFrame.stTint.Get();
	arrResources[stRenderPipeline.nColor] = stFrame.stColor.Get();
	arrResources[stRenderPipeline.nDepth] = stFrame.stDepth.Get();
	arrResources[stRenderPipeline.nBackbuffer] = arrBackbuffers[nIndex].Get();
	if (bSceneMode)
	{
		arrResources[stRenderPipeline.nHdr] = stFrame.stHdr.Get();
		if (stRenderConfiguration.stReflections.bEnabled)
		{
			arrResources[stRenderPipeline.nEnvironmentSpecular] = stFrame.stEnvironmentSpecular.Get();
			arrResources[stRenderPipeline.nReflection] = stFrame.stReflection.Get();
			arrResources[stRenderPipeline.nReflectedHdr] = stFrame.stReflectedHdr.Get();
			for (std::size_t nMip = 0; nMip < stRenderPipeline.arrReflectionMips.size(); ++nMip)
			{
				arrResources[stRenderPipeline.arrReflectionMips[nMip]] = stFrame.arrReflectionMips[nMip].Get();
			}
		}
		if (stForwardEffects.bVolume || stForwardEffects.bTransparency)
		{
			arrResources[stRenderPipeline.nForwardHdr] = stFrame.stForwardHdr.Get();
		}
		if (stForwardEffects.bTransparency)
		{
			arrResources[stRenderPipeline.nReactiveMask] = stFrame.stReactiveMask.Get();
		}
		if (stForwardEffects.bVolume)
		{
			arrResources[stRenderPipeline.nVolumeMedium] = stFrame.arrVolume[0].Get();
			arrResources[stRenderPipeline.nVolumeEmission] = stFrame.arrVolume[1].Get();
			arrResources[stRenderPipeline.nVolumeSource] = stFrame.arrVolume[2].Get();
			arrResources[stRenderPipeline.nVolumeIntegral] = stFrame.arrVolume[3].Get();
			arrResources[stRenderPipeline.nVolumeHistoryRead] = arrVolumeHistory[nVolumeRead].Get();
			arrResources[stRenderPipeline.nVolumeHistoryWrite] = arrVolumeHistory[1 - nVolumeRead].Get();
		}
		arrResources[stRenderPipeline.nDirectionalShadow] = stFrame.stDirectionalShadow.Get();
		arrResources[stRenderPipeline.nLocalShadow] = stFrame.stLocalShadow.Get();
		arrResources[stRenderPipeline.nMotion] = stFrame.stMotion.Get();
		arrResources[stRenderPipeline.nObjectId] = stFrame.stObjectId.Get();
		arrResources[stRenderPipeline.nHistogram] = stFrame.stHistogram.Get();
		arrResources[stRenderPipeline.nPostReadback] = stFrame.stPostReadback.Get();
		arrResources[stRenderPipeline.nExposureRead] = arrExposure[nExposureRead].Get();
		arrResources[stRenderPipeline.nExposureWrite] = arrExposure[1 - nExposureRead].Get();
		for (std::size_t nMip = 0; nMip < stRenderPipeline.arrBloomDown.size(); ++nMip)
		{
			arrResources[stRenderPipeline.arrBloomDown[nMip]] = stFrame.arrBloomDown[nMip].Get();
		}
		for (std::size_t nMip = 0; nMip < stRenderPipeline.arrBloomUp.size(); ++nMip)
		{
			arrResources[stRenderPipeline.arrBloomUp[nMip]] = stFrame.arrBloomUp[nMip].Get();
		}
		if (stRenderConfiguration.stTemporal.bEnabled)
		{
			for (std::size_t nTarget = 0; nTarget < 4; ++nTarget)
			{
				arrResources[stRenderPipeline.arrHistoryRead[nTarget]] = arrHistory[nHistoryRead][nTarget].Get();
				arrResources[stRenderPipeline.arrHistoryWrite[nTarget]] = arrHistory[1 - nHistoryRead][nTarget].Get();
			}
		}
		for (std::size_t nTarget = 0; nTarget < stFrame.arrGbuffer.size(); ++nTarget)
		{
			arrResources[stRenderPipeline.arrGbuffer[nTarget]] = stFrame.arrGbuffer[nTarget].Get();
		}
		if (bMaterialExtensions)
		{
			for (std::size_t nTarget = 0; nTarget < stFrame.arrMaterialBuffers.size(); ++nTarget)
			{
				arrResources[stRenderPipeline.arrMaterialBuffers[nTarget]] = stFrame.arrMaterialBuffers[nTarget].Get();
			}
		}
		stFrameLight = stRenderConfiguration.stDirectionalLight;
		Assets::Diagnostics arrLightDiagnostics;
		if (!EvaluateLightAnimation(stRenderConfiguration.stLightAnimation, stRenderConfiguration.stDirectionalLight.dIlluminance,
									dSeconds, stFrameLight.dIlluminance, arrLightDiagnostics))
		{
			return Fail(arrLightDiagnostics.empty() ? "Evaluate light animation" : arrLightDiagnostics.back().strMessage);
		}
		stTiming.dLightingSeconds = dSeconds;
		stTiming.dDirectionalIlluminance = stFrameLight.dIlluminance;
		if (!UpdateEffectTransforms() || !UpdateConstantBuffer(stFrame) || !UpdateVolumeParameters(nIndex) || !UpdateParticleBuffers(nIndex, dSeconds))
		{
			return false;
		}
		stTiming.nTemporalEpoch = stTemporalFrame.nEpoch;
		stTiming.nTemporalSample = stTemporalFrame.nSampleIndex;
		stTiming.nTemporalRead = nHistoryRead;
		stTiming.arrTemporalJitter = stRenderConfiguration.stTemporal.bEnabled ? stTemporalFrame.arrJitterPixels : std::array<double, 2>{ 0, 0 };
		stTiming.bTemporalHistoryValid = stRenderConfiguration.stTemporal.bEnabled && bHistoryReady && stTemporalFrame.bHistoryValid;
		stTiming.bVolumeHistoryValid = stForwardEffects.bVolume && bVolumeHistoryReady && stTemporalFrame.bHistoryValid;
		stTiming.nVolumeHistoryRead = nVolumeRead;
		stTiming.nParticles = static_cast<std::uint32_t>(arrParticleInstances.size());
	}
	const std::array<float, 4> arrConstants{ static_cast<float>(dSeconds), static_cast<float>(nWidth) / static_cast<float>(nHeight), fCameraX, fCameraY };
	ID3D12DescriptorHeap *pHeap = stViewHeap.Get();
	stFrame.stComputeList->SetDescriptorHeaps(1, &pHeap);
	stFrame.stComputeList->SetComputeRootSignature(stComputeRoot.Get());
	stFrame.stComputeList->SetComputeRoot32BitConstants(0, 4, arrConstants.data(), 0);
	stFrame.stComputeList->SetComputeRootDescriptorTable(1, GpuView(nIndex * FRAME_VIEW_COUNT + 1));
	stFrame.stComputeList->EndQuery(stComputeQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nIndex * 2);
	const CompiledPass &stComputePass = stCompiled.arrPasses[nComputePassIndex];
	ApplyBarriers(stFrame.stComputeList.Get(), stComputePass.arrBeforeBarriers, arrResources);
	stFrame.stComputeList->Dispatch(1, 1, 1);
	ApplyBarriers(stFrame.stComputeList.Get(), stComputePass.arrAfterBarriers, arrResources);
	stFrame.stComputeList->EndQuery(stComputeQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nIndex * 2 + 1);
	stFrame.stComputeList->ResolveQueryData(stComputeQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nIndex * 2, 2, stFrame.stQueries.Get(), 0);
	if (FAILED(stFrame.stComputeList->Close()))
	{
		return Fail("Close compute list");
	}
	ID3D12CommandList *pComputeList = stFrame.stComputeList.Get();
	stCompute.stQueue->ExecuteCommandLists(1, &pComputeList);
	if (!stCompute.Signal(stFrame.nComputeFence))
	{
		return Fail("Compute completion signal");
	}
	for (const CompiledPass &stPass : stCompiled.arrPasses)
	{
		for (PassId nProducer : stPass.arrWaits)
		{
			if (nProducer != stComputePass.nPass || FAILED(stGraphics.stQueue->Wait(stCompute.stFence.Get(), stFrame.nComputeFence)))
			{
				return Fail("Cross-queue compute to graphics dependency");
			}
		}
	}
	stTiming.nComputeFence = stFrame.nComputeFence;
	ID3D12GraphicsCommandList *pList = stFrame.stGraphicsList.Get();
	pList->SetDescriptorHeaps(1, &pHeap);
	pList->SetGraphicsRootSignature(stGraphicsRoot.Get());
	pList->SetGraphicsRoot32BitConstants(0, 4, arrConstants.data(), 0);
	pList->SetGraphicsRootDescriptorTable(1, GpuView(nIndex * FRAME_VIEW_COUNT));
	for (std::size_t nPassIndex = 0; nPassIndex < stCompiled.arrPasses.size(); ++nPassIndex)
	{
		const CompiledPass &stPass = stCompiled.arrPasses[nPassIndex];
		if (stPass.eQueue != QueueType::Graphics)
		{
			continue;
		}
		const PassWork eWork = stRenderPipeline.arrWorkByPass[stPass.nPass];
		const UINT nQueryIndex = nIndex * GraphicsPassCount() * 2 + arrQueryOffsets[nPassIndex] - 2;
		pList->EndQuery(stGraphicsQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nQueryIndex);
		PIXBeginEvent(pList, PIX_COLOR_DEFAULT, stPass.strName.c_str());
		ApplyBarriers(pList, stPass.arrBeforeBarriers, arrResources);
		if (eWork == PassWork::PrepareExposure)
		{
			if (!PreparePostProcess(pList, nIndex))
			{
				return false;
			}
		}
		else if (eWork == PassWork::PostProcessReadback)
		{
			RecordPostProcessReadback(pList, nIndex);
		}
		else if (eWork == PassWork::HistogramBuild || eWork == PassWork::ExposureAdapt || eWork == PassWork::BloomDownsample || eWork == PassWork::BloomUpsample)
		{
			DrawPostProcess(pList, nIndex, eWork, stRenderPipeline.arrPassMipIndex[stPass.nPass], dSeconds);
		}
		else if (eWork == PassWork::ReflectionRadiance || eWork == PassWork::ReflectionColorMip || eWork == PassWork::ReflectionTrace || eWork == PassWork::ReflectionComposite)
		{
			DrawReflections(pList, nIndex, eWork, stRenderPipeline.arrPassMipIndex[stPass.nPass]);
		}
		else if (eWork == PassWork::VolumePrepare || eWork == PassWork::VolumeInject || eWork == PassWork::VolumeLight ||
				 eWork == PassWork::VolumeTemporal || eWork == PassWork::VolumeIntegrate || eWork == PassWork::VolumeComposite)
		{
			DrawVolume(pList, nIndex, eWork);
		}
		else if (eWork == PassWork::ForwardCopy)
		{
			pList->CopyResource(stFrame.stForwardHdr.Get(), stRenderConfiguration.stReflections.bEnabled ? stFrame.stReflectedHdr.Get() : stFrame.stHdr.Get());
		}
		else if (eWork == PassWork::Transparency)
		{
			const std::array<float, 4> arrClear{};
			pList->ClearRenderTargetView(Rtv(FRAME_COUNT * 11 + nIndex), arrClear.data(), 0, nullptr);
			DrawTransparency(pList, nIndex);
		}
		else if (eWork == PassWork::DirectionalShadow)
		{
			DrawShadows(pList, nIndex, false);
		}
		else if (eWork == PassWork::LocalShadow)
		{
			DrawShadows(pList, nIndex, true);
		}
		else if (eWork == PassWork::FixedMesh)
		{
			const D3D12_CPU_DESCRIPTOR_HANDLE stColorHandle = Rtv(nIndex + FRAME_COUNT);
			const D3D12_CPU_DESCRIPTOR_HANDLE stDepthHandle = Dsv(nIndex);
			const std::array<float, 4> arrClear{ 0.025F, 0.035F, 0.055F, 1.0F };
			pList->ClearRenderTargetView(stColorHandle, arrClear.data(), 0, nullptr);
			pList->ClearDepthStencilView(stDepthHandle, D3D12_CLEAR_FLAG_DEPTH, 0.0F, 0, 0, nullptr);
			pList->OMSetRenderTargets(1, &stColorHandle, FALSE, &stDepthHandle);
			const D3D12_VIEWPORT stViewport{ 0, 0, static_cast<float>(nWidth), static_cast<float>(nHeight), 0, 1 };
			const D3D12_RECT stScissor{ 0, 0, static_cast<LONG>(nWidth), static_cast<LONG>(nHeight) };
			pList->RSSetViewports(1, &stViewport);
			pList->RSSetScissorRects(1, &stScissor);
			pList->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
			pList->IASetVertexBuffers(0, 1, &stVertexView);
			pList->IASetIndexBuffer(&stIndexView);
			pList->DrawIndexedInstanced(36, 1, 0, 0, 0);
		}
		else if (eWork == PassWork::GBuffer)
		{
			std::array<D3D12_CPU_DESCRIPTOR_HANDLE, 8> arrTargets{};
			const std::uint32_t nTargetCount = bMaterialExtensions ? 8U : 6U;
			const std::array<float, 4> arrClear{};
			for (std::uint32_t nTarget = 0; nTarget < nTargetCount; ++nTarget)
			{
				if (nTarget < 4)
				{
					arrTargets[nTarget] = Rtv(FRAME_COUNT * 2 + nIndex * 4 + nTarget);
				}
				else if (nTarget < 6)
				{
					arrTargets[nTarget] = Rtv(FRAME_COUNT * (7 + nTarget - 4) + nIndex);
				}
				else
				{
					arrTargets[nTarget] = Rtv(FRAME_COUNT * 12 + nIndex * 2 + nTarget - 6);
				}
				pList->ClearRenderTargetView(arrTargets[nTarget], arrClear.data(), 0, nullptr);
			}
			const D3D12_CPU_DESCRIPTOR_HANDLE stDepthHandle = Dsv(nIndex);
			pList->ClearDepthStencilView(stDepthHandle, D3D12_CLEAR_FLAG_DEPTH, 0.0F, 0, 0, nullptr);
			pList->OMSetRenderTargets(nTargetCount, arrTargets.data(), FALSE, &stDepthHandle);
			DrawScene(pList, nIndex);
		}
		else if (eWork == PassWork::DeferredLighting)
		{
			DrawLighting(pList, nIndex);
		}
		else if (eWork == PassWork::TemporalResolve)
		{
			ResolveTemporal(pList, nIndex);
		}
		else if (eWork == PassWork::ToneMap)
		{
			DrawToneMap(pList, nIndex);
		}
		else if (eWork == PassWork::CopyToBackbuffer)
		{
			pList->CopyResource(arrBackbuffers[nIndex].Get(), stFrame.stColor.Get());
			if (bCapture)
			{
				D3D12_TEXTURE_COPY_LOCATION stDestination{};
				stDestination.pResource = stCapture.Get();
				stDestination.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
				stDestination.PlacedFootprint = stCaptureFootprint;
				D3D12_TEXTURE_COPY_LOCATION stSource{};
				stSource.pResource = stFrame.stColor.Get();
				stSource.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
				pList->CopyTextureRegion(&stDestination, 0, 0, 0, &stSource, nullptr);
			}
		}
		ApplyBarriers(pList, stPass.arrAfterBarriers, arrResources);
		PIXEndEvent(pList);
		pList->EndQuery(stGraphicsQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nQueryIndex + 1);
	}
	pList->ResolveQueryData(stGraphicsQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nIndex * GraphicsPassCount() * 2, GraphicsPassCount() * 2, stFrame.stQueries.Get(), 2 * sizeof(std::uint64_t));
	if (FAILED(pList->Close()))
	{
		return Fail("Close graphics list");
	}
	ID3D12CommandList *pGraphicsList = pList;
	stGraphics.stQueue->ExecuteCommandLists(1, &pGraphicsList);
	const HRESULT nPresent = stSwapchain->Present(stConfig.bVsync ? 1 : 0, !stConfig.bVsync && bTearing ? DXGI_PRESENT_ALLOW_TEARING : 0);
	if (FAILED(nPresent) || !stGraphics.Signal(stFrame.nGraphicsFence))
	{
		return Fail("Present or graphics signal", nPresent);
	}
	if (bSceneMode)
	{
		Assets::Diagnostics arrDiagnostics;
		if (!stTemporalState.CommitFrame(stTemporalFrame.nToken, arrDiagnostics))
		{
			return Fail("Commit submitted temporal frame");
		}
		if (stRenderConfiguration.stTemporal.bEnabled)
		{
			nHistoryRead = 1 - nHistoryRead;
			bHistoryReady = true;
		}
		if (stForwardEffects.bVolume)
		{
			nVolumeRead = 1 - nVolumeRead;
			bVolumeHistoryReady = true;
			stPreviousVolumeCamera = stCameraMatrices;
		}
		nExposureRead = 1 - nExposureRead;
		bExposureReady = true;
		dLastPostSeconds = dSeconds;
	}
	stFrame.bTimingPending = true;
	stFrame.nTimingFrame = nFrames;
	stTiming.nGraphicsFence = stFrame.nGraphicsFence;
	++nFrames;
	if (bCapture && (!stGraphics.Wait(stFrame.nGraphicsFence) || !ReadCapture()))
	{
		return false;
	}
	DXGI_QUERY_VIDEO_MEMORY_INFO stMemory{};
	if (SUCCEEDED(stAdapter->QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_LOCAL, &stMemory)))
	{
		nPeakLocalMemory = (std::max)(nPeakLocalMemory, stMemory.CurrentUsage);
	}
	return true;
}

bool VisualRuntime::Resize()
{
	if (!stGraphics.Flush() || !stCompute.Flush())
	{
		return Fail("Flush before resize");
	}
	for (std::uint32_t nIndex = 0; nIndex < FRAME_COUNT; ++nIndex)
	{
		if (!CollectTiming(arrFrames[nIndex]))
		{
			return false;
		}
		arrBackbuffers[nIndex].Reset();
		arrFrames[nIndex].stColor.Reset();
		arrFrames[nIndex].stHdr.Reset();
		arrFrames[nIndex].stDirectionalShadow.Reset();
		arrFrames[nIndex].stLocalShadow.Reset();
		arrFrames[nIndex].stDepth.Reset();
		arrFrames[nIndex].stMotion.Reset();
		arrFrames[nIndex].stObjectId.Reset();
		arrFrames[nIndex].stEnvironmentSpecular.Reset();
		arrFrames[nIndex].stReflection.Reset();
		arrFrames[nIndex].stReflectedHdr.Reset();
		arrFrames[nIndex].stForwardHdr.Reset();
		arrFrames[nIndex].stReactiveMask.Reset();
		for (ComOwner<ID3D12Resource> &stTarget : arrFrames[nIndex].arrVolume)
		{
			stTarget.Reset();
		}
		for (ComOwner<ID3D12Resource> &stTarget : arrFrames[nIndex].arrReflectionMips)
		{
			stTarget.Reset();
		}
		for (ComOwner<ID3D12Resource> &stTarget : arrFrames[nIndex].arrGbuffer)
		{
			stTarget.Reset();
		}
		for (ComOwner<ID3D12Resource> &stTarget : arrFrames[nIndex].arrMaterialBuffers)
		{
			stTarget.Reset();
		}
	}
	stCapture.Reset();
	nWidth = stWindow.GetWidth();
	nHeight = stWindow.GetHeight();
	const HRESULT nResult = stSwapchain->ResizeBuffers(FRAME_COUNT, nWidth, nHeight, COLOR_FORMAT, bTearing ? DXGI_SWAP_CHAIN_FLAG_ALLOW_TEARING : 0);
	if (FAILED(nResult))
	{
		return Fail("ResizeBuffers", nResult);
	}
	++nResizes;
	return ResetTemporalHistory() && CreateTargets();
}

bool VisualRuntime::ReadCapture()
{
	void *pMapped = nullptr;
	const D3D12_RANGE stReadRange{ 0, static_cast<SIZE_T>(nCaptureBytes) };
	if (FAILED(stCapture->Map(0, &stReadRange, &pMapped)))
	{
		return Fail("Map image readback");
	}
	std::ofstream stFile(std::filesystem::u8path(stConfig.strCapturePath), std::ios::binary);
	stFile << "P6\n"
		   << nWidth << ' ' << nHeight << "\n255\n";
	const std::uint8_t *pPixels = static_cast<const std::uint8_t *>(pMapped) + stCaptureFootprint.Offset;
	for (std::uint32_t nRow = 0; nRow < nHeight; ++nRow)
	{
		const std::uint8_t *pRow = pPixels + static_cast<std::size_t>(nRow) * stCaptureFootprint.Footprint.RowPitch;
		for (std::uint32_t nColumn = 0; nColumn < nWidth; ++nColumn)
		{
			stFile.write(reinterpret_cast<const char *>(pRow + nColumn * 4), 3);
		}
	}
	const D3D12_RANGE stNoWrite{ 0, 0 };
	stCapture->Unmap(0, &stNoWrite);
	stFile.flush();
	stFile.close();
	bCaptureWritten = stFile.good();
	return bCaptureWritten || Fail("Write capture file");
}

bool VisualRuntime::CheckValidation()
{
	if (stInfo.Get() == nullptr)
	{
		return true;
	}
	const UINT64 nMessageCount = stInfo->GetNumStoredMessagesAllowedByRetrievalFilter();
	for (UINT64 nIndex = 0; nIndex < nMessageCount; ++nIndex)
	{
		SIZE_T nBytes = 0;
		if (FAILED(stInfo->GetMessage(nIndex, nullptr, &nBytes)))
		{
			return Fail("Read validation message size");
		}
		std::vector<std::uint8_t> arrStorage(nBytes);
		D3D12_MESSAGE *pMessage = reinterpret_cast<D3D12_MESSAGE *>(arrStorage.data());
		if (FAILED(stInfo->GetMessage(nIndex, pMessage, &nBytes)))
		{
			return Fail("Read validation message");
		}
		if (pMessage->Severity <= D3D12_MESSAGE_SEVERITY_WARNING)
		{
			arrMessages.emplace_back(pMessage->pDescription);
		}
		if (pMessage->Severity <= D3D12_MESSAGE_SEVERITY_ERROR)
		{
			++nValidationErrors;
		}
	}
	return nValidationErrors == 0 || Fail("GPU validation reported errors");
}

bool VisualRuntime::Run()
{
	(void)stWindow.ConsumeResize();
	const std::chrono::steady_clock::time_point stStart = std::chrono::steady_clock::now();
	while (!stWindow.ShouldClose() && (stConfig.nFrameLimit == 0 || nFrames < stConfig.nFrameLimit))
	{
		const std::chrono::steady_clock::time_point stFrameStart = std::chrono::steady_clock::now();
		stWindow.PumpEvents();
		const Platform::Windows::InputState &stInput = stWindow.GetInputState();
		if (stInput.arrKeys[VK_ESCAPE] || stInput.arrPressed[VK_ESCAPE])
		{
			break;
		}
		if (!stConfig.bConnect)
		{
			fCameraX += (stInput.arrKeys['D'] ? 0.01F : 0.0F) - (stInput.arrKeys['A'] ? 0.01F : 0.0F);
			fCameraY += (stInput.arrKeys['W'] ? 0.01F : 0.0F) - (stInput.arrKeys['S'] ? 0.01F : 0.0F);
		}
		if (bNetworkStartedAfterGpuWarmup)
		{
			Gameplay::Vector3 vInput{
				(stInput.arrKeys['D'] ? 1.0F : 0.0F) - (stInput.arrKeys['A'] ? 1.0F : 0.0F),
				0.0F,
				(stInput.arrKeys['S'] ? 1.0F : 0.0F) - (stInput.arrKeys['W'] ? 1.0F : 0.0F)
			};
			const float fLength = std::sqrt(vInput.LengthSquared());
			if (fLength > 1.0F)
			{
				vInput = Gameplay::Scale(vInput, 1.0F / fLength);
			}
			Gameplay::Vector3 vPulse{
				(stInput.arrPressed['D'] ? 1.0F : 0.0F) - (stInput.arrPressed['A'] ? 1.0F : 0.0F),
				0.0F,
				(stInput.arrPressed['S'] ? 1.0F : 0.0F) - (stInput.arrPressed['W'] ? 1.0F : 0.0F)
			};
			const float fPulseLength = std::sqrt(vPulse.LengthSquared());
			if (fPulseLength > 0 && stClient.IsConnected())
			{
				vPulse = Gameplay::Scale(vPulse, 1.0F / fPulseLength);
				if (stClient.QueueMovementPulse(vPulse) != Runtime::RuntimeStatus::Ok)
				{
					return Fail("Queue short gameplay input");
				}
			}
			const Runtime::SystemClock stClock;
			const Runtime::RuntimeStatus eNetworkStatus = stClient.Tick(stClock.NowMsec(), vInput);
			if (eNetworkStatus != Runtime::RuntimeStatus::Ok)
			{
				return Fail("Network visual client step status=" + std::to_string(static_cast<unsigned int>(eNetworkStatus)));
			}
			stClientSnapshot = stClient.GetSnapshot();
			if (nHistoryGeneration != stClientSnapshot.nGeneration)
			{
				nHistoryGeneration = stClientSnapshot.nGeneration;
				if (!ResetTemporalHistory())
				{
					return false;
				}
			}
			if (stClient.HasSucceeded())
			{
				RecordNetworkSample(vInput);
				break;
			}
			if (stInput.arrPressed['R'] && stClient.IsConnected())
			{
				if (stClient.RequestReconnect(100) != Runtime::RuntimeStatus::Ok)
				{
					return Fail("Request gameplay reconnect");
				}
				++nReconnectRequests;
				if (!ResetTemporalHistory())
				{
					return false;
				}
			}
			if (!stWindow.IsMinimized())
			{
				RecordNetworkSample(vInput.LengthSquared() > 0 ? vInput : vPulse);
			}
		}
		if (stWindow.IsMinimized())
		{
			if (!bWasMinimized && !ResetTemporalHistory())
			{
				return false;
			}
			bWasMinimized = true;
			Sleep(10);
			continue;
		}
		if (bWasMinimized)
		{
			bWasMinimized = false;
			if (!ResetTemporalHistory())
			{
				return false;
			}
		}
		if (stWindow.ConsumeResize() && !Resize())
		{
			return false;
		}
		const double dSeconds = stConfig.bDeterministic ? static_cast<double>(nFrames) / 60.0 : std::chrono::duration<double>(stFrameStart - stStart).count();
		const bool bCapture = !stConfig.strCapturePath.empty() && (stConfig.nFrameLimit == 0 ? nFrames == 60 : nFrames + 1 == stConfig.nFrameLimit);
		if (!RenderFrame(dSeconds, bCapture))
		{
			return false;
		}
		if (stConfig.bConnect && !bNetworkStartedAfterGpuWarmup)
		{
			// Driver validation can block the first draw for longer than a transport timeout.
			// Retire that work before starting the peer's handshake clock.
			if (!stGraphics.Flush() || !stCompute.Flush())
			{
				return Fail("Retire GPU warmup before network startup");
			}
			Runtime::RuntimeConfig stNetwork;
			stNetwork.eRole = Runtime::RuntimeRole::Client;
			stNetwork.bNetworkMode = true;
			stNetwork.strAssetPackagePath = stConfig.strAssetPackagePath;
			stNetwork.strBindAddress = stConfig.strServerAddress;
			stNetwork.strClientId = stConfig.strClientId;
			stNetwork.nPort = stConfig.nServerPort;
			const Runtime::RuntimeStatus eNetworkStatus = stClient.Initialize(stNetwork);
			if (eNetworkStatus != Runtime::RuntimeStatus::Ok)
			{
				return Fail("Initialize visual gameplay session status=" + std::to_string(static_cast<unsigned int>(eNetworkStatus)));
			}
			if (stClient.GetPackageDigest() != stRenderScene.strPackageDigest)
			{
				return Fail("Simulation scene package changed before network startup");
			}
			bNetworkStartedAfterGpuWarmup = true;
			std::cout << "ENGINE_NEXT_VISUAL_NETWORK_START client_id=" << stConfig.strClientId << " after_gpu_warmup=1 frame=" << nFrames << '\n'
					  << std::flush;
		}
		Timing(nFrames - 1).dCpuMsec = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - stFrameStart).count();
		if (stConfig.bExerciseResize && (nFrames == 3 || nFrames == 6))
		{
			const HWND hWindow = static_cast<HWND>(stWindow.GetNativeHandle());
			RECT stRect{ 0, 0, static_cast<LONG>(stConfig.nWidth + (nFrames == 3 ? 64 : 0)), static_cast<LONG>(stConfig.nHeight) };
			(void)AdjustWindowRect(&stRect, WS_OVERLAPPEDWINDOW, FALSE);
			(void)SetWindowPos(hWindow, nullptr, 0, 0, stRect.right - stRect.left, stRect.bottom - stRect.top, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
		}
	}
	if (!stGraphics.Flush() || !stCompute.Flush())
	{
		return Fail("Final queue flush");
	}
	for (FrameContext &stFrame : arrFrames)
	{
		if (!CollectTiming(stFrame))
		{
			return false;
		}
	}
	if (!stConfig.strCapturePath.empty() && !bCaptureWritten)
	{
		return Fail("Requested capture did not reach its capture frame");
	}
	return CheckValidation();
}

void VisualRuntime::RecordNetworkSample(const Gameplay::Vector3 &vInput)
{
	using Serialization::JsonValue;
	if (vInput.LengthSquared() > 0)
	{
		++nNetworkInputFrames;
	}
	if (nFrames % 30 != 0 && stClientSnapshot.nGeneration == nObservedGeneration && vInput.LengthSquared() == 0)
	{
		return;
	}
	nObservedGeneration = stClientSnapshot.nGeneration;
	if (arrNetworkSamples.size() >= 4096)
	{
		arrNetworkSamples.erase(arrNetworkSamples.begin());
	}
	JsonValue::Object mapSample;
	mapSample["frame"] = JsonValue(static_cast<std::int64_t>(nFrames));
	mapSample["generation"] = JsonValue(static_cast<std::int64_t>(stClientSnapshot.nGeneration));
	mapSample["session_id"] = JsonValue(std::to_string(stClientSnapshot.nSessionId));
	mapSample["sample_time_msec"] = JsonValue(std::to_string(stClientSnapshot.nSampleTimeMsec));
	mapSample["connected"] = JsonValue(stClientSnapshot.bConnected);
	mapSample["input"] = JsonValue(JsonValue::List{ JsonValue(vInput.fX), JsonValue(vInput.fY), JsonValue(vInput.fZ) });
	JsonValue::List arrEntities;
	for (const Runtime::ClientEntitySnapshot &stEntity : stClientSnapshot.arrEntities)
	{
		JsonValue::Object mapEntity;
		mapEntity["entity_id"] = JsonValue(std::to_string(stEntity.stEntityId.nValue));
		mapEntity["local"] = JsonValue(stEntity.bLocal);
		mapEntity["position"] = JsonValue(JsonValue::List{ JsonValue(stEntity.stState.vPosition.fX), JsonValue(stEntity.stState.vPosition.fY), JsonValue(stEntity.stState.vPosition.fZ) });
		mapEntity["confirmed_sequence"] = JsonValue(std::to_string(stEntity.stState.nConfirmedSequence));
		mapEntity["interpolation"] = JsonValue(static_cast<std::int64_t>(stEntity.eInterpolation));
		arrEntities.emplace_back(std::move(mapEntity));
	}
	mapSample["entities"] = JsonValue(std::move(arrEntities));
	JsonValue::List arrDrawPositions;
	for (const GpuDraw &stDraw : arrDraws)
	{
		const std::array<float, 16> arrWorld = DrawTransform(stDraw);
		JsonValue::Object mapDraw;
		mapDraw["entity_id"] = JsonValue(std::to_string(stDraw.nEntityId));
		mapDraw["simulation_entity_id"] = JsonValue(std::to_string(stDraw.nSimulationEntityId));
		mapDraw["position"] = JsonValue(JsonValue::List{ JsonValue(arrWorld[12]), JsonValue(arrWorld[13]), JsonValue(arrWorld[14]) });
		arrDrawPositions.emplace_back(std::move(mapDraw));
	}
	mapSample["draw_positions"] = JsonValue(std::move(arrDrawPositions));
	arrNetworkSamples.emplace_back(std::move(mapSample));
}

Serialization::JsonValue VisualRuntime::DescribeGraph() const
{
	using Serialization::JsonValue;
	JsonValue::Object mapGraph;
	mapGraph["revision"] = JsonValue(std::int64_t{ 1 });
	mapGraph["scope"] = JsonValue("Fixed pass structure shared by every recorded frame; native allocations vary by frame context and resize.");
	JsonValue::List arrPasses;
	for (const CompiledPass &stPass : stCompiled.arrPasses)
	{
		JsonValue::Object mapPass;
		mapPass["id"] = JsonValue(static_cast<std::int64_t>(stPass.nPass));
		mapPass["name"] = JsonValue(stPass.strName);
		mapPass["queue"] = JsonValue(QueueName(stPass.eQueue));
		mapPass["before_barriers"] = DescribeBarriers(stPass.arrBeforeBarriers);
		mapPass["after_barriers"] = DescribeBarriers(stPass.arrAfterBarriers);
		mapPass["signal_required"] = JsonValue(stPass.bSignalRequired);
		JsonValue::List arrWaits;
		for (PassId nProducer : stPass.arrWaits)
		{
			arrWaits.emplace_back(static_cast<std::int64_t>(nProducer));
		}
		mapPass["waits"] = JsonValue(std::move(arrWaits));
		JsonValue::List arrAccesses;
		for (const ResourceAccess &stAccess : stPass.arrAccesses)
		{
			JsonValue::Object mapAccess;
			mapAccess["resource_id"] = JsonValue(static_cast<std::int64_t>(stAccess.nResource));
			mapAccess["state"] = JsonValue(StateName(stAccess.eState));
			mapAccess["write"] = JsonValue(stAccess.bWrite);
			mapAccess["read_before_write"] = JsonValue(stAccess.bReadBeforeWrite);
			mapAccess["first_subresource"] = JsonValue(static_cast<std::int64_t>(stAccess.nFirstSubresource));
			mapAccess["subresource_count"] = stAccess.nSubresourceCount == ALL_SUBRESOURCES ? JsonValue("all_remaining") : JsonValue(static_cast<std::int64_t>(stAccess.nSubresourceCount));
			arrAccesses.emplace_back(std::move(mapAccess));
		}
		mapPass["accesses"] = JsonValue(std::move(arrAccesses));
		arrPasses.emplace_back(std::move(mapPass));
	}
	mapGraph["passes"] = JsonValue(std::move(arrPasses));
	JsonValue::List arrResources;
	for (const CompiledResource &stResource : stCompiled.arrResources)
	{
		JsonValue::Object mapResource;
		mapResource["id"] = JsonValue(static_cast<std::int64_t>(stResource.nResource));
		mapResource["name"] = JsonValue(stResource.stDescription.strName);
		mapResource["imported"] = JsonValue(stResource.stDescription.bImported);
		mapResource["initial_state"] = JsonValue(StateName(stResource.stDescription.eInitialState));
		mapResource["subresources"] = JsonValue(static_cast<std::int64_t>(stResource.stDescription.nSubresourceCount));
		mapResource["first_pass_id"] = JsonValue(static_cast<std::int64_t>(stResource.nFirstPass));
		mapResource["last_pass_id"] = JsonValue(static_cast<std::int64_t>(stResource.nLastPass));
		mapResource["first_use_index"] = JsonValue(static_cast<std::int64_t>(stResource.nFirstUseIndex));
		mapResource["last_use_index"] = JsonValue(static_cast<std::int64_t>(stResource.nLastUseIndex));
		mapResource["queue_mask"] = JsonValue(static_cast<std::int64_t>(stResource.nQueueMask));
		mapResource["allocation_id"] = JsonValue(static_cast<std::int64_t>(stResource.nAllocationId));
		JsonValue::List arrStates;
		for (ResourceState eState : stResource.arrFinalStates)
		{
			arrStates.emplace_back(StateName(eState));
		}
		mapResource["final_states"] = JsonValue(std::move(arrStates));
		arrResources.emplace_back(std::move(mapResource));
	}
	mapGraph["resources"] = JsonValue(std::move(arrResources));
	return JsonValue(std::move(mapGraph));
}

Serialization::JsonValue VisualRuntime::ReadDred() const
{
	using Serialization::JsonValue;
	JsonValue::Object mapDred;
	if (stDevice.Get() == nullptr)
	{
		mapDred["state"] = JsonValue("device_not_created");
		return JsonValue(std::move(mapDred));
	}
	const HRESULT nRemovedReason = stDevice->GetDeviceRemovedReason();
	if (SUCCEEDED(nRemovedReason))
	{
		mapDred["state"] = JsonValue("not_removed");
		return JsonValue(std::move(mapDred));
	}
	ComOwner<ID3D12DeviceRemovedExtendedData> stDred;
	const HRESULT nQueryResult = stDevice->QueryInterface(IID_PPV_ARGS(stDred.Put()));
	mapDred["query_hresult"] = JsonValue(static_cast<std::int64_t>(nQueryResult));
	if (FAILED(nQueryResult))
	{
		mapDred["state"] = JsonValue("unavailable");
		return JsonValue(std::move(mapDred));
	}
	D3D12_DRED_AUTO_BREADCRUMBS_OUTPUT stBreadcrumbs{};
	const HRESULT nBreadcrumbResult = stDred->GetAutoBreadcrumbsOutput(&stBreadcrumbs);
	mapDred["breadcrumbs_hresult"] = JsonValue(static_cast<std::int64_t>(nBreadcrumbResult));
	if (SUCCEEDED(nBreadcrumbResult))
	{
		JsonValue::List arrBreadcrumbs;
		const D3D12_AUTO_BREADCRUMB_NODE *pNode = stBreadcrumbs.pHeadAutoBreadcrumbNode;
		constexpr std::uint32_t MAX_NODES = 256;
		constexpr std::uint32_t MAX_OPERATIONS = 128;
		for (std::uint32_t nIndex = 0; pNode != nullptr && nIndex < MAX_NODES; ++nIndex)
		{
			JsonValue::Object mapNode;
			mapNode["command_list"] = JsonValue(DebugName(pNode->pCommandListDebugNameA, pNode->pCommandListDebugNameW));
			mapNode["queue"] = JsonValue(DebugName(pNode->pCommandQueueDebugNameA, pNode->pCommandQueueDebugNameW));
			mapNode["breadcrumb_count"] = JsonValue(static_cast<std::int64_t>(pNode->BreadcrumbCount));
			const std::uint32_t nCompleted = pNode->pLastBreadcrumbValue == nullptr ? 0 : (std::min)(*pNode->pLastBreadcrumbValue, pNode->BreadcrumbCount);
			mapNode["completed_breadcrumbs"] = pNode->pLastBreadcrumbValue == nullptr ? JsonValue() : JsonValue(static_cast<std::int64_t>(nCompleted));
			const std::uint32_t nFirstOperation = nCompleted > MAX_OPERATIONS / 2 ? nCompleted - MAX_OPERATIONS / 2 : 0;
			const std::uint32_t nOperationCount = (std::min)(MAX_OPERATIONS, pNode->BreadcrumbCount - nFirstOperation);
			mapNode["first_operation_index"] = JsonValue(static_cast<std::int64_t>(nFirstOperation));
			JsonValue::List arrOperations;
			if (pNode->pCommandHistory != nullptr)
			{
				for (std::uint32_t nOperation = 0; nOperation < nOperationCount; ++nOperation)
				{
					arrOperations.emplace_back(static_cast<std::int64_t>(pNode->pCommandHistory[nFirstOperation + nOperation]));
				}
			}
			mapNode["operation_codes"] = JsonValue(std::move(arrOperations));
			mapNode["operations_truncated"] = JsonValue(nOperationCount < pNode->BreadcrumbCount);
			arrBreadcrumbs.emplace_back(std::move(mapNode));
			pNode = pNode->pNext;
		}
		mapDred["breadcrumbs"] = JsonValue(std::move(arrBreadcrumbs));
		mapDred["breadcrumbs_truncated"] = JsonValue(pNode != nullptr);
	}
	D3D12_DRED_PAGE_FAULT_OUTPUT stFault{};
	const HRESULT nFaultResult = stDred->GetPageFaultAllocationOutput(&stFault);
	mapDred["page_fault_hresult"] = JsonValue(static_cast<std::int64_t>(nFaultResult));
	if (SUCCEEDED(nFaultResult))
	{
		mapDred["page_fault_address"] = JsonValue(std::to_string(stFault.PageFaultVA));
		mapDred["existing_allocations"] = DescribeAllocations(stFault.pHeadExistingAllocationNode);
		mapDred["recently_freed_allocations"] = DescribeAllocations(stFault.pHeadRecentFreedAllocationNode);
	}
	mapDred["state"] = JsonValue("device_removed_diagnostics_queried");
	return JsonValue(std::move(mapDred));
}

bool VisualRuntime::WriteReport(bool bSuccess)
{
	using Serialization::JsonValue;
	JsonValue::Object mapReport;
	mapReport["schema_version"] = JsonValue(std::int64_t{ 1 });
	mapReport["render_path"] = JsonValue(bSceneMode ? "deferred_metallic_roughness_hdr" : "fixed_mesh");
	mapReport["hdr_format"] = JsonValue(bSceneMode ? "RGBA16_FLOAT" : "none");
	mapReport["temporal_aa"] = JsonValue(bSceneMode && stRenderConfiguration.stTemporal.bEnabled);
	mapReport["temporal_epoch"] = JsonValue(static_cast<std::int64_t>(stTemporalState.GetEpoch()));
	mapReport["temporal_resets"] = JsonValue(static_cast<std::int64_t>(nHistoryResets));
	mapReport["temporal_sample_index"] = JsonValue(static_cast<std::int64_t>(stTemporalFrame.nSampleIndex));
	mapReport["directional_shadows"] = JsonValue(bSceneMode && stRenderConfiguration.stShadows.bEnabled);
	mapReport["shadow_cascades"] = JsonValue(static_cast<std::int64_t>(bSceneMode ? 4 : 0));
	mapReport["shadow_resolution"] = JsonValue(static_cast<std::int64_t>(stRenderConfiguration.stShadows.nResolution));
	mapReport["shadow_filter"] = JsonValue("pcf_3x3_cascade_blend");
	mapReport["local_lights"] = JsonValue(static_cast<std::int64_t>(stRenderConfiguration.arrPointLights.size() + stRenderConfiguration.arrSpotLights.size()));
	mapReport["local_shadow_views"] = JsonValue(static_cast<std::int64_t>(stLocalShadowData.arrViews.size()));
	mapReport["local_shadow_resolution"] = JsonValue(static_cast<std::int64_t>(stRenderConfiguration.stShadows.nLocalResolution));
	mapReport["local_shadow_filter"] = JsonValue(stRenderConfiguration.stShadows.eFilter == ShadowFilter::Pcss ? "pcss_5x5" : "pcf_3x3");
	mapReport["shadow_split_distances"] = JsonValue::List{};
	for (const ShadowCascade &stCascade : stShadowData.arrCascades)
	{
		mapReport["shadow_split_distances"].GetList()->emplace_back(stCascade.dSplitFar);
	}
	mapReport["tone_mapping"] = JsonValue(bSceneMode ? "exponential_preexposed_hdr" : "none");
	mapReport["exposure"] = JsonValue(stRenderConfiguration.dExposure);
	const ExposureSettings &stExposure = stRenderConfiguration.stExposure;
	mapReport["exposure_mode"] = JsonValue(stExposure.eMode == ExposureMode::Automatic ? "automatic" : stExposure.eMode == ExposureMode::Manual ? "manual"
																																				: "legacy");
	mapReport["manual_ev100"] = JsonValue(stExposure.dManualEv100);
	mapReport["exposure_compensation_ev"] = JsonValue(stExposure.dCompensationEv);
	mapReport["exposure_histogram_bins"] = JsonValue(static_cast<std::int64_t>(EXPOSURE_HISTOGRAM_BINS));
	mapReport["bloom_enabled"] = JsonValue(stRenderConfiguration.stBloom.bEnabled);
	mapReport["bloom_mip_count"] = JsonValue(static_cast<std::int64_t>(stRenderPipeline.arrBloomDown.size()));
	mapReport["bloom_intensity"] = JsonValue(stRenderConfiguration.stBloom.dIntensity);
	mapReport["render_configuration"] = JsonValue(stConfig.strRenderConfigPath);
	mapReport["camera_view_projection"] = JsonValue::List{};
	mapReport["camera_inverse_view_projection"] = JsonValue::List{};
	for (double dValue : stCameraMatrices.arrViewProjection)
	{
		mapReport["camera_view_projection"].GetList()->emplace_back(dValue);
	}
	for (double dValue : stCameraMatrices.arrInverseViewProjection)
	{
		mapReport["camera_inverse_view_projection"].GetList()->emplace_back(dValue);
	}
	mapReport["environment_lighting"] = JsonValue(bSceneMode ? "procedural_hdr_irradiance_ggx_prefilter_split_sum" : "fixed_lambert");
	mapReport["scene_id"] = JsonValue(stRenderScene.strSceneId);
	mapReport["scene_revision"] = JsonValue(stRenderScene.strSceneRevision);
	mapReport["scene_digest"] = JsonValue(stRenderScene.strSceneDigest);
	mapReport["source_package_digest"] = JsonValue(stRenderScene.strPackageDigest);
	std::uint64_t nLoadedClusters = 0;
	std::uint64_t nCookedMipLevels = 0;
	for (const RenderAsset &stAsset : stRenderScene.arrAssets)
	{
		for (const MeshPrimitive &stPrimitive : stAsset.stMesh.arrPrimitives)
		{
			nLoadedClusters += stPrimitive.arrClusters.size();
		}
		for (const CookedTextureVariant &stVariant : stAsset.stTextureCook.arrVariants)
		{
			nCookedMipLevels += stVariant.arrMips.size();
		}
	}
	mapReport["gpu_package_version"] = JsonValue(static_cast<std::int64_t>(stRenderScene.nGpuFormatVersion));
	mapReport["texture_mip_source"] = JsonValue(!bSceneMode ? "none" : (stRenderScene.nGpuFormatVersion == 2 ? "cooked_gpu_package" : "runtime_decode"));
	mapReport["cooked_texture_mip_levels"] = JsonValue(static_cast<std::int64_t>(nCookedMipLevels));
	mapReport["loaded_mesh_clusters"] = JsonValue(static_cast<std::int64_t>(nLoadedClusters));
	mapReport["mesh_cluster_draw_path"] = JsonValue("indexed_primitive");
	mapReport["materials"] = JsonValue(static_cast<std::int64_t>(arrMaterials.size()));
	mapReport["material_extensions"] = JsonValue(bMaterialExtensions);
	mapReport["material_overrides"] = JsonValue(static_cast<std::int64_t>(stRenderConfiguration.stMaterials.arrOverrides.size()));
	mapReport["material_resource_bytes"] = JsonValue(static_cast<std::int64_t>(nMaterialBytes));
	mapReport["material_parameter_format"] = JsonValue(bMaterialExtensions ? "R32G32B32A32_FLOAT" : "disabled");
	mapReport["material_textures"] = JsonValue(static_cast<std::int64_t>(arrMaterials.size() * MATERIAL_TEXTURE_COUNT));
	mapReport["environment_source"] = JsonValue(bSceneMode ? "procedural_linear_hdr_sky" : "none");
	mapReport["environment_dimensions"] = JsonValue(bSceneMode ? "64x64x6" : "none");
	mapReport["irradiance_dimensions"] = JsonValue(bSceneMode ? "32x32x6" : "none");
	mapReport["brdf_lut_dimensions"] = JsonValue(bSceneMode ? "64x64" : "none");
	mapReport["environment_samples"] = JsonValue(static_cast<std::int64_t>(bSceneMode ? 128 : 0));
	mapReport["environment_mips"] = JsonValue(static_cast<std::int64_t>(nEnvironmentMips));
	mapReport["environment_build_msec"] = JsonValue(dEnvironmentBuildMsec);
	mapReport["environment_importance_entries"] = JsonValue(static_cast<std::int64_t>(nEnvironmentAliasEntries));
	mapReport["environment_importance_bytes"] = JsonValue(static_cast<std::int64_t>(nEnvironmentAliasBytes));
	mapReport["texture_upload_bytes"] = JsonValue(static_cast<std::int64_t>(nTextureUploadBytes));
	mapReport["draw_instances"] = JsonValue(static_cast<std::int64_t>(arrDraws.size()));
	mapReport["scene_triangles"] = JsonValue(static_cast<std::int64_t>(nSceneTriangles));
	mapReport["network_start_after_gpu_warmup"] = JsonValue(bNetworkStartedAfterGpuWarmup);
	mapReport["network_input_frames"] = JsonValue(static_cast<std::int64_t>(nNetworkInputFrames));
	mapReport["network_reconnect_requests"] = JsonValue(static_cast<std::int64_t>(nReconnectRequests));
	mapReport["network_client_id"] = JsonValue(stConfig.strClientId);
	mapReport["network_samples"] = JsonValue(arrNetworkSamples);
	mapReport["network_connected"] = JsonValue(stClientSnapshot.bConnected);
	mapReport["network_generation"] = JsonValue(static_cast<std::int64_t>(stClientSnapshot.nGeneration));
	mapReport["success"] = JsonValue(bSuccess);
	mapReport["failure"] = JsonValue(strFailure);
	mapReport["frames"] = JsonValue(static_cast<std::int64_t>(nFrames));
	mapReport["width"] = JsonValue(static_cast<std::int64_t>(nWidth));
	mapReport["height"] = JsonValue(static_cast<std::int64_t>(nHeight));
	mapReport["resizes"] = JsonValue(static_cast<std::int64_t>(nResizes));
	mapReport["gpu_validation"] = JsonValue(stConfig.bValidation);
	mapReport["validation_errors"] = JsonValue(static_cast<std::int64_t>(nValidationErrors));
	mapReport["capture_written"] = JsonValue(bCaptureWritten);
	mapReport["shader_model"] = JsonValue(static_cast<std::int64_t>(nShaderModel));
	mapReport["raytracing_tier"] = JsonValue(static_cast<std::int64_t>(nRaytracingTier));
	mapReport["feature_level_minimum"] = JsonValue("12_0");
	mapReport["adapter_luid_low"] = JsonValue(static_cast<std::int64_t>(stAdapterDescription.AdapterLuid.LowPart));
	mapReport["adapter_luid_high"] = JsonValue(static_cast<std::int64_t>(stAdapterDescription.AdapterLuid.HighPart));
	mapReport["dedicated_video_memory"] = JsonValue(static_cast<std::int64_t>(stAdapterDescription.DedicatedVideoMemory));
	mapReport["peak_local_memory"] = JsonValue(static_cast<std::int64_t>(nPeakLocalMemory));
	mapReport["screen_space_reflections"] = JsonValue(bSceneMode && stRenderConfiguration.stReflections.bEnabled);
	mapReport["volumetric_fog"] = JsonValue(stForwardEffects.bVolume);
	mapReport["volume_grid_width"] = JsonValue(static_cast<std::int64_t>(stVolumeGrid.nWidth));
	mapReport["volume_grid_height"] = JsonValue(static_cast<std::int64_t>(stVolumeGrid.nHeight));
	mapReport["volume_grid_depth"] = JsonValue(static_cast<std::int64_t>(stVolumeGrid.nDepth));
	mapReport["volume_resource_bytes"] = JsonValue(static_cast<std::int64_t>(nVolumeBytes));
	mapReport["volume_payload_bytes"] = JsonValue(static_cast<std::int64_t>(stVolumeGrid.nResidentVolumeBytes));
	mapReport["volume_coefficients_format"] = JsonValue("RGBA32_FLOAT");
	mapReport["volume_integral_format"] = JsonValue("RGBA16_FLOAT");
	mapReport["transparency"] = JsonValue(stForwardEffects.bTransparency);
	mapReport["particle_emitters"] = JsonValue(static_cast<std::int64_t>(stRenderConfiguration.arrParticles.size()));
	mapReport["peak_particles"] = JsonValue(static_cast<std::int64_t>(nPeakParticles));
	mapReport["particle_upload_bytes"] = JsonValue(static_cast<std::int64_t>(nParticleUploadBytes));
	mapReport["transparent_mesh_draws"] = JsonValue(static_cast<std::int64_t>(arrTransparentOrder.size()));
	mapReport["forward_resource_bytes"] = JsonValue(static_cast<std::int64_t>(nForwardBytes));
	mapReport["reflection_resource_bytes"] = JsonValue(static_cast<std::int64_t>(nReflectionBytes));
	mapReport["reflection_color_mips"] = JsonValue(static_cast<std::int64_t>(bSceneMode && stRenderConfiguration.stReflections.bEnabled ? REFLECTION_MIP_COUNT : 0));
	mapReport["vsync"] = JsonValue(stConfig.bVsync);
	mapReport["tearing_supported"] = JsonValue(bTearing);
	mapReport["compute_queue_used"] = JsonValue(nFrames > 0);
	mapReport["async_overlap_measured"] = JsonValue(false);
	mapReport["timing_sample_capacity"] = JsonValue(static_cast<std::int64_t>(MAX_TIMING_SAMPLES));
	const int nNameLength = WideCharToMultiByte(CP_UTF8, 0, stAdapterDescription.Description, -1, nullptr, 0, nullptr, nullptr);
	std::string strAdapterName(nNameLength > 0 ? static_cast<std::size_t>(nNameLength) : 0, '\0');
	if (nNameLength > 0)
	{
		(void)WideCharToMultiByte(CP_UTF8, 0, stAdapterDescription.Description, -1, strAdapterName.data(), nNameLength, nullptr, nullptr);
		strAdapterName.pop_back();
	}
	mapReport["adapter"] = JsonValue(strAdapterName);
	const Platform::Windows::InputState &stInput = stWindow.GetInputState();
	mapReport["input_key_events"] = JsonValue(static_cast<std::int64_t>(stInput.nKeyEventCount));
	JsonValue::List arrCpu;
	JsonValue::List arrGpu;
	JsonValue::List arrCompute;
	JsonValue::List arrSamples;
	const std::uint32_t nFirstFrame = nFrames > MAX_TIMING_SAMPLES ? nFrames - static_cast<std::uint32_t>(MAX_TIMING_SAMPLES) : 0;
	for (std::uint32_t nFrame = nFirstFrame; nFrame < nFrames; ++nFrame)
	{
		const FrameTiming &stTiming = Timing(nFrame);
		JsonValue::Object mapTiming;
		mapTiming["frame_id"] = JsonValue(static_cast<std::int64_t>(nFrame));
		mapTiming["graph_revision"] = JsonValue(std::int64_t{ 1 });
		mapTiming["width"] = JsonValue(static_cast<std::int64_t>(stTiming.nWidth));
		mapTiming["height"] = JsonValue(static_cast<std::int64_t>(stTiming.nHeight));
		mapTiming["graphics_fence"] = JsonValue(std::to_string(stTiming.nGraphicsFence));
		mapTiming["compute_fence"] = JsonValue(std::to_string(stTiming.nComputeFence));
		mapTiming["cpu_frame_msec"] = JsonValue(stTiming.dCpuMsec);
		mapTiming["gpu_ready"] = JsonValue(stTiming.bGpuReady);
		mapTiming["temporal_epoch"] = JsonValue(static_cast<std::int64_t>(stTiming.nTemporalEpoch));
		mapTiming["temporal_sample"] = JsonValue(static_cast<std::int64_t>(stTiming.nTemporalSample));
		mapTiming["temporal_read_index"] = JsonValue(static_cast<std::int64_t>(stTiming.nTemporalRead));
		mapTiming["temporal_write_index"] = JsonValue(static_cast<std::int64_t>(1 - stTiming.nTemporalRead));
		mapTiming["temporal_history_valid"] = JsonValue(stTiming.bTemporalHistoryValid);
		mapTiming["temporal_jitter"] = JsonValue::List{ stTiming.arrTemporalJitter[0], stTiming.arrTemporalJitter[1] };
		mapTiming["postprocess_ready"] = JsonValue(stTiming.bPostReady);
		mapTiming["volume_history_valid"] = JsonValue(stTiming.bVolumeHistoryValid);
		mapTiming["volume_history_read_index"] = JsonValue(static_cast<std::int64_t>(stTiming.nVolumeHistoryRead));
		mapTiming["particles"] = JsonValue(static_cast<std::int64_t>(stTiming.nParticles));
		mapTiming["lighting_seconds"] = JsonValue(stTiming.dLightingSeconds);
		mapTiming["directional_illuminance"] = JsonValue(stTiming.dDirectionalIlluminance);
		if (stTiming.bPostReady)
		{
			JsonValue::List arrExposureRecord;
			for (float fValue : stTiming.arrExposure)
			{
				arrExposureRecord.emplace_back(static_cast<double>(fValue));
			}
			mapTiming["exposure_record"] = JsonValue(std::move(arrExposureRecord));
			mapTiming["display_exposure"] = JsonValue(static_cast<double>(stTiming.arrExposure[0]));
			mapTiming["frame_pre_exposure"] = JsonValue(static_cast<double>(stTiming.arrExposure[1]));
			mapTiming["target_ev100"] = JsonValue(static_cast<double>(stTiming.arrExposure[2]));
			mapTiming["metered_luminance"] = JsonValue(static_cast<double>(stTiming.arrExposure[3]));
			mapTiming["meter_finite_pixels"] = JsonValue(static_cast<std::int64_t>(stTiming.nMeterFinite));
			mapTiming["meter_invalid_pixels"] = JsonValue(static_cast<std::int64_t>(stTiming.nMeterInvalid));
		}

		mapTiming["graphics_msec"] = stTiming.bGpuReady ? JsonValue(stTiming.dGraphicsMsec) : JsonValue();
		mapTiming["compute_msec"] = stTiming.bGpuReady ? JsonValue(stTiming.dComputeMsec) : JsonValue();
		JsonValue::List arrPassTimes;
		for (std::size_t nPassIndex = 0; nPassIndex < stTiming.arrPassMsec.size() && nPassIndex < stCompiled.arrPasses.size(); ++nPassIndex)
		{
			JsonValue::Object mapPass;
			mapPass["pass_id"] = JsonValue(static_cast<std::int64_t>(stCompiled.arrPasses[nPassIndex].nPass));
			mapPass["gpu_msec"] = stTiming.bGpuReady ? JsonValue(stTiming.arrPassMsec[nPassIndex]) : JsonValue();
			arrPassTimes.emplace_back(std::move(mapPass));
		}
		mapTiming["passes"] = JsonValue(std::move(arrPassTimes));
		arrSamples.emplace_back(std::move(mapTiming));
		arrCpu.emplace_back(stTiming.dCpuMsec);
		arrGpu.push_back(stTiming.bGpuReady ? JsonValue(stTiming.dGraphicsMsec) : JsonValue());
		arrCompute.push_back(stTiming.bGpuReady ? JsonValue(stTiming.dComputeMsec) : JsonValue());
	}
	mapReport["frame_samples"] = JsonValue(std::move(arrSamples));
	mapReport["first_recorded_frame_id"] = JsonValue(static_cast<std::int64_t>(nFirstFrame));
	mapReport["discarded_old_frame_samples"] = JsonValue(static_cast<std::int64_t>(nFirstFrame));
	mapReport["timing_scope"] = JsonValue("CPU frame includes event handling, fence waits and presentation; GPU pass intervals include their resource barriers. Present pass GPU time covers release barriers, not display scanout.");
	mapReport["cpu_frame_msec"] = JsonValue(std::move(arrCpu));
	mapReport["graphics_msec"] = JsonValue(std::move(arrGpu));
	mapReport["compute_msec"] = JsonValue(std::move(arrCompute));
	JsonValue::List arrValidation;
	for (const std::string &strMessage : arrMessages)
	{
		arrValidation.emplace_back(strMessage);
	}
	mapReport["validation_messages"] = JsonValue(std::move(arrValidation));
	mapReport["frame_graph"] = DescribeGraph();
	mapReport["dred"] = ReadDred();
	if (stDevice.Get() != nullptr)
	{
		mapReport["device_removed_reason"] = JsonValue(static_cast<std::int64_t>(stDevice->GetDeviceRemovedReason()));
	}
	std::string strJson;
	if (!Serialization::CanonicalJson(JsonValue(std::move(mapReport)), strJson))
	{
		return false;
	}
	if (!stConfig.strReportPath.empty())
	{
		std::ofstream stFile(std::filesystem::u8path(stConfig.strReportPath), std::ios::binary);
		stFile << strJson << '\n';
		stFile.flush();
		stFile.close();
		if (!stFile)
		{
			return false;
		}
	}
	std::cout << "ENGINE_NEXT_VISUAL frames=" << nFrames << " success=" << (bSuccess ? 1 : 0) << " validation_errors=" << nValidationErrors << '\n';
	return true;
}

} // namespace

int RunVisualClient(const VisualConfig &stConfig)
{
	VisualRuntime stRuntime(stConfig);
	const bool bSuccess = stRuntime.Initialize() && stRuntime.Run();
	const bool bReport = stRuntime.WriteReport(bSuccess);
	return bSuccess && bReport ? 0 : 1;
}

} // namespace EngineNext::Rendering
