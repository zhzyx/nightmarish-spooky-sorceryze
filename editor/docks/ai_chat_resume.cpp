/**************************************************************************/
/*  ai_chat_resume.cpp                                                    */
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

#include "ai_chat_resume.h"

#include "core/config/project_settings.h"
#include "core/crypto/crypto_core.h"
#include "core/io/compression.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/os/os.h"
#include "core/templates/hash_set.h"
#include "editor/file_system/editor_paths.h"

namespace {
bool whole_number(const Variant &p_value, double p_min, double p_max) {
	if (!p_value.is_num()) {
		return false;
	}
	const double value = p_value;
	return value >= p_min && value <= p_max && Math::floor(value) == value;
}

Error store_atomic(const String &p_path, const String &p_body) {
	const String temporary = p_path + ".tmp";
	Error error = OK;
	Ref<FileAccess> file = FileAccess::open(temporary, FileAccess::WRITE, &error);
	if (file.is_null()) {
		return error == OK ? ERR_FILE_CANT_WRITE : error;
	}
	const bool stored = file->store_string(p_body);
	file->flush();
	error = stored ? file->get_error() : ERR_FILE_CANT_WRITE;
	file->close();
	if (error != OK) {
		return error;
	}
	return DirAccess::rename_absolute(temporary, p_path);
}

bool read_small_json(const String &p_path, uint64_t p_limit, Dictionary &r_data) {
	if (!FileAccess::exists(p_path)) {
		return false;
	}
	const Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::READ);
	if (file.is_null() || file->get_length() > p_limit) {
		return false;
	}
	const Variant parsed = JSON::parse_string(file->get_as_utf8_string());
	if (parsed.get_type() != Variant::DICTIONARY) {
		return false;
	}
	r_data = parsed;
	return true;
}
} // namespace

bool AIChatResume::images_valid(const Variant &p_value) {
	if (p_value.get_type() != Variant::ARRAY || Array(p_value).size() > 4) {
		return false;
	}
	int total = 0;
	for (const Variant &value : Array(p_value)) {
		if (value.get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary image = value;
		if (image.get("name", Variant()).get_type() != Variant::STRING || image.get("data", Variant()).get_type() != Variant::STRING || image.get("mime_type", Variant()).get_type() != Variant::STRING) {
			return false;
		}
		const String mime = image["mime_type"];
		const String data = image["data"];
		if ((mime != "image/png" && mime != "image/jpeg") || data.length() > 256 * 1024 || data.is_empty()) {
			return false;
		}
		total += data.length();
	}
	return total <= 512 * 1024;
}

bool AIChatResume::calls_valid(const Variant &p_value) {
	if (p_value.get_type() != Variant::ARRAY || Array(p_value).size() > 8) {
		return false;
	}
	HashSet<String> ids;
	for (const Variant &entry : Array(p_value)) {
		if (entry.get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary call = entry;
		if (call.get("id", Variant()).get_type() != Variant::STRING || String(call["id"]).is_empty() || ids.has(call["id"])) {
			return false;
		}
		ids.insert(call["id"]);
		if (call.get("function", Variant()).get_type() != Variant::DICTIONARY || call.get("type", "") != "function") {
			return false;
		}
		const Dictionary function = call["function"];
		if (function.get("name", Variant()).get_type() != Variant::STRING || function.get("arguments", Variant()).get_type() != Variant::STRING) {
			return false;
		}
	}
	return true;
}

bool AIChatResume::records_valid(const Variant &p_value, bool p_transcript) {
	if (p_value.get_type() != Variant::ARRAY || Array(p_value).size() > 100000) {
		return false;
	}
	for (const Variant &value : Array(p_value)) {
		if (value.get_type() != Variant::DICTIONARY) {
			return false;
		}
		const Dictionary record = value;
		if (record.get("role", Variant()).get_type() != Variant::STRING || record.get("content", Variant()).get_type() != Variant::STRING) {
			return false;
		}
		const String role = record["role"];
		if (role != "user" && role != "assistant" && (p_transcript ? (role != "work" && role != "editor" && role != "error") : role != "tool")) {
			return false;
		}
		if (record.has("images") && (role != "user" || !images_valid(record["images"]))) {
			return false;
		}
		if (p_transcript && record.has("detail") && (role != "work" || record["detail"].get_type() != Variant::STRING)) {
			return false;
		}
		if (!p_transcript && role == "tool" && record.get("tool_call_id", Variant()).get_type() != Variant::STRING) {
			return false;
		}
		if (!p_transcript && record.has("tool_calls") && (role != "assistant" || !calls_valid(record["tool_calls"]))) {
			return false;
		}
	}
	return true;
}

String AIChatResume::journal_path() {
	return EditorPaths::get_singleton()->get_project_settings_dir().path_join("ai_chat_resume.json");
}

String AIChatResume::ack_path() {
	return EditorPaths::get_singleton()->get_project_settings_dir().path_join("ai_chat_restart_ack.json");
}

String AIChatResume::report_path() {
	return EditorPaths::get_singleton()->get_project_settings_dir().path_join("ai_chat_restart_report.json");
}

String AIChatResume::global_dir() {
	return ProjectSettings::get_singleton()->globalize_path(EditorPaths::get_singleton()->get_project_settings_dir());
}

bool AIChatResume::token_valid(const String &p_token) {
	if (p_token.length() < 8 || p_token.length() > 128) {
		return false;
	}
	for (int i = 0; i < p_token.length(); i++) {
		const char32_t character = p_token[i];
		const bool allowed = (character >= '0' && character <= '9') || (character >= 'a' && character <= 'f') || character == '-';
		if (!allowed) {
			return false;
		}
	}
	return true;
}

String AIChatResume::make_token() {
	String token = String::num_uint64(uint64_t(OS::get_singleton()->get_unix_time()), 16);
	token += "-" + String::num_uint64(uint64_t(OS::get_singleton()->get_process_id()), 16);
	token += "-" + String::num_uint64(uint64_t(OS::get_singleton()->get_ticks_usec()), 16);
	token += "-" + String::num_uint64(uint64_t(uint32_t(Math::rand())), 16);
	return token;
}

bool AIChatResume::journal_valid(const Dictionary &p_journal) {
	if (!whole_number(p_journal.get("version", Variant()), VERSION, VERSION)) {
		return false;
	}
	if (!whole_number(p_journal.get("agent", Variant()), 0, INT32_MAX - 1) || !whole_number(p_journal.get("tool_rounds", Variant()), 0, 1 << 20) || !whole_number(p_journal.get("tool_index", Variant()), 0, 8)) {
		return false;
	}
	if (p_journal.get("model", Variant()).get_type() != Variant::STRING || p_journal.get("cli_model", Variant()).get_type() != Variant::STRING) {
		return false;
	}
	const Variant backend = p_journal.get("backend", Variant());
	if (!backend.is_num() || (double(backend) != 0 && double(backend) != 1)) {
		return false;
	}
	if (p_journal.has("smoke_check") && p_journal["smoke_check"].get_type() != Variant::BOOL) {
		return false;
	}
	if (!records_valid(p_journal.get("messages", Variant()), false) || !calls_valid(p_journal.get("tool_calls", Variant()))) {
		return false;
	}
	if (int(p_journal["tool_index"]) > Array(p_journal["tool_calls"]).size()) {
		return false;
	}
	// A journal without a restart intent only documents an interruption; it is
	// never replayed, so the remaining contract below applies to handoffs only.
	if (!p_journal.has("restart")) {
		return true;
	}
	if (p_journal["restart"].get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary restart = p_journal["restart"];
	for (const String &key : { "from_executable", "to_executable", "token" }) {
		if (restart.get(key, Variant()).get_type() != Variant::STRING || String(restart[key]).is_empty()) {
			return false;
		}
	}
	if (!token_valid(restart["token"]) || !whole_number(restart.get("attempt", Variant()), 1, MAX_RESTART_ATTEMPTS)) {
		return false;
	}
	for (const String &key : { "tool_call_id", "tool_name", "log" }) {
		if (restart.has(key) && restart[key].get_type() != Variant::STRING) {
			return false;
		}
	}
	// A restart started from the editor UI carries no tool call, but a recorded
	// one must belong to the batch that is about to be resumed.
	const String awaited = restart.get("tool_call_id", "");
	if (awaited.is_empty()) {
		return true;
	}
	for (const Variant &entry : Array(p_journal["tool_calls"])) {
		if (String(Dictionary(entry)["id"]) == awaited) {
			return true;
		}
	}
	return false;
}

Error AIChatResume::encode_journal(const Dictionary &p_journal, String &r_body, Dictionary &r_stats) {
	r_body = String();
	r_stats.clear();
	r_stats["stage"] = "validation";
	r_stats["encoding"] = "json";
	r_stats["uncompressed_bytes"] = 0;
	r_stats["stored_bytes"] = 0;
	if (!journal_valid(p_journal)) {
		return ERR_INVALID_DATA;
	}
	// Compact JSON alone avoids the old pretty-printing overhead. Small records
	// remain readable by old editors, including the rollback executable.
	const String body = JSON::stringify(p_journal);
	const CharString raw = body.utf8();
	r_stats["uncompressed_bytes"] = raw.length();
	if (uint64_t(raw.length()) > MAX_UNCOMPRESSED_JOURNAL_BYTES) {
		r_stats["stage"] = "uncompressed_limit";
		return ERR_PARAMETER_RANGE_ERROR;
	}
	if (uint64_t(raw.length()) <= MAX_JOURNAL_BYTES) {
		r_body = body;
	} else {
		r_stats["stage"] = "compression";
		r_stats["encoding"] = "gzip-base64";
		Vector<uint8_t> compressed;
		const int64_t capacity = Compression::get_max_compressed_buffer_size(raw.length(), Compression::MODE_GZIP);
		if (capacity <= 0) {
			return FAILED;
		}
		if (compressed.resize(capacity) != OK) {
			return ERR_OUT_OF_MEMORY;
		}
		const int64_t length = Compression::compress(compressed.ptrw(), reinterpret_cast<const uint8_t *>(raw.get_data()), raw.length(), Compression::MODE_GZIP);
		if (length <= 0 || length > capacity) {
			return FAILED;
		}
		// Include Base64 expansion in the disk budget before allocating the envelope.
		const uint64_t encoded_length = 4 * ((uint64_t(length) + 2) / 3);
		if (encoded_length > MAX_JOURNAL_BYTES) {
			r_stats["stage"] = "stored_limit";
			r_stats["stored_bytes"] = int64_t(encoded_length);
			return ERR_PARAMETER_RANGE_ERROR;
		}
		Dictionary envelope;
		envelope["storage"] = "gzip-base64";
		envelope["storage_version"] = 1;
		envelope["uncompressed_bytes"] = raw.length();
		envelope["sha256"] = body.sha256_text();
		envelope["payload"] = CryptoCore::b64_encode_str(compressed.ptr(), length);
		r_body = JSON::stringify(envelope);
	}
	r_stats["stored_bytes"] = r_body.utf8().length();
	if (uint64_t(int64_t(r_stats["stored_bytes"])) > MAX_JOURNAL_BYTES) {
		r_body = String();
		r_stats["stage"] = "stored_limit";
		return ERR_PARAMETER_RANGE_ERROR;
	}
	r_stats["stage"] = "encoded";
	return OK;
}

bool AIChatResume::decode_journal(const String &p_body, Dictionary &r_journal) {
	if (uint64_t(p_body.utf8().length()) > MAX_JOURNAL_BYTES) {
		return false;
	}
	JSON json;
	if (json.parse(p_body) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
		return false;
	}
	Dictionary data = json.get_data();
	if (data.has("storage")) {
		if (data.get("storage", "") != "gzip-base64" || !whole_number(data.get("storage_version", Variant()), 1, 1) || !whole_number(data.get("uncompressed_bytes", Variant()), 1, MAX_UNCOMPRESSED_JOURNAL_BYTES)) {
			return false;
		}
		if (data.get("payload", Variant()).get_type() != Variant::STRING || data.get("sha256", Variant()).get_type() != Variant::STRING) {
			return false;
		}
		const String digest = data["sha256"];
		const CharString encoded = String(data["payload"]).utf8();
		if (digest.length() != 64 || !digest.is_valid_hex_number(false) || encoded.length() == 0 || encoded.length() % 4 != 0) {
			return false;
		}
		Vector<uint8_t> compressed;
		if (compressed.resize(encoded.length() / 4 * 3) != OK) {
			return false;
		}
		size_t compressed_length = 0;
		if (CryptoCore::b64_decode(compressed.ptrw(), compressed.size(), &compressed_length, reinterpret_cast<const uint8_t *>(encoded.get_data()), encoded.length()) != OK || compressed_length == 0) {
			return false;
		}
		// The untrusted declared length is bounded BEFORE allocating/inflating.
		// Exact length and digest checks reject truncated, corrupt or substituted data.
		const int64_t expected = data["uncompressed_bytes"];
		Vector<uint8_t> raw;
		if (raw.resize(expected) != OK || Compression::decompress(raw.ptrw(), expected, compressed.ptr(), compressed_length, Compression::MODE_GZIP) != expected) {
			return false;
		}
		String body;
		if (body.append_utf8(reinterpret_cast<const char *>(raw.ptr()), raw.size()) != OK || body.utf8().length() != expected || body.sha256_text() != digest) {
			return false;
		}
		if (json.parse(body) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
			return false;
		}
		data = json.get_data();
		// No nested envelopes or permissive replay of an invalid decoded journal.
		if (data.has("storage")) {
			return false;
		}
	}
	if (!journal_valid(data)) {
		return false;
	}
	r_journal = data;
	return true;
}

bool AIChatResume::read_journal(Dictionary &r_journal) {
	if (!FileAccess::exists(journal_path())) {
		return false;
	}
	const Ref<FileAccess> file = FileAccess::open(journal_path(), FileAccess::READ);
	if (file.is_null() || file->get_length() > MAX_JOURNAL_BYTES) {
		return false;
	}
	return decode_journal(file->get_as_utf8_string(), r_journal);
}

Error AIChatResume::write_journal(const Dictionary &p_journal, Dictionary *r_stats) {
	String body;
	Dictionary stats;
	Error error = encode_journal(p_journal, body, stats);
	if (error == OK) {
		stats["stage"] = "write";
		error = store_atomic(journal_path(), body);
		if (error == OK) {
			stats["stage"] = "saved";
		}
	}
	if (r_stats) {
		*r_stats = stats;
	}
	return error;
}

void AIChatResume::clear_journal() {
	const String path = journal_path();
	if (FileAccess::exists(path)) {
		DirAccess::remove_absolute(path);
	}
	if (FileAccess::exists(path + ".tmp")) {
		DirAccess::remove_absolute(path + ".tmp");
	}
}

Error AIChatResume::write_ack(const String &p_token, const String &p_executable) {
	ERR_FAIL_COND_V(!token_valid(p_token), ERR_INVALID_PARAMETER);
	Dictionary ack;
	ack["version"] = VERSION;
	ack["token"] = p_token;
	ack["executable"] = p_executable;
	ack["pid"] = OS::get_singleton()->get_process_id();
	ack["unix_time"] = OS::get_singleton()->get_unix_time();
	// Written only once the dock itself is alive, so a binary that starts but
	// cannot build a working AI dock stays unacknowledged and is rolled back.
	ack["dock_ready"] = true;
	return store_atomic(ack_path(), JSON::stringify(ack, "\t"));
}

bool AIChatResume::read_report(Dictionary &r_report) {
	Dictionary data;
	if (!read_small_json(report_path(), 64 * 1024, data)) {
		return false;
	}
	const String status = data.get("status", "");
	if (status != "started" && status != "rolled_back" && status != "startup_unconfirmed" && status != "failed") {
		return false;
	}
	r_report = data;
	return true;
}

void AIChatResume::clear_report() {
	const String path = report_path();
	if (FileAccess::exists(path)) {
		DirAccess::remove_absolute(path);
	}
}
