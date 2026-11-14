/**************************************************************************/
/*  Sha256.cpp                                                            */
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

#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <array>
#include <cstdint>

namespace EngineNext::Serialization
{
namespace
{

constexpr std::array<std::uint32_t, 64> CONSTANTS = {
	0x428a2f98U,
	0x71374491U,
	0xb5c0fbcfU,
	0xe9b5dba5U,
	0x3956c25bU,
	0x59f111f1U,
	0x923f82a4U,
	0xab1c5ed5U,
	0xd807aa98U,
	0x12835b01U,
	0x243185beU,
	0x550c7dc3U,
	0x72be5d74U,
	0x80deb1feU,
	0x9bdc06a7U,
	0xc19bf174U,
	0xe49b69c1U,
	0xefbe4786U,
	0x0fc19dc6U,
	0x240ca1ccU,
	0x2de92c6fU,
	0x4a7484aaU,
	0x5cb0a9dcU,
	0x76f988daU,
	0x983e5152U,
	0xa831c66dU,
	0xb00327c8U,
	0xbf597fc7U,
	0xc6e00bf3U,
	0xd5a79147U,
	0x06ca6351U,
	0x14292967U,
	0x27b70a85U,
	0x2e1b2138U,
	0x4d2c6dfcU,
	0x53380d13U,
	0x650a7354U,
	0x766a0abbU,
	0x81c2c92eU,
	0x92722c85U,
	0xa2bfe8a1U,
	0xa81a664bU,
	0xc24b8b70U,
	0xc76c51a3U,
	0xd192e819U,
	0xd6990624U,
	0xf40e3585U,
	0x106aa070U,
	0x19a4c116U,
	0x1e376c08U,
	0x2748774cU,
	0x34b0bcb5U,
	0x391c0cb3U,
	0x4ed8aa4aU,
	0x5b9cca4fU,
	0x682e6ff3U,
	0x748f82eeU,
	0x78a5636fU,
	0x84c87814U,
	0x8cc70208U,
	0x90befffaU,
	0xa4506cebU,
	0xbef9a3f7U,
	0xc67178f2U,
};

std::uint32_t RotateRight(std::uint32_t in_nValue, std::uint32_t in_nBits)
{
	return (in_nValue >> in_nBits) | (in_nValue << (32U - in_nBits));
}

void Compress(const std::uint8_t *in_pBlock, std::array<std::uint32_t, 8> &out_arrState)
{
	std::array<std::uint32_t, 64> arrWords{};
	for (std::size_t nIndex = 0; nIndex < 16; ++nIndex)
	{
		const std::size_t nOffset = nIndex * 4;
		arrWords[nIndex] = (static_cast<std::uint32_t>(in_pBlock[nOffset]) << 24U) |
				(static_cast<std::uint32_t>(in_pBlock[nOffset + 1]) << 16U) |
				(static_cast<std::uint32_t>(in_pBlock[nOffset + 2]) << 8U) | in_pBlock[nOffset + 3];
	}
	for (std::size_t nIndex = 16; nIndex < 64; ++nIndex)
	{
		const std::uint32_t nS0 = RotateRight(arrWords[nIndex - 15], 7) ^ RotateRight(arrWords[nIndex - 15], 18) ^ (arrWords[nIndex - 15] >> 3U);
		const std::uint32_t nS1 = RotateRight(arrWords[nIndex - 2], 17) ^ RotateRight(arrWords[nIndex - 2], 19) ^ (arrWords[nIndex - 2] >> 10U);
		arrWords[nIndex] = arrWords[nIndex - 16] + nS0 + arrWords[nIndex - 7] + nS1;
	}
	std::uint32_t nA = out_arrState[0];
	std::uint32_t nB = out_arrState[1];
	std::uint32_t nC = out_arrState[2];
	std::uint32_t nD = out_arrState[3];
	std::uint32_t nE = out_arrState[4];
	std::uint32_t nF = out_arrState[5];
	std::uint32_t nG = out_arrState[6];
	std::uint32_t nH = out_arrState[7];
	for (std::size_t nIndex = 0; nIndex < 64; ++nIndex)
	{
		const std::uint32_t nS1 = RotateRight(nE, 6) ^ RotateRight(nE, 11) ^ RotateRight(nE, 25);
		const std::uint32_t nChoice = (nE & nF) ^ (~nE & nG);
		const std::uint32_t nTemp1 = nH + nS1 + nChoice + CONSTANTS[nIndex] + arrWords[nIndex];
		const std::uint32_t nS0 = RotateRight(nA, 2) ^ RotateRight(nA, 13) ^ RotateRight(nA, 22);
		const std::uint32_t nMajority = (nA & nB) ^ (nA & nC) ^ (nB & nC);
		const std::uint32_t nTemp2 = nS0 + nMajority;
		nH = nG;
		nG = nF;
		nF = nE;
		nE = nD + nTemp1;
		nD = nC;
		nC = nB;
		nB = nA;
		nA = nTemp1 + nTemp2;
	}
	out_arrState[0] += nA;
	out_arrState[1] += nB;
	out_arrState[2] += nC;
	out_arrState[3] += nD;
	out_arrState[4] += nE;
	out_arrState[5] += nF;
	out_arrState[6] += nG;
	out_arrState[7] += nH;
}

} // namespace

std::string Sha256Hex(const void *in_pData, std::size_t in_nBytes)
{
	static const char arrHex[] = "0123456789abcdef";
	const std::uint8_t *pData = static_cast<const std::uint8_t *>(in_pData);
	std::array<std::uint32_t, 8> arrState = { 0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU, 0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U };
	std::size_t nOffset = 0;
	while (in_nBytes - nOffset >= 64)
	{
		Compress(pData + nOffset, arrState);
		nOffset += 64;
	}
	std::array<std::uint8_t, 128> arrTail{};
	const std::size_t nRemaining = in_nBytes - nOffset;
	for (std::size_t nIndex = 0; nIndex < nRemaining; ++nIndex)
	{
		arrTail[nIndex] = pData[nOffset + nIndex];
	}
	arrTail[nRemaining] = 0x80U;
	const std::size_t nTailBytes = nRemaining < 56 ? 64 : 128;
	const std::uint64_t nBits = static_cast<std::uint64_t>(in_nBytes) * 8ULL;
	for (std::size_t nIndex = 0; nIndex < 8; ++nIndex)
	{
		arrTail[nTailBytes - 1 - nIndex] = static_cast<std::uint8_t>(nBits >> (nIndex * 8U));
	}
	Compress(arrTail.data(), arrState);
	if (nTailBytes == 128)
	{
		Compress(arrTail.data() + 64, arrState);
	}
	std::string strResult(64, '0');
	for (std::size_t nWord = 0; nWord < arrState.size(); ++nWord)
	{
		for (std::size_t nByte = 0; nByte < 4; ++nByte)
		{
			const std::uint8_t nValue = static_cast<std::uint8_t>(arrState[nWord] >> ((3 - nByte) * 8U));
			strResult[nWord * 8 + nByte * 2] = arrHex[nValue >> 4U];
			strResult[nWord * 8 + nByte * 2 + 1] = arrHex[nValue & 0x0FU];
		}
	}
	return strResult;
}

std::string Sha256Hex(const std::string &in_strData)
{
	return Sha256Hex(in_strData.data(), in_strData.size());
}

} // namespace EngineNext::Serialization
