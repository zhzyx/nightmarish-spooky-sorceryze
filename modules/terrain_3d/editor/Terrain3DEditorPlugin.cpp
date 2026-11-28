/**************************************************************************/
/*  Terrain3DEditorPlugin.cpp                                            */
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

#include "Terrain3DEditorPlugin.h"

#include "Terrain3DExport.h"

#include "core/config/project_settings.h"
#include "core/crypto/crypto_core.h"
#include "core/io/compression.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/resource_loader.h"
#include "core/object/callable_mp.h"
#include "core/object/script_language.h"
#include "core/os/os.h"
#include "editor/editor_node.h"
#include "editor/plugins/editor_plugin.h"
#include "editor/scene/3d/node_3d_editor_plugin.h"
#include "editor/scene/3d/node_3d_editor_viewport.h"

#include <cstring>
#include <iterator>

namespace
{
struct Terrain3DEditorFile
{
	const char *pPath;
	int nSize;
	int nCompressedSize;
	bool bSubstituteRoot;
	const char *const *pChunks;
	size_t nChunkCount;
};
#include "terrain_3d_editor_resources.gen.h"

Error WriteEditorFile(const Terrain3DEditorFile &stAsset, const String &strStagingDir, const String &strRoot)
{
	Vector<uint8_t> arrPacked;
	arrPacked.resize(stAsset.nCompressedSize);
	size_t nOffset = 0;
	for (size_t nI = 0; nI < stAsset.nChunkCount; nI++)
	{
		const char *pChunk = stAsset.pChunks[nI];
		size_t nWritten = 0;
		Error eErr = CryptoCore::b64_decode(arrPacked.ptrw() + nOffset, arrPacked.size() - nOffset, &nWritten, reinterpret_cast<const uint8_t *>(pChunk), std::strlen(pChunk));
		ERR_FAIL_COND_V(eErr != OK, eErr);
		nOffset += nWritten;
	}
	ERR_FAIL_COND_V(nOffset != size_t(stAsset.nCompressedSize), ERR_FILE_CORRUPT);

	Vector<uint8_t> arrData;
	arrData.resize(stAsset.nSize);
	int64_t nSize = Compression::decompress(arrData.ptrw(), arrData.size(), arrPacked.ptr(), arrPacked.size(), Compression::MODE_DEFLATE);
	ERR_FAIL_COND_V(nSize != arrData.size(), ERR_FILE_CORRUPT);

	String strPath = strStagingDir.path_join(stAsset.pPath);
	Error eErr = DirAccess::make_dir_recursive_absolute(strPath.get_base_dir());
	ERR_FAIL_COND_V(eErr != OK, eErr);
	Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE, &eErr);
	ERR_FAIL_COND_V(refFile.is_null(), eErr);
	if (stAsset.bSubstituteRoot)
	{
		CharString strText = String::utf8(reinterpret_cast<const char *>(arrData.ptr()), arrData.size()).replace("@TERRAIN3D_EDITOR_ROOT@", strRoot).utf8();
		ERR_FAIL_COND_V(!refFile->store_buffer(reinterpret_cast<const uint8_t *>(strText.get_data()), strText.length()), ERR_FILE_CANT_WRITE);
	}
	else
	{
		ERR_FAIL_COND_V(!refFile->store_buffer(arrData), ERR_FILE_CANT_WRITE);
	}
	return OK;
}

Error UnpackEditorFiles(const String &strRoot)
{
	if (DirAccess::dir_exists_absolute(strRoot))
	{
		return OK;
	}

	// Publish a complete directory so different editor processes can open a project concurrently.
	const String strStaging = strRoot + "." + itos(OS::get_singleton()->get_process_id()) + "." + itos(OS::get_singleton()->get_ticks_usec());
	Error eErr = DirAccess::make_dir_recursive_absolute(strStaging);
	ERR_FAIL_COND_V(eErr != OK, eErr);
	for (const Terrain3DEditorFile &stFile : terrain_3d_editor_files)
	{
		eErr = WriteEditorFile(stFile, strStaging, strRoot);
		if (eErr != OK)
		{
			break;
		}
	}
	if (eErr == OK)
	{
		eErr = DirAccess::rename_absolute(strStaging, strRoot);
		if (eErr == OK)
		{
			return OK;
		}
		if (DirAccess::dir_exists_absolute(strRoot))
		{
			eErr = OK; // Another editor published this revision first.
		}
	}

	Ref<DirAccess> refTemp = DirAccess::open(strStaging);
	if (refTemp.is_valid())
	{
		refTemp->erase_contents_recursive();
		refTemp.unref();
		DirAccess::remove_absolute(strStaging);
	}
	return eErr;
}

void FrameYugongTerrain(double fMidpoint, double fSize)
{
	Node3DEditor *pEditor = Node3DEditor::get_singleton();
	Node3DEditorViewport *pViewport = pEditor->get_editor_viewport(0);
	ERR_FAIL_NULL(pViewport);
	View3DController::Cursor &stCursor = pViewport->get_controller()->cursor;
	stCursor.pos_x = 0.0;
	stCursor.pos_y = fMidpoint;
	stCursor.pos_z = 0.0;
	stCursor.x_rot = stCursor.unsnapped_x_rot = 0.6f;
	stCursor.y_rot = stCursor.unsnapped_y_rot = -0.65f;
	stCursor.distance = CLAMP(fSize * 1.35, pEditor->get_znear() * 2.0, pEditor->get_zfar() * 0.8);
}

EditorPlugin *CreateTerrain3dEditor()
{
	EditorPlugin *pPlugin = memnew(EditorPlugin);
	const String strDir = ProjectSettings::get_singleton()->get_project_data_path().path_join("terrain_3d_editor").path_join(terrain_3d_editor_revision);
	Error eErr = UnpackEditorFiles(strDir);
	ERR_FAIL_COND_V_MSG(eErr != OK, pPlugin, "Could not prepare Terrain3D editor resources in " + strDir);
	Ref<Script> refScript = ResourceLoader::load(strDir.path_join("src/editor_plugin.gd"), "Script");
	ERR_FAIL_COND_V_MSG(refScript.is_null() || !refScript->can_instantiate(), pPlugin, "Could not load the built-in Terrain3D editor.");
	pPlugin->set_name("Terrain3DEditorPlugin");
	pPlugin->set_meta("frame_yugong_terrain", callable_mp_static(FrameYugongTerrain));
	pPlugin->set_script(refScript);
	return pPlugin;
}
} // namespace

void RegisterTerrain3dEditor()
{
	EditorPlugins::add_create_func(CreateTerrain3dEditor);
	EditorNode::add_init_callback(Terrain3DExportPlugin::Register);
}
