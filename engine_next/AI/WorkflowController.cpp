/**************************************************************************/
/*  WorkflowController.cpp                                                */
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

#include "engine_next/include/EngineNext/AI/WorkflowController.h"

#include "engine_next/Assets/AssetValidation.h"

#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <filesystem>
#include <fstream>

#ifdef _WIN32
#include <windows.h>
// Windows headers define GetObject as a macro; keep the JSON accessor intact.
#undef GetObject
#endif

namespace EngineNext::AI
{
namespace
{

const Serialization::JsonValue *Member(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapObject.find(in_strName);
	return it == in_mapObject.end() ? nullptr : &it->second;
}

const Serialization::JsonValue::Object *ObjectMember(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName)
{
	const Serialization::JsonValue *pValue = Member(in_mapObject, in_strName);
	return pValue == nullptr ? nullptr : pValue->GetObject();
}

const Serialization::JsonValue::List *ListMember(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName)
{
	const Serialization::JsonValue *pValue = Member(in_mapObject, in_strName);
	return pValue == nullptr ? nullptr : pValue->GetList();
}

bool TextMember(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName, std::string &out_strValue)
{
	const Serialization::JsonValue *pValue = Member(in_mapObject, in_strName);
	const std::string *pText = pValue == nullptr ? nullptr : pValue->GetString();
	if (pText == nullptr)
	{
		return false;
	}
	out_strValue = *pText;
	return true;
}

bool BoolMember(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName, bool &out_bValue)
{
	const Serialization::JsonValue *pValue = Member(in_mapObject, in_strName);
	return pValue != nullptr && pValue->GetBool(out_bValue);
}

bool WriteAtomic(const std::string &in_strPath, const std::string &in_strText)
{
	namespace fs = std::filesystem;
	const fs::path stTarget(in_strPath);
	if (!Assets::NoLinkedComponents(stTarget.parent_path()))
	{
		return false;
	}
	const fs::path stTemporary = stTarget.string() + ".tmp";
	{
		std::ofstream stStream(stTemporary, std::ios::binary | std::ios::trunc);
		if (!stStream)
		{
			return false;
		}
		stStream.write(in_strText.data(), static_cast<std::streamsize>(in_strText.size()));
		stStream.flush();
		if (!stStream.good())
		{
			return false;
		}
	}
#ifdef _WIN32
	return MoveFileExW(stTemporary.wstring().c_str(), stTarget.wstring().c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#else
	std::error_code stError;
	fs::rename(stTemporary, stTarget, stError);
	return !stError;
#endif
}

bool SameText(const Serialization::JsonValue::Object &in_mapLeft, const std::string &in_strLeft,
		const Serialization::JsonValue::Object &in_mapRight, const std::string &in_strRight)
{
	std::string strLeft;
	std::string strRight;
	return TextMember(in_mapLeft, in_strLeft, strLeft) && TextMember(in_mapRight, in_strRight, strRight) && strLeft == strRight;
}

} // namespace

WorkflowController::WorkflowController(IProcessTransport &in_stTransport) :
		pTransport(&in_stTransport), stRuntime("m3-controller")
{
}

bool WorkflowController::Execute(const HostConfig &in_stConfig, const std::string &in_strCommand,
		const Serialization::JsonValue &in_stInput, Serialization::JsonValue &out_stResult, Assets::Diagnostics &out_arrDiagnostics)
{
	ProcessSpec stSpec;
	stSpec.strExecutable = in_stConfig.strPython;
	stSpec.nTimeoutMsec = in_stConfig.nTimeoutMsec;
	stSpec.nOutputLimit = in_stConfig.nOutputLimit;
	stSpec.arrArguments = { in_stConfig.strExecutorScript, "--db", in_stConfig.strDatabase };
	if (in_strCommand == "create" || in_strCommand == "step")
	{
		stSpec.arrArguments.insert(stSpec.arrArguments.end(), { "--factory", in_stConfig.strFactory });
	}
	stSpec.arrArguments.push_back(in_strCommand);
	if (!strExecutorRunId.empty())
	{
		stSpec.arrArguments.insert(stSpec.arrArguments.end(), { "--run", strExecutorRunId });
	}
	if (!Serialization::CanonicalJson(in_stInput, stSpec.strInput))
	{
		return false;
	}
	ProcessResult stProcess;
	if (!pTransport->Run(stSpec, stProcess) || !stProcess.bStarted)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "python_unavailable", "$", "Python host could not be started");
		return false;
	}
	if (!stProcess.bExited || stProcess.bTimedOut || stProcess.bOutputOverflow || stProcess.nExitCode != 0)
	{
		Assets::AddDiagnostic(out_arrDiagnostics,
				stProcess.bOutputOverflow ? "process_output_limit" : stProcess.bTimedOut ? "process_timeout"
																						 : "process_exit",
				"$",
				"Executor process failed its lifecycle or output contract");
		return false;
	}
	Serialization::JsonValue stEnvelope;
	std::string strError;
	if (!Serialization::ParseJson(stProcess.strOutput, stEnvelope, strError))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "process_result", "$", "Executor returned malformed JSON");
		return false;
	}
	const Serialization::JsonValue::Object *pEnvelope = stEnvelope.GetObject();
	bool bOk = false;
	if (pEnvelope == nullptr || !BoolMember(*pEnvelope, "ok", bOk) || !bOk)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "executor_command_failed", "$", "Executor command failed");
		return false;
	}
	const Serialization::JsonValue *pResult = Member(*pEnvelope, "result");
	if (pResult == nullptr)
	{
		return false;
	}
	out_stResult = *pResult;
	return true;
}

bool WorkflowController::SaveState(const HostConfig &in_stConfig, const std::string &in_strRequest, const std::string &in_strRequestDigest,
		bool in_bPublished, const std::string &in_strDigest, Assets::Diagnostics &out_arrDiagnostics)
{
	Serialization::JsonValue::List arrArtifacts;
	for (const std::string &strKey : setPublishedArtifacts)
	{
		arrArtifacts.emplace_back(strKey);
	}
	std::string strPublicRun;
	{
		std::lock_guard<std::mutex> stLock(stMutex);
		strPublicRun = strRunId;
	}
	const Serialization::JsonValue stState(Serialization::JsonValue::Object{
			{ "executor_run_id", strExecutorRunId },
			{ "package_digest", in_strDigest },
			{ "public_run_id", strPublicRun },
			{ "published", in_bPublished },
			{ "published_artifacts", std::move(arrArtifacts) },
			{ "request_id", in_strRequest },
			{ "request_sha256", in_strRequestDigest },
			{ "schema_version", std::int64_t(1) },
	});
	std::string strText;
	if (!Serialization::CanonicalJson(stState, strText) || strText.size() > 16 * 1024 * 1024 || !WriteAtomic(in_stConfig.strStatePath, strText))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "state_write", "$", "unable to persist controller state");
		return false;
	}
	return true;
}

bool WorkflowController::ReadState(const HostConfig &in_stConfig, const std::string &in_strRequest,
		const std::string &in_strRequestDigest, Assets::Diagnostics &out_arrDiagnostics)
{
	namespace fs = std::filesystem;
	const fs::path stPath(in_stConfig.strStatePath);
	if (!Assets::NoLinkedComponents(stPath))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "state_read", "$", "resume state cannot contain linked components");
		return false;
	}
	std::error_code stError;
	const std::uintmax_t nSize = fs::file_size(stPath, stError);
	if (stError || nSize == 0 || nSize > 16 * 1024 * 1024)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "state_read", "$", "resume state is missing or invalid");
		return false;
	}
	std::ifstream stStream(stPath, std::ios::binary);
	std::string strText(static_cast<std::size_t>(nSize), '\0');
	stStream.read(strText.data(), static_cast<std::streamsize>(nSize));
	Serialization::JsonValue stValue;
	std::string strError;
	if (!Serialization::ParseJson(strText, stValue, strError))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "state_read", "$", "resume state is malformed");
		return false;
	}
	const Serialization::JsonValue::Object *pState = stValue.GetObject();
	std::string strRequest;
	std::string strDigest;
	if (pState == nullptr || !TextMember(*pState, "executor_run_id", strExecutorRunId) || !TextMember(*pState, "request_id", strRequest) ||
			!TextMember(*pState, "request_sha256", strDigest) || strRequest != in_strRequest || strDigest != in_strRequestDigest)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "state_identity", "$", "resume state does not match the complete request");
		return false;
	}
	setPublishedArtifacts.clear();
	const Serialization::JsonValue::List *pArtifacts = ListMember(*pState, "published_artifacts");
	if (pArtifacts != nullptr)
	{
		for (const Serialization::JsonValue &stArtifactKey : *pArtifacts)
		{
			const std::string *pKey = stArtifactKey.GetString();
			if (pKey == nullptr)
			{
				return false;
			}
			setPublishedArtifacts.insert(*pKey);
		}
	}
	return true;
}

bool WorkflowController::BeginRun(const AiAssetRequest &in_stRequest, const Serialization::JsonValue &in_stOriginalRequest, const std::string &in_strInputDigest)
{
	const Serialization::JsonValue::Object *pOriginal = in_stOriginalRequest.GetObject();
	const Serialization::JsonValue *pBindings = pOriginal == nullptr ? nullptr : Member(*pOriginal, "asset_bindings");
	if (pBindings == nullptr)
	{
		return false;
	}
	const Serialization::JsonValue stBinding(Serialization::JsonValue::Object{
			{ "asset_bindings", *pBindings },
			{ "executor", "ainative" },
			{ "input_sha256", in_strInputDigest },
			{ "scene_id", in_stRequest.stSceneTemplate.strSceneId },
			{ "scene_revision", in_stRequest.stSceneTemplate.strSceneRevision },
			{ "scene_template", Assets::ToJson(in_stRequest.stSceneTemplate) },
	});
	std::lock_guard<std::mutex> stLock(stMutex);
	const RunSnapshot *pRun = stRuntime.Begin("m3", in_stRequest.stSceneTemplate.strSceneId, in_stRequest.strRequestId, in_stRequest.stModel, stBinding);
	if (pRun == nullptr)
	{
		return false;
	}
	strRunId = pRun->strRunId;
	return true;
}

bool WorkflowController::PublishEvent(const std::string &in_strKind, const Serialization::JsonValue &in_stPayload, const std::string &in_strState)
{
	std::lock_guard<std::mutex> stLock(stMutex);
	const RunSnapshot *pRun = stRuntime.Find(strRunId);
	return pRun != nullptr && stRuntime.Publish(strRunId, pRun->nGeneration, in_strKind, in_stPayload, in_strState) != nullptr;
}

bool WorkflowController::IsCancellationRequested() const noexcept
{
	return bCancelRequested.load();
}

std::string WorkflowController::CurrentState()
{
	std::lock_guard<std::mutex> stLock(stMutex);
	const RunSnapshot *pRun = stRuntime.Find(strRunId);
	return pRun == nullptr ? std::string() : pRun->strState;
}

Serialization::JsonValue WorkflowController::CurrentSnapshot()
{
	std::lock_guard<std::mutex> stLock(stMutex);
	const RunSnapshot *pRun = stRuntime.Find(strRunId);
	return pRun == nullptr ? Serialization::JsonValue() : WorkflowSnapshot::ToJson(*pRun);
}

void WorkflowController::CancelExecutor(const HostConfig &in_stConfig)
{
	if (!strExecutorRunId.empty())
	{
		Serialization::JsonValue stResult;
		Assets::Diagnostics arrDiagnostics;
		(void)Execute(in_stConfig, "cancel", Serialization::JsonValue::Object{}, stResult, arrDiagnostics);
	}
}

bool WorkflowController::ValidateProviderModel(const Serialization::JsonValue &in_stStatus, const Serialization::JsonValue &in_stModel)
{
	const Serialization::JsonValue::Object *pStatus = in_stStatus.GetObject();
	const Serialization::JsonValue::Object *pNodes = pStatus == nullptr ? nullptr : ObjectMember(*pStatus, "nodes");
	const Serialization::JsonValue::Object *pModel = in_stModel.GetObject();
	if (pNodes == nullptr || pModel == nullptr)
	{
		return false;
	}
	for (const std::pair<const std::string, Serialization::JsonValue> &stEntry : *pNodes)
	{
		const Serialization::JsonValue::Object *pNode = stEntry.second.GetObject();
		const Serialization::JsonValue::Object *pProvider = pNode == nullptr ? nullptr : ObjectMember(*pNode, "provider_manifest");
		if (pProvider == nullptr)
		{
			return false;
		}
		const Serialization::JsonValue::Object *pSelection = pModel;
		const Serialization::JsonValue::Object *pNodeModels = ObjectMember(*pModel, "nodes");
		if (pNodeModels != nullptr)
		{
			const Serialization::JsonValue::Object *pSpecific = ObjectMember(*pNodeModels, stEntry.first);
			if (pSpecific != nullptr)
			{
				pSelection = pSpecific;
			}
		}
		if (!SameText(*pSelection, "provider", *pProvider, "id") || !SameText(*pSelection, "provider_version", *pProvider, "version") ||
				!SameText(*pSelection, "model", *pProvider, "model") || !SameText(*pSelection, "model_version", *pProvider, "model_version"))
		{
			return false;
		}
	}
	return true;
}

bool WorkflowController::Fail(const std::string &in_strCode, const std::string &in_strMessage, ControllerResult &out_stResult)
{
	Assets::AddDiagnostic(out_stResult.arrDiagnostics, in_strCode, "$", in_strMessage);
	const std::string strState = CurrentState();
	if (!strState.empty() && strState != "succeeded" && strState != "failed" && strState != "cancelled")
	{
		(void)PublishEvent("failed", Serialization::JsonValue::Object{ { "code", in_strCode } }, "failed");
	}
	out_stResult.bHasSnapshot = true;
	out_stResult.stSnapshot = CurrentSnapshot();
	return false;
}

bool WorkflowController::Run(const Serialization::JsonValue &in_stRequest, const HostConfig &in_stConfig, ControllerResult &out_stResult)
{
	out_stResult = ControllerResult{};
	{
		std::lock_guard<std::mutex> stLock(stMutex);
		strRunId.clear();
	}
	strExecutorRunId.clear();
	setPublishedArtifacts.clear();
	bCancelRequested = false;
	AiAssetRequest stRequest;
	if (!ParseAiAssetRequest(in_stRequest, stRequest, out_stResult.arrDiagnostics))
	{
		return false;
	}
	std::string strRequestBytes;
	if (!Serialization::CanonicalJson(in_stRequest, strRequestBytes))
	{
		return false;
	}
	const std::string strRequestDigest = Serialization::Sha256Hex(strRequestBytes);
	if (in_stConfig.bResume && !ReadState(in_stConfig, stRequest.strRequestId, strRequestDigest, out_stResult.arrDiagnostics))
	{
		return false;
	}
	Serialization::JsonValue::Object mapInput;
	mapInput["graph"] = stRequest.stGraph;
	mapInput["manifest"] = stRequest.stManifest;
	std::string strInputBytes;
	if (!Serialization::CanonicalJson(mapInput, strInputBytes))
	{
		return Fail("request_serialization", "unable to freeze Executor input", out_stResult);
	}
	if (!BeginRun(stRequest, in_stRequest, Serialization::Sha256Hex(strInputBytes)))
	{
		return Fail("runtime_rejected", "public runtime rejected the run", out_stResult);
	}
	if (!in_stConfig.bResume)
	{
		Serialization::JsonValue stCreated;
		if (!Execute(in_stConfig, "create", mapInput, stCreated, out_stResult.arrDiagnostics))
		{
			return Fail("create_failed", "Executor create failed", out_stResult);
		}
		const Serialization::JsonValue::Object *pCreated = stCreated.GetObject();
		if (pCreated == nullptr || !TextMember(*pCreated, "run_id", strExecutorRunId) || strExecutorRunId.empty())
		{
			return Fail("create_result", "Executor create returned no run identity", out_stResult);
		}
		out_stResult.strExecutorRunId = strExecutorRunId;
		if (!SaveState(in_stConfig, stRequest.strRequestId, strRequestDigest, false, "", out_stResult.arrDiagnostics))
		{
			return Fail("state_write", "unable to save created run", out_stResult);
		}
	}
	for (std::uint32_t nSteps = 0;;)
	{
		if (IsCancellationRequested())
		{
			CancelExecutor(in_stConfig);
			out_stResult.bHasSnapshot = true;
			out_stResult.stSnapshot = CurrentSnapshot();
			return false;
		}
		Serialization::JsonValue stStatus;
		if (!Execute(in_stConfig, in_stConfig.bResume && nSteps == 0 ? "status" : "step", Serialization::JsonValue::Object{}, stStatus, out_stResult.arrDiagnostics))
		{
			return Fail("step_failed", "Executor status/step failed", out_stResult);
		}
		if (!ValidateProviderModel(stStatus, stRequest.stModel))
		{
			return Fail("provider_identity", "Executor provider identity differs from frozen model", out_stResult);
		}
		std::string strState;
		const Serialization::JsonValue::Object *pStatus = stStatus.GetObject();
		if (pStatus == nullptr || !TextMember(*pStatus, "state", strState))
		{
			return Fail("step_result", "Executor state is missing", out_stResult);
		}
		if (strState == "cancelled")
		{
			(void)PublishEvent("cancelled", Serialization::JsonValue::Object{ { "executor_run_id", strExecutorRunId } }, "cancelled");
			out_stResult.bHasSnapshot = true;
			out_stResult.stSnapshot = CurrentSnapshot();
			return false;
		}
		if (strState == "failed")
		{
			return Fail("executor_failed", "Executor reached terminal failure", out_stResult);
		}
		if (strState != "running" && strState != "reconcile" && strState != "succeeded")
		{
			return Fail("executor_state", "unknown Executor state", out_stResult);
		}
		const std::string strPublicState = strState == "reconcile" ? "reconciling" : "running";
		if (!PublishEvent("progress", Serialization::JsonValue::Object{ { "executor_run_id", strExecutorRunId } }, strPublicState))
		{
			return Fail("runtime_event", "progress event was rejected", out_stResult);
		}
		++nSteps;
		if (strState == "succeeded")
		{
			break;
		}
		if (in_stConfig.nMaxSteps != 0 && nSteps >= in_stConfig.nMaxSteps)
		{
			out_stResult.bHasSnapshot = true;
			out_stResult.stSnapshot = CurrentSnapshot();
			Assets::AddDiagnostic(out_stResult.arrDiagnostics, "step_limit", "$", "step budget reached; resume is required");
			return false;
		}
	}
	Serialization::JsonValue stExported;
	if (!Execute(in_stConfig, "export", Serialization::JsonValue::Object{}, stExported, out_stResult.arrDiagnostics))
	{
		return Fail("export_failed", "Executor export failed", out_stResult);
	}
	if (IsCancellationRequested())
	{
		CancelExecutor(in_stConfig);
		out_stResult.bHasSnapshot = true;
		out_stResult.stSnapshot = CurrentSnapshot();
		return false;
	}
	if (CurrentState() != "running")
	{
		return Fail("runtime_state", "export requires an active running workflow", out_stResult);
	}
	Assets::PackageData stPackage;
	std::vector<Serialization::JsonValue> arrArtifacts;
	const std::string strStateDirectory = std::filesystem::path(in_stConfig.strStatePath).parent_path().string();
	if (!AdaptArtifacts(stRequest, stExported, strStateDirectory, stPackage, arrArtifacts, out_stResult.arrDiagnostics))
	{
		return Fail("artifact_adapter", "Artifact to asset adaptation failed", out_stResult);
	}
	for (const Serialization::JsonValue &stArtifact : arrArtifacts)
	{
		const Serialization::JsonValue::Object *pArtifact = stArtifact.GetObject();
		std::string strAsset;
		std::string strRevision;
		std::string strDigest;
		if (pArtifact == nullptr || !TextMember(*pArtifact, "asset_id", strAsset) || !TextMember(*pArtifact, "revision", strRevision) ||
				!TextMember(*pArtifact, "content_sha256", strDigest))
		{
			return Fail("artifact_event", "artifact identity is incomplete", out_stResult);
		}
		const std::string strKey = strAsset + "\n" + strRevision + "\n" + strDigest;
		if (setPublishedArtifacts.count(strKey) != 0)
		{
			continue;
		}
		if (!PublishEvent("artifact_ready", stArtifact))
		{
			return Fail("artifact_event", "artifact_ready was rejected", out_stResult);
		}
		setPublishedArtifacts.insert(strKey);
		if (!SaveState(in_stConfig, stRequest.strRequestId, strRequestDigest, false, "", out_stResult.arrDiagnostics))
		{
			return Fail("state_write", "unable to persist published artifact identity", out_stResult);
		}
	}
	Assets::PublishResult ePublish = Assets::PublishResult::Published;
	if (!Assets::PublishPackageGuarded(stPackage, in_stConfig.strOutput, ePublish, out_stResult.arrDiagnostics, stMutex,
				[this]()
				{ return IsCancellationRequested(); }))
	{
		if (IsCancellationRequested())
		{
			out_stResult.bHasSnapshot = true;
			out_stResult.stSnapshot = CurrentSnapshot();
			return false;
		}
		return Fail("package_publish", "asset package publication failed", out_stResult);
	}
	if (!SaveState(in_stConfig, stRequest.strRequestId, strRequestDigest, true, stPackage.strPackageDigest, out_stResult.arrDiagnostics))
	{
		return Fail("state_write", "unable to save published state", out_stResult);
	}
	if (!PublishEvent("completed", Serialization::JsonValue::Object{
										   { "package_digest", stPackage.strPackageDigest },
										   { "scene_content_sha256", stPackage.stManifest.strSceneContentSha256 },
										   { "scene_revision", stPackage.stScene.strSceneRevision },
								   },
				"succeeded"))
	{
		return Fail("completion", "completion event was rejected", out_stResult);
	}
	out_stResult.bHasSnapshot = true;
	out_stResult.stSnapshot = CurrentSnapshot();
	out_stResult.strExecutorRunId = strExecutorRunId;
	out_stResult.strPackageDigest = stPackage.strPackageDigest;
	return true;
}

void WorkflowController::Cancel() noexcept
{
	{
		std::lock_guard<std::mutex> stLock(stMutex);
		bCancelRequested = true;
		if (!strRunId.empty())
		{
			(void)stRuntime.Cancel(strRunId);
		}
	}
	if (pTransport != nullptr)
	{
		pTransport->Cancel();
	}
}

} // namespace EngineNext::AI
