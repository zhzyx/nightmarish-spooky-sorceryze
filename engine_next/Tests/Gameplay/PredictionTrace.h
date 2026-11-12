/**************************************************************************/
/*  PredictionTrace.h                                                     */
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

#include <cstdint>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>

namespace EngineNext::GameplayTrace
{

struct TraceInput
{
	std::uint64_t nSequence;
	float fX;
	float fY;
	float fZ;
	std::uint32_t nStepMsec;
};

struct TraceState
{
	float fPositionX = 0.0F;
	float fPositionY = 0.0F;
	float fPositionZ = 0.0F;
	float fVelocityX = 0.0F;
	float fVelocityY = 0.0F;
	float fVelocityZ = 0.0F;
	std::uint64_t nConfirmedSequence = 0;
	std::uint64_t nServerTimeMsec = 0;
};

inline const std::vector<TraceInput> &GetModelInputs()
{
	static const std::vector<TraceInput> arrInputs{
		{ 8, 1.0F, 0.0F, 0.0F, 100 },
		{ 9, 0.0F, 1.0F, 0.0F, 100 },
		{ 10, 0.5F, 0.25F, -0.25F, 100 },
		{ 0, 1.0F, 0.0F, 0.0F, 100 },
		{ 11, 1.0F, 0.0F, 0.0F, 16 },
	};
	return arrInputs;
}

inline TraceState GetInitialState()
{
	TraceState stState;
	stState.fPositionX = 0.25F;
	stState.fPositionY = -0.5F;
	stState.fPositionZ = 2.0F;
	stState.nConfirmedSequence = 7;
	stState.nServerTimeMsec = 900;
	return stState;
}

inline const std::vector<TraceState> &GetBufferSamples()
{
	static const std::vector<TraceState> arrSamples = [] {
		TraceState stFirst;
		stFirst.fPositionX = 20.0F;
		stFirst.fVelocityX = 10.0F;
		stFirst.nConfirmedSequence = 2;
		stFirst.nServerTimeMsec = 300;
		TraceState stSecond;
		stSecond.fVelocityX = 10.0F;
		stSecond.nConfirmedSequence = 1;
		stSecond.nServerTimeMsec = 100;
		TraceState stThird;
		stThird.fPositionX = 30.0F;
		stThird.nConfirmedSequence = 3;
		stThird.nServerTimeMsec = 400;
		TraceState stFourth;
		stFourth.fPositionX = 40.0F;
		stFourth.nConfirmedSequence = 4;
		stFourth.nServerTimeMsec = 500;
		TraceState stDuplicate = stFourth;
		stDuplicate.fPositionX = 41.0F;
		TraceState stReplacement = stFourth;
		stReplacement.fPositionX = 42.0F;
		stReplacement.nConfirmedSequence = 5;
		return std::vector<TraceState>{ stFirst, stSecond, stThird, stFourth, stDuplicate, stReplacement };
	}();
	return arrSamples;
}

inline std::uint32_t GetFloatBits(float fValue)
{
	static_assert(sizeof(float) == sizeof(std::uint32_t), "The trace requires 32-bit float values.");
	std::uint32_t nBits = 0;
	std::memcpy(&nBits, &fValue, sizeof(nBits));
	return nBits;
}

inline void AppendState(std::string &out_strTrace, const TraceState &stState)
{
	std::ostringstream stream;
	stream << std::hex << std::setfill('0')
		   << std::setw(8) << GetFloatBits(stState.fPositionX) << ','
		   << std::setw(8) << GetFloatBits(stState.fPositionY) << ','
		   << std::setw(8) << GetFloatBits(stState.fPositionZ) << ','
		   << std::setw(8) << GetFloatBits(stState.fVelocityX) << ','
		   << std::setw(8) << GetFloatBits(stState.fVelocityY) << ','
		   << std::setw(8) << GetFloatBits(stState.fVelocityZ) << std::dec
		   << "|sequence=" << stState.nConfirmedSequence << "|time=" << stState.nServerTimeMsec;
	out_strTrace += stream.str();
}

inline void AppendModelResult(std::string &out_strTrace, std::size_t nIndex, std::uint32_t nStatus, const TraceState &stState)
{
	std::ostringstream stream;
	stream << "model-" << nIndex << "|status=" << nStatus << '|';
	out_strTrace += stream.str();
	AppendState(out_strTrace, stState);
	out_strTrace += '\n';
}

inline void AppendBufferAdd(std::string &out_strTrace, std::size_t nIndex, std::uint32_t nStatus, std::size_t nCount)
{
	std::ostringstream stream;
	stream << "buffer-add-" << nIndex << "|status=" << nStatus << "|count=" << nCount << '\n';
	out_strTrace += stream.str();
}

inline void AppendBufferSample(std::string &out_strTrace, const char *pLabel, std::uint32_t nStatus, bool bHasState, const TraceState &stState)
{
	std::ostringstream stream;
	stream << "buffer-sample-" << pLabel << "|status=" << nStatus << "|has_state=" << (bHasState ? 1 : 0);
	out_strTrace += stream.str();
	if (bHasState)
	{
		out_strTrace += '|';
		AppendState(out_strTrace, stState);
	}
	out_strTrace += '\n';
}

inline const char *GetLegacyGolden()
{
	return R"GOLDEN(model-0|status=0|3f19999a,bf000000,40000000,40600000,00000000,00000000|sequence=8|time=900
model-1|status=0|3f19999a,be19999a,40000000,00000000,40600000,00000000|sequence=9|time=900
model-2|status=0|3f466667,bd800001,3ff4cccd,3fe00000,3f600000,bf600000|sequence=10|time=900
model-3|status=1|3f466667,bd800001,3ff4cccd,3fe00000,3f600000,bf600000|sequence=10|time=900
model-4|status=1|3f466667,bd800001,3ff4cccd,3fe00000,3f600000,bf600000|sequence=10|time=900
buffer-add-0|status=0|count=1
buffer-add-1|status=0|count=2
buffer-sample-interpolated|status=3|has_state=1|41200000,00000000,00000000,41200000,00000000,00000000|sequence=2|time=200
buffer-add-2|status=0|count=3
buffer-add-3|status=0|count=3
buffer-add-4|status=2|count=3
buffer-add-5|status=0|count=3
buffer-sample-stale|status=5|has_state=1|42280000,00000000,00000000,00000000,00000000,00000000|sequence=5|time=500
buffer-sample-before|status=2|has_state=1|41a00000,00000000,00000000,41200000,00000000,00000000|sequence=2|time=300
buffer-sample-empty|status=0|has_state=0
)GOLDEN";
}

} // namespace EngineNext::GameplayTrace
