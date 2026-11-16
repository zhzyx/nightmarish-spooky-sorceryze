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

#include <array>
#include <chrono>
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
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ParseRenderConfiguration(stValue, strExpectedDigest, stConfiguration, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK_EQ(stConfiguration.dExposure, 321.0);
	ENGINE_NEXT_CHECK_EQ(stConfiguration.stCamera.arrPosition, (std::array<double, 3>{ 6, 7, 8 }));
	ENGINE_NEXT_CHECK_EQ(stConfiguration.strSourcePackageDigest, "unchanged");
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
