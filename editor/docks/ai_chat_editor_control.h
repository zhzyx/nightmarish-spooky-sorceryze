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

#include "core/templates/hash_map.h"
#include "scene/gui/control.h"

class AIChatEditorRegistry;

// Owned by AIChatDock. All calls run on the editor thread.
class AIChatEditorControl : public Control {
	GDCLASS(AIChatEditorControl, Control);

	struct Target {
		ObjectID control;
		String name;
		String screen;
	};
	static AIChatEditorControl *singleton;
	HashMap<String, Target> targets;
	AIChatEditorRegistry *registry = nullptr;
	struct RoutedRequest {
		String fingerprint;
		Dictionary result;
		uint64_t updated = 0;
	};
	HashMap<String, RoutedRequest> routed_requests;
	Dictionary workflow;
	ObjectID guidance_timer;
	ObjectID observed_button;
	uint64_t target_missing_since = 0;
	uint64_t guidance_revision = 0;

	String target_id;
	String hint;
	ObjectID target_object;
	float pulse = 0;
	void _poll_guidance();
	void _target_pressed();
	void _disconnect_observer();
	void _activate_step(bool p_prepare);
	void _advance(const String &p_observation);
	void _persist_guidance() const;
	void _restore_guidance();
	void _set_guidance_status(const String &p_status, const String &p_error = String());
	Dictionary _guidance_action(const Dictionary &p_args, bool p_confirmed);
	static bool _valid_steps(const Array &p_steps);

protected:
	static void _bind_methods();
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
	static AIChatEditorControl *get_singleton() { return singleton; }
	bool register_target(const String &p_id, Control *p_control, const String &p_name, const String &p_screen = String());
	bool unregister_target(const String &p_id);
	Array find_targets(const String &p_query, int p_limit = 8) const;
	Dictionary describe_target(const String &p_id) const;
	Dictionary guidance_status() const;
	void cancel_guidance();
	void suspend_guidance();
	Dictionary get_state(const PackedStringArray &p_secrets = PackedStringArray()) const;
	Dictionary execute(const Dictionary &p_args, bool p_tools_allowed, bool p_consultation, bool p_confirmed = false);
	Dictionary route_message(const Dictionary &p_message, bool p_tools_allowed, bool p_consultation, bool p_confirmed = false);
	Dictionary route_status(const String &p_request_id, const String &p_source) const;
	Dictionary cancel_route(const Dictionary &p_message, const String &p_reason);
	void clear_highlight();
	AIChatEditorControl();
	~AIChatEditorControl();
};
