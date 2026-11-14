/**************************************************************************/
/*  SceneRuntime.cpp                                                      */
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

#include "engine_next/include/EngineNext/Runtime/SceneRuntime.h"

#include <algorithm>

namespace EngineNext::Runtime
{

bool SceneRuntime::Load(const std::string &in_strPackagePath, Assets::Diagnostics &out_arrDiagnostics) noexcept
{
	Clear();
	Assets::PackageData stPackage;
	if (!Assets::LoadPackage(in_strPackagePath, stPackage, out_arrDiagnostics))
	{
		return false;
	}
	if (!stPredictionModel.SetFixedStepMsec(stPackage.stScene.nFixedStepMsec) ||
			!stPredictionModel.SetMaxSpeed(static_cast<float>(stPackage.stScene.dMaxSpeed)))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "invalid_simulation", "$.simulation", "scene simulation cannot configure the prediction model");
		Clear();
		return false;
	}
	for (const Assets::SceneEntity &stEntity : stPackage.stScene.arrEntities)
	{
		if (stEntity.strGameplayKind != "player_spawn")
		{
			continue;
		}
		arrSpawns.push_back(SpawnDefinition{
				EntityId{ static_cast<std::uint64_t>(stEntity.nEntityId) },
				Gameplay::Vector3{
						static_cast<float>(stEntity.stTransform.arrTranslation[0]),
						static_cast<float>(stEntity.stTransform.arrTranslation[1]),
						static_cast<float>(stEntity.stTransform.arrTranslation[2]),
				},
		});
	}
	std::sort(arrSpawns.begin(), arrSpawns.end(), [](const SpawnDefinition &in_stLeft, const SpawnDefinition &in_stRight)
			{ return in_stLeft.stEntityId.nValue < in_stRight.stEntityId.nValue; });
	if (arrSpawns.size() != 2)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "spawn_count", "$.entities", "M2 scene consumption requires exactly two player_spawn entities");
		Clear();
		return false;
	}
	strSceneId = stPackage.stScene.strSceneId;
	strSceneRevision = stPackage.stScene.strSceneRevision;
	strSceneContentSha256 = stPackage.stManifest.strSceneContentSha256;
	strPackageDigest = stPackage.strPackageDigest;
	bLoaded = true;
	return true;
}

bool SceneRuntime::ConfigureDefaultSimulation(std::uint32_t in_nFixedStepMsec) noexcept
{
	return !bLoaded && stPredictionModel.SetFixedStepMsec(in_nFixedStepMsec);
}

bool SceneRuntime::IsLoaded() const noexcept
{
	return bLoaded;
}

const std::string &SceneRuntime::GetSceneId() const noexcept
{
	return strSceneId;
}

const std::string &SceneRuntime::GetSceneRevision() const noexcept
{
	return strSceneRevision;
}

const std::string &SceneRuntime::GetSceneContentSha256() const noexcept
{
	return strSceneContentSha256;
}

const std::string &SceneRuntime::GetPackageDigest() const noexcept
{
	return strPackageDigest;
}

const Gameplay::PredictionModel &SceneRuntime::GetPredictionModel() const noexcept
{
	return stPredictionModel;
}

const SpawnDefinition *SceneRuntime::GetSpawn(std::size_t in_nIndex) const noexcept
{
	return in_nIndex < arrSpawns.size() ? &arrSpawns[in_nIndex] : nullptr;
}

const SpawnDefinition *SceneRuntime::FindSpawn(EntityId in_stEntityId) const noexcept
{
	for (const SpawnDefinition &stSpawn : arrSpawns)
	{
		if (stSpawn.stEntityId == in_stEntityId)
		{
			return &stSpawn;
		}
	}
	return nullptr;
}

std::size_t SceneRuntime::GetSpawnCount() const noexcept
{
	return arrSpawns.size();
}

void SceneRuntime::Clear() noexcept
{
	bLoaded = false;
	strSceneId.clear();
	strSceneRevision.clear();
	strSceneContentSha256.clear();
	strPackageDigest.clear();
	stPredictionModel = Gameplay::PredictionModel{};
	arrSpawns.clear();
}

} // namespace EngineNext::Runtime
