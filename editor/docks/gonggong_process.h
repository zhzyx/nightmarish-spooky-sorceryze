/**************************************************************************/
/*  gonggong_process.h                                                    */
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

#include "core/os/os.h"

#ifdef UNIX_ENABLED
#include <signal.h>
#include <unistd.h>
#endif

// Only pass a PID created and still owned by this editor operation.
static inline void stop_gonggong_process(int64_t p_pid) {
	if (p_pid <= 0 || !OS::get_singleton()->is_process_running(p_pid)) {
		return;
	}
#ifdef WINDOWS_ENABLED
	List<String> arguments;
	arguments.push_back("/PID");
	arguments.push_back(itos(p_pid));
	arguments.push_back("/T");
	arguments.push_back("/F");
	const String taskkill = OS::get_singleton()->get_environment("SystemRoot").path_join("System32/taskkill.exe");
	// The system helper terminates the tree; do not kill its root first.
	if (OS::get_singleton()->create_process(taskkill, arguments) == OK) {
		return;
	}
#endif
#ifdef UNIX_ENABLED
	if (::getpgid(p_pid) == p_pid) {
		::kill(-p_pid, SIGKILL);
	}
#endif
	OS::get_singleton()->kill(p_pid);
}
