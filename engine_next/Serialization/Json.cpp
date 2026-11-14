/**************************************************************************/
/*  Json.cpp                                                              */
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

#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <charconv>
#include <cmath>
#include <cstdio>
#include <limits>
#include <locale>
#include <sstream>
#include <utility>

namespace EngineNext::Serialization
{
namespace
{

constexpr std::size_t MAX_JSON_BYTES = 384ULL * 1024ULL * 1024ULL;
constexpr int MAX_DEPTH = 32;

bool AppendUtf8(std::uint32_t nCodepoint, std::string &out_strText)
{
	if (nCodepoint > 0x10FFFFU || (nCodepoint >= 0xD800U && nCodepoint <= 0xDFFFU))
	{
		return false;
	}
	if (nCodepoint <= 0x7FU)
	{
		out_strText.push_back(static_cast<char>(nCodepoint));
	}
	else if (nCodepoint <= 0x7FFU)
	{
		out_strText.push_back(static_cast<char>(0xC0U | (nCodepoint >> 6U)));
		out_strText.push_back(static_cast<char>(0x80U | (nCodepoint & 0x3FU)));
	}
	else if (nCodepoint <= 0xFFFFU)
	{
		out_strText.push_back(static_cast<char>(0xE0U | (nCodepoint >> 12U)));
		out_strText.push_back(static_cast<char>(0x80U | ((nCodepoint >> 6U) & 0x3FU)));
		out_strText.push_back(static_cast<char>(0x80U | (nCodepoint & 0x3FU)));
	}
	else
	{
		out_strText.push_back(static_cast<char>(0xF0U | (nCodepoint >> 18U)));
		out_strText.push_back(static_cast<char>(0x80U | ((nCodepoint >> 12U) & 0x3FU)));
		out_strText.push_back(static_cast<char>(0x80U | ((nCodepoint >> 6U) & 0x3FU)));
		out_strText.push_back(static_cast<char>(0x80U | (nCodepoint & 0x3FU)));
	}
	return true;
}

bool ValidateUtf8(const std::string &in_strText)
{
	std::size_t nIndex = 0;
	while (nIndex < in_strText.size())
	{
		const unsigned char nFirst = static_cast<unsigned char>(in_strText[nIndex]);
		if (nFirst <= 0x7FU)
		{
			++nIndex;
			continue;
		}
		std::uint32_t nCodepoint = 0;
		std::size_t nLength = 0;
		if (nFirst >= 0xC2U && nFirst <= 0xDFU)
		{
			nCodepoint = nFirst & 0x1FU;
			nLength = 2;
		}
		else if (nFirst >= 0xE0U && nFirst <= 0xEFU)
		{
			nCodepoint = nFirst & 0x0FU;
			nLength = 3;
		}
		else if (nFirst >= 0xF0U && nFirst <= 0xF4U)
		{
			nCodepoint = nFirst & 0x07U;
			nLength = 4;
		}
		else
		{
			return false;
		}
		if (nIndex + nLength > in_strText.size())
		{
			return false;
		}
		for (std::size_t nOffset = 1; nOffset < nLength; ++nOffset)
		{
			const unsigned char nNext = static_cast<unsigned char>(in_strText[nIndex + nOffset]);
			if ((nNext & 0xC0U) != 0x80U)
			{
				return false;
			}
			nCodepoint = (nCodepoint << 6U) | (nNext & 0x3FU);
		}
		if ((nLength == 3 && nCodepoint < 0x800U) || (nLength == 4 && nCodepoint < 0x10000U) ||
			(nCodepoint >= 0xD800U && nCodepoint <= 0xDFFFU) || nCodepoint > 0x10FFFFU)
		{
			return false;
		}
		nIndex += nLength;
	}
	return true;
}

class Parser final
{
	const std::string &strText;
	std::size_t nOffset = 0;
	std::string strError;

	bool Fail(const std::string &in_strMessage)
	{
		if (strError.empty())
		{
			strError = in_strMessage + " at byte " + std::to_string(nOffset);
		}
		return false;
	}

	void SkipWhitespace()
	{
		while (nOffset < strText.size())
		{
			const char nCharacter = strText[nOffset];
			if (nCharacter != ' ' && nCharacter != '\t' && nCharacter != '\r' && nCharacter != '\n')
			{
				break;
			}
			++nOffset;
		}
	}

	bool Consume(char in_nExpected)
	{
		if (nOffset >= strText.size() || strText[nOffset] != in_nExpected)
		{
			return false;
		}
		++nOffset;
		return true;
	}

	bool ParseHex4(std::uint32_t &out_nValue)
	{
		if (nOffset + 4 > strText.size())
		{
			return Fail("truncated Unicode escape");
		}
		std::uint32_t nValue = 0;
		for (int nIndex = 0; nIndex < 4; ++nIndex)
		{
			const char nCharacter = strText[nOffset++];
			nValue <<= 4U;
			if (nCharacter >= '0' && nCharacter <= '9')
			{
				nValue |= static_cast<std::uint32_t>(nCharacter - '0');
			}
			else if (nCharacter >= 'a' && nCharacter <= 'f')
			{
				nValue |= static_cast<std::uint32_t>(nCharacter - 'a' + 10);
			}
			else if (nCharacter >= 'A' && nCharacter <= 'F')
			{
				nValue |= static_cast<std::uint32_t>(nCharacter - 'A' + 10);
			}
			else
			{
				return Fail("invalid Unicode escape");
			}
		}
		out_nValue = nValue;
		return true;
	}

	bool ParseString(std::string &out_strValue)
	{
		if (!Consume('"'))
		{
			return Fail("expected string");
		}
		out_strValue.clear();
		while (nOffset < strText.size())
		{
			const unsigned char nCharacter = static_cast<unsigned char>(strText[nOffset++]);
			if (nCharacter == '"')
			{
				return ValidateUtf8(out_strValue) || Fail("invalid UTF-8 string");
			}
			if (nCharacter < 0x20U)
			{
				return Fail("unescaped control character");
			}
			if (nCharacter != '\\')
			{
				out_strValue.push_back(static_cast<char>(nCharacter));
				continue;
			}
			if (nOffset >= strText.size())
			{
				return Fail("truncated escape");
			}
			const char nEscape = strText[nOffset++];
			switch (nEscape)
			{
				case '"': out_strValue.push_back('"'); break;
				case '\\': out_strValue.push_back('\\'); break;
				case '/': out_strValue.push_back('/'); break;
				case 'b': out_strValue.push_back('\b'); break;
				case 'f': out_strValue.push_back('\f'); break;
				case 'n': out_strValue.push_back('\n'); break;
				case 'r': out_strValue.push_back('\r'); break;
				case 't': out_strValue.push_back('\t'); break;
				case 'u':
				{
					std::uint32_t nCodepoint = 0;
					if (!ParseHex4(nCodepoint))
					{
						return false;
					}
					if (nCodepoint >= 0xD800U && nCodepoint <= 0xDBFFU)
					{
						if (nOffset + 2 > strText.size() || strText[nOffset] != '\\' || strText[nOffset + 1] != 'u')
						{
							return Fail("missing low surrogate");
						}
						nOffset += 2;
						std::uint32_t nLow = 0;
						if (!ParseHex4(nLow) || nLow < 0xDC00U || nLow > 0xDFFFU)
						{
							return Fail("invalid low surrogate");
						}
						nCodepoint = 0x10000U + ((nCodepoint - 0xD800U) << 10U) + (nLow - 0xDC00U);
					}
					else if (nCodepoint >= 0xDC00U && nCodepoint <= 0xDFFFU)
					{
						return Fail("unexpected low surrogate");
					}
					if (!AppendUtf8(nCodepoint, out_strValue))
					{
						return Fail("invalid Unicode codepoint");
					}
					break;
				}
				default: return Fail("unknown escape");
			}
		}
		return Fail("unterminated string");
	}

	bool ParseNumber(JsonValue &out_stValue)
	{
		const std::size_t nBegin = nOffset;
		if (nOffset < strText.size() && strText[nOffset] == '-')
		{
			++nOffset;
		}
		if (nOffset >= strText.size())
		{
			return Fail("truncated number");
		}
		if (strText[nOffset] == '0')
		{
			++nOffset;
			if (nOffset < strText.size() && strText[nOffset] >= '0' && strText[nOffset] <= '9')
			{
				return Fail("leading zero");
			}
		}
		else if (strText[nOffset] >= '1' && strText[nOffset] <= '9')
		{
			while (nOffset < strText.size() && strText[nOffset] >= '0' && strText[nOffset] <= '9')
			{
				++nOffset;
			}
		}
		else
		{
			return Fail("expected digit");
		}
		bool bFloating = false;
		if (nOffset < strText.size() && strText[nOffset] == '.')
		{
			bFloating = true;
			++nOffset;
			const std::size_t nFraction = nOffset;
			while (nOffset < strText.size() && strText[nOffset] >= '0' && strText[nOffset] <= '9')
			{
				++nOffset;
			}
			if (nFraction == nOffset)
			{
				return Fail("missing fraction");
			}
		}
		if (nOffset < strText.size() && (strText[nOffset] == 'e' || strText[nOffset] == 'E'))
		{
			bFloating = true;
			++nOffset;
			if (nOffset < strText.size() && (strText[nOffset] == '+' || strText[nOffset] == '-'))
			{
				++nOffset;
			}
			const std::size_t nExponent = nOffset;
			while (nOffset < strText.size() && strText[nOffset] >= '0' && strText[nOffset] <= '9')
			{
				++nOffset;
			}
			if (nExponent == nOffset)
			{
				return Fail("missing exponent");
			}
		}
		const char *pBegin = strText.data() + nBegin;
		const char *pEnd = strText.data() + nOffset;
		if (!bFloating)
		{
			std::int64_t nValue = 0;
			const std::from_chars_result stResult = std::from_chars(pBegin, pEnd, nValue);
			if (stResult.ec != std::errc() || stResult.ptr != pEnd)
			{
				return Fail("unsafe integer");
			}
			out_stValue = JsonValue(nValue);
			return true;
		}
		double dValue = 0.0;
		std::istringstream stStream(std::string(pBegin, pEnd));
		stStream.imbue(std::locale::classic());
		stStream >> dValue;
		if (!stStream || stStream.peek() != std::char_traits<char>::eof() || !std::isfinite(dValue))
		{
			return Fail("nonfinite or invalid number");
		}
		out_stValue = JsonValue(dValue);
		return true;
	}

	bool ParseList(JsonValue &out_stValue, int in_nDepth)
	{
		if (!Consume('['))
		{
			return Fail("expected array");
		}
		JsonValue::List arrValues;
		SkipWhitespace();
		if (Consume(']'))
		{
			out_stValue = JsonValue(std::move(arrValues));
			return true;
		}
		while (nOffset < strText.size())
		{
			JsonValue stItem;
			if (!ParseValue(stItem, in_nDepth + 1))
			{
				return false;
			}
			arrValues.push_back(std::move(stItem));
			SkipWhitespace();
			if (Consume(']'))
			{
				out_stValue = JsonValue(std::move(arrValues));
				return true;
			}
			if (!Consume(','))
			{
				return Fail("expected array comma");
			}
			SkipWhitespace();
		}
		return Fail("unterminated array");
	}

	bool ParseObject(JsonValue &out_stValue, int in_nDepth)
	{
		if (!Consume('{'))
		{
			return Fail("expected object");
		}
		JsonValue::Object mapValues;
		SkipWhitespace();
		if (Consume('}'))
		{
			out_stValue = JsonValue(std::move(mapValues));
			return true;
		}
		while (nOffset < strText.size())
		{
			std::string strKey;
			if (!ParseString(strKey))
			{
				return false;
			}
			SkipWhitespace();
			if (!Consume(':'))
			{
				return Fail("expected object colon");
			}
			SkipWhitespace();
			JsonValue stItem;
			if (!ParseValue(stItem, in_nDepth + 1))
			{
				return false;
			}
			if (mapValues.find(strKey) != mapValues.end())
			{
				return Fail("duplicate object key");
			}
			mapValues.emplace(std::move(strKey), std::move(stItem));
			SkipWhitespace();
			if (Consume('}'))
			{
				out_stValue = JsonValue(std::move(mapValues));
				return true;
			}
			if (!Consume(','))
			{
				return Fail("expected object comma");
			}
			SkipWhitespace();
		}
		return Fail("unterminated object");
	}

	bool ParseValue(JsonValue &out_stValue, int in_nDepth)
	{
		if (in_nDepth > MAX_DEPTH)
		{
			return Fail("maximum depth exceeded");
		}
		SkipWhitespace();
		if (nOffset >= strText.size())
		{
			return Fail("expected value");
		}
		switch (strText[nOffset])
		{
			case '{': return ParseObject(out_stValue, in_nDepth);
			case '[': return ParseList(out_stValue, in_nDepth);
			case '"':
			{
				std::string strValue;
				if (!ParseString(strValue))
				{
					return false;
				}
				out_stValue = JsonValue(std::move(strValue));
				return true;
			}
			case 't':
				if (strText.compare(nOffset, 4, "true") != 0)
				{
					return Fail("invalid literal");
				}
				nOffset += 4;
				out_stValue = JsonValue(true);
				return true;
			case 'f':
				if (strText.compare(nOffset, 5, "false") != 0)
				{
					return Fail("invalid literal");
				}
				nOffset += 5;
				out_stValue = JsonValue(false);
				return true;
			case 'n':
				if (strText.compare(nOffset, 4, "null") != 0)
				{
					return Fail("invalid literal");
				}
				nOffset += 4;
				out_stValue = JsonValue();
				return true;
			default: return ParseNumber(out_stValue);
		}
	}

public:
	explicit Parser(const std::string &in_strText) :
			strText(in_strText)
	{
	}

	bool Parse(JsonValue &out_stValue, std::string &out_strError)
	{
		if (strText.empty() || strText.size() > MAX_JSON_BYTES)
		{
			out_strError = "empty or oversized JSON input";
			return false;
		}
		if (!ParseValue(out_stValue, 0))
		{
			out_strError = strError;
			return false;
		}
		SkipWhitespace();
		if (nOffset != strText.size())
		{
			out_strError = "trailing JSON data at byte " + std::to_string(nOffset);
			return false;
		}
		return true;
	}
};

bool WriteString(const std::string &in_strValue, std::string &out_strText)
{
	if (!ValidateUtf8(in_strValue))
	{
		return false;
	}
	out_strText.push_back('"');
	for (const unsigned char nCharacter : in_strValue)
	{
		switch (nCharacter)
		{
			case '"': out_strText += "\\\""; break;
			case '\\': out_strText += "\\\\"; break;
			case '\b': out_strText += "\\b"; break;
			case '\f': out_strText += "\\f"; break;
			case '\n': out_strText += "\\n"; break;
			case '\r': out_strText += "\\r"; break;
			case '\t': out_strText += "\\t"; break;
			default:
				if (nCharacter < 0x20U)
				{
					char arrBuffer[7]{};
					const int nWritten = std::snprintf(arrBuffer, sizeof(arrBuffer), "\\u%04x", static_cast<unsigned int>(nCharacter));
					if (nWritten != 6)
					{
						return false;
					}
					out_strText.append(arrBuffer, 6);
				}
				else
				{
					out_strText.push_back(static_cast<char>(nCharacter));
				}
		}
	}
	out_strText.push_back('"');
	return true;
}

bool WriteValue(const JsonValue &in_stValue, std::string &out_strText)
{
	if (in_stValue.IsNull())
	{
		out_strText += "null";
		return true;
	}
	bool bValue = false;
	if (in_stValue.GetBool(bValue))
	{
		out_strText += bValue ? "true" : "false";
		return true;
	}
	std::int64_t nInteger = 0;
	if (in_stValue.GetInteger(nInteger))
	{
		out_strText += std::to_string(nInteger);
		return true;
	}
	if (const std::string *pString = in_stValue.GetString())
	{
		return WriteString(*pString, out_strText);
	}
	if (const JsonValue::List *pList = in_stValue.GetList())
	{
		out_strText.push_back('[');
		for (std::size_t nIndex = 0; nIndex < pList->size(); ++nIndex)
		{
			if (nIndex != 0)
			{
				out_strText.push_back(',');
			}
			if (!WriteValue((*pList)[nIndex], out_strText))
			{
				return false;
			}
		}
		out_strText.push_back(']');
		return true;
	}
	if (const JsonValue::Object *pObject = in_stValue.GetObject())
	{
		out_strText.push_back('{');
		bool bFirst = true;
		for (const std::pair<const std::string, JsonValue> &stEntry : *pObject)
		{
			if (!bFirst)
			{
				out_strText.push_back(',');
			}
			bFirst = false;
			if (!WriteString(stEntry.first, out_strText))
			{
				return false;
			}
			out_strText.push_back(':');
			if (!WriteValue(stEntry.second, out_strText))
			{
				return false;
			}
		}
		out_strText.push_back('}');
		return true;
	}
	double dValue = 0.0;
	if (!in_stValue.GetNumber(dValue) || !std::isfinite(dValue))
	{
		return false;
	}
	if (dValue == 0.0)
	{
		out_strText += "0.0";
		return true;
	}
	char arrBuffer[128]{};
	const std::to_chars_result stResult = std::to_chars(arrBuffer, arrBuffer + sizeof(arrBuffer), dValue, std::chars_format::general);
	if (stResult.ec != std::errc())
	{
		return false;
	}
	std::string strNumber(arrBuffer, stResult.ptr);
	const std::size_t nExponent = strNumber.find_first_of("eE");
	if (nExponent == std::string::npos)
	{
		if (strNumber.find('.') == std::string::npos)
		{
			strNumber += ".0";
		}
	}
	else
	{
		strNumber[nExponent] = 'e';
		std::size_t nDigits = nExponent + 1;
		if (nDigits < strNumber.size() && strNumber[nDigits] == '+')
		{
			strNumber.erase(nDigits, 1);
		}
		if (nDigits < strNumber.size() && strNumber[nDigits] == '-')
		{
			++nDigits;
		}
		while (nDigits + 1 < strNumber.size() && strNumber[nDigits] == '0')
		{
			strNumber.erase(nDigits, 1);
		}
	}
	out_strText += strNumber;
	return true;
}

} // namespace

JsonValue::JsonValue() :
		stValue(nullptr)
{
}

JsonValue::JsonValue(bool in_bValue) :
		stValue(in_bValue)
{
}

JsonValue::JsonValue(std::int64_t in_nValue) :
		stValue(in_nValue)
{
}

JsonValue::JsonValue(double in_dValue) :
		stValue(in_dValue)
{
}

JsonValue::JsonValue(const char *in_pValue) :
		stValue(std::string(in_pValue == nullptr ? "" : in_pValue))
{
}

JsonValue::JsonValue(std::string in_strValue) :
		stValue(std::move(in_strValue))
{
}

JsonValue::JsonValue(List in_arrValue) :
		stValue(std::move(in_arrValue))
{
}

JsonValue::JsonValue(Object in_mapValue) :
		stValue(std::move(in_mapValue))
{
}

bool JsonValue::IsNull() const noexcept { return std::holds_alternative<std::nullptr_t>(stValue); }
bool JsonValue::IsBool() const noexcept { return std::holds_alternative<bool>(stValue); }
bool JsonValue::IsInteger() const noexcept { return std::holds_alternative<std::int64_t>(stValue); }
bool JsonValue::IsNumber() const noexcept { return IsInteger() || std::holds_alternative<double>(stValue); }
bool JsonValue::IsString() const noexcept { return std::holds_alternative<std::string>(stValue); }
bool JsonValue::IsList() const noexcept { return std::holds_alternative<List>(stValue); }
bool JsonValue::IsObject() const noexcept { return std::holds_alternative<Object>(stValue); }

bool JsonValue::GetBool(bool &out_bValue) const noexcept
{
	const bool *pValue = std::get_if<bool>(&stValue);
	if (pValue == nullptr)
	{
		return false;
	}
	out_bValue = *pValue;
	return true;
}

bool JsonValue::GetInteger(std::int64_t &out_nValue) const noexcept
{
	const std::int64_t *pValue = std::get_if<std::int64_t>(&stValue);
	if (pValue == nullptr)
	{
		return false;
	}
	out_nValue = *pValue;
	return true;
}

bool JsonValue::GetNumber(double &out_dValue) const noexcept
{
	if (const double *pValue = std::get_if<double>(&stValue))
	{
		out_dValue = *pValue;
		return std::isfinite(*pValue);
	}
	std::int64_t nValue = 0;
	if (!GetInteger(nValue))
	{
		return false;
	}
	out_dValue = static_cast<double>(nValue);
	return true;
}

const std::string *JsonValue::GetString() const noexcept { return std::get_if<std::string>(&stValue); }
const JsonValue::List *JsonValue::GetList() const noexcept { return std::get_if<List>(&stValue); }
const JsonValue::Object *JsonValue::GetObject() const noexcept { return std::get_if<Object>(&stValue); }
JsonValue::List *JsonValue::GetList() noexcept { return std::get_if<List>(&stValue); }
JsonValue::Object *JsonValue::GetObject() noexcept { return std::get_if<Object>(&stValue); }

bool ParseJson(const std::string &in_strText, JsonValue &out_stValue, std::string &out_strError)
{
	Parser stParser(in_strText);
	return stParser.Parse(out_stValue, out_strError);
}

bool CanonicalJson(const JsonValue &in_stValue, std::string &out_strText)
{
	out_strText.clear();
	return WriteValue(in_stValue, out_strText);
}

} // namespace EngineNext::Serialization
