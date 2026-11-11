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
#include "scene/gui/button.h"
#include "scene/gui/flow_container.h"
#include "scene/gui/label.h"
#include "scene/gui/margin_container.h"
#include "scene/gui/option_button.h"
#include "scene/gui/panel_container.h"
#include "scene/gui/scroll_container.h"
#include "scene/gui/tab_container.h"
#include "scene/main/window.h"

// A settings page uses the available workspace; long form contents scroll
// within it instead of growing the editor's anchored root to their desired size.
class SettingsScrollContainer : public ScrollContainer {
public:
	virtual Size2 get_desired_size() const override { return get_minimum_size(); }
};

static VBoxContainer *settings_category(TabContainer *p_tabs, const String &p_title, const String &p_name) {
	ScrollContainer *scroll = memnew(SettingsScrollContainer);
	scroll->set_name(p_name);
	scroll->set_horizontal_scroll_mode(ScrollContainer::SCROLL_MODE_DISABLED);
	scroll->set_follow_focus(true);
	p_tabs->add_child(scroll);
	p_tabs->set_tab_title(p_tabs->get_tab_count() - 1, p_title);
	MarginContainer *margin = memnew(MarginContainer);
	margin->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	margin->set_custom_maximum_size(Size2(1040 * EDSCALE, -1));
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
	PanelContainer *card = memnew(PanelContainer);
	p_parent->add_child(card);
	MarginContainer *padding = memnew(MarginContainer);
	for (const StringName &side : { SNAME("margin_left"), SNAME("margin_top"), SNAME("margin_right"), SNAME("margin_bottom") }) {
		padding->add_theme_constant_override(side, 16 * EDSCALE);
	}
	card->add_child(padding);
	VBoxContainer *group = memnew(VBoxContainer);
	group->set_name(p_name);
	group->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	group->add_theme_constant_override("separation", 12 * EDSCALE);
	padding->add_child(group);
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
	MarginContainer *frame = memnew(MarginContainer);
	frame->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	for (const StringName &side : { SNAME("margin_left"), SNAME("margin_top"), SNAME("margin_right"), SNAME("margin_bottom") }) {
		frame->add_theme_constant_override(side, 16 * EDSCALE);
	}
	dock->add_child(frame);
	VBoxContainer *page = memnew(VBoxContainer);
	page->add_theme_constant_override("separation", 12 * EDSCALE);
	frame->add_child(page);
	Label *title = memnew(Label);
	title->set_text(U"设置");
	title->add_theme_font_size_override("font_size", 24 * EDSCALE);
	page->add_child(title);
	compact_navigation = memnew(OptionButton);
	compact_navigation->set_name("SettingsCategoryPicker");
	compact_navigation->set_accessibility_name(U"设置分类");
	compact_navigation->connect("item_selected", callable_mp(this, &UnifiedSettingsEditorPlugin::_select_category));
	page->add_child(compact_navigation);
	HBoxContainer *layout = memnew(HBoxContainer);
	layout->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	layout->add_theme_constant_override("separation", 20 * EDSCALE);
	page->add_child(layout);
	navigation = memnew(VBoxContainer);
	navigation->set_name("SettingsNavigation");
	navigation->set_custom_minimum_size(Size2(176 * EDSCALE, 0));
	navigation->add_theme_constant_override("separation", 6 * EDSCALE);
	layout->add_child(navigation);
	const String titles[] = { U"对话与 Agent", U"运行环境", U"个人模型库", U"图像与 Mesh", U"美术工具" };
	for (int i = 0; i < 5; i++) {
		Button *button = memnew(Button);
		button->set_text(titles[i]);
		button->set_name("SettingsCategory" + itos(i));
		button->set_toggle_mode(true);
		button->set_text_alignment(HORIZONTAL_ALIGNMENT_LEFT);
		button->set_custom_minimum_size(Size2(0, 38 * EDSCALE));
		button->connect("pressed", callable_mp(this, &UnifiedSettingsEditorPlugin::_select_category).bind(i));
		navigation->add_child(button);
		section_buttons.push_back(button);
		compact_navigation->add_item(titles[i]);
	}
	VBoxContainer *content = memnew(VBoxContainer);
	content->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	content->add_theme_constant_override("separation", 8 * EDSCALE);
	layout->add_child(content);
	section_title = memnew(Label);
	section_title->set_name("SettingsSectionTitle");
	section_title->add_theme_font_size_override("font_size", 20 * EDSCALE);
	content->add_child(section_title);
	section_description = memnew(Label);
	section_description->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	content->add_child(section_description);
	categories = memnew(TabContainer);
	categories->set_name("UnifiedSettingsCategories");
	categories->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	categories->set_tabs_visible(false);
	content->add_child(categories);
	VBoxContainer *ai = settings_category(categories, titles[0], "AISettingsPage");
	VBoxContainer *project = settings_group(ai, U"项目 AI 配置", "ProjectAISettings");
	ai_summary = memnew(Label);
	ai_summary->set_name("ProjectAIStatus");
	ai_summary->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	project->add_child(ai_summary);
	Label *scope = memnew(Label);
	scope->set_text(U"此项目的对话与 Agent 共用以下模型。凭据仅由当前用户保管。");
	scope->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	project->add_child(scope);
	HFlowContainer *actions = memnew(HFlowContainer);
	project->add_child(actions);
	Button *connect_local = memnew(Button);
	connect_local->set_name("ConnectProjectAI");
	connect_local->set_text(U"一键接入");
	connect_local->set_tooltip_text(U"复用天枢：核对当前身份，识别本机已配置的模型并验证文本回复。");
	connect_local->connect("pressed", callable_mp(this, &UnifiedSettingsEditorPlugin::_connect_local_ai));
	actions->add_child(connect_local);
	ai_verify = memnew(Button);
	ai_verify->set_name("VerifyProjectAI");
	ai_verify->set_text(U"测试连接");
	ai_verify->set_tooltip_text(U"向当前项目模型发送一次简短文本请求，验证实际可用性。");
	ai_verify->connect("pressed", callable_mp(this, &UnifiedSettingsEditorPlugin::_verify_ai));
	actions->add_child(ai_verify);
	chat_ai = settings_group(ai, U"对话与 Agent", "ChatAISettingsSlot");
	VBoxContainer *environment = settings_category(categories, titles[1], "EnvironmentSettingsPage");
	chat_environment = settings_group(environment, U"聊天、工作流与编译环境", "ChatEnvironmentSettingsSlot");
	VBoxContainer *catalog = settings_category(categories, titles[2], "ModelCatalogPage");
	catalog_ai = settings_group(catalog, U"已连接的模型", "ModelCatalogSettingsSlot");
	VBoxContainer *art = settings_category(categories, titles[3], "ArtAISettingsPage");
	art_ai = settings_group(art, U"生成服务", "ArtAISettingsSlot");
	VBoxContainer *tools = settings_category(categories, titles[4], "ArtEnvironmentSettingsPage");
	art_environment = settings_group(tools, U"美术工具与本机模型运行库", "ArtEnvironmentSettingsSlot");
	dock->connect("resized", callable_mp(this, &UnifiedSettingsEditorPlugin::_update_navigation));
	categories->connect("tab_changed", callable_mp(this, &UnifiedSettingsEditorPlugin::_select_category));
	_select_category(0);
	ai_toolbar = memnew(HBoxContainer);
	ai_toolbar_id = ai_toolbar->get_instance_id();
	ai_toolbar->set_name("ProjectAIToolbar");
	ai_toolbar->add_theme_constant_override("separation", 4 * EDSCALE);
	ai_entry = memnew(Button);
	ai_entry->set_name("ProjectAIConfiguration");
	ai_entry->set_text(U"AI 配置");
	ai_entry->set_flat(true);
	ai_entry->set_accessibility_name(U"项目 AI 配置与连接状态");
	ai_entry->connect("pressed", callable_mp(this, &UnifiedSettingsEditorPlugin::_open_section).bind("ai"));
	ai_toolbar->add_child(ai_entry);
	ai_status = memnew(Label);
	ai_status->set_name("ProjectAIConnectionStatus");
	ai_status->set_text(U"●");
	ai_status->set_mouse_filter(Control::MOUSE_FILTER_PASS);
	ai_status->add_theme_font_size_override("font_size", 14 * EDSCALE);
	ai_toolbar->add_child(ai_status);
	add_control_to_container(CONTAINER_TOOLBAR, ai_toolbar);
	_refresh_ai_status();
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
		p_source->connect("settings_requested", callable_mp(this, &UnifiedSettingsEditorPlugin::_open_source_section).bind(uint64_t(id)));
	}
	for (const StringName &signal : { SNAME("ai_configuration_changed"), SNAME("ai_connection_status_changed") }) {
		if (p_source->has_signal(signal)) {
			p_source->connect(signal, callable_mp(this, &UnifiedSettingsEditorPlugin::_refresh_ai_status));
		}
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
	_refresh_ai_status();
}

void UnifiedSettingsEditorPlugin::_refresh_ai_status() {
	if (shutting_down || !ai_status) {
		return;
	}
	Dictionary status;
	Dictionary configuration;
	if (AIChatDock *chat = Object::cast_to<AIChatDock>(settings_source("AI Chat"))) {
		status = chat->get_ai_connection_status();
		configuration = chat->get_ai_configuration();
	}
	const String state = status.get("state", "unconfigured");
	const String message = status.get("message", U"尚未配置项目模型");
	const String label = state == "available" ? String(U"可用") : state == "checking" ? String(U"验证中")
			: state == "unavailable"												  ? String(U"不可用")
																					  : String(U"未验证");
	const Color color = state == "available" ? Color(0.25, 0.8, 0.45) : state == "checking" ? Color(0.95, 0.7, 0.2)
			: state == "unavailable"														? Color(0.95, 0.35, 0.35)
																							: Color(0.55, 0.58, 0.62);
	ai_status->add_theme_color_override("font_color", color);
	ai_status->set_meta("connection_state", state);
	const String description = String(U"项目 AI 接入：") + label + "\n" + message + String(U"\n状态对应当前对话与 Agent 模型；图像/Mesh 服务使用各自的连接检查。");
	ai_status->set_tooltip_text(description);
	ai_entry->set_tooltip_text(description);
	const int backend = configuration.get("backend", 0);
	const String current_model = configuration.get(backend == 1 ? "cli_model" : backend == 2 ? "codex_model"
																							 : "model",
			"");
	const String model_label = current_model.is_empty() ? (backend == 1 || backend == 2 ? String(U"CLI 默认模型") : String(U"尚未选择")) : current_model;
	ai_summary->set_text(String(U"当前模型：") + model_label + "\n" + String(U"连接状态：") + label + " · " + message);
	ai_status->set_accessibility_name(String(U"AI 接入") + label);
	ai_verify->set_text(state == "checking" ? String(U"正在测试…") : String(U"测试连接"));
	ai_verify->set_disabled(state == "checking" || configuration.is_empty());
}

void UnifiedSettingsEditorPlugin::_verify_ai() {
	if (AIChatDock *chat = Object::cast_to<AIChatDock>(settings_source("AI Chat"))) {
		chat->verify_ai_connection();
	}
}

void UnifiedSettingsEditorPlugin::_connect_local_ai() {
	_bind_sources();
	if (EditorDock *planner = settings_source("Daqian")) {
		Node *workspace = planner->find_child("DaqianWorkspace", true, false);
		if (workspace && workspace->has_method("connect_project_models")) {
			workspace->call("connect_project_models");
			return;
		}
	}
	ai_summary->set_text(U"天枢模型接入尚未就绪，请稍后重试。");
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
	callable_mp(this, &UnifiedSettingsEditorPlugin::_refresh_ai_status).call_deferred();
}

void UnifiedSettingsEditorPlugin::_restore_all() {
	while (!attachments.is_empty()) {
		_restore_source(attachments[attachments.size() - 1].source);
	}
}

void UnifiedSettingsEditorPlugin::_visibility_changed() {
	if (ObjectDB::get_instance(dock_id) == dock && dock->is_visible_in_tree()) {
		_bind_sources();
		_update_navigation();
	}
}

void UnifiedSettingsEditorPlugin::_dock_exiting() {
	_restore_all();
}

void UnifiedSettingsEditorPlugin::_open_section(const String &p_section) {
	if (shutting_down || ObjectDB::get_instance(dock_id) != dock || !dock->is_inside_tree()) {
		return;
	}
	_select_category(p_section == "environment" ? 1 : p_section == "catalog" ? 2
					: p_section == "art"									 ? 3
					: p_section == "art_environment"						 ? 4
																			 : 0);
	EditorDockManager::get_singleton()->force_focus_dock(dock);
	_bind_sources();
	if (AIChatDock *chat = Object::cast_to<AIChatDock>(settings_source("AI Chat"))) {
		chat->refresh_runtime_controls();
	}
}

void UnifiedSettingsEditorPlugin::_open_source_section(const String &p_section, uint64_t p_source) {
	Node *source = ObjectDB::get_instance<Node>(ObjectID(p_source));
	String section = p_section;
	if (source && source->has_method("get_settings_sections")) {
		section = p_section == "environment" ? "art_environment" : "art";
	} else if (source && source->has_method("get_model_settings_control") && p_section == "ai") {
		section = "catalog";
	}
	_open_section(section);
}

void UnifiedSettingsEditorPlugin::_select_category(int p_index) {
	ERR_FAIL_INDEX(p_index, section_buttons.size());
	categories->set_current_tab(p_index);
	compact_navigation->select(p_index);
	for (int i = 0; i < section_buttons.size(); i++) {
		section_buttons[i]->set_pressed_no_signal(i == p_index);
	}
	section_title->set_text(section_buttons[p_index]->get_text());
	const String descriptions[] = {
		U"为当前项目选择模型，并检查连接状态。",
		U"管理此电脑上的聊天、工作流与编译工具。",
		U"查看已接入的模型，选择适合当前任务的能力。",
		U"配置图像与三维生成服务，并检查各自的连接。",
		U"管理本机美术工具与模型运行库。"
	};
	section_description->set_text(descriptions[p_index]);
	_update_navigation();
}

void UnifiedSettingsEditorPlugin::_update_navigation() {
	if (shutting_down || !navigation || !dock) {
		return;
	}
	// A hidden category can briefly retain its previous width while containers
	// settle. Never let that stale width reopen the sidebar in a narrow window.
	const real_t width = dock->is_inside_tree() ? dock->get_window()->get_size().x : dock->get_size().x;
	const bool compact = width < 900 * EDSCALE;
	navigation->set_visible(!compact);
	compact_navigation->set_visible(compact);
}

void UnifiedSettingsEditorPlugin::_notification(int p_what) {
	if (p_what == NOTIFICATION_EXIT_TREE || p_what == NOTIFICATION_PREDELETE) {
		shutting_down = true;
		_restore_all();
	}
}

UnifiedSettingsEditorPlugin::~UnifiedSettingsEditorPlugin() {
	_restore_all();
	if (ObjectDB::get_instance(ai_toolbar_id) == ai_toolbar) {
		remove_control_from_container(CONTAINER_TOOLBAR, ai_toolbar);
		memdelete(ai_toolbar);
	}
}
