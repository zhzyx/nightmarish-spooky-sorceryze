/**************************************************************************/
/*  RuntimeVirtualTexturePageManager.cpp                                 */
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

#include "RuntimeVirtualTexturePageManager.h"

#pragma region Engine ZXB
// [ZXB] Implementation of the RVT page table / physical pool bookkeeping.
#pragma endregion

#include "core/math/math_funcs.h"
#include "core/math/vector2i.h"
#include "core/templates/sort_array.h"

#include <utility>

void RVTPageManager::Configure(const Config &in_stConfig)
{
	stConfig = in_stConfig;
	stConfig.nLog2Pages = CLAMP(stConfig.nLog2Pages, 0u, 12u);
	stConfig.nPoolPagesX = CLAMP(stConfig.nPoolPagesX, 1u, 255u);
	stConfig.nPoolPagesY = CLAMP(stConfig.nPoolPagesY, 1u, 255u);
	nMaxLevel = stConfig.nLog2Pages;
	stConfig.nResidentLevels = CLAMP(stConfig.nResidentLevels, 1u, nMaxLevel + 1);
	Reset();
}

void RVTPageManager::Reset()
{
	AdvanceMappingRevision();
	mapPages.clear();
	setBlocked.clear();
	mapRequests.clear();
	const uint32_t nCapacity = GetPoolCapacity();
	arrSlotOwner.resize(nCapacity);
	arrFreeSlots.clear();
	for (uint32_t nI = 0; nI < nCapacity; nI++)
	{
		arrSlotOwner[nI] = INVALID_ID;
		arrFreeSlots.push_back(nCapacity - 1 - nI); // Pop from the back yields slot 0 first.
	}
	arrTableLevels.resize(nMaxLevel + 1);
	for (uint32_t nL = 0; nL <= nMaxLevel; nL++)
	{
		const uint32_t nSize = LevelSize(nL);
		arrTableLevels[nL].resize(nSize * nSize * 4);
		arrTableLevels[nL].fill(0);
	}
	bTableDirty = true;
	nFrame = 1;
	stStats = Stats();
	stStats.nPoolPages = nCapacity;
}

bool RVTPageManager::MoveWindow(const Transform3D &stOldVolume, const Transform3D &stNewVolume)
{
	// A page's physical samples can be reused only if its entire footprint still has
	// the same origin and axes in world space, including the page's border.
	const int32_t nSide = int32_t(LevelSize(0));
	Vector2i vPageShift;
	const Vector3 vAxisX = stOldVolume.basis.get_column(0);
	const Vector3 vAxisZ = stOldVolume.basis.get_column(2);
	const Vector3 vUp = stOldVolume.basis.get_column(1).normalized();
	const bool bSameAxes = vAxisX == stNewVolume.basis.get_column(0) && vAxisZ == stNewVolume.basis.get_column(2) &&
						   vUp.is_equal_approx(stNewVolume.basis.get_column(1).normalized());
	const Basis stAxes(vAxisX.normalized(), vUp, vAxisZ.normalized());
	bool bAligned = false;
	if (bSameAxes && stAxes.is_orthogonal() &&
		!Math::is_zero_approx(stOldVolume.basis.determinant()))
	{
		const Basis stOrientation = stOldVolume.basis.orthonormalized();
		const Vector3 vDelta = stOrientation.transposed().xform(stNewVolume.origin - stOldVolume.origin);
		const Vector2 vOffset(vDelta.x * nSide / vAxisX.length(), vDelta.z * nSide / vAxisZ.length());
		if (vOffset.is_finite() &&
			Math::abs(vOffset.x) < nSide && Math::abs(vOffset.y) < nSide)
		{
			const Vector2 vRounded = vOffset.round();
			// Absolute page-space tolerance: a large world coordinate must not make
			// a fraction of a texel look like an integer translation.
			bAligned = Math::abs(vOffset.x - vRounded.x) <= 0.0001 && Math::abs(vOffset.y - vRounded.y) <= 0.0001;
			vPageShift = Vector2i(vRounded);
		}
	}

	HashMap<uint32_t, Page> mapRetained;
	stStats.nRetainedOnMove = 0;
	stStats.nDiscardedOnMove = 0;
	for (const KeyValue<uint32_t, Page> &stEntry : mapPages)
	{
		const PageKey stOldKey = FromId(stEntry.key);
		const int32_t nSpan = 1 << stOldKey.nLevel;
		const int32_t nLevelSide = nSide / nSpan;
		if (bAligned && stEntry.value.eState == STATE_RESIDENT &&
			vPageShift.x % nSpan == 0 && vPageShift.y % nSpan == 0)
		{
			const int32_t nX = int32_t(stOldKey.nX) - vPageShift.x / nSpan;
			const int32_t nY = int32_t(stOldKey.nY) - vPageShift.y / nSpan;
			if (nX >= 0 && nX < nLevelSide && nY >= 0 && nY < nLevelSide)
			{
				const uint32_t nNewId = MakeId(stOldKey.nLevel, uint32_t(nX), uint32_t(nY));
				Page stPage = stEntry.value;
				if (stPage.rectEditedArea.has_area())
				{
					stPage.rectEditedArea.position -= Vector2(vPageShift) / nSide;
				}
				mapRetained.insert(nNewId, stPage);
				arrSlotOwner[stPage.nSlot] = nNewId;
				stStats.nRetainedOnMove++;
				continue;
			}
		}
		arrSlotOwner[stEntry.value.nSlot] = INVALID_ID;
		arrFreeSlots.push_back(stEntry.value.nSlot);
		stStats.nDiscardedOnMove++;
	}
	mapPages = std::move(mapRetained);
	mapRequests.clear();
	setBlocked.clear();
	arrHeightChanges.clear();
	for (Vector<uint8_t> &arrLevel : arrTableLevels)
	{
		arrLevel.fill(0);
	}
	for (const KeyValue<uint32_t, Page> &stEntry : mapPages)
	{
		MapPage(FromId(stEntry.key), stEntry.value.nSlot);
	}
	bTableDirty = true;
	AdvanceMappingRevision();
	return bAligned;
}

void RVTPageManager::SetEntry(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, const PageTableEntry &stEntry)
{
	const uint32_t nSize = LevelSize(in_nLevel);
	uint8_t *pW = arrTableLevels[in_nLevel].ptrw() + (in_nY * nSize + in_nX) * 4;
	pW[0] = stEntry.nPoolX;
	pW[1] = stEntry.nPoolY;
	pW[2] = stEntry.nLevel;
	pW[3] = stEntry.nValid;
	bTableDirty = true;
}

RVTPageManager::PageTableEntry RVTPageManager::GetEntry(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const
{
	PageTableEntry stE;
	ERR_FAIL_COND_V(in_nLevel > nMaxLevel, stE);
	const uint32_t nSize = LevelSize(in_nLevel);
	ERR_FAIL_COND_V(in_nX >= nSize || in_nY >= nSize, stE);
	const uint8_t *pR = arrTableLevels[in_nLevel].ptr() + (in_nY * nSize + in_nX) * 4;
	stE.nPoolX = pR[0];
	stE.nPoolY = pR[1];
	stE.nLevel = pR[2];
	stE.nValid = pR[3];
	return stE;
}

RVTPageManager::PageTableEntry RVTPageManager::Resolve(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const
{
	for (uint32_t nL = in_nLevel; nL <= nMaxLevel; nL++)
	{
		const uint32_t nShift = nL - in_nLevel;
		const Page *pPage = mapPages.getptr(MakeId(nL, in_nX >> nShift, in_nY >> nShift));
		if (pPage && pPage->eState == STATE_RESIDENT)
		{
			PageTableEntry stE;
			stE.nPoolX = pPage->nSlot % stConfig.nPoolPagesX;
			stE.nPoolY = pPage->nSlot / stConfig.nPoolPagesX;
			stE.nLevel = nL;
			stE.nValid = pPage->nFade;
			return stE;
		}
	}
	return PageTableEntry();
}

void RVTPageManager::MapPage(const PageKey &in_stKey, uint32_t in_nSlot)
{
	PageTableEntry stE;
	stE.nPoolX = in_nSlot % stConfig.nPoolPagesX;
	stE.nPoolY = in_nSlot / stConfig.nPoolPagesX;
	stE.nLevel = in_stKey.nLevel;
	stE.nValid = mapPages[MakeId(in_stKey.nLevel, in_stKey.nX, in_stKey.nY)].nFade;
	SetEntry(in_stKey.nLevel, in_stKey.nX, in_stKey.nY, stE);

	// Descendants that currently resolve to something coarser (or nothing) now use this page.
	for (int nL = (int)in_stKey.nLevel - 1; nL >= 0; nL--)
	{
		const uint32_t nShift = in_stKey.nLevel - nL;
		const uint32_t nX0 = in_stKey.nX << nShift;
		const uint32_t nY0 = in_stKey.nY << nShift;
		const uint32_t nCount = 1u << nShift;
		for (uint32_t nY = nY0; nY < nY0 + nCount; nY++)
		{
			for (uint32_t nX = nX0; nX < nX0 + nCount; nX++)
			{
				const PageTableEntry stCur = GetEntry(nL, nX, nY);
				if (!stCur.nValid || stCur.nLevel >= in_stKey.nLevel)
				{
					SetEntry(nL, nX, nY, stE);
				}
			}
		}
	}
}

void RVTPageManager::UnmapPage(const PageKey &in_stKey, uint32_t in_nSlot)
{
	// The page must already be removed from `pages` so that resolution skips it.
	for (int nL = (int)in_stKey.nLevel; nL >= 0; nL--)
	{
		const uint32_t nShift = in_stKey.nLevel - nL;
		const uint32_t nX0 = in_stKey.nX << nShift;
		const uint32_t nY0 = in_stKey.nY << nShift;
		const uint32_t nCount = 1u << nShift;
		for (uint32_t nY = nY0; nY < nY0 + nCount; nY++)
		{
			for (uint32_t nX = nX0; nX < nX0 + nCount; nX++)
			{
				const PageTableEntry stCur = GetEntry(nL, nX, nY);
				if (stCur.nValid && stCur.nLevel == in_stKey.nLevel)
				{
					SetEntry(nL, nX, nY, Resolve(nL, nX, nY));
				}
			}
		}
	}
}

Rect2 RVTPageManager::PageRect(const PageKey &in_stKey) const
{
	const float fSpan = 1.0f / LevelSize(in_stKey.nLevel);
	return Rect2(Vector2(in_stKey.nX * fSpan, in_stKey.nY * fSpan), Vector2(fSpan, fSpan));
}

void RVTPageManager::ReleasePage(uint32_t in_nId)
{
	Page *pPage = mapPages.getptr(in_nId);
	ERR_FAIL_NULL(pPage);
	const uint32_t nSlot = pPage->nSlot;
	const bool bWasResident = pPage->eState == STATE_RESIDENT;
	mapPages.erase(in_nId);
	arrSlotOwner[nSlot] = INVALID_ID;
	arrFreeSlots.push_back(nSlot);
	if (bWasResident)
	{
		UnmapPage(FromId(in_nId), nSlot);
		if (stConfig.bFadeIn)
		{
			arrHeightChanges.push_back(PageRect(FromId(in_nId)));
		}
	}
}

bool RVTPageManager::AllocateSlot(uint32_t &out_nSlot)
{
	if (!arrFreeSlots.is_empty())
	{
		out_nSlot = arrFreeSlots[arrFreeSlots.size() - 1];
		arrFreeSlots.resize(arrFreeSlots.size() - 1);
		return true;
	}

	// Evict the least recently used page that was not requested this frame (finest level first on ties).
	uint32_t nVictim = INVALID_ID;
	uint64_t nVictimUsed = UINT64_MAX;
	uint32_t nVictimLevel = 0;
	for (const KeyValue<uint32_t, Page> &stKv : mapPages)
	{
		if (stKv.value.eState != STATE_RESIDENT || stKv.value.nLastUsed >= nFrame)
		{
			continue;
		}
		const uint32_t nLevel = stKv.key >> 28;
		if (stKv.value.nLastUsed < nVictimUsed || (stKv.value.nLastUsed == nVictimUsed && nLevel < nVictimLevel))
		{
			nVictim = stKv.key;
			nVictimUsed = stKv.value.nLastUsed;
			nVictimLevel = nLevel;
		}
	}
	if (nVictim == INVALID_ID)
	{
		return false;
	}
	ReleasePage(nVictim);
	stStats.nEvictedTotal++;
	out_nSlot = arrFreeSlots[arrFreeSlots.size() - 1];
	arrFreeSlots.resize(arrFreeSlots.size() - 1);
	return true;
}

void RVTPageManager::BeginFrame()
{
	nFrame++;
	arrHeightChanges.clear();
	mapRequests.clear();
	stStats.nRenderedThisFrame = 0;
	if (stConfig.bFadeIn || stConfig.bPrioritizeCoverage)
	{
		for (KeyValue<uint32_t, Page> &stKv : mapPages)
		{
			Page &stPage = stKv.value;
			const int nMature = stConfig.bPrioritizeCoverage ? (254 | (stPage.nFade & 1)) : 255;
			if (stPage.eState == STATE_RESIDENT && stPage.nFade < nMature)
			{
				stPage.nFade = MIN(int(stPage.nFade) + 32, nMature);
				MapPage(FromId(stKv.key), stPage.nSlot);
				if (stConfig.bFadeIn && stPage.nFade == 255)
				{
					arrHeightChanges.push_back(PageRect(FromId(stKv.key)));
				}
			}
		}
	}
}

void RVTPageManager::RequestPage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, float in_fPriority)
{
	ERR_FAIL_COND(in_nLevel > nMaxLevel);
	const uint32_t nSize = LevelSize(in_nLevel);
	ERR_FAIL_COND(in_nX >= nSize || in_nY >= nSize);
	const uint32_t nId = MakeId(in_nLevel, in_nX, in_nY);
	if (setBlocked.has(nId))
	{
		return; // Known broken page: fall back to an ancestor instead of retrying forever.
	}
	float *pExisting = mapRequests.getptr(nId);
	if (pExisting)
	{
		*pExisting = MIN(*pExisting, in_fPriority);
	}
	else
	{
		mapRequests.insert(nId, in_fPriority);
	}
}

float RVTPageManager::LodAtDistance(const View &stView, float fDistance) const
{
	if (stView.stHeightLod.fLod0Distance > 0.0f)
	{
		const float fD = fDistance / stView.stHeightLod.fLod0Distance;
		const float fBand = fD < 1.0f ? 0.0f : Math::floor(Math::log2(fD)) + 1.0f;
		const float fGeom = MIN(float(stView.stHeightLod.nMaxLod), fBand + Math::smoothstep(0.86f, 1.0f, fD / Math::pow(2.0f, fBand)));
		return CLAMP(fGeom + Math::log2(stView.stHeightLod.fVertexSpacing / stView.fTexelSizeLevel0), 0.0f, float(nMaxLevel));
	}
	const float fPixel = stView.fPixelOrtho > 0.0f ? stView.fPixelOrtho : fDistance * stView.fPixelPerDistance;
	const float fLod = Math::log2(MAX(fPixel, 1e-9f) / MAX(stView.fTexelSizeLevel0, 1e-9f)) + stView.fLodBias;
	return CLAMP(fLod, 0.0f, (float)nMaxLevel);
}

void RVTPageManager::Visit(const View &stView, uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY)
{
	const float fN = (float)LevelSize(in_nLevel);
	const float fX0 = ((float)in_nX / fN - 0.5f) * stView.vSize.x;
	const float fX1 = ((float)(in_nX + 1) / fN - 0.5f) * stView.vSize.x;
	const float fZ0 = ((float)in_nY / fN - 0.5f) * stView.vSize.z;
	const float fZ1 = ((float)(in_nY + 1) / fN - 0.5f) * stView.vSize.z;
	const AABB aabbBox(Vector3(fX0, -stView.vSize.y * 0.5f, fZ0), Vector3(fX1 - fX0, stView.vSize.y, fZ1 - fZ0));

	if (stView.stHeightLod.fLod0Distance <= 0.0f && !stView.arrFrustum.is_empty())
	{
		// Inflate by half a page so small camera motion does not pop pages in.
		const AABB aabbInflated = aabbBox.grow(MAX(fX1 - fX0, fZ1 - fZ0) * 0.5f);
		for (const Plane &planePlane : stView.arrFrustum)
		{
			if (planePlane.distance_to(aabbInflated.get_support(-planePlane.normal)) > 0.0f)
			{
				return;
			}
		}
	}

	const Vector3 vClosest(CLAMP(stView.vViewer.x, aabbBox.position.x, aabbBox.position.x + aabbBox.size.x),
						   CLAMP(stView.vViewer.y, aabbBox.position.y, aabbBox.position.y + aabbBox.size.y),
						   CLAMP(stView.vViewer.z, aabbBox.position.z, aabbBox.position.z + aabbBox.size.z));
	const bool bHeightGrid = stView.stHeightLod.fLod0Distance > 0.0f;
	const Vector2 vEye(stView.vViewer.x, stView.vViewer.z);
	const float fDmin = bHeightGrid ? vEye.distance_to(Vector2(vClosest.x, vClosest.z)) : vClosest.distance_to(stView.vViewer);
	if (bHeightGrid && fDmin > stView.stHeightLod.fMaxDistance + MAX(fX1 - fX0, fZ1 - fZ0))
	{
		return;
	}
	float fDmax = 0.0f;
	for (int nI = 0; nI < 8; nI++)
	{
		const Vector3 vP = aabbBox.get_endpoint(nI);
		fDmax = MAX(fDmax, bHeightGrid ? vEye.distance_to(Vector2(vP.x, vP.z)) : vP.distance_to(stView.vViewer));
	}

	const int nLfMin = (int)Math::floor(LodAtDistance(stView, fDmin));
	const int nLfMax = (int)Math::floor(LodAtDistance(stView, fDmax));
	const int nLevel = (int)in_nLevel;

	if (nLfMin <= nLevel && nLevel <= nLfMax + 2)
	{
		RequestPage(in_nLevel, in_nX, in_nY, fDmin);
	}

	if (nLevel > 0 && nLfMin < nLevel)
	{
		for (uint32_t nCy = 0; nCy < 2; nCy++)
		{
			for (uint32_t nCx = 0; nCx < 2; nCx++)
			{
				Visit(stView, in_nLevel - 1, in_nX * 2 + nCx, in_nY * 2 + nCy);
			}
		}
	}
}

void RVTPageManager::RequestMovingFootprint(const PageKey &stKey, const Vector2 &vCurrentOffsetUV, const Vector2 &vVelocityUV, float fPriority)
{
	ERR_FAIL_COND(stKey.nLevel > nMaxLevel);
	const int32_t nSide = int32_t(LevelSize(stKey.nLevel));
	const Vector2 vCurrent = Vector2(stKey.nX, stKey.nY) + vCurrentOffsetUV * nSide;
	const Vector2 vStep = vVelocityUV * nSide;
	// A live tile takes eight render frames to reach full weight. Sweep that interval
	// without giving a page extra votes when neighboring samples or time steps overlap.
	const int32_t nHorizon = vStep.is_zero_approx() ? 0 : 8;
	for (int32_t nFramesAhead = 0; nFramesAhead <= nHorizon; ++nFramesAhead)
	{
		const Vector2 vPage = vCurrent + vStep * nFramesAhead;
		if (!vPage.is_finite() || vPage.x <= -1 || vPage.y <= -1 || vPage.x >= nSide || vPage.y >= nSide)
		{
			continue;
		}
		const Vector2 vFloor = vPage.floor();
		const Vector2 vFraction = vPage - vFloor;
		for (int32_t nY = 0; nY <= 1; ++nY)
		{
			for (int32_t nX = 0; nX <= 1; ++nX)
			{
				const int32_t nPageX = int32_t(vFloor.x) + nX;
				const int32_t nPageY = int32_t(vFloor.y) + nY;
				const real_t fArea = (nX ? vFraction.x : 1 - vFraction.x) * (nY ? vFraction.y : 1 - vFraction.y);
				if (fArea <= 0.01 || nPageX < 0 || nPageY < 0 || nPageX >= nSide || nPageY >= nSide)
				{
					continue;
				}
				const float fScore = float(fPriority * (1.0 + 0.075 * nFramesAhead) / fArea);
				RequestPage(stKey.nLevel, nPageX, nPageY, fScore);
				if (stKey.nLevel < nMaxLevel)
				{
					RequestPage(stKey.nLevel + 1, nPageX >> 1, nPageY >> 1, fScore);
				}
			}
		}
	}
}

void RVTPageManager::RequestResidentLevels()
{
	const uint32_t nFirstResident = nMaxLevel + 1 - stConfig.nResidentLevels;
	for (uint32_t nL = nFirstResident; nL <= nMaxLevel; nL++)
	{
		const uint32_t nSize = LevelSize(nL);
		for (uint32_t nY = 0; nY < nSize; nY++)
		{
			for (uint32_t nX = 0; nX < nSize; nX++)
			{
				RequestPage(nL, nX, nY, 0.0f);
			}
		}
	}
}

void RVTPageManager::RequestView(const View &stView)
{
	RequestResidentLevels();
	Visit(stView, nMaxLevel, 0, 0);
}

void RVTPageManager::TakePending(uint32_t nMax, LocalVector<PageRender> &out_arrPages)
{
	out_arrPages.clear();

	struct Order
	{
		bool operator()(const Request &stA, const Request &stB) const
		{
			const uint32_t nLa = stA.nId >> 28;
			const uint32_t nLb = stB.nId >> 28;
			if (nLa != nLb)
			{
				return nLa > nLb; // Coarsest first.
			}
			if (stA.fPriority != stB.fPriority)
			{
				return stA.fPriority < stB.fPriority;
			}
			return stA.nId < stB.nId;
		}
	};
	LocalVector<Request> arrWanted;
	arrWanted.reserve(mapRequests.size());
	for (const KeyValue<uint32_t, float> &stKv : mapRequests)
	{
		arrWanted.push_back({ stKv.key, stKv.value });
	}
	struct CoverageOrder
	{
		bool operator()(const Request &stA, const Request &stB) const
		{
			if (stA.fPriority != stB.fPriority)
			{
				return stA.fPriority < stB.fPriority;
			}
			return Order()(stA, stB);
		}
	};
	if (stConfig.bPrioritizeCoverage)
	{
		arrWanted.sort_custom<CoverageOrder>();
		arrWanted.resize(MIN(arrWanted.size(), GetPoolCapacity()));
	}
	else if (stConfig.bFadeIn && arrWanted.size() > GetPoolCapacity())
	{
		arrWanted.sort_custom<Order>();
		arrWanted.resize(GetPoolCapacity());
	}
	LocalVector<Request> arrSorted;
	for (const Request &stRequest : arrWanted)
	{
		Page *pPage = mapPages.getptr(stRequest.nId);
		if (pPage)
		{
			pPage->nLastUsed = nFrame;
		}
		if (!pPage || (pPage->eState == STATE_RESIDENT && pPage->bDirty))
		{
			arrSorted.push_back(stRequest);
		}
	}
	if (!stConfig.bPrioritizeCoverage)
	{
		arrSorted.sort_custom<Order>();
	}
	if (arrSorted.size() > GetPoolCapacity())
	{
		arrSorted.resize(GetPoolCapacity());
	}
	stStats.nRequestedPages = mapRequests.size();

	for (const Request &stR : arrSorted)
	{
		if (out_arrPages.size() >= nMax)
		{
			break;
		}
		Page *pPage = mapPages.getptr(stR.nId);
		PageRender stOut;
		stOut.stKey = FromId(stR.nId);
		if (pPage)
		{
			if (pPage->eState != STATE_RESIDENT || !pPage->bDirty)
			{
				continue;
			}
			stOut.nSlot = pPage->nSlot;
		}
		else
		{
			uint32_t nSlot;
			if (!AllocateSlot(nSlot))
			{
				break;
			}
			Page stNp;
			stNp.nSlot = nSlot;
			stNp.eState = STATE_RENDERING;
			stNp.nLastUsed = nFrame;
			mapPages.insert(stR.nId, stNp);
			arrSlotOwner[nSlot] = stR.nId;
			stOut.nSlot = nSlot;
		}
		stOut.nPoolX = stOut.nSlot % stConfig.nPoolPagesX;
		stOut.nPoolY = stOut.nSlot / stConfig.nPoolPagesX;
		out_arrPages.push_back(stOut);
	}
}

void RVTPageManager::DiscardPage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY)
{
	const uint32_t nId = MakeId(in_nLevel, in_nX, in_nY);
	Page *pPage = mapPages.getptr(nId);
	if (!pPage || pPage->eState == STATE_RESIDENT)
	{
		return; // Resident pages are only removed through eviction.
	}
	const uint32_t nSlot = pPage->nSlot;
	mapPages.erase(nId);
	arrSlotOwner[nSlot] = INVALID_ID;
	arrFreeSlots.push_back(nSlot);
}

void RVTPageManager::InvalidatePage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY)
{
	Page *pPage = mapPages.getptr(MakeId(in_nLevel, in_nX, in_nY));
	if (pPage && pPage->eState == STATE_RESIDENT)
	{
		pPage->bDirty = true;
		if (stConfig.bFadeIn)
		{
			pPage->rectEditedArea = PageRect({ in_nLevel, in_nX, in_nY });
		}
	}
}

RVTPageManager::PageStatus RVTPageManager::GetPageStatus(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const
{
	PageStatus stStatus;
	const uint32_t nId = MakeId(in_nLevel, in_nX, in_nY);
	stStatus.bBlocked = setBlocked.has(nId);
	const Page *pPage = mapPages.getptr(nId);
	if (!pPage)
	{
		return stStatus;
	}
	stStatus.bExists = true;
	stStatus.nContentSerial = pPage->nContentSerial;
	stStatus.bResident = pPage->eState == STATE_RESIDENT;
	stStatus.bDirty = pPage->bDirty;
	stStatus.nPoolX = pPage->nSlot % stConfig.nPoolPagesX;
	stStatus.nPoolY = pPage->nSlot / stConfig.nPoolPagesX;
	return stStatus;
}

void RVTPageManager::BlockPage(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY)
{
	DiscardPage(in_nLevel, in_nX, in_nY);
	setBlocked.insert(MakeId(in_nLevel, in_nX, in_nY));
	bTableDirty = true;
}

void RVTPageManager::MarkRendered(const PageKey &in_stKey, bool bFromDisk)
{
	const uint32_t nId = MakeId(in_stKey.nLevel, in_stKey.nX, in_stKey.nY);
	Page *pPage = mapPages.getptr(nId);
	ERR_FAIL_NULL(pPage);
	const bool bNewlyResident = pPage->eState != STATE_RESIDENT;
	pPage->eState = STATE_RESIDENT;
	pPage->bDirty = false;
	pPage->nLastUsed = nFrame;
	stStats.nRenderedThisFrame++;
	if (stConfig.bFadeIn && !bNewlyResident && pPage->rectEditedArea.has_area())
	{
		arrHeightChanges.push_back(pPage->rectEditedArea);
	}
	pPage->rectEditedArea = Rect2();
	pPage->nContentSerial = ++stStats.nRenderedTotal;
	const uint8_t nPreviousAlpha = pPage->nFade;
	if (stConfig.bPrioritizeCoverage)
	{
		// Bits 7..1 fade from direct shading; bit 0 distinguishes live and disk pages.
		const uint8_t nOrigin = bFromDisk ? 0 : 1;
		if (in_stKey.nLevel == nMaxLevel)
		{
			pPage->nFade = 254 | nOrigin;
		}
		else if (bNewlyResident || (nPreviousAlpha & 1) != nOrigin)
		{
			pPage->nFade = 2 | nOrigin;
		}
	}
	else if (bNewlyResident && stConfig.bFadeIn && in_stKey.nLevel < nMaxLevel)
	{
		pPage->nFade = 1;
	}
	if (bNewlyResident || nPreviousAlpha != pPage->nFade)
	{
		MapPage(in_stKey, pPage->nSlot);
	}
}

void RVTPageManager::InvalidateRect(const Rect2 &rectUvRect)
{
	InvalidateRect(rectUvRect, 0.0f);
}

void RVTPageManager::InvalidateRect(const Rect2 &rectUvRect, float fBorderInTiles, const HashSet<uint32_t> *pExcluded)
{
	for (KeyValue<uint32_t, Page> &stKv : mapPages)
	{
		const PageKey stKey = FromId(stKv.key);
		const float fN = (float)LevelSize(stKey.nLevel);
		const Rect2 rectPageRect(Vector2(stKey.nX / fN, stKey.nY / fN), Vector2(1.0f / fN, 1.0f / fN));
		if ((!pExcluded || !pExcluded->has(stKv.key)) && rectPageRect.grow(fBorderInTiles / fN).intersects(rectUvRect, true))
		{
			if (stConfig.bFadeIn)
			{
				const Rect2 rectEdit = rectUvRect.grow(fBorderInTiles / fN).intersection(rectPageRect);
				stKv.value.rectEditedArea = stKv.value.rectEditedArea.has_area() ? stKv.value.rectEditedArea.merge(rectEdit) : rectEdit;
			}
			stKv.value.bDirty = true;
		}
	}
}

void RVTPageManager::InvalidateAll()
{
	for (KeyValue<uint32_t, Page> &stKv : mapPages)
	{
		stKv.value.bDirty = true;
		if (stConfig.bFadeIn)
		{
			stKv.value.rectEditedArea = PageRect(FromId(stKv.key));
		}
	}
}

bool RVTPageManager::IsResident(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const
{
	const Page *pPage = mapPages.getptr(MakeId(in_nLevel, in_nX, in_nY));
	return pPage && pPage->eState == STATE_RESIDENT;
}

bool RVTPageManager::GetSlot(const PageKey &in_stKey, uint32_t &out_nPoolX, uint32_t &out_nPoolY) const
{
	const Page *pPage = mapPages.getptr(MakeId(in_stKey.nLevel, in_stKey.nX, in_stKey.nY));
	if (!pPage)
	{
		return false;
	}
	out_nPoolX = pPage->nSlot % stConfig.nPoolPagesX;
	out_nPoolY = pPage->nSlot / stConfig.nPoolPagesX;
	return true;
}

LocalVector<int32_t> RVTPageManager::GetResidentPagesByLevel() const
{
	LocalVector<int32_t> arrCounts;
	arrCounts.resize(nMaxLevel + 1);
	for (uint32_t nI = 0; nI <= nMaxLevel; nI++)
	{
		arrCounts[nI] = 0;
	}
	for (const KeyValue<uint32_t, Page> &stKv : mapPages)
	{
		if (stKv.value.eState == STATE_RESIDENT)
		{
			arrCounts[stKv.key >> 28]++;
		}
	}
	return arrCounts;
}

RVTPageManager::Stats RVTPageManager::GetStats() const
{
	Stats stS = stStats;
	stS.nResidentPages = 0;
	for (const KeyValue<uint32_t, Page> &stKv : mapPages)
	{
		if (stKv.value.eState == STATE_RESIDENT)
		{
			stS.nResidentPages++;
		}
	}
	return stS;
}
