/**************************************************************************/
/*  World.cpp                                                             */
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

#include "engine_next/include/EngineNext/Runtime/World.h"

#include <limits>
#include <utility>

namespace EngineNext::Runtime
{

RuntimeStatus World::Create(EntityId &out_stEntityId)
{
	out_stEntityId = EntityId{};
	while (nNextEntityId != 0)
	{
		const EntityId stCandidate{ nNextEntityId };
		if (mapEntities.find(stCandidate) == mapEntities.end())
		{
			mapEntities.emplace(stCandidate, Gameplay::PredictionState{});
			out_stEntityId = stCandidate;
			++nNextEntityId;
			return RuntimeStatus::Ok;
		}
		++nNextEntityId;
	}
	return RuntimeStatus::InvalidState;
}

RuntimeStatus World::CreateWithId(EntityId in_stEntityId)
{
	if (!in_stEntityId.IsValid())
	{
		return RuntimeStatus::InvalidParameter;
	}
	if (mapEntities.find(in_stEntityId) != mapEntities.end())
	{
		return RuntimeStatus::AlreadyExists;
	}
	mapEntities.emplace(in_stEntityId, Gameplay::PredictionState{});
	if (in_stEntityId.nValue >= nNextEntityId)
	{
		nNextEntityId = in_stEntityId.nValue == std::numeric_limits<std::uint64_t>::max() ? 0 : in_stEntityId.nValue + 1;
	}
	return RuntimeStatus::Ok;
}

Gameplay::PredictionState *World::Find(EntityId in_stEntityId) noexcept
{
	const EntityMap::iterator stIterator = mapEntities.find(in_stEntityId);
	return stIterator == mapEntities.end() ? nullptr : &stIterator->second;
}

const Gameplay::PredictionState *World::Find(EntityId in_stEntityId) const noexcept
{
	const EntityMap::const_iterator stIterator = mapEntities.find(in_stEntityId);
	return stIterator == mapEntities.end() ? nullptr : &stIterator->second;
}

bool World::Destroy(EntityId in_stEntityId) noexcept
{
	return mapEntities.erase(in_stEntityId) != 0;
}

std::size_t World::Count() const noexcept
{
	return mapEntities.size();
}

const World::EntityMap &World::GetEntities() const noexcept
{
	return mapEntities;
}

void World::Clear() noexcept
{
	mapEntities.clear();
	nNextEntityId = 1;
}

} // namespace EngineNext::Runtime
