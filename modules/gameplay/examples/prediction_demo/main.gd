extends Node

const OBJECT_BY_USER := {"user-alice": 100, "user-bob": 200}

var role := "client"
var port := 7200
var user := "alice"
var reconnect_token := ""
var latency_msec := 0
var jitter_msec := 0
var loss_permyriad := 0
var exit_after_sec := 0.0
var started_msec := 0

var game_state: GameplayGameState
var game_mode: GameplayGameMode
var session_manager: GameplaySessionManager
var dedicated_server: GameplayDedicatedServer
var session_client: GameplaySessionClient
var replication: GameplayMultiplayerReplication
var prediction: GameplayNetworkPrediction
var graph: GameplayReplicationGraph
var model: GameplayPredictionModel
var registered_users := {}
var authority_states := {}
var local_prediction: GameplayClientPrediction
var remote_buffer: GameplayInterpolationBuffer
var local_object_id := 0
var remote_object_id := 0
var client_registered := false
var input_accumulator := 0.0
var report_accumulator := 0.0


func _ready() -> void:
	started_msec = Time.get_ticks_msec()
	_parse_arguments()
	model = GameplayPredictionModel.new()
	model.fixed_step_msec = 16
	model.max_speed = 8.0
	if role == "server":
		_start_server()
	else:
		_start_client()


func _parse_arguments() -> void:
	for argument in OS.get_cmdline_user_args():
		var pair := argument.trim_prefix("--").split("=", true, 1)
		if pair.size() != 2:
			continue
		match pair[0]:
			"role": role = pair[1]
			"port": port = int(pair[1])
			"user": user = pair[1]
			"reconnect": reconnect_token = pair[1]
			"latency-ms": latency_msec = int(pair[1])
			"jitter-ms": jitter_msec = int(pair[1])
			"loss-permyriad": loss_permyriad = int(pair[1])
			"exit-after": exit_after_sec = float(pair[1])


func _make_conditions(seed_value: int) -> GameplayNetworkSimulator:
	var conditions := GameplayNetworkSimulator.new()
	conditions.set_seed(seed_value)
	conditions.latency_msec = latency_msec
	conditions.jitter_msec = jitter_msec
	conditions.loss_permyriad = loss_permyriad
	return conditions


func _start_server() -> void:
	game_state = GameplayGameState.new()
	game_mode = GameplayGameMode.new()
	session_manager = GameplaySessionManager.new()
	dedicated_server = GameplayDedicatedServer.new()
	replication = GameplayMultiplayerReplication.new()
	prediction = GameplayNetworkPrediction.new()
	graph = GameplayReplicationGraph.new()
	add_child(game_state)
	add_child(game_mode)
	add_child(session_manager)
	add_child(replication)
	add_child(prediction)
	add_child(dedicated_server)
	game_mode.game_state = game_state
	session_manager.game_mode = game_mode
	replication.set_replication_graph(graph)
	prediction.set_replication_graph(graph)
	prediction.set_network_simulator(_make_conditions(1001))
	dedicated_server.authenticator = _authenticate
	dedicated_server.replication = replication
	dedicated_server.prediction = prediction
	var config := GameplayServerConfig.new()
	config.bind_address = "127.0.0.1"
	config.port = port
	config.protocol_version = "prediction-demo-1"
	config.disconnect_grace_period_msec = 30000
	var error := dedicated_server.start(config, session_manager)
	if error != OK:
		push_error("Unable to start Gameplay Dedicated Server: %s" % error_string(error))
		get_tree().quit(1)
		return
	print("GF-5 server listening on 127.0.0.1:%d" % dedicated_server.get_bound_port())


func _authenticate(auth_token: String, supplied_reconnect_token: String) -> Dictionary:
	if auth_token != "alice" and auth_token != "bob":
		return {"accepted": false, "reason": "unknown_user"}
	var expected := "resume-" + auth_token
	if not supplied_reconnect_token.is_empty() and supplied_reconnect_token != expected:
		return {"accepted": false, "reason": "invalid_reconnect_token"}
	return {
		"accepted": true,
		"user_id": "user-" + auth_token,
		"session_id": "session-" + auth_token,
		"reconnect_token": expected,
	}


func _start_client() -> void:
	session_client = GameplaySessionClient.new()
	replication = GameplayMultiplayerReplication.new()
	prediction = GameplayNetworkPrediction.new()
	add_child(replication)
	add_child(prediction)
	add_child(session_client)
	prediction.set_network_simulator(_make_conditions(2001 if user == "alice" else 3001))
	session_client.replication = replication
	session_client.prediction = prediction
	var error := session_client.connect_to_server("127.0.0.1", port, "prediction-demo-1", user, reconnect_token)
	if error != OK:
		push_error("Unable to connect Gameplay client: %s" % error_string(error))
		get_tree().quit(1)


func _register_server_session(session: GameplayUserSession) -> void:
	var user_id := session.user_id
	if not OBJECT_BY_USER.has(user_id):
		return
	var object_id: int = OBJECT_BY_USER[user_id]
	var peer_id := session.peer_id
	if registered_users.has(user_id):
		var previous_peer: int = registered_users[user_id]
		if previous_peer != peer_id:
			prediction.set_server_object_owner_peer_id(object_id, peer_id)
			replication.set_object_owner_peer_id(object_id, peer_id)
			graph.set_object_owner_peer_id(object_id, peer_id)
			graph.remove_connection(previous_peer)
			registered_users[user_id] = peer_id
			print("%s rebound peer %d -> %d; PlayerState=%s" % [user_id, previous_peer, peer_id, session.player_state.get_instance_id()])
	else:
		prediction.register_server_object(object_id, peer_id, model)
		var state := GameplayReplicationState.new()
		var position_property := GameplayReplicationProperty.new()
		position_property.property_name = &"position"
		state.add_property(position_property, Vector3.ZERO)
		replication.register_object(object_id, peer_id, state)
		authority_states[object_id] = state
		var relevant := GameplayRelevancyObject.new()
		relevant.object_id = object_id
		relevant.owner_peer_id = peer_id
		relevant.policy = GameplayRelevancyObject.POLICY_ALWAYS
		relevant.estimated_update_bytes = 128
		graph.add_object(relevant)
		registered_users[user_id] = peer_id
		print("%s spawned object %d on peer %d; PlayerState=%s" % [user_id, object_id, peer_id, session.player_state.get_instance_id()])
	var view := GameplayConnectionView.new()
	view.peer_id = peer_id
	view.bandwidth_budget_bytes = 4096
	view.position = prediction.get_server_object_state(object_id).position
	replication.update_server_connection_view(view)


func _register_client_objects() -> void:
	local_object_id = 100 if user == "alice" else 200
	remote_object_id = 200 if user == "alice" else 100
	local_prediction = GameplayClientPrediction.new()
	local_prediction.set_model(model)
	remote_buffer = GameplayInterpolationBuffer.new()
	prediction.register_owned_client_object(local_object_id, local_prediction)
	prediction.register_remote_client_object(remote_object_id, remote_buffer)
	for object_id in [100, 200]:
		var state := GameplayReplicationState.new()
		var position_property := GameplayReplicationProperty.new()
		position_property.property_name = &"position"
		state.add_property(position_property, Vector3.ZERO)
		replication.register_object(object_id, session_client.get_peer_id() if object_id == local_object_id else 0, state)
	client_registered = true
	print("%s joined as peer %d; stable session=%s reconnect_token=%s" % [user, session_client.get_peer_id(), session_client.session_id, session_client.get_reconnect_token()])


func _process(delta: float) -> void:
	if role == "server":
		for session in session_manager.get_sessions():
			var connection := session_manager.get_connection(session.peer_id) if session.active else null
			if connection != null and connection.state == GameplayConnection.STATE_SPAWNED and session.player_state != null:
				_register_server_session(session)
		for object_id in authority_states:
			var authoritative := prediction.get_server_object_state(object_id)
			if authoritative != null:
				authority_states[object_id].set_property_value(&"position", authoritative.position)
		return

	if session_client.get_multiplayer_peer() != null:
		session_client.poll()
	if exit_after_sec > 0.0 and Time.get_ticks_msec() - started_msec >= int(exit_after_sec * 1000.0):
		session_client.disconnect_from_server()
		print("%s disconnected cleanly after %.1f seconds" % [user, exit_after_sec])
		get_tree().quit()
		return
	if session_client.is_joined() and not client_registered:
		_register_client_objects()
	if not client_registered:
		return
	input_accumulator += delta
	report_accumulator += delta
	while input_accumulator >= 0.016:
		input_accumulator -= 0.016
		var direction := Vector3.RIGHT if user == "alice" else Vector3.LEFT
		prediction.submit_local_input(local_object_id, direction, Time.get_ticks_msec())
	if report_accumulator >= 1.0:
		report_accumulator = 0.0
		var remote_sample := remote_buffer.sample(Time.get_ticks_msec())
		var remote_position := "waiting"
		if remote_sample.has("state"):
			remote_position = str(remote_sample.state.position)
		print("%s owner_predicted=%s ack=%d pending=%d remote_%s=%s (%s)" % [
			user,
			local_prediction.get_predicted_state().position,
			local_prediction.get_last_confirmed_sequence(),
			local_prediction.get_unconfirmed_input_count(),
			"bob" if user == "alice" else "alice",
			remote_position,
			remote_sample.get("status", "empty"),
		])
