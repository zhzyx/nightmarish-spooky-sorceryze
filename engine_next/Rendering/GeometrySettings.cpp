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
#include <limits>
#include <string>

namespace EngineNext::Rendering
{
bool ValidateGeometrySettings(const GeometrySettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stSettings.nMaxCommands == 0)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "geometry_capacity", "$.geometry_culling.max_commands", "A positive command capacity is required.");
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
	for (const char *pField : { "enabled", "occlusion", "max_commands" })
	{
		mapFields.emplace(pField, Serialization::JsonValue{});
	}
	if (!Assets::Fields(mapFields, { "enabled", "occlusion", "max_commands" }, "$.geometry_culling", out_arrDiagnostics))
	{
		return false;
	}
	GeometrySettings stCandidate;
	for (const char *pField : { "enabled", "occlusion" })
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
			else
			{
				stCandidate.bOcclusion = bValue;
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
	if (!ValidateGeometrySettings(stCandidate, out_arrDiagnostics))
	{
		return false;
	}
	out_stSettings = stCandidate;
	return true;
}
} // namespace EngineNext::Rendering
