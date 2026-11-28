/**************************************************************************/
/*  RuntimeVirtualTexturePageManager.h                                   */
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

#pragma once

#pragma region Engine ZXB
// [ZXB] CPU-side page table / physical page pool for Runtime Virtual Texture (renderer agnostic, unit-testable).
#pragma endregion

#include "core/math/aabb.h"
#include "core/math/plane.h"
#include "core/math/rect2.h"
#include "core/math/transform_3d.h"
#include "core/math/vector3.h"
#include "core/templates/hash_map.h"
#include "core/templates/hash_set.h"
#include "core/templates/local_vector.h"
#include "core/templates/vector.h"

// Manages which virtual pages (level, x, y) live in which physical pool slot, and keeps the
// indirection (page table) mips up to date. Missing pages fall back to the nearest resident ancestor.
class RVTPageManager
{
public:
	struct Config
	{
		uint32_t nLog2Pages = 6; // Pages per side at level 0 = 1 << log2_pages.
		uint32_t nPoolPagesX = 16;
		uint32_t nPoolPagesY = 16;
		bool bPrioritizeCoverage = false;
		bool bFadeIn = false;
		uint32_t nResidentLevels = 2; // Coarsest N levels are always requested.
	};

	struct PageKey
	{
		uint32_t nLevel = 0;
		uint32_t nX = 0;
		uint32_t nY = 0;
		bool operator==(const PageKey &stOther) const
		{
			return nLevel == stOther.nLevel && nX == stOther.nX && nY == stOther.nY;
		}
	};

	struct PageRender
	{
		PageKey stKey;
		uint32_t nSlot = 0;
		uint32_t nPoolX = 0;
		uint32_t nPoolY = 0;
	};

	// RGBA8 page table texel. Level `level` is the level of the resident page this texel resolves to.
	struct PageTableEntry
	{
		uint8_t nPoolX = 0;
		uint8_t nPoolY = 0;
		uint8_t nLevel = 0;
		uint8_t nValid = 0;
	};

	// Parameters of a single viewer, all in the volume's metric local space (unscaled, centered at origin).
	struct HeightLOD
	{
		float fLod0Distance = 0.0f; // Zero selects standard screen-space VT requests.
		float fVertexSpacing = 1.0f;
		int nMaxLod = 0;
		float fMaxDistance = 0.0f;
	};
	struct View
	{
		Vector3 vViewer;
		Vector3 vSize = Vector3(1, 1, 1); // Metric size of the volume.
		HeightLOD stHeightLod;
		float fPixelPerDistance = 0.001f; // World size of one pixel at distance 1 (perspective).
		float fPixelOrtho = 0.0f;		  // If > 0, constant world size of one pixel (orthogonal cameras).
		float fLodBias = 0.0f;
		float fTexelSizeLevel0 = 0.01f; // Smallest world size of a level 0 texel.
		Vector<Plane> arrFrustum;		// Outward facing planes. Empty = no frustum culling.
	};

	// Snapshot of one page, for debugging and page picking.
	struct PageStatus
	{
		bool bExists = false;
		bool bResident = false;
		bool bDirty = false;
		bool bBlocked = false;
		uint64_t nContentSerial = 0;
		uint32_t nPoolX = 0;
		uint32_t nPoolY = 0;
	};

	struct Stats
	{
		uint32_t nResidentPages = 0;
		uint32_t nPoolPages = 0;
		uint32_t nRequestedPages = 0;
		uint32_t nRenderedThisFrame = 0;
		uint32_t nEvictedTotal = 0;
		uint32_t nRetainedOnMove = 0;
		uint32_t nDiscardedOnMove = 0;
		uint64_t nRenderedTotal = 0;
	};

private:
	enum PageState : uint8_t
	{
		STATE_RENDERING, // Slot reserved, content not produced yet.
		STATE_RESIDENT,
	};

	struct Page
	{
		uint32_t nSlot = 0;
		PageState eState = STATE_RENDERING;
		bool bDirty = false;
		Rect2 rectEditedArea;
		uint8_t nFade = 255;
		uint64_t nContentSerial = 0;
		uint64_t nLastUsed = 0;
	};

	struct Request
	{
		uint32_t nId;
		float fPriority;
	};

	Config stConfig;
	uint32_t nMaxLevel = 0;
	uint64_t nFrame = 1;
	uint64_t nMappingRevision = 1;

	HashMap<uint32_t, Page> mapPages;
	HashSet<uint32_t> setBlocked;		// Pages that failed to load; requests for them are ignored.
	LocalVector<uint32_t> arrSlotOwner; // Key id per slot, or INVALID_ID.
	LocalVector<uint32_t> arrFreeSlots;
	HashMap<uint32_t, float> mapRequests;

	LocalVector<Vector<uint8_t>> arrTableLevels;
	bool bTableDirty = true;
	LocalVector<Rect2> arrHeightChanges; // Completed fades, replaced contents and evictions in normalized terrain coordinates.
	Stats stStats;

	static constexpr uint32_t INVALID_ID = 0xFFFFFFFF;

public:
	static uint32_t MakePageId(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY)
	{
		return MakeId(in_nLevel, in_nX, in_nY);
	}
	static PageKey DecodePageId(uint32_t in_nId)
	{
		return FromId(in_nId);
	}
	// Number of resident pages per level (index = level).
	LocalVector<int32_t> GetResidentPagesByLevel() const;

private:
	static uint32_t MakeId(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY)
	{
		return (in_nLevel << 28) | (in_nY << 14) | in_nX;
	}
	static PageKey FromId(uint32_t in_nId)
	{
		return PageKey{ in_nId >> 28, in_nId & 0x3FFF, (in_nId >> 14) & 0x3FFF };
	}
	uint32_t LevelSize(uint32_t in_nLevel) const
	{
		return 1u << (stConfig.nLog2Pages - in_nLevel);
	}

	void SetEntry(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, const PageTableEntry &stEntry);
	PageTableEntry GetEntry(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const;
	PageTableEntry Resolve(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const;
	void MapPage(const PageKey &in_stKey, uint32_t in_nSlot);
	void UnmapPage(const PageKey &in_stKey, uint32_t in_nSlot);
	Rect2 PageRect(const PageKey &in_stKey) const;
	void ReleasePage(uint32_t in_nId);
	bool AllocateSlot(uint32_t &out_nSlot);
	void Visit(const View &stView, uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY);
	float LodAtDistance(const View &stView, float fDistance) const;

public:
	void Configure(const Config &in_stConfig);
	const Config &GetConfig() const
	{
		return stConfig;
	}
	void Reset();
	// Render-thread only. Preserve aligned world-space samples in their original physical slots.
	bool MoveWindow(const Transform3D &stOldVolume, const Transform3D &stNewVolume);
	void AdvanceMappingRevision()
	{
		nMappingRevision++;
	}
	uint64_t GetMappingRevision() const
	{
		return nMappingRevision;
	}
	bool IsFeedbackCurrent(uint64_t nRevision) const
	{
		return nRevision == nMappingRevision;
	}

	uint32_t GetMaxLevel() const
	{
		return nMaxLevel;
	}
	uint32_t GetLevelCount() const
	{
		return nMaxLevel + 1;
	}
	uint32_t GetPoolCapacity() const
	{
		return stConfig.nPoolPagesX * stConfig.nPoolPagesY;
	}

	// Starts a new frame, dropping the previous frame's requests.
	const LocalVector<Rect2> &GetHeightChanges() const
	{
		return arrHeightChanges;
	}
	void BeginFrame();

	void RequestPage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, float in_fPriority);
	// Translate a captured screen tile into this frame's window and cover its expected path.
	void RequestMovingFootprint(const PageKey &stKey, const Vector2 &vCurrentOffsetUV, const Vector2 &vVelocityUV, float fPriority);
	void RequestResidentLevels();
	void RequestView(const View &stView);

	// Reserves pool slots for up to p_max missing/dirty requested pages, coarsest first.
	void TakePending(uint32_t nMax, LocalVector<PageRender> &out_arrPages);
	void MarkRendered(const PageKey &in_stKey, bool bFromDisk = false);
	// Drops a page that never produced content (failed load) and frees its pool slot.
	void DiscardPage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY);
	// Drops the page and stops requesting it; sampling falls back to an ancestor.
	void BlockPage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY);
	// Marks a resident page stale so it is produced again (used by page picking).
	void InvalidatePage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY);
	PageStatus GetPageStatus(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const;

	// Marks pages overlapping the UV rect (level 0 UV space, 0..1) as stale.
	void InvalidateRect(const Rect2 &rectUvRect, float fBorderInTiles, const HashSet<uint32_t> *pExcluded = nullptr);
	void InvalidateRect(const Rect2 &rectUvRect);
	void InvalidateAll();

	bool IsResident(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const;
	bool GetSlot(const PageKey &in_stKey, uint32_t &out_nPoolX, uint32_t &out_nPoolY) const;
	PageTableEntry Lookup(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const
	{
		return GetEntry(in_nLevel, in_nX, in_nY);
	}

	bool IsPageTableDirty() const
	{
		return bTableDirty;
	}
	void ClearPageTableDirty()
	{
		bTableDirty = false;
	}
	const Vector<uint8_t> &GetPageTableLevel(uint32_t in_nLevel) const
	{
		return arrTableLevels[in_nLevel];
	}

	Stats GetStats() const;
};
