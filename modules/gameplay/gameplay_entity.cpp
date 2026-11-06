/**************************************************************************/
/*  gameplay_entity.cpp                                                   */
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

#include "gameplay_entity.h"

#include "gameplay_match.h"

#include "core/object/class_db.h"
#include "core/object/object.h"

template <typename T>
static T *_gameplay_object(ObjectID p_id) {
	return Object::cast_to<T>(ObjectDB::get_instance(p_id));
}

void GameplayComponent::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_component_name", "name"), &GameplayComponent::set_component_name);
	ClassDB::bind_method(D_METHOD("get_component_name"), &GameplayComponent::get_component_name);
	ClassDB::bind_method(D_METHOD("set_gameplay_owner", "owner"), &GameplayComponent::set_gameplay_owner);
	ClassDB::bind_method(D_METHOD("get_gameplay_owner"), &GameplayComponent::get_gameplay_owner);
	ClassDB::bind_method(D_METHOD("activate"), &GameplayComponent::activate);
	ClassDB::bind_method(D_METHOD("deactivate"), &GameplayComponent::deactivate);
	ClassDB::bind_method(D_METHOD("is_active"), &GameplayComponent::is_active);

	ADD_PROPERTY(PropertyInfo(Variant::STRING_NAME, "component_name"), "set_component_name", "get_component_name");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "active", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_active");

	ADD_SIGNAL(MethodInfo("gameplay_owner_changed", PropertyInfo(Variant::OBJECT, "old_owner", PROPERTY_HINT_RESOURCE_TYPE, Node::get_class_static()), PropertyInfo(Variant::OBJECT, "new_owner", PROPERTY_HINT_RESOURCE_TYPE, Node::get_class_static())));
	ADD_SIGNAL(MethodInfo("activated"));
	ADD_SIGNAL(MethodInfo("deactivated"));
}

void GameplayComponent::set_component_name(const StringName &p_name) {
	component_name = p_name;
}

StringName GameplayComponent::get_component_name() const {
	return component_name;
}

void GameplayComponent::set_gameplay_owner(Node *p_owner) {
	Node *old_owner = get_gameplay_owner();
	if (old_owner == p_owner) {
		return;
	}
	gameplay_owner_id = p_owner ? p_owner->get_instance_id() : ObjectID();
	emit_signal(SNAME("gameplay_owner_changed"), old_owner, p_owner);
}

Node *GameplayComponent::get_gameplay_owner() const {
	return _gameplay_object<Node>(gameplay_owner_id);
}

void GameplayComponent::activate() {
	if (active) {
		return;
	}
	active = true;
	emit_signal(SNAME("activated"));
}

void GameplayComponent::deactivate() {
	if (!active) {
		return;
	}
	active = false;
	emit_signal(SNAME("deactivated"));
}

bool GameplayComponent::is_active() const {
	return active;
}

void GameplayPawn::_bind_methods() {
	ClassDB::bind_method(D_METHOD("get_controller"), &GameplayPawn::get_controller);
	ClassDB::bind_method(D_METHOD("is_possessed"), &GameplayPawn::is_possessed);
	ClassDB::bind_method(D_METHOD("set_owner_peer_id", "peer_id"), &GameplayPawn::set_owner_peer_id);
	ClassDB::bind_method(D_METHOD("get_owner_peer_id"), &GameplayPawn::get_owner_peer_id);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "owner_peer_id", PROPERTY_HINT_RANGE, "0,2147483647,1"), "set_owner_peer_id", "get_owner_peer_id");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController", PROPERTY_USAGE_NONE), "", "get_controller");

	ADD_SIGNAL(MethodInfo("controller_changed", PropertyInfo(Variant::OBJECT, "old_controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController"), PropertyInfo(Variant::OBJECT, "new_controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController")));
}

void GameplayPawn::_set_controller(GameplayController *p_controller) {
	GameplayController *old_controller = get_controller();
	if (old_controller == p_controller) {
		return;
	}
	controller_id = p_controller ? p_controller->get_instance_id() : ObjectID();
	emit_signal(SNAME("controller_changed"), old_controller, p_controller);
}

GameplayController *GameplayPawn::get_controller() const {
	return _gameplay_object<GameplayController>(controller_id);
}

bool GameplayPawn::is_possessed() const {
	return get_controller() != nullptr;
}

void GameplayPawn::set_owner_peer_id(int p_peer_id) {
	ERR_FAIL_COND_MSG(p_peer_id < 0, "Gameplay owner peer ID cannot be negative.");
	owner_peer_id = p_peer_id;
}

int GameplayPawn::get_owner_peer_id() const {
	return owner_peer_id;
}

GameplayPawn::~GameplayPawn() {
	GameplayController *controller = get_controller();
	if (controller) {
		controller->_pawn_destroyed(this);
	}
}

void GameplayPlayerState::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_user_id", "user_id"), &GameplayPlayerState::set_user_id);
	ClassDB::bind_method(D_METHOD("get_user_id"), &GameplayPlayerState::get_user_id);
	ClassDB::bind_method(D_METHOD("set_session_id", "session_id"), &GameplayPlayerState::set_session_id);
	ClassDB::bind_method(D_METHOD("get_session_id"), &GameplayPlayerState::get_session_id);
	ClassDB::bind_method(D_METHOD("set_peer_id", "peer_id"), &GameplayPlayerState::set_peer_id);
	ClassDB::bind_method(D_METHOD("get_peer_id"), &GameplayPlayerState::get_peer_id);
	ClassDB::bind_method(D_METHOD("activate", "peer_id", "session_id"), &GameplayPlayerState::activate);
	ClassDB::bind_method(D_METHOD("deactivate"), &GameplayPlayerState::deactivate);
	ClassDB::bind_method(D_METHOD("is_active"), &GameplayPlayerState::is_active);
	ClassDB::bind_method(D_METHOD("get_controller"), &GameplayPlayerState::get_controller);
	ClassDB::bind_method(D_METHOD("get_game_state"), &GameplayPlayerState::get_game_state);
	ClassDB::bind_method(D_METHOD("copy_identity_to", "target"), &GameplayPlayerState::copy_identity_to);

	ADD_PROPERTY(PropertyInfo(Variant::STRING, "user_id"), "set_user_id", "get_user_id");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "session_id"), "set_session_id", "get_session_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "peer_id", PROPERTY_HINT_RANGE, "0,2147483647,1"), "set_peer_id", "get_peer_id");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "active", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_active");

	ADD_SIGNAL(MethodInfo("activated", PropertyInfo(Variant::INT, "peer_id"), PropertyInfo(Variant::STRING, "session_id")));
	ADD_SIGNAL(MethodInfo("deactivated", PropertyInfo(Variant::INT, "previous_peer_id")));
	ADD_SIGNAL(MethodInfo("controller_changed", PropertyInfo(Variant::OBJECT, "old_controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController"), PropertyInfo(Variant::OBJECT, "new_controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController")));
}

void GameplayPlayerState::set_user_id(const String &p_user_id) {
	user_id = p_user_id;
}

String GameplayPlayerState::get_user_id() const {
	return user_id;
}

void GameplayPlayerState::set_session_id(const String &p_session_id) {
	session_id = p_session_id;
}

String GameplayPlayerState::get_session_id() const {
	return session_id;
}

void GameplayPlayerState::set_peer_id(int p_peer_id) {
	ERR_FAIL_COND_MSG(p_peer_id < 0, "Peer ID cannot be negative.");
	peer_id = p_peer_id;
}

int GameplayPlayerState::get_peer_id() const {
	return peer_id;
}

void GameplayPlayerState::activate(int p_peer_id, const String &p_session_id) {
	ERR_FAIL_COND_MSG(p_peer_id <= 0, "An active player state requires a positive peer ID.");
	peer_id = p_peer_id;
	session_id = p_session_id;
	active = true;
	emit_signal(SNAME("activated"), peer_id, session_id);
}

void GameplayPlayerState::deactivate() {
	if (!active && peer_id == 0) {
		return;
	}
	const int previous_peer_id = peer_id;
	active = false;
	peer_id = 0;
	emit_signal(SNAME("deactivated"), previous_peer_id);
}

bool GameplayPlayerState::is_active() const {
	return active;
}

void GameplayPlayerState::_set_controller(GameplayController *p_controller) {
	GameplayController *old_controller = get_controller();
	if (old_controller == p_controller) {
		return;
	}
	controller_id = p_controller ? p_controller->get_instance_id() : ObjectID();
	emit_signal(SNAME("controller_changed"), old_controller, p_controller);
}

GameplayController *GameplayPlayerState::get_controller() const {
	return _gameplay_object<GameplayController>(controller_id);
}

void GameplayPlayerState::_set_game_state(GameplayGameState *p_game_state) {
	game_state_id = p_game_state ? p_game_state->get_instance_id() : ObjectID();
}

GameplayGameState *GameplayPlayerState::get_game_state() const {
	return _gameplay_object<GameplayGameState>(game_state_id);
}

void GameplayPlayerState::copy_identity_to(GameplayPlayerState *p_target) const {
	ERR_FAIL_NULL(p_target);
	ERR_FAIL_COND_MSG(p_target == this, "Cannot copy a player state identity to itself.");
	p_target->user_id = user_id;
	p_target->session_id = session_id;
	p_target->peer_id = peer_id;
	p_target->active = active;
}

GameplayPlayerState::~GameplayPlayerState() {
	GameplayController *controller = get_controller();
	if (controller) {
		controller->_player_state_destroyed(this);
	}
	GameplayGameState *game_state = get_game_state();
	if (game_state) {
		game_state->_player_state_destroyed(this);
	}
}

void GameplayController::_bind_methods() {
	ClassDB::bind_method(D_METHOD("possess", "pawn"), &GameplayController::possess);
	ClassDB::bind_method(D_METHOD("unpossess"), &GameplayController::unpossess);
	ClassDB::bind_method(D_METHOD("get_pawn"), &GameplayController::get_pawn);
	ClassDB::bind_method(D_METHOD("has_pawn"), &GameplayController::has_pawn);
	ClassDB::bind_method(D_METHOD("set_player_state", "player_state"), &GameplayController::set_player_state);
	ClassDB::bind_method(D_METHOD("get_player_state"), &GameplayController::get_player_state);
	ClassDB::bind_method(D_METHOD("set_owner_peer_id", "peer_id"), &GameplayController::set_owner_peer_id);
	ClassDB::bind_method(D_METHOD("get_owner_peer_id"), &GameplayController::get_owner_peer_id);
	ClassDB::bind_method(D_METHOD("get_game_mode"), &GameplayController::get_game_mode);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "owner_peer_id", PROPERTY_HINT_RANGE, "0,2147483647,1"), "set_owner_peer_id", "get_owner_peer_id");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState"), "set_player_state", "get_player_state");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "pawn", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPawn", PROPERTY_USAGE_NONE), "", "get_pawn");

	ADD_SIGNAL(MethodInfo("possession_changed", PropertyInfo(Variant::OBJECT, "old_pawn", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPawn"), PropertyInfo(Variant::OBJECT, "new_pawn", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPawn")));
	ADD_SIGNAL(MethodInfo("player_state_changed", PropertyInfo(Variant::OBJECT, "old_player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState"), PropertyInfo(Variant::OBJECT, "new_player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState")));
}

Error GameplayController::possess(GameplayPawn *p_pawn) {
	ERR_FAIL_NULL_V(p_pawn, ERR_INVALID_PARAMETER);
	if (get_pawn() == p_pawn) {
		return OK;
	}

	GameplayController *other_controller = p_pawn->get_controller();
	if (other_controller && other_controller != this) {
		other_controller->unpossess();
	}

	GameplayPawn *old_pawn = get_pawn();
	if (old_pawn) {
		old_pawn->_set_controller(nullptr);
		old_pawn->set_owner_peer_id(0);
	}
	pawn_id = p_pawn->get_instance_id();
	p_pawn->_set_controller(this);
	p_pawn->set_owner_peer_id(owner_peer_id);
	emit_signal(SNAME("possession_changed"), old_pawn, p_pawn);
	return OK;
}

void GameplayController::unpossess() {
	GameplayPawn *old_pawn = get_pawn();
	if (!old_pawn) {
		pawn_id = ObjectID();
		return;
	}
	pawn_id = ObjectID();
	old_pawn->_set_controller(nullptr);
	old_pawn->set_owner_peer_id(0);
	emit_signal(SNAME("possession_changed"), old_pawn, Variant());
}

GameplayPawn *GameplayController::get_pawn() const {
	return _gameplay_object<GameplayPawn>(pawn_id);
}

bool GameplayController::has_pawn() const {
	return get_pawn() != nullptr;
}

void GameplayController::_pawn_destroyed(GameplayPawn *p_pawn) {
	if (get_pawn() != p_pawn) {
		return;
	}
	pawn_id = ObjectID();
	emit_signal(SNAME("possession_changed"), p_pawn, Variant());
}

void GameplayController::set_player_state(GameplayPlayerState *p_player_state) {
	GameplayPlayerState *old_player_state = get_player_state();
	if (old_player_state == p_player_state) {
		return;
	}
	if (p_player_state) {
		GameplayController *other_controller = p_player_state->get_controller();
		if (other_controller && other_controller != this) {
			other_controller->set_player_state(nullptr);
		}
	}
	if (old_player_state) {
		old_player_state->_set_controller(nullptr);
	}
	player_state_id = p_player_state ? p_player_state->get_instance_id() : ObjectID();
	if (p_player_state) {
		p_player_state->_set_controller(this);
	}
	emit_signal(SNAME("player_state_changed"), old_player_state, p_player_state);
}

GameplayPlayerState *GameplayController::get_player_state() const {
	return _gameplay_object<GameplayPlayerState>(player_state_id);
}

void GameplayController::_player_state_destroyed(GameplayPlayerState *p_player_state) {
	if (get_player_state() != p_player_state) {
		return;
	}
	player_state_id = ObjectID();
	emit_signal(SNAME("player_state_changed"), p_player_state, Variant());
}

void GameplayController::set_owner_peer_id(int p_peer_id) {
	ERR_FAIL_COND_MSG(p_peer_id < 0, "Gameplay owner peer ID cannot be negative.");
	owner_peer_id = p_peer_id;
	GameplayPawn *pawn = get_pawn();
	if (pawn) {
		pawn->set_owner_peer_id(owner_peer_id);
	}
}

int GameplayController::get_owner_peer_id() const {
	return owner_peer_id;
}

void GameplayController::_set_game_mode(GameplayGameMode *p_game_mode) {
	game_mode_id = p_game_mode ? p_game_mode->get_instance_id() : ObjectID();
}

GameplayGameMode *GameplayController::get_game_mode() const {
	return _gameplay_object<GameplayGameMode>(game_mode_id);
}

GameplayController::~GameplayController() {
	GameplayGameMode *game_mode = get_game_mode();
	if (game_mode) {
		game_mode->_controller_destroyed(this);
	}
	unpossess();
	set_player_state(nullptr);
}
