/**************************************************************************/
/*  EnvironmentImportance.h                                               */
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

#include "engine_next/Rendering/Cook/EnvironmentLighting.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

constexpr std::uint32_t ENVIRONMENT_UNIFORM_FALLBACK = 1;
constexpr std::uint32_t ENVIRONMENT_SIZE_SHIFT = 1;

struct alignas(16) EnvironmentAliasEntry
{
	float fThreshold = 1.0F;
	std::uint32_t nAlias = 0;
	float fPmf = 0.0F;
	// Face size in bits 1..31, uniform-sphere fallback in bit 0.
	std::uint32_t nMetadata = 0;
};
static_assert(sizeof(EnvironmentAliasEntry) == 16);
static_assert(offsetof(EnvironmentAliasEntry, nAlias) == 4);
static_assert(offsetof(EnvironmentAliasEntry, fPmf) == 8);
static_assert(offsetof(EnvironmentAliasEntry, nMetadata) == 12);

struct EnvironmentImportance
{
	std::uint32_t nFaceSize = 0;
	bool bUniformFallback = true;
	double dIntegratedLuminance = 0;
	std::vector<EnvironmentAliasEntry> arrEntries;
};

[[nodiscard]] double EnvironmentTexelSolidAngle(std::uint32_t nX, std::uint32_t nY, std::uint32_t nFaceSize) noexcept;

// Six square faces follow the existing +X,-X,+Y,-Y,+Z,-Z convention. Alpha is
// ignored; RGB must be finite and negative channels contribute zero energy.
// Output is transactional. Entry count is bounded by exact float indexing.
[[nodiscard]] bool BuildEnvironmentImportance(const std::array<FloatImage, 6> &arrFaces, EnvironmentImportance &out_stImportance, std::string &out_strError);

} // namespace EngineNext::Rendering
