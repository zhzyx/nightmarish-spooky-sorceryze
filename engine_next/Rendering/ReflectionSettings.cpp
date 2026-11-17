/**************************************************************************/
/*  ReflectionSettings.cpp                                                */
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

#include "engine_next/include/EngineNext/Rendering/ReflectionSettings.h"

#include <cmath>
#include <limits>

namespace EngineNext::Rendering
{
namespace
{

bool PositiveGpuValue(double dValue, double dMaximum) noexcept
{
	return std::isfinite(dValue) && dValue >= std::numeric_limits<float>::min() && dValue <= dMaximum;
}

} // namespace

bool ValidateReflectionSettings(const ReflectionSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!PositiveGpuValue(stSettings.dMaxDistance, 1000) || !PositiveGpuValue(stSettings.dThickness, 10) ||
		!PositiveGpuValue(stSettings.dMaxRoughness, 1) || !std::isfinite(stSettings.dNormalBias) ||
		stSettings.dNormalBias < 0 || stSettings.dNormalBias > 1 || stSettings.nMaxSteps < 8 || stSettings.nMaxSteps > 256)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "reflection_settings", "$.reflections", "Reflection ranges require positive normal binary32 distance, thickness and roughness, finite bias in [0,1], and steps in [8,256].");
		return false;
	}
	return true;
}

} // namespace EngineNext::Rendering
