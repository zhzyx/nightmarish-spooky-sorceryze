/**************************************************************************/
/*  TestRenderConfiguration.cpp                                           */
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
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <limits>
#include <string>
#include <system_error>

namespace
{

using JsonValue = EngineNext::Serialization::JsonValue;

const std::string strSourceDigest(64, 'a');

JsonValue ValidConfiguration()
{
	return JsonValue::Object{ { "schema_version", std::int64_t{ 1 } },
							  { "source_package_sha256", strSourceDigest },
							  { "camera", JsonValue::Object{ { "position", JsonValue::List{ 0.0, 0.0, 5.0 } }, { "target", JsonValue::List{ 0.0, 0.0, 0.0 } }, { "up", JsonValue::List{ 0.0, 1.0, 0.0 } }, { "vertical_fov_degrees", 50.0 }, { "near_plane", 0.05 }, { "far_plane", 1000.0 } } },
							  { "exposure", 1.0 } };
}

JsonValue &CameraField(JsonValue &stValue, const std::string &strField)
{
	return (*(*stValue.GetObject())["camera"].GetObject())[strField];
}

void CheckRejected(const JsonValue &stValue, const std::string &strExpectedDigest = strSourceDigest)
{
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	stConfiguration.dExposure = 321;
	stConfiguration.stCamera.arrPosition = { 6, 7, 8 };
	stConfiguration.strSourcePackageDigest = "unchanged";
	stConfiguration.stDirectionalLight.dIlluminance = 432;
	stConfiguration.stShadows.nResolution = 4096;
	stConfiguration.arrPointLights.front().nId = 4321;
	stConfiguration.arrSpotLights.push_back(EngineNext::Rendering::SpotLightSettings{});
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ParseRenderConfiguration(stValue, strExpectedDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK_EQ(stConfiguration.dExposure, 321.0);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stCamera.arrPosition, (std::array<double, 3>{ 6, 7, 8 }));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.strSourcePackageDigest, "unchanged");
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stDirectionalLight.dIlluminance, 432.0);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.nResolution, 4096U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrPointLights.front().nId, 4321U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrSpotLights.size(), 1U);
}

struct TemporaryConfiguration
{
	std::filesystem::path stPath;

	TemporaryConfiguration()
	{
		static std::uint64_t nIndex = 0;
		const std::int64_t nTime = std::chrono::steady_clock::now().time_since_epoch().count();
		stPath = std::filesystem::temp_directory_path() / ("engine-next-render-configuration-" + std::to_string(nTime) + "-" + std::to_string(++nIndex) + ".json");
	}

	~TemporaryConfiguration()
	{
		std::error_code stError;
		std::filesystem::remove(stPath, stError);
	}

	bool Write(const std::string &strText) const
	{
		std::ofstream stFile(stPath, std::ios::binary | std::ios::trunc);
		stFile.write(strText.data(), static_cast<std::streamsize>(strText.size()));
		stFile.close();
		return stFile.good();
	}
};

JsonValue DirectionalLight()
{
	return JsonValue::Object{
		{ "direction", JsonValue::List{ 0.5, -0.8, -0.6 } },
		{ "color", JsonValue::List{ 1.0, 0.9666667, 0.9 } },
		{ "illuminance", 3.0 }
	};
}

JsonValue Shadows()
{
	return JsonValue::Object{
		{ "enabled", true }, { "resolution", std::int64_t{ 2048 } }, { "distance", 50.0 }, { "split_lambda", 0.6 }, { "depth_bias", 0.0005 }, { "normal_bias", 0.01 }
	};
}

JsonValue PointLight(std::int64_t nId = 1)
{
	return JsonValue::Object{
		{ "id", nId }, { "position", JsonValue::List{ 2.0, 3.0, 2.0 } }, { "color", JsonValue::List{ 1.0, 0.6666667, 0.4444444 } }, { "lumens", 226.194671 }, { "range", 25.0 }, { "casts_shadow", true }
	};
}

JsonValue SpotLight(std::int64_t nId = 2)
{
	JsonValue stValue = PointLight(nId);
	(*stValue.GetObject())["direction"] = JsonValue::List{ 0.0, -1.0, 0.0 };
	(*stValue.GetObject())["inner_angle_degrees"] = 20.0;
	(*stValue.GetObject())["outer_angle_degrees"] = 35.0;
	return stValue;
}

} // namespace

ENGINE_NEXT_TEST("Render configuration accepts camera and manual exposure with source binding")
{
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(ValidConfiguration(), strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
	ENGINE_NEXT_CHECK_EQ(stConfiguration.strSourcePackageDigest, strSourceDigest);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stCamera.arrPosition, (std::array<double, 3>{ 0, 0, 5 }));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stCamera.dVerticalFovDegrees, 50.0);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stCamera.dNearPlane, 0.05);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stCamera.dFarPlane, 1000.0);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.dExposure, 1.0);
}

ENGINE_NEXT_TEST("Render configuration rejects unexpected fields missing fields and wrong scalar types")
{
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["unused"] = true;
	CheckRejected(stValue);
	stValue = ValidConfiguration();
	stValue.GetObject()->erase("exposure");
	CheckRejected(stValue);
	stValue = ValidConfiguration();
	(*(*stValue.GetObject())["camera"].GetObject())["projection"] = "perspective";
	CheckRejected(stValue);
	stValue = ValidConfiguration();
	(*stValue.GetObject())["schema_version"] = std::int64_t{ 2 };
	CheckRejected(stValue);
	(*stValue.GetObject())["schema_version"] = 1.0;
	CheckRejected(stValue);
	stValue = ValidConfiguration();
	(*stValue.GetObject())["exposure"] = true;
	CheckRejected(stValue);
	stValue = ValidConfiguration();
	(*stValue.GetObject())["camera"] = "camera";
	CheckRejected(stValue);
	CheckRejected(JsonValue{});
}

ENGINE_NEXT_TEST("Render configuration rejects malformed and mismatched package digests")
{
	JsonValue stValue = ValidConfiguration();
	CheckRejected(stValue, std::string(64, 'b'));
	CheckRejected(stValue, "");
	(*stValue.GetObject())["source_package_sha256"] = std::string(64, 'A');
	CheckRejected(stValue);
	(*stValue.GetObject())["source_package_sha256"] = std::string(63, 'a');
	CheckRejected(stValue);
	(*stValue.GetObject())["source_package_sha256"] = std::int64_t{ 0 };
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration enforces projection and exposure bounds")
{
	const std::array<std::string, 4> arrFields{ "vertical_fov_degrees", "near_plane", "far_plane", "exposure" };
	const std::array<double, 4> arrMinimum{ 1, 0.001, 0.051, 0.001 };
	const std::array<double, 4> arrMaximum{ 170, 100, 1e7, 1000 };
	for (std::size_t nIndex = 0; nIndex < arrFields.size(); ++nIndex)
	{
		for (double dValue : { arrMinimum[nIndex], arrMaximum[nIndex] })
		{
			JsonValue stValue = ValidConfiguration();
			JsonValue &stField = nIndex == 3 ? (*stValue.GetObject())[arrFields[nIndex]] : CameraField(stValue, arrFields[nIndex]);
			stField = dValue;
			EngineNext::Rendering::RenderConfiguration stConfiguration;
			EngineNext::Assets::Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		}
		for (double dValue : { -1.0, arrMaximum[nIndex] * 2, std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
		{
			JsonValue stValue = ValidConfiguration();
			JsonValue &stField = nIndex == 3 ? (*stValue.GetObject())[arrFields[nIndex]] : CameraField(stValue, arrFields[nIndex]);
			stField = dValue;
			CheckRejected(stValue);
		}
	}
	JsonValue stValue = ValidConfiguration();
	CameraField(stValue, "far_plane") = 0.05;
	CheckRejected(stValue);
	CameraField(stValue, "far_plane") = 0.01;
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration rejects degenerate camera vectors and nonfinite components")
{
	for (const std::string &strField : { "position", "target", "up" })
	{
		JsonValue stValue = ValidConfiguration();
		CameraField(stValue, strField) = JsonValue::List{ 0.0, 0.0 };
		CheckRejected(stValue);
		CameraField(stValue, strField) = JsonValue::List{ 0.0, 1.0, std::numeric_limits<double>::infinity() };
		CheckRejected(stValue);
		CameraField(stValue, strField) = JsonValue::List{ 0.0, 1.0, true };
		CheckRejected(stValue);
	}
	JsonValue stValue = ValidConfiguration();
	CameraField(stValue, "target") = JsonValue::List{ 0.0, 0.0, 5.0 };
	CheckRejected(stValue);
	stValue = ValidConfiguration();
	CameraField(stValue, "up") = JsonValue::List{ 0.0, 0.0, 0.0 };
	CheckRejected(stValue);
	CameraField(stValue, "up") = JsonValue::List{ 0.0, 0.0, 1.0 };
	CheckRejected(stValue);
	CameraField(stValue, "up") = JsonValue::List{ 0.0, 1e-14, 1.0 };
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration handles finite extreme direction magnitudes")
{
	JsonValue stValue = ValidConfiguration();
	const double dMaximum = std::numeric_limits<double>::max();
	CameraField(stValue, "position") = JsonValue::List{ 0.0, 0.0, dMaximum };
	CameraField(stValue, "target") = JsonValue::List{ 0.0, 0.0, -dMaximum };
	CameraField(stValue, "up") = JsonValue::List{ 0.0, dMaximum, 0.0 };
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	CameraField(stValue, "position") = JsonValue::List{ 0.0, 0.0, std::numeric_limits<double>::denorm_min() };
	CameraField(stValue, "target") = JsonValue::List{ 0.0, 0.0, 0.0 };
	CameraField(stValue, "up") = JsonValue::List{ 0.0, std::numeric_limits<double>::denorm_min(), 0.0 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
}

ENGINE_NEXT_TEST("Render configuration file loader rejects duplicate keys malformed JSON and oversized input")
{
	TemporaryConfiguration stFile;
	std::string strText;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(ValidConfiguration(), strText));
	ENGINE_NEXT_CHECK(stFile.Write(strText));
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	strText.insert(1, "\"exposure\":2,");
	ENGINE_NEXT_CHECK(stFile.Write(strText));
	stConfiguration.dExposure = 123;
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.dExposure, 123.0);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK(stFile.Write("{"));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(ValidConfiguration(), strText));
	strText.resize(65536, ' ');
	ENGINE_NEXT_CHECK(stFile.Write(strText));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	strText.push_back(' ');
	ENGINE_NEXT_CHECK(stFile.Write(strText));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stFile.Write(""));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath / "missing", strSourceDigest, stConfiguration, arrDiagnostics));
}

ENGINE_NEXT_TEST("Render configuration file loader preserves UTF-8 paths in diagnostics")
{
	TemporaryConfiguration stFile;
	stFile.stPath += std::filesystem::u8path(u8"-\u914d\u7f6e.json");
	std::string strText;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(ValidConfiguration(), strText));
	ENGINE_NEXT_CHECK(stFile.Write(strText));
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
	const std::filesystem::path stMissing = stFile.stPath / "missing";
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadRenderConfiguration(stMissing, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.front().strPath, stMissing.u8string());
}

ENGINE_NEXT_TEST("Render configuration preserves optional lighting and shadow defaults for earlier documents")
{
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(ValidConfiguration(), strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stDirectionalLight.arrDirection, (std::array<double, 3>{ 0.5, -0.8, -0.6 }));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stDirectionalLight.arrColor, (std::array<double, 3>{ 1, 0.9666667, 0.9 }));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stDirectionalLight.dIlluminance, 3.0);
	ENGINE_NEXT_CHECK(stConfiguration.stShadows.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.nResolution, 2048U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.dDistance, 50.0);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.dSplitLambda, 0.6);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.dDepthBias, 0.0005);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.dNormalBias, 0.01);
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["directional_light"] = DirectionalLight();
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	stValue = ValidConfiguration();
	(*stValue.GetObject())["shadows"] = Shadows();
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
}

ENGINE_NEXT_TEST("Render configuration strictly validates optional nested lighting and shadow fields")
{
	for (const std::string &strName : { "directional_light", "shadows" })
	{
		JsonValue stValue = ValidConfiguration();
		(*stValue.GetObject())[strName] = JsonValue{};
		CheckRejected(stValue);
		(*stValue.GetObject())[strName] = strName == "shadows" ? Shadows() : DirectionalLight();
		JsonValue::Object &mapSettings = *(*stValue.GetObject())[strName].GetObject();
		mapSettings["unknown"] = true;
		CheckRejected(stValue);
		mapSettings.erase("unknown");
		mapSettings.erase(mapSettings.begin());
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Render configuration bounds directional color and illuminance while preserving direction magnitude")
{
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["directional_light"] = DirectionalLight();
	JsonValue::Object &mapLight = *(*stValue.GetObject())["directional_light"].GetObject();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	mapLight["direction"] = JsonValue::List{ 0.0, -8.0, 0.0 };
	mapLight["color"] = JsonValue::List{ 0.0, 100.0, 1.0 };
	for (double dValue : { 0.0, 1000000.0 })
	{
		mapLight["illuminance"] = dValue;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stDirectionalLight.arrDirection[1], -8.0);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stDirectionalLight.dIlluminance, dValue);
	}
	for (double dValue : { -0.001, 1000000.01, std::numeric_limits<double>::infinity() })
	{
		mapLight["illuminance"] = dValue;
		CheckRejected(stValue);
	}
	mapLight["illuminance"] = 1.0;
	for (const JsonValue &stDirection : { JsonValue(JsonValue::List{ 0.0, 0.0, 0.0 }), JsonValue(JsonValue::List{ 1.0, 2.0 }),
										  JsonValue(JsonValue::List{ 1.0, true, 0.0 }), JsonValue(JsonValue::List{ std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0 }) })
	{
		mapLight["direction"] = stDirection;
		CheckRejected(stValue);
	}
	mapLight["direction"] = JsonValue::List{ std::numeric_limits<double>::denorm_min(), 0.0, 0.0 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	mapLight["direction"] = JsonValue::List{ std::numeric_limits<double>::max(), 0.0, 0.0 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	for (double dValue : { -0.001, 100.01, std::numeric_limits<double>::infinity() })
	{
		mapLight["color"] = JsonValue::List{ 0.0, dValue, 0.0 };
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Render configuration validates shadow discrete sizes numeric ranges and disabled settings")
{
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["shadows"] = Shadows();
	JsonValue::Object &mapShadows = *(*stValue.GetObject())["shadows"].GetObject();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	for (std::int64_t nSize : { 256, 512, 1024, 2048, 4096 })
	{
		mapShadows["resolution"] = nSize;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.nResolution, static_cast<std::uint32_t>(nSize));
	}
	for (const JsonValue &stSize : { JsonValue(std::int64_t{ 0 }), JsonValue(std::int64_t{ 300 }), JsonValue(std::int64_t{ 8192 }), JsonValue(2048.0) })
	{
		mapShadows["resolution"] = stSize;
		CheckRejected(stValue);
	}
	mapShadows["resolution"] = std::int64_t{ 256 };
	const std::array<std::string, 4> arrFields{ "distance", "split_lambda", "depth_bias", "normal_bias" };
	const std::array<double, 4> arrMinimum{ 0.1, 0, 0, 0 };
	const std::array<double, 4> arrMaximum{ 10000, 1, 0.05, 1 };
	for (std::size_t nIndex = 0; nIndex < arrFields.size(); ++nIndex)
	{
		for (double dValue : { arrMinimum[nIndex], arrMaximum[nIndex] })
		{
			mapShadows[arrFields[nIndex]] = dValue;
			ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		}
		for (double dValue : { -0.001, arrMaximum[nIndex] * 2, std::numeric_limits<double>::quiet_NaN() })
		{
			mapShadows[arrFields[nIndex]] = dValue;
			CheckRejected(stValue);
		}
		mapShadows[arrFields[nIndex]] = arrMinimum[nIndex];
	}
	mapShadows["enabled"] = false;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stConfiguration.stShadows.bEnabled);
	mapShadows["distance"] = -1.0;
	CheckRejected(stValue);
	mapShadows["distance"] = 1.0;
	mapShadows["enabled"] = std::int64_t{ 0 };
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration loads optional settings and rejects duplicate nested keys")
{
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["directional_light"] = DirectionalLight();
	(*stValue.GetObject())["shadows"] = Shadows();
	std::string strText;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stValue, strText));
	TemporaryConfiguration stFile;
	ENGINE_NEXT_CHECK(stFile.Write(strText));
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	const std::string strKey = "\"enabled\":true";
	const std::size_t nKey = strText.find(strKey);
	ENGINE_NEXT_CHECK(nKey != std::string::npos);
	strText.insert(nKey, "\"enabled\":false,");
	ENGINE_NEXT_CHECK(stFile.Write(strText));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::LoadRenderConfiguration(stFile.stPath, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stShadows.bEnabled);
}

ENGINE_NEXT_TEST("Render configuration retains the default point and supports empty local light arrays")
{
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	JsonValue stValue = ValidConfiguration();
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrPointLights.size(), 1U);
	ENGINE_NEXT_CHECK(stConfiguration.arrSpotLights.empty());
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrPointLights[0].nId, 1U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrPointLights[0].dLumens, 226.194671);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrPointLights[0].dRange, 25.0);
	ENGINE_NEXT_CHECK(stConfiguration.arrPointLights[0].bCastsShadow);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.nLocalResolution, 1024U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.eFilter, EngineNext::Rendering::ShadowFilter::Pcf);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.dLightRadius, 0.1);
	(*stValue.GetObject())["point_lights"] = JsonValue::List{};
	(*stValue.GetObject())["spot_lights"] = JsonValue::List{};
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.arrPointLights.empty());
	ENGINE_NEXT_CHECK(stConfiguration.arrSpotLights.empty());
}

ENGINE_NEXT_TEST("Render configuration requires exact local light fields and globally unique positive IDs")
{
	for (const std::string &strArray : { "point_lights", "spot_lights" })
	{
		JsonValue stValue = ValidConfiguration();
		const JsonValue stLight = strArray == "point_lights" ? PointLight() : SpotLight();
		(*stValue.GetObject())[strArray] = JsonValue::List{ stLight };
		EngineNext::Rendering::RenderConfiguration stConfiguration;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		JsonValue::Object &mapLight = *(*stValue.GetObject())[strArray].GetList()->front().GetObject();
		mapLight["unknown"] = true;
		CheckRejected(stValue);
		mapLight.erase("unknown");
		mapLight.erase("color");
		CheckRejected(stValue);
		mapLight["color"] = JsonValue::List{ 1.0, 1.0, 1.0 };
		for (const JsonValue &stId : { JsonValue(std::int64_t{ 0 }), JsonValue(std::int64_t{ -1 }), JsonValue(std::int64_t{ 4294967296LL }), JsonValue(2.0) })
		{
			mapLight["id"] = stId;
			CheckRejected(stValue);
		}
		(*stValue.GetObject())[strArray] = JsonValue::List{ stLight, stLight };
		CheckRejected(stValue);
		(*stValue.GetObject())[strArray] = true;
		CheckRejected(stValue);
		(*stValue.GetObject())[strArray] = JsonValue::List{ JsonValue{} };
		CheckRejected(stValue);
	}
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["spot_lights"] = JsonValue::List{ SpotLight(1) };
	CheckRejected(stValue);
	(*stValue.GetObject())["point_lights"] = JsonValue::List{};
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	(*stValue.GetObject())["point_lights"] = JsonValue::List{ PointLight(1), PointLight(2), PointLight(3), PointLight(4) };
	(*stValue.GetObject())["spot_lights"] = JsonValue::List{ SpotLight(5), SpotLight(6), SpotLight(7), SpotLight(8) };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrPointLights.size() + stConfiguration.arrSpotLights.size(), 8U);
	(*stValue.GetObject())["point_lights"].GetList()->push_back(PointLight(9));
	CheckRejected(stValue);
	(*stValue.GetObject())["point_lights"].GetList()->pop_back();
	(*stValue.GetObject())["spot_lights"].GetList()->push_back(SpotLight(9));
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration bounds local light power range color and position")
{
	for (const std::string &strArray : { "point_lights", "spot_lights" })
	{
		JsonValue stValue = ValidConfiguration();
		(*stValue.GetObject())[strArray] = JsonValue::List{ strArray == "point_lights" ? PointLight() : SpotLight() };
		JsonValue::Object &mapLight = *(*stValue.GetObject())[strArray].GetList()->front().GetObject();
		EngineNext::Rendering::RenderConfiguration stConfiguration;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		mapLight["lumens"] = 0.0;
		mapLight["range"] = 0.1;
		mapLight["color"] = JsonValue::List{ 0.0, 100.0, 0.0 };
		mapLight["casts_shadow"] = false;
		mapLight["position"] = JsonValue::List{ std::numeric_limits<double>::max(), 0.0, 0.0 };
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		mapLight["lumens"] = 1e8;
		mapLight["range"] = 10000.0;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		for (double dInvalid : { -0.01, 1e8 + 1, std::numeric_limits<double>::infinity() })
		{
			mapLight["lumens"] = dInvalid;
			CheckRejected(stValue);
		}
		mapLight["lumens"] = 1.0;
		for (double dInvalid : { 0.0, 10001.0, std::numeric_limits<double>::quiet_NaN() })
		{
			mapLight["range"] = dInvalid;
			CheckRejected(stValue);
		}
		mapLight["range"] = 1.0;
		for (const JsonValue &stColor : { JsonValue(JsonValue::List{ -0.1, 0.0, 0.0 }), JsonValue(JsonValue::List{ 100.1, 0.0, 0.0 }), JsonValue(JsonValue::List{ 1.0, 1.0 }), JsonValue(JsonValue::List{ 0.0, 0.0, std::numeric_limits<double>::infinity() }) })
		{
			mapLight["color"] = stColor;
			CheckRejected(stValue);
		}
		mapLight["color"] = JsonValue::List{ 1.0, 1.0, 1.0 };
		mapLight["position"] = JsonValue::List{ 0.0, std::numeric_limits<double>::infinity(), 0.0 };
		CheckRejected(stValue);
		mapLight["position"] = JsonValue::List{ 0.0, 0.0, 0.0 };
		mapLight["casts_shadow"] = 1.0;
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Render configuration supports narrow spot cones and rejects invalid angles or directions")
{
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["spot_lights"] = JsonValue::List{ SpotLight() };
	JsonValue::Object &mapLight = *(*stValue.GetObject())["spot_lights"].GetList()->front().GetObject();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	mapLight["inner_angle_degrees"] = 0.0;
	mapLight["outer_angle_degrees"] = 0.001;
	mapLight["direction"] = JsonValue::List{ 0.0, -20.0, 0.0 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrSpotLights[0].arrDirection[1], -20.0);
	mapLight["inner_angle_degrees"] = 85.0;
	mapLight["outer_angle_degrees"] = 89.0;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	for (double dInner : { -0.01, 85.1, 89.0, std::numeric_limits<double>::infinity() })
	{
		mapLight["inner_angle_degrees"] = dInner;
		CheckRejected(stValue);
	}
	mapLight["inner_angle_degrees"] = 20.0;
	for (double dOuter : { 0.0, 20.0, 19.9, 89.1, std::numeric_limits<double>::quiet_NaN() })
	{
		mapLight["outer_angle_degrees"] = dOuter;
		CheckRejected(stValue);
	}
	mapLight["outer_angle_degrees"] = 35.0;
	mapLight["direction"] = JsonValue::List{ 0.0, 0.0, 0.0 };
	CheckRejected(stValue);
	mapLight["direction"] = JsonValue::List{ std::numeric_limits<double>::infinity(), 0.0, 0.0 };
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration validates optional local shadow quality settings")
{
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["shadows"] = Shadows();
	JsonValue::Object &mapShadows = *(*stValue.GetObject())["shadows"].GetObject();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	for (std::int64_t nResolution : { 256, 512, 1024, 2048 })
	{
		mapShadows["local_resolution"] = nResolution;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.nLocalResolution, static_cast<std::uint32_t>(nResolution));
	}
	for (const JsonValue &stResolution : { JsonValue(std::int64_t{ 4096 }), JsonValue(std::int64_t{ 300 }), JsonValue(1024.0) })
	{
		mapShadows["local_resolution"] = stResolution;
		CheckRejected(stValue);
	}
	mapShadows["local_resolution"] = std::int64_t{ 1024 };
	mapShadows["filter"] = "pcss";
	mapShadows["light_radius"] = 10.0;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stShadows.eFilter, EngineNext::Rendering::ShadowFilter::Pcss);
	mapShadows["filter"] = "pcf";
	mapShadows["light_radius"] = 0.0;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	for (const JsonValue &stFilter : { JsonValue("PCF"), JsonValue("unknown"), JsonValue(true) })
	{
		mapShadows["filter"] = stFilter;
		CheckRejected(stValue);
	}
	mapShadows["filter"] = "pcf";
	for (double dRadius : { -0.01, 10.01, std::numeric_limits<double>::infinity() })
	{
		mapShadows["light_radius"] = dRadius;
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Spot solid angle preserves declared flux under the shader angular falloff")
{
	constexpr double PI = 3.141592653589793238462643383279502884;
	constexpr std::uint32_t INTEGRATION_STEPS = 65536;
	const std::array<std::array<double, 2>, 5> arrCones{ { { 0, 1e-8 }, { 0, 0.001 }, { 0, 35 }, { 20, 35 }, { 85, 89 } } };
	for (const std::array<double, 2> &arrCone : arrCones)
	{
		double dSolidAngle = 0;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ComputeSpotSolidAngle(arrCone[0], arrCone[1], dSolidAngle));
		ENGINE_NEXT_CHECK(std::isfinite(dSolidAngle) && dSolidAngle > 0);
		const double dInnerSine = std::sin(arrCone[0] * (PI / 360));
		const double dOuterSine = std::sin(arrCone[1] * (PI / 360));
		const double dInnerChordSquared = 4 * dInnerSine * dInnerSine;
		const double dOuterChordSquared = 4 * dOuterSine * dOuterSine;
		const double dAngularStep = arrCone[1] * (PI / 180) / INTEGRATION_STEPS;
		double dIntegratedSolidAngle = 0;
		for (std::uint32_t nStep = 0; nStep < INTEGRATION_STEPS; ++nStep)
		{
			const double dTheta = (nStep + 0.5) * dAngularStep;
			const double dSine = std::sin(dTheta * 0.5);
			const double dChordSquared = 4 * dSine * dSine;
			const double dTransition = std::clamp((dChordSquared - dInnerChordSquared) / (dOuterChordSquared - dInnerChordSquared), 0.0, 1.0);
			const double dFalloff = 1 - dTransition * dTransition * (3 - 2 * dTransition);
			dIntegratedSolidAngle += dFalloff * 2 * PI * std::sin(dTheta) * dAngularStep;
		}
		constexpr double DECLARED_LUMENS = 1200;
		const double dIntegratedLumens = DECLARED_LUMENS * dIntegratedSolidAngle / dSolidAngle;
		ENGINE_NEXT_CHECK(std::abs(dIntegratedLumens / DECLARED_LUMENS - 1) < 1e-7);
	}
}

ENGINE_NEXT_TEST("Spot solid angle rejects invalid and underflowing angles transactionally")
{
	const std::array<std::array<double, 2>, 8> arrCones{ { { -1, 20 }, { 86, 89 }, { 20, 20 }, { 21, 20 }, { 0, 90 }, { std::numeric_limits<double>::quiet_NaN(), 20 }, { 0, std::numeric_limits<double>::infinity() }, { 0, std::numeric_limits<double>::denorm_min() } } };
	for (const std::array<double, 2> &arrCone : arrCones)
	{
		double dSolidAngle = 42;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ComputeSpotSolidAngle(arrCone[0], arrCone[1], dSolidAngle));
		ENGINE_NEXT_CHECK_EQ(dSolidAngle, 42);
	}
}
