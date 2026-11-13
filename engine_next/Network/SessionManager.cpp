/**************************************************************************/
/*  SessionManager.cpp                                                    */
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

#include "engine_next/Network/SessionManager.h"

#include <algorithm>

namespace EngineNext::Network
{

SessionManager::SessionManager(Runtime::World &in_stWorld, std::uint64_t nSeed) :
		pWorld(&in_stWorld), nRandomState(nSeed == 0 ? 1 : nSeed)
{
}

void SessionManager::FillToken(ReconnectToken &out_arrToken) noexcept
{
	for (std::uint8_t &nValue : out_arrToken)
	{
		nRandomState ^= nRandomState << 13U;
		nRandomState ^= nRandomState >> 7U;
		nRandomState ^= nRandomState << 17U;
		nValue = static_cast<std::uint8_t>(nRandomState & 0xFFU);
	}
}

Runtime::RuntimeStatus SessionManager::CreateSession(PeerId in_nPeerId, const ClientHello &in_stHello, ServerWelcome &out_stWelcome, std::uint64_t &out_nSessionId)
{
	const bool bResumeEmpty = in_stHello.nResumeSessionId == 0 &&
			std::all_of(in_stHello.arrResumeToken.begin(), in_stHello.arrResumeToken.end(), [](std::uint8_t nValue) { return nValue == 0; });
	if (in_nPeerId == 0 || !bResumeEmpty)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	if (mapSessions.find(in_nPeerId) != mapSessions.end())
	{
		return Runtime::RuntimeStatus::AlreadyExists;
	}
	if (nNextSessionId == 0)
	{
		return Runtime::RuntimeStatus::InvalidState;
	}
	const std::uint64_t nSessionId = nNextSessionId++;
	const Runtime::EntityId stEntityId{ nSessionId };
	const Runtime::RuntimeStatus eWorldStatus = pWorld->CreateWithId(stEntityId);
	if (eWorldStatus != Runtime::RuntimeStatus::Ok)
	{
		return eWorldStatus;
	}
	Session stSession;
	stSession.nSessionId = nSessionId;
	stSession.nPeerId = in_nPeerId;
	stSession.stEntityId = stEntityId;
	FillToken(stSession.arrResumeToken);
	mapSessions.emplace(in_nPeerId, stSession);

	out_stWelcome = ServerWelcome{};
	out_stWelcome.nEntityId = stEntityId.nValue;
	out_stWelcome.arrResumeToken = stSession.arrResumeToken;
	out_nSessionId = nSessionId;
	return Runtime::RuntimeStatus::Ok;
}

const Session *SessionManager::GetSession(PeerId in_nPeerId) const noexcept
{
	const std::map<PeerId, Session>::const_iterator stIterator = mapSessions.find(in_nPeerId);
	return stIterator == mapSessions.end() ? nullptr : &stIterator->second;
}

std::size_t SessionManager::GetSessionCount() const noexcept
{
	return mapSessions.size();
}

bool SessionManager::RemoveSession(PeerId in_nPeerId) noexcept
{
	const std::map<PeerId, Session>::iterator stIterator = mapSessions.find(in_nPeerId);
	if (stIterator == mapSessions.end())
	{
		return false;
	}
	(void)pWorld->Destroy(stIterator->second.stEntityId);
	mapSessions.erase(stIterator);
	return true;
}

} // namespace EngineNext::Network
