/**************************************************************************/
/*  ai_chat_receipt.h                                                     */
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

#include "core/io/file_access.h"
#include "core/io/json.h"

// Transport validation never executes or replays the completed bridge action.
namespace AIChatReceipt {
static bool CanRetry(Error eError, uint32_t uAttempts, uint64_t uNow, uint64_t uDeadline) {
	return eError == ERR_BUSY && uAttempts < 6 && uNow < uDeadline;
}

static Dictionary Read(const String &strPath) {
	Dictionary dictResult;
	dictResult["ok"] = false;
	Error eRead = OK;
	Ref<FileAccess> refFile = FileAccess::open(strPath, FileAccess::READ, &eRead);
	dictResult["receipt_io_error"] = eRead;
	if (refFile.is_null()) {
		dictResult["receipt_status"] = eRead == ERR_FILE_NOT_FOUND ? "missing" : "read_failed";
		return dictResult;
	}
	const uint64_t uLength = refFile->get_length();
	if (uLength > 1024 * 1024) {
		dictResult["receipt_status"] = "oversized";
		return dictResult;
	}
	Vector<uint8_t> vecBytes;
	vecBytes.resize(uLength);
	const uint64_t uRead = uLength ? refFile->get_buffer(vecBytes.ptrw(), uLength) : 0;
	eRead = refFile->get_error();
	dictResult["receipt_io_error"] = eRead;
	if (uRead != uLength || (eRead != OK && eRead != ERR_FILE_EOF)) {
		dictResult["receipt_status"] = "read_failed";
		return dictResult;
	}
	// append_utf8 stops at NUL even with an explicit length. A raw NUL is not
	// legal JSON; reject it so a valid prefix cannot hide unread trailing bytes.
	if (vecBytes.find(0) >= 0) {
		dictResult["receipt_status"] = "parse_failed";
		return dictResult;
	}
	String strContent;
	if (uLength && strContent.append_utf8(reinterpret_cast<const char *>(vecBytes.ptr()), int(uLength)) != OK) {
		dictResult["receipt_status"] = "invalid_utf8";
		return dictResult;
	}
	JSON jsonParser;
	if (jsonParser.parse(strContent) != OK) {
		dictResult["receipt_status"] = "parse_failed";
		dictResult["receipt_parse_line"] = jsonParser.get_error_line();
		// Parser messages can quote user data; expose only the bounded line number.
		return dictResult;
	}
	const Variant varParsed = jsonParser.get_data();
	if (varParsed.get_type() != Variant::DICTIONARY || Dictionary(varParsed).get("ok", Variant()).get_type() != Variant::BOOL) {
		dictResult["receipt_status"] = "invalid_schema";
		return dictResult;
	}
	dictResult = varParsed;
	dictResult["receipt_status"] = "valid";
	dictResult["receipt_io_error"] = OK;
	dictResult.erase("receipt_parse_line");
	return dictResult;
}
} // namespace AIChatReceipt
