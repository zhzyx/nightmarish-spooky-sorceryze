/**************************************************************************/
/*  AIChatCliTransport.cpp                                                */
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
#include "AIChatCliTransport.h"

#include "core/io/dir_access.h"
#include "core/io/json.h"
#include "core/os/os.h"

AIChatCliTransport::~AIChatCliTransport()
{
	Cancel();
}

void AIChatCliTransport::_bind_methods()
{
}

bool AIChatCliTransport::IsHistoryPrefix(const Vector<String> &arrPrevious, const Vector<String> &arrCurrent)
{
	if (arrPrevious.size() > arrCurrent.size())
	{
		return false;
	}
	for (int nIndex = 0; nIndex < arrPrevious.size(); ++nIndex)
	{
		if (arrPrevious[nIndex] != arrCurrent[nIndex])
		{
			return false;
		}
	}
	return true;
}

AIChatCliPlan AIChatCliTransport::PlanSubmission(const String &strConfiguration, const Vector<String> &arrMessages, bool bIncremental, bool bPersistent)
{
	AIChatCliPlan stPlan;
	stPlan.bRebuilding = HasProcess();
	stPlan.bReused = bPersistent && stSession.bPersistent && IsProcessAlive() && !bWaiting && stSession.strCliConfiguration == strConfiguration;
	stPlan.bReset = bIncremental && bResetRequested && stPlan.bReused;
	stPlan.bIncremental = bIncremental && !stPlan.bReset && stPlan.bReused && IsHistoryPrefix(stSession.arrCliSentMessages, arrMessages);
	if (bIncremental && !stPlan.bIncremental && !stPlan.bReset)
	{
		stPlan.bReused = false;
	}
	stPlan.nPreviousCount = stPlan.bIncremental ? stSession.arrCliSentMessages.size() : 0;
	bResetRequested = false;
	if (!stPlan.bReused)
	{
		Cancel();
	}
	return stPlan;
}

Error AIChatCliTransport::WriteRequest(const AIChatCliRequest &stRequest)
{
	if (stRequest.strBody.utf8().length() > 1024 * 1024)
	{
		return ERR_OUT_OF_MEMORY;
	}
	Error eError = OK;
	refRequestFile = FileAccess::create_temp(FileAccess::WRITE_READ, stRequest.strTempPrefix, "json", false, &eError);
	if (refRequestFile.is_null() || eError != OK)
	{
		return eError == OK ? ERR_CANT_CREATE : eError;
	}
	strRequestPath = refRequestFile->get_path_absolute();
	const bool bStored = refRequestFile->store_string(stRequest.strBody);
	refRequestFile->flush();
	eError = refRequestFile->get_error();
	refRequestFile->close();
	if (!bStored || eError != OK || FileAccess::get_file_as_string(strRequestPath) != stRequest.strBody)
	{
		ReleaseRequest();
		return eError == OK ? ERR_FILE_CANT_WRITE : eError;
	}
	return OK;
}

Error AIChatCliTransport::Submit(const AIChatCliRequest &stRequest, uint64_t nGeneration)
{
	if (bWaiting)
	{
		return ERR_BUSY;
	}
	if (stRequest.strExecutable.is_empty() || stRequest.strTempPrefix.is_empty())
	{
		return ERR_INVALID_PARAMETER;
	}
	if (stRequest.bReuse && (!IsProcessAlive() || stSession.strCliConfiguration != stRequest.strConfiguration || !stSession.bPersistent))
	{
		return ERR_CANT_CONNECT;
	}
	if (!stRequest.bReuse)
	{
		Cancel();
	}
	const Error eWrite = WriteRequest(stRequest);
	if (eWrite != OK)
	{
		return eWrite;
	}
	if (!stRequest.bReuse)
	{
		List<String> arrArguments(stRequest.arrPrefixArguments);
		if (stRequest.bPassRequestPath)
		{
			arrArguments.push_back(strRequestPath);
		}
		for (const String &strArgument : stRequest.arrSuffixArguments)
		{
			arrArguments.push_back(strArgument);
		}
		const Dictionary mapProcess = OS::get_singleton()->execute_with_pipe(stRequest.strExecutable, arrArguments, false);
		if (mapProcess.has("pid"))
		{
			stSession.nCliProcess = mapProcess["pid"];
		}
		if (!mapProcess.has("pid") || !mapProcess.has("stdio") || !mapProcess.has("stderr"))
		{
			Cancel();
			return ERR_CANT_FORK;
		}
		stSession.refCliStdout = mapProcess["stdio"];
		stSession.refCliStderr = mapProcess["stderr"];
	}
	if (stRequest.bPersistent)
	{
		Dictionary mapSubmission = stRequest.mapSubmission.duplicate(true);
		mapSubmission["path"] = strRequestPath;
		if (!stSession.refCliStdout->store_string(JSON::stringify(mapSubmission) + "\n"))
		{
			Cancel();
			return ERR_FILE_CANT_WRITE;
		}
	}
	stSession.bPersistent = stRequest.bPersistent;
	stSession.bCodex = stRequest.bCodex;
	stSession.strCliConfiguration = stRequest.strConfiguration;
	stSession.arrCliSentMessages = stRequest.arrSentMessages;
	nRequestGeneration = nGeneration;
	nStartedMillis = OS::get_singleton()->get_ticks_msec();
	nLastActivityMillis = nStartedMillis;
	bWaiting = true;
	bTruncated = false;
	arrOutput.clear();
	strPartial = String();
	return OK;
}

bool AIChatCliTransport::ReadPipes()
{
	bool bReceived = false;
	for (const Ref<FileAccess> &refPipe : { stSession.refCliStdout, stSession.refCliStderr })
	{
		if (refPipe.is_null())
		{
			continue;
		}
		PackedByteArray arrBytes;
		arrBytes.resize(16384);
		const uint64_t nRead = refPipe->get_buffer(arrBytes.ptrw(), arrBytes.size());
		if (nRead == 0 || nRead > uint64_t(arrBytes.size()))
		{
			continue;
		}
		bReceived = true;
		arrBytes.resize(nRead);
		if (refPipe != stSession.refCliStdout)
		{
			continue;
		}
		if (arrOutput.size() + arrBytes.size() > 2 * 1024 * 1024)
		{
			bTruncated = true;
		}
		else
		{
			arrOutput.append_array(arrBytes);
		}
	}
	return bReceived;
}

int AIChatCliTransport::FindLine() const
{
	if (!stSession.bPersistent && !stSession.bCodex)
	{
		return -1;
	}
	for (int nIndex = 0; nIndex < arrOutput.size(); ++nIndex)
	{
		if (arrOutput[nIndex] == '\n')
		{
			return nIndex;
		}
	}
	return -1;
}

AIChatCliEvent AIChatCliTransport::ConsumeProgress(const Dictionary &mapEnvelope, int nLine, uint64_t nNow)
{
	AIChatCliEvent stEvent;
	stEvent.nGeneration = nRequestGeneration;
	stEvent.mapPayload = mapEnvelope;
	arrOutput = arrOutput.slice(nLine + 1);
	if (!bWaiting && !stSession.bCodex)
	{
		return AIChatCliEvent();
	}
	const String strKind = mapEnvelope.get("event", "");
	if (strKind == "command_result")
	{
		stEvent.eKind = AIChatCliEvent::Kind::CommandResult;
		nLastActivityMillis = nNow;
		return stEvent;
	}
	stEvent.eKind = AIChatCliEvent::Kind::Progress;
	if (stSession.bCodex)
	{
		nLastActivityMillis = nNow;
		return stEvent;
	}
	const String strActivity = mapEnvelope.get("activity", "");
	const Variant varDelta = mapEnvelope.get("content_delta", Variant());
	if (varDelta.get_type() != Variant::STRING || (strActivity != "connecting" && strActivity != "waiting" && strActivity != "analyzing" && strActivity != "responding" && strActivity != "tool_pending" && strActivity != "searching" && strActivity != "executing"))
	{
		return stEvent;
	}
	nLastActivityMillis = nNow;
	if (strActivity == "executing")
	{
		nStartedMillis = nNow;
	}
	const String strDelta = varDelta;
	if (strPartial.utf8().length() + strDelta.utf8().length() > 2 * 1024 * 1024)
	{
		bTruncated = true;
	}
	else
	{
		strPartial += strDelta;
		stEvent.mapPayload["content"] = strPartial;
	}
	return stEvent;
}

AIChatCliEvent AIChatCliTransport::Poll()
{
	AIChatCliEvent stEvent;
	if (!HasProcess())
	{
		return stEvent;
	}
	const bool bReceived = ReadPipes();
	const uint64_t nNow = OS::get_singleton()->get_ticks_msec();
	const bool bTimeout = bWaiting && (nNow - nLastActivityMillis > 310000 || nNow - nStartedMillis > 1810000);
	const bool bRunning = IsProcessAlive();
	int nLine = FindLine();
	if (stSession.bPersistent && !bWaiting && nLine < 0 && !bRunning)
	{
		stEvent.eKind = AIChatCliEvent::Kind::Closed;
		Cancel();
		return stEvent;
	}
	Dictionary mapEnvelope;
	if (nLine >= 0)
	{
		JSON stEnvelope;
		if (stEnvelope.parse(String::utf8(reinterpret_cast<const char *>(arrOutput.ptr()), nLine)) == OK && stEnvelope.get_data().get_type() == Variant::DICTIONARY)
		{
			mapEnvelope = stEnvelope.get_data();
		}
	}
	if (nLine >= 0 && !bTimeout && !bTruncated && mapEnvelope.get("event", "") == "codex_progress" && stSession.bCodex)
	{
		return ConsumeProgress(mapEnvelope, nLine, nNow);
	}
	if (stSession.bCodex && !stSession.bPersistent)
	{
		nLine = -1;
	}
	if (!bTimeout && !bTruncated && nLine < 0 && (bRunning || bReceived))
	{
		return stEvent;
	}
	stEvent.nExitCode = nLine >= 0 ? 0 : OS::get_singleton()->get_process_exit_code(stSession.nCliProcess);
	stEvent.nGeneration = nRequestGeneration;
	stEvent.arrBody = nLine >= 0 ? arrOutput.slice(0, nLine) : arrOutput;
	JSON stResponse;
	if (stResponse.parse(String::utf8(reinterpret_cast<const char *>(stEvent.arrBody.ptr()), stEvent.arrBody.size())) == OK && stResponse.get_data().get_type() == Variant::DICTIONARY)
	{
		mapEnvelope = stResponse.get_data();
	}
	if (nLine >= 0 && (mapEnvelope.get("event", "") == "command_result" || (mapEnvelope.get("event", "") == "progress" && nNow - nStartedMillis <= 1810000)))
	{
		return ConsumeProgress(mapEnvelope, nLine, nNow);
	}
	if (mapEnvelope.has("error"))
	{
		stEvent.nExitCode = 1;
	}
	stEvent.mapPayload = mapEnvelope;
	stEvent.bTimedOut = bTimeout;
	stEvent.bTruncated = bTruncated;
	stEvent.eKind = bTimeout || bTruncated || stEvent.nExitCode != 0 ? AIChatCliEvent::Kind::Failed : AIChatCliEvent::Kind::Completed;
	if (stSession.bPersistent && nLine >= 0 && stEvent.eKind == AIChatCliEvent::Kind::Completed)
	{
		arrOutput = arrOutput.slice(nLine + 1);
		bWaiting = false;
		ReleaseRequest();
	}
	else
	{
		Cancel();
	}
	return stEvent;
}

void AIChatCliTransport::CancelSession(AIChatSessionTransport &stSaved)
{
	if (stSaved.nCliProcess >= 0 && OS::get_singleton()->is_process_running(stSaved.nCliProcess))
	{
		OS::get_singleton()->kill(stSaved.nCliProcess);
	}
	stSaved = AIChatSessionTransport();
}

void AIChatCliTransport::Cancel()
{
	CancelSession(stSession);
	bWaiting = false;
	bResetRequested = false;
	ReleaseRequest();
	arrOutput.clear();
}

void AIChatCliTransport::ReleaseRequest()
{
	refRequestFile.unref();
	if (!strRequestPath.is_empty() && FileAccess::exists(strRequestPath))
	{
		DirAccess::remove_absolute(strRequestPath);
	}
	strRequestPath = String();
}

void AIChatCliTransport::RequestReset()
{
	bResetRequested = true;
}

bool AIChatCliTransport::IsProcessAlive() const
{
	return HasProcess() && OS::get_singleton()->is_process_running(stSession.nCliProcess);
}

bool AIChatCliTransport::HasProcess() const
{
	return stSession.nCliProcess >= 0;
}

bool AIChatCliTransport::HasSession() const
{
	return stSession.bPersistent && HasProcess();
}

int64_t AIChatCliTransport::GetProcessId() const
{
	return stSession.nCliProcess;
}

const Vector<String> &AIChatCliTransport::GetSentMessages() const
{
	return stSession.arrCliSentMessages;
}

void AIChatCliTransport::SetSentMessages(const Vector<String> &arrMessages)
{
	stSession.arrCliSentMessages = arrMessages;
}

bool AIChatCliTransport::IsWaiting() const
{
	return bWaiting;
}

String AIChatCliTransport::GetPartialText() const
{
	return strPartial;
}

void AIChatCliTransport::ClearPartialText()
{
	strPartial = String();
}

String AIChatCliTransport::GetRequestPath() const
{
	return strRequestPath;
}

AIChatSessionTransport AIChatCliTransport::CaptureSession() const
{
	return stSession;
}

void AIChatCliTransport::RestoreSession(const AIChatSessionTransport &stSaved)
{
	// The caller archives CaptureSession before replacing the active idle slot.
	// Do not terminate the archived process when another conversation is shown.
	ReleaseRequest();
	stSession = stSaved;
	bWaiting = false;
	bResetRequested = false;
	bTruncated = false;
	arrOutput.clear();
	strPartial = String();
}
// clang-format on
