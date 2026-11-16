/**************************************************************************/
/*  RenderScene.cpp                                                       */
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

#include "engine_next/include/EngineNext/Rendering/RenderScene.h"
#include "engine_next/Rendering/Cook/GltfDecoder.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

using Matrix = std::array<double, 16>;

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

Matrix TransformMatrix(const Assets::Transform &stTransform)
{
	const double dX = stTransform.arrRotation[0];
	const double dY = stTransform.arrRotation[1];
	const double dZ = stTransform.arrRotation[2];
	const double dW = stTransform.arrRotation[3];
	Matrix arrResult{
		1 - 2 * (dY * dY + dZ * dZ), 2 * (dX * dY + dW * dZ), 2 * (dX * dZ - dW * dY), 0,
		2 * (dX * dY - dW * dZ), 1 - 2 * (dX * dX + dZ * dZ), 2 * (dY * dZ + dW * dX), 0,
		2 * (dX * dZ + dW * dY), 2 * (dY * dZ - dW * dX), 1 - 2 * (dX * dX + dY * dY), 0,
		stTransform.arrTranslation[0], stTransform.arrTranslation[1], stTransform.arrTranslation[2], 1
	};
	for (std::size_t nColumn = 0; nColumn < 3; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < 3; ++nRow)
		{
			arrResult[nColumn * 4 + nRow] *= stTransform.arrScale[nColumn];
		}
	}
	return arrResult;
}

bool WorldMatrix(std::int64_t nEntity, const std::map<std::int64_t, const Assets::SceneEntity *> &mapEntities, std::map<std::int64_t, Matrix> &mapWorld, std::uint32_t nDepth)
{
	if (mapWorld.find(nEntity) != mapWorld.end())
	{
		return true;
	}
	const std::map<std::int64_t, const Assets::SceneEntity *>::const_iterator it = mapEntities.find(nEntity);
	if (it == mapEntities.end() || nDepth > 256)
	{
		return false;
	}
	const Assets::SceneEntity &stEntity = *it->second;
	Matrix arrWorld = TransformMatrix(stEntity.stTransform);
	if (stEntity.nParentEntityId != 0)
	{
		if (!WorldMatrix(stEntity.nParentEntityId, mapEntities, mapWorld, nDepth + 1))
		{
			return false;
		}
		arrWorld = Multiply(mapWorld.at(stEntity.nParentEntityId), arrWorld);
	}
	for (const double dComponent : arrWorld)
	{
		if (!std::isfinite(dComponent))
		{
			return false;
		}
	}
	mapWorld.emplace(nEntity, arrWorld);
	return true;
}

} // namespace

bool BuildRenderScene(const Assets::PackageData &stPackage, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!Assets::ValidateSceneDocument(stPackage.stScene, out_arrDiagnostics) ||
		!Assets::ValidateAssetManifest(stPackage.stManifest, stPackage.stScene, out_arrDiagnostics))
	{
		return false;
	}
	std::size_t nSourceBytes = 0;
	constexpr std::size_t MAX_SOURCE_BYTES = 256ULL * 1024ULL * 1024ULL;
	for (const std::pair<const std::string, std::vector<std::uint8_t>> &stBlob : stPackage.mapBlobs)
	{
		if (stBlob.second.size() > MAX_SOURCE_BYTES - nSourceBytes)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "render_source_budget", "$", "Source package exceeds the M3 blob budget");
			return false;
		}
		nSourceBytes += stBlob.second.size();
	}
	{
		Assets::PackageData stVerified = stPackage;
		if (!Assets::ComputePackageDigest(stVerified, out_arrDiagnostics) || stVerified.strPackageDigest != stPackage.strPackageDigest)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "render_package_digest", "$", "Package identity does not match its canonical source data");
			return false;
		}
	}
	RenderScene stScene;
	stScene.strSceneId = stPackage.stScene.strSceneId;
	stScene.strSceneRevision = stPackage.stScene.strSceneRevision;
	stScene.strSceneDigest = stPackage.stManifest.strSceneContentSha256;
	stScene.strPackageDigest = stPackage.strPackageDigest;
	std::map<std::string, std::uint32_t> mapMeshAssets;
	std::size_t nDecodedBytes = 0;
	constexpr std::size_t MAX_DECODED_BYTES = 512 * 1024 * 1024;
	for (const Assets::AssetEntry &stAsset : stPackage.stManifest.arrAssets)
	{
		if (stAsset.strType != "mesh")
		{
			continue;
		}
		const std::map<std::string, std::vector<std::uint8_t>>::const_iterator it = stPackage.mapBlobs.find(stAsset.strContentSha256);
		if (it == stPackage.mapBlobs.end())
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "render_blob_missing", stAsset.strAssetId, "Mesh blob is missing from the validated package");
			return false;
		}
		if (it->second.size() != stAsset.nByteSize || Serialization::Sha256Hex(it->second.data(), it->second.size()) != stAsset.strContentSha256)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "render_blob_digest", stAsset.strAssetId, "Mesh bytes do not match the original AssetRef");
			return false;
		}
		RenderAsset stRenderAsset;
		stRenderAsset.stIdentity = { stAsset.strAssetId, stAsset.strRevision, stAsset.strContentSha256 };
		if (!DecodeGlb(it->second, stRenderAsset.stMesh, out_arrDiagnostics))
		{
			return false;
		}
		for (const EncodedImage &stImage : stRenderAsset.stMesh.arrImages)
		{
			if (stImage.arrBytes.size() > MAX_DECODED_BYTES - nDecodedBytes)
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "render_decode_budget", stAsset.strAssetId, "Decoded scene image data exceeds its memory budget");
				return false;
			}
			nDecodedBytes += stImage.arrBytes.size();
		}
		for (const MeshPrimitive &stPrimitive : stRenderAsset.stMesh.arrPrimitives)
		{
			const std::size_t nBytes = stPrimitive.arrVertices.size() * sizeof(MeshVertex) + stPrimitive.arrIndices.size() * sizeof(std::uint32_t);
			if (nBytes > MAX_DECODED_BYTES - nDecodedBytes)
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "render_decode_budget", stAsset.strAssetId, "Decoded mesh scene exceeds its memory budget");
				return false;
			}
			nDecodedBytes += nBytes;
		}
		mapMeshAssets.emplace(stAsset.strAssetId, static_cast<std::uint32_t>(stScene.arrAssets.size()));
		stScene.arrAssets.push_back(std::move(stRenderAsset));
	}
	std::map<std::int64_t, const Assets::SceneEntity *> mapEntities;
	std::map<std::int64_t, Matrix> mapWorld;
	for (const Assets::SceneEntity &stEntity : stPackage.stScene.arrEntities)
	{
		mapEntities.emplace(stEntity.nEntityId, &stEntity);
	}
	for (const Assets::SceneEntity &stEntity : stPackage.stScene.arrEntities)
	{
		if (!WorldMatrix(stEntity.nEntityId, mapEntities, mapWorld, 0))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "render_transform", stEntity.strName, "Invalid or overflowing world transform");
			return false;
		}
		for (const Assets::SceneAssetRef &stRef : stEntity.arrAssets)
		{
			if (stRef.strRole != "mesh")
			{
				continue;
			}
			const std::map<std::string, std::uint32_t>::const_iterator it = mapMeshAssets.find(stRef.stAsset.strAssetId);
			if (it == mapMeshAssets.end())
			{
				return false;
			}
			for (const MeshInstance &stInstance : stScene.arrAssets[it->second].stMesh.arrInstances)
			{
				if (stScene.arrInstances.size() >= 65536)
				{
					Assets::AddDiagnostic(out_arrDiagnostics, "render_instance_budget", stEntity.strName, "Expanded render instance budget exceeded");
					return false;
				}
				const Matrix arrWorld = Multiply(mapWorld.at(stEntity.nEntityId), stInstance.arrTransform);
				for (const double dComponent : arrWorld)
				{
					if (!std::isfinite(dComponent) || !std::isfinite(static_cast<float>(dComponent)))
					{
						Assets::AddDiagnostic(out_arrDiagnostics, "render_transform", stEntity.strName, "Combined render transform exceeds binary32 range");
						return false;
					}
				}
				const Matrix &arrEntity = mapWorld.at(stEntity.nEntityId);
				stScene.arrInstances.push_back({ static_cast<std::uint64_t>(stEntity.nEntityId), it->second, stInstance.nPrimitive, stInstance.nNode, arrWorld, { arrEntity[12], arrEntity[13], arrEntity[14] } });
			}
		}
	}
	if (stScene.arrInstances.empty())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "render_empty", "$", "Scene contains no renderable mesh instances");
		return false;
	}
	out_stScene = std::move(stScene);
	return true;
}

bool LoadRenderScene(const std::string &strPath, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::PackageData stPackage;
	return Assets::LoadPackage(strPath, stPackage, out_arrDiagnostics) && BuildRenderScene(stPackage, out_stScene, out_arrDiagnostics);
}

} // namespace EngineNext::Rendering
