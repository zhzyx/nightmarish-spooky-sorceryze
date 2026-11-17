# Microsoft Edge WebView2 native SDK

The manifest pins the official Microsoft.Web.WebView2 NuGet SDK **1.0.3650.58**, its HTTPS package source, package SHA-256, and every consumed file's SHA-256. `LICENSE.txt` and `NOTICE.txt` are unmodified upstream files. Generated SDK inputs are ignored, never hand-authored interface declarations.

From the repository root, run:

```sh
python tools/install_webview2.py
# Offline cache, with the same package and member hash checks:
python tools/install_webview2.py --package /path/to/microsoft.web.webview2.1.0.3650.58.nupkg
# Distribution (same architecture as the editor):
python tools/install_webview2.py --arch x64 --output-dir bin
```

Paths in the installer are resolved against its repository root; `--package` and `--output-dir` are resolved against the invoking directory. The SDK header is `sdk/build/native/include/WebView2.h`; the official architecture-specific loader is `sdk/build/native/{x86,x64,arm64}/WebView2Loader.dll`. Distribution includes this DLL and `WebView2-LICENSE.txt`/`WebView2-NOTICE.txt` next to the executable. The backend loads only that executable-adjacent DLL with restricted Windows loader search flags; it never searches the current directory or PATH.

Build `editor/docks/WebPlatformWindows.cpp` in **Windows editor MSVC or clang-cl** builds with `WEB_PLATFORM_WEBVIEW2_ENABLED`, the SDK include directory, and Windows SDK WRL headers. Link `ole32`, `shell32`, `user32`, and `uuid`. MinGW is not enabled by this backend; use the common unsupported-platform factory unless an independently validated MinGW COM adapter is added. Templates and non-Windows platforms have no dependency. The source is guarded by the explicit capability macro.

This SDK/loader is not the browser runtime. The editor never installs or downloads a runtime. Users need the Microsoft Edge WebView2 Evergreen Runtime, sufficiently current to support `ICoreWebView2_22` (the document request filter includes iframe request sources). Missing/obsolete runtime, wrong/missing loader, inaccessible profile, initialization failures, navigation errors, and process failures produce visible status and an explicit Refresh / Retry path. It never loops restarting a failed browser. Production data stays in the current user's `FOLDERID_LocalAppData/Godot/WebPlatform/WebView2` directory and survives editor closure.

Navigation policy allows only the configured origin, checks redirect destinations, blocks external protocol launching, handles user-initiated same-origin popups in the existing view, and checks nested document requests using the modern request-source filter. Downloads use the browser's normal UI after checking the final download URI (including same-origin blob downloads); hidden hosts reject new downloads. Subresources may use external CDNs; this is navigation confinement, not a network sandbox. Web messaging and native host objects are disabled. Script dialogs use visibility-gated native UI with WebView2 deferrals; hidden or inactive hosts cancel them immediately. Upload controls use the browser's file picker. Real input/IME and system file panels remain separate manual acceptance items.

Standalone Windows verification from an MSVC developer shell:

```sh
python tools/test_web_platform_windows.py --build-dir .godot/webview2-test --report .godot/webview2-test/result.json
```

The test requires an installed runtime and fails when unavailable. It creates a never-shown HWND and isolated temporary profile, serves two local origins, checks real DOM/page/history/persistence, hidden alert/confirm/prompt cancellation, external navigation/frame/popup/redirect denial, bounds/visibility, pending initialization destruction, loading destruction, and real renderer-crash diagnostics with explicit retry. It does not activate the desktop or claim visual/input/dialog acceptance. `.cc` intentionally avoids the Godot recursive test `.cpp` force-link collection.

Official provenance/API references:

- [NuGet SDK package](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3650.58)
- [Microsoft WebView2 threading/lifetime model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/threading-model)
- [ICoreWebView2 navigation and new-window events](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2?view=webview2-1.0.3650.58)
- [DownloadStarting and standard browser UI](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2_4?view=webview2-1.0.3650.58)
- [Modern iframe-aware resource filter](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2_22?view=webview2-1.0.3650.58)
