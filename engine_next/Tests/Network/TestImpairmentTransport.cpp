/**************************************************************************/
/*  TestImpairmentTransport.cpp                                           */
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

#include "engine_next/include/EngineNext/Network/ImpairmentTransport.h"
#include "engine_next/include/EngineNext/Network/Protocol.h"

#include <memory>
#include <utility>
#include <vector>

namespace
{

class FakeTransport final : public EngineNext::Network::ITransport
{
public:
	bool bRunning = true;
	std::vector<std::vector<std::uint8_t>> arrSent;

	EngineNext::Runtime::RuntimeStatus StartServer(const std::string &, std::uint16_t, std::uint32_t) override
	{
		bRunning = true;
		return EngineNext::Runtime::RuntimeStatus::Ok;
	}
	EngineNext::Runtime::RuntimeStatus StartClient(const std::string &, std::uint16_t) override
	{
		bRunning = true;
		return EngineNext::Runtime::RuntimeStatus::Ok;
	}
	EngineNext::Runtime::RuntimeStatus Poll(std::vector<EngineNext::Network::TransportEvent> &out_arrEvents) override
	{
		out_arrEvents.clear();
		return EngineNext::Runtime::RuntimeStatus::Ok;
	}
	EngineNext::Runtime::RuntimeStatus Send(EngineNext::Network::PeerId, std::uint8_t, bool, const std::vector<std::uint8_t> &arrPayload) override
	{
		arrSent.push_back(arrPayload);
		return EngineNext::Runtime::RuntimeStatus::Ok;
	}
	EngineNext::Runtime::RuntimeStatus Disconnect(EngineNext::Network::PeerId) override
	{
		return EngineNext::Runtime::RuntimeStatus::Ok;
	}
	EngineNext::Runtime::RuntimeStatus DisconnectLater(EngineNext::Network::PeerId) override
	{
		return EngineNext::Runtime::RuntimeStatus::Ok;
	}
	std::uint16_t GetBoundPort() const noexcept override
	{
		return 0;
	}
	bool IsRunning() const noexcept override
	{
		return bRunning;
	}
	void Stop() noexcept override
	{
		bRunning = false;
	}
};

std::vector<std::uint8_t> MakeFrame(EngineNext::Network::MessageType eType)
{
	EngineNext::Network::FrameHeader stHeader;
	stHeader.eType = eType;
	stHeader.nSessionId = 1;
	std::vector<std::uint8_t> arrFrame;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, {}, arrFrame), EngineNext::Runtime::RuntimeStatus::Ok);
	return arrFrame;
}

} // namespace

ENGINE_NEXT_TEST("Impairment transport delays forwards and bounds its outgoing queue")
{
	FakeTransport *pFake = new FakeTransport();
	EngineNext::Network::ImpairmentConfig stConfig;
	stConfig.nSeed = 41;
	stConfig.nDelayMsec = 20;
	stConfig.nQueueCapacity = 2;
	EngineNext::Network::ImpairmentTransport stTransport(std::unique_ptr<EngineNext::Network::ITransport>(pFake), stConfig);
	std::vector<EngineNext::Network::TransportEvent> arrEvents;
	ENGINE_NEXT_CHECK_EQ(stTransport.SendAt(1, 1, false, MakeFrame(EngineNext::Network::MessageType::Input), 100), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stTransport.SendAt(1, 1, false, MakeFrame(EngineNext::Network::MessageType::Snapshot), 100), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stTransport.SendAt(1, 1, false, MakeFrame(EngineNext::Network::MessageType::Disconnect), 100), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stTransport.GetQueueHighWater(), 2U);
	ENGINE_NEXT_CHECK_EQ(stTransport.GetDroppedForOverflow(), 1ULL);
	ENGINE_NEXT_CHECK_EQ(stTransport.PollAt(arrEvents, 119), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(pFake->arrSent.size(), 0U);
	ENGINE_NEXT_CHECK_EQ(stTransport.PollAt(arrEvents, 120), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(pFake->arrSent.size(), 2U);
	EngineNext::Network::FrameHeader stHeader;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeHeader(pFake->arrSent[0].data(), pFake->arrSent[0].size(), stHeader), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stHeader.eType == EngineNext::Network::MessageType::Snapshot);
}

ENGINE_NEXT_TEST("Impairment transport drops exactly one real input and supports seeded loss")
{
	FakeTransport *pFake = new FakeTransport();
	EngineNext::Network::ImpairmentConfig stConfig;
	stConfig.nSeed = 41;
	stConfig.bDropFirstInput = true;
	EngineNext::Network::ImpairmentTransport stTransport(std::unique_ptr<EngineNext::Network::ITransport>(pFake), stConfig);
	ENGINE_NEXT_CHECK_EQ(stTransport.SendAt(1, 1, false, MakeFrame(EngineNext::Network::MessageType::Input), 100), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stTransport.SendAt(1, 1, false, MakeFrame(EngineNext::Network::MessageType::Input), 100), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stTransport.GetDroppedFirstInput(), 1ULL);
	ENGINE_NEXT_CHECK_EQ(pFake->arrSent.size(), 1U);
	stConfig.bDropFirstInput = false;
	stConfig.nLossPermille = 1000;
	FakeTransport *pLossFake = new FakeTransport();
	EngineNext::Network::ImpairmentTransport stLossTransport(std::unique_ptr<EngineNext::Network::ITransport>(pLossFake), stConfig);
	ENGINE_NEXT_CHECK_EQ(stLossTransport.SendAt(1, 1, false, MakeFrame(EngineNext::Network::MessageType::Input), 100), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stLossTransport.GetDroppedForLoss(), 1ULL);
	ENGINE_NEXT_CHECK_EQ(pLossFake->arrSent.size(), 0U);
}

ENGINE_NEXT_TEST("Impairment transport validates configuration and releases its upstream")
{
	EngineNext::Network::ImpairmentConfig stConfig;
	stConfig.nQueueCapacity = 0;
	EngineNext::Network::ImpairmentTransport stInvalid(std::make_unique<FakeTransport>(), stConfig);
	ENGINE_NEXT_CHECK(!stInvalid.IsConfigurationValid());
	ENGINE_NEXT_CHECK_EQ(stInvalid.SendAt(1, 0, true, MakeFrame(EngineNext::Network::MessageType::ClientHello), 0), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	stConfig.nQueueCapacity = 1;
	stConfig.nDelayMsec = 10;
	stConfig.nJitterMsec = 5;
	EngineNext::Network::ImpairmentTransport stTransport(std::make_unique<FakeTransport>(), stConfig);
	ENGINE_NEXT_CHECK(stTransport.IsConfigurationValid());
	ENGINE_NEXT_CHECK_EQ(stTransport.SendAt(1, 1, false, MakeFrame(EngineNext::Network::MessageType::Input), 100), EngineNext::Runtime::RuntimeStatus::Ok);
	std::vector<EngineNext::Network::TransportEvent> arrEvents;
	ENGINE_NEXT_CHECK_EQ(stTransport.PollAt(arrEvents, 120), EngineNext::Runtime::RuntimeStatus::Ok);
	stTransport.Stop();
	ENGINE_NEXT_CHECK(!stTransport.IsRunning());
}
