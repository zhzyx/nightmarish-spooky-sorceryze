/**************************************************************************/
/*  ITransport.h                                                          */
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

#include "engine_next/include/EngineNext/Runtime/Types.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Network
{

using PeerId = std::uint32_t;

enum class TransportEventType : std::uint8_t
{
	Connected = 1,
	Disconnected = 2,
	Packet = 3,
};

struct TransportEvent
{
	TransportEventType eType = TransportEventType::Connected;
	PeerId nPeerId = 0;
	std::uint8_t nChannelId = 0;
	std::vector<std::uint8_t> arrPayload;
};

class ITransport
{
public:
	virtual ~ITransport() = default;
	[[nodiscard]] virtual Runtime::RuntimeStatus StartServer(const std::string &in_strBindAddress, std::uint16_t nPort, std::uint32_t nMaxClients) = 0;
	[[nodiscard]] virtual Runtime::RuntimeStatus StartClient(const std::string &in_strAddress, std::uint16_t nPort) = 0;
	[[nodiscard]] virtual Runtime::RuntimeStatus Poll(std::vector<TransportEvent> &out_arrEvents) = 0;
	[[nodiscard]] virtual Runtime::RuntimeStatus Send(PeerId in_nPeerId, std::uint8_t nChannelId, bool bReliable, const std::vector<std::uint8_t> &in_arrPayload) = 0;
	[[nodiscard]] virtual Runtime::RuntimeStatus Disconnect(PeerId in_nPeerId) = 0;
	[[nodiscard]] virtual Runtime::RuntimeStatus DisconnectLater(PeerId in_nPeerId) = 0;
	[[nodiscard]] virtual std::uint16_t GetBoundPort() const noexcept = 0;
	[[nodiscard]] virtual bool IsRunning() const noexcept = 0;
	virtual void Stop() noexcept = 0;
};

[[nodiscard]] ITransport *CreateEnetTransport() noexcept;

} // namespace EngineNext::Network
