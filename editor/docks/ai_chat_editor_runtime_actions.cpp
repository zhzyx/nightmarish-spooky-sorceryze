/**************************************************************************/
/*  ai_chat_editor_runtime_actions.cpp                                   */
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

#include "ai_chat_editor_runtime_actions.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/image.h"
#include "core/os/os.h"
#include "editor/debugger/editor_debugger_node.h"
#include "editor/debugger/script_editor_debugger.h"
#include "editor/editor_interface.h"
#include "editor/editor_node.h"
#include "scene/main/viewport.h"
#include "servers/display/display_server.h"

namespace {
Dictionary result(bool p_ok, const String &p_error = String()) {
	Dictionary r;
	r["ok"] = p_ok;
	if (!p_error.is_empty()) {
		r["error"] = p_error;
	}
	return r;
}
bool integer(const Variant &p_value, int p_max) {
	return p_value.is_num() && Math::is_finite(double(p_value)) && double(p_value) >= 0 && double(p_value) <= p_max && double(p_value) == Math::floor(double(p_value));
}
} //namespace

bool AIChatEditorRuntimeActions::supports(const String &p_action) {
	return p_action == "capture_editor" || p_action == "game_input_state" || p_action == "game_input_query" || p_action == "game_action_pulse";
}

Dictionary AIChatEditorRuntimeActions::perform(const Dictionary &p_args, bool p_confirmed) {
	const String action = p_args.get("action", "");
	if (action == "capture_editor") {
		Viewport *viewport = EditorNode::get_singleton()->get_viewport();
		if (!viewport || !DisplayServer::get_singleton() || DisplayServer::get_singleton()->get_name() == "headless") {
			return result(false, "capture_renderer_unavailable");
		}
		Dictionary state;
		state["viewport_instance"] = int64_t(viewport->get_instance_id());
		Array size;
		size.push_back(viewport->get_visible_rect().size.x);
		size.push_back(viewport->get_visible_rect().size.y);
		state["size"] = size;
		Dictionary r = result(false);
		r["old_value"] = state;
		r["target_instance"] = int64_t(viewport->get_instance_id());
		r["new_value"] = "Capture editor viewport to a generated private PNG; excludes native menus, OS windows and embedded game overlays.";
		r["manual_confirmation_required"] = true;
		if (!p_confirmed) {
			r["confirmation_required"] = true;
			return r;
		}
		if (p_args.get("expected_target_instance", Variant()) != r["target_instance"] || p_args.get("expected_old_value", Variant()) != Variant(state)) {
			return result(false, "capture_changed_since_confirmation");
		}
		Ref<ViewportTexture> texture = viewport->get_texture();
		Ref<Image> image = texture.is_valid() ? texture->get_image() : Ref<Image>();
		if (image.is_null() || image->is_empty() || image->get_width() > 8192 || image->get_height() > 8192 || int64_t(image->get_width()) * image->get_height() > 32 * 1024 * 1024) {
			return result(false, "capture_image_unavailable");
		}
		if (viewport->is_using_hdr_2d()) {
			image->linear_to_srgb();
		}
		const String directory = "user://editor-command-captures";
		if (DirAccess::make_dir_recursive_absolute(directory) != OK) {
			return result(false, "capture_directory_failed");
		}
		const String path = directory.path_join(itos(OS::get_singleton()->get_process_id()) + "-" + uitos(OS::get_singleton()->get_ticks_usec()) + ".png");
		if (image->save_png(path) != OK) {
			return result(false, "capture_save_failed");
		}
		r = result(true);
		r["path"] = path;
		const String hash = FileAccess::get_sha256(path);
		if (hash.is_empty()) {
			return result(false, "capture_readback_failed");
		}
		r["sha256"] = hash;
		r["width"] = image->get_width();
		r["height"] = image->get_height();
		r["scope"] = "editor_viewport_only";
		r["business_completed"] = true;
		return r;
	}
	EditorDebuggerNode *debuggers = EditorDebuggerNode::get_singleton();
	const Variant raw_index = p_args.get("index", 0);
	if (!integer(raw_index, 31)) {
		return result(false, "invalid_game_session_index");
	}
	ScriptEditorDebugger *debugger = debuggers && int(raw_index) < debuggers->get_debugger_count() ? debuggers->get_debugger(int(raw_index)) : nullptr;
	if (!debugger || !debugger->is_session_active() || !EditorInterface::get_singleton()->is_playing_scene()) {
		return result(false, "game_session_unavailable");
	}
	const Dictionary state = debugger->get_semantic_input_state();
	if (action == "game_input_state") {
		Dictionary r = result(true);
		r["state"] = state;
		return r;
	}
	Dictionary request;
	request["editor_generation"] = state["generation"];
	if (action == "game_input_query") {
		request["operation"] = "query";
		request["request_id"] = "query-" + uitos(OS::get_singleton()->get_ticks_usec());
	} else if (action == "game_action_pulse") {
		const Variant raw_value = p_args.get("value", Variant());
		if (raw_value.get_type() != Variant::DICTIONARY) {
			return result(false, "invalid_game_action");
		}
		const Dictionary value = raw_value;
		const Variant name = value.get("name", Variant()), duration = value.get("duration", Variant()), strength = value.get("strength", 1.0), id = value.get("request_id", Variant());
		const Dictionary observation = state.get("receipt", Dictionary());
		if (name.get_type() != Variant::STRING || String(name).is_empty() || String(name).length() > 128 || id.get_type() != Variant::STRING || String(id).is_empty() || String(id).length() > 128 || !duration.is_num() || !Math::is_finite(double(duration)) || double(duration) < 0.01 || double(duration) > 2 || !strength.is_num() || !Math::is_finite(double(strength)) || double(strength) <= 0 || double(strength) > 1) {
			return result(false, "invalid_game_action");
		}
		const String token = observation.get("runtime_token", "");
		if (token.is_empty() || !observation.get("ok", false) || value.get("runtime_token", "") != token) {
			return result(false, "observed_game_runtime_required");
		}
		Dictionary r = result(false);
		r["target_instance"] = int64_t(debugger->get_instance_id());
		r["old_value"] = state;
		r["new_value"] = value.duplicate(true);
		r["manual_confirmation_required"] = true;
		if (!p_confirmed) {
			r["confirmation_required"] = true;
			return r;
		}
		if (p_args.get("expected_target_instance", Variant()) != r["target_instance"] || p_args.get("expected_old_value", Variant()) != Variant(state) || debugger->is_breaked()) {
			return result(false, "game_changed_since_confirmation");
		}
		request = value.duplicate(true);
		request["strength"] = strength;
		request["operation"] = "pulse";
		request["editor_generation"] = state["generation"];
	} else {
		return result(false, "unknown_runtime_action");
	}
	debugger->request_semantic_input(request);
	Dictionary r = result(true);
	r["requested"] = true;
	r["business_completed"] = false;
	r["readback_action"] = "game_input_state";
	return r;
}
