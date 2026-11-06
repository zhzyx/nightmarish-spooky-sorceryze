/**************************************************************************/
/*  gameplay_match.cpp                                                    */
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
/* "Software"), to deal in the Software without restriction, including  */
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

#include "gameplay_match.h"

#include "gameplay_subsystem.h"

#include "core/object/class_db.h"
#include "scene/main/multiplayer_api.h"

template <typename T>
static T *_gameplay_match_object(ObjectID p_id) {
	return Object::cast_to<T>(ObjectDB::get_instance(p_id));
}

void GameplayGameState::_bind_methods() {
	ClassDB::bind_method(D_METHOD("add_player_state", "player_state"), &GameplayGameState::add_player_state);
	ClassDB::bind_method(D_METHOD("remove_player_state", "player_state"), &GameplayGameState::remove_player_state);
	ClassDB::bind_method(D_METHOD("has_player_state", "player_state"), &GameplayGameState::has_player_state);
	ClassDB::bind_method(D_METHOD("get_player_states"), &GameplayGameState::get_player_states);
	ClassDB::bind_method(D_METHOD("get_player_count"), &GameplayGameState::get_player_count);
	ClassDB::bind_method(D_METHOD("set_match_phase", "phase"), &GameplayGameState::set_match_phase);
	ClassDB::bind_method(D_METHOD("get_match_phase"), &GameplayGameState::get_match_phase);

	ADD_PROPERTY(PropertyInfo(Variant::STRING_NAME, "match_phase"), "set_match_phase", "get_match_phase");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "player_count", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_player_count");

	ADD_SIGNAL(MethodInfo("player_state_added", PropertyInfo(Variant::OBJECT, "player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState")));
	ADD_SIGNAL(MethodInfo("player_state_removed", PropertyInfo(Variant::OBJECT, "player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState")));
	ADD_SIGNAL(MethodInfo("match_phase_changed", PropertyInfo(Variant::STRING_NAME, "old_phase"), PropertyInfo(Variant::STRING_NAME, "new_phase")));
}

Error GameplayGameState::add_player_state(GameplayPlayerState *p_player_state) {
	ERR_FAIL_NULL_V(p_player_state, ERR_INVALID_PARAMETER);
	if (has_player_state(p_player_state)) {
		return OK;
	}
	GameplayGameState *old_game_state = p_player_state->get_game_state();
	if (old_game_state && old_game_state != this) {
		old_game_state->remove_player_state(p_player_state);
	}
	player_state_ids.push_back(p_player_state->get_instance_id());
	p_player_state->_set_game_state(this);
	emit_signal(SNAME("player_state_added"), p_player_state);
	return OK;
}

bool GameplayGameState::remove_player_state(GameplayPlayerState *p_player_state) {
	if (!p_player_state) {
		return false;
	}
	const ObjectID id = p_player_state->get_instance_id();
	for (int i = 0; i < player_state_ids.size(); i++) {
		if (player_state_ids[i] == id) {
			player_state_ids.remove_at(i);
			p_player_state->_set_game_state(nullptr);
			emit_signal(SNAME("player_state_removed"), p_player_state);
			return true;
		}
	}
	return false;
}

bool GameplayGameState::has_player_state(GameplayPlayerState *p_player_state) const {
	return p_player_state && player_state_ids.has(p_player_state->get_instance_id());
}

TypedArray<GameplayPlayerState> GameplayGameState::get_player_states() const {
	TypedArray<GameplayPlayerState> states;
	for (const ObjectID &id : player_state_ids) {
		GameplayPlayerState *state = _gameplay_match_object<GameplayPlayerState>(id);
		if (state) {
			states.push_back(state);
		}
	}
	return states;
}

int GameplayGameState::get_player_count() const {
	return get_player_states().size();
}

void GameplayGameState::set_match_phase(const StringName &p_phase) {
	if (match_phase == p_phase) {
		return;
	}
	const StringName old_phase = match_phase;
	match_phase = p_phase;
	emit_signal(SNAME("match_phase_changed"), old_phase, match_phase);
}

StringName GameplayGameState::get_match_phase() const {
	return match_phase;
}

void GameplayGameState::_player_state_destroyed(GameplayPlayerState *p_player_state) {
	if (!p_player_state) {
		return;
	}
	const ObjectID id = p_player_state->get_instance_id();
	const int index = player_state_ids.find(id);
	if (index >= 0) {
		player_state_ids.remove_at(index);
		emit_signal(SNAME("player_state_removed"), p_player_state);
	}
}

GameplayGameState::~GameplayGameState() {
	for (const ObjectID &id : player_state_ids) {
		GameplayPlayerState *state = _gameplay_match_object<GameplayPlayerState>(id);
		if (state && state->get_game_state() == this) {
			state->_set_game_state(nullptr);
		}
	}
	player_state_ids.clear();
}

void GameplayGameMode::_bind_methods() {
	ClassDB::bind_method(D_METHOD("is_authority_context"), &GameplayGameMode::is_authority_context);
	ClassDB::bind_method(D_METHOD("set_game_state", "game_state"), &GameplayGameMode::set_game_state);
	ClassDB::bind_method(D_METHOD("get_game_state"), &GameplayGameMode::get_game_state);
	ClassDB::bind_method(D_METHOD("admit_player", "controller", "player_state"), &GameplayGameMode::admit_player);
	ClassDB::bind_method(D_METHOD("remove_player", "controller", "preserve_player_state"), &GameplayGameMode::remove_player, DEFVAL(false));
	ClassDB::bind_method(D_METHOD("get_controllers"), &GameplayGameMode::get_controllers);
	ClassDB::bind_method(D_METHOD("get_player_count"), &GameplayGameMode::get_player_count);
	ClassDB::bind_method(D_METHOD("start_match"), &GameplayGameMode::start_match);
	ClassDB::bind_method(D_METHOD("end_match"), &GameplayGameMode::end_match);
	ClassDB::bind_method(D_METHOD("is_match_running"), &GameplayGameMode::is_match_running);

	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "game_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayGameState"), "set_game_state", "get_game_state");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "match_running", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_match_running");

	ADD_SIGNAL(MethodInfo("player_admitted", PropertyInfo(Variant::OBJECT, "controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController"), PropertyInfo(Variant::OBJECT, "player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState")));
	ADD_SIGNAL(MethodInfo("player_removed", PropertyInfo(Variant::OBJECT, "controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController"), PropertyInfo(Variant::OBJECT, "player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState"), PropertyInfo(Variant::BOOL, "player_state_preserved")));
	ADD_SIGNAL(MethodInfo("match_started"));
	ADD_SIGNAL(MethodInfo("match_ended"));
}

bool GameplayGameMode::is_authority_context() const {
	Ref<MultiplayerAPI> api = get_multiplayer();
	return api.is_null() || !api->has_multiplayer_peer() || is_multiplayer_authority();
}

void GameplayGameMode::set_game_state(GameplayGameState *p_game_state) {
	if (get_game_state() == p_game_state) {
		return;
	}
	ERR_FAIL_COND_MSG(match_running, "Cannot replace the game state while the match is running.");
	ERR_FAIL_COND_MSG(!controller_ids.is_empty(), "Cannot replace the game state while players are admitted.");
	game_state_id = p_game_state ? p_game_state->get_instance_id() : ObjectID();
}

GameplayGameState *GameplayGameMode::get_game_state() const {
	return _gameplay_match_object<GameplayGameState>(game_state_id);
}

Error GameplayGameMode::admit_player(GameplayController *p_controller, GameplayPlayerState *p_player_state) {
	ERR_FAIL_COND_V_MSG(!is_authority_context(), ERR_UNAUTHORIZED, "Only the gameplay authority can admit players.");
	ERR_FAIL_NULL_V(p_controller, ERR_INVALID_PARAMETER);
	ERR_FAIL_NULL_V(p_player_state, ERR_INVALID_PARAMETER);
	GameplayGameState *game_state = get_game_state();
	ERR_FAIL_NULL_V_MSG(game_state, ERR_UNCONFIGURED, "A game state is required before admitting players.");

	GameplayGameMode *old_mode = p_controller->get_game_mode();
	if (old_mode && old_mode != this) {
		old_mode->_remove_controller(p_controller, true, true);
	}
	GameplayController *state_controller = p_player_state->get_controller();
	ERR_FAIL_COND_V_MSG(state_controller && state_controller != p_controller, ERR_ALREADY_IN_USE, "The player state already belongs to another controller.");
	if (old_mode == this && p_controller->get_player_state() == p_player_state) {
		return OK;
	}
	GameplayPlayerState *old_player_state = p_controller->get_player_state();
	if (old_player_state && old_player_state != p_player_state) {
		game_state->remove_player_state(old_player_state);
	}
	if (!controller_ids.has(p_controller->get_instance_id())) {
		controller_ids.push_back(p_controller->get_instance_id());
	}
	p_controller->_set_game_mode(this);
	p_controller->set_player_state(p_player_state);
	game_state->add_player_state(p_player_state);
	emit_signal(SNAME("player_admitted"), p_controller, p_player_state);
	return OK;
}

void GameplayGameMode::_remove_controller(GameplayController *p_controller, bool p_preserve_player_state, bool p_emit_signal) {
	if (!p_controller) {
		return;
	}
	const ObjectID id = p_controller->get_instance_id();
	const int index = controller_ids.find(id);
	if (index < 0) {
		return;
	}
	controller_ids.remove_at(index);
	GameplayPlayerState *player_state = p_controller->get_player_state();
	p_controller->unpossess();
	p_controller->set_player_state(nullptr);
	p_controller->_set_game_mode(nullptr);
	if (player_state) {
		player_state->deactivate();
	}
	if (!p_preserve_player_state && player_state) {
		GameplayGameState *game_state = get_game_state();
		if (game_state) {
			game_state->remove_player_state(player_state);
		}
	}
	if (p_emit_signal) {
		emit_signal(SNAME("player_removed"), p_controller, player_state, p_preserve_player_state);
	}
}

Error GameplayGameMode::remove_player(GameplayController *p_controller, bool p_preserve_player_state) {
	ERR_FAIL_COND_V_MSG(!is_authority_context(), ERR_UNAUTHORIZED, "Only the gameplay authority can remove players.");
	ERR_FAIL_NULL_V(p_controller, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V_MSG(!controller_ids.has(p_controller->get_instance_id()), ERR_DOES_NOT_EXIST, "The controller is not admitted to this game mode.");
	_remove_controller(p_controller, p_preserve_player_state, true);
	return OK;
}

TypedArray<GameplayController> GameplayGameMode::get_controllers() const {
	TypedArray<GameplayController> controllers;
	for (const ObjectID &id : controller_ids) {
		GameplayController *controller = _gameplay_match_object<GameplayController>(id);
		if (controller) {
			controllers.push_back(controller);
		}
	}
	return controllers;
}

int GameplayGameMode::get_player_count() const {
	return get_controllers().size();
}

Error GameplayGameMode::start_match() {
	ERR_FAIL_COND_V_MSG(!is_authority_context(), ERR_UNAUTHORIZED, "Only the gameplay authority can start a match.");
	ERR_FAIL_COND_V_MSG(match_running, ERR_ALREADY_IN_USE, "The match is already running.");
	ERR_FAIL_NULL_V_MSG(get_game_state(), ERR_UNCONFIGURED, "A game state is required before starting a match.");
	match_running = true;
	get_game_state()->set_match_phase(SNAME("in_progress"));
	emit_signal(SNAME("match_started"));
	return OK;
}

Error GameplayGameMode::end_match() {
	ERR_FAIL_COND_V_MSG(!is_authority_context(), ERR_UNAUTHORIZED, "Only the gameplay authority can end a match.");
	ERR_FAIL_COND_V_MSG(!match_running, ERR_DOES_NOT_EXIST, "The match is not running.");
	match_running = false;
	GameplayGameState *game_state = get_game_state();
	if (game_state) {
		game_state->set_match_phase(SNAME("ended"));
	}
	emit_signal(SNAME("match_ended"));
	return OK;
}

bool GameplayGameMode::is_match_running() const {
	return match_running;
}

void GameplayGameMode::_controller_destroyed(GameplayController *p_controller) {
	_remove_controller(p_controller, false, true);
}

GameplayGameMode::~GameplayGameMode() {
	match_running = false;
	while (!controller_ids.is_empty()) {
		GameplayController *controller = _gameplay_match_object<GameplayController>(controller_ids[controller_ids.size() - 1]);
		if (controller) {
			_remove_controller(controller, false, false);
		} else {
			controller_ids.remove_at(controller_ids.size() - 1);
		}
	}
}

void GameplayWorld::_bind_methods() {
	ClassDB::bind_method(D_METHOD("initialize_world", "game_state", "game_mode", "subsystems"), &GameplayWorld::initialize_world, DEFVAL(Variant()), DEFVAL(Variant()));
	ClassDB::bind_method(D_METHOD("shutdown_world"), &GameplayWorld::shutdown_world);
	ClassDB::bind_method(D_METHOD("is_initialized"), &GameplayWorld::is_initialized);
	ClassDB::bind_method(D_METHOD("get_game_mode"), &GameplayWorld::get_game_mode);
	ClassDB::bind_method(D_METHOD("get_game_state"), &GameplayWorld::get_game_state);
	ClassDB::bind_method(D_METHOD("get_subsystem_registry"), &GameplayWorld::get_subsystem_registry);

	ADD_SIGNAL(MethodInfo("world_initialized"));
	ADD_SIGNAL(MethodInfo("world_shutdown"));
}

Error GameplayWorld::initialize_world(GameplayGameState *p_game_state, GameplayGameMode *p_game_mode, GameplaySubsystemRegistry *p_subsystems) {
	ERR_FAIL_COND_V_MSG(initialized, ERR_ALREADY_IN_USE, "The gameplay world is already initialized.");
	ERR_FAIL_NULL_V_MSG(p_game_state, ERR_INVALID_PARAMETER, "A gameplay world requires a game state.");
	if (p_game_mode) {
		ERR_FAIL_COND_V_MSG(!p_game_mode->is_authority_context(), ERR_UNAUTHORIZED, "A game mode can only initialize in an authority context.");
		p_game_mode->set_game_state(p_game_state);
	}
	if (p_subsystems) {
		ERR_FAIL_COND_V_MSG(p_subsystems->get_scope() != GameplaySubsystem::SCOPE_WORLD, ERR_INVALID_PARAMETER, "A gameplay world requires a world-scoped subsystem registry.");
		const Error err = p_subsystems->initialize_subsystems();
		ERR_FAIL_COND_V(err != OK, err);
	}
	game_state_id = p_game_state->get_instance_id();
	game_mode_id = p_game_mode ? p_game_mode->get_instance_id() : ObjectID();
	subsystem_registry_id = p_subsystems ? p_subsystems->get_instance_id() : ObjectID();
	initialized = true;
	emit_signal(SNAME("world_initialized"));
	return OK;
}

void GameplayWorld::shutdown_world() {
	if (!initialized) {
		return;
	}
	GameplayGameMode *game_mode = get_game_mode();
	if (game_mode && game_mode->is_match_running()) {
		game_mode->end_match();
	}
	GameplaySubsystemRegistry *subsystems = get_subsystem_registry();
	if (subsystems) {
		subsystems->deinitialize_subsystems();
	}
	game_mode_id = ObjectID();
	game_state_id = ObjectID();
	subsystem_registry_id = ObjectID();
	initialized = false;
	emit_signal(SNAME("world_shutdown"));
}

bool GameplayWorld::is_initialized() const {
	return initialized;
}

GameplayGameMode *GameplayWorld::get_game_mode() const {
	return _gameplay_match_object<GameplayGameMode>(game_mode_id);
}

GameplayGameState *GameplayWorld::get_game_state() const {
	return _gameplay_match_object<GameplayGameState>(game_state_id);
}

GameplaySubsystemRegistry *GameplayWorld::get_subsystem_registry() const {
	return _gameplay_match_object<GameplaySubsystemRegistry>(subsystem_registry_id);
}

GameplayWorld::~GameplayWorld() {
	shutdown_world();
}
