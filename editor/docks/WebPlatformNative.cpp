/**************************************************************************/
/*  WebPlatformNative.cpp                                                 */
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

#include "WebPlatformNative.h"

#include <algorithm>
#include <cstdint>

bool ParseWebPlatformOrigin(const std::string &strUrl, std::string &out_strOrigin)
{
	out_strOrigin.clear();
	if (strUrl.size() > 8192 || strUrl.find_first_of("\\\r\n\t ") != std::string::npos)
	{
		return false;
	}
	for (unsigned char nCharacter : strUrl)
	{
		if (nCharacter < 32 || nCharacter == 127)
		{
			return false;
		}
	}
	const std::size_t nSeparator = strUrl.find("://");
	if (nSeparator == std::string::npos)
	{
		return false;
	}
	std::string strScheme = strUrl.substr(0, nSeparator);
	std::transform(strScheme.begin(), strScheme.end(), strScheme.begin(), [](unsigned char nCharacter)
			{
				return static_cast<char>(nCharacter >= 'A' && nCharacter <= 'Z' ? nCharacter + 32 : nCharacter);
			});
	if (strScheme != "https" && strScheme != "http")
	{
		return false;
	}
	const std::size_t nEnd = strUrl.find_first_of("/?#", nSeparator + 3);
	std::string strHost = strUrl.substr(nSeparator + 3, nEnd == std::string::npos ? nEnd : nEnd - nSeparator - 3);
	if (strHost.empty() || strHost.find_first_of("@%") != std::string::npos)
	{
		return false;
	}
	std::transform(strHost.begin(), strHost.end(), strHost.begin(), [](unsigned char nCharacter)
			{
				return static_cast<char>(nCharacter >= 'A' && nCharacter <= 'Z' ? nCharacter + 32 : nCharacter);
			});
	const std::size_t nPortPosition = strHost.front() == '[' ? strHost.find(':', strHost.find(']')) : strHost.find(':');
	std::uint32_t nPort = strScheme == "https" ? 443 : 80;
	if (nPortPosition != std::string::npos)
	{
		const std::string strPort = strHost.substr(nPortPosition + 1);
		if (strPort.empty() || strPort.size() > 5 || strPort.find_first_not_of("0123456789") != std::string::npos)
		{
			return false;
		}
		nPort = 0;
		for (char nDigit : strPort)
		{
			nPort = nPort * 10 + static_cast<std::uint32_t>(nDigit - '0');
		}
		if (nPort == 0 || nPort > 65535)
		{
			return false;
		}
		strHost.resize(nPortPosition);
	}
	if (strHost != "[::1]" && (strHost.empty() || strHost.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789.-") != std::string::npos || strHost.front() == '.' || strHost.back() == '.'))
	{
		return false;
	}
	if (strScheme == "http" && strHost != "localhost" && strHost != "127.0.0.1" && strHost != "[::1]")
	{
		return false;
	}
	out_strOrigin = strScheme + "://" + strHost + ":" + std::to_string(nPort);
	return true;
}

bool IsWebPlatformNavigationAllowed(const std::string &strUrl, const std::string &strOrigin, bool bDownload)
{
	std::string strActualOrigin;
	const std::string strTarget = bDownload && strUrl.compare(0, 5, "blob:") == 0 ? strUrl.substr(5) : strUrl;
	return !strOrigin.empty() && ParseWebPlatformOrigin(strTarget, strActualOrigin) && strActualOrigin == strOrigin;
}

#ifndef MACOS_ENABLED
WebPlatformNative *WebPlatformNative::Create(void *, const std::string &)
{
	return nullptr;
}
#endif
