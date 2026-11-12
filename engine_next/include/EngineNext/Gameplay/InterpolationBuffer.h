/**************************************************************************/
/*  InterpolationBuffer.h                                                 */
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

#include "EngineNext/Gameplay/PredictionTypes.h"
#include "EngineNext/Gameplay/Status.h"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>

namespace EngineNext::Gameplay
{

enum class InterpolationStatus : std::uint8_t
{
	Empty = 0,
	SingleSample = 1,
	BeforeRange = 2,
	Interpolated = 3,
	Held = 4,
	StaleHeld = 5,
};

struct InterpolationResult
{
	InterpolationStatus eStatus = InterpolationStatus::Empty;
	std::optional<PredictionState> stState;
};

class InterpolationBuffer
{
	std::vector<PredictionState> arrSamples;
	std::size_t nMaxSamples = 32;
	std::uint64_t nInterpolationDelayMsec = 100;
	std::uint64_t nStaleAfterMsec = 500;

public:
	[[nodiscard]] bool SetMaxSamples(std::size_t nValue) noexcept;
	[[nodiscard]] std::size_t GetMaxSamples() const noexcept;
	[[nodiscard]] bool SetInterpolationDelayMsec(std::uint64_t nValue) noexcept;
	[[nodiscard]] std::uint64_t GetInterpolationDelayMsec() const noexcept;
	[[nodiscard]] bool SetStaleAfterMsec(std::uint64_t nValue) noexcept;
	[[nodiscard]] std::uint64_t GetStaleAfterMsec() const noexcept;
	[[nodiscard]] Status AddSample(const PredictionState &in_stState);
	[[nodiscard]] InterpolationResult Sample(std::uint64_t nNowMsec) const noexcept;
	[[nodiscard]] std::size_t GetSampleCount() const noexcept;
	void Clear() noexcept;
};

} // namespace EngineNext::Gameplay
