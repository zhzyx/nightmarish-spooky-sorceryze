/**************************************************************************/
/*  ai_chat_resume.h                                                      */
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
#include "core/variant/array.h"
#include "core/variant/dictionary.h"

// Journal of the in-flight agent loop and of the restart handoff contract.
//
// Recompiling the editor can only take effect in a new process, so a rebuild is
// modelled as one very slow tool call: it is issued by the old process and its
// result is reported by the new one. The journal carries the exact loop position
// across that boundary, and the acknowledgement proves that the new executable
// reached a working AI dock rather than merely starting.
class AIChatResume {
public:
	static constexpr int VERSION = 1;
	// Bound both the on-disk envelope and the decoded JSON (also for legacy files).
	static constexpr uint64_t MAX_JOURNAL_BYTES = 16 * 1024 * 1024;
	static constexpr uint64_t MAX_UNCOMPRESSED_JOURNAL_BYTES = 64 * 1024 * 1024;
	// A handoff that keeps failing must stop instead of looping over restarts.
	static constexpr int MAX_RESTART_ATTEMPTS = 2;

	// Chat record validation shared by the journal and the saved chat history.
	static bool images_valid(const Variant &p_value);
	static bool records_valid(const Variant &p_value, bool p_transcript);
	static bool calls_valid(const Variant &p_value);

	static String journal_path();
	static String ack_path();
	static String report_path();
	// Globalized directory of the files above, for processes without res:// support.
	static String global_dir();

	static bool journal_valid(const Dictionary &p_journal);
	// Storage codec only: never summarizes messages or changes pending tool arguments.
	static Error encode_journal(const Dictionary &p_journal, String &r_body, Dictionary &r_stats);
	static bool decode_journal(const String &p_body, Dictionary &r_journal);
	static bool read_journal(Dictionary &r_journal);
	static Error write_journal(const Dictionary &p_journal, Dictionary *r_stats = nullptr);
	static void clear_journal();

	static Error write_ack(const String &p_token, const String &p_executable);
	static bool read_report(Dictionary &r_report);
	static void clear_report();

	// Correlates one handoff with one acknowledgement. Not a security secret.
	static String make_token();
	static bool token_valid(const String &p_token);
};
