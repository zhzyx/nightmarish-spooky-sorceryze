// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#pragma once

#include "constants.h"

class Terrain3DData;

// CPU snapshots share Image storage until a region is edited. The mip chain holds
// conservative metre ranges for the actual vertex lattice, including resident-ancestor sampling.
class Terrain3DHeightBounds
{
	Rect2i rectExtent;
	int nPages = 0;
	int nTileSize = 0;
	int nRegionSize = 0;
	bool bHasBackground = false;
	float fGroundHeight = 0.f;
	Vector2 vNoiseRange;
	Vector<PackedByteArray> arrRegions;
	PackedByteArray arrPyramid;
	RID ridTexture;

	Rect2i PageSupport(Vector2i vPage) const;
	Vector2 Range(const Rect2i &in_rectRect) const;
	void UpdatePyramid(const Rect2i &rectChanged);

public:
	void Clear();
	void Update(Terrain3DData *in_pData, const Rect2i &in_rectExtent, int in_nRegionSize, int in_nPages, int in_nTileSize,
				bool in_bHasBackground, float fGround, Vector2 in_vNoiseRange, Vector<Rect2i> &out_arrChanged);
	Vector2 GetGlobalRange() const;
	RID GetTexture() const
	{
		return ridTexture;
	}
};
