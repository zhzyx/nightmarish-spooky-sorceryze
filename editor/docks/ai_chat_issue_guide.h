/**************************************************************************/
/*  ai_chat_issue_guide.h                                                 */
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

// Pure parsing for the in-conversation Issue guide. The guide never reaches a
// model or tool; it only helps bind a real Issue before the normal intake runs.
class AIChatIssueGuide {
public:
	static constexpr int MAX_REQUEST_ID = 80;
	static constexpr int MAX_TITLE = 120;

	static bool is_request_id(const String &p_id) {
		if (p_id.is_empty() || p_id.length() > MAX_REQUEST_ID || p_id.begins_with("-") || p_id.ends_with("-") || p_id.contains("--")) {
			return false;
		}
		for (int i = 0; i < p_id.length(); i++) {
			const char32_t c = p_id[i];
			if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-')) {
				return false;
			}
		}
		return true;
	}

	static bool is_bound(int64_t p_number, const String &p_request_id) {
		return p_number >= 1 && is_request_id(p_request_id);
	}

	// Only a missing/invalid local binding is guided; real intake rejections stay visible errors.
	static bool is_binding_error(const String &p_error) {
		return p_error.begins_with("Missing host request: request_id") || p_error.begins_with("Before development, create/reuse a real Issue");
	}

	// Accepts "#22 request-id", "22 request-id" and an optional leading "绑定"/"bind".
	static bool parse_binding(const String &p_text, int64_t &r_number, String &r_request_id) {
		PackedStringArray parts = p_text.strip_edges().replace("\t", " ").split(" ", false);
		if (parts.size() == 3 && (parts[0] == U"绑定" || parts[0].to_lower() == "bind")) {
			parts.remove_at(0);
		}
		if (parts.size() != 2) {
			return false;
		}
		String number = parts[0];
		if (number.begins_with("#")) {
			number = number.substr(1);
		}
		if (number.is_empty() || number.length() > 9) {
			return false;
		}
		for (int i = 0; i < number.length(); i++) {
			if (number[i] < '0' || number[i] > '9') {
				return false;
			}
		}
		const int64_t value = number.to_int();
		if (value < 1 || !is_request_id(parts[1])) {
			return false;
		}
		r_number = value;
		r_request_id = parts[1];
		return true;
	}

	static String suggest_title(const String &p_outcome) {
		for (const String &line : p_outcome.split("\n", false)) {
			const String title = line.strip_edges().trim_prefix("#").strip_edges();
			if (!title.is_empty()) {
				return title.left(MAX_TITLE);
			}
		}
		return U"Godot 编辑器会话需求";
	}

	// ASCII words of the title plus a timestamp keep the ID stable, readable and unique.
	static String suggest_request_id(const String &p_title, const String &p_stamp) {
		PackedStringArray words;
		String word;
		const String lower = p_title.to_lower();
		for (int i = 0; i <= lower.length(); i++) {
			const char32_t c = i < lower.length() ? lower[i] : U' ';
			if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
				word += c;
			} else if (!word.is_empty()) {
				words.push_back(word);
				word = String();
			}
		}
		String slug;
		for (int i = 0; i < words.size() && i < 5; i++) {
			slug += (slug.is_empty() ? "" : "-") + words[i];
		}
		if (slug.is_empty()) {
			slug = "godot-chat";
		}
		const int budget = MAX_REQUEST_ID - p_stamp.length() - 1;
		slug = slug.left(MAX(budget, 1)).rstrip("-");
		return slug + "-" + p_stamp;
	}

	// p_categories holds Dictionaries with "name" (without the type: prefix).
	static String category_from_reply(const String &p_reply, const Array &p_categories) {
		String reply = p_reply.strip_edges().to_lower().trim_prefix("type:");
		if (reply.is_valid_int()) {
			const int64_t index = reply.to_int();
			if (index >= 1 && index <= p_categories.size()) {
				return Dictionary(p_categories[index - 1]).get("name", "");
			}
			return String();
		}
		for (const Variant &value : p_categories) {
			const String name = Dictionary(value).get("name", "");
			if (!name.is_empty() && reply == name) {
				return name;
			}
		}
		return String();
	}

	static Array categories_from_labels(const Variant &p_labels) {
		Array result;
		if (p_labels.get_type() != Variant::ARRAY) {
			return result;
		}
		for (const Variant &value : Array(p_labels)) {
			if (value.get_type() != Variant::DICTIONARY) {
				continue;
			}
			const Dictionary label = value;
			const String name = label.get("name", "");
			if (name.begins_with("type:") && name.length() > 5) {
				Dictionary category;
				category["name"] = name.substr(5);
				category["description"] = label.get("description", "");
				result.push_back(category);
			}
		}
		return result;
	}

	static bool is_word(const String &p_text, const char32_t *const *p_words) {
		const String text = p_text.strip_edges().to_lower();
		for (int i = 0; p_words[i]; i++) {
			if (text == String(p_words[i])) {
				return true;
			}
		}
		return false;
	}

	static bool is_cancel(const String &p_text) {
		static const char32_t *const words[] = { U"取消", U"放弃", U"退出", U"cancel", U"quit", nullptr };
		return is_word(p_text, words);
	}
	static bool is_create(const String &p_text) {
		static const char32_t *const words[] = { U"新建", U"创建", U"new", U"create", U"2", nullptr };
		return is_word(p_text, words);
	}
	static bool is_reuse(const String &p_text) {
		static const char32_t *const words[] = { U"复用", U"已有", U"reuse", U"1", nullptr };
		return is_word(p_text, words);
	}
	static bool is_default(const String &p_text) {
		static const char32_t *const words[] = { U"默认", U"好", U"可以", U"ok", U"default", U"y", U"yes", nullptr };
		return is_word(p_text, words);
	}
	static bool is_confirm(const String &p_text) {
		static const char32_t *const words[] = { U"确认", U"确定", U"创建", U"confirm", U"y", U"yes", nullptr };
		return is_word(p_text, words);
	}
	static bool is_start(const String &p_text) {
		static const char32_t *const words[] = { U"开始", U"开工", U"start", nullptr };
		return is_word(p_text, words);
	}
	static bool is_retry(const String &p_text) {
		static const char32_t *const words[] = { U"已更新", U"已修改", U"重试", U"继续", U"retry", U"done", nullptr };
		return is_word(p_text, words);
	}
};
