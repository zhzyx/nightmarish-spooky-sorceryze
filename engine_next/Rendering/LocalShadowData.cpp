/**************************************************************************/
/*  LocalShadowData.cpp                                                   */
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

#include "engine_next/include/EngineNext/Rendering/LocalShadowData.h"

#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::size_t MAX_LIGHTS_PER_KIND = 4;
constexpr double PI = 3.141592653589793238462643383279502884;
using Vector = std::array<double, 3>;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pCode, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, "$.local_shadows", pMessage);
	return false;
}

bool IsInRange(double dValue, double dMinimum, double dMaximum) noexcept
{
	return std::isfinite(dValue) && dValue >= dMinimum && dValue <= dMaximum;
}

bool Normalize(Vector &out_arrVector) noexcept
{
	const double dScale = (std::max)({ std::abs(out_arrVector[0]), std::abs(out_arrVector[1]), std::abs(out_arrVector[2]) });
	if (dScale == 0 || !std::isfinite(dScale))
	{
		return false;
	}
	double dLengthSquared = 0;
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

bool ValidateLight(std::uint32_t nId, const Vector &arrPosition, const Vector &arrColor, double dLumens, double dRange,
				   std::vector<std::uint32_t> &out_arrIds, Assets::Diagnostics &out_arrDiagnostics)
{
	if (nId == 0 || std::find(out_arrIds.begin(), out_arrIds.end(), nId) != out_arrIds.end())
	{
		return Fail(out_arrDiagnostics, "local_shadow_id", "Local lights require unique nonzero IDs across point and spot lights.");
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!IsInRange(arrPosition[nAxis], -std::numeric_limits<float>::max(), std::numeric_limits<float>::max()) || !IsInRange(arrColor[nAxis], 0.0, 100.0))
		{
			return Fail(out_arrDiagnostics, "local_shadow_light", "Local light coordinates or color are outside the finite GPU range.");
		}
	}
	if (!IsInRange(dLumens, 0.0, 1.0e8) || !IsInRange(dRange, 0.1, 1.0e4))
	{
		return Fail(out_arrDiagnostics, "local_shadow_light", "Local light lumens or range are outside the supported limits.");
	}
	out_arrIds.push_back(nId);
	return true;
}

bool BuildView(const Vector &arrPosition, const Vector &arrDirection, const Vector &arrReferenceUp, double dRange,
			   double dHalfAngleDegrees, std::uint32_t nId, std::uint32_t nFace, LocalShadowView &out_stView)
{
	Vector arrRight = Cross(arrDirection, arrReferenceUp);
	if (!Normalize(arrRight))
	{
		return false;
	}
	const Vector arrUp = Cross(arrRight, arrDirection);
	const Vector arrBackward{ -arrDirection[0], -arrDirection[1], -arrDirection[2] };
	const double dTangent = std::tan(dHalfAngleDegrees * (PI / 180.0));
	const double dScale = 1.0 / dTangent;
	const double dNear = (std::min)(0.05, dRange * 0.01);
	const double dDepthScale = dNear / (dRange - dNear);
	const double dDepthOffset = dRange * dDepthScale;
	if (!std::isfinite(dScale) || dScale <= 0.0)
	{
		return false;
	}
	LocalShadowView stView;
	stView.nLightId = nId;
	stView.nFace = nFace;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		stView.arrViewProjection[nAxis * 4] = dScale * arrRight[nAxis];
		stView.arrViewProjection[nAxis * 4 + 1] = dScale * arrUp[nAxis];
		stView.arrViewProjection[nAxis * 4 + 2] = dDepthScale * arrBackward[nAxis];
		stView.arrViewProjection[nAxis * 4 + 3] = -arrBackward[nAxis];
	}
	stView.arrViewProjection[12] = -dScale * Dot(arrRight, arrPosition);
	stView.arrViewProjection[13] = -dScale * Dot(arrUp, arrPosition);
	stView.arrViewProjection[14] = dDepthOffset - dDepthScale * Dot(arrBackward, arrPosition);
	stView.arrViewProjection[15] = Dot(arrBackward, arrPosition);
	for (double dValue : stView.arrViewProjection)
	{
		if (!IsInRange(dValue, -std::numeric_limits<float>::max(), std::numeric_limits<float>::max()))
		{
			return false;
		}
	}
	out_stView = stView;
	return true;
}

} // namespace

bool BuildLocalShadows(const std::vector<PointLightSettings> &arrPointLights, const std::vector<SpotLightSettings> &arrSpotLights,
					   LocalShadowData &out_stData, Assets::Diagnostics &out_arrDiagnostics)
{
	if (arrPointLights.size() > MAX_LIGHTS_PER_KIND || arrSpotLights.size() > MAX_LIGHTS_PER_KIND)
	{
		return Fail(out_arrDiagnostics, "local_shadow_count", "At most four point lights and four spot lights are supported.");
	}
	LocalShadowData stData;
	std::vector<std::uint32_t> arrIds;
	arrIds.reserve(arrPointLights.size() + arrSpotLights.size());
	stData.arrViews.reserve(arrPointLights.size() * 6 + arrSpotLights.size());
	constexpr std::array<Vector, 6> FACE_DIRECTIONS{ {
			{ 1, 0, 0 },
			{ -1, 0, 0 },
			{ 0, 1, 0 },
			{ 0, -1, 0 },
			{ 0, 0, 1 },
			{ 0, 0, -1 },
	} };
	constexpr std::array<Vector, 6> FACE_UP{ {
			{ 0, 1, 0 },
			{ 0, 1, 0 },
			{ 0, 0, -1 },
			{ 0, 0, 1 },
			{ 0, 1, 0 },
			{ 0, 1, 0 },
	} };
	for (const PointLightSettings &stLight : arrPointLights)
	{
		if (!ValidateLight(stLight.nId, stLight.arrPosition, stLight.arrColor, stLight.dLumens, stLight.dRange, arrIds, out_arrDiagnostics))
		{
			return false;
		}
		if (!stLight.bCastsShadow)
		{
			continue;
		}
		for (std::uint32_t nFace = 0; nFace < 6; ++nFace)
		{
			LocalShadowView stView;
			if (!BuildView(stLight.arrPosition, FACE_DIRECTIONS[nFace], FACE_UP[nFace], stLight.dRange, 45.0, stLight.nId, nFace, stView))
			{
				return Fail(out_arrDiagnostics, "local_shadow_matrix", "Point-light shadow matrix exceeds the finite GPU range.");
			}
			stData.arrViews.push_back(stView);
		}
	}
	for (const SpotLightSettings &stLight : arrSpotLights)
	{
		if (!ValidateLight(stLight.nId, stLight.arrPosition, stLight.arrColor, stLight.dLumens, stLight.dRange, arrIds, out_arrDiagnostics))
		{
			return false;
		}
		Vector arrDirection = stLight.arrDirection;
		for (double dValue : arrDirection)
		{
			if (!std::isfinite(dValue))
			{
				return Fail(out_arrDiagnostics, "local_shadow_direction", "Spot light direction must be finite and nonzero.");
			}
		}
		if (!Normalize(arrDirection) || !IsInRange(stLight.dInnerAngleDegrees, 0.0, 85.0) ||
			!IsInRange(stLight.dOuterAngleDegrees, stLight.dInnerAngleDegrees, 89.0) || stLight.dOuterAngleDegrees <= stLight.dInnerAngleDegrees)
		{
			return Fail(out_arrDiagnostics, "local_shadow_direction", "Spot light direction or inner/outer cone angles are invalid.");
		}
		if (!stLight.bCastsShadow)
		{
			continue;
		}
		const Vector arrReferenceUp = std::abs(arrDirection[1]) < 0.99 ? Vector{ 0, 1, 0 } : Vector{ 1, 0, 0 };
		LocalShadowView stView;
		if (!BuildView(stLight.arrPosition, arrDirection, arrReferenceUp, stLight.dRange, stLight.dOuterAngleDegrees, stLight.nId, 0, stView))
		{
			return Fail(out_arrDiagnostics, "local_shadow_matrix", "Spot-light shadow matrix exceeds the finite GPU range.");
		}
		stData.arrViews.push_back(stView);
	}
	out_stData = std::move(stData);
	return true;
}

} // namespace EngineNext::Rendering
