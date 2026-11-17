/**************************************************************************/
/*  TestVolumeParse.cpp                                                   */
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

#include "engine_next/include/EngineNext/Rendering/VolumeSettings.h"
#include "engine_next/Tests/TestFramework.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <cstdint>
#include <initializer_list>
#include <limits>
#include <string>

namespace
{

using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::LocalVolumeShape;
using EngineNext::Rendering::ParseVolumeSettings;
using EngineNext::Rendering::VolumeSettings;
using EngineNext::Serialization::JsonValue;

bool ParseText(const std::string &strText, VolumeSettings &out_stSettings, Diagnostics &out_arrDiagnostics)
{
	JsonValue stValue;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(strText, stValue, strError));
	return ParseVolumeSettings(stValue, out_stSettings, out_arrDiagnostics);
}

VolumeSettings Sentinel()
{
	VolumeSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dDistance = 321;
	stSettings.dDensity = .7;
	stSettings.nLocalVolumeCount = 1;
	stSettings.arrLocalVolumes[0].nEntityId = 17;
	stSettings.arrLocalVolumes[0].arrCenter = { 2, 3, 4 };
	return stSettings;
}

void CheckSentinel(const VolumeSettings &stSettings)
{
	ENGINE_NEXT_CHECK(stSettings.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.dDistance, 321);
	ENGINE_NEXT_CHECK_EQ(stSettings.dDensity, .7);
	ENGINE_NEXT_CHECK_EQ(stSettings.nLocalVolumeCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].nEntityId.value_or(0), 17ULL);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].arrCenter[0], 2);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].arrCenter[1], 3);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].arrCenter[2], 4);
}

} // namespace

ENGINE_NEXT_TEST("Volume parser accepts empty optional objects and restores defaults")
{
	VolumeSettings stSettings = Sentinel();
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(ParseText("{}", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stSettings.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.dDistance, 100);
	ENGINE_NEXT_CHECK_EQ(stSettings.nCellPixels, 16U);
	ENGINE_NEXT_CHECK_EQ(stSettings.nDepthSlices, 64U);
	ENGINE_NEXT_CHECK_EQ(stSettings.nLocalVolumeCount, 0U);
	ENGINE_NEXT_CHECK(ParseText(R"({"local_volumes":[{}]})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.nLocalVolumeCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].eShape, LocalVolumeShape::Box);
	ENGINE_NEXT_CHECK(!stSettings.arrLocalVolumes[0].nEntityId.has_value());
}

ENGINE_NEXT_TEST("Volume parser handles every scalar vector and local field")
{
	VolumeSettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(ParseText(R"({
		"enabled":true,"distance":75,"cell_pixels":8,"depth_slices":96,
		"density":0.02,"height":-3,"height_falloff":0.4,"albedo":[0.1,0.2,1],
		"emission":[0,1,2],"phase_g":-0.6,"history_weight":0.7,
		"local_volumes":[{"shape":"sphere","center":[-2,3,-4],"extent":[2,2,2],
		"density":0.3,"albedo":[1,0.5,0],"emission":[2,1,0],"edge_fraction":0.25,"entity_id":9223372036854775807}]
	})",
								stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSettings.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stSettings.dDistance, 75);
	ENGINE_NEXT_CHECK_EQ(stSettings.nCellPixels, 8U);
	ENGINE_NEXT_CHECK_EQ(stSettings.nDepthSlices, 96U);
	ENGINE_NEXT_CHECK_EQ(stSettings.dDensity, .02);
	ENGINE_NEXT_CHECK_EQ(stSettings.dHeight, -3);
	ENGINE_NEXT_CHECK_EQ(stSettings.dHeightFalloff, .4);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrAlbedo[1], .2);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrEmission[2], 2);
	ENGINE_NEXT_CHECK_EQ(stSettings.dPhaseG, -.6);
	ENGINE_NEXT_CHECK_EQ(stSettings.dHistoryWeight, .7);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].eShape, LocalVolumeShape::Sphere);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].arrCenter[2], -4);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].arrExtent[0], 2);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].dDensity, .3);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].arrAlbedo[1], .5);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].arrEmission[0], 2);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].dEdgeFraction, .25);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].nEntityId.value_or(0), 9223372036854775807ULL);
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Volume parser rejects unknown and malformed values transactionally")
{
	for (const char *pText : { "null",
							   "[]",
							   "true",
							   R"({"unknown":1})",
							   R"({"enabled":1})",
							   R"({"density":"0.1"})",
							   R"({"cell_pixels":16.0})",
							   R"({"depth_slices":64.5})",
							   R"({"cell_pixels":-1})",
							   R"({"cell_pixels":4294967296})",
							   R"({"albedo":[1,1]})",
							   R"({"albedo":[1,1,1,1]})",
							   R"({"albedo":[1,"x",1]})",
							   R"({"emission":null})",
							   R"({"local_volumes":{}})",
							   R"({"local_volumes":[null]})",
							   R"({"local_volumes":[{"extra":false}]})",
							   R"({"local_volumes":[{"shape":"capsule"}]})",
							   R"({"local_volumes":[{"shape":1}]})",
							   R"({"local_volumes":[{"center":[0,1]}]})",
							   R"({"local_volumes":[{"extent":[1,false,1]}]})",
							   R"({"local_volumes":[{"entity_id":0}]})",
							   R"({"local_volumes":[{"entity_id":-1}]})",
							   R"({"local_volumes":[{"entity_id":1.0}]})",
							   R"({"local_volumes":[{"entity_id":"1"}]})" })
	{
		VolumeSettings stSettings = Sentinel();
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!ParseText(pText, stSettings, arrDiagnostics));
		CheckSentinel(stSettings);
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	}
}

ENGINE_NEXT_TEST("Volume parser applies range validation while disabled")
{
	for (const char *pText :
		 { R"({"enabled":false,"distance":0})", R"({"enabled":false,"density":-0.1})", R"({"enabled":false,"height_falloff":-1})",
		   R"({"enabled":false,"phase_g":1})", R"({"enabled":false,"history_weight":1})", R"({"enabled":false,"cell_pixels":12})",
		   R"({"enabled":false,"depth_slices":16})", R"({"enabled":false,"albedo":[1,1.01,1]})", R"({"enabled":false,"emission":[-1,0,0]})",
		   R"({"enabled":false,"local_volumes":[{"extent":[0,1,1]}]})", R"({"enabled":false,"local_volumes":[{"shape":"sphere","extent":[1,2,1]}]})",
		   R"({"enabled":false,"local_volumes":[{"edge_fraction":1.1}]})", R"({"enabled":false,"local_volumes":[{"albedo":[0,2,0]}]})" })
	{
		VolumeSettings stSettings = Sentinel();
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!ParseText(pText, stSettings, arrDiagnostics));
		CheckSentinel(stSettings);
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	}
}

ENGINE_NEXT_TEST("Volume parser bounds local arrays before writing fixed storage")
{
	JsonValue::List arrLocals(16, JsonValue::Object{});
	JsonValue stValue(JsonValue::Object{ { "local_volumes", arrLocals } });
	VolumeSettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(ParseVolumeSettings(stValue, stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.nLocalVolumeCount, 16U);
	arrLocals.emplace_back(JsonValue::Object{});
	stValue = JsonValue::Object{ { "local_volumes", arrLocals } };
	stSettings = Sentinel();
	ENGINE_NEXT_CHECK(!ParseVolumeSettings(stValue, stSettings, arrDiagnostics));
	CheckSentinel(stSettings);
}

ENGINE_NEXT_TEST("Volume parser rejects direct nonfinite JSON numbers")
{
	for (double dInvalid : { std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
	{
		VolumeSettings stSettings = Sentinel();
		Diagnostics arrDiagnostics;
		JsonValue stValue(JsonValue::Object{ { "density", dInvalid } });
		ENGINE_NEXT_CHECK(!ParseVolumeSettings(stValue, stSettings, arrDiagnostics));
		CheckSentinel(stSettings);
	}
}

ENGINE_NEXT_TEST("Volume parsing preserves strict duplicate key JSON behavior")
{
	JsonValue stValue;
	std::string strError;
	ENGINE_NEXT_CHECK(!EngineNext::Serialization::ParseJson(R"({"density":0,"density":1})", stValue, strError));
	ENGINE_NEXT_CHECK(!EngineNext::Serialization::ParseJson(R"({"local_volumes":[{"entity_id":1,"entity_id":2}]})", stValue, strError));
}

ENGINE_NEXT_TEST("Volume parser accepts inclusive grid and color limits")
{
	VolumeSettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(ParseText(R"({"enabled":true,"cell_pixels":32,"depth_slices":128,
		"density":0,"height_falloff":0,"albedo":[0,0.5,1],"emission":[0,1,65504],
		"phase_g":-0.95,"history_weight":0.99,"local_volumes":[]})",
								stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.arrAlbedo[2], 1);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrEmission[2], 65504);
	ENGINE_NEXT_CHECK_EQ(stSettings.nDepthSlices, 128U);
	ENGINE_NEXT_CHECK_EQ(stSettings.nCellPixels, 32U);
	ENGINE_NEXT_CHECK(ParseText(R"({"local_volumes":[{"entity_id":1,"density":0,"edge_fraction":0,"albedo":[0,1,0]}]})", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.arrLocalVolumes[0].nEntityId.value_or(0), 1ULL);
}
