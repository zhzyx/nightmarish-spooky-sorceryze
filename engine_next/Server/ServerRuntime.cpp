/**************************************************************************/
/*  ServerRuntime.cpp                                                     */
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

#include "engine_next/Server/ServerRuntime.h"

#include "engine_next/Network/SessionManager.h"
#include "engine_next/include/EngineNext/Gameplay/PredictionModel.h"
#include "engine_next/include/EngineNext/Runtime/Clock.h"

#include <chrono>
#include <deque>
#include <iostream>
#include <map>
#include <memory>
#include <thread>

namespace EngineNext::Runtime
{
namespace
{

struct EntityInputQueue
{
	std::deque<Gameplay::PredictionInput> arrInputs;
	std::uint64_t nLastProcessedSequence = 0;
};

struct DrainState
{
	bool bActive = false;
	bool bFailed = false;
	std::uint64_t nDeadlineMsec = 0;
	std::uint64_t nDeadlineTick = 0;
	std::map<Network::PeerId, std::uint64_t> mapPendingAcknowledges;
	std::map<Network::PeerId, std::uint64_t> mapCompletionAcknowledges;
	std::size_t nNotified = 0;
	std::size_t nAcknowledged = 0;
	std::size_t nForced = 0;
};

std::uint64_t NextSequence(std::map<Network::PeerId, std::uint64_t> &mapSequences, Network::PeerId nPeerId)
{
	std::uint64_t &nSequence = mapSequences[nPeerId];
	if (nSequence == 0)
	{
		nSequence = 1;
	}
	return nSequence++;
}

RuntimeStatus SendFrame(Network::ITransport &in_stTransport, Network::PeerId nPeerId, const Network::FrameHeader &in_stHeader, const std::vector<std::uint8_t> &in_arrPayload)
{
	std::vector<std::uint8_t> arrFrame;
	const RuntimeStatus eEncodeStatus = Network::EncodeFrame(in_stHeader, in_arrPayload, arrFrame);
	if (eEncodeStatus != RuntimeStatus::Ok)
	{
		return eEncodeStatus;
	}
	return in_stTransport.Send(nPeerId, 0, true, arrFrame);
}

void Reject(Network::ITransport &in_stTransport, Network::PeerId nPeerId, std::map<Network::PeerId, std::uint64_t> &mapSequences, const Network::FrameHeader &in_stIncoming, std::uint16_t nReason, bool bFatal = true)
{
	Network::ErrorReject stError;
	stError.nRejectedType = static_cast<std::uint16_t>(in_stIncoming.eType);
	stError.nReason = nReason;
	stError.nFatal = bFatal ? 1 : 0;
	stError.nRejectedSequence = in_stIncoming.nMessageSequence;
	std::cout << "ENGINE_NEXT_REJECT peer_id=" << nPeerId << " type=" << stError.nRejectedType << " reason=" << nReason
			  << " fatal=" << (bFatal ? 1 : 0) << '\n'
			  << std::flush;
	Network::FrameHeader stHeader;
	stHeader.eType = Network::MessageType::ErrorReject;
	stHeader.nMessageSequence = NextSequence(mapSequences, nPeerId);
	stHeader.nSessionId = in_stIncoming.nSessionId;
	(void)SendFrame(in_stTransport, nPeerId, stHeader, Network::EncodeErrorReject(stError));
	(void)in_stTransport.DisconnectLater(nPeerId);
}

RuntimeStatus SendSnapshot(Network::ITransport &in_stTransport, const Network::Session &in_stRecipient, std::uint64_t nEntityId, std::uint64_t nServerTick, const Gameplay::PredictionState &in_stState, std::uint64_t nLastProcessed)
{
	Network::Snapshot stSnapshot;
	stSnapshot.nServerTick = nServerTick;
	stSnapshot.nEntityId = nEntityId;
	stSnapshot.nLastProcessedInputSequence = nLastProcessed;
	stSnapshot.vPosition = in_stState.vPosition;
	stSnapshot.vVelocity = in_stState.vVelocity;
	Network::FrameHeader stHeader;
	stHeader.eType = Network::MessageType::Snapshot;
	stHeader.nMessageSequence = nServerTick;
	stHeader.nSessionId = in_stRecipient.nSessionId;
	std::vector<std::uint8_t> arrFrame;
	const RuntimeStatus eEncodeStatus = Network::EncodeFrame(stHeader, Network::EncodeSnapshot(stSnapshot), arrFrame);
	if (eEncodeStatus != RuntimeStatus::Ok)
	{
		return eEncodeStatus;
	}
	return in_stTransport.Send(in_stRecipient.nPeerId, 1, true, arrFrame);
}

RuntimeStatus BeginDrain(Network::ITransport &in_stTransport, Network::SessionManager &in_stSessions, std::map<Network::PeerId, std::uint64_t> &mapSequences, std::uint64_t nNowMsec, std::uint64_t nTick, std::uint32_t nTimeoutMsec, DrainState &out_stDrain)
{
	out_stDrain.bActive = true;
	out_stDrain.nDeadlineMsec = nNowMsec + nTimeoutMsec;
	out_stDrain.nDeadlineTick = nTick + (nTimeoutMsec + 15) / 16;
	for (const std::pair<const Network::PeerId, Network::Session> &stEntry : in_stSessions.GetSessions())
	{
		Network::Disconnect stDisconnect;
		stDisconnect.nReason = static_cast<std::uint16_t>(Network::DisconnectReason::ServerDraining);
		stDisconnect.nDrainDeadlineTick = out_stDrain.nDeadlineTick;
		Network::FrameHeader stHeader;
		stHeader.eType = Network::MessageType::Disconnect;
		stHeader.nMessageSequence = NextSequence(mapSequences, stEntry.first);
		stHeader.nSessionId = stEntry.second.nSessionId;
		const RuntimeStatus eStatus = SendFrame(in_stTransport, stEntry.first, stHeader, Network::EncodeDisconnect(stDisconnect));
		if (eStatus != RuntimeStatus::Ok)
		{
			return eStatus;
		}
		out_stDrain.mapPendingAcknowledges.emplace(stEntry.first, stHeader.nMessageSequence);
		++out_stDrain.nNotified;
	}
	std::cout << "ENGINE_NEXT_DRAIN_BEGIN peers=" << out_stDrain.nNotified << " deadline_tick=" << out_stDrain.nDeadlineTick << '\n'
			  << std::flush;
	return RuntimeStatus::Ok;
}

} // namespace

RuntimeStatus RunServer(const RuntimeConfig &in_stConfig)
{
	std::unique_ptr<Network::ITransport> pTransport(Network::CreateEnetTransport());
	if (pTransport == nullptr)
	{
		return RuntimeStatus::InvalidState;
	}
	RuntimeStatus eStatus = pTransport->StartServer(in_stConfig.strBindAddress, in_stConfig.nPort, 8);
	if (eStatus != RuntimeStatus::Ok)
	{
		return eStatus;
	}
	RuntimeHost stHost(RuntimeRole::Server);
	eStatus = stHost.Initialize(in_stConfig);
	if (eStatus != RuntimeStatus::Ok)
	{
		pTransport->Stop();
		return eStatus;
	}

	Network::SessionManager stSessions(stHost.GetWorld(), in_stConfig.nSeed);
	SystemClock stClock;
	FixedStepBatch stPrimeBatch;
	(void)stHost.GetFixedStepLoop().Advance(stClock.NowMsec(), stPrimeBatch);
	std::map<Network::PeerId, std::uint64_t> mapSequences;
	std::map<std::uint64_t, EntityInputQueue> mapInputQueues;
	Gameplay::PredictionModel stModel;
	DrainState stDrain;
	const std::uint64_t nStartedMsec = stClock.NowMsec();
	std::uint32_t nCreatedSessions = 0;
	std::uint32_t nResumedSessions = 0;
	bool bStopped = false;
	std::cout << "ENGINE_NEXT_SERVER_READY port=" << pTransport->GetBoundPort() << '\n'
			  << std::flush;

	while (!bStopped && stClock.NowMsec() - nStartedMsec < in_stConfig.nDurationMsec)
	{
		const std::uint64_t nNowMsec = stClock.NowMsec();
		std::vector<Network::TransportEvent> arrEvents;
		eStatus = pTransport->Poll(arrEvents);
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		for (const Network::TransportEvent &stEvent : arrEvents)
		{
			if (stEvent.eType == Network::TransportEventType::Disconnected)
			{
				const Network::Session *pSession = stSessions.GetSession(stEvent.nPeerId);
				const std::uint64_t nDisconnectedSessionId = pSession == nullptr ? 0 : pSession->nSessionId;
				const Runtime::EntityId stDisconnectedEntityId = pSession == nullptr ? Runtime::EntityId{} : pSession->stEntityId;
				if (stDrain.mapPendingAcknowledges.find(stEvent.nPeerId) != stDrain.mapPendingAcknowledges.end())
				{
					++stDrain.nForced;
					stDrain.bFailed = true;
					stDrain.mapPendingAcknowledges.erase(stEvent.nPeerId);
					if (pSession != nullptr)
					{
						mapInputQueues.erase(stDisconnectedEntityId.nValue);
						(void)stSessions.RemoveSession(stEvent.nPeerId);
					}
					std::cout << "ENGINE_NEXT_DRAIN_FORCED peer_id=" << stEvent.nPeerId << '\n'
							  << std::flush;
				}
				else if (pSession != nullptr && stSessions.DisconnectSession(stEvent.nPeerId, nNowMsec))
				{
					std::cout << "ENGINE_NEXT_DISCONNECT peer_id=" << stEvent.nPeerId << " session_id=" << nDisconnectedSessionId
							  << " entity_id=" << stDisconnectedEntityId.nValue << " grace_ms=5000\n"
							  << std::flush;
				}
				mapSequences.erase(stEvent.nPeerId);
				continue;
			}
			if (stEvent.eType == Network::TransportEventType::Connected)
			{
				std::cout << "ENGINE_NEXT_TRANSPORT_CONNECT peer_id=" << stEvent.nPeerId << '\n'
						  << std::flush;
				continue;
			}
			if (stEvent.eType != Network::TransportEventType::Packet)
			{
				continue;
			}
			Network::FrameHeader stHeader;
			const RuntimeStatus eDecodeStatus = Network::DecodeHeader(stEvent.arrPayload.data(), stEvent.arrPayload.size(), stHeader);
			if (eDecodeStatus != RuntimeStatus::Ok)
			{
				Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 1);
				continue;
			}
			if (stHeader.eType == Network::MessageType::Disconnect)
			{
				Network::Disconnect stDisconnect;
				const Network::Session *pSession = stSessions.GetSession(stEvent.nPeerId);
				if (Network::DecodeDisconnect(stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stDisconnect) != RuntimeStatus::Ok ||
					pSession == nullptr || pSession->nSessionId != stHeader.nSessionId)
				{
					Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 6);
					continue;
				}
				const std::map<Network::PeerId, std::uint64_t>::const_iterator stPending = stDrain.mapPendingAcknowledges.find(stEvent.nPeerId);
				const std::map<Network::PeerId, std::uint64_t>::const_iterator stCompletion = stDrain.mapCompletionAcknowledges.find(stEvent.nPeerId);
				const bool bDrainAcknowledge = stDrain.bActive && stPending != stDrain.mapPendingAcknowledges.end() &&
						stCompletion == stDrain.mapCompletionAcknowledges.end() &&
						stDisconnect.nReason == static_cast<std::uint16_t>(Network::DisconnectReason::DrainAcknowledge) &&
						stDisconnect.nAcknowledgeSequence == stPending->second && stDisconnect.nDrainDeadlineTick == stDrain.nDeadlineTick;
				const bool bDrainComplete = stDrain.bActive && stPending != stDrain.mapPendingAcknowledges.end() &&
						stCompletion != stDrain.mapCompletionAcknowledges.end() &&
						stDisconnect.nReason == static_cast<std::uint16_t>(Network::DisconnectReason::DrainComplete) &&
						stDisconnect.nAcknowledgeSequence == stCompletion->second && stDisconnect.nDrainDeadlineTick == stDrain.nDeadlineTick;
				const bool bClientLeaving = !stDrain.bActive && stDisconnect.nReason == static_cast<std::uint16_t>(Network::DisconnectReason::ClientLeaving);
				if (!bDrainAcknowledge && !bDrainComplete && !bClientLeaving)
				{
					Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 9);
					continue;
				}
				if (bDrainAcknowledge)
				{
					Network::Disconnect stResponse;
					stResponse.nReason = static_cast<std::uint16_t>(Network::DisconnectReason::DrainAcknowledge);
					stResponse.nAcknowledgeSequence = stHeader.nMessageSequence;
					stResponse.nDrainDeadlineTick = stDrain.nDeadlineTick;
					Network::FrameHeader stResponseHeader;
					stResponseHeader.eType = Network::MessageType::Disconnect;
					stResponseHeader.nMessageSequence = NextSequence(mapSequences, stEvent.nPeerId);
					stResponseHeader.nSessionId = stHeader.nSessionId;
					eStatus = SendFrame(*pTransport, stEvent.nPeerId, stResponseHeader, Network::EncodeDisconnect(stResponse));
					if (eStatus != RuntimeStatus::Ok)
					{
						break;
					}
					stDrain.mapCompletionAcknowledges.emplace(stEvent.nPeerId, stResponseHeader.nMessageSequence);
					std::cout << "ENGINE_NEXT_DRAIN_ACK peer_id=" << stEvent.nPeerId << " session_id=" << stHeader.nSessionId << '\n'
							  << std::flush;
					continue;
				}
				const Runtime::EntityId stEntityId = pSession->stEntityId;
				mapInputQueues.erase(stEntityId.nValue);
				(void)stSessions.RemoveSession(stEvent.nPeerId);
				(void)stHost.RecordTrace(stHost.GetFixedStepLoop().GetTick(), "session_disconnected", stEntityId, stHeader.nSessionId);
				if (bDrainComplete)
				{
					stDrain.mapPendingAcknowledges.erase(stEvent.nPeerId);
					stDrain.mapCompletionAcknowledges.erase(stEvent.nPeerId);
					++stDrain.nAcknowledged;
					(void)pTransport->DisconnectLater(stEvent.nPeerId);
					std::cout << "ENGINE_NEXT_DRAIN_COMPLETE_PEER peer_id=" << stEvent.nPeerId << " session_id=" << stHeader.nSessionId << '\n'
							  << std::flush;
				}
				else
				{
					(void)pTransport->Disconnect(stEvent.nPeerId);
					std::cout << "ENGINE_NEXT_DISCONNECT peer_id=" << stEvent.nPeerId << " session_id=" << stHeader.nSessionId << '\n'
							  << std::flush;
				}
				continue;
			}
			if (stHeader.eType == Network::MessageType::Input)
			{
				if (stDrain.bActive)
				{
					continue;
				}
				const Network::Session *pSession = stSessions.GetSession(stEvent.nPeerId);
				Network::InputCommand stCommand;
				const RuntimeStatus eInputStatus = Network::DecodeInputCommand(
						stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES,
						stHeader.nPayloadBytes,
						stCommand);
				if (stEvent.nChannelId != 1 || pSession == nullptr || pSession->nSessionId != stHeader.nSessionId ||
					pSession->stEntityId.nValue != stCommand.nEntityId || eInputStatus != RuntimeStatus::Ok)
				{
					Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 6);
					continue;
				}
				EntityInputQueue &stQueue = mapInputQueues[stCommand.nEntityId];
				if (stCommand.stInput.nSequence <= stQueue.nLastProcessedSequence)
				{
					const Gameplay::PredictionState *pState = stHost.GetWorld().Find(pSession->stEntityId);
					if (pState == nullptr)
					{
						eStatus = RuntimeStatus::InvalidState;
						break;
					}
					eStatus = SendSnapshot(*pTransport, *pSession, pSession->stEntityId.nValue, stHost.GetFixedStepLoop().GetTick(), *pState, stQueue.nLastProcessedSequence);
					if (eStatus != RuntimeStatus::Ok)
					{
						break;
					}
					continue;
				}
				bool bDuplicate = false;
				std::deque<Gameplay::PredictionInput>::iterator stInsert = stQueue.arrInputs.begin();
				for (; stInsert != stQueue.arrInputs.end(); ++stInsert)
				{
					if (stInsert->nSequence == stCommand.stInput.nSequence)
					{
						bDuplicate = true;
						break;
					}
					if (stInsert->nSequence > stCommand.stInput.nSequence)
					{
						break;
					}
				}
				if (bDuplicate)
				{
					continue;
				}
				if (stCommand.stInput.nSequence > stQueue.nLastProcessedSequence + 32 ||
					stQueue.arrInputs.size() >= 64 || stCommand.stInput.nStepMsec != stModel.GetFixedStepMsec())
				{
					Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 7);
					continue;
				}
				stQueue.arrInputs.insert(stInsert, stCommand.stInput);
				continue;
			}
			if (stEvent.nChannelId != 0 || stHeader.eType != Network::MessageType::ClientHello)
			{
				Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 4);
				continue;
			}
			Network::ClientHello stHello;
			if (Network::DecodeClientHello(stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stHello) != RuntimeStatus::Ok)
			{
				Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 2);
				continue;
			}
			if (stDrain.bActive)
			{
				Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, Network::REJECT_SERVER_DRAINING, false);
				continue;
			}
			Network::ServerWelcome stWelcome;
			std::uint64_t nSessionId = 0;
			const bool bResume = stHello.nResumeSessionId != 0;
			const RuntimeStatus eSessionStatus = bResume
					? stSessions.ResumeSession(stEvent.nPeerId, stHello, nNowMsec, stWelcome, nSessionId)
					: stSessions.CreateSession(stEvent.nPeerId, stHello, stWelcome, nSessionId);
			if (eSessionStatus != RuntimeStatus::Ok)
			{
				std::cout << "ENGINE_NEXT_SESSION_REJECT peer_id=" << stEvent.nPeerId << " resume=" << (bResume ? 1 : 0)
						  << " session_id=" << stHello.nResumeSessionId << " status=" << static_cast<int>(eSessionStatus) << '\n'
						  << std::flush;
				Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 3);
				continue;
			}
			Network::FrameHeader stWelcomeHeader;
			stWelcomeHeader.eType = Network::MessageType::ServerWelcome;
			stWelcomeHeader.nMessageSequence = NextSequence(mapSequences, stEvent.nPeerId);
			stWelcomeHeader.nSessionId = nSessionId;
			eStatus = SendFrame(*pTransport, stEvent.nPeerId, stWelcomeHeader, Network::EncodeServerWelcome(stWelcome));
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			const Network::Session *pSession = stSessions.GetSession(stEvent.nPeerId);
			if (bResume)
			{
				++nResumedSessions;
				std::cout << "ENGINE_NEXT_RESUME peer_id=" << stEvent.nPeerId << " session_id=" << nSessionId
						  << " entity_id=" << stWelcome.nEntityId << " confirmed=" << stWelcome.nConfirmedInputSequence << '\n'
						  << std::flush;
				(void)stHost.RecordTrace(stHost.GetFixedStepLoop().GetTick(), "session_resumed", pSession->stEntityId, nSessionId);
			}
			else
			{
				++nCreatedSessions;
				std::cout << "ENGINE_NEXT_SESSION peer_id=" << stEvent.nPeerId << " session_id=" << nSessionId
						  << " entity_id=" << stWelcome.nEntityId << '\n'
						  << std::flush;
				(void)stHost.RecordTrace(stHost.GetFixedStepLoop().GetTick(), "session_spawned", pSession->stEntityId, nSessionId);
			}
		}
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		if (stDrain.bActive)
		{
			if (!stDrain.mapPendingAcknowledges.empty() && stClock.NowMsec() >= stDrain.nDeadlineMsec)
			{
				for (const std::pair<const Network::PeerId, std::uint64_t> &stEntry : stDrain.mapPendingAcknowledges)
				{
					std::cout << "ENGINE_NEXT_DRAIN_TIMEOUT peer_id=" << stEntry.first << '\n'
							  << std::flush;
					(void)pTransport->Disconnect(stEntry.first);
					++stDrain.nForced;
				}
				stDrain.bFailed = true;
			}
			if (stDrain.mapPendingAcknowledges.empty() || stDrain.bFailed)
			{
				std::cout << "ENGINE_NEXT_DRAIN_COMPLETE notified=" << stDrain.nNotified << " acknowledged=" << stDrain.nAcknowledged
						  << " forced=" << stDrain.nForced << " resumed=" << nResumedSessions << '\n'
						  << std::flush;
				bStopped = true;
				break;
			}
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
			continue;
		}
		FixedStepBatch stBatch;
		eStatus = stHost.GetFixedStepLoop().Advance(stClock.NowMsec(), stBatch);
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		for (std::uint32_t nStep = 0; nStep < stBatch.nStepCount; ++nStep)
		{
			const std::uint64_t nTick = stBatch.nFirstTick + nStep;
			for (std::pair<const std::uint64_t, EntityInputQueue> &stEntry : mapInputQueues)
			{
				EntityInputQueue &stQueue = stEntry.second;
				if (stQueue.arrInputs.empty() || stSessions.IsEntityDisconnected(stEntry.first))
				{
					continue;
				}
				if (stQueue.arrInputs.front().nSequence != stQueue.nLastProcessedSequence + 1)
				{
					continue;
				}
				const Gameplay::PredictionInput stInput = stQueue.arrInputs.front();
				stQueue.arrInputs.pop_front();
				Gameplay::PredictionState *pState = stHost.GetWorld().Find(Runtime::EntityId{ stEntry.first });
				if (pState == nullptr || stModel.Simulate(*pState, stInput) != Gameplay::Status::Ok)
				{
					return RuntimeStatus::InvalidState;
				}
				pState->nServerTimeMsec = nTick * stModel.GetFixedStepMsec();
				stQueue.nLastProcessedSequence = stInput.nSequence;
			}
			if (nTick % 3 != 0)
			{
				continue;
			}
			for (const std::pair<const Runtime::EntityId, Gameplay::PredictionState> &stEntity : stHost.GetWorld().GetEntities())
			{
				const std::uint64_t nOwnerEntityId = stEntity.first.nValue;
				const Gameplay::PredictionState &stState = stEntity.second;
				const EntityInputQueue &stQueue = mapInputQueues[nOwnerEntityId];
				if (stSessions.IsEntityDisconnected(nOwnerEntityId))
				{
					continue;
				}
				for (const std::pair<const Network::PeerId, Network::Session> &stRecipientEntry : stSessions.GetSessions())
				{
					const Network::Session &stRecipient = stRecipientEntry.second;
					eStatus = SendSnapshot(*pTransport, stRecipient, nOwnerEntityId, nTick, stState, stQueue.nLastProcessedSequence);
					(void)stHost.RecordTrace(nTick, "snapshot", Runtime::EntityId{ nOwnerEntityId }, stRecipient.nSessionId);
					if (eStatus != RuntimeStatus::Ok)
					{
						break;
					}
				}
				if (eStatus != RuntimeStatus::Ok)
				{
					break;
				}
			}
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
		}
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		std::vector<Runtime::EntityId> arrExpired;
		(void)stSessions.ExpireDisconnected(stClock.NowMsec(), arrExpired);
		for (const Runtime::EntityId stEntityId : arrExpired)
		{
			mapInputQueues.erase(stEntityId.nValue);
			std::cout << "ENGINE_NEXT_EXPIRE entity_id=" << stEntityId.nValue << '\n'
					  << std::flush;
		}
		if (in_stConfig.nDrainAfterMsec != 0 && stClock.NowMsec() - nStartedMsec >= in_stConfig.nDrainAfterMsec)
		{
			eStatus = BeginDrain(*pTransport, stSessions, mapSequences, stClock.NowMsec(), stHost.GetFixedStepLoop().GetTick(), in_stConfig.nDrainTimeoutMsec, stDrain);
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
		}
		else if (nCreatedSessions == 2 && stSessions.GetSessionCount() == 0 && stSessions.GetDisconnectedCount() == 0)
		{
			bStopped = true;
			break;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	const bool bGracefulDrain = stDrain.bActive && !stDrain.bFailed && stDrain.nNotified >= 2 &&
			stDrain.nAcknowledged == stDrain.nNotified && stDrain.nForced == 0;
	const bool bSessionsClosed = nCreatedSessions == 2 && stSessions.GetSessionCount() == 0 && stSessions.GetDisconnectedCount() == 0;
	pTransport->Stop();
	stHost.Shutdown();
	return eStatus == RuntimeStatus::Ok && (bGracefulDrain || bSessionsClosed) ? RuntimeStatus::Ok : RuntimeStatus::IoError;
}

} // namespace EngineNext::Runtime
