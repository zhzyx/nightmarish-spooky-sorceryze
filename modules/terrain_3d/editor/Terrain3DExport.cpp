/**************************************************************************/
/*  Terrain3DExport.cpp                                                  */
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

#include "Terrain3DExport.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/resource_loader.h"
#include "core/object/class_db.h"
#include "editor/export/editor_export.h"
#include "editor/file_system/editor_file_system.h"
#include "scene/resources/packed_scene.h"
#include "scene/resources/resource_format_text.h"

namespace
{
class TerrainExportDependencies
{
public:
	explicit TerrainExportDependencies(HashSet<String> &out_setPaths)
		: setPaths(out_setPaths)
	{
	}

	bool SceneMayUseTerrain(const String &strPath)
	{
		// Binary and imported PackedScenes can keep their node types inside the bundled state.
		if (strPath.get_extension().to_lower() != "tscn")
		{
			return true;
		}
		const bool *pbCached = mapTerrainScenes.getptr(strPath);
		if (pbCached)
		{
			return *pbCached;
		}
		// A cycle or an unindexed dependency cannot be ruled out by metadata.
		mapTerrainScenes.insert(strPath, true);
		const Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::READ);
		if (refFile.is_null())
		{
			return true;
		}
		HashSet<StringName> setClasses;
		// The generic loader also inserts the file's own PackedScene type.
		// Here only an embedded PackedScene should require inspecting its bundled state.
		ResourceLoaderText stText;
		stText.open(refFile);
		if (stText.get_classes_used(&setClasses) != OK)
		{
			return true;
		}
		for (const StringName &snClass : setClasses)
		{
			if (snClass == SNAME("PackedScene") || ClassDB::is_parent_class(snClass, SNAME("Terrain3D")) ||
				ClassDB::is_parent_class(snClass, SNAME("Terrain3DMaterial")))
			{
				return true;
			}
		}
		int nFileIndex = -1;
		const EditorFileSystem *pFileSystem = EditorFileSystem::get_singleton();
		const EditorFileSystemDirectory *pDirectory = pFileSystem->find_file(strPath, &nFileIndex);
		if (!pDirectory)
		{
			return true;
		}
		// A text scene with only local instance overrides can inherit its terrain type.
		for (const String &strDependency : pDirectory->get_file_deps(nFileIndex))
		{
			const StringName snType = pFileSystem->get_file_type(strDependency);
			if (snType == StringName() || (snType == SNAME("PackedScene") && SceneMayUseTerrain(strDependency)))
			{
				return true;
			}
		}
		mapTerrainScenes.insert(strPath, false);
		return false;
	}

	void CollectResource(const Ref<Resource> &refResource)
	{
		if (setResources.has(refResource->get_instance_id()))
		{
			return;
		}
		setResources.insert(refResource->get_instance_id());
		if (refResource->is_class("Terrain3DMaterial"))
		{
			AddStream(refResource->get("material_rvt_stream_file"));
			AddStream(refResource->get("material_rvt_far_stream_file"));
			return;
		}
		const Ref<PackedScene> refScene = refResource;
		if (refScene.is_valid())
		{
			CollectScene(refScene->get_state());
			return;
		}
		List<PropertyInfo> arrProperties;
		refResource->get_property_list(&arrProperties);
		for (const PropertyInfo &stProperty : arrProperties)
		{
			if ((stProperty.usage & PROPERTY_USAGE_STORAGE) &&
				(stProperty.type == Variant::OBJECT || stProperty.type == Variant::ARRAY || stProperty.type == Variant::DICTIONARY || stProperty.type == Variant::NIL))
			{
				CollectEmbeddedMaterials(refResource->get(stProperty.name));
			}
		}
	}

	void CollectScene(const Ref<SceneState> &refState)
	{
		for (int nNode = 0; nNode < refState->get_node_count(); ++nNode)
		{
			const Ref<PackedScene> refInstance = refState->get_node_instance(nNode);
			if (refInstance.is_valid() && refInstance->is_built_in())
			{
				CollectResource(refInstance);
			}
			for (int nProperty = 0; nProperty < refState->get_node_property_count(nNode); ++nProperty)
			{
				const StringName snProperty = refState->get_node_property_name(nNode, nProperty);
				const Variant vValue = refState->get_node_property_value(nNode, nProperty);
				if (vValue.get_type() == Variant::STRING && (snProperty == SNAME("height_vt_stream_file") || snProperty == SNAME("data_directory")))
				{
					StringName snType = refState->get_node_type(nNode);
					if (snType == StringName())
					{
						snType = ResolveNodeType(refState, String(refState->get_node_path(nNode)).trim_prefix("./"));
					}
					if (ClassDB::is_parent_class(snType, SNAME("Terrain3D")))
					{
						if (snProperty == SNAME("data_directory"))
						{
							AddRegions(vValue);
						}
						else
						{
							AddStream(vValue);
						}
					}
				}
				else
				{
					CollectEmbeddedMaterials(vValue);
				}
			}
		}
	}

private:
	HashSet<String> &setPaths;
	HashSet<String> setDirectories;
	HashSet<ObjectID> setResources;
	HashSet<const void *> setContainers;
	HashMap<String, bool> mapTerrainScenes;

	// Local overrides on instanced/inherited nodes have no serialized native type.
	static StringName ResolveNodeType(const Ref<SceneState> &refState, const String &strPath)
	{
		for (int nNode = refState->get_node_count() - 1; nNode >= 0; --nNode)
		{
			const String strNodePath = String(refState->get_node_path(nNode)).trim_prefix("./");
			const StringName snType = refState->get_node_type(nNode);
			if (strNodePath == strPath && snType != StringName())
			{
				return snType;
			}
			if (strNodePath != "." && strPath != strNodePath && !strPath.begins_with(strNodePath + "/"))
			{
				continue;
			}
			const Ref<PackedScene> refInstance = refState->get_node_instance(nNode);
			if (refInstance.is_valid())
			{
				const String strRelative = strNodePath == strPath ? String(".") : strPath.trim_prefix(strNodePath + "/");
				const StringName snBaseType = ResolveNodeType(refInstance->get_state(), strRelative);
				if (snBaseType != StringName())
				{
					return snBaseType;
				}
			}
		}
		return StringName();
	}

	void CollectEmbeddedMaterials(const Variant &vValue)
	{
		switch (vValue.get_type())
		{
		case Variant::OBJECT: {
			const Ref<Resource> refResource = vValue;
			// External resources are visited as independent files in the export selection.
			if (refResource.is_valid() && refResource->is_built_in())
			{
				CollectResource(refResource);
			}
			break;
		}
		case Variant::ARRAY: {
			const Array arrValues = vValue;
			if (setContainers.has(arrValues.id()))
			{
				return;
			}
			setContainers.insert(arrValues.id());
			for (const Variant &vElement : arrValues)
			{
				CollectEmbeddedMaterials(vElement);
			}
			setContainers.erase(arrValues.id());
			break;
		}
		case Variant::DICTIONARY: {
			const Dictionary mapValues = vValue;
			if (setContainers.has(mapValues.id()))
			{
				return;
			}
			setContainers.insert(mapValues.id());
			for (const KeyValue<Variant, Variant> &stEntry : mapValues)
			{
				CollectEmbeddedMaterials(stEntry.key);
				CollectEmbeddedMaterials(stEntry.value);
			}
			setContainers.erase(mapValues.id());
			break;
		}
		default:
			break;
		}
	}

	void AddStream(const String &strFile)
	{
		if (!strFile.begins_with("res://") || strFile.get_extension().to_lower() != "svt")
		{
			return;
		}
		const String strPath = strFile.simplify_path();
		if (FileAccess::exists(strPath))
		{
			setPaths.insert(strPath);
		}
		else
		{
			WARN_PRINT(vformat("Cannot export referenced Terrain3D SVT file '%s'.", strPath));
		}
	}

	void AddRegions(const String &strDirectory)
	{
		if (!strDirectory.begins_with("res://"))
		{
			return;
		}
		const String strPath = strDirectory.simplify_path();
		if (setDirectories.has(strPath))
		{
			return;
		}
		setDirectories.insert(strPath);
		const Ref<DirAccess> refDir = DirAccess::open(strPath);
		if (refDir.is_null())
		{
			WARN_PRINT(vformat("Cannot open Terrain3D data directory '%s' during export.", strPath));
			return;
		}
		for (const String &strName : refDir->get_files())
		{
			if (strName.matchn("terrain3d*.res"))
			{
				const String strFile = strPath.path_join(strName);
				if (ClassDB::is_parent_class(ResourceLoader::get_resource_type(strFile), SNAME("Terrain3DRegion")))
				{
					setPaths.insert(strFile);
				}
			}
		}
	}
};
} // namespace

void Terrain3DExportPlugin::Register()
{
	Ref<Terrain3DExportPlugin> refPlugin;
	refPlugin.instantiate();
	EditorExport::get_singleton()->add_export_plugin(refPlugin);
}

String Terrain3DExportPlugin::get_name() const
{
	return "Terrain3D";
}

void Terrain3DExportPlugin::CollectExportDependencies(const HashSet<String> &setPaths, HashSet<String> &out_setDependencies) const
{
	TerrainExportDependencies stCollector(out_setDependencies);
	for (const String &strPath : setPaths)
	{
		const StringName snType = EditorFileSystem::get_singleton()->get_file_type(strPath);
		if (snType == SNAME("PackedScene"))
		{
			if (!stCollector.SceneMayUseTerrain(strPath))
			{
				continue;
			}
		}
		else if (!ClassDB::is_parent_class(snType, SNAME("Terrain3DMaterial")))
		{
			const String strExtension = strPath.get_extension().to_lower();
			if (strExtension != "res" && strExtension != "tres")
			{
				continue;
			}
			// Check the serialized class table before loading an unrelated resource into memory.
			HashSet<StringName> setClasses;
			ResourceLoader::get_classes_used(strPath, &setClasses);
			if (!setClasses.has(SNAME("Terrain3DMaterial")) && !setClasses.has(SNAME("PackedScene")))
			{
				continue;
			}
		}
		const Ref<Resource> refResource = ResourceLoader::load(strPath, "", ResourceFormatLoader::CACHE_MODE_IGNORE);
		if (refResource.is_valid())
		{
			stCollector.CollectResource(refResource);
		}
	}
}
