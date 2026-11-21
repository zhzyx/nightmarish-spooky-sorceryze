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

#include "core/io/file_access.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/editor_node.h"
#include "scene/3d/mesh_instance_3d.h"
#include "scene/gui/button.h"
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
} // namespace

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

String AIChatDock::StageWorkbenchReference(Control *pHost, Node *pNode)
{
	AIChatDock *pWorker = selected_worker ? selected_worker : this;
	if (!pHost || pHost->get_instance_id() != pWorker->daqian_chat_host || pWorker->daqian_mount_conversation != pWorker->GetAiSession().strConversation)
	{
		return U"聊天挂载已改变，请重新打开。";
	}
	AIChatSessionData &stSession = pWorker->GetAiSession();
	if (!stSession.arrDraftEditorReferences.is_empty() || !pWorker->input->get_text().is_empty() || !stSession.arrDraftImages.is_empty() || !stSession.arrQueuedMessages.is_empty())
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
	pWorker->RefreshWorkbenchReference();
	pWorker->_queue_history_save();
	return String();
}

bool AIChatDock::WorkbenchReferenceValid(bool bCheckBytes)
{
	AIChatSessionData &stSession = GetAiSession();
	const Array &arrReferences = stSession.arrDraftEditorReferences;
	Node *pRoot = EditorNode::get_singleton()->get_edited_scene();
	Node *pNode = ObjectDB::get_instance<Node>(stSession.idDraftNode);
	if (!IsLiveSceneNode(pNode, pRoot) || pRoot->get_instance_id() != stSession.idDraftScene)
	{
		return false;
	}
	const String strScene = pRoot->get_scene_file_path();
	const String strAsset = GetWorkbenchModelAsset(pNode, pRoot);
	if (arrReferences.size() != ((!strAsset.is_empty() && strAsset != strScene) ? 2 : 1))
	{
		return false;
	}
	for (int32_t nIndex = 0; nIndex < arrReferences.size(); ++nIndex)
	{
		const String strSource = nIndex == 0 ? strScene : strAsset;
		const String strTarget = nIndex == 0 ? strScene + "#" + String(pRoot->get_path_to(pNode)) : strAsset;
		const Dictionary mapReference = arrReferences[nIndex];
		const String strRevision = mapReference.get("revision", "");
		if (mapReference.get("object_id", "") != strTarget || strRevision.length() != 64 || !FileAccess::exists(strSource) || (bCheckBytes && FileAccess::get_sha256(strSource) != strRevision))
		{
			return false;
		}
	}
	return true;
}

void AIChatDock::WorkbenchSceneChanged()
{
	Node *pRoot = EditorNode::get_singleton()->get_edited_scene();
	const ObjectID idCurrentRoot = pRoot ? pRoot->get_instance_id() : ObjectID();
	for (KeyValue<int, AgentSession> &entry : agent_sessions)
	{
		if (entry.value.stData.idDraftScene != idCurrentRoot)
		{
			entry.value.stData.idDraftNode = ObjectID();
		}
	}
	RefreshWorkbenchReference();
}

void AIChatDock::RefreshWorkbenchReference()
{
	const Array &arrReferences = GetAiSession().arrDraftEditorReferences;
	pWorkbenchReference->set_visible(!arrReferences.is_empty());
	if (arrReferences.is_empty())
	{
		pWorkbenchReferenceTimer->stop();
		return;
	}
	const bool bValid = WorkbenchReferenceValid(false);
	if (!bValid)
	{
		// An observed mismatch stays invalid until the user explicitly selects again.
		GetAiSession().idDraftNode = ObjectID();
		pWorkbenchReferenceTimer->stop();
	}
	else if (pWorkbenchReferenceTimer->is_stopped() && is_inside_tree())
	{
		pWorkbenchReferenceTimer->start();
	}
	const String strTarget = Dictionary(arrReferences[0]).get("object_id", "");
	const String strLabel = (bValid ? String(U"编辑器引用 · ") : String(U"引用已失效 · ")) + strTarget;
	pWorkbenchReference->set_text(strLabel);
	String strDetails = strLabel;
	if (arrReferences.size() == 2)
	{
		strDetails += "\n" + String(Dictionary(arrReferences[1]).get("object_id", ""));
	}
	pWorkbenchReference->set_tooltip_text(strDetails + U"\n点击移除此引用");
}

void AIChatDock::RemoveWorkbenchReference()
{
	GetAiSession().arrDraftEditorReferences = Array();
	GetAiSession().idDraftScene = ObjectID();
	GetAiSession().idDraftNode = ObjectID();
	RefreshWorkbenchReference();
	_queue_history_save();
}
