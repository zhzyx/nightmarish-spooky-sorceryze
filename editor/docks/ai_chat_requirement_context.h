/**************************************************************************/
/*  ai_chat_requirement_context.h                                         */
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
#include "core/variant/array.h"
#include "core/variant/dictionary.h"

// Select original visible records, never an inferred summary of user intent.
// Environment chatter must not displace user corrections merely by arriving later.
class AIChatRequirementContext {
	static bool read_record(const Array &p_transcript, int p_index, String &r_role, String &r_text) {
		if (p_index < 0 || p_index >= p_transcript.size() || p_transcript[p_index].get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary record = p_transcript[p_index];
		const Variant role = record.get("role", Variant());
		const Variant content = record.get("content", Variant());
		if (role.get_type() != Variant::STRING || content.get_type() != Variant::STRING) {
			return false;
		}
		r_role = role;
		r_text = content;
		return (r_role == "user" || r_role == "editor" || r_role == "assistant") && !r_text.strip_edges().is_empty();
	}

	static int preceding_reply(const Array &p_transcript, int p_user) {
		for (int i = p_user - 1; i >= 0; i--) {
			String role, text;
			if (!read_record(p_transcript, i, role, text)) {
				continue;
			}
			// Do not pair an answer with a reply preceding another user turn.
			return role == "user" ? -1 : i;
		}
		return -1;
	}

	static void keep(const Array &p_transcript, int p_index, Vector<int> &r_indices, Array &r_records, int &r_characters) {
		if (p_index < 0 || r_indices.find(p_index) >= 0 || r_records.size() >= MAX_RECORDS || r_characters >= MAX_CHARACTERS) {
			return;
		}
		String role, text;
		if (!read_record(p_transcript, p_index, role, text)) {
			return;
		}
		text = text.left(MIN(MAX_RECORD_CHARACTERS, MAX_CHARACTERS - r_characters));
		Dictionary entry;
		entry["role"] = role;
		entry["content"] = text;
		r_indices.push_back(p_index);
		r_records.push_back(entry);
		r_characters += text.length();
	}

public:
	static constexpr int MAX_RECORDS = 32;
	static constexpr int MAX_CHARACTERS = 16000;
	static constexpr int MAX_RECORD_CHARACTERS = 4000;

	// Called only when the host has actually consumed this user turn as an intake
	// transport retry. The selector must never infer that from the user's wording.
	static bool mark_transport_retry(Array &p_transcript, const String &p_text) {
		const int last = p_transcript.size() - 1;
		String role, text;
		if (!read_record(p_transcript, last, role, text) || role != "user" || text != p_text) {
			return false;
		}
		Dictionary record = p_transcript[last];
		record["requirements_transport_retry"] = true;
		p_transcript[last] = record;
		return true;
	}

	static Array select(const Array &p_transcript) {
		Vector<int> users;
		int latest_retry = -1;
		int latest_user = -1;
		for (int i = 0; i < p_transcript.size(); i++) {
			String role, text;
			if (!read_record(p_transcript, i, role, text) || role != "user") {
				continue;
			}
			latest_user = i;
			const Dictionary record = p_transcript[i];
			const Variant transport = record.get("requirements_transport_retry", Variant());
			if (transport.get_type() == Variant::BOOL && bool(transport)) {
				latest_retry = i;
			} else {
				// Equal user answers can refer to different questions; do not deduplicate them.
				users.push_back(i);
			}
		}

		Vector<int> indices;
		Array records;
		int characters = 0;
		// A recent "yes" must keep its actual question, even when older turns fill the budget.
		keep(p_transcript, latest_user, indices, records, characters);
		keep(p_transcript, preceding_reply(p_transcript, latest_user), indices, records, characters);
		for (int i = users.size() - 1; i >= 0; i--) {
			keep(p_transcript, users[i], indices, records, characters);
		}
		// Use remaining room for the replies associated with the retained user turns.
		for (int i = users.size() - 1; i >= 0; i--) {
			if (indices.find(users[i]) >= 0) {
				keep(p_transcript, preceding_reply(p_transcript, users[i]), indices, records, characters);
			}
		}
		// Transport retry commands are lower priority and only the newest one is needed.
		keep(p_transcript, latest_retry, indices, records, characters);

		Array result;
		for (int i = 0; i < p_transcript.size(); i++) {
			const int selected = indices.find(i);
			if (selected >= 0) {
				result.push_back(records[selected]);
			}
		}
		return result;
	}
};
