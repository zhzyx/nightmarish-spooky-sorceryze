/**************************************************************************/
/*  WebPlatformNative.h                                                   */
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

#include <string>

// Platform boundary only. All calls and destruction belong to the UI thread.
// The native parent is borrowed; Destroy must precede its destruction.
class WebPlatformNative
{
public:
	virtual ~WebPlatformNative() = default;
	virtual void SetBounds(double dX, double dY, double dWidth, double dHeight, double dParentWidth, double dParentHeight) = 0;
	virtual void SetVisible(bool bVisible) = 0;
	virtual void Navigate(const std::string &strUrl) = 0;
	virtual void Back() = 0;
	virtual void Forward() = 0;
	virtual void Reload() = 0;
	virtual bool CanGoBack() const = 0;
	virtual bool CanGoForward() const = 0;
	virtual std::string GetStatus() const = 0;
	static WebPlatformNative *Create(void *pNativeParent, const std::string &strUrl);
};

// Only an explicit HTTPS origin (or loopback HTTP) can become trusted.
// Reject userinfo, ambiguous authority spellings and non-web schemes.
bool ParseWebPlatformOrigin(const std::string &strUrl, std::string &out_strOrigin);
bool IsWebPlatformNavigationAllowed(const std::string &strUrl, const std::string &strOrigin, bool bDownload = false);
