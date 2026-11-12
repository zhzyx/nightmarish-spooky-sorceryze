/**************************************************************************/
/*  TestScriptIterator.h                                                  */
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

// Included by script_iterator.cpp so this test uses the module's private dependencies.
#pragma once

#include "../script_iterator.h"

#include "tests/test_macros.h"

namespace TestScriptIterator
{

TEST_CASE("[TextServer] Bracket pairing survives stack growth")
{
	// 128 entries fit locally; 129 moves to the heap; 257 grows it again.
	for (int nOuterDepth : { 1, 127, 128, 256 })
	{
		CAPTURE(nOuterDepth);
		String strOpening;
		String strClosing;
		for (int nIndex = 0; nIndex < nOuterDepth; nIndex++)
		{
			strOpening += (nIndex % 2 == 0) ? "(" : "[";
			strClosing = String((nIndex % 2 == 0) ? ")" : "]") + strClosing;
		}
		// The inner Greek bracket triggers growth while the outer Latin
		// brackets are still live. Their closers must return to Latin.
		const String strLatin = strOpening + "a";
		const String strGreek = U"α{β}";
		const String strText = strLatin + strGreek + strClosing;
		const ScriptIterator scriptIterator(strText, 0, strText.length());
		REQUIRE(scriptIterator.script_ranges.size() == 3);
		if (scriptIterator.script_ranges.size() != 3)
		{
			continue;
		}
		CHECK(scriptIterator.script_ranges[0].start == 0);
		CHECK(scriptIterator.script_ranges[0].end == strLatin.length());
		CHECK(scriptIterator.script_ranges[0].script == HB_SCRIPT_LATIN);
		CHECK(scriptIterator.script_ranges[1].start == strLatin.length());
		CHECK(scriptIterator.script_ranges[1].end == strLatin.length() + strGreek.length());
		CHECK(scriptIterator.script_ranges[1].script == HB_SCRIPT_GREEK);
		CHECK(scriptIterator.script_ranges[2].start == strLatin.length() + strGreek.length());
		CHECK(scriptIterator.script_ranges[2].end == strText.length());
		CHECK(scriptIterator.script_ranges[2].script == HB_SCRIPT_LATIN);
	}
}

} // namespace TestScriptIterator
