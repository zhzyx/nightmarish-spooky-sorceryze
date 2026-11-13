/**************************************************************************/
/*  GameReceiptGuard.cpp                                                  */
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

#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/ai_chat_host_runtime.h"
#include "editor/docks/gonggong_runtime_config.h"

Dictionary AIChatDock::GetGameReceiptGuard(String &out_strError, const Dictionary &mapRuntime, bool bPrepare, const Dictionary &mapReporting) const
{
	const String strPython = GongGongRuntimeConfig::path(mapRuntime, "workflow_python");
	const String strWorker = _engine_root().path_join("tools/editor_provenance_guard.py");
	List<String> arrArguments;
	for (const String &strArgument : { strWorker, String("--game-workspace"), _workflow_root(), String("--game-reporting"), JSON::stringify(mapReporting.is_empty() ? gonggong_reporting : mapReporting), String(bPrepare ? "--prepare-game" : "--recover-game") })
	{
		arrArguments.push_back(strArgument);
	}
	// Unlike execute() with captured output on Unix, this passes every argument
	// directly to the child, without a shell interpreting JSON or local paths.
	const Dictionary mapProcess = OS::get_singleton()->execute_with_pipe(strPython, arrArguments, false);
	const int64_t nPid = mapProcess.get("pid", -1);
	Ref<FileAccess> stOutputPipe = mapProcess.get("stdio", Variant());
	Ref<FileAccess> stErrorPipe = mapProcess.get("stderr", Variant());
	PackedByteArray arrOutput;
	PackedByteArray arrError;
	Error eResult = OK;
	Error eCleanup = OK;
	String strCleanupState = "not_requested";
	String strExecutionStage;
	int nExitCode = -1;
	if (nPid <= 0 || stOutputPipe.is_null() || stErrorPipe.is_null())
	{
		eResult = ERR_CANT_FORK;
		strExecutionStage = "process_start";
	}
	else
	{
		// Recovery can include helper operations with a 120-second timeout.
		const uint64_t nDeadline = OS::get_singleton()->get_ticks_msec() + 300000;
		const int64_t nOutputLimit = 4 * 1024 * 1024;
		while (eResult == OK)
		{
			// Check before draining: an exited child may still have its final JSON
			// buffered. Do not race its last write by checking only after a read.
			const bool bRunning = OS::get_singleton()->is_process_running(nPid);
			bool bReceived = false;
			for (const Ref<FileAccess> &stPipe : { stOutputPipe, stErrorPipe })
			{
				// Bound each stream's turn so a noisy stream cannot starve the
				// other, the deadline check, or process-state polling.
				for (int nChunk = 0; nChunk < 8; nChunk++)
				{
					const uint64_t nAvailable = stPipe->get_length();
					if (nAvailable == 0)
					{
						break;
					}
					const PackedByteArray arrBytes = stPipe->get_buffer(MIN(nAvailable, uint64_t(8192)));
					if (arrBytes.is_empty())
					{
						eResult = ERR_FILE_CANT_READ;
						strExecutionStage = "pipe_read";
						break;
					}
					bReceived = true;
					if (arrOutput.size() + arrError.size() + arrBytes.size() > nOutputLimit)
					{
						eResult = ERR_OUT_OF_MEMORY;
						strExecutionStage = "output_limit";
						break;
					}
					(stPipe == stOutputPipe ? arrOutput : arrError).append_array(arrBytes);
				}
				if (eResult != OK)
				{
					break;
				}
			}
			if (eResult != OK || (!bRunning && !bReceived))
			{
				break;
			}
			if (OS::get_singleton()->get_ticks_msec() >= nDeadline)
			{
				eResult = ERR_TIMEOUT;
				strExecutionStage = "timeout";
				break;
			}
			if (!bReceived)
			{
				OS::get_singleton()->delay_usec(1000);
			}
		}
	}
	if (nPid > 0)
	{
		if (eResult != OK && OS::get_singleton()->is_process_running(nPid))
		{
			// Use the host's owned-child cleanup. Its OS-level wait is not an
			// absolute wall-clock guarantee under operating-system failure.
			eCleanup = OS::get_singleton()->kill(nPid);
			// Successful host kill consumes the child on Unix and removes its
			// handle on Windows. A later exit-code lookup is not authoritative
			// (and Unix would report ECHILD); keep -1 as explicitly unknown.
			if (eCleanup == OK)
			{
				strCleanupState = "host_kill_returned";
			}
			else
			{
				strCleanupState = OS::get_singleton()->is_process_running(nPid) ? "still_running" : "exited";
				nExitCode = OS::get_singleton()->get_process_exit_code(nPid);
			}
		}
		else
		{
			nExitCode = OS::get_singleton()->get_process_exit_code(nPid);
		}
	}
	if (stOutputPipe.is_valid())
	{
		stOutputPipe->close();
	}
	if (stErrorPipe.is_valid())
	{
		stErrorPipe->close();
	}
	// Decode only after collecting bytes so chunk boundaries cannot split UTF-8.
	const String strOutput = arrOutput.is_empty() ? String() : String::utf8(reinterpret_cast<const char *>(arrOutput.ptr()), arrOutput.size());
	const String strError = arrError.is_empty() ? String() : String::utf8(reinterpret_cast<const char *>(arrError.ptr()), arrError.size());
	// Existence is diagnostic only: the host can resolve a Python name via PATH.
	const String strDiagnostic = vformat("game_receipt_guard_failed: eResult=%d nExitCode=%d stdout_utf8_bytes=%d stderr_utf8_bytes=%d python_file_exists=%s worker_file_exists=%s", int(eResult), nExitCode, arrOutput.size(), arrError.size(), FileAccess::exists(strPython) ? "true" : "false", FileAccess::exists(strWorker) ? "true" : "false");
	const String strJson = strOutput.strip_edges();
	if (eResult != OK || nExitCode != 0 || strJson.is_empty())
	{
		out_strError = strDiagnostic + " stage=" + (strExecutionStage.is_empty() ? String("execution_or_empty_output") : strExecutionStage) + vformat(" cleanup_result=%d cleanup_state=%s", int(eCleanup), strCleanupState) + " stdout=" + strOutput.left(1000) + " stderr=" + strError.left(1000);
		return Dictionary();
	}
	JSON stJson;
	const Error eParse = stJson.parse(strJson);
	if (eParse != OK)
	{
		out_strError = strDiagnostic + vformat(" stage=json_parse parse_error=%d parse_line=%d", int(eParse), stJson.get_error_line()) + " stderr=" + strError.left(1000);
		return Dictionary();
	}
	const Variant varParsed = stJson.get_data();
	if (varParsed.get_type() != Variant::DICTIONARY || !bool(Dictionary(varParsed).get("ok", false)))
	{
		out_strError = strDiagnostic + " stage=response_rejected stdout=" + strOutput.left(1000) + " stderr=" + strError.left(1000);
		return Dictionary();
	}
	if (!bPrepare)
	{
		return varParsed;
	}
	return AIChatHostRuntime::command_guard(varParsed, strPython, _engine_root(), out_strError);
}
