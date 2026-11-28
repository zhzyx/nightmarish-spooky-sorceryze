// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "Terrain3DQuadtree.h"

#include "terrain_3d.h"

Rect2i Terrain3DQuadTree::GetMaterialExtent() const
{
	if (!pTerrain || pTerrain->get_material()->get_world_background() == Terrain3DMaterial::NONE)
	{
		return rectExtent;
	}
	const int nSide = pTerrain->get_region_size() * Terrain3DData::REGION_MAP_SIZE;
	return Rect2i(-nSide / 2, -nSide / 2, nSide, nSide);
}

void Terrain3DQuadTree::Initialize(Terrain3D *in_pTerrain)
{
	pTerrain = in_pTerrain;
	Rebuild();
	UpdateIfDirty();
}

void Terrain3DQuadTree::UpdateIfDirty()
{
	if (!bDirty)
	{
		return;
	}
	bDirty = false;
	rectExtent = Rect2i();
	const TypedArray<Vector2i> arrLocations = pTerrain->get_data()->get_region_locations();
	if (arrLocations.is_empty())
	{
		return;
	}
	const int nRs = pTerrain->get_region_size();
	Vector2i vLo = arrLocations[0];
	Vector2i vHi = vLo;
	for (int nI = 1; nI < arrLocations.size(); ++nI)
	{
		const Vector2i vLoc = arrLocations[nI];
		vLo = vLo.min(vLoc);
		vHi = vHi.max(vLoc);
	}
	const Vector2i vSize = (vHi - vLo + Vector2i(1, 1)) * nRs;
	const int nSide = VariantUtilityFunctions::nearest_po2(MAX(nTileRes, MAX(vSize.x, vSize.y)));
	rectExtent = Rect2i(vLo * nRs, Vector2i(nSide, nSide));
}
