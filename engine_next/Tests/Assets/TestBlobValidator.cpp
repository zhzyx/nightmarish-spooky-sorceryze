/**************************************************************************/
/*  TestBlobValidator.cpp                                                 */
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

#include "engine_next/Tests/TestFramework.h"
#include "engine_next/Tests/Assets/FixtureSupport.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"

#include <algorithm>

ENGINE_NEXT_TEST("Blob validator accepts structural PNG JPEG and self-contained GLB")
{
	for (const auto &stEntry : { std::pair<const char *, const char *>{ "valid.png", "image/png" }, { "valid.jpg", "image/jpeg" }, { "valid-rgb.jpg", "image/jpeg" }, { "valid.glb", "model/gltf-binary" } })
	{
		const std::vector<std::uint8_t> arrBytes = EngineNext::Tests::Assets::ReadFixture(stEntry.first);
		EngineNext::Assets::BlobInfo stInfo;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateBlob(stEntry.second, arrBytes, stInfo, arrDiagnostics));
	}
	EngineNext::Assets::BlobInfo stGlb;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateBlob("model/gltf-binary", EngineNext::Tests::Assets::ReadFixture("valid.glb"), stGlb, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGlb.nVertexCount, 3ULL);
	ENGINE_NEXT_CHECK_EQ(stGlb.nTriangleCount, 1ULL);
}

ENGINE_NEXT_TEST("Blob validator rejects CRC truncation unsupported and oversized inputs")
{
	for (const auto &stEntry : {
				 std::pair<const char *, const char *>{ "invalid.png", "image/png" },
				 { "invalid.jpg", "image/jpeg" },
				 { "invalid.glb", "model/gltf-binary" },
				 { "invalid-ihdr.png", "image/png" },
				 { "empty-scan.jpg", "image/jpeg" },
				 { "invalid-accessor.glb", "model/gltf-binary" },
				 { "invalid-buffer.glb", "model/gltf-binary" },
				 { "invalid-depth.png", "image/png" },
		 })
	{
		EngineNext::Assets::BlobInfo stInfo;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateBlob(stEntry.second, EngineNext::Tests::Assets::ReadFixture(stEntry.first), stInfo, arrDiagnostics));
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	}
	EngineNext::Assets::BlobInfo stInfo;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateBlob("application/octet-stream", { 1 }, stInfo, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateBlob("image/png", {}, stInfo, arrDiagnostics));
	std::vector<std::uint8_t> arrHuge(16 * 1024 * 1024 + 1, 0);
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateBlob("image/png", arrHuge, stInfo, arrDiagnostics));
}

ENGINE_NEXT_TEST("Blob validator rejects short IHDR and SOS before field access")
{
	std::vector<std::uint8_t> arrPng = EngineNext::Tests::Assets::ReadFixture("valid.png");
	const std::size_t nShort = arrPng.size() - 12;
	std::fill(arrPng.begin() + static_cast<std::ptrdiff_t>(nShort), arrPng.end(), std::uint8_t{ 0 });
	arrPng[nShort + 4] = 'I';
	arrPng[nShort + 5] = 'H';
	arrPng[nShort + 6] = 'D';
	arrPng[nShort + 7] = 'R';
	const std::vector<std::uint8_t> arrJpeg = { 0xFF, 0xD8, 0xFF, 0xDA, 0x00, 0x02 };
	EngineNext::Assets::BlobInfo stInfo;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateBlob("image/png", arrPng, stInfo, arrDiagnostics));
	arrDiagnostics.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Assets::ValidateBlob("image/jpeg", arrJpeg, stInfo, arrDiagnostics));
}
