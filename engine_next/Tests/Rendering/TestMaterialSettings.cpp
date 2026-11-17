/**************************************************************************/
/*  TestMaterialSettings.cpp                                              */
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
#include "engine_next/include/EngineNext/Rendering/MaterialSettings.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace
{

using EngineNext::Rendering::MaterialOverride;
using EngineNext::Rendering::MaterialSettings;
using EngineNext::Rendering::RenderAsset;
using EngineNext::Rendering::RenderScene;
using EngineNext::Rendering::RuntimeMaterialAsset;
using EngineNext::Serialization::JsonValue;

bool Parse(const std::string &strText, MaterialSettings &out_stSettings, EngineNext::Assets::Diagnostics &out_arrDiagnostics)
{
	JsonValue stValue;
	std::string strError;
	if (!EngineNext::Serialization::ParseJson(strText, stValue, strError))
	{
		EngineNext::Assets::AddDiagnostic(out_arrDiagnostics, "json", "$", strError);
		return false;
	}
	return EngineNext::Rendering::ParseMaterialSettings(stValue, out_stSettings, out_arrDiagnostics);
}

MaterialSettings Settings()
{
	MaterialSettings stSettings;
	MaterialOverride stOverride;
	stOverride.strAssetId = "material.fixture";
	stSettings.arrOverrides.push_back(stOverride);
	return stSettings;
}

RenderScene Scene()
{
	RenderScene stScene;
	RenderAsset stAsset;
	stAsset.stIdentity.strAssetId = "material.fixture";
	stAsset.stIdentity.strRevision = "r1";
	stAsset.stMesh.arrMaterials.resize(2);
	stScene.arrAssets.push_back(stAsset);
	stAsset.stIdentity.strAssetId = "material.second";
	stAsset.stMesh.arrMaterials.resize(1);
	stScene.arrAssets.push_back(stAsset);
	return stScene;
}

void CheckSource(const EngineNext::Rendering::MaterialData &stActual, const EngineNext::Rendering::MaterialData &stExpected)
{
	ENGINE_NEXT_CHECK(stActual.arrBaseColor == stExpected.arrBaseColor);
	ENGINE_NEXT_CHECK_EQ(stActual.fMetallic, stExpected.fMetallic);
	ENGINE_NEXT_CHECK_EQ(stActual.fRoughness, stExpected.fRoughness);
	ENGINE_NEXT_CHECK(stActual.arrEmissive == stExpected.arrEmissive);
	ENGINE_NEXT_CHECK_EQ(stActual.fNormalScale, stExpected.fNormalScale);
	ENGINE_NEXT_CHECK_EQ(stActual.fOcclusionStrength, stExpected.fOcclusionStrength);
	ENGINE_NEXT_CHECK_EQ(stActual.fAlphaCutoff, stExpected.fAlphaCutoff);
	ENGINE_NEXT_CHECK_EQ(stActual.bDoubleSided, stExpected.bDoubleSided);
	ENGINE_NEXT_CHECK(stActual.eAlphaMode == stExpected.eAlphaMode);
	ENGINE_NEXT_CHECK_EQ(stActual.nBaseColorTexture, stExpected.nBaseColorTexture);
	ENGINE_NEXT_CHECK_EQ(stActual.nMetallicRoughnessTexture, stExpected.nMetallicRoughnessTexture);
	ENGINE_NEXT_CHECK_EQ(stActual.nNormalTexture, stExpected.nNormalTexture);
	ENGINE_NEXT_CHECK_EQ(stActual.nOcclusionTexture, stExpected.nOcclusionTexture);
	ENGINE_NEXT_CHECK_EQ(stActual.nEmissiveTexture, stExpected.nEmissiveTexture);
}

} // namespace

ENGINE_NEXT_TEST("Material settings preserve defaults and optional fields")
{
	MaterialSettings stSettings;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(Parse("[]", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSettings.arrOverrides.empty());
	ENGINE_NEXT_CHECK(Parse(R"([{"asset_id":"material.fixture","material_index":0}])", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides.size(), 1U);
	const MaterialOverride &stOverride = stSettings.arrOverrides[0];
	ENGINE_NEXT_CHECK_EQ(stOverride.nMaterialIndex, 0U);
	ENGINE_NEXT_CHECK_EQ(stOverride.stClearcoat.dFactor, 0.0);
	ENGINE_NEXT_CHECK_EQ(stOverride.stClearcoat.dRoughness, 0.1);
	ENGINE_NEXT_CHECK_EQ(stOverride.stAnisotropy.dStrength, 0.0);
	ENGINE_NEXT_CHECK_EQ(stOverride.stAnisotropy.dRotationRadians, 0.0);
	ENGINE_NEXT_CHECK(Parse(R"([{"asset_id":"material.fixture","material_index":1,"clearcoat":{"factor":1},"anisotropy":{"strength":-1}}])", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stClearcoat.dFactor, 1.0);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stClearcoat.dRoughness, 0.1);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stAnisotropy.dStrength, -1.0);
	ENGINE_NEXT_CHECK(Parse(R"([{"asset_id":"material.fixture","material_index":1,"clearcoat":{"factor":0.75,"roughness":0.25},"anisotropy":{"strength":0.5,"rotation_radians":-1.5}}])", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stClearcoat.dFactor, 0.75);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stClearcoat.dRoughness, 0.25);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stAnisotropy.dStrength, 0.5);
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stAnisotropy.dRotationRadians, -1.5);
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Material parsing rejects malformed fields without replacing settings")
{
	for (const char *pText : {
				 "{}", "null", "[null]", "[{}]",
				 R"([{"asset_id":"material.fixture"}])",
				 R"([{"asset_id":1,"material_index":0}])",
				 R"([{"asset_id":"","material_index":0}])",
				 R"([{"asset_id":"material fixture","material_index":0}])",
				 R"([{"asset_id":"material.fixture","material_index":-1}])",
				 R"([{"asset_id":"material.fixture","material_index":true}])",
				 R"([{"asset_id":"material.fixture","material_index":1.0}])",
				 R"([{"asset_id":"material.fixture","material_index":4294967296}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"unknown":0}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"clearcoat":null}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"clearcoat":{"unknown":0}}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"clearcoat":{"factor":true}}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"anisotropy":[]}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"anisotropy":{"rotation_radians":"1"}}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"anisotropy":{"angle":0}}])",
				 R"([{"asset_id":"material.fixture","material_index":0,"material_index":1}])",
				 R"([{"asset_id":"material.fixture","material_index":0},{"asset_id":"material.second","material_index":0,"clearcoat":false}])" })
	{
		MaterialSettings stSettings = Settings();
		stSettings.arrOverrides[0].stClearcoat.dFactor = 0.25;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!Parse(pText, stSettings, arrDiagnostics));
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
		ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides.size(), 1U);
		ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].stClearcoat.dFactor, 0.25);
	}
}

ENGINE_NEXT_TEST("Material numeric boundaries are finite and inclusive")
{
	MaterialSettings stSettings = Settings();
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const double dTwoPi = 6.283185307179586476925286766559;
	for (double dSign : { -1.0, 1.0 })
	{
		stSettings.arrOverrides[0].stClearcoat.dFactor = dSign > 0 ? 1 : 0;
		stSettings.arrOverrides[0].stClearcoat.dRoughness = dSign > 0 ? 0 : 1;
		stSettings.arrOverrides[0].stAnisotropy.dStrength = dSign;
		stSettings.arrOverrides[0].stAnisotropy.dRotationRadians = dSign * dTwoPi;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	}
	for (double dValue : { -0.01, std::nextafter(1.0, 2.0), std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
	{
		stSettings = Settings();
		stSettings.arrOverrides[0].stClearcoat.dFactor = dValue;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
		stSettings = Settings();
		stSettings.arrOverrides[0].stClearcoat.dRoughness = dValue;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	}
	for (double dValue : { std::nextafter(-1.0, -2.0), std::nextafter(1.0, 2.0), std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
	{
		stSettings = Settings();
		stSettings.arrOverrides[0].stAnisotropy.dStrength = dValue;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	}
	for (double dValue : { std::nextafter(-dTwoPi, -10.0), std::nextafter(dTwoPi, 10.0), std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
	{
		stSettings = Settings();
		stSettings.arrOverrides[0].stAnisotropy.dRotationRadians = dValue;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	}
	JsonValue stNonfinite(JsonValue::List{ JsonValue(JsonValue::Object{
			{ "asset_id", JsonValue("material.fixture") },
			{ "material_index", JsonValue(std::int64_t{ 0 }) },
			{ "clearcoat", JsonValue(JsonValue::Object{ { "factor", JsonValue(std::numeric_limits<double>::infinity()) } }) } }) });
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ParseMaterialSettings(stNonfinite, stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Material override identity is unique by asset and material slot")
{
	MaterialSettings stSettings = Settings();
	EngineNext::Assets::Diagnostics arrDiagnostics;
	stSettings.arrOverrides.push_back(stSettings.arrOverrides[0]);
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	stSettings.arrOverrides[1].nMaterialIndex = 1;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	stSettings.arrOverrides[1].strAssetId = "material.second";
	stSettings.arrOverrides[1].nMaterialIndex = 0;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(Parse(R"([{"asset_id":"material.fixture","material_index":4294967295,"clearcoat":{},"anisotropy":{}}])", stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.arrOverrides[0].nMaterialIndex, std::numeric_limits<std::uint32_t>::max());
}

ENGINE_NEXT_TEST("Material resolution preserves all source fields and array order")
{
	RenderScene stScene = Scene();
	EngineNext::Rendering::MaterialData &stSource = stScene.arrAssets[0].stMesh.arrMaterials[1];
	stSource.arrBaseColor = { .2F, .3F, .4F, .5F };
	stSource.fMetallic = .6F;
	stSource.fRoughness = .7F;
	stSource.arrEmissive = { .3F, .1F, .9F };
	stSource.fNormalScale = 1.3F;
	stSource.fOcclusionStrength = .4F;
	stSource.fAlphaCutoff = .6F;
	stSource.bDoubleSided = true;
	stSource.eAlphaMode = EngineNext::Rendering::AlphaMode::Blend;
	stSource.nBaseColorTexture = 4;
	stSource.nMetallicRoughnessTexture = 3;
	stSource.nNormalTexture = 2;
	stSource.nOcclusionTexture = 1;
	stSource.nEmissiveTexture = 0;
	const EngineNext::Rendering::MaterialData stOriginal = stSource;
	MaterialSettings stSettings = Settings();
	stSettings.arrOverrides[0].nMaterialIndex = 1;
	stSettings.arrOverrides[0].stClearcoat.dFactor = .8;
	stSettings.arrOverrides[0].stAnisotropy.dStrength = -.6;
	stSettings.arrOverrides[0].stAnisotropy.dRotationRadians = 1.2;
	std::vector<RuntimeMaterialAsset> arrResolved;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ResolveMaterialSettings(stSettings, stScene, arrResolved, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrResolved.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(arrResolved[0].arrMaterials.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(arrResolved[1].arrMaterials.size(), 1U);
	CheckSource(arrResolved[0].arrMaterials[1].stSource, stOriginal);
	CheckSource(stSource, stOriginal);
	ENGINE_NEXT_CHECK(!arrResolved[0].arrMaterials[0].bOverridden);
	ENGINE_NEXT_CHECK(arrResolved[0].arrMaterials[1].bOverridden);
	ENGINE_NEXT_CHECK_EQ(arrResolved[0].arrMaterials[1].fClearcoatFactor, .8F);
	ENGINE_NEXT_CHECK_EQ(arrResolved[0].arrMaterials[1].fAnisotropyStrength, -.6F);
	ENGINE_NEXT_CHECK_EQ(arrResolved[0].arrMaterials[1].fAnisotropyRotationRadians, 1.2F);
	ENGINE_NEXT_CHECK(!arrResolved[1].arrMaterials[0].bOverridden);
	arrResolved[0].arrMaterials[1].stSource.nBaseColorTexture = 99;
	CheckSource(stSource, stOriginal);
}

ENGINE_NEXT_TEST("Absent and zero material overrides retain legacy source defaults")
{
	const RenderScene stScene = Scene();
	MaterialSettings stSettings;
	std::vector<RuntimeMaterialAsset> arrResolved;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ResolveMaterialSettings(stSettings, stScene, arrResolved, arrDiagnostics));
	CheckSource(arrResolved[0].arrMaterials[0].stSource, stScene.arrAssets[0].stMesh.arrMaterials[0]);
	ENGINE_NEXT_CHECK(!arrResolved[0].arrMaterials[0].bOverridden);
	stSettings = Settings();
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ResolveMaterialSettings(stSettings, stScene, arrResolved, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrResolved[0].arrMaterials[0].bOverridden);
	ENGINE_NEXT_CHECK_EQ(arrResolved[0].arrMaterials[0].fClearcoatFactor, 0.0F);
	ENGINE_NEXT_CHECK_EQ(arrResolved[0].arrMaterials[0].fAnisotropyStrength, 0.0F);
}

ENGINE_NEXT_TEST("Material resolution failures preserve existing runtime materials")
{
	for (std::uint32_t nCase = 0; nCase < 5; ++nCase)
	{
		RenderScene stScene = Scene();
		MaterialSettings stSettings = Settings();
		if (nCase == 0)
		{
			stSettings.arrOverrides[0].strAssetId = "missing.asset";
		}
		if (nCase == 1)
		{
			stSettings.arrOverrides[0].nMaterialIndex = 2;
		}
		if (nCase == 2)
		{
			stSettings.arrOverrides.push_back(stSettings.arrOverrides[0]);
		}
		if (nCase == 3)
		{
			stScene.arrAssets[1].stIdentity.strAssetId = "material.fixture";
			stScene.arrAssets[1].stIdentity.strRevision = "r2";
		}
		if (nCase == 4)
		{
			MaterialOverride stLater = stSettings.arrOverrides[0];
			stLater.nMaterialIndex = 99;
			stSettings.arrOverrides.push_back(stLater);
		}
		std::vector<RuntimeMaterialAsset> arrResolved(1);
		arrResolved[0].arrMaterials.resize(1);
		arrResolved[0].arrMaterials[0].fClearcoatFactor = .123F;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ResolveMaterialSettings(stSettings, stScene, arrResolved, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(arrResolved.size(), 1U);
		ENGINE_NEXT_CHECK_EQ(arrResolved[0].arrMaterials[0].fClearcoatFactor, .123F);
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	}
}

ENGINE_NEXT_TEST("Material direct API validates large unique target arrays")
{
	MaterialSettings stSettings;
	for (std::uint32_t nIndex = 0; nIndex < 4100; ++nIndex)
	{
		MaterialOverride stOverride;
		stOverride.strAssetId = "material.fixture";
		stOverride.nMaterialIndex = nIndex;
		stSettings.arrOverrides.push_back(stOverride);
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateMaterialSettings(stSettings, arrDiagnostics));
	std::vector<RuntimeMaterialAsset> arrResolved(1);
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ResolveMaterialSettings(MaterialSettings{}, RenderScene{}, arrResolved, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrResolved.empty());
}

ENGINE_NEXT_TEST("Material runtime parameters match GPU subnormal handling")
{
	const double dMinimum = std::numeric_limits<float>::min();
	const double dBelow = std::nextafter(std::numeric_limits<float>::min(), 0.0F);
	const double dAbove = std::nextafter(std::numeric_limits<float>::min(), 1.0F);
	const RenderScene stScene = Scene();
	for (double dValue : { std::numeric_limits<double>::min(), dBelow, dMinimum, dAbove })
	{
		for (double dSign : { -1.0, 1.0 })
		{
			MaterialSettings stSettings = Settings();
			MaterialOverride &stOverride = stSettings.arrOverrides[0];
			stOverride.stClearcoat.dFactor = dValue;
			stOverride.stClearcoat.dRoughness = dValue;
			stOverride.stAnisotropy.dStrength = dSign * dValue;
			stOverride.stAnisotropy.dRotationRadians = dSign * dValue;
			std::vector<RuntimeMaterialAsset> arrResolved;
			EngineNext::Assets::Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(EngineNext::Rendering::ResolveMaterialSettings(stSettings, stScene, arrResolved, arrDiagnostics));
			const EngineNext::Rendering::RuntimeMaterial &stRuntime = arrResolved[0].arrMaterials[0];
			const float fExpected = dValue < dMinimum ? 0.0F : static_cast<float>(dValue);
			ENGINE_NEXT_CHECK_EQ(stRuntime.fClearcoatFactor, fExpected);
			ENGINE_NEXT_CHECK_EQ(stRuntime.fClearcoatRoughness, fExpected);
			ENGINE_NEXT_CHECK_EQ(stRuntime.fAnisotropyStrength, dSign * fExpected);
			ENGINE_NEXT_CHECK_EQ(stRuntime.fAnisotropyRotationRadians, dSign * fExpected);
			ENGINE_NEXT_CHECK_EQ(stOverride.stClearcoat.dFactor, dValue);
			ENGINE_NEXT_CHECK_EQ(stOverride.stAnisotropy.dStrength, dSign * dValue);
		}
	}
}
