/**************************************************************************/
/*  TestCVars.cpp                                                        */
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

TEST_FORCE_LINK(TestCVars)

#include "core/config/CVars.h"
#include "core/config/engine.h"
#include "core/debugger/engine_debugger.h"
#include "core/input/input_event.h"
#include "core/io/file_access.h"
#include "core/math/math_funcs.h"
#include "core/object/callable_mp.h"
#include "scene/debugger/CVarConsole.h"
#include "scene/gui/line_edit.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"
#include "tests/test_utils.h"

#include <atomic>

static int nChangeHits = 0;

static void TestOnChanged(String in_strName, Variant varValue)
{
	nChangeHits++;
	(void)in_strName;
	(void)varValue;
}

static String strCommandArgs;

static void TestCommand(PackedStringArray in_arrArgs)
{
	strCommandArgs = String();
	for (int nI = 0; nI < in_arrArgs.size(); nI++)
	{
		if (nI > 0)
		{
			strCommandArgs += ",";
		}
		strCommandArgs += in_arrArgs[nI];
	}
}

static std::atomic<int32_t> atomLinkedInt{ 0 };
static std::atomic<double> atomLinkedFloat{ 1.5 };
static std::atomic<int32_t> atomLinkedBool{ 0 };

static void TestBumpOther(void *pUserdata)
{
	(void)pUserdata;
	CVars::GetSingleton()->SetValue("test.b", 5);
}

namespace TestCVars
{

TEST_CASE("[CVars] priority, parsing, file, and engine builtins")
{
	CVars *pCv = CVars::GetSingleton();
	REQUIRE(pCv != nullptr);
	REQUIRE(Engine::get_singleton() != nullptr);

	const bool bSavedCheat = pCv->AreCheatCommandsAllowed();
	const double dSavedScale = Engine::get_singleton()->get_time_scale();
	const int nSavedFps = Engine::get_singleton()->get_max_fps();
	Vector<String> arrRegisteredNames;
	struct Restore
	{
		CVars *pCv = nullptr;
		bool bCheat = false;
		double dScale = 1.0;
		int nFps = 0;
		Vector<String> *pRegistered = nullptr;
		~Restore()
		{
			if (!pCv || !Engine::get_singleton())
			{
				return;
			}
			if (pRegistered)
			{
				for (const String &strName : *pRegistered)
				{
					pCv->Unregister(strName);
				}
			}
			pCv->SetCheatCommandsAllowed(bCheat);
			pCv->SetConfigFile("");
			pCv->Reset("con.ConfigPollMs");
			Engine::get_singleton()->set_time_scale(dScale);
			Engine::get_singleton()->set_max_fps(nFps);
			pCv->SyncEngineBuiltins(false, false);
		}
	} stRestore;
	stRestore.pCv = pCv;
	stRestore.bCheat = bSavedCheat;
	stRestore.dScale = dSavedScale;
	stRestore.nFps = nSavedFps;
	stRestore.pRegistered = &arrRegisteredNames;

	auto fnTrackName = [pCv, &arrRegisteredNames](const String &in_strName)
	{
		if (pCv->HasVariable(in_strName) || pCv->HasCommand(in_strName))
		{
			pCv->Unregister(in_strName);
		}
		arrRegisteredNames.push_back(in_strName);
	};

	auto fnRegister = [pCv, &fnTrackName](const String &in_strName, const Variant &varDefault, uint32_t nFlags = 0)
	{
		fnTrackName(in_strName);
		return pCv->RegisterVariable(in_strName, varDefault, in_strName, nFlags);
	};

	CHECK(pCv->Help("t.timescale").contains("t.TimeScale"));
	CHECK(pCv->Help("t.timescale").contains("float"));
	CHECK(pCv->Execute("dump t.maxfps").contains("t.MaxFPS"));

	REQUIRE(fnRegister("test.p", 0));
	CHECK(pCv->SetValueWithPriority("test.p", 1, CVars::SET_BY_CONFIG_FILE));
	CHECK_EQ(pCv->GetSetBy("test.p"), CVars::SET_BY_CONFIG_FILE);
	CHECK(pCv->Execute("test.p 1").contains("test.p = 1"));
	CHECK_EQ(pCv->GetSetBy("test.p"), CVars::SET_BY_CONSOLE);
	ERR_PRINT_OFF;
	CHECK_FALSE(pCv->SetValueWithPriority("test.p", 2, CVars::SET_BY_CONFIG_FILE));
	CHECK_FALSE(pCv->SetValue("test.p", 4));
	ERR_PRINT_ON;
	CHECK_EQ((int64_t)pCv->GetValue("test.p"), (int64_t)1);
	CHECK(pCv->Reset("test.p"));
	CHECK_EQ((int64_t)pCv->GetValue("test.p"), (int64_t)0);
	CHECK_EQ(pCv->GetSetBy("test.p"), CVars::SET_BY_CONSTRUCTOR);
	CHECK(pCv->SetValue("test.p", 4));
	CHECK_EQ(pCv->GetSetBy("test.p"), CVars::SET_BY_CODE);
	CHECK(pCv->Execute("test.p 5").contains("= 5"));
	CHECK_EQ((int64_t)pCv->GetValue("test.p"), (int64_t)5);

	nChangeHits = 0;
	CHECK(pCv->Reset("test.p"));
	CHECK(pCv->SetChangedCallback("test.p", callable_mp_static(TestOnChanged)));
	CHECK(pCv->SetValue("test.p", 1));
	CHECK(pCv->SetValue("test.p", 1));
	CHECK(pCv->SetValue("test.p", 2));
	CHECK_EQ(nChangeHits, 2);

	REQUIRE(fnRegister("test.trunc", 0));
	CHECK(pCv->Execute("test.trunc 3.9").contains("= 3"));
	CHECK_EQ((int64_t)pCv->GetValue("test.trunc"), (int64_t)3);
	CHECK(pCv->Execute("test.trunc 1; test.trunc 2").contains("= 2"));
	CHECK_EQ((int64_t)pCv->GetValue("test.trunc"), (int64_t)2);
	CHECK(pCv->Execute("# test.trunc 9").is_empty());
	CHECK(pCv->Execute("test.trunc 1e100").contains("outside the signed 64-bit integer range"));
	CHECK(pCv->Execute("test.trunc 9.223372036854776e18").contains("outside the signed 64-bit integer range"));
	CHECK(pCv->Execute("test.trunc -9.223372036854776e18").contains("= -9223372036854775808"));
	CHECK(pCv->Reset("test.trunc"));
	ERR_PRINT_OFF;
	CHECK_FALSE(pCv->SetValue("test.trunc", 1e100));
	CHECK_FALSE(pCv->SetValue("test.trunc", -1e100));
	ERR_PRINT_ON;
	CHECK_EQ((int64_t)pCv->GetValue("test.trunc"), (int64_t)0);
	CHECK(pCv->SetValue("test.trunc", -3.9));
	CHECK_EQ((int64_t)pCv->GetValue("test.trunc"), (int64_t)-3);

	REQUIRE(fnRegister("test.str", ""));
	CHECK_EQ(String(pCv->GetValue("test.str")), String(""));
	(void)pCv->Execute("test.str \"a;b\"");
	CHECK_EQ(String(pCv->GetValue("test.str")), String("a;b"));
	(void)pCv->Execute("test.str=hello world");
	CHECK_EQ(String(pCv->GetValue("test.str")), String("hello world"));

	REQUIRE(fnRegister("test.CaseName", 1));
	(void)pCv->Execute("TEST.casename 4");
	CHECK_EQ((int64_t)pCv->GetValue("test.CASENAME"), (int64_t)4);

	REQUIRE(fnRegister("test.flag", false));
	(void)pCv->Execute("test.flag off");
	CHECK_FALSE(bool(pCv->GetValue("test.flag")));
	(void)pCv->Execute("test.flag yes");
	CHECK(bool(pCv->GetValue("test.flag")));
	CHECK(pCv->Reset("test.flag"));
	CHECK(pCv->SetValue("test.flag", 0.5));
	CHECK(bool(pCv->GetValue("test.flag")));

	REQUIRE(fnRegister("test.ro", 5, CVars::FLAG_READ_ONLY));
	CHECK(pCv->Execute("test.ro 9").contains("read-only"));
	CHECK_EQ((int64_t)pCv->GetValue("test.ro"), (int64_t)5);
	CHECK(pCv->SetValue("test.ro", 8));
	CHECK_EQ((int64_t)pCv->GetValue("test.ro"), (int64_t)8);
	CHECK(pCv->Execute("reset test.ro").contains("read-only"));

	pCv->SetCheatCommandsAllowed(false);
	REQUIRE(fnRegister("test.cheat", 1, CVars::FLAG_CHEAT));
	CHECK(pCv->Execute("test.cheat 2").contains("cheat"));
	CHECK_EQ((int64_t)pCv->GetValue("test.cheat"), (int64_t)1);
	ERR_PRINT_OFF;
	CHECK_FALSE(pCv->SetValueWithPriority("test.cheat", 3, CVars::SET_BY_CONFIG_FILE));
	ERR_PRINT_ON;
	CHECK(pCv->SetValue("test.cheat", 4));
	CHECK_EQ((int64_t)pCv->GetValue("test.cheat"), (int64_t)4);
	pCv->SetCheatCommandsAllowed(true);
	(void)pCv->Execute("test.cheat 5");
	CHECK_EQ((int64_t)pCv->GetValue("test.cheat"), (int64_t)5);
	CHECK(pCv->Execute("help test.cheat").contains("cheat"));

	REQUIRE(fnRegister("test.rt", 1, CVars::FLAG_RENDER_THREAD_SAFE));
	(void)pCv->Execute("test.rt 9");
	CHECK_EQ(pCv->GetIntRenderThread("test.rt"), 9);
	CHECK(pCv->Execute("test.rt 4294967297").contains("outside the signed 32-bit integer range"));
	CHECK_EQ(int64_t(pCv->GetValue("test.rt")), int64_t(9));
	CHECK_EQ(pCv->GetIntRenderThread("test.rt"), 9);
	REQUIRE(fnRegister("test.nort", 1));
	ERR_PRINT_OFF;
	CHECK_EQ(pCv->GetIntRenderThread("test.nort"), 0);
	ERR_PRINT_ON;

	fnTrackName("test.a");
	fnTrackName("test.b");
	REQUIRE(fnRegister("test.b", 0));
	atomLinkedInt.store(0);
	REQUIRE(pCv->RegisterIntRef("test.a", &atomLinkedInt, 0, "a", 0, TestBumpOther, nullptr));
	(void)pCv->Execute("test.a 1");
	CHECK_EQ(atomLinkedInt.load(), 1);
	CHECK_EQ((int64_t)pCv->GetValue("test.b"), (int64_t)5);
	CHECK_EQ(pCv->GetIntRenderThread("test.a"), 1);

	fnTrackName("test.fatom");
	atomLinkedFloat.store(1.5);
	REQUIRE(pCv->RegisterFloatRef("test.fatom", &atomLinkedFloat, 1.5, "f"));
	(void)pCv->Execute("test.fatom 3.25");
	CHECK(Math::is_equal_approx(atomLinkedFloat.load(), 3.25));
	CHECK(Math::is_equal_approx(pCv->GetFloatRenderThread("test.fatom"), 3.25));

	fnTrackName("test.batom");
	atomLinkedBool.store(0);
	REQUIRE(pCv->RegisterBoolRef("test.batom", &atomLinkedBool, false, "b"));
	(void)pCv->Execute("test.batom yes");
	CHECK_EQ(atomLinkedBool.load(), 1);
	CHECK(pCv->GetBoolRenderThread("test.batom"));
	(void)pCv->Execute("test.batom off");
	CHECK_FALSE(bool(pCv->GetValue("test.batom")));
	CHECK_FALSE(pCv->GetBoolRenderThread("test.batom"));

	strCommandArgs = String();
	fnTrackName("test.cmd");
	REQUIRE(pCv->RegisterCommand("test.cmd", callable_mp_static(TestCommand), "joins args"));
	CHECK(pCv->HasCommand("test.cmd"));
	(void)pCv->Execute("test.cmd alpha beta");
	CHECK_EQ(strCommandArgs, String("alpha,beta"));
	CHECK(pCv->Execute("test.no_such 1").contains("error:"));

	CHECK(CVars::RecognizesArg("--cvar"));
	CHECK(CVars::RecognizesArg("--cvar=t.X=1"));
	CHECK(CVars::RecognizesArg("--cvar-exec"));
	CHECK(CVars::RecognizesArg("--cvar-file=user://cvars.cfg"));
	CHECK_FALSE(CVars::RecognizesArg("--cvar-nope"));
	const CVars::ArgResult stMissing = pCv->ParseEngineArg("--cvar", "", false);
	CHECK(stMissing.bRecognized);
	CHECK(stMissing.bError);

	pCv->SetConfigFile("");
	const CVars::ArgResult stQueued = pCv->ParseEngineArg("--cvar", "test.cli=4", true);
	CHECK(stQueued.bConsumedNext);
	CHECK_FALSE(stQueued.bError);
	(void)pCv->ApplyStartup();
	fnTrackName("test.cli");
	REQUIRE(pCv->RegisterVariable("test.cli", 0, "cli"));
	CHECK_EQ((int64_t)pCv->GetValue("test.cli"), (int64_t)4);
	CHECK_EQ(pCv->GetSetBy("test.cli"), CVars::SET_BY_COMMAND_LINE);

	const CVars::ArgResult stExecArg = pCv->ParseEngineArg("--cvar-exec=test.cli 6", "", false);
	CHECK_FALSE(stExecArg.bConsumedNext);
	CHECK_FALSE(stExecArg.bError);
	(void)pCv->ApplyStartup();
	CHECK_EQ((int64_t)pCv->GetValue("test.cli"), (int64_t)6);

	const String strPath = TestUtils::get_temp_path("cvar_test.cfg");
	{
		Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refFile.is_valid());
		refFile->store_string("# comment\n; also\n\n[ConsoleVariables]\ntest.file_var=7\ntest.file_bool off\ntest.file_str=hello world\n");
		refFile->flush();
	}
	fnTrackName("test.file_var");
	fnTrackName("test.file_bool");
	fnTrackName("test.file_str");
	REQUIRE(fnRegister("test.file_var", 0));
	REQUIRE(fnRegister("test.file_bool", true));
	REQUIRE(fnRegister("test.file_str", ""));
	const CVars::ArgResult stFileArg = pCv->ParseEngineArg("--cvar-file", strPath, true);
	CHECK(stFileArg.bConsumedNext);
	CHECK_EQ(pCv->GetConfigFile(), strPath);
	const String strLoaded = pCv->ReloadConfigFile();
	CHECK(strLoaded.contains("test.file_var = 7"));
	CHECK_EQ((int64_t)pCv->GetValue("test.file_var"), (int64_t)7);
	CHECK_FALSE(bool(pCv->GetValue("test.file_bool")));
	CHECK_EQ(String(pCv->GetValue("test.file_str")), String("hello world"));
	CHECK_EQ(pCv->GetSetBy("test.file_var"), CVars::SET_BY_CONFIG_FILE);
	CHECK(pCv->ReloadConfigFile().is_empty());

	(void)pCv->Execute("test.file_var 9");
	{
		Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refFile.is_valid());
		refFile->store_string("test.file_var=3\n");
		refFile->flush();
	}
	const String strIgnored = pCv->ReloadConfigFile();
	CHECK(strIgnored.contains("ignored"));
	CHECK_EQ((int64_t)pCv->GetValue("test.file_var"), (int64_t)9);

	pCv->SetValue("con.ConfigPollMs", 100000);
	CHECK(pCv->PollConfigFile().is_empty());
	{
		Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refFile.is_valid());
		refFile->store_string("test.file_str=polled\n");
		refFile->flush();
	}
	CHECK(pCv->PollConfigFile().is_empty());
	CHECK_EQ(String(pCv->GetValue("test.file_str")), String("hello world"));
	pCv->SetValue("con.ConfigPollMs", 0);
	const String strPolled = pCv->PollConfigFile();
	CHECK(strPolled.contains("test.file_str = polled"));
	CHECK_EQ(String(pCv->GetValue("test.file_str")), String("polled"));

	fnTrackName("test.pending");
	const CVars::ArgResult stPendingArg = pCv->ParseEngineArg("--cvar=test.pending=8", "", false);
	CHECK_FALSE(stPendingArg.bError);
	(void)pCv->ApplyStartup();
	{
		Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refFile.is_valid());
		refFile->store_string("test.pending=1\n");
		refFile->flush();
	}
	(void)pCv->ReloadConfigFile();
	REQUIRE(pCv->RegisterVariable("test.pending", 0, "pending"));
	CHECK_EQ((int64_t)pCv->GetValue("test.pending"), (int64_t)8);
	CHECK_EQ(pCv->GetSetBy("test.pending"), CVars::SET_BY_COMMAND_LINE);

	const String strBuiltinOut = pCv->Execute("t.TimeScale 2.5");
	CHECK(strBuiltinOut.contains("t.TimeScale = 2.5"));
	CHECK(Math::is_equal_approx(Engine::get_singleton()->get_time_scale(), 2.5));
	(void)pCv->Execute("t.MaxFPS 33");
	CHECK_EQ(Engine::get_singleton()->get_max_fps(), 33);

	Engine::get_singleton()->set_max_fps(40);
	pCv->SyncEngineBuiltins(false, true);
	CHECK_EQ((int64_t)pCv->GetValue("t.MaxFPS"), (int64_t)40);
	CHECK_EQ(pCv->GetSetBy("t.MaxFPS"), CVars::SET_BY_COMMAND_LINE);
	ERR_PRINT_OFF;
	CHECK_FALSE(pCv->SetValueWithPriority("t.MaxFPS", 10, CVars::SET_BY_CONFIG_FILE));
	ERR_PRINT_ON;
	CHECK_EQ(Engine::get_singleton()->get_max_fps(), 40);

	CHECK(EngineDebugger::has_capture("cvar"));
	bool bCaptured = false;
	Array arrArgs;
	arrArgs.push_back("test.cli 8");
	const Error eCaptureError = pCv->HandleDebuggerMessage("exec", arrArgs, bCaptured);
	CHECK_EQ(eCaptureError, OK);
	CHECK(bCaptured);
	CHECK_EQ((int64_t)pCv->GetValue("test.cli"), (int64_t)8);
	bCaptured = false;
	const Error eIgnoredCapture = pCv->HandleDebuggerMessage("nope", Array(), bCaptured);
	CHECK_EQ(eIgnoredCapture, OK);
	CHECK_FALSE(bCaptured);
}

TEST_CASE("[CVars] a command registered after the startup lines is replayed once")
{
	CVars *pCv = CVars::GetSingleton();
	REQUIRE(pCv != nullptr);
	if (pCv->HasCommand("test.late"))
	{
		pCv->Unregister("test.late");
	}
	pCv->SetConfigFile("");
	const String strSavedArgs = strCommandArgs;
	strCommandArgs = String();

	// The command does not exist yet, so the line is parked instead of failing.
	const CVars::ArgResult stExecArg = pCv->ParseEngineArg("--cvar-exec=test.late alpha beta", "", false);
	CHECK_FALSE(stExecArg.bError);
	CHECK(pCv->ApplyStartup().is_empty());
	CHECK(strCommandArgs.is_empty());
	REQUIRE(pCv->RegisterCommand("test.late", callable_mp_static(TestCommand), "late command"));
	CHECK_EQ(strCommandArgs, String("alpha,beta"));

	// Replaying is one-shot, and a zero-argument line is parked as well.
	ERR_PRINT_OFF;
	CHECK_FALSE(pCv->RegisterCommand("test.late", callable_mp_static(TestCommand), "duplicate"));
	ERR_PRINT_ON;
	strCommandArgs = String("sentinel");
	pCv->Unregister("test.late");
	CHECK_FALSE(pCv->ParseEngineArg("--cvar-exec=test.late", "", false).bError);
	CHECK(pCv->ApplyStartup().is_empty());
	REQUIRE(pCv->RegisterCommand("test.late", callable_mp_static(TestCommand), "late command"));
	CHECK_EQ(strCommandArgs, String());

	pCv->Unregister("test.late");
	strCommandArgs = strSavedArgs;
}

TEST_CASE("[SceneTree][CVars] in-game console toggles and submits")
{
	CVars *pCv = CVars::GetSingleton();
	REQUIRE(pCv != nullptr);
	REQUIRE(SceneTree::get_singleton() != nullptr);
	if (pCv->HasVariable("test.ui_var"))
	{
		pCv->Unregister("test.ui_var");
	}
	REQUIRE(pCv->RegisterVariable("test.ui_var", 0, "ui"));

	CVarConsole *pConsole = memnew(CVarConsole);
	SceneTree::get_singleton()->get_root()->add_child(pConsole);
	CHECK_FALSE(pConsole->IsOpen());

	Ref<InputEventKey> refKey;
	refKey.instantiate();
	refKey->set_keycode(Key::F1);
	refKey->set_pressed(true);
	pConsole->input(refKey);
	CHECK(pConsole->IsOpen());
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());

	refKey->set_keycode(Key::QUOTELEFT);
	refKey->set_unicode('`');
	pConsole->input(refKey);
	CHECK(pConsole->IsOpen());
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());

	refKey->set_shift_pressed(true);
	refKey->set_unicode('~');
	pConsole->input(refKey);
	CHECK(pConsole->IsOpen());
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());
	refKey->set_shift_pressed(false);
	refKey->set_unicode(0);
	refKey->set_keycode(Key::ASCIITILDE);
	pConsole->input(refKey);
	CHECK(pConsole->IsOpen());
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());

	pConsole->SubmitLine("test.ui_var 4");
	CHECK_EQ((int64_t)pCv->GetValue("test.ui_var"), (int64_t)4);
	CHECK_EQ(pCv->GetSetBy("test.ui_var"), CVars::SET_BY_CONSOLE);

	SceneTree::get_singleton()->get_root()->remove_child(pConsole);
	memdelete(pConsole);
	pCv->Unregister("test.ui_var");
}

static String strEditorHookLine;

static String TestEditorHook(const String &strLine, const String &strLocalResult, void *pUserdata)
{
	(void)pUserdata;
	(void)strLocalResult;
	strEditorHookLine = strLine;
	return "sent to running game";
}

TEST_CASE("[SceneTree][CVars] editor console does not steal F1")
{
	CVars *pCv = CVars::GetSingleton();
	REQUIRE(pCv != nullptr);
	REQUIRE(SceneTree::get_singleton() != nullptr);
	if (pCv->HasVariable("test.editor_var"))
	{
		pCv->Unregister("test.editor_var");
	}
	REQUIRE(pCv->RegisterVariable("test.editor_var", 0, "editor"));

	CVarConsole *pConsole = memnew(CVarConsole);
	pConsole->SetEditorMode(true);
	pConsole->SetSubmittedHook(TestEditorHook, nullptr);
	SceneTree::get_singleton()->get_root()->add_child(pConsole);
	CHECK_FALSE(pConsole->IsOpen());

	Ref<InputEventKey> refKey;
	refKey.instantiate();
	refKey->set_pressed(true);
	refKey->set_keycode(Key::F1);
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());

	refKey->set_keycode(Key::QUOTELEFT);
	refKey->set_shift_pressed(true);
	refKey->set_unicode('~');
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());
	refKey->set_shift_pressed(false);
	refKey->set_unicode(0);

	pConsole->Toggle();
	CHECK(pConsole->IsOpen());
	refKey->set_keycode(Key::QUOTELEFT);
	refKey->set_unicode('`');
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());

	pConsole->Toggle();
	CHECK(pConsole->IsOpen());
	TypedArray<Node> arrEdits = pConsole->find_children("*", "LineEdit", true, false);
	REQUIRE(arrEdits.size() == 1);
	LineEdit *pEdit = Object::cast_to<LineEdit>(arrEdits[0]);
	REQUIRE(pEdit != nullptr);
	pEdit->grab_focus();
	Ref<InputEventKey> refThroughViewport;
	refThroughViewport.instantiate();
	refThroughViewport->set_pressed(true);
	refThroughViewport->set_keycode(Key::QUOTELEFT);
	refThroughViewport->set_unicode('`');
	SceneTree::get_singleton()->get_root()->push_input(refThroughViewport);
	CHECK_FALSE(pConsole->IsOpen());
	CHECK(pEdit->get_text().is_empty());

	pConsole->Toggle();
	CHECK(pConsole->IsOpen());
	refKey->set_keycode(Key::ESCAPE);
	pConsole->input(refKey);
	CHECK_FALSE(pConsole->IsOpen());

	strEditorHookLine = String();
	pConsole->SubmitLine("test.editor_var 3");
	CHECK_EQ(strEditorHookLine, "test.editor_var 3");
	CHECK_EQ((int64_t)pCv->GetValue("test.editor_var"), (int64_t)3);

	SceneTree::get_singleton()->get_root()->remove_child(pConsole);
	memdelete(pConsole);
	pCv->Unregister("test.editor_var");
}

} // namespace TestCVars
