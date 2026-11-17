/**************************************************************************/
/*  TestParticles.cpp                                                     */
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
#include "engine_next/include/EngineNext/Rendering/ParticleState.h"
#include "engine_next/Tests/TestFramework.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>
#include <string>
#include <vector>

namespace
{

using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::BillboardInstance;
using EngineNext::Rendering::EvaluateParticles;
using EngineNext::Rendering::ParticleFrame;
using EngineNext::Rendering::ParticleSettings;
using EngineNext::Rendering::ValidateParticleSettings;

void CheckSameFrame(const ParticleFrame &stLeft, const ParticleFrame &stRight)
{
	ENGINE_NEXT_CHECK_EQ(stLeft.nCount, stRight.nCount);
	for (std::uint32_t nIndex = 0; nIndex < stLeft.nCount; ++nIndex)
	{
		const BillboardInstance &stA = stLeft.arrInstances[nIndex];
		const BillboardInstance &stB = stRight.arrInstances[nIndex];
		ENGINE_NEXT_CHECK_EQ(stA.stId.nEmitterId, stB.stId.nEmitterId);
		ENGINE_NEXT_CHECK_EQ(stA.stId.nSeed, stB.stId.nSeed);
		ENGINE_NEXT_CHECK_EQ(stA.stId.nSpawnIndex, stB.stId.nSpawnIndex);
		ENGINE_NEXT_CHECK_EQ(stA.arrCenter, stB.arrCenter);
		ENGINE_NEXT_CHECK_EQ(stA.dSize, stB.dSize);
		ENGINE_NEXT_CHECK_EQ(stA.arrColor, stB.arrColor);
		ENGINE_NEXT_CHECK_EQ(stA.dAge, stB.dAge);
	}
}

void Near(double dActual, double dExpected)
{
	ENGINE_NEXT_CHECK(std::isfinite(dActual));
	ENGINE_NEXT_CHECK(std::abs(dActual - dExpected) <= 1e-10 * (1 + std::abs(dExpected)));
}

} // namespace

ENGINE_NEXT_TEST("Particle defaults are bounded and disabled")
{
	ParticleSettings stSettings;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!stSettings.bEnabled);
	ENGINE_NEXT_CHECK(stSettings.bLoop);
	ENGINE_NEXT_CHECK_EQ(stSettings.nSeed, 1ULL);
	ENGINE_NEXT_CHECK(ValidateParticleSettings(stSettings, arrDiagnostics));
	ParticleFrame stFrame;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 0, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
}

ENGINE_NEXT_TEST("Particle replay uses exact seed time and increasing stable identity")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.nSeed = 0xffffffffffffffffULL;
	stSettings.arrPositionSpread = { 1, 2, 3 };
	stSettings.arrVelocitySpread = { 3, 2, 1 };
	static ParticleFrame stFirst;
	static ParticleFrame stSecond;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.7, { 10, -2, 4 }, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 100, { 0, 0, 0 }, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.7, { 10, -2, 4 }, stSecond, arrDiagnostics));
	CheckSameFrame(stFirst, stSecond);
	for (std::uint32_t nIndex = 0; nIndex < stFirst.nCount; ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stFirst.arrInstances[nIndex].stId.nSeed, stSettings.nSeed);
		ENGINE_NEXT_CHECK_EQ(stFirst.arrInstances[nIndex].stId.nSpawnIndex, nIndex);
	}
	stSettings.nSeed = 2;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.7, { 10, -2, 4 }, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK(stFirst.arrInstances[0].arrCenter != stSecond.arrInstances[0].arrCenter);
}

ENGINE_NEXT_TEST("Particle analytical motion color and size stay continuous")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 1;
	stSettings.dLifetime = 4;
	stSettings.arrVelocity = { 2, -4, 6 };
	stSettings.arrPosition = { 1, 2, 3 };
	stSettings.dStartSize = 2;
	stSettings.dEndSize = 6;
	stSettings.arrStartColor = { 1, 0, .5, 1 };
	stSettings.arrEndColor = { 0, 1, .5, 0 };
	static ParticleFrame stFirst;
	static ParticleFrame stSecond;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1, { 10, 20, 30 }, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.01, { 10, 20, 30 }, stSecond, arrDiagnostics));
	const BillboardInstance &stBefore = stFirst.arrInstances[0];
	const BillboardInstance &stAfter = stSecond.arrInstances[0];
	ENGINE_NEXT_CHECK_EQ(stBefore.stId.nSpawnIndex, stAfter.stId.nSpawnIndex);
	Near(stBefore.dAge, 1);
	Near(stBefore.arrCenter[0], 13);
	Near(stAfter.arrCenter[0] - stBefore.arrCenter[0], .02);
	Near(stAfter.arrCenter[1] - stBefore.arrCenter[1], -.04);
	Near(stBefore.dSize, 3);
	Near(stBefore.arrColor[0], .75);
	Near(stBefore.arrColor[1], .25);
	Near(stBefore.arrColor[3], .75);
}

ENGINE_NEXT_TEST("Particle birth death intervals include zero age and exclude expired age")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 4;
	stSettings.dLifetime = 1;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 0, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].dAge, 0);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 4U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[3].stId.nSpawnIndex, 4ULL);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[3].dAge, 0);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::nextafter(1.0, 0.0), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[stFrame.nCount - 1].stId.nSpawnIndex, 3ULL);
}

ENGINE_NEXT_TEST("One shot stops births and retains live tail without modulo restart")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.bLoop = false;
	stSettings.dRate = 4;
	stSettings.dLifetime = 1;
	stSettings.dDuration = 1;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 3U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[2].stId.nSpawnIndex, 3ULL);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.7, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 3ULL);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.75, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::numeric_limits<double>::max(), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
}

ENGINE_NEXT_TEST("Particle fixed budget accepts 4096 live entries")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 4096;
	stSettings.dLifetime = 1;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 4096U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[4095].stId.nSpawnIndex, 4096ULL);
	stSettings.dLifetime = 1.00001;
	ENGINE_NEXT_CHECK(!ValidateParticleSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Particle large times remain bounded and precision failures are transactional")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 16;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1e9, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 32U);
	for (std::uint32_t nIndex = 0; nIndex < stFrame.nCount; ++nIndex)
	{
		ENGINE_NEXT_CHECK(stFrame.arrInstances[nIndex].dAge >= 0);
		ENGINE_NEXT_CHECK(stFrame.arrInstances[nIndex].dAge < stSettings.dLifetime);
		ENGINE_NEXT_CHECK(std::isfinite(stFrame.arrInstances[nIndex].arrCenter[1]));
	}
	stFrame.nCount = 77;
	ENGINE_NEXT_CHECK(!EvaluateParticles(stSettings, std::numeric_limits<double>::max(), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 77U);
	stSettings.dRate = 0;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::numeric_limits<double>::max(), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
}

ENGINE_NEXT_TEST("Particle origin moves existing analytic instances without changing identity")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	static ParticleFrame stFirst;
	static ParticleFrame stSecond;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, .5, { 0, 0, 0 }, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, .5, { 3, -2, 4 }, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFirst.nCount, stSecond.nCount);
	for (std::uint32_t nIndex = 0; nIndex < stFirst.nCount; ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stFirst.arrInstances[nIndex].stId.nSpawnIndex, stSecond.arrInstances[nIndex].stId.nSpawnIndex);
		Near(stSecond.arrInstances[nIndex].arrCenter[0] - stFirst.arrInstances[nIndex].arrCenter[0], 3);
		Near(stSecond.arrInstances[nIndex].arrCenter[1] - stFirst.arrInstances[nIndex].arrCenter[1], -2);
		Near(stSecond.arrInstances[nIndex].arrCenter[2] - stFirst.arrInstances[nIndex].arrCenter[2], 4);
	}
}

ENGINE_NEXT_TEST("Particle settings reject every nonfinite input and invalid range")
{
	double ParticleSettings::*arrFields[] = { &ParticleSettings::dRate, &ParticleSettings::dLifetime, &ParticleSettings::dDuration,
											  &ParticleSettings::dStartSize, &ParticleSettings::dEndSize };
	for (double ParticleSettings::*pField : arrFields)
	{
		for (double dInvalid : { -1.0, std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
		{
			ParticleSettings stSettings;
			stSettings.*pField = dInvalid;
			Diagnostics arrDiagnostics;
			ENGINE_NEXT_CHECK(!ValidateParticleSettings(stSettings, arrDiagnostics));
		}
	}
	ParticleSettings stSettings;
	Diagnostics arrDiagnostics;
	stSettings.arrPosition[2] = 1e6 + 1;
	ENGINE_NEXT_CHECK(!ValidateParticleSettings(stSettings, arrDiagnostics));
	stSettings = ParticleSettings{};
	stSettings.arrVelocitySpread[0] = -1;
	ENGINE_NEXT_CHECK(!ValidateParticleSettings(stSettings, arrDiagnostics));
	stSettings = ParticleSettings{};
	stSettings.arrEndColor[3] = 1.001;
	ENGINE_NEXT_CHECK(!ValidateParticleSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Particle invalid time and world origin preserve old output")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	static ParticleFrame stFrame;
	stFrame.nCount = 57;
	Diagnostics arrDiagnostics;
	for (double dInvalid : { -1.0, std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN() })
	{
		ENGINE_NEXT_CHECK(!EvaluateParticles(stSettings, dInvalid, { 0, 0, 0 }, stFrame, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 57U);
	}
	ENGINE_NEXT_CHECK(!EvaluateParticles(stSettings, 0, { std::numeric_limits<double>::max(), 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 57U);
}

ENGINE_NEXT_TEST("Particle fractional rates include exact analytical birth instants")
{
	for (double dRate : { .1, .3, 1.3, 13.7, 127.1 })
	{
		ParticleSettings stSettings;
		stSettings.bEnabled = true;
		stSettings.dRate = dRate;
		static ParticleFrame stFrame;
		Diagnostics arrDiagnostics;
		for (std::uint64_t nIndex : { 1ULL, 7ULL, 1001ULL, 1000001ULL })
		{
			const double dTime = static_cast<double>(nIndex) / dRate;
			ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, dTime, { 0, 0, 0 }, stFrame, arrDiagnostics));
			ENGINE_NEXT_CHECK(stFrame.nCount > 0);
			ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[stFrame.nCount - 1].stId.nSpawnIndex, nIndex);
			ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[stFrame.nCount - 1].dAge, 0);
		}
	}
}

ENGINE_NEXT_TEST("Particle large exact indices either retain distinct ages or fail transactionally")
{
	for (double dRate : { .1, .3, 1.3, 127.1, 2047.3 })
	{
		ParticleSettings stSettings;
		stSettings.bEnabled = true;
		stSettings.dRate = dRate;
		stSettings.dLifetime = 1;
		static ParticleFrame stFrame;
		Diagnostics arrDiagnostics;
		stFrame.nCount = 37;
		const double dSeconds = static_cast<double>(EngineNext::Rendering::MAX_EXACT_PARTICLE_INDEX - 8) / dRate;
		if (EvaluateParticles(stSettings, dSeconds, { 0, 0, 0 }, stFrame, arrDiagnostics))
		{
			for (std::uint32_t nIndex = 1; nIndex < stFrame.nCount; ++nIndex)
			{
				ENGINE_NEXT_CHECK(stFrame.arrInstances[nIndex].stId.nSpawnIndex > stFrame.arrInstances[nIndex - 1].stId.nSpawnIndex);
				ENGINE_NEXT_CHECK(stFrame.arrInstances[nIndex].dAge < stFrame.arrInstances[nIndex - 1].dAge);
			}
		}
		else
		{
			ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 37U);
			ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
		}
	}
}

ENGINE_NEXT_TEST("Particle zero duration and zero emission are empty at every finite time")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.bLoop = false;
	stSettings.dDuration = 0;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	for (double dTime : { 0.0, 1.0, 1e100, std::numeric_limits<double>::max() })
	{
		ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, dTime, { 0, 0, 0 }, stFrame, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
	}
	stSettings.bLoop = true;
	stSettings.dRate = 0;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::numeric_limits<double>::max(), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
}

ENGINE_NEXT_TEST("Particle fractional active sets match a direct analytical reference")
{
	for (double dRate : { .1, .3, 1.3, 13.7 })
	{
		for (double dLifetime : { .001, .7, 2.1 })
		{
			ParticleSettings stSettings;
			stSettings.bEnabled = true;
			stSettings.dRate = dRate;
			stSettings.dLifetime = dLifetime;
			static ParticleFrame stFrame;
			Diagnostics arrDiagnostics;
			for (int nTimeIndex = 0; nTimeIndex <= 100; ++nTimeIndex)
			{
				const double dTime = nTimeIndex * .137;
				ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, dTime, { 0, 0, 0 }, stFrame, arrDiagnostics));
				std::uint32_t nExpectedCount = 0;
				for (std::uint64_t nSpawn = 0; nSpawn < 200; ++nSpawn)
				{
					const double dAge = dTime - static_cast<double>(nSpawn) / dRate;
					if (dAge >= 0 && dAge < dLifetime)
					{
						ENGINE_NEXT_CHECK(nExpectedCount < stFrame.nCount);
						if (nExpectedCount < stFrame.nCount)
						{
							ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[nExpectedCount].stId.nSpawnIndex, nSpawn);
							Near(stFrame.arrInstances[nExpectedCount].dAge, dAge);
						}
						++nExpectedCount;
					}
				}
				ENGINE_NEXT_CHECK_EQ(stFrame.nCount, nExpectedCount);
			}
		}
	}
}

ENGINE_NEXT_TEST("Particle replay matches a fixed integer hash golden instance")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.nSeed = 123456789;
	stSettings.arrPositionSpread = { 1, 2, 3 };
	stSettings.arrVelocitySpread = { 3, 2, 1 };
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, .5, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 9U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].arrCenter[0], -0x1.8fca7d18fb57fp+0);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].arrCenter[1], 0x1.fd242324fb846p-1);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].arrCenter[2], -0x1.291e1b8c98a28p+1);
}

ENGINE_NEXT_TEST("Particle identities include emitter and optional entity bindings")
{
	ParticleSettings stSettings;
	stSettings.nEmitterId = 51;
	stSettings.nSourceEntityId = 9223372036854775807ULL;
	stSettings.bEnabled = true;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 0, { 1, 2, 3 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nEmitterId, 51U);
	stSettings.nEmitterId = 0;
	ENGINE_NEXT_CHECK(!ValidateParticleSettings(stSettings, arrDiagnostics));
	stSettings.nEmitterId = 51;
	stSettings.nSourceEntityId = 0;
	ENGINE_NEXT_CHECK(!ValidateParticleSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Particle emitter aggregate validates identities and total live budget")
{
	std::vector<ParticleSettings> arrEmitters(2);
	arrEmitters[0].nEmitterId = 1;
	arrEmitters[1].nEmitterId = 2;
	arrEmitters[0].dRate = 2048;
	arrEmitters[0].dLifetime = 1;
	arrEmitters[1].dRate = 2048;
	arrEmitters[1].dLifetime = 1;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateParticleEmitters(arrEmitters, arrDiagnostics));
	arrEmitters[1].nEmitterId = 1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateParticleEmitters(arrEmitters, arrDiagnostics));
	arrEmitters[1].nEmitterId = 2;
	arrEmitters[1].dRate = 2048.1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateParticleEmitters(arrEmitters, arrDiagnostics));
	arrEmitters[0].dRate = 4096;
	arrEmitters[1].dRate = std::numeric_limits<double>::denorm_min();
	arrEmitters[1].dLifetime = .001;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateParticleEmitters(arrEmitters, arrDiagnostics));
	arrEmitters.assign(17, ParticleSettings{});
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateParticleEmitters(arrEmitters, arrDiagnostics));
}

ENGINE_NEXT_TEST("Particle array parser accepts defaults fields and exact integer identity")
{
	using EngineNext::Serialization::JsonValue;
	JsonValue stValue;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(R"([{
		"emitter_id":4294967295,"entity_id":9223372036854775807,"enabled":true,"loop":false,"seed":0,
		"rate":4,"lifetime":3,"duration":2,"position":[1,2,3],"position_spread":[2,3,4],
		"velocity":[-1,0,1],"velocity_spread":[1,2,3],"start_size":0.2,"end_size":0.4,
		"start_color":[1,0,0,1],"end_color":[0,1,0,0.1]}])",
														   stValue, strError));
	std::vector<ParticleSettings> arrEmitters;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseParticleEmitters(stValue, arrEmitters, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrEmitters.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].nEmitterId, 4294967295U);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].nSourceEntityId.value_or(0), 9223372036854775807ULL);
	ENGINE_NEXT_CHECK(arrEmitters[0].bEnabled);
	ENGINE_NEXT_CHECK(!arrEmitters[0].bLoop);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].nSeed, 0ULL);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].dRate, 4);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].dLifetime, 3);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].dDuration, 2);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].arrPosition[2], 3);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].arrVelocity[0], -1);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].dEndSize, .4);
	ENGINE_NEXT_CHECK_EQ(arrEmitters[0].arrEndColor[3], .1);
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ParseParticleEmitters(JsonValue::List{}, arrEmitters, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrEmitters.empty());
}

ENGINE_NEXT_TEST("Particle array parser rejects invalid optional inputs transactionally")
{
	using EngineNext::Serialization::JsonValue;
	for (const char *pText :
		 { "null", "{}", "[{}]", R"([{"emitter_id":0}])", R"([{"emitter_id":4294967296}])", R"([{"emitter_id":1.0}])", R"([{"emitter_id":1,"entity_id":0}])",
		   R"([{"emitter_id":1,"seed":-1}])", R"([{"emitter_id":1,"extra":0}])", R"([{"emitter_id":1,"enabled":1}])", R"([{"emitter_id":1,"loop":"false"}])",
		   R"([{"emitter_id":1,"position":[0,0]}])", R"([{"emitter_id":1,"start_color":[1,1,1]}])", R"([{"emitter_id":1,"end_color":[1,1,1,2]}])",
		   R"([{"emitter_id":1,"lifetime":-1}])", R"([{"emitter_id":1},{"emitter_id":1}])", R"([{"emitter_id":1,"rate":4096,"lifetime":1},{"emitter_id":2}])" })
	{
		JsonValue stValue;
		std::string strError;
		ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(pText, stValue, strError));
		std::vector<ParticleSettings> arrEmitters(1);
		arrEmitters[0].nEmitterId = 123;
		arrEmitters[0].dRate = 3;
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::ParseParticleEmitters(stValue, arrEmitters, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(arrEmitters.size(), 1U);
		ENGINE_NEXT_CHECK_EQ(arrEmitters[0].nEmitterId, 123U);
		ENGINE_NEXT_CHECK_EQ(arrEmitters[0].dRate, 3);
	}
}

ENGINE_NEXT_TEST("Particle lifecycle phases honor the declared live budget at frame times")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 20;
	stSettings.dLifetime = 2;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	for (int nFrame = 0; nFrame <= 240; ++nFrame)
	{
		ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, nFrame / 60.0, { 0, 0, 0 }, stFrame, arrDiagnostics));
		ENGINE_NEXT_CHECK(stFrame.nCount <= 40);
		for (std::uint32_t nIndex = 0; nIndex < stFrame.nCount; ++nIndex)
		{
			ENGINE_NEXT_CHECK(stFrame.arrInstances[nIndex].dAge >= 0);
			ENGINE_NEXT_CHECK(stFrame.arrInstances[nIndex].dAge < stSettings.dLifetime);
		}
	}
	ENGINE_NEXT_CHECK_EQ(stSettings.dRate, 20);
	ENGINE_NEXT_CHECK_EQ(stSettings.dLifetime, 2);
	stSettings.dRate = 10;
	stSettings.dLifetime = .3;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.4, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 3U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 12ULL);
}

ENGINE_NEXT_TEST("Particle phase boundaries distinguish births and nextafter neighbors")
{
	for (double dRate : { .1, .3, 1.3, 10.0, 20.0, 4095.5 })
	{
		ParticleSettings stSettings;
		stSettings.bEnabled = true;
		stSettings.dRate = dRate;
		stSettings.dLifetime = .3;
		static ParticleFrame stBefore;
		static ParticleFrame stAt;
		static ParticleFrame stAfter;
		Diagnostics arrDiagnostics;
		for (std::uint64_t nBirth : { 1ULL, 7ULL, 101ULL, 1000001ULL })
		{
			const double dTime = static_cast<double>(nBirth) / dRate;
			ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::nextafter(dTime, 0.0), { 0, 0, 0 }, stBefore, arrDiagnostics));
			ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, dTime, { 0, 0, 0 }, stAt, arrDiagnostics));
			ENGINE_NEXT_CHECK(
					EvaluateParticles(stSettings, std::nextafter(dTime, std::numeric_limits<double>::infinity()), { 0, 0, 0 }, stAfter, arrDiagnostics));
			ENGINE_NEXT_CHECK(stBefore.nCount == 0 || stBefore.arrInstances[stBefore.nCount - 1].stId.nSpawnIndex < nBirth);
			ENGINE_NEXT_CHECK(stAt.nCount > 0);
			ENGINE_NEXT_CHECK_EQ(stAt.arrInstances[stAt.nCount - 1].stId.nSpawnIndex, nBirth);
			ENGINE_NEXT_CHECK_EQ(stAt.arrInstances[stAt.nCount - 1].dAge, 0);
			ENGINE_NEXT_CHECK(stAfter.nCount > 0);
			ENGINE_NEXT_CHECK_EQ(stAfter.arrInstances[stAfter.nCount - 1].stId.nSpawnIndex, nBirth);
			ENGINE_NEXT_CHECK(stAfter.arrInstances[stAfter.nCount - 1].dAge > 0);
			const double dBudget = std::ceil(dRate * stSettings.dLifetime);
			ENGINE_NEXT_CHECK(stBefore.nCount <= dBudget && stAt.nCount <= dBudget && stAfter.nCount <= dBudget);
		}
	}
}

ENGINE_NEXT_TEST("Particle nextafter lifetime boundaries preserve half open expiry")
{
	for (double dLifetime : { std::nextafter(.3, 0.0), .3, std::nextafter(.3, 1.0), std::nextafter(2.0, 0.0), 2.0, std::nextafter(2.0, 3.0) })
	{
		ParticleSettings stSettings;
		stSettings.bEnabled = true;
		stSettings.dRate = 10;
		stSettings.dLifetime = dLifetime;
		static ParticleFrame stFrame;
		Diagnostics arrDiagnostics;
		for (double dTime : { std::nextafter(dLifetime, 0.0), dLifetime, std::nextafter(dLifetime, std::numeric_limits<double>::infinity()) })
		{
			ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, dTime, { 0, 0, 0 }, stFrame, arrDiagnostics));
			ENGINE_NEXT_CHECK(stFrame.nCount <= std::ceil(stSettings.dRate * dLifetime));
			if (dTime < dLifetime)
			{
				ENGINE_NEXT_CHECK(stFrame.nCount > 0 && stFrame.arrInstances[0].stId.nSpawnIndex == 0);
			}
			else
			{
				ENGINE_NEXT_CHECK(stFrame.nCount == 0 || stFrame.arrInstances[0].stId.nSpawnIndex > 0);
			}
		}
	}
}

ENGINE_NEXT_TEST("Particle maximum aggregate capacity remains valid throughout replay")
{
	std::vector<ParticleSettings> arrEmitters(2);
	arrEmitters[0].nEmitterId = 1;
	arrEmitters[0].bEnabled = true;
	arrEmitters[0].dRate = 20;
	arrEmitters[0].dLifetime = 2;
	arrEmitters[1].nEmitterId = 2;
	arrEmitters[1].bEnabled = true;
	arrEmitters[1].dRate = 2028;
	arrEmitters[1].dLifetime = 2;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateParticleEmitters(arrEmitters, arrDiagnostics));
	static ParticleFrame stFrame;
	for (int nFrame = 0; nFrame <= 240; ++nFrame)
	{
		std::uint32_t nTotal = 0;
		for (const ParticleSettings &stEmitter : arrEmitters)
		{
			ENGINE_NEXT_CHECK(EvaluateParticles(stEmitter, nFrame / 60.0, { 0, 0, 0 }, stFrame, arrDiagnostics));
			ENGINE_NEXT_CHECK(stFrame.nCount <= std::ceil(stEmitter.dRate * stEmitter.dLifetime));
			if (stFrame.nCount > 0)
			{
				ENGINE_NEXT_CHECK(stFrame.arrInstances[0].dAge >= 0 && stFrame.arrInstances[0].dAge < stEmitter.dLifetime);
			}
			nTotal += stFrame.nCount;
		}
		ENGINE_NEXT_CHECK(nTotal <= 4096);
	}
}

ENGINE_NEXT_TEST("Particle positive emission duration retains first birth through product underflow")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.bLoop = false;
	stSettings.dRate = 1e-200;
	stSettings.dDuration = 1e-200;
	stSettings.dLifetime = 1;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 0, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 0ULL);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, .5, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 1U);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
	stSettings.dDuration = 0;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 0, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
}

ENGINE_NEXT_TEST("Particle one-shot duration retains the represented side of birth boundaries")
{
	for (double dRate : { .3, 1.3, 3.0, 10.0, 20.0, 4095.5 })
	{
		ParticleSettings stSettings;
		stSettings.bEnabled = true;
		stSettings.bLoop = false;
		stSettings.dRate = dRate;
		stSettings.dLifetime = .5;
		const double dBirth = 1 / dRate;
		static ParticleFrame stFrame;
		Diagnostics arrDiagnostics;
		for (double dDuration : { std::nextafter(dBirth, 0.0), dBirth, std::nextafter(dBirth, std::numeric_limits<double>::infinity()) })
		{
			stSettings.dDuration = dDuration;
			ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, dBirth, { 0, 0, 0 }, stFrame, arrDiagnostics));
			const bool bIncludesBirth = stFrame.nCount > 0 && stFrame.arrInstances[stFrame.nCount - 1].stId.nSpawnIndex == 1;
			ENGINE_NEXT_CHECK_EQ(bIncludesBirth, dDuration > dBirth);
			ENGINE_NEXT_CHECK(stFrame.nCount <= std::ceil(stSettings.dRate * stSettings.dLifetime));
		}
	}
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.bLoop = false;
	stSettings.dRate = 3;
	stSettings.dLifetime = 2;
	stSettings.dDuration = std::nextafter(1.0 / 3.0, std::numeric_limits<double>::infinity());
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 1.0 / 3.0, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 2U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[1].stId.nSpawnIndex, 1ULL);
}

ENGINE_NEXT_TEST("Particle loop deaths use represented lifetime deadlines")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 1.0 / 3.0;
	stSettings.dLifetime = 2;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::nextafter(5.0, 0.0), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 1ULL);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, 5.0, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::nextafter(5.0, std::numeric_limits<double>::infinity()), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
}

ENGINE_NEXT_TEST("Particle short positive lifetime retains exact large timestamp birth")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 1;
	stSettings.dLifetime = .001;
	constexpr double dBirth = 1e15;
	static ParticleFrame stFrame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::nextafter(dBirth, 0.0), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, dBirth, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 1U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].stId.nSpawnIndex, 1000000000000000ULL);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].dAge, 0);
	ENGINE_NEXT_CHECK(EvaluateParticles(stSettings, std::nextafter(dBirth, std::numeric_limits<double>::infinity()), { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 0U);
}

ENGINE_NEXT_TEST("Particle future birth time collisions fail transactionally")
{
	const std::array<std::array<double, 2>, 2> arrCases{ { { 20, 450359962737044.6 }, { 3, 3002399751580297.5 } } };
	for (const std::array<double, 2> &arrCase : arrCases)
	{
		ParticleSettings stSettings;
		stSettings.bEnabled = true;
		stSettings.dRate = arrCase[0];
		stSettings.dLifetime = .001;
		static ParticleFrame stFrame;
		stFrame.nCount = 37;
		stFrame.arrInstances[0].dAge = 42;
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(!EvaluateParticles(stSettings, arrCase[1], { 0, 0, 0 }, stFrame, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 37U);
		ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].dAge, 42);
		ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	}
}

ENGINE_NEXT_TEST("Particle earlier candidate time collisions fail with distinct latest neighbors")
{
	ParticleSettings stSettings;
	stSettings.bEnabled = true;
	stSettings.dRate = 3;
	stSettings.dLifetime = 1;
	constexpr std::uint64_t nLastBirth = 9007199254739991ULL;
	constexpr double dTime = 3002399751579997.0;
	ENGINE_NEXT_CHECK(static_cast<double>(nLastBirth) / 3 > static_cast<double>(nLastBirth - 1) / 3);
	ENGINE_NEXT_CHECK(static_cast<double>(nLastBirth + 1) / 3 > static_cast<double>(nLastBirth) / 3);
	ENGINE_NEXT_CHECK_EQ(static_cast<double>(nLastBirth - 2) / 3, static_cast<double>(nLastBirth - 1) / 3);
	static ParticleFrame stFrame;
	stFrame.nCount = 37;
	stFrame.arrInstances[0].dAge = 42;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EvaluateParticles(stSettings, dTime, { 0, 0, 0 }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nCount, 37U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrInstances[0].dAge, 42);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}
