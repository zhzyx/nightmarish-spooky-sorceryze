/**************************************************************************/
/*  ClientSession.cpp                                                     */
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

#include "engine_next/Client/ClientSession.h"

#include "engine_next/include/EngineNext/Gameplay/PredictionReconciler.h"
#include "engine_next/include/EngineNext/Network/ImpairmentTransport.h"
#include "engine_next/include/EngineNext/Network/Protocol.h"
#include "engine_next/include/EngineNext/Runtime/RuntimeHost.h"

#include <algorithm>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <utility>

namespace EngineNext::Runtime
{
namespace
{

const char *GetInterpolationStatusName(Gameplay::InterpolationStatus in_eStatus) noexcept
{
	switch (in_eStatus)
	{
		case Gameplay::InterpolationStatus::Empty:
			return "empty";
		case Gameplay::InterpolationStatus::SingleSample:
			return "single_sample";
		case Gameplay::InterpolationStatus::BeforeRange:
			return "before_range";
		case Gameplay::InterpolationStatus::Interpolated:
			return "interpolated";
		case Gameplay::InterpolationStatus::Held:
			return "held";
		case Gameplay::InterpolationStatus::StaleHeld:
			return "stale_held";
		case Gameplay::InterpolationStatus::NumericError:
			return "numeric_error";
	}
	return "unknown";
}

RuntimeStatus SendInput(Network::ImpairmentTransport &in_stTransport, std::uint64_t nSessionId, std::uint64_t nEntityId, const Gameplay::PredictionInput &in_stInput, std::uint64_t nNowMsec)
{
	Network::InputCommand stCommand;
	stCommand.nEntityId = nEntityId;
	stCommand.stInput = in_stInput;
	Network::FrameHeader stHeader;
	stHeader.eType = Network::MessageType::Input;
	stHeader.nMessageSequence = in_stInput.nSequence;
	stHeader.nSessionId = nSessionId;
	std::vector<std::uint8_t> arrFrame;
	const RuntimeStatus eStatus = Network::EncodeFrame(stHeader, Network::EncodeInputCommand(stCommand), arrFrame);
	if (eStatus != RuntimeStatus::Ok)
	{
		return eStatus;
	}
	return in_stTransport.SendAt(1, 1, false, arrFrame, nNowMsec);
}

RuntimeStatus SendDisconnect(Network::ImpairmentTransport &in_stTransport, std::uint64_t nSessionId, const Network::Disconnect &in_stDisconnect, std::uint64_t nNowMsec)
{
	Network::FrameHeader stHeader;
	stHeader.eType = Network::MessageType::Disconnect;
	stHeader.nMessageSequence = in_stDisconnect.nAcknowledgeSequence != 0 ? in_stDisconnect.nAcknowledgeSequence : 2;
	stHeader.nSessionId = nSessionId;
	std::vector<std::uint8_t> arrFrame;
	const RuntimeStatus eStatus = Network::EncodeFrame(stHeader, Network::EncodeDisconnect(in_stDisconnect), arrFrame);
	if (eStatus != RuntimeStatus::Ok)
	{
		return eStatus;
	}
	return in_stTransport.SendAt(1, 0, true, arrFrame, nNowMsec);
}

} // namespace

struct ClientSession::State
{
	RuntimeConfig in_stConfig;
	RuntimeHost stHost{ RuntimeRole::Client };
	Gameplay::PredictionReconciler stPrediction;
	std::unique_ptr<Network::ImpairmentTransport> pTransport;
	ClientSessionMode eMode = ClientSessionMode::Interactive;
	RuntimeStatus eStatus = RuntimeStatus::Ok;
	std::uint64_t nNowMsec = 0;
	std::uint64_t nGeneration = 0;
	bool bInitialized = false;
	bool bHasTime = false;
	bool bConnected = false;
	Gameplay::Vector3 vPendingMovement;
	std::map<std::uint64_t, Gameplay::InterpolationBuffer> mapRemoteBuffers;
	std::map<std::uint64_t, Gameplay::PredictionInput> mapUnacknowledgedInputs;
	std::map<std::uint64_t, std::size_t> mapRemoteHighWater;
	std::size_t nUnacknowledgedHighWater = 0;
	bool bMove = false;
	Network::ReconnectToken arrResumeToken{};
	std::uint64_t nSessionId = 0;
	std::uint64_t nEntityId = 0;
	std::uint64_t nSentInputs = 0;
	std::uint64_t nResentInputs = 0;
	std::uint64_t nNextInputMsec = 0;
	std::uint64_t nNextRetransmitMsec = 0;
	std::uint64_t nReconnectAtMsec = 0;
	std::uint64_t nLatestServerTimeMsec = 0;
	std::uint64_t nLatestSnapshotLocalMsec = 0;
	std::uint64_t nStaleServerTimeMsec = 0;
	bool bAwaitingReconnect = false;
	bool bReconnecting = false;
	bool bReconnectAttempted = false;
	bool bReconnectComplete = false;
	bool bPredictionComplete = false;
	bool bRemoteSeen = false;
	bool bStaleSeen = false;
	bool bRemoteRecovered = false;
	bool bDrainReceived = false;
	bool bClosing = false;
	bool bDisconnectSent = false;
	bool bCloseSucceeded = false;
	bool bCompletionSent = false;
	std::uint64_t nDisconnectAtMsec = 0;
	std::uint64_t nCloseDeadlineMsec = 0;
	std::uint64_t nExpectedDrainAcknowledge = 0;
	std::uint64_t nDrainDeadlineTick = 0;
	bool bSucceeded = false;

	RuntimeStatus Initialize(const RuntimeConfig &stConfig, std::unique_ptr<Network::ITransport> pUpstream, ClientSessionMode eSessionMode);
	RuntimeStatus ProcessEvents();
	RuntimeStatus Step(const Gameplay::Vector3 &vMovement);
	void PrintBounds() const;
};

RuntimeStatus ClientSession::State::Initialize(const RuntimeConfig &stConfig, std::unique_ptr<Network::ITransport> pUpstream, ClientSessionMode eSessionMode)
{
	in_stConfig = stConfig;
	eMode = eSessionMode;
	bMove = stConfig.strClientId == "A";
	eStatus = stHost.Initialize(stConfig);
	if (eStatus != RuntimeStatus::Ok)
	{
		return eStatus;
	}
	const SceneRuntime &stScene = stHost.GetSceneRuntime();
	if (stScene.IsLoaded())
	{
		std::cout << "ENGINE_NEXT_CLIENT_SCENE client_id=" << stConfig.strClientId << " scene_id=" << stScene.GetSceneId()
				  << " scene_revision=" << stScene.GetSceneRevision() << " scene_content_sha256=" << stScene.GetSceneContentSha256()
				  << " package_digest=" << stScene.GetPackageDigest() << '\n'
				  << std::flush;
	}
	if (!stPrediction.SetModel(stScene.GetPredictionModel()) || pUpstream == nullptr)
	{
		return RuntimeStatus::InvalidParameter;
	}
	Network::ImpairmentConfig stImpairment;
	stImpairment.nSeed = stConfig.nSeed;
	stImpairment.nDelayMsec = stConfig.nImpairmentDelayMsec;
	stImpairment.nJitterMsec = stConfig.nImpairmentJitterMsec;
	stImpairment.nLossPermille = stConfig.nImpairmentLossPermille;
	stImpairment.nQueueCapacity = stConfig.nImpairmentQueueCapacity;
	stImpairment.bDropFirstInput = stConfig.bDropFirstInput;
	pTransport = std::make_unique<Network::ImpairmentTransport>(std::move(pUpstream), stImpairment);
	eStatus = pTransport->StartClient(stConfig.strBindAddress, stConfig.nPort);
	bInitialized = eStatus == RuntimeStatus::Ok;
	return eStatus;
}

RuntimeStatus ClientSession::State::ProcessEvents()
{
	std::vector<Network::TransportEvent> arrEvents;
	eStatus = pTransport->PollAt(arrEvents, nNowMsec);
	if (eStatus != RuntimeStatus::Ok)
	{
		std::cout << "ENGINE_NEXT_CLIENT_POLL_ERROR client_id=" << in_stConfig.strClientId << " status=" << static_cast<int>(eStatus) << '\n'
				  << std::flush;
		return eStatus;
	}
	for (const Network::TransportEvent &stEvent : arrEvents)
	{
		if (stEvent.nPeerId != 1)
		{
			return RuntimeStatus::InvalidParameter;
		}
		if (stEvent.eType == Network::TransportEventType::Connected)
		{
			std::cout << "ENGINE_NEXT_CLIENT_TRANSPORT_CONNECTED client_id=" << in_stConfig.strClientId
					  << " reconnecting=" << (bReconnecting ? 1 : 0) << " session_id=" << nSessionId << '\n'
					  << std::flush;
			Network::ClientHello stHello;
			stHello.nClientNonce = in_stConfig.nSeed;
			if (bReconnecting)
			{
				stHello.nResumeSessionId = nSessionId;
				stHello.arrResumeToken = arrResumeToken;
			}
			Network::FrameHeader stHeader;
			stHeader.eType = Network::MessageType::ClientHello;
			std::vector<std::uint8_t> arrFrame;
			eStatus = Network::EncodeFrame(stHeader, Network::EncodeClientHello(stHello), arrFrame);
			if (eStatus == RuntimeStatus::Ok)
			{
				eStatus = pTransport->SendAt(1, 0, true, arrFrame, nNowMsec);
			}
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			continue;
		}
		if (stEvent.eType == Network::TransportEventType::Disconnected)
		{
			if (bClosing && bCloseSucceeded && (!bDrainReceived || bCompletionSent))
			{
				std::cout << "ENGINE_NEXT_CLIENT_CLOSE client_id=" << in_stConfig.strClientId << " drain=" << (bDrainReceived ? 1 : 0) << '\n'
						  << std::flush;
				bSucceeded = true;
				break;
			}
			std::cout << "ENGINE_NEXT_CLIENT_TRANSPORT_DISCONNECT client_id=" << in_stConfig.strClientId
					  << " reconnecting=" << (bReconnecting ? 1 : 0) << " closing=" << (bClosing ? 1 : 0)
					  << " ready=" << (bCloseSucceeded ? 1 : 0) << '\n'
					  << std::flush;
			eStatus = RuntimeStatus::IoError;
			break;
		}
		if (stEvent.eType != Network::TransportEventType::Packet)
		{
			continue;
		}
		Network::FrameHeader stHeader;
		eStatus = Network::DecodeHeader(stEvent.arrPayload.data(), stEvent.arrPayload.size(), stHeader);
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		(void)stHost.RecordTrace(stHeader.nMessageSequence, "packet", Runtime::EntityId{ static_cast<std::uint16_t>(stHeader.eType) }, stHeader.nSessionId);
		if (stHeader.eType == Network::MessageType::ServerWelcome)
		{
			Network::ServerWelcome stWelcome;
			eStatus = Network::DecodeServerWelcome(stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stWelcome);
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			const bool bResume = bReconnecting && bReconnectAttempted;
			if ((!bReconnecting && nSessionId != 0) || stHeader.nSessionId == 0 || stWelcome.nEntityId == 0 || stWelcome.nFixedStepMsec != stHost.GetFixedStepLoop().GetFixedStepMsec() ||
				(bResume && (stHeader.nSessionId != nSessionId || stWelcome.nEntityId != nEntityId || stWelcome.arrResumeToken == arrResumeToken)))
			{
				eStatus = RuntimeStatus::InvalidParameter;
				break;
			}
			Gameplay::PredictionState stInitialState;
			stInitialState.vPosition = stWelcome.vPosition;
			stInitialState.vVelocity = stWelcome.vVelocity;
			stInitialState.nConfirmedSequence = stWelcome.nConfirmedInputSequence;
			if (stWelcome.nServerTick > std::numeric_limits<std::uint64_t>::max() / stWelcome.nFixedStepMsec)
			{
				eStatus = RuntimeStatus::InvalidParameter;
				break;
			}
			stInitialState.nServerTimeMsec = stWelcome.nServerTick * stWelcome.nFixedStepMsec;
			float fResumeError = 0.0F;
			const bool bStateRestored = bResume ? stPrediction.RestoreAfterReconnect(stInitialState, fResumeError) : stPrediction.SetInitialState(stInitialState);
			if (!bStateRestored)
			{
				eStatus = RuntimeStatus::InvalidState;
				break;
			}
			nSessionId = stHeader.nSessionId;
			++nGeneration;
			bConnected = true;
			nEntityId = stWelcome.nEntityId;
			arrResumeToken = stWelcome.arrResumeToken;
			const std::map<std::uint64_t, Gameplay::PredictionInput>::iterator stFirstUnconfirmed = mapUnacknowledgedInputs.upper_bound(stWelcome.nConfirmedInputSequence);
			mapUnacknowledgedInputs.erase(mapUnacknowledgedInputs.begin(), stFirstUnconfirmed);
			nNextInputMsec = nNowMsec;
			nNextRetransmitMsec = nNowMsec + 32;
			bReconnecting = false;
			bReconnectComplete = bReconnectComplete || bResume;
			std::cout << "ENGINE_NEXT_CLIENT_WELCOME client_id=" << in_stConfig.strClientId
					  << " session_id=" << nSessionId << " entity_id=" << nEntityId << " resumed=" << (bResume ? 1 : 0) << '\n';
			if (bResume)
			{
				std::cout << "ENGINE_NEXT_CLIENT_RESUME client_id=" << in_stConfig.strClientId << " session_id=" << nSessionId
						  << " entity_id=" << nEntityId << " confirmed=" << stWelcome.nConfirmedInputSequence
						  << " error=" << fResumeError << '\n';
			}
			std::cout << std::flush;
			(void)stHost.RecordTrace(stWelcome.nServerTick, bResume ? "resume" : "welcome", Runtime::EntityId{ nEntityId }, nSessionId);
			continue;
		}
		if (stHeader.eType == Network::MessageType::ErrorReject)
		{
			Network::ErrorReject stReject;
			if (Network::DecodeErrorReject(stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stReject) != RuntimeStatus::Ok)
			{
				eStatus = RuntimeStatus::InvalidParameter;
				break;
			}
			std::cout << "ENGINE_NEXT_CLIENT_REJECT client_id=" << in_stConfig.strClientId << " reason=" << stReject.nReason
					  << " fatal=" << stReject.nFatal << '\n'
					  << std::flush;
			eStatus = RuntimeStatus::IoError;
			break;
		}
		if (stHeader.eType == Network::MessageType::Disconnect)
		{
			Network::Disconnect stDisconnect;
			if (Network::DecodeDisconnect(stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stDisconnect) != RuntimeStatus::Ok ||
				stHeader.nSessionId != nSessionId)
			{
				eStatus = RuntimeStatus::InvalidParameter;
				break;
			}
			if (stDisconnect.nReason == static_cast<std::uint16_t>(Network::DisconnectReason::DrainAcknowledge))
			{
				if (!bClosing || !bCloseSucceeded || stDisconnect.nAcknowledgeSequence != nExpectedDrainAcknowledge ||
					stDisconnect.nDrainDeadlineTick != nDrainDeadlineTick)
				{
					eStatus = RuntimeStatus::InvalidState;
					break;
				}
				Network::Disconnect stComplete;
				stComplete.nReason = static_cast<std::uint16_t>(Network::DisconnectReason::DrainComplete);
				stComplete.nAcknowledgeSequence = stHeader.nMessageSequence;
				stComplete.nDrainDeadlineTick = nDrainDeadlineTick;
				eStatus = SendDisconnect(*pTransport, nSessionId, stComplete, nNowMsec);
				if (eStatus != RuntimeStatus::Ok)
				{
					break;
				}
				bCompletionSent = true;
				bDisconnectSent = false;
				nDisconnectAtMsec = nNowMsec + 32;
				std::cout << "ENGINE_NEXT_CLIENT_DRAIN_COMPLETE client_id=" << in_stConfig.strClientId << " drain=1\n"
						  << std::flush;
				continue;
			}
			if (stDisconnect.nReason != static_cast<std::uint16_t>(Network::DisconnectReason::ServerDraining) || stDisconnect.nDrainDeadlineTick == 0)
			{
				eStatus = RuntimeStatus::InvalidParameter;
				break;
			}
			nExpectedDrainAcknowledge = stHeader.nMessageSequence;
			nDrainDeadlineTick = stDisconnect.nDrainDeadlineTick;
			std::cout << "ENGINE_NEXT_CLIENT_DRAIN client_id=" << in_stConfig.strClientId
					  << " deadline_tick=" << stDisconnect.nDrainDeadlineTick << '\n'
					  << std::flush;
			if (in_stConfig.bWithholdDrainAck)
			{
				std::cout << "ENGINE_NEXT_CLIENT_DRAIN_WITHHELD client_id=" << in_stConfig.strClientId << '\n'
						  << std::flush;
				bDrainReceived = true;
				bClosing = true;
				bCloseSucceeded = false;
				nDisconnectAtMsec = static_cast<std::uint64_t>(-1);
				nCloseDeadlineMsec = nNowMsec + 2000;
				continue;
			}
			Network::Disconnect stAcknowledge;
			stAcknowledge.nReason = static_cast<std::uint16_t>(Network::DisconnectReason::DrainAcknowledge);
			stAcknowledge.nAcknowledgeSequence = stHeader.nMessageSequence;
			stAcknowledge.nDrainDeadlineTick = stDisconnect.nDrainDeadlineTick;
			eStatus = SendDisconnect(*pTransport, nSessionId, stAcknowledge, nNowMsec);
			bDrainReceived = true;
			bClosing = true;
			bDisconnectSent = false;
			nDisconnectAtMsec = nNowMsec + 32;
			nCloseDeadlineMsec = nNowMsec + 1000;
			const bool bGameplayComplete = eMode == ClientSessionMode::Interactive || (bMove ? bPredictionComplete && (!in_stConfig.bReconnectTest || bReconnectComplete) : bRemoteSeen && (!in_stConfig.bReconnectTest || (bStaleSeen && bRemoteRecovered)));
			bCloseSucceeded = eStatus == RuntimeStatus::Ok && bGameplayComplete;
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			continue;
		}
		if (stHeader.eType != Network::MessageType::Snapshot || nSessionId == 0 || stHeader.nSessionId != nSessionId || bReconnecting)
		{
			continue;
		}
		Network::Snapshot stSnapshot;
		eStatus = Network::DecodeSnapshot(stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stSnapshot);
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		if (stSnapshot.nEntityId == 0)
		{
			eStatus = RuntimeStatus::InvalidParameter;
			break;
		}
		Gameplay::PredictionState stState;
		stState.vPosition = stSnapshot.vPosition;
		stState.vVelocity = stSnapshot.vVelocity;
		stState.nConfirmedSequence = stSnapshot.nLastProcessedInputSequence;
		if (stSnapshot.nServerTick > std::numeric_limits<std::uint64_t>::max() / stHost.GetFixedStepLoop().GetFixedStepMsec())
		{
			eStatus = RuntimeStatus::InvalidParameter;
			break;
		}
		stState.nServerTimeMsec = stSnapshot.nServerTick * stHost.GetFixedStepLoop().GetFixedStepMsec();
		nLatestServerTimeMsec = stState.nServerTimeMsec;
		nLatestSnapshotLocalMsec = nNowMsec;
		(void)stHost.RecordTrace(stSnapshot.nServerTick, "decoded_snapshot", Runtime::EntityId{ stSnapshot.nEntityId }, stHeader.nSessionId);
		if (stSnapshot.nEntityId == nEntityId)
		{
			float fPositionError = 0.0F;
			if (!stPrediction.ApplyAuthoritativeState(stState, fPositionError))
			{
				eStatus = RuntimeStatus::InvalidState;
				break;
			}
			const std::map<std::uint64_t, Gameplay::PredictionInput>::iterator stFirstUnconfirmed = mapUnacknowledgedInputs.upper_bound(stSnapshot.nLastProcessedInputSequence);
			mapUnacknowledgedInputs.erase(mapUnacknowledgedInputs.begin(), stFirstUnconfirmed);
			if (fPositionError > 0.001F)
			{
				std::cout << "ENGINE_NEXT_CLIENT_CORRECTION client_id=" << in_stConfig.strClientId
						  << " sequence=" << stSnapshot.nLastProcessedInputSequence << " error=" << fPositionError << '\n'
						  << std::flush;
			}
			continue;
		}
		if (mapRemoteBuffers.find(stSnapshot.nEntityId) == mapRemoteBuffers.end() && mapRemoteBuffers.size() >= 255)
		{
			eStatus = RuntimeStatus::InvalidState;
			break;
		}
		Gameplay::InterpolationBuffer &stBuffer = mapRemoteBuffers[stSnapshot.nEntityId];
		const Gameplay::Status eBufferStatus = stBuffer.AddSample(stState);
		std::size_t &nRemoteHighWater = mapRemoteHighWater[stSnapshot.nEntityId];
		nRemoteHighWater = nRemoteHighWater < stBuffer.GetSampleCount() ? stBuffer.GetSampleCount() : nRemoteHighWater;
		(void)stHost.RecordTrace(stState.nServerTimeMsec, "remote_sample", Runtime::EntityId{ stSnapshot.nEntityId }, stBuffer.GetSampleCount());
		if (eBufferStatus != Gameplay::Status::Ok && eBufferStatus != Gameplay::Status::AlreadyExists)
		{
			eStatus = RuntimeStatus::InvalidState;
			break;
		}
	}
	return eStatus;
}

RuntimeStatus ClientSession::State::Step(const Gameplay::Vector3 &vMovement)
{
	const SceneRuntime &stScene = stHost.GetSceneRuntime();
	if (bAwaitingReconnect)
	{
		if (nNowMsec < nReconnectAtMsec)
		{
			return RuntimeStatus::Ok;
		}
		eStatus = pTransport->StartClient(in_stConfig.strBindAddress, in_stConfig.nPort);
		if (eStatus != RuntimeStatus::Ok)
		{
			return eStatus;
		}
		bAwaitingReconnect = false;
		bReconnecting = true;
		std::cout << "ENGINE_NEXT_CLIENT_RECONNECT client_id=" << in_stConfig.strClientId << " session_id=" << nSessionId
				  << " entity_id=" << nEntityId << " offline_ms=600\n"
				  << std::flush;
	}
	eStatus = ProcessEvents();
	if (eStatus != RuntimeStatus::Ok || bSucceeded)
	{
		return eStatus;
	}
	if (bClosing)
	{
		if (!bDisconnectSent && (bCompletionSent || !bDrainReceived) && nNowMsec >= nDisconnectAtMsec)
		{
			eStatus = pTransport->DisconnectLater(1);
			bDisconnectSent = true;
			if (eStatus == RuntimeStatus::NotFound && bCloseSucceeded && (bCompletionSent || !bDrainReceived))
			{
				std::cout << "ENGINE_NEXT_CLIENT_CLOSE_TRANSPORT client_id=" << in_stConfig.strClientId << " already_disconnected=1\n"
						  << std::flush;
				bSucceeded = true;
				eStatus = RuntimeStatus::Ok;
				return eStatus;
			}
			if (eStatus != RuntimeStatus::Ok)
			{
				std::cout << "ENGINE_NEXT_CLIENT_CLOSE_ERROR client_id=" << in_stConfig.strClientId << " status=" << static_cast<int>(eStatus)
						  << " drain=" << (bDrainReceived ? 1 : 0) << " ready=" << (bCloseSucceeded ? 1 : 0) << '\n'
						  << std::flush;
				return eStatus;
			}
		}
		if (nNowMsec >= nCloseDeadlineMsec)
		{
			std::cout << "ENGINE_NEXT_CLIENT_CLOSE_TIMEOUT client_id=" << in_stConfig.strClientId << " drain=" << (bDrainReceived ? 1 : 0) << '\n'
					  << std::flush;
			eStatus = RuntimeStatus::IoError;
			return eStatus;
		}
		return RuntimeStatus::Ok;
	}

	if (eMode == ClientSessionMode::Interactive && bConnected && !bReconnecting)
	{
		std::uint32_t nSteps = 0;
		while (nNowMsec >= nNextInputMsec && nSteps < 8)
		{
			if (mapUnacknowledgedInputs.size() >= 256)
			{
				return RuntimeStatus::InvalidState;
			}
			Gameplay::PredictionInput stInput;
			const Gameplay::Vector3 vStepMovement = vMovement.LengthSquared() > 0 ? vMovement : vPendingMovement;
			if (!stPrediction.PredictInput(vStepMovement, stInput))
			{
				return RuntimeStatus::InvalidParameter;
			}
			eStatus = SendInput(*pTransport, nSessionId, nEntityId, stInput, nNowMsec);
			if (eStatus != RuntimeStatus::Ok)
			{
				return eStatus;
			}
			vPendingMovement = {};
			mapUnacknowledgedInputs.emplace(stInput.nSequence, stInput);
			nUnacknowledgedHighWater = (std::max)(nUnacknowledgedHighWater, mapUnacknowledgedInputs.size());
			++nSentInputs;
			++nSteps;
			nNextInputMsec += stHost.GetFixedStepLoop().GetFixedStepMsec();
		}
		if (nNowMsec >= nNextInputMsec)
		{
			nNextInputMsec = nNowMsec + stHost.GetFixedStepLoop().GetFixedStepMsec();
		}
	}
	if (eMode == ClientSessionMode::Acceptance && bMove && !bAwaitingReconnect && !bReconnecting && nSessionId != 0 && nSentInputs < 24 && nNowMsec >= nNextInputMsec)
	{
		Gameplay::PredictionInput stInput;
		if (!stPrediction.PredictInput(Gameplay::Vector3{ 1.0F, 0.0F, 0.0F }, stInput))
		{
			eStatus = RuntimeStatus::InvalidState;
			return eStatus;
		}
		eStatus = SendInput(*pTransport, nSessionId, nEntityId, stInput, nNowMsec);
		if (eStatus != RuntimeStatus::Ok)
		{
			return eStatus;
		}
		mapUnacknowledgedInputs.emplace(stInput.nSequence, stInput);
		nUnacknowledgedHighWater = nUnacknowledgedHighWater < mapUnacknowledgedInputs.size() ? mapUnacknowledgedInputs.size() : nUnacknowledgedHighWater;
		++nSentInputs;
		nNextInputMsec = nNowMsec + stHost.GetFixedStepLoop().GetFixedStepMsec();
		if (in_stConfig.bReconnectTest && !bReconnectAttempted && nSentInputs == 12)
		{
			bReconnectAttempted = true;
			bAwaitingReconnect = true;
			nReconnectAtMsec = nNowMsec + 600;
			std::cout << "ENGINE_NEXT_CLIENT_RECONNECT_WAIT client_id=A session_id=" << nSessionId
					  << " entity_id=" << nEntityId << " sent=" << nSentInputs << " offline_ms=600\n"
					  << std::flush;
			eStatus = pTransport->Disconnect(1);
			pTransport->Stop();
			if (eStatus != RuntimeStatus::Ok)
			{
				return eStatus;
			}
			return RuntimeStatus::Ok;
		}
	}
	if ((bMove || eMode == ClientSessionMode::Interactive) && !bAwaitingReconnect && !bReconnecting && !bClosing && nSessionId != 0 && !mapUnacknowledgedInputs.empty() && nNowMsec >= nNextRetransmitMsec)
	{
		for (const std::pair<const std::uint64_t, Gameplay::PredictionInput> &stEntry : mapUnacknowledgedInputs)
		{
			eStatus = SendInput(*pTransport, nSessionId, nEntityId, stEntry.second, nNowMsec);
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			++nResentInputs;
		}
		nNextRetransmitMsec = nNowMsec + 32;
		if (eStatus != RuntimeStatus::Ok)
		{
			return eStatus;
		}
	}

	if (eMode == ClientSessionMode::Acceptance && bMove && !bPredictionComplete && nSentInputs == 24 && stPrediction.GetUnconfirmedInputCount() == 0 &&
		mapUnacknowledgedInputs.empty() && stPrediction.GetLastConfirmedSequence() == 24)
	{
		const Gameplay::PredictionState &stState = stPrediction.GetPredictedState();
		std::cout << "ENGINE_NEXT_CLIENT_PREDICTION client_id=" << in_stConfig.strClientId
				  << " confirmed=" << stPrediction.GetLastConfirmedSequence()
				  << " position_x=" << stState.vPosition.fX
				  << " history=" << stPrediction.GetUnconfirmedInputCount()
				  << " corrections=" << stPrediction.GetCorrectionCount()
				  << " retransmissions=" << nResentInputs << '\n'
				  << std::flush;
		bPredictionComplete = true;
	}
	if (eMode == ClientSessionMode::Acceptance && !bMove && nEntityId != 0 && !mapRemoteBuffers.empty())
	{
		for (const std::pair<const std::uint64_t, Gameplay::InterpolationBuffer> &stEntry : mapRemoteBuffers)
		{
			const std::uint64_t nElapsedMsec = nNowMsec - nLatestSnapshotLocalMsec;
			const std::uint64_t nEstimatedServerTime = nLatestServerTimeMsec + nElapsedMsec;
			const Gameplay::InterpolationResult stResult = stEntry.second.Sample(nEstimatedServerTime);
			if (!stResult.stState.has_value())
			{
				continue;
			}
			const SpawnDefinition *pSpawn = stScene.FindSpawn(EntityId{ stEntry.first });
			const float fSpawnX = pSpawn == nullptr ? 0.0F : pSpawn->vPosition.fX;
			const float fDisplacement = stResult.stState->vPosition.fX - fSpawnX;
			const bool bMovingSample = fDisplacement > 0.0001F || fDisplacement < -0.0001F;
			if (bMovingSample && !bRemoteSeen &&
				(stResult.eStatus == Gameplay::InterpolationStatus::Interpolated || stResult.eStatus == Gameplay::InterpolationStatus::Held))
			{
				bRemoteSeen = true;
				std::cout << "ENGINE_NEXT_CLIENT_REMOTE client_id=B entity_id=" << stEntry.first
						  << " position_x=" << stResult.stState->vPosition.fX
						  << " status=" << GetInterpolationStatusName(stResult.eStatus)
						  << " samples=" << stEntry.second.GetSampleCount()
						  << " server_time=" << stResult.stState->nServerTimeMsec << '\n'
						  << std::flush;
			}
			if (stResult.eStatus == Gameplay::InterpolationStatus::StaleHeld && !bStaleSeen)
			{
				bStaleSeen = true;
				nStaleServerTimeMsec = stResult.stState->nServerTimeMsec;
				std::cout << "ENGINE_NEXT_CLIENT_REMOTE client_id=B entity_id=" << stEntry.first
						  << " position_x=" << stResult.stState->vPosition.fX
						  << " status=stale_held samples=" << stEntry.second.GetSampleCount()
						  << " server_time=" << nStaleServerTimeMsec << '\n'
						  << std::flush;
			}
			if (bStaleSeen && !bRemoteRecovered && bMovingSample && stResult.stState->nServerTimeMsec > nStaleServerTimeMsec &&
				(stResult.eStatus == Gameplay::InterpolationStatus::Interpolated || stResult.eStatus == Gameplay::InterpolationStatus::Held))
			{
				bRemoteRecovered = true;
				std::cout << "ENGINE_NEXT_CLIENT_REMOTE client_id=B entity_id=" << stEntry.first
						  << " position_x=" << stResult.stState->vPosition.fX
						  << " status=" << GetInterpolationStatusName(stResult.eStatus)
						  << " samples=" << stEntry.second.GetSampleCount()
						  << " server_time=" << stResult.stState->nServerTimeMsec << '\n'
						  << std::flush;
			}
		}
	}
	if (eMode == ClientSessionMode::Acceptance && !in_stConfig.bReconnectTest && ((bMove && bPredictionComplete) || (!bMove && bRemoteSeen)))
	{
		Network::Disconnect stDisconnect;
		stDisconnect.nReason = static_cast<std::uint16_t>(Network::DisconnectReason::ClientLeaving);
		eStatus = SendDisconnect(*pTransport, nSessionId, stDisconnect, nNowMsec);
		if (eStatus != RuntimeStatus::Ok)
		{
			return eStatus;
		}
		bClosing = true;
		bCloseSucceeded = true;
		nDisconnectAtMsec = nNowMsec + 32;
		nCloseDeadlineMsec = nNowMsec + 1000;
	}
	return eStatus;
}

void ClientSession::State::PrintBounds() const
{
	std::size_t nRemoteHighWater = 0;
	for (const std::pair<const std::uint64_t, std::size_t> &stEntry : mapRemoteHighWater)
	{
		nRemoteHighWater = nRemoteHighWater < stEntry.second ? stEntry.second : nRemoteHighWater;
	}
	const Network::TransportStats stTransportStats = pTransport->GetStats();
	std::cout << "ENGINE_NEXT_CLIENT_BOUNDS client_id=" << in_stConfig.strClientId
			  << " prediction_history=" << stPrediction.GetHistoryHighWater()
			  << " unconfirmed_transport=" << nUnacknowledgedHighWater
			  << " interpolation=" << nRemoteHighWater
			  << " enet_outgoing_high_water=" << stTransportStats.nOutgoingPacketHighWater
			  << " poll_event_high_water=" << stTransportStats.nPollEventHighWater << '\n'
			  << std::flush;
	std::cout << "ENGINE_NEXT_IMPAIRMENT client_id=" << in_stConfig.strClientId
			  << " dropped_input=" << pTransport->GetDroppedFirstInput()
			  << " dropped_loss=" << pTransport->GetDroppedForLoss()
			  << " dropped_overflow=" << pTransport->GetDroppedForOverflow()
			  << " high_water=" << pTransport->GetQueueHighWater() << '\n'
			  << std::flush;
}

ClientSession::ClientSession() = default;
ClientSession::~ClientSession()
{
	Shutdown();
}

RuntimeStatus ClientSession::Initialize(const RuntimeConfig &stConfig, ClientSessionMode eMode)
{
	return Initialize(stConfig, std::unique_ptr<Network::ITransport>(Network::CreateEnetTransport()), eMode);
}

RuntimeStatus ClientSession::Initialize(const RuntimeConfig &stConfig, std::unique_ptr<Network::ITransport> pTransport, ClientSessionMode eMode)
{
	if (pState != nullptr)
	{
		return RuntimeStatus::AlreadyExists;
	}
	if (eMode != ClientSessionMode::Interactive && eMode != ClientSessionMode::Acceptance)
	{
		return RuntimeStatus::InvalidParameter;
	}
	std::unique_ptr<State> pCandidate = std::make_unique<State>();
	const RuntimeStatus eStatus = pCandidate->Initialize(stConfig, std::move(pTransport), eMode);
	if (eStatus != RuntimeStatus::Ok)
	{
		if (pCandidate->pTransport != nullptr)
		{
			pCandidate->pTransport->Stop();
		}
		return eStatus;
	}
	pState = std::move(pCandidate);
	return RuntimeStatus::Ok;
}

RuntimeStatus ClientSession::Tick(std::uint64_t nNowMsec, const Gameplay::Vector3 &vMovement)
{
	if (pState == nullptr || !pState->bInitialized)
	{
		return RuntimeStatus::InvalidState;
	}
	if ((pState->bHasTime && nNowMsec < pState->nNowMsec) || nNowMsec > std::numeric_limits<std::uint64_t>::max() - 60000 ||
		!vMovement.IsFinite() || vMovement.LengthSquared() > 1.000001F)
	{
		return RuntimeStatus::InvalidParameter;
	}
	if (pState->eStatus != RuntimeStatus::Ok)
	{
		return pState->eStatus;
	}
	pState->nNowMsec = nNowMsec;
	pState->bHasTime = true;
	pState->eStatus = pState->Step(vMovement);
	if (pState->eStatus != RuntimeStatus::Ok || pState->bSucceeded)
	{
		pState->bConnected = false;
		pState->pTransport->Stop();
	}
	return pState->eStatus;
}

RuntimeStatus ClientSession::QueueMovementPulse(const Gameplay::Vector3 &vMovement)
{
	if (!vMovement.IsFinite() || vMovement.LengthSquared() == 0 || vMovement.LengthSquared() > 1.000001F)
	{
		return RuntimeStatus::InvalidParameter;
	}
	if (!IsConnected() || pState->eMode != ClientSessionMode::Interactive)
	{
		return RuntimeStatus::InvalidState;
	}
	pState->vPendingMovement = vMovement;
	return RuntimeStatus::Ok;
}

ClientSnapshot ClientSession::GetSnapshot() const
{
	ClientSnapshot stResult;
	if (pState == nullptr)
	{
		return stResult;
	}
	stResult.nGeneration = pState->nGeneration;
	stResult.nSessionId = pState->nSessionId;
	stResult.nSampleTimeMsec = pState->nNowMsec;
	stResult.bConnected = IsConnected();
	if (pState->nEntityId == 0)
	{
		return stResult;
	}
	stResult.arrEntities.push_back(ClientEntitySnapshot{ EntityId{ pState->nEntityId }, pState->stPrediction.GetPredictedState(), Gameplay::InterpolationStatus::Empty, true });
	const std::uint64_t nElapsed = pState->nNowMsec - pState->nLatestSnapshotLocalMsec;
	const std::uint64_t nMaximum = std::numeric_limits<std::uint64_t>::max();
	const std::uint64_t nEstimatedServerTime = nElapsed > nMaximum - pState->nLatestServerTimeMsec ? nMaximum : pState->nLatestServerTimeMsec + nElapsed;
	for (const std::pair<const std::uint64_t, Gameplay::InterpolationBuffer> &stEntry : pState->mapRemoteBuffers)
	{
		const Gameplay::InterpolationResult stSample = stEntry.second.Sample(nEstimatedServerTime);
		if (stSample.stState.has_value())
		{
			stResult.arrEntities.push_back(ClientEntitySnapshot{ EntityId{ stEntry.first }, *stSample.stState, stSample.eStatus, false });
		}
	}
	return stResult;
}

std::string ClientSession::GetPackageDigest() const
{
	return pState == nullptr ? std::string{} : pState->stHost.GetSceneRuntime().GetPackageDigest();
}

bool ClientSession::IsConnected() const noexcept
{
	return pState != nullptr && pState->bConnected && !pState->bAwaitingReconnect && !pState->bReconnecting && !pState->bClosing;
}

bool ClientSession::HasSucceeded() const noexcept
{
	return pState != nullptr && pState->bSucceeded && pState->eStatus == RuntimeStatus::Ok;
}

RuntimeStatus ClientSession::RequestReconnect(std::uint64_t nDelayMsec)
{
	if (pState == nullptr || !IsConnected() || nDelayMsec > 60000)
	{
		return RuntimeStatus::InvalidState;
	}
	const RuntimeStatus eStatus = pState->pTransport->Disconnect(1);
	if (eStatus != RuntimeStatus::Ok)
	{
		return eStatus;
	}
	pState->pTransport->Stop();
	pState->vPendingMovement = {};
	pState->bConnected = false;
	pState->bReconnectAttempted = true;
	pState->bAwaitingReconnect = true;
	pState->nReconnectAtMsec = pState->nNowMsec + nDelayMsec;
	return RuntimeStatus::Ok;
}

void ClientSession::Shutdown() noexcept
{
	if (pState != nullptr)
	{
		if (pState->pTransport != nullptr)
		{
			if (pState->eMode == ClientSessionMode::Acceptance)
			{
				pState->PrintBounds();
			}
			pState->pTransport->Stop();
		}
		pState->stHost.Shutdown();
		pState.reset();
	}
}

} // namespace EngineNext::Runtime
