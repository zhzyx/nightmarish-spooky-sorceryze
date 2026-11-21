/**************************************************************************/
/*  AIWorkbenchDraft.cpp                                                  */
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

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/file_system/editor_paths.h"
#include "scene/gui/box_container.h"

namespace
{
String GetDraftPath(const String &strKey)
{
	return EditorPaths::get_singleton()->get_data_dir().path_join("business-drafts").path_join(strKey.sha256_text() + ".json");
}
} // namespace

Dictionary AIChatDock::ReadBusinessDraft(const String &strKey) const
{
	const String strPath = GetDraftPath(strKey);
	if (!FileAccess::exists(strPath))
	{
		return Dictionary();
	}
	const Variant varRecord = JSON::parse_string(FileAccess::get_file_as_string(strPath));
	return varRecord.get_type() == Variant::DICTIONARY ? Dictionary(varRecord) : Dictionary();
}

bool AIChatDock::WriteBusinessDraft(const String &strKey, const Dictionary &mapDraft)
{
	ERR_FAIL_COND_V(strKey.is_empty() || strBusinessModule.is_empty(), false);
	const String strPath = GetDraftPath(strKey);
	ERR_FAIL_COND_V(DirAccess::make_dir_recursive_absolute(strPath.get_base_dir()) != OK, false);
	Dictionary mapRecord = mapDraft.duplicate(true);
	mapRecord["text"] = _redact(mapRecord.get("text", ""));
	RedactWorkbenchDraft(stBusinessReferences);
	mapRecord["references"] = stBusinessReferences.arrDraftEditorReferences;
	mapRecord["excerpts"] = stBusinessReferences.mapDraftScriptExcerpts;
	mapRecord["resource_selection"] = stBusinessReferences.bLiveResourceDraft;
	Array arrInvalid;
	for (int nIndex : stBusinessReferences.arrInvalidReferences)
	{
		arrInvalid.push_back(nIndex);
	}
	mapRecord["invalid"] = arrInvalid;
	const String strTemporary = strPath + "." + AIChatResume::make_token() + ".tmp";
	Ref<FileAccess> refFile = FileAccess::open(strTemporary, FileAccess::WRITE);
	ERR_FAIL_COND_V(refFile.is_null(), false);
	const bool bWritten = refFile->store_string(JSON::stringify(mapRecord));
	refFile->flush();
	const Error eError = refFile->get_error();
	refFile.unref();
	if (!bWritten || eError != OK || DirAccess::rename_absolute(strTemporary, strPath) != OK)
	{
		DirAccess::remove_absolute(strTemporary);
		return false;
	}
	return true;
}

void AIChatDock::RestoreBusinessReferences(const Dictionary &mapDraft)
{
	if (strBusinessModule.is_empty())
	{
		return;
	}
	const Array arrReferences = mapDraft.get("references", Array());
	ERR_FAIL_COND(arrReferences.size() > AIChatSessionData::MAX_EDITOR_REFERENCES);
	for (const Variant &varEntry : arrReferences)
	{
		ERR_FAIL_COND(varEntry.get_type() != Variant::DICTIONARY || Dictionary(varEntry).get("object_id", Variant()).get_type() != Variant::STRING);
	}
	stBusinessReferences.arrDraftEditorReferences = arrReferences.duplicate(true);
	stBusinessReferences.mapDraftScriptExcerpts = mapDraft.get("excerpts", Dictionary());
	stBusinessReferences.bLiveResourceDraft = mapDraft.get("resource_selection", false);
	for (const Variant &varIndex : Array(mapDraft.get("invalid", Array())))
	{
		if (varIndex.is_num() && int(varIndex) >= 0 && int(varIndex) < arrReferences.size())
		{
			stBusinessReferences.arrInvalidReferences.push_back(int(varIndex));
		}
	}
	// Only file revisions and frozen script excerpts remain usable across processes.
	WorkbenchReferenceValid(stBusinessReferences, true);
	RefreshWorkbenchReference();
}
