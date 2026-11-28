/**************************************************************************/
/*  RuntimeVirtualTextureVolume.cpp                                      */
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

#include "RuntimeVirtualTextureVolume.h"

#pragma region Engine ZXB
// [ZXB] RuntimeVirtualTextureVolume implementation.
#pragma endregion

#include "core/object/class_db.h"
#include "scene/main/viewport.h"
#include "scene/resources/3d/world_3d.h"

RuntimeVirtualTextureVolume::RuntimeVirtualTextureVolume()
{
	set_notify_transform(true);
}

void RuntimeVirtualTextureVolume::UpdateWorld()
{
	if (refVirtualTexture.is_null())
	{
		return;
	}
	RID ridScenario;
	if (is_inside_tree() && is_visible_in_tree() && get_world_3d().is_valid())
	{
		ridScenario = get_world_3d()->get_scenario();
	}
	// The node scale is ignored, the covered box is defined by `size`.
	const Transform3D xformNodeTransform = is_inside_tree() ? get_global_transform() : get_transform();
	const Basis basisBasis = xformNodeTransform.basis.orthonormalized() * Basis::from_scale(vSize);
	refVirtualTexture->SetWorld(ridScenario, Transform3D(basisBasis, xformNodeTransform.origin));
}

void RuntimeVirtualTextureVolume::_notification(int nWhat)
{
	switch (nWhat)
	{
	case NOTIFICATION_ENTER_WORLD:
	case NOTIFICATION_EXIT_WORLD:
	case NOTIFICATION_TRANSFORM_CHANGED:
	case NOTIFICATION_VISIBILITY_CHANGED: {
		UpdateWorld();
	}
	break;
	}
}

void RuntimeVirtualTextureVolume::SetVirtualTexture(const Ref<RuntimeVirtualTexture> &refTexture)
{
	if (refVirtualTexture == refTexture)
	{
		return;
	}
	if (refVirtualTexture.is_valid())
	{
		refVirtualTexture->SetWorld(RID(), refVirtualTexture->GetWorldTransform());
	}
	refVirtualTexture = refTexture;
	UpdateWorld();
	update_configuration_warnings();
}

void RuntimeVirtualTextureVolume::SetSize(const Vector3 &in_vSize)
{
	vSize = in_vSize.max(Vector3(0.01, 0.01, 0.01));
	UpdateWorld();
	update_gizmos();
}

PackedStringArray RuntimeVirtualTextureVolume::get_configuration_warnings() const
{
	PackedStringArray arrWarnings = Node3D::get_configuration_warnings();
	if (refVirtualTexture.is_null())
	{
		arrWarnings.push_back(RTR("A RuntimeVirtualTexture resource is required."));
	}
	return arrWarnings;
}

void RuntimeVirtualTextureVolume::_bind_methods()
{
	ClassDB::bind_method(D_METHOD("set_virtual_texture", "texture"), &RuntimeVirtualTextureVolume::SetVirtualTexture);
	ClassDB::bind_method(D_METHOD("get_virtual_texture"), &RuntimeVirtualTextureVolume::GetVirtualTexture);

	ClassDB::bind_method(D_METHOD("set_size", "size"), &RuntimeVirtualTextureVolume::SetSize);
	ClassDB::bind_method(D_METHOD("get_size"), &RuntimeVirtualTextureVolume::GetSize);

	ADD_PROPERTY(PropertyInfo(Variant::VECTOR3, "size", PROPERTY_HINT_RANGE, "0.01,4096,0.01,or_greater,suffix:m"), "set_size", "get_size");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "virtual_texture", PROPERTY_HINT_RESOURCE_TYPE, "RuntimeVirtualTexture"), "set_virtual_texture", "get_virtual_texture");
}
