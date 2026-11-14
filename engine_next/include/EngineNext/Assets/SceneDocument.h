/**************************************************************************/
/*  SceneDocument.h                                                       */
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

#include "engine_next/include/EngineNext/Assets/Types.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Assets
{

struct Transform
{
	std::array<double, 3> arrTranslation{ 0.0, 0.0, 0.0 };
	std::array<double, 4> arrRotation{ 0.0, 0.0, 0.0, 1.0 };
	std::array<double, 3> arrScale{ 1.0, 1.0, 1.0 };
};

struct SceneAssetRef
{
	std::string strRole;
	AssetRef stAsset;
};

struct SceneEntity
{
	std::int64_t nEntityId = 0;
	std::string strName;
	std::string strNodeType;
	std::int64_t nParentEntityId = 0;
	Transform stTransform;
	std::string strGameplayKind;
	std::vector<SceneAssetRef> arrAssets;
};

struct SceneDocument
{
	std::string strSceneId;
	std::string strSceneRevision;
	std::uint32_t nFixedStepMsec = 16;
	double dMaxSpeed = 8.0;
	std::vector<SceneEntity> arrEntities;
};

[[nodiscard]] bool ParseSceneDocument(const Serialization::JsonValue &in_stValue, SceneDocument &out_stScene, Diagnostics &out_arrDiagnostics);
[[nodiscard]] Serialization::JsonValue ToJson(const SceneDocument &in_stScene);
[[nodiscard]] bool ValidateSceneDocument(const SceneDocument &in_stScene, Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Assets
