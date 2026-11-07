/**************************************************************************/
/*  test_ai_chat_editor_complex.cpp                                       */
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

TEST_FORCE_LINK(test_ai_chat_editor_complex)

#ifdef TOOLS_ENABLED
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "editor/docks/ai_chat_editor_registry.h"
#include "editor/scene/curve_editor_plugin.h"
#include "scene/gui/graph_edit.h"
#include "scene/gui/graph_node.h"
#include "scene/gui/item_list.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/popup_menu.h"
#include "scene/gui/tree.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

namespace TestAIChatEditorComplex {
Dictionary authorize(Dictionary p_args, const Dictionary &p_preview) {
	p_args["expected_target_instance"] = p_preview["target_instance"];
	p_args["expected_old_value"] = p_preview["old_value"];
	return p_args;
}
struct Observer : Object {
	int requests = 0;
	void delete_graph() {
		memdelete(graph);
		graph = nullptr;
	}
	GraphEdit *graph = nullptr;
	void activated(int p_index) { requests += p_index + 1; }
	void tree_activated() { requests++; }
	void connection(StringName p_from, int p_from_port, StringName p_to, int p_to_port) {
		requests++;
		graph->connect_node(p_from, p_from_port, p_to, p_to_port);
	}
};

TEST_CASE("[SceneTree][AIChat][Complex] Popup Window activation uses native IDs and stale guards") {
	AIChatEditorRegistry registry;
	PopupMenu *menu = memnew(PopupMenu);
	SceneTree::get_singleton()->get_root()->add_child(menu);
	menu->add_item("Business action", 37);
	menu->add_separator();
	menu->add_item("Disabled", 39);
	menu->set_item_disabled(2, true);
	menu->popup();
	Observer observer;
	menu->connect("id_pressed", callable_mp(&observer, &Observer::activated));
	Dictionary args = JSON::parse_string("{\"action\":\"activate_menu_item\",\"index\":0}");
	Dictionary preview = registry.perform(menu, "popup", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	CHECK(observer.requests == 0);
	CHECK(registry.perform(menu, "popup", args, true)["error"] == Variant("target_changed_since_confirmation"));
	menu->set_item_text(0, "Changed");
	CHECK(registry.perform(menu, "popup", authorize(args, preview), true)["error"] == Variant("target_changed_since_confirmation"));
	preview = registry.perform(menu, "popup", args, false);
	menu->set_item_metadata(0, "changed-context");
	CHECK(registry.perform(menu, "popup", authorize(args, preview), true)["error"] == Variant("target_changed_since_confirmation"));
	preview = registry.perform(menu, "popup", args, false);
	Dictionary done = registry.perform(menu, "popup", JSON::parse_string(JSON::stringify(authorize(args, preview))), true);
	CHECK(bool(done["ok"]));
	CHECK(bool(done["requested"]));
	CHECK_FALSE(bool(done["business_completed"]));
	CHECK(observer.requests == 38);
	menu->popup();
	args["index"] = 1;
	CHECK(registry.perform(menu, "popup", args, false)["error"] == Variant("menu_item_not_activatable"));
	args["index"] = 2;
	CHECK(registry.perform(menu, "popup", args, false)["error"] == Variant("menu_item_not_activatable"));
	menu->set_meta("ai_control_exclude", true);
	CHECK(registry.perform(menu, "popup", args, false)["error"] == Variant("protected_target"));
	memdelete(menu);
}

TEST_CASE("[SceneTree][AIChat][Complex] Popup item pages preserve byte and count capacity") {
	AIChatEditorRegistry registry;
	PopupMenu *menu = memnew(PopupMenu);
	SceneTree::get_singleton()->get_root()->add_child(menu);
	for (int i = 0; i < 4097; i++) {
		menu->add_item(String("long").repeat(40));
	}
	menu->popup();
	Dictionary args;
	args["action"] = "read_menu_items";
	args["limit"] = 100;
	Dictionary page = registry.perform(menu, "popup", args, false);
	CHECK(int(page["total"]) == 4097);
	CHECK(bool(page["truncated"]));
	CHECK(JSON::stringify(page["items"]).utf8().length() <= 8192);
	CHECK(int(page["next_offset"]) > 0);
	args["offset"] = 0.5;
	CHECK(registry.perform(menu, "popup", args, false)["error"] == Variant("invalid_item_page"));
	args["action"] = "activate_menu_item";
	args["index"] = 0;
	CHECK(registry.perform(menu, "popup", args, false)["error"] == Variant("item_capacity_exceeded"));
	memdelete(menu);
}

TEST_CASE("[SceneTree][AIChat][Complex] Graph requests verify ports and read native handler state") {
	AIChatEditorRegistry registry;
	GraphEdit *graph = memnew(GraphEdit);
	SceneTree::get_singleton()->get_root()->add_child(graph);
	for (const char *name : { "Source", "Destination" }) {
		GraphNode *node = memnew(GraphNode);
		node->set_name(name);
		graph->add_child(node);
		node->add_child(memnew(Control));
		node->set_slot(0, true, 0, Color(1, 1, 1), true, 0, Color(1, 1, 1));
	}
	Observer observer;
	observer.graph = graph;
	graph->connect("connection_request", callable_mp(&observer, &Observer::connection));
	Dictionary args = JSON::parse_string("{\"action\":\"graph_connect\",\"value\":{\"from\":\"Source\",\"from_port\":0,\"to\":\"Destination\",\"to_port\":0}}");
	Dictionary preview = registry.perform(graph, "graph", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	CHECK(graph->get_connections().is_empty());
	Dictionary done = registry.perform(graph, "graph", authorize(args, preview), true);
	CHECK(bool(done["ok"]));
	CHECK(bool(done["state_changed"]));
	CHECK_FALSE(bool(done["business_completed"]));
	CHECK(observer.requests == 1);
	CHECK(graph->is_node_connected("Source", 0, "Destination", 0));
	args["action"] = "read_graph_connections";
	Dictionary page = registry.perform(graph, "graph", args, false);
	CHECK(Array(page["items"]).size() == 1);
	graph->get_node(NodePath("Source"))->set_meta("ai_control_exclude", true);
	page = registry.perform(graph, "graph", args, false);
	CHECK(Array(page["items"]).is_empty());
	args["action"] = "graph_disconnect";
	CHECK(registry.perform(graph, "graph", args, false)["error"] == Variant("protected_target"));
	memdelete(graph);
}

TEST_CASE("[SceneTree][AIChat][Complex] List and tree activation use native accept handlers") {
	AIChatEditorRegistry registry;
	Observer observer;
	ItemList *items = memnew(ItemList);
	SceneTree::get_singleton()->get_root()->add_child(items);
	items->add_item("Open");
	items->set_item_metadata(0, "res://old.gd");
	items->connect("item_activated", callable_mp(&observer, &Observer::activated));
	Dictionary args = JSON::parse_string("{\"action\":\"activate_item\",\"index\":0}");
	Dictionary preview = registry.perform(items, "items", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	items->set_item_metadata(0, "res://new.gd");
	CHECK(registry.perform(items, "items", authorize(args, preview), true)["error"] == Variant("target_changed_since_confirmation"));
	CHECK(observer.requests == 0);
	preview = registry.perform(items, "items", args, false);
	Dictionary done = registry.perform(items, "items", authorize(args, preview), true);
	CHECK(bool(done["requested"]));
	CHECK_FALSE(bool(done["business_completed"]));
	CHECK(observer.requests == 1);
	Tree *tree = memnew(Tree);
	SceneTree::get_singleton()->get_root()->add_child(tree);
	tree->create_item()->set_text(0, "Open");
	tree->get_root()->set_metadata(0, "res://old.tscn");
	tree->connect("item_activated", callable_mp(&observer, &Observer::tree_activated));
	args["action"] = "activate_tree_item";
	preview = registry.perform(tree, "tree", args, false);
	tree->get_root()->set_metadata(0, "res://new.tscn");
	CHECK(registry.perform(tree, "tree", authorize(args, preview), true)["error"] == Variant("target_changed_since_confirmation"));
	CHECK(observer.requests == 1);
	preview = registry.perform(tree, "tree", args, false);
	done = registry.perform(tree, "tree", authorize(args, preview), true);
	CHECK(bool(done["requested"]));
	CHECK(observer.requests == 2);
	memdelete(tree);
	memdelete(items);
}

TEST_CASE("[SceneTree][AIChat][Complex] Graph move stops after synchronous owner destruction") {
	AIChatEditorRegistry registry;
	GraphEdit *graph = memnew(GraphEdit);
	SceneTree::get_singleton()->get_root()->add_child(graph);
	GraphNode *node = memnew(GraphNode);
	node->set_name("Movable");
	graph->add_child(node);
	Observer observer;
	observer.graph = graph;
	graph->connect("begin_node_move", callable_mp(&observer, &Observer::delete_graph));
	Dictionary args = JSON::parse_string("{\"action\":\"graph_move_node\",\"value\":{\"node\":\"Movable\",\"position\":[30,40]}}");
	Dictionary preview = registry.perform(graph, "graph", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	ERR_PRINT_OFF; // Intentional hostile synchronous deletion; the engine diagnoses it.
	Dictionary done = registry.perform(graph, "graph", authorize(args, preview), true);
	ERR_PRINT_ON;
	CHECK(bool(done["requested"]));
	CHECK_FALSE(bool(done["business_completed"]));
	CHECK(done["halted_reason"] == Variant("target_unavailable_during_native_callback"));
	CHECK(observer.graph == nullptr);
}

TEST_CASE("[AIChat][Complex] Resource identities survive real JSON without numeric truncation") {
	CurveEdit *edit = memnew(CurveEdit);
	Ref<Curve> curve;
	curve.instantiate();
	curve->add_point(Vector2(0, 0));
	curve->add_point(Vector2(1, 1));
	edit->set_curve(curve);
	Dictionary state = AIChatEditorComplexActions::state(edit);
	Dictionary wire = JSON::parse_string(JSON::stringify(state));
	CHECK(wire["resource_instance"].get_type() == Variant::STRING);
	CHECK(wire["resource_instance"] == Variant(String::num_uint64(uint64_t(curve->get_instance_id()))));
	curve->set_point_value(0, 0.5);
	CHECK(AIChatEditorComplexActions::state(edit)["content_hash"] != wire["content_hash"]);
	memdelete(edit);
}

TEST_CASE("[SceneTree][AIChat][Complex] Curve resource capacity rejects point writes without manager access") {
	AIChatEditorRegistry registry;
	CurveEdit *edit = memnew(CurveEdit);
	Ref<Curve> curve;
	curve.instantiate();
	curve->set_point_count(4097);
	edit->set_curve(curve);
	ERR_PRINT_OFF; // The native CurveEdit enter-tree theme uses EditorSettings absent from this unit fixture.
	SceneTree::get_singleton()->get_root()->add_child(edit);
	ERR_PRINT_ON;
	Dictionary args = JSON::parse_string("{\"action\":\"curve_add_point\",\"value\":[0.5,0.5]}");
	CHECK(registry.perform(edit, "curve", args, false)["error"] == Variant("item_capacity_exceeded"));
	args["action"] = "read_curve";
	args["limit"] = 1;
	Dictionary page = registry.perform(edit, "curve", args, false);
	CHECK(int(page["total"]) == 4097);
	CHECK(int(page["capacity"]) == 4096);
	CHECK(bool(page["truncated"]));
	memdelete(edit);
}

TEST_CASE("[SceneTree][AIChat][Complex] Submenu wrapper uses native parent-child lifecycle") {
	AIChatEditorRegistry registry;
	PopupMenu *parent = memnew(PopupMenu);
	PopupMenu *child = memnew(PopupMenu);
	SceneTree::get_singleton()->get_root()->add_child(parent);
	parent->add_child(child);
	child->add_item("Leaf", 91);
	parent->add_submenu_node_item("Nested", child, 75);
	CHECK_FALSE(parent->open_submenu(0));
	parent->popup();
	parent->set_item_disabled(0, true);
	CHECK_FALSE(parent->open_submenu(0));
	parent->set_item_disabled(0, false);
	Dictionary args = JSON::parse_string("{\"action\":\"open_menu_submenu\",\"index\":0}");
	Dictionary preview = registry.perform(parent, "menu", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	Dictionary opened = registry.perform(parent, "menu", authorize(args, preview), true);
	CHECK(opened["submenu_request_status"] == Variant("queued"));
	CHECK(parent->open_submenu(0));
	CHECK_FALSE(bool(opened["business_completed"]));
	CHECK(child->is_visible());
	child->activate_item(0);
	CHECK_FALSE(child->is_visible());
	CHECK_FALSE(parent->is_visible());
	memdelete(parent);
}

TEST_CASE("[SceneTree][AIChat][Complex] Shared descriptions reject protected ancestors") {
	Control *parent = memnew(Control);
	SceneTree::get_singleton()->get_root()->add_child(parent);
	LineEdit *line = memnew(LineEdit);
	parent->add_child(line);
	line->set_text("Visible value");
	CHECK(AIChatEditorRegistry::describe_node(line, "alias")["value"] == Variant("Visible value"));
	parent->set_meta("ai_control_page_only", true);
	CHECK(AIChatEditorRegistry::describe_node(line, "alias")["error"] == Variant("protected_target"));
	parent->remove_meta("ai_control_page_only");
	line->set_secret(true);
	CHECK(AIChatEditorRegistry::describe_node(line, "alias")["error"] == Variant("protected_target"));
	memdelete(parent);
}
} // namespace TestAIChatEditorComplex
#endif
