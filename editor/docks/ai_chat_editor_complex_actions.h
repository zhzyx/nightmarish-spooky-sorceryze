/**************************************************************************/
/*  ai_chat_editor_complex_actions.h                                      */
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

#include "core/object/object.h"
#include "core/object/ref_counted.h"
#include "core/templates/hash_map.h"
#include "core/variant/dictionary.h"

class Node;

// A closed semantic vocabulary; never exposes arbitrary calls or signals.
class AIChatEditorComplexActions {
	struct ResourceUndo {
		ObjectID resource;
		int history = -99;
		uint64_t version = 0;
		Dictionary before;
		Dictionary after;
		bool undone = false;
		uint64_t epoch = 0;
	};
	HashMap<ObjectID, ResourceUndo> resource_undo;
	Ref<RefCounted> history_fence;
	ObjectID history_manager;

public:
	static bool supports(const String &p_action);
	static bool target(Node *p_node);
	static Array actions(Node *p_node);
	static Dictionary state(Node *p_node);
	Dictionary perform(Node *p_node, const String &p_id, const Dictionary &p_args, bool p_confirmed);
};
