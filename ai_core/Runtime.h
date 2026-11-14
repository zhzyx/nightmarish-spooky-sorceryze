/**************************************************************************/
/*  Runtime.h                                                             */
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

#include <cstdint>
#include <map>
#include <string>

// Preserve the project Allman convention during formatter migration.
// clang-format off
namespace AICore
{
enum class State : uint8_t
{
	Running,
	WaitingTool,
	WaitingConfirmation,
	Reconciling,
	Succeeded,
	Failed,
	Cancelled,
};

enum class EventKind : uint8_t
{
	Progress,
	TextDelta,
	ToolRequested,
	ArtifactReady,
	Completed,
	Failed,
	Cancelled,
};

struct Run
{
	std::string strId;
	std::string strWorkflow;
	std::string strScope;
	std::string strRequest;
	std::string strInput;
	uint64_t nGeneration = 0;
	uint64_t nSequence = 1;
	State eState = State::Running;
};

// One runtime belongs to one serialized executor. Hosts synchronize access and
// retain the runtime independently of any view. Input is an opaque canonical
// serialization of the frozen model and binding, never a credential store.
class Runtime final
{
public:
	explicit Runtime(const std::string &strIdentity);
	const Run *Begin(const std::string &strWorkflow, const std::string &strScope,
			const std::string &strRequest, const std::string &strInput);
	const Run *Find(const std::string &strId) const;
	bool Apply(const std::string &strId, uint64_t nGeneration, EventKind eKind, State eState);
	static bool IsTerminal(State eState);

private:
	std::string strIdentity;
	uint64_t nGeneration = 0;
	std::map<std::string, Run> mapRuns;
	std::map<std::string, std::string> mapRequests;
};
}
// clang-format on
