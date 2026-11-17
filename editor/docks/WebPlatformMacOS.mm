/**************************************************************************/
/*  WebPlatformMacOS.mm                                                   */
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

#include <algorithm>
#include <cmath>

@interface GodotWebPlatformDelegate : NSObject <WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate>
@property(nonatomic, copy) NSString *origin;
@property(nonatomic, copy) NSString *status;
@property(nonatomic, weak) WKWebView *view;
@property(nonatomic) BOOL active;
@property(nonatomic, strong) NSMutableArray<NSWindow *> *panels;
@property(nonatomic, strong) NSMutableArray *downloads;
- (BOOL)allowsURL:(NSURL *)url download:(BOOL)download;
- (void)shutdown;
@end

@implementation GodotWebPlatformDelegate
- (BOOL)allowsURL:(NSURL *)url download:(BOOL)download
{
	const char *pUrl = url.absoluteString.UTF8String;
	return self.active && pUrl != nullptr && IsWebPlatformNavigationAllowed(pUrl, self.origin.UTF8String, download);
}

- (void)shutdown
{
	self.active = NO;
	for (NSWindow *pPanel in [self.panels copy])
	{
		[pPanel.sheetParent endSheet:pPanel returnCode:NSModalResponseCancel];
		[pPanel orderOut:nil];
	}
	[self.panels removeAllObjects];
	if (@available(macOS 11.3, *))
	{
		for (WKDownload *pDownload in [self.downloads copy])
		{
			pDownload.delegate = nil;
			[pDownload cancel:nil];
		}
	}
	[self.downloads removeAllObjects];
}

- (void)webView:(WKWebView *)pView decidePolicyForNavigationAction:(WKNavigationAction *)pAction decisionHandler:(void (^)(WKNavigationActionPolicy))fnDecision
{
	BOOL bDownload = NO;
	if (@available(macOS 11.3, *))
	{
		bDownload = pAction.shouldPerformDownload;
	}
	if (![self allowsURL:pAction.request.URL download:bDownload])
	{
		self.status = @"已阻止站外或不受支持的导航。";
		fnDecision(WKNavigationActionPolicyCancel);
		return;
	}
	if (bDownload)
	{
		if (@available(macOS 11.3, *))
		{
			fnDecision(WKNavigationActionPolicyDownload);
		}
		else
		{
			fnDecision(WKNavigationActionPolicyCancel);
		}
	}
	else if (pAction.targetFrame == nil)
	{
		fnDecision(WKNavigationActionPolicyCancel);
		[pView loadRequest:pAction.request];
	}
	else
	{
		fnDecision(WKNavigationActionPolicyAllow);
	}
}

- (void)webView:(WKWebView *)pView decidePolicyForNavigationResponse:(WKNavigationResponse *)pResponse decisionHandler:(void (^)(WKNavigationResponsePolicy))fnDecision
{
	if (![self allowsURL:pResponse.response.URL download:YES])
	{
		fnDecision(WKNavigationResponsePolicyCancel);
		self.status = @"已阻止站外响应。";
	}
	else
	{
		if (pResponse.canShowMIMEType)
		{
			fnDecision(WKNavigationResponsePolicyAllow);
		}
		else if (@available(macOS 11.3, *))
		{
			fnDecision(WKNavigationResponsePolicyDownload);
		}
		else
		{
			self.status = @"此系统版本不支持内嵌下载，请升级至 macOS 11.3 或更新版本。";
			fnDecision(WKNavigationResponsePolicyCancel);
		}
	}
}

- (void)webView:(WKWebView *)pView didStartProvisionalNavigation:(WKNavigation *)pNavigation
{
	self.status = @"正在加载工作台…";
}

- (void)webView:(WKWebView *)pView didFinishNavigation:(WKNavigation *)pNavigation
{
	self.status = @"已连接 · 登录及权限由天璇管理";
}

- (void)webView:(WKWebView *)pView didFailProvisionalNavigation:(WKNavigation *)pNavigation withError:(NSError *)pError
{
	if (pError.code != NSURLErrorCancelled)
	{
		self.status = @"加载失败，请检查服务与网络后点击刷新 / 重试。";
	}
}

- (void)webView:(WKWebView *)pView didFailNavigation:(WKNavigation *)pNavigation withError:(NSError *)pError
{
	[self webView:pView didFailProvisionalNavigation:pNavigation withError:pError];
}

- (void)webViewWebContentProcessDidTerminate:(WKWebView *)pView
{
	self.status = @"网页进程已停止。可点击刷新 / 重试；其他编辑器工作区仍可使用。";
}

- (void)webView:(WKWebView *)pView runJavaScriptAlertPanelWithMessage:(NSString *)strMessage initiatedByFrame:(WKFrameInfo *)pFrame completionHandler:(void (^)(void))fnComplete
{
	if (!self.active || pView.hidden || pView.window == nil)
	{
		fnComplete();
		return;
	}
	NSAlert *pAlert = [[NSAlert alloc] init];
	pAlert.messageText = @"天璇";
	pAlert.informativeText = strMessage;
	[pAlert addButtonWithTitle:@"确定"];
	[self.panels addObject:pAlert.window];
	[pAlert beginSheetModalForWindow:pView.window
				   completionHandler:^(NSModalResponse nResponse) {
					   [self.panels removeObject:pAlert.window];
					   fnComplete();
				   }];
}

- (void)webView:(WKWebView *)pView runJavaScriptConfirmPanelWithMessage:(NSString *)strMessage initiatedByFrame:(WKFrameInfo *)pFrame completionHandler:(void (^)(BOOL))fnComplete
{
	if (!self.active || pView.hidden || pView.window == nil)
	{
		fnComplete(NO);
		return;
	}
	NSAlert *pAlert = [[NSAlert alloc] init];
	pAlert.messageText = @"天璇";
	pAlert.informativeText = strMessage;
	[pAlert addButtonWithTitle:@"确定"];
	[pAlert addButtonWithTitle:@"取消"];
	[self.panels addObject:pAlert.window];
	[pAlert beginSheetModalForWindow:pView.window
				   completionHandler:^(NSModalResponse nResponse) {
					   [self.panels removeObject:pAlert.window];
					   fnComplete(self.active && nResponse == NSAlertFirstButtonReturn);
				   }];
}

- (void)webView:(WKWebView *)pView runOpenPanelWithParameters:(WKOpenPanelParameters *)pParameters initiatedByFrame:(WKFrameInfo *)pFrame completionHandler:(void (^)(NSArray<NSURL *> *))fnComplete
{
	if (!self.active || pView.hidden || pView.window == nil)
	{
		fnComplete(nil);
		return;
	}
	NSOpenPanel *pPanel = [NSOpenPanel openPanel];
	pPanel.canChooseFiles = YES;
	pPanel.canChooseDirectories = pParameters.allowsDirectories;
	pPanel.allowsMultipleSelection = pParameters.allowsMultipleSelection;
	[self.panels addObject:pPanel];
	[pPanel beginSheetModalForWindow:pView.window
				   completionHandler:^(NSModalResponse nResponse) {
					   [self.panels removeObject:pPanel];
					   fnComplete(self.active && nResponse == NSModalResponseOK ? pPanel.URLs : nil);
				   }];
}

- (void)webView:(WKWebView *)pView runJavaScriptTextInputPanelWithPrompt:(NSString *)strPrompt defaultText:(NSString *)strDefault initiatedByFrame:(WKFrameInfo *)pFrame completionHandler:(void (^)(NSString *))fnComplete
{
	if (!self.active || pView.hidden || pView.window == nil)
	{
		fnComplete(nil);
		return;
	}
	NSAlert *pAlert = [[NSAlert alloc] init];
	pAlert.messageText = @"天璇";
	pAlert.informativeText = strPrompt;
	NSTextField *pInput = [[NSTextField alloc] initWithFrame:NSMakeRect(0, 0, 360, 24)];
	pInput.stringValue = strDefault ?: @"";
	pAlert.accessoryView = pInput;
	[pAlert addButtonWithTitle:@"确定"];
	[pAlert addButtonWithTitle:@"取消"];
	[self.panels addObject:pAlert.window];
	[pAlert beginSheetModalForWindow:pView.window
				   completionHandler:^(NSModalResponse nResponse) {
					   [self.panels removeObject:pAlert.window];
					   fnComplete(self.active && nResponse == NSAlertFirstButtonReturn ? pInput.stringValue : nil);
				   }];
}

- (void)webView:(WKWebView *)pView navigationAction:(WKNavigationAction *)pAction didBecomeDownload:(WKDownload *)pDownload API_AVAILABLE(macos(11.3))
{
	[self.downloads addObject:pDownload];
	pDownload.delegate = self;
}

- (void)webView:(WKWebView *)pView navigationResponse:(WKNavigationResponse *)pResponse didBecomeDownload:(WKDownload *)pDownload API_AVAILABLE(macos(11.3))
{
	[self.downloads addObject:pDownload];
	pDownload.delegate = self;
}

- (void)download:(WKDownload *)pDownload decideDestinationUsingResponse:(NSURLResponse *)pResponse suggestedFilename:(NSString *)strFilename completionHandler:(void (^)(NSURL *))fnComplete API_AVAILABLE(macos(11.3))
{
	if (!self.active || self.view.hidden || self.view.window == nil || ![self allowsURL:pResponse.URL download:YES])
	{
		fnComplete(nil);
		return;
	}
	NSSavePanel *pPanel = [NSSavePanel savePanel];
	pPanel.nameFieldStringValue = strFilename.lastPathComponent;
	[self.panels addObject:pPanel];
	[pPanel beginSheetModalForWindow:self.view.window
				   completionHandler:^(NSModalResponse nResponse) {
					   [self.panels removeObject:pPanel];
					   if (!self.active || nResponse != NSModalResponseOK)
					   {
						   fnComplete(nil);
					   }
					   else if ([[NSFileManager defaultManager] fileExistsAtPath:pPanel.URL.path])
					   {
						   self.status = @"下载取消：请选择尚不存在的文件名。";
						   fnComplete(nil);
					   }
					   else
					   {
						   fnComplete(pPanel.URL);
					   }
				   }];
}

- (void)download:(WKDownload *)pDownload willPerformHTTPRedirection:(NSHTTPURLResponse *)pResponse newRequest:(NSURLRequest *)pRequest decisionHandler:(void (^)(WKDownloadRedirectPolicy))fnDecision API_AVAILABLE(macos(11.3))
{
	fnDecision([self allowsURL:pRequest.URL download:NO] ? WKDownloadRedirectPolicyAllow : WKDownloadRedirectPolicyCancel);
}

- (void)downloadDidFinish:(WKDownload *)pDownload API_AVAILABLE(macos(11.3))
{
	self.status = @"下载完成。";
	[self.downloads removeObject:pDownload];
}

- (void)download:(WKDownload *)pDownload didFailWithError:(NSError *)pError resumeData:(NSData *)pData API_AVAILABLE(macos(11.3))
{
	self.status = @"下载未完成，可从页面重新发起。";
	[self.downloads removeObject:pDownload];
}
@end

class WebPlatformMacOS final : public WebPlatformNative
{
	__strong WKWebView *pView = nil;
	__strong GodotWebPlatformDelegate *pDelegate = nil;
	std::string strInitialUrl;

public:
	WebPlatformMacOS(NSView *pParent, const std::string &strUrl, const std::string &strOrigin) :
			strInitialUrl(strUrl)
	{
		WKWebViewConfiguration *pConfiguration = [[WKWebViewConfiguration alloc] init];
		pConfiguration.websiteDataStore = [WKWebsiteDataStore defaultDataStore];
		pConfiguration.preferences.javaScriptCanOpenWindowsAutomatically = NO;
		pView = [[WKWebView alloc] initWithFrame:NSZeroRect configuration:pConfiguration];
		pView.hidden = YES;
		pView.allowsMagnification = YES;
		pDelegate = [[GodotWebPlatformDelegate alloc] init];
		pDelegate.active = YES;
		pDelegate.origin = [NSString stringWithUTF8String:strOrigin.c_str()];
		pDelegate.status = @"正在连接天璇…";
		pDelegate.panels = [NSMutableArray array];
		pDelegate.downloads = [NSMutableArray array];
		pDelegate.view = pView;
		pView.navigationDelegate = pDelegate;
		pView.UIDelegate = pDelegate;
		[pParent addSubview:pView];
		Navigate(strUrl);
	}

	~WebPlatformMacOS() override
	{
		SetVisible(false);
		[pDelegate shutdown];
		pView.navigationDelegate = nil;
		pView.UIDelegate = nil;
		[pView stopLoading];
		[pView removeFromSuperview];
		pView = nil;
		pDelegate = nil;
	}

	void SetBounds(double dX, double dY, double dWidth, double dHeight, double dParentWidth, double dParentHeight) override
	{
		NSView *pParent = pView.superview;
		if (pParent == nil || dParentWidth <= 0 || dParentHeight <= 0)
		{
			SetVisible(false);
			return;
		}
		const NSRect stParent = pParent.bounds;
		const double dScaleX = stParent.size.width / dParentWidth;
		const double dScaleY = stParent.size.height / dParentHeight;
		const NSRect stFrame = NSMakeRect(stParent.origin.x + dX * dScaleX,
				stParent.origin.y + (pParent.isFlipped ? dY : dParentHeight - dY - dHeight) * dScaleY,
				std::max(0.0, dWidth * dScaleX), std::max(0.0, dHeight * dScaleY));
		pView.frame = NSIntersectionRect(stFrame, stParent);
	}

	void SetVisible(bool bVisible) override
	{
		if (!bVisible && !pView.hidden)
		{
			NSResponder *pResponder = pView.window.firstResponder;
			if ([pResponder isKindOfClass:[NSView class]] && [(NSView *)pResponder isDescendantOf:pView])
			{
				[pView.window makeFirstResponder:pView.superview];
			}
		}
		pView.hidden = !bVisible;
	}

	void Navigate(const std::string &strUrl) override
	{
		NSURL *pUrl = [NSURL URLWithString:[NSString stringWithUTF8String:strUrl.c_str()]];
		if ([pDelegate allowsURL:pUrl download:NO])
		{
			[pView loadRequest:[NSURLRequest requestWithURL:pUrl]];
		}
	}
	void Back() override
	{
		[pView goBack];
	}
	void Forward() override
	{
		[pView goForward];
	}
	void Reload() override
	{
		if (pView.URL == nil)
		{
			Navigate(strInitialUrl);
		}
		else
		{
			[pView reload];
		}
	}
	bool CanGoBack() const override
	{
		return pView.canGoBack;
	}
	bool CanGoForward() const override
	{
		return pView.canGoForward;
	}
	std::string GetStatus() const override
	{
		return pDelegate.status.UTF8String;
	}
};

WebPlatformNative *WebPlatformNative::Create(void *pNativeParent, const std::string &strUrl)
{
	std::string strOrigin;
	if (pNativeParent == nullptr || ![NSThread isMainThread] || !ParseWebPlatformOrigin(strUrl, strOrigin))
	{
		return nullptr;
	}
	return new WebPlatformMacOS((__bridge NSView *)pNativeParent, strUrl, strOrigin);
}
