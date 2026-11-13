/**************************************************************************/
/*  TestProtocol.cpp                                                      */
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

#include "engine_next/Network/SessionManager.h"

ENGINE_NEXT_TEST("Protocol encodes and decodes little-endian hello and welcome frames")
{
	EngineNext::Network::ClientHello stHello;
	stHello.nClientNonce = 0x1122334455667788ULL;
	stHello.arrResumeToken[0] = 7;
	const std::vector<std::uint8_t> arrPayload = EngineNext::Network::EncodeClientHello(stHello);
	ENGINE_NEXT_CHECK_EQ(arrPayload.size(), 32ULL);
	ENGINE_NEXT_CHECK_EQ(arrPayload[0], 0x88);
	EngineNext::Network::FrameHeader stHeader;
	stHeader.eType = EngineNext::Network::MessageType::ClientHello;
	stHeader.nMessageSequence = 9;
	std::vector<std::uint8_t> arrFrame;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, arrPayload, arrFrame), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(arrFrame.size(), 64ULL);
	ENGINE_NEXT_CHECK_EQ(arrFrame[0], 'N');
	ENGINE_NEXT_CHECK_EQ(arrFrame[1], 'E');
	ENGINE_NEXT_CHECK_EQ(arrFrame[2], 'X');
	ENGINE_NEXT_CHECK_EQ(arrFrame[3], 'T');
	ENGINE_NEXT_CHECK_EQ(arrFrame[16], 9);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeHeader(arrFrame.data(), arrFrame.size(), stHeader), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stHeader.nMessageSequence, 9ULL);
	EngineNext::Network::ClientHello stDecoded;
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Network::DecodeClientHello(arrFrame.data() + EngineNext::Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stDecoded),
			EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nClientNonce, stHello.nClientNonce);
	ENGINE_NEXT_CHECK_EQ(stDecoded.arrResumeToken[0], 7);

	EngineNext::Network::ServerWelcome stWelcome;
	stWelcome.nEntityId = 42;
	stWelcome.nServerTick = 100;
	stWelcome.vPosition = EngineNext::Gameplay::Vector3{ 1.0F, 2.0F, 3.0F };
	stWelcome.vVelocity = EngineNext::Gameplay::Vector3{ 4.0F, 5.0F, 6.0F };
	const std::vector<std::uint8_t> arrWelcome = EngineNext::Network::EncodeServerWelcome(stWelcome);
	ENGINE_NEXT_CHECK_EQ(arrWelcome.size(), 72ULL);
	stHeader.eType = EngineNext::Network::MessageType::ServerWelcome;
	stHeader.nSessionId = 42;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, arrWelcome, arrFrame), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeHeader(arrFrame.data(), arrFrame.size(), stHeader), EngineNext::Runtime::RuntimeStatus::Ok);
	EngineNext::Network::ServerWelcome stDecodedWelcome;
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Network::DecodeServerWelcome(arrFrame.data() + EngineNext::Network::FRAME_HEADER_BYTES, stHeader.nPayloadBytes, stDecodedWelcome),
			EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stDecodedWelcome.nEntityId, 42ULL);
	ENGINE_NEXT_CHECK_EQ(stDecodedWelcome.nServerTick, 100ULL);
	ENGINE_NEXT_CHECK_FLOAT(stDecodedWelcome.vPosition.fY, 2.0F);
	ENGINE_NEXT_CHECK_FLOAT(stDecodedWelcome.vVelocity.fZ, 6.0F);
}

ENGINE_NEXT_TEST("Protocol rejects bad versions, lengths, flags, sequences and oversized packets")
{
	EngineNext::Network::FrameHeader stHeader;
	const std::vector<std::uint8_t> arrPayload{ 1, 2, 3 };
	std::vector<std::uint8_t> arrFrame;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, arrPayload, arrFrame), EngineNext::Runtime::RuntimeStatus::Ok);
	arrFrame[4] = 2;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeHeader(arrFrame.data(), arrFrame.size(), stHeader), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	arrFrame[0] = 'B';
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeHeader(arrFrame.data(), arrFrame.size(), stHeader), EngineNext::Runtime::RuntimeStatus::InvalidParameter);

	stHeader.nMessageSequence = 0;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, arrPayload, arrFrame), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	stHeader.nMessageSequence = 1;
	stHeader.nFlags = 1;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, arrPayload, arrFrame), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	stHeader.nFlags = 0;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, std::vector<std::uint8_t>(1169, 0), arrFrame), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeHeader(arrFrame.data(), 1201, stHeader), EngineNext::Runtime::RuntimeStatus::InvalidParameter);

	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::EncodeFrame(stHeader, arrPayload, arrFrame), EngineNext::Runtime::RuntimeStatus::Ok);
	arrFrame.push_back(0);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeHeader(arrFrame.data(), arrFrame.size(), stHeader), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
}

ENGINE_NEXT_TEST("Protocol disconnect carries drain deadline and acknowledgement")
{
	EngineNext::Network::Disconnect stDisconnect;
	stDisconnect.nReason = static_cast<std::uint16_t>(EngineNext::Network::DisconnectReason::DrainAcknowledge);
	stDisconnect.nAcknowledgeSequence = 17;
	stDisconnect.nDrainDeadlineTick = 200;
	const std::vector<std::uint8_t> arrPayload = EngineNext::Network::EncodeDisconnect(stDisconnect);
	ENGINE_NEXT_CHECK_EQ(arrPayload.size(), 18ULL);
	EngineNext::Network::Disconnect stDecoded;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeDisconnect(arrPayload.data(), arrPayload.size(), stDecoded), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nReason, 3U);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nAcknowledgeSequence, 17ULL);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nDrainDeadlineTick, 200ULL);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeDisconnect(arrPayload.data(), arrPayload.size() - 1, stDecoded), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
}

ENGINE_NEXT_TEST("Session creation keeps peer, session and entity identities separate")
{
	EngineNext::Runtime::World stWorld;
	EngineNext::Network::SessionManager stSessions(stWorld, 7);
	EngineNext::Network::ClientHello stHello;
	EngineNext::Network::ServerWelcome stFirstWelcome;
	EngineNext::Network::ServerWelcome stSecondWelcome;
	std::uint64_t nFirstSession = 0;
	std::uint64_t nSecondSession = 0;
	ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(11, stHello, stFirstWelcome, nFirstSession), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(22, stHello, stSecondWelcome, nSecondSession), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(nFirstSession != nSecondSession);
	ENGINE_NEXT_CHECK(stFirstWelcome.nEntityId != stSecondWelcome.nEntityId);
	ENGINE_NEXT_CHECK(stFirstWelcome.arrResumeToken != stSecondWelcome.arrResumeToken);
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 2ULL);
	ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(11, stHello, stFirstWelcome, nFirstSession), EngineNext::Runtime::RuntimeStatus::AlreadyExists);
	stHello.nResumeSessionId = nSecondSession;
	ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(33, stHello, stFirstWelcome, nFirstSession), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK(stSessions.RemoveSession(11));
	ENGINE_NEXT_CHECK(!stSessions.RemoveSession(11));
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 1ULL);
}

ENGINE_NEXT_TEST("Reconnect preserves identity and authority rotates tokens and rejects replay")
{
	EngineNext::Runtime::World stWorld;
	EngineNext::Network::SessionManager stSessions(stWorld, 41);
	EngineNext::Network::ClientHello stHello;
	EngineNext::Network::ServerWelcome stWelcome;
	std::uint64_t nSessionId = 0;
	ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(1, stHello, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::Ok);
	EngineNext::Gameplay::PredictionState *pState = stWorld.Find(EngineNext::Runtime::EntityId{ nSessionId });
	ENGINE_NEXT_CHECK(pState != nullptr);
	pState->vPosition = { 1.536F, 0.0F, 0.0F };
	pState->nConfirmedSequence = 12;
	pState->nServerTimeMsec = 192;
	ENGINE_NEXT_CHECK(stSessions.DisconnectSession(1, 100));
	ENGINE_NEXT_CHECK_EQ(stSessions.GetDisconnectedCount(), 1U);
	ENGINE_NEXT_CHECK(stSessions.IsEntityDisconnected(nSessionId));
	ENGINE_NEXT_CHECK(stSessions.GetSession(1) == nullptr);
	EngineNext::Network::ClientHello stResume;
	stResume.nResumeSessionId = nSessionId;
	stResume.arrResumeToken = stWelcome.arrResumeToken;
	stResume.arrResumeToken[0] ^= 1U;
	ENGINE_NEXT_CHECK_EQ(stSessions.ResumeSession(2, stResume, 200, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	stResume.arrResumeToken = stWelcome.arrResumeToken;
	ENGINE_NEXT_CHECK_EQ(stSessions.ResumeSession(2, stResume, 200, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(nSessionId, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stWelcome.nEntityId, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stWelcome.nConfirmedInputSequence, 12ULL);
	ENGINE_NEXT_CHECK_FLOAT(stWelcome.vPosition.fX, 1.536F);
	ENGINE_NEXT_CHECK(stWelcome.arrResumeToken != stResume.arrResumeToken);
	ENGINE_NEXT_CHECK_EQ(stSessions.GetDisconnectedCount(), 0U);
	ENGINE_NEXT_CHECK(!stSessions.IsEntityDisconnected(1));
	ENGINE_NEXT_CHECK(stSessions.GetSession(2) != nullptr);
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 1U);
	ENGINE_NEXT_CHECK_EQ(stSessions.ResumeSession(3, stResume, 201, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::AlreadyExists);
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 1U);
}

ENGINE_NEXT_TEST("Disconnected sessions expire exactly at the grace deadline")
{
	EngineNext::Runtime::World stWorld;
	EngineNext::Network::SessionManager stSessions(stWorld, 7);
	EngineNext::Network::ClientHello stHello;
	EngineNext::Network::ServerWelcome stWelcome;
	std::uint64_t nSessionId = 0;
	ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(1, stHello, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stSessions.DisconnectSession(1, 100));
	stHello.nResumeSessionId = nSessionId;
	stHello.arrResumeToken = stWelcome.arrResumeToken;
	ENGINE_NEXT_CHECK_EQ(stSessions.ResumeSession(2, stHello, 5100, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	std::vector<EngineNext::Runtime::EntityId> arrExpired;
	ENGINE_NEXT_CHECK_EQ(stSessions.ExpireDisconnected(5099, arrExpired), 0U);
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 1U);
	ENGINE_NEXT_CHECK_EQ(stSessions.ExpireDisconnected(5100, arrExpired), 1U);
	ENGINE_NEXT_CHECK_EQ(arrExpired.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(arrExpired[0].nValue, nSessionId);
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 0U);
	ENGINE_NEXT_CHECK_EQ(stSessions.GetDisconnectedCount(), 0U);
}

ENGINE_NEXT_TEST("Protocol decodes nonfatal draining rejects and validates flags")
{
	EngineNext::Network::ErrorReject stReject;
	stReject.nRejectedType = static_cast<std::uint16_t>(EngineNext::Network::MessageType::ClientHello);
	stReject.nReason = EngineNext::Network::REJECT_SERVER_DRAINING;
	stReject.nFatal = 0;
	stReject.nRejectedSequence = 9;
	const std::vector<std::uint8_t> arrPayload = EngineNext::Network::EncodeErrorReject(stReject);
	EngineNext::Network::ErrorReject stDecoded;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeErrorReject(arrPayload.data(), arrPayload.size(), stDecoded), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nRejectedType, 1U);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nReason, 8U);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nFatal, 0U);
	ENGINE_NEXT_CHECK_EQ(stDecoded.nRejectedSequence, 9ULL);
	std::vector<std::uint8_t> arrInvalid = arrPayload;
	arrInvalid[4] = 2;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Network::DecodeErrorReject(arrInvalid.data(), arrInvalid.size(), stDecoded), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
}
