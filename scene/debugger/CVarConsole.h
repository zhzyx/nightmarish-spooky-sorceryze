/**************************************************************************/
/*  CVarConsole.h                                                        */
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

#pragma once

#include "core/input/input_event.h"
#include "core/string/ustring.h"
#include "core/templates/vector.h"
#include "scene/main/node.h"

class ColorRect;
class LineEdit;
class RichTextLabel;

// Drop-down console. In a game it toggles with F1 or the ` / ~ key. The editor uses
// that same key so F1 stays "Search Help". A text field that has focus still receives the character.
class CVarConsole : public Node
{
	GDCLASS(CVarConsole, Node);

public:
	typedef String (*SubmittedHook)(const String &in_strLine, const String &strLocalResult, void *pUserdata);

private:
	ColorRect *pBackground = nullptr;
	RichTextLabel *pLogLabel = nullptr;
	LineEdit *pLineEdit = nullptr;
	Vector<String> arrHistory;
	int nHistoryPos = -1;
	String strDraft;
	bool bOpen = false;
	bool bLogHasLine = false;
	bool bEditorMode = false;
	SubmittedHook pSubmittedHook = nullptr;
	void *pSubmittedUserdata = nullptr;

	void BuildUi();
	void Append(const String &strText);
	void SetOpen(bool in_bOpen);
	void OnTextSubmitted(const String &strText);
	void LineGuiInput(const Ref<InputEvent> &refEvent);
	void SuppressIme();

protected:
	static void _bind_methods();
	void _notification(int nWhat);

public:
	static bool IsTildeToggle(const Ref<InputEventKey> &in_refKey);

	void input(const Ref<InputEvent> &refEvent) override;
	void SubmitLine(const String &in_strLine);
	void Toggle();
	void SetEditorMode(bool bEditor);
	void SetSubmittedHook(SubmittedHook pHook, void *pUserdata);
	bool IsOpen() const
	{
		return bOpen;
	}
};
