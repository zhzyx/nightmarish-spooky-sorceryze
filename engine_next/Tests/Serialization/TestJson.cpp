/**************************************************************************/
/*  TestJson.cpp                                                          */
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
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <limits>

ENGINE_NEXT_TEST("Json parses portable values and writes canonical bytes")
{
	EngineNext::Serialization::JsonValue stValue;
	std::string strError;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson("{\"z\":1,\"a\":[true,null,\"\\u4e2d\"],\"n\":8.0}", stValue, strError));
	std::string strCanonical;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stValue, strCanonical));
	ENGINE_NEXT_CHECK_EQ(strCanonical, std::string("{\"a\":[true,null,\"中\"],\"n\":8.0,\"z\":1}"));
	EngineNext::Serialization::JsonValue stRoundtrip;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::ParseJson(strCanonical, stRoundtrip, strError));
	std::string strSecond;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stRoundtrip, strSecond));
	ENGINE_NEXT_CHECK_EQ(strSecond, strCanonical);
}

ENGINE_NEXT_TEST("Json rejects ambiguous, unsafe and nonfinite inputs")
{
	for (const std::string &strInput : { std::string("{\"a\":1,\"a\":2}"), std::string("01"), std::string("9223372036854775808"),
			 std::string("1e999"), std::string("\"\\ud800\""), std::string("[] trailing") })
	{
		EngineNext::Serialization::JsonValue stValue;
		std::string strError;
		ENGINE_NEXT_CHECK(!EngineNext::Serialization::ParseJson(strInput, stValue, strError));
		ENGINE_NEXT_CHECK(!strError.empty());
	}
	EngineNext::Serialization::JsonValue stInvalid(std::numeric_limits<double>::infinity());
	std::string strOutput;
	ENGINE_NEXT_CHECK(!EngineNext::Serialization::CanonicalJson(stInvalid, strOutput));
}

ENGINE_NEXT_TEST("Json depth and exponent output are deterministic")
{
	std::string strDeep = "[";
	for (int nIndex = 0; nIndex < 34; ++nIndex)
	{
		strDeep += "[";
	}
	for (int nIndex = 0; nIndex < 35; ++nIndex)
	{
		strDeep += "]";
	}
	EngineNext::Serialization::JsonValue stValue;
	std::string strError;
	ENGINE_NEXT_CHECK(!EngineNext::Serialization::ParseJson(strDeep, stValue, strError));
	stValue = EngineNext::Serialization::JsonValue(1e-7);
	std::string strOutput;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(stValue, strOutput));
	ENGINE_NEXT_CHECK_EQ(strOutput, std::string("1e-7"));
}
