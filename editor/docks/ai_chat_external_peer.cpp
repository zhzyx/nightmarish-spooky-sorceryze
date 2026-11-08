/**************************************************************************/
/*  ai_chat_external_peer.cpp                                             */
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

#include "ai_chat_external_peer.h"

namespace {
Dictionary rejected(const char *p_error) {
	Dictionary result;
	result["ok"] = false;
	result["error"] = p_error;
	return result;
}

bool same_process(const AIChatExternalPeer::Process &p_a, const AIChatExternalPeer::Process &p_b) {
	return p_a.pid == p_b.pid && p_a.ppid == p_b.ppid && p_a.uid == p_b.uid && p_a.real_uid == p_b.real_uid && p_a.saved_uid == p_b.saved_uid && p_a.birth_sec == p_b.birth_sec && p_a.birth_usec == p_b.birth_usec && p_a.code == p_b.code && p_a.fingerprint == p_b.fingerprint;
}
} // namespace

Dictionary AIChatExternalPeer::validate_chain(const Vector<Process> &p_before, const Vector<Process> &p_after, uint32_t p_uid, int p_engine_pid) {
	if (p_engine_pid <= 1 || p_uid == 0 || p_before.is_empty() || p_before.size() > 64 || p_before.size() != p_after.size()) {
		return rejected("ancestor_chain_incomplete");
	}
	int desktop = 0;
	for (int i = 0; i < p_before.size(); i++) {
		const Process &entry = p_before[i];
		if (!same_process(entry, p_after[i]) || entry.birth_sec == 0 || entry.birth_usec >= 1000000) {
			return rejected("ancestor_identity_changed");
		}
		if (entry.pid == p_engine_pid || entry.code == GODOT) {
			return rejected("godot_ancestor");
		}
		for (int earlier = 0; earlier < i; earlier++) {
			if (p_before[earlier].pid == entry.pid) {
				return rejected("ancestor_cycle");
			}
		}
		if (entry.pid <= 1 || entry.uid != p_uid || entry.real_uid != p_uid || entry.saved_uid != p_uid) {
			return rejected("ancestor_uid_mismatch");
		}
		if (entry.code != APPLE_PLATFORM && entry.code != OPENAI_CLI && entry.code != OPENAI_DESKTOP) {
			return rejected("unrecognized_ancestor_code");
		}
		if (entry.fingerprint.is_empty()) {
			return rejected("ancestor_code_identity_missing");
		}
		if (i == p_before.size() - 1) {
			// The actual last process must report the kernel's reserved init PID
			// in both snapshots. PID 1 is not an authorization anchor, and its
			// protected metadata is neither queried nor synthesized.
			if (entry.ppid != 1) {
				return rejected("ancestor_chain_incomplete");
			}
		} else {
			const Process &parent = p_before[i + 1];
			if (entry.ppid != parent.pid || parent.birth_sec > entry.birth_sec || (parent.birth_sec == entry.birth_sec && parent.birth_usec > entry.birth_usec)) {
				return rejected("ancestor_link_changed");
			}
		}
		if (entry.code == OPENAI_DESKTOP) {
			desktop = entry.pid;
		}
	}
	if (desktop == 0) {
		return rejected("trusted_desktop_missing");
	}
	Dictionary result;
	result["ok"] = true;
	result["peer_pid"] = p_before[0].pid;
	result["peer_birth_sec"] = int64_t(p_before[0].birth_sec);
	result["peer_birth_usec"] = int64_t(p_before[0].birth_usec);
	result["trusted_desktop_pid"] = desktop;
	return result;
}

#ifdef MACOS_ENABLED
#include <CoreFoundation/CoreFoundation.h>
#include <Security/Security.h>
#include <libproc.h>
#include <mach/message.h>
#include <sys/proc.h>
#include <sys/proc_info.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <cstring>

namespace {
template <typename T>
struct OwnedCF {
	T value = nullptr;
	~OwnedCF() {
		if (value) {
			CFRelease(value);
		}
	}
};

struct Peer {
	pid_t pid = 0;
	uid_t uid = 0;
	gid_t gid = 0;
	audit_token_t audit = {};
};

bool read_peer(int p_fd, Peer &r_peer) {
	sockaddr_un local = {};
	sockaddr_un remote = {};
	socklen_t local_size = sizeof(local);
	socklen_t remote_size = sizeof(remote);
	int type = 0;
	socklen_t type_size = sizeof(type);
	socklen_t pid_size = sizeof(r_peer.pid);
	socklen_t audit_size = sizeof(r_peer.audit);
	return p_fd >= 0 && getsockname(p_fd, reinterpret_cast<sockaddr *>(&local), &local_size) == 0 && local.sun_family == AF_UNIX && getpeername(p_fd, reinterpret_cast<sockaddr *>(&remote), &remote_size) == 0 && remote.sun_family == AF_UNIX && getsockopt(p_fd, SOL_SOCKET, SO_TYPE, &type, &type_size) == 0 && type_size == sizeof(type) && type == SOCK_STREAM && getpeereid(p_fd, &r_peer.uid, &r_peer.gid) == 0 && getsockopt(p_fd, SOL_LOCAL, LOCAL_PEERPID, &r_peer.pid, &pid_size) == 0 && pid_size == sizeof(r_peer.pid) && getsockopt(p_fd, SOL_LOCAL, LOCAL_PEERTOKEN, &r_peer.audit, &audit_size) == 0 && audit_size == sizeof(r_peer.audit);
}

bool read_process(int p_pid, AIChatExternalPeer::Process &r_process) {
	proc_bsdinfo info = {};
	if (proc_pidinfo(p_pid, PROC_PIDTBSDINFO, 0, &info, sizeof(info)) != sizeof(info) || info.pbi_pid != uint32_t(p_pid) || info.pbi_status == SZOMB || info.pbi_start_tvsec == 0) {
		return false;
	}
	r_process.pid = info.pbi_pid;
	r_process.ppid = info.pbi_ppid;
	r_process.uid = info.pbi_uid;
	r_process.real_uid = info.pbi_ruid;
	r_process.saved_uid = info.pbi_svuid;
	r_process.birth_sec = info.pbi_start_tvsec;
	r_process.birth_usec = info.pbi_start_tvusec;
	return true;
}

bool code_identity(int p_pid, const audit_token_t *p_audit, SecRequirementRef p_desktop, SecRequirementRef p_cli, SecRequirementRef p_apple, AIChatExternalPeer::Process &r_process) {
	OwnedCF<CFNumberRef> pid_number;
	OwnedCF<CFDataRef> audit_data;
	const void *key;
	const void *value;
	if (p_audit) {
		audit_data.value = CFDataCreate(nullptr, reinterpret_cast<const UInt8 *>(p_audit), sizeof(*p_audit));
		key = kSecGuestAttributeAudit;
		value = audit_data.value;
	} else {
		pid_number.value = CFNumberCreate(nullptr, kCFNumberIntType, &p_pid);
		key = kSecGuestAttributePid;
		value = pid_number.value;
	}
	if (!value) {
		return false;
	}
	OwnedCF<CFDictionaryRef> attributes;
	attributes.value = CFDictionaryCreate(nullptr, &key, &value, 1, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
	OwnedCF<SecCodeRef> code;
	if (!attributes.value || SecCodeCopyGuestWithAttributes(nullptr, attributes.value, kSecCSDefaultFlags, &code.value) != errSecSuccess || SecCodeCheckValidity(code.value, kSecCSDefaultFlags, nullptr) != errSecSuccess) {
		return false;
	}
	OwnedCF<CFDictionaryRef> info;
	if (SecCodeCopySigningInformation(code.value, kSecCSDefaultFlags, &info.value) != errSecSuccess || !info.value) {
		return false;
	}
	CFTypeRef identifier = CFDictionaryGetValue(info.value, kSecCodeInfoIdentifier);
	CFTypeRef unique = CFDictionaryGetValue(info.value, kSecCodeInfoUnique);
	char id[512] = {};
	if (!identifier || CFGetTypeID(identifier) != CFStringGetTypeID() || !CFStringGetCString(static_cast<CFStringRef>(identifier), id, sizeof(id), kCFStringEncodingUTF8) || !unique || CFGetTypeID(unique) != CFDataGetTypeID()) {
		return false;
	}
	const CFDataRef digest = static_cast<CFDataRef>(unique);
	if (CFDataGetLength(digest) <= 0 || CFDataGetLength(digest) > 64) {
		return false;
	}
	r_process.fingerprint = String::hex_encode_buffer(CFDataGetBytePtr(digest), CFDataGetLength(digest));
	const String signing_id = String::utf8(id);
	if (signing_id.to_lower().contains("godot")) {
		r_process.code = AIChatExternalPeer::GODOT;
	} else if (SecCodeCheckValidity(code.value, kSecCSDefaultFlags, p_desktop) == errSecSuccess) {
		r_process.code = AIChatExternalPeer::OPENAI_DESKTOP;
	} else if (signing_id == "codex" && SecCodeCheckValidity(code.value, kSecCSDefaultFlags, p_cli) == errSecSuccess) {
		r_process.code = AIChatExternalPeer::OPENAI_CLI;
	} else if (signing_id.begins_with("com.apple.") && SecCodeCheckValidity(code.value, kSecCSDefaultFlags, p_apple) == errSecSuccess) {
		r_process.code = AIChatExternalPeer::APPLE_PLATFORM;
	} else {
		r_process.code = AIChatExternalPeer::UNKNOWN;
	}
	return true;
}

bool capture_chain(const Peer &p_peer, SecRequirementRef p_desktop, SecRequirementRef p_cli, SecRequirementRef p_apple, Vector<AIChatExternalPeer::Process> &r_chain) {
	int pid = p_peer.pid;
	for (int i = 0; i < 64; i++) {
		AIChatExternalPeer::Process process;
		if (pid <= 1 || !read_process(pid, process)) {
			return false;
		}
		if (!code_identity(pid, i == 0 ? &p_peer.audit : nullptr, p_desktop, p_cli, p_apple, process)) {
			return false;
		}
		AIChatExternalPeer::Process after;
		if (!read_process(pid, after) || after.pid != process.pid || after.ppid != process.ppid || after.uid != process.uid || after.real_uid != process.real_uid || after.saved_uid != process.saved_uid || after.birth_sec != process.birth_sec || after.birth_usec != process.birth_usec) {
			return false;
		}
		r_chain.push_back(process);
		if (process.ppid == 1) {
			return true;
		}
		pid = process.ppid;
	}
	return false;
}
} // namespace
#endif

Dictionary AIChatExternalPeer::verify(int p_socket_fd, int p_engine_pid) {
#ifdef MACOS_ENABLED
	if (p_engine_pid != getpid() || getuid() != geteuid()) {
		return rejected("host_identity_mismatch");
	}
	Peer before;
	if (!read_peer(p_socket_fd, before) || before.pid <= 1 || before.uid != getuid()) {
		return rejected("peer_credentials_unavailable");
	}
	if (before.pid == p_engine_pid) {
		return rejected("godot_ancestor");
	}
	OwnedCF<SecRequirementRef> desktop;
	OwnedCF<SecRequirementRef> cli;
	OwnedCF<SecRequirementRef> apple;
	if (SecRequirementCreateWithString(CFSTR("identifier \"com.openai.codex\" and anchor apple generic and certificate leaf[subject.OU] = \"2DC432GLL2\""), kSecCSDefaultFlags, &desktop.value) != errSecSuccess || SecRequirementCreateWithString(CFSTR("identifier \"codex\" and anchor apple generic and certificate leaf[subject.OU] = \"2DC432GLL2\""), kSecCSDefaultFlags, &cli.value) != errSecSuccess || SecRequirementCreateWithString(CFSTR("anchor apple"), kSecCSDefaultFlags, &apple.value) != errSecSuccess) {
		return rejected("code_requirements_unavailable");
	}
	Vector<Process> chain_before;
	Vector<Process> chain_after;
	if (!capture_chain(before, desktop.value, cli.value, apple.value, chain_before) || !capture_chain(before, desktop.value, cli.value, apple.value, chain_after)) {
		return rejected("ancestor_identity_unavailable");
	}
	Peer after;
	if (!read_peer(p_socket_fd, after) || before.pid != after.pid || before.uid != after.uid || before.gid != after.gid || std::memcmp(&before.audit, &after.audit, sizeof(before.audit)) != 0) {
		return rejected("peer_identity_changed");
	}
	return validate_chain(chain_before, chain_after, before.uid, p_engine_pid);
#else
	return rejected("external_peer_identity_unsupported");
#endif
}
