/**************************************************************************/
/*  RuntimeVirtualTextureRD.cpp                                          */
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

#include "RuntimeVirtualTextureRD.h"

#include "core/object/callable_mp.h"

#pragma region Engine ZXB
// [ZXB] Implementation of the Runtime Virtual Texture RD backend.
#pragma endregion

#include "servers/rendering/renderer_rd/storage_rd/render_scene_buffers_rd.h"
#include "servers/rendering/renderer_rd/storage_rd/material_storage.h"
#include "servers/rendering/rendering_server_globals.h"
#include "servers/rendering/rendering_method.h"
#include "servers/rendering/renderer_rd/storage_rd/texture_storage.h"

#include "servers/rendering/renderer_rd/uniform_set_cache_rd.h"

namespace RendererRD
{

RuntimeVirtualTextureRD::RuntimeVirtualTextureRD(RendererSceneRender *in_pSceneRender)
{
	stHeightShader.initialize({ String() });
	ridHeightVersion = stHeightShader.version_create();
	ridHeightPipeline = RD::get_singleton()->compute_pipeline_create(stHeightShader.version_get_shader(ridHeightVersion, 0));
	pSceneRender = in_pSceneRender;

	Vector<String> arrModes;
	arrModes.push_back("\n#define MODE_BASE_COLOR\n");
	arrModes.push_back("\n#define MODE_BASE_COLOR_NORMAL_ROUGHNESS\n");
	arrModes.push_back("\n#define MODE_WORLD_HEIGHT\n");
	arrModes.push_back("\n#define MODE_TERRAIN_PBR\n");
	stComposeShader.initialize(arrModes);
	ridComposeVersion = stComposeShader.version_create();
	for (int nI = 0; nI < RSE::RVT_MATERIAL_MAX; nI++)
	{
		arrComposePipelines[nI] = RD::get_singleton()->compute_pipeline_create(stComposeShader.version_get_shader(ridComposeVersion, nI));
	}

	ridNearestSampler = RD::get_singleton()->sampler_create(RD::SamplerState());
}

RuntimeVirtualTextureRD::~RuntimeVirtualTextureRD()
{
	LocalVector<RID> arrRemaining;
	arrRemaining.resize(stOwner.get_rid_count());
	stOwner.fill_owned_buffer(arrRemaining.ptr());
	for (const RID &ridResource : arrRemaining)
	{
		Free(ridResource);
	}
	if (ridFeedbackVersion.is_valid())
	{
		stFeedbackShader.version_free(ridFeedbackVersion);
		RD::get_singleton()->free_rid(ridFeedbackBuffer);
	}
	stHeightShader.version_free(ridHeightVersion);
	stComposeShader.version_free(ridComposeVersion);
	RD::get_singleton()->free_rid(ridNearestSampler);
}

void RuntimeVirtualTextureRD::PublishTexture(RID ridGodotTexture, RID ridRdTexture)
{
	if (ridGodotTexture.is_null())
	{
		return;
	}
	TextureStorage *pTextureStorage = TextureStorage::get_singleton();
	const RID ridTmp = pTextureStorage->texture_allocate();
	pTextureStorage->texture_rd_initialize(ridTmp, ridRdTexture, RSE::TEXTURE_LAYERED_2D_ARRAY);
	pTextureStorage->texture_replace(ridGodotTexture, ridTmp);
}

RID RuntimeVirtualTextureRD::Create(const Config &in_stConfig, RID ridPageTableTexture, RID ridPhysicalTexture0, RID ridPhysicalTexture1)
{
	RD *pRd = RD::get_singleton();
	GPU stGpu;
	stGpu.stConfig = in_stConfig;
	stGpu.nStride = in_stConfig.nTileSize + 2 * in_stConfig.nTileBorder;
	stGpu.bStreaming = in_stConfig.bStreaming;
	const bool bTerrainPbr = in_stConfig.stType == RSE::RVT_MATERIAL_TERRAIN_PBR;
	const bool bHasNormal = bTerrainPbr || in_stConfig.stType == RSE::RVT_MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS;
	stGpu.nLayerCount = !in_stConfig.bStreaming && bHasNormal ? 2 : 1;

	bool bBlockCompressed = false;
	if (in_stConfig.bStreaming)
	{
		switch (in_stConfig.nFormat)
		{
		// Streaming pools store sRGB encoded bytes in UNORM views: the shader include decodes
		// them explicitly, the same contract the rendered RVT pool uses. Binding an sRGB view
		// here would decode twice.
		case 1: // BC1 (RGB, no alpha; TextureStorage only maps the RGB variants)
			stGpu.ePoolFormat = RD::DATA_FORMAT_BC1_RGB_UNORM_BLOCK;
			bBlockCompressed = true;
			break;
		case 2: // BC7
			stGpu.ePoolFormat = RD::DATA_FORMAT_BC7_UNORM_BLOCK;
			bBlockCompressed = true;
			break;
		case 3: // R32F
			stGpu.ePoolFormat = RD::DATA_FORMAT_R32_SFLOAT;
			break;
		default:
			stGpu.ePoolFormat = RD::DATA_FORMAT_R8G8B8A8_UNORM;
			break;
		}
	}
	else
	{
		stGpu.ePoolFormat = in_stConfig.stType == RSE::RVT_MATERIAL_WORLD_HEIGHT ? RD::DATA_FORMAT_R32_SFLOAT : RD::DATA_FORMAT_R8G8B8A8_UNORM;
	}

	// Physical page pool.
	RD::TextureFormat eTf;
	eTf.width = stGpu.nStride * in_stConfig.nPoolTilesX;
	eTf.height = stGpu.nStride * in_stConfig.nPoolTilesY;
	eTf.format = stGpu.ePoolFormat;
	if (stGpu.bStreaming)
	{
		eTf.usage_bits = RD::TEXTURE_USAGE_SAMPLING_BIT | RD::TEXTURE_USAGE_CAN_COPY_TO_BIT;
	}
	else
	{
		eTf.usage_bits = RD::TEXTURE_USAGE_STORAGE_BIT | RD::TEXTURE_USAGE_SAMPLING_BIT | RD::TEXTURE_USAGE_CAN_COPY_FROM_BIT | RD::TEXTURE_USAGE_CAN_COPY_TO_BIT;
	}
	for (uint32_t nI = 0; nI < stGpu.nLayerCount; nI++)
	{
		if (bTerrainPbr && nI == 1)
		{
			eTf.format = RD::DATA_FORMAT_R16G16B16A16_UNORM;
		}
		stGpu.arrPhysical[nI] = pRd->texture_create(eTf, RD::TextureView());
		pRd->set_resource_name(stGpu.arrPhysical[nI], "RVT Physical Texture");
		if (!bBlockCompressed)
		{
			pRd->texture_clear(stGpu.arrPhysical[nI], Color(0, 0, 0, 0), 0, 1, 0, 1);
		}
	}

	// Page table with one mip per virtual texture level.
	const uint32_t nLevels = in_stConfig.nLog2TileCount + 1;
	RD::TextureFormat ePtf;
	ePtf.width = 1u << in_stConfig.nLog2TileCount;
	ePtf.height = ePtf.width;
	ePtf.mipmaps = nLevels;
	ePtf.format = RD::DATA_FORMAT_R8G8B8A8_UNORM;
	ePtf.usage_bits = RD::TEXTURE_USAGE_SAMPLING_BIT | RD::TEXTURE_USAGE_CAN_UPDATE_BIT | RD::TEXTURE_USAGE_CAN_COPY_FROM_BIT;
	stGpu.ridPageTable = pRd->texture_create(ePtf, RD::TextureView());
	pRd->set_resource_name(stGpu.ridPageTable, "RVT Page Table");
	{
		uint32_t nTotal = 0;
		for (uint32_t nL = 0; nL < nLevels; nL++)
		{
			const uint32_t nS = ePtf.width >> nL;
			nTotal += nS * nS * 4;
		}
		Vector<uint8_t> arrZeros;
		arrZeros.resize_initialized(nTotal);
		pRd->texture_update(stGpu.ridPageTable, 0, arrZeros);
	}

	if (stGpu.bStreaming || in_stConfig.bHeightGrid || bTerrainPbr)
	{
		// Tile sized staging texture: texture_update() then a region texture_copy() into the pool.
		RD::TextureFormat eStg;
		eStg.width = stGpu.nStride;
		eStg.height = stGpu.nStride;
		eStg.format = stGpu.ePoolFormat;
		eStg.usage_bits = RD::TEXTURE_USAGE_CAN_UPDATE_BIT | RD::TEXTURE_USAGE_CAN_COPY_FROM_BIT;
		stGpu.ridStaging = pRd->texture_create(eStg, RD::TextureView());
		pRd->set_resource_name(stGpu.ridStaging, "RVT Streaming Staging");
		if (bTerrainPbr)
		{
			eStg.format = RD::DATA_FORMAT_R16G16B16A16_UNORM;
			stGpu.ridSurfaceStaging = pRd->texture_create(eStg, RD::TextureView());
		}
	}
	if (!stGpu.bStreaming && !in_stConfig.bHeightGrid)
	{
		// Scratch targets of the material pass. Same layout as the VoxelGI dynamic object pass.
		RD::TextureFormat eStf;
		eStf.width = stGpu.nStride;
		eStf.height = stGpu.nStride;
		eStf.format = RD::DATA_FORMAT_R8G8B8A8_SRGB;
		eStf.usage_bits = RD::TEXTURE_USAGE_COLOR_ATTACHMENT_BIT | RD::TEXTURE_USAGE_SAMPLING_BIT;
		stGpu.ridAlbedo = pRd->texture_create(eStf, RD::TextureView());
		eStf.format = RD::DATA_FORMAT_R8G8B8A8_UNORM;
		stGpu.ridNormal = pRd->texture_create(eStf, RD::TextureView());
		stGpu.ridOrm = pRd->texture_create(eStf, RD::TextureView());
		eStf.format = RD::DATA_FORMAT_R16G16B16A16_SFLOAT;
		eStf.usage_bits = RD::TEXTURE_USAGE_COLOR_ATTACHMENT_BIT | (bTerrainPbr ? uint32_t(RD::TEXTURE_USAGE_SAMPLING_BIT) : 0u);
		stGpu.ridEmission = pRd->texture_create(eStf, RD::TextureView());
		eStf.format = RD::DATA_FORMAT_R32_SFLOAT;
		eStf.usage_bits = RD::TEXTURE_USAGE_COLOR_ATTACHMENT_BIT | RD::TEXTURE_USAGE_SAMPLING_BIT;
		stGpu.ridDepth = pRd->texture_create(eStf, RD::TextureView());
		eStf.format = pRd->texture_is_format_supported_for_usage(RD::DATA_FORMAT_D16_UNORM, RD::TEXTURE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT) ? RD::DATA_FORMAT_D16_UNORM : RD::DATA_FORMAT_X8_D24_UNORM_PACK32;
		eStf.usage_bits = RD::TEXTURE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT;
		stGpu.ridDepthStencil = pRd->texture_create(eStf, RD::TextureView());

		Vector<RID> arrFb;
		arrFb.push_back(stGpu.ridAlbedo);
		arrFb.push_back(stGpu.ridNormal);
		arrFb.push_back(stGpu.ridOrm);
		arrFb.push_back(stGpu.ridEmission);
		arrFb.push_back(stGpu.ridDepth);
		arrFb.push_back(stGpu.ridDepthStencil);
		stGpu.ridFramebuffer = pRd->framebuffer_create(arrFb);

		// Compose pass uniform sets. Only bindings used by the selected mode are bound.
		const RID ridShader = stComposeShader.version_get_shader(ridComposeVersion, in_stConfig.stType);
		{
			Vector<RD::Uniform> arrUniforms;
			const RID arrSources[5] = { stGpu.ridAlbedo, stGpu.ridNormal, stGpu.ridOrm, stGpu.ridDepth, stGpu.ridEmission };
			const bool arrUsed[5] = {
				true,
				bHasNormal,
				bHasNormal,
				in_stConfig.stType == RSE::RVT_MATERIAL_WORLD_HEIGHT,
				bTerrainPbr,
			};
			for (int nI = 0; nI < 5; nI++)
			{
				if (!arrUsed[nI])
				{
					continue;
				}
				RD::Uniform stU;
				stU.uniform_type = RD::UNIFORM_TYPE_SAMPLER_WITH_TEXTURE;
				stU.binding = nI;
				stU.append_id(ridNearestSampler);
				stU.append_id(arrSources[nI]);
				arrUniforms.push_back(stU);
			}
			stGpu.ridComposeInputs = pRd->uniform_set_create(arrUniforms, ridShader, 0);
		}
		{
			Vector<RD::Uniform> arrUniforms;
			for (uint32_t nI = 0; nI < stGpu.nLayerCount; nI++)
			{
				RD::Uniform stU;
				stU.uniform_type = RD::UNIFORM_TYPE_IMAGE;
				stU.binding = nI;
				stU.append_id(stGpu.arrPhysical[nI]);
				arrUniforms.push_back(stU);
			}
			stGpu.ridComposeOutputs = pRd->uniform_set_create(arrUniforms, ridShader, 1);
		}
	}

	// Expose the textures through the placeholder texture RIDs handed out by the server.
	PublishTexture(ridPageTableTexture, stGpu.ridPageTable);
	PublishTexture(ridPhysicalTexture0, stGpu.arrPhysical[0]);
	if (stGpu.nLayerCount > 1)
	{
		PublishTexture(ridPhysicalTexture1, stGpu.arrPhysical[1]);
	}

	return stOwner.make_rid(stGpu);
}

void RuntimeVirtualTextureRD::FreeGpu(GPU *in_pGpu)
{
	RD *pRd = RD::get_singleton();
	if (in_pGpu->ridRegionBuffer.is_valid())
	{
		pRd->free_rid(in_pGpu->ridRegionBuffer);
	}
	const RID arrRids[] = { in_pGpu->ridFeedbackFilter, in_pGpu->ridComposeInputs, in_pGpu->ridComposeOutputs, in_pGpu->ridFramebuffer, in_pGpu->ridAlbedo, in_pGpu->ridNormal, in_pGpu->ridOrm, in_pGpu->ridEmission, in_pGpu->ridDepth, in_pGpu->ridDepthStencil, in_pGpu->ridStaging, in_pGpu->ridSurfaceStaging, in_pGpu->ridPageTable, in_pGpu->arrPhysical[0], in_pGpu->arrPhysical[1] };
	for (const RID &ridResource : arrRids)
	{
		if (ridResource.is_valid())
		{
			pRd->free_rid(ridResource);
		}
	}
}

void RuntimeVirtualTextureRD::Free(RID ridGpu)
{
	GPU *pGpu = stOwner.get_or_null(ridGpu);
	ERR_FAIL_NULL(pGpu);
	FreeGpu(pGpu);
	stOwner.free(ridGpu);
}

void RuntimeVirtualTextureRD::UpdatePageTable(RID ridGpu, const LocalVector<Vector<uint8_t>> &arrLevels)
{
	GPU *pGpu = stOwner.get_or_null(ridGpu);
	ERR_FAIL_NULL(pGpu);
	Vector<uint8_t> arrData;
	for (const Vector<uint8_t> &arrLevel : arrLevels)
	{
		arrData.append_array(arrLevel);
	}
	RD::get_singleton()->texture_update(pGpu->ridPageTable, 0, arrData);
}

void RuntimeVirtualTextureRD::RenderPage(RID ridGpu, const Transform3D &xformCamera, const Projection &projProjection, const PagedArray<RenderGeometryInstance *> &arrInstances, uint32_t nPoolX, uint32_t nPoolY, float fVolumeHeight)
{
	GPU *pGpu = stOwner.get_or_null(ridGpu);
	ERR_FAIL_NULL(pGpu);
	RD *pRd = RD::get_singleton();

	pSceneRender->render_material(xformCamera, projProjection, true, arrInstances, pGpu->ridFramebuffer, Rect2i(0, 0, pGpu->nStride, pGpu->nStride));

	ComposePushConstant stPc = {};
	stPc.arrDstOffset[0] = nPoolX * pGpu->nStride;
	stPc.arrDstOffset[1] = nPoolY * pGpu->nStride;
	stPc.arrSize[0] = pGpu->nStride;
	stPc.arrSize[1] = pGpu->nStride;
	stPc.fHeightScale = 1.0f / MAX(fVolumeHeight, 0.0001f);
	stPc.nFlipY = 1; // Material pass output is vertically flipped relative to the camera up vector.

	RD::ComputeListID nCl = pRd->compute_list_begin();
	pRd->compute_list_bind_compute_pipeline(nCl, arrComposePipelines[pGpu->stConfig.stType]);
	pRd->compute_list_bind_uniform_set(nCl, pGpu->ridComposeInputs, 0);
	pRd->compute_list_bind_uniform_set(nCl, pGpu->ridComposeOutputs, 1);
	pRd->compute_list_set_push_constant(nCl, &stPc, sizeof(stPc));
	pRd->compute_list_dispatch_threads(nCl, pGpu->nStride, pGpu->nStride, 1);
	pRd->compute_list_end();
}

void RuntimeVirtualTextureRD::CollectFeedback(RID ridSurface, RID ridViewport, const Transform3D &xformVolume, uint32_t nLog2Tiles, uint32_t in_nTileSize, int nMaxAnisotropy, float in_fLodBias, const Vector4 &vLimits, uint64_t in_nRevision, RID ridGpu, const Ref<RenderSceneBuffers> &in_refBuffers, const RendererSceneRender::CameraData &stCamera)
{
	Ref<RenderSceneBuffersRD> refBuffers = in_refBuffers;
	if (refBuffers.is_null() || Math::is_zero_approx(xformVolume.basis.determinant()))
	{
		return;
	}
	const Size2i vSize = refBuffers->get_internal_size();
	const unsigned int nViews = MIN(refBuffers->get_view_count(), stCamera.view_count);
	if (MIN(vSize.x, vSize.y) < 2 || !nViews)
	{
		return;
	}
	RD *pRd = RD::get_singleton();
	if (ridFeedbackVersion.is_null())
	{
		stFeedbackShader.initialize({ String(), "\n#define DEPTH_MSAA\n", "\n#define WORLD_LIMITS\n", "\n#define DEPTH_MSAA\n#define WORLD_LIMITS\n" });
		ridFeedbackVersion = stFeedbackShader.version_create();
		for (uint32_t nI = 0; nI < std_size(arrFeedbackPipelines); nI++)
		{
			arrFeedbackPipelines[nI] = pRd->compute_pipeline_create(stFeedbackShader.version_get_shader(ridFeedbackVersion, nI));
		}
	}
	const int nStep = MAX(4, MAX(Math::division_round_up(vSize.x, 128), Math::division_round_up(vSize.y, 96)));
	const Size2i vGrid(Math::division_round_up(vSize.x, nStep), Math::division_round_up(vSize.y, nStep));
	const uint32_t nBytes = vGrid.x * vGrid.y * nViews * sizeof(uint32_t);
	if (nBytes > nFeedbackCapacity)
	{
		if (ridFeedbackBuffer.is_valid())
		{
			pRd->free_rid(ridFeedbackBuffer);
		}
		ridFeedbackBuffer = pRd->storage_buffer_create(nBytes);
		nFeedbackCapacity = nBytes;
	}
	const bool bMsaa = refBuffers->get_msaa_3d() != RSE::VIEWPORT_MSAA_DISABLED;
	Projection projCorrection;
	projCorrection.set_depth_correction(true);
	projCorrection.add_jitter_offset(stCamera.taa_jitter);
	const Transform3D xformViewInVolume = xformVolume.affine_inverse() * stCamera.main_transform;
	const Projection projCameraToVolume(xformViewInVolume);
	const bool bLimited = vLimits != Vector4();
	const uint32_t nVariant = uint32_t(bMsaa) + (bLimited ? 2 : 0);
	RID ridFilter;
	if (bLimited)
	{
		GPU *pGpu = stOwner.get_or_null(ridGpu);
		ERR_FAIL_NULL(pGpu);
		if (pGpu->ridFeedbackFilter.is_null() || pGpu->basisFeedbackFilterBasis != xformVolume.basis || pGpu->vFeedbackFilterLimits != vLimits)
		{
			// These values stay constant as a clipmap scrolls and can be shared by all
			// cameras. Immutable UBOs also avoid overwriting an earlier queued dispatch.
			struct Filter
			{
				float arrAxes[3][4];
				float arrLimits[4];
			} stParameters = {};
			for (int nI = 0; nI < 3; ++nI)
			{
				const Vector3 vAxis = xformVolume.basis.get_column(nI);
				for (int nC = 0; nC < 3; ++nC)
				{
					stParameters.arrAxes[nI][nC] = vAxis[nC];
				}
			}
			for (int nI = 0; nI < 4; ++nI)
			{
				stParameters.arrLimits[nI] = vLimits[nI];
			}
			const RID ridReplacement = pRd->uniform_buffer_create(sizeof(stParameters), Span<uint8_t>(reinterpret_cast<const uint8_t *>(&stParameters), sizeof(stParameters)));
			ERR_FAIL_COND(ridReplacement.is_null());
			if (pGpu->ridFeedbackFilter.is_valid())
			{
				pRd->free_rid(pGpu->ridFeedbackFilter);
			}
			pGpu->ridFeedbackFilter = ridReplacement;
			pGpu->basisFeedbackFilterBasis = xformVolume.basis;
			pGpu->vFeedbackFilterLimits = vLimits;
		}
		ridFilter = pGpu->ridFeedbackFilter;
	}
	for (uint32_t nV = 0; nV < nViews; ++nV)
	{
		const RID ridDepth = bMsaa ? refBuffers->get_depth_msaa(nV) : refBuffers->get_depth_texture(nV);
		if (ridDepth.is_null())
		{
			return;
		}
		RD::Uniform stInput(RD::UNIFORM_TYPE_SAMPLER_WITH_TEXTURE, 0, ridNearestSampler);
		stInput.append_id(ridDepth);
		const RID ridShader = stFeedbackShader.version_get_shader(ridFeedbackVersion, nVariant);
		const RD::Uniform stOutput(RD::UNIFORM_TYPE_STORAGE_BUFFER, 1, ridFeedbackBuffer);
		UniformSetCacheRD *pCache = UniformSetCacheRD::get_singleton();
		const RID ridSet = bLimited ? pCache->get_cache(ridShader, 0, stInput, stOutput, RD::Uniform(RD::UNIFORM_TYPE_UNIFORM_BUFFER, 2, ridFilter)) : pCache->get_cache(ridShader, 0, stInput, stOutput);
		ERR_FAIL_COND(ridSet.is_null());
		struct Push
		{
			float arrTransform[16];
			int32_t nWidth, stHeight, stGridWidth, stGridHeight, stStep, stOffset, stLevels, stTileSize, stAnisotropy;
			float fLodBias;
			int32_t arrPadding[2];
			float arrEyeInVolume[4];
		} stPc = {};
		static_assert(sizeof(Push) == 128);
		for (int nI = 0; nI < 3; ++nI)
		{
			stPc.arrEyeInVolume[nI] = xformViewInVolume.origin[nI];
		}
		MaterialStorage::store_camera(projCameraToVolume * (projCorrection * stCamera.view_projection[nV]).inverse(), stPc.arrTransform);
		stPc.nWidth = vSize.x;
		stPc.stHeight = vSize.y;
		stPc.stGridWidth = vGrid.x;
		stPc.stGridHeight = vGrid.y;
		stPc.stStep = nStep;
		stPc.stOffset = nV * vGrid.x * vGrid.y;
		stPc.stLevels = nLog2Tiles;
		stPc.stTileSize = in_nTileSize;
		stPc.stAnisotropy = nMaxAnisotropy;
		stPc.fLodBias = in_fLodBias;
		const RD::ComputeListID nList = pRd->compute_list_begin();
		pRd->compute_list_bind_compute_pipeline(nList, arrFeedbackPipelines[nVariant]);
		pRd->compute_list_bind_uniform_set(nList, ridSet, 0);
		pRd->compute_list_set_push_constant(nList, &stPc, sizeof(stPc));
		pRd->compute_list_dispatch_threads(nList, vGrid.x, vGrid.y, 1);
		pRd->compute_list_end();
	}
	pRd->buffer_get_data_async(ridFeedbackBuffer, callable_mp_static(&RuntimeVirtualTextureRD::DeliverFeedback).bind(ridSurface, ridViewport, in_nRevision), 0, nBytes);
}

void RuntimeVirtualTextureRD::DeliverFeedback(const Vector<uint8_t> &in_arrData, RID ridSurface, RID ridViewport, uint64_t nRevision)
{
	if (!RSG::scene || in_arrData.is_empty())
	{
		return;
	}
	const uint32_t *pValues = reinterpret_cast<const uint32_t *>(in_arrData.ptr());
	Vector<uint32_t> arrPages;
	arrPages.reserve(in_arrData.size() / sizeof(uint32_t));
	for (size_t nI = 0; nI < in_arrData.size() / sizeof(uint32_t); ++nI)
	{
		if (pValues[nI] != UINT32_MAX)
		{
			arrPages.push_back(pValues[nI]);
		}
	}
	RSG::scene->RuntimeVirtualTextureSubmitGpuFeedback(ridSurface, ridViewport, arrPages, nRevision);
}

bool RuntimeVirtualTextureRD::DrawHeight(RID ridGpu, const RendererSceneRender::HeightGrid &in_stSource, const Vector2i &vPage, uint32_t nLevel, const Vector2i &vSlot)
{
	GPU *pGpu = stOwner.get_or_null(ridGpu);
	ERR_FAIL_NULL_V(pGpu, false);
	RD *pRd = RD::get_singleton();
	if (!pGpu->stConfig.bHeightGrid || in_stSource.ridHeightArray.is_null() || in_stSource.arrRegionMap.is_empty())
	{
		return false;
	}
	RID ridHeights = TextureStorage::get_singleton()->texture_get_rd_texture(in_stSource.ridHeightArray);
	if (ridHeights.is_null())
	{
		return false;
	}
	if (in_stSource.nRevision != pGpu->nRegionRevision || pGpu->ridRegionBuffer.is_null())
	{
		if (pGpu->ridRegionBuffer.is_valid())
		{
			pRd->free_rid(pGpu->ridRegionBuffer);
		}
		Vector<uint8_t> arrBytes = in_stSource.arrRegionMap.to_byte_array();
		pGpu->ridRegionBuffer = pRd->storage_buffer_create(arrBytes.size(), arrBytes.span());
		pGpu->nRegionRevision = in_stSource.nRevision;
	}
	RD::Uniform stSource(RD::UNIFORM_TYPE_SAMPLER_WITH_TEXTURE, 0, ridNearestSampler);
	stSource.append_id(ridHeights);
	RID ridSet = UniformSetCacheRD::get_singleton()->get_cache(stHeightShader.version_get_shader(ridHeightVersion, 0), 0, stSource,
															   RD::Uniform(RD::UNIFORM_TYPE_STORAGE_BUFFER, 1, pGpu->ridRegionBuffer), RD::Uniform(RD::UNIFORM_TYPE_IMAGE, 2, pGpu->arrPhysical[0]));
	ERR_FAIL_COND_V(ridSet.is_null(), false);
	const int nTile = pGpu->stConfig.nTileSize;
	const int nStride = pGpu->nStride;
	const int32_t arrPc[] = { vPage.x * nTile, vPage.y * nTile, vSlot.x * nStride, vSlot.y * nStride, in_stSource.vOrigin.x, in_stSource.vOrigin.y,
							  nTile << (pGpu->stConfig.nLog2TileCount - nLevel), in_stSource.nExtent, in_stSource.nRegionSize, in_stSource.nMapWidth, int32_t(pGpu->stConfig.nTileBorder), nStride };
	RD::ComputeListID nList = pRd->compute_list_begin();
	pRd->compute_list_bind_compute_pipeline(nList, ridHeightPipeline);
	pRd->compute_list_bind_uniform_set(nList, ridSet, 0);
	pRd->compute_list_set_push_constant(nList, arrPc, sizeof(arrPc));
	pRd->compute_list_dispatch_threads(nList, nStride, nStride, 1);
	pRd->compute_list_end();
	return true;
}

Vector<uint8_t> RuntimeVirtualTextureRD::ReadMaterialTile(RID ridGpu)
{
	GPU *pGpu = stOwner.get_or_null(ridGpu);
	ERR_FAIL_NULL_V(pGpu, Vector<uint8_t>());
	ERR_FAIL_COND_V(pGpu->nLayerCount != 2 || pGpu->stConfig.nPoolTilesX != 1 || pGpu->stConfig.nPoolTilesY != 1, Vector<uint8_t>());
	RD *pRd = RD::get_singleton();
	Vector<uint8_t> arrData = pRd->texture_get_data(pGpu->arrPhysical[0], 0);
	const Vector<uint8_t> arrSurface = pRd->texture_get_data(pGpu->arrPhysical[1], 0);
	const int64_t nPixels = int64_t(pGpu->nStride) * pGpu->nStride;
	ERR_FAIL_COND_V(arrData.size() != nPixels * 4 || arrSurface.size() != nPixels * 8, Vector<uint8_t>());
	arrData.append_array(arrSurface);
	return arrData;
}

void RuntimeVirtualTextureRD::UploadPage(RID ridGpu, uint32_t nPoolX, uint32_t nPoolY, const Vector<uint8_t> &in_arrData)
{
	GPU *pGpu = stOwner.get_or_null(ridGpu);
	ERR_FAIL_NULL(pGpu);
	ERR_FAIL_COND(pGpu->ridStaging.is_null());
	RD *pRd = RD::get_singleton();

	if (pGpu->ridSurfaceStaging.is_valid())
	{
		const int64_t nPixels = int64_t(pGpu->nStride) * pGpu->nStride;
		ERR_FAIL_COND(in_arrData.size() != nPixels * 12);
		const Vector<uint8_t> arrColor = in_arrData.slice(0, nPixels * 4);
		const Vector<uint8_t> arrSurface = in_arrData.slice(nPixels * 4);
		ERR_FAIL_COND(pRd->texture_update(pGpu->ridStaging, 0, arrColor) != OK || pRd->texture_update(pGpu->ridSurfaceStaging, 0, arrSurface) != OK);
		pRd->texture_copy(pGpu->ridSurfaceStaging, pGpu->arrPhysical[1], Vector3(), Vector3(nPoolX * pGpu->nStride, nPoolY * pGpu->nStride, 0), Vector3(pGpu->nStride, pGpu->nStride, 1), 0, 0, 0, 0);
	}
	else if (pRd->texture_update(pGpu->ridStaging, 0, in_arrData) != OK)
	{
		return;
	}
	pRd->texture_copy(pGpu->ridStaging, pGpu->arrPhysical[0],
					  Vector3(0, 0, 0),
					  Vector3(nPoolX * pGpu->nStride, nPoolY * pGpu->nStride, 0),
					  Vector3(pGpu->nStride, pGpu->nStride, 1),
					  0, 0, 0, 0);
}

} // namespace RendererRD
