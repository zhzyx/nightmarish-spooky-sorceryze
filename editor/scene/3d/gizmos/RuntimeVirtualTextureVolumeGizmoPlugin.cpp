/**************************************************************************/
/*  RuntimeVirtualTextureVolumeGizmoPlugin.cpp                           */
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

#include "RuntimeVirtualTextureVolumeGizmoPlugin.h"

#pragma region Engine ZXB
// [ZXB] RuntimeVirtualTextureVolume gizmo, a box with resize handles.
#pragma endregion

#include "editor/editor_node.h"
#include "editor/scene/3d/gizmos/gizmo_3d_helper.h"
#include "editor/settings/editor_settings.h"
#include "scene/3d/RuntimeVirtualTextureVolume.h"

RuntimeVirtualTextureVolumeGizmoPlugin::RuntimeVirtualTextureVolumeGizmoPlugin()
{
	refHelper.instantiate();
	// Shares the fog volume color, both are authoring volumes.
	const Color colGizmoColor = EDITOR_GET("editors/3d_gizmos/gizmo_colors/fog_volume");
	create_material("shape_material", colGizmoColor);
	create_handle_material("handles");
}

bool RuntimeVirtualTextureVolumeGizmoPlugin::has_gizmo(Node3D *pSpatial)
{
	return Object::cast_to<RuntimeVirtualTextureVolume>(pSpatial) != nullptr;
}

String RuntimeVirtualTextureVolumeGizmoPlugin::get_gizmo_name() const
{
	return "RuntimeVirtualTextureVolume";
}

int RuntimeVirtualTextureVolumeGizmoPlugin::get_priority() const
{
	return -1;
}

String RuntimeVirtualTextureVolumeGizmoPlugin::get_handle_name(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary) const
{
	return refHelper->box_get_handle_name(nId);
}

Variant RuntimeVirtualTextureVolumeGizmoPlugin::get_handle_value(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary) const
{
	return Vector3(pGizmo->get_node_3d()->call("get_size"));
}

void RuntimeVirtualTextureVolumeGizmoPlugin::begin_handle_action(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary)
{
	refHelper->initialize_handle_action(get_handle_value(pGizmo, nId, bSecondary), pGizmo->get_node_3d()->get_global_transform());
}

void RuntimeVirtualTextureVolumeGizmoPlugin::set_handle(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary, Camera3D *pCamera, const Point2 &vPoint)
{
	RuntimeVirtualTextureVolume *pVolume = Object::cast_to<RuntimeVirtualTextureVolume>(pGizmo->get_node_3d());
	Vector3 vSize = pVolume->GetSize();

	Vector3 arrSg[2];
	refHelper->get_segment(pCamera, vPoint, arrSg);

	Vector3 vPosition;
	refHelper->box_set_handle(arrSg, nId, vSize, vPosition);
	pVolume->SetSize(vSize);
	pVolume->set_global_position(vPosition);
}

void RuntimeVirtualTextureVolumeGizmoPlugin::commit_handle(const EditorNode3DGizmo *pGizmo, int nId, bool bSecondary, const Variant &varRestore, bool bCancel)
{
	refHelper->box_commit_handle(TTR("Change RuntimeVirtualTextureVolume Size"), bCancel, pGizmo->get_node_3d());
}

void RuntimeVirtualTextureVolumeGizmoPlugin::redraw(EditorNode3DGizmo *pGizmo)
{
	RuntimeVirtualTextureVolume *pVolume = Object::cast_to<RuntimeVirtualTextureVolume>(pGizmo->get_node_3d());

	pGizmo->clear();

	AABB aabbAabb;
	aabbAabb.size = pVolume->GetSize();
	aabbAabb.position = aabbAabb.size / -2;

	Vector<Vector3> arrLines;
	for (int nI = 0; nI < 12; nI++)
	{
		Vector3 vA, stB;
		aabbAabb.get_edge(nI, vA, stB);
		arrLines.push_back(vA);
		arrLines.push_back(stB);
	}

	// Line from the top face center to the origin: the texture is rendered looking down.
	arrLines.push_back(Vector3(0, aabbAabb.size.y * 0.5f, 0));
	arrLines.push_back(Vector3());

	pGizmo->add_lines(arrLines, get_material("shape_material", pGizmo));
	pGizmo->add_collision_segments(arrLines);
	pGizmo->add_handles(refHelper->box_get_handles(pVolume->GetSize()), get_material("handles"));
}
