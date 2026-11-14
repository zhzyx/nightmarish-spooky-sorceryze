/**************************************************************************/
/*  ClientRuntime.cpp                                                     */
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

#include "engine_next/Client/ClientRuntime.h"

#include "engine_next/include/EngineNext/Gameplay/InterpolationBuffer.h"
#include "engine_next/include/EngineNext/Gameplay/PredictionReconciler.h"
#include "engine_next/include/EngineNext/Network/ITransport.h"
#include "engine_next/include/EngineNext/Network/ImpairmentTransport.h"
#include "engine_next/include/EngineNext/Network/Protocol.h"
#include "engine_next/include/EngineNext/Runtime/Clock.h"

#include <algorithm>
#include <chrono>
#include <iostream>
#include <map>
#include <memory>
#include <thread>
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

RuntimeStatus SendInput(Network::ITransport &in_stTransport, std::uint64_t nSessionId, std::uint64_t nEntityId, const Gameplay::PredictionInput &in_stInput)
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
	return in_stTransport.Send(1, 1, false, arrFrame);
}

RuntimeStatus SendDisconnect(Network::ITransport &in_stTransport, std::uint64_t nSessionId, const Network::Disconnect &in_stDisconnect)
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
	return in_stTransport.Send(1, 0, true, arrFrame);
}

} // namespace

RuntimeStatus RunClient(const RuntimeConfig &in_stConfig)
{
	std::unique_ptr<Network::ITransport> pEnetTransport(Network::CreateEnetTransport());
	if (pEnetTransport == nullptr)
	{
		return RuntimeStatus::InvalidState;
	}
	Network::ImpairmentConfig stImpairmentConfig;
	stImpairmentConfig.nSeed = in_stConfig.nSeed;
	stImpairmentConfig.nDelayMsec = in_stConfig.nImpairmentDelayMsec;
	stImpairmentConfig.nJitterMsec = in_stConfig.nImpairmentJitterMsec;
	stImpairmentConfig.nLossPermille = in_stConfig.nImpairmentLossPermille;
	stImpairmentConfig.nQueueCapacity = in_stConfig.nImpairmentQueueCapacity;
	stImpairmentConfig.bDropFirstInput = in_stConfig.bDropFirstInput;
	std::unique_ptr<Network::ImpairmentTransport> pTransport = std::make_unique<Network::ImpairmentTransport>(std::move(pEnetTransport), stImpairmentConfig);
	RuntimeStatus eStatus = pTransport->StartClient(in_stConfig.strBindAddress, in_stConfig.nPort);
	if (eStatus != RuntimeStatus::Ok)
	{
		return eStatus;
	}
	RuntimeHost stHost(RuntimeRole::Client);
	eStatus = stHost.Initialize(in_stConfig);
	if (eStatus != RuntimeStatus::Ok)
	{
		pTransport->Stop();
		return eStatus;
	}

	SystemClock stClock;
	Gameplay::PredictionReconciler stPrediction;
	std::map<std::uint64_t, Gameplay::InterpolationBuffer> mapRemoteBuffers;
	std::map<std::uint64_t, Gameplay::PredictionInput> mapUnacknowledgedInputs;
	std::map<std::uint64_t, std::size_t> mapRemoteHighWater;
	std::size_t nUnacknowledgedHighWater = 0;
	const bool bMove = in_stConfig.strClientId == "A";
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
	const std::uint64_t nStartedMsec = stClock.NowMsec();
	while (!bSucceeded && stClock.NowMsec() - nStartedMsec < in_stConfig.nDurationMsec)
	{
		const std::uint64_t nNowMsec = stClock.NowMsec();
		if (bAwaitingReconnect)
		{
			if (nNowMsec < nReconnectAtMsec)
			{
				std::this_thread::sleep_for(std::chrono::milliseconds(1));
				continue;
			}
			eStatus = pTransport->StartClient(in_stConfig.strBindAddress, in_stConfig.nPort);
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			bAwaitingReconnect = false;
			bReconnecting = true;
			std::cout << "ENGINE_NEXT_CLIENT_RECONNECT client_id=" << in_stConfig.strClientId << " session_id=" << nSessionId
					  << " entity_id=" << nEntityId << " offline_ms=600\n"
					  << std::flush;
		}
		std::vector<Network::TransportEvent> arrEvents;
		eStatus = pTransport->Poll(arrEvents);
		if (eStatus != RuntimeStatus::Ok)
		{
			std::cout << "ENGINE_NEXT_CLIENT_POLL_ERROR client_id=" << in_stConfig.strClientId << " status=" << static_cast<int>(eStatus) << '\n'
					  << std::flush;
			break;
		}
		for (const Network::TransportEvent &stEvent : arrEvents)
		{
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
					eStatus = pTransport->Send(1, 0, true, arrFrame);
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
				if (stHeader.nSessionId == 0 || (bResume && (stHeader.nSessionId != nSessionId || stWelcome.nEntityId != nEntityId || stWelcome.arrResumeToken == arrResumeToken)))
				{
					eStatus = RuntimeStatus::InvalidParameter;
					break;
				}
				Gameplay::PredictionState stInitialState;
				stInitialState.vPosition = stWelcome.vPosition;
				stInitialState.vVelocity = stWelcome.vVelocity;
				stInitialState.nConfirmedSequence = stWelcome.nConfirmedInputSequence;
				stInitialState.nServerTimeMsec = stWelcome.nServerTick * stWelcome.nFixedStepMsec;
				float fResumeError = 0.0F;
				const bool bStateRestored = bResume ? stPrediction.RestoreAfterReconnect(stInitialState, fResumeError) : stPrediction.SetInitialState(stInitialState);
				if (!bStateRestored)
				{
					eStatus = RuntimeStatus::InvalidState;
					break;
				}
				nSessionId = stHeader.nSessionId;
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
					eStatus = SendDisconnect(*pTransport, nSessionId, stComplete);
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
				eStatus = SendDisconnect(*pTransport, nSessionId, stAcknowledge);
				bDrainReceived = true;
				bClosing = true;
				bDisconnectSent = false;
				nDisconnectAtMsec = nNowMsec + 32;
				nCloseDeadlineMsec = nNowMsec + 1000;
				const bool bGameplayComplete = bMove
						? bPredictionComplete && (!in_stConfig.bReconnectTest || bReconnectComplete)
						: bRemoteSeen && (!in_stConfig.bReconnectTest || (bStaleSeen && bRemoteRecovered));
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
			Gameplay::PredictionState stState;
			stState.vPosition = stSnapshot.vPosition;
			stState.vVelocity = stSnapshot.vVelocity;
			stState.nConfirmedSequence = stSnapshot.nLastProcessedInputSequence;
			stState.nServerTimeMsec = stSnapshot.nServerTick * 16;
			nLatestServerTimeMsec = stState.nServerTimeMsec;
			nLatestSnapshotLocalMsec = stClock.NowMsec();
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
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		if (bClosing)
		{
			if (!bDisconnectSent && nNowMsec >= nDisconnectAtMsec)
			{
				eStatus = pTransport->DisconnectLater(1);
				bDisconnectSent = true;
				if (eStatus == RuntimeStatus::NotFound && bCloseSucceeded && (bCompletionSent || !bDrainReceived))
				{
					std::cout << "ENGINE_NEXT_CLIENT_CLOSE_TRANSPORT client_id=" << in_stConfig.strClientId << " already_disconnected=1\n"
							  << std::flush;
					bSucceeded = true;
					eStatus = RuntimeStatus::Ok;
					break;
				}
				if (eStatus != RuntimeStatus::Ok)
				{
					std::cout << "ENGINE_NEXT_CLIENT_CLOSE_ERROR client_id=" << in_stConfig.strClientId << " status=" << static_cast<int>(eStatus)
							  << " drain=" << (bDrainReceived ? 1 : 0) << " ready=" << (bCloseSucceeded ? 1 : 0) << '\n'
							  << std::flush;
					break;
				}
			}
			if (nNowMsec >= nCloseDeadlineMsec)
			{
				std::cout << "ENGINE_NEXT_CLIENT_CLOSE_TIMEOUT client_id=" << in_stConfig.strClientId << " drain=" << (bDrainReceived ? 1 : 0) << '\n'
						  << std::flush;
				eStatus = RuntimeStatus::IoError;
				break;
			}
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
			continue;
		}

		if (bMove && !bAwaitingReconnect && !bReconnecting && nSessionId != 0 && nSentInputs < 24 && nNowMsec >= nNextInputMsec)
		{
			Gameplay::PredictionInput stInput;
			if (!stPrediction.PredictInput(Gameplay::Vector3{ 1.0F, 0.0F, 0.0F }, stInput))
			{
				eStatus = RuntimeStatus::InvalidState;
				break;
			}
			eStatus = SendInput(*pTransport, nSessionId, nEntityId, stInput);
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			mapUnacknowledgedInputs.emplace(stInput.nSequence, stInput);
			nUnacknowledgedHighWater = nUnacknowledgedHighWater < mapUnacknowledgedInputs.size() ? mapUnacknowledgedInputs.size() : nUnacknowledgedHighWater;
			++nSentInputs;
			nNextInputMsec = nNowMsec + 16;
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
					break;
				}
				continue;
			}
		}
		if (bMove && !bAwaitingReconnect && !bReconnecting && !bClosing && nSessionId != 0 && !mapUnacknowledgedInputs.empty() && nNowMsec >= nNextRetransmitMsec)
		{
			for (const std::pair<const std::uint64_t, Gameplay::PredictionInput> &stEntry : mapUnacknowledgedInputs)
			{
				eStatus = SendInput(*pTransport, nSessionId, nEntityId, stEntry.second);
				if (eStatus != RuntimeStatus::Ok)
				{
					break;
				}
				++nResentInputs;
			}
			nNextRetransmitMsec = nNowMsec + 32;
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
		}

		if (bMove && !bPredictionComplete && nSentInputs == 24 && stPrediction.GetUnconfirmedInputCount() == 0 &&
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
		if (!bMove && nEntityId != 0 && !mapRemoteBuffers.empty())
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
				const bool bMovingSample = stResult.stState->vPosition.fX > 0.0F;
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
		if (!in_stConfig.bReconnectTest && ((bMove && bPredictionComplete) || (!bMove && bRemoteSeen)))
		{
			Network::Disconnect stDisconnect;
			stDisconnect.nReason = static_cast<std::uint16_t>(Network::DisconnectReason::ClientLeaving);
			eStatus = SendDisconnect(*pTransport, nSessionId, stDisconnect);
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			bClosing = true;
			bCloseSucceeded = true;
			nDisconnectAtMsec = nNowMsec + 32;
			nCloseDeadlineMsec = nNowMsec + 1000;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
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
	pTransport->Stop();
	stHost.Shutdown();
	return bSucceeded && eStatus == RuntimeStatus::Ok ? RuntimeStatus::Ok : RuntimeStatus::IoError;
}

} // namespace EngineNext::Runtime
