/**************************************************************************/
/*  GpuPagedPackage.cpp                                                   */
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

#include "engine_next/Rendering/Cook/GpuPagedPackage.h"

#include "engine_next/Assets/AssetValidation.h"
#include "engine_next/Rendering/Cook/GpuPackageCodec.h"
#include "engine_next/Rendering/Cook/GpuPackage.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <set>
#include <string>
#include <vector>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
namespace fs = std::filesystem;
using Serialization::JsonValue;
constexpr std::uint32_t MESH_MAGIC = 0x3348534d;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "gpu_pages", "$", pMessage);
	return false;
}

bool ValidLimits(const GpuPageLimits &stLimits)
{
	return stLimits.nMaximumIndexBytes > 0 && stLimits.nMaximumIndexBytes <= 32ULL * 1024 * 1024 &&
			stLimits.nMaximumPageBytes > 0 && stLimits.nMaximumPageBytes <= 512ULL * 1024 * 1024 &&
			stLimits.nMaximumPayloadBytes > 0 && stLimits.nMaximumPayloadBytes <= 1024ULL * 1024 * 1024 &&
			stLimits.nMaximumPinnedBytes > 0 && stLimits.nMaximumPages > 0 && stLimits.nMaximumPages <= 262144 &&
			stLimits.nMaximumSourceDistanceTests <= 256000000;
}

bool ReadWhole(const fs::path &stPath, std::uint64_t nLimit, std::vector<std::uint8_t> &out_arrBytes)
{
	std::error_code stError;
	if (!Assets::NoLinkedComponents(stPath) || !fs::is_regular_file(stPath, stError) || stError)
	{
		return false;
	}
	const std::uintmax_t nBytes = fs::file_size(stPath, stError);
	if (stError || nBytes == 0 || nBytes > nLimit)
	{
		return false;
	}
	std::ifstream stStream(stPath, std::ios::binary);
	std::vector<std::uint8_t> arrBytes(static_cast<std::size_t>(nBytes));
	stStream.read(reinterpret_cast<char *>(arrBytes.data()), static_cast<std::streamsize>(nBytes));
	if (!stStream || stStream.peek() != std::char_traits<char>::eof())
	{
		return false;
	}
	out_arrBytes = std::move(arrBytes);
	return true;
}

bool ExactFiles(const fs::path &stRoot, const std::string &strMetadata, const std::string &strPayload)
{
	std::set<std::string> setFiles{ "GpuManifest.json", "metadata/" + strMetadata, "blobs/" + strPayload };
	std::error_code stError;
	fs::recursive_directory_iterator itFile(stRoot, fs::directory_options::none, stError);
	const fs::recursive_directory_iterator itEnd;
	std::uint32_t nEntries = 0;
	while (!stError && itFile != itEnd)
	{
		if (++nEntries > 5 || itFile->is_symlink(stError) || stError)
		{
			return false;
		}
		const std::string strRelative = itFile->path().lexically_relative(stRoot).generic_u8string();
		if (itFile->is_directory(stError))
		{
			if (strRelative != "metadata" && strRelative != "blobs")
			{
				return false;
			}
		}
		else if (stError || !itFile->is_regular_file(stError) || stError || setFiles.erase(strRelative) != 1)
		{
			return false;
		}
		itFile.increment(stError);
	}
	return !stError && setFiles.empty();
}

bool WriteWhole(const fs::path &stPath, const std::uint8_t *pBytes, std::size_t nBytes)
{
	std::ofstream stStream(stPath, std::ios::binary);
	stStream.write(reinterpret_cast<const char *>(pBytes), static_cast<std::streamsize>(nBytes));
	stStream.flush();
	stStream.close();
	return stStream.good();
}

bool Uint(const JsonValue::Object &mapValue, const char *pName, std::uint64_t nMaximum, std::uint64_t &out_nValue, Assets::Diagnostics &out_arrDiagnostics)
{
	std::int64_t nValue = 0;
	if (!Assets::Integer(mapValue, pName, "$", nValue, out_arrDiagnostics) || nValue < 0 || static_cast<std::uint64_t>(nValue) > nMaximum)
	{
		return false;
	}
	out_nValue = static_cast<std::uint64_t>(nValue);
	return true;
}

bool Uint32(const JsonValue::Object &mapValue, const char *pName, std::uint32_t &out_nValue, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint64_t nValue = 0;
	if (!Uint(mapValue, pName, UINT32_MAX, nValue, out_arrDiagnostics))
	{
		return false;
	}
	out_nValue = static_cast<std::uint32_t>(nValue);
	return true;
}

const JsonValue::List *List(const JsonValue::Object &mapValue, const char *pName)
{
	const JsonValue::Object::const_iterator itValue = mapValue.find(pName);
	return itValue == mapValue.end() ? nullptr : itValue->second.GetList();
}

JsonValue Integer(std::uint64_t nValue)
{
	return JsonValue(static_cast<std::int64_t>(nValue));
}

JsonValue VectorJson(const std::array<double, 3> &arrValue)
{
	return JsonValue::List{ JsonValue(arrValue[0]), JsonValue(arrValue[1]), JsonValue(arrValue[2]) };
}

bool Vector(const JsonValue::Object &mapValue, const char *pName, std::array<double, 3> &out_arrValue)
{
	const JsonValue::Object::const_iterator itValue = mapValue.find(pName);
	const JsonValue::List *pValues = itValue == mapValue.end() ? nullptr : itValue->second.GetList();
	if (pValues == nullptr || pValues->size() != 3)
	{
		return false;
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!(*pValues)[nAxis].GetNumber(out_arrValue[nAxis]) || !std::isfinite(out_arrValue[nAxis]) || std::abs(out_arrValue[nAxis]) > std::numeric_limits<float>::max())
		{
			return false;
		}
	}
	return true;
}

void WriteUint(std::vector<std::uint8_t> &out_arrBytes, std::uint32_t nValue)
{
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> (nByte * 8)));
	}
}

void WriteFloat(std::vector<std::uint8_t> &out_arrBytes, float fValue)
{
	std::uint32_t nBits = 0;
	std::memcpy(&nBits, &fValue, sizeof(nBits));
	WriteUint(out_arrBytes, nBits);
}

std::uint32_t ReadUint(const std::vector<std::uint8_t> &arrBytes, std::size_t nOffset)
{
	return static_cast<std::uint32_t>(arrBytes[nOffset]) | (static_cast<std::uint32_t>(arrBytes[nOffset + 1]) << 8) |
			(static_cast<std::uint32_t>(arrBytes[nOffset + 2]) << 16) | (static_cast<std::uint32_t>(arrBytes[nOffset + 3]) << 24);
}

bool MeshBytes(const MeshPrimitive &stPrimitive, const LodGeometry &stGeometry, std::uint32_t nAsset, std::uint32_t nPrimitive,
			   std::uint32_t nNode, std::uint64_t nLimit, std::vector<std::uint8_t> &out_arrBytes)
{
	std::vector<std::uint32_t> arrVertices = stGeometry.arrIndices;
	std::sort(arrVertices.begin(), arrVertices.end());
	arrVertices.erase(std::unique(arrVertices.begin(), arrVertices.end()), arrVertices.end());
	const std::uint64_t nBytes = 24 + static_cast<std::uint64_t>(arrVertices.size()) * 52 + static_cast<std::uint64_t>(stGeometry.arrIndices.size()) * 4;
	if (nBytes > nLimit)
	{
		return false;
	}
	std::vector<std::uint8_t> arrBytes;
	arrBytes.reserve(static_cast<std::size_t>(nBytes));
	for (std::uint32_t nValue : { MESH_MAGIC, nAsset, nPrimitive, nNode, static_cast<std::uint32_t>(arrVertices.size()), static_cast<std::uint32_t>(stGeometry.arrIndices.size()) })
	{
		WriteUint(arrBytes, nValue);
	}
	for (std::uint32_t nVertex : arrVertices)
	{
		WriteUint(arrBytes, nVertex);
		const MeshVertex &stVertex = stPrimitive.arrVertices[nVertex];
		for (float fValue : stVertex.arrPosition)
		{
			WriteFloat(arrBytes, fValue);
		}
		for (float fValue : stVertex.arrNormal)
		{
			WriteFloat(arrBytes, fValue);
		}
		for (float fValue : stVertex.arrTangent)
		{
			WriteFloat(arrBytes, fValue);
		}
		for (float fValue : stVertex.arrTexcoord)
		{
			WriteFloat(arrBytes, fValue);
		}
	}
	for (std::uint32_t nIndex : stGeometry.arrIndices)
	{
		WriteUint(arrBytes, static_cast<std::uint32_t>(std::lower_bound(arrVertices.begin(), arrVertices.end(), nIndex) - arrVertices.begin()));
	}
	out_arrBytes = std::move(arrBytes);
	return true;
}

bool ValidateMeshBytes(const GpuPageDescription &stPage, const GpuLodTree &stTree, const std::vector<std::uint8_t> &arrBytes)
{
	if (arrBytes.size() < 24 || ReadUint(arrBytes, 0) != MESH_MAGIC || ReadUint(arrBytes, 4) != stPage.nAsset ||
		ReadUint(arrBytes, 8) != stPage.nItem || ReadUint(arrBytes, 12) != stPage.nLevel)
	{
		return false;
	}
	const std::uint32_t nVertices = ReadUint(arrBytes, 16);
	const std::uint32_t nIndices = ReadUint(arrBytes, 20);
	if (nVertices == 0 || nIndices == 0 || nIndices % 3 != 0 || nVertices > stTree.nSourceVertices ||
		24ULL + static_cast<std::uint64_t>(nVertices) * 52 + static_cast<std::uint64_t>(nIndices) * 4 != arrBytes.size())
	{
		return false;
	}
	std::uint32_t nPreviousVertex = 0;
	for (std::uint32_t nVertex = 0; nVertex < nVertices; ++nVertex)
	{
		const std::size_t nStart = 24 + static_cast<std::size_t>(nVertex) * 52;
		const std::uint32_t nSource = ReadUint(arrBytes, nStart);
		if (nSource >= stTree.nSourceVertices || (nVertex != 0 && nSource <= nPreviousVertex))
		{
			return false;
		}
		nPreviousVertex = nSource;
		std::array<float, 12> arrValues{};
		for (std::size_t nComponent = 0; nComponent < arrValues.size(); ++nComponent)
		{
			const std::uint32_t nBits = ReadUint(arrBytes, nStart + 4 + nComponent * 4);
			std::memcpy(&arrValues[nComponent], &nBits, sizeof(nBits));
			if (!std::isfinite(arrValues[nComponent]))
			{
				return false;
			}
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			const LodNode &stNode = stTree.arrNodes[stPage.nLevel];
			if (arrValues[nAxis] < stNode.arrMinimum[nAxis] || arrValues[nAxis] > stNode.arrMaximum[nAxis])
			{
				return false;
			}
		}
		double dNormal = 0;
		double dTangent = 0;
		double dDot = 0;
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			dNormal += static_cast<double>(arrValues[3 + nAxis]) * arrValues[3 + nAxis];
			dTangent += static_cast<double>(arrValues[6 + nAxis]) * arrValues[6 + nAxis];
			dDot += static_cast<double>(arrValues[3 + nAxis]) * arrValues[6 + nAxis];
		}
		if (std::abs(dNormal - 1) > .001 || std::abs(dTangent - 1) > .001 || std::abs(dDot) > .001 || (arrValues[9] != -1 && arrValues[9] != 1))
		{
			return false;
		}
	}
	const std::size_t nIndexStart = 24 + static_cast<std::size_t>(nVertices) * 52;
	for (std::uint32_t nIndex = 0; nIndex < nIndices; ++nIndex)
	{
		if (ReadUint(arrBytes, nIndexStart + static_cast<std::size_t>(nIndex) * 4) >= nVertices)
		{
			return false;
		}
	}
	return true;
}

bool ParsePages(const JsonValue::List &arrValues, const GpuPageLimits &stLimits, std::uint64_t nPayloadBytes,
				std::vector<GpuPageDescription> &out_arrPages, Assets::Diagnostics &out_arrDiagnostics)
{
	if (arrValues.empty() || arrValues.size() > stLimits.nMaximumPages)
	{
		return false;
	}
	std::uint64_t nNextOffset = 0;
	std::set<std::array<std::uint32_t, 4>> setKeys;
	for (const JsonValue &stValue : arrValues)
	{
		const JsonValue::Object *pPage = stValue.GetObject();
		GpuPageDescription stPage;
		std::uint32_t nKind = 0;
		if (pPage == nullptr || !Assets::Fields(*pPage, { "kind", "asset", "item", "level", "width", "height", "offset", "bytes", "sha256", "pinned" }, "$", out_arrDiagnostics) ||
			!Uint32(*pPage, "kind", nKind, out_arrDiagnostics) || nKind < 1 || nKind > 3 ||
			!Uint32(*pPage, "asset", stPage.nAsset, out_arrDiagnostics) || !Uint32(*pPage, "item", stPage.nItem, out_arrDiagnostics) ||
			!Uint32(*pPage, "level", stPage.nLevel, out_arrDiagnostics) || !Uint(*pPage, "offset", nPayloadBytes, stPage.nOffset, out_arrDiagnostics) ||
			!Uint32(*pPage, "width", stPage.nWidth, out_arrDiagnostics) || !Uint32(*pPage, "height", stPage.nHeight, out_arrDiagnostics) ||
			(nKind == 1 ? (stPage.nWidth != 0 || stPage.nHeight != 0) : (stPage.nWidth == 0 || stPage.nHeight == 0 || stPage.nWidth > 8192 || stPage.nHeight > 8192)) ||
			!Uint(*pPage, "bytes", stLimits.nMaximumPageBytes, stPage.nBytes, out_arrDiagnostics) || stPage.nBytes == 0 ||
			!Assets::String(*pPage, "sha256", "$", stPage.strDigest, out_arrDiagnostics) || !Assets::IsSha256(stPage.strDigest) ||
			pPage->find("pinned") == pPage->end() || !pPage->at("pinned").GetBool(stPage.bPinned) ||
			stPage.nOffset != nNextOffset || stPage.nBytes > nPayloadBytes - nNextOffset ||
			!setKeys.insert({ nKind, stPage.nAsset, stPage.nItem, stPage.nLevel }).second)
		{
			return false;
		}
		stPage.eKind = static_cast<GpuPageKind>(nKind);
		nNextOffset += stPage.nBytes;
		out_arrPages.push_back(std::move(stPage));
	}
	return nNextOffset == nPayloadBytes;
}

bool ParseTrees(const JsonValue::List &arrValues, const RenderScene &stMetadata, const std::vector<GpuPageDescription> &arrPages,
				std::vector<GpuLodTree> &out_arrTrees, Assets::Diagnostics &out_arrDiagnostics)
{
	std::size_t nExpectedTrees = 0;
	for (const RenderAsset &stAsset : stMetadata.arrAssets)
	{
		nExpectedTrees += stAsset.stMesh.arrPrimitives.size();
	}
	if (arrValues.size() != nExpectedTrees)
	{
		return false;
	}
	std::set<std::array<std::uint32_t, 2>> setKeys;
	std::set<std::uint32_t> setMeshPages;
	for (const JsonValue &stValue : arrValues)
	{
		const JsonValue::Object *pTree = stValue.GetObject();
		GpuLodTree stTree;
		if (pTree == nullptr || !Assets::Fields(*pTree, { "asset", "primitive", "source_vertices", "source_triangles", "nodes", "roots" }, "$", out_arrDiagnostics) ||
			!Uint32(*pTree, "asset", stTree.nAsset, out_arrDiagnostics) || stTree.nAsset >= stMetadata.arrAssets.size() ||
			!Uint32(*pTree, "primitive", stTree.nPrimitive, out_arrDiagnostics) || stTree.nPrimitive >= stMetadata.arrAssets[stTree.nAsset].stMesh.arrPrimitives.size() ||
			!Uint32(*pTree, "source_vertices", stTree.nSourceVertices, out_arrDiagnostics) || stTree.nSourceVertices == 0 || stTree.nSourceVertices > 6000000 ||
			!Uint32(*pTree, "source_triangles", stTree.nSourceTriangles, out_arrDiagnostics) || stTree.nSourceTriangles == 0 || stTree.nSourceTriangles > 2000000 ||
			!setKeys.insert({ stTree.nAsset, stTree.nPrimitive }).second)
		{
			return false;
		}
		const JsonValue::List *pNodes = List(*pTree, "nodes");
		const JsonValue::List *pRoots = List(*pTree, "roots");
		if (pNodes == nullptr || pNodes->empty() || pNodes->size() > arrPages.size() || pRoots == nullptr || pRoots->size() != 1)
		{
			return false;
		}
		for (const JsonValue &stNodeValue : *pNodes)
		{
			const JsonValue::Object *pNode = stNodeValue.GetObject();
			LodNode stNode;
			std::array<std::uint32_t, 2> arrSourceInterval{};
			if (pNode == nullptr || !Assets::Fields(*pNode, { "page", "minimum", "maximum", "error", "first_child", "child_count", "first_triangle", "triangle_count" }, "$", out_arrDiagnostics) ||
				!Uint32(*pNode, "page", stNode.nPage, out_arrDiagnostics) || stNode.nPage >= arrPages.size() || !setMeshPages.insert(stNode.nPage).second ||
				!Vector(*pNode, "minimum", stNode.arrMinimum) || !Vector(*pNode, "maximum", stNode.arrMaximum) ||
				!Assets::Number(*pNode, "error", "$", stNode.dGeometricErrorBound, out_arrDiagnostics) ||
				!Uint32(*pNode, "first_child", stNode.nFirstChild, out_arrDiagnostics) || !Uint32(*pNode, "child_count", stNode.nChildCount, out_arrDiagnostics) ||
				!Uint32(*pNode, "first_triangle", arrSourceInterval[0], out_arrDiagnostics) || !Uint32(*pNode, "triangle_count", arrSourceInterval[1], out_arrDiagnostics) ||
				arrSourceInterval[1] == 0 || arrSourceInterval[0] > stTree.nSourceTriangles || arrSourceInterval[1] > stTree.nSourceTriangles - arrSourceInterval[0])
			{
				return false;
			}
			const GpuPageDescription &stPage = arrPages[stNode.nPage];
			if (stPage.eKind != GpuPageKind::MeshGeometry || stPage.nAsset != stTree.nAsset || stPage.nItem != stTree.nPrimitive || stPage.nLevel != stTree.arrNodes.size())
			{
				return false;
			}
			stTree.arrNodes.push_back(stNode);
			stTree.arrSourceRanges.push_back(arrSourceInterval);
		}
		std::int64_t nRoot = 0;
		if (!(*pRoots)[0].GetInteger(nRoot) || nRoot < 0 || static_cast<std::size_t>(nRoot) >= stTree.arrNodes.size())
		{
			return false;
		}
		stTree.arrRoots.push_back(static_cast<std::uint32_t>(nRoot));
		if (stTree.arrSourceRanges[nRoot] != std::array<std::uint32_t, 2>{ 0, stTree.nSourceTriangles })
		{
			return false;
		}
		for (std::size_t nNode = 0; nNode < stTree.arrNodes.size(); ++nNode)
		{
			const LodNode &stNode = stTree.arrNodes[nNode];
			if (arrPages[stNode.nPage].bPinned != (nNode == static_cast<std::size_t>(nRoot)) || stNode.nFirstChild > stTree.arrNodes.size() || stNode.nChildCount > stTree.arrNodes.size() - stNode.nFirstChild)
			{
				return false;
			}
			std::uint32_t nNext = stTree.arrSourceRanges[nNode][0];
			for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
			{
				if (stTree.arrSourceRanges[nChild][0] != nNext || stTree.arrSourceRanges[nChild][1] > stTree.nSourceTriangles - nNext)
				{
					return false;
				}
				nNext += stTree.arrSourceRanges[nChild][1];
			}
			if (stNode.nChildCount != 0 && nNext != stTree.arrSourceRanges[nNode][0] + stTree.arrSourceRanges[nNode][1])
			{
				return false;
			}
		}
		LodSelection stSelection;
		if (!SelectLodCut(stTree.arrNodes, stTree.arrRoots, std::vector<std::uint8_t>(arrPages.size(), 1), {}, static_cast<std::uint32_t>(stTree.arrNodes.size()), stSelection, out_arrDiagnostics))
		{
			return false;
		}
		out_arrTrees.push_back(std::move(stTree));
	}
	std::size_t nMeshPages = 0;
	for (const GpuPageDescription &stPage : arrPages)
	{
		nMeshPages += stPage.eKind == GpuPageKind::MeshGeometry ? 1 : 0;
	}
	return nMeshPages == setMeshPages.size();
}

bool ValidateTexturePages(const RenderScene &stMetadata, const std::vector<GpuPageDescription> &arrPages)
{
	std::size_t nExpected = 0;
	for (const RenderAsset &stAsset : stMetadata.arrAssets)
	{
		nExpected += stAsset.stMesh.arrImages.size();
		for (const CookedTextureVariant &stVariant : stAsset.stTextureCook.arrVariants)
		{
			nExpected += stVariant.arrMips.size();
		}
	}
	std::size_t nActual = 0;
	for (const GpuPageDescription &stPage : arrPages)
	{
		if (stPage.eKind == GpuPageKind::MeshGeometry)
		{
			continue;
		}
		++nActual;
		if (stPage.nAsset >= stMetadata.arrAssets.size() || stPage.bPinned)
		{
			return false;
		}
		const RenderAsset &stAsset = stMetadata.arrAssets[stPage.nAsset];
		if (stPage.eKind == GpuPageKind::EncodedImage)
		{
			if (stPage.nItem >= stAsset.stMesh.arrImages.size() || stPage.nLevel != 0)
			{
				return false;
			}
		}
		else
		{
			if (stPage.nItem >= stAsset.stTextureCook.arrVariants.size() || stPage.nLevel >= stAsset.stTextureCook.arrVariants[stPage.nItem].arrMips.size())
			{
				return false;
			}
			const MipLevel &stMip = stAsset.stTextureCook.arrVariants[stPage.nItem].arrMips[stPage.nLevel];
			if (stPage.nBytes != static_cast<std::uint64_t>(stMip.nWidth) * stMip.nHeight * 4 || stPage.nWidth != stMip.nWidth || stPage.nHeight != stMip.nHeight)
			{
				return false;
			}
		}
	}
	return nActual == nExpected;
}
bool ValidCookSettings(const LodCookSettings &stSettings)
{
	return stSettings.nGroupSize >= 2 && stSettings.nGroupSize <= 8 && stSettings.nMaximumNodes > 0 &&
			stSettings.nMaximumNodes <= 1048576 && stSettings.nVerificationDepth <= 8 &&
			stSettings.nMaximumDistanceTests <= static_cast<std::uint64_t>(INT64_MAX) &&
			stSettings.nMaximumOutputIndices > 0 && stSettings.nMaximumOutputIndices <= 64000000 &&
			std::isfinite(stSettings.dTargetTriangleRatio) && stSettings.dTargetTriangleRatio >= .05 && stSettings.dTargetTriangleRatio <= 1 &&
			std::isfinite(stSettings.dVerificationCellRadius) && stSettings.dVerificationCellRadius > 0;
}

JsonValue CookSettingsJson(const LodCookSettings &stSettings)
{
	return JsonValue::Object{
		{ "group_size", Integer(stSettings.nGroupSize) }, { "maximum_nodes", Integer(stSettings.nMaximumNodes) }, { "verification_depth", Integer(stSettings.nVerificationDepth) }, { "maximum_distance_tests", Integer(stSettings.nMaximumDistanceTests) }, { "maximum_output_indices", Integer(stSettings.nMaximumOutputIndices) }, { "target_triangle_ratio", stSettings.dTargetTriangleRatio }, { "verification_cell_radius", stSettings.dVerificationCellRadius }
	};
}

bool ParseCookSettings(const JsonValue::Object &mapManifest, LodCookSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	const JsonValue::Object::const_iterator it = mapManifest.find("lod_settings");
	const JsonValue::Object *pSettings = it == mapManifest.end() ? nullptr : it->second.GetObject();
	if (pSettings == nullptr || !Assets::Fields(*pSettings, { "group_size", "maximum_nodes", "verification_depth", "maximum_distance_tests", "maximum_output_indices", "target_triangle_ratio", "verification_cell_radius" }, "$.lod_settings", out_arrDiagnostics))
	{
		return false;
	}
	const JsonValue::Object::const_iterator itRatio = pSettings->find("target_triangle_ratio");
	const JsonValue::Object::const_iterator itRadius = pSettings->find("verification_cell_radius");
	return Uint32(*pSettings, "group_size", out_stSettings.nGroupSize, out_arrDiagnostics) &&
			Uint32(*pSettings, "maximum_nodes", out_stSettings.nMaximumNodes, out_arrDiagnostics) &&
			Uint32(*pSettings, "verification_depth", out_stSettings.nVerificationDepth, out_arrDiagnostics) &&
			Uint(*pSettings, "maximum_distance_tests", INT64_MAX, out_stSettings.nMaximumDistanceTests, out_arrDiagnostics) &&
			Uint(*pSettings, "maximum_output_indices", 64000000, out_stSettings.nMaximumOutputIndices, out_arrDiagnostics) &&
			itRatio != pSettings->end() && itRatio->second.GetNumber(out_stSettings.dTargetTriangleRatio) &&
			itRadius != pSettings->end() && itRadius->second.GetNumber(out_stSettings.dVerificationCellRadius) && ValidCookSettings(out_stSettings);
}

std::string DescriptionDigest(const std::string &strMetadataDigest, const LodCookSettings &stSettings,
							  const JsonValue::List &arrPages, const JsonValue::List &arrTrees)
{
	std::string strCanonical;
	const JsonValue stValue(JsonValue::Object{ { "metadata_sha256", strMetadataDigest }, { "lod_settings", CookSettingsJson(stSettings) }, { "pages", arrPages }, { "trees", arrTrees } });
	if (!Serialization::CanonicalJson(stValue, strCanonical))
	{
		return {};
	}
	return Serialization::Sha256Hex(strCanonical);
}

bool BuildPagedData(const RenderScene &stPrepared, const LodCookSettings &stLodSettings, const GpuPageLimits &stLimits,
					std::vector<std::uint8_t> *pPayload, JsonValue::List &arrPages, JsonValue::List &arrTrees, std::uint64_t nDistanceBudget, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint64_t nPayloadBytes = 0;
	std::uint64_t nPinnedBytes = 0;
	std::uint64_t nDistanceTests = 0;
	const auto fnAddPage = [pPayload, &arrPages, &nPayloadBytes, &nPinnedBytes, &stLimits](GpuPageKind eKind, std::uint32_t nAsset, std::uint32_t nItem, std::uint32_t nLevel, bool bPinned, const std::vector<std::uint8_t> &arrBytes, std::uint32_t nWidth, std::uint32_t nHeight) -> bool
	{
		if (arrBytes.empty() || arrBytes.size() > stLimits.nMaximumPageBytes || arrBytes.size() > stLimits.nMaximumPayloadBytes - nPayloadBytes || arrPages.size() >= stLimits.nMaximumPages || (bPinned && arrBytes.size() > stLimits.nMaximumPinnedBytes - nPinnedBytes))
		{
			return false;
		}
		arrPages.emplace_back(JsonValue::Object{ { "kind", Integer(static_cast<std::uint32_t>(eKind)) }, { "asset", Integer(nAsset) }, { "item", Integer(nItem) }, { "level", Integer(nLevel) }, { "width", Integer(nWidth) }, { "height", Integer(nHeight) }, { "offset", Integer(nPayloadBytes) }, { "bytes", Integer(arrBytes.size()) }, { "sha256", Serialization::Sha256Hex(arrBytes.data(), arrBytes.size()) }, { "pinned", bPinned } });
		nPayloadBytes += arrBytes.size();
		if (pPayload != nullptr)
		{
			pPayload->insert(pPayload->end(), arrBytes.begin(), arrBytes.end());
		}
		if (bPinned)
		{
			nPinnedBytes += arrBytes.size();
		}
		return true;
	};
	for (std::uint32_t nAsset = 0; nAsset < stPrepared.arrAssets.size(); ++nAsset)
	{
		const RenderAsset &stAsset = stPrepared.arrAssets[nAsset];
		for (std::uint32_t nImage = 0; nImage < stAsset.stMesh.arrImages.size(); ++nImage)
		{
			Assets::BlobInfo stInfo;
			const EncodedImage &stImage = stAsset.stMesh.arrImages[nImage];
			if (!Assets::ValidateBlob(stImage.strMimeType, stImage.arrBytes, stInfo, out_arrDiagnostics) ||
				!fnAddPage(GpuPageKind::EncodedImage, nAsset, nImage, 0, false, stImage.arrBytes, stInfo.nWidth, stInfo.nHeight))
			{
				return Fail(out_arrDiagnostics, "Encoded image page exceeds budget.");
			}
		}
		for (std::uint32_t nVariant = 0; nVariant < stAsset.stTextureCook.arrVariants.size(); ++nVariant)
		{
			const CookedTextureVariant &stVariant = stAsset.stTextureCook.arrVariants[nVariant];
			for (std::uint32_t nMip = 0; nMip < stVariant.arrMips.size(); ++nMip)
			{
				if (!fnAddPage(GpuPageKind::TextureMip, nAsset, nVariant, nMip, false, stVariant.arrMips[nMip].arrRgba8, stVariant.arrMips[nMip].nWidth, stVariant.arrMips[nMip].nHeight))
				{
					return Fail(out_arrDiagnostics, "Texture mip page exceeds budget.");
				}
			}
		}
		for (std::uint32_t nPrimitive = 0; nPrimitive < stAsset.stMesh.arrPrimitives.size(); ++nPrimitive)
		{
			const MeshPrimitive &stPrimitive = stAsset.stMesh.arrPrimitives[nPrimitive];
			CookedLodHierarchy stHierarchy;
			LodCookSettings stBoundedSettings = stLodSettings;
			stBoundedSettings.nMaximumDistanceTests = (std::min)(stLodSettings.nMaximumDistanceTests, nDistanceBudget - nDistanceTests);
			if (!CookLodHierarchy(stPrimitive, stBoundedSettings, stHierarchy, out_arrDiagnostics))
			{
				return false;
			}
			if (stBoundedSettings.nMaximumDistanceTests < stLodSettings.nMaximumDistanceTests && stHierarchy.nVerificationFallbacks != 0)
			{
				return Fail(out_arrDiagnostics, "Source verification distance budget exhausted; increase the caller limit for this package.");
			}
			nDistanceTests += stHierarchy.nDistanceTests;
			JsonValue::List arrNodes;
			for (std::uint32_t nNode = 0; nNode < stHierarchy.arrNodes.size(); ++nNode)
			{
				const LodNode &stNode = stHierarchy.arrNodes[nNode];
				const LodGeometry &stGeometry = stHierarchy.arrGeometry[nNode];
				const std::uint32_t nPage = static_cast<std::uint32_t>(arrPages.size());
				const bool bPinned = std::find(stHierarchy.arrRoots.begin(), stHierarchy.arrRoots.end(), nNode) != stHierarchy.arrRoots.end();
				std::vector<std::uint8_t> arrMesh;
				if (!MeshBytes(stPrimitive, stGeometry, nAsset, nPrimitive, nNode, stLimits.nMaximumPageBytes, arrMesh) || !fnAddPage(GpuPageKind::MeshGeometry, nAsset, nPrimitive, nNode, bPinned, arrMesh, 0, 0))
				{
					return Fail(out_arrDiagnostics, "Mesh or pinned root page exceeds budget.");
				}
				arrNodes.emplace_back(JsonValue::Object{ { "page", Integer(nPage) }, { "minimum", VectorJson(stNode.arrMinimum) }, { "maximum", VectorJson(stNode.arrMaximum) }, { "error", stNode.dGeometricErrorBound }, { "first_child", Integer(stNode.nFirstChild) }, { "child_count", Integer(stNode.nChildCount) }, { "first_triangle", Integer(stGeometry.nFirstSourceTriangle) }, { "triangle_count", Integer(stGeometry.nSourceTriangleCount) } });
			}
			JsonValue::List arrRoots;
			for (std::uint32_t nRoot : stHierarchy.arrRoots)
			{
				arrRoots.push_back(Integer(nRoot));
			}
			arrTrees.emplace_back(JsonValue::Object{ { "asset", Integer(nAsset) }, { "primitive", Integer(nPrimitive) }, { "source_vertices", Integer(stPrimitive.arrVertices.size()) }, { "source_triangles", Integer(stPrimitive.arrIndices.size() / 3) }, { "nodes", std::move(arrNodes) }, { "roots", std::move(arrRoots) } });
		}
	}
	return true;
}

bool VerifyPrepared(const RenderScene &stPrepared, const GpuPageIndex &stIndex, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stPrepared.strPackageDigest != stIndex.Metadata().strPackageDigest)
	{
		return Fail(out_arrDiagnostics, "Paged source identity differs from the validated M3 package.");
	}
	std::vector<std::uint8_t> arrMetadata;
	JsonValue::List arrPages;
	JsonValue::List arrTrees;
	GpuPageLimits stLimits;
	stLimits.nMaximumPageBytes = 512ULL * 1024 * 1024;
	stLimits.nMaximumPinnedBytes = stLimits.nMaximumPayloadBytes;
	if (!EncodeGpuSceneMetadata(stPrepared, arrMetadata, out_arrDiagnostics) ||
		!BuildPagedData(stPrepared, stIndex.CookSettings(), stLimits, nullptr, arrPages, arrTrees, stIndex.SourceDistanceBudget(), out_arrDiagnostics))
	{
		return false;
	}
	const std::string strMetadataDigest = Serialization::Sha256Hex(arrMetadata.data(), arrMetadata.size());
	if (DescriptionDigest(strMetadataDigest, stIndex.CookSettings(), arrPages, arrTrees) != stIndex.DescriptionDigest())
	{
		return Fail(out_arrDiagnostics, "Paged metadata, hierarchy or payload digest differs from its canonical source Cook.");
	}
	return true;
}

const GpuLodTree *PageTree(const GpuPageIndex &stIndex, const GpuPageDescription &stPage)
{
	for (const GpuLodTree &stTree : stIndex.Trees())
	{
		if (stTree.nAsset == stPage.nAsset && stTree.nPrimitive == stPage.nItem)
		{
			return &stTree;
		}
	}
	return nullptr;
}

void CopyMeshPage(const std::vector<std::uint8_t> &arrBytes, const GpuLodTree &stTree, std::uint32_t nNode, MeshPrimitive &out_stPrimitive)
{
	const std::uint32_t nVertices = ReadUint(arrBytes, 16);
	const std::uint32_t nIndices = ReadUint(arrBytes, 20);
	for (std::uint32_t nVertex = 0; nVertex < nVertices; ++nVertex)
	{
		const std::size_t nStart = 24 + static_cast<std::size_t>(nVertex) * 52;
		MeshVertex &stVertex = out_stPrimitive.arrVertices[ReadUint(arrBytes, nStart)];
		float *arrComponents[] = { stVertex.arrPosition.data(), stVertex.arrNormal.data(), stVertex.arrTangent.data(), stVertex.arrTexcoord.data() };
		const std::size_t arrCounts[] = { 3, 3, 4, 2 };
		std::size_t nComponent = 0;
		for (std::size_t nAttribute = 0; nAttribute < 4; ++nAttribute)
		{
			for (std::size_t nValue = 0; nValue < arrCounts[nAttribute]; ++nValue, ++nComponent)
			{
				const std::uint32_t nBits = ReadUint(arrBytes, nStart + 4 + nComponent * 4);
				std::memcpy(arrComponents[nAttribute] + nValue, &nBits, sizeof(nBits));
			}
		}
	}
	const std::size_t nStart = 24 + static_cast<std::size_t>(nVertices) * 52;
	const std::size_t nOutput = static_cast<std::size_t>(stTree.arrSourceRanges[nNode][0]) * 3;
	for (std::uint32_t nIndex = 0; nIndex < nIndices; ++nIndex)
	{
		const std::uint32_t nLocal = ReadUint(arrBytes, nStart + static_cast<std::size_t>(nIndex) * 4);
		out_stPrimitive.arrIndices[nOutput + nIndex] = ReadUint(arrBytes, 24 + static_cast<std::size_t>(nLocal) * 52);
	}
}

} // namespace

const RenderScene &GpuPageIndex::Metadata() const noexcept
{
	return stMetadata;
}
const std::vector<GpuPageDescription> &GpuPageIndex::Pages() const noexcept
{
	return arrPages;
}
const std::vector<GpuLodTree> &GpuPageIndex::Trees() const noexcept
{
	return arrTrees;
}
std::uint64_t GpuPageIndex::PinnedBytes() const noexcept
{
	return nPinnedBytes;
}
std::uint64_t GpuPageIndex::IndexBytesRead() const noexcept
{
	return nIndexBytesRead;
}
const LodCookSettings &GpuPageIndex::CookSettings() const noexcept
{
	return stCookSettings;
}
const std::string &GpuPageIndex::DescriptionDigest() const noexcept
{
	return strDescriptionDigest;
}
std::uint64_t GpuPageIndex::SourceDistanceBudget() const noexcept
{
	return nSourceDistanceBudget;
}

bool LoadGpuPageIndex(const std::string &strPackage, const std::string &strExpectedSourceDigest,
					  const GpuPageLimits &stLimits, GpuPageIndex &out_stIndex, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidLimits(stLimits) || !Assets::IsSha256(strExpectedSourceDigest))
	{
		return Fail(out_arrDiagnostics, "Invalid page limits or source digest.");
	}
	std::error_code stError;
	const fs::path stRoot = fs::absolute(fs::u8path(strPackage), stError).lexically_normal();
	std::vector<std::uint8_t> arrManifest;
	if (stError || !ReadWhole(stRoot / "GpuManifest.json", stLimits.nMaximumIndexBytes, arrManifest))
	{
		return Fail(out_arrDiagnostics, "Cannot read the v3 manifest.");
	}
	const std::string strManifest(arrManifest.begin(), arrManifest.end());
	JsonValue stValue;
	std::string strError;
	std::string strCanonical;
	if (!Serialization::ParseJson(strManifest, stValue, strError) || !Serialization::CanonicalJson(stValue, strCanonical) || strCanonical != strManifest)
	{
		return Fail(out_arrDiagnostics, "Manifest is not canonical JSON.");
	}
	const JsonValue::Object *pManifest = stValue.GetObject();
	std::uint64_t nVersion = 0;
	std::uint64_t nMetadataBytes = 0;
	std::string strSource;
	std::string strMetadataDigest;
	std::string strPayloadDigest;
	GpuPageIndex stCandidate;
	if (pManifest == nullptr || !Assets::Fields(*pManifest, { "schema_version", "source_package_sha256", "metadata_sha256", "metadata_bytes", "payload_sha256", "payload_bytes", "pages", "trees", "lod_settings" }, "$", out_arrDiagnostics) ||
		!Uint(*pManifest, "schema_version", 3, nVersion, out_arrDiagnostics) || nVersion != 3 ||
		!ParseCookSettings(*pManifest, stCandidate.stCookSettings, out_arrDiagnostics) ||
		!Assets::String(*pManifest, "source_package_sha256", "$", strSource, out_arrDiagnostics) || strSource != strExpectedSourceDigest ||
		!Assets::String(*pManifest, "metadata_sha256", "$", strMetadataDigest, out_arrDiagnostics) || !Assets::IsSha256(strMetadataDigest) ||
		!Uint(*pManifest, "metadata_bytes", stLimits.nMaximumIndexBytes - arrManifest.size(), nMetadataBytes, out_arrDiagnostics) || nMetadataBytes == 0 ||
		!Assets::String(*pManifest, "payload_sha256", "$", strPayloadDigest, out_arrDiagnostics) || !Assets::IsSha256(strPayloadDigest) ||
		!Uint(*pManifest, "payload_bytes", stLimits.nMaximumPayloadBytes, stCandidate.nPayloadBytes, out_arrDiagnostics) || stCandidate.nPayloadBytes == 0)
	{
		return Fail(out_arrDiagnostics, "Invalid v3 manifest identity or byte budget.");
	}
	std::vector<std::uint8_t> arrMetadata;
	if (!ReadWhole(stRoot / "metadata" / strMetadataDigest, nMetadataBytes, arrMetadata) || arrMetadata.size() != nMetadataBytes ||
		Serialization::Sha256Hex(arrMetadata.data(), arrMetadata.size()) != strMetadataDigest ||
		!DecodeGpuSceneMetadata(arrMetadata, strSource, stCandidate.stMetadata, out_arrDiagnostics))
	{
		return Fail(out_arrDiagnostics, "Invalid metadata payload.");
	}
	const JsonValue::List *pPages = List(*pManifest, "pages");
	const JsonValue::List *pTrees = List(*pManifest, "trees");
	if (pPages == nullptr || pTrees == nullptr || !ParsePages(*pPages, stLimits, stCandidate.nPayloadBytes, stCandidate.arrPages, out_arrDiagnostics) ||
		!ParseTrees(*pTrees, stCandidate.stMetadata, stCandidate.arrPages, stCandidate.arrTrees, out_arrDiagnostics) ||
		!ValidateTexturePages(stCandidate.stMetadata, stCandidate.arrPages))
	{
		return Fail(out_arrDiagnostics, "Invalid page directory or LOD hierarchy.");
	}
	for (const GpuPageDescription &stPage : stCandidate.arrPages)
	{
		if (stPage.bPinned)
		{
			if (stPage.nBytes > stLimits.nMaximumPinnedBytes - stCandidate.nPinnedBytes)
			{
				return Fail(out_arrDiagnostics, "Root geometry exceeds the pinned budget.");
			}
			stCandidate.nPinnedBytes += stPage.nBytes;
		}
	}
	const fs::path stPayload = stRoot / "blobs" / strPayloadDigest;
	if (!Assets::NoLinkedComponents(stPayload) || !fs::is_regular_file(stPayload, stError) || stError || fs::file_size(stPayload, stError) != stCandidate.nPayloadBytes || stError)
	{
		return Fail(out_arrDiagnostics, "Payload file identity or size is invalid.");
	}
	if (!ExactFiles(stRoot, strMetadataDigest, strPayloadDigest))
	{
		return Fail(out_arrDiagnostics, "Package contains unlisted files or linked entries.");
	}
	stCandidate.strDescriptionDigest = DescriptionDigest(strMetadataDigest, stCandidate.stCookSettings, *pPages, *pTrees);
	stCandidate.nSourceDistanceBudget = stLimits.nMaximumSourceDistanceTests;
	stCandidate.strPayloadPath = stPayload.u8string();
	stCandidate.nIndexBytesRead = arrManifest.size() + arrMetadata.size();
	out_stIndex = std::move(stCandidate);
	return true;
}

bool ReadGpuPage(const GpuPageIndex &stIndex, std::uint32_t nPage, std::vector<std::uint8_t> &out_arrBytes,
				 GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics)
{
	if (nPage >= stIndex.arrPages.size() || out_stStats.nReadRequests == UINT64_MAX)
	{
		return Fail(out_arrDiagnostics, "Invalid page request.");
	}
	const GpuPageDescription &stPage = stIndex.arrPages[nPage];
	if (stPage.nBytes > UINT64_MAX - out_stStats.nBytesRead || out_stStats.nVerifiedPages == UINT64_MAX)
	{
		return Fail(out_arrDiagnostics, "Page telemetry overflow.");
	}
	const fs::path stPath = fs::u8path(stIndex.strPayloadPath);
	std::error_code stError;
	if (!Assets::NoLinkedComponents(stPath) || !fs::is_regular_file(stPath, stError) || stError || fs::file_size(stPath, stError) != stIndex.nPayloadBytes || stError)
	{
		return Fail(out_arrDiagnostics, "Payload changed since index open.");
	}
	std::ifstream stStream(stPath, std::ios::binary);
	stStream.seekg(static_cast<std::streamoff>(stPage.nOffset));
	if (!stStream)
	{
		return Fail(out_arrDiagnostics, "Page seek failed.");
	}
	std::vector<std::uint8_t> arrBytes(static_cast<std::size_t>(stPage.nBytes));
	++out_stStats.nReadRequests;
	stStream.read(reinterpret_cast<char *>(arrBytes.data()), static_cast<std::streamsize>(arrBytes.size()));
	out_stStats.nBytesRead += static_cast<std::uint64_t>(stStream.gcount());
	if (!stStream || Serialization::Sha256Hex(arrBytes.data(), arrBytes.size()) != stPage.strDigest)
	{
		return Fail(out_arrDiagnostics, "Page read or SHA-256 validation failed.");
	}
	if (stPage.eKind == GpuPageKind::MeshGeometry)
	{
		const GpuLodTree *pTree = nullptr;
		for (const GpuLodTree &stTree : stIndex.arrTrees)
		{
			if (stTree.nAsset == stPage.nAsset && stTree.nPrimitive == stPage.nItem)
			{
				pTree = &stTree;
				break;
			}
		}
		if (pTree == nullptr || !ValidateMeshBytes(stPage, *pTree, arrBytes))
		{
			return Fail(out_arrDiagnostics, "Invalid mesh page layout.");
		}
	}
	else if (stPage.eKind == GpuPageKind::EncodedImage)
	{
		Assets::BlobInfo stInfo;
		const EncodedImage &stImage = stIndex.stMetadata.arrAssets[stPage.nAsset].stMesh.arrImages[stPage.nItem];
		if (!Assets::ValidateBlob(stImage.strMimeType, arrBytes, stInfo, out_arrDiagnostics))
		{
			return false;
		}
		if (stInfo.nWidth != stPage.nWidth || stInfo.nHeight != stPage.nHeight)
		{
			return Fail(out_arrDiagnostics, "Encoded image dimensions differ from its page description.");
		}
		for (const CookedTextureVariant &stVariant : stIndex.stMetadata.arrAssets[stPage.nAsset].stTextureCook.arrVariants)
		{
			if (stVariant.nImage == stPage.nItem && (stVariant.arrMips[0].nWidth != stInfo.nWidth || stVariant.arrMips[0].nHeight != stInfo.nHeight))
			{
				return Fail(out_arrDiagnostics, "Encoded image dimensions differ from mip metadata.");
			}
		}
	}
	++out_stStats.nVerifiedPages;
	out_arrBytes = std::move(arrBytes);
	return true;
}

bool ReadGpuMeshPage(const GpuPageIndex &stIndex, std::uint32_t nPage, GpuMeshPage &out_stPage,
					 GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics)
{
	if (nPage >= stIndex.Pages().size() || stIndex.Pages()[nPage].eKind != GpuPageKind::MeshGeometry)
	{
		return Fail(out_arrDiagnostics, "Requested page is not mesh geometry.");
	}
	std::vector<std::uint8_t> arrBytes;
	if (!ReadGpuPage(stIndex, nPage, arrBytes, out_stStats, out_arrDiagnostics))
	{
		return false;
	}
	GpuMeshPage stCandidate;
	stCandidate.nAsset = ReadUint(arrBytes, 4);
	stCandidate.nPrimitive = ReadUint(arrBytes, 8);
	stCandidate.nNode = ReadUint(arrBytes, 12);
	const std::uint32_t nVertices = ReadUint(arrBytes, 16);
	const std::uint32_t nIndices = ReadUint(arrBytes, 20);
	stCandidate.arrVertices.resize(nVertices);
	stCandidate.arrSourceVertices.resize(nVertices);
	stCandidate.arrIndices.resize(nIndices);
	for (std::uint32_t nVertex = 0; nVertex < nVertices; ++nVertex)
	{
		const std::size_t nStart = 24 + static_cast<std::size_t>(nVertex) * 52;
		stCandidate.arrSourceVertices[nVertex] = ReadUint(arrBytes, nStart);
		MeshVertex &stVertex = stCandidate.arrVertices[nVertex];
		float *arrComponents[] = { stVertex.arrPosition.data(), stVertex.arrNormal.data(), stVertex.arrTangent.data(), stVertex.arrTexcoord.data() };
		const std::size_t arrCounts[] = { 3, 3, 4, 2 };
		std::size_t nComponent = 0;
		for (std::size_t nAttribute = 0; nAttribute < 4; ++nAttribute)
		{
			for (std::size_t nValue = 0; nValue < arrCounts[nAttribute]; ++nValue, ++nComponent)
			{
				const std::uint32_t nBits = ReadUint(arrBytes, nStart + 4 + nComponent * 4);
				std::memcpy(arrComponents[nAttribute] + nValue, &nBits, sizeof(nBits));
			}
		}
	}
	const std::size_t nStart = 24 + static_cast<std::size_t>(nVertices) * 52;
	for (std::uint32_t nIndex = 0; nIndex < nIndices; ++nIndex)
	{
		stCandidate.arrIndices[nIndex] = ReadUint(arrBytes, nStart + static_cast<std::size_t>(nIndex) * 4);
	}
	out_stPage = std::move(stCandidate);
	return true;
}

bool VerifyPagedScene(const RenderScene &stSource, const GpuPageIndex &stIndex, Assets::Diagnostics &out_arrDiagnostics)
{
	RenderScene stPrepared;
	return PrepareGpuSceneForPaging(stSource, stPrepared, out_arrDiagnostics) && VerifyPrepared(stPrepared, stIndex, out_arrDiagnostics);
}

bool LoadVerifiedGpuPackage(const std::string &strPackage, const RenderScene &stSource, const GpuPageLimits &stLimits,
							RenderScene &out_stScene, GpuPageReadStats &out_stStats, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidLimits(stLimits))
	{
		return Fail(out_arrDiagnostics, "Invalid GPU package limits.");
	}
	std::vector<std::uint8_t> arrManifest;
	if (!ReadWhole(fs::u8path(strPackage) / "GpuManifest.json", stLimits.nMaximumIndexBytes, arrManifest))
	{
		return Fail(out_arrDiagnostics, "Cannot read GPU package version.");
	}
	JsonValue stManifest;
	std::string strError;
	std::uint64_t nVersion = 0;
	if (!Serialization::ParseJson(std::string(arrManifest.begin(), arrManifest.end()), stManifest, strError) ||
		stManifest.GetObject() == nullptr || !Uint(*stManifest.GetObject(), "schema_version", 3, nVersion, out_arrDiagnostics))
	{
		return Fail(out_arrDiagnostics, "Invalid GPU package version.");
	}
	RenderScene stCandidate;
	if (nVersion != 3)
	{
		if (!LoadGpuPackage(strPackage, stSource.strPackageDigest, stCandidate, out_arrDiagnostics) ||
			!VerifyCookedScene(stSource, stCandidate, out_arrDiagnostics))
		{
			return false;
		}
		out_stScene = std::move(stCandidate);
		return true;
	}
	GpuPageIndex stIndex;
	if (!LoadGpuPageIndex(strPackage, stSource.strPackageDigest, stLimits, stIndex, out_arrDiagnostics) ||
		!PrepareGpuSceneForPaging(stSource, stCandidate, out_arrDiagnostics) || !VerifyPrepared(stCandidate, stIndex, out_arrDiagnostics))
	{
		return false;
	}
	// Referenced source vertices and original triangle intervals are replaced
	// by verified page data. Unreferenced vertices retain their source values.
	// The initial compatibility path loads all leaf geometry; streaming callers
	// use the same verified index without materializing its complete payload.
	for (std::uint32_t nPage = 0; nPage < stIndex.Pages().size(); ++nPage)
	{
		const GpuPageDescription &stPage = stIndex.Pages()[nPage];
		const GpuLodTree *pTree = nullptr;
		if (stPage.eKind == GpuPageKind::MeshGeometry)
		{
			pTree = PageTree(stIndex, stPage);
			if (pTree == nullptr)
			{
				return Fail(out_arrDiagnostics, "Missing mesh hierarchy during materialization.");
			}
			if (pTree->arrNodes[stPage.nLevel].nChildCount != 0)
			{
				continue;
			}
		}
		std::vector<std::uint8_t> arrBytes;
		if (!ReadGpuPage(stIndex, nPage, arrBytes, out_stStats, out_arrDiagnostics))
		{
			return false;
		}
		RenderAsset &stAsset = stCandidate.arrAssets[stPage.nAsset];
		if (stPage.eKind == GpuPageKind::MeshGeometry)
		{
			CopyMeshPage(arrBytes, *pTree, stPage.nLevel, stAsset.stMesh.arrPrimitives[stPage.nItem]);
		}
		else if (stPage.eKind == GpuPageKind::EncodedImage)
		{
			stAsset.stMesh.arrImages[stPage.nItem].arrBytes = std::move(arrBytes);
		}
		else
		{
			stAsset.stTextureCook.arrVariants[stPage.nItem].arrMips[stPage.nLevel].arrRgba8 = std::move(arrBytes);
		}
	}
	stCandidate.nGpuFormatVersion = 3;
	out_stScene = std::move(stCandidate);
	return true;
}

bool CookPagedGpuPackage(const std::string &strSourcePackage, const std::string &strTargetPackage,
						 const LodCookSettings &stLodSettings, const GpuPageLimits &stLimits, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidLimits(stLimits) || !ValidCookSettings(stLodSettings))
	{
		return Fail(out_arrDiagnostics, "Invalid v3 page or LOD limits.");
	}
	RenderScene stSource;
	RenderScene stPrepared;
	if (!LoadRenderScene(strSourcePackage, stSource, out_arrDiagnostics) || !PrepareGpuSceneForPaging(stSource, stPrepared, out_arrDiagnostics))
	{
		return false;
	}
	std::vector<std::uint8_t> arrMetadata;
	if (!EncodeGpuSceneMetadata(stPrepared, arrMetadata, out_arrDiagnostics) || arrMetadata.size() > stLimits.nMaximumIndexBytes)
	{
		return false;
	}
	std::vector<std::uint8_t> arrPayload;
	JsonValue::List arrPages;
	JsonValue::List arrTrees;
	if (!BuildPagedData(stPrepared, stLodSettings, stLimits, &arrPayload, arrPages, arrTrees, UINT64_MAX, out_arrDiagnostics))
	{
		return false;
	}
	const std::string strMetadataDigest = Serialization::Sha256Hex(arrMetadata.data(), arrMetadata.size());
	const std::string strPayloadDigest = Serialization::Sha256Hex(arrPayload.data(), arrPayload.size());
	JsonValue stManifest(JsonValue::Object{ { "schema_version", Integer(3) }, { "lod_settings", CookSettingsJson(stLodSettings) }, { "source_package_sha256", stSource.strPackageDigest }, { "metadata_sha256", strMetadataDigest }, { "metadata_bytes", Integer(arrMetadata.size()) }, { "payload_sha256", strPayloadDigest }, { "payload_bytes", Integer(arrPayload.size()) }, { "pages", std::move(arrPages) }, { "trees", std::move(arrTrees) } });
	std::string strManifest;
	if (!Serialization::CanonicalJson(stManifest, strManifest) || strManifest.size() > stLimits.nMaximumIndexBytes - arrMetadata.size())
	{
		return Fail(out_arrDiagnostics, "Index exceeds byte budget.");
	}
	std::error_code stError;
	const fs::path stTarget = fs::absolute(fs::u8path(strTargetPackage), stError).lexically_normal();
	if (stError || stTarget.filename().empty() || !Assets::NoLinkedComponents(stTarget.parent_path()))
	{
		return Fail(out_arrDiagnostics, "Invalid package parent.");
	}
	static std::atomic<std::uint64_t> nSequence{ 0 };
	fs::path stStage;
	bool bCreated = false;
	for (std::uint32_t nAttempt = 0; nAttempt < 64 && !bCreated; ++nAttempt)
	{
		const std::chrono::steady_clock::duration::rep nStamp = std::chrono::steady_clock::now().time_since_epoch().count();
		stStage = stTarget.parent_path() / (stTarget.filename().u8string() + ".staging." + std::to_string(nStamp) + "." + std::to_string(nSequence.fetch_add(1)));
		bCreated = fs::create_directory(stStage, stError);
		if (stError && stError != std::errc::file_exists)
		{
			return Fail(out_arrDiagnostics, "Cannot create staging directory.");
		}
	}
	if (!bCreated)
	{
		return Fail(out_arrDiagnostics, "Cannot reserve unique staging directory.");
	}
	bool bWritten = fs::create_directory(stStage / "metadata", stError) && !stError && fs::create_directory(stStage / "blobs", stError) && !stError;
	bWritten = bWritten && WriteWhole(stStage / "metadata" / strMetadataDigest, arrMetadata.data(), arrMetadata.size()) &&
			WriteWhole(stStage / "blobs" / strPayloadDigest, arrPayload.data(), arrPayload.size()) &&
			WriteWhole(stStage / "GpuManifest.json", reinterpret_cast<const std::uint8_t *>(strManifest.data()), strManifest.size());
	GpuPageIndex stVerify;
	bWritten = bWritten && LoadGpuPageIndex(stStage.u8string(), stSource.strPackageDigest, stLimits, stVerify, out_arrDiagnostics);
	if (bWritten)
	{
		GpuPageReadStats stStats;
		for (std::uint32_t nPage = 0; nPage < stVerify.Pages().size(); ++nPage)
		{
			std::vector<std::uint8_t> arrBytes;
			if (!ReadGpuPage(stVerify, nPage, arrBytes, stStats, out_arrDiagnostics))
			{
				bWritten = false;
				break;
			}
		}
	}
	if (bWritten && PublishGpuDirectoryNoReplace(stStage, stTarget))
	{
		return true;
	}
	fs::remove_all(stStage, stError);
	std::vector<std::uint8_t> arrExisting;
	if (bWritten && ReadWhole(stTarget / "GpuManifest.json", stLimits.nMaximumIndexBytes, arrExisting) && std::string(arrExisting.begin(), arrExisting.end()) == strManifest &&
		LoadGpuPageIndex(stTarget.u8string(), stSource.strPackageDigest, stLimits, stVerify, out_arrDiagnostics))
	{
		GpuPageReadStats stStats;
		for (std::uint32_t nPage = 0; nPage < stVerify.Pages().size(); ++nPage)
		{
			std::vector<std::uint8_t> arrBytes;
			if (!ReadGpuPage(stVerify, nPage, arrBytes, stStats, out_arrDiagnostics))
			{
				return false;
			}
		}
		return true;
	}
	return Fail(out_arrDiagnostics, "Package publication failed or target contains different content.");
}
} // namespace EngineNext::Rendering
