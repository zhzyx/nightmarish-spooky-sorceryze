/**************************************************************************/
/*  TestWebPlatformMacOS.mm                                               */
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

#include "editor/docks/WebPlatformNative.h"

#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>

#include <chrono>
#include <iostream>
#include <memory>
#include <string>

static void Pump()
{
	[[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.01]];
}

static bool Evaluate(WKWebView *pView, NSString *strScript, NSString **out_pValue)
{
	__block BOOL bFinished = NO;
	__block NSError *pFailure = nil;
	__block NSString *strValue = nil;
	[pView evaluateJavaScript:strScript
			completionHandler:^(id pResult, NSError *pError) {
				pFailure = pError;
				strValue = [pResult description];
				bFinished = YES;
			}];
	const std::chrono::steady_clock::time_point stDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
	while (!bFinished && std::chrono::steady_clock::now() < stDeadline)
	{
		Pump();
	}
	*out_pValue = strValue;
	return bFinished && pFailure == nil;
}

static bool WaitForPage(WebPlatformNative *pNative, WKWebView *pView, NSString *strPath)
{
	const std::chrono::steady_clock::time_point stDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(40);
	while (std::chrono::steady_clock::now() < stDeadline)
	{
		Pump();
		if (!pView.loading && [pView.URL.path isEqualToString:strPath] && pNative->GetStatus().find("已连接") != std::string::npos)
		{
			return true;
		}
	}
	std::cerr << pNative->GetStatus() << '\n';
	return false;
}

int main(int nArgc, char **ppArgv)
{
	@autoreleasepool
	{
		if ((nArgc != 2 && nArgc != 3) || ![[NSBundle mainBundle].bundleIdentifier hasPrefix:@"org.godotengine.webplatform.validation."])
		{
			return 2;
		}
		[NSApplication sharedApplication];
		[NSApp setActivationPolicy:NSApplicationActivationPolicyProhibited];
		// Never order, activate or focus this window. This is a hidden native consumer.
		NSWindow *pWindow = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 800, 600) styleMask:NSWindowStyleMaskBorderless backing:NSBackingStoreBuffered defer:NO];
		pWindow.releasedWhenClosed = NO;
		NSView *pParent = pWindow.contentView;
		std::unique_ptr<WebPlatformNative> ptrNative(WebPlatformNative::Create((__bridge void *)pParent, ppArgv[1]));
		if (!ptrNative || pParent.subviews.count != 1)
		{
			return 3;
		}
		WKWebView *pView = (WKWebView *)pParent.subviews[0];
		ptrNative->SetBounds(100, 200, 1000, 600, 1600, 1200);
		if (!NSEqualRects(pView.frame, NSMakeRect(50, 200, 500, 300)) || !pView.hidden || pWindow.visible)
		{
			return 4;
		}
		ptrNative->SetVisible(true);
		if (pView.hidden || pWindow.visible || !WaitForPage(ptrNative.get(), pView, @"/"))
		{
			return 5;
		}
		NSString *strValue = nil;
		if (!Evaluate(pView, @"document.body.innerText.length > 0", &strValue) || ![strValue isEqualToString:@"1"])
		{
			return 6;
		}
		for (const std::string &strPath : { "/docs", "/issues", "/requirements", "/repos", "/search", "/settings", "/accounts", "/login" })
		{
			ptrNative->Navigate(std::string(ppArgv[1]) + strPath);
			// The first pump consumes the scheduled navigation before observing completion.
			for (int nIndex = 0; nIndex < 20; ++nIndex)
			{
				Pump();
			}
			if (!WaitForPage(ptrNative.get(), pView, [NSString stringWithUTF8String:strPath.c_str()]) || !Evaluate(pView, @"document.body.innerText.length > 0", &strValue) || ![strValue isEqualToString:@"1"])
			{
				return 7;
			}
			if (nArgc == 3)
			{
				if (!Evaluate(pView, @"Boolean(document.querySelector('h1')?.innerText) && !document.body.innerText.includes('Application error') && !document.body.innerText.includes('This page could not be found')", &strValue) || ![strValue isEqualToString:@"1"])
				{
					return 16;
				}
				if (strPath == "/docs" && (!Evaluate(pView, @"document.body.innerText.includes('Godot native integration proof')", &strValue) || ![strValue isEqualToString:@"1"]))
				{
					return 17;
				}
			}
			std::cout << "PAGE_OK " << strPath << '\n';
		}
		if (!Evaluate(pView, @"localStorage.setItem('godot-native-test','persist'); document.cookie='godot_native_test=persist;path=/'; 'saved'", &strValue))
		{
			return 8;
		}
		ptrNative->SetVisible(false);
		if (!pView.hidden)
		{
			return 9;
		}
		ptrNative.reset();
		if (pParent.subviews.count != 0)
		{
			return 10;
		}
		ptrNative.reset(WebPlatformNative::Create((__bridge void *)pParent, ppArgv[1]));
		pView = (WKWebView *)pParent.subviews[0];
		if (!WaitForPage(ptrNative.get(), pView, @"/"))
		{
			return 11;
		}
		pView = (WKWebView *)pParent.subviews[0];
		if (!Evaluate(pView, @"localStorage.getItem('godot-native-test') + ':' + document.cookie.includes('godot_native_test=persist')", &strValue) || ![strValue isEqualToString:@"persist:true"])
		{
			return 12;
		}
		if (!Evaluate(pView, @"localStorage.removeItem('godot-native-test'); document.cookie='godot_native_test=;Max-Age=0;path=/'; window.location.href='https://example.invalid/'; 'requested'", &strValue))
		{
			return 13;
		}
		for (int nIndex = 0; nIndex < 100; ++nIndex)
		{
			Pump();
		}
		if (ptrNative->GetStatus().find("已阻止") == std::string::npos || [pView.URL.host isEqualToString:@"example.invalid"])
		{
			return 14;
		}
		ptrNative->Navigate(std::string(ppArgv[1]) + "/docs");
		ptrNative.reset();
		for (int nIndex = 0; nIndex < 100; ++nIndex)
		{
			Pump();
		}
		if (pParent.subviews.count != 0 || pWindow.visible)
		{
			return 15;
		}
		[pWindow close];
		std::cout << "WEB_PLATFORM_MACOS_OK hidden_native=true\n";
	}
	return 0;
}
