/**************************************************************************/
/*  AIChatController                                                      */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                     */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#pragma once

#include "AIChatEngineExecution.h"
#include "AIChatDeliveryExecution.h"
#include "ai_chat_resume.h"
#include "ai_chat_task_authorization.h"
#include "core/io/file_access.h"
#include "core/object/ref_counted.h"
#include "core/templates/list.h"
#include "core/templates/vector.h"
#include "core/variant/array.h"
#include "core/variant/callable.h"
#include "core/variant/dictionary.h"

class Node;

// Main-thread execution owner; no GUI types or View callbacks are required.
// A host supplies a scene-tree Node solely for HTTPRequest polling.
class AIChatController : public RefCounted
{
	GDCLASS(AIChatController, RefCounted);

public:
	struct ReadResult
	{
		String strContent;
		bool bSuccess = false;
	};
	struct Session
	{
		String strConversationId;
		String strSnapshotId;
		Dictionary mapSnapshotState;
		bool bConsultationTurn = false;
		bool bTurnCompleted = false;
		uint64_t nTurnStarted = 0;
		int nTurnSteps = 0;
		int nTurnModelRequests = 0;
		String strRequestKey;
		String strRequestCredentialAudience;
		AIChatTaskAuthorization stTaskNativeGrant;
		uint64_t nTaskNativeEpoch = 0;
		uint64_t nTaskNativeRequestEpoch = 0;
		AIChatResume stResumeStorage;
		Array arrQueuedMessages;
		bool bQueuePaused = false;
		Array arrTranscript;
		Dictionary mapReasoningPreferences;
		int64_t nGonggongPid = -1;
		uint64_t nGonggongGeneration = 0;
		bool bGonggongResume = false;
		String strGonggongContext;
		String strGonggongGovernanceDigest;
		String strGonggongInputPath;
		String strGonggongOutputPath;
		Dictionary mapGonggongReporting;
		String strGonggongReportRoot;
		String strGonggongReportPython;
		Dictionary mapGonggongRunningSteps;
		int64_t nGonggongReceiptPid = -1;
		bool bGongGongReceiptExited = false;
		int nGongGongReceiptExitCode = -1;
		uint32_t nGongGongReceiptReadAttempts = 0;
		uint64_t nGongGongReceiptReadDeadline = 0;
		String strGonggongReceiptPath;
		uint64_t nGonggongReceiptGeneration = 0;
		String strGonggongRecoveredResult;
		String strGonggongRecoveryAckToken;
		Dictionary mapCommandRecoveryReporting;
		String strCommandOfferId;
		String strCommandOfferPath;
		bool bRestoringCommandOffer = false;
		bool bGonggongRecoveryCanSend = false;
		Callable callGonggongReceiptContinuation;
		uint64_t nGonggongContinuationGeneration = 0;
		Array arrGonggongReceiptQueue;
		String strGonggongReceiptRoot;
		Dictionary mapGonggongReceiptScope;
		int64_t nCandidatePid = -1;
		uint64_t nCandidateGeneration = 0;
		String strCandidateResultPath;
		String strPendingPath;
		String strPendingBefore;
		String strPendingAfter;
		Dictionary mapPendingEditorAction;
		Dictionary mapPendingExternalEditorMessage;
		String strPendingAction;
		String strPendingCommand;
		String strCompletedCommandReceiptPath;
		String strCompletedCommandOwner;
		String strCompletedCommandCall;
		String strObservedCommandOwner;
		String strRecoveringCommandDigest;
		Dictionary mapConsumedCommandByOwner;
		String strPendingCwd;
		bool bPendingExisted = false;
		Dictionary mapDaqianApproval;
		uint64_t nDaqianApprovalGeneration = 0;
		bool bDaqianApprovalRunning = false;
		String strDaqianPreviewSource;
		String strDaqianPreviewConversation;
		Array arrMessages;
		Array arrToolCalls;
		int nReadBatchCount = 0;
		Vector<ReadResult> arrReadBatchResults;
		int nToolIndex = 0;
		int nToolRounds = 0;
		uint64_t nRequestGeneration = 0;
		uint64_t nSessionGeneration = 0;
		bool bBusy = false;
		int64_t nCliProcessId = -1;
		uint64_t nCliStarted = 0;
		uint64_t nCliLastActivity = 0;
		uint64_t nCliGeneration = 0;
		Ref<FileAccess> refCliStdout;
		Ref<FileAccess> refCliStderr;
		Ref<FileAccess> refCliRequestFile;
		PackedByteArray arrCliOutput;
		String strCliInputPath;
		bool bCliTruncated = false;
		bool bCliSession = false;
		bool bCliSteeringReset = false;
		bool bCliWaiting = false;
		String strCliConfiguration;
		Vector<String> arrCliSentMessages;
		bool bCodexChat = false;
		int64_t nCommandProcessId = -1;
		uint64_t nCommandStarted = 0;
		Ref<FileAccess> refCommandStdout;
		Ref<FileAccess> refCommandStderr;
		Ref<RefCounted> refCommandFile;
		PackedByteArray arrCommandStdout;
		PackedByteArray arrCommandStderr;
		bool bCommandTruncated = false;
		bool bCommandTimedOut = false;
		int nCommandTimeoutSeconds = 120;
		String strCommandGuardResultPath;
		String strCommandRevocationPath;
	};

	Session &GetSession();
	AIChatEngineExecution &GetEngineExecution();
	AIChatDeliveryExecution &GetDeliveryExecution();
	Dictionary CaptureDeliveryResult(const Dictionary &mapProcessResult, const Dictionary &mapScope, const String &strCurrentCredential);
	void RevokeNativeTask();
	bool GrantNativeTask(const Dictionary &mapScope, const Dictionary &mapPolicy);
	bool AllowsNativeTask(const Dictionary &mapScope, const Dictionary &mapPolicy, const String &strTool, const Dictionary &mapArguments);
	static String NewIdentity();
	static Variant RedactSnapshotValue(const Variant &varValue, const Callable &callRedact, int nDepth = 0, bool bDataKeys = false);
	bool HasActiveRun() const;
	Dictionary StartTurn(const Dictionary &mapMessage, const Dictionary &mapContext, const String &strCurrentCredential);
	Dictionary BeginRun(const Dictionary &mapRequest);
	Dictionary QueryRun() const;
	void DetachRun();
	Dictionary CaptureCheckpoint() const;
	bool RestoreCheckpoint(const Dictionary &mapCheckpoint);
	Dictionary PrepareCliIncrement(const Array &arrRecords, const Array &arrPreparedMessages, const String &strConfiguration);
	Dictionary AttachRun(const String &strRunId);
	Dictionary PublishState(const String &strKind, const String &strState, const Dictionary &mapPayload = Dictionary());
	void FinishRun(bool bSucceeded);
	void Cancel();
	bool Accepts(uint64_t nGeneration) const;
	Dictionary GetFrozenModel() const;
	int GetRunBackend(int nFallback) const;
	static Dictionary MakeMessage(const String &strRole, const String &strContent);
	Dictionary BuildToolPolicy(const Dictionary &mapPolicy) const;
	bool BuildModelMessages(const Dictionary &mapScope, const Dictionary &mapPolicy, int nBackend, Array &out_arrMessages, Dictionary &out_mapStats) const;
	Dictionary BuildHttpPayload(const Array &arrPreparedMessages, const Array &arrDefinitions, const Dictionary &mapPolicy, int nBackend) const;
	Dictionary ConsumeModelResponse(int nResult, int nCode, const PackedByteArray &arrBody, uint64_t nGeneration, int nBackend, bool bToolsAllowed, const String &strCurrentCredential);
	Dictionary DecodeResponse(const PackedByteArray &arrBody, int nBackend, bool bToolsAllowed) const;
	Dictionary PrepareTool(uint64_t nSessionGeneration, int nOffset, bool bToolsAllowed, bool bConsultationOnly) const;
	bool AppendToolResult(const String &strResult, bool bFileSuccess, int nBackend);
	bool HasPendingSteering() const;
	Array ApplyPendingSteering(int nBackend);
	String PlanNextTool(uint64_t nSessionGeneration);
	void RecordToolResult(const String &strResult, bool bFileSuccess, bool bStructured, int nBackend, const String &strCurrentCredential);
	bool AdvanceTool(uint64_t nSessionGeneration);
	Error StartHttp(Node *pHost, const String &strEndpoint, const Vector<String> &arrHeaders, const String &strBody, const String &strProxy, int nPort);
	void CancelHttp();
	bool ValidateCandidate(const Dictionary &mapExpected, bool bRequireEngine, String &out_strError) const;
	Error StartCandidate(const Dictionary &mapHost);
	bool PollCandidate(Dictionary &out_mapResult);
	void CancelCandidate();
	static String GetUserOutcome(const Array &arrMessages);
	Dictionary BuildWorkOrderInput(const Dictionary &mapScope, const Dictionary &mapPolicy, const Dictionary &mapDelegation) const;
	String ValidateWorkOrderResult(const Dictionary &mapResult, bool bChild, const Dictionary &mapDelegation);
	Error StartWorkOrderContext(const Dictionary &mapRequest, const Dictionary &mapHost);
	bool PollWorkOrderContext(Dictionary &out_mapResult);
	void ClearWorkOrderContextFiles();
	void CancelWorkOrderContext();
	String RedactText(const String &strText, const String &strCurrentCredential) const;
	Dictionary StartReceiptFlush(const String &strPython, const String &strInstallation, const String &strBridge, const String &strCacheDirectory);
	Dictionary PollReceiptFlush(const String &strCurrentCredential);
	bool RecordWorkOrderEvent(const String &strKind, const String &strPhase, const String &strStatus, const String &strBoard, const String &strActorTitle, String &out_strError);
	bool BuildCommandArguments(const String &strProjectRoot, String &out_strExecutable, List<String> &out_arrArguments, String &out_strError);
	static Dictionary MakeToolResult(const String &strContent, bool bFileSuccess = false, bool bStructured = false, const String &strReadSha256 = String());
	Dictionary ExecuteEditorTool(ObjectID idExecutor, const String &strName, const Dictionary &mapArguments, bool bToolsAllowed, bool bConfirmed, const String &strCurrentCredential);
	bool ReadLocalTool(const String &strName, const Dictionary &mapArguments, const String &strProjectRoot, bool bReview, Dictionary &out_mapResult) const;
	bool PrepareSnapshotWrite(const String &strSnapshotPath, String &out_strError);
	bool ApplyFileWrite(const String &strAbsolutePath, const String &strSnapshotPath, String &out_strError);
	Error StartCommand(const String &strExecutable, const List<String> &arrArguments, const String &strRevocationPath = String());
	void CancelCommand();
	Dictionary PollCommand();
	Error SubmitCodex(const String &strBody, const Dictionary &mapTransport);
	Error SubmitCodeBuddy(const String &strBody, const Dictionary &mapTransport, const Vector<String> &arrCurrentMessages);
	void BeginToolBatch(const Array &arrCalls, const String &strRedactedContent);
	Error StoreCliRequest(const String &strBody);
	Error StartCliProcess(const String &strExecutable, const List<String> &arrArguments, bool bSession, bool bCodex);
	Error SubmitCliRequest(const Dictionary &mapSubmission);
	void BeginCliResponse();
	void PollCli();
	void CancelCli();
	void ReleaseCliRequest();
	~AIChatController();

protected:
	static void _bind_methods();

private:
	Session stSession;
	Ref<AIChatEngineExecution> refEngineExecution = memnew(AIChatEngineExecution);
	Ref<AIChatDeliveryExecution> refDeliveryExecution = memnew(AIChatDeliveryExecution);
	ObjectID idHttpRequest;
	String strRunId;
	bool bOwnsRun = false;
	Dictionary mapRunSnapshot;
	bool DrainCommandPipe(const Ref<FileAccess> &refPipe, PackedByteArray &out_arrOutput);
	void HttpCompleted(int nResult, int nCode, const PackedStringArray &arrHeaders, const PackedByteArray &arrBody, uint64_t nGeneration);
};
