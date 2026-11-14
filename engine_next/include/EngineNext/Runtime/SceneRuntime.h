/**************************************************************************/
/*  SceneRuntime.h                                                        */
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

#pragma once

#include "engine_next/include/EngineNext/Assets/AssetPackage.h"
#include "engine_next/include/EngineNext/Gameplay/PredictionModel.h"
#include "engine_next/include/EngineNext/Runtime/Types.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Runtime
{

struct SpawnDefinition
{
	EntityId stEntityId;
	Gameplay::Vector3 vPosition;
};

class SceneRuntime
{
	bool bSceneLoaded = false;
	std::string strSceneId;
	std::string strSceneRevision;
	std::string strSceneContentSha256;
	std::string strPackageDigest;
	Gameplay::PredictionModel stPredictionModel;
	std::vector<SpawnDefinition> arrSpawns;

public:
	[[nodiscard]] bool Load(const std::string &in_strPackagePath, Assets::Diagnostics &out_arrDiagnostics) noexcept;
	[[nodiscard]] bool ConfigureDefaultSimulation(std::uint32_t in_nFixedStepMsec) noexcept;
	[[nodiscard]] bool IsLoaded() const noexcept;
	[[nodiscard]] const std::string &GetSceneId() const noexcept;
	[[nodiscard]] const std::string &GetSceneRevision() const noexcept;
	[[nodiscard]] const std::string &GetSceneContentSha256() const noexcept;
	[[nodiscard]] const std::string &GetPackageDigest() const noexcept;
	[[nodiscard]] const Gameplay::PredictionModel &GetPredictionModel() const noexcept;
	[[nodiscard]] const SpawnDefinition *GetSpawn(std::size_t in_nIndex) const noexcept;
	[[nodiscard]] const SpawnDefinition *FindSpawn(EntityId in_stEntityId) const noexcept;
	[[nodiscard]] std::size_t GetSpawnCount() const noexcept;
	void Clear() noexcept;
};

} // namespace EngineNext::Runtime
