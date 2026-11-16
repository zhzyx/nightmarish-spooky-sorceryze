/**************************************************************************/
/*  EnvironmentLighting.h                                                 */
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

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

struct FloatImage
{
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::vector<std::array<float, 4>> arrPixels;
};

struct EnvironmentConfig
{
	std::uint32_t nEnvironmentSize = 64;
	std::uint32_t nIrradianceSize = 32;
	std::uint32_t nBrdfSize = 64;
	std::uint32_t nSampleCount = 128;
	std::array<float, 3> arrSkyZenith{ 0.25F, 0.5F, 1.5F };
	std::array<float, 3> arrSkyHorizon{ 1.0F, 1.2F, 1.5F };
	std::array<float, 3> arrGround{ 0.08F, 0.06F, 0.04F };
	std::array<float, 3> arrSunDirection{ 0.4F, 0.8F, 0.4F };
	std::array<float, 3> arrSunRadiance{ 30.0F, 25.0F, 20.0F };
	float fSunAngularRadius = 0.08F;
};

struct EnvironmentLighting
{
	// Direct3D cube face order +X, -X, +Y, -Y, +Z, -Z. Rows start at v=0.
	std::array<FloatImage, 6> arrEnvironment;
	// Irradiance stores integral L*cos(theta)*dOmega; Lambert BRDF divides by PI.
	std::array<FloatImage, 6> arrIrradiance;
	std::vector<std::array<FloatImage, 6>> arrPrefilteredMips;
	// LUT coordinates are NdotV (x), perceptual roughness (y), channels A/B.
	FloatImage stBrdfLut;
};

// Deterministic CPU preprocessing of linear HDR radiance. No file, GPU or
// platform dependencies. Failed validation leaves the prior output unchanged.
[[nodiscard]] bool GenerateEnvironmentLighting(const EnvironmentConfig &stConfig, EnvironmentLighting &out_stLighting, std::string &out_strError);

} // namespace EngineNext::Rendering
