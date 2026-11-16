/**************************************************************************/
/*  RenderPipeline.cpp                                                    */
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

#include "engine_next/Rendering/RenderPipeline.h"

#include <cstddef>
#include <utility>

namespace EngineNext::Rendering
{

namespace
{

bool AddPipelinePass(FrameGraph &stGraph, RenderPipeline &stPipeline, const PassDesc &stDescription, PassWork eWork, GraphDiagnostic &out_stDiagnostic)
{
	const PassId nPass = stGraph.AddPass(stDescription);
	if (nPass == INVALID_PASS)
	{
		out_stDiagnostic = { GraphError::InvalidPass, INVALID_PASS, INVALID_RESOURCE, "Render pipeline pass declaration failed." };
		return false;
	}
	stPipeline.arrWorkByPass.resize(static_cast<std::size_t>(nPass) + 1);
	stPipeline.arrWorkByPass[nPass] = eWork;
	return true;
}

} // namespace

bool BuildRenderPipeline(bool bSceneMode, RenderPipeline &out_stPipeline, GraphDiagnostic &out_stDiagnostic, std::uint32_t nLocalShadowViews, bool bTemporal)
{
	if (nLocalShadowViews > 28)
	{
		out_stDiagnostic = { GraphError::CapacityExceeded, INVALID_PASS, INVALID_RESOURCE, "Local shadow view budget exceeded." };
		return false;
	}
	FrameGraph stGraph;
	RenderPipeline stPipeline;
	stPipeline.nTint = stGraph.AddResource({ "Tint", ResourceState::Common, true });
	stPipeline.nColor = stGraph.AddResource({ "Color", ResourceState::Common, false });
	stPipeline.nDepth = stGraph.AddResource({ "Depth", ResourceState::DepthWrite, true });
	stPipeline.nBackbuffer = stGraph.AddResource({ "Backbuffer", ResourceState::Present, true });
	if (!AddPipelinePass(stGraph, stPipeline, { "ComputeTint", QueueType::Compute, { { stPipeline.nTint, ResourceState::UnorderedAccess, true } }, {} }, PassWork::ComputeTint, out_stDiagnostic))
	{
		return false;
	}
	if (bSceneMode)
	{
		stPipeline.nDirectionalShadow = stGraph.AddResource({ "DirectionalShadow", ResourceState::DepthWrite, true, 4 });
		if (!AddPipelinePass(stGraph, stPipeline, { "DirectionalShadow", QueueType::Graphics, { { stPipeline.nDirectionalShadow, ResourceState::DepthWrite, true } }, {} }, PassWork::DirectionalShadow, out_stDiagnostic))
		{
			return false;
		}
		stPipeline.nLocalShadow = stGraph.AddResource({ "LocalShadow", ResourceState::DepthWrite, true, nLocalShadowViews == 0 ? 1U : nLocalShadowViews });
		if (!AddPipelinePass(stGraph, stPipeline, { "LocalShadow", QueueType::Graphics, { { stPipeline.nLocalShadow, ResourceState::DepthWrite, true } }, {} }, PassWork::LocalShadow, out_stDiagnostic))
		{
			return false;
		}
		stPipeline.arrGbuffer[0] = stGraph.AddResource({ "GBufferBase", ResourceState::Common, false });
		stPipeline.arrGbuffer[1] = stGraph.AddResource({ "GBufferNormal", ResourceState::Common, false });
		stPipeline.arrGbuffer[2] = stGraph.AddResource({ "GBufferSurface", ResourceState::Common, false });
		stPipeline.arrGbuffer[3] = stGraph.AddResource({ "GBufferEmissive", ResourceState::Common, false });
		stPipeline.nHdr = stGraph.AddResource({ "HdrColor", ResourceState::Common, false });
		PassDesc stGbuffer{ "GBuffer", QueueType::Graphics, {}, {} };
		PassDesc stLighting{ "DeferredLighting", QueueType::Graphics, { { stPipeline.nTint, ResourceState::ShaderRead, false } }, {} };
		for (ResourceId nResource : stPipeline.arrGbuffer)
		{
			stGbuffer.arrAccesses.push_back({ nResource, ResourceState::RenderTarget, true });
			stLighting.arrAccesses.push_back({ nResource, ResourceState::ShaderRead, false });
		}
		stPipeline.nMotion = stGraph.AddResource({ "Motion", ResourceState::Common, false });
		stPipeline.nObjectId = stGraph.AddResource({ "ObjectId", ResourceState::Common, false });
		stGbuffer.arrAccesses.push_back({ stPipeline.nMotion, ResourceState::RenderTarget, true });
		stGbuffer.arrAccesses.push_back({ stPipeline.nObjectId, ResourceState::RenderTarget, true });
		stGbuffer.arrAccesses.push_back({ stPipeline.nDepth, ResourceState::DepthWrite, true });
		stLighting.arrAccesses.push_back({ stPipeline.nDepth, ResourceState::DepthRead, false });
		stLighting.arrAccesses.push_back({ stPipeline.nHdr, ResourceState::RenderTarget, true });
		stLighting.arrAccesses.push_back({ stPipeline.nDirectionalShadow, ResourceState::ShaderRead, false });
		stLighting.arrAccesses.push_back({ stPipeline.nLocalShadow, ResourceState::ShaderRead, false });
		if (!AddPipelinePass(stGraph, stPipeline, stGbuffer, PassWork::GBuffer, out_stDiagnostic) ||
			!AddPipelinePass(stGraph, stPipeline, stLighting, PassWork::DeferredLighting, out_stDiagnostic))
		{
			return false;
		}
		ResourceId nToneMapSource = stPipeline.nHdr;
		if (bTemporal)
		{
			const std::array<const char *, 4> arrReadNames{ "HistoryReadColor", "HistoryReadDepth", "HistoryReadNormal", "HistoryReadObjectId" };
			const std::array<const char *, 4> arrWriteNames{ "HistoryWriteColor", "HistoryWriteDepth", "HistoryWriteNormal", "HistoryWriteObjectId" };
			PassDesc stTemporal{ "TemporalResolve", QueueType::Graphics, { { stPipeline.nHdr, ResourceState::NonPixelShaderRead, false }, { stPipeline.nDepth, ResourceState::DepthRead, false }, { stPipeline.arrGbuffer[1], ResourceState::NonPixelShaderRead, false }, { stPipeline.nMotion, ResourceState::NonPixelShaderRead, false }, { stPipeline.nObjectId, ResourceState::NonPixelShaderRead, false } }, {} };
			for (std::size_t nHistory = 0; nHistory < stPipeline.arrHistoryRead.size(); ++nHistory)
			{
				stPipeline.arrHistoryRead[nHistory] = stGraph.AddResource({ arrReadNames[nHistory], ResourceState::Common, true });
				stPipeline.arrHistoryWrite[nHistory] = stGraph.AddResource({ arrWriteNames[nHistory], ResourceState::Common, true });
				stTemporal.arrAccesses.push_back({ stPipeline.arrHistoryRead[nHistory], ResourceState::NonPixelShaderRead, false });
				stTemporal.arrAccesses.push_back({ stPipeline.arrHistoryWrite[nHistory], ResourceState::UnorderedAccess, true });
			}
			if (!AddPipelinePass(stGraph, stPipeline, stTemporal, PassWork::TemporalResolve, out_stDiagnostic))
			{
				return false;
			}
			nToneMapSource = stPipeline.arrHistoryWrite[0];
		}
		if (!AddPipelinePass(stGraph, stPipeline, { "ToneMap", QueueType::Graphics, { { nToneMapSource, ResourceState::ShaderRead, false }, { stPipeline.nColor, ResourceState::RenderTarget, true } }, {} }, PassWork::ToneMap, out_stDiagnostic))
		{
			return false;
		}
	}
	else if (!AddPipelinePass(stGraph, stPipeline, { "FixedMesh", QueueType::Graphics, { { stPipeline.nTint, ResourceState::ShaderRead, false }, { stPipeline.nColor, ResourceState::RenderTarget, true }, { stPipeline.nDepth, ResourceState::DepthWrite, true } }, {} }, PassWork::FixedMesh, out_stDiagnostic))
	{
		return false;
	}
	if (!AddPipelinePass(stGraph, stPipeline, { "CopyToBackbuffer", QueueType::Graphics, { { stPipeline.nColor, ResourceState::CopySource, false }, { stPipeline.nBackbuffer, ResourceState::CopyDestination, true } }, {} }, PassWork::CopyToBackbuffer, out_stDiagnostic))
	{
		return false;
	}
	PassDesc stPresent{ "Present", QueueType::Graphics, { { stPipeline.nTint, ResourceState::Common, false }, { stPipeline.nColor, ResourceState::Common, false }, { stPipeline.nBackbuffer, ResourceState::Present, false } }, {} };
	if (bSceneMode)
	{
		stPresent.arrAccesses.push_back({ stPipeline.nDepth, ResourceState::DepthWrite, true, 0, ALL_SUBRESOURCES, true });
		stPresent.arrAccesses.push_back({ stPipeline.nHdr, ResourceState::Common, false });
		stPresent.arrAccesses.push_back({ stPipeline.nDirectionalShadow, ResourceState::DepthWrite, true, 0, ALL_SUBRESOURCES, true });
		stPresent.arrAccesses.push_back({ stPipeline.nLocalShadow, ResourceState::DepthWrite, true, 0, ALL_SUBRESOURCES, true });
		for (ResourceId nResource : stPipeline.arrGbuffer)
		{
			stPresent.arrAccesses.push_back({ nResource, ResourceState::Common, false });
		}
		stPresent.arrAccesses.push_back({ stPipeline.nMotion, ResourceState::Common, false });
		stPresent.arrAccesses.push_back({ stPipeline.nObjectId, ResourceState::Common, false });
		if (bTemporal)
		{
			for (std::size_t nHistory = 0; nHistory < stPipeline.arrHistoryRead.size(); ++nHistory)
			{
				stPresent.arrAccesses.push_back({ stPipeline.arrHistoryRead[nHistory], ResourceState::Common, false });
				stPresent.arrAccesses.push_back({ stPipeline.arrHistoryWrite[nHistory], ResourceState::Common, false });
			}
		}
	}
	if (!AddPipelinePass(stGraph, stPipeline, stPresent, PassWork::Present, out_stDiagnostic) || !stGraph.Compile(stPipeline.stGraph, out_stDiagnostic))
	{
		return false;
	}
	for (const CompiledPass &stPass : stPipeline.stGraph.arrPasses)
	{
		stPipeline.nGraphicsPassCount += stPass.eQueue == QueueType::Graphics ? 1U : 0U;
		stPipeline.nComputePassCount += stPass.eQueue == QueueType::Compute ? 1U : 0U;
	}
	out_stPipeline = std::move(stPipeline);
	return true;
}

} // namespace EngineNext::Rendering
