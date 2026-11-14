/**************************************************************************/
/*  Runtime.cpp                                                           */
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

#include "Runtime.h"

#include <limits>

// Preserve the project Allman convention during formatter migration.
// clang-format off
namespace AICore
{
Runtime::Runtime(const std::string &strIdentity) :
		strIdentity(strIdentity)
{
}

const Run *Runtime::Begin(const std::string &strWorkflow, const std::string &strScope,
		const std::string &strRequest, const std::string &strInput)
{
	if (strIdentity.empty() || strWorkflow.empty() || strScope.empty() || strRequest.empty())
	{
		return nullptr;
	}
	const std::string strKey = std::to_string(strWorkflow.size()) + ":" + strWorkflow +
			std::to_string(strScope.size()) + ":" + strScope + strRequest;
	const std::map<std::string, std::string>::const_iterator itRequest = mapRequests.find(strKey);
	if (itRequest != mapRequests.end())
	{
		const Run *pRun = Find(itRequest->second);
		return pRun != nullptr && pRun->strInput == strInput ? pRun : nullptr;
	}
	if (nGeneration == std::numeric_limits<uint64_t>::max())
	{
		return nullptr;
	}
	Run stRun;
	stRun.strId = strIdentity + "/" + std::to_string(++nGeneration);
	stRun.strWorkflow = strWorkflow;
	stRun.strScope = strScope;
	stRun.strRequest = strRequest;
	stRun.strInput = strInput;
	stRun.nGeneration = nGeneration;
	mapRequests.emplace(strKey, stRun.strId);
	return &mapRuns.emplace(stRun.strId, stRun).first->second;
}

const Run *Runtime::Find(const std::string &strId) const
{
	const std::map<std::string, Run>::const_iterator itRun = mapRuns.find(strId);
	return itRun == mapRuns.end() ? nullptr : &itRun->second;
}

bool Runtime::IsTerminal(State eState)
{
	return eState == State::Succeeded || eState == State::Failed || eState == State::Cancelled;
}

bool Runtime::Apply(const std::string &strId, uint64_t nExpectedGeneration, EventKind eKind, State eState)
{
	const std::map<std::string, Run>::iterator itRun = mapRuns.find(strId);
	if (itRun == mapRuns.end() || itRun->second.nGeneration != nExpectedGeneration ||
			IsTerminal(itRun->second.eState) || itRun->second.nSequence == std::numeric_limits<uint64_t>::max())
	{
		return false;
	}
	State eExpected = eState;
	switch (eKind)
	{
		case EventKind::Completed:
			eExpected = State::Succeeded;
			break;
		case EventKind::Failed:
			eExpected = State::Failed;
			break;
		case EventKind::Cancelled:
			eExpected = State::Cancelled;
			break;
		default:
			if (IsTerminal(eState))
			{
				return false;
			}
			break;
	}
	if (eExpected != eState)
	{
		return false;
	}
	itRun->second.eState = eState;
	++itRun->second.nSequence;
	return true;
}
}
// clang-format on
