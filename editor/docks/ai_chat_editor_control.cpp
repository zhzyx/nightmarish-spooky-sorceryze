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
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/docks/ai_chat_editor_registry.h"
#include "editor/docks/ai_chat_editor_scene_actions.h"
#include "editor/docks/ai_chat_editor_settings_actions.h"
#include "editor/docks/ai_chat_tools.h"
#include "editor/docks/editor_dock.h"
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
#include "scene/main/scene_tree.h"
#include "scene/main/timer.h"
#include "scene/main/window.h"
#include "scene/resources/packed_scene.h"

#ifdef UNIX_ENABLED
#include <signal.h>

#include <cerrno>
#endif

namespace {
const int MAX_WORKFLOW_BYTES = 16384;
const int MAX_WORKFLOW_STEPS = 32;

String routes_path() {
	return ProjectSettings::get_singleton()->globalize_path("res://.godot/editor/ai_control_receipts.json");
}

bool receipt_owner_may_be_alive(int64_t p_pid) {
#ifdef UNIX_ENABLED
	if (p_pid <= 0 || p_pid > INT32_MAX) {
		return true;
	}
	// OS::is_process_running can be child-only on Unix. Signal zero probes
	// unrelated editor instances without sending a signal; unknown stays held.
	if (::kill(static_cast<pid_t>(p_pid), 0) == 0) {
		return true;
	}
	return errno != ESRCH;
#else
	// Without an authoritative non-child liveness probe, preserve the lock.
	return true;
#endif
}

uint64_t route_clock() {
	return uint64_t(Time::get_singleton()->get_unix_time_from_system() * 1000);
}

String workflow_path() {
	return ProjectSettings::get_singleton()->globalize_path("res://.godot/editor/ai_chat_guidance.json");
}

EditorDock *main_screen_dock(const String &p_name) {
	EditorMainScreen *screen = EditorNode::get_editor_main_screen();
	EditorDock *found = nullptr;
	for (int i = 0; i < screen->get_tab_count(); i++) {
		EditorDock *dock = screen->get_dock(i);
		if (dock && (dock->get_name() == p_name || dock->get_display_title() == p_name || dock->get_effective_layout_key() == p_name)) {
			if (found && found != dock) {
				return nullptr;
			}
			found = dock;
		}
	}
	return found;
}

bool preparation_action(const String &p_action) {
	return p_action == "project_settings" || p_action == "editor_settings" || p_action == "main_screen" || p_action == "open_scene" || p_action == "open_script" || p_action == "select_node" || p_action == "reveal_target" || p_action == "open_target" || p_action == "focus";
}

bool declarative_action(const Variant &p_value, bool p_writing) {
	if (p_value.get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary args = p_value;
	for (const Variant &key : args.keys()) {
		if (key != "action" && key != "target" && key != "line" && key != "column" && key != "value" && key != "start" && key != "end" && key != "index" && key != "type" && key != "name" && key != "parent" && key != "property" && key != "nodes" && key != "value_type") {
			return false;
		}
	}
	if (args.get("action", Variant()).get_type() != Variant::STRING || args.get("target", Variant()).get_type() != Variant::STRING) {
		return false;
	}
	const String action = args.get("action", "");
	return preparation_action(action) || (p_writing && (action == "set_project_setting" || action == "clear_project_setting" || action == "open_resource" || AIChatEditorRegistry::supported(action) || AIChatEditorSceneActions::supports(action) || AIChatEditorSettingsActions::supports(action)));
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
	ClassDB::bind_method(D_METHOD("find_targets_page", "query", "limit", "offset"), &AIChatEditorControl::find_targets_page, DEFVAL(20), DEFVAL(0));
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
	if (p_id.begins_with("editor.")) {
		return registry->describe(p_id);
	}
	const bool core = target_ids().has(p_id);
	const Target *entry = targets.getptr(p_id);
	const String screen = entry ? entry->screen : p_id == "project_settings" || p_id == "editor_settings" ? p_id
																										  : String("editor");
	Dictionary result = outcome(core || entry, core || entry ? String() : String("unknown_target"));
	Control *control = core || entry ? resolve_target(p_id) : nullptr;
	if (control && control->is_inside_tree()) {
		// Explicit aliases share the same live-state protection and byte budgets
		// as discovered targets; registering an alias does not grant disclosure.
		result = AIChatEditorRegistry::describe_node(control, p_id, screen);
	}
	result["id"] = p_id;
	result["display_name"] = entry ? entry->name : p_id.replace("_", " ").capitalize();
	result["owner_screen"] = screen;
	result["automatic"] = false;
	if (!result.has("available")) {
		result["available"] = false;
		result["visible"] = false;
		result["actions"] = Array();
		if (result.has("error")) {
			result["unavailable_reason"] = result["error"];
		}
	}
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
	if (result.size() < CLAMP(p_limit, 1, 20)) {
		result.append_array(registry->find(p_query, CLAMP(p_limit, 1, 20) - result.size()));
	}
	return result;
}

Dictionary AIChatEditorControl::find_targets_page(const String &p_query, int p_limit, int p_offset) const {
	if (p_limit < 1 || p_limit > 20 || p_offset < 0 || p_offset > 8326 || p_query.length() > 128) {
		return outcome(false, "invalid_target_page");
	}
	Array ids = target_ids();
	for (const KeyValue<String, Target> &entry : targets) {
		ids.push_back(entry.key);
	}
	ids.sort();
	Array core;
	const String query = p_query.strip_edges().to_lower();
	const bool exact = ids.has(p_query);
	for (const Variant &id : ids) {
		Dictionary description = describe_target(id);
		if (exact ? id == Variant(p_query) : query.is_empty() || String(id).contains(query) || String(description["display_name"]).to_lower().contains(query)) {
			core.push_back(description);
		}
	}
	Dictionary automatic = exact ? Dictionary() : registry->find_page(p_query, p_limit, MAX(0, p_offset - core.size()));
	const int total = core.size() + int(automatic.get("total", 0));
	Array page;
	for (int i = p_offset; i < core.size() && page.size() < p_limit; i++) {
		page.push_back(core[i]);
	}
	const Array found = automatic.get("targets", Array());
	int page_bytes = JSON::stringify(page).utf8().length();
	bool byte_truncated = automatic.get("byte_truncated", false);
	for (int i = 0; i < found.size() && page.size() < p_limit; i++) {
		const int bytes = JSON::stringify(found[i]).utf8().length();
		if (!page.is_empty() && page_bytes + bytes > 30 * 1024) {
			byte_truncated = true;
			break;
		}
		page.push_back(found[i]);
		page_bytes += bytes;
	}
	Dictionary result = outcome(true);
	result["targets"] = page;
	result["total"] = total;
	result["offset"] = p_offset;
	result["next_offset"] = p_offset + page.size() < total ? Variant(p_offset + page.size()) : Variant();
	result["truncated"] = bool(automatic.get("truncated", false)) || byte_truncated;
	result["has_more"] = p_offset + page.size() < total;
	result["byte_truncated"] = byte_truncated;
	result["scan_truncated"] = automatic.get("scan_truncated", false);
	result["total_is_lower_bound"] = automatic.get("total_is_lower_bound", false);
	result["registry"] = registry->status();
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
			if (key != "type" && key != "setting" && key != "path" && key != "value" && key != "request_id" && key != "source") {
				return false;
			}
		}
		const String type = observe.get("type", "manual");
		if (type == "project_setting" && !AIChatEditorSettingsActions::allowed_project_key(observe.get("setting", ""))) {
			return false;
		}
		if (type != "manual" && type != "control_pressed" && type != "target_visible" && type != "main_screen" && type != "selected_node" && type != "project_setting" && type != "field_value" && type != "window_closed" && type != "request_completed") {
			return false;
		}
		if (type == "request_completed" && (observe.get("request_id", Variant()).get_type() != Variant::STRING || String(observe["request_id"]).is_empty() || String(observe["request_id"]).length() > 96 || observe.get("source", Variant()).get_type() != Variant::STRING || String(observe["source"]).is_empty() || String(observe["source"]).length() > 96)) {
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
	if (type == "field_value" || type == "window_closed") {
		Control *target = resolve_target(step["target"]);
		const Dictionary description = describe_target(step["target"]);
		if (!target || (type == "field_value" && (!description.has("value") || bool(description.get("value_omitted", false)))) || (type == "window_closed" && (!target->get_window() || target->get_window() == target->get_tree()->get_root() || !target->get_window()->is_visible()))) {
			_set_guidance_status("failed", "observer_target_unavailable");
			return;
		}
		workflow["observer_instance"] = int64_t(target->get_instance_id());
		workflow["baseline"] = type == "field_value" ? description["value"] : Variant(int64_t(target->get_window()->get_instance_id()));
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
	} else if (p_observation == "control_pressed" || p_observation == "target_visible" || p_observation == "field_value" || p_observation == "window_closed") {
		observation["target"] = step.get("target", "");
	}
	if (p_observation == "request_completed") {
		observation["request_id"] = observe.get("request_id", "");
		observation["source"] = observe.get("source", "");
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
	const Dictionary observe = step.get("observe", Dictionary());
	const String type = observe.get("type", "manual");
	if (type == "request_completed") {
		const Dictionary request = route_status(observe["request_id"], observe["source"]);
		if (bool(request.get("ok", false)) && request.get("routing_status", "") == "completed") {
			_advance(type);
		}
		return;
	}
	if (type == "window_closed") {
		if (!target || int64_t(target->get_instance_id()) != int64_t(workflow.get("observer_instance", 0)) || !target->get_window() || int64_t(target->get_window()->get_instance_id()) != int64_t(workflow.get("baseline", 0))) {
			_set_guidance_status("failed", "observer_target_changed");
		} else if (!target->get_window()->is_visible()) {
			_advance(type);
		}
		return;
	}
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
	} else if (type == "field_value") {
		const Dictionary description = describe_target(id);
		if (int64_t(target->get_instance_id()) != int64_t(workflow.get("observer_instance", 0)) || !description.has("value") || bool(description.get("value_omitted", false))) {
			_set_guidance_status("failed", "observer_target_changed");
			return;
		}
		const Variant value = description["value"];
		complete = value != baseline && (!observe.has("value") || value == observe["value"]);
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
		const Variant limit = p_args.get("limit", 8), offset = p_args.get("offset", 0), query = p_args.get("query", "");
		if (!bounded_integer(limit, 1, 20) || !bounded_integer(offset, 0, 8326) || query.get_type() != Variant::STRING) {
			return outcome(false, "invalid_target_page");
		}
		return find_targets_page(query, int(limit), int(offset));
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
		if (p_args.has("expected_target_instance")) {
			args["expected_target_instance"] = p_args["expected_target_instance"];
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
	return p_name == "get_editor_state" || p_name == "editor_action" || p_name == "route_engine_message";
}

bool AIChatEditorControl::_acquire_routes_lock() {
	if (!EditorNode::get_singleton()) {
		return true;
	}
	const String path = routes_path(), lock = path + ".lock";
	Ref<DirAccess> directory = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
	String parent = ProjectSettings::get_singleton()->get_resource_path();
	for (const String &part : { String(".godot"), String("editor") }) {
		parent = parent.path_join(part);
		if (directory->is_link(parent)) {
			return false;
		}
	}
	if (directory->is_link(path) || directory->is_link(path + ".pending") || directory->is_link(lock) || DirAccess::make_dir_recursive_absolute(parent) != OK) {
		return false;
	}
	// Serialize observation + stale-lock replacement. Never reclaim this short
	// acquisition lock automatically: an interrupted acquisition needs recovery.
	const String arbitration = path + ".acquiring";
	if (directory->is_link(arbitration) || DirAccess::make_dir_absolute(arbitration) != OK) {
		return false;
	}
	struct AcquisitionGuard {
		String path;
		~AcquisitionGuard() { DirAccess::remove_absolute(path); }
	} acquisition_guard{ arbitration };
	if (DirAccess::dir_exists_absolute(lock)) {
		const String previous = FileAccess::get_file_as_string(lock.path_join("owner"));
		if (!previous.is_valid_int() || previous.to_int() <= 0 || receipt_owner_may_be_alive(previous.to_int())) {
			return false;
		}
		// Reclaim only after the recorded OS process has ended, never by elapsed time.
		const String stale = lock + ".stale-" + itos(OS::get_singleton()->get_process_id());
		if (DirAccess::rename_absolute(lock, stale) != OK) {
			return false;
		}
		DirAccess::remove_absolute(stale.path_join("owner"));
		DirAccess::remove_absolute(stale);
	}
	if (DirAccess::make_dir_absolute(lock) != OK) {
		return false;
	}
	Ref<FileAccess> owner = FileAccess::open(lock.path_join("owner"), FileAccess::WRITE_READ);
	if (owner.is_null() || !owner->store_string(itos(OS::get_singleton()->get_process_id())) || owner->get_error() != OK) {
		return false;
	}
	owner->close();
	routes_lock_owned = true;
	return true;
}

bool AIChatEditorControl::_persist_routes() const {
	// Unit-only instances have no editor/project lifecycle and never touch user files.
	if (!EditorNode::get_singleton()) {
		return true;
	}
	Array records;
	for (const KeyValue<String, RoutedRequest> &entry : routed_requests) {
		Dictionary record, summary;
		record["identity"] = entry.key;
		record["fingerprint"] = entry.value.fingerprint;
		record["updated"] = entry.value.updated;
		// Persist outcome metadata, never composer text, prior values or credentials.
		for (const String &field : { "ok", "error", "routing_status", "routed", "route", "request_id", "source", "idempotency_window_seconds" }) {
			if (entry.value.result.has(field)) {
				summary[field] = entry.value.result[field];
			}
		}
		record["result"] = summary;
		records.push_back(record);
	}
	Dictionary document;
	document["version"] = 1;
	document["records"] = records;
	const String contents = JSON::stringify(document);
	if (records.size() > 256 || contents.utf8().length() > 256 * 1024) {
		return false;
	}
	if (!routes_lock_owned) {
		return false;
	}
	const String path = routes_path(), pending = path + ".pending";
	if (DirAccess::make_dir_recursive_absolute(path.get_base_dir()) != OK) {
		return false;
	}
	Ref<FileAccess> file = FileAccess::open(pending, FileAccess::WRITE);
	if (file.is_null()) {
		return false;
	}
#ifndef WINDOWS_ENABLED
	if (FileAccess::set_unix_permissions(file->get_path_absolute(), FileAccess::UNIX_READ_OWNER | FileAccess::UNIX_WRITE_OWNER) != OK) {
		file->close();
		return false;
	}
#endif
	const bool stored = file->store_string(contents) && file->get_error() == OK;
	file->close();
	if (!stored || FileAccess::get_sha256(pending) != contents.sha256_text()) {
		return false;
	}
	return DirAccess::rename_absolute(pending, path) == OK;
}

void AIChatEditorControl::_restore_routes() {
	if (!EditorNode::get_singleton() || !FileAccess::exists(routes_path())) {
		return;
	}
	Ref<FileAccess> file = FileAccess::open(routes_path(), FileAccess::READ);
	if (file.is_null() || file->get_length() > 256 * 1024) {
		routes_store_healthy = false;
		routes_store_error = "record_file_unreadable_or_large";
		return;
	}
	const Variant parsed = JSON::parse_string(file->get_as_text());
	if (parsed.get_type() != Variant::DICTIONARY || !bounded_integer(Dictionary(parsed).get("version", Variant()), 1, 1) || Dictionary(parsed).get("records", Variant()).get_type() != Variant::ARRAY || Array(Dictionary(parsed)["records"]).size() > 256) {
		routes_store_healthy = false;
		routes_store_error = "invalid_record_document";
		return;
	}
	const Array records = Dictionary(parsed)["records"];
	HashMap<String, RoutedRequest> restored;
	for (const Variant &value : records) {
		if (value.get_type() != Variant::DICTIONARY) {
			routes_store_healthy = false;
			routes_store_error = "invalid_record_entry";
			return;
		}
		const Dictionary record = value;
		const String identity = record.get("identity", ""), fingerprint = record.get("fingerprint", "");
		if (identity.is_empty() || identity.length() > 193 || restored.has(identity) || fingerprint.length() != 64 || !fingerprint.is_valid_hex_number(false) || !bounded_integer(record.get("updated", Variant()), 0, 9007199254740991LL) || record.get("result", Variant()).get_type() != Variant::DICTIONARY) {
			routes_store_healthy = false;
			routes_store_error = "invalid_record_fields";
			return;
		}
		Dictionary result = Dictionary(record["result"]).duplicate(true);
		const String id = result.get("request_id", ""), source = result.get("source", "");
		if (id.is_empty() || source.is_empty() || identity != source + ":" + id) {
			routes_store_healthy = false;
			routes_store_error = "invalid_record_identity";
			return;
		}
		const uint64_t updated = int64_t(record["updated"]);
		if (route_clock() > updated && route_clock() - updated > 900000) {
			continue;
		}
		const String status = result.get("routing_status", "");
		if (status == "awaiting_confirmation") {
			result["ok"] = false;
			result["routing_status"] = "cancelled";
			result["error"] = "interrupted_by_editor_restart";
		} else if (status == "execution_interrupted") {
			// The effect may have happened before the final receipt reached disk.
			// Preserve uncertainty and never replay or claim it was cancelled.
			result["ok"] = false;
			result["routing_status"] = "execution_unknown";
			result["error"] = "execution_result_unknown_after_restart";
		}
		result["receipt_restored"] = true;
		result["result_details_omitted"] = true;
		restored[identity] = { fingerprint, result, updated };
	}
	routed_requests = restored;
	routes_store_healthy = _persist_routes();
}

void AIChatEditorControl::_publish_route_event(const Dictionary &p_result) {
	Dictionary event;
	event["cursor"] = int64_t(++route_event_sequence);
	for (const String &field : { "ok", "error", "routing_status", "request_id", "source" }) {
		if (p_result.has(field)) {
			event[field] = p_result[field];
		}
	}
	route_event_log.push_back(event);
	if (route_event_log.size() > 256) {
		route_event_log.remove_at(0);
	}
}

Dictionary AIChatEditorControl::route_events(int64_t p_after, int p_limit) const {
	if (p_after < 0 || uint64_t(p_after) > route_event_sequence || p_limit < 1 || p_limit > 100) {
		return outcome(false, "invalid_event_cursor");
	}
	Dictionary result = outcome(true);
	Array events;
	int64_t next = p_after;
	for (const Variant &value : route_event_log) {
		const Dictionary event = value;
		if (int64_t(event["cursor"]) > p_after && events.size() < p_limit) {
			events.push_back(event);
			next = event["cursor"];
		}
	}
	result["events"] = events;
	result["next_cursor"] = next;
	result["latest_cursor"] = int64_t(route_event_sequence);
	result["gap"] = !route_event_log.is_empty() && p_after < int64_t(Dictionary(route_event_log[0])["cursor"]) - 1;
	result["has_more"] = uint64_t(next) < route_event_sequence;
	result["transport"] = "bounded_poll";
	return result;
}

Dictionary AIChatEditorControl::route_status(const String &p_request_id, const String &p_source) const {
	const RoutedRequest *request = routed_requests.getptr(p_source + ":" + p_request_id);
	if (request) {
		return request->result.duplicate(true);
	}
	Dictionary result = outcome(false, routes_store_healthy ? "unknown_request" : "receipt_store_unavailable");
	if (!routes_store_healthy) {
		result["reason"] = routes_store_error;
	}
	return result;
}

Dictionary AIChatEditorControl::cancel_route(const Dictionary &p_message, const String &p_reason) {
	const String key = String(p_message.get("source", "internal-ai")) + ":" + String(p_message.get("request_id", ""));
	Dictionary result = outcome(false, p_reason);
	result["routing_status"] = "cancelled";
	result["request_id"] = p_message.get("request_id", "");
	result["source"] = p_message.get("source", "internal-ai");
	if (RoutedRequest *request = routed_requests.getptr(key)) {
		request->result = result;
		request->updated = route_clock();
		_publish_route_event(result);
		routes_store_healthy = _persist_routes();
	}
	return result;
}

Dictionary AIChatEditorControl::route_message(const Dictionary &p_message, bool p_tools_allowed, bool p_consultation, bool p_confirmed, bool p_host_context) {
	if (!p_tools_allowed || p_consultation) {
		return outcome(false, "permission_denied");
	}
	if (JSON::stringify(p_message).utf8().length() > 32768) {
		return outcome(false, "message_too_large");
	}
	if (p_message.get("intent", Variant()).get_type() != Variant::STRING || p_message["intent"] != "engine_operation") {
		Dictionary result = outcome(true);
		result["routed"] = false;
		result["routing_status"] = "not_applicable";
		return result;
	}
	const Variant request_id = p_message.get("request_id", Variant());
	const Variant source = p_message.get("source", "internal-ai");
	if (request_id.get_type() != Variant::STRING || source.get_type() != Variant::STRING || String(request_id).is_empty() || String(request_id).length() > 96 || String(source).is_empty() || String(source).length() > 96) {
		return outcome(false, "invalid_route_identity");
	}
	for (const String &identity : { String(request_id), String(source) }) {
		for (int i = 0; i < identity.length(); i++) {
			const char32_t c = identity[i];
			if (!(c == '-' || c == '_' || c == '.' || (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'))) {
				return outcome(false, "invalid_route_identity");
			}
		}
	}
	Dictionary normalized;
	for (const String &field : { "intent", "request_id", "source", "request", "operation" }) {
		if (p_message.has(field)) {
			normalized[field] = p_message[field];
		}
	}
	normalized["source"] = source;
	const String key = String(source) + ":" + String(request_id);
	const String fingerprint = JSON::stringify(normalized).sha256_text();
	const uint64_t now = route_clock();
	if (!routes_store_healthy) {
		return outcome(false, "receipt_store_unavailable");
	}
	Vector<String> expired;
	for (const KeyValue<String, RoutedRequest> &entry : routed_requests) {
		if (now > entry.value.updated && now - entry.value.updated > 15 * 60 * 1000 && entry.value.result.get("routing_status", "") != "awaiting_confirmation") {
			expired.push_back(entry.key);
		}
	}
	for (const String &id : expired) {
		routed_requests.erase(id);
	}
	if (const RoutedRequest *previous = routed_requests.getptr(key)) {
		if (previous->fingerprint != fingerprint) {
			return outcome(false, "request_id_conflict");
		}
		if (!p_confirmed || previous->result.get("routing_status", "") != "awaiting_confirmation") {
			Dictionary result = previous->result.duplicate(true);
			result["idempotent"] = true;
			return result;
		}
	} else if (p_confirmed || routed_requests.size() >= 256) {
		return outcome(false, p_confirmed ? "unknown_confirmation" : "route_capacity_exceeded");
	}
	if ((!p_message.has("operation") && (p_message.get("request", Variant()).get_type() != Variant::STRING || String(p_message["request"]).length() > 8192)) || (p_message.has("operation") && p_message["operation"].get_type() != Variant::DICTIONARY)) {
		return outcome(false, "invalid_engine_operation");
	}
	// Durable uncertainty precedes every effect. A crash never replays an approval.
	Dictionary interrupted = outcome(false, "execution_result_unknown");
	interrupted["routing_status"] = "execution_interrupted";
	interrupted["request_id"] = request_id;
	interrupted["source"] = source;
	routed_requests[key] = { fingerprint, interrupted, now };
	if (!_persist_routes()) {
		routes_store_healthy = false;
		return outcome(false, "receipt_store_unavailable");
	}
	Dictionary result;
	if (!p_message.has("operation")) {
		if (p_message.get("request", Variant()).get_type() != Variant::STRING || String(p_message["request"]).length() > 8192) {
			return outcome(false, "invalid_engine_request");
		}
		result = outcome(true);
		result["routing_status"] = "planning_required";
		result["targets"] = find_targets(p_message.get("request", ""), 8);
		result["next"] = "Discover targets with editor_action/find_targets, then route_engine_message with a NEW request_id and one declarative operation. Use start_guidance for multi-step help. Do not claim an operation happened yet.";
	} else {
		if (p_message["operation"].get_type() != Variant::DICTIONARY) {
			return outcome(false, "invalid_engine_operation");
		}
		Dictionary operation = Dictionary(p_message["operation"]).duplicate(true);
		for (const String &field : { "expected_old_value", "expected_target_instance", "guidance_revision" }) {
			operation.erase(field);
			if (p_confirmed && p_message.has(field)) {
				operation[field] = p_message[field];
			}
		}
		result = execute(operation, p_tools_allowed, p_consultation, p_confirmed, p_host_context);
		result["routing_status"] = bool(result.get("confirmation_required", false)) ? "awaiting_confirmation" : bool(result.get("ok", false)) ? "completed"
																																			  : "failed";
	}
	result["routed"] = true;
	result["route"] = "engine_control";
	result["request_id"] = request_id;
	result["source"] = source;
	result["idempotency_window_seconds"] = 900;
	routed_requests[key] = { fingerprint, result.duplicate(true), now };
	_publish_route_event(result);
	if (!_persist_routes()) {
		routes_store_healthy = false;
		result["receipt_persistence_failed"] = true;
		routes_store_error = "receipt_write_failed";
		routed_requests[key].result["receipt_persistence_failed"] = true;
	}

	return result;
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
	if (p_id.begins_with("editor.")) {
		return registry->resolve(p_id);
	}
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

Dictionary AIChatEditorControl::execute(const Dictionary &p_args, bool p_tools_allowed, bool p_consultation, bool p_confirmed, bool p_host_context) {
	if (!p_tools_allowed || p_consultation) {
		return outcome(false, "permission_denied");
	}
	if (p_args.get("action", Variant()).get_type() != Variant::STRING) {
		return outcome(false, "invalid_action");
	}
	const String action = p_args["action"];
	if (action.begins_with("chat_")) {
		if (!p_host_context || !chat_host_handler.is_valid()) {
			return outcome(false, "host_only_action");
		}
		const Variant result = chat_host_handler.call(p_args, p_confirmed);
		return result.get_type() == Variant::DICTIONARY ? Dictionary(result) : outcome(false, "host_action_unavailable");
	}
	if (action == "find_targets" || action == "describe_target" || action == "start_guidance" || action.begins_with("guidance_")) {
		return _guidance_action(p_args, p_confirmed);
	}
	const Variant target_value = p_args.get("target", "");
	if (target_value.get_type() != Variant::STRING || String(target_value).length() > 1024) {
		return outcome(false, "invalid_target");
	}
	const String target = target_value;
	if (AIChatEditorSceneActions::supports(action)) {
		return AIChatEditorSceneActions::perform(p_args, p_confirmed);
	}
	if (AIChatEditorSettingsActions::supports(action)) {
		return AIChatEditorSettingsActions::perform(p_args, p_confirmed);
	}
	if (AIChatEditorRegistry::supported(action)) {
		return registry->perform(target.begins_with("editor.") ? registry->resolve_node(target) : resolve_target(target), target, p_args, p_confirmed);
	}
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
	if (action == "inspect_ui") {
		const Variant limit = p_args.get("limit", 20), offset = p_args.get("offset", 0);
		if (!bounded_integer(limit, 1, 100) || !bounded_integer(offset, 0, 50000)) {
			return outcome(false, "invalid_ui_page");
		}
		return registry->inspect_tree(int(limit), int(offset));
	}
	if (action == "inspect_scene") {
		const Variant limit = p_args.get("limit", 20), offset = p_args.get("offset", 0);
		if (!bounded_integer(limit, 1, 100) || !bounded_integer(offset, 0, 50000)) {
			return outcome(false, "invalid_scene_page");
		}
		Node *root = editor->get_edited_scene_root();
		Dictionary result = outcome(true);
		Array nodes;
		LocalVector<Node *> stack;
		if (root) {
			stack.push_back(root);
		}
		int visited = 0, consumed = 0, omitted = 0, bytes = 0;
		while (!stack.is_empty() && visited < 50000) {
			Node *node = stack[stack.size() - 1];
			stack.remove_at(stack.size() - 1);
			const int index = visited++;
			if (index >= int(offset) && consumed < int(limit)) {
				Dictionary entry;
				const String path = String(root->get_path_to(node));
				entry["index"] = index;
				entry["path"] = path;
				entry["class"] = node->get_class();
				entry["instance"] = int64_t(node->get_instance_id());
				const int size = JSON::stringify(entry).utf8().length();
				if (path.length() > 1024 || bytes + size > 14 * 1024) {
					omitted++;
				} else {
					nodes.push_back(entry);
					bytes += size;
				}
				consumed++;
			}
			for (int i = node->get_child_count() - 1; i >= 0; i--) {
				stack.push_back(node->get_child(i));
			}
		}
		result["nodes"] = nodes;
		result["offset"] = offset;
		result["total"] = visited;
		result["next_offset"] = int(offset) + consumed < visited ? Variant(int(offset) + consumed) : Variant();
		result["truncated"] = !stack.is_empty() || omitted > 0;
		result["total_is_lower_bound"] = !stack.is_empty();
		result["omitted_items"] = omitted;
		return result;
	}
	if (action == "list_main_screens") {
		Dictionary result = outcome(true);
		Array screens;
		EditorMainScreen *main_screen = EditorNode::get_editor_main_screen();
		for (int i = 0; i < main_screen->get_tab_count(); i++) {
			EditorDock *dock = main_screen->get_dock(i);
			if (!dock) {
				continue;
			}
			Dictionary entry;
			entry["name"] = dock->get_name();
			entry["title"] = dock->get_display_title();
			entry["layout_key"] = dock->get_effective_layout_key();
			entry["selected"] = main_screen->get_current_tab() == i;
			entry["hidden"] = main_screen->is_tab_hidden(i);
			screens.push_back(entry);
		}
		result["main_screens"] = screens;
		return result;
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
		if (target.is_empty() || !main_screen_dock(target)) {
			return outcome(false, "unknown_main_screen");
		}
		main_screen_dock(target)->make_visible();
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
	} else if (action == "open_scene" || action == "open_script" || action == "open_resource") {
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
		if (action == "open_resource") {
			if (!FileAccess::exists(target)) {
				return outcome(false, "resource_load_failed");
			}
			Dictionary state;
			state["path"] = target;
			state["sha256"] = FileAccess::get_sha256(target);
			Dictionary preview = outcome(false);
			preview["old_value"] = state;
			preview["new_value"] = "open_resource";
			preview["target_instance"] = int64_t(editor->get_instance_id());
			if (!p_confirmed) {
				preview["confirmation_required"] = true;
				return preview;
			}
			if (p_args.get("expected_target_instance", Variant()).get_type() != Variant::INT || int64_t(p_args["expected_target_instance"]) != int64_t(editor->get_instance_id()) || !p_args.has("expected_old_value") || p_args["expected_old_value"] != Variant(state)) {
				return outcome(false, "resource_changed_since_confirmation");
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
		} else if (action == "open_resource") {
			if (resource.is_null()) {
				return outcome(false, "resource_load_failed");
			}
			editor->edit_resource(resource);
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
		if (!AIChatEditorSettingsActions::allowed_project_key(target)) {
			return outcome(false, "protected_setting");
		}
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
		visible_target = main_screen_dock(target);
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
			for (const String &key : { String("action"), String("target"), String("hint"), String("line"), String("column"), String("value"), String("query"), String("title"), String("limit"), String("offset"), String("index"), String("start"), String("end"), String("value_type"), String("type"), String("name"), String("parent"), String("property"), String("nodes"), String("steps"), String("receiver"), String("signal"), String("method"), String("resource_path"), String("destination"), String("preset"), String("format"), String("debug") }) {
				Dictionary schema;
				if (key == "nodes") {
					schema["type"] = "array";
					Dictionary item;
					item["type"] = "string";
					schema["items"] = item;
					schema["maxItems"] = 100;
				} else if (key == "steps") {
					schema["type"] = "array";
					Dictionary step;
					step["type"] = "object";
					schema["items"] = step;
					schema["maxItems"] = MAX_WORKFLOW_STEPS;
				} else if (key == "debug") {
					schema["type"] = "boolean";
				} else if (key != "value") {
					schema["type"] = key == "line" || key == "column" || key == "limit" || key == "offset" || key == "index" || key == "start" || key == "end" ? "integer" : "string";
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
		function["description"] = name == "get_editor_state" ? "Read bounded editor state without changing it." : "Semantic editor action. Actions: project_settings, editor_settings, main_screen (discovered dock name), list_main_screens, open_scene, open_resource, open_script (1-based line/column), select_node, set_project_setting (value), clear_project_setting, reveal_target (expand ancestors, select tabs, scroll), highlight (optional hint), clear_highlight; find_targets(query,limit,offset) returns total/next_offset and scan truncation, describe_target(target); start_guidance(title,steps) creates a preview, then guidance_start, guidance_next, guidance_previous, guidance_relocate, guidance_execute, guidance_cancel, guidance_status. Steps: target, message, optional non-writing prepare action, optional execute action, observe object with type manual/control_pressed/target_visible/main_screen(value)/selected_node(path)/project_setting(setting,value)/field_value(value)/window_closed/request_completed(request_id,source). Core IDs: scene_tree, inspector, filesystem, main_screen_tabs, project_settings, editor_settings; discover plugin IDs first. Discover target actions; complex targets expose read_menu_items/activate_menu_item/open_menu_submenu(index), read_curve/curve_preset(value 0..4), curve_add_point(value=[offset,y]), curve_remove_point(index), curve_set_point(index,value=[offset,y]), curve_set_tangents(index,value=[left,right]), curve_set_tangent_modes(index,value=[left_mode,right_mode],0=free/1=linear), read_gradient/gradient_add_point(value=[offset,r,g,b,a])/gradient_set_color(index,value=[r,g,b,a])/gradient_remove_point(index)/gradient_reverse/gradient_set_offset(index,value=offset)/undo_resource_edit/redo_resource_edit, read_graph_nodes/read_graph_connections(limit,offset), read_graph_ports(value={node,direction:input/output},limit,offset), graph_connect/graph_disconnect(value={from,from_port,to,to_port}), graph_move_node(value={node,position:[x,y]}), activate_tree_item/tree_context_menu/activate_item/item_context_menu(index). requested:true and business_completed:false mean only the native business request was delivered; use readback and later reads to verify effects. Scripted and extension resources are refused; resource point edits and Undo/Redo require unchanged instances, resource state and bound history. read_text, read_items(limit,offset), select_text_range(start,end), append_text(value), replace_text_range(start,end,value) use Unicode character offsets, submit_text, undo_text; select_tree_item/expand_tree_item(index), select_item/select_tab(index), set_color(value=[r,g,b,a]), scroll_to(value=[x,y]). inspect_scene/inspect_ui(limit,offset) read bounded scene/UI trees with explicit omission markers. get_project_setting/get_editor_setting(target), create_project_setting(target,value_type,value), update_project_setting(target,value), set_editor_setting/reset_editor_setting(target,value); EditorSettings limited to appearance preferences, no auth or tool policy. Scene actions: scene_create_node(target parent,type,name), scene_delete_node(target subtree), scene_rename_node(target,name), scene_reparent_node(target subtree,parent), scene_select_nodes(nodes), scene_set_property(target,property,value), scene_assign_resource(target,property,resource_path), scene_connect_signal/scene_disconnect_signal(target,signal,receiver,method), scene_import_resource(resource_path), scene_export_resource(target,property,destination), project_export(preset,format project/pack/zip,debug boolean,destination), run_project, run_scene(target resource path), stop_project; run always requires explicit human confirmation and returns only run_requested. Scripted/inherited/instanced scene edits follow native ownership rules; unsafe script or metadata reference scopes are refused. Resource operations accept only bounded native types, and export destinations stay inside the project. Scene writes, import/export and run require explicit native human confirmation. Writes including guidance_execute require host confirmation. Never claim completion on failure.";
		function["parameters"] = parameters;
		tool["type"] = "function";
		tool["function"] = function;
		tools.push_back(tool);
	}
	Dictionary route_properties;
	for (const String &field : { "intent", "request_id", "source", "request", "operation" }) {
		Dictionary schema;
		schema["type"] = field == "operation" ? "object" : "string";
		route_properties[field] = schema;
	}
	Dictionary route_parameters;
	route_parameters["type"] = "object";
	route_parameters["properties"] = route_properties;
	Array route_required;
	route_required.push_back("intent");
	route_required.push_back("request_id");
	route_parameters["required"] = route_required;
	route_parameters["additionalProperties"] = false;
	Dictionary route_function;
	route_function["name"] = "route_engine_message";
	route_function["description"] = "Whenever user intent is to operate this editor, automatically enter this route. Set intent=engine_operation, a unique request_id and source. Discover current targets via editor_action/find_targets or describe_target, then pass one declarative operation using editor_action's schema. New pages and inputs are discovered automatically; open_target, focus, highlight, set_text(value), set_value(value), select_option(index in value) and press depend on actual target capabilities. Use start_guidance for multiple steps. Natural-language request without operation returns planning_required: discover and plan, then submit a NEW request_id. Repeat identical IDs only to recover results; a changed operation needs a new ID. All execution and confirmation remain host-controlled; rejection is final.";
	route_function["parameters"] = route_parameters;
	Dictionary route_tool;
	route_tool["type"] = "function";
	route_tool["function"] = route_function;
	tools.push_back(route_tool);
	return tools;
}

AIChatEditorControl::AIChatEditorControl() {
	singleton = this;
	registry = memnew(AIChatEditorRegistry);
	set_name("AIEditorHighlight");
	set_mouse_filter(MOUSE_FILTER_IGNORE);
	set_focus_mode(FOCUS_NONE);
	set_z_index(4095);
	clear_highlight();
	_restore_guidance();
	routes_store_healthy = _acquire_routes_lock();
	if (!routes_store_healthy) {
		routes_store_error = "receipt_store_locked_or_linked";
	}
	if (routes_store_healthy) {
		_restore_routes();
	}
}

AIChatEditorControl::~AIChatEditorControl() {
	if (routes_lock_owned) {
		const String lock = routes_path() + ".lock";
		if (FileAccess::get_file_as_string(lock.path_join("owner")) == itos(OS::get_singleton()->get_process_id())) {
			DirAccess::remove_absolute(lock.path_join("owner"));
			DirAccess::remove_absolute(lock);
		}
	}
	memdelete(registry);
	_disconnect_observer();
	if (Timer *timer = ObjectDB::get_instance<Timer>(guidance_timer)) {
		memdelete(timer);
	}
	if (singleton == this) {
		singleton = nullptr;
	}
}
