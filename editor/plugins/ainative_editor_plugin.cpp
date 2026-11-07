/**************************************************************************/
/*  ainative_editor_plugin.cpp                                                         */
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

#include "ainative_editor_plugin.h"

#include "core/config/project_settings.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/resource_loader.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/object/script_language.h"
#include "core/os/os.h"
#include "editor/ainative/bundle.gen.h"
#include "editor/docks/editor_dock.h"
#include "editor/docks/editor_dock_manager.h"
#include "editor/file_system/editor_paths.h"
#include "scene/gui/box_container.h"
#include "scene/gui/label.h"

static Error install_ainative_bundle(const String &p_directory) {
	for (const AINativeBundledFile &file : ainative_bundle_files) {
		const String path = p_directory.path_join(file.path);
		if (FileAccess::get_sha256(path) == file.sha256) {
			continue;
		}
		Error err = DirAccess::make_dir_recursive_absolute(path.get_base_dir());
		ERR_FAIL_COND_V(err != OK, err);
		String source;
		for (int i = 0; file.source[i]; i++) {
			source += String::utf8(file.source[i]);
		}
		// Atomic replacement avoids another editor observing partially written
		// scripts. Content hashes bind the whole immutable version directory.
		const String temporary = path + ".tmp-" + itos(OS::get_singleton()->get_process_id());
		Ref<FileAccess> output = FileAccess::open(temporary, FileAccess::WRITE, &err);
		ERR_FAIL_COND_V(output.is_null(), err);
		output->store_string(source);
		output->flush();
		const Error write_error = output->get_error();
		output.unref();
		ERR_FAIL_COND_V(write_error != OK, write_error);
		err = DirAccess::rename_absolute(temporary, path);
		ERR_FAIL_COND_V(err != OK, err);
		ERR_FAIL_COND_V(FileAccess::get_sha256(path) != file.sha256, ERR_FILE_CORRUPT);
	}
	return OK;
}

void AINativeEditorPlugin::_open_workbench() {
	if (initialized || !dock->is_visible_in_tree()) {
		return;
	}
	if (!ClassDB::class_exists("GDScript")) {
		notice->set_text(U"AINative 需要此编辑器启用 GDScript 支持。");
		return;
	}
	const String data = EditorPaths::get_singleton()->get_data_dir().path_join("ainative");
	const String bundle = data.path_join("bundles").path_join(ainative_bundle_version);
	if (install_ainative_bundle(bundle) != OK) {
		notice->set_text(U"无法准备内置 AINative 工具，请检查编辑器数据目录是否可写。");
		return;
	}
	Ref<Script> script = ResourceLoader::load(bundle.path_join("scripts/workbench.gd"), "Script");
	if (script.is_null() || !script->can_instantiate()) {
		notice->set_text(U"无法加载内置 AINative 工作台，请检查编辑器错误日志。");
		return;
	}
	const String project_key = ProjectSettings::get_singleton()->get_resource_path().sha256_text();
	VBoxContainer *workbench = memnew(VBoxContainer);
	workbench->set_name("AINativeWorkbench");
	workbench->set_script(script);
	workbench->set_meta("ainative_builtin", true);
	workbench->set_meta("ainative_tools_dir", bundle.path_join("tools"));
	workbench->set("state_dir", data.path_join("projects").path_join(project_key));
	workbench->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	workbench->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	initialized = true;
	notice->queue_free();
	dock->add_child(workbench);
}

AINativeEditorPlugin::AINativeEditorPlugin() {
	dock = memnew(EditorDock);
	dock->set_name("AINative");
	dock->set_title("AINative");
	dock->set_layout_key("AINativeMainScreen");
	dock->set_icon_name("MeshInstance3D");
	dock->set_available_layouts(EditorDock::DOCK_LAYOUT_MAIN_SCREEN | EditorDock::DOCK_LAYOUT_ALL);
	dock->set_default_slot(EditorDock::DOCK_SLOT_MAIN_SCREEN);
	notice = memnew(Label);
	notice->set_text(U"AINative · Mesh 生成与骨骼绑定");
	dock->add_child(notice);
	dock->connect("visibility_changed", callable_mp(this, &AINativeEditorPlugin::_open_workbench));
	EditorDockManager::get_singleton()->add_dock(dock);
	callable_mp(this, &AINativeEditorPlugin::_open_workbench).call_deferred();
}
