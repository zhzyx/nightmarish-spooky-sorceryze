/**************************************************************************/
/*  gameplay_subsystem.cpp                                                */
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

#include "gameplay_subsystem.h"

#include "core/object/class_db.h"

template <typename T>
static T *_gameplay_subsystem_object(ObjectID p_id) {
	return Object::cast_to<T>(ObjectDB::get_instance(p_id));
}

void GameplaySubsystem::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_subsystem_id", "id"), &GameplaySubsystem::set_subsystem_id);
	ClassDB::bind_method(D_METHOD("get_subsystem_id"), &GameplaySubsystem::get_subsystem_id);
	ClassDB::bind_method(D_METHOD("set_scope", "scope"), &GameplaySubsystem::set_scope);
	ClassDB::bind_method(D_METHOD("get_scope"), &GameplaySubsystem::get_scope);
	ClassDB::bind_method(D_METHOD("is_initialized"), &GameplaySubsystem::is_initialized);
	ClassDB::bind_method(D_METHOD("get_registry"), &GameplaySubsystem::get_registry);

	GDVIRTUAL_BIND(_initialize);
	GDVIRTUAL_BIND(_deinitialize);

	ADD_PROPERTY(PropertyInfo(Variant::STRING_NAME, "subsystem_id"), "set_subsystem_id", "get_subsystem_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "scope", PROPERTY_HINT_ENUM, "Application,World,Local Player,Connection"), "set_scope", "get_scope");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "initialized", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_initialized");

	ADD_SIGNAL(MethodInfo("subsystem_initialized"));
	ADD_SIGNAL(MethodInfo("subsystem_deinitialized"));

	BIND_ENUM_CONSTANT(SCOPE_APPLICATION);
	BIND_ENUM_CONSTANT(SCOPE_WORLD);
	BIND_ENUM_CONSTANT(SCOPE_LOCAL_PLAYER);
	BIND_ENUM_CONSTANT(SCOPE_CONNECTION);
}

void GameplaySubsystem::_notification(int p_what) {
	if (p_what == NOTIFICATION_PREDELETE) {
		_deinitialize_internal();
	}
}

void GameplaySubsystem::set_subsystem_id(const StringName &p_id) {
	ERR_FAIL_COND_MSG(is_initialized(), "Cannot rename an initialized subsystem.");
	ERR_FAIL_COND_MSG(get_registry() != nullptr, "Remove the subsystem from its registry before renaming it.");
	subsystem_id = p_id;
}

StringName GameplaySubsystem::get_subsystem_id() const {
	return subsystem_id;
}

void GameplaySubsystem::set_scope(Scope p_scope) {
	ERR_FAIL_INDEX(int(p_scope), int(SCOPE_CONNECTION) + 1);
	ERR_FAIL_COND_MSG(is_initialized(), "Cannot change the scope of an initialized subsystem.");
	ERR_FAIL_COND_MSG(get_registry() != nullptr, "Remove the subsystem from its registry before changing its scope.");
	scope = p_scope;
}

GameplaySubsystem::Scope GameplaySubsystem::get_scope() const {
	return scope;
}

void GameplaySubsystem::_set_registry(GameplaySubsystemRegistry *p_registry) {
	registry_id = p_registry ? p_registry->get_instance_id() : ObjectID();
}

GameplaySubsystemRegistry *GameplaySubsystem::get_registry() const {
	return _gameplay_subsystem_object<GameplaySubsystemRegistry>(registry_id);
}

void GameplaySubsystem::_initialize_internal() {
	if (initialized) {
		return;
	}
	initialized = true;
	on_initialize();
	if (!initialized) {
		return;
	}
	GDVIRTUAL_CALL(_initialize);
	if (initialized) {
		emit_signal(SNAME("subsystem_initialized"));
	}
}

void GameplaySubsystem::_deinitialize_internal() {
	if (!initialized) {
		return;
	}
	initialized = false;
	GDVIRTUAL_CALL(_deinitialize);
	on_deinitialize();
	emit_signal(SNAME("subsystem_deinitialized"));
}

bool GameplaySubsystem::is_initialized() const {
	return initialized;
}

GameplaySubsystem::~GameplaySubsystem() {
	GameplaySubsystemRegistry *registry = get_registry();
	if (registry) {
		registry->_subsystem_destroyed(this);
	}
	_deinitialize_internal();
}

void GameplaySubsystemRegistry::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_scope", "scope"), &GameplaySubsystemRegistry::set_scope);
	ClassDB::bind_method(D_METHOD("get_scope"), &GameplaySubsystemRegistry::get_scope);
	ClassDB::bind_method(D_METHOD("add_subsystem", "subsystem"), &GameplaySubsystemRegistry::add_subsystem);
	ClassDB::bind_method(D_METHOD("remove_subsystem", "subsystem"), &GameplaySubsystemRegistry::remove_subsystem);
	ClassDB::bind_method(D_METHOD("get_subsystem", "id"), &GameplaySubsystemRegistry::get_subsystem);
	ClassDB::bind_method(D_METHOD("get_subsystems"), &GameplaySubsystemRegistry::get_subsystems);
	ClassDB::bind_method(D_METHOD("initialize_subsystems"), &GameplaySubsystemRegistry::initialize_subsystems);
	ClassDB::bind_method(D_METHOD("deinitialize_subsystems"), &GameplaySubsystemRegistry::deinitialize_subsystems);
	ClassDB::bind_method(D_METHOD("is_initialized"), &GameplaySubsystemRegistry::is_initialized);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "scope", PROPERTY_HINT_ENUM, "Application,World,Local Player,Connection"), "set_scope", "get_scope");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "initialized", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_initialized");

	ADD_SIGNAL(MethodInfo("subsystem_added", PropertyInfo(Variant::OBJECT, "subsystem", PROPERTY_HINT_RESOURCE_TYPE, "GameplaySubsystem")));
	ADD_SIGNAL(MethodInfo("subsystem_removed", PropertyInfo(Variant::OBJECT, "subsystem", PROPERTY_HINT_RESOURCE_TYPE, "GameplaySubsystem")));
}

void GameplaySubsystemRegistry::_notification(int p_what) {
	if (p_what == NOTIFICATION_PREDELETE) {
		deinitialize_subsystems();
	}
}

void GameplaySubsystemRegistry::set_scope(GameplaySubsystem::Scope p_scope) {
	ERR_FAIL_INDEX(int(p_scope), int(GameplaySubsystem::SCOPE_CONNECTION) + 1);
	ERR_FAIL_COND_MSG(initialized || !subsystem_ids.is_empty(), "A populated subsystem registry cannot change scope.");
	scope = p_scope;
}

GameplaySubsystem::Scope GameplaySubsystemRegistry::get_scope() const {
	return scope;
}

Error GameplaySubsystemRegistry::add_subsystem(GameplaySubsystem *p_subsystem) {
	ERR_FAIL_NULL_V(p_subsystem, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V_MSG(p_subsystem->get_subsystem_id().is_empty(), ERR_INVALID_PARAMETER, "A subsystem requires a non-empty ID.");
	ERR_FAIL_COND_V_MSG(p_subsystem->get_scope() != scope, ERR_INVALID_PARAMETER, "The subsystem scope does not match the registry scope.");
	ERR_FAIL_COND_V_MSG(get_subsystem(p_subsystem->get_subsystem_id()) != nullptr, ERR_ALREADY_EXISTS, "The subsystem ID is already registered.");
	ERR_FAIL_COND_V_MSG(p_subsystem->get_registry() != nullptr, ERR_ALREADY_IN_USE, "The subsystem already belongs to a registry.");
	ERR_FAIL_COND_V_MSG(p_subsystem->get_parent() != nullptr && p_subsystem->get_parent() != this, ERR_ALREADY_IN_USE, "The subsystem already has another parent.");

	if (!p_subsystem->get_parent()) {
		add_child(p_subsystem);
	}
	subsystem_ids.push_back(p_subsystem->get_instance_id());
	p_subsystem->_set_registry(this);
	if (initialized && !lifecycle_transition) {
		_initialize_registered_subsystems();
	}
	emit_signal(SNAME("subsystem_added"), p_subsystem);
	return OK;
}

bool GameplaySubsystemRegistry::remove_subsystem(GameplaySubsystem *p_subsystem) {
	if (!p_subsystem) {
		return false;
	}
	const int index = subsystem_ids.find(p_subsystem->get_instance_id());
	if (index < 0) {
		return false;
	}
	subsystem_ids.remove_at(index);
	const bool previous_transition = lifecycle_transition;
	lifecycle_transition = true;
	p_subsystem->_deinitialize_internal();
	lifecycle_transition = previous_transition;
	p_subsystem->_set_registry(nullptr);
	if (p_subsystem->get_parent() == this) {
		remove_child(p_subsystem);
	}
	emit_signal(SNAME("subsystem_removed"), p_subsystem);
	if (initialized && !lifecycle_transition) {
		_initialize_registered_subsystems();
	}
	return true;
}

GameplaySubsystem *GameplaySubsystemRegistry::get_subsystem(const StringName &p_id) const {
	for (const ObjectID &id : subsystem_ids) {
		GameplaySubsystem *subsystem = _gameplay_subsystem_object<GameplaySubsystem>(id);
		if (subsystem && subsystem->get_subsystem_id() == p_id) {
			return subsystem;
		}
	}
	return nullptr;
}

TypedArray<GameplaySubsystem> GameplaySubsystemRegistry::get_subsystems() const {
	TypedArray<GameplaySubsystem> subsystems;
	for (const ObjectID &id : subsystem_ids) {
		GameplaySubsystem *subsystem = _gameplay_subsystem_object<GameplaySubsystem>(id);
		if (subsystem) {
			subsystems.push_back(subsystem);
		}
	}
	return subsystems;
}

void GameplaySubsystemRegistry::_initialize_registered_subsystems() {
	lifecycle_transition = true;
	bool initialized_any = true;
	while (initialized_any) {
		initialized_any = false;
		const Vector<ObjectID> initializing_ids = subsystem_ids;
		for (const ObjectID &id : initializing_ids) {
			GameplaySubsystem *subsystem = _gameplay_subsystem_object<GameplaySubsystem>(id);
			if (subsystem && subsystem->get_registry() == this && !subsystem->is_initialized()) {
				subsystem->_initialize_internal();
				initialized_any = true;
				// A callback may reorder registrations, so select the next service from a fresh snapshot.
				break;
			}
		}
	}
	lifecycle_transition = false;
}

Error GameplaySubsystemRegistry::initialize_subsystems() {
	ERR_FAIL_COND_V_MSG(lifecycle_transition, ERR_BUSY, "Cannot start a nested subsystem lifecycle transition.");
	if (initialized) {
		return OK;
	}
	initialized = true;
	_initialize_registered_subsystems();
	return OK;
}

void GameplaySubsystemRegistry::deinitialize_subsystems() {
	ERR_FAIL_COND_MSG(lifecycle_transition, "Cannot start a nested subsystem lifecycle transition.");
	if (!initialized) {
		return;
	}
	initialized = false;
	lifecycle_transition = true;
	const Vector<ObjectID> deinitializing_ids = subsystem_ids;
	for (int i = deinitializing_ids.size() - 1; i >= 0; i--) {
		GameplaySubsystem *subsystem = _gameplay_subsystem_object<GameplaySubsystem>(deinitializing_ids[i]);
		if (subsystem && subsystem->get_registry() == this) {
			subsystem->_deinitialize_internal();
		}
	}
	lifecycle_transition = false;
}

bool GameplaySubsystemRegistry::is_initialized() const {
	return initialized;
}

void GameplaySubsystemRegistry::_subsystem_destroyed(GameplaySubsystem *p_subsystem) {
	if (!p_subsystem) {
		return;
	}
	const int index = subsystem_ids.find(p_subsystem->get_instance_id());
	if (index >= 0) {
		subsystem_ids.remove_at(index);
		emit_signal(SNAME("subsystem_removed"), p_subsystem);
	}
}

GameplaySubsystemRegistry::~GameplaySubsystemRegistry() {
	deinitialize_subsystems();
	for (const ObjectID &id : subsystem_ids) {
		GameplaySubsystem *subsystem = _gameplay_subsystem_object<GameplaySubsystem>(id);
		if (subsystem && subsystem->get_registry() == this) {
			subsystem->_set_registry(nullptr);
		}
	}
	subsystem_ids.clear();
}
