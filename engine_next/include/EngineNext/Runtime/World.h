/**************************************************************************/
/*  World.h                                                               */
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
#include "engine_next/include/EngineNext/Runtime/Types.h"

#include <cstddef>
#include <cstdint>
#include <map>

namespace EngineNext::Runtime
{

class World
{
	using EntityMap = std::map<EntityId, Gameplay::PredictionState>;

	EntityMap mapEntities;
	std::uint64_t nNextEntityId = 1;

public:
	[[nodiscard]] RuntimeStatus Create(EntityId &out_stEntityId);
	[[nodiscard]] RuntimeStatus CreateWithId(EntityId in_stEntityId);
	[[nodiscard]] Gameplay::PredictionState *Find(EntityId in_stEntityId) noexcept;
	[[nodiscard]] const Gameplay::PredictionState *Find(EntityId in_stEntityId) const noexcept;
	[[nodiscard]] bool Destroy(EntityId in_stEntityId) noexcept;
	[[nodiscard]] std::size_t Count() const noexcept;
	[[nodiscard]] const EntityMap &GetEntities() const noexcept;
	void Clear() noexcept;
};

} // namespace EngineNext::Runtime
