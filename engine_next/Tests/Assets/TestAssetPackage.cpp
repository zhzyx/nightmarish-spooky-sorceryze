/**************************************************************************/
/*  TestAssetPackage.cpp                                                  */
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

#include "engine_next/Tests/TestFramework.h"
#include "engine_next/Tests/Assets/FixtureSupport.h"
#include "engine_next/include/EngineNext/Assets/AssetCompiler.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <atomic>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <thread>

namespace
{

EngineNext::Assets::BuildRequest ValidRequest()
{
	const std::vector<std::uint8_t> arrBytes = EngineNext::Tests::Assets::ReadFixture("valid.glb");
	const std::string strDigest = EngineNext::Serialization::Sha256Hex(arrBytes.data(), arrBytes.size());
	EngineNext::Assets::BuildRequest stRequest;
	stRequest.stScene.strSceneId = "m3.package";
	stRequest.stScene.strSceneRevision = "r1";
	EngineNext::Assets::SceneEntity stEntity;
	stEntity.nEntityId = 7;
	stEntity.strName = "mesh";
	stEntity.strNodeType = "MeshInstance3D";
	stEntity.strGameplayKind = "static";
	stEntity.arrAssets.push_back(EngineNext::Assets::SceneAssetRef{ "mesh", { "mesh", "r1", strDigest } });
	stRequest.stScene.arrEntities.push_back(stEntity);
	EngineNext::Assets::AssetInput stInput;
	stInput.stAsset.strAssetId = "mesh";
	stInput.stAsset.strRevision = "r1";
	stInput.stAsset.strType = "mesh";
	stInput.stAsset.strMediaType = "model/gltf-binary";
	stInput.stAsset.stSource.strKind = "godot_whitelist_import";
	stInput.stAsset.stSource.strImporterVersion = "1";
	stInput.strPath = "valid.glb";
	stRequest.arrAssets.push_back(stInput);
	return stRequest;
}

} // namespace

ENGINE_NEXT_TEST("Asset package is deterministic across clean directories and no-clobber")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3PackageTest";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot / "a");
	fs::create_directories(stRoot / "b");
	const EngineNext::Assets::BuildRequest stRequest = ValidRequest();
	EngineNext::Assets::PackageData stFirst;
	EngineNext::Assets::PackageData stSecond;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), stRequest, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), stRequest, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFirst.strManifestJson, stSecond.strManifestJson);
	ENGINE_NEXT_CHECK_EQ(stFirst.strPackageDigest, stSecond.strPackageDigest);
	EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
	ENGINE_NEXT_CHECK(EngineNext::Assets::PublishPackage(stFirst, (stRoot / "a/scene.enpak").string(), eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(eResult == EngineNext::Assets::PublishResult::Published);
	ENGINE_NEXT_CHECK(EngineNext::Assets::PublishPackage(stSecond, (stRoot / "a/scene.enpak").string(), eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(eResult == EngineNext::Assets::PublishResult::ReconciledExisting);
	EngineNext::Assets::PackageData stLoaded;
	ENGINE_NEXT_CHECK(EngineNext::Assets::LoadPackage((stRoot / "a/scene.enpak").string(), stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stLoaded.strPackageDigest, stFirst.strPackageDigest);
	ENGINE_NEXT_CHECK(EngineNext::Assets::PublishPackage(stSecond, (stRoot / "b/scene.enpak").string(), eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stLoaded.strManifestJson, stSecond.strManifestJson);
	fs::remove_all(stRoot);
}

ENGINE_NEXT_TEST("Asset compiler rejects path escape duplicate IDs and invalid blobs")
{
	EngineNext::Assets::BuildRequest stRequest = ValidRequest();
	stRequest.arrAssets[0].strPath = "../valid.glb";
	EngineNext::Assets::PackageData stPackage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), stRequest, stPackage, arrDiagnostics));

	stRequest = ValidRequest();
	stRequest.arrAssets.push_back(stRequest.arrAssets.front());
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), stRequest, stPackage, arrDiagnostics));

	stRequest = ValidRequest();
	stRequest.arrAssets[0].strPath = "invalid.glb";
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), stRequest, stPackage, arrDiagnostics));
}

ENGINE_NEXT_TEST("Asset package rejects tampering and unexpected files without modifying the source")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3TamperTest";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	EngineNext::Assets::PackageData stPackage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), ValidRequest(), stPackage, arrDiagnostics));
	EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
	ENGINE_NEXT_CHECK(EngineNext::Assets::PublishPackage(stPackage, (stRoot / "scene.enpak").string(), eResult, arrDiagnostics));
	const fs::path stBlob = stRoot / "scene.enpak/blobs" / stPackage.stManifest.arrAssets[0].strContentSha256;
	std::ofstream stStream(stBlob, std::ios::binary | std::ios::app);
	stStream.put('X');
	stStream.close();
	EngineNext::Assets::PackageData stLoaded;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::LoadPackage((stRoot / "scene.enpak").string(), stLoaded, arrDiagnostics));
	stStream.open(stRoot / "scene.enpak/unexpected.txt");
	stStream << "unexpected";
	stStream.close();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::LoadPackage((stRoot / "scene.enpak").string(), stLoaded, arrDiagnostics));
	fs::remove_all(stRoot);
}

ENGINE_NEXT_TEST("Asset compiler rejects intermediate directory links")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3LinkTest";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot / "source");
	fs::create_directories(stRoot / "outside");
	fs::copy_file(EngineNext::Tests::Assets::FixtureRoot() / "valid.glb", stRoot / "outside/valid.glb");
	std::error_code stError;
	fs::create_directory_symlink(stRoot / "outside", stRoot / "source/link", stError);
	if (!stError)
	{
		EngineNext::Assets::BuildRequest stRequest = ValidRequest();
		stRequest.arrAssets[0].strPath = "link/valid.glb";
		EngineNext::Assets::PackageData stPackage;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Assets::CompilePackage((stRoot / "source").string(), stRequest, stPackage, arrDiagnostics));
	}
	fs::remove_all(stRoot);
}

ENGINE_NEXT_TEST("Asset publication validates forged input before reconciling an existing package")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3ForgeTest";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	EngineNext::Assets::PackageData stPackage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), ValidRequest(), stPackage, arrDiagnostics));
	EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
	ENGINE_NEXT_CHECK(EngineNext::Assets::PublishPackage(stPackage, (stRoot / "scene.enpak").string(), eResult, arrDiagnostics));
	EngineNext::Assets::PackageData stForged = stPackage;
	stForged.mapBlobs.begin()->second.push_back(0);
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::PublishPackage(stForged, (stRoot / "scene.enpak").string(), eResult, arrDiagnostics));
	EngineNext::Assets::PackageData stLoaded;
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(EngineNext::Assets::LoadPackage((stRoot / "scene.enpak").string(), stLoaded, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stLoaded.strPackageDigest, stPackage.strPackageDigest);
	fs::remove_all(stRoot);
}

ENGINE_NEXT_TEST("Guarded publication cancels before the atomic rename")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3GuardedTest";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	EngineNext::Assets::PackageData stPackage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), ValidRequest(), stPackage, arrDiagnostics));
	EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
	std::mutex stCancellationMutex;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::PublishPackageGuarded(stPackage, (stRoot / "scene.enpak").string(), eResult, arrDiagnostics, stCancellationMutex, []()
			{ return true; }));
	ENGINE_NEXT_CHECK(!fs::exists(stRoot / "scene.enpak"));
	fs::remove_all(stRoot);
}

ENGINE_NEXT_TEST("Guarded publication serializes cancellation with the atomic rename")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3GuardedRaceTest";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	EngineNext::Assets::PackageData stPackage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const bool bCompiled = EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), ValidRequest(), stPackage, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCompiled);
	if (!bCompiled)
	{
		fs::remove_all(stRoot);
		return;
	}
	std::mutex stCancellationMutex;
	std::atomic<bool> bCallbackEntered{ false };
	std::atomic<bool> bTryLockReturned{ false };
	std::atomic<bool> bCancelRequested{ false };
	std::atomic<bool> bCancellationReturned{ false };
	std::thread stCancellation([&]()
			{
		while (!bCallbackEntered)
		{
			std::this_thread::yield();
		}
		std::unique_lock<std::mutex> stLock(stCancellationMutex, std::defer_lock);
		const bool bLocked = stLock.try_lock();
		if (bLocked)
		{
			bCancelRequested = true;
		}
		bTryLockReturned = true;
		if (!bLocked)
		{
			stLock.lock();
			bCancelRequested = true;
		}
		bCancellationReturned = true; });
	EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
	const bool bPublished = EngineNext::Assets::PublishPackageGuarded(stPackage, (stRoot / "scene.enpak").string(), eResult, arrDiagnostics,
			stCancellationMutex,
			[&]()
			{
				bCallbackEntered = true;
				while (!bTryLockReturned)
				{
					std::this_thread::yield();
				}
				return bCancelRequested.load();
			});
	stCancellation.join();
	ENGINE_NEXT_CHECK(bPublished);
	ENGINE_NEXT_CHECK(eResult == EngineNext::Assets::PublishResult::Published);
	ENGINE_NEXT_CHECK(bCancellationReturned);
	ENGINE_NEXT_CHECK(fs::exists(stRoot / "scene.enpak"));
	fs::remove_all(stRoot);
}
