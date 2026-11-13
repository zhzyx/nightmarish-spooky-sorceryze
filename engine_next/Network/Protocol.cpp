/**************************************************************************/
/*  Protocol.cpp                                                          */
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

#include "engine_next/include/EngineNext/Network/Protocol.h"

#include <cmath>
#include <cstring>

namespace EngineNext::Network
{
namespace
{

void Write16(std::uint16_t nValue, std::vector<std::uint8_t> &out_arrData)
{
	out_arrData.push_back(static_cast<std::uint8_t>(nValue & 0xFFU));
	out_arrData.push_back(static_cast<std::uint8_t>((nValue >> 8U) & 0xFFU));
}

void Write32(std::uint32_t nValue, std::vector<std::uint8_t> &out_arrData)
{
	for (std::uint32_t nShift = 0; nShift < 32; nShift += 8)
	{
		out_arrData.push_back(static_cast<std::uint8_t>((nValue >> nShift) & 0xFFU));
	}
}

void Write64(std::uint64_t nValue, std::vector<std::uint8_t> &out_arrData)
{
	for (std::uint64_t nShift = 0; nShift < 64; nShift += 8)
	{
		out_arrData.push_back(static_cast<std::uint8_t>((nValue >> nShift) & 0xFFU));
	}
}

void WriteFloat(float fValue, std::vector<std::uint8_t> &out_arrData)
{
	static_assert(sizeof(float) == sizeof(std::uint32_t), "Protocol floats must be 32-bit");
	std::uint32_t nBits = 0;
	std::memcpy(&nBits, &fValue, sizeof(nBits));
	Write32(nBits, out_arrData);
}

void WriteToken(const ReconnectToken &in_arrToken, std::vector<std::uint8_t> &out_arrData)
{
	out_arrData.insert(out_arrData.end(), in_arrToken.begin(), in_arrToken.end());
}

std::uint16_t Read16(const std::uint8_t *pData) noexcept
{
	return static_cast<std::uint16_t>(pData[0]) | static_cast<std::uint16_t>(pData[1] << 8U);
}

std::uint32_t Read32(const std::uint8_t *pData) noexcept
{
	std::uint32_t nValue = 0;
	for (std::uint32_t nShift = 0; nShift < 32; nShift += 8)
	{
		nValue |= static_cast<std::uint32_t>(pData[nShift / 8]) << nShift;
	}
	return nValue;
}

std::uint64_t Read64(const std::uint8_t *pData) noexcept
{
	std::uint64_t nValue = 0;
	for (std::uint64_t nShift = 0; nShift < 64; nShift += 8)
	{
		nValue |= static_cast<std::uint64_t>(pData[nShift / 8]) << nShift;
	}
	return nValue;
}

float ReadFloat(const std::uint8_t *pData) noexcept
{
	const std::uint32_t nBits = Read32(pData);
	float fValue = 0.0F;
	std::memcpy(&fValue, &nBits, sizeof(fValue));
	return fValue;
}

bool IsFinite(Gameplay::Vector3 in_vValue) noexcept
{
	return std::isfinite(in_vValue.fX) && std::isfinite(in_vValue.fY) && std::isfinite(in_vValue.fZ);
}

bool IsValidType(std::uint16_t nType) noexcept
{
	return nType >= static_cast<std::uint16_t>(MessageType::ClientHello) &&
			nType <= static_cast<std::uint16_t>(MessageType::ErrorReject);
}

} // namespace

Runtime::RuntimeStatus EncodeFrame(const FrameHeader &in_stHeader, const std::vector<std::uint8_t> &in_arrPayload, std::vector<std::uint8_t> &out_arrFrame)
{
	if (in_stHeader.nFlags != 0 || in_stHeader.nMessageSequence == 0 ||
		!IsValidType(static_cast<std::uint16_t>(in_stHeader.eType)) ||
		in_arrPayload.size() > MAX_PACKET_BYTES - FRAME_HEADER_BYTES)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	out_arrFrame.clear();
	out_arrFrame.reserve(FRAME_HEADER_BYTES + in_arrPayload.size());
	out_arrFrame.insert(out_arrFrame.end(), { 'N', 'E', 'X', 'T' });
	Write16(PROTOCOL_VERSION, out_arrFrame);
	Write16(static_cast<std::uint16_t>(in_stHeader.eType), out_arrFrame);
	Write16(static_cast<std::uint16_t>(FRAME_HEADER_BYTES), out_arrFrame);
	Write16(in_stHeader.nFlags, out_arrFrame);
	Write32(static_cast<std::uint32_t>(in_arrPayload.size()), out_arrFrame);
	Write64(in_stHeader.nMessageSequence, out_arrFrame);
	Write64(in_stHeader.nSessionId, out_arrFrame);
	out_arrFrame.insert(out_arrFrame.end(), in_arrPayload.begin(), in_arrPayload.end());
	return Runtime::RuntimeStatus::Ok;
}

Runtime::RuntimeStatus DecodeHeader(const std::uint8_t *pData, std::size_t nSize, FrameHeader &out_stHeader) noexcept
{
	if (pData == nullptr || nSize < FRAME_HEADER_BYTES || nSize > MAX_PACKET_BYTES)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	const std::uint16_t nType = Read16(pData + 6);
	out_stHeader.eType = static_cast<MessageType>(nType);
	out_stHeader.nFlags = Read16(pData + 10);
	out_stHeader.nPayloadBytes = Read32(pData + 12);
	out_stHeader.nMessageSequence = Read64(pData + 16);
	out_stHeader.nSessionId = Read64(pData + 24);
	const bool bValid = std::memcmp(pData, "NEXT", 4) == 0 &&
			Read16(pData + 4) == PROTOCOL_VERSION && IsValidType(nType) &&
			Read16(pData + 8) == FRAME_HEADER_BYTES && out_stHeader.nFlags == 0 &&
			out_stHeader.nMessageSequence != 0 && out_stHeader.nPayloadBytes == nSize - FRAME_HEADER_BYTES;
	return bValid ? Runtime::RuntimeStatus::Ok : Runtime::RuntimeStatus::InvalidParameter;
}

std::vector<std::uint8_t> EncodeClientHello(const ClientHello &in_stHello)
{
	std::vector<std::uint8_t> arrPayload;
	arrPayload.reserve(32);
	Write64(in_stHello.nClientNonce, arrPayload);
	Write64(in_stHello.nResumeSessionId, arrPayload);
	WriteToken(in_stHello.arrResumeToken, arrPayload);
	return arrPayload;
}

Runtime::RuntimeStatus DecodeClientHello(const std::uint8_t *pData, std::size_t nSize, ClientHello &out_stHello) noexcept
{
	if (pData == nullptr || nSize != 32)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	out_stHello.nClientNonce = Read64(pData);
	out_stHello.nResumeSessionId = Read64(pData + 8);
	std::memcpy(out_stHello.arrResumeToken.data(), pData + 16, out_stHello.arrResumeToken.size());
	return Runtime::RuntimeStatus::Ok;
}

std::vector<std::uint8_t> EncodeServerWelcome(const ServerWelcome &in_stWelcome)
{
	std::vector<std::uint8_t> arrPayload;
	arrPayload.reserve(72);
	Write64(in_stWelcome.nEntityId, arrPayload);
	WriteToken(in_stWelcome.arrResumeToken, arrPayload);
	Write64(in_stWelcome.nServerTick, arrPayload);
	Write32(in_stWelcome.nFixedStepMsec, arrPayload);
	Write32(in_stWelcome.nSnapshotIntervalTicks, arrPayload);
	Write64(in_stWelcome.nConfirmedInputSequence, arrPayload);
	WriteFloat(in_stWelcome.vPosition.fX, arrPayload);
	WriteFloat(in_stWelcome.vPosition.fY, arrPayload);
	WriteFloat(in_stWelcome.vPosition.fZ, arrPayload);
	WriteFloat(in_stWelcome.vVelocity.fX, arrPayload);
	WriteFloat(in_stWelcome.vVelocity.fY, arrPayload);
	WriteFloat(in_stWelcome.vVelocity.fZ, arrPayload);
	return arrPayload;
}

Runtime::RuntimeStatus DecodeServerWelcome(const std::uint8_t *pData, std::size_t nSize, ServerWelcome &out_stWelcome) noexcept
{
	if (pData == nullptr || nSize != 72)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	out_stWelcome.nEntityId = Read64(pData);
	std::memcpy(out_stWelcome.arrResumeToken.data(), pData + 8, out_stWelcome.arrResumeToken.size());
	out_stWelcome.nServerTick = Read64(pData + 24);
	out_stWelcome.nFixedStepMsec = Read32(pData + 32);
	out_stWelcome.nSnapshotIntervalTicks = Read32(pData + 36);
	out_stWelcome.nConfirmedInputSequence = Read64(pData + 40);
	out_stWelcome.vPosition = Gameplay::Vector3{ ReadFloat(pData + 48), ReadFloat(pData + 52), ReadFloat(pData + 56) };
	out_stWelcome.vVelocity = Gameplay::Vector3{ ReadFloat(pData + 60), ReadFloat(pData + 64), ReadFloat(pData + 68) };
	const bool bValid = out_stWelcome.nEntityId != 0 && out_stWelcome.nFixedStepMsec > 0 &&
			out_stWelcome.nFixedStepMsec <= 1000 && out_stWelcome.nSnapshotIntervalTicks != 0 &&
			IsFinite(out_stWelcome.vPosition) && IsFinite(out_stWelcome.vVelocity);
	return bValid ? Runtime::RuntimeStatus::Ok : Runtime::RuntimeStatus::InvalidParameter;
}

std::vector<std::uint8_t> EncodeInputCommand(const InputCommand &in_stCommand)
{
	std::vector<std::uint8_t> arrPayload;
	arrPayload.reserve(32);
	Write64(in_stCommand.nEntityId, arrPayload);
	Write64(in_stCommand.stInput.nSequence, arrPayload);
	Write32(in_stCommand.stInput.nStepMsec, arrPayload);
	WriteFloat(in_stCommand.stInput.vMovementInput.fX, arrPayload);
	WriteFloat(in_stCommand.stInput.vMovementInput.fY, arrPayload);
	WriteFloat(in_stCommand.stInput.vMovementInput.fZ, arrPayload);
	return arrPayload;
}

Runtime::RuntimeStatus DecodeInputCommand(const std::uint8_t *pData, std::size_t nSize, InputCommand &out_stCommand) noexcept
{
	if (pData == nullptr || nSize != 32)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	out_stCommand.nEntityId = Read64(pData);
	out_stCommand.stInput.nSequence = Read64(pData + 8);
	out_stCommand.stInput.nStepMsec = Read32(pData + 16);
	out_stCommand.stInput.vMovementInput = Gameplay::Vector3{ ReadFloat(pData + 20), ReadFloat(pData + 24), ReadFloat(pData + 28) };
	const bool bValid = out_stCommand.nEntityId != 0 && out_stCommand.stInput.nSequence != 0 &&
			out_stCommand.stInput.nStepMsec > 0 && out_stCommand.stInput.nStepMsec <= 1000 &&
			IsFinite(out_stCommand.stInput.vMovementInput) && out_stCommand.stInput.vMovementInput.LengthSquared() <= 1.000001F;
	return bValid ? Runtime::RuntimeStatus::Ok : Runtime::RuntimeStatus::InvalidParameter;
}

std::vector<std::uint8_t> EncodeSnapshot(const Snapshot &in_stSnapshot)
{
	std::vector<std::uint8_t> arrPayload;
	arrPayload.reserve(48);
	Write64(in_stSnapshot.nServerTick, arrPayload);
	Write64(in_stSnapshot.nEntityId, arrPayload);
	Write64(in_stSnapshot.nLastProcessedInputSequence, arrPayload);
	WriteFloat(in_stSnapshot.vPosition.fX, arrPayload);
	WriteFloat(in_stSnapshot.vPosition.fY, arrPayload);
	WriteFloat(in_stSnapshot.vPosition.fZ, arrPayload);
	WriteFloat(in_stSnapshot.vVelocity.fX, arrPayload);
	WriteFloat(in_stSnapshot.vVelocity.fY, arrPayload);
	WriteFloat(in_stSnapshot.vVelocity.fZ, arrPayload);
	return arrPayload;
}

Runtime::RuntimeStatus DecodeSnapshot(const std::uint8_t *pData, std::size_t nSize, Snapshot &out_stSnapshot) noexcept
{
	if (pData == nullptr || nSize != 48)
	{
		return Runtime::RuntimeStatus::InvalidParameter;
	}
	out_stSnapshot.nServerTick = Read64(pData);
	out_stSnapshot.nEntityId = Read64(pData + 8);
	out_stSnapshot.nLastProcessedInputSequence = Read64(pData + 16);
	out_stSnapshot.vPosition = Gameplay::Vector3{ ReadFloat(pData + 24), ReadFloat(pData + 28), ReadFloat(pData + 32) };
	out_stSnapshot.vVelocity = Gameplay::Vector3{ ReadFloat(pData + 36), ReadFloat(pData + 40), ReadFloat(pData + 44) };
	const bool bValid = out_stSnapshot.nEntityId != 0 && IsFinite(out_stSnapshot.vPosition) && IsFinite(out_stSnapshot.vVelocity);
	return bValid ? Runtime::RuntimeStatus::Ok : Runtime::RuntimeStatus::InvalidParameter;
}

std::vector<std::uint8_t> EncodeDisconnect(const Disconnect &in_stDisconnect)
{
	std::vector<std::uint8_t> arrPayload;
	arrPayload.reserve(18);
	Write16(in_stDisconnect.nReason, arrPayload);
	Write64(in_stDisconnect.nAcknowledgeSequence, arrPayload);
	Write64(in_stDisconnect.nDrainDeadlineTick, arrPayload);
	return arrPayload;
}

std::vector<std::uint8_t> EncodeErrorReject(const ErrorReject &in_stError)
{
	std::vector<std::uint8_t> arrPayload;
	arrPayload.reserve(14);
	Write16(in_stError.nRejectedType, arrPayload);
	Write16(in_stError.nReason, arrPayload);
	Write16(in_stError.nFatal, arrPayload);
	Write64(in_stError.nRejectedSequence, arrPayload);
	return arrPayload;
}

} // namespace EngineNext::Network
