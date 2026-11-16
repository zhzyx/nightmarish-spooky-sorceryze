/**************************************************************************/
/*  RenderConfiguration.cpp                                               */
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

#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include "engine_next/Assets/AssetValidation.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <string>
#include <system_error>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::uintmax_t MAX_CONFIGURATION_BYTES = 64ULL * 1024ULL;
constexpr double MIN_CAMERA_CROSS_SQUARED = 1e-24;

bool Fail(const std::string &strCode, const std::string &strPath, const std::string &strMessage, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::AddDiagnostic(out_arrDiagnostics, strCode, strPath, strMessage);
	return false;
}

bool Vector(const Serialization::JsonValue::Object &mapValue, const std::string &strName, const std::string &strParentPath, std::array<double, 3> &out_arrVector, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::List *pValues = mapValue.find(strName)->second.GetList();
	const std::string strPath = strParentPath + "." + strName;
	if (pValues == nullptr || pValues->size() != out_arrVector.size())
	{
		return Fail("configuration_vector", strPath, "Expected exactly three finite numbers.", out_arrDiagnostics);
	}
	for (std::size_t nIndex = 0; nIndex < out_arrVector.size(); ++nIndex)
	{
		if (!(*pValues)[nIndex].GetNumber(out_arrVector[nIndex]))
		{
			return Fail("configuration_vector", strPath + "[" + std::to_string(nIndex) + "]", "Expected a finite number.", out_arrDiagnostics);
		}
	}
	return true;
}

bool BoundedNumber(const Serialization::JsonValue::Object &mapValue, const std::string &strName, const std::string &strPath, double dMinimum, double dMaximum, double &out_dNumber,
				   Assets::Diagnostics &out_arrDiagnostics)
{
	if (!Assets::Number(mapValue, strName, strPath, out_dNumber, out_arrDiagnostics))
	{
		return false;
	}
	if (out_dNumber < dMinimum || out_dNumber > dMaximum)
	{
		return Fail("range", strPath + "." + strName, "Number is outside the supported range.", out_arrDiagnostics);
	}
	return true;
}

bool Normalize(std::array<double, 3> &arrVector)
{
	const double dMaximum = (std::max)({ std::abs(arrVector[0]), std::abs(arrVector[1]), std::abs(arrVector[2]) });
	if (dMaximum == 0)
	{
		return false;
	}
	double dSquaredLength = 0;
	for (double &dComponent : arrVector)
	{
		dComponent /= dMaximum;
		dSquaredLength += dComponent * dComponent;
	}
	const double dLength = std::sqrt(dSquaredLength);
	for (double &dComponent : arrVector)
	{
		dComponent /= dLength;
	}
	return true;
}

bool CameraBasis(const CameraSettings &stCamera, Assets::Diagnostics &out_arrDiagnostics)
{
	std::array<double, 3> arrDirection{};
	bool bFiniteDifference = true;
	for (std::size_t nIndex = 0; nIndex < arrDirection.size(); ++nIndex)
	{
		arrDirection[nIndex] = stCamera.arrTarget[nIndex] - stCamera.arrPosition[nIndex];
		bFiniteDifference = bFiniteDifference && std::isfinite(arrDirection[nIndex]);
	}
	if (!bFiniteDifference)
	{
		const double dScale = (std::max)({ std::abs(stCamera.arrPosition[0]), std::abs(stCamera.arrPosition[1]), std::abs(stCamera.arrPosition[2]), std::abs(stCamera.arrTarget[0]),
										   std::abs(stCamera.arrTarget[1]), std::abs(stCamera.arrTarget[2]) });
		for (std::size_t nIndex = 0; nIndex < arrDirection.size(); ++nIndex)
		{
			arrDirection[nIndex] = stCamera.arrTarget[nIndex] / dScale - stCamera.arrPosition[nIndex] / dScale;
		}
	}
	std::array<double, 3> arrUp = stCamera.arrUp;
	if (!Normalize(arrDirection) || !Normalize(arrUp))
	{
		return Fail("camera_basis", "$.camera", "Camera direction and up must be nonzero.", out_arrDiagnostics);
	}
	const std::array<double, 3> arrCross{ arrDirection[1] * arrUp[2] - arrDirection[2] * arrUp[1], arrDirection[2] * arrUp[0] - arrDirection[0] * arrUp[2],
										  arrDirection[0] * arrUp[1] - arrDirection[1] * arrUp[0] };
	const double dCrossSquared = arrCross[0] * arrCross[0] + arrCross[1] * arrCross[1] + arrCross[2] * arrCross[2];
	if (dCrossSquared <= MIN_CAMERA_CROSS_SQUARED)
	{
		return Fail("camera_basis", "$.camera.up", "Camera direction and up must be nonparallel.", out_arrDiagnostics);
	}
	return true;
}

bool RootFields(const Serialization::JsonValue::Object &mapRoot, Assets::Diagnostics &out_arrDiagnostics)
{
	Serialization::JsonValue::Object mapFields;
	for (const std::pair<const std::string, Serialization::JsonValue> &stField : mapRoot)
	{
		if (stField.first != "directional_light" && stField.first != "shadows")
		{
			mapFields.emplace(stField.first, Serialization::JsonValue{});
		}
	}
	return Assets::Fields(mapFields, { "schema_version", "source_package_sha256", "camera", "exposure" }, "$", out_arrDiagnostics);
}

bool ParseDirectionalLight(const Serialization::JsonValue &stValue, DirectionalLightSettings &out_stLight, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::string strPath = "$.directional_light";
	const Serialization::JsonValue::Object *pLight = Assets::Object(stValue, strPath, out_arrDiagnostics);
	if (pLight == nullptr || !Assets::Fields(*pLight, { "direction", "color", "illuminance" }, strPath, out_arrDiagnostics))
	{
		return false;
	}
	if (!Vector(*pLight, "direction", strPath, out_stLight.arrDirection, out_arrDiagnostics) ||
		!Vector(*pLight, "color", strPath, out_stLight.arrColor, out_arrDiagnostics) ||
		!BoundedNumber(*pLight, "illuminance", strPath, 0, 1e6, out_stLight.dIlluminance, out_arrDiagnostics))
	{
		return false;
	}
	const std::array<double, 3> &arrDirection = out_stLight.arrDirection;
	if (arrDirection[0] == 0 && arrDirection[1] == 0 && arrDirection[2] == 0)
	{
		return Fail("light_direction", strPath + ".direction", "Light direction must be nonzero.", out_arrDiagnostics);
	}
	for (double dChannel : out_stLight.arrColor)
	{
		if (dChannel < 0 || dChannel > 100)
		{
			return Fail("range", strPath + ".color", "Light color components must be in the range zero to 100.", out_arrDiagnostics);
		}
	}
	return true;
}

bool ParseShadows(const Serialization::JsonValue &stValue, ShadowSettings &out_stShadows, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::string strPath = "$.shadows";
	const Serialization::JsonValue::Object *pShadows = Assets::Object(stValue, strPath, out_arrDiagnostics);
	if (pShadows == nullptr || !Assets::Fields(*pShadows, { "enabled", "resolution", "distance", "split_lambda", "depth_bias", "normal_bias" }, strPath, out_arrDiagnostics))
	{
		return false;
	}
	if (!pShadows->find("enabled")->second.GetBool(out_stShadows.bEnabled))
	{
		return Fail("type", strPath + ".enabled", "Expected a boolean.", out_arrDiagnostics);
	}
	std::int64_t nResolution = 0;
	if (!Assets::Integer(*pShadows, "resolution", strPath, nResolution, out_arrDiagnostics))
	{
		return false;
	}
	if (nResolution != 256 && nResolution != 512 && nResolution != 1024 && nResolution != 2048 && nResolution != 4096)
	{
		return Fail("range", strPath + ".resolution", "Expected shadow resolution 256, 512, 1024, 2048 or 4096.", out_arrDiagnostics);
	}
	out_stShadows.nResolution = static_cast<std::uint32_t>(nResolution);
	return BoundedNumber(*pShadows, "distance", strPath, 0.1, 10000, out_stShadows.dDistance, out_arrDiagnostics) &&
			BoundedNumber(*pShadows, "split_lambda", strPath, 0, 1, out_stShadows.dSplitLambda, out_arrDiagnostics) &&
			BoundedNumber(*pShadows, "depth_bias", strPath, 0, 0.05, out_stShadows.dDepthBias, out_arrDiagnostics) &&
			BoundedNumber(*pShadows, "normal_bias", strPath, 0, 1, out_stShadows.dNormalBias, out_arrDiagnostics);
}

} // namespace

bool ParseRenderConfiguration(const Serialization::JsonValue &stValue, const std::string &strExpectedDigest, RenderConfiguration &out_stConfiguration,
							  Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pRoot = Assets::Object(stValue, "$", out_arrDiagnostics);
	if (pRoot == nullptr || !RootFields(*pRoot, out_arrDiagnostics))
	{
		return false;
	}
	std::int64_t nVersion = 0;
	if (!Assets::Integer(*pRoot, "schema_version", "$", nVersion, out_arrDiagnostics))
	{
		return false;
	}
	if (nVersion != 1)
	{
		return Fail("schema_version", "$.schema_version", "Expected render configuration version 1.", out_arrDiagnostics);
	}
	RenderConfiguration stConfiguration;
	if (!Assets::String(*pRoot, "source_package_sha256", "$", stConfiguration.strSourcePackageDigest, out_arrDiagnostics))
	{
		return false;
	}
	if (!Assets::IsSha256(strExpectedDigest) || !Assets::IsSha256(stConfiguration.strSourcePackageDigest) || stConfiguration.strSourcePackageDigest != strExpectedDigest)
	{
		return Fail("source_package", "$.source_package_sha256", "Expected the loaded source package SHA-256.", out_arrDiagnostics);
	}
	const Serialization::JsonValue::Object *pCamera = Assets::Object(pRoot->find("camera")->second, "$.camera", out_arrDiagnostics);
	if (pCamera == nullptr || !Assets::Fields(*pCamera, { "position", "target", "up", "vertical_fov_degrees", "near_plane", "far_plane" }, "$.camera", out_arrDiagnostics))
	{
		return false;
	}
	CameraSettings &stCamera = stConfiguration.stCamera;
	if (!Vector(*pCamera, "position", "$.camera", stCamera.arrPosition, out_arrDiagnostics) || !Vector(*pCamera, "target", "$.camera", stCamera.arrTarget, out_arrDiagnostics) ||
		!Vector(*pCamera, "up", "$.camera", stCamera.arrUp, out_arrDiagnostics) ||
		!BoundedNumber(*pCamera, "vertical_fov_degrees", "$.camera", 1, 170, stCamera.dVerticalFovDegrees, out_arrDiagnostics) ||
		!BoundedNumber(*pCamera, "near_plane", "$.camera", 0.001, 100, stCamera.dNearPlane, out_arrDiagnostics) ||
		!BoundedNumber(*pCamera, "far_plane", "$.camera", 0.001, 1e7, stCamera.dFarPlane, out_arrDiagnostics) ||
		!BoundedNumber(*pRoot, "exposure", "$", 0.001, 1000, stConfiguration.dExposure, out_arrDiagnostics))
	{
		return false;
	}
	if (stCamera.dFarPlane <= stCamera.dNearPlane)
	{
		return Fail("camera_planes", "$.camera.far_plane", "Far plane must exceed the near plane.", out_arrDiagnostics);
	}
	if (!CameraBasis(stCamera, out_arrDiagnostics))
	{
		return false;
	}
	const Serialization::JsonValue::Object::const_iterator itLight = pRoot->find("directional_light");
	if (itLight != pRoot->end() && !ParseDirectionalLight(itLight->second, stConfiguration.stDirectionalLight, out_arrDiagnostics))
	{
		return false;
	}
	const Serialization::JsonValue::Object::const_iterator itShadows = pRoot->find("shadows");
	if (itShadows != pRoot->end() && !ParseShadows(itShadows->second, stConfiguration.stShadows, out_arrDiagnostics))
	{
		return false;
	}
	out_stConfiguration = std::move(stConfiguration);
	return true;
}

bool LoadRenderConfiguration(const std::filesystem::path &stPath, const std::string &strExpectedDigest, RenderConfiguration &out_stConfiguration,
							 Assets::Diagnostics &out_arrDiagnostics)
{
	std::error_code stError;
	const std::uintmax_t nBytes = std::filesystem::file_size(stPath, stError);
	if (stError || nBytes == 0 || nBytes > MAX_CONFIGURATION_BYTES)
	{
		return Fail("configuration_file", stPath.u8string(), "Expected a readable configuration file of 1 to 65536 bytes.", out_arrDiagnostics);
	}
	std::ifstream stFile(stPath, std::ios::binary);
	std::string strText(static_cast<std::size_t>(nBytes), '\0');
	stFile.read(strText.data(), static_cast<std::streamsize>(nBytes));
	if (!stFile.good() || stFile.peek() != std::char_traits<char>::eof())
	{
		return Fail("configuration_file", stPath.u8string(), "Configuration file could not be read completely.", out_arrDiagnostics);
	}
	Serialization::JsonValue stValue;
	std::string strError;
	if (!Serialization::ParseJson(strText, stValue, strError))
	{
		return Fail("configuration_json", stPath.u8string(), strError, out_arrDiagnostics);
	}
	return ParseRenderConfiguration(stValue, strExpectedDigest, out_stConfiguration, out_arrDiagnostics);
}

} // namespace EngineNext::Rendering
