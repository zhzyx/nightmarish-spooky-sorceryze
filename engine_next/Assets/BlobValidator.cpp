/**************************************************************************/
/*  BlobValidator.cpp                                                     */
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

#include "engine_next/include/EngineNext/Assets/BlobValidator.h"

#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <cstddef>
#include <limits>
#include <string>

namespace EngineNext::Assets
{
namespace
{

constexpr std::size_t MAX_IMAGE_BYTES = 16ULL * 1024ULL * 1024ULL;
constexpr std::size_t MAX_GLB_BYTES = 64ULL * 1024ULL * 1024ULL;
constexpr std::uint64_t MAX_PIXELS = 67108864ULL;
constexpr std::uint64_t MAX_VERTICES = 1000000ULL;
constexpr std::uint64_t MAX_TRIANGLES = 2000000ULL;

std::uint32_t Read32BE(const std::vector<std::uint8_t> &in_arrBytes, std::size_t in_nOffset)
{
	return (static_cast<std::uint32_t>(in_arrBytes[in_nOffset]) << 24U) |
			(static_cast<std::uint32_t>(in_arrBytes[in_nOffset + 1]) << 16U) |
			(static_cast<std::uint32_t>(in_arrBytes[in_nOffset + 2]) << 8U) | in_arrBytes[in_nOffset + 3];
}

std::uint32_t Read32LE(const std::uint8_t *in_pData)
{
	return static_cast<std::uint32_t>(in_pData[0]) | (static_cast<std::uint32_t>(in_pData[1]) << 8U) |
			(static_cast<std::uint32_t>(in_pData[2]) << 16U) | (static_cast<std::uint32_t>(in_pData[3]) << 24U);
}

std::uint32_t Crc32(const std::uint8_t *in_pData, std::size_t in_nBytes)
{
	std::uint32_t nCrc = 0xFFFFFFFFU;
	for (std::size_t nIndex = 0; nIndex < in_nBytes; ++nIndex)
	{
		nCrc ^= in_pData[nIndex];
		for (int nBit = 0; nBit < 8; ++nBit)
		{
			nCrc = (nCrc >> 1U) ^ (0xEDB88320U & (0U - (nCrc & 1U)));
		}
	}
	return nCrc ^ 0xFFFFFFFFU;
}

bool ValidDimensions(std::uint32_t in_nWidth, std::uint32_t in_nHeight, Diagnostics &out_arrDiagnostics)
{
	if (in_nWidth == 0 || in_nHeight == 0 || in_nWidth > 16384 || in_nHeight > 16384 ||
		static_cast<std::uint64_t>(in_nWidth) * in_nHeight > MAX_PIXELS)
	{
		AddDiagnostic(out_arrDiagnostics, "image_dimensions", "$", "invalid dimensions or pixel budget");
		return false;
	}
	return true;
}

bool ValidatePng(const std::vector<std::uint8_t> &in_arrBytes, BlobInfo &out_stInfo, Diagnostics &out_arrDiagnostics)
{
	static const std::uint8_t arrSignature[] = { 0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n' };
	if (in_arrBytes.size() < 45 || in_arrBytes.size() > MAX_IMAGE_BYTES)
	{
		AddDiagnostic(out_arrDiagnostics, "png_budget", "$", "PNG is too small or exceeds budget");
		return false;
	}
	for (std::size_t nIndex = 0; nIndex < 8; ++nIndex)
	{
		if (in_arrBytes[nIndex] != arrSignature[nIndex])
		{
			AddDiagnostic(out_arrDiagnostics, "png_signature", "$", "invalid PNG signature");
			return false;
		}
	}
	std::size_t nOffset = 8;
	bool bHeader = false;
	bool bPalette = false;
	std::uint8_t nColorType = 0;
	bool bData = false;
	bool bDataEnded = false;
	bool bEnded = false;
	while (nOffset + 12 <= in_arrBytes.size())
	{
		const std::uint32_t nLength = Read32BE(in_arrBytes, nOffset);
		if (nLength > in_arrBytes.size() - nOffset - 12)
		{
			AddDiagnostic(out_arrDiagnostics, "png_chunk_bounds", "$", "truncated PNG chunk");
			return false;
		}
		const std::size_t nType = nOffset + 4;
		const std::string strType(reinterpret_cast<const char *>(in_arrBytes.data() + nType), 4);
		if (nOffset == 8 && strType != "IHDR")
		{
			AddDiagnostic(out_arrDiagnostics, "png_header", "$", "IHDR must be first");
			return false;
		}
		if (strType == "IHDR")
		{
			if (nLength != 13 || nOffset != 8)
			{
				AddDiagnostic(out_arrDiagnostics, "png_header", "$.IHDR", "invalid IHDR length or position");
				return false;
			}
			const std::uint8_t nDepth = in_arrBytes[nOffset + 16];
			const std::uint8_t nColor = in_arrBytes[nOffset + 17];
			const bool bDepthColor = (nColor == 0 && (nDepth == 1 || nDepth == 2 || nDepth == 4 || nDepth == 8 || nDepth == 16)) ||
					(nColor == 2 && (nDepth == 8 || nDepth == 16)) ||
					(nColor == 3 && nDepth != 0 && nDepth <= 8 && (nDepth & (nDepth - 1)) == 0) ||
					((nColor == 4 || nColor == 6) && (nDepth == 8 || nDepth == 16));
			if (!bDepthColor || in_arrBytes[nOffset + 18] != 0 || in_arrBytes[nOffset + 19] != 0 || in_arrBytes[nOffset + 20] > 1)
			{
				AddDiagnostic(out_arrDiagnostics, "png_header", "$.IHDR", "invalid IHDR fields or depth/color combination");
				return false;
			}
			nColorType = nColor;
			out_stInfo.nWidth = Read32BE(in_arrBytes, nOffset + 8);
			out_stInfo.nHeight = Read32BE(in_arrBytes, nOffset + 12);
			bHeader = ValidDimensions(out_stInfo.nWidth, out_stInfo.nHeight, out_arrDiagnostics);
		}
		else if (strType == "PLTE")
		{
			if (!bHeader || bData || bPalette)
			{
				AddDiagnostic(out_arrDiagnostics, "png_order", "$.PLTE", "PLTE must precede IDAT and occur once");
				return false;
			}
			bPalette = true;
		}
		else if (strType == "IDAT")
		{
			if (!bHeader || bDataEnded || (nColorType == 3 && !bPalette))
			{
				AddDiagnostic(out_arrDiagnostics, "png_order", "$.IDAT", "IDAT must follow IHDR and remain consecutive");
				return false;
			}
			bData = true;
		}
		else if (strType == "IEND")
		{
			if (nLength != 0 || nOffset + 12 != in_arrBytes.size() || !bData)
			{
				AddDiagnostic(out_arrDiagnostics, "png_end", "$.IEND", "invalid IEND, missing IDAT or trailing bytes");
				return false;
			}
			bEnded = true;
		}
		else
		{
			bDataEnded = bDataEnded || bData;
			if ((in_arrBytes[nType] & 0x20U) == 0)
			{
				AddDiagnostic(out_arrDiagnostics, "png_critical_chunk", "$." + strType, "unknown critical chunk");
				return false;
			}
		}
		const std::uint32_t nExpected = Read32BE(in_arrBytes, nOffset + 8 + nLength);
		const std::uint32_t nActual = Crc32(in_arrBytes.data() + nType, nLength + 4);
		if (nExpected != nActual)
		{
			AddDiagnostic(out_arrDiagnostics, "png_crc", "$." + strType, "CRC mismatch");
			return false;
		}
		nOffset += nLength + 12;
		if (bEnded)
		{
			break;
		}
	}
	if (!bHeader || !bData || !bEnded || nOffset != in_arrBytes.size())
	{
		AddDiagnostic(out_arrDiagnostics, "png_structure", "$", "PNG requires valid IHDR, IDAT and IEND");
		return false;
	}
	return true;
}

bool ValidateJpeg(const std::vector<std::uint8_t> &in_arrBytes, BlobInfo &out_stInfo, Diagnostics &out_arrDiagnostics)
{
	if (in_arrBytes.size() < 4 || in_arrBytes.size() > MAX_IMAGE_BYTES || in_arrBytes[0] != 0xFF || in_arrBytes[1] != 0xD8)
	{
		AddDiagnostic(out_arrDiagnostics, "jpeg_signature", "$", "invalid JPEG signature or budget");
		return false;
	}
	std::size_t nOffset = 2;
	bool bFrame = false;
	bool bScan = false;
	bool bEntropy = false;
	while (nOffset < in_arrBytes.size())
	{
		if (in_arrBytes[nOffset++] != 0xFF)
		{
			AddDiagnostic(out_arrDiagnostics, "jpeg_marker", "$", "expected JPEG marker");
			return false;
		}
		while (nOffset < in_arrBytes.size() && in_arrBytes[nOffset] == 0xFF)
		{
			++nOffset;
		}
		if (nOffset >= in_arrBytes.size())
		{
			break;
		}
		const std::uint8_t nMarker = in_arrBytes[nOffset++];
		if (nMarker == 0xD9)
		{
			if (!bFrame || !bScan || !bEntropy || nOffset != in_arrBytes.size())
			{
				AddDiagnostic(out_arrDiagnostics, "jpeg_end", "$", "invalid EOI or trailing bytes");
				return false;
			}
			return true;
		}
		if (nMarker == 0x01 || (nMarker >= 0xD0 && nMarker <= 0xD7))
		{
			continue;
		}
		if (nOffset + 2 > in_arrBytes.size())
		{
			break;
		}
		const std::uint16_t nLength = static_cast<std::uint16_t>((in_arrBytes[nOffset] << 8U) | in_arrBytes[nOffset + 1]);
		if (nLength < 2 || (nMarker == 0xDA && nLength < 8) || nOffset + nLength > in_arrBytes.size())
		{
			AddDiagnostic(out_arrDiagnostics, "jpeg_segment", "$", "invalid JPEG segment length");
			return false;
		}
		const bool bStartFrame = (nMarker >= 0xC0 && nMarker <= 0xC3) || (nMarker >= 0xC5 && nMarker <= 0xC7) ||
				(nMarker >= 0xC9 && nMarker <= 0xCB) || (nMarker >= 0xCD && nMarker <= 0xCF);
		if (bStartFrame)
		{
			if (nLength < 8)
			{
				AddDiagnostic(out_arrDiagnostics, "jpeg_frame", "$", "short JPEG frame");
				return false;
			}
			out_stInfo.nHeight = static_cast<std::uint32_t>((in_arrBytes[nOffset + 3] << 8U) | in_arrBytes[nOffset + 4]);
			out_stInfo.nWidth = static_cast<std::uint32_t>((in_arrBytes[nOffset + 5] << 8U) | in_arrBytes[nOffset + 6]);
			bFrame = ValidDimensions(out_stInfo.nWidth, out_stInfo.nHeight, out_arrDiagnostics);
		}
		nOffset += nLength;
		if (nMarker == 0xDA)
		{
			const std::uint8_t nComponents = in_arrBytes[nOffset - nLength + 2];
			if (nComponents == 0 || nLength != 6 + 2 * nComponents)
			{
				AddDiagnostic(out_arrDiagnostics, "jpeg_sos", "$", "invalid SOS component table or length");
				return false;
			}
			const std::size_t nSpectral = nOffset;
			if (in_arrBytes[nSpectral - 3] > 63 || in_arrBytes[nSpectral - 3] > in_arrBytes[nSpectral - 2] ||
				in_arrBytes[nSpectral - 2] > 63 || (in_arrBytes[nSpectral - 1] >> 4U) > 13 || (in_arrBytes[nSpectral - 1] & 0x0FU) > 13)
			{
				AddDiagnostic(out_arrDiagnostics, "jpeg_sos", "$", "invalid spectral or approximation parameters");
				return false;
			}
			bScan = true;
			bEntropy = false;
			while (nOffset + 1 < in_arrBytes.size())
			{
				if (in_arrBytes[nOffset] != 0xFF)
				{
					++nOffset;
					bEntropy = true;
					continue;
				}
				const std::uint8_t nNext = in_arrBytes[nOffset + 1];
				if (nNext == 0x00 || (nNext >= 0xD0 && nNext <= 0xD7) || nNext == 0xFF)
				{
					bEntropy = bEntropy || nNext == 0x00;
					nOffset += 2;
					continue;
				}
				break;
			}
		}
	}
	AddDiagnostic(out_arrDiagnostics, "jpeg_structure", "$", "JPEG requires a frame, scan and EOI");
	return false;
}

bool HasExternalUri(const Serialization::JsonValue &in_stValue)
{
	if (const Serialization::JsonValue::Object *pObject = in_stValue.GetObject())
	{
		for (const std::pair<const std::string, Serialization::JsonValue> &stEntry : *pObject)
		{
			if (stEntry.first == "uri" || HasExternalUri(stEntry.second))
			{
				return true;
			}
		}
	}
	if (const Serialization::JsonValue::List *pList = in_stValue.GetList())
	{
		for (const Serialization::JsonValue &stItem : *pList)
		{
			if (HasExternalUri(stItem))
			{
				return true;
			}
		}
	}
	return false;
}

const Serialization::JsonValue::List *MemberList(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapObject.find(in_strName);
	return it == in_mapObject.end() ? nullptr : it->second.GetList();
}

bool JsonInteger(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName, std::int64_t in_nDefault, std::int64_t &out_nValue)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapObject.find(in_strName);
	out_nValue = in_nDefault;
	return it == in_mapObject.end() || it->second.GetInteger(out_nValue);
}

bool JsonString(const Serialization::JsonValue::Object &in_mapObject, const std::string &in_strName, std::string &out_strValue)
{
	const Serialization::JsonValue::Object::const_iterator it = in_mapObject.find(in_strName);
	const std::string *pValue = it == in_mapObject.end() ? nullptr : it->second.GetString();
	if (pValue == nullptr)
	{
		return false;
	}
	out_strValue = *pValue;
	return true;
}

std::uint64_t ComponentBytes(std::int64_t in_nType)
{
	if (in_nType == 5120 || in_nType == 5121)
	{
		return 1;
	}
	if (in_nType == 5122 || in_nType == 5123)
	{
		return 2;
	}
	if (in_nType == 5125 || in_nType == 5126)
	{
		return 4;
	}
	return 0;
}

std::uint64_t ComponentCount(const std::string &in_strType)
{
	if (in_strType == "SCALAR")
	{
		return 1;
	}
	if (in_strType == "VEC2")
	{
		return 2;
	}
	if (in_strType == "VEC3")
	{
		return 3;
	}
	if (in_strType == "VEC4")
	{
		return 4;
	}
	if (in_strType == "MAT2")
	{
		return 4;
	}
	if (in_strType == "MAT3")
	{
		return 9;
	}
	if (in_strType == "MAT4")
	{
		return 16;
	}
	return 0;
}

struct ViewLayout
{
	std::uint64_t nOffset = 0;
	std::uint64_t nLength = 0;
	std::uint64_t nStride = 0;
};

struct AccessorLayout
{
	std::uint64_t nView = 0;
	std::uint64_t nOffset = 0;
	std::uint64_t nCount = 0;
	std::uint64_t nElementBytes = 0;
	std::int64_t nComponentType = 0;
	std::string strType;
};

bool ValidateAccessorGeometry(const Serialization::JsonValue::Object &in_mapRoot, const std::vector<std::uint8_t> &in_arrBytes, std::size_t in_nBinaryOffset, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::List *pBuffers = MemberList(in_mapRoot, "buffers");
	const Serialization::JsonValue::List *pViews = MemberList(in_mapRoot, "bufferViews");
	const Serialization::JsonValue::List *pAccessors = MemberList(in_mapRoot, "accessors");
	const Serialization::JsonValue::List *pMeshes = MemberList(in_mapRoot, "meshes");
	if (pBuffers == nullptr || pViews == nullptr || pAccessors == nullptr || pMeshes == nullptr)
	{
		return false;
	}
	const std::uint64_t nBinaryBytes = in_arrBytes.size() - in_nBinaryOffset;
	std::uint64_t nDeclaredBytes = 0;
	if (pBuffers->size() != 1)
	{
		AddDiagnostic(out_arrDiagnostics, "glb_buffer", "$.buffers", "exactly one internal buffer is required");
		return false;
	}
	for (const Serialization::JsonValue &stValue : *pBuffers)
	{
		const Serialization::JsonValue::Object *pBuffer = stValue.GetObject();
		std::int64_t nLength = -1;
		if (pBuffer == nullptr || !JsonInteger(*pBuffer, "byteLength", -1, nLength) || nLength < 0 || static_cast<std::uint64_t>(nLength) > nBinaryBytes)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_buffer", "$.buffers", "buffer exceeds BIN chunk");
			return false;
		}
		nDeclaredBytes = static_cast<std::uint64_t>(nLength);
	}
	std::vector<ViewLayout> arrViews;
	for (const Serialization::JsonValue &stValue : *pViews)
	{
		const Serialization::JsonValue::Object *pView = stValue.GetObject();
		std::int64_t nBuffer = -1;
		std::int64_t nOffset = 0;
		std::int64_t nLength = -1;
		std::int64_t nStride = 0;
		if (pView == nullptr || !JsonInteger(*pView, "buffer", -1, nBuffer) || nBuffer != 0 ||
			!JsonInteger(*pView, "byteOffset", 0, nOffset) || !JsonInteger(*pView, "byteLength", -1, nLength) ||
			!JsonInteger(*pView, "byteStride", 0, nStride) || nOffset < 0 || nLength < 0 || nStride < 0 ||
			nOffset % 4 != 0 || nStride % 4 != 0 || static_cast<std::uint64_t>(nOffset) + static_cast<std::uint64_t>(nLength) > nBinaryBytes ||
			static_cast<std::uint64_t>(nOffset) + static_cast<std::uint64_t>(nLength) > nDeclaredBytes)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_view_alignment", "$.bufferViews", "invalid bufferView range or alignment");
			return false;
		}
		arrViews.push_back(ViewLayout{ static_cast<std::uint64_t>(nOffset), static_cast<std::uint64_t>(nLength), static_cast<std::uint64_t>(nStride) });
	}
	std::vector<AccessorLayout> arrAccessors;
	for (const Serialization::JsonValue &stValue : *pAccessors)
	{
		const Serialization::JsonValue::Object *pAccessor = stValue.GetObject();
		std::int64_t nView = -1;
		std::int64_t nOffset = 0;
		std::int64_t nCount = -1;
		std::int64_t nComponent = 0;
		std::string strType;
		if (pAccessor == nullptr || pAccessor->find("sparse") != pAccessor->end() || !JsonInteger(*pAccessor, "bufferView", -1, nView) ||
			!JsonInteger(*pAccessor, "byteOffset", 0, nOffset) || !JsonInteger(*pAccessor, "count", -1, nCount) ||
			!JsonInteger(*pAccessor, "componentType", 0, nComponent) || !JsonString(*pAccessor, "type", strType) ||
			nView < 0 || nView >= static_cast<std::int64_t>(arrViews.size()) || nOffset < 0 || nCount <= 0)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_accessor_layout", "$.accessors", "invalid or sparse accessor");
			return false;
		}
		const std::uint64_t nElementBytes = ComponentBytes(nComponent) * ComponentCount(strType);
		if (nElementBytes == 0)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_accessor_type", "$.accessors", "unsupported component or element type");
			return false;
		}
		const ViewLayout &stView = arrViews[static_cast<std::size_t>(nView)];
		const std::uint64_t nStride = stView.nStride == 0 ? nElementBytes : stView.nStride;
		if (nStride < nElementBytes || nOffset % ComponentBytes(nComponent) != 0 || (stView.nOffset + nOffset) % ComponentBytes(nComponent) != 0)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_accessor_alignment", "$.accessors", "accessor stride or alignment is invalid");
			return false;
		}
		if (static_cast<std::uint64_t>(nOffset) > stView.nLength ||
			static_cast<std::uint64_t>(nCount - 1) > (stView.nLength - static_cast<std::uint64_t>(nOffset)) / nStride)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_accessor_bounds", "$.accessors", "accessor count exceeds bufferView");
			return false;
		}
		const std::uint64_t nLastOffset = static_cast<std::uint64_t>(nOffset) + static_cast<std::uint64_t>(nCount - 1) * nStride;
		if (nLastOffset > stView.nLength || nElementBytes > stView.nLength - nLastOffset)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_accessor_bounds", "$.accessors", "accessor exceeds bufferView");
			return false;
		}
		arrAccessors.push_back(AccessorLayout{ static_cast<std::uint64_t>(nView), static_cast<std::uint64_t>(nOffset), static_cast<std::uint64_t>(nCount), nElementBytes, nComponent, strType });
	}
	const Serialization::JsonValue::List *pImages = MemberList(in_mapRoot, "images");
	if (pImages != nullptr)
	{
		for (const Serialization::JsonValue &stValue : *pImages)
		{
			const Serialization::JsonValue::Object *pImage = stValue.GetObject();
			std::int64_t nView = -1;
			if (pImage == nullptr || !JsonInteger(*pImage, "bufferView", -1, nView) || nView < 0 || nView >= static_cast<std::int64_t>(arrViews.size()))
			{
				AddDiagnostic(out_arrDiagnostics, "glb_image", "$.images", "image must reference a valid internal bufferView");
				return false;
			}
		}
	}
	for (const Serialization::JsonValue &stMeshValue : *pMeshes)
	{
		const Serialization::JsonValue::Object *pMesh = stMeshValue.GetObject();
		const Serialization::JsonValue::List *pPrimitives = pMesh == nullptr ? nullptr : MemberList(*pMesh, "primitives");
		if (pPrimitives == nullptr)
		{
			return false;
		}
		for (const Serialization::JsonValue &stPrimitiveValue : *pPrimitives)
		{
			const Serialization::JsonValue::Object *pPrimitive = stPrimitiveValue.GetObject();
			if (pPrimitive == nullptr || pPrimitive->find("attributes") == pPrimitive->end())
			{
				return false;
			}
			const Serialization::JsonValue::Object *pAttributes = pPrimitive->at("attributes").GetObject();
			std::int64_t nPosition = -1;
			if (pAttributes == nullptr || !JsonInteger(*pAttributes, "POSITION", -1, nPosition) || nPosition < 0 || nPosition >= static_cast<std::int64_t>(arrAccessors.size()))
			{
				return false;
			}
			const AccessorLayout &stPosition = arrAccessors[static_cast<std::size_t>(nPosition)];
			if (stPosition.nComponentType != 5126 || stPosition.strType != "VEC3")
			{
				AddDiagnostic(out_arrDiagnostics, "glb_position_type", "$.meshes", "POSITION must use float VEC3");
				return false;
			}
			if (pPrimitive->find("indices") == pPrimitive->end())
			{
				continue;
			}
			std::int64_t nIndex = -1;
			if (!JsonInteger(*pPrimitive, "indices", -1, nIndex) || nIndex < 0 || nIndex >= static_cast<std::int64_t>(arrAccessors.size()))
			{
				return false;
			}
			const AccessorLayout &stIndices = arrAccessors[static_cast<std::size_t>(nIndex)];
			if (stIndices.strType != "SCALAR" || (stIndices.nComponentType != 5121 && stIndices.nComponentType != 5123 && stIndices.nComponentType != 5125))
			{
				AddDiagnostic(out_arrDiagnostics, "glb_index_type", "$.meshes", "indices must use unsigned integer SCALAR");
				return false;
			}
			const ViewLayout &stView = arrViews[stIndices.nView];
			const std::uint64_t nStride = stView.nStride == 0 ? stIndices.nElementBytes : stView.nStride;
			for (std::uint64_t nItem = 0; nItem < stIndices.nCount; ++nItem)
			{
				const std::uint64_t nOffset = in_nBinaryOffset + stView.nOffset + stIndices.nOffset + nItem * nStride;
				std::uint64_t nValue = 0;
				for (std::uint64_t nByte = 0; nByte < stIndices.nElementBytes; ++nByte)
				{
					nValue |= static_cast<std::uint64_t>(in_arrBytes[nOffset + nByte]) << (nByte * 8U);
				}
				if (nValue >= stPosition.nCount)
				{
					AddDiagnostic(out_arrDiagnostics, "glb_index_value", "$.meshes", "index exceeds POSITION vertex count");
					return false;
				}
			}
		}
	}
	return true;
}

bool ValidateGlb(const std::vector<std::uint8_t> &in_arrBytes, BlobInfo &out_stInfo, Diagnostics &out_arrDiagnostics)
{
	if (in_arrBytes.size() < 20 || in_arrBytes.size() > MAX_GLB_BYTES || Read32LE(in_arrBytes.data()) != 0x46546C67U ||
		Read32LE(in_arrBytes.data() + 4) != 2 || Read32LE(in_arrBytes.data() + 8) != in_arrBytes.size())
	{
		AddDiagnostic(out_arrDiagnostics, "glb_header", "$", "invalid GLB header, version, length or budget");
		return false;
	}
	std::size_t nOffset = 12;
	Serialization::JsonValue stDocument;
	const std::vector<std::uint8_t> *pBinary = nullptr;
	std::size_t nBinaryOffset = 0;
	bool bJson = false;
	bool bBinary = false;
	while (nOffset < in_arrBytes.size())
	{
		if (nOffset + 8 > in_arrBytes.size())
		{
			AddDiagnostic(out_arrDiagnostics, "glb_chunk_bounds", "$", "truncated GLB chunk");
			return false;
		}
		const std::uint32_t nLength = Read32LE(in_arrBytes.data() + nOffset);
		const std::uint32_t nType = Read32LE(in_arrBytes.data() + nOffset + 4);
		nOffset += 8;
		if (nLength > in_arrBytes.size() - nOffset || nLength % 4 != 0 || nOffset % 4 != 0)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_chunk_bounds", "$", "invalid GLB chunk length or alignment");
			return false;
		}
		if (nType == 0x4E4F534AU && !bJson)
		{
			const std::string strJson(reinterpret_cast<const char *>(in_arrBytes.data() + nOffset), nLength);
			std::string strError;
			if (!Serialization::ParseJson(strJson, stDocument, strError))
			{
				AddDiagnostic(out_arrDiagnostics, "glb_json", "$", strError);
				return false;
			}
			bJson = true;
		}
		else if (nType == 0x004E4942U && bJson && !bBinary)
		{
			nBinaryOffset = nOffset;
			pBinary = &in_arrBytes;
			bBinary = true;
		}
		else
		{
			AddDiagnostic(out_arrDiagnostics, "glb_chunk_order", "$", "unknown, duplicate or misordered GLB chunk");
			return false;
		}
		nOffset += nLength;
	}
	if (!bJson || !bBinary || nOffset != in_arrBytes.size() || HasExternalUri(stDocument))
	{
		AddDiagnostic(out_arrDiagnostics, "glb_self_contained", "$", "GLB must contain JSON and BIN without URI references");
		return false;
	}
	const Serialization::JsonValue::Object *pRoot = stDocument.GetObject();
	const Serialization::JsonValue::List *pViews = pRoot == nullptr ? nullptr : MemberList(*pRoot, "bufferViews");
	const Serialization::JsonValue::List *pAccessors = pRoot == nullptr ? nullptr : MemberList(*pRoot, "accessors");
	const Serialization::JsonValue::List *pMeshes = pRoot == nullptr ? nullptr : MemberList(*pRoot, "meshes");
	if (pRoot == nullptr || pViews == nullptr || pAccessors == nullptr || pMeshes == nullptr)
	{
		AddDiagnostic(out_arrDiagnostics, "glb_structure", "$", "GLB requires bufferViews, accessors and meshes");
		return false;
	}
	const std::size_t nBinaryBytes = in_arrBytes.size() - nBinaryOffset;
	for (const Serialization::JsonValue &stValue : *pViews)
	{
		const Serialization::JsonValue::Object *pView = stValue.GetObject();
		std::int64_t nBuffer = 0;
		std::int64_t nOffsetValue = 0;
		std::int64_t nLength = 0;
		const Serialization::JsonValue::Object::const_iterator itBuffer = pView == nullptr ? Serialization::JsonValue::Object::const_iterator{} : pView->find("buffer");
		const Serialization::JsonValue::Object::const_iterator itOffset = pView == nullptr ? Serialization::JsonValue::Object::const_iterator{} : pView->find("byteOffset");
		const Serialization::JsonValue::Object::const_iterator itLength = pView == nullptr ? Serialization::JsonValue::Object::const_iterator{} : pView->find("byteLength");
		if (pView == nullptr || itBuffer == pView->end() || !itBuffer->second.GetInteger(nBuffer) || nBuffer != 0 ||
			itLength == pView->end() || !itLength->second.GetInteger(nLength) || nLength < 0 ||
			(itOffset != pView->end() && (!itOffset->second.GetInteger(nOffsetValue) || nOffsetValue < 0)) ||
			nOffsetValue > static_cast<std::int64_t>(nBinaryBytes) || nLength > static_cast<std::int64_t>(nBinaryBytes) - nOffsetValue)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_buffer_view", "$.bufferViews", "bufferView exceeds internal BIN chunk");
			return false;
		}
	}
	for (const Serialization::JsonValue &stValue : *pAccessors)
	{
		const Serialization::JsonValue::Object *pAccessor = stValue.GetObject();
		std::int64_t nView = 0;
		std::int64_t nCount = 0;
		if (pAccessor == nullptr || pAccessor->find("bufferView") == pAccessor->end() ||
			!pAccessor->at("bufferView").GetInteger(nView) || nView < 0 || nView >= static_cast<std::int64_t>(pViews->size()) ||
			pAccessor->find("count") == pAccessor->end() || !pAccessor->at("count").GetInteger(nCount) || nCount <= 0)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_accessor", "$.accessors", "invalid accessor view or count");
			return false;
		}
	}
	for (const Serialization::JsonValue &stMeshValue : *pMeshes)
	{
		const Serialization::JsonValue::Object *pMesh = stMeshValue.GetObject();
		const Serialization::JsonValue::List *pPrimitives = pMesh == nullptr ? nullptr : MemberList(*pMesh, "primitives");
		if (pPrimitives == nullptr)
		{
			AddDiagnostic(out_arrDiagnostics, "glb_mesh", "$.meshes", "mesh requires primitives");
			return false;
		}
		for (const Serialization::JsonValue &stPrimitiveValue : *pPrimitives)
		{
			const Serialization::JsonValue::Object *pPrimitive = stPrimitiveValue.GetObject();
			const Serialization::JsonValue::Object::const_iterator itAttributes = pPrimitive == nullptr ? Serialization::JsonValue::Object::const_iterator{} : pPrimitive->find("attributes");
			const Serialization::JsonValue::Object *pAttributes = pPrimitive == nullptr || itAttributes == pPrimitive->end() ? nullptr : itAttributes->second.GetObject();
			std::int64_t nPosition = -1;
			if (pAttributes == nullptr || pAttributes->find("POSITION") == pAttributes->end() ||
				!pAttributes->at("POSITION").GetInteger(nPosition) || nPosition < 0 || nPosition >= static_cast<std::int64_t>(pAccessors->size()))
			{
				AddDiagnostic(out_arrDiagnostics, "glb_position", "$.meshes", "primitive requires a valid POSITION accessor");
				return false;
			}
			std::int64_t nVertices = 0;
			if (!pAccessors->at(static_cast<std::size_t>(nPosition)).GetObject()->at("count").GetInteger(nVertices))
			{
				return false;
			}
			out_stInfo.nVertexCount += static_cast<std::uint64_t>(nVertices);
			std::int64_t nIndices = nVertices;
			if (pPrimitive->find("indices") != pPrimitive->end())
			{
				std::int64_t nIndexAccessor = -1;
				if (!pPrimitive->at("indices").GetInteger(nIndexAccessor) || nIndexAccessor < 0 || nIndexAccessor >= static_cast<std::int64_t>(pAccessors->size()) ||
					!pAccessors->at(static_cast<std::size_t>(nIndexAccessor)).GetObject()->at("count").GetInteger(nIndices))
				{
					AddDiagnostic(out_arrDiagnostics, "glb_indices", "$.meshes", "invalid index accessor");
					return false;
				}
			}
			std::int64_t nMode = 4;
			if (pPrimitive->find("mode") != pPrimitive->end() && !pPrimitive->at("mode").GetInteger(nMode))
			{
				AddDiagnostic(out_arrDiagnostics, "glb_mode", "$.meshes", "invalid primitive mode");
				return false;
			}
			if (nMode == 4 && nIndices % 3 != 0)
			{
				AddDiagnostic(out_arrDiagnostics, "glb_triangle_count", "$.meshes", "triangle primitive count must be divisible by three");
				return false;
			}
			if (nMode == 4)
			{
				out_stInfo.nTriangleCount += static_cast<std::uint64_t>(nIndices / 3);
			}
			if (out_stInfo.nVertexCount > MAX_VERTICES || out_stInfo.nTriangleCount > MAX_TRIANGLES)
			{
				AddDiagnostic(out_arrDiagnostics, "glb_budget", "$.meshes", "vertex or triangle budget exceeded");
				return false;
			}
		}
	}
	(void)pBinary;
	return out_stInfo.nVertexCount > 0 && ValidateAccessorGeometry(*pRoot, in_arrBytes, nBinaryOffset, out_arrDiagnostics);
}

} // namespace

bool ValidateBlob(const std::string &in_strMediaType, const std::vector<std::uint8_t> &in_arrBytes, BlobInfo &out_stInfo, Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_stInfo = BlobInfo{};
	if (in_arrBytes.empty())
	{
		AddDiagnostic(out_arrDiagnostics, "empty_blob", "$", "empty blob");
		return false;
	}
	if (in_strMediaType == "image/png")
	{
		return ValidatePng(in_arrBytes, out_stInfo, out_arrDiagnostics);
	}
	if (in_strMediaType == "image/jpeg")
	{
		return ValidateJpeg(in_arrBytes, out_stInfo, out_arrDiagnostics);
	}
	if (in_strMediaType == "model/gltf-binary")
	{
		return ValidateGlb(in_arrBytes, out_stInfo, out_arrDiagnostics);
	}
	AddDiagnostic(out_arrDiagnostics, "unsupported_media_type", "$", "unsupported media type");
	return false;
}

} // namespace EngineNext::Assets
