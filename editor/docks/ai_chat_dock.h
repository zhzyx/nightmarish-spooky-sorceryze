/**************************************************************************/
/*  ai_chat_dock.h                                                        */
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

#include "core/io/file_access.h"
#include "core/os/thread.h"
#include "core/templates/safe_refcount.h"
#include "editor/docks/editor_dock.h"

class AIChatEditorControl;
class AIChatEditorBridge;
class Button;
class CheckBox;
class ConfirmationDialog;
class HTTPRequest;
class HBoxContainer;
class AcceptDialog;
class Label;
class LineEdit;
class GongGongPanel;
class OptionButton;
class PanelContainer;
class PopupMenu;
class ProgressBar;
class RichTextLabel;
class TabBar;
class TabContainer;
class SpinBox;
class TextEdit;
class Timer;
class Tree;
class ItemList;
class VBoxContainer;
class ScrollContainer;
class FileDialog;
class HFlowContainer;
class Image;
class InputEvent;
class Texture2D;
class ShaderMaterial;
class TextureRect;

class AIChatDock : public EditorDock {
	GDCLASS(AIChatDock, EditorDock);
	Timer *gonggong_timer = nullptr;
	int64_t gonggong_pid = -1;
	uint64_t gonggong_generation = 0;
	bool gonggong_resume = false;
	String gonggong_context;
	String gonggong_input_path;
	String gonggong_output_path;
	Dictionary gonggong_reporting;
	String gonggong_report_root;
	String gonggong_report_python;
	Dictionary gonggong_running_steps;
	Timer *gonggong_receipt_timer = nullptr;
	int64_t gonggong_receipt_pid = -1;
	String gonggong_receipt_path;
	uint64_t gonggong_receipt_generation = 0;
	String gonggong_recovered_result;
	String gonggong_recovery_ack_token;
	bool gonggong_recovery_can_send = false;
	bool _record_gonggong(const String &p_kind, const String &p_phase, const String &p_status);
	Callable gonggong_receipt_continuation;
	uint64_t gonggong_continuation_generation = 0;
	bool gonggong_receipt_reflush = false;
	void _flush_gonggong(const Callable &p_continuation);
	void _start_gonggong_flush();
	void _send_completion_after_receipt();
	void _response_after_receipt(int p_result, int p_code, const PackedStringArray &p_headers, const PackedByteArray &p_body, uint64_t p_generation);
	void _tool_after_receipt(uint64_t p_session);
	void _finish_tool_after_receipt(const String &p_result, bool p_file_success, bool p_structured_state);
	void _poll_gonggong_receipt();
	void _end_gonggong(const String &p_status);
	bool _direct_daqian_task() const;
	String _daqian_board_workspace() const;
	void _begin_gonggong_context();
	void _environment_setup_completed();
	void _poll_gonggong_context();
	void _clear_gonggong_files();

	// Unbound work orders are resolved in the conversation by the host itself;
	// guide replies never enter `messages`, so no model or tool runs before intake.
	GongGongPanel *gonggong_panel = nullptr;
	String issue_guide_state;
	String issue_agent_checked;
	void _begin_issue_agent(const String &p_outcome, bool p_retry = false, bool p_clarifying = false);
	String issue_guide_outcome;
	Dictionary issue_guide_fields;
	Array issue_guide_categories;
	uint64_t issue_guide_generation = 0;
	uint64_t issue_guide_run_generation = 0;
	int64_t issue_guide_pid = -1;
	String issue_guide_action;
	String issue_guide_input_path;
	String issue_guide_output_path;
	Timer *issue_guide_timer = nullptr;
	bool _start_issue_guide();
	void _issue_guide_reply(const String &p_text);
	void _issue_guide_prompt();
	void _issue_guide_run(const String &p_action, const Dictionary &p_request);
	void _poll_issue_guide();
	void _clear_issue_guide_files();
	void _cancel_issue_guide(const String &p_notice);
	void _issue_guide_bind(int64_t p_number, const String &p_request_id);
	void _issue_guide_retry();

	// Local environment igniter: python/node/git gaps become a host-local guide
	// instead of a blocking "system blocked" reply; replies never reach a model.
	String igniter_state;
	bool igniter_for_intake = false;
	String igniter_outcome;
	Array igniter_missing;
	Dictionary igniter_fields;
	uint64_t igniter_generation = 0;
	uint64_t igniter_run_generation = 0;
	int64_t igniter_pid = -1;
	String igniter_action;
	String igniter_input_path;
	String igniter_output_path;
	Timer *igniter_timer = nullptr;
	bool _start_igniter(const Array &p_missing);
	void _igniter_reply(const String &p_text);
	void _igniter_prompt();
	void _igniter_run(const String &p_action, const Dictionary &p_request);
	void _poll_igniter();
	void _clear_igniter_files();
	void _cancel_igniter(const String &p_notice, const String &p_phase = "cancelled");
	void _igniter_resume();

	Button *engine_build_button = nullptr;
	Button *engine_restart_button = nullptr;
	Button *engine_cancel_button = nullptr;
	CheckBox *engine_auto_restart = nullptr;
	ProgressBar *engine_build_progress = nullptr;
	Label *engine_build_status = nullptr;
	LineEdit *engine_python = nullptr;
	TextEdit *engine_build_arguments = nullptr;
	ConfirmationDialog *engine_approval = nullptr;
	AcceptDialog *engine_log_dialog = nullptr;
	TextEdit *engine_log_text = nullptr;
	Timer *engine_build_timer = nullptr;
	int64_t engine_build_pid = -1;
	uint64_t engine_build_started = 0;
	String engine_build_root;
	int64_t candidate_pid = -1;
	uint64_t candidate_generation = 0;
	String candidate_result_path;
	Timer *candidate_timer = nullptr;
	bool _ensure_engine_candidate(const Dictionary &p_runtime = Dictionary());
	void _poll_engine_candidate();
	void _cancel_engine_candidate();
	String _candidate_root() const;
	String _workflow_root(int p_agent = -1) const;
	bool _validate_engine_candidate(String &r_error) const;
	bool _recover_active_provenance(String &r_error, const Dictionary &p_runtime = Dictionary()) const;

	String engine_status_path;
	String engine_log_path;
	String engine_cancel_path;
	String engine_updated_executable;
	String engine_dialog_action;
	bool engine_restart_approved = false;
	bool engine_restart_requested = false;
	// A rebuild is modeled as one tool call that spans the process switch: it is
	// issued here and its result is reported by the newly built editor.
	String engine_tool_call_id;
	String engine_tool_name;
	Dictionary engine_tool_arguments;
	bool engine_tool_wants_restart = false;
	String engine_restart_target;
	String engine_restart_token;
	int engine_restart_attempt = 0;
	bool engine_restart_armed = false;
	uint64_t engine_restart_armed_msec = 0;
	void _build_engine();
	void _start_engine_build();
	void _poll_engine_build();
	void _cancel_engine_build();
	void _restart_updated_engine();
	void _confirm_engine_action();
	void _reject_engine_action();
	void _show_engine_log();
	void _refresh_engine_controls();
	String _engine_root() const;
	String _rollback_executable() const;
	void _run_engine_tool(const String &p_name, const Dictionary &p_arguments);
	void _start_engine_tool();
	void _finish_engine_tool(const Dictionary &p_result);
	bool _arm_engine_restart(const String &p_executable, int p_attempt);
	void _arm_restart_watchdog();
	void _abandon_engine_restart(const String &p_reason);
	void _save_resume();
	void _clear_resume();
	void _load_resume();

	LineEdit *endpoint = nullptr;
	LineEdit *model = nullptr;
	LineEdit *api_key = nullptr;
	CheckBox *allow_tools = nullptr;
	CheckBox *auto_apply_file_changes = nullptr;
	CheckBox *auto_execute_commands = nullptr;
	ScrollContainer *chat_scroll = nullptr;
	bool chat_follow_latest = true;
	bool chat_scroll_update_pending = false;
	int chat_scroll_position = 0;
	VBoxContainer *message_list = nullptr;
	VBoxContainer *active_reply = nullptr;
	RichTextLabel *work_text = nullptr;
	Button *work_toggle = nullptr;
	uint64_t turn_started = 0;
	int turn_steps = 0;
	TextEdit *input = nullptr;
	CheckBox *consultation_only = nullptr;
	bool consultation_turn = false;
	Button *send_button = nullptr;
	Button *stop_button = nullptr;
	String snapshot_id;
	Dictionary snapshot_state;
	String restoring_snapshot_id;
	Dictionary restoring_snapshot;
	bool snapshot_restoring = false;
	bool snapshot_transaction_failed = false;
	bool _plan_version_restore(const String &p_id, Dictionary &r_plan, String &r_error) const;
	bool _recover_version_transaction(const Dictionary &p_history, String &r_error);
	void _rebuild_snapshot_transcript();
	Button *snapshot_history_button = nullptr;
	AcceptDialog *snapshot_history_dialog = nullptr;
	VBoxContainer *snapshot_history_list = nullptr;
	AcceptDialog *snapshot_changes_dialog = nullptr;
	ItemList *snapshot_changes_files = nullptr;
	Label *snapshot_changes_info = nullptr;
	TextEdit *snapshot_changes_diff = nullptr;
	TextEdit *snapshot_changes_before = nullptr;
	TextEdit *snapshot_changes_after = nullptr;
	Button *snapshot_changes_external = nullptr;
	Dictionary viewing_snapshot;
	void _show_snapshot_changes(const String &p_id);
	void _snapshot_file_selected(int p_index);
	void _open_external_diff();
	void _show_snapshot_history();
	void _jump_to_snapshot(const String &p_id);
	String _snapshot_path(const String &p_id) const;
	bool _prepare_snapshot_write(String &r_error);
	void _add_snapshot_button(Control *p_parent, const String &p_id);
	void _preview_snapshot_restore(const String &p_id);
	void _confirm_snapshot_restore();
	void _reject_snapshot_restore();
	bool _check_snapshot_editor(const Dictionary &p_snapshot, String &r_error) const;
	Button *add_image = nullptr;
	Button *paste_image = nullptr;
	HFlowContainer *image_attachments = nullptr;
	FileDialog *image_picker = nullptr;
	AcceptDialog *image_dialog = nullptr;
	TextureRect *image_preview = nullptr;
	Array draft_images;
	Array queued_messages;
	bool queue_paused = false;
	bool turn_completed = false;
	VBoxContainer *message_queue = nullptr;
	Label *queue_status = nullptr;
	VBoxContainer *queue_list = nullptr;
	Button *queue_resume = nullptr;
	void _refresh_message_queue();
	void _remove_queued_message(int p_index);
	void _resume_message_queue();
	void _dispatch_queued_message(int p_agent);
	bool _start_message(const Dictionary &p_message, const Dictionary &p_daqian_selection = Dictionary());
	HTTPRequest *request = nullptr;
	ConfirmationDialog *confirmation = nullptr;
	ObjectID confirmation_id;
	TextEdit *preview = nullptr;
	Label *progress_status = nullptr;
	Timer *progress_timer = nullptr;
	AcceptDialog *details_dialog = nullptr;
	TextEdit *details_text = nullptr;
	Vector<String> tool_details;
	String current_activity;
	uint64_t activity_started = 0;
	OptionButton *backend = nullptr;
	VBoxContainer *codex_settings = nullptr;
	LineEdit *codex_entry = nullptr;
	LineEdit *codex_model = nullptr;
	void _start_codex(const Array &p_messages);
	LineEdit *cli_node = nullptr;
	LineEdit *cli_bridge = nullptr;
	LineEdit *cli_entry = nullptr;
	LineEdit *cli_model = nullptr;
	Button *cli_login = nullptr;
	Label *cli_login_status = nullptr;
	VBoxContainer *http_settings = nullptr;
	VBoxContainer *cli_settings = nullptr;
	OptionButton *model_picker = nullptr;
	OptionButton *reasoning_picker = nullptr;
	void _sync_reasoning_picker();
	void _reasoning_selected(int p_index);
	String _reasoning_effort() const;
	Timer *codex_login_timer = nullptr;
	Timer *model_config_timer = nullptr;
	int64_t codex_login_pid = -1;
	uint64_t codex_login_started = 0;
	int64_t codex_status_pid = -1;
	uint64_t codex_status_started = 0;
	uint8_t codex_status_sources = 0;
	String codex_status_config;
	uint8_t pending_model_sources = 0;
	uint8_t consumed_model_sources = 0;
	int pending_model_backend = -1;
	String pending_model_config;
	void _request_model_refresh(uint8_t p_source);
	void _try_pending_model_refresh();
	void _runtime_field_changed(const String &p_value, const String &p_field);
	void _model_config_changed(const String &p_text);
	void _model_config_timeout();
	String _model_config_signature(const Dictionary &p_runtime = Dictionary()) const;
	Label *model_status = nullptr;
	HTTPRequest *model_request = nullptr;
	bool models_loading = false;
	bool cli_listing_models = false;
	String model_request_key;
	String model_request_config;
	Array model_catalog;
	String model_catalog_config;
	Dictionary discovered_model_catalogs;

	void _refresh_models();
	void _refresh_codex_models_on_start();
	void _start_codex_status_check(uint8_t p_sources);
	void _poll_codex_login();
	void _models_completed(int p_result, int p_code, const PackedStringArray &p_headers, const PackedByteArray &p_body, uint64_t p_generation);
	void _apply_models(const Array &p_models);
	LineEdit *_active_model_field() const;
	void _sync_model_picker();
	void _model_selected(int p_index);
	void _model_edited(const String &p_text);

	Array messages;
	Array transcript;
	Timer *history_timer = nullptr;
	bool history_loaded = false;
	bool history_restoring = false;
	bool history_writable = true;
	bool history_primary_valid = false;
	bool history_save_error = false;
	bool history_dirty = false;
	bool history_cleanup_pending = false;
	struct HistorySaveJob {
		Thread thread;
		SafeFlag done;
		Dictionary data;
		PackedStringArray keys;
		String path;
		bool backup = false;
		bool cleanup_backup = false;
		Error error = OK;
		uint64_t snapshot_usec = 0;
		uint64_t write_usec = 0;
		uint64_t bytes = 0;
	};
	HistorySaveJob *history_save_job = nullptr;
	Timer *history_poll_timer = nullptr;
	uint64_t history_save_count = 0;

	String conversation_id;
	String _agent_title(int p_agent) const;

	String _history_path() const;
	void _queue_history_save();
	void _draft_changed();
	void _update_composer_height();
	void _toggle_chat_settings(bool p_visible);
	void _request_settings(const String &p_section);
	void _save_chat_settings();
	void _update_settings_summary();
	void _runtime_configuration_changed();
	Button *settings_button = nullptr;
	Label *settings_summary = nullptr;
	VBoxContainer *ai_settings_control = nullptr;
	VBoxContainer *environment_settings_control = nullptr;
	void _save_history();
	static void _write_history(void *p_job);
	void _poll_history_save();
	void _flush_history();
	void _load_history();
	void _replay_transcript(const Array &p_transcript);
	void _cleanup_completed_turn();

	Array tool_calls;
	int tool_index = 0;
	int tool_rounds = 0;
	uint64_t request_generation = 0;
	uint64_t session_generation = 0;
	bool busy = false;
	String request_key;
	String pending_path;
	String pending_before;
	String pending_after;
	ObjectID editor_control_id;
	AIChatEditorControl *_get_editor_control();
	Dictionary pending_editor_action;
	Dictionary pending_external_editor_message;
	Dictionary _editor_bridge_request(const Dictionary &p_envelope);
	Dictionary _chat_instruction_context() const;
	String _chat_instruction_blocked_reason() const;
	Dictionary _chat_instruction_action(const Dictionary &p_args);
	Dictionary _chat_instruction_request(const Dictionary &p_message);
	Dictionary _chat_host_action(const Dictionary &p_args, bool p_confirmed);
	Dictionary _chat_extended_host_action(const Dictionary &p_args, bool p_confirmed);
	void _finish_external_editor_request();
	void _cancel_external_editor_request(const String &p_reason);
	String pending_action;
	Dictionary pending_delivery_request;
	Dictionary delivery_receipt;
	Dictionary delivery_retry_route;
	String delivery_retry_instance;
	String _delivery_retry_blocked_reason() const;
	Dictionary _pending_delivery_retry() const;
	Dictionary _run_delivery_retry(const Dictionary &p_args);
	void _begin_delivery_retry();
	void _finish_delivery_retry(const String &p_process_result);
	String delivery_request_path;
	String delivery_result_path;
	void _run_delivery_tool(const Dictionary &p_arguments);
	bool _delivery_process_arguments(String &r_executable, List<String> &r_arguments, const Dictionary &p_runtime);
	void _capture_delivery_result(Dictionary &r_process_result);
	void _finish_delivery();
	void _clear_delivery_files();
	String pending_command;
	String process_guard_result_path;
	String pending_cwd;
	int process_timeout_seconds = 120;
	bool pending_existed = false;
	// Each write is durably captured before changing the target file.

	int64_t process_id = -1;
	uint64_t process_started = 0;
	Ref<FileAccess> process_stdout;
	Ref<FileAccess> process_stderr;
	PackedByteArray stdout_output;
	PackedByteArray stderr_output;
	bool output_truncated = false;
	bool process_timed_out = false;

	int64_t cli_process_id = -1;
	uint64_t cli_started = 0;
	uint64_t cli_last_activity = 0;
	RichTextLabel *cli_stream_text = nullptr;
	String cli_partial;
	uint64_t cli_generation = 0;
	Ref<FileAccess> cli_stdout;
	Ref<FileAccess> cli_stderr;
	Ref<FileAccess> cli_request_file;
	PackedByteArray cli_output;
	String cli_input_path;
	bool cli_truncated = false;
	bool cli_session = false;
	bool cli_steering_reset = false;
	bool cli_waiting = false;
	String cli_configuration;
	Vector<String> cli_sent_messages;
	int turn_model_requests = 0;

	struct AgentSession {
		String conversation_id;
		Array messages;
		Array transcript;
		Vector<String> tool_details;
		VBoxContainer *message_list = nullptr;
		String draft;
		Array draft_images;
		Array queued_messages;
		bool queue_paused = false;
		String model;
		String cli_model;
		String codex_model;
		Array model_catalog;
		String model_catalog_config;
		int backend = 1;
		int scroll = 0;
		bool follow_latest = true;
		int64_t cli_process_id = -1;
		Ref<FileAccess> cli_stdout;
		Ref<FileAccess> cli_stderr;
		String cli_configuration;
		Vector<String> cli_sent_messages;
		Dictionary transport;
		Dictionary response_transport;
		String snapshot_id;
		Dictionary snapshot_state;
	};
	HashMap<int, AgentSession> agent_sessions;
	PanelContainer *agent_tabs_panel = nullptr;
	TabBar *agent_tabs = nullptr;
	Button *add_agent = nullptr;
	Control *add_agent_placeholder = nullptr;
	ConfirmationDialog *agent_close_confirmation = nullptr;
	PopupMenu *agent_context_menu = nullptr;
	ConfirmationDialog *agent_rename_dialog = nullptr;
	LineEdit *agent_name = nullptr;
	VBoxContainer *agent_archive = nullptr;
	int pending_close_agent = -1;
	int pending_rename_agent = -1;
	int active_agent = 0;
	int next_agent = 1;
	AgentSession model_query_session;
	bool cli_suspended_for_models = false;

	// Periodic tasks share the single executor, but own separate Agent histories.
	TabContainer *workspace_pages = nullptr;
	VBoxContainer *session_navigation = nullptr;
	ObjectID daqian_chat_host;
	String daqian_mount_conversation;
	bool _mount_daqian_chat(Control *p_host);
	void _unmount_daqian_chat();
	VBoxContainer *agents_page = nullptr;
	Ref<ShaderMaterial> glow_material;
	VBoxContainer *chat_layout = nullptr;
	VBoxContainer *timer_chat_host = nullptr;
	TabBar *timer_agent_tabs = nullptr;
	OptionButton *schedule_picker = nullptr;
	Label *schedule_description = nullptr;
	Label *schedule_notice = nullptr;
	Label *manual_schedule_notice = nullptr;
	CheckBox *schedule_enabled = nullptr;
	Button *schedule_edit = nullptr;
	Button *schedule_delete = nullptr;
	Button *schedule_run = nullptr;
	ConfirmationDialog *schedule_dialog = nullptr;
	ConfirmationDialog *schedule_delete_dialog = nullptr;
	LineEdit *schedule_title = nullptr;
	TextEdit *schedule_prompt = nullptr;
	SpinBox *schedule_frequency = nullptr;
	OptionButton *schedule_unit = nullptr;
	Label *schedule_validation = nullptr;
	Timer *schedule_timer = nullptr;
	Array schedule_tasks;
	HashMap<int, Dictionary> scheduled_agents;
	int next_schedule = 1;
	int selected_schedule = -1;
	int editing_schedule = -1;
	int deleting_schedule = -1;
	int last_manual_agent = 0;
	bool schedule_ui_updating = false;
	void _build_scheduler_ui(Control *p_page);
	void _load_schedules(const Dictionary &p_data);
	void _refresh_schedules();
	void _refresh_schedule_agents();
	void _route_chat_layout();
	void _workspace_selected(int p_index);
	void _schedule_selected(int p_index);
	void _edit_schedule(bool p_new);
	void _validate_schedule();
	void _save_schedule();
	void _delete_schedule_requested();
	void _delete_schedule();
	void _enable_schedule(bool p_enabled);
	void _run_schedule_now();
	void _scheduler_tick();
	void _scheduler_dispatch();
	void _scheduler_finished();
	void _timer_agent_selected(int p_index);
	void _timer_agent_close(int p_index);
	int _schedule_index(int p_id) const;
	int _agent_index(int p_id) const;
	int _manual_agent_count() const;
	bool _schedule_outstanding(int p_id) const;
	bool _enqueue_schedule(int p_index);
	void _scheduled_agent_removed(int p_id);

	// Child Agents are hidden in agent_tabs and shown only inside their parent's
	// window. Only a top-level (manual, non-scheduled) Agent can own children.
	HashMap<int, Dictionary> sub_agents;
	// Live dispatch ownership never comes from saved chat history.
	HashMap<int, Dictionary> design_batches;
	int design_child_starting = -1;
	int design_parent_starting = -1;
	uint64_t design_last_blocked_generation = UINT64_MAX;
	void _register_design_batch(int p_parent, const String &p_request_id, int64_t p_issue, int p_review = -1);
	bool _is_review_child() const;
	String _delegate_review(const Dictionary &p_arguments);
	void _cancel_design_batch(int p_agent);
	bool _design_parent_matches(int p_parent, const Dictionary &p_batch) const;
	int _design_child_parent(int p_child) const;
	void _design_turn_started();
	void _record_design_tool_receipt(const String &p_tool, const String &p_result, bool p_file_success, bool p_terminal = false);
	void _design_reporting_blocked(uint64_t p_generation = 0);
	void _resume_design_completions(uint64_t p_generation);
	bool _design_child_finished(int p_agent, bool p_completed, uint64_t p_generation);
	bool _queue_design_parent_result(int p_parent);
	bool _design_return_allowed(int p_parent, const Dictionary &p_message) const;
	int64_t sub_agent_parallel_pid = -1;
	String sub_agent_parallel_output;
	bool _dispatch_parallel_sub_agents();
	void _poll_parallel_sub_agents();
	Dictionary sub_agent_spawned;
	HBoxContainer *sub_agent_bar = nullptr;
	TabBar *sub_agent_tabs = nullptr;
	Button *add_sub_agent = nullptr;
	Button *spawn_sub_agents = nullptr;
	void _build_sub_agent_ui(VBoxContainer *p_page, int p_position);
	void _load_sub_agents(const Dictionary &p_data);
	void _refresh_sub_agents();
	void _sub_agent_tab_selected(int p_index);
	void _sub_agent_tab_close(int p_index);
	int _sub_agent_root(int p_id) const;
	Vector<int> _sub_agent_children(int p_parent, bool p_design_only, const String &p_request_id = String()) const;
	int _create_sub_agent(int p_parent, const String &p_title, const Dictionary &p_info, const String &p_prompt);
	void _add_sub_agent();
	void _spawn_sub_agents_pressed();
	bool _spawn_work_order_agents(int p_parent, bool p_explicit);
	bool _resume_work_order_agents(int p_parent, const String &p_request_id);
	void _sub_agent_dispatch();
	void _sub_agent_finished(int p_agent, bool p_completed, uint64_t p_generation);
	void _sub_agent_removed(int p_id);
	String _parent_context_result() const;

	void _restore_cli_after_models();
	AgentSession _capture_agent() const;
	void _restore_agent(const AgentSession &p_session);
	void _agent_selected(int p_index);
	void _agent_close_requested(int p_index);
	void _agent_right_clicked(int p_index);
	void _agent_menu_selected(int p_id);
	void _validate_agent_name();
	void _rename_agent();
	void _cancel_agent_rename();
	void _close_agent();
	void _add_agent();
	void _update_agent_add_button();
	void _cancel_all_agents();
	void _release_cli_request();
	bool _validate_cli(const Dictionary &p_runtime = Dictionary()) const;
	void _backend_changed(int p_backend);
	void _login_cli();
	void _start_cli(const Array &p_messages);
	void _poll_cli();
	void _cancel_cli();
	void _append(const String &p_role, const String &p_text);
	void _choose_images();
	void _images_selected(const Vector<String> &p_paths);
	void _paste_image();
	void _input_gui_input(const Ref<InputEvent> &p_event);
	void _add_image(const Ref<Image> &p_image, const String &p_name);
	void _remove_image(int p_index);
	void _refresh_images();
	void _render_images(Control *p_parent, const Array &p_images, bool p_draft);
	void _show_image(const Ref<Texture2D> &p_texture, const String &p_name);
	VBoxContainer *_message_card(const String &p_role, bool p_user, bool p_error = false);
	RichTextLabel *_message_text(VBoxContainer *p_parent, bool p_small = false);
	void _render_markdown(RichTextLabel *p_label, const String &p_text);
	void _begin_reply();
	void _append_work(const String &p_text);
	void _queue_chat_scroll_update();
	void _update_chat_scroll();
	void _chat_scrolled();
	void _set_activity(const String &p_activity);
	void _update_activity();
	void _show_details(const Variant &p_meta);
	String _tool_summary(const String &p_name, const Dictionary &p_arguments, const String &p_result) const;
	void _set_busy(bool p_busy);
	void _automation_toggled(bool p_enabled);
	void _send();
	bool _has_pending_steering() const;
	void _apply_pending_steering();
	void _request_completion();
	void _request_completed(int p_result, int p_code, const PackedStringArray &p_headers, const PackedByteArray &p_body, uint64_t p_generation);
	void _cancel_model_query();
	void _stop();
	void _next_tool(uint64_t p_session);
	void _finish_tool(const String &p_result, bool p_file_success = false, bool p_structured_state = false);
	void _show_confirmation();
	void _restore_confirmation_parent();
	void _confirm_action();
	void _reject_action();
	// The only file recovery action is the per-turn local snapshot restore.
	bool _resolve(const String &p_path, String &r_absolute, String &r_error) const;
	bool _has_unsaved_script(const String &p_path) const;
	void _refresh_script(const String &p_path);
	void _start_process();
	void _cancel_process();
	void _poll_process();
	bool _drain_pipe(const Ref<FileAccess> &p_pipe, PackedByteArray &r_output);
	String _redact(const String &p_text) const;
	Dictionary _current_host_runtime_metadata() const;

	Dictionary daqian_approval;
	uint64_t daqian_approval_generation = 0;
	bool daqian_approval_running = false;
	bool _offer_daqian_approval(const String &p_detail);
	Dictionary _get_daqian_approval() const;
	bool _confirm_daqian_approval(const String &p_token);
	void _end_daqian_approval(const String &p_state);
	void _daqian_tool_result(const String &p_result, bool p_file_success);

	String daqian_preview_source;
	String daqian_preview_conversation;
	String _work_order_binding(const String &p_field, int p_agent = -1) const;
	String _get_legacy_candidate_failure(const String &p_owner, const String &p_workspace, int64_t p_issue) const;
	Dictionary _get_daqian_models() const;
	Dictionary _launch_daqian_routing(const Dictionary &p_binding, const Dictionary &p_selection) const;
	void _set_issue_model_config(Dictionary &r_request, const Dictionary &p_runtime = Dictionary()) const;
	void _emit_daqian_requirement_phase(const String &p_phase, const Dictionary &p_design = Dictionary());
	String _open_daqian_chat(const String &p_source, int64_t p_issue, const String &p_request, const String &p_message, bool p_preview, const Dictionary &p_selection, bool p_embedded, const String &p_preview_receipt);

protected:
	static void _bind_methods();
	void _notification(int p_what);

public:
	Dictionary get_runtime_configuration() const;
	Dictionary prepare_runtime_configuration() const;
	String set_runtime_field(const String &p_field, const String &p_value);
	void refresh_runtime_controls();
	Control *get_ai_settings_control() const;
	Control *get_environment_settings_control() const;
	void set_environment_changing_handler(const Callable &p_handler);
	AIChatDock();
	~AIChatDock();
};
