@tool
extends RefCounted

const ROOT := "@TERRAIN3D_EDITOR_ROOT@"

static func icon(file_name: String) -> ImageTexture:
	var path := ROOT.path_join("icons").path_join(file_name)
	var image := Image.new()
	var result := image.load_svg_from_string(FileAccess.get_file_as_string(path), EditorInterface.get_editor_scale())
	if result != OK:
		push_error("Failed to load Terrain3D editor icon %s (%s)" % [file_name, error_string(result)])
		return null
	return ImageTexture.create_from_image(image)


static func custom_brush_directory() -> String:
	return EditorInterface.get_editor_paths().get_data_dir().path_join("terrain3d/brushes")


static func open_custom_brush_directory() -> void:
	var path := custom_brush_directory()
	var result := DirAccess.make_dir_recursive_absolute(path)
	if result != OK:
		push_error("Could not create Terrain3D brush directory %s (%s)" % [path, error_string(result)])
		return
	OS.shell_open(path)


static func brush_paths() -> Dictionary[String, String]:
	var paths: Dictionary[String, String] = {}
	for directory in [ROOT.path_join("brushes"), custom_brush_directory()]:
		if not DirAccess.dir_exists_absolute(directory):
			continue
		for file_name in DirAccess.get_files_at(directory):
			if file_name.get_extension().to_lower() == "exr":
				paths[file_name] = directory.path_join(file_name)
	return paths
