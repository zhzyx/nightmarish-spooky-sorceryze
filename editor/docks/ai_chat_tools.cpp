/**************************************************************************/
/*  ai_chat_tools.cpp                                                     */
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

#include "ai_chat_tools.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/templates/hash_set.h"

namespace {
bool read_script_bytes(const String &p_path, Vector<uint8_t> &r_bytes) {
	Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::READ);
	if (file.is_null() || file->get_length() > AIChatTools::MAX_SCRIPT_BYTES) {
		return false;
	}
	const uint64_t length = file->get_length();
	r_bytes.resize(length);
	if (length > 0 && file->get_buffer(r_bytes.ptrw(), length) != length) {
		return false;
	}
	return file->get_error() == OK;
}

bool decode_script_bytes(const Vector<uint8_t> &p_bytes, String &r_text) {
	r_text = String();
	if (!p_bytes.is_empty() && r_text.append_utf8(reinterpret_cast<const char *>(p_bytes.ptr()), p_bytes.size()) != OK) {
		return false;
	}
	if (p_bytes.size() >= 3 && p_bytes[0] == 0xef && p_bytes[1] == 0xbb && p_bytes[2] == 0xbf) {
		r_text = String::chr(0xfeff) + r_text;
	}
	return true;
}

bool store_script_bytes(const String &p_path, const Vector<uint8_t> &p_bytes) {
	Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::WRITE);
	if (file.is_null()) {
		return false;
	}
	const bool stored = p_bytes.is_empty() || file->store_buffer(p_bytes);
	file->flush();
	const Error error = file->get_error();
	file->close();
	Vector<uint8_t> saved;
	return stored && error == OK && read_script_bytes(p_path, saved) && saved == p_bytes;
}
} // namespace

bool AIChatTools::compact_context(const Array &p_messages, Array &r_messages, Dictionary &r_stats) {
	const Array original = p_messages.duplicate(true);
	Array deduplicated = original.duplicate(true);
	Vector<String> sources;
	sources.resize(original.size());
	HashMap<String, String> calls;
	for (int i = 0; i < original.size(); i++) {
		const Dictionary message = original[i];
		if (String(message.get("role", "")) == "assistant") {
			calls.clear();
			const Array tools = message.get("tool_calls", Array());
			for (int j = 0; j < tools.size(); j++) {
				const Dictionary call = tools[j];
				calls[String(call.get("id", ""))] = JSON::stringify(call.get("function", Dictionary()));
			}
		} else if (String(message.get("role", "")) == "tool") {
			const String id = message.get("tool_call_id", "");
			if (calls.has(id)) {
				sources.write[i] = calls[id];
			}
		}
	}
	HashSet<String> snapshots;
	int duplicates = 0;
	for (int i = original.size() - 1; i >= 0; i--) {
		Dictionary message = deduplicated[i];
		const String content = message.get("content", "");
		if (sources[i].is_empty() || content.length() < 4096 || content.begins_with("Error: ") || content.begins_with("User rejected")) {
			continue;
		}
		const String key = sources[i].sha256_text() + content.sha256_text();
		if (snapshots.has(key)) {
			message["content"] = "[Context compacted: duplicate tool snapshot, SHA-256 " + content.sha256_text() + ". The later identical snapshot is retained; this is not a new read or a new success.]";
			duplicates++;
		} else {
			snapshots.insert(key);
		}
	}
	int shortened = 0;
	int dropped_turns = 0;
	for (const int limit : { 32768, 8192, 2048 }) {
		r_messages = deduplicated.duplicate(true);
		shortened = 0;
		for (int i = 0; i < r_messages.size(); i++) {
			Dictionary message = r_messages[i];
			const String role = message.get("role", "");
			const String content = message.get("content", "");
			if (role == "tool" && content.length() > limit) {
				const String marker = vformat("\n[Context compacted: %d characters omitted from a %d-character tool result; SHA-256 %s. This is an incomplete excerpt, not a semantic summary. Re-read the file using offset/limit for missing lines before relying on them.]\n", content.length() - limit, content.length(), content.sha256_text());
				JSON json;
				bool structured = false;
				if (json.parse(content) == OK) {
					Dictionary output;
					if (json.get_data().get_type() == Variant::DICTIONARY) {
						output = json.get_data();
						bool text_shortened = false;
						for (const String &field : { String("stdout"), String("stderr"), String("content") }) {
							const Variant value = output.get(field, Variant());
							if (value.get_type() != Variant::STRING) {
								continue;
							}
							const String text = value;
							if (text.length() > limit / 2) {
								const String field_marker = vformat("\n[Context compacted: %d characters omitted from this %d-character text field; SHA-256 %s. This is an incomplete excerpt, not the full returned range.]\n", text.length() - limit / 2, text.length(), text.sha256_text());
								output[field] = text.left(limit / 4) + field_marker + text.right(limit / 4);
								text_shortened = true;
							}
						}
						if (text_shortened) {
							output["context_excerpted"] = true;
							output["context_note"] = "Original operation metadata is preserved, but text fields are incomplete excerpts. returned_lines/total_lines describe the original read, not the shortened text. Use offset/limit to re-read missing sections.";
							message["content"] = JSON::stringify(output);
							structured = true;
						}
					}
					if (!structured) {
						Dictionary excerpt;
						excerpt["context_excerpted"] = true;
						excerpt["context_note"] = "Original structured result was omitted. excerpt is a fragment, not a complete JSON document or a complete result.";
						excerpt["original_characters"] = content.length();
						excerpt["sha256"] = content.sha256_text();
						excerpt["excerpt"] = content.left(limit * 3 / 4) + marker + content.right(limit / 4);
						message["content"] = JSON::stringify(excerpt);
						structured = true;
					}
				}
				if (!structured) {
					message["content"] = content.left(limit * 3 / 4) + marker + content.right(limit / 4);
				}
				shortened++;
			}
			const Array tools = message.get("tool_calls", Array());
			for (int j = 0; j < tools.size(); j++) {
				Dictionary call = tools[j];
				Dictionary function = call.get("function", Dictionary());
				const String arguments = function.get("arguments", "");
				JSON json;
				if (arguments.length() > limit && json.parse(arguments) == OK && json.get_data().get_type() == Variant::DICTIONARY) {
					Dictionary parameters = json.get_data();
					const String replacement = parameters.get("content", "");
					if (replacement.length() > limit) {
						parameters["content"] = vformat("[Context compacted: historical replacement content omitted (%d characters, SHA-256 %s). This is not executable replacement content. Use the associated tool result to determine whether the write was approved/successful and re-read the current file before further edits.]", replacement.length(), replacement.sha256_text());
						function["arguments"] = JSON::stringify(parameters);
						shortened++;
					}
				}
			}
		}
		if (JSON::stringify(r_messages).utf8().length() <= MAX_CONTEXT_BYTES) {
			break;
		}
	}
	while (JSON::stringify(r_messages).utf8().length() > MAX_CONTEXT_BYTES - 1024) {
		int next_turn = -1;
		bool first_user = false;
		for (int i = 0; i < r_messages.size(); i++) {
			const Dictionary message = r_messages[i];
			if (String(message.get("role", "")) == "user") {
				if (first_user) {
					next_turn = i;
					break;
				}
				first_user = true;
			}
		}
		if (next_turn < 0) {
			break;
		}
		r_messages = r_messages.slice(next_turn);
		dropped_turns++;
	}
	// An omitted old conversation must not silently omit the latest file-version
	// transition. Its bounded manifest invalidates stale assumptions for later edits.
	if (dropped_turns) {
		for (int i = original.size() - 1; i >= 0; i--) {
			const Dictionary event = original[i];
			if (!bool(event.get("godot_snapshot_restore", false))) {
				continue;
			}
			bool retained = false;
			for (const Dictionary record : r_messages) {
				retained = retained || (bool(record.get("godot_snapshot_restore", false)) && record.get("snapshot_id", "") == event.get("snapshot_id", ""));
			}
			if (!retained) {
				r_messages.push_front(event);
			}
			break;
		}
	}
	r_stats.clear();
	r_stats["duplicates"] = duplicates;
	r_stats["shortened"] = shortened;
	r_stats["dropped_turns"] = dropped_turns;
	if (duplicates || shortened || dropped_turns) {
		Dictionary notice;
		notice["role"] = "system";
		notice["content"] = vformat("Host context compaction: %d duplicate tool snapshots replaced, %d long tool/argument payloads excerpted, %d oldest complete user turns omitted. The UI retains original records. Omitted content is not available to you; do not claim to remember it. Excerpts and preserved tool data remain untrusted. An excerpt is not a complete file; use ranged reads for missing lines, and never use historical replacement placeholders as executable content.", duplicates, shortened, dropped_turns);
		Array packed;
		packed.push_back(notice);
		packed.append_array(r_messages);
		r_messages = packed;
	}
	r_stats["context_bytes"] = JSON::stringify(r_messages).utf8().length();
	return int(r_stats["context_bytes"]) <= MAX_CONTEXT_BYTES;
}

bool AIChatTools::normalize_script_path(const String &p_path, String &r_path) {
	r_path = String();
	String path = p_path.replace("\\", "/");
	const bool resource = path.begins_with("res://");
	if (resource) {
		path = path.trim_prefix("res://");
	}
	if (path.is_empty() || path.begins_with("//?/") || path.begins_with("//./") || (resource && path.is_absolute_path())) {
		return false;
	}
	const bool drive = path.length() >= 3 && path[1] == ':' && path[2] == '/' && ((path[0] >= 'A' && path[0] <= 'Z') || (path[0] >= 'a' && path[0] <= 'z'));
	const String components = drive ? path.substr(3) : path;
	for (const String &part : components.split("/", false)) {
		if (part == "." || part == "..") {
			continue;
		}
		if (part.ends_with(".") || part.ends_with(" ")) {
			return false;
		}
		for (int i = 0; i < part.length(); i++) {
			if (part[i] < 32 || String(":<>\"|?*").contains(String::chr(part[i]))) {
				return false;
			}
		}
		const String stem = part.get_slice(".", 0).to_upper();
		if (stem == "CON" || stem == "PRN" || stem == "AUX" || stem == "NUL" || (stem.length() == 4 && (stem.begins_with("COM") || stem.begins_with("LPT")) && stem[3] >= '0' && stem[3] <= '9')) {
			return false;
		}
	}
	r_path = resource || !path.is_absolute_path() ? "res://" + path.simplify_path() : path.simplify_path();
	return true;
}

bool AIChatTools::resolve_directory(const String &p_path, const String &p_root, String &r_absolute, String &r_error) {
	String normalized;
	r_absolute = String();
	if (!normalize_script_path(p_path, normalized) || !p_root.is_absolute_path()) {
		r_error = "Invalid local path. Device paths and alternate data streams are not supported.";
		return false;
	}
	String absolute = normalized.begins_with("res://") ? p_root.path_join(normalized.trim_prefix("res://")).simplify_path() : normalized;
	Ref<DirAccess> directory = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
	if (directory->change_dir(absolute) != OK) {
		r_error = "The directory does not exist or is not accessible.";
		return false;
	}
	r_absolute = directory->get_current_dir();
	return true;
}

bool AIChatTools::resolve_script_path(const String &p_path, const String &p_root, String &r_absolute, String &r_error) {
	String normalized;
	r_absolute = String();
	if (!normalize_script_path(p_path, normalized) || !p_root.is_absolute_path()) {
		r_error = "Invalid local file path. Device paths and alternate data streams are not supported.";
		return false;
	}
	String absolute = normalized.begins_with("res://") ? p_root.path_join(normalized.trim_prefix("res://")).simplify_path() : normalized;
	Ref<DirAccess> directory = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
	if (absolute.get_file().is_empty() || directory->dir_exists(absolute) || !directory->dir_exists(absolute.get_base_dir())) {
		r_error = "The parent directory must exist and the target must be a file.";
		return false;
	}
	r_absolute = absolute;
	return true;
}

bool AIChatTools::read_script(const String &p_absolute, String &r_content, String &r_error) {
	Vector<uint8_t> bytes;
	if (!read_script_bytes(p_absolute, bytes) || !decode_script_bytes(bytes, r_content)) {
		r_error = "Cannot read a complete UTF-8 script within the 256 KiB limit.";
		return false;
	}
	return true;
}

bool AIChatTools::write_script(const String &p_absolute, const String &p_before, const String &p_after, bool p_existed, String &r_error, bool p_preserve_bom) {
	String replacement = p_after;
	const String bom = String::chr(0xfeff);
	if (p_preserve_bom && p_existed && p_before.begins_with(bom) && !replacement.begins_with(bom)) {
		replacement = bom + replacement;
	}
	const Vector<uint8_t> proposed = replacement.to_utf8_buffer();
	if (proposed.size() > MAX_SCRIPT_BYTES) {
		r_error = "The proposed script exceeds the 256 KiB limit.";
		return false;
	}
	if (FileAccess::exists(p_absolute) != p_existed) {
		r_error = "File existence changed since the preview. Nothing was written.";
		return false;
	}
	Vector<uint8_t> original;
	String current;
	if (p_existed && (!read_script_bytes(p_absolute, original) || !decode_script_bytes(original, current) || current != p_before)) {
		r_error = "The script changed or could not be read since the preview. Nothing was written.";
		return false;
	}
	String backup_path;
	if (p_existed) {
		Error backup_error = OK;
		Ref<FileAccess> backup = FileAccess::create_temp(FileAccess::WRITE_READ, "godot_ai_chat_backup", "bak", true, &backup_error);
		if (backup.is_null() || backup_error != OK) {
			r_error = "Cannot create a recovery backup. Nothing was written.";
			return false;
		}
		backup_path = backup->get_path_absolute();
		const bool stored = original.is_empty() || backup->store_buffer(original);
		backup->flush();
		const Error error = backup->get_error();
		backup->close();
		Vector<uint8_t> saved;
		if (!stored || error != OK || !read_script_bytes(backup_path, saved) || saved != original) {
			DirAccess::remove_absolute(backup_path);
			r_error = "Cannot verify the recovery backup. Nothing was written.";
			return false;
		}
	}
	if (!store_script_bytes(p_absolute, proposed)) {
		const bool restored = p_existed ? store_script_bytes(p_absolute, original) : (!FileAccess::exists(p_absolute) || DirAccess::remove_absolute(p_absolute) == OK);
		if (restored) {
			if (!backup_path.is_empty()) {
				DirAccess::remove_absolute(backup_path);
			}
			r_error = "Writing failed. The original file state was restored and verified.";
		} else {
			r_error = "Writing and automatic recovery failed. Stop editing and recover the original from: " + backup_path;
		}
		return false;
	}
	if (!backup_path.is_empty()) {
		DirAccess::remove_absolute(backup_path);
	}
	return true;
}

namespace {
constexpr int MAX_SNAPSHOT_BYTES = 48 * 1024 * 1024;

bool snapshot_schema(const Dictionary &p_snapshot) {
	const Variant version = p_snapshot.get("version", Variant());
	if (!version.is_num() || double(version) != 1 || p_snapshot.get("files", Variant()).get_type() != Variant::ARRAY) {
		return false;
	}
	const Array files = p_snapshot["files"];
	if (files.size() > 64) {
		return false;
	}
	HashSet<String> paths;
	for (const Variant &value : files) {
		if (value.get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary entry = value;
		for (const char *key : { "path", "before", "after" }) {
			if (entry.get(key, Variant()).get_type() != Variant::STRING) {
				return false;
			}
		}
		if (entry.get("existed", Variant()).get_type() != Variant::BOOL || (entry.has("after_existed") && entry["after_existed"].get_type() != Variant::BOOL)) {
			return false;
		}
		if (entry.has("pending_before") && (entry["pending_before"].get_type() != Variant::STRING || entry.get("pending_existed", Variant()).get_type() != Variant::BOOL || String(entry["pending_before"]).to_utf8_buffer().size() > AIChatTools::MAX_SCRIPT_BYTES)) {
			return false;
		}
		const String path = entry["path"];
		String normalized;
		if (!path.is_absolute_path() || !AIChatTools::normalize_script_path(path, normalized) || path != normalized || paths.has(path.to_lower())) {
			return false;
		}
		paths.insert(path.to_lower());
		if (String(entry["before"]).to_utf8_buffer().size() > AIChatTools::MAX_SCRIPT_BYTES || String(entry["after"]).to_utf8_buffer().size() > AIChatTools::MAX_SCRIPT_BYTES) {
			return false;
		}
	}
	return true;
}

bool set_snapshot_file(const Dictionary &p_entry, bool p_restore, String &r_error) {
	const String path = p_entry["path"];
	const bool exists = FileAccess::exists(path);
	String current;
	if (exists && !AIChatTools::read_script(path, current, r_error)) {
		return false;
	}
	const bool expected_exists = p_restore ? true : bool(p_entry["existed"]);
	const String expected = p_entry[p_restore ? "after" : "before"];
	const bool pending_before = p_restore && p_entry.has("pending_before") && exists == bool(p_entry["pending_existed"]) && (!exists || current == String(p_entry["pending_before"]));
	if (!pending_before && (exists != expected_exists || (exists && current != expected))) {
		r_error = "File changed during restore; no overwrite was performed: " + path;
		return false;
	}
	const bool wanted_exists = !p_restore || bool(p_entry["existed"]);
	const String wanted = p_entry[p_restore ? "before" : "after"];
	if (wanted_exists) {
		return AIChatTools::write_script(path, current, wanted, exists, r_error, false);
	}
	if (exists && DirAccess::remove_absolute(path) != OK) {
		r_error = "Cannot remove the file created by this turn: " + path;
		return false;
	}
	return !FileAccess::exists(path);
}
} // namespace

bool AIChatTools::save_snapshot(const String &p_path, const Dictionary &p_snapshot, String &r_error) {
	if (!snapshot_schema(p_snapshot)) {
		r_error = "Invalid local snapshot data; no files were changed.";
		return false;
	}
	const String body = JSON::stringify(p_snapshot);
	Dictionary envelope;
	envelope["payload"] = body;
	envelope["sha256"] = body.sha256_text();
	const String encoded = JSON::stringify(envelope);
	if (encoded.utf8().length() > MAX_SNAPSHOT_BYTES) {
		r_error = "The local snapshot exceeds its storage limit; no files were changed.";
		return false;
	}
	const String temporary = p_path + ".tmp";
	Ref<FileAccess> file = FileAccess::open(temporary, FileAccess::WRITE);
	if (file.is_null()) {
		r_error = "Cannot save the local snapshot: " + p_path;
		return false;
	}
	file->store_string(encoded);
	file->flush();
	const Error error = file->get_error();
	file->close();
	Dictionary verified;
	if (error != OK || !load_snapshot(temporary, verified, r_error) || DirAccess::rename_absolute(temporary, p_path) != OK) {
		r_error = "Cannot verify or install the local snapshot: " + p_path;
		return false;
	}
	return true;
}

bool AIChatTools::load_snapshot(const String &p_path, Dictionary &r_snapshot, String &r_error) {
	r_snapshot.clear();
	Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::READ);
	if (file.is_null() || file->get_length() > MAX_SNAPSHOT_BYTES) {
		r_error = "Cannot read the bounded local snapshot: " + p_path;
		return false;
	}
	JSON json;
	if (json.parse(file->get_as_text()) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
		r_error = "Invalid local snapshot JSON.";
		return false;
	}
	const Dictionary envelope = json.get_data();
	if (envelope.get("payload", Variant()).get_type() != Variant::STRING || envelope.get("sha256", Variant()).get_type() != Variant::STRING) {
		r_error = "Invalid local snapshot envelope.";
		return false;
	}
	const String body = envelope["payload"];
	if (body.sha256_text() != String(envelope.get("sha256", "")) || json.parse(body) != OK || json.get_data().get_type() != Variant::DICTIONARY || !snapshot_schema(json.get_data())) {
		r_error = "Local snapshot integrity check failed; no files were changed.";
		return false;
	}
	r_snapshot = json.get_data();
	return true;
}

bool AIChatTools::check_snapshot(const Dictionary &p_snapshot, String &r_error) {
	if (!snapshot_schema(p_snapshot) || bool(p_snapshot.get("restored", false))) {
		r_error = "This local snapshot is invalid or already restored.";
		return false;
	}
	const Array files = p_snapshot["files"];
	for (const Dictionary entry : files) {
		const String path = entry["path"];
		String resolved;
		if (!resolve_script_path(path, path.get_base_dir(), resolved, r_error)) {
			return false;
		}
		const bool exists = FileAccess::exists(path);
		String current;
		if (exists && !read_script(path, current, r_error)) {
			return false;
		}
		// A prepared write interrupted before execution may still be at before.
		const bool already_before = exists == bool(entry["existed"]) && (!exists || current == String(entry["before"]));
		const bool pending_before = entry.has("pending_before") && exists == bool(entry["pending_existed"]) && (!exists || current == String(entry["pending_before"]));
		if (!already_before && !pending_before && (!exists || current != String(entry["after"]))) {
			r_error = "File changed since this turn; the entire restore was refused: " + path;
			return false;
		}
	}
	return true;
}

bool AIChatTools::restore_snapshot(const Dictionary &p_snapshot, String &r_error) {
	if (!check_snapshot(p_snapshot, r_error)) {
		return false;
	}
	const Array files = p_snapshot["files"];
	Array applied;
	for (const Dictionary entry : files) {
		const String path = entry["path"];
		const bool exists = FileAccess::exists(path);
		String current;
		const bool readable = !exists || read_script(path, current, r_error);
		if (readable && exists == bool(entry["existed"]) && (!exists || current == String(entry["before"]))) {
			continue;
		}
		const bool pending_before = entry.has("pending_before") && exists == bool(entry["pending_existed"]) && (!exists || current == String(entry["pending_before"]));
		if (!readable || (!pending_before && (!exists || current != String(entry["after"]))) || !set_snapshot_file(entry, true, r_error)) {
			bool recovered = true;
			for (int i = applied.size() - 1; i >= 0; i--) {
				String recovery_error;
				recovered = set_snapshot_file(applied[i], false, recovery_error) && recovered;
			}
			r_error += recovered ? "\nEarlier restored files were returned to their post-turn state." : "\nAutomatic recovery failed. Preserve this snapshot and stop editing.";
			return false;
		}
		Dictionary rollback_entry = entry.duplicate(true);
		rollback_entry["after"] = current;
		applied.push_back(rollback_entry);
	}
	return true;
}

bool AIChatTools::check_snapshot_transition(const Dictionary &p_snapshot, bool p_forward, String &r_error, bool p_recovery) {
	if (!snapshot_schema(p_snapshot)) {
		r_error = "Invalid version transaction; no files were changed.";
		return false;
	}
	for (const Dictionary entry : Array(p_snapshot["files"])) {
		const String path = entry["path"];
		String resolved;
		String current;
		if (!resolve_script_path(path, path.get_base_dir(), resolved, r_error)) {
			return false;
		}
		const bool exists = FileAccess::exists(path);
		if (exists && !read_script(path, current, r_error)) {
			return false;
		}
		const bool before = exists == bool(entry["existed"]) && (!exists || current == String(entry["before"]));
		const bool after = exists == bool(entry.get("after_existed", true)) && (!exists || current == String(entry["after"]));
		if (!(p_forward ? before : after) && !(p_recovery && (before || after))) {
			r_error = "File changed outside the Agent version transaction; all files were refused: " + path;
			return false;
		}
	}
	return true;
}

bool AIChatTools::apply_snapshot_transition(const Dictionary &p_snapshot, bool p_forward, String &r_error, bool p_recovery) {
	if (!check_snapshot_transition(p_snapshot, p_forward, r_error, p_recovery)) {
		return false;
	}
	Array applied;
	for (const Dictionary entry : Array(p_snapshot["files"])) {
		const String path = entry["path"];
		const bool exists = FileAccess::exists(path);
		String current;
		const bool readable = !exists || read_script(path, current, r_error);
		const bool wanted_exists = p_forward ? bool(entry.get("after_existed", true)) : bool(entry["existed"]);
		const String wanted = entry[p_forward ? "after" : "before"];
		if (readable && exists == wanted_exists && (!exists || current == wanted)) {
			continue;
		}
		Dictionary single = p_snapshot.duplicate();
		Array one;
		one.push_back(entry);
		single["files"] = one;
		bool changed = readable && check_snapshot_transition(single, p_forward, r_error);
		if (changed) {
			changed = wanted_exists ? write_script(path, current, wanted, exists, r_error, false) : DirAccess::remove_absolute(path) == OK;
		}
		if (!changed) {
			bool recovered = true;
			for (int i = applied.size() - 1; i >= 0; i--) {
				Dictionary rollback = p_snapshot.duplicate();
				Array undo;
				undo.push_back(applied[i]);
				rollback["files"] = undo;
				String recovery_error;
				recovered = apply_snapshot_transition(rollback, !p_forward, recovery_error) && recovered;
			}
			r_error += recovered ? "\nEarlier files were rolled back; the transaction was not committed." : "\nRecovery failed; preserve the transaction journal and stop editing.";
			return false;
		}
		applied.push_back(entry);
	}
	return true;
}
