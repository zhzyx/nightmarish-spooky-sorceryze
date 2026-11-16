/**************************************************************************/
/*  ShadowData.cpp                                                        */
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

#include "engine_next/include/EngineNext/Rendering/ShadowData.h"

#include "engine_next/include/EngineNext/Rendering/CameraMatrices.h"
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::size_t MAX_CASTER_COUNT = 65536;
constexpr double PI = 3.141592653589793238462643383279502884;
constexpr double RADIUS_ROUNDING_SCALE = 16.0;
using Vector = std::array<double, 3>;
using Corners = std::array<Vector, 8>;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pCode, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, "$.shadows", pMessage);
	return false;
}

bool IsInRange(double dValue, double dMinimum, double dMaximum) noexcept
{
	return std::isfinite(dValue) && dValue >= dMinimum && dValue <= dMaximum;
}

bool Normalize(Vector &out_arrVector) noexcept
{
	const double dScale = (std::max)({ std::abs(out_arrVector[0]), std::abs(out_arrVector[1]), std::abs(out_arrVector[2]) });
	if (dScale == 0.0 || !std::isfinite(dScale))
	{
		return false;
	}
	double dLengthSquared = 0.0;
	for (double &dValue : out_arrVector)
	{
		dValue /= dScale;
		dLengthSquared += dValue * dValue;
	}
	const double dLength = std::sqrt(dLengthSquared);
	for (double &dValue : out_arrVector)
	{
		dValue /= dLength;
	}
	return true;
}

Vector Cross(const Vector &arrLeft, const Vector &arrRight) noexcept
{
	return {
		arrLeft[1] * arrRight[2] - arrLeft[2] * arrRight[1],
		arrLeft[2] * arrRight[0] - arrLeft[0] * arrRight[2],
		arrLeft[0] * arrRight[1] - arrLeft[1] * arrRight[0],
	};
}

double Dot(const Vector &arrLeft, const Vector &arrRight) noexcept
{
	return arrLeft[0] * arrRight[0] + arrLeft[1] * arrRight[1] + arrLeft[2] * arrRight[2];
}

Corners BoundsCorners(const WorldBounds &stBounds) noexcept
{
	Corners arrCorners{};
	for (std::size_t nCorner = 0; nCorner < arrCorners.size(); ++nCorner)
	{
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrCorners[nCorner][nAxis] = (nCorner & (std::size_t{ 1 } << nAxis)) == 0 ? stBounds.arrMinimum[nAxis] : stBounds.arrMaximum[nAxis];
		}
	}
	return arrCorners;
}

Corners FrustumCorners(const CameraSettings &stCamera, const CameraMatrices &stMatrices, double dSplitNear, double dSplitFar, double dTangent, double dAspect) noexcept
{
	Corners arrCorners{};
	for (std::size_t nCorner = 0; nCorner < arrCorners.size(); ++nCorner)
	{
		const double dDistance = nCorner < 4 ? dSplitNear : dSplitFar;
		const double dX = (nCorner & 1U) == 0 ? -dDistance * dTangent * dAspect : dDistance * dTangent * dAspect;
		const double dY = (nCorner & 2U) == 0 ? -dDistance * dTangent : dDistance * dTangent;
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrCorners[nCorner][nAxis] = stCamera.arrPosition[nAxis] + stMatrices.arrView[nAxis * 4] * dX +
					stMatrices.arrView[nAxis * 4 + 1] * dY - stMatrices.arrView[nAxis * 4 + 2] * dDistance;
		}
	}
	return arrCorners;
}

bool BuildCascade(const CameraSettings &stCamera, const CameraMatrices &stMatrices, const ShadowSettings &stSettings,
				  const Vector &arrLightRight, const Vector &arrLightUp, const Vector &arrLightDirection, double dCasterNear, double dCasterFar,
				  double dFitNear, double dSplitNear, double dSplitFar, double dTangent, double dAspect, ShadowCascade &out_stCascade)
{
	const double dMiddle = (dFitNear + dSplitFar) * 0.5;
	const double dHalfDepth = (dSplitFar - dFitNear) * 0.5;
	const double dFarHeight = dSplitFar * dTangent;
	const double dRadius = std::sqrt(dFarHeight * dFarHeight * (1.0 + dAspect * dAspect) + dHalfDepth * dHalfDepth);
	const double dRoundedRadius = std::ceil(dRadius * RADIUS_ROUNDING_SCALE) / RADIUS_ROUNDING_SCALE;
	// One texel of padding absorbs at most half a texel of center snapping.
	const double dExtent = dRoundedRadius * stSettings.nResolution / (stSettings.nResolution - 2.0);
	const double dTexelSize = 2.0 * dExtent / stSettings.nResolution;
	Vector arrCenter{};
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		arrCenter[nAxis] = stCamera.arrPosition[nAxis] - stMatrices.arrView[nAxis * 4 + 2] * dMiddle;
	}
	const double dCenterX = std::round(Dot(arrLightRight, arrCenter) / dTexelSize) * dTexelSize;
	const double dCenterY = std::round(Dot(arrLightUp, arrCenter) / dTexelSize) * dTexelSize;
	double dLightNear = dCasterNear;
	double dLightFar = dCasterFar;
	const Corners arrCorners = FrustumCorners(stCamera, stMatrices, dFitNear, dSplitFar, dTangent, dAspect);
	for (const Vector &arrCorner : arrCorners)
	{
		const double dDepth = Dot(arrLightDirection, arrCorner);
		dLightNear = (std::min)(dLightNear, dDepth);
		dLightFar = (std::max)(dLightFar, dDepth);
	}
	const double dPadding = (std::max)(1.0, (dLightFar - dLightNear) * 0.01);
	dLightNear -= dPadding;
	dLightFar += dPadding;
	const double dInverseDepth = 1.0 / (dLightFar - dLightNear);
	ShadowCascade stCascade;
	stCascade.dSplitNear = dSplitNear;
	stCascade.dSplitFar = dSplitFar;
	stCascade.dWorldUnitsPerTexel = dTexelSize;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		stCascade.arrViewProjection[nAxis * 4] = arrLightRight[nAxis] / dExtent;
		stCascade.arrViewProjection[nAxis * 4 + 1] = arrLightUp[nAxis] / dExtent;
		stCascade.arrViewProjection[nAxis * 4 + 2] = -arrLightDirection[nAxis] * dInverseDepth;
	}
	stCascade.arrViewProjection[12] = -dCenterX / dExtent;
	stCascade.arrViewProjection[13] = -dCenterY / dExtent;
	stCascade.arrViewProjection[14] = dLightFar * dInverseDepth;
	stCascade.arrViewProjection[15] = 1.0;
	for (double dValue : stCascade.arrViewProjection)
	{
		if (!IsInRange(dValue, -std::numeric_limits<float>::max(), std::numeric_limits<float>::max()))
		{
			return false;
		}
	}
	if (!IsInRange(dTexelSize, std::numeric_limits<float>::denorm_min(), std::numeric_limits<float>::max()))
	{
		return false;
	}
	out_stCascade = stCascade;
	return true;
}

} // namespace

bool BuildDirectionalShadows(const CameraSettings &stCamera, std::uint32_t nViewportWidth, std::uint32_t nViewportHeight,
							 const DirectionalLightSettings &stLight, const ShadowSettings &stSettings, const std::vector<WorldBounds> &arrCasters,
							 ShadowData &out_stData, Assets::Diagnostics &out_arrDiagnostics)
{
	CameraMatrices stMatrices;
	if (!BuildCameraMatrices(stCamera, nViewportWidth, nViewportHeight, { 0, 0 }, stMatrices, out_arrDiagnostics))
	{
		return false;
	}
	const bool bValidResolution = stSettings.nResolution == 256 || stSettings.nResolution == 512 || stSettings.nResolution == 1024 ||
			stSettings.nResolution == 2048 || stSettings.nResolution == 4096;
	if (!bValidResolution || !IsInRange(stSettings.dDistance, 0.1, 1.0e4) || stSettings.dDistance <= stCamera.dNearPlane ||
		!IsInRange(stSettings.dSplitLambda, 0.0, 1.0) || !IsInRange(stSettings.dDepthBias, 0.0, 0.05) || !IsInRange(stSettings.dNormalBias, 0.0, 1.0) ||
		arrCasters.size() > MAX_CASTER_COUNT)
	{
		return Fail(out_arrDiagnostics, "shadow_settings", "Shadow resolution, distance, split, bias or caster count is outside the supported limits.");
	}
	Vector arrLightDirection = stLight.arrDirection;
	for (double dValue : arrLightDirection)
	{
		if (!std::isfinite(dValue))
		{
			return Fail(out_arrDiagnostics, "shadow_direction", "Directional light rays require a finite nonzero direction.");
		}
	}
	if (!Normalize(arrLightDirection))
	{
		return Fail(out_arrDiagnostics, "shadow_direction", "Directional light rays require a finite nonzero direction.");
	}
	const Vector arrReferenceUp = std::abs(arrLightDirection[1]) < 0.99 ? Vector{ 0, 1, 0 } : Vector{ 1, 0, 0 };
	Vector arrLightRight = Cross(arrLightDirection, arrReferenceUp);
	(void)Normalize(arrLightRight);
	const Vector arrLightUp = Cross(arrLightRight, arrLightDirection);
	double dCasterNear = std::numeric_limits<double>::infinity();
	double dCasterFar = -std::numeric_limits<double>::infinity();
	for (const WorldBounds &stBounds : arrCasters)
	{
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			if (!IsInRange(stBounds.arrMinimum[nAxis], -std::numeric_limits<float>::max(), std::numeric_limits<float>::max()) ||
				!IsInRange(stBounds.arrMaximum[nAxis], stBounds.arrMinimum[nAxis], std::numeric_limits<float>::max()))
			{
				return Fail(out_arrDiagnostics, "shadow_bounds", "Caster bounds must be ordered and finite in binary32 range.");
			}
		}
		for (const Vector &arrCorner : BoundsCorners(stBounds))
		{
			const double dDepth = Dot(arrLightDirection, arrCorner);
			dCasterNear = (std::min)(dCasterNear, dDepth);
			dCasterFar = (std::max)(dCasterFar, dDepth);
		}
	}
	const double dShadowFar = (std::min)(stCamera.dFarPlane, stSettings.dDistance);
	if (static_cast<float>(dShadowFar) <= static_cast<float>(stCamera.dNearPlane))
	{
		return Fail(out_arrDiagnostics, "shadow_split_range", "Shadow distance and camera near plane must remain distinct in binary32.");
	}
	const double dTangent = std::tan(stCamera.dVerticalFovDegrees * PI / 360.0);
	const double dAspect = static_cast<double>(nViewportWidth) / nViewportHeight;
	ShadowData stData;
	double dSplitNear = stCamera.dNearPlane;
	for (std::size_t nCascade = 0; nCascade < stData.arrCascades.size(); ++nCascade)
	{
		const double dFraction = static_cast<double>(nCascade + 1) / stData.arrCascades.size();
		const double dLogSplit = stCamera.dNearPlane * std::pow(dShadowFar / stCamera.dNearPlane, dFraction);
		const double dLinearSplit = stCamera.dNearPlane + (dShadowFar - stCamera.dNearPlane) * dFraction;
		const double dSplitFar = nCascade + 1 == stData.arrCascades.size() ? dShadowFar : stSettings.dSplitLambda * dLogSplit + (1.0 - stSettings.dSplitLambda) * dLinearSplit;
		if (static_cast<float>(dSplitFar) <= static_cast<float>(dSplitNear))
		{
			return Fail(out_arrDiagnostics, "shadow_split_range", "Each cascade must span a distinct binary32 camera-depth interval.");
		}
		// The preceding cascade samples this cascade throughout its transition.
		// Cascade zero's shader transition uses zero as its interval start.
		const double dPreviousStart = nCascade < 2 ? 0.0 : stData.arrCascades[nCascade - 1].dSplitNear;
		const double dFitNear = nCascade == 0 ? dSplitNear : (std::max)(stCamera.dNearPlane, dSplitNear - (dSplitNear - dPreviousStart) * SHADOW_CASCADE_BLEND_FRACTION);
		if (!BuildCascade(stCamera, stMatrices, stSettings, arrLightRight, arrLightUp, arrLightDirection, dCasterNear, dCasterFar,
						  dFitNear, dSplitNear, dSplitFar, dTangent, dAspect, stData.arrCascades[nCascade]))
		{
			return Fail(out_arrDiagnostics, "shadow_matrix_range", "Directional shadow matrices exceed binary32 range.");
		}
		dSplitNear = dSplitFar;
	}
	out_stData = stData;
	return true;
}

} // namespace EngineNext::Rendering
