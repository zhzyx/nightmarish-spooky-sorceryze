/**************************************************************************/
/*  DeformationChanges.cpp                                                */
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

#include "engine_next/Rendering/DeformationChanges.h"
#include "engine_next/Rendering/ShadowBounds.h"

#include <cstddef>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
bool Bounds(const std::vector<MeshVertex> &arrVertices, const AnimationMatrix &arrWorld,
			WorldBounds &out_stBounds, Assets::Diagnostics &out_arrDiagnostics)
{
	const AnimationMatrix arrIdentity{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	WorldBounds stLocal;
	if (!TransformShadowBounds(arrVertices, arrIdentity, stLocal, out_arrDiagnostics))
	{
		return false;
	}
	if (!TransformProbeGeometryBounds(stLocal, arrWorld, out_stBounds))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "deformation_changes", "$", "Deformed world bounds exceed the finite GPU transform range.");
		return false;
	}
	return true;
}
} // namespace

bool BuildDeformationGeometryChanges(const DeformationFrame &stPrevious, const DeformationFrame &stCurrent,
									 const std::vector<AnimationMatrix> &arrPreviousWorlds, const std::vector<AnimationMatrix> &arrCurrentWorlds,
									 std::vector<GiGeometryChange> &out_arrChanges, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stPrevious.arrDraws.size() != stCurrent.arrDraws.size() || arrPreviousWorlds.size() != arrCurrentWorlds.size())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "deformation_changes", "$", "Pose or temporal instance layouts differ.");
		return false;
	}
	std::vector<GiGeometryChange> arrChanges;
	for (std::size_t nIndex = 0; nIndex < stCurrent.arrDraws.size(); ++nIndex)
	{
		const DeformedDraw &stBefore = stPrevious.arrDraws[nIndex];
		const DeformedDraw &stAfter = stCurrent.arrDraws[nIndex];
		if (stBefore.nDraw != stAfter.nDraw || stAfter.nDraw >= arrCurrentWorlds.size() ||
			stBefore.arrVertices.size() != stAfter.arrVertices.size() || stAfter.arrVertices.empty() ||
			(nIndex != 0 && stCurrent.arrDraws[nIndex - 1].nDraw >= stAfter.nDraw))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "deformation_changes", "$", "Deformed draws require stable unique ordered identities and vertex counts.");
			return false;
		}
		bool bChanged = arrPreviousWorlds[stAfter.nDraw] != arrCurrentWorlds[stAfter.nDraw];
		for (std::size_t nVertex = 0; nVertex < stAfter.arrVertices.size() && !bChanged; ++nVertex)
		{
			const MeshVertex &stOld = stBefore.arrVertices[nVertex];
			const MeshVertex &stNew = stAfter.arrVertices[nVertex];
			bChanged = stOld.arrPosition != stNew.arrPosition || stOld.arrNormal != stNew.arrNormal ||
					stOld.arrTangent != stNew.arrTangent || stOld.arrTexcoord != stNew.arrTexcoord;
		}
		if (!bChanged)
		{
			continue;
		}
		GiGeometryChange stChange;
		stChange.nDraw = stAfter.nDraw;
		if (!Bounds(stBefore.arrVertices, arrPreviousWorlds[stAfter.nDraw], stChange.stPreviousWorldBounds, out_arrDiagnostics) ||
			!Bounds(stAfter.arrVertices, arrCurrentWorlds[stAfter.nDraw], stChange.stCurrentWorldBounds, out_arrDiagnostics))
		{
			return false;
		}
		arrChanges.push_back(stChange);
	}
	out_arrChanges = std::move(arrChanges);
	return true;
}
} // namespace EngineNext::Rendering
