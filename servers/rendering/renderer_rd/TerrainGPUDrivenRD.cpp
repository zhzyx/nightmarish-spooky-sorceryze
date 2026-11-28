/**************************************************************************/
/*  TerrainGPUDrivenRD.cpp                                               */
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

#include "TerrainGPUDrivenRD.h"

#include "servers/rendering/renderer_rd/uniform_set_cache_rd.h"

#include "core/object/callable_mp.h"
#include "servers/rendering/renderer_geometry_instance.h"
#include "servers/rendering/renderer_rd/storage_rd/mesh_storage.h"
#include "servers/rendering/renderer_rd/storage_rd/texture_storage.h"
#include "servers/rendering/rendering_server_globals.h"

namespace RendererRD
{

TerrainGPUDrivenRD::TerrainGPUDrivenRD()
{
	Vector<String> arrModes{ String(), String("#define NATIVE_MULTIMESH\n") };
	stCullShader.initialize(arrModes);
	stFinalizeShader.initialize(arrModes);
	ridCullVersion = stCullShader.version_create();
	ridFinalizeVersion = stFinalizeShader.version_create();
	RD *pDevice = RD::get_singleton();
	for (int nMode = 0; nMode < 2; ++nMode)
	{
		arrCullPipelines[nMode] = pDevice->compute_pipeline_create(stCullShader.version_get_shader(ridCullVersion, nMode));
		arrFinalizePipelines[nMode] = pDevice->compute_pipeline_create(stFinalizeShader.version_get_shader(ridFinalizeVersion, nMode));
	}
	ridCullSampler = pDevice->sampler_create(RD::SamplerState());
}

TerrainGPUDrivenRD::~TerrainGPUDrivenRD()
{
	stCullShader.version_free(ridCullVersion);
	stFinalizeShader.version_free(ridFinalizeVersion);
	RD::get_singleton()->free_rid(ridCullSampler);
	for (KeyValue<RID, Work> &stEntry : mapWork)
	{
		Release(stEntry.value);
	}
}

void TerrainGPUDrivenRD::Release(Work &out_stWork)
{
	for (RID ridBuffer : { out_stWork.ridCompaction, out_stWork.ridFeedback, out_stWork.ridConfiguration })
	{
		if (ridBuffer.is_valid())
		{
			RD::get_singleton()->free_rid(ridBuffer);
		}
	}
}

void TerrainGPUDrivenRD::GatherBuffers(const PagedArray<RenderGeometryInstance *> &arrInstances, LocalVector<uint64_t> &out_arrBuffers) const
{
	out_arrBuffers.clear();
	const HashMap<RID, RenderingMethod::GPUTerrain> *pTerrains = RSG::scene->GpuDrivenTerrainGetMap();
	if (!pTerrains || pTerrains->is_empty())
	{
		return;
	}
	for (uint32_t nI = 0; nI < arrInstances.size(); nI++)
	{
		const RenderGeometryInstanceBase *pInstance = static_cast<const RenderGeometryInstanceBase *>(arrInstances[nI]);
		if (pInstance->data && pInstance->data->base_type == RSE::INSTANCE_MULTIMESH)
		{
			out_arrBuffers.push_back(MeshStorage::get_singleton()->multimesh_get_buffer_rd_rid(pInstance->data->base).get_id());
		}
	}
}

void TerrainGPUDrivenRD::BeginView(RID in_ridViewport, uint32_t nLayers, const Projection &projProjection,
								   const Transform3D &xformCamera, const PagedArray<RenderGeometryInstance *> *pInstances)
{
	ridViewport = in_ridViewport;
	nCameraLayers = nLayers;
	bShadowCut = false;
	projColorVp = projProjection * Projection(xformCamera.affine_inverse());
	vCameraPosition = xformCamera.origin;
	// Preserve the default 75-degree camera density, adjust coverage for a changed FOV.
	// The largest factor matches the candidate windows generated by Terrain3D.
	fProjectionScale = projProjection.is_orthogonal() ? 4.0f : CLAMP(float(MAX(Math::abs(projProjection[0][0]), Math::abs(projProjection[1][1]))) * 0.76732699f, 0.25f, 2.0f);
	nViewSerial++;
	const HashMap<RID, RenderingMethod::GPUTerrain> *pTerrains = RSG::scene->GpuDrivenTerrainGetMap();
	LocalVector<RID> arrStale;
	for (KeyValue<RID, Work> &stEntry : mapWork)
	{
		if (!pTerrains || !pTerrains->has(stEntry.key))
		{
			Release(stEntry.value);
			arrStale.push_back(stEntry.key);
		}
	}
	for (RID ridId : arrStale)
	{
		mapWork.erase(ridId);
	}
	arrMainBuffers.clear();
	if (pInstances && nCameraLayers)
	{
		GatherBuffers(*pInstances, arrMainBuffers);
		SelectPass(projColorVp, 1, arrMainBuffers, true);
	}
}

void TerrainGPUDrivenRD::SelectPass(const Projection &projVp, uint32_t nClipMode, const LocalVector<uint64_t> &arrBuffers, bool bColor)
{
	const HashMap<RID, RenderingMethod::GPUTerrain> *pTerrains = RSG::scene->GpuDrivenTerrainGetMap();
	if (!pTerrains || !nCameraLayers)
	{
		return;
	}
	for (const KeyValue<RID, RenderingMethod::GPUTerrain> &stEntry : *pTerrains)
	{
		const RenderingMethod::GPUTerrain &stT = stEntry.value;
		if (!stT.bEnabled || !(stT.nRenderLayers & nCameraLayers) || !stT.nCullNodeCount || !stT.nIndexCount ||
			!stT.nCullSrcNodesRd || !stT.nCullCompactNodesRd || !stT.nCullArgsRd)
		{
			continue;
		}
		if (stT.nCullShadowArgsRd)
		{
			if (!bColor || !stT.nCullCounterRd)
			{
				continue;
			}
		}
		else if (!arrBuffers.has(stT.nCullCompactNodesRd))
		{
			continue;
		}
		Dispatch(stEntry.key, stT, projVp, nClipMode);
	}
}

void TerrainGPUDrivenRD::SelectShadow(const Projection &projVp, bool bPancake, bool bDualParaboloid, const LocalVector<uint64_t> &arrBuffers)
{
	if (arrBuffers.is_empty() || !nCameraLayers)
	{
		return;
	}
	SelectPass(projVp, bDualParaboloid ? 0 : (bPancake ? 2 : 1), arrBuffers, false);
	bShadowCut = true;
}

void TerrainGPUDrivenRD::EndShadows()
{
	// The scene MultiMesh is shared by all passes of a view. Restore exactly the
	// same ordered color list that the depth prepass used before opaque rendering.
	if (bShadowCut)
	{
		SelectPass(projColorVp, 1, arrMainBuffers, true);
	}
	const HashMap<RID, RenderingMethod::GPUTerrain> *pTerrains = RSG::scene->GpuDrivenTerrainGetMap();
	if (!pTerrains)
	{
		return;
	}
	for (const KeyValue<RID, Work> &stEntry : mapWork)
	{
		const RenderingMethod::GPUTerrain *pTerrain = pTerrains->getptr(stEntry.key);
		if (stEntry.value.nViewSerial == nViewSerial && pTerrain && pTerrain->ridHeightVt.is_valid() && ridViewport.is_valid())
		{
			RD::get_singleton()->buffer_get_data_async(stEntry.value.ridFeedback, callable_mp_static(&TerrainGPUDrivenRD::SubmitFeedback).bind(pTerrain->ridHeightVt, ridViewport, pTerrain->nHeightLog2Pages));
		}
	}
}

void TerrainGPUDrivenRD::SubmitFeedback(const Vector<uint8_t> &arrData, RID in_ridHeightVt, RID in_ridViewport, int nLog2Tiles)
{
	if (!RSG::scene || arrData.is_empty())
	{
		return;
	}
	const uint32_t *pWords = reinterpret_cast<const uint32_t *>(arrData.ptr());
	Vector<uint32_t> arrRequests;
	uint32_t nStart = 0;
	// Only decode set bits. Feedback is immutable after the RD staging copy for this view.
	for (int nLevel = 0; nLevel <= nLog2Tiles; ++nLevel)
	{
		const uint32_t nSide = 1u << (nLog2Tiles - nLevel);
		const uint32_t nEnd = nStart + nSide * nSide;
		for (uint32_t nWi = nStart / 32; nWi <= (nEnd - 1) / 32; ++nWi)
		{
			uint32_t nMask = pWords[nWi];
			while (nMask)
			{
				const uint32_t nIndex = nWi * 32 + uint32_t(Math::get_shift_from_power_of_2(nMask & (0u - nMask)));
				nMask &= nMask - 1;
				if (nIndex >= nStart && nIndex < nEnd)
				{
					const uint32_t nLocal = nIndex - nStart;
					arrRequests.push_back((uint32_t(nLevel) << 24) | ((nLocal / nSide) << 12) | (nLocal % nSide));
				}
			}
		}
		nStart = nEnd;
	}
	RSG::scene->RuntimeVirtualTextureSubmitGpuFeedback(in_ridHeightVt, in_ridViewport, arrRequests);
}

void TerrainGPUDrivenRD::Dispatch(RID in_ridId, const RenderingMethod::GPUTerrain &stT, const Projection &projCullVp, uint32_t nClipMode)
{
	RD *pRd = RD::get_singleton();
	UniformSetCacheRD *pCache = UniformSetCacheRD::get_singleton();
	const bool bNative = stT.nCullShadowArgsRd == 0;
	const int nPipelineMode = bNative ? 1 : 0;
	const RID ridCull = stCullShader.version_get_shader(ridCullVersion, nPipelineMode);
	const RID ridFinalize = stFinalizeShader.version_get_shader(ridFinalizeVersion, nPipelineMode);
	const uint32_t nGroups = (stT.nCullNodeCount + 63) / 64;
	const uint32_t nBlocks = (nGroups + 255) / 256;
	RD::Uniform stNodes(RD::UNIFORM_TYPE_SAMPLER_WITH_TEXTURE, 1, ridCullSampler);
	stNodes.append_id(RID::from_uint64(stT.nCullSrcNodesRd));
	const RD::Uniform stOutput(bNative ? RD::UNIFORM_TYPE_STORAGE_BUFFER : RD::UNIFORM_TYPE_IMAGE, 0, RID::from_uint64(stT.nCullCompactNodesRd));
	const RD::Uniform stArgs(RD::UNIFORM_TYPE_STORAGE_BUFFER, 1, RID::from_uint64(stT.nCullArgsRd));
	RID ridCullSet;
	RID ridFinalizeSet;
	if (bNative)
	{
		Work &stW = mapWork[in_ridId];
		const uint32_t nBytes = (nGroups + nBlocks) * 16;
		if (stW.nCompactionBytes < nBytes)
		{
			if (stW.ridCompaction.is_valid())
			{
				pRd->free_rid(stW.ridCompaction);
			}
			stW.ridCompaction = pRd->storage_buffer_create(nBytes);
			stW.nCompactionBytes = nBytes;
		}
		const uint32_t nPages = stT.ridHeightVt.is_valid() ? ((4u << (2 * stT.nHeightLog2Pages)) - 1) / 3 : 1u;
		const uint32_t nFeedbackBytes = ((nPages + 31) / 32) * sizeof(uint32_t);
		if (stW.nFeedbackBytes != nFeedbackBytes)
		{
			if (stW.ridFeedback.is_valid())
			{
				pRd->free_rid(stW.ridFeedback);
			}
			stW.ridFeedback = pRd->storage_buffer_create(nFeedbackBytes);
			stW.nFeedbackBytes = nFeedbackBytes;
			stW.nViewSerial = 0;
		}
		RID ridBounds;
		if (stT.ridHeightBounds.is_valid())
		{
			ridBounds = TextureStorage::get_singleton()->texture_get_rd_texture(stT.ridHeightBounds);
		}
		if (stW.nViewSerial != nViewSerial)
		{
			struct
			{
				float arrDomain[4];
				float arrRange[4];
				uint32_t arrGrid[4];
			} stConfig = {
				{ float(stT.rectHeightDomain.position.x), float(stT.rectHeightDomain.position.y), float(stT.rectHeightDomain.size.x), float(stT.rectHeightDomain.size.y) },
				{ float(stT.vBackgroundHeights.x), float(stT.vBackgroundHeights.y), stT.fHeightMargin, ridBounds.is_valid() ? 1.f : 0.f },
				{ uint32_t(stT.nHeightLog2Pages), uint32_t(stT.nHeightTileSize), stT.ridHeightVt.is_valid() && stT.rectHeightDomain.has_area() ? 1u : 0u, 0u }
			};
			if (!stW.ridConfiguration.is_valid())
			{
				stW.ridConfiguration = pRd->uniform_buffer_create(sizeof(stConfig));
			}
			pRd->buffer_update(stW.ridConfiguration, 0, sizeof(stConfig), &stConfig);
			if (stT.ridHeightVt.is_valid())
			{
				pRd->buffer_clear(stW.ridFeedback, 0, nFeedbackBytes);
			}
			stW.nViewSerial = nViewSerial;
		}
		if (!ridBounds.is_valid())
		{
			ridBounds = TextureStorage::get_singleton()->texture_rd_get_default(TextureStorage::DEFAULT_RD_TEXTURE_BLACK);
		}
		RD::Uniform stHeightBounds(RD::UNIFORM_TYPE_SAMPLER_WITH_TEXTURE, 3, ridCullSampler);
		stHeightBounds.append_id(ridBounds);
		ridCullSet = pCache->get_cache(ridCull, 0, stOutput, stNodes, stHeightBounds,
									 RD::Uniform(RD::UNIFORM_TYPE_STORAGE_BUFFER, 4, stW.ridFeedback), RD::Uniform(RD::UNIFORM_TYPE_UNIFORM_BUFFER, 5, stW.ridConfiguration),
									 RD::Uniform(RD::UNIFORM_TYPE_STORAGE_BUFFER, 6, stW.ridCompaction));
		ridFinalizeSet = pCache->get_cache(ridFinalize, 0, stArgs, RD::Uniform(RD::UNIFORM_TYPE_STORAGE_BUFFER, 3, stW.ridCompaction));
	}
	else
	{
		const RID ridCounter = RID::from_uint64(stT.nCullCounterRd);
		ridCullSet = pCache->get_cache(ridCull, 0, stOutput, stNodes, RD::Uniform(RD::UNIFORM_TYPE_STORAGE_BUFFER, 2, ridCounter));
		ridFinalizeSet = pCache->get_cache(ridFinalize, 0, RD::Uniform(RD::UNIFORM_TYPE_STORAGE_BUFFER, 0, ridCounter), stArgs,
										   RD::Uniform(RD::UNIFORM_TYPE_STORAGE_BUFFER, 2, RID::from_uint64(stT.nCullShadowArgsRd)));
	}
	struct
	{
		float arrProjection[16];
		float arrCamera[4];
		float arrParams0[4];
		float arrParams1[4];
	} stPush = {};
	for (int nColumn = 0; nColumn < 4; ++nColumn)
	{
		for (int nRow = 0; nRow < 4; ++nRow)
		{
			stPush.arrProjection[nColumn * 4 + nRow] = projCullVp[nColumn][nRow];
		}
	}
	stPush.arrCamera[0] = vCameraPosition.x;
	stPush.arrCamera[1] = vCameraPosition.y;
	stPush.arrCamera[2] = vCameraPosition.z;
	stPush.arrCamera[3] = stT.rectHeightDomain.has_area() ? fProjectionScale : 4.0f;
	stPush.arrParams0[0] = stT.fCullSrcTexWidth;
	stPush.arrParams0[1] = float(stT.nCullNodeCount);
	stPush.arrParams0[2] = stT.fCullLod0Dist;
	stPush.arrParams0[3] = stT.fCullMaxDistance;
	stPush.arrParams1[0] = float(stT.nCullMaxLod);
	stPush.arrParams1[1] = stT.fCullVertexSpacing;
	stPush.arrParams1[2] = stT.fCullCompactTexWidth;
	stPush.arrParams1[3] = stT.rectHeightDomain.has_area() ? float(nClipMode) : 0.0f;
	uint32_t arrFinalPush[4] = { stT.nIndexCount, uint32_t(stT.fCullCompactTexWidth), nGroups, 0 };
	const uint32_t nDispatchWidth = MIN(nGroups, uint32_t(pRd->limit_get(RD::LIMIT_MAX_COMPUTE_WORKGROUP_COUNT_X)));
	const RD::ComputeListID nList = pRd->compute_list_begin();
	auto stDispatchTiles = [this, pRd, nList, nPipelineMode, ridCullSet, &stPush, nDispatchWidth, nGroups]()
	{
		pRd->compute_list_bind_compute_pipeline(nList, arrCullPipelines[nPipelineMode]);
		pRd->compute_list_bind_uniform_set(nList, ridCullSet, 0);
		pRd->compute_list_set_push_constant(nList, &stPush, sizeof(stPush));
		pRd->compute_list_dispatch(nList, nDispatchWidth, (nGroups + nDispatchWidth - 1) / nDispatchWidth, 1);
	};
	stDispatchTiles();
	pRd->compute_list_add_barrier(nList);
	pRd->compute_list_bind_compute_pipeline(nList, arrFinalizePipelines[nPipelineMode]);
	pRd->compute_list_bind_uniform_set(nList, ridFinalizeSet, 0);
	pRd->compute_list_set_push_constant(nList, arrFinalPush, sizeof(arrFinalPush));
	if (bNative)
	{
		// Stable candidate order across the color/depth and shadow passes.
		pRd->compute_list_dispatch(nList, nBlocks, 1, 1);
		pRd->compute_list_add_barrier(nList);
		arrFinalPush[3] = 1;
		pRd->compute_list_set_push_constant(nList, arrFinalPush, sizeof(arrFinalPush));
	}
	pRd->compute_list_dispatch(nList, 1, 1, 1);
	if (bNative)
	{
		pRd->compute_list_add_barrier(nList);
		stPush.arrParams1[3] += 4.0f;
		stDispatchTiles();
	}
	pRd->compute_list_end();
}

} // namespace RendererRD
