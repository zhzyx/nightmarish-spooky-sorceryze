/**************************************************************************/
/*  gonggong_panel.h                                                      */
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

#pragma once

#include "scene/gui/box_container.h"

class LineEdit;
class Label;
class ConfirmationDialog;
class Button;
class TextEdit;
class Timer;

class GongGongPanel : public VBoxContainer {
	VBoxContainer *environment_settings_control = nullptr;
	Callable settings_requested;
	Callable environment_changing;
	Callable runtime_changed;
	bool task_locked = false;
	LineEdit *workspace = nullptr;
	LineEdit *python = nullptr;
	LineEdit *tenant = nullptr;
	LineEdit *issue_number = nullptr;
	LineEdit *request_id = nullptr;
	TextEdit *output = nullptr;
	Timer *timer = nullptr;
	int64_t worker = -1;
	String result_path;
	String setup_progress_path;
	String setup_last_progress;
	ConfirmationDialog *setup_dialog = nullptr;
	Label *setup_missing = nullptr;
	TextEdit *setup_progress = nullptr;
	Button *setup_github_login = nullptr;
	String setup_github_path;
	String setup_agent_details;
	bool setup_github_authenticating = false;
	Button *setup_rollback = nullptr;
	bool setup_running = false;
	bool setup_rolling_back = false;
	bool setup_attempted = false;
	Dictionary setup_previous;
	String setup_receipt;
	Callable setup_completed;
	void open_setup();
	void start_setup();
	void rollback_setup();
	void run_setup(bool p_rollback);
	void set_setup_status(const String &p_status);
	void refresh_setup_progress();
	void login_github();
	void finish_setup_github(const Dictionary &p_github);
	void run_action(const String &p_action);
	void poll();
	void save_issue_binding(const String &p_text);
	void runtime_python_changed(const String &p_value);
	void save_environment_settings();
	void request_environment_settings();
	void update_environment_controls();
	bool apply_environment_settings(const String &p_workspace, const String &p_tenant);

public:
	GongGongPanel(bool p_check_environment = true);
	bool ensure_environment();
	bool ensure_environment_with_snapshot(const Dictionary &p_runtime);
	Control *get_environment_settings_control() const { return environment_settings_control; }
	void set_settings_requested(const Callable &p_callback) { settings_requested = p_callback; }
	void set_environment_changing_handler(const Callable &p_callback) { environment_changing = p_callback; }
	void set_runtime_changed_handler(const Callable &p_callback) { runtime_changed = p_callback; }
	void set_task_locked(bool p_locked);
	bool set_environment_python(const String &p_python);
	String set_runtime_field(const String &p_field, const String &p_value);
	void refresh_runtime_controls(const Dictionary &p_runtime);
	bool start_ai_setup(const Array &p_missing);
	void set_setup_completed(const Callable &p_callback) { setup_completed = p_callback; }
	// Reflect a binding saved elsewhere (the chat Issue guide) without re-saving it.
	void reload_issue_binding();
};
