/**************************************************************************/
/*  Protocol.h                                                            */
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

#include "engine_next/include/EngineNext/Gameplay/Vector3.h"
#include "engine_next/include/EngineNext/Runtime/Types.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace EngineNext::Network
{

inline constexpr std::uint16_t PROTOCOL_VERSION = 1;
inline constexpr std::size_t FRAME_HEADER_BYTES = 32;
inline constexpr std::size_t MAX_PACKET_BYTES = 1200;
using ReconnectToken = std::array<std::uint8_t, 16>;

enum class MessageType : std::uint16_t
{
	ClientHello = 1,
	ServerWelcome = 2,
	Input = 3,
	Snapshot = 4,
	Disconnect = 5,
	ErrorReject = 6,
};

struct FrameHeader
{
	MessageType eType = MessageType::ClientHello;
	std::uint16_t nFlags = 0;
	std::uint32_t nPayloadBytes = 0;
	std::uint64_t nMessageSequence = 1;
	std::uint64_t nSessionId = 0;
};

struct ClientHello
{
	std::uint64_t nClientNonce = 0;
	std::uint64_t nResumeSessionId = 0;
	ReconnectToken arrResumeToken{};
};

struct ServerWelcome
{
	std::uint64_t nEntityId = 0;
	ReconnectToken arrResumeToken{};
	std::uint64_t nServerTick = 0;
	std::uint32_t nFixedStepMsec = 16;
	std::uint32_t nSnapshotIntervalTicks = 3;
	std::uint64_t nConfirmedInputSequence = 0;
	Gameplay::Vector3 vPosition{};
	Gameplay::Vector3 vVelocity{};
};

struct Disconnect
{
	std::uint16_t nReason = 0;
	std::uint64_t nAcknowledgeSequence = 0;
	std::uint64_t nDrainDeadlineTick = 0;
};

struct ErrorReject
{
	std::uint16_t nRejectedType = 0;
	std::uint16_t nReason = 0;
	std::uint16_t nFatal = 0;
	std::uint64_t nRejectedSequence = 0;
};

[[nodiscard]] Runtime::RuntimeStatus EncodeFrame(const FrameHeader &in_stHeader, const std::vector<std::uint8_t> &in_arrPayload, std::vector<std::uint8_t> &out_arrFrame);
[[nodiscard]] Runtime::RuntimeStatus DecodeHeader(const std::uint8_t *pData, std::size_t nSize, FrameHeader &out_stHeader) noexcept;
[[nodiscard]] std::vector<std::uint8_t> EncodeClientHello(const ClientHello &in_stHello);
[[nodiscard]] Runtime::RuntimeStatus DecodeClientHello(const std::uint8_t *pData, std::size_t nSize, ClientHello &out_stHello) noexcept;
[[nodiscard]] std::vector<std::uint8_t> EncodeServerWelcome(const ServerWelcome &in_stWelcome);
[[nodiscard]] Runtime::RuntimeStatus DecodeServerWelcome(const std::uint8_t *pData, std::size_t nSize, ServerWelcome &out_stWelcome) noexcept;
[[nodiscard]] std::vector<std::uint8_t> EncodeDisconnect(const Disconnect &in_stDisconnect);
[[nodiscard]] std::vector<std::uint8_t> EncodeErrorReject(const ErrorReject &in_stError);

} // namespace EngineNext::Network
