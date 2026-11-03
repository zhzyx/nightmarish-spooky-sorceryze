// OpenAI wire adapters. Internal history always uses Chat Completions records.
#pragma once

#include "core/variant/array.h"
#include "core/variant/dictionary.h"

namespace AIChatOpenAI {
inline String endpoint(const String &p_url, bool p_responses) {
	if (!p_url.ends_with("/chat/completions") && !p_url.ends_with("/responses")) {
		return p_url;
	}
	return p_url.trim_suffix("/chat/completions").trim_suffix("/responses") + (p_responses ? "/responses" : "/chat/completions");
}

inline Dictionary responses_payload(const Dictionary &p_chat) {
	Dictionary result;
	result["model"] = p_chat["model"];
	result["stream"] = false;
	result["store"] = false;
	Array input;
	const Array messages = p_chat["messages"];
	for (const Variant &value : messages) {
		const Dictionary message = value;
		const String role = message["role"];
		if (role == "tool") {
			Dictionary item;
			item["type"] = "function_call_output";
			item["call_id"] = message["tool_call_id"];
			item["output"] = message["content"];
			input.push_back(item);
			continue;
		}
		const Variant content = message.get("content", Variant());
		if (content.get_type() == Variant::STRING && !String(content).is_empty()) {
			Dictionary item;
			item["role"] = role;
			item["content"] = content;
			input.push_back(item);
		} else if (content.get_type() == Variant::ARRAY) {
			Array parts;
			for (const Variant &part_value : Array(content)) {
				const Dictionary part = part_value;
				Dictionary converted;
				if (part.get("type", "") == "text") {
					converted["type"] = role == "assistant" ? "output_text" : "input_text";
					converted["text"] = part["text"];
				} else if (part.get("type", "") == "image_url") {
					converted["type"] = "input_image";
					converted["image_url"] = Dictionary(part["image_url"])["url"];
				} else {
					continue;
				}
				parts.push_back(converted);
			}
			Dictionary item;
			item["role"] = role;
			item["content"] = parts;
			input.push_back(item);
		}
		const Array calls = message.get("tool_calls", Array());
		for (const Variant &call_value : calls) {
			const Dictionary call = call_value;
			const Dictionary function = call["function"];
			Dictionary item;
			item["type"] = "function_call";
			item["call_id"] = call["id"];
			item["name"] = function["name"];
			item["arguments"] = function["arguments"];
			input.push_back(item);
		}
	}
	result["input"] = input;
	if (p_chat.has("tools")) {
		Array tools;
		for (const Variant &value : Array(p_chat["tools"])) {
			const Dictionary function = Dictionary(value)["function"];
			Dictionary tool = function.duplicate(true);
			tool["type"] = "function";
			// Existing Godot schemas use optional arguments.
			tool["strict"] = false;
			tools.push_back(tool);
		}
		result["tools"] = tools;
		result["tool_choice"] = "auto";
	}
	return result;
}

inline Dictionary chat_completion(const Dictionary &p_response) {
	// Never execute calls from a failed or truncated response.
	if (p_response.get("status", "") != "completed" || p_response.get("output", Variant()).get_type() != Variant::ARRAY) {
		return Dictionary();
	}
	String text;
	Array calls;
	for (const Variant &value : Array(p_response["output"])) {
		if (value.get_type() != Variant::DICTIONARY) {
			return Dictionary();
		}
		const Dictionary item = value;
		if (item.get("type", "") == "message") {
			if (item.get("content", Variant()).get_type() != Variant::ARRAY) {
				return Dictionary();
			}
			for (const Variant &part_value : Array(item["content"])) {
				if (part_value.get_type() != Variant::DICTIONARY) {
					return Dictionary();
				}
				const Dictionary part = part_value;
				if (part.get("type", "") == "output_text" || part.get("type", "") == "refusal") {
					text += String(part.get("text", part.get("refusal", "")));
				}
			}
		} else if (item.get("type", "") == "function_call") {
			for (const char *field : { "call_id", "name", "arguments" }) {
				if (item.get(field, Variant()).get_type() != Variant::STRING) {
					return Dictionary();
				}
			}
			Dictionary function;
			function["name"] = item["name"];
			function["arguments"] = item["arguments"];
			Dictionary call;
			call["id"] = item["call_id"];
			call["type"] = "function";
			call["function"] = function;
			calls.push_back(call);
		}
	}
	Dictionary message;
	message["role"] = "assistant";
	message["content"] = text;
	if (!calls.is_empty()) {
		message["tool_calls"] = calls;
	}
	Dictionary choice;
	choice["message"] = message;
	choice["finish_reason"] = calls.is_empty() ? "stop" : "tool_calls";
	Array choices;
	choices.push_back(choice);
	Dictionary result;
	result["choices"] = choices;
	return result;
}
} // namespace AIChatOpenAI
