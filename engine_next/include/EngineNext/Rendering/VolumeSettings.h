/**************************************************************************/
/*  VolumeSettings.h                                                      */
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
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <array>
#include <cstdint>
#include <optional>

namespace EngineNext::Rendering
{

inline constexpr std::uint32_t MAX_LOCAL_VOLUMES = 16;
inline constexpr std::uint64_t MAX_VOLUME_FROXELS = 8ULL * 1024 * 1024;
inline constexpr double MAX_VOLUME_COEFFICIENT = 65504;

enum class LocalVolumeShape : std::uint8_t
{
	Box = 0,
	Sphere = 1,
};

struct LocalVolumeSettings
{
	LocalVolumeShape eShape = LocalVolumeShape::Box;
	std::array<double, 3> arrCenter{ 0, 0, 0 };
	// Axis-aligned box half-extents, or three identical sphere radii.
	std::array<double, 3> arrExtent{ 1, 1, 1 };
	std::optional<std::uint64_t> nEntityId;
	double dDensity = 0.01;
	std::array<double, 3> arrAlbedo{ 0.9, 0.9, 0.9 };
	std::array<double, 3> arrEmission{ 0, 0, 0 };
	double dEdgeFraction = 0.1;
};

struct VolumeSettings
{
	bool bEnabled = false;
	double dDistance = 100;
	std::uint32_t nCellPixels = 16;
	std::uint32_t nDepthSlices = 64;
	double dDensity = 0.01;
	double dHeight = 0;
	double dHeightFalloff = 0.1;
	std::array<double, 3> arrAlbedo{ 0.9, 0.9, 0.9 };
	std::array<double, 3> arrEmission{ 0, 0, 0 };
	double dPhaseG = 0.2;
	double dHistoryWeight = 0.85;
	std::uint32_t nLocalVolumeCount = 0;
	std::array<LocalVolumeSettings, MAX_LOCAL_VOLUMES> arrLocalVolumes{};
};

// Value-only settings. Validation never mutates inputs and can run on any thread
// with exclusive diagnostic access. Disabled settings receive the same checks.
// Distance and local extents must survive binary32 conversion as normal values.
// Each world bound must remain distinct from its center in binary32.
// Nonzero density, emission and falloff must remain normal binary32 values.
// Accumulated medium coefficients use explicit [0,65504] saturation in GPU math.
// Albedo is [0,1], g is [-0.95,0.95], history is [0,0.99].
// Cell sizes are 8/16/32 and slice counts 32/64/96/128. Local entity IDs, when
// present, are positive. Entity lookup and resolved world centers remain owned
// by the caller; the optional ID does not alter these world-space value fields.
[[nodiscard]] bool ValidateVolumeSettings(const VolumeSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);

// Parses the contents of the optional volumetric_fog object. All recognized
// fields are optional and omissions restore defaults. Unknown fields, malformed
// vectors, unsupported local shapes and invalid values fail transactionally.
// entity_id uses the positive int64 JSON domain of existing M3 entities and is
// stored without precision loss in the optional uint64 member.
[[nodiscard]] bool ParseVolumeSettings(const Serialization::JsonValue &stValue, VolumeSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
