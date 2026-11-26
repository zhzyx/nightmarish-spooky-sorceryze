/**************************************************************************/
/*  Window.h                                                              */
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

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

namespace EngineNext::Platform::Windows
{

struct InputState
{
	std::array<bool, 256> arrKeys{};
	std::array<bool, 256> arrPressed{};
	std::array<bool, 5> arrMouseButtons{};
	std::int64_t nMouseDeltaX = 0;
	std::int64_t nMouseDeltaY = 0;
	std::int64_t nWheelDelta = 0;
	std::int64_t nHorizontalWheelDelta = 0;
	std::int32_t nPointerClientX = 0;
	std::int32_t nPointerClientY = 0;
	std::uint64_t nKeyEventCount = 0;
	std::uint64_t nMouseButtonEventCount = 0;
	std::uint64_t nRawKeyboardEventCount = 0;
	std::uint64_t nRawMouseEventCount = 0;
	std::uint64_t nFocusEventCount = 0;
	std::uint64_t nInputErrorCount = 0;
	std::uint64_t nLastEventQpc = 0;
	// Accepted keyboard/mouse messages only; focus/paint/resize are excluded.
	// Several receipts may coalesce into the latest state before one frame.
	std::uint64_t nInputRevision = 0;
	std::uint64_t nInputReceivedQpc = 0;
	std::uint64_t nQpcFrequency = 0;
	bool bFocused = false;
};

// All methods, state reads and destruction belong to the creating thread.
// The native handle is borrowed until Shutdown; WM_CLOSE only requests shutdown
// so the renderer can retire its GPU work before destroying the window.
class Window final
{
public:
	Window() noexcept;
	~Window();
	Window(const Window &) = delete;
	Window &operator=(const Window &) = delete;
	Window(Window &&) = delete;
	Window &operator=(Window &&) = delete;

	[[nodiscard]] bool Initialize(const wchar_t *pTitle, std::uint32_t nWidth, std::uint32_t nHeight, bool bHidden, std::string &out_strError);
	void Shutdown() noexcept;
	// Processes a bounded batch of this window's messages. Relative motion and
	// wheel deltas and key-press edges reset at entry; counters and held states persist.
	void PumpEvents() noexcept;
	[[nodiscard]] void *GetNativeHandle() const noexcept;
	[[nodiscard]] std::uint32_t GetWidth() const noexcept;
	[[nodiscard]] std::uint32_t GetHeight() const noexcept;
	[[nodiscard]] bool ShouldClose() const noexcept;
	[[nodiscard]] bool IsMinimized() const noexcept;
	[[nodiscard]] bool ConsumeResize() noexcept;
	[[nodiscard]] const InputState &GetInputState() const noexcept;

private:
	struct State;
	std::unique_ptr<State> ptrState;
};

} // namespace EngineNext::Platform::Windows
