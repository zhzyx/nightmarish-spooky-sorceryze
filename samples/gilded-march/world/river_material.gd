@tool
extends Node3D
const WATER_SHADER := preload("res://world/river.gdshader")
func _ready() -> void:
	var water := find_child("玉灰河",true,false) as MeshInstance3D
	if water:
		var surface := ShaderMaterial.new()
		surface.shader = WATER_SHADER
		water.material_override = surface
