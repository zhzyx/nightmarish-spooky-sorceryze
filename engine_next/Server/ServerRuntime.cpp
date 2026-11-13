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

void Reject(Network::ITransport &in_stTransport, Network::PeerId nPeerId, std::map<Network::PeerId, std::uint64_t> &mapSequences, const Network::FrameHeader &in_stIncoming, std::uint16_t nReason)
{
	Network::ErrorReject stError;
	stError.nRejectedType = static_cast<std::uint16_t>(in_stIncoming.eType);
	stError.nReason = nReason;
	stError.nFatal = 1;
	stError.nRejectedSequence = in_stIncoming.nMessageSequence;
	Network::FrameHeader stHeader;
	stHeader.eType = Network::MessageType::ErrorReject;
	stHeader.nMessageSequence = NextSequence(mapSequences, nPeerId);
	stHeader.nSessionId = in_stIncoming.nSessionId;
	(void)SendFrame(in_stTransport, nPeerId, stHeader, Network::EncodeErrorReject(stError));
	(void)in_stTransport.Disconnect(nPeerId);
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
	const std::uint64_t nStartedMsec = stClock.NowMsec();
	std::uint32_t nWelcomed = 0;
	std::cout << "ENGINE_NEXT_SERVER_READY port=" << pTransport->GetBoundPort() << '\n'
			  << std::flush;

	while (stClock.NowMsec() - nStartedMsec < in_stConfig.nDurationMsec)
	{
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
				if (pSession != nullptr)
				{
					mapInputQueues.erase(pSession->stEntityId.nValue);
				}
				if (stSessions.RemoveSession(stEvent.nPeerId))
				{
					std::cout << "ENGINE_NEXT_DISCONNECT peer_id=" << stEvent.nPeerId << '\n';
				}
				mapSequences.erase(stEvent.nPeerId);
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
				const Network::Session *pSession = stSessions.GetSession(stEvent.nPeerId);
				if (pSession != nullptr && pSession->nSessionId == stHeader.nSessionId)
				{
					const Runtime::EntityId stEntityId = pSession->stEntityId;
					mapInputQueues.erase(stEntityId.nValue);
					(void)stSessions.RemoveSession(stEvent.nPeerId);
					(void)stHost.RecordTrace(stHost.GetFixedStepLoop().GetTick(), "session_disconnected", stEntityId, stHeader.nSessionId);
					std::cout << "ENGINE_NEXT_DISCONNECT peer_id=" << stEvent.nPeerId << '\n';
				}
				continue;
			}
			if (stHeader.eType == Network::MessageType::Input)
			{
				const Network::Session *pSession = stSessions.GetSession(stEvent.nPeerId);
				Network::InputCommand stCommand;
				const RuntimeStatus eInputStatus = Network::DecodeInputCommand(
						stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES,
						stHeader.nPayloadBytes,
						stCommand);
				if (pSession == nullptr || pSession->nSessionId != stHeader.nSessionId ||
					pSession->stEntityId.nValue != stCommand.nEntityId || eInputStatus != RuntimeStatus::Ok)
				{
					Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 6);
					continue;
				}
				EntityInputQueue &stQueue = mapInputQueues[stCommand.nEntityId];
				if (stCommand.stInput.nSequence <= stQueue.nLastProcessedSequence)
				{
					const Gameplay::PredictionState *pState = stHost.GetWorld().Find(pSession->stEntityId);
					eStatus = SendSnapshot(*pTransport, *pSession, pSession->stEntityId.nValue, stHost.GetFixedStepLoop().GetTick(), *pState, stQueue.nLastProcessedSequence);
					if (eStatus != RuntimeStatus::Ok)
					{
						break;
					}
					continue;
				}
				if (stCommand.stInput.nSequence > stQueue.nLastProcessedSequence + 32 ||
					stQueue.arrInputs.size() >= 64 || stCommand.stInput.nStepMsec != stModel.GetFixedStepMsec())
				{
					Reject(*pTransport, stEvent.nPeerId, mapSequences, stHeader, 7);
					continue;
				}
				stQueue.arrInputs.push_back(stCommand.stInput);
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
			Network::ServerWelcome stWelcome;
			std::uint64_t nSessionId = 0;
			const RuntimeStatus eSessionStatus = stSessions.CreateSession(stEvent.nPeerId, stHello, stWelcome, nSessionId);
			if (eSessionStatus != RuntimeStatus::Ok)
			{
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
			++nWelcomed;
			const Network::Session *pSession = stSessions.GetSession(stEvent.nPeerId);
			std::cout << "ENGINE_NEXT_SESSION peer_id=" << stEvent.nPeerId << " session_id=" << nSessionId
					  << " entity_id=" << stWelcome.nEntityId << '\n'
					  << std::flush;
			(void)stHost.RecordTrace(stHost.GetFixedStepLoop().GetTick(), "session_spawned", pSession->stEntityId, nSessionId);
		}
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
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
				if (stQueue.arrInputs.empty())
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
		if (nWelcomed == 2 && stSessions.GetSessionCount() == 0)
		{
			pTransport->Stop();
			stHost.Shutdown();
			return RuntimeStatus::Ok;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	pTransport->Stop();
	stHost.Shutdown();
	return eStatus == RuntimeStatus::Ok && nWelcomed == 2 && stSessions.GetSessionCount() == 0 ? RuntimeStatus::Ok : RuntimeStatus::IoError;
}

} // namespace EngineNext::Runtime
