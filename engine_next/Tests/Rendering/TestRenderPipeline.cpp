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

const CompiledPass *FindWork(const RenderPipeline &stPipeline, PassWork eWork, std::uint32_t nMip = EngineNext::Rendering::INVALID_RESOURCE)
{
	for (const CompiledPass &stPass : stPipeline.stGraph.arrPasses)
	{
		if (stPipeline.arrWorkByPass[stPass.nPass] == eWork && stPipeline.arrPassMipIndex[stPass.nPass] == nMip)
		{
			return &stPass;
		}
	}
	return nullptr;
}

bool HasAccess(const CompiledPass &stPass, ResourceId nResource, ResourceState eState, bool bWrite)
{
	for (const EngineNext::Rendering::ResourceAccess &stAccess : stPass.arrAccesses)
	{
		if (stAccess.nResource == nResource && stAccess.eState == eState && stAccess.bWrite == bWrite)
		{
			return true;
		}
	}
	return false;
}

} // namespace

ENGINE_NEXT_TEST("Ray reflection graph separates lobe histories and preserves barriers")
{
	for (bool bGi : { false, true })
	{
		for (std::uint32_t nSpatial = 0; nSpatial <= 3; ++nSpatial)
		{
			RenderPipeline stPipeline;
			GraphDiagnostic stDiagnostic;
			ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 1, {}, true, bGi, {}, bGi, false, false, false, { true, nSpatial }));
			const CompiledPass *pTrace = FindWork(stPipeline, PassWork::RayReflectionTrace);
			const CompiledPass *pTemporal = FindWork(stPipeline, PassWork::RayReflectionTemporal);
			const CompiledPass *pComposite = FindWork(stPipeline, PassWork::RayReflectionComposite);
			const CompiledPass *pReadback = FindWork(stPipeline, PassWork::RayReflectionReadback);
			ENGINE_NEXT_CHECK(pTrace != nullptr && pTemporal != nullptr && pComposite != nullptr && pReadback != nullptr);
			ENGINE_NEXT_CHECK(pTrace->nPass < pTemporal->nPass && pTemporal->nPass < pComposite->nPass && pComposite->nPass < pReadback->nPass);
			ENGINE_NEXT_CHECK((FindWork(stPipeline, PassWork::RayReflectionBuildScene) == nullptr) == bGi);
			ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::ReflectionTrace) == nullptr);
			ENGINE_NEXT_CHECK(HasAccess(*pTrace, stPipeline.nRayScene, ResourceState::AccelerationStructure, false));
			for (std::uint32_t nImage = 0; nImage < 7; ++nImage)
			{
				ENGINE_NEXT_CHECK(stPipeline.arrRayHistoryRead[nImage] != stPipeline.arrRayHistoryWrite[nImage]);
				ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.arrRayHistoryRead[nImage], ResourceState::NonPixelShaderRead, false));
				ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.arrRayHistoryWrite[nImage], ResourceState::UnorderedAccess, true));
			}
			for (std::uint32_t nIndex = 0; nIndex < 3; ++nIndex)
			{
				ENGINE_NEXT_CHECK((FindWork(stPipeline, PassWork::RayReflectionSpatial, nIndex) != nullptr) == (nIndex < nSpatial));
			}
			CheckReusableStates(stPipeline);
		}
	}
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 0, {}, true, true, {}, false, false, false, false, { true, 1 }));
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 1, {}, false, true, {}, false, false, false, false, { true, 1 }));
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 1, {}, true, true, {}, false, false, false, false, { true, 4 }));
}

ENGINE_NEXT_TEST("Ray reflection graph retains animated raster and shared scene ordering")
{
	for (bool bGi : { false, true })
	{
		RenderPipeline stPipeline;
		GraphDiagnostic stDiagnostic;
		ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 1, {}, true, bGi, {}, bGi, true, true, false, { true, 2 }));
		const CompiledPass *pUpload = FindWork(stPipeline, PassWork::DeformationUpload);
		const CompiledPass *pGbuffer = FindWork(stPipeline, PassWork::GBuffer);
		const CompiledPass *pTrace = FindWork(stPipeline, PassWork::RayReflectionTrace);
		const CompiledPass *pReadback = FindWork(stPipeline, PassWork::RayReflectionReadback);
		ENGINE_NEXT_CHECK(pUpload != nullptr && pGbuffer != nullptr && pTrace != nullptr && pReadback != nullptr);
		ENGINE_NEXT_CHECK(pUpload->nPass < pGbuffer->nPass && pGbuffer->nPass < pTrace->nPass && pTrace->nPass < pReadback->nPass);
		ENGINE_NEXT_CHECK(HasAccess(*pGbuffer, stPipeline.nDeformedVertices, ResourceState::VertexIndexRead, false));
		if (bGi)
		{
			const CompiledPass *pGiReadback = FindWork(stPipeline, PassWork::GiReadback);
			ENGINE_NEXT_CHECK(pGiReadback != nullptr && pGiReadback->nPass < pTrace->nPass);
			ENGINE_NEXT_CHECK(stPipeline.nRayScene == stPipeline.nGiScene);
		}
		CheckReusableStates(stPipeline);
	}
}

ENGINE_NEXT_TEST("RenderPipeline orders probe remapping tracing integration and receivers")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 6, true, true, 3, 6, { true, true }, true, true));
	const std::array<PassWork, 7> arrGiWork{ PassWork::GiBuildScene, PassWork::GiUpload, PassWork::GiPrepare,
											 PassWork::GiRemap, PassWork::GiTrace, PassWork::GiUpdate, PassWork::GiReadback };
	PassId nPrevious = 0;
	for (PassWork eWork : arrGiWork)
	{
		const CompiledPass *pPass = FindWork(stPipeline, eWork);
		ENGINE_NEXT_CHECK(pPass != nullptr);
		if (pPass == nullptr)
		{
			return;
		}
		ENGINE_NEXT_CHECK(pPass->nPass > nPrevious);
		nPrevious = pPass->nPass;
		ENGINE_NEXT_CHECK_EQ(pPass->eQueue, QueueType::Graphics);
	}
	const CompiledPass *pTrace = FindWork(stPipeline, PassWork::GiTrace);
	const CompiledPass *pUpdate = FindWork(stPipeline, PassWork::GiUpdate);
	const CompiledPass *pLighting = FindWork(stPipeline, PassWork::DeferredLighting);
	const CompiledPass *pTransparency = FindWork(stPipeline, PassWork::Transparency);
	ENGINE_NEXT_CHECK(pTrace != nullptr && pUpdate != nullptr && pLighting != nullptr && pTransparency != nullptr);
	if (pTrace == nullptr || pUpdate == nullptr || pLighting == nullptr || pTransparency == nullptr)
	{
		return;
	}
	ENGINE_NEXT_CHECK(HasAccess(*pTrace, stPipeline.nGiScene, ResourceState::AccelerationStructure, false));
	for (std::size_t nKind = 0; nKind < stPipeline.arrGiWrite.size(); ++nKind)
	{
		ENGINE_NEXT_CHECK(HasAccess(*pTrace, stPipeline.arrGiWrite[nKind], ResourceState::NonPixelShaderRead, false));
		ENGINE_NEXT_CHECK(HasAccess(*pUpdate, stPipeline.arrGiRead[nKind], ResourceState::NonPixelShaderRead, false));
		ENGINE_NEXT_CHECK(HasAccess(*pUpdate, stPipeline.arrGiWrite[nKind], ResourceState::UnorderedAccess, true));
		ENGINE_NEXT_CHECK(HasAccess(*pLighting, stPipeline.arrGiWrite[nKind], ResourceState::ShaderRead, false));
		ENGINE_NEXT_CHECK(HasAccess(*pTransparency, stPipeline.arrGiWrite[nKind], ResourceState::ShaderRead, false));
	}
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("Paged geometry ray reflections and screen effects preserve their combined graph")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 6, true, true, 6, 6,
										  { true, true }, true, true, { true, true, 8, true }, true, true, false, true, { true, 2 }));
	const CompiledPass *pUpload = FindWork(stPipeline, PassWork::GeometryUpload);
	const CompiledPass *pGbuffer = FindWork(stPipeline, PassWork::GBuffer);
	const CompiledPass *pRay = FindWork(stPipeline, PassWork::RayReflectionComposite);
	const CompiledPass *pForward = FindWork(stPipeline, PassWork::Transparency);
	const CompiledPass *pTemporal = FindWork(stPipeline, PassWork::TemporalResolve);
	const CompiledPass *pTone = FindWork(stPipeline, PassWork::ToneMap);
	ENGINE_NEXT_CHECK(pUpload != nullptr && pGbuffer != nullptr && pRay != nullptr && pForward != nullptr && pTemporal != nullptr && pTone != nullptr);
	if (pUpload == nullptr || pGbuffer == nullptr || pRay == nullptr || pForward == nullptr || pTemporal == nullptr || pTone == nullptr)
	{
		return;
	}
	ENGINE_NEXT_CHECK(pUpload->nPass < pGbuffer->nPass && pGbuffer->nPass < pRay->nPass && pRay->nPass < pForward->nPass && pForward->nPass < pTemporal->nPass && pTemporal->nPass < pTone->nPass);
	ENGINE_NEXT_CHECK(HasAccess(*pTone, stPipeline.nColorLut, ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTone, stPipeline.arrHistoryWrite[0], ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(stPipeline.nRayScene == stPipeline.nGiScene);
	ENGINE_NEXT_CHECK(stPipeline.nGeometryPages != EngineNext::Rendering::INVALID_RESOURCE);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline ignores GI resources in fixed mesh mode")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 0, true, false, 0, 0, {}, false, true));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGiScene, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::GiTrace) == nullptr);
	CheckReusableStates(stPipeline);
}

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
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, false));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 8U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 13U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, 7U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nComputePassCount, 1U);
	ENGINE_NEXT_CHECK(stPipeline.nHdr != stPipeline.nColor);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[stPipeline.nHdr].stDescription.strName, "HdrColor");
	const std::array<PassWork, 8> arrWork{ PassWork::ComputeTint, PassWork::DirectionalShadow, PassWork::LocalShadow, PassWork::GBuffer,
										   PassWork::DeferredLighting, PassWork::ToneMap, PassWork::CopyToBackbuffer, PassWork::Present };
	const std::array<const char *, 8> arrNames{ "ComputeTint", "DirectionalShadow", "LocalShadow", "GBuffer",
												"DeferredLighting", "ToneMap", "CopyToBackbuffer", "Present" };
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
	for (ResourceId nResource : { stPipeline.nMotion, stPipeline.nObjectId })
	{
		ENGINE_NEXT_CHECK(HasTransition(stGbuffer, nResource, ResourceState::Common, ResourceState::RenderTarget));
		ENGINE_NEXT_CHECK(HasTransition(stPipeline.stGraph.arrPasses[7], nResource, ResourceState::RenderTarget, ResourceState::Common));
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
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, false));
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nHdr, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass[1], PassWork::FixedMesh);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, 3U);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, false));
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
		ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, nViews, false));
		const CompiledResource &stLocal = stPipeline.stGraph.arrResources[stPipeline.nLocalShadow];
		ENGINE_NEXT_CHECK_EQ(stLocal.stDescription.nSubresourceCount, nViews == 0 ? 1U : nViews);
		ENGINE_NEXT_CHECK_EQ(stLocal.stDescription.eInitialState, ResourceState::DepthWrite);
		CheckReusableStates(stPipeline);
	}
	const ResourceId nLocalShadow = stPipeline.nLocalShadow;
	const std::vector<PassWork> arrWork = stPipeline.arrWorkByPass;
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 29, false));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::CapacityExceeded);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nLocalShadow, nLocalShadow);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, arrWork);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[nLocalShadow].stDescription.nSubresourceCount, 28U);
	CheckReusableStates(stPipeline);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 28));
	ENGINE_NEXT_CHECK_EQ(stPipeline.nLocalShadow, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass,
						 (std::vector<PassWork>{ PassWork::ComputeTint, PassWork::FixedMesh, PassWork::CopyToBackbuffer, PassWork::Present }));
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline enables temporal history by default with graphics queue resolve")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::None);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 9U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 21U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, 8U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nComputePassCount, 1U);
	const std::array<PassWork, 9> arrWork{ PassWork::ComputeTint, PassWork::DirectionalShadow, PassWork::LocalShadow,
										   PassWork::GBuffer, PassWork::DeferredLighting, PassWork::TemporalResolve,
										   PassWork::ToneMap, PassWork::CopyToBackbuffer, PassWork::Present };
	for (std::size_t nIndex = 0; nIndex < arrWork.size(); ++nIndex)
	{
		const CompiledPass &stPass = stPipeline.stGraph.arrPasses[nIndex];
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass[stPass.nPass], arrWork[nIndex]);
		ENGINE_NEXT_CHECK_EQ(stPass.eQueue, nIndex == 0 ? QueueType::Compute : QueueType::Graphics);
	}
	const CompiledPass &stGbuffer = stPipeline.stGraph.arrPasses[3];
	const CompiledPass &stTemporal = stPipeline.stGraph.arrPasses[5];
	const CompiledPass &stToneMap = stPipeline.stGraph.arrPasses[6];
	ENGINE_NEXT_CHECK_EQ(stTemporal.strName, "TemporalResolve");
	ENGINE_NEXT_CHECK(stTemporal.arrWaits.empty());
	ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses.size(), 13U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses[4].arrWaits, std::vector<PassId>{ stPipeline.stGraph.arrPasses[0].nPass });
	ENGINE_NEXT_CHECK(HasTransition(stGbuffer, stPipeline.nMotion, ResourceState::Common, ResourceState::RenderTarget));
	ENGINE_NEXT_CHECK(HasTransition(stGbuffer, stPipeline.nObjectId, ResourceState::Common, ResourceState::RenderTarget));
	ENGINE_NEXT_CHECK(HasTransition(stTemporal, stPipeline.nMotion, ResourceState::RenderTarget, ResourceState::NonPixelShaderRead));
	ENGINE_NEXT_CHECK(HasTransition(stTemporal, stPipeline.nObjectId, ResourceState::RenderTarget, ResourceState::NonPixelShaderRead));
	ENGINE_NEXT_CHECK(HasTransition(stTemporal, stPipeline.nHdr, ResourceState::RenderTarget, ResourceState::NonPixelShaderRead));
	ENGINE_NEXT_CHECK(HasTransition(stTemporal, stPipeline.arrGbuffer[1], ResourceState::ShaderRead, ResourceState::NonPixelShaderRead));
	ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses[0].nResource, stPipeline.nHdr);
	ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses[1].nResource, stPipeline.nDepth);
	ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses[1].eState, ResourceState::DepthRead);
	ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses[2].nResource, stPipeline.arrGbuffer[1]);
	ENGINE_NEXT_CHECK_EQ(stToneMap.arrAccesses[0].nResource, stPipeline.arrHistoryWrite[0]);
	ENGINE_NEXT_CHECK(HasTransition(stToneMap, stPipeline.arrHistoryWrite[0], ResourceState::UnorderedAccess, ResourceState::ShaderRead));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[stPipeline.nMotion].nFirstPass, stGbuffer.nPass);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[stPipeline.nObjectId].nFirstPass, stGbuffer.nPass);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline keeps all temporal history reads and writes distinct and reusable")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 28, true));
	const CompiledPass &stTemporal = stPipeline.stGraph.arrPasses[5];
	const CompiledPass &stPresent = stPipeline.stGraph.arrPasses.back();
	const std::array<const char *, 4> arrReadNames{ "HistoryReadColor", "HistoryReadDepth", "HistoryReadNormal", "HistoryReadObjectId" };
	const std::array<const char *, 4> arrWriteNames{ "HistoryWriteColor", "HistoryWriteDepth", "HistoryWriteNormal", "HistoryWriteObjectId" };
	for (std::size_t nHistory = 0; nHistory < stPipeline.arrHistoryRead.size(); ++nHistory)
	{
		const ResourceId nRead = stPipeline.arrHistoryRead[nHistory];
		const ResourceId nWrite = stPipeline.arrHistoryWrite[nHistory];
		const CompiledResource &stRead = stPipeline.stGraph.arrResources[nRead];
		const CompiledResource &stWrite = stPipeline.stGraph.arrResources[nWrite];
		ENGINE_NEXT_CHECK(stRead.stDescription.bImported);
		ENGINE_NEXT_CHECK(stWrite.stDescription.bImported);
		ENGINE_NEXT_CHECK_EQ(stRead.stDescription.strName, arrReadNames[nHistory]);
		ENGINE_NEXT_CHECK_EQ(stWrite.stDescription.strName, arrWriteNames[nHistory]);
		ENGINE_NEXT_CHECK_EQ(stRead.nFirstPass, stTemporal.nPass);
		ENGINE_NEXT_CHECK_EQ(stWrite.nFirstPass, stTemporal.nPass);
		ENGINE_NEXT_CHECK_EQ(stRead.nLastPass, stPresent.nPass);
		ENGINE_NEXT_CHECK_EQ(stWrite.nLastPass, stPresent.nPass);
		ENGINE_NEXT_CHECK(HasTransition(stTemporal, nRead, ResourceState::Common, ResourceState::NonPixelShaderRead));
		ENGINE_NEXT_CHECK(HasTransition(stTemporal, nWrite, ResourceState::Common, ResourceState::UnorderedAccess));
		ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses[5 + nHistory * 2].nResource, nRead);
		ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses[5 + nHistory * 2].eState, ResourceState::NonPixelShaderRead);
		ENGINE_NEXT_CHECK(!stTemporal.arrAccesses[5 + nHistory * 2].bWrite);
		ENGINE_NEXT_CHECK_EQ(stTemporal.arrAccesses[6 + nHistory * 2].nResource, nWrite);
		ENGINE_NEXT_CHECK(stTemporal.arrAccesses[6 + nHistory * 2].bWrite);
		ENGINE_NEXT_CHECK(!stTemporal.arrAccesses[6 + nHistory * 2].bReadBeforeWrite);
		for (std::size_t nOther = 0; nOther < stPipeline.arrHistoryRead.size(); ++nOther)
		{
			ENGINE_NEXT_CHECK(nRead != stPipeline.arrHistoryWrite[nOther]);
			if (nHistory != nOther)
			{
				ENGINE_NEXT_CHECK(nRead != stPipeline.arrHistoryRead[nOther]);
				ENGINE_NEXT_CHECK(nWrite != stPipeline.arrHistoryWrite[nOther]);
			}
		}
	}
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[stPipeline.nLocalShadow].stDescription.nSubresourceCount, 28U);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline toggles temporal resources without retaining history or changing fixed mode")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 7));
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 7, false));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 8U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 13U);
	ENGINE_NEXT_CHECK(stPipeline.nMotion != EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(stPipeline.nObjectId != EngineNext::Rendering::INVALID_RESOURCE);
	for (std::size_t nHistory = 0; nHistory < stPipeline.arrHistoryRead.size(); ++nHistory)
	{
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrHistoryRead[nHistory], EngineNext::Rendering::INVALID_RESOURCE);
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrHistoryWrite[nHistory], EngineNext::Rendering::INVALID_RESOURCE);
	}
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses[5].arrAccesses[0].nResource, stPipeline.nHdr);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 7, true));
	const std::vector<PassWork> arrSavedWork = stPipeline.arrWorkByPass;
	const ResourceId nSavedHistory = stPipeline.arrHistoryRead[0];
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 29, true));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::CapacityExceeded);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, arrSavedWork);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrHistoryRead[0], nSavedHistory);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 9U);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 28, true));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nMotion, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nObjectId, EngineNext::Rendering::INVALID_RESOURCE);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline prepares exposure before geometry and meters resolved HDR")
{
	for (bool bTemporal : { false, true })
	{
		RenderPipeline stPipeline;
		GraphDiagnostic stDiagnostic;
		ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 28, bTemporal, true));
		ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), bTemporal ? 13U : 12U);
		ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), bTemporal ? 25U : 17U);
		ENGINE_NEXT_CHECK_EQ(stPipeline.nComputePassCount, 1U);
		ENGINE_NEXT_CHECK_EQ(stPipeline.nGraphicsPassCount, bTemporal ? 12U : 11U);
		const CompiledPass *pPrepare = FindWork(stPipeline, PassWork::PrepareExposure);
		const CompiledPass *pGeometry = FindWork(stPipeline, PassWork::GBuffer);
		const CompiledPass *pLighting = FindWork(stPipeline, PassWork::DeferredLighting);
		const CompiledPass *pBuild = FindWork(stPipeline, PassWork::HistogramBuild);
		const CompiledPass *pAdapt = FindWork(stPipeline, PassWork::ExposureAdapt);
		const CompiledPass *pTone = FindWork(stPipeline, PassWork::ToneMap);
		ENGINE_NEXT_CHECK(pPrepare != nullptr && pGeometry != nullptr && pLighting != nullptr && pBuild != nullptr && pAdapt != nullptr && pTone != nullptr);
		if (pPrepare == nullptr || pGeometry == nullptr || pLighting == nullptr || pBuild == nullptr || pAdapt == nullptr || pTone == nullptr)
		{
			continue;
		}
		ENGINE_NEXT_CHECK(pPrepare->nPass < pGeometry->nPass);
		ENGINE_NEXT_CHECK(pLighting->nPass < pBuild->nPass);
		ENGINE_NEXT_CHECK(pBuild->nPass < pAdapt->nPass && pAdapt->nPass < pTone->nPass);
		ENGINE_NEXT_CHECK(HasAccess(*pPrepare, stPipeline.nExposureRead, ResourceState::UnorderedAccess, true));
		ENGINE_NEXT_CHECK(pPrepare->arrAccesses[0].bReadBeforeWrite);
		ENGINE_NEXT_CHECK(HasAccess(*pPrepare, stPipeline.nHistogram, ResourceState::UnorderedAccess, true));
		ENGINE_NEXT_CHECK(HasTransition(*pGeometry, stPipeline.nExposureRead, ResourceState::UnorderedAccess, ResourceState::ShaderRead));
		ENGINE_NEXT_CHECK(HasAccess(*pLighting, stPipeline.nExposureRead, ResourceState::ShaderRead, false));
		const ResourceId nResolved = bTemporal ? stPipeline.arrHistoryWrite[0] : stPipeline.nHdr;
		ENGINE_NEXT_CHECK(HasAccess(*pBuild, nResolved, ResourceState::NonPixelShaderRead, false));
		bool bHistogramOrdering = false;
		for (const ResourceBarrier &stBarrier : pBuild->arrBeforeBarriers)
		{
			bHistogramOrdering =
					bHistogramOrdering || (stBarrier.nResource == stPipeline.nHistogram && stBarrier.eKind == EngineNext::Rendering::BarrierKind::Uav);
		}
		ENGINE_NEXT_CHECK(bHistogramOrdering);
		ENGINE_NEXT_CHECK(HasTransition(*pAdapt, stPipeline.nHistogram, ResourceState::UnorderedAccess, ResourceState::NonPixelShaderRead));
		ENGINE_NEXT_CHECK(HasTransition(*pAdapt, stPipeline.nExposureWrite, ResourceState::Common, ResourceState::UnorderedAccess));
		ENGINE_NEXT_CHECK(HasAccess(*pTone, stPipeline.nExposureRead, ResourceState::ShaderRead, false));
		ENGINE_NEXT_CHECK(HasTransition(*pTone, stPipeline.nExposureWrite, ResourceState::UnorderedAccess, ResourceState::ShaderRead));
		if (bTemporal)
		{
			const CompiledPass *pTemporal = FindWork(stPipeline, PassWork::TemporalResolve);
			ENGINE_NEXT_CHECK(pTemporal != nullptr);
			if (pTemporal != nullptr)
			{
				ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false));
				ENGINE_NEXT_CHECK(pTemporal->nPass < pBuild->nPass);
			}
		}
		for (ResourceId nResource : { stPipeline.nHistogram, stPipeline.nExposureRead, stPipeline.nExposureWrite })
		{
			ENGINE_NEXT_CHECK(stPipeline.stGraph.arrResources[nResource].stDescription.bImported);
		}
		CheckReusableStates(stPipeline);
	}
}

ENGINE_NEXT_TEST("RenderPipeline maps every bloom mip to distinct resources and ordered work")
{
	for (std::uint32_t nMips = 1; nMips <= 6; ++nMips)
	{
		RenderPipeline stPipeline;
		GraphDiagnostic stDiagnostic;
		ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 6, true, true, nMips));
		ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 13U + nMips * 2U - 1U);
		ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 25U + nMips * 2U - 1U);
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrBloomDown.size(), nMips);
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrBloomUp.size(), nMips - 1U);
		ENGINE_NEXT_CHECK_EQ(stPipeline.arrPassMipIndex.size(), stPipeline.arrWorkByPass.size());
		const CompiledPass *pAdapt = FindWork(stPipeline, PassWork::ExposureAdapt);
		const CompiledPass *pLastDown = FindWork(stPipeline, PassWork::BloomDownsample, nMips - 1);
		for (std::uint32_t nMip = 0; nMip < nMips; ++nMip)
		{
			const CompiledPass *pDown = FindWork(stPipeline, PassWork::BloomDownsample, nMip);
			ENGINE_NEXT_CHECK(pDown != nullptr && pAdapt != nullptr);
			if (pDown == nullptr || pAdapt == nullptr)
			{
				continue;
			}
			const ResourceId nSource = nMip == 0 ? stPipeline.arrHistoryWrite[0] : stPipeline.arrBloomDown[nMip - 1];
			ENGINE_NEXT_CHECK(HasAccess(*pDown, nSource, ResourceState::NonPixelShaderRead, false));
			ENGINE_NEXT_CHECK(HasAccess(*pDown, stPipeline.arrBloomDown[nMip], ResourceState::UnorderedAccess, true));
			ENGINE_NEXT_CHECK(pDown->nPass > pAdapt->nPass);
			ENGINE_NEXT_CHECK(HasTransition(*pDown, stPipeline.arrBloomDown[nMip], ResourceState::Common, ResourceState::UnorderedAccess));
			if (nMip == 0)
			{
				ENGINE_NEXT_CHECK(HasAccess(*pDown, stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false));
				ENGINE_NEXT_CHECK(HasTransition(*pDown, stPipeline.nExposureWrite, ResourceState::UnorderedAccess, ResourceState::NonPixelShaderRead));
			}
		}
		for (std::uint32_t nMip = 0; nMip + 1 < nMips; ++nMip)
		{
			const CompiledPass *pUp = FindWork(stPipeline, PassWork::BloomUpsample, nMip);
			ENGINE_NEXT_CHECK(pUp != nullptr);
			if (pUp == nullptr)
			{
				continue;
			}
			const ResourceId nLower = nMip + 2 == nMips ? stPipeline.arrBloomDown[nMip + 1] : stPipeline.arrBloomUp[nMip + 1];
			ENGINE_NEXT_CHECK(HasAccess(*pUp, stPipeline.arrBloomDown[nMip], ResourceState::NonPixelShaderRead, false));
			ENGINE_NEXT_CHECK(HasAccess(*pUp, nLower, ResourceState::NonPixelShaderRead, false));
			ENGINE_NEXT_CHECK(HasAccess(*pUp, stPipeline.arrBloomUp[nMip], ResourceState::UnorderedAccess, true));
			ENGINE_NEXT_CHECK(pLastDown != nullptr);
			if (pLastDown != nullptr)
			{
				ENGINE_NEXT_CHECK(pUp->nPass > pLastDown->nPass);
			}
		}
		const CompiledPass *pTone = FindWork(stPipeline, PassWork::ToneMap);
		ENGINE_NEXT_CHECK(pTone != nullptr);
		if (pTone != nullptr)
		{
			const ResourceId nBloom = nMips == 1 ? stPipeline.arrBloomDown[0] : stPipeline.arrBloomUp[0];
			ENGINE_NEXT_CHECK(HasAccess(*pTone, nBloom, ResourceState::ShaderRead, false));
		}
		for (const CompiledPass &stPass : stPipeline.stGraph.arrPasses)
		{
			const PassWork eWork = stPipeline.arrWorkByPass[stPass.nPass];
			if (eWork != PassWork::BloomDownsample && eWork != PassWork::BloomUpsample)
			{
				ENGINE_NEXT_CHECK_EQ(stPipeline.arrPassMipIndex[stPass.nPass], EngineNext::Rendering::INVALID_RESOURCE);
			}
		}
		CheckReusableStates(stPipeline);
	}
}

ENGINE_NEXT_TEST("RenderPipeline meters and blooms current HDR when temporal resolve is disabled")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, false, true, 6));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 23U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 28U);
	ENGINE_NEXT_CHECK_EQ(FindWork(stPipeline, PassWork::TemporalResolve), nullptr);
	const CompiledPass *pBuild = FindWork(stPipeline, PassWork::HistogramBuild);
	const CompiledPass *pDown = FindWork(stPipeline, PassWork::BloomDownsample, 0);
	const CompiledPass *pTone = FindWork(stPipeline, PassWork::ToneMap);
	ENGINE_NEXT_CHECK(pBuild != nullptr && pDown != nullptr && pTone != nullptr);
	if (pBuild != nullptr && pDown != nullptr && pTone != nullptr)
	{
		ENGINE_NEXT_CHECK(HasAccess(*pBuild, stPipeline.nHdr, ResourceState::NonPixelShaderRead, false));
		ENGINE_NEXT_CHECK(HasAccess(*pDown, stPipeline.nHdr, ResourceState::NonPixelShaderRead, false));
		ENGINE_NEXT_CHECK(HasAccess(*pTone, stPipeline.nHdr, ResourceState::ShaderRead, false));
	}
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline bounds post-process settings without replacing an existing graph")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 28, true, true, 6));
	const std::vector<PassWork> arrWork = stPipeline.arrWorkByPass;
	const std::vector<ResourceId> arrBloom = stPipeline.arrBloomDown;
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 7));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, arrWork);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrBloomDown, arrBloom);
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, false, 1));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, arrWork);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 9U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nExposureRead, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(stPipeline.arrBloomDown.empty() && stPipeline.arrBloomUp.empty());
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 28, true, true, 6));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK(stPipeline.arrBloomDown.empty() && stPipeline.arrBloomUp.empty());
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline declares post-process readback transfers and restores sources")
{
	for (bool bTemporal : { false, true })
	{
		for (std::uint32_t nMips : { 0U, 1U, 6U })
		{
			RenderPipeline stPipeline;
			GraphDiagnostic stDiagnostic;
			ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, bTemporal, true, nMips));
			const CompiledPass *pTone = FindWork(stPipeline, PassWork::ToneMap);
			const CompiledPass *pReadback = FindWork(stPipeline, PassWork::PostProcessReadback);
			const CompiledPass *pCopy = FindWork(stPipeline, PassWork::CopyToBackbuffer);
			const CompiledPass *pPresent = FindWork(stPipeline, PassWork::Present);
			ENGINE_NEXT_CHECK(pTone != nullptr && pReadback != nullptr && pCopy != nullptr && pPresent != nullptr);
			if (pTone == nullptr || pReadback == nullptr || pCopy == nullptr || pPresent == nullptr)
			{
				continue;
			}
			ENGINE_NEXT_CHECK(pTone->nPass < pReadback->nPass && pReadback->nPass < pCopy->nPass);
			ENGINE_NEXT_CHECK_EQ(pReadback->eQueue, QueueType::Graphics);
			ENGINE_NEXT_CHECK_EQ(pReadback->arrAccesses.size(), 3U);
			ENGINE_NEXT_CHECK(HasAccess(*pReadback, stPipeline.nHistogram, ResourceState::CopySource, false));
			ENGINE_NEXT_CHECK(HasAccess(*pReadback, stPipeline.nExposureWrite, ResourceState::CopySource, false));
			ENGINE_NEXT_CHECK(HasAccess(*pReadback, stPipeline.nPostReadback, ResourceState::CopyDestination, true));
			ENGINE_NEXT_CHECK(HasTransition(*pReadback, stPipeline.nHistogram, ResourceState::NonPixelShaderRead, ResourceState::CopySource));
			ENGINE_NEXT_CHECK(HasTransition(*pReadback, stPipeline.nExposureWrite, ResourceState::ShaderRead, ResourceState::CopySource));
			ENGINE_NEXT_CHECK(HasTransition(*pPresent, stPipeline.nHistogram, ResourceState::CopySource, ResourceState::Common));
			ENGINE_NEXT_CHECK(HasTransition(*pPresent, stPipeline.nExposureWrite, ResourceState::CopySource, ResourceState::Common));
			const CompiledResource &stReadback = stPipeline.stGraph.arrResources[stPipeline.nPostReadback];
			ENGINE_NEXT_CHECK(stReadback.stDescription.bImported);
			ENGINE_NEXT_CHECK_EQ(stReadback.stDescription.eInitialState, ResourceState::CopyDestination);
			ENGINE_NEXT_CHECK_EQ(stReadback.arrFinalStates, (std::vector<ResourceState>{ ResourceState::CopyDestination }));
			CheckReusableStates(stPipeline);
		}
	}
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.nPostReadback, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(FindWork(stPipeline, PassWork::PostProcessReadback), nullptr);
}

ENGINE_NEXT_TEST("RenderPipeline separates reflection lighting and composes before temporal")
{
	for (bool bTemporal : { false, true })
	{
		for (std::uint32_t nLevels : { 1U, 6U })
		{
			RenderPipeline stPipeline;
			GraphDiagnostic stDiagnostic;
			ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, bTemporal, true, 0, nLevels));
			ENGINE_NEXT_CHECK_EQ(stPipeline.arrReflectionMips.size(), nLevels - 1U);
			ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), (bTemporal ? 13U : 12U) + nLevels + 2U);
			ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), (bTemporal ? 25U : 17U) + nLevels + 2U);
			const CompiledPass *pLight = FindWork(stPipeline, PassWork::DeferredLighting);
			const CompiledPass *pTrace = FindWork(stPipeline, PassWork::ReflectionTrace);
			const CompiledPass *pRadiance = FindWork(stPipeline, PassWork::ReflectionRadiance);
			const CompiledPass *pComposite = FindWork(stPipeline, PassWork::ReflectionComposite);
			const CompiledPass *pNext = FindWork(stPipeline, bTemporal ? PassWork::TemporalResolve : PassWork::HistogramBuild);
			ENGINE_NEXT_CHECK(pLight != nullptr && pRadiance != nullptr && pTrace != nullptr && pComposite != nullptr && pNext != nullptr);
			if (pLight == nullptr || pRadiance == nullptr || pTrace == nullptr || pComposite == nullptr || pNext == nullptr)
			{
				continue;
			}
			ENGINE_NEXT_CHECK(HasAccess(*pLight, stPipeline.nHdr, ResourceState::RenderTarget, true));
			ENGINE_NEXT_CHECK(HasAccess(*pLight, stPipeline.nEnvironmentSpecular, ResourceState::RenderTarget, true));
			ENGINE_NEXT_CHECK(pLight->nPass < pRadiance->nPass && pRadiance->nPass < pTrace->nPass && pTrace->nPass < pComposite->nPass &&
							  pComposite->nPass < pNext->nPass);
			ENGINE_NEXT_CHECK(HasAccess(*pRadiance, stPipeline.nHdr, ResourceState::NonPixelShaderRead, false));
			ENGINE_NEXT_CHECK(HasAccess(*pRadiance, stPipeline.nEnvironmentSpecular, ResourceState::NonPixelShaderRead, false));
			ENGINE_NEXT_CHECK(HasAccess(*pRadiance, stPipeline.nReflectedHdr, ResourceState::UnorderedAccess, true));
			for (ResourceId nResource : { stPipeline.nReflectedHdr, stPipeline.arrGbuffer[0], stPipeline.arrGbuffer[1], stPipeline.arrGbuffer[2] })
			{
				ENGINE_NEXT_CHECK(HasAccess(*pTrace, nResource, ResourceState::NonPixelShaderRead, false));
			}
			ENGINE_NEXT_CHECK(HasAccess(*pTrace, stPipeline.nDepth, ResourceState::DepthRead, false));
			ENGINE_NEXT_CHECK(HasAccess(*pTrace, stPipeline.nReflection, ResourceState::UnorderedAccess, true));
			ENGINE_NEXT_CHECK(HasTransition(*pRadiance, stPipeline.nEnvironmentSpecular, ResourceState::RenderTarget, ResourceState::NonPixelShaderRead));
			ENGINE_NEXT_CHECK(HasTransition(*pComposite, stPipeline.nReflection, ResourceState::UnorderedAccess, ResourceState::NonPixelShaderRead));
			ENGINE_NEXT_CHECK(HasAccess(*pComposite, stPipeline.nReflectedHdr, ResourceState::UnorderedAccess, true));
			ENGINE_NEXT_CHECK(HasTransition(*pComposite, stPipeline.nReflectedHdr, ResourceState::NonPixelShaderRead, ResourceState::UnorderedAccess));
			ENGINE_NEXT_CHECK(HasTransition(*pNext, stPipeline.nReflectedHdr, ResourceState::UnorderedAccess, ResourceState::NonPixelShaderRead));
			for (std::uint32_t nLevel = 1; nLevel < nLevels; ++nLevel)
			{
				const CompiledPass *pMip = FindWork(stPipeline, PassWork::ReflectionColorMip, nLevel);
				ENGINE_NEXT_CHECK(pMip != nullptr);
				if (pMip == nullptr)
				{
					continue;
				}
				const ResourceId nSource = nLevel == 1 ? stPipeline.nReflectedHdr : stPipeline.arrReflectionMips[nLevel - 2];
				const ResourceId nOutput = stPipeline.arrReflectionMips[nLevel - 1];
				ENGINE_NEXT_CHECK(HasAccess(*pMip, nSource, ResourceState::NonPixelShaderRead, false));
				ENGINE_NEXT_CHECK(HasAccess(*pMip, nOutput, ResourceState::UnorderedAccess, true));
				ENGINE_NEXT_CHECK(HasAccess(*pTrace, nOutput, ResourceState::NonPixelShaderRead, false));
				ENGINE_NEXT_CHECK(pMip->nPass < pTrace->nPass);
			}
			CheckReusableStates(stPipeline);
		}
	}
}

ENGINE_NEXT_TEST("RenderPipeline bounds reflections and preserves disabled and fixed entry points")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 6, 6));
	const std::vector<PassWork> arrWork = stPipeline.arrWorkByPass;
	const ResourceId nReflected = stPipeline.nReflectedHdr;
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 6, 7));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::CapacityExceeded);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nReflectedHdr, nReflected);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, arrWork);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 9U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nReflection, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nEnvironmentSpecular, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(stPipeline.arrReflectionMips.empty());
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 0, true, true, 6, 6));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nReflectedHdr, EngineNext::Rendering::INVALID_RESOURCE);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline volume passes own their temporal history with TAA disabled")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 7, false, true, 0, 0, { true, false }));
	const CompiledPass *pPrepare = FindWork(stPipeline, PassWork::VolumePrepare);
	const CompiledPass *pInject = FindWork(stPipeline, PassWork::VolumeInject);
	const CompiledPass *pLight = FindWork(stPipeline, PassWork::VolumeLight);
	const CompiledPass *pTemporal = FindWork(stPipeline, PassWork::VolumeTemporal);
	const CompiledPass *pIntegrate = FindWork(stPipeline, PassWork::VolumeIntegrate);
	const CompiledPass *pComposite = FindWork(stPipeline, PassWork::VolumeComposite);
	const CompiledPass *pToneMap = FindWork(stPipeline, PassWork::ToneMap);
	ENGINE_NEXT_CHECK(pPrepare && pInject && pLight && pTemporal && pIntegrate && pComposite && pToneMap);
	if (!pPrepare || !pInject || !pLight || !pTemporal || !pIntegrate || !pComposite || !pToneMap)
	{
		return;
	}
	ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::TemporalResolve) == nullptr);
	ENGINE_NEXT_CHECK(HasAccess(*pPrepare, stPipeline.nVolumeHistoryRead, ResourceState::UnorderedAccess, true));
	ENGINE_NEXT_CHECK(pPrepare->arrAccesses[0].bReadBeforeWrite);
	ENGINE_NEXT_CHECK(HasAccess(*pInject, stPipeline.nVolumeMedium, ResourceState::UnorderedAccess, true));
	ENGINE_NEXT_CHECK(HasAccess(*pLight, stPipeline.nVolumeEmission, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pLight, stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.nVolumeHistoryRead, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.nVolumeHistoryWrite, ResourceState::UnorderedAccess, true));
	ENGINE_NEXT_CHECK(HasAccess(*pIntegrate, stPipeline.nVolumeHistoryWrite, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pComposite, stPipeline.nVolumeIntegral, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pComposite, stPipeline.nHdr, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pToneMap, stPipeline.nForwardHdr, ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(stPipeline.nVolumeHistoryRead != stPipeline.nVolumeHistoryWrite);
	ENGINE_NEXT_CHECK(stPipeline.stGraph.arrResources[stPipeline.nVolumeHistoryRead].stDescription.bImported);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources[stPipeline.nVolumeMedium].stDescription.nSubresourceCount, 1U);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline transparency copies opaque HDR and preserves it during blending")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 0, { false, true }));
	const CompiledPass *pCopy = FindWork(stPipeline, PassWork::ForwardCopy);
	const CompiledPass *pTransparency = FindWork(stPipeline, PassWork::Transparency);
	const CompiledPass *pTemporal = FindWork(stPipeline, PassWork::TemporalResolve);
	ENGINE_NEXT_CHECK(pCopy && pTransparency && pTemporal);
	if (!pCopy || !pTransparency || !pTemporal)
	{
		return;
	}
	ENGINE_NEXT_CHECK(HasAccess(*pCopy, stPipeline.nHdr, ResourceState::CopySource, false));
	ENGINE_NEXT_CHECK(HasAccess(*pCopy, stPipeline.nForwardHdr, ResourceState::CopyDestination, true));
	ENGINE_NEXT_CHECK(HasAccess(*pTransparency, stPipeline.nForwardHdr, ResourceState::RenderTarget, true));
	ENGINE_NEXT_CHECK(pTransparency->arrAccesses[0].bReadBeforeWrite);
	ENGINE_NEXT_CHECK(HasAccess(*pTransparency, stPipeline.nDepth, ResourceState::DepthRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTransparency, stPipeline.nReactiveMask, ResourceState::RenderTarget, true));
	ENGINE_NEXT_CHECK(HasAccess(*pTransparency, stPipeline.nExposureRead, ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.nReactiveMask, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTemporal, stPipeline.nForwardHdr, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::VolumeInject) == nullptr);
	ENGINE_NEXT_CHECK(HasTransition(*pTransparency, stPipeline.nForwardHdr, ResourceState::CopyDestination, ResourceState::RenderTarget));
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline composes reflections fog and transparency before temporal resolve")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 28, true, true, 6, 6, { true, true }));
	const CompiledPass *pReflection = FindWork(stPipeline, PassWork::ReflectionComposite);
	const CompiledPass *pVolume = FindWork(stPipeline, PassWork::VolumeComposite);
	const CompiledPass *pTransparency = FindWork(stPipeline, PassWork::Transparency);
	const CompiledPass *pTemporal = FindWork(stPipeline, PassWork::TemporalResolve);
	ENGINE_NEXT_CHECK(pReflection && pVolume && pTransparency && pTemporal);
	if (!pReflection || !pVolume || !pTransparency || !pTemporal)
	{
		return;
	}
	ENGINE_NEXT_CHECK(pReflection->nPass < pVolume->nPass);
	ENGINE_NEXT_CHECK(pVolume->nPass < pTransparency->nPass);
	ENGINE_NEXT_CHECK(pTransparency->nPass < pTemporal->nPass);
	ENGINE_NEXT_CHECK(HasAccess(*pVolume, stPipeline.nReflectedHdr, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTransparency, stPipeline.nVolumeHistoryWrite, ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTransparency, stPipeline.nVolumeIntegral, ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::ForwardCopy) == nullptr);
	ENGINE_NEXT_CHECK(stPipeline.stGraph.arrPasses.size() < 64);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline forward feature combinations remain reusable and fixed mode compatible")
{
	for (bool bVolume : { false, true })
	{
		for (bool bTransparency : { false, true })
		{
			for (bool bTemporal : { false, true })
			{
				for (bool bExposure : { false, true })
				{
					RenderPipeline stPipeline;
					GraphDiagnostic stDiagnostic;
					ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, bTemporal, bExposure, 0, 0, { bVolume, bTransparency }));
					ENGINE_NEXT_CHECK_EQ(FindWork(stPipeline, PassWork::VolumeTemporal) != nullptr, bVolume);
					ENGINE_NEXT_CHECK_EQ(FindWork(stPipeline, PassWork::Transparency) != nullptr, bTransparency);
					ENGINE_NEXT_CHECK_EQ(FindWork(stPipeline, PassWork::TemporalResolve) != nullptr, bTemporal);
					CheckReusableStates(stPipeline);
				}
			}
		}
	}
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 0, true, false, 0, 0, { true, true }));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrResources.size(), 4U);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline material buffers follow geometry lighting reflections and retirement")
{
	for (bool bReflections : { false, true })
	{
		for (bool bForward : { false, true })
		{
			RenderPipeline stPipeline;
			GraphDiagnostic stDiagnostic;
			ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 6, true, true, 6,
												  bReflections ? 6U : 0U, { bForward, bForward }, true));
			const CompiledPass *pGeometry = FindWork(stPipeline, PassWork::GBuffer);
			const CompiledPass *pLighting = FindWork(stPipeline, PassWork::DeferredLighting);
			const CompiledPass *pPresent = FindWork(stPipeline, PassWork::Present);
			ENGINE_NEXT_CHECK(pGeometry && pLighting && pPresent);
			if (!pGeometry || !pLighting || !pPresent)
			{
				return;
			}
			for (ResourceId nResource : stPipeline.arrMaterialBuffers)
			{
				ENGINE_NEXT_CHECK(nResource != EngineNext::Rendering::INVALID_RESOURCE);
				ENGINE_NEXT_CHECK(HasAccess(*pGeometry, nResource, ResourceState::RenderTarget, true));
				ENGINE_NEXT_CHECK(HasAccess(*pLighting, nResource, ResourceState::ShaderRead, false));
				ENGINE_NEXT_CHECK(HasAccess(*pPresent, nResource, ResourceState::Common, false));
				if (bReflections)
				{
					const CompiledPass *pTrace = FindWork(stPipeline, PassWork::ReflectionTrace);
					ENGINE_NEXT_CHECK(pTrace != nullptr);
					if (pTrace != nullptr)
					{
						ENGINE_NEXT_CHECK(HasAccess(*pTrace, nResource, ResourceState::NonPixelShaderRead, false));
						ENGINE_NEXT_CHECK(HasAccess(*pTrace, stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false));
					}
				}
			}
			CheckReusableStates(stPipeline);
		}
	}
}

ENGINE_NEXT_TEST("RenderPipeline keeps optional material buffers absent in legacy and fixed mesh modes")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrMaterialBuffers[0], EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrMaterialBuffers[1], EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 0, true, false, 0, 0, {}, true));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrMaterialBuffers[0], EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrMaterialBuffers[1], EngineNext::Rendering::INVALID_RESOURCE);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("Geometry pipeline preserves current depth and indirect dependencies")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 0, {}, false, false, { true, true, 8 }));
	const CompiledPass *pDepth = FindWork(stPipeline, PassWork::GeometryDepth);
	const CompiledPass *pCull = FindWork(stPipeline, PassWork::GeometryCullColor);
	const CompiledPass *pGbuffer = FindWork(stPipeline, PassWork::GBuffer);
	const CompiledPass *pReadback = FindWork(stPipeline, PassWork::GeometryReadback);
	ENGINE_NEXT_CHECK(pDepth != nullptr && pCull != nullptr && pGbuffer != nullptr && pReadback != nullptr);
	ENGINE_NEXT_CHECK(HasAccess(*pDepth, stPipeline.nDepth, ResourceState::DepthWrite, true));
	ENGINE_NEXT_CHECK(HasAccess(*pDepth, stPipeline.arrGeometryArguments[0], ResourceState::IndirectArgument, false));
	ENGINE_NEXT_CHECK(HasAccess(*pCull, stPipeline.nGeometryHiZ, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pGbuffer, stPipeline.arrGeometryArguments[1], ResourceState::IndirectArgument, false));
	ENGINE_NEXT_CHECK(HasAccess(*pReadback, stPipeline.arrGeometryCounters[1], ResourceState::CopySource, false));
	for (std::uint32_t nMip = 0; nMip < 8; ++nMip)
	{
		ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::GeometryHiZ, nMip) != nullptr);
	}
	CheckReusableStates(stPipeline);
}
ENGINE_NEXT_TEST("Geometry disabled occlusion retains frustum submissions and original fixed path")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, false, false, 0, 0, {}, false, false, { true, false, 1 }));
	ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::GeometryDepth) != nullptr);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGeometryHiZ, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::GeometryHiZ, 0) == nullptr);
	CheckReusableStates(stPipeline);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 0, true, false, 0, 0, {}, false, false, { true, true, 8 }));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGeometryClusters, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(!BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, false, 0, 0, {}, false, false, { true, true, 16 }));
}

ENGINE_NEXT_TEST("RenderPipeline combines GI and geometry with reusable resources")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 28, true, true, 6, 6, { true, true }, true, true, { true, true, 15 }, true));
	const CompiledPass *pGiUpdate = FindWork(stPipeline, PassWork::GiUpdate);
	const CompiledPass *pCull = FindWork(stPipeline, PassWork::GeometryCullColor);
	const CompiledPass *pGbuffer = FindWork(stPipeline, PassWork::GBuffer);
	const CompiledPass *pLighting = FindWork(stPipeline, PassWork::DeferredLighting);
	ENGINE_NEXT_CHECK(pGiUpdate != nullptr && pCull != nullptr && pGbuffer != nullptr && pLighting != nullptr);
	if (pGiUpdate == nullptr || pCull == nullptr || pGbuffer == nullptr || pLighting == nullptr)
	{
		return;
	}
	ENGINE_NEXT_CHECK(pGiUpdate->nPass < pLighting->nPass);
	ENGINE_NEXT_CHECK(pCull->nPass < pGbuffer->nPass);
	ENGINE_NEXT_CHECK(HasAccess(*pGbuffer, stPipeline.arrGeometryArguments[1], ResourceState::IndirectArgument, false));
	ENGINE_NEXT_CHECK(HasAccess(*pLighting, stPipeline.arrGiWrite[0], ResourceState::ShaderRead, false));
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline orders deformation copies before vertex consumers")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 0, {}, false, true, {}, false, false, true));
	const CompiledPass *pUpload = FindWork(stPipeline, PassWork::DeformationUpload);
	const CompiledPass *pShadow = FindWork(stPipeline, PassWork::DirectionalShadow);
	const CompiledPass *pGbuffer = FindWork(stPipeline, PassWork::GBuffer);
	ENGINE_NEXT_CHECK(pUpload != nullptr && pShadow != nullptr && pGbuffer != nullptr);
	if (pUpload == nullptr || pShadow == nullptr || pGbuffer == nullptr)
	{
		return;
	}
	ENGINE_NEXT_CHECK(pUpload->nPass < pShadow->nPass && pShadow->nPass < pGbuffer->nPass);
	ENGINE_NEXT_CHECK(HasTransition(*pUpload, stPipeline.nDeformedVertices, ResourceState::Common, ResourceState::CopyDestination));
	ENGINE_NEXT_CHECK(HasTransition(*pShadow, stPipeline.nDeformedVertices, ResourceState::CopyDestination, ResourceState::VertexIndexRead));
	ENGINE_NEXT_CHECK(HasTransition(*pGbuffer, stPipeline.nPreviousPositions, ResourceState::CopyDestination, ResourceState::VertexIndexRead));
	ENGINE_NEXT_CHECK(HasAccess(*pGbuffer, stPipeline.nDeformedVertices, ResourceState::VertexIndexRead, false));
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline relocates probes between remap and radiance tracing")
{
	RenderPipeline stPipeline;
	RenderPipeline stLegacy;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stLegacy, stDiagnostic, 0, false, false, 0, 0, {}, false, true));
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, false, false, 0, 0, {}, false, true, {}, true));
	ENGINE_NEXT_CHECK_EQ(stPipeline.stGraph.arrPasses.size(), stLegacy.stGraph.arrPasses.size() + 1);
	const CompiledPass *pRemap = FindWork(stPipeline, PassWork::GiRemap);
	const CompiledPass *pPlacement = FindWork(stPipeline, PassWork::GiRelocate);
	const CompiledPass *pTrace = FindWork(stPipeline, PassWork::GiTrace);
	ENGINE_NEXT_CHECK(pRemap != nullptr && pPlacement != nullptr && pTrace != nullptr);
	if (pRemap != nullptr && pPlacement != nullptr && pTrace != nullptr)
	{
		ENGINE_NEXT_CHECK(pRemap->nPass < pPlacement->nPass && pPlacement->nPass < pTrace->nPass);
		ENGINE_NEXT_CHECK(HasAccess(*pPlacement, stPipeline.nGiScene, ResourceState::AccelerationStructure, false));
		ENGINE_NEXT_CHECK(HasAccess(*pPlacement, stPipeline.nGiPositions, ResourceState::NonPixelShaderRead, false));
		for (ResourceId nResource : stPipeline.arrGiWrite)
		{
			ENGINE_NEXT_CHECK(HasAccess(*pPlacement, nResource, ResourceState::UnorderedAccess, true));
		}
	}
	ENGINE_NEXT_CHECK(FindWork(stLegacy, PassWork::GiRelocate) == nullptr);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("RenderPipeline orders bounded shadow uploads feedback and receiver reads")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 6, true, true, 0, 0, { false, true }, false, false, {}, false, true, true, false, {}, true, 17));
	const CompiledPass *pUpload = FindWork(stPipeline, PassWork::ShadowPageUpload);
	const CompiledPass *pRender = FindWork(stPipeline, PassWork::ShadowPageRender);
	const CompiledPass *pFeedback = FindWork(stPipeline, PassWork::ShadowPageFeedback);
	const CompiledPass *pReadback = FindWork(stPipeline, PassWork::ShadowPageReadback);
	const CompiledPass *pLighting = FindWork(stPipeline, PassWork::DeferredLighting);
	const CompiledPass *pTransparent = FindWork(stPipeline, PassWork::Transparency);
	ENGINE_NEXT_CHECK(pUpload != nullptr && pRender != nullptr && pFeedback != nullptr && pReadback != nullptr && pLighting != nullptr && pTransparent != nullptr);
	if (pUpload == nullptr || pRender == nullptr || pFeedback == nullptr || pReadback == nullptr || pLighting == nullptr || pTransparent == nullptr)
	{
		return;
	}
	ENGINE_NEXT_CHECK(HasTransition(*pUpload, stPipeline.nShadowPageTable, ResourceState::Common, ResourceState::CopyDestination));
	ENGINE_NEXT_CHECK(HasAccess(*pRender, stPipeline.nDeformedVertices, ResourceState::VertexIndexRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pRender, stPipeline.nShadowPagePool, ResourceState::DepthWrite, true));
	ENGINE_NEXT_CHECK(HasAccess(*pFeedback, stPipeline.nDepth, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pFeedback, stPipeline.nShadowPageFeedback, ResourceState::UnorderedAccess, true));
	ENGINE_NEXT_CHECK(HasTransition(*pReadback, stPipeline.nShadowPageFeedback, ResourceState::UnorderedAccess, ResourceState::CopySource));
	ENGINE_NEXT_CHECK(HasAccess(*pLighting, stPipeline.nShadowPagePool, ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pTransparent, stPipeline.nShadowPageTable, ResourceState::ShaderRead, false));
	ENGINE_NEXT_CHECK(stPipeline.stGraph.arrResources[stPipeline.nShadowPagePool].stDescription.nSubresourceCount == 17);
	bool bLastDepth = false;
	bool bLastReceiver = false;
	for (const ResourceBarrier &stBarrier : pRender->arrBeforeBarriers)
	{
		bLastDepth = bLastDepth || (stBarrier.nResource == stPipeline.nShadowPagePool && stBarrier.nSubresource == 16 && stBarrier.eBefore == ResourceState::Common && stBarrier.eAfter == ResourceState::DepthWrite);
	}
	for (const ResourceBarrier &stBarrier : pLighting->arrBeforeBarriers)
	{
		bLastReceiver = bLastReceiver || (stBarrier.nResource == stPipeline.nShadowPagePool && stBarrier.nSubresource == 16 && stBarrier.eBefore == ResourceState::DepthWrite && stBarrier.eAfter == ResourceState::ShaderRead);
	}
	ENGINE_NEXT_CHECK(bLastDepth && bLastReceiver);
	CheckReusableStates(stPipeline);
	RenderPipeline stFixed;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stFixed, stDiagnostic, 0, false, false, 0, 0, {}, false, false, {}, false, false, false, false, {}, true));
	ENGINE_NEXT_CHECK(FindWork(stFixed, PassWork::ShadowPageUpload) == nullptr);
}

ENGINE_NEXT_TEST("Ambient occlusion reads the completed GBuffer and feeds indirect lighting")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 0, {}, false, false, {}, false, true));
	const CompiledPass *pGbuffer = FindWork(stPipeline, PassWork::GBuffer);
	const CompiledPass *pAmbient = FindWork(stPipeline, PassWork::AmbientOcclusion);
	const CompiledPass *pHorizontal = FindWork(stPipeline, PassWork::AmbientBlurHorizontal);
	const CompiledPass *pVertical = FindWork(stPipeline, PassWork::AmbientBlurVertical);
	const CompiledPass *pLighting = FindWork(stPipeline, PassWork::DeferredLighting);
	ENGINE_NEXT_CHECK(pGbuffer != nullptr && pAmbient != nullptr && pHorizontal != nullptr && pVertical != nullptr && pLighting != nullptr);
	if (pGbuffer == nullptr || pAmbient == nullptr || pHorizontal == nullptr || pVertical == nullptr || pLighting == nullptr)
	{
		return;
	}
	ENGINE_NEXT_CHECK(pGbuffer->nPass < pAmbient->nPass && pAmbient->nPass < pHorizontal->nPass && pHorizontal->nPass < pVertical->nPass && pVertical->nPass < pLighting->nPass);
	ENGINE_NEXT_CHECK(HasAccess(*pAmbient, stPipeline.nDepth, ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pAmbient, stPipeline.arrGbuffer[1], ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pHorizontal, stPipeline.arrAmbientOcclusion[0], ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pVertical, stPipeline.arrAmbientOcclusion[1], ResourceState::NonPixelShaderRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pLighting, stPipeline.arrAmbientOcclusion[2], ResourceState::ShaderRead, false));
	CheckReusableStates(stPipeline);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(false, stPipeline, stDiagnostic, 0, true, false, 0, 0, {}, false, false, {}, false, true));
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrAmbientOcclusion[0], EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(FindWork(stPipeline, PassWork::AmbientOcclusion) == nullptr);
}

ENGINE_NEXT_TEST("Color grading LUT is an immutable input of the tone mapping pass")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 0, {}, false, false, {}, false, false, false, true));
	ENGINE_NEXT_CHECK(stPipeline.nColorLut != EngineNext::Rendering::INVALID_RESOURCE);
	const CompiledPass *pToneMap = FindWork(stPipeline, PassWork::ToneMap);
	ENGINE_NEXT_CHECK(pToneMap != nullptr);
	if (pToneMap != nullptr)
	{
		ENGINE_NEXT_CHECK(HasAccess(*pToneMap, stPipeline.nColorLut, ResourceState::ShaderRead, false));
	}
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stPipeline.nColorLut, EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, true, 0, 2, {}, true, false, { true, true, 8, true }, false, false, false, true, { true, 2 }, true, 17));
	ENGINE_NEXT_CHECK(stPipeline.nColorLut != EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(stPipeline.nGeometryPages != EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(stPipeline.nShadowPagePool != EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(stPipeline.stGraph.arrResources[stPipeline.nShadowPagePool].stDescription.nSubresourceCount == 17);
	CheckReusableStates(stPipeline);
}

ENGINE_NEXT_TEST("Paged geometry pool declares all physical upload draw and retirement states")
{
	RenderPipeline stPipeline;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 28, true, true, 6, 6, { true, true }, true, true, { true, true, 8, true }, true, true));
	const CompiledPass *pUpload = FindWork(stPipeline, PassWork::GeometryUpload);
	const CompiledPass *pDepth = FindWork(stPipeline, PassWork::GeometryDepth);
	const CompiledPass *pGbuffer = FindWork(stPipeline, PassWork::GBuffer);
	const CompiledPass *pPresent = FindWork(stPipeline, PassWork::Present);
	ENGINE_NEXT_CHECK(pUpload && pDepth && pGbuffer && pPresent);
	if (!pUpload || !pDepth || !pGbuffer || !pPresent)
	{
		return;
	}
	ENGINE_NEXT_CHECK(stPipeline.nGeometryPages != EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK(HasAccess(*pUpload, stPipeline.nGeometryPages, ResourceState::CopyDestination, true));
	ENGINE_NEXT_CHECK(HasAccess(*pDepth, stPipeline.nGeometryPages, ResourceState::VertexIndexRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pGbuffer, stPipeline.nGeometryPages, ResourceState::VertexIndexRead, false));
	ENGINE_NEXT_CHECK(HasAccess(*pPresent, stPipeline.nGeometryPages, ResourceState::Common, false));
	CheckReusableStates(stPipeline);
	ENGINE_NEXT_CHECK(BuildRenderPipeline(true, stPipeline, stDiagnostic, 0, true, false, 0, 0, {}, false, false, { true, true, 8 }));
	ENGINE_NEXT_CHECK_EQ(stPipeline.nGeometryPages, EngineNext::Rendering::INVALID_RESOURCE);
}
