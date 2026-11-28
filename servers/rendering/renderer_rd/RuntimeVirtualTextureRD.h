/**************************************************************************/
/*  RuntimeVirtualTextureRD.h                                            */
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

#pragma region Engine ZXB
// [ZXB] RenderingDevice backend of Runtime Virtual Texture: physical page pool, page table texture,
// and page rendering through the material pass (same pass used by VoxelGI).
#pragma endregion

#include "core/templates/rid_owner.h"
#include "servers/rendering/renderer_rd/shaders/terrain_material_feedback.glsl.gen.h"
#include "servers/rendering/renderer_rd/shaders/terrain_height_page.glsl.gen.h"
#include "servers/rendering/renderer_rd/shaders/runtime_virtual_texture_compose.glsl.gen.h"
#include "servers/rendering/renderer_scene_render.h"
#include "servers/rendering/rendering_device.h"

namespace RendererRD
{

class RuntimeVirtualTextureRD
{
public:
	using Config = RendererSceneRender::RuntimeVirtualTextureGPUConfig;

private:
	struct ComposePushConstant
	{
		int32_t arrDstOffset[2];
		int32_t arrSize[2];
		float fHeightScale;
		int32_t nFlipY;
		float arrPad[2];
	};

	struct GPU
	{
		Config stConfig;
		uint32_t nStride = 0; // tile_size + 2 * tile_border.
		uint32_t nLayerCount = 1;
		bool bStreaming = false;
		RD::DataFormat ePoolFormat = RD::DATA_FORMAT_R8G8B8A8_UNORM;
		RID ridRegionBuffer;
		uint64_t nRegionRevision = 0;
		RID ridSurfaceStaging;
		RID ridFeedbackFilter;
		Basis basisFeedbackFilterBasis;
		Vector4 vFeedbackFilterLimits;
		RID ridStaging; // Streaming uploads: tile sized texture copied into the pool region.

		RID ridPageTable;
		RID arrPhysical[2];

		RID ridAlbedo;
		RID ridNormal;
		RID ridOrm;
		RID ridEmission;
		RID ridDepth;
		RID ridDepthStencil;
		RID ridFramebuffer;
		RID ridComposeInputs;
		RID ridComposeOutputs;
	};

	RendererSceneRender *pSceneRender = nullptr;
	RID_Owner<GPU, true> stOwner;

	TerrainMaterialFeedbackShaderRD stFeedbackShader;
	RID ridFeedbackVersion;
	RID arrFeedbackPipelines[4];
	RID ridFeedbackBuffer;
	uint32_t nFeedbackCapacity = 0;
	static void DeliverFeedback(const Vector<uint8_t> &in_arrData, RID ridSurface, RID ridViewport, uint64_t nRevision);

	TerrainHeightPageShaderRD stHeightShader;
	RID ridHeightVersion;
	RID ridHeightPipeline;
	RuntimeVirtualTextureComposeShaderRD stComposeShader;
	RID ridComposeVersion;
	RID arrComposePipelines[RSE::RVT_MATERIAL_MAX];
	RID ridNearestSampler;

	static void PublishTexture(RID ridGodotTexture, RID ridRdTexture);
	void FreeGpu(GPU *in_pGpu);

public:
	RID Create(const Config &in_stConfig, RID ridPageTableTexture, RID ridPhysicalTexture0, RID ridPhysicalTexture1);
	void Free(RID ridGpu);
	void UpdatePageTable(RID ridGpu, const LocalVector<Vector<uint8_t>> &arrLevels);
	void RenderPage(RID ridGpu, const Transform3D &xformCamera, const Projection &projProjection, const PagedArray<RenderGeometryInstance *> &arrInstances, uint32_t nPoolX, uint32_t nPoolY, float fVolumeHeight);
	void CollectFeedback(RID ridSurface, RID ridViewport, const Transform3D &xformVolume, uint32_t nLog2Tiles, uint32_t in_nTileSize, int nMaxAnisotropy, float in_fLodBias, const Vector4 &vLimits, uint64_t in_nRevision, RID ridGpu, const Ref<RenderSceneBuffers> &in_refBuffers, const RendererSceneRender::CameraData &stCamera);
	bool DrawHeight(RID ridGpu, const RendererSceneRender::HeightGrid &in_stSource, const Vector2i &vPage, uint32_t nLevel, const Vector2i &vSlot);
	Vector<uint8_t> ReadMaterialTile(RID ridGpu);
	void UploadPage(RID ridGpu, uint32_t nPoolX, uint32_t nPoolY, const Vector<uint8_t> &in_arrData);
	bool Owns(RID ridGpu) const
	{
		return stOwner.owns(ridGpu);
	}

	RuntimeVirtualTextureRD(RendererSceneRender *in_pSceneRender);
	~RuntimeVirtualTextureRD();
};

} // namespace RendererRD
