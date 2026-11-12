/**************************************************************************/
/*  test_runtime_config.cpp                                               */
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

#include "tests/test_macros.h"

TEST_FORCE_LINK(test_runtime_config)

#ifdef TOOLS_ENABLED
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_host_runtime.h"
#include "editor/docks/gonggong_engine_origin.h"
#include "editor/docks/gonggong_runtime_config.h"
#include "editor/file_system/editor_paths.h"

TEST_CASE("[Editor][AIChat] Ready build validates the reported sibling manifest before trusting its contents") {
	const String executable = OS::get_singleton()->get_executable_path().get_base_dir().path_join("missing-ready-test.exe");
	const String manifest = AIChatHostRuntime::candidate_manifest_path(executable);
	String error;
	CHECK_FALSE(AIChatHostRuntime::ready_artifact_matches(executable, Variant(), Dictionary(), error));
	CHECK(error == "candidate_artifact_manifest_path_mismatch");
	CHECK_FALSE(AIChatHostRuntime::ready_artifact_matches(executable, manifest + ".other", Dictionary(), error));
	CHECK(error == "candidate_artifact_manifest_path_mismatch");
	CHECK_FALSE(AIChatHostRuntime::ready_artifact_matches(executable, manifest, Dictionary(), error));
	CHECK(error == "candidate_artifact_manifest_missing");
	CHECK_FALSE(AIChatHostRuntime::ready_artifact_matches(executable, manifest.replace_char('/', '\\'), Dictionary(), error));
#ifdef WINDOWS_ENABLED
	CHECK(error == "candidate_artifact_manifest_missing");
#else
	CHECK(error == "candidate_artifact_manifest_path_mismatch");
#endif
}

TEST_CASE("[Editor][AIChat] Recorded candidate directory preserves identity across native path separators") {
	const String path = AIChatHostRuntime::canonical_directory(OS::get_singleton()->get_executable_path().get_base_dir());
	REQUIRE_FALSE(path.is_empty());
	CHECK(AIChatHostRuntime::matches_recorded_directory(path, path));
#ifdef WINDOWS_ENABLED
	CHECK(AIChatHostRuntime::matches_recorded_directory(path, path.replace_char('/', '\\')));
#endif
	CHECK_FALSE(AIChatHostRuntime::matches_recorded_directory(path, path + "-another"));
	CHECK_FALSE(AIChatHostRuntime::matches_recorded_directory(path, path.path_join("..")));

	// An opt-in host receipt exercises the actual native checkout guard without dispatching a model.
	const String receipt = OS::get_singleton()->get_environment("GONGGONG_TEST_CANDIDATE_RECEIPT");
	if (!receipt.is_empty()) {
		Dictionary candidate = JSON::parse_string(FileAccess::get_file_as_string(receipt));
		String error;
		REQUIRE_MESSAGE(AIChatHostRuntime::validate_candidate_checkout(candidate, error), error.utf8().get_data());
		const String branch = candidate["branch"];
		candidate["branch"] = branch + "-different";
		CHECK_FALSE(AIChatHostRuntime::validate_candidate_checkout(candidate, error));
		CHECK(error.begins_with("candidate_branch_changed"));
		candidate["branch"] = branch;
		candidate["common_dir"] = path;
		CHECK_FALSE(AIChatHostRuntime::validate_candidate_checkout(candidate, error));
		CHECK(error.begins_with("candidate_repository_or_base_changed"));
	}
	const String game_receipt = OS::get_singleton()->get_environment("GONGGONG_TEST_GAME_CANDIDATE_RECEIPT");
	if (!game_receipt.is_empty()) {
		const Dictionary game = JSON::parse_string(FileAccess::get_file_as_string(game_receipt));
		String error;
		const String game_common = AIChatHostRuntime::checkout_common_directory(game["source_root"]);
		CHECK(game_common == String(game["common_dir"]));
		CHECK_FALSE(AIChatHostRuntime::validate_candidate_checkout(game, error));
		CHECK(error.begins_with("candidate_source_changed"));
		REQUIRE_MESSAGE(AIChatHostRuntime::validate_candidate_checkout(game, error, false), error.utf8().get_data());
		Dictionary changed = game.duplicate(true);
		changed["common_dir"] = path;
		CHECK_FALSE(AIChatHostRuntime::validate_candidate_checkout(changed, error, false));
		CHECK(error.begins_with("candidate_repository_or_base_changed"));
		changed = game.duplicate(true);
		changed["branch"] = String(game["branch"]) + "-different";
		CHECK_FALSE(AIChatHostRuntime::validate_candidate_checkout(changed, error, false));
		CHECK(error.begins_with("candidate_branch_changed"));
		changed = game.duplicate(true);
		changed["base_sha"] = "0000000000000000000000000000000000000000";
		CHECK_FALSE(AIChatHostRuntime::validate_candidate_checkout(changed, error, false));
		CHECK(error.begins_with("candidate_repository_or_base_changed"));
	}
}

class RuntimeConfigTestAccess {
public:
	static Error update_file(const String &p_file, const String &p_field, const String &p_value) {
		return GongGongRuntimeConfig::update_file_at(p_file, p_field, p_value);
	}
};

namespace TestRuntimeConfig {
Error native_lock(const String &p_configuration, const Callable &p_callback) {
	GongGongRuntimeConfig::FileLock lock;
	if (!lock.acquire(p_configuration + ".lock")) {
		return ERR_BUSY;
	}
	if (p_callback.is_valid()) {
		p_callback.call();
	}
	return OK;
}
bool wait_for_file(const String &p_file) {
	const uint64_t deadline = OS::get_singleton()->get_ticks_msec() + 7000;
	while (!FileAccess::exists(p_file) && OS::get_singleton()->get_ticks_msec() < deadline) {
		OS::get_singleton()->delay_usec(10000);
	}
	return FileAccess::exists(p_file);
}

void write_file(const String &p_path, const String &p_text) {
	Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::WRITE);
	REQUIRE(file.is_valid());
	file->store_string(p_text);
}

struct LockProbe : public Object {
	String directory;
	String mode;
	ProcessID pid = 0;
	bool started = false;

	void start() {
		const String config = directory.path_join("configuration.json");
		if (mode == "read") {
			Ref<FileAccess> lock = FileAccess::open(config + ".lock", FileAccess::READ);
			REQUIRE(lock.is_valid());
			CHECK(lock->get_length() == 0);
		}
		const String script = directory.path_join("lock_probe.py");
		write_file(script,
				"import importlib.util,json,pathlib,sys,time\n"
				"root=pathlib.Path(sys.argv[1]); config=root/'configuration.json'\n"
				"spec=importlib.util.spec_from_file_location('runtime',sys.argv[2]); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
				"if sys.argv[3]=='read':\n"
				" (root/'started').write_text('started'); result=module.read_effective(config,env={'PATH':''})\n"
				" (root/'done').write_text(json.dumps({'ok':result['ok']}))\n"
				"else:\n"
				" with module.locked(config):\n"
				"  (root/'started').write_text('locked'); deadline=time.monotonic()+7\n"
				"  while not (root/'release').exists() and time.monotonic()<deadline:time.sleep(.01)\n"
				" (root/'done').write_text('released')\n");
		String python = OS::get_singleton()->get_environment("GONGGONG_TEST_PYTHON");
		if (python.is_empty()) {
			python = OS::get_singleton()->get_name() == "Windows" ? "python.exe" : "python3";
		}
		List<String> args;
		for (const String &arg : { script, directory, OS::get_singleton()->get_cwd().path_join("tools/gonggong_runtime_config.py"), mode }) {
			args.push_back(arg);
		}
		REQUIRE(OS::get_singleton()->create_process(python, args, &pid) == OK);
		started = wait_for_file(directory.path_join("started"));
		CHECK(started);
		if (mode == "read") {
			OS::get_singleton()->delay_usec(200000);
			CHECK_FALSE(FileAccess::exists(directory.path_join("done")));
		}
	}

	void finish() {
		CHECK(wait_for_file(directory.path_join("done")));
		const uint64_t deadline = OS::get_singleton()->get_ticks_msec() + 3000;
		while (pid > 0 && OS::get_singleton()->is_process_running(pid) && OS::get_singleton()->get_ticks_msec() < deadline) {
			OS::get_singleton()->delay_usec(10000);
		}
		if (pid > 0 && OS::get_singleton()->is_process_running(pid)) {
			OS::get_singleton()->kill(pid);
			FAIL_CHECK("owned lock fixture did not exit");
		}
	}
};

TEST_CASE("[Editor][RuntimeConfig] Native-first empty lock waits in the Python reader") {
	Error error = OK;
	Ref<DirAccess> temporary = DirAccess::create_temp("runtime_config_共工 space", false, &error);
	REQUIRE(error == OK);
	LockProbe probe;
	probe.directory = temporary->get_current_dir();
	probe.mode = "read";
	CHECK(native_lock(probe.directory.path_join("configuration.json"), callable_mp(&probe, &LockProbe::start)) == OK);
	probe.finish();
	const Variant value = JSON::parse_string(FileAccess::get_file_as_string(probe.directory.path_join("done")));
	REQUIRE(value.get_type() == Variant::DICTIONARY);
	CHECK(bool(Dictionary(value).get("ok", false)));
}

TEST_CASE("[Editor][RuntimeConfig] Python-first lock blocks native and releases after process exit") {
	Error error = OK;
	Ref<DirAccess> temporary = DirAccess::create_temp("runtime_config_python_first", false, &error);
	REQUIRE(error == OK);
	LockProbe probe;
	probe.directory = temporary->get_current_dir();
	probe.mode = "hold";
	probe.start();
	REQUIRE(probe.started);
	const String config = probe.directory.path_join("configuration.json");
	CHECK(native_lock(config, Callable()) == ERR_BUSY);
	write_file(probe.directory.path_join("release"), "release");
	probe.finish();
	CHECK(native_lock(config, Callable()) == OK);
}

TEST_CASE("[Editor][RuntimeConfig] Native field replacement preserves other fields and invalid input") {
	Error error = OK;
	Ref<DirAccess> temporary = DirAccess::create_temp("runtime_config_merge", false, &error);
	REQUIRE(error == OK);
	const String config = temporary->get_current_dir().path_join("configuration.json");
	CHECK(RuntimeConfigTestAccess::update_file(config, "node", "node A") == OK);
	CHECK(RuntimeConfigTestAccess::update_file(config, "codex", "codex B") == OK);
	Dictionary document = JSON::parse_string(FileAccess::get_file_as_string(config));
	Dictionary paths = document["runtimes"];
	CHECK(String(paths["node"]) == "node A");
	CHECK(String(paths["codex"]) == "codex B");
	CHECK(RuntimeConfigTestAccess::update_file(config, "credential", "do not store") == ERR_INVALID_PARAMETER);
	const String before = FileAccess::get_file_as_string(config);
	CHECK(RuntimeConfigTestAccess::update_file(config, "workflow_python", String(U"汉").repeat(32768)) == ERR_PARAMETER_RANGE_ERROR);
	CHECK(FileAccess::get_file_as_string(config) == before);
	write_file(config, "{invalid json");
	CHECK(RuntimeConfigTestAccess::update_file(config, "node", "replacement") == ERR_FILE_CORRUPT);
	CHECK(FileAccess::get_file_as_string(config) == "{invalid json");
}

TEST_CASE("[Editor][RuntimeConfig] Process termination releases the Python lock") {
	Error error = OK;
	Ref<DirAccess> temporary = DirAccess::create_temp("runtime_config_terminated", false, &error);
	REQUIRE(error == OK);
	LockProbe probe;
	probe.directory = temporary->get_current_dir();
	probe.mode = "hold";
	probe.start();
	REQUIRE(probe.started);
	REQUIRE(OS::get_singleton()->kill(probe.pid) == OK);
	const uint64_t deadline = OS::get_singleton()->get_ticks_msec() + 3000;
	while (OS::get_singleton()->is_process_running(probe.pid) && OS::get_singleton()->get_ticks_msec() < deadline) {
		OS::get_singleton()->delay_usec(10000);
	}
	CHECK_FALSE(OS::get_singleton()->is_process_running(probe.pid));
	CHECK(native_lock(probe.directory.path_join("configuration.json"), Callable()) == OK);
}
TEST_CASE("[Editor][RuntimeConfig] Early scope cannot access a global configuration") {
	if (!EditorPaths::get_singleton()) {
		CHECK(GongGongRuntimeConfig::configuration_path().is_empty());
		const Dictionary snapshot = GongGongRuntimeConfig::read_effective();
		CHECK_FALSE(bool(snapshot["ok"]));
		CHECK(String(snapshot["config_path"]).is_empty());
	}
}

TEST_CASE("[Editor][RuntimeConfig] Default project ignores only macOS system bookkeeping") {
	List<String> arguments;
	CHECK(GongGongEngineOrigin::uses_default_project(arguments));
#ifdef MACOS_ENABLED
	arguments.push_back("-psn_0_12345");
	CHECK(GongGongEngineOrigin::uses_default_project(arguments));
#endif
	arguments.push_back("--headless");
	CHECK_FALSE(GongGongEngineOrigin::uses_default_project(arguments));
	arguments.push_back("--path");
	arguments.push_back("/explicit/project");
	CHECK_FALSE(GongGongEngineOrigin::uses_default_project(arguments));
}

TEST_CASE("[Editor][RuntimeConfig] Native App self-update uses only its external manifest") {
	const String source = "/private/fixture";
	const String raw = source.path_join("bin/godot.macos.editor.arm64.self_update_a");
	const String app = raw + ".app";
	const String executable = app.path_join("Contents/MacOS/Godot");
	CHECK(AIChatHostRuntime::self_update_path_matches(raw, source));
	CHECK(AIChatHostRuntime::self_update_path_matches(executable, source));
	CHECK_FALSE(AIChatHostRuntime::self_update_path_matches(app.path_join("Contents/MacOS/other"), source));
	CHECK_FALSE(AIChatHostRuntime::self_update_path_matches(executable, "/another/source"));
	CHECK(AIChatHostRuntime::candidate_manifest_path(raw) == raw + ".candidate.json");
	CHECK(AIChatHostRuntime::candidate_manifest_path(executable) == app + ".candidate.json");
	CHECK(AIChatHostRuntime::candidate_manifest_path(executable) != executable + ".candidate.json");
}

TEST_CASE("[Editor][RuntimeConfig] Native artifact directory is bound to source and OS user") {
	const String source = "/private/fixture";
	const String directory = GongGongEngineOrigin::native_artifact_directory(source);
#ifdef MACOS_ENABLED
	REQUIRE_FALSE(directory.is_empty());
	CHECK(directory.get_file() == source.sha256_text());
	CHECK(directory.get_base_dir().ends_with("/Library/Application Support/gonggong/engine-artifacts"));
	const String app = directory.path_join("godot.macos.editor.arm64.self_update_b.app");
	const String executable = app.path_join("Contents/MacOS/Godot");
	CHECK(AIChatHostRuntime::self_update_path_matches(executable, source));
	CHECK_FALSE(AIChatHostRuntime::self_update_path_matches(directory.path_join("godot.macos.editor.arm64.self_update_b"), source));
	CHECK_FALSE(AIChatHostRuntime::self_update_path_matches(executable, "/another/source"));
	CHECK_FALSE(AIChatHostRuntime::self_update_path_matches(directory.path_join("other.app/Contents/MacOS/Godot"), source));
	CHECK_FALSE(AIChatHostRuntime::self_update_path_matches(directory.path_join("extra/godot.macos.editor.arm64.self_update_b.app/Contents/MacOS/Godot"), source));
	CHECK(GongGongEngineOrigin::native_artifact_directory("relative/source").is_empty());
	CHECK(GongGongEngineOrigin::native_artifact_directory("/private/fixture/../fixture").is_empty());
#else
	CHECK(directory.is_empty());
#endif
}
} // namespace TestRuntimeConfig
#endif
