/**************************************************************************/
/*  CVarConsole.cpp                                                      */
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

#include "scene/debugger/CVarConsole.h"

#include "core/config/CVars.h"
#include "servers/display/display_server.h"
#include "core/input/input_event.h"
#include "core/object/callable_mp.h"
#include "scene/gui/color_rect.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/rich_text_label.h"
#include "scene/main/canvas_layer.h"
#include "scene/main/window.h"

void CVarConsole::_bind_methods()
{
}

void CVarConsole::_notification(int nWhat)
{
	switch (nWhat)
	{
	case NOTIFICATION_ENTER_TREE: {
		set_name("CVarConsole");
		set_process_mode(PROCESS_MODE_ALWAYS);
		set_process_input(true);
		BuildUi();
	}
	break;
	case NOTIFICATION_PROCESS: {
		if (bOpen)
		{
			SuppressIme();
		}
	}
	break;
	case NOTIFICATION_EXIT_TREE: {
		pBackground = nullptr;
		pLogLabel = nullptr;
		pLineEdit = nullptr;
	}
	break;
	default:
		break;
	}
}

void CVarConsole::BuildUi()
{
	if (pBackground)
	{
		return;
	}
	CanvasLayer *pLayer = memnew(CanvasLayer);
	pLayer->set_layer(128);
	add_child(pLayer);

	pBackground = memnew(ColorRect);
	pBackground->set_color(Color(0.02, 0.03, 0.04, 0.92));
	pBackground->set_anchors_and_offsets_preset(Control::PRESET_BOTTOM_WIDE);
	pBackground->set_offset(Side::SIDE_TOP, -280);
	pBackground->set_mouse_filter(Control::MOUSE_FILTER_STOP);
	pBackground->set_visible(false);
	pLayer->add_child(pBackground);

	pLogLabel = memnew(RichTextLabel);
	pLogLabel->set_anchors_and_offsets_preset(Control::PRESET_FULL_RECT);
	pLogLabel->Control::set_offset(Side::SIDE_LEFT, 8);
	pLogLabel->Control::set_offset(Side::SIDE_TOP, 8);
	pLogLabel->Control::set_offset(Side::SIDE_RIGHT, -8);
	pLogLabel->Control::set_offset(Side::SIDE_BOTTOM, -40);
	pLogLabel->set_scroll_follow(true);
	pLogLabel->set_selection_enabled(true);
	pLogLabel->add_theme_color_override("default_color", Color(0.92, 0.93, 0.95));
	pBackground->add_child(pLogLabel);

	pLineEdit = memnew(LineEdit);
	pLineEdit->set_anchors_and_offsets_preset(Control::PRESET_BOTTOM_WIDE);
	pLineEdit->set_offset(Side::SIDE_LEFT, 8);
	pLineEdit->set_offset(Side::SIDE_TOP, -36);
	pLineEdit->set_offset(Side::SIDE_RIGHT, -8);
	pLineEdit->set_offset(Side::SIDE_BOTTOM, -6);
	pLineEdit->set_placeholder("name value    |    help    |    dump    |    reset name");
	pLineEdit->add_theme_color_override("font_color", Color(1, 1, 1));
	pLineEdit->connect("text_submitted", callable_mp(this, &CVarConsole::OnTextSubmitted));
	pLineEdit->connect("gui_input", callable_mp(this, &CVarConsole::LineGuiInput));
	pBackground->add_child(pLineEdit);

	if (bEditorMode)
	{
		Append("CVars (editor). Press the ` / ~ key when not typing, or use Editor > Toggle CVar Console. Esc closes. A running game receives the same command.");
	}
	else
	{
		Append("CVars. F1 or the ` / ~ key toggles this console. Try: help");
	}
}

void CVarConsole::Append(const String &strText)
{
	if (!pLogLabel || strText.is_empty())
	{
		return;
	}
	if (bLogHasLine)
	{
		pLogLabel->add_text("\n");
	}
	pLogLabel->add_text(strText);
	bLogHasLine = true;
}

void CVarConsole::SetOpen(bool in_bOpen)
{
	bOpen = in_bOpen;
	set_process(in_bOpen);
	if (pBackground)
	{
		pBackground->set_visible(in_bOpen);
	}
	if (in_bOpen)
	{
		SuppressIme();
		callable_mp(this, &CVarConsole::SuppressIme).call_deferred();
	}
	if (!pLineEdit)
	{
		return;
	}
	if (in_bOpen)
	{
		pLineEdit->grab_focus();
	}
	else
	{
		pLineEdit->release_focus();
	}
}

void CVarConsole::SuppressIme()
{
	// A focused LineEdit turns the IME on. The next press of ` is then delivered as
	// composed text instead of the toggle key, so it gets typed and the window stays open.
	if (!pLineEdit || !pLineEdit->is_inside_tree() || !DisplayServer::get_singleton())
	{
		return;
	}
	if (!DisplayServer::get_singleton()->has_feature(DisplayServerEnums::FEATURE_IME))
	{
		return;
	}
	Window *pWindow = pLineEdit->get_window();
	if (!pWindow)
	{
		return;
	}
	DisplayServer::get_singleton()->window_set_ime_active(false, pWindow->get_window_id());
}

void CVarConsole::LineGuiInput(const Ref<InputEvent> &refEvent)
{
	// The line edit is focused while the console is open, so this key arrives here
	// before LineEdit inserts it as text. Close instead of typing the toggle character.
	const Ref<InputEventKey> refKey = refEvent;
	if (!bOpen || !IsTildeToggle(refKey))
	{
		return;
	}
	if (pLineEdit)
	{
		pLineEdit->accept_event();
	}
	SetOpen(false);
}

void CVarConsole::OnTextSubmitted(const String &strText)
{
	SubmitLine(strText);
	if (pLineEdit)
	{
		pLineEdit->set_text("");
	}
	nHistoryPos = -1;
	strDraft = String();
}

void CVarConsole::SubmitLine(const String &in_strLine)
{
	const String strLine = in_strLine.strip_edges();
	if (strLine.is_empty() || !CVars::GetSingleton())
	{
		return;
	}
	arrHistory.push_back(strLine);
	nHistoryPos = -1;
	Append("> " + strLine);
	String strResult = CVars::GetSingleton()->Execute(strLine);
	if (pSubmittedHook)
	{
		const String strExtra = pSubmittedHook(strLine, strResult, pSubmittedUserdata);
		if (!strExtra.is_empty())
		{
			if (!strResult.is_empty())
			{
				strResult += "\n";
			}
			strResult += strExtra;
		}
	}
	if (!strResult.is_empty())
	{
		Append(strResult);
	}
}

void CVarConsole::Toggle()
{
	SetOpen(!bOpen);
}

void CVarConsole::SetEditorMode(bool bEditor)
{
	bEditorMode = bEditor;
}

void CVarConsole::SetSubmittedHook(SubmittedHook pHook, void *pUserdata)
{
	pSubmittedHook = pHook;
	pSubmittedUserdata = pUserdata;
}

bool CVarConsole::IsTildeToggle(const Ref<InputEventKey> &in_refKey)
{
	if (in_refKey.is_null() || !in_refKey->is_pressed() || in_refKey->is_echo())
	{
		return false;
	}
	if (in_refKey->is_ctrl_pressed() || in_refKey->is_alt_pressed() || in_refKey->is_meta_pressed())
	{
		return false;
	}
	// The key left of 1. Unshifted it is `, shifted it is ~. Either press opens the console.
	if (in_refKey->get_keycode() == Key::QUOTELEFT || in_refKey->get_keycode() == Key::ASCIITILDE || in_refKey->get_key_label() == Key::ASCIITILDE)
	{
		return true;
	}
	const char32_t chTyped = in_refKey->get_unicode();
	return chTyped == '`' || chTyped == '~';
}

void CVarConsole::input(const Ref<InputEvent> &refEvent)
{
	const Ref<InputEventKey> refKey = refEvent;
	if (refKey.is_null() || !refKey->is_pressed())
	{
		return;
	}
	const Key stCode = refKey->get_keycode();
	const bool bConsoleKey = IsTildeToggle(refKey);
	// Game: the key toggles. Editor: the shortcut opens it, and a second press
	// closes it here so the focused line edit does not swallow the key as text.
	const bool bToggle = (!bEditorMode && (stCode == Key::F1 || bConsoleKey)) || (bEditorMode && bOpen && bConsoleKey);
	if (refKey->is_echo() && !bToggle && stCode != Key::UP && stCode != Key::DOWN)
	{
		return;
	}
	Viewport *pViewport = get_viewport();

	if (bToggle && !refKey->is_echo())
	{
		SetOpen(!bOpen);
		if (pViewport)
		{
			pViewport->set_input_as_handled();
		}
		return;
	}
	if (!bOpen || !pLineEdit)
	{
		return;
	}
	if (stCode == Key::ESCAPE && !refKey->is_echo())
	{
		SetOpen(false);
		if (pViewport)
		{
			pViewport->set_input_as_handled();
		}
		return;
	}
	if (stCode != Key::UP && stCode != Key::DOWN)
	{
		return;
	}
	if (arrHistory.is_empty())
	{
		if (pViewport)
		{
			pViewport->set_input_as_handled();
		}
		return;
	}
	if (stCode == Key::UP)
	{
		if (nHistoryPos == -1)
		{
			strDraft = pLineEdit->get_text();
			nHistoryPos = arrHistory.size() - 1;
		}
		else if (nHistoryPos > 0)
		{
			nHistoryPos--;
		}
	}
	else if (nHistoryPos >= 0)
	{
		nHistoryPos++;
		if (nHistoryPos >= arrHistory.size())
		{
			nHistoryPos = -1;
		}
	}
	if (nHistoryPos == -1)
	{
		pLineEdit->set_text(strDraft);
	}
	else
	{
		pLineEdit->set_text(arrHistory[nHistoryPos]);
	}
	pLineEdit->set_caret_column(pLineEdit->get_text().length());
	if (pViewport)
	{
		pViewport->set_input_as_handled();
	}
}
