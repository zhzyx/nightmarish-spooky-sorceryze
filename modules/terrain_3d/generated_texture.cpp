// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "servers/rendering/rendering_server.h"

#include "generated_texture.h"
#include "logger.h"
#include "terrain_3d.h"

///////////////////////////
// Public Functions
///////////////////////////

void GeneratedTexture::clear() {
	if (_rid.is_valid()) {
		LOG(EXTREME, "GeneratedTexture freeing ", _rid);
		TERRAIN_RS->free_rid(_rid);
	}
	if (_image.is_valid()) {
		LOG(EXTREME, "GeneratedTexture unref image", _image);
		_image.unref();
	}
	_rid = RID();
	_dirty = true;
	_size = 0;
}

RID GeneratedTexture::create(const TypedArray<Image> &p_layers) {
	if (!p_layers.is_empty()) {
		if (Terrain3D::debug_level >= DEBUG) {
			LOG(EXTREME, "RenderingServer creating Texture2DArray, layers size: ", p_layers.size());
			for (int i = 0; i < p_layers.size(); i++) {
				Ref<Image> img = p_layers[i];
				LOG(EXTREME, i, ": ", img, ", empty: ", img->is_empty(), ", size: ", img->get_size(), ", format: ", img->get_format());
			}
		}
		Vector<Ref<Image>> arrImages;
		arrImages.resize(p_layers.size());
		for (int nI = 0; nI < p_layers.size(); ++nI)
		{
			arrImages.set(nI, p_layers[nI]);
		}
		_rid = TERRAIN_RS->texture_2d_layered_create(arrImages, RSE::TEXTURE_LAYERED_2D_ARRAY);
		_dirty = false;
		_size = p_layers.size();
	} else {
		clear();
	}
	return _rid;
}

void GeneratedTexture::update(const Ref<Image> &p_image, const int p_layer) {
	LOG(EXTREME, "RenderingServer updating Texture2DArray at index: ", p_layer);
	TERRAIN_RS->texture_2d_update(_rid, p_image, p_layer);
}

RID GeneratedTexture::create(const Ref<Image> &p_image) {
	LOG(EXTREME, "RenderingServer creating Texture2D");
	_image = p_image;
	_rid = TERRAIN_RS->texture_2d_create(_image);
	_dirty = false;
	return _rid;
}
