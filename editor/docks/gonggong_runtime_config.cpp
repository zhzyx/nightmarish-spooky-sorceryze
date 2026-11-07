/**************************************************************************/
/*  gonggong_runtime_config.cpp                                           */
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

#include "gonggong_runtime_config.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/mutex.h"
#include "core/os/os.h"
#include "editor/docks/gonggong_host_paths.h"
#include "editor/file_system/editor_paths.h"

#ifdef WINDOWS_ENABLED
#include <windows.h>
#elif defined(UNIX_ENABLED)
#include <fcntl.h>
#include <stdio.h>
#include <sys/file.h>
#include <unistd.h>
#endif

namespace {
Mutex runtime_mutex;
bool environment_captured = false;
Dictionary startup_overrides;
Dictionary runtime_defaults;
String startup_config;
const char *runtime_fields[] = { "node", "workflow_python", "build_python", "codex" };
const char *runtime_environment[] = { "GONGGONG_NODE", "GONGGONG_PYTHON", "GONGGONG_BUILD_PYTHON", "GONGGONG_CODEX" };

bool known_field(const String &p_field) {
	for (const char *field : runtime_fields) {
		if (p_field == field) {
			return true;
		}
	}
	return false;
}

bool executable_path(const String &p_path) {
	if (!p_path.is_absolute_path() || p_path.contains("://") || !FileAccess::exists(p_path)) {
		return false;
	}
#ifdef UNIX_ENABLED
	return (FileAccess::get_unix_permissions(p_path) & 0111) != 0;
#else
	return true;
#endif
}

// The stable lock inode is never replaced or removed with the JSON snapshot.
class RuntimeLock {
#ifdef WINDOWS_ENABLED
	HANDLE handle = INVALID_HANDLE_VALUE;
	OVERLAPPED position = {};
#elif defined(UNIX_ENABLED)
	int descriptor = -1;
#endif
	bool locked = false;

public:
	bool acquire(const String &p_file) {
		if (DirAccess::make_dir_recursive_absolute(p_file.get_base_dir()) != OK) {
			return false;
		}
#ifdef WINDOWS_ENABLED
		const Char16String name = p_file.replace("/", "\\").utf16();
		handle = CreateFileW((LPCWSTR)name.get_data(), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
		if (handle == INVALID_HANDLE_VALUE) {
			return false;
		}
#elif defined(UNIX_ENABLED)
		descriptor = ::open(p_file.utf8().get_data(), O_CREAT | O_RDWR | O_CLOEXEC, 0600);
		if (descriptor < 0) {
			return false;
		}
#else
		return false;
#endif
		const uint64_t deadline = OS::get_singleton()->get_ticks_msec() + 2000;
		do {
#ifdef WINDOWS_ENABLED
			locked = LockFileEx(handle, LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, &position) != 0;
#elif defined(UNIX_ENABLED)
			locked = ::flock(descriptor, LOCK_EX | LOCK_NB) == 0;
#endif
			if (locked) {
				return true;
			}
			OS::get_singleton()->delay_usec(10000);
		} while (OS::get_singleton()->get_ticks_msec() < deadline);
		return false;
	}

	~RuntimeLock() {
#ifdef WINDOWS_ENABLED
		if (handle != INVALID_HANDLE_VALUE) {
			if (locked) {
				UnlockFileEx(handle, 0, 1, 0, &position);
			}
			CloseHandle(handle);
		}
#elif defined(UNIX_ENABLED)
		if (descriptor >= 0) {
			if (locked) {
				::flock(descriptor, LOCK_UN);
			}
			::close(descriptor);
		}
#endif
	}
};

Error read_document(const String &p_file, Dictionary &r_document, String &r_error) {
	r_document["schema_version"] = 1;
	r_document["runtimes"] = Dictionary();
	if (!FileAccess::exists(p_file)) {
		return OK;
	}
	const Ref<FileAccess> file = FileAccess::open(p_file, FileAccess::READ);
	if (file.is_null() || file->get_length() > 64 * 1024) {
		r_error = "runtime_configuration_unreadable";
		return ERR_FILE_CANT_READ;
	}
	JSON json;
	if (json.parse(file->get_as_text()) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
		r_error = "runtime_configuration_invalid";
		return ERR_FILE_CORRUPT;
	}
	const Dictionary document = json.get_data();
	const Variant version = document.get("schema_version", Variant());
	if ((version.get_type() != Variant::INT && version.get_type() != Variant::FLOAT) || double(version) != 1.0 || document.get("runtimes", Variant()).get_type() != Variant::DICTIONARY) {
		r_error = "runtime_configuration_version_unsupported";
		return ERR_FILE_CORRUPT;
	}
	const Dictionary paths = document["runtimes"];
	for (const Variant &name : paths.keys()) {
		if (name.get_type() != Variant::STRING || !known_field(name) || paths[name].get_type() != Variant::STRING || String(paths[name]).length() > 32768) {
			r_error = "runtime_configuration_invalid";
			return ERR_FILE_CORRUPT;
		}
	}
	r_document = document;
	return OK;
}

Error write_document(const String &p_file, const Dictionary &p_document, String &r_error) {
	const String payload = JSON::stringify(p_document, "\t") + "\n";
	if (payload.utf8().length() > 64 * 1024) {
		r_error = "runtime_configuration_too_large";
		return ERR_PARAMETER_RANGE_ERROR;
	}
	const String temporary = p_file + ".tmp-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(OS::get_singleton()->get_ticks_usec());
	Ref<FileAccess> file = FileAccess::open(temporary, FileAccess::WRITE);
	if (file.is_null()) {
		r_error = "runtime_configuration_write_failed";
		return ERR_FILE_CANT_WRITE;
	}
	file->store_string(payload);
	file->flush();
	const Error stored = file->get_error();
	file.unref();
	bool replaced = false;
	if (stored == OK) {
#ifdef WINDOWS_ENABLED
		const Char16String from = temporary.replace("/", "\\").utf16();
		const Char16String to = p_file.replace("/", "\\").utf16();
		replaced = MoveFileExW((LPCWSTR)from.get_data(), (LPCWSTR)to.get_data(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#elif defined(UNIX_ENABLED)
		replaced = ::rename(temporary.utf8().get_data(), p_file.utf8().get_data()) == 0;
#endif
	}
	if (!replaced) {
		DirAccess::remove_absolute(temporary);
		r_error = "runtime_configuration_replace_failed";
		return ERR_FILE_CANT_WRITE;
	}
	return OK;
}

Error update_file(const String &p_file, const String &p_field, const String &p_value, String &r_error) {
	if (!known_field(p_field) || p_value.length() > 32768) {
		r_error = "runtime_configuration_field_invalid";
		return ERR_INVALID_PARAMETER;
	}
	GongGongRuntimeConfig::FileLock lock;
	if (p_file.is_empty() || !lock.acquire(p_file + ".lock")) {
		r_error = "runtime_configuration_busy";
		return ERR_BUSY;
	}
	Dictionary document;
	const Error read = read_document(p_file, document, r_error);
	if (read != OK) {
		return read;
	}
	Dictionary paths = document["runtimes"];
	paths[p_field] = p_value.strip_edges();
	return write_document(p_file, document, r_error);
}
} // namespace

GongGongRuntimeConfig::FileLock::FileLock() {
	implementation = memnew(RuntimeLock);
}

GongGongRuntimeConfig::FileLock::~FileLock() {
	memdelete(static_cast<RuntimeLock *>(implementation));
}

bool GongGongRuntimeConfig::FileLock::acquire(const String &p_lock_file) {
	return static_cast<RuntimeLock *>(implementation)->acquire(p_lock_file);
}

Error GongGongRuntimeConfig::update_file_at(const String &p_configuration, const String &p_field, const String &p_value) {
	String error;
	return update_file(p_configuration, p_field, p_value, error);
}

void GongGongRuntimeConfig::initialize() {
	MutexLock guard(runtime_mutex);
	if (environment_captured) {
		return;
	}
	const String derived_text = OS::get_singleton()->get_environment("GONGGONG_RUNTIME_DERIVED_ENV");
	JSON derived_json;
	const Variant derived_value = !derived_text.is_empty() && derived_text.length() <= 64 * 1024 && derived_json.parse(derived_text) == OK ? derived_json.get_data() : Variant();
	const Dictionary derived = derived_value.get_type() == Variant::DICTIONARY ? Dictionary(derived_value) : Dictionary();
	for (int i = 0; i < 4; i++) {
		const String value = OS::get_singleton()->get_environment(runtime_environment[i]).strip_edges();
		if (!value.is_empty() && derived.get(runtime_fields[i], Variant()) != Variant(value)) {
			startup_overrides[runtime_fields[i]] = value;
		}
	}
	const bool windows = OS::get_singleton()->get_name() == "Windows";
	for (const String &directory : OS::get_singleton()->get_environment("PATH").split(windows ? ";" : ":")) {
		const String node = directory.path_join(windows ? "node.exe" : "node");
		if (executable_path(node)) {
			runtime_defaults["node"] = node;
			break;
		}
	}
	const String source = GongGongHostPaths::engine_source();
	if (!source.is_empty()) {
		const String build_python = source.path_join(windows ? ".venv/Scripts/python.exe" : ".venv/bin/python");
		if (executable_path(build_python)) {
			runtime_defaults["build_python"] = build_python;
		}
		const String workflow_python = source.path_join("project/runtime/python/python.exe");
		if (executable_path(workflow_python)) {
			runtime_defaults["workflow_python"] = workflow_python;
		}
	}
	startup_config = OS::get_singleton()->get_environment("GONGGONG_RUNTIME_CONFIG").strip_edges();
	environment_captured = true;
}

String GongGongRuntimeConfig::configuration_path() {
	initialize();
	// No file access until the editor has resolved its self-contained scope.
	if (!EditorPaths::get_singleton()) {
		return String();
	}
	if (EditorPaths::get_singleton()->is_self_contained()) {
		return EditorPaths::get_singleton()->get_config_dir().path_join("gonggong/config.json");
	}
	if (startup_config.is_absolute_path() && !startup_config.contains("://")) {
		return startup_config;
	}
	const String directory = OS::get_singleton()->get_config_path();
	return directory.is_absolute_path() ? directory.path_join("gonggong/config.json") : String();
}

Dictionary GongGongRuntimeConfig::read_effective() {
	const String file = configuration_path();
	Dictionary snapshot;
	snapshot["config_path"] = file;
	snapshot["schema_version"] = 1;
	Dictionary document;
	String error;
	GongGongRuntimeConfig::FileLock lock;
	const bool locked = !file.is_empty() && lock.acquire(file + ".lock");
	const Error result = locked ? read_document(file, document, error) : ERR_BUSY;
	if (!locked) {
		error = "runtime_configuration_busy";
	}
	snapshot["ok"] = result == OK;
	snapshot["error"] = error;
	Dictionary paths;
	Dictionary sources;
	const Dictionary configured = document.get("runtimes", Dictionary());
	for (const char *name : runtime_fields) {
		const bool external = startup_overrides.has(name);
		paths[name] = external ? startup_overrides[name] : configured.get(name, runtime_defaults.get(name, ""));
		sources[name] = external ? "environment" : configured.has(name) ? "configuration"
				: runtime_defaults.has(name)							? "default"
																		: "missing";
	}
	snapshot["paths"] = paths;
	snapshot["sources"] = sources;
	snapshot["configured"] = configured;
	Dictionary executables;
	for (const char *name : runtime_fields) {
		executables[name] = path(snapshot, name);
	}
	snapshot["executables"] = executables;
	return snapshot;
}

String GongGongRuntimeConfig::path(const Dictionary &p_snapshot, const String &p_field) {
	if (!bool(p_snapshot.get("ok", false)) || !known_field(p_field)) {
		return String();
	}
	const Dictionary paths = p_snapshot.get("paths", Dictionary());
	const String value = String(paths.get(p_field, "")).strip_edges();
	return executable_path(value) ? value : String();
}

Dictionary GongGongRuntimeConfig::metadata(const Dictionary &p_snapshot) {
	Dictionary result;
	result["source"] = "current_host";
	result["schema_version"] = 1;
	Dictionary entries;
	const Dictionary sources = p_snapshot.get("sources", Dictionary());
	for (const char *name : runtime_fields) {
		Dictionary entry;
		const String value = path(p_snapshot, name);
		entry["path"] = value.is_empty() ? Variant() : Variant(value);
		entry["version"] = Variant();
		entry["source"] = sources.get(name, "missing");
		entries[name] = entry;
	}
	result["runtimes"] = entries;
	return result;
}

Error GongGongRuntimeConfig::update_field(const String &p_field, const String &p_value, String &r_error) {
	return update_file(configuration_path(), p_field, p_value, r_error);
}

Error GongGongRuntimeConfig::migrate_legacy(const Dictionary &p_legacy, String &r_error) {
	const String file = configuration_path();
	GongGongRuntimeConfig::FileLock lock;
	if (file.is_empty() || !lock.acquire(file + ".lock")) {
		r_error = "runtime_configuration_busy";
		return ERR_BUSY;
	}
	Dictionary document;
	const Error read = read_document(file, document, r_error);
	if (read != OK) {
		return read;
	}
	Dictionary paths = document["runtimes"];
	bool changed = false;
	for (const char *name : runtime_fields) {
		const Variant legacy = p_legacy.get(name, Variant());
		if (!paths.has(name) && legacy.get_type() == Variant::STRING && executable_path(legacy)) {
			paths[name] = String(legacy).strip_edges();
			changed = true;
		}
	}
	return changed ? write_document(file, document, r_error) : OK;
}

void GongGongRuntimeConfig::prepare_child_environment(const Dictionary &p_snapshot) {
	initialize();
	// Resolution uses the frozen startup overrides, never these derived values.
	OS::get_singleton()->set_environment("GONGGONG_RUNTIME_CONFIG", String(p_snapshot.get("config_path", "")));
	Dictionary derived;
	const Dictionary paths = p_snapshot.get("paths", Dictionary());
	const Dictionary sources = p_snapshot.get("sources", Dictionary());
	for (int i = 0; i < 4; i++) {
		const bool external = sources.get(runtime_fields[i], "") == "environment";
		const String value = external ? String(paths.get(runtime_fields[i], "")) : path(p_snapshot, runtime_fields[i]);
		if (!value.is_empty()) {
			OS::get_singleton()->set_environment(runtime_environment[i], value);
			if (!external) {
				derived[runtime_fields[i]] = value;
			}
		} else {
			OS::get_singleton()->unset_environment(runtime_environment[i]);
		}
	}
	OS::get_singleton()->set_environment("GONGGONG_RUNTIME_DERIVED_ENV", JSON::stringify(derived));
}
