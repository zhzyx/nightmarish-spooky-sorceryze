/**************************************************************************/
/*  TestSceneRuntime.cpp                                                  */
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
#include "engine_next/Network/SessionManager.h"
#include "engine_next/Tests/Assets/FixtureSupport.h"
#include "engine_next/include/EngineNext/Assets/AssetCompiler.h"
#include "engine_next/include/EngineNext/Runtime/SceneRuntime.h"

#include <filesystem>

namespace
{

EngineNext::Assets::BuildRequest SpawnRequest()
{
	EngineNext::Assets::BuildRequest stRequest;
	stRequest.stScene.strSceneId = "m3.runtime";
	stRequest.stScene.strSceneRevision = "r7";
	stRequest.stScene.nFixedStepMsec = 20;
	stRequest.stScene.dMaxSpeed = 4.5;
	for (const std::int64_t nEntityId : { 20, 10 })
	{
		EngineNext::Assets::SceneEntity stEntity;
		stEntity.nEntityId = nEntityId;
		stEntity.strName = "spawn" + std::to_string(nEntityId);
		stEntity.strNodeType = "Node3D";
		stEntity.strGameplayKind = "player_spawn";
		stEntity.stTransform.arrTranslation[0] = nEntityId == 10 ? 2.0 : -3.0;
		stRequest.stScene.arrEntities.push_back(stEntity);
	}
	return stRequest;
}

} // namespace

ENGINE_NEXT_TEST("SceneRuntime loads package identity simulation and stable ordered spawns")
{
	namespace fs = std::filesystem;
	const fs::path stRoot = fs::current_path() / "M3SceneRuntimeTest";
	fs::remove_all(stRoot);
	fs::create_directories(stRoot);
	EngineNext::Assets::PackageData stPackage;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const bool bCompiled = EngineNext::Assets::CompilePackage(EngineNext::Tests::Assets::FixtureRoot().string(), SpawnRequest(), stPackage, arrDiagnostics);
	ENGINE_NEXT_CHECK(bCompiled);
	if (bCompiled)
	{
		EngineNext::Assets::PublishResult eResult = EngineNext::Assets::PublishResult::Published;
		ENGINE_NEXT_CHECK(EngineNext::Assets::PublishPackage(stPackage, (stRoot / "scene.enpak").string(), eResult, arrDiagnostics));
		EngineNext::Runtime::SceneRuntime stScene;
		ENGINE_NEXT_CHECK(stScene.Load((stRoot / "scene.enpak").string(), arrDiagnostics));
		ENGINE_NEXT_CHECK(stScene.IsLoaded());
		ENGINE_NEXT_CHECK_EQ(stScene.GetSceneId(), std::string("m3.runtime"));
		ENGINE_NEXT_CHECK_EQ(stScene.GetSceneRevision(), std::string("r7"));
		ENGINE_NEXT_CHECK_EQ(stScene.GetPackageDigest(), stPackage.strPackageDigest);
		ENGINE_NEXT_CHECK_EQ(stScene.GetSceneContentSha256(), stPackage.stManifest.strSceneContentSha256);
		ENGINE_NEXT_CHECK_EQ(stScene.GetPredictionModel().GetFixedStepMsec(), 20U);
		ENGINE_NEXT_CHECK_FLOAT(stScene.GetPredictionModel().GetMaxSpeed(), 4.5F);
		ENGINE_NEXT_CHECK_EQ(stScene.GetSpawnCount(), 2U);
		const EngineNext::Runtime::SpawnDefinition *pFirst = stScene.GetSpawn(0);
		const EngineNext::Runtime::SpawnDefinition *pSecond = stScene.GetSpawn(1);
		ENGINE_NEXT_CHECK(pFirst != nullptr && pSecond != nullptr);
		ENGINE_NEXT_CHECK_EQ(pFirst->stEntityId.nValue, 10ULL);
		ENGINE_NEXT_CHECK_EQ(pSecond->stEntityId.nValue, 20ULL);
		ENGINE_NEXT_CHECK_FLOAT(pFirst->vPosition.fX, 2.0F);
		ENGINE_NEXT_CHECK_FLOAT(pSecond->vPosition.fX, -3.0F);
		ENGINE_NEXT_CHECK(stScene.FindSpawn(EngineNext::Runtime::EntityId{ 20 }) == pSecond);
		ENGINE_NEXT_CHECK(stScene.FindSpawn(EngineNext::Runtime::EntityId{ 1 }) == nullptr);
		ENGINE_NEXT_CHECK(stScene.GetSpawn(2) == nullptr);
		EngineNext::Runtime::World stWorld;
		EngineNext::Network::SessionManager stSessions(stWorld, 7, &stScene, stScene.GetPredictionModel().GetFixedStepMsec());
		for (EngineNext::Network::PeerId nPeerId = 1; nPeerId <= 2; ++nPeerId)
		{
			EngineNext::Network::ClientHello stHello;
			EngineNext::Network::ServerWelcome stWelcome;
			std::uint64_t nSessionId = 0;
			ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(nPeerId, stHello, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::Ok);
			ENGINE_NEXT_CHECK_EQ(stWelcome.nEntityId, nPeerId == 1 ? 10ULL : 20ULL);
			ENGINE_NEXT_CHECK_EQ(stWelcome.nFixedStepMsec, 20U);
			ENGINE_NEXT_CHECK_FLOAT(stWelcome.vPosition.fX, nPeerId == 1 ? 2.0F : -3.0F);
		}
		EngineNext::Network::ClientHello stHello;
		EngineNext::Network::ServerWelcome stWelcome;
		std::uint64_t nSessionId = 0;
		ENGINE_NEXT_CHECK_EQ(stSessions.CreateSession(3, stHello, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::InvalidState);
		EngineNext::Runtime::World stZeroWorld;
		EngineNext::Network::SessionManager stZeroSessions(stZeroWorld, 7, nullptr, 0);
		ENGINE_NEXT_CHECK_EQ(stZeroSessions.CreateSession(1, stHello, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
		stHello.nResumeSessionId = 1;
		ENGINE_NEXT_CHECK_EQ(stZeroSessions.ResumeSession(1, stHello, 0, stWelcome, nSessionId), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
		ENGINE_NEXT_CHECK(!stScene.Load((stRoot / "missing.enpak").string(), arrDiagnostics));
		ENGINE_NEXT_CHECK(!stScene.IsLoaded());
		ENGINE_NEXT_CHECK_EQ(stScene.GetPredictionModel().GetFixedStepMsec(), 16U);
		ENGINE_NEXT_CHECK(stScene.ConfigureDefaultSimulation(20));
		ENGINE_NEXT_CHECK_EQ(stScene.GetPredictionModel().GetFixedStepMsec(), 20U);
		ENGINE_NEXT_CHECK(!stScene.ConfigureDefaultSimulation(0));
	}
	fs::remove_all(stRoot);
}
