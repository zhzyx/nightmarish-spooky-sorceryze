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
	ENGINE_NEXT_CHECK_EQ(stPipeline.arrWorkByPass, (std::vector<PassWork>{ PassWork::ComputeTint, PassWork::FixedMesh, PassWork::CopyToBackbuffer, PassWork::Present }));
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
										   PassWork::GBuffer, PassWork::DeferredLighting, PassWork::TemporalResolve, PassWork::ToneMap, PassWork::CopyToBackbuffer, PassWork::Present };
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
			bHistogramOrdering = bHistogramOrdering || (stBarrier.nResource == stPipeline.nHistogram && stBarrier.eKind == EngineNext::Rendering::BarrierKind::Uav);
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
			ENGINE_NEXT_CHECK(pLight->nPass < pRadiance->nPass && pRadiance->nPass < pTrace->nPass && pTrace->nPass < pComposite->nPass && pComposite->nPass < pNext->nPass);
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
