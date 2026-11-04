/**************************************************************************/
/*  ai_chat_editor_control.h                                              */
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

#include "scene/gui/control.h"

// Owned by AIChatDock. All calls run on the editor thread.
class AIChatEditorControl : public Control {
	GDCLASS(AIChatEditorControl, Control);

	String target_id;
	String hint;
	ObjectID target_object;
	float pulse = 0;

protected:
	void _notification(int p_what);

public:
	static constexpr int MAX_STATE_JSON_BYTES = 16 * 1024;
	static constexpr int MAX_STATE_STRING_LENGTH = 1024;
	static constexpr int MAX_STATE_ITEMS = 100;
	// Internal normalization; deliberately not exposed through ClassDB.
	static Dictionary bound_state(const Dictionary &p_state, const PackedStringArray &p_secrets = PackedStringArray());
	static Array tool_definitions();
	static bool handles(const String &p_name);
	static bool valid_project_path(const String &p_path);
	static Array target_ids();
	static bool save_setting_snapshot(const String &p_path, const String &p_original, const String &p_target, const Variant &p_value, String &r_error);
	Control *resolve_target(const String &p_id) const;
	Dictionary get_state(const PackedStringArray &p_secrets = PackedStringArray()) const;
	Dictionary execute(const Dictionary &p_args, bool p_tools_allowed, bool p_consultation, bool p_confirmed = false);
	void clear_highlight();
	AIChatEditorControl();
};
