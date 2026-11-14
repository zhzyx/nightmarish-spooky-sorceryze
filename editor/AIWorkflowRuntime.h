/**************************************************************************/
/*  ai_workflow_runtime.h                                                 */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).   */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                     */
/* SPDX-License-Identifier: MIT                                           */
/**************************************************************************/
#pragma once

#include "ai_core/WorkflowRuntime.h"
#include "core/object/object.h"
#include "core/variant/dictionary.h"
#include "core/templates/vector.h"

// Editor-owned service. Godot Dictionary conversion and signals are main-thread
// only. Workers marshal their completion to their owning main-thread Controller.
class AIWorkflowRuntime : public Object
{
	GDCLASS(AIWorkflowRuntime, Object);

public:
	AIWorkflowRuntime();
	~AIWorkflowRuntime();
	static AIWorkflowRuntime *get_singleton();
	Dictionary begin_run(const Dictionary &mapRequest);
	Dictionary publish(const Dictionary &mapEvent);
	Dictionary cancel(const String &strRunId, int64_t nGeneration, const String &strEventId = "cancel");
	Dictionary snapshot(const String &strRunId) const;

protected:
	static void _bind_methods();

private:
	static AIWorkflowRuntime *pSingleton;
	AICore::WorkflowRuntime stRuntime;
	Vector<Dictionary> arrPendingEvents;
	bool bEmittingEvents = false;
	Dictionary EmitResult(const AICore::Result &stResult);
	static Dictionary ConvertResult(const AICore::Result &stResult);
	static Dictionary ErrorResult(const String &strCode, const String &strReason);
	static bool ValidateJSON(const Variant &varValue, int nDepth = 0);
	static bool ReadMetadata(const Dictionary &mapValue, bool bModel, AICore::Metadata &out_mapValue);
};
