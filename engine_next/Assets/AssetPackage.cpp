/**************************************************************************/
/*  AssetPackage.cpp                                                      */
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

#include "engine_next/include/EngineNext/Assets/AssetPackage.h"

#include "engine_next/Assets/AssetValidation.h"

#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <filesystem>
#include <fstream>
#include <random>
#include <set>

#ifdef _WIN32
#include <windows.h>
#elif defined(__APPLE__)
#include <cstdio>
#elif defined(__linux__)
#include <fcntl.h>
#include <sys/syscall.h>
#include <unistd.h>
#endif

namespace EngineNext::Assets
{
namespace
{

namespace fs = std::filesystem;
constexpr std::size_t MAX_JSON_BYTES = 4ULL * 1024ULL * 1024ULL;

void AppendUint64(std::uint64_t in_nValue, std::vector<std::uint8_t> &out_arrBytes)
{
	for (std::size_t nIndex = 0; nIndex < 8; ++nIndex)
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(in_nValue >> (nIndex * 8U)));
	}
}

void AppendPart(const std::string &in_strName, const std::uint8_t *in_pData, std::size_t in_nBytes, std::vector<std::uint8_t> &out_arrBytes)
{
	AppendUint64(in_strName.size(), out_arrBytes);
	out_arrBytes.insert(out_arrBytes.end(), in_strName.begin(), in_strName.end());
	AppendUint64(in_nBytes, out_arrBytes);
	out_arrBytes.insert(out_arrBytes.end(), in_pData, in_pData + in_nBytes);
}

bool ReadFile(const fs::path &in_strPath, std::size_t in_nLimit, std::vector<std::uint8_t> &out_arrBytes, Diagnostics &out_arrDiagnostics)
{
	std::error_code stError;
	const fs::file_status stStatus = fs::symlink_status(in_strPath, stError);
	if (stError || fs::is_symlink(stStatus) || !fs::is_regular_file(stStatus))
	{
		AddDiagnostic(out_arrDiagnostics, "input_type", in_strPath.filename().generic_string(), "expected regular non-linked file");
		return false;
	}
	const std::uintmax_t nSize = fs::file_size(in_strPath, stError);
	if (stError || nSize > in_nLimit)
	{
		AddDiagnostic(out_arrDiagnostics, "input_budget", in_strPath.filename().generic_string(), "file exceeds budget");
		return false;
	}
	std::ifstream stStream(in_strPath, std::ios::binary);
	if (!stStream)
	{
		AddDiagnostic(out_arrDiagnostics, "read_failed", in_strPath.filename().generic_string(), "unable to read file");
		return false;
	}
	out_arrBytes.resize(static_cast<std::size_t>(nSize));
	if (nSize != 0)
	{
		stStream.read(reinterpret_cast<char *>(out_arrBytes.data()), static_cast<std::streamsize>(nSize));
	}
	return stStream.good() || stStream.eof();
}

bool ReadText(const fs::path &in_strPath, std::string &out_strText, Diagnostics &out_arrDiagnostics)
{
	std::vector<std::uint8_t> arrBytes;
	if (!ReadFile(in_strPath, MAX_JSON_BYTES, arrBytes, out_arrDiagnostics))
	{
		return false;
	}
	out_strText.assign(arrBytes.begin(), arrBytes.end());
	return true;
}

bool WriteFile(const fs::path &in_strPath, const std::uint8_t *in_pData, std::size_t in_nBytes, Diagnostics &out_arrDiagnostics)
{
	std::ofstream stStream(in_strPath, std::ios::binary | std::ios::out);
	if (!stStream)
	{
		AddDiagnostic(out_arrDiagnostics, "write_failed", in_strPath.filename().generic_string(), "unable to create staging file");
		return false;
	}
	if (in_nBytes != 0)
	{
		stStream.write(reinterpret_cast<const char *>(in_pData), static_cast<std::streamsize>(in_nBytes));
	}
	stStream.flush();
	if (!stStream.good())
	{
		AddDiagnostic(out_arrDiagnostics, "write_failed", in_strPath.filename().generic_string(), "staging write failed");
		return false;
	}
	stStream.close();
	return stStream.good();
}

bool RenameNoReplace(const fs::path &in_strSource, const fs::path &in_strTarget)
{
#ifdef _WIN32
	return MoveFileExW(in_strSource.wstring().c_str(), in_strTarget.wstring().c_str(), 0) != 0;
#elif defined(__APPLE__)
	return renamex_np(in_strSource.c_str(), in_strTarget.c_str(), RENAME_EXCL) == 0;
#elif defined(__linux__)
	return syscall(SYS_renameat2, AT_FDCWD, in_strSource.c_str(), AT_FDCWD, in_strTarget.c_str(), 1U) == 0;
#else
	return false;
#endif
}

} // namespace

bool ComputePackageDigest(PackageData &out_stPackage, Diagnostics &out_arrDiagnostics)
{
	std::string strManifest;
	std::string strScene;
	if (!Serialization::CanonicalJson(ToJson(out_stPackage.stManifest), strManifest) ||
		!Serialization::CanonicalJson(ToJson(out_stPackage.stScene), strScene))
	{
		AddDiagnostic(out_arrDiagnostics, "canonical_json", "$", "unable to canonicalize package");
		return false;
	}
	if (out_stPackage.strManifestJson.empty())
	{
		out_stPackage.strManifestJson = strManifest;
	}
	if (out_stPackage.strSceneJson.empty())
	{
		out_stPackage.strSceneJson = strScene;
	}
	if (out_stPackage.strManifestJson != strManifest || out_stPackage.strSceneJson != strScene)
	{
		AddDiagnostic(out_arrDiagnostics, "noncanonical_package", "$", "package JSON is not canonical");
		return false;
	}
	out_stPackage.strManifestSha256 = Serialization::Sha256Hex(strManifest);
	std::vector<std::uint8_t> arrDigestInput;
	const std::string strDomain("ENPAK1\0", 7);
	arrDigestInput.insert(arrDigestInput.end(), strDomain.begin(), strDomain.end());
	AppendPart("AssetManifest.json", reinterpret_cast<const std::uint8_t *>(strManifest.data()), strManifest.size(), arrDigestInput);
	AppendPart("Scene.json", reinterpret_cast<const std::uint8_t *>(strScene.data()), strScene.size(), arrDigestInput);
	for (const std::pair<const std::string, std::vector<std::uint8_t>> &stEntry : out_stPackage.mapBlobs)
	{
		const std::string strName = "blobs/" + stEntry.first;
		AppendPart(strName, stEntry.second.data(), stEntry.second.size(), arrDigestInput);
	}
	out_stPackage.strPackageDigest = Serialization::Sha256Hex(arrDigestInput.data(), arrDigestInput.size());
	return true;
}

bool LoadPackage(const std::string &in_strPackageRoot, PackageData &out_stPackage, Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	out_stPackage = PackageData{};
	const fs::path stRoot(in_strPackageRoot);
	std::error_code stError;
	const fs::file_status stRootStatus = fs::symlink_status(stRoot, stError);
	if (stError || !NoLinkedComponents(stRoot) || fs::is_symlink(stRootStatus) || !fs::is_directory(stRootStatus))
	{
		AddDiagnostic(out_arrDiagnostics, "package_root", "$", "package root must be a real directory");
		return false;
	}
	std::set<std::string> setFiles;
	for (fs::recursive_directory_iterator it(stRoot, fs::directory_options::none, stError), stEnd; !stError && it != stEnd; it.increment(stError))
	{
		const fs::file_status stStatus = it->symlink_status(stError);
		if (stError || fs::is_symlink(stStatus))
		{
			AddDiagnostic(out_arrDiagnostics, "symbolic_link", "$", "package cannot contain symbolic links");
			return false;
		}
		if (fs::is_directory(stStatus))
		{
			continue;
		}
		setFiles.insert(fs::relative(it->path(), stRoot, stError).generic_string());
	}
	if (stError)
	{
		AddDiagnostic(out_arrDiagnostics, "package_read", "$", "package traversal failed");
		return false;
	}
	if (!setFiles.count("AssetManifest.json") || !setFiles.count("Scene.json"))
	{
		AddDiagnostic(out_arrDiagnostics, "missing_package_file", "$", "manifest and scene are required");
		return false;
	}
	if (!ReadText(stRoot / "AssetManifest.json", out_stPackage.strManifestJson, out_arrDiagnostics) ||
		!ReadText(stRoot / "Scene.json", out_stPackage.strSceneJson, out_arrDiagnostics))
	{
		return false;
	}
	Serialization::JsonValue stManifestValue;
	Serialization::JsonValue stSceneValue;
	std::string strError;
	if (!Serialization::ParseJson(out_stPackage.strManifestJson, stManifestValue, strError) ||
		!Serialization::ParseJson(out_stPackage.strSceneJson, stSceneValue, strError))
	{
		AddDiagnostic(out_arrDiagnostics, "invalid_json", "$", strError);
		return false;
	}
	if (!ParseSceneDocument(stSceneValue, out_stPackage.stScene, out_arrDiagnostics) ||
		!ParseAssetManifest(stManifestValue, out_stPackage.stManifest, out_arrDiagnostics))
	{
		return false;
	}
	if (!ValidateAssetManifest(out_stPackage.stManifest, out_stPackage.stScene, out_arrDiagnostics))
	{
		return false;
	}
	std::set<std::string> setExpected = { "AssetManifest.json", "Scene.json" };
	std::uint64_t nTotalBytes = 0;
	for (const AssetEntry &stAsset : out_stPackage.stManifest.arrAssets)
	{
		if (!IsSha256(stAsset.strContentSha256))
		{
			AddDiagnostic(out_arrDiagnostics, "path_escape", "$.assets", "invalid blob digest");
			return false;
		}
		const std::string strName = "blobs/" + stAsset.strContentSha256;
		setExpected.insert(strName);
		std::vector<std::uint8_t> arrBytes;
		if (!ReadFile(stRoot / strName, 64ULL * 1024ULL * 1024ULL, arrBytes, out_arrDiagnostics))
		{
			return false;
		}
		if (arrBytes.size() != stAsset.nByteSize || Serialization::Sha256Hex(arrBytes.data(), arrBytes.size()) != stAsset.strContentSha256)
		{
			AddDiagnostic(out_arrDiagnostics, "digest_mismatch", strName, "blob size or digest differs from manifest");
			return false;
		}
		BlobInfo stInfo;
		if (!ValidateBlob(stAsset.strMediaType, arrBytes, stInfo, out_arrDiagnostics))
		{
			return false;
		}
		nTotalBytes += arrBytes.size();
		out_stPackage.mapBlobs.emplace(stAsset.strContentSha256, std::move(arrBytes));
	}
	if (nTotalBytes > 256ULL * 1024ULL * 1024ULL || setFiles != setExpected)
	{
		AddDiagnostic(out_arrDiagnostics, "package_contents", "$", "unexpected files or package budget exceeded");
		return false;
	}
	if (!ValidateAssetManifest(out_stPackage.stManifest, out_stPackage.stScene, out_arrDiagnostics))
	{
		return false;
	}
	return ComputePackageDigest(out_stPackage, out_arrDiagnostics);
}

bool PublishPackage(const PackageData &in_stPackage, const std::string &in_strTargetRoot, PublishResult &out_eResult, Diagnostics &out_arrDiagnostics)
{
	std::mutex stCancellationMutex;
	return PublishPackageGuarded(in_stPackage, in_strTargetRoot, out_eResult, out_arrDiagnostics, stCancellationMutex, std::function<bool()>());
}

bool PublishPackageGuarded(const PackageData &in_stPackage, const std::string &in_strTargetRoot, PublishResult &out_eResult,
						   Diagnostics &out_arrDiagnostics, std::mutex &in_stCancellationMutex, const std::function<bool()> &in_fnCancelRequested)
{
	out_arrDiagnostics.clear();
	const fs::path stTarget(in_strTargetRoot);
	if (stTarget.extension() != ".enpak" || stTarget.filename().empty())
	{
		AddDiagnostic(out_arrDiagnostics, "package_name", "$", "target must use .enpak");
		return false;
	}
	std::error_code stError;
	const fs::file_status stParentStatus = fs::symlink_status(stTarget.parent_path(), stError);
	if (stError || !NoLinkedComponents(stTarget.parent_path()) || fs::is_symlink(stParentStatus) || !fs::is_directory(stParentStatus))
	{
		AddDiagnostic(out_arrDiagnostics, "package_parent", "$", "target parent must be a real directory without linked components");
		return false;
	}
	PackageData stCopy = in_stPackage;
	if (!ValidateSceneDocument(stCopy.stScene, out_arrDiagnostics) ||
		!ValidateAssetManifest(stCopy.stManifest, stCopy.stScene, out_arrDiagnostics) || !ComputePackageDigest(stCopy, out_arrDiagnostics) ||
		stCopy.strPackageDigest != in_stPackage.strPackageDigest)
	{
		return false;
	}
	const bool bTargetExists = fs::exists(stTarget, stError);
	if (stError)
	{
		AddDiagnostic(out_arrDiagnostics, "package_status", "$", "unable to inspect target");
		return false;
	}
	if (bTargetExists)
	{
		PackageData stExisting;
		Diagnostics arrExisting;
		if (LoadPackage(in_strTargetRoot, stExisting, arrExisting) && stExisting.strPackageDigest == stCopy.strPackageDigest)
		{
			out_eResult = PublishResult::ReconciledExisting;
			return true;
		}
		AddDiagnostic(out_arrDiagnostics, "already_exists", "$", "target exists and will not be overwritten");
		return false;
	}
	const std::string strSuffix = std::to_string(std::random_device{}());
	const fs::path stStaging = stTarget.parent_path() / (stTarget.filename().string() + ".tmp-" + strSuffix);
	if (!fs::create_directory(stStaging, stError) || stError)
	{
		AddDiagnostic(out_arrDiagnostics, "staging_create", "$", "unable to create unique staging directory");
		return false;
	}
	bool bPublished = false;
	do
	{
		if (!WriteFile(stStaging / "AssetManifest.json", reinterpret_cast<const std::uint8_t *>(stCopy.strManifestJson.data()), stCopy.strManifestJson.size(), out_arrDiagnostics) ||
			!WriteFile(stStaging / "Scene.json", reinterpret_cast<const std::uint8_t *>(stCopy.strSceneJson.data()), stCopy.strSceneJson.size(), out_arrDiagnostics) ||
			!fs::create_directory(stStaging / "blobs", stError) || stError)
		{
			break;
		}
		bool bWriteSucceeded = true;
		for (const std::pair<const std::string, std::vector<std::uint8_t>> &stEntry : stCopy.mapBlobs)
		{
			bWriteSucceeded = WriteFile(stStaging / "blobs" / stEntry.first, stEntry.second.data(), stEntry.second.size(), out_arrDiagnostics) && bWriteSucceeded;
		}
		if (!bWriteSucceeded)
		{
			break;
		}
		PackageData stVerify;
		Diagnostics arrVerify;
		if (!LoadPackage(stStaging.string(), stVerify, arrVerify) || stVerify.strPackageDigest != stCopy.strPackageDigest)
		{
			AddDiagnostic(out_arrDiagnostics, "staging_verify", "$", "staging package verification failed");
			break;
		}
		// Cancel uses the same mutex, so the final check and rename share one
		// linearization point rather than a check-then-act race window.
		std::lock_guard<std::mutex> stCancellationLock(in_stCancellationMutex);
		if (in_fnCancelRequested && in_fnCancelRequested())
		{
			AddDiagnostic(out_arrDiagnostics, "cancelled", "$", "publication was cancelled before atomic rename");
			break;
		}
		if (!RenameNoReplace(stStaging, stTarget))
		{
			AddDiagnostic(out_arrDiagnostics, "publish_failed", "$", "atomic no-clobber publication failed");
			break;
		}
		bPublished = true;
		out_eResult = PublishResult::Published;
	} while (false);
	if (!bPublished)
	{
		fs::remove_all(stStaging, stError);
	}
	return bPublished;
}

Serialization::JsonValue DiagnosticsJson(const Diagnostics &in_arrDiagnostics)
{
	Serialization::JsonValue::List arrDiagnostics;
	for (const Diagnostic &stDiagnostic : in_arrDiagnostics)
	{
		arrDiagnostics.emplace_back(Serialization::JsonValue::Object{
				{ "code", stDiagnostic.strCode },
				{ "message", stDiagnostic.strMessage },
				{ "path", stDiagnostic.strPath },
		});
	}
	return Serialization::JsonValue(std::move(arrDiagnostics));
}

} // namespace EngineNext::Assets
