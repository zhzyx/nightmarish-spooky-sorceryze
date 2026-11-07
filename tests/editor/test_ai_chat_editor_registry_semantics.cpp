/**************************************************************************/
/*  test_ai_chat_editor_registry_semantics.cpp                             */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).  */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                    */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining    */
/* a copy of this software and associated documentation files (the          */
/* "Software"), to deal in the Software without restriction, including      */
/* without limitation the rights to use, copy, modify, merge, publish,       */
/* distribute, sublicense, and/or sell copies of the Software, and to        */
/* permit persons to whom the Software is furnished to do so, subject to    */
/* the following conditions:                                               */
/*                                                                        */
/* The above copyright notice and this permission notice shall be           */
/* included in all copies or substantial portions of the Software.          */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,          */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF       */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY    */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,     */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE        */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                   */
/**************************************************************************/

#include "tests/test_macros.h"

TEST_FORCE_LINK(test_ai_chat_editor_registry_semantics)

#ifdef TOOLS_ENABLED
#include "core/config/project_settings.h"
#include "core/io/json.h"
#include "editor/docks/ai_chat_editor_registry.h"
#include "editor/inspector/editor_inspector.h"
#include "scene/gui/color_picker.h"
#include "scene/gui/item_list.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/scroll_container.h"
#include "scene/gui/tab_bar.h"
#include "scene/gui/text_edit.h"
#include "scene/gui/tree.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

namespace TestAIChatEditorRegistrySemantics {
static Dictionary authorize(const Dictionary &p_args, const Dictionary &p_preview) {
	Dictionary args = p_args.duplicate(true);
	args["expected_target_instance"] = p_preview["target_instance"];
	args["expected_old_value"] = p_preview["old_value"];
	return args;
}

TEST_CASE("[SceneTree][AIChat] Registry text reads and edits preserve confirmation boundaries") {
	AIChatEditorRegistry registry;
	LineEdit *line = memnew(LineEdit);
	SceneTree::get_singleton()->get_root()->add_child(line);
	line->set_text(String::utf8("甲乙丙"));
	Dictionary args;
	args["action"] = "read_text";
	CHECK(registry.perform(line, "test", args, false)["value"] == Variant(String::utf8("甲乙丙")));
	args["action"] = "replace_text_range";
	args = JSON::parse_string("{\"action\":\"replace_text_range\",\"start\":1,\"end\":2,\"value\":\"X\"}");
	CHECK(args["start"].get_type() == Variant::FLOAT);
	Dictionary preview = registry.perform(line, "test", args, false);
	CHECK(bool(preview["confirmation_required"]));
	CHECK(line->get_text() == String::utf8("甲乙丙"));
	CHECK_FALSE(bool(registry.perform(line, "test", args, true)["ok"]));
	CHECK(bool(registry.perform(line, "test", authorize(args, preview), true)["ok"]));
	CHECK(line->get_text() == String::utf8("甲X丙"));
	CHECK_FALSE(bool(registry.perform(line, "test", authorize(args, preview), true)["ok"]));
	args.clear();
	args["action"] = "undo_text";
	preview = registry.perform(line, "test", args, false);
	CHECK(bool(registry.perform(line, "test", authorize(args, preview), true)["ok"]));
	CHECK(line->get_text() == String::utf8("甲乙丙"));
	args["action"] = "append_text";
	args["value"] = "safe";
	preview = registry.perform(line, "test", args, false);
	CHECK(bool(registry.perform(line, "test", authorize(args, preview), true)["ok"]));
	line->set_text("user edit");
	args["action"] = "undo_text";
	CHECK(registry.perform(line, "test", args, false)["error"] == Variant("undo_unavailable"));
	args["action"] = "replace_text_range";
	args["start"] = -1;
	args["end"] = 2;
	args["value"] = "X";
	CHECK(registry.perform(line, "test", args, false)["error"] == Variant("invalid_text_range"));
	args["action"] = "append_text";
	args["value"] = String("x").repeat(8192);
	CHECK(registry.perform(line, "test", args, false)["error"] == Variant("invalid_input_value"));
	line->set_secret(true);
	args["action"] = "read_text";
	CHECK(registry.perform(line, "test", args, false)["error"] == Variant("protected_target"));
	line->set_secret(false);
	line->set_name("APIKeyInput");
	CHECK(registry.perform(line, "test", args, false)["error"] == Variant("protected_target"));
	memdelete(line);
}

TEST_CASE("[SceneTree][AIChat] Registry rejects excluded ancestors and stale tree identities") {
	AIChatEditorRegistry registry;
	Control *page = memnew(Control);
	SceneTree::get_singleton()->get_root()->add_child(page);
	Tree *tree = memnew(Tree);
	page->add_child(tree);
	TreeItem *root = tree->create_item();
	root->set_text(0, "Root");
	TreeItem *child = tree->create_item(root);
	child->set_text(0, "Before");
	Dictionary args;
	args["action"] = "select_tree_item";
	args["index"] = 1;
	Dictionary preview = registry.perform(tree, "test", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	child->set_text(0, "After");
	CHECK(registry.perform(tree, "test", authorize(args, preview), true)["error"] == Variant("target_changed_since_confirmation"));
	preview = registry.perform(tree, "test", args, false);
	CHECK(bool(registry.perform(tree, "test", authorize(args, preview), true)["ok"]));
	CHECK(child->is_selected(0));
	page->set_meta("ai_control_page_only", true);
	CHECK(registry.perform(tree, "test", args, false)["error"] == Variant("protected_target"));
	page->remove_meta("ai_control_page_only");
	page->set_meta("ai_control_exclude", true);
	CHECK(registry.perform(tree, "test", args, false)["error"] == Variant("protected_target"));
	memdelete(page);
}

TEST_CASE("[SceneTree][AIChat] Registry item and JSON color actions validate capacity and state") {
	AIChatEditorRegistry registry;
	ItemList *items = memnew(ItemList);
	SceneTree::get_singleton()->get_root()->add_child(items);
	items->add_item("Allowed");
	items->add_item("Disabled");
	items->set_item_disabled(1, true);
	Dictionary args;
	args["action"] = "select_item";
	args["index"] = 1;
	CHECK(registry.perform(items, "test", args, false)["error"] == Variant("invalid_item_index"));
	args = JSON::parse_string("{\"action\":\"select_item\",\"index\":0}");
	CHECK(args["index"].get_type() == Variant::FLOAT);
	Dictionary preview = registry.perform(items, "test", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	items->set_item_text(0, "Replaced");
	CHECK(registry.perform(items, "test", authorize(args, preview), true)["error"] == Variant("target_changed_since_confirmation"));
	args["index"] = int64_t(1) << 40;
	CHECK(registry.perform(items, "test", args, false)["error"] == Variant("invalid_item_index"));
	memdelete(items);

	ColorPicker *picker = memnew(ColorPicker);
	SceneTree::get_singleton()->get_root()->add_child(picker);
	args.clear();
	args["action"] = "set_color";
	Array color;
	color.push_back(0.25);
	color.push_back(0.5);
	color.push_back(0.75);
	color.push_back(1.0);
	args["value"] = color;
	preview = registry.perform(picker, "test", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	CHECK(bool(registry.perform(picker, "test", authorize(args, preview), true)["ok"]));
	CHECK(picker->get_pick_color() == Color(0.25, 0.5, 0.75, 1.0));
	color[0] = 2.0;
	CHECK(registry.perform(picker, "test", args, false)["error"] == Variant("invalid_input_value"));
	memdelete(picker);
}

TEST_CASE("[SceneTree][AIChat] Registry selection binds caret state and item reads paginate") {
	AIChatEditorRegistry registry;
	LineEdit *line = memnew(LineEdit);
	SceneTree::get_singleton()->get_root()->add_child(line);
	line->set_text("abcdef");
	Dictionary args = JSON::parse_string("{\"action\":\"select_text_range\",\"start\":1,\"end\":3}");
	Dictionary preview = registry.perform(line, "test", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	line->set_caret_column(4);
	CHECK(registry.perform(line, "test", authorize(args, preview), true)["error"] == Variant("target_changed_since_confirmation"));
	preview = registry.perform(line, "test", args, false);
	CHECK(bool(registry.perform(line, "test", authorize(args, preview), true)["ok"]));
	CHECK(line->get_selection_from_column() == 1);
	CHECK(line->get_selection_to_column() == 3);
	args["action"] = "read_text";
	Dictionary selection = registry.perform(line, "test", args, false)["selection"];
	CHECK(int(selection["start"]) == 1);
	CHECK(int(selection["end"]) == 3);
	memdelete(line);

	ItemList *items = memnew(ItemList);
	SceneTree::get_singleton()->get_root()->add_child(items);
	for (int i = 0; i < 205; i++) {
		items->add_item(String::num_int64(i));
	}
	args = JSON::parse_string("{\"action\":\"read_items\",\"limit\":100,\"offset\":100}");
	Dictionary page = registry.perform(items, "test", args, false);
	CHECK(bool(page["ok"]));
	CHECK(Array(page["items"]).size() == 100);
	CHECK(int(page["total"]) == 205);
	CHECK(int(page["next_offset"]) == 200);
	CHECK(int(Dictionary(Array(page["items"])[0])["index"]) == 100);
	args["limit"] = 101;
	CHECK(registry.perform(items, "test", args, false)["error"] == Variant("invalid_item_page"));
	memdelete(items);
}

TEST_CASE("[SceneTree][AIChat] Registry scroll JSON rejects fractional coordinates and tree capacity") {
	AIChatEditorRegistry registry;
	ScrollContainer *scroll = memnew(ScrollContainer);
	SceneTree::get_singleton()->get_root()->add_child(scroll);
	Dictionary args = JSON::parse_string("{\"action\":\"scroll_to\",\"value\":[0.5,0]}");
	CHECK(registry.perform(scroll, "test", args, false)["error"] == Variant("invalid_input_value"));
	args = JSON::parse_string("{\"action\":\"scroll_to\",\"value\":[0,0]}");
	Dictionary preview = registry.perform(scroll, "test", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	CHECK(bool(registry.perform(scroll, "test", authorize(args, preview), true)["ok"]));
	memdelete(scroll);

	Tree *tree = memnew(Tree);
	SceneTree::get_singleton()->get_root()->add_child(tree);
	TreeItem *root = tree->create_item();
	for (int i = 0; i < 4096; i++) {
		tree->create_item(root);
	}
	args = JSON::parse_string("{\"action\":\"select_tree_item\",\"index\":0}");
	CHECK(registry.perform(tree, "test", args, false)["error"] == Variant("item_capacity_exceeded"));
	memdelete(tree);
}

TEST_CASE("[SceneTree][AIChat] Registry TextEdit undo binds native history version") {
	AIChatEditorRegistry registry;
	TextEdit *text = memnew(TextEdit);
	SceneTree::get_singleton()->get_root()->add_child(text);
	text->set_text("before");
	Dictionary args = JSON::parse_string("{\"action\":\"append_text\",\"value\":\" after\"}");
	Dictionary preview = registry.perform(text, "test", args, false);
	REQUIRE(bool(preview.get("confirmation_required", false)));
	CHECK(bool(registry.perform(text, "test", authorize(args, preview), true)["ok"]));
	CHECK(text->get_text() == "before after");
	args.clear();
	args["action"] = "undo_text";
	preview = registry.perform(text, "test", args, false);
	CHECK(bool(registry.perform(text, "test", authorize(args, preview), true)["ok"]));
	CHECK(text->get_text() == "before");
	args["action"] = "append_text";
	args["value"] = " after";
	preview = registry.perform(text, "test", args, false);
	CHECK(bool(registry.perform(text, "test", authorize(args, preview), true)["ok"]));
	text->begin_complex_operation();
	text->insert_text("!", 0, 0);
	text->remove_text(0, 0, 0, 1);
	text->end_complex_operation();
	args["action"] = "undo_text";
	CHECK(registry.perform(text, "test", args, false)["error"] == Variant("undo_unavailable"));
	memdelete(text);
}

TEST_CASE("[AIChat] Registry pagination reports bounded empty pages") {
	AIChatEditorRegistry registry;
	Dictionary page = registry.find_page("", 20000, -1);
	CHECK(Array(page["targets"]).is_empty());
	CHECK(int(page["total"]) == 0);
	CHECK(int(page["offset"]) == 0);
	CHECK(int(page["limit"]) == 20);
	CHECK(int(page["next_offset"]) == -1);
	CHECK(page.has("revision"));
	CHECK(registry.find("", 20).is_empty());
}
TEST_CASE("[SceneTree][AIChat] Registry item pages bound escaped UTF-8 bytes without losing entries") {
	AIChatEditorRegistry registry;
	ItemList *items = memnew(ItemList);
	SceneTree::get_singleton()->get_root()->add_child(items);
	for (int i = 0; i < 100; i++) {
		items->add_item(String::chr(1).repeat(120));
	}
	int offset = 0;
	int seen = 0;
	while (offset >= 0) {
		Dictionary args;
		args["action"] = "read_items";
		args["limit"] = 100;
		args["offset"] = offset;
		const Dictionary page = registry.perform(items, "bounded", args, false);
		REQUIRE(bool(page.get("ok", false)));
		CHECK(JSON::stringify(page).utf8().length() < 16384);
		const Array entries = page["items"];
		REQUIRE(!entries.is_empty());
		for (const Variant &entry : entries) {
			CHECK(int(Dictionary(entry)["index"]) == seen++);
		}
		offset = page["next_offset"];
	}
	CHECK(seen == 100);
	memdelete(items);
}

TEST_CASE("[SceneTree][AIChat] Registry excludes host authority rendered through generic inspector properties") {
	AIChatEditorRegistry registry;
	EditorProperty *property = memnew(EditorProperty);
	property->set_object_and_property(ProjectSettings::get_singleton(), "ai_chat/auto_execute_commands");
	SceneTree::get_singleton()->get_root()->add_child(property);
	LineEdit *line = memnew(LineEdit);
	property->add_child(line);
	line->set_text("host-state-must-not-be-read");
	Dictionary args;
	args["action"] = "read_text";
	CHECK(registry.perform(line, "protected", args, false)["error"] == Variant("protected_target"));
	property->set_object_and_property(ProjectSettings::get_singleton(), "custom/api_key");
	CHECK(registry.perform(line, "protected", args, false)["error"] == Variant("protected_target"));
	memdelete(property);
}

} // namespace TestAIChatEditorRegistrySemantics
#endif
