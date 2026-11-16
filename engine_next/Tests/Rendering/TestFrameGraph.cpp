/**************************************************************************/
/*  TestFrameGraph.cpp                                                    */
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

#include "engine_next/include/EngineNext/Rendering/FrameGraph.h"

#include <cstdint>
#include <vector>

namespace
{

using EngineNext::Rendering::BarrierKind;
using EngineNext::Rendering::CompiledGraph;
using EngineNext::Rendering::FrameGraph;
using EngineNext::Rendering::GraphDiagnostic;
using EngineNext::Rendering::GraphError;
using EngineNext::Rendering::PassDesc;
using EngineNext::Rendering::PassId;
using EngineNext::Rendering::QueueType;
using EngineNext::Rendering::ResourceAccess;
using EngineNext::Rendering::ResourceDesc;
using EngineNext::Rendering::ResourceId;
using EngineNext::Rendering::ResourceState;

PassDesc MakePass(const char *pName, QueueType eQueue, ResourceId nResource, ResourceState eState, bool bWrite)
{
	PassDesc stPass;
	stPass.strName = pName;
	stPass.eQueue = eQueue;
	stPass.arrAccesses.push_back(ResourceAccess{ nResource, eState, bWrite });
	return stPass;
}

} // namespace

ENGINE_NEXT_TEST("FrameGraph emits fixed mesh transitions and a compute handoff")
{
	FrameGraph stGraph;
	const ResourceId nTint = stGraph.AddResource(ResourceDesc{ "Tint", ResourceState::Common, false });
	const ResourceId nColor = stGraph.AddResource(ResourceDesc{ "Color", ResourceState::Common, false });
	const ResourceId nBackbuffer = stGraph.AddResource(ResourceDesc{ "Backbuffer", ResourceState::Present, true });
	const PassId nCompute = stGraph.AddPass(MakePass("ComputeTint", QueueType::Compute, nTint, ResourceState::UnorderedAccess, true));
	PassDesc stDraw = MakePass("FixedMesh", QueueType::Graphics, nColor, ResourceState::RenderTarget, true);
	stDraw.arrAccesses.push_back(ResourceAccess{ nTint, ResourceState::ShaderRead, false });
	const PassId nDraw = stGraph.AddPass(stDraw);
	PassDesc stCopy = MakePass("CopyToBackbuffer", QueueType::Graphics, nColor, ResourceState::CopySource, false);
	stCopy.arrAccesses.push_back(ResourceAccess{ nBackbuffer, ResourceState::CopyDestination, true });
	const PassId nCopy = stGraph.AddPass(stCopy);
	PassDesc stPresent = MakePass("Present", QueueType::Graphics, nBackbuffer, ResourceState::Present, false);
	stPresent.arrAccesses.push_back(ResourceAccess{ nTint, ResourceState::Common, false });
	const PassId nPresent = stGraph.AddPass(stPresent);

	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::None);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].nPass, nCompute);
	ENGINE_NEXT_CHECK(stCompiled.arrPasses[0].bSignalRequired);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].arrBeforeBarriers.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].arrAfterBarriers.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].arrAfterBarriers[0].eBefore, ResourceState::UnorderedAccess);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].arrAfterBarriers[0].eAfter, ResourceState::Common);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].nPass, nDraw);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrWaits, std::vector<PassId>{ nCompute });
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers[1].eBefore, ResourceState::Common);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers[1].eAfter, ResourceState::ShaderRead);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[2].nPass, nCopy);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[3].nPass, nPresent);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[nTint].arrFinalStates[0], ResourceState::Common);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[nBackbuffer].arrFinalStates[0], ResourceState::Present);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[nColor].nFirstPass, nDraw);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[nColor].nLastPass, nCopy);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[nTint].nQueueMask, 3U);
}

ENGINE_NEXT_TEST("FrameGraph topological sorting honors forward independent dependencies")
{
	FrameGraph stGraph;
	PassDesc stFirst;
	stFirst.strName = "Dependent";
	stFirst.arrDependencies.push_back(1);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stFirst), 0U);
	PassDesc stSecond;
	stSecond.strName = "Producer";
	stSecond.eQueue = QueueType::Compute;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stSecond), 1U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].nPass, 1U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].nPass, 0U);
	ENGINE_NEXT_CHECK(stCompiled.arrPasses[0].bSignalRequired);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrWaits, std::vector<PassId>{ 1 });
}

ENGINE_NEXT_TEST("FrameGraph rejects unknown dependencies and cycles without replacing output")
{
	FrameGraph stGraph;
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	PassDesc stFirst;
	stFirst.strName = "First";
	stFirst.arrDependencies.push_back(1);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stFirst), 0U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::InvalidDependency);
	ENGINE_NEXT_CHECK(stCompiled.arrPasses.empty());
	PassDesc stSecond;
	stSecond.strName = "Second";
	stSecond.arrDependencies.push_back(0);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stSecond), 1U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::DependencyCycle);
	ENGINE_NEXT_CHECK(stCompiled.arrPasses.empty());
}

ENGINE_NEXT_TEST("FrameGraph rejects transient reads and read modify write before initialization")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "Uninitialized", ResourceState::Common, false });
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("Read", QueueType::Graphics, nResource, ResourceState::ShaderRead, false)), 0U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::UninitializedRead);
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.nResource, nResource);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "ReadModifyWrite", ResourceState::Common, false }), 0U);
	PassDesc stPass = MakePass("ReadModifyWrite", QueueType::Compute, 0, ResourceState::UnorderedAccess, true);
	stPass.arrAccesses[0].bReadBeforeWrite = true;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stPass), 0U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::UninitializedRead);
}

ENGINE_NEXT_TEST("FrameGraph serializes unordered accesses with UAV barriers")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "Storage", ResourceState::Common, false });
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("Write", QueueType::Compute, nResource, ResourceState::UnorderedAccess, true)), 0U);
	PassDesc stModify = MakePass("Modify", QueueType::Compute, nResource, ResourceState::UnorderedAccess, true);
	stModify.arrAccesses[0].bReadBeforeWrite = true;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stModify), 1U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("Read", QueueType::Compute, nResource, ResourceState::UnorderedAccess, false)), 2U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers[0].eKind, BarrierKind::Uav);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[2].arrBeforeBarriers[0].eKind, BarrierKind::Uav);
}

ENGINE_NEXT_TEST("FrameGraph tracks initialization and transitions per subresource")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "MipChain", ResourceState::Common, false, 2 });
	PassDesc stWrite = MakePass("WriteMip0", QueueType::Graphics, nResource, ResourceState::RenderTarget, true);
	stWrite.arrAccesses[0].nSubresourceCount = 1;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stWrite), 0U);
	PassDesc stWriteSecond = MakePass("WriteMip1", QueueType::Compute, nResource, ResourceState::UnorderedAccess, true);
	stWriteSecond.arrAccesses[0].nFirstSubresource = 1;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stWriteSecond), 1U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("ReadAllMips", QueueType::Graphics, nResource, ResourceState::ShaderRead, false)), 2U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].arrBeforeBarriers[0].nSubresource, 0U);
	ENGINE_NEXT_CHECK(stCompiled.arrPasses[0].bSignalRequired);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrWaits, std::vector<PassId>{ 0 });
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers[0].nSubresource, 1U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[2].arrBeforeBarriers.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[2].arrWaits, std::vector<PassId>{ 1 });
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[0].arrFinalStates.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[0].arrFinalStates[1], ResourceState::ShaderRead);
}

ENGINE_NEXT_TEST("FrameGraph serializes queue ownership for disjoint texture writes")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "TwoMips", ResourceState::Common, false, 2 });
	PassDesc stGraphics = MakePass("GraphicsMip", QueueType::Graphics, nResource, ResourceState::RenderTarget, true);
	stGraphics.arrAccesses[0].nSubresourceCount = 1;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stGraphics), 0U);
	PassDesc stCompute = MakePass("ComputeMip", QueueType::Compute, nResource, ResourceState::UnorderedAccess, true);
	stCompute.arrAccesses[0].nFirstSubresource = 1;
	stCompute.arrAccesses[0].nSubresourceCount = 1;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stCompute), 1U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK(stCompiled.arrPasses[0].bSignalRequired);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrWaits, std::vector<PassId>{ 0 });
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[0].arrFinalStates[0], ResourceState::RenderTarget);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[0].arrFinalStates[1], ResourceState::UnorderedAccess);
}

ENGINE_NEXT_TEST("FrameGraph rejects overlapping and out of bounds subresource ranges")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "Image", ResourceState::Common, true, 2 });
	PassDesc stPass = MakePass("Conflicting", QueueType::Graphics, nResource, ResourceState::ShaderRead, false);
	stPass.arrAccesses.push_back(ResourceAccess{ nResource, ResourceState::CopyDestination, true, 1, 1 });
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stPass), 0U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::OverlappingAccess);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "Image", ResourceState::Common, true, 2 }), 0U);
	stPass.arrAccesses.resize(1);
	stPass.arrAccesses[0].nFirstSubresource = 1;
	stPass.arrAccesses[0].nSubresourceCount = 2;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stPass), 0U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::InvalidAccess);
}

ENGINE_NEXT_TEST("FrameGraph enforces queue capabilities including inherited initial states")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "PixelInput", ResourceState::ShaderRead, true });
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("Unsupported", QueueType::Compute, nResource, ResourceState::ShaderRead, false)), 0U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::UnsupportedQueueState);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "PixelInput", ResourceState::ShaderRead, true }), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("NeedsGraphicsRelease", QueueType::Compute, 0, ResourceState::UnorderedAccess, true)), 0U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::UnsupportedQueueState);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "CopyInput", ResourceState::Common, true }), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("Copy", QueueType::Copy, 0, ResourceState::CopySource, false)), 0U);
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
}

ENGINE_NEXT_TEST("FrameGraph reports invalid handles and access modes")
{
	FrameGraph stGraph;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("Unknown", QueueType::Graphics, 17, ResourceState::ShaderRead, false)), 0U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::InvalidResource);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "Image", ResourceState::Common, true }), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("IncorrectWrite", QueueType::Graphics, 0, ResourceState::ShaderRead, true)), 0U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::InvalidAccess);
}

ENGINE_NEXT_TEST("FrameGraph keeps distinct allocations for asynchronous transient lifetimes")
{
	FrameGraph stGraph;
	const ResourceId nFirst = stGraph.AddResource(ResourceDesc{ "First", ResourceState::Common, false });
	const ResourceId nSecond = stGraph.AddResource(ResourceDesc{ "Second", ResourceState::Common, false });
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("FirstCompute", QueueType::Compute, nFirst, ResourceState::UnorderedAccess, true)), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("SecondGraphics", QueueType::Graphics, nSecond, ResourceState::RenderTarget, true)), 1U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK(stCompiled.arrPasses[1].arrWaits.empty());
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[0].nAllocationId, nFirst);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[1].nAllocationId, nSecond);
	ENGINE_NEXT_CHECK(stCompiled.arrResources[0].nAllocationId != stCompiled.arrResources[1].nAllocationId);
}

ENGINE_NEXT_TEST("FrameGraph descriptor limits are bounded and clear resets handles")
{
	FrameGraph stGraph;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{}), EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "Invalid", ResourceState::Undefined, false }), EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "Empty", ResourceState::Common, false, 0 }), EngineNext::Rendering::INVALID_RESOURCE);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(PassDesc{}), EngineNext::Rendering::INVALID_PASS);
	for (std::uint32_t nIndex = 0; nIndex < EngineNext::Rendering::MAX_GRAPH_RESOURCES; ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "Bounded", ResourceState::Common, false }), nIndex);
	}
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "Overflow", ResourceState::Common, false }), EngineNext::Rendering::INVALID_RESOURCE);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource(ResourceDesc{ "AfterClear", ResourceState::Common, false }), 0U);
}

ENGINE_NEXT_TEST("FrameGraph preserves a prior plan when a later declaration fails")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "Imported", ResourceState::Common, true });
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("ReadImported", QueueType::Graphics, nResource, ResourceState::ShaderRead, false)), 0U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("Invalid", QueueType::Graphics, 42, ResourceState::ShaderRead, false)), 1U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[0].strName, "ReadImported");
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[0].arrFinalStates[0], ResourceState::ShaderRead);
}

ENGINE_NEXT_TEST("FrameGraph bounds expanded subresource work before creating a plan")
{
	FrameGraph stGraph;
	const ResourceId nResource = stGraph.AddResource(ResourceDesc{ "LargeArray", ResourceState::Common, true, EngineNext::Rendering::MAX_RESOURCE_SUBRESOURCES });
	for (std::uint32_t nIndex = 0; nIndex <= EngineNext::Rendering::MAX_GRAPH_SUBRESOURCE_ACCESSES / EngineNext::Rendering::MAX_RESOURCE_SUBRESOURCES; ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("ReadArray", QueueType::Graphics, nResource, ResourceState::ShaderRead, false)), nIndex);
	}
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::CapacityExceeded);
	ENGINE_NEXT_CHECK(stCompiled.arrPasses.empty());
}

ENGINE_NEXT_TEST("FrameGraph supports read-only depth on graphics and restores depth writes")
{
	FrameGraph stGraph;
	const ResourceId nDepth = stGraph.AddResource({ "Depth", ResourceState::DepthWrite, false });
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("WriteDepth", QueueType::Graphics, nDepth, ResourceState::DepthWrite, true)), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("ReadDepth", QueueType::Graphics, nDepth, ResourceState::DepthRead, false)), 1U);
	PassDesc stRestore = MakePass("RestoreDepth", QueueType::Graphics, nDepth, ResourceState::DepthWrite, true);
	stRestore.arrAccesses[0].bReadBeforeWrite = true;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(stRestore), 2U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers[0].eBefore, ResourceState::DepthWrite);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[1].arrBeforeBarriers[0].eAfter, ResourceState::DepthRead);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[2].arrBeforeBarriers[0].eBefore, ResourceState::DepthRead);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrPasses[2].arrBeforeBarriers[0].eAfter, ResourceState::DepthWrite);
	ENGINE_NEXT_CHECK_EQ(stCompiled.arrResources[nDepth].arrFinalStates[0], ResourceState::DepthWrite);
}

ENGINE_NEXT_TEST("FrameGraph rejects depth reads on compute and depth reads declared as writes")
{
	FrameGraph stGraph;
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource({ "Depth", ResourceState::Common, true }), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("ComputeDepth", QueueType::Compute, 0, ResourceState::DepthRead, false)), 0U);
	CompiledGraph stCompiled;
	GraphDiagnostic stDiagnostic;
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::UnsupportedQueueState);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource({ "Depth", ResourceState::DepthRead, true }), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("IncompatibleInitialDepth", QueueType::Compute, 0, ResourceState::UnorderedAccess, true)), 0U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::UnsupportedQueueState);
	stGraph.Clear();
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource({ "Depth", ResourceState::Common, true }), 0U);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddPass(MakePass("InvalidDepthWrite", QueueType::Graphics, 0, ResourceState::DepthRead, true)), 0U);
	ENGINE_NEXT_CHECK(!stGraph.Compile(stCompiled, stDiagnostic));
	ENGINE_NEXT_CHECK_EQ(stDiagnostic.eError, GraphError::InvalidAccess);
	ENGINE_NEXT_CHECK_EQ(stGraph.AddResource({ "UnknownState", static_cast<ResourceState>(11), true }), EngineNext::Rendering::INVALID_RESOURCE);
}
