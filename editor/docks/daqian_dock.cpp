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

#include "core/config/engine.h"
#include "core/crypto/crypto_core.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/object/script_language.h"
#include "core/os/os.h"
#include "editor/docks/daqian_board.gen.h"
#include "editor/docks/daqian_scripts.gen.h"
#include "editor/docks/editor_dock.h"
#include "editor/docks/gonggong_process.h"
#include "editor/docks/startup_checks.gen.h"
#include "main/main.h"
#include "scene/gui/box_container.h"
#include "scene/gui/label.h"

#ifdef MACOS_ENABLED
#include "editor/docks/gonggong_validation.gen.h"
#endif

static String editor_script_source(const char *const *p_source) {
	String source;
	for (int i = 0; p_source[i]; i++) {
		source += String::utf8(p_source[i]);
	}
	return source;
}

static Ref<Script> load_editor_script(const String &p_source) {
	Ref<Script> script = Object::cast_to<Script>(ClassDB::instantiate("GDScript"));
	ERR_FAIL_COND_V(script.is_null(), Ref<Script>());
	script->set_source_code(p_source);
	ERR_FAIL_COND_V(script->reload() != OK, Ref<Script>());
	return script;
}

static Ref<Script> load_editor_script(const char *const *p_source) {
	return load_editor_script(editor_script_source(p_source));
}

#if defined(WINDOWS_ENABLED) || defined(MACOS_ENABLED) || defined(LINUXBSD_ENABLED)
static Dictionary load_tianshu_package() {
	OS *os = OS::get_singleton();
	String executable = os->get_executable_path();
	String directory = executable.get_base_dir();
	String filename = "tianshu-ui.json";
	for (const String &slot : { String("self_update_a"), String("self_update_b") }) {
		if (executable.get_file().split(".").has(slot)) {
			filename = "tianshu-ui." + slot + ".json";
		}
	}
#ifdef MACOS_ENABLED
	if (directory.get_file() == "MacOS" && directory.get_base_dir().get_file() == "Contents") {
		directory = directory.get_base_dir().path_join("Resources");
		filename = "tianshu-ui.json";
	}
#endif
	String path = directory.path_join(filename);
	String pin;
	if (os->has_environment("GONGGONG_TIANSHU_UI_PACKAGE") || os->has_environment("GONGGONG_TIANSHU_UI_SHA256")) {
		path = os->get_environment("GONGGONG_TIANSHU_UI_PACKAGE");
		pin = os->get_environment("GONGGONG_TIANSHU_UI_SHA256").to_lower();
		ERR_FAIL_COND_V_MSG(!path.is_absolute_path() || path.contains("://") || pin.length() != 64 || !pin.is_valid_hex_number(false), Dictionary(), "Tianshu UI requires an absolute filesystem path and a SHA-256 pin.");
	}
	// Bypass project packs. Verify and compile the same bytes (one open).
	Ref<FileAccess> file = FileAccess::open(path, FileAccess::READ | FileAccess::SKIP_PACK);
	ERR_FAIL_COND_V_MSG(file.is_null(), Dictionary(), "Tianshu UI package missing: " + path);
	uint64_t size = file->get_length();
	ERR_FAIL_COND_V_MSG(size == 0 || size > 4 * 1024 * 1024, Dictionary(), "Invalid Tianshu UI package size.");
	Vector<uint8_t> bytes = file->get_buffer(size);
	ERR_FAIL_COND_V((uint64_t)bytes.size() != size, Dictionary());
	if (!pin.is_empty()) {
		uint8_t digest[32];
		ERR_FAIL_COND_V(CryptoCore::sha256(bytes.ptr(), bytes.size(), digest) != OK, Dictionary());
		ERR_FAIL_COND_V_MSG(String::hex_encode_buffer(digest, 32) != pin, Dictionary(), "Tianshu UI package pin mismatch.");
	}
	Variant envelope = JSON::parse_string(String::utf8((const char *)bytes.ptr(), bytes.size()));
	ERR_FAIL_COND_V_MSG(envelope.get_type() != Variant::DICTIONARY, Dictionary(), "Invalid Tianshu UI package.");
	Dictionary manifest = envelope;
	String payload = manifest.get("payload", "");
	ERR_FAIL_COND_V_MSG(payload.is_empty() || payload.sha256_text() != String(manifest.get("sha256", "")), Dictionary(), "Tianshu UI payload checksum mismatch.");
	Variant parsed = JSON::parse_string(payload);
	ERR_FAIL_COND_V(parsed.get_type() != Variant::DICTIONARY, Dictionary());
	Dictionary data = parsed;
	ERR_FAIL_COND_V_MSG(data.get("abi", "") != Variant("tianshu-graph/1"), Dictionary(), "Incompatible Tianshu UI package ABI.");
	for (const char *field : { "version", "graph_layout", "issue_graph" }) {
		Variant value = data.get(field, Variant());
		ERR_FAIL_COND_V_MSG(value.get_type() != Variant::STRING || String(value).strip_edges().is_empty(), Dictionary(), "Incomplete Tianshu UI package.");
	}
	return data;
}
#endif

#ifdef MACOS_ENABLED
void install_gonggong_startup_validation(Node *p_editor) {
	if (Engine::get_singleton()->is_recovery_mode_hint() || Main::is_cmdline_tool()) {
		return;
	}
	Ref<Script> validation = load_editor_script(daqian_macos_validation);
	Ref<Script> startup = load_editor_script(daqian_silent_validation);
	ERR_FAIL_COND(validation.is_null() || startup.is_null());
	Node *coordinator = memnew(Node);
	coordinator->set_name("SilentValidation");
	coordinator->set_script(startup);
	Node *preset = memnew(Node);
	preset->set_name("GongGongStartupValidation");
	preset->set_script(validation);
	preset->set("probe_source", editor_script_source(daqian_daqian_ai_entry));
	coordinator->add_child(preset);
	coordinator->set("entry_validation", preset);
	p_editor->add_child(coordinator);
}
#endif

Node *create_gonggong_startup_checks() {
	Ref<Script> script = load_editor_script(daqian_startup_checks);
	Ref<Script> git = load_editor_script(daqian_startup_git);
	ERR_FAIL_COND_V(script.is_null() || git.is_null(), nullptr);
	Node *checks = memnew(Node);
	checks->set_name("StartupConfigurationChecks");
	checks->set_script(script);
	checks->set("git_script", git);
	checks->set("git_helper_source", editor_script_source(daqian_startup_git_helper));
	checks->set("automatic_enabled", !Engine::get_singleton()->is_recovery_mode_hint() && !Main::is_cmdline_tool());
	return checks;
}

EditorDock *create_daqian_dock() {
	EditorDock *dock = memnew(EditorDock);
	dock->set_name("Daqian");
	dock->set_title(U"天枢");
	dock->set_layout_key("DaqianMainScreen");
	dock->set_icon_name("StarryNight");
	dock->set_available_layouts(EditorDock::DOCK_LAYOUT_MAIN_SCREEN | EditorDock::DOCK_LAYOUT_ALL);
	dock->set_default_slot(EditorDock::DOCK_SLOT_MAIN_SCREEN);
#ifndef MACOS_ENABLED
	Ref<Script> silent_validation = load_editor_script(daqian_silent_validation);
	if (silent_validation.is_valid()) {
		Node *probe = memnew(Node);
		probe->set_name("SilentValidation");
		probe->set_script(silent_validation);
		dock->add_child(probe);
	}
#endif
	Ref<Script> rules = load_editor_script(daqian_graph_rules);
#if defined(WINDOWS_ENABLED) || defined(MACOS_ENABLED) || defined(LINUXBSD_ENABLED)
	Ref<Script> layout;
	Ref<Script> graph;
	Dictionary package = load_tianshu_package();
	if (!package.is_empty()) {
		layout = load_editor_script(String(package["graph_layout"]));
		graph = load_editor_script(String(package["issue_graph"]));
	}
#else
	Ref<Script> layout = load_editor_script(daqian_graph_layout);
	Ref<Script> graph = load_editor_script(daqian_issue_graph);
#endif
	Ref<Script> details = load_editor_script(daqian_operation_details);
	Ref<Script> inspector = load_editor_script(daqian_issue_inspector);
	Ref<Script> canvas = load_editor_script(daqian_canvas_context);
	Ref<Script> workspace = load_editor_script(daqian_workspace);
	Ref<Script> spatial = load_editor_script(daqian_spatial_workbench);
	Ref<Script> models = load_editor_script(daqian_model_settings);
	if (spatial.is_null() || inspector.is_null() || details.is_null() || canvas.is_null() || rules.is_null() || layout.is_null() || graph.is_null() || workspace.is_null() || models.is_null()) {
		Label *message = memnew(Label);
		message->set_text(U"加载天枢失败，请核对编辑器的 天枢业务包、GDScript 支持及错误日志。");
		dock->add_child(message);
		return dock;
	}
	VBoxContainer *content = memnew(VBoxContainer);
	content->set_name("DaqianWorkspace");
	content->set_script(workspace);
	content->set("process_stopper", callable_mp_static(&stop_gonggong_process));
	content->set("board_bundle_base64", editor_script_source(daqian_board_base64));
	content->set("board_bundle_sha256", daqian_board_sha256);
	content->set("details_script", details);
	content->set("inspector_script", inspector);
	content->set("canvas_script", canvas);
	content->set("spatial_script", spatial);
	content->set_meta("unified_settings", true);
	content->set("rules", rules);
	content->set("graph_layout", layout);
	content->set("graph_script", graph);
	content->set("models_script", models);
	content->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	content->set_h_size_flags(Control::SIZE_EXPAND_FILL);
	dock->add_child(content);
	return dock;
}
