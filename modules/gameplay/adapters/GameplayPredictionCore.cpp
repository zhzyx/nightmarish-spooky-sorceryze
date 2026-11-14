/**************************************************************************/
/*  GameplayPredictionCore.cpp                                            */
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

#include "GameplayPredictionCore.h"

#include "core/math/math_funcs.h"
#include "core/object/class_db.h"

namespace
{

Vector3 ToGodot(const EngineNext::Gameplay::Vector3 &vValue)
{
	return Vector3(vValue.fX, vValue.fY, vValue.fZ);
}

EngineNext::Gameplay::Vector3 ToCore(const Vector3 &vValue)
{
	return EngineNext::Gameplay::Vector3{
		static_cast<float>(vValue.x),
		static_cast<float>(vValue.y),
		static_cast<float>(vValue.z),
	};
}

Ref<GameplayPredictionState> ToGodot(const EngineNext::Gameplay::PredictionState &stState)
{
	Ref<GameplayPredictionState> refResult;
	refResult.instantiate();
	refResult->set_position(ToGodot(stState.vPosition));
	refResult->set_velocity(ToGodot(stState.vVelocity));
	refResult->set_confirmed_sequence(stState.nConfirmedSequence);
	refResult->set_server_time_msec(stState.nServerTimeMsec);
	return refResult;
}

Dictionary VectorToDictionary(const Vector3 &vValue)
{
	Dictionary dictResult;
	dictResult["x"] = vValue.x;
	dictResult["y"] = vValue.y;
	dictResult["z"] = vValue.z;
	return dictResult;
}

Error ToGodotError(EngineNext::Gameplay::Status eStatus)
{
	switch (eStatus)
	{
		case EngineNext::Gameplay::Status::Ok:
			return OK;
		case EngineNext::Gameplay::Status::AlreadyExists:
			return ERR_ALREADY_EXISTS;
		case EngineNext::Gameplay::Status::InvalidParameter:
			return ERR_INVALID_PARAMETER;
	}
	return ERR_INVALID_PARAMETER;
}

String ToGodotStatus(EngineNext::Gameplay::InterpolationStatus eStatus)
{
	switch (eStatus)
	{
		case EngineNext::Gameplay::InterpolationStatus::Empty:
			return "empty";
		case EngineNext::Gameplay::InterpolationStatus::SingleSample:
			return "single_sample";
		case EngineNext::Gameplay::InterpolationStatus::BeforeRange:
			return "before_range";
		case EngineNext::Gameplay::InterpolationStatus::Interpolated:
			return "interpolated";
		case EngineNext::Gameplay::InterpolationStatus::Held:
			return "held";
		case EngineNext::Gameplay::InterpolationStatus::StaleHeld:
			return "stale_held";
		case EngineNext::Gameplay::InterpolationStatus::NumericError:
			return "numeric_error";
	}
	return "empty";
}

} // namespace

void GameplayPredictionInput::_bind_methods()
{
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

void GameplayPredictionInput::set_sequence(uint64_t p_sequence)
{
	stInput.nSequence = p_sequence;
}

uint64_t GameplayPredictionInput::get_sequence() const
{
	return stInput.nSequence;
}

void GameplayPredictionInput::set_movement_input(const Vector3 &p_input)
{
	ERR_FAIL_COND_MSG(!p_input.is_finite(), "Prediction input must be finite.");
	stInput.vMovementInput = ToCore(p_input);
}

Vector3 GameplayPredictionInput::get_movement_input() const
{
	return ToGodot(stInput.vMovementInput);
}

void GameplayPredictionInput::set_step_msec(uint32_t p_step_msec)
{
	ERR_FAIL_COND_MSG(p_step_msec == 0 || p_step_msec > 1000, "Prediction step must be between 1 and 1000 milliseconds.");
	stInput.nStepMsec = p_step_msec;
}

uint32_t GameplayPredictionInput::get_step_msec() const
{
	return stInput.nStepMsec;
}

Dictionary GameplayPredictionInput::to_dictionary() const
{
	Dictionary dictResult;
	dictResult["sequence"] = stInput.nSequence;
	dictResult["input"] = VectorToDictionary(ToGodot(stInput.vMovementInput));
	dictResult["step_msec"] = stInput.nStepMsec;
	return dictResult;
}

void GameplayPredictionState::_bind_methods()
{
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

void GameplayPredictionState::set_position(const Vector3 &p_position)
{
	ERR_FAIL_COND_MSG(!p_position.is_finite(), "Prediction position must be finite.");
	stState.vPosition = ToCore(p_position);
}

Vector3 GameplayPredictionState::get_position() const
{
	return ToGodot(stState.vPosition);
}

void GameplayPredictionState::set_velocity(const Vector3 &p_velocity)
{
	ERR_FAIL_COND_MSG(!p_velocity.is_finite(), "Prediction velocity must be finite.");
	stState.vVelocity = ToCore(p_velocity);
}

Vector3 GameplayPredictionState::get_velocity() const
{
	return ToGodot(stState.vVelocity);
}

void GameplayPredictionState::set_confirmed_sequence(uint64_t p_sequence)
{
	stState.nConfirmedSequence = p_sequence;
}

uint64_t GameplayPredictionState::get_confirmed_sequence() const
{
	return stState.nConfirmedSequence;
}

void GameplayPredictionState::set_server_time_msec(uint64_t p_time_msec)
{
	stState.nServerTimeMsec = p_time_msec;
}

uint64_t GameplayPredictionState::get_server_time_msec() const
{
	return stState.nServerTimeMsec;
}

Ref<GameplayPredictionState> GameplayPredictionState::duplicate_state() const
{
	return ToGodot(stState);
}

Dictionary GameplayPredictionState::to_dictionary() const
{
	Dictionary dictResult;
	dictResult["position"] = VectorToDictionary(ToGodot(stState.vPosition));
	dictResult["velocity"] = VectorToDictionary(ToGodot(stState.vVelocity));
	dictResult["confirmed_sequence"] = stState.nConfirmedSequence;
	dictResult["server_time_msec"] = stState.nServerTimeMsec;
	return dictResult;
}

void GameplayPredictionModel::_bind_methods()
{
	ClassDB::bind_method(D_METHOD("set_max_speed", "max_speed"), &GameplayPredictionModel::set_max_speed);
	ClassDB::bind_method(D_METHOD("get_max_speed"), &GameplayPredictionModel::get_max_speed);
	ClassDB::bind_method(D_METHOD("set_fixed_step_msec", "step_msec"), &GameplayPredictionModel::set_fixed_step_msec);
	ClassDB::bind_method(D_METHOD("get_fixed_step_msec"), &GameplayPredictionModel::get_fixed_step_msec);
	ClassDB::bind_method(D_METHOD("simulate", "state", "input"), &GameplayPredictionModel::simulate);

	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "max_speed", PROPERTY_HINT_RANGE, "0.001,100000,0.001,or_greater"), "set_max_speed", "get_max_speed");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "fixed_step_msec", PROPERTY_HINT_RANGE, "1,1000,1"), "set_fixed_step_msec", "get_fixed_step_msec");
}

void GameplayPredictionModel::set_max_speed(float p_max_speed)
{
	ERR_FAIL_COND_MSG(!stModel.SetMaxSpeed(p_max_speed), "Maximum speed must be finite and positive.");
}

float GameplayPredictionModel::get_max_speed() const
{
	return stModel.GetMaxSpeed();
}

void GameplayPredictionModel::set_fixed_step_msec(uint32_t p_step_msec)
{
	ERR_FAIL_COND_MSG(!stModel.SetFixedStepMsec(p_step_msec), "Fixed prediction step must be between 1 and 1000 milliseconds.");
}

uint32_t GameplayPredictionModel::get_fixed_step_msec() const
{
	return stModel.GetFixedStepMsec();
}

const EngineNext::Gameplay::PredictionInput &GameplayPredictionInput::GetCoreInput() const
{
	return stInput;
}

EngineNext::Gameplay::PredictionState &GameplayPredictionState::GetMutableCoreState()
{
	return stState;
}

Error GameplayPredictionModel::simulate(const Ref<GameplayPredictionState> &p_state, const Ref<GameplayPredictionInput> &p_input) const
{
	ERR_FAIL_COND_V(p_state.is_null() || p_input.is_null(), ERR_INVALID_PARAMETER);
	return ToGodotError(stModel.Simulate(p_state->GetMutableCoreState(), p_input->GetCoreInput()));
}

const EngineNext::Gameplay::PredictionModel &GameplayPredictionModel::GetCoreModel() const
{
	return stModel;
}

void GameplayInterpolationBuffer::_bind_methods()
{
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

void GameplayInterpolationBuffer::set_max_samples(int p_max_samples)
{
	ERR_FAIL_COND(p_max_samples < 2 || p_max_samples > 4096);
	ERR_FAIL_COND(!stBuffer.SetMaxSamples(static_cast<std::size_t>(p_max_samples)));
}

int GameplayInterpolationBuffer::get_max_samples() const
{
	return static_cast<int>(stBuffer.GetMaxSamples());
}

void GameplayInterpolationBuffer::set_interpolation_delay_msec(uint64_t p_delay_msec)
{
	ERR_FAIL_COND(p_delay_msec > 60000);
	ERR_FAIL_COND(!stBuffer.SetInterpolationDelayMsec(p_delay_msec));
}

uint64_t GameplayInterpolationBuffer::get_interpolation_delay_msec() const
{
	return stBuffer.GetInterpolationDelayMsec();
}

void GameplayInterpolationBuffer::set_stale_after_msec(uint64_t p_stale_after_msec)
{
	ERR_FAIL_COND(p_stale_after_msec == 0 || p_stale_after_msec > 60000);
	ERR_FAIL_COND(!stBuffer.SetStaleAfterMsec(p_stale_after_msec));
}

uint64_t GameplayInterpolationBuffer::get_stale_after_msec() const
{
	return stBuffer.GetStaleAfterMsec();
}

Error GameplayInterpolationBuffer::add_sample(const Ref<GameplayPredictionState> &p_state)
{
	ERR_FAIL_COND_V(p_state.is_null(), ERR_INVALID_PARAMETER);
	return ToGodotError(stBuffer.AddSample(p_state->GetMutableCoreState()));
}

Dictionary GameplayInterpolationBuffer::sample(uint64_t p_now_msec) const
{
	Dictionary dictResult;
	const EngineNext::Gameplay::InterpolationResult stResult = stBuffer.Sample(p_now_msec);
	dictResult["status"] = ToGodotStatus(stResult.eStatus);
	if (stResult.stState.has_value())
	{
		dictResult["state"] = ToGodot(*stResult.stState);
	}
	return dictResult;
}

int GameplayInterpolationBuffer::get_sample_count() const
{
	return static_cast<int>(stBuffer.GetSampleCount());
}

void GameplayInterpolationBuffer::clear()
{
	stBuffer.Clear();
}
