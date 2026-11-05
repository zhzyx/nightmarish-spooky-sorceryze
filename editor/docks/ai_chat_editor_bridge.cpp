/**************************************************************************/
/*  ai_chat_editor_bridge.cpp                                              */
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

#include "ai_chat_editor_bridge.h"

#include "core/config/project_settings.h"
#include "core/crypto/crypto_core.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/settings/editor_settings.h"

namespace {
Dictionary bridge_error(const String &p_error) {
	Dictionary result;
	result["ok"] = false;
	result["error"] = p_error;
	return result;
}

String header_value(const HashMap<String, String> &p_headers, const String &p_key, const String &p_default = String()) {
	const String *value = p_headers.getptr(p_key);
	return value ? *value : p_default;
}

String parameter(const String &p_query, const String &p_name, const String &p_default = String()) {
	for (const String &part : p_query.split("&")) {
		const int equal = part.find_char('=');
		if (equal > 0 && part.substr(0, equal) == p_name) {
			return part.substr(equal + 1).uri_decode().left(1024);
		}
	}
	return p_default;
}
} // namespace

void AIChatEditorBridge::_start() {
	if (!bool(EDITOR_GET("ai_chat/editor_control_bridge_enabled"))) {
		return;
	}
	uint8_t random[48];
	if (CryptoCore::generate_random(random, sizeof(random)) != OK) {
		return;
	}
	token = String::hex_encode_buffer(random, 32);
	session = String::hex_encode_buffer(random + 32, 16);
	server.instantiate();
	if (server->listen(0, IPAddress("127.0.0.1")) != OK) {
		server.unref();
		token = String();
		return;
	}
	port = server->get_local_port();
	const String folder = ProjectSettings::get_singleton()->globalize_path("res://.godot/editor/ai_control");
	if (DirAccess::make_dir_recursive_absolute(folder) != OK) {
		_stop();
		return;
	}
	descriptor = folder.path_join(itos(OS::get_singleton()->get_process_id()) + ".json");
	Ref<FileAccess> file = FileAccess::open(descriptor, FileAccess::WRITE);
	if (file.is_null()) {
		_stop();
		return;
	}
#ifndef WINDOWS_ENABLED
	if (FileAccess::set_unix_permissions(descriptor, FileAccess::UNIX_READ_OWNER | FileAccess::UNIX_WRITE_OWNER) != OK) {
		file->close();
		_stop();
		return;
	}
#endif
	Dictionary discovery;
	discovery["protocol_version"] = 1;
	discovery["project"] = ProjectSettings::get_singleton()->get_resource_path();
	discovery["pid"] = OS::get_singleton()->get_process_id();
	discovery["session"] = session;
	discovery["url"] = "http://127.0.0.1:" + itos(port);
	discovery["token"] = token;
	discovery["routing"] = "When the user intends an engine operation, discover targets, then POST /v1/messages with intent=engine_operation, request_id, source and a declarative operation. Natural language alone returns planning_required, never an execution claim.";
	if (!file->store_string(JSON::stringify(discovery)) || file->get_error() != OK) {
		file->close();
		_stop();
		return;
	}
	file->close();
	set_process(true);
}

void AIChatEditorBridge::_stop() {
	set_process(false);
	for (Client &client : clients) {
		client.peer->disconnect_from_host();
	}
	clients.clear();
	if (server.is_valid()) {
		server->stop();
		server.unref();
	}
	if (!descriptor.is_empty() && FileAccess::exists(descriptor)) {
		const Variant value = JSON::parse_string(FileAccess::get_file_as_string(descriptor));
		if (value.get_type() == Variant::DICTIONARY && Dictionary(value).get("session", "") == session) {
			DirAccess::remove_absolute(descriptor);
		}
	}
	token = String();
	session = String();
	descriptor = String();
}

void AIChatEditorBridge::_respond(Client &p_client, int p_status, const Dictionary &p_result) {
	const CharString body = JSON::stringify(p_result).utf8();
	const String reason = p_status == 200 ? "OK" : p_status == 202 ? "Accepted"
			: p_status == 401									   ? "Unauthorized"
			: p_status == 403									   ? "Forbidden"
			: p_status == 404									   ? "Not Found"
			: p_status == 409									   ? "Conflict"
			: p_status == 413									   ? "Payload Too Large"
																   : "Bad Request";
	const CharString header = ("HTTP/1.1 " + itos(p_status) + " " + reason + "\r\nContent-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: " + itos(body.length()) + "\r\n\r\n").utf8();
	p_client.output.resize(header.length() + body.length());
	memcpy(p_client.output.ptrw(), header.get_data(), header.length());
	memcpy(p_client.output.ptrw() + header.length(), body.get_data(), body.length());
}

void AIChatEditorBridge::_dispatch(Client &p_client) {
	int end = -1;
	for (int i = 0; i + 3 < p_client.input.size(); i++) {
		if (p_client.input[i] == '\r' && p_client.input[i + 1] == '\n' && p_client.input[i + 2] == '\r' && p_client.input[i + 3] == '\n') {
			end = i;
			break;
		}
	}
	if (end < 0) {
		if (p_client.input.size() > 8192) {
			_respond(p_client, 413, bridge_error("headers_too_large"));
		}
		return;
	}
	if (end > 8192) {
		_respond(p_client, 413, bridge_error("headers_too_large"));
		return;
	}
	const String text = String::utf8(reinterpret_cast<const char *>(p_client.input.ptr()), end);
	const PackedStringArray lines = text.substr(0, end).split("\r\n");
	const PackedStringArray request_line = lines[0].split(" ");
	if (request_line.size() != 3 || request_line[2] != "HTTP/1.1") {
		_respond(p_client, 400, bridge_error("invalid_http_request"));
		return;
	}
	HashMap<String, String> headers;
	for (int i = 1; i < lines.size(); i++) {
		const int colon = lines[i].find_char(':');
		const String key = lines[i].substr(0, colon).to_lower();
		if (colon <= 0 || headers.has(key)) {
			_respond(p_client, 400, bridge_error("invalid_http_headers"));
			return;
		}
		headers[key] = lines[i].substr(colon + 1).strip_edges();
	}
	if (headers.has("origin") || headers.has("transfer-encoding") || header_value(headers, "host") != "127.0.0.1:" + itos(port)) {
		_respond(p_client, 403, bridge_error("invalid_request_origin"));
		return;
	}
	if (header_value(headers, "authorization") != "Bearer " + token || header_value(headers, "x-godot-session") != session) {
		_respond(p_client, 401, bridge_error("invalid_editor_session"));
		return;
	}
	const String length = header_value(headers, "content-length", "0");
	if (length.length() > 5 || !length.is_valid_int() || length.to_int() < 0 || length.to_int() > 32768) {
		_respond(p_client, 413, bridge_error("message_too_large"));
		return;
	}
	const int header_bytes = end + 4;
	const int body_length = length.to_int();
	if (p_client.input.size() < header_bytes + body_length) {
		return;
	}
	if (p_client.input.size() != header_bytes + body_length) {
		_respond(p_client, 400, bridge_error("http_pipelining_forbidden"));
		return;
	}
	const int question = request_line[1].find_char('?');
	const String path = request_line[1].get_slice("?", 0);
	const String query = question < 0 ? String() : request_line[1].substr(question + 1);
	Dictionary envelope;
	if (request_line[0] == "GET" && body_length == 0 && path == "/v1/capabilities") {
		envelope["kind"] = "capabilities";
		envelope["query"] = parameter(query, "query");
	} else if (request_line[0] == "GET" && body_length == 0 && path == "/v1/requests") {
		envelope["kind"] = "status";
		envelope["request_id"] = parameter(query, "id");
		envelope["source"] = parameter(query, "source", "external-ai");
	} else if (request_line[0] == "POST" && path == "/v1/messages" && header_value(headers, "content-type").get_slice(";", 0) == "application/json") {
		JSON json;
		if (json.parse(String::utf8(reinterpret_cast<const char *>(p_client.input.ptr() + header_bytes), body_length)) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
			_respond(p_client, 400, bridge_error("invalid_json_message"));
			return;
		}
		envelope["kind"] = "message";
		envelope["message"] = json.get_data();
	} else {
		_respond(p_client, 404, bridge_error("unknown_editor_endpoint"));
		return;
	}
	const Variant value = handler.call(envelope);
	if (value.get_type() != Variant::DICTIONARY) {
		_respond(p_client, 400, bridge_error("editor_handler_unavailable"));
		return;
	}
	Dictionary result = value;
	result["session"] = session;
	const String error = result.get("error", "");
	const int status = result.get("routing_status", "") == "awaiting_confirmation" ? 202 : bool(result.get("ok", false)) ? 200
			: error == "editor_busy" || error == "request_id_conflict"													 ? 409
			: error == "unknown_request"																				 ? 404
			: error == "permission_denied"																				 ? 403
																														 : 400;
	_respond(p_client, status, result);
}

void AIChatEditorBridge::_poll() {
	if (server.is_null()) {
		return;
	}
	if (server->is_connection_available()) {
		Ref<StreamPeerTCP> peer = server->take_connection();
		if (peer.is_valid()) {
			if (clients.size() < 8) {
				Client client;
				client.peer = peer;
				client.started = Time::get_singleton()->get_ticks_msec();
				clients.push_back(client);
			} else {
				peer->disconnect_from_host();
			}
		}
	}
	for (int i = clients.size() - 1; i >= 0; i--) {
		Client &client = clients.write[i];
		client.peer->poll();
		bool closed = client.peer->get_status() != StreamPeerSocket::STATUS_CONNECTED || Time::get_singleton()->get_ticks_msec() - client.started > 5000;
		if (!closed && client.output.is_empty()) {
			const int available = MIN(client.peer->get_available_bytes(), 4096);
			if (available > 0) {
				if (client.input.size() + available > 40960) {
					_respond(client, 413, bridge_error("message_too_large"));
				} else {
					uint8_t buffer[4096];
					int received = 0;
					if (client.peer->get_partial_data(buffer, available, received) != OK) {
						closed = true;
					} else {
						const int offset = client.input.size();
						client.input.resize(offset + received);
						memcpy(client.input.ptrw() + offset, buffer, received);
						_dispatch(client);
					}
				}
			}
		}
		if (!closed && !client.output.is_empty()) {
			int sent = 0;
			if (client.peer->put_partial_data(client.output.ptr() + client.sent, client.output.size() - client.sent, sent) != OK) {
				closed = true;
			} else {
				client.sent += sent;
				closed = client.sent == client.output.size();
			}
		}
		if (closed) {
			client.peer->disconnect_from_host();
			clients.remove_at(i);
		}
	}
}

void AIChatEditorBridge::_notification(int p_what) {
	if (p_what == NOTIFICATION_READY) {
		_start();
	} else if (p_what == NOTIFICATION_PROCESS) {
		_poll();
	} else if (p_what == NOTIFICATION_EXIT_TREE) {
		_stop();
	}
}

AIChatEditorBridge::~AIChatEditorBridge() {
	_stop();
}
