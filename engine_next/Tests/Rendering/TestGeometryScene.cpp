/**************************************************************************/
/*  TestGeometryScene.cpp                                                 */
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
#include "engine_next/include/EngineNext/Rendering/GeometryScene.h"
#include "engine_next/Rendering/Cook/MeshCluster.h"
#include <cstring>
#include <limits>

namespace
{
using namespace EngineNext::Rendering;
RenderScene Scene()
{
	RenderScene stScene;
	RenderAsset stAsset;
	stAsset.stMesh.arrMaterials.resize(1);
	MeshPrimitive stPrimitive;
	MeshVertex stA, stB, stC;
	stA.arrPosition = { -1, -1, 0 };
	stB.arrPosition = { 1, -1, 0 };
	stC.arrPosition = { 0, 1, 0 };
	stPrimitive.arrVertices = { stA, stB, stC };
	stPrimitive.arrIndices = { 0, 1, 2 };
	stAsset.stMesh.arrPrimitives.push_back(stPrimitive);
	stScene.arrAssets.push_back(stAsset);
	for (std::uint32_t nIndex = 0; nIndex < 2; ++nIndex)
	{
		RenderInstance stInstance;
		stInstance.nEntityId = nIndex + 1;
		stInstance.arrTransform = { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, static_cast<double>(nIndex) * 3, 0, 0, 1 };
		stScene.arrInstances.push_back(stInstance);
	}
	return stScene;
}
} //namespace
ENGINE_NEXT_TEST("Geometry source adaptation preserves cluster ranges and draw identity")
{
	RenderScene stScene = Scene();
	GeometrySettings stSettings;
	GeometryClusterSet stOutput;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildGeometryClusterSet(stScene, stSettings, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.nCandidateCount, 2U);
	ENGINE_NEXT_CHECK_EQ(stOutput.nTriangleCount, 2U);
	ENGINE_NEXT_CHECK_EQ(stOutput.arrBuckets.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stOutput.arrBuckets[0].nCommandCapacity, 2U);
	ENGINE_NEXT_CHECK_EQ(stOutput.arrClusters[0].stInput.arrDraw, (std::array<std::uint32_t, 4>{ 3, 0, 0, 0 }));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrClusters[1].stInput.arrDraw, (std::array<std::uint32_t, 4>{ 3, 0, 0, 1 }));
	const GeometryClusterSet stLegacy = stOutput;
	ENGINE_NEXT_CHECK(CookMeshClusters(stScene.arrAssets[0].stMesh.arrPrimitives[0], stScene.arrAssets[0].stMesh.arrPrimitives[0].arrClusters, arrDiagnostics));
	stScene.nGpuFormatVersion = 2;
	ENGINE_NEXT_CHECK(BuildGeometryClusterSet(stScene, stSettings, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK(std::memcmp(stLegacy.arrClusters.data(), stOutput.arrClusters.data(), 2 * sizeof(GeometryCluster)) == 0);
}
ENGINE_NEXT_TEST("Geometry command budget selects complete conventional fallback")
{
	GeometrySettings stSettings;
	stSettings.nMaxCommands = 1;
	GeometryClusterSet stOutput;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildGeometryClusterSet(Scene(), stSettings, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK(stOutput.bCapacityFallback);
	ENGINE_NEXT_CHECK_EQ(stOutput.nCandidateCount, 2U);
	ENGINE_NEXT_CHECK(stOutput.arrClusters.empty() && stOutput.arrBuckets.empty());
}
ENGINE_NEXT_TEST("Geometry buckets preserve material and winding variants")
{
	RenderScene stScene = Scene();
	stScene.arrInstances[1].arrTransform[0] = -1;
	GeometryClusterSet stOutput;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildGeometryClusterSet(stScene, GeometrySettings{}, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrBuckets.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stOutput.arrBuckets[0].nFlags, 0U);
	ENGINE_NEXT_CHECK_EQ(stOutput.arrBuckets[1].nFlags, 1U);
	stScene.arrAssets[0].stMesh.arrMaterials[0].bDoubleSided = true;
	ENGINE_NEXT_CHECK(BuildGeometryClusterSet(stScene, GeometrySettings{}, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrBuckets[0].nFlags, 2U);
	ENGINE_NEXT_CHECK_EQ(stOutput.arrBuckets[1].nFlags, 3U);
	stScene.arrAssets[0].stMesh.arrMaterials[0].eAlphaMode = AlphaMode::Blend;
	ENGINE_NEXT_CHECK(BuildGeometryClusterSet(stScene, GeometrySettings{}, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK(stOutput.arrClusters.empty() && !stOutput.bCapacityFallback);
	ENGINE_NEXT_CHECK_EQ(stOutput.nTriangleCount, 2U);
}
ENGINE_NEXT_TEST("Geometry invalid topology and transforms preserve prior output")
{
	RenderScene stScene = Scene();
	GeometryClusterSet stOutput;
	stOutput.nCandidateCount = 88;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	stScene.arrInstances[0].arrTransform[0] = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!BuildGeometryClusterSet(stScene, GeometrySettings{}, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.nCandidateCount, 88U);
	stScene = Scene();
	ENGINE_NEXT_CHECK(CookMeshClusters(stScene.arrAssets[0].stMesh.arrPrimitives[0], stScene.arrAssets[0].stMesh.arrPrimitives[0].arrClusters, arrDiagnostics));
	stScene.arrAssets[0].stMesh.arrPrimitives[0].arrClusters[0].arrVertexIndices[0] = 2;
	ENGINE_NEXT_CHECK(!BuildGeometryClusterSet(stScene, GeometrySettings{}, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.nCandidateCount, 88U);
}
