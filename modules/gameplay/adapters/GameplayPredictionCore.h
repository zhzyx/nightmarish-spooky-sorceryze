/**************************************************************************/
/*  GameplayPredictionCore.h                                              */
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
/* "Software"), to deal in the Software without restriction, including    */
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

#include "engine_next/include/EngineNext/Gameplay/InterpolationBuffer.h"
#include "engine_next/include/EngineNext/Gameplay/PredictionModel.h"

#include "core/io/resource.h"

class GameplayPredictionInput : public RefCounted
{
	GDCLASS(GameplayPredictionInput, RefCounted);

	EngineNext::Gameplay::PredictionInput stInput;

protected:
	static void _bind_methods();

public:
	void set_sequence(uint64_t p_sequence);
	uint64_t get_sequence() const;
	void set_movement_input(const Vector3 &p_input);
	Vector3 get_movement_input() const;
	void set_step_msec(uint32_t p_step_msec);
	uint32_t get_step_msec() const;
	Dictionary to_dictionary() const;
	const EngineNext::Gameplay::PredictionInput &GetCoreInput() const;
};

class GameplayPredictionState : public RefCounted
{
	GDCLASS(GameplayPredictionState, RefCounted);

	EngineNext::Gameplay::PredictionState stState;

protected:
	static void _bind_methods();

public:
	void set_position(const Vector3 &p_position);
	Vector3 get_position() const;
	void set_velocity(const Vector3 &p_velocity);
	Vector3 get_velocity() const;
	void set_confirmed_sequence(uint64_t p_sequence);
	uint64_t get_confirmed_sequence() const;
	void set_server_time_msec(uint64_t p_time_msec);
	uint64_t get_server_time_msec() const;
	Ref<GameplayPredictionState> duplicate_state() const;
	Dictionary to_dictionary() const;
	EngineNext::Gameplay::PredictionState &GetMutableCoreState();
};

class GameplayPredictionModel : public Resource
{
	GDCLASS(GameplayPredictionModel, Resource);

	EngineNext::Gameplay::PredictionModel stModel;

protected:
	static void _bind_methods();

public:
	void set_max_speed(float p_max_speed);
	float get_max_speed() const;
	void set_fixed_step_msec(uint32_t p_step_msec);
	uint32_t get_fixed_step_msec() const;
	Error simulate(const Ref<GameplayPredictionState> &p_state, const Ref<GameplayPredictionInput> &p_input) const;
	const EngineNext::Gameplay::PredictionModel &GetCoreModel() const;
};

class GameplayInterpolationBuffer : public RefCounted
{
	GDCLASS(GameplayInterpolationBuffer, RefCounted);

	EngineNext::Gameplay::InterpolationBuffer stBuffer;

protected:
	static void _bind_methods();

public:
	void set_max_samples(int p_max_samples);
	int get_max_samples() const;
	void set_interpolation_delay_msec(uint64_t p_delay_msec);
	uint64_t get_interpolation_delay_msec() const;
	void set_stale_after_msec(uint64_t p_stale_after_msec);
	uint64_t get_stale_after_msec() const;
	Error add_sample(const Ref<GameplayPredictionState> &p_state);
	Dictionary sample(uint64_t p_now_msec) const;
	int get_sample_count() const;
	void clear();
};
