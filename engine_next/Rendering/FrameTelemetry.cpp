/**************************************************************************/
/*  FrameTelemetry.cpp                                                    */
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

#include "engine_next/Rendering/FrameTelemetry.h"

#include <filesystem>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
bool Fail(const char *pMessage, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "frame_telemetry", "$.telemetry", pMessage);
	return false;
}
} // namespace

Serialization::JsonValue DescribeTextureTelemetry(const TextureResidencyTelemetry &stTextures, std::uint64_t nTextureChangeSerial)
{
	using Serialization::JsonValue;
	JsonValue::Object mapTextures;
	mapTextures["change_serial"] = JsonValue(std::to_string(nTextureChangeSerial));
	mapTextures["resident_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nResidentBytes));
	mapTextures["retired_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nRetiredBytes));
	mapTextures["pending_gpu_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nPendingGpuBytes));
	mapTextures["gpu_reserved_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nGpuReservedBytes));
	mapTextures["io_reserved_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nIoReservedBytes));
	mapTextures["upload_reserved_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nUploadReservedBytes));
	mapTextures["peak_gpu_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nPeakGpuReservedBytes));
	mapTextures["peak_upload_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nPeakUploadReservedBytes));
	mapTextures["peak_io_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nPeakIoReservedBytes));
	mapTextures["loads"] = JsonValue(static_cast<std::int64_t>(stTextures.nLoadsStarted));
	mapTextures["installs"] = JsonValue(static_cast<std::int64_t>(stTextures.nInstalls));
	mapTextures["cancellations"] = JsonValue(static_cast<std::int64_t>(stTextures.nCancellations));
	mapTextures["failures"] = JsonValue(static_cast<std::int64_t>(stTextures.nFailures));
	mapTextures["budget_stalls"] = JsonValue(static_cast<std::int64_t>(stTextures.nBudgetStalls));
	mapTextures["fallback_floor_bytes"] = JsonValue(static_cast<std::int64_t>(stTextures.nFallbackBudgetBytes));
	return JsonValue(std::move(mapTextures));
}

Serialization::JsonValue DescribeFrameTiming(const FrameTiming &stTiming, const CompiledGraph &stGraph)
{
	using Serialization::JsonValue;
	JsonValue::Object mapTiming;
	mapTiming["frame_id"] = JsonValue(static_cast<std::int64_t>(stTiming.nFrame));
	mapTiming["graph_revision"] = JsonValue(std::int64_t{ 1 });
	mapTiming["scene_instances"] = JsonValue(static_cast<std::int64_t>(stTiming.nSceneInstances));
	mapTiming["scene_triangles"] = JsonValue(static_cast<std::int64_t>(stTiming.nSceneTriangles));
	mapTiming["geometry_visible_draws"] = stTiming.bGeometryCountersReady ? JsonValue(static_cast<std::int64_t>(stTiming.nVisibleGeometryDraws)) : JsonValue();
	mapTiming["geometry_visible_triangles"] = stTiming.bGeometryCountersReady ? JsonValue(static_cast<std::int64_t>(stTiming.nVisibleGeometryTriangles)) : JsonValue();
	mapTiming["upscale_mode"] = JsonValue(std::string(stTiming.nRenderScalePercent == 100 ? "native" : "dxgi_spatial_stretch"));
	mapTiming["render_width"] = JsonValue(static_cast<std::int64_t>(stTiming.nWidth));
	mapTiming["render_height"] = JsonValue(static_cast<std::int64_t>(stTiming.nHeight));
	mapTiming["backbuffer_width"] = JsonValue(static_cast<std::int64_t>(stTiming.nBackbufferWidth));
	mapTiming["backbuffer_height"] = JsonValue(static_cast<std::int64_t>(stTiming.nBackbufferHeight));
	mapTiming["client_output_width"] = JsonValue(static_cast<std::int64_t>(stTiming.nOutputWidth));
	mapTiming["client_output_height"] = JsonValue(static_cast<std::int64_t>(stTiming.nOutputHeight));
	mapTiming["output_width"] = JsonValue(static_cast<std::int64_t>(stTiming.nOutputWidth));
	mapTiming["output_height"] = JsonValue(static_cast<std::int64_t>(stTiming.nOutputHeight));
	mapTiming["render_scale_percent"] = JsonValue(static_cast<std::int64_t>(stTiming.nRenderScalePercent));
	mapTiming["width"] = JsonValue(static_cast<std::int64_t>(stTiming.nWidth));
	mapTiming["height"] = JsonValue(static_cast<std::int64_t>(stTiming.nHeight));
	mapTiming["graphics_fence"] = JsonValue(std::to_string(stTiming.nGraphicsFence));
	mapTiming["compute_fence"] = JsonValue(std::to_string(stTiming.nComputeFence));
	mapTiming["cpu_frame_msec"] = JsonValue(stTiming.dCpuMsec);
	mapTiming["gpu_ready"] = JsonValue(stTiming.bGpuReady);
	mapTiming["temporal_epoch"] = JsonValue(static_cast<std::int64_t>(stTiming.nTemporalEpoch));
	mapTiming["temporal_sample"] = JsonValue(static_cast<std::int64_t>(stTiming.nTemporalSample));
	mapTiming["temporal_read_index"] = JsonValue(static_cast<std::int64_t>(stTiming.nTemporalRead));
	mapTiming["temporal_write_index"] = JsonValue(static_cast<std::int64_t>(1 - stTiming.nTemporalRead));
	mapTiming["temporal_history_valid"] = JsonValue(stTiming.bTemporalHistoryValid);
	mapTiming["temporal_jitter"] = JsonValue::List{ stTiming.arrTemporalJitter[0], stTiming.arrTemporalJitter[1] };
	mapTiming["postprocess_ready"] = JsonValue(stTiming.bPostReady);
	mapTiming["volume_history_valid"] = JsonValue(stTiming.bVolumeHistoryValid);
	mapTiming["volume_history_read_index"] = JsonValue(static_cast<std::int64_t>(stTiming.nVolumeHistoryRead));
	mapTiming["particles"] = JsonValue(static_cast<std::int64_t>(stTiming.nParticles));
	mapTiming["paged_lod"] = JsonValue(stTiming.bPagedLod);
	mapTiming["page_candidates"] = JsonValue(static_cast<std::int64_t>(stTiming.nPageCandidates));
	mapTiming["page_triangles"] = JsonValue(static_cast<std::int64_t>(stTiming.nPageTriangles));
	mapTiming["page_resident_bytes"] = JsonValue(static_cast<std::int64_t>(stTiming.nPageResidentBytes));
	mapTiming["page_read_requests"] = JsonValue(static_cast<std::int64_t>(stTiming.nPageReadRequests));
	mapTiming["lighting_seconds"] = JsonValue(stTiming.dLightingSeconds);
	mapTiming["directional_illuminance"] = JsonValue(stTiming.dDirectionalIlluminance);
	mapTiming["animation_seconds"] = JsonValue(stTiming.dAnimationSeconds);
	mapTiming["animation_cpu_msec"] = JsonValue(stTiming.dAnimationCpuMsec);
	mapTiming["animation_max_local_motion"] = JsonValue(stTiming.dAnimationMaxMotion);
	mapTiming["animation_vertices"] = JsonValue(static_cast<std::int64_t>(stTiming.nAnimatedVertices));
	mapTiming["animation_gi_changed_draws"] = JsonValue(static_cast<std::int64_t>(stTiming.nAnimationGiChangedDraws));
	JsonValue::List arrRecordingThreads;
	for (std::uint32_t nIndex = 0; nIndex < stTiming.stRecording.nThreads && nIndex < stTiming.stRecording.arrThreads.size(); ++nIndex)
	{
		const RecordingThreadStatistics &stThread = stTiming.stRecording.arrThreads[nIndex];
		arrRecordingThreads.emplace_back(JsonValue::Object{
				{ "thread_id", JsonValue(static_cast<std::int64_t>(stThread.nThreadId)) },
				{ "draws", JsonValue(static_cast<std::int64_t>(stThread.nDraws)) },
				{ "bundles", JsonValue(static_cast<std::int64_t>(stThread.nLists)) },
				{ "begin_qpc", JsonValue(std::to_string(stThread.nBeginQpc)) },
				{ "end_qpc", JsonValue(std::to_string(stThread.nEndQpc)) } });
	}
	mapTiming["shadow_executed_bundles"] = JsonValue(static_cast<std::int64_t>(stTiming.stRecording.nExecutedBundles));
	mapTiming["shadow_recording_threads"] = JsonValue(std::move(arrRecordingThreads));
	mapTiming["shadow_recording_batch_msec"] = JsonValue(stTiming.stRecording.dBatchMsec);
	mapTiming["texture_streaming"] = DescribeTextureTelemetry(stTiming.stTextures, stTiming.nTextureChangeSerial);
	mapTiming["ray_reflection_primary"] = JsonValue(static_cast<std::int64_t>(stTiming.nRayPrimary));
	mapTiming["ray_reflection_screen_hits"] = JsonValue(static_cast<std::int64_t>(stTiming.nRayScreenHits));
	mapTiming["ray_reflection_scene_hits"] = JsonValue(static_cast<std::int64_t>(stTiming.nRaySceneHits));
	mapTiming["ray_reflection_misses"] = JsonValue(static_cast<std::int64_t>(stTiming.nRayMisses));
	mapTiming["ray_reflection_invalid"] = JsonValue(static_cast<std::int64_t>(stTiming.nRayInvalid));
	mapTiming["ray_reflection_shadow_rays"] = JsonValue(static_cast<std::int64_t>(stTiming.nRayShadowRays));
	mapTiming["ray_reflection_witness_rays"] = JsonValue(static_cast<std::int64_t>(stTiming.nRayWitnessRays));
	mapTiming["shadow_pages_requested"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nRequested));
	mapTiming["shadow_pages_resident"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nResident));
	mapTiming["shadow_pages_reused"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nReused));
	mapTiming["shadow_pages_rendered"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nRendered));
	mapTiming["shadow_pages_invalidated"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nInvalidated));
	mapTiming["shadow_pages_evicted"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nEvicted));
	mapTiming["shadow_pages_deferred"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nDeferred));
	mapTiming["shadow_pages_rejected_feedback"] = JsonValue(static_cast<std::int64_t>(stTiming.stShadowPages.nRejectedFeedback));
	mapTiming["shadow_feedback_receivers"] = JsonValue(static_cast<std::int64_t>(stTiming.arrShadowFeedback[0]));
	mapTiming["shadow_feedback_mapped_receivers"] = JsonValue(static_cast<std::int64_t>(stTiming.arrShadowFeedback[1]));
	mapTiming["shadow_feedback_missing_receivers"] = JsonValue(static_cast<std::int64_t>(stTiming.arrShadowFeedback[2]));
	mapTiming["shadow_feedback_invalid"] = JsonValue(static_cast<std::int64_t>(stTiming.arrShadowFeedback[3]));
	mapTiming["shadow_coarse_reused"] = JsonValue(stTiming.bCoarseShadowReused);
	mapTiming["animation_history_valid"] = JsonValue(stTiming.bAnimationHistoryValid);
	if (stTiming.bPostReady)
	{
		JsonValue::List arrExposureRecord;
		for (float fValue : stTiming.arrExposure)
		{
			arrExposureRecord.emplace_back(static_cast<double>(fValue));
		}
		mapTiming["exposure_record"] = JsonValue(std::move(arrExposureRecord));
		mapTiming["display_exposure"] = JsonValue(static_cast<double>(stTiming.arrExposure[0]));
		mapTiming["frame_pre_exposure"] = JsonValue(static_cast<double>(stTiming.arrExposure[1]));
		mapTiming["target_ev100"] = JsonValue(static_cast<double>(stTiming.arrExposure[2]));
		mapTiming["metered_luminance"] = JsonValue(static_cast<double>(stTiming.arrExposure[3]));
		mapTiming["meter_finite_pixels"] = JsonValue(static_cast<std::int64_t>(stTiming.nMeterFinite));
		mapTiming["meter_invalid_pixels"] = JsonValue(static_cast<std::int64_t>(stTiming.nMeterInvalid));
	}

	mapTiming["graphics_msec"] = stTiming.bGpuReady ? JsonValue(stTiming.dGraphicsMsec) : JsonValue();
	mapTiming["compute_msec"] = stTiming.bGpuReady ? JsonValue(stTiming.dComputeMsec) : JsonValue();
	JsonValue::List arrPassTimes;
	for (std::size_t nPassIndex = 0; nPassIndex < stTiming.arrPassMsec.size() && nPassIndex < stGraph.arrPasses.size(); ++nPassIndex)
	{
		JsonValue::Object mapPass;
		mapPass["pass_id"] = JsonValue(static_cast<std::int64_t>(stGraph.arrPasses[nPassIndex].nPass));
		mapPass["gpu_msec"] = stTiming.bGpuReady ? JsonValue(stTiming.arrPassMsec[nPassIndex]) : JsonValue();
		arrPassTimes.emplace_back(std::move(mapPass));
	}
	mapTiming["passes"] = JsonValue(std::move(arrPassTimes));
	mapTiming["graph_epoch"] = JsonValue(std::to_string(stTiming.nGraphEpoch));
	mapTiming["frame_begin_qpc"] = JsonValue(std::to_string(stTiming.nFrameBeginQpc));
	mapTiming["cpu_end_qpc"] = JsonValue(std::to_string(stTiming.nCpuEndQpc));
	mapTiming["input_revision"] = JsonValue(std::to_string(stTiming.nInputRevision));
	mapTiming["input_received_qpc"] = JsonValue(std::to_string(stTiming.nInputReceivedQpc));
	mapTiming["input_receipts_since_previous_frame"] = JsonValue(std::to_string(stTiming.nInputReceipts));
	mapTiming["new_input"] = JsonValue(stTiming.bNewInput);
	mapTiming["window_event_qpc"] = JsonValue(std::to_string(stTiming.nWindowEventQpc));
	mapTiming["input_observed_qpc"] = JsonValue(std::to_string(stTiming.nInputObservedQpc));
	mapTiming["submit_qpc"] = JsonValue(std::to_string(stTiming.nSubmitQpc));
	mapTiming["present_begin_qpc"] = JsonValue(std::to_string(stTiming.nPresentBeginQpc));
	mapTiming["present_end_qpc"] = JsonValue(std::to_string(stTiming.nPresentEndQpc));
	mapTiming["completion_observed_qpc"] = JsonValue(std::to_string(stTiming.nCompletionObservedQpc));
	mapTiming["synchronous_page_read_bytes"] = JsonValue(std::to_string(stTiming.nSynchronousPageReadBytes));
	mapTiming["upload_copy_bytes"] = JsonValue(std::to_string(stTiming.nSynchronousUploadBytes));
	mapTiming["dedicated_usage_bytes"] = JsonValue(std::to_string(stTiming.nDedicatedUsageBytes));
	mapTiming["dedicated_budget_bytes"] = JsonValue(std::to_string(stTiming.nDedicatedBudgetBytes));
	mapTiming["process_private_bytes"] = JsonValue(std::to_string(stTiming.nProcessPrivateBytes));
	mapTiming["process_working_set_bytes"] = JsonValue(std::to_string(stTiming.nProcessWorkingSetBytes));
	mapTiming["process_handles"] = JsonValue(std::to_string(stTiming.nProcessHandles));
	mapTiming["graph_resources"] = JsonValue(std::to_string(stTiming.nGraphResources));
	mapTiming["descriptor_capacity"] = JsonValue(std::to_string(stTiming.nDescriptorCapacity));
	mapTiming["allocated_mesh_pages"] = JsonValue(std::to_string(stTiming.nAllocatedPageResources));
	mapTiming["page_evictions"] = JsonValue(std::to_string(stTiming.nPageEvictions));
	mapTiming["page_stalls"] = JsonValue(std::to_string(stTiming.nPageStalls));
	mapTiming["retirement_readback_msec"] = JsonValue(stTiming.dRetireReadbackMsec);
	mapTiming["fence_wait_msec"] = JsonValue(stTiming.dFenceWaitMsec);
	mapTiming["prepare_msec"] = JsonValue(stTiming.dPrepareMsec);
	mapTiming["record_submit_msec"] = JsonValue(stTiming.dRecordSubmitMsec);
	mapTiming["animation_upload_msec"] = JsonValue(stTiming.dAnimationUploadMsec);
	mapTiming["page_prepare_msec"] = JsonValue(stTiming.dPagePrepareMsec);
	mapTiming["present_msec"] = JsonValue(stTiming.dPresentMsec);
	mapTiming["memory_ready"] = JsonValue(stTiming.bMemoryReady);
	mapTiming["process_ready"] = JsonValue(stTiming.bProcessReady);
	return JsonValue(std::move(mapTiming));
}

FrameTelemetry::~FrameTelemetry()
{
	if (pOutput != nullptr)
	{
		(void)std::fclose(pOutput);
	}
}

bool FrameTelemetry::Write(const Serialization::JsonValue &stValue, Assets::Diagnostics &out_arrDiagnostics)
{
	std::string strJson;
	if (bFailed || pOutput == nullptr || !Serialization::CanonicalJson(stValue, strJson) || strJson.size() >= 1024 * 1024 || strJson.size() >= std::numeric_limits<std::uint64_t>::max() - nBytes)
	{
		bFailed = true;
		return Fail("Cannot serialize a telemetry record", out_arrDiagnostics);
	}
	if (std::fwrite(strJson.data(), 1, strJson.size(), pOutput) != strJson.size() || std::fputc('\n', pOutput) == EOF)
	{
		bFailed = true;
		return Fail("Cannot write telemetry output", out_arrDiagnostics);
	}
	nBytes += static_cast<std::uint64_t>(strJson.size()) + 1;
	return true;
}

bool FrameTelemetry::Open(const std::string &strPath, Serialization::JsonValue stMetadata, Assets::Diagnostics &out_arrDiagnostics)
{
	if (strPath.empty() || pOutput != nullptr || nRecords != 0 || !stMetadata.IsObject())
	{
		return Fail("Telemetry requires a new output path and object metadata", out_arrDiagnostics);
	}
	const std::filesystem::path stPath = std::filesystem::u8path(strPath);
#if defined(_WIN32)
	const bool bOpened = _wfopen_s(&pOutput, stPath.c_str(), L"wbx") == 0;
#else
	pOutput = std::fopen(stPath.c_str(), "wbx");
	const bool bOpened = pOutput != nullptr;
#endif
	if (!bOpened)
	{
		return Fail("Cannot exclusively create telemetry output", out_arrDiagnostics);
	}
	if (std::setvbuf(pOutput, arrBuffer.data(), _IOFBF, arrBuffer.size()) != 0)
	{
		(void)std::fclose(pOutput);
		pOutput = nullptr;
		return Fail("Cannot configure the bounded telemetry buffer", out_arrDiagnostics);
	}
	(*stMetadata.GetObject())["record"] = "header";
	(*stMetadata.GetObject())["schema_version"] = std::int64_t{ 1 };
	return Write(stMetadata, out_arrDiagnostics);
}

bool FrameTelemetry::Append(const FrameTiming &stTiming, const CompiledGraph &stGraph, Assets::Diagnostics &out_arrDiagnostics)
{
	using Serialization::JsonValue;
	if (!stTiming.bGpuReady || stTiming.stRecording.nThreads == 0 || stTiming.stRecording.nThreads > stTiming.stRecording.arrThreads.size() || stTiming.nGraphEpoch == 0 || stGraph.arrPasses.size() > MAX_GRAPH_PASSES || stTiming.arrPassMsec.size() > MAX_GRAPH_PASSES || nRecords == std::numeric_limits<std::uint64_t>::max())
	{
		return Fail("Only retired frames may be streamed", out_arrDiagnostics);
	}
	if (nGraphEpoch != stTiming.nGraphEpoch)
	{
		JsonValue::List arrPasses;
		for (const CompiledPass &stPass : stGraph.arrPasses)
		{
			arrPasses.emplace_back(JsonValue::Object{ { "pass_id", static_cast<std::int64_t>(stPass.nPass) }, { "name", stPass.strName }, { "queue", stPass.eQueue == QueueType::Compute ? "compute" : "graphics" } });
		}
		if (!Write(JsonValue::Object{ { "record", "graph" }, { "graph_epoch", std::to_string(stTiming.nGraphEpoch) }, { "passes", std::move(arrPasses) } }, out_arrDiagnostics))
		{
			return false;
		}
		nGraphEpoch = stTiming.nGraphEpoch;
	}
	JsonValue stValue = DescribeFrameTiming(stTiming, stGraph);
	(*stValue.GetObject())["record"] = "frame";
	(*stValue.GetObject())["record_id"] = std::to_string(nRecords);
	if (!Write(stValue, out_arrDiagnostics))
	{
		return false;
	}
	++nRecords;
	if (nRecords % 256 == 0)
	{
		if (std::fflush(pOutput) != 0)
		{
			bFailed = true;
			return Fail("Cannot flush telemetry output", out_arrDiagnostics);
		}
	}
	return true;
}

bool FrameTelemetry::Finish(bool bSuccess, std::uint64_t nExpectedFrames, Assets::Diagnostics &out_arrDiagnostics)
{
	using Serialization::JsonValue;
	const bool bComplete = bSuccess && !bFailed && nExpectedFrames == nRecords;
	if (!Write(JsonValue::Object{ { "record", "footer" }, { "complete", bComplete }, { "frames", std::to_string(nRecords) }, { "expected_frames", std::to_string(nExpectedFrames) } }, out_arrDiagnostics))
	{
		return false;
	}
	const bool bFlushed = std::fflush(pOutput) == 0;
	const bool bClosed = std::fclose(pOutput) == 0;
	pOutput = nullptr;
	if (!bFlushed || !bClosed || (bSuccess && !bComplete))
	{
		return Fail("Telemetry output is incomplete", out_arrDiagnostics);
	}
	return true;
}

bool FrameTelemetry::IsOpen() const noexcept
{
	return pOutput != nullptr;
}

std::uint64_t FrameTelemetry::Records() const noexcept
{
	return nRecords;
}

std::uint64_t FrameTelemetry::Bytes() const noexcept
{
	return nBytes;
}

} // namespace EngineNext::Rendering
