/**************************************************************************/
/*  GameReceiptGuard.cpp                                                  */
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

#include "core/io/json.h"
#include "core/os/os.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/ai_chat_host_runtime.h"
#include "editor/docks/gonggong_runtime_config.h"

Dictionary AIChatDock::GetGameReceiptGuard(String &out_strError, const Dictionary &mapRuntime, bool bPrepare, const Dictionary &mapReporting) const
{
	const String strPython = GongGongRuntimeConfig::path(mapRuntime, "workflow_python");
	const String strWorker = _engine_root().path_join("tools/editor_provenance_guard.py");
	List<String> arrArguments;
	for (const String &strArgument : { strWorker, String("--game-workspace"), _workflow_root(), String("--game-reporting"), JSON::stringify(mapReporting.is_empty() ? gonggong_reporting : mapReporting), String(bPrepare ? "--prepare-game" : "--recover-game") })
	{
		arrArguments.push_back(strArgument);
	}
	String strOutput;
	int nExitCode = -1;
	const Error eResult = OS::get_singleton()->execute(strPython, arrArguments, &strOutput, &nExitCode);
	const Variant varParsed = JSON::parse_string(strOutput.strip_edges());
	if (eResult != OK || nExitCode != 0 || varParsed.get_type() != Variant::DICTIONARY || !bool(Dictionary(varParsed).get("ok", false)))
	{
		out_strError = "game_receipt_guard_failed: " + strOutput.left(1000);
		return Dictionary();
	}
	if (!bPrepare)
	{
		return varParsed;
	}
	return AIChatHostRuntime::command_guard(varParsed, strPython, _engine_root(), out_strError);
}
