/**************************************************************************/
/*  AIWorkbenchSidebar.cpp                                                */
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

#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/object/script_language.h"
#include "editor/docks/ai_chat_dock.h"
#include "editor/docks/dock_tab_container.h"
#include "editor/docks/editor_dock_manager.h"
#include "editor/docks/workbench/AIWorkbenchWindow.h"
#include "editor/docks/workbench/BusinessSession.gen.h"
#include "editor/docks/workbench/IssueCreation.gen.h"
#include "editor/docks/workbench/module_selector.gen.h"
#include "editor/editor_main_screen.h"
#include "editor/editor_node.h"
#include "editor/settings/editor_command_palette.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/box_container.h"
#include "scene/gui/button.h"
#include "scene/gui/check_box.h"
#include "scene/gui/menu_button.h"
#include "scene/gui/popup_menu.h"
#include "scene/gui/text_edit.h"
#include "scene/main/viewport.h"

static constexpr char WORKBENCH_SHORTCUT[] = "editor/open_ai_workbench";

static Ref<Script> LoadWorkbenchControlScript(const char *const *pChunks)
{
	Ref<Script> refScript = Object::cast_to<Script>(ClassDB::instantiate("GDScript"));
	ERR_FAIL_COND_V(refScript.is_null(), Ref<Script>());
	String strSource;
	for (int nChunk = 0; pChunks[nChunk]; nChunk++)
	{
		strSource += String::utf8(pChunks[nChunk]);
	}
	refScript->set_source_code(strSource);
	ERR_FAIL_COND_V(refScript->reload() != OK, Ref<Script>());
	return refScript;
}

static VBoxContainer *MountWorkbenchControl(Node *pParent, const char *pName, const char *const *pChunks)
{
	Ref<Script> refScript = LoadWorkbenchControlScript(pChunks);
	ERR_FAIL_COND_V(refScript.is_null(), nullptr);
	VBoxContainer *pControl = memnew(VBoxContainer);
	pControl->set_name(pName);
	pControl->set_script(refScript);
	pParent->add_child(pControl);
	return pControl;
}

void AIChatDock::RegisterWorkbenchSidebar(EditorCommandPalette *pPalette, Button *pTitleButton)
{
	add_child(CreateWorkbenchWindowRouter(pConversationView, input, agent_name, pPalette, callable_mp(this, &AIChatDock::PrepareWorkbenchConsultation)));
	// The view controls and command palette take focus before moving the composer.
	input->set_deselect_on_focus_loss_enabled(false);
	pWorkbenchSidebar = memnew(EditorDock);
	pWorkbenchSidebar->set_name("AIWorkbenchSidebar");
	pWorkbenchSidebar->set_title(TTR("AI Workbench"));
	pWorkbenchSidebar->set_layout_key("AIWorkbenchSidebar");
	pWorkbenchSidebar->set_meta("ai_control_page_only", true);
	pWorkbenchSidebar->set_icon_name("AIChatWave");
	// Share the right column with Inspector so narrow windows retain their editing viewport.
	pWorkbenchSidebar->set_default_slot(DOCK_SLOT_RIGHT_UL);
	pWorkbenchSidebar->set_available_layouts(DOCK_LAYOUT_VERTICAL);
	pWorkbenchSidebar->set_global(false);
	pWorkbenchSidebar->set_transient(true);
	pWorkbenchSidebar->set_closable(true);
	pSidebarLayout = memnew(VBoxContainer);
	pWorkbenchSidebar->add_child(pSidebarLayout);
	Button *pExpand = memnew(Button);
	pExpand->set_name("ExpandWorkbench");
	pExpand->set_text(TTR("Expand AI Workbench"));
	pExpand->connect(SNAME("pressed"), callable_mp(this, &AIChatDock::ExpandWorkbenchSidebar));
	pSidebarLayout->add_child(pExpand);
	// The editor owns this session for the lifetime of the sidebar.
	VBoxContainer *pSession = MountWorkbenchControl(pSidebarLayout, "WorkbenchBusinessSession", daqian_business_session);
	if (pSession)
	{
		Ref<Script> refParagraphSuggestion = LoadWorkbenchControlScript(daqian_paragraph_suggestion);
		if (refParagraphSuggestion.is_valid())
		{
			pSession->call("install_paragraph_suggestion", refParagraphSuggestion);
		}
		MountWorkbenchControl(pSession, "WorkbenchIssueCreation", daqian_issue_creation);
		MountWorkbenchControl(pSession, "WorkbenchIssueDetail", daqian_issue_detail);
	}
	MenuButton *pResourceMenu = memnew(MenuButton);
	pResourceMenu->set_name("WorkbenchResourceSelection");
	pResourceMenu->set_text(TTR("Attach Resource"));
	pResourceMenu->get_popup()->add_item(TTR("From Inspector"), 0);
	pResourceMenu->get_popup()->add_item(TTR("From FileSystem"), 1);
	pResourceMenu->get_popup()->connect(SNAME("id_pressed"), callable_mp(this, &AIChatDock::AddWorkbenchResourceSelection));
	pSidebarLayout->add_child(pResourceMenu);
	Button *pClose = memnew(Button);
	pClose->set_text(TTR("Close AI Workbench"));
	pClose->set_name("CloseWorkbench");
	pClose->connect(SNAME("pressed"), callable_mp(pWorkbenchSidebar, &EditorDock::close));
	pSidebarLayout->add_child(pClose);
	pRestoreSidebar = memnew(Button);
	pRestoreSidebar->set_name("RestoreWorkbenchSidebar");
	pRestoreSidebar->set_text(TTR("Return to Sidebar"));
	pRestoreSidebar->connect(SNAME("pressed"), callable_mp(this, &AIChatDock::OpenWorkbenchSidebar));
	workspace_pages->get_internal_container()->add_child(pRestoreSidebar);
	pRestoreSidebar->hide();
	EditorDockManager::get_singleton()->add_dock(pWorkbenchSidebar);
	pWorkbenchSidebar->close();
	pWorkbenchSidebar->connect(SNAME("closed"), callable_mp(this, &AIChatDock::CloseWorkbenchSidebar));
	pPalette->connect(SNAME("about_to_popup"), callable_mp(this, &AIChatDock::CaptureWorkbenchSource));
	pTitleButton->connect(SNAME("button_down"), callable_mp(this, &AIChatDock::CaptureWorkbenchSource));
	pTitleButton->connect(SNAME("pressed"), callable_mp(this, &AIChatDock::OpenWorkbenchSidebar));
	const Ref<Shortcut> workbench_shortcut = ED_SHORTCUT(WORKBENCH_SHORTCUT, TTRC("Open AI Workbench"), KeyModifierMask::CMD_OR_CTRL | KeyModifierMask::SHIFT | Key::M);
	pPalette->add_command(TTR("Open AI Workbench"), WORKBENCH_SHORTCUT, callable_mp(this, &AIChatDock::OpenWorkbenchSidebar), workbench_shortcut);
	set_process_shortcut_input(true);

	// The selector travels with the same view when it is docked or expanded.
	Ref<Script> selector_script = LoadWorkbenchControlScript(daqian_module_selector);
	if (selector_script.is_valid())
	{
		VBoxContainer *selector = memnew(VBoxContainer);
		selector->set_name("WorkbenchBusinessModules");
		pBusinessModules = selector;
		selector->set_script(selector_script);
		selector->set_meta("change_reference_scope", callable_mp(this, &AIChatDock::ChangeWorkbenchReferenceScope));
		selector->set_meta("freeze_references", callable_mp(this, &AIChatDock::FreezeBusinessReferences));
		selector->set_meta("workbench_sidebar", pWorkbenchSidebar);
		Ref<Script> asset_script = LoadWorkbenchControlScript(daqian_asset_picker);
		if (asset_script.is_valid())
		{
			selector->set_meta("asset_picker_script", asset_script);
		}
		pConversationView->add_child(selector);
		pConversationView->move_child(selector, 0);
	}
}

void AIChatDock::shortcut_input(const Ref<InputEvent> &p_event)
{
	if (p_event->is_pressed() && !p_event->is_echo() && ED_IS_SHORTCUT(WORKBENCH_SHORTCUT, p_event))
	{
		CaptureWorkbenchSource();
		OpenWorkbenchSidebar();
		get_viewport()->set_input_as_handled();
	}
}

void AIChatDock::CaptureWorkbenchSource()
{
	if (nConversationIndex < 0 && idWorkbenchReturnScreen.is_null())
	{
		Control *pFocus = get_viewport()->gui_get_focus_owner();
		idSidebarSource = pFocus ? pFocus->get_instance_id() : ObjectID();
	}
}

void AIChatDock::PrepareWorkbenchConsultation()
{
	if (!task_native_grant.matches(_native_task_scope()))
	{
		consultation_only->set_pressed(true);
	}
}

void AIChatDock::OpenWorkbenchSidebar()
{
	if (idWorkbenchReturnScreen.is_null() && !WorkbenchReferenceLocked())
	{
		if (nConversationIndex < 0)
		{
			StageWorkbenchPageReference();
		}
		Control *pScreen = EditorNode::get_editor_main_screen()->get_current_tab_control();
		if (pScreen && (pScreen->get_name() == SNAME("2D") || pScreen->get_name() == SNAME("3D")))
		{
			StageWorkbenchSelection();
		}
		else
		{
			CaptureWorkbenchScriptSelection();
		}
	}
	if (idWorkbenchReturnScreen.is_valid())
	{
		EditorDock *pScreen = ObjectDB::get_instance<EditorDock>(idWorkbenchReturnScreen);
		idWorkbenchReturnScreen = ObjectID();
		pRestoreSidebar->hide();
		if (pScreen && !pScreen->is_queued_for_deletion() && pScreen->get_parent_container() == EditorNode::get_editor_main_screen() && pScreen->is_dock_open())
		{
			EditorDockManager::get_singleton()->force_focus_dock(pScreen);
		}
	}
	else if (nConversationIndex < 0)
	{
		// Entering from an editing surface starts in consultation. Returning from
		// the expanded view retains the mode selected for this conversation.
		PrepareWorkbenchConsultation();
	}
	if (nConversationIndex < 0)
	{
		nConversationIndex = pConversationView->get_index();
		pConversationView->reparent(pSidebarLayout, false);
	}
	EditorDockManager::get_singleton()->force_focus_dock(pWorkbenchSidebar);
	// Full-workspace and distraction-free screens hide normal dock slots.
	if (DockTabContainer *pSlot = pWorkbenchSidebar->get_parent_container())
	{
		pSlot->show();
	}
	if (input->is_visible_in_tree())
	{
		input->grab_focus();
	}
	else if (Control *composer = Object::cast_to<Control>(pConversationView->find_child("ModuleChatInput", true, false)))
	{
		composer->grab_focus();
	}
}

void AIChatDock::ExpandWorkbenchSidebar()
{
	if (nConversationIndex < 0)
	{
		return;
	}
	Control *pScreen = EditorNode::get_editor_main_screen()->get_current_tab_control();
	ERR_FAIL_NULL(pScreen);
	idWorkbenchReturnScreen = pScreen->get_instance_id();
	// Store the displayed offset before reflow. The conversation's scroll handler
	// retains it through layout clamps and tracks subsequent scrolling in the full view.
	_chat_scrolled();
	pWorkbenchSidebar->close();
	EditorDockManager::get_singleton()->force_focus_dock(this);
	workspace_pages->set_current_tab(chat_layout->get_parent() == timer_chat_host ? 1 : 0);
	pRestoreSidebar->show();
	if (input->is_visible_in_tree())
	{
		input->grab_focus();
	}
	else if (Control *composer = Object::cast_to<Control>(pConversationView->find_child("ModuleChatInput", true, false)))
	{
		composer->grab_focus();
	}
}

void AIChatDock::CloseWorkbenchSidebar()
{
	if (nConversationIndex < 0)
	{
		return;
	}
	pConversationView->reparent(chat_layout, false);
	chat_layout->move_child(pConversationView, nConversationIndex);
	nConversationIndex = -1;
	if (idWorkbenchReturnScreen.is_valid())
	{
		return;
	}
	// Closing a dock restores its previous tab after emitting the closed signal.
	callable_mp(this, &AIChatDock::RestoreWorkbenchFocus).call_deferred(idSidebarSource);
	idSidebarSource = ObjectID();
}

void AIChatDock::DismissWorkbenchSidebar()
{
	if (nConversationIndex >= 0)
	{
		// Explicit navigation to another conversation host takes precedence over restoring focus.
		idSidebarSource = ObjectID();
		pWorkbenchSidebar->close();
	}
}

void AIChatDock::RestoreWorkbenchFocus(ObjectID idSource)
{
	Control *pSource = ObjectDB::get_instance<Control>(idSource);
	if (nConversationIndex < 0 && pSource && !pSource->is_queued_for_deletion() && pSource->is_visible_in_tree() && pSource->get_focus_mode_with_override() != FOCUS_NONE)
	{
		pSource->grab_focus();
	}
}
