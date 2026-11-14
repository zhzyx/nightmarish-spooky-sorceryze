/**************************************************************************/
/*  Types.cpp                                                             */
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

#include "engine_next/include/EngineNext/Assets/Types.h"

#include <algorithm>
#include <cctype>

namespace EngineNext::Assets
{

bool IsIdentity(const std::string &in_strValue) noexcept
{
	if (in_strValue.empty() || in_strValue.size() > 128 || std::isalnum(static_cast<unsigned char>(in_strValue.front())) == 0)
	{
		return false;
	}
	for (const unsigned char nCharacter : in_strValue)
	{
		if (std::isalnum(nCharacter) == 0 && nCharacter != '.' && nCharacter != '_' && nCharacter != '-')
		{
			return false;
		}
	}
	return true;
}

bool IsRevision(const std::string &in_strValue) noexcept
{
	return in_strValue.size() <= 64 && IsIdentity(in_strValue);
}

bool IsSha256(const std::string &in_strValue) noexcept
{
	if (in_strValue.size() != 64)
	{
		return false;
	}
	for (const unsigned char nCharacter : in_strValue)
	{
		if ((nCharacter < '0' || nCharacter > '9') && (nCharacter < 'a' || nCharacter > 'f'))
		{
			return false;
		}
	}
	return true;
}

void AddDiagnostic(Diagnostics &out_arrDiagnostics, const std::string &in_strCode, const std::string &in_strPath, const std::string &in_strMessage)
{
	out_arrDiagnostics.push_back(Diagnostic{ in_strCode, in_strPath, in_strMessage });
}

void SortDiagnostics(Diagnostics &out_arrDiagnostics)
{
	std::sort(out_arrDiagnostics.begin(), out_arrDiagnostics.end(), [](const Diagnostic &in_stLeft, const Diagnostic &in_stRight)
	{
		if (in_stLeft.strPath != in_stRight.strPath)
		{
			return in_stLeft.strPath < in_stRight.strPath;
		}
		return in_stLeft.strCode < in_stRight.strCode;
	});
}

} // namespace EngineNext::Assets
