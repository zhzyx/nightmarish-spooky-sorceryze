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

#include "engine_next/include/EngineNext/AI/ProcessTransport.h"
#include "engine_next/include/EngineNext/AI/WorkflowController.h"
#include "engine_next/include/EngineNext/Assets/AssetCompiler.h"

#include <charconv>
#include <filesystem>
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

bool ReadInput(const std::string &in_strPath, std::size_t in_nLimit, std::string &out_strText, EngineNext::Assets::Diagnostics &out_arrDiagnostics)
{
	std::ifstream stStream(in_strPath, std::ios::binary | std::ios::ate);
	if (!stStream || stStream.tellg() <= 0 || stStream.tellg() > static_cast<std::streamoff>(in_nLimit))
	{
		EngineNext::Assets::AddDiagnostic(out_arrDiagnostics, "request_read", "$", "request is missing, empty or oversized");
		return false;
	}
	out_strText.assign(static_cast<std::size_t>(stStream.tellg()), '\0');
	stStream.seekg(0);
	stStream.read(out_strText.data(), static_cast<std::streamsize>(out_strText.size()));
	return stStream.good();
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

bool UnsignedOption(const std::string &in_strValue, std::uint32_t &out_nValue)
{
	if (in_strValue.empty())
	{
		return false;
	}
	const char *pBegin = in_strValue.data();
	const char *pEnd = pBegin + in_strValue.size();
	const std::from_chars_result stResult = std::from_chars(pBegin, pEnd, out_nValue);
	return stResult.ec == std::errc() && stResult.ptr == pEnd;
}

bool SizeOption(const std::string &in_strValue, std::size_t &out_nValue)
{
	if (in_strValue.empty())
	{
		return false;
	}
	const char *pBegin = in_strValue.data();
	const char *pEnd = pBegin + in_strValue.size();
	const std::from_chars_result stResult = std::from_chars(pBegin, pEnd, out_nValue);
	return stResult.ec == std::errc() && stResult.ptr == pEnd;
}

int RunAi(const std::map<std::string, std::string> &in_mapOptions)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	std::string strRequest;
	if (!ReadInput(in_mapOptions.at("--request"), 384ULL * 1024ULL * 1024ULL, strRequest, arrDiagnostics))
	{
		return Failure(arrDiagnostics);
	}
	JsonValue stRequest;
	std::string strError;
	if (!EngineNext::Serialization::ParseJson(strRequest, stRequest, strError))
	{
		EngineNext::Assets::AddDiagnostic(arrDiagnostics, "invalid_json", "$", strError);
		return Failure(arrDiagnostics);
	}
	EngineNext::AI::HostConfig stConfig;
	stConfig.strPython = in_mapOptions.at("--python");
	stConfig.strExecutorScript = in_mapOptions.at("--executor-script");
	stConfig.strFactory = in_mapOptions.at("--factory");
	stConfig.strDatabase = in_mapOptions.at("--database");
	stConfig.strStatePath = in_mapOptions.at("--state");
	stConfig.strOutput = in_mapOptions.at("--output");
	stConfig.bResume = in_mapOptions.count("--resume") != 0;
	if (in_mapOptions.count("--max-steps") && !UnsignedOption(in_mapOptions.at("--max-steps"), stConfig.nMaxSteps))
	{
		return 2;
	}
	if (in_mapOptions.count("--timeout-ms") && (!UnsignedOption(in_mapOptions.at("--timeout-ms"), stConfig.nTimeoutMsec) || stConfig.nTimeoutMsec == 0))
	{
		return 2;
	}
	if (in_mapOptions.count("--output-limit") &&
			(!SizeOption(in_mapOptions.at("--output-limit"), stConfig.nOutputLimit) || stConfig.nOutputLimit == 0 || stConfig.nOutputLimit > 384ULL * 1024ULL * 1024ULL))
	{
		return 2;
	}
	const std::filesystem::path stStateDirectory = std::filesystem::path(stConfig.strStatePath).parent_path();
	std::error_code stError;
	if (!stStateDirectory.empty())
	{
		std::filesystem::create_directories(stStateDirectory, stError);
	}
	if (stError)
	{
		EngineNext::Assets::AddDiagnostic(arrDiagnostics, "state_directory", "$", "unable to create state directory");
		return Failure(arrDiagnostics);
	}
	EngineNext::AI::ProcessTransport stTransport;
	EngineNext::AI::WorkflowController stController(stTransport);
	EngineNext::AI::ControllerResult stResult;
	const bool bSucceeded = stController.Run(stRequest, stConfig, stResult);
	arrDiagnostics.insert(arrDiagnostics.end(), stResult.arrDiagnostics.begin(), stResult.arrDiagnostics.end());
	JsonValue::Object mapOutput{
		{ "diagnostics", EngineNext::Assets::DiagnosticsJson(arrDiagnostics) },
		{ "executor_run_id", stResult.strExecutorRunId },
		{ "package_digest", stResult.strPackageDigest },
		{ "valid", bSucceeded },
	};
	if (stResult.bHasSnapshot)
	{
		mapOutput["snapshot"] = stResult.stSnapshot;
	}
	Print(JsonValue(std::move(mapOutput)));
	return bSucceeded ? 0 : 1;
}

} // namespace

int main(int in_nArgumentCount, char **in_ppArguments)
{
	if (in_nArgumentCount < 2 || (in_nArgumentCount == 2 && std::string(in_ppArguments[1]) == "--help"))
	{
		std::cout << "Usage: next_asset compile --request FILE --source-root DIR --output DIR.enpak | validate --package DIR.enpak | inspect --package DIR.enpak | ai-run --request FILE --python FILE --executor-script FILE --factory NAME --database FILE --state FILE --output DIR.enpak [--resume]\n";
		return in_nArgumentCount == 2 ? 0 : 2;
	}
	const std::string strCommand = in_ppArguments[1];
	std::map<std::string, std::string> mapOptions;
	for (int nIndex = 2; nIndex < in_nArgumentCount; ++nIndex)
	{
		const std::string strOption = in_ppArguments[nIndex];
		if (strOption == "--resume")
		{
			mapOptions[strOption] = "true";
			continue;
		}
		static const char *arrOptions[] = { "--request", "--source-root", "--output", "--package", "--python", "--executor-script", "--factory", "--database", "--state", "--max-steps", "--timeout-ms", "--output-limit" };
		bool bKnown = false;
		for (const char *pOption : arrOptions)
		{
			bKnown = bKnown || strOption == pOption;
		}
		if (!bKnown)
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
	if (strCommand == "ai-run")
	{
		static const char *arrRequired[] = { "--request", "--python", "--executor-script", "--factory", "--database", "--state", "--output" };
		for (const char *pRequired : arrRequired)
		{
			if (mapOptions.count(pRequired) == 0)
			{
				return 2;
			}
		}
		return RunAi(mapOptions);
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	if (strCommand == "compile")
	{
		std::string strRequest;
		if (!ReadInput(mapOptions["--request"], 4 * 1024 * 1024, strRequest, arrDiagnostics))
		{
			return Failure(arrDiagnostics);
		}
		JsonValue stValue;
		std::string strError;
		EngineNext::Assets::BuildRequest stRequest;
		EngineNext::Assets::PackageData stPackage;
		if (!EngineNext::Serialization::ParseJson(strRequest, stValue, strError))
		{
			EngineNext::Assets::AddDiagnostic(arrDiagnostics, "invalid_json", "$", strError);
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
