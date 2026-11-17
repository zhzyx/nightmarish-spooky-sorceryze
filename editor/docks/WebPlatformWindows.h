/**************************************************************************/
/*  WebPlatformWindows.h                                                  */
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

#include "editor/docks/WebPlatformNative.h"

#include <memory>

struct WebPlatformWindowsState;

class WebPlatformWindows final : public WebPlatformNative
{
public:
	WebPlatformWindows(void *pNativeParent, const std::string &strUrl, const std::string &strOrigin);
	~WebPlatformWindows() override;
	void SetBounds(double dX, double dY, double dWidth, double dHeight, double dParentWidth, double dParentHeight) override;
	void SetVisible(bool bVisible) override;
	void Navigate(const std::string &strUrl) override;
	void Back() override;
	void Forward() override;
	void Reload() override;
	bool CanGoBack() const override;
	bool CanGoForward() const override;
	std::string GetStatus() const override;
#ifdef WEB_PLATFORM_WINDOWS_TESTS
	// Borrowed COM interfaces, solely for the standalone runtime harness.
	void *TestGetWebView() const;
	void *TestGetController() const;
#endif

private:
	std::shared_ptr<WebPlatformWindowsState> ptrState;
};
