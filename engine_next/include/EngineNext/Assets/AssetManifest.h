/**************************************************************************/
/*  AssetManifest.h                                                       */
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

#include "engine_next/include/EngineNext/Assets/SceneDocument.h"

#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Assets
{

struct AssetSource
{
	std::string strKind;
	std::string strArtifactId;
	std::string strArtifactRevision;
	std::string strImporterVersion;
};

struct AssetEntry
{
	std::string strAssetId;
	std::string strRevision;
	std::string strType;
	std::string strMediaType;
	std::string strContentSha256;
	std::uint64_t nByteSize = 0;
	std::vector<AssetRef> arrDependencies;
	AssetSource stSource;
};

struct AssetManifest
{
	std::string strSceneId;
	std::string strSceneRevision;
	std::string strSceneContentSha256;
	std::vector<AssetEntry> arrAssets;
};

[[nodiscard]] bool ParseAssetManifest(const Serialization::JsonValue &in_stValue, AssetManifest &out_stManifest, Diagnostics &out_arrDiagnostics);
[[nodiscard]] Serialization::JsonValue ToJson(const AssetManifest &in_stManifest);
[[nodiscard]] bool ValidateAssetManifest(const AssetManifest &in_stManifest, const SceneDocument &in_stScene, Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Assets
