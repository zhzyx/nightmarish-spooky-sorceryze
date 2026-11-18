/**************************************************************************/
/*  RhiComOwner.h                                                         */
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

namespace EngineNext::Rendering
{

// COM references stay in the backend and are retired only after queue fences.
template <typename Interface>
class ComOwner final
{
public:
	ComOwner() = default;
	~ComOwner()
	{
		Reset();
	}
	ComOwner(const ComOwner &) = delete;
	ComOwner &operator=(const ComOwner &) = delete;
	ComOwner(ComOwner &&stOther) noexcept : pValue(stOther.pValue)
	{
		stOther.pValue = nullptr;
	}
	ComOwner &operator=(ComOwner &&stOther) noexcept
	{
		if (this != &stOther)
		{
			Reset();
			pValue = stOther.pValue;
			stOther.pValue = nullptr;
		}
		return *this;
	}
	Interface *Get() const noexcept
	{
		return pValue;
	}
	Interface **Put() noexcept
	{
		Reset();
		return &pValue;
	}
	Interface *operator->() const noexcept
	{
		return pValue;
	}
	void Reset() noexcept
	{
		if (pValue != nullptr)
		{
			pValue->Release();
			pValue = nullptr;
		}
	}

private:
	Interface *pValue = nullptr;
};

} // namespace EngineNext::Rendering
