/**************************************************************************/
/*  MaterialSettings.h                                                    */
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
#include "engine_next/include/EngineNext/Rendering/MeshData.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

struct RenderScene;

struct ClearcoatSettings
{
	double dFactor = 0.0;
	double dRoughness = 0.1;
};

struct AnisotropySettings
{
	double dStrength = 0.0;
	double dRotationRadians = 0.0;
};

struct MaterialOverride
{
	std::string strAssetId;
	std::uint32_t nMaterialIndex = 0;
	ClearcoatSettings stClearcoat;
	AnisotropySettings stAnisotropy;
};

struct MaterialSettings
{
	std::vector<MaterialOverride> arrOverrides;
};

struct RuntimeMaterial
{
	MaterialData stSource;
	float fClearcoatFactor = 0.0F;
	float fClearcoatRoughness = 0.1F;
	float fAnisotropyStrength = 0.0F;
	float fAnisotropyRotationRadians = 0.0F;
	bool bOverridden = false;
};

struct RuntimeMaterialAsset
{
	// Entries retain the source asset's material order, including unused slots.
	std::vector<RuntimeMaterial> arrMaterials;
};

[[nodiscard]] bool ValidateMaterialSettings(const MaterialSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);

// Parses the material_overrides array. Its enclosing render configuration owns
// the package digest and file-size limit. Missing optional fields use defaults.
// Failure appends diagnostics and preserves the output settings.
[[nodiscard]] bool ParseMaterialSettings(const Serialization::JsonValue &stValue, MaterialSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics);

// Pure CPU resolution. Asset and material order match stScene; source data is
// copied unchanged. An ambiguous asset ID or missing target fails atomically.
// Zero lobe strengths preserve the existing BRDF even for explicit overrides.
// Runtime binary32 subnormal parameters become zero to match shader arithmetic;
// the original double-precision settings remain unchanged.
[[nodiscard]] bool ResolveMaterialSettings(const MaterialSettings &stSettings, const RenderScene &stScene, std::vector<RuntimeMaterialAsset> &out_arrMaterials, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
