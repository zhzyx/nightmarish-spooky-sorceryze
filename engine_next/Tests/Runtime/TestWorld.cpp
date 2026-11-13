/**************************************************************************/
/*  TestWorld.cpp                                                         */
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

#include "engine_next/Tests/TestFramework.h"

#include "engine_next/include/EngineNext/Runtime/World.h"

ENGINE_NEXT_TEST("World creates stable identifiers and explicit entity lifetimes")
{
	EngineNext::Runtime::World stWorld;
	EngineNext::Runtime::EntityId stFirst;
	EngineNext::Runtime::EntityId stSecond;
	ENGINE_NEXT_CHECK_EQ(stWorld.Create(stFirst), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stWorld.Create(stSecond), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stFirst.IsValid());
	ENGINE_NEXT_CHECK(stSecond.IsValid());
	ENGINE_NEXT_CHECK(stFirst != stSecond);
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 2ULL);
	ENGINE_NEXT_CHECK_EQ(stWorld.CreateWithId({ 10 }), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stWorld.CreateWithId({ 10 }), EngineNext::Runtime::RuntimeStatus::AlreadyExists);
	ENGINE_NEXT_CHECK_EQ(stWorld.CreateWithId({}), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(stWorld.Create(stSecond), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stSecond.nValue, 11ULL);

	EngineNext::Gameplay::PredictionState *pState = stWorld.Find(stFirst);
	ENGINE_NEXT_CHECK(pState != nullptr);
	pState->vPosition.fX = 3.0F;
	ENGINE_NEXT_CHECK_FLOAT(stWorld.Find(stFirst)->vPosition.fX, 3.0F);
	ENGINE_NEXT_CHECK(stWorld.Destroy(stFirst));
	ENGINE_NEXT_CHECK(!stWorld.Destroy(stFirst));
	ENGINE_NEXT_CHECK(stWorld.Find(stFirst) == nullptr);

	ENGINE_NEXT_CHECK_EQ(stWorld.CreateWithId({ 3 }), EngineNext::Runtime::RuntimeStatus::Ok);
	std::uint64_t nPrevious = 0;
	for (const std::pair<const EngineNext::Runtime::EntityId, EngineNext::Gameplay::PredictionState> &stEntry : stWorld.GetEntities())
	{
		ENGINE_NEXT_CHECK(stEntry.first.nValue >= nPrevious);
		nPrevious = stEntry.first.nValue;
	}
	stWorld.Clear();
	ENGINE_NEXT_CHECK_EQ(stWorld.Count(), 0ULL);
	ENGINE_NEXT_CHECK_EQ(stWorld.Create(stFirst), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stFirst.nValue, 1ULL);
}
