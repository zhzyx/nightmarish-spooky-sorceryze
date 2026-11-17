/**************************************************************************/
/*  TestWebPlatformWindows.cc                                             */
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

#include "editor/docks/WebPlatformWindows.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <objbase.h>
#include <wrl.h>

// Match the backend's explicit COM setup under Godot's lean Windows wrapper.
#include <WebView2.h>

#include <chrono>
#include <iostream>
#include <memory>
#include <string>

namespace
{
using Microsoft::WRL::Callback;

void Pump()
{
	MSG stMessage;
	while (PeekMessageW(&stMessage, nullptr, 0, 0, PM_REMOVE))
	{
		TranslateMessage(&stMessage);
		DispatchMessageW(&stMessage);
	}
	Sleep(5);
}

std::string Source(WebPlatformWindows *pNative)
{
	ICoreWebView2 *pView = static_cast<ICoreWebView2 *>(pNative->TestGetWebView());
	LPWSTR pSource = nullptr;
	if (!pView || FAILED(pView->get_Source(&pSource)) || !pSource)
	{
		return {};
	}
	// Fixtures deliberately use only ASCII URLs.
	const std::wstring strWide(pSource);
	CoTaskMemFree(pSource);
	std::string strResult;
	for (const wchar_t nCharacter : strWide)
	{
		if (nCharacter > 127)
		{
			return {};
		}
		strResult.push_back(static_cast<char>(nCharacter));
	}
	return strResult;
}

bool WaitForPage(WebPlatformWindows *pNative, const std::string &strUrl)
{
	const std::chrono::steady_clock::time_point stDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(40);
	while (std::chrono::steady_clock::now() < stDeadline)
	{
		Pump();
		if (Source(pNative) == strUrl && pNative->GetStatus().find("Connected") != std::string::npos)
		{
			return true;
		}
	}
	std::cerr << "PAGE_FAILURE " << pNative->GetStatus() << '\n';
	return false;
}

struct ScriptResult
{
	bool bFinished = false;
	HRESULT nResult = E_PENDING;
	std::wstring strValue;
};

bool Evaluate(WebPlatformWindows *pNative, const std::wstring &strScript, const std::wstring &strExpected)
{
	ICoreWebView2 *pView = static_cast<ICoreWebView2 *>(pNative->TestGetWebView());
	if (!pView)
	{
		return false;
	}
	const std::shared_ptr<ScriptResult> ptrResult = std::make_shared<ScriptResult>();
	const HRESULT nResult = pView->ExecuteScript(strScript.c_str(), Callback<ICoreWebView2ExecuteScriptCompletedHandler>([ptrResult](HRESULT nError, LPCWSTR pValue) -> HRESULT
																														 {
																															 ptrResult->nResult = nError;
																															 ptrResult->strValue = pValue ? pValue : L"";
																															 ptrResult->bFinished = true;
																															 return S_OK;
																														 })
																			.Get());
	const std::chrono::steady_clock::time_point stDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
	while (SUCCEEDED(nResult) && !ptrResult->bFinished && std::chrono::steady_clock::now() < stDeadline)
	{
		Pump();
	}
	if (!ptrResult->bFinished || FAILED(ptrResult->nResult) || ptrResult->strValue != strExpected)
	{
		std::wcerr << L"SCRIPT_FAILURE expected=" << strExpected << L" actual=" << ptrResult->strValue << L'\n';
		return false;
	}
	return true;
}

void Drain()
{
	const std::chrono::steady_clock::time_point stDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
	while (std::chrono::steady_clock::now() < stDeadline)
	{
		Pump();
	}
}
} //namespace

int main(int nArgc, char **ppArgv)
{
	if (nArgc != 3 || GetEnvironmentVariableW(L"GODOT_WEB_PLATFORM_TEST_DATA", nullptr, 0) == 0)
	{
		return 2;
	}
	const HRESULT nCom = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
	if (FAILED(nCom))
	{
		return 3;
	}
	const HWND pForeground = GetForegroundWindow();
	// Never show, activate, or focus the parent, including failure paths.
	const HWND pWindow = CreateWindowExW(WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW, L"STATIC", L"Godot WebView2 hidden validation", WS_POPUP, 0, 0, 800, 600, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
	if (!pWindow)
	{
		return 4;
	}
	const std::string strBase = ppArgv[1];
	const std::string strExternal = ppArgv[2];
	for (int nIndex = 0; nIndex < 4; ++nIndex)
	{
		std::unique_ptr<WebPlatformNative> ptrPending(WebPlatformNative::Create(pWindow, strBase + "/"));
		if (!ptrPending)
		{
			return 5;
		}
		ptrPending.reset();
	}
	Drain();
	std::unique_ptr<WebPlatformWindows> ptrNative(static_cast<WebPlatformWindows *>(WebPlatformNative::Create(pWindow, strBase + "/")));
	if (!ptrNative)
	{
		return 6;
	}
	ptrNative->SetBounds(100, 200, 1000, 600, 1600, 1200);
	ptrNative->SetVisible(true);
	if (!WaitForPage(ptrNative.get(), strBase + "/"))
	{
		return 7;
	}
	ICoreWebView2Controller *pController = static_cast<ICoreWebView2Controller *>(ptrNative->TestGetController());
	RECT stBounds;
	BOOL bVisible = FALSE;
	HWND pHost = nullptr;
	pController->get_Bounds(&stBounds);
	pController->get_IsVisible(&bVisible);
	pController->get_ParentWindow(&pHost);
	RECT stHost;
	GetWindowRect(pHost, &stHost);
	MapWindowPoints(nullptr, pWindow, reinterpret_cast<POINT *>(&stHost), 2);
	if (stBounds.left != 0 || stBounds.top != 0 || stBounds.right != 500 || stBounds.bottom != 300 || stHost.left != 50 || stHost.top != 100 || !bVisible || IsWindowVisible(pWindow))
	{
		return 8;
	}
	if (!Evaluate(ptrNative.get(), L"document.body.innerText.includes('WebView2 fixture')", L"true") ||
		!Evaluate(ptrNative.get(), L"localStorage.setItem('web-platform-test','persist'); document.cookie='web_platform_test=persist;path=/;max-age=3600'; true", L"true"))
	{
		return 9;
	}
	if (!Evaluate(ptrNative.get(), L"alert('hidden parent'); confirm('hidden parent') === false && prompt('hidden parent') === null", L"true"))
	{
		return 26;
	}
	ptrNative->Navigate(strBase + "/second");
	Drain();
	if (!WaitForPage(ptrNative.get(), strBase + "/second") || !ptrNative->CanGoBack())
	{
		return 10;
	}
	ptrNative->Back();
	Drain();
	if (!WaitForPage(ptrNative.get(), strBase + "/") || !ptrNative->CanGoForward())
	{
		return 11;
	}
	ptrNative->Forward();
	Drain();
	if (!WaitForPage(ptrNative.get(), strBase + "/second"))
	{
		return 12;
	}
	if (!Evaluate(ptrNative.get(), L"window.allowedFrameExecuted=false; window.addEventListener('message',function(e){if(e.data==='allowed-page-executed')window.allowedFrameExecuted=true;}); var control=document.createElement('iframe'); control.src='/allowed-frame'; document.body.append(control); true", L"true"))
	{
		return 28;
	}
	Drain();
	if (!Evaluate(ptrNative.get(), L"window.allowedFrameExecuted === true", L"true"))
	{
		return 29;
	}
	Evaluate(ptrNative.get(), L"control.remove(); true", L"true");
	const std::wstring strExternalWide(strExternal.begin(), strExternal.end());
	if (!Evaluate(ptrNative.get(), L"location.href='" + strExternalWide + L"/outside'; true", L"true"))
	{
		return 13;
	}
	Drain();
	if (Source(ptrNative.get()) != strBase + "/second" || ptrNative->GetStatus().find("Blocked") == std::string::npos)
	{
		return 14;
	}
	if (!Evaluate(ptrNative.get(), L"window.externalPageExecuted=false; window.addEventListener('message',function(e){if(e.data==='external-page-executed')window.externalPageExecuted=true;}); var f=document.createElement('iframe'); f.src='" + strExternalWide + L"/frame'; document.body.append(f); window.open('" + strExternalWide + L"/popup'); true", L"true"))
	{
		return 15;
	}
	Drain();
	if (!Evaluate(ptrNative.get(), L"window.externalPageExecuted === false", L"true"))
	{
		return 27;
	}
	ptrNative->Navigate(strBase + "/redirect");
	Drain();
	if (Source(ptrNative.get()).find(strExternal) == 0)
	{
		return 16;
	}
	ptrNative->SetVisible(false);
	pController->get_IsVisible(&bVisible);
	if (bVisible || (GetWindowLongPtrW(pHost, GWL_STYLE) & WS_VISIBLE))
	{
		return 17;
	}
	if (!Evaluate(ptrNative.get(), L"alert('hidden'); confirm('hidden') === false && prompt('hidden') === null", L"true"))
	{
		return 25;
	}
	ptrNative.reset();
	Drain();
	if (IsWindow(pHost))
	{
		return 18;
	}
	ptrNative.reset(static_cast<WebPlatformWindows *>(WebPlatformNative::Create(pWindow, strBase + "/")));
	if (!ptrNative || !WaitForPage(ptrNative.get(), strBase + "/") ||
		!Evaluate(ptrNative.get(), L"localStorage.getItem('web-platform-test')", L"\"persist\"") ||
		!Evaluate(ptrNative.get(), L"document.cookie.includes('web_platform_test=persist')", L"true"))
	{
		return 19;
	}
	// Real renderer failure: the installed browser's DevTools command crashes
	// only this isolated fixture renderer, never a user's browser or profile.
	ICoreWebView2 *pView = static_cast<ICoreWebView2 *>(ptrNative->TestGetWebView());
	const HRESULT nCrash = pView->CallDevToolsProtocolMethod(L"Page.crash", L"{}", Callback<ICoreWebView2CallDevToolsProtocolMethodCompletedHandler>([](HRESULT, LPCWSTR) -> HRESULT
																																					 {
																																						 return S_OK;
																																					 })
																						   .Get());
	if (FAILED(nCrash))
	{
		return 20;
	}
	const std::chrono::steady_clock::time_point stDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
	while (ptrNative->GetStatus().find("process failed") == std::string::npos && std::chrono::steady_clock::now() < stDeadline)
	{
		Pump();
	}
	if (ptrNative->GetStatus().find("process failed") == std::string::npos)
	{
		return 21;
	}
	ptrNative->Reload();
	if (!WaitForPage(ptrNative.get(), strBase + "/"))
	{
		return 22;
	}
	ptrNative->Navigate(strBase + "/slow");
	ptrNative.reset();
	Drain();
	if (IsWindowVisible(pWindow) || GetForegroundWindow() != pForeground || GetWindow(pWindow, GW_CHILD))
	{
		return 23;
	}
	DestroyWindow(pWindow);
	CoUninitialize();
	std::cout << "WEB_PLATFORM_WINDOWS_OK hidden_native=true persistence=true navigation=true renderer_retry=true lifecycle=true\n";
	return 0;
}
