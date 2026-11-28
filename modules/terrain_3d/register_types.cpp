// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "core/object/class_db.h"

#include "register_types.h"
#include "terrain_3d.h"
#include "terrain_3d_editor.h"

#ifdef TOOLS_ENABLED
#include "editor/Terrain3DEditorPlugin.h"
#endif

void initialize_terrain_3d_module(ModuleInitializationLevel p_level) {
#ifdef TOOLS_ENABLED
	if (p_level == MODULE_INITIALIZATION_LEVEL_EDITOR)
	{
		RegisterTerrain3dEditor();
	}
#endif
	if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
		return;
	}
	Terrain3D::RegisterCVars();
	GDREGISTER_CLASS(Terrain3D);
	GDREGISTER_ABSTRACT_CLASS(Terrain3DAssetResource);
	GDREGISTER_CLASS(Terrain3DAssets);
	GDREGISTER_CLASS(Terrain3DData);
	GDREGISTER_CLASS(Terrain3DEditor);
	GDREGISTER_CLASS(Terrain3DCollision);
	GDREGISTER_CLASS(Terrain3DInstancer);
	GDREGISTER_CLASS(Terrain3DMaterial);
	GDREGISTER_CLASS(Terrain3DMeshAsset);
	GDREGISTER_CLASS(Terrain3DRegion);
	GDREGISTER_CLASS(Terrain3DTextureAsset);
	GDREGISTER_CLASS(Terrain3DUtil);
}

void uninitialize_terrain_3d_module(ModuleInitializationLevel p_level) {
	if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
		return;
	}
}
