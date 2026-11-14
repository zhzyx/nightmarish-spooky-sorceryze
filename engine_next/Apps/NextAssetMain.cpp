/**************************************************************************/
/*  NextAssetMain.cpp                                                     */
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

#include "engine_next/include/EngineNext/Assets/AssetCompiler.h"

#include <fstream>
#include <iostream>
#include <map>
#include <string>

namespace
{

using EngineNext::Serialization::JsonValue;

void Print(const JsonValue &in_stValue)
{
	std::string strText;
	if (EngineNext::Serialization::CanonicalJson(in_stValue, strText))
	{
		std::cout << strText << '\n';
	}
}

int Failure(const EngineNext::Assets::Diagnostics &in_arrDiagnostics)
{
	Print(JsonValue::Object{ { "diagnostics", EngineNext::Assets::DiagnosticsJson(in_arrDiagnostics) }, { "valid", false } });
	return 1;
}

bool OptionValue(int in_nCount, char **in_ppArguments, int &out_nIndex, std::string &out_strValue)
{
	if (out_nIndex + 1 >= in_nCount)
	{
		return false;
	}
	out_strValue = in_ppArguments[++out_nIndex];
	return !out_strValue.empty();
}

JsonValue InspectJson(const EngineNext::Assets::PackageData &in_stPackage)
{
	JsonValue::List arrAssets;
	for (const EngineNext::Assets::AssetEntry &stAsset : in_stPackage.stManifest.arrAssets)
	{
		arrAssets.emplace_back(JsonValue::Object{
				{ "asset_id", stAsset.strAssetId },
				{ "byte_size", static_cast<std::int64_t>(stAsset.nByteSize) },
				{ "content_sha256", stAsset.strContentSha256 },
				{ "revision", stAsset.strRevision },
				{ "type", stAsset.strType },
		});
	}
	return JsonValue::Object{
		{ "assets", std::move(arrAssets) },
		{ "manifest_sha256", in_stPackage.strManifestSha256 },
		{ "package_digest", in_stPackage.strPackageDigest },
		{ "scene_id", in_stPackage.stScene.strSceneId },
		{ "scene_revision", in_stPackage.stScene.strSceneRevision },
		{ "valid", true },
	};
}

} // namespace

int main(int in_nArgumentCount, char **in_ppArguments)
{
	if (in_nArgumentCount < 2 || (in_nArgumentCount == 2 && std::string(in_ppArguments[1]) == "--help"))
	{
		std::cout << "Usage: next_asset compile --request FILE --source-root DIR --output DIR.enpak | validate --package DIR.enpak | inspect --package DIR.enpak\n";
		return in_nArgumentCount == 2 ? 0 : 2;
	}
	const std::string strCommand = in_ppArguments[1];
	std::map<std::string, std::string> mapOptions;
	for (int nIndex = 2; nIndex < in_nArgumentCount; ++nIndex)
	{
		const std::string strOption = in_ppArguments[nIndex];
		if (strOption != "--request" && strOption != "--source-root" && strOption != "--output" && strOption != "--package")
		{
			return 2;
		}
		std::string strValue;
		if (!OptionValue(in_nArgumentCount, in_ppArguments, nIndex, strValue))
		{
			return 2;
		}
		mapOptions[strOption] = strValue;
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	if (strCommand == "compile")
	{
		std::ifstream stStream(mapOptions["--request"], std::ios::binary | std::ios::ate);
		if (!stStream || stStream.tellg() <= 0 || stStream.tellg() > 4 * 1024 * 1024)
		{
			AddDiagnostic(arrDiagnostics, "request_read", "$", "request is missing, empty or oversized");
			return Failure(arrDiagnostics);
		}
		std::string strRequest(static_cast<std::size_t>(stStream.tellg()), '\0');
		stStream.seekg(0);
		stStream.read(strRequest.data(), static_cast<std::streamsize>(strRequest.size()));
		JsonValue stValue;
		std::string strError;
		EngineNext::Assets::BuildRequest stRequest;
		EngineNext::Assets::PackageData stPackage;
		if (!EngineNext::Serialization::ParseJson(strRequest, stValue, strError))
		{
			AddDiagnostic(arrDiagnostics, "invalid_json", "$", strError);
			return Failure(arrDiagnostics);
		}
		if (!EngineNext::Assets::ParseBuildRequest(stValue, stRequest, arrDiagnostics) ||
			!EngineNext::Assets::CompilePackage(mapOptions["--source-root"], stRequest, stPackage, arrDiagnostics))
		{
			return Failure(arrDiagnostics);
		}
		EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
		if (!EngineNext::Assets::PublishPackage(stPackage, mapOptions["--output"], eResult, arrDiagnostics))
		{
			return Failure(arrDiagnostics);
		}
		JsonValue stResult = InspectJson(stPackage);
		stResult.GetObject()->emplace("reconciled_existing", eResult == EngineNext::Assets::PublishResult::ReconciledExisting);
		Print(stResult);
		return 0;
	}
	if (strCommand == "validate" || strCommand == "inspect")
	{
		EngineNext::Assets::PackageData stPackage;
		if (!EngineNext::Assets::LoadPackage(mapOptions["--package"], stPackage, arrDiagnostics))
		{
			return Failure(arrDiagnostics);
		}
		if (strCommand == "validate")
		{
			Print(JsonValue::Object{ { "diagnostics", JsonValue::List{} }, { "valid", true } });
		}
		else
		{
			Print(InspectJson(stPackage));
		}
		return 0;
	}
	return 2;
}
