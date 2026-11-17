/**************************************************************************/
/*  MaterialSettings.cpp                                                  */
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

#include "engine_next/include/EngineNext/Rendering/MaterialSettings.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"

#include <cmath>
#include <cstddef>
#include <initializer_list>
#include <limits>
#include <map>
#include <set>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

constexpr double TWO_PI = 6.283185307179586476925286766559;

bool Error(Assets::Diagnostics &out_arrDiagnostics, const std::string &strPath, const std::string &strMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "material_settings", strPath, strMessage);
	return false;
}

bool Fields(const Serialization::JsonValue::Object &mapValue, std::initializer_list<const char *> arrAllowed, const std::string &strPath, Assets::Diagnostics &out_arrDiagnostics)
{
	for (const std::pair<const std::string, Serialization::JsonValue> &stField : mapValue)
	{
		bool bKnown = false;
		for (const char *pName : arrAllowed)
		{
			bKnown = bKnown || stField.first == pName;
		}
		if (!bKnown)
		{
			return Error(out_arrDiagnostics, strPath + "." + stField.first, "Unknown material field.");
		}
	}
	return true;
}

bool OptionalNumber(const Serialization::JsonValue::Object &mapValue, const char *pName, double &out_dValue, const std::string &strPath, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator itValue = mapValue.find(pName);
	if (itValue == mapValue.end())
	{
		return true;
	}
	if (!itValue->second.GetNumber(out_dValue) || !std::isfinite(out_dValue))
	{
		return Error(out_arrDiagnostics, strPath + "." + pName, "Expected a finite number.");
	}
	return true;
}

bool ParseOverride(const Serialization::JsonValue &stValue, const std::string &strPath, MaterialOverride &out_stOverride, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = stValue.GetObject();
	if (pObject == nullptr)
	{
		return Error(out_arrDiagnostics, strPath, "Expected a material override object.");
	}
	if (!Fields(*pObject, { "asset_id", "material_index", "clearcoat", "anisotropy" }, strPath, out_arrDiagnostics))
	{
		return false;
	}
	const Serialization::JsonValue::Object::const_iterator itAsset = pObject->find("asset_id");
	const Serialization::JsonValue::Object::const_iterator itIndex = pObject->find("material_index");
	if (itAsset == pObject->end() || itAsset->second.GetString() == nullptr)
	{
		return Error(out_arrDiagnostics, strPath + ".asset_id", "Expected an asset identity string.");
	}
	std::int64_t nIndex = 0;
	if (itIndex == pObject->end() || !itIndex->second.GetInteger(nIndex) || nIndex < 0 ||
		static_cast<std::uint64_t>(nIndex) > std::numeric_limits<std::uint32_t>::max())
	{
		return Error(out_arrDiagnostics, strPath + ".material_index", "Expected a zero-based unsigned 32-bit material index.");
	}
	out_stOverride.strAssetId = *itAsset->second.GetString();
	out_stOverride.nMaterialIndex = static_cast<std::uint32_t>(nIndex);
	const Serialization::JsonValue::Object::const_iterator itCoat = pObject->find("clearcoat");
	if (itCoat != pObject->end())
	{
		const Serialization::JsonValue::Object *pCoat = itCoat->second.GetObject();
		if (pCoat == nullptr)
		{
			return Error(out_arrDiagnostics, strPath + ".clearcoat", "Expected a clearcoat object.");
		}
		if (!Fields(*pCoat, { "factor", "roughness" }, strPath + ".clearcoat", out_arrDiagnostics) ||
			!OptionalNumber(*pCoat, "factor", out_stOverride.stClearcoat.dFactor, strPath + ".clearcoat", out_arrDiagnostics) ||
			!OptionalNumber(*pCoat, "roughness", out_stOverride.stClearcoat.dRoughness, strPath + ".clearcoat", out_arrDiagnostics))
		{
			return false;
		}
	}
	const Serialization::JsonValue::Object::const_iterator itAnisotropy = pObject->find("anisotropy");
	if (itAnisotropy != pObject->end())
	{
		const Serialization::JsonValue::Object *pAnisotropy = itAnisotropy->second.GetObject();
		if (pAnisotropy == nullptr)
		{
			return Error(out_arrDiagnostics, strPath + ".anisotropy", "Expected an anisotropy object.");
		}
		if (!Fields(*pAnisotropy, { "strength", "rotation_radians" }, strPath + ".anisotropy", out_arrDiagnostics) ||
			!OptionalNumber(*pAnisotropy, "strength", out_stOverride.stAnisotropy.dStrength, strPath + ".anisotropy", out_arrDiagnostics) ||
			!OptionalNumber(*pAnisotropy, "rotation_radians", out_stOverride.stAnisotropy.dRotationRadians, strPath + ".anisotropy", out_arrDiagnostics))
		{
			return false;
		}
	}
	return true;
}

bool InRange(double dValue, double dMinimum, double dMaximum) noexcept
{
	return std::isfinite(dValue) && dValue >= dMinimum && dValue <= dMaximum;
}

float GpuParameter(double dValue) noexcept
{
	const float fValue = static_cast<float>(dValue);
	// Shader arithmetic flushes binary32 subnormal values to zero.
	return std::abs(fValue) < std::numeric_limits<float>::min() ? 0.0F : fValue;
}

} // namespace

bool ValidateMaterialSettings(const MaterialSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	std::set<std::pair<std::string, std::uint32_t>> setTargets;
	for (std::size_t nIndex = 0; nIndex < stSettings.arrOverrides.size(); ++nIndex)
	{
		const MaterialOverride &stOverride = stSettings.arrOverrides[nIndex];
		const std::string strPath = "$.material_overrides[" + std::to_string(nIndex) + "]";
		if (!Assets::IsIdentity(stOverride.strAssetId))
		{
			return Error(out_arrDiagnostics, strPath + ".asset_id", "Invalid asset identity.");
		}
		if (!setTargets.emplace(stOverride.strAssetId, stOverride.nMaterialIndex).second)
		{
			return Error(out_arrDiagnostics, strPath, "The asset and material index already have an override.");
		}
		if (!InRange(stOverride.stClearcoat.dFactor, 0, 1) || !InRange(stOverride.stClearcoat.dRoughness, 0, 1))
		{
			return Error(out_arrDiagnostics, strPath + ".clearcoat", "Clearcoat factor and roughness must be finite values in [0,1].");
		}
		if (!InRange(stOverride.stAnisotropy.dStrength, -1, 1) || !InRange(stOverride.stAnisotropy.dRotationRadians, -TWO_PI, TWO_PI))
		{
			return Error(out_arrDiagnostics, strPath + ".anisotropy", "Anisotropy strength must be in [-1,1] and rotation in [-2*pi,2*pi] radians.");
		}
	}
	return true;
}

bool ParseMaterialSettings(const Serialization::JsonValue &stValue, MaterialSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::List *pValues = stValue.GetList();
	if (pValues == nullptr)
	{
		return Error(out_arrDiagnostics, "$.material_overrides", "Expected a material override array.");
	}
	MaterialSettings stCandidate;
	stCandidate.arrOverrides.reserve(pValues->size());
	for (std::size_t nIndex = 0; nIndex < pValues->size(); ++nIndex)
	{
		MaterialOverride stOverride;
		if (!ParseOverride((*pValues)[nIndex], "$.material_overrides[" + std::to_string(nIndex) + "]", stOverride, out_arrDiagnostics))
		{
			return false;
		}
		stCandidate.arrOverrides.push_back(std::move(stOverride));
	}
	if (!ValidateMaterialSettings(stCandidate, out_arrDiagnostics))
	{
		return false;
	}
	out_stSettings = std::move(stCandidate);
	return true;
}

bool ResolveMaterialSettings(const MaterialSettings &stSettings, const RenderScene &stScene, std::vector<RuntimeMaterialAsset> &out_arrMaterials, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateMaterialSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	std::map<std::string, std::size_t> mapAssets;
	std::vector<RuntimeMaterialAsset> arrCandidate;
	arrCandidate.reserve(stScene.arrAssets.size());
	for (std::size_t nAsset = 0; nAsset < stScene.arrAssets.size(); ++nAsset)
	{
		const RenderAsset &stAsset = stScene.arrAssets[nAsset];
		const std::pair<std::map<std::string, std::size_t>::iterator, bool> stInserted = mapAssets.emplace(stAsset.stIdentity.strAssetId, nAsset);
		if (!stInserted.second)
		{
			stInserted.first->second = std::numeric_limits<std::size_t>::max();
		}
		RuntimeMaterialAsset stMaterials;
		stMaterials.arrMaterials.reserve(stAsset.stMesh.arrMaterials.size());
		for (const MaterialData &stSource : stAsset.stMesh.arrMaterials)
		{
			RuntimeMaterial stMaterial;
			stMaterial.stSource = stSource;
			stMaterials.arrMaterials.push_back(stMaterial);
		}
		arrCandidate.push_back(std::move(stMaterials));
	}
	for (const MaterialOverride &stOverride : stSettings.arrOverrides)
	{
		const std::map<std::string, std::size_t>::const_iterator itAsset = mapAssets.find(stOverride.strAssetId);
		if (itAsset == mapAssets.end() || itAsset->second == std::numeric_limits<std::size_t>::max())
		{
			return Error(out_arrDiagnostics, "$.material_overrides", "Override asset ID is missing or ambiguous in the source scene.");
		}
		std::vector<RuntimeMaterial> &arrMaterials = arrCandidate[itAsset->second].arrMaterials;
		if (stOverride.nMaterialIndex >= arrMaterials.size())
		{
			return Error(out_arrDiagnostics, "$.material_overrides", "Override material index is outside the source material array.");
		}
		RuntimeMaterial &stMaterial = arrMaterials[stOverride.nMaterialIndex];
		stMaterial.fClearcoatFactor = GpuParameter(stOverride.stClearcoat.dFactor);
		stMaterial.fClearcoatRoughness = GpuParameter(stOverride.stClearcoat.dRoughness);
		stMaterial.fAnisotropyStrength = GpuParameter(stOverride.stAnisotropy.dStrength);
		stMaterial.fAnisotropyRotationRadians = GpuParameter(stOverride.stAnisotropy.dRotationRadians);
		stMaterial.bOverridden = true;
	}
	out_arrMaterials = std::move(arrCandidate);
	return true;
}

} // namespace EngineNext::Rendering
