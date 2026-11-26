/**************************************************************************/
/*  ImageDecoder.cpp                                                      */
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

#include "engine_next/Rendering/Cook/ImageDecoder.h"

#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/thirdparty/zlib/zlib.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <memory>
#include <utility>

#if defined(_WIN32)
#include "engine_next/Rendering/Cook/JpegValidation.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <objbase.h>
#include <wincodec.h>
#endif

namespace EngineNext::Rendering
{
namespace
{

constexpr std::uint32_t MAX_IMAGE_DIMENSION = 8192;
constexpr std::uint64_t MAX_IMAGE_PIXELS = 67108864ULL;
constexpr std::size_t MAX_ENCODED_IMAGE_BYTES = 16ULL * 1024ULL * 1024ULL;

std::uint32_t ReadBigEndian(const std::vector<std::uint8_t> &arrBytes, std::size_t nOffset)
{
	return (static_cast<std::uint32_t>(arrBytes[nOffset]) << 24U) |
			(static_cast<std::uint32_t>(arrBytes[nOffset + 1]) << 16U) |
			(static_cast<std::uint32_t>(arrBytes[nOffset + 2]) << 8U) | arrBytes[nOffset + 3];
}

struct ScanlinePass
{
	std::uint32_t nRowBytes = 0;
	std::uint32_t nRows = 0;
};

class PngInflater final
{
public:
	PngInflater() : nResult(inflateInit(&stStream))
	{
	}

	~PngInflater()
	{
		if (nResult == Z_OK)
		{
			inflateEnd(&stStream);
		}
	}

	PngInflater(const PngInflater &) = delete;
	PngInflater &operator=(const PngInflater &) = delete;
	z_stream stStream{};
	int nResult;
};

std::uint8_t PngPredictor(std::uint8_t nFilter, int nLeft, int nUp, int nUpperLeft)
{
	switch (nFilter)
	{
		case 1:
			return static_cast<std::uint8_t>(nLeft);
		case 2:
			return static_cast<std::uint8_t>(nUp);
		case 3:
			return static_cast<std::uint8_t>((nLeft + nUp) / 2);
		case 4:
		{
			const int nEstimate = nLeft + nUp - nUpperLeft;
			const int nLeftDistance = std::abs(nEstimate - nLeft);
			const int nUpDistance = std::abs(nEstimate - nUp);
			const int nCornerDistance = std::abs(nEstimate - nUpperLeft);
			if (nLeftDistance <= nUpDistance && nLeftDistance <= nCornerDistance)
			{
				return static_cast<std::uint8_t>(nLeft);
			}
			return static_cast<std::uint8_t>(nUpDistance <= nCornerDistance ? nUp : nUpperLeft);
		}
		default:
			return 0;
	}
}

bool InflatePngData(const std::vector<std::uint8_t> &arrBytes, const Assets::BlobInfo &stInfo, std::vector<std::uint8_t> *pRgba8, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint8_t nBitDepth = arrBytes[24];
	const std::uint8_t nColorType = arrBytes[25];
	const std::uint32_t nChannels = nColorType == 0 || nColorType == 3 ? 1 : (nColorType == 2 ? 3 : (nColorType == 4 ? 2 : 4));
	const std::array<std::uint32_t, 7> arrStartX{ 0, 4, 0, 2, 0, 1, 0 };
	const std::array<std::uint32_t, 7> arrStartY{ 0, 0, 4, 0, 2, 0, 1 };
	const std::array<std::uint32_t, 7> arrStepX{ 8, 8, 4, 4, 2, 2, 1 };
	const std::array<std::uint32_t, 7> arrStepY{ 8, 8, 8, 4, 4, 2, 2 };
	std::vector<ScanlinePass> arrPasses;
	const bool bInterlaced = arrBytes[28] == 1;
	const std::size_t nPassCount = bInterlaced ? 7 : 1;
	for (std::size_t nPass = 0; nPass < nPassCount; ++nPass)
	{
		const std::uint32_t nStartX = bInterlaced ? arrStartX[nPass] : 0;
		const std::uint32_t nStartY = bInterlaced ? arrStartY[nPass] : 0;
		const std::uint32_t nStepX = bInterlaced ? arrStepX[nPass] : 1;
		const std::uint32_t nStepY = bInterlaced ? arrStepY[nPass] : 1;
		if (stInfo.nWidth > nStartX && stInfo.nHeight > nStartY)
		{
			const std::uint32_t nWidth = (stInfo.nWidth - nStartX + nStepX - 1) / nStepX;
			const std::uint32_t nHeight = (stInfo.nHeight - nStartY + nStepY - 1) / nStepY;
			arrPasses.push_back({ (nWidth * nChannels * nBitDepth + 7) / 8, nHeight });
		}
	}
	std::vector<std::uint8_t> arrCompressed;
	std::size_t nOffset = 8;
	while (nOffset + 12 <= arrBytes.size())
	{
		const std::uint32_t nLength = ReadBigEndian(arrBytes, nOffset);
		if (arrBytes[nOffset + 4] == 'I' && arrBytes[nOffset + 5] == 'D' && arrBytes[nOffset + 6] == 'A' && arrBytes[nOffset + 7] == 'T')
		{
			arrCompressed.insert(arrCompressed.end(), arrBytes.begin() + static_cast<std::ptrdiff_t>(nOffset + 8), arrBytes.begin() + static_cast<std::ptrdiff_t>(nOffset + 8 + nLength));
		}
		nOffset += nLength + 12;
	}
	PngInflater stInflater;
	if (stInflater.nResult != Z_OK)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_png_deflate", "$.IDAT", "PNG decompressor initialization failed.");
		return false;
	}
	stInflater.stStream.next_in = arrCompressed.data();
	stInflater.stStream.avail_in = static_cast<uInt>(arrCompressed.size());
	std::array<std::uint8_t, 65536> arrOutput;
	std::size_t nPass = 0;
	std::uint32_t nRow = 0;
	std::uint32_t nRowOffset = 0;
	std::uint8_t nFilter = 0;
	int nResult = Z_OK;
	while (nResult != Z_STREAM_END)
	{
		stInflater.stStream.next_out = arrOutput.data();
		stInflater.stStream.avail_out = static_cast<uInt>(arrOutput.size());
		nResult = inflate(&stInflater.stStream, Z_NO_FLUSH);
		if (nResult != Z_OK && nResult != Z_STREAM_END)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "image_png_deflate", "$.IDAT", "PNG compressed stream or checksum is invalid.");
			return false;
		}
		const std::size_t nProduced = arrOutput.size() - stInflater.stStream.avail_out;
		for (std::size_t nByte = 0; nByte < nProduced; ++nByte)
		{
			if (nPass >= arrPasses.size() || (nRowOffset == 0 && arrOutput[nByte] > 4))
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "image_png_scanline", "$.IDAT", "PNG scanline length or filter is invalid.");
				return false;
			}
			if (pRgba8 != nullptr)
			{
				if (nRowOffset == 0)
				{
					nFilter = arrOutput[nByte];
				}
				else
				{
					const std::size_t nPosition = pRgba8->size();
					const std::size_t nStride = arrPasses[nPass].nRowBytes;
					const bool bHasLeft = nRowOffset > 4;
					const int nLeft = bHasLeft ? (*pRgba8)[nPosition - 4] : 0;
					const int nUp = nRow > 0 ? (*pRgba8)[nPosition - nStride] : 0;
					const int nUpperLeft = bHasLeft && nRow > 0 ? (*pRgba8)[nPosition - nStride - 4] : 0;
					pRgba8->push_back(static_cast<std::uint8_t>(arrOutput[nByte] + PngPredictor(nFilter, nLeft, nUp, nUpperLeft)));
				}
			}
			++nRowOffset;
			if (nRowOffset == arrPasses[nPass].nRowBytes + 1)
			{
				nRowOffset = 0;
				++nRow;
				if (nRow == arrPasses[nPass].nRows)
				{
					++nPass;
					nRow = 0;
				}
			}
		}
		if (nResult == Z_OK && nProduced == 0 && stInflater.stStream.avail_in == 0)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "image_png_deflate", "$.IDAT", "PNG compressed stream is truncated.");
			return false;
		}
	}
	if (nPass != arrPasses.size() || nRowOffset != 0 || stInflater.stStream.avail_in != 0)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_png_scanline", "$.IDAT", "PNG data does not contain exactly the declared scanlines.");
		return false;
	}
	return true;
}

bool CheckDimensions(std::uint32_t nWidth, std::uint32_t nHeight, Assets::Diagnostics &out_arrDiagnostics)
{
	if (nWidth == 0 || nHeight == 0 || nWidth > MAX_IMAGE_DIMENSION || nHeight > MAX_IMAGE_DIMENSION || static_cast<std::uint64_t>(nWidth) * nHeight > MAX_IMAGE_PIXELS)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_dimensions", "$", "Image dimensions exceed the GPU Cook limits.");
		return false;
	}
	return true;
}

double DecodeSrgb(double dValue)
{
	return dValue <= 0.04045 ? dValue / 12.92 : std::pow((dValue + 0.055) / 1.055, 2.4);
}

double EncodeSrgb(double dValue)
{
	return dValue <= 0.0031308 ? 12.92 * dValue : 1.055 * std::pow(dValue, 1.0 / 2.4) - 0.055;
}

std::uint8_t EncodeByte(double dValue)
{
	return static_cast<std::uint8_t>(std::clamp(std::lround(dValue * 255.0), 0L, 255L));
}

void FilterTexel(const MipLevel &stSource, MipLevel &out_stDestination, std::uint32_t nX, std::uint32_t nY, ImageSemantic eSemantic)
{
	const double dLeft = static_cast<double>(nX) * stSource.nWidth / out_stDestination.nWidth;
	const double dRight = static_cast<double>(nX + 1) * stSource.nWidth / out_stDestination.nWidth;
	const double dTop = static_cast<double>(nY) * stSource.nHeight / out_stDestination.nHeight;
	const double dBottom = static_cast<double>(nY + 1) * stSource.nHeight / out_stDestination.nHeight;
	std::array<double, 4> arrSum{};
	double dTotalWeight = 0.0;
	for (std::uint32_t nSourceY = static_cast<std::uint32_t>(dTop); nSourceY < static_cast<std::uint32_t>(std::ceil(dBottom)); ++nSourceY)
	{
		const double dWeightY = std::min(dBottom, static_cast<double>(nSourceY + 1)) - std::max(dTop, static_cast<double>(nSourceY));
		for (std::uint32_t nSourceX = static_cast<std::uint32_t>(dLeft); nSourceX < static_cast<std::uint32_t>(std::ceil(dRight)); ++nSourceX)
		{
			const double dWeightX = std::min(dRight, static_cast<double>(nSourceX + 1)) - std::max(dLeft, static_cast<double>(nSourceX));
			const double dWeight = dWeightX * dWeightY;
			const std::size_t nOffset = (static_cast<std::size_t>(nSourceY) * stSource.nWidth + nSourceX) * 4;
			const double dAlpha = stSource.arrRgba8[nOffset + 3] / 255.0;
			for (std::size_t nChannel = 0; nChannel < arrSum.size(); ++nChannel)
			{
				double dValue = stSource.arrRgba8[nOffset + nChannel] / 255.0;
				if (nChannel < 3 && eSemantic == ImageSemantic::Srgb)
				{
					dValue = DecodeSrgb(dValue);
				}
				else if (nChannel < 3 && eSemantic == ImageSemantic::Normal)
				{
					dValue = dValue * 2.0 - 1.0;
				}
				if (nChannel < 3 && eSemantic == ImageSemantic::Srgb)
				{
					dValue *= dAlpha;
				}
				arrSum[nChannel] += dValue * dWeight;
			}
			dTotalWeight += dWeight;
		}
	}
	for (double &dChannel : arrSum)
	{
		dChannel /= dTotalWeight;
	}
	if (eSemantic == ImageSemantic::Normal)
	{
		const double dLength = std::sqrt(arrSum[0] * arrSum[0] + arrSum[1] * arrSum[1] + arrSum[2] * arrSum[2]);
		if (dLength <= 1.0 / 255.0)
		{
			arrSum[0] = 0.0;
			arrSum[1] = 0.0;
			arrSum[2] = 1.0;
		}
		else
		{
			for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
			{
				arrSum[nChannel] /= dLength;
			}
		}
	}
	else if (eSemantic == ImageSemantic::Srgb && arrSum[3] > 0.0)
	{
		for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
		{
			arrSum[nChannel] /= arrSum[3];
		}
	}
	const std::size_t nDestination = (static_cast<std::size_t>(nY) * out_stDestination.nWidth + nX) * 4;
	for (std::size_t nChannel = 0; nChannel < arrSum.size(); ++nChannel)
	{
		double dValue = arrSum[nChannel];
		if (nChannel < 3 && eSemantic == ImageSemantic::Srgb)
		{
			dValue = EncodeSrgb(dValue);
		}
		else if (nChannel < 3 && eSemantic == ImageSemantic::Normal)
		{
			dValue = (dValue + 1.0) * 0.5;
		}
		out_stDestination.arrRgba8[nDestination + nChannel] = EncodeByte(dValue);
	}
}

#if defined(_WIN32)
class ComApartment final
{
public:
	ComApartment() noexcept : nResult(CoInitializeEx(nullptr, COINIT_MULTITHREADED))
	{
	}

	~ComApartment()
	{
		if (SUCCEEDED(nResult))
		{
			CoUninitialize();
		}
	}

	ComApartment(const ComApartment &) = delete;
	ComApartment &operator=(const ComApartment &) = delete;

	[[nodiscard]] HRESULT GetResult() const noexcept
	{
		return nResult;
	}

private:
	HRESULT nResult;
};

template <typename Interface>
struct ReleaseCom
{
	void operator()(Interface *pValue) const noexcept
	{
		if (pValue != nullptr)
		{
			pValue->Release();
		}
	}
};

template <typename Interface>
using OwnedCom = std::unique_ptr<Interface, ReleaseCom<Interface>>;

bool ReportWicFailure(const char *pOperation, HRESULT nResult, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_wic", "$", std::string(pOperation) + " failed, HRESULT=" + std::to_string(static_cast<std::int32_t>(nResult)));
	return false;
}

bool DecodeWic(const std::vector<std::uint8_t> &arrEncoded, const std::string &strMediaType, const Assets::BlobInfo &stInfo, DecodedImage &out_stImage, Assets::Diagnostics &out_arrDiagnostics)
{
	ComApartment stApartment;
	const HRESULT nApartmentResult = stApartment.GetResult();
	if (FAILED(nApartmentResult) && nApartmentResult != RPC_E_CHANGED_MODE)
	{
		return ReportWicFailure("CoInitializeEx", nApartmentResult, out_arrDiagnostics);
	}
	IWICImagingFactory *pFactory = nullptr;
	HRESULT nResult = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&pFactory));
	OwnedCom<IWICImagingFactory> ptrFactory(pFactory);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC factory", nResult, out_arrDiagnostics);
	}
	// WIC's memory stream accepts mutable storage and borrows it. Keep an owned
	// copy alive until the decoder and stream are both released.
	std::vector<std::uint8_t> arrStreamBytes = arrEncoded;
	IWICStream *pStream = nullptr;
	nResult = ptrFactory->CreateStream(&pStream);
	OwnedCom<IWICStream> ptrStream(pStream);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC stream", nResult, out_arrDiagnostics);
	}
	nResult = ptrStream->InitializeFromMemory(arrStreamBytes.data(), static_cast<DWORD>(arrStreamBytes.size()));
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC stream memory", nResult, out_arrDiagnostics);
	}
	const GUID &stContainer = strMediaType == "image/png" ? GUID_ContainerFormatPng : GUID_ContainerFormatJpeg;
	IWICBitmapDecoder *pDecoder = nullptr;
	nResult = ptrFactory->CreateDecoder(stContainer, &GUID_VendorMicrosoft, &pDecoder);
	OwnedCom<IWICBitmapDecoder> ptrDecoder(pDecoder);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC built-in decoder", nResult, out_arrDiagnostics);
	}
	nResult = ptrDecoder->Initialize(ptrStream.get(), WICDecodeMetadataCacheOnDemand);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC decoder initialize", nResult, out_arrDiagnostics);
	}
	UINT nFrameCount = 0;
	nResult = ptrDecoder->GetFrameCount(&nFrameCount);
	if (FAILED(nResult) || nFrameCount != 1)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_frames", "$", "GPU Cook requires exactly one decoded image frame.");
		return false;
	}
	IWICBitmapFrameDecode *pFrame = nullptr;
	nResult = ptrDecoder->GetFrame(0, &pFrame);
	OwnedCom<IWICBitmapFrameDecode> ptrFrame(pFrame);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC image frame", nResult, out_arrDiagnostics);
	}
	UINT nWidth = 0;
	UINT nHeight = 0;
	nResult = ptrFrame->GetSize(&nWidth, &nHeight);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC image dimensions", nResult, out_arrDiagnostics);
	}
	if (!CheckDimensions(nWidth, nHeight, out_arrDiagnostics))
	{
		return false;
	}
	if (nWidth != stInfo.nWidth || nHeight != stInfo.nHeight)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_dimensions", "$", "Decoded dimensions disagree with the validated asset header.");
		return false;
	}
	IWICFormatConverter *pConverter = nullptr;
	nResult = ptrFactory->CreateFormatConverter(&pConverter);
	OwnedCom<IWICFormatConverter> ptrConverter(pConverter);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC pixel converter", nResult, out_arrDiagnostics);
	}
	nResult = ptrConverter->Initialize(ptrFrame.get(), GUID_WICPixelFormat32bppRGBA, WICBitmapDitherTypeNone, nullptr, 0.0, WICBitmapPaletteTypeCustom);
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC RGBA8 conversion", nResult, out_arrDiagnostics);
	}
	DecodedImage stDecoded;
	stDecoded.nWidth = nWidth;
	stDecoded.nHeight = nHeight;
	const std::uint64_t nByteCount = static_cast<std::uint64_t>(nWidth) * nHeight * 4;
	if (nByteCount > std::numeric_limits<UINT>::max() || nByteCount > std::numeric_limits<std::size_t>::max())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_size", "$", "Decoded pixel storage exceeds the platform limits.");
		return false;
	}
	stDecoded.arrRgba8.resize(static_cast<std::size_t>(nByteCount));
	nResult = ptrConverter->CopyPixels(nullptr, nWidth * 4, static_cast<UINT>(nByteCount), stDecoded.arrRgba8.data());
	if (FAILED(nResult))
	{
		return ReportWicFailure("WIC pixel decode", nResult, out_arrDiagnostics);
	}
	out_stImage = std::move(stDecoded);
	return true;
}
#endif

} // namespace

bool DecodeImage(const std::vector<std::uint8_t> &arrEncoded, const std::string &strMediaType, DecodedImage &out_stImage, Assets::Diagnostics &out_arrDiagnostics)
{
	if (strMediaType != "image/png" && strMediaType != "image/jpeg")
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_media", "$", "GPU Cook only decodes PNG and JPEG image assets.");
		return false;
	}
	if (arrEncoded.empty() || arrEncoded.size() > MAX_ENCODED_IMAGE_BYTES)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_size", "$", "Image input is empty or exceeds 16 MiB.");
		return false;
	}
	Assets::BlobInfo stInfo;
	if (!Assets::ValidateBlob(strMediaType, arrEncoded, stInfo, out_arrDiagnostics) || !CheckDimensions(stInfo.nWidth, stInfo.nHeight, out_arrDiagnostics))
	{
		return false;
	}
	if (strMediaType == "image/png")
	{
		const bool bRgba8 = arrEncoded[24] == 8 && arrEncoded[25] == 6 && arrEncoded[28] == 0;
		DecodedImage stCandidate;
		if (!InflatePngData(arrEncoded, stInfo, bRgba8 ? &stCandidate.arrRgba8 : nullptr, out_arrDiagnostics))
		{
			return false;
		}
		if (bRgba8)
		{
			stCandidate.nWidth = stInfo.nWidth;
			stCandidate.nHeight = stInfo.nHeight;
			out_stImage = std::move(stCandidate);
			return true;
		}
	}
#if defined(_WIN32)
	if (strMediaType == "image/jpeg")
	{
		std::array<char, 256> arrMessage{};
		if (EngineNextValidateJpeg(arrEncoded.data(), arrEncoded.size(), stInfo.nWidth, stInfo.nHeight, arrMessage.data(), arrMessage.size()) == 0)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "image_jpeg_entropy", "$", arrMessage.data());
			return false;
		}
	}
	return DecodeWic(arrEncoded, strMediaType, stInfo, out_stImage, out_arrDiagnostics);
#else
	Assets::AddDiagnostic(out_arrDiagnostics, "image_decode_platform", "$", "This PNG layout or JPEG requires Windows WIC. Portable decoding supports non-interlaced 8-bit RGBA PNG.");
	return false;
#endif
}

bool BuildMipChain(const DecodedImage &stImage, ImageSemantic eSemantic, std::vector<MipLevel> &out_arrLevels, Assets::Diagnostics &out_arrDiagnostics)
{
	if (eSemantic != ImageSemantic::Linear && eSemantic != ImageSemantic::Srgb && eSemantic != ImageSemantic::Normal)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_mip_semantic", "$", "Unknown mip filtering semantic.");
		return false;
	}
	if (!CheckDimensions(stImage.nWidth, stImage.nHeight, out_arrDiagnostics))
	{
		return false;
	}
	const std::uint64_t nExpectedBytes = static_cast<std::uint64_t>(stImage.nWidth) * stImage.nHeight * 4;
	if (nExpectedBytes != stImage.arrRgba8.size())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "image_mip_size", "$", "RGBA8 storage must match the exact image dimensions.");
		return false;
	}
	std::vector<MipLevel> arrLevels;
	arrLevels.push_back(stImage);
	while (arrLevels.back().nWidth > 1 || arrLevels.back().nHeight > 1)
	{
		const MipLevel &stSource = arrLevels.back();
		MipLevel stNext;
		stNext.nWidth = std::max(stSource.nWidth / 2, 1U);
		stNext.nHeight = std::max(stSource.nHeight / 2, 1U);
		stNext.arrRgba8.resize(static_cast<std::size_t>(stNext.nWidth) * stNext.nHeight * 4);
		for (std::uint32_t nY = 0; nY < stNext.nHeight; ++nY)
		{
			for (std::uint32_t nX = 0; nX < stNext.nWidth; ++nX)
			{
				FilterTexel(stSource, stNext, nX, nY, eSemantic);
			}
		}
		arrLevels.push_back(std::move(stNext));
	}
	out_arrLevels = std::move(arrLevels);
	return true;
}

} // namespace EngineNext::Rendering
