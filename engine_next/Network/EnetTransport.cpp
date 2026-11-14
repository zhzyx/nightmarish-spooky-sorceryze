/**************************************************************************/
/*  EnetTransport.cpp                                                     */
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

#include "engine_next/include/EngineNext/Network/ITransport.h"

#include <enet/enet.h>

#include <map>
#include <new>
#include <utility>

namespace EngineNext::Network
{
namespace
{

int g_nEnetUsers = 0;

bool AcquireEnet() noexcept
{
	if (g_nEnetUsers == 0 && enet_initialize() != 0)
	{
		return false;
	}
	++g_nEnetUsers;
	return true;
}

void ReleaseEnet() noexcept
{
	if (g_nEnetUsers <= 0)
	{
		return;
	}
	--g_nEnetUsers;
	if (g_nEnetUsers == 0)
	{
		enet_deinitialize();
	}
}

class EnetTransport final : public ITransport
{
	ENetHost *pHost = nullptr;
	ENetPeer *pClientPeer = nullptr;
	std::map<PeerId, ENetPeer *> mapPeers;
	std::map<ENetPeer *, PeerId> mapPeerIds;
	PeerId nNextPeerId = 1;
	std::size_t nOutgoingPacketHighWater = 0;
	std::size_t nPollEventHighWater = 0;
	bool bServer = false;
	bool bRunning = false;

	[[nodiscard]] static std::size_t CountList(const ENetList &stList) noexcept
	{
		std::size_t nCount = 0;
		for (ENetListIterator stIterator = enet_list_begin(&stList); stIterator != enet_list_end(&stList); stIterator = enet_list_next(stIterator))
		{
			++nCount;
		}
		return nCount;
	}

	[[nodiscard]] std::size_t CountOutgoingPackets() const noexcept
	{
		std::size_t nCount = 0;
		for (const std::pair<const PeerId, ENetPeer *> &stEntry : mapPeers)
		{
			nCount += CountList(stEntry.second->outgoingCommands);
			nCount += CountList(stEntry.second->outgoingSendReliableCommands);
			nCount += CountList(stEntry.second->sentReliableCommands);
		}
		return nCount;
	}

	void UpdateOutgoingHighWater() noexcept
	{
		nOutgoingPacketHighWater = nOutgoingPacketHighWater < CountOutgoingPackets() ? CountOutgoingPackets() : nOutgoingPacketHighWater;
	}

	[[nodiscard]] PeerId RegisterPeer(ENetPeer *pPeer)
	{
		const std::map<ENetPeer *, PeerId>::const_iterator stExisting = mapPeerIds.find(pPeer);
		if (stExisting != mapPeerIds.end())
		{
			return stExisting->second;
		}
		const PeerId nPeerId = nNextPeerId++;
		mapPeerIds.emplace(pPeer, nPeerId);
		mapPeers.emplace(nPeerId, pPeer);
		return nPeerId;
	}

public:
	~EnetTransport() override
	{
		Stop();
	}

	Runtime::RuntimeStatus StartServer(const std::string &in_strBindAddress, std::uint16_t nPort, std::uint32_t nMaxClients) override
	{
		Stop();
		if (nMaxClients == 0 || !AcquireEnet())
		{
			return Runtime::RuntimeStatus::InvalidState;
		}
		ENetAddress stAddress;
		stAddress.host = ENET_HOST_ANY;
		stAddress.port = nPort;
		if (enet_address_set_host_ip(&stAddress, in_strBindAddress.c_str()) != 0)
		{
			ReleaseEnet();
			return Runtime::RuntimeStatus::InvalidParameter;
		}
		pHost = enet_host_create(&stAddress, nMaxClients, 2, 0, 0);
		if (pHost == nullptr)
		{
			ReleaseEnet();
			return Runtime::RuntimeStatus::IoError;
		}
		bServer = true;
		bRunning = true;
		return Runtime::RuntimeStatus::Ok;
	}

	Runtime::RuntimeStatus StartClient(const std::string &in_strAddress, std::uint16_t nPort) override
	{
		Stop();
		if (nPort == 0 || !AcquireEnet())
		{
			return Runtime::RuntimeStatus::InvalidState;
		}
		pHost = enet_host_create(nullptr, 1, 2, 0, 0);
		if (pHost == nullptr)
		{
			ReleaseEnet();
			return Runtime::RuntimeStatus::IoError;
		}
		ENetAddress stAddress;
		stAddress.host = ENET_HOST_ANY;
		stAddress.port = nPort;
		if (enet_address_set_host_ip(&stAddress, in_strAddress.c_str()) != 0)
		{
			Stop();
			return Runtime::RuntimeStatus::InvalidParameter;
		}
		pClientPeer = enet_host_connect(pHost, &stAddress, 2, 0);
		if (pClientPeer == nullptr)
		{
			Stop();
			return Runtime::RuntimeStatus::IoError;
		}
		bServer = false;
		bRunning = true;
		return Runtime::RuntimeStatus::Ok;
	}

	Runtime::RuntimeStatus Poll(std::vector<TransportEvent> &out_arrEvents) override
	{
		out_arrEvents.clear();
		if (!bRunning || pHost == nullptr)
		{
			return Runtime::RuntimeStatus::InvalidState;
		}
		ENetEvent stEvent;
		int nResult = 0;
		while ((nResult = enet_host_service(pHost, &stEvent, 0)) > 0)
		{
			TransportEvent stOutput;
			switch (stEvent.type)
			{
				case ENET_EVENT_TYPE_CONNECT:
					stOutput.eType = TransportEventType::Connected;
					stOutput.nPeerId = bServer ? RegisterPeer(stEvent.peer) : 1;
					if (!bServer)
					{
						mapPeers.emplace(1, stEvent.peer);
						mapPeerIds.emplace(stEvent.peer, 1);
					}
					break;
				case ENET_EVENT_TYPE_RECEIVE:
				{
					const std::map<ENetPeer *, PeerId>::const_iterator stPeer = mapPeerIds.find(stEvent.peer);
					stOutput.eType = TransportEventType::Packet;
					stOutput.nPeerId = stPeer == mapPeerIds.end() ? 0 : stPeer->second;
					stOutput.nChannelId = stEvent.channelID;
					if (stEvent.packet != nullptr)
					{
						stOutput.arrPayload.assign(
								stEvent.packet->data,
								stEvent.packet->data + stEvent.packet->dataLength);
						enet_packet_destroy(stEvent.packet);
					}
					break;
				}
				case ENET_EVENT_TYPE_DISCONNECT:
				{
					const std::map<ENetPeer *, PeerId>::iterator stPeer = mapPeerIds.find(stEvent.peer);
					stOutput.eType = TransportEventType::Disconnected;
					stOutput.nPeerId = stPeer == mapPeerIds.end() ? 0 : stPeer->second;
					if (stPeer != mapPeerIds.end())
					{
						mapPeers.erase(stPeer->second);
						mapPeerIds.erase(stPeer);
					}
					break;
				}
				case ENET_EVENT_TYPE_NONE:
					break;
			}
			out_arrEvents.push_back(std::move(stOutput));
		}
		UpdateOutgoingHighWater();
		nPollEventHighWater = nPollEventHighWater < out_arrEvents.size() ? out_arrEvents.size() : nPollEventHighWater;
		return nResult < 0 ? Runtime::RuntimeStatus::IoError : Runtime::RuntimeStatus::Ok;
	}

	Runtime::RuntimeStatus Send(PeerId in_nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &in_arrPayload) override
	{
		if (!bRunning || in_arrPayload.empty())
		{
			return Runtime::RuntimeStatus::InvalidState;
		}
		const std::map<PeerId, ENetPeer *>::const_iterator stPeer = mapPeers.find(in_nPeerId);
		if (stPeer == mapPeers.end())
		{
			return Runtime::RuntimeStatus::NotFound;
		}
		ENetPacket *pPacket = enet_packet_create(
				in_arrPayload.data(),
				in_arrPayload.size(),
				bReliable ? ENET_PACKET_FLAG_RELIABLE : 0);
		if (pPacket == nullptr)
		{
			return Runtime::RuntimeStatus::IoError;
		}
		if (enet_peer_send(stPeer->second, nChannelId, pPacket) != 0)
		{
			enet_packet_destroy(pPacket);
			return Runtime::RuntimeStatus::IoError;
		}
		UpdateOutgoingHighWater();
		return Runtime::RuntimeStatus::Ok;
	}

	Runtime::RuntimeStatus Disconnect(PeerId in_nPeerId) override
	{
		const std::map<PeerId, ENetPeer *>::const_iterator stPeer = mapPeers.find(in_nPeerId);
		if (stPeer == mapPeers.end())
		{
			return Runtime::RuntimeStatus::NotFound;
		}
		// Put already queued reliable rejects on the wire before ENet resets outgoing queues.
		enet_host_flush(pHost);
		enet_peer_disconnect(stPeer->second, 0);
		enet_host_flush(pHost);
		return Runtime::RuntimeStatus::Ok;
	}

	Runtime::RuntimeStatus DisconnectLater(PeerId in_nPeerId) override
	{
		const std::map<PeerId, ENetPeer *>::const_iterator stPeer = mapPeers.find(in_nPeerId);
		if (!bRunning || pHost == nullptr || stPeer == mapPeers.end())
		{
			return Runtime::RuntimeStatus::NotFound;
		}
		enet_peer_disconnect_later(stPeer->second, 0);
		enet_host_flush(pHost);
		return Runtime::RuntimeStatus::Ok;
	}

	TransportStats GetStats() const noexcept override
	{
		return TransportStats{ CountOutgoingPackets(), nOutgoingPacketHighWater, nPollEventHighWater };
	}

	std::uint16_t GetBoundPort() const noexcept override
	{
		return pHost == nullptr ? 0 : pHost->address.port;
	}

	bool IsRunning() const noexcept override
	{
		return bRunning;
	}

	void Stop() noexcept override
	{
		mapPeers.clear();
		mapPeerIds.clear();
		pClientPeer = nullptr;
		nNextPeerId = 1;
		if (pHost != nullptr)
		{
			enet_host_destroy(pHost);
			pHost = nullptr;
		}
		if (bRunning)
		{
			ReleaseEnet();
		}
		bRunning = false;
		bServer = false;
	}
};

} // namespace

ITransport *CreateEnetTransport() noexcept
{
	return new (std::nothrow) EnetTransport();
}

} // namespace EngineNext::Network
