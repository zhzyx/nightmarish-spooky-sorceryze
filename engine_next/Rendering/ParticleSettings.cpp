/**************************************************************************/
/*  ParticleSettings.cpp                                                  */
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

#include "engine_next/include/EngineNext/Rendering/ParticleSettings.h"

#include "engine_next/Assets/AssetValidation.h"

#include <cmath>
#include <cstddef>
#include <algorithm>
#include <array>
#include <initializer_list>
#include <limits>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

bool InRange(double dValue, double dMinimum, double dMaximum) noexcept
{
	return std::isfinite(dValue) && dValue >= dMinimum && dValue <= dMaximum;
}

bool OptionalFields(const Serialization::JsonValue::Object &mapValue, const std::string &strPath, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::initializer_list<const char *> arrFields = {
		"emitter_id", "entity_id", "enabled", "loop", "seed", "rate", "lifetime", "duration", "position",
		"position_spread", "velocity", "velocity_spread", "start_size", "end_size", "start_color", "end_color"
	};
	Serialization::JsonValue::Object mapFields;
	for (const char *pName : arrFields)
	{
		if (std::string(pName) != "emitter_id")
		{
			mapFields.emplace(pName, Serialization::JsonValue{});
		}
	}
	for (const std::pair<const std::string, Serialization::JsonValue> &stField : mapValue)
	{
		mapFields.emplace(stField.first, Serialization::JsonValue{});
	}
	return Assets::Fields(mapFields, arrFields, strPath, out_arrDiagnostics);
}

bool OptionalNumber(const Serialization::JsonValue::Object &mapValue, const char *pName, const std::string &strPath, double &out_dValue,
					Assets::Diagnostics &out_arrDiagnostics)
{
	return mapValue.find(pName) == mapValue.end() || Assets::Number(mapValue, pName, strPath, out_dValue, out_arrDiagnostics);
}

bool OptionalBool(const Serialization::JsonValue::Object &mapValue, const char *pName, const std::string &strPath, bool &out_bValue,
				  Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator itValue = mapValue.find(pName);
	if (itValue == mapValue.end())
	{
		return true;
	}
	if (!itValue->second.GetBool(out_bValue))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "type", strPath + "." + pName, "Expected a boolean.");
		return false;
	}
	return true;
}

template <std::size_t N>
bool OptionalVector(const Serialization::JsonValue::Object &mapValue, const char *pName, const std::string &strPath, std::array<double, N> &out_arrValues,
					Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object::const_iterator itValue = mapValue.find(pName);
	if (itValue == mapValue.end())
	{
		return true;
	}
	const Serialization::JsonValue::List *pValues = itValue->second.GetList();
	if (pValues == nullptr || pValues->size() != N)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "type", strPath + "." + pName, "Expected a fixed-size array of finite numbers.");
		return false;
	}
	for (std::size_t nIndex = 0; nIndex < N; ++nIndex)
	{
		if (!(*pValues)[nIndex].GetNumber(out_arrValues[nIndex]))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "type", strPath + "." + pName, "Expected finite vector components.");
			return false;
		}
	}
	return true;
}

bool ParseEmitter(const Serialization::JsonValue &stValue, const std::string &strPath, ParticleSettings &out_stSettings,
				  Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Assets::Object(stValue, strPath, out_arrDiagnostics);
	if (pObject == nullptr || !OptionalFields(*pObject, strPath, out_arrDiagnostics))
	{
		return false;
	}
	std::int64_t nEmitterId = 0;
	if (!Assets::Integer(*pObject, "emitter_id", strPath, nEmitterId, out_arrDiagnostics))
	{
		return false;
	}
	if (nEmitterId <= 0 || static_cast<std::uint64_t>(nEmitterId) > std::numeric_limits<std::uint32_t>::max())
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "particle_id", strPath + ".emitter_id", "Expected a positive uint32 emitter identity.");
		return false;
	}
	out_stSettings.nEmitterId = static_cast<std::uint32_t>(nEmitterId);
	if (pObject->find("entity_id") != pObject->end())
	{
		std::int64_t nEntityId = 0;
		if (!Assets::Integer(*pObject, "entity_id", strPath, nEntityId, out_arrDiagnostics))
		{
			return false;
		}
		if (nEntityId <= 0)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "particle_entity", strPath + ".entity_id", "Expected a positive existing-scene integer identity.");
			return false;
		}
		out_stSettings.nSourceEntityId = static_cast<std::uint64_t>(nEntityId);
	}
	if (pObject->find("seed") != pObject->end())
	{
		std::int64_t nSeed = 0;
		if (!Assets::Integer(*pObject, "seed", strPath, nSeed, out_arrDiagnostics))
		{
			return false;
		}
		if (nSeed < 0)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "particle_seed", strPath + ".seed", "Expected a nonnegative integer seed.");
			return false;
		}
		out_stSettings.nSeed = static_cast<std::uint64_t>(nSeed);
	}
	return OptionalBool(*pObject, "enabled", strPath, out_stSettings.bEnabled, out_arrDiagnostics) &&
			OptionalBool(*pObject, "loop", strPath, out_stSettings.bLoop, out_arrDiagnostics) &&
			OptionalNumber(*pObject, "rate", strPath, out_stSettings.dRate, out_arrDiagnostics) &&
			OptionalNumber(*pObject, "lifetime", strPath, out_stSettings.dLifetime, out_arrDiagnostics) &&
			OptionalNumber(*pObject, "duration", strPath, out_stSettings.dDuration, out_arrDiagnostics) &&
			OptionalVector(*pObject, "position", strPath, out_stSettings.arrPosition, out_arrDiagnostics) &&
			OptionalVector(*pObject, "position_spread", strPath, out_stSettings.arrPositionSpread, out_arrDiagnostics) &&
			OptionalVector(*pObject, "velocity", strPath, out_stSettings.arrVelocity, out_arrDiagnostics) &&
			OptionalVector(*pObject, "velocity_spread", strPath, out_stSettings.arrVelocitySpread, out_arrDiagnostics) &&
			OptionalNumber(*pObject, "start_size", strPath, out_stSettings.dStartSize, out_arrDiagnostics) &&
			OptionalNumber(*pObject, "end_size", strPath, out_stSettings.dEndSize, out_arrDiagnostics) &&
			OptionalVector(*pObject, "start_color", strPath, out_stSettings.arrStartColor, out_arrDiagnostics) &&
			OptionalVector(*pObject, "end_color", strPath, out_stSettings.arrEndColor, out_arrDiagnostics);
}

} // namespace

bool ValidateParticleSettings(const ParticleSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stSettings.nEmitterId == 0 || (stSettings.nSourceEntityId.has_value() && *stSettings.nSourceEntityId == 0) || !InRange(stSettings.dRate, 0, 4096) ||
		!InRange(stSettings.dLifetime, 0.001, 3600) || !InRange(stSettings.dDuration, 0, 86400) || stSettings.dRate * stSettings.dLifetime > MAX_PARTICLES ||
		!InRange(stSettings.dStartSize, 0, 1e4) || !InRange(stSettings.dEndSize, 0, 1e4))
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "particle_settings", "$.particles",
							  "Particle timing and size ranges must be finite and the live birth budget must fit 4096 particles.");
		return false;
	}
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!InRange(stSettings.arrPosition[nAxis], -1e6, 1e6) || !InRange(stSettings.arrPositionSpread[nAxis], 0, 1e6) ||
			!InRange(stSettings.arrVelocity[nAxis], -1e4, 1e4) || !InRange(stSettings.arrVelocitySpread[nAxis], 0, 1e4))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "particle_vector", "$.particles",
								  "Particle positions, velocities and symmetric spreads must be finite and bounded.");
			return false;
		}
	}
	for (std::size_t nChannel = 0; nChannel < 4; ++nChannel)
	{
		if (!InRange(stSettings.arrStartColor[nChannel], 0, 1) || !InRange(stSettings.arrEndColor[nChannel], 0, 1))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "particle_color", "$.particles", "Particle color and alpha endpoints must be finite in [0,1].");
			return false;
		}
	}
	return true;
}

bool ValidateParticleEmitters(const std::vector<ParticleSettings> &arrEmitters, Assets::Diagnostics &out_arrDiagnostics)
{
	if (arrEmitters.size() > MAX_PARTICLE_EMITTERS)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "particle_emitters", "$.particles", "At most 16 particle emitters are supported.");
		return false;
	}
	std::uint64_t nCapacity = 0;
	for (std::size_t nIndex = 0; nIndex < arrEmitters.size(); ++nIndex)
	{
		const ParticleSettings &stEmitter = arrEmitters[nIndex];
		if (!ValidateParticleSettings(stEmitter, out_arrDiagnostics))
		{
			return false;
		}
		for (std::size_t nPrevious = 0; nPrevious < nIndex; ++nPrevious)
		{
			if (arrEmitters[nPrevious].nEmitterId == stEmitter.nEmitterId)
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "particle_id", "$.particles", "Emitter identities must be unique.");
				return false;
			}
		}
		nCapacity += stEmitter.dRate > 0 ? static_cast<std::uint64_t>((std::max)(1.0, std::ceil(stEmitter.dRate * stEmitter.dLifetime))) : 0;
		if (nCapacity > MAX_PARTICLES)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "particle_budget", "$.particles", "Combined emitter capacity exceeds 4096 live particles.");
			return false;
		}
	}
	return true;
}

bool ParseParticleEmitters(const Serialization::JsonValue &stValue, std::vector<ParticleSettings> &out_arrEmitters, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::List *pValues = stValue.GetList();
	if (pValues == nullptr || pValues->size() > MAX_PARTICLE_EMITTERS)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "particle_emitters", "$.particles", "Expected an array of at most 16 particle emitters.");
		return false;
	}
	std::vector<ParticleSettings> arrCandidate(pValues->size());
	for (std::size_t nIndex = 0; nIndex < pValues->size(); ++nIndex)
	{
		if (!ParseEmitter((*pValues)[nIndex], "$.particles[" + std::to_string(nIndex) + "]", arrCandidate[nIndex], out_arrDiagnostics))
		{
			return false;
		}
	}
	if (!ValidateParticleEmitters(arrCandidate, out_arrDiagnostics))
	{
		return false;
	}
	out_arrEmitters = std::move(arrCandidate);
	return true;
}

} // namespace EngineNext::Rendering
