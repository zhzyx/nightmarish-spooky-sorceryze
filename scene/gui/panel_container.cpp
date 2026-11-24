/**************************************************************************/
/*  panel_container.cpp                                                   */
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

#include "panel_container.h"

#include "scene/theme/theme_db.h"
#include "servers/rendering/rendering_server.h"

Size2 PanelContainer::get_minimum_size() const {
	Size2 ms = Container::_get_minimum_size();

	if (theme_cache.panel_style.is_valid()) {
		ms += theme_cache.panel_style->get_minimum_size();
	}
	return ms;
}

Size2 PanelContainer::get_desired_size() const {
	Size2 ds;

	for (int i = 0; i < get_child_count(); i++) {
		Control *c = as_sortable_control(get_child(i), SortableVisibilityMode::VISIBLE);
		if (!c) {
			continue;
		}

		Size2 minsize = c->get_bound_desired_size();
		ds = ds.max(minsize);
	}
	if (theme_cache.panel_style.is_valid()) {
		ds += theme_cache.panel_style->get_minimum_size();
	}
	return ds;
}

Size2 PanelContainer::get_inner_combined_maximum_size() const {
	Size2 ms = Container::get_inner_combined_maximum_size();

	if (theme_cache.panel_style.is_valid()) {
		ms -= theme_cache.panel_style->get_minimum_size();
	}

	return ms;
}

Vector<int> PanelContainer::get_allowed_size_flags_horizontal() const {
	Vector<int> flags;
	flags.append(SIZE_FILL);
	flags.append(SIZE_SHRINK_BEGIN);
	flags.append(SIZE_SHRINK_CENTER);
	flags.append(SIZE_SHRINK_END);
	flags.append(SIZE_MAXIMIZE);
	return flags;
}

Vector<int> PanelContainer::get_allowed_size_flags_vertical() const {
	Vector<int> flags;
	flags.append(SIZE_FILL);
	flags.append(SIZE_SHRINK_BEGIN);
	flags.append(SIZE_SHRINK_CENTER);
	flags.append(SIZE_SHRINK_END);
	flags.append(SIZE_MAXIMIZE);
	return flags;
}

void PanelContainer::_notification(int p_what) {
	switch (p_what) {
		case NOTIFICATION_THEME_CHANGED: {
			// Opt-in only. A user-provided material always takes precedence.
			if (theme_cache.background_blur > 0 && (get_material().is_null() || get_material() == background_material)) {
				if (background_material.is_null()) {
					Ref<Shader> shader;
					shader.instantiate();
					shader->set_code(R"(
shader_type canvas_item;
render_mode unshaded;
uniform sampler2D backdrop : hint_screen_texture, repeat_disable, filter_linear;
uniform float radius = 3.0;
void fragment() {
    vec2 offset = SCREEN_PIXEL_SIZE * radius;
    vec3 blurred = texture(backdrop, SCREEN_UV).rgb * 0.25;
    blurred += texture(backdrop, SCREEN_UV + vec2(offset.x, 0.0)).rgb * 0.125;
    blurred += texture(backdrop, SCREEN_UV - vec2(offset.x, 0.0)).rgb * 0.125;
    blurred += texture(backdrop, SCREEN_UV + vec2(0.0, offset.y)).rgb * 0.125;
    blurred += texture(backdrop, SCREEN_UV - vec2(0.0, offset.y)).rgb * 0.125;
    blurred += texture(backdrop, SCREEN_UV + offset).rgb * 0.0625;
    blurred += texture(backdrop, SCREEN_UV - offset).rgb * 0.0625;
    blurred += texture(backdrop, SCREEN_UV + vec2(offset.x, -offset.y)).rgb * 0.0625;
    blurred += texture(backdrop, SCREEN_UV + vec2(-offset.x, offset.y)).rgb * 0.0625;
    COLOR.rgb = mix(blurred, COLOR.rgb, 0.82);
}
)");
					background_material.instantiate();
					background_material->set_shader(shader);
				}
				background_material->set_shader_parameter("radius", CLAMP(theme_cache.background_blur, 1, 12));
				set_material(background_material);
			} else if (get_material().is_valid() && get_material() == background_material) {
				set_material(Ref<Material>());
				background_material.unref();
			}
		} break;
		case NOTIFICATION_DRAW: {
			RID ci = get_canvas_item();
			// Screen-texture auto copies are shared by the viewport. Refresh before
			// each glass panel so intervening and overlapping items are included.
			const bool copy_backdrop = background_material.is_valid() && get_material() == background_material;
			RS::get_singleton()->canvas_item_set_copy_to_backbuffer(ci, copy_backdrop, Rect2());
			theme_cache.panel_style->draw(ci, Rect2(Point2(), get_size()));
		} break;

		case NOTIFICATION_SORT_CHILDREN: {
			Size2 size = get_size();
			Point2 ofs;
			if (theme_cache.panel_style.is_valid()) {
				size -= theme_cache.panel_style->get_minimum_size();
				ofs += theme_cache.panel_style->get_offset();
			}

			for (int i = 0; i < get_child_count(); i++) {
				Control *c = as_sortable_control(get_child(i));
				if (!c) {
					continue;
				}

				fit_child_in_rect(c, Rect2(ofs, size));
			}
		} break;
	}
}

void PanelContainer::_bind_methods() {
	BIND_THEME_ITEM_CUSTOM(Theme::DATA_TYPE_STYLEBOX, PanelContainer, panel_style, "panel");
	BIND_THEME_ITEM(Theme::DATA_TYPE_CONSTANT, PanelContainer, background_blur);
}

PanelContainer::PanelContainer() {
	// Has visible stylebox, so stop by default.
	set_mouse_filter(MOUSE_FILTER_STOP);
}
