/* THIS FILE IS GENERATED DO NOT EDIT */
#pragma once

// IWYU pragma: begin_keep
#include "core/object/script_instance.h"
#include "core/variant/method_ptrcall.h"
#include "core/variant/variant_caster.h"
#include "core/variant/variant_internal.h"
// IWYU pragma: end_keep

inline constexpr uintptr_t _INVALID_GDVIRTUAL_FUNC_ADDR = static_cast<uintptr_t>(-1);

template <typename... Args>
_NO_INLINE_ void _gdvirtual_set_method_info_args(MethodInfo &p_method_info) {
	p_method_info.arguments = { GetTypeInfo<Args>::get_class_info()... };
	p_method_info.arguments_metadata = { GetTypeInfo<Args>::METADATA... };
}

_NO_INLINE_ inline void _gdvirtual_print_required_error(const Object *p_object, const StringName &p_method_name, bool &r_error_shown) {
	// Like ERR_PRINT_ONCE but outlined, to save on binary space.
	if (!r_error_shown) {
		r_error_shown = true;
		ERR_PRINT(vformat("Required virtual method %s::%s must be overridden before calling.", p_object->get_class_name(), p_method_name));
	}
}

/* 0 Arguments */

#define GDVIRTUAL0(m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call() {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			_script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
						if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		return method_info;\
	}

#define GDVIRTUAL0R(m_ret, m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
					PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		return method_info;\
	}

#define GDVIRTUAL0C(m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			_script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
						if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		return method_info;\
	}

#define GDVIRTUAL0RC(m_ret, m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
					PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		return method_info;\
	}

#define GDVIRTUAL0_REQUIRED(m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call() {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			_script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
						if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		return method_info;\
	}

#define GDVIRTUAL0R_REQUIRED(m_ret, m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
					PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		return method_info;\
	}

#define GDVIRTUAL0C_REQUIRED(m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			_script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
						if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		return method_info;\
	}

#define GDVIRTUAL0RC_REQUIRED(m_ret, m_name)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, nullptr, 0, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
					PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, nullptr, &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), nullptr, &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		return method_info;\
	}

#define GDVIRTUAL0_COMPAT(m_alias, m_name)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call() {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
						if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, nullptr, nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), nullptr, nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		return method_info;\
	}

#define GDVIRTUAL0R_COMPAT(m_alias, m_ret, m_name)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
					PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, nullptr, &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), nullptr, &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		return method_info;\
	}

#define GDVIRTUAL0C_COMPAT(m_alias, m_name)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
						if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, nullptr, nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), nullptr, nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		return method_info;\
	}

#define GDVIRTUAL0RC_COMPAT(m_alias, m_ret, m_name)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
					PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, nullptr, &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), nullptr, &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		return method_info;\
	}

/* 1 Arguments */

#define GDVIRTUAL1(m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1R(m_ret, m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1C(m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1RC(m_ret, m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1_REQUIRED(m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1R_REQUIRED(m_ret, m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1C_REQUIRED(m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1RC_REQUIRED(m_ret, m_name, m_type1)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[1] = { VariantInternal::make(arg1) };\
			const Variant *vargptrs[1] = { &vargs[0] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 1, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1_COMPAT(m_alias, m_name, m_type1)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1R_COMPAT(m_alias, m_ret, m_name, m_type1)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1C_COMPAT(m_alias, m_name, m_type1)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL1RC_COMPAT(m_alias, m_ret, m_name, m_type1)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			GDExtensionConstTypePtr argptrs[1] = { &argval1 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1>(method_info);\
		return method_info;\
	}

/* 2 Arguments */

#define GDVIRTUAL2(m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2R(m_ret, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2C(m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2RC(m_ret, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2_REQUIRED(m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2R_REQUIRED(m_ret, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2C_REQUIRED(m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2RC_REQUIRED(m_ret, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[2] = { VariantInternal::make(arg1), VariantInternal::make(arg2) };\
			const Variant *vargptrs[2] = { &vargs[0], &vargs[1] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 2, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2_COMPAT(m_alias, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2C_COMPAT(m_alias, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL2RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			GDExtensionConstTypePtr argptrs[2] = { &argval1, &argval2 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2>(method_info);\
		return method_info;\
	}

/* 3 Arguments */

#define GDVIRTUAL3(m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3R(m_ret, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3C(m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3RC(m_ret, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3_REQUIRED(m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3C_REQUIRED(m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[3] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3) };\
			const Variant *vargptrs[3] = { &vargs[0], &vargs[1], &vargs[2] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 3, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL3RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			GDExtensionConstTypePtr argptrs[3] = { &argval1, &argval2, &argval3 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3>(method_info);\
		return method_info;\
	}

/* 4 Arguments */

#define GDVIRTUAL4(m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4C(m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[4] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4) };\
			const Variant *vargptrs[4] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 4, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL4RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			GDExtensionConstTypePtr argptrs[4] = { &argval1, &argval2, &argval3, &argval4 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4>(method_info);\
		return method_info;\
	}

/* 5 Arguments */

#define GDVIRTUAL5(m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[5] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5) };\
			const Variant *vargptrs[5] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 5, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL5RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			GDExtensionConstTypePtr argptrs[5] = { &argval1, &argval2, &argval3, &argval4, &argval5 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5>(method_info);\
		return method_info;\
	}

/* 6 Arguments */

#define GDVIRTUAL6(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[6] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6) };\
			const Variant *vargptrs[6] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 6, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL6RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			GDExtensionConstTypePtr argptrs[6] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6>(method_info);\
		return method_info;\
	}

/* 7 Arguments */

#define GDVIRTUAL7(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[7] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7) };\
			const Variant *vargptrs[7] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 7, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL7RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			GDExtensionConstTypePtr argptrs[7] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7>(method_info);\
		return method_info;\
	}

/* 8 Arguments */

#define GDVIRTUAL8(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[8] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8) };\
			const Variant *vargptrs[8] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 8, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL8RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			GDExtensionConstTypePtr argptrs[8] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8>(method_info);\
		return method_info;\
	}

/* 9 Arguments */

#define GDVIRTUAL9(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[9] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9) };\
			const Variant *vargptrs[9] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 9, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL9RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			GDExtensionConstTypePtr argptrs[9] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9>(method_info);\
		return method_info;\
	}

/* 10 Arguments */

#define GDVIRTUAL10(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[10] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10) };\
			const Variant *vargptrs[10] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 10, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL10RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			GDExtensionConstTypePtr argptrs[10] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10>(method_info);\
		return method_info;\
	}

/* 11 Arguments */

#define GDVIRTUAL11(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[11] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11) };\
			const Variant *vargptrs[11] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 11, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL11RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			GDExtensionConstTypePtr argptrs[11] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11>(method_info);\
		return method_info;\
	}

/* 12 Arguments */

#define GDVIRTUAL12(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12R(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12C(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12RC(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12R_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12C_REQUIRED(m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			_script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12RC_REQUIRED(m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_name = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance) {\
			Callable::CallError ce;\
			Variant vargs[12] = { VariantInternal::make(arg1), VariantInternal::make(arg2), VariantInternal::make(arg3), VariantInternal::make(arg4), VariantInternal::make(arg5), VariantInternal::make(arg6), VariantInternal::make(arg7), VariantInternal::make(arg8), VariantInternal::make(arg9), VariantInternal::make(arg10), VariantInternal::make(arg11), VariantInternal::make(arg12) };\
			const Variant *vargptrs[12] = { &vargs[0], &vargs[1], &vargs[2], &vargs[3], &vargs[4], &vargs[5], &vargs[6], &vargs[7], &vargs[8], &vargs[9], &vargs[10], &vargs[11] };\
			Variant ret = _script_instance->callp(_gdvirtual_##m_name##_sn, (const Variant **)vargptrs, 12, ce);\
			if (ce.error == Callable::CallError::CALL_OK) {\
				r_ret = VariantCaster<m_ret>::cast(ret);\
				return true;\
			}\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_name##_sn, _gdvirtual_##m_name, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_name)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		static bool _gdvirtual_required_error_shown = false;\
		_gdvirtual_print_required_error(this, _gdvirtual_##m_name##_sn, _gdvirtual_required_error_shown);\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_name##_overridden() const {\
		static const StringName _gdvirtual_##m_name##_sn = StringName(#m_name, true);\
		ScriptInstance *_script_instance = ((Object *)(this))->get_script_instance();\
		if (_script_instance && _script_instance->has_method(_gdvirtual_##m_name##_sn)) {\
			return true;\
		}\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_name)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_name##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_name, _gdvirtual_##m_name##_sn, false);\
			}\
			if (_gdvirtual_##m_name != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_name##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST | METHOD_FLAG_VIRTUAL_REQUIRED;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12R_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12, m_ret &r_ret) {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12C_COMPAT(m_alias, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
					if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), nullptr);\
					}\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

#define GDVIRTUAL12RC_COMPAT(m_alias, m_ret, m_name, m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12)\
	mutable void *_gdvirtual_##m_alias = nullptr;\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_call(m_type1 arg1, m_type2 arg2, m_type3 arg3, m_type4 arg4, m_type5 arg5, m_type6 arg6, m_type7 arg7, m_type8 arg8, m_type9 arg9, m_type10 arg10, m_type11 arg11, m_type12 arg12, m_ret &r_ret) const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				PtrToArg<m_type1>::EncodeT argval1; PtrToArg<m_type1>::encode(arg1, &argval1);\
			PtrToArg<m_type2>::EncodeT argval2; PtrToArg<m_type2>::encode(arg2, &argval2);\
			PtrToArg<m_type3>::EncodeT argval3; PtrToArg<m_type3>::encode(arg3, &argval3);\
			PtrToArg<m_type4>::EncodeT argval4; PtrToArg<m_type4>::encode(arg4, &argval4);\
			PtrToArg<m_type5>::EncodeT argval5; PtrToArg<m_type5>::encode(arg5, &argval5);\
			PtrToArg<m_type6>::EncodeT argval6; PtrToArg<m_type6>::encode(arg6, &argval6);\
			PtrToArg<m_type7>::EncodeT argval7; PtrToArg<m_type7>::encode(arg7, &argval7);\
			PtrToArg<m_type8>::EncodeT argval8; PtrToArg<m_type8>::encode(arg8, &argval8);\
			PtrToArg<m_type9>::EncodeT argval9; PtrToArg<m_type9>::encode(arg9, &argval9);\
			PtrToArg<m_type10>::EncodeT argval10; PtrToArg<m_type10>::encode(arg10, &argval10);\
			PtrToArg<m_type11>::EncodeT argval11; PtrToArg<m_type11>::encode(arg11, &argval11);\
			PtrToArg<m_type12>::EncodeT argval12; PtrToArg<m_type12>::encode(arg12, &argval12);\
			GDExtensionConstTypePtr argptrs[12] = { &argval1, &argval2, &argval3, &argval4, &argval5, &argval6, &argval7, &argval8, &argval9, &argval10, &argval11, &argval12 };\
				PtrToArg<m_ret>::EncodeT ret;\
				if (_get_extension()->call_virtual_with_data) {\
					_get_extension()->call_virtual_with_data(_get_extension_instance(), &_gdvirtual_##m_alias##_sn, _gdvirtual_##m_alias, reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				} else {\
					((GDExtensionClassCallVirtual)_gdvirtual_##m_alias)(_get_extension_instance(), reinterpret_cast<GDExtensionConstTypePtr *>(argptrs), &ret);\
					r_ret = (m_ret)ret;\
				}\
				return true;\
			}\
		}\
		(void)r_ret;\
		return false;\
	}\
	_FORCE_INLINE_ bool _gdvirtual_##m_alias##_overridden() const {\
		static const StringName _gdvirtual_##m_alias##_sn = StringName(#m_name, true);\
		\
		if (_get_extension()) {\
			if (unlikely(!_gdvirtual_##m_alias)) {\
			    _gdvirtual_init_method_ptr(_gdvirtual_##m_alias##_get_method_info().get_compatibility_hash(), _gdvirtual_##m_alias, _gdvirtual_##m_alias##_sn, true);\
			}\
			if (_gdvirtual_##m_alias != reinterpret_cast<void*>(_INVALID_GDVIRTUAL_FUNC_ADDR)) {\
				return true;\
			}\
		}\
		return false;\
	}\
	_FORCE_INLINE_ static MethodInfo _gdvirtual_##m_alias##_get_method_info() {\
		MethodInfo method_info;\
		method_info.name = #m_name;\
		method_info.flags = METHOD_FLAG_VIRTUAL | METHOD_FLAG_CONST;\
		method_info.return_val = GetTypeInfo<m_ret>::get_class_info();\
		method_info.return_val_metadata = GetTypeInfo<m_ret>::METADATA;\
		_gdvirtual_set_method_info_args<m_type1, m_type2, m_type3, m_type4, m_type5, m_type6, m_type7, m_type8, m_type9, m_type10, m_type11, m_type12>(method_info);\
		return method_info;\
	}

