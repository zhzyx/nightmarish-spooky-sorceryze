/**************************************************************************/
/*  test_gdscript_compile.cpp                                             */
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

TEST_FORCE_LINK(test_gdscript_compile)

#include "modules/modules_enabled.gen.h"
#ifdef MODULE_GDSCRIPT_ENABLED
#include "modules/gdscript/gdscript.h"
#include "modules/gdscript/gdscript_cache.h"

namespace GDScriptTests {
class RuntimeCompilationCacheAccessor {
public:
	static bool contains(const String &p_path) {
		auto *cache = GDScriptCache::singleton;
		if (cache->full_gdscript_cache.has(p_path) || cache->shallow_gdscript_cache.has(p_path) || cache->parser_map.has(p_path) || cache->dependencies.has(p_path) || cache->abandoned_parser_map.has(p_path)) {
			return true;
		}
		for (const KeyValue<String, HashSet<String>> &entry : cache->parser_inverse_dependencies) {
			if (entry.key == p_path || entry.value.has(p_path)) {
				return true;
			}
		}
		return false;
	}
};

TEST_CASE("[GDScript][RuntimeCompile] Virtual scripts release cache bookkeeping") {
	GDScriptLanguage::get_singleton()->init();
	for (int i = 0; i < 64; i++) {
		Dictionary result = GDScript::compile_source("extends RefCounted\nstatic var answer: int = 42\n");
		REQUIRE(int(result["error"]) == OK);
		Ref<GDScript> script = result["script"];
		REQUIRE(script.is_valid());
		if (script.is_null()) {
			return;
		}
		CHECK_FALSE(RuntimeCompilationCacheAccessor::contains(script->get_path()));
		ObjectID id = script->get_instance_id();
		script.unref();
		result.clear();
		CHECK(ObjectDB::get_instance(id) == nullptr);
	}
}
} // namespace GDScriptTests
#endif // MODULE_GDSCRIPT_ENABLED
