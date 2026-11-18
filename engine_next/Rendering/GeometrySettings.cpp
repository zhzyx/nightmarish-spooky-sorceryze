/**************************************************************************/
/*  GeometrySettings.cpp                                                  */
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

#include "engine_next/include/EngineNext/Rendering/GeometrySettings.h"
#include "engine_next/Assets/AssetValidation.h"

#include <initializer_list>
#include <cmath>
#include <limits>
#include <string>

namespace EngineNext::Rendering
{
bool ValidateGeometrySettings(const GeometrySettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stSettings.nMaxCommands == 0 || !std::isfinite(stSettings.dPixelError) || stSettings.dPixelError <= 0 ||
		!std::isfinite(stSettings.dLodHysteresis) || stSettings.dLodHysteresis < 0 || stSettings.dLodHysteresis >= 1 ||
		stSettings.nPageGpuBytes < 65536 || stSettings.nPageGpuBytes > 2ULL * 1024 * 1024 * 1024 ||
		stSettings.nPageStagingBytes < 65536 || stSettings.nPageStagingBytes > 256ULL * 1024 * 1024 ||
		stSettings.nMaxPageLoads == 0 || stSettings.nMaxPageLoads > 256)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "geometry_capacity", "$.geometry_culling.max_commands", "Geometry command, LOD tolerance, upload count or physical memory budget is invalid.");
		return false;
	}
	return true;
}

bool ParseGeometrySettings(const Serialization::JsonValue &stValue, GeometrySettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Assets::Object(stValue, "$.geometry_culling", out_arrDiagnostics);
	if (pObject == nullptr)
	{
		return false;
	}
	Serialization::JsonValue::Object mapFields = *pObject;
	for (const char *pField : { "enabled", "occlusion", "max_commands", "lod_enabled", "pixel_error", "lod_hysteresis", "page_gpu_bytes", "page_staging_bytes", "max_page_loads" })
	{
		mapFields.emplace(pField, Serialization::JsonValue{});
	}
	if (!Assets::Fields(mapFields, { "enabled", "occlusion", "max_commands", "lod_enabled", "pixel_error", "lod_hysteresis", "page_gpu_bytes", "page_staging_bytes", "max_page_loads" }, "$.geometry_culling", out_arrDiagnostics))
	{
		return false;
	}
	GeometrySettings stCandidate;
	for (const char *pField : { "enabled", "occlusion", "lod_enabled" })
	{
		const Serialization::JsonValue::Object::const_iterator it = pObject->find(pField);
		bool bValue = false;
		if (it != pObject->end())
		{
			if (!it->second.GetBool(bValue))
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "geometry_boolean", std::string("$.geometry_culling.") + pField, "Expected a boolean.");
				return false;
			}
			if (std::string(pField) == "enabled")
			{
				stCandidate.bEnabled = bValue;
			}
			else if (std::string(pField) == "occlusion")
			{
				stCandidate.bOcclusion = bValue;
			}
			else
			{
				stCandidate.bLodEnabled = bValue;
			}
		}
	}
	const Serialization::JsonValue::Object::const_iterator itCapacity = pObject->find("max_commands");
	if (itCapacity != pObject->end())
	{
		std::int64_t nCapacity = 0;
		if (!itCapacity->second.GetInteger(nCapacity) || nCapacity <= 0 || nCapacity > std::numeric_limits<std::uint32_t>::max())
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "geometry_capacity", "$.geometry_culling.max_commands", "Expected a positive uint32 capacity.");
			return false;
		}
		stCandidate.nMaxCommands = static_cast<std::uint32_t>(nCapacity);
	}
	for (const char *pField : { "pixel_error", "lod_hysteresis" })
	{
		const Serialization::JsonValue::Object::const_iterator it = pObject->find(pField);
		double dValue = 0;
		if (it != pObject->end())
		{
			if (!it->second.GetNumber(dValue))
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "geometry_number", std::string("$.geometry_culling.") + pField, "Expected a finite number.");
				return false;
			}
			if (std::string(pField) == "pixel_error")
			{
				stCandidate.dPixelError = dValue;
			}
			else
			{
				stCandidate.dLodHysteresis = dValue;
			}
		}
	}
	for (const char *pField : { "page_gpu_bytes", "page_staging_bytes", "max_page_loads" })
	{
		const Serialization::JsonValue::Object::const_iterator it = pObject->find(pField);
		std::int64_t nValue = 0;
		if (it != pObject->end())
		{
			if (!it->second.GetInteger(nValue) || nValue < 0 || (std::string(pField) == "max_page_loads" && nValue > 256))
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "geometry_budget", std::string("$.geometry_culling.") + pField, "Expected a bounded nonnegative integer.");
				return false;
			}
			if (std::string(pField) == "page_gpu_bytes")
			{
				stCandidate.nPageGpuBytes = static_cast<std::uint64_t>(nValue);
			}
			else if (std::string(pField) == "page_staging_bytes")
			{
				stCandidate.nPageStagingBytes = static_cast<std::uint64_t>(nValue);
			}
			else
			{
				stCandidate.nMaxPageLoads = static_cast<std::uint32_t>(nValue);
			}
		}
	}
	if (!ValidateGeometrySettings(stCandidate, out_arrDiagnostics))
	{
		return false;
	}
	out_stSettings = stCandidate;
	return true;
}
} // namespace EngineNext::Rendering
