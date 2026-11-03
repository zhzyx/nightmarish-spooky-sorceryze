/**************************************************************************/
/*  ai_chat_cli_login.h                                                   */
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

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/string/ustring.h"

namespace AIChatCLILogin {

inline String shell_quote(const String &p_value) {
	return "'" + p_value.replace("'", "'\\''") + "'";
}

inline String macos_script(const String &p_node, const String &p_bridge, const String &p_entry) {
	return "#!/bin/sh\n"
		   "trap '/bin/rm -f -- \"$0\"' 0\n"
		   "trap 'exit 129' HUP\n"
		   "trap 'exit 130' INT\n"
		   "trap 'exit 143' TERM\n"
		   "printf '%s\\n' 'CodeBuddy CLI login: complete authentication in this terminal and browser.'\n" +
			shell_quote(p_node) + " " + shell_quote(p_bridge) + " login " + shell_quote(p_entry) + "\n"
			"status=$?\n"
			"if [ \"$status\" -ne 0 ]; then\n"
			"  printf '\\nCodeBuddy CLI exited with status %s. Check the error above.\\n' \"$status\"\n"
			"  if [ -t 0 ]; then\n"
			"    printf '%s' 'Press Enter to close...'\n"
			"    IFS= read -r reply\n"
			"  fi\n"
			"fi\n"
			"exit \"$status\"\n";
}

// FileAccess writes to "<path>-XXXXXX" and renames on close, so only the
// caller-supplied final path is valid after the handle is released.
inline Error write_macos_script(const String &p_path, const String &p_node, const String &p_bridge, const String &p_entry) {
	Error error = OK;
	{
		Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::WRITE, &error);
		if (file.is_null()) {
			return error == OK ? ERR_FILE_CANT_OPEN : error;
		}
		if (!file->store_string(macos_script(p_node, p_bridge, p_entry))) {
			error = ERR_FILE_CANT_WRITE;
		}
	}
	if (error == OK && !FileAccess::exists(p_path)) {
		error = ERR_FILE_CANT_WRITE;
	}
	if (error == OK) {
		error = FileAccess::set_unix_permissions(p_path, 0700);
	}
	if (error != OK) {
		DirAccess::remove_absolute(p_path);
	}
	return error;
}

} // namespace AIChatCLILogin
