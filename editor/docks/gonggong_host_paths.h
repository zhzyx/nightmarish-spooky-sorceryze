/**************************************************************************/
/*  gonggong_host_paths.h                                                 */
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

#include "core/io/file_access.h"
#include "core/os/os.h"

// Resolve from the installed executable, independently of the current directory.
class GongGongHostPaths {
public:
	static String find_ancestor(String directory, const String &marker) {
		while (!directory.is_empty()) {
			if (FileAccess::exists(directory.path_join(marker))) {
				return directory;
			}
			const String parent = directory.get_base_dir();
			if (parent == directory) {
				break;
			}
			directory = parent;
		}
		return String();
	}

	static String workspace() {
		const String configured = OS::get_singleton()->get_environment("GONGGONG_WORKSPACE");
		if (!configured.is_empty()) {
			return configured;
		}
		const String executable_dir = OS::get_singleton()->get_executable_path().get_base_dir();
		const String ancestor = find_ancestor(executable_dir, "gonggong-workspace.json");
		if (!ancestor.is_empty()) {
			return ancestor;
		}
		return String();
	}
};
