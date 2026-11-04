/**************************************************************************/
/*  test_ai_chat_openai.cpp                                               */
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

#include "tests/test_macros.h"
TEST_FORCE_LINK(test_ai_chat_openai)

#ifdef TOOLS_ENABLED
#include "core/io/json.h"
#include "editor/docks/ai_chat_openai.h"

namespace TestAIChatOpenAI {
Dictionary parse(const String &p_json) {
	return JSON::parse_string(p_json);
}

TEST_CASE("[AIChat] Responses tool loop preserves call IDs and image inputs") {
	const Dictionary chat = parse(R"({"model":"test","messages":[
		{"role":"system","content":"instructions"},
		{"role":"user","content":[{"type":"text","text":"look"},{"type":"image_url","image_url":{"url":"data:image/png;base64,AA=="}}]},
		{"role":"assistant","content":null,"tool_calls":[{"id":"call_1","type":"function","function":{"name":"read_file","arguments":"{}"}}]},
		{"role":"tool","tool_call_id":"call_1","content":"file data"}
	],"tools":[{"type":"function","function":{"name":"read_file","parameters":{"type":"object","properties":{}}}}]})");
	const Dictionary payload = AIChatOpenAI::responses_payload(chat);
	CHECK_FALSE(bool(payload["store"]));
	const Array items = payload["input"];
	REQUIRE(items.size() == 4);
	CHECK(Dictionary(items[2])["call_id"] == "call_1");
	CHECK(Dictionary(items[3])["type"] == "function_call_output");
	CHECK(Dictionary(items[3])["output"] == "file data");
	const Array parts = Dictionary(items[1])["content"];
	CHECK(Dictionary(parts[1])["type"] == "input_image");
	const Array tools = payload["tools"];
	CHECK(Dictionary(tools[0])["name"] == "read_file");
	CHECK_FALSE(bool(Dictionary(tools[0])["strict"]));
}

TEST_CASE("[AIChat] Responses results normalize text and tool calls and reject incomplete output") {
	const Dictionary response = parse(R"({"status":"completed","output":[
		{"type":"reasoning","summary":[]},
		{"type":"message","content":[{"type":"output_text","text":"hello"}]},
		{"type":"function_call","call_id":"call_2","name":"read_file","arguments":"{}"}
	]})");
	const Dictionary normalized = AIChatOpenAI::chat_completion(response);
	const Dictionary choice = Array(normalized["choices"])[0];
	const Dictionary message = choice["message"];
	CHECK(message["content"] == "hello");
	const Array calls = message["tool_calls"];
	CHECK(Dictionary(calls[0])["id"] == "call_2");
	Dictionary incomplete = response.duplicate(true);
	incomplete["status"] = "incomplete";
	CHECK(AIChatOpenAI::chat_completion(incomplete).is_empty());
	CHECK(AIChatOpenAI::chat_completion(parse(R"({"status":"completed","output":[{"type":"function_call","name":"bad"}]})")).is_empty());
}

TEST_CASE("[AIChat] OpenAI endpoints select the wire protocol and preserve custom URLs") {
	CHECK(AIChatOpenAI::endpoint("https://api.openai.com/v1/chat/completions", true) == "https://api.openai.com/v1/responses");
	CHECK(AIChatOpenAI::endpoint("https://api.openai.com/v1/responses", false) == "https://api.openai.com/v1/chat/completions");
	CHECK(AIChatOpenAI::endpoint("http://localhost:8000/custom", false) == "http://localhost:8000/custom");
}
} // namespace TestAIChatOpenAI
#endif
