/**************************************************************************/
/*  TestReflectionTrace.cpp                                               */
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

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>
#include <vector>

namespace
{

struct Float2
{
	float x;
	float y;
	Float2() : Float2(0, 0)
	{
	}
	Float2(float fX, float fY) : x(fX), y(fY)
	{
	}
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
	Float4(float fX, float fY, float fZ, float fW) : x(fX), y(fY), z(fZ), w(fW)
	{
	}
};
struct Int2
{
	int x;
	int y;
	Int2() : Int2(0, 0)
	{
	}
	Int2(float fX, float fY) : x(static_cast<int>(fX)), y(static_cast<int>(fY))
	{
	}
};
struct Int3
{
	int x;
	int y;
	int z;
	Int3(int nX, int nY, int nZ) : x(nX), y(nY), z(nZ)
	{
	}
};

Float2 operator+(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y };
}
Float2 operator-(Float2 stLeft, Float2 stRight)
{
	return { stLeft.x - stRight.x, stLeft.y - stRight.y };
}
Float2 operator*(Float2 stLeft, float fScale)
{
	return { stLeft.x * fScale, stLeft.y * fScale };
}
Float3 operator+(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y, stLeft.z + stRight.z };
}
Float3 operator*(Float3 stLeft, float fScale)
{
	return { stLeft.x * fScale, stLeft.y * fScale, stLeft.z * fScale };
}
Float3 operator/(Float3 stLeft, float fScale)
{
	return { stLeft.x / fScale, stLeft.y / fScale, stLeft.z / fScale };
}

using uint = std::uint32_t;
using float2 = Float2;
using float3 = Float3;
using float4 = Float4;
using int2 = Int2;
using int3 = Int3;

float min(float fA, float fB)
{
	return (std::min)(fA, fB);
}
float max(float fA, float fB)
{
	return (std::max)(fA, fB);
}
float abs(float fA)
{
	return std::abs(fA);
}
float sqrt(float fA)
{
	return std::sqrt(fA);
}
float floor(float fA)
{
	return std::floor(fA);
}
float ceil(float fA)
{
	return std::ceil(fA);
}
float lerp(float fA, float fB, float fT)
{
	return fA + (fB - fA) * fT;
}
float clamp(float fA, float fMin, float fMax)
{
	return std::clamp(fA, fMin, fMax);
}
float saturate(float fA)
{
	return clamp(fA, 0, 1);
}
bool isfinite(float fA)
{
	return std::isfinite(fA);
}

template <typename T>
struct Texture2D
{
	std::uint32_t nWidth;
	std::uint32_t nHeight;
	std::vector<T> arrValues;
	void GetDimensions(std::uint32_t &out_nWidth,
					   std::uint32_t &out_nHeight) const
	{
		out_nWidth = nWidth;
		out_nHeight = nHeight;
	}
	T Load(Int3 stPixel) const
	{
		ENGINE_NEXT_CHECK(stPixel.x >= 0 && stPixel.y >= 0 &&
						  stPixel.x < static_cast<int>(nWidth) &&
						  stPixel.y < static_cast<int>(nHeight) &&
						  stPixel.z == 0);
		if (stPixel.x < 0 || stPixel.y < 0 ||
			stPixel.x >= static_cast<int>(nWidth) ||
			stPixel.y >= static_cast<int>(nHeight))
		{
			return T{};
		}
		return arrValues[static_cast<std::size_t>(stPixel.y) * nWidth +
						 stPixel.x];
	}
};

#include "engine_next/Rendering/Shaders/ReflectionTrace.hlsli"

SsrTraceParameters Parameters()
{
	return { { 64, 64 }, { 1, 1, 0, 0 }, { .1f, 100 }, 20, .1f, .01f, 4, 256 };
}
Texture2D<float> Surface(float fDepth = 0)
{
	return { 64, 64, std::vector<float>(64 * 64, fDepth) };
}
float Device(float fDepth, Float2 stPlanes = { .1f, 100 })
{
	return stPlanes.x * (stPlanes.y - fDepth) /
			(fDepth * (stPlanes.y - stPlanes.x));
}
void Near(float fActual, float fExpected, float fTolerance = .0001f)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(fActual - fExpected) <=
					  fTolerance * (1 + std::abs(fExpected)));
}

} // namespace

ENGINE_NEXT_TEST(
		"SSR reverse-Z conversion retains near far and positive interior")
{
	const Float2 stPlanes{ .1f, 100 };
	Near(SsrViewDepth(1, stPlanes), .1f);
	Near(SsrViewDepth(0, stPlanes), 100);
	for (float fDepth : { .1f, 1.0f, 4.0f, 40.0f, 100.0f })
	{
		Near(SsrViewDepth(Device(fDepth), stPlanes), fDepth);
	}
}

ENGINE_NEXT_TEST("SSR perspective DDA resolves an analytic plane intersection")
{
	Texture2D<float> stTexture = Surface(Device(4));
	SsrTraceResult stResult =
			TraceScreenRay(stTexture, { -1, 0, -2 }, { 1, 0, -1 }, Parameters());
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	Near(stResult.RayDistance, 2 * std::sqrt(2.0f));
	Near(stResult.ViewDepth, 4);
	Near(stResult.ProjectedUv.x, .625f);
	Near(stResult.ProjectedUv.y, .5f);
	ENGINE_NEXT_CHECK(stResult.Confidence > .99f);
	ENGINE_NEXT_CHECK(stResult.Steps <= 256);
}

ENGINE_NEXT_TEST("SSR clips rays entering near side and leaving far planes")
{
	SsrTraceParameters stParameters = Parameters();
	Texture2D<float> stTexture = Surface(Device(2));
	SsrTraceResult stResult =
			TraceScreenRay(stTexture, { -1, 0, 1 }, { 0, 0, -1 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	Near(stResult.RayDistance, 3);
	Near(stResult.ProjectedUv.x, .25f);
	stParameters.NearFar = { .1f, 3 };
	stTexture = Surface(0);
	stResult = TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, -1 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_MISS);
	ENGINE_NEXT_CHECK(stResult.Steps < 16);
	stResult = TraceScreenRay(stTexture, { 0, 0, 1 }, { 0, 0, 1 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_CLIPPED);
}

ENGINE_NEXT_TEST(
		"SSR excludes its source pixel and accepts a neighboring depth slab")
{
	Texture2D<float> stTexture = Surface(0);
	stTexture.arrValues[32 * 64 + 32] = Device(2);
	SsrTraceParameters stParameters = Parameters();
	stParameters.Thickness = .1f;
	SsrTraceResult stResult =
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_MISS);
	stTexture.arrValues[32 * 64 + 35] = Device(2);
	stResult = TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	ENGINE_NEXT_CHECK(stResult.Uv.x >= 35.0f / 64);
	ENGINE_NEXT_CHECK(stResult.RayDistance >= stParameters.MinDistance);
}

ENGINE_NEXT_TEST("SSR rejects sky and invalid depth samples with bounded loads")
{
	SsrTraceParameters stParameters = Parameters();
	for (float fDepth :
		 { 0.0f, -.1f, 1.1f, std::numeric_limits<float>::infinity(),
		   std::numeric_limits<float>::quiet_NaN() })
	{
		Texture2D<float> stTexture = Surface(fDepth);
		SsrTraceResult stResult =
				TraceScreenRay(stTexture, { -1, 0, -2 }, { 1, 0, -1 }, stParameters);
		ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_MISS);
		ENGINE_NEXT_CHECK(stResult.Steps <= 256);
	}
}

ENGINE_NEXT_TEST(
		"SSR honors traversal budget and viewport exit without a false hit")
{
	Texture2D<float> stTexture = Surface(0);
	SsrTraceParameters stParameters = Parameters();
	stParameters.MaxSteps = 3;
	SsrTraceResult stResult =
			TraceScreenRay(stTexture, { -1, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_BUDGET);
	ENGINE_NEXT_CHECK_EQ(stResult.Steps, 3U);
	stParameters.MaxSteps = 256;
	stResult = TraceScreenRay(stTexture, { -1, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_MISS);
	ENGINE_NEXT_CHECK(stResult.Steps <= 64);
}

ENGINE_NEXT_TEST("SSR fades edge hits and handles projection jitter")
{
	Texture2D<float> stTexture = Surface(0);
	stTexture.arrValues[32 * 64 + 63] = Device(2);
	SsrTraceResult stResult =
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, 0 }, Parameters());
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	ENGINE_NEXT_CHECK(stResult.Confidence > 0 && stResult.Confidence < .3f);
	Texture2D<float> stPlane = Surface(Device(4));
	SsrTraceParameters stParameters = Parameters();
	stParameters.Projection.z = .03125f;
	stParameters.Projection.w = -.03125f;
	stResult = TraceScreenRay(stPlane, { -1, 0, -2 }, { 1, 0, -1 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	Near(stResult.ProjectedUv.x, .625f + 1.0f / 64);
	Near(stResult.ProjectedUv.y, .5f + 1.0f / 64);
}

ENGINE_NEXT_TEST(
		"SSR accepts reverse screen direction and diagonal cell crossings")
{
	Texture2D<float> stTexture = Surface(Device(4));
	SsrTraceResult stResult =
			TraceScreenRay(stTexture, { 1, 0, -2 }, { -1, 0, -1 }, Parameters());
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	Near(stResult.ProjectedUv.x, .375f);
	stResult =
			TraceScreenRay(stTexture, { -1, -1, -2 }, { 1, 1, -1 }, Parameters());
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	Near(stResult.RayDistance, 2 * std::sqrt(3.0f));
	Near(stResult.ProjectedUv.x, .625f);
	Near(stResult.ProjectedUv.y, .375f);
}

ENGINE_NEXT_TEST("SSR rejects unsupported parameters before texture access")
{
	Texture2D<float> stTexture = Surface(0);
	SsrTraceParameters stParameters = Parameters();
	stParameters.MaxSteps = 257;
	ENGINE_NEXT_CHECK_EQ(
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, -1 }, stParameters).Reason,
			SSR_INVALID);
	stParameters = Parameters();
	stParameters.Thickness = -1;
	ENGINE_NEXT_CHECK_EQ(
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, -1 }, stParameters).Reason,
			SSR_INVALID);
	stParameters = Parameters();
	stParameters.NearFar = { 1, 1 };
	ENGINE_NEXT_CHECK_EQ(
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, -1 }, stParameters).Reason,
			SSR_INVALID);
	stParameters = Parameters();
	stParameters.Viewport = { 65, 64 };
	ENGINE_NEXT_CHECK_EQ(
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, -1 }, stParameters).Reason,
			SSR_INVALID);
	stParameters = Parameters();
	ENGINE_NEXT_CHECK_EQ(
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 0, 0, 0 }, stParameters).Reason,
			SSR_INVALID);
	ENGINE_NEXT_CHECK_EQ(
			TraceScreenRay(stTexture, { 0, 0, -2 },
						   { std::numeric_limits<float>::quiet_NaN(), 0, 0 },
						   stParameters)
					.Reason,
			SSR_INVALID);
}

ENGINE_NEXT_TEST(
		"SSR matches analytic intersections across perspective ray slopes")
{
	Texture2D<float> stTexture = Surface(Device(4));
	for (float fOriginX : { -.75f, 0.0f, .75f })
	{
		for (float fOriginY : { -.75f, 0.0f, .75f })
		{
			for (float fDirectionX : { -.5f, .5f })
			{
				for (float fDirectionY : { -.5f, .5f })
				{
					const Float3 stDirection{ fDirectionX, fDirectionY, -1 };
					const SsrTraceResult stResult =
							TraceScreenRay(stTexture, { fOriginX, fOriginY, -2 },
										   stDirection, Parameters());
					ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
					const float fDistance =
							2 * std::sqrt(fDirectionX * fDirectionX + fDirectionY * fDirectionY + 1);
					Near(stResult.RayDistance, fDistance);
					Near(stResult.ProjectedUv.x,
						 (fOriginX + 2 * fDirectionX) / 8 + .5f);
					Near(stResult.ProjectedUv.y,
						 .5f - (fOriginY + 2 * fDirectionY) / 8);
				}
			}
		}
	}
}

ENGINE_NEXT_TEST(
		"SSR depth slab rejects separated surfaces and accepts bounded overlap")
{
	Texture2D<float> stTexture = Surface(Device(1));
	SsrTraceParameters stParameters = Parameters();
	SsrTraceResult stResult =
			TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_MISS);
	stTexture = Surface(Device(1.95f));
	stResult = TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	Near(stResult.Confidence, 1);
	stParameters.Thickness = 0;
	stResult = TraceScreenRay(stTexture, { 0, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_MISS);
}

ENGINE_NEXT_TEST(
		"SSR planar depth cell offsets preserve accepted hit confidence")
{
	Texture2D<float> stTexture = Surface();
	for (std::uint32_t nY = 0; nY < stTexture.nHeight; ++nY)
	{
		for (std::uint32_t nX = 0; nX < stTexture.nWidth; ++nX)
		{
			const float fNdcX = (static_cast<float>(nX) + .5f) / 32 - 1;
			// The same plane satisfies depth = 2 + 0.2 * viewX.
			const float fDepth = 2 / (1 - .2f * fNdcX);
			stTexture.arrValues[nY * stTexture.nWidth + nX] = Device(fDepth);
		}
	}
	const SsrTraceParameters stParameters = Parameters();
	for (int nSourceX = 24; nSourceX <= 30; ++nSourceX)
	{
		const float fOriginX = ((static_cast<float>(nSourceX) + .5f) / 32 - 1) * 2;
		const SsrTraceResult stResult = TraceScreenRay(
				stTexture, { fOriginX, 0, -2 }, { 1, 0, 0 }, stParameters);
		ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
		ENGINE_NEXT_CHECK_EQ(stResult.Pixel.x, nSourceX + 1);
		const float fSurfaceDepth = SsrViewDepth(
				stTexture.arrValues[32 * 64 + stResult.Pixel.x], stParameters.NearFar);
		const float fDepthOffset = stResult.ViewDepth - fSurfaceDepth;
		ENGINE_NEXT_CHECK(fDepthOffset > 0);
		ENGINE_NEXT_CHECK(fDepthOffset < stParameters.Thickness);
		Near(stResult.Confidence, 1);
	}
}

ENGINE_NEXT_TEST("SSR clip and projection retain shifted screen edges")
{
	SsrTraceParameters stParameters = Parameters();
	stParameters.Projection = { 1.5f, 2.0f, -.25f, .125f };
	const Float2 stPixel = SsrProjectPixel({ 1, -.5f, -4 }, stParameters);
	Near(stPixel.x, 36);
	Near(stPixel.y, 36);
	stParameters.NearFar = { 1e-20f, 100 };
	ENGINE_NEXT_CHECK_EQ(
			TraceScreenRay(Surface(), { 0, 0, -2 }, { 1, 0, 0 }, stParameters).Reason,
			SSR_INVALID);
}

ENGINE_NEXT_TEST(
		"SSR negative traversal returns the tested cell for boundary hits")
{
	Texture2D<float> stTexture = Surface(0);
	stTexture.arrValues[32 * 64 + 28] = Device(2);
	const SsrTraceResult stResult =
			TraceScreenRay(stTexture, { 0, 0, -2 }, { -1, 0, 0 }, Parameters());
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	ENGINE_NEXT_CHECK_EQ(stResult.Pixel.x, 28);
	ENGINE_NEXT_CHECK_EQ(static_cast<int>(std::floor(stResult.Uv.x * 64)), 28);
}

ENGINE_NEXT_TEST(
		"SSR enters 4K and 8K negative viewport boundaries without epsilon loss")
{
	for (std::uint32_t nWidth : { 4096U, 8192U })
	{
		Texture2D<float> stTexture{ nWidth, 4,
									std::vector<float>(nWidth * 4, 0) };
		stTexture.arrValues[2 * nWidth + nWidth - 1] = Device(2);
		SsrTraceParameters stParameters = Parameters();
		stParameters.Viewport = { static_cast<float>(nWidth), 4 };
		const SsrTraceResult stResult =
				TraceScreenRay(stTexture, { 3, 0, -2 }, { -1, 0, 0 }, stParameters);
		ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
		ENGINE_NEXT_CHECK_EQ(stResult.Pixel.x, static_cast<int>(nWidth) - 1);
		ENGINE_NEXT_CHECK_EQ(
				static_cast<int>(std::floor(stResult.Uv.x * nWidth)),
				static_cast<int>(nWidth) - 1);
	}
}

ENGINE_NEXT_TEST(
		"SSR preserves the initial cell immediately before a positive boundary")
{
	Texture2D<float> stTexture = Surface(0);
	stTexture.arrValues[32 * 64 + 10] = Device(2);
	SsrTraceParameters stParameters = Parameters();
	stParameters.MinDistance = 2;
	const float fStartX = (10.99995f / 32 - 1) * 2;
	// At t=2 the clipped start projects to 10.99995. Its actual origin was
	// outside the viewport, so the first cell is an eligible surface candidate.
	const SsrTraceResult stResult = TraceScreenRay(
			stTexture, { fStartX - 2, 0, -2 }, { 1, 0, 0 }, stParameters);
	ENGINE_NEXT_CHECK_EQ(stResult.Reason, SSR_HIT);
	ENGINE_NEXT_CHECK_EQ(stResult.Pixel.x, 10);
}
