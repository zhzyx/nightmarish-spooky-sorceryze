/**************************************************************************/
/*  FixedStepLoop.h                                                       */
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

#include "engine_next/include/EngineNext/Runtime/Types.h"

#include <cstdint>

namespace EngineNext::Runtime
{

struct FixedStepBatch
{
	std::uint64_t nFirstTick = 0;
	std::uint32_t nStepCount = 0;
	std::uint64_t nDroppedMsec = 0;
};

class FixedStepLoop
{
	std::uint32_t nFixedStepMsec = 16;
	std::uint32_t nMaxCatchUpSteps = 8;
	std::uint64_t nLastNowMsec = 0;
	std::uint64_t nAccumulatorMsec = 0;
	std::uint64_t nTick = 0;
	bool bStarted = false;

public:
	[[nodiscard]] bool SetFixedStepMsec(std::uint32_t nValue) noexcept;
	[[nodiscard]] bool SetMaxCatchUpSteps(std::uint32_t nValue) noexcept;
	[[nodiscard]] std::uint32_t GetFixedStepMsec() const noexcept;
	[[nodiscard]] std::uint64_t GetTick() const noexcept;
	[[nodiscard]] std::uint64_t GetAccumulatorMsec() const noexcept;
	[[nodiscard]] RuntimeStatus Advance(std::uint64_t nNowMsec, FixedStepBatch &out_stBatch) noexcept;
	void Reset() noexcept;
};

} // namespace EngineNext::Runtime
