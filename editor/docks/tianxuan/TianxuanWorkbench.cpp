/**************************************************************************/
/*  TianxuanWorkbench.cpp                                                 */
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

#include "TianxuanWorkbench.h"

#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/object/script_language.h"
#include "core/os/os.h"
#include "editor/docks/editor_dock.h"
#include "editor/docks/editor_dock_manager.h"
#include "editor/docks/gonggong_runtime_config.h"
#include "editor/docks/startup_checks.gen.h"
#include "editor/docks/tianxuan/TianxuanModelHost.h"
#include "editor/docks/tianxuan/TianxuanScripts.gen.h"
#include "editor/editor_node.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/control.h"
#include "scene/gui/panel_container.h"
#include "scene/main/node.h"

#ifdef WINDOWS_ENABLED
#include <windows.h>
#elif defined(UNIX_ENABLED)
#include <unistd.h>

#include <cerrno>
#endif

// Install the completed download without replacing a file created during the request.
Error InstallTianxuanAssetIfAbsent(const String &strTemporary, const String &strDestination)
{
#ifdef WINDOWS_ENABLED
	if (MoveFileW((LPCWSTR)strTemporary.utf16().get_data(), (LPCWSTR)strDestination.utf16().get_data()))
	{
		return OK;
	}
	DWORD nError = GetLastError();
	return nError == ERROR_ALREADY_EXISTS || nError == ERROR_FILE_EXISTS ? ERR_ALREADY_EXISTS : ERR_CANT_CREATE;
#elif defined(UNIX_ENABLED)
	if (::link(strTemporary.utf8().get_data(), strDestination.utf8().get_data()) == 0)
	{
		return OK;
	}
	return errno == EEXIST ? ERR_ALREADY_EXISTS : ERR_CANT_CREATE;
#else
	return ERR_UNAVAILABLE;
#endif
}

namespace
{
bool IsLocalProductionSnapshotCurrent(const Dictionary &mapSnapshot)
{
	EditorNode *pEditor = EditorNode::get_singleton();
	Node *pWorkspace = pEditor ? pEditor->get_gui_base()->get_node_or_null(NodePath("TianxuanWorkspaceController")) : nullptr;
	if (!pWorkspace || !pWorkspace->has_method("local_production_specification"))
	{
		return false;
	}
	Dictionary mapCurrent = pWorkspace->call("local_production_specification");
	return !mapCurrent.has("error") && mapCurrent == mapSnapshot;
}

Dictionary PrepareLocalProductionHandoff(const Dictionary &mapSnapshot)
{
	Dictionary mapResult;
	mapResult["ok"] = false;
	if (!IsLocalProductionSnapshotCurrent(mapSnapshot))
	{
		mapResult["error"] = U"账号、对话或已确认规格已变化，请从天璇重新进入。";
		return mapResult;
	}
	EditorNode *pEditor = EditorNode::get_singleton();
	EditorDock *pDock = pEditor ? Object::cast_to<EditorDock>(pEditor->find_child("AINative", true, false)) : nullptr;
	if (!pDock || !pDock->is_inside_tree() || !pDock->has_meta("prepare_spec_handoff"))
	{
		mapResult["error"] = U"马良工作台尚未就绪，请检查内置工具是否可用。";
		return mapResult;
	}
	Callable callablePrepare = pDock->get_meta("prepare_spec_handoff");
	if (!callablePrepare.is_valid())
	{
		mapResult["error"] = U"马良工作台尚未就绪，请检查内置工具是否可用。";
		return mapResult;
	}
	return callablePrepare.call(mapSnapshot, callable_mp_static(&IsLocalProductionSnapshotCurrent));
}

void ClearLocalProductionHandoff()
{
	EditorNode *pEditor = EditorNode::get_singleton();
	EditorDock *pDock = pEditor ? Object::cast_to<EditorDock>(pEditor->find_child("AINative", true, false)) : nullptr;
	if (pDock && pDock->has_meta("clear_spec_handoff"))
	{
		Callable callableClear = pDock->get_meta("clear_spec_handoff");
		if (callableClear.is_valid())
		{
			callableClear.call();
		}
	}
}

String CredentialPython()
{
	return GongGongRuntimeConfig::path(GongGongRuntimeConfig::read_effective(), "workflow_python");
}

String ScriptSource(const char *const *pChunks)
{
	String strSource;
	for (int nChunk = 0; pChunks[nChunk] != nullptr; ++nChunk)
	{
		strSource += String::utf8(pChunks[nChunk]);
	}
	return strSource;
}

Ref<Script> LoadScript(const char *const *pChunks)
{
	Ref<Script> refScript = Object::cast_to<Script>(ClassDB::instantiate("GDScript"));
	ERR_FAIL_COND_V(refScript.is_null(), Ref<Script>());
	refScript->set_source_code(ScriptSource(pChunks));
	ERR_FAIL_COND_V(refScript->reload() != OK, Ref<Script>());
	return refScript;
}

Node *GetWorkspaceController(AIChatDock *pModelSettings)
{
	Control *pRoot = EditorNode::get_singleton()->get_gui_base();
	Node *pController = pRoot->get_node_or_null(NodePath("TianxuanWorkspaceController"));
	if (pController != nullptr)
	{
		return pController;
	}
	Ref<Script> refScript = LoadScript(daqian_workspace_controller);
	ERR_FAIL_COND_V(refScript.is_null(), nullptr);
	Ref<Script> refLocale = LoadScript(daqian_locale);
	ERR_FAIL_COND_V(refLocale.is_null(), nullptr);
	Ref<Script> refDocuments = LoadScript(daqian_document_controller);
	ERR_FAIL_COND_V(refDocuments.is_null(), nullptr);
	Ref<Script> refEditor = LoadScript(daqian_editor_controller);
	ERR_FAIL_COND_V(refEditor.is_null(), nullptr);
	Ref<Script> refIssues = LoadScript(daqian_issue_controller);
	ERR_FAIL_COND_V(refIssues.is_null(), nullptr);
	Ref<Script> refAssetDecoder = LoadScript(daqian_asset_decoder);
	ERR_FAIL_COND_V(refAssetDecoder.is_null(), nullptr);
	Ref<Script> refRepositories = LoadScript(daqian_repositories_controller);
	ERR_FAIL_COND_V(refRepositories.is_null(), nullptr);
	Ref<Script> refRepositoryCollaboration = LoadScript(daqian_repository_collaboration_controller);
	ERR_FAIL_COND_V(refRepositoryCollaboration.is_null(), nullptr);
	Ref<Script> refGameConfig = LoadScript(daqian_game_config_controller);
	ERR_FAIL_COND_V(refGameConfig.is_null(), nullptr);
	Ref<Script> refMigration = LoadScript(daqian_migration_controller);
	ERR_FAIL_COND_V(refMigration.is_null(), nullptr);
	Ref<Script> refAccounts = LoadScript(daqian_accounts_controller);
	ERR_FAIL_COND_V(refAccounts.is_null(), nullptr);
	Ref<Script> refExecution = LoadScript(daqian_execution_controller);
	ERR_FAIL_COND_V(refExecution.is_null(), nullptr);
	Ref<Script> refLocalConversation = LoadScript(daqian_local_conversation_controller);
	ERR_FAIL_COND_V(refLocalConversation.is_null(), nullptr);
	Node *pSession = GetTianxuanSessionController();
	ERR_FAIL_NULL_V(pSession, nullptr);
	TianxuanModelHost *pModelHost = memnew(TianxuanModelHost(pModelSettings));
	pModelHost->set_name("TianxuanModelHost");
	pRoot->add_child(pModelHost);
	pController = memnew(Node);
	pController->set_name("TianxuanWorkspaceController");
	pController->set_script(refScript);
	pController->set_meta("session_controller", pSession);
	pController->set_meta("locale_script", refLocale);
	pController->set_meta("document_script", refDocuments);
	pController->set_meta("editor_script", refEditor);
	pController->set_meta("issue_script", refIssues);
	pController->set_meta("asset_decoder_script", refAssetDecoder);
	pController->set_meta("repository_script", refRepositories);
	pController->set_meta("repository_collaboration_script", refRepositoryCollaboration);
	pController->set_meta("game_config_script", refGameConfig);
	pController->set_meta("migration_script", refMigration);
	pController->set_meta("accounts_script", refAccounts);
	pController->set_meta("execution_script", refExecution);
	pController->set_meta("local_conversation_script", refLocalConversation);
	pController->set_meta("model_host", pModelHost);
	pController->set_meta("local_production_handoff", callable_mp_static(&PrepareLocalProductionHandoff));
	pController->set_meta("local_production_clear", callable_mp_static(&ClearLocalProductionHandoff));
	pController->set_meta("install_asset_if_absent", callable_mp_static(&InstallTianxuanAssetIfAbsent));
	pController->set("storage_root", EditorPaths::get_singleton()->get_data_dir().path_join("tianxuan-drafts"));
	pRoot->add_child(pController);
	return pController;
}

Control *CreateView(Node *pController, bool bCompact)
{
	Ref<Script> refScript = LoadScript(daqian_workspace_view);
	ERR_FAIL_COND_V(refScript.is_null(), nullptr);
	Dictionary mapScripts;
	mapScripts["theme"] = LoadScript(daqian_native_theme);
	mapScripts["markdown"] = LoadScript(daqian_markdown_view);
	mapScripts["home"] = LoadScript(daqian_home_page);
	mapScripts["documents"] = LoadScript(daqian_documents_page);
	mapScripts["design"] = LoadScript(daqian_design_page);
	mapScripts["issues"] = LoadScript(daqian_issues_page);
	mapScripts["issue_assets"] = LoadScript(daqian_issue_assets);
	mapScripts["issue_flow"] = LoadScript(daqian_issue_flow);
	mapScripts["repos"] = LoadScript(daqian_repositories_page);
	mapScripts["repository_collaboration"] = LoadScript(daqian_repository_collaboration_page);
	mapScripts["game_config"] = LoadScript(daqian_game_config_page);
	mapScripts["migration"] = LoadScript(daqian_migration_page);
	mapScripts["accounts"] = LoadScript(daqian_accounts_page);
	mapScripts["execution"] = LoadScript(daqian_execution_page);
	Ref<Script> refLibrary = LoadScript(daqian_library_page);
	mapScripts["requirements"] = refLibrary;
	mapScripts["runs"] = refLibrary;
	mapScripts["search"] = refLibrary;
	for (const Variant &varKey : mapScripts.keys())
	{
		Ref<Script> refPageScript = mapScripts[varKey];
		ERR_FAIL_COND_V(refPageScript.is_null(), nullptr);
	}
	PanelContainer *pView = memnew(PanelContainer);
	pView->set_script(refScript);
	pView->set_meta("controller", pController);
	pView->set_meta("compact", bCompact);
	pView->set_meta("scripts", mapScripts);
	return pView;
}
} // namespace

Node *GetTianxuanSessionController()
{
	Control *pRoot = EditorNode::get_singleton()->get_gui_base();
	Node *pController = pRoot->get_node_or_null(NodePath("TianxuanSessionController"));
	if (pController != nullptr)
	{
		return pController;
	}
	Ref<Script> refScript = LoadScript(daqian_session_controller);
	ERR_FAIL_COND_V(refScript.is_null(), nullptr);
	pController = memnew(Node);
	pController->set_name("TianxuanSessionController");
	pController->set_script(refScript);
	const String strPreviousUrl = EDITOR_DEF("network/web_platform/url", "");
	pController->set("credential_transport", LoadScript(daqian_session_memory));
	pController->set("helper_source", ScriptSource(daqian_session_credentials));
	pController->set("credential_python", callable_mp_static(&CredentialPython));
	if (OS::get_singleton()->get_environment("TIANXUAN_API").is_empty() && !strPreviousUrl.is_empty())
	{
		pController->call("set_origin", strPreviousUrl);
	}
	pRoot->add_child(pController);
	return pController;
}

EditorDock *CreateTianxuanDock(AIChatDock *pModelSettings)
{
	Node *pController = GetWorkspaceController(pModelSettings);
	ERR_FAIL_NULL_V(pController, nullptr);
	Control *pMainView = CreateView(pController, false);
	ERR_FAIL_NULL_V(pMainView, nullptr);
	Control *pSidebarView = CreateView(pController, true);
	if (pSidebarView == nullptr)
	{
		memdelete(pMainView);
		return nullptr;
	}
	EditorDock *pMain = memnew(EditorDock);
	// Preserve the saved main-screen location while replacing its implementation.
	pMain->set_name("WebPlatform");
	pMain->set_title(U"天璇");
	pMain->set_layout_key("WebPlatformMainScreen");
	pMain->set_icon_name("WorldEnvironment");
	pMain->set_available_layouts(EditorDock::DOCK_LAYOUT_MAIN_SCREEN);
	pMain->set_default_slot(EditorDock::DOCK_SLOT_MAIN_SCREEN);
	pMain->add_child(pMainView);

	EditorDock *pSidebar = memnew(EditorDock);
	pSidebar->set_name("TianxuanSidebar");
	pSidebar->set_title(U"天璇侧栏");
	pSidebar->set_layout_key("TianxuanSidebar");
	pSidebar->set_icon_name("WorldEnvironment");
	pSidebar->set_available_layouts(EditorDock::DOCK_LAYOUT_VERTICAL | EditorDock::DOCK_LAYOUT_FLOATING);
	pSidebar->set_default_slot(EditorDock::DOCK_SLOT_RIGHT_UL);
	pSidebar->set_closable(true);
	pSidebarView->set_meta("auxiliary_dock", pSidebar);
	pSidebar->add_child(pSidebarView);
	pMainView->connect("companion_requested", callable_mp(pSidebar, &EditorDock::make_visible));
	pSidebarView->connect("companion_requested", callable_mp(pSidebar, &EditorDock::ToggleAuxiliaryExpanded));
	pSidebar->connect("auxiliary_expansion_changed", Callable(pSidebarView, "auxiliary_expansion_changed"));
	// Full workspace navigation is distinct from expanding the current chat.
	pSidebarView->connect("workspace_requested", callable_mp(EditorDockManager::get_singleton(), &EditorDockManager::force_focus_dock).bind(pMain));
	EditorDockManager::get_singleton()->add_dock(pSidebar);
	pSidebar->close();
	return pMain;
}
