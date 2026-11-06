/**************************************************************************/
/*  gameplay_entity.h                                                     */
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

#pragma once

#include "scene/main/node.h"

class GameplayController;
class GameplayGameMode;
class GameplayGameState;

class GameplayComponent : public Node {
	GDCLASS(GameplayComponent, Node);

	StringName component_name;
	ObjectID gameplay_owner_id;
	bool active = false;

protected:
	static void _bind_methods();

public:
	void set_component_name(const StringName &p_name);
	StringName get_component_name() const;

	void set_gameplay_owner(Node *p_owner);
	Node *get_gameplay_owner() const;

	void activate();
	void deactivate();
	bool is_active() const;
};

class GameplayPawn : public Node {
	GDCLASS(GameplayPawn, Node);

	friend class GameplayController;

	ObjectID controller_id;
	int owner_peer_id = 0;

	void _set_controller(GameplayController *p_controller);

protected:
	static void _bind_methods();

public:
	GameplayController *get_controller() const;
	bool is_possessed() const;

	void set_owner_peer_id(int p_peer_id);
	int get_owner_peer_id() const;

	~GameplayPawn();
};

class GameplayPlayerState : public Node {
	GDCLASS(GameplayPlayerState, Node);

	friend class GameplayController;
	friend class GameplayGameState;

	String user_id;
	String session_id;
	int peer_id = 0;
	bool active = false;
	ObjectID controller_id;
	ObjectID game_state_id;

	void _set_controller(GameplayController *p_controller);
	void _set_game_state(GameplayGameState *p_game_state);

protected:
	static void _bind_methods();

public:
	void set_user_id(const String &p_user_id);
	String get_user_id() const;

	void set_session_id(const String &p_session_id);
	String get_session_id() const;

	void set_peer_id(int p_peer_id);
	int get_peer_id() const;

	void activate(int p_peer_id, const String &p_session_id);
	void deactivate();
	bool is_active() const;

	GameplayController *get_controller() const;
	GameplayGameState *get_game_state() const;

	void copy_identity_to(GameplayPlayerState *p_target) const;

	~GameplayPlayerState();
};

class GameplayController : public Node {
	GDCLASS(GameplayController, Node);

	friend class GameplayPawn;
	friend class GameplayPlayerState;
	friend class GameplayGameMode;

	ObjectID pawn_id;
	ObjectID player_state_id;
	ObjectID game_mode_id;
	int owner_peer_id = 0;

	void _pawn_destroyed(GameplayPawn *p_pawn);
	void _player_state_destroyed(GameplayPlayerState *p_player_state);
	void _set_game_mode(GameplayGameMode *p_game_mode);

protected:
	static void _bind_methods();

public:
	Error possess(GameplayPawn *p_pawn);
	void unpossess();
	GameplayPawn *get_pawn() const;
	bool has_pawn() const;

	void set_player_state(GameplayPlayerState *p_player_state);
	GameplayPlayerState *get_player_state() const;

	void set_owner_peer_id(int p_peer_id);
	int get_owner_peer_id() const;

	GameplayGameMode *get_game_mode() const;

	~GameplayController();
};
