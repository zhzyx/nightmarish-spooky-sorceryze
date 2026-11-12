/**************************************************************************/
/*  Vector3.h                                                             */
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

#pragma once

#include <cmath>

namespace EngineNext::Gameplay
{

struct Vector3
{
	float fX = 0.0F;
	float fY = 0.0F;
	float fZ = 0.0F;

	[[nodiscard]] bool IsFinite() const
	{
		return std::isfinite(fX) && std::isfinite(fY) && std::isfinite(fZ);
	}

	[[nodiscard]] float LengthSquared() const
	{
		const float fX2 = fX * fX;
		const float fY2 = fY * fY;
		const float fZ2 = fZ * fZ;
		return fX2 + fY2 + fZ2;
	}
};

[[nodiscard]] inline Vector3 Add(const Vector3 &vLeft, const Vector3 &vRight)
{
	return Vector3{ vLeft.fX + vRight.fX, vLeft.fY + vRight.fY, vLeft.fZ + vRight.fZ };
}

[[nodiscard]] inline Vector3 Scale(const Vector3 &vValue, float fScalar)
{
	return Vector3{ vValue.fX * fScalar, vValue.fY * fScalar, vValue.fZ * fScalar };
}

[[nodiscard]] inline Vector3 Lerp(const Vector3 &vFrom, const Vector3 &vTo, float fWeight)
{
	return Vector3{
		vFrom.fX + (vTo.fX - vFrom.fX) * fWeight,
		vFrom.fY + (vTo.fY - vFrom.fY) * fWeight,
		vFrom.fZ + (vTo.fZ - vFrom.fZ) * fWeight,
	};
}

} // namespace EngineNext::Gameplay
