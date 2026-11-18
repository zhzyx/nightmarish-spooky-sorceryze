/**************************************************************************/
/*  ColorLut.h                                                            */
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

#include "engine_next/include/EngineNext/Assets/Types.h"

#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

struct DecodedImage;

struct ColorLut
{
	std::uint32_t nSize = 0;
	std::vector<std::uint8_t> arrRgba8;
};

// Reorders an N*N by N, top-left RGBA8 strip into a 3D texture. Red varies
// within a tile, green across rows, and blue across horizontal tiles.
// N is [2,64]. RGB samples represent display-linear values, alpha is ignored.
// Input stays immutable and failures leave the output unchanged. This pure
// conversion is callable on any thread with exclusive output access.
[[nodiscard]] bool BuildColorLut(const DecodedImage &stImage, ColorLut &out_stLut, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
