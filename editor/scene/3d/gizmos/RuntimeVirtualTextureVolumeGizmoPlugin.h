/**************************************************************************/
/*  RuntimeVirtualTextureVolumeGizmoPlugin.h                             */
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

#pragma region Engine ZXB
// [ZXB] Editor gizmo showing the box covered by a RuntimeVirtualTextureVolume.
#pragma endregion

#include "editor/scene/3d/node_3d_editor_gizmos.h"

class Gizmo3DHelper;

class RuntimeVirtualTextureVolumeGizmoPlugin : public EditorNode3DGizmoPlugin
{
	GDCLASS(RuntimeVirtualTextureVolumeGizmoPlugin, EditorNode3DGizmoPlugin);

	Ref<Gizmo3DHelper> refHelper;

public:
	bool has_gizmo(Node3D *pSpatial) override;
	String get_gizmo_name() const override;
	int get_priority() const override;
	void redraw(EditorNode3DGizmo *pGizmo) override;

	String get_handle_name(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary) const override;
	Variant get_handle_value(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary) const override;
	void begin_handle_action(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary) override;
	void set_handle(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary, Camera3D *pCamera, const Point2 &vPoint) override;
	void commit_handle(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary, const Variant &varRestore, bool bCancel = false) override;

	RuntimeVirtualTextureVolumeGizmoPlugin();
};
