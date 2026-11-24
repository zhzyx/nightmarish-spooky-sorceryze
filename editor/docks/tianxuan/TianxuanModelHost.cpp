/**************************************************************************/
/*  TianxuanModelHost.cpp                                                 */
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

#include "TianxuanModelHost.h"

#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/object/object.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_dock.h"
#include "scene/gui/check_box.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"
#include "scene/main/timer.h"

namespace
{
Dictionary Failure(const String &strError)
{
	Dictionary mapResult;
	mapResult["ok"] = false;
	mapResult["error"] = strError;
	return mapResult;
}
}

TianxuanModelHost::TianxuanModelHost(AIChatDock *pSettingsOwner)
{
	if (pSettingsOwner != nullptr)
	{
		idSettingsOwner = pSettingsOwner->get_instance_id();
	}
}

void TianxuanModelHost::_bind_methods()
{
	ClassDB::bind_method(D_METHOD("configuration"), &TianxuanModelHost::Configuration);
	ClassDB::bind_method(D_METHOD("start", "scope", "request_id", "messages"), &TianxuanModelHost::Start);
	ClassDB::bind_method(D_METHOD("progress", "request_id"), &TianxuanModelHost::Progress);
	ClassDB::bind_method(D_METHOD("cancel", "request_id"), &TianxuanModelHost::Cancel);
	ADD_SIGNAL(MethodInfo("finished", PropertyInfo(Variant::STRING, "request_id"), PropertyInfo(Variant::DICTIONARY, "result")));
}

Dictionary TianxuanModelHost::Configuration() const
{
	AIChatDock *pOwner = ObjectDB::get_instance<AIChatDock>(idSettingsOwner);
	if (pOwner == nullptr)
	{
		return Failure(TTR("The editor's local model settings are unavailable."));
	}
	const Dictionary mapConfiguration = pOwner->get_ai_configuration();
	const int nBackend = mapConfiguration.get("backend", -1);
	Dictionary mapModel;
	mapModel["backend"] = nBackend;
	mapModel["provider"] = nBackend == 1 ? "codebuddy" : nBackend == 2 ? "codex" : nBackend == 3 ? "openai_responses" : "openai";
	mapModel["id"] = mapConfiguration.get(nBackend == 1 ? "cli_model" : nBackend == 2 ? "codex_model" : "model", String());
	mapModel["reasoning_effort"] = mapConfiguration.get("reasoning_effort", String());
	mapModel["configured"] = pOwner->_ai_connection_configured();
	return mapModel;
}

Dictionary TianxuanModelHost::Start(const String &strScope, const String &strRequestId, const Array &arrMessages)
{
	AIChatDock *pOwner = ObjectDB::get_instance<AIChatDock>(idSettingsOwner);
	if (!is_inside_tree() || pOwner == nullptr || !pOwner->is_inside_tree())
	{
		return Failure(TTR("The editor's local model host is unavailable."));
	}
	if (strScope.strip_edges().is_empty() || strScope.length() > 2048 || strRequestId.strip_edges().is_empty() || strRequestId.length() > 256)
	{
		return Failure(TTR("The local conversation identity is invalid."));
	}
	if (setConsumedRequests.has(strRequestId))
	{
		return Failure(TTR("This local model request has already been submitted. Use a new request ID to retry."));
	}
	if (mapWorkers.size() >= 4)
	{
		return Failure(TTR("Four local conversations are already running. Wait for one to finish or cancel it."));
	}
	if (arrMessages.is_empty() || arrMessages.size() > 128)
	{
		return Failure(TTR("The local conversation must contain between 1 and 128 messages."));
	}
	Array arrContext;
	int64_t nContentBytes = 0;
	for (int nIndex = 0; nIndex < arrMessages.size(); ++nIndex)
	{
		if (arrMessages[nIndex].get_type() != Variant::DICTIONARY)
		{
			return Failure(TTR("The local conversation contains an invalid message."));
		}
		const Dictionary mapInput = arrMessages[nIndex];
		const Variant varRole = mapInput.get("role", Variant());
		const Variant varContent = mapInput.get("content", Variant());
		if (varRole.get_type() != Variant::STRING || varContent.get_type() != Variant::STRING)
		{
			return Failure(TTR("Local messages require a text role and content."));
		}
		const String strRole = varRole;
		const String strContent = varContent;
		if ((strRole != "user" && strRole != "assistant" && strRole != "system") || strContent.strip_edges().is_empty())
		{
			return Failure(TTR("Local messages must contain nonempty user, assistant or system text."));
		}
		nContentBytes += strContent.utf8().length();
		if (nContentBytes > 512 * 1024)
		{
			return Failure(TTR("The local conversation exceeds the 512 KiB input limit."));
		}
		Dictionary mapMessage;
		mapMessage["role"] = strRole;
		mapMessage["content"] = strContent;
		arrContext.push_back(mapMessage);
	}
	Dictionary mapLast = arrContext.back();
	if (String(mapLast["role"]) != "user")
	{
		return Failure(TTR("The last local conversation message must be from the user."));
	}
	const Dictionary mapModel = Configuration();
	if (!bool(mapModel.get("configured", false)))
	{
		Dictionary mapFailure = Failure(TTR("Configure the editor's local CLI or API connection in model settings before sending."));
		mapFailure["model"] = mapModel;
		return mapFailure;
	}

	// A nonempty private directory disables the editor bridge and scheduled work.
	// This worker never loads or persists AI Chat history; Tianxuan owns its transcript.
	const String strPrivateScope = strScope.sha256_text() + "-" + strRequestId.sha256_text();
	const String strDirectory = OS::get_singleton()->get_temp_path().path_join("godot-tianxuan-model").path_join(itos(get_instance_id())).path_join(strPrivateScope);
	AIChatDock *pWorker = memnew(AIChatDock(strDirectory));
	pWorker->bLocalConsultationWorker = true;
	pWorker->set_name("TianxuanConsultationWorker");
	pWorker->hide();
	pWorker->set_process_shortcut_input(false);
	// Copy access and selection once. Later settings changes affect the next request only.
	pWorker->endpoint->set_text(pOwner->endpoint->get_text());
	pWorker->CopyApiCredential(pOwner);
	pWorker->backend->select(pOwner->backend->get_selected());
	pWorker->model->set_text(pOwner->model->get_text());
	pWorker->cli_model->set_text(pOwner->cli_model->get_text());
	pWorker->codex_model->set_text(pOwner->codex_model->get_text());
	pWorker->cli_bridge->set_text(pOwner->cli_bridge->get_text());
	pWorker->cli_entry->set_text(pOwner->cli_entry->get_text());
	pWorker->GetAiSession().mapReasoningPreferences = pOwner->GetAiSession().mapReasoningPreferences.duplicate(true);
	pWorker->model_catalog = pOwner->model_catalog.duplicate(true);
	pWorker->discovered_model_catalogs = pOwner->discovered_model_catalogs.duplicate(true);
	pWorker->SyncAiSessionInputs();
	pWorker->_sync_reasoning_picker();
	pWorker->allow_tools->set_pressed_no_signal(false);
	pWorker->consultation_only->set_pressed_no_signal(true);
	pWorker->auto_apply_file_changes->set_pressed_no_signal(false);
	pWorker->auto_execute_commands->set_pressed_no_signal(false);
	pWorker->engine_auto_restart->set_pressed_no_signal(false);
	pWorker->ai_connection_timer->set_autostart(false);
	pWorker->mapLocalConsultationBinding["scope"] = strScope;
	pWorker->mapLocalConsultationBinding["request_id"] = strRequestId;
	pWorker->mapLocalConsultationBinding["messages_sha256"] = JSON::stringify(arrContext).sha256_text();
	pWorker->fnLocalConsultationFinished = callable_mp(this, &TianxuanModelHost::WorkerFinished).bind(strRequestId, uint64_t(pWorker->get_instance_id()));
	add_child(pWorker);
	pWorker->model_config_timer->stop();
	arrContext.resize(arrContext.size() - 1);
	pWorker->GetAiSession().arrMessages = arrContext;
	mapLast["consultation_only"] = true;
	mapWorkers.insert(strRequestId, pWorker->get_instance_id());
	mapModels.insert(strRequestId, mapModel.duplicate(true));
	setConsumedRequests.insert(strRequestId);
	if (!pWorker->_start_message(mapLast))
	{
		const Array &arrTranscript = pWorker->GetAiSession().arrTranscript;
		const Dictionary mapLastRecord = arrTranscript.is_empty() ? Dictionary() : Dictionary(arrTranscript.back());
		const String strError = mapLastRecord.get("role", "") == "error" ? String(mapLastRecord.get("content", "")) : TTR("The local model request could not start.");
		pWorker->fnLocalConsultationFinished = Callable();
		mapWorkers.erase(strRequestId);
		mapModels.erase(strRequestId);
		pWorker->queue_free();
		Dictionary mapFailure = Failure(pOwner->_redact(strError));
		mapFailure["model"] = mapModel;
		return mapFailure;
	}
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["model"] = mapModel;
	return mapResult;
}

Dictionary TianxuanModelHost::Progress(const String &strRequestId) const
{
	Dictionary mapProgress;
	mapProgress["active"] = false;
	mapProgress["phase"] = "idle";
	const ObjectID *pWorkerId = mapWorkers.getptr(strRequestId);
	if (!is_inside_tree() || pWorkerId == nullptr)
	{
		return mapProgress;
	}
	const AIChatDock *pWorker = ObjectDB::get_instance<AIChatDock>(*pWorkerId);
	if (pWorker == nullptr || !pWorker->is_inside_tree() || pWorker->get_parent() != this || !pWorker->bLocalConsultationWorker || !pWorker->IsAiBusy())
	{
		return mapProgress;
	}
	const Dictionary mapSnapshot = pWorker->GetAiWorkflowSnapshot();
	const Dictionary mapBinding = mapSnapshot.get("binding", Dictionary());
	const Dictionary mapConsultation = mapBinding.get("local_consultation", Dictionary());
	if (mapConsultation.is_empty() || mapConsultation.get("request_id", String()) != Variant(strRequestId) || mapConsultation != pWorker->mapLocalConsultationBinding)
	{
		return mapProgress;
	}
	// CLI and HTTP expose different progress events. A live authoritative run proves
	// waiting, but never a percentage, generated asset, or a safe partial answer.
	mapProgress["active"] = true;
	mapProgress["phase"] = "waiting";
	return mapProgress;
}

void AIChatDock::FinishLocalConsultation()
{
	if (!fnLocalConsultationFinished.is_valid())
	{
		return;
	}
	Dictionary mapResult;
	const Array &arrMessages = GetAiSession().arrMessages;
	const Dictionary mapLast = arrMessages.is_empty() ? Dictionary() : Dictionary(arrMessages.back());
	const String strText = mapLast.get("role", "") == "assistant" ? _redact(mapLast.get("content", "")) : String();
	const bool bSuccess = turn_completed && !strText.strip_edges().is_empty() && GetAiWorkflowSnapshot().get("state", "") == "succeeded";
	mapResult["ok"] = bSuccess;
	mapResult["text"] = bSuccess ? strText : String();
	if (!bSuccess)
	{
		const Array &arrTranscript = GetAiSession().arrTranscript;
		const Dictionary mapLastRecord = arrTranscript.is_empty() ? Dictionary() : Dictionary(arrTranscript.back());
		mapResult["error"] = mapLastRecord.get("role", "") == "error" ? _redact(mapLastRecord.get("content", "")) : TTR("The local model did not return a complete answer. Check its connection and retry.");
	}
	const Callable fnFinished = fnLocalConsultationFinished;
	fnLocalConsultationFinished = Callable();
	// Complete transport cleanup before the owner releases this worker or starts another turn.
	fnFinished.call_deferred(mapResult);
}

void TianxuanModelHost::WorkerFinished(const Dictionary &mapResult, const String &strRequestId, uint64_t nWorkerId)
{
	const ObjectID *pWorkerId = mapWorkers.getptr(strRequestId);
	if (pWorkerId == nullptr || uint64_t(*pWorkerId) != nWorkerId)
	{
		return;
	}
	AIChatDock *pWorker = ObjectDB::get_instance<AIChatDock>(*pWorkerId);
	Dictionary mapFinished = mapResult.duplicate(true);
	mapFinished["model"] = mapModels[strRequestId].duplicate(true);
	mapWorkers.erase(strRequestId);
	mapModels.erase(strRequestId);
	if (pWorker != nullptr)
	{
		pWorker->queue_free();
	}
	EmitFinished(strRequestId, mapFinished);
}

void TianxuanModelHost::EmitFinished(const String &strRequestId, const Dictionary &mapResult)
{
	if (is_inside_tree())
	{
		emit_signal("finished", strRequestId, mapResult);
	}
}

bool TianxuanModelHost::Cancel(const String &strRequestId)
{
	const ObjectID *pWorkerId = mapWorkers.getptr(strRequestId);
	if (pWorkerId == nullptr)
	{
		return false;
	}
	AIChatDock *pWorker = ObjectDB::get_instance<AIChatDock>(*pWorkerId);
	Dictionary mapResult = Failure(TTR("The local model request was cancelled."));
	mapResult["model"] = mapModels[strRequestId].duplicate(true);
	mapResult["cancelled"] = true;
	mapWorkers.erase(strRequestId);
	mapModels.erase(strRequestId);
	if (pWorker != nullptr)
	{
		pWorker->fnLocalConsultationFinished = Callable();
		pWorker->refAiController->RequestCancel();
		pWorker->_set_busy(false);
		pWorker->queue_free();
	}
	callable_mp(this, &TianxuanModelHost::EmitFinished).call_deferred(strRequestId, mapResult);
	return true;
}

void TianxuanModelHost::_notification(int nWhat)
{
	if (nWhat != NOTIFICATION_EXIT_TREE)
	{
		return;
	}
	for (const KeyValue<String, ObjectID> &stEntry : mapWorkers)
	{
		AIChatDock *pWorker = ObjectDB::get_instance<AIChatDock>(stEntry.value);
		if (pWorker != nullptr)
		{
			pWorker->fnLocalConsultationFinished = Callable();
			pWorker->refAiController->RequestCancel();
		}
	}
	mapWorkers.clear();
	mapModels.clear();
}

// clang-format on
