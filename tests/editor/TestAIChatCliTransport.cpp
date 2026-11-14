/**************************************************************************/
/*  TestAIChatCliTransport.cpp                                            */
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

// Preserve CPP_CODING_STANDARD.md v1.1 Allman style during formatter transition.
// clang-format off
#include "tests/test_macros.h"
TEST_FORCE_LINK(TestAIChatCliTransport)

#ifdef TOOLS_ENABLED
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "editor/docks/AIChatCliTransport.h"

namespace TestAIChatCliTransport
{
TEST_CASE("[AIChat][AICore] CLI incremental reuse requires the complete history prefix")
{
	Vector<String> arrPrevious;
	arrPrevious.push_back("first");
	Vector<String> arrCurrent = arrPrevious;
	arrCurrent.push_back("second");
	CHECK(AIChatCliTransport::IsHistoryPrefix(arrPrevious, arrCurrent));
	arrCurrent.write[0] = "changed";
	CHECK_FALSE(AIChatCliTransport::IsHistoryPrefix(arrPrevious, arrCurrent));
	arrCurrent.clear();
	CHECK_FALSE(AIChatCliTransport::IsHistoryPrefix(arrPrevious, arrCurrent));
}

TEST_CASE("[AIChat][AICore] CLI transport owns process and temporary request lifetime")
{
	Ref<AIChatCliTransport> refTransport;
	refTransport.instantiate();
	AIChatCliRequest stRequest;
	stRequest.strExecutable = OS::get_singleton()->get_executable_path();
	stRequest.arrPrefixArguments.push_back("--version");
	stRequest.strBody = "{}";
	stRequest.strTempPrefix = "godot_cli_transport_test";
	REQUIRE(refTransport->Submit(stRequest, 27) == OK);
	const String strRequest = refTransport->GetRequestPath();
	REQUIRE(FileAccess::exists(strRequest));
	AIChatCliEvent stEvent;
	const uint64_t nDeadline = OS::get_singleton()->get_ticks_msec() + 10000;
	while (stEvent.eKind == AIChatCliEvent::Kind::None && OS::get_singleton()->get_ticks_msec() < nDeadline)
	{
		stEvent = refTransport->Poll();
		OS::get_singleton()->delay_usec(1000);
	}
	CHECK(stEvent.eKind == AIChatCliEvent::Kind::Completed);
	CHECK(stEvent.nGeneration == 27);
	CHECK_FALSE(stEvent.arrBody.is_empty());
	CHECK_FALSE(refTransport->HasProcess());
	CHECK_FALSE(FileAccess::exists(strRequest));
}

TEST_CASE("[AIChat][AICore] CLI cancellation detaches the request and prevents late delivery")
{
	Ref<AIChatCliTransport> refTransport;
	refTransport.instantiate();
	AIChatCliRequest stRequest;
	stRequest.strExecutable = OS::get_singleton()->get_executable_path();
	stRequest.arrPrefixArguments.push_back("--version");
	stRequest.strBody = "{}";
	stRequest.strTempPrefix = "godot_cli_cancel_test";
	REQUIRE(refTransport->Submit(stRequest, 28) == OK);
	const String strRequest = refTransport->GetRequestPath();
	refTransport->Cancel();
	CHECK_FALSE(refTransport->HasProcess());
	CHECK_FALSE(FileAccess::exists(strRequest));
	CHECK(refTransport->Poll().eKind == AIChatCliEvent::Kind::None);
}

TEST_CASE("[AIChat][AICore] Codex stage frames precede the final response in both session modes")
{
	Error eError = OK;
	Ref<DirAccess> refDirectory = DirAccess::create_temp("godot_codex_transport", false, &eError);
	REQUIRE(eError == OK);
	REQUIRE(refDirectory.is_valid());
	const String strRoot = refDirectory->get_current_dir();
	Ref<FileAccess> refProject = FileAccess::open(strRoot.path_join("project.godot"), FileAccess::WRITE);
	REQUIRE(refProject.is_valid());
	REQUIRE(refProject->store_string("config_version=5\n"));
	refProject.unref();
	const String strScript = strRoot.path_join("progress.gd");
	Ref<FileAccess> refScript = FileAccess::open(strScript, FileAccess::WRITE);
	REQUIRE(refScript.is_valid());
	REQUIRE(refScript->store_string(
			"extends SceneTree\n"
			"func _initialize():\n"
			"\tprint('{\"event\":\"codex_progress\",\"activity\":\"thread_started\"}')\n"
			"\tprint('{\"event\":\"codex_progress\",\"activity\":\"content_preview\",\"content_preview\":\"hello\"}')\n"
			"\tprint('{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"done\"},\"finish_reason\":\"stop\"}]}')\n"
			"\tquit()\n"));
	refScript.unref();
	for (const bool bPersistent : { false, true })
	{
		Ref<AIChatCliTransport> refTransport;
		refTransport.instantiate();
		AIChatCliRequest stRequest;
		stRequest.strExecutable = OS::get_singleton()->get_executable_path();
		for (const String &strArgument : { String("--headless"), String("--no-header"), String("--path"), strRoot, String("--script"), strScript })
		{
			stRequest.arrPrefixArguments.push_back(strArgument);
		}
		stRequest.strBody = "{}";
		stRequest.strTempPrefix = "godot_codex_frames";
		stRequest.bCodex = true;
		stRequest.bPersistent = bPersistent;
		REQUIRE(refTransport->Submit(stRequest, 29) == OK);
		int nProgress = 0;
		AIChatCliEvent stEvent;
		const uint64_t nDeadline = OS::get_singleton()->get_ticks_msec() + 10000;
		while (OS::get_singleton()->get_ticks_msec() < nDeadline)
		{
			stEvent = refTransport->Poll();
			if (stEvent.eKind == AIChatCliEvent::Kind::Progress)
			{
				CHECK(String(stEvent.mapPayload["event"]) == "codex_progress");
				++nProgress;
			}
			if (stEvent.eKind == AIChatCliEvent::Kind::Completed || stEvent.eKind == AIChatCliEvent::Kind::Failed)
			{
				break;
			}
			OS::get_singleton()->delay_usec(1000);
		}
		CHECK(nProgress == 2);
		CHECK(stEvent.eKind == AIChatCliEvent::Kind::Completed);
		CHECK(stEvent.nGeneration == 29);
		JSON stResponse;
		REQUIRE(stResponse.parse(String::utf8(reinterpret_cast<const char *>(stEvent.arrBody.ptr()), stEvent.arrBody.size())) == OK);
		REQUIRE(stResponse.get_data().get_type() == Variant::DICTIONARY);
		CHECK(Dictionary(stResponse.get_data()).has("choices"));
		refTransport->Cancel();
	}
}
}
#endif
// clang-format on
