/**************************************************************************/
/*  TestAIChatDeliveryExecution.cpp                                                  */
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

#include "editor/docks/AIChatDeliveryExecution.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/os/process_id.h"
#include "tests/test_macros.h"

TEST_FORCE_LINK(TestAIChatDeliveryExecution)

// Godot disables exceptions: REQUIRE alone does not return from a failed test.
#define TEST_DELIVERY_REQUIRE(m_condition) \
	do \
	{ \
		const bool bCondition = (m_condition); \
		CHECK_MESSAGE(bCondition, #m_condition); \
		if (!bCondition) \
		{ \
			return; \
		} \
	} while (false)

namespace TestAIChatDeliveryExecution
{
const String SHA = "1234567890123456789012345678901234567890";

String Redact(const String &strText)
{
	return strText.replace("fixture-secret", "[redacted]");
}

class Fixture
{
public:
	Ref<AIChatDeliveryExecution> refExecution;
	String strRoot;
	Dictionary mapScope;
	Dictionary mapArguments;
	Dictionary mapHost;

	Fixture()
	{
		refExecution.instantiate();
		strRoot = OS::get_singleton()->get_temp_path().path_join("ai-delivery-domain-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(OS::get_singleton()->get_ticks_usec()));
		CHECK(DirAccess::make_dir_recursive_absolute(strRoot.path_join("tools")) == OK);
		CHECK(DirAccess::make_dir_recursive_absolute(strRoot.path_join("gonggong-delivery-finalization")) == OK);
		Dictionary mapBinding;
		mapBinding["version"] = 1;
		mapBinding["owner"] = "owner";
		mapBinding["issue"] = 1223;
		mapBinding["request_id"] = "isolated-test";
		mapBinding["source_root"] = strRoot;
		mapBinding["branch"] = "isolated-test";
		mapBinding["base_sha"] = SHA;
		mapBinding["common_dir"] = strRoot;
		mapBinding["repository"] = "example/isolated";
		mapBinding["origin"] = "https://github.com/example/isolated.git";
		mapBinding["binding_path"] = strRoot.path_join("binding.json");
		Write(String(mapBinding["binding_path"]), JSON::stringify(mapBinding));
		mapScope["engine_candidate"] = mapBinding;
		Dictionary mapValidation;
		mapValidation["ok"] = true;
		mapScope["candidate_validation"] = mapValidation;
		mapScope["owner"] = "owner";
		mapScope["snapshot_id"] = "snapshot";
		mapScope["generation"] = int64_t(7);
		mapScope["source_root"] = strRoot;
		mapScope["consultation_turn"] = false;
		mapScope["consultation_only"] = false;
		mapScope["is_child"] = false;
		mapScope["is_scheduled"] = false;
		mapScope["allow_tools"] = true;
		mapScope["auto_execute_commands"] = true;
		mapScope["retry_blocked_reason"] = "";
		mapArguments["pr"] = 17;
		mapArguments["candidate"] = SHA;
		mapArguments["signed_commit"] = SHA;
		Array arrItems;
		arrItems.push_back("isolated fixture");
		mapArguments["acceptance_items"] = arrItems;
		mapHost["scope"] = mapScope;
		mapHost["busy"] = true;
		mapHost["workflow_python"] = OS::get_singleton()->get_executable_path();
		mapHost["engine_root"] = strRoot;
		mapHost["cache_dir"] = strRoot;
		Write(strRoot.path_join("tools/editor_delivery_finalize.py"), "# isolated fixture\n");
		Write(strRoot.path_join("tools/editor_delivery_retry.py"), "# isolated fixture\n");
		Write(strRoot.path_join("tools/gonggong_bridge.py"), "# isolated fixture\n");
		refExecution->GetState().strRetryInstance = "isolated-host";
	}

	~Fixture()
	{
		refExecution->ClearFiles();
		Ref<DirAccess> refDirectory = DirAccess::open(strRoot);
		if (refDirectory.is_valid())
		{
			CHECK(refDirectory->erase_contents_recursive() == OK);
			refDirectory.unref();
			CHECK(DirAccess::remove_absolute(strRoot) == OK);
		}
	}

	static void Write(const String &strPath, const String &strText)
	{
		Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
		TEST_DELIVERY_REQUIRE(refFile.is_valid());
		CHECK(refFile->store_string(strText));
		refFile->flush();
		CHECK(refFile->get_error() == OK);
	}

	bool Prepare()
	{
		return bool(refExecution->PrepareDelivery(mapArguments, mapScope).get("ok", false));
	}

	bool Build()
	{
		String strExecutable;
		List<String> arrArguments;
		return bool(refExecution->BuildProcessArguments(mapHost, strExecutable, arrArguments).get("ok", false));
	}

	Dictionary Receipt()
	{
		const Dictionary mapRequest = refExecution->GetState().mapPendingRequest;
		Dictionary mapResult;
		mapResult["schema_version"] = 1;
		mapResult["kind"] = mapRequest.get("kind", "native_delivery_finalization");
		for (const String &strKey : { String("owner"), String("snapshot_id"), String("generation"), String("nonce"), String("source_root"), String("engine_pid"), String("host_instance_id"), String("host_action_request_id"), String("original_journal_sha256") })
		{
			if (mapRequest.has(strKey))
			{
				mapResult[strKey] = mapRequest[strKey];
			}
		}
		mapResult["issue"] = 1223;
		mapResult["request_id"] = "isolated-test";
		mapResult["completion_verified"] = true;
		mapResult["mutations_may_have_started"] = true;
		mapResult["ok"] = true;
		mapResult["stage"] = "complete";
		Dictionary mapFacts;
		mapFacts["repository"] = "example/isolated";
		mapFacts["issue"] = 1223;
		mapFacts["request_id"] = "isolated-test";
		mapFacts["candidate"] = SHA;
		mapFacts["signed_commit"] = SHA;
		mapFacts["pr_state"] = "MERGED";
		mapFacts["pull_request"] = "https://github.com/example/isolated/pull/17";
		mapFacts["delivered_paths_differ"] = Array();
		mapFacts["tree"] = SHA;
		mapFacts["current_main"] = SHA;
		mapFacts["merge_commit"] = SHA;
		Dictionary mapIssue;
		mapIssue["state"] = "CLOSED";
		mapIssue["reason"] = "COMPLETED";
		Array arrLabels;
		arrLabels.push_back("status:done");
		arrLabels.push_back("workspace:gonggong");
		mapIssue["labels"] = arrLabels;
		mapFacts["issue_receipt"] = mapIssue;
		mapResult["host_facts"] = mapFacts;
		Array arrChecks;
		Dictionary mapCheck;
		mapCheck["state"] = "SUCCESS";
		arrChecks.push_back(mapCheck);
		mapResult["ci"] = arrChecks;
		return mapResult;
	}

	Dictionary Process()
	{
		Dictionary mapResult;
		mapResult["delivery_scope"] = mapScope.duplicate(true);
		mapResult["busy"] = true;
		mapResult["exit_code"] = 0;
		mapResult["timed_out"] = false;
		Dictionary mapGuard;
		mapGuard["ok"] = true;
		mapResult["provenance_guard"] = mapGuard;
		return mapResult;
	}

	void Journal(const String &strName = "one.json")
	{
		Dictionary mapSaved;
		Dictionary mapJournalScope;
		mapJournalScope["owner"] = "owner";
		mapJournalScope["source_root"] = strRoot;
		mapJournalScope["issue"] = 1223;
		mapJournalScope["request_id"] = "isolated-test";
		mapJournalScope["candidate"] = SHA;
		mapJournalScope["signed_commit"] = SHA;
		mapSaved["scope"] = mapJournalScope;
		Dictionary mapReceipt;
		mapReceipt["snapshot_id"] = "snapshot";
		mapReceipt["completion_verified"] = true;
		mapReceipt["ok"] = false;
		mapReceipt["stage"] = "activation_pending";
		Dictionary mapFacts;
		mapFacts["pull_request"] = "https://github.com/example/isolated/pull/17";
		mapReceipt["host_facts"] = mapFacts;
		mapSaved["last_receipt"] = mapReceipt;
		Write(strRoot.path_join("gonggong-delivery-finalization").path_join(strName), JSON::stringify(mapSaved));
	}
};

TEST_CASE("[AIChatDeliveryExecution] Prepare validates scope and immutable candidate binding")
{
	Fixture stFixture;
	CHECK_FALSE(bool(stFixture.refExecution->PrepareDelivery(stFixture.mapArguments, Dictionary()).get("ok", true)));
	stFixture.mapArguments["pr"] = 1.5;
	CHECK_FALSE(stFixture.Prepare());
	stFixture.mapArguments["pr"] = 17;
	TEST_DELIVERY_REQUIRE(stFixture.Prepare());
	const Dictionary mapRequest = stFixture.refExecution->GetState().mapPendingRequest;
	CHECK(String(mapRequest["nonce"]).length() == 32);
	CHECK(Dictionary(mapRequest["binding"])["issue"].get_type() == Variant::INT);
	Dictionary mapChanged = stFixture.mapScope["engine_candidate"];
	mapChanged["branch"] = "changed-on-disk";
	Fixture::Write(String(mapChanged["binding_path"]), JSON::stringify(mapChanged));
	CHECK_FALSE(stFixture.Build());
	CHECK(stFixture.refExecution->GetState().strRequestPath.is_empty());
}

TEST_CASE("[AIChatDeliveryExecution] Mapped request owns files and cancellation preserves readback archive")
{
	Fixture stFixture;
	stFixture.mapScope["mapped_parent"] = true;
	CHECK_FALSE(stFixture.Prepare());
	Dictionary mapGuard;
	Array arrDecisions;
	Dictionary mapDecision;
	mapDecision["number"] = 1223;
	arrDecisions.push_back(mapDecision);
	mapGuard["live_decisions"] = arrDecisions;
	stFixture.mapScope["parent_completion_guard"] = mapGuard;
	Array arrVerified;
	arrVerified.push_back("independent evidence");
	stFixture.mapScope["verified_acceptance_items"] = arrVerified;
	TEST_DELIVERY_REQUIRE(stFixture.Prepare());
	stFixture.mapHost["scope"] = stFixture.mapScope;
	TEST_DELIVERY_REQUIRE(stFixture.Build());
	const String strRequest = stFixture.refExecution->GetState().strRequestPath;
	CHECK(FileAccess::exists(strRequest));
	CHECK(FileAccess::exists(strRequest + ".original.json"));
	const Dictionary mapSaved = JSON::parse_string(FileAccess::get_file_as_string(strRequest));
	CHECK(bool(mapSaved["active"]));
	TEST_DELIVERY_REQUIRE(mapSaved.get("acceptance_items", Variant()).get_type() == Variant::ARRAY && !Array(mapSaved["acceptance_items"]).is_empty());
	CHECK(Array(mapSaved["acceptance_items"])[0] == Variant("independent evidence"));
	CHECK(Dictionary(mapSaved["parent_completion_guard"])["host_liveness_path"] == Variant(strRequest));
	CHECK_FALSE(stFixture.Build());
	stFixture.refExecution->ClearFiles();
	CHECK_FALSE(FileAccess::exists(strRequest));
	CHECK(FileAccess::exists(strRequest + ".original.json"));
	CHECK_FALSE(stFixture.Build());
}

TEST_CASE("[AIChatDeliveryExecution] Receipt captures require exact identity process and host facts")
{
	for (int nCase = 0; nCase < 9; nCase++)
	{
		Fixture stFixture;
		TEST_DELIVERY_REQUIRE(stFixture.Prepare());
		TEST_DELIVERY_REQUIRE(stFixture.Build());
		Dictionary mapReceipt = stFixture.Receipt();
		Dictionary mapProcess = stFixture.Process();
		if (nCase == 1)
		{
			mapReceipt["nonce"] = "wrong";
		}
		else if (nCase == 2)
		{
			mapProcess["exit_code"] = 23;
		}
		else if (nCase == 3)
		{
			mapProcess["timed_out"] = true;
		}
		else if (nCase == 4)
		{
			mapProcess["cancelled"] = true;
		}
		else if (nCase == 5)
		{
			mapProcess["provenance_guard"] = Dictionary();
		}
		else if (nCase == 6)
		{
			Dictionary mapFacts = mapReceipt["host_facts"];
			mapFacts["candidate"] = "ffffffffffffffffffffffffffffffffffffffff";
		}
		else if (nCase == 7)
		{
			mapReceipt["ci"] = Array();
		}
		else if (nCase == 8)
		{
			mapReceipt["ok"] = "true";
		}
		Fixture::Write(stFixture.refExecution->GetState().strResultPath, JSON::stringify(mapReceipt));
		const Dictionary mapCaptured = stFixture.refExecution->CaptureResult(mapProcess);
		CHECK(bool(mapCaptured["ok"]) == (nCase == 0));
		CHECK(stFixture.refExecution->GetState().bQueuePaused);
		CHECK_FALSE(mapCaptured.has("delivery_scope"));
		CHECK(stFixture.refExecution->GetState().strRequestPath.is_empty());
		if (nCase > 0)
		{
			const Dictionary mapActual = mapCaptured["delivery_finalization"];
			const Dictionary mapDiagnostic = mapActual["private_worker_diagnostic"];
			CHECK(FileAccess::exists(mapDiagnostic["path"]));
		}
	}
}

TEST_CASE("[AIChatDeliveryExecution] Stale owner and bounded malformed results cannot finalize")
{
	Fixture stFixture;
	TEST_DELIVERY_REQUIRE(stFixture.Prepare());
	TEST_DELIVERY_REQUIRE(stFixture.Build());
	Fixture::Write(stFixture.refExecution->GetState().strResultPath, JSON::stringify(stFixture.Receipt()));
	Dictionary mapProcess = stFixture.Process();
	Dictionary mapScope = mapProcess["delivery_scope"];
	mapScope["generation"] = int64_t(8);
	const Dictionary mapCaptured = stFixture.refExecution->CaptureResult(mapProcess);
	CHECK_FALSE(bool(mapCaptured["ok"]));
	CHECK_FALSE(mapCaptured.has("delivery_finalization"));
	CHECK(stFixture.refExecution->GetState().mapReceipt.is_empty());
	for (int nCase = 0; nCase < 3; nCase++)
	{
		TEST_DELIVERY_REQUIRE(stFixture.Prepare());
		TEST_DELIVERY_REQUIRE(stFixture.Build());
		if (nCase != 0)
		{
			Fixture::Write(stFixture.refExecution->GetState().strResultPath, nCase == 1 ? "{broken" : String("x").repeat(256 * 1024 + 1));
		}
		const Dictionary mapUnknown = stFixture.refExecution->CaptureResult(stFixture.Process());
		CHECK_FALSE(bool(mapUnknown["ok"]));
		CHECK(stFixture.refExecution->GetState().bQueuePaused);
		CHECK(String(Dictionary(mapUnknown["delivery_finalization"])["error"]).begins_with("delivery_readback_unknown"));
	}
}

TEST_CASE("[AIChatDeliveryExecution] Optional pure redaction preserves unknown diagnostics without authorization")
{
	Fixture stFixture;
	TEST_DELIVERY_REQUIRE(stFixture.Prepare());
	TEST_DELIVERY_REQUIRE(stFixture.Build());
	Dictionary mapReceipt = stFixture.Receipt();
	mapReceipt["stage"] = "fixture-secret";
	mapReceipt["error"] = "fixture-secret failure";
	mapReceipt["private_diagnostic_ref"] = "private-ref";
	Fixture::Write(stFixture.refExecution->GetState().strResultPath, JSON::stringify(mapReceipt));
	Dictionary mapProcess = stFixture.Process();
	mapProcess["exit_code"] = 19;
	const Dictionary mapCaptured = stFixture.refExecution->CaptureResult(mapProcess, callable_mp_static(&Redact));
	CHECK_FALSE(bool(mapCaptured["ok"]));
	const Dictionary mapUnknown = mapCaptured["delivery_finalization"];
	CHECK(mapUnknown["worker_stage"] == Variant("[redacted]"));
	CHECK(mapUnknown["worker_error"] == Variant("[redacted] failure"));
	CHECK(mapUnknown["private_diagnostic_ref"] == Variant("private-ref"));
}

TEST_CASE("[AIChatDeliveryExecution] Pre-mutation rejection remains correctable")
{
	Fixture stFixture;
	TEST_DELIVERY_REQUIRE(stFixture.Prepare());
	TEST_DELIVERY_REQUIRE(stFixture.Build());
	Dictionary mapReceipt = stFixture.Receipt();
	mapReceipt["ok"] = false;
	mapReceipt["completion_verified"] = false;
	mapReceipt["mutations_may_have_started"] = false;
	mapReceipt["stage"] = "validation";
	Fixture::Write(stFixture.refExecution->GetState().strResultPath, JSON::stringify(mapReceipt));
	const Dictionary mapCaptured = stFixture.refExecution->CaptureResult(stFixture.Process());
	CHECK_FALSE(bool(mapCaptured["ok"]));
	CHECK(Dictionary(mapCaptured["delivery_finalization"])["stage"] == Variant("validation"));
	CHECK(stFixture.refExecution->GetState().mapReceipt.is_empty());
	CHECK_FALSE(stFixture.refExecution->GetState().bQueuePaused);
}

TEST_CASE("[AIChatDeliveryExecution] Retry selects one journal and rechecks permission durability and journal")
{
	Fixture stFixture;
	CHECK_FALSE(bool(stFixture.refExecution->PendingRetry(stFixture.mapScope).get("ok", true)));
	stFixture.Journal();
	Dictionary mapArgs;
	mapArgs["host_action_request_id"] = "host-action";
	TEST_DELIVERY_REQUIRE(bool(stFixture.refExecution->PrepareRetry(mapArgs, stFixture.mapScope).get("ok", false)));
	CHECK_FALSE(stFixture.Build());
	Dictionary mapRoute;
	mapRoute["delivery_retry_started"] = true;
	mapRoute["receipt_persistence_failed"] = false;
	stFixture.mapHost["retry_route_status"] = mapRoute;
	Dictionary mapChangedScope = stFixture.mapScope.duplicate(true);
	mapChangedScope["allow_tools"] = false;
	stFixture.mapHost["scope"] = mapChangedScope;
	CHECK_FALSE(stFixture.Build());
	stFixture.mapHost["scope"] = stFixture.mapScope;
	stFixture.Journal("two.json");
	CHECK_FALSE(stFixture.Build());
	CHECK(DirAccess::remove_absolute(stFixture.strRoot.path_join("gonggong-delivery-finalization/two.json")) == OK);
	TEST_DELIVERY_REQUIRE(stFixture.Build());
	Dictionary mapReceipt = stFixture.Receipt();
	mapReceipt["host_action_request_id"] = "different-action";
	Fixture::Write(stFixture.refExecution->GetState().strResultPath, JSON::stringify(mapReceipt));
	const Dictionary mapCaptured = stFixture.refExecution->CaptureResult(stFixture.Process());
	CHECK_FALSE(bool(mapCaptured["ok"]));
	CHECK(String(mapCaptured["delivery_worker_result_sha256"]).length() == 64);
}

#ifdef UNIX_ENABLED
TEST_CASE("[AIChatDeliveryExecution] Controlled local worker exit and cancellation never call installed workers")
{
	Fixture stFixture;
	const String strPython = OS::get_singleton()->has_environment("GONGGONG_TEST_WORKFLOW_PYTHON") ? OS::get_singleton()->get_environment("GONGGONG_TEST_WORKFLOW_PYTHON") : String("/usr/bin/python3");
	TEST_DELIVERY_REQUIRE(FileAccess::exists(strPython));
	stFixture.mapHost["workflow_python"] = strPython;
	// This worker reads only fixture-owned paths and never imports production code.
	Fixture::Write(stFixture.strRoot.path_join("tools/editor_delivery_finalize.py"),
			"import pathlib,sys\n"
			"a=sys.argv; p=pathlib.Path(a[a.index('--request')+1]); o=pathlib.Path(a[a.index('--out')+1])\n"
			"o.write_text((p.parent/'fixture-receipt.json').read_text())\n"
			"sys.exit(int((p.parent/'fixture-exit.txt').read_text()))\n");
	String strExecutable;
	List<String> arrArguments;
	Dictionary mapProcess;
	for (const int nExpectedExit : { 0, 19 })
	{
		TEST_DELIVERY_REQUIRE(stFixture.Prepare());
		TEST_DELIVERY_REQUIRE(bool(stFixture.refExecution->BuildProcessArguments(stFixture.mapHost, strExecutable, arrArguments).get("ok", false)));
		Fixture::Write(stFixture.strRoot.path_join("fixture-receipt.json"), JSON::stringify(stFixture.Receipt()));
		Fixture::Write(stFixture.strRoot.path_join("fixture-exit.txt"), itos(nExpectedExit));
		int nExitCode = -1;
		String strOutput;
		TEST_DELIVERY_REQUIRE(OS::get_singleton()->execute(strExecutable, arrArguments, &strOutput, &nExitCode) == OK);
		CHECK(nExitCode == nExpectedExit);
		mapProcess = stFixture.Process();
		mapProcess["exit_code"] = nExitCode;
		CHECK(bool(stFixture.refExecution->CaptureResult(mapProcess)["ok"]) == (nExpectedExit == 0));
	}
	// A child observing revoked request liveness exits without publishing a result.
	Fixture::Write(stFixture.strRoot.path_join("tools/editor_delivery_finalize.py"),
			"import pathlib,sys,time\n"
			"a=sys.argv;p=pathlib.Path(a[a.index('--request')+1])\n"
			"for i in range(200):\n"
			" if not p.exists(): sys.exit(0)\n"
			" time.sleep(.01)\n"
			"sys.exit(31)\n");
	TEST_DELIVERY_REQUIRE(stFixture.Prepare());
	arrArguments.clear();
	TEST_DELIVERY_REQUIRE(bool(stFixture.refExecution->BuildProcessArguments(stFixture.mapHost, strExecutable, arrArguments).get("ok", false)));
	ProcessID nPid = -1;
	TEST_DELIVERY_REQUIRE(OS::get_singleton()->create_process(strExecutable, arrArguments, &nPid) == OK);
	stFixture.refExecution->ClearFiles();
	for (int nAttempt = 0; nAttempt < 300 && OS::get_singleton()->is_process_running(nPid); nAttempt++)
	{
		OS::get_singleton()->delay_usec(10000);
	}
	const bool bRunning = OS::get_singleton()->is_process_running(nPid);
	CHECK_FALSE(bRunning);
	if (bRunning)
	{
		OS::get_singleton()->kill(nPid);
	}
	else
	{
		CHECK(OS::get_singleton()->get_process_exit_code(nPid) == 0);
	}
	mapProcess = stFixture.Process();
	mapProcess["cancelled"] = true;
	CHECK_FALSE(bool(stFixture.refExecution->CaptureResult(mapProcess)["ok"]));
}
#endif
}

#undef TEST_DELIVERY_REQUIRE
