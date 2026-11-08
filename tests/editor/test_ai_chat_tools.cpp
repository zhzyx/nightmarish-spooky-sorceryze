/**************************************************************************/
/*  test_ai_chat_tools.cpp                                                */
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

TEST_FORCE_LINK(test_ai_chat_tools)

#ifdef TOOLS_ENABLED
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_cli_login.h"
#include "editor/docks/ai_chat_delivery_receipt.h"
#include "editor/docks/ai_chat_issue_guide.h"
#include "editor/docks/ai_chat_requirement_context.h"
#include "editor/docks/ai_chat_resume.h"
#include "editor/docks/ai_chat_sub_agent_receipts.h"
#include "editor/docks/ai_chat_sub_agents.h"
#include "editor/docks/ai_chat_tools.h"

namespace TestAIChatTools {

TEST_CASE("[Editor][AIChat] Delivery receipt binds private worker identity and exact candidate") {
	const Dictionary expected = JSON::parse_string(R"({"owner":"parent","snapshot_id":"turn","nonce":"nonce","source_root":"/owned","generation":4,"pr":7,"expected_candidate":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","expected_signed_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","binding":{"issue":9,"request_id":"flow-test","repository":"org/repo"}})");
	const Dictionary receipt = JSON::parse_string(R"({"schema_version":1,"kind":"native_delivery_finalization","owner":"parent","snapshot_id":"turn","nonce":"nonce","source_root":"/owned","generation":4,"issue":9,"request_id":"flow-test","completion_verified":true,"mutations_may_have_started":true,"host_facts":{"repository":"org/repo","issue":9,"request_id":"flow-test","candidate":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","signed_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","tree":"cccccccccccccccccccccccccccccccccccccccc","current_main":"dddddddddddddddddddddddddddddddddddddddd","merge_commit":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","pull_request":"https://github.com/org/repo/pull/7","pr_state":"MERGED","delivered_paths_differ":[],"issue_receipt":{"state":"CLOSED","reason":"COMPLETED","labels":["status:done","workspace:gonggong"]}},"ci":[{"name":"actual","state":"SUCCESS"},{"name":"configured skip","state":"SKIPPED"}]})");
	CHECK(AIChatDeliveryReceipt::matches(receipt, expected));
	CHECK(AIChatDeliveryReceipt::completed(receipt, expected));
	for (const String &key : { String("owner"), String("snapshot_id"), String("nonce"), String("source_root"), String("request_id"), String("kind") }) {
		Dictionary changed = receipt.duplicate(true);
		changed[key] = "foreign";
		CHECK_FALSE(AIChatDeliveryReceipt::matches(changed, expected));
		CHECK_FALSE(AIChatDeliveryReceipt::completed(changed, expected));
	}
	for (const Variant &value : { Variant(true), Variant("4"), Variant(4.5), Variant(5) }) {
		Dictionary changed = receipt.duplicate(true);
		changed["generation"] = value;
		CHECK_FALSE(AIChatDeliveryReceipt::matches(changed, expected));
	}
	for (const String &key : { String("candidate"), String("signed_commit"), String("repository"), String("request_id"), String("pull_request"), String("current_main"), String("tree") }) {
		Dictionary changed = receipt.duplicate(true);
		Dictionary facts = changed["host_facts"];
		facts[key] = "foreign";
		CHECK_FALSE(AIChatDeliveryReceipt::completed(changed, expected));
	}
	for (const String &state : { String("PENDING"), String("FAILURE"), String("CANCELLED"), String("NEUTRAL") }) {
		Dictionary changed = receipt.duplicate(true);
		Array checks = changed["ci"];
		Dictionary check = checks[0];
		check["state"] = state;
		CHECK_FALSE(AIChatDeliveryReceipt::completed(changed, expected));
	}
	for (const String &field : { String("state"), String("reason") }) {
		Dictionary changed = receipt.duplicate(true);
		Dictionary facts = changed["host_facts"];
		Dictionary issue = facts["issue_receipt"];
		issue[field] = "unknown";
		CHECK_FALSE(AIChatDeliveryReceipt::completed(changed, expected));
	}
	Dictionary changed = receipt.duplicate(true);
	Dictionary facts = changed["host_facts"];
	Dictionary issue = facts["issue_receipt"];
	Array labels = issue["labels"];
	labels.push_back("status:in-progress");
	CHECK_FALSE(AIChatDeliveryReceipt::completed(changed, expected));
	Dictionary live = expected.duplicate(true);
	live["kind"] = "native_delivery_retry";
	live["host_action_request_id"] = "desktop-retry";
	live["original_journal_sha256"] = String("f").repeat(64);
	live["engine_pid"] = 123;
	live["host_instance_id"] = String("e").repeat(32);
	Dictionary retried = receipt.duplicate(true);
	for (const String &key : { String("kind"), String("host_action_request_id"), String("original_journal_sha256"), String("engine_pid"), String("host_instance_id") }) {
		retried[key] = live[key];
	}
	CHECK(AIChatDeliveryReceipt::completed(retried, live));
	CHECK_FALSE(AIChatDeliveryReceipt::matches(receipt, live));
	CHECK_FALSE(AIChatDeliveryReceipt::matches(retried, expected));
	for (const String &key : { String("host_action_request_id"), String("original_journal_sha256"), String("engine_pid"), String("host_instance_id") }) {
		Dictionary foreign = retried.duplicate(true);
		foreign[key] = "foreign";
		CHECK_FALSE(AIChatDeliveryReceipt::matches(foreign, live));
	}
}

Ref<DirAccess> make_temporary_directory(const String &p_prefix = "godot_ai_chat") {
	Error error = OK;
	Ref<DirAccess> directory = DirAccess::create_temp(p_prefix, false, &error);
	CHECK(error == OK);
	return directory;
}

TEST_CASE("[AIChat] CLI login shell quoting preserves literal paths") {
	CHECK(AIChatCLILogin::shell_quote("/tmp/Node runtime/node") == "'/tmp/Node runtime/node'");
	CHECK(AIChatCLILogin::shell_quote("/tmp/user's CLI") == "'/tmp/user'\\''s CLI'");
	CHECK(AIChatCLILogin::shell_quote("/tmp/$HOME; `id` $(id)") == "'/tmp/$HOME; `id` $(id)'");
	const String script = AIChatCLILogin::macos_script("/tmp/node", "/tmp/bridge.js", "/tmp/cli");
	CHECK(script.begins_with("#!/bin/sh\n"));
	CHECK(script.contains("'/tmp/node' '/tmp/bridge.js' login '/tmp/cli'\nstatus=$?\n"));
	CHECK(script.contains("trap '/bin/rm -f -- \"$0\"' 0"));
	CHECK(script.contains("exit \"$status\""));
}

#ifdef UNIX_ENABLED
TEST_CASE("[AIChat] CLI login script is written at its final executable path") {
	Ref<DirAccess> root = make_temporary_directory("godot_cli_login_write");
	REQUIRE(root.is_valid());
	const String directory = root->get_current_dir();
	const String path = directory.path_join("login.command");
	REQUIRE(AIChatCLILogin::write_macos_script(path, "/tmp/node", "/tmp/bridge.js", "/tmp/cli") == OK);
	CHECK(FileAccess::exists(path));
	CHECK((uint32_t(FileAccess::get_unix_permissions(path)) & 0777) == 0700);
	CHECK(FileAccess::get_file_as_string(path) == AIChatCLILogin::macos_script("/tmp/node", "/tmp/bridge.js", "/tmp/cli"));
	root->list_dir_begin();
	int entries = 0;
	for (String name = root->get_next(); !name.is_empty(); name = root->get_next()) {
		if (name != "." && name != "..") {
			entries++;
			CHECK_MESSAGE(name == "login.command", name);
		}
	}
	root->list_dir_end();
	CHECK(entries == 1);
	CHECK(AIChatCLILogin::write_macos_script(directory.path_join("missing/login.command"), "/tmp/node", "/tmp/bridge.js", "/tmp/cli") != OK);
}

TEST_CASE("[AIChat] CLI login script preserves arguments, exit status and cleans up") {
	Ref<DirAccess> root = make_temporary_directory("godot_cli_login_test");
	REQUIRE(root.is_valid());
	const String directory = root->get_current_dir();
	const String bridge = directory.path_join("bridge ' $HOME; `id` $(id).sh");
	const String entry = directory.path_join(String::utf8("CLI 入口 '$HOME; `id` $(id)"));
	const String result_path = directory.path_join("arguments.txt");
	const String command_path = directory.path_join("login.command");
	for (int expected_status : { 0, 7 }) {
		Ref<FileAccess> mock = FileAccess::open(bridge, FileAccess::WRITE);
		REQUIRE(mock.is_valid());
		REQUIRE(mock->store_string("printf '%s\\n' \"$@\" > " + AIChatCLILogin::shell_quote(result_path) + "\nexit " + itos(expected_status) + "\n"));
		mock.unref();
		Ref<FileAccess> command = FileAccess::open(command_path, FileAccess::WRITE);
		REQUIRE(command.is_valid());
		REQUIRE(command->store_string(AIChatCLILogin::macos_script("/bin/sh", bridge, entry)));
		command.unref();
		REQUIRE(FileAccess::set_unix_permissions(command_path, 0700) == OK);
		List<String> arguments;
		arguments.push_back("-c");
		arguments.push_back(AIChatCLILogin::shell_quote(command_path) + " </dev/null >/dev/null 2>&1");
		int exit_code = -1;
		REQUIRE(OS::get_singleton()->execute("/bin/sh", arguments, nullptr, &exit_code) == OK);
		CHECK(exit_code == expected_status);
		CHECK(FileAccess::get_file_as_string(result_path) == "login\n" + entry + "\n");
		CHECK_FALSE(FileAccess::exists(command_path));
	}
}
#endif

TEST_CASE("[AIChat] Script path normalization") {
	String path;
	CHECK(AIChatTools::normalize_script_path("res://scripts/player.gd", path));
	CHECK(path == "res://scripts/player.gd");
	CHECK(AIChatTools::normalize_script_path("scripts\\Player.cs", path));
	CHECK(path == "res://scripts/Player.cs");
	CHECK(AIChatTools::normalize_script_path(String::utf8("scripts/角色.gd"), path));
}

TEST_CASE("[AIChat] Absolute, hidden and engine source paths are supported") {
	for (const char *value : { "../outside.cpp", "res://.godot/config.txt", "res://scripts/.hidden.h", "C:/Engine/editor/editor_node.cpp", "//server/share/config.json", "res://scene.tscn" }) {
		String path;
		CHECK_MESSAGE(AIChatTools::normalize_script_path(value, path), value);
	}
}

TEST_CASE("[AIChat] Reject invalid device and non-file paths") {
	const char *invalid[] = {
		"user://file.gd", "res://scripts/file.gd:stream", "res://scripts/CON.gd", "res://scripts/LPT1.gd",
		"res://scripts/folder./file.gd", "res://scripts/folder /file.gd", "res://scripts/file?.gd",
		"//?/C:/file.gd", "//./device", "res://scripts/file.gd\n", "res://", ""
	};
	for (const char *value : invalid) {
		String path;
		CHECK_MESSAGE(!AIChatTools::normalize_script_path(value, path), value);
		CHECK(path.is_empty());
	}
}

TEST_CASE("[AIChat] Resolve requires existing parents and rejects directory targets") {
	Ref<DirAccess> root = make_temporary_directory();
	REQUIRE(root.is_valid());
	const String directory = root->get_current_dir();
	String absolute;
	String error;
	CHECK(AIChatTools::resolve_script_path("res://new.gd", directory, absolute, error));
	CHECK(absolute == directory.path_join("new.gd"));
	CHECK_FALSE(AIChatTools::resolve_script_path("res://missing/new.gd", directory, absolute, error));
	REQUIRE(root->make_dir("folder.gd") == OK);
	CHECK_FALSE(AIChatTools::resolve_script_path("res://folder.gd", directory, absolute, error));
}

TEST_CASE("[AIChat] Approved writes detect disk changes and file creation conflicts") {
	Ref<DirAccess> root = make_temporary_directory();
	REQUIRE(root.is_valid());
	const String path = root->get_current_dir().path_join("script.gd");
	String error;
	String content;
	const String before = "extends Node\n";
	const String after = "extends Node\nvar value = 1\n";
	REQUIRE(AIChatTools::write_script(path, "", before, false, error));
	CHECK_FALSE(AIChatTools::write_script(path, "", after, false, error));
	CHECK_FALSE(AIChatTools::write_script(path, "stale", after, true, error));
	REQUIRE(AIChatTools::read_script(path, content, error));
	CHECK(content == before);
	REQUIRE(AIChatTools::write_script(path, before, after, true, error));
	REQUIRE(AIChatTools::read_script(path, content, error));
	CHECK(content == after);
	REQUIRE(AIChatTools::write_script(path, after, before, true, error));
	REQUIRE(AIChatTools::read_script(path, content, error));
	CHECK(content == before);
}

TEST_CASE("[AIChat] Oversized replacements are refused without creating a file") {
	Ref<DirAccess> root = make_temporary_directory();
	REQUIRE(root.is_valid());
	const String path = root->get_current_dir().path_join("script.gd");
	String error;
	CHECK_FALSE(AIChatTools::write_script(path, "", String("x").repeat(AIChatTools::MAX_SCRIPT_BYTES + 1), false, error));
	CHECK_FALSE(FileAccess::exists(path));
}

TEST_CASE("[AIChat] UTF-8 BOM survives replacement and undo") {
	Ref<DirAccess> root = make_temporary_directory();
	REQUIRE(root.is_valid());
	const String path = root->get_current_dir().path_join("script.cs");
	const String bom = String::chr(0xfeff);
	const String before = bom + "class Example {}\r\n";
	String error;
	String content;
	REQUIRE(AIChatTools::write_script(path, "", before, false, error));
	REQUIRE(AIChatTools::read_script(path, content, error));
	CHECK(content == before);
	REQUIRE(AIChatTools::write_script(path, before, "class Changed {}\r\n", true, error));
	REQUIRE(AIChatTools::read_script(path, content, error));
	CHECK(content == bom + "class Changed {}\r\n");
	REQUIRE(AIChatTools::write_script(path, content, before, true, error));
	REQUIRE(AIChatTools::read_script(path, content, error));
	CHECK(content == before);
}

TEST_CASE("[AIChat] Invalid UTF-8 is refused before replacement") {
	Ref<DirAccess> root = make_temporary_directory();
	REQUIRE(root.is_valid());
	const String path = root->get_current_dir().path_join("script.gd");
	Ref<FileAccess> file = FileAccess::open(path, FileAccess::WRITE);
	REQUIRE(file.is_valid());
	const uint8_t invalid[] = { 0xff, 0xfe, 0xff };
	REQUIRE(file->store_buffer(invalid, sizeof(invalid)));
	file->close();
	String error;
	String content;
	ERR_PRINT_OFF;
	CHECK_FALSE(AIChatTools::read_script(path, content, error));
	CHECK_FALSE(AIChatTools::write_script(path, "", "extends Node\n", true, error));
	ERR_PRINT_ON;
	file = FileAccess::open(path, FileAccess::READ);
	REQUIRE(file.is_valid());
	uint8_t saved[sizeof(invalid)] = {};
	REQUIRE(file->get_buffer(saved, sizeof(saved)) == sizeof(saved));
	for (unsigned int i = 0; i < sizeof(saved); i++) {
		CHECK(saved[i] == invalid[i]);
	}
}

TEST_CASE("[AIChat] Linked directories are accessible where supported") {
	Ref<DirAccess> root = make_temporary_directory();
	Ref<DirAccess> outside = make_temporary_directory("godot_ai_chat_outside");
	REQUIRE(root.is_valid());
	REQUIRE(outside.is_valid());
	const String link = root->get_current_dir().path_join("linked");
	if (root->create_link(outside->get_current_dir(), link) == OK) {
		String absolute;
		String error;
		CHECK(AIChatTools::resolve_script_path("res://linked/script.gd", root->get_current_dir(), absolute, error));
		CHECK(root->remove(link) == OK);
	}
}

Dictionary make_resume_journal(const String &p_content = "task") {
	Dictionary function;
	function["name"] = "Bash";
	function["arguments"] = "{\"command\":\"godot-host-action build_engine\"}";
	Dictionary call;
	call["id"] = "pending_build";
	call["type"] = "function";
	call["function"] = function;
	Array calls;
	calls.push_back(call);
	Dictionary user;
	user["role"] = "user";
	user["content"] = p_content;
	Dictionary assistant;
	assistant["role"] = "assistant";
	assistant["content"] = "";
	assistant["tool_calls"] = calls;
	Array messages;
	messages.push_back(user);
	messages.push_back(assistant);
	Dictionary restart;
	restart["from_executable"] = "old.exe";
	restart["to_executable"] = "new.exe";
	restart["token"] = "abc12345";
	restart["attempt"] = 1;
	restart["tool_call_id"] = "pending_build";
	Dictionary journal;
	journal["version"] = AIChatResume::VERSION;
	journal["agent"] = 0;
	journal["tool_rounds"] = 12;
	journal["tool_index"] = 0;
	journal["model"] = "test";
	journal["cli_model"] = "test";
	journal["backend"] = 1;
	journal["messages"] = messages;
	journal["tool_calls"] = calls;
	journal["restart"] = restart;
	return journal;
}

TEST_CASE("[AIChat] Resume validates expanded Codex read batches") {
	Dictionary journal = make_resume_journal();
	journal.erase("restart");
	journal["backend"] = 2;
	Array calls = journal["tool_calls"];
	calls.clear();
	for (int i = 0; i < 32; i++) {
		Dictionary function;
		function["name"] = "read_file";
		function["arguments"] = "{}";
		Dictionary call;
		call["function"] = function;
		call["id"] = "read-" + itos(i);
		call["type"] = "function";
		calls.push_back(call);
	}
	journal["tool_index"] = 21;
	CHECK(AIChatResume::journal_valid(journal));
	journal["backend"] = 1;
	CHECK_FALSE(AIChatResume::journal_valid(journal));
	journal["backend"] = 2;
	Dictionary last = calls[31];
	Dictionary function = last["function"];
	function["name"] = "run_command";
	CHECK_FALSE(AIChatResume::journal_valid(journal));
}

TEST_CASE("[AIChat] Resume journal legacy JSON and compact encoding remain compatible") {
	const Dictionary journal = make_resume_journal(String::utf8("保留用户约束\n"));
	Dictionary restored;
	REQUIRE(AIChatResume::decode_journal(JSON::stringify(journal, "\t"), restored));
	CHECK(Variant(restored) == JSON::parse_string(JSON::stringify(journal)));
	String body;
	Dictionary stats;
	REQUIRE(AIChatResume::encode_journal(journal, body, stats) == OK);
	CHECK(stats["encoding"] == Variant("json"));
	CHECK(body == JSON::stringify(journal));
	REQUIRE(AIChatResume::decode_journal(body, restored));
	CHECK(Variant(restored) == JSON::parse_string(JSON::stringify(journal)));
}

TEST_CASE("[AIChat] Resume journal oversized history is losslessly compressed with exact pending tools") {
	const Dictionary journal = make_resume_journal(String("x").repeat(AIChatResume::MAX_JOURNAL_BYTES + 1));
	String body;
	Dictionary stats;
	REQUIRE(AIChatResume::encode_journal(journal, body, stats) == OK);
	CHECK(stats["encoding"] == Variant("gzip-base64"));
	CHECK(int64_t(stats["uncompressed_bytes"]) > int64_t(AIChatResume::MAX_JOURNAL_BYTES));
	CHECK(body.utf8().length() < int64_t(AIChatResume::MAX_JOURNAL_BYTES));
	Dictionary restored;
	REQUIRE(AIChatResume::decode_journal(body, restored));
	CHECK(Variant(restored) == JSON::parse_string(JSON::stringify(journal)));

	Dictionary envelope = JSON::parse_string(body);
	envelope["uncompressed_bytes"] = int64_t(AIChatResume::MAX_UNCOMPRESSED_JOURNAL_BYTES + 1);
	CHECK_FALSE(AIChatResume::decode_journal(JSON::stringify(envelope), restored));
	envelope = JSON::parse_string(body);
	envelope["sha256"] = String("0").repeat(64);
	CHECK_FALSE(AIChatResume::decode_journal(JSON::stringify(envelope), restored));
	envelope = JSON::parse_string(body);
	envelope["payload"] = "!!!!";
	CHECK_FALSE(AIChatResume::decode_journal(JSON::stringify(envelope), restored));
	envelope = JSON::parse_string(body);
	envelope["storage_version"] = 2;
	CHECK_FALSE(AIChatResume::decode_journal(JSON::stringify(envelope), restored));
}

TEST_CASE("[AIChat] Resume journal invalid data never produces a partial record") {
	Dictionary journal = make_resume_journal();
	journal["tool_index"] = 2;
	String body = "stale";
	Dictionary stats;
	CHECK(AIChatResume::encode_journal(journal, body, stats) == ERR_INVALID_DATA);
	CHECK(body.is_empty());
	CHECK(stats["stage"] == Variant("validation"));
	Dictionary restored;
	CHECK_FALSE(AIChatResume::decode_journal(JSON::stringify(journal), restored));
	CHECK_FALSE(AIChatResume::decode_journal("[]", restored));
}

TEST_CASE("[AIChat] Issue guide parses bindings and only guides missing local bindings") {
	int64_t number = 0;
	String request_id;
	CHECK(AIChatIssueGuide::parse_binding(" #22  godot-chat-issue-guide-20261103 ", number, request_id));
	CHECK(number == 22);
	CHECK(request_id == "godot-chat-issue-guide-20261103");
	CHECK(AIChatIssueGuide::parse_binding(U"绑定 7 req-7", number, request_id));
	CHECK(number == 7);
	for (const String &invalid : { String("#0 req"), String("#-3 req"), String("#22"), String("22 Req"), String("22 req--x"), String("22 -req"), String("#22a req"), String("1234567890 req"), String("#22 req extra") }) {
		number = -1;
		CHECK_FALSE(AIChatIssueGuide::parse_binding(invalid, number, request_id));
		CHECK(number == -1);
	}
	CHECK(AIChatIssueGuide::is_bound(22, "req-22"));
	CHECK_FALSE(AIChatIssueGuide::is_bound(0, "req-22"));
	CHECK_FALSE(AIChatIssueGuide::is_bound(22, ""));
	CHECK_FALSE(AIChatIssueGuide::is_request_id(String("a").repeat(81)));
	CHECK(AIChatIssueGuide::is_binding_error("Missing host request: request_id"));
	CHECK(AIChatIssueGuide::is_binding_error("Before development, create/reuse a real Issue and bind issue_number and stable request_id"));
	CHECK_FALSE(AIChatIssueGuide::is_binding_error("Missing host request: outcome"));
	CHECK_FALSE(AIChatIssueGuide::is_binding_error("Issue intake rejected; verify GitHub access"));
}

TEST_CASE("[AIChat] Issue guide explains gh login without running it") {
	const String text = AIChatIssueGuide::gh_login_text("/x/gh auth login --hostname github.com --git-protocol https --web", U"确认");
	CHECK(text.contains("```\n/x/gh auth login --hostname github.com --git-protocol https --web\n```"));
	CHECK(text.contains(U"尚未登录 github.com"));
	CHECK(text.contains(U"回复 `确认` 重试"));
	const String bare = AIChatIssueGuide::gh_login_text("", "");
	CHECK_FALSE(bare.contains("```"));
	CHECK_FALSE(bare.contains(U"重试"));
}

TEST_CASE("[AIChat] Issue guide suggests stable fields and resolves categories") {
	CHECK(AIChatIssueGuide::suggest_title(U"\n  # 修复 Godot 聊天阻塞\n第二行") == U"修复 Godot 聊天阻塞");
	CHECK(AIChatIssueGuide::suggest_title("   ") == U"Godot 编辑器会话需求");
	CHECK(AIChatIssueGuide::suggest_title(String("x").repeat(200)).length() == AIChatIssueGuide::MAX_TITLE);
	CHECK(AIChatIssueGuide::suggest_request_id(U"修复 Godot 聊天 Issue-Guide 阻塞", "20261103-210501") == "godot-issue-guide-20261103-210501");
	CHECK(AIChatIssueGuide::suggest_request_id(U"纯中文标题", "20261103-210501") == "godot-chat-20261103-210501");
	const String long_id = AIChatIssueGuide::suggest_request_id(String("abcdefghij ").repeat(12), "20261103-210501");
	CHECK(AIChatIssueGuide::is_request_id(long_id));
	CHECK(long_id.length() <= AIChatIssueGuide::MAX_REQUEST_ID);

	Variant labels = JSON::parse_string(R"([{"name":"type:development","description":"dev"},{"name":"status:planned"},{"name":"type:bug"},{"name":"type:"},7])");
	const Array categories = AIChatIssueGuide::categories_from_labels(labels);
	REQUIRE(categories.size() == 2);
	CHECK(AIChatIssueGuide::category_from_reply("1", categories) == "development");
	CHECK(AIChatIssueGuide::category_from_reply(" Type:Bug ", categories) == "bug");
	CHECK(AIChatIssueGuide::category_from_reply("3", categories).is_empty());
	CHECK(AIChatIssueGuide::category_from_reply("planned", categories).is_empty());
	CHECK(AIChatIssueGuide::categories_from_labels(Variant()).is_empty());

	CHECK(AIChatIssueGuide::is_cancel(U" 取消 "));
	CHECK(AIChatIssueGuide::is_confirm("YES"));
	CHECK_FALSE(AIChatIssueGuide::is_confirm(U"确认一下吧"));
	CHECK(AIChatIssueGuide::is_start(U"开始"));
	CHECK(AIChatIssueGuide::is_retry(U"已更新"));
}

TEST_CASE("[AIChat] Requirements decisions are bound to a user turn and actual Issue") {
	const String key = AIChatIssueGuide::requirement_key("chat", "turn-1", "add a button", "22", "req");
	CHECK(key == AIChatIssueGuide::requirement_key("chat", "turn-1", "add a button", "22", "req"));
	CHECK(key != AIChatIssueGuide::requirement_key("chat", "turn-2", "add a button", "22", "req"));
	CHECK(key != AIChatIssueGuide::requirement_key("chat", "turn-1", "add a button", "24", "other"));
}

Dictionary requirement_record(const String &p_role, const String &p_text) {
	Dictionary record;
	record["role"] = p_role;
	record["content"] = p_text;
	return record;
}

TEST_CASE("[AIChat] Requirement context keeps corrections and the latest real question after setup chatter") {
	Array transcript;
	const Dictionary initial = requirement_record("user", "Implement the selected connection.");
	const Dictionary correction = requirement_record("user", "Support only connection A; leave an extension TODO.");
	const Dictionary second_correction = requirement_record("user", "Use the three explicit values from my previous answer.");
	const Dictionary question = requirement_record("editor", "Should unsupported additional values be visible but disabled?");
	const Dictionary answer = requirement_record("user", "Yes.");
	transcript.push_back(initial);
	transcript.push_back(correction);
	transcript.push_back(second_correction);
	for (int i = 0; i < 45; i++) {
		transcript.push_back(requirement_record("editor", vformat("Environment deployment step %d", i)));
		transcript.push_back(requirement_record("work", "Checking the same prerequisite."));
		transcript.push_back(requirement_record("user", U"重试"));
		REQUIRE(AIChatRequirementContext::mark_transport_retry(transcript, U"重试"));
	}
	transcript.push_back(question);
	transcript.push_back(answer);
	const Array original = transcript.duplicate(true);
	const Array selected = AIChatRequirementContext::select(transcript);
	REQUIRE(selected.size() == 6);
	CHECK(selected[0] == initial);
	CHECK(selected[1] == correction);
	CHECK(selected[2] == second_correction);
	CHECK(selected[3] == requirement_record("user", U"重试"));
	CHECK(selected[4] == question);
	CHECK(selected[5] == answer);
	CHECK(transcript == original);
}

TEST_CASE("[AIChat] Requirement context does not deduplicate answers to different questions") {
	Array transcript;
	transcript.push_back(requirement_record("editor", "First question?"));
	transcript.push_back(requirement_record("user", "Yes."));
	transcript.push_back(requirement_record("assistant", "Second question?"));
	transcript.push_back(requirement_record("user", "Yes."));
	for (int i = 0; i < 40; i++) {
		transcript.push_back(requirement_record("editor", "A repeated environment failure."));
		transcript.push_back(requirement_record("user", U"重试"));
		REQUIRE(AIChatRequirementContext::mark_transport_retry(transcript, U"重试"));
	}
	const Array selected = AIChatRequirementContext::select(transcript);
	REQUIRE(selected.size() == 6);
	for (int i = 0; i < 4; i++) {
		CHECK(selected[i] == transcript[i]);
	}
	CHECK(selected[4] == requirement_record("editor", "A repeated environment failure."));
	CHECK(selected[5] == requirement_record("user", U"重试"));

	Array continuations;
	continuations.push_back(requirement_record("editor", "Proceed with the first choice?"));
	continuations.push_back(requirement_record("user", U"继续"));
	continuations.push_back(requirement_record("editor", "Proceed with the second choice?"));
	continuations.push_back(requirement_record("user", U"继续"));
	CHECK(AIChatRequirementContext::select(continuations) == continuations);
}

TEST_CASE("[AIChat] Requirement context preserves literal retry answers without host transport metadata") {
	Array transcript;
	transcript.push_back(requirement_record("user", "Create a button."));
	transcript.push_back(requirement_record("editor", "What should the button text be?"));
	transcript.push_back(requirement_record("user", U"重试"));
	CHECK(AIChatRequirementContext::select(transcript) == transcript);

	transcript.push_back(requirement_record("assistant", "What text should the second button show?"));
	transcript.push_back(requirement_record("user", U"重试"));
	transcript.push_back(requirement_record("editor", "What should the tooltip show?"));
	transcript.push_back(requirement_record("user", "retry"));
	CHECK(AIChatRequirementContext::select(transcript) == transcript);
	CHECK_FALSE(Dictionary(transcript[2]).has("requirements_transport_retry"));
	CHECK_FALSE(Dictionary(transcript[4]).has("requirements_transport_retry"));
	CHECK_FALSE(Dictionary(transcript[6]).has("requirements_transport_retry"));

	// A producer cannot accidentally mark an earlier or non-user turn.
	CHECK_FALSE(AIChatRequirementContext::mark_transport_retry(transcript, "different text"));
	transcript.push_back(requirement_record("editor", "retry"));
	CHECK_FALSE(AIChatRequirementContext::mark_transport_retry(transcript, "retry"));

	Array legacy;
	const Dictionary old_correction = requirement_record("user", "Use the user-specified values, not the original proposal.");
	legacy.push_back(old_correction);
	for (int i = 0; i < 24; i++) {
		legacy.push_back(requirement_record("editor", "Legacy setup message."));
		legacy.push_back(requirement_record("user", "retry"));
	}
	legacy.push_back(requirement_record("editor", "What should the final button say?"));
	legacy.push_back(requirement_record("user", "retry"));
	const Array retained = AIChatRequirementContext::select(legacy);
	CHECK(retained.has(old_correction));
	int legacy_users = 0;
	for (const Variant &value : retained) {
		if (Dictionary(value)["role"] == "user") {
			legacy_users++;
		}
	}
	CHECK(legacy_users == 26);
	CHECK(retained[retained.size() - 2] == legacy[legacy.size() - 2]);
	CHECK(retained[retained.size() - 1] == legacy[legacy.size() - 1]);

	Array transport;
	transport.push_back(requirement_record("user", "retry"));
	REQUIRE(AIChatRequirementContext::mark_transport_retry(transport, "retry"));
	CHECK(AIChatResume::records_valid(transport, true));
	const Array model_context = AIChatRequirementContext::select(transport);
	REQUIRE(model_context.size() == 1);
	CHECK_FALSE(Dictionary(model_context[0]).has("requirements_transport_retry"));
}

TEST_CASE("[AIChat] Requirement context keeps chronology and all three existing budgets") {
	Array transcript;
	for (int i = 0; i < 70; i++) {
		transcript.push_back(requirement_record("user", vformat("User statement %d", i)));
	}
	const Array selected = AIChatRequirementContext::select(transcript);
	REQUIRE(selected.size() == AIChatRequirementContext::MAX_RECORDS);
	for (int i = 0; i < selected.size(); i++) {
		CHECK(selected[i] == transcript[70 - selected.size() + i]);
	}

	Array large;
	for (int i = 0; i < 20; i++) {
		large.push_back(requirement_record("user", vformat("%d:", i) + String(U"问").repeat(5000)));
	}
	const Array bounded = AIChatRequirementContext::select(large);
	REQUIRE(bounded.size() == 4);
	int characters = 0;
	for (int i = 0; i < bounded.size(); i++) {
		const String text = Dictionary(bounded[i])["content"];
		CHECK(text == String(Dictionary(large[16 + i])["content"]).left(4000));
		CHECK(text.length() <= AIChatRequirementContext::MAX_RECORD_CHARACTERS);
		characters += text.length();
	}
	CHECK(characters == AIChatRequirementContext::MAX_CHARACTERS);
	CHECK(String(Dictionary(large[19])["content"]).length() > 4000);

	const Dictionary long_question = requirement_record("editor", String("Question ").repeat(400));
	const Dictionary last_answer = requirement_record("user", "Yes.");
	large.push_back(long_question);
	large.push_back(last_answer);
	const Array with_question = AIChatRequirementContext::select(large);
	REQUIRE(with_question.size() >= 2);
	CHECK(with_question[with_question.size() - 2] == long_question);
	CHECK(with_question[with_question.size() - 1] == last_answer);
}

TEST_CASE("[AIChat] Requirement context ignores malformed records and bounds retry-only chatter") {
	Array transcript;
	transcript.push_back(Variant("not a record"));
	transcript.push_back(requirement_record("user", " "));
	transcript.push_back(requirement_record("work", "Tool details are not requirement authority."));
	CHECK(AIChatRequirementContext::select(transcript).is_empty());
	for (int i = 0; i < 40; i++) {
		transcript.push_back(requirement_record("editor", vformat("Deployment failed %d", i)));
		transcript.push_back(requirement_record("user", "retry"));
		REQUIRE(AIChatRequirementContext::mark_transport_retry(transcript, "retry"));
	}
	const Array selected = AIChatRequirementContext::select(transcript);
	REQUIRE(selected.size() == 2);
	CHECK(selected[0] == requirement_record("editor", "Deployment failed 39"));
	CHECK(selected[1] == requirement_record("user", "retry"));
}

TEST_CASE("[Editor][AIChat] Sub-agent work orders come only from a finalized design") {
	const String document = String(U"# 标题\r\n\r\n## 设计定版确认（2026-11-04）\r\n\r\n- 确认\r\n\r\n## 生产工单（拆分）\r\n\r\n（说明行）\r\n\r\n1. 第一张\r\n   - 目标：A\r\n   - 依赖：无。\r\n\r\n2. 第二张\r\n   - 依赖：工单 1。\r\n\r\n## 验证与采集证据\r\n\r\n1. 不是工单\r\n");
	const Dictionary parsed = AIChatSubAgents::parse_work_orders(document);
	CHECK(bool(parsed["finalized"]));
	const Array orders = parsed["orders"];
	REQUIRE(orders.size() == 2);
	const Dictionary first = orders[0];
	CHECK(String(first["title"]) == U"第一张");
	CHECK(String(first["body"]).contains(U"目标：A"));
	CHECK_FALSE(String(first["body"]).contains(U"第二张"));
	const Dictionary second = orders[1];
	CHECK(int(second["number"]) == 2);
	CHECK(String(second["body"]).contains(U"工单 1"));
	CHECK_FALSE(String(second["body"]).contains(U"不是工单"));

	const Dictionary draft = AIChatSubAgents::parse_work_orders(U"# 标题\n\n## 生产工单\n\n1. 未定版\n");
	CHECK_FALSE(bool(draft["finalized"]));
	CHECK(Array(draft["orders"]).size() == 1);

	String many = U"## 设计定版确认\n## 生产工单\n";
	for (int i = 1; i <= 20; i++) {
		many += itos(i) + ". order\n";
	}
	CHECK(Array(AIChatSubAgents::parse_work_orders(many)["orders"]).size() == AIChatSubAgents::MAX_CHILDREN_PER_PARENT);
	CHECK(Array(AIChatSubAgents::parse_work_orders(U"## 设计定版确认\n## 生产工单\n1.no space\n12345. too long\n")["orders"]).is_empty());

	const String title = AIChatSubAgents::tab_title(3, String(U"一个非常非常非常非常非常非常非常非常长的工单标题\n后续"));
	CHECK(title.begins_with(U"子3 · "));
	CHECK_FALSE(title.contains("\n"));
	CHECK(title.ends_with(U"…"));

	const String prompt = AIChatSubAgents::work_order_prompt("Agent 1", 1, 2, first, 47, "requirement-x");
	CHECK(prompt.contains(U"工单 1/2"));
	CHECK(prompt.contains("Issue #47"));
	CHECK(prompt.contains("design-docs/requirement-x.md"));
	CHECK(prompt.contains("get_parent_context"));
	for (int backend : { 0, 1, 2, 3 }) {
		CHECK(AIChatSubAgents::supports_read_only_backend(backend));
	}
	CHECK_FALSE(AIChatSubAgents::supports_read_only_backend(-1));
	CHECK_FALSE(AIChatSubAgents::supports_read_only_backend(4));
	CHECK(AIChatSubAgents::is_state("interrupted"));
	CHECK_FALSE(AIChatSubAgents::is_state("unknown"));
}

TEST_CASE("[Editor][AIChat] Sub-agent parent context keeps recent visible records within bounds") {
	Array transcript;
	for (int i = 0; i < 70; i++) {
		Dictionary record;
		record["role"] = i % 3 == 0 ? "user" : (i % 3 == 1 ? "assistant" : "work");
		record["content"] = vformat("message %d", i);
		transcript.push_back(record);
	}
	transcript.push_back(Variant("not a record"));
	Dictionary context = AIChatSubAgents::parent_context(transcript);
	Array records = context["records"];
	CHECK(records.size() == 40);
	CHECK(bool(context["truncated"]));
	CHECK(String(Dictionary(records[records.size() - 1])["content"]) == "message 69");
	for (int i = 0; i < records.size(); i++) {
		CHECK(String(Dictionary(records[i])["role"]) != "work");
	}

	Array large;
	for (int i = 0; i < 10; i++) {
		Dictionary record;
		record["role"] = "assistant";
		record["content"] = String("x").repeat(AIChatSubAgents::MAX_CONTEXT_RECORD_CHARS + 100);
		large.push_back(record);
	}
	context = AIChatSubAgents::parent_context(large);
	CHECK(int(context["bytes"]) <= AIChatSubAgents::MAX_CONTEXT_BYTES);
	CHECK(bool(context["truncated"]));
	CHECK(String(Dictionary(Array(context["records"])[0])["content"]).contains(U"已截断"));
	CHECK(Array(AIChatSubAgents::parent_context(Array())["records"]).is_empty());
}

TEST_CASE("[Editor][AIChat] Sub-agent receipts separate approval from process execution") {
	const String approval = R"({"approved":true,"exit_code":0,"timed_out":false,"stdout":"not execution evidence"})";
	const Dictionary approved = AIChatSubAgentReceipts::summarize("run_command", approval, true);
	CHECK(String(approved["phase"]) == "approval");
	CHECK(approved["ok"].get_type() == Variant::NIL);
	CHECK(approved["exit_code"].get_type() == Variant::NIL);
	CHECK(approved["timed_out"].get_type() == Variant::NIL);
	CHECK(approved["business_accepted"].get_type() == Variant::NIL);

	for (const String &tool : { String("run_command"), String("check_script"), String("run_test") }) {
		const Dictionary passed = AIChatSubAgentReceipts::summarize(tool, R"({"exit_code":0,"timed_out":false,"stdout":"private output"})", false);
		CHECK(String(passed["phase"]) == "execution");
		CHECK(passed["exit_code"].get_type() == Variant::INT);
		CHECK(int64_t(passed["exit_code"]) == 0);
		CHECK(bool(passed["ok"]));
		CHECK_FALSE(bool(passed["timed_out"]));
		CHECK(passed["business_accepted"].get_type() == Variant::NIL);
		const Dictionary failed = AIChatSubAgentReceipts::summarize(tool, R"({"exit_code":7,"timed_out":false,"stderr":"private error"})", false);
		CHECK(String(failed["phase"]) == "execution");
		CHECK(int64_t(failed["exit_code"]) == 7);
		CHECK_FALSE(bool(failed["ok"]));
	}
}

TEST_CASE("[Editor][AIChat] Sub-agent receipts use native terminal status instead of output claims") {
	const String result = R"({"exit_status":{"exitCode":7,"_meta":{"timed_out":false,"start_failed":false}},"exit_code":0,"output":"{\"ok\":true,\"exit_code\":0}"})";
	const Dictionary receipt = AIChatSubAgentReceipts::summarize("run_command", result, false, true);
	CHECK(String(receipt["phase"]) == "execution");
	CHECK(int64_t(receipt["exit_code"]) == 7);
	CHECK_FALSE(bool(receipt["ok"]));
	CHECK_FALSE(bool(receipt["timed_out"]));
	CHECK_FALSE(bool(receipt["start_failed"]));
	CHECK(receipt["business_accepted"].get_type() == Variant::NIL);

	for (const String &failure : {
				 String(R"({"exit_status":{"exitCode":0,"_meta":{"timed_out":true,"start_failed":false}}})"),
				 String(R"({"exit_status":{"exitCode":0,"_meta":{"timed_out":false,"start_failed":true}}})"),
				 String(R"({"exit_status":{"exitCode":0,"signal":"SIGTERM","_meta":{"timed_out":false,"start_failed":false}}})") }) {
		CHECK_FALSE(bool(AIChatSubAgentReceipts::summarize("run_command", failure, false, true)["ok"]));
	}
	const Dictionary missing = AIChatSubAgentReceipts::summarize("run_command", R"({"exit_status":{"_meta":{"timed_out":false,"start_failed":false}},"output":"exit 0"})", false, true);
	CHECK(String(missing["phase"]) == "execution");
	CHECK(missing["ok"].get_type() == Variant::NIL);
	CHECK(missing["exit_code"].get_type() == Variant::NIL);
	const Dictionary wrong_shape = AIChatSubAgentReceipts::summarize("run_command", R"({"exit_code":0,"timed_out":false})", false, true);
	CHECK(String(wrong_shape["phase"]) == "host_result");
	CHECK(wrong_shape["ok"].get_type() == Variant::NIL);
}

TEST_CASE("[Editor][AIChat] Sub-agent receipts preserve Windows DWORD failure codes and reject invalid numbers") {
	for (const String &code : { String("-2147483648"), String("3221225477"), String("4294967295") }) {
		const Dictionary regular = AIChatSubAgentReceipts::summarize("run_command", "{\"exit_code\":" + code + "}", false);
		CHECK(regular["exit_code"].get_type() == Variant::INT);
		CHECK(int64_t(regular["exit_code"]) == code.to_int());
		CHECK_FALSE(bool(regular["ok"]));
		const Dictionary native = AIChatSubAgentReceipts::summarize("run_command", "{\"exit_status\":{\"exitCode\":" + code + "}}", false, true);
		CHECK(native["exit_code"].get_type() == Variant::INT);
		CHECK(int64_t(native["exit_code"]) == code.to_int());
		CHECK_FALSE(bool(native["ok"]));
	}
	for (const String &code : { String("-2147483649"), String("4294967296"), String("0.5"), String("\"0\""), String("true"), String("null") }) {
		const Dictionary regular = AIChatSubAgentReceipts::summarize("run_command", "{\"exit_code\":" + code + "}", false);
		CHECK(regular["exit_code"].get_type() == Variant::NIL);
		CHECK(regular["ok"].get_type() == Variant::NIL);
		const Dictionary native = AIChatSubAgentReceipts::summarize("run_command", "{\"exit_status\":{\"exitCode\":" + code + "}}", false, true);
		CHECK(native["exit_code"].get_type() == Variant::NIL);
		CHECK(native["ok"].get_type() == Variant::NIL);
	}
	const Dictionary untyped_flags = AIChatSubAgentReceipts::summarize("run_command", R"({"timed_out":"true","start_failed":1,"ok":true})", false);
	CHECK(String(untyped_flags["phase"]) == "host_result");
	CHECK(untyped_flags["timed_out"].get_type() == Variant::NIL);
	CHECK(untyped_flags["start_failed"].get_type() == Variant::NIL);
	CHECK(untyped_flags["ok"].get_type() == Variant::NIL);
}

TEST_CASE("[Editor][AIChat] Sub-agent receipts do not parse file contents as host status") {
	for (const String &tool : { String("read_file"), String("read_script"), String("write_file"), String("write_script") }) {
		for (const String &contents : { String(R"({"approved":true,"ok":true,"exit_code":0})"), String("Error: this is literal file content") }) {
			const Dictionary success = AIChatSubAgentReceipts::summarize(tool, contents, true);
			CHECK(String(success["phase"]) == "file_result");
			CHECK(bool(success["ok"]));
			CHECK(success["exit_code"].get_type() == Variant::NIL);
			CHECK(success["business_accepted"].get_type() == Variant::NIL);
			const Dictionary failure = AIChatSubAgentReceipts::summarize(tool, contents, false);
			CHECK_FALSE(bool(failure["ok"]));
			CHECK(failure["exit_code"].get_type() == Variant::NIL);
		}
	}
	const Dictionary error = AIChatSubAgentReceipts::summarize("read_file", "Error: inaccessible file", false);
	CHECK(String(error["phase"]) == "host_error");
	CHECK_FALSE(bool(error["ok"]));
	const Dictionary command_error = AIChatSubAgentReceipts::summarize("run_command", "Error: command was not started", false);
	CHECK(String(command_error["phase"]) == "host_error");
	CHECK_FALSE(bool(command_error["ok"]));
	CHECK(command_error["exit_code"].get_type() == Variant::NIL);
}

TEST_CASE("[Editor][AIChat] Sub-agent receipts retain bounded typed metadata without result text") {
	const String result = String(U"秘密正文：") + R"({"ok":true,"command":"private command","output":"private output"})";
	const Dictionary receipt = AIChatSubAgentReceipts::summarize("read_logs", result, false);
	CHECK(receipt.size() == 10);
	CHECK(String(receipt["source"]) == "host_callback");
	CHECK(String(receipt["tool"]) == "read_logs");
	CHECK(String(receipt["result_sha256"]) == result.sha256_text());
	CHECK(int64_t(receipt["result_bytes"]) == result.utf8().length());
	const String serialized = JSON::stringify(receipt);
	CHECK_FALSE(serialized.contains(U"秘密正文"));
	CHECK_FALSE(serialized.contains("private command"));
	CHECK_FALSE(serialized.contains("private output"));
	CHECK(serialized.utf8().length() < 512);

	const Dictionary host_result = AIChatSubAgentReceipts::summarize("read_logs", R"({"ok":true,"logs":"not business acceptance"})", false);
	CHECK(String(host_result["phase"]) == "host_result");
	CHECK(bool(host_result["ok"]));
	CHECK(host_result["business_accepted"].get_type() == Variant::NIL);
	const Dictionary unknown = AIChatSubAgentReceipts::summarize(String("untrusted tool ").repeat(1000), R"({"ok":true,"exit_code":0})", false);
	CHECK(String(unknown["tool"]) == "unknown");
	CHECK(unknown["ok"].get_type() == Variant::NIL);
	CHECK(JSON::stringify(unknown).utf8().length() < 512);

	const String large = String(" ").repeat(AIChatSubAgentReceipts::MAX_RESULT_PARSE_BYTES) + R"({"ok":true})";
	const Dictionary oversized = AIChatSubAgentReceipts::summarize("read_logs", large, false);
	CHECK(String(oversized["result_sha256"]) == large.sha256_text());
	CHECK(int64_t(oversized["result_bytes"]) == large.utf8().length());
	CHECK(oversized["ok"].get_type() == Variant::NIL);
	CHECK(JSON::stringify(oversized).utf8().length() < 512);
	CHECK(AIChatSubAgentReceipts::MAX_RECEIPTS_PER_CHILD == 24);
	CHECK(AIChatSubAgentReceipts::MAX_CHILD_RECEIPT_BYTES <= AIChatSubAgentReceipts::MAX_PARENT_RECEIPT_BYTES);
	CHECK(AIChatSubAgentReceipts::MAX_PARENT_RECEIPT_BYTES == 64 * 1024);
}

} // namespace TestAIChatTools
#endif // TOOLS_ENABLED
