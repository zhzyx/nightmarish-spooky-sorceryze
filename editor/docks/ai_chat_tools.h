/**************************************************************************/
/*  ai_chat_tools.h                                                       */
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

class AIChatTools {
public:
	static constexpr int MAX_SCRIPT_BYTES = 256 * 1024;
	static constexpr int MAX_READ_SCAN_BYTES = 16 * 1024 * 1024;
	static constexpr int MAX_CONTEXT_BYTES = 384 * 1024;
	static constexpr int MAX_REQUEST_BYTES = 1024 * 1024;

	static bool is_read_only_tool(const String &p_name);
	static bool compact_context(const Array &p_messages, Array &r_messages, Dictionary &r_stats);

	static bool normalize_script_path(const String &p_path, String &r_path);
	static bool resolve_script_path(const String &p_path, const String &p_root, String &r_absolute, String &r_error);
	static bool resolve_directory(const String &p_path, const String &p_root, String &r_absolute, String &r_error);
	static bool read_script(const String &p_absolute, String &r_content, String &r_error);
	static bool read_script_range(const String &p_absolute, int p_offset, int p_limit, Dictionary &r_result, String &r_error);
	static bool write_script(const String &p_absolute, const String &p_before, const String &p_after, bool p_existed, String &r_error, bool p_preserve_bom = true);
	// Local, per-turn text snapshots. No repository or external process is used.
	static bool save_snapshot(const String &p_path, const Dictionary &p_snapshot, String &r_error);
	static bool load_snapshot(const String &p_path, Dictionary &r_snapshot, String &r_error);
	static bool check_snapshot(const Dictionary &p_snapshot, String &r_error);
	static bool restore_snapshot(const Dictionary &p_snapshot, String &r_error);
	// Version transactions use exact before/after states, including file absence.
	static bool check_snapshot_transition(const Dictionary &p_snapshot, bool p_forward, String &r_error, bool p_recovery = false);
	static bool apply_snapshot_transition(const Dictionary &p_snapshot, bool p_forward, String &r_error, bool p_recovery = false);
};
