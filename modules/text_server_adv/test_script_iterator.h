/**************************************************************************/
/*  test_script_iterator.h                                                */
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

#include "script_iterator.h"
#include "tests/test_macros.h"

namespace TestScriptIterator {

TEST_CASE("[TextServer] Bracket pairing survives stack growth") {
	// 128 entries fit locally; 129 moves to the heap; 257 grows it again.
	for (int outer_depth : { 1, 127, 128, 256 }) {
		CAPTURE(outer_depth);
		String opening;
		String closing;
		for (int i = 0; i < outer_depth; i++) {
			opening += (i % 2 == 0) ? "(" : "[";
			closing = String((i % 2 == 0) ? ")" : "]") + closing;
		}
		// The inner Greek bracket triggers growth while the outer Latin
		// brackets are still live. Their closers must return to Latin.
		const String latin = opening + "a";
		const String greek = U"α{β}";
		const String text = latin + greek + closing;
		const ScriptIterator iterator(text, 0, text.length());
		REQUIRE(iterator.script_ranges.size() == 3);
		if (iterator.script_ranges.size() != 3) {
			continue;
		}
		CHECK(iterator.script_ranges[0].start == 0);
		CHECK(iterator.script_ranges[0].end == latin.length());
		CHECK(iterator.script_ranges[0].script == HB_SCRIPT_LATIN);
		CHECK(iterator.script_ranges[1].start == latin.length());
		CHECK(iterator.script_ranges[1].end == latin.length() + greek.length());
		CHECK(iterator.script_ranges[1].script == HB_SCRIPT_GREEK);
		CHECK(iterator.script_ranges[2].start == latin.length() + greek.length());
		CHECK(iterator.script_ranges[2].end == text.length());
		CHECK(iterator.script_ranges[2].script == HB_SCRIPT_LATIN);
	}
}

} // namespace TestScriptIterator
