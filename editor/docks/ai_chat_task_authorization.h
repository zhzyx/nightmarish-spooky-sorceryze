/**************************************************************************/
/*  ai_chat_task_authorization.h                                          */
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

#include "core/variant/dictionary.h"
#include "core/variant/variant.h"

// Host-only ephemeral state. Never serialize this into tool arguments or sessions.
class AIChatTaskAuthorization {
	Dictionary scope;

public:
	void revoke() { scope.clear(); }
	bool matches(const Dictionary &p_scope) const { return !scope.is_empty() && scope == p_scope; }
	bool grant(const Dictionary &p_scope) {
		revoke();
		if (String(p_scope.get("project", "")).is_empty() || String(p_scope.get("conversation", "")).is_empty() || int64_t(p_scope.get("issue", 0)) <= 0 || String(p_scope.get("request", "")).is_empty()) {
			return false;
		}
		scope = p_scope.duplicate(true);
		return true;
	}
	void advance(const Dictionary &p_previous, const Dictionary &p_next) {
		if (matches(p_previous)) {
			Dictionary expected = p_previous.duplicate(true);
			expected["generation"] = p_next.get("generation", Variant());
			if (expected == p_next) {
				scope = p_next.duplicate(true);
				return;
			}
		}
		revoke();
	}
	static bool action_allowed(const String &p_action) {
		return p_action == "scene_create_node" || p_action == "scene_delete_node" || p_action == "scene_rename_node" || p_action == "scene_reparent_node" || p_action == "scene_select_nodes" || p_action == "scene_set_property" || p_action == "scene_assign_resource" || p_action == "scene_connect_signal" || p_action == "scene_disconnect_signal" || p_action == "scene_import_resource" || p_action == "run_project" || p_action == "run_scene" || p_action == "stop_project" || p_action == "game_action_pulse";
	}
	bool allows(const Dictionary &p_scope, const String &p_action, bool p_read_only) const {
		return !p_read_only && matches(p_scope) && action_allowed(p_action);
	}
};
