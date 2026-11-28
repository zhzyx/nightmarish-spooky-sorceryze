// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "core/config/engine.h"
#include "scene/resources/environment.h"
#include "scene/resources/image_texture.h"
#include "servers/rendering/rendering_server.h"
#include "core/io/resource_saver.h"

#include "logger.h"
#include "terrain_3d_assets.h"
#include "terrain_3d_util.h"

///////////////////////////
// Private Functions
///////////////////////////

void Terrain3DAssets::_swap_ids(const AssetType p_type, const int p_src_id, const int p_dst_id) {
	LOG(INFO, "Swapping asset ID: ", p_src_id, " and ID: ", p_dst_id);
	Array list;
	switch (p_type) {
		case TYPE_TEXTURE:
			list = _texture_list;
			break;
		case TYPE_MESH:
			list = _mesh_list;
			break;
		default:
			return;
	}
	if (p_src_id < 0 || p_src_id >= list.size()) {
		LOG(ERROR, "Source ID out of range: ", p_src_id);
		return;
	}
	Ref<Terrain3DAssetResource> res_src = list[p_src_id];
	if (res_src.is_null()) {
		LOG(ERROR, "Source Asset is null at ID: ", p_src_id);
		return;
	}
	// User can type in any value, -1 means swap with first, >size means swap with last
	int dst_id = CLAMP(p_dst_id, 0, list.size() - 1);
	if (dst_id == p_src_id) {
		// They're likely the same due to the clamp, when new ID is <0 or >= array_size)
		res_src->_id = p_src_id;
		return;
	}
	Ref<Terrain3DAssetResource> res_dst = list[dst_id];
	if (res_dst.is_valid()) {
		res_dst->_id = p_src_id;
	}
	res_src->_id = dst_id;
	list[dst_id] = res_src;
	list[p_src_id] = res_dst;

	switch (p_type) {
		case TYPE_TEXTURE:
			update_texture_list();
			emit_signal("ids_swapped", AssetType::TYPE_TEXTURE, p_src_id, dst_id);
			break;
		case TYPE_MESH:
			if (_terrain) {
				_terrain->get_instancer()->swap_ids(p_src_id, dst_id);
			} else {
				LOG(ERROR, "Changing IDs before the terrain is initialized. Meshes on the ground may be wrong.");
			}
			update_mesh_list();
			emit_signal("ids_swapped", AssetType::TYPE_MESH, p_src_id, dst_id);
			break;
		default:
			return;
	}
}

/**
 * _set_asset_list attempts to keep the asset ID as saved in the resource file.
 * But if an ID is invalid or already taken, the new ID is changed to the next available one
 */
void Terrain3DAssets::_set_asset_list(const AssetType p_type, const TypedArray<Terrain3DAssetResource> &p_list) {
	Array list;
	int max_size;
	switch (p_type) {
		case TYPE_TEXTURE:
			list = _texture_list;
			max_size = MAX_TEXTURES;
			break;
		case TYPE_MESH:
			list = _mesh_list;
			max_size = MAX_MESHES;
			break;
		default:
			return;
	}
	int array_size = CLAMP(p_list.size(), 0, max_size);
	list.resize(array_size);
	int filled_id = -1;
	// For all provided textures up to MAX SIZE
	for (int i = 0; i < array_size; i++) {
		Ref<Terrain3DAssetResource> res = p_list[i];
		if (res.is_null()) {
			LOG(ERROR, "Asset ID: ", i, " is null");
			continue;
		}
		int id = res->get_id();
		// If saved texture ID is in range and doesn't exist, add it
		if (id >= 0 && id < array_size && !list[id]) {
			list[id] = res;
		} else {
			// Else texture ID is invalid or slot is already taken, insert in first available
			for (int j = filled_id + 1; j < array_size; j++) {
				if (!list[j]) {
					LOG(ERROR, res->get_class(), " ID ", id, " already exists. Setting '",
							res->get_asset_name(), "' to ID ", j,
							". Textures/Meshes on the ground may be wrong. Review Asset list to ensure each have unique IDs.");
					res->set_id(j);
					list[j] = res;
					filled_id = j;
					break;
				}
			}
		}
		if (!res->is_connected("id_changed", callable_mp(this, &Terrain3DAssets::_swap_ids))) {
			LOG(DEBUG, "Connecting to id_changed, ID: ", id);
			res->connect("id_changed", callable_mp(this, &Terrain3DAssets::_swap_ids));
		}
		res->initialize();
	}
	if (Terrain3D::debug_level >= DEBUG) {
		for (int i = 0; i < list.size(); i++) {
			Ref<Terrain3DAssetResource> res = list[i];
			int id = res.is_valid() ? res->get_id() : -1;
			String name = res.is_valid() ? res->get_asset_name() : "";
			LOG(DEBUG, "Asset ", i, ": ", name, ", ", res, ", stored ID: ", id);
		}
	}
}

void Terrain3DAssets::_set_asset(const AssetType p_type, const int p_id, const Ref<Terrain3DAssetResource> &p_asset) {
	LOG(INFO, "Setting asset type: ", p_type, ", ID: ", p_id, ", asset: ", p_asset);
	Array list;
	int max_size;
	switch (p_type) {
		case TYPE_TEXTURE:
			list = _texture_list;
			max_size = MAX_TEXTURES;
			break;
		case TYPE_MESH:
			list = _mesh_list;
			max_size = MAX_MESHES;
			break;
		default:
			return;
	}

	if (p_id < 0 || p_id >= max_size) {
		LOG(ERROR, "Invalid asset id: ", p_id, " range is 0-", max_size);
		return;
	}
	int id = CLAMP(p_id, 0, list.size());
	// Delete asset if null
	if (p_asset.is_null()) {
		// If final asset, remove it
		if (id == list.size() - 1) {
			LOG(DEBUG, "Deleting asset id: ", id);
			list.pop_back();
		} else {
			// Else just clear it
			Ref<Terrain3DAssetResource> res = list[id];
			res->clear();
			res->_id = id;
			res->initialize();
		}
	} else {
		// Else Insert/Add Asset at end if a high number
		if (id == list.size()) {
			p_asset->_id = id;
			list.push_back(p_asset);
		} else {
			// Else overwrite an existing slot
			p_asset->_id = id;
			list[id] = p_asset;
		}
		if (!p_asset->is_connected("id_changed", callable_mp(this, &Terrain3DAssets::_swap_ids))) {
			LOG(DEBUG, "Connecting to id_changed");
			p_asset->connect("id_changed", callable_mp(this, &Terrain3DAssets::_swap_ids));
		}
		p_asset->initialize();
	}
}

// A generated preview can stay on its asset until the user supplies a real texture.
static bool NeedsTerrainPlaceholder(const Ref<Texture2D> &in_refTexture)
{
	return in_refTexture.is_null() || in_refTexture->has_meta(SNAME("_terrain3d_generated_placeholder"));
}

static Image::Format TerrainLayerFormat(Image::Format eSource, bool bHasPlaceholder)
{
	if (eSource == Image::FORMAT_MAX)
	{
		return Image::FORMAT_RGBA8;
	}
	if (!bHasPlaceholder || eSource < Image::FORMAT_DXT1)
	{
		return eSource;
	}
	// Export templates need only the decoder. All layers of this array use one
	// format, so the authored pixels and mip levels can share it with the filler.
	switch (eSource)
	{
	case Image::FORMAT_BPTC_RGBF:
	case Image::FORMAT_BPTC_RGBFU:
	case Image::FORMAT_ASTC_4x4_HDR:
	case Image::FORMAT_ASTC_6x6_HDR:
	case Image::FORMAT_ASTC_8x8_HDR:
		return Image::FORMAT_RGBAH;
	default:
		return Image::FORMAT_RGBA8;
	}
}

void Terrain3DAssets::_update_texture_files() {
	IS_INIT(VOID);
	LOG(DEBUG, "Received texture_changed signal");
	arrMaterialTextureLayers.clear();
	_generated_albedo_textures.clear();
	_generated_normal_textures.clear();
	if (_texture_list.is_empty()) {
		LOG(DEBUG, "Emitting textures_changed");
		emit_signal("textures_changed");
		return;
	}

	// Detect image sizes and formats
	LOG(DEBUG, "Validating texture sizes");
	Vector2i albedo_size = V2I_ZERO;
	Vector2i normal_size = V2I_ZERO;
	Image::Format albedo_format = Image::FORMAT_MAX;
	Image::Format normal_format = Image::FORMAT_MAX;
	bool bMissingAlbedo = false;
	bool bMissingNormal = false;
	bool albedo_mipmaps = true;
	bool normal_mipmaps = true;
	_terrain->set_warning(WARN_ALL, false);

	for (const Ref<Terrain3DTextureAsset> &ta : _texture_list) {
		if (ta.is_null()) {
			continue;
		}

		Ref<Texture2D> albedo_tex = ta->_albedo_texture;
		if (NeedsTerrainPlaceholder(albedo_tex))
		{
			bMissingAlbedo = true;
		}
		else
		{
			Vector2i tex_size = albedo_tex->get_size();
			Ref<Image> img = albedo_tex->get_image();
			Image::Format format = img->get_format(); // DEPRECATED - In 4.7+ we can query albedo_tex->get_format() and albedo_tex->has_mipmaps()
			bool mipmaps = img->has_mipmaps();

			// If this is the first valid texture, set expected size and format for the arrays
			if (albedo_format == Image::FORMAT_MAX) {
				albedo_size = tex_size;
				albedo_format = format;
				albedo_mipmaps = mipmaps;
			} else { // else validate against first texture
				if (tex_size != albedo_size) {
					_terrain->set_warning(WARN_MISMATCHED_SIZE, true);
					LOG(ERROR, "Texture ID ", ta->get_id(), " albedo size: ", tex_size, " doesn't match size of first texture: ", albedo_size, ". They must be identical. Read Texture Prep in docs.");
				}
				if (format != albedo_format) {
					_terrain->set_warning(WARN_MISMATCHED_FORMAT, true);
					LOG(ERROR, "Texture ID ", ta->get_id(), " albedo format: ", format, " doesn't match format of first texture: ", albedo_format, ". They must be identical. Read Texture Prep in docs.");
				}
				if (mipmaps != albedo_mipmaps) {
					_terrain->set_warning(WARN_MISMATCHED_MIPMAPS, true);
					LOG(ERROR, "Texture ID ", ta->get_id(), " albedo mipmap setting (", mipmaps, ") doesn't match first texture (", albedo_mipmaps, "). They must be identical. Read Texture Prep in docs.");
				}
			}
		}

		Ref<Texture2D> normal_tex = ta->_normal_texture;
		if (NeedsTerrainPlaceholder(normal_tex))
		{
			bMissingNormal = true;
		}
		else
		{
			Vector2i tex_size = normal_tex->get_size();
			Ref<Image> img = normal_tex->get_image();
			Image::Format format = img->get_format(); // DEPRECATED - In 4.7+ we can query normal_tex->get_format() and normal_tex->has_mipmaps()
			bool mipmaps = img->has_mipmaps();

			// If this is the first valid texture, set expected size and format for the arrays
			if (normal_format == Image::FORMAT_MAX) {
				normal_size = tex_size;
				normal_format = format;
				normal_mipmaps = mipmaps;
			} else { // else validate against first texture
				if (tex_size != normal_size) {
					_terrain->set_warning(WARN_MISMATCHED_SIZE, true);
					LOG(ERROR, "Texture ID ", ta->get_id(), " normal size: ", tex_size, " doesn't match size of first texture: ", normal_size, ". They must be identical. Read Texture Prep in docs.");
				}
				if (format != normal_format) {
					_terrain->set_warning(WARN_MISMATCHED_FORMAT, true);
					LOG(ERROR, "Texture ID ", ta->get_id(), " normal format: ", format, " doesn't match format of first texture: ", normal_format, ". They must be identical. Read Texture Prep in docs.");
				}
				if (mipmaps != normal_mipmaps) {
					_terrain->set_warning(WARN_MISMATCHED_MIPMAPS, true);
					LOG(ERROR, "Texture ID ", ta->get_id(), " normal mipmap setting (", mipmaps, ") doesn't match first texture (", normal_mipmaps, "). They must be identical. Read Texture Prep in docs.");
				}
			}
		}
	}
	if (_terrain->get_warnings()) {
		return;
	}

	// Setup defaults for generated texture
	if (normal_size == V2I_ZERO) {
		normal_size = albedo_size;
	} else if (albedo_size == V2I_ZERO) {
		albedo_size = normal_size;
	}
	if (albedo_size == V2I_ZERO) {
		albedo_size = V2I(1024);
		normal_size = albedo_size;
	}

	const Image::Format eTargetAlbedo = TerrainLayerFormat(albedo_format, bMissingAlbedo);
	const Image::Format eTargetNormal = TerrainLayerFormat(normal_format, bMissingNormal);
	auto stBuildLayers = [&](bool bAlbedo, Vector2i vSize, bool bMipmaps, Image::Format eFormat, TypedArray<Image> &out_arrLayers) -> Error
	{
		Ref<ImageTexture> refPlaceholder;
		for (const Ref<Terrain3DTextureAsset> &refAsset : _texture_list)
		{
			if (refAsset.is_null())
			{
				continue;
			}
			const Ref<Texture2D> refTexture = bAlbedo ? refAsset->_albedo_texture : refAsset->_normal_texture;
			Ref<Image> refImage;
			if (NeedsTerrainPlaceholder(refTexture))
			{
				if (refPlaceholder.is_null())
				{
					refImage = Util::get_filled_image(vSize, bAlbedo ? COLOR_CHECKED : COLOR_NORMAL, bMipmaps, eFormat);
					refPlaceholder = ImageTexture::create_from_image(refImage);
					refPlaceholder->set_meta(SNAME("_terrain3d_generated_placeholder"), true);
				}
				else
				{
					refImage = refPlaceholder->get_image();
				}
				// Keep the preview and thumbnail visible without recursively rebuilding the arrays.
				const bool bBlocked = refAsset->is_blocking_signals();
				refAsset->set_block_signals(true);
				if (bAlbedo)
				{
					refAsset->set_albedo_texture(refPlaceholder);
				}
				else
				{
					refAsset->set_normal_texture(refPlaceholder);
				}
				refAsset->set_block_signals(bBlocked);
			} else {
				refImage = refTexture->get_image();
				ERR_FAIL_COND_V(refImage.is_null(), ERR_UNAVAILABLE);
				if (!IS_EDITOR && refTexture->get_path().contains("ImageTexture"))
				{
					LOG(WARN, "Texture ID ", refAsset->get_id(), " is saved in the scene. Save it as a file and link it.");
				}
				if (refImage->get_format() != eFormat)
				{
					refImage = refImage->duplicate();
					if (refImage->is_compressed())
					{
						Error eErr = refImage->decompress();
						ERR_FAIL_COND_V_MSG(eErr != OK, eErr, "Could not decode a Terrain3D layer for an array with missing textures.");
					}
					refImage->convert(eFormat);
				}
			}
			out_arrLayers.push_back(refImage);
		}
		return OK;
	};

	TypedArray<Image> arrAlbedos;
	TypedArray<Image> arrNormals;
	if (stBuildLayers(true, albedo_size, albedo_mipmaps, eTargetAlbedo, arrAlbedos) != OK ||
		stBuildLayers(false, normal_size, normal_mipmaps, eTargetNormal, arrNormals) != OK)
	{
		return;
	}
	if (!arrAlbedos.is_empty())
	{
		_generated_albedo_textures.create(arrAlbedos);
		_generated_normal_textures.create(arrNormals);
	}
	int nLayer = 0;
	for (const Ref<Terrain3DTextureAsset> &refAsset : _texture_list)
	{
		arrMaterialTextureLayers.push_back(refAsset.is_valid() ? nLayer++ : -1);
	}
	LOG(DEBUG, "Emitting textures_changed");
	emit_signal("textures_changed");
}

void Terrain3DAssets::_update_texture_settings() {
	LOG(DEBUG, "Received setting_changed signal");
	if (!_texture_list.is_empty()) {
		LOG(INFO, "Updating texture asset settings arrays");
		_texture_colors.clear();
		_texture_normal_depths.clear();
		_texture_ao_strengths.clear();
		_texture_ao_light_affects.clear();
		_texture_roughness_mods.clear();
		_texture_uv_scales.clear();
		_texture_detiles.clear();
		_texture_displacements.clear();

		for (const Ref<Terrain3DTextureAsset> &ta : _texture_list) {
			if (ta.is_null()) {
				continue;
			}
			if (ta->is_highlighted()) {
				_texture_colors.push_back(ta->get_highlight_color());
			} else {
				_texture_colors.push_back(ta->get_albedo_color());
			}
			_texture_normal_depths.push_back(ta->get_normal_depth());
			_texture_ao_strengths.push_back(ta->get_ao_strength());
			_texture_ao_light_affects.push_back(ta->get_ao_light_affect());
			_texture_roughness_mods.push_back(ta->get_roughness());
			_texture_uv_scales.push_back(ta->get_uv_scale());
			_texture_detiles.push_back(Vector2(ta->get_detiling_rotation(), ta->get_detiling_shift()));
			_texture_displacements.push_back(Vector2(ta->get_displacement_offset(), ta->get_displacement_scale()));
		}
	}
	LOG(DEBUG, "Emitting textures_changed");
	emit_signal("textures_changed");
}

void Terrain3DAssets::_update_mesh(const int p_id) {
	if (p_id < 0 || p_id >= _mesh_list.size()) {
		LOG(ERROR, "Invalid mesh ID: ", p_id);
		return;
	}
	Ref<Terrain3DMeshAsset> ma = _mesh_list[p_id];
	create_mesh_thumbnails(p_id, V2I(512), true);
	IS_INSTANCER_INIT(VOID);
	Terrain3DInstancer *instancer = _terrain->get_instancer();
	instancer->update_mmis(p_id, V2I_MAX, false);
}

void Terrain3DAssets::_setup_thumbnail_creation() {
	IS_INIT(VOID);
	if (_scenario.is_valid()) {
		return;
	}
	LOG(INFO, "Setting up mesh thumbnail creation viewports");
	// Setup Mesh preview environment
	_scenario = TERRAIN_RS->scenario_create();

	_viewport = TERRAIN_RS->viewport_create();
	TERRAIN_RS->viewport_set_update_mode(_viewport, RSE::VIEWPORT_UPDATE_DISABLED);
	TERRAIN_RS->viewport_set_scenario(_viewport, _scenario);
	TERRAIN_RS->viewport_set_size(_viewport, 128, 128);
	TERRAIN_RS->viewport_set_transparent_background(_viewport, true);
	TERRAIN_RS->viewport_set_active(_viewport, true);
	_viewport_texture = TERRAIN_RS->viewport_get_texture(_viewport);

	_camera = TERRAIN_RS->camera_create();
	TERRAIN_RS->viewport_attach_camera(_viewport, _camera);
	TERRAIN_RS->camera_set_transform(_camera, Transform3D(Basis(), Vector3(0, 0, 3)));
	TERRAIN_RS->camera_set_orthogonal(_camera, 1.0, 0.01, 1000.0);

	_key_light = TERRAIN_RS->directional_light_create();
	_key_light_instance = TERRAIN_RS->instance_create2(_key_light, _scenario);
	TERRAIN_RS->instance_set_transform(_key_light_instance, Transform3D().looking_at(V3(-1), V3_UP));

	_fill_light = TERRAIN_RS->directional_light_create();
	TERRAIN_RS->light_set_color(_fill_light, Color(0.3, 0.3, 0.3));
	_fill_light_instance = TERRAIN_RS->instance_create2(_fill_light, _scenario);
	TERRAIN_RS->instance_set_transform(_fill_light_instance, Transform3D().looking_at(V3_UP, Vector3(0, 0, 1)));

	_mesh_instance = TERRAIN_RS->instance_create();
	TERRAIN_RS->instance_set_scenario(_mesh_instance, _scenario);
}

///////////////////////////
// Public Functions
///////////////////////////

void Terrain3DAssets::initialize(Terrain3D *p_terrain) {
	if (p_terrain) {
		_terrain = p_terrain;
	} else {
		LOG(ERROR, "Initialization failed, p_terrain is null");
		return;
	}
	LOG(INFO, "Initializing assets");
	if (IS_EDITOR) {
		_setup_thumbnail_creation();
	}

	// Update assets
	update_texture_list();
	update_mesh_list();
}

void Terrain3DAssets::uninitialize() {
	LOG(INFO, "Uninitializing assets");
	_terrain = nullptr;
}

void Terrain3DAssets::destroy() {
	LOG(INFO, "Destroying assets");
	_terrain = nullptr;
	_generated_albedo_textures.clear();
	_generated_normal_textures.clear();
	_texture_list.clear();
	arrMaterialTextureLayers.clear();
	_mesh_list.clear();
	_texture_colors.clear();
	_texture_normal_depths.clear();
	_texture_ao_strengths.clear();
	_texture_ao_light_affects.clear();
	_texture_roughness_mods.clear();
	_texture_uv_scales.clear();
	_texture_detiles.clear();

	if (_scenario.is_valid()) {
		TERRAIN_RS->free_rid(_mesh_instance);
		TERRAIN_RS->free_rid(_fill_light_instance);
		TERRAIN_RS->free_rid(_fill_light);
		TERRAIN_RS->free_rid(_key_light_instance);
		TERRAIN_RS->free_rid(_key_light);
		TERRAIN_RS->free_rid(_camera);
		TERRAIN_RS->free_rid(_viewport);
		TERRAIN_RS->free_rid(_scenario);
		_mesh_instance = RID();
		_fill_light_instance = RID();
		_fill_light = RID();
		_key_light_instance = RID();
		_key_light = RID();
		_camera = RID();
		_viewport = RID();
		_scenario = RID();
	}
}

// Called when creating a new asset
void Terrain3DAssets::set_texture_asset(const int p_id, const Ref<Terrain3DTextureAsset> &p_texture) {
	if (p_id < 0 || p_id >= MAX_TEXTURES) {
		LOG(ERROR, "Invalid texture id: ", p_id, " range is 0-", MAX_TEXTURES - 1);
		return;
	}
	if (p_id < _texture_list.size() && _texture_list[p_id] == p_texture) {
		return;
	}
	LOG(INFO, "Setting texture id: ", p_id);
	_set_asset(TYPE_TEXTURE, p_id, p_texture);
	update_texture_list();
}

// Called when loading a list of assets from an assets resource file on disk
void Terrain3DAssets::set_texture_list(const TypedArray<Terrain3DTextureAsset> &p_texture_list) {
	LOG(INFO, "Setting texture list with ", p_texture_list.size(), " entries");
	if (!differs(_texture_list, p_texture_list)) {
		return;
	}
	_set_asset_list(TYPE_TEXTURE, p_texture_list);
	update_texture_list();
}

void Terrain3DAssets::clear_textures(const bool p_update) {
	LOG(INFO, "Clearing texture list");
	_texture_list.clear();
	if (p_update) {
		update_texture_list();
	}
}

void Terrain3DAssets::update_texture_list() {
	LOG(INFO, "Reconnecting texture signals");
	for (const Ref<Terrain3DTextureAsset> &ta : _texture_list) {
		if (ta.is_null()) {
			LOG(ERROR, "Null TextureAsset found at index: ", _texture_list.find(ta));
			continue;
		}
		if (!ta->is_connected("file_changed", callable_mp(this, &Terrain3DAssets::_update_texture_files))) {
			LOG(DEBUG, "Connecting file_changed signal");
			ta->connect("file_changed", callable_mp(this, &Terrain3DAssets::_update_texture_files));
		}
		if (!ta->is_connected("setting_changed", callable_mp(this, &Terrain3DAssets::_update_texture_settings))) {
			LOG(DEBUG, "Connecting setting_changed signal");
			ta->connect("setting_changed", callable_mp(this, &Terrain3DAssets::_update_texture_settings));
		}
	}
	_update_texture_files();
	_update_texture_settings();
}

// Called when creating a new asset
void Terrain3DAssets::set_mesh_asset(const int p_id, const Ref<Terrain3DMeshAsset> &p_mesh_asset) {
	if (p_id < 0 || p_id >= MAX_MESHES) {
		LOG(ERROR, "Invalid mesh id: ", p_id, " range is 0-", MAX_MESHES - 1);
		return;
	}
	if (p_id < _mesh_list.size() && _mesh_list[p_id] == p_mesh_asset) {
		return;
	}
	LOG(INFO, "Setting mesh id: ", p_id, ", ", p_mesh_asset);
	if (p_mesh_asset.is_null()) {
		IS_INSTANCER_INIT(VOID);
		_terrain->get_instancer()->clear_by_mesh(p_id);
	}
	_set_asset(TYPE_MESH, p_id, p_mesh_asset);
	update_mesh_list();
}

// Called when loading a list of assets from an assets resource file on disk
void Terrain3DAssets::set_mesh_list(const TypedArray<Terrain3DMeshAsset> &p_mesh_list) {
	LOG(INFO, "Setting mesh list with ", p_mesh_list.size(), " entries");
	if (!differs(_mesh_list, p_mesh_list)) {
		return;
	}
	_set_asset_list(TYPE_MESH, p_mesh_list);
	update_mesh_list();
}

// p_id = -1 for all meshes
// Adapted from godot\editor\plugins\editor_preview_plugins.cpp:EditorMeshPreviewPlugin
void Terrain3DAssets::create_mesh_thumbnails(const int p_id, const Vector2i &p_size, const bool p_force) {
	LOG(INFO, "Creating mesh thumbnails for ID: ", p_id, ", size: ", p_size);
	int max = get_mesh_count();
	if (p_id < -1 || p_id >= max) {
		return;
	}
	if (!_mesh_instance.is_valid()) {
		_setup_thumbnail_creation();
	}
	int start, end;
	if (p_id < 0) {
		start = 0;
		end = max;
	} else {
		start = CLAMP(p_id, 0, max - 1);
		end = CLAMP(p_id + 1, 0, max);
	}
	Vector2i size = CLAMP(p_size, V2I(2), V2I(4096));

	LOG(DEBUG, "Creating thumbnails for ids: ", start, " through ", end - 1);
	for (int i = start; i < end; i++) {
		Ref<Terrain3DMeshAsset> ma = get_mesh_asset(i);
		LOG(EXTREME, i, ": Getting Terrain3DMeshAsset: ", ptr_to_str(*ma));
		if (ma.is_null()) {
			LOG(ERROR, i, ": Terrain3DMeshAsset is null, skipping");
			continue;
		}
		if (!p_force && ma->get_thumbnail().is_valid()) {
			LOG(EXTREME, "Thumbnail already generated, skipping");
			continue;
		}
		// Setup mesh
		Ref<Mesh> mesh = ma->get_mesh(0);
		LOG(EXTREME, i, ": Getting Mesh 0: ", mesh);
		if (mesh.is_null()) {
			LOG(ERROR, i, ": Mesh is null, skipping");
			continue;
		}
		TERRAIN_RS->instance_set_base(_mesh_instance, mesh->get_rid());

		// Setup material
		Ref<Material> mat = ma->get_material_override();
		RID rid = mat.is_valid() ? mat->get_rid() : RID();
		TERRAIN_RS->instance_geometry_set_material_override(_mesh_instance, rid);
		mat = ma->get_material_overlay();
		rid = mat.is_valid() ? mat->get_rid() : RID();
		TERRAIN_RS->instance_geometry_set_material_overlay(_mesh_instance, rid);

		// Setup scene
		AABB aabb = mesh->get_aabb();
		Vector3 ofs = aabb.get_center();
		aabb.position -= ofs;
		Transform3D xform;
		xform.basis = Basis().rotated(V3_UP, -Math::PI * 0.125f);
		xform.basis = Basis().rotated(Vector3(1.f, 0.f, 0.f), Math::PI * 0.125f) * xform.basis;
		AABB rot_aabb = xform.xform(aabb);
		real_t m = MAX(rot_aabb.size.x, rot_aabb.size.y) * 0.5f;
		if (m == 0.f) {
			m = 1.f;
		}
		m = .5f / m;
		xform.basis.scale(V3(m));
		xform.origin = -xform.basis.xform(ofs);
		xform.origin.z -= rot_aabb.size.z * 2.f;
		TERRAIN_RS->instance_set_transform(_mesh_instance, xform);

		// Capture image
		TERRAIN_RS->viewport_set_size(_viewport, size.x, size.y);
		TERRAIN_RS->viewport_set_update_mode(_viewport, RSE::VIEWPORT_UPDATE_ONCE);
		TERRAIN_RS->draw(true, 0.0);

		Ref<Image> refImg = TERRAIN_RS->texture_2d_get(_viewport_texture);
		TERRAIN_RS->instance_set_base(_mesh_instance, RID()); // Clear mesh
		if (refImg.is_valid())
		{
			LOG(EXTREME, i, ": Retrieving image: ", refImg, " size: ", refImg->get_size(), " format: ", refImg->get_format());
			ma->set_thumbnail(ImageTexture::create_from_image(refImg));
		} else {
			LOG(ERROR, "_viewport_texture is null. Couldn't create thumbnail picture");
		}
	}
	return;
}

void Terrain3DAssets::update_mesh_list() {
	IS_INSTANCER_INIT(VOID);
	LOG(INFO, "Updating mesh list");
	if (_mesh_list.size() == 0) {
		LOG(DEBUG, "Mesh list empty, clearing instancer and adding a default mesh");
		_terrain->get_instancer()->destroy();
		Ref<Terrain3DMeshAsset> new_ma;
		new_ma.instantiate();
		set_mesh_asset(0, new_ma);
	}
	LOG(DEBUG, "Reconnecting mesh instance signals");
	for (Ref<Terrain3DMeshAsset> ma : _mesh_list) {
		if (ma.is_null()) {
			LOG(ERROR, "Null Terrain3DMeshAsset found at index ", _mesh_list.find(ma));
			continue;
		}
		if (ma->get_mesh().is_null()) {
			LOG(ERROR, "Terrain3DMeshAsset has null mesh at index ", _mesh_list.find(ma));
			continue;
		}
		if (!ma->is_connected("instancer_setting_changed", callable_mp(this, &Terrain3DAssets::_update_mesh))) {
			LOG(DEBUG, "Connecting instancer_setting_changed signal to _update_mesh");
			ma->connect("instancer_setting_changed", callable_mp(this, &Terrain3DAssets::_update_mesh));
		}
	}
	LOG(DEBUG, "Emitting meshes_changed");
	emit_signal("meshes_changed");
}

void Terrain3DAssets::load_pending_meshes() {
	// Reload meshes for all mesh assets that have changed. Used by the instancer after clearing
	for (const Ref<Terrain3DMeshAsset> &ma : _mesh_list) {
		if (ma.is_valid() && ma->is_scene_file_pending()) {
			ma->commit_meshes();
		}
	}
}

Error Terrain3DAssets::save(const String &p_path) {
	if (p_path.is_empty() && get_path().is_empty()) {
		return ERR_FILE_NOT_FOUND;
	}
	if (!p_path.is_empty()) {
		LOG(DEBUG, "Setting file path to ", p_path);
		set_path(p_path, true);
	}
	// Save to external resource file if specified
	Error err = OK;
	String path = get_path();
	if (path.get_extension() == "tres" || path.get_extension() == "res") {
		LOG(DEBUG, "Attempting to save external file: " + path);
		err = ResourceSaver::save(this, path, ResourceSaver::FLAG_COMPRESS);
		if (err == OK) {
			LOG(INFO, "File saved successfully: ", path);
		} else {
			LOG(ERROR, "Cannot save file: ", path, ". Error code: ", ERROR, ". Look up @GlobalScope Error enum in the Godot docs");
		}
	}
	return err;
}

///////////////////////////
// Protected Functions
///////////////////////////

void Terrain3DAssets::_bind_methods() {
	BIND_ENUM_CONSTANT(TYPE_TEXTURE);
	BIND_ENUM_CONSTANT(TYPE_MESH);
	BIND_CONSTANT(MAX_TEXTURES);
	BIND_CONSTANT(MAX_MESHES);

	ADD_SIGNAL(MethodInfo("ids_swapped",
			PropertyInfo(Variant::INT, "type"),
			PropertyInfo(Variant::INT, "old_id"),
			PropertyInfo(Variant::INT, "new_id")));

	ClassDB::bind_method(D_METHOD("set_texture_asset", "id", "texture"), &Terrain3DAssets::set_texture_asset);
	ClassDB::bind_method(D_METHOD("get_texture_asset", "id"), &Terrain3DAssets::get_texture_asset);
	ClassDB::bind_method(D_METHOD("set_texture_list", "texture_list"), &Terrain3DAssets::set_texture_list);
	ClassDB::bind_method(D_METHOD("get_texture_list"), &Terrain3DAssets::get_texture_list);
	ClassDB::bind_method(D_METHOD("get_texture_count"), &Terrain3DAssets::get_texture_count);
	ClassDB::bind_method(D_METHOD("get_albedo_array_rid"), &Terrain3DAssets::get_albedo_array_rid);
	ClassDB::bind_method(D_METHOD("get_normal_array_rid"), &Terrain3DAssets::get_normal_array_rid);
	ClassDB::bind_method(D_METHOD("get_texture_colors"), &Terrain3DAssets::get_texture_colors);
	ClassDB::bind_method(D_METHOD("get_texture_normal_depths"), &Terrain3DAssets::get_texture_normal_depths);
	ClassDB::bind_method(D_METHOD("get_texture_ao_strengths"), &Terrain3DAssets::get_texture_ao_strengths);
	ClassDB::bind_method(D_METHOD("get_texture_ao_light_affects"), &Terrain3DAssets::get_texture_ao_light_affects);
	ClassDB::bind_method(D_METHOD("get_texture_roughness_mods"), &Terrain3DAssets::get_texture_roughness_mods);
	ClassDB::bind_method(D_METHOD("get_texture_uv_scales"), &Terrain3DAssets::get_texture_uv_scales);
	ClassDB::bind_method(D_METHOD("get_texture_detiles"), &Terrain3DAssets::get_texture_detiles);
	ClassDB::bind_method(D_METHOD("get_texture_displacements"), &Terrain3DAssets::get_texture_displacements);
	ClassDB::bind_method(D_METHOD("clear_textures", "update"), &Terrain3DAssets::clear_textures, DEFVAL(false));
	ClassDB::bind_method(D_METHOD("update_texture_list"), &Terrain3DAssets::update_texture_list);

	ClassDB::bind_method(D_METHOD("set_mesh_asset", "id", "mesh"), &Terrain3DAssets::set_mesh_asset);
	ClassDB::bind_method(D_METHOD("get_mesh_asset", "id"), &Terrain3DAssets::get_mesh_asset);
	ClassDB::bind_method(D_METHOD("set_mesh_list", "mesh_list"), &Terrain3DAssets::set_mesh_list);
	ClassDB::bind_method(D_METHOD("get_mesh_list"), &Terrain3DAssets::get_mesh_list);
	ClassDB::bind_method(D_METHOD("get_mesh_count"), &Terrain3DAssets::get_mesh_count);
	ClassDB::bind_method(D_METHOD("create_mesh_thumbnails", "id", "size", "force"), &Terrain3DAssets::create_mesh_thumbnails, DEFVAL(-1), DEFVAL(V2I(512)), DEFVAL(false));
	ClassDB::bind_method(D_METHOD("update_mesh_list"), &Terrain3DAssets::update_mesh_list);

	ClassDB::bind_method(D_METHOD("save", "path"), &Terrain3DAssets::save, DEFVAL(""));

	int ro_flags = PROPERTY_USAGE_STORAGE | PROPERTY_USAGE_EDITOR | PROPERTY_USAGE_READ_ONLY;
	ADD_PROPERTY(PropertyInfo(Variant::ARRAY, "mesh_list", PROPERTY_HINT_ARRAY_TYPE, "Terrain3DMeshAsset", ro_flags), "set_mesh_list", "get_mesh_list");
	ADD_PROPERTY(PropertyInfo(Variant::ARRAY, "texture_list", PROPERTY_HINT_ARRAY_TYPE, "Terrain3DTextureAsset", ro_flags), "set_texture_list", "get_texture_list");

	ADD_SIGNAL(MethodInfo("meshes_changed"));
	ADD_SIGNAL(MethodInfo("textures_changed"));
}
