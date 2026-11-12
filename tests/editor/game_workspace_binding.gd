@tool
extends SceneTree

# Launch this same probe with --editor --headless --path B and B/game.
# It does not connect providers or modify settings.
func _initialize() -> void:
	_run.call_deferred()

func _run() -> void:
	for attempt in range(100):
		var dock = root.find_child("AI Chat", true, false)
		if dock != null:
			await create_timer(2.0).timeout
			var expected := OS.get_environment("GAME_WORKSPACE_EXPECTED").replace("\\", "/").simplify_path()
			var actual := str(dock.get_production_workspace()).replace("\\", "/").simplify_path()
			var host := str(dock.get_installed_host_root()).replace("\\", "/").simplify_path()
			var result := {"ok": actual == expected and host != actual, "workspace":actual, "host":host,
				"project": ProjectSettings.globalize_path("res://"), "provider_execution":false}
			FileAccess.open(OS.get_environment("GAME_WORKSPACE_REPORT"), FileAccess.WRITE).store_string(JSON.stringify(result))
			quit(0 if result.ok else 1)
			return
		await process_frame
	quit(2)
