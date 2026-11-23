/**************************************************************************/
/*  TianxuanModelHost.h                                                   */
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

// Preserve CPP_CODING_STANDARD.md v1.1 Allman style during formatter transition.
// clang-format off

#include "core/object/object_id.h"
#include "core/string/ustring.h"
#include "core/templates/hash_map.h"
#include "core/templates/hash_set.h"
#include "core/variant/array.h"
#include "core/variant/dictionary.h"
#include "scene/main/node.h"

class AIChatDock;

// Main-thread provider adapter. The editor owns this node independently of its views.
// Each request owns an isolated AIChatController through the established consultation loop.
class TianxuanModelHost : public Node
{
	GDCLASS(TianxuanModelHost, Node);

public:
	explicit TianxuanModelHost(AIChatDock *pSettingsOwner);
	Dictionary Configuration() const;
	Dictionary Start(const String &strScope, const String &strRequestId, const Array &arrMessages);
	bool Cancel(const String &strRequestId);

protected:
	static void _bind_methods();
	void _notification(int nWhat);

private:
	ObjectID idSettingsOwner;
	HashMap<String, ObjectID> mapWorkers;
	HashMap<String, Dictionary> mapModels;
	HashSet<String> setConsumedRequests;
	void WorkerFinished(const Dictionary &mapResult, const String &strRequestId, uint64_t nWorkerId);
	void EmitFinished(const String &strRequestId, const Dictionary &mapResult);
};

// clang-format on
