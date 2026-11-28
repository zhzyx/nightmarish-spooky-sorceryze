/**************************************************************************/
/*  CVars.h                                                              */
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

#include "core/object/object.h"
#include "core/os/mutex.h"
#include "core/templates/hash_map.h"
#include "core/templates/vector.h"
#include "core/variant/type_info.h"

#include <atomic>

// Runtime console variables. Priority matches Unreal's console (low to high):
// constructor, project setting, config file, command line, code, console.
// A lower priority write cannot replace a higher one.

class CVars : public Object
{
	GDCLASS(CVars, Object);

public:
	enum Flag
	{
		FLAG_NONE = 0,
		FLAG_CHEAT = 1 << 0,
		FLAG_READ_ONLY = 1 << 1,
		FLAG_RENDER_THREAD_SAFE = 1 << 2,
	};

	enum SetBy
	{
		SET_BY_CONSTRUCTOR = 0,
		SET_BY_PROJECT_SETTING = 1,
		SET_BY_CONFIG_FILE = 2,
		SET_BY_COMMAND_LINE = 3,
		SET_BY_CODE = 4,
		SET_BY_CONSOLE = 5,
	};

	struct ArgResult
	{
		bool bRecognized = false;
		bool bError = false;
		bool bConsumedNext = false;
		String strMessage;
	};

	typedef void (*ChangedCallback)(void *pUserdata);

private:
	struct Variable
	{
		String strName;
		Variant::Type eType = Variant::NIL;
		Variant varValue;
		Variant varDefaultValue;
		String strHelp;
		uint32_t nFlags = FLAG_NONE;
		SetBy eSetBy = SET_BY_CONSTRUCTOR;
		std::atomic<int32_t> *pIntRef = nullptr;
		std::atomic<double> *pFloatRef = nullptr;
		std::atomic<int32_t> *pBoolRef = nullptr;
		std::atomic<int64_t> atomShadowInt{ 0 };
		std::atomic<double> atomShadowFloat{ 0.0 };
		Callable cbChanged;
		ChangedCallback pChangedFn = nullptr;
		void *pChangedUd = nullptr;
	};

	struct Command
	{
		String strName;
		String strHelp;
		Callable cbCallback;
	};

	struct Pending
	{
		String strText;
		String strLine;
		SetBy eSetBy = SET_BY_CONSTRUCTOR;
		bool bHasText = false;
		bool bHasLine = false;
	};

	struct AssignResult
	{
		bool bAccepted = false;
		bool bChanged = false;
		String strMessage;
	};

	static inline CVars *pSingleton = nullptr;

	mutable Mutex mtxMutex;
	HashMap<StringName, Variable *> mapVariables;
	HashMap<StringName, Command> mapCommands;
	HashMap<StringName, Pending> mapPending;
	Vector<String> arrStartupLines;
	String strConfigPath;
	String strConfigText;
	uint64_t nLastPollMsec = 0;
	bool bCheatCommandsAllowed = false;

	static StringName KeyOf(const String &in_strName);
	static bool IsValidName(const String &in_strName, String &out_strError);
	static bool IsBuiltinName(const String &in_strKey);
	static bool ParseBoolWord(const String &in_strText, bool &out_bValue);
	static bool ParseText(Variant::Type in_eType, const String &in_strText, Variant &out_varOut, String &out_strError);
	static bool Coerce(Variant::Type in_eType, const Variant &varIn, Variant &out_varOut, String &out_strError);
	static bool SameValue(Variant::Type in_eType, const Variant &varA, const Variant &varB);
	static String FormatValue(const Variant &in_varValue);
	static const char *TypeName(Variant::Type in_eType);
	static const char *SetByName(SetBy in_eSetBy);
	static String Unquote(const String &in_strText);
	static Vector<String> SplitCommands(const String &in_strLine);
	static Vector<String> Tokenize(const String &in_strText);

	Variable *GetVariable(const String &in_strName);
	const Variable *GetVariable(const String &in_strName) const;
	void DeferPendingLocked(const String &in_strName, const String &in_strText, SetBy in_eSetBy);
	void DeferPendingLineLocked(const String &in_strName, const String &in_strLine, SetBy in_eSetBy);
	bool IsUserSource(SetBy in_eSetBy) const;
	bool Allows(const Variable *in_pVariable, SetBy in_eSetBy, String &out_strError) const;
	void WriteShadow(Variable *in_pVariable);
	String Describe(const Variable *in_pVariable) const;
	void FireChanged(const Callable &in_cbCallback, ChangedCallback pFn, void *pUd, const String &in_strName, const Variant &in_varValue);
	AssignResult Assign(const String &in_strName, const Variant &in_varValue, SetBy in_eSetBy, bool bDeferUnknown);
	AssignResult AssignText(const String &in_strName, const String &in_strText, SetBy in_eSetBy, bool bDeferUnknown);
	String ExecuteOne(const String &in_strLine, SetBy in_eSetBy, bool bDeferUnknown);
	String ExecuteWithPriority(const String &strCommand, SetBy in_eSetBy, bool bDeferUnknown);
	bool Register(const String &in_strName, const Variant &varDefault, const String &in_strHelp, uint32_t in_nFlags, std::atomic<int32_t> *in_pIntRef, std::atomic<double> *in_pFloatRef, std::atomic<int32_t> *in_pBoolRef, ChangedCallback pChanged, void *pUserdata);
	void Seed(const String &in_strName, const Variant &in_varValue, SetBy in_eSetBy);
	void RegisterBuiltins();
	void EnsureDebuggerCapture();
	static Error DebuggerCapture(void *pUser, const String &strMsg, const Array &in_arrArgs, bool &out_bCaptured);

protected:
	static void _bind_methods();

public:
	static CVars *GetSingleton()
	{
		return pSingleton;
	}
	static bool RecognizesArg(const String &strArg);

	CVars();
	~CVars();

	bool RegisterVariable(const String &in_strName, const Variant &varDefault, const String &in_strHelp = String(), BitField<Flag> in_nFlags = FLAG_NONE);
	bool RegisterIntRef(const String &in_strName, std::atomic<int32_t> *pRef, int32_t nDefault, const String &in_strHelp, uint32_t in_nFlags = FLAG_NONE, ChangedCallback pChanged = nullptr, void *pUserdata = nullptr);
	bool RegisterFloatRef(const String &in_strName, std::atomic<double> *pRef, double dDefault, const String &in_strHelp, uint32_t in_nFlags = FLAG_NONE, ChangedCallback pChanged = nullptr, void *pUserdata = nullptr);
	bool RegisterBoolRef(const String &in_strName, std::atomic<int32_t> *pRef, bool bDefault, const String &in_strHelp, uint32_t in_nFlags = FLAG_NONE, ChangedCallback pChanged = nullptr, void *pUserdata = nullptr);
	bool RegisterCommand(const String &in_strName, const Callable &in_cbCallback, const String &in_strHelp = String());
	void Unregister(const String &in_strName);

	bool HasVariable(const String &in_strName) const;
	bool HasCommand(const String &in_strName) const;
	Variant GetValue(const String &in_strName) const;
	SetBy GetSetBy(const String &in_strName) const;
	int32_t GetIntRenderThread(const String &in_strName) const;
	double GetFloatRenderThread(const String &in_strName) const;
	bool GetBoolRenderThread(const String &in_strName) const;

	bool SetValue(const String &in_strName, const Variant &in_varValue);
	bool SetValueWithPriority(const String &in_strName, const Variant &in_varValue, SetBy in_eSetBy);
	bool SetChangedCallback(const String &in_strName, const Callable &in_cbCallback);
	bool Reset(const String &in_strName);

	String Execute(const String &strCommand);
	String Help(const String &in_strFilter = String()) const;

	void PushStartupLine(const String &in_strLine);
	String ApplyStartup();
	ArgResult ParseEngineArg(const String &strArg, const String &strNext, bool bHasNext);

	void SetConfigFile(const String &in_strPath);
	String GetConfigFile() const;
	String ReloadConfigFile();
	String PollConfigFile();

	void SyncEngineBuiltins(bool bTimeScaleCmdline, bool bMaxFpsCmdline);
	void SetCheatCommandsAllowed(bool bAllowed);
	bool AreCheatCommandsAllowed() const;
	Error HandleDebuggerMessage(const String &strMsg, const Array &in_arrArgs, bool &out_bCaptured);
};

VARIANT_BITFIELD_CAST(CVars::Flag);
VARIANT_ENUM_CAST(CVars::SetBy);
