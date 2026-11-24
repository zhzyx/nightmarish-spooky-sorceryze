/**************************************************************************/
/*  AIWorkbenchWindow.cpp                                                 */
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

#include "AIWorkbenchWindow.h"

#include "core/input/input_event.h"
#include "core/object/callable_mp.h"
#include "editor/docks/ai_chat_editor_registry.h"
#include "editor/editor_node.h"
#include "editor/settings/editor_settings.h"
#include "editor/themes/editor_scale.h"
#include "scene/gui/box_container.h"
#include "scene/gui/button.h"
#include "scene/gui/dialogs.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/popup.h"
#include "scene/gui/text_edit.h"
#include "scene/main/scene_tree.h"

namespace
{
class WindowShortcut final : public Node
{
public:
	Callable fnOpen;

	void input(const Ref<InputEvent> &refEvent) override
	{
		if (!refEvent->is_pressed() || refEvent->is_echo() || (refEvent->get_type() != InputEventType::KEY && refEvent->get_type() != InputEventType::SHORTCUT))
		{
			return;
		}
		Window *pWindow = get_window();
		// An exclusive dialog cannot pass its command palette shortcut to the main editor.
		if (ED_IS_SHORTCUT("editor/ask_ai_in_window", refEvent) || (pWindow->is_exclusive() && ED_IS_SHORTCUT("editor/command_palette", refEvent)))
		{
			pWindow->set_input_as_handled();
			fnOpen.call(pWindow);
		}
	}
};

class WorkbenchWindowRouter final : public Node
{
	Control *pConversation;
	TextEdit *pInput;
	Callable fnPrepareConsultation;
	LineEdit *pSessionName;
	Window *pPalette;
	AcceptDialog *pWorkbench = nullptr;
	ObjectID idPreviousParent;
	int32_t nPreviousIndex = 0;
	ObjectID idSourceFocus;
	bool bDeselectOnBlur = true;
	bool bSelectAllOnFocus = false;
	String strReference;

	void AttachWindow(ObjectID idWindow)
	{
		Window *pWindow = ObjectDB::get_instance<Window>(idWindow);
		if (!pWindow || !pWindow->is_inside_tree() || pWindow->is_queued_for_deletion() || pWindow == pWorkbench || pWindow == pPalette ||
			Object::cast_to<Popup>(pWindow) || pWindow->is_part_of_edited_scene() ||
			!EditorNode::get_singleton()->is_ancestor_of(pWindow) || pWindow->has_node(NodePath("AIWorkbenchWindowShortcut")))
		{
			return;
		}
		WindowShortcut *pShortcut = memnew(WindowShortcut);
		pShortcut->set_name("AIWorkbenchWindowShortcut");
		pShortcut->fnOpen = callable_mp(this, &WorkbenchWindowRouter::OpenWindow);
		pWindow->add_child(pShortcut, false, INTERNAL_MODE_BACK);
		pShortcut->set_process_input(true);
	}

	void WindowAdded(Node *pNode)
	{
		if (Object::cast_to<Window>(pNode))
		{
			callable_mp(this, &WorkbenchWindowRouter::AttachWindow).call_deferred(pNode->get_instance_id());
		}
	}

	void InsertReference()
	{
		if (!strReference.is_empty())
		{
			pInput->set_caret_line(pInput->get_line_count() - 1);
			pInput->set_caret_column(pInput->get_line(pInput->get_caret_line()).length());
			pInput->deselect();
			pInput->insert_text_at_caret((pInput->get_text().is_empty() ? "" : "\n") + strReference, 0);
			pInput->grab_focus();
		}
	}

	void RestoreFocus()
	{
		Control *pSource = ObjectDB::get_instance<Control>(idSourceFocus);
		idSourceFocus = ObjectID();
		if (!pSource)
		{
			return;
		}
		if (pSource->is_inside_tree() && pSource->is_visible_in_tree() && pSource->get_window()->is_visible() &&
			!pSource->is_queued_for_deletion() && !pSource->get_window()->is_queued_for_deletion())
		{
			pSource->grab_focus();
		}
		if (LineEdit *pLine = Object::cast_to<LineEdit>(pSource))
		{
			pLine->set_deselect_on_focus_loss_enabled(bDeselectOnBlur);
			pLine->set_select_all_on_focus(bSelectAllOnFocus);
		}
		else if (TextEdit *pText = Object::cast_to<TextEdit>(pSource))
		{
			pText->set_deselect_on_focus_loss_enabled(bDeselectOnBlur);
		}
	}

	void CloseWindow()
	{
		if (!pWorkbench)
		{
			return;
		}
		AcceptDialog *pDialog = pWorkbench;
		pWorkbench = nullptr;
		pDialog->disconnect(SNAME("visibility_changed"), callable_mp(this, &WorkbenchWindowRouter::DialogVisibilityChanged));
		if (Node *pLayout = pConversation->get_parent())
		{
			Callable fnClose = callable_mp(this, &WorkbenchWindowRouter::CloseWindow);
			if (pLayout->is_connected(SNAME("tree_exiting"), fnClose))
			{
				pLayout->disconnect(SNAME("tree_exiting"), fnClose);
			}
		}
		Window *pSource = Object::cast_to<Window>(pDialog->get_parent());
		if (pSource)
		{
			pSource->disconnect(SNAME("visibility_changed"), callable_mp(this, &WorkbenchWindowRouter::SourceVisibilityChanged));
		}
		Node *pParent = ObjectDB::get_instance<Node>(idPreviousParent);
		if (pParent && !pParent->is_queued_for_deletion() && pConversation->get_parent() != pParent)
		{
			pConversation->reparent(pParent, false);
			pParent->move_child(pConversation, MIN(nPreviousIndex, pParent->get_child_count() - 1));
		}
		pDialog->hide();
		pDialog->queue_free();
		strReference = String();
		RestoreFocus();
	}

	void SourceVisibilityChanged()
	{
		if (pWorkbench && !Object::cast_to<Window>(pWorkbench->get_parent())->is_visible())
		{
			CloseWindow();
		}
	}

	void OpenWindow(Window *pSourceWindow)
	{
		if (pWorkbench || !is_inside_tree() || !pSourceWindow->is_visible() || pSourceWindow->get_exclusive_child() || pConversation->is_ancestor_of(pSourceWindow))
		{
			return;
		}
		Control *pSource = pSourceWindow->gui_get_focus_owner();
		idSourceFocus = pSource ? pSource->get_instance_id() : ObjectID();
		// The registry protects private fields, including credentials rendered by Editor Settings.
		// The session-name field is a known public field inside the otherwise private chat UI.
		const bool bCanQuote = pSource && (pSource == pSessionName || !AIChatEditorRegistry::is_protected(pSource));
		String strContent;
		if (LineEdit *pLine = Object::cast_to<LineEdit>(pSource))
		{
			bDeselectOnBlur = pLine->is_deselect_on_focus_loss_enabled();
			bSelectAllOnFocus = pLine->is_select_all_on_focus();
			pLine->set_deselect_on_focus_loss_enabled(false);
			pLine->set_select_all_on_focus(false);
			if (bCanQuote && !pLine->is_secret())
			{
				strContent = pLine->has_selection() ? pLine->get_selected_text() : pLine->get_text();
			}
		}
		else if (TextEdit *pText = Object::cast_to<TextEdit>(pSource))
		{
			bDeselectOnBlur = pText->is_deselect_on_focus_loss_enabled();
			pText->set_deselect_on_focus_loss_enabled(false);
			if (bCanQuote)
			{
				strContent = pText->has_selection() ? pText->get_selected_text() : pText->get_text();
			}
		}
		if (strContent.is_empty() && !Object::cast_to<LineEdit>(pSource) && !Object::cast_to<TextEdit>(pSource) && !AIChatEditorRegistry::is_protected(pSourceWindow))
		{
			if (AcceptDialog *pPrompt = Object::cast_to<AcceptDialog>(pSourceWindow))
			{
				strContent = pPrompt->get_text();
			}
		}
		idPreviousParent = pConversation->get_parent()->get_instance_id();
		nPreviousIndex = pConversation->get_index();
		pWorkbench = memnew(AcceptDialog);
		pWorkbench->set_name("AIWorkbenchWindow");
		pWorkbench->set_title(TTR("AI Workbench"));
		pWorkbench->set_ok_button_text(TTR("Return to Window"));
		pWorkbench->set_meta("ai_control_exclude", true);
		VBoxContainer *pLayout = memnew(VBoxContainer);
		pWorkbench->add_child(pLayout);
		if (!strContent.is_empty())
		{
			strReference = vformat(TTR("Window reference (%s):"), pSourceWindow->get_title()) + "\n" + strContent;
			Button *pQuote = memnew(Button);
			pQuote->set_name("InsertWindowReference");
			pQuote->set_text(TTR("Quote current content"));
			pQuote->set_tooltip_text(strContent.left(240));
			pQuote->connect(SNAME("pressed"), callable_mp(this, &WorkbenchWindowRouter::InsertReference));
			pLayout->add_child(pQuote);
		}
		pSourceWindow->add_child(pWorkbench);
		pConversation->reparent(pLayout, false);
		fnPrepareConsultation.call();
		pWorkbench->connect(SNAME("visibility_changed"), callable_mp(this, &WorkbenchWindowRouter::DialogVisibilityChanged));
		pLayout->connect(SNAME("tree_exiting"), callable_mp(this, &WorkbenchWindowRouter::CloseWindow));
		pSourceWindow->connect(SNAME("visibility_changed"), callable_mp(this, &WorkbenchWindowRouter::SourceVisibilityChanged));
		pWorkbench->popup_centered_clamped(Size2i(660, 600) * EDSCALE);
		pInput->grab_focus();
	}

	void DialogVisibilityChanged()
	{
		if (pWorkbench && !pWorkbench->is_visible())
		{
			CloseWindow();
		}
	}

public:
	WorkbenchWindowRouter(Control *pView, TextEdit *pComposer, LineEdit *pRename, Window *pCommandPalette, const Callable &fnPrepare) :
			pConversation(pView), pInput(pComposer), fnPrepareConsultation(fnPrepare), pSessionName(pRename), pPalette(pCommandPalette)
	{
		connect(SNAME("ready"), callable_mp(this, &WorkbenchWindowRouter::Start));
	}

	void Start()
	{
		get_tree()->connect(SNAME("node_added"), callable_mp(this, &WorkbenchWindowRouter::WindowAdded));
		TypedArray<Node> arrWindows = EditorNode::get_singleton()->find_children("*", "Window", true, false);
		for (int32_t nIndex = 0; nIndex < arrWindows.size(); ++nIndex)
		{
			WindowAdded(Object::cast_to<Node>(arrWindows[nIndex]));
		}
	}
};
} // namespace

Node *CreateWorkbenchWindowRouter(Control *pView, TextEdit *pInput, LineEdit *pRename, Window *pPalette, const Callable &fnPrepareConsultation)
{
	ED_SHORTCUT("editor/ask_ai_in_window", TTRC("Ask AI in Current Window"), KeyModifierMask::CMD_OR_CTRL | KeyModifierMask::ALT | Key::I);
	return memnew(WorkbenchWindowRouter(pView, pInput, pRename, pPalette, fnPrepareConsultation));
}
