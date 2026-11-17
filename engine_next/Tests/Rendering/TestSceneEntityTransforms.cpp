/**************************************************************************/
/*  TestSceneEntityTransforms.cpp                                         */
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
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"

#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>

namespace
{

EngineNext::Assets::SceneDocument Scene()
{
	EngineNext::Assets::SceneDocument stScene;
	stScene.strSceneId = "volume.hierarchy";
	stScene.strSceneRevision = "r1";
	EngineNext::Assets::SceneEntity stRoot;
	stRoot.nEntityId = 1;
	stRoot.strName = "root";
	stRoot.strNodeType = "Node3D";
	stRoot.strGameplayKind = "static";
	EngineNext::Assets::SceneEntity stChild = stRoot;
	stChild.nEntityId = 2;
	stChild.nParentEntityId = 1;
	stChild.strName = "child";
	stScene.arrEntities = { stChild, stRoot };
	return stScene;
}

void Near(double dActual, double dExpected)
{
	ENGINE_NEXT_CHECK(std::isfinite(dActual));
	ENGINE_NEXT_CHECK(std::abs(dActual - dExpected) < 1e-10 * (1 + std::abs(dExpected)));
}

} // namespace

ENGINE_NEXT_TEST("Scene entity transforms include non-renderable parents and nested rotation scale")
{
	EngineNext::Assets::SceneDocument stScene = Scene();
	const double dHalfSqrt = std::sqrt(.5);
	stScene.arrEntities[1].stTransform.arrTranslation = { 10, 20, 30 };
	stScene.arrEntities[1].stTransform.arrRotation = { 0, 0, dHalfSqrt, dHalfSqrt };
	stScene.arrEntities[1].stTransform.arrScale = { 2, 3, 4 };
	stScene.arrEntities[0].stTransform.arrTranslation = { 1, 2, 3 };
	stScene.arrEntities[0].stTransform.arrScale = { .5, 2, 1 };
	std::map<std::uint64_t, std::array<double, 16>> mapTransforms;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildSceneEntityTransforms(stScene, mapTransforms, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(mapTransforms.size(), 2U);
	const std::array<double, 16> &arrChild = mapTransforms.at(2);
	Near(arrChild[12], 4);
	Near(arrChild[13], 22);
	Near(arrChild[14], 42);
	Near(arrChild[0], 0);
	Near(arrChild[1], 1);
	Near(arrChild[4], -6);
	Near(arrChild[5], 0);
	Near(arrChild[10], 4);
	ENGINE_NEXT_CHECK_EQ(stScene.arrEntities[0].stTransform.arrTranslation[0], 1);
}

ENGINE_NEXT_TEST("Scene entity transforms resolve submitted local translations through parents")
{
	EngineNext::Assets::SceneDocument stScene = Scene();
	stScene.arrEntities[1].stTransform.arrTranslation = { 10, 0, 0 };
	stScene.arrEntities[1].stTransform.arrScale = { -2, 1, 1 };
	stScene.arrEntities[0].stTransform.arrTranslation = { 3, 0, 0 };
	std::map<std::uint64_t, std::array<double, 16>> mapTransforms;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildSceneEntityTransforms(stScene, mapTransforms, arrDiagnostics));
	Near(mapTransforms.at(2)[12], 4);
	stScene.arrEntities[0].stTransform.arrTranslation = { 4, 0, 0 };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildSceneEntityTransforms(stScene, mapTransforms, arrDiagnostics));
	Near(mapTransforms.at(2)[12], 2);
}

ENGINE_NEXT_TEST("Scene entity transform validation preserves output on invalid hierarchy")
{
	for (int nCase = 0; nCase < 5; ++nCase)
	{
		EngineNext::Assets::SceneDocument stScene = Scene();
		if (nCase == 0)
		{
			stScene.arrEntities[0].nParentEntityId = 7;
		}
		else if (nCase == 1)
		{
			stScene.arrEntities[1].nParentEntityId = 2;
		}
		else if (nCase == 2)
		{
			stScene.arrEntities[0].stTransform.arrScale[0] = 0;
		}
		else if (nCase == 3)
		{
			stScene.arrEntities[0].stTransform.arrTranslation[0] = std::numeric_limits<double>::quiet_NaN();
		}
		else
		{
			stScene.arrEntities[1].stTransform.arrScale[0] = std::numeric_limits<float>::max();
			stScene.arrEntities[0].stTransform.arrScale[0] = 2;
		}
		std::map<std::uint64_t, std::array<double, 16>> mapTransforms{ { 99, {} } };
		mapTransforms[99][12] = 123;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildSceneEntityTransforms(stScene, mapTransforms, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(mapTransforms.size(), 1U);
		ENGINE_NEXT_CHECK_EQ(mapTransforms.at(99)[12], 123);
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	}
}

ENGINE_NEXT_TEST("Scene entity transform success does not consume unrelated diagnostics")
{
	std::map<std::uint64_t, std::array<double, 16>> mapTransforms;
	EngineNext::Assets::Diagnostics arrDiagnostics{ { "previous", "$", "unrelated" } };
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildSceneEntityTransforms(Scene(), mapTransforms, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(mapTransforms.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(arrDiagnostics.size(), 1U);
}
