/**************************************************************************/
/*  TestRenderPipeline.cpp                                                */
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

#include "engine_next/Tests/TestFramework.h"

#include "engine_next/Rendering/RenderPipeline.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace
{

using EngineNext::Rendering::BuildRenderPipeline;
using EngineNext::Rendering::CompiledPass;
using EngineNext::Rendering::CompiledResource;
using EngineNext::Rendering::GraphDiagnostic;
using EngineNext::Rendering::GraphError;
using EngineNext::Rendering::PassId;
using EngineNext::Rendering::PassWork;
using EngineNext::Rendering::QueueType;
using EngineNext::Rendering::RenderPipeline;
using EngineNext::Rendering::ResourceBarrier;
using EngineNext::Rendering::ResourceId;
using EngineNext::Rendering::ResourceState;

bool HasTransition(const CompiledPass &stPass, ResourceId nResource, ResourceState eBefore, ResourceState eAfter)
{
	for (const ResourceBarrier &stBarrier : stPass.arrBeforeBarriers)
	{
		if (stBarrier.nResource == nResource && stBarrier.eBefore == eBefore && stBarrier.eAfter == eAfter)
		{
			return true;
		}
	}
	return false;
}

void CheckReusableStates(const RenderPipeline &stPipeline)
{
	for (const CompiledResource &stResource : stPipeline.stGraph.arrResources)
	{
		ENGINE_NEXT_CHECK_EQ(stResource.arrFinalStates.size(), stResource.stDescription.nSubresourceCount);
		for (ResourceState eState : stResource.arrFinalStates)
		{
			ENGINE_NEXT_CHECK_EQ(eState, stResource.stDescription.eInitialState);
		}
	}
}

} // namespace

ENGINE_NEXT_TEST("RenderPipeline preserves the fixed mesh compute and graphics plan")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::None);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, 3U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nComputePassCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nHdr, EngineNext::Rendering::INVALID_RESOURCE);
	for (ResourceId nResource : stPipeline.arrGbuffer)
	{
		ENGINE_NEXT_CHECK_EQ(nResource, EngineNext::Rendering::INVALID_RESOURCE);
	}
	const std::array<PassWork, 4> arrWork{ PassWork::ComputeTint, PassWork::FixedMesh, PassWork::CopyToBackbuffer, PassWork::Present };
	const std::array<const char *, 4> arrNames{ "ComputeTint", "FixedMesh", "CopyToBackbuffer", "Present" };
	for (std::size_t nIndex = 0; nIndex < arrWork.size(); ++nIndex)
	{
		const CompiledPass &stPass = stPipeline.stGraph.arrPasses[nIndex];
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass[stPass.nPass], arrWork[nIndex]);
		ENGINE_NEXT_CHECK_EQ(stPass.strName, arrNames[nIndex]);
		ENGINE_NEXT_CHECK_EQ(stPass.eQueue, nIndex == 0 ? QueueType::Compute : QueueType::Graphics);
	}
	const CompiledPass &stCompute = stPipeline.stGraph.arrPasses[0];
	const CompiledPass &stMesh = stPipeline.stGraph.arrPasses[1];
	ENGINE_NEXT_CHECK(stCompute.bSignalRequired);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrWaits, std::vector<PassId>{ stCompute.nPass });
	ENGINE_NEXT_CHECK(HasTransition(stMesh, stPipeline.nTint, ResourceState::Common, ResourceState::ShaderRead));
	ENGINE_NEXT_CHECK(HasTransition(stPipeline.stGraph.arrPasses[2], stPipeline.nColor, ResourceState::RenderTarget, ResourceState::CopySource));
	ENGINE_NEXT_CHECK(HasTransition(stPipeline.stGraph.arrPasses[3], stPipeline.nBackbuffer, ResourceState::CopyDestination, ResourceState::Present));
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline separates deferred HDR lighting from tone mapping")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 8U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 11U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, 7U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nComputePassCount, 1U);
	ENGINE_NEXT_CHECK(stPipeline.nHdr != stPipeline.nColor);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[stPipeline.nHdr].stDescription.strName, "HdrColor");
	const std::array<PassWork, 8> arrWork{ PassWork::ComputeTint, PassWork::DirectionalShadow, PassWork::LocalShadow, PassWork::GBuffer, PassWork::DeferredLighting, PassWork::ToneMap, PassWork::CopyToBackbuffer, PassWork::Present };
	const std::array<const char *, 8> arrNames{ "ComputeTint", "DirectionalShadow", "LocalShadow", "GBuffer", "DeferredLighting", "ToneMap", "CopyToBackbuffer", "Present" };
	for (std::size_t nIndex = 0; nIndex < arrWork.size(); ++nIndex)
	{
		const CompiledPass &stPass = stPipeline.stGraph.arrPasses[nIndex];
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass[stPass.nPass], arrWork[nIndex]);
		ENGINE_NEXT_CHECK_EQ(stPass.strName, arrNames[nIndex]);
		ENGINE_NEXT_CHECK_EQ(stPass.eQueue, nIndex == 0 ? QueueType::Compute : QueueType::Graphics);
	}
	const CompiledPass &stCompute = stPipeline.stGraph.arrPasses[0];
	const CompiledPass &stGbuffer = stPipeline.stGraph.arrPasses[3];
	const CompiledPass &stLighting = stPipeline.stGraph.arrPasses[4];
	const CompiledPass &stToneMap = stPipeline.stGraph.arrPasses[5];
	ENGINE_NEXT_CHECK(stCompute.bSignalRequired);
	ENGINE_NEXT_CHECK(stGbuffer.arrWaits.empty());
	ENGINE_NEXT_CHECK_EQ(stLighting.arrWaits, std::vector<PassId>{ stCompute.nPass });
	ENGINE_NEXT_CHECK_EQ(stLighting.arrAccesses.back().nResource, stPipeline.nLocalShadow);
	ENGINE_NEXT_CHECK_EQ(stLighting.arrAccesses.back().eState, ResourceState::ShaderRead);
	ENGINE_NEXT_CHECK(HasTransition(stLighting, stPipeline.nDepth, ResourceState::DepthWrite, ResourceState::DepthRead));
	for (ResourceId nResource : stPipeline.arrGbuffer)
	{
		ENGINE_NEXT_CHECK(HasTransition(stGbuffer, nResource, ResourceState::Common, ResourceState::RenderTarget));
		ENGINE_NEXT_CHECK(HasTransition(stLighting, nResource, ResourceState::RenderTarget, ResourceState::ShaderRead));
	}
	ENGINE_NEXT_CHECK(HasTransition(stToneMap, stPipeline.nHdr, ResourceState::RenderTarget, ResourceState::ShaderRead));
	ENGINE_NEXT_CHECK(HasTransition(stToneMap, stPipeline.nColor, ResourceState::Common, ResourceState::RenderTarget));
	ENGINE_NEXT_CHECK(HasTransition(stPipeline.stGraph.arrPasses[6], stPipeline.nColor, ResourceState::RenderTarget, ResourceState::CopySource));
	ENGINE_NEXT_CHECK(HasTransition(stPipeline.stGraph.arrPasses[7], stPipeline.nDepth, ResourceState::DepthRead, ResourceState::DepthWrite));
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline rebuild replaces owned scene resources and pass mappings")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nHdr, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass[1], PassWork::FixedMesh);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, 3U);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass.size(), 8U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass[1], PassWork::DirectionalShadow);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, 7U);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline bounds local shadow slices and preserves the fixed mesh plan")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	for (std::uint32_t nViews : { 0U, 6U, 28U })
	{
		ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, nViews));
		const CompiledResource &stLocal = stPipeline.stGraph.arrResources[stPipeline.nLocalShadow];
		ENGINE_NEXT_CHECK_EQ(stLocal.stDescription.nSubresourceCount, nViews == 0 ? 1U : nViews);
		ENGINE_NEXT_CHECK_EQ(stLocal.stDescription.eInitialState, ResourceState::DepthWrite);
		CheckReusableStates(stPipeline);
	}
	const ResourceId nLocalShadow = stPipeline.nLocalShadow;
	const std::vector<PassWork> arrWork = stPipeline.arrWorkByPass;
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 29));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::CapacityExceeded);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nLocalShadow, nLocalShadow);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, arrWork);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[nLocalShadow].stDescription.nSubresourceCount, 28U);
	CheckReusableStates(stPipeline);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 28));
	ENGINE_NEXT_CHECK_EQ(stPipeline.nLocalShadow, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, (std::vector<PassWork>{ PassWork::ComputeTint, PassWork::FixedMesh, PassWork::CopyToBackbuffer, PassWork::Present }));
	CheckReusableStates(stPipeline);
}
