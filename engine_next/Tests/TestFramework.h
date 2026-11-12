/**************************************************************************/
/*  TestFramework.h                                                       */
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

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

namespace EngineNext::Tests
{

using TestFunction = void (*)();

struct TestCase
{
	const char *pName;
	TestFunction pFunction;
};

inline std::vector<TestCase> &GetRegistry()
{
	static std::vector<TestCase> arrRegistry;
	return arrRegistry;
}

inline int &GetCheckCount()
{
	static int nCount = 0;
	return nCount;
}

inline int &GetFailureCount()
{
	static int nCount = 0;
	return nCount;
}

inline bool RegisterTest(const char *pName, TestFunction pFunction)
{
	GetRegistry().push_back(TestCase{ pName, pFunction });
	return true;
}

inline void Check(bool bCondition, const char *pExpression, const char *pFile, int nLine)
{
	++GetCheckCount();
	if (!bCondition)
	{
		++GetFailureCount();
		std::cerr << pFile << ':' << nLine << ": check failed: " << pExpression << '\n';
	}
}

template <typename ActualType, typename ExpectedType>
void CheckEqual(const ActualType &in_Actual, const ExpectedType &in_Expected, const char *pExpression, const char *pFile, int nLine)
{
	Check(in_Actual == in_Expected, pExpression, pFile, nLine);
}

inline std::uint32_t FloatBits(float fValue)
{
	static_assert(sizeof(float) == sizeof(std::uint32_t), "The trace requires 32-bit float values.");
	std::uint32_t nBits = 0;
	std::memcpy(&nBits, &fValue, sizeof(nBits));
	return nBits;
}

} // namespace EngineNext::Tests

#define ENGINE_NEXT_TEST_JOIN_IMPL(m_Left, m_Right) m_Left##m_Right
#define ENGINE_NEXT_TEST_JOIN(m_Left, m_Right) ENGINE_NEXT_TEST_JOIN_IMPL(m_Left, m_Right)
#define ENGINE_NEXT_TEST_IMPL(m_Name, m_Index)                                                                 \
	static void ENGINE_NEXT_TEST_JOIN(TestFunction_, m_Index)();                                                \
	static const bool ENGINE_NEXT_TEST_JOIN(bRegistered_, m_Index) =                                            \
		EngineNext::Tests::RegisterTest(m_Name, &ENGINE_NEXT_TEST_JOIN(TestFunction_, m_Index));                \
	static void ENGINE_NEXT_TEST_JOIN(TestFunction_, m_Index)()
#define ENGINE_NEXT_TEST(m_Name) ENGINE_NEXT_TEST_IMPL(m_Name, __COUNTER__)
#define ENGINE_NEXT_CHECK(m_Condition) EngineNext::Tests::Check(static_cast<bool>(m_Condition), #m_Condition, __FILE__, __LINE__)
#define ENGINE_NEXT_CHECK_EQ(m_Actual, m_Expected) EngineNext::Tests::CheckEqual((m_Actual), (m_Expected), #m_Actual " == " #m_Expected, __FILE__, __LINE__)
#define ENGINE_NEXT_CHECK_FLOAT(m_Actual, m_Expected) ENGINE_NEXT_CHECK_EQ(EngineNext::Tests::FloatBits(m_Actual), EngineNext::Tests::FloatBits(m_Expected))
