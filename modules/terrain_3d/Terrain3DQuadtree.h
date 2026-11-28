// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#pragma once

#include "constants.h"

class Terrain3D;
class Terrain3DGPUDriven;

// The GPU derives each node's origin and parent from a power-of-two grid.
class Terrain3DQuadTree
{
	CLASS_NAME_STATIC("Terrain3DQuadTree");

	Terrain3D *pTerrain = nullptr;
	Rect2i rectExtent; // Authored region bounds in vertex-grid cells, padded to a square.
	int nTileRes = 32;
	bool bDirty = true;

public:
	void Initialize(Terrain3D *in_pTerrain);
	void Rebuild()
	{
		bDirty = true;
	}
	void UpdateIfDirty();
	const Rect2i &GetExtent() const
	{
		return rectExtent;
	}
	Rect2i GetMaterialExtent() const;
	int GetTileRes() const
	{
		return nTileRes;
	}
	void SetTileRes(int in_nTileRes)
	{
		if (nTileRes != in_nTileRes)
		{
			nTileRes = in_nTileRes;
			Rebuild();
		}
	}
};
