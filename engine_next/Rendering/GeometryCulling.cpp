/**************************************************************************/
/*  GeometryCulling.cpp                                                   */
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

#include "engine_next/include/EngineNext/Rendering/GeometryCulling.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{

bool BuildCullingFrustum(const std::array<float, 16> &arrViewProjection,
						 std::array<std::array<float, 4>, 6> &out_arrPlanes, Assets::Diagnostics &out_arrDiagnostics)
{
	for (float fValue : arrViewProjection)
	{
		if (!std::isfinite(fValue))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "culling_frustum", "$", "View-projection matrix must be finite.");
			return false;
		}
	}
	const std::array<std::pair<std::uint32_t, int>, 6> arrRows{ { { 0, 1 }, { 0, -1 }, { 1, 1 }, { 1, -1 }, { 2, 0 }, { 2, -1 } } };
	std::array<std::array<float, 4>, 6> arrCandidate{};
	for (std::size_t nPlane = 0; nPlane < arrRows.size(); ++nPlane)
	{
		std::array<double, 4> arrPlane{};
		double dScale = 0;
		for (std::uint32_t nAxis = 0; nAxis < 4; ++nAxis)
		{
			const double dRow = arrViewProjection[nAxis * 4 + arrRows[nPlane].first];
			arrPlane[nAxis] = arrRows[nPlane].second == 0 ? dRow : arrViewProjection[nAxis * 4 + 3] + arrRows[nPlane].second * dRow;
			dScale = std::max(dScale, std::abs(arrPlane[nAxis]));
		}
		if (dScale == 0)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "culling_frustum", "$", "Frustum plane is degenerate.");
			return false;
		}
		bool bGpuRepresentable = true;
		for (std::uint32_t nAxis = 0; nAxis < 4; ++nAxis)
		{
			const double dValue = arrPlane[nAxis] / dScale;
			const float fValue = static_cast<float>(dValue);
			arrCandidate[nPlane][nAxis] = fValue;
			bGpuRepresentable = bGpuRepresentable && (dValue == 0 || std::abs(fValue) >= std::numeric_limits<float>::min());
		}
		if (!bGpuRepresentable)
		{
			arrCandidate[nPlane] = { 0, 0, 0, 1 };
		}
	}
	out_arrPlanes = arrCandidate;
	return true;
}

bool BuildClusterInput(const MeshCluster &stCluster, const std::array<double, 16> &arrWorld, std::uint32_t nStartIndex, std::int32_t nBaseVertex,
					   std::uint32_t nInstance, GpuClusterInput &out_stInput, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stCluster.arrVertexIndices.empty() || stCluster.arrVertexIndices.size() > MAX_MESH_CLUSTER_VERTICES || stCluster.arrTriangleIndices.empty() ||
		stCluster.arrTriangleIndices.size() > MAX_MESH_CLUSTER_TRIANGLES * 3 || stCluster.arrTriangleIndices.size() % 3 != 0 || arrWorld[3] != 0 ||
		arrWorld[7] != 0 || arrWorld[11] != 0 || arrWorld[15] != 1)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "cluster_input", "$", "Cluster topology and affine transform are invalid.");
		return false;
	}
	for (std::uint8_t nIndex : stCluster.arrTriangleIndices)
	{
		if (nIndex >= stCluster.arrVertexIndices.size())
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "cluster_input", "$", "Cluster-local index is out of range.");
			return false;
		}
	}
	for (double dValue : arrWorld)
	{
		if (!std::isfinite(dValue))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "cluster_input", "$", "World transform must be finite.");
			return false;
		}
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!std::isfinite(stCluster.arrBoundsMinimum[nAxis]) || !std::isfinite(stCluster.arrBoundsMaximum[nAxis]) ||
			stCluster.arrBoundsMinimum[nAxis] > stCluster.arrBoundsMaximum[nAxis])
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "cluster_input", "$", "Cluster bounds must be ordered and finite.");
			return false;
		}
	}
	std::array<double, 3> arrMinimum{ std::numeric_limits<double>::max(), std::numeric_limits<double>::max(), std::numeric_limits<double>::max() };
	std::array<double, 3> arrMaximum{ -std::numeric_limits<double>::max(), -std::numeric_limits<double>::max(), -std::numeric_limits<double>::max() };
	for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		const double dX = (nCorner & 1) != 0 ? stCluster.arrBoundsMaximum[0] : stCluster.arrBoundsMinimum[0];
		const double dY = (nCorner & 2) != 0 ? stCluster.arrBoundsMaximum[1] : stCluster.arrBoundsMinimum[1];
		const double dZ = (nCorner & 4) != 0 ? stCluster.arrBoundsMaximum[2] : stCluster.arrBoundsMinimum[2];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			const double dValue = arrWorld[nAxis] * dX + arrWorld[4 + nAxis] * dY + arrWorld[8 + nAxis] * dZ + arrWorld[12 + nAxis];
			if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "cluster_input", "$", "Transformed cluster bounds exceed binary32.");
				return false;
			}
			arrMinimum[nAxis] = (std::min)(arrMinimum[nAxis], dValue);
			arrMaximum[nAxis] = (std::max)(arrMaximum[nAxis], dValue);
		}
	}
	GpuClusterInput stCandidate;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		float fMinimum = static_cast<float>(arrMinimum[nAxis]);
		float fMaximum = static_cast<float>(arrMaximum[nAxis]);
		if (static_cast<double>(fMinimum) > arrMinimum[nAxis])
		{
			fMinimum = std::nextafter(fMinimum, -std::numeric_limits<float>::infinity());
		}
		if (static_cast<double>(fMaximum) < arrMaximum[nAxis])
		{
			fMaximum = std::nextafter(fMaximum, std::numeric_limits<float>::infinity());
		}
		stCandidate.arrMinimum[nAxis] = fMinimum;
		stCandidate.arrMaximum[nAxis] = fMaximum;
	}
	stCandidate.arrDraw = { static_cast<std::uint32_t>(stCluster.arrTriangleIndices.size()), nStartIndex, static_cast<std::uint32_t>(nBaseVertex), nInstance };
	out_stInput = stCandidate;
	return true;
}

} // namespace EngineNext::Rendering
