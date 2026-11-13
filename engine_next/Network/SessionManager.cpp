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
			std::all_of(in_stHello.arrResumeToken.begin(), in_stHello.arrResumeToken.end(), [](std::uint8_t nValue)
						{ return nValue == 0; });
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

const std::map<PeerId, Session> &SessionManager::GetSessions() const noexcept
{
	return mapSessions;
}

std::size_t SessionManager::GetSessionCount() const noexcept
{
	return mapSessions.size();
}

std::size_t SessionManager::GetDisconnectedCount() const noexcept
{
	return mapDisconnected.size();
}

bool SessionManager::IsEntityDisconnected(std::uint64_t nEntityId) const noexcept
{
	for (const std::pair<const std::uint64_t, DisconnectedSession> &stEntry : mapDisconnected)
	{
		if (stEntry.second.stSession.stEntityId.nValue == nEntityId)
		{
			return true;
		}
	}
	return false;
}

bool SessionManager::DisconnectSession(PeerId in_nPeerId, std::uint64_t nNowMsec) noexcept
{
	const std::map<PeerId, Session>::iterator stIterator = mapSessions.find(in_nPeerId);
	if (stIterator == mapSessions.end())
	{
		return false;
	}
	DisconnectedSession stDisconnected{ stIterator->second, nNowMsec + 5000 };
	mapDisconnected.emplace(stDisconnected.stSession.nSessionId, stDisconnected);
	mapSessions.erase(stIterator);
	return true;
}

Runtime::RuntimeStatus SessionManager::ResumeSession(PeerId in_nPeerId, const ClientHello &in_stHello, std::uint64_t nNowMsec, ServerWelcome &out_stWelcome, std::uint64_t &out_nSessionId)
{
	if (in_nPeerId == 0 || in_stHello.nResumeSessionId == 0)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	if (mapSessions.find(in_nPeerId) != mapSessions.end())
	{
		return Runtime::RuntimeStatus::AlreadyExists;
	}
	for (const std::pair<const PeerId, Session> &stEntry : mapSessions)
	{
		if (stEntry.second.nSessionId == in_stHello.nResumeSessionId)
		{
			return Runtime::RuntimeStatus::AlreadyExists;
		}
	}
	const std::map<std::uint64_t, DisconnectedSession>::iterator stDisconnected = mapDisconnected.find(in_stHello.nResumeSessionId);
	if (stDisconnected == mapDisconnected.end() || stDisconnected->second.nGraceDeadlineMsec <= nNowMsec ||
		stDisconnected->second.stSession.arrResumeToken != in_stHello.arrResumeToken)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	const Gameplay::PredictionState *pState = pWorld->Find(stDisconnected->second.stSession.stEntityId);
	if (pState == nullptr)
	{
		return Runtime::RuntimeStatus::InvalidState;
	}
	Session stSession = stDisconnected->second.stSession;
	stSession.nPeerId = in_nPeerId;
	FillToken(stSession.arrResumeToken);
	mapDisconnected.erase(stDisconnected);
	mapSessions.emplace(in_nPeerId, stSession);

	out_stWelcome = ServerWelcome{};
	out_stWelcome.nEntityId = stSession.stEntityId.nValue;
	out_stWelcome.arrResumeToken = stSession.arrResumeToken;
	out_stWelcome.nServerTick = pState->nServerTimeMsec / 16;
	out_stWelcome.nConfirmedInputSequence = pState->nConfirmedSequence;
	out_stWelcome.vPosition = pState->vPosition;
	out_stWelcome.vVelocity = pState->vVelocity;
	out_nSessionId = stSession.nSessionId;
	return Runtime::RuntimeStatus::Ok;
}

std::size_t SessionManager::ExpireDisconnected(std::uint64_t nNowMsec, std::vector<Runtime::EntityId> &out_arrExpired) noexcept
{
	out_arrExpired.clear();
	for (std::map<std::uint64_t, DisconnectedSession>::iterator stIterator = mapDisconnected.begin(); stIterator != mapDisconnected.end();)
	{
		if (stIterator->second.nGraceDeadlineMsec > nNowMsec)
		{
			++stIterator;
			continue;
		}
		out_arrExpired.push_back(stIterator->second.stSession.stEntityId);
		(void)pWorld->Destroy(stIterator->second.stSession.stEntityId);
		stIterator = mapDisconnected.erase(stIterator);
	}
	return out_arrExpired.size();
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
