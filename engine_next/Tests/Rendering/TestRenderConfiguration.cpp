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
	stConfiguration.stTemporal.bEnabled = false;
	stConfiguration.stTemporal.dHistoryWeight = 0.25;
	stConfiguration.stTemporal.dDepthThreshold = 0.125;
	stConfiguration.stExposure.eMode = EngineNext::Rendering::ExposureMode::Manual;
	stConfiguration.stExposure.dManualEv100 = 7;
	stConfiguration.stBloom.bEnabled = true;
	stConfiguration.stBloom.dIntensity = 0.5;
	stConfiguration.stLightAnimation.bLoop = true;
	stConfiguration.stLightAnimation.eInterpolation = EngineNext::Rendering::LightInterpolation::Step;
	stConfiguration.stLightAnimation.arrKeyframes = { { 0, 2 }, { 1, 3 } };
	stConfiguration.stReflections.bEnabled = true;
	stConfiguration.stReflections.dMaxDistance = 321;
	stConfiguration.stVolume.dDistance = 456;
	stConfiguration.arrParticles = { EngineNext::Rendering::ParticleSettings{} };
	stConfiguration.arrParticles[0].nEmitterId = 123;
	stConfiguration.stMaterials.arrOverrides = { { "retained.asset", 7, {}, {} } };
	stConfiguration.stGlobalIllumination.nRaysPerProbe = 256;
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
	ENGINE_NEXT_CHECK(!stConfiguration.stTemporal.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.dHistoryWeight, 0.25);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.dDepthThreshold, 0.125);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.eMode, EngineNext::Rendering::ExposureMode::Manual);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dManualEv100, 7);
	ENGINE_NEXT_CHECK(stConfiguration.stBloom.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.dIntensity, 0.5);
	ENGINE_NEXT_CHECK(stConfiguration.stLightAnimation.bLoop);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.eInterpolation, EngineNext::Rendering::LightInterpolation::Step);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.arrKeyframes.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.arrKeyframes.back().dMultiplier, 3);
	ENGINE_NEXT_CHECK(stConfiguration.stReflections.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stReflections.dMaxDistance, 321);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stVolume.dDistance, 456);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrParticles.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrParticles[0].nEmitterId, 123U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stMaterials.arrOverrides.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stMaterials.arrOverrides[0].strAssetId, "retained.asset");
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stMaterials.arrOverrides[0].nMaterialIndex, 7U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stGlobalIllumination.nRaysPerProbe, 256U);
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

ENGINE_NEXT_TEST("Render configuration defaults and bounds optional temporal settings")
{
	JsonValue stValue = ValidConfiguration();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stTemporal.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.dHistoryWeight, 0.9);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.dDepthThreshold, 0.01);
	for (bool bEnabled : { false, true })
	{
		for (double dWeight : { 0.0, 0.9, 0.99 })
		{
			for (double dThreshold : { 0.0001, 0.01, 0.25 })
			{
				(*stValue.GetObject())["temporal_aa"] = JsonValue::Object{
					{ "enabled", bEnabled }, { "history_weight", dWeight }, { "depth_threshold", dThreshold }
				};
				ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
				ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.bEnabled, bEnabled);
				ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.dHistoryWeight, dWeight);
				ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.dDepthThreshold, dThreshold);
			}
		}
	}
	stValue.GetObject()->erase("temporal_aa");
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stTemporal.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stTemporal.dHistoryWeight, 0.9);
}

ENGINE_NEXT_TEST("Render configuration rejects malformed temporal settings transactionally")
{
	JsonValue stValue = ValidConfiguration();
	const JsonValue stValidTemporal = JsonValue::Object{
		{ "enabled", true }, { "history_weight", 0.9 }, { "depth_threshold", 0.01 }
	};
	for (const JsonValue &stWrongType : { JsonValue{}, JsonValue(true), JsonValue(1.0), JsonValue("temporal"), JsonValue(JsonValue::List{}) })
	{
		(*stValue.GetObject())["temporal_aa"] = stWrongType;
		CheckRejected(stValue);
	}
	for (const std::string &strField : { "enabled", "history_weight", "depth_threshold" })
	{
		(*stValue.GetObject())["temporal_aa"] = stValidTemporal;
		(*stValue.GetObject())["temporal_aa"].GetObject()->erase(strField);
		CheckRejected(stValue);
	}
	(*stValue.GetObject())["temporal_aa"] = stValidTemporal;
	JsonValue::Object &mapTemporal = *(*stValue.GetObject())["temporal_aa"].GetObject();
	mapTemporal["unknown"] = true;
	CheckRejected(stValue);
	mapTemporal.erase("unknown");
	mapTemporal["enabled"] = 1.0;
	CheckRejected(stValue);
	mapTemporal["enabled"] = false;
	for (const JsonValue &stWeight : { JsonValue(-0.001), JsonValue(0.991), JsonValue(std::numeric_limits<double>::quiet_NaN()),
									   JsonValue(std::numeric_limits<double>::infinity()), JsonValue(true), JsonValue("0.5") })
	{
		mapTemporal["history_weight"] = stWeight;
		CheckRejected(stValue);
	}
	mapTemporal["history_weight"] = 0.9;
	for (const JsonValue &stThreshold : { JsonValue(0.0), JsonValue(0.000099), JsonValue(0.251), JsonValue(std::numeric_limits<double>::quiet_NaN()),
										  JsonValue(std::numeric_limits<double>::infinity()), JsonValue(false), JsonValue("0.01") })
	{
		mapTemporal["depth_threshold"] = stThreshold;
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Render configuration preserves numeric exposure with optional post-process defaults")
{
	JsonValue stValue = ValidConfiguration();
	(*stValue.GetObject())["exposure"] = 321.0;
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	for (bool bIncludeObjects : { false, true })
	{
		if (bIncludeObjects)
		{
			(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{};
			(*stValue.GetObject())["bloom"] = JsonValue::Object{};
		}
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stConfiguration.dExposure, 321);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.eMode, EngineNext::Rendering::ExposureMode::Legacy);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dManualEv100, 10);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dCompensationEv, 0);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dMinimumEv100, -16);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dMaximumEv100, 24);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dLowPercentile, 0.1);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dHighPercentile, 0.9);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dLightHalfLife, 0.25);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dDarkHalfLife, 0.75);
		ENGINE_NEXT_CHECK(!stConfiguration.stBloom.bEnabled);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.dIntensity, 0.04);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.dThreshold, 1);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.dSoftKnee, 0.5);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.nMipCount, 6U);
	}
	stValue.GetObject()->erase("exposure");
	CheckRejected(stValue);
	(*stValue.GetObject())["exposure"] = JsonValue::Object{};
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration accepts exposure modes and inclusive post-process limits")
{
	JsonValue stValue = ValidConfiguration();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const std::array<EngineNext::Rendering::ExposureMode, 3> arrModes{
		EngineNext::Rendering::ExposureMode::Legacy, EngineNext::Rendering::ExposureMode::Manual, EngineNext::Rendering::ExposureMode::Automatic
	};
	const std::array<std::string, 3> arrNames{ "legacy", "manual", "automatic" };
	for (std::size_t nMode = 0; nMode < arrModes.size(); ++nMode)
	{
		for (double dEndpoint : { 0.0, 1.0 })
		{
			(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{
				{ "mode", arrNames[nMode] }, { "manual_ev100", -16 + 40 * dEndpoint }, { "compensation_ev", -10 + 20 * dEndpoint }, { "min_ev100", -16.0 }, { "max_ev100", 24.0 }, { "low_percentile", 0.0 }, { "high_percentile", 1.0 }, { "light_half_life", 10 * dEndpoint }, { "dark_half_life", 10 * dEndpoint }
			};
			(*stValue.GetObject())["bloom"] = JsonValue::Object{
				{ "enabled", dEndpoint != 0 }, { "intensity", 10 * dEndpoint }, { "threshold", 65504 * dEndpoint }, { "soft_knee", dEndpoint }, { "mip_count", std::int64_t{ dEndpoint == 0 ? 1 : 6 } }
			};
			ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.eMode, arrModes[nMode]);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dManualEv100, -16 + 40 * dEndpoint);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dCompensationEv, -10 + 20 * dEndpoint);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dLightHalfLife, 10 * dEndpoint);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dDarkHalfLife, 10 * dEndpoint);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.bEnabled, dEndpoint != 0);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.dIntensity, 10 * dEndpoint);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.dThreshold, 65504 * dEndpoint);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.dSoftKnee, dEndpoint);
			ENGINE_NEXT_CHECK_EQ(stConfiguration.stBloom.nMipCount, dEndpoint == 0 ? 1U : 6U);
		}
	}
	(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{ { "min_ev100", 4.0 }, { "max_ev100", 4.0 } };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dMinimumEv100, 4);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stExposure.dMaximumEv100, 4);
}

ENGINE_NEXT_TEST("Render configuration rejects malformed post-process objects transactionally")
{
	JsonValue stValue = ValidConfiguration();
	for (const std::string &strObject : { "exposure_settings", "bloom" })
	{
		for (const JsonValue &stWrong : { JsonValue{}, JsonValue(true), JsonValue(1.0), JsonValue("settings"), JsonValue(JsonValue::List{}) })
		{
			(*stValue.GetObject())[strObject] = stWrong;
			CheckRejected(stValue);
		}
		(*stValue.GetObject())[strObject] = JsonValue::Object{ { "unknown", true } };
		CheckRejected(stValue);
		stValue.GetObject()->erase(strObject);
	}
	for (const JsonValue &stMode : { JsonValue("Manual"), JsonValue("auto"), JsonValue(true), JsonValue(1.0), JsonValue{} })
	{
		(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{ { "mode", stMode } };
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Render configuration validates every optional exposure number and its relationships")
{
	JsonValue stValue = ValidConfiguration();
	const std::array<std::string, 8> arrFields{
		"manual_ev100", "compensation_ev", "min_ev100", "max_ev100", "low_percentile", "high_percentile", "light_half_life", "dark_half_life"
	};
	for (const std::string &strField : arrFields)
	{
		for (const JsonValue &stWrong : { JsonValue(true), JsonValue("1"), JsonValue{}, JsonValue(std::numeric_limits<double>::infinity()), JsonValue(std::numeric_limits<double>::quiet_NaN()), JsonValue(-100.0), JsonValue(100.0) })
		{
			(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{ { strField, stWrong } };
			CheckRejected(stValue);
		}
	}
	(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{ { "min_ev100", 3.0 }, { "max_ev100", 2.0 } };
	CheckRejected(stValue);
	(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{ { "low_percentile", 0.7 }, { "high_percentile", 0.7 } };
	CheckRejected(stValue);
	(*stValue.GetObject())["exposure_settings"] = JsonValue::Object{ { "low_percentile", 0.8 }, { "high_percentile", 0.7 } };
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration validates bloom fields even while disabled")
{
	JsonValue stValue = ValidConfiguration();
	for (const std::string &strField : { "enabled", "intensity", "threshold", "soft_knee", "mip_count" })
	{
		for (const JsonValue &stWrong : { JsonValue("1"), JsonValue{}, JsonValue(std::numeric_limits<double>::infinity()) })
		{
			(*stValue.GetObject())["bloom"] = JsonValue::Object{ { "enabled", false } };
			(*(*stValue.GetObject())["bloom"].GetObject())[strField] = stWrong;
			CheckRejected(stValue);
		}
	}
	for (const JsonValue &stWrong : { JsonValue(0.0), JsonValue(1.0), JsonValue(std::int64_t{ 0 }), JsonValue(std::int64_t{ 7 }), JsonValue(true) })
	{
		(*stValue.GetObject())["bloom"] = JsonValue::Object{ { "mip_count", stWrong } };
		CheckRejected(stValue);
	}
	for (const std::string &strField : { "intensity", "threshold", "soft_knee" })
	{
		for (const JsonValue &stWrong : { JsonValue(true), JsonValue(-0.001), JsonValue(65505.0) })
		{
			(*stValue.GetObject())["bloom"] = JsonValue::Object{ { "enabled", false }, { strField, stWrong } };
			CheckRejected(stValue);
		}
	}
}

ENGINE_NEXT_TEST("Render configuration defaults and parses a directional light timeline")
{
	JsonValue stValue = ValidConfiguration();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stLightAnimation.arrKeyframes.empty());
	ENGINE_NEXT_CHECK(!stConfiguration.stLightAnimation.bLoop);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.eInterpolation, EngineNext::Rendering::LightInterpolation::Linear);
	for (const std::string &strInterpolation : { "linear", "step" })
	{
		(*stValue.GetObject())["light_animation"] = JsonValue::Object{
			{ "loop", true }, { "interpolation", strInterpolation }, { "keyframes", JsonValue::List{ JsonValue::Object{ { "seconds", 0.0 }, { "multiplier", 1.0 } }, JsonValue::Object{ { "seconds", 2.0 }, { "multiplier", 100.0 } }, JsonValue::Object{ { "seconds", 4.0 }, { "multiplier", 0.0 } } } }
		};
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		ENGINE_NEXT_CHECK(stConfiguration.stLightAnimation.bLoop);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.arrKeyframes.size(), 3U);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.arrKeyframes[1].dSeconds, 2);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.arrKeyframes[1].dMultiplier, 100);
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.eInterpolation, strInterpolation == "linear" ? EngineNext::Rendering::LightInterpolation::Linear : EngineNext::Rendering::LightInterpolation::Step);
	}
	for (const JsonValue &stEmpty : { JsonValue(JsonValue::Object{}), JsonValue(JsonValue::Object{ { "loop", true }, { "keyframes", JsonValue::List{} } }) })
	{
		(*stValue.GetObject())["light_animation"] = stEmpty;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
		ENGINE_NEXT_CHECK(stConfiguration.stLightAnimation.arrKeyframes.empty());
		ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.eInterpolation, EngineNext::Rendering::LightInterpolation::Linear);
	}
}

ENGINE_NEXT_TEST("Render configuration rejects malformed light timeline objects and key fields")
{
	JsonValue stValue = ValidConfiguration();
	for (const JsonValue &stBad : { JsonValue{}, JsonValue(true), JsonValue(1.0), JsonValue("track"), JsonValue(JsonValue::List{}), JsonValue(JsonValue::Object{ { "unknown", true } }) })
	{
		(*stValue.GetObject())["light_animation"] = stBad;
		CheckRejected(stValue);
	}
	for (const JsonValue &stBad : { JsonValue("LINEAR"), JsonValue("spline"), JsonValue(true), JsonValue{} })
	{
		(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "interpolation", stBad } };
		CheckRejected(stValue);
	}
	for (const JsonValue &stBad : { JsonValue("true"), JsonValue(1.0), JsonValue{} })
	{
		(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "loop", stBad } };
		CheckRejected(stValue);
	}
	for (const JsonValue &stBad : { JsonValue{}, JsonValue(true), JsonValue(JsonValue::Object{}), JsonValue("keys") })
	{
		(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "keyframes", stBad } };
		CheckRejected(stValue);
	}
	for (const JsonValue &stBadKey : { JsonValue(true), JsonValue(JsonValue::Object{}), JsonValue(JsonValue::Object{ { "seconds", 0.0 } }),
									   JsonValue(JsonValue::Object{ { "multiplier", 1.0 } }), JsonValue(JsonValue::Object{ { "seconds", 0.0 }, { "multiplier", 1.0 }, { "extra", true } }) })
	{
		(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "keyframes", JsonValue::List{ stBadKey } } };
		CheckRejected(stValue);
	}
	for (const std::string &strField : { "seconds", "multiplier" })
	{
		for (const JsonValue &stBad : { JsonValue(true), JsonValue("0"), JsonValue{}, JsonValue(-1.0), JsonValue(std::numeric_limits<double>::infinity()), JsonValue(std::numeric_limits<double>::quiet_NaN()) })
		{
			JsonValue stKey = JsonValue::Object{ { "seconds", 0.0 }, { "multiplier", 1.0 } };
			(*stKey.GetObject())[strField] = stBad;
			(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "keyframes", JsonValue::List{ stKey } } };
			CheckRejected(stValue);
		}
	}
}

ENGINE_NEXT_TEST("Render configuration validates ordered timeline budget and illuminance product")
{
	JsonValue stValue = ValidConfiguration();
	for (const JsonValue::List &arrBadKeys : {
				 JsonValue::List{ JsonValue::Object{ { "seconds", 1.0 }, { "multiplier", 1.0 } } },
				 JsonValue::List{ JsonValue::Object{ { "seconds", 0.0 }, { "multiplier", 1.0 } }, JsonValue::Object{ { "seconds", 0.0 }, { "multiplier", 1.0 } } } })
	{
		(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "keyframes", arrBadKeys } };
		CheckRejected(stValue);
	}
	(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "loop", true }, { "keyframes", JsonValue::List{ JsonValue::Object{ { "seconds", 0.0 }, { "multiplier", 1.0 } } } } };
	CheckRejected(stValue);
	JsonValue::List arrKeys;
	for (std::uint32_t nKey = 0; nKey < 256; ++nKey)
	{
		arrKeys.emplace_back(JsonValue::Object{ { "seconds", static_cast<double>(nKey) }, { "multiplier", 1.0 } });
	}
	(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "keyframes", arrKeys } };
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stLightAnimation.arrKeyframes.size(), 256U);
	arrKeys.emplace_back(JsonValue::Object{ { "seconds", 256.0 }, { "multiplier", 1.0 } });
	(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "keyframes", arrKeys } };
	CheckRejected(stValue);
	(*stValue.GetObject())["directional_light"] = DirectionalLight();
	(*(*stValue.GetObject())["directional_light"].GetObject())["illuminance"] = 1e6;
	(*stValue.GetObject())["light_animation"] = JsonValue::Object{ { "keyframes", JsonValue::List{ JsonValue::Object{ { "seconds", 0.0 }, { "multiplier", 1.0 } } } } };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	(*(*stValue.GetObject())["light_animation"].GetObject())["keyframes"].GetList()->front().GetObject()->at("multiplier") = 2.0;
	CheckRejected(stValue);
	(*(*stValue.GetObject())["directional_light"].GetObject())["illuminance"] = 0.0;
	(*(*stValue.GetObject())["light_animation"].GetObject())["keyframes"].GetList()->front().GetObject()->at("multiplier") = std::numeric_limits<double>::max();
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
}

ENGINE_NEXT_TEST("Render configuration supports optional reflection defaults and bounds")
{
	JsonValue stValue = ValidConfiguration();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stConfiguration.stReflections.bEnabled);
	(*stValue.GetObject())["reflections"] = JsonValue::Object{};
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stReflections.dMaxDistance, 100);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stReflections.dThickness, .1);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stReflections.dNormalBias, .02);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stReflections.nMaxSteps, 128U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stReflections.dMaxRoughness, .8);
	(*stValue.GetObject())["reflections"] = JsonValue::Object{ { "enabled", true }, { "max_distance", 1000.0 }, { "thickness", 10.0 }, { "normal_bias", 1.0 }, { "max_steps", std::int64_t{ 256 } }, { "max_roughness", 1.0 } };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stReflections.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stReflections.nMaxSteps, 256U);
	(*stValue.GetObject())["reflections"] = JsonValue::Object{ { "enabled", false }, { "normal_bias", 0.0 }, { "max_steps", std::int64_t{ 8 } } };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
}

ENGINE_NEXT_TEST("Render configuration rejects malformed reflection fields transactionally")
{
	JsonValue stValue = ValidConfiguration();
	for (const JsonValue &stBad : { JsonValue{}, JsonValue(true), JsonValue(1.0), JsonValue("reflection"), JsonValue(JsonValue::List{}), JsonValue(JsonValue::Object{ { "unknown", 1.0 } }) })
	{
		(*stValue.GetObject())["reflections"] = stBad;
		CheckRejected(stValue);
	}
	for (const std::string &strName : { "enabled", "max_distance", "thickness", "normal_bias", "max_steps", "max_roughness" })
	{
		for (const JsonValue &stBad : { JsonValue{}, JsonValue("1"), JsonValue(std::numeric_limits<double>::infinity()) })
		{
			(*stValue.GetObject())["reflections"] = JsonValue::Object{ { strName, stBad } };
			CheckRejected(stValue);
		}
	}
	for (const std::string &strName : { "max_distance", "thickness", "max_roughness" })
	{
		for (double dBad : { 0.0, -1.0, std::numeric_limits<double>::min(), 1001.0 })
		{
			(*stValue.GetObject())["reflections"] = JsonValue::Object{ { strName, dBad } };
			CheckRejected(stValue);
		}
	}
	for (const JsonValue &stBad : { JsonValue(8.0), JsonValue(true), JsonValue(std::int64_t{ 7 }), JsonValue(std::int64_t{ 257 }) })
	{
		(*stValue.GetObject())["reflections"] = JsonValue::Object{ { "max_steps", stBad } };
		CheckRejected(stValue);
	}
	(*stValue.GetObject())["reflections"] = JsonValue::Object{ { "enabled", false }, { "normal_bias", -1.0 } };
	CheckRejected(stValue);
}

ENGINE_NEXT_TEST("Render configuration accepts optional fog and particle emitters")
{
	JsonValue stValue = ValidConfiguration();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stConfiguration.stVolume.bEnabled);
	ENGINE_NEXT_CHECK(stConfiguration.arrParticles.empty());
	(*stValue.GetObject())["volumetric_fog"] = JsonValue::Object{
		{ "enabled", true }, { "density", .03 }, { "local_volumes", JsonValue::List{ JsonValue::Object{ { "shape", "sphere" }, { "entity_id", std::int64_t{ 7 } } } } }
	};
	(*stValue.GetObject())["particles"] =
			JsonValue::List{ JsonValue::Object{ { "emitter_id", std::int64_t{ 9 } }, { "entity_id", std::int64_t{ 7 } }, { "enabled", true } } };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stVolume.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stVolume.dDensity, .03);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stVolume.nLocalVolumeCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stVolume.arrLocalVolumes[0].nEntityId.value_or(0), 7ULL);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrParticles.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrParticles[0].nEmitterId, 9U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.arrParticles[0].nSourceEntityId.value_or(0), 7ULL);
}

ENGINE_NEXT_TEST("Render configuration rejects invalid fog and particle inputs transactionally")
{
	for (const JsonValue &stFog :
		 { JsonValue{}, JsonValue(JsonValue::Object{ { "unknown", true } }), JsonValue(JsonValue::Object{ { "enabled", false }, { "density", -1.0 } }) })
	{
		JsonValue stValue = ValidConfiguration();
		(*stValue.GetObject())["volumetric_fog"] = stFog;
		CheckRejected(stValue);
	}
	for (const JsonValue &stParticles :
		 { JsonValue{}, JsonValue(JsonValue::List{ JsonValue::Object{} }),
		   JsonValue(JsonValue::List{ JsonValue::Object{ { "emitter_id", std::int64_t{ 1 } } }, JsonValue::Object{ { "emitter_id", std::int64_t{ 1 } } } }) })
	{
		JsonValue stValue = ValidConfiguration();
		(*stValue.GetObject())["particles"] = stParticles;
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Render configuration parses source-bound optional material overrides")
{
	JsonValue stValue = ValidConfiguration();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stMaterials.arrOverrides.empty());
	(*stValue.GetObject())["material_overrides"] = JsonValue::List{
		JsonValue::Object{
				{ "asset_id", "material.asset" }, { "material_index", std::int64_t{ 2 } }, { "clearcoat", JsonValue::Object{ { "factor", 0.7 }, { "roughness", 0.2 } } }, { "anisotropy", JsonValue::Object{ { "strength", -0.5 }, { "rotation_radians", 1.2 } } } }
	};
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stMaterials.arrOverrides.size(), 1U);
	const EngineNext::Rendering::MaterialOverride &stOverride = stConfiguration.stMaterials.arrOverrides[0];
	ENGINE_NEXT_CHECK_EQ(stOverride.strAssetId, "material.asset");
	ENGINE_NEXT_CHECK_EQ(stOverride.nMaterialIndex, 2U);
	ENGINE_NEXT_CHECK_EQ(stOverride.stClearcoat.dFactor, 0.7);
	ENGINE_NEXT_CHECK_EQ(stOverride.stClearcoat.dRoughness, 0.2);
	ENGINE_NEXT_CHECK_EQ(stOverride.stAnisotropy.dStrength, -0.5);
	ENGINE_NEXT_CHECK_EQ(stOverride.stAnisotropy.dRotationRadians, 1.2);
	CheckRejected(stValue, std::string(64, 'b'));
	stValue.GetObject()->erase("material_overrides");
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stMaterials.arrOverrides.empty());
}

ENGINE_NEXT_TEST("Render configuration rejects malformed material overrides transactionally")
{
	for (const JsonValue &stBad : {
				 JsonValue{}, JsonValue(true), JsonValue(JsonValue::Object{}),
				 JsonValue(JsonValue::List{ JsonValue::Object{} }),
				 JsonValue(JsonValue::List{ JsonValue::Object{ { "asset_id", "a" }, { "material_index", std::int64_t{ 0 } }, { "clearcoat", JsonValue::Object{ { "factor", 1.1 } } } } }),
				 JsonValue(JsonValue::List{ JsonValue::Object{ { "asset_id", "a" }, { "material_index", std::int64_t{ 0 } }, { "anisotropy", JsonValue::Object{ { "strength", -1.1 } } } } }) })
	{
		JsonValue stValue = ValidConfiguration();
		(*stValue.GetObject())["material_overrides"] = stBad;
		CheckRejected(stValue);
	}
}

ENGINE_NEXT_TEST("Render configuration accepts bounded clipmap global illumination")
{
	JsonValue stValue = ValidConfiguration();
	EngineNext::Rendering::RenderConfiguration stConfiguration;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stConfiguration.stGlobalIllumination.bEnabled);
	(*stValue.GetObject())["global_illumination"] = JsonValue::Object{
		{ "enabled", true }, { "clipmap_levels", std::int64_t{ 2 } }, { "probe_counts", JsonValue::List{ std::int64_t{ 8 }, std::int64_t{ 8 }, std::int64_t{ 8 } } }, { "updates_per_frame", std::int64_t{ 128 } }, { "rays_per_probe", std::int64_t{ 32 } }, { "history_change_threshold", 0.0 }
	};
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(stConfiguration.stGlobalIllumination.bEnabled);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stGlobalIllumination.nClipmapLevels, 2U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stGlobalIllumination.arrProbeCounts, (std::array<std::uint32_t, 3>{ 8, 8, 8 }));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stGlobalIllumination.nUpdatesPerFrame, 128U);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stGlobalIllumination.dHistoryChangeThreshold, 0.0);
	stValue.GetObject()->erase("global_illumination");
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseRenderConfiguration(stValue, strSourceDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stConfiguration.stGlobalIllumination.bEnabled);
}

ENGINE_NEXT_TEST("Render configuration rejects invalid GI even when disabled")
{
	for (const JsonValue &stBad : {
				 JsonValue{}, JsonValue(JsonValue::List{}), JsonValue(true),
				 JsonValue(JsonValue::Object{ { "unrecognized", 1.0 } }),
				 JsonValue(JsonValue::Object{ { "enabled", false }, { "rays_per_probe", std::int64_t{ 0 } } }),
				 JsonValue(JsonValue::Object{ { "enabled", false }, { "probe_counts", JsonValue::List{ std::int64_t{ 1 }, std::int64_t{ 8 }, std::int64_t{ 8 } } } }) })
	{
		JsonValue stValue = ValidConfiguration();
		(*stValue.GetObject())["global_illumination"] = stBad;
		CheckRejected(stValue);
	}
}
