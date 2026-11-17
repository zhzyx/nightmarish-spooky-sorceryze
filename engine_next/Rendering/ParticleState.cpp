/**************************************************************************/
/*  ParticleState.cpp                                                     */
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

#include "engine_next/include/EngineNext/Rendering/ParticleState.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>

namespace EngineNext::Rendering
{
namespace
{

std::uint64_t MixBits(std::uint64_t nValue) noexcept
{
	nValue += 0x9e3779b97f4a7c15ULL;
	nValue = (nValue ^ (nValue >> 30)) * 0xbf58476d1ce4e5b9ULL;
	nValue = (nValue ^ (nValue >> 27)) * 0x94d049bb133111ebULL;
	return nValue ^ (nValue >> 31);
}

double SignedRandom(std::uint64_t nSeed, std::uint64_t nSpawnIndex, std::uint64_t nChannel) noexcept
{
	const std::uint64_t nBits = MixBits(nSeed ^ MixBits(nSpawnIndex) ^ MixBits(nChannel));
	// Exactly representable integer conversion avoids implementation-dependent
	// distributions and preserves the same seed/index sequence across compilers.
	return static_cast<double>(nBits >> 11) * (2.0 / 9007199254740992.0) - 1;
}

bool GpuCoordinate(double dValue) noexcept
{
	return std::isfinite(dValue) && std::abs(dValue) <= std::numeric_limits<float>::max();
}

struct EmissionPhase
{
	std::uint64_t nLastBirth = 0;
	bool bAtBirth = false;
};

EmissionPhase ResolvePhase(double dSeconds, double dRate, double dProduct) noexcept
{
	const double dNearest = std::round(dProduct);
	const double dBirthTime = dNearest / dRate;
	EmissionPhase stPhase;
	// Recognize the represented scheduled birth exactly. This preserves calls
	// at i/rate without treating their nextafter neighbors as the same instant.
	if (dSeconds == dBirthTime)
	{
		stPhase.nLastBirth = static_cast<std::uint64_t>(dNearest);
		stPhase.bAtBirth = true;
		return stPhase;
	}
	stPhase.nLastBirth = static_cast<std::uint64_t>(std::floor(dProduct));
	if (dProduct == dNearest && dSeconds < dBirthTime && stPhase.nLastBirth > 0)
	{
		--stPhase.nLastBirth;
	}
	return stPhase;
}

std::uint64_t LifetimeSlots(double dLifetime, double dRate) noexcept
{
	const double dProduct = dLifetime * dRate;
	const double dNearest = std::round(dProduct);
	const double dNormalized = dLifetime == dNearest / dRate ? dNearest : dProduct;
	return static_cast<std::uint64_t>((std::max)(1.0, std::ceil(dNormalized)));
}

BillboardInstance EvaluateInstance(const ParticleSettings &stSettings, std::uint64_t nSpawnIndex, double dAge, const std::array<double, 3> &arrOrigin) noexcept
{
	BillboardInstance stInstance;
	stInstance.stId = { stSettings.nEmitterId, stSettings.nSeed, nSpawnIndex };
	stInstance.dAge = dAge;
	const double dFraction = std::clamp(dAge / stSettings.dLifetime, 0.0, 1.0);
	stInstance.dSize = stSettings.dStartSize + (stSettings.dEndSize - stSettings.dStartSize) * dFraction;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		const double dOffset = stSettings.arrPosition[nAxis] + stSettings.arrPositionSpread[nAxis] * SignedRandom(stSettings.nSeed, nSpawnIndex, nAxis);
		const double dVelocity = stSettings.arrVelocity[nAxis] + stSettings.arrVelocitySpread[nAxis] * SignedRandom(stSettings.nSeed, nSpawnIndex, nAxis + 3);
		stInstance.arrCenter[nAxis] = arrOrigin[nAxis] + dOffset + dVelocity * dAge;
	}
	for (std::size_t nChannel = 0; nChannel < 4; ++nChannel)
	{
		stInstance.arrColor[nChannel] =
				stSettings.arrStartColor[nChannel] + (stSettings.arrEndColor[nChannel] - stSettings.arrStartColor[nChannel]) * dFraction;
	}
	return stInstance;
}

} // namespace

bool EvaluateParticles(const ParticleSettings &stSettings, double dSeconds, const std::array<double, 3> &arrOrigin, ParticleFrame &out_stFrame,
					   Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidateParticleSettings(stSettings, out_arrDiagnostics))
	{
		return false;
	}
	if (!std::isfinite(dSeconds) || dSeconds < 0)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "particle_time", "$.particles", "Particle time must be finite and nonnegative.");
		return false;
	}
	for (double dValue : arrOrigin)
	{
		if (!GpuCoordinate(dValue))
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "particle_origin", "$.particles", "Emitter origin must fit finite binary32 coordinates.");
			return false;
		}
	}
	ParticleFrame stCandidate;
	if (!stSettings.bEnabled || stSettings.dRate == 0 ||
		(!stSettings.bLoop && (stSettings.dDuration == 0 || dSeconds >= stSettings.dDuration + stSettings.dLifetime)))
	{
		out_stFrame = stCandidate;
		return true;
	}
	const double dProduct = dSeconds * stSettings.dRate;
	if (!std::isfinite(dProduct) || dProduct > MAX_EXACT_PARTICLE_INDEX)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "particle_precision", "$.particles", "Active birth indices must remain exactly representable in binary64.");
		return false;
	}
	const EmissionPhase stPhase = ResolvePhase(dSeconds, stSettings.dRate, dProduct);
	const double dLastBirth = static_cast<double>(stPhase.nLastBirth) / stSettings.dRate;
	const bool bPreviousOverlaps = stPhase.nLastBirth > 0 && dLastBirth <= static_cast<double>(stPhase.nLastBirth - 1) / stSettings.dRate;
	const bool bNextOverlaps = stPhase.nLastBirth < MAX_EXACT_PARTICLE_INDEX && static_cast<double>(stPhase.nLastBirth + 1) / stSettings.dRate <= dLastBirth;
	if (bPreviousOverlaps || bNextOverlaps)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "particle_precision", "$.particles",
							  "Adjacent active particle birth times must remain distinct in binary64.");
		return false;
	}
	const std::uint64_t nSlots = LifetimeSlots(stSettings.dLifetime, stSettings.dRate);
	const std::uint64_t nCandidateCount = (std::min)(nSlots, stPhase.nLastBirth + 1);
	const std::uint64_t nFirstIndex = stPhase.nLastBirth + 1 - nCandidateCount;
	std::uint64_t nLastIndex = stPhase.nLastBirth;
	bool bHasParticles = true;
	if (!stSettings.bLoop)
	{
		const EmissionPhase stEndPhase = ResolvePhase(stSettings.dDuration, stSettings.dRate, stSettings.dDuration * stSettings.dRate);
		const std::uint64_t nBirthLimit = stEndPhase.nLastBirth + (stEndPhase.bAtBirth ? 0 : 1);
		bHasParticles = bHasParticles && nBirthLimit > 0 && nFirstIndex < nBirthLimit;
		if (nBirthLimit > 0)
		{
			nLastIndex = (std::min)(nLastIndex, nBirthLimit - 1);
		}
	}
	if (!bHasParticles)
	{
		out_stFrame = stCandidate;
		return true;
	}
	for (std::uint64_t nIndex = nFirstIndex; nIndex <= nLastIndex; ++nIndex)
	{
		const double dBirth = static_cast<double>(nIndex) / stSettings.dRate;
		if (nIndex > nFirstIndex && dBirth <= static_cast<double>(nIndex - 1) / stSettings.dRate)
		{
			Assets::AddDiagnostic(out_arrDiagnostics, "particle_precision", "$.particles",
								  "Adjacent active particle birth times must remain distinct in binary64.");
			return false;
		}
		double dDeath = dBirth + stSettings.dLifetime;
		// A positive lifetime shorter than one timestamp ULP still includes its
		// exact birth. The next representable timestamp has already expired.
		if (dDeath <= dBirth)
		{
			dDeath = std::nextafter(dBirth, std::numeric_limits<double>::infinity());
		}
		// The earlier lifetime/slot deadline prevents rounded addition from
		// extending a particle beyond K following births. This gives a bounded
		// candidate interval without dropping any generated live instance.
		if (nSlots <= MAX_EXACT_PARTICLE_INDEX - nIndex)
		{
			dDeath = (std::min)(dDeath, static_cast<double>(nIndex + nSlots) / stSettings.dRate);
		}
		if (dSeconds < dBirth || dSeconds >= dDeath)
		{
			continue;
		}
		double dAge = dSeconds - dBirth;
		// A represented deadline establishes liveness. Normalize a subtraction
		// that rounds onto the excluded age endpoint back into that interval.
		if (dAge >= stSettings.dLifetime)
		{
			dAge = std::nextafter(stSettings.dLifetime, 0.0);
		}
		const BillboardInstance stInstance = EvaluateInstance(stSettings, nIndex, dAge, arrOrigin);
		for (double dCoordinate : stInstance.arrCenter)
		{
			if (!GpuCoordinate(dCoordinate))
			{
				Assets::AddDiagnostic(out_arrDiagnostics, "particle_position", "$.particles",
									  "Evaluated particle world position exceeds finite binary32 coordinates.");
				return false;
			}
		}
		stCandidate.arrInstances[stCandidate.nCount] = stInstance;
		++stCandidate.nCount;
	}
	out_stFrame = stCandidate;
	return true;
}

} // namespace EngineNext::Rendering
