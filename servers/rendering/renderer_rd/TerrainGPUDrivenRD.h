/**************************************************************************/
/*  TerrainGPUDrivenRD.h                                                 */
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

#pragma once

#include "servers/rendering/rendering_method.h"
#include "servers/rendering/renderer_geometry_instance.h"
#include "core/templates/paged_array.h"
#include "servers/rendering/renderer_rd/shaders/terrain_cull.glsl.gen.h"
#include "servers/rendering/renderer_rd/shaders/terrain_cull_finalize.glsl.gen.h"

namespace RendererRD
{

class TerrainGPUDrivenRD
{
	TerrainCullShaderRD stCullShader;
	TerrainCullFinalizeShaderRD stFinalizeShader;
	RID ridCullVersion;
	RID ridFinalizeVersion;
	RID arrCullPipelines[2];
	RID arrFinalizePipelines[2];
	RID ridCullSampler;
	struct Work
	{
		RID ridCompaction;
		RID ridFeedback;
		RID ridConfiguration;
		uint32_t nCompactionBytes = 0;
		uint32_t nFeedbackBytes = 0;
		uint64_t nViewSerial = 0;
	};
	HashMap<RID, Work> mapWork;
	uint64_t nViewSerial = 0;
	uint32_t nCameraLayers = 0;
	RID ridViewport;
	Projection projColorVp;
	Vector3 vCameraPosition;
	float fProjectionScale = 1.0f;
	bool bShadowCut = false;
	LocalVector<uint64_t> arrMainBuffers;

	void Release(Work &out_stWork);
	void Dispatch(RID in_ridId, const RenderingMethod::GPUTerrain &stTerrain, const Projection &projCullVp, uint32_t nClipMode);
	void SelectPass(const Projection &projVp, uint32_t nClipMode, const LocalVector<uint64_t> &arrBuffers, bool bColor);
	static void SubmitFeedback(const Vector<uint8_t> &arrData, RID in_ridHeightVt, RID in_ridViewport, int nLog2Tiles);

public:
	TerrainGPUDrivenRD();
	~TerrainGPUDrivenRD();
	void BeginView(RID in_ridViewport, uint32_t nLayers, const Projection &projProjection, const Transform3D &xformCamera,
				   const PagedArray<RenderGeometryInstance *> *pInstances);
	void GatherBuffers(const PagedArray<RenderGeometryInstance *> &arrInstances, LocalVector<uint64_t> &out_arrBuffers) const;
	void SelectShadow(const Projection &projVp, bool bPancake, bool bDualParaboloid, const LocalVector<uint64_t> &arrBuffers);
	void EndShadows();
};

} // namespace RendererRD
