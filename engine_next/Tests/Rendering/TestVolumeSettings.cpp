/**************************************************************************/
/*  TestVolumeSettings.cpp                                                */
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
#include "engine_next/include/EngineNext/Rendering/VolumeSettings.h"
#include "engine_next/Tests/TestFramework.h"
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <array>
#include <cmath>
#include <cstdint>
#include <initializer_list>
#include <limits>

namespace
{

using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::BuildVolumeGrid;
using EngineNext::Rendering::CameraSettings;
using EngineNext::Rendering::LocalVolumeShape;
using EngineNext::Rendering::ValidateVolumeSettings;
using EngineNext::Rendering::VolumeGrid;
using EngineNext::Rendering::VolumeSettings;

} // namespace

ENGINE_NEXT_TEST("Volume settings have disabled bounded value defaults")
{
	const VolumeSettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!stSettings.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.dDistance, 100);
	ENGINE_NEXT_CHECK_EQ(stSettings.nCellPixels, 16U);
	ENGINE_NEXT_CHECK_EQ(stSettings.nDepthSlices, 64U);
	ENGINE_NEXT_CHECK_EQ(stSettings.dDensity, .01);
	ENGINE_NEXT_CHECK_EQ(stSettings.dHeight, 0);
	ENGINE_NEXT_CHECK_EQ(stSettings.dHeightFalloff, .1);
	ENGINE_NEXT_CHECK_EQ(stSettings.dPhaseG, .2);
	ENGINE_NEXT_CHECK_EQ(stSettings.dHistoryWeight, .85);
	ENGINE_NEXT_CHECK_EQ(stSettings.nLocalVolumeCount, 0U);
	ENGINE_NEXT_CHECK(ValidateVolumeSettings(stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Volume settings accept finite inclusive coefficient ranges")
{
	for (double dDensity : { 0.0, 65504.0 })
	{
		for (double dPhase : { -.95, .95 })
		{
			VolumeSettings stSettings;
			stSettings.dDensity = dDensity;
			stSettings.dPhaseG = dPhase;
			stSettings.dHeightFalloff = dDensity;
			stSettings.arrAlbedo = { 0, 1, .5 };
			stSettings.arrEmission = { 0, 65504, 1 };
			stSettings.dHistoryWeight = .99;
			stSettings.nLocalVolumeCount = 16;
			Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(ValidateVolumeSettings(stSettings, arrDiagnostics));
		}
	}
}

ENGINE_NEXT_TEST("Volume settings reject invalid values with disabled mode")
{
	double VolumeSettings::*arrFields[] = { &VolumeSettings::dDensity, &VolumeSettings::dHeightFalloff, &VolumeSettings::dDistance };
	for (double VolumeSettings::*pField : arrFields)
	{
		for (double dInvalid : { -1.0, std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
		{
			VolumeSettings stSettings;
			stSettings.*pField = dInvalid;
			Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
			ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
		}
	}
	for (double dInvalid : { -.01, 1.0, std::numeric_limits<double>::quiet_NaN() })
	{
		VolumeSettings stSettings;
		stSettings.dHistoryWeight = dInvalid;
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	}
	for (std::uint32_t nInvalid : { 0U, 7U, 17U, 256U })
	{
		VolumeSettings stSettings;
		stSettings.nCellPixels = nInvalid;
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	}
	VolumeSettings stSettings;
	stSettings.nLocalVolumeCount = 17;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings = VolumeSettings{};
	stSettings.arrEmission[1] = 65505;
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings = VolumeSettings{};
	stSettings.dPhaseG = .95001;
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings = VolumeSettings{};
	stSettings.dHeight = std::numeric_limits<double>::max();
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Local volumes validate finite world bounds and optional identities")
{
	VolumeSettings stSettings;
	stSettings.nLocalVolumeCount = 1;
	stSettings.arrLocalVolumes[0].nEntityId = std::numeric_limits<std::uint64_t>::max();
	stSettings.arrLocalVolumes[0].arrCenter = { -20, -5, -10 };
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.arrLocalVolumes[0].nEntityId = 0;
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.arrLocalVolumes[0].nEntityId.reset();
	stSettings.arrLocalVolumes[0].eShape = LocalVolumeShape::Sphere;
	stSettings.arrLocalVolumes[0].arrExtent = { 1, 2, 1 };
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.arrLocalVolumes[0].arrExtent = { 2, 2, 2 };
	ENGINE_NEXT_CHECK(ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.arrLocalVolumes[0].arrExtent[0] = 0;
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.arrLocalVolumes[0].eShape = LocalVolumeShape::Box;
	stSettings.arrLocalVolumes[0].arrExtent = { std::numeric_limits<float>::max(), 1, 1 };
	stSettings.arrLocalVolumes[0].arrCenter[0] = std::numeric_limits<float>::max();
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.arrLocalVolumes[0].arrExtent = { 1, 1, 1 };
	stSettings.arrLocalVolumes[0].arrCenter = { 1e20, 0, 0 };
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.arrLocalVolumes[0].arrCenter = { 0, 0, 0 };
	stSettings.arrLocalVolumes[0].eShape = static_cast<LocalVolumeShape>(3);
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Volume grid computes 4K dimensions and explicit texture payload bytes")
{
	VolumeSettings stSettings;
	CameraSettings stCamera;
	VolumeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildVolumeGrid(stCamera, 3840, 2160, stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.nWidth, 240U);
	ENGINE_NEXT_CHECK_EQ(stGrid.nHeight, 135U);
	ENGINE_NEXT_CHECK_EQ(stGrid.nDepth, 64U);
	ENGINE_NEXT_CHECK_EQ(stGrid.nFroxelCount, 2073600ULL);
	ENGINE_NEXT_CHECK_EQ(stGrid.nCoefficientTextureBytes, 33177600ULL);
	ENGINE_NEXT_CHECK_EQ(stGrid.nIntegralTextureBytes, 16588800ULL);
	ENGINE_NEXT_CHECK_EQ(stGrid.nCurrentFrameBytes, 116121600ULL);
	ENGINE_NEXT_CHECK_EQ(stGrid.nHistoryBytes, 66355200ULL);
	ENGINE_NEXT_CHECK_EQ(stGrid.nResidentVolumeBytes, 414720000ULL);
	ENGINE_NEXT_CHECK_EQ(stGrid.dNear, .05);
	ENGINE_NEXT_CHECK_EQ(stGrid.dFar, 100);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrDepthBoundaries[0], .05);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrDepthBoundaries[64], 100);
	for (std::uint32_t nSlice = 1; nSlice <= stGrid.nDepth; ++nSlice)
	{
		ENGINE_NEXT_CHECK(stGrid.arrDepthBoundaries[nSlice] > stGrid.arrDepthBoundaries[nSlice - 1]);
		ENGINE_NEXT_CHECK(static_cast<float>(stGrid.arrDepthBoundaries[nSlice]) > static_cast<float>(stGrid.arrDepthBoundaries[nSlice - 1]));
	}
}

ENGINE_NEXT_TEST("Volume grid handles odd viewports and camera far truncation")
{
	VolumeSettings stSettings;
	CameraSettings stCamera;
	stCamera.dFarPlane = 25;
	VolumeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildVolumeGrid(stCamera, 1, 1, stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.nWidth, 1U);
	ENGINE_NEXT_CHECK_EQ(stGrid.nHeight, 1U);
	ENGINE_NEXT_CHECK_EQ(stGrid.dFar, 25);
	ENGINE_NEXT_CHECK(BuildVolumeGrid(stCamera, 1919, 1079, stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.nWidth, 120U);
	ENGINE_NEXT_CHECK_EQ(stGrid.nHeight, 68U);
}

ENGINE_NEXT_TEST("Volume grid preserves previous output on budget and numeric rejection")
{
	VolumeSettings stSettings;
	CameraSettings stCamera;
	VolumeGrid stGrid;
	stGrid.nWidth = 37;
	stGrid.dNear = 123;
	Diagnostics arrDiagnostics;
	stSettings.nCellPixels = 8;
	ENGINE_NEXT_CHECK(!BuildVolumeGrid(stCamera, 16384, 16384, stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.nWidth, 37U);
	ENGINE_NEXT_CHECK_EQ(stGrid.dNear, 123);
	stSettings = VolumeSettings{};
	ENGINE_NEXT_CHECK(!BuildVolumeGrid(stCamera, 0, 480, stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK(!BuildVolumeGrid(stCamera, std::numeric_limits<std::uint32_t>::max(), 480, stSettings, stGrid, arrDiagnostics));
	stSettings.dDistance = stCamera.dNearPlane;
	ENGINE_NEXT_CHECK(!BuildVolumeGrid(stCamera, 640, 480, stSettings, stGrid, arrDiagnostics));
	stSettings.dDistance = std::nextafter(stCamera.dNearPlane, 1.0);
	ENGINE_NEXT_CHECK(!BuildVolumeGrid(stCamera, 640, 480, stSettings, stGrid, arrDiagnostics));
	stSettings.dDistance = static_cast<double>(std::nextafter(static_cast<float>(stCamera.dNearPlane), 1.0f));
	ENGINE_NEXT_CHECK(!BuildVolumeGrid(stCamera, 640, 480, stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.nWidth, 37U);
	ENGINE_NEXT_CHECK_EQ(stGrid.dNear, 123);
}

ENGINE_NEXT_TEST("Volume grid accepts exact froxel budget across supported dimensions")
{
	for (std::uint32_t nCell : { 8U, 16U, 32U })
	{
		for (std::uint32_t nSlices : { 32U, 64U, 96U, 128U })
		{
			VolumeSettings stSettings;
			stSettings.nCellPixels = nCell;
			stSettings.nDepthSlices = nSlices;
			VolumeGrid stGrid;
			Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(BuildVolumeGrid(CameraSettings{}, 640, 480, stSettings, stGrid, arrDiagnostics));
			ENGINE_NEXT_CHECK_EQ(stGrid.nDepth, nSlices);
		}
	}
	VolumeSettings stSettings;
	stSettings.nCellPixels = 8;
	stSettings.nDepthSlices = 128;
	VolumeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildVolumeGrid(CameraSettings{}, 2048, 2048, stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.nFroxelCount, EngineNext::Rendering::MAX_VOLUME_FROXELS);
	ENGINE_NEXT_CHECK(!BuildVolumeGrid(CameraSettings{}, 2049, 2048, stSettings, stGrid, arrDiagnostics));
}

ENGINE_NEXT_TEST("Volume GPU coefficients preserve zero and reject subnormal inputs")
{
	VolumeSettings stSettings;
	Diagnostics arrDiagnostics;
	stSettings.dDensity = std::numeric_limits<float>::min();
	stSettings.dHeightFalloff = std::numeric_limits<float>::min();
	stSettings.arrEmission = { std::numeric_limits<float>::min(), 0, 0 };
	ENGINE_NEXT_CHECK(ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.dDensity = std::numeric_limits<float>::denorm_min();
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.dDensity = 0;
	stSettings.dHeightFalloff = std::numeric_limits<float>::denorm_min();
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
	stSettings.dHeightFalloff = 0;
	stSettings.arrEmission[0] = std::numeric_limits<double>::min();
	ENGINE_NEXT_CHECK(!ValidateVolumeSettings(stSettings, arrDiagnostics));
}
