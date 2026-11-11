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

	// These backends have host-enforced read-only transport boundaries.
	static bool supports_read_only_backend(int p_backend) {
		return p_backend >= 0 && p_backend <= 3;
	}

	static bool is_state(const String &p_state) {
		return p_state == "manual" || p_state == "waiting" || p_state == "pending_host" || p_state == "running" || p_state == "review" || p_state == "completed" || p_state == "failed" || p_state == "interrupted";
	}

	static String state_text(const String &p_state) {
		if (p_state == "pending_host") {
			return U"已提交，等待宿主回执";
		}
		if (p_state == "review") {
			return U"已执行，待验收";
		}
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

	// Accept individual earlier order numbers and inclusive ranges used by legacy designs.
	static bool parse_dependencies(String p_value, const Array &p_prior, Array &r_dependencies) {
		p_value = p_value.strip_edges().trim_suffix(U"。").strip_edges();
		if (p_value == U"无") {
			return true;
		}
		p_value = p_value.replace(U"工单", "").replace(U"、", ",").replace(U"，", ",").replace(U"–", "-").replace(U"—", "-");
		for (const String &part : p_value.split(",")) {
			const Vector<String> ends = part.strip_edges().split("-");
			if (ends.is_empty() || ends.size() > 2 || !ends[0].strip_edges().is_valid_int() || !ends[ends.size() - 1].strip_edges().is_valid_int()) {
				return false;
			}
			const int64_t first = ends[0].strip_edges().to_int();
			const int64_t last = ends[ends.size() - 1].strip_edges().to_int();
			if (first < 1 || last < first || last > 999 || last - first >= MAX_CHILDREN_PER_PARENT) {
				return false;
			}
			for (int number = first; number <= last; number++) {
				if (!p_prior.has(number)) {
					return false;
				}
				if (!r_dependencies.has(number)) {
					r_dependencies.push_back(number);
				}
			}
		}
		return !p_value.is_empty();
	}

	static Dictionary parse_work_orders(const String &p_document) {
		Dictionary result;
		bool confirmation_section = false;
		bool valid = true;
		Array prior;
		Array dependencies;
		bool in_section = false;
		Array orders;
		Dictionary current;
		String body;
		const Vector<String> lines = p_document.replace("\r\n", "\n").replace("\r", "\n").split("\n");
		auto flush = [&]() {
			if (current.is_empty()) {
				return;
			}
			current["dependencies"] = dependencies;
			dependencies = Array();
			prior.push_back(current["number"]);
			current["body"] = body.strip_edges().left(MAX_WORK_ORDER_CHARS);
			Array criteria;
			Array ids;
			bool criteria_valid = true;
			for (const String &line : body.split("\n")) {
				const String field = line.strip_edges().trim_prefix("- ").replace(U"：", ":");
				if (!field.begins_with(U"验收:")) {
					continue;
				}
				const Vector<String> parts = field.substr(field.find(":") + 1).split("|");
				if (parts.size() != 2 || parts[0].strip_edges().is_empty() || parts[1].strip_edges().is_empty() || ids.has(parts[0].strip_edges())) {
					criteria_valid = false;
					continue;
				}
				Dictionary criterion;
				criterion["id"] = parts[0].strip_edges();
				criterion["requirement"] = parts[1].strip_edges();
				ids.push_back(criterion["id"]);
				criteria.push_back(criterion);
			}
			current["acceptance_criteria"] = criteria;
			current["acceptance_criteria_valid"] = criteria_valid && !criteria.is_empty();
			orders.push_back(current);
			current = Dictionary();
			body = String();
		};
		for (const String &line : lines) {
			const String stripped = line.strip_edges();
			if (stripped.begins_with("#")) {
				const String dated = stripped.trim_prefix(U"## 设计定版确认（").trim_suffix(U"）");
				const String digits = dated.replace("-", "");
				const bool date_suffix = dated.length() == 10 && dated[4] == '-' && dated[7] == '-' &&
						digits.length() == 8 && !digits.begins_with("+") && digits.is_valid_int();
				if (stripped == U"## 设计定版确认" || stripped == U"## 设计定版确认：当前操作者代表任务" ||
						(stripped == String(U"## 设计定版确认（") + dated + U"）" && date_suffix)) {
					confirmation_section = true;
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
					valid = false;
					break;
				}
				valid = valid && number > 0 && !prior.has(number);
				current["number"] = number;
				current["title"] = title;
				continue;
			}
			if (!current.is_empty()) {
				const String field = stripped.trim_prefix("- ").strip_edges().replace(U"：", ":");
				if (field.begins_with(U"依赖:") || field.begins_with(U"业务依赖:")) {
					valid = parse_dependencies(field.substr(field.find(":") + 1), prior, dependencies) && valid;
				}
				body += line + "\n";
			}
		}
		if (in_section) {
			flush();
		}
		result["confirmation_section"] = confirmation_section;
		result["valid"] = valid;
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
		String prompt = vformat(U"你是父 Agent「%s」派生的子 Agent，负责落地生产工单 %d（第 %d 项，共 %d 项）：%s\n\n", p_parent, int(p_work_order["number"]), p_order, p_total, String(p_work_order.get("title", "")));
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
