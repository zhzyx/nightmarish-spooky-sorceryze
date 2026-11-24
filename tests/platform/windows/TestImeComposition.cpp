/**************************************************************************/
/*  TestImeComposition.cpp                                                */
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

#include "tests/test_macros.h"

#include "platform/windows/ime/ImeComposition.h"

TEST_FORCE_LINK(TestImeComposition)

namespace TestImeComposition
{
// Each mock writes only the available sample units that fit in the supplied buffer.
struct Sample
{
	const char16_t *pUnits;
	int32_t nUnits;
	int32_t nQueryBytes;
	int32_t nReadBytes;
	int32_t nReads = 0;

	int32_t Read(char16_t *pBuffer, uint32_t nCapacityBytes)
	{
		if (!pBuffer)
		{
			return nQueryBytes;
		}
		++nReads;
		const uint32_t nCapacity = nCapacityBytes / WindowsIme::UNIT_BYTES;
		for (int32_t nIndex = 0; nIndex < nUnits && static_cast<uint32_t>(nIndex) < nCapacity; ++nIndex)
		{
			pBuffer[nIndex] = pUnits[nIndex];
		}
		return nReadBytes;
	}

	WindowsIme::Composition Get(int32_t nCursor = 0)
	{
		const auto readBytes = [this](char16_t *pBuffer, uint32_t nCapacityBytes)
		{
			return Read(pBuffer, nCapacityBytes);
		};
		return WindowsIme::ReadComposition(readBytes, nCursor);
	}
};

TEST_CASE("[Windows][IME] Composition uses only whole UTF-16 units reported by the second read")
{
	Sample stSample{ u"漢A", 2, 4, 2 };
	CHECK(stSample.Get().strText == U"漢");
	CHECK(stSample.nReads == 1);

	for (int32_t nBytes : { -1, 0, 1, WindowsIme::MAX_COMPOSITION_BYTES + 2 })
	{
		stSample.nQueryBytes = nBytes;
		CHECK(stSample.Get().strText.is_empty());
		CHECK(stSample.nReads == 1);
	}
	stSample.nQueryBytes = 4;
	for (int32_t nBytes : { -1, 0, 3, 6 })
	{
		stSample.nReadBytes = nBytes;
		CHECK(stSample.Get().strText.is_empty());
		CHECK(stSample.Get(2).nCursor == 0);
	}
}

TEST_CASE("[Windows][IME] Cursor counts complete Unicode scalar values")
{
	Sample stSample{ u"漢\U0001f642Z", 4, 8, 8 };
	CHECK(stSample.Get().strText == U"漢\U0001f642Z");
	const int32_t arrExpected[] = { 0, 0, 1, 1, 2, 3, 3 };
	for (int32_t nIndex = 0; nIndex < 7; ++nIndex)
	{
		CHECK(stSample.Get(nIndex - 1).nCursor == arrExpected[nIndex]);
	}

	stSample.nReadBytes = 2;
	CHECK(stSample.Get(4).nCursor == 1);
}

TEST_CASE("[Windows][IME] Incomplete scalars yield empty text and selection")
{
	const char16_t arrUnits[][2] = {
		{ u'A', 0xd800 },
		{ 0xd800, u'A' },
		{ 0xdc00, u'A' },
		{ 0xd800, 0xd800 },
		{ 0, u'A' },
	};
	for (const char16_t (&arrSample)[2] : arrUnits)
	{
		Sample stSample{ arrSample, 2, 4, 4 };
		CHECK(stSample.Get().strText.is_empty());
		CHECK(stSample.Get(2).nCursor == 0);
	}
}

#ifdef WINDOWS_ENABLED
TEST_CASE("[Windows][IME] Native reads tolerate an absent or empty input context")
{
	CHECK(WindowsIme::ReadNativeComposition(nullptr, true).nCursor == 0);
	CHECK(WindowsIme::ReadNativeComposition(nullptr, false).strText.is_empty());

	const HIMC hContext = ImmCreateContext();
	REQUIRE(hContext != nullptr);
	const WindowsIme::Composition stEmpty = WindowsIme::ReadNativeComposition(hContext, true);
	CHECK(stEmpty.strText.is_empty());
	CHECK(stEmpty.nCursor == 0);
	CHECK(ImmDestroyContext(hContext));
}
#endif
} // namespace TestImeComposition
