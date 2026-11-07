/**************************************************************************/
/*  test_ai_chat_editor_control.cpp                                       */
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

TEST_FORCE_LINK(test_ai_chat_editor_control)

#ifdef TOOLS_ENABLED
#include "core/config/project_settings.h"
#include "core/io/dir_access.h"
#include "core/io/json.h"
#include "editor/docks/ai_chat_editor_control.h"
#include "editor/docks/ai_chat_tools.h"

namespace TestAIChatEditorControl {
TEST_CASE("[AIChat] State preserves empty values and exact usable paths") {
	Dictionary state;
	state["main_screen"] = StringName("2D");
	state["scene"] = Variant();
	state["script"] = Variant();
	Array selection;
	selection.push_back("Parent/Child");
	state["selected_nodes"] = selection;
	PackedStringArray scenes;
	scenes.push_back("res://example.tscn");
	state["unsaved_scenes"] = scenes;
	Dictionary result = AIChatEditorControl::bound_state(state);
	CHECK_FALSE(bool(result["truncated"]));
	CHECK(result["scene"].get_type() == Variant::NIL);
	CHECK(result["script"].get_type() == Variant::NIL);
	CHECK(result["script_unsaved"].get_type() == Variant::NIL);
	CHECK(result["main_screen"] == Variant("2D"));
	CHECK(Array(result["selected_nodes"])[0] == Variant("Parent/Child"));
	CHECK(Array(result["unsaved_scenes"])[0] == Variant("res://example.tscn"));
}

TEST_CASE("[AIChat] State omits overlong paths with explicit field markers") {
	Dictionary state;
	const String long_path = String::utf8("界").repeat(20000);
	for (const String &field : { "scene", "script", "main_screen", "highlight" }) {
		state[field] = long_path;
	}
	Array paths;
	paths.push_back(long_path);
	paths.push_back("Child");
	state["selected_nodes"] = paths;
	state["unsaved_scenes"] = paths;
	Dictionary result = AIChatEditorControl::bound_state(state);
	CHECK(bool(result["truncated"]));
	CHECK(Array(result["truncated_fields"]).size() == 6);
	CHECK(result["scene"].get_type() == Variant::NIL);
	CHECK(result["script"].get_type() == Variant::NIL);
	CHECK(Array(result["selected_nodes"]).size() == 1);
	CHECK(Array(result["selected_nodes"])[0] == Variant("Child"));
	CHECK(Array(state["selected_nodes"]).size() == 2);
	CHECK(JSON::stringify(result).utf8().length() <= AIChatEditorControl::MAX_STATE_JSON_BYTES);
}

TEST_CASE("[AIChat] State redaction preserves JSON structure and budget") {
	for (const String &secret : { String("test"), String("null"), String("true") }) {
		Dictionary state;
		Array paths;
		for (int i = 0; i < 14; i++) {
			paths.push_back(secret.repeat(256));
		}
		paths.push_back("SafeChild");
		state["selected_nodes"] = paths;
		state["scene"] = "res://" + secret + ".tscn";
		state["running"] = true;
		PackedStringArray secrets;
		secrets.push_back(secret);
		Dictionary result = AIChatEditorControl::bound_state(state, secrets);
		CHECK(result["scene"].get_type() == Variant::NIL);
		CHECK(bool(result["running"]));
		CHECK(Array(result["selected_nodes"]).size() == 1);
		CHECK(Array(result["selected_nodes"])[0] == Variant("SafeChild"));
		CHECK(Array(result["redacted_fields"]).size() == 2);
		const String json = JSON::stringify(result);
		CHECK(JSON::parse_string(json).get_type() == Variant::DICTIONARY);
		CHECK(json.utf8().length() <= AIChatEditorControl::MAX_STATE_JSON_BYTES);
	}
}

TEST_CASE("[AIChat] State bounds counts and actual escaped UTF-8 JSON bytes") {
	// ASCII, CJK, four-byte Unicode and JSON escape expansion exercise different budgets.
	for (const String &unit : { String("a"), String::utf8("界"), String::utf8("😀"), String("\t"), String("\\\"") }) {
		Dictionary state;
		const String path = unit.repeat(1024 / unit.length());
		for (const String &field : { "scene", "script", "main_screen", "highlight" }) {
			state[field] = path;
		}
		Array paths;
		for (int i = 0; i < 105; i++) {
			paths.push_back(path);
		}
		state["selected_nodes"] = paths;
		state["unsaved_scenes"] = paths;
		state["running"] = true;
		state["script_unsaved"] = true;
		Dictionary result = AIChatEditorControl::bound_state(state);
		const String json = JSON::stringify(result);
		CHECK(json.utf8().length() <= AIChatEditorControl::MAX_STATE_JSON_BYTES);
		CHECK(JSON::parse_string(json).get_type() == Variant::DICTIONARY);
		CHECK(bool(result["truncated"]));
		CHECK(bool(result["running"]));
		CHECK(bool(result["script_unsaved"]));
		CHECK(Array(result["selected_nodes"]).size() <= 100);
		CHECK(Array(result["unsaved_scenes"]).size() <= 100);
	}
	Dictionary state;
	Array paths;
	for (int i = 0; i < 101; i++) {
		paths.push_back("Node" + itos(i));
	}
	state["selected_nodes"] = paths;
	state["unsaved_scenes"] = paths;
	Dictionary result = AIChatEditorControl::bound_state(state);
	CHECK(Array(result["selected_nodes"]).size() == 100);
	CHECK(Array(result["unsaved_scenes"]).size() == 100);
	CHECK(Array(result["truncated_fields"]).size() == 2);
}

TEST_CASE("[AIChat] Semantic paths reject absolute paths and traversal") {
	CHECK(AIChatEditorControl::valid_project_path("res://scenes/main.tscn"));
	CHECK_FALSE(AIChatEditorControl::valid_project_path("res://../outside.tscn"));
	CHECK_FALSE(AIChatEditorControl::valid_project_path("res://scenes/../main.tscn"));
	CHECK_FALSE(AIChatEditorControl::valid_project_path("C:/project/main.tscn"));
	CHECK_FALSE(AIChatEditorControl::valid_project_path("user://main.tscn"));
}

TEST_CASE("[AIChat] Semantic actions fail closed before accessing editor UI") {
	AIChatEditorControl *control = memnew(AIChatEditorControl);
	Dictionary args;
	args["action"] = "set_project_setting";
	args["target"] = "application/config/name";
	args["value"] = "unauthorized";
	for (bool confirmed : { false, true }) {
		CHECK_FALSE(bool(control->execute(args, false, false, confirmed)["ok"]));
		CHECK_FALSE(bool(control->execute(args, true, true, confirmed)["ok"]));
	}
	args["action"] = "execute_script";
	CHECK(control->execute(args, true, false)["error"] == Variant("unknown_action"));
	CHECK(control->get_mouse_filter() == Control::MOUSE_FILTER_IGNORE);
	memdelete(control);
}

TEST_CASE("[AIChat] Project setting preview does not mutate and validates type") {
	ProjectSettings *settings = ProjectSettings::get_singleton();
	const String key = "ai_chat_semantic_test/preview";
	settings->set_setting(key, 42);
	AIChatEditorControl *control = memnew(AIChatEditorControl);
	Dictionary args;
	args["action"] = "set_project_setting";
	args["target"] = key;
	args["value"] = JSON::parse_string("43");
	Dictionary result = control->execute(args, true, false);
	CHECK(bool(result["confirmation_required"]));
	CHECK(result["old_value"] == Variant(42));
	CHECK(result["new_value"] == Variant(43));
	CHECK(settings->get_setting(key) == Variant(42));
	args["value"] = JSON::parse_string("43.5");
	CHECK(control->execute(args, true, false)["error"] == Variant("setting_type_mismatch"));
	args["value"] = "wrong type";
	CHECK(control->execute(args, true, false)["error"] == Variant("setting_type_mismatch"));
	args["action"] = "clear_project_setting";
	CHECK(bool(control->execute(args, true, false)["confirmation_required"]));
	CHECK(settings->has_setting(key));
	settings->set_setting(key, Variant());
	memdelete(control);
}
TEST_CASE("[AIChat] Project setting save rejects a stale parsed snapshot") {
	Error error_code = OK;
	Ref<DirAccess> directory = DirAccess::create_temp("semantic_setting", false, &error_code);
	REQUIRE(error_code == OK);
	const String path = directory->get_current_dir().path_join("project.godot");
	const String original = "[application]\nconfig/name=\"Original\"\n[display]\nwindow/size/viewport_width=640\n";
	const String concurrent = original.replace("Original", "External edit");
	String error, actual;
	REQUIRE(AIChatTools::write_script(path, "", original, false, error));
	REQUIRE(AIChatTools::write_script(path, original, concurrent, true, error));
	CHECK_FALSE(AIChatEditorControl::save_setting_snapshot(path, original, "display/window/size/viewport_width", 777, error));
	REQUIRE(AIChatTools::read_script(path, actual, error));
	CHECK(actual == concurrent);
	REQUIRE(AIChatEditorControl::save_setting_snapshot(path, concurrent, "display/window/size/viewport_width", 777, error));
	REQUIRE(AIChatTools::read_script(path, actual, error));
	CHECK(actual.contains("External edit"));
	CHECK(actual.contains("777"));
	DirAccess::remove_absolute(path);
	DirAccess::remove_absolute(directory->get_current_dir());
}
TEST_CASE("[SceneTree][AIChat] Routed receipts enforce capacity and bounded event recovery") {
	AIChatEditorControl *control = memnew(AIChatEditorControl);
	Dictionary operation;
	operation["action"] = "clear_highlight";
	Dictionary message;
	message["intent"] = "engine_operation";
	message["source"] = "capacity-test";
	message["operation"] = operation;
	for (int i = 0; i < 256; i++) {
		message["request_id"] = "request-" + itos(i);
		REQUIRE(bool(control->route_message(message, true, false)["ok"]));
	}
	message["request_id"] = "overflow";
	CHECK(control->route_message(message, true, false)["error"] == Variant("route_capacity_exceeded"));
	Dictionary events = control->route_events(0, 100);
	CHECK(Array(events["events"]).size() == 100);
	CHECK(int64_t(events["next_cursor"]) == 100);
	CHECK(int64_t(events["latest_cursor"]) == 256);
	CHECK(bool(events["has_more"]));
	CHECK_FALSE(bool(events["gap"]));
	CHECK(Array(control->route_events(200, 100)["events"]).size() == 56);
	CHECK(control->route_events(257, 100)["error"] == Variant("invalid_event_cursor"));
	message["request_id"] = "request-0";
	control->cancel_route(message, "test-cancelled");
	CHECK(bool(control->route_events(0, 100)["gap"]));
	CHECK(control->route_message(message, true, false)["routing_status"] == Variant("cancelled"));
	operation["action"] = "focus";
	message["operation"] = operation;
	CHECK(control->route_message(message, true, false)["error"] == Variant("request_id_conflict"));
	message["request"] = String("x").repeat(32768);
	CHECK(control->route_message(message, true, false)["error"] == Variant("message_too_large"));
	Dictionary chat;
	chat["action"] = "chat_send_request";
	CHECK(control->execute(chat, true, false)["error"] == Variant("host_only_action"));
	CHECK(control->execute(chat, true, false, true)["error"] == Variant("host_only_action"));
	Dictionary observe_args;
	observe_args["action"] = "start_guidance";
	observe_args["steps"] = JSON::parse_string("[{\"target\":\"scene_tree\",\"observe\":{\"type\":\"project_setting\",\"setting\":\"custom/api_key\"}}]");
	CHECK(control->execute(observe_args, true, false)["error"] == Variant("invalid_guidance_steps"));
	memdelete(control);
}

TEST_CASE("[AIChat][SceneCompletionSchema] Scene resource and signal fields are exposed with bounded tool schema") {
	const Array tools = AIChatEditorControl::tool_definitions();
	Dictionary editor_action;
	for (const Variant &entry : tools) {
		const Dictionary tool = entry;
		const Dictionary function = tool.get("function", Dictionary());
		if (function.get("name", "") == Variant("editor_action")) {
			editor_action = function;
		}
	}
	REQUIRE_FALSE(editor_action.is_empty());
	const Dictionary parameters = editor_action["parameters"];
	CHECK(parameters["additionalProperties"] == Variant(false));
	const Dictionary properties = parameters["properties"];
	for (const String &field : { "receiver", "signal", "method", "resource_path", "destination", "preset", "format" }) {
		REQUIRE(properties.has(field));
		CHECK(Dictionary(properties[field])["type"] == Variant("string"));
	}
	REQUIRE(properties.has("debug"));
	CHECK(Dictionary(properties["debug"])["type"] == Variant("boolean"));
	const String description = editor_action["description"];
	for (const String &action : { "scene_assign_resource", "scene_connect_signal", "scene_disconnect_signal", "scene_import_resource", "scene_export_resource", "project_export" }) {
		CHECK(description.contains(action));
	}
	CHECK_FALSE(properties.has("callable"));
	CHECK_FALSE(properties.has("code"));
}

} //namespace TestAIChatEditorControl
#endif
