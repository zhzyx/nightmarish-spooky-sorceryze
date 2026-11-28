/**************************************************************************/
/*  StreamingVirtualTextureFile.h                                        */
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
// [ZXB] Streaming Virtual Texture page file: header / index parser and the offline baker.
// Format (little endian):
//   header 48 B: magic "GSVT", version, flags(bit0 sRGB), format, log2_tile_count,
//                tile_size, tile_border, layer_count, level_count, reserved[3]
//   index: per level { u32 tiles_x, u32 tiles_y, then tiles_x*tiles_y * { u64 offset, u32 size } }
//   payload: compressed (or raw) tiles, tile_size + 2 * tile_border on a side.
// TerrainPBR v2 reuses the common fields. The first reserved u32 is the first stored mip,
// followed after the common header by four f64 world XZ rect components and a u64 source signature.
// Only stored levels have index entries, ordered by mip, then row, then column.
// A v2 entry is {u64 offset, u32 stored size, u32 Murmur3 of raw bytes}. Zstd is used when
// smaller than the native payload: one whole RGBA8 tile followed by one whole RGBA16_UNORM tile.
#pragma endregion

#include "core/io/file_access.h"
#include "core/io/image.h"
#include "core/templates/local_vector.h"
#include "core/math/rect2.h"

class StreamingVirtualTextureFile
{
public:
	enum Format
	{
		FORMAT_RGBA8 = 0,
		FORMAT_BC1 = 1,
		FORMAT_BC7 = 2,
		FORMAT_R32F = 3,
		FORMAT_TERRAIN_PBR = 4,
		FORMAT_MAX,
	};

	enum
	{
		MAGIC = 0x54565347, // "GSVT"
		VERSION = 1,
		HEADER_SIZE = 48,
		INDEX_ENTRY_SIZE = 12,
		TERRAIN_PBR_VERSION = 2,
		TERRAIN_PBR_HEADER_SIZE = 88,
		TERRAIN_PBR_ENTRY_SIZE = 16,
	};

	struct Header
	{
		uint32_t nVersion = 0;
		uint32_t nFlags = 0;
		uint32_t nFormat = FORMAT_RGBA8;
		uint32_t nLog2TileCount = 0;
		uint32_t nTileSize = 0;
		uint32_t nTileBorder = 0;
		uint32_t nLayerCount = 1;
		uint32_t nLevelCount = 1;
		uint32_t nFirstStoredMip = 0;
		Rect2 rectWorldRect;
		uint64_t nSourceSignature = 0;

		bool IsSrgb() const
		{
			return (nFlags & 1) != 0;
		}
	};

	struct Tile
	{
		uint64_t nOffset = 0;
		uint32_t nSize = 0; // Stored bytes, including any v2 Zstd compression.
		uint32_t nChecksum = 0;
	};

	class TerrainPBRWriter
	{
		Ref<FileAccess> refFile;
		String strTargetPath;
		String strTemporaryPath;
		LocalVector<Tile> arrIndex;
		uint32_t nPageBytes = 0;
		uint32_t nPageCount = 0;

	public:
		TerrainPBRWriter() = default;
		TerrainPBRWriter(const TerrainPBRWriter &) = delete;
		TerrainPBRWriter &operator=(const TerrainPBRWriter &) = delete;
		~TerrainPBRWriter()
		{
			Cancel();
		}
		Error Begin(const String &in_strPath, uint32_t in_nLog2TileCount, uint32_t in_nTileSize, uint32_t in_nTileBorder,
					uint32_t in_nFirstStoredMip, const Rect2 &in_rectWorldRect, uint64_t in_nSourceSignature);
		Error WriteNext(const Vector<uint8_t> &arrTwoLayers);
		Error Finish();
		void Cancel();
	};

private:
	Header stHeader;
	String strPath;
	LocalVector<uint32_t> arrLevelOffset; // Index into `tiles` of the first tile of each level.
	LocalVector<Tile> arrTiles;

	uint32_t TilesPerSide(uint32_t in_nLevel) const;
	uint32_t TileBytes() const;

public:
	Error Open(const String &in_strPath);
	bool IsOpen() const
	{
		return !strPath.is_empty();
	}
	const Header &GetHeader() const
	{
		return stHeader;
	}
	const String &GetPath() const
	{
		return strPath;
	}
	uint32_t GetLevelCount() const
	{
		return stHeader.nLevelCount;
	}
	uint32_t GetTilesPerSide(uint32_t in_nLevel) const
	{
		return TilesPerSide(in_nLevel);
	}
	const Tile *GetTile(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY) const;
	uint32_t GetTileBytes() const
	{
		return TileBytes();
	}

	// p_reader may be shared between calls to avoid reopening the file (worker thread usage).
	Error ReadTile(uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, Vector<uint8_t> &out_arrData, FileAccess *in_pReader = nullptr) const;

	static Error WriteTerrainPbr(const String &in_strPath, uint32_t in_nLog2TileCount, uint32_t in_nTileSize, uint32_t in_nTileBorder,
								 uint32_t in_nFirstStoredMip, const Rect2 &in_rectWorldRect, uint64_t in_nSourceSignature, const Vector<Vector<uint8_t>> &in_arrTiles);

	// Bakes `p_image` into a page file. Page count per side is 1 << p_log2_tile_count.
	static Error BakeImage(const String &in_strPath, const Ref<Image> &refImage, uint32_t in_nLog2TileCount,
						   uint32_t in_nTileSize, uint32_t in_nTileBorder, Format eFormat, bool bSrgb = true, bool bVertexGrid = false);
};
