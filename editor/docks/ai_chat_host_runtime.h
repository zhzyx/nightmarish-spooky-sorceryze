/**************************************************************************/
/*  ai_chat_host_runtime.h                                                */
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

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "editor/docks/gonggong_host_paths.h"

// Host configuration and accidental cross-worktree protection, not a shell sandbox.
class AIChatHostRuntime {
public:
	static bool executable_exists(const String &p_path) {
		return p_path.is_absolute_path() && FileAccess::exists(p_path);
	}

	static String node_path(const String &p_explicit, const String &p_cli) {
		return executable_exists(p_explicit) ? p_explicit : executable_exists(p_cli) ? p_cli
																					 : String();
	}

	static void prepare_node(const String &p_cli) {
		const String node = node_path(OS::get_singleton()->get_environment("GONGGONG_NODE"), p_cli.strip_edges());
		if (!node.is_empty()) {
			OS::get_singleton()->set_environment("GONGGONG_NODE", node);
		}
	}

	static String canonical_directory(const String &p_path) {
		Ref<DirAccess> directory = DirAccess::open(p_path);
		return directory.is_valid() ? directory->get_current_dir() : String();
	}

	static String workspace(const String &p_bound, const String &p_engine, const String &p_project) {
		for (const String &path : { p_bound, p_engine, p_project }) {
			if (!path.is_empty()) {
				const String directory = canonical_directory(path);
				if (!directory.is_empty()) {
					return directory;
				}
			}
		}
		return String();
	}

	static bool artifact_matches(const String &p_executable, const String &p_manifest, const Dictionary &p_binding, String &r_error) {
		const Ref<FileAccess> file = FileAccess::open(p_manifest, FileAccess::READ);
		if (file.is_null() || file->get_length() > 16 * 1024 * 1024) {
			r_error = "candidate_artifact_manifest_missing";
			return false;
		}
		const Variant parsed = JSON::parse_string(file->get_as_text());
		if (parsed.get_type() != Variant::DICTIONARY) {
			r_error = "candidate_artifact_manifest_invalid";
			return false;
		}
		const Dictionary manifest = parsed;
		const Dictionary binding = manifest.get("binding", Dictionary());
		for (const String &key : { String("source_root"), String("issue"), String("request_id"), String("owner"), String("branch"), String("base_sha") }) {
			if (!p_binding.has(key) || binding.get(key, Variant()) != p_binding[key]) {
				r_error = "candidate_artifact_binding_mismatch";
				return false;
			}
		}
		if (String(manifest.get("executable", "")).replace("\\", "/").simplify_path() != p_executable.replace("\\", "/").simplify_path() || String(manifest.get("artifact_sha256", "")).length() != 64 || manifest["artifact_sha256"] != FileAccess::get_sha256(p_executable)) {
			r_error = "candidate_artifact_digest_mismatch";
			return false;
		}
		return true;
	}

	static bool source_matches(const String &p_python, const String &p_worker, const String &p_manifest, const Dictionary &p_binding, String &r_error) {
		if (!executable_exists(p_python) || !FileAccess::exists(p_worker)) {
			r_error = "candidate_source_verifier_missing";
			return false;
		}
		List<String> args;
		for (const String &arg : { p_worker, String("--root"), String(p_binding.get("source_root", "")), String("--manifest"), p_manifest }) {
			args.push_back(arg);
		}
		String output;
		int code = -1;
		const Error error = OS::get_singleton()->execute(p_python, args, &output, &code);
		const Variant parsed = JSON::parse_string(output.strip_edges());
		if (error != OK || code != 0 || parsed.get_type() != Variant::DICTIONARY || !bool(Dictionary(parsed).get("ok", false))) {
			r_error = parsed.get_type() == Variant::DICTIONARY ? String(Dictionary(parsed).get("error", "candidate_source_verification_failed")) : String("candidate_source_verification_failed");
			return false;
		}
		return true;
	}

	static String command_profile(const Dictionary &p_candidate, const String &p_project) {
		const String source = p_candidate.get("source_root", "");
		List<String> args;
		for (const String &arg : { String("-C"), source, String("worktree"), String("list"), String("--porcelain") }) {
			args.push_back(arg);
		}
		String output;
		int code = -1;
		const String git = OS::get_singleton()->get_environment("GONGGONG_GIT").is_empty() ? String("git") : OS::get_singleton()->get_environment("GONGGONG_GIT");
		if (OS::get_singleton()->execute(git, args, &output, &code) != OK || code != 0) {
			return String();
		}
		Array roots = Array(p_candidate.get("protected_roots", Array())).duplicate();
		bool source_found = false;
		for (const String &line : output.split("\n")) {
			if (!line.begins_with("worktree ")) {
				continue;
			}
			const String path = line.trim_prefix("worktree ");
			const String root = canonical_directory(path);
			if (root.is_empty() || path != root) {
				return String();
			}
			if (root == source) {
				source_found = true;
			} else if (!roots.has(root)) {
				roots.push_back(root);
			}
		}
		if (!source_found) {
			return String();
		}
		String profile = "(version 1)(allow default)";
		const String project = canonical_directory(p_project);
		const String common = canonical_directory(p_candidate.get("common_dir", ""));
		for (const Variant &value : roots) {
			const String root = canonical_directory(value);
			if (root.is_empty()) {
				continue;
			}
			profile += "(deny file-write* (require-all (subpath " + JSON::stringify(root) + ")";
			for (const String &allowed : { common, project, root.path_join("bin") }) {
				if (!allowed.is_empty() && allowed != root) {
					profile += " (require-not (subpath " + JSON::stringify(allowed) + "))";
				}
			}
			profile += "))";
		}
		return profile;
	}

	static bool contains(const String &p_directory, const String &p_path) {
		return !p_directory.is_empty() && (p_path == p_directory || p_path.begins_with(p_directory.path_join("")));
	}

	static bool production_path(const String &p_path, const String &p_workspace, const String &p_project, String &r_error) {
		const String parent = DirAccess::dir_exists_absolute(p_path) ? p_path : p_path.get_base_dir();
		const String canonical = canonical_directory(parent);
		const String source = GongGongHostPaths::find_ancestor(canonical, "SConstruct");
		const String bound = canonical_directory(p_workspace);
		if (source.is_empty() || source == bound) {
			return true;
		}
		// The open project can live under another checkout; its own assets stay writable.
		const String project = canonical_directory(p_project);
		if (project != source && FileAccess::exists(project.path_join("project.godot")) && contains(project, canonical)) {
			return true;
		}
		r_error = "workspace_mismatch: this path belongs to another engine source checkout. Use the bound work-order workspace: " + bound + ". Read-only file access remains available.";
		return false;
	}
};
