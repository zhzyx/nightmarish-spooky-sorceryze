/**************************************************************************/
/*  GlobalIlluminationSettings.cpp                                        */
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

#include "engine_next/include/EngineNext/Rendering/GlobalIlluminationSettings.h"
#include "engine_next/Assets/AssetValidation.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <initializer_list>
#include <limits>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr const char *GI_PATH = "$.global_illumination";

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "global_illumination", GI_PATH, pMessage);
	return false;
}

bool FloatValue(double dValue)
{
	return std::isfinite(dValue) && std::abs(dValue) <= std::numeric_limits<float>::max();
}

bool OptionalFields(const Serialization::JsonValue::Object &mapObject, std::initializer_list<const char *> arrNames, Assets::Diagnostics &out_arrDiagnostics)
{
	Serialization::JsonValue::Object mapComplete;
	for (const std::pair<const std::string, Serialization::JsonValue> &stField : mapObject)
	{
		mapComplete.emplace(stField.first, Serialization::JsonValue{});
	}
	for (const char *pName : arrNames)
	{
		mapComplete.emplace(pName, Serialization::JsonValue{});
	}
	return Assets::Fields(mapComplete, arrNames, GI_PATH, out_arrDiagnostics);
}

bool Number(const Serialization::JsonValue::Object &mapObject, const char *pName, double &out_dValue, Assets::Diagnostics &out_arrDiagnostics)
{
	return mapObject.find(pName) == mapObject.end() || Assets::Number(mapObject, pName, GI_PATH, out_dValue, out_arrDiagnostics);
}

bool Integer(const Serialization::JsonValue::Object &mapObject, const char *pName, std::uint64_t &out_nValue, Assets::Diagnostics &out_arrDiagnostics)
{
	if (mapObject.find(pName) == mapObject.end())
	{
		return true;
	}
	std::int64_t nValue = 0;
	if (!Assets::Integer(mapObject, pName, GI_PATH, nValue, out_arrDiagnostics) || nValue < 0)
	{
		return Fail(out_arrDiagnostics, "Expected a nonnegative integer setting.");
	}
	out_nValue = static_cast<std::uint64_t>(nValue);
	return true;
}

bool Vector(const Serialization::JsonValue::Object &mapObject, const char *pName, std::array<double, 3> &out_arrValue, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator it = mapObject.find(pName);
	if (it == mapObject.end())
	{
		return true;
	}
	const Serialization::JsonValue::List *pValues = it->second.GetList();
	if (pValues == nullptr || pValues->size() != 3)
	{
		return Fail(out_arrDiagnostics, "Expected three finite world coordinates.");
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!(*pValues)[nAxis].GetNumber(out_arrValue[nAxis]))
		{
			return Fail(out_arrDiagnostics, "Expected three finite world coordinates.");
		}
	}
	return true;
}

bool Placement(const Serialization::JsonValue &stValue, ProbeRelocationSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Assets::Object(stValue, GI_PATH, out_arrDiagnostics);
	if (pObject == nullptr || !OptionalFields(*pObject, { "enabled", "minimum_clearance", "maximum_offset_fraction", "backface_threshold", "rays_per_probe", "stable_updates" }, out_arrDiagnostics))
	{
		return false;
	}
	ProbeRelocationSettings stSettings;
	const Serialization::JsonValue::Object::const_iterator itEnabled = pObject->find("enabled");
	if (itEnabled != pObject->end() && !itEnabled->second.GetBool(stSettings.bEnabled))
	{
		return Fail(out_arrDiagnostics, "Placement enabled must be boolean.");
	}
	double dClearance = stSettings.fMinimumClearance;
	double dOffset = stSettings.fMaximumOffsetFraction;
	double dBackfaces = stSettings.fBackfaceThreshold;
	std::uint64_t nRays = stSettings.nMinimumRays;
	std::uint64_t nStable = stSettings.nRequiredStableUpdates;
	if (!Number(*pObject, "minimum_clearance", dClearance, out_arrDiagnostics) || !Number(*pObject, "maximum_offset_fraction", dOffset, out_arrDiagnostics) ||
		!Number(*pObject, "backface_threshold", dBackfaces, out_arrDiagnostics) || !Integer(*pObject, "rays_per_probe", nRays, out_arrDiagnostics) ||
		!Integer(*pObject, "stable_updates", nStable, out_arrDiagnostics) || !FloatValue(dClearance) || !FloatValue(dOffset) || !FloatValue(dBackfaces) || nRays > 1024 || nStable > 64)
	{
		return Fail(out_arrDiagnostics, "Invalid placement numeric setting.");
	}
	stSettings.fMinimumClearance = static_cast<float>(dClearance);
	stSettings.fMaximumOffsetFraction = static_cast<float>(dOffset);
	stSettings.fBackfaceThreshold = static_cast<float>(dBackfaces);
	stSettings.nMinimumRays = static_cast<std::uint32_t>(nRays);
	stSettings.nRequiredStableUpdates = static_cast<std::uint32_t>(nStable);
	if (!ValidateProbeRelocationSettings(stSettings))
	{
		return Fail(out_arrDiagnostics, "Invalid placement clearance, offset, rays or stable update count.");
	}
	out_stSettings = stSettings;
	return true;
}
} // namespace

bool BuildGlobalIlluminationBudget(const GlobalIlluminationSettings &stSettings, GlobalIlluminationBudget &out_stBudget, Assets::Diagnostics &out_arrDiagnostics)
{
	ProbeRelocationSettings stPlacement = stSettings.stPlacement;
	if (!ValidateProbeRelocationSettings(stPlacement))
	{
		return Fail(out_arrDiagnostics, "Probe placement settings must be finite and bounded; enabled clearance must fit the trace distance.");
	}
	if (stSettings.nClipmapLevels == 0 || stSettings.nClipmapLevels > MAX_GI_CLIPMAP_LEVELS || stSettings.nUpdatesPerFrame == 0 || stSettings.nUpdatesPerFrame > MAX_GI_PROBES || stSettings.nRaysPerProbe < 16 || stSettings.nRaysPerProbe > 1024)
	{
		return Fail(out_arrDiagnostics, "Expected 1..3 clipmaps, 1..65536 updates and 16..1024 rays per updated probe.");
	}
	std::uint64_t nPerLevel = 1;
	for (std::uint32_t nCount : stSettings.arrProbeCounts)
	{
		if (nCount < 2 || nCount > MAX_GI_PROBES || nPerLevel > MAX_GI_PROBES / nCount)
		{
			return Fail(out_arrDiagnostics, "Each axis needs at least two probes and the total probe count must fit 65536.");
		}
		nPerLevel *= nCount;
	}
	if (nPerLevel * stSettings.nClipmapLevels > MAX_GI_PROBES)
	{
		return Fail(out_arrDiagnostics, "The total probe count across clipmaps exceeds 65536.");
	}
	if (!FloatValue(stSettings.dTraceDistance) || stSettings.dTraceDistance < std::numeric_limits<float>::min())
	{
		return Fail(out_arrDiagnostics, "Trace distance must be a positive normal binary32 value.");
	}
	const float fTrace = static_cast<float>(stSettings.dTraceDistance);
	if (stPlacement.bEnabled && fTrace < stPlacement.fMinimumClearance)
	{
		return Fail(out_arrDiagnostics, "Enabled placement clearance must fit the trace distance.");
	}
	if (static_cast<double>(fTrace) * fTrace > std::numeric_limits<float>::max())
	{
		return Fail(out_arrDiagnostics, "Squared binary32 trace distance must remain finite.");
	}
	if (!FloatValue(stSettings.dHysteresis) || stSettings.dHysteresis < 0 || stSettings.dHysteresis > 0.99 || !FloatValue(stSettings.dNormalBias) || stSettings.dNormalBias < 0 || !FloatValue(stSettings.dViewBias) || stSettings.dViewBias < 0 || !FloatValue(stSettings.dBounceStrength) || stSettings.dBounceStrength < 0 || stSettings.dBounceStrength > 1 || !FloatValue(stSettings.dHistoryChangeThreshold) || stSettings.dHistoryChangeThreshold < 0 || stSettings.dHistoryChangeThreshold > 1)
	{
		return Fail(out_arrDiagnostics, "Invalid hysteresis, nonnegative bias, bounce strength or nonnegative history threshold.");
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		const double dMinimum = stSettings.arrBoundsMinimum[nAxis];
		const double dMaximum = stSettings.arrBoundsMaximum[nAxis];
		if (!FloatValue(dMinimum) || !FloatValue(dMaximum) || dMaximum <= dMinimum)
		{
			return Fail(out_arrDiagnostics, "World bounds must be ordered finite binary32 coordinates.");
		}
		const double dCenter = (dMinimum + dMaximum) * 0.5;
		for (std::uint32_t nLevel = 0; nLevel < stSettings.nClipmapLevels; ++nLevel)
		{
			const double dSpan = std::ldexp(dMaximum - dMinimum, static_cast<int>(nLevel));
			const double dStart = dCenter - dSpan * 0.5;
			const double dSpacing = dSpan / (stSettings.arrProbeCounts[nAxis] - 1);
			if (!FloatValue(dSpacing) || !std::isnormal(static_cast<float>(dSpacing)))
			{
				return Fail(out_arrDiagnostics, "Probe cell spacing must be a normal finite binary32 value.");
			}
			const float fInverseSpacing = 1.0F / static_cast<float>(dSpacing);
			if (!std::isnormal(fInverseSpacing) || fInverseSpacing <= 0)
			{
				return Fail(out_arrDiagnostics, "Inverse GPU probe spacing must remain positive normal binary32.");
			}
			double dPrevious = -std::numeric_limits<double>::infinity();
			for (std::uint32_t nIndex = 0; nIndex < stSettings.arrProbeCounts[nAxis]; ++nIndex)
			{
				const double dPosition = dStart + dSpacing * nIndex;
				if (!FloatValue(dPosition))
				{
					return Fail(out_arrDiagnostics, "Expanded probe coordinates must remain distinct finite binary32 values.");
				}
				const float fPosition = static_cast<float>(dPosition);
				const float fGpuPosition = std::abs(fPosition) < std::numeric_limits<float>::min() ? 0 : fPosition;
				if (fGpuPosition <= dPrevious)
				{
					return Fail(out_arrDiagnostics, "GPU-normalized probe coordinates must remain distinct.");
				}
				dPrevious = fGpuPosition;
			}
		}
	}
	GlobalIlluminationBudget stBudget;
	stBudget.nProbeCount = static_cast<std::uint32_t>(nPerLevel * stSettings.nClipmapLevels);
	stBudget.nUpdateCount = std::min(stSettings.nUpdatesPerFrame, stBudget.nProbeCount);
	stBudget.nRayCount = stBudget.nUpdateCount * stSettings.nRaysPerProbe;
	stBudget.nStateStride = stPlacement.bEnabled ? GI_STATE_STRIDE + sizeof(ProbePlacement) : GI_STATE_STRIDE;
	const std::uint64_t nHistoryStride = GI_SH_STRIDE + GI_DISTANCE_RESOLUTION * GI_DISTANCE_RESOLUTION * GI_MOMENTS_STRIDE + stBudget.nStateStride;
	stBudget.nHistoryBytes = 2 * nHistoryStride * stBudget.nProbeCount;
	stBudget.nPositionBytes = static_cast<std::uint64_t>(GI_POSITION_STRIDE) * stBudget.nProbeCount;
	stBudget.nRayBytes = static_cast<std::uint64_t>(GI_PENDING_FRAMES) * (GI_RAY_RESULT_STRIDE + GI_RAY_STATUS_STRIDE) * stBudget.nRayCount;
	stBudget.nUpdateBytes = static_cast<std::uint64_t>(GI_PENDING_FRAMES) * sizeof(std::uint32_t) * stBudget.nUpdateCount;
	if (stPlacement.bEnabled)
	{
		stBudget.nUpdateBytes += static_cast<std::uint64_t>(GI_PENDING_FRAMES) * sizeof(std::uint32_t) * stBudget.nProbeCount;
	}
	stBudget.nTotalBytes = stBudget.nHistoryBytes + stBudget.nPositionBytes + stBudget.nRayBytes + stBudget.nUpdateBytes;
	if (stSettings.nMaxGpuBytes == 0 || stSettings.nMaxGpuBytes > MAX_GI_GPU_BYTES || stBudget.nTotalBytes > stSettings.nMaxGpuBytes)
	{
		return Fail(out_arrDiagnostics, "GI buffers exceed the explicit GPU budget or its 512 MiB ceiling.");
	}
	out_stBudget = stBudget;
	return true;
}

bool ValidateGlobalIlluminationSettings(const GlobalIlluminationSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	GlobalIlluminationBudget stBudget;
	return BuildGlobalIlluminationBudget(stSettings, stBudget, out_arrDiagnostics);
}

bool ParseGlobalIlluminationSettings(const Serialization::JsonValue &stValue, GlobalIlluminationSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Assets::Object(stValue, GI_PATH, out_arrDiagnostics);
	if (pObject == nullptr || !OptionalFields(*pObject, { "enabled", "world_bounds", "probe_counts", "clipmap_levels", "updates_per_frame", "rays_per_probe", "trace_distance", "hysteresis", "normal_bias", "view_bias", "bounce_strength", "history_change_threshold", "max_gpu_bytes", "placement" }, out_arrDiagnostics))
	{
		return false;
	}
	GlobalIlluminationSettings stSettings;
	const Serialization::JsonValue::Object::const_iterator itEnabled = pObject->find("enabled");
	if (itEnabled != pObject->end() && !itEnabled->second.GetBool(stSettings.bEnabled))
	{
		return Fail(out_arrDiagnostics, "Expected a boolean enabled setting.");
	}
	const Serialization::JsonValue::Object::const_iterator itBounds = pObject->find("world_bounds");
	if (itBounds != pObject->end())
	{
		const Serialization::JsonValue::Object *pBounds = Assets::Object(itBounds->second, GI_PATH, out_arrDiagnostics);
		if (pBounds == nullptr || !OptionalFields(*pBounds, { "minimum", "maximum" }, out_arrDiagnostics) || !Vector(*pBounds, "minimum", stSettings.arrBoundsMinimum, out_arrDiagnostics) || !Vector(*pBounds, "maximum", stSettings.arrBoundsMaximum, out_arrDiagnostics))
		{
			return false;
		}
	}
	const Serialization::JsonValue::Object::const_iterator itCounts = pObject->find("probe_counts");
	if (itCounts != pObject->end())
	{
		const Serialization::JsonValue::List *pCounts = itCounts->second.GetList();
		if (pCounts == nullptr || pCounts->size() != 3)
		{
			return Fail(out_arrDiagnostics, "Expected three integer probe counts.");
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			std::int64_t nCount = 0;
			if (!(*pCounts)[nAxis].GetInteger(nCount) || nCount < 0 || nCount > MAX_GI_PROBES)
			{
				return Fail(out_arrDiagnostics, "Probe counts must be bounded nonnegative integers.");
			}
			stSettings.arrProbeCounts[nAxis] = static_cast<std::uint32_t>(nCount);
		}
	}
	std::uint64_t nLevels = stSettings.nClipmapLevels;
	std::uint64_t nUpdates = stSettings.nUpdatesPerFrame;
	std::uint64_t nRays = stSettings.nRaysPerProbe;
	if (!Integer(*pObject, "clipmap_levels", nLevels, out_arrDiagnostics) || !Integer(*pObject, "updates_per_frame", nUpdates, out_arrDiagnostics) || !Integer(*pObject, "rays_per_probe", nRays, out_arrDiagnostics) || !Integer(*pObject, "max_gpu_bytes", stSettings.nMaxGpuBytes, out_arrDiagnostics) || nLevels > MAX_GI_CLIPMAP_LEVELS || nUpdates > MAX_GI_PROBES || nRays > 1024 || !Number(*pObject, "trace_distance", stSettings.dTraceDistance, out_arrDiagnostics) || !Number(*pObject, "hysteresis", stSettings.dHysteresis, out_arrDiagnostics) || !Number(*pObject, "normal_bias", stSettings.dNormalBias, out_arrDiagnostics) || !Number(*pObject, "view_bias", stSettings.dViewBias, out_arrDiagnostics) || !Number(*pObject, "bounce_strength", stSettings.dBounceStrength, out_arrDiagnostics) || !Number(*pObject, "history_change_threshold", stSettings.dHistoryChangeThreshold, out_arrDiagnostics))
	{
		return Fail(out_arrDiagnostics, "Invalid GI numeric setting.");
	}
	stSettings.nClipmapLevels = static_cast<std::uint32_t>(nLevels);
	stSettings.nUpdatesPerFrame = static_cast<std::uint32_t>(nUpdates);
	stSettings.nRaysPerProbe = static_cast<std::uint32_t>(nRays);
	const Serialization::JsonValue::Object::const_iterator itPlacement = pObject->find("placement");
	if (itPlacement != pObject->end() && !Placement(itPlacement->second, stSettings.stPlacement, out_arrDiagnostics))
	{
		return false;
	}
	if (!ValidateGlobalIlluminationSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	out_stSettings = stSettings;
	return true;
}

} // namespace EngineNext::Rendering
