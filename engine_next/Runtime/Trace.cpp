/**************************************************************************/
/*  Trace.cpp                                                             */
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

#include "engine_next/include/EngineNext/Runtime/Trace.h"

namespace EngineNext::Runtime
{

Trace::~Trace()
{
	Close();
}

RuntimeStatus Trace::Open(const std::string &in_strPath)
{
	if (bOpen || in_strPath.empty())
	{
		return RuntimeStatus::InvalidState;
	}
	stStream.open(in_strPath, std::ios::out | std::ios::trunc);
	if (!stStream.is_open())
	{
		return RuntimeStatus::IoError;
	}
	bOpen = true;
	return RuntimeStatus::Ok;
}

RuntimeStatus Trace::Record(std::uint64_t nTick, const std::string &in_strEvent, EntityId in_stEntityId, std::uint64_t nValue)
{
	if (!bOpen)
	{
		return RuntimeStatus::Ok;
	}
	if (in_strEvent.empty() || in_strEvent.size() > 64)
	{
		return RuntimeStatus::InvalidState;
	}
	for (const char nCharacter : in_strEvent)
	{
		const bool bValid = (nCharacter >= 'a' && nCharacter <= 'z') ||
				(nCharacter >= '0' && nCharacter <= '9') || nCharacter == '_';
		if (!bValid)
		{
			return RuntimeStatus::InvalidParameter;
		}
	}
	stStream << "{\"tick\":" << nTick << ",\"event\":\"" << in_strEvent << "\",\"entity_id\":"
			 << in_stEntityId.nValue << ",\"value\":" << nValue << "}\n";
	stStream.flush();
	return stStream.good() ? RuntimeStatus::Ok : RuntimeStatus::IoError;
}

bool Trace::IsOpen() const noexcept
{
	return bOpen;
}

void Trace::Close() noexcept
{
	if (stStream.is_open())
	{
		stStream.flush();
		stStream.close();
	}
	bOpen = false;
}

} // namespace EngineNext::Runtime
