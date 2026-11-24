/**************************************************************************/
/*  ImeComposition.h                                                      */
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

#include "core/string/ustring.h"
#include "core/templates/vector.h"

#ifdef WINDOWS_ENABLED
#include <windows.h>

#include <imm.h>
#endif

namespace WindowsIme
{
// Bound a single in-progress composition before allocating from an IMM size query.
constexpr int32_t MAX_COMPOSITION_BYTES = 1024 * 1024;
constexpr int32_t UNIT_BYTES = sizeof(char16_t);

inline bool IsValidByteCount(int32_t nBytes, int32_t nCapacityBytes)
{
	return nBytes > 0 && nBytes <= nCapacityBytes && nBytes % UNIT_BYTES == 0;
}

struct Composition
{
	String strText;
	int32_t nCursor = 0;
};

template <typename Reader>
Composition ReadComposition(Reader readBytes, int32_t nCursor)
{
	const int32_t nCapacityBytes = readBytes(nullptr, 0);
	if (!IsValidByteCount(nCapacityBytes, MAX_COMPOSITION_BYTES))
	{
		return {};
	}
	Vector<char16_t> arrUnits;
	if (arrUnits.resize(nCapacityBytes / UNIT_BYTES) != OK)
	{
		return {};
	}
	const int32_t nBytes = readBytes(arrUnits.ptrw(), nCapacityBytes);
	if (!IsValidByteCount(nBytes, nCapacityBytes))
	{
		return {};
	}

	const int32_t nUnits = nBytes / UNIT_BYTES;
	const char16_t *pUnits = arrUnits.ptr();
	Composition stResult;
	if (stResult.strText.resize_uninitialized(nUnits + 1) != OK)
	{
		return {};
	}
	char32_t *pText = stResult.strText.ptrw();
	int32_t nCharacters = 0;
	for (int32_t nOffset = 0; nOffset < nUnits;)
	{
		char32_t nCharacter = pUnits[nOffset++];
		if (nCharacter >= 0xd800 && nCharacter <= 0xdbff)
		{
			if (nOffset == nUnits || pUnits[nOffset] < 0xdc00 || pUnits[nOffset] > 0xdfff)
			{
				return {};
			}
			nCharacter = 0x10000 + ((nCharacter - 0xd800) << 10) + (pUnits[nOffset++] - 0xdc00);
		}
		else if (nCharacter == 0 || (nCharacter >= 0xdc00 && nCharacter <= 0xdfff))
		{
			return {};
		}
		pText[nCharacters++] = nCharacter;
		// Count only complete scalars before the UTF-16 cursor, including when the read shrinks.
		if (nOffset <= nCursor)
		{
			stResult.nCursor = nCharacters;
		}
	}
	pText[nCharacters] = 0;
	if (stResult.strText.resize_uninitialized(nCharacters + 1) != OK)
	{
		return {};
	}
	return stResult;
}

#ifdef WINDOWS_ENABLED
inline Composition ReadNativeComposition(HIMC hContext, bool bReadCursor)
{
	if (!hContext)
	{
		return {};
	}
	const LONG nCursor = bReadCursor ? ImmGetCompositionStringW(hContext, GCS_CURSORPOS, nullptr, 0) : 0;
	const auto readBytes = [hContext](char16_t *pBuffer, uint32_t nCapacityBytes)
	{
		return ImmGetCompositionStringW(hContext, GCS_COMPSTR, pBuffer, nCapacityBytes);
	};
	return ReadComposition(readBytes, nCursor);
}
#endif
} // namespace WindowsIme
