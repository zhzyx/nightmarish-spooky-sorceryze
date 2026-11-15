/**************************************************************************/
/*  VisualRuntime.cpp                                                               */
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
#include <string>
#include <utility>
#include <vector>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::uint32_t FRAME_COUNT = 3;
constexpr DXGI_FORMAT COLOR_FORMAT = DXGI_FORMAT_R8G8B8A8_UNORM;
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
	ComOwner<ID3D12Resource> stDepth;
	ComOwner<ID3D12Resource> stTint;
	ComOwner<ID3D12Resource> stQueries;
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
	double dCpuMsec = 0.0;
	double dGraphicsMsec = 0.0;
	double dComputeMsec = 0.0;
	std::array<double, 4> arrPassMsec{};
	bool bGpuReady = false;
};

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
	bool CreateTargets();
	bool CreateFrameContexts();
	bool Resize();
	bool BuildGraph();
	bool RenderFrame(double dSeconds, bool bCapture);
	bool CollectTiming(FrameContext &stFrame);
	bool ReadCapture();
	bool CheckValidation();
	FrameTiming &Timing(std::uint32_t nFrame);
	Serialization::JsonValue DescribeGraph() const;
	Serialization::JsonValue ReadDred() const;
	void ApplyBarriers(ID3D12GraphicsCommandList *pList, const std::vector<ResourceBarrier> &arrBarriers, const std::array<ID3D12Resource *, 4> &arrResources);
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
	ComOwner<ID3D12PipelineState> stGraphicsPipeline;
	ComOwner<ID3D12PipelineState> stComputePipeline;
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
	FrameGraph stGraph;
	CompiledGraph stCompiled;
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
	stHeap.NumDescriptors = FRAME_COUNT * 2;
	if (FAILED(stDevice->CreateDescriptorHeap(&stHeap, IID_PPV_ARGS(stRtvHeap.Put()))))
	{
		return Fail("Create RTV heap");
	}
	stHeap.Type = D3D12_DESCRIPTOR_HEAP_TYPE_DSV;
	stHeap.NumDescriptors = FRAME_COUNT;
	if (FAILED(stDevice->CreateDescriptorHeap(&stHeap, IID_PPV_ARGS(stDsvHeap.Put()))))
	{
		return Fail("Create DSV heap");
	}
	stHeap.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
	stHeap.NumDescriptors = FRAME_COUNT * 2;
	stHeap.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
	if (FAILED(stDevice->CreateDescriptorHeap(&stHeap, IID_PPV_ARGS(stViewHeap.Put()))))
	{
		return Fail("Create shader-visible view heap");
	}
	nRtvStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
	nDsvStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_DSV);
	nViewStride = stDevice->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
	return CreateFrameContexts() && CreateTargets() && CreatePipeline() && CreateMesh() && BuildGraph();
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
		stBuffer = BufferDescription(8 * sizeof(std::uint64_t));
		if (FAILED(stDevice->CreateCommittedResource(&stReadback, D3D12_HEAP_FLAG_NONE, &stBuffer, D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(stFrame.stQueries.Put()))))
		{
			return Fail("Create timestamp readback");
		}
		D3D12_SHADER_RESOURCE_VIEW_DESC stSrv{};
		stSrv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
		stSrv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
		stSrv.Buffer.NumElements = 1;
		stSrv.Buffer.StructureByteStride = 16;
		stDevice->CreateShaderResourceView(stFrame.stTint.Get(), &stSrv, View(nIndex * 2));
		D3D12_UNORDERED_ACCESS_VIEW_DESC stUav{};
		stUav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
		stUav.Buffer.NumElements = 1;
		stUav.Buffer.StructureByteStride = 16;
		stDevice->CreateUnorderedAccessView(stFrame.stTint.Get(), nullptr, &stUav, View(nIndex * 2 + 1));
		(void)stFrame.stTint->SetName(L"EngineNext.ComputeTint");
	}
	D3D12_QUERY_HEAP_DESC stQuery{};
	stQuery.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP;
	stQuery.Count = FRAME_COUNT * 6;
	if (FAILED(stDevice->CreateQueryHeap(&stQuery, IID_PPV_ARGS(stGraphicsQueries.Put()))))
	{
		return Fail("Create graphics timestamp heap");
	}
	stQuery.Count = FRAME_COUNT * 2;
	return SUCCEEDED(stDevice->CreateQueryHeap(&stQuery, IID_PPV_ARGS(stComputeQueries.Put()))) || Fail("Create compute timestamp heap");
}

bool VisualRuntime::CreateTargets()
{
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
		stDepthDescription.Format = DXGI_FORMAT_D32_FLOAT;
		stDepthDescription.Flags = D3D12_RESOURCE_FLAG_ALLOW_DEPTH_STENCIL;
		D3D12_CLEAR_VALUE stDepthClear{};
		stDepthClear.Format = DXGI_FORMAT_D32_FLOAT;
		stDepthClear.DepthStencil.Depth = 0.0F;
		if (FAILED(stDevice->CreateCommittedResource(&stHeap, D3D12_HEAP_FLAG_NONE, &stDepthDescription, D3D12_RESOURCE_STATE_DEPTH_WRITE, &stDepthClear, IID_PPV_ARGS(stFrame.stDepth.Put()))))
		{
			return Fail("Create depth target");
		}
		stDevice->CreateDepthStencilView(stFrame.stDepth.Get(), nullptr, Dsv(nIndex));
		(void)stFrame.stColor->SetName(L"EngineNext.FrameColor");
		(void)stFrame.stDepth->SetName(L"EngineNext.ReverseDepth");
		(void)arrBackbuffers[nIndex]->SetName(L"EngineNext.Backbuffer");
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

bool VisualRuntime::BuildGraph()
{
	stGraph.Clear();
	const ResourceId nTint = stGraph.AddResource({ "Tint", ResourceState::Common, true });
	const ResourceId nColor = stGraph.AddResource({ "Color", ResourceState::Common, false });
	const ResourceId nDepth = stGraph.AddResource({ "Depth", ResourceState::DepthWrite, true });
	const ResourceId nBackbuffer = stGraph.AddResource({ "Backbuffer", ResourceState::Present, true });
	(void)stGraph.AddPass({ "ComputeTint", QueueType::Compute, { { nTint, ResourceState::UnorderedAccess, true } }, {} });
	(void)stGraph.AddPass({ "FixedMesh", QueueType::Graphics, { { nTint, ResourceState::ShaderRead, false }, { nColor, ResourceState::RenderTarget, true }, { nDepth, ResourceState::DepthWrite, true } }, {} });
	(void)stGraph.AddPass({ "CopyToBackbuffer", QueueType::Graphics, { { nColor, ResourceState::CopySource, false }, { nBackbuffer, ResourceState::CopyDestination, true } }, {} });
	(void)stGraph.AddPass({ "Present", QueueType::Graphics, { { nTint, ResourceState::Common, false }, { nColor, ResourceState::Common, false }, { nBackbuffer, ResourceState::Present, false } }, {} });
	GraphDiagnostic stDiagnostic;
	if (!stGraph.Compile(stCompiled, stDiagnostic))
	{
		return Fail("FrameGraph compilation failed");
	}
	const std::array<const char *, 4> arrPassNames{ "ComputeTint", "FixedMesh", "CopyToBackbuffer", "Present" };
	if (stCompiled.arrPasses.size() != arrPassNames.size() || stCompiled.arrResources.size() != 4)
	{
		return Fail("Fixed renderer graph has an unsupported shape");
	}
	for (std::size_t nIndex = 0; nIndex < arrPassNames.size(); ++nIndex)
	{
		const CompiledPass &stPass = stCompiled.arrPasses[nIndex];
		const QueueType eExpected = nIndex == 0 ? QueueType::Compute : QueueType::Graphics;
		if (stPass.nPass != nIndex || stPass.strName != arrPassNames[nIndex] || stPass.eQueue != eExpected)
		{
			return Fail("Unsupported fixed renderer pass or queue");
		}
		for (const PassId nProducer : stPass.arrWaits)
		{
			if (nProducer != 0 || nIndex != 1)
			{
				return Fail("Unsupported fixed renderer queue dependency");
			}
		}
	}
	return true;
}

void VisualRuntime::ApplyBarriers(ID3D12GraphicsCommandList *pList, const std::vector<ResourceBarrier> &arrBarriers, const std::array<ID3D12Resource *, 4> &arrResources)
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

bool VisualRuntime::CollectTiming(FrameContext &stFrame)
{
	if (!stFrame.bTimingPending)
	{
		return true;
	}
	void *pMapped = nullptr;
	const D3D12_RANGE stReadRange{ 0, 8 * sizeof(std::uint64_t) };
	if (FAILED(stFrame.stQueries->Map(0, &stReadRange, &pMapped)))
	{
		return Fail("Map timestamp queries");
	}
	std::array<std::uint64_t, 8> arrTimes{};
	std::memcpy(arrTimes.data(), pMapped, sizeof(arrTimes));
	const D3D12_RANGE stNoWrite{ 0, 0 };
	stFrame.stQueries->Unmap(0, &stNoWrite);
	if (stCompute.nFrequency == 0 || stGraphics.nFrequency == 0 || arrTimes[1] < arrTimes[0] || arrTimes[7] < arrTimes[2])
	{
		return Fail("Invalid completed GPU timestamps");
	}
	FrameTiming &stTiming = Timing(stFrame.nTimingFrame);
	stTiming.dComputeMsec = 1000.0 * static_cast<double>(arrTimes[1] - arrTimes[0]) / static_cast<double>(stCompute.nFrequency);
	stTiming.dGraphicsMsec = 1000.0 * static_cast<double>(arrTimes[7] - arrTimes[2]) / static_cast<double>(stGraphics.nFrequency);
	stTiming.arrPassMsec[0] = stTiming.dComputeMsec;
	for (std::size_t nPassIndex = 1; nPassIndex < stTiming.arrPassMsec.size(); ++nPassIndex)
	{
		const std::size_t nTimeIndex = nPassIndex * 2;
		if (arrTimes[nTimeIndex + 1] < arrTimes[nTimeIndex])
		{
			return Fail("Invalid completed pass timestamps");
		}
		stTiming.arrPassMsec[nPassIndex] = 1000.0 * static_cast<double>(arrTimes[nTimeIndex + 1] - arrTimes[nTimeIndex]) / static_cast<double>(stGraphics.nFrequency);
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
	const std::array<ID3D12Resource *, 4> arrResources = { stFrame.stTint.Get(), stFrame.stColor.Get(), stFrame.stDepth.Get(), arrBackbuffers[nIndex].Get() };
	const std::array<float, 4> arrConstants{ static_cast<float>(dSeconds), static_cast<float>(nWidth) / static_cast<float>(nHeight), fCameraX, fCameraY };
	ID3D12DescriptorHeap *pHeap = stViewHeap.Get();
	stFrame.stComputeList->SetDescriptorHeaps(1, &pHeap);
	stFrame.stComputeList->SetComputeRootSignature(stComputeRoot.Get());
	stFrame.stComputeList->SetComputeRoot32BitConstants(0, 4, arrConstants.data(), 0);
	stFrame.stComputeList->SetComputeRootDescriptorTable(1, GpuView(nIndex * 2 + 1));
	stFrame.stComputeList->EndQuery(stComputeQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nIndex * 2);
	const CompiledPass &stComputePass = stCompiled.arrPasses[0];
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
	for (const PassId nProducer : stCompiled.arrPasses[1].arrWaits)
	{
		if (nProducer != 0 || FAILED(stGraphics.stQueue->Wait(stCompute.stFence.Get(), stFrame.nComputeFence)))
		{
			return Fail("Cross-queue compute to graphics dependency");
		}
	}
	stTiming.nComputeFence = stFrame.nComputeFence;
	ID3D12GraphicsCommandList *pList = stFrame.stGraphicsList.Get();
	pList->SetDescriptorHeaps(1, &pHeap);
	pList->SetGraphicsRootSignature(stGraphicsRoot.Get());
	pList->SetGraphicsRoot32BitConstants(0, 4, arrConstants.data(), 0);
	pList->SetGraphicsRootDescriptorTable(1, GpuView(nIndex * 2));
	for (std::size_t nPassIndex = 1; nPassIndex < stCompiled.arrPasses.size(); ++nPassIndex)
	{
		const CompiledPass &stPass = stCompiled.arrPasses[nPassIndex];
		const UINT nQueryIndex = nIndex * 6 + static_cast<UINT>((nPassIndex - 1) * 2);
		pList->EndQuery(stGraphicsQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nQueryIndex);
		PIXBeginEvent(pList, PIX_COLOR_DEFAULT, stPass.strName.c_str());
		ApplyBarriers(pList, stPass.arrBeforeBarriers, arrResources);
		if (stPass.strName == "FixedMesh")
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
		else if (stPass.strName == "CopyToBackbuffer")
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
	pList->ResolveQueryData(stGraphicsQueries.Get(), D3D12_QUERY_TYPE_TIMESTAMP, nIndex * 6, 6, stFrame.stQueries.Get(), 2 * sizeof(std::uint64_t));
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
		arrFrames[nIndex].stDepth.Reset();
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
	return CreateTargets();
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
		if (stWindow.IsMinimized())
		{
			Sleep(10);
			continue;
		}
		if (stWindow.ConsumeResize() && !Resize())
		{
			return false;
		}
		const Platform::Windows::InputState &stInput = stWindow.GetInputState();
		if (stInput.arrKeys[VK_ESCAPE])
		{
			break;
		}
		fCameraX += (stInput.arrKeys['D'] ? 0.01F : 0.0F) - (stInput.arrKeys['A'] ? 0.01F : 0.0F);
		fCameraY += (stInput.arrKeys['W'] ? 0.01F : 0.0F) - (stInput.arrKeys['S'] ? 0.01F : 0.0F);
		const double dSeconds = stConfig.bDeterministic ? static_cast<double>(nFrames) / 60.0 : std::chrono::duration<double>(stFrameStart - stStart).count();
		const bool bCapture = !stConfig.strCapturePath.empty() && (stConfig.nFrameLimit == 0 ? nFrames == 60 : nFrames + 1 == stConfig.nFrameLimit);
		if (!RenderFrame(dSeconds, bCapture))
		{
			return false;
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
