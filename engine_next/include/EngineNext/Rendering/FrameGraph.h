/**************************************************************************/
/*  FrameGraph.h                                                          */
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

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

using ResourceId = std::uint32_t;
using PassId = std::uint32_t;

constexpr ResourceId INVALID_RESOURCE = std::numeric_limits<ResourceId>::max();
constexpr PassId INVALID_PASS = std::numeric_limits<PassId>::max();
constexpr std::uint32_t ALL_SUBRESOURCES = std::numeric_limits<std::uint32_t>::max();
constexpr std::uint32_t MAX_GRAPH_RESOURCES = 1024;
constexpr std::uint32_t MAX_GRAPH_PASSES = 1024;
constexpr std::uint32_t MAX_RESOURCE_SUBRESOURCES = 4096;
constexpr std::uint32_t MAX_GRAPH_SUBRESOURCES = 65536;
constexpr std::uint32_t MAX_GRAPH_DECLARATIONS = 65536;
constexpr std::uint32_t MAX_GRAPH_SUBRESOURCE_ACCESSES = 262144;

enum class QueueType : std::uint8_t
{
	Graphics = 0,
	Compute = 1,
	Copy = 2,
};

enum class ResourceState : std::uint8_t
{
	Undefined = 0,
	Common = 1,
	CopySource = 2,
	CopyDestination = 3,
	RenderTarget = 4,
	DepthWrite = 5,
	ShaderRead = 6,
	UnorderedAccess = 7,
	Present = 8,
	NonPixelShaderRead = 9,
	DepthRead = 10,
	AccelerationStructure = 11,
	GenericRead = 12,
	IndirectArgument = 13,
};

enum class BarrierKind : std::uint8_t
{
	Transition = 0,
	Uav = 1,
};

enum class GraphError : std::uint8_t
{
	None = 0,
	InvalidResource = 1,
	InvalidPass = 2,
	InvalidAccess = 3,
	OverlappingAccess = 4,
	InvalidDependency = 5,
	DependencyCycle = 6,
	UninitializedRead = 7,
	UnsupportedQueueState = 8,
	CapacityExceeded = 9,
};

struct ResourceDesc
{
	std::string strName;
	ResourceState eInitialState = ResourceState::Common;
	bool bImported = false;
	std::uint32_t nSubresourceCount = 1;
};

struct ResourceAccess
{
	ResourceId nResource = INVALID_RESOURCE;
	ResourceState eState = ResourceState::Undefined;
	bool bWrite = false;
	std::uint32_t nFirstSubresource = 0;
	std::uint32_t nSubresourceCount = ALL_SUBRESOURCES;
	bool bReadBeforeWrite = false;
};

struct PassDesc
{
	std::string strName;
	QueueType eQueue = QueueType::Graphics;
	std::vector<ResourceAccess> arrAccesses;
	std::vector<PassId> arrDependencies;
};

struct ResourceBarrier
{
	BarrierKind eKind = BarrierKind::Transition;
	ResourceId nResource = INVALID_RESOURCE;
	std::uint32_t nSubresource = 0;
	ResourceState eBefore = ResourceState::Undefined;
	ResourceState eAfter = ResourceState::Undefined;
};

struct CompiledPass
{
	PassId nPass = INVALID_PASS;
	std::string strName;
	QueueType eQueue = QueueType::Graphics;
	std::vector<ResourceAccess> arrAccesses;
	std::vector<ResourceBarrier> arrBeforeBarriers;
	std::vector<ResourceBarrier> arrAfterBarriers;
	// Wait for each producer's completion signal before any before-barriers execute.
	std::vector<PassId> arrWaits;
	bool bSignalRequired = false;
};

struct CompiledResource
{
	ResourceId nResource = INVALID_RESOURCE;
	ResourceDesc stDescription;
	PassId nFirstPass = INVALID_PASS;
	PassId nLastPass = INVALID_PASS;
	std::uint32_t nFirstUseIndex = INVALID_PASS;
	std::uint32_t nLastUseIndex = INVALID_PASS;
	std::uint8_t nQueueMask = 0;
	// Every resource has its own allocation. Linear pass indices never authorize aliasing.
	std::uint32_t nAllocationId = INVALID_RESOURCE;
	std::vector<ResourceState> arrFinalStates;
};

struct CompiledGraph
{
	std::vector<CompiledPass> arrPasses;
	std::vector<CompiledResource> arrResources;
};

struct GraphDiagnostic
{
	GraphError eError = GraphError::None;
	PassId nPass = INVALID_PASS;
	ResourceId nResource = INVALID_RESOURCE;
	std::string strMessage;
};

// Build and compile on one owner thread. A successful plan owns copies of all data.
// Access registration order defines resource versions. Dependencies may reorder
// independent passes. Imported resources must already be synchronized by the caller.
class FrameGraph final
{
public:
	// Invalid descriptions or exhausted limits return the corresponding invalid ID.
	[[nodiscard]] ResourceId AddResource(const ResourceDesc &stDescription);
	[[nodiscard]] PassId AddPass(const PassDesc &stDescription);
	// On failure, the last successful output plan is preserved and diagnostic is set.
	[[nodiscard]] bool Compile(CompiledGraph &out_stGraph, GraphDiagnostic &out_stDiagnostic) const;
	void Clear() noexcept;

private:
	std::vector<ResourceDesc> arrResources;
	std::vector<PassDesc> arrPasses;
	std::uint32_t nTotalSubresources = 0;
	std::uint32_t nTotalAccesses = 0;
	std::uint32_t nTotalDependencies = 0;
};

} // namespace EngineNext::Rendering
