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
#include "editor/docks/ai_chat_issue_guide.h"
#include "editor/docks/ai_chat_resume.h"
#include "editor/docks/ai_chat_tools.h"

namespace TestAIChatTools {

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

} // namespace TestAIChatTools
#endif // TOOLS_ENABLED
