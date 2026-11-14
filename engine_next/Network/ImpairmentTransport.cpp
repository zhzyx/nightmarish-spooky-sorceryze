/**************************************************************************/
/*  ImpairmentTransport.cpp                                               */
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

#include "engine_next/include/EngineNext/Network/ImpairmentTransport.h"

#include "engine_next/include/EngineNext/Network/Protocol.h"
#include "engine_next/include/EngineNext/Runtime/Clock.h"

namespace EngineNext::Network
{

ImpairmentTransport::ImpairmentTransport(std::unique_ptr<ITransport> in_pUpstream, const ImpairmentConfig &in_stConfig) noexcept :
		pUpstream(std::move(in_pUpstream)), stConfig(in_stConfig), nRandomState(in_stConfig.nSeed == 0 ? 1 : in_stConfig.nSeed)
{
}

bool ImpairmentTransport::IsConfigurationValid() const noexcept
{
	return pUpstream != nullptr && stConfig.nSeed != 0 && stConfig.nDelayMsec <= 60000 &&
			stConfig.nJitterMsec <= 60000 && stConfig.nLossPermille <= 1000 &&
			stConfig.nQueueCapacity > 0 && stConfig.nQueueCapacity <= 4096;
}

std::uint64_t ImpairmentTransport::NextRandom() noexcept
{
	nRandomState ^= nRandomState << 13U;
	nRandomState ^= nRandomState >> 7U;
	nRandomState ^= nRandomState << 17U;
	return nRandomState;
}

Runtime::RuntimeStatus ImpairmentTransport::StartServer(const std::string &in_strBindAddress, std::uint16_t nPort, std::uint32_t nMaxClients)
{
	return IsConfigurationValid() ? pUpstream->StartServer(in_strBindAddress, nPort, nMaxClients) : Runtime::RuntimeStatus::InvalidParameter;
}

Runtime::RuntimeStatus ImpairmentTransport::StartClient(const std::string &in_strAddress, std::uint16_t nPort)
{
	return IsConfigurationValid() ? pUpstream->StartClient(in_strAddress, nPort) : Runtime::RuntimeStatus::InvalidParameter;
}

Runtime::RuntimeStatus ImpairmentTransport::Poll(std::vector<TransportEvent> &out_arrEvents)
{
	const Runtime::SystemClock stClock;
	return PollAt(out_arrEvents, stClock.NowMsec());
}

Runtime::RuntimeStatus ImpairmentTransport::PollAt(std::vector<TransportEvent> &out_arrEvents, std::uint64_t nNowMsec)
{
	if (!IsConfigurationValid())
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	const Runtime::RuntimeStatus eStatus = pUpstream->Poll(out_arrEvents);
	if (eStatus != Runtime::RuntimeStatus::Ok)
	{
		return eStatus;
	}
	for (std::deque<PendingPacket>::iterator stIterator = arrPending.begin(); stIterator != arrPending.end();)
	{
		if (stIterator->nDeliveryMsec > nNowMsec)
		{
			++stIterator;
			continue;
		}
		const Runtime::RuntimeStatus eSendStatus = pUpstream->Send(stIterator->nPeerId, stIterator->nChannelId, stIterator->bReliable, stIterator->arrPayload);
		if (eSendStatus != Runtime::RuntimeStatus::Ok)
		{
			return eSendStatus;
		}
		stIterator = arrPending.erase(stIterator);
	}
	UpdateCombinedHighWater();
	return Runtime::RuntimeStatus::Ok;
}

Runtime::RuntimeStatus ImpairmentTransport::Send(PeerId in_nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &in_arrPayload)
{
	const Runtime::SystemClock stClock;
	return SendAt(in_nPeerId, nChannelId, bReliable, in_arrPayload, stClock.NowMsec(), true);
}

Runtime::RuntimeStatus ImpairmentTransport::SendAt(PeerId in_nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &in_arrPayload, std::uint64_t nNowMsec)
{
	return SendAt(in_nPeerId, nChannelId, bReliable, in_arrPayload, nNowMsec, true);
}

Runtime::RuntimeStatus ImpairmentTransport::SendAt(PeerId nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &arrPayload, std::uint64_t nNowMsec, bool bValidateConfig)
{
	if ((bValidateConfig && !IsConfigurationValid()) || pUpstream == nullptr)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	FrameHeader stHeader;
	const bool bInput = DecodeHeader(arrPayload.data(), arrPayload.size(), stHeader) == Runtime::RuntimeStatus::Ok &&
			stHeader.eType == MessageType::Input;
	if (stConfig.bDropFirstInput && bInput && !bFirstInputDropped)
	{
		bFirstInputDropped = true;
		++nDroppedFirstInput;
		return Runtime::RuntimeStatus::Ok;
	}
	if (stConfig.nLossPermille != 0 && NextRandom() % 1000U < stConfig.nLossPermille)
	{
		++nDroppedForLoss;
		return Runtime::RuntimeStatus::Ok;
	}
	if (stConfig.nDelayMsec == 0 && stConfig.nJitterMsec == 0)
	{
		const Runtime::RuntimeStatus eStatus = pUpstream->Send(nPeerId, nChannelId, bReliable, arrPayload);
		UpdateCombinedHighWater();
		return eStatus;
	}
	if (nNowMsec > static_cast<std::uint64_t>(-1) - stConfig.nDelayMsec - stConfig.nJitterMsec)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	std::uint64_t nDeliveryMsec = nNowMsec + stConfig.nDelayMsec;
	if (stConfig.nJitterMsec != 0)
	{
		const std::uint64_t nJitterRange = stConfig.nJitterMsec * 2 + 1;
		const std::int64_t nJitter = static_cast<std::int64_t>(NextRandom() % nJitterRange) - static_cast<std::int64_t>(stConfig.nJitterMsec);
		if (nJitter < 0)
		{
			const std::uint64_t nMagnitude = static_cast<std::uint64_t>(-nJitter);
			nDeliveryMsec = nMagnitude > nDeliveryMsec ? 0 : nDeliveryMsec - nMagnitude;
		}
		else
		{
			nDeliveryMsec += static_cast<std::uint64_t>(nJitter);
		}
	}
	if (arrPending.size() >= stConfig.nQueueCapacity)
	{
		arrPending.pop_front();
		++nDroppedForOverflow;
	}
	arrPending.push_back(PendingPacket{ nPeerId, nChannelId, bReliable, nDeliveryMsec, arrPayload });
	nQueueHighWater = nQueueHighWater < arrPending.size() ? arrPending.size() : nQueueHighWater;
	UpdateCombinedHighWater();
	return Runtime::RuntimeStatus::Ok;
}

Runtime::RuntimeStatus ImpairmentTransport::Disconnect(PeerId in_nPeerId)
{
	return IsConfigurationValid() ? pUpstream->Disconnect(in_nPeerId) : Runtime::RuntimeStatus::InvalidParameter;
}

Runtime::RuntimeStatus ImpairmentTransport::DisconnectLater(PeerId in_nPeerId)
{
	return IsConfigurationValid() ? pUpstream->DisconnectLater(in_nPeerId) : Runtime::RuntimeStatus::InvalidParameter;
}

std::uint16_t ImpairmentTransport::GetBoundPort() const noexcept
{
	return pUpstream == nullptr ? 0 : pUpstream->GetBoundPort();
}

bool ImpairmentTransport::IsRunning() const noexcept
{
	return pUpstream != nullptr && pUpstream->IsRunning();
}

void ImpairmentTransport::Stop() noexcept
{
	arrPending.clear();
	if (pUpstream != nullptr)
	{
		pUpstream->Stop();
	}
}

void ImpairmentTransport::UpdateCombinedHighWater() noexcept
{
	if (pUpstream == nullptr)
	{
		return;
	}
	const std::size_t nCurrent = pUpstream->GetStats().nOutgoingPackets + arrPending.size();
	nCombinedHighWater = nCombinedHighWater < nCurrent ? nCurrent : nCombinedHighWater;
}

TransportStats ImpairmentTransport::GetStats() const noexcept
{
	TransportStats stStats = pUpstream == nullptr ? TransportStats{} : pUpstream->GetStats();
	stStats.nOutgoingPackets += arrPending.size();
	stStats.nOutgoingPacketHighWater = stStats.nOutgoingPacketHighWater < nCombinedHighWater ? nCombinedHighWater : stStats.nOutgoingPacketHighWater;
	return stStats;
}

std::size_t ImpairmentTransport::GetQueueHighWater() const noexcept
{
	return nQueueHighWater;
}

std::uint64_t ImpairmentTransport::GetDroppedForLoss() const noexcept
{
	return nDroppedForLoss;
}

std::uint64_t ImpairmentTransport::GetDroppedForOverflow() const noexcept
{
	return nDroppedForOverflow;
}

std::uint64_t ImpairmentTransport::GetDroppedFirstInput() const noexcept
{
	return nDroppedFirstInput;
}

} // namespace EngineNext::Network
