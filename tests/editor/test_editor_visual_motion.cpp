/**************************************************************************/
/*  test_editor_visual_motion.cpp                                         */
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

TEST_FORCE_LINK(test_editor_visual_motion)

#ifdef TOOLS_ENABLED
#include "editor/file_system/editor_paths.h"
#include "editor/inspector/editor_inspector.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/box_container.h"
#include "scene/gui/control.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

namespace TestEditorVisualMotion {
TEST_CASE("[SceneTree][EditorVisual] Inspector reversals and reduced motion") {
	// Run in the runner's private self-contained editor, never the installed editor.
	const bool own_settings = EditorSettings::get_singleton() == nullptr;
	const bool own_paths = EditorPaths::get_singleton() == nullptr;
	if (own_paths) {
		EditorPaths::create();
	}
	if (own_settings) {
		EditorSettings::create();
	}
	EditorSettings *settings = EditorSettings::get_singleton();
	const Variant original = settings->get("interface/theme/reduce_motion");
	settings->set("interface/theme/reduce_motion", false);
	SceneTree *tree = SceneTree::get_singleton();
	Node *target = memnew(Node);
	EditorInspectorSection *section = memnew(EditorInspectorSection);
	section->setup("visual_probe", "Display", target, Color(0.5, 0.5, 0.5), true);
	Control *content = memnew(Control);
	content->set_custom_minimum_size(Size2(240, 160));
	section->get_vbox()->add_child(content);
	tree->get_root()->add_child(section);
	section->unfold();
	tree->process(0.25);
	const real_t expanded = section->get_minimum_size().y;
	section->fold();
	tree->process(0.06);
	const real_t middle = section->get_minimum_size().y;
	CHECK(middle < expanded);
	CHECK(middle > expanded - 160);
	CHECK_FALSE(content->is_visible_in_tree());
	section->unfold();
	CHECK(Math::is_equal_approx(section->get_minimum_size().y, middle));
	tree->process(0.25);
	CHECK(Math::is_equal_approx(section->get_minimum_size().y, expanded));
	CHECK_FALSE(section->is_clipping_contents());
	settings->set("interface/theme/reduce_motion", true);
	section->fold();
	CHECK(section->get_minimum_size().y < middle);
	memdelete(section);
	memdelete(target);
	settings->set("interface/theme/reduce_motion", original);
	if (own_settings) {
		EditorSettings::destroy();
	}
	if (own_paths) {
		EditorPaths::free();
	}
}
} // namespace TestEditorVisualMotion
#endif
