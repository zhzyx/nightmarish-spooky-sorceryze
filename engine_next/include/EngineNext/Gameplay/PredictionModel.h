/**************************************************************************/
/*  PredictionModel.h                                                     */
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

#include "engine_next/include/EngineNext/Gameplay/PredictionTypes.h"
#include "engine_next/include/EngineNext/Gameplay/Status.h"

#include <cstdint>

namespace EngineNext::Gameplay
{

class PredictionModel
{
	float fMaxSpeed = 8.0F;
	std::uint32_t nFixedStepMsec = 16;

public:
	[[nodiscard]] bool SetMaxSpeed(float fValue) noexcept;
	[[nodiscard]] float GetMaxSpeed() const noexcept;
	[[nodiscard]] bool SetFixedStepMsec(std::uint32_t nValue) noexcept;
	[[nodiscard]] std::uint32_t GetFixedStepMsec() const noexcept;
	[[nodiscard]] Status Simulate(PredictionState &out_stState, const PredictionInput &in_stInput) const noexcept;
};

} // namespace EngineNext::Gameplay
