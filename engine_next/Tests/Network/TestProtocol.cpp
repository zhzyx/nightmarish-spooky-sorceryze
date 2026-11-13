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
