/**************************************************************************/
/*  ai_chat_editor_scene_completion.cpp                                   */
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

#include "ai_chat_editor_scene_completion.h"

#include "core/config/project_settings.h"
#include "core/crypto/crypto_core.h"
#include "core/io/config_file.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/io/marshalls.h"
#include "core/object/class_db.h"
#include "core/object/undo_redo.h"
#include "core/version.h"
#include "editor/docks/ai_chat_editor_scene_actions.h"
#include "editor/editor_interface.h"
#include "editor/editor_undo_redo_manager.h"
#include "editor/export/editor_export.h"
#include "editor/export/editor_export_platform_pc.h"
#include "editor/export/editor_export_plugin.h"
#include "editor/export/editor_export_preset.h"
#include "editor/file_system/editor_file_system.h"
#include "editor/file_system/editor_paths.h"
#include "scene/main/node.h"
#include "scene/resources/compressed_texture.h"
#include "scene/resources/resource_format_text.h"
#include "servers/text/text_server.h"

namespace {
Dictionary result(bool p_ok, const String &p_error = String()) {
	Dictionary r;
	r["ok"] = p_ok;
	if (!p_error.is_empty()) {
		r["error"] = p_error;
	}
	return r;
}

bool same(const Variant &p_a, const Variant &p_b) {
	if (p_a.is_num() && p_b.is_num()) {
		return double(p_a) == double(p_b);
	}
	if (p_a.get_type() != p_b.get_type()) {
		return false;
	}
	if (p_a.get_type() == Variant::DICTIONARY) {
		const Dictionary a = p_a, b = p_b;
		if (a.size() != b.size()) {
			return false;
		}
		for (const Variant &key : a.keys()) {
			if (!b.has(key) || !same(a[key], b[key])) {
				return false;
			}
		}
		return true;
	}
	if (p_a.get_type() == Variant::ARRAY) {
		const Array a = p_a, b = p_b;
		if (a.size() != b.size()) {
			return false;
		}
		for (int i = 0; i < a.size(); i++) {
			if (!same(a[i], b[i])) {
				return false;
			}
		}
		return true;
	}
	return p_a == p_b;
}

// Credential-related options must be absent/disabled, with exact Variant
// types. In particular, a nonempty array of empty strings is still nonempty.
bool empty_credential_option(const Variant &p_value) {
	switch (p_value.get_type()) {
		case Variant::NIL:
			return true;
		case Variant::BOOL:
			return !bool(p_value);
		case Variant::INT:
			return int64_t(p_value) == 0;
		case Variant::FLOAT:
			return double(p_value) == 0.0;
		case Variant::STRING:
			return String(p_value).is_empty();
		case Variant::STRING_NAME:
			return StringName(p_value) == StringName();
		case Variant::ARRAY:
			return Array(p_value).is_empty();
		case Variant::DICTIONARY:
			return Dictionary(p_value).is_empty();
		case Variant::PACKED_BYTE_ARRAY:
			return PackedByteArray(p_value).is_empty();
		case Variant::PACKED_INT32_ARRAY:
			return PackedInt32Array(p_value).is_empty();
		case Variant::PACKED_INT64_ARRAY:
			return PackedInt64Array(p_value).is_empty();
		case Variant::PACKED_FLOAT32_ARRAY:
			return PackedFloat32Array(p_value).is_empty();
		case Variant::PACKED_FLOAT64_ARRAY:
			return PackedFloat64Array(p_value).is_empty();
		case Variant::PACKED_STRING_ARRAY:
			return PackedStringArray(p_value).is_empty();
		case Variant::PACKED_VECTOR2_ARRAY:
			return PackedVector2Array(p_value).is_empty();
		case Variant::PACKED_VECTOR3_ARRAY:
			return PackedVector3Array(p_value).is_empty();
		case Variant::PACKED_VECTOR4_ARRAY:
			return PackedVector4Array(p_value).is_empty();
		case Variant::PACKED_COLOR_ARRAY:
			return PackedColorArray(p_value).is_empty();
		default:
			return false;
	}
}

bool file_state(const String &p_path, Dictionary &r_state) {
	if (!AIChatEditorSceneActions::valid_project_path(p_path) || !AIChatEditorSceneCompletion::unlinked(p_path)) {
		return false;
	}
	if (FileAccess::exists(p_path)) {
		Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::READ);
		if (file.is_null() || file->get_length() > 256 * 1024 * 1024) {
			return false;
		}
	}
	r_state[p_path] = FileAccess::exists(p_path) ? FileAccess::get_sha256(p_path) : String();
	return true;
}

// Only host-resolved template inputs may be read outside res://. Their paths
// are hashed into the private manifest and never returned on the model wire.
bool template_input(const String &p_path, String &r_manifest, int &r_count, uint64_t &r_bytes) {
	if (p_path.is_empty()) {
		r_manifest += "missing-template\n";
		return true;
	}
	const String absolute = ProjectSettings::get_singleton()->globalize_path(p_path);
	Ref<DirAccess> dir = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
	String current = absolute.get_base_dir();
	while (!current.is_empty()) {
		if (dir->is_link(current)) {
			return false;
		}
		const String parent = current.get_base_dir();
		if (parent == current) {
			break;
		}
		current = parent;
	}
	if (dir->is_link(absolute)) {
		return false;
	}
	r_manifest += absolute.sha256_text() + "\n";
	if (FileAccess::exists(absolute)) {
		Ref<FileAccess> file = FileAccess::open(absolute, FileAccess::READ);
		if (file.is_null() || ++r_count > 2000 || (r_bytes += file->get_length()) > 256 * 1024 * 1024) {
			return false;
		}
		r_manifest += FileAccess::get_sha256(absolute);
	}
	r_manifest += "\n";
	return true;
}

// Exact native storage graph, never Object::get or script property callbacks.
// The closed class set excludes arbitrary native virtual getters and extensions.
struct ResourceSnapshot {
	HashSet<ObjectID> active;
	int count = 0;
	int bytes = 0;
	bool encode(const Variant &p_value, Variant &r_value, int p_depth = 0) {
		if (p_depth > 12 || ++count > 1024) {
			return false;
		}
		if (p_value.get_type() == Variant::OBJECT) {
			Object *object = p_value;
			if (object && !Object::cast_to<Resource>(object)) {
				return false;
			}
			Ref<Resource> resource = p_value;
			if (resource.is_null()) {
				r_value = Variant();
				return true;
			}
			const String type = resource->get_class();
			if (resource->get_script().get_type() != Variant::NIL || ClassDB::is_gdextension(resource->get_class()) || resource->is_extension_placeholder() || ClassDB::get_api_type(type) != ClassDB::API_CORE || (type != "Gradient" && type != "Curve" && type != "StandardMaterial3D" && type != "ORMMaterial3D" && type != "BoxMesh" && type != "SphereMesh" && type != "StyleBoxFlat" && type != "CompressedTexture2D")) {
				return false;
			}
			const ObjectID id = resource->get_instance_id();
			if (active.has(id)) {
				return false;
			}
			active.insert(id);
			Dictionary fields;
			fields["instance"] = String::num_uint64(uint64_t(id));
			fields["class"] = type;
			const String path = resource->get_path().get_slice("::", 0);
			if (!path.is_empty()) {
				Dictionary source;
				if (!file_state(path, source)) {
					return false;
				}
				fields["file"] = source;
			}
			List<PropertyInfo> properties;
			ClassDB::get_property_list(resource->get_class(), &properties);
			Dictionary storage;
			for (const PropertyInfo &property : properties) {
				if (!(property.usage & PROPERTY_USAGE_STORAGE) || property.name == "script") {
					continue;
				}
				Variant value, encoded;
				if (!resource->get_native(property.name, value) || !encode(value, encoded, p_depth + 1)) {
					return false;
				}
				storage[property.name] = encoded;
			}
			// Compressed textures store their immutable data in a native imported file.
			if (type == "CompressedTexture2D") {
				Dictionary source;
				if (!AIChatEditorSceneCompletion::resource_input(resource->get_path(), source)) {
					return false;
				}
				fields["source"] = source;
				CompressedTexture2D *texture = Object::cast_to<CompressedTexture2D>(resource.ptr());
				if (texture->get_width() > 4096 || texture->get_height() > 4096) {
					return false;
				}
				Ref<Image> image = texture->CompressedTexture2D::get_image();
				if (image.is_null()) {
					return false;
				}
				const Vector<uint8_t> data = image->get_data();
				if (data.size() > 64 * 1024 * 1024) {
					return false;
				}
				unsigned char hash[32];
				if (CryptoCore::sha256(data.ptr(), data.size(), hash) != OK) {
					return false;
				}
				fields["pixels_sha256"] = String::hex_encode_buffer(hash, 32);
				fields["image_format"] = int(image->get_format());
				fields["image_mipmaps"] = image->has_mipmaps();
			}
			List<StringName> metadata;
			resource->get_meta_list(&metadata);
			if (metadata.size() > 256) {
				return false;
			}
			Dictionary encoded_metadata;
			for (const StringName &key : metadata) {
				if (String(key).length() > 8192) {
					return false;
				}
				Variant encoded;
				if (!encode(resource->get_meta(key), encoded, p_depth + 1)) {
					return false;
				}
				encoded_metadata[key] = encoded;
			}
			fields["metadata"] = encoded_metadata;
			fields["storage"] = storage;
			active.erase(id);
			r_value = fields;
		} else if (p_value.get_type() == Variant::ARRAY) {
			Array encoded;
			const Array array = p_value;
			if (array.size() > 256) {
				return false;
			}
			for (const Variant &value : array) {
				Variant item;
				if (!encode(value, item, p_depth + 1)) {
					return false;
				}
				encoded.push_back(item);
			}
			r_value = encoded;
		} else if (p_value.get_type() == Variant::DICTIONARY) {
			Array encoded;
			const Dictionary dictionary = p_value;
			if (dictionary.size() > 256) {
				return false;
			}
			for (const Variant &key : dictionary.keys()) {
				Variant encoded_key, encoded_value;
				if (!encode(key, encoded_key, p_depth + 1) || !encode(dictionary[key], encoded_value, p_depth + 1)) {
					return false;
				}
				Array pair;
				pair.push_back(encoded_key);
				pair.push_back(encoded_value);
				encoded.push_back(pair);
			}
			r_value = encoded;
		} else {
			if (p_value.get_type() == Variant::CALLABLE || p_value.get_type() == Variant::SIGNAL || p_value.get_type() == Variant::RID) {
				return false;
			}
			// Encode only atomic native Variants, preserving type and exact numeric
			// payload (including negative zero); no object serialization is possible.
			int elements = 0;
			switch (p_value.get_type()) {
				case Variant::STRING:
					if (String(p_value).length() > 8192) {
						return false;
					}
					break;
				case Variant::PACKED_BYTE_ARRAY:
					elements = PackedByteArray(p_value).size();
					break;
				case Variant::PACKED_INT32_ARRAY:
					elements = PackedInt32Array(p_value).size();
					break;
				case Variant::PACKED_INT64_ARRAY:
					elements = PackedInt64Array(p_value).size();
					break;
				case Variant::PACKED_FLOAT32_ARRAY:
					elements = PackedFloat32Array(p_value).size();
					break;
				case Variant::PACKED_FLOAT64_ARRAY:
					elements = PackedFloat64Array(p_value).size();
					break;
				case Variant::PACKED_STRING_ARRAY: {
					const PackedStringArray strings = p_value;
					if (strings.size() > 256) {
						return false;
					}
					for (const String &item : strings) {
						if (item.length() > 8192) {
							return false;
						}
					}
					elements = strings.size();
				} break;
				case Variant::PACKED_VECTOR2_ARRAY:
					elements = PackedVector2Array(p_value).size();
					break;
				case Variant::PACKED_VECTOR3_ARRAY:
					elements = PackedVector3Array(p_value).size();
					break;
				case Variant::PACKED_VECTOR4_ARRAY:
					elements = PackedVector4Array(p_value).size();
					break;
				case Variant::PACKED_COLOR_ARRAY:
					elements = PackedColorArray(p_value).size();
					break;
				default:
					break;
			}
			if (elements > 256) {
				return false;
			}
			int length = 0;
			if (encode_variant(p_value, nullptr, length, false) != OK || length > 8192 - bytes) {
				return false;
			}
			Vector<uint8_t> buffer;
			buffer.resize(length);
			if (encode_variant(p_value, buffer.ptrw(), length, false) != OK) {
				return false;
			}
			bytes += length;
			r_value = String::hex_encode_buffer(buffer.ptr(), length);
		}
		return JSON::stringify(r_value).utf8().length() <= 12288;
	}
};

// Hash bounded files without loading resources or invoking plugin dependencies.
bool input_tree(const String &p_path, const String &p_output, String &r_manifest, int &r_count, uint64_t &r_bytes, int p_depth = 0) {
	Ref<DirAccess> dir = DirAccess::open(p_path);
	if (dir.is_null() || p_depth > 32) {
		return false;
	}
	PackedStringArray entries;
	dir->list_dir_begin();
	for (String entry = dir->get_next(); !entry.is_empty(); entry = dir->get_next()) {
		if (entry != "." && entry != ".." && entry != ".godot" && entry != ".git") {
			entries.push_back(entry);
		}
	}
	dir->list_dir_end();
	entries.sort();
	for (const String &entry : entries) {
		const String path = p_path.path_join(entry);
		if (!AIChatEditorSceneCompletion::unlinked(path)) {
			return false;
		}
		if (path == p_output) {
			continue;
		}
		if (++r_count > 2000 || dir->is_link(entry)) {
			return false;
		}
		if (dir->dir_exists(entry)) {
			if (!input_tree(path, p_output, r_manifest, r_count, r_bytes, p_depth + 1)) {
				return false;
			}
		} else {
			Ref<FileAccess> file = FileAccess::open(path, FileAccess::READ);
			if (file.is_null() || (r_bytes += file->get_length()) > 256 * 1024 * 1024) {
				return false;
			}
			r_manifest += path + "\n" + FileAccess::get_sha256(path) + "\n";
			if (EditorFileSystem::get_singleton()) {
				r_manifest += String::num_uint64(EditorFileSystem::get_singleton()->get_file_uid(path)) + "\n";
			}
			if (path.get_extension() == "gdextension") {
				Ref<ConfigFile> extension;
				extension.instantiate();
				if (extension->load(path) != OK) {
					return false;
				}
				for (const String &section : { "libraries", "dependencies" }) {
					if (!extension->has_section(section)) {
						continue;
					}
					for (const String &key : extension->get_section_keys(section)) {
						const Variant value = extension->get_value(section, key);
						Array dependencies;
						if (section == "libraries" && value.get_type() == Variant::STRING) {
							dependencies.push_back(value);
						} else if (section == "dependencies" && value.get_type() == Variant::DICTIONARY) {
							dependencies = Dictionary(value).keys();
						} else {
							return false;
						}
						for (const Variant &dependency : dependencies) {
							if (dependency.get_type() != Variant::STRING) {
								return false;
							}
							String source = dependency;
							if (!source.is_absolute_path()) {
								source = path.get_base_dir().path_join(source).simplify_path();
							}
							if (!AIChatEditorSceneActions::valid_project_path(source) || !AIChatEditorSceneCompletion::unlinked(source)) {
								return false;
							}
						}
					}
				}
			}
			if (path.get_extension() == "import") {
				Ref<ConfigFile> config;
				config.instantiate();
				if (config->load(path) != OK) {
					return false;
				}
				for (const String &key : config->get_section_keys("remap")) {
					if (key == "path" || key.begins_with("path.")) {
						const String remap = config->get_value("remap", key, "");
						if (!AIChatEditorSceneActions::valid_project_path(remap) || !AIChatEditorSceneCompletion::unlinked(remap) || !FileAccess::exists(remap)) {
							return false;
						}
						Ref<FileAccess> imported = FileAccess::open(remap, FileAccess::READ);
						if (imported.is_null() || ++r_count > 2000 || (r_bytes += imported->get_length()) > 256 * 1024 * 1024) {
							return false;
						}
						r_manifest += remap + "\n" + FileAccess::get_sha256(remap) + "\n";
					}
				}
			}
		}
	}
	return true;
}
} // namespace

bool AIChatEditorSceneCompletion::supports(const String &p_action) {
	return p_action == "scene_import_resource" || p_action == "scene_export_resource" || p_action == "project_export";
}

bool AIChatEditorSceneCompletion::unlinked(const String &p_path) {
	ProjectSettings *settings = ProjectSettings::get_singleton();
	Ref<DirAccess> dir = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
	if (!settings || dir.is_null()) {
		return false;
	}
	String path = settings->get_resource_path();
	if (dir->is_link(path)) {
		return false;
	}
	for (const String &part : p_path.trim_prefix("res://").split("/")) {
		path = path.path_join(part);
		if (dir->is_link(path)) {
			return false;
		}
	}
	return true;
}

bool AIChatEditorSceneCompletion::resource_snapshot(const Variant &p_resource, Dictionary &r_state) {
	ResourceSnapshot snapshot;
	Variant value;
	if (!snapshot.encode(p_resource, value)) {
		return false;
	}
	r_state["content"] = value;
	return true;
}

bool AIChatEditorSceneCompletion::resource_input(const String &p_path, Dictionary &r_state) {
	if (!file_state(p_path, r_state) || !FileAccess::exists(p_path)) {
		return false;
	}
	const String extension = p_path.get_extension().to_lower();
	if (extension == "tres") {
		Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::READ);
		if (file.is_null() || file->get_length() > 1024 * 1024) {
			return false;
		}
		const String text = file->get_as_text();
		// Self-contained native data only. This refuses script/custom resources,
		// embedded code and unbound external-resource dependency loading.
		if (text.contains("[ext_resource") || text.contains("[sub_resource") || text.contains("script") || text.contains("Resource(")) {
			return false;
		}
		for (const String &type : { "Gradient", "Curve", "StandardMaterial3D", "ORMMaterial3D", "BoxMesh", "SphereMesh", "StyleBoxFlat" }) {
			if (text.begins_with("[gd_resource type=\"" + type + "\"")) {
				return true;
			}
		}
		return false;
	}
	if (extension != "png" && extension != "jpg" && extension != "jpeg" && extension != "webp") {
		return false;
	}
	const String import_path = p_path + ".import";
	if (!file_state(import_path, r_state) || !FileAccess::exists(import_path)) {
		return false;
	}
	Ref<ConfigFile> config;
	config.instantiate();
	if (config->load(import_path) != OK || config->get_value("remap", "importer", "") != Variant("texture")) {
		return false;
	}
	const PackedStringArray files = config->get_value("deps", "dest_files", PackedStringArray());
	if (files.is_empty() || files.size() > 16) {
		return false;
	}
	for (const String &path : files) {
		if (!path.begins_with("res://.godot/imported/") || !file_state(path, r_state) || !FileAccess::exists(path)) {
			return false;
		}
	}
	return true;
}

Dictionary AIChatEditorSceneCompletion::perform(const Dictionary &p_args, bool p_confirmed) {
	const String action = p_args.get("action", "");
	EditorInterface *editor = EditorInterface::get_singleton();
	EditorFileSystem *filesystem = EditorFileSystem::get_singleton();
	if (!supports(action) || !editor || !filesystem) {
		return result(false, "editor_unavailable");
	}
	if (filesystem->is_scanning() || filesystem->is_importing() || editor->is_playing_scene()) {
		return result(false, "editor_busy");
	}
	const bool importing = action == "scene_import_resource", exporting = action == "project_export";
	Dictionary proposal = p_args.duplicate(true);
	proposal.erase("expected_old_value");
	proposal.erase("expected_target_instance");
	Dictionary state;
	state["proposal"] = proposal;
	state["root"] = editor->get_edited_scene_root() ? int64_t(editor->get_edited_scene_root()->get_instance_id()) : 0;
	state["running"] = false;
	Node *edited_root = editor->get_edited_scene_root();
	EditorUndoRedoManager *undo = EditorUndoRedoManager::get_singleton();
	if (edited_root && undo) {
		const int history_id = undo->get_history_id_for_object(edited_root);
		state["scene_version"] = undo->has_history(history_id) ? int64_t(undo->get_history_undo_redo(history_id)->get_version()) : 0;
	}
	state["history"] = AIChatEditorSceneActions::history_state(edited_root);
	if (Dictionary(state["history"]).has("unavailable")) {
		return result(false, "history_snapshot_capacity");
	}
	String destination;
	Ref<Resource> resource;
	Ref<EditorExportPreset> preset;
	if (importing) {
		const Variant path = p_args.get("resource_path", Variant());
		if (path.get_type() != Variant::STRING || !file_state(path, state) || !FileAccess::exists(path)) {
			return result(false, "invalid_project_path");
		}
		const String extension = String(path).get_extension().to_lower();
		if (extension != "png" && extension != "jpg" && extension != "jpeg" && extension != "webp") {
			return result(false, "unsupported_import_type");
		}
		if (!file_state(String(path) + ".import", state)) {
			return result(false, "linked_project_path");
		}
	} else {
		const Variant path = p_args.get("destination", Variant());
		if (path.get_type() != Variant::STRING || !file_state(path, state)) {
			return result(false, "invalid_project_path");
		}
		destination = path;
		if (DirAccess::exists(destination)) {
			String manifest;
			int count = 0;
			uint64_t bytes = 0;
			if (!input_tree(destination, String(), manifest, count, bytes)) {
				return result(false, "destination_capacity_or_link");
			}
			state["destination_directory_sha256"] = manifest.sha256_text();
		}
		if (!DirAccess::exists(destination.get_base_dir())) {
			return result(false, "destination_directory_missing");
		}
		if (exporting) {
			const Variant name = p_args.get("preset", Variant());
			EditorExport *exports = EditorExport::get_singleton();
			if (name.get_type() != Variant::STRING || !exports || p_args.get("debug", false).get_type() != Variant::BOOL) {
				return result(false, "invalid_export_preset");
			}
			for (int i = 0; i < exports->get_export_preset_count(); i++) {
				if (exports->get_export_preset(i)->get_name() == String(name)) {
					if (preset.is_valid()) {
						return result(false, "ambiguous_export_preset");
					}
					preset = exports->get_export_preset(i);
				}
			}
			if (preset.is_null() || preset->get_platform().is_null() || preset->get_script().get_type() != Variant::NIL || ClassDB::is_gdextension(preset->get_class()) || preset->is_extension_placeholder() || ClassDB::is_gdextension(preset->get_platform()->get_class()) || preset->get_platform()->is_extension_placeholder() || preset->get_platform()->get_script().get_type() != Variant::NIL) {
				return result(false, "export_preset_unavailable");
			}
			const String format = p_args.get("format", "project");
			if ((format != "project" && format != "pack" && format != "zip") || (format == "pack" && destination.get_extension() != "pck") || (format == "zip" && destination.get_extension() != "zip")) {
				return result(false, "invalid_export_format");
			}
			// Encryption and signing may consume external/environment credentials.
			// Keep this action local and unsigned without changing the preset.
			if (preset->get_enc_pck() || preset->get_enc_directory()) {
				return result(false, "credential_export_not_supported");
			}
			Array plugins;
			for (const Ref<EditorExportPlugin> &plugin : exports->get_export_plugins()) {
				if (plugin->get_script().get_type() != Variant::NIL || ClassDB::is_gdextension(plugin->get_class()) || plugin->is_extension_placeholder() || ClassDB::get_api_type(plugin->get_class()) == ClassDB::API_EXTENSION) {
					return result(false, "unsupported_export_plugin_snapshot");
				}
				plugins.push_back(String::num_uint64(uint64_t(plugin->get_instance_id())));
			}
			state["export_plugins"] = plugins;
			Dictionary values;
			for (const KeyValue<StringName, Variant> &option : preset->get_values()) {
				const String key = option.key;
				if ((key.contains("codesign") || key.contains("notarization") || key.contains("keystore") || key.contains("password") || key.contains("certificate")) && !empty_credential_option(option.value)) {
					return result(false, "credential_export_not_supported");
				}
				if (key.contains("custom_template") && !String(option.value).is_empty() && (!AIChatEditorSceneActions::valid_project_path(option.value) || !unlinked(option.value))) {
					return result(false, "external_export_template");
				}
				values[key] = option.value;
			}
			state["preset_instance"] = String::num_uint64(uint64_t(preset->get_instance_id()));
			state["preset_values_sha256"] = JSON::stringify(values, "", true).sha256_text();
			state["preset_filter"] = int(preset->get_export_filter());
			state["include_filter"] = preset->get_include_filter();
			state["exclude_filter"] = preset->get_exclude_filter();
			state["platform"] = preset->get_platform()->get_name();
			PackedStringArray selected;
			for (const String &file : preset->get_selected_files()) {
				selected.push_back(file);
			}
			selected.sort();
			Dictionary filters;
			filters["selected"] = selected;
			filters["customized"] = preset->get_customized_files();
			filters["features"] = preset->get_custom_features();
			filters["dedicated_server"] = preset->is_dedicated_server();
			filters["script_export_mode"] = int(preset->get_script_export_mode());
			state["preset_filter_sha256"] = JSON::stringify(filters, "", true).sha256_text();
			state["selected_files"] = selected.size();
			if (!file_state("res://export_presets.cfg", state)) {
				return result(false, "linked_project_path");
			}
			String manifest;
			int count = 0;
			uint64_t bytes = 0;
			if (!input_tree("res://", destination, manifest, count, bytes)) {
				return result(false, "project_input_capacity_or_link");
			}
			// Native export consumes imported remaps, customization caches and
			// global class/extension metadata. Editor receipts and shader caches are
			// deliberately outside this closure, so approval cannot invalidate itself.
			const String data = ProjectSettings::get_singleton()->get_project_data_path();
			if (!data.begins_with("res://") || !unlinked(data)) {
				return result(false, "external_export_cache");
			}
			for (const String &directory : { "imported" }) {
				const String cache = data.path_join(directory);
				if (DirAccess::exists(cache) && !input_tree(cache, destination, manifest, count, bytes)) {
					return result(false, "project_input_capacity_or_link");
				}
			}
			for (const String &name : { "global_script_class_cache.cfg", "extension_list.cfg", "uid_cache.bin" }) {
				const String cache = data.path_join(name);
				if (!unlinked(cache)) {
					return result(false, "project_input_capacity_or_link");
				}
				manifest += cache + "\n";
				if (FileAccess::exists(cache)) {
					Ref<FileAccess> file = FileAccess::open(cache, FileAccess::READ);
					if (file.is_null() || ++count > 2000 || (bytes += file->get_length()) > 256 * 1024 * 1024) {
						return result(false, "project_input_capacity_or_link");
					}
					manifest += FileAccess::get_sha256(cache);
				}
				manifest += "\n";
			}
			const bool debug = p_args.get("debug", false);
			const String template_key = debug ? "custom_template/debug" : "custom_template/release";
			const String custom_template = String(values.get(template_key, "")).strip_edges();
			String template_path = custom_template;
			const String template_directory = EditorPaths::get_singleton()->get_export_templates_dir().path_join(GODOT_VERSION_FULL_CONFIG);
			if (format == "project") {
				EditorExportPlatformPC *pc = Object::cast_to<EditorExportPlatformPC>(preset->get_platform().ptr());
				if (custom_template.is_empty()) {
					if (pc) {
						template_path = template_directory.path_join(pc->get_template_file_name(debug ? "debug" : "release", values.get("binary_format/architecture", "")));
					} else if (preset->get_platform()->get_name() == "macOS") {
						template_path = template_directory.path_join("macos.zip");
					} else {
						return result(false, "unsupported_platform_template_snapshot");
					}
				}
				if (!template_input(template_path, manifest, count, bytes)) {
					return result(false, "template_input_capacity_or_link");
				}
				if (pc && !template_path.is_empty()) {
					for (const String &suffix : { ".console.exe", "_console.exe", " console.exe", "console.exe" }) {
						if (!template_input(template_path.get_basename() + suffix, manifest, count, bytes)) {
							return result(false, "template_input_capacity_or_link");
						}
					}
					for (const String &suffix : { ".debugsymbols", ".debugsymbols.zip" }) {
						if (!template_input(template_path + suffix, manifest, count, bytes)) {
							return result(false, "template_input_capacity_or_link");
						}
					}
				}
			}
			const String support_name = TextServerManager::get_singleton()->get_primary_interface()->get_support_data_filename();
			if (!support_name.is_empty()) {
				const String support_directory = custom_template.is_empty() ? template_directory : custom_template.get_base_dir();
				if (!template_input(support_directory.path_join(support_name), manifest, count, bytes)) {
					return result(false, "template_input_capacity_or_link");
				}
			}
			state["stable_input_sha256"] = manifest.sha256_text();
			const String export_cache = data.path_join("exported");
			if (DirAccess::exists(export_cache) && !input_tree(export_cache, destination, manifest, count, bytes)) {
				return result(false, "project_input_capacity_or_link");
			}
			state["input_bytes"] = String::num_uint64(bytes);
			state["input_sha256"] = manifest.sha256_text();
			state["input_entries"] = count;
		} else {
			if (destination.get_extension() != "tres") {
				return result(false, "unsupported_resource_destination");
			}
			Node *root = editor->get_edited_scene_root();
			const String target = p_args.get("target", "."), property = p_args.get("property", "");
			if (target.contains("..") || NodePath(target).is_absolute() || NodePath(target).get_subname_count()) {
				return result(false, "invalid_node_path");
			}
			Node *node = root ? root->get_node_or_null(NodePath(target)) : nullptr;
			Variant value;
			if (!node || ClassDB::is_gdextension(node->get_class()) || node->is_extension_placeholder() || ClassDB::get_api_type(node->get_class()) != ClassDB::API_CORE || (property != "texture" && property != "mesh" && property != "material_override" && property != "gradient") || !node->get_native(property, value)) {
				return result(false, "resource_unavailable");
			}
			resource = value;
			if (resource.is_null() || resource->get_script().get_type() != Variant::NIL || ClassDB::is_gdextension(resource->get_class()) || resource->is_extension_placeholder() || ClassDB::get_api_type(resource->get_class()) != ClassDB::API_CORE) {
				return result(false, "unsupported_resource_type");
			}
			state["target_instance"] = int64_t(node->get_instance_id());
			state["resource_instance"] = String::num_uint64(uint64_t(resource->get_instance_id()));
			state["resource_version"] = int64_t(resource->get_edited_version());
			Dictionary content;
			if (!resource_snapshot(resource, content) || resource->get_class() == "CompressedTexture2D") {
				return result(false, "unsupported_resource_snapshot");
			}
			state["resource_content"] = content;
			const String source = resource->get_path().get_slice("::", 0);
			if (!source.is_empty() && !file_state(source, state)) {
				return result(false, "invalid_resource_source");
			}
		}
	}
	if (JSON::stringify(state).utf8().length() > 16384) {
		return result(false, "scene_snapshot_capacity");
	}
	Dictionary r = result(false);
	r["action"] = action;
	r["target_instance"] = int64_t(editor->get_instance_id());
	r["old_value"] = state;
	r["manual_confirmation_required"] = true;
	r["undoable"] = false;
	if (!p_confirmed) {
		r["confirmation_required"] = true;
		return r;
	}
	if (!same(p_args.get("expected_target_instance", Variant()), r["target_instance"]) || !same(p_args.get("expected_old_value", Variant()), state)) {
		return result(false, "scene_changed_since_confirmation");
	}
	if (importing) {
		const String path = p_args["resource_path"];
		Vector<String> files;
		files.push_back(path);
		filesystem->reimport_files(files);
		filesystem->scan_changes();
		int index = -1;
		EditorFileSystemDirectory *directory = filesystem->find_file(path, &index);
		const bool valid = directory && index >= 0 && directory->get_file_import_is_valid(index);
		r["import_requested"] = true;
		r["import_valid"] = valid;
		r["importing"] = filesystem->is_importing();
		r["import_metadata_sha256"] = FileAccess::get_sha256(path + ".import");
		r["ok"] = valid && !filesystem->is_importing();
		if (!bool(r["ok"])) {
			r["error"] = "import_failed_or_pending";
		}
	} else {
		Error error = OK;
		if (exporting) {
			const String format = p_args.get("format", "project");
			const bool debug = p_args.get("debug", false);
			Ref<EditorExportPlatform> platform = preset->get_platform();
			if (format == "project") {
				String explanation;
				bool missing_templates = false;
				if (!platform->can_export(preset, explanation, missing_templates, debug)) {
					r["error"] = "project_export_unavailable";
					r["missing_templates"] = missing_templates;
					return r;
				}
				error = platform->export_project(preset, debug, ProjectSettings::get_singleton()->globalize_path(destination));
			} else if (format == "pack") {
				error = platform->export_pack(preset, debug, ProjectSettings::get_singleton()->globalize_path(destination));
			} else {
				error = platform->export_zip(preset, debug, ProjectSettings::get_singleton()->globalize_path(destination));
			}
		} else {
			// Dispatch directly to the native text saver, excluding custom savers.
			Dictionary before;
			if (!resource_snapshot(resource, before) || !same(before, state["resource_content"])) {
				return result(false, "resource_changed_before_save");
			}
			ResourceFormatSaverText saver;
			error = saver.save(resource, destination);
			Dictionary after;
			if (!resource_snapshot(resource, after) || !same(before, after)) {
				return result(false, "resource_changed_during_save");
			}
		}
		if (exporting && String(p_args.get("format", "project")) != "project") {
			// Native customization writes its own exported cache. Recheck the stable
			// source/import/template inputs independently of those generated outputs.
			const Dictionary refreshed = perform(p_args, false);
			const Dictionary refreshed_state = refreshed.get("old_value", Dictionary());
			if (!same(refreshed_state.get("stable_input_sha256", Variant()), state.get("stable_input_sha256", Variant()))) {
				return result(false, "project_input_changed_during_export");
			}
		}
		r["native_error"] = int(error);
		String output_hash = FileAccess::exists(destination) ? FileAccess::get_sha256(destination) : String();
		const bool directory_output = DirAccess::exists(destination);
		if (directory_output) {
			String manifest;
			int count = 0;
			uint64_t bytes = 0;
			if (input_tree(destination, String(), manifest, count, bytes)) {
				output_hash = manifest.sha256_text();
			}
		}
		r["output_exists"] = FileAccess::exists(destination) || directory_output;
		r["output_directory"] = directory_output;
		r["output_sha256"] = output_hash;
		r["ok"] = error == OK && bool(r["output_exists"]) && !output_hash.is_empty();
		if (!bool(r["ok"])) {
			r["error"] = "export_failed";
		}
		filesystem->scan_changes();
	}
	return r;
}
