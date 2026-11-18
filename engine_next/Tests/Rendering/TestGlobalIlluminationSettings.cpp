/**************************************************************************/
/*  TestGlobalIlluminationSettings.cpp                                    */
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
#include "engine_next/include/EngineNext/Rendering/GlobalIlluminationSettings.h"

#include <cmath>
#include <limits>
#include <string>

namespace
{
using namespace EngineNext::Rendering;
using EngineNext::Assets::Diagnostics;

bool Parse(const char *pJson, GlobalIlluminationSettings &out_stSettings, Diagnostics &out_arrDiagnostics)
{
	EngineNext::Serialization::JsonValue stJson;
	std::string strError;
	return EngineNext::Serialization::ParseJson(pJson, stJson, strError) && ParseGlobalIlluminationSettings(stJson, out_stSettings, out_arrDiagnostics);
}
} //namespace

ENGINE_NEXT_TEST("GI defaults retain disabled three level High layout and exact byte budget")
{
	GlobalIlluminationSettings stSettings;
	GlobalIlluminationBudget stBudget;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stSettings.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stBudget.nProbeCount, 41472U);
	ENGINE_NEXT_CHECK_EQ(stBudget.nUpdateCount, 128U);
	ENGINE_NEXT_CHECK_EQ(stBudget.nRayCount, 4096U);
	ENGINE_NEXT_CHECK_EQ(stBudget.nHistoryBytes, 55738368ULL);
	ENGINE_NEXT_CHECK_EQ(stBudget.nTotalBytes, 56796672ULL);
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("GI resource budgets enforce exact cap and output transaction")
{
	GlobalIlluminationSettings stSettings;
	GlobalIlluminationBudget stBudget;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	stSettings.nMaxGpuBytes = stBudget.nTotalBytes;
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	--stSettings.nMaxGpuBytes;
	stBudget.nProbeCount = 123;
	ENGINE_NEXT_CHECK(!BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nProbeCount, 123U);
	stSettings.nMaxGpuBytes = MAX_GI_GPU_BYTES + 1;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("GI total count and ray buffers remain bounded")
{
	GlobalIlluminationSettings stSettings;
	stSettings.nClipmapLevels = 1;
	stSettings.arrProbeCounts = { 32, 32, 64 };
	GlobalIlluminationBudget stBudget;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nProbeCount, MAX_GI_PROBES);
	stSettings.nClipmapLevels = 2;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings.nClipmapLevels = 1;
	stSettings.nUpdatesPerFrame = MAX_GI_PROBES;
	stSettings.nRaysPerProbe = 1024;
	stSettings.nMaxGpuBytes = MAX_GI_GPU_BYTES;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.arrProbeCounts = { 2, 2, 2 };
	stSettings.nUpdatesPerFrame = MAX_GI_PROBES;
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nUpdateCount, 24U);
}

ENGINE_NEXT_TEST("GI trace distance rejects vanished or overflowing GPU values")
{
	GlobalIlluminationSettings stSettings;
	Diagnostics arrDiagnostics;
	stSettings.dTraceDistance = std::numeric_limits<float>::min();
	ENGINE_NEXT_CHECK(ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	for (double dValue : { 0.0, -1.0, 1e-99, static_cast<double>(std::numeric_limits<float>::max()), std::numeric_limits<double>::infinity() })
	{
		stSettings.dTraceDistance = dValue;
		ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	}
	stSettings.dTraceDistance = std::nextafter(std::sqrt(std::numeric_limits<float>::max()), 0.0F);
	ENGINE_NEXT_CHECK(ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("GI world bounds validate expanded levels and binary32 cell precision")
{
	GlobalIlluminationSettings stSettings;
	Diagnostics arrDiagnostics;
	stSettings.arrBoundsMaximum[0] = stSettings.arrBoundsMinimum[0];
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.arrBoundsMinimum[0] = 1e20;
	stSettings.arrBoundsMaximum[0] = 1e20 + 100000;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.arrBoundsMinimum[0] = -std::numeric_limits<float>::max();
	stSettings.arrBoundsMaximum[0] = std::numeric_limits<float>::max();
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings.nClipmapLevels = 1;
	ENGINE_NEXT_CHECK(ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("GI zero history threshold and bias preserve valid explicit endpoints")
{
	GlobalIlluminationSettings stSettings;
	Diagnostics arrDiagnostics;
	stSettings.dHysteresis = 0;
	stSettings.dHistoryChangeThreshold = 0;
	stSettings.dNormalBias = 1e-99;
	stSettings.dViewBias = 0;
	ENGINE_NEXT_CHECK(ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings.dHistoryChangeThreshold = 1e-99;
	ENGINE_NEXT_CHECK(ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.dHistoryChangeThreshold, 1e-99);
	stSettings.dBounceStrength = 1.01;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings.dBounceStrength = 1;
	stSettings.dNormalBias = -1;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings.dNormalBias = 0;
	stSettings.dHysteresis = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
}
ENGINE_NEXT_TEST("GI inverse spacing preserves the normal binary32 GPU boundary")
{
	GlobalIlluminationSettings stSettings;
	stSettings.arrProbeCounts = { 2, 2, 2 };
	stSettings.nClipmapLevels = 1;
	stSettings.arrBoundsMinimum[0] = 0;
	const float fLastSpacing = 1.0F / std::numeric_limits<float>::min();
	stSettings.arrBoundsMaximum[0] = fLastSpacing;
	GlobalIlluminationBudget stBudget;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	stBudget.nProbeCount = 777;
	stSettings.arrBoundsMaximum[0] = std::nextafter(fLastSpacing, std::numeric_limits<float>::infinity());
	ENGINE_NEXT_CHECK(!BuildGlobalIlluminationBudget(stSettings, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nProbeCount, 777U);
	stSettings.arrBoundsMaximum[0] = std::numeric_limits<float>::max();
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
	stSettings.arrBoundsMaximum[0] = fLastSpacing;
	stSettings.nClipmapLevels = 2;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("GI strict optional parsing preserves defaults and supported complete object")
{
	GlobalIlluminationSettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(Parse("{}", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.nClipmapLevels, 3U);
	ENGINE_NEXT_CHECK(Parse(R"({"enabled":true,"world_bounds":{"minimum":[-2,-3,-4],"maximum":[2,3,4]},"probe_counts":[3,4,5],"clipmap_levels":2,"updates_per_frame":16,"rays_per_probe":64,"trace_distance":100,"hysteresis":0.7,"normal_bias":0.02,"view_bias":0.03,"bounce_strength":0.8,"history_change_threshold":0,"max_gpu_bytes":16777216})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSettings.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrProbeCounts[1], 4U);
	ENGINE_NEXT_CHECK_EQ(stSettings.nRaysPerProbe, 64U);
	ENGINE_NEXT_CHECK_EQ(stSettings.dHistoryChangeThreshold, 0);
}

ENGINE_NEXT_TEST("GI malformed and disabled invalid objects fail transactionally")
{
	GlobalIlluminationSettings stSettings;
	stSettings.nRaysPerProbe = 123;
	Diagnostics arrDiagnostics;
	for (const char *pJson : { "null", "[]", R"({"extra":1})", R"({"enabled":1})", R"({"world_bounds":{"extra":0}})", R"({"probe_counts":[2,3]})", R"({"probe_counts":[2,3,4.5]})", R"({"enabled":false,"trace_distance":0})", R"({"clipmap_levels":0})", R"({"updates_per_frame":-1})", R"({"rays_per_probe":4096})", R"({"max_gpu_bytes":1})" })
	{
		ENGINE_NEXT_CHECK(!Parse(pJson, stSettings, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stSettings.nRaysPerProbe, 123U);
	}
}

ENGINE_NEXT_TEST("GI placement is opt in and its full float state is budgeted")
{
	GlobalIlluminationSettings stSettings;
	GlobalIlluminationBudget stLegacy;
	GlobalIlluminationBudget stPlaced;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(Parse("{}", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stSettings.stPlacement.bEnabled);
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stLegacy, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stLegacy.nStateStride, 16U);
	ENGINE_NEXT_CHECK(Parse(R"({"placement":{"enabled":true,"minimum_clearance":0.05,"maximum_offset_fraction":0.4,"backface_threshold":0.2,"rays_per_probe":64,"stable_updates":3}})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSettings.stPlacement.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.stPlacement.nMinimumRays, 64U);
	ENGINE_NEXT_CHECK(BuildGlobalIlluminationBudget(stSettings, stPlaced, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stPlaced.nStateStride, 48U);
	ENGINE_NEXT_CHECK_EQ(stPlaced.nHistoryBytes - stLegacy.nHistoryBytes, 2ULL * 32 * stPlaced.nProbeCount);
	ENGINE_NEXT_CHECK_EQ(stPlaced.nTotalBytes - stLegacy.nTotalBytes, 76ULL * stPlaced.nProbeCount);
	stSettings.nMaxGpuBytes = stLegacy.nTotalBytes;
	ENGINE_NEXT_CHECK(!ValidateGlobalIlluminationSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("GI placement settings reject unsafe numeric and unknown fields transactionally")
{
	GlobalIlluminationSettings stSettings;
	stSettings.nRaysPerProbe = 123;
	Diagnostics arrDiagnostics;
	for (const char *pJson : {
				 R"({"placement":null})", R"({"placement":{"enabled":1}})", R"({"placement":{"unknown":0}})",
				 R"({"placement":{"minimum_clearance":0}})", R"({"placement":{"maximum_offset_fraction":0.5}})",
				 R"({"placement":{"rays_per_probe":5}})", R"({"placement":{"rays_per_probe":1025}})",
				 R"({"placement":{"stable_updates":0}})", R"({"placement":{"stable_updates":65}})",
				 R"({"placement":{"backface_threshold":1}})", R"({"trace_distance":0.001,"placement":{"enabled":true}})" })
	{
		ENGINE_NEXT_CHECK(!Parse(pJson, stSettings, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stSettings.nRaysPerProbe, 123U);
	}
	ENGINE_NEXT_CHECK(Parse(R"({"trace_distance":0.001,"placement":{"enabled":false}})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(Parse(R"({"trace_distance":50,"placement":{"minimum_clearance":30,"enabled":true}})", stSettings, arrDiagnostics));
}
