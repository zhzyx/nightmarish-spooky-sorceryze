/**************************************************************************/
/*  TemporalState.h                                                       */
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

#include "engine_next/include/EngineNext/Rendering/CameraMatrices.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

struct CameraSettings;

constexpr std::uint32_t TEMPORAL_SAMPLE_COUNT = 8;
constexpr std::uint32_t MAX_TEMPORAL_DRAWS = 65536;

// Matches RenderInstance identity fields. A mesh node is required because one
// entity may instantiate the same asset primitive through multiple nodes.
struct TemporalDrawKey
{
	std::uint64_t nEntityId = 0;
	std::uint32_t nAssetIndex = 0;
	std::uint32_t nPrimitive = 0;
	std::uint32_t nNode = 0;
};

struct TemporalDrawInput
{
	TemporalDrawKey stKey;
	std::array<double, 16> arrWorld{};
	bool bResetHistory = false;
};

struct TemporalDrawFrame
{
	TemporalDrawKey stKey;
	std::array<double, 16> arrCurrentWorld{};
	std::array<double, 16> arrPreviousWorld{};
	bool bHistoryValid = false;
};

struct TemporalFrame
{
	std::uint64_t nToken = 0;
	std::uint64_t nEpoch = 0;
	std::uint32_t nSampleIndex = 0;
	std::array<double, 2> arrJitterPixels{};
	CameraMatrices stCurrentCamera;
	CameraMatrices stCurrentUnjitteredCamera;
	CameraMatrices stPreviousUnjitteredCamera;
	std::vector<TemporalDrawFrame> arrDraws;
	bool bHistoryValid = false;
};

// One render-thread owner per view. GPU resources and fences remain caller-owned.
// PrepareFrame builds a candidate without advancing committed camera, transforms,
// epoch, or jitter. Only the newest successful candidate token can be committed.
// Call CommitFrame after successful submission, including the completion signal.
// Abandoned candidates consume no jitter sample. A later successful prepare
// supersedes an older candidate; failed preparation preserves it and its token.
//
// Jitter is an eight-sample centered Halton(2,3) sequence in pixels, positive right
// and down. Motion uses unjittered matrices. Projection or viewport changes reset
// the candidate history and restart its sequence. Ordinary camera motion retains
// history. Reset explicitly handles camera cuts, reconnects, and scene replacement.
// Per-draw reset invalidates only that draw for the current candidate. New draws
// have invalid previous data, while removed draws disappear after commit.
//
// Input worlds are finite column-major doubles. GPU conversion is caller-owned.
// Invalid history falls back to current data. Output draw order matches input.
// Failure appends diagnostics and preserves output and all state.
class TemporalState final
{
public:
	[[nodiscard]] bool PrepareFrame(const CameraSettings &stCamera, std::uint32_t nWidth, std::uint32_t nHeight,
									const std::vector<TemporalDrawInput> &arrDraws, TemporalFrame &out_stFrame, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool CommitFrame(std::uint64_t nToken, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Reset(Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] std::uint64_t GetEpoch() const noexcept;
	[[nodiscard]] bool HasHistory() const noexcept;

private:
	struct Snapshot
	{
		CameraMatrices stCamera;
		std::vector<TemporalDrawInput> arrDraws;
		std::uint32_t nWidth = 0;
		std::uint32_t nHeight = 0;
		double dVerticalFovDegrees = 0;
		double dNearPlane = 0;
		double dFarPlane = 0;
		std::uint64_t nEpoch = 1;
		std::uint32_t nNextSampleIndex = 0;
	};

	Snapshot stCommitted;
	Snapshot stPending;
	std::uint64_t nEpoch = 1;
	std::uint64_t nLastToken = 0;
	std::uint64_t nPendingToken = 0;
	bool bHasCommitted = false;
};

} // namespace EngineNext::Rendering
