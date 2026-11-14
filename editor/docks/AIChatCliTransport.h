/**************************************************************************/
/*  AIChatCliTransport.h                                                  */
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

// Preserve CPP_CODING_STANDARD.md v1.1 Allman style during formatter transition.
// clang-format off
#include "core/error/error_list.h"
#include "core/io/file_access.h"
#include "core/object/ref_counted.h"
#include "core/templates/list.h"
#include "core/templates/vector.h"
#include "core/variant/dictionary.h"

struct AIChatSessionTransport
{
	int64_t nCliProcess = -1;
	Ref<FileAccess> refCliStdout;
	Ref<FileAccess> refCliStderr;
	String strCliConfiguration;
	Vector<String> arrCliSentMessages;
	bool bPersistent = false;
	bool bCodex = false;
};

struct AIChatCliPlan
{
	bool bReused = false;
	bool bIncremental = false;
	bool bReset = false;
	bool bRebuilding = false;
	int nPreviousCount = 0;
};

struct AIChatCliRequest
{
	String strExecutable;
	List<String> arrPrefixArguments;
	List<String> arrSuffixArguments;
	String strBody;
	String strTempPrefix;
	String strConfiguration;
	Dictionary mapSubmission;
	Vector<String> arrSentMessages;
	bool bPassRequestPath = false;
	bool bPersistent = false;
	bool bCodex = false;
	bool bReuse = false;
};

struct AIChatCliEvent
{
	enum class Kind : uint8_t
	{
		None,
		Progress,
		CommandResult,
		Completed,
		Failed,
		Closed,
	};
	Kind eKind = Kind::None;
	Dictionary mapPayload;
	PackedByteArray arrBody;
	uint64_t nGeneration = 0;
	int nExitCode = 0;
	bool bTimedOut = false;
	bool bTruncated = false;
};

// Main-thread process transport. Poll returns data and never calls a View.
// A session snapshot retains an idle process while its conversation is archived.
class AIChatCliTransport final : public RefCounted
{
	GDCLASS(AIChatCliTransport, RefCounted);

public:
	~AIChatCliTransport() override;
	AIChatCliPlan PlanSubmission(const String &strConfiguration, const Vector<String> &arrMessages, bool bIncremental, bool bPersistent);
	Error Submit(const AIChatCliRequest &stRequest, uint64_t nGeneration);
	AIChatCliEvent Poll();
	void Cancel();
	void ReleaseRequest();
	void RequestReset();
	bool IsProcessAlive() const;
	bool HasProcess() const;
	bool HasSession() const;
	bool IsWaiting() const;
	int64_t GetProcessId() const;
	const Vector<String> &GetSentMessages() const;
	void SetSentMessages(const Vector<String> &arrMessages);
	String GetPartialText() const;
	void ClearPartialText();
	String GetRequestPath() const;
	AIChatSessionTransport CaptureSession() const;
	void RestoreSession(const AIChatSessionTransport &stSaved);
	static void CancelSession(AIChatSessionTransport &stSaved);
	static bool IsHistoryPrefix(const Vector<String> &arrPrevious, const Vector<String> &arrCurrent);

protected:
	static void _bind_methods();

private:
	bool ReadPipes();
	int FindLine() const;
	AIChatCliEvent ConsumeProgress(const Dictionary &mapEnvelope, int nLine, uint64_t nNow);
	Error WriteRequest(const AIChatCliRequest &stRequest);
	AIChatSessionTransport stSession;
	Ref<FileAccess> refRequestFile;
	String strRequestPath;
	String strPartial;
	PackedByteArray arrOutput;
	uint64_t nRequestGeneration = 0;
	uint64_t nStartedMillis = 0;
	uint64_t nLastActivityMillis = 0;
	bool bWaiting = false;
	bool bResetRequested = false;
	bool bTruncated = false;
};
// clang-format on
