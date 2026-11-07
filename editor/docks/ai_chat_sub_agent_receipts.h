/**************************************************************************/
/*  ai_chat_sub_agent_receipts.h                                          */
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

#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/string/ustring.h"
#include "core/variant/dictionary.h"

// Summarizes host callbacks, never child claims or tool arguments. The caller
// supplies the redacted result and owns bounded storage and call/history refs.
class AIChatSubAgentReceipts {
	static bool known_tool(const String &p_tool) {
		return p_tool == "read_logs" || p_tool == "list_scripts" || p_tool == "read_script" || p_tool == "write_script" || p_tool == "check_script" || p_tool == "run_test" || p_tool == "read_file" || p_tool == "write_file" || p_tool == "list_directory" || p_tool == "run_command" || p_tool == "build_engine" || p_tool == "restart_engine" || p_tool == "rollback_engine" || p_tool == "get_parent_context" || p_tool == "get_editor_state" || p_tool == "editor_action" || p_tool == "route_engine_message";
	}

	static Variant boolean_field(const Dictionary &p_value, const String &p_key) {
		const Variant value = p_value.get(p_key, Variant());
		return value.get_type() == Variant::BOOL ? value : Variant();
	}

	static Variant exit_code(const Variant &p_value) {
		if (p_value.get_type() != Variant::INT && p_value.get_type() != Variant::FLOAT) {
			return Variant();
		}
		const double value = p_value;
		if (!Math::is_finite(value) || value < -2147483648.0 || value > 4294967295.0 || value != Math::floor(value)) {
			return Variant();
		}
		return int64_t(value);
	}

public:
	static constexpr int MAX_RECEIPTS_PER_CHILD = 24;
	static constexpr int MAX_CHILD_RECEIPT_BYTES = 12 * 1024;
	static constexpr int MAX_PARENT_RECEIPT_BYTES = 64 * 1024;
	static constexpr int MAX_RESULT_PARSE_BYTES = 512 * 1024;

	static Dictionary summarize(const String &p_tool, const String &p_result, bool p_file_success, bool p_native_terminal = false) {
		Dictionary receipt;
		receipt["source"] = "host_callback";
		receipt["tool"] = known_tool(p_tool) ? p_tool : p_native_terminal ? String("native_terminal")
																		  : String("unknown");
		receipt["result_sha256"] = p_result.sha256_text();
		receipt["result_bytes"] = p_result.utf8().length();
		receipt["phase"] = "host_result";
		receipt["ok"] = Variant();
		receipt["exit_code"] = Variant();
		receipt["timed_out"] = Variant();
		receipt["start_failed"] = Variant();
		receipt["business_accepted"] = Variant();

		// File contents can contain arbitrary JSON and even an Error: prefix.
		// Only the host's separate success flag establishes a file result.
		const bool file_tool = p_tool == "read_file" || p_tool == "read_script" || p_tool == "write_file" || p_tool == "write_script";
		if (file_tool && !p_native_terminal) {
			receipt["phase"] = !p_file_success && p_result.begins_with("Error:") ? "host_error" : "file_result";
			receipt["ok"] = p_file_success;
			return receipt;
		}
		if (!p_file_success && p_result.begins_with("Error:")) {
			receipt["phase"] = "host_error";
			receipt["ok"] = false;
			return receipt;
		}
		if ((!known_tool(p_tool) && !p_native_terminal) || int64_t(receipt["result_bytes"]) > MAX_RESULT_PARSE_BYTES) {
			return receipt;
		}
		JSON json;
		if (json.parse(p_result) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
			return receipt;
		}
		const Dictionary result = json.get_data();
		if (result.get("approved", Variant()).get_type() == Variant::BOOL && bool(result["approved"])) {
			receipt["phase"] = "approval";
			return receipt;
		}

		const bool process_tool = p_tool == "run_command" || p_tool == "check_script" || p_tool == "run_test";
		if (p_native_terminal || process_tool) {
			Dictionary status = result;
			Dictionary flags = result;
			if (p_native_terminal) {
				const Variant status_value = result.get("exit_status", Variant());
				if (status_value.get_type() != Variant::DICTIONARY) {
					return receipt;
				}
				status = status_value;
				const Variant meta = status.get("_meta", Variant());
				flags = meta.get_type() == Variant::DICTIONARY ? Dictionary(meta) : Dictionary();
			}
			const Variant code = exit_code(status.get(p_native_terminal ? "exitCode" : "exit_code", Variant()));
			const Variant timed_out = boolean_field(flags, "timed_out");
			const Variant start_failed = boolean_field(flags, "start_failed");
			const Variant signal = p_native_terminal ? status.get("signal", Variant()) : Variant();
			const bool signaled = signal.get_type() == Variant::STRING && !String(signal).is_empty();
			if (code.get_type() == Variant::NIL && timed_out.get_type() == Variant::NIL && start_failed.get_type() == Variant::NIL && !signaled) {
				return receipt;
			}
			receipt["phase"] = "execution";
			receipt["exit_code"] = code;
			receipt["timed_out"] = timed_out;
			receipt["start_failed"] = start_failed;
			if (signaled || (timed_out.get_type() == Variant::BOOL && bool(timed_out)) || (start_failed.get_type() == Variant::BOOL && bool(start_failed))) {
				receipt["ok"] = false;
			} else if (code.get_type() == Variant::INT) {
				receipt["ok"] = int64_t(code) == 0;
			}
			return receipt;
		}
		receipt["ok"] = boolean_field(result, "ok");
		return receipt;
	}
};
