/**************************************************************************/
/*  gameplay_replication.cpp                                              */
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

#include "gameplay_replication.h"

#include "core/crypto/crypto_core.h"
#include "core/io/json.h"
#include "core/io/marshalls.h"
#include "core/object/class_db.h"

static Error _gameplay_encode_variant(const Variant &p_value, PackedByteArray &r_bytes) {
	int length = 0;
	Error error = encode_variant(p_value, nullptr, length, false);
	if (error != OK) {
		return error;
	}
	r_bytes.resize(length);
	if (length == 0) {
		return OK;
	}
	return encode_variant(p_value, r_bytes.ptrw(), length, false);
}

static Error _gameplay_decode_variant(const PackedByteArray &p_bytes, Variant &r_value) {
	ERR_FAIL_COND_V(p_bytes.is_empty(), ERR_INVALID_DATA);
	return decode_variant(r_value, p_bytes.ptr(), p_bytes.size(), nullptr, false);
}

static Error _gameplay_decode_base64(const String &p_encoded, PackedByteArray &r_bytes) {
	ERR_FAIL_COND_V(p_encoded.is_empty(), ERR_INVALID_DATA);
	const CharString source = p_encoded.ascii();
	r_bytes.resize(source.length() / 4 * 3 + 1);
	size_t decoded_length = 0;
	const Error error = CryptoCore::b64_decode(r_bytes.ptrw(), r_bytes.size(), &decoded_length, reinterpret_cast<const uint8_t *>(source.get_data()), source.length());
	if (error != OK) {
		r_bytes.clear();
		return error;
	}
	r_bytes.resize(decoded_length);
	return OK;
}

void GameplayReplicationProperty::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_property_name", "name"), &GameplayReplicationProperty::set_property_name);
	ClassDB::bind_method(D_METHOD("get_property_name"), &GameplayReplicationProperty::get_property_name);
	ClassDB::bind_method(D_METHOD("set_condition", "condition"), &GameplayReplicationProperty::set_condition);
	ClassDB::bind_method(D_METHOD("get_condition"), &GameplayReplicationProperty::get_condition);
	ClassDB::bind_method(D_METHOD("set_rep_notify", "enabled"), &GameplayReplicationProperty::set_rep_notify);
	ClassDB::bind_method(D_METHOD("is_rep_notify"), &GameplayReplicationProperty::is_rep_notify);
	ClassDB::bind_method(D_METHOD("set_update_interval_msec", "interval_msec"), &GameplayReplicationProperty::set_update_interval_msec);
	ClassDB::bind_method(D_METHOD("get_update_interval_msec"), &GameplayReplicationProperty::get_update_interval_msec);

	ADD_PROPERTY(PropertyInfo(Variant::STRING_NAME, "property_name"), "set_property_name", "get_property_name");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "condition", PROPERTY_HINT_ENUM, "Always,Initial Only,Owner Only,Skip Owner"), "set_condition", "get_condition");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "rep_notify"), "set_rep_notify", "is_rep_notify");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "update_interval_msec", PROPERTY_HINT_RANGE, "0,60000,1,or_greater"), "set_update_interval_msec", "get_update_interval_msec");

	BIND_ENUM_CONSTANT(CONDITION_ALWAYS);
	BIND_ENUM_CONSTANT(CONDITION_INITIAL_ONLY);
	BIND_ENUM_CONSTANT(CONDITION_OWNER_ONLY);
	BIND_ENUM_CONSTANT(CONDITION_SKIP_OWNER);
}

void GameplayReplicationProperty::set_property_name(const StringName &p_name) {
	ERR_FAIL_COND_MSG(p_name.is_empty(), "A replicated property requires a non-empty name.");
	property_name = p_name;
}

StringName GameplayReplicationProperty::get_property_name() const {
	return property_name;
}

void GameplayReplicationProperty::set_condition(Condition p_condition) {
	ERR_FAIL_COND_MSG(
			p_condition != CONDITION_ALWAYS && p_condition != CONDITION_INITIAL_ONLY && p_condition != CONDITION_OWNER_ONLY && p_condition != CONDITION_SKIP_OWNER,
			"Invalid replication condition.");
	condition = p_condition;
}

GameplayReplicationProperty::Condition GameplayReplicationProperty::get_condition() const {
	return condition;
}

void GameplayReplicationProperty::set_rep_notify(bool p_enabled) {
	rep_notify = p_enabled;
}

bool GameplayReplicationProperty::is_rep_notify() const {
	return rep_notify;
}

void GameplayReplicationProperty::set_update_interval_msec(uint64_t p_interval_msec) {
	update_interval_msec = p_interval_msec;
}

uint64_t GameplayReplicationProperty::get_update_interval_msec() const {
	return update_interval_msec;
}

void GameplayRPCConfig::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_rpc_name", "name"), &GameplayRPCConfig::set_rpc_name);
	ClassDB::bind_method(D_METHOD("get_rpc_name"), &GameplayRPCConfig::get_rpc_name);
	ClassDB::bind_method(D_METHOD("set_direction", "direction"), &GameplayRPCConfig::set_direction);
	ClassDB::bind_method(D_METHOD("get_direction"), &GameplayRPCConfig::get_direction);
	ClassDB::bind_method(D_METHOD("set_require_owner", "require_owner"), &GameplayRPCConfig::set_require_owner);
	ClassDB::bind_method(D_METHOD("is_owner_required"), &GameplayRPCConfig::is_owner_required);
	ClassDB::bind_method(D_METHOD("set_max_payload_bytes", "max_payload_bytes"), &GameplayRPCConfig::set_max_payload_bytes);
	ClassDB::bind_method(D_METHOD("get_max_payload_bytes"), &GameplayRPCConfig::get_max_payload_bytes);

	ADD_PROPERTY(PropertyInfo(Variant::STRING_NAME, "rpc_name"), "set_rpc_name", "get_rpc_name");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "direction", PROPERTY_HINT_ENUM, "Server,Owner,Client,Multicast"), "set_direction", "get_direction");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "require_owner"), "set_require_owner", "is_owner_required");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_payload_bytes", PROPERTY_HINT_RANGE, "1,65536,1"), "set_max_payload_bytes", "get_max_payload_bytes");

	BIND_ENUM_CONSTANT(DIRECTION_SERVER);
	BIND_ENUM_CONSTANT(DIRECTION_OWNER);
	BIND_ENUM_CONSTANT(DIRECTION_CLIENT);
	BIND_ENUM_CONSTANT(DIRECTION_MULTICAST);
}

void GameplayRPCConfig::set_rpc_name(const StringName &p_name) {
	ERR_FAIL_COND_MSG(p_name.is_empty(), "An RPC requires a non-empty name.");
	rpc_name = p_name;
}

StringName GameplayRPCConfig::get_rpc_name() const {
	return rpc_name;
}

void GameplayRPCConfig::set_direction(Direction p_direction) {
	ERR_FAIL_COND_MSG(
			p_direction != DIRECTION_SERVER && p_direction != DIRECTION_OWNER && p_direction != DIRECTION_CLIENT && p_direction != DIRECTION_MULTICAST,
			"Invalid RPC direction.");
	direction = p_direction;
}

GameplayRPCConfig::Direction GameplayRPCConfig::get_direction() const {
	return direction;
}

void GameplayRPCConfig::set_require_owner(bool p_require_owner) {
	require_owner = p_require_owner;
}

bool GameplayRPCConfig::is_owner_required() const {
	return require_owner;
}

void GameplayRPCConfig::set_max_payload_bytes(int p_max_payload_bytes) {
	ERR_FAIL_COND_MSG(p_max_payload_bytes < 1 || p_max_payload_bytes > 65536, "RPC payload limit must be between 1 and 65536 bytes.");
	max_payload_bytes = p_max_payload_bytes;
}

int GameplayRPCConfig::get_max_payload_bytes() const {
	return max_payload_bytes;
}

void GameplayReplicationState::_bind_methods() {
	ClassDB::bind_method(D_METHOD("add_property", "descriptor", "initial_value"), &GameplayReplicationState::add_property, DEFVAL(Variant()));
	ClassDB::bind_method(D_METHOD("remove_property", "name"), &GameplayReplicationState::remove_property);
	ClassDB::bind_method(D_METHOD("has_property", "name"), &GameplayReplicationState::has_property);
	ClassDB::bind_method(D_METHOD("get_property_descriptors"), &GameplayReplicationState::get_property_descriptors);
	ClassDB::bind_method(D_METHOD("set_property_value", "name", "value"), &GameplayReplicationState::set_property_value);
	ClassDB::bind_method(D_METHOD("get_property_value", "name"), &GameplayReplicationState::get_property_value);
	ClassDB::bind_method(D_METHOD("mark_property_dirty", "name"), &GameplayReplicationState::mark_property_dirty);
	ClassDB::bind_method(D_METHOD("is_property_dirty", "name"), &GameplayReplicationState::is_property_dirty);
	ClassDB::bind_method(D_METHOD("is_property_dirty_for_peer", "name", "peer_id"), &GameplayReplicationState::is_property_dirty_for_peer);
	ClassDB::bind_method(D_METHOD("register_peer", "peer_id"), &GameplayReplicationState::register_peer);
	ClassDB::bind_method(D_METHOD("unregister_peer", "peer_id"), &GameplayReplicationState::unregister_peer);
	ClassDB::bind_method(D_METHOD("collect_updates", "peer_id", "owner_peer_id", "now_msec"), &GameplayReplicationState::collect_updates);
	ClassDB::bind_method(D_METHOD("reset_peer_updates", "peer_id", "updates"), &GameplayReplicationState::reset_peer_updates);
	ClassDB::bind_method(D_METHOD("apply_updates", "updates"), &GameplayReplicationState::apply_updates);
	ClassDB::bind_method(D_METHOD("get_change_serial"), &GameplayReplicationState::get_change_serial);
	ClassDB::bind_method(D_METHOD("set_rep_notify_handler", "handler"), &GameplayReplicationState::set_rep_notify_handler);
	ClassDB::bind_method(D_METHOD("get_rep_notify_handler"), &GameplayReplicationState::get_rep_notify_handler);

	ADD_PROPERTY(PropertyInfo(Variant::CALLABLE, "rep_notify_handler"), "set_rep_notify_handler", "get_rep_notify_handler");
	ADD_SIGNAL(MethodInfo("property_rep_notified", PropertyInfo(Variant::STRING_NAME, "property"), PropertyInfo(Variant::NIL, "old_value"), PropertyInfo(Variant::NIL, "new_value")));
}

Error GameplayReplicationState::add_property(const Ref<GameplayReplicationProperty> &p_descriptor, const Variant &p_initial_value) {
	ERR_FAIL_COND_V(p_descriptor.is_null() || p_descriptor->get_property_name().is_empty(), ERR_INVALID_PARAMETER);
	const StringName name = p_descriptor->get_property_name();
	ERR_FAIL_COND_V_MSG(properties.has(name), ERR_ALREADY_EXISTS, "A replication descriptor with this name already exists.");
	PropertyRuntime runtime;
	runtime.descriptor = p_descriptor;
	runtime.value = p_initial_value;
	properties.insert(name, runtime);
	change_serial++;
	return OK;
}

bool GameplayReplicationState::remove_property(const StringName &p_name) {
	const bool removed = properties.erase(p_name);
	if (removed) {
		change_serial++;
	}
	return removed;
}

bool GameplayReplicationState::has_property(const StringName &p_name) const {
	return properties.has(p_name);
}

Array GameplayReplicationState::get_property_descriptors() const {
	Array result;
	for (const KeyValue<StringName, PropertyRuntime> &entry : properties) {
		result.push_back(entry.value.descriptor);
	}
	return result;
}

Error GameplayReplicationState::set_property_value(const StringName &p_name, const Variant &p_value) {
	PropertyRuntime *runtime = properties.getptr(p_name);
	ERR_FAIL_NULL_V(runtime, ERR_DOES_NOT_EXIST);
	if (runtime->value == p_value) {
		return OK;
	}
	runtime->value = p_value;
	runtime->revision++;
	change_serial++;
	return OK;
}

Variant GameplayReplicationState::get_property_value(const StringName &p_name) const {
	const PropertyRuntime *runtime = properties.getptr(p_name);
	ERR_FAIL_NULL_V(runtime, Variant());
	return runtime->value;
}

Error GameplayReplicationState::mark_property_dirty(const StringName &p_name) {
	PropertyRuntime *runtime = properties.getptr(p_name);
	ERR_FAIL_NULL_V(runtime, ERR_DOES_NOT_EXIST);
	runtime->revision++;
	change_serial++;
	return OK;
}

bool GameplayReplicationState::is_property_dirty(const StringName &p_name) const {
	const PropertyRuntime *runtime = properties.getptr(p_name);
	ERR_FAIL_NULL_V(runtime, false);
	if (registered_peers.is_empty()) {
		return true;
	}
	for (const int peer_id : registered_peers) {
		if (is_property_dirty_for_peer(p_name, peer_id)) {
			return true;
		}
	}
	return false;
}

bool GameplayReplicationState::is_property_dirty_for_peer(const StringName &p_name, int p_peer_id) const {
	const PropertyRuntime *runtime = properties.getptr(p_name);
	ERR_FAIL_NULL_V(runtime, false);
	if (runtime->descriptor->get_condition() == GameplayReplicationProperty::CONDITION_INITIAL_ONLY && runtime->initial_sent.has(p_peer_id)) {
		return false;
	}
	const uint64_t *sent_revision = runtime->sent_revisions.getptr(p_peer_id);
	return !sent_revision || *sent_revision < runtime->revision;
}

void GameplayReplicationState::register_peer(int p_peer_id) {
	ERR_FAIL_COND(p_peer_id <= 0);
	registered_peers.insert(p_peer_id);
}

void GameplayReplicationState::unregister_peer(int p_peer_id) {
	registered_peers.erase(p_peer_id);
	for (KeyValue<StringName, PropertyRuntime> &entry : properties) {
		entry.value.sent_revisions.erase(p_peer_id);
		entry.value.last_sent_msec.erase(p_peer_id);
		entry.value.initial_sent.erase(p_peer_id);
	}
}

Array GameplayReplicationState::collect_updates(int p_peer_id, int p_owner_peer_id, uint64_t p_now_msec) {
	Array updates;
	ERR_FAIL_COND_V(p_peer_id <= 0, updates);
	register_peer(p_peer_id);
	for (KeyValue<StringName, PropertyRuntime> &entry : properties) {
		PropertyRuntime &runtime = entry.value;
		const GameplayReplicationProperty::Condition condition = runtime.descriptor->get_condition();
		if (condition == GameplayReplicationProperty::CONDITION_OWNER_ONLY && p_peer_id != p_owner_peer_id) {
			continue;
		}
		if (condition == GameplayReplicationProperty::CONDITION_SKIP_OWNER && p_peer_id == p_owner_peer_id) {
			continue;
		}
		if (condition == GameplayReplicationProperty::CONDITION_INITIAL_ONLY && runtime.initial_sent.has(p_peer_id)) {
			continue;
		}
		const uint64_t *sent_revision = runtime.sent_revisions.getptr(p_peer_id);
		if (sent_revision && *sent_revision >= runtime.revision) {
			continue;
		}
		const uint64_t *last_sent = runtime.last_sent_msec.getptr(p_peer_id);
		if (last_sent && p_now_msec < *last_sent + runtime.descriptor->get_update_interval_msec()) {
			continue;
		}
		Dictionary update;
		update["name"] = entry.key;
		update["value"] = runtime.value;
		update["revision"] = int64_t(runtime.revision);
		updates.push_back(update);
		runtime.sent_revisions.insert(p_peer_id, runtime.revision);
		runtime.last_sent_msec.insert(p_peer_id, p_now_msec);
		if (condition == GameplayReplicationProperty::CONDITION_INITIAL_ONLY) {
			runtime.initial_sent.insert(p_peer_id);
		}
	}
	return updates;
}

void GameplayReplicationState::reset_peer_updates(int p_peer_id, const Array &p_updates) {
	for (int i = 0; i < p_updates.size(); i++) {
		if (p_updates[i].get_type() != Variant::DICTIONARY) {
			continue;
		}
		const Dictionary update = p_updates[i];
		PropertyRuntime *runtime = properties.getptr(update.get("name", StringName()));
		if (!runtime) {
			continue;
		}
		runtime->sent_revisions.erase(p_peer_id);
		runtime->last_sent_msec.erase(p_peer_id);
		runtime->initial_sent.erase(p_peer_id);
	}
}

Error GameplayReplicationState::apply_updates(const Array &p_updates) {
	for (int i = 0; i < p_updates.size(); i++) {
		ERR_FAIL_COND_V(p_updates[i].get_type() != Variant::DICTIONARY, ERR_INVALID_DATA);
		const Dictionary update = p_updates[i];
		const StringName name = update.get("name", StringName());
		PropertyRuntime *runtime = properties.getptr(name);
		ERR_FAIL_NULL_V(runtime, ERR_DOES_NOT_EXIST);
		const int64_t revision_value = update.get("revision", int64_t(0));
		ERR_FAIL_COND_V(revision_value <= 0, ERR_INVALID_DATA);
		const uint64_t revision = uint64_t(revision_value);
		if (revision <= runtime->received_revision) {
			continue;
		}
		const Variant old_value = runtime->value;
		const Variant new_value = update.get("value", Variant());
		runtime->value = new_value;
		runtime->received_revision = revision;
		if (runtime->descriptor->is_rep_notify() && old_value != new_value) {
			emit_signal(SNAME("property_rep_notified"), name, old_value, new_value);
			if (rep_notify_handler.is_valid()) {
				rep_notify_handler.call(name, old_value, new_value);
			}
		}
	}
	return OK;
}

uint64_t GameplayReplicationState::get_change_serial() const {
	return change_serial;
}

void GameplayReplicationState::set_rep_notify_handler(const Callable &p_handler) {
	rep_notify_handler = p_handler;
}

Callable GameplayReplicationState::get_rep_notify_handler() const {
	return rep_notify_handler;
}

void GameplayReplicationFragmenter::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_chunk_payload_bytes", "bytes"), &GameplayReplicationFragmenter::set_chunk_payload_bytes);
	ClassDB::bind_method(D_METHOD("get_chunk_payload_bytes"), &GameplayReplicationFragmenter::get_chunk_payload_bytes);
	ClassDB::bind_method(D_METHOD("set_max_transfer_bytes", "bytes"), &GameplayReplicationFragmenter::set_max_transfer_bytes);
	ClassDB::bind_method(D_METHOD("get_max_transfer_bytes"), &GameplayReplicationFragmenter::get_max_transfer_bytes);
	ClassDB::bind_method(D_METHOD("set_max_chunks", "chunks"), &GameplayReplicationFragmenter::set_max_chunks);
	ClassDB::bind_method(D_METHOD("get_max_chunks"), &GameplayReplicationFragmenter::get_max_chunks);
	ClassDB::bind_method(D_METHOD("set_max_pending_assemblies", "count"), &GameplayReplicationFragmenter::set_max_pending_assemblies);
	ClassDB::bind_method(D_METHOD("get_max_pending_assemblies"), &GameplayReplicationFragmenter::get_max_pending_assemblies);
	ClassDB::bind_method(D_METHOD("set_assembly_timeout_msec", "timeout_msec"), &GameplayReplicationFragmenter::set_assembly_timeout_msec);
	ClassDB::bind_method(D_METHOD("get_assembly_timeout_msec"), &GameplayReplicationFragmenter::get_assembly_timeout_msec);
	ClassDB::bind_method(D_METHOD("get_last_error"), &GameplayReplicationFragmenter::get_last_error);
	ClassDB::bind_method(D_METHOD("get_pending_assembly_count"), &GameplayReplicationFragmenter::get_pending_assembly_count);
	ClassDB::bind_method(D_METHOD("fragment", "sequence", "payload"), &GameplayReplicationFragmenter::fragment);
	ClassDB::bind_method(D_METHOD("accept_fragment", "sender_peer_id", "fragment", "now_msec"), &GameplayReplicationFragmenter::accept_fragment);
	ClassDB::bind_method(D_METHOD("expire_assemblies", "now_msec"), &GameplayReplicationFragmenter::expire_assemblies);
	ClassDB::bind_method(D_METHOD("clear"), &GameplayReplicationFragmenter::clear);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "chunk_payload_bytes", PROPERTY_HINT_RANGE, "64,768,1"), "set_chunk_payload_bytes", "get_chunk_payload_bytes");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_transfer_bytes", PROPERTY_HINT_RANGE, "1,16777216,1"), "set_max_transfer_bytes", "get_max_transfer_bytes");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_chunks", PROPERTY_HINT_RANGE, "1,8192,1"), "set_max_chunks", "get_max_chunks");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_pending_assemblies", PROPERTY_HINT_RANGE, "1,256,1"), "set_max_pending_assemblies", "get_max_pending_assemblies");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "assembly_timeout_msec", PROPERTY_HINT_RANGE, "1,60000,1"), "set_assembly_timeout_msec", "get_assembly_timeout_msec");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "last_error", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_last_error");
	ADD_SIGNAL(MethodInfo("assembly_failed", PropertyInfo(Variant::STRING, "reason")));
}

void GameplayReplicationFragmenter::set_chunk_payload_bytes(int p_bytes) {
	ERR_FAIL_COND_MSG(p_bytes < 64 || p_bytes > 768, "Chunk payload must remain between 64 and 768 bytes to preserve the packet safety budget.");
	chunk_payload_bytes = p_bytes;
}

int GameplayReplicationFragmenter::get_chunk_payload_bytes() const {
	return chunk_payload_bytes;
}

void GameplayReplicationFragmenter::set_max_transfer_bytes(int p_bytes) {
	ERR_FAIL_COND_MSG(p_bytes < 1 || p_bytes > 16 * 1024 * 1024, "Transfer limit must be between 1 byte and 16 MiB.");
	max_transfer_bytes = p_bytes;
}

int GameplayReplicationFragmenter::get_max_transfer_bytes() const {
	return max_transfer_bytes;
}

void GameplayReplicationFragmenter::set_max_chunks(int p_chunks) {
	ERR_FAIL_COND_MSG(p_chunks < 1 || p_chunks > 8192, "Chunk count limit must be between 1 and 8192.");
	max_chunks = p_chunks;
}

int GameplayReplicationFragmenter::get_max_chunks() const {
	return max_chunks;
}

void GameplayReplicationFragmenter::set_max_pending_assemblies(int p_count) {
	ERR_FAIL_COND_MSG(p_count < 1 || p_count > 256, "Pending assembly limit must be between 1 and 256.");
	max_pending_assemblies = p_count;
}

int GameplayReplicationFragmenter::get_max_pending_assemblies() const {
	return max_pending_assemblies;
}

void GameplayReplicationFragmenter::set_assembly_timeout_msec(uint64_t p_timeout_msec) {
	ERR_FAIL_COND_MSG(p_timeout_msec < 1 || p_timeout_msec > 60000, "Assembly timeout must be between 1 and 60000 milliseconds.");
	assembly_timeout_msec = p_timeout_msec;
}

uint64_t GameplayReplicationFragmenter::get_assembly_timeout_msec() const {
	return assembly_timeout_msec;
}
String GameplayReplicationFragmenter::get_last_error() const {
	return last_error;
}
int GameplayReplicationFragmenter::get_pending_assembly_count() const {
	return assemblies.size();
}

Dictionary GameplayReplicationFragmenter::_reject(const String &p_reason) {
	last_error = p_reason;
	emit_signal(SNAME("assembly_failed"), p_reason);
	Dictionary result;
	result["status"] = "rejected";
	result["reason"] = p_reason;
	return result;
}

Array GameplayReplicationFragmenter::fragment(uint64_t p_sequence, const PackedByteArray &p_payload) {
	Array result;
	last_error.clear();
	if (p_sequence == 0) {
		last_error = "invalid_sequence";
		return result;
	}
	if (p_payload.is_empty() || p_payload.size() > max_transfer_bytes) {
		last_error = p_payload.is_empty() ? "empty_transfer" : "transfer_too_large";
		return result;
	}
	const int count = (p_payload.size() + chunk_payload_bytes - 1) / chunk_payload_bytes;
	if (count > max_chunks) {
		last_error = "too_many_chunks";
		return result;
	}
	for (int index = 0; index < count; index++) {
		const int offset = index * chunk_payload_bytes;
		const int length = MIN(chunk_payload_bytes, p_payload.size() - offset);
		PackedByteArray chunk;
		chunk.resize(length);
		memcpy(chunk.ptrw(), p_payload.ptr() + offset, length);
		Dictionary fragment_data;
		fragment_data["sequence"] = int64_t(p_sequence);
		fragment_data["chunk_index"] = index;
		fragment_data["chunk_count"] = count;
		fragment_data["total_size"] = p_payload.size();
		fragment_data["payload"] = chunk;
		result.push_back(fragment_data);
	}
	return result;
}

Dictionary GameplayReplicationFragmenter::accept_fragment(int p_sender_peer_id, const Dictionary &p_fragment, uint64_t p_now_msec) {
	const int64_t sequence_value = p_fragment.get("sequence", int64_t(0));
	const int chunk_index = p_fragment.get("chunk_index", -1);
	const int chunk_count = p_fragment.get("chunk_count", 0);
	const int total_size = p_fragment.get("total_size", 0);
	const Variant payload_variant = p_fragment.get("payload", Variant());
	if (p_sender_peer_id <= 0 || sequence_value <= 0 || chunk_count < 1 || chunk_count > max_chunks || chunk_index < 0 || chunk_index >= chunk_count || total_size < 1 || total_size > max_transfer_bytes || payload_variant.get_type() != Variant::PACKED_BYTE_ARRAY) {
		return _reject("invalid_fragment_header");
	}
	const uint64_t sequence = uint64_t(sequence_value);
	const uint64_t *completed = last_completed_sequence.getptr(p_sender_peer_id);
	if (completed && sequence <= *completed) {
		return _reject("stale_sequence");
	}
	const PackedByteArray payload = payload_variant;
	const int expected_count = (total_size + chunk_payload_bytes - 1) / chunk_payload_bytes;
	const int expected_size = chunk_index == chunk_count - 1 ? total_size - chunk_index * chunk_payload_bytes : chunk_payload_bytes;
	if (chunk_count != expected_count || payload.size() != expected_size || payload.size() > chunk_payload_bytes) {
		return _reject("invalid_fragment_size");
	}
	const String key = itos(p_sender_peer_id) + ":" + itos(sequence_value);
	Assembly *assembly = assemblies.getptr(key);
	if (!assembly) {
		if (assemblies.size() >= uint32_t(max_pending_assemblies)) {
			return _reject("too_many_pending_assemblies");
		}
		Assembly created;
		created.created_msec = p_now_msec;
		created.chunk_count = chunk_count;
		created.total_size = total_size;
		created.chunks.resize(chunk_count);
		created.received.resize(chunk_count);
		created.received.fill(0);
		assemblies.insert(key, created);
		assembly = assemblies.getptr(key);
	} else if (assembly->chunk_count != chunk_count || assembly->total_size != total_size) {
		assemblies.erase(key);
		return _reject("fragment_metadata_conflict");
	}
	if (assembly->received[chunk_index]) {
		if (assembly->chunks[chunk_index] != payload) {
			assemblies.erase(key);
			return _reject("conflicting_duplicate_fragment");
		}
		Dictionary duplicate;
		duplicate["status"] = "duplicate";
		return duplicate;
	}
	assembly->chunks.write[chunk_index] = payload;
	assembly->received.write[chunk_index] = 1;
	assembly->received_size += payload.size();
	if (assembly->received_size < assembly->total_size) {
		Dictionary pending;
		pending["status"] = "pending";
		return pending;
	}
	PackedByteArray complete;
	complete.resize(assembly->total_size);
	int offset = 0;
	for (int index = 0; index < assembly->chunk_count; index++) {
		if (!assembly->received[index]) {
			return _reject("incomplete_assembly");
		}
		const PackedByteArray &chunk = assembly->chunks[index];
		memcpy(complete.ptrw() + offset, chunk.ptr(), chunk.size());
		offset += chunk.size();
	}
	assemblies.erase(key);
	last_completed_sequence.insert(p_sender_peer_id, sequence);
	Dictionary complete_result;
	complete_result["status"] = "complete";
	complete_result["payload"] = complete;
	return complete_result;
}

int GameplayReplicationFragmenter::expire_assemblies(uint64_t p_now_msec) {
	Vector<String> expired;
	for (const KeyValue<String, Assembly> &entry : assemblies) {
		if (p_now_msec >= entry.value.created_msec + assembly_timeout_msec) {
			expired.push_back(entry.key);
		}
	}
	for (const String &key : expired) {
		assemblies.erase(key);
		emit_signal(SNAME("assembly_failed"), "missing_fragments");
	}
	if (!expired.is_empty()) {
		last_error = "missing_fragments";
	}
	return expired.size();
}

void GameplayReplicationFragmenter::clear() {
	assemblies.clear();
	last_completed_sequence.clear();
	last_error.clear();
}

void GameplayMultiplayerReplication::_bind_methods() {
	ClassDB::bind_method(D_METHOD("configure_server", "peer", "session_manager"), &GameplayMultiplayerReplication::configure_server);
	ClassDB::bind_method(D_METHOD("configure_client", "peer"), &GameplayMultiplayerReplication::configure_client);
	ClassDB::bind_method(D_METHOD("clear_transport"), &GameplayMultiplayerReplication::clear_transport);
	ClassDB::bind_method(D_METHOD("is_server"), &GameplayMultiplayerReplication::is_server);
	ClassDB::bind_method(D_METHOD("register_object", "object_id", "owner_peer_id", "state"), &GameplayMultiplayerReplication::register_object, DEFVAL(Ref<GameplayReplicationState>()));
	ClassDB::bind_method(D_METHOD("unregister_object", "object_id"), &GameplayMultiplayerReplication::unregister_object);
	ClassDB::bind_method(D_METHOD("set_object_owner_peer_id", "object_id", "owner_peer_id"), &GameplayMultiplayerReplication::set_object_owner_peer_id);
	ClassDB::bind_method(D_METHOD("get_object_owner_peer_id", "object_id"), &GameplayMultiplayerReplication::get_object_owner_peer_id);
	ClassDB::bind_method(D_METHOD("register_rpc", "object_id", "config", "handler"), &GameplayMultiplayerReplication::register_rpc);
	ClassDB::bind_method(D_METHOD("invoke_rpc", "object_id", "rpc_name", "arguments", "target_peer_id"), &GameplayMultiplayerReplication::invoke_rpc, DEFVAL(Array()), DEFVAL(0));
	ClassDB::bind_method(D_METHOD("replicate", "now_msec"), &GameplayMultiplayerReplication::replicate);
	ClassDB::bind_method(D_METHOD("receive_packet", "transport_sender_peer_id", "message", "now_msec"), &GameplayMultiplayerReplication::receive_packet);
	ClassDB::bind_method(D_METHOD("handles_message", "message"), &GameplayMultiplayerReplication::handles_message);
	ClassDB::bind_method(D_METHOD("expire_reassemblies", "now_msec"), &GameplayMultiplayerReplication::expire_reassemblies);
	ClassDB::bind_method(D_METHOD("set_fragmenter", "fragmenter"), &GameplayMultiplayerReplication::set_fragmenter);
	ClassDB::bind_method(D_METHOD("get_fragmenter"), &GameplayMultiplayerReplication::get_fragmenter);
	ClassDB::bind_method(D_METHOD("set_replication_graph", "graph"), &GameplayMultiplayerReplication::set_replication_graph);
	ClassDB::bind_method(D_METHOD("get_replication_graph"), &GameplayMultiplayerReplication::get_replication_graph);
	ClassDB::bind_method(D_METHOD("update_server_connection_view", "view"), &GameplayMultiplayerReplication::update_server_connection_view);
	ClassDB::bind_method(D_METHOD("set_object_dormant", "object_id", "dormant"), &GameplayMultiplayerReplication::set_object_dormant);
	ClassDB::bind_method(D_METHOD("wake_object", "object_id"), &GameplayMultiplayerReplication::wake_object);
	ClassDB::bind_method(D_METHOD("get_last_rejection_reason"), &GameplayMultiplayerReplication::get_last_rejection_reason);
	ClassDB::bind_method(D_METHOD("get_rejected_packet_count"), &GameplayMultiplayerReplication::get_rejected_packet_count);

	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "fragmenter", PROPERTY_HINT_RESOURCE_TYPE, "GameplayReplicationFragmenter"), "set_fragmenter", "get_fragmenter");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "replication_graph", PROPERTY_HINT_RESOURCE_TYPE, "GameplayReplicationGraph"), "set_replication_graph", "get_replication_graph");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "server", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_server");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "last_rejection_reason", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_last_rejection_reason");
	ADD_SIGNAL(MethodInfo("rpc_received", PropertyInfo(Variant::INT, "sender_peer_id"), PropertyInfo(Variant::INT, "object_id"), PropertyInfo(Variant::STRING_NAME, "rpc_name")));
	ADD_SIGNAL(MethodInfo("rpc_rejected", PropertyInfo(Variant::INT, "sender_peer_id"), PropertyInfo(Variant::STRING_NAME, "rpc_name"), PropertyInfo(Variant::STRING, "reason")));
	ADD_SIGNAL(MethodInfo("replication_applied", PropertyInfo(Variant::INT, "object_id")));
	ADD_SIGNAL(MethodInfo("replication_failed", PropertyInfo(Variant::STRING, "reason")));
	ADD_SIGNAL(MethodInfo("object_became_relevant", PropertyInfo(Variant::INT, "peer_id"), PropertyInfo(Variant::INT, "object_id")));
	ADD_SIGNAL(MethodInfo("object_became_irrelevant", PropertyInfo(Variant::INT, "peer_id"), PropertyInfo(Variant::INT, "object_id")));
	ADD_SIGNAL(MethodInfo("relevancy_rejected", PropertyInfo(Variant::INT, "sender_peer_id"), PropertyInfo(Variant::STRING, "reason")));
}

void GameplayMultiplayerReplication::configure_server(const Ref<MultiplayerPeer> &p_peer, GameplaySessionManager *p_session_manager) {
	ERR_FAIL_COND_MSG(p_peer.is_null() || !p_session_manager, "Server replication requires a peer and a session manager.");
	server = true;
	multiplayer_peer = p_peer;
	session_manager_id = p_session_manager->get_instance_id();
	if (fragmenter.is_null()) {
		fragmenter.instantiate();
	}
}

void GameplayMultiplayerReplication::configure_client(const Ref<MultiplayerPeer> &p_peer) {
	ERR_FAIL_COND_MSG(p_peer.is_null(), "Client replication requires a peer.");
	server = false;
	multiplayer_peer = p_peer;
	session_manager_id = ObjectID();
	if (fragmenter.is_null()) {
		fragmenter.instantiate();
	}
}

void GameplayMultiplayerReplication::clear_transport() {
	multiplayer_peer.unref();
	session_manager_id = ObjectID();
	if (fragmenter.is_valid()) {
		fragmenter->clear();
	}
	if (replication_graph.is_valid()) {
		const Array peer_ids = replication_graph->get_connection_peer_ids();
		for (int i = 0; i < peer_ids.size(); i++) {
			replication_graph->remove_connection(peer_ids[i]);
		}
	}
}

bool GameplayMultiplayerReplication::is_server() const {
	return server;
}

Error GameplayMultiplayerReplication::register_object(int p_object_id, int p_owner_peer_id, const Ref<GameplayReplicationState> &p_state) {
	ERR_FAIL_COND_V(p_object_id <= 0 || p_owner_peer_id < 0, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V_MSG(objects.has(p_object_id), ERR_ALREADY_EXISTS, "The replication object ID is already registered.");
	ObjectBinding binding;
	binding.owner_peer_id = p_owner_peer_id;
	binding.state = p_state;
	objects.insert(p_object_id, binding);
	return OK;
}

bool GameplayMultiplayerReplication::unregister_object(int p_object_id) {
	if (replication_graph.is_valid()) {
		replication_graph->remove_object(p_object_id);
	}
	return objects.erase(p_object_id);
}

Error GameplayMultiplayerReplication::set_object_owner_peer_id(int p_object_id, int p_owner_peer_id) {
	ObjectBinding *binding = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(binding, ERR_DOES_NOT_EXIST);
	ERR_FAIL_COND_V(p_owner_peer_id < 0, ERR_INVALID_PARAMETER);
	binding->owner_peer_id = p_owner_peer_id;
	if (replication_graph.is_valid() && replication_graph->has_object(p_object_id)) {
		replication_graph->set_object_owner_peer_id(p_object_id, p_owner_peer_id);
	}
	return OK;
}

int GameplayMultiplayerReplication::get_object_owner_peer_id(int p_object_id) const {
	const ObjectBinding *binding = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(binding, 0);
	return binding->owner_peer_id;
}

Error GameplayMultiplayerReplication::register_rpc(int p_object_id, const Ref<GameplayRPCConfig> &p_config, const Callable &p_handler) {
	ObjectBinding *binding = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(binding, ERR_DOES_NOT_EXIST);
	ERR_FAIL_COND_V(p_config.is_null() || p_config->get_rpc_name().is_empty() || !p_handler.is_valid(), ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V_MSG(binding->rpcs.has(p_config->get_rpc_name()), ERR_ALREADY_EXISTS, "The RPC is already registered for this object.");
	RPCBinding rpc;
	rpc.config = p_config;
	rpc.handler = p_handler;
	binding->rpcs.insert(p_config->get_rpc_name(), rpc);
	return OK;
}

bool GameplayMultiplayerReplication::_is_joined_peer(int p_peer_id) const {
	GameplaySessionManager *manager = Object::cast_to<GameplaySessionManager>(ObjectDB::get_instance(session_manager_id));
	if (!manager) {
		return false;
	}
	const Ref<GameplayConnection> connection = manager->get_connection(p_peer_id);
	GameplayUserSession *session = manager->get_session_by_peer(p_peer_id);
	return connection.is_valid() && connection->get_state() == GameplayConnection::STATE_SPAWNED && session && session->is_active() && session->get_peer_id() == p_peer_id;
}

Error GameplayMultiplayerReplication::_send_dictionary(int p_target_peer_id, const Dictionary &p_message, int *r_sent_bytes) {
	ERR_FAIL_COND_V(multiplayer_peer.is_null(), ERR_UNCONFIGURED);
	const CharString payload = JSON::stringify(p_message).utf8();
	ERR_FAIL_COND_V_MSG(payload.length() > 1200, ERR_INVALID_DATA, "Gameplay replication packet exceeds the explicit 1200-byte safety budget.");
	const MultiplayerPeer::TransferMode previous_mode = multiplayer_peer->get_transfer_mode();
	const int previous_channel = multiplayer_peer->get_transfer_channel();
	multiplayer_peer->set_transfer_mode(MultiplayerPeer::TRANSFER_MODE_RELIABLE);
	multiplayer_peer->set_transfer_channel(1);
	multiplayer_peer->set_target_peer(p_target_peer_id);
	const Error error = multiplayer_peer->put_packet(reinterpret_cast<const uint8_t *>(payload.get_data()), payload.length());
	multiplayer_peer->set_transfer_channel(previous_channel);
	multiplayer_peer->set_transfer_mode(previous_mode);
	if (r_sent_bytes) {
		*r_sent_bytes = error == OK ? payload.length() : 0;
	}
	return error;
}

Error GameplayMultiplayerReplication::_reject_rpc(int p_sender_peer_id, const StringName &p_rpc_name, const String &p_reason) {
	last_rejection_reason = p_reason;
	rejected_packet_count++;
	emit_signal(SNAME("rpc_rejected"), p_sender_peer_id, p_rpc_name, p_reason);
	return ERR_UNAUTHORIZED;
}

Error GameplayMultiplayerReplication::_reject_replication(const String &p_reason) {
	last_rejection_reason = p_reason;
	rejected_packet_count++;
	emit_signal(SNAME("replication_failed"), p_reason);
	return ERR_INVALID_DATA;
}

Error GameplayMultiplayerReplication::_reject_relevancy(int p_sender_peer_id, const String &p_reason) {
	last_rejection_reason = p_reason;
	rejected_packet_count++;
	emit_signal(SNAME("relevancy_rejected"), p_sender_peer_id, p_reason);
	return ERR_UNAUTHORIZED;
}

Error GameplayMultiplayerReplication::invoke_rpc(int p_object_id, const StringName &p_rpc_name, const Array &p_arguments, int p_target_peer_id) {
	ObjectBinding *object = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(object, ERR_DOES_NOT_EXIST);
	RPCBinding *rpc = object->rpcs.getptr(p_rpc_name);
	ERR_FAIL_NULL_V(rpc, ERR_DOES_NOT_EXIST);
	PackedByteArray encoded_arguments;
	const Error encode_error = _gameplay_encode_variant(p_arguments, encoded_arguments);
	ERR_FAIL_COND_V(encode_error != OK, encode_error);
	ERR_FAIL_COND_V_MSG(encoded_arguments.size() > rpc->config->get_max_payload_bytes(), ERR_INVALID_DATA, "RPC arguments exceed the configured payload limit.");

	if (!server && rpc->config->get_direction() != GameplayRPCConfig::DIRECTION_SERVER) {
		return _reject_rpc(multiplayer_peer.is_valid() ? multiplayer_peer->get_unique_id() : 0, p_rpc_name, "client_cannot_send_authority_rpc");
	}
	if (server && rpc->config->get_direction() == GameplayRPCConfig::DIRECTION_SERVER) {
		rpc->handler.callv(p_arguments);
		emit_signal(SNAME("rpc_received"), MultiplayerPeer::TARGET_PEER_SERVER, p_object_id, p_rpc_name);
		return OK;
	}

	Dictionary message;
	message["type"] = "gameplay_rpc";
	message["sender_peer_id"] = server ? MultiplayerPeer::TARGET_PEER_SERVER : multiplayer_peer->get_unique_id();
	message["object_id"] = p_object_id;
	message["rpc_name"] = p_rpc_name;
	message["payload"] = CryptoCore::b64_encode_str(encoded_arguments.ptr(), encoded_arguments.size());

	if (!server) {
		message["target_peer_id"] = MultiplayerPeer::TARGET_PEER_SERVER;
		return _send_dictionary(MultiplayerPeer::TARGET_PEER_SERVER, message);
	}

	const GameplayRPCConfig::Direction direction = rpc->config->get_direction();
	if (direction == GameplayRPCConfig::DIRECTION_OWNER) {
		p_target_peer_id = object->owner_peer_id;
	}
	if (direction == GameplayRPCConfig::DIRECTION_CLIENT || direction == GameplayRPCConfig::DIRECTION_OWNER) {
		ERR_FAIL_COND_V_MSG(p_target_peer_id <= 1 || !_is_joined_peer(p_target_peer_id), ERR_UNAUTHORIZED, "The RPC target is not an admitted gameplay connection.");
		message["target_peer_id"] = p_target_peer_id;
		return _send_dictionary(p_target_peer_id, message);
	}
	ERR_FAIL_COND_V(direction != GameplayRPCConfig::DIRECTION_MULTICAST, ERR_INVALID_PARAMETER);
	rpc->handler.callv(p_arguments);
	emit_signal(SNAME("rpc_received"), MultiplayerPeer::TARGET_PEER_SERVER, p_object_id, p_rpc_name);
	GameplaySessionManager *manager = Object::cast_to<GameplaySessionManager>(ObjectDB::get_instance(session_manager_id));
	ERR_FAIL_NULL_V(manager, ERR_UNCONFIGURED);
	message["target_peer_id"] = MultiplayerPeer::TARGET_PEER_BROADCAST;
	Error result = OK;
	const TypedArray<GameplayUserSession> sessions = manager->get_sessions();
	for (int i = 0; i < sessions.size(); i++) {
		GameplayUserSession *session = Object::cast_to<GameplayUserSession>(sessions[i]);
		if (session && session->is_active() && _is_joined_peer(session->get_peer_id())) {
			const Error send_error = _send_dictionary(session->get_peer_id(), message);
			if (send_error != OK) {
				result = send_error;
			}
		}
	}
	return result;
}

Error GameplayMultiplayerReplication::_handle_rpc(int p_transport_sender_peer_id, const Dictionary &p_message) {
	const int claimed_sender = p_message.get("sender_peer_id", 0);
	const int object_id = p_message.get("object_id", 0);
	const StringName rpc_name = p_message.get("rpc_name", StringName());
	const int target_peer_id = p_message.get("target_peer_id", 0);
	ObjectBinding *object = objects.getptr(object_id);
	if (!object) {
		return _reject_rpc(p_transport_sender_peer_id, rpc_name, "unknown_object");
	}
	RPCBinding *rpc = object->rpcs.getptr(rpc_name);
	if (!rpc) {
		return _reject_rpc(p_transport_sender_peer_id, rpc_name, "unknown_rpc");
	}
	if (claimed_sender != p_transport_sender_peer_id) {
		return _reject_rpc(p_transport_sender_peer_id, rpc_name, "sender_mismatch");
	}
	if (server) {
		if (!_is_joined_peer(p_transport_sender_peer_id)) {
			return _reject_rpc(p_transport_sender_peer_id, rpc_name, "sender_not_joined");
		}
		if (rpc->config->get_direction() != GameplayRPCConfig::DIRECTION_SERVER) {
			return _reject_rpc(p_transport_sender_peer_id, rpc_name, "client_claimed_authority_direction");
		}
		if (rpc->config->is_owner_required() && object->owner_peer_id != p_transport_sender_peer_id) {
			return _reject_rpc(p_transport_sender_peer_id, rpc_name, "gameplay_owner_mismatch");
		}
	} else {
		if (p_transport_sender_peer_id != MultiplayerPeer::TARGET_PEER_SERVER) {
			return _reject_rpc(p_transport_sender_peer_id, rpc_name, "non_server_authority_sender");
		}
		if (rpc->config->get_direction() == GameplayRPCConfig::DIRECTION_SERVER) {
			return _reject_rpc(p_transport_sender_peer_id, rpc_name, "unexpected_server_direction");
		}
		const int unique_id = multiplayer_peer.is_valid() ? multiplayer_peer->get_unique_id() : 0;
		if (rpc->config->get_direction() != GameplayRPCConfig::DIRECTION_MULTICAST && target_peer_id != unique_id) {
			return _reject_rpc(p_transport_sender_peer_id, rpc_name, "client_target_mismatch");
		}
		if (rpc->config->get_direction() == GameplayRPCConfig::DIRECTION_OWNER && object->owner_peer_id != unique_id) {
			return _reject_rpc(p_transport_sender_peer_id, rpc_name, "local_gameplay_owner_mismatch");
		}
	}

	const String encoded_payload = p_message.get("payload", String());
	const int max_encoded_size = ((rpc->config->get_max_payload_bytes() + 2) / 3) * 4;
	PackedByteArray encoded_arguments;
	if (encoded_payload.length() > max_encoded_size || _gameplay_decode_base64(encoded_payload, encoded_arguments) != OK || encoded_arguments.size() > rpc->config->get_max_payload_bytes()) {
		return _reject_rpc(p_transport_sender_peer_id, rpc_name, "invalid_rpc_payload");
	}
	Variant decoded;
	if (_gameplay_decode_variant(encoded_arguments, decoded) != OK || decoded.get_type() != Variant::ARRAY) {
		return _reject_rpc(p_transport_sender_peer_id, rpc_name, "invalid_rpc_arguments");
	}
	rpc->handler.callv(Array(decoded));
	emit_signal(SNAME("rpc_received"), p_transport_sender_peer_id, object_id, rpc_name);
	return OK;
}

Error GameplayMultiplayerReplication::_send_replication_payload(int p_peer_id, const Dictionary &p_payload, int *r_sent_bytes) {
	PackedByteArray encoded;
	const Error encode_error = _gameplay_encode_variant(p_payload, encoded);
	ERR_FAIL_COND_V(encode_error != OK, encode_error);
	ERR_FAIL_COND_V(fragmenter.is_null(), ERR_UNCONFIGURED);
	const uint64_t sequence = next_transfer_sequence++;
	const Array fragments = fragmenter->fragment(sequence, encoded);
	ERR_FAIL_COND_V_MSG(fragments.is_empty(), ERR_INVALID_DATA, fragmenter->get_last_error());
	int total_sent_bytes = 0;
	for (int i = 0; i < fragments.size(); i++) {
		const Dictionary fragment_data = fragments[i];
		const PackedByteArray bytes = fragment_data["payload"];
		Dictionary message;
		message["type"] = "gameplay_replication_chunk";
		message["sender_peer_id"] = MultiplayerPeer::TARGET_PEER_SERVER;
		message["sequence"] = fragment_data["sequence"];
		message["chunk_index"] = fragment_data["chunk_index"];
		message["chunk_count"] = fragment_data["chunk_count"];
		message["total_size"] = fragment_data["total_size"];
		message["payload"] = CryptoCore::b64_encode_str(bytes.ptr(), bytes.size());
		int fragment_sent_bytes = 0;
		const Error send_error = _send_dictionary(p_peer_id, message, &fragment_sent_bytes);
		if (send_error != OK) {
			if (r_sent_bytes) {
				*r_sent_bytes = total_sent_bytes;
			}
			return send_error;
		}
		total_sent_bytes += fragment_sent_bytes;
	}
	if (r_sent_bytes) {
		*r_sent_bytes = total_sent_bytes;
	}
	return OK;
}

Error GameplayMultiplayerReplication::replicate(uint64_t p_now_msec) {
	ERR_FAIL_COND_V(!server || multiplayer_peer.is_null(), ERR_UNCONFIGURED);
	GameplaySessionManager *manager = Object::cast_to<GameplaySessionManager>(ObjectDB::get_instance(session_manager_id));
	ERR_FAIL_NULL_V(manager, ERR_UNCONFIGURED);
	Error result = OK;
	const TypedArray<GameplayUserSession> sessions = manager->get_sessions();
	if (replication_graph.is_valid()) {
		for (const KeyValue<int, ObjectBinding> &entry : objects) {
			if (entry.value.state.is_valid() && replication_graph->has_object(entry.key) && replication_graph->is_object_dormant(entry.key)) {
				replication_graph->notify_object_dirty(entry.key, entry.value.state->get_change_serial());
			}
		}
	}
	for (int session_index = 0; session_index < sessions.size(); session_index++) {
		GameplayUserSession *session = Object::cast_to<GameplayUserSession>(sessions[session_index]);
		if (!session || !session->is_active() || !_is_joined_peer(session->get_peer_id())) {
			continue;
		}
		const int peer_id = session->get_peer_id();
		Array selected_objects;
		if (replication_graph.is_valid()) {
			if (!replication_graph->has_connection(peer_id)) {
				continue;
			}
			const Dictionary plan = replication_graph->plan_connection(peer_id, p_now_msec);
			const Array left = plan.get("left", Array());
			for (int i = 0; i < left.size(); i++) {
				ObjectBinding *binding = objects.getptr(left[i]);
				if (binding && binding->state.is_valid()) {
					binding->state->unregister_peer(peer_id);
				}
				emit_signal(SNAME("object_became_irrelevant"), peer_id, left[i]);
			}
			const Array entered = plan.get("entered", Array());
			for (int i = 0; i < entered.size(); i++) {
				ObjectBinding *binding = objects.getptr(entered[i]);
				if (binding && binding->state.is_valid()) {
					binding->state->register_peer(peer_id);
				}
				emit_signal(SNAME("object_became_relevant"), peer_id, entered[i]);
			}
			selected_objects = plan.get("selected", Array());
		} else {
			for (const KeyValue<int, ObjectBinding> &entry : objects) {
				selected_objects.push_back(entry.key);
			}
		}
		for (int object_index = 0; object_index < selected_objects.size(); object_index++) {
			const int object_id = selected_objects[object_index];
			ObjectBinding *entry = objects.getptr(object_id);
			if (!entry || entry->state.is_null()) {
				if (replication_graph.is_valid() && replication_graph->has_object(object_id)) {
					replication_graph->record_send_result(peer_id, object_id, p_now_msec, 0, true);
				}
				continue;
			}
			const Array updates = entry->state->collect_updates(peer_id, entry->owner_peer_id, p_now_msec);
			if (updates.is_empty()) {
				if (replication_graph.is_valid()) {
					replication_graph->record_send_result(peer_id, object_id, p_now_msec, 0, true);
				}
				continue;
			}
			Dictionary payload;
			payload["object_id"] = object_id;
			payload["updates"] = updates;
			int actual_sent_bytes = 0;
			const Error send_error = _send_replication_payload(peer_id, payload, &actual_sent_bytes);
			if (send_error != OK) {
				entry->state->reset_peer_updates(peer_id, updates);
				last_rejection_reason = fragmenter->get_last_error().is_empty() ? String("replication_send_failed") : fragmenter->get_last_error();
				emit_signal(SNAME("replication_failed"), last_rejection_reason);
				result = send_error;
			}
			if (replication_graph.is_valid()) {
				replication_graph->record_send_result(peer_id, object_id, p_now_msec, actual_sent_bytes, send_error == OK);
			}
		}
	}
	return result;
}

Error GameplayMultiplayerReplication::_handle_replication_chunk(int p_transport_sender_peer_id, const Dictionary &p_message, uint64_t p_now_msec) {
	if (server) {
		return _reject_replication("client_cannot_replicate_authority_state");
	}
	if (p_transport_sender_peer_id != MultiplayerPeer::TARGET_PEER_SERVER || int(p_message.get("sender_peer_id", 0)) != MultiplayerPeer::TARGET_PEER_SERVER) {
		return _reject_replication("replication_sender_not_server");
	}
	const String encoded_payload = p_message.get("payload", String());
	const int max_encoded_size = ((fragmenter->get_chunk_payload_bytes() + 2) / 3) * 4;
	PackedByteArray decoded_payload;
	if (encoded_payload.length() > max_encoded_size || _gameplay_decode_base64(encoded_payload, decoded_payload) != OK) {
		return _reject_replication("invalid_fragment_encoding");
	}
	Dictionary fragment_data;
	fragment_data["sequence"] = p_message.get("sequence", int64_t(0));
	fragment_data["chunk_index"] = p_message.get("chunk_index", -1);
	fragment_data["chunk_count"] = p_message.get("chunk_count", 0);
	fragment_data["total_size"] = p_message.get("total_size", 0);
	fragment_data["payload"] = decoded_payload;
	const Dictionary result = fragmenter->accept_fragment(p_transport_sender_peer_id, fragment_data, p_now_msec);
	const String status = result.get("status", String());
	if (status == "pending" || status == "duplicate") {
		return OK;
	}
	if (status != "complete") {
		return _reject_replication(result.get("reason", String("fragment_rejected")));
	}
	Variant decoded;
	if (_gameplay_decode_variant(result["payload"], decoded) != OK || decoded.get_type() != Variant::DICTIONARY) {
		return _reject_replication("invalid_replication_payload");
	}
	const Dictionary payload = decoded;
	const int object_id = payload.get("object_id", 0);
	ObjectBinding *object = objects.getptr(object_id);
	if (!object || object->state.is_null()) {
		return _reject_replication("unknown_replication_object");
	}
	const Variant updates_variant = payload.get("updates", Variant());
	if (updates_variant.get_type() != Variant::ARRAY || object->state->apply_updates(updates_variant) != OK) {
		return _reject_replication("invalid_replication_updates");
	}
	emit_signal(SNAME("replication_applied"), object_id);
	return OK;
}

Error GameplayMultiplayerReplication::receive_packet(int p_transport_sender_peer_id, const Dictionary &p_message, uint64_t p_now_msec) {
	const String type = p_message.get("type", String());
	if (type == "gameplay_relevancy_control") {
		return _reject_relevancy(p_transport_sender_peer_id, server ? String("client_cannot_control_relevancy") : String("server_does_not_delegate_relevancy"));
	}
	if (type == "gameplay_rpc") {
		return _handle_rpc(p_transport_sender_peer_id, p_message);
	}
	if (type == "gameplay_replication_chunk") {
		return _handle_replication_chunk(p_transport_sender_peer_id, p_message, p_now_msec);
	}
	return ERR_DOES_NOT_EXIST;
}

bool GameplayMultiplayerReplication::handles_message(const Dictionary &p_message) const {
	const String type = p_message.get("type", String());
	return type == "gameplay_rpc" || type == "gameplay_replication_chunk" || type == "gameplay_relevancy_control";
}

void GameplayMultiplayerReplication::expire_reassemblies(uint64_t p_now_msec) {
	if (fragmenter.is_valid() && fragmenter->expire_assemblies(p_now_msec) > 0) {
		last_rejection_reason = fragmenter->get_last_error();
		emit_signal(SNAME("replication_failed"), last_rejection_reason);
	}
}

void GameplayMultiplayerReplication::set_fragmenter(const Ref<GameplayReplicationFragmenter> &p_fragmenter) {
	ERR_FAIL_COND(p_fragmenter.is_null());
	fragmenter = p_fragmenter;
}

Ref<GameplayReplicationFragmenter> GameplayMultiplayerReplication::get_fragmenter() const {
	return fragmenter;
}

Error GameplayMultiplayerReplication::set_replication_graph(const Ref<GameplayReplicationGraph> &p_graph) {
	ERR_FAIL_COND_V(p_graph.is_null(), ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V_MSG(multiplayer_peer.is_valid() && !server, ERR_UNAUTHORIZED, "Only a configured server may install a replication graph.");
	replication_graph = p_graph;
	return OK;
}

Ref<GameplayReplicationGraph> GameplayMultiplayerReplication::get_replication_graph() const {
	return replication_graph;
}

Error GameplayMultiplayerReplication::update_server_connection_view(const Ref<GameplayConnectionView> &p_view) {
	ERR_FAIL_COND_V(!server || replication_graph.is_null() || p_view.is_null(), ERR_UNCONFIGURED);
	ERR_FAIL_COND_V_MSG(!_is_joined_peer(p_view->get_peer_id()), ERR_UNAUTHORIZED, "Only an admitted server-side connection may receive a connection view.");
	return replication_graph->has_connection(p_view->get_peer_id()) ? replication_graph->update_connection(p_view) : replication_graph->add_connection(p_view);
}

Error GameplayMultiplayerReplication::set_object_dormant(int p_object_id, bool p_dormant) {
	ERR_FAIL_COND_V(!server || replication_graph.is_null(), ERR_UNCONFIGURED);
	ObjectBinding *object = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(object, ERR_DOES_NOT_EXIST);
	ERR_FAIL_COND_V(!replication_graph->has_object(p_object_id), ERR_DOES_NOT_EXIST);
	const uint64_t change_serial_value = object->state.is_valid() ? object->state->get_change_serial() : 0;
	return replication_graph->set_object_dormant(p_object_id, p_dormant, change_serial_value);
}

Error GameplayMultiplayerReplication::wake_object(int p_object_id) {
	ERR_FAIL_COND_V(!server || replication_graph.is_null(), ERR_UNCONFIGURED);
	return replication_graph->wake_object(p_object_id);
}

String GameplayMultiplayerReplication::get_last_rejection_reason() const {
	return last_rejection_reason;
}

int GameplayMultiplayerReplication::get_rejected_packet_count() const {
	return rejected_packet_count;
}
