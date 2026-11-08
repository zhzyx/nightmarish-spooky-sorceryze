/**************************************************************************/
/*  ai_chat_editor_instruction_bridge.cpp                                 */
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

#include "core/io/json.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/docks/ai_chat_editor_bridge.h"
#include "editor/docks/ai_chat_external_peer.h"

#ifdef MACOS_ENABLED
#include <fcntl.h>
#include <limits.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

#include <cerrno>
#include <cstdlib>

namespace {
Dictionary instruction_error(const String &p_error) {
	Dictionary result;
	result["ok"] = false;
	result["error"] = p_error;
	return result;
}

PackedByteArray instruction_reply(const Dictionary &p_result) {
	Dictionary result = p_result.duplicate(true);
	result["protocol_version"] = 1;
	result["engine_pid"] = OS::get_singleton()->get_process_id();
	return (JSON::stringify(result) + "\n").to_utf8_buffer();
}

bool instruction_fd(int p_fd) {
	const int flags = fcntl(p_fd, F_GETFL);
	const int signal_option = 1;
	return flags >= 0 && fcntl(p_fd, F_SETFL, flags | O_NONBLOCK) == 0 && fcntl(p_fd, F_SETFD, FD_CLOEXEC) == 0 && setsockopt(p_fd, SOL_SOCKET, SO_NOSIGPIPE, &signal_option, sizeof(signal_option)) == 0;
}
} // namespace
#endif

void AIChatEditorBridge::_start_instructions() {
#ifdef MACOS_ENABLED
	if (!instruction_handler.is_valid()) {
		return;
	}
	// Short and local: project and Application Support paths may exceed sun_path.
	char directory_template[] = "/private/tmp/gonggong-chat-XXXXXX";
	char *created = mkdtemp(directory_template);
	if (!created) {
		return;
	}
	instruction_directory = String::utf8(created);
	struct stat directory_info = {};
	char resolved[PATH_MAX];
	if (!realpath(created, resolved) || instruction_directory != String::utf8(resolved) || lstat(created, &directory_info) != 0 || !S_ISDIR(directory_info.st_mode) || directory_info.st_uid != getuid() || (directory_info.st_mode & 077) != 0) {
		_stop_instructions();
		return;
	}
	instruction_directory_inode = directory_info.st_ino;
	instruction_directory_device = directory_info.st_dev;
	instruction_directory_fd = open(created, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	instruction_socket = instruction_directory.path_join("instruction.sock");
	struct sockaddr_un address = {};
	address.sun_family = AF_UNIX;
	const CharString path = instruction_socket.utf8();
	if (instruction_directory_fd < 0 || path.length() >= int(sizeof(address.sun_path))) {
		_stop_instructions();
		return;
	}
	memcpy(address.sun_path, path.get_data(), path.length() + 1);
	instruction_server = socket(AF_UNIX, SOCK_STREAM, 0);
	if (instruction_server < 0 || !instruction_fd(instruction_server) || bind(instruction_server, reinterpret_cast<sockaddr *>(&address), sizeof(address)) != 0) {
		_stop_instructions();
		return;
	}
	struct stat socket_info = {};
	if (fstatat(instruction_directory_fd, "instruction.sock", &socket_info, AT_SYMLINK_NOFOLLOW) != 0 || !S_ISSOCK(socket_info.st_mode) || socket_info.st_uid != getuid()) {
		_stop_instructions();
		return;
	}
	instruction_inode = socket_info.st_ino;
	instruction_device = socket_info.st_dev;
	if (fchmodat(instruction_directory_fd, "instruction.sock", 0600, AT_SYMLINK_NOFOLLOW) != 0 || listen(instruction_server, 8) != 0) {
		_stop_instructions();
	}
#endif
}

void AIChatEditorBridge::_stop_instructions() {
#ifdef MACOS_ENABLED
	for (InstructionClient &client : instruction_clients) {
		close(client.fd);
	}
	instruction_clients.clear();
	if (instruction_server >= 0) {
		close(instruction_server);
		instruction_server = -1;
	}
	struct stat info = {};
	if (instruction_directory_fd >= 0) {
		if (fstatat(instruction_directory_fd, "instruction.sock", &info, AT_SYMLINK_NOFOLLOW) == 0 && S_ISSOCK(info.st_mode) && uint64_t(info.st_ino) == instruction_inode && uint64_t(info.st_dev) == instruction_device) {
			unlinkat(instruction_directory_fd, "instruction.sock", 0);
		}
		close(instruction_directory_fd);
		instruction_directory_fd = -1;
	}
	if (!instruction_directory.is_empty() && lstat(instruction_directory.utf8().get_data(), &info) == 0 && S_ISDIR(info.st_mode) && uint64_t(info.st_ino) == instruction_directory_inode && uint64_t(info.st_dev) == instruction_directory_device) {
		rmdir(instruction_directory.utf8().get_data());
	}
	instruction_directory = String();
	instruction_socket = String();
	instruction_inode = 0;
	instruction_device = 0;
	instruction_directory_inode = 0;
	instruction_directory_device = 0;
#endif
}

void AIChatEditorBridge::_poll_instructions() {
#ifdef MACOS_ENABLED
	if (instruction_server < 0) {
		return;
	}
	const int incoming = accept(instruction_server, nullptr, nullptr);
	if (incoming >= 0) {
		if (instruction_clients.size() >= 8 || !instruction_fd(incoming)) {
			close(incoming);
		} else {
			InstructionClient client;
			client.fd = incoming;
			client.started = Time::get_singleton()->get_ticks_msec();
			const Dictionary identity = AIChatExternalPeer::verify(incoming, OS::get_singleton()->get_process_id());
			if (!bool(identity.get("ok", false))) {
				client.output = instruction_reply(identity);
			}
			instruction_clients.push_back(client);
		}
	}
	for (int i = instruction_clients.size() - 1; i >= 0; i--) {
		InstructionClient &client = instruction_clients.write[i];
		bool closed = Time::get_singleton()->get_ticks_msec() - client.started > 5000;
		if (!closed && client.output.is_empty()) {
			uint8_t buffer[4096];
			const ssize_t received = recv(client.fd, buffer, sizeof(buffer), 0);
			if (received == 0 || (received < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)) {
				closed = true;
			} else if (received > 0) {
				const int offset = client.input.size();
				if (offset + received > 32768) {
					client.output = instruction_reply(instruction_error("message_too_large"));
				} else {
					client.input.resize(offset + received);
					memcpy(client.input.ptrw() + offset, buffer, received);
					int newline = -1;
					for (int j = offset; j < client.input.size(); j++) {
						if (client.input[j] == '\n') {
							newline = j;
							break;
						}
					}
					if (newline >= 0) {
						JSON json;
						const Dictionary identity = AIChatExternalPeer::verify(client.fd, OS::get_singleton()->get_process_id());
						if (!bool(identity.get("ok", false))) {
							client.output = instruction_reply(identity);
						} else if (newline != client.input.size() - 1 || json.parse(String::utf8(reinterpret_cast<const char *>(client.input.ptr()), newline)) != OK || json.get_data().get_type() != Variant::DICTIONARY) {
							client.output = instruction_reply(instruction_error("invalid_instruction_message"));
						} else {
							const Variant value = instruction_handler.call(json.get_data());
							Dictionary result = value.get_type() == Variant::DICTIONARY ? Dictionary(value) : instruction_error("instruction_handler_unavailable");
							result["authenticated_desktop_peer"] = true;
							result["peer_pid"] = identity["peer_pid"];
							result["trusted_desktop_pid"] = identity["trusted_desktop_pid"];
							client.output = instruction_reply(result);
						}
					}
				}
			}
		}
		if (!closed && !client.output.is_empty()) {
			const ssize_t sent = send(client.fd, client.output.ptr() + client.sent, client.output.size() - client.sent, 0);
			if (sent > 0) {
				client.sent += sent;
				closed = client.sent == client.output.size();
			} else if (sent < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) {
				closed = true;
			}
		}
		if (closed) {
			close(client.fd);
			instruction_clients.remove_at(i);
		}
	}
#endif
}
