/**************************************************************************/
/*  TestReflectionSettings.cpp                                            */
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
#include "engine_next/include/EngineNext/Rendering/ReflectionSettings.h"

#include <initializer_list>
#include <limits>

ENGINE_NEXT_TEST("Reflection settings default to a disabled bounded trace")
{
	EngineNext::Rendering::ReflectionSettings stSettings;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!stSettings.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.dMaxDistance, 100);
	ENGINE_NEXT_CHECK_EQ(stSettings.dThickness, .1);
	ENGINE_NEXT_CHECK_EQ(stSettings.dNormalBias, .02);
	ENGINE_NEXT_CHECK_EQ(stSettings.nMaxSteps, 128U);
	ENGINE_NEXT_CHECK_EQ(stSettings.dMaxRoughness, .8);
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateReflectionSettings(stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Reflection settings accept inclusive bounds and normal GPU minimum")
{
	EngineNext::Rendering::ReflectionSettings stSettings;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	stSettings.bEnabled = true;
	stSettings.dMaxDistance = 1000;
	stSettings.dThickness = 10;
	stSettings.dNormalBias = 1;
	stSettings.dMaxRoughness = 1;
	stSettings.nMaxSteps = 256;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateReflectionSettings(stSettings, arrDiagnostics));
	stSettings.dMaxDistance = std::numeric_limits<float>::min();
	stSettings.dThickness = std::numeric_limits<float>::min();
	stSettings.dNormalBias = 0;
	stSettings.dMaxRoughness = std::numeric_limits<float>::min();
	stSettings.nMaxSteps = 8;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateReflectionSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Reflection settings reject invalid values even when disabled")
{
	using EngineNext::Rendering::ReflectionSettings;
	double ReflectionSettings::*arrPositiveFields[] = { &ReflectionSettings::dMaxDistance, &ReflectionSettings::dThickness, &ReflectionSettings::dMaxRoughness };
	for (double ReflectionSettings::*pField : arrPositiveFields)
	{
		for (double dValue : { -1.0, 0.0, std::numeric_limits<double>::min(), std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN(), 1001.0 })
		{
			ReflectionSettings stSettings;
			stSettings.*pField = dValue;
			EngineNext::Assets::Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateReflectionSettings(stSettings, arrDiagnostics));
			ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
		}
	}
	for (double dBias : { -.001, 1.001, std::numeric_limits<double>::quiet_NaN() })
	{
		ReflectionSettings stSettings;
		stSettings.dNormalBias = dBias;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateReflectionSettings(stSettings, arrDiagnostics));
	}
	for (std::uint32_t nSteps : { 0U, 7U, 257U })
	{
		ReflectionSettings stSettings;
		stSettings.nMaxSteps = nSteps;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateReflectionSettings(stSettings, arrDiagnostics));
	}
}
