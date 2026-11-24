/**************************************************************************/
/*  AuxiliaryDockLayout.cpp                                               */
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

#include "editor/docks/editor_dock.h"
#include "editor/docks/editor_dock_manager.h"
#include "editor/editor_main_screen.h"
#include "editor/editor_node.h"
#include "editor/gui/window_wrapper.h"
#include "editor/themes/editor_scale.h"
#include "scene/gui/control.h"
#include "scene/main/viewport.h"
#include "scene/main/window.h"
#include "servers/display/display_server.h"

void EditorDock::SetAuxiliaryExpanded(bool bExpanded)
{
	EditorDockManager::get_singleton()->SetDockAuxiliaryExpanded(this, bExpanded);
}

void EditorDock::ToggleAuxiliaryExpanded()
{
	SetAuxiliaryExpanded(!IsAuxiliaryExpanded());
}

bool EditorDock::IsAuxiliaryExpanded() const
{
	return dock_window != nullptr || bAuxiliaryInlineExpanded;
}

Vector<ObjectID> EditorDockManager::GetAuxiliaryColumns() const
{
	Vector<ObjectID> arrColumns;
	if (main_hsplit == nullptr)
	{
		return arrColumns;
	}
	for (int nIndex = 0; nIndex < main_hsplit->get_child_count(false); nIndex++)
	{
		Control *pColumn = Object::cast_to<Control>(main_hsplit->get_child(nIndex, false));
		if (pColumn != nullptr && pColumn->is_visible() && !pColumn->is_set_as_top_level())
		{
			arrColumns.push_back(pColumn->get_instance_id());
		}
	}
	return arrColumns;
}

void EditorDockManager::RestoreAuxiliarySplit()
{
	if (idInlineExpandedDock.is_null())
	{
		return;
	}
	EditorDock *pDock = ObjectDB::get_instance<EditorDock>(idInlineExpandedDock);
	idInlineExpandedDock = ObjectID();
	// A user may have rearranged columns while expanded. Never apply old indices
	// to a different layout, or dereference a removed dock or column.
	if (main_hsplit != nullptr && GetAuxiliaryColumns() == arrAuxiliaryColumns)
	{
		main_hsplit->set_split_offsets(arrAuxiliarySplitOffsets);
	}
	arrAuxiliarySplitOffsets.clear();
	arrAuxiliaryColumns.clear();
	if (pDock != nullptr)
	{
		pDock->bAuxiliaryInlineExpanded = false;
		pDock->emit_signal(SNAME("auxiliary_expansion_changed"), false);
	}
}

void EditorDockManager::ExpandAuxiliarySplit(EditorDock *pDock)
{
	RestoreAuxiliarySplit();
	if (main_hsplit == nullptr || !main_hsplit->is_ancestor_of(pDock))
	{
		return;
	}
	const Vector<ObjectID> arrColumns = GetAuxiliaryColumns();
	int nTarget = -1;
	int nCenter = -1;
	for (int nIndex = 0; nIndex < arrColumns.size(); nIndex++)
	{
		Control *pColumn = ObjectDB::get_instance<Control>(arrColumns[nIndex]);
		if (pColumn->is_ancestor_of(pDock))
		{
			nTarget = nIndex;
		}
		if (pColumn->is_ancestor_of(EditorNode::get_editor_main_screen()))
		{
			nCenter = nIndex;
		}
	}
	if (nTarget < 0 || nCenter < 0 || nTarget == nCenter)
	{
		return;
	}
	Control *pTarget = ObjectDB::get_instance<Control>(arrColumns[nTarget]);
	Control *pCenter = ObjectDB::get_instance<Control>(arrColumns[nCenter]);
	PackedInt32Array arrOffsets = main_hsplit->get_split_offsets();
	if (arrOffsets.size() != arrColumns.size() - 1)
	{
		return;
	}
	const real_t fDesired = MIN(main_hsplit->get_size().x * 0.48, MAX(pTarget->get_size().x * 1.6, 560 * EDSCALE));
	const real_t fAvailable = MAX(real_t(0), pCenter->get_size().x - MAX(pCenter->get_combined_minimum_size().x, 320 * EDSCALE));
	const int nDelta = int(MIN(MAX(real_t(0), fDesired - pTarget->get_size().x), fAvailable));
	arrAuxiliaryColumns = arrColumns;
	arrAuxiliarySplitOffsets = arrOffsets;
	idInlineExpandedDock = pDock->get_instance_id();
	// Move all boundaries between the main area and the chosen side column.
	// Other side columns keep their widths, including custom left/right layouts.
	for (int nIndex = MIN(nTarget, nCenter); nIndex < MAX(nTarget, nCenter); nIndex++)
	{
		arrOffsets.set(nIndex, arrOffsets[nIndex] + (nTarget < nCenter ? nDelta : -nDelta));
	}
	main_hsplit->set_split_offsets(arrOffsets);
	pDock->bAuxiliaryInlineExpanded = true;
	pDock->emit_signal(SNAME("auxiliary_expansion_changed"), true);
}

void EditorDockManager::RestoreDockFromWindow(EditorDock *pDock)
{
	ERR_FAIL_NULL(pDock);
	ERR_FAIL_COND(!all_docks.has(pDock));
	if (pDock->dock_window == nullptr)
	{
		return;
	}
	Control *pFocus = pDock->get_viewport()->gui_get_focus_owner();
	const ObjectID idFocus = pFocus != nullptr && pDock->is_ancestor_of(pFocus) ? pFocus->get_instance_id() : ObjectID();
	_close_window(pDock->dock_window);
	if (pDock->dock_slot_index != EditorDock::DOCK_SLOT_NONE)
	{
		pDock->is_open = false;
		force_focus_dock(pDock);
		pFocus = ObjectDB::get_instance<Control>(idFocus);
		if (pFocus != nullptr && !pFocus->is_queued_for_deletion() && pFocus->is_visible_in_tree())
		{
			pFocus->grab_focus();
		}
	}
	else
	{
		close_dock(pDock);
	}
}

void EditorDockManager::SetDockAuxiliaryExpanded(EditorDock *pDock, bool bExpanded)
{
	ERR_FAIL_NULL(pDock);
	ERR_FAIL_COND(!all_docks.has(pDock));
	if (!bExpanded)
	{
		if (pDock->get_instance_id() == idInlineExpandedDock)
		{
			RestoreAuxiliarySplit();
		}
		RestoreDockFromWindow(pDock);
		return;
	}
	if (pDock->IsAuxiliaryExpanded() || !pDock->enabled || pDock->is_queued_for_deletion())
	{
		return;
	}
	// Auxiliary expansion is for side docks. A main or bottom dock keeps its
	// own layout contract instead of being silently moved to a different slot.
	if (pDock->dock_slot_index < EditorDock::DOCK_SLOT_LEFT_UL || pDock->dock_slot_index >= EditorDock::DOCK_SLOT_BOTTOM)
	{
		return;
	}
	force_focus_dock(pDock);
	const bool bNativeWindows = DisplayServer::get_singleton()->get_screen_count() > 0 &&
			DisplayServer::get_singleton()->has_feature(DisplayServerEnums::FEATURE_SUBWINDOWS);
	if (bNativeWindows && EditorNode::get_singleton()->is_multi_window_enabled() && pDock->available_layouts.has_flag(EditorDock::DOCK_LAYOUT_FLOATING))
	{
		make_dock_floating(pDock);
		Window *pWindow = pDock->get_window();
		Size2i vAvailable = DisplayServer::get_singleton()->screen_get_usable_rect(pWindow->get_current_screen()).size;
		if (vAvailable.x <= 0 || vAvailable.y <= 0)
		{
			vAvailable = EditorNode::get_singleton()->get_window()->get_size();
		}
		const Size2i vSize = pWindow->get_size();
		pWindow->set_size(Size2i(MIN(MAX(vSize.x, int(720 * EDSCALE)), int(vAvailable.x * 0.9)),
								 MIN(MAX(vSize.y, int(600 * EDSCALE)), int(vAvailable.y * 0.9))));
		pWindow->move_to_center();
	}
	else
	{
		ExpandAuxiliarySplit(pDock);
	}
}
