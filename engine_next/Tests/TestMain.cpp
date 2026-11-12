/**************************************************************************/
/*  TestMain.cpp                                                          */
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

#include "engine_next/Tests/TestFramework.h"

#include <cstring>
#include <iostream>

namespace EngineNext::Tests
{

bool WritePredictionTrace(const char *pPath);

} // namespace EngineNext::Tests

int main(int nArgumentCount, char **ppArguments)
{
	const char *pTracePath = nullptr;
	for (int nIndex = 1; nIndex < nArgumentCount; ++nIndex)
	{
		if (std::strcmp(ppArguments[nIndex], "--trace-output") == 0 && nIndex + 1 < nArgumentCount)
		{
			pTracePath = ppArguments[++nIndex];
			continue;
		}
		std::cerr << "Unknown argument: " << ppArguments[nIndex] << '\n';
		return 2;
	}

	for (const EngineNext::Tests::TestCase &stTest : EngineNext::Tests::GetRegistry())
	{
		stTest.pFunction();
	}

	if (pTracePath != nullptr && !EngineNext::Tests::WritePredictionTrace(pTracePath))
	{
		std::cerr << "Could not write the prediction trace.\n";
		return 2;
	}

	const int nFailures = EngineNext::Tests::GetFailureCount();
	std::cout << "ENGINE_NEXT_TEST_SUMMARY tests=" << EngineNext::Tests::GetRegistry().size()
			  << " checks=" << EngineNext::Tests::GetCheckCount() << " failures=" << nFailures << '\n';
	return nFailures == 0 ? 0 : 1;
}
