/**************************************************************************/
/*  ai_chat_engine_candidate.cpp                                          */
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

#include "core/config/project_settings.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/time.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/ai_chat_host_runtime.h"
#include "editor/docks/ai_chat_tools.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/check_box.h"
#include "scene/main/timer.h"

String AIChatDock::_candidate_root() const {
	const Dictionary candidate = snapshot_state.get("engine_candidate", Dictionary());
	return candidate.get("source_root", ProjectSettings::get_singleton()->get_resource_path());
}

String AIChatDock::_workflow_root(int p_agent) const {
	const Dictionary state = p_agent >= 0 && p_agent != active_agent && agent_sessions.has(p_agent) ? agent_sessions[p_agent].snapshot_state : snapshot_state;
	const Dictionary candidate = state.get("engine_candidate", Dictionary());
	return candidate.get("source_root", state.get("requirement_workspace", EDITOR_GET("gonggong/workspace")));
}

bool AIChatDock::_recover_active_provenance(String &r_error) const {
	const Dictionary candidate = snapshot_state.get("engine_candidate", Dictionary());
	if (candidate.is_empty()) {
		return true;
	}
	const String pending = String(candidate.get("common_dir", "")).path_join("gonggong-provenance-guards").path_join(String(candidate.get("binding_path", "")).get_file().get_basename()).path_join("pending");
	if (!DirAccess::dir_exists_absolute(pending)) {
		if (FileAccess::exists(pending)) {
			r_error = "active_provenance_pending_path_invalid";
			return false;
		}
		return true;
	}
	Ref<DirAccess> directory = DirAccess::open(pending);
	if (directory.is_null() || directory->get_current_dir().replace("\\", "/").simplify_path() != pending.replace("\\", "/").simplify_path()) {
		r_error = "active_provenance_pending_path_unreadable";
		return false;
	}
	if (directory->get_files().is_empty()) {
		return true;
	}
	if (!_validate_engine_candidate(r_error)) {
		return false;
	}
	const Dictionary guard = AIChatHostRuntime::command_guard(candidate, EDITOR_GET("gonggong/python"), _engine_root(), r_error);
	if (guard.is_empty()) {
		return false;
	}
	List<String> args;
	for (const String &arg : { String(guard["worker"]), String("--binding"), String(guard["binding"]), String("--recover") }) {
		args.push_back(arg);
	}
	String output;
	int code = -1;
	const Error error = OS::get_singleton()->execute(guard["python"], args, &output, &code);
	const Variant parsed = JSON::parse_string(output.strip_edges());
	if (error != OK || code != 0 || parsed.get_type() != Variant::DICTIONARY || !bool(Dictionary(parsed).get("ok", false))) {
		r_error = "active_provenance_recovery_failed: " + (parsed.get_type() == Variant::DICTIONARY ? JSON::stringify(parsed).left(1000) : String("guard did not return a verified result"));
		return false;
	}
	return true;
}

bool AIChatDock::_validate_engine_candidate(String &r_error) const {
	const Dictionary candidate = snapshot_state.get("engine_candidate", Dictionary());
	if (candidate.is_empty()) {
		// Non-engine hosts and isolated mock workspaces keep their project behavior.
		if (!FileAccess::exists(_workflow_root().path_join("SConstruct"))) {
			return true;
		}
		r_error = "candidate_binding_missing: no verified work-order source candidate is active.";
		return false;
	}
	const Dictionary recorded = JSON::parse_string(FileAccess::get_file_as_string(candidate.get("binding_path", "")));
	for (const String &field : { String("source_root"), String("branch"), String("base_sha"), String("issue"), String("request_id"), String("owner"), String("common_dir") }) {
		if (!candidate.has(field) || recorded.get(field, Variant()) != candidate[field]) {
			r_error = "candidate_binding_changed: source ownership must be revalidated before execution.";
			return false;
		}
	}
	if (String(candidate["owner"]) != conversation_id || int64_t(candidate["issue"]) != String(_work_order_binding("issue_number")).to_int() || candidate["request_id"] != _work_order_binding("request_id")) {
		r_error = "candidate_issue_mismatch: active Issue or conversation changed.";
		return false;
	}
	const String source = candidate["source_root"];
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
	if (AIChatHostRuntime::canonical_directory(source) != source || head != "ref: refs/heads/" + String(candidate["branch"]) || !FileAccess::exists(source.path_join("SConstruct"))) {
		r_error = "candidate_branch_changed: the host-owned source branch is no longer active.";
		return false;
	}
	const String git = OS::get_singleton()->get_environment("GONGGONG_GIT").is_empty() ? String("git") : OS::get_singleton()->get_environment("GONGGONG_GIT");
	for (const bool ancestry : { false, true }) {
		List<String> args;
		args.push_back("-C");
		args.push_back(source);
		if (ancestry) {
			for (const String &arg : { String("merge-base"), String("--is-ancestor"), String(candidate["base_sha"]), String("HEAD") }) {
				args.push_back(arg);
			}
		} else {
			args.push_back("rev-parse");
			args.push_back("--path-format=absolute");
			args.push_back("--git-common-dir");
		}
		String output;
		int code = -1;
		if (OS::get_singleton()->execute(git, args, &output, &code) != OK || code != 0 || (!ancestry && (output.is_empty() || AIChatHostRuntime::canonical_directory(output.strip_edges()) != String(candidate["common_dir"])))) {
			r_error = "candidate_repository_or_base_changed: source identity must be revalidated.";
			return false;
		}
	}
	return true;
}

bool AIChatDock::_ensure_engine_candidate() {
	if (!allow_tools->is_pressed() || !FileAccess::exists(_workflow_root().path_join("SConstruct"))) {
		return true;
	}
	if (candidate_pid >= 0) {
		return false;
	}
	if (snapshot_state.has("engine_candidate")) {
		String error;
		if (!_validate_engine_candidate(error)) {
			_append(TTR("Error"), error);
			_set_busy(false);
			return false;
		}
		return true;
	}
	const String worker = _engine_root().path_join("tools/editor_engine_candidate.py");
	const String python = EDITOR_GET("gonggong/python");
	if (!FileAccess::exists(worker) || !FileAccess::exists(python)) {
		_append(TTR("Error"), U"无法准备隔离源码候选：宿主候选管理器或工作流 Python 缺失，尚未执行生产修改。");
		_set_busy(false);
		return false;
	}
	candidate_result_path = EditorPaths::get_singleton()->get_cache_dir().path_join("engine-candidate-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
	List<String> args;
	for (const String &arg : { worker, String("--workspace"), _workflow_root(), String("--issue"), _work_order_binding("issue_number"), String("--request-id"), _work_order_binding("request_id"), String("--owner"), conversation_id, String("--launch-executable"), OS::get_singleton()->get_executable_path(), String("--out"), candidate_result_path }) {
		args.push_back(arg);
	}
	ProcessID pid;
	if (OS::get_singleton()->create_process(python, args, &pid) != OK) {
		_append(TTR("Error"), U"无法启动隔离候选准备，尚未执行生产修改。");
		_set_busy(false);
		return false;
	}
	candidate_pid = pid;
	candidate_generation = session_generation;
	if (!candidate_timer) {
		candidate_timer = memnew(Timer);
		candidate_timer->set_wait_time(0.1);
		candidate_timer->connect("timeout", callable_mp(this, &AIChatDock::_poll_engine_candidate));
		add_child(candidate_timer);
	}
	candidate_timer->start();
	_set_activity(U"正在核对工单并自动准备专用源码分支");
	return false;
}

void AIChatDock::_poll_engine_candidate() {
	if (candidate_pid < 0 || OS::get_singleton()->is_process_running(candidate_pid)) {
		return;
	}
	const int exit_code = OS::get_singleton()->get_process_exit_code(candidate_pid);
	candidate_pid = -1;
	candidate_timer->stop();
	const Variant parsed = JSON::parse_string(FileAccess::get_file_as_string(candidate_result_path));
	if (!busy || candidate_generation != session_generation) {
		return;
	}
	if (exit_code != 0 || parsed.get_type() != Variant::DICTIONARY || !bool(Dictionary(parsed).get("ok", false))) {
		_append(TTR("Error"), String(U"隔离源码候选准备未通过，未发送生产模型请求：") + String(parsed.get_type() == Variant::DICTIONARY ? Dictionary(parsed).get("error", "candidate_failed") : Variant("candidate_result_missing")));
		_set_busy(false);
		return;
	}
	snapshot_state["engine_candidate"] = parsed;
	snapshot_state["requirement_workspace"] = _candidate_root();
	String error;
	if (!_validate_engine_candidate(error) || !AIChatTools::save_snapshot(_snapshot_path(snapshot_id), snapshot_state, error)) {
		_append(TTR("Error"), error);
		_set_busy(false);
		return;
	}
	gonggong_report_root = _candidate_root();
	_append_work(String(U"已为当前工单绑定独立源码候选：") + _candidate_root());
	_send_completion_after_receipt();
}

void AIChatDock::_cancel_engine_candidate() {
	if (candidate_pid >= 0) {
		OS::get_singleton()->kill(candidate_pid);
		candidate_pid = -1;
	}
	if (candidate_timer) {
		candidate_timer->stop();
	}
}
