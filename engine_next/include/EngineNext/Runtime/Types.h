/**************************************************************************/
/*  Types.h                                                               */
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

namespace EngineNext::Runtime
{

enum class RuntimeStatus : std::uint8_t
{
	Ok = 0,
	InvalidParameter = 1,
	AlreadyExists = 2,
	NotFound = 3,
	InvalidState = 4,
	IoError = 5,
};

enum class RuntimeRole : std::uint8_t
{
	Server = 1,
	Client = 2,
};

struct EntityId
{
	std::uint64_t nValue = 0;

	[[nodiscard]] constexpr bool IsValid() const noexcept
	{
		return nValue != 0;
	}
};

[[nodiscard]] constexpr bool operator==(EntityId in_stLeft, EntityId in_stRight) noexcept
{
	return in_stLeft.nValue == in_stRight.nValue;
}

[[nodiscard]] constexpr bool operator!=(EntityId in_stLeft, EntityId in_stRight) noexcept
{
	return !(in_stLeft == in_stRight);
}

[[nodiscard]] constexpr bool operator<(EntityId in_stLeft, EntityId in_stRight) noexcept
{
	return in_stLeft.nValue < in_stRight.nValue;
}

} // namespace EngineNext::Runtime
