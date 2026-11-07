/**************************************************************************/
/*  test_ai_chat_editor_scene_actions.cpp                                 */
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

TEST_FORCE_LINK(test_ai_chat_editor_scene_actions)

#ifdef TOOLS_ENABLED
#include "core/io/json.h"
#include "core/object/class_db.h"
#include "editor/docks/ai_chat_editor_scene_actions.h"
#include "editor/docks/ai_chat_editor_scene_completion.h"
#include "scene/resources/gradient.h"

namespace TestAIChatEditorSceneActions {
Dictionary args(const String &p_action) {
	Dictionary d;
	d["action"] = p_action;
	return d;
}

TEST_CASE("[AIChat][SceneActions] Commands have a closed action vocabulary") {
	for (const String &action : { "scene_create_node", "scene_delete_node", "scene_rename_node", "scene_reparent_node", "scene_select_nodes", "scene_set_property", "scene_assign_resource", "scene_connect_signal", "scene_disconnect_signal", "scene_import_resource", "scene_export_resource", "project_export", "run_project", "run_scene", "stop_project" }) {
		CHECK(AIChatEditorSceneActions::supports(action));
	}
	CHECK_FALSE(AIChatEditorSceneActions::supports("execute_script"));
	CHECK_FALSE(AIChatEditorSceneActions::supports("scene_call_method"));
	CHECK(AIChatEditorSceneActions::perform(args("execute_script"), true)["error"] == Variant("unknown_action"));
}

TEST_CASE("[AIChat][SceneActions] Project paths reject traversal absolute and alternate schemes") {
	CHECK(AIChatEditorSceneActions::valid_project_path("res://scenes/main.tscn"));
	CHECK(AIChatEditorSceneActions::valid_project_path("res://图像/角色.png"));
	for (const String &path : { "", "res://", "user://a.tscn", "/tmp/a.tscn", "res://../a.tscn", "res://a/../b.tscn", "res://a/./b.tscn", "res://a//b.tscn", "res://a\\b.tscn", "res://a:property", "res://a/", "res:///tmp/a.tscn" }) {
		CHECK_FALSE(AIChatEditorSceneActions::valid_project_path(path));
		Dictionary d = args("run_scene");
		d["target"] = path;
		if (!path.is_empty()) {
			CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_project_path"));
		}
	}
	CHECK_FALSE(AIChatEditorSceneActions::valid_project_path("res://" + String("a").repeat(1025)));
}

TEST_CASE("[AIChat][SceneActions] Invalid node inputs fail before editor access even when confirmed") {
	for (const String &path : { "", "../Node", "/root/Node", "Node:position", "A//B", "A/./B", "A/", "A\\B" }) {
		Dictionary d = args("scene_delete_node");
		d["target"] = path;
		CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_node_path"));
	}
	Dictionary d = args("scene_create_node");
	d["name"] = "../Execute";
	d["type"] = "Node";
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_node_name"));
	d["name"] = "Safe";
	d["type"] = "EditorPlugin";
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("unsupported_node_type"));
	d["type"] = "res://script.gd";
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("unsupported_node_type"));
	d = args("scene_reparent_node");
	d["parent"] = "../outside";
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_parent_path"));
}

TEST_CASE("[AIChat][SceneActions] Selection and protected properties reject unsafe inputs") {
	Dictionary d = args("scene_select_nodes");
	Array nodes;
	nodes.push_back("A");
	nodes.push_back("A");
	d["nodes"] = nodes;
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_selection"));
	nodes.clear();
	nodes.push_back(1);
	d["nodes"] = nodes;
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_selection"));
	for (const String &name : { "script", "owner", "name", "scene_file_path", "metadata/secret", "texture" }) {
		d = args("scene_set_property");
		d["property"] = name;
		CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("protected_property"));
	}
	d = args("scene_connect_signal");
	d["method"] = "execute_script";
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_signal_arguments"));
	d = args("scene_assign_resource");
	d["resource_path"] = "res://../outside.tres";
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_project_path"));
}

TEST_CASE("[AIChat][SceneActions] JSON numbers and compound values convert only within exact bounds") {
	Variant converted;
	CHECK(AIChatEditorSceneActions::convert_json_value(12.0, Variant::INT, converted));
	CHECK(converted.get_type() == Variant::INT);
	CHECK(converted == Variant(12));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(12.5, Variant::INT, converted));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(9007199254740992.0, Variant::INT, converted));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value("12", Variant::INT, converted));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(true, Variant::INT, converted));
	Array a;
	a.push_back(1.5);
	a.push_back(-2.0);
	CHECK(AIChatEditorSceneActions::convert_json_value(a, Variant::VECTOR2, converted));
	CHECK(converted == Variant(Vector2(1.5, -2)));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(a, Variant::VECTOR2I, converted));
	a[0] = 2.0;
	CHECK(AIChatEditorSceneActions::convert_json_value(a, Variant::VECTOR2I, converted));
	a.push_back(0.0);
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(a, Variant::VECTOR2, converted));
	a[0] = "2";
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(a, Variant::VECTOR3, converted));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(Variant(), Variant::OBJECT, converted));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value("res://script.gd", Variant::OBJECT, converted));
	CHECK_FALSE(AIChatEditorSceneActions::convert_json_value(String("a").repeat(8193), Variant::STRING, converted));
}

TEST_CASE("[AIChat][SceneActions] JSON wire requests reject oversized and non JSON input") {
	Dictionary d = args("scene_set_property");
	d["property"] = "text";
	d["value"] = String("x").repeat(32769);
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_scene_arguments"));
	d = args("scene_delete_node");
	d["target"] = NodePath("Node");
	CHECK(AIChatEditorSceneActions::perform(d, true)["error"] == Variant("invalid_scene_arguments"));
	d = args("scene_delete_node");
	d["target"] = ".";
	Ref<JSON> json;
	json.instantiate();
	REQUIRE(json->parse(JSON::stringify(d)) == OK);
	CHECK(Dictionary(json->get_data())["target"] == Variant("."));
	// Pure request validation is shared by native and JSON callers.
	Dictionary parsed = json->get_data();
	parsed["target"] = "../changed";
	CHECK(AIChatEditorSceneActions::perform(parsed, true)["error"] == Variant("invalid_node_path"));
}
TEST_CASE("[AIChat][SceneActions] Resource snapshots bind content without edited versions") {
	Ref<Gradient> gradient;
	gradient.instantiate();
	Dictionary before, after;
	CHECK(AIChatEditorSceneCompletion::resource_snapshot(gradient, before));
	const uint32_t version = gradient->get_edited_version();
	Vector<Color> colors;
	colors.push_back(Color(1, 0, 0));
	colors.push_back(Color(0, 1, 0));
	gradient->set_colors(colors);
	CHECK(gradient->get_edited_version() == version);
	CHECK(AIChatEditorSceneCompletion::resource_snapshot(gradient, after));
	CHECK(before != after);
	Array array;
	Dictionary dictionary;
	dictionary["gradient"] = gradient;
	array.push_back(dictionary);
	gradient->set_meta("cycle", array);
	CHECK_FALSE(AIChatEditorSceneCompletion::resource_snapshot(gradient, after));
	gradient->remove_meta("cycle");
	gradient->set_meta("large", String("x").repeat(9000));
	CHECK_FALSE(AIChatEditorSceneCompletion::resource_snapshot(gradient, after));
	gradient->remove_meta("large");
	Ref<Gradient> child;
	child.instantiate();
	dictionary["gradient"] = child;
	gradient->set_meta("child", array);
	CHECK(AIChatEditorSceneCompletion::resource_snapshot(gradient, before));
	child->set_colors(colors);
	CHECK(AIChatEditorSceneCompletion::resource_snapshot(gradient, after));
	CHECK(before != after);
}

TEST_CASE("[AIChat][SceneActions] Synthetic extension placeholders reject native resource snapshots") {
	// Exercise Object's actual placeholder state, without claiming that a
	// separately compiled GDExtension library was loaded by this test.
	Ref<Gradient> resource;
	resource.instantiate();
	ObjectGDExtension placeholder{};
	placeholder.is_placeholder = true;
	placeholder.class_name = "SyntheticGradientPlaceholder";
	placeholder.gdtype = &Gradient::get_gdtype_static();
	placeholder.recreate_instance = [](void *, GDExtensionObjectPtr p_object) -> GDExtensionClassInstancePtr { return p_object; };
	resource->reset_internal_extension(&placeholder);
	CHECK(resource->is_extension_placeholder());
	CHECK(resource->get_class() == "Gradient");
	CHECK(ClassDB::get_api_type(resource->get_class()) == ClassDB::API_CORE);
	CHECK_FALSE(ClassDB::is_gdextension(resource->get_class()));
	Dictionary state;
	CHECK_FALSE(AIChatEditorSceneCompletion::resource_snapshot(resource, state));
	Ref<Gradient> parent;
	parent.instantiate();
	Array nested;
	nested.push_back(resource);
	parent->set_meta("nested", nested);
	CHECK_FALSE(AIChatEditorSceneCompletion::resource_snapshot(parent, state));
	parent->remove_meta("nested");
	resource->clear_internal_extension();
	CHECK(AIChatEditorSceneCompletion::resource_snapshot(resource, state));
}

} // namespace TestAIChatEditorSceneActions
#endif
