/**************************************************************************/
/*  ai_chat_external_peer.h                                                */
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

#include "core/templates/vector.h"
#include "core/variant/dictionary.h"
#include "core/variant/variant.h"

// The only authorization entry is verify(), which collects facts from the kernel
// and Security.framework. The typed chain validator grants no socket capability.
class AIChatExternalPeer {
public:
	enum CodeKind {
		UNKNOWN,
		APPLE_PLATFORM,
		OPENAI_CLI,
		OPENAI_DESKTOP,
		GODOT,
	};

	struct Process {
		int pid = 0;
		int ppid = 0;
		uint32_t uid = 0;
		uint32_t real_uid = 0;
		uint32_t saved_uid = 0;
		uint64_t birth_sec = 0;
		uint64_t birth_usec = 0;
		CodeKind code = UNKNOWN;
		String fingerprint;
	};

	static Dictionary validate_chain(const Vector<Process> &p_before, const Vector<Process> &p_after, uint32_t p_uid, int p_engine_pid);
	static Dictionary verify(int p_socket_fd, int p_engine_pid);
};
