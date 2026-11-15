/**************************************************************************/
/*  Window.cpp                                                            */
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

#include "engine_next/Platform/Windows/Window.h"

#include <algorithm>
#include <cstdlib>
#include <limits>
#include <new>
#include <utility>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

namespace EngineNext::Platform::Windows
{
namespace
{

constexpr wchar_t WINDOW_CLASS_NAME[] = L"EngineNextVisualWindow";
constexpr std::uint32_t MAX_MESSAGES_PER_PUMP = 4096;

std::uint64_t ReadQpc() noexcept
{
	LARGE_INTEGER stCounter{};
	if (!QueryPerformanceCounter(&stCounter) || stCounter.QuadPart < 0)
	{
		return 0;
	}
	return static_cast<std::uint64_t>(stCounter.QuadPart);
}

void AddDelta(std::int64_t &out_nTotal, std::int64_t nDelta) noexcept
{
	if (nDelta > 0 && out_nTotal > std::numeric_limits<std::int64_t>::max() - nDelta)
	{
		out_nTotal = std::numeric_limits<std::int64_t>::max();
	}
	else if (nDelta < 0 && out_nTotal < std::numeric_limits<std::int64_t>::min() - nDelta)
	{
		out_nTotal = std::numeric_limits<std::int64_t>::min();
	}
	else
	{
		out_nTotal += nDelta;
	}
}

} // namespace

struct Window::State
{
	HWND hWindow = nullptr;
	DWORD nOwnerThread = 0;
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	InputState stInput;
	bool bCloseRequested = true;
	bool bMinimized = false;
	bool bResized = false;
	bool bHaveAbsoluteMouse = false;
	HANDLE hAbsoluteMouseDevice = nullptr;
	LONG nAbsoluteMouseX = 0;
	LONG nAbsoluteMouseY = 0;

	void RequireOwnerThread() const noexcept
	{
		if (nOwnerThread != GetCurrentThreadId())
		{
			// A callback still refers to this state while HWND exists. Freeing it
			// on a different thread would violate the window lifetime invariant.
			std::abort();
		}
	}

	void SetKey(std::uint32_t nKey, bool bPressed) noexcept
	{
		if (nKey < stInput.arrKeys.size() && stInput.arrKeys[nKey] != bPressed)
		{
			stInput.arrKeys[nKey] = bPressed;
			++stInput.nKeyEventCount;
			stInput.nLastEventQpc = ReadQpc();
		}
	}

	void SetMouseButton(std::size_t nButton, bool bPressed) noexcept
	{
		if (nButton < stInput.arrMouseButtons.size() && stInput.arrMouseButtons[nButton] != bPressed)
		{
			stInput.arrMouseButtons[nButton] = bPressed;
			++stInput.nMouseButtonEventCount;
			stInput.nLastEventQpc = ReadQpc();
		}
	}

	void SetKeyboardKey(std::uint32_t nKey, std::uint32_t nScanCode, bool bExtended, bool bPressed) noexcept
	{
		std::uint32_t nSideKey = nKey;
		if (nKey == VK_SHIFT)
		{
			nSideKey = MapVirtualKeyW(nScanCode, MAPVK_VSC_TO_VK_EX);
		}
		else if (nKey == VK_CONTROL)
		{
			nSideKey = bExtended ? VK_RCONTROL : VK_LCONTROL;
		}
		else if (nKey == VK_MENU)
		{
			nSideKey = bExtended ? VK_RMENU : VK_LMENU;
		}
		SetKey(nSideKey, bPressed);
		if (nSideKey == VK_LSHIFT || nSideKey == VK_RSHIFT)
		{
			SetKey(VK_SHIFT, stInput.arrKeys[VK_LSHIFT] || stInput.arrKeys[VK_RSHIFT]);
		}
		else if (nSideKey == VK_LCONTROL || nSideKey == VK_RCONTROL)
		{
			SetKey(VK_CONTROL, stInput.arrKeys[VK_LCONTROL] || stInput.arrKeys[VK_RCONTROL]);
		}
		else if (nSideKey == VK_LMENU || nSideKey == VK_RMENU)
		{
			SetKey(VK_MENU, stInput.arrKeys[VK_LMENU] || stInput.arrKeys[VK_RMENU]);
		}
	}

	void ReleaseInput() noexcept
	{
		for (std::uint32_t nKey = 0; nKey < stInput.arrKeys.size(); ++nKey)
		{
			SetKey(nKey, false);
		}
		for (std::size_t nButton = 0; nButton < stInput.arrMouseButtons.size(); ++nButton)
		{
			SetMouseButton(nButton, false);
		}
		bHaveAbsoluteMouse = false;
	}

	void SetFocus(bool bFocused) noexcept
	{
		if (stInput.bFocused != bFocused)
		{
			stInput.bFocused = bFocused;
			++stInput.nFocusEventCount;
			stInput.nLastEventQpc = ReadQpc();
		}
		if (!bFocused)
		{
			ReleaseInput();
			stInput.nMouseDeltaX = 0;
			stInput.nMouseDeltaY = 0;
			stInput.nWheelDelta = 0;
			stInput.nHorizontalWheelDelta = 0;
		}
	}

	void UpdateSize(HWND hTarget) noexcept
	{
		RECT stClient{};
		if (GetClientRect(hTarget, &stClient))
		{
			const std::uint32_t nNewWidth = static_cast<std::uint32_t>(std::max<LONG>(stClient.right - stClient.left, 0));
			const std::uint32_t nNewHeight = static_cast<std::uint32_t>(std::max<LONG>(stClient.bottom - stClient.top, 0));
			if (nWidth != nNewWidth || nHeight != nNewHeight)
			{
				nWidth = nNewWidth;
				nHeight = nNewHeight;
				bResized = true;
			}
		}
	}

	void ReadRawMouse(const RAWINPUT &stRawInput) noexcept
	{
		const RAWMOUSE &stMouse = stRawInput.data.mouse;
		++stInput.nRawMouseEventCount;
		if ((stMouse.usFlags & MOUSE_MOVE_ABSOLUTE) != 0)
		{
			const bool bVirtualDesktop = (stMouse.usFlags & MOUSE_VIRTUAL_DESKTOP) != 0;
			const int nOriginX = bVirtualDesktop ? GetSystemMetrics(SM_XVIRTUALSCREEN) : 0;
			const int nOriginY = bVirtualDesktop ? GetSystemMetrics(SM_YVIRTUALSCREEN) : 0;
			const int nDesktopWidth = GetSystemMetrics(bVirtualDesktop ? SM_CXVIRTUALSCREEN : SM_CXSCREEN);
			const int nDesktopHeight = GetSystemMetrics(bVirtualDesktop ? SM_CYVIRTUALSCREEN : SM_CYSCREEN);
			const LONG nPositionX = nOriginX + MulDiv(std::clamp<LONG>(stMouse.lLastX, 0, 65535), nDesktopWidth, 65535);
			const LONG nPositionY = nOriginY + MulDiv(std::clamp<LONG>(stMouse.lLastY, 0, 65535), nDesktopHeight, 65535);
			if (bHaveAbsoluteMouse && hAbsoluteMouseDevice == stRawInput.header.hDevice)
			{
				AddDelta(stInput.nMouseDeltaX, static_cast<std::int64_t>(nPositionX) - nAbsoluteMouseX);
				AddDelta(stInput.nMouseDeltaY, static_cast<std::int64_t>(nPositionY) - nAbsoluteMouseY);
			}
			nAbsoluteMouseX = nPositionX;
			nAbsoluteMouseY = nPositionY;
			hAbsoluteMouseDevice = stRawInput.header.hDevice;
			bHaveAbsoluteMouse = true;
		}
		else
		{
			AddDelta(stInput.nMouseDeltaX, stMouse.lLastX);
			AddDelta(stInput.nMouseDeltaY, stMouse.lLastY);
			bHaveAbsoluteMouse = false;
		}
		for (std::size_t nButton = 0; nButton < stInput.arrMouseButtons.size(); ++nButton)
		{
			const USHORT nDownFlag = static_cast<USHORT>(1U << (nButton * 2));
			const USHORT nUpFlag = static_cast<USHORT>(nDownFlag << 1U);
			if ((stMouse.usButtonFlags & nDownFlag) != 0)
			{
				SetMouseButton(nButton, true);
			}
			if ((stMouse.usButtonFlags & nUpFlag) != 0)
			{
				SetMouseButton(nButton, false);
			}
		}
		const std::int16_t nWheel = static_cast<std::int16_t>(stMouse.usButtonData);
		if ((stMouse.usButtonFlags & RI_MOUSE_WHEEL) != 0)
		{
			AddDelta(stInput.nWheelDelta, nWheel);
		}
		if ((stMouse.usButtonFlags & RI_MOUSE_HWHEEL) != 0)
		{
			AddDelta(stInput.nHorizontalWheelDelta, nWheel);
		}
		stInput.nLastEventQpc = ReadQpc();
	}

	void ReadRawInput(LPARAM nParameter) noexcept
	{
		RAWINPUT stRawInput{};
		UINT nSize = sizeof(stRawInput);
		const UINT nReadSize = GetRawInputData(reinterpret_cast<HRAWINPUT>(nParameter), RID_INPUT, &stRawInput, &nSize, sizeof(RAWINPUTHEADER));
		if (nReadSize == static_cast<UINT>(-1) || nReadSize < sizeof(RAWINPUTHEADER))
		{
			++stInput.nInputErrorCount;
			return;
		}
		if (!stInput.bFocused)
		{
			return;
		}
		if (stRawInput.header.dwType == RIM_TYPEMOUSE && nReadSize >= sizeof(RAWINPUTHEADER) + sizeof(RAWMOUSE))
		{
			ReadRawMouse(stRawInput);
		}
		else if (stRawInput.header.dwType == RIM_TYPEKEYBOARD && nReadSize >= sizeof(RAWINPUTHEADER) + sizeof(RAWKEYBOARD))
		{
			++stInput.nRawKeyboardEventCount;
			const RAWKEYBOARD &stKeyboard = stRawInput.data.keyboard;
			if (stKeyboard.MakeCode != KEYBOARD_OVERRUN_MAKE_CODE && stKeyboard.VKey < 255)
			{
				SetKeyboardKey(stKeyboard.VKey, stKeyboard.MakeCode, (stKeyboard.Flags & RI_KEY_E0) != 0, (stKeyboard.Flags & RI_KEY_BREAK) == 0);
			}
			else
			{
				++stInput.nInputErrorCount;
			}
			stInput.nLastEventQpc = ReadQpc();
		}
	}

	static LRESULT CALLBACK WindowProcedure(HWND hTarget, UINT nMessage, WPARAM nWordParameter, LPARAM nLongParameter)
	{
		State *pState = reinterpret_cast<State *>(GetWindowLongPtrW(hTarget, GWLP_USERDATA));
		if (nMessage == WM_NCCREATE)
		{
			const CREATESTRUCTW *pCreate = reinterpret_cast<const CREATESTRUCTW *>(nLongParameter);
			pState = static_cast<State *>(pCreate->lpCreateParams);
			SetLastError(ERROR_SUCCESS);
			if (SetWindowLongPtrW(hTarget, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(pState)) == 0 && GetLastError() != ERROR_SUCCESS)
			{
				return FALSE;
			}
			pState->hWindow = hTarget;
		}
		if (pState == nullptr)
		{
			return DefWindowProcW(hTarget, nMessage, nWordParameter, nLongParameter);
		}
		switch (nMessage)
		{
			case WM_CLOSE:
				pState->bCloseRequested = true;
				return 0;
			case WM_DESTROY:
				pState->bCloseRequested = true;
				pState->SetFocus(false);
				return 0;
			case WM_NCDESTROY:
				SetWindowLongPtrW(hTarget, GWLP_USERDATA, 0);
				pState->hWindow = nullptr;
				return DefWindowProcW(hTarget, nMessage, nWordParameter, nLongParameter);
			case WM_SIZE:
				pState->bMinimized = nWordParameter == SIZE_MINIMIZED;
				pState->UpdateSize(hTarget);
				return 0;
			case WM_SETFOCUS:
				pState->SetFocus(true);
				return 0;
			case WM_KILLFOCUS:
				pState->SetFocus(false);
				return 0;
			case WM_INPUT:
				pState->ReadRawInput(nLongParameter);
				// DefWindowProc performs the required foreground WM_INPUT cleanup.
				return DefWindowProcW(hTarget, nMessage, nWordParameter, nLongParameter);
			case WM_KEYDOWN:
			case WM_SYSKEYDOWN:
				if (pState->stInput.bFocused)
				{
					pState->SetKeyboardKey(static_cast<std::uint32_t>(nWordParameter), static_cast<std::uint32_t>((nLongParameter >> 16) & 0xFF), (nLongParameter & (1L << 24)) != 0, true);
				}
				break;
			case WM_KEYUP:
			case WM_SYSKEYUP:
				pState->SetKeyboardKey(static_cast<std::uint32_t>(nWordParameter), static_cast<std::uint32_t>((nLongParameter >> 16) & 0xFF), (nLongParameter & (1L << 24)) != 0, false);
				break;
			case WM_MOUSEMOVE:
				pState->stInput.nPointerClientX = static_cast<std::int16_t>(LOWORD(nLongParameter));
				pState->stInput.nPointerClientY = static_cast<std::int16_t>(HIWORD(nLongParameter));
				break;
			case WM_DPICHANGED:
			{
				const RECT *pSuggested = reinterpret_cast<const RECT *>(nLongParameter);
				SetWindowPos(hTarget, nullptr, pSuggested->left, pSuggested->top, pSuggested->right - pSuggested->left, pSuggested->bottom - pSuggested->top, SWP_NOZORDER | SWP_NOACTIVATE);
				return 0;
			}
			case WM_ERASEBKGND:
				return 1;
			default:
				break;
		}
		return DefWindowProcW(hTarget, nMessage, nWordParameter, nLongParameter);
	}
};

Window::Window() noexcept = default;

Window::~Window()
{
	Shutdown();
}

bool Window::Initialize(const wchar_t *pTitle, std::uint32_t nWidth, std::uint32_t nHeight, bool bHidden, std::string &out_strError)
{
	out_strError.clear();
	if (ptrState != nullptr)
	{
		out_strError = "Window is already initialized.";
		return false;
	}
	if (pTitle == nullptr || pTitle[0] == L'\0' || nWidth == 0 || nHeight == 0 || nWidth > 32767 || nHeight > 32767)
	{
		out_strError = "Window title and client dimensions (1..32767 pixels) are required.";
		return false;
	}
	std::unique_ptr<State> ptrNewState(new (std::nothrow) State);
	if (ptrNewState == nullptr)
	{
		out_strError = "Window state allocation failed.";
		return false;
	}
	ptrNewState->nOwnerThread = GetCurrentThreadId();
	LARGE_INTEGER stFrequency{};
	if (!QueryPerformanceFrequency(&stFrequency) || stFrequency.QuadPart <= 0)
	{
		out_strError = "QueryPerformanceFrequency failed.";
		return false;
	}
	ptrNewState->stInput.nQpcFrequency = static_cast<std::uint64_t>(stFrequency.QuadPart);
	const HINSTANCE hInstance = GetModuleHandleW(nullptr);
	WNDCLASSEXW stClass{};
	stClass.cbSize = sizeof(stClass);
	stClass.style = CS_HREDRAW | CS_VREDRAW;
	stClass.lpfnWndProc = State::WindowProcedure;
	stClass.hInstance = hInstance;
	stClass.hCursor = LoadCursorW(nullptr, MAKEINTRESOURCEW(32512));
	stClass.lpszClassName = WINDOW_CLASS_NAME;
	if (RegisterClassExW(&stClass) == 0)
	{
		WNDCLASSEXW stRegistered{};
		stRegistered.cbSize = sizeof(stRegistered);
		if (GetLastError() != ERROR_CLASS_ALREADY_EXISTS || !GetClassInfoExW(hInstance, WINDOW_CLASS_NAME, &stRegistered) || stRegistered.lpfnWndProc != State::WindowProcedure)
		{
			out_strError = "RegisterClassExW failed: " + std::to_string(GetLastError());
			return false;
		}
	}
	const DPI_AWARENESS_CONTEXT hPreviousDpi = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
	RECT stRectangle{ 0, 0, static_cast<LONG>(nWidth), static_cast<LONG>(nHeight) };
	const DWORD nStyle = WS_OVERLAPPEDWINDOW;
	const bool bRectangleValid = AdjustWindowRectExForDpi(&stRectangle, nStyle, FALSE, 0, GetDpiForSystem()) != FALSE;
	if (!bRectangleValid)
	{
		const DWORD nError = GetLastError();
		if (hPreviousDpi != nullptr)
		{
			SetThreadDpiAwarenessContext(hPreviousDpi);
		}
		out_strError = "AdjustWindowRectExForDpi failed: " + std::to_string(nError);
		return false;
	}
	ptrNewState->hWindow = CreateWindowExW(0, WINDOW_CLASS_NAME, pTitle, nStyle, CW_USEDEFAULT, CW_USEDEFAULT, stRectangle.right - stRectangle.left, stRectangle.bottom - stRectangle.top, nullptr, nullptr, hInstance, ptrNewState.get());
	const DWORD nCreateError = GetLastError();
	if (hPreviousDpi != nullptr)
	{
		SetThreadDpiAwarenessContext(hPreviousDpi);
	}
	if (ptrNewState->hWindow == nullptr)
	{
		out_strError = "CreateWindowExW failed: " + std::to_string(nCreateError);
		return false;
	}
	// A null target routes raw input to the focused window on this process.
	// Keeping legacy messages preserves system shortcuts and text input.
	const RAWINPUTDEVICE arrDevices[] = { { 0x01, 0x02, 0, nullptr }, { 0x01, 0x06, 0, nullptr } };
	if (!RegisterRawInputDevices(arrDevices, 2, sizeof(RAWINPUTDEVICE)))
	{
		const DWORD nError = GetLastError();
		DestroyWindow(ptrNewState->hWindow);
		out_strError = "RegisterRawInputDevices failed: " + std::to_string(nError);
		return false;
	}
	ptrNewState->bCloseRequested = false;
	ptrNewState->UpdateSize(ptrNewState->hWindow);
	ptrNewState->bResized = false;
	ptrState = std::move(ptrNewState);
	if (!bHidden)
	{
		ShowWindow(ptrState->hWindow, SW_SHOW);
		UpdateWindow(ptrState->hWindow);
	}
	return true;
}

void Window::Shutdown() noexcept
{
	if (ptrState == nullptr)
	{
		return;
	}
	ptrState->RequireOwnerThread();
	if (ptrState->hWindow != nullptr && !DestroyWindow(ptrState->hWindow))
	{
		// Destruction failure would leave the OS callback pointing into freed state.
		std::abort();
	}
	ptrState.reset();
}

void Window::PumpEvents() noexcept
{
	if (ptrState == nullptr)
	{
		return;
	}
	ptrState->RequireOwnerThread();
	if (ptrState->hWindow == nullptr)
	{
		return;
	}
	ptrState->stInput.nMouseDeltaX = 0;
	ptrState->stInput.nMouseDeltaY = 0;
	ptrState->stInput.nWheelDelta = 0;
	ptrState->stInput.nHorizontalWheelDelta = 0;
	MSG stMessage{};
	for (std::uint32_t nIndex = 0; nIndex < MAX_MESSAGES_PER_PUMP && PeekMessageW(&stMessage, ptrState->hWindow, 0, 0, PM_REMOVE); ++nIndex)
	{
		if (stMessage.message == WM_QUIT)
		{
			ptrState->bCloseRequested = true;
			return;
		}
		TranslateMessage(&stMessage);
		DispatchMessageW(&stMessage);
	}
}

void *Window::GetNativeHandle() const noexcept
{
	return ptrState != nullptr ? ptrState->hWindow : nullptr;
}

std::uint32_t Window::GetWidth() const noexcept
{
	return ptrState != nullptr ? ptrState->nWidth : 0;
}

std::uint32_t Window::GetHeight() const noexcept
{
	return ptrState != nullptr ? ptrState->nHeight : 0;
}

bool Window::ShouldClose() const noexcept
{
	return ptrState == nullptr || ptrState->bCloseRequested;
}

bool Window::IsMinimized() const noexcept
{
	return ptrState != nullptr && ptrState->bMinimized;
}

bool Window::ConsumeResize() noexcept
{
	if (ptrState == nullptr)
	{
		return false;
	}
	ptrState->RequireOwnerThread();
	const bool bResized = ptrState->bResized;
	ptrState->bResized = false;
	return bResized;
}

const InputState &Window::GetInputState() const noexcept
{
	static const InputState stEmptyInput;
	return ptrState != nullptr ? ptrState->stInput : stEmptyInput;
}

} // namespace EngineNext::Platform::Windows
