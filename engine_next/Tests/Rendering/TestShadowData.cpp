/**************************************************************************/
/*  TestShadowData.cpp                                                    */
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
#include "engine_next/include/EngineNext/Rendering/CameraMatrices.h"
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"
#include "engine_next/include/EngineNext/Rendering/ShadowData.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace
{

using EngineNext::Rendering::CameraSettings;
using EngineNext::Rendering::DirectionalLightSettings;
using EngineNext::Rendering::ShadowCascade;
using EngineNext::Rendering::ShadowData;
using EngineNext::Rendering::ShadowSettings;
using EngineNext::Rendering::WorldBounds;
using Point = std::array<double, 3>;

Point Project(const ShadowCascade &stCascade, const Point &arrPoint)
{
	Point arrResult{};
	for (std::size_t nRow = 0; nRow < 3; ++nRow)
	{
		arrResult[nRow] = stCascade.arrViewProjection[12 + nRow];
		for (std::size_t nColumn = 0; nColumn < 3; ++nColumn)
		{
			arrResult[nRow] += stCascade.arrViewProjection[nColumn * 4 + nRow] * arrPoint[nColumn];
		}
	}
	return arrResult;
}

bool Build(const CameraSettings &stCamera, const DirectionalLightSettings &stLight, const ShadowSettings &stSettings, const std::vector<WorldBounds> &arrCasters, ShadowData &out_stData)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return EngineNext::Rendering::BuildDirectionalShadows(stCamera, 1920, 1080, stLight, stSettings, arrCasters, out_stData, arrDiagnostics);
}

void CheckNear(double dActual, double dExpected, double dTolerance = 1.0e-10)
{
	ENGINE_NEXT_CHECK(std::abs(dActual - dExpected) <= dTolerance * (std::max)(1.0, std::abs(dExpected)));
}

void CheckFrustum(const CameraSettings &stCamera, const ShadowData &stData, std::uint32_t nWidth = 1920, std::uint32_t nHeight = 1080)
{
	EngineNext::Rendering::CameraMatrices stCameraMatrices;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildCameraMatrices(stCamera, nWidth, nHeight, { 0, 0 }, stCameraMatrices, arrDiagnostics));
	const double dTangent = std::tan(stCamera.dVerticalFovDegrees * 3.14159265358979323846 / 360.0);
	const double dAspect = static_cast<double>(nWidth) / nHeight;
	for (const ShadowCascade &stCascade : stData.arrCascades)
	{
		for (std::size_t nCorner = 0; nCorner < 8; ++nCorner)
		{
			const double dDepth = nCorner < 4 ? stCascade.dSplitNear : stCascade.dSplitFar;
			const double dX = ((nCorner & 1U) == 0 ? -1.0 : 1.0) * dDepth * dTangent * dAspect;
			const double dY = ((nCorner & 2U) == 0 ? -1.0 : 1.0) * dDepth * dTangent;
			Point arrWorld{};
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrWorld[nAxis] = stCamera.arrPosition[nAxis] + dX * stCameraMatrices.arrView[nAxis * 4] +
						dY * stCameraMatrices.arrView[nAxis * 4 + 1] - dDepth * stCameraMatrices.arrView[nAxis * 4 + 2];
			}
			const Point arrClip = Project(stCascade, arrWorld);
			ENGINE_NEXT_CHECK(std::abs(arrClip[0]) <= 1.0 + 1.0e-10);
			ENGINE_NEXT_CHECK(std::abs(arrClip[1]) <= 1.0 + 1.0e-10);
			ENGINE_NEXT_CHECK(arrClip[2] >= -1.0e-10 && arrClip[2] <= 1.0 + 1.0e-10);
		}
	}
}

void CheckFailure(const CameraSettings &stCamera, const DirectionalLightSettings &stLight, const ShadowSettings &stSettings, const std::vector<WorldBounds> &arrCasters, std::uint32_t nWidth = 1920, std::uint32_t nHeight = 1080)
{
	ShadowData stData;
	for (ShadowCascade &stCascade : stData.arrCascades)
	{
		stCascade.arrViewProjection.fill(17.0);
		stCascade.dSplitNear = 18;
		stCascade.dSplitFar = 19;
		stCascade.dWorldUnitsPerTexel = 20;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildDirectionalShadows(stCamera, nWidth, nHeight, stLight, stSettings, arrCasters, stData, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	for (const ShadowCascade &stCascade : stData.arrCascades)
	{
		ENGINE_NEXT_CHECK_EQ(stCascade.arrViewProjection, (std::array<double, 16>{ 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17 }));
		ENGINE_NEXT_CHECK_EQ(stCascade.dSplitNear, 18);
		ENGINE_NEXT_CHECK_EQ(stCascade.dSplitFar, 19);
		ENGINE_NEXT_CHECK_EQ(stCascade.dWorldUnitsPerTexel, 20);
	}
}

} // namespace

ENGINE_NEXT_TEST("Directional shadows generate four monotonic reverse depth receiver cascades")
{
	const CameraSettings stCamera;
	const DirectionalLightSettings stLight;
	const ShadowSettings stSettings;
	ShadowData stData;
	ENGINE_NEXT_CHECK(Build(stCamera, stLight, stSettings, {}, stData));
	double dPrevious = stCamera.dNearPlane;
	for (const ShadowCascade &stCascade : stData.arrCascades)
	{
		ENGINE_NEXT_CHECK_EQ(stCascade.dSplitNear, dPrevious);
		ENGINE_NEXT_CHECK(stCascade.dSplitFar > stCascade.dSplitNear);
		ENGINE_NEXT_CHECK(stCascade.dWorldUnitsPerTexel > 0.0);
		dPrevious = stCascade.dSplitFar;
	}
	ENGINE_NEXT_CHECK_EQ(dPrevious, stSettings.dDistance);
	CheckFrustum(stCamera, stData);
	ShadowData stRepeated;
	ENGINE_NEXT_CHECK(Build(stCamera, stLight, stSettings, {}, stRepeated));
	for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		ENGINE_NEXT_CHECK_EQ(stData.arrCascades[nCascade].arrViewProjection, stRepeated.arrCascades[nCascade].arrViewProjection);
	}
}

ENGINE_NEXT_TEST("Directional shadow splits honor linear logarithmic and camera far limits")
{
	CameraSettings stCamera;
	stCamera.dNearPlane = 1;
	stCamera.dFarPlane = 16;
	ShadowSettings stSettings;
	stSettings.dDistance = 100;
	stSettings.dSplitLambda = 1;
	ShadowData stData;
	ENGINE_NEXT_CHECK(Build(stCamera, DirectionalLightSettings{}, stSettings, {}, stData));
	for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		CheckNear(stData.arrCascades[nCascade].dSplitFar, std::pow(2.0, static_cast<double>(nCascade + 1)));
	}
	stSettings.dSplitLambda = 0;
	ENGINE_NEXT_CHECK(Build(stCamera, DirectionalLightSettings{}, stSettings, {}, stData));
	for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		CheckNear(stData.arrCascades[nCascade].dSplitFar, 1.0 + 15.0 * static_cast<double>(nCascade + 1) / 4.0);
	}
}

ENGINE_NEXT_TEST("Directional shadow depth includes negative and offscreen caster bounds")
{
	DirectionalLightSettings stLight;
	stLight.arrDirection = { 0, 0, -1 };
	const std::vector<WorldBounds> arrCasters{
		{ { -3, -4, 98 }, { -1, -2, 100 } },
		{ { 10000, 10000, -200 }, { 10001, 10001, -198 } },
	};
	ShadowData stData;
	ENGINE_NEXT_CHECK(Build(CameraSettings{}, stLight, ShadowSettings{}, arrCasters, stData));
	for (const ShadowCascade &stCascade : stData.arrCascades)
	{
		for (const WorldBounds &stBounds : arrCasters)
		{
			for (std::size_t nCorner = 0; nCorner < 8; ++nCorner)
			{
				Point arrWorld{};
				for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
				{
					arrWorld[nAxis] = (nCorner & (std::size_t{ 1 } << nAxis)) == 0 ? stBounds.arrMinimum[nAxis] : stBounds.arrMaximum[nAxis];
				}
				const double dDepth = Project(stCascade, arrWorld)[2];
				ENGINE_NEXT_CHECK(dDepth >= 0 && dDepth <= 1);
			}
		}
		ENGINE_NEXT_CHECK(Project(stCascade, { 0, 0, 100 })[2] > Project(stCascade, { 0, 0, -200 })[2]);
	}
	CheckFrustum(CameraSettings{}, stData);
}

ENGINE_NEXT_TEST("Directional shadow texel snapping stabilizes subtexel camera translation")
{
	CameraSettings stCamera;
	DirectionalLightSettings stLight;
	stLight.arrDirection = { 0, 0, -1 };
	const ShadowSettings stSettings;
	ShadowData stOriginal;
	ENGINE_NEXT_CHECK(Build(stCamera, stLight, stSettings, {}, stOriginal));
	const double dDelta = stOriginal.arrCascades[0].dWorldUnitsPerTexel * 0.2;
	stCamera.arrPosition[0] += dDelta;
	stCamera.arrTarget[0] += dDelta;
	ShadowData stShifted;
	ENGINE_NEXT_CHECK(Build(stCamera, stLight, stSettings, {}, stShifted));
	for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		ENGINE_NEXT_CHECK_EQ(stOriginal.arrCascades[nCascade].arrViewProjection, stShifted.arrCascades[nCascade].arrViewProjection);
		ENGINE_NEXT_CHECK_EQ(stOriginal.arrCascades[nCascade].dWorldUnitsPerTexel, stShifted.arrCascades[nCascade].dWorldUnitsPerTexel);
	}
	stCamera.arrPosition[0] = stOriginal.arrCascades[0].dWorldUnitsPerTexel * 0.75;
	stCamera.arrTarget[0] = stCamera.arrPosition[0];
	ENGINE_NEXT_CHECK(Build(stCamera, stLight, stSettings, {}, stShifted));
	const double dClipShift = stShifted.arrCascades[0].arrViewProjection[12] - stOriginal.arrCascades[0].arrViewProjection[12];
	CheckNear(dClipShift, -2.0 / stSettings.nResolution);
}

ENGINE_NEXT_TEST("Directional shadow receiver sphere remains stable for rotated camera and vertical light")
{
	CameraSettings stCamera;
	stCamera.arrPosition = { -12, 4, -5 };
	stCamera.arrTarget = { -11, 5, -3 };
	DirectionalLightSettings stLight;
	stLight.arrDirection = { 0, -1, 0 };
	ShadowData stData;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildDirectionalShadows(stCamera, 1080, 1920, stLight, ShadowSettings{}, {}, stData, arrDiagnostics));
	CheckFrustum(stCamera, stData, 1080, 1920);
	stLight.arrDirection = { 0, 1, 0 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildDirectionalShadows(stCamera, 1080, 1920, stLight, ShadowSettings{}, {}, stData, arrDiagnostics));
	CheckFrustum(stCamera, stData, 1080, 1920);
	stLight.arrDirection = { std::numeric_limits<double>::denorm_min(), 0, 0 };
	ENGINE_NEXT_CHECK(Build(stCamera, stLight, ShadowSettings{}, {}, stData));
	CheckFrustum(stCamera, stData);
}

ENGINE_NEXT_TEST("Directional shadow validation preserves output for invalid configuration and bounds")
{
	const CameraSettings stCamera;
	DirectionalLightSettings stLight;
	ShadowSettings stSettings;
	stLight.arrDirection = { 0, 0, 0 };
	CheckFailure(stCamera, stLight, stSettings, {});
	stLight.arrDirection = { 0, std::numeric_limits<double>::infinity(), 0 };
	CheckFailure(stCamera, stLight, stSettings, {});
	stLight = DirectionalLightSettings{};
	for (std::uint32_t nResolution : { 0U, 128U, 257U, 8192U })
	{
		stSettings.nResolution = nResolution;
		CheckFailure(stCamera, stLight, stSettings, {});
	}
	stSettings = ShadowSettings{};
	stSettings.dDistance = stCamera.dNearPlane;
	CheckFailure(stCamera, stLight, stSettings, {});
	stSettings.dDistance = 10001;
	CheckFailure(stCamera, stLight, stSettings, {});
	stSettings = ShadowSettings{};
	stSettings.dSplitLambda = -0.1;
	CheckFailure(stCamera, stLight, stSettings, {});
	stSettings.dSplitLambda = std::numeric_limits<double>::quiet_NaN();
	CheckFailure(stCamera, stLight, stSettings, {});
	stSettings = ShadowSettings{};
	stSettings.dDepthBias = 0.051;
	CheckFailure(stCamera, stLight, stSettings, {});
	stSettings = ShadowSettings{};
	stSettings.dNormalBias = -0.1;
	CheckFailure(stCamera, stLight, stSettings, {});
	stSettings = ShadowSettings{};
	CheckFailure(stCamera, stLight, stSettings, { { { 0, 0, 0 }, { -1, 1, 1 } } });
	CheckFailure(stCamera, stLight, stSettings, { { { 0, 0, 0 }, { 1, std::numeric_limits<double>::quiet_NaN(), 1 } } });
	CheckFailure(stCamera, stLight, stSettings, { { { 0, 0, 0 }, { 1, 1, std::numeric_limits<double>::max() } } });
	CheckFailure(stCamera, stLight, stSettings, std::vector<WorldBounds>(65537));
	CheckFailure(stCamera, stLight, stSettings, {}, 0, 1080);
}

ENGINE_NEXT_TEST("Directional shadows preserve rounded receiver scale under camera rotation")
{
	CameraSettings stCamera;
	stCamera.arrPosition = { 0, 0, 0 };
	stCamera.arrTarget = { 0, 0, -1 };
	ShadowData stFirst;
	ShadowData stSecond;
	ENGINE_NEXT_CHECK(Build(stCamera, DirectionalLightSettings{}, ShadowSettings{}, {}, stFirst));
	stCamera.arrTarget = { 1, 0.5, -2 };
	ENGINE_NEXT_CHECK(Build(stCamera, DirectionalLightSettings{}, ShadowSettings{}, {}, stSecond));
	for (std::size_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		ENGINE_NEXT_CHECK_EQ(stFirst.arrCascades[nCascade].dWorldUnitsPerTexel, stSecond.arrCascades[nCascade].dWorldUnitsPerTexel);
	}
	CheckFrustum(stCamera, stSecond);
}

ENGINE_NEXT_TEST("Directional shadows validate representable split intervals and maximum caster count")
{
	CameraSettings stCamera;
	stCamera.dNearPlane = 1.0;
	ShadowSettings stSettings;
	stSettings.dDistance = std::nextafter(1.0, 2.0);
	CheckFailure(stCamera, DirectionalLightSettings{}, stSettings, {});
	stSettings.dDistance = static_cast<double>(std::nextafter(1.0F, 2.0F));
	CheckFailure(stCamera, DirectionalLightSettings{}, stSettings, {});
	ShadowData stData;
	stSettings = ShadowSettings{};
	stSettings.bEnabled = false;
	ENGINE_NEXT_CHECK(Build(stCamera, DirectionalLightSettings{}, stSettings, std::vector<WorldBounds>(65536), stData));
	const float fLimit = std::numeric_limits<float>::max();
	ENGINE_NEXT_CHECK(Build(CameraSettings{}, DirectionalLightSettings{}, ShadowSettings{}, { { { -fLimit, -fLimit, -fLimit }, { fLimit, fLimit, fLimit } } }, stData));
	for (const ShadowCascade &stCascade : stData.arrCascades)
	{
		for (double dValue : stCascade.arrViewProjection)
		{
			ENGINE_NEXT_CHECK(std::isfinite(dValue));
			ENGINE_NEXT_CHECK(std::abs(dValue) <= std::numeric_limits<float>::max());
		}
	}
}

ENGINE_NEXT_TEST("Directional shadows cover the full preceding cascade blend interval")
{
	CameraSettings stCamera;
	stCamera.dVerticalFovDegrees = 1.0;
	DirectionalLightSettings stLight;
	stLight.arrDirection = { 1, 0, 0 };
	ShadowSettings stSettings;
	stSettings.dSplitLambda = 0;
	ShadowData stData;
	ENGINE_NEXT_CHECK(Build(stCamera, stLight, stSettings, {}, stData));
	ShadowData stBlendCoverage = stData;
	for (std::size_t nCascade = 1; nCascade < 4; ++nCascade)
	{
		const double dPreviousStart = nCascade == 1 ? 0.0 : stData.arrCascades[nCascade - 1].dSplitNear;
		const double dSplitNear = stData.arrCascades[nCascade].dSplitNear;
		stBlendCoverage.arrCascades[nCascade].dSplitNear = (std::max)(stCamera.dNearPlane, dSplitNear - (dSplitNear - dPreviousStart) * 0.1);
		ENGINE_NEXT_CHECK_EQ(stData.arrCascades[nCascade].dSplitNear, stData.arrCascades[nCascade - 1].dSplitFar);
	}
	CheckFrustum(stCamera, stBlendCoverage);
}
