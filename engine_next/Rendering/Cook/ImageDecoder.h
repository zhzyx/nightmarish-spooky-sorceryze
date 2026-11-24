/**************************************************************************/
/*  ImageDecoder.h                                                        */
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
#include "engine_next/include/EngineNext/Rendering/ImageData.h"

#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{

// Synchronous CPU decode with caller-owned inputs and outputs. Non-interlaced RGBA8 PNG
// decoding is portable. Windows WIC handles other PNG layouts and JPEG.
// The 16 MiB source and 8192-pixel dimension limits apply before pixel allocation.
// PNG zlib completion, checksum, scanline lengths and filter bytes are validated
// independently before the OS decoder, including Adam7 interlaced scanlines.
// JPEG coefficient decoding uses libjpeg-turbo and treats all warnings as errors.
// No EXIF rotation, profile transform or implicit color-space conversion occurs.
// Every failure appends a diagnostic and preserves the previous output.
[[nodiscard]] bool DecodeImage(const std::vector<std::uint8_t> &arrEncoded, const std::string &strMediaType, DecodedImage &out_stImage, Assets::Diagnostics &out_arrDiagnostics);

// The complete chain includes the original image and ends at 1x1. Odd dimensions
// use area-weighted footprints so every source texel contributes. RGB is filtered
// in the selected space; Srgb filtering uses premultiplied weights and stores
// straight alpha again. Linear data channels are independent. Masked alpha-coverage correction is a
// separate material-cook operation and is not applied by this function.
[[nodiscard]] bool BuildMipChain(const DecodedImage &stImage, ImageSemantic eSemantic, std::vector<MipLevel> &out_arrLevels, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
