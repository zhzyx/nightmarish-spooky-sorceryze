/**************************************************************************/
/*  editor_main_screen.cpp                                                */
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

#include "editor_main_screen.h"

#include "core/object/callable_mp.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/editor_dock.h"
#include "editor/docks/editor_dock_manager.h"
#include "editor/editor_node.h"
#include "editor/gui/editor_bottom_panel.h"
#include "editor/plugins/editor_plugin.h"
#include "editor/scene/3d/node_3d_editor_plugin.h"
#include "editor/scene/editor_scene_tabs.h"
#include "editor/script/script_editor_plugin.h"
#include "editor/settings/editor_settings.h"
#include "editor/themes/editor_scale.h"
#include "scene/gui/menu_button.h"
#include "scene/gui/split_container.h"

#ifndef DISABLE_DEPRECATED
void LegacyMainScreenContainer::_force_dock_visible(EditorDock *p_dock, CanvasItem *p_child) {
	if (p_dock->is_visible_in_tree()) {
		p_child->show();
	}
}

void LegacyMainScreenContainer::add_child_notify(Node *p_child) {
	EditorMainScreen *ms = EditorNode::get_editor_main_screen();
	if (!ms->adding_plugin || !ms->adding_plugin->has_main_screen()) {
		return;
	}

	EditorDock *dock = memnew(EditorDock);
	dock->set_default_slot(EditorDock::DOCK_SLOT_MAIN_SCREEN);
	dock->set_available_layouts(EditorDock::DOCK_LAYOUT_MAIN_SCREEN);
	dock->set_title(ms->adding_plugin->get_plugin_name());
	dock->set_dock_icon(ms->adding_plugin->get_plugin_icon());
	dock->set_icon_name(ms->adding_plugin->get_plugin_name());
	EditorDockManager::get_singleton()->add_dock(dock);

	ms->adding_plugin->set_meta("_dock", dock);

	CanvasItem *ci_child = Object::cast_to<CanvasItem>(p_child);
	if (ci_child) {
		ci_child->show();
		dock->connect(SceneStringName(visibility_changed), callable_mp(this, &LegacyMainScreenContainer::_force_dock_visible).bind(dock, ci_child));
	}

	callable_mp(p_child, &Node::reparent).call_deferred(dock, false);
}
#endif

void EditorMainScreen::_set_window_fill(bool p_fill) {
	// Distraction-free settings may have changed dock visibility since the last
	// tab switch, including when switching between two full-workspace pages.
	if (p_fill && !window_filling) {
		restore_expanded_bottom_panel = !EditorNode::get_top_split()->is_visible();
	}
	EditorNode::get_bottom_panel()->set_hidden_by_main_screen(p_fill);
	if (!p_fill && window_filling && restore_expanded_bottom_panel) {
		EditorNode::get_bottom_panel()->set_expanded(true);
	}
	window_filling = p_fill;
	EditorNode::get_singleton()->update_workspace_focus_button(p_fill);
	EditorSceneTabs::get_singleton()->set_visible(!p_fill);
	EditorDockManager::get_singleton()->set_docks_visible(!p_fill && !EditorNode::get_singleton()->is_distraction_free_mode_enabled());
}

void EditorMainScreen::suspend_window_fill() {
	_set_window_fill(false);
}

void EditorMainScreen::update_window_fill() {
	// Docks are added while the editor is being constructed, before the first real selection.
	if (is_inside_tree()) {
		const EditorDock *dock = get_dock(get_current_tab());
		_set_window_fill(dock && (Object::cast_to<AIChatDock>(dock) || dock->get_layout_key() == "DaqianMainScreen" || dock->get_layout_key() == "AINativeMainScreen" || dock->get_layout_key() == "UnifiedSettingsMainScreen"));
	}
}

void EditorMainScreen::_update_workspace_menu() {
	PopupMenu *popup = workspace_menu->get_popup();
	popup->clear();
	for (int i = 0; i < get_tab_count(); i++) {
		if (is_tab_hidden(i)) {
			continue;
		}
		popup->add_icon_radio_check_item(get_tab_icon(i), get_tab_title(i), i);
		const int item = popup->get_item_count() - 1;
		popup->set_item_checked(item, i == get_current_tab());
		popup->set_item_disabled(item, is_tab_disabled(i));
	}
}

void EditorMainScreen::_select_workspace(int p_tab) {
	// This is explicit user navigation, not automatic selection while inspecting a node.
	if (p_tab >= 0 && p_tab < get_tab_count() && !is_tab_hidden(p_tab) && !is_tab_disabled(p_tab)) {
		set_current_tab(p_tab);
	}
}

void EditorMainScreen::_on_tab_changed(int p_tab) {
	EditorNode::get_singleton()->update_distraction_free_mode();
	update_window_fill();

	EditorDock *dock = get_dock(p_tab);
	if (!dock) {
		return;
	}
	const String new_main_screen = dock->get_display_title();

	EditorData &editor_data = EditorNode::get_editor_data();
	int plugin_count = editor_data.get_editor_plugin_count();
	for (int i = 0; i < plugin_count; i++) {
		editor_data.get_editor_plugin(i)->notify_main_screen_changed(new_main_screen);
	}
}

void EditorMainScreen::_notification(int p_what) {
	switch (p_what) {
		case NOTIFICATION_POSTINITIALIZE: {
			set_tab_alignment(TabBar::ALIGNMENT_LEFT);
			get_internal_container()->set_alignment(BoxContainer::ALIGNMENT_BEGIN);
			connect("tab_changed", callable_mp(this, &EditorMainScreen::_on_tab_changed));
		} break;

		case NOTIFICATION_READY: {
			set_popup(nullptr);

			for (int i = 0; i < get_tab_count(); i++) {
				EditorDock *dock = get_dock(i);
				if (dock == Node3DEditor::get_singleton()) {
					dock->make_visible();
					break;
				}
			}
			// AI Chat is the default workspace when the editor opens.
			for (int i = 0; i < get_tab_count(); i++) {
				EditorDock *dock = get_dock(i);
				if (Object::cast_to<AIChatDock>(dock)) {
					dock->make_visible();
					break;
				}
			}
			update_window_fill();
		} break;
	}
}

DockTabContainer::TabStyle EditorMainScreen::get_tab_style() const {
	return (TabStyle)EDITOR_GET("interface/editor/docks/main_screen_dock_tab_style").operator int();
}

Rect2 EditorMainScreen::get_drag_hint_rect() const {
	const Rect2 tab_rect = get_internal_container()->get_global_rect();
	const Rect2 content_rect = get_global_rect();
	Rect2 final_rect = tab_rect.merge(content_rect);
	if (get_tab_count() > 0) {
		float tab_x = get_tab_bar()->get_global_transform().xform(get_tab_bar()->get_tab_rect(0).position).x;
		final_rect.position.x = MIN(tab_x, content_rect.position.x);
		tab_x = get_tab_bar()->get_global_transform().xform(get_tab_bar()->get_tab_rect(-1).get_end()).x;
		final_rect.set_end(Vector2(MAX(tab_x, content_rect.get_end().x), final_rect.get_end().y));
	}
	return final_rect;
}

bool EditorMainScreen::can_switch_dock() const {
	if (get_current_tab() == -1) {
		return true;
	}
	EditorDock *dock = get_dock(get_current_tab());
	return dock->is_allow_switch_screen();
}

void EditorMainScreen::select_next() {
	if (get_tab_count() == 0) {
		return;
	}
	if (get_current_tab() < get_tab_count() - 1) {
		set_current_tab(get_current_tab() + 1);
	} else {
		set_current_tab(0);
	}
}

void EditorMainScreen::select_prev() {
	if (get_tab_count() == 0) {
		return;
	}
	if (get_current_tab() > 0) {
		set_current_tab(get_current_tab() - 1);
	} else {
		set_current_tab(get_tab_count() - 1);
	}
}

#ifndef DISABLE_DEPRECATED
VBoxContainer *EditorMainScreen::get_control() const {
	return main_screen_vbox;
}

void EditorMainScreen::add_main_plugin(EditorPlugin *p_editor) {
	editor_table.push_back(p_editor);
}

void EditorMainScreen::remove_main_plugin(EditorPlugin *p_editor) {
	if (p_editor->has_meta("_dock")) {
		EditorDock *dock = Object::cast_to<EditorDock>(p_editor->get_meta("_dock").get_validated_object());
		if (dock) {
			EditorDockManager::get_singleton()->remove_dock(dock);
		}
	}

	editor_table.erase(p_editor);
}
#endif

EditorMainScreen::EditorMainScreen() :
		DockTabContainer(EditorDock::DOCK_SLOT_MAIN_SCREEN) {
	layout = EditorDock::DOCK_LAYOUT_MAIN_SCREEN;
	grid_rect = Rect2i(2, 0, 4, 4);

	set_theme_type_variation("MainScreenContainer");
	set_custom_minimum_size(Size2(0, 80) * EDSCALE);
	set_v_size_flags(Control::SIZE_EXPAND_FILL);
	set_draw_behind_parent(true);
	get_tab_bar()->set_mouse_filter(Control::MOUSE_FILTER_PASS);
	set_clip_tabs(true);
	get_tab_bar()->set_scroll_to_selected(true);

	workspace_menu = memnew(MenuButton);
	workspace_menu->set_name("WorkspaceMenu");
	workspace_menu->set_focus_mode(Control::FOCUS_ALL);
	workspace_menu->set_text(TTR("Workspaces"));
	workspace_menu->set_tooltip_text(TTR("Select any workspace, including tabs outside the visible area."));
	workspace_menu->set_theme_type_variation("FlatMenuButton");
	workspace_menu->connect("about_to_popup", callable_mp(this, &EditorMainScreen::_update_workspace_menu));
	workspace_menu->get_popup()->connect("id_pressed", callable_mp(this, &EditorMainScreen::_select_workspace));
	get_internal_container()->add_child(workspace_menu);

#ifndef DISABLE_DEPRECATED
	main_screen_vbox = memnew(LegacyMainScreenContainer);
	main_screen_vbox->hide();
	EditorNode::get_singleton()->get_gui_base()->add_child(main_screen_vbox);
#endif

	Ref<StyleBoxEmpty> sb;
	sb.instantiate();
	add_theme_style_override(SceneStringName(panel), sb);
}
