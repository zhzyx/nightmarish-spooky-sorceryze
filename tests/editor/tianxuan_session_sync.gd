extends SceneTree

const LocalModelFixture = preload("res://local_model_fixture.gd")

var checks: Array[String] = []
var session: Node
var main: Control
var sidebar: Control
var legacy: Control
var modules: Control

func _initialize() -> void:
	run.call_deferred()

func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Native session synchronization: " + description)
		quit(1)
		return false
	checks.append(description)
	print("SESSION_SYNC_CHECK ", checks.size(), ": ", description)
	return true

func wait_until(predicate: Callable) -> bool:
	for attempt in 500:
		if predicate.call(): return true
		await create_timer(0.025).timeout
	return false

func login(view: Control, password: String, project := "workspace") -> bool:
	if not await wait_until(func(): return view._auth_mode == "accounts" and not view._submit.disabled): return false
	view._email.text = "first@example.invalid"
	view._secret.text = password
	view._project.text = project
	view._submit.pressed.emit()
	return await wait_until(func(): return not view._submit.disabled)

func choose_page(view: Control, page: String) -> void:
	for index in view._page_picker.item_count:
		if view._page_picker.get_item_metadata(index) == page:
			view._page_picker.select(index)
			view._page_picker.item_selected.emit(index)
			return

func select_module() -> bool:
	if not await wait_until(func(): return not modules.busy): return false
	modules.picker.select(1)
	modules.picker.item_selected.emit(1)
	if not await wait_until(func(): return not modules.busy and modules.picker.item_count > 1 and modules.picker.get_item_metadata(1) != null): return false
	modules.picker.get_popup().hide()
	for index in modules.picker.item_count:
		if modules.picker.get_item_metadata(index) == OS.get_environment("TX_MODULE"):
			modules.picker.select(index)
			modules.picker.item_selected.emit(index)
			return await wait_until(func(): return not modules.busy and modules.module_id == OS.get_environment("TX_MODULE"))
	return false

func run() -> void:
	root.size = Vector2i(1500, 950)
	await create_timer(0.3).timeout
	if not check(not (await LocalModelFixture.configure(self)).is_empty(), "only the isolated local model catalog is configured; no completion is requested"): return
	var base := EditorInterface.get_base_control()
	main = base.find_child("TianxuanWorkspaceView", true, false)
	sidebar = base.find_child("TianxuanSidebarView", true, false)
	legacy = base.find_child("WorkbenchBusinessSession", true, false)
	modules = base.find_child("WorkbenchBusinessModules", true, false)
	session = main.get_meta("controller").session
	var password := OS.get_environment("TX_PASSWORD")
	if not check(sidebar.get_meta("controller").session == session and legacy.get_meta("session_controller") == session, "all three native surfaces share the same editor-owned session"): return
	if not check(main._current_page == "account" and sidebar._current_page == "account", "both native views initially show their authentication gate"): return
	sidebar._secret.text = "unsubmitted-right-fixture-secret"
	legacy._secret.text = "unsubmitted-workbench-fixture-secret"
	if not check(await login(main, password), "the left login controls finish a real isolated password authentication"): return
	if not check(not session.get_identity().is_empty() and main._current_page == "home" and sidebar._current_page == "home", "login in the left workspace releases both authentication gates without a second login"): return
	if not check(sidebar._secret.text.is_empty() and legacy._secret.text.is_empty(), "successful login clears unsent credentials in the other native surfaces"): return
	var identity: Dictionary = session.get_identity()
	var shown_name := str(identity.get("name", identity.id))
	if not check(main._connection.text.contains(shown_name) and sidebar._connection.text.contains(shown_name) and main._connection.text.contains(identity.project) and sidebar._connection.text.contains(identity.project) and legacy._status.text.contains(identity.project), "visible status text on all surfaces reflects the authenticated account and project"): return
	if not check(legacy.get_identity() == identity and not legacy._form.visible and legacy._sign_out.visible and legacy._project.text == identity.project, "AIWorkbench immediately displays the same identity and project and closes its login form"): return
	var temporary := "本次登录未保存；关闭编辑器后需重新登录。"
	if not check(main.find_child("TianxuanLoginPersistence", true, false).text == temporary and sidebar.find_child("TianxuanLoginPersistence", true, false).text == temporary and legacy.find_child("WorkbenchLoginPersistence", true, false).text == temporary, "all login views explain the real temporary session without claiming a saved device grant"): return
	choose_page(sidebar, "account")
	choose_page(main, "documents")
	var generation: int = session.generation
	legacy.find_child("ChooseAccount", true, false).pressed.emit()
	legacy._email.text = "first@example.invalid"
	legacy._secret.text = password
	legacy.find_child("Authenticate", true, false).pressed.emit()
	if not check(await wait_until(func(): return session.generation > generation), "AIWorkbench reauthentication reaches the same real session"): return
	if not check(main._current_page == "documents" and sidebar._current_page == "account", "reauthentication preserves a working page and an explicitly selected connection page"): return
	identity = session.get_identity()
	generation = session.generation
	var controller: Node = main.get_meta("controller")
	if not check(controller.save_draft("session-sync-proof", {"text": "retained private fixture draft"}), "store a draft before a refused account switch"): return
	if not check(await login(sidebar, "incorrect-private-fixture-password"), "an invalid password completes with a refusal"): return
	if not check(session.get_identity() == identity and session.generation == generation and main._current_page == "documents" and sidebar._current_page == "account" and not legacy.get_identity().is_empty(), "failed login preserves the prior identity, project and other view's working page"): return
	if not check(controller.load_draft("session-sync-proof").get("text") == "retained private fixture draft", "failed authentication retains the prior scope's unsent draft"): return
	await session.reset()
	if not check(main._current_page == "account" and sidebar._current_page == "account" and legacy.get_identity().is_empty(), "sign-out clears every native identity display together"): return
	main._secret.text = "unsubmitted-left-fixture-secret"
	if not check(await login(sidebar, password) and main._current_page == "home" and sidebar._current_page == "home", "login in the right sidebar also releases the left authentication gate"): return
	if not check(main._secret.text.is_empty(), "reverse-direction login clears the left view's unsent credential"): return
	var open_chat: Button = base.find_child("OpenAIWorkbench", true, false)
	open_chat.button_down.emit()
	open_chat.pressed.emit()
	if not check(await select_module(), "select the real fixture business module before saving a draft"): return
	var legacy_key := JSON.stringify([session.origin, session.get_identity().id, "workspace", ProjectSettings.globalize_path("res://"), modules.module_id, null])
	if not check(modules.get_meta("write_draft").call(legacy_key, {"text": "UNVERIFIED_LEGACY_ORIGIN_DRAFT"}), "seed an ambiguous historical draft using the old origin-key format"): return
	modules._restore_draft()
	if not check(modules._draft_key(null) != legacy_key and modules.composer.text.is_empty() and modules._read_draft(legacy_key).get("text") == "UNVERIFIED_LEGACY_ORIGIN_DRAFT", "new trusted-origin keys do not import ambiguous old drafts or delete their stored bytes"): return
	var legacy_scope := JSON.stringify([session.origin, session.get_identity().id, "workspace", ProjectSettings.globalize_path("res://")]).sha256_text()
	modules.restore_consultation_location({"scope": legacy_scope, "number": 1, "id": "legacy-unknown-target"})
	if not check(modules._consultation_scope() != legacy_scope and modules.get_consultation_location().is_empty(), "old consultation locations cannot be restored under a newly trusted service scope"): return
	modules.composer.text = "ORIGIN_A_DRAFT"
	modules.composer.text_changed.emit()
	if not check(modules._save_draft(), "save an unsent business draft under the first origin"): return
	var first_key: String = modules._draft_key(null)
	var first_actor: String = str(session.get_identity().id)
	choose_page(main, "account")
	main._address.text = OS.get_environment("TX_SECOND_API")
	main._connect_service()
	if not check(session.get_identity().is_empty() and main._address.text == session.origin and sidebar._address.text == session.origin and legacy.find_child("WorkbenchServiceAddress", true, false).text.contains(session.origin), "changing the service updates both native addresses and AIWorkbench without retaining the old identity"): return
	if not check(await login(sidebar, password) and str(session.get_identity().id) == first_actor, "the second private HTTP origin authenticates the exact same fixture actor"): return
	if not check(main._current_page == "account", "an explicitly selected connection page stays open during another view's login"): return
	open_chat.button_down.emit()
	open_chat.pressed.emit()
	if not check(await select_module(), "select the same business module identifier under the second origin"): return
	var second_key: String = modules._draft_key(null)
	if not check(first_key != second_key and modules.composer.text.is_empty() and modules._read_draft(first_key).get("text") == "ORIGIN_A_DRAFT", "identical actors and module IDs across origins do not reuse a draft, and the first draft remains stored"): return
	modules.composer.text = "ORIGIN_B_DRAFT"
	modules.composer.text_changed.emit()
	if not check(modules._save_draft(), "save a distinct second-origin draft"): return
	main._address.text = OS.get_environment("TX_API")
	main._connect_service()
	if not check(await login(main, password), "return to the first real HTTP origin"): return
	open_chat.button_down.emit()
	open_chat.pressed.emit()
	if not check(await select_module() and modules._draft_key(null) == first_key and modules.composer.text == "ORIGIN_A_DRAFT", "returning to the original service restores only its own unsent draft"): return
	choose_page(main, "account")
	choose_page(sidebar, "documents")
	generation = session.generation
	legacy.find_child("ChooseAccount", true, false).pressed.emit()
	legacy._email.text = "first@example.invalid"
	legacy._secret.text = password
	legacy._project.text = "workspace-two"
	legacy.find_child("Authenticate", true, false).pressed.emit()
	if not check(await wait_until(func(): return session.generation > generation) and session.get_identity().project == "workspace-two", "a verified project change is shared across the editor session"): return
	if not check(main._project.text == "workspace-two" and sidebar._project.text == "workspace-two" and modules.project == "workspace-two" and main._current_page == "account" and sidebar._current_page == "documents", "project labels refresh without overriding explicit pages or changing business module ownership"): return
	await session.reset()
	if not check(main.find_child("TianxuanLoginPersistence", true, false).text == "尚未登录" and legacy.find_child("WorkbenchLoginPersistence", true, false).text == "尚未登录", "logout replaces persistence claims with the signed-out state"): return
	print(JSON.stringify({"passed": true, "checks": checks, "cross_origin_keys_distinct": first_key != second_key}))
	quit(0)
