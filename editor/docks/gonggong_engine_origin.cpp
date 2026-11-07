/**************************************************************************/
/*  gonggong_engine_origin.cpp                                            */
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

#include "gonggong_engine_origin.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"

namespace {
String text_field(const Dictionary &p_value, const String &p_key) {
	const Variant value = p_value.get(p_key, Variant());
	return value.get_type() == Variant::STRING ? String(value) : String();
}

Dictionary read_object(const String &p_file, uint64_t p_limit) {
	Ref<FileAccess> file = FileAccess::open(p_file, FileAccess::READ);
	if (file.is_null() || file->get_length() > p_limit) {
		return Dictionary();
	}
	JSON json;
	if (json.parse(file->get_as_text()) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
		return Dictionary();
	}
	return json.get_data();
}

String directory(const String &p_path) {
	Ref<DirAccess> access = DirAccess::open(p_path);
	return access.is_valid() ? access->get_current_dir() : String();
}

String common_directory(const String &p_source) {
	String git = p_source.path_join(".git");
	if (!DirAccess::dir_exists_absolute(git)) {
		const String pointer = FileAccess::get_file_as_string(git).strip_edges();
		if (!pointer.begins_with("gitdir: ")) {
			return String();
		}
		git = pointer.trim_prefix("gitdir: ").strip_edges();
		if (!git.is_absolute_path()) {
			git = p_source.path_join(git).simplify_path();
		}
	}
	if (FileAccess::exists(git.path_join("commondir"))) {
		git = git.path_join(FileAccess::get_file_as_string(git.path_join("commondir")).strip_edges()).simplify_path();
	}
	return directory(git);
}

bool source_matches(const String &p_root, const Dictionary &p_manifest) {
	const Variant raw_inputs = p_manifest.get("source_inputs", Variant());
	if (raw_inputs.get_type() != Variant::DICTIONARY || Dictionary(raw_inputs).is_empty()) {
		return false;
	}
	const Dictionary inputs = raw_inputs;
	for (const Variant &key : inputs.keys()) {
		if (key.get_type() != Variant::STRING || inputs[key].get_type() != Variant::DICTIONARY) {
			return false;
		}
		const String name = key;
		if (name.is_absolute_path() || name.split("/").has("..") || name.contains("\\")) {
			return false;
		}
		const Dictionary expected = inputs[key];
		const String path = p_root.path_join(name);
		if (expected.get("absent", Variant()).get_type() == Variant::BOOL && bool(expected["absent"])) {
			if (FileAccess::exists(path) || DirAccess::dir_exists_absolute(path)) {
				return false;
			}
		} else if (!FileAccess::exists(path) || FileAccess::get_sha256(path) != text_field(expected, "sha256")) {
			return false;
		}
	}
	return true;
}

Dictionary read_origin() {
	Dictionary result;
	result["managed"] = false;
	result["ok"] = false;
	const String resources = OS::get_singleton()->get_bundle_resource_dir();
	const String locator_file = resources.path_join("gonggong_engine_origin.json");
	if (resources.is_empty() || !FileAccess::exists(locator_file)) {
		return result;
	}
	result["managed"] = true;
	result["error"] = "engine_origin_locator_invalid";
	const Dictionary locator = read_object(locator_file, 64 * 1024);
	const String source = text_field(locator, "source_root");
	const String manifest_file = text_field(locator, "candidate_manifest");
	const String binding_file = text_field(locator, "binding_path");
	const Variant version = locator.get("schema_version", Variant());
	if ((version.get_type() != Variant::INT && version.get_type() != Variant::FLOAT) || double(version) != 1.0 || !source.is_absolute_path() || directory(source) != source || !FileAccess::exists(source.path_join("SConstruct")) || !manifest_file.is_absolute_path() || manifest_file.get_base_dir() != source.path_join("bin")) {
		return result;
	}
	const String common = common_directory(source);
	if (common.is_empty() || binding_file.get_base_dir() != common.path_join("gonggong-engine-candidates")) {
		result["error"] = "engine_origin_binding_location_invalid";
		return result;
	}
	const Dictionary manifest = read_object(manifest_file, 16 * 1024 * 1024);
	const Dictionary trusted = read_object(binding_file, 16 * 1024 * 1024);
	if (manifest.get("binding", Variant()).get_type() != Variant::DICTIONARY || trusted.get("state", "") != Variant("prepared") || text_field(trusted, "artifact_manifest") != manifest_file) {
		result["error"] = "engine_origin_binding_record_invalid";
		return result;
	}
	const Dictionary binding = manifest["binding"];
	for (const String &name : { String("source_root"), String("common_dir"), String("repository"), String("issue"), String("request_id"), String("owner"), String("branch"), String("base_sha"), String("initial_launch_executable") }) {
		if (!trusted.has(name) || trusted[name] != binding.get(name, Variant())) {
			result["error"] = "engine_origin_binding_changed:" + name;
			return result;
		}
	}
	const String project = text_field(locator, "project_root");
	if (text_field(binding, "source_root") != source || text_field(binding, "common_dir") != common || text_field(binding, "binding_path") != binding_file || !project.is_absolute_path() || project != text_field(manifest, "project_root") || !FileAccess::exists(project.path_join("project.godot"))) {
		result["error"] = "engine_origin_project_changed";
		return result;
	}
	const String expected_hash = text_field(manifest, "artifact_sha256");
	if (expected_hash.length() != 64 || FileAccess::get_sha256(OS::get_singleton()->get_executable_path()) != expected_hash) {
		result["error"] = "engine_origin_artifact_changed";
		return result;
	}
	if (!source_matches(source, manifest)) {
		result["error"] = "engine_origin_source_changed";
		return result;
	}
	result["ok"] = true;
	result["error"] = "";
	result["source_root"] = source;
	result["project_root"] = project;
	result["candidate_manifest"] = manifest_file;
	return result;
}
} // namespace

Dictionary GongGongEngineOrigin::read() {
	// The installed candidate remains fixed for this process. Tool permissions
	// and active Issue bindings are still checked by their existing entry points.
	static const Dictionary origin = read_origin();
	return origin;
}

String GongGongEngineOrigin::source_root() {
	const Dictionary origin = read();
	return bool(origin.get("ok", false)) ? String(origin.get("source_root", "")) : String();
}

bool GongGongEngineOrigin::uses_default_project(const List<String> &p_arguments) {
#ifdef MACOS_ENABLED
	for (const String &argument : p_arguments) {
		// Main already ignores this Launch Services/Gatekeeper bookkeeping.
		if (argument.begins_with("-psn_")) {
			continue;
		}
		return false;
	}
	return true;
#else
	return p_arguments.is_empty();
#endif
}
