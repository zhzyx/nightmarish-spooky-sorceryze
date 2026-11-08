/**************************************************************************/
/*  ai_chat_host_commands.cpp                                             */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                     */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining a */
/* copy of this software and associated documentation files (the           */
/* "Software"), to deal in the Software without restriction, including     */
/* without limitation the rights to use, copy, modify, merge, publish,      */
/* distribute, sublicense, and/or sell copies of the Software, and to       */
/* permit persons to whom the Software is furnished to do so, subject to    */
/* the following conditions:                                              */
/* The above copyright notice and this permission notice shall be          */
/* included in all copies or substantial portions of the Software.         */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS */
/* OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF              */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY    */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,     */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE        */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                  */
/**************************************************************************/

#include "ai_chat_dock.h"

#include "core/io/image.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "drivers/png/png_driver_common.h"
#include "editor/docks/ai_chat_issue_guide.h"
#include "editor/docks/ai_chat_tools.h"
#include "editor/settings/editor_settings.h"

#include "modules/modules_enabled.gen.h"
#ifdef MODULE_JPG_ENABLED
#include "modules/jpg/image_loader_libjpeg_turbo.h"
#endif
#ifdef MODULE_WEBP_ENABLED
#include "modules/webp/webp_common.h"
#endif
#include "scene/gui/box_container.h"
#include "scene/gui/button.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"
#include "scene/gui/spin_box.h"
#include "scene/gui/tab_bar.h"
#include "scene/gui/text_edit.h"
#include "servers/display/display_server.h"

namespace {
bool bounded_integer(const Variant &p_value, int64_t p_min, int64_t p_max) {
	return p_value.is_num() && Math::is_finite(double(p_value)) && double(p_value) == Math::floor(double(p_value)) && double(p_value) >= p_min && double(p_value) <= p_max;
}
bool safe_name(const Variant &p_value, int p_limit, bool p_empty = false) {
	if (p_value.get_type() != Variant::STRING) {
		return false;
	}
	const String name = String(p_value).strip_edges();
	if ((!p_empty && name.is_empty()) || name.length() > p_limit) {
		return false;
	}
	for (int i = 0; i < name.length(); i++) {
		if (name[i] < 32 || name[i] == 127) {
			return false;
		}
	}
	return true;
}
} // namespace

Dictionary AIChatDock::_chat_extended_host_action(const Dictionary &p_args, bool p_confirmed) {
	Dictionary result;
	result["ok"] = false;
	const String action = p_args.get("action", "");
	const Variant value = p_args.get("value", Variant());
	const bool read = action == "chat_sessions" || action == "chat_schedules" || action == "chat_configuration" || action == "chat_attachments" || action == "chat_history" || action == "chat_host_context";
	int offset = 0, limit = 100;
	if (!bounded_integer(p_args.get("offset", 0), 0, 100000) || !bounded_integer(p_args.get("limit", 100), 1, 100)) {
		result["error"] = "invalid_chat_page";
		return result;
	}
	offset = p_args.get("offset", 0);
	limit = p_args.get("limit", 100);

	// Snapshot every relevant actual object and value before showing the host's
	// confirmation. Hashes bind hidden content without disclosing conversations,
	// credentials, or attachment bytes in the proposal.
	Array session_state, attachments, history;
	for (int i = 0; i < agent_tabs->get_tab_count(); i++) {
		const int id = agent_tabs->get_tab_metadata(i);
		const AgentSession session = id == active_agent ? _capture_agent() : agent_sessions[id];
		Dictionary entry;
		entry["agent_id"] = id;
		entry["index"] = i;
		entry["parent_id"] = sub_agents.has(id) ? Variant(sub_agents[id].get("parent", -1)) : Variant();
		entry["kind"] = scheduled_agents.has(id) ? "scheduled" : sub_agents.has(id) ? String(sub_agents[id].get("source", "child"))
																					: "parent";
		entry["title"] = _redact(agent_tabs->get_tab_title(i)).left(120);
		entry["title_hash"] = agent_tabs->get_tab_title(i).sha256_text();
		entry["owner_hash"] = JSON::stringify(session.snapshot_state).sha256_text();
		entry["queue_hash"] = JSON::stringify(session.queued_messages).sha256_text();
		entry["lifecycle_hash"] = JSON::stringify(sub_agents.has(id) ? sub_agents[id] : scheduled_agents.has(id) ? scheduled_agents[id]
																												 : Dictionary())
										  .sha256_text();
		entry["conversation_id"] = session.conversation_id;
		entry["content_hash"] = JSON::stringify(session.messages).sha256_text() + JSON::stringify(session.transcript).sha256_text();
		entry["draft_hash"] = session.draft.sha256_text() + JSON::stringify(session.draft_images).sha256_text();
		session_state.push_back(entry);
	}
	for (int i = 0; i < draft_images.size(); i++) {
		const Dictionary image = draft_images[i];
		Dictionary entry;
		entry["index"] = i;
		entry["name"] = _redact(image.get("name", "")).left(128);
		entry["mime_type"] = image.get("mime_type", "");
		entry["sha256"] = String(image.get("data", "")).sha256_text();
		attachments.push_back(entry);
	}
	HashSet<String> seen;
	if (!snapshot_id.is_empty()) {
		seen.insert(snapshot_id);
		history.push_back(snapshot_id);
	}
	for (int i = transcript.size() - 1; i >= 0; i--) {
		const Dictionary record = transcript[i];
		const String id = record.get("snapshot_id", "");
		if (!id.is_empty() && !seen.has(id)) {
			seen.insert(id);
			history.push_back(id);
		}
	}
	Dictionary state;
	state["conversation_id"] = conversation_id;
	state["generation"] = int64_t(session_generation);
	state["host_instance"] = int64_t(daqian_chat_host);
	state["mounted_conversation"] = daqian_mount_conversation;
	state["owner_hash"] = JSON::stringify(snapshot_state.get("engine_candidate", Dictionary())).sha256_text();
	state["issue_number"] = _work_order_binding("issue_number");
	state["request_id"] = _work_order_binding("request_id");
	state["active_agent"] = active_agent;
	state["sessions_hash"] = JSON::stringify(session_state).sha256_text();
	state["schedule_hash"] = JSON::stringify(schedule_tasks).sha256_text();
	state["selected_schedule"] = selected_schedule;
	state["next_agent"] = next_agent;
	state["next_schedule"] = next_schedule;
	state["draft_hash"] = input->get_text().sha256_text();
	state["attachments_hash"] = JSON::stringify(attachments).sha256_text();
	state["queue_hash"] = JSON::stringify(queued_messages).sha256_text();
	state["history_hash"] = JSON::stringify(history).sha256_text();
	state["backend"] = backend->get_selected();
	state["model_hash"] = _active_model_field()->get_text().sha256_text();
	state["catalog_hash"] = JSON::stringify(model_catalog).sha256_text();
	state["reasoning"] = _reasoning_effort();
	const Dictionary runtime = get_runtime_configuration();
	state["runtime_hash"] = JSON::stringify(runtime).sha256_text();
	state["cli_bridge_hash"] = cli_bridge->get_text().sha256_text();
	state["cli_entry_hash"] = cli_entry->get_text().sha256_text();
	if (read) {
		Array rows;
		if (action == "chat_sessions") {
			rows = session_state;
		} else if (action == "chat_schedules") {
			for (const Dictionary task : schedule_tasks) {
				Dictionary row = task.duplicate(true);
				row["title"] = _redact(row.get("title", ""));
				row["prompt"] = _redact(row.get("prompt", "")).left(8192);
				row["prompt_truncated"] = String(task.get("prompt", "")).length() > 8192;
				rows.push_back(row);
			}
		} else if (action == "chat_attachments") {
			rows = attachments;
		} else if (action == "chat_history") {
			rows = history;
		} else if (action == "chat_host_context") {
			result["host_instance"] = int64_t(daqian_chat_host);
			result["mounted_conversation"] = daqian_mount_conversation;
			result["mounted"] = daqian_chat_host.is_valid();
		} else {
			Dictionary configuration;
			configuration["backend"] = backend->get_selected();
			configuration["model_id"] = _redact(_active_model_field()->get_text());
			configuration["reasoning"] = _reasoning_effort();
			Array efforts;
			for (int i = 0; i < reasoning_picker->get_item_count(); i++) {
				if (!reasoning_picker->is_item_disabled(i)) {
					efforts.push_back(reasoning_picker->get_item_metadata(i));
				}
			}
			configuration["supported_reasoning"] = efforts;
			configuration["runtime_paths"] = runtime.get("paths", Dictionary());
			configuration["codebuddy_bridge"] = _redact(cli_bridge->get_text());
			configuration["codebuddy_entry"] = _redact(cli_entry->get_text());
			result["configuration"] = configuration;
		}
		Array page;
		for (int i = offset; i < MIN(offset + limit, rows.size()); i++) {
			page.push_back(rows[i]);
		}
		result["ok"] = true;
		result["rows"] = page;
		result["total"] = rows.size();
		result["next_offset"] = offset + limit < rows.size() ? Variant(offset + limit) : Variant();
		result["observation"] = state;
		return result;
	}

	if (busy || models_loading || history_restoring || snapshot_restoring || snapshot_transaction_failed || engine_build_pid >= 0 || engine_restart_requested || !gonggong_recovered_result.is_empty() || (daqian_chat_host.is_valid() && action != "chat_host_send_message") || !history_writable || input->has_ime_text()) {
		result["error"] = daqian_chat_host.is_valid() ? "host_chat_mounted" : "chat_mutation_unavailable";
		return result;
	}
	int agent = -1, schedule = -1, index = -1, effort = -1;
	Ref<Image> added_image;
	String image_path;
	Dictionary snapshot_data;
	if (action == "chat_host_send_message") {
		Control *host = ObjectDB::get_instance<Control>(daqian_chat_host);
		const Dictionary candidate = snapshot_state.get("engine_candidate", Dictionary());
		String owner_error;
		if (!host || !host->is_inside_tree() || host->is_queued_for_deletion() || host->get_tree() != get_tree() || chat_layout->get_parent() != host || daqian_mount_conversation.is_empty() || daqian_mount_conversation != conversation_id || sub_agents.has(active_agent) || scheduled_agents.has(active_agent) || (!bounded_integer(p_args.get("host_instance", Variant()), 1, 9007199254740991LL) || int64_t(p_args["host_instance"]) != int64_t(daqian_chat_host)) || !AIChatIssueGuide::is_bound(_work_order_binding("issue_number").to_int(), _work_order_binding("request_id")) || String(candidate.get("owner", "")).is_empty() || candidate.get("owner", "") != Variant(conversation_id) || !_validate_engine_candidate(owner_error)) {
			result["error"] = "mounted_host_owner_changed_or_unbound";
			return result;
		}
	}
	if (action == "chat_rename_session" || action == "chat_close_session") {
		if (!bounded_integer(p_args.get("agent_id", Variant()), 0, INT32_MAX - 1) || _agent_index(int(p_args["agent_id"])) < 0) {
			result["error"] = "unknown_chat_session";
			return result;
		}
		agent = p_args["agent_id"];
		if (sub_agents.has(agent) && String(sub_agents[agent].get("source", "")) != "manual") {
			result["error"] = "managed_child_lifecycle_protected";
			return result;
		}
		if (action == "chat_rename_session" && !safe_name(value, 64)) {
			result["error"] = "invalid_chat_name";
			return result;
		}
	} else if (action == "chat_create_child") {
		if (!bounded_integer(p_args.get("parent_id", Variant()), 0, INT32_MAX - 1) || int(p_args["parent_id"]) != active_agent || sub_agents.has(active_agent) || scheduled_agents.has(active_agent) || agent_tabs->get_tab_count() >= 256 || _sub_agent_children(active_agent, false).size() >= 16 || sub_agents.size() >= 128 || next_agent >= INT32_MAX - 1) {
			result["error"] = "invalid_child_parent_or_capacity";
			return result;
		}
	} else if (action.begins_with("chat_schedule_")) {
		if (action != "chat_schedule_create" && action != "chat_schedule_update" && action != "chat_schedule_delete" && action != "chat_schedule_enable" && action != "chat_schedule_run" && action != "chat_schedule_select") {
			result["error"] = "unknown_host_chat_action";
			return result;
		}
		if (action != "chat_schedule_create") {
			if (!bounded_integer(p_args.get("schedule_id", Variant()), 1, INT32_MAX - 1) || (schedule = _schedule_index(int(p_args["schedule_id"]))) < 0) {
				result["error"] = "unknown_schedule";
				return result;
			}
		}
		if (action == "chat_schedule_create" || action == "chat_schedule_update") {
			if (value.get_type() != Variant::DICTIONARY) {
				result["error"] = "invalid_schedule_definition";
				return result;
			}
			const Dictionary definition = value;
			if (definition.size() != 4 || !safe_name(definition.get("title", Variant()), 48) || definition.get("prompt", Variant()).get_type() != Variant::STRING || String(definition["prompt"]).strip_edges().is_empty() || String(definition["prompt"]).utf8().length() > 256 * 1024 || !bounded_integer(definition.get("frequency", Variant()), 1, 10000) || !bounded_integer(definition.get("unit", Variant()), 0, 3)) {
				result["error"] = "invalid_schedule_definition";
				return result;
			}
			for (int i = 0; i < schedule_tasks.size(); i++) {
				if (i != schedule && Dictionary(schedule_tasks[i]).get("title", "") == Variant(_redact(String(definition["title"]).strip_edges()))) {
					result["error"] = "duplicate_schedule_title";
					return result;
				}
			}
			if (action == "chat_schedule_create" && (schedule_tasks.size() >= 32 || next_schedule >= INT32_MAX - 1)) {
				result["error"] = "schedule_capacity_exceeded";
				return result;
			}
		} else if (action == "chat_schedule_enable" && value.get_type() != Variant::BOOL) {
			result["error"] = "invalid_schedule_enabled";
			return result;
		} else if (action == "chat_schedule_run" && (_schedule_outstanding(int(p_args["schedule_id"])) || agent_tabs->get_tab_count() >= 256)) {
			result["error"] = "schedule_run_unavailable";
			return result;
		}
	} else if (action == "chat_set_model_id") {
		if (!safe_name(value, 256, true)) {
			result["error"] = "invalid_model_id";
			return result;
		}
	} else if (action == "chat_set_reasoning") {
		if (value.get_type() == Variant::STRING) {
			for (int i = 0; i < reasoning_picker->get_item_count(); i++) {
				if (reasoning_picker->get_item_metadata(i) == value && !reasoning_picker->is_item_disabled(i)) {
					effort = i;
				}
			}
		}
		if (effort < 0) {
			result["error"] = "unsupported_reasoning_effort";
			return result;
		}
	} else if (action == "chat_set_runtime_field") {
		const String field = p_args.get("field", "");
		if ((field != "node" && field != "codex" && field != "workflow_python" && field != "build_python") || value.get_type() != Variant::STRING || String(value).utf8().length() > 4096) {
			result["error"] = "invalid_runtime_field";
			return result;
		}
	} else if (action == "chat_set_cli_path") {
		const String field = p_args.get("field", "");
		if ((field != "codebuddy_bridge" && field != "codebuddy_entry") || value.get_type() != Variant::STRING || String(value).length() > 4096 || !String(value).is_absolute_path() || String(value).get_extension().to_lower() != "js" || !FileAccess::exists(value) || !(field == "codebuddy_bridge" ? cli_bridge : cli_entry)->is_editable()) {
			result["error"] = "invalid_cli_path";
			return result;
		}
		state["cli_path_hash"] = FileAccess::get_sha256(value);
	} else if (action == "chat_attachment_add") {
		if (value.get_type() != Variant::STRING || draft_images.size() >= 4 || send_button->is_disabled()) {
			result["error"] = "attachment_unavailable";
			return result;
		}
		image_path = value;
		const String extension = image_path.get_extension().to_lower();
		Ref<FileAccess> file = FileAccess::open(image_path, FileAccess::READ);
		const uint64_t image_length = file.is_valid() ? file->get_length() : 0;
		if ((extension != "png" && extension != "jpg" && extension != "jpeg" && extension != "webp") || file.is_null() || image_length > 16 * 1024 * 1024) {
			result["error"] = "invalid_attachment_file";
			return result;
		}
		const PackedByteArray image_bytes = file->get_buffer(image_length);
		if (uint64_t(image_bytes.size()) != image_length) {
			result["error"] = "attachment_file_changed_or_unreadable";
			return result;
		}
		state["attachment_file_content_hash"] = String::hex_encode_buffer(image_bytes.ptr(), image_bytes.size()).sha256_text();
		int image_width = 0, image_height = 0;
		Error header_error = ERR_UNAVAILABLE;
		if (extension == "png") {
			header_error = PNGDriverCommon::png_get_dimensions(image_bytes.ptr(), image_bytes.size(), image_width, image_height);
		}
#ifdef MODULE_JPG_ENABLED
		if (extension == "jpg" || extension == "jpeg") {
			header_error = jpeg_turbo_get_dimensions(image_bytes.ptr(), image_bytes.size(), image_width, image_height);
		}
#endif
#ifdef MODULE_WEBP_ENABLED
		if (extension == "webp") {
			header_error = WebPCommon::webp_get_dimensions(image_bytes.ptr(), image_bytes.size(), image_width, image_height);
		}
#endif
		if (header_error == ERR_UNAVAILABLE) {
			result["error"] = "attachment_format_unavailable_in_this_build";
			return result;
		}
		if (header_error != OK || image_width < 1 || image_height < 1 || image_width > 8192 || image_height > 8192 || int64_t(image_width) * image_height > 32 * 1024 * 1024) {
			result["error"] = "attachment_image_header_invalid_or_oversize";
			return result;
		}
		added_image.instantiate();
		const Error image_error = extension == "png" ? added_image->load_png_from_buffer(image_bytes) : extension == "webp" ? added_image->load_webp_from_buffer(image_bytes)
																															: added_image->load_jpg_from_buffer(image_bytes);
		if (image_error != OK || added_image->is_empty() || added_image->get_width() > 8192 || added_image->get_height() > 8192 || int64_t(added_image->get_width()) * added_image->get_height() > 32 * 1024 * 1024) {
			result["error"] = "invalid_attachment_image";
			return result;
		}
	} else if (action == "chat_attachment_paste") {
		if (draft_images.size() >= 4 || send_button->is_disabled() || DisplayServer::get_singleton()->get_name() == "headless") {
			result["error"] = "clipboard_image_unavailable";
			return result;
		}
		added_image = DisplayServer::get_singleton()->clipboard_get_image();
		if (added_image.is_null() || added_image->is_empty() || added_image->get_width() > 8192 || added_image->get_height() > 8192 || int64_t(added_image->get_width()) * added_image->get_height() > 32 * 1024 * 1024) {
			result["error"] = "clipboard_image_unavailable_or_oversize";
			return result;
		}
		const PackedByteArray pixels = added_image->get_data();
		state["clipboard_image_hash"] = String::hex_encode_buffer(pixels.ptr(), pixels.size()).sha256_text();
		state["clipboard_image_width"] = added_image->get_width();
		state["clipboard_image_height"] = added_image->get_height();
		state["clipboard_image_format"] = added_image->get_format();
	} else if (action == "chat_attachment_remove") {
		if (!bounded_integer(p_args.get("index", Variant()), 0, draft_images.size() - 1) || send_button->is_disabled()) {
			result["error"] = "invalid_attachment_index";
			return result;
		}
		index = p_args["index"];
	} else if (action == "chat_send_message" || action == "chat_host_send_message") {
		if (value.get_type() != Variant::STRING || String(value).strip_edges().is_empty() || String(value).utf8().length() > 8192 || !input->get_text().is_empty() || send_button->is_disabled() || queued_messages.size() >= 32 || !issue_guide_state.is_empty() || !igniter_state.is_empty()) {
			result["error"] = "invalid_message_or_existing_draft";
			return result;
		}
	} else if (action == "chat_show_changes") {
		String error;
		if (value.get_type() != Variant::STRING || !seen.has(value) || !AIChatTools::load_snapshot(_snapshot_path(value), snapshot_data, error) || snapshot_data.get("conversation_id", "") != conversation_id || Array(snapshot_data.get("files", Array())).is_empty()) {
			result["error"] = "snapshot_not_in_current_conversation";
			return result;
		}
		state["snapshot_hash"] = JSON::stringify(snapshot_data).sha256_text();
	} else if (action != "chat_show_history") {
		result["error"] = "unknown_host_chat_action";
		return result;
	}
	Dictionary proposal = p_args.duplicate(true);
	proposal.erase("expected_old_value");
	proposal.erase("expected_target_instance");
	if (action == "chat_close_session" || action == "chat_schedule_delete") {
		proposal["destructive"] = "Deletes the session history, drafts and child/run sessions; applied file changes are retained.";
	}
	result["old_value"] = state;
	result["target_instance"] = int64_t(get_instance_id());
	result["new_value"] = proposal;
	result["manual_confirmation_required"] = true;
	if (!p_confirmed) {
		result["confirmation_required"] = true;
		return result;
	}
	if (p_args.get("expected_target_instance", Variant()).get_type() != Variant::INT || int64_t(p_args["expected_target_instance"]) != int64_t(get_instance_id()) || p_args.get("expected_old_value", Variant()) != Variant(state)) {
		result["error"] = "chat_changed_since_confirmation";
		return result;
	}
	if (action == "chat_rename_session") {
		pending_rename_agent = agent;
		agent_name->set_text(String(value).strip_edges());
		_rename_agent();
		result["title"] = agent_tabs->get_tab_title(_agent_index(agent));
	} else if (action == "chat_close_session") {
		pending_close_agent = agent;
		_close_agent();
		result["closed_agent_id"] = agent;
	} else if (action == "chat_create_child") {
		const int previous = next_agent;
		_add_sub_agent();
		if (active_agent != previous || !sub_agents.has(previous)) {
			result["error"] = "child_creation_failed";
			return result;
		}
		result["child_id"] = previous;
		result["parent_id"] = p_args["parent_id"];
	} else if (action.begins_with("chat_schedule_")) {
		if (schedule >= 0) {
			selected_schedule = Dictionary(schedule_tasks[schedule])["id"];
		}
		if (action == "chat_schedule_create" || action == "chat_schedule_update") {
			const Dictionary definition = value;
			editing_schedule = schedule >= 0 ? selected_schedule : -1;
			schedule_title->set_text(String(definition["title"]).strip_edges());
			schedule_prompt->set_text(definition["prompt"]);
			schedule_frequency->set_value(definition["frequency"]);
			schedule_unit->select(definition["unit"]);
			_save_schedule();
			result["schedule_id"] = selected_schedule;
		} else if (action == "chat_schedule_delete") {
			deleting_schedule = selected_schedule;
			_delete_schedule();
		} else if (action == "chat_schedule_enable") {
			_enable_schedule(value);
		} else if (action == "chat_schedule_run") {
			const int previous = next_agent;
			_run_schedule_now();
			result["run_queued"] = next_agent > previous;
			if (next_agent <= previous) {
				result["error"] = "schedule_run_not_queued";
				return result;
			}
		} else {
			_refresh_schedules();
		}
	} else if (action == "chat_set_model_id") {
		_active_model_field()->set_text(String(value).strip_edges());
		_save_chat_settings();
		_model_edited(String(value));
		result["model_id"] = _active_model_field()->get_text();
	} else if (action == "chat_set_reasoning") {
		reasoning_picker->select(effort);
		_reasoning_selected(effort);
		result["reasoning"] = _reasoning_effort();
	} else if (action == "chat_set_runtime_field") {
		const String error = set_runtime_field(p_args["field"], value);
		if (!error.is_empty()) {
			result["error"] = error;
			return result;
		}
		refresh_runtime_controls();
		result["runtime_paths"] = get_runtime_configuration().get("paths", Dictionary());
	} else if (action == "chat_set_cli_path") {
		LineEdit *field = String(p_args["field"]) == "codebuddy_bridge" ? cli_bridge : cli_entry;
		field->set_text(value);
		_save_chat_settings();
		result["field"] = p_args["field"];
		result["path"] = field->get_text();
	} else if (action == "chat_attachment_add" || action == "chat_attachment_paste") {
		const int previous = draft_images.size();
		_add_image(added_image, action == "chat_attachment_paste" ? String(U"剪贴板截图") : image_path.get_file());
		if (draft_images.size() != previous + 1) {
			result["error"] = "attachment_encoding_or_budget_failed";
			return result;
		}
		result["attachment_index"] = previous;
	} else if (action == "chat_attachment_remove") {
		_remove_image(index);
		result["attachment_count"] = draft_images.size();
	} else if (action == "chat_send_message" || action == "chat_host_send_message") {
		input->set_text(value);
		_send();
		result["send_requested"] = true;
		result["business_completed"] = false;
	} else if (action == "chat_show_history") {
		_show_snapshot_history();
		result["opened"] = snapshot_history_dialog->is_visible();
		if (!bool(result["opened"])) {
			result["error"] = "history_view_not_opened";
			return result;
		}
	} else if (action == "chat_show_changes") {
		_show_snapshot_changes(value);
		result["opened"] = snapshot_changes_dialog->is_visible();
		if (!bool(result["opened"])) {
			result["error"] = "snapshot_view_not_opened";
			return result;
		}
	}
	_queue_history_save();
	result["ok"] = true;
	result["active_agent"] = active_agent;
	result["generation"] = int64_t(session_generation);
	return result;
}
