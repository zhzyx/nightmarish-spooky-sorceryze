/**************************************************************************/
/*  RenderConfiguration.h                                                 */
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

#include "engine_next/include/EngineNext/Assets/Types.h"
#include "engine_next/include/EngineNext/Rendering/PostProcessSettings.h"
#include "engine_next/include/EngineNext/Rendering/LightTimeline.h"
#include "engine_next/include/EngineNext/Rendering/ReflectionSettings.h"
#include "engine_next/include/EngineNext/Rendering/VolumeSettings.h"
#include "engine_next/include/EngineNext/Rendering/ParticleSettings.h"
#include "engine_next/include/EngineNext/Rendering/MaterialSettings.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

struct CameraSettings
{
	std::array<double, 3> arrPosition{ 0, 0, 5 };
	std::array<double, 3> arrTarget{ 0, 0, 0 };
	std::array<double, 3> arrUp{ 0, 1, 0 };
	double dVerticalFovDegrees = 50;
	double dNearPlane = 0.05;
	double dFarPlane = 1000;
};

struct DirectionalLightSettings
{
	// World-space direction in which the light rays travel.
	std::array<double, 3> arrDirection{ 0.5, -0.8, -0.6 };
	std::array<double, 3> arrColor{ 1, 0.9666667, 0.9 };
	double dIlluminance = 3;
};

struct PointLightSettings
{
	std::uint32_t nId = 1;
	std::array<double, 3> arrPosition{ 2, 3, 2 };
	std::array<double, 3> arrColor{ 1, 0.6666667, 0.4444444 };
	double dLumens = 226.194671;
	double dRange = 25;
	bool bCastsShadow = true;
};

struct SpotLightSettings
{
	std::uint32_t nId = 1;
	std::array<double, 3> arrPosition{ 2, 3, 2 };
	std::array<double, 3> arrColor{ 1, 0.6666667, 0.4444444 };
	std::array<double, 3> arrDirection{ 0, -1, 0 };
	double dLumens = 226.194671;
	double dRange = 25;
	bool bCastsShadow = true;
	double dInnerAngleDegrees = 20;
	double dOuterAngleDegrees = 35;
};

enum class ShadowFilter : std::uint8_t
{
	Pcf = 0,
	Pcss = 1,
};

struct ShadowSettings
{
	bool bEnabled = true;
	std::uint32_t nResolution = 2048;
	double dDistance = 50;
	double dSplitLambda = 0.6;
	double dDepthBias = 0.0005;
	double dNormalBias = 0.01;
	std::uint32_t nLocalResolution = 1024;
	ShadowFilter eFilter = ShadowFilter::Pcf;
	double dLightRadius = 0.1;
};

struct TemporalSettings
{
	bool bEnabled = true;
	double dHistoryWeight = 0.9;
	double dDepthThreshold = 0.01;
};

struct RenderConfiguration
{
	CameraSettings stCamera;
	DirectionalLightSettings stDirectionalLight;
	ShadowSettings stShadows;
	TemporalSettings stTemporal;
	ExposureSettings stExposure;
	BloomSettings stBloom;
	LightAnimationSettings stLightAnimation;
	ReflectionSettings stReflections;
	VolumeSettings stVolume;
	std::vector<ParticleSettings> arrParticles;
	MaterialSettings stMaterials;
	std::vector<PointLightSettings> arrPointLights{ PointLightSettings{} };
	std::vector<SpotLightSettings> arrSpotLights;
	double dExposure = 1;
	std::string strSourcePackageDigest;
};

// Integrates the spotlight's unit-peak angular falloff over solid angle.
// The falloff is one inside the inner cone and falls to zero with smoothstep
// in squared chord length between the inner and outer cones. Angles are degrees,
// output is steradians. The supported angle ranges match SpotLightSettings.
// Invalid or unrepresentable results leave the output unchanged. This pure
// calculation is callable on any thread with exclusive output access.
[[nodiscard]] bool ComputeSpotSolidAngle(double dInnerAngleDegrees, double dOuterAngleDegrees, double &out_dSteradians) noexcept;

// Camera vectors must be finite with nonzero direction and up. Their normalized
// cross product squared must exceed 1e-24. FOV is [1, 170] degrees, near is
// [0.001, 100], and near < far <= 1e7. Exposure is a multiplier in [0.001, 1000].
// Optional lighting and shadow objects use defaults when absent. Explicit empty
// point_lights or spot_lights arrays disable that light type. Each has at most
// four entries with positive IDs unique across both arrays.
// Light colors are [0, 100], directional illuminance [0, 1e6], local lumens
// [0, 1e8], local range [0.1, 10000], and directions are finite and nonzero.
// Spot angles satisfy 0 <= inner <= 85 and inner < outer <= 89 degrees.
// Optional temporal_aa uses defaults when absent. Its history weight is [0, 0.99]
// and relative depth threshold is [0.0001, 0.25], including when disabled.
// Optional exposure_settings and bloom fields use PostProcessSettings defaults.
// Numeric exposure remains required and supplies the legacy-mode multiplier.
// Optional light_animation applies its timeline to directional illuminance.
// Its omitted fields default to an empty, non-looping linear track.
// Optional reflections uses disabled ReflectionSettings defaults when absent.
// Optional volumetric_fog uses disabled VolumeSettings defaults. Optional
// particles has at most sixteen uniquely identified emitters and 4096 combined
// live particles, including disabled emitters.
// Optional material_overrides selects source asset IDs and material indices.
// Source existence is resolved against the loaded scene before GPU allocation.
// Both functions append diagnostics and leave the output unchanged on failure.
[[nodiscard]] bool ParseRenderConfiguration(const Serialization::JsonValue &stValue, const std::string &strExpectedDigest, RenderConfiguration &out_stConfiguration,
											Assets::Diagnostics &out_arrDiagnostics);
// Reads at most 65536 bytes of strict UTF-8 JSON and rejects duplicate keys.
[[nodiscard]] bool LoadRenderConfiguration(const std::filesystem::path &stPath, const std::string &strExpectedDigest, RenderConfiguration &out_stConfiguration,
										   Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
