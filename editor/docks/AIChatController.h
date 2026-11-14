/**************************************************************************/
/*  AIChatController.h                                                    */
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
#include "core/templates/vector.h"
#include "core/variant/array.h"
#include "core/variant/callable.h"
#include "core/variant/dictionary.h"
#include "modules/ai_core/AIWorkflowRuntime.h"
#include "editor/docks/AIChatCliTransport.h"

class HTTPRequest;
class Node;

// Serializable chat data is independent of the widgets presenting it.
struct AIChatSessionData
{
	String strConversation;
	Array arrMessages;
	Array arrTranscript;
	Vector<String> arrToolDetails;
	String strDraft;
	Array arrDraftImages;
	Array arrQueuedMessages;
	bool bQueuePaused = false;
	String strModel;
	String strCliModel;
	String strCodexModel;
	Dictionary mapReasoningPreferences;
	int nBackend = 1;
	Dictionary mapTransport;
	Dictionary mapResponseTransport;
	String strSnapshot;
	Dictionary mapSnapshot;
};

struct AIChatHttpRequest
{
	String strUrl;
	Vector<String> arrHeaders;
	String strBody;
	String strProxy;
	int nProxyPort = 0;
};

struct AIChatTurnState
{
	Array arrToolCalls;
	int nToolIndex = 0;
	int nToolRounds = 0;
};

// Main-thread controller. A view supplies commands and renders snapshots, while
// this object owns run state, request generations and HTTP request lifetimes.
class AIChatController final : public RefCounted
{
	GDCLASS(AIChatController, RefCounted);

public:
	AIChatController();
	~AIChatController() override;
	void BeginRun(const String &strScope, const String &strRequest, const Dictionary &mapModel, const Dictionary &mapBinding);
	void FinishRun(bool bSucceeded);
	void RequestCancel();
	void CancelRun();
	bool IsRunning() const;
	Dictionary GetSnapshot() const;
	Dictionary GetSessionSnapshot() const;
	AIChatSessionData &GetSession();
	const AIChatSessionData &GetSession() const;
	AIChatTurnState &GetTurn();
	const AIChatTurnState &GetTurn() const;
	Dictionary Publish(const String &strKind, const Dictionary &mapPayload = Dictionary(), const String &strState = String());
	uint64_t GetRequestGeneration() const;
	uint64_t GetSessionGeneration() const;
	uint64_t AdvanceRequestGeneration();
	uint64_t AdvanceSessionGeneration();
	Error StartHttp(Node *pHost, const AIChatHttpRequest &stRequest, const Callable &fnCompletion);
	Error StartCli(const AIChatCliRequest &stRequest);
	AIChatCliEvent PollCli();
	AIChatCliTransport *GetCliTransport() const;
	void SetTextFilter(const Callable &fnFilter);
	void CancelHttp();
	bool IsCurrentRequest(uint64_t nGeneration) const;

protected:
	static void _bind_methods();

private:
	void HttpCompleted(int nResult, int nCode, const PackedStringArray &arrHeaders, const PackedByteArray &arrBody, uint64_t nGeneration);
	HTTPRequest *GetHttpRequest() const;
	Ref<AIWorkflowRuntime> refRuntime;
	Ref<AIChatCliTransport> refCliTransport;
	Callable fnTextFilter;
	AIChatSessionData stSession;
	AIChatTurnState stTurn;
	String strRun;
	int64_t nRunGeneration = 0;
	uint64_t nRunCount = 0;
	uint64_t nRequestGeneration = 0;
	uint64_t nSessionGeneration = 0;
	bool bCancellationRequested = false;
	ObjectID idHttpRequest;
	Callable fnHttpCompletion;
	Callable fnHttpSignal;
};
// clang-format on
