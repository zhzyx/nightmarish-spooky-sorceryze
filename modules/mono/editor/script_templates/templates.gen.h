/**************************************************************************/
/*  templates.gen.h                                                       */
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

/* THIS FILE IS GENERATED. EDITS WILL BE LOST. */

#pragma once

#include "core/object/script_language.h"
#include "core/string/ustring.h"

inline constexpr int TEMPLATES_ARRAY_SIZE = 9;
static const struct ScriptLanguage::ScriptTemplate TEMPLATES[TEMPLATES_ARRAY_SIZE] = {
	{ String("CharacterBody2D"), String("Basic Movement"), String("Classic movement for gravity games (platformer, ...)"), String("using _BINDINGS_NAMESPACE_;\nusing System;\n\npublic partial class _CLASS_ : _BASE_\n{\n_TS_public const float Speed = 300.0f;\n_TS_public const float JumpVelocity = -400.0f;\n\n_TS_public override void _PhysicsProcess(double delta)\n_TS_{\n_TS__TS_Vector2 velocity = Velocity;\n\n_TS__TS_// Add the gravity.\n_TS__TS_if (!IsOnFloor())\n_TS__TS_{\n_TS__TS__TS_velocity += GetGravity() * (float)delta;\n_TS__TS_}\n\n_TS__TS_// Handle Jump.\n_TS__TS_if (Input.IsActionJustPressed(\"ui_accept\") && IsOnFloor())\n_TS__TS_{\n_TS__TS__TS_velocity.Y = JumpVelocity;\n_TS__TS_}\n\n_TS__TS_// Get the input direction and handle the movement/deceleration.\n_TS__TS_// As good practice, you should replace UI actions with custom gameplay actions.\n_TS__TS_Vector2 direction = Input.GetVector(\"ui_left\", \"ui_right\", \"ui_up\", \"ui_down\");\n_TS__TS_if (direction != Vector2.Zero)\n_TS__TS_{\n_TS__TS__TS_velocity.X = direction.X * Speed;\n_TS__TS_}\n_TS__TS_else\n_TS__TS_{\n_TS__TS__TS_velocity.X = Mathf.MoveToward(Velocity.X, 0, Speed);\n_TS__TS_}\n\n_TS__TS_Velocity = velocity;\n_TS__TS_MoveAndSlide();\n_TS_}\n}\n") },
	{ String("CharacterBody3D"), String("Basic Movement"), String("Classic movement for gravity games (FPS, TPS, ...)"), String("using _BINDINGS_NAMESPACE_;\nusing System;\n\npublic partial class _CLASS_ : _BASE_\n{\n_TS_public const float Speed = 5.0f;\n_TS_public const float JumpVelocity = 4.5f;\n\n_TS_public override void _PhysicsProcess(double delta)\n_TS_{\n_TS__TS_Vector3 velocity = Velocity;\n\n_TS__TS_// Add the gravity.\n_TS__TS_if (!IsOnFloor())\n_TS__TS_{\n_TS__TS__TS_velocity += GetGravity() * (float)delta;\n_TS__TS_}\n\n_TS__TS_// Handle Jump.\n_TS__TS_if (Input.IsActionJustPressed(\"ui_accept\") && IsOnFloor())\n_TS__TS_{\n_TS__TS__TS_velocity.Y = JumpVelocity;\n_TS__TS_}\n\n_TS__TS_// Get the input direction and handle the movement/deceleration.\n_TS__TS_// As good practice, you should replace UI actions with custom gameplay actions.\n_TS__TS_Vector2 inputDir = Input.GetVector(\"ui_left\", \"ui_right\", \"ui_up\", \"ui_down\");\n_TS__TS_Vector3 direction = (Transform.Basis * new Vector3(inputDir.X, 0, inputDir.Y)).Normalized();\n_TS__TS_if (direction != Vector3.Zero)\n_TS__TS_{\n_TS__TS__TS_velocity.X = direction.X * Speed;\n_TS__TS__TS_velocity.Z = direction.Z * Speed;\n_TS__TS_}\n_TS__TS_else\n_TS__TS_{\n_TS__TS__TS_velocity.X = Mathf.MoveToward(Velocity.X, 0, Speed);\n_TS__TS__TS_velocity.Z = Mathf.MoveToward(Velocity.Z, 0, Speed);\n_TS__TS_}\n\n_TS__TS_Velocity = velocity;\n_TS__TS_MoveAndSlide();\n_TS_}\n}\n") },
	{ String("EditorPlugin"), String("Plugin"), String("Basic plugin template"), String("#if TOOLS\nusing _BINDINGS_NAMESPACE_;\nusing System;\n\n[Tool]\npublic partial class _CLASS_ : _BASE_\n{\n_TS_public override void _EnterTree()\n_TS_{\n_TS__TS_// Initialization of the plugin goes here.\n_TS_}\n\n_TS_public override void _ExitTree()\n_TS_{\n_TS__TS_// Clean-up of the plugin goes here.\n_TS_}\n}\n#endif\n") },
	{ String("EditorScenePostImport"), String("Basic Import Script"), String("Basic import script template"), String("#if TOOLS\nusing _BINDINGS_NAMESPACE_;\nusing System;\n\n[Tool]\npublic partial class _CLASS_ : _BASE_\n{\n_TS_public override GodotObject _PostImport(Node scene)\n_TS_{\n_TS__TS_// Modify the contents of the scene upon import.\n_TS__TS_return scene; // Return the modified root node when you're done.\n_TS_}\n}\n#endif\n") },
	{ String("EditorScenePostImport"), String("No Comments"), String("Basic import script template (no comments)"), String("#if TOOLS\nusing _BINDINGS_NAMESPACE_;\nusing System;\n\n[Tool]\npublic partial class _CLASS_ : _BASE_\n{\n_TS_public override GodotObject _PostImport(Node scene)\n_TS_{\n_TS__TS_return scene;\n_TS_}\n}\n#endif\n") },
	{ String("EditorScript"), String("Basic Editor Script"), String("Basic editor script template"), String("#if TOOLS\nusing _BINDINGS_NAMESPACE_;\nusing System;\n\n[Tool]\npublic partial class _CLASS_ : _BASE_\n{\n_TS_// Called when the script is executed (using File -> Run in Script Editor).\n_TS_public override void _Run()\n_TS_{\n_TS_}\n}\n#endif\n") },
	{ String("Node"), String("Default"), String("Base template for Node with default Godot cycle methods"), String("using _BINDINGS_NAMESPACE_;\nusing System;\n\npublic partial class _CLASS_ : _BASE_\n{\n_TS_// Called when the node enters the scene tree for the first time.\n_TS_public override void _Ready()\n_TS_{\n_TS_}\n\n_TS_// Called every frame. 'delta' is the elapsed time since the previous frame.\n_TS_public override void _Process(double delta)\n_TS_{\n_TS_}\n}\n") },
	{ String("Object"), String("Empty"), String("Empty template suitable for all Objects"), String("using _BINDINGS_NAMESPACE_;\nusing System;\n\npublic partial class _CLASS_ : _BASE_\n{\n}\n") },
	{ String("VisualShaderNodeCustom"), String("Basic"), String("Visual shader's node plugin template"), String("using _BINDINGS_NAMESPACE_;\nusing System;\n\n[Tool]\n[GlobalClass]\npublic partial class VisualShaderNode_CLASS_ : _BASE_\n{\n_TS_public override string _GetName()\n_TS_{\n_TS__TS_return \"_CLASS_\";\n_TS_}\n\n_TS_public override string _GetCategory()\n_TS_{\n_TS__TS_return \"\";\n_TS_}\n\n_TS_public override string _GetDescription()\n_TS_{\n_TS__TS_return \"\";\n_TS_}\n\n_TS_public override VisualShaderNode.PortType _GetReturnIconType()\n_TS_{\n_TS__TS_return 0;\n_TS_}\n\n_TS_public override int _GetInputPortCount()\n_TS_{\n_TS__TS_return 0;\n_TS_}\n\n_TS_public override string _GetInputPortName(int port)\n_TS_{\n_TS__TS_return \"\";\n_TS_}\n\n_TS_public override VisualShaderNode.PortType _GetInputPortType(int port)\n_TS_{\n_TS__TS_return 0;\n_TS_}\n\n_TS_public override int _GetOutputPortCount()\n_TS_{\n_TS__TS_return 1;\n_TS_}\n\n_TS_public override string _GetOutputPortName(int port)\n_TS_{\n_TS__TS_return \"result\";\n_TS_}\n\n_TS_public override VisualShaderNode.PortType _GetOutputPortType(int port)\n_TS_{\n_TS__TS_return 0;\n_TS_}\n\n_TS_public override string _GetCode(Godot.Collections.Array<string> inputVars, Godot.Collections.Array<string> outputVars, Shader.Mode mode, VisualShader.Type type)\n_TS_{\n_TS__TS_return \"\";\n_TS_}\n}\n") },
};
