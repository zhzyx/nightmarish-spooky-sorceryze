/**************************************************************************/
/*  unified_settings_editor_plugin.h                                      */
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

#include "core/templates/hash_set.h"
#include "editor/plugins/editor_plugin.h"

class EditorDock;
class TabContainer;
class VBoxContainer;

class UnifiedSettingsEditorPlugin : public EditorPlugin {
	GDCLASS(UnifiedSettingsEditorPlugin, EditorPlugin);

	struct Attachment {
		ObjectID source;
		ObjectID control;
		ObjectID original_parent;
	};
	Vector<Attachment> attachments;
	HashSet<ObjectID> watched_sources;
	EditorDock *dock = nullptr;
	ObjectID dock_id;
	TabContainer *categories = nullptr;
	VBoxContainer *chat_ai = nullptr;
	VBoxContainer *art_ai = nullptr;
	VBoxContainer *catalog_ai = nullptr;
	VBoxContainer *chat_environment = nullptr;
	VBoxContainer *art_environment = nullptr;
	bool binding = false;
	bool shutting_down = false;

	void _borrow(Control *p_control, VBoxContainer *p_target, Node *p_source);
	void _watch_source(Node *p_source);
	void _source_exiting(uint64_t p_id);
	void _restore_source(ObjectID p_source);
	void _restore_all();
	void _bind_sources();
	void _visibility_changed();
	void _dock_exiting();
	void _open_section(const String &p_section);

protected:
	static void _bind_methods();
	void _notification(int p_what);

public:
	virtual String get_plugin_name() const override { return U"设置"; }
	UnifiedSettingsEditorPlugin();
	~UnifiedSettingsEditorPlugin();
};
