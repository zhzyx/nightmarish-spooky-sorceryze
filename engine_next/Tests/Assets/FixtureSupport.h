/**************************************************************************/
/*  FixtureSupport.h                                                      */
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

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace EngineNext::Tests::Assets
{

inline std::filesystem::path FixtureRoot()
{
	return std::filesystem::path(__FILE__).parent_path() / "../Fixtures/M3";
}

inline std::vector<std::uint8_t> ReadFixture(const std::string &in_strName)
{
	const std::filesystem::path stPath = FixtureRoot() / in_strName;
	std::ifstream stStream(stPath, std::ios::binary | std::ios::ate);
	if (!stStream || stStream.tellg() < 0)
	{
		return {};
	}
	std::vector<std::uint8_t> arrBytes(static_cast<std::size_t>(stStream.tellg()));
	stStream.seekg(0);
	if (!arrBytes.empty())
	{
		stStream.read(reinterpret_cast<char *>(arrBytes.data()), static_cast<std::streamsize>(arrBytes.size()));
	}
	return arrBytes;
}

} // namespace EngineNext::Tests::Assets
