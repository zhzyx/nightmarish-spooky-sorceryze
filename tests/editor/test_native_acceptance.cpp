/**************************************************************************/
/*  test_native_acceptance.cpp                                            */
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
TEST_FORCE_LINK(test_native_acceptance)
#ifdef TOOLS_ENABLED
#include "editor/docks/ai_chat_sub_agent_receipts.h"
#include "editor/docks/ai_chat_sub_agents.h"
namespace TestNativeAcceptance {
static Dictionary order(const String &p_body) {
	const Dictionary parsed = AIChatSubAgents::parse_work_orders(String(U"## 设计定版确认\n确认\n## 生产工单\n1. task\n") + p_body);
	return Array(parsed["orders"])[0];
}
TEST_CASE("[Editor][NativeAcceptance] Exact explicit criteria are retained") {
	const Dictionary parsed = order(U"- 验收: A | run actual fixture\n- 验收： B | verify receipt\n");
	CHECK(bool(parsed["acceptance_criteria_valid"]));
	const Array criteria = parsed["acceptance_criteria"];
	REQUIRE(criteria.size() == 2);
	CHECK(String(Dictionary(criteria[0])["id"]) == "A");
	CHECK(String(Dictionary(criteria[1])["requirement"]) == "verify receipt");
}
TEST_CASE("[Editor][NativeAcceptance] Empty duplicate and ambiguous criteria fail closed") {
	for (const String &body : { String("free form passes"), String(U"- 验收: A |\n"), String(U"- 验收: A | first\n- 验收: A | second\n"), String(U"- 验收: A | one | two\n") }) {
		CHECK_FALSE(bool(order(body)["acceptance_criteria_valid"]));
	}
}
TEST_CASE("[Editor][NativeAcceptance] Directory receipt needs an explicit host outcome") {
	CHECK(AIChatSubAgentReceipts::summarize("list_directory", "{\"entries\":[]}", false)["ok"].get_type() == Variant::NIL);
	CHECK(bool(AIChatSubAgentReceipts::summarize("list_directory", "{\"ok\":true,\"entries\":[]}", false)["ok"]));
	CHECK_FALSE(bool(AIChatSubAgentReceipts::summarize("list_directory", "Error: Cannot list the directory.", false)["ok"]));
}
} //namespace TestNativeAcceptance
#endif
