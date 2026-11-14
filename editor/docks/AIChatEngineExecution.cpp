/**************************************************************************/
/*  AIChatEngineExecution.cpp                                                      */
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

#include "AIChatEngineExecution.h"

#include "core/config/engine.h"
#include "core/crypto/crypto_core.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_host_runtime.h"
#include "editor/docks/ai_chat_resume.h"
#include "editor/docks/gonggong_runtime_config.h"

void AIChatEngineExecution::_bind_methods()
{
}

AIChatEngineExecution::State &AIChatEngineExecution::GetState()
{
	return stState;
}

Dictionary AIChatEngineExecution::Failure(const String &strError)
{
	Dictionary mapResult;
	mapResult["ok"] = false;
	mapResult["error"] = strError;
	mapResult["running"] = false;
	mapResult["restart_needed"] = false;
	mapResult["next_action"] = "none";
	return mapResult;
}

String AIChatEngineExecution::PythonPath(const Dictionary &mapHostSnapshot, const String &strPurpose)
{
	const String strExplicit = mapHostSnapshot.get(strPurpose, "");
	if (!strExplicit.is_empty())
	{
		return strExplicit;
	}
	return GongGongRuntimeConfig::path(mapHostSnapshot.get("runtime", Dictionary()), strPurpose);
}

bool AIChatEngineExecution::ValidateCandidate(const Dictionary &mapHostSnapshot, String &out_strError)
{
	// The host additionally checks live conversation/work-order ownership.
	if (!bool(mapHostSnapshot.get("candidate_validated", false)))
	{
		out_strError = mapHostSnapshot.get("candidate_error", "Engine candidate authorization has not been validated by the host.");
		return false;
	}
	const Dictionary mapCandidate = mapHostSnapshot.get("engine_candidate", Dictionary());
	return mapCandidate.is_empty() || AIChatHostRuntime::validate_candidate_checkout(mapCandidate, out_strError);
}

Dictionary AIChatEngineExecution::HostBuildOptions()
{
	Dictionary mapOptions;
	mapOptions["platform"] = OS::get_singleton()->get_name() == "macOS" ? "macos" : OS::get_singleton()->get_name() == "Windows" ? "windows" : "linuxbsd";
	mapOptions["target"] = "editor";
	mapOptions["arch"] = Engine::get_singleton()->get_architecture_name();
#ifdef DEV_ENABLED
	mapOptions["dev_build"] = "yes";
#else
	mapOptions["dev_build"] = "no";
#endif
#ifdef REAL_T_IS_DOUBLE
	mapOptions["precision"] = "double";
#else
	mapOptions["precision"] = "single";
#endif
	mapOptions["module_mono_enabled"] = OS::get_singleton()->has_feature("mono") ? "yes" : "no";
#ifdef USE_VOLK
	mapOptions["use_volk"] = "yes";
#else
	mapOptions["use_volk"] = "no";
#endif
#ifdef ACCESSKIT_ENABLED
	mapOptions["accesskit"] = "yes";
#else
	mapOptions["accesskit"] = "no";
#endif
	return mapOptions;
}

Dictionary AIChatEngineExecution::Prepare(const String &strTool, const Dictionary &mapArguments, const Dictionary &mapHostSnapshot)
{
	if (stState.nBuildPid >= 0 || stState.bRestartArmed || !mapPreparedJournal.is_empty())
	{
		return Failure("An editor self-update is already in progress. Wait for its result instead of starting another one.");
	}
	if (!bool(mapHostSnapshot.get("tool_permission", false)))
	{
		return Failure("Local tool permission is disabled. No action was executed.");
	}
	String strSummary;
	bool bWantsRestart = true;
	if (strTool == "build_engine")
	{
		const Variant varRestart = mapArguments.get("restart", mapHostSnapshot.get("auto_restart", false));
		const Variant varExtra = mapArguments.get("scons_args", Array());
		if (varRestart.get_type() != Variant::BOOL || varExtra.get_type() != Variant::ARRAY || Array(varExtra).size() > 16)
		{
			return Failure("build_engine accepts an optional boolean restart and at most 16 string scons_args.");
		}
		for (const Variant &varValue : Array(varExtra))
		{
			if (varValue.get_type() != Variant::STRING || !String(varValue).contains("=") || String(varValue).length() > 200 || String(varValue).contains("\n") || String(varValue).contains("\r"))
			{
				return Failure("Each scons_args entry must be a single-line key=value string.");
			}
		}
		bWantsRestart = varRestart;
		strSummary = String(U"AI 请求重新编译当前引擎源码到独立的新编辑器文件，不覆盖正在运行的版本。\n编译完成后会校验新版本能启动且 AI 对话可用。\n") + (bWantsRestart ? String(U"校验通过后将保存场景并切换到新版本；本次对话会在新进程中自动继续。\n失败或新版本无响应时自动回滚到当前版本。") : String(U"本次只编译并校验，不切换版本。"));
	}
	else if (strTool == "restart_engine")
	{
		if (stState.strUpdatedExecutable.is_empty() || !FileAccess::exists(stState.strUpdatedExecutable))
		{
			return Failure("No verified side-by-side editor is available. Call build_engine first.");
		}
		strSummary = String(U"AI 请求切换到已编译并校验过的新编辑器：\n") + stState.strUpdatedExecutable + U"\n本次对话会在新进程中自动继续；新版本无响应时自动回滚。";
	}
	else if (strTool == "rollback_engine")
	{
		const String strRollback = mapHostSnapshot.get("rollback_executable", "");
		if (strRollback.is_empty() || !FileAccess::exists(strRollback))
		{
			return Failure("No previous editor executable is recorded, so there is nothing to roll back to.");
		}
		strSummary = String(U"AI 请求回退到上一个编辑器版本：\n") + strRollback + U"\n本次对话会在回退后的进程中自动继续。";
	}
	else
	{
		return Failure("Unknown editor self-update tool.");
	}
	stState.strToolCallId = mapHostSnapshot.get("tool_call_id", "");
	stState.strToolName = strTool;
	stState.mapToolArguments = mapArguments.duplicate(true);
	stState.bToolWantsRestart = bWantsRestart;
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["summary"] = strSummary;
	mapResult["next_action"] = strTool == "build_engine" ? "build" : "restart";
	return mapResult;
}

Dictionary AIChatEngineExecution::StartBuild(const Dictionary &mapHostSnapshot)
{
	if (stState.nBuildPid >= 0 || stState.bRestartArmed || !mapPreparedJournal.is_empty())
	{
		return Failure("An editor self-update is already in progress.");
	}
	if (!bool(mapHostSnapshot.get("tool_permission", false)) || (bool(mapHostSnapshot.get("busy", false)) && stState.strToolCallId.is_empty()))
	{
		return Failure("The host has not authorized this build in the current turn.");
	}
	String strError;
	if (!ValidateCandidate(mapHostSnapshot, strError))
	{
		return Failure(strError);
	}
	const Dictionary mapCandidate = mapHostSnapshot.get("engine_candidate", Dictionary());
	const String strRoot = mapCandidate.is_empty() ? String(mapHostSnapshot.get("engine_root", "")) : String(mapCandidate.get("source_root", ""));
	const String strWorker = strRoot.path_join("tools/editor_self_build.py");
	const String strPython = PythonPath(mapHostSnapshot, "build_python");
	const String strCache = mapHostSnapshot.get("cache_directory", "");
	const String strCurrent = mapHostSnapshot.get("current_executable", OS::get_singleton()->get_executable_path());
	if (!strRoot.is_absolute_path() || !FileAccess::exists(strWorker) || !AIChatHostRuntime::executable_exists(strPython) || !strCache.is_absolute_path() || !DirAccess::dir_exists_absolute(strCache) || !FileAccess::exists(strCurrent))
	{
		return Failure("The engine source, build Python, current executable or absolute cache directory is unavailable.");
	}
	const String strJob = vformat("ai_engine_build_%d_%s", OS::get_singleton()->get_process_id(), AIChatResume::make_token());
	stState.strBuildRoot = strRoot;
	stState.strStatusPath = strCache.path_join(strJob + ".json");
	stState.strLogPath = strCache.path_join(strJob + ".log");
	stState.strCancelPath = strCache.path_join(strJob + ".cancel");
	List<String> arrArguments;
	arrArguments.push_back("-u");
	arrArguments.push_back(strWorker);
	if (!mapCandidate.is_empty())
	{
		arrArguments.push_back("--binding");
		arrArguments.push_back(mapCandidate.get("binding_path", ""));
		arrArguments.push_back("--project");
		arrArguments.push_back(mapHostSnapshot.get("project_root", ""));
#ifdef MACOS_ENABLED
		arrArguments.push_back("--artifact-layout");
		arrArguments.push_back("native_app");
#endif
	}
	arrArguments.push_back("--host-build-options");
	arrArguments.push_back(JSON::stringify(HostBuildOptions()));
	arrArguments.push_back("--current");
	arrArguments.push_back(strCurrent);
	arrArguments.push_back("--status");
	arrArguments.push_back(stState.strStatusPath);
	arrArguments.push_back("--log");
	arrArguments.push_back(stState.strLogPath);
	arrArguments.push_back("--cancel");
	arrArguments.push_back(stState.strCancelPath);
	for (const String &strLine : String(mapHostSnapshot.get("build_arguments", "")).split("\n", false))
	{
		const String strOption = strLine.strip_edges();
		if (!strOption.is_empty())
		{
			arrArguments.push_back("--scons-arg");
			arrArguments.push_back(strOption);
		}
	}
	for (const Variant &varValue : Array(stState.mapToolArguments.get("scons_args", Array())))
	{
		arrArguments.push_back("--scons-arg");
		arrArguments.push_back(String(varValue).strip_edges());
	}
	GongGongRuntimeConfig::prepare_child_environment(mapHostSnapshot.get("runtime", Dictionary()));
	ProcessID nPid = -1;
	const Error eError = OS::get_singleton()->create_process(strPython, arrArguments, &nPid);
	if (eError != OK)
	{
		return Failure(vformat("The build worker could not be started (error %d).", int(eError)));
	}
	mapBuildSnapshot = mapHostSnapshot.duplicate(true);
	mapBuildSnapshot["current_executable"] = strCurrent;
	stState.nBuildPid = nPid;
	stState.nBuildStarted = OS::get_singleton()->get_ticks_msec();
	stState.strUpdatedExecutable = String();
	stState.bRestartRequested = false;
	bCancelRequested = false;
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["running"] = true;
	mapResult["stage"] = "preparing";
	mapResult["phase"] = String(U"正在准备构建并统计任务总量");
	mapResult["progress"] = 0;
	mapResult["next_action"] = "none";
	return mapResult;
}

Dictionary AIChatEngineExecution::ReadStatus(const String &strPath)
{
	if (!FileAccess::exists(strPath))
	{
		return Dictionary();
	}
	const Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::READ);
	if (refFile.is_valid() && refFile->get_length() < 16384)
	{
		Ref<JSON> refJson;
		refJson.instantiate();
		if (refJson->parse(refFile->get_as_text()) == OK && refJson->get_data().get_type() == Variant::DICTIONARY)
		{
			return refJson->get_data();
		}
	}
	return Dictionary();
}

Dictionary AIChatEngineExecution::PollBuild()
{
	Dictionary mapProjection;
	mapProjection["ok"] = true;
	mapProjection["running"] = stState.nBuildPid >= 0;
	mapProjection["restart_needed"] = false;
	mapProjection["next_action"] = "none";
	if (stState.nBuildPid < 0)
	{
		if (stState.bRestartArmed && OS::get_singleton()->get_ticks_msec() - stState.nRestartArmedMsec > 90000)
		{
			mapProjection = Failure("The editor did not restart, so the rebuilt version is not active. The running editor is unchanged.");
			mapProjection["next_action"] = "abandon_restart";
			mapProjection["result"] = mapProjection.duplicate(true);
		}
		else if (!stState.strUpdatedExecutable.is_empty() && stState.bRestartApproved && !stState.bRestartRequested)
		{
			mapProjection["restart_needed"] = true;
			mapProjection["next_action"] = "restart";
		}
		return mapProjection;
	}
	Dictionary mapStatus = ReadStatus(stState.strStatusPath);
	const bool bRunning = OS::get_singleton()->is_process_running(stState.nBuildPid);
	int nExitCode = -1;
	if (!bRunning)
	{
		nExitCode = OS::get_singleton()->get_process_exit_code(stState.nBuildPid);
		stState.nBuildPid = -1;
		// The final atomic status write can race the first read above.
		mapStatus = ReadStatus(stState.strStatusPath);
	}
	const String strStage = mapStatus.get("stage", "preparing");
	mapProjection["running"] = bRunning;
	mapProjection["status"] = mapStatus;
	mapProjection["stage"] = strStage;
	mapProjection["phase"] = strStage == "checking" ? String(U"构建完成，正在校验新编辑器") : strStage == "building" ? String(U"正在编译（构建节点估算）") : String(U"正在准备构建并统计任务总量");
	mapProjection["progress"] = CLAMP(int(mapStatus.get("percent", 0)), 0, 99);
	mapProjection["elapsed_seconds"] = int64_t((OS::get_singleton()->get_ticks_msec() - stState.nBuildStarted) / 1000);
	if (bRunning)
	{
		return mapProjection;
	}
	mapProjection["exit_code"] = nExitCode;
	const String strExecutable = String(mapStatus.get("executable", "")).replace("\\", "/").simplify_path();
	const String strCurrent = String(mapBuildSnapshot.get("current_executable", "")).replace("\\", "/").simplify_path();
	String strError = mapStatus.get("error", "");
	bool bReady = !bCancelRequested && nExitCode == 0 && strStage == "ready" && int(mapStatus.get("exit_code", -1)) == 0 && AIChatHostRuntime::self_update_path_matches(strExecutable, stState.strBuildRoot) && FileAccess::exists(strExecutable) && strExecutable.nocasecmp_to(strCurrent) != 0;
	const Dictionary mapCandidate = mapBuildSnapshot.get("engine_candidate", Dictionary());
	if (bReady && !mapCandidate.is_empty())
	{
		bReady = AIChatHostRuntime::ready_artifact_matches(strExecutable, mapStatus.get("candidate_manifest", Variant()), mapCandidate, strError);
	}
	Dictionary mapResult;
	mapResult["ok"] = bReady;
	mapResult["built"] = bReady;
	mapResult["restarted"] = false;
	mapResult["stage"] = strStage;
	mapResult["exit_code"] = nExitCode;
	mapResult["build_log"] = stState.strLogPath;
	if (bReady)
	{
		stState.strUpdatedExecutable = strExecutable;
		mapProjection["progress"] = 100;
		mapProjection["phase"] = String(U"编译与启动校验通过 · 新版本已就绪");
		mapResult["executable"] = strExecutable;
		mapResult["candidate_manifest"] = mapStatus.get("candidate_manifest", Variant());
		mapResult["note"] = "The build and its startup check passed. The edited C++ is NOT active until a restart.";
		const bool bRestart = !stState.strToolCallId.is_empty() ? stState.bToolWantsRestart : stState.bRestartApproved;
		mapProjection["restart_needed"] = bRestart;
		mapProjection["next_action"] = bRestart ? "restart" : stState.strToolCallId.is_empty() ? "none" : "finish_tool";
	}
	else
	{
		stState.bRestartApproved = false;
		stState.strUpdatedExecutable = String();
		if (strError.is_empty())
		{
			strError = bCancelRequested ? String("The build was cancelled; the running editor is unchanged.") : String("The worker did not produce a verified independent editor with a successful process exit.");
		}
		mapResult["error"] = strError;
		mapResult["note"] = "The running editor is unchanged and no version was switched. Read build_log before changing the source again.";
		mapProjection["ok"] = false;
		mapProjection["error"] = strError;
		mapProjection["next_action"] = stState.strToolCallId.is_empty() ? "none" : "finish_tool";
	}
	mapProjection["result"] = mapResult;
	return mapProjection;
}

Dictionary AIChatEngineExecution::CancelBuild()
{
	if (stState.nBuildPid < 0)
	{
		return Failure("No build worker is running.");
	}
	const Ref<FileAccess> refFile = FileAccess::open(stState.strCancelPath, FileAccess::WRITE);
	if (refFile.is_null())
	{
		return Failure("The build cancellation marker could not be written; the worker may still be running.");
	}
	refFile->store_string("cancel\n");
	refFile->flush();
	if (refFile->get_error() != OK)
	{
		return Failure("The build cancellation marker could not be persisted; the worker may still be running.");
	}
	bCancelRequested = true;
	stState.bRestartApproved = false;
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["running"] = true;
	mapResult["stage"] = "cancelling";
	mapResult["phase"] = String(U"正在取消编译及其子进程；不会重启编辑器。");
	mapResult["next_action"] = "none";
	return mapResult;
}

Dictionary AIChatEngineExecution::PrepareRestart(const Dictionary &mapHostSnapshot)
{
	if (stState.nBuildPid >= 0 || stState.bRestartArmed || !mapPreparedJournal.is_empty() || !bool(mapHostSnapshot.get("tool_permission", false)))
	{
		return Failure("A restart is already pending or local tool permission is disabled.");
	}
	const String strTarget = mapHostSnapshot.get("target_executable", stState.strToolName == "rollback_engine" ? mapHostSnapshot.get("rollback_executable", "") : Variant(stState.strUpdatedExecutable));
	const String strCurrent = mapHostSnapshot.get("current_executable", OS::get_singleton()->get_executable_path());
	const int nAttempt = mapHostSnapshot.get("restart_attempt", 1);
	if (!AIChatHostRuntime::executable_exists(strTarget) || nAttempt < 1 || nAttempt > AIChatResume::MAX_RESTART_ATTEMPTS || strTarget.replace("\\", "/").simplify_path().nocasecmp_to(strCurrent.replace("\\", "/").simplify_path()) == 0)
	{
		return Failure("The restart target or restart attempt is invalid; no version was switched.");
	}
	const String strDirectory = mapHostSnapshot.get("session_directory", "");
	if (!strDirectory.is_absolute_path() || !DirAccess::dir_exists_absolute(strDirectory))
	{
		return Failure("An absolute resume session directory is required.");
	}
	Dictionary mapJournal = Dictionary(mapHostSnapshot.get("journal", mapHostSnapshot.get("tool_checkpoint", Dictionary()))).duplicate(true);
	if (mapJournal.is_empty())
	{
		return Failure("The host must supply the complete restart checkpoint.");
	}
	const bool bToolDriven = mapHostSnapshot.get("tool_driven", false);
	if (bToolDriven && stState.strToolCallId.is_empty())
	{
		return Failure("The live tool call is missing from the restart checkpoint.");
	}
	Dictionary mapRestart;
	mapRestart["tool_call_id"] = bToolDriven ? stState.strToolCallId : String();
	mapRestart["tool_name"] = stState.strToolName;
	mapRestart["from_executable"] = strCurrent;
	mapRestart["to_executable"] = strTarget;
	mapRestart["token"] = AIChatResume::make_token();
	mapRestart["attempt"] = nAttempt;
	mapRestart["log"] = stState.strLogPath;
	const Dictionary mapCandidate = mapHostSnapshot.get("engine_candidate", Dictionary());
	if (!mapCandidate.is_empty() && stState.strToolName != "rollback_engine")
	{
		String strError;
		const String strManifest = AIChatHostRuntime::candidate_manifest_path(strTarget);
		const String strVerifier = String(mapHostSnapshot.get("engine_root", "")).path_join("tools/editor_source_manifest.py");
		if (!ValidateCandidate(mapHostSnapshot, strError) || !AIChatHostRuntime::artifact_matches(strTarget, strManifest, mapCandidate, strError) || !AIChatHostRuntime::source_matches(PythonPath(mapHostSnapshot, "workflow_python"), strVerifier, strManifest, mapCandidate, strError))
		{
			return Failure(strError);
		}
		mapRestart["engine_candidate"] = mapCandidate;
		mapRestart["candidate_manifest"] = strManifest;
	}
	mapJournal["version"] = AIChatResume::VERSION;
	mapJournal["restart"] = mapRestart;
	if (!AIChatResume::journal_valid(mapJournal))
	{
		return Failure("The complete restart checkpoint failed journal validation.");
	}
	if (bToolDriven)
	{
		const Array arrCalls = mapJournal["tool_calls"];
		const int nToolIndex = mapJournal["tool_index"];
		if (nToolIndex < 0 || nToolIndex >= arrCalls.size())
		{
			return Failure("The restart checkpoint does not point at the live tool call.");
		}
		const Dictionary mapCall = arrCalls[nToolIndex];
		const Dictionary mapFunction = mapCall["function"];
		if (mapCall.get("id", "") != stState.strToolCallId || mapFunction.get("name", "") != stState.strToolName)
		{
			return Failure("The restart checkpoint belongs to a different tool call.");
		}
	}
	AIChatResume stStorage;
	stStorage.directory = strDirectory;
	const String strJournalPath = mapHostSnapshot.get("journal_path", stStorage.journal_path());
	if (strJournalPath != stStorage.journal_path())
	{
		return Failure("The restart journal does not belong to the supplied session directory.");
	}
	// JSON journals decode all numbers as floats. Normalize through the same
	// lossless storage codec before strict recursive comparison at readback.
	String strEncodedJournal;
	Dictionary mapEncodingStats;
	if (AIChatResume::encode_journal(mapJournal, strEncodedJournal, mapEncodingStats) != OK || !AIChatResume::decode_journal(strEncodedJournal, mapPreparedJournal))
	{
		mapPreparedJournal.clear();
		return Failure("The complete restart checkpoint cannot be encoded within the journal safety limits.");
	}
	strPreparedDirectory = strDirectory;
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["journal"] = mapJournal;
	mapResult["restart"] = mapRestart;
	mapResult["target"] = strTarget;
	mapResult["token"] = mapRestart["token"];
	mapResult["next_action"] = "persist_restart";
	return mapResult;
}

Dictionary AIChatEngineExecution::ConfirmRestartPersistence(const Dictionary &mapHostSnapshot)
{
	if (mapPreparedJournal.is_empty() || stState.bRestartArmed || !bool(mapHostSnapshot.get("tool_permission", false)) || String(mapHostSnapshot.get("session_directory", "")) != strPreparedDirectory)
	{
		return Failure("The pending restart or its host authorization is no longer valid.");
	}
	AIChatResume stStorage;
	stStorage.directory = strPreparedDirectory;
	Dictionary mapStored;
	if (!stStorage.read_journal(mapStored) || !mapStored.recursive_equal(mapPreparedJournal, 0))
	{
		return Failure("The complete restart checkpoint has not been durably persisted; the editor must not restart.");
	}
	const Dictionary mapRestart = mapPreparedJournal["restart"];
	stStorage.clear_report();
	stState.strRestartTarget = mapRestart["to_executable"];
	stState.strRestartToken = mapRestart["token"];
	stState.nRestartAttempt = mapRestart["attempt"];
	stState.bRestartArmed = true;
	stState.nRestartArmedMsec = OS::get_singleton()->get_ticks_msec();
	stState.bRestartRequested = true;
	stState.bRestartApproved = false;
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["restart"] = mapRestart;
	mapResult["rollback_executable"] = mapRestart["from_executable"];
	mapResult["next_action"] = "save_and_restart";
	return mapResult;
}

Dictionary AIChatEngineExecution::ArmWatchdog(const Dictionary &mapHostSnapshot)
{
	if (!stState.bRestartArmed || stState.strRestartToken.is_empty() || mapPreparedJournal.is_empty() || !bool(mapHostSnapshot.get("tool_permission", false)))
	{
		return Failure("No durably persisted restart is armed.");
	}
	AIChatResume stStorage;
	stStorage.directory = strPreparedDirectory;
	Dictionary mapStored;
	if (!stStorage.read_journal(mapStored) || !mapStored.recursive_equal(mapPreparedJournal, 0))
	{
		return Failure("The restart checkpoint changed before editor exit.");
	}
	const String strPython = PythonPath(mapHostSnapshot, "workflow_python");
	const String strWatchdog = String(mapHostSnapshot.get("engine_root", "")).path_join("tools/editor_restart_watchdog.py");
	if (!AIChatHostRuntime::executable_exists(strPython) || !FileAccess::exists(strWatchdog))
	{
		return Failure("The restart supervisor is unavailable; no unverified version switch was scheduled.");
	}
	List<String> arrArguments;
	arrArguments.push_back("-u");
	arrArguments.push_back(strWatchdog);
	arrArguments.push_back("--new");
	arrArguments.push_back(stState.strRestartTarget);
	arrArguments.push_back("--old");
	arrArguments.push_back(Dictionary(mapPreparedJournal["restart"])["from_executable"]);
	arrArguments.push_back("--ack");
	arrArguments.push_back(strPreparedDirectory.path_join("ai_chat_restart_ack.json"));
	arrArguments.push_back("--report");
	arrArguments.push_back(strPreparedDirectory.path_join("ai_chat_restart_report.json"));
	arrArguments.push_back("--token");
	arrArguments.push_back(stState.strRestartToken);
	arrArguments.push_back("--wait-pid");
	arrArguments.push_back(itos(OS::get_singleton()->get_process_id()));
	Array arrEditorArguments;
	if (mapHostSnapshot.has("restart_arguments"))
	{
		arrEditorArguments = mapHostSnapshot["restart_arguments"];
	}
	else
	{
		for (const String &strArgument : OS::get_singleton()->get_restart_on_exit_arguments())
		{
			arrEditorArguments.push_back(strArgument);
		}
	}
	const Vector<uint8_t> arrEncoded = JSON::stringify(arrEditorArguments).to_utf8_buffer();
	arrArguments.push_back("--editor-args-b64");
	arrArguments.push_back(CryptoCore::b64_encode_str(arrEncoded.ptr(), arrEncoded.size()));
	GongGongRuntimeConfig::prepare_child_environment(mapHostSnapshot.get("runtime", Dictionary()));
	OS::get_singleton()->set_restart_on_exit(true, arrArguments);
	OS::get_singleton()->set_restart_on_exit_executable(strPython);
	strWatchdogPython = strPython;
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["supervised"] = true;
	mapResult["next_action"] = "exit";
	return mapResult;
}

void AIChatEngineExecution::AbandonRestart()
{
	if (!strWatchdogPython.is_empty() && OS::get_singleton()->get_restart_on_exit_executable() == strWatchdogPython)
	{
		for (const String &strArgument : OS::get_singleton()->get_restart_on_exit_arguments())
		{
			if (!stState.strRestartToken.is_empty() && strArgument == stState.strRestartToken)
			{
				OS::get_singleton()->set_restart_on_exit(false, List<String>());
				OS::get_singleton()->set_restart_on_exit_executable(String());
				break;
			}
		}
	}
	strWatchdogPython = String();
	// Never erase a journal owned by another or a newer handoff.
	if (!strPreparedDirectory.is_empty() && !mapPreparedJournal.is_empty())
	{
		AIChatResume stStorage;
		stStorage.directory = strPreparedDirectory;
		Dictionary mapStored;
		if (stStorage.read_journal(mapStored) && mapStored.recursive_equal(mapPreparedJournal, 0))
		{
			stStorage.clear_journal();
		}
	}
	stState.bRestartArmed = false;
	stState.bRestartRequested = false;
	stState.bRestartApproved = false;
	stState.strRestartTarget = String();
	stState.strRestartToken = String();
	stState.nRestartAttempt = 0;
	stState.nRestartArmedMsec = 0;
	mapPreparedJournal.clear();
	strPreparedDirectory = String();
}

void AIChatEngineExecution::FinishTool()
{
	stState.strToolCallId = String();
	stState.strToolName = String();
	stState.mapToolArguments.clear();
	stState.bToolWantsRestart = false;
}
