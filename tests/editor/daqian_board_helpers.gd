@tool
extends SceneTree

# Run against the candidate editor with DAQIAN_TEST_REPO pointing to a checkout
# containing both reviewed official helper revisions.
const BOARD := "customizations/components/godot-host/daqian/board.py"
const REVISIONS := ["26cda2ab35b3ec2f12daa8b3205518d8f7e55c7d", "69efa21779715953a567f9024137018896047909"]
var errors := []


func _initialize() -> void:
	run.call_deferred()


func check(ok: bool, message: String) -> void:
	if not ok:
		errors.append(message)


func run() -> void:
	for i in 8:
		await process_frame
	var workspace = root.find_child("DaqianWorkspace", true, false)
	var repo := OS.get_environment("DAQIAN_TEST_REPO")
	if not workspace or repo.is_empty():
		push_error("Candidate editor and DAQIAN_TEST_REPO are required")
		quit(1)
		return
	var folder := OS.get_user_data_dir().path_join("helper-" + Crypto.new().generate_random_bytes(8).hex_encode())
	DirAccess.make_dir_recursive_absolute(folder)
	var script := folder.path_join("board.py")
	var modern := folder.path_join("board_delta.py")
	for revision in REVISIONS:
		var git := OS.execute_with_pipe("git", ["-C", repo, "cat-file", "blob", revision + ":" + BOARD], true)
		if git.is_empty():
			check(false, "Missing historical Git fixture " + revision)
			continue
		var bytes: PackedByteArray = git.stdio.get_buffer(1024 * 1024)
		git.stdio.close()
		git.stderr.close()
		var source := bytes.get_string_from_utf8().replace("\r\n", "\n")
		var file := FileAccess.open(script, FileAccess.WRITE)
		file.store_string(source.replace("\n", "\r\n"))
		file.close()
		var args: PackedStringArray = workspace._board_entry_args(script)
		check(args.size() == 5 and args[0] == "-I" and args[1] == "-B" and args[3] == "--workspace-board-sha256" and args[4] == source.sha256_text(), "Helper digest was not forwarded for " + revision)
		if args.size() == 5:
			check(FileAccess.get_sha256(args[2]) == workspace.board_bundle_sha256, "Adapter payload failed its editor digest")
		file = FileAccess.open(modern, FileAccess.WRITE)
		file.close()
		check(workspace._board_entry_args(script) == PackedStringArray([script]), "Modern workspace helper was overridden")
		DirAccess.remove_absolute(modern)
		file = FileAccess.open(script, FileAccess.WRITE)
		file.store_string(source + "# custom installation\n")
		file.close()
		check(workspace._board_entry_args(script) == PackedStringArray([script]), "Modified helper was accepted as an official build")
	DirAccess.remove_absolute(script)
	DirAccess.remove_absolute(folder)
	for message in errors:
		push_error(message)
	if errors.is_empty():
		print("DAQIAN_BOARD_HELPERS_OK")
	quit(0 if errors.is_empty() else 1)
