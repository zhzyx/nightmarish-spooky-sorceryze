/**************************************************************************/
/*  test_input_semantic.cpp                                   */
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

#include "core/input/input.h"
#include "core/input/input_map.h"
#include "tests/test_macros.h"

TEST_FORCE_LINK(test_input_semantic)

namespace TestInputSemantic {
TEST_CASE("[SceneTree][Input][Semantic] Debugger source release preserves project API and physical input") {
	Input *input = Input::get_singleton();
	InputMap *map = InputMap::get_singleton();
	const StringName name = "__semantic_action_fixture";
	map->add_action(name);
	input->semantic_action_press(name, 0.5f);
	CHECK(input->is_action_pressed(name));
	CHECK(input->get_action_strength(name) == doctest::Approx(0.5f));
	input->action_press(name, 0.8f);
	input->semantic_action_release(name);
	CHECK(input->is_action_pressed(name));
	CHECK(input->get_action_strength(name) == doctest::Approx(0.8f));
	input->action_release(name);
	CHECK_FALSE(input->is_action_pressed(name));
	Ref<InputEventAction> physical;
	physical.instantiate();
	physical->set_action(name);
	physical->set_pressed(true);
	physical->set_strength(0.7f);
	physical->set_device(12);
	input->parse_input_event(physical);
	input->flush_buffered_events();
	input->semantic_action_press(name, 1.0f);
	input->semantic_action_release(name);
	CHECK(input->is_action_pressed(name));
	CHECK(input->get_action_strength(name) == doctest::Approx(0.7f));
	Ref<InputEventAction> released;
	released.instantiate();
	released->set_action(name);
	released->set_device(12);
	released->set_pressed(false);
	input->parse_input_event(released);
	input->flush_buffered_events();
	CHECK_FALSE(input->is_action_pressed(name));
	input->semantic_action_press(name, 1.0f);
	map->erase_action(name);
	input->semantic_action_release(name);
}
} //namespace TestInputSemantic
