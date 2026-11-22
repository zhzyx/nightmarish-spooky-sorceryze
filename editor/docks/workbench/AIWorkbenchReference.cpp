/**************************************************************************/
/*  AIWorkbenchReference.cpp                                              */
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

#include "core/config/project_settings.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/editor_interface.h"
#include "editor/editor_main_screen.h"
#include "editor/editor_node.h"
#include "editor/inspector/editor_inspector.h"
#include "editor/script/script_editor_plugin.h"
#include "editor/settings/editor_settings.h"
#include "editor/themes/editor_scale.h"
#include "scene/3d/mesh_instance_3d.h"
#include "scene/gui/box_container.h"
#include "scene/gui/button.h"
#include "scene/gui/flow_container.h"
#include "scene/gui/label.h"
#include "scene/gui/scroll_container.h"
#include "scene/gui/text_edit.h"
#include "scene/main/timer.h"

namespace
{
bool IsLiveSceneNode(Node *pNode, Node *pRoot)
{
	if (!pRoot || !pNode || !pNode->is_inside_tree())
	{
		return false;
	}
	for (Node *pAncestor = pNode; pAncestor; pAncestor = pAncestor->get_parent())
	{
		if (pAncestor->is_queued_for_deletion())
		{
			return false;
		}
		if (pAncestor == pRoot)
		{
			return true;
		}
	}
	return false;
}

Dictionary EditorReference(const String &strObject, const String &strSource)
{
	Dictionary mapReference;
	mapReference["kind"] = "editor";
	mapReference["object_id"] = strObject;
	mapReference["revision"] = FileAccess::exists(strSource) ? FileAccess::get_sha256(strSource) : String();
	return mapReference;
}
// Temporary references describe an instance and its inspector edit generation in this editor run.
Dictionary TemporaryResourceReference(Resource *pResource)
{
	static const String strProcess = AIChatResume::make_token();
	const String strTarget = "temporary://" + strProcess + "/" + pResource->get_class() + "/" + itos(int64_t(pResource->get_instance_id()));
	Dictionary mapReference;
	mapReference["kind"] = "editor";
	mapReference["object_id"] = strTarget;
	mapReference["revision"] = (strTarget + ":" + uitos(pResource->get_edited_version())).sha256_text();
	return mapReference;
}

bool ResourceReferenceValid(const Dictionary &mapReference, bool bCheckBytes)
{
	const String strTarget = mapReference.get("object_id", "");
	if (strTarget.begins_with("temporary://"))
	{
		Resource *pResource = ObjectDB::get_instance<Resource>(ObjectID(uint64_t(strTarget.get_file().to_int())));
		return pResource && (pResource->get_path().is_empty() || pResource->get_path().begins_with("local://")) &&
				TemporaryResourceReference(pResource) == mapReference;
	}
	const String strSource = strTarget.get_slice("::", 0);
	return strSource.begins_with("res://") && FileAccess::exists(strSource) && (!bCheckBytes || FileAccess::get_sha256(strSource) == String(mapReference.get("revision", "")));
}

Dictionary PageReference(EditorDock *pPage)
{
	const String strName = pPage->get_display_title();
	const String strModule = pPage->get_meta("_editor_plugin_source", pPage->get_effective_layout_key());
	Dictionary mapReference;
	mapReference["kind"] = "editor";
	const String strId = "editor-page://" + strModule.uri_encode() + "#" + strName.uri_encode();
	mapReference["object_id"] = strId;
	mapReference["revision"] = strId.sha256_text();
	return mapReference;
}

} // namespace

Dictionary AIChatDock::WorkbenchPageSnapshot(const Array &arrReferences)
{
	Dictionary mapContext;
	if (arrReferences.size() != 1)
	{
		return mapContext;
	}
	const String strId = Dictionary(arrReferences[0]).get("object_id", "");
	if (!strId.begins_with("editor-page://"))
	{
		return mapContext;
	}
	const String strLocator = strId.trim_prefix("editor-page://");
	mapContext["page_name"] = strLocator.get_slice("#", 1).uri_decode();
	mapContext["module_id"] = strLocator.get_slice("#", 0).uri_decode();
	mapContext["readable_scope"] = Array({ "page_name", "module_id" });
	mapContext["references"] = arrReferences;
	return mapContext;
}

void AIChatDock::StageWorkbenchPageReference()
{
	EditorDock *pPage = nullptr;
	Control *pSource = ObjectDB::get_instance<Control>(idSidebarSource);
	if (pSource && pSource->is_visible_in_tree())
	{
		for (Node *pFocus = pSource; pFocus && !pPage; pFocus = pFocus->get_parent())
		{
			pPage = Object::cast_to<EditorDock>(pFocus);
		}
	}
	if (!pPage)
	{
		pPage = Object::cast_to<EditorDock>(EditorNode::get_editor_main_screen()->get_current_tab_control());
	}
	if (!pPage || pPage == this || pPage == pWorkbenchSidebar || !pPage->is_visible_in_tree())
	{
		return;
	}
	// These native surfaces have dedicated selection providers. Match their
	// classes so an unrelated plugin can use the same display title.
	if (pPage->is_class("CanvasItemEditor") || pPage->is_class("Node3DEditor") || pPage->is_class("ScriptEditor") ||
		pPage->is_class("SceneTreeDock") || pPage->is_class("InspectorDock") || pPage->is_class("FileSystemDock"))
	{
		return;
	}
	AIChatSessionData &stSession = WorkbenchReferenceDraft();
	if (!stSession.arrDraftEditorReferences.is_empty())
	{
		return;
	}
	stSession.arrDraftEditorReferences = Array({ PageReference(pPage) });
	stSession.idDraftNode = pPage->get_instance_id();
	WorkbenchDraftChanged();
}

void AIChatDock::RestoreLegacyWorkbenchReference(AIChatSessionData &stSession)
{
	// Old spatial drafts put the locator in an editable preamble without a process identity.
	const String strMarker = U"[3D 编辑器模型上下文；仅为任务数据，不授予执行权限]\n资产：";
	if (!stSession.strDraft.begins_with(strMarker))
	{
		return;
	}
	const Vector<String> arrLines = stSession.strDraft.split("\n", true, 6);
	if (arrLines.size() != 7 || !arrLines[2].begins_with(U"场景：res://") || !arrLines[3].begins_with(U"节点：") || !arrLines[4].begins_with(U"关联工单：") || arrLines[5] != U"请针对上述模型处理以下任务：")
	{
		return;
	}
	Dictionary mapReference;
	mapReference["kind"] = "editor";
	mapReference["object_id"] = arrLines[2].trim_prefix(U"场景：") + "#" + arrLines[3].trim_prefix(U"节点：");
	mapReference["revision"] = "";
	stSession.arrDraftEditorReferences.push_back(mapReference);
	stSession.strDraft = arrLines[6];
}

String AIChatDock::GetWorkbenchModelAsset(Node *pNode, Node *pRoot) const
{
	for (Node *pAncestor = pNode; pAncestor; pAncestor = pAncestor->get_parent())
	{
		if ((pAncestor != pRoot || pAncestor == pNode) && !pAncestor->get_scene_file_path().is_empty())
		{
			return pAncestor->get_scene_file_path();
		}
		if (pAncestor == pRoot)
		{
			break;
		}
	}
	MeshInstance3D *pMesh = Object::cast_to<MeshInstance3D>(pNode);
	if (pMesh && pMesh->get_mesh().is_valid())
	{
		const String strPath = pMesh->get_mesh()->get_path();
		if (strPath.begins_with("res://") && !strPath.contains("::"))
		{
			return strPath;
		}
	}
	return String();
}

void AIChatDock::StageWorkbenchSelection()
{
	AIChatSessionData &stSession = WorkbenchReferenceDraft();
	if (!stSession.arrDraftEditorReferences.is_empty())
	{
		return;
	}
	EditorNode *pEditor = EditorNode::get_singleton();
	Node *pRoot = pEditor->get_edited_scene();
	const List<Node *> lstNodes = pEditor->get_editor_selection()->get_full_selected_node_list();
	if (!pRoot || lstNodes.is_empty())
	{
		return;
	}
	if (lstNodes.size() > AIChatSessionData::MAX_EDITOR_REFERENCES)
	{
		_append(TTR("Editor"), vformat(U"当前选区包含 %d 个节点，每条消息最多引用 %d 项。请缩小选区，再打开工作台。", lstNodes.size(), AIChatSessionData::MAX_EDITOR_REFERENCES));
		return;
	}
	const String strScene = pRoot->get_scene_file_path();
	const String strRevision = FileAccess::exists(strScene) ? FileAccess::get_sha256(strScene) : String();
	Array arrReferences;
	Vector<ObjectID> arrNodes;
	for (Node *pNode : lstNodes)
	{
		if (!IsLiveSceneNode(pNode, pRoot))
		{
			return;
		}
		Dictionary mapReference;
		mapReference["kind"] = "editor";
		mapReference["object_id"] = strScene + "#" + String(pRoot->get_path_to(pNode));
		mapReference["revision"] = strRevision;
		arrReferences.push_back(mapReference);
		arrNodes.push_back(pNode->get_instance_id());
	}
	stSession.arrDraftEditorReferences = arrReferences;
	stSession.idDraftScene = pRoot->get_instance_id();
	stSession.arrDraftSelection = arrNodes;
	WorkbenchDraftChanged();
}

String AIChatDock::StageWorkbenchReference(Control *pHost, Node *pNode)
{
	const bool bBusiness = pHost && pHost == pBusinessModules && !strBusinessModule.is_empty();
	AIChatDock *pWorker = bBusiness || !selected_worker ? this : selected_worker;
	if (!bBusiness && (!pHost || pHost->get_instance_id() != pWorker->daqian_chat_host || pWorker->daqian_mount_conversation != pWorker->GetAiSession().strConversation))
	{
		return U"聊天挂载已改变，请重新打开。";
	}
	AIChatSessionData &stSession = bBusiness ? stBusinessReferences : pWorker->GetAiSession();
	TextEdit *pInput = bBusiness ? Object::cast_to<TextEdit>(pHost->get("composer")) : pWorker->input;
	if (!pInput || !stSession.arrDraftEditorReferences.is_empty() || !pInput->get_text().is_empty() || !stSession.arrDraftImages.is_empty() || !stSession.arrQueuedMessages.is_empty())
	{
		return U"已保留原草稿及引用。";
	}
	Node *pRoot = EditorNode::get_singleton()->get_edited_scene();
	if (!IsLiveSceneNode(pNode, pRoot))
	{
		return U"原节点引用已失效，请重新选择。";
	}
	const String strScene = pRoot->get_scene_file_path();
	const String strAsset = GetWorkbenchModelAsset(pNode, pRoot);
	Array arrReferences;
	arrReferences.push_back(EditorReference(strScene + "#" + String(pRoot->get_path_to(pNode)), strScene));
	if (!strAsset.is_empty() && strAsset != strScene)
	{
		arrReferences.push_back(EditorReference(strAsset, strAsset));
	}
	stSession.arrDraftEditorReferences = arrReferences;
	stSession.idDraftScene = pRoot->get_instance_id();
	stSession.idDraftNode = pNode->get_instance_id();
	if (bBusiness)
	{
		WorkbenchDraftChanged();
	}
	else
	{
		pWorker->RefreshWorkbenchReference();
		pWorker->_queue_history_save();
	}
	return String();
}

void AIChatDock::CaptureWorkbenchScriptSelection()
{
	ScriptEditor *pScriptEditor = ScriptEditor::get_singleton();
	AIChatSessionData &stSession = WorkbenchReferenceDraft();
	if (!pScriptEditor || EditorNode::get_editor_main_screen()->get_current_tab_control() != pScriptEditor || (!stSession.arrDraftEditorReferences.is_empty() && stSession.mapDraftScriptExcerpts.is_empty()))
	{
		return;
	}
	ScriptEditorBase *pTab = pScriptEditor->get_current_editor();
	TextEdit *pText = pTab ? Object::cast_to<TextEdit>(pTab->get_base_editor()) : nullptr;
	if (!pText || !pText->has_selection(0))
	{
		return;
	}
	const Ref<Script> refScript = pTab->get_edited_resource();
	if (refScript.is_null() || !refScript->get_path().begins_with("res://"))
	{
		return;
	}
	String strExcerpt = _redact(pText->get_selected_text(0));
	if (!strBusinessModule.is_empty())
	{
		strExcerpt = pBusinessModules->call("redact_reference", strExcerpt);
	}
	const String strLocator = vformat("%s#L%d:%d-L%d:%d", refScript->get_path(), pText->get_selection_from_line() + 1, pText->get_selection_from_column() + 1, pText->get_selection_to_line() + 1, pText->get_selection_to_column() + 1);
	Dictionary mapReference;
	mapReference["kind"] = "editor";
	mapReference["object_id"] = strLocator;
	mapReference["revision"] = pText->get_text().sha256_text();
	if (strExcerpt.is_empty() || strLocator.length() > 1024 || strExcerpt.utf8().length() > 256 * 1024)
	{
		return;
	}
	for (int i = 0; i < stSession.arrDraftEditorReferences.size(); i++)
	{
		if (Dictionary(stSession.arrDraftEditorReferences[i]).get("object_id", "") == strLocator)
		{
			stSession.arrDraftEditorReferences[i] = mapReference;
			stSession.mapDraftScriptExcerpts[strLocator] = strExcerpt;
			stSession.arrInvalidReferences.erase(i);
			WorkbenchDraftChanged();
			return;
		}
	}
	if (stSession.arrDraftEditorReferences.size() >= AIChatSessionData::MAX_EDITOR_REFERENCES)
	{
		_append(TTR("Editor"), U"每条消息最多引用 16 项。");
		return;
	}
	stSession.arrDraftEditorReferences.push_back(mapReference);
	stSession.mapDraftScriptExcerpts[strLocator] = strExcerpt;
	WorkbenchDraftChanged();
}

void AIChatDock::AddWorkbenchResourceSelection(int nSource)
{
	AIChatSessionData &stSession = WorkbenchReferenceDraft();
	if (WorkbenchReferenceLocked() || (strBusinessModule.is_empty() && send_button->is_disabled()))
	{
		return;
	}
	if (!stSession.arrDraftEditorReferences.is_empty() && (!stSession.bLiveResourceDraft || !WorkbenchReferenceValid(stSession, true)))
	{
		_append(TTR("Editor"), U"请先移除当前引用，再添加所选资源。");
		return;
	}
	EditorInterface *pEditor = EditorInterface::get_singleton();
	Vector<String> arrPaths;
	Array arrAdded;
	if (nSource == 0)
	{
		Resource *pResource = Object::cast_to<Resource>(pEditor->get_inspector()->get_edited_object());
		if (pResource)
		{
			const String strPath = pResource->get_path();
			if (strPath.is_empty() || strPath.begins_with("local://"))
			{
				arrAdded.push_back(TemporaryResourceReference(pResource));
			}
			else
			{
				arrPaths.push_back(strPath);
			}
		}
	}
	else if (nSource == 1)
	{
		arrPaths = pEditor->get_selected_paths();
	}
	for (const String &strPath : arrPaths)
	{
		const String strSource = strPath.get_slice("::", 0);
		if (strPath.begins_with("res://") && FileAccess::exists(strSource))
		{
			if (strPath.length() > 1024)
			{
				_append(TTR("Editor"), U"所选资源路径超过单条引用的 1024 字符限制。");
				return;
			}
			const Dictionary mapReference = EditorReference(strPath, strSource);
			if (String(mapReference["revision"]).length() == 64)
			{
				arrAdded.push_back(mapReference);
				if (arrAdded.size() > AIChatSessionData::MAX_EDITOR_REFERENCES)
				{
					break;
				}
			}
		}
	}
	if (arrAdded.is_empty())
	{
		_append(TTR("Editor"), U"请在检查器打开资源，或在文件系统选中文件。");
		return;
	}
	Array arrDraft = stSession.arrDraftEditorReferences.duplicate();
	for (const Dictionary mapReference : arrAdded)
	{
		if (!arrDraft.has(mapReference))
		{
			arrDraft.push_back(mapReference);
		}
	}
	if (arrDraft.size() > AIChatSessionData::MAX_EDITOR_REFERENCES)
	{
		_append(TTR("Editor"), U"每条消息最多引用 16 个对象，请缩小选区。");
		return;
	}
	stSession.arrDraftEditorReferences = arrDraft;
	stSession.bLiveResourceDraft = true;
	WorkbenchDraftChanged();
}

bool AIChatDock::WorkbenchReferenceAtValid(const AIChatSessionData &stSession, int pIndex, bool bCheckBytes)
{
	const Dictionary mapReference = stSession.arrDraftEditorReferences[pIndex];
	const String strTarget = mapReference.get("object_id", "");
	const String strRevision = mapReference.get("revision", "");
	if (mapReference.get("kind", "") != "editor" || strRevision.length() != 64 || !strRevision.is_valid_hex_number(false))
	{
		return false;
	}
	if (strTarget.begins_with("editor-page://"))
	{
		EditorDock *pPage = ObjectDB::get_instance<EditorDock>(stSession.idDraftNode);
		return pPage && !pPage->is_queued_for_deletion() && pPage->is_dock_open() && pPage->is_inside_tree() && PageReference(pPage) == mapReference;
	}
	if (!stSession.mapDraftScriptExcerpts.is_empty())
	{
		return strTarget.begins_with("res://") && strTarget.contains("#L") &&
				stSession.mapDraftScriptExcerpts.get(strTarget, Variant()).get_type() == Variant::STRING &&
				!String(stSession.mapDraftScriptExcerpts[strTarget]).is_empty();
	}
	if (stSession.bLiveResourceDraft)
	{
		return ResourceReferenceValid(mapReference, bCheckBytes);
	}
	Node *pRoot = EditorNode::get_singleton()->get_edited_scene();
	if (!pRoot || pRoot->get_instance_id() != stSession.idDraftScene)
	{
		return false;
	}
	const bool bSceneSelection = !stSession.arrDraftSelection.is_empty();
	if (bSceneSelection && pIndex >= stSession.arrDraftSelection.size())
	{
		return false;
	}
	Node *pNode = ObjectDB::get_instance<Node>(bSceneSelection ? stSession.arrDraftSelection[pIndex] : stSession.idDraftNode);
	if (!IsLiveSceneNode(pNode, pRoot))
	{
		return false;
	}
	String strSource = pRoot->get_scene_file_path();
	if (strTarget != strSource + "#" + String(pRoot->get_path_to(pNode)))
	{
		if (bSceneSelection)
		{
			return false;
		}
		strSource = GetWorkbenchModelAsset(pNode, pRoot);
		if (strSource.is_empty() || strTarget != strSource)
		{
			return false;
		}
	}
	return FileAccess::exists(strSource) && (!bCheckBytes || FileAccess::get_sha256(strSource) == strRevision);
}

bool AIChatDock::WorkbenchReferenceValid(AIChatSessionData &stSession, bool bCheckBytes)
{
	for (int i = 0; i < stSession.arrDraftEditorReferences.size(); i++)
	{
		if (!stSession.arrInvalidReferences.has(i) && !WorkbenchReferenceAtValid(stSession, i, bCheckBytes))
		{
			stSession.arrInvalidReferences.push_back(i);
		}
	}
	return stSession.arrInvalidReferences.is_empty();
}

void AIChatDock::WorkbenchSceneChanged()
{
	Node *pRoot = EditorNode::get_singleton()->get_edited_scene();
	const ObjectID idCurrentRoot = pRoot ? pRoot->get_instance_id() : ObjectID();
	for (KeyValue<int, AgentSession> &entry : agent_sessions)
	{
		if (entry.value.stData.idDraftScene != idCurrentRoot)
		{
			entry.value.stData.idDraftScene = ObjectID();
		}
	}
	RefreshWorkbenchReference();
}

String AIChatDock::WorkbenchIssueContext() const
{
	const String strNumber = _work_order_binding("issue_number");
	if (strNumber.is_empty())
	{
		return U"新需求";
	}
	const Dictionary bindings = EditorSettings::get_singleton()->get_project_metadata("daqian", "bindings", Dictionary());
	const Dictionary entry = bindings.get(GetAiSession().strConversation, Dictionary());
	const String strUrl = entry.get("issue_url", "");
	const String strSource = entry.get("source", "");
	const String strRequest = _work_order_binding("request_id");
	String strIssue = "#" + strNumber;
	if (String(entry.get("issue_number", "")) == strNumber && String(entry.get("request_id", "")) == strRequest)
	{
		if (!strUrl.is_empty())
		{
			strIssue = strUrl;
		}
		else if (strSource.ends_with("/issues/" + strNumber))
		{
			strIssue = strSource;
		}
	}
	return strIssue + (strRequest.is_empty() ? String() : String(U" · ") + strRequest);
}

bool AIChatDock::RedactWorkbenchDraft(AIChatSessionData &pSession) const
{
	bool changed = false;
	for (const Variant &locator : pSession.mapDraftScriptExcerpts.get_key_list())
	{
		const String excerpt = pSession.mapDraftScriptExcerpts[locator];
		const String safe = _redact(excerpt);
		if (safe != excerpt)
		{
			pSession.mapDraftScriptExcerpts[locator] = safe;
			changed = true;
		}
	}
	for (Dictionary message : pSession.arrQueuedMessages)
	{
		if (message.has("editor_references"))
		{
			const String content = message["content"];
			const String safe = _redact(content);
			if (safe != content)
			{
				message["content"] = safe;
				changed = true;
			}
		}
	}
	return changed;
}

AIChatSessionData &AIChatDock::WorkbenchReferenceDraft()
{
	return strBusinessModule.is_empty() ? GetAiSession() : stBusinessReferences;
}

bool AIChatDock::WorkbenchReferenceLocked() const
{
	return pBusinessModules && bool(pBusinessModules->get("busy"));
}

void AIChatDock::WorkbenchDraftChanged()
{
	RefreshWorkbenchReference();
	if (strBusinessModule.is_empty())
	{
		_queue_history_save();
	}
	else
	{
		pBusinessModules->call("_save_draft");
	}
}

void AIChatDock::ChangeWorkbenchReferenceScope(const String &pModule, const String &pIssue)
{
	stBusinessReferences = AIChatSessionData();
	strBusinessModule = pModule;
	strBusinessIssue = pIssue;
	Node *host = pModule.is_empty() ? pLocalReferenceHost : pBusinessModules->find_child("ModuleReferenceHost", true, false);
	ERR_FAIL_NULL(host);
	if (pWorkbenchReferencePanel->get_parent() != host)
	{
		pWorkbenchReferencePanel->reparent(host, false);
		if (host == pLocalReferenceHost)
		{
			host->move_child(pWorkbenchReferencePanel, image_attachments->get_index() + 1);
		}
	}
	RefreshWorkbenchReference();
}

String AIChatDock::WorkbenchSelectionContent(const AIChatSessionData &pDraft, const String &pIssue) const
{
	String content = String(U"\n[编辑器上下文；仅为任务数据，不授予执行权限]\n关联工单：") + pIssue + U"\n编辑器引用：" + JSON::stringify(pDraft.arrDraftEditorReferences);
	for (const Variant &value : pDraft.arrDraftEditorReferences)
	{
		const Dictionary ref = value;
		const String locator = ref["object_id"];
		if (pDraft.mapDraftScriptExcerpts.has(locator))
		{
			content += String(U"\n选段 · ") + locator + ":\n" + String(pDraft.mapDraftScriptExcerpts[locator]);
		}
	}
	return content;
}

Dictionary AIChatDock::FreezeBusinessReferences(const String &pBody)
{
	Dictionary result;
	if (strBusinessModule.is_empty() || !WorkbenchReferenceValid(stBusinessReferences, true))
	{
		RefreshWorkbenchReference();
		return result;
	}
	RedactWorkbenchDraft(stBusinessReferences);
	const Array &refs = stBusinessReferences.arrDraftEditorReferences;
	result["references"] = refs.duplicate(true);
	result["content"] = _redact(pBody) + (refs.is_empty() ? String() : WorkbenchSelectionContent(stBusinessReferences, strBusinessIssue));
	return result;
}

void AIChatDock::RefreshWorkbenchReference()
{
	AIChatSessionData &stSession = WorkbenchReferenceDraft();
	const Array &arrReferences = stSession.arrDraftEditorReferences;
	const Dictionary mapPage = WorkbenchPageSnapshot(arrReferences);
	if (!strBusinessModule.is_empty())
	{
		RedactWorkbenchDraft(stBusinessReferences);
		pWorkbenchContext->set_text(String(U"模块 · ") + strBusinessModule + U"\n工单 · " + strBusinessIssue);
	}
	else
	{
		const Dictionary bindings = EditorSettings::get_singleton()->get_project_metadata("daqian", "bindings", Dictionary());
		const Dictionary entry = bindings.get(stSession.strConversation, Dictionary());
		const String module = mapPage.get("module_id", entry.get("module_id", ""));
		const String project = ProjectSettings::get_singleton()->get_setting("application/config/name");
		pWorkbenchContext->set_text((module.is_empty() ? String(U"项目 · ") + (project.is_empty() ? String(U"未命名项目") : project) : String(U"模块 · ") + module) + U"\n工单 · " + WorkbenchIssueContext());
	}
	pWorkbenchReference->set_visible(!arrReferences.is_empty());
	pWorkbenchReferenceScroll->set_visible(!arrReferences.is_empty());
	while (pWorkbenchReferenceRows->get_child_count() > arrReferences.size())
	{
		Node *row = pWorkbenchReferenceRows->get_child(pWorkbenchReferenceRows->get_child_count() - 1);
		pWorkbenchReferenceRows->remove_child(row);
		row->queue_free();
	}
	if (arrReferences.is_empty())
	{
		pWorkbenchReferenceTimer->stop();
		return;
	}
	const bool bValid = WorkbenchReferenceValid(stSession, false);
	if (stSession.mapDraftScriptExcerpts.is_empty() && stSession.arrInvalidReferences.size() < arrReferences.size())
	{
		if (pWorkbenchReferenceTimer->is_stopped() && is_inside_tree())
		{
			pWorkbenchReferenceTimer->start();
		}
	}
	else
	{
		pWorkbenchReferenceTimer->stop();
	}
	PackedStringArray arrTargets;
	PackedStringArray arrDetails;
	for (int i = 0; i < arrReferences.size(); i++)
	{
		const Dictionary ref = arrReferences[i];
		const String strTarget = ref.get("object_id", "");
		const String strRevision = ref.get("revision", "");
		String strDetail = strTarget + "\n" + (strRevision.is_empty() ? String(U"修订未知") : strRevision);
		if (stSession.mapDraftScriptExcerpts.has(strTarget))
		{
			strDetail += "\n" + _redact(stSession.mapDraftScriptExcerpts[strTarget]);
		}
		const String strStatus = stSession.arrInvalidReferences.has(i) ? String(U"已失效 · ") : String();
		arrTargets.push_back(strTarget.begins_with("temporary://") ? String(U"临时资源 · ") + strTarget : strTarget);
		arrDetails.push_back(strStatus + strDetail);
		Button *pRow = nullptr;
		if (i == pWorkbenchReferenceRows->get_child_count())
		{
			pRow = memnew(Button);
			pRow->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
			pRow->set_text_alignment(HORIZONTAL_ALIGNMENT_LEFT);
			pRow->connect(SNAME("pressed"), callable_mp(this, &AIChatDock::RemoveWorkbenchReferenceAt).bind(i));
			pWorkbenchReferenceRows->add_child(pRow);
		}
		else
		{
			pRow = Object::cast_to<Button>(pWorkbenchReferenceRows->get_child(i));
		}
		pRow->set_text(String(U"移除 · ") + strStatus + strDetail);
	}
	const String strLabel = bValid ? String(U"清空引用 · ") : String(U"引用已失效 · 清空引用 · ");
	pWorkbenchReference->set_autowrap_mode(mapPage.is_empty() ? TextServer::AUTOWRAP_OFF : TextServer::AUTOWRAP_WORD_SMART);
	if (mapPage.is_empty())
	{
		pWorkbenchReference->set_text(strLabel + String(U"、").join(arrTargets));
	}
	else
	{
		const String details = (bValid ? String(U"页面：") : String(U"引用已失效 · 页面：")) + String(mapPage["page_name"]) +
				U"\n模块：" + String(mapPage["module_id"]) + U"\n可读范围：页面名、模块标识";
		pWorkbenchReference->set_text(details);
	}
	pWorkbenchReference->set_tooltip_text(String("\n").join(arrDetails));
	pWorkbenchReferenceScroll->set_custom_minimum_size(Size2(0, MIN(arrReferences.size(), 2) * 72 * EDSCALE));
}

void AIChatDock::RemoveWorkbenchReferenceAt(int pIndex)
{
	if (WorkbenchReferenceLocked())
	{
		return;
	}
	AIChatSessionData &stSession = WorkbenchReferenceDraft();
	ERR_FAIL_INDEX(pIndex, stSession.arrDraftEditorReferences.size());
	if (stSession.arrDraftEditorReferences.size() == 1)
	{
		RemoveWorkbenchReference();
		return;
	}
	stSession.mapDraftScriptExcerpts.erase(Dictionary(stSession.arrDraftEditorReferences[pIndex])["object_id"]);
	stSession.arrDraftEditorReferences.remove_at(pIndex);
	if (!stSession.arrDraftSelection.is_empty())
	{
		stSession.arrDraftSelection.remove_at(pIndex);
	}
	for (int i = stSession.arrInvalidReferences.size() - 1; i >= 0; i--)
	{
		if (stSession.arrInvalidReferences[i] == pIndex)
		{
			stSession.arrInvalidReferences.remove_at(i);
		}
		else if (stSession.arrInvalidReferences[i] > pIndex)
		{
			stSession.arrInvalidReferences.write[i]--;
		}
	}
	WorkbenchDraftChanged();
}

void AIChatDock::RemoveWorkbenchReference()
{
	if (!WorkbenchReferenceLocked())
	{
		ClearWorkbenchReferences(WorkbenchReferenceDraft());
	}
}

void AIChatDock::ClearWorkbenchReferences(AIChatSessionData &stSession)
{
	stSession.arrDraftEditorReferences = Array();
	stSession.mapDraftScriptExcerpts = Dictionary();
	stSession.bLiveResourceDraft = false;
	stSession.idDraftScene = ObjectID();
	stSession.idDraftNode = ObjectID();
	stSession.arrDraftSelection.clear();
	stSession.arrInvalidReferences.clear();
	RefreshWorkbenchReference();
	if (&stSession != &stBusinessReferences)
	{
		_queue_history_save();
	}
}
