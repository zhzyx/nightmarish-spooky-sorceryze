/**************************************************************************/
/*  FrameGraph.cpp                                                        */
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

#include "engine_next/include/EngineNext/Rendering/FrameGraph.h"

#include <algorithm>
#include <cstddef>
#include <utility>

namespace EngineNext::Rendering
{

namespace
{

struct SubresourceUsage
{
	PassId nLastPass = INVALID_PASS;
	ResourceState eState = ResourceState::Common;
	bool bInitialized = false;
	bool bLastWrite = false;
};

bool Fail(GraphDiagnostic &out_stDiagnostic, GraphError eError, PassId nPass, ResourceId nResource, const char *pMessage)
{
	out_stDiagnostic = GraphDiagnostic{ eError, nPass, nResource, pMessage };
	return false;
}

bool IsQueueValid(QueueType eQueue)
{
	return eQueue == QueueType::Graphics || eQueue == QueueType::Compute || eQueue == QueueType::Copy;
}

bool IsStateValid(ResourceState eState)
{
	return eState >= ResourceState::Common && eState <= ResourceState::DepthRead;
}

bool IsQueueStateSupported(QueueType eQueue, ResourceState eState)
{
	if (eQueue == QueueType::Graphics)
	{
		return IsStateValid(eState);
	}
	if (eState == ResourceState::Common || eState == ResourceState::CopySource || eState == ResourceState::CopyDestination)
	{
		return true;
	}
	return eQueue == QueueType::Compute && (eState == ResourceState::NonPixelShaderRead || eState == ResourceState::UnorderedAccess);
}

bool IsWriteState(ResourceState eState)
{
	return eState == ResourceState::RenderTarget || eState == ResourceState::DepthWrite || eState == ResourceState::CopyDestination || eState == ResourceState::UnorderedAccess;
}

std::uint32_t GetAccessCount(const ResourceAccess &stAccess, const ResourceDesc &stResource)
{
	return stAccess.nSubresourceCount == ALL_SUBRESOURCES ? stResource.nSubresourceCount - stAccess.nFirstSubresource : stAccess.nSubresourceCount;
}

void AddUnique(std::vector<PassId> &out_arrValues, PassId nValue)
{
	if (std::find(out_arrValues.begin(), out_arrValues.end(), nValue) == out_arrValues.end())
	{
		out_arrValues.push_back(nValue);
	}
}

bool ValidatePass(const PassDesc &stPass, PassId nPass, const std::vector<ResourceDesc> &arrResources, std::size_t nPassCount, GraphDiagnostic &out_stDiagnostic)
{
	if (!IsQueueValid(stPass.eQueue))
	{
		return Fail(out_stDiagnostic, GraphError::InvalidPass, nPass, INVALID_RESOURCE, "Pass queue is invalid.");
	}
	for (PassId nDependency : stPass.arrDependencies)
	{
		if (nDependency >= nPassCount || nDependency == nPass)
		{
			return Fail(out_stDiagnostic, GraphError::InvalidDependency, nPass, INVALID_RESOURCE, "Pass dependency is unknown or self-referential.");
		}
	}
	std::vector<std::vector<bool>> arrAccessed(arrResources.size());
	for (const ResourceAccess &stAccess : stPass.arrAccesses)
	{
		if (stAccess.nResource >= arrResources.size())
		{
			return Fail(out_stDiagnostic, GraphError::InvalidResource, nPass, stAccess.nResource, "Resource access refers to an unknown resource.");
		}
		const ResourceDesc &stResource = arrResources[stAccess.nResource];
		if (stAccess.nFirstSubresource >= stResource.nSubresourceCount)
		{
			return Fail(out_stDiagnostic, GraphError::InvalidAccess, nPass, stAccess.nResource, "Subresource range starts outside the resource.");
		}
		const std::uint32_t nCount = GetAccessCount(stAccess, stResource);
		if (nCount == 0 || nCount > stResource.nSubresourceCount - stAccess.nFirstSubresource || !IsStateValid(stAccess.eState) ||
			(stAccess.bWrite && !IsWriteState(stAccess.eState)) || (stAccess.bReadBeforeWrite && !stAccess.bWrite) ||
			(!stAccess.bWrite && IsWriteState(stAccess.eState) && stAccess.eState != ResourceState::UnorderedAccess))
		{
			return Fail(out_stDiagnostic, GraphError::InvalidAccess, nPass, stAccess.nResource, "Resource access has an invalid range, state, or read/write mode.");
		}
		if (!IsQueueStateSupported(stPass.eQueue, stAccess.eState))
		{
			return Fail(out_stDiagnostic, GraphError::UnsupportedQueueState, nPass, stAccess.nResource, "Requested resource state is unsupported on this queue.");
		}
		std::vector<bool> &arrSubresources = arrAccessed[stAccess.nResource];
		if (arrSubresources.empty())
		{
			arrSubresources.assign(stResource.nSubresourceCount, false);
		}
		for (std::uint32_t nOffset = 0; nOffset < nCount; ++nOffset)
		{
			const std::uint32_t nSubresource = stAccess.nFirstSubresource + nOffset;
			if (arrSubresources[nSubresource])
			{
				return Fail(out_stDiagnostic, GraphError::OverlappingAccess, nPass, stAccess.nResource, "A pass declares overlapping accesses to one subresource.");
			}
			arrSubresources[nSubresource] = true;
		}
	}
	return true;
}

bool SortPasses(const std::vector<std::vector<PassId>> &arrDependencies, std::vector<PassId> &out_arrOrder, GraphDiagnostic &out_stDiagnostic)
{
	std::vector<std::uint32_t> arrRemainingDependencies;
	std::vector<std::vector<PassId>> arrConsumers(arrDependencies.size());
	for (PassId nPass = 0; nPass < arrDependencies.size(); ++nPass)
	{
		arrRemainingDependencies.push_back(static_cast<std::uint32_t>(arrDependencies[nPass].size()));
		for (PassId nDependency : arrDependencies[nPass])
		{
			arrConsumers[nDependency].push_back(nPass);
		}
	}
	std::vector<bool> arrEmitted(arrDependencies.size(), false);
	while (out_arrOrder.size() < arrDependencies.size())
	{
		PassId nReady = INVALID_PASS;
		for (PassId nPass = 0; nPass < arrDependencies.size(); ++nPass)
		{
			if (!arrEmitted[nPass] && arrRemainingDependencies[nPass] == 0)
			{
				nReady = nPass;
				break;
			}
		}
		if (nReady == INVALID_PASS)
		{
			return Fail(out_stDiagnostic, GraphError::DependencyCycle, INVALID_PASS, INVALID_RESOURCE, "Pass dependencies contain a cycle.");
		}
		arrEmitted[nReady] = true;
		out_arrOrder.push_back(nReady);
		for (PassId nConsumer : arrConsumers[nReady])
		{
			--arrRemainingDependencies[nConsumer];
		}
	}
	return true;
}

void AddTransition(std::vector<ResourceBarrier> &out_arrBarriers, ResourceId nResource, std::uint32_t nSubresource, ResourceState eBefore, ResourceState eAfter)
{
	if (eBefore != eAfter)
	{
		out_arrBarriers.push_back(ResourceBarrier{ BarrierKind::Transition, nResource, nSubresource, eBefore, eAfter });
	}
}

} // namespace

ResourceId FrameGraph::AddResource(const ResourceDesc &stDescription)
{
	if (stDescription.strName.empty() || stDescription.strName.size() > 256 || !IsStateValid(stDescription.eInitialState) ||
		stDescription.nSubresourceCount == 0 || stDescription.nSubresourceCount > MAX_RESOURCE_SUBRESOURCES ||
		arrResources.size() >= MAX_GRAPH_RESOURCES || stDescription.nSubresourceCount > MAX_GRAPH_SUBRESOURCES - nTotalSubresources)
	{
		return INVALID_RESOURCE;
	}
	const ResourceId nResource = static_cast<ResourceId>(arrResources.size());
	arrResources.push_back(stDescription);
	nTotalSubresources += stDescription.nSubresourceCount;
	return nResource;
}

PassId FrameGraph::AddPass(const PassDesc &stDescription)
{
	if (stDescription.strName.empty() || stDescription.strName.size() > 256 || arrPasses.size() >= MAX_GRAPH_PASSES ||
		stDescription.arrAccesses.size() > MAX_GRAPH_DECLARATIONS - nTotalAccesses ||
		stDescription.arrDependencies.size() > MAX_GRAPH_DECLARATIONS - nTotalDependencies)
	{
		return INVALID_PASS;
	}
	const PassId nPass = static_cast<PassId>(arrPasses.size());
	arrPasses.push_back(stDescription);
	nTotalAccesses += static_cast<std::uint32_t>(stDescription.arrAccesses.size());
	nTotalDependencies += static_cast<std::uint32_t>(stDescription.arrDependencies.size());
	return nPass;
}

bool FrameGraph::Compile(CompiledGraph &out_stGraph, GraphDiagnostic &out_stDiagnostic) const
{
	out_stDiagnostic = GraphDiagnostic{};
	std::vector<std::vector<PassId>> arrDependencies(arrPasses.size());
	std::vector<std::vector<SubresourceUsage>> arrUsages;
	std::vector<PassId> arrLastResourcePass(arrResources.size(), INVALID_PASS);
	for (const ResourceDesc &stResource : arrResources)
	{
		arrUsages.emplace_back(stResource.nSubresourceCount, SubresourceUsage{ INVALID_PASS, stResource.eInitialState, stResource.bImported, false });
	}
	std::uint32_t nExpandedAccesses = 0;
	for (PassId nPass = 0; nPass < arrPasses.size(); ++nPass)
	{
		const PassDesc &stPass = arrPasses[nPass];
		if (!ValidatePass(stPass, nPass, arrResources, arrPasses.size(), out_stDiagnostic))
		{
			return false;
		}
		for (PassId nDependency : stPass.arrDependencies)
		{
			AddUnique(arrDependencies[nPass], nDependency);
		}
		for (const ResourceAccess &stAccess : stPass.arrAccesses)
		{
			// D3D12 queue write ownership is resource-wide, even when mip ranges
			// do not overlap. Serialize resource users while tracking each state
			// transition at subresource granularity.
			PassId &nLastResourcePass = arrLastResourcePass[stAccess.nResource];
			if (nLastResourcePass != INVALID_PASS && nLastResourcePass != nPass)
			{
				AddUnique(arrDependencies[nPass], nLastResourcePass);
			}
			nLastResourcePass = nPass;
			const std::uint32_t nCount = GetAccessCount(stAccess, arrResources[stAccess.nResource]);
			if (nCount > MAX_GRAPH_SUBRESOURCE_ACCESSES - nExpandedAccesses)
			{
				return Fail(out_stDiagnostic, GraphError::CapacityExceeded, nPass, stAccess.nResource, "Expanded subresource accesses exceed the graph limit.");
			}
			nExpandedAccesses += nCount;
			for (std::uint32_t nOffset = 0; nOffset < nCount; ++nOffset)
			{
				SubresourceUsage &stUsage = arrUsages[stAccess.nResource][stAccess.nFirstSubresource + nOffset];
				// Serialize subresource users, including readers, so ownership is unambiguous.
				if (stUsage.nLastPass != INVALID_PASS)
				{
					AddUnique(arrDependencies[nPass], stUsage.nLastPass);
				}
				stUsage.nLastPass = nPass;
			}
		}
	}

	std::vector<PassId> arrOrder;
	if (!SortPasses(arrDependencies, arrOrder, out_stDiagnostic))
	{
		return false;
	}
	CompiledGraph stResult;
	std::vector<std::uint32_t> arrPassIndices(arrPasses.size(), INVALID_PASS);
	for (ResourceId nResource = 0; nResource < arrResources.size(); ++nResource)
	{
		const ResourceDesc &stDescription = arrResources[nResource];
		CompiledResource stResource;
		stResource.nResource = nResource;
		stResource.stDescription = stDescription;
		stResource.nAllocationId = nResource;
		stResource.arrFinalStates.assign(stDescription.nSubresourceCount, stDescription.eInitialState);
		stResult.arrResources.push_back(std::move(stResource));
		arrUsages[nResource].assign(stDescription.nSubresourceCount, SubresourceUsage{ INVALID_PASS, stDescription.eInitialState, stDescription.bImported, false });
	}
	for (PassId nPass : arrOrder)
	{
		const PassDesc &stDescription = arrPasses[nPass];
		CompiledPass stPass;
		stPass.nPass = nPass;
		stPass.strName = stDescription.strName;
		stPass.eQueue = stDescription.eQueue;
		stPass.arrAccesses = stDescription.arrAccesses;
		for (PassId nDependency : arrDependencies[nPass])
		{
			if (arrPasses[nDependency].eQueue != stPass.eQueue)
			{
				AddUnique(stPass.arrWaits, nDependency);
				stResult.arrPasses[arrPassIndices[nDependency]].bSignalRequired = true;
			}
		}
		for (const ResourceAccess &stAccess : stDescription.arrAccesses)
		{
			CompiledResource &stResource = stResult.arrResources[stAccess.nResource];
			const std::uint32_t nUseIndex = static_cast<std::uint32_t>(stResult.arrPasses.size());
			if (stResource.nFirstPass == INVALID_PASS)
			{
				stResource.nFirstPass = nPass;
				stResource.nFirstUseIndex = nUseIndex;
			}
			stResource.nLastPass = nPass;
			stResource.nLastUseIndex = nUseIndex;
			stResource.nQueueMask |= static_cast<std::uint8_t>(1U << static_cast<std::uint8_t>(stPass.eQueue));
			const std::uint32_t nCount = GetAccessCount(stAccess, stResource.stDescription);
			for (std::uint32_t nOffset = 0; nOffset < nCount; ++nOffset)
			{
				const std::uint32_t nSubresource = stAccess.nFirstSubresource + nOffset;
				SubresourceUsage &stUsage = arrUsages[stAccess.nResource][nSubresource];
				const bool bNeedsContents = stAccess.eState != ResourceState::Common && (!stAccess.bWrite || stAccess.bReadBeforeWrite);
				if (bNeedsContents && !stUsage.bInitialized)
				{
					return Fail(out_stDiagnostic, GraphError::UninitializedRead, nPass, stAccess.nResource, "Pass reads a transient subresource before its first write.");
				}
				if (stUsage.nLastPass != INVALID_PASS && arrPasses[stUsage.nLastPass].eQueue != stPass.eQueue)
				{
					CompiledPass &stProducer = stResult.arrPasses[arrPassIndices[stUsage.nLastPass]];
					AddTransition(stProducer.arrAfterBarriers, stAccess.nResource, nSubresource, stUsage.eState, ResourceState::Common);
					stUsage.eState = ResourceState::Common;
				}
				if (!IsQueueStateSupported(stPass.eQueue, stUsage.eState))
				{
					return Fail(out_stDiagnostic, GraphError::UnsupportedQueueState, nPass, stAccess.nResource, "Initial resource state requires a release on a compatible queue before use.");
				}
				if (stUsage.eState == ResourceState::UnorderedAccess && stAccess.eState == ResourceState::UnorderedAccess && (stUsage.bLastWrite || stAccess.bWrite))
				{
					stPass.arrBeforeBarriers.push_back(ResourceBarrier{ BarrierKind::Uav, stAccess.nResource, nSubresource, stUsage.eState, stAccess.eState });
				}
				AddTransition(stPass.arrBeforeBarriers, stAccess.nResource, nSubresource, stUsage.eState, stAccess.eState);
				stUsage.eState = stAccess.eState;
				stUsage.nLastPass = nPass;
				stUsage.bLastWrite = stAccess.bWrite;
				stUsage.bInitialized = stUsage.bInitialized || stAccess.bWrite;
				stResource.arrFinalStates[nSubresource] = stAccess.eState;
			}
		}
		std::sort(stPass.arrWaits.begin(), stPass.arrWaits.end());
		arrPassIndices[nPass] = static_cast<std::uint32_t>(stResult.arrPasses.size());
		stResult.arrPasses.push_back(std::move(stPass));
	}
	out_stGraph = std::move(stResult);
	return true;
}

void FrameGraph::Clear() noexcept
{
	arrResources.clear();
	arrPasses.clear();
	nTotalSubresources = 0;
	nTotalAccesses = 0;
	nTotalDependencies = 0;
}

} // namespace EngineNext::Rendering
