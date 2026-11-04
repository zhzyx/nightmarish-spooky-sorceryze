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
} //namespace TestAIChatEditorControl
#endif
