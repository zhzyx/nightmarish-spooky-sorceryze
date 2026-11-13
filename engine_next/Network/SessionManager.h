/**************************************************************************/
/*  SessionManager.h                                                      */
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
#include "engine_next/include/EngineNext/Network/Protocol.h"
#include "engine_next/include/EngineNext/Runtime/World.h"

#include <cstdint>
#include <map>
#include <vector>

namespace EngineNext::Network
{

struct Session
{
	std::uint64_t nSessionId = 0;
	PeerId nPeerId = 0;
	Runtime::EntityId stEntityId;
	ReconnectToken arrResumeToken{};
};

class SessionManager
{
	Runtime::World *pWorld = nullptr;
	struct DisconnectedSession
	{
		Session stSession;
		std::uint64_t nGraceDeadlineMsec = 0;
	};

	std::map<PeerId, Session> mapSessions;
	std::map<std::uint64_t, DisconnectedSession> mapDisconnected;
	std::uint64_t nNextSessionId = 1;
	std::uint64_t nRandomState = 1;

	void FillToken(ReconnectToken &out_arrToken) noexcept;

public:
	SessionManager(Runtime::World &in_stWorld, std::uint64_t nSeed);
	[[nodiscard]] Runtime::RuntimeStatus CreateSession(PeerId in_nPeerId, const ClientHello &in_stHello, ServerWelcome &out_stWelcome, std::uint64_t &out_nSessionId);
	[[nodiscard]] const Session *GetSession(PeerId in_nPeerId) const noexcept;
	[[nodiscard]] const std::map<PeerId, Session> &GetSessions() const noexcept;
	[[nodiscard]] std::size_t GetSessionCount() const noexcept;
	[[nodiscard]] std::size_t GetDisconnectedCount() const noexcept;
	[[nodiscard]] bool IsEntityDisconnected(std::uint64_t nEntityId) const noexcept;
	[[nodiscard]] bool DisconnectSession(PeerId in_nPeerId, std::uint64_t nNowMsec) noexcept;
	[[nodiscard]] Runtime::RuntimeStatus ResumeSession(PeerId in_nPeerId, const ClientHello &in_stHello, std::uint64_t nNowMsec, ServerWelcome &out_stWelcome, std::uint64_t &out_nSessionId);
	[[nodiscard]] std::size_t ExpireDisconnected(std::uint64_t nNowMsec, std::vector<Runtime::EntityId> &out_arrExpired) noexcept;
	[[nodiscard]] bool RemoveSession(PeerId in_nPeerId) noexcept;
};

} // namespace EngineNext::Network
