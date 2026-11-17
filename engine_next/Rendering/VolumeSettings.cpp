/**************************************************************************/
/*  VolumeSettings.cpp                                                    */
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

#include "engine_next/include/EngineNext/Rendering/VolumeSettings.h"

#include "engine_next/Assets/AssetValidation.h"

#include <cmath>
#include <cstddef>
#include <limits>
#include <initializer_list>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

bool InRange(double dValue, double dMinimum, double dMaximum) noexcept
{
	return std::isfinite(dValue) && dValue >= dMinimum && dValue <= dMaximum;
}

bool GpuCoordinate(double dValue) noexcept
{
	return InRange(dValue, -std::numeric_limits<float>::max(), std::numeric_limits<float>::max());
}

bool GpuCoefficient(double dValue) noexcept
{
	return InRange(dValue, 0, MAX_VOLUME_COEFFICIENT) && (dValue == 0 || dValue >= std::numeric_limits<float>::min());
}

bool MediumValues(double dDensity, const std::array<double, 3> &arrAlbedo, const std::array<double, 3> &arrEmission) noexcept
{
	if (!GpuCoefficient(dDensity))
	{
		return false;
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!InRange(arrAlbedo[nAxis], 0, 1) || !GpuCoefficient(arrEmission[nAxis]))
		{
			return false;
		}
	}
	return true;
}

bool OptionalFields(const Serialization::JsonValue::Object &mapValue, std::initializer_list<const char *> arrAllowed, const std::string &strPath,
					Assets::Diagnostics &out_arrDiagnostics)
{
	// Reuse Assets::Fields for its unknown-field diagnostic while supplying
	// defaults for allowed optional keys solely in this small validation map.
	Serialization::JsonValue::Object mapFields;
	for (const char *pName : arrAllowed)
	{
		mapFields.emplace(pName, Serialization::JsonValue{});
	}
	for (const std::pair<const std::string, Serialization::JsonValue> &stField : mapValue)
	{
		mapFields.emplace(stField.first, Serialization::JsonValue{});
	}
	return Assets::Fields(mapFields, arrAllowed, strPath, out_arrDiagnostics);
}

bool OptionalNumber(const Serialization::JsonValue::Object &mapValue, const char *pName, const std::string &strPath, double &out_dValue,
					Assets::Diagnostics &out_arrDiagnostics)
{
	return mapValue.find(pName) == mapValue.end() || Assets::Number(mapValue, pName, strPath, out_dValue, out_arrDiagnostics);
}

bool OptionalVector(const Serialization::JsonValue::Object &mapValue, const char *pName, const std::string &strPath, std::array<double, 3> &out_arrValues,
					Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator itValue = mapValue.find(pName);
	if (itValue == mapValue.end())
	{
		return true;
	}
	const Serialization::JsonValue::List *pValues = itValue->second.GetList();
	if (pValues == nullptr || pValues->size() != out_arrValues.size())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "type", strPath + "." + pName, "Expected exactly three finite numbers.");
		return false;
	}
	for (std::size_t nAxis = 0; nAxis < out_arrValues.size(); ++nAxis)
	{
		if (!(*pValues)[nAxis].GetNumber(out_arrValues[nAxis]))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "type", strPath + "." + pName + "[" + std::to_string(nAxis) + "]", "Expected a finite number.");
			return false;
		}
	}
	return true;
}

bool OptionalGridCount(const Serialization::JsonValue::Object &mapValue, const char *pName, const std::string &strPath, std::uint32_t &out_nValue,
					   Assets::Diagnostics &out_arrDiagnostics)
{
	if (mapValue.find(pName) == mapValue.end())
	{
		return true;
	}
	std::int64_t nValue = 0;
	if (!Assets::Integer(mapValue, pName, strPath, nValue, out_arrDiagnostics))
	{
		return false;
	}
	if (nValue < 0 || static_cast<std::uint64_t>(nValue) > std::numeric_limits<std::uint32_t>::max())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "range", strPath + "." + pName, "Expected a supported nonnegative grid count.");
		return false;
	}
	out_nValue = static_cast<std::uint32_t>(nValue);
	return true;
}

bool ParseLocalVolume(const Serialization::JsonValue &stValue, const std::string &strPath, LocalVolumeSettings &out_stLocal,
					  Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Assets::Object(stValue, strPath, out_arrDiagnostics);
	if (pObject == nullptr ||
		!OptionalFields(*pObject, { "shape", "center", "extent", "density", "albedo", "emission", "edge_fraction", "entity_id" }, strPath, out_arrDiagnostics))
	{
		return false;
	}
	if (pObject->find("shape") != pObject->end())
	{
		std::string strShape;
		if (!Assets::String(*pObject, "shape", strPath, strShape, out_arrDiagnostics))
		{
			return false;
		}
		if (strShape != "box" && strShape != "sphere")
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "volume_shape", strPath + ".shape", "Expected box or sphere.");
			return false;
		}
		out_stLocal.eShape = strShape == "box" ? LocalVolumeShape::Box : LocalVolumeShape::Sphere;
	}
	if (pObject->find("entity_id") != pObject->end())
	{
		std::int64_t nEntity = 0;
		if (!Assets::Integer(*pObject, "entity_id", strPath, nEntity, out_arrDiagnostics))
		{
			return false;
		}
		if (nEntity <= 0)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "volume_entity", strPath + ".entity_id", "Expected a positive existing-scene integer identity.");
			return false;
		}
		out_stLocal.nEntityId = static_cast<std::uint64_t>(nEntity);
	}
	return OptionalVector(*pObject, "center", strPath, out_stLocal.arrCenter, out_arrDiagnostics) &&
			OptionalVector(*pObject, "extent", strPath, out_stLocal.arrExtent, out_arrDiagnostics) &&
			OptionalNumber(*pObject, "density", strPath, out_stLocal.dDensity, out_arrDiagnostics) &&
			OptionalVector(*pObject, "albedo", strPath, out_stLocal.arrAlbedo, out_arrDiagnostics) &&
			OptionalVector(*pObject, "emission", strPath, out_stLocal.arrEmission, out_arrDiagnostics) &&
			OptionalNumber(*pObject, "edge_fraction", strPath, out_stLocal.dEdgeFraction, out_arrDiagnostics);
}

} // namespace

bool ValidateVolumeSettings(const VolumeSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!InRange(stSettings.dDistance, std::numeric_limits<float>::min(), 1.0e7) ||
		(stSettings.nCellPixels != 8 && stSettings.nCellPixels != 16 && stSettings.nCellPixels != 32) ||
		(stSettings.nDepthSlices != 32 && stSettings.nDepthSlices != 64 && stSettings.nDepthSlices != 96 && stSettings.nDepthSlices != 128) ||
		!MediumValues(stSettings.dDensity, stSettings.arrAlbedo, stSettings.arrEmission) || !GpuCoordinate(stSettings.dHeight) ||
		!GpuCoefficient(stSettings.dHeightFalloff) || !InRange(stSettings.dPhaseG, -0.95, 0.95) || !InRange(stSettings.dHistoryWeight, 0, 0.99) ||
		stSettings.nLocalVolumeCount > MAX_LOCAL_VOLUMES)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "volume_settings", "$.volumetric_fog",
							  "Volume settings require finite GPU values, supported grid dimensions, bounded medium coefficients, phase and history weights.");
		return false;
	}
	for (std::uint32_t nIndex = 0; nIndex < stSettings.nLocalVolumeCount; ++nIndex)
	{
		const LocalVolumeSettings &stLocal = stSettings.arrLocalVolumes[nIndex];
		if ((stLocal.eShape != LocalVolumeShape::Box && stLocal.eShape != LocalVolumeShape::Sphere) ||
			(stLocal.nEntityId.has_value() && *stLocal.nEntityId == 0) || !MediumValues(stLocal.dDensity, stLocal.arrAlbedo, stLocal.arrEmission) ||
			!InRange(stLocal.dEdgeFraction, 0, 1))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "volume_local", "$.volumetric_fog.local_volumes",
								  "Local volumes require a supported shape, positive optional entity ID, and bounded medium coefficients.");
			return false;
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			if (!GpuCoordinate(stLocal.arrCenter[nAxis]) ||
				!InRange(stLocal.arrExtent[nAxis], std::numeric_limits<float>::min(), std::numeric_limits<float>::max()) ||
				!GpuCoordinate(stLocal.arrCenter[nAxis] - stLocal.arrExtent[nAxis]) || !GpuCoordinate(stLocal.arrCenter[nAxis] + stLocal.arrExtent[nAxis]) ||
				static_cast<float>(stLocal.arrCenter[nAxis] - stLocal.arrExtent[nAxis]) >= static_cast<float>(stLocal.arrCenter[nAxis]) ||
				static_cast<float>(stLocal.arrCenter[nAxis] + stLocal.arrExtent[nAxis]) <= static_cast<float>(stLocal.arrCenter[nAxis]))
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "volume_bounds", "$.volumetric_fog.local_volumes",
									  "Local volume centers, positive extents and world bounds must be finite and distinct in binary32.");
				return false;
			}
		}
		if (stLocal.eShape == LocalVolumeShape::Sphere && (stLocal.arrExtent[0] != stLocal.arrExtent[1] || stLocal.arrExtent[0] != stLocal.arrExtent[2]))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "volume_sphere", "$.volumetric_fog.local_volumes",
								  "Sphere extents must contain the same radius on all three axes.");
			return false;
		}
	}
	return true;
}

bool ParseVolumeSettings(const Serialization::JsonValue &stValue, VolumeSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::string strPath = "$.volumetric_fog";
	const Serialization::JsonValue::Object *pObject = Assets::Object(stValue, strPath, out_arrDiagnostics);
	if (pObject == nullptr || !OptionalFields(*pObject, { "enabled", "distance", "cell_pixels", "depth_slices", "density", "height", "height_falloff", "albedo", "emission", "phase_g", "history_weight", "local_volumes" }, strPath, out_arrDiagnostics))
	{
		return false;
	}
	VolumeSettings stCandidate;
	const Serialization::JsonValue::Object::const_iterator itEnabled = pObject->find("enabled");
	if (itEnabled != pObject->end() && !itEnabled->second.GetBool(stCandidate.bEnabled))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "type", strPath + ".enabled", "Expected a boolean.");
		return false;
	}
	if (!OptionalNumber(*pObject, "distance", strPath, stCandidate.dDistance, out_arrDiagnostics) ||
		!OptionalGridCount(*pObject, "cell_pixels", strPath, stCandidate.nCellPixels, out_arrDiagnostics) ||
		!OptionalGridCount(*pObject, "depth_slices", strPath, stCandidate.nDepthSlices, out_arrDiagnostics) ||
		!OptionalNumber(*pObject, "density", strPath, stCandidate.dDensity, out_arrDiagnostics) ||
		!OptionalNumber(*pObject, "height", strPath, stCandidate.dHeight, out_arrDiagnostics) ||
		!OptionalNumber(*pObject, "height_falloff", strPath, stCandidate.dHeightFalloff, out_arrDiagnostics) ||
		!OptionalVector(*pObject, "albedo", strPath, stCandidate.arrAlbedo, out_arrDiagnostics) ||
		!OptionalVector(*pObject, "emission", strPath, stCandidate.arrEmission, out_arrDiagnostics) ||
		!OptionalNumber(*pObject, "phase_g", strPath, stCandidate.dPhaseG, out_arrDiagnostics) ||
		!OptionalNumber(*pObject, "history_weight", strPath, stCandidate.dHistoryWeight, out_arrDiagnostics))
	{
		return false;
	}
	const Serialization::JsonValue::Object::const_iterator itLocals = pObject->find("local_volumes");
	if (itLocals != pObject->end())
	{
		const Serialization::JsonValue::List *pLocals = itLocals->second.GetList();
		if (pLocals == nullptr || pLocals->size() > MAX_LOCAL_VOLUMES)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "volume_locals", strPath + ".local_volumes", "Expected an array of at most 16 local volumes.");
			return false;
		}
		stCandidate.nLocalVolumeCount = static_cast<std::uint32_t>(pLocals->size());
		for (std::size_t nIndex = 0; nIndex < pLocals->size(); ++nIndex)
		{
			if (!ParseLocalVolume((*pLocals)[nIndex], strPath + ".local_volumes[" + std::to_string(nIndex) + "]", stCandidate.arrLocalVolumes[nIndex],
								  out_arrDiagnostics))
			{
				return false;
			}
		}
	}
	if (!ValidateVolumeSettings(stCandidate, out_arrDiagnostics))
	{
		return false;
	}
	out_stSettings = stCandidate;
	return true;
}

} // namespace EngineNext::Rendering
