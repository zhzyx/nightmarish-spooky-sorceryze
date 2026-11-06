/**************************************************************************/
/*  test_os.cpp                                                           */
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

TEST_FORCE_LINK(test_os)

#include "core/os/os.h"

#ifdef MACOS_ENABLED
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "tests/test_utils.h"
#endif

namespace TestOS {

#ifdef MACOS_ENABLED
class RestartStateGuard {
	OS *os;
	bool enabled;
	List<String> arguments;
	String executable;

public:
	explicit RestartStateGuard(OS *p_os) :
			os(p_os),
			enabled(p_os->is_restart_on_exit_set()),
			arguments(p_os->get_restart_on_exit_arguments()),
			executable(p_os->get_restart_on_exit_executable()) {}

	~RestartStateGuard() {
		os->set_restart_on_exit(enabled, arguments);
		os->set_restart_on_exit_executable(executable);
	}
};

static void check_process_receipt(OS *p_os, ProcessID p_child_id, const String &p_receipt_path, const String &p_payload) {
	const uint64_t deadline = p_os->get_ticks_msec() + 5000;
	while (p_os->is_process_running(p_child_id) && p_os->get_ticks_msec() < deadline) {
		p_os->delay_usec(1000);
	}
	const bool running = p_os->is_process_running(p_child_id);
	CHECK_FALSE(running);
	if (running) {
		CHECK(p_os->kill(p_child_id) == OK);
		return;
	}
	CHECK(p_os->get_process_exit_code(p_child_id) == 0);
	CHECK(FileAccess::get_file_as_string(p_receipt_path) == itos(p_child_id) + "\n" + p_payload);
	if (FileAccess::exists(p_receipt_path)) {
		CHECK(DirAccess::remove_absolute(p_receipt_path) == OK);
	}
}
#endif

TEST_CASE("[OS] Environment variables") {
#ifdef WINDOWS_ENABLED
	CHECK_MESSAGE(
			OS::get_singleton()->has_environment("USERPROFILE"),
			"The USERPROFILE environment variable should be present.");
#else
	CHECK_MESSAGE(
			OS::get_singleton()->has_environment("HOME"),
			"The HOME environment variable should be present.");
#endif
}

TEST_CASE("[OS] UTF-8 environment variables") {
	String value = String::utf8("hell\xc3\xb6"); // "hellö", UTF-8 encoded

	OS::get_singleton()->set_environment("HELLO", value);
	String val = OS::get_singleton()->get_environment("HELLO");
	CHECK_MESSAGE(
			val == value,
			"The previously-set HELLO environment variable should return the expected value.");
	CHECK_MESSAGE(
			val.length() == 5,
			"The previously-set HELLO environment variable was decoded as UTF-8 and should have a length of 5.");
	OS::get_singleton()->unset_environment("HELLO");
}

TEST_CASE("[OS] Non-UTF-8 environment variables") {
	String value = String("\xff t\xf6rkylempij\xe4vongahdus"); // hex FF and a Finnish pangram, latin-1
	OS::get_singleton()->set_environment("HELLO", value);
	String val = OS::get_singleton()->get_environment("HELLO");
	CHECK_MESSAGE(
			val == value,
			"The previously-set HELLO environment variable should return the expected value.");
	CHECK_MESSAGE(
			val.length() == 23,
			"The previously-set HELLO environment variable was not decoded from Latin-1.");
	OS::get_singleton()->unset_environment("HELLO");
}

TEST_CASE("[OS] Command line arguments") {
	List<String> arguments = OS::get_singleton()->get_cmdline_args();
	bool found = false;
	for (const String &arg : arguments) {
		if (arg == "--test") {
			found = true;
			break;
		}
	}
	CHECK_MESSAGE(
			found,
			"The `--test` option must be present in the list of command line arguments.");
}

TEST_CASE("[OS] Executable and data paths") {
	CHECK_MESSAGE(
			OS::get_singleton()->get_executable_path().is_absolute_path(),
			"The executable path returned should be an absolute path.");
	CHECK_MESSAGE(
			OS::get_singleton()->get_data_path().is_absolute_path(),
			"The user data path returned should be an absolute path.");
	CHECK_MESSAGE(
			OS::get_singleton()->get_config_path().is_absolute_path(),
			"The user configuration path returned should be an absolute path.");
	CHECK_MESSAGE(
			OS::get_singleton()->get_cache_path().is_absolute_path(),
			"The cache path returned should be an absolute path.");
}

TEST_CASE("[OS] Ticks") {
	CHECK_MESSAGE(
			OS::get_singleton()->get_ticks_usec() > 1000,
			"The returned ticks (in microseconds) must be greater than 1,000.");
	CHECK_MESSAGE(
			OS::get_singleton()->get_ticks_msec() > 1,
			"The returned ticks (in milliseconds) must be greater than 1.");
}

TEST_CASE("[OS] Feature tags") {
#ifdef TOOLS_ENABLED
	CHECK_MESSAGE(
			OS::get_singleton()->has_feature("editor"),
			"The binary has the \"editor\" feature tag.");
	CHECK_MESSAGE(
			!OS::get_singleton()->has_feature("template"),
			"The binary does not have the \"template\" feature tag.");
	CHECK_MESSAGE(
			!OS::get_singleton()->has_feature("template_debug"),
			"The binary does not have the \"template_debug\" feature tag.");
	CHECK_MESSAGE(
			!OS::get_singleton()->has_feature("template_release"),
			"The binary does not have the \"template_release\" feature tag.");
#else
	CHECK_MESSAGE(
			!OS::get_singleton()->has_feature("editor"),
			"The binary does not have the \"editor\" feature tag.");
	CHECK_MESSAGE(
			OS::get_singleton()->has_feature("template"),
			"The binary has the \"template\" feature tag.");
#ifdef DEBUG_ENABLED
	CHECK_MESSAGE(
			OS::get_singleton()->has_feature("template_debug"),
			"The binary has the \"template_debug\" feature tag.");
	CHECK_MESSAGE(
			!OS::get_singleton()->has_feature("template_release"),
			"The binary does not have the \"template_release\" feature tag.");
#else
	CHECK_MESSAGE(
			!OS::get_singleton()->has_feature("template_debug"),
			"The binary does not have the \"template_debug\" feature tag.");
	CHECK_MESSAGE(
			OS::get_singleton()->has_feature("template_release"),
			"The binary has the \"template_release\" feature tag.");
#endif // DEBUG_ENABLED
#endif // TOOLS_ENABLED
}

TEST_CASE("[OS] Process ID") {
	CHECK_MESSAGE(
			OS::get_singleton()->get_process_id() >= 1,
			"The returned process ID should be greater than zero.");
}

TEST_CASE("[OS] Processor count and memory information") {
	CHECK_MESSAGE(
			OS::get_singleton()->get_processor_count() >= 1,
			"The returned processor count should be greater than zero.");
#ifdef DEBUG_ENABLED
	CHECK_MESSAGE(
			OS::get_singleton()->get_static_memory_usage() >= 1,
			"The returned static memory usage should be greater than zero.");
	CHECK_MESSAGE(
			OS::get_singleton()->get_static_memory_peak_usage() >= 1,
			"The returned static memory peak usage should be greater than zero.");
#endif // DEBUG_ENABLED
}

TEST_CASE("[OS] Execute") {
#ifdef WINDOWS_ENABLED
	List<String> arguments;
	arguments.push_back("/C");
	arguments.push_back("dir > NUL");
	int exit_code;
	const Error err = OS::get_singleton()->execute("cmd", arguments, nullptr, &exit_code);
	CHECK_MESSAGE(
			err == OK,
			"(Running the command `cmd /C \"dir > NUL\"` returns the expected Godot error code (OK).");
	CHECK_MESSAGE(
			exit_code == 0,
			"Running the command `cmd /C \"dir > NUL\"` returns a zero (successful) exit code.");
	arguments.clear();
	arguments.push_back("/C");
	arguments.push_back("exit /B 7");
	String output;
	const Error pipe_err = OS::get_singleton()->execute("cmd", arguments, &output, &exit_code, true);
	CHECK_MESSAGE(pipe_err == OK, "A shell command with captured output starts successfully.");
	CHECK_MESSAGE(exit_code == 7, "A nonzero shell exit code is preserved with captured output.");
#else
	List<String> arguments;
	arguments.push_back("-c");
	arguments.push_back("ls > /dev/null");
	int exit_code;
	const Error err = OS::get_singleton()->execute("sh", arguments, nullptr, &exit_code);
	CHECK_MESSAGE(
			err == OK,
			"(Running the command `sh -c \"ls > /dev/null\"` returns the expected Godot error code (OK).");
	CHECK_MESSAGE(
			exit_code == 0,
			"Running the command `sh -c \"ls > /dev/null\"` returns a zero (successful) exit code.");
#endif
}

#ifdef MACOS_ENABLED
TEST_CASE("[OS][MacOS] Explicit restart executable") {
	OS *os = OS::get_singleton();
	const String receipt_path = TestUtils::get_temp_path("macos_restart_executable.txt");
	const String payload = String::utf8("restart argument with spaces and 中文");
	List<String> arguments;
	arguments.push_back("-c");
	arguments.push_back("printf '%s\\n%s' \"$$\" \"$1\" > \"$2\"");
	arguments.push_back("godot-restart-test");
	arguments.push_back(payload);
	arguments.push_back(receipt_path);
	// Keep an incorrect self-launch headless and short-lived if the target regresses.
	arguments.push_back("--headless");
	arguments.push_back("--quit");

	ProcessID child_id = 0;
	Error err = FAILED;
	{
		const RestartStateGuard restore(os);
		os->set_restart_on_exit(true, arguments);
		os->set_restart_on_exit_executable("/bin/sh");
		err = os->create_instance(arguments, &child_id);
	}
	REQUIRE(err == OK);
	REQUIRE(child_id > 0);

	check_process_receipt(os, child_id, receipt_path, payload);
}

TEST_CASE("[OS][MacOS] Headless instance without an explicit restart executable") {
	OS *os = OS::get_singleton();
	bool restart = true;
	String executable;
	SUBCASE("Enabled restart with an empty target") {}
	SUBCASE("Disabled restart ignores a configured target") {
		restart = false;
		executable = "/usr/bin/false";
	}

	const String project_path = TestUtils::get_temp_path("macos_restart_fallback");
	const String receipt_path = project_path.path_join("receipt.txt");
	const String script_path = project_path.path_join("probe.gd");
	const String payload = "ordinary headless instance";
	REQUIRE(DirAccess::make_dir_recursive_absolute(project_path) == OK);
	{
		Ref<FileAccess> project = FileAccess::open(project_path.path_join("project.godot"), FileAccess::WRITE);
		REQUIRE(project.is_valid());
		project->store_string("config_version=5\n[application]\nconfig/name=\"Restart fallback probe\"\n");
		Ref<FileAccess> script = FileAccess::open(script_path, FileAccess::WRITE);
		REQUIRE(script.is_valid());
		script->store_string("extends SceneTree\n\nfunc _initialize():\n\tvar args = OS.get_cmdline_user_args()\n\tvar file = FileAccess.open(args[0], FileAccess.WRITE)\n\tfile.store_string(str(OS.get_process_id()) + \"\\n\" + args[1])\n\tfile.close()\n\tquit()\n");
	}
	List<String> arguments;
	arguments.push_back("--headless");
	arguments.push_back("--path");
	arguments.push_back(project_path);
	arguments.push_back("--script");
	arguments.push_back(script_path);
	arguments.push_back("--");
	arguments.push_back(receipt_path);
	arguments.push_back(payload);

	ProcessID child_id = 0;
	Error err = FAILED;
	{
		const RestartStateGuard restore(os);
		os->set_restart_on_exit(restart, arguments);
		os->set_restart_on_exit_executable(executable);
		err = os->create_instance(arguments, &child_id);
	}
	REQUIRE(err == OK);
	REQUIRE(child_id > 0);
	check_process_receipt(os, child_id, receipt_path, payload);
	Ref<DirAccess> project = DirAccess::open(project_path);
	REQUIRE(project.is_valid());
	CHECK(project->erase_contents_recursive() == OK);
	project.unref();
	CHECK(DirAccess::remove_absolute(project_path) == OK);
}
#endif

} // namespace TestOS
