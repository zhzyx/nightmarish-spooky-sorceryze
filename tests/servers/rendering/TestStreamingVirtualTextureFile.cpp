/**************************************************************************/
/*  TestStreamingVirtualTextureFile.cpp                                  */
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

#pragma region Engine ZXB
// [ZXB] Unit tests for the Streaming Virtual Texture page file.
#pragma endregion

#include "tests/test_macros.h"

TEST_FORCE_LINK(TestStreamingVirtualTextureFile)

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/image.h"
#include "core/os/os.h"
#include "servers/rendering/StreamingVirtualTextureFile.h"

namespace TestStreamingVirtualTextureFile
{

static String TempPath(const String &strName)
{
	return OS::get_singleton()->get_temp_path().path_join(strName);
}

static Ref<Image> MakeImage(int in_nSize, const Color &colColor)
{
	Ref<Image> refImg = Image::create_empty(in_nSize, in_nSize, false, Image::FORMAT_RGBA8);
	refImg->fill(colColor);
	return refImg;
}

TEST_CASE("[SVTPageFile] Bake and read back an uncompressed page file")
{
	const String strPath = TempPath("godot_svt_test_rgba8.svt");
	Ref<Image> refImg = MakeImage(256, Color(1, 0, 0, 1));
	REQUIRE(StreamingVirtualTextureFile::BakeImage(strPath, refImg, 1, 128, 4, StreamingVirtualTextureFile::FORMAT_RGBA8, false) == OK);

	StreamingVirtualTextureFile stFile;
	REQUIRE(stFile.Open(strPath) == OK);
	CHECK(stFile.GetHeader().nLog2TileCount == 1);
	CHECK(stFile.GetLevelCount() == 2);
	CHECK(stFile.GetTilesPerSide(0) == 2);
	CHECK(stFile.GetTilesPerSide(1) == 1);
	CHECK(stFile.GetTileBytes() == 136 * 136 * 4);

	Vector<uint8_t> arrTile;
	REQUIRE(stFile.ReadTile(0, 1, 1, arrTile) == OK);
	REQUIRE(arrTile.size() == 136 * 136 * 4);
	// Uniform red survives bake + border padding.
	CHECK(arrTile[0] == 255);
	CHECK(arrTile[1] == 0);
	CHECK(arrTile[2] == 0);
	CHECK(arrTile[3] == 255);

	Vector<uint8_t> arrCoarse;
	REQUIRE(stFile.ReadTile(1, 0, 0, arrCoarse) == OK);
	CHECK(arrCoarse.size() == 136 * 136 * 4);

	CHECK(stFile.ReadTile(2, 0, 0, arrTile) != OK); // Level out of range.
	CHECK(stFile.ReadTile(0, 2, 0, arrTile) != OK); // Page out of range.

	DirAccess::remove_absolute(strPath);
}

TEST_CASE("[SVTPageFile] Block compressed tiles keep their block size")
{
	const String strPath = TempPath("godot_svt_test_bc1.svt");
	Ref<Image> refImg = MakeImage(256, Color(0, 1, 0, 1));
	REQUIRE(StreamingVirtualTextureFile::BakeImage(strPath, refImg, 1, 128, 4, StreamingVirtualTextureFile::FORMAT_BC1, true) == OK);

	StreamingVirtualTextureFile stFile;
	REQUIRE(stFile.Open(strPath) == OK);
	CHECK(stFile.GetHeader().IsSrgb());
	CHECK(stFile.GetHeader().nFormat == StreamingVirtualTextureFile::FORMAT_BC1);
	CHECK(stFile.GetTileBytes() == 34 * 34 * 8);

	Vector<uint8_t> arrTile;
	REQUIRE(stFile.ReadTile(0, 0, 0, arrTile) == OK);
	CHECK(arrTile.size() == 34 * 34 * 8);

	DirAccess::remove_absolute(strPath);
}

TEST_CASE("[SVTPageFile] Edge clamped borders replicate the source edge")
{
	const String strPath = TempPath("godot_svt_test_border.svt");
	Ref<Image> refImg = MakeImage(128, Color(0, 0, 1, 1));
	refImg->fill_rect(Rect2i(0, 0, 64, 128), Color(1, 0, 0, 1)); // Left half red, right half blue.
	REQUIRE(StreamingVirtualTextureFile::BakeImage(strPath, refImg, 0, 128, 4, StreamingVirtualTextureFile::FORMAT_RGBA8, false) == OK);

	StreamingVirtualTextureFile stFile;
	REQUIRE(stFile.Open(strPath) == OK);
	Vector<uint8_t> arrTile;
	REQUIRE(stFile.ReadTile(0, 0, 0, arrTile) == OK);
	REQUIRE(arrTile.size() == 136 * 136 * 4);
	auto stPixel = [&arrTile](int nX, int nY)
	{
		return &arrTile[(nY * 136 + nX) * 4];
	};
	// Left border replicates the leftmost column (red), right border the rightmost one (blue).
	CHECK(stPixel(0, 4)[0] == 255);
	CHECK(stPixel(0, 4)[2] == 0);
	CHECK(stPixel(135, 4)[0] == 0);
	CHECK(stPixel(135, 4)[2] == 255);
	// Interior is offset by the border.
	CHECK(stPixel(4, 4)[0] == 255);
	CHECK(stPixel(131, 4)[2] == 255);
	// Top and bottom borders replicate the first and last row.
	CHECK(stPixel(4, 0)[0] == 255);
	CHECK(stPixel(4, 135)[0] == 255);
	CHECK(stPixel(131, 135)[2] == 255);

	DirAccess::remove_absolute(strPath);
}

TEST_CASE("[SVTPageFile] Rejects invalid layouts and corrupt files")
{
	const String strPath = TempPath("godot_svt_test_bad.svt");
	Ref<Image> refImg = MakeImage(128, Color(0, 0, 1, 1));

	// BC1 requires block aligned tiles and borders.
	CHECK(StreamingVirtualTextureFile::BakeImage(strPath, refImg, 0, 130, 4, StreamingVirtualTextureFile::FORMAT_BC1) == ERR_INVALID_PARAMETER);
	CHECK(StreamingVirtualTextureFile::BakeImage(strPath, refImg, 0, 128, 2, StreamingVirtualTextureFile::FORMAT_BC1) == ERR_INVALID_PARAMETER);

	REQUIRE(StreamingVirtualTextureFile::BakeImage(strPath, refImg, 0, 128, 4, StreamingVirtualTextureFile::FORMAT_RGBA8) == OK);
	PackedByteArray arrRaw = FileAccess::get_file_as_bytes(strPath);
	REQUIRE(arrRaw.size() > 48);

	// Bad magic.
	{
		Vector<uint8_t> arrBytes;
		arrBytes.resize(arrRaw.size());
		memcpy(arrBytes.ptrw(), arrRaw.ptr(), arrRaw.size());
		arrBytes.write[0] = 'X';
		Ref<FileAccess> refF = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refF.is_valid());
		refF->store_buffer(arrBytes.ptr(), arrBytes.size());
		refF->flush();
		refF.unref();
		StreamingVirtualTextureFile stFile;
		CHECK(stFile.Open(strPath) == ERR_FILE_UNRECOGNIZED);
	}

	// Truncated payload.
	{
		Vector<uint8_t> arrBytes;
		arrBytes.resize(arrRaw.size() / 2);
		memcpy(arrBytes.ptrw(), arrRaw.ptr(), arrBytes.size());
		Ref<FileAccess> refF = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refF.is_valid());
		refF->store_buffer(arrBytes.ptr(), arrBytes.size());
		refF->flush();
		refF.unref();
		StreamingVirtualTextureFile stFile;
		CHECK(stFile.Open(strPath) == ERR_FILE_CORRUPT);
	}

	StreamingVirtualTextureFile stMissing;
	CHECK(stMissing.Open(TempPath("godot_svt_does_not_exist.svt")) == ERR_FILE_CANT_OPEN);

	DirAccess::remove_absolute(strPath);
}

TEST_CASE("[SVTPageFile] Sparse TerrainPBR mips preserve both native layers and the world domain")
{
	using SVT = StreamingVirtualTextureFile;
	const String strPath = TempPath("godot_svt_test_terrain_pbr.gsvt");
	const Rect2 rectRect(-255.75, 42.5, 512, 256);
	const uint64_t nSignature = 0xd374a19be6d50c81ULL;
	const int nBytes = 6 * 6 * 12; // Four interior texels with a one-texel border.
	Vector<Vector<uint8_t>> arrPages;
	uint32_t nRandom = 0x1a2097b4;
	for (int nI = 0; nI < 5; ++nI)
	{
		Vector<uint8_t> arrTile;
		arrTile.resize(nBytes);
		uint8_t *pDst = arrTile.ptrw();
		for (int nJ = 0; nJ < nBytes; ++nJ)
		{
			nRandom ^= nRandom << 13;
			nRandom ^= nRandom >> 17;
			nRandom ^= nRandom << 5;
			// The root exercises the raw page branch, the rest compress independently.
			pDst[nJ] = nI == 4 ? uint8_t(nRandom) : uint8_t(nI + (nJ < 6 * 6 * 4 ? 0 : 128));
		}
		arrPages.push_back(arrTile);
	}
	REQUIRE(SVT::WriteTerrainPbr(strPath, 10, 4, 1, 9, rectRect, nSignature, arrPages) == OK);
	SVT stFile;
	REQUIRE(stFile.Open(strPath) == OK);
	CHECK(stFile.GetHeader().nFormat == SVT::FORMAT_TERRAIN_PBR);
	CHECK(stFile.GetHeader().nLayerCount == 2);
	CHECK(stFile.GetHeader().rectWorldRect == rectRect);
	CHECK(stFile.GetHeader().nSourceSignature == nSignature);
	CHECK(stFile.GetHeader().nFirstStoredMip == 9);
	CHECK(stFile.GetLevelCount() == 11);
	CHECK(stFile.GetTilesPerSide(0) == 1024);
	CHECK(stFile.GetTileBytes() == nBytes);
	CHECK(stFile.GetTile(8, 0, 0) == nullptr);
	CHECK(stFile.GetTile(9, 2, 0) == nullptr);
	Ref<FileAccess> refShared = FileAccess::open(strPath, FileAccess::READ);
	REQUIRE(refShared.is_valid());
	CHECK(refShared->get_length() < 5 * nBytes);
	for (int nI = 0; nI < 5; ++nI)
	{
		const int nLevel = nI == 4 ? 10 : 9;
		const int nX = nI == 4 ? 0 : nI % 2;
		const int nY = nI == 4 ? 0 : nI / 2;
		const SVT::Tile *pTile = stFile.GetTile(nLevel, nX, nY);
		REQUIRE(pTile);
		CHECK((pTile->nSize == nBytes) == (nI == 4));
		Vector<uint8_t> arrDecoded;
		REQUIRE(stFile.ReadTile(nLevel, nX, nY, arrDecoded, refShared.ptr()) == OK);
		CHECK(arrDecoded == arrPages[nI]);
	}
	refShared.unref();
	const Vector<uint8_t> arrOriginal = FileAccess::get_file_as_bytes(strPath);
	{
		SVT::TerrainPBRWriter stWriter;
		REQUIRE(stWriter.Begin(strPath, 2, 4, 1, 1, rectRect, 0) == OK);
		CHECK(stWriter.WriteNext(Vector<uint8_t>()) == ERR_INVALID_PARAMETER);
		REQUIRE(stWriter.WriteNext(arrPages[0]) == OK);
		CHECK(stWriter.Finish() != OK);
	}
	CHECK(FileAccess::get_file_as_bytes(strPath) == arrOriginal);
	CHECK(SVT::WriteTerrainPbr(strPath, 1, 4, 1, 2, rectRect, 0, arrPages) == ERR_INVALID_PARAMETER);
	CHECK(SVT::WriteTerrainPbr(strPath, 1, 4, 1, 0, Rect2(), 0, arrPages) == ERR_INVALID_PARAMETER);

	auto stReplaceFile = [&strPath](const Vector<uint8_t> &in_arrBytes)
	{
		Ref<FileAccess> refOut = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refOut.is_valid());
		REQUIRE(refOut->store_buffer(in_arrBytes.ptr(), in_arrBytes.size()));
	};
	for (int nI = 0; nI < 2; ++nI)
	{
		const int nLevel = nI == 0 ? 9 : 10;
		Vector<uint8_t> arrDamaged = arrOriginal;
		const int64_t nOffset = stFile.GetTile(nLevel, 0, 0)->nOffset;
		arrDamaged.write[nOffset] ^= 0xff;
		stReplaceFile(arrDamaged);
		Vector<uint8_t> arrDecoded;
		CHECK(stFile.ReadTile(nLevel, 0, 0, arrDecoded) == ERR_FILE_CORRUPT);
		CHECK(arrDecoded.is_empty());
	}

	Vector<uint8_t> arrTruncated = arrOriginal;
	arrTruncated.resize(arrTruncated.size() - 1);
	stReplaceFile(arrTruncated);
	CHECK(stFile.Open(strPath) == ERR_FILE_CORRUPT);
	CHECK(!stFile.IsOpen());
	CHECK(stFile.GetTile(0, 0, 0) == nullptr);
	Vector<uint8_t> arrMalformed = arrOriginal;
	for (int nI = 0; nI < 8; ++nI)
	{
		arrMalformed.write[SVT::TERRAIN_PBR_HEADER_SIZE + nI] = 0xff;
	}
	stReplaceFile(arrMalformed);
	CHECK(stFile.Open(strPath) == ERR_FILE_CORRUPT);
	DirAccess::remove_absolute(strPath);
}

TEST_CASE("[SVTPageFile] Abandoned and completed rebakes of the same destination")
{
	using SVT = StreamingVirtualTextureFile;
	const String strPath = TempPath("godot_svt_rebake_" + itos(OS::get_singleton()->get_process_id()) + ".svt");
	const Rect2 rectRect(0, 0, 32, 32);
	Vector<uint8_t> arrFirst;
	arrFirst.resize_initialized(4 * 4 * 12);
	Vector<uint8_t> arrSecond = arrFirst;
	arrSecond.fill(0x59);
	{
		SVT::TerrainPBRWriter stWriter;
		REQUIRE(stWriter.Begin(strPath, 1, 4, 0, 1, rectRect, 123) == OK);
		REQUIRE(stWriter.WriteNext(arrFirst) == OK);
		REQUIRE(stWriter.Finish() == OK);
	}
	const Vector<uint8_t> arrGoodFile = FileAccess::get_file_as_bytes(strPath);
	REQUIRE(!arrGoodFile.is_empty());
	{
		SVT::TerrainPBRWriter stWriter;
		REQUIRE(stWriter.Begin(strPath, 1, 4, 0, 0, rectRect, 123) == OK);
		REQUIRE(stWriter.WriteNext(arrSecond) == OK);
		CHECK(stWriter.Finish() != OK);
	}
	CHECK(FileAccess::get_file_as_bytes(strPath) == arrGoodFile);
#ifdef WINDOWS_ENABLED
	// A reader without FILE_SHARE_DELETE can refuse replacement. The source file and
	// its index must remain intact until the caller can retry after the lock clears.
	{
		Ref<FileAccess> refReader = FileAccess::open(strPath, FileAccess::READ);
		REQUIRE(refReader.is_valid());
		SVT::TerrainPBRWriter stWriter;
		REQUIRE(stWriter.Begin(strPath, 1, 4, 0, 1, rectRect, 456) == OK);
		REQUIRE(stWriter.WriteNext(arrSecond) == OK);
		CHECK(stWriter.Finish() != OK);
		CHECK(FileAccess::get_file_as_bytes(strPath) == arrGoodFile);
	}
#endif
	{
		SVT::TerrainPBRWriter stWriter;
		REQUIRE(stWriter.Begin(strPath, 1, 4, 0, 0, rectRect, 123) == OK);
		for (int nI = 0; nI < 5; ++nI)
		{
			REQUIRE(stWriter.WriteNext(arrSecond) == OK);
		}
		REQUIRE(stWriter.Finish() == OK);
	}
	SVT stReopened;
	REQUIRE(stReopened.Open(strPath) == OK);
	CHECK(stReopened.GetHeader().nFirstStoredMip == 0);
	CHECK(stReopened.GetHeader().nSourceSignature == 123);
	Vector<uint8_t> arrTile;
	REQUIRE(stReopened.ReadTile(1, 0, 0, arrTile) == OK);
	CHECK(arrTile == arrSecond);
	CHECK(DirAccess::remove_absolute(strPath) == OK);
}

TEST_CASE("[SVTPageFile] Legacy R32F vertex grid retains its single linear layer")
{
	using SVT = StreamingVirtualTextureFile;
	const String strPath = TempPath("godot_svt_test_legacy_height.gsvt");
	Ref<Image> refHeights = Image::create_empty(8, 8, false, Image::FORMAT_RF);
	refHeights->fill(Color(-2.5, 0, 0));
	REQUIRE(SVT::BakeImage(strPath, refHeights, 1, 4, 1, SVT::FORMAT_R32F, false, true) == OK);
	SVT stFile;
	REQUIRE(stFile.Open(strPath) == OK);
	CHECK(stFile.GetHeader().nVersion == 1);
	CHECK(stFile.GetHeader().nLayerCount == 1);
	CHECK(stFile.GetHeader().nFirstStoredMip == 0);
	CHECK(!stFile.GetHeader().IsSrgb());
	Vector<uint8_t> arrRoot;
	REQUIRE(stFile.ReadTile(1, 0, 0, arrRoot) == OK);
	REQUIRE(arrRoot.size() == 6 * 6 * int(sizeof(float)));
	CHECK(reinterpret_cast<const float *>(arrRoot.ptr())[0] == -2.5f);
	DirAccess::remove_absolute(strPath);
}

} // namespace TestStreamingVirtualTextureFile
