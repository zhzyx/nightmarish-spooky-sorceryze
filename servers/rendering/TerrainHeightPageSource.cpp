/**************************************************************************/
/*  TerrainHeightPageSource.cpp                                          */
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

#include "TerrainHeightPageSource.h"

#include "core/math/math_funcs.h"

Vector<uint8_t> TerrainHeightPageSource::Produce(uint32_t nLevel, uint32_t in_nX, uint32_t in_nY) const
{
	const int nDim = nVirtualSize >> nLevel;
	ERR_FAIL_COND_V(nDim < nTile || nTile <= 0 || nRegionSize <= 0 || nExtent <= 0 || arrRegions.size() != arrLookup.size(), {});
	const int nStride = nTile + 2 * nBorder;
	Vector<uint8_t> arrBytes;
	ERR_FAIL_COND_V(arrBytes.resize(int64_t(nStride) * nStride * sizeof(float)) != OK, {});
	float *pOut = reinterpret_cast<float *>(arrBytes.ptrw());
	// Terrain3D region sizes are powers of two. Use floor division explicitly for negative world cells.
	auto fnSampleHeight = [this](int nX, int nZ) -> float
	{
		const int nRx = nX >= 0 ? nX / nRegionSize : -1 - ((-1 - nX) / nRegionSize);
		const int nRz = nZ >= 0 ? nZ / nRegionSize : -1 - ((-1 - nZ) / nRegionSize);
		const int nMx = nRx + nMapWidth / 2;
		const int nMz = nRz + nMapWidth / 2;
		if (uint32_t(nMx) >= uint32_t(nMapWidth) || uint32_t(nMz) >= uint32_t(nMapWidth))
		{
			return 0.f;
		}
		const int nIndex = nMz * nMapWidth + nMx;
		const Vector<uint8_t> &arrRegion = arrRegions[nIndex];
		if (arrLookup[nIndex] <= 0 || arrRegion.is_empty())
		{
			return 0.f;
		}
		const float fH = reinterpret_cast<const float *>(arrRegion.ptr())[(nZ - nRz * nRegionSize) * nRegionSize + (nX - nRx * nRegionSize)];
		return Math::is_finite(fH) ? fH : 0.f;
	};
	for (int nJ = 0; nJ < nStride; ++nJ)
	{
		const int nY = CLAMP(int(in_nY) * nTile + nJ - nBorder, 0, nDim - 1);
		const double dV = MIN(double(nY) * nExtent / nDim, double(nExtent - 1));
		const int nZ0 = vOrigin.y + int(dV);
		const int nZ1 = MIN(nZ0 + 1, vOrigin.y + nExtent - 1);
		const float fFz = float(dV - int(dV));
		for (int nI = 0; nI < nStride; ++nI)
		{
			const int nX = CLAMP(int(in_nX) * nTile + nI - nBorder, 0, nDim - 1);
			const double dU = MIN(double(nX) * nExtent / nDim, double(nExtent - 1));
			const int nX0 = vOrigin.x + int(dU);
			const float fFx = float(dU - int(dU));
			float fH = fnSampleHeight(nX0, nZ0);
			if (fFx != 0.f || fFz != 0.f)
			{
				const int nX1 = MIN(nX0 + 1, vOrigin.x + nExtent - 1);
				fH = Math::lerp(Math::lerp(fH, fnSampleHeight(nX1, nZ0), fFx), Math::lerp(fnSampleHeight(nX0, nZ1), fnSampleHeight(nX1, nZ1), fFx), fFz);
			}
			*pOut++ = fH;
		}
	}
	return arrBytes;
}
