/**************************************************************************/
/*  RayTracingScene.h                                                     */
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

#include "engine_next/Platform/Windows/RhiComOwner.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <d3d12.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

constexpr std::uint32_t RAY_TRACING_FRAME_COUNT = 3;
constexpr std::uint32_t NO_RAY_TRACING_FRAME = RAY_TRACING_FRAME_COUNT;

struct RayTracingLimits
{
	std::uint32_t nMaxInstances = 65536;
	std::uint32_t nMaxGeometries = 65536;
	std::uint64_t nMaxResidentBytes = 512ULL * 1024 * 1024;
	std::uint64_t nMaxScratchBytes = 256ULL * 1024 * 1024;
	std::uint64_t nMaxUploadBytes = 256ULL * 1024 * 1024;
};

struct RayTracingMemory
{
	std::uint64_t nResidentBytes = 0;
	std::uint64_t nScratchBytes = 0;
	std::uint64_t nUploadBytes = 0;
	std::uint64_t nGeometryPayloadBytes = 0;
	std::uint64_t nAccelerationPayloadBytes = 0;
	std::uint64_t nRetiredScratchBytes = 0;
	std::uint64_t nRetiredUploadBytes = 0;
};

struct RayTracingDraw
{
	std::uint32_t nFirstIndex = 0;
	std::uint32_t nBaseVertex = 0;
	std::uint32_t nMaterial = 0;
	std::uint32_t nIndexCount = 0;
};
struct RayTracingMaterial
{
	std::array<float, 4> arrBaseColor{};
	std::array<float, 4> arrEmissive{};
	// Normal scale is zero when the source has no normal texture.
	std::array<float, 4> arrSurface{};
	std::uint32_t nBaseTexture = UINT32_MAX;
	std::uint32_t nBaseSampler = UINT32_MAX;
	std::uint32_t nAlphaMode = 0;
	float fAlphaCutoff = 0.5F;
};
struct RayTracingIdentity
{
	std::uint64_t nEntityId = 0;
	std::uint32_t nAsset = 0;
	std::uint32_t nPrimitive = 0;
	std::uint32_t nNode = 0;
	std::uint32_t nGeometry = 0;
};
struct RayTracingTextureBinding
{
	std::uint32_t nAsset = 0;
	std::uint32_t nTexture = 0;
	TextureData stSource;
};
struct RayTracingSourceMaterial
{
	std::uint32_t nAsset = 0;
	std::uint32_t nMaterial = 0;
	MaterialData stSource;
};
static_assert(sizeof(MeshVertex) == 48);
static_assert(offsetof(MeshVertex, arrTexcoord) == 40);
static_assert(sizeof(RayTracingDraw) == 16);
static_assert(sizeof(RayTracingMaterial) == 64);
static_assert(offsetof(RayTracingMaterial, arrSurface) == 32);
static_assert(offsetof(RayTracingMaterial, nBaseTexture) == 48);

// Private D3D12 backend object. One owner thread and one DIRECT graphics queue
// fence domain are required. Device/list parameters are borrowed for the call.
// All owned resources must be Release'd after their final fence before object
// destruction or move-assignment by the host. No command list is submitted here.
class RayTracingScene final
{
public:
	RayTracingScene() = default;
	RayTracingScene(const RayTracingScene &) = delete;
	RayTracingScene &operator=(const RayTracingScene &) = delete;
	RayTracingScene(RayTracingScene &&stOther) noexcept;
	RayTracingScene &operator=(RayTracingScene &&stOther) noexcept;

	[[nodiscard]] static bool CheckCapabilities(ID3D12Device *pDevice, Assets::Diagnostics &out_arrDiagnostics);
	// Existing resources must already be retired. Candidate allocation and
	// source validation are transactional. Source pointers are never retained.
	[[nodiscard]] bool Prepare(ID3D12Device5 *pDevice, const RenderScene &stSource, const RayTracingLimits &stLimits, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	// Worlds follow Identities() order. The selected slot must be retired.
	// This records geometry copies/BLAS once and TLAS build or update per slot.
	[[nodiscard]] bool RecordBuildOrUpdate(std::uint32_t nFrame, ID3D12GraphicsCommandList4 *pList, const std::vector<std::array<double, 16>> &arrWorlds, std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	// Call after ExecuteCommandLists and successful signal on the same queue.
	[[nodiscard]] bool CommitSubmission(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	// Call only after discarding/resetting the unsubmitted command list.
	[[nodiscard]] bool CancelRecorded(std::uint32_t nFrame, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool MarkUsed(std::uint32_t nFrame, std::uint64_t nFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Retire(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Release(std::uint64_t nCompletedFence, Assets::Diagnostics &out_arrDiagnostics);

	D3D12_GPU_VIRTUAL_ADDRESS TlasAddress(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *TlasResource(std::uint32_t nFrame) const noexcept;
	ID3D12Resource *VertexBuffer() const noexcept;
	ID3D12Resource *IndexBuffer() const noexcept;
	ID3D12Resource *DrawBuffer() const noexcept;
	ID3D12Resource *MaterialBuffer() const noexcept;
	const std::vector<RayTracingIdentity> &Identities() const noexcept;
	const std::vector<RayTracingTextureBinding> &TextureBindings() const noexcept;
	const std::vector<RayTracingSourceMaterial> &SourceMaterials() const noexcept;
	const RayTracingMemory &Memory() const noexcept;

private:
	struct Geometry
	{
		D3D12_RAYTRACING_GEOMETRY_DESC stDescription{};
		std::uint64_t nResultOffset = 0;
	};
	struct Frame
	{
		ComOwner<ID3D12Resource> stTlas;
		ComOwner<ID3D12Resource> stScratch;
		ComOwner<ID3D12Resource> stInstances;
		std::uint64_t nFence = 0;
		bool bBuilt = false;
	};
	bool IsOwner() const noexcept;
	bool CanRelease(std::uint64_t nCompletedFence) const noexcept;

	DWORD nOwnerThread = 0;
	std::vector<Geometry> arrGeometry;
	std::vector<RayTracingIdentity> arrIdentities;
	std::vector<RayTracingTextureBinding> arrTextures;
	std::vector<RayTracingSourceMaterial> arrSourceMaterials;
	std::vector<D3D12_RAYTRACING_INSTANCE_DESC> arrInstances;
	std::array<Frame, RAY_TRACING_FRAME_COUNT> arrFrames;
	ComOwner<ID3D12Resource> stVertices;
	ComOwner<ID3D12Resource> stIndices;
	ComOwner<ID3D12Resource> stDraws;
	ComOwner<ID3D12Resource> stMaterials;
	ComOwner<ID3D12Resource> stBlas;
	ComOwner<ID3D12Resource> stBlasScratch;
	ComOwner<ID3D12Resource> stGeometryUpload;
	std::uint64_t nVertexBytes = 0;
	std::uint64_t nIndexBytes = 0;
	std::uint64_t nIndexUploadOffset = 0;
	std::uint64_t nStaticBuildFence = 0;
	std::uint64_t nLatestFence = 0;
	std::uint64_t nBlasScratchAllocation = 0;
	std::uint64_t nGeometryUploadAllocation = 0;
	std::uint32_t nPendingFrame = NO_RAY_TRACING_FRAME;
	bool bPendingStaticBuild = false;
	bool bStaticBuilt = false;
	bool bPrepared = false;
	RayTracingMemory stMemory;
};

} // namespace EngineNext::Rendering
