/**************************************************************************/
/*  ImpairmentTransport.h                                                 */
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

#pragma once

#include "engine_next/include/EngineNext/Network/ITransport.h"

#include <deque>
#include <memory>

namespace EngineNext::Network
{

struct ImpairmentConfig
{
	std::uint64_t nSeed = 1;
	std::uint64_t nDelayMsec = 0;
	std::uint64_t nJitterMsec = 0;
	std::uint32_t nLossPermille = 0;
	std::size_t nQueueCapacity = 64;
	bool bDropFirstInput = false;
};

// Delays and drops real outgoing transport packets. It never changes gameplay state.
class ImpairmentTransport final : public ITransport
{
	struct PendingPacket
	{
		PeerId nPeerId = 0;
		std::uint8_t nChannelId = 0;
		bool bReliable = false;
		std::uint64_t nDeliveryMsec = 0;
		std::vector<std::uint8_t> arrPayload;
	};

	std::unique_ptr<ITransport> pUpstream;
	ImpairmentConfig stConfig;
	std::uint64_t nRandomState = 1;
	std::deque<PendingPacket> arrPending;
	std::size_t nQueueHighWater = 0;
	std::uint64_t nDroppedForLoss = 0;
	std::uint64_t nDroppedForOverflow = 0;
	std::uint64_t nDroppedFirstInput = 0;
	bool bFirstInputDropped = false;

	[[nodiscard]] std::uint64_t NextRandom() noexcept;
	[[nodiscard]] Runtime::RuntimeStatus SendAt(PeerId nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &arrPayload, std::uint64_t nNowMsec, bool bValidateConfig);

public:
	ImpairmentTransport(std::unique_ptr<ITransport> in_pUpstream, const ImpairmentConfig &in_stConfig) noexcept;
	[[nodiscard]] bool IsConfigurationValid() const noexcept;
	[[nodiscard]] Runtime::RuntimeStatus StartServer(const std::string &in_strBindAddress, std::uint16_t nPort, std::uint32_t nMaxClients) override;
	[[nodiscard]] Runtime::RuntimeStatus StartClient(const std::string &in_strAddress, std::uint16_t nPort) override;
	[[nodiscard]] Runtime::RuntimeStatus Poll(std::vector<TransportEvent> &out_arrEvents) override;
	[[nodiscard]] Runtime::RuntimeStatus Send(PeerId in_nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &in_arrPayload) override;
	[[nodiscard]] Runtime::RuntimeStatus Disconnect(PeerId in_nPeerId) override;
	[[nodiscard]] Runtime::RuntimeStatus DisconnectLater(PeerId in_nPeerId) override;
	[[nodiscard]] std::uint16_t GetBoundPort() const noexcept override;
	[[nodiscard]] bool IsRunning() const noexcept override;
	void Stop() noexcept override;

	// Explicit time entry points make queue behavior deterministic in native tests.
	[[nodiscard]] Runtime::RuntimeStatus SendAt(PeerId in_nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &in_arrPayload, std::uint64_t nNowMsec);
	[[nodiscard]] Runtime::RuntimeStatus PollAt(std::vector<TransportEvent> &out_arrEvents, std::uint64_t nNowMsec);
	[[nodiscard]] std::size_t GetQueueHighWater() const noexcept;
	[[nodiscard]] std::uint64_t GetDroppedForLoss() const noexcept;
	[[nodiscard]] std::uint64_t GetDroppedForOverflow() const noexcept;
	[[nodiscard]] std::uint64_t GetDroppedFirstInput() const noexcept;
};

} // namespace EngineNext::Network
