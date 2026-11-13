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
#include "engine_next/include/EngineNext/Network/Protocol.h"
#include "engine_next/include/EngineNext/Runtime/Clock.h"

#include <chrono>
#include <cmath>
#include <iostream>
#include <map>
#include <memory>
#include <thread>

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

} // namespace

RuntimeStatus RunClient(const RuntimeConfig &in_stConfig)
{
	std::unique_ptr<Network::ITransport> pTransport(Network::CreateEnetTransport());
	if (pTransport == nullptr)
	{
		return RuntimeStatus::InvalidState;
	}
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
	const bool bMove = in_stConfig.strClientId == "A";
	std::uint64_t nSessionId = 0;
	std::uint64_t nEntityId = 0;
	std::uint64_t nSentInputs = 0;
	std::uint64_t nNextInputMsec = 0;
	std::uint64_t nLatestServerTimeMsec = 0;
	std::uint64_t nLatestSnapshotLocalMsec = 0;
	const std::uint64_t nStartedMsec = stClock.NowMsec();
	bool bComplete = false;
	while (!bComplete && stClock.NowMsec() - nStartedMsec < in_stConfig.nDurationMsec)
	{
		std::vector<Network::TransportEvent> arrEvents;
		eStatus = pTransport->Poll(arrEvents);
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		for (const Network::TransportEvent &stEvent : arrEvents)
		{
			if (stEvent.eType == Network::TransportEventType::Connected)
			{
				Network::ClientHello stHello;
				stHello.nClientNonce = in_stConfig.nSeed;
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
				eStatus = RuntimeStatus::IoError;
				break;
			}
			if (stEvent.eType != Network::TransportEventType::Packet)
			{
				continue;
			}
			Network::FrameHeader stHeader;
			eStatus = Network::DecodeHeader(stEvent.arrPayload.data(), stEvent.arrPayload.size(), stHeader);
			if (eStatus != RuntimeStatus::Ok || stHeader.nSessionId == 0)
			{
				eStatus = RuntimeStatus::InvalidParameter;
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
				nSessionId = stHeader.nSessionId;
				nEntityId = stWelcome.nEntityId;
				Gameplay::PredictionState stInitialState;
				stInitialState.vPosition = stWelcome.vPosition;
				stInitialState.vVelocity = stWelcome.vVelocity;
				stInitialState.nConfirmedSequence = stWelcome.nConfirmedInputSequence;
				stInitialState.nServerTimeMsec = stWelcome.nServerTick * stWelcome.nFixedStepMsec;
				if (!stPrediction.SetInitialState(stInitialState))
				{
					eStatus = RuntimeStatus::InvalidState;
					break;
				}
				nNextInputMsec = stClock.NowMsec();
				std::cout << "ENGINE_NEXT_CLIENT_WELCOME client_id=" << in_stConfig.strClientId
						  << " session_id=" << nSessionId << " entity_id=" << nEntityId << '\n'
						  << std::flush;
				(void)stHost.RecordTrace(0, "welcome", Runtime::EntityId{ nEntityId }, nSessionId);
				continue;
			}
			if (stHeader.eType != Network::MessageType::Snapshot || nSessionId == 0 || stHeader.nSessionId == 0)
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
				if (fPositionError > 0.001F)
				{
					std::cout << "ENGINE_NEXT_CLIENT_CORRECTION client_id=" << in_stConfig.strClientId
							  << " error=" << fPositionError << '\n';
				}
				continue;
			}
			Gameplay::InterpolationBuffer &stBuffer = mapRemoteBuffers[stSnapshot.nEntityId];
			const Gameplay::Status eBufferStatus = stBuffer.AddSample(stState);
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

		const std::uint64_t nNowMsec = stClock.NowMsec();
		if (bMove && nSessionId != 0 && nSentInputs < 24 && nNowMsec >= nNextInputMsec)
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
			++nSentInputs;
			nNextInputMsec = nNowMsec + 16;
		}

		if (bMove && nSentInputs == 24 && stPrediction.GetUnconfirmedInputCount() == 0 &&
			stPrediction.GetLastConfirmedSequence() == 24)
		{
			const Gameplay::PredictionState &stState = stPrediction.GetPredictedState();
			std::cout << "ENGINE_NEXT_CLIENT_PREDICTION client_id=" << in_stConfig.strClientId
					  << " confirmed=" << stPrediction.GetLastConfirmedSequence()
					  << " position_x=" << stState.vPosition.fX
					  << " history=" << stPrediction.GetUnconfirmedInputCount()
					  << " corrections=" << stPrediction.GetCorrectionCount() << '\n'
					  << std::flush;
			bComplete = true;
		}
		if (!bMove && nEntityId != 0 && !mapRemoteBuffers.empty())
		{
			for (const std::pair<const std::uint64_t, Gameplay::InterpolationBuffer> &stEntry : mapRemoteBuffers)
			{
				const std::uint64_t nEstimatedServerTime = nLatestServerTimeMsec +
						(nNowMsec - nLatestSnapshotLocalMsec);
				const std::uint64_t nTargetTime = nEstimatedServerTime > 100 ? nEstimatedServerTime - 100 : 0;
				const Gameplay::InterpolationResult stResult = stEntry.second.Sample(nTargetTime);
				if (stResult.stState.has_value() && stResult.stState->vPosition.fX > 0.0F &&
					(stResult.eStatus == Gameplay::InterpolationStatus::Interpolated ||
					 stResult.eStatus == Gameplay::InterpolationStatus::Held))
				{
					std::cout << "ENGINE_NEXT_CLIENT_REMOTE client_id=" << in_stConfig.strClientId
							  << " entity_id=" << stEntry.first
							  << " position_x=" << stResult.stState->vPosition.fX
							  << " status=" << GetInterpolationStatusName(stResult.eStatus)
							  << " samples=" << stEntry.second.GetSampleCount() << '\n'
							  << std::flush;
					bComplete = true;
					break;
				}
			}
		}
		if (bComplete)
		{
			Network::Disconnect stDisconnect;
			Network::FrameHeader stDisconnectHeader;
			stDisconnectHeader.eType = Network::MessageType::Disconnect;
			stDisconnectHeader.nMessageSequence = 2;
			stDisconnectHeader.nSessionId = nSessionId;
			std::vector<std::uint8_t> arrFrame;
			eStatus = Network::EncodeFrame(stDisconnectHeader, Network::EncodeDisconnect(stDisconnect), arrFrame);
			if (eStatus == RuntimeStatus::Ok)
			{
				eStatus = pTransport->Send(1, 0, true, arrFrame);
			}
			if (eStatus == RuntimeStatus::Ok)
			{
				eStatus = pTransport->Disconnect(1);
			}
			bComplete = eStatus == RuntimeStatus::Ok;
			break;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	pTransport->Stop();
	stHost.Shutdown();
	return bComplete ? RuntimeStatus::Ok : RuntimeStatus::IoError;
}

} // namespace EngineNext::Runtime
