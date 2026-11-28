/**************************************************************************/
/*  TerrainGPUCull.cpp                                                   */
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

#include "renderer_scene_cull.h"

#pragma region Engine ZXB
// [ZXB] GPU-driven terrain entries. The extension creates the RD vertex/index arrays, the material
// and the indirect buffers; the forward renderer issues the indirect draws (see RenderForwardClustered).

RID RendererSceneCull::GpuDrivenTerrainAllocate()
{
	MutexLock lockTerrains(mtxGpuDrivenTerrainMutex);
	GPUTerrain stTerrain;
	RID ridTerrain = stGpuDrivenTerrainOwner.make_rid(stTerrain);
	mapGpuDrivenTerrains[ridTerrain] = stTerrain;
	return ridTerrain;
}

void RendererSceneCull::GpuDrivenTerrainInitialize(RID ridTerrain)
{
	MutexLock lockTerrains(mtxGpuDrivenTerrainMutex);
	ERR_FAIL_COND(!stGpuDrivenTerrainOwner.owns(ridTerrain));
}

void RendererSceneCull::GpuDrivenTerrainConfigure(RID ridTerrain, RID in_ridMaterial, RID in_ridVertexArray, RID in_ridIndexArray, uint32_t in_nIndexCount, int64_t in_nVertexFormatId, uint32_t in_nRenderLayers, bool in_bCastShadows)
{
	MutexLock lockTerrains(mtxGpuDrivenTerrainMutex);
	ERR_FAIL_COND(!stGpuDrivenTerrainOwner.owns(ridTerrain));
	GPUTerrain &stTerrain = mapGpuDrivenTerrains[ridTerrain];
	stTerrain.ridMaterial = in_ridMaterial;
	stTerrain.ridVertexArray = in_ridVertexArray;
	stTerrain.ridIndexArray = in_ridIndexArray;
	stTerrain.nIndexCount = in_nIndexCount;
	stTerrain.nVertexFormatId = in_nVertexFormatId;
	stTerrain.nRenderLayers = in_nRenderLayers;
	stTerrain.bCastShadows = in_bCastShadows;
}

void RendererSceneCull::GpuDrivenTerrainSetIndirect(RID ridTerrain, RID in_ridIndirectColor, uint32_t nColorOffset, RID in_ridIndirectShadow, uint32_t nShadowOffset)
{
	MutexLock lockTerrains(mtxGpuDrivenTerrainMutex);
	ERR_FAIL_COND(!stGpuDrivenTerrainOwner.owns(ridTerrain));
	GPUTerrain &stTerrain = mapGpuDrivenTerrains[ridTerrain];
	stTerrain.ridIndirectColor = in_ridIndirectColor;
	stTerrain.nIndirectColorOffset = nColorOffset;
	stTerrain.ridIndirectShadow = in_ridIndirectShadow;
	stTerrain.nIndirectShadowOffset = nShadowOffset;
}

void RendererSceneCull::GpuDrivenTerrainSetCull(RID ridTerrain, int64_t nSrcNodesRd, int64_t nCompactNodesRd, int64_t nCounterRd, int64_t nArgsRd, int64_t nShadowArgsRd, uint32_t nNodeCount, float fSrcTexWidth, float fCompactTexWidth, float fLod0Dist, int32_t nMaxLod, float fMaxDistance, float fVertexSpacing)
{
	MutexLock lockTerrains(mtxGpuDrivenTerrainMutex);
	ERR_FAIL_COND(!stGpuDrivenTerrainOwner.owns(ridTerrain));
	GPUTerrain &stTerrain = mapGpuDrivenTerrains[ridTerrain];
	stTerrain.nCullSrcNodesRd = nSrcNodesRd;
	stTerrain.nCullCompactNodesRd = nCompactNodesRd;
	stTerrain.nCullCounterRd = nCounterRd;
	stTerrain.nCullArgsRd = nArgsRd;
	stTerrain.nCullShadowArgsRd = nShadowArgsRd;
	stTerrain.nCullNodeCount = nNodeCount;
	stTerrain.fCullSrcTexWidth = fSrcTexWidth;
	stTerrain.fCullCompactTexWidth = fCompactTexWidth;
	stTerrain.fCullLod0Dist = fLod0Dist;
	stTerrain.nCullMaxLod = nMaxLod;
	stTerrain.fCullMaxDistance = fMaxDistance;
	stTerrain.fCullVertexSpacing = fVertexSpacing;
}

void RendererSceneCull::GpuDrivenTerrainSetHeightfield(RID ridTerrain, RID in_ridHeightVt, RID ridBoundsTexture, const Rect2 &rectDomain, const Vector2 &in_vBackgroundHeights, float in_fHeightMargin, int nLog2Tiles, int nTileSize)
{
	MutexLock lockTerrains(mtxGpuDrivenTerrainMutex);
	ERR_FAIL_COND(!stGpuDrivenTerrainOwner.owns(ridTerrain));
	ERR_FAIL_COND(nLog2Tiles < 0 || nLog2Tiles > 10 || nTileSize < 0);
	GPUTerrain &stTerrain = mapGpuDrivenTerrains[ridTerrain];
	stTerrain.ridHeightVt = in_ridHeightVt;
	stTerrain.ridHeightBounds = ridBoundsTexture;
	stTerrain.rectHeightDomain = rectDomain;
	stTerrain.vBackgroundHeights = in_vBackgroundHeights;
	stTerrain.fHeightMargin = MAX(0.0f, in_fHeightMargin);
	stTerrain.nHeightLog2Pages = nLog2Tiles;
	stTerrain.nHeightTileSize = nTileSize;
}

void RendererSceneCull::GpuDrivenTerrainSetEnabled(RID ridTerrain, bool in_bEnabled)
{
	MutexLock lockTerrains(mtxGpuDrivenTerrainMutex);
	ERR_FAIL_COND(!stGpuDrivenTerrainOwner.owns(ridTerrain));
	mapGpuDrivenTerrains[ridTerrain].bEnabled = in_bEnabled;
}
#pragma endregion
