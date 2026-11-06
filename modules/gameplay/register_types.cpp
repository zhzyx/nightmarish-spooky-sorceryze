/**************************************************************************/
/*  register_types.cpp                                                    */
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
/* "Software"), to deal in the Software without restriction, including  */
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

#include "register_types.h"

#include "gameplay_entity.h"
#include "gameplay_match.h"
#include "gameplay_prediction.h"
#include "gameplay_relevancy.h"
#include "gameplay_replication.h"
#include "gameplay_server.h"
#include "gameplay_session.h"
#include "gameplay_subsystem.h"

#include "core/object/class_db.h"

void initialize_gameplay_module(ModuleInitializationLevel p_level) {
	if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
		return;
	}

	GDREGISTER_CLASS(GameplayComponent);
	GDREGISTER_CLASS(GameplayPawn);
	GDREGISTER_CLASS(GameplayPlayerState);
	GDREGISTER_CLASS(GameplayController);
	GDREGISTER_CLASS(GameplayGameState);
	GDREGISTER_CLASS(GameplayGameMode);
	GDREGISTER_CLASS(GameplaySubsystem);
	GDREGISTER_CLASS(GameplaySubsystemRegistry);
	GDREGISTER_CLASS(GameplayWorld);
	GDREGISTER_CLASS(GameplayConnection);
	GDREGISTER_CLASS(GameplayUserSession);
	GDREGISTER_CLASS(GameplaySessionManager);
	GDREGISTER_CLASS(GameplayServerConfig);
	GDREGISTER_CLASS(GameplayDedicatedServer);
	GDREGISTER_CLASS(GameplaySessionClient);
	GDREGISTER_CLASS(GameplayConnectionView);
	GDREGISTER_CLASS(GameplayRelevancyObject);
	GDREGISTER_CLASS(GameplayReplicationGraph);
	GDREGISTER_CLASS(GameplayPredictionInput);
	GDREGISTER_CLASS(GameplayPredictionState);
	GDREGISTER_CLASS(GameplayPredictionModel);
	GDREGISTER_CLASS(GameplayClientPrediction);
	GDREGISTER_CLASS(GameplayServerPrediction);
	GDREGISTER_CLASS(GameplayInterpolationBuffer);
	GDREGISTER_CLASS(GameplayNetworkSimulator);
	GDREGISTER_CLASS(GameplayNetworkPrediction);
	GDREGISTER_CLASS(GameplayReplicationProperty);
	GDREGISTER_CLASS(GameplayRPCConfig);
	GDREGISTER_CLASS(GameplayReplicationState);
	GDREGISTER_CLASS(GameplayReplicationFragmenter);
	GDREGISTER_CLASS(GameplayMultiplayerReplication);
}

void uninitialize_gameplay_module(ModuleInitializationLevel p_level) {
}
