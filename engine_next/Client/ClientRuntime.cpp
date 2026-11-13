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

#include "engine_next/include/EngineNext/Network/ITransport.h"
#include "engine_next/include/EngineNext/Network/Protocol.h"
#include "engine_next/include/EngineNext/Runtime/Clock.h"

#include <chrono>
#include <iostream>
#include <memory>
#include <thread>

namespace EngineNext::Runtime
{

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
			if (eStatus != RuntimeStatus::Ok || stHeader.eType != Network::MessageType::ServerWelcome || stHeader.nSessionId == 0)
			{
				eStatus = RuntimeStatus::InvalidParameter;
				break;
			}
			Network::ServerWelcome stWelcome;
			eStatus = Network::DecodeServerWelcome(stEvent.arrPayload.data() + Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stWelcome);
			if (eStatus != RuntimeStatus::Ok)
			{
				break;
			}
			std::cout << "ENGINE_NEXT_CLIENT_WELCOME client_id=" << in_stConfig.strClientId
					  << " session_id=" << stHeader.nSessionId << " entity_id=" << stWelcome.nEntityId << '\n' << std::flush;
			(void)stHost.RecordTrace(0, "welcome", Runtime::EntityId{ stWelcome.nEntityId }, stHeader.nSessionId);

			Network::Disconnect stDisconnect;
			stDisconnect.nAcknowledgeSequence = stHeader.nMessageSequence;
			Network::FrameHeader stDisconnectHeader;
			stDisconnectHeader.eType = Network::MessageType::Disconnect;
			stDisconnectHeader.nMessageSequence = 2;
			stDisconnectHeader.nSessionId = stHeader.nSessionId;
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
