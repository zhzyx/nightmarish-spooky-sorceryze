/**************************************************************************/
/*  ProductionParentGateTests.cpp                                         */
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

#include "tests/test_macros.h"
TEST_FORCE_LINK(ProductionParentGateTests)

#ifdef TOOLS_ENABLED
#include "editor/docks/production/ParentGate.h"

namespace TestProductionParentGate
{
TEST_CASE("[AIChat][ProductionParentGate] Cold opted-in history cannot authorize producer continuation")
{
	CHECK(ProductionParentGate::GetBlockReason(true, false, "", false) == "parent_completion_binding_required");
	CHECK(ProductionParentGate::GetBlockReason(true, false, "continuation_idle", false) == "parent_completion_binding_required");
	CHECK(ProductionParentGate::GetBlockReason(true, false, "running", false) == "parent_completion_binding_required");
	CHECK(ProductionParentGate::GetBlockReason(true, false, "parent_held", false) == "parent_completion_gate_owns_batch");
}

TEST_CASE("[AIChat][ProductionParentGate] Live binding and reserved decisions retain batch ownership")
{
	for (const String &strState : { String("parent_binding"), String("parent_held"), String("parent_preflight") })
	{
		for (bool bHasContract : { false, true })
		{
			CHECK(ProductionParentGate::GetBlockReason(true, bHasContract, strState, false) == "parent_completion_gate_owns_batch");
		}
	}
	// A check can own a running batch before its asynchronous result arrives.
	CHECK(ProductionParentGate::GetBlockReason(true, true, "running", true) == "parent_completion_gate_owns_batch");
}

TEST_CASE("[AIChat][ProductionParentGate] Late producer currentness cannot reopen a held parent")
{
	// Initial proposal may pass; use current state again when its receipt arrives.
	REQUIRE(ProductionParentGate::GetBlockReason(true, true, "running", false).is_empty());
	CHECK_FALSE(ProductionParentGate::GetBlockReason(true, true, "parent_held", false).is_empty());
	CHECK_FALSE(ProductionParentGate::GetBlockReason(true, false, "running", false).is_empty());
	CHECK_FALSE(ProductionParentGate::GetBlockReason(true, true, "running", true).is_empty());
}

TEST_CASE("[AIChat][ProductionParentGate] Legacy parents and bound released parents can continue")
{
	for (const String &strState : { String(), String("continuation_idle"), String("running") })
	{
		CHECK(ProductionParentGate::GetBlockReason(false, false, strState, false).is_empty());
	}
	CHECK(ProductionParentGate::GetBlockReason(true, true, "running", false).is_empty());
	// A held batch remains protected even if a stale caller omits the opt-in bit.
	CHECK_FALSE(ProductionParentGate::GetBlockReason(false, true, "parent_held", false).is_empty());
}
} //namespace TestProductionParentGate
#endif // TOOLS_ENABLED
