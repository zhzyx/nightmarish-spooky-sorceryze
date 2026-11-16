/**************************************************************************/
/*  CameraMatrices.cpp                                                    */
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

#include "engine_next/include/EngineNext/Rendering/CameraMatrices.h"

#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>

namespace EngineNext::Rendering
{
namespace
{

constexpr double PI = 3.141592653589793238462643383279502884;
constexpr double MIN_AXIS_CROSS_SQUARED = 1.0e-24;
using Vector = std::array<double, 3>;
using Matrix = std::array<double, 16>;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pCode, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, "$.camera", pMessage);
	return false;
}

bool IsFinite(const Vector &arrVector) noexcept
{
	return std::isfinite(arrVector[0]) && std::isfinite(arrVector[1]) && std::isfinite(arrVector[2]);
}

bool Normalize(Vector &out_arrVector) noexcept
{
	const double dScale = (std::max)({ std::abs(out_arrVector[0]), std::abs(out_arrVector[1]), std::abs(out_arrVector[2]) });
	if (dScale == 0.0 || !std::isfinite(dScale))
	{
		return false;
	}
	for (double &dValue : out_arrVector)
	{
		dValue /= dScale;
	}
	const double dLength = std::sqrt(out_arrVector[0] * out_arrVector[0] + out_arrVector[1] * out_arrVector[1] + out_arrVector[2] * out_arrVector[2]);
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

Matrix Multiply(const Matrix &arrLeft, const Matrix &arrRight) noexcept
{
	Matrix arrResult{};
	for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < 4; ++nRow)
		{
			for (std::size_t nInner = 0; nInner < 4; ++nInner)
			{
				arrResult[nColumn * 4 + nRow] += arrLeft[nInner * 4 + nRow] * arrRight[nColumn * 4 + nInner];
			}
		}
	}
	return arrResult;
}

bool IsGpuRepresentable(const Matrix &arrMatrix) noexcept
{
	for (double dValue : arrMatrix)
	{
		if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
		{
			return false;
		}
	}
	return true;
}

} // namespace

bool BuildCameraMatrices(const CameraSettings &stSettings, std::uint32_t nViewportWidth, std::uint32_t nViewportHeight,
						 const std::array<double, 2> &arrJitterPixels, CameraMatrices &out_stMatrices, Assets::Diagnostics &out_arrDiagnostics)
{
	if (nViewportWidth == 0 || nViewportHeight == 0 || !std::isfinite(arrJitterPixels[0]) || !std::isfinite(arrJitterPixels[1]) ||
		!IsFinite(stSettings.arrPosition) || !IsFinite(stSettings.arrTarget) || !IsFinite(stSettings.arrUp))
	{
		return Fail(out_arrDiagnostics, "camera_matrix_input", "Camera coordinates and pixel jitter must be finite, and viewport dimensions must be positive.");
	}
	if (!std::isfinite(stSettings.dVerticalFovDegrees) || stSettings.dVerticalFovDegrees < 1.0 || stSettings.dVerticalFovDegrees > 170.0 ||
		!std::isfinite(stSettings.dNearPlane) || stSettings.dNearPlane < 0.001 || stSettings.dNearPlane > 100.0 ||
		!std::isfinite(stSettings.dFarPlane) || stSettings.dFarPlane <= stSettings.dNearPlane || stSettings.dFarPlane > 1.0e7)
	{
		return Fail(out_arrDiagnostics, "camera_matrix_projection", "Camera field of view or finite clipping planes are outside the supported ranges.");
	}
	if (static_cast<float>(stSettings.dFarPlane) <= static_cast<float>(stSettings.dNearPlane))
	{
		return Fail(out_arrDiagnostics, "camera_matrix_projection", "Near and far planes must remain distinct in binary32 GPU constants.");
	}
	Vector arrForward{};
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		arrForward[nAxis] = stSettings.arrTarget[nAxis] - stSettings.arrPosition[nAxis];
	}
	if (!IsFinite(arrForward))
	{
		const double dScale = (std::max)({ std::abs(stSettings.arrPosition[0]), std::abs(stSettings.arrPosition[1]), std::abs(stSettings.arrPosition[2]),
										   std::abs(stSettings.arrTarget[0]), std::abs(stSettings.arrTarget[1]), std::abs(stSettings.arrTarget[2]) });
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrForward[nAxis] = stSettings.arrTarget[nAxis] / dScale - stSettings.arrPosition[nAxis] / dScale;
		}
	}
	Vector arrUp = stSettings.arrUp;
	if (!Normalize(arrForward) || !Normalize(arrUp))
	{
		return Fail(out_arrDiagnostics, "camera_matrix_axes", "Camera direction and up axes must have nonzero length.");
	}
	Vector arrRight = Cross(arrForward, arrUp);
	if (Dot(arrRight, arrRight) <= MIN_AXIS_CROSS_SQUARED || !Normalize(arrRight))
	{
		return Fail(out_arrDiagnostics, "camera_matrix_axes", "Camera direction and up axes must be sufficiently nonparallel.");
	}
	arrUp = Cross(arrRight, arrForward);
	const Vector arrBackward{ -arrForward[0], -arrForward[1], -arrForward[2] };
	CameraMatrices stMatrices;
	stMatrices.arrView = {
		arrRight[0],
		arrUp[0],
		arrBackward[0],
		0.0,
		arrRight[1],
		arrUp[1],
		arrBackward[1],
		0.0,
		arrRight[2],
		arrUp[2],
		arrBackward[2],
		0.0,
		-Dot(arrRight, stSettings.arrPosition),
		-Dot(arrUp, stSettings.arrPosition),
		-Dot(arrBackward, stSettings.arrPosition),
		1.0,
	};
	const double dVerticalScale = 1.0 / std::tan(stSettings.dVerticalFovDegrees * (PI / 360.0));
	const double dHorizontalScale = dVerticalScale * static_cast<double>(nViewportHeight) / nViewportWidth;
	const double dDepthScale = stSettings.dNearPlane / (stSettings.dFarPlane - stSettings.dNearPlane);
	const double dDepthOffset = stSettings.dFarPlane * dDepthScale;
	const double dJitterX = 2.0 * (arrJitterPixels[0] / nViewportWidth);
	const double dJitterY = 2.0 * (arrJitterPixels[1] / nViewportHeight);
	stMatrices.arrProjection = {
		dHorizontalScale,
		0.0,
		0.0,
		0.0,
		0.0,
		dVerticalScale,
		0.0,
		0.0,
		-dJitterX,
		dJitterY,
		dDepthScale,
		-1.0,
		0.0,
		0.0,
		dDepthOffset,
		0.0,
	};
	stMatrices.arrViewProjection = Multiply(stMatrices.arrProjection, stMatrices.arrView);
	const Matrix arrInverseView{
		arrRight[0],
		arrRight[1],
		arrRight[2],
		0.0,
		arrUp[0],
		arrUp[1],
		arrUp[2],
		0.0,
		arrBackward[0],
		arrBackward[1],
		arrBackward[2],
		0.0,
		stSettings.arrPosition[0],
		stSettings.arrPosition[1],
		stSettings.arrPosition[2],
		1.0,
	};
	const Matrix arrInverseProjection{
		1.0 / dHorizontalScale,
		0.0,
		0.0,
		0.0,
		0.0,
		1.0 / dVerticalScale,
		0.0,
		0.0,
		0.0,
		0.0,
		0.0,
		1.0 / dDepthOffset,
		-dJitterX / dHorizontalScale,
		dJitterY / dVerticalScale,
		-1.0,
		1.0 / stSettings.dFarPlane,
	};
	stMatrices.arrInverseViewProjection = Multiply(arrInverseView, arrInverseProjection);
	if (!IsGpuRepresentable(stMatrices.arrView) || !IsGpuRepresentable(stMatrices.arrProjection) ||
		!IsGpuRepresentable(stMatrices.arrViewProjection) || !IsGpuRepresentable(stMatrices.arrInverseViewProjection))
	{
		return Fail(out_arrDiagnostics, "camera_matrix_range", "Camera matrices exceed finite binary32 GPU constant range.");
	}
	out_stMatrices = stMatrices;
	return true;
}

} // namespace EngineNext::Rendering
