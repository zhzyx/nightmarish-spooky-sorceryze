/**************************************************************************/
/*  ai_chat_editor_bridge.h                                               */
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

#pragma once

#include "core/io/stream_peer_tcp.h"
#include "core/io/tcp_server.h"
#include "scene/main/node.h"

// Loopback-only, bounded HTTP transport. All callbacks run on the editor thread.
class AIChatEditorBridge : public Node {
	GDCLASS(AIChatEditorBridge, Node);

	struct Client {
		Ref<StreamPeerTCP> peer;
		PackedByteArray input;
		PackedByteArray output;
		int sent = 0;
		uint64_t started = 0;
	};
	Ref<TCPServer> server;
	Vector<Client> clients;
	Callable handler;
	Callable instruction_handler;
	String token;
	String session;
	String descriptor;
	int port = 0;
#ifdef MACOS_ENABLED
	struct InstructionClient {
		int fd = -1;
		PackedByteArray input;
		PackedByteArray output;
		int sent = 0;
		uint64_t started = 0;
	};
	int instruction_server = -1;
	int instruction_directory_fd = -1;
	String instruction_directory;
	String instruction_socket;
	uint64_t instruction_directory_inode = 0;
	uint64_t instruction_directory_device = 0;
	uint64_t instruction_inode = 0;
	uint64_t instruction_device = 0;
	Vector<InstructionClient> instruction_clients;
#endif
	void _start_instructions();
	void _stop_instructions();
	void _poll_instructions();

	void _poll();
	void _dispatch(Client &p_client);
	void _respond(Client &p_client, int p_status, const Dictionary &p_result);
	void _start();
	void _stop();

protected:
	void _notification(int p_what);

public:
	void set_handler(const Callable &p_handler) { handler = p_handler; }
	void set_instruction_handler(const Callable &p_handler) { instruction_handler = p_handler; }
	~AIChatEditorBridge();
};
