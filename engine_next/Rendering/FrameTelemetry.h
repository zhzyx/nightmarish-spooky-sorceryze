/**************************************************************************/
/*  FrameTelemetry.h                                                      */
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

#include "engine_next/include/EngineNext/Rendering/FrameGraph.h"
#include "engine_next/include/EngineNext/Assets/Types.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include "engine_next/Rendering/ShadowPageCache.h"
#include "engine_next/include/EngineNext/Rendering/TextureResidency.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

struct RecordingThreadStatistics
{
	std::uint32_t nThreadId = 0;
	std::uint32_t nLists = 0;
	std::uint64_t nDraws = 0;
	std::uint64_t nBeginQpc = 0;
	std::uint64_t nEndQpc = 0;
};

struct RecordingStatistics
{
	std::uint32_t nThreads = 1;
	std::uint32_t nExecutedBundles = 0;
	double dBatchMsec = 0;
	std::array<RecordingThreadStatistics, 4> arrThreads{};
};

// Shared by the bounded ordinary report and the optional full-session stream.
// QPC values are CPU observations. Completion is observed after fence retirement;
// Present return is not scanout and the latest window event need not cause this frame.
struct FrameTiming
{
	RecordingStatistics stRecording;
	TextureResidencyTelemetry stTextures;
	std::uint64_t nTextureChangeSerial = 0;
	std::uint64_t nRayPrimary = 0;
	std::uint64_t nRayScreenHits = 0;
	std::uint64_t nRaySceneHits = 0;
	std::uint64_t nRayMisses = 0;
	std::uint64_t nRayInvalid = 0;
	std::uint64_t nRayShadowRays = 0;
	std::uint64_t nRayWitnessRays = 0;
	ShadowPageStatistics stShadowPages;
	std::array<std::uint32_t, 4> arrShadowFeedback{};
	bool bCoarseShadowReused = false;
	std::uint32_t nFrame = 0;
	std::uint64_t nSceneInstances = 0;
	std::uint64_t nSceneTriangles = 0;
	std::uint64_t nVisibleGeometryDraws = 0;
	std::uint64_t nVisibleGeometryTriangles = 0;
	bool bGeometryCountersReady = false;
	std::uint32_t nBackbufferWidth = 0;
	std::uint32_t nBackbufferHeight = 0;
	std::uint32_t nOutputWidth = 0;
	std::uint32_t nOutputHeight = 0;
	std::uint32_t nRenderScalePercent = 100;
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint64_t nGraphicsFence = 0;
	std::uint64_t nComputeFence = 0;
	std::uint64_t nTemporalEpoch = 0;
	std::uint32_t nTemporalSample = 0;
	std::uint32_t nTemporalRead = 0;
	std::array<double, 2> arrTemporalJitter{};
	std::array<float, 4> arrExposure{};
	std::uint32_t nMeterFinite = 0;
	std::uint32_t nMeterInvalid = 0;
	bool bPostReady = false;
	double dLightingSeconds = 0;
	double dDirectionalIlluminance = 0;
	double dAnimationSeconds = 0;
	double dAnimationCpuMsec = 0;
	double dAnimationMaxMotion = 0;
	std::uint64_t nAnimatedVertices = 0;
	std::uint32_t nAnimationGiChangedDraws = 0;
	bool bAnimationHistoryValid = false;
	bool bTemporalHistoryValid = false;
	bool bVolumeHistoryValid = false;
	std::uint32_t nVolumeHistoryRead = 0;
	std::uint32_t nParticles = 0;
	bool bPagedLod = false;
	std::uint64_t nPageCandidates = 0;
	std::uint64_t nPageTriangles = 0;
	std::uint64_t nPageResidentBytes = 0;
	std::uint64_t nPageReadRequests = 0;
	double dCpuMsec = 0.0;
	double dGraphicsMsec = 0.0;
	double dComputeMsec = 0.0;
	std::vector<double> arrPassMsec;
	bool bGpuReady = false;

	std::uint64_t nGraphEpoch = 0;
	std::uint64_t nFrameBeginQpc = 0;
	std::uint64_t nCpuEndQpc = 0;
	std::uint64_t nWindowEventQpc = 0;
	std::uint64_t nInputRevision = 0;
	std::uint64_t nInputReceivedQpc = 0;
	std::uint64_t nInputReceipts = 0;
	bool bNewInput = false;
	std::uint64_t nInputObservedQpc = 0;
	std::uint64_t nSubmitQpc = 0;
	std::uint64_t nPresentBeginQpc = 0;
	std::uint64_t nPresentEndQpc = 0;
	std::uint64_t nCompletionObservedQpc = 0;
	double dFenceWaitMsec = 0;
	double dRetireReadbackMsec = 0;
	double dPrepareMsec = 0;
	double dRecordSubmitMsec = 0;
	double dPresentMsec = 0;
	double dAnimationUploadMsec = 0;
	double dPagePrepareMsec = 0;
	std::uint64_t nSynchronousUploadBytes = 0;
	std::uint64_t nSynchronousPageReadBytes = 0;
	std::uint64_t nDedicatedUsageBytes = 0;
	std::uint64_t nDedicatedBudgetBytes = 0;
	std::uint64_t nProcessPrivateBytes = 0;
	std::uint64_t nProcessWorkingSetBytes = 0;
	std::uint64_t nProcessHandles = 0;
	std::uint64_t nGraphResources = 0;
	std::uint64_t nDescriptorCapacity = 0;
	std::uint64_t nAllocatedPageResources = 0;
	std::uint64_t nPageEvictions = 0;
	std::uint64_t nPageStalls = 0;
	bool bMemoryReady = false;
	bool bProcessReady = false;
};

[[nodiscard]] Serialization::JsonValue DescribeTextureTelemetry(const TextureResidencyTelemetry &stTextures, std::uint64_t nTextureChangeSerial);
[[nodiscard]] Serialization::JsonValue DescribeFrameTiming(const FrameTiming &stTiming, const CompiledGraph &stGraph);

// Single render-thread owner. Open refuses an existing destination. One frame and
// at most one graph record are materialized at a time. I/O errors are explicit;
// a missing/unsuccessful footer is an incomplete trace, never a successful run.
class FrameTelemetry final
{
public:
	FrameTelemetry() noexcept = default;
	~FrameTelemetry();
	FrameTelemetry(const FrameTelemetry &) = delete;
	FrameTelemetry &operator=(const FrameTelemetry &) = delete;
	FrameTelemetry(FrameTelemetry &&) = delete;
	FrameTelemetry &operator=(FrameTelemetry &&) = delete;
	[[nodiscard]] bool Open(const std::string &strPath, Serialization::JsonValue stMetadata, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Append(const FrameTiming &stTiming, const CompiledGraph &stGraph, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Finish(bool bSuccess, std::uint64_t nExpectedFrames, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool IsOpen() const noexcept;
	[[nodiscard]] std::uint64_t Records() const noexcept;
	[[nodiscard]] std::uint64_t Bytes() const noexcept;

private:
	[[nodiscard]] bool Write(const Serialization::JsonValue &stValue, Assets::Diagnostics &out_arrDiagnostics);
	std::FILE *pOutput = nullptr;
	std::array<char, 8192> arrBuffer{};
	std::uint64_t nRecords = 0;
	std::uint64_t nBytes = 0;
	std::uint64_t nGraphEpoch = 0;
	bool bFailed = false;
};

} // namespace EngineNext::Rendering
