/**************************************************************************/
/*  unified_settings_editor_plugin.cpp                                    */
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

#include "unified_settings_editor_plugin.h"

#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/editor_dock.h"
#include "editor/docks/editor_dock_manager.h"
#include "editor/editor_node.h"
#include "editor/themes/editor_scale.h"
#include "scene/gui/box_container.h"
#include "scene/gui/label.h"
#include "scene/gui/margin_container.h"
#include "scene/gui/scroll_container.h"
#include "scene/gui/tab_container.h"

static VBoxContainer *settings_category(TabContainer *p_tabs, const String &p_title, const String &p_name) {
	ScrollContainer *scroll = memnew(ScrollContainer);
	scroll->set_name(p_name);
	scroll->set_horizontal_scroll_mode(ScrollContainer::SCROLL_MODE_DISABLED);
	scroll->set_follow_focus(true);
	p_tabs->add_child(scroll);
	p_tabs->set_tab_title(p_tabs->get_tab_count() - 1, p_title);
	MarginContainer *margin = memnew(MarginContainer);
	margin->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	for (const StringName &side : { SNAME("margin_left"), SNAME("margin_top"), SNAME("margin_right"), SNAME("margin_bottom") }) {
		margin->add_theme_constant_override(side, 18 * EDSCALE);
	}
	scroll->add_child(margin);
	VBoxContainer *body = memnew(VBoxContainer);
	body->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	body->add_theme_constant_override("separation", 18 * EDSCALE);
	margin->add_child(body);
	return body;
}

static EditorDock *settings_source(const String &p_name) {
	return Object::cast_to<EditorDock>(EditorNode::get_singleton()->find_child(p_name, true, false));
}

static VBoxContainer *settings_group(VBoxContainer *p_parent, const String &p_title, const String &p_name) {
	VBoxContainer *group = memnew(VBoxContainer);
	group->set_name(p_name);
	group->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	p_parent->add_child(group);
	Label *heading = memnew(Label);
	heading->set_text(p_title);
	heading->add_theme_font_size_override("font_size", 18 * EDSCALE);
	group->add_child(heading);
	return group;
}

void UnifiedSettingsEditorPlugin::_bind_methods() {
	ClassDB::bind_method(D_METHOD("open_section", "section"), &UnifiedSettingsEditorPlugin::_open_section);
}

UnifiedSettingsEditorPlugin::UnifiedSettingsEditorPlugin() {
	dock = memnew(EditorDock);
	dock_id = dock->get_instance_id();
	dock->set_name("UnifiedSettings");
	dock->set_meta("ai_control_page_only", true);
	dock->set_title(U"设置");
	dock->set_layout_key("UnifiedSettingsMainScreen");
	dock->set_icon_name("Tools");
	// A stable settings viewport keeps runtime controls and leases in one tree.
	dock->set_available_layouts(EditorDock::DOCK_LAYOUT_MAIN_SCREEN);
	dock->set_default_slot(EditorDock::DOCK_SLOT_MAIN_SCREEN);
	dock->set_meta("settings_navigator", callable_mp(this, &UnifiedSettingsEditorPlugin::_open_section));
	dock->set_meta("settings_source_ready", callable_mp(this, &UnifiedSettingsEditorPlugin::_bind_sources));
	categories = memnew(TabContainer);
	categories->set_name("UnifiedSettingsCategories");
	categories->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	dock->add_child(categories);
	VBoxContainer *ai = settings_category(categories, "AI", "AISettingsPage");
	chat_ai = settings_group(ai, U"对话与 Agent", "ChatAISettingsSlot");
	art_ai = settings_group(ai, U"图像与 Mesh 生成", "ArtAISettingsSlot");
	catalog_ai = settings_group(ai, U"个人模型库", "ModelCatalogSettingsSlot");
	VBoxContainer *environment = settings_category(categories, U"环境", "EnvironmentSettingsPage");
	chat_environment = settings_group(environment, U"聊天、工作流与编译环境", "ChatEnvironmentSettingsSlot");
	art_environment = settings_group(environment, U"美术工具与本机模型运行库", "ArtEnvironmentSettingsSlot");
	dock->connect(SceneStringName(visibility_changed), callable_mp(this, &UnifiedSettingsEditorPlugin::_visibility_changed));
	dock->connect(SceneStringName(tree_exiting), callable_mp(this, &UnifiedSettingsEditorPlugin::_dock_exiting));
	dock->connect(SceneStringName(tree_entered), callable_mp(this, &UnifiedSettingsEditorPlugin::_bind_sources), CONNECT_DEFERRED);
	EditorDockManager::get_singleton()->add_dock(dock);
	callable_mp(this, &UnifiedSettingsEditorPlugin::_bind_sources).call_deferred();
}

void UnifiedSettingsEditorPlugin::_watch_source(Node *p_source) {
	const ObjectID id = p_source->get_instance_id();
	if (watched_sources.has(id)) {
		return;
	}
	watched_sources.insert(id);
	p_source->connect(SceneStringName(tree_exiting), callable_mp(this, &UnifiedSettingsEditorPlugin::_source_exiting).bind(uint64_t(id)));
	p_source->connect(SceneStringName(tree_entered), callable_mp(this, &UnifiedSettingsEditorPlugin::_bind_sources), CONNECT_DEFERRED);
	if (p_source->has_signal("settings_requested")) {
		p_source->connect("settings_requested", callable_mp(this, &UnifiedSettingsEditorPlugin::_open_section));
	}
}

void UnifiedSettingsEditorPlugin::_borrow(Control *p_control, VBoxContainer *p_target, Node *p_source) {
	if (!p_control || !p_source || !p_control->get_parent()) {
		return;
	}
	_watch_source(p_source);
	if (p_control->get_parent() != p_target) {
		attachments.push_back({ p_source->get_instance_id(), p_control->get_instance_id(), p_control->get_parent()->get_instance_id() });
		p_control->reparent(p_target, false);
	}
	p_control->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	p_control->show();
}

void UnifiedSettingsEditorPlugin::_bind_sources() {
	if (binding || shutting_down || ObjectDB::get_instance(dock_id) != dock || !dock->is_inside_tree() || !EditorDockManager::get_singleton()) {
		return;
	}
	binding = true;
	AIChatDock *chat = Object::cast_to<AIChatDock>(settings_source("AI Chat"));
	if (chat) {
		_borrow(chat->get_ai_settings_control(), chat_ai, chat);
		_borrow(chat->get_environment_settings_control(), chat_environment, chat);
	}
	if (EditorDock *art = settings_source("AINative")) {
		Node *workbench = art->find_child("AINativeWorkbench", true, false);
		if (!workbench && dock->is_visible_in_tree() && art->has_meta("settings_initializer")) {
			Callable initialize = art->get_meta("settings_initializer");
			if (initialize.is_valid()) {
				initialize.call();
				workbench = art->find_child("AINativeWorkbench", true, false);
			}
		}
		if (workbench && workbench->has_method("get_settings_sections")) {
			Dictionary sections = workbench->call("get_settings_sections");
			_borrow(Object::cast_to<Control>(sections.get("ai", Variant())), art_ai, workbench);
			_borrow(Object::cast_to<Control>(sections.get("environment", Variant())), art_environment, workbench);
		}
	}
	if (EditorDock *planner = settings_source("Daqian")) {
		Node *workspace = planner->find_child("DaqianWorkspace", true, false);
		if (chat && workspace && workspace->has_method("prepare_environment_change")) {
			chat->set_environment_changing_handler(Callable(workspace, "prepare_environment_change"));
		}
		if (workspace && workspace->has_method("get_model_settings_control")) {
			_borrow(Object::cast_to<Control>(workspace->call("get_model_settings_control")), catalog_ai, workspace);
		}
	}
	binding = false;
}

void UnifiedSettingsEditorPlugin::_restore_source(ObjectID p_source) {
	for (int i = attachments.size() - 1; i >= 0; i--) {
		const Attachment &entry = attachments[i];
		if (entry.source != p_source) {
			continue;
		}
		Control *control = ObjectDB::get_instance<Control>(entry.control);
		Node *parent = ObjectDB::get_instance<Node>(entry.original_parent);
		if (control && parent) {
			if (control->get_parent() != parent) {
				control->reparent(parent, false);
			}
			control->hide();
		}
		attachments.remove_at(i);
	}
}

void UnifiedSettingsEditorPlugin::_source_exiting(uint64_t p_id) {
	_restore_source(ObjectID(p_id));
}

void UnifiedSettingsEditorPlugin::_restore_all() {
	while (!attachments.is_empty()) {
		_restore_source(attachments[attachments.size() - 1].source);
	}
}

void UnifiedSettingsEditorPlugin::_visibility_changed() {
	if (ObjectDB::get_instance(dock_id) == dock && dock->is_visible_in_tree()) {
		_bind_sources();
	}
}

void UnifiedSettingsEditorPlugin::_dock_exiting() {
	_restore_all();
}

void UnifiedSettingsEditorPlugin::_open_section(const String &p_section) {
	if (shutting_down || ObjectDB::get_instance(dock_id) != dock || !dock->is_inside_tree()) {
		return;
	}
	categories->set_current_tab(p_section == "environment" ? 1 : 0);
	EditorDockManager::get_singleton()->force_focus_dock(dock);
	_bind_sources();
}

void UnifiedSettingsEditorPlugin::_notification(int p_what) {
	if (p_what == NOTIFICATION_EXIT_TREE || p_what == NOTIFICATION_PREDELETE) {
		shutting_down = true;
		_restore_all();
	}
}

UnifiedSettingsEditorPlugin::~UnifiedSettingsEditorPlugin() {
	_restore_all();
}
