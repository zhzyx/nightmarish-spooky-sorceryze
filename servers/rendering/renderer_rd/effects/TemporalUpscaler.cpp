/**************************************************************************/
/*  TemporalUpscaler.cpp                                                  */
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

#include "TemporalUpscaler.h"

#include "core/os/os.h"
#include "servers/rendering/renderer_rd/storage_rd/render_scene_buffers_rd.h"

#ifdef TEMPORAL_SDK_VULKAN
#include "drivers/vulkan/rendering_device_driver_vulkan.h"
#include "drivers/vulkan/UpscalerExtensions.h"
#ifdef D3D12_ENABLED
#include "drivers/d3d12/rendering_device_driver_d3d12.h"
#include <dxgi1_5.h>
#include <ffx_api.h>
#include <ffx_api_types.h>
// The vendor headers reuse callback typedef names with backend-specific signatures.
namespace AmdDx12 {
#include <dx12/ffx_api_dx12.h>
}
#endif
#include <windows.h>
#include <nvsdk_ngx_helpers.h>
#include <nvsdk_ngx_helpers_vk.h>
#include <ffx_api_loader.h>
#include <vk/ffx_api_vk.h>
#include <ffx_upscale.h>

namespace {
using Frame = RendererRD::FSR2Effect::Parameters;

bool IsDirectX()
{
	return OS::get_singleton()->get_current_rendering_driver_name() == "d3d12";
}

struct NativeCommands
{
	VkCommandBuffer stVulkan = VK_NULL_HANDLE;
#ifdef D3D12_ENABLED
	ID3D12GraphicsCommandList *pDirectX = nullptr;
#endif
};

struct NativeImage
{
	VkImage image;
	VkImageView view;
	VkFormat format;
	uint32_t width;
	uint32_t height;

	static NativeImage FromRid(RID ridTexture, Size2i vSize)
	{
		RD *pDevice = RD::get_singleton();
		return {
			(VkImage)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_TEXTURE, ridTexture),
			(VkImageView)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_TEXTURE_VIEW, ridTexture),
			(VkFormat)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_TEXTURE_DATA_FORMAT, ridTexture),
			(uint32_t)vSize.x, (uint32_t)vSize.y
		};
	}

	FfxApiResource AsFsr(bool bOutput) const
	{
#ifdef D3D12_ENABLED
		if (IsDirectX())
		{
			return AmdDx12::ffxApiGetResourceDX12((ID3D12Resource *)image,
					bOutput ? FFX_API_RESOURCE_STATE_UNORDERED_ACCESS : FFX_API_RESOURCE_STATE_COMPUTE_READ);
		}
#endif
		VkImageCreateInfo stInfo{ VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO };
		stInfo.imageType = VK_IMAGE_TYPE_2D;
		stInfo.format = format;
		stInfo.extent = { width, height, 1 };
		stInfo.arrayLayers = 1;
		stInfo.mipLevels = 1;
		stInfo.usage = bOutput ? VK_IMAGE_USAGE_STORAGE_BIT : VK_IMAGE_USAGE_SAMPLED_BIT;
		return ffxApiGetResourceVK((void *)image, ffxApiGetImageResourceDescriptionVK(image, stInfo, 0),
				bOutput ? FFX_API_RESOURCE_STATE_UNORDERED_ACCESS : FFX_API_RESOURCE_STATE_COMPUTE_READ);
	}

	NVSDK_NGX_Resource_VK AsDlss(bool bOutput, VkImageAspectFlags nAspect = VK_IMAGE_ASPECT_COLOR_BIT) const
	{
		return NVSDK_NGX_Create_ImageView_Resource_VK(view, image, { nAspect, 0, 1, 0, 1 }, format, width, height, bOutput);
	}
};

struct Images
{
	NativeImage color;
	NativeImage depth;
	NativeImage velocity;
	NativeImage reactive;
	NativeImage output;
};

class NativeBackend : public RefCounted
{
public:
	String strName;
	virtual bool Record(const NativeCommands &stCmd, const Frame &stFrame, const Images &stImages, bool bReset) = 0;
};

class AmdBackend final : public NativeBackend
{
	HMODULE hLibrary = nullptr;
	ffxFunctions stFunctions = {};
	ffxContext pContext = nullptr;

public:
	bool Initialize(Size2i vInput, Size2i vOutput)
	{
		String strPath = OS::get_singleton()->get_executable_path().get_base_dir().path_join(IsDirectX() ? "amd_fidelityfx_loader_dx12.dll" : "amd_fidelityfx_loader_vk.dll");
		hLibrary = LoadLibraryExW((LPCWSTR)strPath.utf16().get_data(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
		if (!hLibrary)
		{
			return false;
		}
		ffxLoadFunctions(&stFunctions, hLibrary);
		if (!stFunctions.CreateContext || !stFunctions.DestroyContext || !stFunctions.Query || !stFunctions.Dispatch)
		{
			return false;
		}
		RD *pDevice = RD::get_singleton();
		ffxApiHeader *pBackend = nullptr;
#ifdef D3D12_ENABLED
		AmdDx12::ffxCreateBackendDX12Desc stDx = {};
		if (IsDirectX())
		{
			stDx.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12;
			stDx.device = (ID3D12Device *)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_LOGICAL_DEVICE);
			pBackend = &stDx.header;
		}
#endif
		ffxCreateBackendVKDesc stBackend = {};
		stBackend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK;
		stBackend.deviceContext = { (VkDevice)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_LOGICAL_DEVICE),
			(VkPhysicalDevice)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_PHYSICAL_DEVICE), vkGetDeviceProcAddr };
		ffxCreateContextDescUpscale stDesc = {};
		ffxCreateContextDescUpscaleVersion stVersionDesc = {};
		stVersionDesc.header = { FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE_VERSION, pBackend ? pBackend : &stBackend.header };
		stVersionDesc.version = FFX_UPSCALER_VERSION;
		stDesc.header = { FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE, &stVersionDesc.header };
		stDesc.flags = FFX_UPSCALE_ENABLE_DEPTH_INVERTED | FFX_UPSCALE_ENABLE_AUTO_EXPOSURE | FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE;
		stDesc.maxRenderSize = { (uint32_t)vInput.x, (uint32_t)vInput.y };
		stDesc.maxUpscaleSize = { (uint32_t)vOutput.x, (uint32_t)vOutput.y };
		ffxReturnCode_t nResult = stFunctions.CreateContext(&pContext, &stDesc.header, nullptr);
		if (nResult != FFX_API_RETURN_OK)
		{
			WARN_PRINT(vformat("AMD FSR context creation failed (%d).", nResult));
			return false;
		}
		ffxQueryGetProviderVersion stVersion = {};
		stVersion.header.type = FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
		strName = "AMD FSR";
		if (stFunctions.Query(&pContext, &stVersion.header) == FFX_API_RETURN_OK && stVersion.versionName)
		{
			strName += String(" ") + stVersion.versionName;
		}
		return true;
	}

	bool Record(const NativeCommands &stCmd, const Frame &stFrame, const Images &stImages, bool bReset) override
	{
		ffxDispatchDescUpscale stDesc = {};
		stDesc.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE;
		stDesc.commandList = stCmd.stVulkan;
#ifdef D3D12_ENABLED
		if (stCmd.pDirectX)
		{
			stDesc.commandList = stCmd.pDirectX;
		}
#endif
		stDesc.color = stImages.color.AsFsr(false);
		stDesc.depth = stImages.depth.AsFsr(false);
		stDesc.motionVectors = stImages.velocity.AsFsr(false);
		stDesc.reactive = stImages.reactive.AsFsr(false);
		stDesc.output = stImages.output.AsFsr(true);
		stDesc.renderSize = { stImages.color.width, stImages.color.height };
		stDesc.upscaleSize = { stImages.output.width, stImages.output.height };
		stDesc.motionVectorScale = { (float)stImages.color.width, (float)stImages.color.height };
		stDesc.jitterOffset = { stFrame.jitter.x, stFrame.jitter.y };
		stDesc.preExposure = 1.0f;
		stDesc.frameTimeDelta = stFrame.delta_time * 1000.0f;
		stDesc.cameraNear = stFrame.z_near;
		stDesc.cameraFar = stFrame.z_far;
		stDesc.cameraFovAngleVertical = Math::deg_to_rad(stFrame.fovy);
		stDesc.viewSpaceToMetersFactor = 1.0f;
		stDesc.enableSharpening = stFrame.sharpness > 0.0f;
		stDesc.sharpness = stFrame.sharpness;
		stDesc.reset = bReset;
		return stFunctions.Dispatch(&pContext, &stDesc.header) == FFX_API_RETURN_OK;
	}

	~AmdBackend() override
	{
		if (pContext)
		{
			stFunctions.DestroyContext(&pContext, nullptr);
		}
		if (hLibrary)
		{
			FreeLibrary(hLibrary);
		}
	}
};

// NGX initialization belongs to the logical device, while each viewport owns a feature handle.
class NgxDevice final : public RefCounted
{
public:
	static NgxDevice *pActive;
	VkDevice stDevice = VK_NULL_HANDLE;
	static Ref<NgxDevice> Acquire()
	{
		if (pActive)
		{
			return Ref<NgxDevice>(pActive);
		}
		RD *pRD = RD::get_singleton();
		VkDevice stDevice = (VkDevice)pRD->get_driver_resource(RD::DRIVER_RESOURCE_LOGICAL_DEVICE);
		Char16String strDirectory = OS::get_singleton()->get_executable_path().get_base_dir().utf16();
		const wchar_t *pDirectory = (const wchar_t *)strDirectory.get_data();
		NVSDK_NGX_FeatureCommonInfo stInfo = {};
		stInfo.PathListInfo = { &pDirectory, 1 };
		Char16String strData = OS::get_singleton()->get_user_data_dir().utf16();
		NVSDK_NGX_Result eResult;
#ifdef D3D12_ENABLED
		if (IsDirectX())
		{
			eResult = NVSDK_NGX_D3D12_Init_with_ProjectID("646bdd3d-5875-4fe1-8a27-79f87141ae0c", NVSDK_NGX_ENGINE_TYPE_CUSTOM,
					"Godot 4.8", (const wchar_t *)strData.get_data(), (ID3D12Device *)stDevice, &stInfo);
		}
		else
#endif
		{
			eResult = NVSDK_NGX_VULKAN_Init_with_ProjectID("646bdd3d-5875-4fe1-8a27-79f87141ae0c",
				NVSDK_NGX_ENGINE_TYPE_CUSTOM, "Godot 4.8", (const wchar_t *)strData.get_data(),
				(VkInstance)pRD->get_driver_resource(RD::DRIVER_RESOURCE_TOPMOST_OBJECT),
				(VkPhysicalDevice)pRD->get_driver_resource(RD::DRIVER_RESOURCE_PHYSICAL_DEVICE), stDevice,
				vkGetInstanceProcAddr, vkGetDeviceProcAddr, &stInfo);
		}
		if (NVSDK_NGX_FAILED(eResult))
		{
			WARN_PRINT(vformat("DLSS NGX initialization failed (0x%x).", (uint32_t)eResult));
			return {};
		}
		Ref<NgxDevice> refDevice;
		refDevice.instantiate();
		refDevice->stDevice = stDevice;
		pActive = refDevice.ptr();
		return refDevice;
	}

	~NgxDevice() override
	{
#ifdef D3D12_ENABLED
		if (IsDirectX())
		{
			NVSDK_NGX_D3D12_Shutdown1((ID3D12Device *)stDevice);
		}
		else
#endif
		{
			NVSDK_NGX_VULKAN_Shutdown1(stDevice);
		}
		pActive = nullptr;
	}
};

NgxDevice *NgxDevice::pActive = nullptr;

class DlssBackend final : public NativeBackend
{
	template <typename Eval>
	static void SetEvaluationInputs(Eval &stEval, const Frame &stFrame, const Images &stImages, bool bReset)
	{
		stEval.InRenderSubrectDimensions = { stImages.color.width, stImages.color.height };
		stEval.InJitterOffsetX = stFrame.jitter.x;
		stEval.InJitterOffsetY = stFrame.jitter.y;
		stEval.InMVScaleX = (float)stImages.color.width;
		stEval.InMVScaleY = (float)stImages.color.height;
		stEval.InPreExposure = 1.0f;
		stEval.InExposureScale = 1.0f;
		stEval.InReset = bReset;
		stEval.InFrameTimeDeltaInMsec = stFrame.delta_time * 1000.0f;
	}
	Ref<NgxDevice> refDevice;
	NVSDK_NGX_Parameter *pParams = nullptr;
	NVSDK_NGX_Handle *pFeature = nullptr;

public:
	bool Initialize()
	{
		refDevice = NgxDevice::Acquire();
		if (refDevice.is_null())
		{
			return false;
		}
		NVSDK_NGX_Result eResult;
#ifdef D3D12_ENABLED
		if (IsDirectX())
		{
			eResult = NVSDK_NGX_D3D12_GetCapabilityParameters(&pParams);
		}
		else
#endif
		{
			eResult = NVSDK_NGX_VULKAN_GetCapabilityParameters(&pParams);
		}
		if (NVSDK_NGX_FAILED(eResult))
		{
			return false;
		}
		int nAvailable = 0;
		pParams->Get(NVSDK_NGX_Parameter_SuperSampling_Available, &nAvailable);
		strName = "NVIDIA DLSS SR";
		return nAvailable != 0;
	}

	bool Record(const NativeCommands &stCmd, const Frame &stFrame, const Images &stImages, bool bReset) override
	{
		if (!pFeature)
		{
			float fRatio = (float)stImages.color.width / stImages.output.width;
			NVSDK_NGX_DLSS_Create_Params stCreate = {};
			stCreate.Feature.InWidth = stImages.color.width;
			stCreate.Feature.InHeight = stImages.color.height;
			stCreate.Feature.InTargetWidth = stImages.output.width;
			stCreate.Feature.InTargetHeight = stImages.output.height;
			stCreate.Feature.InPerfQualityValue = NVSDK_NGX_PerfQuality_Value_MaxQuality;
			if (stImages.color.width == stImages.output.width && stImages.color.height == stImages.output.height)
			{
				stCreate.Feature.InPerfQualityValue = NVSDK_NGX_PerfQuality_Value_DLAA;
			}
			else if (fRatio < 0.43f)
			{
				stCreate.Feature.InPerfQualityValue = NVSDK_NGX_PerfQuality_Value_UltraPerformance;
			}
			else if (fRatio < 0.55f)
			{
				stCreate.Feature.InPerfQualityValue = NVSDK_NGX_PerfQuality_Value_MaxPerf;
			}
			else if (fRatio < 0.625f)
			{
				stCreate.Feature.InPerfQualityValue = NVSDK_NGX_PerfQuality_Value_Balanced;
			}
			unsigned int nOptimalW = 0, nOptimalH = 0, nMaxW = 0, nMaxH = 0, nMinW = 0, nMinH = 0;
			float fSharpness = 0.0f;
			NVSDK_NGX_Result eSettings = NGX_DLSS_GET_OPTIMAL_SETTINGS(pParams, stImages.output.width, stImages.output.height,
					stCreate.Feature.InPerfQualityValue, &nOptimalW, &nOptimalH, &nMaxW, &nMaxH, &nMinW, &nMinH, &fSharpness);
			if (NVSDK_NGX_FAILED(eSettings) || stImages.color.width < nMinW || stImages.color.width > nMaxW ||
					stImages.color.height < nMinH || stImages.color.height > nMaxH)
			{
				WARN_PRINT(vformat("DLSS input %dx%d falls outside the supported range %dx%d to %dx%d for this preset.", stImages.color.width, stImages.color.height, nMinW, nMinH, nMaxW, nMaxH));
				return false;
			}
			stCreate.InFeatureCreateFlags = NVSDK_NGX_DLSS_Feature_Flags_IsHDR | NVSDK_NGX_DLSS_Feature_Flags_MVLowRes |
					NVSDK_NGX_DLSS_Feature_Flags_DepthInverted | NVSDK_NGX_DLSS_Feature_Flags_AutoExposure;
			NVSDK_NGX_Result eResult;
#ifdef D3D12_ENABLED
			if (stCmd.pDirectX)
			{
				eResult = NGX_D3D12_CREATE_DLSS_EXT(stCmd.pDirectX, 1, 1, &pFeature, pParams, &stCreate);
			}
			else
#endif
			{
				eResult = NGX_VULKAN_CREATE_DLSS_EXT1(refDevice->stDevice, stCmd.stVulkan, 1, 1, &pFeature, pParams, &stCreate);
			}
			if (NVSDK_NGX_FAILED(eResult))
			{
				WARN_PRINT(vformat("DLSS feature creation failed (0x%x).", (uint32_t)eResult));
				return false;
			}
		}
#ifdef D3D12_ENABLED
		if (stCmd.pDirectX)
		{
			NVSDK_NGX_D3D12_DLSS_Eval_Params stEval = {};
			stEval.Feature.pInColor = (ID3D12Resource *)stImages.color.image;
			stEval.Feature.pInOutput = (ID3D12Resource *)stImages.output.image;
			stEval.pInDepth = (ID3D12Resource *)stImages.depth.image;
			stEval.pInMotionVectors = (ID3D12Resource *)stImages.velocity.image;
			stEval.pInBiasCurrentColorMask = (ID3D12Resource *)stImages.reactive.image;
			SetEvaluationInputs(stEval, stFrame, stImages, bReset);
			return !NVSDK_NGX_FAILED(NGX_D3D12_EVALUATE_DLSS_EXT(stCmd.pDirectX, pFeature, pParams, &stEval));
		}
#endif
		NVSDK_NGX_Resource_VK stColor = stImages.color.AsDlss(false);
		NVSDK_NGX_Resource_VK stDepth = stImages.depth.AsDlss(false, ffxApiIsDepthFormat(stImages.depth.format) ? VK_IMAGE_ASPECT_DEPTH_BIT : VK_IMAGE_ASPECT_COLOR_BIT);
		NVSDK_NGX_Resource_VK stReactive = stImages.reactive.AsDlss(false);
		NVSDK_NGX_Resource_VK stVelocity = stImages.velocity.AsDlss(false);
		NVSDK_NGX_Resource_VK stOutput = stImages.output.AsDlss(true);
		NVSDK_NGX_VK_DLSS_Eval_Params stEval = {};
		stEval.Feature.pInColor = &stColor;
		stEval.Feature.pInOutput = &stOutput;
		stEval.pInDepth = &stDepth;
		stEval.pInMotionVectors = &stVelocity;
		stEval.pInBiasCurrentColorMask = &stReactive;
		SetEvaluationInputs(stEval, stFrame, stImages, bReset);
		NVSDK_NGX_Result eResult = NGX_VULKAN_EVALUATE_DLSS_EXT(stCmd.stVulkan, pFeature, pParams, &stEval);
		if (NVSDK_NGX_FAILED(eResult))
		{
			WARN_PRINT(vformat("DLSS Vulkan evaluation failed (0x%x).", (uint32_t)eResult));
			return false;
		}
		return true;
	}

	~DlssBackend() override
	{
#ifdef D3D12_ENABLED
		if (IsDirectX())
		{
			if (pFeature)
			{
				NVSDK_NGX_D3D12_ReleaseFeature(pFeature);
			}
			if (pParams)
			{
				NVSDK_NGX_D3D12_DestroyParameters(pParams);
			}
			return;
		}
#endif
		if (pFeature)
		{
			NVSDK_NGX_VULKAN_ReleaseFeature(pFeature);
		}
		if (pParams)
		{
			NVSDK_NGX_VULKAN_DestroyParameters(pParams);
		}
	}
};

// A failed SDK recording can be discarded before it becomes part of the frame graph.
class RecordedUpscale final : public RefCounted
{
public:
	Ref<NativeBackend> refBackend;
	VkDevice stDevice = VK_NULL_HANDLE;
	VkCommandPool stPool = VK_NULL_HANDLE;
	VkCommandBuffer stCommands = VK_NULL_HANDLE;

	bool BeginVulkan()
	{
		RD *pDevice = RD::get_singleton();
		stDevice = (VkDevice)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_LOGICAL_DEVICE);
		VkCommandPoolCreateInfo stPoolInfo{ VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO };
		stPoolInfo.queueFamilyIndex = (uint32_t)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_QUEUE_FAMILY);
		stPoolInfo.flags = VK_COMMAND_POOL_CREATE_TRANSIENT_BIT;
		if (vkCreateCommandPool(stDevice, &stPoolInfo, nullptr, &stPool) != VK_SUCCESS)
		{
			return false;
		}
		VkCommandBufferAllocateInfo stAllocate{ VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO };
		stAllocate.commandPool = stPool;
		stAllocate.level = VK_COMMAND_BUFFER_LEVEL_SECONDARY;
		stAllocate.commandBufferCount = 1;
		if (vkAllocateCommandBuffers(stDevice, &stAllocate, &stCommands) != VK_SUCCESS)
		{
			return false;
		}
		VkCommandBufferInheritanceInfo stInheritance{ VK_STRUCTURE_TYPE_COMMAND_BUFFER_INHERITANCE_INFO };
		VkCommandBufferBeginInfo stBegin{ VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
		stBegin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
		stBegin.pInheritanceInfo = &stInheritance;
		if (vkBeginCommandBuffer(stCommands, &stBegin) != VK_SUCCESS)
		{
			return false;
		}
		return true;
	}

#ifdef D3D12_ENABLED
	Microsoft::WRL::ComPtr<ID3D12CommandAllocator> pAllocator;
	Microsoft::WRL::ComPtr<ID3D12GraphicsCommandList> pCommands;
	Microsoft::WRL::ComPtr<ID3D12GraphicsCommandList> pContinuation;
	RDD::TextureID arrTextures[5];

	bool BeginDirectX()
	{
		ID3D12Device *pDevice = (ID3D12Device *)RD::get_singleton()->get_driver_resource(RD::DRIVER_RESOURCE_LOGICAL_DEVICE);
		if (FAILED(pDevice->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(pAllocator.GetAddressOf()))))
		{
			return false;
		}
		return SUCCEEDED(pDevice->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, pAllocator.Get(), nullptr, IID_PPV_ARGS(pCommands.GetAddressOf())));
	}
#endif

	bool Submit(const Frame &stFrame, Size2i vOutput, bool bReset)
	{
		RD *pDevice = RD::get_singleton();
		NativeCommands stNative;
#ifdef D3D12_ENABLED
		if (IsDirectX())
		{
			if (!BeginDirectX())
			{
				return false;
			}
			stNative.pDirectX = pCommands.Get();
		}
		else
#endif
		{
			if (!BeginVulkan())
			{
				return false;
			}
			stNative.stVulkan = stCommands;
		}
		Images stImages = { NativeImage::FromRid(stFrame.color, stFrame.internal_size),
			NativeImage::FromRid(stFrame.depth, stFrame.internal_size), NativeImage::FromRid(stFrame.velocity, stFrame.internal_size),
			NativeImage::FromRid(stFrame.reactive, stFrame.internal_size), NativeImage::FromRid(stFrame.output, vOutput) };
		if (!refBackend->Record(stNative, stFrame, stImages, bReset))
		{
			return false;
		}
#ifdef D3D12_ENABLED
		if (IsDirectX())
		{
			ID3D12Device *pDxDevice = (ID3D12Device *)pDevice->get_driver_resource(RD::DRIVER_RESOURCE_LOGICAL_DEVICE);
			if (FAILED(pCommands->Close()) || FAILED(pDxDevice->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT,
					pAllocator.Get(), nullptr, IID_PPV_ARGS(pContinuation.GetAddressOf()))))
			{
				return false;
			}
			arrTextures[0] = pDevice->GetCallbackTexture(stFrame.color);
			arrTextures[1] = pDevice->GetCallbackTexture(stFrame.depth);
			arrTextures[2] = pDevice->GetCallbackTexture(stFrame.velocity);
			arrTextures[3] = pDevice->GetCallbackTexture(stFrame.reactive);
			arrTextures[4] = pDevice->GetCallbackTexture(stFrame.output);
		}
		else
#endif
		if (vkEndCommandBuffer(stCommands) != VK_SUCCESS)
		{
			return false;
		}
		RD::CallbackResource arrResources[] = {
			{ stFrame.color, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE },
			{ stFrame.depth, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE },
			{ stFrame.velocity, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE },
			{ stFrame.reactive, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE },
			{ stFrame.output, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_STORAGE_IMAGE_READ_WRITE },
		};
		if (pDevice->driver_callback_add(Execute, this, VectorView<RD::CallbackResource>(arrResources, std::size(arrResources))) != OK)
		{
			return false;
		}
		pDevice->RetainForGpuFrame(Ref<RecordedUpscale>(this));
		return true;
	}

	static void Execute(RDD *pDriver, RDD::CommandBufferID stPrimary, void *pUser)
	{
		RecordedUpscale *pFrame = static_cast<RecordedUpscale *>(pUser);
#ifdef D3D12_ENABLED
		if (pFrame->pCommands)
		{
			static_cast<RenderingDeviceDriverD3D12 *>(pDriver)->AppendUpscalingCommands(stPrimary, pFrame->pCommands.Get(),
					pFrame->pContinuation.Get(), VectorView<RDD::TextureID>(pFrame->arrTextures, std::size(pFrame->arrTextures)));
			return;
		}
#endif
		static_cast<RenderingDeviceDriverVulkan *>(pDriver)->ExecuteSecondary(stPrimary, pFrame->stCommands);
	}

	~RecordedUpscale() override
	{
		if (stPool)
		{
			vkDestroyCommandPool(stDevice, stPool, nullptr);
		}
	}
};
}
#endif

#ifdef TEMPORAL_SDK_VULKAN
Vector<CharString> GetUpscalerExtensions(VkInstance stInstance, VkPhysicalDevice stPhysicalDevice)
{
	Vector<CharString> arrExtensions;
	Char16String strRoot = OS::get_singleton()->get_executable_path().get_base_dir().utf16();
	const wchar_t *pRoot = (const wchar_t *)strRoot.get_data();
	NVSDK_NGX_FeatureCommonInfo stCommon = {};
	stCommon.PathListInfo = { &pRoot, 1 };
	NVSDK_NGX_FeatureDiscoveryInfo stInfo = {};
	stInfo.SDKVersion = NVSDK_NGX_Version_API;
	stInfo.FeatureID = NVSDK_NGX_Feature_SuperSampling;
	stInfo.Identifier.IdentifierType = NVSDK_NGX_Application_Identifier_Type_Project_Id;
	stInfo.Identifier.v.ProjectDesc = { "646bdd3d-5875-4fe1-8a27-79f87141ae0c", NVSDK_NGX_ENGINE_TYPE_CUSTOM, "Godot 4.8" };
	Char16String strData = OS::get_singleton()->get_user_data_dir().utf16();
	stInfo.ApplicationDataPath = (const wchar_t *)strData.get_data();
	stInfo.FeatureInfo = &stCommon;
	uint32_t nCount = 0;
	VkExtensionProperties *pProperties = nullptr;
	NVSDK_NGX_Result eResult;
	if (stPhysicalDevice)
	{
		eResult = NVSDK_NGX_VULKAN_GetFeatureDeviceExtensionRequirements(stInstance, stPhysicalDevice, &stInfo, &nCount, &pProperties);
	}
	else
	{
		eResult = NVSDK_NGX_VULKAN_GetFeatureInstanceExtensionRequirements(&stInfo, &nCount, &pProperties);
	}
	if (!NVSDK_NGX_FAILED(eResult))
	{
		for (uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
		{
			arrExtensions.push_back(CharString(pProperties[nIndex].extensionName));
		}
	}
	return arrExtensions;
}
#endif

void RendererRD::TemporalUpscaler::Reset()
{
	refBackend.unref();
	bTriedDlss = false;
	bTriedFsr = false;
	bReportedFallback = false;
	bHasHistory = false;
}

bool RendererRD::TemporalUpscaler::Dispatch(const Ref<RenderSceneBuffersRD> &refBuffers, const FSR2Effect::Parameters &stFrame,
		const Transform3D &stCamera, uint32_t nView)
{
#ifdef TEMPORAL_SDK_VULKAN
	if ((OS::get_singleton()->get_current_rendering_driver_name() == "vulkan" || IsDirectX()) && refBuffers->get_view_count() == 1 && nView == 0)
	{
		const RSE::ViewportScaling3DMode eMode = refBuffers->get_scaling_3d_mode();
		bool bAllowDlss = eMode != RSE::VIEWPORT_SCALING_3D_MODE_AMD_FSR && RD::get_singleton()->get_device_vendor_name() == "NVIDIA";
		bool bAllowFsr = eMode != RSE::VIEWPORT_SCALING_3D_MODE_DLSS_SR;
		while (true)
		{
			if (refBackend.is_null() && !bTriedDlss && bAllowDlss)
			{
				bTriedDlss = true;
				Ref<DlssBackend> refDlss;
				refDlss.instantiate();
				if (refDlss->Initialize())
				{
					refBackend = refDlss;
				}
			}
			if (refBackend.is_null() && !bTriedFsr && bAllowFsr)
			{
				bTriedFsr = true;
				Ref<AmdBackend> refFsr;
				refFsr.instantiate();
				if (refFsr->Initialize(stFrame.internal_size, refBuffers->get_target_size()))
				{
					if (bTriedDlss)
					{
						refBuffers->strUpscalerFallback = "DLSS SR unavailable. Auto selected AMD FSR.";
					}
					refBackend = refFsr;
				}
			}
			if (refBackend.is_null())
			{
				break;
			}
			Ref<RecordedUpscale> refCommands;
			refCommands.instantiate();
			refCommands->refBackend = Ref<NativeBackend>(static_cast<NativeBackend *>(refBackend.ptr()));
			bool bReset = !bHasHistory || stFrame.reset_accumulation || stCamera.origin.distance_squared_to(stLastCamera.origin) > 100.0f ||
					stCamera.basis.get_column(2).dot(stLastCamera.basis.get_column(2)) < 0.5f;
			if (refCommands->Submit(stFrame, refBuffers->get_target_size(), bReset))
			{
				if (!bHasHistory)
				{
					refBuffers->strUpscalerImplementation = refCommands->refBackend->strName;
					print_line(vformat("Temporal upscaling: %s, %s, %s -> %s", refCommands->refBackend->strName, OS::get_singleton()->get_current_rendering_driver_name(), stFrame.internal_size, refBuffers->get_target_size()));
				}
				bHasHistory = true;
				stLastCamera = stCamera;
				return true;
			}
			WARN_PRINT(vformat("%s did not record this frame. Selecting fallback.", refCommands->refBackend->strName));
			refBackend.unref();
			bHasHistory = false;
		}
	}
#endif
	if (!bReportedFallback)
	{
		refBuffers->strUpscalerImplementation = "FSR 2.2";
		refBuffers->strUpscalerFallback = "Requested SDK unavailable or dispatch failed for this device, view count or backend.";
		print_line("Temporal upscaling: built-in FSR 2.2 fallback (requested SDK unavailable for this viewport).");
		bReportedFallback = true;
	}
	return false;
}
