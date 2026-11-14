/**************************************************************************/
/*  AssetValidation.h                                                     */
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
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <initializer_list>
#include <string>

namespace EngineNext::Assets
{

inline const Serialization::JsonValue::Object *Object(const Serialization::JsonValue &in_stValue, const std::string &in_strPath, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = in_stValue.GetObject();
	if (pObject == nullptr)
	{
		AddDiagnostic(out_arrDiagnostics, "type", in_strPath, "expected object");
	}
	return pObject;
}

inline bool Fields(const Serialization::JsonValue::Object &in_mapValue, std::initializer_list<const char *> in_arrNames, const std::string &in_strPath, Diagnostics &out_arrDiagnostics)
{
	bool bValid = true;
	for (const std::pair<const std::string, Serialization::JsonValue> &stEntry : in_mapValue)
	{
		bool bKnown = false;
		for (const char *pName : in_arrNames)
		{
			bKnown = bKnown || stEntry.first == pName;
		}
		if (!bKnown)
		{
			AddDiagnostic(out_arrDiagnostics, "unknown_field", in_strPath, "unknown field: " + stEntry.first);
			bValid = false;
		}
	}
	for (const char *pName : in_arrNames)
	{
		if (in_mapValue.find(pName) == in_mapValue.end())
		{
			AddDiagnostic(out_arrDiagnostics, "missing_field", in_strPath, "missing field: " + std::string(pName));
			bValid = false;
		}
	}
	return bValid;
}

inline bool String(const Serialization::JsonValue::Object &in_mapValue, const std::string &in_strName, const std::string &in_strPath, std::string &out_strValue, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapValue.find(in_strName);
	const std::string *pValue = it == in_mapValue.end() ? nullptr : it->second.GetString();
	if (pValue == nullptr)
	{
		AddDiagnostic(out_arrDiagnostics, "type", in_strPath + "." + in_strName, "expected string");
		return false;
	}
	out_strValue = *pValue;
	return true;
}

inline bool Integer(const Serialization::JsonValue::Object &in_mapValue, const std::string &in_strName, const std::string &in_strPath, std::int64_t &out_nValue, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapValue.find(in_strName);
	if (it == in_mapValue.end() || !it->second.GetInteger(out_nValue))
	{
		AddDiagnostic(out_arrDiagnostics, "type", in_strPath + "." + in_strName, "expected safe integer");
		return false;
	}
	return true;
}

inline bool Number(const Serialization::JsonValue::Object &in_mapValue, const std::string &in_strName, const std::string &in_strPath, double &out_dValue, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapValue.find(in_strName);
	if (it == in_mapValue.end() || !it->second.GetNumber(out_dValue))
	{
		AddDiagnostic(out_arrDiagnostics, "type", in_strPath + "." + in_strName, "expected finite number");
		return false;
	}
	return true;
}

inline bool ParseRef(const Serialization::JsonValue &in_stValue, const std::string &in_strPath, AssetRef &out_stRef, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Object(in_stValue, in_strPath, out_arrDiagnostics);
	if (pObject == nullptr)
	{
		return false;
	}
	Fields(*pObject, { "asset_id", "revision", "content_sha256" }, in_strPath, out_arrDiagnostics);
	const bool bId = String(*pObject, "asset_id", in_strPath, out_stRef.strAssetId, out_arrDiagnostics);
	const bool bRevision = String(*pObject, "revision", in_strPath, out_stRef.strRevision, out_arrDiagnostics);
	const bool bDigest = String(*pObject, "content_sha256", in_strPath, out_stRef.strContentSha256, out_arrDiagnostics);
	if (bId && !IsIdentity(out_stRef.strAssetId))
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_asset_id", in_strPath + ".asset_id", "invalid asset identity");
	}
	if (bRevision && !IsRevision(out_stRef.strRevision))
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_revision", in_strPath + ".revision", "invalid immutable revision");
	}
	if (bDigest && !IsSha256(out_stRef.strContentSha256))
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_digest", in_strPath + ".content_sha256", "expected lowercase SHA-256");
	}
	return IsIdentity(out_stRef.strAssetId) && IsRevision(out_stRef.strRevision) && IsSha256(out_stRef.strContentSha256);
}

inline Serialization::JsonValue RefJson(const AssetRef &in_stRef)
{
	return Serialization::JsonValue::Object{
		{ "asset_id", in_stRef.strAssetId },
		{ "content_sha256", in_stRef.strContentSha256 },
		{ "revision", in_stRef.strRevision },
	};
}

} // namespace EngineNext::Assets
