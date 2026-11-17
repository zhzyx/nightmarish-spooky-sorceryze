/**************************************************************************/
/*  VolumeGrid.cpp                                                        */
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

#include "engine_next/include/EngineNext/Rendering/VolumeGrid.h"

#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <cmath>
#include <cstddef>

namespace EngineNext::Rendering
{

bool BuildVolumeGrid(const CameraSettings &stCamera, std::uint32_t nViewportWidth, std::uint32_t nViewportHeight, const VolumeSettings &stSettings,
					 VolumeGrid &out_stGrid, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateVolumeSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	if (nViewportWidth == 0 || nViewportHeight == 0 || nViewportWidth > 16384 || nViewportHeight > 16384 || !std::isfinite(stCamera.dNearPlane) ||
		!std::isfinite(stCamera.dFarPlane) || stCamera.dNearPlane < 0.001 || stCamera.dNearPlane > 100 || stCamera.dFarPlane <= stCamera.dNearPlane ||
		stCamera.dFarPlane > 1.0e7)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "volume_grid", "$.volumetric_fog",
							  "Volume grid requires supported viewport dimensions and finite camera clipping distances.");
		return false;
	}
	VolumeGrid stCandidate;
	stCandidate.nWidth = (nViewportWidth - 1) / stSettings.nCellPixels + 1;
	stCandidate.nHeight = (nViewportHeight - 1) / stSettings.nCellPixels + 1;
	stCandidate.nDepth = stSettings.nDepthSlices;
	stCandidate.nFroxelCount = static_cast<std::uint64_t>(stCandidate.nWidth) * stCandidate.nHeight * stCandidate.nDepth;
	if (stCandidate.nFroxelCount > MAX_VOLUME_FROXELS)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "volume_budget", "$.volumetric_fog", "Volume grid exceeds the 8388608-froxel budget.");
		return false;
	}
	stCandidate.dNear = stCamera.dNearPlane;
	stCandidate.dFar = (std::min)(stCamera.dFarPlane, stSettings.dDistance);
	if (static_cast<float>(stCandidate.dFar) <= static_cast<float>(stCandidate.dNear))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "volume_depth", "$.volumetric_fog.distance", "Fog distance must exceed the camera near plane in binary32.");
		return false;
	}
	stCandidate.dLogDepthRatio = std::log(stCandidate.dFar / stCandidate.dNear);
	const double dLogRange = stCandidate.dLogDepthRatio;
	stCandidate.dInverseLogDepthRatio = 1 / dLogRange;
	stCandidate.arrDepthBoundaries[0] = stCandidate.dNear;
	for (std::uint32_t nSlice = 1; nSlice <= stCandidate.nDepth; ++nSlice)
	{
		const double dBoundary =
				nSlice == stCandidate.nDepth ? stCandidate.dFar : stCandidate.dNear * std::exp(dLogRange * (static_cast<double>(nSlice) / stCandidate.nDepth));
		if (static_cast<float>(dBoundary) <= static_cast<float>(stCandidate.arrDepthBoundaries[nSlice - 1]))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "volume_depth", "$.volumetric_fog.distance",
								  "Adjacent fog depth slices must remain distinct in binary32.");
			return false;
		}
		stCandidate.arrDepthBoundaries[nSlice] = dBoundary;
	}
	stCandidate.nCoefficientTextureBytes = stCandidate.nFroxelCount * 16;
	stCandidate.nIntegralTextureBytes = stCandidate.nFroxelCount * 8;
	stCandidate.nCurrentFrameBytes = stCandidate.nCoefficientTextureBytes * 3 + stCandidate.nIntegralTextureBytes;
	stCandidate.nHistoryBytes = stCandidate.nCoefficientTextureBytes * 2;
	stCandidate.nResidentVolumeBytes = stCandidate.nCurrentFrameBytes * 3 + stCandidate.nHistoryBytes;
	out_stGrid = stCandidate;
	return true;
}

} // namespace EngineNext::Rendering
