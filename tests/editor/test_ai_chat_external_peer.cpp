/**************************************************************************/
/*  test_ai_chat_external_peer.cpp                                                */
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

#include "tests/test_macros.h"

TEST_FORCE_LINK(test_ai_chat_external_peer)

#ifdef TOOLS_ENABLED
#include "editor/docks/ai_chat_external_peer.h"

#ifdef MACOS_ENABLED
#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cstdlib>
#include <cstring>
#endif

namespace TestAIChatExternalPeer {
using Peer = AIChatExternalPeer;

static Vector<Peer::Process> normal_chain() {
	Vector<Peer::Process> chain;
	for (int i = 0; i < 3; i++) {
		Peer::Process process;
		process.pid = 80 - i * 10;
		process.ppid = i == 2 ? 1 : process.pid - 10;
		process.uid = process.real_uid = process.saved_uid = 501;
		process.birth_sec = 400 - i * 100;
		process.code = i == 0 ? Peer::APPLE_PLATFORM : i == 1 ? Peer::OPENAI_CLI
															  : Peer::OPENAI_DESKTOP;
		process.fingerprint = "actual-code-digest";
		chain.push_back(process);
	}
	return chain;
}

TEST_CASE("[Editor][AIChat][ExternalPeer] Stable kernel chain requires the official desktop") {
	const Vector<Peer::Process> chain = normal_chain();
	Dictionary result = Peer::validate_chain(chain, chain, 501, 90);
	CHECK(bool(result["ok"]));
	CHECK(int(result["peer_pid"]) == 80);
	CHECK(int(result["trusted_desktop_pid"]) == 60);
	Vector<Peer::Process> changed = chain;
	changed.write[2].code = Peer::OPENAI_CLI;
	CHECK_FALSE(bool(Peer::validate_chain(changed, changed, 501, 90)["ok"]));
}

TEST_CASE("[Editor][AIChat][ExternalPeer] Ancestor identity and permissions fail closed") {
	const Vector<Peer::Process> original = normal_chain();
	Vector<Peer::Process> before = original;
	Vector<Peer::Process> after = original;
	SUBCASE("PID reuse birth changed") {
		after.write[0].birth_sec++;
	}
	SUBCASE("parent changed") {
		after.write[1].ppid = 1;
	}
	SUBCASE("code exec changed") {
		after.write[0].fingerprint = "other-code";
	}
	SUBCASE("code class changed") {
		after.write[1].code = Peer::UNKNOWN;
	}
	SUBCASE("effective UID changed") {
		after.write[0].uid = 502;
	}
	SUBCASE("real UID differs") {
		before.write[0].real_uid = after.write[0].real_uid = 502;
	}
	SUBCASE("saved UID differs") {
		before.write[1].saved_uid = after.write[1].saved_uid = 502;
	}
	SUBCASE("unknown or adhoc intermediate") {
		before.write[1].code = after.write[1].code = Peer::UNKNOWN;
	}
	SUBCASE("empty code fingerprint") {
		before.write[0].fingerprint = "";
		after.write[0].fingerprint = "";
	}
	SUBCASE("zero birth") {
		before.write[0].birth_sec = after.write[0].birth_sec = 0;
	}
	SUBCASE("invalid birth microseconds") {
		before.write[0].birth_usec = after.write[0].birth_usec = 1000000;
	}
	SUBCASE("parent younger than child") {
		before.write[1].birth_sec = after.write[1].birth_sec = 500;
	}
	SUBCASE("broken parent link") {
		before.write[1].ppid = after.write[1].ppid = 1;
	}
	SUBCASE("cycle") {
		before.write[2].pid = after.write[2].pid = 80;
	}
	SUBCASE("truncated chain") {
		before.resize(2);
		after.resize(2);
	}
	SUBCASE("different chain lengths") {
		after.resize(2);
	}
	SUBCASE("last actual ancestor changes UID") {
		before.write[2].uid = after.write[2].uid = 502;
	}
	SUBCASE("unknown terminal") {
		before.write[2].code = after.write[2].code = Peer::UNKNOWN;
	}
	SUBCASE("last actual ancestor has no parent") {
		before.write[2].ppid = after.write[2].ppid = 0;
	}
	SUBCASE("last actual ancestor parent changed") {
		after.write[2].ppid = 2;
	}

	CHECK_FALSE(bool(Peer::validate_chain(before, after, 501, 90)["ok"]));
}

TEST_CASE("[Editor][AIChat][ExternalPeer] Godot is denied anywhere even above a valid desktop") {
	const Vector<Peer::Process> original = normal_chain();
	for (int i = 0; i < 3; i++) {
		Vector<Peer::Process> changed = original;
		changed.write[i].code = Peer::GODOT;
		CHECK(Peer::validate_chain(changed, changed, 501, 90)["error"] == "godot_ancestor");
		CHECK(Peer::validate_chain(original, original, 501, original[i].pid)["error"] == "godot_ancestor");
	}
	Vector<Peer::Process> changed = original;
	Peer::Process outer = changed[2];
	outer.pid = 55;
	outer.birth_sec = 150;
	outer.code = Peer::GODOT;
	changed.write[2].ppid = 55;
	changed.insert(3, outer);
	CHECK(Peer::validate_chain(changed, changed, 501, 90)["error"] == "godot_ancestor");
}

TEST_CASE("[Editor][AIChat][ExternalPeer] Invalid inputs never authorize") {
	const Vector<Peer::Process> chain = normal_chain();
	CHECK_FALSE(bool(Peer::validate_chain(chain, chain, 0, 90)["ok"]));
	CHECK_FALSE(bool(Peer::validate_chain(chain, chain, 501, 1)["ok"]));
	CHECK_FALSE(bool(Peer::validate_chain(Vector<Peer::Process>(), Vector<Peer::Process>(), 501, 90)["ok"]));
	CHECK_FALSE(bool(Peer::verify(-1, 90)["ok"]));
}

#ifdef MACOS_ENABLED
TEST_CASE("[Editor][AIChat][ExternalPeer] Private engine child cannot authorize through its desktop ancestor") {
	char directory[] = "/tmp/gonggong-peer-test-XXXXXX";
	REQUIRE(mkdtemp(directory) != nullptr);
	sockaddr_un address = {};
	address.sun_family = AF_UNIX;
	std::strcpy(address.sun_path, directory);
	std::strcat(address.sun_path, "/peer.sock");
	const int listener = socket(AF_UNIX, SOCK_STREAM, 0);
	REQUIRE(listener >= 0);
	REQUIRE(bind(listener, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0);
	REQUIRE(listen(listener, 1) == 0);
	const pid_t child = fork();
	REQUIRE(child >= 0);
	if (child == 0) {
		close(listener);
		// The peer is a valid Apple interpreter; rejection must be caused by
		// its engine ancestor, rather than an unknown child executable.
		execl("/usr/bin/python3", "python3", "-c", "import socket,sys; s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(3); s.connect(sys.argv[1]); assert s.recv(1)==bytes([1]); s.close()", address.sun_path, static_cast<char *>(nullptr));
		_exit(2);
	}
	pollfd ready = { listener, POLLIN, 0 };
	const bool connected = poll(&ready, 1, 3000) == 1;
	const int accepted = connected ? accept(listener, nullptr, nullptr) : -1;
	Dictionary result;
	if (accepted >= 0) {
		result = Peer::verify(accepted, getpid());
		const char byte = 1;
		CHECK(write(accepted, &byte, 1) == 1);
		close(accepted);
	}
	close(listener);
	int status = 0;
	CHECK(waitpid(child, &status, 0) == child);
	unlink(address.sun_path);
	rmdir(directory);
	REQUIRE(accepted >= 0);
	CHECK(WIFEXITED(status));
	CHECK(WEXITSTATUS(status) == 0);
	CHECK_FALSE(bool(result.get("ok", true)));
	CHECK(result.get("error", "") == "godot_ancestor");
}
#endif
} // namespace TestAIChatExternalPeer
#endif
