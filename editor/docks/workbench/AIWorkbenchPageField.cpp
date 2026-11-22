/**************************************************************************/
/*  AIWorkbenchPageField.cpp                                              */
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

#include "AIWorkbenchPageField.h"

#include "core/config/project_settings.h"
#include "core/io/json.h"
#include "editor/docks/ai_chat_resume.h"
#include "editor/docks/editor_dock.h"
#include "scene/gui/line_edit.h"

namespace
{
constexpr int MAX_FIELD_LENGTH = 4096;

EditorDock *GetFieldPage(LineEdit *pField)
{
	for (Node *pNode = pField; pNode && !pNode->is_queued_for_deletion(); pNode = pNode->get_parent())
	{
		EditorDock *pPage = Object::cast_to<EditorDock>(pNode);
		if (pPage)
		{
			return pPage->is_inside_tree() && pPage->is_dock_open() ? pPage : nullptr;
		}
	}
	return nullptr;
}

Dictionary DescribeField(LineEdit *pField, EditorDock *pPage)
{
	if (!pField || !pPage || pField->is_secret() || pField->get_text().length() > MAX_FIELD_LENGTH)
	{
		return Dictionary();
	}
	const Variant varFields = pPage->get_meta("workbench_fields", Dictionary());
	const String strField = String(pPage->get_path_to(pField));
	const Variant varMode = varFields.get_type() == Variant::DICTIONARY ? Dictionary(varFields).get(strField, Variant()) : Variant();
	if (varMode != "read" && varMode != "replace_text")
	{
		return Dictionary();
	}
	const bool bEditable = varMode == "replace_text" && pField->is_editable();
	const String strPage = pPage->get_display_title();
	const String strModule = pPage->get_meta("_editor_plugin_source", pPage->get_effective_layout_key());
	const String strTarget = "editor-page://" + strModule.uri_encode() + "#" + strPage.uri_encode() + "#" + strField.uri_encode() + "#" + uitos(pField->get_instance_id());
	if (strTarget.length() > 1024)
	{
		return Dictionary();
	}
	static const String strProcessNonce = AIChatResume::make_token();
	Dictionary mapRef;
	mapRef["kind"] = "editor";
	mapRef["object_id"] = strTarget;
	mapRef["revision"] = JSON::stringify(Array({ strProcessNonce, ProjectSettings::get_singleton()->get_resource_path(), uitos(pPage->get_instance_id()), strTarget, pField->get_text(), bEditable })).sha256_text();
	Dictionary mapResult;
	mapResult["field"] = strField;
	mapResult["value"] = pField->get_text();
	mapResult["actions"] = bEditable ? Array({ "replace_page_field" }) : Array();
	if (bEditable)
	{
		mapResult["required_authorization"] = "confirm_exact_replacement";
	}
	mapResult["reference"] = mapRef;
	return mapResult;
}

LineEdit *ResolveField(const String &strTarget)
{
	if (!strTarget.begins_with("editor-page://") || strTarget.get_slice_count("#") != 4)
	{
		return nullptr;
	}
	const String strInstance = strTarget.get_slice("#", 3);
	if (!strInstance.is_valid_int())
	{
		return nullptr;
	}
	return ObjectDB::get_instance<LineEdit>(ObjectID(uint64_t(strInstance.to_int())));
}

Dictionary FieldError(const String &strError)
{
	Dictionary mapResult;
	mapResult["ok"] = false;
	mapResult["error"] = strError;
	return mapResult;
}
} // namespace

Dictionary AIWorkbenchPageField::Capture(EditorDock *pPage, Control *pFocus)
{
	LineEdit *pField = Object::cast_to<LineEdit>(pFocus);
	if (!pField || !pField->is_visible_in_tree() || GetFieldPage(pField) != pPage)
	{
		return Dictionary();
	}
	return DescribeField(pField, pPage).get("reference", Dictionary());
}

Dictionary AIWorkbenchPageField::Snapshot(const Dictionary &mapReference)
{
	LineEdit *pField = ResolveField(mapReference.get("object_id", ""));
	Dictionary mapResult = DescribeField(pField, GetFieldPage(pField));
	if (mapResult.get("reference", Variant()) != mapReference)
	{
		return Dictionary();
	}
	mapResult.erase("reference");
	return mapResult;
}

Dictionary AIWorkbenchPageField::Replace(const Dictionary &mapArgs, bool bConfirmed)
{
	const String strTarget = mapArgs.get("target", "");
	const Variant varReplacement = mapArgs.get("value", Variant());
	if (varReplacement.get_type() != Variant::STRING || String(varReplacement).length() > MAX_FIELD_LENGTH || String(varReplacement).strip_escapes() != String(varReplacement))
	{
		return FieldError("invalid_field_value");
	}
	LineEdit *pField = ResolveField(strTarget);
	const Dictionary mapDetails = DescribeField(pField, GetFieldPage(pField));
	const Dictionary mapRef = mapDetails.get("reference", Dictionary());
	if (mapRef.is_empty() || mapRef["object_id"] != strTarget || mapRef["revision"] != mapArgs.get("revision", Variant()))
	{
		return FieldError("stale_field_reference");
	}
	if (Array(mapDetails["actions"]).is_empty())
	{
		return FieldError("read_only_field");
	}
	if (pField->get_max_length() > 0 && String(varReplacement).length() > pField->get_max_length())
	{
		return FieldError("invalid_field_value");
	}
	Dictionary mapResult;
	mapResult["ok"] = true;
	mapResult["target"] = strTarget;
	mapResult["field"] = mapDetails["field"];
	mapResult["revision"] = mapRef["revision"];
	mapResult["old_value"] = pField->get_text();
	mapResult["new_value"] = varReplacement;
	if (!bConfirmed)
	{
		mapResult["confirmation_required"] = true;
		mapResult["manual_confirmation_required"] = true;
		return mapResult;
	}
	if (mapArgs.get("expected_old_value", Variant()) != mapResult["old_value"])
	{
		return FieldError("stale_field_preview");
	}
	if (mapResult["old_value"] != varReplacement)
	{
		pField->set_text(varReplacement);
		pField->emit_signal(SNAME("text_changed"), varReplacement);
	}
	pField = ResolveField(strTarget);
	const Dictionary mapUpdated = DescribeField(pField, GetFieldPage(pField));
	if (mapUpdated.is_empty() || mapUpdated["value"] != varReplacement || Dictionary(mapUpdated["reference"])["object_id"] != strTarget)
	{
		return FieldError("field_readback_failed");
	}
	mapResult["updated_reference"] = mapUpdated["reference"];
	return mapResult;
}
