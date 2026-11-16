/**************************************************************************/
/*  GltfDecoder.cpp                                                       */
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

#include "engine_next/Rendering/Cook/GltfDecoder.h"

#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace EngineNext::Rendering
{
namespace
{

using Serialization::JsonValue;
using Matrix = std::array<double, 16>;
constexpr std::size_t MAX_ITEMS = 65536;
constexpr std::size_t MAX_DEPTH = 128;
constexpr std::size_t MAX_DECODED_BYTES = 256ULL * 1024ULL * 1024ULL;

const JsonValue *Find(const JsonValue::Object &mapObject, const char *pName)
{
	const JsonValue::Object::const_iterator itValue = mapObject.find(pName);
	return itValue == mapObject.end() ? nullptr : &itValue->second;
}

std::uint32_t Read32(const std::uint8_t *pBytes)
{
	return static_cast<std::uint32_t>(pBytes[0]) | (static_cast<std::uint32_t>(pBytes[1]) << 8U) |
			(static_cast<std::uint32_t>(pBytes[2]) << 16U) | (static_cast<std::uint32_t>(pBytes[3]) << 24U);
}

Matrix Identity()
{
	return Matrix{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
}

std::uint32_t ComponentCount(const std::string &strType)
{
	if (strType == "SCALAR")
	{
		return 1;
	}
	if (strType == "VEC2")
	{
		return 2;
	}
	if (strType == "VEC3")
	{
		return 3;
	}
	if (strType == "VEC4")
	{
		return 4;
	}
	return strType == "MAT4" ? 16 : 0;
}

std::size_t ComponentBytes(std::uint32_t nType)
{
	switch (nType)
	{
		case 5120:
		case 5121:
			return 1;
		case 5122:
		case 5123:
			return 2;
		case 5125:
		case 5126:
			return 4;
		default:
			return 0;
	}
}

Matrix Multiply(const Matrix &arrLeft, const Matrix &arrRight)
{
	Matrix arrResult{};
	for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < 4; ++nRow)
		{
			for (std::size_t nInner = 0; nInner < 4; ++nInner)
			{
				arrResult[nColumn * 4 + nRow] += arrLeft[nInner * 4 + nRow] * arrRight[nColumn * 4 + nInner];
			}
		}
	}
	return arrResult;
}

bool Normalize(std::array<float, 3> &out_arrVector)
{
	const double dLength = std::sqrt(static_cast<double>(out_arrVector[0]) * out_arrVector[0] +
									 static_cast<double>(out_arrVector[1]) * out_arrVector[1] + static_cast<double>(out_arrVector[2]) * out_arrVector[2]);
	if (!std::isfinite(dLength) || dLength < 1.0e-20)
	{
		return false;
	}
	for (float &fValue : out_arrVector)
	{
		fValue = static_cast<float>(fValue / dLength);
	}
	return true;
}

struct BufferView
{
	std::size_t nOffset = 0;
	std::size_t nLength = 0;
	std::size_t nStride = 0;
};

struct Accessor
{
	std::size_t nOffset = 0;
	std::size_t nStride = 0;
	std::size_t nCount = 0;
	std::uint32_t nComponent = 0;
	std::uint32_t nComponents = 0;
	bool bNormalized = false;
};

class Decoder final
{
public:
	Decoder(const std::vector<std::uint8_t> &in_arrBytes, Assets::Diagnostics &out_arrDiagnostics) : arrBytes(in_arrBytes), arrDiagnostics(out_arrDiagnostics) {}
	bool Run(DecodedMesh &out_stMesh);

private:
	bool Error(const std::string &strPath, const char *pMessage, const char *pCode = "gltf_render_semantics");
	bool Integer(const JsonValue::Object &mapObject, const char *pName, std::int64_t nDefault, std::int64_t &out_nValue);
	bool Number(const JsonValue::Object &mapObject, const char *pName, double dDefault, double &out_dValue);
	bool Boolean(const JsonValue::Object &mapObject, const char *pName, bool bDefault, bool &out_bValue);
	bool List(const JsonValue::Object &mapObject, const char *pName, const JsonValue::List *&out_pList);
	bool RejectUnsupported(const JsonValue &stValue, const std::string &strPath, std::size_t nDepth);
	bool ReadLayouts(const JsonValue::Object &mapRoot);
	bool ReadImages(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh);
	bool ReadTextures(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh);
	bool ReadMaterials(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh);
	bool Texture(const JsonValue::Object &mapMaterial, const char *pName, std::size_t nTextureCount, std::int32_t &out_nTexture);
	bool Factors(const JsonValue::Object &mapObject, const char *pName, float *out_pValues, std::size_t nCount, double dMinimum, double dMaximum);
	bool ReadMeshes(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh);
	bool ReadPrimitive(const JsonValue::Object &mapPrimitive, DecodedMesh &out_stMesh);
	bool Attribute(const JsonValue::Object &mapAttributes, const char *pName, std::uint32_t nComponents, std::size_t nVertexCount, std::int64_t &out_nAccessor);
	bool Values(const Accessor &stAccessor, std::size_t nElement, float *out_pValues);
	bool GenerateBasis(MeshPrimitive &out_stPrimitive, bool bNormals, bool bTangents, bool bTexcoord);
	bool ReadInstances(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh);
	bool Transform(const JsonValue::Object &mapNode, Matrix &out_arrTransform);
	bool WalkNode(std::uint32_t nNode, const Matrix &arrParent, std::size_t nDepth, const JsonValue::List &arrNodes, DecodedMesh &out_stMesh);

	const std::vector<std::uint8_t> &arrBytes;
	Assets::Diagnostics &arrDiagnostics;
	std::size_t nBinaryOffset = 0;
	std::vector<BufferView> arrViews;
	std::vector<Accessor> arrAccessors;
	std::vector<std::vector<std::uint32_t>> arrMeshPrimitives;
	std::vector<std::uint8_t> arrNodeState;
	std::size_t nDecodedBytes = 0;
	std::string strContext;
};

bool Decoder::Error(const std::string &strPath, const char *pMessage, const char *pCode)
{
	Assets::AddDiagnostic(arrDiagnostics, pCode, strPath, pMessage);
	return false;
}

bool Decoder::Integer(const JsonValue::Object &mapObject, const char *pName, std::int64_t nDefault, std::int64_t &out_nValue)
{
	out_nValue = nDefault;
	const JsonValue *pValue = Find(mapObject, pName);
	return pValue == nullptr || pValue->GetInteger(out_nValue) || Error(strContext + "." + pName, "Expected an integer.");
}

bool Decoder::Number(const JsonValue::Object &mapObject, const char *pName, double dDefault, double &out_dValue)
{
	out_dValue = dDefault;
	const JsonValue *pValue = Find(mapObject, pName);
	return pValue == nullptr || (pValue->GetNumber(out_dValue) && std::isfinite(out_dValue) && std::abs(out_dValue) <= std::numeric_limits<float>::max()) || Error(strContext + "." + pName, "Expected a finite binary32 number.");
}

bool Decoder::Boolean(const JsonValue::Object &mapObject, const char *pName, bool bDefault, bool &out_bValue)
{
	out_bValue = bDefault;
	const JsonValue *pValue = Find(mapObject, pName);
	return pValue == nullptr || pValue->GetBool(out_bValue) || Error(strContext + "." + pName, "Expected a boolean.");
}

bool Decoder::List(const JsonValue::Object &mapObject, const char *pName, const JsonValue::List *&out_pList)
{
	const JsonValue *pValue = Find(mapObject, pName);
	out_pList = pValue == nullptr ? nullptr : pValue->GetList();
	return pValue == nullptr || (out_pList != nullptr && out_pList->size() <= MAX_ITEMS) || Error(strContext + "." + pName, "Expected a bounded array.");
}

bool Decoder::RejectUnsupported(const JsonValue &stValue, const std::string &strPath, std::size_t nDepth)
{
	if (nDepth > MAX_DEPTH)
	{
		return Error(strPath, "Document exceeds rendering nesting budget.");
	}
	const JsonValue::Object *pObject = stValue.GetObject();
	if (pObject != nullptr)
	{
		for (const std::pair<const std::string, JsonValue> &stMember : *pObject)
		{
			if (stMember.first == "extras")
			{
				continue;
			}
			if (stMember.first == "extensions")
			{
				const JsonValue::Object *pExtensions = stMember.second.GetObject();
				if (pExtensions == nullptr || !pExtensions->empty())
				{
					return Error(strPath + ".extensions", "Material or geometry extensions are not yet supported by this decoder.", "gltf_unsupported");
				}
			}
			if (!RejectUnsupported(stMember.second, strPath + "." + stMember.first, nDepth + 1))
			{
				return false;
			}
		}
	}
	const JsonValue::List *pList = stValue.GetList();
	if (pList != nullptr)
	{
		for (std::size_t nIndex = 0; nIndex < pList->size(); ++nIndex)
		{
			if (!RejectUnsupported((*pList)[nIndex], strPath + "[" + std::to_string(nIndex) + "]", nDepth + 1))
			{
				return false;
			}
		}
	}
	return true;
}

bool Decoder::ReadLayouts(const JsonValue::Object &mapRoot)
{
	const JsonValue::List *pBuffers = nullptr;
	if (!List(mapRoot, "buffers", pBuffers) || pBuffers == nullptr || pBuffers->size() != 1)
	{
		return Error("$.buffers", "Exactly one internal buffer is required.");
	}
	const JsonValue::Object *pBuffer = (*pBuffers)[0].GetObject();
	std::int64_t nDeclaredBytes = 0;
	strContext = "$.buffers[0]";
	if (pBuffer == nullptr || !Integer(*pBuffer, "byteLength", 0, nDeclaredBytes) || nDeclaredBytes <= 0 ||
		static_cast<std::uint64_t>(nDeclaredBytes) > arrBytes.size() - nBinaryOffset)
	{
		return Error(strContext, "The declared buffer length exceeds the BIN chunk.");
	}
	const std::size_t nPaddingStart = nBinaryOffset + static_cast<std::size_t>(nDeclaredBytes);
	if (arrBytes.size() - nPaddingStart > 3 || std::any_of(arrBytes.begin() + static_cast<std::ptrdiff_t>(nPaddingStart), arrBytes.end(), [](std::uint8_t nByte)
														   { return nByte != 0; }))
	{
		return Error(strContext, "BIN padding must contain at most three zero bytes.");
	}
	const JsonValue::List *pViews = nullptr;
	const JsonValue::List *pAccessors = nullptr;
	if (!List(mapRoot, "bufferViews", pViews) || !List(mapRoot, "accessors", pAccessors) || pViews == nullptr || pAccessors == nullptr)
	{
		return Error("$", "GLB layouts are missing.");
	}
	for (std::size_t nIndex = 0; nIndex < pViews->size(); ++nIndex)
	{
		strContext = "$.bufferViews[" + std::to_string(nIndex) + "]";
		const JsonValue::Object *pView = (*pViews)[nIndex].GetObject();
		std::int64_t nOffset = 0;
		std::int64_t nLength = 0;
		std::int64_t nStride = 0;
		if (pView == nullptr || !Integer(*pView, "byteOffset", 0, nOffset) || !Integer(*pView, "byteLength", -1, nLength) || !Integer(*pView, "byteStride", 0, nStride) || nOffset < 0 || nLength < 0 || nStride < 0 || (nStride != 0 && (nStride < 4 || nStride > 252)))
		{
			return Error(strContext, "Invalid rendering bufferView layout.");
		}
		arrViews.push_back(BufferView{ nBinaryOffset + static_cast<std::size_t>(nOffset), static_cast<std::size_t>(nLength), static_cast<std::size_t>(nStride) });
	}
	for (std::size_t nIndex = 0; nIndex < pAccessors->size(); ++nIndex)
	{
		strContext = "$.accessors[" + std::to_string(nIndex) + "]";
		const JsonValue::Object *pAccessor = (*pAccessors)[nIndex].GetObject();
		std::int64_t nView = -1;
		std::int64_t nOffset = 0;
		std::int64_t nCount = 0;
		std::int64_t nComponent = 0;
		bool bNormalized = false;
		if (pAccessor == nullptr || !Integer(*pAccessor, "bufferView", -1, nView) || !Integer(*pAccessor, "byteOffset", 0, nOffset) || !Integer(*pAccessor, "count", 0, nCount) || !Integer(*pAccessor, "componentType", 0, nComponent) || !Boolean(*pAccessor, "normalized", false, bNormalized) || nView < 0 || nView >= static_cast<std::int64_t>(arrViews.size()))
		{
			return Error(strContext, "Invalid accessor.");
		}
		const JsonValue *pType = Find(*pAccessor, "type");
		const std::string *pTypeName = pType == nullptr ? nullptr : pType->GetString();
		const std::uint32_t nComponents = pTypeName == nullptr ? 0 : ComponentCount(*pTypeName);
		const std::size_t nComponentBytes = ComponentBytes(static_cast<std::uint32_t>(nComponent));
		if (nComponents == 0 || nComponentBytes == 0 || nCount <= 0 || nOffset < 0 || (bNormalized && (nComponent == 5125 || nComponent == 5126)))
		{
			return Error(strContext, "Unsupported accessor component representation.");
		}
		const BufferView &stView = arrViews[static_cast<std::size_t>(nView)];
		const std::size_t nElementBytes = nComponents * nComponentBytes;
		const std::size_t nStride = stView.nStride == 0 ? nElementBytes : stView.nStride;
		const std::size_t nLocalOffset = static_cast<std::size_t>(nOffset);
		if (nLocalOffset > stView.nLength || nElementBytes > stView.nLength - nLocalOffset || nStride < nElementBytes || static_cast<std::uint64_t>(nCount - 1) > (stView.nLength - nLocalOffset - nElementBytes) / nStride)
		{
			return Error(strContext, "Accessor exceeds its bufferView.");
		}
		arrAccessors.push_back(Accessor{ stView.nOffset + nLocalOffset, nStride, static_cast<std::size_t>(nCount), static_cast<std::uint32_t>(nComponent), nComponents, bNormalized });
	}
	return true;
}

bool Decoder::ReadImages(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh)
{
	const JsonValue::List *pImages = nullptr;
	if (!List(mapRoot, "images", pImages))
	{
		return false;
	}
	if (pImages == nullptr)
	{
		return true;
	}
	for (std::size_t nIndex = 0; nIndex < pImages->size(); ++nIndex)
	{
		strContext = "$.images[" + std::to_string(nIndex) + "]";
		const JsonValue::Object *pImage = (*pImages)[nIndex].GetObject();
		std::int64_t nView = -1;
		if (pImage == nullptr || !Integer(*pImage, "bufferView", -1, nView) || nView < 0 || nView >= static_cast<std::int64_t>(arrViews.size()))
		{
			return Error(strContext, "Image requires an internal bufferView.");
		}
		const JsonValue *pMime = Find(*pImage, "mimeType");
		const std::string *pMimeName = pMime == nullptr ? nullptr : pMime->GetString();
		if (pMimeName == nullptr || (*pMimeName != "image/png" && *pMimeName != "image/jpeg"))
		{
			return Error(strContext, "Only PNG and JPEG image payloads are supported.", "gltf_unsupported");
		}
		const BufferView &stView = arrViews[static_cast<std::size_t>(nView)];
		if (stView.nStride != 0 || stView.nLength > MAX_DECODED_BYTES - nDecodedBytes)
		{
			return Error(strContext, "Image stride or cumulative payload budget is invalid.");
		}
		EncodedImage stImage;
		stImage.strMimeType = *pMimeName;
		stImage.arrBytes.assign(arrBytes.begin() + static_cast<std::ptrdiff_t>(stView.nOffset), arrBytes.begin() + static_cast<std::ptrdiff_t>(stView.nOffset + stView.nLength));
		Assets::BlobInfo stInfo;
		Assets::Diagnostics arrImageDiagnostics;
		if (!Assets::ValidateBlob(stImage.strMimeType, stImage.arrBytes, stInfo, arrImageDiagnostics))
		{
			return Error(strContext, "Embedded image failed the M3 payload validator.");
		}
		nDecodedBytes += stView.nLength;
		out_stMesh.arrImages.push_back(std::move(stImage));
	}
	return true;
}

bool Decoder::ReadTextures(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh)
{
	const JsonValue::List *pSamplers = nullptr;
	const JsonValue::List *pTextures = nullptr;
	if (!List(mapRoot, "samplers", pSamplers) || !List(mapRoot, "textures", pTextures))
	{
		return false;
	}
	std::vector<TextureData> arrSamplers;
	if (pSamplers != nullptr)
	{
		for (const JsonValue &stValue : *pSamplers)
		{
			strContext = "$.samplers";
			const JsonValue::Object *pSampler = stValue.GetObject();
			TextureData stSampler;
			std::int64_t nMag = 0;
			std::int64_t nMin = 0;
			std::int64_t nWrapS = 0;
			std::int64_t nWrapT = 0;
			if (pSampler == nullptr || !Integer(*pSampler, "magFilter", 0, nMag) || !Integer(*pSampler, "minFilter", 0, nMin) || !Integer(*pSampler, "wrapS", 10497, nWrapS) || !Integer(*pSampler, "wrapT", 10497, nWrapT) ||
				(nMag != 0 && nMag != 9728 && nMag != 9729) || (nMin != 0 && nMin != 9728 && nMin != 9729 && (nMin < 9984 || nMin > 9987)) ||
				(nWrapS != 33071 && nWrapS != 33648 && nWrapS != 10497) || (nWrapT != 33071 && nWrapT != 33648 && nWrapT != 10497))
			{
				return Error(strContext, "Invalid sampler mode.");
			}
			stSampler.nMagFilter = static_cast<std::int32_t>(nMag);
			stSampler.nMinFilter = static_cast<std::int32_t>(nMin);
			stSampler.nWrapS = static_cast<std::int32_t>(nWrapS);
			stSampler.nWrapT = static_cast<std::int32_t>(nWrapT);
			arrSamplers.push_back(stSampler);
		}
	}
	if (pTextures == nullptr)
	{
		return true;
	}
	for (const JsonValue &stValue : *pTextures)
	{
		strContext = "$.textures";
		const JsonValue::Object *pTexture = stValue.GetObject();
		std::int64_t nImage = -1;
		std::int64_t nSampler = -1;
		if (pTexture == nullptr || !Integer(*pTexture, "source", -1, nImage) || !Integer(*pTexture, "sampler", -1, nSampler) || nImage < 0 || nImage >= static_cast<std::int64_t>(out_stMesh.arrImages.size()) || nSampler < -1 || nSampler >= static_cast<std::int64_t>(arrSamplers.size()) || (nSampler == -1 && Find(*pTexture, "sampler") != nullptr))
		{
			return Error(strContext, "Invalid image or sampler reference.");
		}
		TextureData stTexture = nSampler == -1 ? TextureData{} : arrSamplers[static_cast<std::size_t>(nSampler)];
		stTexture.nImage = static_cast<std::uint32_t>(nImage);
		out_stMesh.arrTextures.push_back(stTexture);
	}
	return true;
}

bool Decoder::Factors(const JsonValue::Object &mapObject, const char *pName, float *out_pValues, std::size_t nCount, double dMinimum, double dMaximum)
{
	const JsonValue *pValue = Find(mapObject, pName);
	if (pValue == nullptr)
	{
		return true;
	}
	const JsonValue::List *pValues = pValue->GetList();
	if (pValues == nullptr || pValues->size() != nCount)
	{
		return Error(strContext + "." + pName, "Invalid factor vector length.");
	}
	for (std::size_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		double dValue = 0;
		if (!(*pValues)[nIndex].GetNumber(dValue) || !std::isfinite(dValue) || dValue < dMinimum || dValue > dMaximum)
		{
			return Error(strContext + "." + pName, "Factor lies outside its allowed finite range.");
		}
		out_pValues[nIndex] = static_cast<float>(dValue);
	}
	return true;
}

bool Decoder::Texture(const JsonValue::Object &mapMaterial, const char *pName, std::size_t nTextureCount, std::int32_t &out_nTexture)
{
	const JsonValue *pValue = Find(mapMaterial, pName);
	if (pValue == nullptr)
	{
		return true;
	}
	const JsonValue::Object *pInfo = pValue->GetObject();
	std::int64_t nIndex = -1;
	std::int64_t nTexcoord = 0;
	if (pInfo == nullptr || !Integer(*pInfo, "index", -1, nIndex) || !Integer(*pInfo, "texCoord", 0, nTexcoord) || nIndex < 0 || nIndex >= static_cast<std::int64_t>(nTextureCount) || nTexcoord != 0)
	{
		return Error(strContext + "." + pName, "Texture requires a valid index and supported TEXCOORD_0.");
	}
	out_nTexture = static_cast<std::int32_t>(nIndex);
	return true;
}

bool Decoder::ReadMaterials(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh)
{
	const JsonValue::List *pMaterials = nullptr;
	if (!List(mapRoot, "materials", pMaterials))
	{
		return false;
	}
	if (pMaterials == nullptr)
	{
		return true;
	}
	for (std::size_t nIndex = 0; nIndex < pMaterials->size(); ++nIndex)
	{
		strContext = "$.materials[" + std::to_string(nIndex) + "]";
		const JsonValue::Object *pMaterial = (*pMaterials)[nIndex].GetObject();
		if (pMaterial == nullptr)
		{
			return Error(strContext, "Material must be an object.");
		}
		MaterialData stMaterial;
		const JsonValue *pPbrValue = Find(*pMaterial, "pbrMetallicRoughness");
		const JsonValue::Object *pPbr = pPbrValue == nullptr ? nullptr : pPbrValue->GetObject();
		if (pPbrValue != nullptr && pPbr == nullptr)
		{
			return Error(strContext, "Metallic/roughness material must be an object.");
		}
		double dMetallic = 1;
		double dRoughness = 1;
		if (pPbr != nullptr && (!Factors(*pPbr, "baseColorFactor", stMaterial.arrBaseColor.data(), 4, 0, 1) || !Number(*pPbr, "metallicFactor", 1, dMetallic) || !Number(*pPbr, "roughnessFactor", 1, dRoughness) || !Texture(*pPbr, "baseColorTexture", out_stMesh.arrTextures.size(), stMaterial.nBaseColorTexture) || !Texture(*pPbr, "metallicRoughnessTexture", out_stMesh.arrTextures.size(), stMaterial.nMetallicRoughnessTexture)))
		{
			return false;
		}
		if (dMetallic < 0 || dMetallic > 1 || dRoughness < 0 || dRoughness > 1)
		{
			return Error(strContext, "Metallic and roughness factors must be in [0,1].");
		}
		stMaterial.fMetallic = static_cast<float>(dMetallic);
		stMaterial.fRoughness = static_cast<float>(dRoughness);
		if (!Factors(*pMaterial, "emissiveFactor", stMaterial.arrEmissive.data(), 3, 0, 1) || !Boolean(*pMaterial, "doubleSided", false, stMaterial.bDoubleSided) ||
			!Texture(*pMaterial, "normalTexture", out_stMesh.arrTextures.size(), stMaterial.nNormalTexture) || !Texture(*pMaterial, "occlusionTexture", out_stMesh.arrTextures.size(), stMaterial.nOcclusionTexture) || !Texture(*pMaterial, "emissiveTexture", out_stMesh.arrTextures.size(), stMaterial.nEmissiveTexture))
		{
			return false;
		}
		const JsonValue *pNormal = Find(*pMaterial, "normalTexture");
		const JsonValue *pOcclusion = Find(*pMaterial, "occlusionTexture");
		double dNormalScale = 1;
		double dOcclusionStrength = 1;
		double dCutoff = 0.5;
		if ((pNormal != nullptr && !Number(*pNormal->GetObject(), "scale", 1, dNormalScale)) || (pOcclusion != nullptr && !Number(*pOcclusion->GetObject(), "strength", 1, dOcclusionStrength)) ||
			!Number(*pMaterial, "alphaCutoff", 0.5, dCutoff) || dCutoff < 0 || dOcclusionStrength < 0 || dOcclusionStrength > 1)
		{
			return Error(strContext, "Invalid normal, occlusion or alpha factor.");
		}
		stMaterial.fNormalScale = static_cast<float>(dNormalScale);
		stMaterial.fOcclusionStrength = static_cast<float>(dOcclusionStrength);
		stMaterial.fAlphaCutoff = static_cast<float>(dCutoff);
		const JsonValue *pAlpha = Find(*pMaterial, "alphaMode");
		if (pAlpha != nullptr)
		{
			const std::string *pMode = pAlpha->GetString();
			if (pMode == nullptr || (*pMode != "OPAQUE" && *pMode != "MASK" && *pMode != "BLEND"))
			{
				return Error(strContext, "Invalid alpha mode.");
			}
			stMaterial.eAlphaMode = *pMode == "MASK" ? AlphaMode::Mask : *pMode == "BLEND" ? AlphaMode::Blend
																						   : AlphaMode::Opaque;
		}
		out_stMesh.arrMaterials.push_back(stMaterial);
	}
	return true;
}

bool Decoder::Values(const Accessor &stAccessor, std::size_t nElement, float *out_pValues)
{
	const std::size_t nComponentBytes = ComponentBytes(stAccessor.nComponent);
	const std::uint8_t *pElement = arrBytes.data() + stAccessor.nOffset + nElement * stAccessor.nStride;
	for (std::uint32_t nComponent = 0; nComponent < stAccessor.nComponents; ++nComponent)
	{
		const std::uint8_t *pValue = pElement + nComponent * nComponentBytes;
		float fValue = 0;
		if (stAccessor.nComponent == 5126)
		{
			const std::uint32_t nBits = Read32(pValue);
			std::memcpy(&fValue, &nBits, sizeof(fValue));
		}
		else
		{
			std::uint32_t nValue = pValue[0];
			if (nComponentBytes >= 2)
			{
				nValue |= static_cast<std::uint32_t>(pValue[1]) << 8U;
			}
			if (nComponentBytes == 4)
			{
				nValue = Read32(pValue);
			}
			if (stAccessor.nComponent == 5120 || stAccessor.nComponent == 5122)
			{
				const std::int32_t nSigned = stAccessor.nComponent == 5120 ? (nValue >= 128 ? static_cast<std::int32_t>(nValue) - 256 : static_cast<std::int32_t>(nValue)) : (nValue >= 32768 ? static_cast<std::int32_t>(nValue) - 65536 : static_cast<std::int32_t>(nValue));
				fValue = stAccessor.bNormalized ? (std::max)(-1.0F, static_cast<float>(nSigned) / (stAccessor.nComponent == 5120 ? 127.0F : 32767.0F)) : static_cast<float>(nSigned);
			}
			else
			{
				fValue = stAccessor.bNormalized ? static_cast<float>(nValue) / (stAccessor.nComponent == 5121 ? 255.0F : 65535.0F) : static_cast<float>(nValue);
			}
		}
		if (!std::isfinite(fValue))
		{
			return Error(strContext, "Non-finite vertex component.");
		}
		out_pValues[nComponent] = fValue;
	}
	return true;
}

bool Decoder::Attribute(const JsonValue::Object &mapAttributes, const char *pName, std::uint32_t nComponents, std::size_t nVertexCount, std::int64_t &out_nAccessor)
{
	if (!Integer(mapAttributes, pName, -1, out_nAccessor))
	{
		return false;
	}
	if (out_nAccessor == -1)
	{
		return Find(mapAttributes, pName) == nullptr || Error(strContext, "Negative attribute index.");
	}
	if (out_nAccessor < 0 || out_nAccessor >= static_cast<std::int64_t>(arrAccessors.size()))
	{
		return Error(strContext, "Invalid vertex accessor index.");
	}
	const Accessor &stAccessor = arrAccessors[static_cast<std::size_t>(out_nAccessor)];
	const bool bFloat = stAccessor.nComponent == 5126 && !stAccessor.bNormalized;
	const bool bUv = nComponents == 2 && stAccessor.bNormalized && (stAccessor.nComponent == 5121 || stAccessor.nComponent == 5123);
	const bool bSigned = nComponents != 2 && stAccessor.bNormalized && (stAccessor.nComponent == 5120 || stAccessor.nComponent == 5122);
	if (stAccessor.nComponents != nComponents || stAccessor.nCount != nVertexCount || (!bFloat && !bUv && !bSigned))
	{
		return Error(strContext, "Attribute count, shape or normalized component type is invalid.");
	}
	return true;
}

bool Decoder::GenerateBasis(MeshPrimitive &out_stPrimitive, bool bNormals, bool bTangents, bool bTexcoord)
{
	std::vector<std::array<double, 3>> arrNormals(out_stPrimitive.arrVertices.size());
	std::vector<std::array<double, 3>> arrTangents(out_stPrimitive.arrVertices.size());
	std::vector<std::array<double, 3>> arrBitangents(out_stPrimitive.arrVertices.size());
	for (std::size_t nIndex = 0; nIndex < out_stPrimitive.arrIndices.size(); nIndex += 3)
	{
		const MeshVertex &stA = out_stPrimitive.arrVertices[out_stPrimitive.arrIndices[nIndex]];
		const MeshVertex &stB = out_stPrimitive.arrVertices[out_stPrimitive.arrIndices[nIndex + 1]];
		const MeshVertex &stC = out_stPrimitive.arrVertices[out_stPrimitive.arrIndices[nIndex + 2]];
		std::array<double, 3> arrEdge1{};
		std::array<double, 3> arrEdge2{};
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrEdge1[nAxis] = static_cast<double>(stB.arrPosition[nAxis]) - stA.arrPosition[nAxis];
			arrEdge2[nAxis] = static_cast<double>(stC.arrPosition[nAxis]) - stA.arrPosition[nAxis];
		}
		const std::array<double, 3> arrNormal{ arrEdge1[1] * arrEdge2[2] - arrEdge1[2] * arrEdge2[1], arrEdge1[2] * arrEdge2[0] - arrEdge1[0] * arrEdge2[2], arrEdge1[0] * arrEdge2[1] - arrEdge1[1] * arrEdge2[0] };
		const double dU1 = static_cast<double>(stB.arrTexcoord[0]) - stA.arrTexcoord[0];
		const double dV1 = static_cast<double>(stB.arrTexcoord[1]) - stA.arrTexcoord[1];
		const double dU2 = static_cast<double>(stC.arrTexcoord[0]) - stA.arrTexcoord[0];
		const double dV2 = static_cast<double>(stC.arrTexcoord[1]) - stA.arrTexcoord[1];
		const double dDeterminant = dU1 * dV2 - dU2 * dV1;
		for (std::size_t nCorner = 0; nCorner < 3; ++nCorner)
		{
			const std::uint32_t nVertex = out_stPrimitive.arrIndices[nIndex + nCorner];
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrNormals[nVertex][nAxis] += arrNormal[nAxis];
				if (bTexcoord && std::abs(dDeterminant) > 1.0e-20)
				{
					arrTangents[nVertex][nAxis] += (arrEdge1[nAxis] * dV2 - arrEdge2[nAxis] * dV1) / dDeterminant;
					arrBitangents[nVertex][nAxis] += (arrEdge2[nAxis] * dU1 - arrEdge1[nAxis] * dU2) / dDeterminant;
				}
			}
		}
	}
	for (std::size_t nIndex = 0; nIndex < out_stPrimitive.arrVertices.size(); ++nIndex)
	{
		MeshVertex &stVertex = out_stPrimitive.arrVertices[nIndex];
		if (bNormals)
		{
			const double dLength = std::sqrt(arrNormals[nIndex][0] * arrNormals[nIndex][0] + arrNormals[nIndex][1] * arrNormals[nIndex][1] + arrNormals[nIndex][2] * arrNormals[nIndex][2]);
			if (dLength > 1.0e-20 && std::isfinite(dLength))
			{
				for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
				{
					stVertex.arrNormal[nAxis] = static_cast<float>(arrNormals[nIndex][nAxis] / dLength);
				}
			}
		}
		if (!Normalize(stVertex.arrNormal))
		{
			return Error(strContext, "Normal has zero length.");
		}
		std::array<float, 3> arrTangent{ stVertex.arrTangent[0], stVertex.arrTangent[1], stVertex.arrTangent[2] };
		if (bTangents)
		{
			const double dLength = std::sqrt(arrTangents[nIndex][0] * arrTangents[nIndex][0] + arrTangents[nIndex][1] * arrTangents[nIndex][1] + arrTangents[nIndex][2] * arrTangents[nIndex][2]);
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrTangent[nAxis] = dLength > 1.0e-20 && std::isfinite(dLength) ? static_cast<float>(arrTangents[nIndex][nAxis] / dLength) : 0.0F;
			}
		}
		const float fDot = arrTangent[0] * stVertex.arrNormal[0] + arrTangent[1] * stVertex.arrNormal[1] + arrTangent[2] * stVertex.arrNormal[2];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrTangent[nAxis] -= fDot * stVertex.arrNormal[nAxis];
		}
		if (!Normalize(arrTangent))
		{
			if (!bTangents)
			{
				return Error(strContext, "Tangent is parallel to the normal or has zero length.");
			}
			arrTangent = std::abs(stVertex.arrNormal[0]) < 0.9F ? std::array<float, 3>{ 1, 0, 0 } : std::array<float, 3>{ 0, 1, 0 };
			const float fProjection = arrTangent[0] * stVertex.arrNormal[0] + arrTangent[1] * stVertex.arrNormal[1] + arrTangent[2] * stVertex.arrNormal[2];
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrTangent[nAxis] -= fProjection * stVertex.arrNormal[nAxis];
			}
			(void)Normalize(arrTangent);
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stVertex.arrTangent[nAxis] = arrTangent[nAxis];
		}
		if (bTangents)
		{
			const std::array<float, 3> &arrNormal = stVertex.arrNormal;
			const double dHandedness = (arrNormal[1] * arrTangent[2] - arrNormal[2] * arrTangent[1]) * arrBitangents[nIndex][0] +
					(arrNormal[2] * arrTangent[0] - arrNormal[0] * arrTangent[2]) * arrBitangents[nIndex][1] + (arrNormal[0] * arrTangent[1] - arrNormal[1] * arrTangent[0]) * arrBitangents[nIndex][2];
			stVertex.arrTangent[3] = dHandedness < 0 ? -1.0F : 1.0F;
		}
	}
	return true;
}

bool Decoder::ReadPrimitive(const JsonValue::Object &mapPrimitive, DecodedMesh &out_stMesh)
{
	std::int64_t nMode = 4;
	std::int64_t nMaterial = -1;
	std::int64_t nIndices = -1;
	if (!Integer(mapPrimitive, "mode", 4, nMode) || nMode != 4 || Find(mapPrimitive, "targets") != nullptr || !Integer(mapPrimitive, "material", -1, nMaterial) || !Integer(mapPrimitive, "indices", -1, nIndices))
	{
		return Error(strContext, "Only triangle primitives without morph targets are supported.", "gltf_unsupported");
	}
	const JsonValue *pAttributeValue = Find(mapPrimitive, "attributes");
	const JsonValue::Object *pAttributes = pAttributeValue == nullptr ? nullptr : pAttributeValue->GetObject();
	std::int64_t nPosition = -1;
	if (pAttributes == nullptr || !Integer(*pAttributes, "POSITION", -1, nPosition) || nPosition < 0 || nPosition >= static_cast<std::int64_t>(arrAccessors.size()))
	{
		return Error(strContext, "Primitive requires POSITION.");
	}
	for (const std::pair<const std::string, JsonValue> &stMember : *pAttributes)
	{
		if (stMember.first != "POSITION" && stMember.first != "NORMAL" && stMember.first != "TANGENT" && stMember.first != "TEXCOORD_0")
		{
			return Error(strContext + ".attributes." + stMember.first, "Unsupported vertex attribute.", "gltf_unsupported");
		}
	}
	const Accessor &stPosition = arrAccessors[static_cast<std::size_t>(nPosition)];
	if (stPosition.nComponents != 3 || stPosition.nComponent != 5126 || stPosition.bNormalized)
	{
		return Error(strContext, "POSITION requires non-normalized FLOAT VEC3.");
	}
	std::int64_t nNormal = -1;
	std::int64_t nTangent = -1;
	std::int64_t nUv = -1;
	if (!Attribute(*pAttributes, "NORMAL", 3, stPosition.nCount, nNormal) || !Attribute(*pAttributes, "TANGENT", 4, stPosition.nCount, nTangent) || !Attribute(*pAttributes, "TEXCOORD_0", 2, stPosition.nCount, nUv))
	{
		return false;
	}
	const std::size_t nMaterialCount = out_stMesh.arrMaterials.size() - 1;
	if (nMaterial < -1 || nMaterial >= static_cast<std::int64_t>(nMaterialCount) || (nMaterial == -1 && Find(mapPrimitive, "material") != nullptr))
	{
		return Error(strContext, "Invalid material reference.");
	}
	MeshPrimitive stPrimitive;
	stPrimitive.nMaterial = static_cast<std::int32_t>(nMaterial == -1 ? nMaterialCount : static_cast<std::size_t>(nMaterial));
	const MaterialData &stMaterial = out_stMesh.arrMaterials[static_cast<std::size_t>(stPrimitive.nMaterial)];
	if (nUv < 0 && (stMaterial.nBaseColorTexture >= 0 || stMaterial.nMetallicRoughnessTexture >= 0 || stMaterial.nNormalTexture >= 0 || stMaterial.nOcclusionTexture >= 0 || stMaterial.nEmissiveTexture >= 0))
	{
		return Error(strContext, "Textured material requires TEXCOORD_0.");
	}
	std::size_t nIndexCount = stPosition.nCount;
	if (nIndices == -1 && Find(mapPrimitive, "indices") != nullptr)
	{
		return Error(strContext, "Explicit index reference must be nonnegative.");
	}
	if (nIndices != -1)
	{
		if (nIndices < 0 || nIndices >= static_cast<std::int64_t>(arrAccessors.size()))
		{
			return Error(strContext, "Invalid index accessor.");
		}
		const Accessor &stIndex = arrAccessors[static_cast<std::size_t>(nIndices)];
		if (stIndex.nComponents != 1 || stIndex.bNormalized || (stIndex.nComponent != 5121 && stIndex.nComponent != 5123 && stIndex.nComponent != 5125))
		{
			return Error(strContext, "Indices require non-normalized unsigned scalar values.");
		}
		nIndexCount = stIndex.nCount;
	}
	if (nIndexCount == 0 || nIndexCount % 3 != 0 || stPosition.nCount > (MAX_DECODED_BYTES - nDecodedBytes) / sizeof(MeshVertex))
	{
		return Error(strContext, "Primitive budget or triangle count is invalid.");
	}
	nDecodedBytes += stPosition.nCount * sizeof(MeshVertex);
	if (nIndexCount > (MAX_DECODED_BYTES - nDecodedBytes) / sizeof(std::uint32_t))
	{
		return Error(strContext, "Decoded index budget exceeded.");
	}
	nDecodedBytes += nIndexCount * sizeof(std::uint32_t);
	stPrimitive.arrVertices.resize(stPosition.nCount);
	for (std::size_t nVertex = 0; nVertex < stPosition.nCount; ++nVertex)
	{
		MeshVertex &stVertex = stPrimitive.arrVertices[nVertex];
		if (!Values(stPosition, nVertex, stVertex.arrPosition.data()) ||
			(nNormal >= 0 && !Values(arrAccessors[static_cast<std::size_t>(nNormal)], nVertex, stVertex.arrNormal.data())) ||
			(nTangent >= 0 && !Values(arrAccessors[static_cast<std::size_t>(nTangent)], nVertex, stVertex.arrTangent.data())) ||
			(nUv >= 0 && !Values(arrAccessors[static_cast<std::size_t>(nUv)], nVertex, stVertex.arrTexcoord.data())))
		{
			return false;
		}
		if (nTangent >= 0 && stVertex.arrTangent[3] != 1.0F && stVertex.arrTangent[3] != -1.0F)
		{
			return Error(strContext, "Tangent handedness must be +1 or -1.");
		}
	}
	for (std::size_t nIndex = 0; nIndex < nIndexCount; ++nIndex)
	{
		std::uint32_t nValue = static_cast<std::uint32_t>(nIndex);
		if (nIndices >= 0)
		{
			const Accessor &stIndex = arrAccessors[static_cast<std::size_t>(nIndices)];
			const std::uint8_t *pValue = arrBytes.data() + stIndex.nOffset + nIndex * stIndex.nStride;
			nValue = stIndex.nComponent == 5121 ? pValue[0] : stIndex.nComponent == 5123 ? static_cast<std::uint32_t>(pValue[0]) | (static_cast<std::uint32_t>(pValue[1]) << 8U)
																						 : Read32(pValue);
		}
		if (nValue >= stPosition.nCount)
		{
			return Error(strContext, "Index lies outside vertex data.");
		}
		stPrimitive.arrIndices.push_back(nValue);
	}
	if (nNormal < 0)
	{
		// glTF requires flat normals when NORMAL is absent. Split indexed
		// vertices so adjacent faces cannot accidentally share a smoothed normal.
		const std::size_t nOldVertexBytes = stPrimitive.arrVertices.size() * sizeof(MeshVertex);
		if (nIndexCount > (MAX_DECODED_BYTES - nDecodedBytes + nOldVertexBytes) / sizeof(MeshVertex))
		{
			return Error(strContext, "Flat-normal vertex expansion exceeds budget.");
		}
		std::vector<MeshVertex> arrExpanded;
		arrExpanded.reserve(nIndexCount);
		for (std::uint32_t nIndex : stPrimitive.arrIndices)
		{
			arrExpanded.push_back(stPrimitive.arrVertices[nIndex]);
		}
		stPrimitive.arrVertices = std::move(arrExpanded);
		for (std::size_t nIndex = 0; nIndex < nIndexCount; ++nIndex)
		{
			stPrimitive.arrIndices[nIndex] = static_cast<std::uint32_t>(nIndex);
		}
		nDecodedBytes = nDecodedBytes - nOldVertexBytes + nIndexCount * sizeof(MeshVertex);
	}
	if (!GenerateBasis(stPrimitive, nNormal < 0, nNormal < 0 || nTangent < 0, nUv >= 0))
	{
		return false;
	}
	out_stMesh.arrPrimitives.push_back(std::move(stPrimitive));
	return true;
}

bool Decoder::ReadMeshes(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh)
{
	const JsonValue::List *pMeshes = nullptr;
	if (!List(mapRoot, "meshes", pMeshes) || pMeshes == nullptr || pMeshes->empty())
	{
		return Error("$.meshes", "At least one mesh is required.");
	}
	out_stMesh.arrMaterials.push_back(MaterialData{});
	for (std::size_t nMesh = 0; nMesh < pMeshes->size(); ++nMesh)
	{
		strContext = "$.meshes[" + std::to_string(nMesh) + "]";
		const JsonValue::Object *pMesh = (*pMeshes)[nMesh].GetObject();
		const JsonValue::List *pPrimitives = nullptr;
		if (pMesh == nullptr || Find(*pMesh, "weights") != nullptr || !List(*pMesh, "primitives", pPrimitives) || pPrimitives == nullptr || pPrimitives->empty())
		{
			return Error(strContext, "Mesh requires primitives and cannot use morph weights.", "gltf_unsupported");
		}
		std::vector<std::uint32_t> arrPrimitiveIds;
		for (std::size_t nPrimitive = 0; nPrimitive < pPrimitives->size(); ++nPrimitive)
		{
			strContext = "$.meshes[" + std::to_string(nMesh) + "].primitives[" + std::to_string(nPrimitive) + "]";
			const JsonValue::Object *pPrimitive = (*pPrimitives)[nPrimitive].GetObject();
			if (pPrimitive == nullptr || out_stMesh.arrPrimitives.size() >= MAX_ITEMS)
			{
				return Error(strContext, "Invalid primitive or primitive budget exceeded.");
			}
			arrPrimitiveIds.push_back(static_cast<std::uint32_t>(out_stMesh.arrPrimitives.size()));
			if (!ReadPrimitive(*pPrimitive, out_stMesh))
			{
				return false;
			}
		}
		arrMeshPrimitives.push_back(std::move(arrPrimitiveIds));
	}
	return true;
}

bool Decoder::Transform(const JsonValue::Object &mapNode, Matrix &out_arrTransform)
{
	const JsonValue *pMatrix = Find(mapNode, "matrix");
	if (pMatrix != nullptr)
	{
		if (Find(mapNode, "translation") != nullptr || Find(mapNode, "rotation") != nullptr || Find(mapNode, "scale") != nullptr)
		{
			return Error(strContext, "Node matrix and TRS are mutually exclusive.");
		}
		const JsonValue::List *pValues = pMatrix->GetList();
		if (pValues == nullptr || pValues->size() != 16)
		{
			return Error(strContext, "Node matrix requires 16 numbers.");
		}
		for (std::size_t nIndex = 0; nIndex < 16; ++nIndex)
		{
			if (!(*pValues)[nIndex].GetNumber(out_arrTransform[nIndex]) || !std::isfinite(out_arrTransform[nIndex]))
			{
				return Error(strContext, "Node matrix must be finite.");
			}
		}
		if (std::abs(out_arrTransform[3]) > 1.0e-10 || std::abs(out_arrTransform[7]) > 1.0e-10 || std::abs(out_arrTransform[11]) > 1.0e-10 || std::abs(out_arrTransform[15] - 1) > 1.0e-10)
		{
			return Error(strContext, "Node matrix must be affine.");
		}
		out_arrTransform[3] = 0;
		out_arrTransform[7] = 0;
		out_arrTransform[11] = 0;
		out_arrTransform[15] = 1;
	}
	else
	{
		std::array<float, 3> arrTranslation{};
		std::array<float, 3> arrScale{ 1, 1, 1 };
		std::array<float, 4> arrRotation{ 0, 0, 0, 1 };
		const double dMax = std::numeric_limits<float>::max();
		if (!Factors(mapNode, "translation", arrTranslation.data(), 3, -dMax, dMax) || !Factors(mapNode, "scale", arrScale.data(), 3, -dMax, dMax) || !Factors(mapNode, "rotation", arrRotation.data(), 4, -1, 1))
		{
			return false;
		}
		const double dX = arrRotation[0];
		const double dY = arrRotation[1];
		const double dZ = arrRotation[2];
		const double dW = arrRotation[3];
		if (std::abs(dX * dX + dY * dY + dZ * dZ + dW * dW - 1) > 1.0e-4)
		{
			return Error(strContext, "Node quaternion must be normalized.");
		}
		out_arrTransform = Matrix{ (1 - 2 * (dY * dY + dZ * dZ)) * arrScale[0], 2 * (dX * dY + dZ * dW) * arrScale[0], 2 * (dX * dZ - dY * dW) * arrScale[0], 0,
								   2 * (dX * dY - dZ * dW) * arrScale[1], (1 - 2 * (dX * dX + dZ * dZ)) * arrScale[1], 2 * (dY * dZ + dX * dW) * arrScale[1], 0,
								   2 * (dX * dZ + dY * dW) * arrScale[2], 2 * (dY * dZ - dX * dW) * arrScale[2], (1 - 2 * (dX * dX + dY * dY)) * arrScale[2], 0,
								   arrTranslation[0], arrTranslation[1], arrTranslation[2], 1 };
	}
	const Matrix &arrM = out_arrTransform;
	const double dDeterminant = arrM[0] * (arrM[5] * arrM[10] - arrM[9] * arrM[6]) - arrM[4] * (arrM[1] * arrM[10] - arrM[9] * arrM[2]) + arrM[8] * (arrM[1] * arrM[6] - arrM[5] * arrM[2]);
	return (std::isfinite(dDeterminant) && std::abs(dDeterminant) > 1.0e-20) || Error(strContext, "Node transform is singular or exceeds numeric range.");
}

bool Decoder::WalkNode(std::uint32_t nNode, const Matrix &arrParent, std::size_t nDepth, const JsonValue::List &arrNodes, DecodedMesh &out_stMesh)
{
	strContext = "$.nodes[" + std::to_string(nNode) + "]";
	if (nDepth > MAX_DEPTH || arrNodeState[nNode] != 0)
	{
		return Error(strContext, "Node hierarchy is cyclic, repeated, or too deep.");
	}
	arrNodeState[nNode] = 1;
	const JsonValue::Object &mapNode = *arrNodes[nNode].GetObject();
	Matrix arrLocal = Identity();
	if (!Transform(mapNode, arrLocal))
	{
		return false;
	}
	const Matrix arrWorld = Multiply(arrParent, arrLocal);
	for (double dValue : arrWorld)
	{
		if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
		{
			return Error(strContext, "Composed transform exceeds the rendering coordinate range.");
		}
	}
	std::int64_t nMesh = -1;
	if (!Integer(mapNode, "mesh", -1, nMesh) || nMesh < -1 || nMesh >= static_cast<std::int64_t>(arrMeshPrimitives.size()) || (nMesh == -1 && Find(mapNode, "mesh") != nullptr))
	{
		return Error(strContext, "Invalid node mesh index.");
	}
	if (nMesh >= 0)
	{
		for (std::uint32_t nPrimitive : arrMeshPrimitives[static_cast<std::size_t>(nMesh)])
		{
			if (out_stMesh.arrInstances.size() >= MAX_ITEMS)
			{
				return Error(strContext, "Instance budget exceeded.");
			}
			out_stMesh.arrInstances.push_back(MeshInstance{ nPrimitive, nNode, arrWorld });
		}
	}
	const JsonValue::List *pChildren = nullptr;
	if (!List(mapNode, "children", pChildren))
	{
		return false;
	}
	if (pChildren != nullptr)
	{
		for (const JsonValue &stChild : *pChildren)
		{
			std::int64_t nChild = -1;
			if (!stChild.GetInteger(nChild) || nChild < 0 || nChild >= static_cast<std::int64_t>(arrNodes.size()) || !WalkNode(static_cast<std::uint32_t>(nChild), arrWorld, nDepth + 1, arrNodes, out_stMesh))
			{
				return Error(strContext, "Invalid child node.");
			}
		}
	}
	arrNodeState[nNode] = 2;
	return true;
}

bool Decoder::ReadInstances(const JsonValue::Object &mapRoot, DecodedMesh &out_stMesh)
{
	const JsonValue::List *pNodes = nullptr;
	const JsonValue::List *pScenes = nullptr;
	if (!List(mapRoot, "nodes", pNodes) || !List(mapRoot, "scenes", pScenes))
	{
		return false;
	}
	if (pNodes == nullptr)
	{
		if (pScenes != nullptr || Find(mapRoot, "scene") != nullptr)
		{
			return Error("$.nodes", "Scene roots require a node array.");
		}
		for (std::uint32_t nPrimitive = 0; nPrimitive < out_stMesh.arrPrimitives.size(); ++nPrimitive)
		{
			out_stMesh.arrInstances.push_back(MeshInstance{ nPrimitive, 0, Identity() });
		}
		return true;
	}
	std::vector<std::uint32_t> arrParents(pNodes->size(), 0);
	for (std::size_t nNode = 0; nNode < pNodes->size(); ++nNode)
	{
		strContext = "$.nodes[" + std::to_string(nNode) + "]";
		const JsonValue::Object *pNode = (*pNodes)[nNode].GetObject();
		const JsonValue::List *pChildren = nullptr;
		Matrix arrValidated = Identity();
		if (pNode == nullptr || Find(*pNode, "skin") != nullptr || Find(*pNode, "weights") != nullptr || Find(*pNode, "camera") != nullptr || !List(*pNode, "children", pChildren) || !Transform(*pNode, arrValidated))
		{
			return Error(strContext, "Invalid node or unsupported skin, morph, or embedded camera.", "gltf_unsupported");
		}
		if (pChildren != nullptr)
		{
			for (const JsonValue &stValue : *pChildren)
			{
				std::int64_t nChild = -1;
				if (!stValue.GetInteger(nChild) || nChild < 0 || nChild >= static_cast<std::int64_t>(pNodes->size()) || ++arrParents[static_cast<std::size_t>(nChild)] > 1)
				{
					return Error(strContext, "Child node is invalid or has multiple parents.");
				}
			}
		}
	}
	arrNodeState.assign(pNodes->size(), 0);
	// Validate every hierarchy, including nodes outside the selected scene.
	DecodedMesh stValidation;
	for (std::uint32_t nNode = 0; nNode < pNodes->size(); ++nNode)
	{
		if (arrParents[nNode] == 0 && !WalkNode(nNode, Identity(), 0, *pNodes, stValidation))
		{
			return false;
		}
	}
	if (std::find(arrNodeState.begin(), arrNodeState.end(), 0) != arrNodeState.end())
	{
		return Error("$.nodes", "Node hierarchy contains a cycle.");
	}
	arrNodeState.assign(pNodes->size(), 0);
	std::vector<std::uint32_t> arrRoots;
	if (pScenes != nullptr)
	{
		std::int64_t nScene = 0;
		if (!Integer(mapRoot, "scene", 0, nScene) || nScene < 0 || nScene >= static_cast<std::int64_t>(pScenes->size()))
		{
			return Error("$.scene", "Invalid default scene.");
		}
		const JsonValue::Object *pScene = (*pScenes)[static_cast<std::size_t>(nScene)].GetObject();
		const JsonValue::List *pRoots = nullptr;
		if (pScene == nullptr || !List(*pScene, "nodes", pRoots))
		{
			return Error("$.scenes", "Invalid scene.");
		}
		if (pRoots != nullptr)
		{
			for (const JsonValue &stValue : *pRoots)
			{
				std::int64_t nRoot = -1;
				if (!stValue.GetInteger(nRoot) || nRoot < 0 || nRoot >= static_cast<std::int64_t>(pNodes->size()) || arrParents[static_cast<std::size_t>(nRoot)] != 0)
				{
					return Error("$.scenes.nodes", "Scene root is invalid or has a parent.");
				}
				arrRoots.push_back(static_cast<std::uint32_t>(nRoot));
			}
		}
	}
	else
	{
		if (Find(mapRoot, "scene") != nullptr)
		{
			return Error("$.scene", "Default scene requires scenes.");
		}
		for (std::uint32_t nNode = 0; nNode < pNodes->size(); ++nNode)
		{
			if (arrParents[nNode] == 0)
			{
				arrRoots.push_back(nNode);
			}
		}
	}
	for (std::uint32_t nRoot : arrRoots)
	{
		if (!WalkNode(nRoot, Identity(), 0, *pNodes, out_stMesh))
		{
			return false;
		}
	}
	return !out_stMesh.arrInstances.empty() || Error("$.scenes", "Selected scene has no drawable instances.");
}

bool Decoder::Run(DecodedMesh &out_stMesh)
{
	Assets::BlobInfo stInfo;
	if (!Assets::ValidateBlob("model/gltf-binary", arrBytes, stInfo, arrDiagnostics))
	{
		return false;
	}
	const std::size_t nJsonLength = Read32(arrBytes.data() + 12);
	nBinaryOffset = 20 + nJsonLength + 8;
	JsonValue stDocument;
	std::string strError;
	if (!Serialization::ParseJson(std::string(reinterpret_cast<const char *>(arrBytes.data() + 20), nJsonLength), stDocument, strError))
	{
		return Error("$", "Unable to decode validated GLB JSON.");
	}
	const JsonValue::Object &mapRoot = *stDocument.GetObject();
	const JsonValue *pAssetValue = Find(mapRoot, "asset");
	const JsonValue::Object *pAsset = pAssetValue == nullptr ? nullptr : pAssetValue->GetObject();
	const JsonValue *pVersionValue = pAsset == nullptr ? nullptr : Find(*pAsset, "version");
	const std::string *pVersion = pVersionValue == nullptr ? nullptr : pVersionValue->GetString();
	if (pVersion == nullptr || *pVersion != "2.0")
	{
		return Error("$.asset.version", "Rendering requires glTF 2.0 metadata.");
	}
	const JsonValue *pMinimumVersionValue = Find(*pAsset, "minVersion");
	const std::string *pMinimumVersion = pMinimumVersionValue == nullptr ? nullptr : pMinimumVersionValue->GetString();
	if (pMinimumVersionValue != nullptr && (pMinimumVersion == nullptr || *pMinimumVersion != "2.0"))
	{
		return Error("$.asset.minVersion", "The asset requires a different glTF version.", "gltf_unsupported");
	}
	for (const char *pUnsupported : { "extensionsRequired", "skins", "animations" })
	{
		const JsonValue::List *pList = nullptr;
		if (!List(mapRoot, pUnsupported, pList) || (pList != nullptr && !pList->empty()))
		{
			return Error(std::string("$.") + pUnsupported, "Required extensions, skinning and animation await their rendering implementation.", "gltf_unsupported");
		}
	}
	DecodedMesh stResult;
	if (!RejectUnsupported(stDocument, "$", 0) || !ReadLayouts(mapRoot) || !ReadImages(mapRoot, stResult) || !ReadTextures(mapRoot, stResult) || !ReadMaterials(mapRoot, stResult) || !ReadMeshes(mapRoot, stResult) || !ReadInstances(mapRoot, stResult))
	{
		return false;
	}
	out_stMesh = std::move(stResult);
	return true;
}

} // namespace

bool DecodeGlb(const std::vector<std::uint8_t> &arrBytes, DecodedMesh &out_stMesh, Assets::Diagnostics &out_arrDiagnostics)
{
	Decoder stDecoder(arrBytes, out_arrDiagnostics);
	return stDecoder.Run(out_stMesh);
}

} // namespace EngineNext::Rendering
