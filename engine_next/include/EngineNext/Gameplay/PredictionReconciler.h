/**************************************************************************/
/*  PredictionReconciler.h                                                */
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

#include "engine_next/include/EngineNext/Gameplay/PredictionModel.h"

#include <cstdint>
#include <deque>

namespace EngineNext::Gameplay
{

class PredictionReconciler
{
	struct HistoryEntry
	{
		PredictionInput stInput;
		PredictionState stPredictedState;
	};

	PredictionModel stModel;
	PredictionState stPredictedState;
	std::deque<HistoryEntry> arrHistory;
	std::uint64_t nNextSequence = 1;
	std::uint64_t nLastConfirmedSequence = 0;
	std::uint32_t nCorrectionCount = 0;
	std::uint32_t nMaxHistory = 256;
	float fCorrectionThreshold = 0.001F;

public:
	[[nodiscard]] bool SetInitialState(const PredictionState &in_stState) noexcept;
	// Resume keeps the next local sequence, discards untransported history and rebases on authority.
	[[nodiscard]] bool RestoreAfterReconnect(const PredictionState &in_stState, float &out_fPositionError) noexcept;
	[[nodiscard]] bool PredictInput(const Vector3 &in_vMovement, PredictionInput &out_stInput) noexcept;
	[[nodiscard]] bool ApplyAuthoritativeState(const PredictionState &in_stState, float &out_fPositionError) noexcept;
	[[nodiscard]] const PredictionState &GetPredictedState() const noexcept;
	[[nodiscard]] std::size_t GetUnconfirmedInputCount() const noexcept;
	[[nodiscard]] std::uint64_t GetLastConfirmedSequence() const noexcept;
	[[nodiscard]] std::uint32_t GetCorrectionCount() const noexcept;
};

} // namespace EngineNext::Gameplay
