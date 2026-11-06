/**************************************************************************/
/*  gameplay_prediction.cpp                                               */
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

#include "gameplay_prediction.h"

#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/object/class_db.h"

static Dictionary _gameplay_vector3_to_dictionary(const Vector3 &p_value) {
	Dictionary result;
	result["x"] = p_value.x;
	result["y"] = p_value.y;
	result["z"] = p_value.z;
	return result;
}

static bool _gameplay_dictionary_to_vector3(const Variant &p_value, Vector3 &r_value) {
	if (p_value.get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary source = p_value;
	if (!source.has("x") || !source.has("y") || !source.has("z")) {
		return false;
	}
	r_value = Vector3(double(source["x"]), double(source["y"]), double(source["z"]));
	return r_value.is_finite();
}

void GameplayPredictionInput::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_sequence", "sequence"), &GameplayPredictionInput::set_sequence);
	ClassDB::bind_method(D_METHOD("get_sequence"), &GameplayPredictionInput::get_sequence);
	ClassDB::bind_method(D_METHOD("set_movement_input", "movement_input"), &GameplayPredictionInput::set_movement_input);
	ClassDB::bind_method(D_METHOD("get_movement_input"), &GameplayPredictionInput::get_movement_input);
	ClassDB::bind_method(D_METHOD("set_step_msec", "step_msec"), &GameplayPredictionInput::set_step_msec);
	ClassDB::bind_method(D_METHOD("get_step_msec"), &GameplayPredictionInput::get_step_msec);
	ClassDB::bind_method(D_METHOD("to_dictionary"), &GameplayPredictionInput::to_dictionary);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "sequence"), "set_sequence", "get_sequence");
	ADD_PROPERTY(PropertyInfo(Variant::VECTOR3, "movement_input"), "set_movement_input", "get_movement_input");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "step_msec", PROPERTY_HINT_RANGE, "1,1000,1"), "set_step_msec", "get_step_msec");
}

void GameplayPredictionInput::set_sequence(uint64_t p_sequence) {
	sequence = p_sequence;
}

uint64_t GameplayPredictionInput::get_sequence() const {
	return sequence;
}

void GameplayPredictionInput::set_movement_input(const Vector3 &p_input) {
	ERR_FAIL_COND_MSG(!p_input.is_finite(), "Prediction input must be finite.");
	movement_input = p_input;
}

Vector3 GameplayPredictionInput::get_movement_input() const {
	return movement_input;
}

void GameplayPredictionInput::set_step_msec(uint32_t p_step_msec) {
	ERR_FAIL_COND_MSG(p_step_msec == 0 || p_step_msec > 1000, "Prediction step must be between 1 and 1000 milliseconds.");
	step_msec = p_step_msec;
}

uint32_t GameplayPredictionInput::get_step_msec() const {
	return step_msec;
}

Dictionary GameplayPredictionInput::to_dictionary() const {
	Dictionary result;
	result["sequence"] = sequence;
	result["input"] = _gameplay_vector3_to_dictionary(movement_input);
	result["step_msec"] = step_msec;
	return result;
}

void GameplayPredictionState::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_position", "position"), &GameplayPredictionState::set_position);
	ClassDB::bind_method(D_METHOD("get_position"), &GameplayPredictionState::get_position);
	ClassDB::bind_method(D_METHOD("set_velocity", "velocity"), &GameplayPredictionState::set_velocity);
	ClassDB::bind_method(D_METHOD("get_velocity"), &GameplayPredictionState::get_velocity);
	ClassDB::bind_method(D_METHOD("set_confirmed_sequence", "sequence"), &GameplayPredictionState::set_confirmed_sequence);
	ClassDB::bind_method(D_METHOD("get_confirmed_sequence"), &GameplayPredictionState::get_confirmed_sequence);
	ClassDB::bind_method(D_METHOD("set_server_time_msec", "time_msec"), &GameplayPredictionState::set_server_time_msec);
	ClassDB::bind_method(D_METHOD("get_server_time_msec"), &GameplayPredictionState::get_server_time_msec);
	ClassDB::bind_method(D_METHOD("duplicate_state"), &GameplayPredictionState::duplicate_state);
	ClassDB::bind_method(D_METHOD("to_dictionary"), &GameplayPredictionState::to_dictionary);

	ADD_PROPERTY(PropertyInfo(Variant::VECTOR3, "position"), "set_position", "get_position");
	ADD_PROPERTY(PropertyInfo(Variant::VECTOR3, "velocity"), "set_velocity", "get_velocity");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "confirmed_sequence"), "set_confirmed_sequence", "get_confirmed_sequence");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "server_time_msec"), "set_server_time_msec", "get_server_time_msec");
}

void GameplayPredictionState::set_position(const Vector3 &p_position) {
	ERR_FAIL_COND_MSG(!p_position.is_finite(), "Prediction position must be finite.");
	position = p_position;
}

Vector3 GameplayPredictionState::get_position() const {
	return position;
}

void GameplayPredictionState::set_velocity(const Vector3 &p_velocity) {
	ERR_FAIL_COND_MSG(!p_velocity.is_finite(), "Prediction velocity must be finite.");
	velocity = p_velocity;
}

Vector3 GameplayPredictionState::get_velocity() const {
	return velocity;
}

void GameplayPredictionState::set_confirmed_sequence(uint64_t p_sequence) {
	confirmed_sequence = p_sequence;
}

uint64_t GameplayPredictionState::get_confirmed_sequence() const {
	return confirmed_sequence;
}

void GameplayPredictionState::set_server_time_msec(uint64_t p_time_msec) {
	server_time_msec = p_time_msec;
}

uint64_t GameplayPredictionState::get_server_time_msec() const {
	return server_time_msec;
}

Ref<GameplayPredictionState> GameplayPredictionState::duplicate_state() const {
	Ref<GameplayPredictionState> result;
	result.instantiate();
	result->position = position;
	result->velocity = velocity;
	result->confirmed_sequence = confirmed_sequence;
	result->server_time_msec = server_time_msec;
	return result;
}

Dictionary GameplayPredictionState::to_dictionary() const {
	Dictionary result;
	result["position"] = _gameplay_vector3_to_dictionary(position);
	result["velocity"] = _gameplay_vector3_to_dictionary(velocity);
	result["confirmed_sequence"] = confirmed_sequence;
	result["server_time_msec"] = server_time_msec;
	return result;
}

void GameplayPredictionModel::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_max_speed", "max_speed"), &GameplayPredictionModel::set_max_speed);
	ClassDB::bind_method(D_METHOD("get_max_speed"), &GameplayPredictionModel::get_max_speed);
	ClassDB::bind_method(D_METHOD("set_fixed_step_msec", "step_msec"), &GameplayPredictionModel::set_fixed_step_msec);
	ClassDB::bind_method(D_METHOD("get_fixed_step_msec"), &GameplayPredictionModel::get_fixed_step_msec);
	ClassDB::bind_method(D_METHOD("simulate", "state", "input"), &GameplayPredictionModel::simulate);

	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "max_speed", PROPERTY_HINT_RANGE, "0.001,100000,0.001,or_greater"), "set_max_speed", "get_max_speed");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "fixed_step_msec", PROPERTY_HINT_RANGE, "1,1000,1"), "set_fixed_step_msec", "get_fixed_step_msec");
}

void GameplayPredictionModel::set_max_speed(float p_max_speed) {
	ERR_FAIL_COND_MSG(!Math::is_finite(p_max_speed) || p_max_speed <= 0.0f, "Maximum speed must be finite and positive.");
	max_speed = p_max_speed;
}

float GameplayPredictionModel::get_max_speed() const {
	return max_speed;
}

void GameplayPredictionModel::set_fixed_step_msec(uint32_t p_step_msec) {
	ERR_FAIL_COND_MSG(p_step_msec == 0 || p_step_msec > 1000, "Fixed prediction step must be between 1 and 1000 milliseconds.");
	fixed_step_msec = p_step_msec;
}

uint32_t GameplayPredictionModel::get_fixed_step_msec() const {
	return fixed_step_msec;
}

Error GameplayPredictionModel::simulate(const Ref<GameplayPredictionState> &p_state, const Ref<GameplayPredictionInput> &p_input) const {
	ERR_FAIL_COND_V(p_state.is_null() || p_input.is_null(), ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(p_input->get_sequence() == 0 || p_input->get_step_msec() != fixed_step_msec, ERR_INVALID_PARAMETER);
	Vector3 movement = p_input->get_movement_input();
	ERR_FAIL_COND_V(!movement.is_finite() || movement.length_squared() > 1.000001f, ERR_INVALID_PARAMETER);
	const Vector3 velocity = movement * max_speed;
	p_state->set_velocity(velocity);
	p_state->set_position(p_state->get_position() + velocity * (double(fixed_step_msec) / 1000.0));
	p_state->set_confirmed_sequence(p_input->get_sequence());
	return OK;
}

GameplayClientPrediction::GameplayClientPrediction() {
	model.instantiate();
	predicted_state.instantiate();
}

void GameplayClientPrediction::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_model", "model"), &GameplayClientPrediction::set_model);
	ClassDB::bind_method(D_METHOD("get_model"), &GameplayClientPrediction::get_model);
	ClassDB::bind_method(D_METHOD("set_initial_state", "state"), &GameplayClientPrediction::set_initial_state);
	ClassDB::bind_method(D_METHOD("get_predicted_state"), &GameplayClientPrediction::get_predicted_state);
	ClassDB::bind_method(D_METHOD("set_max_history", "max_history"), &GameplayClientPrediction::set_max_history);
	ClassDB::bind_method(D_METHOD("get_max_history"), &GameplayClientPrediction::get_max_history);
	ClassDB::bind_method(D_METHOD("set_max_inputs_per_second", "max_inputs"), &GameplayClientPrediction::set_max_inputs_per_second);
	ClassDB::bind_method(D_METHOD("get_max_inputs_per_second"), &GameplayClientPrediction::get_max_inputs_per_second);
	ClassDB::bind_method(D_METHOD("set_correction_threshold", "threshold"), &GameplayClientPrediction::set_correction_threshold);
	ClassDB::bind_method(D_METHOD("get_correction_threshold"), &GameplayClientPrediction::get_correction_threshold);
	ClassDB::bind_method(D_METHOD("predict_input", "movement_input", "now_msec"), &GameplayClientPrediction::predict_input);
	ClassDB::bind_method(D_METHOD("apply_authoritative_state", "state"), &GameplayClientPrediction::apply_authoritative_state);
	ClassDB::bind_method(D_METHOD("get_unconfirmed_inputs"), &GameplayClientPrediction::get_unconfirmed_inputs);
	ClassDB::bind_method(D_METHOD("get_unconfirmed_input_count"), &GameplayClientPrediction::get_unconfirmed_input_count);
	ClassDB::bind_method(D_METHOD("get_last_confirmed_sequence"), &GameplayClientPrediction::get_last_confirmed_sequence);
	ClassDB::bind_method(D_METHOD("get_correction_count"), &GameplayClientPrediction::get_correction_count);
	ClassDB::bind_method(D_METHOD("get_last_replayed_input_count"), &GameplayClientPrediction::get_last_replayed_input_count);
	ClassDB::bind_method(D_METHOD("get_last_rejection_reason"), &GameplayClientPrediction::get_last_rejection_reason);
	ClassDB::bind_method(D_METHOD("clear"), &GameplayClientPrediction::clear);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_history", PROPERTY_HINT_RANGE, "1,4096,1"), "set_max_history", "get_max_history");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_inputs_per_second", PROPERTY_HINT_RANGE, "1,1000,1"), "set_max_inputs_per_second", "get_max_inputs_per_second");
	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "correction_threshold", PROPERTY_HINT_RANGE, "0,1000,0.0001,or_greater"), "set_correction_threshold", "get_correction_threshold");
}

void GameplayClientPrediction::set_model(const Ref<GameplayPredictionModel> &p_model) {
	ERR_FAIL_COND(p_model.is_null());
	model = p_model;
}

Ref<GameplayPredictionModel> GameplayClientPrediction::get_model() const {
	return model;
}

void GameplayClientPrediction::set_initial_state(const Ref<GameplayPredictionState> &p_state) {
	ERR_FAIL_COND(p_state.is_null() || !p_state->get_position().is_finite() || !p_state->get_velocity().is_finite());
	predicted_state = p_state->duplicate_state();
	history.clear();
	last_confirmed_sequence = p_state->get_confirmed_sequence();
	next_sequence = last_confirmed_sequence + 1;
	last_replayed_input_count = 0;
}

Ref<GameplayPredictionState> GameplayClientPrediction::get_predicted_state() const {
	return predicted_state;
}

void GameplayClientPrediction::set_max_history(int p_max_history) {
	ERR_FAIL_COND_MSG(p_max_history < 1 || p_max_history > 4096 || p_max_history < history.size(), "The history limit cannot discard unconfirmed inputs.");
	max_history = p_max_history;
}

int GameplayClientPrediction::get_max_history() const {
	return max_history;
}

void GameplayClientPrediction::set_max_inputs_per_second(int p_max_inputs) {
	ERR_FAIL_COND(p_max_inputs < 1 || p_max_inputs > 1000);
	max_inputs_per_second = p_max_inputs;
}

int GameplayClientPrediction::get_max_inputs_per_second() const {
	return max_inputs_per_second;
}

void GameplayClientPrediction::set_correction_threshold(float p_threshold) {
	ERR_FAIL_COND(!Math::is_finite(p_threshold) || p_threshold < 0.0f);
	correction_threshold = p_threshold;
}

float GameplayClientPrediction::get_correction_threshold() const {
	return correction_threshold;
}

Ref<GameplayPredictionInput> GameplayClientPrediction::predict_input(const Vector3 &p_input, uint64_t p_now_msec) {
	last_rejection_reason.clear();
	if (!p_input.is_finite() || p_input.length_squared() > 1.000001f) {
		last_rejection_reason = "invalid_movement_input";
		return Ref<GameplayPredictionInput>();
	}
	if (history.size() >= max_history) {
		last_rejection_reason = "history_limit_reached";
		return Ref<GameplayPredictionInput>();
	}
	if (rate_window_started_msec == 0 || p_now_msec < rate_window_started_msec || p_now_msec - rate_window_started_msec >= 1000) {
		rate_window_started_msec = p_now_msec;
		inputs_in_rate_window = 0;
	}
	if (inputs_in_rate_window >= max_inputs_per_second) {
		last_rejection_reason = "input_rate_limit";
		return Ref<GameplayPredictionInput>();
	}
	Ref<GameplayPredictionInput> input;
	input.instantiate();
	input->set_sequence(next_sequence++);
	input->set_movement_input(p_input);
	input->set_step_msec(model->get_fixed_step_msec());
	if (model->simulate(predicted_state, input) != OK) {
		last_rejection_reason = "simulation_rejected";
		return Ref<GameplayPredictionInput>();
	}
	HistoryEntry entry;
	entry.input = input;
	entry.predicted_state = predicted_state->duplicate_state();
	history.push_back(entry);
	inputs_in_rate_window++;
	return input;
}

Dictionary GameplayClientPrediction::apply_authoritative_state(const Ref<GameplayPredictionState> &p_state) {
	Dictionary result;
	result["accepted"] = false;
	last_replayed_input_count = 0;
	if (p_state.is_null() || !p_state->get_position().is_finite() || !p_state->get_velocity().is_finite()) {
		last_rejection_reason = "invalid_authoritative_state";
		result["reason"] = last_rejection_reason;
		return result;
	}
	const uint64_t confirmed = p_state->get_confirmed_sequence();
	if (confirmed < last_confirmed_sequence) {
		last_rejection_reason = "stale_authoritative_state";
		result["reason"] = last_rejection_reason;
		return result;
	}
	if (confirmed >= next_sequence) {
		history.clear();
		predicted_state = p_state->duplicate_state();
		last_confirmed_sequence = confirmed;
		next_sequence = confirmed + 1;
		last_rejection_reason.clear();
		result["accepted"] = true;
		result["position_error"] = 0.0f;
		result["corrected"] = false;
		result["resynchronized"] = true;
		result["replayed_input_count"] = 0;
		result["remaining_input_count"] = 0;
		return result;
	}
	float error = predicted_state->get_position().distance_to(p_state->get_position());
	for (const HistoryEntry &entry : history) {
		if (entry.input->get_sequence() == confirmed) {
			error = entry.predicted_state->get_position().distance_to(p_state->get_position());
			break;
		}
	}
	while (!history.is_empty() && history[0].input->get_sequence() <= confirmed) {
		history.remove_at(0);
	}
	predicted_state = p_state->duplicate_state();
	for (HistoryEntry &entry : history) {
		model->simulate(predicted_state, entry.input);
		entry.predicted_state = predicted_state->duplicate_state();
		last_replayed_input_count++;
	}
	last_confirmed_sequence = confirmed;
	if (error > correction_threshold) {
		correction_count++;
	}
	last_rejection_reason.clear();
	result["accepted"] = true;
	result["position_error"] = error;
	result["corrected"] = error > correction_threshold;
	result["replayed_input_count"] = last_replayed_input_count;
	result["remaining_input_count"] = history.size();
	return result;
}

Array GameplayClientPrediction::get_unconfirmed_inputs() const {
	Array result;
	for (const HistoryEntry &entry : history) {
		result.push_back(entry.input);
	}
	return result;
}

int GameplayClientPrediction::get_unconfirmed_input_count() const {
	return history.size();
}

uint64_t GameplayClientPrediction::get_last_confirmed_sequence() const {
	return last_confirmed_sequence;
}

int GameplayClientPrediction::get_correction_count() const {
	return correction_count;
}

int GameplayClientPrediction::get_last_replayed_input_count() const {
	return last_replayed_input_count;
}

String GameplayClientPrediction::get_last_rejection_reason() const {
	return last_rejection_reason;
}

void GameplayClientPrediction::clear() {
	history.clear();
	predicted_state.instantiate();
	next_sequence = 1;
	last_confirmed_sequence = 0;
	rate_window_started_msec = 0;
	inputs_in_rate_window = 0;
	correction_count = 0;
	last_replayed_input_count = 0;
	last_rejection_reason.clear();
}

void GameplayServerPrediction::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_max_sequence_gap", "gap"), &GameplayServerPrediction::set_max_sequence_gap);
	ClassDB::bind_method(D_METHOD("get_max_sequence_gap"), &GameplayServerPrediction::get_max_sequence_gap);
	ClassDB::bind_method(D_METHOD("set_max_inputs_per_second", "max_inputs"), &GameplayServerPrediction::set_max_inputs_per_second);
	ClassDB::bind_method(D_METHOD("get_max_inputs_per_second"), &GameplayServerPrediction::get_max_inputs_per_second);
	ClassDB::bind_method(D_METHOD("register_object", "object_id", "owner_peer_id", "model", "initial_state"), &GameplayServerPrediction::register_object, DEFVAL(Ref<GameplayPredictionState>()));
	ClassDB::bind_method(D_METHOD("unregister_object", "object_id"), &GameplayServerPrediction::unregister_object);
	ClassDB::bind_method(D_METHOD("set_object_owner_peer_id", "object_id", "owner_peer_id"), &GameplayServerPrediction::set_object_owner_peer_id);
	ClassDB::bind_method(D_METHOD("get_object_owner_peer_id", "object_id"), &GameplayServerPrediction::get_object_owner_peer_id);
	ClassDB::bind_method(D_METHOD("get_object_state", "object_id"), &GameplayServerPrediction::get_object_state);
	ClassDB::bind_method(D_METHOD("consume_input", "transport_sender_peer_id", "object_id", "input", "now_msec"), &GameplayServerPrediction::consume_input);
	ClassDB::bind_method(D_METHOD("get_last_rejection_reason"), &GameplayServerPrediction::get_last_rejection_reason);
	ClassDB::bind_method(D_METHOD("get_rejected_input_count"), &GameplayServerPrediction::get_rejected_input_count);
	ClassDB::bind_method(D_METHOD("clear"), &GameplayServerPrediction::clear);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_sequence_gap", PROPERTY_HINT_RANGE, "1,4096,1"), "set_max_sequence_gap", "get_max_sequence_gap");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_inputs_per_second", PROPERTY_HINT_RANGE, "1,1000,1"), "set_max_inputs_per_second", "get_max_inputs_per_second");
}

Dictionary GameplayServerPrediction::_reject(const String &p_reason) {
	last_rejection_reason = p_reason;
	rejected_input_count++;
	Dictionary result;
	result["accepted"] = false;
	result["reason"] = p_reason;
	return result;
}

void GameplayServerPrediction::set_max_sequence_gap(int p_gap) {
	ERR_FAIL_COND(p_gap < 1 || p_gap > 4096);
	max_sequence_gap = p_gap;
}

int GameplayServerPrediction::get_max_sequence_gap() const {
	return max_sequence_gap;
}

void GameplayServerPrediction::set_max_inputs_per_second(int p_max_inputs) {
	ERR_FAIL_COND(p_max_inputs < 1 || p_max_inputs > 1000);
	max_inputs_per_second = p_max_inputs;
}

int GameplayServerPrediction::get_max_inputs_per_second() const {
	return max_inputs_per_second;
}

Error GameplayServerPrediction::register_object(int p_object_id, int p_owner_peer_id, const Ref<GameplayPredictionModel> &p_model, const Ref<GameplayPredictionState> &p_initial_state) {
	ERR_FAIL_COND_V(p_object_id <= 0 || p_owner_peer_id <= 1 || p_model.is_null() || objects.has(p_object_id), ERR_INVALID_PARAMETER);
	ObjectRuntime runtime;
	runtime.owner_peer_id = p_owner_peer_id;
	runtime.model = p_model;
	if (p_initial_state.is_valid()) {
		runtime.state = p_initial_state->duplicate_state();
	} else {
		runtime.state.instantiate();
	}
	objects.insert(p_object_id, runtime);
	return OK;
}

bool GameplayServerPrediction::unregister_object(int p_object_id) {
	return objects.erase(p_object_id);
}

Error GameplayServerPrediction::set_object_owner_peer_id(int p_object_id, int p_owner_peer_id) {
	ObjectRuntime *runtime = objects.getptr(p_object_id);
	ERR_FAIL_COND_V(!runtime || p_owner_peer_id <= 1, ERR_INVALID_PARAMETER);
	runtime->owner_peer_id = p_owner_peer_id;
	return OK;
}

int GameplayServerPrediction::get_object_owner_peer_id(int p_object_id) const {
	const ObjectRuntime *runtime = objects.getptr(p_object_id);
	return runtime ? runtime->owner_peer_id : 0;
}

Ref<GameplayPredictionState> GameplayServerPrediction::get_object_state(int p_object_id) const {
	const ObjectRuntime *runtime = objects.getptr(p_object_id);
	return runtime ? runtime->state : Ref<GameplayPredictionState>();
}

Dictionary GameplayServerPrediction::consume_input(int p_transport_sender_peer_id, int p_object_id, const Ref<GameplayPredictionInput> &p_input, uint64_t p_now_msec) {
	ObjectRuntime *runtime = objects.getptr(p_object_id);
	if (!runtime) {
		return _reject("unknown_object");
	}
	if (p_transport_sender_peer_id != runtime->owner_peer_id) {
		return _reject("gameplay_owner_mismatch");
	}
	if (p_input.is_null() || p_input->get_sequence() == 0 || p_input->get_step_msec() != runtime->model->get_fixed_step_msec() || !p_input->get_movement_input().is_finite() || p_input->get_movement_input().length_squared() > 1.000001f) {
		return _reject("invalid_input_command");
	}
	const uint64_t last_sequence = runtime->state->get_confirmed_sequence();
	if (p_input->get_sequence() == last_sequence) {
		return _reject("duplicate_sequence");
	}
	if (p_input->get_sequence() < last_sequence) {
		return _reject("sequence_too_old");
	}
	if (p_input->get_sequence() > last_sequence + uint64_t(max_sequence_gap)) {
		return _reject("sequence_gap_too_large");
	}
	if (runtime->rate_window_started_msec == 0 || p_now_msec < runtime->rate_window_started_msec || p_now_msec - runtime->rate_window_started_msec >= 1000) {
		runtime->rate_window_started_msec = p_now_msec;
		runtime->inputs_in_rate_window = 0;
	}
	if (runtime->inputs_in_rate_window >= max_inputs_per_second) {
		return _reject("input_rate_limit");
	}
	const Error simulation_error = runtime->model->simulate(runtime->state, p_input);
	if (simulation_error != OK) {
		return _reject("simulation_rejected");
	}
	runtime->inputs_in_rate_window++;
	runtime->state->set_server_time_msec(p_now_msec);
	last_rejection_reason.clear();
	Dictionary result;
	result["accepted"] = true;
	result["state"] = runtime->state->duplicate_state();
	return result;
}

String GameplayServerPrediction::get_last_rejection_reason() const {
	return last_rejection_reason;
}

int GameplayServerPrediction::get_rejected_input_count() const {
	return rejected_input_count;
}

void GameplayServerPrediction::clear() {
	objects.clear();
	last_rejection_reason.clear();
	rejected_input_count = 0;
}

void GameplayInterpolationBuffer::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_max_samples", "max_samples"), &GameplayInterpolationBuffer::set_max_samples);
	ClassDB::bind_method(D_METHOD("get_max_samples"), &GameplayInterpolationBuffer::get_max_samples);
	ClassDB::bind_method(D_METHOD("set_interpolation_delay_msec", "delay_msec"), &GameplayInterpolationBuffer::set_interpolation_delay_msec);
	ClassDB::bind_method(D_METHOD("get_interpolation_delay_msec"), &GameplayInterpolationBuffer::get_interpolation_delay_msec);
	ClassDB::bind_method(D_METHOD("set_stale_after_msec", "stale_after_msec"), &GameplayInterpolationBuffer::set_stale_after_msec);
	ClassDB::bind_method(D_METHOD("get_stale_after_msec"), &GameplayInterpolationBuffer::get_stale_after_msec);
	ClassDB::bind_method(D_METHOD("add_sample", "state"), &GameplayInterpolationBuffer::add_sample);
	ClassDB::bind_method(D_METHOD("sample", "now_msec"), &GameplayInterpolationBuffer::sample);
	ClassDB::bind_method(D_METHOD("get_sample_count"), &GameplayInterpolationBuffer::get_sample_count);
	ClassDB::bind_method(D_METHOD("clear"), &GameplayInterpolationBuffer::clear);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_samples", PROPERTY_HINT_RANGE, "2,4096,1"), "set_max_samples", "get_max_samples");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "interpolation_delay_msec", PROPERTY_HINT_RANGE, "0,60000,1"), "set_interpolation_delay_msec", "get_interpolation_delay_msec");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "stale_after_msec", PROPERTY_HINT_RANGE, "1,60000,1"), "set_stale_after_msec", "get_stale_after_msec");
}

void GameplayInterpolationBuffer::set_max_samples(int p_max_samples) {
	ERR_FAIL_COND(p_max_samples < 2 || p_max_samples > 4096);
	max_samples = p_max_samples;
	while (samples.size() > max_samples) {
		samples.remove_at(0);
	}
}

int GameplayInterpolationBuffer::get_max_samples() const {
	return max_samples;
}

void GameplayInterpolationBuffer::set_interpolation_delay_msec(uint64_t p_delay_msec) {
	ERR_FAIL_COND(p_delay_msec > 60000);
	interpolation_delay_msec = p_delay_msec;
}

uint64_t GameplayInterpolationBuffer::get_interpolation_delay_msec() const {
	return interpolation_delay_msec;
}

void GameplayInterpolationBuffer::set_stale_after_msec(uint64_t p_stale_after_msec) {
	ERR_FAIL_COND(p_stale_after_msec == 0 || p_stale_after_msec > 60000);
	stale_after_msec = p_stale_after_msec;
}

uint64_t GameplayInterpolationBuffer::get_stale_after_msec() const {
	return stale_after_msec;
}

Error GameplayInterpolationBuffer::add_sample(const Ref<GameplayPredictionState> &p_state) {
	ERR_FAIL_COND_V(p_state.is_null() || !p_state->get_position().is_finite() || !p_state->get_velocity().is_finite(), ERR_INVALID_PARAMETER);
	const uint64_t sample_time = p_state->get_server_time_msec();
	int insert_at = samples.size();
	for (int i = 0; i < samples.size(); i++) {
		const uint64_t existing_time = samples[i]->get_server_time_msec();
		if (existing_time == sample_time) {
			if (p_state->get_confirmed_sequence() <= samples[i]->get_confirmed_sequence()) {
				return ERR_ALREADY_EXISTS;
			}
			samples.write[i] = p_state->duplicate_state();
			return OK;
		}
		if (sample_time < existing_time) {
			insert_at = i;
			break;
		}
	}
	samples.insert(insert_at, p_state->duplicate_state());
	while (samples.size() > max_samples) {
		samples.remove_at(0);
	}
	return OK;
}

Dictionary GameplayInterpolationBuffer::sample(uint64_t p_now_msec) const {
	Dictionary result;
	if (samples.is_empty()) {
		result["status"] = "empty";
		return result;
	}
	const uint64_t target_time = p_now_msec > interpolation_delay_msec ? p_now_msec - interpolation_delay_msec : 0;
	if (samples.size() == 1 || target_time <= samples[0]->get_server_time_msec()) {
		result["status"] = samples.size() == 1 ? "single_sample" : "before_range";
		result["state"] = samples[0]->duplicate_state();
		return result;
	}
	for (int i = 1; i < samples.size(); i++) {
		const Ref<GameplayPredictionState> &previous = samples[i - 1];
		const Ref<GameplayPredictionState> &next = samples[i];
		if (target_time <= next->get_server_time_msec()) {
			const uint64_t span = next->get_server_time_msec() - previous->get_server_time_msec();
			const float weight = span == 0 ? 1.0f : float(target_time - previous->get_server_time_msec()) / float(span);
			Ref<GameplayPredictionState> interpolated;
			interpolated.instantiate();
			interpolated->set_position(previous->get_position().lerp(next->get_position(), weight));
			interpolated->set_velocity(previous->get_velocity().lerp(next->get_velocity(), weight));
			interpolated->set_confirmed_sequence(next->get_confirmed_sequence());
			interpolated->set_server_time_msec(target_time);
			result["status"] = "interpolated";
			result["state"] = interpolated;
			return result;
		}
	}
	const Ref<GameplayPredictionState> latest = samples[samples.size() - 1];
	result["status"] = p_now_msec > latest->get_server_time_msec() && p_now_msec - latest->get_server_time_msec() > stale_after_msec ? "stale_held" : "held";
	result["state"] = latest->duplicate_state();
	return result;
}

int GameplayInterpolationBuffer::get_sample_count() const {
	return samples.size();
}

void GameplayInterpolationBuffer::clear() {
	samples.clear();
}

void GameplayNetworkSimulator::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_latency_msec", "latency_msec"), &GameplayNetworkSimulator::set_latency_msec);
	ClassDB::bind_method(D_METHOD("get_latency_msec"), &GameplayNetworkSimulator::get_latency_msec);
	ClassDB::bind_method(D_METHOD("set_jitter_msec", "jitter_msec"), &GameplayNetworkSimulator::set_jitter_msec);
	ClassDB::bind_method(D_METHOD("get_jitter_msec"), &GameplayNetworkSimulator::get_jitter_msec);
	ClassDB::bind_method(D_METHOD("set_loss_permyriad", "loss_permyriad"), &GameplayNetworkSimulator::set_loss_permyriad);
	ClassDB::bind_method(D_METHOD("get_loss_permyriad"), &GameplayNetworkSimulator::get_loss_permyriad);
	ClassDB::bind_method(D_METHOD("set_max_queued_packets", "max_packets"), &GameplayNetworkSimulator::set_max_queued_packets);
	ClassDB::bind_method(D_METHOD("get_max_queued_packets"), &GameplayNetworkSimulator::get_max_queued_packets);
	ClassDB::bind_method(D_METHOD("set_seed", "seed"), &GameplayNetworkSimulator::set_seed);
	ClassDB::bind_method(D_METHOD("get_seed"), &GameplayNetworkSimulator::get_seed);
	ClassDB::bind_method(D_METHOD("enqueue", "target_peer_id", "message", "now_msec"), &GameplayNetworkSimulator::enqueue);
	ClassDB::bind_method(D_METHOD("drain", "now_msec"), &GameplayNetworkSimulator::drain);
	ClassDB::bind_method(D_METHOD("discard_target", "target_peer_id"), &GameplayNetworkSimulator::discard_target);
	ClassDB::bind_method(D_METHOD("get_queued_packet_count"), &GameplayNetworkSimulator::get_queued_packet_count);
	ClassDB::bind_method(D_METHOD("get_dropped_packet_count"), &GameplayNetworkSimulator::get_dropped_packet_count);
	ClassDB::bind_method(D_METHOD("get_overflow_packet_count"), &GameplayNetworkSimulator::get_overflow_packet_count);
	ClassDB::bind_method(D_METHOD("clear"), &GameplayNetworkSimulator::clear);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "latency_msec", PROPERTY_HINT_RANGE, "0,60000,1"), "set_latency_msec", "get_latency_msec");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "jitter_msec", PROPERTY_HINT_RANGE, "0,60000,1"), "set_jitter_msec", "get_jitter_msec");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "loss_permyriad", PROPERTY_HINT_RANGE, "0,10000,1"), "set_loss_permyriad", "get_loss_permyriad");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_queued_packets", PROPERTY_HINT_RANGE, "1,65536,1"), "set_max_queued_packets", "get_max_queued_packets");
}

uint64_t GameplayNetworkSimulator::_next_random() {
	random_state ^= random_state << 13;
	random_state ^= random_state >> 7;
	random_state ^= random_state << 17;
	return random_state;
}

void GameplayNetworkSimulator::set_latency_msec(uint64_t p_latency_msec) {
	ERR_FAIL_COND(p_latency_msec > 60000);
	latency_msec = p_latency_msec;
}

uint64_t GameplayNetworkSimulator::get_latency_msec() const {
	return latency_msec;
}

void GameplayNetworkSimulator::set_jitter_msec(uint64_t p_jitter_msec) {
	ERR_FAIL_COND(p_jitter_msec > 60000);
	jitter_msec = p_jitter_msec;
}

uint64_t GameplayNetworkSimulator::get_jitter_msec() const {
	return jitter_msec;
}

void GameplayNetworkSimulator::set_loss_permyriad(int p_loss_permyriad) {
	ERR_FAIL_COND(p_loss_permyriad < 0 || p_loss_permyriad > 10000);
	loss_permyriad = p_loss_permyriad;
}

int GameplayNetworkSimulator::get_loss_permyriad() const {
	return loss_permyriad;
}

void GameplayNetworkSimulator::set_max_queued_packets(int p_max_packets) {
	ERR_FAIL_COND(p_max_packets < 1 || p_max_packets > 65536);
	max_queued_packets = p_max_packets;
	while (queue.size() > max_queued_packets) {
		queue.remove_at(queue.size() - 1);
		overflow_packet_count++;
	}
}

int GameplayNetworkSimulator::get_max_queued_packets() const {
	return max_queued_packets;
}

void GameplayNetworkSimulator::set_seed(uint64_t p_seed) {
	random_state = p_seed == 0 ? 1 : p_seed;
}

uint64_t GameplayNetworkSimulator::get_seed() const {
	return random_state;
}

Dictionary GameplayNetworkSimulator::enqueue(int p_target_peer_id, const Dictionary &p_message, uint64_t p_now_msec) {
	Dictionary result;
	if (p_target_peer_id == 0 || p_message.is_empty()) {
		result["queued"] = false;
		result["reason"] = "invalid_packet";
		return result;
	}
	if (loss_permyriad > 0 && int(_next_random() % 10000) < loss_permyriad) {
		dropped_packet_count++;
		result["queued"] = false;
		result["reason"] = "simulated_loss";
		return result;
	}
	if (queue.size() >= max_queued_packets) {
		overflow_packet_count++;
		result["queued"] = false;
		result["reason"] = "queue_limit";
		return result;
	}
	int64_t jitter = 0;
	if (jitter_msec > 0) {
		jitter = int64_t(_next_random() % (jitter_msec * 2 + 1)) - int64_t(jitter_msec);
	}
	const int64_t delay = MAX<int64_t>(0, int64_t(latency_msec) + jitter);
	QueuedPacket packet;
	packet.target_peer_id = p_target_peer_id;
	packet.message = p_message.duplicate(true);
	packet.delivery_time_msec = p_now_msec + uint64_t(delay);
	int insert_at = queue.size();
	for (int i = 0; i < queue.size(); i++) {
		if (packet.delivery_time_msec < queue[i].delivery_time_msec) {
			insert_at = i;
			break;
		}
	}
	queue.insert(insert_at, packet);
	result["queued"] = true;
	result["delivery_time_msec"] = packet.delivery_time_msec;
	return result;
}

Array GameplayNetworkSimulator::drain(uint64_t p_now_msec) {
	Array result;
	for (int i = 0; i < queue.size();) {
		if (queue[i].delivery_time_msec > p_now_msec) {
			i++;
			continue;
		}
		Dictionary packet;
		packet["target_peer_id"] = queue[i].target_peer_id;
		packet["message"] = queue[i].message;
		packet["delivery_time_msec"] = queue[i].delivery_time_msec;
		result.push_back(packet);
		queue.remove_at(i);
	}
	return result;
}

int GameplayNetworkSimulator::discard_target(int p_target_peer_id) {
	int discarded = 0;
	for (int i = queue.size() - 1; i >= 0; i--) {
		if (queue[i].target_peer_id == p_target_peer_id) {
			queue.remove_at(i);
			discarded++;
		}
	}
	return discarded;
}

int GameplayNetworkSimulator::get_queued_packet_count() const {
	return queue.size();
}

uint64_t GameplayNetworkSimulator::get_dropped_packet_count() const {
	return dropped_packet_count;
}

uint64_t GameplayNetworkSimulator::get_overflow_packet_count() const {
	return overflow_packet_count;
}

void GameplayNetworkSimulator::clear() {
	queue.clear();
	dropped_packet_count = 0;
	overflow_packet_count = 0;
}

GameplayNetworkPrediction::GameplayNetworkPrediction() {
	authority.instantiate();
	network_simulator.instantiate();
}

void GameplayNetworkPrediction::_bind_methods() {
	ClassDB::bind_method(D_METHOD("configure_server", "peer", "session_manager"), &GameplayNetworkPrediction::configure_server);
	ClassDB::bind_method(D_METHOD("configure_client", "peer"), &GameplayNetworkPrediction::configure_client);
	ClassDB::bind_method(D_METHOD("clear_transport"), &GameplayNetworkPrediction::clear_transport);
	ClassDB::bind_method(D_METHOD("peer_disconnected", "peer_id"), &GameplayNetworkPrediction::peer_disconnected);
	ClassDB::bind_method(D_METHOD("is_server"), &GameplayNetworkPrediction::is_server);
	ClassDB::bind_method(D_METHOD("set_network_simulator", "simulator"), &GameplayNetworkPrediction::set_network_simulator);
	ClassDB::bind_method(D_METHOD("get_network_simulator"), &GameplayNetworkPrediction::get_network_simulator);
	ClassDB::bind_method(D_METHOD("set_replication_graph", "graph"), &GameplayNetworkPrediction::set_replication_graph);
	ClassDB::bind_method(D_METHOD("get_replication_graph"), &GameplayNetworkPrediction::get_replication_graph);
	ClassDB::bind_method(D_METHOD("set_resend_interval_msec", "interval_msec"), &GameplayNetworkPrediction::set_resend_interval_msec);
	ClassDB::bind_method(D_METHOD("get_resend_interval_msec"), &GameplayNetworkPrediction::get_resend_interval_msec);
	ClassDB::bind_method(D_METHOD("register_server_object", "object_id", "owner_peer_id", "model", "initial_state"), &GameplayNetworkPrediction::register_server_object, DEFVAL(Ref<GameplayPredictionState>()));
	ClassDB::bind_method(D_METHOD("set_server_object_owner_peer_id", "object_id", "owner_peer_id"), &GameplayNetworkPrediction::set_server_object_owner_peer_id);
	ClassDB::bind_method(D_METHOD("register_owned_client_object", "object_id", "prediction"), &GameplayNetworkPrediction::register_owned_client_object);
	ClassDB::bind_method(D_METHOD("register_remote_client_object", "object_id", "buffer"), &GameplayNetworkPrediction::register_remote_client_object);
	ClassDB::bind_method(D_METHOD("get_owned_client_object", "object_id"), &GameplayNetworkPrediction::get_owned_client_object);
	ClassDB::bind_method(D_METHOD("get_remote_client_object", "object_id"), &GameplayNetworkPrediction::get_remote_client_object);
	ClassDB::bind_method(D_METHOD("get_server_object_state", "object_id"), &GameplayNetworkPrediction::get_server_object_state);
	ClassDB::bind_method(D_METHOD("submit_local_input", "object_id", "movement_input", "now_msec"), &GameplayNetworkPrediction::submit_local_input);
	ClassDB::bind_method(D_METHOD("receive_packet", "transport_sender_peer_id", "message", "now_msec"), &GameplayNetworkPrediction::receive_packet);
	ClassDB::bind_method(D_METHOD("handles_message", "message"), &GameplayNetworkPrediction::handles_message);
	ClassDB::bind_method(D_METHOD("poll", "now_msec"), &GameplayNetworkPrediction::poll);
	ClassDB::bind_method(D_METHOD("get_last_rejection_reason"), &GameplayNetworkPrediction::get_last_rejection_reason);
	ClassDB::bind_method(D_METHOD("get_rejected_packet_count"), &GameplayNetworkPrediction::get_rejected_packet_count);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "resend_interval_msec", PROPERTY_HINT_RANGE, "1,60000,1"), "set_resend_interval_msec", "get_resend_interval_msec");
}

void GameplayNetworkPrediction::configure_server(const Ref<MultiplayerPeer> &p_peer, GameplaySessionManager *p_session_manager) {
	server = true;
	multiplayer_peer = p_peer;
	session_manager_id = p_session_manager ? p_session_manager->get_instance_id() : ObjectID();
}

void GameplayNetworkPrediction::configure_client(const Ref<MultiplayerPeer> &p_peer) {
	server = false;
	multiplayer_peer = p_peer;
	session_manager_id = ObjectID();
}

void GameplayNetworkPrediction::clear_transport() {
	multiplayer_peer.unref();
	session_manager_id = ObjectID();
	last_resend_msec.clear();
	if (network_simulator.is_valid()) {
		network_simulator->clear();
	}
}

void GameplayNetworkPrediction::peer_disconnected(int p_peer_id) {
	if (!server || p_peer_id <= 1) {
		return;
	}
	if (network_simulator.is_valid()) {
		network_simulator->discard_target(p_peer_id);
	}
	if (replication_graph.is_valid()) {
		replication_graph->remove_connection(p_peer_id);
	}
}

bool GameplayNetworkPrediction::is_server() const {
	return server;
}

void GameplayNetworkPrediction::set_network_simulator(const Ref<GameplayNetworkSimulator> &p_simulator) {
	ERR_FAIL_COND(p_simulator.is_null());
	network_simulator = p_simulator;
}

Ref<GameplayNetworkSimulator> GameplayNetworkPrediction::get_network_simulator() const {
	return network_simulator;
}

void GameplayNetworkPrediction::set_replication_graph(const Ref<GameplayReplicationGraph> &p_graph) {
	replication_graph = p_graph;
}

Ref<GameplayReplicationGraph> GameplayNetworkPrediction::get_replication_graph() const {
	return replication_graph;
}

void GameplayNetworkPrediction::set_resend_interval_msec(uint64_t p_interval_msec) {
	ERR_FAIL_COND(p_interval_msec == 0 || p_interval_msec > 60000);
	resend_interval_msec = p_interval_msec;
}

uint64_t GameplayNetworkPrediction::get_resend_interval_msec() const {
	return resend_interval_msec;
}

Error GameplayNetworkPrediction::register_server_object(int p_object_id, int p_owner_peer_id, const Ref<GameplayPredictionModel> &p_model, const Ref<GameplayPredictionState> &p_initial_state) {
	ERR_FAIL_COND_V(!server, ERR_UNAUTHORIZED);
	return authority->register_object(p_object_id, p_owner_peer_id, p_model, p_initial_state);
}

Error GameplayNetworkPrediction::set_server_object_owner_peer_id(int p_object_id, int p_owner_peer_id) {
	ERR_FAIL_COND_V(!server, ERR_UNAUTHORIZED);
	return authority->set_object_owner_peer_id(p_object_id, p_owner_peer_id);
}

Error GameplayNetworkPrediction::register_owned_client_object(int p_object_id, const Ref<GameplayClientPrediction> &p_prediction) {
	ERR_FAIL_COND_V(server || p_object_id <= 0 || p_prediction.is_null() || owned_objects.has(p_object_id), ERR_INVALID_PARAMETER);
	owned_objects.insert(p_object_id, p_prediction);
	return OK;
}

Error GameplayNetworkPrediction::register_remote_client_object(int p_object_id, const Ref<GameplayInterpolationBuffer> &p_buffer) {
	ERR_FAIL_COND_V(server || p_object_id <= 0 || p_buffer.is_null() || remote_objects.has(p_object_id), ERR_INVALID_PARAMETER);
	remote_objects.insert(p_object_id, p_buffer);
	return OK;
}

Ref<GameplayClientPrediction> GameplayNetworkPrediction::get_owned_client_object(int p_object_id) const {
	const Ref<GameplayClientPrediction> *prediction = owned_objects.getptr(p_object_id);
	return prediction ? *prediction : Ref<GameplayClientPrediction>();
}

Ref<GameplayInterpolationBuffer> GameplayNetworkPrediction::get_remote_client_object(int p_object_id) const {
	const Ref<GameplayInterpolationBuffer> *buffer = remote_objects.getptr(p_object_id);
	return buffer ? *buffer : Ref<GameplayInterpolationBuffer>();
}

Ref<GameplayPredictionState> GameplayNetworkPrediction::get_server_object_state(int p_object_id) const {
	return authority->get_object_state(p_object_id);
}

Ref<GameplayPredictionInput> GameplayNetworkPrediction::submit_local_input(int p_object_id, const Vector3 &p_input, uint64_t p_now_msec) {
	if (server) {
		last_rejection_reason = "server_cannot_submit_local_input";
		return Ref<GameplayPredictionInput>();
	}
	Ref<GameplayClientPrediction> *prediction = owned_objects.getptr(p_object_id);
	if (!prediction) {
		last_rejection_reason = "unknown_owned_object";
		return Ref<GameplayPredictionInput>();
	}
	Ref<GameplayPredictionInput> input = (*prediction)->predict_input(p_input, p_now_msec);
	if (input.is_null()) {
		last_rejection_reason = (*prediction)->get_last_rejection_reason();
		return input;
	}
	Dictionary message;
	message["type"] = "gameplay_prediction_input";
	message["object_id"] = p_object_id;
	message["command"] = input->to_dictionary();
	network_simulator->enqueue(MultiplayerPeer::TARGET_PEER_SERVER, message, p_now_msec);
	last_resend_msec.insert(p_object_id, p_now_msec);
	last_rejection_reason.clear();
	return input;
}

Error GameplayNetworkPrediction::_send_dictionary(int p_target_peer_id, const Dictionary &p_message) {
	ERR_FAIL_COND_V(multiplayer_peer.is_null(), ERR_UNCONFIGURED);
	const CharString payload = JSON::stringify(p_message).utf8();
	ERR_FAIL_COND_V(payload.length() > 4096, ERR_OUT_OF_MEMORY);
	multiplayer_peer->set_target_peer(p_target_peer_id);
	return multiplayer_peer->put_packet(reinterpret_cast<const uint8_t *>(payload.get_data()), payload.length());
}

Error GameplayNetworkPrediction::_queue_snapshot(int p_target_peer_id, int p_object_id, const Ref<GameplayPredictionState> &p_state, uint64_t p_now_msec) {
	Dictionary message;
	message["type"] = "gameplay_prediction_snapshot";
	message["object_id"] = p_object_id;
	message["state"] = p_state->to_dictionary();
	const Dictionary queued = network_simulator->enqueue(p_target_peer_id, message, p_now_msec);
	return bool(queued.get("queued", false)) || queued.get("reason", String()) == "simulated_loss" ? OK : ERR_OUT_OF_MEMORY;
}

Error GameplayNetworkPrediction::_reject(const String &p_reason) {
	last_rejection_reason = p_reason;
	rejected_packet_count++;
	return ERR_UNAUTHORIZED;
}

bool GameplayNetworkPrediction::_is_joined_peer(int p_peer_id) const {
	GameplaySessionManager *manager = Object::cast_to<GameplaySessionManager>(ObjectDB::get_instance(session_manager_id));
	if (!manager) {
		return false;
	}
	const Ref<GameplayConnection> connection = manager->get_connection(p_peer_id);
	return connection.is_valid() && connection->get_state() == GameplayConnection::STATE_SPAWNED && manager->get_session_by_peer(p_peer_id) != nullptr;
}

Error GameplayNetworkPrediction::receive_packet(int p_transport_sender_peer_id, const Dictionary &p_message, uint64_t p_now_msec) {
	const String type = p_message.get("type", String());
	if (type == "gameplay_prediction_input") {
		if (!server) {
			return _reject("client_cannot_receive_input_command");
		}
		if (!_is_joined_peer(p_transport_sender_peer_id)) {
			return _reject("sender_not_joined");
		}
		if (p_message.has("position") || p_message.has("velocity") || p_message.has("state") || p_message.get("command", Variant()).get_type() != Variant::DICTIONARY) {
			return _reject("forged_authoritative_state");
		}
		const Dictionary command_data = p_message["command"];
		if (command_data.has("position") || command_data.has("velocity") || command_data.has("state") || !command_data.has("sequence") || !command_data.has("input") || !command_data.has("step_msec")) {
			return _reject("forged_authoritative_state");
		}
		Vector3 movement;
		if (!_gameplay_dictionary_to_vector3(command_data["input"], movement)) {
			return _reject("invalid_input_command");
		}
		Ref<GameplayPredictionInput> input;
		input.instantiate();
		input->set_sequence(uint64_t(command_data["sequence"]));
		input->set_movement_input(movement);
		const int64_t step_msec = int64_t(command_data["step_msec"]);
		if (step_msec <= 0 || step_msec > 1000) {
			return _reject("invalid_input_command");
		}
		input->set_step_msec(uint32_t(step_msec));
		const int object_id = int(p_message.get("object_id", 0));
		const Dictionary consumed = authority->consume_input(p_transport_sender_peer_id, object_id, input, p_now_msec);
		if (!bool(consumed.get("accepted", false))) {
			const String reason = consumed.get("reason", String("input_rejected"));
			if (reason == "duplicate_sequence" || reason == "sequence_too_old") {
				const Ref<GameplayPredictionState> current = authority->get_object_state(object_id);
				if (current.is_valid()) {
					_queue_snapshot(p_transport_sender_peer_id, object_id, current, p_now_msec);
				}
			}
			return _reject(reason);
		}
		const Ref<GameplayPredictionState> state = consumed["state"];
		HashSet<int> recipients;
		recipients.insert(p_transport_sender_peer_id);
		if (replication_graph.is_valid()) {
			for (const Variant &peer_variant : replication_graph->get_connection_peer_ids()) {
				const int peer_id = int(peer_variant);
				if (replication_graph->get_relevant_object_ids(peer_id).has(object_id)) {
					recipients.insert(peer_id);
				}
			}
		}
		for (const int recipient : recipients) {
			_queue_snapshot(recipient, object_id, state, p_now_msec);
		}
		last_rejection_reason.clear();
		return OK;
	}
	if (type == "gameplay_prediction_snapshot") {
		if (server || p_transport_sender_peer_id != MultiplayerPeer::TARGET_PEER_SERVER) {
			return _reject("snapshot_not_from_server");
		}
		if (p_message.get("state", Variant()).get_type() != Variant::DICTIONARY) {
			return _reject("invalid_snapshot");
		}
		const Dictionary state_data = p_message["state"];
		Vector3 position;
		Vector3 velocity;
		if (!_gameplay_dictionary_to_vector3(state_data.get("position", Variant()), position) || !_gameplay_dictionary_to_vector3(state_data.get("velocity", Variant()), velocity)) {
			return _reject("invalid_snapshot");
		}
		Ref<GameplayPredictionState> state;
		state.instantiate();
		state->set_position(position);
		state->set_velocity(velocity);
		state->set_confirmed_sequence(uint64_t(state_data.get("confirmed_sequence", 0)));
		state->set_server_time_msec(uint64_t(state_data.get("server_time_msec", 0)));
		const int object_id = int(p_message.get("object_id", 0));
		if (Ref<GameplayClientPrediction> *prediction = owned_objects.getptr(object_id)) {
			const Dictionary applied = (*prediction)->apply_authoritative_state(state);
			if (!bool(applied.get("accepted", false))) {
				return _reject(applied.get("reason", String("snapshot_rejected")));
			}
			last_rejection_reason.clear();
			return OK;
		}
		if (Ref<GameplayInterpolationBuffer> *buffer = remote_objects.getptr(object_id)) {
			const Error error = (*buffer)->add_sample(state);
			if (error != OK && error != ERR_ALREADY_EXISTS) {
				return _reject("snapshot_buffer_rejected");
			}
			last_rejection_reason.clear();
			return OK;
		}
		return _reject("unknown_snapshot_object");
	}
	return ERR_DOES_NOT_EXIST;
}

bool GameplayNetworkPrediction::handles_message(const Dictionary &p_message) const {
	const String type = p_message.get("type", String());
	return type == "gameplay_prediction_input" || type == "gameplay_prediction_snapshot";
}

Error GameplayNetworkPrediction::poll(uint64_t p_now_msec) {
	ERR_FAIL_COND_V(multiplayer_peer.is_null(), ERR_UNCONFIGURED);
	if (!server) {
		for (const KeyValue<int, Ref<GameplayClientPrediction>> &entry : owned_objects) {
			const uint64_t *last_resend = last_resend_msec.getptr(entry.key);
			if (last_resend && p_now_msec >= *last_resend && p_now_msec - *last_resend >= resend_interval_msec) {
				for (const Variant &input_variant : entry.value->get_unconfirmed_inputs()) {
					const Ref<GameplayPredictionInput> input = input_variant;
					Dictionary message;
					message["type"] = "gameplay_prediction_input";
					message["object_id"] = entry.key;
					message["command"] = input->to_dictionary();
					network_simulator->enqueue(MultiplayerPeer::TARGET_PEER_SERVER, message, p_now_msec);
				}
				last_resend_msec.insert(entry.key, p_now_msec);
			}
		}
	}
	const Array due = network_simulator->drain(p_now_msec);
	Error first_error = OK;
	for (const Variant &packet_variant : due) {
		const Dictionary packet = packet_variant;
		const Error error = _send_dictionary(int(packet["target_peer_id"]), packet["message"]);
		if (first_error == OK && error != OK) {
			first_error = error;
		}
	}
	return first_error;
}

String GameplayNetworkPrediction::get_last_rejection_reason() const {
	return last_rejection_reason;
}

int GameplayNetworkPrediction::get_rejected_packet_count() const {
	return rejected_packet_count;
}
