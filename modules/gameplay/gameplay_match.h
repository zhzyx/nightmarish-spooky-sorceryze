/**************************************************************************/
/*  gameplay_match.h                                                      */
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

#include "gameplay_entity.h"

#include "core/variant/typed_array.h"

class GameplaySubsystemRegistry;

class GameplayGameState : public Node {
	GDCLASS(GameplayGameState, Node);

	friend class GameplayPlayerState;

	Vector<ObjectID> player_state_ids;
	StringName match_phase;

	void _player_state_destroyed(GameplayPlayerState *p_player_state);

protected:
	static void _bind_methods();

public:
	Error add_player_state(GameplayPlayerState *p_player_state);
	bool remove_player_state(GameplayPlayerState *p_player_state);
	bool has_player_state(GameplayPlayerState *p_player_state) const;
	TypedArray<GameplayPlayerState> get_player_states() const;
	int get_player_count() const;

	void set_match_phase(const StringName &p_phase);
	StringName get_match_phase() const;

	~GameplayGameState();
};

class GameplayGameMode : public Node {
	GDCLASS(GameplayGameMode, Node);

	friend class GameplayController;

	ObjectID game_state_id;
	Vector<ObjectID> controller_ids;
	bool match_running = false;

	void _controller_destroyed(GameplayController *p_controller);
	void _remove_controller(GameplayController *p_controller, bool p_preserve_player_state, bool p_emit_signal);

protected:
	static void _bind_methods();

public:
	bool is_authority_context() const;

	void set_game_state(GameplayGameState *p_game_state);
	GameplayGameState *get_game_state() const;

	Error admit_player(GameplayController *p_controller, GameplayPlayerState *p_player_state);
	Error remove_player(GameplayController *p_controller, bool p_preserve_player_state = false);
	TypedArray<GameplayController> get_controllers() const;
	int get_player_count() const;

	Error start_match();
	Error end_match();
	bool is_match_running() const;

	~GameplayGameMode();
};

class GameplayWorld : public Node {
	GDCLASS(GameplayWorld, Node);

	ObjectID game_mode_id;
	ObjectID game_state_id;
	ObjectID subsystem_registry_id;
	bool initialized = false;

protected:
	static void _bind_methods();
	void _notification(int p_what);

public:
	Error initialize_world(GameplayGameState *p_game_state, GameplayGameMode *p_game_mode = nullptr, GameplaySubsystemRegistry *p_subsystems = nullptr);
	void shutdown_world();
	bool is_initialized() const;

	GameplayGameMode *get_game_mode() const;
	GameplayGameState *get_game_state() const;
	GameplaySubsystemRegistry *get_subsystem_registry() const;

	~GameplayWorld();
};
