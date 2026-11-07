/**************************************************************************/
/*  test_ai_chat_editor_alias_metadata.cpp                                */
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

TEST_FORCE_LINK(test_ai_chat_editor_alias_metadata)

#ifdef TOOLS_ENABLED
#include "core/io/json.h"
#include "editor/docks/ai_chat_editor_control.h"
#include "editor/docks/ai_chat_editor_registry.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/popup_menu.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

namespace TestAIChatEditorAliasMetadata {

TEST_CASE("[SceneTree][AIChat][AliasMetadata] Explicit aliases expose bounded live metadata") {
	AIChatEditorControl control;
	LineEdit *line = memnew(LineEdit);
	SceneTree::get_singleton()->get_root()->add_child(line);
	line->set_text(String::utf8("甲乙丙"));
	line->select(1, 2);
	REQUIRE(control.register_target("plugin.alias_field", line, "Alias field", "Plugin page"));
	Dictionary description = control.describe_target("plugin.alias_field");
	CHECK(bool(description["ok"]));
	CHECK_FALSE(bool(description["automatic"]));
	CHECK(description["display_name"] == Variant("Alias field"));
	CHECK(description["owner_screen"] == Variant("Plugin page"));
	CHECK(description["class"] == Variant("LineEdit"));
	CHECK(description["target_instance"] == Variant(int64_t(line->get_instance_id())));
	CHECK(description["window_instance"] == Variant(int64_t(line->get_window()->get_instance_id())));
	CHECK(Array(description["position"]).size() == 2);
	CHECK(Array(description["size"]).size() == 2);
	CHECK(description.has("selection"));
	CHECK(description["value"] == Variant(String::utf8("甲乙丙")));
	line->set_editable(false);
	description = control.describe_target("plugin.alias_field");
	CHECK(bool(description["readonly"]));
	CHECK(description["unavailable_reason"] == Variant("readonly"));
	CHECK_FALSE(Array(description["actions"]).has("set_text"));
	// Escaped JSON is larger than its source UTF-8 bytes.
	line->set_text(String("\\").repeat(4096));
	description = control.describe_target("plugin.alias_field");
	CHECK(bool(description["value_omitted"]));
	CHECK_FALSE(description.has("value"));
	CHECK_FALSE(description.has("selection"));
	memdelete(line);
}

TEST_CASE("[SceneTree][AIChat][AliasMetadata] An alias cannot disclose a newly protected field") {
	AIChatEditorControl control;
	Control *parent = memnew(Control);
	LineEdit *line = memnew(LineEdit);
	parent->add_child(line);
	SceneTree::get_singleton()->get_root()->add_child(parent);
	line->set_text("PRIVATE_SENTINEL");
	REQUIRE(control.register_target("plugin.private_field", line, "Field", "Plugin"));
	CHECK(control.describe_target("plugin.private_field").has("value"));
	line->set_secret(true);
	Dictionary description = control.describe_target("plugin.private_field");
	CHECK_FALSE(bool(description["ok"]));
	CHECK_FALSE(bool(description["available"]));
	CHECK(description["error"] == Variant("protected_target"));
	CHECK_FALSE(JSON::stringify(description).contains("PRIVATE_SENTINEL"));
	CHECK_FALSE(description.has("value"));
	CHECK(Array(description["actions"]).is_empty());
	line->set_secret(false);
	for (const StringName &flag : { StringName("ai_control_exclude"), StringName("ai_control_page_only") }) {
		parent->set_meta(flag, true);
		description = control.describe_target("plugin.private_field");
		CHECK_FALSE(bool(description["available"]));
		CHECK_FALSE(description.has("value"));
		parent->remove_meta(flag);
	}
	memdelete(parent);
}

TEST_CASE("[SceneTree][AIChat][AliasMetadata] Descriptions do not keep a deleted alias alive") {
	AIChatEditorControl control;
	LineEdit *line = memnew(LineEdit);
	SceneTree::get_singleton()->get_root()->add_child(line);
	REQUIRE(control.register_target("plugin.closed_field", line, "Field", "Plugin"));
	CHECK(bool(control.describe_target("plugin.closed_field")["available"]));
	memdelete(line);
	Dictionary description = control.describe_target("plugin.closed_field");
	CHECK(bool(description["ok"]));
	CHECK_FALSE(bool(description["available"]));
	CHECK_FALSE(bool(description["visible"]));
	CHECK_FALSE(description.has("value"));
	CHECK_FALSE(description.has("target_instance"));
	CHECK(Array(description["actions"]).is_empty());
	CHECK(control.describe_target("plugin.unknown")["error"] == Variant("unknown_target"));
}

TEST_CASE("[SceneTree][AIChat][AliasMetadata] Popup windows expose geometry without a Control cast") {
	PopupMenu *menu = memnew(PopupMenu);
	SceneTree::get_singleton()->get_root()->add_child(menu);
	Dictionary description = AIChatEditorRegistry::describe_node(menu, "editor.popup_metadata", "Popup page");
	CHECK(bool(description["ok"]));
	CHECK(description["class"] == Variant("PopupMenu"));
	CHECK(description["window_instance"] == Variant(int64_t(menu->get_instance_id())));
	CHECK(Array(description["position"]).size() == 2);
	CHECK(Array(description["size"]).size() == 2);
	CHECK(description.has("focused"));
	CHECK(description.has("focusable"));
	CHECK_FALSE(bool(description["readonly"]));
	CHECK_FALSE(bool(description["visible"]));
	CHECK(description["unavailable_reason"] == Variant("not_visible"));
	menu->set_meta("_ai_complex_submenu_status", 42);
	CHECK(AIChatEditorRegistry::describe_node(menu, "editor.popup_metadata")["submenu_request_status"] == Variant("idle"));
	menu->set_meta("ai_control_exclude", true);
	CHECK_FALSE(bool(AIChatEditorRegistry::describe_node(menu, "editor.popup_metadata")["ok"]));
	memdelete(menu);
}

} // namespace TestAIChatEditorAliasMetadata
#endif
