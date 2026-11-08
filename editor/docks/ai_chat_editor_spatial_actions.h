#pragma once

#include "core/string/ustring.h"
#include "core/variant/dictionary.h"

// Permission and confirmation are owned by the host. This helper only exposes
// bounded native camera/data operations, never input events or arbitrary calls.
class AIChatEditorSpatialActions {
public:
	static bool supports(const String &p_action);
	static Dictionary perform(const Dictionary &p_args, bool p_confirmed);
};
