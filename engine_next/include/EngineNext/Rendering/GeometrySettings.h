/**************************************************************************/
/*  GeometrySettings.h                                                    */
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
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <cstdint>

namespace EngineNext::Rendering
{
struct GeometrySettings
{
	bool bEnabled = false;
	bool bOcclusion = true;
	std::uint32_t nMaxCommands = 262144;
	bool bLodEnabled = true;
	double dPixelError = 1;
	double dLodHysteresis = .1;
	std::uint64_t nPageGpuBytes = 128ULL * 1024 * 1024;
	std::uint64_t nPageStagingBytes = 16ULL * 1024 * 1024;
	std::uint32_t nMaxPageLoads = 16;
};

// A positive command capacity is an explicit upper bound. The renderer plans
// actual candidates and allocations before enabling GPU submission. Capacity
// or allocation failures retain the complete conventional draw path.
[[nodiscard]] bool ValidateGeometrySettings(const GeometrySettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool ParseGeometrySettings(const Serialization::JsonValue &stValue, GeometrySettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics);
} // namespace EngineNext::Rendering
