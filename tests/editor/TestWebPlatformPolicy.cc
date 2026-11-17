/**************************************************************************/
/*  TestWebPlatformPolicy.cc                                              */
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

#include <cassert>
#include <iostream>
#include <string>

int main()
{
	std::string strOrigin;
	assert(ParseWebPlatformOrigin("https://Workspace.Example/docs", strOrigin));
	assert(strOrigin == "https://workspace.example:443");
	assert(IsWebPlatformNavigationAllowed("https://workspace.example:443/docs/a?tab=history#v2", strOrigin));
	assert(!IsWebPlatformNavigationAllowed("https://workspace.example.evil/docs", strOrigin));
	assert(!IsWebPlatformNavigationAllowed("https://workspace.example:444/", strOrigin));
	assert(!IsWebPlatformNavigationAllowed("http://workspace.example/", strOrigin));
	assert(!IsWebPlatformNavigationAllowed("blob:https://workspace.example/a", strOrigin));
	assert(IsWebPlatformNavigationAllowed("blob:https://workspace.example/a", strOrigin, true));
	assert(!IsWebPlatformNavigationAllowed("blob:https://other.example/a", strOrigin, true));
	for (const std::string &strUrl : { "http://localhost:3000/", "http://127.0.0.1:8000/", "http://[::1]:3000/", "https://example.com" })
	{
		assert(ParseWebPlatformOrigin(strUrl, strOrigin));
	}
	for (const std::string &strUrl : { "", "file:///etc/passwd", "javascript:alert(1)", "https://user:pass@example.com/", "https://user@example.com/", "http://192.168.1.1/", "http://localhost.evil/", "http://127.1/", "https://example.com:0", "https://example.com:65536", "https://example.com:443.evil/", "https://example.com\\@evil/", "https://example.com%2Fevil/", "https://example.com\n/path", "https://example.com /", "//example.com/", "https:///example.com", "https://[::1", "https://example.com:", "https://example.com./", "https://example.com:443@evil/" })
	{
		assert(!ParseWebPlatformOrigin(strUrl, strOrigin));
		assert(strOrigin.empty());
	}
	assert(!ParseWebPlatformOrigin(std::string("https://example.com/\0evil", 24), strOrigin));
	assert(!ParseWebPlatformOrigin("https://example.com/" + std::string(8192, 'x'), strOrigin));
	std::cout << "WEB_PLATFORM_POLICY_OK\n";
}
