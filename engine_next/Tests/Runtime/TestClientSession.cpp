/**************************************************************************/
/*  TestClientSession.cpp                                                */
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

#include "engine_next/Tests/TestFramework.h"

#include "engine_next/Client/ClientSession.h"
#include "engine_next/include/EngineNext/Network/Protocol.h"

#include <limits>
#include <memory>
#include <utility>
#include <vector>

namespace
{

using EngineNext::Runtime::RuntimeStatus;

class SessionTransport final : public EngineNext::Network::ITransport
{
public:
	bool bRunning = false;
	std::uint32_t nStarts = 0;
	std::vector<EngineNext::Network::TransportEvent> arrEvents;
	std::vector<std::vector<std::uint8_t>> arrSent;
	RuntimeStatus StartServer(const std::string &, std::uint16_t, std::uint32_t) override
	{
		return RuntimeStatus::InvalidState;
	}
	RuntimeStatus StartClient(const std::string &, std::uint16_t) override
	{
		bRunning = true;
		++nStarts;
		return RuntimeStatus::Ok;
	}
	RuntimeStatus Poll(std::vector<EngineNext::Network::TransportEvent> &out_arrEvents) override
	{
		out_arrEvents = std::move(arrEvents);
		arrEvents.clear();
		return RuntimeStatus::Ok;
	}
	RuntimeStatus Send(EngineNext::Network::PeerId, std::uint8_t, bool, const std::vector<std::uint8_t> &arrPayload) override
	{
		arrSent.push_back(arrPayload);
		return RuntimeStatus::Ok;
	}
	RuntimeStatus Disconnect(EngineNext::Network::PeerId) override
	{
		return RuntimeStatus::Ok;
	}
	RuntimeStatus DisconnectLater(EngineNext::Network::PeerId) override
	{
		arrEvents.push_back({ EngineNext::Network::TransportEventType::Disconnected, 1, 0, {} });
		return RuntimeStatus::Ok;
	}
	std::uint16_t GetBoundPort() const noexcept override
	{
		return 1234;
	}
	bool IsRunning() const noexcept override
	{
		return bRunning;
	}
	EngineNext::Network::TransportStats GetStats() const noexcept override
	{
		return {};
	}
	void Stop() noexcept override
	{
		bRunning = false;
		arrEvents.clear();
	}
	void Packet(EngineNext::Network::MessageType eType, const std::vector<std::uint8_t> &arrPayload)
	{
		EngineNext::Network::FrameHeader stHeader;
		stHeader.eType = eType;
		stHeader.nSessionId = 7;
		std::vector<std::uint8_t> arrFrame;
		ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, arrPayload, arrFrame), RuntimeStatus::Ok);
		arrEvents.push_back({ EngineNext::Network::TransportEventType::Packet, 1, 0, std::move(arrFrame) });
	}
	void Welcome(std::uint8_t nToken = 1, std::uint64_t nConfirmed = 0)
	{
		EngineNext::Network::ServerWelcome stWelcome;
		stWelcome.nEntityId = 11;
		stWelcome.nFixedStepMsec = 16;
		stWelcome.nConfirmedInputSequence = nConfirmed;
		stWelcome.arrResumeToken.fill(nToken);
		Packet(EngineNext::Network::MessageType::ServerWelcome, EngineNext::Network::EncodeServerWelcome(stWelcome));
	}
};

EngineNext::Runtime::RuntimeConfig Config()
{
	EngineNext::Runtime::RuntimeConfig stConfig;
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Client;
	stConfig.bNetworkMode = true;
	stConfig.nPort = 1234;
	return stConfig;
}

} // namespace

ENGINE_NEXT_TEST("ClientSession steps interactive prediction on caller time and preserves snapshot ownership")
{
	EngineNext::Runtime::ClientSession stSession;
	std::unique_ptr<SessionTransport> pFake = std::make_unique<SessionTransport>();
	SessionTransport *pTransport = pFake.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pFake)), RuntimeStatus::Ok);
	pTransport->Welcome();
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, { 1.0F, 0.0F, 0.0F }), RuntimeStatus::Ok);
	const EngineNext::Runtime::ClientSnapshot stFirst = stSession.GetSnapshot();
	ENGINE_NEXT_CHECK(stSession.IsConnected());
	ENGINE_NEXT_CHECK(stSession.GetPackageDigest().empty());
	ENGINE_NEXT_CHECK_EQ(stFirst.arrEntities.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stFirst.arrEntities[0].stEntityId.nValue, 11ULL);
	ENGINE_NEXT_CHECK_FLOAT(stFirst.arrEntities[0].stState.vPosition.fX, 0.128F);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(115, { 1.0F, 0.0F, 0.0F }), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX, 0.128F);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(116, { 1.0F, 0.0F, 0.0F }), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX, 0.256F);
	ENGINE_NEXT_CHECK_FLOAT(stFirst.arrEntities[0].stState.vPosition.fX, 0.128F);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(110, {}), RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK(stSession.IsConnected());
	stSession.Shutdown();
	ENGINE_NEXT_CHECK(!stSession.IsConnected());
	ENGINE_NEXT_CHECK(stSession.GetSnapshot().arrEntities.empty());
	ENGINE_NEXT_CHECK(stSession.GetPackageDigest().empty());
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(117, {}), RuntimeStatus::InvalidState);
}

ENGINE_NEXT_TEST("ClientSession reconnect retains identity and rotates resume token")
{
	EngineNext::Runtime::ClientSession stSession;
	std::unique_ptr<SessionTransport> pFake = std::make_unique<SessionTransport>();
	SessionTransport *pTransport = pFake.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pFake)), RuntimeStatus::Ok);
	pTransport->Welcome();
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stSession.RequestReconnect(25), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(!stSession.IsConnected());
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(124, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(pTransport->nStarts, 1U);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(125, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(pTransport->nStarts, 2U);
	pTransport->arrEvents.push_back({ EngineNext::Network::TransportEventType::Connected, 1, 0, {} });
	pTransport->Welcome(2, 1);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(126, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stSession.IsConnected());
	ENGINE_NEXT_CHECK_EQ(stSession.GetSnapshot().nSessionId, 7ULL);
	ENGINE_NEXT_CHECK_EQ(stSession.GetSnapshot().nGeneration, 2ULL);
}

ENGINE_NEXT_TEST("ClientSession rejects invalid input and limits a single catch-up call")
{
	EngineNext::Runtime::ClientSession stSession;
	std::unique_ptr<SessionTransport> pFake = std::make_unique<SessionTransport>();
	SessionTransport *pTransport = pFake.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pFake)), RuntimeStatus::Ok);
	pTransport->Welcome();
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, { std::numeric_limits<float>::quiet_NaN(), 0.0F, 0.0F }), RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100000, { 1.0F, 0.0F, 0.0F }), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX < 1.1F);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(std::numeric_limits<std::uint64_t>::max(), {}), RuntimeStatus::InvalidParameter);
}

ENGINE_NEXT_TEST("ClientSession interpolates remote state without writing prediction")
{
	EngineNext::Runtime::ClientSession stSession;
	std::unique_ptr<SessionTransport> pFake = std::make_unique<SessionTransport>();
	SessionTransport *pTransport = pFake.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pFake)), RuntimeStatus::Ok);
	pTransport->Welcome();
	EngineNext::Network::Snapshot stRemote;
	stRemote.nEntityId = 22;
	stRemote.nServerTick = 10;
	stRemote.vPosition.fX = 4.0F;
	pTransport->Packet(EngineNext::Network::MessageType::Snapshot, EngineNext::Network::EncodeSnapshot(stRemote));
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, {}), RuntimeStatus::Ok);
	const EngineNext::Runtime::ClientSnapshot stSnapshot = stSession.GetSnapshot();
	ENGINE_NEXT_CHECK_EQ(stSnapshot.arrEntities.size(), 2U);
	ENGINE_NEXT_CHECK_FLOAT(stSnapshot.arrEntities[0].stState.vPosition.fX, 0.0F);
	ENGINE_NEXT_CHECK_FLOAT(stSnapshot.arrEntities[1].stState.vPosition.fX, 4.0F);
	ENGINE_NEXT_CHECK(!stSnapshot.arrEntities[1].bLocal);
}

ENGINE_NEXT_TEST("ClientSession refuses duplicate welcome and overflowing server time")
{
	EngineNext::Runtime::ClientSession stSession;
	std::unique_ptr<SessionTransport> pFake = std::make_unique<SessionTransport>();
	SessionTransport *pTransport = pFake.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pFake)), RuntimeStatus::Ok);
	pTransport->Welcome();
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, {}), RuntimeStatus::Ok);
	pTransport->Welcome();
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(116, {}), RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK(!stSession.IsConnected());
	stSession.Shutdown();
	std::unique_ptr<SessionTransport> pSecond = std::make_unique<SessionTransport>();
	pTransport = pSecond.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pSecond)), RuntimeStatus::Ok);
	pTransport->Welcome();
	EngineNext::Network::Snapshot stRemote;
	stRemote.nEntityId = 22;
	stRemote.nServerTick = std::numeric_limits<std::uint64_t>::max();
	pTransport->Packet(EngineNext::Network::MessageType::Snapshot, EngineNext::Network::EncodeSnapshot(stRemote));
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, {}), RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK(!stSession.IsConnected());
}

ENGINE_NEXT_TEST("ClientSession bounds missing acknowledgments and remote entity storage")
{
	EngineNext::Runtime::ClientSession stSession;
	std::unique_ptr<SessionTransport> pFake = std::make_unique<SessionTransport>();
	SessionTransport *pTransport = pFake.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pFake)), RuntimeStatus::Ok);
	pTransport->Welcome();
	for (std::uint64_t nIndex = 0; nIndex < 256; ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stSession.Tick(nIndex * 16, {}), RuntimeStatus::Ok);
	}
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(256 * 16, {}), RuntimeStatus::InvalidState);
	ENGINE_NEXT_CHECK(!stSession.IsConnected());
	stSession.Shutdown();
	std::unique_ptr<SessionTransport> pSecond = std::make_unique<SessionTransport>();
	pTransport = pSecond.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pSecond)), RuntimeStatus::Ok);
	pTransport->Welcome();
	for (std::uint64_t nIndex = 0; nIndex < 256; ++nIndex)
	{
		EngineNext::Network::Snapshot stRemote;
		stRemote.nEntityId = 100 + nIndex;
		stRemote.nServerTick = 1;
		pTransport->Packet(EngineNext::Network::MessageType::Snapshot, EngineNext::Network::EncodeSnapshot(stRemote));
	}
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(0, {}), RuntimeStatus::InvalidState);
	ENGINE_NEXT_CHECK(stSession.GetSnapshot().arrEntities.size() <= 256);
}

ENGINE_NEXT_TEST("ClientSession retains a short movement pulse for exactly one fixed step")
{
	EngineNext::Runtime::ClientSession stSession;
	ENGINE_NEXT_CHECK_EQ(stSession.QueueMovementPulse({ 1.0F, 0.0F, 0.0F }), RuntimeStatus::InvalidState);
	std::unique_ptr<SessionTransport> pFake = std::make_unique<SessionTransport>();
	SessionTransport *pTransport = pFake.get();
	ENGINE_NEXT_CHECK_EQ(stSession.Initialize(Config(), std::move(pFake)), RuntimeStatus::Ok);
	pTransport->Welcome();
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(100, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stSession.QueueMovementPulse({ 1.0F, 0.0F, 0.0F }), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(101, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX, 0.0F);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(116, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX, 0.128F);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(132, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX, 0.128F);
	ENGINE_NEXT_CHECK_EQ(stSession.QueueMovementPulse({}), RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(stSession.QueueMovementPulse({ 2.0F, 0.0F, 0.0F }), RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(stSession.QueueMovementPulse({ -1.0F, 0.0F, 0.0F }), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(148, { 1.0F, 0.0F, 0.0F }), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX, 0.256F);
	ENGINE_NEXT_CHECK_EQ(stSession.Tick(164, {}), RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stSession.GetSnapshot().arrEntities[0].stState.vPosition.fX, 0.256F);
}
