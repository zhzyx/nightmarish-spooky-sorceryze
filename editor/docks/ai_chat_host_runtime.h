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

	// Python records canonical native paths; DirAccess and Git report slash-separated paths on Windows.
	static bool matches_recorded_directory(const String &p_actual, const String &p_recorded) {
		if (p_actual.is_empty() || p_recorded.is_empty()) {
			return false;
		}
#ifdef WINDOWS_ENABLED
		return canonical_directory(p_actual) == p_recorded.replace_char('\\', '/');
#else
		return canonical_directory(p_actual) == p_recorded;
#endif
	}

	static bool validate_candidate_checkout(const Dictionary &p_candidate, String &r_error) {
		const String source = p_candidate["source_root"];
		const String link = FileAccess::get_file_as_string(source.path_join(".git")).strip_edges();
		if (!link.begins_with("gitdir: ")) {
			r_error = "candidate_git_link_invalid: expected an owned Git worktree.";
			return false;
		}
		String gitdir = link.trim_prefix("gitdir: ");
		if (!gitdir.is_absolute_path()) {
			gitdir = source.path_join(gitdir).simplify_path();
		}
		const String head = FileAccess::get_file_as_string(gitdir.path_join("HEAD")).strip_edges();
		if (!AIChatHostRuntime::matches_recorded_directory(source, source) || !FileAccess::exists(source.path_join("SConstruct"))) {
			r_error = "candidate_source_changed: the recorded source directory is no longer the engine source.";
			return false;
		}
		if (head != "ref: refs/heads/" + String(p_candidate["branch"])) {
			r_error = "candidate_branch_changed: the host-owned source branch is no longer active.";
			return false;
		}
		const String git = OS::get_singleton()->get_environment("GONGGONG_GIT").is_empty() ? String("git") : OS::get_singleton()->get_environment("GONGGONG_GIT");
		for (const bool ancestry : { false, true }) {
			List<String> args;
			args.push_back("-C");
			args.push_back(ancestry ? source : String(p_candidate["common_dir"]));
			if (ancestry) {
				for (const String &arg : { String("merge-base"), String("--is-ancestor"), String(p_candidate["base_sha"]), String("HEAD") }) {
					args.push_back(arg);
				}
			} else {
				// Ask Git from the recorded common directory. A matching repository
				// returns "./" even when Windows console decoding cannot represent its path.
				args.push_back("--git-dir=" + source.path_join(".git"));
				args.push_back("rev-parse");
				args.push_back("--path-format=relative");
				args.push_back("--git-common-dir");
			}
			String output;
			int code = -1;
			if (OS::get_singleton()->execute(git, args, &output, &code) != OK || code != 0 || (!ancestry && output.strip_edges().trim_suffix("/") != ".")) {
				r_error = "candidate_repository_or_base_changed: source identity must be revalidated.";
				return false;
			}
		}
		return true;
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

	static String native_app_for_executable(const String &p_executable) {
		const String executable = p_executable.replace("\\", "/").simplify_path();
		const String app = executable.get_base_dir().get_base_dir().get_base_dir();
		return app.ends_with(".app") && executable == app.path_join("Contents/MacOS/Godot") ? app : String();
	}

	static String candidate_manifest_path(const String &p_executable) {
		const String app = native_app_for_executable(p_executable);
		return (app.is_empty() ? p_executable : app) + ".candidate.json";
	}

	static bool self_update_path_matches(const String &p_executable, const String &p_source) {
		const String executable = p_executable.replace("\\", "/").simplify_path();
		const String app = native_app_for_executable(executable);
		const String output = app.is_empty() ? executable : app;
		const String file = output.get_file();
		bool directory_matches = output.get_base_dir().nocasecmp_to(p_source.path_join("bin").replace("\\", "/").simplify_path()) == 0;
		if (!app.is_empty()) {
			const String native_directory = GongGongEngineOrigin::native_artifact_directory(p_source);
			directory_matches = directory_matches || (!native_directory.is_empty() && output.get_base_dir() == native_directory);
		}
		return directory_matches && file.begins_with("godot.") && file.contains(".editor.") && (file.contains(".self_update_a.") || file.ends_with(".self_update_a") || file.contains(".self_update_b.") || file.ends_with(".self_update_b"));
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
		const String app = native_app_for_executable(p_executable);
		if (!app.is_empty()) {
			const Dictionary native_app = manifest.get("native_app", Dictionary());
			const Dictionary recorded = JSON::parse_string(FileAccess::get_file_as_string(p_binding.get("binding_path", "")));
			if (native_app.size() != 3 || native_app.get("bundle_path", "") != app || native_app.get("executable_relative", "") != "Contents/MacOS/Godot" || native_app.get("origin_relative", "") != "Contents/Resources/gonggong_engine_origin.json" || p_manifest != candidate_manifest_path(p_executable) || recorded.get("artifact_manifest", "") != p_manifest) {
				r_error = "candidate_native_artifact_layout_mismatch";
				return false;
			}
		} else if (manifest.has("native_app")) {
			r_error = "candidate_native_artifact_layout_mismatch";
			return false;
		}
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

	static bool ready_artifact_matches(const String &p_executable, const Variant &p_reported_manifest, const Dictionary &p_binding, String &r_error) {
		const String expected = candidate_manifest_path(p_executable);
		String reported = p_reported_manifest.get_type() == Variant::STRING ? String(p_reported_manifest) : String();
#ifdef WINDOWS_ENABLED
		reported = reported.replace_char('\\', '/');
#endif
		if (reported != expected) {
			r_error = "candidate_artifact_manifest_path_mismatch";
			return false;
		}
		return artifact_matches(p_executable, expected, p_binding, r_error);
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
		// Keep non-ASCII paths readable; Godot strings cannot carry Git's NUL
		// records, so decode the quoted forms still used for special characters.
		for (const String &arg : { String("-c"), String("core.quotePath=false"), String("-C"), source, String("worktree"), String("list"), String("--porcelain") }) {
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
			String path = line.trim_prefix("worktree ");
			if (path.begins_with("\"")) {
				const Variant decoded = JSON::parse_string(path);
				if (decoded.get_type() != Variant::STRING) {
					return String();
				}
				path = decoded;
			}
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

	static Dictionary command_guard(const Dictionary &p_candidate, const String &p_python, const String &p_installation, String &r_error) {
		Dictionary guard;
		const String worker = p_installation.path_join("tools/editor_provenance_guard.py");
		const String binding = p_candidate.get("binding_path", "");
		if (!executable_exists(p_python) || !FileAccess::exists(worker) || !binding.is_absolute_path() || !FileAccess::exists(binding)) {
			r_error = "active_provenance_guard_unavailable: command was not started.";
			return guard;
		}
		guard["protocol"] = 1;
		guard["python"] = p_python;
		guard["worker"] = worker;
		guard["binding"] = binding;
		return guard;
	}

	static bool evidence_write_allowed(const String &p_path, const Dictionary &p_candidate, String &r_error) {
		if (p_candidate.is_empty()) {
			return true;
		}
		String source = p_candidate.get("source_root", "");
		const Dictionary config = JSON::parse_string(FileAccess::get_file_as_string(source.path_join("work-items.json")));
		const String tenant = config.get("tenant_id", "");
		const String request = p_candidate.get("request_id", "");
		if (tenant.is_empty() || request.is_empty()) {
			r_error = "active_provenance_configuration_invalid";
			return false;
		}
		String target = canonical_write_target(p_path);
		if (target.is_empty()) {
			r_error = "active_provenance_write_target_unresolved";
			return false;
		}
#if defined(MACOS_ENABLED) || defined(WINDOWS_ENABLED)
		// A differently cased spelling must not bypass a protected path on the
		// default case-insensitive filesystems of these hosts.
		source = source.to_lower();
		target = target.to_lower();
#endif
		const String events = source.path_join("gonggong-diting-data/events").path_join(tenant).path_join(request);
		if (contains(events, target) || contains(source.path_join(".gonggong-outbox/chat"), target) || target == source.path_join("gonggong-diting-data/dataset.json") || target == source.path_join("gonggong-diting-data/.gitattributes") || (contains(source.path_join("data-collection"), target) && FileAccess::exists(p_path))) {
			r_error = "active_provenance_is_host_owned: preserve existing events and receipts; use the framework to append new evidence.";
			return false;
		}
		return true;
	}

	static String canonical_write_target(const String &p_path) {
		String path = p_path;
		for (int depth = 0; depth < 32; depth++) {
			String parent = path.get_base_dir();
			String suffix = path.get_file();
			Ref<DirAccess> directory = DirAccess::open(parent);
			while (directory.is_null() && !parent.is_empty()) {
				const String next = parent.get_base_dir();
				if (next == parent) {
					break;
				}
				suffix = parent.get_file().path_join(suffix);
				parent = next;
				directory = DirAccess::open(parent);
			}
			if (directory.is_null()) {
				return String();
			}
			const String canonical = directory->get_current_dir();
			if (!directory->is_link(suffix)) {
				return canonical.path_join(suffix).simplify_path();
			}
			const String link = directory->read_link(suffix);
			if (link.is_empty()) {
				return String();
			}
			path = (link.is_absolute_path() ? link : canonical.path_join(link)).simplify_path();
		}
		return String();
	}

	static bool contains(const String &p_directory, const String &p_path) {
		return !p_directory.is_empty() && (p_path == p_directory || p_path.begins_with(p_directory.path_join("")));
	}

	static bool production_path(const String &p_path, const String &p_workspace, const String &p_project, String &r_error) {
		const String target = canonical_write_target(p_path);
		if (target.is_empty()) {
			r_error = "workspace_write_target_unresolved";
			return false;
		}
		const String canonical = DirAccess::dir_exists_absolute(target) ? target : target.get_base_dir();
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
