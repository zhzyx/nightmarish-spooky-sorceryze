/**************************************************************************/
/*  AIChatEngineExecution.h                                                      */
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

#pragma once

#include "core/object/ref_counted.h"
#include "core/variant/dictionary.h"

// Main-thread domain owner. The host supplies authorization and the complete
// checkpoint; this class owns subprocesses and validates durable handoffs.
class AIChatEngineExecution : public RefCounted
{
	GDCLASS(AIChatEngineExecution, RefCounted);

public:
	struct State
	{
		int64_t nBuildPid = -1;
		uint64_t nBuildStarted = 0;
		String strBuildRoot;
		String strStatusPath;
		String strLogPath;
		String strCancelPath;
		String strUpdatedExecutable;
		String strDialogAction;
		bool bRestartApproved = false;
		bool bRestartRequested = false;
		String strToolCallId;
		String strToolName;
		Dictionary mapToolArguments;
		bool bToolWantsRestart = false;
		String strRestartTarget;
		String strRestartToken;
		int nRestartAttempt = 0;
		bool bRestartArmed = false;
		uint64_t nRestartArmedMsec = 0;
	};

	State &GetState();
	Dictionary Prepare(const String &strTool, const Dictionary &mapArguments, const Dictionary &mapHostSnapshot);
	Dictionary StartBuild(const Dictionary &mapHostSnapshot);
	Dictionary PollBuild();
	Dictionary CancelBuild();
	Dictionary PrepareRestart(const Dictionary &mapHostSnapshot);
	// Call after the host writes PrepareRestart's complete journal, before save/exit.
	Dictionary ConfirmRestartPersistence(const Dictionary &mapHostSnapshot);
	// Call from the host's actual editor-exit notification, after confirmation.
	Dictionary ArmWatchdog(const Dictionary &mapHostSnapshot);
	void AbandonRestart();
	void FinishTool();

protected:
	static void _bind_methods();

private:
	State stState;
	Dictionary mapBuildSnapshot;
	Dictionary mapPreparedJournal;
	String strPreparedDirectory;
	bool bCancelRequested = false;
	String strWatchdogPython;

	static Dictionary Failure(const String &strError);
	static bool ValidateCandidate(const Dictionary &mapHostSnapshot, String &out_strError);
	static String PythonPath(const Dictionary &mapHostSnapshot, const String &strPurpose);
	static Dictionary HostBuildOptions();
	static Dictionary ReadStatus(const String &strPath);
};
