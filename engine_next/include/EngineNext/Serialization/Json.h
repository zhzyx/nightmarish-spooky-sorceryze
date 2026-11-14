/**************************************************************************/
/*  Json.h                                                                */
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

#include <cstdint>
#include <map>
#include <string>
#include <variant>
#include <vector>

namespace EngineNext::Serialization
{

class JsonValue
{
public:
	using List = std::vector<JsonValue>;
	using Object = std::map<std::string, JsonValue>;
	using Storage = std::variant<std::nullptr_t, bool, std::int64_t, double, std::string, List, Object>;

	JsonValue();
	JsonValue(bool in_bValue);
	JsonValue(std::int64_t in_nValue);
	JsonValue(double in_dValue);
	JsonValue(const char *in_pValue);
	JsonValue(std::string in_strValue);
	JsonValue(List in_arrValue);
	JsonValue(Object in_mapValue);

	[[nodiscard]] bool IsNull() const noexcept;
	[[nodiscard]] bool IsBool() const noexcept;
	[[nodiscard]] bool IsInteger() const noexcept;
	[[nodiscard]] bool IsNumber() const noexcept;
	[[nodiscard]] bool IsString() const noexcept;
	[[nodiscard]] bool IsList() const noexcept;
	[[nodiscard]] bool IsObject() const noexcept;
	[[nodiscard]] bool GetBool(bool &out_bValue) const noexcept;
	[[nodiscard]] bool GetInteger(std::int64_t &out_nValue) const noexcept;
	[[nodiscard]] bool GetNumber(double &out_dValue) const noexcept;
	[[nodiscard]] const std::string *GetString() const noexcept;
	[[nodiscard]] const List *GetList() const noexcept;
	[[nodiscard]] const Object *GetObject() const noexcept;
	[[nodiscard]] List *GetList() noexcept;
	[[nodiscard]] Object *GetObject() noexcept;

private:
	Storage stValue;
};

[[nodiscard]] bool ParseJson(const std::string &in_strText, JsonValue &out_stValue, std::string &out_strError);
[[nodiscard]] bool CanonicalJson(const JsonValue &in_stValue, std::string &out_strText);

} // namespace EngineNext::Serialization
