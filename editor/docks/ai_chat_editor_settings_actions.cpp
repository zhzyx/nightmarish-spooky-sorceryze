/**************************************************************************/
/*  ai_chat_editor_settings_actions.cpp                                   */
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

#include "ai_chat_editor_settings_actions.h"

#include "core/config/project_settings.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/io/resource_saver.h"
#include "core/math/math_funcs.h"
#include "editor/docks/ai_chat_editor_control.h"
#include "editor/docks/ai_chat_tools.h"
#include "editor/settings/editor_settings.h"

namespace {
Dictionary result(bool p_ok, const String &p_error = String()) {
	Dictionary r;
	r["ok"] = p_ok;
	if (!p_error.is_empty()) {
		r["error"] = p_error;
	}
	return r;
}

bool safe_editor_key(const String &p_key) {
	return AIChatEditorSettingsActions::allowed_project_key(p_key) && (p_key.begins_with("interface/theme/") || p_key == "interface/editor/appearance/display_scale" || p_key == "interface/editor/appearance/custom_display_scale" || p_key == "interface/editor/localization/editor_language" || p_key == "interface/editor/localization/localize_settings" || p_key == "interface/editor/fonts/main_font" || p_key == "interface/editor/fonts/main_font_bold" || p_key == "interface/editor/fonts/code_font" || p_key.begins_with("text_editor/theme/") || p_key.begins_with("text_editor/appearance/"));
}

Variant wire(const Variant &p_value) {
	Array a;
	if (p_value.get_type() == Variant::VECTOR2) {
		Vector2 v = p_value;
		a.push_back(v.x);
		a.push_back(v.y);
	} else if (p_value.get_type() == Variant::VECTOR2I) {
		Vector2i v = p_value;
		a.push_back(v.x);
		a.push_back(v.y);
	} else if (p_value.get_type() == Variant::VECTOR3) {
		Vector3 v = p_value;
		a.push_back(v.x);
		a.push_back(v.y);
		a.push_back(v.z);
	} else if (p_value.get_type() == Variant::VECTOR3I) {
		Vector3i v = p_value;
		a.push_back(v.x);
		a.push_back(v.y);
		a.push_back(v.z);
	} else if (p_value.get_type() == Variant::COLOR) {
		Color v = p_value;
		a.push_back(v.r);
		a.push_back(v.g);
		a.push_back(v.b);
		a.push_back(v.a);
	} else {
		return p_value;
	}
	return a;
}

bool convert(const Variant &p_value, Variant::Type p_type, Variant &r_value) {
	if (JSON::stringify(p_value).utf8().length() > 8192) {
		return false;
	}
	if (p_type == Variant::INT && p_value.is_num() && Math::is_finite(double(p_value)) && double(p_value) == Math::floor(double(p_value)) && Math::abs(double(p_value)) <= 9007199254740991.0) {
		r_value = int64_t(p_value);
		return true;
	}
	if (p_type == Variant::FLOAT && p_value.is_num() && Math::is_finite(double(p_value))) {
		r_value = double(p_value);
		return true;
	}
	if ((p_type == Variant::BOOL || p_type == Variant::STRING || p_type == Variant::ARRAY || p_type == Variant::DICTIONARY) && p_value.get_type() == p_type) {
		r_value = p_value;
		return true;
	}
	if (p_type == Variant::STRING_NAME && p_value.get_type() == Variant::STRING) {
		r_value = StringName(String(p_value));
		return true;
	}
	const int count = p_type == Variant::VECTOR2 || p_type == Variant::VECTOR2I ? 2 : p_type == Variant::VECTOR3 || p_type == Variant::VECTOR3I ? 3
			: p_type == Variant::COLOR																											? 4
																																				: 0;
	if (!count || p_value.get_type() != Variant::ARRAY || Array(p_value).size() != count) {
		return false;
	}
	const Array a = p_value;
	for (const Variant &v : a) {
		if (!v.is_num() || !Math::is_finite(double(v)) || Math::abs(double(v)) > 1000000000.0 || ((p_type == Variant::VECTOR2I || p_type == Variant::VECTOR3I) && double(v) != Math::floor(double(v)))) {
			return false;
		}
	}
	switch (p_type) {
		case Variant::VECTOR2:
			r_value = Vector2(a[0], a[1]);
			break;
		case Variant::VECTOR2I:
			r_value = Vector2i(int(a[0]), int(a[1]));
			break;
		case Variant::VECTOR3:
			r_value = Vector3(a[0], a[1], a[2]);
			break;
		case Variant::VECTOR3I:
			r_value = Vector3i(int(a[0]), int(a[1]), int(a[2]));
			break;
		case Variant::COLOR:
			r_value = Color(a[0], a[1], a[2], a[3]);
			break;
		default:
			return false;
	}
	return true;
}
} // namespace

bool AIChatEditorSettingsActions::allowed_project_key(const String &p_key) {
	if (p_key.is_empty() || p_key.length() > 256 || !p_key.contains("/") || p_key.contains("..") || p_key.contains("\\") || p_key.contains(":")) {
		return false;
	}
	const String key = p_key.to_lower().replace("_", "").replace("-", "").replace("/", "");
	return !key.contains("password") && !key.contains("credential") && !key.contains("apikey") && !key.contains("token") && !key.contains("secret") && !key.contains("authentication");
}

bool AIChatEditorSettingsActions::supports(const String &p_action) {
	return p_action == "get_project_setting" || p_action == "get_editor_setting" || p_action == "create_project_setting" || p_action == "update_project_setting" || p_action == "set_editor_setting" || p_action == "reset_editor_setting";
}

Dictionary AIChatEditorSettingsActions::perform(const Dictionary &p_args, bool p_confirmed) {
	const String action = p_args.get("action", ""), key = p_args.get("target", "");
	const bool editor = action.contains("editor_setting"), read = action.begins_with("get_"), create = action == "create_project_setting";
	if (!supports(action) || !(editor ? safe_editor_key(key) : allowed_project_key(key))) {
		return result(false, "protected_setting");
	}
	Object *settings = editor ? static_cast<Object *>(EditorSettings::get_singleton()) : static_cast<Object *>(ProjectSettings::get_singleton());
	if (!settings) {
		return result(false, "settings_unavailable");
	}
	const bool exists = editor ? EditorSettings::get_singleton()->has_setting(key) : ProjectSettings::get_singleton()->has_setting(key);
	if ((!exists && !create) || (exists && create)) {
		return result(false, exists ? "setting_already_exists" : "unknown_setting");
	}
	const Variant previous = exists ? settings->get(key) : Variant();
	const String path = editor ? EditorSettings::get_singleton()->get_path() : ProjectSettings::get_singleton()->get_resource_path().path_join("project.godot");
	Ref<DirAccess> directory = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
	if (directory->is_link(path) || !FileAccess::exists(path)) {
		return result(false, "settings_file_unavailable");
	}
	const Variant previous_wire = wire(previous);
	if (JSON::stringify(previous_wire).utf8().length() > 16384 || previous.get_type() == Variant::OBJECT || previous.get_type() == Variant::CALLABLE || previous.get_type() == Variant::SIGNAL) {
		return result(false, "setting_value_unavailable");
	}
	Dictionary state;
	state["exists"] = exists;
	state["value"] = previous_wire;
	state["value_type"] = Variant::get_type_name(previous.get_type());
	state["file_sha256"] = FileAccess::get_sha256(path);
	if (read) {
		Dictionary r = result(true);
		r["value"] = previous_wire;
		r["value_type"] = state["value_type"];
		return r;
	}
	Variant value;
	Variant::Type type = previous.get_type();
	if (create) {
		const String type_name = p_args.get("value_type", "");
		type = Variant::NIL;
		for (Variant::Type candidate : { Variant::BOOL, Variant::INT, Variant::FLOAT, Variant::STRING, Variant::ARRAY, Variant::DICTIONARY, Variant::VECTOR2, Variant::VECTOR2I, Variant::VECTOR3, Variant::VECTOR3I, Variant::COLOR }) {
			if (Variant::get_type_name(candidate) == type_name) {
				type = candidate;
			}
		}
	}
	if (action == "reset_editor_setting") {
		if (!settings->property_can_revert(key)) {
			return result(false, "setting_revert_unavailable");
		}
		value = settings->property_get_revert(key);
	} else if (!convert(p_args.get("value", Variant()), type, value)) {
		return result(false, "setting_type_mismatch");
	}
	Dictionary r = result(false);
	r["old_value"] = state;
	r["new_value"] = wire(value);
	r["target"] = key;
	r["target_instance"] = int64_t(settings->get_instance_id());
	if (!p_confirmed) {
		r["confirmation_required"] = true;
		return r;
	}
	if (p_args.get("expected_target_instance", Variant()).get_type() != Variant::INT || int64_t(p_args["expected_target_instance"]) != int64_t(settings->get_instance_id()) || !p_args.has("expected_old_value") || p_args["expected_old_value"] != Variant(state)) {
		return result(false, "setting_changed_since_confirmation");
	}
	if (editor) {
		EditorSettings *editor_settings = EditorSettings::get_singleton();
		editor_settings->set_setting(key, value);
		Ref<EditorSettings> resource = editor_settings;
		const Error saved = ResourceSaver::save(resource);
		if (saved != OK) {
			editor_settings->set_setting(key, previous);
			return result(false, "save_failed");
		}
	} else {
		String original, error;
		if (!AIChatTools::read_script(path, original, error) || !AIChatEditorControl::save_setting_snapshot(path, original, key, value, error)) {
			return result(false, "save_failed");
		}
		ProjectSettings::get_singleton()->set_setting(key, value);
	}
	r["ok"] = true;
	r["saved"] = true;
	r["value_type"] = Variant::get_type_name(value.get_type());
	return r;
}
