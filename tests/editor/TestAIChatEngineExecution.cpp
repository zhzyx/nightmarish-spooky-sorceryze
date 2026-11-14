/**************************************************************************/
/*  TestAIChatEngineExecution.cpp                                                      */
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

#include "core/crypto/crypto_core.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "editor/docks/AIChatEngineExecution.h"
#include "editor/docks/ai_chat_resume.h"
#include "tests/test_macros.h"

TEST_FORCE_LINK(TestAIChatEngineExecution);

namespace TestAIChatEngineExecution
{
namespace
{
void WriteText(const String &strPath, const String &strText)
{
	const Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
	REQUIRE(refFile.is_valid());
	refFile->store_string(strText);
	refFile->flush();
	REQUIRE(refFile->get_error() == OK);
}

struct Fixture
{
	String strRoot;
	Dictionary mapHost;
	Ref<AIChatEngineExecution> refExecution;

	Fixture()
	{
		strRoot = OS::get_singleton()->get_temp_path().path_join("ai-engine-execution-" + AIChatResume::make_token());
		REQUIRE(DirAccess::make_dir_recursive_absolute(strRoot.path_join("tools")) == OK);
		REQUIRE(DirAccess::make_dir_recursive_absolute(strRoot.path_join("bin")) == OK);
		refExecution.instantiate();
		mapHost["engine_root"] = strRoot;
		mapHost["cache_directory"] = strRoot;
		mapHost["session_directory"] = strRoot;
		mapHost["current_executable"] = OS::get_singleton()->get_executable_path();
		mapHost["tool_permission"] = true;
		mapHost["candidate_validated"] = true;
		mapHost["tool_call_id"] = "engine-call-1";
		mapHost["build_python"] = OS::get_singleton()->get_environment("GONGGONG_TEST_PYTHON");
#ifdef UNIX_ENABLED
		if (String(mapHost["build_python"]).is_empty())
		{
			mapHost["build_python"] = "/usr/bin/python3";
		}
#endif
		WriteText(strRoot.path_join("bin/godot.test.editor.self_update_a"), "controlled-test-artifact\n");
	}

	~Fixture()
	{
		if (refExecution->GetState().nBuildPid >= 0)
		{
			refExecution->CancelBuild();
			for (int nAttempt = 0; nAttempt < 100 && refExecution->GetState().nBuildPid >= 0; ++nAttempt)
			{
				OS::get_singleton()->delay_usec(10000);
				refExecution->PollBuild();
			}
			if (refExecution->GetState().nBuildPid >= 0)
			{
				OS::get_singleton()->kill(refExecution->GetState().nBuildPid);
			}
		}
		refExecution->AbandonRestart();
		const Ref<DirAccess> refDirectory = DirAccess::open(strRoot);
		if (refDirectory.is_valid())
		{
			refDirectory->erase_contents_recursive();
			DirAccess::remove_absolute(strRoot);
		}
	}

	void InstallWorker(const String &strMode)
	{
		WriteText(strRoot.path_join("mode"), strMode);
		WriteText(strRoot.path_join("tools/editor_self_build.py"),
				"import json, pathlib, sys, time\n"
				"root = pathlib.Path(__file__).absolute().parents[1]\n"
				"args = sys.argv[1:]\n"
				"value = lambda key: args[args.index(key) + 1]\n"
				"mode = (root / 'mode').read_text()\n"
				"status = pathlib.Path(value('--status'))\n"
				"cancel = pathlib.Path(value('--cancel'))\n"
				"artifact = str(root / 'bin/godot.test.editor.self_update_a')\n"
				"data = dict(stage='ready', percent=100, exit_code=0, executable=artifact)\n"
				"if mode == 'current': data['executable'] = value('--current')\n"
				"if mode == 'outside': data['executable'] = str(root / 'outside')\n"
				"if mode == 'cancel':\n"
				"    deadline = time.monotonic() + 5\n"
				"    while not cancel.exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
				"if mode != 'missing':\n"
				"    temporary = status.with_suffix('.tmp')\n"
				"    temporary.write_text('{' if mode == 'malformed' else json.dumps(data))\n"
				"    temporary.replace(status)\n"
				"if mode == 'live': time.sleep(0.3)\n"
				"sys.exit(7 if mode == 'failure' else 0)\n");
	}

	void Start(const String &strMode, bool bRestart = false)
	{
		InstallWorker(strMode);
		Dictionary mapArguments;
		mapArguments["restart"] = bRestart;
		REQUIRE(bool(refExecution->Prepare("build_engine", mapArguments, mapHost).get("ok", false)));
		REQUIRE(bool(refExecution->StartBuild(mapHost).get("ok", false)));
		REQUIRE(refExecution->GetState().nBuildPid >= 0);
	}

	Dictionary Wait()
	{
		Dictionary mapResult;
		for (int nAttempt = 0; nAttempt < 600; ++nAttempt)
		{
			mapResult = refExecution->PollBuild();
			if (!bool(mapResult.get("running", false)))
			{
				return mapResult;
			}
			OS::get_singleton()->delay_usec(10000);
		}
		FAIL_CHECK("Controlled build worker did not exit within six seconds.");
		return mapResult;
	}

	Dictionary Checkpoint() const
	{
		Dictionary mapJournal;
		mapJournal["version"] = AIChatResume::VERSION;
		mapJournal["agent"] = 0;
		mapJournal["tool_rounds"] = 0;
		mapJournal["tool_index"] = 0;
		mapJournal["model"] = "test-model";
		mapJournal["cli_model"] = "test-cli";
		mapJournal["codex_model"] = "test-codex";
		mapJournal["backend"] = 0;
		mapJournal["snapshot_id"] = "test-snapshot";
		mapJournal["messages"] = Array();
		mapJournal["tool_calls"] = Array();
		return mapJournal;
	}
};
}

TEST_CASE("[AIChatEngineExecution] Preparation validates authority and arguments without Dock")
{
	Fixture stFixture;
	Dictionary mapArguments;
	mapArguments["restart"] = "yes";
	CHECK_FALSE(bool(stFixture.refExecution->Prepare("build_engine", mapArguments, stFixture.mapHost).get("ok", true)));
	CHECK(stFixture.refExecution->GetState().strToolCallId.is_empty());
	mapArguments["restart"] = false;
	Array arrOptions;
	arrOptions.push_back("jobs=2\rplatform=wrong");
	mapArguments["scons_args"] = arrOptions;
	CHECK_FALSE(bool(stFixture.refExecution->Prepare("build_engine", mapArguments, stFixture.mapHost).get("ok", true)));
	mapArguments.clear();
	stFixture.mapHost["tool_permission"] = false;
	CHECK_FALSE(bool(stFixture.refExecution->Prepare("build_engine", mapArguments, stFixture.mapHost).get("ok", true)));
	stFixture.mapHost["tool_permission"] = true;
	CHECK_FALSE(bool(stFixture.refExecution->Prepare("unrecognized", mapArguments, stFixture.mapHost).get("ok", true)));
	CHECK(bool(stFixture.refExecution->Prepare("build_engine", mapArguments, stFixture.mapHost).get("ok", false)));
	stFixture.refExecution->FinishTool();
	CHECK(stFixture.refExecution->GetState().strToolCallId.is_empty());
	CHECK(stFixture.refExecution->GetState().mapToolArguments.is_empty());
}

TEST_CASE("[AIChatEngineExecution] Build refuses missing live candidate validation")
{
	Fixture stFixture;
	stFixture.InstallWorker("success");
	stFixture.mapHost["candidate_validated"] = false;
	CHECK_FALSE(bool(stFixture.refExecution->StartBuild(stFixture.mapHost).get("ok", true)));
	CHECK(stFixture.refExecution->GetState().nBuildPid == -1);
}

#if defined(UNIX_ENABLED)
TEST_CASE("[AIChatEngineExecution] Real worker exit controls build success and restart projection")
{
	Fixture stFixture;
	stFixture.Start("live", true);
	const Dictionary mapLive = stFixture.refExecution->PollBuild();
	CHECK(bool(mapLive.get("running", false)));
	CHECK_FALSE(mapLive.has("result"));
	CHECK_FALSE(bool(stFixture.refExecution->StartBuild(stFixture.mapHost).get("ok", true)));
	const Dictionary mapDone = stFixture.Wait();
	CHECK(int(mapDone.get("exit_code", -1)) == 0);
	CHECK(int(mapDone.get("progress", -1)) == 100);
	CHECK(bool(mapDone.get("restart_needed", false)));
	CHECK(String(mapDone.get("next_action", "")) == "restart");
	CHECK(bool(Dictionary(mapDone.get("result", Dictionary())).get("built", false)));
	CHECK_FALSE(stFixture.refExecution->GetState().bRestartArmed);
}

TEST_CASE("[AIChatEngineExecution] Ready receipt cannot override a real failing exit")
{
	Fixture stFixture;
	stFixture.Start("failure");
	const Dictionary mapDone = stFixture.Wait();
	CHECK(int(mapDone.get("exit_code", -1)) == 7);
	CHECK_FALSE(bool(mapDone.get("ok", true)));
	CHECK_FALSE(bool(mapDone.get("restart_needed", true)));
	CHECK(stFixture.refExecution->GetState().strUpdatedExecutable.is_empty());
	CHECK(String(mapDone.get("next_action", "")) == "finish_tool");
}

TEST_CASE("[AIChatEngineExecution] Missing malformed and current executable receipts are rejected")
{
	Fixture stFixture;
	String strMode;
	SUBCASE("missing")
	{
		strMode = "missing";
	}
	SUBCASE("malformed")
	{
		strMode = "malformed";
	}
	SUBCASE("current executable")
	{
		strMode = "current";
	}
	SUBCASE("outside output root")
	{
		strMode = "outside";
		WriteText(stFixture.strRoot.path_join("outside"), "not-a-candidate");
	}
	stFixture.Start(strMode);
	const Dictionary mapDone = stFixture.Wait();
	CHECK_FALSE(bool(mapDone.get("ok", true)));
	CHECK(stFixture.refExecution->GetState().strUpdatedExecutable.is_empty());
}

TEST_CASE("[AIChatEngineExecution] Cancellation wins over a late successful ready receipt")
{
	Fixture stFixture;
	stFixture.Start("cancel", true);
	CHECK(bool(stFixture.refExecution->CancelBuild().get("ok", false)));
	CHECK(FileAccess::exists(stFixture.refExecution->GetState().strCancelPath));
	const Dictionary mapDone = stFixture.Wait();
	CHECK(int(mapDone.get("exit_code", -1)) == 0);
	CHECK_FALSE(bool(mapDone.get("ok", true)));
	CHECK_FALSE(bool(mapDone.get("restart_needed", true)));
	CHECK(stFixture.refExecution->GetState().strUpdatedExecutable.is_empty());
}
#endif

TEST_CASE("[AIChatEngineExecution] Restart requires exact durable checkpoint and preserves foreign journal")
{
	Fixture stFixture;
	stFixture.mapHost["target_executable"] = stFixture.strRoot.path_join("bin/godot.test.editor.self_update_a");
	stFixture.mapHost["journal"] = stFixture.Checkpoint();
	const Dictionary mapPrepared = stFixture.refExecution->PrepareRestart(stFixture.mapHost);
	REQUIRE(bool(mapPrepared.get("ok", false)));
	CHECK_FALSE(stFixture.refExecution->GetState().bRestartArmed);
	CHECK_FALSE(bool(stFixture.refExecution->ConfirmRestartPersistence(stFixture.mapHost).get("ok", true)));
	AIChatResume stStorage;
	stStorage.directory = stFixture.strRoot;
	const Dictionary mapJournal = mapPrepared["journal"];
	REQUIRE(stStorage.write_journal(mapJournal) == OK);
	REQUIRE(bool(stFixture.refExecution->ConfirmRestartPersistence(stFixture.mapHost).get("ok", false)));
	CHECK(stFixture.refExecution->GetState().bRestartArmed);
	// A missing supervisor never schedules the current test executable to restart.
	CHECK_FALSE(bool(stFixture.refExecution->ArmWatchdog(stFixture.mapHost).get("ok", true)));
	Dictionary mapForeign = mapJournal.duplicate(true);
	Dictionary mapRestart = mapForeign["restart"];
	mapRestart["token"] = AIChatResume::make_token();
	mapForeign["restart"] = mapRestart;
	REQUIRE(stStorage.write_journal(mapForeign) == OK);
	stFixture.refExecution->AbandonRestart();
	Dictionary mapReadback;
	CHECK(stStorage.read_journal(mapReadback));
	CHECK(mapReadback.recursive_equal(JSON::parse_string(JSON::stringify(mapForeign)), 0));
	CHECK_FALSE(stFixture.refExecution->GetState().bRestartArmed);
}

TEST_CASE("[AIChatEngineExecution] Restart rejects changed journal and excessive attempts")
{
	Fixture stFixture;
	stFixture.mapHost["target_executable"] = stFixture.strRoot.path_join("bin/godot.test.editor.self_update_a");
	stFixture.mapHost["journal"] = stFixture.Checkpoint();
	stFixture.mapHost["restart_attempt"] = AIChatResume::MAX_RESTART_ATTEMPTS + 1;
	CHECK_FALSE(bool(stFixture.refExecution->PrepareRestart(stFixture.mapHost).get("ok", true)));
	stFixture.mapHost["restart_attempt"] = 1;
	const Dictionary mapPrepared = stFixture.refExecution->PrepareRestart(stFixture.mapHost);
	REQUIRE(bool(mapPrepared.get("ok", false)));
	Dictionary mapChanged = Dictionary(mapPrepared["journal"]).duplicate(true);
	mapChanged["model"] = "changed-model";
	AIChatResume stStorage;
	stStorage.directory = stFixture.strRoot;
	REQUIRE(stStorage.write_journal(mapChanged) == OK);
	CHECK_FALSE(bool(stFixture.refExecution->ConfirmRestartPersistence(stFixture.mapHost).get("ok", true)));
	CHECK_FALSE(stFixture.refExecution->GetState().bRestartArmed);
}
TEST_CASE("[AIChatEngineExecution] Tool restart preserves complete messages arguments and loop position")
{
	Fixture stFixture;
	Dictionary mapArguments;
	mapArguments["restart"] = true;
	REQUIRE(bool(stFixture.refExecution->Prepare("build_engine", mapArguments, stFixture.mapHost).get("ok", false)));
	Dictionary mapJournal = stFixture.Checkpoint();
	Dictionary mapFunction;
	mapFunction["name"] = "build_engine";
	mapFunction["arguments"] = JSON::stringify(mapArguments);
	Dictionary mapCall;
	mapCall["id"] = "engine-call-1";
	mapCall["type"] = "function";
	mapCall["function"] = mapFunction;
	Array arrCalls;
	arrCalls.push_back(mapCall);
	mapJournal["tool_calls"] = arrCalls;
	Dictionary mapMessage;
	mapMessage["role"] = "user";
	mapMessage["content"] = String::utf8("Preserve this exact checkpoint, including Unicode: 继续。");
	Array arrMessages;
	arrMessages.push_back(mapMessage);
	mapJournal["messages"] = arrMessages;
	mapJournal["tool_rounds"] = 7;
	stFixture.mapHost["tool_driven"] = true;
	stFixture.mapHost["target_executable"] = stFixture.strRoot.path_join("bin/godot.test.editor.self_update_a");
	stFixture.mapHost["journal"] = mapJournal;
	const Dictionary mapPrepared = stFixture.refExecution->PrepareRestart(stFixture.mapHost);
	REQUIRE(bool(mapPrepared.get("ok", false)));
	const Dictionary mapPreserved = mapPrepared["journal"];
	CHECK(Array(mapPreserved["messages"]).recursive_equal(arrMessages, 0));
	CHECK(Array(mapPreserved["tool_calls"]).recursive_equal(arrCalls, 0));
	CHECK(int(mapPreserved["tool_rounds"]) == 7);
	CHECK(Dictionary(mapPreserved["restart"])["tool_call_id"] == "engine-call-1");
	AIChatResume stStorage;
	stStorage.directory = stFixture.strRoot;
	REQUIRE(stStorage.write_journal(mapPreserved) == OK);
	REQUIRE(bool(stFixture.refExecution->ConfirmRestartPersistence(stFixture.mapHost).get("ok", false)));
	stFixture.refExecution->AbandonRestart();
	CHECK_FALSE(FileAccess::exists(stStorage.journal_path()));
	mapJournal["tool_index"] = 1;
	stFixture.mapHost["journal"] = mapJournal;
	CHECK_FALSE(bool(stFixture.refExecution->PrepareRestart(stFixture.mapHost).get("ok", true)));
}

#if defined(UNIX_ENABLED)
TEST_CASE("[AIChatEngineExecution] Watchdog config preserves arguments and abandon revokes only its handoff")
{
	struct RestoreRestart
	{
		bool bEnabled = OS::get_singleton()->is_restart_on_exit_set();
		String strExecutable = OS::get_singleton()->get_restart_on_exit_executable();
		List<String> arrArguments = OS::get_singleton()->get_restart_on_exit_arguments();

		~RestoreRestart()
		{
			OS::get_singleton()->set_restart_on_exit(bEnabled, arrArguments);
			OS::get_singleton()->set_restart_on_exit_executable(strExecutable);
		}
	} stRestore;
	Fixture stFixture;
	WriteText(stFixture.strRoot.path_join("tools/editor_restart_watchdog.py"), "# controlled supervisor fixture; never executed\n");
	stFixture.mapHost["workflow_python"] = stFixture.mapHost["build_python"];
	stFixture.mapHost["target_executable"] = stFixture.strRoot.path_join("bin/godot.test.editor.self_update_a");
	stFixture.mapHost["journal"] = stFixture.Checkpoint();
	Array arrEditorArguments;
	arrEditorArguments.push_back("--headless");
	arrEditorArguments.push_back("--path");
	arrEditorArguments.push_back("a path with spaces");
	stFixture.mapHost["restart_arguments"] = arrEditorArguments;
	const Dictionary mapPrepared = stFixture.refExecution->PrepareRestart(stFixture.mapHost);
	REQUIRE(bool(mapPrepared.get("ok", false)));
	AIChatResume stStorage;
	stStorage.directory = stFixture.strRoot;
	REQUIRE(stStorage.write_journal(mapPrepared["journal"]) == OK);
	REQUIRE(bool(stFixture.refExecution->ConfirmRestartPersistence(stFixture.mapHost).get("ok", false)));
	REQUIRE(bool(stFixture.refExecution->ArmWatchdog(stFixture.mapHost).get("ok", false)));
	CHECK(OS::get_singleton()->is_restart_on_exit_set());
	CHECK(OS::get_singleton()->get_restart_on_exit_executable() == String(stFixture.mapHost["build_python"]));
	bool bHasToken = false;
	bool bHasEncodedArguments = false;
	const Vector<uint8_t> arrEncoded = JSON::stringify(arrEditorArguments).to_utf8_buffer();
	const String strEncoded = CryptoCore::b64_encode_str(arrEncoded.ptr(), arrEncoded.size());
	for (const String &strArgument : OS::get_singleton()->get_restart_on_exit_arguments())
	{
		bHasToken = bHasToken || strArgument == stFixture.refExecution->GetState().strRestartToken;
		bHasEncodedArguments = bHasEncodedArguments || strArgument == strEncoded;
	}
	CHECK(bHasToken);
	CHECK(bHasEncodedArguments);
	stFixture.refExecution->AbandonRestart();
	CHECK_FALSE(OS::get_singleton()->is_restart_on_exit_set());
	CHECK_FALSE(FileAccess::exists(stStorage.journal_path()));
}
#endif

TEST_CASE("[AIChatEngineExecution] Save prompt timeout requests abandonment without claiming restart success")
{
	Fixture stFixture;
	stFixture.refExecution->GetState().bRestartArmed = true;
	stFixture.refExecution->GetState().nRestartArmedMsec = OS::get_singleton()->get_ticks_msec() - 90001;
	const Dictionary mapResult = stFixture.refExecution->PollBuild();
	CHECK_FALSE(bool(mapResult.get("ok", true)));
	CHECK(String(mapResult.get("next_action", "")) == "abandon_restart");
	CHECK_FALSE(bool(mapResult.get("restart_needed", true)));
	stFixture.refExecution->AbandonRestart();
	CHECK_FALSE(stFixture.refExecution->GetState().bRestartArmed);
}

}
