/**************************************************************************/
/*  StreamingVirtualTextureFile.cpp                                      */
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

#include "StreamingVirtualTextureFile.h"

#pragma region Engine ZXB
// [ZXB] Streaming Virtual Texture page file reader and baker.
#pragma endregion

#include "core/io/compression.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/os/os.h"
#include "core/templates/hashfuncs.h"

uint32_t StreamingVirtualTextureFile::TilesPerSide(uint32_t in_nLevel) const
{
	if (in_nLevel >= stHeader.nLevelCount)
	{
		return 0;
	}
	return 1u << (stHeader.nLog2TileCount - in_nLevel);
}

static uint32_t StoredPageCount(uint32_t nLog2, uint32_t nFirst)
{
	const uint32_t nSide = 1u << (nLog2 - nFirst);
	return (4u * nSide * nSide - 1u) / 3u;
}

static uint32_t GetFormatTileBytes(const StreamingVirtualTextureFile::Header &in_stHeader)
{
	const uint32_t nSide = in_stHeader.nTileSize + 2 * in_stHeader.nTileBorder;
	switch (in_stHeader.nFormat)
	{
	case StreamingVirtualTextureFile::FORMAT_RGBA8:
	case StreamingVirtualTextureFile::FORMAT_R32F:
		return nSide * nSide * 4;
	case StreamingVirtualTextureFile::FORMAT_BC1:
		return (nSide / 4) * (nSide / 4) * 8;
	case StreamingVirtualTextureFile::FORMAT_BC7:
		return (nSide / 4) * (nSide / 4) * 16;
	case StreamingVirtualTextureFile::FORMAT_TERRAIN_PBR:
		return nSide * nSide * 12;
	default:
		return 0;
	}
}

static bool ValidPbrLayout(uint32_t nLog2, uint32_t in_nTileSize, uint32_t nBorder, uint32_t nFirst, const Rect2 &rectRect)
{
	return nLog2 <= 10 && nFirst <= nLog2 && in_nTileSize > 0 && in_nTileSize <= 2048 &&
		   nBorder <= 16 && rectRect.is_finite() && rectRect.get_end().is_finite() && rectRect.has_area();
}

uint32_t StreamingVirtualTextureFile::TileBytes() const
{
	return GetFormatTileBytes(stHeader);
}

Error StreamingVirtualTextureFile::Open(const String &in_strPath)
{
	strPath = String();
	stHeader = Header();
	arrLevelOffset.clear();
	arrTiles.clear();
	Ref<FileAccess> refF = FileAccess::open(in_strPath, FileAccess::READ);
	if (refF.is_null())
	{
		return ERR_FILE_CANT_OPEN;
	}

	const uint64_t nFileSize = refF->get_length();
	if (nFileSize < 8 || refF->get_32() != MAGIC)
	{
		return ERR_FILE_UNRECOGNIZED;
	}
	Header stH;
	stH.nVersion = refF->get_32();
	const bool bPbr = stH.nVersion == TERRAIN_PBR_VERSION;
	if (!bPbr && stH.nVersion != VERSION)
	{
		return ERR_FILE_UNRECOGNIZED;
	}
	if (nFileSize < uint64_t(bPbr ? TERRAIN_PBR_HEADER_SIZE : HEADER_SIZE))
	{
		return ERR_FILE_CORRUPT;
	}
	stH.nFlags = refF->get_32();
	stH.nFormat = refF->get_32();
	stH.nLog2TileCount = refF->get_32();
	stH.nTileSize = refF->get_32();
	stH.nTileBorder = refF->get_32();
	stH.nLayerCount = refF->get_32();
	stH.nLevelCount = refF->get_32();
	if (stH.nLog2TileCount > 12 || stH.nLevelCount != stH.nLog2TileCount + 1 || stH.nTileSize == 0 || stH.nTileSize > 2048 || stH.nTileBorder > 16)
	{
		return ERR_FILE_CORRUPT;
	}
	if (bPbr)
	{
		stH.nFirstStoredMip = refF->get_32();
		if (refF->get_32() != 0 || refF->get_32() != 0)
		{
			return ERR_FILE_CORRUPT;
		}
		stH.rectWorldRect.position.x = refF->get_double();
		stH.rectWorldRect.position.y = refF->get_double();
		stH.rectWorldRect.size.x = refF->get_double();
		stH.rectWorldRect.size.y = refF->get_double();
		stH.nSourceSignature = refF->get_64();
		if (stH.nFormat != FORMAT_TERRAIN_PBR || stH.nFlags != 0 || stH.nLayerCount != 2 ||
			!ValidPbrLayout(stH.nLog2TileCount, stH.nTileSize, stH.nTileBorder, stH.nFirstStoredMip, stH.rectWorldRect))
		{
			return ERR_FILE_CORRUPT;
		}
	}
	else
	{
		refF->seek(HEADER_SIZE);
		if (stH.nFormat > FORMAT_R32F || stH.nLayerCount == 0 || stH.nLayerCount > 2 ||
			((stH.nFormat == FORMAT_BC1 || stH.nFormat == FORMAT_BC7) && ((stH.nTileSize % 4) != 0 || (stH.nTileBorder % 4) != 0)))
		{
			return ERR_FILE_CORRUPT;
		}
	}
	const uint32_t nPages = StoredPageCount(stH.nLog2TileCount, stH.nFirstStoredMip);
	const uint64_t nDataStart = bPbr ? TERRAIN_PBR_HEADER_SIZE + uint64_t(nPages) * TERRAIN_PBR_ENTRY_SIZE : HEADER_SIZE + uint64_t(nPages) * INDEX_ENTRY_SIZE + uint64_t(stH.nLevelCount) * 8;
	if (nDataStart > nFileSize)
	{
		return ERR_FILE_CORRUPT;
	}
	const uint32_t nNativeSize = GetFormatTileBytes(stH);
	LocalVector<uint32_t> arrOffsets;
	arrOffsets.resize(stH.nLevelCount);
	LocalVector<Tile> arrEntries;
	arrEntries.reserve(nPages);
	uint64_t nCursor = nDataStart;
	for (uint32_t nLevel = stH.nFirstStoredMip; nLevel < stH.nLevelCount; ++nLevel)
	{
		const uint32_t nSide = 1u << (stH.nLog2TileCount - nLevel);
		if (!bPbr && (refF->get_32() != nSide || refF->get_32() != nSide))
		{
			return ERR_FILE_CORRUPT;
		}
		arrOffsets[nLevel] = arrEntries.size();
		for (uint32_t nI = 0; nI < nSide * nSide; ++nI)
		{
			Tile stTile;
			stTile.nOffset = refF->get_64();
			stTile.nSize = refF->get_32();
			if (stTile.nOffset < nDataStart || stTile.nOffset > nFileSize || stTile.nSize > nFileSize - stTile.nOffset)
			{
				return ERR_FILE_CORRUPT;
			}
			if (bPbr)
			{
				stTile.nChecksum = refF->get_32();
				if (stTile.nOffset != nCursor || stTile.nSize == 0 || stTile.nSize > nNativeSize)
				{
					return ERR_FILE_CORRUPT;
				}
				nCursor += stTile.nSize;
			}
			else if (stTile.nSize != nNativeSize && stTile.nSize != 0)
			{
				return ERR_FILE_CORRUPT;
			}
			arrEntries.push_back(stTile);
		}
	}
	if (refF->get_error() != OK || (bPbr && nCursor != nFileSize))
	{
		return ERR_FILE_CORRUPT;
	}
	stHeader = stH;
	arrLevelOffset = std::move(arrOffsets);
	arrTiles = std::move(arrEntries);
	strPath = in_strPath;
	return OK;
}

const StreamingVirtualTextureFile::Tile *StreamingVirtualTextureFile::GetTile(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const
{
	if (!IsOpen() || in_nLevel < stHeader.nFirstStoredMip || in_nLevel >= stHeader.nLevelCount)
	{
		return nullptr;
	}
	const uint32_t nSide = TilesPerSide(in_nLevel);
	if (in_nX >= nSide || in_nY >= nSide)
	{
		return nullptr;
	}
	const uint32_t nIndex = arrLevelOffset[in_nLevel] + in_nY * nSide + in_nX;
	if (nIndex >= arrTiles.size())
	{
		return nullptr;
	}
	return &arrTiles[nIndex];
}

Error StreamingVirtualTextureFile::ReadTile(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, Vector<uint8_t> &out_arrData, FileAccess *in_pReader) const
{
	out_arrData.clear();
	const Tile *pTile = GetTile(in_nLevel, in_nX, in_nY);
	if (!pTile || pTile->nSize == 0)
	{
		return ERR_INVALID_PARAMETER;
	}

	Ref<FileAccess> refOwned;
	FileAccess *pReader = in_pReader;
	if (!pReader)
	{
		refOwned = FileAccess::open(strPath, FileAccess::READ);
		if (refOwned.is_null())
		{
			return ERR_FILE_CANT_OPEN;
		}
		pReader = refOwned.ptr();
	}

	pReader->seek(pTile->nOffset);
	Vector<uint8_t> arrStored;
	if (arrStored.resize(pTile->nSize) != OK)
	{
		return ERR_OUT_OF_MEMORY;
	}
	if (pReader->get_buffer(arrStored.ptrw(), pTile->nSize) != pTile->nSize)
	{
		return ERR_FILE_CORRUPT;
	}
	if (stHeader.nFormat == FORMAT_TERRAIN_PBR)
	{
		const uint32_t nNativeSize = TileBytes();
		if (pTile->nSize < nNativeSize)
		{
			Vector<uint8_t> arrDecoded;
			if (arrDecoded.resize(nNativeSize) != OK)
			{
				return ERR_OUT_OF_MEMORY;
			}
			if (Compression::decompress(arrDecoded.ptrw(), nNativeSize, arrStored.ptr(), pTile->nSize, Compression::MODE_ZSTD) != nNativeSize)
			{
				return ERR_FILE_CORRUPT;
			}
			arrStored = std::move(arrDecoded);
		}
		if (hash_murmur3_buffer(arrStored.ptr(), nNativeSize) != pTile->nChecksum)
		{
			return ERR_FILE_CORRUPT;
		}
	}
	out_arrData = std::move(arrStored);
	return OK;
}

void StreamingVirtualTextureFile::TerrainPBRWriter::Cancel()
{
	refFile.unref();
	if (!strTemporaryPath.is_empty())
	{
		DirAccess::remove_absolute(strTemporaryPath);
		strTemporaryPath = String();
	}
	strTargetPath = String();
	arrIndex.clear();
}

Error StreamingVirtualTextureFile::TerrainPBRWriter::Begin(const String &in_strPath, uint32_t in_nLog2TileCount, uint32_t in_nTileSize,
														   uint32_t in_nTileBorder, uint32_t in_nFirstStoredMip, const Rect2 &in_rectWorldRect, uint64_t in_nSourceSignature)
{
	if (refFile.is_valid())
	{
		return ERR_ALREADY_IN_USE;
	}
	if (in_strPath.is_empty() || !ValidPbrLayout(in_nLog2TileCount, in_nTileSize, in_nTileBorder, in_nFirstStoredMip, in_rectWorldRect))
	{
		return ERR_INVALID_PARAMETER;
	}
	// Use a sibling temporary file so publishing a finished bake is a same-volume rename.
	const String strPrefix = in_strPath + ".tmp-" + itos(OS::get_singleton()->get_process_id()) + "-" + uitos(uint64_t(uintptr_t(this)));
	String strTemp = strPrefix;
	for (uint32_t nSuffix = 1; FileAccess::exists(strTemp); ++nSuffix)
	{
		strTemp = strPrefix + "-" + uitos(nSuffix);
	}
	// This writer already owns a sibling staging file. WRITE_READ avoids nesting
	// FileAccess's editor backup/rename operation inside our own transaction.
	refFile = FileAccess::open(strTemp, FileAccess::WRITE_READ);
	if (refFile.is_null())
	{
		return ERR_FILE_CANT_OPEN;
	}
	strTargetPath = in_strPath;
	strTemporaryPath = strTemp;
	nPageCount = StoredPageCount(in_nLog2TileCount, in_nFirstStoredMip);
	const uint32_t nSide = in_nTileSize + 2 * in_nTileBorder;
	nPageBytes = nSide * nSide * 12;
	const uint32_t arrFields[] = { MAGIC, TERRAIN_PBR_VERSION, 0, FORMAT_TERRAIN_PBR, in_nLog2TileCount, in_nTileSize, in_nTileBorder,
								   2, in_nLog2TileCount + 1, in_nFirstStoredMip, 0, 0 };
	for (uint32_t nField : arrFields)
	{
		if (!refFile->store_32(nField))
		{
			Cancel();
			return ERR_FILE_CANT_WRITE;
		}
	}
	const uint64_t nPayload = TERRAIN_PBR_HEADER_SIZE + uint64_t(nPageCount) * TERRAIN_PBR_ENTRY_SIZE;
	if (!refFile->store_double(in_rectWorldRect.position.x) || !refFile->store_double(in_rectWorldRect.position.y) ||
		!refFile->store_double(in_rectWorldRect.size.x) || !refFile->store_double(in_rectWorldRect.size.y) || !refFile->store_64(in_nSourceSignature) ||
		refFile->resize(nPayload) != OK)
	{
		Cancel();
		return ERR_FILE_CANT_WRITE;
	}
	refFile->seek(nPayload);
	return OK;
}

Error StreamingVirtualTextureFile::TerrainPBRWriter::WriteNext(const Vector<uint8_t> &arrTwoLayers)
{
	if (refFile.is_null())
	{
		return ERR_UNCONFIGURED;
	}
	if (arrIndex.size() >= nPageCount || arrTwoLayers.size() != nPageBytes)
	{
		return ERR_INVALID_PARAMETER;
	}
	Vector<uint8_t> arrCompressed;
	if (arrCompressed.resize(Compression::get_max_compressed_buffer_size(nPageBytes, Compression::MODE_ZSTD)) != OK)
	{
		return ERR_OUT_OF_MEMORY;
	}
	const int64_t nSize = Compression::compress(arrCompressed.ptrw(), arrTwoLayers.ptr(), nPageBytes, Compression::MODE_ZSTD);
	const bool bUseCompressed = nSize > 0 && nSize < nPageBytes;
	Tile stTile;
	stTile.nOffset = refFile->get_position();
	stTile.nSize = bUseCompressed ? uint32_t(nSize) : nPageBytes;
	stTile.nChecksum = hash_murmur3_buffer(arrTwoLayers.ptr(), nPageBytes);
	if (!refFile->store_buffer(bUseCompressed ? arrCompressed.ptr() : arrTwoLayers.ptr(), stTile.nSize))
	{
		Cancel();
		return ERR_FILE_CANT_WRITE;
	}
	arrIndex.push_back(stTile);
	return OK;
}

Error StreamingVirtualTextureFile::TerrainPBRWriter::Finish()
{
	if (refFile.is_null() || arrIndex.size() != nPageCount)
	{
		return ERR_UNCONFIGURED;
	}
	refFile->seek(TERRAIN_PBR_HEADER_SIZE);
	for (const Tile &stTile : arrIndex)
	{
		if (!refFile->store_64(stTile.nOffset) || !refFile->store_32(stTile.nSize) || !refFile->store_32(stTile.nChecksum))
		{
			Cancel();
			return ERR_FILE_CANT_WRITE;
		}
	}
	refFile->flush();
	if (refFile->get_error() != OK)
	{
		Cancel();
		return ERR_FILE_CANT_WRITE;
	}
	refFile.unref();
	// Some filesystem backends only report a short buffered write on close. Validate
	// the final index and the stored payloads before replacing the previous good file.
	StreamingVirtualTextureFile stStaged;
	Error eErr = stStaged.Open(strTemporaryPath);
	if (eErr == OK)
	{
		Ref<FileAccess> refReader = FileAccess::open(strTemporaryPath, FileAccess::READ);
		if (refReader.is_null())
		{
			eErr = ERR_FILE_CANT_READ;
		}
		else
		{
			Vector<uint8_t> arrData;
			const Header &stStagedHeader = stStaged.GetHeader();
			for (uint32_t nMip = stStagedHeader.nFirstStoredMip; nMip < stStagedHeader.nLevelCount && eErr == OK; ++nMip)
			{
				const uint32_t nN = stStaged.GetTilesPerSide(nMip);
				for (uint32_t nY = 0; nY < nN && eErr == OK; ++nY)
				{
					for (uint32_t nX = 0; nX < nN && eErr == OK; ++nX)
					{
						eErr = stStaged.ReadTile(nMip, nX, nY, arrData, refReader.ptr());
					}
				}
			}
		}
	}
	if (eErr == OK)
	{
		eErr = DirAccess::rename_absolute(strTemporaryPath, strTargetPath);
	}
	if (eErr == OK)
	{
		strTemporaryPath = String();
	}
	Cancel();
	return eErr;
}

Error StreamingVirtualTextureFile::WriteTerrainPbr(const String &in_strPath, uint32_t in_nLog2TileCount, uint32_t in_nTileSize, uint32_t in_nTileBorder,
												   uint32_t in_nFirstStoredMip, const Rect2 &in_rectWorldRect, uint64_t in_nSourceSignature, const Vector<Vector<uint8_t>> &in_arrTiles)
{
	TerrainPBRWriter stWriter;
	Error eErr = stWriter.Begin(in_strPath, in_nLog2TileCount, in_nTileSize, in_nTileBorder, in_nFirstStoredMip, in_rectWorldRect, in_nSourceSignature);
	if (eErr != OK)
	{
		return eErr;
	}
	for (const Vector<uint8_t> &arrPage : in_arrTiles)
	{
		eErr = stWriter.WriteNext(arrPage);
		if (eErr != OK)
		{
			return eErr;
		}
	}
	return stWriter.Finish();
}

Error StreamingVirtualTextureFile::BakeImage(const String &in_strPath, const Ref<Image> &refImage, uint32_t in_nLog2TileCount,
											 uint32_t in_nTileSize, uint32_t in_nTileBorder, Format eFormat, bool bSrgb, bool bVertexGrid)
{
	ERR_FAIL_COND_V(refImage.is_null() || refImage->is_empty(), ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(bVertexGrid && eFormat != FORMAT_R32F, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(in_nLog2TileCount > 10, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(in_nTileSize == 0 || in_nTileSize > 1024, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(in_nTileBorder > 16, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(eFormat < FORMAT_RGBA8 || eFormat > FORMAT_R32F, ERR_INVALID_PARAMETER);
	if (eFormat != FORMAT_RGBA8 && eFormat != FORMAT_R32F)
	{
		ERR_FAIL_COND_V((in_nTileSize % 4) != 0 || (in_nTileBorder % 4) != 0, ERR_INVALID_PARAMETER);
	}

	const uint32_t nLevels = in_nLog2TileCount + 1;
	const uint32_t nTilesSide = 1u << in_nLog2TileCount;
	const uint32_t nVirtualSize = nTilesSide * in_nTileSize;
	// Baking holds roughly two copies of the source while running.
	ERR_FAIL_COND_V(nVirtualSize > 32768, ERR_INVALID_PARAMETER);
	const uint32_t nStride = in_nTileSize + 2 * in_nTileBorder;

	// Index layout must be known before the payload is written.
	uint64_t nIndexSize = 0;
	for (uint32_t nLevel = 0; nLevel < nLevels; nLevel++)
	{
		const uint32_t nSide = 1u << (in_nLog2TileCount - nLevel);
		nIndexSize += 8 + uint64_t(nSide) * nSide * INDEX_ENTRY_SIZE;
	}
	const uint64_t nPayloadStart = HEADER_SIZE + nIndexSize;

	Ref<FileAccess> refF = FileAccess::open(in_strPath, FileAccess::WRITE);
	if (refF.is_null())
	{
		return ERR_FILE_CANT_OPEN;
	}

	refF->store_32(MAGIC);
	refF->store_32(VERSION);
	refF->store_32(bSrgb ? 1u : 0u);
	refF->store_32(eFormat);
	refF->store_32(in_nLog2TileCount);
	refF->store_32(in_nTileSize);
	refF->store_32(in_nTileBorder);
	refF->store_32(1); // layer_count
	refF->store_32(nLevels);
	for (int nI = 0; nI < 3; nI++)
	{
		refF->store_32(0);
	}

	// Reserve the index.
	Vector<uint8_t> arrZeros;
	arrZeros.resize_initialized(nIndexSize);
	ERR_FAIL_COND_V(!refF->store_buffer(arrZeros.ptr(), arrZeros.size()), ERR_FILE_CANT_WRITE);

	// Index bytes are filled in place while tiles are written, then flushed once.
	Vector<uint8_t> arrIndexBytes;
	arrIndexBytes.resize_initialized(nIndexSize);
	uint8_t *pIndexPtr = arrIndexBytes.ptrw();
	Vector<uint64_t> arrLevelIndexOffset;
	arrLevelIndexOffset.resize(nLevels);
	{
		uint64_t nOffset = 0;
		for (uint32_t nLevel = 0; nLevel < nLevels; nLevel++)
		{
			const uint32_t nSide = 1u << (in_nLog2TileCount - nLevel);
			arrLevelIndexOffset.write[nLevel] = nOffset;
			nOffset += 8 + uint64_t(nSide) * nSide * INDEX_ENTRY_SIZE;
		}
	}
	auto stPutU32 = [](uint8_t *in_pDst, uint32_t nValue)
	{
		for (int nI = 0; nI < 4; nI++)
		{
			in_pDst[nI] = uint8_t(nValue >> (nI * 8));
		}
	};
	auto stPutU64 = [](uint8_t *in_pDst, uint64_t nValue)
	{
		for (int nI = 0; nI < 8; nI++)
		{
			in_pDst[nI] = uint8_t(nValue >> (nI * 8));
		}
	};
	for (uint32_t nLevel = 0; nLevel < nLevels; nLevel++)
	{
		const uint32_t nSide = 1u << (in_nLog2TileCount - nLevel);
		uint8_t *pLevelBase = pIndexPtr + arrLevelIndexOffset[nLevel];
		stPutU32(pLevelBase, nSide);
		stPutU32(pLevelBase + 4, nSide);
	}

	uint64_t nCursor = nPayloadStart;
	const Image::Format ePixelFormat = eFormat == FORMAT_R32F ? Image::FORMAT_RF : Image::FORMAT_RGBA8;
	Ref<Image> refLevelImage = refImage;
	if (refLevelImage->get_format() != ePixelFormat)
	{
		refLevelImage = refImage->duplicate();
		refLevelImage->convert(ePixelFormat);
	}

	for (uint32_t nLevel = 0; nLevel < nLevels; nLevel++)
	{
		const uint32_t nSide = 1u << (in_nLog2TileCount - nLevel);
		const uint32_t nLevelSize = nVirtualSize >> nLevel;
		Ref<Image> refSrc = refLevelImage;
		if (refSrc->get_width() != int(nLevelSize) || refSrc->get_height() != int(nLevelSize))
		{
			if (bVertexGrid)
			{
				// Texel i represents vertex i * extent / resolution. Every second vertex
				// coincides with its parent mip, including the first vertex on a page.
				const int nW = refSrc->get_width();
				const int nH = refSrc->get_height();
				Vector<uint8_t> arrSourceBytes = refSrc->get_data();
				const float *pHeights = reinterpret_cast<const float *>(arrSourceBytes.ptr());
				Vector<uint8_t> arrResampled;
				arrResampled.resize(uint64_t(nLevelSize) * nLevelSize * sizeof(float));
				float *pDst = reinterpret_cast<float *>(arrResampled.ptrw());
				for (uint32_t nY = 0; nY < nLevelSize; ++nY)
				{
					const double dV = double(nY) * nH / nLevelSize;
					const int nRow = int(dV) * nW;
					const int nNextRow = MIN(int(dV) + 1, nH - 1) * nW;
					for (uint32_t nX = 0; nX < nLevelSize; ++nX)
					{
						const double dU = double(nX) * nW / nLevelSize;
						const int nI = int(dU);
						const int nJ = MIN(nI + 1, nW - 1);
						const float fA = Math::lerp(pHeights[nRow + nI], pHeights[nRow + nJ], float(dU - nI));
						const float fB = Math::lerp(pHeights[nNextRow + nI], pHeights[nNextRow + nJ], float(dU - nI));
						*pDst++ = Math::lerp(fA, fB, float(dV - int(dV)));
					}
				}
				refSrc = Image::create_from_data(nLevelSize, nLevelSize, false, ePixelFormat, arrResampled);
			}
			else
			{
				refSrc = refLevelImage->duplicate();
				refSrc->resize(nLevelSize, nLevelSize, Image::INTERPOLATE_CUBIC);
			}
		}

		// Build each tile from a clamped copy of the level: no full padded level image is kept,
		// which keeps bake memory at about one extra copy of the source for big virtual sizes.
		Vector<uint8_t> arrPixels = refSrc->get_data();
		const uint8_t *pSp = arrPixels.ptr();
		const int nB = in_nTileBorder;
		Vector<uint8_t> arrTileBytes;
		arrTileBytes.resize(nStride * nStride * 4);

		for (uint32_t nY = 0; nY < nSide; nY++)
		{
			for (uint32_t nX = 0; nX < nSide; nX++)
			{
				const int nSx0 = int(nX * in_nTileSize) - nB;
				const int nSy0 = int(nY * in_nTileSize) - nB;
				uint8_t *pTp = arrTileBytes.ptrw();
				for (uint32_t nTy = 0; nTy < nStride; nTy++)
				{
					const int nSy = CLAMP(nSy0 + int(nTy), 0, int(nLevelSize) - 1);
					for (uint32_t nTx = 0; nTx < nStride; nTx++)
					{
						const int nSx = CLAMP(nSx0 + int(nTx), 0, int(nLevelSize) - 1);
						memcpy(pTp + (nTy * nStride + nTx) * 4, pSp + (nSy * nLevelSize + nSx) * 4, 4);
					}
				}

				Vector<uint8_t> arrData;
				switch (eFormat)
				{
				case FORMAT_RGBA8:
				case FORMAT_R32F: {
					arrData = arrTileBytes;
				}
				break;
				case FORMAT_BC1: {
					Ref<Image> refC = Image::create_from_data(nStride, nStride, false, Image::FORMAT_RGBA8, arrTileBytes);
					// Force BC1 (RGB) instead of letting the alpha channel pick BC3.
					if (refC->compress_from_channels(Image::COMPRESS_S3TC, Image::USED_CHANNELS_RGB) != OK)
					{
						return ERR_CANT_CREATE;
					}
					arrData = refC->get_data();
				}
				break;
				case FORMAT_BC7: {
					Ref<Image> refC = Image::create_from_data(nStride, nStride, false, Image::FORMAT_RGBA8, arrTileBytes);
					if (refC->compress(Image::COMPRESS_BPTC) != OK)
					{
						return ERR_CANT_CREATE;
					}
					arrData = refC->get_data();
				}
				break;
				default:
					return ERR_INVALID_PARAMETER;
				}
				ERR_FAIL_COND_V(!refF->store_buffer(arrData.ptr(), arrData.size()), ERR_FILE_CANT_WRITE);
				uint8_t *pEntry = pIndexPtr + arrLevelIndexOffset[nLevel] + 8 + uint64_t(nY * nSide + nX) * INDEX_ENTRY_SIZE;
				stPutU64(pEntry, nCursor);
				stPutU32(pEntry + 8, arrData.size());
				nCursor += arrData.size();
			}
		}
	}

	// Rewrite the index now that the offsets are known.
	refF->seek(HEADER_SIZE);
	ERR_FAIL_COND_V(!refF->store_buffer(pIndexPtr, arrIndexBytes.size()), ERR_FILE_CANT_WRITE);
	refF->flush();
	return refF->get_error();
}
