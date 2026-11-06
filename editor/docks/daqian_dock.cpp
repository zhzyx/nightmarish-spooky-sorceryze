/**************************************************************************/
/*  daqian_dock.cpp                                                       */
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

#include "daqian_dock.h"

#include "core/object/class_db.h"
#include "core/object/script_language.h"
#include "editor/docks/daqian_scripts.gen.h"
#include "editor/docks/editor_dock.h"
#include "scene/gui/box_container.h"
#include "scene/gui/label.h"

static Ref<Script> load_editor_script(const char *const *p_source) {
	Ref<Script> script = Object::cast_to<Script>(ClassDB::instantiate("GDScript"));
	ERR_FAIL_COND_V(script.is_null(), Ref<Script>());
	String source;
	for (int i = 0; p_source[i]; i++) {
		source += String::utf8(p_source[i]);
	}
	script->set_source_code(source);
	ERR_FAIL_COND_V(script->reload() != OK, Ref<Script>());
	return script;
}

EditorDock *create_daqian_dock() {
	EditorDock *dock = memnew(EditorDock);
	dock->set_name("Daqian");
	dock->set_title(U"大千");
	dock->set_layout_key("DaqianMainScreen");
	dock->set_icon_name("GraphEdit");
	dock->set_available_layouts(EditorDock::DOCK_LAYOUT_MAIN_SCREEN | EditorDock::DOCK_LAYOUT_ALL);
	dock->set_default_slot(EditorDock::DOCK_SLOT_MAIN_SCREEN);
	Ref<Script> silent_validation = load_editor_script(daqian_silent_validation);
	if (silent_validation.is_valid()) {
		Node *probe = memnew(Node);
		probe->set_name("SilentValidation");
		probe->set_script(silent_validation);
		dock->add_child(probe);
	}
	Ref<Script> rules = load_editor_script(daqian_graph_rules);
	Ref<Script> graph = load_editor_script(daqian_issue_graph);
	Ref<Script> workspace = load_editor_script(daqian_workspace);
	Ref<Script> models = load_editor_script(daqian_model_settings);
	if (rules.is_null() || graph.is_null() || workspace.is_null() || models.is_null()) {
		Label *message = memnew(Label);
		message->set_text(U"加载大千失败，请核对编辑器的 GDScript 支持及错误日志。");
		dock->add_child(message);
		return dock;
	}
	VBoxContainer *content = memnew(VBoxContainer);
	content->set_name("DaqianWorkspace");
	content->set_script(workspace);
	content->set("rules", rules);
	content->set("graph_script", graph);
	content->set("models_script", models);
	content->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	content->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	dock->add_child(content);
	return dock;
}
