/**************************************************************************/
/*  ParticleSettings.h                                                    */
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

#include <array>
#include <cstdint>
#include <optional>
#include <vector>

#include "engine_next/include/EngineNext/Serialization/Json.h"

namespace EngineNext::Rendering
{

inline constexpr std::uint32_t MAX_PARTICLES = 4096;
inline constexpr std::uint32_t MAX_PARTICLE_EMITTERS = 16;
inline constexpr std::uint64_t MAX_EXACT_PARTICLE_INDEX = (1ULL << 53) - 1;

struct ParticleSettings
{
	std::uint32_t nEmitterId = 1;
	std::optional<std::uint64_t> nSourceEntityId;
	bool bEnabled = false;
	bool bLoop = true;
	std::uint64_t nSeed = 1;
	double dRate = 16;
	double dLifetime = 2;
	// Used only by one-shot emitters. Birth times occupy [0,dDuration).
	double dDuration = 1;
	std::array<double, 3> arrPosition{ 0, 0, 0 };
	std::array<double, 3> arrPositionSpread{ 0, 0, 0 };
	std::array<double, 3> arrVelocity{ 0, 1, 0 };
	std::array<double, 3> arrVelocitySpread{ 0, 0, 0 };
	double dStartSize = 0.1;
	double dEndSize = 0.1;
	std::array<double, 4> arrStartColor{ 1, 1, 1, 1 };
	std::array<double, 4> arrEndColor{ 1, 1, 1, 0 };
};

// Pure value validation, safe on any thread with exclusive diagnostics.
// Rate is [0,4096] births/second, lifetime [0.001,3600] seconds, and duration
// [0,86400] seconds. ceil(rate*lifetime) must fit MAX_PARTICLES. Local position
// and its spread are bounded by 1e6 world units; velocity and spread by 1e4
// world units/second. Size endpoints are [0,1e4], linear RGBA endpoints [0,1].
// Disabled emitters receive the same input validation. Emitter IDs are positive.
// The optional source entity is resolved by the caller to the current origin.
[[nodiscard]] bool ValidateParticleSettings(const ParticleSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);

// Validates at most sixteen uniquely identified emitters and a combined live
// capacity of 4096, including disabled emitters for deterministic re-enabling.
[[nodiscard]] bool ValidateParticleEmitters(const std::vector<ParticleSettings> &arrEmitters, Assets::Diagnostics &out_arrDiagnostics);
// Parses the optional particles array. Each entry requires emitter_id; all
// other fields use ParticleSettings defaults. Unknown fields fail. entity_id
// uses the positive int64 JSON identity domain. Failure preserves output.
[[nodiscard]] bool ParseParticleEmitters(const Serialization::JsonValue &stValue, std::vector<ParticleSettings> &out_arrEmitters,
										 Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
