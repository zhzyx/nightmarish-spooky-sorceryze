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

#include "core/config/project_settings.h"
#include "core/io/config_file.h"
#include "core/io/dir_access.h"
#include "core/io/json.h"
#include "core/io/resource_loader.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/os/time.h"
#include "editor/docks/ai_chat_tools.h"
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
#include "scene/gui/base_button.h"
#include "scene/gui/foldable_container.h"
#include "scene/gui/scroll_container.h"
#include "scene/gui/tab_bar.h"
#include "scene/gui/tab_container.h"
#include "scene/main/timer.h"
#include "scene/main/window.h"
#include "scene/resources/packed_scene.h"

namespace {
const int MAX_WORKFLOW_BYTES = 16384;
const int MAX_WORKFLOW_STEPS = 32;

String workflow_path() {
	return ProjectSettings::get_singleton()->globalize_path("res://.godot/editor/ai_chat_guidance.json");
}

bool preparation_action(const String &p_action) {
	return p_action == "project_settings" || p_action == "editor_settings" || p_action == "main_screen" || p_action == "open_scene" || p_action == "open_script" || p_action == "select_node" || p_action == "reveal_target";
}

bool declarative_action(const Variant &p_value, bool p_writing) {
	if (p_value.get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary args = p_value;
	for (const Variant &key : args.keys()) {
		if (key != "action" && key != "target" && key != "line" && key != "column" && key != "value") {
			return false;
		}
	}
	if (args.get("action", Variant()).get_type() != Variant::STRING || args.get("target", Variant()).get_type() != Variant::STRING) {
		return false;
	}
	const String action = args.get("action", "");
	return preparation_action(action) || (p_writing && (action == "set_project_setting" || action == "clear_project_setting"));
}
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

AIChatEditorControl *AIChatEditorControl::singleton = nullptr;

void AIChatEditorControl::_bind_methods() {
	ClassDB::bind_static_method("AIChatEditorControl", D_METHOD("get_singleton"), &AIChatEditorControl::get_singleton);
	ClassDB::bind_method(D_METHOD("register_target", "id", "control", "display_name", "owner_screen"), &AIChatEditorControl::register_target, DEFVAL(String()));
	ClassDB::bind_method(D_METHOD("unregister_target", "id"), &AIChatEditorControl::unregister_target);
	ClassDB::bind_method(D_METHOD("find_targets", "query", "limit"), &AIChatEditorControl::find_targets, DEFVAL(8));
	ClassDB::bind_method(D_METHOD("describe_target", "id"), &AIChatEditorControl::describe_target);
	ClassDB::bind_method(D_METHOD("guidance_status"), &AIChatEditorControl::guidance_status);
}

bool AIChatEditorControl::register_target(const String &p_id, Control *p_control, const String &p_name, const String &p_screen) {
	if (!p_id.begins_with("plugin.") || p_id.length() > 128 || p_id.ends_with(".") || p_id.contains("..") || !p_control || !p_control->is_inside_tree() || p_name.is_empty() || p_name.length() > 120 || p_screen.length() > 120 || targets.size() >= 128) {
		return false;
	}
	for (int i = 0; i < p_id.length(); i++) {
		const char32_t c = p_id[i];
		if (!(c == '.' || c == '_' || c == '-' || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'))) {
			return false;
		}
	}
	const Target *existing = targets.getptr(p_id);
	if (existing && ObjectDB::get_instance(existing->control) && existing->control != p_control->get_instance_id()) {
		return false;
	}
	targets[p_id] = { p_control->get_instance_id(), p_name, p_screen };
	return true;
}

bool AIChatEditorControl::unregister_target(const String &p_id) {
	if (target_id == p_id) {
		_disconnect_observer();
		clear_highlight();
	}
	return targets.erase(p_id);
}

Dictionary AIChatEditorControl::describe_target(const String &p_id) const {
	const bool core = target_ids().has(p_id);
	const Target *entry = targets.getptr(p_id);
	Dictionary result = outcome(core || entry, core || entry ? String() : String("unknown_target"));
	result["id"] = p_id;
	result["display_name"] = entry ? entry->name : p_id.replace("_", " ").capitalize();
	result["owner_screen"] = entry ? entry->screen : p_id == "project_settings" || p_id == "editor_settings" ? p_id
																											 : String("editor");
	Control *control = resolve_target(p_id);
	result["available"] = control && control->is_inside_tree();
	result["visible"] = control && control->is_visible_in_tree() && control->get_window() && control->get_window()->is_visible();
	Array actions;
	actions.push_back("highlight");
	actions.push_back("reveal_target");
	result["actions"] = actions;
	return result;
}

Array AIChatEditorControl::find_targets(const String &p_query, int p_limit) const {
	Array ids = target_ids();
	for (const KeyValue<String, Target> &entry : targets) {
		ids.push_back(entry.key);
	}
	Array result;
	if (ids.has(p_query)) {
		result.push_back(describe_target(p_query));
		return result;
	}
	const String query = p_query.strip_edges().to_lower().left(128);
	for (const Variant &id : ids) {
		Dictionary description = describe_target(id);
		if (query.is_empty() || String(id).contains(query) || String(description["display_name"]).to_lower().contains(query)) {
			result.push_back(description);
			if (result.size() >= CLAMP(p_limit, 1, 20)) {
				break;
			}
		}
	}
	return result;
}

Dictionary AIChatEditorControl::guidance_status() const {
	Dictionary result = outcome(true);
	for (const String &key : { "status", "title", "current_step", "error", "last_observation", "restored" }) {
		result[key] = workflow.get(key, Variant());
	}
	const Array steps = workflow.get("steps", Array());
	result["step_count"] = steps.size();
	const int index = workflow.get("current_step", 0);
	if (index >= 0 && index < steps.size()) {
		const Dictionary step = steps[index];
		result["target"] = step.get("target", "");
		result["message"] = step.get("message", "");
	}
	result["highlight_visible"] = is_visible_in_tree();
	if (workflow.get("status", "") == "failed") {
		result["recovery"] = "Restore the target's dock/window and call guidance_relocate, or cancel the workflow.";
	}
	return result;
}

bool AIChatEditorControl::_valid_steps(const Array &p_steps) {
	if (p_steps.is_empty() || p_steps.size() > MAX_WORKFLOW_STEPS || JSON::stringify(p_steps).utf8().length() > MAX_WORKFLOW_BYTES) {
		return false;
	}
	for (const Variant &value : p_steps) {
		if (value.get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary step = value;
		for (const Variant &key : step.keys()) {
			if (key != "target" && key != "message" && key != "prepare" && key != "execute" && key != "observe") {
				return false;
			}
		}
		if (step.get("target", Variant()).get_type() != Variant::STRING || String(step["target"]).is_empty() || String(step["target"]).length() > 128 || step.get("message", "").get_type() != Variant::STRING || String(step.get("message", "")).length() > 240) {
			return false;
		}
		if ((step.has("prepare") && !declarative_action(step["prepare"], false)) || (step.has("execute") && !declarative_action(step["execute"], true))) {
			return false;
		}
		if (step.get("observe", Dictionary()).get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary observe = step.get("observe", Dictionary());
		for (const Variant &key : observe.keys()) {
			if (key != "type" && key != "setting" && key != "path" && key != "value") {
				return false;
			}
		}
		const String type = observe.get("type", "manual");
		if (type != "manual" && type != "control_pressed" && type != "target_visible" && type != "main_screen" && type != "selected_node" && type != "project_setting") {
			return false;
		}
		for (const String &key : { "setting", "path", "value" }) {
			if ((type == "main_screen" && key == "value") || (type == "selected_node" && key == "path") || (type == "project_setting" && key == "setting")) {
				if (observe.get(key, Variant()).get_type() != Variant::STRING || String(observe[key]).length() > 1024) {
					return false;
				}
			}
		}
	}
	return true;
}

void AIChatEditorControl::_persist_guidance() const {
	const String status = workflow.get("status", "");
	if (status.is_empty() || status == "cancelled" || status == "completed") {
		if (FileAccess::exists(workflow_path())) {
			DirAccess::remove_absolute(workflow_path());
		}
		return;
	}
	// Persist only declarative input and progress, never pointers or observed values.
	Dictionary saved;
	for (const String &key : { "title", "steps", "current_step" }) {
		saved[key] = workflow.get(key, Variant());
	}
	Ref<FileAccess> file = FileAccess::open(workflow_path(), FileAccess::WRITE);
	if (file.is_valid()) {
		file->store_string(JSON::stringify(saved));
	}
}

void AIChatEditorControl::_restore_guidance() {
	Ref<FileAccess> file = FileAccess::open(workflow_path(), FileAccess::READ);
	if (file.is_null() || file->get_length() > MAX_WORKFLOW_BYTES + 1024) {
		return;
	}
	const Variant saved = JSON::parse_string(file->get_as_text());
	if (saved.get_type() != Variant::DICTIONARY) {
		return;
	}
	const Dictionary restored = saved;
	if (restored.get("steps", Variant()).get_type() != Variant::ARRAY || !_valid_steps(restored["steps"]) || !bounded_integer(restored.get("current_step", 0), 0, Array(restored["steps"]).size() - 1)) {
		return;
	}
	workflow["title"] = String(restored.get("title", "")).left(160);
	workflow["steps"] = restored["steps"];
	workflow["current_step"] = int(restored.get("current_step", 0));
	workflow["status"] = "preview";
	workflow["restored"] = true;
}

void AIChatEditorControl::_disconnect_observer() {
	BaseButton *button = ObjectDB::get_instance<BaseButton>(observed_button);
	const Callable callback = callable_mp(this, &AIChatEditorControl::_target_pressed);
	if (button && button->is_connected("pressed", callback)) {
		button->disconnect("pressed", callback);
	}
	observed_button = ObjectID();
}

void AIChatEditorControl::_set_guidance_status(const String &p_status, const String &p_error) {
	workflow["status"] = p_status;
	workflow["error"] = p_error;
	if (p_status != "waiting_user") {
		_disconnect_observer();
		if (Timer *timer = ObjectDB::get_instance<Timer>(guidance_timer)) {
			timer->stop();
		}
	}
	if (p_status == "failed" || p_status == "completed" || p_status == "cancelled") {
		clear_highlight();
	}
	_persist_guidance();
}

void AIChatEditorControl::cancel_guidance() {
	if (!workflow.is_empty() && workflow.get("status", "") != "completed") {
		_set_guidance_status("cancelled");
	}
	clear_highlight();
}

void AIChatEditorControl::suspend_guidance() {
	_disconnect_observer();
	if (Timer *timer = ObjectDB::get_instance<Timer>(guidance_timer)) {
		timer->stop();
	}
	_persist_guidance();
	clear_highlight();
}

void AIChatEditorControl::_activate_step(bool p_prepare) {
	guidance_revision++;
	_disconnect_observer();
	clear_highlight();
	const Array steps = workflow.get("steps", Array());
	const int index = workflow.get("current_step", 0);
	if (index < 0 || index >= steps.size()) {
		_set_guidance_status("completed");
		return;
	}
	const Dictionary step = steps[index];
	const Dictionary observe = step.get("observe", Dictionary());
	const String type = observe.get("type", "manual");
	const Dictionary state = get_state();
	if (type == "project_setting") {
		const String setting = observe.get("setting", "");
		workflow["baseline"] = ProjectSettings::get_singleton()->get_setting(setting, Variant());
	} else if (type == "main_screen") {
		workflow["baseline"] = state.get("main_screen", Variant());
	} else if (type == "selected_node") {
		workflow["baseline"] = state.get("selected_nodes", Array());
	} else if (type == "target_visible") {
		workflow["baseline"] = describe_target(step["target"])["visible"];
	}
	workflow["status"] = "running";
	if (p_prepare && step.has("prepare")) {
		const Dictionary prepared = execute(step["prepare"], true, false);
		if (!bool(prepared.get("ok", false))) {
			_set_guidance_status("failed", prepared.get("error", "preparation_failed"));
			return;
		}
	}
	target_missing_since = 0;
	_set_guidance_status("waiting_user");
	Timer *timer = ObjectDB::get_instance<Timer>(guidance_timer);
	if (!timer) {
		timer = memnew(Timer);
		guidance_timer = timer->get_instance_id();
		timer->set_wait_time(0.1);
		timer->connect("timeout", callable_mp(this, &AIChatEditorControl::_poll_guidance));
		EditorNode::get_singleton()->get_gui_base()->add_child(timer);
	}
	timer->start();
	_poll_guidance();
}

void AIChatEditorControl::_advance(const String &p_observation) {
	Dictionary observation;
	observation["type"] = p_observation;
	const Array steps = workflow.get("steps", Array());
	const Dictionary step = steps[int(workflow.get("current_step", 0))];
	const Dictionary observe = step.get("observe", Dictionary());
	if (p_observation == "project_setting") {
		Variant value = ProjectSettings::get_singleton()->get_setting(observe.get("setting", ""), Variant());
		if (JSON::stringify(value).utf8().length() <= 1024) {
			observation["value"] = value;
		} else {
			observation["value_omitted"] = true;
		}
	} else if (p_observation == "main_screen") {
		observation["value"] = get_state().get("main_screen", Variant());
	} else if (p_observation == "selected_node") {
		observation["path"] = observe.get("path", "");
	} else if (p_observation == "control_pressed" || p_observation == "target_visible") {
		observation["target"] = step.get("target", "");
	}
	workflow["last_observation"] = observation;
	workflow["current_step"] = int(workflow.get("current_step", 0)) + 1;
	_activate_step(true);
}

void AIChatEditorControl::_target_pressed() {
	if (workflow.get("status", "") != "waiting_user") {
		return;
	}
	const Array steps = workflow["steps"];
	const Dictionary step = steps[int(workflow["current_step"])];
	Control *target = resolve_target(step["target"]);
	if (target && target->get_instance_id() == observed_button && target->is_visible_in_tree() && target->get_window()->is_visible()) {
		_advance("control_pressed");
	}
}

void AIChatEditorControl::_poll_guidance() {
	if (workflow.get("status", "") != "waiting_user") {
		return;
	}
	const Array steps = workflow["steps"];
	const Dictionary step = steps[int(workflow["current_step"])];
	const String id = step["target"];
	Control *target = resolve_target(id);
	if (!target || !target->is_visible_in_tree() || !target->get_window()->is_visible()) {
		_disconnect_observer();
		if (target_missing_since == 0) {
			target_missing_since = Time::get_singleton()->get_ticks_msec();
		}
		if (Time::get_singleton()->get_ticks_msec() - target_missing_since > 5000) {
			clear_highlight();
			_set_guidance_status("failed", "target_unavailable");
		}
		return;
	}
	target_missing_since = 0;
	if (target_object != target->get_instance_id() || target_id != id || !is_visible_in_tree()) {
		Dictionary highlight;
		highlight["action"] = "highlight";
		highlight["target"] = id;
		highlight["hint"] = step.get("message", "");
		execute(highlight, true, false);
	}
	const Dictionary observe = step.get("observe", Dictionary());
	const String type = observe.get("type", "manual");
	const Variant baseline = workflow.get("baseline", Variant());
	bool complete = false;
	if (type == "control_pressed") {
		BaseButton *button = Object::cast_to<BaseButton>(target);
		if (!button) {
			_set_guidance_status("failed", "observer_requires_button");
		} else if (observed_button != button->get_instance_id()) {
			_disconnect_observer();
			observed_button = button->get_instance_id();
			button->connect("pressed", callable_mp(this, &AIChatEditorControl::_target_pressed));
		}
	} else if (type == "target_visible") {
		complete = baseline.get_type() == Variant::BOOL && !bool(baseline);
	} else if (type == "project_setting") {
		const Variant value = ProjectSettings::get_singleton()->get_setting(observe.get("setting", ""), Variant());
		Variant expected = observe.get("value", Variant());
		if (value.get_type() == Variant::INT && expected.get_type() == Variant::FLOAT && bounded_integer(expected, -9007199254740991LL, 9007199254740991LL)) {
			expected = int64_t(expected);
		}
		complete = value != baseline && (!observe.has("value") || value == expected);
	} else if (type == "main_screen") {
		const Variant value = get_state().get("main_screen", Variant());
		complete = value != baseline && value == observe.get("value", Variant());
	} else if (type == "selected_node") {
		const Array value = get_state().get("selected_nodes", Array());
		complete = value != baseline && value.has(observe.get("path", ""));
	}
	if (complete) {
		_advance(type);
	}
}

Dictionary AIChatEditorControl::_guidance_action(const Dictionary &p_args, bool p_confirmed) {
	const String action = p_args["action"];
	if (action == "find_targets") {
		Dictionary result = outcome(true);
		result["targets"] = find_targets(p_args.get("query", ""), p_args.get("limit", 8));
		return result;
	}
	if (action == "describe_target") {
		Dictionary result = describe_target(p_args.get("target", ""));
		if (!bool(result["ok"])) {
			result["candidates"] = find_targets("", 5);
		}
		return result;
	}
	if (action == "start_guidance") {
		if (p_args.get("steps", Variant()).get_type() != Variant::ARRAY || !_valid_steps(p_args["steps"])) {
			return outcome(false, "invalid_guidance_steps");
		}
		cancel_guidance();
		guidance_revision++;
		workflow.clear();
		workflow["title"] = String(p_args.get("title", "Guided workflow")).left(160);
		workflow["steps"] = Array(p_args["steps"]).duplicate(true);
		workflow["current_step"] = 0;
		_set_guidance_status("preview");
		return guidance_status();
	}
	if (action == "guidance_status") {
		return guidance_status();
	}
	const String status = workflow.get("status", "");
	if (workflow.is_empty() || status == "cancelled") {
		return outcome(false, "no_active_guidance");
	}
	if (action == "guidance_cancel") {
		cancel_guidance();
	} else if (action == "guidance_start") {
		if (status != "preview") {
			return outcome(false, "guidance_not_preview");
		}
		workflow["restored"] = false;
		_activate_step(true);
	} else if (action == "guidance_next") {
		if (status != "waiting_user") {
			return outcome(false, "guidance_not_running");
		}
		_advance("manual_advance");
	} else if (action == "guidance_previous") {
		workflow["current_step"] = MAX(0, int(workflow.get("current_step", 0)) - 1);
		_activate_step(false);
	} else if (action == "guidance_relocate") {
		if (status == "preview" || status == "completed") {
			return outcome(false, "guidance_not_running");
		}
		const Variant baseline = workflow.get("baseline", Variant());
		_activate_step(false);
		workflow["baseline"] = baseline;
	} else if (action == "guidance_execute") {
		if (status != "waiting_user") {
			return outcome(false, "guidance_not_running");
		}
		const Array steps = workflow["steps"];
		if (p_confirmed && (p_args.get("guidance_revision", Variant()).get_type() != Variant::INT || uint64_t(p_args["guidance_revision"]) != guidance_revision)) {
			return outcome(false, "guidance_changed_since_confirmation");
		}
		const Dictionary step = steps[int(workflow["current_step"])];
		if (!step.has("execute")) {
			return outcome(false, "no_executable_step_action");
		}
		Dictionary args = Dictionary(step["execute"]).duplicate(true);
		if (p_args.has("expected_old_value")) {
			args["expected_old_value"] = p_args["expected_old_value"];
		}
		Dictionary result = execute(args, true, false, p_confirmed);
		if (bool(result.get("confirmation_required", false))) {
			result["guidance_revision"] = guidance_revision;
		}
		return result;
	} else {
		return outcome(false, "unknown_guidance_action");
	}
	return guidance_status();
}

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
	if (const Target *entry = targets.getptr(p_id)) {
		Control *control = ObjectDB::get_instance<Control>(entry->control);
		return control && control->is_inside_tree() ? control : nullptr;
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

Dictionary AIChatEditorControl::bound_state(const Dictionary &p_state, const PackedStringArray &p_secrets) {
	Dictionary result = outcome(true);
	result["running"] = p_state.get("running", false);
	result["script_unsaved"] = p_state.get("script_unsaved", Variant());
	Array truncated_fields;
	Array redacted_fields;
	const auto contains_secret = [&p_secrets](const String &p_text) {
		for (const String &secret : p_secrets) {
			if (!secret.is_empty() && p_text.contains(secret)) {
				return true;
			}
		}
		return false;
	};
	// Reserve space for all fixed keys, punctuation and truncation metadata.
	// Charge the actual escaped JSON UTF-8 size, not the String character count.
	int remaining = MAX_STATE_JSON_BYTES - 1024;
	for (const String &field : { "scene", "main_screen", "script", "highlight" }) {
		const Variant value = p_state.get(field, Variant());
		result[field] = Variant();
		if (value.get_type() == Variant::NIL) {
			continue;
		}
		const String text = value;
		if (text.length() > MAX_STATE_STRING_LENGTH) {
			truncated_fields.push_back(field);
			continue;
		}
		if (contains_secret(text)) {
			truncated_fields.push_back(field);
			redacted_fields.push_back(field);
			continue;
		}
		const int bytes = JSON::stringify(text).utf8().length() + 1;
		if (bytes > remaining) {
			truncated_fields.push_back(field);
			continue;
		}
		remaining -= bytes;
		result[field] = text;
	}
	for (const String &field : { "selected_nodes", "unsaved_scenes" }) {
		const Array values = p_state.get(field, Array());
		Array accepted;
		bool truncated = values.size() > MAX_STATE_ITEMS;
		bool redacted = false;
		for (int i = 0; i < MIN(values.size(), MAX_STATE_ITEMS); i++) {
			const String text = values[i];
			if (text.length() > MAX_STATE_STRING_LENGTH) {
				truncated = true;
				continue;
			}
			if (contains_secret(text)) {
				truncated = true;
				redacted = true;
				continue;
			}
			const int bytes = JSON::stringify(text).utf8().length() + 1;
			if (bytes > remaining) {
				truncated = true;
				continue;
			}
			remaining -= bytes;
			accepted.push_back(text);
		}
		result[field] = accepted;
		if (truncated) {
			truncated_fields.push_back(field);
		}
		if (redacted) {
			redacted_fields.push_back(field);
		}
	}
	// Omit whole paths rather than returning prefixes that could identify another node.
	result["truncated"] = !truncated_fields.is_empty();
	result["truncated_fields"] = truncated_fields;
	result["redacted_fields"] = redacted_fields;
	return result;
}

Dictionary AIChatEditorControl::get_state(const PackedStringArray &p_secrets) const {
	EditorInterface *editor = EditorInterface::get_singleton();
	Dictionary result = outcome(true);
	Node *root = editor->get_edited_scene_root();
	result["scene"] = root ? Variant(root->get_scene_file_path()) : Variant();
	Array selection;
	for (Node *node : editor->get_selection()->get_full_selected_node_list()) {
		if (root && (root == node || root->is_ancestor_of(node))) {
			selection.push_back(String(root->get_path_to(node)));
			if (selection.size() > MAX_STATE_ITEMS) {
				break;
			}
		}
	}
	result["selected_nodes"] = selection;
	EditorMainScreen *screen = EditorNode::get_editor_main_screen();
	result["main_screen"] = screen->get_current_tab_control() ? Variant(screen->get_current_tab_control()->get_name()) : Variant();
	ScriptEditorBase *script = editor->get_script_editor()->get_current_editor();
	Ref<Resource> resource = script ? script->get_edited_resource() : Ref<Resource>();
	result["script"] = resource.is_valid() ? Variant(resource->get_path()) : Variant();
	result["running"] = editor->is_playing_scene();
	result["unsaved_scenes"] = editor->get_unsaved_scenes().slice(0, MAX_STATE_ITEMS + 1);
	result["script_unsaved"] = script ? Variant(script->is_unsaved()) : Variant();
	result["highlight"] = target_id.is_empty() ? Variant() : Variant(target_id);
	return bound_state(result, p_secrets);
}

Dictionary AIChatEditorControl::execute(const Dictionary &p_args, bool p_tools_allowed, bool p_consultation, bool p_confirmed) {
	if (!p_tools_allowed || p_consultation) {
		return outcome(false, "permission_denied");
	}
	if (p_args.get("action", Variant()).get_type() != Variant::STRING) {
		return outcome(false, "invalid_action");
	}
	const String action = p_args["action"];
	if (action == "find_targets" || action == "describe_target" || action == "start_guidance" || action.begins_with("guidance_")) {
		return _guidance_action(p_args, p_confirmed);
	}
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
	} else if (action == "reveal_target") {
		Control *control = resolve_target(target);
		if (!control) {
			return outcome(false, "target_unavailable");
		}
		for (Node *child = control; child->get_parent(); child = child->get_parent()) {
			Node *parent = child->get_parent();
			if (FoldableContainer *foldable = Object::cast_to<FoldableContainer>(parent)) {
				foldable->set_folded(false);
			}
			if (TabContainer *tabs = Object::cast_to<TabContainer>(parent)) {
				Control *tab = Object::cast_to<Control>(child);
				const int index = tab ? tabs->get_tab_idx_from_control(tab) : -1;
				if (index >= 0) {
					tabs->set_current_tab(index);
				}
			}
			if (ScrollContainer *scroll = Object::cast_to<ScrollContainer>(parent)) {
				scroll->call_deferred("ensure_control_visible", control);
			}
		}
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
			for (const String &key : { String("action"), String("target"), String("hint"), String("line"), String("column"), String("value"), String("query"), String("title"), String("limit"), String("steps") }) {
				Dictionary schema;
				if (key == "steps") {
					schema["type"] = "array";
					Dictionary step;
					step["type"] = "object";
					schema["items"] = step;
					schema["maxItems"] = MAX_WORKFLOW_STEPS;
				} else if (key != "value") {
					schema["type"] = key == "line" || key == "column" || key == "limit" ? "integer" : "string";
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
		function["description"] = name == "get_editor_state" ? "Read bounded editor state without changing it." : "Semantic editor action. Actions: project_settings, editor_settings, main_screen, open_scene, open_script (1-based line/column), select_node, set_project_setting (value), clear_project_setting, reveal_target (expand ancestors, select tabs, scroll), highlight (optional hint), clear_highlight; find_targets(query,limit), describe_target(target); start_guidance(title,steps) creates a preview, then guidance_start, guidance_next, guidance_previous, guidance_relocate, guidance_execute, guidance_cancel, guidance_status. Steps: target, message, optional non-writing prepare action, optional execute action, observe object with type manual/control_pressed/target_visible/main_screen(value)/selected_node(path)/project_setting(setting,value). Core IDs: scene_tree, inspector, filesystem, main_screen_tabs, project_settings, editor_settings; discover plugin IDs first. Writes including guidance_execute require host confirmation. Never claim completion on failure.";
		function["parameters"] = parameters;
		tool["type"] = "function";
		tool["function"] = function;
		tools.push_back(tool);
	}
	return tools;
}

AIChatEditorControl::AIChatEditorControl() {
	singleton = this;
	set_name("AIEditorHighlight");
	set_mouse_filter(MOUSE_FILTER_IGNORE);
	set_focus_mode(FOCUS_NONE);
	set_z_index(4095);
	clear_highlight();
	_restore_guidance();
}

AIChatEditorControl::~AIChatEditorControl() {
	_disconnect_observer();
	if (Timer *timer = ObjectDB::get_instance<Timer>(guidance_timer)) {
		memdelete(timer);
	}
	if (singleton == this) {
		singleton = nullptr;
	}
}
