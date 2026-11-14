/**************************************************************************/
/*  AIChatDeliveryExecution.h                                                  */
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

#include "core/object/ref_counted.h"
#include "core/templates/list.h"
#include "core/variant/dictionary.h"
#include "core/variant/callable.h"

// Main-thread domain owner. Snapshots are supplied only by the live controller
// after its existing authorization/parent-acceptance checks, never tool arguments.
class AIChatDeliveryExecution : public RefCounted
{
	GDCLASS(AIChatDeliveryExecution, RefCounted);

public:
	struct State
	{
		Dictionary mapPendingRequest;
		Dictionary mapReceipt;
		Dictionary mapRetryRoute;
		String strRetryInstance;
		String strRequestPath;
		String strResultPath;
		bool bExecutionStarted = false;
		bool bQueuePaused = false;
	};

	State &GetState();
	const State &GetState() const;
	Dictionary PrepareDelivery(const Dictionary &mapArguments, const Dictionary &mapScopeSnapshot);
	Dictionary PendingRetry(const Dictionary &mapScopeSnapshot) const;
	Dictionary PrepareRetry(const Dictionary &mapArguments, const Dictionary &mapScopeSnapshot);
	Dictionary BuildProcessArguments(const Dictionary &mapHostSnapshot, String &out_strExecutable, List<String> &out_arrArguments);
	// Requires current delivery_scope and busy alongside process exit/provenance.
	// Returned dictionary replaces the caller's process result.
	Dictionary CaptureResult(const Dictionary &mapProcessResult, const Callable &callRedact = Callable());
	// Removes live request/result, retaining .original.json and diagnostics.
	// Clearing a live request revokes the mapped worker's liveness lease.
	void ClearFiles();

protected:
	static void _bind_methods();

private:
	State stState;
	Dictionary ReadBinding(const Dictionary &mapScopeSnapshot) const;
	bool MatchesScope(const Dictionary &mapScopeSnapshot) const;
	Dictionary CreateRequest(const Dictionary &mapScopeSnapshot, const Dictionary &mapBinding) const;
};
