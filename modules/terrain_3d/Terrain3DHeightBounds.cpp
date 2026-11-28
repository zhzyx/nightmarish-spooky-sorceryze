// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "Terrain3DHeightBounds.h"

#include "core/templates/hash_map.h"
#include "servers/rendering/rendering_server.h"

#include "terrain_3d_data.h"

namespace
{
struct PageFootprintHasher
{
	static uint32_t hash(const Rect2i &rectFootprint)
	{
		return hash_murmur3_one_32(HashMapHasherDefault::hash(rectFootprint.size), HashMapHasherDefault::hash(rectFootprint.position));
	}
};
} // namespace

void Terrain3DHeightBounds::Clear()
{
	if (ridTexture.is_valid())
	{
		TERRAIN_RS->free_rid(ridTexture);
		ridTexture = RID();
	}
	rectExtent = Rect2i();
	arrRegions.clear();
	arrPyramid.clear();
}

Vector2 Terrain3DHeightBounds::GetGlobalRange() const
{
	if (arrPyramid.is_empty())
	{
		return Vector2();
	}
	const float *pRoot = reinterpret_cast<const float *>(arrPyramid.ptr() + arrPyramid.size()) - 2;
	return Vector2(pRoot[0], pRoot[1]);
}

Rect2i Terrain3DHeightBounds::PageSupport(Vector2i vPage) const
{
	// Every coarser mip's texel centres lie on a subset of the finest lattice.
	// Snap out to the coarsest texels: bilinear filtering and streaming fades
	// stay within this range even when just the root page is available.
	const Vector2i vLo = vPage * nTileSize / nPages;
	const Vector2i vHi = ((vPage + V2I(1)) * nTileSize + V2I(nPages - 1)) / nPages;
	const Vector2i vFrom = vLo * rectExtent.size.x / nTileSize;
	const Vector2i vLast = ((vHi * rectExtent.size.x + V2I(nTileSize - 1)) / nTileSize).min(rectExtent.size - V2I(1));
	return Rect2i(vFrom, vLast - vFrom + V2I(1));
}

Vector2 Terrain3DHeightBounds::Range(const Rect2i &in_rectRect) const
{
	const Vector2i vEnd = in_rectRect.get_end();
	const Vector2i vFirst = in_rectRect.position / nRegionSize;
	const Vector2i vLast = (vEnd - V2I(1)) / nRegionSize;
	const int nColumns = rectExtent.size.x / nRegionSize;
	float fLow = FLT_MAX;
	float fHigh = -FLT_MAX;
	for (int nRz = vFirst.y; nRz <= vLast.y; ++nRz)
	{
		for (int nRx = vFirst.x; nRx <= vLast.x; ++nRx)
		{
			const PackedByteArray &arrRegion = arrRegions[nRz * nColumns + nRx];
			if (arrRegion.is_empty())
			{
				fLow = MIN(fLow, 0.f);
				fHigh = MAX(fHigh, 0.f);
				continue;
			}
			const Vector2i vOrigin = Vector2i(nRx, nRz) * nRegionSize;
			const Vector2i vLo = in_rectRect.position.max(vOrigin) - vOrigin;
			const Vector2i vHi = vEnd.min(vOrigin + V2I(nRegionSize)) - vOrigin;
			const float *pData = reinterpret_cast<const float *>(arrRegion.ptr());
			for (int nY = vLo.y; nY < vHi.y; ++nY)
			{
				for (int nX = vLo.x; nX < vHi.x; ++nX)
				{
					const float fSample = pData[nY * nRegionSize + nX];
					const float fH = Math::is_finite(fSample) ? fSample : 0.f;
					fLow = MIN(fLow, fH);
					fHigh = MAX(fHigh, fH);
				}
			}
		}
	}
	// Both background blend functions read the four regions surrounding the
	// half-region-offset coordinate. Only their footprints can see ground/noise.
	if (bHasBackground)
	{
		const Rect2i rectFootprint = in_rectRect.grow(int(Math::ceil(0.502f * nRegionSize)) + 1);
		const Rect2i rectDomain(V2I(0), rectExtent.size);
		bool bBlends = !rectDomain.encloses(rectFootprint);
		const Rect2i rectClipped = rectDomain.intersection(rectFootprint);
		const Vector2i vLo = rectClipped.position / nRegionSize;
		const Vector2i vHi = (rectClipped.get_end() - V2I(1)) / nRegionSize;
		for (int nZ = vLo.y; !bBlends && nZ <= vHi.y; ++nZ)
		{
			for (int nX = vLo.x; nX <= vHi.x; ++nX)
			{
				if (arrRegions[nZ * nColumns + nX].is_empty())
				{
					bBlends = true;
					break;
				}
			}
		}
		if (bBlends)
		{
			fLow = MIN(fLow, fGroundHeight) + vNoiseRange.x;
			fHigh = MAX(fHigh, fGroundHeight) + vNoiseRange.y;
		}
	}
	return Vector2(fLow, fHigh);
}

void Terrain3DHeightBounds::UpdatePyramid(const Rect2i &rectChanged)
{
	const int nExtent = rectExtent.size.x;
	const int nRootStep = (nExtent + nTileSize - 1) / nTileSize;
	const Rect2i rectLocal(rectChanged.position - rectExtent.position, rectChanged.size);
	const Rect2i rectAffected = rectLocal.grow(nRootStep + 1).intersection(Rect2i(V2I(0), rectExtent.size));
	Vector2i vLo = rectAffected.position * nPages / nExtent;
	Vector2i vHi = ((rectAffected.get_end() * nPages + V2I(nExtent - 1)) / nExtent).min(V2I(nPages));
	float *pLevel = reinterpret_cast<float *>(arrPyramid.ptrw());
	HashMap<Rect2i, Vector2, PageFootprintHasher> mapReusableRanges;
	for (int nY = vLo.y; nY < vHi.y; ++nY)
	{
		for (int nX = vLo.x; nX < vHi.x; ++nX)
		{
			const Rect2i rectSupport = PageSupport(Vector2i(nX, nY));
			if (!rectSupport.intersects(rectLocal))
			{
				continue;
			}
			Vector2 vRange;
			if (nPages > nTileSize)
			{
				// Many fine pages have exactly the same coarsest sampling footprint.
				const Vector2 *pCachedRange = mapReusableRanges.getptr(rectSupport);
				if (pCachedRange)
				{
					vRange = *pCachedRange;
				}
				else
				{
					vRange = Range(rectSupport);
					mapReusableRanges.insert(rectSupport, vRange);
				}
			}
			else
			{
				vRange = Range(rectSupport);
			}
			const int nI = (nY * nPages + nX) * 2;
			pLevel[nI] = vRange.x;
			pLevel[nI + 1] = vRange.y;
		}
	}
	for (int nSide = nPages; nSide > 1; nSide >>= 1)
	{
		float *pParent = pLevel + nSide * nSide * 2;
		vLo /= 2;
		vHi = (vHi + V2I(1)) / 2;
		for (int nY = vLo.y; nY < vHi.y; ++nY)
		{
			for (int nX = vLo.x; nX < vHi.x; ++nX)
			{
				const float *pRow = pLevel + (2 * nY * nSide + 2 * nX) * 2;
				const float *pNext = pRow + 2 * nSide;
				const int nI = (nY * (nSide / 2) + nX) * 2;
				pParent[nI] = MIN(MIN(pRow[0], pRow[2]), MIN(pNext[0], pNext[2]));
				pParent[nI + 1] = MAX(MAX(pRow[1], pRow[3]), MAX(pNext[1], pNext[3]));
			}
		}
		pLevel = pParent;
	}
}

void Terrain3DHeightBounds::Update(Terrain3DData *in_pData, const Rect2i &in_rectExtent, int in_nRegionSize,
								   int in_nPages, int in_nTileSize, bool in_bHasBackground, float fGround, Vector2 in_vNoiseRange, Vector<Rect2i> &out_arrChanged)
{
	const bool bFresh = rectExtent != in_rectExtent || nPages != in_nPages || nTileSize != in_nTileSize || nRegionSize != in_nRegionSize;
	if (bFresh)
	{
		Clear();
		rectExtent = in_rectExtent;
		nRegionSize = in_nRegionSize;
		nPages = in_nPages;
		nTileSize = in_nTileSize;
		const int nColumns = rectExtent.size.x / nRegionSize;
		arrRegions.resize(nColumns * nColumns);
		int nTexels = 0;
		for (int nSide = in_nPages; nSide; nSide >>= 1)
		{
			nTexels += nSide * nSide;
		}
		arrPyramid.resize(nTexels * 2 * sizeof(float));
	}
	bool bRebuildBounds = bFresh || bHasBackground != in_bHasBackground || fGroundHeight != fGround || vNoiseRange != in_vNoiseRange;
	bHasBackground = in_bHasBackground;
	fGroundHeight = fGround;
	vNoiseRange = in_vNoiseRange;
	const Vector2i vFirstRegion = rectExtent.position / nRegionSize;
	const int nColumns = rectExtent.size.x / nRegionSize;
	for (int nI = 0; nI < arrRegions.size(); ++nI)
	{
		const Vector2i vLocation = vFirstRegion + Vector2i(nI % nColumns, nI / nColumns);
		Terrain3DRegion *pRegion = in_pData->get_region_ptr(vLocation);
		PackedByteArray arrNow;
		if (pRegion && !pRegion->is_deleted())
		{
			Ref<Image> refH = pRegion->get_height_map();
			if (refH.is_valid() && refH->get_format() == Image::FORMAT_RF && refH->get_size() == V2I(nRegionSize))
			{
				arrNow = refH->get_data();
			}
		}
		if (!bFresh)
		{
			bRebuildBounds |= bHasBackground && arrRegions[nI].is_empty() != arrNow.is_empty();
			Rect2i rectRect = Terrain3DData::GetChangedMapRect(arrRegions[nI], arrNow, nRegionSize);
			if (rectRect.has_area())
			{
				rectRect.position += vLocation * nRegionSize;
				out_arrChanged.push_back(rectRect);
			}
		}
		arrRegions.ptrw()[nI] = arrNow;
	}
	if (bFresh)
	{
		out_arrChanged.push_back(rectExtent);
	}
	if (bRebuildBounds || !out_arrChanged.is_empty())
	{
		if (bRebuildBounds)
		{
			UpdatePyramid(rectExtent);
		}
		else
		{
			for (const Rect2i &rectRect : out_arrChanged)
			{
				UpdatePyramid(rectRect);
			}
		}
		const Ref<Image> refImg = Image::create_from_data(nPages, nPages, true, Image::FORMAT_RGF, arrPyramid);
		if (ridTexture.is_valid())
		{
			TERRAIN_RS->texture_2d_update(ridTexture, refImg, 0);
		}
		else
		{
			ridTexture = TERRAIN_RS->texture_2d_create(refImg);
		}
	}
}
