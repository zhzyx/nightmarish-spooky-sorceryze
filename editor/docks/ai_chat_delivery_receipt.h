/**************************************************************************/
/*  ai_chat_delivery_receipt.h                                            */
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

#include "core/math/math_funcs.h"
#include "core/variant/dictionary.h"

// Only the fixed finalizer's private result is passed here, never tool stdout.
class AIChatDeliveryReceipt {
	static bool number_is(const Variant &p_value, int64_t p_expected) {
		return (p_value.get_type() == Variant::INT || p_value.get_type() == Variant::FLOAT) && Math::is_finite(double(p_value)) && double(p_value) == double(p_expected);
	}

public:
	static bool matches(const Dictionary &p_value, const Dictionary &p_expected) {
		const String kind = p_expected.get("kind", "native_delivery_finalization");
		if (!number_is(p_value.get("schema_version", Variant()), 1) || p_value.get("kind", "") != kind) {
			return false;
		}
		const String expected_mode = p_expected.get("delivery_mode", "complete");
		if (expected_mode != "complete" && expected_mode != "slice") {
			return false;
		}
		if (p_value.has("delivery_mode") && p_value.get("delivery_mode", "") != expected_mode) {
			return false;
		}
		if (kind == "native_delivery_retry" && (p_value.get("host_action_request_id", "") != p_expected.get("host_action_request_id", "") || p_value.get("original_journal_sha256", "") != p_expected.get("original_journal_sha256", "") || p_value.get("host_instance_id", "") != p_expected.get("host_instance_id", "") || !number_is(p_value.get("engine_pid", Variant()), p_expected["engine_pid"]))) {
			return false;
		}
		for (const String &key : { String("owner"), String("snapshot_id"), String("nonce"), String("source_root") }) {
			if (p_value.get(key, Variant()).get_type() != Variant::STRING || p_value[key] != p_expected[key]) {
				return false;
			}
		}
		const Dictionary binding = p_expected["binding"];
		return number_is(p_value.get("generation", Variant()), p_expected["generation"]) && number_is(p_value.get("issue", Variant()), binding["issue"]) && p_value.get("request_id", "") == binding["request_id"] && p_value.get("completion_verified", Variant()).get_type() == Variant::BOOL && p_value.get("mutations_may_have_started", Variant()).get_type() == Variant::BOOL;
	}

	static bool completed(const Dictionary &p_value, const Dictionary &p_expected) {
		if (!matches(p_value, p_expected) || !bool(p_value["completion_verified"]) || p_value.get("host_facts", Variant()).get_type() != Variant::DICTIONARY || p_value.get("ci", Variant()).get_type() != Variant::ARRAY) {
			return false;
		}
		const String expected_mode = p_expected.get("delivery_mode", "complete");
		const Dictionary binding = p_expected["binding"];
		const Dictionary facts = p_value["host_facts"];
		if (facts.get("repository", "") != binding["repository"] || !number_is(facts.get("issue", Variant()), binding["issue"]) || facts.get("request_id", "") != binding["request_id"] || facts.get("candidate", "") != p_expected["expected_candidate"] || facts.get("signed_commit", "") != p_expected["expected_signed_commit"] || facts.get("pr_state", "") != "MERGED" || facts.get("pull_request", "") != "https://github.com/" + String(binding["repository"]) + "/pull/" + itos(p_expected["pr"]) || facts.get("delivered_paths_differ", Variant()).get_type() != Variant::ARRAY || !Array(facts["delivered_paths_differ"]).is_empty()) {
			return false;
		}
		for (const String &key : { String("tree"), String("current_main"), String("merge_commit") }) {
			const String value = facts.get(key, "");
			if (value.length() != 40 || !value.is_valid_hex_number(false)) {
				return false;
			}
		}
		if (facts.get("issue_receipt", Variant()).get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary issue = facts["issue_receipt"];
		if (issue.get("labels", Variant()).get_type() != Variant::ARRAY) {
			return false;
		}
		const Array labels = issue["labels"];
		int statuses = 0;
		for (const Variant &label : labels) {
			if (label.get_type() != Variant::STRING) {
				return false;
			}
			statuses += String(label).begins_with("status:") ? 1 : 0;
		}
		if (expected_mode == "slice") {
			if (issue.get("state", "") != "OPEN" || statuses != 1 || !(labels.has("status:in-progress") || labels.has("status:in-review")) || !labels.has("workspace:gonggong")) {
				return false;
			}
		} else {
			if (issue.get("state", "") != "CLOSED" || issue.get("reason", "") != "COMPLETED" || statuses != 1 || !labels.has("status:done") || !labels.has("workspace:gonggong")) {
				return false;
			}
		}
		const Array checks = p_value["ci"];
		if (checks.is_empty()) {
			return false;
		}
		for (const Variant &entry : checks) {
			if (entry.get_type() != Variant::DICTIONARY) {
				return false;
			}
			const String state = Dictionary(entry).get("state", "");
			if (state != "SUCCESS" && state != "SKIPPED") {
				return false;
			}
		}
		return true;
	}
};
