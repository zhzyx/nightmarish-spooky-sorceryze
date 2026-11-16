/**************************************************************************/
/*  ClientSession.h                                                       */
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

#include "engine_next/include/EngineNext/Gameplay/InterpolationBuffer.h"
#include "engine_next/include/EngineNext/Network/ITransport.h"
#include "engine_next/include/EngineNext/Runtime/RuntimeConfig.h"

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace EngineNext::Runtime
{

enum class ClientSessionMode : std::uint8_t
{
	Interactive = 0,
	Acceptance = 1,
};

struct ClientEntitySnapshot
{
	EntityId stEntityId;
	Gameplay::PredictionState stState;
	Gameplay::InterpolationStatus eInterpolation = Gameplay::InterpolationStatus::Empty;
	bool bLocal = false;
};

struct ClientSnapshot
{
	std::uint64_t nGeneration = 0;
	std::uint64_t nSessionId = 0;
	std::uint64_t nSampleTimeMsec = 0;
	bool bConnected = false;
	std::vector<ClientEntitySnapshot> arrEntities;
};

// All methods have one owner thread. Snapshot values own their data and can be
// copied to a renderer; the session never accepts state written by rendering.
class ClientSession final
{
public:
	ClientSession();
	~ClientSession();
	ClientSession(const ClientSession &) = delete;
	ClientSession &operator=(const ClientSession &) = delete;
	[[nodiscard]] RuntimeStatus Initialize(const RuntimeConfig &stConfig, ClientSessionMode eMode = ClientSessionMode::Interactive);
	// Takes ownership of the supplied transport, including Stop on error/Shutdown.
	[[nodiscard]] RuntimeStatus Initialize(const RuntimeConfig &stConfig, std::unique_ptr<Network::ITransport> pTransport, ClientSessionMode eMode = ClientSessionMode::Interactive);
	// Monotonic milliseconds. Nonblocking and at most eight input steps per call.
	[[nodiscard]] RuntimeStatus Tick(std::uint64_t nNowMsec, const Gameplay::Vector3 &vMovement);
	// A short input edge survives until the next real input step. At most one
	// pending direction is retained; held movement takes precedence at that step.
	[[nodiscard]] RuntimeStatus QueueMovementPulse(const Gameplay::Vector3 &vMovement);
	[[nodiscard]] ClientSnapshot GetSnapshot() const;
	[[nodiscard]] std::string GetPackageDigest() const;
	[[nodiscard]] bool IsConnected() const noexcept;
	[[nodiscard]] bool HasSucceeded() const noexcept;
	[[nodiscard]] RuntimeStatus RequestReconnect(std::uint64_t nDelayMsec = 0);
	void Shutdown() noexcept;

private:
	struct State;
	std::unique_ptr<State> pState;
};

} // namespace EngineNext::Runtime
