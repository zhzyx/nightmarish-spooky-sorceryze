/**************************************************************************/
/*  RayReflectionSettings.cpp                                             */
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

#include "engine_next/include/EngineNext/Rendering/RayReflectionSettings.h"

#include <cmath>

namespace EngineNext::Rendering
{
namespace
{

bool UnitRange(double dValue, double dMinimum, double dMaximum)
{
	return std::isfinite(dValue) && dValue >= dMinimum && dValue <= dMaximum;
}

} // namespace

bool ValidateRayReflectionSettings(const RayReflectionSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if ((stSettings.nResolutionDivisor != 1 && stSettings.nResolutionDivisor != 2) ||
		stSettings.nSamplesPerLobe < 1 || stSettings.nSamplesPerLobe > 4 || stSettings.nSpatialPasses > 3 ||
		stSettings.nMaxHistory < 1 || stSettings.nMaxHistory > 64 || !UnitRange(stSettings.dHistoryWeight, 0, 0.98) ||
		!UnitRange(stSettings.dDepthThreshold, 0.000001, 1) || !UnitRange(stSettings.dNormalThreshold, 0, 1) ||
		!UnitRange(stSettings.dRoughnessThreshold, 0, 1) || stSettings.nMaxGpuBytes == 0 ||
		stSettings.nMaxGpuBytes > 2ULL * 1024 * 1024 * 1024)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "ray_reflection_settings", "$.reflections.ray_tracing",
							  "Ray reflections require resolution divisor 1 or 2, one to four samples per lobe, at most three spatial passes, bounded history, and a positive budget of at most 2 GiB.");
		return false;
	}
	return true;
}

bool BuildRayReflectionBudget(const RayReflectionSettings &stSettings, std::uint32_t nWidth, std::uint32_t nHeight,
							  RayReflectionBudget &out_stBudget, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateRayReflectionSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	if (nWidth == 0 || nHeight == 0 || nWidth > 32767 || nHeight > 32767)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "ray_reflection_dimensions", "$.reflections.ray_tracing", "Ray reflection dimensions must be in [1,32767].");
		return false;
	}
	RayReflectionBudget stCandidate;
	stCandidate.nWidth = (nWidth + stSettings.nResolutionDivisor - 1) / stSettings.nResolutionDivisor;
	stCandidate.nHeight = (nHeight + stSettings.nResolutionDivisor - 1) / stSettings.nResolutionDivisor;
	stCandidate.nPixels = static_cast<std::uint64_t>(stCandidate.nWidth) * stCandidate.nHeight;
	// Raw base/coat/hit data: 48 bytes. Two seven-image history sets: 168.
	// Base/coat spatial scratch: 32. Small counter/readback buffers: 3 * 128.
	stCandidate.nPayloadBytes = stCandidate.nPixels * 248 + 3 * 128;
	// Two lobes, each with paired BRDF and environment proposals. A separate
	// central visibility witness is bounded by one additional ray per pixel.
	stCandidate.nPrimaryRays = stCandidate.nPixels * stSettings.nSamplesPerLobe * 4;
	if (stCandidate.nPayloadBytes > stSettings.nMaxGpuBytes || stCandidate.nPrimaryRays > 0xffffffffULL)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "ray_reflection_budget", "$.reflections.ray_tracing.max_gpu_bytes", "Ray reflection resources or primary ray count exceed the configured budget.");
		return false;
	}
	out_stBudget = stCandidate;
	return true;
}

} // namespace EngineNext::Rendering
