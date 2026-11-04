/**************************************************************************/
/*  ai_chat_sub_agents.h                                                  */
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
#include "core/variant/variant.h"

// Pure helpers for child Agents. Children are host UI sessions that live in
// their parent's window; they are not registered GongGong framework Agents.
class AIChatSubAgents {
public:
	static constexpr int MAX_CHILDREN_PER_PARENT = 16;
	static constexpr int MAX_CHILDREN = 128;
	static constexpr int MAX_WORK_ORDER_CHARS = 8192;
	static constexpr int MAX_TITLE_CHARS = 24;
	static constexpr int MAX_CONTEXT_RECORDS = 40;
	static constexpr int MAX_CONTEXT_RECORD_CHARS = 8000;
	static constexpr int MAX_CONTEXT_BYTES = 48 * 1024;

	static bool is_state(const String &p_state) {
		return p_state == "manual" || p_state == "waiting" || p_state == "running" || p_state == "completed" || p_state == "failed" || p_state == "interrupted";
	}

	static String state_text(const String &p_state) {
		if (p_state == "waiting") {
			return U"等待执行";
		}
		if (p_state == "running") {
			return U"执行中";
		}
		if (p_state == "completed") {
			return U"已完成";
		}
		if (p_state == "failed") {
			return U"失败／已停止";
		}
		if (p_state == "interrupted") {
			return U"已中断，未自动重跑";
		}
		return U"手动子 Agent";
	}

	static bool parse_numbered(const String &p_line, int &r_number, String &r_title) {
		int i = 0;
		while (i < p_line.length() && i < 3 && p_line[i] >= '0' && p_line[i] <= '9') {
			i++;
		}
		if (i == 0 || i + 1 >= p_line.length() || p_line[i] != '.' || p_line[i + 1] != ' ') {
			return false;
		}
		const String title = p_line.substr(i + 2).strip_edges();
		if (title.is_empty()) {
			return false;
		}
		r_number = p_line.substr(0, i).to_int();
		r_title = title;
		return true;
	}

	// A finalized design document has a "设计定版确认" heading and a
	// "## 生产工单" section whose top-level numbered items are the work orders.
	static Dictionary parse_work_orders(const String &p_document) {
		Dictionary result;
		bool finalized = false;
		bool in_section = false;
		Array orders;
		Dictionary current;
		String body;
		const Vector<String> lines = p_document.replace("\r\n", "\n").replace("\r", "\n").split("\n");
		auto flush = [&]() {
			if (current.is_empty()) {
				return;
			}
			current["body"] = body.strip_edges().left(MAX_WORK_ORDER_CHARS);
			orders.push_back(current);
			current = Dictionary();
			body = String();
		};
		for (const String &line : lines) {
			const String stripped = line.strip_edges();
			if (stripped.begins_with("#")) {
				if (stripped.contains(U"设计定版确认")) {
					finalized = true;
				}
				if (stripped.begins_with("# ") || stripped.begins_with("## ")) {
					if (in_section) {
						flush();
					}
					in_section = stripped.begins_with(U"## 生产工单");
					continue;
				}
			}
			if (!in_section) {
				continue;
			}
			int number = 0;
			String title;
			const bool indented = line.begins_with(" ") || line.begins_with("\t");
			if (!indented && parse_numbered(line, number, title)) {
				flush();
				if (orders.size() >= MAX_CHILDREN_PER_PARENT) {
					break;
				}
				current["number"] = number;
				current["title"] = title;
				continue;
			}
			if (!current.is_empty()) {
				body += line + "\n";
			}
		}
		if (in_section) {
			flush();
		}
		result["finalized"] = finalized;
		result["orders"] = orders;
		return result;
	}

	static String tab_title(int p_order, const String &p_title) {
		const String source = p_title.strip_edges();
		String title;
		for (int i = 0; i < source.length(); i++) {
			title += (source[i] < 32 || source[i] == 127) ? char32_t(' ') : source[i];
		}
		if (title.length() > MAX_TITLE_CHARS) {
			title = title.left(MAX_TITLE_CHARS - 1) + U"…";
		}
		return vformat(U"子%d · %s", p_order, title);
	}

	static String work_order_prompt(const String &p_parent, int p_order, int p_total, const Dictionary &p_work_order, int64_t p_issue, const String &p_request_id) {
		String prompt = vformat(U"你是父 Agent「%s」派生的子 Agent，负责落地生产工单 %d/%d：%s\n\n", p_parent, p_order, p_total, String(p_work_order.get("title", "")));
		const String body = p_work_order.get("body", "");
		if (!body.is_empty()) {
			prompt += body + "\n\n";
		}
		prompt += vformat(U"绑定：Issue #%d，需求 ID %s，需求文档 design-docs/%s.md。设计已定版，直接实施本工单，不重新设计、不重复提问已确认的内容。\n", p_issue, p_request_id, p_request_id);
		prompt += U"要求：只实现本工单范围；前序工单由前面的子 Agent 完成，先读取代码现状再动手。需要父会话的结论或上下文时调用 get_parent_context（CodeBuddy CLI 下执行 Bash 命令 godot-host-action get_parent_context）。完成后汇报改动文件、实际验证结果与未决问题；没有工具成功结果不得声称已完成。";
		return prompt;
	}

	// Recent visible records only, newest kept, bounded by count and bytes.
	static Dictionary parent_context(const Array &p_transcript) {
		Array records;
		int bytes = 0;
		bool truncated = false;
		for (int i = p_transcript.size() - 1; i >= 0; i--) {
			if (p_transcript[i].get_type() != Variant::DICTIONARY) {
				continue;
			}
			const Dictionary record = p_transcript[i];
			const String role = record.get("role", "");
			if (role != "user" && role != "assistant" && role != "editor") {
				continue;
			}
			if (records.size() >= MAX_CONTEXT_RECORDS) {
				truncated = true;
				break;
			}
			String content = record.get("content", "");
			if (content.length() > MAX_CONTEXT_RECORD_CHARS) {
				content = content.left(MAX_CONTEXT_RECORD_CHARS) + U"\n[节选：本条已截断]";
				truncated = true;
			}
			const int size = content.utf8().length();
			if (bytes + size > MAX_CONTEXT_BYTES) {
				truncated = true;
				break;
			}
			bytes += size;
			Dictionary item;
			item["role"] = role;
			item["content"] = content;
			records.push_front(item);
		}
		Dictionary result;
		result["records"] = records;
		result["truncated"] = truncated;
		result["bytes"] = bytes;
		return result;
	}
};
