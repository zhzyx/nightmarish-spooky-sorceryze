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
class CheckBox;
class ConfirmationDialog;
class FileDialog;
class Button;
class TextEdit;
class Timer;

class GongGongPanel : public VBoxContainer {
	VBoxContainer *environment_settings_control = nullptr;
	Callable settings_requested;
	Callable environment_changing;
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
	ConfirmationDialog *setup_dialog = nullptr;
	FileDialog *setup_source_dialog = nullptr;
	LineEdit *setup_source = nullptr;
	Label *setup_missing = nullptr;
	CheckBox *setup_components[3] = {};
	Button *setup_rollback = nullptr;
	bool setup_running = false;
	bool setup_rolling_back = false;
	Dictionary setup_previous;
	String setup_receipt;
	Callable setup_completed;
	void open_setup();
	void start_setup();
	void rollback_setup();
	void run_setup(bool p_rollback);
	void choose_setup_source(const String &p_directory);
	void open_setup_source();
	void run_action(const String &p_action);
	void poll();
	void save_issue_binding(const String &p_text);
	void save_environment_settings();
	void request_environment_settings();
	void update_environment_controls();
	bool apply_environment_settings(const String &p_workspace, const String &p_python, const String &p_tenant);

public:
	GongGongPanel();
	bool ensure_environment();
	Control *get_environment_settings_control() const { return environment_settings_control; }
	void set_settings_requested(const Callable &p_callback) { settings_requested = p_callback; }
	void set_environment_changing_handler(const Callable &p_callback) { environment_changing = p_callback; }
	void set_task_locked(bool p_locked);
	bool set_environment_python(const String &p_python);
	void set_setup_completed(const Callable &p_callback) { setup_completed = p_callback; }
	// Reflect a binding saved elsewhere (the chat Issue guide) without re-saving it.
	void reload_issue_binding();
};
