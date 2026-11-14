/**************************************************************************/
/*  SceneDocument.cpp                                                     */
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

#include "engine_next/include/EngineNext/Assets/SceneDocument.h"

#include "engine_next/Assets/AssetValidation.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <utility>

namespace EngineNext::Assets
{
namespace
{

bool ParseNumbers(const Serialization::JsonValue &in_stValue, const std::string &in_strPath, double *out_pValues, std::size_t in_nCount, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::List *pArray = in_stValue.GetList();
	if (pArray == nullptr || pArray->size() != in_nCount)
	{
		AddDiagnostic(out_arrDiagnostics, "array_size", in_strPath, "unexpected numeric array size");
		return false;
	}
	bool bValid = true;
	for (std::size_t nIndex = 0; nIndex < in_nCount; ++nIndex)
	{
		double dValue = 0.0;
		if (!(*pArray)[nIndex].GetNumber(dValue) || !std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
		{
			AddDiagnostic(out_arrDiagnostics, "invalid_number", in_strPath + "[" + std::to_string(nIndex) + "]", "expected finite binary32-compatible number");
			bValid = false;
			continue;
		}
		out_pValues[nIndex] = dValue;
	}
	return bValid;
}

bool ParseTransform(const Serialization::JsonValue &in_stValue, const std::string &in_strPath, Transform &out_stTransform, Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Object(in_stValue, in_strPath, out_arrDiagnostics);
	if (pObject == nullptr)
	{
		return false;
	}
	Fields(*pObject, { "translation", "rotation_xyzw", "scale" }, in_strPath, out_arrDiagnostics);
	const Serialization::JsonValue::Object::const_iterator itTranslation = pObject->find("translation");
	const Serialization::JsonValue::Object::const_iterator itRotation = pObject->find("rotation_xyzw");
	const Serialization::JsonValue::Object::const_iterator itScale = pObject->find("scale");
	if (itTranslation == pObject->end() || itRotation == pObject->end() || itScale == pObject->end())
	{
		return false;
	}
	const bool bTranslation = ParseNumbers(itTranslation->second, in_strPath + ".translation", out_stTransform.arrTranslation.data(), 3, out_arrDiagnostics);
	const bool bRotation = ParseNumbers(itRotation->second, in_strPath + ".rotation_xyzw", out_stTransform.arrRotation.data(), 4, out_arrDiagnostics);
	const bool bScale = ParseNumbers(itScale->second, in_strPath + ".scale", out_stTransform.arrScale.data(), 3, out_arrDiagnostics);
	return bTranslation && bRotation && bScale;
}

Serialization::JsonValue Numbers(const double *in_pValues, std::size_t in_nCount)
{
	Serialization::JsonValue::List arrValues;
	for (std::size_t nIndex = 0; nIndex < in_nCount; ++nIndex)
	{
		arrValues.emplace_back(in_pValues[nIndex]);
	}
	return Serialization::JsonValue(std::move(arrValues));
}

Serialization::JsonValue TransformJson(const Transform &in_stTransform)
{
	return Serialization::JsonValue::Object{
		{ "rotation_xyzw", Numbers(in_stTransform.arrRotation.data(), 4) },
		{ "scale", Numbers(in_stTransform.arrScale.data(), 3) },
		{ "translation", Numbers(in_stTransform.arrTranslation.data(), 3) },
	};
}

} // namespace

bool ParseSceneDocument(const Serialization::JsonValue &in_stValue, SceneDocument &out_stScene, Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_stScene = SceneDocument{};
	const Serialization::JsonValue::Object *pObject = Object(in_stValue, "$", out_arrDiagnostics);
	if (pObject == nullptr)
	{
		return false;
	}
	Fields(*pObject, { "schema_version", "scene_id", "scene_revision", "simulation", "entities" }, "$", out_arrDiagnostics);
	std::int64_t nSchema = 0;
	Integer(*pObject, "schema_version", "$", nSchema, out_arrDiagnostics);
	if (nSchema != 1)
	{
		AddDiagnostic(out_arrDiagnostics, "unsupported_schema", "$.schema_version", "expected schema 1");
	}
	String(*pObject, "scene_id", "$", out_stScene.strSceneId, out_arrDiagnostics);
	String(*pObject, "scene_revision", "$", out_stScene.strSceneRevision, out_arrDiagnostics);
	const Serialization::JsonValue::Object::const_iterator itSimulation = pObject->find("simulation");
	if (itSimulation != pObject->end())
	{
		const Serialization::JsonValue::Object *pSimulation = Object(itSimulation->second, "$.simulation", out_arrDiagnostics);
		if (pSimulation != nullptr)
		{
			Fields(*pSimulation, { "fixed_step_ms", "max_speed" }, "$.simulation", out_arrDiagnostics);
			std::int64_t nStep = 0;
			Integer(*pSimulation, "fixed_step_ms", "$.simulation", nStep, out_arrDiagnostics);
			Number(*pSimulation, "max_speed", "$.simulation", out_stScene.dMaxSpeed, out_arrDiagnostics);
			if (nStep >= 0 && nStep <= 1000)
			{
				out_stScene.nFixedStepMsec = static_cast<std::uint32_t>(nStep);
			}
			else
			{
				AddDiagnostic(out_arrDiagnostics, "invalid_fixed_step", "$.simulation.fixed_step_ms", "expected 1..1000 ms");
			}
		}
	}
	const Serialization::JsonValue::Object::const_iterator itEntities = pObject->find("entities");
	const Serialization::JsonValue::List *pEntities = itEntities == pObject->end() ? nullptr : itEntities->second.GetList();
	if (pEntities == nullptr)
	{
		AddDiagnostic(out_arrDiagnostics, "type", "$.entities", "expected array");
	}
	else
	{
		for (std::size_t nIndex = 0; nIndex < pEntities->size(); ++nIndex)
		{
			const std::string strPath = "$.entities[" + std::to_string(nIndex) + "]";
			const Serialization::JsonValue::Object *pEntity = Object((*pEntities)[nIndex], strPath, out_arrDiagnostics);
			if (pEntity == nullptr)
			{
				continue;
			}
			SceneEntity stEntity;
			Fields(*pEntity, { "entity_id", "name", "node_type", "parent_entity_id", "transform", "gameplay", "assets" }, strPath, out_arrDiagnostics);
			Integer(*pEntity, "entity_id", strPath, stEntity.nEntityId, out_arrDiagnostics);
			Integer(*pEntity, "parent_entity_id", strPath, stEntity.nParentEntityId, out_arrDiagnostics);
			String(*pEntity, "name", strPath, stEntity.strName, out_arrDiagnostics);
			String(*pEntity, "node_type", strPath, stEntity.strNodeType, out_arrDiagnostics);
			const Serialization::JsonValue::Object::const_iterator itTransform = pEntity->find("transform");
			if (itTransform != pEntity->end())
			{
				ParseTransform(itTransform->second, strPath + ".transform", stEntity.stTransform, out_arrDiagnostics);
			}
			const Serialization::JsonValue::Object::const_iterator itGameplay = pEntity->find("gameplay");
			if (itGameplay != pEntity->end())
			{
				const Serialization::JsonValue::Object *pGameplay = Object(itGameplay->second, strPath + ".gameplay", out_arrDiagnostics);
				if (pGameplay != nullptr)
				{
					Fields(*pGameplay, { "kind" }, strPath + ".gameplay", out_arrDiagnostics);
					String(*pGameplay, "kind", strPath + ".gameplay", stEntity.strGameplayKind, out_arrDiagnostics);
				}
			}
			const Serialization::JsonValue::Object::const_iterator itAssets = pEntity->find("assets");
			const Serialization::JsonValue::List *pAssets = itAssets == pEntity->end() ? nullptr : itAssets->second.GetList();
			if (pAssets == nullptr)
			{
				AddDiagnostic(out_arrDiagnostics, "type", strPath + ".assets", "expected array");
			}
			else
			{
				for (std::size_t nAsset = 0; nAsset < pAssets->size(); ++nAsset)
				{
					const std::string strAssetPath = strPath + ".assets[" + std::to_string(nAsset) + "]";
					const Serialization::JsonValue::Object *pAsset = Object((*pAssets)[nAsset], strAssetPath, out_arrDiagnostics);
					if (pAsset == nullptr)
					{
						continue;
					}
					Fields(*pAsset, { "role", "asset_id", "revision", "content_sha256" }, strAssetPath, out_arrDiagnostics);
					SceneAssetRef stRef;
					String(*pAsset, "role", strAssetPath, stRef.strRole, out_arrDiagnostics);
					ParseRef((*pAssets)[nAsset], strAssetPath, stRef.stAsset, out_arrDiagnostics);
					stEntity.arrAssets.push_back(std::move(stRef));
				}
			}
			out_stScene.arrEntities.push_back(std::move(stEntity));
		}
	}
	return ValidateSceneDocument(out_stScene, out_arrDiagnostics);
}

Serialization::JsonValue ToJson(const SceneDocument &in_stScene)
{
	std::vector<SceneEntity> arrEntities = in_stScene.arrEntities;
	std::sort(arrEntities.begin(), arrEntities.end(), [](const SceneEntity &in_stLeft, const SceneEntity &in_stRight)
	{
		return in_stLeft.nEntityId < in_stRight.nEntityId;
	});
	Serialization::JsonValue::List arrJsonEntities;
	for (const SceneEntity &stEntity : arrEntities)
	{
		std::vector<SceneAssetRef> arrAssets = stEntity.arrAssets;
		std::sort(arrAssets.begin(), arrAssets.end(), [](const SceneAssetRef &in_stLeft, const SceneAssetRef &in_stRight)
		{
			if (in_stLeft.strRole != in_stRight.strRole)
			{
				return in_stLeft.strRole < in_stRight.strRole;
			}
			return in_stLeft.stAsset.strAssetId < in_stRight.stAsset.strAssetId;
		});
		Serialization::JsonValue::List arrJsonAssets;
		for (const SceneAssetRef &stRef : arrAssets)
		{
			Serialization::JsonValue::Object mapRef{
				{ "asset_id", stRef.stAsset.strAssetId },
				{ "content_sha256", stRef.stAsset.strContentSha256 },
				{ "revision", stRef.stAsset.strRevision },
			};
			mapRef["role"] = stRef.strRole;
			arrJsonAssets.emplace_back(std::move(mapRef));
		}
		arrJsonEntities.emplace_back(Serialization::JsonValue::Object{
			{ "assets", std::move(arrJsonAssets) },
			{ "entity_id", stEntity.nEntityId },
			{ "gameplay", Serialization::JsonValue::Object{ { "kind", stEntity.strGameplayKind } } },
			{ "name", stEntity.strName },
			{ "node_type", stEntity.strNodeType },
			{ "parent_entity_id", stEntity.nParentEntityId },
			{ "transform", TransformJson(stEntity.stTransform) },
		});
	}
	return Serialization::JsonValue::Object{
		{ "entities", std::move(arrJsonEntities) },
		{ "scene_id", in_stScene.strSceneId },
		{ "scene_revision", in_stScene.strSceneRevision },
		{ "schema_version", std::int64_t(1) },
		{ "simulation", Serialization::JsonValue::Object{
			{ "fixed_step_ms", static_cast<std::int64_t>(in_stScene.nFixedStepMsec) },
			{ "max_speed", in_stScene.dMaxSpeed },
		} },
	};
}

bool ValidateSceneDocument(const SceneDocument &in_stScene, Diagnostics &out_arrDiagnostics)
{
	if (!IsIdentity(in_stScene.strSceneId))
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_scene_id", "$.scene_id", "invalid scene identity");
	}
	if (!IsRevision(in_stScene.strSceneRevision))
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_revision", "$.scene_revision", "invalid scene revision");
	}
	if (in_stScene.nFixedStepMsec == 0 || in_stScene.nFixedStepMsec > 1000)
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_fixed_step", "$.simulation.fixed_step_ms", "expected 1..1000 ms");
	}
	if (!std::isfinite(in_stScene.dMaxSpeed) || in_stScene.dMaxSpeed <= 0.0 || in_stScene.dMaxSpeed > 10000.0)
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_max_speed", "$.simulation.max_speed", "expected speed in (0, 10000]");
	}
	if (in_stScene.arrEntities.empty() || in_stScene.arrEntities.size() > 256)
	{
		AddDiagnostic(out_arrDiagnostics, "entity_budget", "$.entities", "expected 1..256 entities");
	}
	std::map<std::int64_t, std::int64_t> mapParents;
	std::set<std::string> setNames;
	for (std::size_t nIndex = 0; nIndex < in_stScene.arrEntities.size(); ++nIndex)
	{
		const SceneEntity &stEntity = in_stScene.arrEntities[nIndex];
		const std::string strPath = "$.entities[" + std::to_string(nIndex) + "]";
		if (stEntity.nEntityId <= 0 || !mapParents.emplace(stEntity.nEntityId, stEntity.nParentEntityId).second)
		{
			AddDiagnostic(out_arrDiagnostics, "duplicate_entity_id", strPath + ".entity_id", "entity IDs must be positive and unique");
		}
		if (stEntity.strName.empty() || stEntity.strName.size() > 128 || !setNames.insert(stEntity.strName).second)
		{
			AddDiagnostic(out_arrDiagnostics, "duplicate_entity_name", strPath + ".name", "entity names must be nonempty and unique");
		}
		if (stEntity.strNodeType != "Node3D" && stEntity.strNodeType != "MeshInstance3D")
		{
			AddDiagnostic(out_arrDiagnostics, "unsupported_node", strPath + ".node_type", "only Node3D and MeshInstance3D are supported");
		}
		if (stEntity.strGameplayKind != "player_spawn" && stEntity.strGameplayKind != "static")
		{
			AddDiagnostic(out_arrDiagnostics, "unsupported_gameplay", strPath + ".gameplay.kind", "unknown gameplay kind");
		}
		const double dNorm = std::sqrt(stEntity.stTransform.arrRotation[0] * stEntity.stTransform.arrRotation[0] +
			stEntity.stTransform.arrRotation[1] * stEntity.stTransform.arrRotation[1] +
			stEntity.stTransform.arrRotation[2] * stEntity.stTransform.arrRotation[2] +
			stEntity.stTransform.arrRotation[3] * stEntity.stTransform.arrRotation[3]);
		if (!std::isfinite(dNorm) || std::abs(dNorm - 1.0) > 0.00001)
		{
			AddDiagnostic(out_arrDiagnostics, "invalid_rotation", strPath + ".transform.rotation_xyzw", "quaternion must be normalized");
		}
		for (const double dScale : stEntity.stTransform.arrScale)
		{
			if (!std::isfinite(dScale) || dScale == 0.0)
			{
				AddDiagnostic(out_arrDiagnostics, "invalid_scale", strPath + ".transform.scale", "scale components must be finite and nonzero");
			}
		}
		std::size_t nMeshCount = 0;
		std::set<std::string> setRoles;
		for (std::size_t nAsset = 0; nAsset < stEntity.arrAssets.size(); ++nAsset)
		{
			const SceneAssetRef &stRef = stEntity.arrAssets[nAsset];
			if ((stRef.strRole != "mesh" && stRef.strRole != "texture") || !setRoles.insert(stRef.strRole + "\n" + stRef.stAsset.strAssetId).second)
			{
				AddDiagnostic(out_arrDiagnostics, "invalid_asset_role", strPath + ".assets[" + std::to_string(nAsset) + "]", "unsupported or duplicate asset role");
			}
			nMeshCount += stRef.strRole == "mesh" ? 1 : 0;
		}
		if ((stEntity.strNodeType == "MeshInstance3D" && nMeshCount != 1) || (stEntity.strNodeType == "Node3D" && nMeshCount != 0))
		{
			AddDiagnostic(out_arrDiagnostics, "mesh_reference", strPath + ".assets", "mesh reference does not match node type");
		}
	}
	for (const std::pair<const std::int64_t, std::int64_t> &stEntry : mapParents)
	{
		if (stEntry.second != 0 && mapParents.find(stEntry.second) == mapParents.end())
		{
			AddDiagnostic(out_arrDiagnostics, "missing_parent", "$.entities", "parent entity does not exist");
		}
		std::int64_t nCurrent = stEntry.first;
		for (std::size_t nDepth = 0; nDepth <= mapParents.size(); ++nDepth)
		{
			const std::map<std::int64_t, std::int64_t>::const_iterator itParent = mapParents.find(nCurrent);
			if (itParent == mapParents.end() || itParent->second == 0)
			{
				break;
			}
			nCurrent = itParent->second;
			if (nCurrent == stEntry.first)
			{
				AddDiagnostic(out_arrDiagnostics, "parent_cycle", "$.entities", "entity parent cycle");
				break;
			}
			if (nDepth == mapParents.size())
			{
				AddDiagnostic(out_arrDiagnostics, "parent_cycle", "$.entities", "entity parent cycle");
			}
		}
	}
	SortDiagnostics(out_arrDiagnostics);
	return out_arrDiagnostics.empty();
}

} // namespace EngineNext::Assets
