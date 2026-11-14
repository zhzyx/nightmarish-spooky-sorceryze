/**************************************************************************/
/*  AIChatController.cpp                                                  */
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
#include "AIChatController.h"

#include "core/object/callable_mp.h"
#include "core/object/object.h"
#include "scene/main/http_request.h"
#include "scene/main/node.h"

AIChatController::AIChatController()
{
	refRuntime.instantiate();
	refCliTransport.instantiate();
}

AIChatController::~AIChatController()
{
	CancelHttp();
	refCliTransport->Cancel();
}

void AIChatController::_bind_methods()
{
}

void AIChatController::BeginRun(const String &strScope, const String &strRequest, const Dictionary &mapModel, const Dictionary &mapBinding)
{
	if (IsRunning())
	{
		return;
	}
	const String strAttempt = strRequest + "/" + itos(++nRunCount);
	const String strEffectiveScope = strScope.is_empty() ? itos(get_instance_id()) : strScope;
	bCancellationRequested = false;
	const Dictionary mapStarted = refRuntime->BeginRun("aichat", strEffectiveScope, strAttempt, mapModel, mapBinding);
	strRun = mapStarted.get("run_id", String());
	// BeginRun emits a synchronous event. Read the authoritative state after
	// listeners return, including a cancellation performed by a listener.
	const Dictionary mapCurrent = GetSnapshot();
	nRunGeneration = mapCurrent.get("generation", 0);
}

void AIChatController::FinishRun(bool bSucceeded)
{
	CancelHttp();
	if (bCancellationRequested)
	{
		CancelRun();
		return;
	}
	Publish(bSucceeded ? "completed" : "failed");
}

void AIChatController::RequestCancel()
{
	bCancellationRequested = true;
	AdvanceRequestGeneration();
	CancelHttp();
	refCliTransport->Cancel();
}

void AIChatController::CancelRun()
{
	AdvanceRequestGeneration();
	CancelHttp();
	refCliTransport->Cancel();
	if (!strRun.is_empty())
	{
		refRuntime->Cancel(strRun);
	}
}

bool AIChatController::IsRunning() const
{
	const Dictionary mapState = GetSnapshot();
	const String strState = mapState.get("state", String());
	return !strState.is_empty() && strState != "succeeded" && strState != "failed" && strState != "cancelled";
}

Dictionary AIChatController::GetSnapshot() const
{
	return strRun.is_empty() ? Dictionary() : refRuntime->Snapshot(strRun);
}

Dictionary AIChatController::GetSessionSnapshot() const
{
	Dictionary mapSession;
	mapSession["conversation_id"] = stSession.strConversation;
	mapSession["model"] = stSession.strModel;
	mapSession["cli_model"] = stSession.strCliModel;
	mapSession["codex_model"] = stSession.strCodexModel;
	mapSession["backend"] = stSession.nBackend;
	mapSession["reasoning_preferences"] = stSession.mapReasoningPreferences.duplicate(true);
	mapSession["draft"] = stSession.strDraft;
	mapSession["draft_images"] = stSession.arrDraftImages.duplicate(true);
	return mapSession;
}

AIChatSessionData &AIChatController::GetSession()
{
	return stSession;
}

const AIChatSessionData &AIChatController::GetSession() const
{
	return stSession;
}

AIChatTurnState &AIChatController::GetTurn()
{
	return stTurn;
}

const AIChatTurnState &AIChatController::GetTurn() const
{
	return stTurn;
}

Dictionary AIChatController::Publish(const String &strKind, const Dictionary &mapPayload, const String &strState)
{
	if (strRun.is_empty())
	{
		return Dictionary();
	}
	return refRuntime->Publish(strRun, nRunGeneration, strKind, mapPayload, strState);
}

uint64_t AIChatController::GetRequestGeneration() const
{
	return nRequestGeneration;
}

uint64_t AIChatController::GetSessionGeneration() const
{
	return nSessionGeneration;
}

uint64_t AIChatController::AdvanceRequestGeneration()
{
	return ++nRequestGeneration;
}

uint64_t AIChatController::AdvanceSessionGeneration()
{
	return ++nSessionGeneration;
}

bool AIChatController::IsCurrentRequest(uint64_t nGeneration) const
{
	return IsRunning() && nGeneration == nRequestGeneration;
}

AIChatCliTransport *AIChatController::GetCliTransport() const
{
	return refCliTransport.ptr();
}

void AIChatController::SetTextFilter(const Callable &fnFilter)
{
	fnTextFilter = fnFilter;
}

Error AIChatController::StartCli(const AIChatCliRequest &stRequest)
{
	if (GetSnapshot().get("state", String()) != "running" || bCancellationRequested)
	{
		return ERR_SKIP;
	}
	return refCliTransport->Submit(stRequest, AdvanceRequestGeneration());
}

AIChatCliEvent AIChatController::PollCli()
{
	AIChatCliEvent stEvent = refCliTransport->Poll();
	if (stEvent.eKind == AIChatCliEvent::Kind::None || stEvent.eKind == AIChatCliEvent::Kind::Closed)
	{
		return stEvent;
	}
	if (!IsCurrentRequest(stEvent.nGeneration))
	{
		return AIChatCliEvent();
	}
	if (stEvent.eKind == AIChatCliEvent::Kind::Progress)
	{
		Dictionary mapProgress;
		const String strActivity = stEvent.mapPayload.get("activity", "");
		mapProgress["activity"] = fnTextFilter.is_valid() ? String(fnTextFilter.call(strActivity)) : String();
		if (!IsCurrentRequest(stEvent.nGeneration))
		{
			return AIChatCliEvent();
		}
		Publish("progress", mapProgress);
		if (IsCurrentRequest(stEvent.nGeneration) && stEvent.mapPayload.has("content") && fnTextFilter.is_valid())
		{
			Dictionary mapText;
			mapText["text"] = fnTextFilter.call(stEvent.mapPayload["content"]);
			mapText["replace"] = true;
			if (IsCurrentRequest(stEvent.nGeneration))
			{
				Publish("text_delta", mapText);
			}
		}
	}
	return IsCurrentRequest(stEvent.nGeneration) ? stEvent : AIChatCliEvent();
}

HTTPRequest *AIChatController::GetHttpRequest() const
{
	return ObjectDB::get_instance<HTTPRequest>(idHttpRequest);
}

Error AIChatController::StartHttp(Node *pHost, const AIChatHttpRequest &stRequest, const Callable &fnCompletion)
{
	ERR_FAIL_NULL_V(pHost, ERR_INVALID_PARAMETER);
	const Dictionary mapCurrent = GetSnapshot();
	if (mapCurrent.get("state", String()) != "running" || bCancellationRequested || !fnCompletion.is_valid())
	{
		return ERR_SKIP;
	}
	const String strExpectedRun = strRun;
	CancelHttp();
	const uint64_t nGeneration = AdvanceRequestGeneration();
	HTTPRequest *pRequest = memnew(HTTPRequest);
	idHttpRequest = pRequest->get_instance_id();
	const ObjectID idExpectedRequest = idHttpRequest;
	fnHttpCompletion = fnCompletion;
	fnHttpSignal = callable_mp(this, &AIChatController::HttpCompleted).bind(nGeneration);
	// Nonblocking polling keeps cancellation independent of server response time.
	pRequest->set_use_threads(false);
	pRequest->set_timeout(120);
	pRequest->set_body_size_limit(2 * 1024 * 1024);
	pRequest->set_max_redirects(0);
	pRequest->connect("request_completed", fnHttpSignal);
	pHost->add_child(pRequest);
	// Adding a child emits synchronous scene-tree signals. A listener may have
	// cancelled this run or started another request before control returns.
	if (strRun != strExpectedRun || !IsCurrentRequest(nGeneration) || idHttpRequest != idExpectedRequest || GetSnapshot().get("state", String()) != "running")
	{
		if (idHttpRequest == idExpectedRequest)
		{
			CancelHttp();
		}
		return ERR_SKIP;
	}
	pRequest->set_http_proxy(stRequest.strProxy, stRequest.nProxyPort);
	pRequest->set_https_proxy(stRequest.strProxy, stRequest.nProxyPort);
	const Error eResult = pRequest->request(stRequest.strUrl, stRequest.arrHeaders, HTTPClient::METHOD_POST, stRequest.strBody);
	if (eResult != OK)
	{
		CancelHttp();
	}
	return eResult;
}

void AIChatController::CancelHttp()
{
	HTTPRequest *pRequest = GetHttpRequest();
	idHttpRequest = ObjectID();
	fnHttpCompletion = Callable();
	if (pRequest)
	{
		if (pRequest->is_connected("request_completed", fnHttpSignal))
		{
			pRequest->disconnect("request_completed", fnHttpSignal);
		}
		pRequest->cancel_request();
		pRequest->queue_free();
	}
	fnHttpSignal = Callable();
}

void AIChatController::HttpCompleted(int nResult, int nCode, const PackedStringArray &arrHeaders, const PackedByteArray &arrBody, uint64_t nGeneration)
{
	if (!IsCurrentRequest(nGeneration))
	{
		return;
	}
	const Callable fnCompletion = fnHttpCompletion;
	CancelHttp();
	fnCompletion.call(nResult, nCode, arrHeaders, arrBody, nGeneration);
}
// clang-format on
