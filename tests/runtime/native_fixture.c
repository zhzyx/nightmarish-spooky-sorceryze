/**************************************************************************/
/*  native_fixture.c                                                      */
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

/* Plain C ABI fixture, also compiled as C++; no godot-cpp dependency. */
#include "gdextension_interface.gen.h"

#include <stdint.h>
#include <string.h>
#ifndef FIXTURE_VALUE
#define FIXTURE_VALUE 42
#endif
/* Opaque StringName storage is pointer sized, with pointer alignment. */
static void *class_name;
static GDExtensionClassLibraryPtr library;
static GDExtensionInterfaceGetProcAddress get_proc;
static GDExtensionVariantFromTypeConstructorFunc from_int;
static void answer(void *userdata, GDExtensionClassInstancePtr instance,
		const GDExtensionConstVariantPtr *args, GDExtensionInt count,
		GDExtensionVariantPtr result, GDExtensionCallError *error) {
	int64_t value = FIXTURE_VALUE;
	(void)userdata;
	(void)instance;
	(void)args;
	(void)count;
	from_int(result, &value);
	error->error = GDEXTENSION_CALL_OK;
}
static void answer_ptr(void *userdata, GDExtensionClassInstancePtr instance,
		const GDExtensionConstTypePtr *args, GDExtensionTypePtr result) {
	(void)userdata;
	(void)instance;
	(void)args;
	*(int64_t *)result = FIXTURE_VALUE;
}
static void free_instance(void *userdata, GDExtensionClassInstancePtr instance) {
	(void)userdata;
	(void)instance;
}
static void initialize(void *userdata, GDExtensionInitializationLevel level) {
	void *parent_name = 0;
	void *method_name = 0;
	void *empty_name = 0;
	void *empty_string = 0;
	GDExtensionClassCreationInfo6 info;
	GDExtensionClassMethodInfo method;
	GDExtensionPropertyInfo return_info;
	GDExtensionInterfaceStringNameNewWithUtf8Chars make_name =
			(GDExtensionInterfaceStringNameNewWithUtf8Chars)get_proc("string_name_new_with_utf8_chars");
	GDExtensionPtrDestructor destroy_name =
			((GDExtensionInterfaceVariantGetPtrDestructor)get_proc("variant_get_ptr_destructor"))(GDEXTENSION_VARIANT_TYPE_STRING_NAME);
	(void)userdata;
	if (level != GDEXTENSION_INITIALIZATION_SCENE) {
		return;
	}
	make_name(&class_name, "RuntimeNativeFixture");
	make_name(&parent_name, "Object");
	make_name(&method_name, "answer");
	make_name(&empty_name, "");
	((GDExtensionInterfaceStringNewWithUtf8Chars)get_proc("string_new_with_utf8_chars"))(&empty_string, "");
	memset(&info, 0, sizeof(info));
	info.is_abstract = 1;
	info.is_exposed = 1;
	info.is_runtime = 1;
	info.free_instance_func = free_instance;
	((GDExtensionInterfaceClassdbRegisterExtensionClass6)get_proc("classdb_register_extension_class6"))(library, &class_name, &parent_name, &info);
	memset(&method, 0, sizeof(method));
	memset(&return_info, 0, sizeof(return_info));
	return_info.type = GDEXTENSION_VARIANT_TYPE_INT;
	return_info.name = &empty_name;
	return_info.class_name = &empty_name;
	return_info.hint_string = &empty_string;
	method.name = &method_name;
	method.call_func = answer;
	method.ptrcall_func = answer_ptr;
	method.method_flags = GDEXTENSION_METHOD_FLAG_NORMAL | GDEXTENSION_METHOD_FLAG_STATIC;
	method.has_return_value = 1;
	method.return_value_info = &return_info;
	((GDExtensionInterfaceClassdbRegisterExtensionClassMethod)get_proc("classdb_register_extension_class_method"))(library, &class_name, &method);
	((GDExtensionInterfaceVariantGetPtrDestructor)get_proc("variant_get_ptr_destructor"))(GDEXTENSION_VARIANT_TYPE_STRING)(&empty_string);
	destroy_name(&empty_name);
	destroy_name(&method_name);
	destroy_name(&parent_name);
}
static void deinitialize(void *userdata, GDExtensionInitializationLevel level) {
	(void)userdata;
	if (level != GDEXTENSION_INITIALIZATION_SCENE) {
		return;
	}
	((GDExtensionInterfaceClassdbUnregisterExtensionClass)get_proc("classdb_unregister_extension_class"))(library, &class_name);
	((GDExtensionInterfaceVariantGetPtrDestructor)get_proc("variant_get_ptr_destructor"))(GDEXTENSION_VARIANT_TYPE_STRING_NAME)(&class_name);
}
#ifdef __cplusplus
extern "C"
#endif
#if defined(_WIN32)
		__declspec(dllexport)
#else
__attribute__((visibility("default")))
#endif
		GDExtensionBool runtime_native_init(GDExtensionInterfaceGetProcAddress proc,
				GDExtensionClassLibraryPtr lib, GDExtensionInitialization *init) {
	get_proc = proc;
	library = lib;
	from_int = ((GDExtensionInterfaceGetVariantFromTypeConstructor)proc("get_variant_from_type_constructor"))(GDEXTENSION_VARIANT_TYPE_INT);
	init->minimum_initialization_level = GDEXTENSION_INITIALIZATION_SCENE;
	init->userdata = 0;
	init->initialize = initialize;
	init->deinitialize = deinitialize;
	return 1;
}
