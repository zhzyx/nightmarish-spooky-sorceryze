/**************************************************************************/
/*  WebPlatformWindows.cpp                                                */
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

#ifdef WEB_PLATFORM_WEBVIEW2_ENABLED

#include "WebPlatformWindows.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <objbase.h>
#include <shlobj.h>
#include <wrl.h>

// Godot's lean windows.h omits COM declarations required by the generated SDK.
#include <WebView2.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

namespace
{
using Microsoft::WRL::Callback;
using Microsoft::WRL::ComPtr;

std::wstring ToWide(const std::string &strText)
{
	const int nSize = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, strText.c_str(), -1, nullptr, 0);
	if (nSize <= 0)
	{
		return {};
	}
	std::wstring strResult(nSize, L'\0');
	MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, strText.c_str(), -1, &strResult[0], nSize);
	strResult.resize(nSize - 1);
	return strResult;
}

std::string TakeUtf8(LPWSTR pText)
{
	if (!pText)
	{
		return {};
	}
	const int nSize = WideCharToMultiByte(CP_UTF8, 0, pText, -1, nullptr, 0, nullptr, nullptr);
	std::string strResult(nSize > 0 ? nSize : 0, '\0');
	if (nSize > 0)
	{
		WideCharToMultiByte(CP_UTF8, 0, pText, -1, &strResult[0], nSize, nullptr, nullptr);
		strResult.resize(nSize - 1);
	}
	CoTaskMemFree(pText);
	return strResult;
}

std::string Failure(const char *pStage, HRESULT nResult)
{
	char arrCode[16];
	std::snprintf(arrCode, sizeof(arrCode), "0x%08lX", static_cast<unsigned long>(nResult));
	return std::string(pStage) + " (" + arrCode + "). Check WebView2 Runtime, installation permissions and service connectivity; click Refresh / Retry.";
}
} //namespace

// All state and COM references stay on the HWND's STA thread. Creation callbacks
// retain this state, never the C++ facade. Event handlers retain only weak state.
struct WebPlatformWindowsState : public std::enable_shared_from_this<WebPlatformWindowsState>
{
	HWND pParent = nullptr;
	HWND pHost = nullptr;
	HWND pDialog = nullptr;
	bool bPresentingDialog = false;
	struct PendingDialog
	{
		ComPtr<ICoreWebView2ScriptDialogOpeningEventArgs> ptrArgs;
		ComPtr<ICoreWebView2Deferral> ptrDeferral;
	};
	std::vector<PendingDialog> arrDialogs;
	static constexpr UINT nDialogMessage = WM_APP + 122;
	HMODULE pLoader = nullptr;
	bool bActive = true;
	bool bVisible = false;
	bool bInitializing = false;
	bool bRetry = false;
	bool bComInitialized = false;
	unsigned int nGeneration = 0;
	RECT stBounds = {};
	std::string strOrigin;
	std::string strPendingUrl;
	std::string strStatus = "Starting WebView2...";
	ComPtr<ICoreWebView2Environment> ptrEnvironment;
	ComPtr<ICoreWebView2Controller> ptrController;
	ComPtr<ICoreWebView2> ptrView;
	std::vector<ComPtr<ICoreWebView2DownloadOperation>> arrDownloads;

	~WebPlatformWindowsState()
	{
		Close();
		if (pLoader)
		{
			FreeLibrary(pLoader);
		}
		if (bComInitialized)
		{
			CoUninitialize();
		}
	}

	struct DialogContext
	{
		WebPlatformWindowsState *pState = nullptr;
		COREWEBVIEW2_SCRIPT_DIALOG_KIND eKind = COREWEBVIEW2_SCRIPT_DIALOG_KIND_ALERT;
		std::wstring strMessage;
		std::wstring strText;
	};

	static INT_PTR CALLBACK DialogProc(HWND pWindow, UINT nMessage, WPARAM nWParam, LPARAM nLParam)
	{
		DialogContext *pContext = reinterpret_cast<DialogContext *>(GetWindowLongPtrW(pWindow, DWLP_USER));
		if (nMessage == WM_INITDIALOG)
		{
			pContext = reinterpret_cast<DialogContext *>(nLParam);
			SetWindowLongPtrW(pWindow, DWLP_USER, nLParam);
			pContext->pState->pDialog = pWindow;
			SetWindowTextW(pWindow, ToWide(pContext->pState->strOrigin).c_str());
			RECT stClient = {};
			GetClientRect(pWindow, &stClient);
			const int nWidth = stClient.right;
			const int nHeight = stClient.bottom;
			CreateWindowExW(0, L"STATIC", pContext->strMessage.c_str(), WS_CHILD | WS_VISIBLE | SS_LEFT,
							12, 10, nWidth - 24, nHeight - 86, pWindow, nullptr, nullptr, nullptr);
			if (pContext->eKind == COREWEBVIEW2_SCRIPT_DIALOG_KIND_PROMPT)
			{
				const HWND pEdit = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", pContext->strText.c_str(),
												   WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL, 12, nHeight - 70, nWidth - 24, 24,
												   pWindow, reinterpret_cast<HMENU>(100), nullptr, nullptr);
				SendMessageW(pEdit, EM_SETLIMITTEXT, 65535, 0);
				SetFocus(pEdit);
			}
			CreateWindowExW(0, L"BUTTON", L"OK", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
							nWidth - 172, nHeight - 34, 76, 24, pWindow, reinterpret_cast<HMENU>(IDOK), nullptr, nullptr);
			if (pContext->eKind != COREWEBVIEW2_SCRIPT_DIALOG_KIND_ALERT)
			{
				CreateWindowExW(0, L"BUTTON", L"Cancel", WS_CHILD | WS_VISIBLE | WS_TABSTOP,
								nWidth - 88, nHeight - 34, 76, 24, pWindow, reinterpret_cast<HMENU>(IDCANCEL), nullptr, nullptr);
			}
			return pContext->eKind == COREWEBVIEW2_SCRIPT_DIALOG_KIND_PROMPT ? FALSE : TRUE;
		}
		if (nMessage == WM_COMMAND && (LOWORD(nWParam) == IDOK || LOWORD(nWParam) == IDCANCEL))
		{
			if (LOWORD(nWParam) == IDOK && pContext && pContext->eKind == COREWEBVIEW2_SCRIPT_DIALOG_KIND_PROMPT)
			{
				const HWND pEdit = GetDlgItem(pWindow, 100);
				const int nLength = GetWindowTextLengthW(pEdit);
				pContext->strText.resize(nLength + 1);
				GetWindowTextW(pEdit, &pContext->strText[0], nLength + 1);
				pContext->strText.resize(nLength);
			}
			EndDialog(pWindow, LOWORD(nWParam));
			return TRUE;
		}
		if (nMessage == WM_CLOSE)
		{
			EndDialog(pWindow, IDCANCEL);
			return TRUE;
		}
		return FALSE;
	}

	void CancelDialogs()
	{
		if (pDialog)
		{
			EndDialog(pDialog, IDCANCEL);
		}
		std::vector<PendingDialog> arrPending;
		arrPending.swap(arrDialogs);
		for (const PendingDialog &stDialog : arrPending)
		{
			stDialog.ptrDeferral->Complete();
		}
	}

	bool CanShowDialog() const
	{
		const HWND pForeground = GetForegroundWindow();
		return bActive && bVisible && IsWindowVisible(pParent) && IsWindowEnabled(pParent) &&
				pForeground && GetAncestor(pForeground, GA_ROOT) == GetAncestor(pParent, GA_ROOT);
	}

	void PresentDialogs()
	{
		if (bPresentingDialog)
		{
			return;
		}
		// Hold state across the native modal loop; the facade may be destroyed there.
		const std::shared_ptr<WebPlatformWindowsState> ptrKeepAlive = shared_from_this();
		bPresentingDialog = true;
		while (!arrDialogs.empty())
		{
			const PendingDialog stPending = arrDialogs.front();
			arrDialogs.erase(arrDialogs.begin());
			if (CanShowDialog())
			{
				DialogContext stContext;
				stContext.pState = this;
				stPending.ptrArgs->get_Kind(&stContext.eKind);
				LPWSTR pText = nullptr;
				stPending.ptrArgs->get_Message(&pText);
				stContext.strMessage = ToWide(TakeUtf8(pText));
				pText = nullptr;
				stPending.ptrArgs->get_DefaultText(&pText);
				stContext.strText = ToWide(TakeUtf8(pText));
				// Standard zero-control template. Controls are created in WM_INITDIALOG.
				// Explicit WORD fields avoid ABI padding between the three variable strings.
				std::vector<WORD> arrTemplate((sizeof(DLGTEMPLATE) + 6 + 3) / 2, 0);
				DLGTEMPLATE *pTemplate = reinterpret_cast<DLGTEMPLATE *>(arrTemplate.data());
				pTemplate->style = WS_POPUP | WS_CAPTION | WS_SYSMENU | DS_MODALFRAME | DS_CENTER;
				pTemplate->cx = 260;
				pTemplate->cy = 120;
				const INT_PTR nResult = DialogBoxIndirectParamW(GetModuleHandleW(nullptr), pTemplate, pParent, DialogProc, reinterpret_cast<LPARAM>(&stContext));
				pDialog = nullptr;
				if (nResult == IDOK && bActive && bVisible)
				{
					stPending.ptrArgs->put_ResultText(stContext.strText.c_str());
					stPending.ptrArgs->Accept();
				}
			}
			stPending.ptrDeferral->Complete();
		}
		bPresentingDialog = false;
	}

	static LRESULT CALLBACK HostProc(HWND pWindow, UINT nMessage, WPARAM nWParam, LPARAM nLParam)
	{
		if (nMessage == WM_NCCREATE)
		{
			const CREATESTRUCTW *pCreation = reinterpret_cast<CREATESTRUCTW *>(nLParam);
			SetWindowLongPtrW(pWindow, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(pCreation->lpCreateParams));
		}
		WebPlatformWindowsState *pState = reinterpret_cast<WebPlatformWindowsState *>(GetWindowLongPtrW(pWindow, GWLP_USERDATA));
		if (nMessage == nDialogMessage && pState)
		{
			pState->PresentDialogs();
			return 0;
		}
		if (nMessage == WM_NCDESTROY)
		{
			SetWindowLongPtrW(pWindow, GWLP_USERDATA, 0);
		}
		return DefWindowProcW(pWindow, nMessage, nWParam, nLParam);
	}

	void RestoreFocus()
	{
		const HWND pFocus = GetFocus();
		// WebView2 owns descendant HWNDs. Never activate a window or take focus
		// away from another application, modal dialog, or another editor window.
		if (pFocus && IsWindow(pParent) && pFocus != pParent && (pFocus == pHost || IsChild(pHost, pFocus)) && ptrController)
		{
			HWND pBrowserParent = nullptr;
			ptrController->get_ParentWindow(&pBrowserParent);
			if (pBrowserParent == pHost && IsWindowEnabled(pParent))
			{
				SetFocus(pParent);
			}
		}
	}

	void Close()
	{
		CancelDialogs();
		RestoreFocus();
		for (const ComPtr<ICoreWebView2DownloadOperation> &ptrDownload : arrDownloads)
		{
			ptrDownload->Cancel();
		}
		arrDownloads.clear();
		if (ptrController)
		{
			ptrController->Close();
		}
		ptrView.Reset();
		ptrController.Reset();
		ptrEnvironment.Reset();
	}

	bool Allows(const std::string &strUrl, bool bDownload = false)
	{
		const bool bAllowed = bActive && IsWebPlatformNavigationAllowed(strUrl, strOrigin, bDownload);
		if (!bAllowed)
		{
			strStatus = "Blocked navigation outside the configured origin or to an unsupported URL.";
		}
		return bAllowed;
	}

	bool Check(HRESULT nResult, const char *pStage)
	{
		if (SUCCEEDED(nResult))
		{
			return true;
		}
		strStatus = Failure(pStage, nResult);
		bRetry = true;
		return false;
	}

	bool Configure()
	{
		ComPtr<ICoreWebView2Settings> ptrSettings;
		ComPtr<ICoreWebView2_22> ptrPolicyView;
		if (!Check(ptrView->get_Settings(&ptrSettings), "WebView2 settings unavailable") ||
			!Check(ptrView.As(&ptrPolicyView), "WebView2 Runtime is too old; update the Evergreen Runtime"))
		{
			return false;
		}
		if (!Check(ptrSettings->put_IsWebMessageEnabled(FALSE), "Disable web messaging") ||
			!Check(ptrSettings->put_AreHostObjectsAllowed(FALSE), "Disable host objects") ||
			!Check(ptrSettings->put_AreDefaultScriptDialogsEnabled(FALSE), "Enable browser dialogs") ||
			!Check(ptrSettings->put_AreDevToolsEnabled(FALSE), "Disable developer tools"))
		{
			return false;
		}
		const std::weak_ptr<WebPlatformWindowsState> ptrWeak = shared_from_this();
		EventRegistrationToken stToken = {};

		const auto fnScriptDialog = [ptrWeak](ICoreWebView2 *, ICoreWebView2ScriptDialogOpeningEventArgs *pArgs) -> HRESULT
		{
			const std::shared_ptr<WebPlatformWindowsState> ptrState = ptrWeak.lock();
			if (!ptrState || !ptrState->CanShowDialog())
			{
				return S_OK; // No Accept: hidden confirm/prompt/beforeunload is cancelled.
			}
			PendingDialog stPending;
			stPending.ptrArgs = pArgs;
			if (FAILED(pArgs->GetDeferral(&stPending.ptrDeferral)))
			{
				return S_OK;
			}
			ptrState->arrDialogs.push_back(stPending);
			if (!PostMessageW(ptrState->pHost, nDialogMessage, 0, 0))
			{
				ptrState->CancelDialogs();
			}
			return S_OK;
		};
		if (!Check(ptrView->add_ScriptDialogOpening(Callback<ICoreWebView2ScriptDialogOpeningEventHandler>(fnScriptDialog).Get(), &stToken), "Register script dialog policy"))
		{
			return false;
		}
		const auto fnDocument = [ptrWeak](ICoreWebView2 *, ICoreWebView2WebResourceRequestedEventArgs *pArgs) -> HRESULT
		{
			const std::shared_ptr<WebPlatformWindowsState> ptrState = ptrWeak.lock();
			if (!ptrState || !ptrState->bActive)
			{
				return E_ABORT;
			}
			ComPtr<ICoreWebView2WebResourceRequest> ptrRequest;
			LPWSTR pUri = nullptr;
			if (SUCCEEDED(pArgs->get_Request(&ptrRequest)))
			{
				ptrRequest->get_Uri(&pUri);
			}
			if (!ptrState->Allows(TakeUtf8(pUri)))
			{
				ComPtr<ICoreWebView2WebResourceResponse> ptrResponse;
				if (SUCCEEDED(ptrState->ptrEnvironment->CreateWebResourceResponse(nullptr, 403, L"Blocked origin", L"Content-Type: text/plain", &ptrResponse)))
				{
					pArgs->put_Response(ptrResponse.Get());
				}
			}
			return S_OK;
		};
		const ComPtr<ICoreWebView2WebResourceRequestedEventHandler> ptrDocumentHandler = Callback<ICoreWebView2WebResourceRequestedEventHandler>(fnDocument);
		const auto fnPopup = [ptrWeak](ICoreWebView2 *, ICoreWebView2NewWindowRequestedEventArgs *pArgs) -> HRESULT
		{
			pArgs->put_Handled(TRUE);
			const std::shared_ptr<WebPlatformWindowsState> ptrState = ptrWeak.lock();
			LPWSTR pUri = nullptr;
			pArgs->get_Uri(&pUri);
			const std::string strUri = TakeUtf8(pUri);
			BOOL bUserInitiated = FALSE;
			pArgs->get_IsUserInitiated(&bUserInitiated);
			if (ptrState && ptrState->bVisible && bUserInitiated && ptrState->Allows(strUri))
			{
				ptrState->ptrView->Navigate(ToWide(strUri).c_str());
			}
			return S_OK;
		};
		const ComPtr<ICoreWebView2NewWindowRequestedEventHandler> ptrPopupHandler = Callback<ICoreWebView2NewWindowRequestedEventHandler>(fnPopup);
		const auto fnExternalProtocol = [](ICoreWebView2 *, ICoreWebView2LaunchingExternalUriSchemeEventArgs *pArgs) -> HRESULT
		{
			return pArgs->put_Cancel(TRUE);
		};
		const ComPtr<ICoreWebView2LaunchingExternalUriSchemeEventHandler> ptrExternalProtocolHandler = Callback<ICoreWebView2LaunchingExternalUriSchemeEventHandler>(fnExternalProtocol);
		const auto fnDownload = [ptrWeak](ICoreWebView2 *, ICoreWebView2DownloadStartingEventArgs *pArgs) -> HRESULT
		{
			const std::shared_ptr<WebPlatformWindowsState> ptrState = ptrWeak.lock();
			ComPtr<ICoreWebView2DownloadOperation> ptrDownload;
			LPWSTR pUri = nullptr;
			if (SUCCEEDED(pArgs->get_DownloadOperation(&ptrDownload)))
			{
				ptrDownload->get_Uri(&pUri);
			}
			const std::string strUri = TakeUtf8(pUri);
			if (!ptrState || !ptrState->bVisible || !IsWindowVisible(ptrState->pParent) || !ptrState->Allows(strUri, true))
			{
				return pArgs->put_Cancel(TRUE);
			}
			// Keep the browser's standard download UI and file selection behavior.
			// Retain only in-progress downloads, and cancel them during shutdown.
			std::vector<ComPtr<ICoreWebView2DownloadOperation>> &arrDownloads = ptrState->arrDownloads;
			arrDownloads.erase(std::remove_if(arrDownloads.begin(), arrDownloads.end(), [](const ComPtr<ICoreWebView2DownloadOperation> &ptrItem)
											  {
												  COREWEBVIEW2_DOWNLOAD_STATE eState = COREWEBVIEW2_DOWNLOAD_STATE_INTERRUPTED;
												  ptrItem->get_State(&eState);
												  return eState != COREWEBVIEW2_DOWNLOAD_STATE_IN_PROGRESS;
											  }),
							   arrDownloads.end());
			arrDownloads.push_back(ptrDownload);
			return S_OK;
		};
		const ComPtr<ICoreWebView2DownloadStartingEventHandler> ptrDownloadHandler = Callback<ICoreWebView2DownloadStartingEventHandler>(fnDownload);
		const auto fnCompletion = [ptrWeak](ICoreWebView2 *, ICoreWebView2NavigationCompletedEventArgs *pArgs) -> HRESULT
		{
			const std::shared_ptr<WebPlatformWindowsState> ptrState = ptrWeak.lock();
			if (!ptrState || !ptrState->bActive || ptrState->bRetry)
			{
				return S_OK;
			}
			BOOL bSuccess = FALSE;
			pArgs->get_IsSuccess(&bSuccess);
			COREWEBVIEW2_WEB_ERROR_STATUS eError = COREWEBVIEW2_WEB_ERROR_STATUS_UNKNOWN;
			pArgs->get_WebErrorStatus(&eError);
			if (bSuccess)
			{
				ptrState->strStatus = "Connected - sign-in and permissions are managed by the website.";
			}
			else if (eError != COREWEBVIEW2_WEB_ERROR_STATUS_OPERATION_CANCELED)
			{
				ptrState->strStatus = "Page load failed (WebView2 error " + std::to_string(eError) + "). Check the service and network, then click Refresh / Retry.";
			}
			return S_OK;
		};
		const ComPtr<ICoreWebView2NavigationCompletedEventHandler> ptrCompletionHandler = Callback<ICoreWebView2NavigationCompletedEventHandler>(fnCompletion);
		const auto fnFailure = [ptrWeak](ICoreWebView2 *, ICoreWebView2ProcessFailedEventArgs *pArgs) -> HRESULT
		{
			const std::shared_ptr<WebPlatformWindowsState> ptrState = ptrWeak.lock();
			if (ptrState && ptrState->bActive)
			{
				COREWEBVIEW2_PROCESS_FAILED_KIND eKind = COREWEBVIEW2_PROCESS_FAILED_KIND_BROWSER_PROCESS_EXITED;
				pArgs->get_ProcessFailedKind(&eKind);
				ptrState->strStatus = "WebView2 process failed (kind " + std::to_string(eKind) + "). Click Refresh / Retry to recreate the browser.";
				ptrState->bRetry = true;
			}
			return S_OK;
		};
		const ComPtr<ICoreWebView2ProcessFailedEventHandler> ptrFailureHandler = Callback<ICoreWebView2ProcessFailedEventHandler>(fnFailure);

		const auto fnNavigation = [ptrWeak](ICoreWebView2 *, ICoreWebView2NavigationStartingEventArgs *pArgs) -> HRESULT
		{
			const std::shared_ptr<WebPlatformWindowsState> ptrState = ptrWeak.lock();
			LPWSTR pUri = nullptr;
			pArgs->get_Uri(&pUri);
			const std::string strUri = TakeUtf8(pUri);
			if (!ptrState || !ptrState->Allows(strUri))
			{
				pArgs->put_Cancel(TRUE);
			}
			return S_OK;
		};
		if (!Check(ptrView->add_NavigationStarting(Callback<ICoreWebView2NavigationStartingEventHandler>(fnNavigation).Get(), &stToken), "Register navigation policy") ||
			!Check(ptrView->add_FrameNavigationStarting(Callback<ICoreWebView2NavigationStartingEventHandler>(fnNavigation).Get(), &stToken), "Register frame policy"))
		{
			return false;
		}
		// All document requests, including nested frames and redirects, are checked.
		// Subresources may use CDN origins: this is navigation confinement, not a network sandbox.
		if (!Check(ptrPolicyView->AddWebResourceRequestedFilterWithRequestSourceKinds(L"*", COREWEBVIEW2_WEB_RESOURCE_CONTEXT_DOCUMENT, COREWEBVIEW2_WEB_RESOURCE_REQUEST_SOURCE_KINDS_ALL), "Register document filter") ||
			!Check(ptrView->add_WebResourceRequested(ptrDocumentHandler.Get(), &stToken), "Register document policy"))
		{
			return false;
		}
		if (!Check(ptrView->add_NewWindowRequested(ptrPopupHandler.Get(), &stToken), "Register popup policy") ||
			!Check(ptrPolicyView->add_LaunchingExternalUriScheme(ptrExternalProtocolHandler.Get(), &stToken), "Register external protocol policy"))
		{
			return false;
		}
		if (!Check(ptrPolicyView->add_DownloadStarting(ptrDownloadHandler.Get(), &stToken), "Register download policy") ||
			!Check(ptrView->add_NavigationCompleted(ptrCompletionHandler.Get(), &stToken), "Register load diagnostics") ||
			!Check(ptrView->add_ProcessFailed(ptrFailureHandler.Get(), &stToken), "Register process diagnostics"))
		{
			return false;
		}
		return true;
	}

	void OnController(unsigned int nAttempt, HRESULT nError, ICoreWebView2Controller *pController)
	{
		if (!bActive || nAttempt != nGeneration || !IsWindow(pHost))
		{
			if (pController)
			{
				pController->Close();
			}
			return;
		}
		bInitializing = false;
		if (!Check(FAILED(nError) ? nError : (pController ? S_OK : E_POINTER), "Cannot create WebView2 controller"))
		{
			return;
		}
		ptrController = pController;
		if (!Check(pController->get_CoreWebView2(&ptrView), "Cannot access WebView2") || !Configure())
		{
			Close();
			return;
		}
		if (!Check(pController->put_Bounds(stBounds), "Cannot set WebView2 bounds") || !Check(pController->put_IsVisible(bVisible), "Cannot set WebView2 visibility"))
		{
			Close();
			return;
		}
		Check(ptrView->Navigate(ToWide(strPendingUrl).c_str()), "Cannot navigate WebView2");
	}

	void OnEnvironment(unsigned int nAttempt, HRESULT nError, ICoreWebView2Environment *pEnvironment)
	{
		if (!bActive || nAttempt != nGeneration || !IsWindow(pHost))
		{
			return;
		}
		if (!Check(FAILED(nError) ? nError : (pEnvironment ? S_OK : E_POINTER), "Cannot start WebView2; install or repair Microsoft Edge WebView2 Evergreen Runtime"))
		{
			bInitializing = false;
			return;
		}
		ptrEnvironment = pEnvironment;
		const std::shared_ptr<WebPlatformWindowsState> ptrState = shared_from_this();
		const auto fnHandler = [ptrState, nAttempt](HRESULT nControllerError, ICoreWebView2Controller *pController) -> HRESULT
		{
			ptrState->OnController(nAttempt, nControllerError, pController);
			return S_OK;
		};
		const ComPtr<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler> ptrHandler = Callback<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler>(fnHandler);
		if (!Check(pEnvironment->CreateCoreWebView2Controller(pHost, ptrHandler.Get()), "Cannot request WebView2 controller"))
		{
			bInitializing = false;
		}
	}

	void Start()
	{
		if (!bActive || bInitializing || !IsWindow(pHost))
		{
			return;
		}
		Close();
		bRetry = false;
		strStatus = "Starting WebView2...";
		if (!bComInitialized)
		{
			const HRESULT nResult = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
			if (!Check(nResult, "WebView2 requires the window's STA UI thread"))
			{
				return;
			}
			bComInitialized = true;
		}
		if (!pLoader)
		{
			std::wstring strPath(32768, L'\0');
			const DWORD nLength = GetModuleFileNameW(nullptr, &strPath[0], static_cast<DWORD>(strPath.size()));
			if (!nLength || nLength >= strPath.size())
			{
				Check(HRESULT_FROM_WIN32(ERROR_BAD_PATHNAME), "Cannot locate editor installation");
				return;
			}
			strPath.resize(nLength);
			strPath.resize(strPath.find_last_of(L"\\/") + 1);
			strPath += L"WebView2Loader.dll";
			// No PATH/current-directory lookup, and no runtime download or installation.
			pLoader = LoadLibraryExW(strPath.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
			if (!pLoader)
			{
				Check(HRESULT_FROM_WIN32(GetLastError()), "WebView2Loader.dll missing or wrong architecture; repair the editor package");
				return;
			}
		}
		using CreateEnvironment = HRESULT(STDAPICALLTYPE *)(PCWSTR, PCWSTR, ICoreWebView2EnvironmentOptions *, ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler *);
		const CreateEnvironment fnCreate = reinterpret_cast<CreateEnvironment>(GetProcAddress(pLoader, "CreateCoreWebView2EnvironmentWithOptions"));
		if (!fnCreate)
		{
			Check(E_NOINTERFACE, "Invalid WebView2 loader; repair the editor package");
			return;
		}
		PWSTR pLocalData = nullptr;
		if (!Check(SHGetKnownFolderPath(FOLDERID_LocalAppData, KF_FLAG_CREATE, nullptr, &pLocalData), "Cannot access per-user application data"))
		{
			return;
		}
		std::wstring strData = std::wstring(pLocalData) + L"\\Godot\\WebPlatform\\WebView2";
		CoTaskMemFree(pLocalData);
#ifdef WEB_PLATFORM_WINDOWS_TESTS
		// Harness-only isolation; production never consumes a test data directory.
		wchar_t arrTestData[32768];
		const DWORD nTestLength = GetEnvironmentVariableW(L"GODOT_WEB_PLATFORM_TEST_DATA", arrTestData, 32768);
		if (nTestLength > 0 && nTestLength < 32768)
		{
			strData = arrTestData;
		}
#endif
		const int nDirectory = SHCreateDirectoryExW(nullptr, strData.c_str(), nullptr);
		if (nDirectory != ERROR_SUCCESS && nDirectory != ERROR_ALREADY_EXISTS && nDirectory != ERROR_FILE_EXISTS)
		{
			Check(HRESULT_FROM_WIN32(nDirectory), "Cannot create WebView2 user-data directory");
			return;
		}
		bInitializing = true;
		const unsigned int nAttempt = ++nGeneration;
		const std::shared_ptr<WebPlatformWindowsState> ptrState = shared_from_this();
		const auto fnHandler = [ptrState, nAttempt](HRESULT nError, ICoreWebView2Environment *pEnvironment) -> HRESULT
		{
			ptrState->OnEnvironment(nAttempt, nError, pEnvironment);
			return S_OK;
		};
		const ComPtr<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler> ptrHandler = Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>(fnHandler);
		const HRESULT nResult = fnCreate(nullptr, strData.c_str(), nullptr, ptrHandler.Get());
		if (!Check(nResult, "Cannot request WebView2 environment; install or repair Microsoft Edge WebView2 Evergreen Runtime"))
		{
			bInitializing = false;
		}
	}
};

WebPlatformWindows::WebPlatformWindows(void *pNativeParent, const std::string &strUrl, const std::string &strOrigin) :
		ptrState(std::make_shared<WebPlatformWindowsState>())
{
	ptrState->pParent = static_cast<HWND>(pNativeParent);
	WNDCLASSW stClass = {};
	stClass.lpfnWndProc = WebPlatformWindowsState::HostProc;
	stClass.hInstance = GetModuleHandleW(nullptr);
	stClass.lpszClassName = L"GodotWebPlatformHost";
	if (!RegisterClassW(&stClass) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
	{
		ptrState->Check(HRESULT_FROM_WIN32(GetLastError()), "Cannot register WebView2 child window");
		return;
	}
	ptrState->pHost = CreateWindowExW(0, stClass.lpszClassName, L"Godot Web Platform", WS_CHILD | WS_CLIPCHILDREN | WS_CLIPSIBLINGS, 0, 0, 0, 0, ptrState->pParent, nullptr, stClass.hInstance, ptrState.get());
	ptrState->strPendingUrl = strUrl;
	ptrState->strOrigin = strOrigin;
	if (!ptrState->pHost)
	{
		ptrState->Check(HRESULT_FROM_WIN32(GetLastError()), "Cannot create the WebView2 child window");
	}
	else
	{
		ptrState->Start();
	}
}

WebPlatformWindows::~WebPlatformWindows()
{
	ptrState->bActive = false;
	++ptrState->nGeneration;
	ptrState->Close();
	if (ptrState->pHost)
	{
		DestroyWindow(ptrState->pHost);
		ptrState->pHost = nullptr;
	}
}

void WebPlatformWindows::SetBounds(double dX, double dY, double dWidth, double dHeight, double dParentWidth, double dParentHeight)
{
	RECT stParent = {};
	if (!GetClientRect(ptrState->pParent, &stParent) || dParentWidth <= 0 || dParentHeight <= 0 ||
		!std::isfinite(dX) || !std::isfinite(dY) || !std::isfinite(dWidth) || !std::isfinite(dHeight) || !std::isfinite(dParentWidth) || !std::isfinite(dParentHeight))
	{
		SetVisible(false);
		return;
	}
	const double dScaleX = stParent.right / dParentWidth;
	const double dScaleY = stParent.bottom / dParentHeight;
	RECT stLayout = {
		static_cast<LONG>(std::clamp(dX * dScaleX, 0.0, static_cast<double>(stParent.right))),
		static_cast<LONG>(std::clamp(dY * dScaleY, 0.0, static_cast<double>(stParent.bottom))),
		static_cast<LONG>(std::clamp((dX + std::max(0.0, dWidth)) * dScaleX, 0.0, static_cast<double>(stParent.right))),
		static_cast<LONG>(std::clamp((dY + std::max(0.0, dHeight)) * dScaleY, 0.0, static_cast<double>(stParent.bottom)))
	};
	SetWindowPos(ptrState->pHost, nullptr, stLayout.left, stLayout.top, stLayout.right - stLayout.left, stLayout.bottom - stLayout.top, SWP_NOACTIVATE | SWP_NOZORDER);
	ptrState->stBounds = { 0, 0, stLayout.right - stLayout.left, stLayout.bottom - stLayout.top };
	if (ptrState->ptrController)
	{
		ptrState->ptrController->put_Bounds(ptrState->stBounds);
		ptrState->ptrController->NotifyParentWindowPositionChanged();
	}
}

void WebPlatformWindows::SetVisible(bool bVisible)
{
	if (!bVisible && ptrState->bVisible)
	{
		ptrState->RestoreFocus();
	}
	ptrState->bVisible = bVisible;
	ShowWindow(ptrState->pHost, bVisible ? SW_SHOWNA : SW_HIDE);
	if (!bVisible)
	{
		ptrState->CancelDialogs();
	}
	if (ptrState->ptrController)
	{
		ptrState->ptrController->put_IsVisible(bVisible);
	}
}

void WebPlatformWindows::Navigate(const std::string &strUrl)
{
	if (!ptrState->Allows(strUrl))
	{
		return;
	}
	ptrState->strPendingUrl = strUrl;
	if (ptrState->ptrView && !ptrState->bRetry)
	{
		ptrState->strStatus = "Loading...";
		ptrState->Check(ptrState->ptrView->Navigate(ToWide(strUrl).c_str()), "Cannot navigate WebView2");
	}
}

void WebPlatformWindows::Back()
{
	if (CanGoBack())
	{
		ptrState->Check(ptrState->ptrView->GoBack(), "Cannot go back");
	}
}

void WebPlatformWindows::Forward()
{
	if (CanGoForward())
	{
		ptrState->Check(ptrState->ptrView->GoForward(), "Cannot go forward");
	}
}

void WebPlatformWindows::Reload()
{
	if (ptrState->bInitializing)
	{
		// A user retry invalidates even a stalled creation request. Its late
		// callback can only close its own controller, never replace this attempt.
		++ptrState->nGeneration;
		ptrState->bInitializing = false;
	}
	if (ptrState->bRetry || !ptrState->ptrView)
	{
		ptrState->Start();
	}
	else
	{
		ptrState->Check(ptrState->ptrView->Reload(), "Cannot reload WebView2");
	}
}

bool WebPlatformWindows::CanGoBack() const
{
	BOOL bCan = FALSE;
	if (ptrState->ptrView && !ptrState->bRetry)
	{
		ptrState->ptrView->get_CanGoBack(&bCan);
	}
	return bCan;
}

bool WebPlatformWindows::CanGoForward() const
{
	BOOL bCan = FALSE;
	if (ptrState->ptrView && !ptrState->bRetry)
	{
		ptrState->ptrView->get_CanGoForward(&bCan);
	}
	return bCan;
}

std::string WebPlatformWindows::GetStatus() const
{
	return ptrState->strStatus;
}

#ifdef WEB_PLATFORM_WINDOWS_TESTS
void *WebPlatformWindows::TestGetWebView() const
{
	return ptrState->ptrView.Get();
}

void *WebPlatformWindows::TestGetController() const
{
	return ptrState->ptrController.Get();
}
#endif

WebPlatformNative *WebPlatformNative::Create(void *pNativeParent, const std::string &strUrl)
{
	std::string strOrigin;
	const HWND pParent = static_cast<HWND>(pNativeParent);
	if (!pParent || !IsWindow(pParent) || GetWindowThreadProcessId(pParent, nullptr) != GetCurrentThreadId() || !ParseWebPlatformOrigin(strUrl, strOrigin))
	{
		return nullptr;
	}
	return new WebPlatformWindows(pNativeParent, strUrl, strOrigin);
}

#endif // WEB_PLATFORM_WEBVIEW2_ENABLED
