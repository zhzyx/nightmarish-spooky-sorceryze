/**************************************************************************/
/*  CVars.cpp                                                            */
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

#include "core/config/CVars.h"

#include "core/config/engine.h"
#include "core/debugger/engine_debugger.h"
#include "core/io/file_access.h"
#include "core/object/class_db.h"
#include "core/os/os.h"
#include "core/string/print_string.h"

static std::atomic<double> atomBuiltinTimeScale{ 1.0 };
static std::atomic<int32_t> atomBuiltinMaxFps{ 0 };

static void ApplyTimeScale(void *pUserdata)
{
	(void)pUserdata;
	Engine *pEngine = Engine::get_singleton();
	if (pEngine)
	{
		pEngine->set_time_scale(atomBuiltinTimeScale.load(std::memory_order_acquire));
	}
}

static void ApplyMaxFps(void *pUserdata)
{
	(void)pUserdata;
	Engine *pEngine = Engine::get_singleton();
	if (!pEngine)
	{
		return;
	}
	int nFps = atomBuiltinMaxFps.load(std::memory_order_acquire);
	pEngine->set_max_fps(nFps);
}

StringName CVars::KeyOf(const String &in_strName)
{
	return StringName(in_strName.to_lower());
}

bool CVars::IsValidName(const String &in_strName, String &out_strError)
{
	if (in_strName.is_empty())
	{
		out_strError = "Name is empty.";
		return false;
	}
	for (int nI = 0; nI < in_strName.length(); nI++)
	{
		const char32_t chC = in_strName[nI];
		if (chC <= 32 || chC == '=' || chC == ';' || chC == '"' || chC == '#')
		{
			out_strError = "Name contains a space, quote, or separator.";
			return false;
		}
	}
	return true;
}

bool CVars::IsBuiltinName(const String &in_strKey)
{
	return in_strKey == "help" || in_strKey == "?" || in_strKey == "dump" || in_strKey == "reset";
}

bool CVars::ParseBoolWord(const String &in_strText, bool &out_bValue)
{
	const String strText = in_strText.strip_edges().to_lower();
	if (strText == "1" || strText == "true" || strText == "on" || strText == "yes")
	{
		out_bValue = true;
		return true;
	}
	if (strText == "0" || strText == "false" || strText == "off" || strText == "no")
	{
		out_bValue = false;
		return true;
	}
	return false;
}

static bool FitsInt32(int64_t in_nValue)
{
	return in_nValue >= INT32_MIN && in_nValue <= INT32_MAX;
}

static bool ConvertInteger(double in_dValue, Variant &out_varValue, String &out_strError)
{
	// INT64_MAX rounds to 2^63 in double, so use an exclusive upper bound.
	constexpr double dUpperBound = 0x1p63;
	if (!(in_dValue >= -dUpperBound && in_dValue < dUpperBound))
	{
		out_strError = "Value is outside the signed 64-bit integer range.";
		return false;
	}
	out_varValue = static_cast<int64_t>(in_dValue);
	return true;
}

bool CVars::ParseText(Variant::Type in_eType, const String &in_strText, Variant &out_varOut, String &out_strError)
{
	const String strText = in_strText.strip_edges();
	bool bBoolean = false;
	const bool bIsBoolWord = ParseBoolWord(strText, bBoolean);
	switch (in_eType)
	{
	case Variant::BOOL: {
		if (!bIsBoolWord)
		{
			out_strError = "Expected true/false, on/off, yes/no, or 1/0.";
			return false;
		}
		out_varOut = bBoolean;
		return true;
	}
	break;
	case Variant::INT: {
		if (bIsBoolWord && !strText.is_valid_int())
		{
			out_varOut = bBoolean ? 1 : 0;
			return true;
		}
		if (strText.is_valid_int())
		{
			out_varOut = strText.to_int();
			return true;
		}
		if (strText.is_valid_float())
		{
			return ConvertInteger(strText.to_float(), out_varOut, out_strError);
		}
		out_strError = "Expected an int.";
		return false;
	}
	break;
	case Variant::FLOAT: {
		if (bIsBoolWord && !strText.is_valid_float())
		{
			out_varOut = bBoolean ? 1.0 : 0.0;
			return true;
		}
		if (strText.is_valid_float())
		{
			out_varOut = strText.to_float();
			return true;
		}
		out_strError = "Expected a float.";
		return false;
	}
	break;
	case Variant::STRING: {
		out_varOut = strText;
		return true;
	}
	break;
	default: {
		out_strError = "Unsupported variable type.";
		return false;
	}
	break;
	}
}

bool CVars::Coerce(Variant::Type in_eType, const Variant &varIn, Variant &out_varOut, String &out_strError)
{
	if (varIn.get_type() == Variant::STRING)
	{
		return ParseText(in_eType, varIn, out_varOut, out_strError);
	}
	switch (in_eType)
	{
	case Variant::BOOL: {
		if (varIn.get_type() == Variant::BOOL)
		{
			out_varOut = varIn;
			return true;
		}
		if (varIn.get_type() == Variant::INT || varIn.get_type() == Variant::FLOAT)
		{
			out_varOut = bool(varIn);
			return true;
		}
	}
	break;
	case Variant::INT: {
		if (varIn.get_type() == Variant::INT)
		{
			out_varOut = varIn;
			return true;
		}
		if (varIn.get_type() == Variant::FLOAT)
		{
			return ConvertInteger(double(varIn), out_varOut, out_strError);
		}
		if (varIn.get_type() == Variant::BOOL)
		{
			out_varOut = bool(varIn) ? 1 : 0;
			return true;
		}
	}
	break;
	case Variant::FLOAT: {
		if (varIn.get_type() == Variant::FLOAT || varIn.get_type() == Variant::INT)
		{
			out_varOut = (double)varIn;
			return true;
		}
		if (varIn.get_type() == Variant::BOOL)
		{
			out_varOut = bool(varIn) ? 1.0 : 0.0;
			return true;
		}
	}
	break;
	case Variant::STRING: {
		out_varOut = String(varIn);
		return true;
	}
	break;
	default:
		break;
	}
	if (varIn.get_type() != Variant::NIL)
	{
		return ParseText(in_eType, String(varIn), out_varOut, out_strError);
	}
	out_strError = "Unsupported value.";
	return false;
}

bool CVars::SameValue(Variant::Type in_eType, const Variant &varA, const Variant &varB)
{
	switch (in_eType)
	{
	case Variant::INT:
		return (int64_t)varA == (int64_t)varB;
	case Variant::FLOAT:
		return (double)varA == (double)varB;
	case Variant::BOOL:
		return bool(varA) == bool(varB);
	case Variant::STRING:
		return String(varA) == String(varB);
	default:
		return false;
	}
}

String CVars::FormatValue(const Variant &in_varValue)
{
	if (in_varValue.get_type() == Variant::BOOL)
	{
		return bool(in_varValue) ? "true" : "false";
	}
	return String(in_varValue);
}

const char *CVars::TypeName(Variant::Type in_eType)
{
	switch (in_eType)
	{
	case Variant::INT:
		return "int";
	case Variant::FLOAT:
		return "float";
	case Variant::BOOL:
		return "bool";
	case Variant::STRING:
		return "String";
	default:
		return "?";
	}
}

const char *CVars::SetByName(SetBy in_eSetBy)
{
	switch (in_eSetBy)
	{
	case SET_BY_CONSTRUCTOR:
		return "constructor";
	case SET_BY_PROJECT_SETTING:
		return "project";
	case SET_BY_CONFIG_FILE:
		return "config";
	case SET_BY_COMMAND_LINE:
		return "command_line";
	case SET_BY_CODE:
		return "code";
	case SET_BY_CONSOLE:
		return "console";
	}
	return "unknown";
}

String CVars::Unquote(const String &in_strText)
{
	const String strText = in_strText.strip_edges();
	if (strText.length() >= 2 && strText[0] == '"' && strText[strText.length() - 1] == '"')
	{
		return strText.substr(1, strText.length() - 2);
	}
	return strText;
}

Vector<String> CVars::SplitCommands(const String &in_strLine)
{
	Vector<String> arrParts;
	String strCurrent;
	bool bQuoted = false;
	for (int nI = 0; nI < in_strLine.length(); nI++)
	{
		const char32_t chC = in_strLine[nI];
		if (chC == '"')
		{
			bQuoted = !bQuoted;
			strCurrent += chC;
		}
		else if (chC == ';' && !bQuoted)
		{
			arrParts.push_back(strCurrent.strip_edges());
			strCurrent = String();
		}
		else
		{
			strCurrent += chC;
		}
	}
	strCurrent = strCurrent.strip_edges();
	if (!strCurrent.is_empty())
	{
		arrParts.push_back(strCurrent);
	}
	return arrParts;
}

Vector<String> CVars::Tokenize(const String &in_strText)
{
	Vector<String> arrTokens;
	String strCurrent;
	bool bQuoted = false;
	for (int nI = 0; nI < in_strText.length(); nI++)
	{
		const char32_t chC = in_strText[nI];
		if (chC == '"')
		{
			bQuoted = !bQuoted;
			continue;
		}
		if (!bQuoted && (chC == ' ' || chC == '\t'))
		{
			if (!strCurrent.is_empty())
			{
				arrTokens.push_back(strCurrent);
				strCurrent = String();
			}
			continue;
		}
		strCurrent += chC;
	}
	if (!strCurrent.is_empty())
	{
		arrTokens.push_back(strCurrent);
	}
	return arrTokens;
}

void CVars::DeferPendingLocked(const String &in_strName, const String &in_strText, SetBy in_eSetBy)
{
	const StringName snKey = KeyOf(in_strName);
	if (Pending *pFound = mapPending.getptr(snKey))
	{
		if (in_eSetBy < pFound->eSetBy)
		{
			return;
		}
		pFound->strText = in_strText;
		pFound->bHasText = true;
		pFound->eSetBy = in_eSetBy;
		return;
	}
	Pending stItem;
	stItem.strText = in_strText;
	stItem.bHasText = true;
	stItem.eSetBy = in_eSetBy;
	mapPending.insert(snKey, stItem);
}

// Commands can be registered by a script long after the startup lines ran (a demo registers its
// debug commands in _ready). Keep the whole line so register_command() can replay it, which is the
// command-side counterpart of the value kept by _defer_pending_locked().
void CVars::DeferPendingLineLocked(const String &in_strName, const String &in_strLine, SetBy in_eSetBy)
{
	const StringName snKey = KeyOf(in_strName);
	if (Pending *pFound = mapPending.getptr(snKey))
	{
		if (in_eSetBy < pFound->eSetBy)
		{
			return;
		}
		pFound->strLine = in_strLine;
		pFound->bHasLine = true;
		pFound->eSetBy = in_eSetBy;
		return;
	}
	Pending stItem;
	stItem.strLine = in_strLine;
	stItem.bHasLine = true;
	stItem.eSetBy = in_eSetBy;
	mapPending.insert(snKey, stItem);
}

CVars::Variable *CVars::GetVariable(const String &in_strName)
{
	Variable **pSlot = mapVariables.getptr(KeyOf(in_strName));
	return pSlot ? *pSlot : nullptr;
}

const CVars::Variable *CVars::GetVariable(const String &in_strName) const
{
	Variable *const *pSlot = mapVariables.getptr(KeyOf(in_strName));
	return pSlot ? *pSlot : nullptr;
}

bool CVars::IsUserSource(SetBy in_eSetBy) const
{
	return in_eSetBy == SET_BY_CONFIG_FILE || in_eSetBy == SET_BY_COMMAND_LINE || in_eSetBy == SET_BY_CONSOLE;
}

bool CVars::Allows(const Variable *in_pVariable, SetBy in_eSetBy, String &out_strError) const
{
	if ((in_pVariable->nFlags & FLAG_READ_ONLY) && IsUserSource(in_eSetBy))
	{
		out_strError = vformat("error: %s is read-only", in_pVariable->strName);
		return false;
	}
	if ((in_pVariable->nFlags & FLAG_CHEAT) && IsUserSource(in_eSetBy) && !bCheatCommandsAllowed)
	{
		out_strError = vformat("error: %s is marked cheat and cheat commands are disabled", in_pVariable->strName);
		return false;
	}
	if (in_eSetBy < in_pVariable->eSetBy)
	{
		out_strError = vformat("error: ignored %s (current priority %s, attempted %s)", in_pVariable->strName, SetByName(in_pVariable->eSetBy), SetByName(in_eSetBy));
		return false;
	}
	return true;
}

void CVars::WriteShadow(Variable *in_pVariable)
{
	switch (in_pVariable->eType)
	{
	case Variant::INT: {
		if (!(in_pVariable->nFlags & FLAG_RENDER_THREAD_SAFE))
		{
			break;
		}
		const int32_t nValue = static_cast<int32_t>(int64_t(in_pVariable->varValue));
		in_pVariable->atomShadowInt.store(nValue, std::memory_order_release);
		if (in_pVariable->pIntRef)
		{
			in_pVariable->pIntRef->store(nValue, std::memory_order_release);
		}
	}
	break;
	case Variant::BOOL: {
		const int32_t nValue = bool(in_pVariable->varValue) ? 1 : 0;
		in_pVariable->atomShadowInt.store(nValue, std::memory_order_release);
		if (in_pVariable->pBoolRef)
		{
			in_pVariable->pBoolRef->store(nValue, std::memory_order_release);
		}
	}
	break;
	case Variant::FLOAT: {
		const double dValue = in_pVariable->varValue;
		in_pVariable->atomShadowFloat.store(dValue, std::memory_order_release);
		if (in_pVariable->pFloatRef)
		{
			in_pVariable->pFloatRef->store(dValue, std::memory_order_release);
		}
	}
	break;
	default:
		break;
	}
}

String CVars::Describe(const Variable *in_pVariable) const
{
	String strTags = TypeName(in_pVariable->eType);
	if (in_pVariable->nFlags & FLAG_CHEAT)
	{
		strTags += ", cheat";
	}
	if (in_pVariable->nFlags & FLAG_READ_ONLY)
	{
		strTags += ", read-only";
	}
	if (in_pVariable->nFlags & FLAG_RENDER_THREAD_SAFE)
	{
		strTags += ", render-thread";
	}
	return vformat("%s = %s (%s) [%s] %s", in_pVariable->strName, FormatValue(in_pVariable->varValue), SetByName(in_pVariable->eSetBy), strTags, in_pVariable->strHelp);
}

void CVars::FireChanged(const Callable &in_cbCallback, ChangedCallback pFn, void *pUd, const String &in_strName, const Variant &in_varValue)
{
	if (pFn)
	{
		pFn(pUd);
	}
	if (in_cbCallback.is_valid())
	{
		in_cbCallback.call(in_strName, in_varValue);
	}
}

CVars::AssignResult CVars::Assign(const String &in_strName, const Variant &in_varValue, SetBy in_eSetBy, bool bDeferUnknown)
{
	AssignResult stResult;
	Callable cbScriptCb;
	ChangedCallback pChangedFn = nullptr;
	void *pChangedUd = nullptr;
	String strCallbackName;
	Variant varCallbackValue;
	bool bFire = false;

	{
		MutexLock lockRegistry(mtxMutex);
		Variable *pVariable = GetVariable(in_strName);
		if (!pVariable)
		{
			if (bDeferUnknown)
			{
				const String strText = in_varValue.get_type() == Variant::STRING ? String(in_varValue) : FormatValue(in_varValue);
				DeferPendingLocked(in_strName, strText, in_eSetBy);
				stResult.bAccepted = true;
				return stResult;
			}
			stResult.strMessage = vformat("error: unknown command or variable '%s'", in_strName);
			return stResult;
		}

		String strError;
		if (!Allows(pVariable, in_eSetBy, strError))
		{
			stResult.strMessage = strError;
			return stResult;
		}

		Variant varCoerced;
		if (!Coerce(pVariable->eType, in_varValue, varCoerced, strError))
		{
			stResult.strMessage = vformat("error: %s: %s", pVariable->strName, strError);
			return stResult;
		}

		if (pVariable->eType == Variant::INT && (pVariable->nFlags & FLAG_RENDER_THREAD_SAFE) && !FitsInt32(int64_t(varCoerced)))
		{
			stResult.strMessage = vformat("error: %s: Value is outside the signed 32-bit integer range.", pVariable->strName);
			return stResult;
		}
		const bool bChanged = !SameValue(pVariable->eType, pVariable->varValue, varCoerced);
		pVariable->varValue = varCoerced;
		pVariable->eSetBy = in_eSetBy;
		WriteShadow(pVariable);
		if (bChanged)
		{
			bFire = true;
			cbScriptCb = pVariable->cbChanged;
			pChangedFn = pVariable->pChangedFn;
			pChangedUd = pVariable->pChangedUd;
			strCallbackName = pVariable->strName;
			varCallbackValue = pVariable->varValue;
		}
		stResult.bAccepted = true;
		stResult.bChanged = bChanged;
		stResult.strMessage = vformat("%s = %s", pVariable->strName, FormatValue(pVariable->varValue));
	}

	if (bFire)
	{
		FireChanged(cbScriptCb, pChangedFn, pChangedUd, strCallbackName, varCallbackValue);
	}
	return stResult;
}

CVars::AssignResult CVars::AssignText(const String &in_strName, const String &in_strText, SetBy in_eSetBy, bool bDeferUnknown)
{
	{
		MutexLock lockRegistry(mtxMutex);
		if (!GetVariable(in_strName))
		{
			if (bDeferUnknown)
			{
				DeferPendingLocked(in_strName, in_strText, in_eSetBy);
				AssignResult stDeferred;
				stDeferred.bAccepted = true;
				return stDeferred;
			}
		}
	}
	return Assign(in_strName, in_strText, in_eSetBy, false);
}

String CVars::ExecuteOne(const String &in_strLine, SetBy in_eSetBy, bool bDeferUnknown)
{
	const String strLine = in_strLine.strip_edges();
	if (strLine.is_empty() || strLine[0] == '#' || strLine[0] == ';' || strLine[0] == '[')
	{
		return String();
	}

	int nSplit = 0;
	while (nSplit < strLine.length() && strLine[nSplit] != ' ' && strLine[nSplit] != '\t' && strLine[nSplit] != '=')
	{
		nSplit++;
	}
	const String strName = strLine.substr(0, nSplit);
	while (nSplit < strLine.length() && (strLine[nSplit] == ' ' || strLine[nSplit] == '\t'))
	{
		nSplit++;
	}

	bool bHasValue = false;
	String strRawValue;
	Vector<String> arrArgs;
	if (nSplit < strLine.length())
	{
		bHasValue = true;
		if (strLine[nSplit] == '=')
		{
			strRawValue = Unquote(strLine.substr(nSplit + 1));
			if (!strRawValue.is_empty())
			{
				arrArgs.push_back(strRawValue);
			}
		}
		else
		{
			const String strRest = strLine.substr(nSplit);
			strRawValue = Unquote(strRest);
			arrArgs = Tokenize(strRest);
		}
	}

	const String strKey = strName.to_lower();
	if (strKey == "help" || strKey == "?")
	{
		return Help(bHasValue ? strRawValue : String());
	}
	if (strKey == "dump")
	{
		const String strFilter = bHasValue ? strRawValue.strip_edges().to_lower() : String();
		Vector<String> arrLines;
		{
			MutexLock lockRegistry(mtxMutex);
			for (const KeyValue<StringName, Variable *> &stEntry : mapVariables)
			{
				if (!strFilter.is_empty() && !stEntry.value->strName.to_lower().contains(strFilter))
				{
					continue;
				}
				arrLines.push_back(Describe(stEntry.value));
			}
		}
		arrLines.sort();
		String strOut;
		for (int nI = 0; nI < arrLines.size(); nI++)
		{
			if (nI > 0)
			{
				strOut += "\n";
			}
			strOut += arrLines[nI];
		}
		return strOut;
	}
	if (strKey == "reset")
	{
		if (arrArgs.is_empty())
		{
			return "error: usage: reset <name>";
		}
		if (!Reset(arrArgs[0]))
		{
			if (!HasVariable(arrArgs[0]))
			{
				return vformat("error: unknown variable '%s'", arrArgs[0]);
			}
			Variable *pVariable = nullptr;
			String strMessage;
			{
				MutexLock lockRegistry(mtxMutex);
				pVariable = GetVariable(arrArgs[0]);
				if (pVariable)
				{
					Allows(pVariable, SET_BY_CONSOLE, strMessage);
				}
			}
			if (!strMessage.is_empty())
			{
				return strMessage;
			}
			return vformat("error: cannot reset '%s'", arrArgs[0]);
		}
		return vformat("%s = %s", arrArgs[0], FormatValue(GetValue(arrArgs[0])));
	}

	Callable cbCommandCallback;
	bool bFoundCommand = false;
	{
		MutexLock lockRegistry(mtxMutex);
		if (const Command *pCommand = mapCommands.getptr(KeyOf(strName)))
		{
			cbCommandCallback = pCommand->cbCallback;
			bFoundCommand = true;
		}
	}
	if (bFoundCommand)
	{
		if (!cbCommandCallback.is_valid())
		{
			return vformat("error: command '%s' has no callback", strName);
		}
		const Variant varResult = cbCommandCallback.call(arrArgs);
		if (varResult.get_type() == Variant::NIL)
		{
			return String();
		}
		return String(varResult);
	}

	if (!bHasValue)
	{
		MutexLock lockRegistry(mtxMutex);
		const Variable *pVariable = GetVariable(strName);
		if (!pVariable)
		{
			if (bDeferUnknown)
			{
				// Maybe a command, maybe a variable that is still read-only: keep the line and let
				// register_command() / register_variable() replay it.
				DeferPendingLineLocked(strName, strLine, in_eSetBy);
				return String();
			}
			return vformat("error: unknown command or variable '%s'", strName);
		}
		return Describe(pVariable);
	}

	if (bDeferUnknown)
	{
		MutexLock lockRegistry(mtxMutex);
		if (!GetVariable(strName) && !mapCommands.has(KeyOf(strName)))
		{
			DeferPendingLineLocked(strName, strLine, in_eSetBy);
		}
	}

	const AssignResult stAssigned = AssignText(strName, strRawValue, in_eSetBy, bDeferUnknown);
	return stAssigned.strMessage;
}

String CVars::ExecuteWithPriority(const String &strCommand, SetBy in_eSetBy, bool bDeferUnknown)
{
	const Vector<String> arrParts = SplitCommands(strCommand);
	String strOutput;
	for (const String &strPart : arrParts)
	{
		const String strOne = ExecuteOne(strPart, in_eSetBy, bDeferUnknown);
		if (strOne.is_empty())
		{
			continue;
		}
		if (!strOutput.is_empty())
		{
			strOutput += "\n";
		}
		strOutput += strOne;
	}
	return strOutput;
}

bool CVars::Register(const String &in_strName, const Variant &varDefault, const String &in_strHelp, uint32_t in_nFlags, std::atomic<int32_t> *in_pIntRef, std::atomic<double> *in_pFloatRef, std::atomic<int32_t> *in_pBoolRef, ChangedCallback pChanged, void *pUserdata)
{
	String strNameError;
	ERR_FAIL_COND_V_MSG(!IsValidName(in_strName, strNameError), false, strNameError);
	const StringName snKey = KeyOf(in_strName);
	ERR_FAIL_COND_V_MSG(IsBuiltinName(String(snKey)), false, vformat("'%s' is a built-in console command.", in_strName));

	Variant::Type eType = varDefault.get_type();
	if (in_pFloatRef)
	{
		eType = Variant::FLOAT;
	}
	else if (in_pBoolRef)
	{
		eType = Variant::BOOL;
	}
	else if (in_pIntRef)
	{
		eType = Variant::INT;
	}
	ERR_FAIL_COND_V_MSG(eType != Variant::INT && eType != Variant::FLOAT && eType != Variant::BOOL && eType != Variant::STRING, false, "CVars only support int, float, bool, and String.");
	ERR_FAIL_COND_V_MSG(eType == Variant::INT && (in_pIntRef || (in_nFlags & FLAG_RENDER_THREAD_SAFE)) && !FitsInt32(int64_t(varDefault)), false, "Render-thread CVar defaults must fit in a signed 32-bit integer.");

	Pending stDeferred;
	bool bHasDeferred = false;
	{
		MutexLock lockRegistry(mtxMutex);
		ERR_FAIL_COND_V_MSG(mapVariables.has(snKey) || mapCommands.has(snKey), false, vformat("Console name '%s' is already registered.", in_strName));
		Variable *pVariable = memnew(Variable);
		pVariable->strName = in_strName;
		pVariable->eType = eType;
		pVariable->varDefaultValue = varDefault;
		pVariable->varValue = varDefault;
		pVariable->strHelp = in_strHelp;
		pVariable->nFlags = in_nFlags;
		if (in_pIntRef || in_pFloatRef || in_pBoolRef)
		{
			pVariable->nFlags |= FLAG_RENDER_THREAD_SAFE;
		}
		pVariable->pIntRef = in_pIntRef;
		pVariable->pFloatRef = in_pFloatRef;
		pVariable->pBoolRef = in_pBoolRef;
		pVariable->pChangedFn = pChanged;
		pVariable->pChangedUd = pUserdata;
		WriteShadow(pVariable);
		mapVariables.insert(snKey, pVariable);
		if (Pending *pFound = mapPending.getptr(snKey))
		{
			if (pFound->bHasText)
			{
				stDeferred = *pFound;
				bHasDeferred = true;
			}
			mapPending.erase(snKey);
		}
	}

	if (bHasDeferred)
	{
		const AssignResult stAssigned = AssignText(in_strName, stDeferred.strText, stDeferred.eSetBy, false);
		if (!stAssigned.bAccepted && !stAssigned.strMessage.is_empty())
		{
			ERR_PRINT(stAssigned.strMessage);
		}
	}
	return true;
}

void CVars::Seed(const String &in_strName, const Variant &in_varValue, SetBy in_eSetBy)
{
	MutexLock lockRegistry(mtxMutex);
	Variable *pVariable = GetVariable(in_strName);
	if (!pVariable)
	{
		return;
	}
	Variant varCoerced;
	String strError;
	if (!Coerce(pVariable->eType, in_varValue, varCoerced, strError))
	{
		return;
	}
	if (pVariable->eType == Variant::INT && (pVariable->nFlags & FLAG_RENDER_THREAD_SAFE) && !FitsInt32(int64_t(varCoerced)))
	{
		return;
	}
	pVariable->varValue = varCoerced;
	pVariable->eSetBy = in_eSetBy;
	WriteShadow(pVariable);
}

void CVars::RegisterBuiltins()
{
#ifdef DEBUG_ENABLED
	const bool bAutoConsole = true;
#else
	const bool bAutoConsole = false;
#endif
	RegisterFloatRef("t.TimeScale", &atomBuiltinTimeScale, 1.0, "Scales engine time. 1 is realtime. Applied immediately.", FLAG_NONE, ApplyTimeScale, nullptr);
	RegisterIntRef("t.MaxFPS", &atomBuiltinMaxFps, 0, "Maximum rendered frames per second. 0 is unlimited. Applied immediately.", FLAG_NONE, ApplyMaxFps, nullptr);
	RegisterVariable("con.AutoConsole", bAutoConsole, "Show the in-game console (F1 or `) on runs that have a window and are not the editor.");
	RegisterVariable("con.ConfigPollMs", 500, "How often to re-read the --cvar-file, in milliseconds. 0 polls every frame.");
}

void CVars::EnsureDebuggerCapture()
{
	if (!EngineDebugger::has_capture(SNAME("cvar")))
	{
		EngineDebugger::register_message_capture(SNAME("cvar"), EngineDebugger::Capture(nullptr, DebuggerCapture));
	}
}

Error CVars::DebuggerCapture(void *pUser, const String &strMsg, const Array &in_arrArgs, bool &out_bCaptured)
{
	(void)pUser;
	if (strMsg != "exec")
	{
		return OK;
	}
	out_bCaptured = true;
	ERR_FAIL_NULL_V(pSingleton, ERR_UNCONFIGURED);
	ERR_FAIL_COND_V(in_arrArgs.is_empty(), ERR_INVALID_PARAMETER);
	const String strOutput = pSingleton->Execute(String(in_arrArgs[0]));
	if (!strOutput.is_empty())
	{
		print_line(strOutput);
	}
	return OK;
}

void CVars::_bind_methods()
{
	ClassDB::bind_method(D_METHOD("register_variable", "name", "default_value", "help", "flags"), &CVars::RegisterVariable, DEFVAL(""), DEFVAL(0));
	ClassDB::bind_method(D_METHOD("register_command", "name", "callback", "help"), &CVars::RegisterCommand, DEFVAL(""));
	ClassDB::bind_method(D_METHOD("unregister", "name"), &CVars::Unregister);
	ClassDB::bind_method(D_METHOD("has_variable", "name"), &CVars::HasVariable);
	ClassDB::bind_method(D_METHOD("has_command", "name"), &CVars::HasCommand);
	ClassDB::bind_method(D_METHOD("get_value", "name"), &CVars::GetValue);
	ClassDB::bind_method(D_METHOD("get_set_by", "name"), &CVars::GetSetBy);
	ClassDB::bind_method(D_METHOD("set_value", "name", "value"), &CVars::SetValue);
	ClassDB::bind_method(D_METHOD("set_value_with_priority", "name", "value", "set_by"), &CVars::SetValueWithPriority);
	ClassDB::bind_method(D_METHOD("set_changed_callback", "name", "callback"), &CVars::SetChangedCallback);
	ClassDB::bind_method(D_METHOD("reset", "name"), &CVars::Reset);
	ClassDB::bind_method(D_METHOD("execute", "command"), &CVars::Execute);
	ClassDB::bind_method(D_METHOD("help", "filter"), &CVars::Help, DEFVAL(""));
	ClassDB::bind_method(D_METHOD("set_config_file", "path"), &CVars::SetConfigFile);
	ClassDB::bind_method(D_METHOD("get_config_file"), &CVars::GetConfigFile);
	ClassDB::bind_method(D_METHOD("reload_config_file"), &CVars::ReloadConfigFile);

	BIND_BITFIELD_FLAG(FLAG_NONE);
	BIND_BITFIELD_FLAG(FLAG_CHEAT);
	BIND_BITFIELD_FLAG(FLAG_READ_ONLY);
	BIND_BITFIELD_FLAG(FLAG_RENDER_THREAD_SAFE);

	BIND_ENUM_CONSTANT(SET_BY_CONSTRUCTOR);
	BIND_ENUM_CONSTANT(SET_BY_PROJECT_SETTING);
	BIND_ENUM_CONSTANT(SET_BY_CONFIG_FILE);
	BIND_ENUM_CONSTANT(SET_BY_COMMAND_LINE);
	BIND_ENUM_CONSTANT(SET_BY_CODE);
	BIND_ENUM_CONSTANT(SET_BY_CONSOLE);
}

CVars::CVars()
{
	ERR_FAIL_COND(pSingleton != nullptr);
	pSingleton = this;
#ifdef DEBUG_ENABLED
	bCheatCommandsAllowed = true;
#else
	bCheatCommandsAllowed = false;
#endif
	RegisterBuiltins();
	EnsureDebuggerCapture();
}

CVars::~CVars()
{
	if (EngineDebugger::has_capture(SNAME("cvar")))
	{
		EngineDebugger::unregister_message_capture(SNAME("cvar"));
	}
	for (KeyValue<StringName, Variable *> &stEntry : mapVariables)
	{
		memdelete(stEntry.value);
		stEntry.value = nullptr;
	}
	mapVariables.clear();
	if (pSingleton == this)
	{
		pSingleton = nullptr;
	}
}

bool CVars::RegisterVariable(const String &in_strName, const Variant &varDefault, const String &in_strHelp, BitField<Flag> in_nFlags)
{
	return Register(in_strName, varDefault, in_strHelp, (uint32_t)in_nFlags, nullptr, nullptr, nullptr, nullptr, nullptr);
}

bool CVars::RegisterIntRef(const String &in_strName, std::atomic<int32_t> *pRef, int32_t nDefault, const String &in_strHelp, uint32_t in_nFlags, ChangedCallback pChanged, void *pUserdata)
{
	ERR_FAIL_NULL_V(pRef, false);
	return Register(in_strName, nDefault, in_strHelp, in_nFlags, pRef, nullptr, nullptr, pChanged, pUserdata);
}

bool CVars::RegisterFloatRef(const String &in_strName, std::atomic<double> *pRef, double dDefault, const String &in_strHelp, uint32_t in_nFlags, ChangedCallback pChanged, void *pUserdata)
{
	ERR_FAIL_NULL_V(pRef, false);
	return Register(in_strName, dDefault, in_strHelp, in_nFlags, nullptr, pRef, nullptr, pChanged, pUserdata);
}

bool CVars::RegisterBoolRef(const String &in_strName, std::atomic<int32_t> *pRef, bool bDefault, const String &in_strHelp, uint32_t in_nFlags, ChangedCallback pChanged, void *pUserdata)
{
	ERR_FAIL_NULL_V(pRef, false);
	return Register(in_strName, bDefault, in_strHelp, in_nFlags, nullptr, nullptr, pRef, pChanged, pUserdata);
}

bool CVars::RegisterCommand(const String &in_strName, const Callable &in_cbCallback, const String &in_strHelp)
{
	String strNameError;
	ERR_FAIL_COND_V_MSG(!IsValidName(in_strName, strNameError), false, strNameError);
	ERR_FAIL_COND_V_MSG(!in_cbCallback.is_valid(), false, "CVars command callback is invalid.");
	const StringName snKey = KeyOf(in_strName);
	ERR_FAIL_COND_V_MSG(IsBuiltinName(String(snKey)), false, vformat("'%s' is a built-in console command.", in_strName));
	Pending stDeferred;
	bool bHasDeferred = false;
	{
		MutexLock lockRegistry(mtxMutex);
		ERR_FAIL_COND_V_MSG(mapVariables.has(snKey) || mapCommands.has(snKey), false, vformat("Console name '%s' is already registered.", in_strName));
		Command stCommand;
		stCommand.strName = in_strName;
		stCommand.strHelp = in_strHelp;
		stCommand.cbCallback = in_cbCallback;
		mapCommands.insert(snKey, stCommand);
		if (Pending *pFound = mapPending.getptr(snKey))
		{
			if (pFound->bHasLine)
			{
				stDeferred = *pFound;
				bHasDeferred = true;
			}
			mapPending.erase(snKey);
		}
	}

	if (bHasDeferred)
	{
		// Replay outside the lock: the callback is free to call back into CVars.
		const String strOutput = ExecuteWithPriority(stDeferred.strLine, stDeferred.eSetBy, false);
		if (!strOutput.is_empty())
		{
			print_line(strOutput);
		}
	}
	return true;
}

void CVars::Unregister(const String &in_strName)
{
	const StringName snKey = KeyOf(in_strName);
	MutexLock lockRegistry(mtxMutex);
	if (Variable **pSlot = mapVariables.getptr(snKey))
	{
		memdelete(*pSlot);
		mapVariables.erase(snKey);
	}
	mapCommands.erase(snKey);
	mapPending.erase(snKey);
}

bool CVars::HasVariable(const String &in_strName) const
{
	MutexLock lockRegistry(mtxMutex);
	return GetVariable(in_strName) != nullptr;
}

bool CVars::HasCommand(const String &in_strName) const
{
	MutexLock lockRegistry(mtxMutex);
	return mapCommands.has(KeyOf(in_strName));
}

Variant CVars::GetValue(const String &in_strName) const
{
	MutexLock lockRegistry(mtxMutex);
	const Variable *pVariable = GetVariable(in_strName);
	if (!pVariable)
	{
		return Variant();
	}
	return pVariable->varValue;
}

CVars::SetBy CVars::GetSetBy(const String &in_strName) const
{
	MutexLock lockRegistry(mtxMutex);
	const Variable *pVariable = GetVariable(in_strName);
	if (!pVariable)
	{
		return SET_BY_CONSTRUCTOR;
	}
	return pVariable->eSetBy;
}

int32_t CVars::GetIntRenderThread(const String &in_strName) const
{
	MutexLock lockRegistry(mtxMutex);
	const Variable *pVariable = GetVariable(in_strName);
	ERR_FAIL_NULL_V(pVariable, 0);
	ERR_FAIL_COND_V_MSG(!(pVariable->nFlags & FLAG_RENDER_THREAD_SAFE), 0, vformat("%s is not render-thread safe.", pVariable->strName));
	ERR_FAIL_COND_V_MSG(pVariable->eType != Variant::INT, 0, vformat("%s is not an int.", pVariable->strName));
	return (int32_t)pVariable->atomShadowInt.load(std::memory_order_acquire);
}

double CVars::GetFloatRenderThread(const String &in_strName) const
{
	MutexLock lockRegistry(mtxMutex);
	const Variable *pVariable = GetVariable(in_strName);
	ERR_FAIL_NULL_V(pVariable, 0.0);
	ERR_FAIL_COND_V_MSG(!(pVariable->nFlags & FLAG_RENDER_THREAD_SAFE), 0.0, vformat("%s is not render-thread safe.", pVariable->strName));
	ERR_FAIL_COND_V_MSG(pVariable->eType != Variant::FLOAT, 0.0, vformat("%s is not a float.", pVariable->strName));
	return pVariable->atomShadowFloat.load(std::memory_order_acquire);
}

bool CVars::GetBoolRenderThread(const String &in_strName) const
{
	MutexLock lockRegistry(mtxMutex);
	const Variable *pVariable = GetVariable(in_strName);
	ERR_FAIL_NULL_V(pVariable, false);
	ERR_FAIL_COND_V_MSG(!(pVariable->nFlags & FLAG_RENDER_THREAD_SAFE), false, vformat("%s is not render-thread safe.", pVariable->strName));
	ERR_FAIL_COND_V_MSG(pVariable->eType != Variant::BOOL, false, vformat("%s is not a bool.", pVariable->strName));
	return pVariable->atomShadowInt.load(std::memory_order_acquire) != 0;
}

bool CVars::SetValue(const String &in_strName, const Variant &in_varValue)
{
	return SetValueWithPriority(in_strName, in_varValue, SET_BY_CODE);
}

bool CVars::SetValueWithPriority(const String &in_strName, const Variant &in_varValue, SetBy in_eSetBy)
{
	const AssignResult stResult = Assign(in_strName, in_varValue, in_eSetBy, false);
	if (!stResult.bAccepted && !stResult.strMessage.is_empty())
	{
		ERR_PRINT(stResult.strMessage);
	}
	return stResult.bAccepted;
}

bool CVars::SetChangedCallback(const String &in_strName, const Callable &in_cbCallback)
{
	MutexLock lockRegistry(mtxMutex);
	Variable *pVariable = GetVariable(in_strName);
	ERR_FAIL_NULL_V(pVariable, false);
	pVariable->cbChanged = in_cbCallback;
	return true;
}

bool CVars::Reset(const String &in_strName)
{
	Callable cbScriptCb;
	ChangedCallback pChangedFn = nullptr;
	void *pChangedUd = nullptr;
	String strCallbackName;
	Variant varCallbackValue;
	bool bFire = false;
	{
		MutexLock lockRegistry(mtxMutex);
		Variable *pVariable = GetVariable(in_strName);
		if (!pVariable)
		{
			return false;
		}
		String strError;
		if (!Allows(pVariable, SET_BY_CONSOLE, strError))
		{
			return false;
		}
		const bool bChanged = !SameValue(pVariable->eType, pVariable->varValue, pVariable->varDefaultValue);
		pVariable->varValue = pVariable->varDefaultValue;
		pVariable->eSetBy = SET_BY_CONSTRUCTOR;
		WriteShadow(pVariable);
		if (bChanged)
		{
			bFire = true;
			cbScriptCb = pVariable->cbChanged;
			pChangedFn = pVariable->pChangedFn;
			pChangedUd = pVariable->pChangedUd;
			strCallbackName = pVariable->strName;
			varCallbackValue = pVariable->varValue;
		}
	}
	if (bFire)
	{
		FireChanged(cbScriptCb, pChangedFn, pChangedUd, strCallbackName, varCallbackValue);
	}
	return true;
}

String CVars::Execute(const String &strCommand)
{
	return ExecuteWithPriority(strCommand, SET_BY_CONSOLE, false);
}

String CVars::Help(const String &in_strFilter) const
{
	const String strFilter = in_strFilter.strip_edges().to_lower();
	Vector<String> arrLines;
	{
		MutexLock lockRegistry(mtxMutex);
		for (const KeyValue<StringName, Variable *> &stEntry : mapVariables)
		{
			if (!strFilter.is_empty() && !stEntry.value->strName.to_lower().contains(strFilter))
			{
				continue;
			}
			arrLines.push_back(Describe(stEntry.value));
		}
		for (const KeyValue<StringName, Command> &stEntry : mapCommands)
		{
			if (!strFilter.is_empty() && !stEntry.value.strName.to_lower().contains(strFilter))
			{
				continue;
			}
			arrLines.push_back(stEntry.value.strName + " (command) " + stEntry.value.strHelp);
		}
	}
	arrLines.sort();
	String strOut = "Commands: help [filter], dump [filter], reset <name>. Assignment: name value | name=value. Separate commands with ';'.\n";
	for (const String &strLine : arrLines)
	{
		strOut += strLine;
		strOut += "\n";
	}
	return strOut;
}

void CVars::PushStartupLine(const String &in_strLine)
{
	const String strLine = in_strLine.strip_edges();
	if (strLine.is_empty())
	{
		return;
	}
	MutexLock lockRegistry(mtxMutex);
	arrStartupLines.push_back(strLine);
}

String CVars::ApplyStartup()
{
	EnsureDebuggerCapture();
	String strOutput = ReloadConfigFile();
	Vector<String> arrLines;
	{
		MutexLock lockRegistry(mtxMutex);
		arrLines = arrStartupLines;
		arrStartupLines.clear();
	}
	for (const String &strLine : arrLines)
	{
		const String strOne = ExecuteWithPriority(strLine, SET_BY_COMMAND_LINE, true);
		if (strOne.is_empty())
		{
			continue;
		}
		if (!strOutput.is_empty())
		{
			strOutput += "\n";
		}
		strOutput += strOne;
	}
	int nWaiting = 0;
	{
		MutexLock lockRegistry(mtxMutex);
		nWaiting = mapPending.size();
	}
	if (nWaiting > 0)
	{
		print_verbose(vformat("CVars: %d assignment(s) are waiting for the variable to be registered.", nWaiting));
	}
	return strOutput;
}

bool CVars::RecognizesArg(const String &strArg)
{
	return strArg == "--cvar" || strArg.begins_with("--cvar=") || strArg == "--cvar-exec" || strArg.begins_with("--cvar-exec=") || strArg == "--cvar-file" || strArg.begins_with("--cvar-file=");
}

CVars::ArgResult CVars::ParseEngineArg(const String &strArg, const String &strNext, bool bHasNext)
{
	ArgResult stResult;
	stResult.bRecognized = RecognizesArg(strArg);
	if (!stResult.bRecognized)
	{
		return stResult;
	}

	String strPayload;
	bool bTakesNext = false;
	bool bIsFile = false;
	if (strArg == "--cvar" || strArg == "--cvar-exec" || strArg == "--cvar-file")
	{
		bTakesNext = true;
		bIsFile = strArg == "--cvar-file";
		if (!bHasNext || strNext.is_empty())
		{
			stResult.bError = true;
			stResult.strMessage = vformat("Missing value for %s.", strArg);
			return stResult;
		}
		strPayload = strNext;
		stResult.bConsumedNext = true;
	}
	else if (strArg.begins_with("--cvar-file="))
	{
		bIsFile = true;
		strPayload = strArg.substr(String("--cvar-file=").length());
	}
	else if (strArg.begins_with("--cvar-exec="))
	{
		strPayload = strArg.substr(String("--cvar-exec=").length());
	}
	else if (strArg.begins_with("--cvar="))
	{
		strPayload = strArg.substr(String("--cvar=").length());
	}
	if (strPayload.is_empty())
	{
		stResult.bError = true;
		stResult.strMessage = vformat("Missing value for %s.", strArg);
		return stResult;
	}
	if (bIsFile)
	{
		SetConfigFile(strPayload);
	}
	else
	{
		PushStartupLine(strPayload);
	}
	(void)bTakesNext;
	return stResult;
}

void CVars::SetConfigFile(const String &in_strPath)
{
	MutexLock lockRegistry(mtxMutex);
	if (strConfigPath == in_strPath)
	{
		return;
	}
	strConfigPath = in_strPath;
	strConfigText = String();
}

String CVars::GetConfigFile() const
{
	MutexLock lockRegistry(mtxMutex);
	return strConfigPath;
}

String CVars::ReloadConfigFile()
{
	String strPath;
	{
		MutexLock lockRegistry(mtxMutex);
		strPath = strConfigPath;
	}
	if (strPath.is_empty() || !FileAccess::exists(strPath))
	{
		return String();
	}
	Error eErr = OK;
	const String strText = FileAccess::get_file_as_string(strPath, &eErr);
	if (eErr != OK)
	{
		return String();
	}
	{
		MutexLock lockRegistry(mtxMutex);
		if (strText == strConfigText)
		{
			return String();
		}
		strConfigText = strText;
	}
	const Vector<String> arrLines = strText.split("\n", true);
	String strOutput;
	for (const String &strLine : arrLines)
	{
		const String strOne = ExecuteWithPriority(strLine, SET_BY_CONFIG_FILE, true);
		if (strOne.is_empty())
		{
			continue;
		}
		if (!strOutput.is_empty())
		{
			strOutput += "\n";
		}
		strOutput += strOne;
	}
	return strOutput;
}

String CVars::PollConfigFile()
{
	if (!OS::get_singleton())
	{
		return String();
	}
	int nInterval = 500;
	const Variant varSetting = GetValue("con.ConfigPollMs");
	if (varSetting.get_type() == Variant::INT)
	{
		nInterval = varSetting;
	}
	const uint64_t nNow = OS::get_singleton()->get_ticks_msec();
	if (nInterval > 0 && nLastPollMsec != 0 && nNow - nLastPollMsec < (uint64_t)nInterval)
	{
		return String();
	}
	nLastPollMsec = nNow;
	return ReloadConfigFile();
}

void CVars::SyncEngineBuiltins(bool bTimeScaleCmdline, bool bMaxFpsCmdline)
{
	Engine *pEngine = Engine::get_singleton();
	if (!pEngine)
	{
		return;
	}
	Seed("t.TimeScale", pEngine->get_time_scale(), bTimeScaleCmdline ? SET_BY_COMMAND_LINE : SET_BY_CONSTRUCTOR);
	Seed("t.MaxFPS", pEngine->get_max_fps(), bMaxFpsCmdline ? SET_BY_COMMAND_LINE : SET_BY_PROJECT_SETTING);
}

Error CVars::HandleDebuggerMessage(const String &strMsg, const Array &in_arrArgs, bool &out_bCaptured)
{
	return DebuggerCapture(nullptr, strMsg, in_arrArgs, out_bCaptured);
}

void CVars::SetCheatCommandsAllowed(bool bAllowed)
{
	MutexLock lockRegistry(mtxMutex);
	bCheatCommandsAllowed = bAllowed;
}

bool CVars::AreCheatCommandsAllowed() const
{
	MutexLock lockRegistry(mtxMutex);
	return bCheatCommandsAllowed;
}
