@tool
# Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.
# Menu for Terrain3D
extends HBoxContainer

const EditorResources = preload("../src/editor_resources.gd")


const DirectoryWizard: Script = preload("@TERRAIN3D_EDITOR_ROOT@/menu/directory_setup.gd")
const ChannelPacker: Script = preload("@TERRAIN3D_EDITOR_ROOT@/menu/channel_packer.gd")
const LodBaker: Script = preload("@TERRAIN3D_EDITOR_ROOT@/menu/baker.gd")

const MaterialSVTDialog: Script = preload("@TERRAIN3D_EDITOR_ROOT@/menu/material_svt_dialog.gd")

var material_svt: MaterialSVTDialog = MaterialSVTDialog.new()
var plugin: EditorPlugin
var initialize_button := Button.new()
var menu_button: MenuButton = MenuButton.new()
var directory_setup: DirectoryWizard = DirectoryWizard.new()
var packer: ChannelPacker = ChannelPacker.new()
var baker: LodBaker = LodBaker.new()

# These are IDs and order must be consistent with add_item and set_disabled IDs
enum {
	MENU_DIRECTORY_SETUP,
	MENU_PACK_TEXTURES,
	MENU_SEPARATOR,
	MENU_BAKE_ARRAY_MESH,
	MENU_BAKE_OCCLUDER,
	MENU_BAKE_MATERIAL_SVT,
	MENU_SEPARATOR2,
	MENU_SET_UP_NAVIGATION,
	MENU_BAKE_NAV_MESH,
	MENU_SEPARATOR3,
	MENU_BRUSH_DIRECTORY,
	MENU_SEPARATOR4,
	MENU_VIEW_LIVE_INFO_PANEL,
	MENU_INITIALIZE,
	MENU_PREVIEW_HEIGHT_VT,
}


func _enter_tree() -> void:
	directory_setup.plugin = plugin
	packer.plugin = plugin
	baker.plugin = plugin
	add_child(directory_setup)
	add_child(baker)
	add_child(material_svt)

	menu_button.text = "Terrain3D"
	menu_button.get_popup().add_item("Directory Setup...", 	MENU_DIRECTORY_SETUP)
	menu_button.get_popup().add_item("Pack Textures...", MENU_PACK_TEXTURES)
	menu_button.get_popup().add_separator("", MENU_SEPARATOR)
	menu_button.get_popup().add_item("Bake ArrayMesh...", MENU_BAKE_ARRAY_MESH)
	menu_button.get_popup().add_item("Bake Occluder3D...", MENU_BAKE_OCCLUDER)
	menu_button.get_popup().add_item("Build Material Streaming Mips…", MENU_BAKE_MATERIAL_SVT)
	menu_button.get_popup().add_separator("", MENU_SEPARATOR2)
	menu_button.get_popup().add_item("Set up Navigation...", MENU_SET_UP_NAVIGATION)
	menu_button.get_popup().add_item("Bake NavMesh...", MENU_BAKE_NAV_MESH)
	menu_button.get_popup().add_separator("", MENU_SEPARATOR3)
	menu_button.get_popup().add_item("Open Brush Directory...", MENU_BRUSH_DIRECTORY)
	menu_button.get_popup().add_separator("", MENU_SEPARATOR4)
	menu_button.get_popup().add_check_item("View LiveInfo Panel", MENU_VIEW_LIVE_INFO_PANEL)
	menu_button.get_popup().add_item("Initialize Empty Terrain", MENU_INITIALIZE)
	menu_button.get_popup().add_item("Preview Quadtree + Height VT", MENU_PREVIEW_HEIGHT_VT)
	menu_button.get_popup().set_item_tooltip(MENU_PREVIEW_HEIGHT_VT,
			"Use GPU quadtree geometry and virtual height pages for all terrains in this editor session.")

	menu_button.get_popup().id_pressed.connect(_on_menu_pressed)
	menu_button.about_to_popup.connect(_on_menu_about_to_popup)
	add_child(menu_button)
	initialize_button.name = "InitializeTerrain"
	initialize_button.text = "Initialize Terrain"
	initialize_button.tooltip_text = "Create a new data directory and a first editable region for this terrain."
	initialize_button.pressed.connect(plugin.initialize_selected_terrain)
	add_child(initialize_button)
	refresh_initialize_button()


func refresh_initialize_button() -> void:
	initialize_button.visible = plugin.can_initialize_terrain(plugin.terrain)


func _on_menu_pressed(p_id: int) -> void:
	match p_id:
		MENU_INITIALIZE:
			plugin.initialize_selected_terrain()
		MENU_PREVIEW_HEIGHT_VT:
			plugin.preview_height_vt()
		MENU_DIRECTORY_SETUP:
			directory_setup.directory_setup_popup()
		MENU_PACK_TEXTURES:
			packer.pack_textures_popup()
		MENU_BAKE_ARRAY_MESH:
			baker.bake_mesh_popup()
		MENU_BAKE_OCCLUDER:
			baker.bake_occluder_popup()
		MENU_BAKE_MATERIAL_SVT:
			material_svt.edit(plugin.terrain)
		MENU_SET_UP_NAVIGATION:
			baker.set_up_navigation_popup()
		MENU_BAKE_NAV_MESH:
			baker.bake_nav_mesh()
		MENU_BRUSH_DIRECTORY:
			EditorResources.open_custom_brush_directory()
		MENU_VIEW_LIVE_INFO_PANEL:
			plugin.ui.live_info_panel.enabled = !plugin.ui.live_info_panel.enabled
			menu_button.get_popup().set_item_checked(MENU_VIEW_LIVE_INFO_PANEL, plugin.ui.live_info_panel.enabled)
			# Reopen the popup since it is closed automatically
			menu_button.show_popup()


func _on_menu_about_to_popup() -> void:
	menu_button.get_popup().set_item_disabled(MENU_INITIALIZE, not plugin.can_initialize_terrain(plugin.terrain))
	menu_button.get_popup().set_item_disabled(MENU_PREVIEW_HEIGHT_VT, not plugin.terrain)
	menu_button.get_popup().set_item_disabled(MENU_DIRECTORY_SETUP, not plugin.terrain)
	menu_button.get_popup().set_item_disabled(MENU_PACK_TEXTURES, not plugin.terrain)
	menu_button.get_popup().set_item_disabled(MENU_BAKE_ARRAY_MESH, not plugin.terrain)
	menu_button.get_popup().set_item_disabled(MENU_BAKE_OCCLUDER, not plugin.terrain)
	menu_button.get_popup().set_item_disabled(MENU_BAKE_MATERIAL_SVT, not plugin.terrain)

	menu_button.get_popup().set_item_disabled(MENU_VIEW_LIVE_INFO_PANEL, not plugin.terrain)
	menu_button.get_popup().set_item_checked(MENU_VIEW_LIVE_INFO_PANEL, plugin.ui.live_info_panel.enabled)

	if plugin.terrain:
		var nav_regions: Array[NavigationRegion3D] = baker.find_terrain_nav_regions(plugin.terrain)
		menu_button.get_popup().set_item_disabled(MENU_BAKE_NAV_MESH, nav_regions.size() == 0)
		menu_button.get_popup().set_item_disabled(MENU_SET_UP_NAVIGATION, nav_regions.size() != 0)
	elif plugin.nav_region:
		var terrains: Array[Terrain3D] = baker.find_nav_region_terrains(plugin.nav_region)
		menu_button.get_popup().set_item_disabled(MENU_BAKE_NAV_MESH, terrains.size() == 0)
		menu_button.get_popup().set_item_disabled(MENU_SET_UP_NAVIGATION, true)
	else:
		menu_button.get_popup().set_item_disabled(MENU_BAKE_NAV_MESH, true)
		menu_button.get_popup().set_item_disabled(MENU_SET_UP_NAVIGATION, true)
