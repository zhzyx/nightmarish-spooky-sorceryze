/**************************************************************************/
/*  TestGeometrySettings.cpp                                              */
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
#include "engine_next/include/EngineNext/Rendering/GeometrySettings.h"

#include <limits>
#include <string>

namespace
{
using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::GeometrySettings;
bool Parse(const char *pJson, GeometrySettings &out_stSettings, Diagnostics &out_arrDiagnostics)
{
	EngineNext::Serialization::JsonValue stJson;
	std::string strError;
	return EngineNext::Serialization::ParseJson(pJson, stJson, strError) &&
			EngineNext::Rendering::ParseGeometrySettings(stJson, out_stSettings, out_arrDiagnostics);
}
} //namespace
ENGINE_NEXT_TEST("Geometry defaults preserve conventional rendering")
{
	GeometrySettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(Parse("{}", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stSettings.bEnabled);
	ENGINE_NEXT_CHECK(stSettings.bOcclusion);
	ENGINE_NEXT_CHECK_EQ(stSettings.nMaxCommands, 262144U);
	ENGINE_NEXT_CHECK(Parse(R"({"enabled":true,"occlusion":false,"max_commands":1})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSettings.bEnabled && !stSettings.bOcclusion && stSettings.nMaxCommands == 1);
	ENGINE_NEXT_CHECK(Parse(R"({"max_commands":4294967295})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.nMaxCommands, std::numeric_limits<std::uint32_t>::max());
}
ENGINE_NEXT_TEST("Geometry invalid options preserve output")
{
	GeometrySettings stSettings;
	stSettings.bEnabled = true;
	stSettings.nMaxCommands = 17;
	Diagnostics arrDiagnostics;
	for (const char *pJson : { "null", "[]", R"({"unknown":true})", R"({"enabled":1})", R"({"occlusion":"true"})",
							   R"({"max_commands":0})", R"({"max_commands":-1})", R"({"max_commands":1.5})", R"({"max_commands":4294967296})" })
	{
		ENGINE_NEXT_CHECK(!Parse(pJson, stSettings, arrDiagnostics));
		ENGINE_NEXT_CHECK(stSettings.bEnabled && stSettings.nMaxCommands == 17);
	}
	stSettings.nMaxCommands = 0;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateGeometrySettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Geometry paging controls are bounded and preserve disabled validation")
{
	GeometrySettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(Parse(R"({"lod_enabled":false,"pixel_error":2.5,"lod_hysteresis":0.2,"page_gpu_bytes":65536,"page_staging_bytes":65536,"max_page_loads":1})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stSettings.bLodEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.dPixelError, 2.5);
	ENGINE_NEXT_CHECK_EQ(stSettings.nPageGpuBytes, 65536ULL);
	for (const char *pJson : { R"({"enabled":false,"pixel_error":0})", R"({"lod_hysteresis":1})", R"({"page_gpu_bytes":65535})", R"({"page_staging_bytes":268435457})", R"({"max_page_loads":0})", R"({"max_page_loads":257})" })
	{
		ENGINE_NEXT_CHECK(!Parse(pJson, stSettings, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stSettings.dPixelError, 2.5);
	}
}
