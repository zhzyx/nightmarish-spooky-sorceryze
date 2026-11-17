/**************************************************************************/
/*  ParticleState.h                                                       */
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

#include "engine_next/include/EngineNext/Rendering/ParticleSettings.h"

#include <array>
#include <cstdint>

namespace EngineNext::Rendering
{

struct ParticleId
{
	std::uint32_t nEmitterId = 0;
	std::uint64_t nSeed = 0;
	std::uint64_t nSpawnIndex = 0;
};

struct BillboardInstance
{
	ParticleId stId;
	std::array<double, 3> arrCenter{};
	double dSize = 0;
	std::array<double, 4> arrColor{};
	double dAge = 0;
};

struct ParticleFrame
{
	std::uint32_t nCount = 0;
	std::array<BillboardInstance, MAX_PARTICLES> arrInstances{};
};

// Stateless analytical evaluation. Birth index i has represented time i/rate.
// At most K recent births are candidates, where K is the ceiling of normalized
// rate*lifetime (and at least one for positive rates). Scheduled i/rate times
// normalize to integer phase while nextafter neighbors retain their side.
// Death is the earlier of birth+lifetime and birth(i+K), with the latter used
// only inside the exact index domain. This canonical deadline prevents rounded
// addition from extending life into more than K birth slots. Age is [0,lifetime).
// If positive lifetime addition rounds to birth, expiry advances to the next
// representable timestamp so the exact birth remains present with age zero.
// Loop means continuous births; one-shot stops births at duration and lets the
// existing particles expire. The duration endpoint uses its represented birth
// boundary side independently of lifetime-slot normalization. Seek/replay never
// depends on preceding calls.
// Position is caller origin + local spawn offset + velocity*age. Current origin
// moves the whole emitter and its live particles; there is no hidden entity or
// world-at-birth history. Instances are ordered by increasing spawn index.
// Emitter ID, seed and birth index identify one configured particle.
// The caller resolves source entity transforms into the current origin.
// Time is finite and nonnegative. Continuous-emission evaluation fails once
// rate*time exceeds MAX_EXACT_PARTICLE_INDEX, retaining exact binary64 indices.
// Candidate births and the immediate scheduled neighbors must have distinct
// binary64 times. The next neighbor is checked only inside the exact index domain.
// Finished one-shots and zero-rate emitters support any finite nonnegative time.
// World centers must fit finite binary32. Failure preserves the output frame.
// Pure CPU operation callable with immutable inputs and exclusive output access.
[[nodiscard]] bool EvaluateParticles(const ParticleSettings &stSettings, double dSeconds, const std::array<double, 3> &arrOrigin, ParticleFrame &out_stFrame,
									 Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
