/**************************************************************************/
/*  ai_chat_scheduler.cpp                                                 */
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

#include "core/object/callable_mp.h"
#include "core/os/time.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/themes/editor_scale.h"
#include "scene/gui/box_container.h"
#include "scene/gui/check_box.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/label.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"
#include "scene/gui/spin_box.h"
#include "scene/gui/tab_bar.h"
#include "scene/gui/tab_container.h"
#include "scene/gui/text_edit.h"
#include "scene/main/timer.h"

namespace {
constexpr int64_t PERIODS[] = { 60, 3600, 86400, 604800 };
const char32_t *UNITS[] = { U"分钟", U"小时", U"天", U"周" };

int64_t period_seconds(const Dictionary &p_task) {
	return int64_t(p_task["frequency"]) * PERIODS[int(p_task["unit"])];
}

bool valid_task(const Dictionary &p_task) {
	for (const char *field : { "id", "frequency", "unit", "sequence", "next_due", "backend" }) {
		Variant value = p_task.get(field, Variant());
		if (!value.is_num() || double(value) < 0 || double(value) >= (String(field) == "next_due" ? 1000000000000.0 : double(INT32_MAX - 1)) || double(value) != Math::floor(double(value))) {
			return false;
		}
	}
	for (const char *field : { "title", "prompt", "model", "cli_model" }) {
		if (p_task.get(field, Variant()).get_type() != Variant::STRING) {
			return false;
		}
	}
	const String title = p_task["title"];
	for (int i = 0; i < title.length(); i++) {
		if (title[i] < 32 || title[i] == 127) {
			return false;
		}
	}
	return int(p_task["id"]) > 0 && !title.strip_edges().is_empty() && title.length() <= 48 &&
			!String(p_task["prompt"]).strip_edges().is_empty() && String(p_task["prompt"]).utf8().length() <= 256 * 1024 &&
			int(p_task["frequency"]) >= 1 && int(p_task["frequency"]) <= 10000 && int(p_task["unit"]) < 4 &&
			int(p_task["backend"]) < 4 && p_task.get("enabled", Variant()).get_type() == Variant::BOOL;
}

String run_status(const String &p_state) {
	if (p_state == "waiting") {
		return U"等待空闲";
	}
	if (p_state == "running") {
		return U"执行中";
	}
	if (p_state == "completed") {
		return U"已完成";
	}
	if (p_state == "failed") {
		return U"失败／已停止";
	}
	return U"重启中断，未自动重跑";
}
} //namespace

int AIChatDock::_schedule_index(int p_id) const {
	for (int i = 0; i < schedule_tasks.size(); i++) {
		if (int(Dictionary(schedule_tasks[i])["id"]) == p_id) {
			return i;
		}
	}
	return -1;
}

int AIChatDock::_agent_index(int p_id) const {
	for (int i = 0; i < agent_tabs->get_tab_count(); i++) {
		if (int(agent_tabs->get_tab_metadata(i)) == p_id) {
			return i;
		}
	}
	return -1;
}

int AIChatDock::_manual_agent_count() const {
	return agent_tabs->get_tab_count() - scheduled_agents.size() - sub_agents.size();
}

bool AIChatDock::_schedule_outstanding(int p_id) const {
	for (const KeyValue<int, Dictionary> &entry : scheduled_agents) {
		const String state = entry.value["state"];
		if (int(entry.value["schedule_id"]) == p_id && (state == "waiting" || state == "running")) {
			return true;
		}
	}
	return false;
}

void AIChatDock::_build_scheduler_ui(Control *p_page) {
	VBoxContainer *page = Object::cast_to<VBoxContainer>(p_page);
	page->add_theme_constant_override("separation", 8 * EDSCALE);
	HBoxContainer *toolbar = memnew(HBoxContainer);
	page->add_child(toolbar);
	schedule_picker = memnew(OptionButton);
	schedule_picker->set_name("ScheduledTasks");
	schedule_picker->set_h_size_flags(SIZE_EXPAND_FILL);
	schedule_picker->connect("item_selected", callable_mp(this, &AIChatDock::_schedule_selected));
	toolbar->add_child(schedule_picker);
	Button *create = memnew(Button);
	create->set_name("AddScheduledTask");
	create->set_text(U"新增任务");
	create->connect("pressed", callable_mp(this, &AIChatDock::_edit_schedule).bind(true));
	toolbar->add_child(create);
	schedule_edit = memnew(Button);
	schedule_edit->set_name("EditScheduledTask");
	schedule_edit->set_text(U"编辑");
	schedule_edit->connect("pressed", callable_mp(this, &AIChatDock::_edit_schedule).bind(false));
	toolbar->add_child(schedule_edit);
	schedule_delete = memnew(Button);
	schedule_delete->set_name("DeleteScheduledTask");
	schedule_delete->set_text(U"删除任务");
	schedule_delete->connect("pressed", callable_mp(this, &AIChatDock::_delete_schedule_requested));
	toolbar->add_child(schedule_delete);
	schedule_description = memnew(Label);
	schedule_description->set_name("ScheduledTaskDescription");
	schedule_description->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	page->add_child(schedule_description);
	HBoxContainer *actions = memnew(HBoxContainer);
	page->add_child(actions);
	schedule_enabled = memnew(CheckBox);
	schedule_enabled->set_name("ScheduledTaskEnabled");
	schedule_enabled->set_text(U"启用周期执行");
	schedule_enabled->connect("toggled", callable_mp(this, &AIChatDock::_enable_schedule));
	actions->add_child(schedule_enabled);
	schedule_run = memnew(Button);
	schedule_run->set_name("RunScheduledTaskNow");
	schedule_run->set_text(U"立即执行");
	schedule_run->connect("pressed", callable_mp(this, &AIChatDock::_run_schedule_now));
	actions->add_child(schedule_run);
	Label *policy = memnew(Label);
	policy->set_text(U"仅编辑器运行时触发；首次在一个周期后执行。天／周为间隔周期，不是固定日历时刻。忙时等待，同任务不重叠；重启不补跑。沿用当前工具审批设置。");
	policy->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	page->add_child(policy);
	timer_agent_tabs = memnew(TabBar);
	timer_agent_tabs->set_name("ScheduledAgentTabs");
	timer_agent_tabs->set_tab_alignment(TabBar::ALIGNMENT_LEFT);
	timer_agent_tabs->set_tab_close_display_policy(TabBar::CLOSE_BUTTON_SHOW_ALWAYS);
	timer_agent_tabs->set_clip_tabs(true);
	timer_agent_tabs->connect("tab_selected", callable_mp(this, &AIChatDock::_timer_agent_selected));
	timer_agent_tabs->connect("tab_close_pressed", callable_mp(this, &AIChatDock::_timer_agent_close));
	page->add_child(timer_agent_tabs);
	schedule_notice = memnew(Label);
	schedule_notice->set_name("ScheduledTaskStatus");
	schedule_notice->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	page->add_child(schedule_notice);
	timer_chat_host = memnew(VBoxContainer);
	timer_chat_host->set_name("ScheduledAgentChat");
	timer_chat_host->set_v_size_flags(SIZE_EXPAND_FILL);
	page->add_child(timer_chat_host);

	schedule_dialog = memnew(ConfirmationDialog);
	schedule_dialog->set_name("ScheduledTaskDialog");
	schedule_dialog->set_title(U"周期任务");
	schedule_dialog->set_ok_button_text(U"保存任务");
	schedule_dialog->connect("confirmed", callable_mp(this, &AIChatDock::_save_schedule));
	add_child(schedule_dialog);
	VBoxContainer *form = memnew(VBoxContainer);
	schedule_dialog->add_child(form);
	Label *title_hint = memnew(Label);
	title_hint->set_text(U"主题（每次生成 主题_n，最多 48 字符）");
	form->add_child(title_hint);
	schedule_title = memnew(LineEdit);
	schedule_title->set_name("ScheduledTaskTitle");
	schedule_title->set_max_length(48);
	schedule_title->connect("text_changed", callable_mp(this, &AIChatDock::_validate_schedule).unbind(1));
	form->add_child(schedule_title);
	Label *prompt_hint = memnew(Label);
	prompt_hint->set_text(U"任务介绍／发给 AI 的指令");
	form->add_child(prompt_hint);
	schedule_prompt = memnew(TextEdit);
	schedule_prompt->set_name("ScheduledTaskPrompt");
	schedule_prompt->set_custom_minimum_size(Size2(580, 180) * EDSCALE);
	schedule_prompt->set_line_wrapping_mode(TextEdit::LINE_WRAPPING_BOUNDARY);
	schedule_prompt->connect("text_changed", callable_mp(this, &AIChatDock::_validate_schedule));
	form->add_child(schedule_prompt);
	HBoxContainer *period = memnew(HBoxContainer);
	form->add_child(period);
	Label *every = memnew(Label);
	every->set_text(U"每");
	period->add_child(every);
	schedule_frequency = memnew(SpinBox);
	schedule_frequency->set_name("ScheduledTaskFrequency");
	schedule_frequency->set_min(1);
	schedule_frequency->set_max(10000);
	schedule_frequency->set_step(1);
	period->add_child(schedule_frequency);
	schedule_unit = memnew(OptionButton);
	schedule_unit->set_name("ScheduledTaskUnit");
	for (const char32_t *unit : UNITS) {
		schedule_unit->add_item(unit);
	}
	period->add_child(schedule_unit);
	schedule_validation = memnew(Label);
	schedule_validation->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	form->add_child(schedule_validation);
	schedule_delete_dialog = memnew(ConfirmationDialog);
	schedule_delete_dialog->set_name("DeleteScheduledTaskConfirmation");
	schedule_delete_dialog->set_title(U"删除周期任务");
	schedule_delete_dialog->connect("confirmed", callable_mp(this, &AIChatDock::_delete_schedule));
	add_child(schedule_delete_dialog);
	schedule_timer = memnew(Timer);
	schedule_timer->set_name("ScheduledTaskTimer");
	schedule_timer->set_wait_time(1.0);
	schedule_timer->connect("timeout", callable_mp(this, &AIChatDock::_scheduler_tick));
	add_child(schedule_timer);
	_refresh_schedules();
}

void AIChatDock::_load_schedules(const Dictionary &p_data) {
	const Variant tasks = p_data.get("scheduled_tasks", Array());
	if (tasks.get_type() == Variant::ARRAY && Array(tasks).size() <= 32) {
		const int64_t now = int64_t(Time::get_singleton()->get_unix_time_from_system());
		for (const Variant &value : Array(tasks)) {
			if (value.get_type() != Variant::DICTIONARY || !valid_task(value)) {
				continue;
			}
			Dictionary task = Dictionary(value).duplicate(true);
			const int id = task["id"];
			if (_schedule_index(id) >= 0) {
				continue;
			}
			next_schedule = MAX(next_schedule, id + 1);
			// Offline ticks never accumulate and never replay interrupted operations.
			if (int64_t(task["next_due"]) <= now) {
				task["next_due"] = now + period_seconds(task);
			}
			schedule_tasks.push_back(task);
		}
	}
	const Array agents = p_data.get("agents", Array());
	for (const Variant &value : agents) {
		const Dictionary agent = value;
		const Variant run_value = agent.get("scheduled_run", Variant());
		if (run_value.get_type() != Variant::DICTIONARY) {
			continue;
		}
		Dictionary run = Dictionary(run_value).duplicate(true);
		const Variant owner = run.get("schedule_id", Variant());
		const Variant state = run.get("state", Variant());
		if (!owner.is_num() || _schedule_index(int(owner)) < 0 || state.get_type() != Variant::STRING) {
			continue;
		}
		const int id = agent["id"];
		const int index = _agent_index(id);
		if (index < 0 || scheduled_agents.size() >= 128) {
			continue;
		}
		const String status = state;
		if (status != "waiting" && status != "running" && status != "completed" && status != "failed" && status != "interrupted") {
			continue;
		}
		if (status == "waiting" || status == "running") {
			run["state"] = "interrupted";
		}
		scheduled_agents.insert(id, run);
		agent_tabs->set_tab_hidden(index, true);
	}
	if (!schedule_tasks.is_empty()) {
		selected_schedule = Dictionary(schedule_tasks[0])["id"];
	}
	if (scheduled_agents.has(active_agent)) {
		selected_schedule = scheduled_agents[active_agent]["schedule_id"];
	}
	for (int i = 0; i < agent_tabs->get_tab_count(); i++) {
		const int id = agent_tabs->get_tab_metadata(i);
		if (!scheduled_agents.has(id)) {
			last_manual_agent = id;
			break;
		}
	}
	_refresh_schedules();
	_route_chat_layout();
}

void AIChatDock::_refresh_schedules() {
	if (!schedule_picker) {
		return;
	}
	schedule_ui_updating = true;
	schedule_picker->clear();
	for (int i = 0; i < schedule_tasks.size(); i++) {
		const Dictionary task = schedule_tasks[i];
		schedule_picker->add_item(String(task["title"]) + (bool(task["enabled"]) ? U" · 已启用" : U" · 已暂停"));
		schedule_picker->set_item_metadata(i, task["id"]);
		if (int(task["id"]) == selected_schedule) {
			schedule_picker->select(i);
		}
	}
	const int index = _schedule_index(selected_schedule);
	schedule_enabled->set_disabled(index < 0);
	schedule_edit->set_disabled(index < 0);
	schedule_delete->set_disabled(index < 0);
	schedule_run->set_disabled(index < 0 || _schedule_outstanding(selected_schedule));
	schedule_enabled->set_pressed_no_signal(index >= 0 && bool(Dictionary(schedule_tasks[index])["enabled"]));
	if (index >= 0) {
		const Dictionary task = schedule_tasks[index];
		const String next = Time::get_singleton()->get_datetime_string_from_unix_time(int64_t(task["next_due"]) + int64_t(Time::get_singleton()->get_time_zone_from_system()["bias"]) * 60);
		schedule_description->set_text(vformat(U"%s · 每 %d %s · %s\n%s", task["title"], task["frequency"], UNITS[int(task["unit"])], bool(task["enabled"]) ? String(U"下次：") + next : String(U"已暂停"), String(task["prompt"]).left(600)));
		schedule_description->set_text(schedule_description->get_text() + String(task.get("notice", "")));
		schedule_description->set_tooltip_text(task["prompt"]);
	} else {
		schedule_description->set_text(U"暂无任务。新增主题、任务介绍和执行频率后，每次触发都会创建独立的 主题_n 会话。");
	}
	schedule_ui_updating = false;
	_refresh_schedule_agents();
}

void AIChatDock::_refresh_schedule_agents() {
	if (!timer_agent_tabs) {
		return;
	}
	timer_agent_tabs->set_block_signals(true);
	timer_agent_tabs->clear_tabs();
	for (int i = 0; i < agent_tabs->get_tab_count(); i++) {
		const int id = agent_tabs->get_tab_metadata(i);
		if (!scheduled_agents.has(id) || int(scheduled_agents[id]["schedule_id"]) != selected_schedule) {
			continue;
		}
		const Dictionary run = scheduled_agents[id];
		const int index = timer_agent_tabs->get_tab_count();
		timer_agent_tabs->add_tab(agent_tabs->get_tab_title(i));
		timer_agent_tabs->set_tab_metadata(index, id);
		timer_agent_tabs->set_tab_tooltip(index, run_status(run["state"]));
		if (id == active_agent) {
			timer_agent_tabs->set_current_tab(index);
		}
	}
	timer_agent_tabs->set_block_signals(false);
	const bool showing = scheduled_agents.has(active_agent) && int(scheduled_agents[active_agent]["schedule_id"]) == selected_schedule;
	if (showing) {
		schedule_notice->set_text(_agent_title(active_agent) + U" · " + run_status(scheduled_agents[active_agent]["state"]));
	} else {
		schedule_notice->set_text(busy ? U"当前有会话执行中，结束后可切换查看；定时任务等待空闲，不打断它。" : U"在任务介绍下选择一个执行会话查看对话。每次执行均有独立上下文。");
	}
	_route_chat_layout();
}

void AIChatDock::_route_chat_layout() {
	if (!chat_layout || !timer_chat_host) {
		return;
	}
	const bool scheduled = scheduled_agents.has(active_agent);
	manual_schedule_notice->set_visible(scheduled);
	if (scheduled) {
		manual_schedule_notice->set_text(_agent_title(active_agent) + U" 正在定时器页执行／显示。任务结束后可切回普通会话；执行中仍可切页查看，普通会话草稿不会被使用。");
	}
	Control *target = scheduled ? timer_chat_host : agents_page;
	if (!scheduled && daqian_chat_host.is_valid()) {
		target = ObjectDB::get_instance<Control>(daqian_chat_host);
		ERR_FAIL_NULL(target);
	}
	if (chat_layout->get_parent() != target) {
		chat_layout->reparent(target);
	}
	chat_layout->set_visible(!scheduled || int(scheduled_agents[active_agent]["schedule_id"]) == selected_schedule);
}

void AIChatDock::_workspace_selected(int p_index) {
	if (p_index == 0 && scheduled_agents.has(active_agent) && !busy && !models_loading && engine_build_pid < 0) {
		const int index = _agent_index(last_manual_agent);
		if (index >= 0) {
			_agent_selected(index);
		}
	}
	_route_chat_layout();
}

void AIChatDock::_schedule_selected(int p_index) {
	if (schedule_ui_updating || p_index < 0 || p_index >= schedule_picker->get_item_count()) {
		return;
	}
	selected_schedule = schedule_picker->get_item_metadata(p_index);
	_refresh_schedules();
}

void AIChatDock::_edit_schedule(bool p_new) {
	if (p_new && schedule_tasks.size() >= 32) {
		schedule_notice->set_text(U"最多 32 个周期任务，请删除不再需要的任务。");
		return;
	}
	const int index = _schedule_index(selected_schedule);
	if (!p_new && index < 0) {
		return;
	}
	editing_schedule = p_new ? -1 : selected_schedule;
	const Dictionary task = p_new ? Dictionary() : Dictionary(schedule_tasks[index]);
	schedule_title->set_text(task.get("title", ""));
	schedule_prompt->set_text(task.get("prompt", ""));
	schedule_frequency->set_value(task.get("frequency", 1));
	schedule_unit->select(task.get("unit", 1));
	_validate_schedule();
	schedule_dialog->popup_centered();
	schedule_title->grab_focus();
}

void AIChatDock::_validate_schedule() {
	const String task_title = schedule_title->get_text().strip_edges();
	bool valid = !task_title.is_empty() && task_title.length() <= 48 && !schedule_prompt->get_text().strip_edges().is_empty() && schedule_prompt->get_text().utf8().length() <= 256 * 1024;
	for (int i = 0; i < task_title.length(); i++) {
		if (task_title[i] < 32 || task_title[i] == 127) {
			valid = false;
		}
	}
	for (const Variant &value : schedule_tasks) {
		const Dictionary task = value;
		if (int(task["id"]) != editing_schedule && String(task["title"]) == task_title) {
			valid = false;
		}
	}
	schedule_dialog->get_ok_button()->set_disabled(!valid);
	schedule_validation->set_text(valid ? U"保存后从一个完整周期开始计时；使用当前连接方式和模型。不会修改已创建会话的指令。" : U"请输入唯一主题和任务指令（正文最多 256 KiB）。");
}

void AIChatDock::_save_schedule() {
	_validate_schedule();
	if (schedule_dialog->get_ok_button()->is_disabled() || !history_writable) {
		return;
	}
	int index = _schedule_index(editing_schedule);
	if (editing_schedule >= 0 && index < 0) {
		return;
	}
	Dictionary task = index >= 0 ? Dictionary(schedule_tasks[index]).duplicate(true) : Dictionary();
	if (index < 0) {
		if (schedule_tasks.size() >= 32 || next_schedule >= INT32_MAX - 1) {
			return;
		}
		task["id"] = next_schedule++;
		task["sequence"] = 0;
		task["enabled"] = true;
	}
	task["title"] = _redact(schedule_title->get_text().strip_edges());
	task["prompt"] = _redact(schedule_prompt->get_text());
	task["frequency"] = int(schedule_frequency->get_value());
	task["unit"] = schedule_unit->get_selected();
	task["backend"] = backend->get_selected();
	task["model"] = model->get_text();
	task["cli_model"] = backend->get_selected() == 2 ? codex_model->get_text() : cli_model->get_text();
	task["next_due"] = int64_t(Time::get_singleton()->get_unix_time_from_system()) + period_seconds(task);
	if (index < 0) {
		schedule_tasks.push_back(task);
	} else {
		schedule_tasks[index] = task;
	}
	selected_schedule = task["id"];
	schedule_dialog->hide();
	_refresh_schedules();
	_queue_history_save();
}

void AIChatDock::_delete_schedule_requested() {
	if (_schedule_index(selected_schedule) < 0) {
		return;
	}
	deleting_schedule = selected_schedule;
	schedule_delete_dialog->set_text(U"删除该周期任务及其全部执行会话和聊天？执行中的任务会停止，已应用的文件修改不会撤销。此操作不可恢复。");
	schedule_delete_dialog->popup_centered();
}

void AIChatDock::_delete_schedule() {
	const int index = _schedule_index(deleting_schedule);
	if (index < 0) {
		return;
	}
	Vector<int> remove;
	for (const KeyValue<int, Dictionary> &entry : scheduled_agents) {
		if (int(entry.value["schedule_id"]) == deleting_schedule) {
			remove.push_back(entry.key);
		}
	}
	// Removing the active run last keeps the surviving manual session selected.
	for (int id : remove) {
		if (id != active_agent) {
			pending_close_agent = id;
			_close_agent();
		}
	}
	if (scheduled_agents.has(active_agent) && int(scheduled_agents[active_agent]["schedule_id"]) == deleting_schedule) {
		pending_close_agent = active_agent;
		_close_agent();
	}
	schedule_tasks.remove_at(index);
	selected_schedule = schedule_tasks.is_empty() ? -1 : int(Dictionary(schedule_tasks[0])["id"]);
	deleting_schedule = -1;
	_refresh_schedules();
	_queue_history_save();
}

void AIChatDock::_enable_schedule(bool p_enabled) {
	if (schedule_ui_updating) {
		return;
	}
	const int index = _schedule_index(selected_schedule);
	if (index < 0) {
		return;
	}
	Dictionary task = schedule_tasks[index];
	task["enabled"] = p_enabled;
	task.erase("notice");
	if (p_enabled) {
		task["next_due"] = int64_t(Time::get_singleton()->get_unix_time_from_system()) + period_seconds(task);
	}
	if (!p_enabled) {
		for (KeyValue<int, Dictionary> &entry : scheduled_agents) {
			if (int(entry.value["schedule_id"]) == selected_schedule && String(entry.value["state"]) == "waiting") {
				entry.value["state"] = "failed";
				if (agent_sessions.has(entry.key)) {
					agent_sessions[entry.key].queue_paused = true;
				}
			}
		}
	}
	_refresh_schedules();
	_queue_history_save();
}

void AIChatDock::_run_schedule_now() {
	const int index = _schedule_index(selected_schedule);
	if (index < 0) {
		return;
	}
	_enqueue_schedule(index);
	_refresh_schedules();
	_scheduler_dispatch();
}

bool AIChatDock::_enqueue_schedule(int p_index) {
	Dictionary task = schedule_tasks[p_index];
	if (_schedule_outstanding(task["id"])) {
		return false;
	}
	if (!history_writable || scheduled_agents.size() >= 128 || agent_tabs->get_tab_count() >= 256 || next_agent >= INT32_MAX - 1 || int(task["sequence"]) >= INT32_MAX - 1) {
		task["enabled"] = false;
		task["notice"] = U"\n定时任务已暂停：历史无法保存，或执行历史已达上限（128 个定时会话）。请删除不再需要的执行会话后重新启用。";
		_queue_history_save();
		return false;
	}
	const int id = next_agent++;
	const int sequence = int(task["sequence"]) + 1;
	task["sequence"] = sequence;
	AgentSession session;
	session.model = task["model"];
	session.cli_model = task["cli_model"];
	session.codex_model = task["cli_model"];
	session.backend = task["backend"];
	session.message_list = memnew(VBoxContainer);
	session.message_list->set_name(vformat("ArchivedMessages%d", id));
	session.message_list->set_h_size_flags(SIZE_EXPAND_FILL);
	session.message_list->add_theme_constant_override("separation", 16 * EDSCALE);
	agent_archive->add_child(session.message_list);
	Dictionary message;
	message["role"] = "user";
	message["content"] = task["prompt"];
	session.queued_messages.push_back(message);
	agent_sessions.insert(id, session);
	Dictionary run;
	run["schedule_id"] = task["id"];
	run["state"] = "waiting";
	scheduled_agents.insert(id, run);
	agent_tabs->set_block_signals(true);
	const int tab = agent_tabs->get_tab_count();
	agent_tabs->add_tab(vformat("%s_%d", task["title"], sequence));
	agent_tabs->set_tab_metadata(tab, id);
	agent_tabs->set_tab_hidden(tab, true);
	agent_tabs->set_block_signals(false);
	_queue_history_save();
	return true;
}

void AIChatDock::_scheduler_tick() {
	if (!history_loaded || history_restoring || !history_writable || engine_restart_requested) {
		return;
	}
	const int64_t now = int64_t(Time::get_singleton()->get_unix_time_from_system());
	bool changed = false;
	for (int i = 0; i < schedule_tasks.size(); i++) {
		Dictionary task = schedule_tasks[i];
		if (!bool(task["enabled"]) || now < int64_t(task["next_due"])) {
			continue;
		}
		const int64_t period = period_seconds(task);
		const int64_t due = task["next_due"];
		task["next_due"] = due + ((now - due) / period + 1) * period;
		_enqueue_schedule(i);
		changed = true;
	}
	if (changed) {
		_refresh_schedules();
		_queue_history_save();
	}
	_scheduler_dispatch();
}

void AIChatDock::_scheduler_dispatch() {
	if (!is_inside_tree() || !history_loaded || history_restoring || busy || models_loading || engine_build_pid >= 0 || engine_restart_requested || (!queue_paused && !queued_messages.is_empty())) {
		return;
	}
	// Stable Agent creation order is the scheduler's FIFO, not HashMap order.
	for (int i = 0; i < agent_tabs->get_tab_count(); i++) {
		const int id = agent_tabs->get_tab_metadata(i);
		if (!scheduled_agents.has(id) || String(scheduled_agents[id]["state"]) != "waiting") {
			continue;
		}
		selected_schedule = scheduled_agents[id]["schedule_id"];
		_agent_selected(i);
		if (active_agent != id) {
			return;
		}
		scheduled_agents[id]["state"] = "running";
		_dispatch_queued_message(id);
		if (!busy) {
			scheduled_agents[id]["state"] = "failed";
		}
		_refresh_schedules();
		_queue_history_save();
		return;
	}
}

void AIChatDock::_scheduler_finished() {
	if (!is_inside_tree() || history_restoring) {
		return;
	}
	// Completed periodic Agents retain history, not idle CLI subprocesses.
	if (!busy && scheduled_agents.has(active_agent) && queued_messages.is_empty()) {
		_cancel_cli();
		set_process(process_id >= 0 || sub_agent_parallel_pid >= 0);
	}
	if (!busy && !models_loading && engine_build_pid < 0 && _manual_agent_count() == 0) {
		_add_agent();
	}
	_refresh_schedules();
	if (!busy && !models_loading && engine_build_pid < 0 && workspace_pages->get_current_tab() == 0 && scheduled_agents.has(active_agent)) {
		const int index = _agent_index(last_manual_agent);
		if (index >= 0) {
			_agent_selected(index);
		}
	}
	_scheduler_dispatch();
}

void AIChatDock::_timer_agent_selected(int p_index) {
	if (p_index < 0 || p_index >= timer_agent_tabs->get_tab_count()) {
		return;
	}
	const int index = _agent_index(timer_agent_tabs->get_tab_metadata(p_index));
	if (index >= 0) {
		_agent_selected(index);
	}
	_refresh_schedule_agents();
}

void AIChatDock::_timer_agent_close(int p_index) {
	if (p_index < 0 || p_index >= timer_agent_tabs->get_tab_count()) {
		return;
	}
	const int index = _agent_index(timer_agent_tabs->get_tab_metadata(p_index));
	if (index >= 0) {
		_agent_close_requested(index);
	}
}

void AIChatDock::_scheduled_agent_removed(int p_id) {
	scheduled_agents.erase(p_id);
	if (_manual_agent_count() == 0 && !busy && !models_loading && engine_build_pid < 0) {
		_add_agent();
	}
	_refresh_schedules();
}
