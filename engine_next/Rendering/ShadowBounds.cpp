/**************************************************************************/
/*  ShadowBounds.cpp                                                      */
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

#include "engine_next/Rendering/ShadowBounds.h"

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

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pCode, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, "$.shadow.bounds", pMessage);
	return false;
}

} // namespace

bool TransformShadowBounds(const MeshPrimitive &stPrimitive, const std::array<double, 16> &arrWorld,
						   WorldBounds &out_stBounds, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stPrimitive.arrVertices.empty())
	{
		return Fail(out_arrDiagnostics, "shadow_bounds_geometry", "Shadow bounds require at least one vertex.");
	}
	for (double dValue : arrWorld)
	{
		if (!std::isfinite(dValue))
		{
			return Fail(out_arrDiagnostics, "shadow_bounds_transform", "Shadow bounds require a finite world transform.");
		}
	}
	if (arrWorld[3] != 0.0 || arrWorld[7] != 0.0 || arrWorld[11] != 0.0 || arrWorld[15] != 1.0)
	{
		return Fail(out_arrDiagnostics, "shadow_bounds_transform", "Shadow bounds require an affine world transform.");
	}
	std::array<double, 3> arrMinimum{
		std::numeric_limits<double>::infinity(),
		std::numeric_limits<double>::infinity(),
		std::numeric_limits<double>::infinity(),
	};
	std::array<double, 3> arrMaximum{
		-std::numeric_limits<double>::infinity(),
		-std::numeric_limits<double>::infinity(),
		-std::numeric_limits<double>::infinity(),
	};
	for (const MeshVertex &stVertex : stPrimitive.arrVertices)
	{
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			const double dValue = stVertex.arrPosition[nAxis];
			if (!std::isfinite(dValue))
			{
				return Fail(out_arrDiagnostics, "shadow_bounds_geometry", "Shadow vertex positions must be finite.");
			}
			arrMinimum[nAxis] = (std::min)(arrMinimum[nAxis], dValue);
			arrMaximum[nAxis] = (std::max)(arrMaximum[nAxis], dValue);
		}
	}
	WorldBounds stBounds;
	stBounds.arrMinimum.fill(std::numeric_limits<double>::infinity());
	stBounds.arrMaximum.fill(-std::numeric_limits<double>::infinity());
	for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		for (std::size_t nRow = 0; nRow < 3; ++nRow)
		{
			double dLower = arrWorld[12 + nRow];
			double dUpper = dLower;
			for (std::size_t nColumn = 0; nColumn < 3; ++nColumn)
			{
				const double dCoordinate = (nCorner & (1U << nColumn)) != 0 ? arrMaximum[nColumn] : arrMinimum[nColumn];
				const double dCoefficient = arrWorld[nColumn * 4 + nRow];
				if (dCoordinate == 0.0 || dCoefficient == 0.0)
				{
					continue;
				}
				// One rounding per multiply-add, expanded outward after each term.
				dLower = std::nextafter(std::fma(dCoefficient, dCoordinate, dLower), -std::numeric_limits<double>::infinity());
				dUpper = std::nextafter(std::fma(dCoefficient, dCoordinate, dUpper), std::numeric_limits<double>::infinity());
			}
			if (!std::isfinite(dLower) || !std::isfinite(dUpper))
			{
				return Fail(out_arrDiagnostics, "shadow_bounds_range", "Transformed shadow bounds exceed the finite binary64 range.");
			}
			stBounds.arrMinimum[nRow] = (std::min)(stBounds.arrMinimum[nRow], dLower);
			stBounds.arrMaximum[nRow] = (std::max)(stBounds.arrMaximum[nRow], dUpper);
		}
	}
	out_stBounds = stBounds;
	return true;
}

} // namespace EngineNext::Rendering
