extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if not dock:
		return
	if not require(await wait_for(func(): return FileAccess.file_exists(OS.get_environment("R09_DONE"))), "recovery receiver"):
		return
	print("R09_EDITOR ", OS.get_process_id())
	quit()
