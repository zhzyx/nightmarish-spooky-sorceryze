/**************************************************************************/
/*  TestImageDecoder.cpp                                                  */
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

#include "engine_next/Rendering/Cook/ImageDecoder.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/thirdparty/zlib/zlib.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <objbase.h>
#endif

namespace
{

using EngineNext::Rendering::DecodedImage;
using EngineNext::Rendering::ImageSemantic;
using EngineNext::Rendering::MipLevel;

std::uint32_t Crc32(const std::uint8_t *pBytes, std::size_t nSize)
{
	std::uint32_t nCrc = 0xFFFFFFFFU;
	for (std::size_t nIndex = 0; nIndex < nSize; ++nIndex)
	{
		nCrc ^= pBytes[nIndex];
		for (std::uint32_t nBit = 0; nBit < 8; ++nBit)
		{
			nCrc = (nCrc >> 1U) ^ (0xEDB88320U & (0U - (nCrc & 1U)));
		}
	}
	return nCrc ^ 0xFFFFFFFFU;
}

void AppendBigEndian(std::vector<std::uint8_t> &out_arrBytes, std::uint32_t nValue)
{
	out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> 24U));
	out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> 16U));
	out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> 8U));
	out_arrBytes.push_back(static_cast<std::uint8_t>(nValue));
}

void AppendChunk(std::vector<std::uint8_t> &out_arrBytes, const std::array<std::uint8_t, 4> &arrType, const std::vector<std::uint8_t> &arrData)
{
	AppendBigEndian(out_arrBytes, static_cast<std::uint32_t>(arrData.size()));
	const std::size_t nCrcStart = out_arrBytes.size();
	out_arrBytes.insert(out_arrBytes.end(), arrType.begin(), arrType.end());
	out_arrBytes.insert(out_arrBytes.end(), arrData.begin(), arrData.end());
	AppendBigEndian(out_arrBytes, Crc32(out_arrBytes.data() + nCrcStart, arrData.size() + 4));
}

std::vector<std::uint8_t> MakePng()
{
	// Two RGBA8 texels in a single uncompressed zlib block. This fixture is
	// authored here and carries complete image data, unlike M3 header fixtures.
	const std::vector<std::uint8_t> arrPixels{ 0, 255, 0, 0, 255, 0, 255, 0, 64 };
	std::vector<std::uint8_t> arrCompressed{ 0x78, 0x01, 0x01, 0x09, 0x00, 0xF6, 0xFF };
	arrCompressed.insert(arrCompressed.end(), arrPixels.begin(), arrPixels.end());
	std::uint32_t nFirst = 1;
	std::uint32_t nSecond = 0;
	for (const std::uint8_t nValue : arrPixels)
	{
		nFirst = (nFirst + nValue) % 65521;
		nSecond = (nSecond + nFirst) % 65521;
	}
	AppendBigEndian(arrCompressed, (nSecond << 16U) | nFirst);
	std::vector<std::uint8_t> arrPng{ 0x89, 'P', 'N', 'G', 13, 10, 26, 10 };
	const std::vector<std::uint8_t> arrHeader{ 0, 0, 0, 2, 0, 0, 0, 1, 8, 6, 0, 0, 0 };
	AppendChunk(arrPng, { 'I', 'H', 'D', 'R' }, arrHeader);
	AppendChunk(arrPng, { 'I', 'D', 'A', 'T' }, arrCompressed);
	AppendChunk(arrPng, { 'I', 'E', 'N', 'D' }, {});
	return arrPng;
}

std::vector<std::uint8_t> ReplacePngData(const std::vector<std::uint8_t> &arrRawData, bool bInterlaced = false)
{
	std::vector<std::uint8_t> arrPng = MakePng();
	arrPng.resize(8);
	std::vector<std::uint8_t> arrHeader{ 0, 0, 0, 2, 0, 0, 0, 1, 8, 6, 0, 0, static_cast<std::uint8_t>(bInterlaced) };
	AppendChunk(arrPng, { 'I', 'H', 'D', 'R' }, arrHeader);
	std::vector<std::uint8_t> arrCompressed{ 0x78, 0x01, 0x01 };
	const std::uint16_t nSize = static_cast<std::uint16_t>(arrRawData.size());
	const std::uint16_t nInverseSize = static_cast<std::uint16_t>(~nSize);
	arrCompressed.push_back(static_cast<std::uint8_t>(nSize));
	arrCompressed.push_back(static_cast<std::uint8_t>(nSize >> 8U));
	arrCompressed.push_back(static_cast<std::uint8_t>(nInverseSize));
	arrCompressed.push_back(static_cast<std::uint8_t>(nInverseSize >> 8U));
	arrCompressed.insert(arrCompressed.end(), arrRawData.begin(), arrRawData.end());
	AppendBigEndian(arrCompressed, static_cast<std::uint32_t>(adler32(1, arrRawData.data(), static_cast<uInt>(arrRawData.size()))));
	AppendChunk(arrPng, { 'I', 'D', 'A', 'T' }, arrCompressed);
	AppendChunk(arrPng, { 'I', 'E', 'N', 'D' }, {});
	return arrPng;
}

std::vector<std::uint8_t> MakeJpeg()
{
	// A project-authored 1x1 RGB image encoded as baseline JPEG at quality 100.
	return {
		0xFF,
		0xD8,
		0xFF,
		0xE0,
		0x00,
		0x10,
		0x4A,
		0x46,
		0x49,
		0x46,
		0x00,
		0x01,
		0x01,
		0x00,
		0x00,
		0x01,
		0x00,
		0x01,
		0x00,
		0x00,
		0xFF,
		0xDB,
		0x00,
		0x43,
		0x00,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0xFF,
		0xDB,
		0x00,
		0x43,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0x01,
		0xFF,
		0xC0,
		0x00,
		0x11,
		0x08,
		0x00,
		0x01,
		0x00,
		0x01,
		0x03,
		0x01,
		0x11,
		0x00,
		0x02,
		0x11,
		0x01,
		0x03,
		0x11,
		0x01,
		0xFF,
		0xC4,
		0x00,
		0x14,
		0x00,
		0x01,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x09,
		0xFF,
		0xC4,
		0x00,
		0x14,
		0x10,
		0x01,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0xFF,
		0xC4,
		0x00,
		0x15,
		0x01,
		0x01,
		0x01,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x09,
		0x0A,
		0xFF,
		0xC4,
		0x00,
		0x14,
		0x11,
		0x01,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0x00,
		0xFF,
		0xDA,
		0x00,
		0x0C,
		0x03,
		0x01,
		0x00,
		0x02,
		0x11,
		0x03,
		0x11,
		0x00,
		0x3F,
		0x00,
		0x1F,
		0xC7,
		0x7A,
		0xE4,
		0x1F,
		0xFF,
		0xD9,
	};
}

DecodedImage MakeBlackWhite()
{
	DecodedImage stImage;
	stImage.nWidth = 2;
	stImage.nHeight = 1;
	stImage.arrRgba8 = { 0, 0, 0, 255, 255, 255, 255, 255 };
	return stImage;
}

} // namespace

ENGINE_NEXT_TEST("Image decoder rejects unsupported malformed and oversized sources transactionally")
{
	DecodedImage stImage = MakeBlackWhite();
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage({ 1 }, "image/gif", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage({}, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage({ 0, 1, 2 }, "image/jpeg", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(MakePng(), "image/jpeg", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(std::vector<std::uint8_t>(16 * 1024 * 1024 + 1), "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stImage.nWidth, 2U);
	ENGINE_NEXT_CHECK_EQ(stImage.arrRgba8, MakeBlackWhite().arrRgba8);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Image decoder enforces dimensions before decoded allocation")
{
	std::vector<std::uint8_t> arrBytes = MakePng();
	arrBytes[16] = 0;
	arrBytes[17] = 0;
	arrBytes[18] = 0x20;
	arrBytes[19] = 0x01;
	const std::uint32_t nCrc = Crc32(arrBytes.data() + 12, 17);
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		arrBytes[29 + nByte] = static_cast<std::uint8_t>(nCrc >> ((3 - nByte) * 8));
	}
	DecodedImage stImage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(arrBytes, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("image_decode_dimensions"));
}

ENGINE_NEXT_TEST("Image decoder handles complete PNG and JPEG pixel payloads")
{
	DecodedImage stPng;
	DecodedImage stJpeg;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const std::vector<std::uint8_t> arrSource = MakePng();
#if defined(_WIN32)
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeImage(arrSource, "image/png", stPng, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stPng.nWidth, 2U);
	ENGINE_NEXT_CHECK_EQ(stPng.nHeight, 1U);
	ENGINE_NEXT_CHECK_EQ(stPng.arrRgba8, (std::vector<std::uint8_t>{ 255, 0, 0, 255, 0, 255, 0, 64 }));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeImage(MakeJpeg(), "image/jpeg", stJpeg, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stJpeg.nWidth, 1U);
	ENGINE_NEXT_CHECK_EQ(stJpeg.nHeight, 1U);
	ENGINE_NEXT_CHECK_EQ(stJpeg.arrRgba8.size(), 4ULL);
	if (stJpeg.arrRgba8.size() == 4)
	{
		ENGINE_NEXT_CHECK(stJpeg.arrRgba8[0] >= 237 && stJpeg.arrRgba8[0] <= 243);
		ENGINE_NEXT_CHECK(stJpeg.arrRgba8[1] >= 7 && stJpeg.arrRgba8[1] <= 13);
		ENGINE_NEXT_CHECK(stJpeg.arrRgba8[2] >= 17 && stJpeg.arrRgba8[2] <= 23);
		ENGINE_NEXT_CHECK_EQ(stJpeg.arrRgba8[3], 255);
	}
#else
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(MakePng(), "image/png", stPng, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("image_decode_platform"));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(MakeJpeg(), "image/jpeg", stJpeg, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("image_decode_platform"));
#endif
	ENGINE_NEXT_CHECK_EQ(arrSource, MakePng());
}

ENGINE_NEXT_TEST("Image decoder rejects damaged pixel payloads after structural validation")
{
	std::vector<std::uint8_t> arrBytes = MakePng();
	arrBytes.resize(33);
	AppendChunk(arrBytes, { 'I', 'D', 'A', 'T' }, { 0x78 });
	AppendChunk(arrBytes, { 'I', 'E', 'N', 'D' }, {});
	EngineNext::Assets::BlobInfo stInfo;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateBlob("image/png", arrBytes, stInfo, arrDiagnostics));
	DecodedImage stImage = MakeBlackWhite();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(arrBytes, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stImage.arrRgba8, MakeBlackWhite().arrRgba8);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Image decoder validates PNG inflated length filter and Adler checksum")
{
	std::vector<std::vector<std::uint8_t>> arrInvalidPngs;
	arrInvalidPngs.push_back(ReplacePngData({ 5, 255, 0, 0, 255, 0, 255, 0, 64 }));
	arrInvalidPngs.push_back(ReplacePngData({ 0, 255, 0, 0, 255, 0, 255, 0 }));
	arrInvalidPngs.push_back(ReplacePngData({ 0, 255, 0, 0, 255, 0, 255, 0, 64, 0 }));
	std::vector<std::uint8_t> arrBadChecksum = MakePng();
	arrBadChecksum[60] ^= 1;
	const std::uint32_t nCrc = Crc32(arrBadChecksum.data() + 37, 24);
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		arrBadChecksum[61 + nByte] = static_cast<std::uint8_t>(nCrc >> ((3 - nByte) * 8));
	}
	arrInvalidPngs.push_back(arrBadChecksum);
	for (const std::vector<std::uint8_t> &arrPng : arrInvalidPngs)
	{
		EngineNext::Assets::Diagnostics arrDiagnostics;
		EngineNext::Assets::BlobInfo stInfo;
		ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateBlob("image/png", arrPng, stInfo, arrDiagnostics));
		DecodedImage stImage = MakeBlackWhite();
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(arrPng, "image/png", stImage, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stImage.arrRgba8, MakeBlackWhite().arrRgba8);
	}
}

ENGINE_NEXT_TEST("Image decoder rejects trailing compressed bytes and accepts split IDAT")
{
	const std::vector<std::uint8_t> arrSource = MakePng();
	const std::vector<std::uint8_t> arrCompressed(arrSource.begin() + 41, arrSource.begin() + 61);
	std::vector<std::uint8_t> arrSplit(arrSource.begin(), arrSource.begin() + 33);
	AppendChunk(arrSplit, { 'I', 'D', 'A', 'T' }, std::vector<std::uint8_t>(arrCompressed.begin(), arrCompressed.begin() + 7));
	AppendChunk(arrSplit, { 'I', 'D', 'A', 'T' }, std::vector<std::uint8_t>(arrCompressed.begin() + 7, arrCompressed.end()));
	AppendChunk(arrSplit, { 'I', 'E', 'N', 'D' }, {});
	DecodedImage stImage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
#if defined(_WIN32)
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeImage(arrSplit, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stImage.arrRgba8, (std::vector<std::uint8_t>{ 255, 0, 0, 255, 0, 255, 0, 64 }));
#else
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(arrSplit, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("image_decode_platform"));
#endif
	std::vector<std::uint8_t> arrTrailing(arrSource.begin(), arrSource.begin() + 33);
	std::vector<std::uint8_t> arrExtra = arrCompressed;
	arrExtra.push_back(0);
	AppendChunk(arrTrailing, { 'I', 'D', 'A', 'T' }, arrExtra);
	AppendChunk(arrTrailing, { 'I', 'E', 'N', 'D' }, {});
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(arrTrailing, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("image_png_scanline"));
}

ENGINE_NEXT_TEST("Image decoder accepts PNG Adam7 scanline layout")
{
	const std::vector<std::uint8_t> arrPng = ReplacePngData({ 0, 255, 0, 0, 255, 0, 0, 255, 0, 64 }, true);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	DecodedImage stImage;
#if defined(_WIN32)
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeImage(arrPng, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stImage.arrRgba8, (std::vector<std::uint8_t>{ 255, 0, 0, 255, 0, 255, 0, 64 }));
#else
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(arrPng, "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("image_decode_platform"));
#endif
}

#if defined(_WIN32)
ENGINE_NEXT_TEST("Image decoder rejects truncated JPEG entropy even with an end marker")
{
	const std::vector<std::uint8_t> arrSource = MakeJpeg();
	std::size_t nEntropyStart = 0;
	for (std::size_t nOffset = 0; nOffset + 4 < arrSource.size(); ++nOffset)
	{
		if (arrSource[nOffset] == 0xFF && arrSource[nOffset + 1] == 0xDA)
		{
			nEntropyStart = nOffset + 2 + (static_cast<std::size_t>(arrSource[nOffset + 2]) << 8U) + arrSource[nOffset + 3];
			break;
		}
	}
	ENGINE_NEXT_CHECK(nEntropyStart > 0 && nEntropyStart + 2 < arrSource.size());
	for (std::size_t nLength = 1; nEntropyStart + nLength < arrSource.size() - 2; ++nLength)
	{
		std::vector<std::uint8_t> arrTruncated(arrSource.begin(), arrSource.begin() + static_cast<std::ptrdiff_t>(nEntropyStart + nLength));
		arrTruncated.push_back(0xFF);
		arrTruncated.push_back(0xD9);
		EngineNext::Assets::BlobInfo stInfo;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateBlob("image/jpeg", arrTruncated, stInfo, arrDiagnostics));
		DecodedImage stImage = MakeBlackWhite();
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeImage(arrTruncated, "image/jpeg", stImage, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(arrDiagnostics.back().strCode, std::string("image_jpeg_entropy"));
		ENGINE_NEXT_CHECK_EQ(stImage.arrRgba8, MakeBlackWhite().arrRgba8);
	}
}

ENGINE_NEXT_TEST("Image decoder preserves existing STA and MTA COM apartment ownership")
{
	const HRESULT nApartment = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
	ENGINE_NEXT_CHECK(SUCCEEDED(nApartment));
	DecodedImage stImage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeImage(MakePng(), "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(CoInitializeEx(nullptr, COINIT_MULTITHREADED), RPC_E_CHANGED_MODE);
	if (SUCCEEDED(nApartment))
	{
		CoUninitialize();
	}
	const HRESULT nMta = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
	ENGINE_NEXT_CHECK(SUCCEEDED(nMta));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeImage(MakePng(), "image/png", stImage, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED), RPC_E_CHANGED_MODE);
	if (SUCCEEDED(nMta))
	{
		CoUninitialize();
	}
	const HRESULT nFinalSta = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
	ENGINE_NEXT_CHECK_EQ(nFinalSta, S_OK);
	if (SUCCEEDED(nFinalSta))
	{
		CoUninitialize();
	}
}
#endif

ENGINE_NEXT_TEST("Mip generation filters sRGB in linear space and retains level zero")
{
	const DecodedImage stImage = MakeBlackWhite();
	std::vector<MipLevel> arrLinear;
	std::vector<MipLevel> arrSrgb;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildMipChain(stImage, ImageSemantic::Linear, arrLinear, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildMipChain(stImage, ImageSemantic::Srgb, arrSrgb, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrLinear.size(), 2ULL);
	ENGINE_NEXT_CHECK_EQ(arrSrgb.size(), 2ULL);
	ENGINE_NEXT_CHECK_EQ(arrSrgb[0].arrRgba8, stImage.arrRgba8);
	ENGINE_NEXT_CHECK_EQ(arrLinear[1].arrRgba8[0], 128);
	ENGINE_NEXT_CHECK_EQ(arrSrgb[1].arrRgba8[0], 188);
	ENGINE_NEXT_CHECK_EQ(arrSrgb[1].arrRgba8[3], 255);
}

ENGINE_NEXT_TEST("Mip generation includes odd edge texels and ends at one pixel")
{
	DecodedImage stImage;
	stImage.nWidth = 3;
	stImage.nHeight = 1;
	stImage.arrRgba8 = { 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255, 255 };
	std::vector<MipLevel> arrMips;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildMipChain(stImage, ImageSemantic::Linear, arrMips, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrMips.size(), 2ULL);
	ENGINE_NEXT_CHECK_EQ(arrMips.back().nWidth, 1U);
	ENGINE_NEXT_CHECK_EQ(arrMips.back().nHeight, 1U);
	ENGINE_NEXT_CHECK_EQ(arrMips.back().arrRgba8[0], 85);
}

ENGINE_NEXT_TEST("Mip generation normalizes normals and filters alpha without transparent color bleed")
{
	DecodedImage stNormal;
	stNormal.nWidth = 2;
	stNormal.nHeight = 1;
	stNormal.arrRgba8 = { 255, 128, 128, 255, 128, 255, 128, 255 };
	std::vector<MipLevel> arrMips;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildMipChain(stNormal, ImageSemantic::Normal, arrMips, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrMips[1].arrRgba8[0] >= 217 && arrMips[1].arrRgba8[0] <= 219);
	ENGINE_NEXT_CHECK(arrMips[1].arrRgba8[1] >= 217 && arrMips[1].arrRgba8[1] <= 219);
	DecodedImage stColor;
	stColor.nWidth = 2;
	stColor.nHeight = 1;
	stColor.arrRgba8 = { 255, 0, 0, 0, 0, 0, 255, 255 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildMipChain(stColor, ImageSemantic::Srgb, arrMips, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrMips[1].arrRgba8, (std::vector<std::uint8_t>{ 0, 0, 255, 128 }));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildMipChain(stColor, ImageSemantic::Linear, arrMips, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrMips[1].arrRgba8, (std::vector<std::uint8_t>{ 128, 0, 128, 128 }));
}

ENGINE_NEXT_TEST("Mip generation rejects inconsistent dimensions and unknown semantics transactionally")
{
	std::vector<MipLevel> arrMips{ MakeBlackWhite() };
	const std::vector<std::uint8_t> arrOriginal = arrMips[0].arrRgba8;
	DecodedImage stBad = MakeBlackWhite();
	stBad.arrRgba8.pop_back();
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildMipChain(stBad, ImageSemantic::Linear, arrMips, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildMipChain(MakeBlackWhite(), static_cast<ImageSemantic>(255), arrMips, arrDiagnostics));
	stBad.nWidth = 8193;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildMipChain(stBad, ImageSemantic::Linear, arrMips, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrMips.size(), 1ULL);
	ENGINE_NEXT_CHECK_EQ(arrMips[0].arrRgba8, arrOriginal);
}
