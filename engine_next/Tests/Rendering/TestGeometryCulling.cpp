/**************************************************************************/
/*  TestGeometryCulling.cpp                                               */
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
#include "engine_next/Tests/TestFramework.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>

namespace
{

struct Bool3
{
	bool x;
	bool y;
	bool z;
};
struct Bool4
{
	bool x;
	bool y;
	bool z;
	bool w;
};
struct Float3
{
	float x;
	float y;
	float z;
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
};
struct Float4
{
	float x;
	float y;
	float z;
	float w;
	Float3 xyz;
	Float4(float fX, float fY, float fZ, float fW) : x(fX), y(fY), z(fZ), w(fW), xyz{ fX, fY, fZ }
	{
	}
};
Bool3 operator<=(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x <= stRight.x, stLeft.y <= stRight.y, stLeft.z <= stRight.z };
}
bool all(Bool3 stValue)
{
	return stValue.x && stValue.y && stValue.z;
}
bool all(Bool4 stValue)
{
	return stValue.x && stValue.y && stValue.z && stValue.w;
}
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
Bool3 isfinite(Float3 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y), std::isfinite(stValue.z) };
}
Bool4 isfinite(Float4 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y), std::isfinite(stValue.z), std::isfinite(stValue.w) };
}
float dot(Float3 stLeft, Float3 stRight)
{
	return stLeft.x * stRight.x + stLeft.y * stRight.y + stLeft.z * stRight.z;
}
float min(float fA, float fB)
{
	return (std::min)(fA, fB);
}
std::uint32_t min(std::uint32_t nA, std::uint32_t nB)
{
	return (std::min)(nA, nB);
}
float max(float fA, float fB)
{
	return (std::max)(fA, fB);
}
std::uint32_t max(std::uint32_t nA, std::uint32_t nB)
{
	return (std::max)(nA, nB);
}
float floor(float fValue)
{
	return std::floor(fValue);
}
float ceil(float fValue)
{
	return std::ceil(fValue);
}
float saturate(float fValue)
{
	return std::clamp(fValue, 0.0f, 1.0f);
}
using uint = std::uint32_t;
using float3 = Float3;
using float4 = Float4;
#include "engine_next/Rendering/Shaders/GeometryVisibility.hlsli"

std::array<Float4, 8> BoxClips(float fLeft, float fRight, float fDepth = .5f, float fW = 1)
{
	return { { { fLeft, -.5f, fDepth, fW },
			   { fRight, -.5f, fDepth, fW },
			   { fLeft, .5f, fDepth, fW },
			   { fRight, .5f, fDepth, fW },
			   { fLeft, -.5f, fDepth, fW },
			   { fRight, -.5f, fDepth, fW },
			   { fLeft, .5f, fDepth, fW },
			   { fRight, .5f, fDepth, fW } } };
}

} // namespace

ENGINE_NEXT_TEST("Cluster frustum culling preserves boundary and near-plane intersections")
{
	ENGINE_NEXT_CHECK(ClusterBoundsValid({ -1, -1, -1 }, { 1, 1, 1 }));
	ENGINE_NEXT_CHECK(!ClusterBoundsValid({ 1, 0, 0 }, { 0, 1, 1 }));
	ENGINE_NEXT_CHECK(!ClusterBoundsValid({ std::numeric_limits<float>::quiet_NaN(), 0, 0 }, { 1, 1, 1 }));
	Float4 arrPlanes[6]{ { 1, 0, 0, 1 }, { -1, 0, 0, 1 }, { 0, 1, 0, 1 }, { 0, -1, 0, 1 }, { 0, 0, 1, 10 }, { 0, 0, -1, -.1f } };
	ENGINE_NEXT_CHECK(ClusterInFrustum({ -.5f, -.5f, -2 }, { .5f, .5f, -1 }, arrPlanes));
	ENGINE_NEXT_CHECK(!ClusterInFrustum({ 2, -.5f, -2 }, { 3, .5f, -1 }, arrPlanes));
	ENGINE_NEXT_CHECK(ClusterInFrustum({ 1, -.5f, -2 }, { 2, .5f, -1 }, arrPlanes));
	ENGINE_NEXT_CHECK(ClusterInFrustum({ -.5f, -.5f, -2 }, { .5f, .5f, 0 }, arrPlanes));
	ENGINE_NEXT_CHECK(!ClusterInFrustum({ -.5f, -.5f, 0 }, { .5f, .5f, 1 }, arrPlanes));
}

ENGINE_NEXT_TEST("Cluster projection keeps integer screen bounds and skips near crossings")
{
	std::array<Float4, 8> arrClips = BoxClips(-1, 1);
	ClusterScreenBounds stBounds{};
	ENGINE_NEXT_CHECK(ClusterProjectBounds(arrClips.data(), 64, 64, stBounds));
	ENGINE_NEXT_CHECK_EQ(stBounds.MinimumX, 0U);
	ENGINE_NEXT_CHECK_EQ(stBounds.MaximumX, 63U);
	ENGINE_NEXT_CHECK_EQ(stBounds.MinimumY, 16U);
	ENGINE_NEXT_CHECK_EQ(stBounds.MaximumY, 47U);
	arrClips[0] = Float4(-1, -.5f, 1.1f, 1);
	ENGINE_NEXT_CHECK(!ClusterProjectBounds(arrClips.data(), 64, 64, stBounds));
	arrClips = BoxClips(1, 1);
	ENGINE_NEXT_CHECK(ClusterProjectBounds(arrClips.data(), 641, 479, stBounds));
	ENGINE_NEXT_CHECK_EQ(stBounds.MinimumX, 640U);
	ENGINE_NEXT_CHECK_EQ(stBounds.MaximumX, 640U);
	arrClips[0] = Float4(0, 0, .5f, 0);
	ENGINE_NEXT_CHECK(!ClusterProjectBounds(arrClips.data(), 64, 64, stBounds));
}

ENGINE_NEXT_TEST("Cluster HiZ footprint spans all tiles and requires available mip coverage")
{
	ClusterScreenBounds stBounds{ 31, 0, 33, 3, .1f };
	ClusterHiZFootprint stFootprint{};
	ENGINE_NEXT_CHECK(ClusterChooseHiZ(stBounds, 7, stFootprint));
	ENGINE_NEXT_CHECK_EQ(stFootprint.Mip, 2U);
	ENGINE_NEXT_CHECK_EQ(stFootprint.MinimumX, 7U);
	ENGINE_NEXT_CHECK_EQ(stFootprint.MaximumX, 8U);
	ENGINE_NEXT_CHECK(!ClusterChooseHiZ(stBounds, 1, stFootprint));
	stBounds = { 0, 0, 16383, 16383, .1f };
	ENGINE_NEXT_CHECK(ClusterChooseHiZ(stBounds, 15, stFootprint));
	ENGINE_NEXT_CHECK_EQ(stFootprint.Mip, 14U);
	ENGINE_NEXT_CHECK_EQ(stFootprint.MaximumX, 0U);
}

ENGINE_NEXT_TEST("ReverseZ HiZ uses minimum depth and treats holes conservatively")
{
	ENGINE_NEXT_CHECK_EQ(ClusterReduceReverseDepth(.8f, .7f, .6f, .5f), .5f);
	ENGINE_NEXT_CHECK(ClusterDepthOccluded(.4f, .5f, .01f));
	ENGINE_NEXT_CHECK(!ClusterDepthOccluded(.5f, .5f, 0));
	ENGINE_NEXT_CHECK(!ClusterDepthOccluded(.6f, .5f, 0));
	ENGINE_NEXT_CHECK_EQ(ClusterReduceReverseDepth(.8f, 0, .8f, .8f), 0);
	ENGINE_NEXT_CHECK(!ClusterDepthOccluded(.1f, 0, 0));
	ENGINE_NEXT_CHECK_EQ(ClusterReduceReverseDepth(.8f, std::numeric_limits<float>::quiet_NaN(), .8f, .8f), 0);
	ENGINE_NEXT_CHECK(!ClusterDepthOccluded(std::numeric_limits<float>::infinity(), .5f, 0));
}

ENGINE_NEXT_TEST("Visibility output capacity does not admit the overflow slot")
{
	ENGINE_NEXT_CHECK(!ClusterOutputSlot(0, 0));
	ENGINE_NEXT_CHECK(ClusterOutputSlot(63, 64));
	ENGINE_NEXT_CHECK(!ClusterOutputSlot(64, 64));
	ENGINE_NEXT_CHECK(!ClusterOutputSlot(std::numeric_limits<std::uint32_t>::max(), 64));
}

ENGINE_NEXT_TEST("Existing mesh clusters adapt to outward-rounded world bounds")
{
	EngineNext::Rendering::MeshCluster stCluster;
	stCluster.arrVertexIndices = { 0, 1, 2 };
	stCluster.arrTriangleIndices = { 0, 1, 2 };
	stCluster.arrBoundsMinimum = { -1, -2, -3 };
	stCluster.arrBoundsMaximum = { 1, 2, 3 };
	std::array<double, 16> arrWorld{ -2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, .1, .2, .3, 1 };
	EngineNext::Rendering::GpuClusterInput stInput;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildClusterInput(stCluster, arrWorld, 9, -3, 7, stInput, arrDiagnostics));
	ENGINE_NEXT_CHECK(static_cast<double>(stInput.arrMinimum[0]) <= -1.9);
	ENGINE_NEXT_CHECK(static_cast<double>(stInput.arrMaximum[0]) >= 2.1);
	ENGINE_NEXT_CHECK_EQ(stInput.arrDraw[0], 3U);
	ENGINE_NEXT_CHECK_EQ(stInput.arrDraw[1], 9U);
	ENGINE_NEXT_CHECK_EQ(stInput.arrDraw[2], static_cast<std::uint32_t>(-3));
	ENGINE_NEXT_CHECK_EQ(stInput.arrDraw[3], 7U);
	arrWorld[15] = 0;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildClusterInput(stCluster, arrWorld, 1, 0, 0, stInput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stInput.arrDraw[1], 9U);
}

ENGINE_NEXT_TEST("Frustum arithmetic overflow keeps a cluster conservatively visible")
{
	const float fMaximum = std::numeric_limits<float>::max();
	ENGINE_NEXT_CHECK(!ClusterBoxOutsidePlane({ -fMaximum, -fMaximum, 0 }, { -fMaximum, -fMaximum, 1 }, { 1, 1, 0, 0 }));
	ENGINE_NEXT_CHECK(ClusterBoxOutsidePlane({ -2, -2, 0 }, { -2, -2, 1 }, { 1, 1, 0, 0 }));
}

ENGINE_NEXT_TEST("Frustum extraction preserves GPU FTZ conservative visibility and transactionality")
{
	std::array<float, 16> arrMatrix{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	std::array<std::array<float, 4>, 6> arrPlanes{};
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildCullingFrustum(arrMatrix, arrPlanes, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrPlanes[0], (std::array<float, 4>{ 1, 0, 0, 1 }));
	arrMatrix[12] = -1e38F;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildCullingFrustum(arrMatrix, arrPlanes, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrPlanes[0], (std::array<float, 4>{ 0, 0, 0, 1 }));
	ENGINE_NEXT_CHECK_EQ(arrPlanes[1], (std::array<float, 4>{ 0, 0, 0, 1 }));
	Float4 arrGpuPlanes[6]{ { 0, 0, 0, 0 }, { 0, 0, 0, 0 }, { 0, 0, 0, 0 }, { 0, 0, 0, 0 }, { 0, 0, 0, 0 }, { 0, 0, 0, 0 } };
	for (std::size_t nPlane = 0; nPlane < 6; ++nPlane)
	{
		const std::array<float, 4> &arrPlane = arrPlanes[nPlane];
		arrGpuPlanes[nPlane] = { arrPlane[0], arrPlane[1], arrPlane[2], arrPlane[3] };
	}
	ENGINE_NEXT_CHECK(ClusterInFrustum({ .5e38F, -.5F, .25F }, { 1.5e38F, .5F, .75F }, arrGpuPlanes));
	const std::array<std::array<float, 4>, 6> arrPrevious = arrPlanes;
	arrMatrix[0] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildCullingFrustum(arrMatrix, arrPlanes, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrPlanes, arrPrevious);
	arrMatrix = {};
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildCullingFrustum(arrMatrix, arrPlanes, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrPlanes, arrPrevious);
}
