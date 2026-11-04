/**************************************************************************/
/*  ai_chat_editor_control.cpp                                            */
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

#include "ai_chat_editor_control.h"

#include "ai_chat_tools.h"

#include "core/config/project_settings.h"
#include "core/io/config_file.h"
#include "core/io/dir_access.h"
#include "core/io/resource_loader.h"
#include "editor/docks/filesystem_dock.h"
#include "editor/docks/scene_tree_dock.h"
#include "editor/editor_data.h"
#include "editor/editor_interface.h"
#include "editor/editor_main_screen.h"
#include "editor/editor_node.h"
#include "editor/inspector/editor_inspector.h"
#include "editor/script/script_editor_plugin.h"
#include "editor/settings/editor_settings.h"
#include "editor/settings/editor_settings_dialog.h"
#include "editor/settings/project_settings_editor.h"
#include "scene/gui/tab_bar.h"
#include "scene/main/window.h"
#include "scene/resources/packed_scene.h"

namespace {
bool bounded_integer(const Variant &p_value, int64_t p_min, int64_t p_max) {
	if (p_value.get_type() == Variant::INT) {
		return int64_t(p_value) >= p_min && int64_t(p_value) <= p_max;
	}
	if (p_value.get_type() != Variant::FLOAT) {
		return false;
	}
	double value = p_value;
	return Math::is_finite(value) && value >= double(p_min) && value <= double(p_max) && Math::floor(value) == value;
}

Dictionary outcome(bool p_ok, const String &p_error = String()) {
	Dictionary result;
	result["ok"] = p_ok;
	if (!p_error.is_empty()) {
		result["error"] = p_error;
	}
	return result;
}
} //namespace

bool AIChatEditorControl::handles(const String &p_name) {
	return p_name == "get_editor_state" || p_name == "editor_action";
}

bool AIChatEditorControl::valid_project_path(const String &p_path) {
	return p_path.begins_with("res://") && p_path == p_path.simplify_path() && !p_path.contains("\\") && !p_path.contains("..") && p_path.length() <= 1024;
}

Array AIChatEditorControl::target_ids() {
	Array result;
	for (const char *id : { "scene_tree", "inspector", "filesystem", "main_screen_tabs", "project_settings", "editor_settings" }) {
		result.push_back(id);
	}
	return result;
}

Control *AIChatEditorControl::resolve_target(const String &p_id) const {
	if (p_id == "scene_tree") {
		return SceneTreeDock::get_singleton();
	}
	if (p_id == "inspector") {
		return EditorInterface::get_singleton()->get_inspector();
	}
	if (p_id == "filesystem") {
		return FileSystemDock::get_singleton();
	}
	if (p_id == "main_screen_tabs") {
		return EditorNode::get_editor_main_screen()->get_tab_bar();
	}
	if (p_id == "project_settings") {
		return ProjectSettingsEditor::get_singleton()->get_tabs();
	}
	if (p_id == "editor_settings") {
		return EditorSettingsDialog::get_singleton()->get_tabs();
	}
	return nullptr;
}

void AIChatEditorControl::clear_highlight() {
	target_id = String();
	target_object = ObjectID();
	hint = String();
	hide();
	set_process(false);
	if (get_parent()) {
		get_parent()->remove_child(this);
	}
}

void AIChatEditorControl::_notification(int p_what) {
	if (p_what == NOTIFICATION_PROCESS) {
		Control *target = resolve_target(target_id);
		if (!target || !target->is_visible_in_tree() || !target->get_window()->is_visible() || target->get_instance_id() != target_object) {
			clear_highlight();
			return;
		}
		if (target->get_window() != get_window()) {
			reparent(target->get_window(), false);
		}
		set_global_position(target->get_global_position());
		set_size(target->get_size());
		pulse += get_process_delta_time();
		queue_redraw();
	} else if (p_what == NOTIFICATION_DRAW) {
		draw_rect(Rect2(Vector2(2, 2), get_size() - Vector2(4, 4)), Color(0.3, 0.7, 1.0, 0.65 + 0.3 * Math::sin(pulse * 4)), false, 3);
		if (!hint.is_empty()) {
			draw_string(get_theme_default_font(), Vector2(8, 24), hint, HORIZONTAL_ALIGNMENT_LEFT, MAX(0.0f, get_size().x - 16), get_theme_default_font_size());
		}
	}
}

Dictionary AIChatEditorControl::get_state() const {
	EditorInterface *editor = EditorInterface::get_singleton();
	Dictionary result = outcome(true);
	Node *root = editor->get_edited_scene_root();
	result["scene"] = root ? Variant(root->get_scene_file_path()) : Variant();
	Array selection;
	for (Node *node : editor->get_selection()->get_full_selected_node_list()) {
		if (root && (root == node || root->is_ancestor_of(node)) && selection.size() < 100) {
			selection.push_back(String(root->get_path_to(node)));
		}
	}
	result["selected_nodes"] = selection;
	EditorMainScreen *screen = EditorNode::get_editor_main_screen();
	result["main_screen"] = screen->get_current_tab_control() ? Variant(screen->get_current_tab_control()->get_name()) : Variant();
	ScriptEditorBase *script = editor->get_script_editor()->get_current_editor();
	Ref<Resource> resource = script ? script->get_edited_resource() : Ref<Resource>();
	result["script"] = resource.is_valid() ? Variant(resource->get_path()) : Variant();
	result["running"] = editor->is_playing_scene();
	result["unsaved_scenes"] = editor->get_unsaved_scenes().slice(0, 100);
	result["script_unsaved"] = script ? Variant(script->is_unsaved()) : Variant();
	result["highlight"] = target_id.is_empty() ? Variant() : Variant(target_id);
	return result;
}

Dictionary AIChatEditorControl::execute(const Dictionary &p_args, bool p_tools_allowed, bool p_consultation, bool p_confirmed) {
	if (!p_tools_allowed || p_consultation) {
		return outcome(false, "permission_denied");
	}
	if (p_args.get("action", Variant()).get_type() != Variant::STRING) {
		return outcome(false, "invalid_action");
	}
	const String action = p_args["action"];
	const Variant target_value = p_args.get("target", "");
	if (target_value.get_type() != Variant::STRING || String(target_value).length() > 1024) {
		return outcome(false, "invalid_target");
	}
	const String target = target_value;
	EditorInterface *editor = EditorInterface::get_singleton();
	if (action == "project_settings" || action == "editor_settings") {
		List<PropertyInfo> properties;
		if (action == "project_settings") {
			ProjectSettings::get_singleton()->get_property_list(&properties);
		} else {
			EditorSettings::get_singleton()->get_property_list(&properties);
		}
		bool found = target.is_empty();
		for (const PropertyInfo &property : properties) {
			if (property.name == target.to_lower() || property.name.begins_with(target.to_lower() + "/")) {
				found = true;
				break;
			}
		}
		if (!found) {
			return outcome(false, "unknown_settings_section");
		}
	}
	if (action == "clear_highlight") {
		clear_highlight();
	} else if (action == "highlight") {
		Control *control = resolve_target(target);
		if (!control || !control->is_visible_in_tree() || !control->get_window()->is_visible()) {
			Dictionary result = outcome(false, "target_unavailable");
			result["candidates"] = target_ids();
			return result;
		}
		if (get_parent()) {
			get_parent()->remove_child(this);
		}
		control->get_window()->add_child(this);
		target_id = target;
		target_object = control->get_instance_id();
		hint = String(p_args.get("hint", "")).left(160);
		set_global_position(control->get_global_position());
		set_size(control->get_size());
		show();
		set_process(true);
	} else if (action == "project_settings") {
		ProjectSettingsEditor::get_singleton()->popup_project_settings(true);
		ProjectSettingsEditor::get_singleton()->set_general_page(target.to_lower());
		if (ProjectSettings::get_singleton()->has_setting(target)) {
			ProjectSettingsEditor::get_singleton()->set_filter(target);
		}
	} else if (action == "editor_settings") {
		EditorSettingsDialog::get_singleton()->popup_edit_settings();
		EditorSettingsDialog::get_singleton()->show_general_section(target.to_lower());
	} else if (action == "main_screen") {
		if ((target != "2D" && target != "3D" && target != "Script" && target != "AssetLib" && target != "AI Chat") || !EditorNode::get_editor_main_screen()->get_dock_by_name(target)) {
			return outcome(false, "unknown_main_screen");
		}
		editor->set_main_screen_editor(target);
	} else if (action == "select_node") {
		Node *root = editor->get_edited_scene_root();
		NodePath path(target);
		if (!root || path.is_absolute() || path.get_subname_count() || target.contains("..")) {
			return outcome(false, "invalid_node_path");
		}
		Node *node = root->get_node_or_null(path);
		if (!node || (node != root && !root->is_ancestor_of(node))) {
			return outcome(false, "node_not_found");
		}
		editor->get_selection()->clear();
		editor->get_selection()->add_node(node);
		editor->edit_node(node);
	} else if (action == "open_scene" || action == "open_script") {
		if (!valid_project_path(target)) {
			return outcome(false, "invalid_project_path");
		}
		Ref<DirAccess> directory = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
		String absolute = ProjectSettings::get_singleton()->get_resource_path();
		for (const String &part : target.trim_prefix("res://").split("/")) {
			absolute = absolute.path_join(part);
			if (directory->is_link(absolute)) {
				return outcome(false, "linked_project_path");
			}
		}
		Ref<Resource> resource = ResourceLoader::load(target);
		if (action == "open_scene") {
			Ref<PackedScene> scene = resource;
			if (scene.is_null()) {
				return outcome(false, "not_a_scene");
			}
			if (EditorNode::get_singleton()->is_changing_scene() || EditorNode::get_singleton()->open_scene(target) != OK) {
				return outcome(false, "scene_open_failed");
			}
		} else {
			Ref<Script> script = resource;
			Variant line = p_args.get("line", 1), column = p_args.get("column", 1);
			if (script.is_null() || !bounded_integer(line, 1, 1000000) || !bounded_integer(column, 1, 1000000)) {
				return outcome(false, "invalid_script_location");
			}
			if (!editor->get_script_editor()->edit(script, int(line) - 1, int(column) - 1)) {
				return outcome(false, "script_open_failed");
			}
		}
	} else if (action == "set_project_setting" || action == "clear_project_setting") {
		ProjectSettings *settings = ProjectSettings::get_singleton();
		if (!settings->has_setting(target)) {
			return outcome(false, "unknown_setting");
		}
		Variant previous = settings->get_setting(target);
		Variant value = action == "clear_project_setting" ? Variant() : p_args.get("value", Variant());
		// JSON numbers are FLOAT in Godot. Convert only exact safe integers.
		if (action == "set_project_setting" && previous.get_type() == Variant::INT && value.get_type() == Variant::FLOAT && bounded_integer(value, -9007199254740991LL, 9007199254740991LL)) {
			value = int64_t(value);
		}
		if (action == "set_project_setting" && value.get_type() != previous.get_type()) {
			return outcome(false, "setting_type_mismatch");
		}
		Dictionary result = outcome(false);
		result["old_value"] = previous;
		result["new_value"] = value;
		const Variant effective_value = action == "clear_project_setting" ? settings->property_get_revert(target) : value;
		result["effective_value"] = effective_value;
		result["target"] = target;
		if (!p_confirmed) {
			result["confirmation_required"] = true;
			return result;
		}
		if (p_args.has("expected_old_value") && p_args["expected_old_value"] != previous) {
			return outcome(false, "setting_changed_since_confirmation");
		}
		// Prepare disk content first. On failure the entire in-memory VariantContainer
		// (including initial value, order and flags) remains untouched.
		const String path = settings->get_resource_path().path_join("project.godot");
		String original, error;
		const bool saved = AIChatTools::read_script(path, original, error) && save_setting_snapshot(path, original, target, value, error);
		if (!saved) {
			result["error"] = "save_failed";
			result["detail"] = error;
		} else {
			settings->set_setting(target, effective_value);
			result["ok"] = true;
			result["readback_value"] = settings->get_setting(target, Variant());
		}
		result["saved"] = saved;
		return result;
	} else {
		return outcome(false, "unknown_action");
	}
	Dictionary result = outcome(true);
	result["action"] = action;
	result["target"] = action == "project_settings" || action == "editor_settings" ? action : target;
	Control *visible_target = resolve_target(result["target"]);
	if (action == "main_screen") {
		visible_target = EditorNode::get_editor_main_screen()->get_dock_by_name(target);
	}
	if (visible_target) {
		result["visible"] = visible_target->is_visible_in_tree() && visible_target->get_window()->is_visible();
	}
	return result;
}

bool AIChatEditorControl::save_setting_snapshot(const String &p_path, const String &p_original, const String &p_target, const Variant &p_value, String &r_error) {
	Ref<ConfigFile> config;
	config.instantiate();
	if (config->parse(p_original) != OK) {
		r_error = "Cannot parse project.godot.";
		return false;
	}
	const int slash = p_target.find_char('/');
	const String section = slash < 0 ? String() : p_target.substr(0, slash);
	const String key = slash < 0 ? p_target : p_target.substr(slash + 1);
	config->set_value(section, key, p_value);
	// The serialized content and compare-before-write baseline share one read.
	return AIChatTools::write_script(p_path, p_original, config->encode_to_text(), true, r_error);
}

Array AIChatEditorControl::tool_definitions() {
	Array tools;
	for (const String &name : { String("get_editor_state"), String("editor_action") }) {
		Dictionary properties, parameters, function, tool;
		Array required;
		if (name == "editor_action") {
			for (const String &key : { String("action"), String("target"), String("hint"), String("line"), String("column"), String("value") }) {
				Dictionary schema;
				if (key != "value") {
					schema["type"] = key == "line" || key == "column" ? "integer" : "string";
				}
				properties[key] = schema;
			}
			required.push_back("action");
		}
		parameters["type"] = "object";
		parameters["properties"] = properties;
		parameters["required"] = required;
		parameters["additionalProperties"] = false;
		function["name"] = name;
		function["description"] = name == "get_editor_state" ? "Read bounded editor state without changing it." : "Semantic editor action. Actions: project_settings, editor_settings, main_screen, open_scene, open_script (1-based line/column), select_node, set_project_setting (value), clear_project_setting, highlight (optional hint), clear_highlight. target is a setting/section, main screen name, res:// path, scene-relative NodePath, or highlight ID: scene_tree, inspector, filesystem, main_screen_tabs, project_settings, editor_settings. Setting writes require host confirmation. Never claim completion on failure.";
		function["parameters"] = parameters;
		tool["type"] = "function";
		tool["function"] = function;
		tools.push_back(tool);
	}
	return tools;
}

AIChatEditorControl::AIChatEditorControl() {
	set_name("AIEditorHighlight");
	set_mouse_filter(MOUSE_FILTER_IGNORE);
	set_focus_mode(FOCUS_NONE);
	set_z_index(4095);
	clear_highlight();
}
