/**************************************************************************/
/*  RuntimeVirtualTextureCull.cpp                                        */
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

#pragma region Engine ZXB
// [ZXB] Runtime Virtual Texture: server side logic of RendererSceneCull (viewers, page scheduling, page culling).
#pragma endregion

#include "renderer_scene_cull.h"

#include "core/config/project_settings.h"
#include "core/io/dir_access.h"
#include "core/os/os.h"
#include "servers/rendering/renderer_viewport.h"

namespace
{
constexpr float RVT_NEAR = 0.0001f;
}

RID RendererSceneCull::RuntimeVirtualTextureAllocate()
{
	return stRuntimeVirtualTextureOwner.allocate_rid();
}

void RendererSceneCull::RuntimeVirtualTextureInitialize(RID ridRvt)
{
	stRuntimeVirtualTextureOwner.initialize_rid(ridRvt);
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	pRvt->ridSelf = ridRvt;

	// Placeholders get replaced by the GPU backend once the textures exist.
	pRvt->ridPageTableTexture = RSG::texture_storage->texture_allocate();
	RSG::texture_storage->texture_2d_placeholder_initialize(pRvt->ridPageTableTexture);
	for (int nI = 0; nI < 2; nI++)
	{
		pRvt->arrPhysicalTexture[nI] = RSG::texture_storage->texture_allocate();
		RSG::texture_storage->texture_2d_placeholder_initialize(pRvt->arrPhysicalTexture[nI]);
	}

	arrRuntimeVirtualTextures.push_back(ridRvt);
}

void RendererSceneCull::RuntimeVirtualTextureConfigure(RID ridRvt, RSE::RuntimeVirtualTextureMaterialType in_stType, int in_nLog2TileCount, int in_nTileSize, int in_nTileBorder, int in_nPoolTiles)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	ERR_FAIL_INDEX(in_stType, RSE::RVT_MATERIAL_MAX);
	pRvt->eMaterialType = in_stType;
	pRvt->nLog2TileCount = CLAMP(in_nLog2TileCount, 1, 10);
	pRvt->nTileSize = CLAMP(in_nTileSize, 16, 1024);
	pRvt->nTileBorder = CLAMP(in_nTileBorder, 0, 16);
	pRvt->nPoolTiles = CLAMP(in_nPoolTiles, 2, 255);
	pRvt->bConfigDirty = true;
}

void RendererSceneCull::RuntimeVirtualTextureSetScenario(RID ridRvt, RID ridScenario)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	if (pRvt->ridScenario != ridScenario)
	{
		pRvt->ridScenario = ridScenario;
		pRvt->bInvalidateAll = true;
	}
}

void RendererSceneCull::RuntimeVirtualTextureSetTransform(RID ridRvt, const Transform3D &xformTransform)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	if (pRvt->xformWorld != xformTransform)
	{
		const Transform3D xformOld = pRvt->xformWorld;
		pRvt->xformWorld = xformTransform;
		const bool bTerrainPbr = pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR;
		const bool bLocalMaterial = bTerrainPbr && pRvt->eSource == RSE::RVT_SOURCE_RENDER && pRvt->strPageFile.is_empty();
		const bool bTiltChanged = bLocalMaterial && !xformOld.basis.get_column(1).normalized().is_equal_approx(xformTransform.basis.get_column(1).normalized());
		const bool bHeightMovesUV = bLocalMaterial && xformOld.origin.y != xformTransform.origin.y &&
									(xformOld.basis.get_column(0).y != 0 || xformOld.basis.get_column(2).y != 0);
		const bool bMappingChanged = xformOld.origin.x != xformTransform.origin.x || xformOld.origin.z != xformTransform.origin.z ||
									 xformOld.basis.get_column(0) != xformTransform.basis.get_column(0) || xformOld.basis.get_column(2) != xformTransform.basis.get_column(2) ||
									 bTiltChanged || bHeightMovesUV;
		if (bTerrainPbr && bMappingChanged)
		{
			bool bReuseFeedback = false;
			pRvt->nFeedbackPages = 0;
			if (bLocalMaterial && !pRvt->bConfigDirty && pRvt->ridGpu.is_valid())
			{
				bReuseFeedback = pRvt->stPages.MoveWindow(xformOld, xformTransform) && pRvt->IsMovingMaterialDetail();
				pRvt->mapLockedPages.clear();
				pRvt->setDiskResidents.clear();
			}
			else
			{
				pRvt->bInvalidateAll = true;
				if (!pRvt->strPageFile.is_empty())
				{
					pRvt->bConfigDirty = true; // Recheck the baked file's world domain.
				}
			}
			if (!bReuseFeedback)
			{
				pRvt->mapFeedbackViews.clear();
				pRvt->mapMotionViews.clear();
			}
		}
		else if (!bTerrainPbr && (bMappingChanged || pRvt->eSource != RSE::RVT_SOURCE_HEIGHT_GRID))
		{
			pRvt->bInvalidateAll = true;
		}
	}
}

void RendererSceneCull::RuntimeVirtualTextureSetCullMask(RID ridRvt, uint32_t in_nMask)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	if (pRvt->nCullMask != in_nMask)
	{
		pRvt->nCullMask = in_nMask;
		pRvt->bInvalidateAll = true;
	}
}

void RendererSceneCull::RuntimeVirtualTextureSetHeightLod(RID ridRvt, float fLod0Distance, float fVertexSpacing, int nMaxLod, float fMaxDistance)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	pRvt->stHeightLod = { MAX(0.0f, fLod0Distance), MAX(0.0001f, fVertexSpacing), MAX(0, nMaxLod), MAX(0.0f, fMaxDistance) };
}

void RendererSceneCull::RuntimeVirtualTextureSetHeightSource(RID ridRvt, RID in_ridHeightArray, const PackedInt32Array &in_arrRegionMap, int in_nRegionSize, const Vector2i &in_vOrigin, int in_nExtent)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	const int nWidth = int(Math::sqrt(double(in_arrRegionMap.size())));
	ERR_FAIL_COND(nWidth == 0 || int64_t(nWidth) * nWidth != in_arrRegionMap.size() || in_nRegionSize <= 0 || in_nExtent <= 0);
	if (pRvt->eSource != RSE::RVT_SOURCE_HEIGHT_GRID)
	{
		RuntimeVirtualTextureSetSource(ridRvt, RSE::RVT_SOURCE_HEIGHT_GRID);
	}
	RendererSceneRender::HeightGrid &stGrid = pRvt->stHeightGrid;
	if (stGrid.nExtent != in_nExtent || stGrid.vOrigin != in_vOrigin || stGrid.nRegionSize != in_nRegionSize)
	{
		pRvt->bInvalidateAll = true;
	}
	stGrid.ridHeightArray = in_ridHeightArray;
	stGrid.arrRegionMap = in_arrRegionMap;
	stGrid.nRegionSize = in_nRegionSize;
	stGrid.nMapWidth = nWidth;
	stGrid.vOrigin = in_vOrigin;
	stGrid.nExtent = in_nExtent;
	TerrainHeightPageSource &stSparse = pRvt->stSparseGrid;
	if (stSparse.nMapWidth != nWidth || stSparse.nRegionSize != in_nRegionSize)
	{
		stSparse.arrRegions.clear();
		stSparse.arrRegions.resize(in_arrRegionMap.size());
	}
	stSparse.arrLookup = in_arrRegionMap;
	stSparse.nMapWidth = nWidth;
	stSparse.nRegionSize = in_nRegionSize;
	stSparse.vOrigin = in_vOrigin;
	stSparse.nExtent = in_nExtent;
	stGrid.nRevision++;
}

void RendererSceneCull::RuntimeVirtualTextureSetHeightRegion(RID ridRvt, const Vector2i &vLocation, const Ref<Image> &refHeight)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	TerrainHeightPageSource &stGrid = pRvt->stSparseGrid;
	const Vector2i vP = vLocation + Vector2i(stGrid.nMapWidth / 2, stGrid.nMapWidth / 2);
	ERR_FAIL_COND(uint32_t(vP.x) >= uint32_t(stGrid.nMapWidth) || uint32_t(vP.y) >= uint32_t(stGrid.nMapWidth));
	ERR_FAIL_COND(refHeight.is_valid() && (refHeight->get_format() != Image::FORMAT_RF || refHeight->get_size() != Vector2i(stGrid.nRegionSize, stGrid.nRegionSize)));
	stGrid.arrRegions.write[vP.y * stGrid.nMapWidth + vP.x] = refHeight.is_valid() ? refHeight->get_data() : Vector<uint8_t>();
}

void RendererSceneCull::RuntimeVirtualTextureSetHeightStream(RID ridRvt, const String &strPath, int in_nLevels)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	const int nLevels = CLAMP(in_nLevels, 0, int(pRvt->nLog2TileCount) + 1);
	if (pRvt->strPageFile == strPath && pRvt->nStreamLevels == nLevels)
	{
		return;
	}
	pRvt->strPageFile = strPath;
	pRvt->nStreamLevels = nLevels;
	pRvt->setModifiedStreamPages.clear();
	pRvt->bConfigDirty = true;
}

void RendererSceneCull::RuntimeVirtualTextureSetMaterialHeightSource(RID ridRvt, RID ridHeight)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	ERR_FAIL_COND(ridHeight.is_valid() && !stRuntimeVirtualTextureOwner.owns(ridHeight));
	if (pRvt->ridMaterialHeightSource != ridHeight)
	{
		pRvt->ridMaterialHeightSource = ridHeight;
		pRvt->stPages.InvalidateAll();
	}
}

void RendererSceneCull::RuntimeVirtualTextureSetMaterialStream(RID ridRvt, const String &strPath, int64_t nSignature)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	ERR_FAIL_COND(pRvt->eMaterialType != RSE::RVT_MATERIAL_TERRAIN_PBR);
	const bool bSameSource = pRvt->strPageFile == strPath && pRvt->nMaterialSignature == uint64_t(nSignature);
	if (bSameSource && (pRvt->bConfigDirty || strPath.is_empty()))
	{
		return;
	}
	// Explicitly reattaching a pathname must re-read its index. An importer may have
	// installed a valid bake after the old file was rejected, even within one clock tick.
	if (!bSameSource || pRvt->bMaterialStreamStale)
	{
		// A verified reattachment can also restore a previously quarantined source
		// when the caller has reverted its terrain edits to the original signature.
		pRvt->bMaterialStreamStale = false;
		pRvt->setModifiedStreamPages.clear();
	}
	else if (pRvt->bInvalidateAll)
	{
		// A rebuild consumes invalidate_all before the normal residency pass sees it.
		pRvt->bMaterialStreamStale = true;
	}
	pRvt->strPageFile = strPath;
	pRvt->nMaterialSignature = uint64_t(nSignature);
	pRvt->nStreamLevels = 0;
	pRvt->bConfigDirty = true;
}

Error RendererSceneCull::RuntimeVirtualTextureBakeMaterialStream(RID ridRvt, const String &strPath, int nCoarseLevels, int64_t nSignature)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL_V(pRvt, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(!pRvt->bEnabled || pRvt->eMaterialType != RSE::RVT_MATERIAL_TERRAIN_PBR || !scene_render->RuntimeVirtualTextureGpuIsSupported(), ERR_UNAVAILABLE);
	update_dirty_instances();
	RSG::utilities->update_dirty_resources();
	Instance *pWriter = instance_owner.get_or_null(pRvt->ridMaterialWriter);
	ERR_FAIL_COND_V(!pWriter || !pWriter->scenario || pWriter->scenario != scenario_owner.get_or_null(pRvt->ridScenario) || !pWriter->base_data || !pWriter->visible, ERR_UNCONFIGURED);
	ERR_FAIL_COND_V(nCoarseLevels < 1 || nCoarseLevels > int(pRvt->nLog2TileCount + 1), ERR_INVALID_PARAMETER);
	const Vector3 vSize = pRvt->xformWorld.basis.get_scale().abs();
	const Vector2 vExtent(vSize.x, vSize.z);
	const Rect2 rectRect(Vector2(pRvt->xformWorld.origin.x, pRvt->xformWorld.origin.z) - vExtent * 0.5f, vExtent);
	const uint32_t nFirstMip = pRvt->nLog2TileCount + 1 - nCoarseLevels;
	StreamingVirtualTextureFile::TerrainPBRWriter stFile;
	Error eErr = stFile.Begin(strPath, pRvt->nLog2TileCount, pRvt->nTileSize, pRvt->nTileBorder, nFirstMip, rectRect, uint64_t(nSignature));
	if (eErr != OK)
	{
		return eErr;
	}
	RendererSceneRender::RuntimeVirtualTextureGPUConfig stConfig;
	stConfig.stType = pRvt->eMaterialType;
	stConfig.nLog2TileCount = pRvt->nLog2TileCount;
	stConfig.nTileSize = pRvt->nTileSize;
	stConfig.nTileBorder = pRvt->nTileBorder;
	stConfig.nPoolTilesX = stConfig.nPoolTilesY = 1;
	const RID ridTarget = scene_render->RuntimeVirtualTextureGpuCreate(stConfig, RID(), RID(), RID());
	ERR_FAIL_COND_V(ridTarget.is_null(), ERR_CANT_CREATE);
	for (uint32_t nMip = nFirstMip; nMip <= pRvt->nLog2TileCount && eErr == OK; nMip++)
	{
		const uint32_t nN = 1u << (pRvt->nLog2TileCount - nMip);
		for (uint32_t nY = 0; nY < nN && eErr == OK; ++nY)
		{
			for (uint32_t nX = 0; nX < nN && eErr == OK; ++nX)
			{
				RVTPageManager::PageRender stPage;
				stPage.stKey = { nMip, nX, nY };
				stPage.nPoolX = stPage.nPoolY = 0;
				RuntimeVirtualTextureRenderPage(pRvt, stPage, ridTarget);
				const Vector<uint8_t> arrData = scene_render->RuntimeVirtualTextureGpuReadMaterialTile(ridTarget);
				eErr = arrData.is_empty() ? FAILED : stFile.WriteNext(arrData);
			}
		}
	}
	scene_render->RuntimeVirtualTextureGpuFree(ridTarget);
	if (eErr != OK)
	{
		return eErr;
	}

	// A loader may hold a Windows read handle or a batch decoded against the old index.
	// Let those readers finish before atomically publishing the replacement. On failure
	// their existing source and resident pages are still valid.
	const String strDestination = ProjectSettings::get_singleton()->globalize_path(strPath).simplify_path();
	const bool bCaseSensitive = DirAccess::create(DirAccess::ACCESS_FILESYSTEM)->is_case_sensitive(strDestination.get_base_dir());
	LocalVector<RuntimeVirtualTextureData *> arrConsumers;
	for (const RID &ridTexture : arrRuntimeVirtualTextures)
	{
		RuntimeVirtualTextureData *pConsumer = stRuntimeVirtualTextureOwner.get_or_null(ridTexture);
		if (!pConsumer || pConsumer->strPageFile.is_empty())
		{
			continue;
		}
		const String strCandidate = ProjectSettings::get_singleton()->globalize_path(pConsumer->strPageFile).simplify_path();
		if (bCaseSensitive ? strCandidate == strDestination : strCandidate.nocasecmp_to(strDestination) == 0)
		{
			pConsumer->stStreamLoader.Flush();
			arrConsumers.push_back(pConsumer);
		}
	}
	eErr = stFile.Finish();
	if (eErr != OK)
	{
		return eErr;
	}
	for (RuntimeVirtualTextureData *pConsumer : arrConsumers)
	{
		if (pConsumer == pRvt)
		{
			// This writer supplied the exact content being published. A peer sharing the
			// path must still check its own expected signature and local edit exclusions.
			pConsumer->nMaterialSignature = uint64_t(nSignature);
			pConsumer->bMaterialStreamStale = false;
			pConsumer->setModifiedStreamPages.clear();
			pConsumer->arrPendingInvalidations.clear();
			pConsumer->bInvalidateAll = false;
		}
		else if (pConsumer->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR && pConsumer->bInvalidateAll)
		{
			pConsumer->bMaterialStreamStale = true;
		}
		pConsumer->bConfigDirty = true;
	}
	return OK;
}

void RendererSceneCull::RuntimeVirtualTextureSetMaterialFeedbackLimits(RID ridRvt, const Vector4 &vLimits)
{
	RuntimeVirtualTextureData *pSurface = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pSurface);
	ERR_FAIL_COND(!vLimits.is_finite() || vLimits.x < 0 || vLimits.y < 0 || vLimits.z < 0 || vLimits.w < 0);
	if (pSurface->vMaterialFeedbackLimits != vLimits)
	{
		pSurface->vMaterialFeedbackLimits = vLimits;
		pSurface->mapFeedbackViews.clear();
		pSurface->mapMotionViews.clear();
		pSurface->nFeedbackPages = 0;
		pSurface->stPages.AdvanceMappingRevision();
	}
}

void RendererSceneCull::RuntimeVirtualTextureSetMaterialWriter(RID ridRvt, RID ridInstance, int nMaxAnisotropy)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	pRvt->nMaterialAnisotropy = CLAMP(nMaxAnisotropy, 1, 4);
	if (pRvt->ridMaterialWriter != ridInstance)
	{
		pRvt->ridMaterialWriter = ridInstance;
		pRvt->bInvalidateAll = true;
	}
}

void RendererSceneCull::RuntimeVirtualTextureSubmitGpuFeedback(RID ridRvt, RID ridView, const Vector<uint32_t> &arrIds, uint64_t nRevision)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	if (!pRvt || (pRvt->eSource != RSE::RVT_SOURCE_HEIGHT_GRID && pRvt->ridMaterialWriter.is_null()))
	{
		return; // Delayed readback from a freed terrain or a replaced source.
	}
	// Moving volumes bind an opaque capture ticket to the GPU dispatch. Look up the
	// actual camera and volume origins even if newer captures completed first.
	RuntimeVirtualTextureData::FeedbackCapture stCapture;
	if (nRevision & RuntimeVirtualTextureData::CAPTURE_FLAG)
	{
		RuntimeVirtualTextureData::MotionView *pView = pRvt->mapMotionViews.getptr(ridView);
		if (pView)
		{
			for (RuntimeVirtualTextureData::FeedbackCapture &stPending : pView->arrCaptures)
			{
				if (stPending.nTicket == nRevision)
				{
					stCapture = stPending;
					stPending.nTicket = 0;
					break;
				}
			}
		}
		const RuntimeVirtualTextureData::Feedback *pPrevious = pRvt->mapFeedbackViews.getptr(ridView);
		if (!stCapture.nTicket || (pPrevious && pPrevious->stCapture.nTicket >= stCapture.nTicket))
		{
			pRvt->nStaleFeedbackBatches++;
			return;
		}
		nRevision = stCapture.nRevision;
	}
	// Check the epoch even if a volume moved away and back to the same transform.
	if ((nRevision != 0 || pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR) && (pRvt->bConfigDirty || !pRvt->stPages.IsFeedbackCurrent(nRevision)))
	{
		pRvt->nStaleFeedbackBatches++;
		return;
	}
	RuntimeVirtualTextureData::Feedback &stFeedback = pRvt->mapFeedbackViews[ridView];
	stFeedback.stCapture = stCapture;
	stFeedback.mapSamples.clear();
	for (uint32_t nId : arrIds)
	{
		stFeedback.mapSamples[nId]++;
	}
	stFeedback.nStamp = pRvt->nUpdateFrame;
	pRvt->nFeedbackBatches++;
}

void RendererSceneCull::RuntimeVirtualTextureSetLodBias(RID ridRvt, float fBias)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	pRvt->fLodBias = fBias;
}

void RendererSceneCull::RuntimeVirtualTextureSetMaxPagesPerFrame(RID ridRvt, int nPages)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	pRvt->nMaxPagesPerFrame = MAX(nPages, 1);
}

void RendererSceneCull::RuntimeVirtualTextureSetEnabled(RID ridRvt, bool in_bEnabled)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	pRvt->bEnabled = in_bEnabled;
}

void RendererSceneCull::RuntimeVirtualTextureSetSource(RID ridRvt, RSE::RuntimeVirtualTextureSource in_eSource)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	if (pRvt->eSource != in_eSource)
	{
		pRvt->stStreamLoader.Configure(String());
		pRvt->mapFeedbackViews.clear();
		pRvt->mapMotionViews.clear();
		pRvt->eSource = in_eSource;
		pRvt->stStreamFile = StreamingVirtualTextureFile();
		pRvt->stPages.Reset();
		pRvt->bInvalidateAll = true;
		pRvt->bConfigDirty = true;
	}
}

void RendererSceneCull::RuntimeVirtualTextureSetDebug(RID ridRvt, RSE::RuntimeVirtualTextureDebugMode eMode, int nForceLod)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	ERR_FAIL_INDEX(eMode, RSE::RVT_DEBUG_MAX);
	pRvt->eDebugMode = eMode;
	pRvt->nDebugForceLod = CLAMP(nForceLod, -1, (int)pRvt->nLog2TileCount);
}

Dictionary RendererSceneCull::RuntimeVirtualTextureGetPageInfo(RID ridRvt, int in_nLevel, int in_nX, int in_nY) const
{
	Dictionary dictD;
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL_V(pRvt, dictD);
	ERR_FAIL_COND_V(in_nLevel < 0 || in_nLevel > (int)pRvt->stPages.GetMaxLevel(), dictD);
	const RVTPageManager::PageStatus stStatus = pRvt->stPages.GetPageStatus(in_nLevel, in_nX, in_nY);
	const uint32_t nId = RVTPageManager::MakePageId(in_nLevel, in_nX, in_nY);
	dictD["level"] = in_nLevel;
	dictD["x"] = in_nX;
	dictD["y"] = in_nY;
	dictD["exists"] = stStatus.bExists;
	dictD["resident"] = stStatus.bResident;
	dictD["dirty"] = stStatus.bDirty;
	dictD["blocked"] = stStatus.bBlocked;
	dictD["pool_x"] = (int)stStatus.nPoolX;
	dictD["pool_y"] = (int)stStatus.nPoolY;
	dictD["from_disk"] = stStatus.bResident && pRvt->setDiskResidents.has(nId);
	dictD["content_serial"] = int64_t(stStatus.nContentSerial);
	dictD["in_flight"] = pRvt->setStreamInFlight.has(nId);
	dictD["locked"] = pRvt->mapLockedPages.has(nId);
	if (pRvt->mapLockedPages.has(nId))
	{
		const uint64_t nNow = OS::get_singleton()->get_ticks_msec();
		const uint64_t nExpiry = pRvt->mapLockedPages[nId];
		dictD["lock_seconds_left"] = nExpiry > nNow ? double(nExpiry - nNow) / 1000.0 : 0.0;
	}
	return dictD;
}

void RendererSceneCull::RuntimeVirtualTextureLockPage(RID ridRvt, int in_nLevel, int in_nX, int in_nY, float fSeconds)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	ERR_FAIL_COND(in_nLevel < 0 || in_nLevel > (int)pRvt->stPages.GetMaxLevel());

	// Mirrors r.VT.RVT.MaxLockedPages: keep at most 6 pages, drop the one expiring first.
	constexpr uint32_t MAX_LOCKED_PAGES = 6;
	if (!pRvt->mapLockedPages.has(RVTPageManager::MakePageId(in_nLevel, in_nX, in_nY)) && pRvt->mapLockedPages.size() >= MAX_LOCKED_PAGES)
	{
		uint32_t nOldest = 0;
		uint64_t nOldestExpiry = UINT64_MAX;
		for (const KeyValue<uint32_t, uint64_t> &stKv : pRvt->mapLockedPages)
		{
			if (stKv.value < nOldestExpiry)
			{
				nOldestExpiry = stKv.value;
				nOldest = stKv.key;
			}
		}
		pRvt->mapLockedPages.erase(nOldest);
	}
	const uint64_t nNow = OS::get_singleton()->get_ticks_msec();
	const uint64_t nExpiry = nNow + uint64_t(MAX(fSeconds, 1.0f) * 1000.0);
	pRvt->mapLockedPages[RVTPageManager::MakePageId(in_nLevel, in_nX, in_nY)] = nExpiry;
}

void RendererSceneCull::RuntimeVirtualTextureUnlockPage(RID ridRvt, int in_nLevel, int in_nX, int in_nY)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	pRvt->mapLockedPages.erase(RVTPageManager::MakePageId(in_nLevel, in_nX, in_nY));
}

void RendererSceneCull::RuntimeVirtualTextureUnlockAllPages(RID ridRvt)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	pRvt->mapLockedPages.clear();
}

void RendererSceneCull::RuntimeVirtualTextureSetPageFile(RID ridRvt, const String &strPath)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	if (pRvt->strPageFile != strPath)
	{
		pRvt->strPageFile = strPath;
		pRvt->stStreamFile = StreamingVirtualTextureFile();
		pRvt->stPages.Reset();
		pRvt->bInvalidateAll = true;
		pRvt->bConfigDirty = true;
	}
}

void RendererSceneCull::RuntimeVirtualTextureInvalidate(RID ridRvt, const AABB &aabbWorldAabb)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	if (pRvt->arrPendingInvalidations.size() >= 64)
	{
		if (pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID)
		{
			pRvt->nStreamLevels = 0;
		}
		pRvt->bInvalidateAll = true; // Too many separate regions, refresh everything.
		return;
	}
	pRvt->arrPendingInvalidations.push_back(aabbWorldAabb);
}

void RendererSceneCull::RuntimeVirtualTextureInvalidateAll(RID ridRvt)
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL(pRvt);
	if (pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID)
	{
		pRvt->nStreamLevels = 0;
	}
	pRvt->bInvalidateAll = true;
}

RID RendererSceneCull::RuntimeVirtualTextureGetPageTableTexture(RID ridRvt) const
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL_V(pRvt, RID());
	return pRvt->ridPageTableTexture;
}

RID RendererSceneCull::RuntimeVirtualTextureGetPhysicalTexture(RID ridRvt, int nLayer) const
{
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL_V(pRvt, RID());
	ERR_FAIL_INDEX_V(nLayer, 2, RID());
	return pRvt->arrPhysicalTexture[nLayer];
}

Dictionary RendererSceneCull::RuntimeVirtualTextureGetStats(RID ridRvt) const
{
	Dictionary dictD;
	RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridRvt);
	ERR_FAIL_NULL_V(pRvt, dictD);
	const RVTPageManager::Stats stS = pRvt->stPages.GetStats();
	dictD["resident_pages"] = stS.nResidentPages;
	dictD["pool_pages"] = stS.nPoolPages;
	dictD["requested_pages"] = stS.nRequestedPages;
	dictD["rendered_this_frame"] = stS.nRenderedThisFrame;
	dictD["rendered_total"] = (int64_t)stS.nRenderedTotal;
	dictD["evicted_total"] = stS.nEvictedTotal;
	dictD["gpu_ready"] = pRvt->ridGpu.is_valid();
	PackedInt32Array arrLevels;
	for (int32_t nCount : pRvt->stPages.GetResidentPagesByLevel())
	{
		arrLevels.push_back(nCount);
	}
	dictD["levels"] = arrLevels;
	dictD["streaming"] = pRvt->eSource == RSE::RVT_SOURCE_STREAM;
	dictD["height_grid"] = pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID;
	dictD["sparse_height_source"] = pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID && pRvt->stHeightGrid.ridHeightArray.is_null();
	dictD["mapping_revision"] = int64_t(pRvt->stPages.GetMappingRevision());
	dictD["stale_feedback_batches"] = int64_t(pRvt->nStaleFeedbackBatches);
	dictD["retained_on_move"] = int64_t(stS.nRetainedOnMove);
	dictD["discarded_on_move"] = int64_t(stS.nDiscardedOnMove);
	dictD["gpu_feedback_batches"] = int64_t(pRvt->nFeedbackBatches);
	dictD["gpu_feedback_views"] = int(pRvt->mapFeedbackViews.size());
	dictD["gpu_feedback_pages"] = int64_t(pRvt->nFeedbackPages);
	dictD["produced_height_pages"] = int64_t(pRvt->nProducedPages);
	dictD["material_rendered_pages"] = int64_t(pRvt->nMaterialRenderedPages);
	dictD["material_height_source"] = pRvt->ridMaterialHeightSource;
	dictD["height_dependency_invalidations"] = int64_t(pRvt->nHeightDependencyInvalidations);
	dictD["stream_first_mip"] = pRvt->nStreamLevels && pRvt->stStreamFile.IsOpen() ? int(pRvt->nLog2TileCount + 1 - pRvt->nStreamLevels) : -1;
	dictD["disk_pages"] = int64_t(pRvt->nDiskPages);
	dictD["modified_stream_pages"] = int64_t(pRvt->setModifiedStreamPages.size());
	return dictD;
}

void RendererSceneCull::RuntimeVirtualTextureRefreshHeightDependents(RuntimeVirtualTextureData *pHeight)
{
	const LocalVector<Rect2> &arrAreas = pHeight->stPages.GetHeightChanges();
	if (arrAreas.is_empty())
	{
		return;
	}
	for (RID ridId : arrRuntimeVirtualTextures)
	{
		RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridId);
		if (!pRvt || pRvt->ridMaterialHeightSource != pHeight->ridSelf || pRvt->ridGpu.is_null())
		{
			continue;
		}
		const Transform3D xformUvTransform = pRvt->xformWorld.affine_inverse() * pHeight->xformWorld;
		const float fNormalRadius = 2.0f / MAX(pHeight->stHeightGrid.nExtent, 1);
		for (const Rect2 &rectArea : arrAreas)
		{
			// The normal stencil spans two height samples. Expand in the height
			// grid before mapping into a material volume with different world bounds.
			const Rect2 rectAffected = rectArea.grow(fNormalRadius);
			const Vector2 vPos = rectAffected.position - Vector2(0.5f, 0.5f);
			const AABB aabbLocal = xformUvTransform.xform(AABB(Vector3(vPos.x, -0.5f, vPos.y), Vector3(rectAffected.size.x, 1.0f, rectAffected.size.y)));
			const Rect2 rectUv(aabbLocal.position.x + 0.5f, aabbLocal.position.z + 0.5f, aabbLocal.size.x, aabbLocal.size.z);
			pRvt->stPages.InvalidateRect(rectUv, float(pRvt->nTileBorder + 1) / pRvt->nTileSize, &pRvt->setDiskResidents);
			pRvt->nHeightDependencyInvalidations++;
		}
	}
}

void RendererSceneCull::RuntimeVirtualTextureCollectMaterialFeedback(RID ridScenario, RID ridViewport, const Ref<RenderSceneBuffers> &refBuffers, const RendererSceneRender::CameraData &stCamera)
{
	for (RID ridId : arrRuntimeVirtualTextures)
	{
		RuntimeVirtualTextureData *pSurface = stRuntimeVirtualTextureOwner.get_or_null(ridId);
		if (!pSurface || !pSurface->bEnabled || pSurface->ridScenario != ridScenario || !pSurface->ridMaterialWriter.is_valid() || !pSurface->ridGpu.is_valid())
		{
			continue;
		}
		const bool bCapture = pSurface->nUpdateFrame % 4 == 0;
		uint64_t nTicket = pSurface->stPages.GetMappingRevision();
		if (pSurface->IsMovingMaterialDetail())
		{
			RuntimeVirtualTextureData::MotionView &stView = pSurface->mapMotionViews[ridViewport];
			const Vector3 vEye = stCamera.main_transform.origin;
			if (stView.nFrame != pSurface->nUpdateFrame)
			{
				const Vector3 vDelta = vEye - stView.vEye;
				const real_t fCutDistance = pSurface->vMaterialFeedbackLimits.z * 0.5f;
				if (stView.nFrame != UINT64_MAX && vDelta.length_squared() > fCutDistance * fCutDistance)
				{
					stView = RuntimeVirtualTextureData::MotionView();
					pSurface->mapFeedbackViews.erase(ridViewport);
				}
				stView.vVelocity = stView.nFrame != UINT64_MAX && stView.nFrame + 1 == pSurface->nUpdateFrame ? vDelta : Vector3();
				stView.vEye = vEye;
				stView.nFrame = pSurface->nUpdateFrame;
			}
			if (bCapture)
			{
				RuntimeVirtualTextureData::FeedbackCapture &stCapture = stView.arrCaptures[stView.nNextCapture++ % 8];
				stCapture.nTicket = ++pSurface->nNextCaptureTicket;
				stCapture.nRevision = nTicket;
				stCapture.vEye = vEye;
				stCapture.vOrigin = pSurface->xformWorld.origin;
				nTicket = stCapture.nTicket;
			}
		}
		if (bCapture)
		{
			scene_render->RuntimeVirtualTextureGpuFeedback(ridId, ridViewport, pSurface->xformWorld, pSurface->nLog2TileCount, pSurface->nTileSize, pSurface->nMaterialAnisotropy, pSurface->fLodBias, pSurface->vMaterialFeedbackLimits, nTicket, pSurface->ridGpu, refBuffers, stCamera);
		}
	}
}

void RendererSceneCull::RuntimeVirtualTextureRegisterViewer(const RendererSceneRender::CameraData *pCameraData, RID ridViewport, RID ridScenario)
{
	RuntimeVirtualTextureViewer stViewer;
	stViewer.ridScenario = ridScenario;
	stViewer.xformWorld = pCameraData->main_transform;
	stViewer.arrFrustum = pCameraData->main_projection.get_projection_planes(pCameraData->main_transform);

	// Projection [1][1] is cot(fov_y / 2) for perspective cameras and 2 / height for orthogonal ones.
	const Size2i vTargetSize = RSG::texture_storage->render_target_get_size(RSG::viewport->viewport_get_render_target(ridViewport));
	const float fHeightPixels = vTargetSize.y > 0 ? (float)vTargetSize.y : 720.0f;
	const float fWorldPerPixel = 2.0f / (Math::abs(pCameraData->main_projection.columns[1][1]) * fHeightPixels);
	if (pCameraData->is_orthogonal)
	{
		stViewer.fPixelOrtho = fWorldPerPixel;
	}
	else
	{
		stViewer.fPixelPerDistance = fWorldPerPixel;
	}

	if (arrRuntimeVirtualTextureViewers.size() < 16)
	{
		arrRuntimeVirtualTextureViewers.push_back(stViewer);
	}
}

void RendererSceneCull::RuntimeVirtualTextureInvalidateInstance(const Instance *in_pInstance, uint32_t in_nLayers) const
{
	if (!in_pInstance->scenario || !(((1 << in_pInstance->base_type) & RSE::INSTANCE_GEOMETRY_MASK)))
	{
		return;
	}
	AABB aabbBounds = in_pInstance->transformed_aabb;
	if (in_pInstance->prev_transformed_aabb.has_surface())
	{
		aabbBounds = aabbBounds.has_surface() ? aabbBounds.merge(in_pInstance->prev_transformed_aabb) : in_pInstance->prev_transformed_aabb;
	}
	if (!aabbBounds.has_surface())
	{
		return;
	}

	const uint32_t nLayers = in_nLayers ? in_nLayers : in_pInstance->layer_mask;
	for (const RID &ridTexture : arrRuntimeVirtualTextures)
	{
		RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridTexture);
		if (!pRvt || pRvt->eSource != RSE::RVT_SOURCE_RENDER || pRvt->ridMaterialWriter.is_valid() || pRvt->ridScenario != in_pInstance->scenario->self || !(pRvt->nCullMask & nLayers))
		{
			continue;
		}
		if (pRvt->arrPendingInvalidations.size() >= 64)
		{
			pRvt->bInvalidateAll = true;
		}
		else
		{
			pRvt->arrPendingInvalidations.push_back(aabbBounds);
		}
	}
}

void RendererSceneCull::RuntimeVirtualTextureRebuildGpu(RuntimeVirtualTextureData *in_pRvt)
{
	const RID ridOldGpu = in_pRvt->ridGpu;
	in_pRvt->stStreamLoader.Configure(String());
	in_pRvt->setDiskResidents.clear();
	in_pRvt->setStreamInFlight.clear();
	in_pRvt->mapStreamFailures.clear();
	in_pRvt->setObsoleteWork.clear();

	if (in_pRvt->eSource == RSE::RVT_SOURCE_STREAM)
	{
		if (in_pRvt->strPageFile.is_empty() || in_pRvt->stStreamFile.Open(in_pRvt->strPageFile) != OK)
		{
			WARN_PRINT(vformat("RuntimeVirtualTexture: cannot open page file '%s'.", in_pRvt->strPageFile));
			if (ridOldGpu.is_valid())
			{
				scene_render->RuntimeVirtualTextureGpuFree(ridOldGpu);
			}
			in_pRvt->ridGpu = RID();
			in_pRvt->bConfigDirty = false;
			return;
		}
		// The baked file owns the layout; the resource only supplies the pool size.
		const StreamingVirtualTextureFile::Header &stHeader = in_pRvt->stStreamFile.GetHeader();
		if (stHeader.nLog2TileCount > 10 || stHeader.nFormat == StreamingVirtualTextureFile::FORMAT_TERRAIN_PBR)
		{
			WARN_PRINT(vformat("RuntimeVirtualTexture: '%s' is incompatible with this single-layer streaming surface (format %d, log2 tiles %d).", in_pRvt->strPageFile, stHeader.nFormat, stHeader.nLog2TileCount));
			if (ridOldGpu.is_valid())
			{
				scene_render->RuntimeVirtualTextureGpuFree(ridOldGpu);
			}
			in_pRvt->ridGpu = RID();
			in_pRvt->bConfigDirty = false;
			return;
		}
		in_pRvt->nLog2TileCount = stHeader.nLog2TileCount;
		in_pRvt->nTileSize = stHeader.nTileSize;
		in_pRvt->nTileBorder = stHeader.nTileBorder;
		in_pRvt->nStreamFormat = stHeader.nFormat;
		in_pRvt->bStreamSrgb = stHeader.IsSrgb();
		in_pRvt->stStreamLoader.Configure(in_pRvt->strPageFile);
	}
	else if (in_pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR && !in_pRvt->bMaterialStreamStale && !in_pRvt->strPageFile.is_empty())
	{
		const Error eErr = in_pRvt->stStreamFile.Open(in_pRvt->strPageFile);
		const StreamingVirtualTextureFile::Header &stHeader = in_pRvt->stStreamFile.GetHeader();
		const Vector3 vSize = in_pRvt->xformWorld.basis.get_scale().abs();
		const Vector2 vExtent(vSize.x, vSize.z);
		const Rect2 rectRect(Vector2(in_pRvt->xformWorld.origin.x, in_pRvt->xformWorld.origin.z) - vExtent * 0.5f, vExtent);
		if (eErr == OK && stHeader.nFormat == StreamingVirtualTextureFile::FORMAT_TERRAIN_PBR && stHeader.nTileSize == in_pRvt->nTileSize && stHeader.nTileBorder == in_pRvt->nTileBorder &&
			stHeader.nLog2TileCount == in_pRvt->nLog2TileCount && stHeader.rectWorldRect.is_equal_approx(rectRect) && stHeader.nSourceSignature == in_pRvt->nMaterialSignature)
		{
			in_pRvt->nStreamLevels = stHeader.nLevelCount - stHeader.nFirstStoredMip;
			in_pRvt->stStreamLoader.Configure(in_pRvt->strPageFile);
		}
		else
		{
			if (eErr != OK)
			{
				WARN_PRINT(vformat("Terrain material SVT: cannot open '%s' (error %d), rendering live pages.", in_pRvt->strPageFile, int(eErr)));
			}
			else if (stHeader.nSourceSignature != in_pRvt->nMaterialSignature)
			{
				WARN_PRINT(vformat("Terrain material SVT: '%s' was baked for source %s, current source is %s. Rendering live pages. Rebuild through Terrain3D > Build Material Streaming Mips after source changes or when migrating a bake that omitted released textures.", in_pRvt->strPageFile, String::num_uint64(stHeader.nSourceSignature, 16), String::num_uint64(in_pRvt->nMaterialSignature, 16)));
			}
			else
			{
				WARN_PRINT(vformat("Terrain material SVT: the layout or world bounds of '%s' differ from this terrain. Rendering live pages.", in_pRvt->strPageFile));
			}
			in_pRvt->nStreamLevels = 0;
			in_pRvt->stStreamFile = StreamingVirtualTextureFile();
		}
	}
	else if (in_pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID && in_pRvt->nStreamLevels > 0 && !in_pRvt->strPageFile.is_empty())
	{
		const Error eErr = in_pRvt->stStreamFile.Open(in_pRvt->strPageFile);
		const StreamingVirtualTextureFile::Header &stHeader = in_pRvt->stStreamFile.GetHeader();
		if (eErr == OK && stHeader.nFormat == StreamingVirtualTextureFile::FORMAT_R32F && !stHeader.IsSrgb() && stHeader.nTileSize == in_pRvt->nTileSize &&
			stHeader.nTileBorder == in_pRvt->nTileBorder && stHeader.nLog2TileCount == in_pRvt->nLog2TileCount)
		{
			in_pRvt->stStreamLoader.Configure(in_pRvt->strPageFile);
		}
		else
		{
			in_pRvt->stStreamFile = StreamingVirtualTextureFile();
			WARN_PRINT(vformat("Height VT: incompatible baked coarse grid '%s', generating pages from terrain.", in_pRvt->strPageFile));
		}
	}
	else if (in_pRvt->stStreamFile.IsOpen())
	{
		in_pRvt->stStreamFile = StreamingVirtualTextureFile();
	}

	// A pool tile is tile_size + 2 * border texels; clamp the pool so the pool texture stays
	// inside the 16384 px limit every supported backend guarantees.
	const uint32_t nStrideTexels = in_pRvt->nTileSize + 2 * in_pRvt->nTileBorder;
	const uint32_t nMaxPoolTiles = MAX(1u, 16384u / nStrideTexels);
	if (in_pRvt->nPoolTiles > nMaxPoolTiles)
	{
		in_pRvt->nPoolTiles = nMaxPoolTiles;
	}

	RVTPageManager::Config stPm;
	stPm.nLog2Pages = in_pRvt->nLog2TileCount;
	stPm.nPoolPagesX = in_pRvt->nPoolTiles;
	stPm.nPoolPagesY = in_pRvt->nPoolTiles;
	stPm.nResidentLevels = in_pRvt->nPoolTiles >= 3 ? 2 : 1;
	stPm.bPrioritizeCoverage = in_pRvt->ridMaterialWriter.is_valid();
	stPm.bFadeIn = in_pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID;
	in_pRvt->stPages.Configure(stPm);
	if (in_pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR)
	{
		in_pRvt->mapFeedbackViews.clear();
		in_pRvt->mapMotionViews.clear();
		in_pRvt->nFeedbackPages = 0;
	}

	RendererSceneRender::RuntimeVirtualTextureGPUConfig stConfig;
	stConfig.stType = in_pRvt->eMaterialType;
	stConfig.nLog2TileCount = in_pRvt->nLog2TileCount;
	stConfig.nTileSize = in_pRvt->nTileSize;
	stConfig.nTileBorder = in_pRvt->nTileBorder;
	stConfig.nPoolTilesX = in_pRvt->nPoolTiles;
	stConfig.nPoolTilesY = in_pRvt->nPoolTiles;
	stConfig.bHeightGrid = in_pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID;
	stConfig.bStreaming = in_pRvt->eSource == RSE::RVT_SOURCE_STREAM;
	stConfig.nFormat = in_pRvt->nStreamFormat;
	stConfig.bSrgb = in_pRvt->bStreamSrgb;
	in_pRvt->ridGpu = scene_render->RuntimeVirtualTextureGpuCreate(stConfig, in_pRvt->ridPageTableTexture, in_pRvt->arrPhysicalTexture[0], in_pRvt->arrPhysicalTexture[1]);
	in_pRvt->bConfigDirty = false;

	// Free the old pool only after the new textures replaced the placeholders so no stale views are left behind.
	if (ridOldGpu.is_valid())
	{
		scene_render->RuntimeVirtualTextureGpuFree(ridOldGpu);
	}
}

void RendererSceneCull::RuntimeVirtualTextureRenderPage(RuntimeVirtualTextureData *in_pRvt, const RVTPageManager::PageRender &in_stPage, RID ridBakeTarget)
{
	const Transform3D xformRigid(in_pRvt->xformWorld.basis.orthonormalized(), in_pRvt->xformWorld.origin);
	const Vector3 vSize = in_pRvt->xformWorld.basis.get_scale().abs();

	// Page rectangle in volume UV space, grown by the border so bilinear filtering works across pages.
	const float fTiles = (float)(1u << (in_pRvt->nLog2TileCount - in_stPage.stKey.nLevel));
	const float fBorderUv = (float)in_pRvt->nTileBorder / ((float)in_pRvt->nTileSize * fTiles);
	const float fU0 = (float)in_stPage.stKey.nX / fTiles - fBorderUv;
	const float fU1 = (float)(in_stPage.stKey.nX + 1) / fTiles + fBorderUv;
	const float fV0 = (float)in_stPage.stKey.nY / fTiles - fBorderUv;
	const float fV1 = (float)(in_stPage.stKey.nY + 1) / fTiles + fBorderUv;

	const float fX0 = (fU0 - 0.5f) * vSize.x;
	const float fX1 = (fU1 - 0.5f) * vSize.x;
	const float fZ0 = (fV0 - 0.5f) * vSize.z;
	const float fZ1 = (fV1 - 0.5f) * vSize.z;

	// Camera above the volume looking down: image x = local +X, image y = local -Z.
	const Basis basisLookDown(Vector3(1, 0, 0), Vector3(0, 0, -1), Vector3(0, 1, 0));
	const Transform3D xformCamera = xformRigid * Transform3D(basisLookDown, Vector3((fX0 + fX1) * 0.5f, vSize.y * 0.5f, (fZ0 + fZ1) * 0.5f));

	Projection projProjection;
	projProjection.set_orthogonal(-(fX1 - fX0) * 0.5f, (fX1 - fX0) * 0.5f, -(fZ1 - fZ0) * 0.5f, (fZ1 - fZ0) * 0.5f, RVT_NEAR, vSize.y);

	const AABB aabbLocalBox(Vector3(fX0, -vSize.y * 0.5f, fZ0), Vector3(fX1 - fX0, vSize.y, fZ1 - fZ0));
	const AABB aabbWorldBox = xformRigid.xform(aabbLocalBox);

	Scenario *pScenario = scenario_owner.get_or_null(in_pRvt->ridScenario);
	ERR_FAIL_NULL(pScenario);

	struct CullAABB
	{
		PagedArray<Instance *> *pResult;
		uint32_t nMask;
		_FORCE_INLINE_ bool operator()(void *pData)
		{
			Instance *pInstance = (Instance *)pData;
			if (pInstance->visible && (pInstance->layer_mask & nMask))
			{
				pResult->push_back(pInstance);
			}
			return false;
		}
	};

	instance_cull_result.clear();
	scene_cull_result.geometry_instances.clear();
	CullAABB stPageCull;
	stPageCull.pResult = &instance_cull_result;
	stPageCull.nMask = in_pRvt->nCullMask;
	if (in_pRvt->ridMaterialWriter.is_valid())
	{
		Instance *pWriter = instance_owner.get_or_null(in_pRvt->ridMaterialWriter);
		if (pWriter && pWriter->scenario == pScenario && pWriter->visible)
		{
			instance_cull_result.push_back(pWriter);
		}
	}
	else
	{
		pScenario->indexers[Scenario::INDEXER_GEOMETRY].aabb_query(aabbWorldBox, stPageCull);
		pScenario->indexers[Scenario::INDEXER_VOLUMES].aabb_query(aabbWorldBox, stPageCull);
	}

	for (uint32_t nI = 0; nI < instance_cull_result.size(); nI++)
	{
		Instance *pInstance = instance_cull_result[nI];
		if (!pInstance || !((1 << pInstance->base_type) & (RSE::INSTANCE_GEOMETRY_MASK & ~(1 << RSE::INSTANCE_PARTICLES))))
		{
			continue;
		}
		InstanceGeometryData *pGeom = static_cast<InstanceGeometryData *>(pInstance->base_data);
		if (pGeom && pGeom->geometry_instance)
		{
			scene_cull_result.geometry_instances.push_back(pGeom->geometry_instance);
		}
	}

	scene_render->RuntimeVirtualTextureGpuRenderPage(ridBakeTarget.is_valid() ? ridBakeTarget : in_pRvt->ridGpu, xformCamera, projProjection, scene_cull_result.geometry_instances, in_stPage.nPoolX, in_stPage.nPoolY, vSize.y);
}

// Runs before dirty resources are flushed so materials rebind the replaced textures in the same frame.
void RendererSceneCull::UpdateRuntimeVirtualTextureObjects()
{
	if (arrRuntimeVirtualTextures.is_empty() || !scene_render->RuntimeVirtualTextureGpuIsSupported())
	{
		return;
	}
	for (const RID &ridTexture : arrRuntimeVirtualTextures)
	{
		RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridTexture);
		if (!pRvt || !pRvt->bEnabled || !scenario_owner.owns(pRvt->ridScenario))
		{
			continue;
		}
		if (pRvt->bConfigDirty || pRvt->ridGpu.is_null())
		{
			RuntimeVirtualTextureRebuildGpu(pRvt);
			pRvt->bInvalidateAll = false;
		}
	}
}

void RendererSceneCull::RenderRuntimeVirtualTextures()
{
	LocalVector<RuntimeVirtualTextureViewer> arrViewers = std::move(arrRuntimeVirtualTextureViewers);
	arrRuntimeVirtualTextureViewers.clear();

	if (arrRuntimeVirtualTextures.is_empty() || !scene_render->RuntimeVirtualTextureGpuIsSupported())
	{
		return;
	}

	for (const RID &ridTexture : arrRuntimeVirtualTextures)
	{
		RuntimeVirtualTextureData *pRvt = stRuntimeVirtualTextureOwner.get_or_null(ridTexture);
		if (!pRvt || !pRvt->bEnabled || !scenario_owner.owns(pRvt->ridScenario))
		{
			continue;
		}

		if (pRvt->bConfigDirty || pRvt->ridGpu.is_null())
		{
			continue; // Created by update_runtime_virtual_texture_objects() next frame.
		}

		const Transform3D xformRigid(pRvt->xformWorld.basis.orthonormalized(), pRvt->xformWorld.origin);
		const Transform3D xformToLocal = xformRigid.affine_inverse();
		const Vector3 vSize = pRvt->xformWorld.basis.get_scale().abs();

		pRvt->nUpdateFrame++;
		const bool bHeightGrid = pRvt->eSource == RSE::RVT_SOURCE_HEIGHT_GRID;
		const bool bSparse = bHeightGrid && pRvt->stHeightGrid.ridHeightArray.is_null();
		pRvt->stSparseGrid.nVirtualSize = (1u << pRvt->nLog2TileCount) * pRvt->nTileSize;
		pRvt->stSparseGrid.nTile = pRvt->nTileSize;
		pRvt->stSparseGrid.nBorder = pRvt->nTileBorder;
		const bool bHybrid = (bHeightGrid || pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR) && pRvt->stStreamFile.IsOpen() && pRvt->nStreamLevels > 0;
		if (pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR && (!instance_owner.owns(pRvt->ridMaterialWriter) || !instance_owner.get_or_null(pRvt->ridMaterialWriter)->base_data))
		{
			continue;
		}
		if (pRvt->bInvalidateAll)
		{
			pRvt->stPages.InvalidateAll();
			pRvt->setObsoleteWork = pRvt->setStreamInFlight;
			if (bHybrid)
			{
				// All baked tiles are now stale. They can be used again after a new bake is supplied.
				pRvt->bMaterialStreamStale = pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR;
				pRvt->nStreamLevels = 0;
			}
		}
		else
		{
			for (const AABB &aabbWorld : pRvt->arrPendingInvalidations)
			{
				const AABB aabbLocal = xformToLocal.xform(aabbWorld);
				const Rect2 rectUvRect(Vector2(aabbLocal.position.x / vSize.x + 0.5f, aabbLocal.position.z / vSize.z + 0.5f), Vector2(aabbLocal.size.x / vSize.x, aabbLocal.size.z / vSize.z));
				const float fApron = float(pRvt->nTileBorder + 1) / pRvt->nTileSize;
				for (uint32_t nId : pRvt->setStreamInFlight)
				{
					const RVTPageManager::PageKey stKey = RVTPageManager::DecodePageId(nId);
					const float fSpan = 1.f / float(1u << (pRvt->nLog2TileCount - stKey.nLevel));
					Rect2 rectRect(Vector2(stKey.nX * fSpan, stKey.nY * fSpan), Vector2(fSpan, fSpan));
					if (rectRect.grow(fApron * fSpan + 1e-7f).intersects(rectUvRect, true))
					{
						pRvt->setObsoleteWork.insert(nId);
					}
				}
				pRvt->stPages.InvalidateRect(rectUvRect.grow(1e-7f), fApron);
				if (bHybrid)
				{
					for (int nL = int(pRvt->nLog2TileCount) + 1 - pRvt->nStreamLevels; nL <= int(pRvt->nLog2TileCount); ++nL)
					{
						const int nN = 1 << (pRvt->nLog2TileCount - nL);
						const Rect2 rectRect = rectUvRect.grow((fApron + 1e-5f) / nN);
						Vector2i vLo = (rectRect.position * nN).floor();
						Vector2i vHi = (rectRect.get_end() * nN).floor();
						for (int nY = MAX(0, vLo.y); nY <= MIN(nN - 1, vHi.y); nY++)
						{
							for (int nX = MAX(0, vLo.x); nX <= MIN(nN - 1, vHi.x); nX++)
							{
								pRvt->setModifiedStreamPages.insert(RVTPageManager::MakePageId(nL, nX, nY));
							}
						}
					}
				}
			}
		}
		pRvt->bInvalidateAll = false;
		pRvt->arrPendingInvalidations.clear();

		pRvt->stPages.BeginFrame();
		pRvt->stPages.RequestResidentLevels();

		// Locked pages stay in the request set (highest priority) so they are produced even when
		// off screen, and are refreshed every frame until they expire (UE RefreshPickedPage).
		if (!pRvt->mapLockedPages.is_empty())
		{
			const uint64_t nNow = OS::get_singleton()->get_ticks_msec();
			LocalVector<uint32_t> arrExpired;
			for (const KeyValue<uint32_t, uint64_t> &stKv : pRvt->mapLockedPages)
			{
				if (stKv.value <= nNow)
				{
					arrExpired.push_back(stKv.key);
					continue;
				}
				const RVTPageManager::PageKey stKey = RVTPageManager::DecodePageId(stKv.key);
				pRvt->stPages.RequestPage(stKey.nLevel, stKey.nX, stKey.nY, -2.0f);
				if (pRvt->eSource == RSE::RVT_SOURCE_RENDER && pRvt->eMaterialType != RSE::RVT_MATERIAL_TERRAIN_PBR)
				{
					pRvt->stPages.InvalidatePage(stKey.nLevel, stKey.nX, stKey.nY);
				}
			}
			for (const uint32_t nId : arrExpired)
			{
				pRvt->mapLockedPages.erase(nId);
			}
		}

		pRvt->nFeedbackPages = 0;
		Vector<RID> arrExpiredMotion;
		for (const auto &stView : pRvt->mapMotionViews)
		{
			if (pRvt->nUpdateFrame - stView.value.nFrame > 24)
			{
				arrExpiredMotion.push_back(stView.key);
			}
		}
		for (const RID &stViewport : arrExpiredMotion)
		{
			pRvt->mapMotionViews.erase(stViewport);
			pRvt->mapFeedbackViews.erase(stViewport);
		}

		Vector<RID> arrExpiredFeedback;
		for (const auto &stItem : pRvt->mapFeedbackViews)
		{
			if (pRvt->nUpdateFrame - stItem.value.nStamp > 24)
			{
				arrExpiredFeedback.push_back(stItem.key);
				continue;
			}
			const RuntimeVirtualTextureData::MotionView *pMotion = stItem.value.stCapture.nTicket ? pRvt->mapMotionViews.getptr(stItem.key) : nullptr;
			Vector2 vCurrentOffsetUV;
			Vector2 vVelocityUV;
			if (pMotion)
			{
				// VT updates precede the viewport draw, so the most recent eye belongs to
				// the previous frame. Shift completed feedback in world space, then express
				// it in the new window, including quarter-window snaps between readbacks.
				const Vector3 vVelocity = pRvt->nUpdateFrame - pMotion->nFrame <= 1 ? pMotion->vVelocity : Vector3();
				const Vector3 vDelta = (pMotion->vEye - stItem.value.stCapture.vEye) +
									   (stItem.value.stCapture.vOrigin - pRvt->xformWorld.origin) + vVelocity;
				const Vector3 vLocalDelta = xformToLocal.basis.xform(vDelta);
				const Vector3 vLocalVelocity = xformToLocal.basis.xform(vVelocity);
				vCurrentOffsetUV = Vector2(vLocalDelta.x / vSize.x, vLocalDelta.z / vSize.z);
				vVelocityUV = Vector2(vLocalVelocity.x / vSize.x, vLocalVelocity.z / vSize.z);
			}
			for (const KeyValue<uint32_t, uint32_t> &stHit : stItem.value.mapSamples)
			{
				const uint32_t nPacked = stHit.key;
				const uint32_t nLevel = nPacked >> 24;
				const uint32_t nX = nPacked & 4095;
				const uint32_t nY = (nPacked >> 12) & 4095;
				if (nLevel > pRvt->nLog2TileCount)
				{
					continue;
				}
				const uint32_t nN = 1u << (pRvt->nLog2TileCount - nLevel);
				if (nX >= nN || nY >= nN)
				{
					continue;
				}
				if (pRvt->ridMaterialWriter.is_valid())
				{
					// A trilinear lookup consumes the indicated level and its immediate parent.
					const float fWeight = 1.0f / stHit.value;
					if (pMotion)
					{
						pRvt->stPages.RequestMovingFootprint({ nLevel, nX, nY }, vCurrentOffsetUV, vVelocityUV, fWeight);
						pRvt->nFeedbackPages++;
						continue;
					}
					pRvt->stPages.RequestPage(nLevel, nX, nY, fWeight);
					if (nLevel < pRvt->nLog2TileCount)
					{
						pRvt->stPages.RequestPage(nLevel + 1, nX >> 1, nY >> 1, fWeight);
					}
					pRvt->nFeedbackPages++;
					continue;
				}
				const Vector2 vCenter(((nX + 0.5f) / nN - 0.5f) * vSize.x, ((nY + 0.5f) / nN - 0.5f) * vSize.z);
				float fPriority = FLT_MAX;
				for (const RuntimeVirtualTextureViewer &stViewer : arrViewers)
				{
					if (stViewer.ridScenario == pRvt->ridScenario)
					{
						const Vector3 vPos = xformToLocal.xform(stViewer.xformWorld.origin);
						fPriority = MIN(fPriority, Vector2(vPos.x, vPos.z).distance_squared_to(vCenter));
					}
				}
				for (uint32_t nL = nLevel; nL <= pRvt->nLog2TileCount; nL++)
				{
					pRvt->stPages.RequestPage(nL, nX >> (nL - nLevel), nY >> (nL - nLevel), fPriority);
				}
				pRvt->nFeedbackPages++;
			}
		}
		for (RID ridStaleView : arrExpiredFeedback)
		{
			pRvt->mapFeedbackViews.erase(ridStaleView);
		}

		RVTPageManager::View stView;
		stView.vSize = vSize;
		stView.stHeightLod = pRvt->stHeightLod;
		stView.fLodBias = pRvt->fLodBias;
		stView.fTexelSizeLevel0 = MIN(vSize.x, vSize.z) / (float)((1u << pRvt->nLog2TileCount) * pRvt->nTileSize);
		for (const RuntimeVirtualTextureViewer &stViewer : arrViewers)
		{
			if (stViewer.ridScenario != pRvt->ridScenario || !pRvt->mapFeedbackViews.is_empty())
			{
				continue;
			}
			stView.vViewer = xformToLocal.xform(stViewer.xformWorld.origin);
			stView.fPixelPerDistance = stViewer.fPixelPerDistance;
			stView.fPixelOrtho = stViewer.fPixelOrtho;
			stView.arrFrustum.clear();
			for (const Plane &planeFrustum : stViewer.arrFrustum)
			{
				stView.arrFrustum.push_back(xformToLocal.xform(planeFrustum));
			}
			pRvt->stPages.RequestView(stView);
		}

		const bool bStreaming = pRvt->eSource == RSE::RVT_SOURCE_STREAM;
		if (bStreaming || bHeightGrid || bHybrid || pRvt->stStreamLoader.HasPending() || pRvt->stStreamLoader.IsBusy() || !pRvt->setStreamInFlight.is_empty())
		{
			LocalVector<StreamingVirtualTextureLoader::Result> arrResults;
			if (pRvt->stStreamLoader.Poll(arrResults))
			{
				for (const StreamingVirtualTextureLoader::Result &stResult : arrResults)
				{
					const RVTPageManager::PageKey stKey = RVTPageManager::DecodePageId(stResult.nId);
					pRvt->setStreamInFlight.erase(stResult.nId);
					if (pRvt->setObsoleteWork.erase(stResult.nId))
					{
						pRvt->stPages.DiscardPage(stKey.nLevel, stKey.nX, stKey.nY);
						continue;
					}
					if (!stResult.bFromGrid && !bStreaming && (!pRvt->nStreamLevels || pRvt->setModifiedStreamPages.has(stResult.nId) || stResult.arrData.is_empty()))
					{
						pRvt->setModifiedStreamPages.insert(stResult.nId);
						pRvt->stPages.DiscardPage(stKey.nLevel, stKey.nX, stKey.nY);
						continue;
					}
					if (stResult.arrData.is_empty())
					{
						pRvt->stPages.DiscardPage(stKey.nLevel, stKey.nX, stKey.nY);
						// Retry a couple of times, then give up and let the page resolve through an
						// ancestor so the slot is not held forever by a broken tile.
						const uint8_t nFailures = pRvt->mapStreamFailures.has(stResult.nId) ? pRvt->mapStreamFailures[stResult.nId] + 1 : 1;
						pRvt->mapStreamFailures[stResult.nId] = nFailures;
						if (nFailures >= 3)
						{
							pRvt->stPages.BlockPage(stKey.nLevel, stKey.nX, stKey.nY);
							pRvt->mapStreamFailures.erase(stResult.nId);
						}
						continue;
					}
					uint32_t nPoolX = 0;
					uint32_t nPoolY = 0;
					if (!pRvt->stPages.GetSlot(stKey, nPoolX, nPoolY))
					{
						continue;
					}
					scene_render->RuntimeVirtualTextureGpuUploadPage(pRvt->ridGpu, nPoolX, nPoolY, stResult.arrData);
					if (stResult.bFromGrid)
					{
						pRvt->setDiskResidents.erase(stResult.nId);
						pRvt->nProducedPages++;
					}
					else
					{
						pRvt->nDiskPages++;
						pRvt->setDiskResidents.insert(stResult.nId);
					}
					pRvt->stPages.MarkRendered(stKey, !stResult.bFromGrid);
				}
			}
		}

		LocalVector<RVTPageManager::PageRender> arrPending;
		if ((!bStreaming && !bSparse && !bHybrid) || (!pRvt->stStreamLoader.IsBusy() && !pRvt->stStreamLoader.HasPending()))
		{
			pRvt->stPages.TakePending(pRvt->nMaxPagesPerFrame, arrPending);
		}
		for (const RVTPageManager::PageRender &stPage : arrPending)
		{
			const uint32_t nId = RVTPageManager::MakePageId(stPage.stKey.nLevel, stPage.stKey.nX, stPage.stKey.nY);
			const bool bFromDisk = bHybrid && int(stPage.stKey.nLevel) > int(pRvt->nLog2TileCount) - pRvt->nStreamLevels && !pRvt->setModifiedStreamPages.has(nId);
			if (bFromDisk && stPage.stKey.nLevel == pRvt->nLog2TileCount)
			{
				// The root must be usable by this draw even before asynchronous fine pages arrive.
				Vector<uint8_t> arrRoot;
				if (pRvt->stStreamFile.ReadTile(stPage.stKey.nLevel, 0, 0, arrRoot) == OK)
				{
					scene_render->RuntimeVirtualTextureGpuUploadPage(pRvt->ridGpu, stPage.nPoolX, stPage.nPoolY, arrRoot);
					pRvt->stPages.MarkRendered(stPage.stKey, true);
					pRvt->nDiskPages++;
					pRvt->setDiskResidents.insert(nId);
					continue;
				}
				pRvt->setModifiedStreamPages.insert(nId);
			}
			if (bStreaming || (bFromDisk && !pRvt->setModifiedStreamPages.has(nId)))
			{
				if (pRvt->setStreamInFlight.has(nId))
				{
					continue;
				}
				pRvt->setStreamInFlight.insert(nId);
				pRvt->stStreamLoader.RequestPage(nId, stPage.stKey.nLevel, stPage.stKey.nX, stPage.stKey.nY);
			}
			else if (bSparse && stPage.stKey.nLevel == pRvt->nLog2TileCount)
			{
				const Vector<uint8_t> arrData = pRvt->stSparseGrid.Produce(stPage.stKey.nLevel, 0, 0);
				if (!arrData.is_empty())
				{
					scene_render->RuntimeVirtualTextureGpuUploadPage(pRvt->ridGpu, stPage.nPoolX, stPage.nPoolY, arrData);
					pRvt->stPages.MarkRendered(stPage.stKey);
					pRvt->setDiskResidents.erase(nId);
					pRvt->nProducedPages++;
				}
				else
				{
					pRvt->stPages.DiscardPage(stPage.stKey.nLevel, stPage.stKey.nX, stPage.stKey.nY);
				}
			}
			else if (bSparse)
			{
				if (!pRvt->setStreamInFlight.has(nId))
				{
					pRvt->setStreamInFlight.insert(nId);
					pRvt->stStreamLoader.RequestPage(nId, stPage.stKey.nLevel, stPage.stKey.nX, stPage.stKey.nY, pRvt->stSparseGrid);
				}
			}
			else if (bHeightGrid)
			{
				if (scene_render->RuntimeVirtualTextureGpuDrawHeight(pRvt->ridGpu, pRvt->stHeightGrid, Vector2i(stPage.stKey.nX, stPage.stKey.nY), stPage.stKey.nLevel, Vector2i(stPage.nPoolX, stPage.nPoolY)))
				{
					pRvt->stPages.MarkRendered(stPage.stKey);
					pRvt->setDiskResidents.erase(nId);
					pRvt->nProducedPages++;
				}
				else
				{
					pRvt->stPages.DiscardPage(stPage.stKey.nLevel, stPage.stKey.nX, stPage.stKey.nY);
				}
			}
			else
			{
				RuntimeVirtualTextureRenderPage(pRvt, stPage);
				pRvt->stPages.MarkRendered(stPage.stKey);
				if (pRvt->eMaterialType == RSE::RVT_MATERIAL_TERRAIN_PBR)
				{
					pRvt->nMaterialRenderedPages++;
					pRvt->setDiskResidents.erase(nId);
				}
			}
		}
		if (bStreaming || bHybrid || bSparse)
		{
			pRvt->stStreamLoader.Submit();
		}

		if (pRvt->stPages.IsPageTableDirty())
		{
			LocalVector<Vector<uint8_t>> arrLevels;
			for (uint32_t nL = 0; nL < pRvt->stPages.GetLevelCount(); nL++)
			{
				arrLevels.push_back(pRvt->stPages.GetPageTableLevel(nL));
			}
			scene_render->RuntimeVirtualTextureGpuUpdatePageTable(pRvt->ridGpu, arrLevels);
			pRvt->stPages.ClearPageTableDirty();
		}
		if (bHeightGrid)
		{
			RuntimeVirtualTextureRefreshHeightDependents(pRvt);
		}
	}
}
