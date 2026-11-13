/**************************************************************************/
/*  test_ai_chat_receipt.cpp                                              */
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

#include "tests/test_macros.h"
TEST_FORCE_LINK(test_ai_chat_receipt)

#ifdef TOOLS_ENABLED
#include "core/io/dir_access.h"
#include "editor/docks/ai_chat_receipt.h"
#include "tests/test_utils.h"
#ifdef WINDOWS_ENABLED
#include <windows.h>
#endif

namespace TestAIChatReceipt {
TEST_CASE("[AIChat] Receipt parse failures retain private bytes and expose bounded status") {
	const String strPath = TestUtils::get_temp_path("chat-receipt.json");
	for (const String &strBody : { String("{\n\"private\": "), String("[]"), String("{\"ok\":1}"), String("{}"), String("{\"ok\":true}") }) {
		Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
		REQUIRE(refFile.is_valid());
		refFile->store_string(strBody);
		refFile.unref();
		const Dictionary dictResult = AIChatReceipt::Read(strPath);
		CHECK(FileAccess::get_file_as_string(strPath) == strBody);
		if (strBody == "{\"ok\":true}") {
			CHECK(dictResult["receipt_status"] == "valid");
			CHECK(bool(dictResult["ok"]));
		} else {
			CHECK_FALSE(bool(dictResult["ok"]));
			CHECK(dictResult["receipt_status"] == (strBody.contains("private") ? "parse_failed" : "invalid_schema"));
			CHECK_FALSE(JSON::stringify(dictResult).contains("private"));
		}
	}
	DirAccess::remove_absolute(strPath);
	CHECK(AIChatReceipt::Read(strPath)["receipt_status"] == "missing");
}

TEST_CASE("[AIChat] Receipt invalid UTF8 and raw NUL fail closed without deleting evidence") {
	const String strPath = TestUtils::get_temp_path("chat-receipt-encoding.json");
	const uint8_t aInvalid[] = { 0x80 };
	Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
	REQUIRE(refFile.is_valid());
	refFile->store_buffer(aInvalid, sizeof(aInvalid));
	refFile.unref();
	ERR_PRINT_OFF;
	const Dictionary dictInvalid = AIChatReceipt::Read(strPath);
	ERR_PRINT_ON;
	CHECK(dictInvalid["receipt_status"] == "invalid_utf8");
	CHECK_FALSE(bool(dictInvalid["ok"]));
	CHECK(FileAccess::exists(strPath));
	const char szNullBody[] = "{\"ok\":true}\0private";
	refFile = FileAccess::open(strPath, FileAccess::WRITE);
	REQUIRE(refFile.is_valid());
	refFile->store_buffer(reinterpret_cast<const uint8_t *>(szNullBody), sizeof(szNullBody) - 1);
	refFile.unref();
	const Dictionary dictNull = AIChatReceipt::Read(strPath);
	CHECK(dictNull["receipt_status"] == "parse_failed");
	CHECK_FALSE(bool(dictNull["ok"]));
	refFile = FileAccess::open(strPath, FileAccess::READ);
	REQUIRE(refFile.is_valid());
	CHECK(refFile->get_length() == sizeof(szNullBody) - 1);
	refFile.unref();
	DirAccess::remove_absolute(strPath);
}

TEST_CASE("[AIChat] Receipt access retry rejects permanent errors and respects count and time bounds") {
	CHECK(AIChatReceipt::CanRetry(ERR_BUSY, 1, 100, 1000));
	CHECK_FALSE(AIChatReceipt::CanRetry(ERR_BUSY, 6, 100, 1000));
	CHECK_FALSE(AIChatReceipt::CanRetry(ERR_BUSY, 1, 1000, 1000));
	for (const Error eError : { OK, ERR_FILE_NOT_FOUND, ERR_FILE_CANT_OPEN, ERR_FILE_NO_PERMISSION, ERR_PARSE_ERROR }) {
		CHECK_FALSE(AIChatReceipt::CanRetry(eError, 1, 100, 1000));
	}
}

#ifdef WINDOWS_ENABLED
TEST_CASE("[AIChat] Windows receipt sharing violation is transient and unlock recovers original bytes") {
	const String strPath = TestUtils::get_temp_path("chat-receipt-locked.json");
	Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::WRITE);
	REQUIRE(refFile.is_valid());
	refFile->store_string("{\"ok\":true}");
	refFile.unref();
	HANDLE hLock = CreateFileW(reinterpret_cast<LPCWSTR>(strPath.utf16().get_data()), GENERIC_READ, 0, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
	REQUIRE(hLock != INVALID_HANDLE_VALUE);
	const Dictionary dictLocked = AIChatReceipt::Read(strPath);
	CloseHandle(hLock);
	CHECK(dictLocked["receipt_status"] == "read_failed");
	CHECK(int(dictLocked["receipt_io_error"]) == ERR_BUSY);
	CHECK(bool(AIChatReceipt::Read(strPath)["ok"]));
	CHECK(FileAccess::exists(strPath));
	DirAccess::remove_absolute(strPath);
}
#endif
} // namespace TestAIChatReceipt
#endif // TOOLS_ENABLED
