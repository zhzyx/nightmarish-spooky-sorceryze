/**************************************************************************/
/*  TestFrameTelemetry.cpp                                                */
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

#include "engine_next/Tests/TestFramework.h"
#include "engine_next/Rendering/FrameTelemetry.h"

#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <limits>
#include <iterator>
#include <initializer_list>
#include <string>
#include <system_error>
#include <thread>

namespace
{
using EngineNext::Rendering::CompiledGraph;
using EngineNext::Rendering::FrameTelemetry;
using EngineNext::Rendering::FrameTiming;
namespace fs = std::filesystem;

struct TelemetryFixture
{
	fs::path stRoot;
	TelemetryFixture()
	{
		static std::atomic<std::uint64_t> nSequence{ 0 };
		stRoot = fs::temp_directory_path() / ("engine-next-telemetry-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + "-" + std::to_string(nSequence.fetch_add(1)));
		std::error_code stError;
		ENGINE_NEXT_CHECK(fs::create_directory(stRoot, stError));
	}
	~TelemetryFixture()
	{
		std::error_code stError;
		fs::remove_all(stRoot, stError);
	}
};

EngineNext::Serialization::JsonValue Header()
{
	return EngineNext::Serialization::JsonValue::Object{ { "qpc_frequency", "1000" } };
}

std::string Read(const fs::path &stPath)
{
	std::ifstream stInput(stPath, std::ios::binary);
	return std::string(std::istreambuf_iterator<char>(stInput), std::istreambuf_iterator<char>());
}
} // namespace

ENGINE_NEXT_TEST("Frame telemetry preserves every frame beyond the ordinary report window")
{
	TelemetryFixture stFixture;
	const fs::path stPath = stFixture.stRoot / "full.jsonl";
	FrameTelemetry stWriter;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	if (!stWriter.Open(stPath.u8string(), Header(), arrDiagnostics))
	{
		ENGINE_NEXT_CHECK(false);
		return;
	}
	CompiledGraph stGraph;
	FrameTiming stFrame;
	stFrame.bGpuReady = true;
	stFrame.nGraphEpoch = 1;
	constexpr std::uint32_t FRAME_COUNT = 65540;
	for (std::uint32_t nFrame = 0; nFrame < FRAME_COUNT; ++nFrame)
	{
		stFrame.nFrame = nFrame;
		if (!stWriter.Append(stFrame, stGraph, arrDiagnostics))
		{
			ENGINE_NEXT_CHECK(false);
			return;
		}
	}
	ENGINE_NEXT_CHECK_EQ(stWriter.Records(), static_cast<std::uint64_t>(FRAME_COUNT));
	ENGINE_NEXT_CHECK(stWriter.Finish(true, FRAME_COUNT, arrDiagnostics));
	std::ifstream stInput(stPath);
	std::string strLine;
	std::uint32_t nFrames = 0;
	bool bFirst = false;
	bool bLast = false;
	while (std::getline(stInput, strLine))
	{
		if (strLine.find("\"record\":\"frame\"") != std::string::npos)
		{
			++nFrames;
			bFirst = bFirst || strLine.find("\"frame_id\":0,") != std::string::npos;
			bLast = bLast || strLine.find("\"frame_id\":65539,") != std::string::npos;
		}
	}
	ENGINE_NEXT_CHECK_EQ(nFrames, FRAME_COUNT);
	ENGINE_NEXT_CHECK(bFirst && bLast);
	ENGINE_NEXT_CHECK(fs::file_size(stPath) == stWriter.Bytes());
	ENGINE_NEXT_CHECK(!stWriter.IsOpen());
}

ENGINE_NEXT_TEST("Frame telemetry accepts retired slot order and marks incomplete sessions")
{
	TelemetryFixture stFixture;
	FrameTelemetry stWriter;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	const fs::path stPath = stFixture.stRoot / "order.jsonl";
	ENGINE_NEXT_CHECK(stWriter.Open(stPath.u8string(), Header(), arrDiagnostics));
	CompiledGraph stGraph;
	FrameTiming stFrame;
	stFrame.nGraphEpoch = 1;
	stFrame.stRecording.nThreads = 2;
	stFrame.stRecording.arrThreads[1] = { 57, 3, 21, 207, 225 };
	stFrame.stRecording.dBatchMsec = 0.5;
	stFrame.stTextures.nResidentBytes = 196608;
	stFrame.nTextureChangeSerial = 7;
	ENGINE_NEXT_CHECK(!stWriter.Append(stFrame, stGraph, arrDiagnostics));
	stFrame.bGpuReady = true;
	for (std::uint32_t nFrame : { 2U, 0U, 1U })
	{
		stFrame.nFrame = nFrame;
		ENGINE_NEXT_CHECK(stWriter.Append(stFrame, stGraph, arrDiagnostics));
	}
	ENGINE_NEXT_CHECK(stWriter.Finish(false, 4, arrDiagnostics));
	const std::string strText = Read(stPath);
	ENGINE_NEXT_CHECK(strText.find("\"thread_id\":57") != std::string::npos);
	ENGINE_NEXT_CHECK(strText.find("\"bundles\":3") != std::string::npos);
	ENGINE_NEXT_CHECK(strText.find("\"resident_bytes\":196608") != std::string::npos);
	ENGINE_NEXT_CHECK(strText.find("\"change_serial\":\"7\"") != std::string::npos);
	ENGINE_NEXT_CHECK(strText.find("\"complete\":false") != std::string::npos);
	ENGINE_NEXT_CHECK(strText.find("\"frames\":\"3\"") != std::string::npos);
	ENGINE_NEXT_CHECK(!stWriter.Append(stFrame, stGraph, arrDiagnostics));
}

ENGINE_NEXT_TEST("Frame telemetry refuses replacement and nonfinite records")
{
	TelemetryFixture stFixture;
	const fs::path stExisting = stFixture.stRoot / "existing.jsonl";
	std::ofstream(stExisting) << "preserved";
	EngineNext::Assets::Diagnostics arrDiagnostics;
	FrameTelemetry stWriter;
	ENGINE_NEXT_CHECK(!stWriter.Open(stExisting.u8string(), Header(), arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(Read(stExisting), std::string("preserved"));
	ENGINE_NEXT_CHECK(!stWriter.Open((stFixture.stRoot / "missing" / "trace.jsonl").u8string(), Header(), arrDiagnostics));
	// A fresh owner avoids retaining the failed stream's error state.
	FrameTelemetry stFresh;
	ENGINE_NEXT_CHECK(stFresh.Open((stFixture.stRoot / "finite.jsonl").u8string(), Header(), arrDiagnostics));
	FrameTiming stFrame;
	stFrame.bGpuReady = true;
	stFrame.nGraphEpoch = 1;
	stFrame.dCpuMsec = std::numeric_limits<double>::quiet_NaN();
	CompiledGraph stGraph;
	ENGINE_NEXT_CHECK(!stFresh.Append(stFrame, stGraph, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFresh.Records(), 0ULL);
	ENGINE_NEXT_CHECK(!stFresh.Finish(true, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Frame telemetry exclusively creates a shared path under competing writers")
{
	TelemetryFixture stFixture;
	for (std::uint32_t nRound = 0; nRound < 32; ++nRound)
	{
		const fs::path stPath = stFixture.stRoot / ("race-" + std::to_string(nRound) + ".jsonl");
		std::atomic<std::uint32_t> nReady{ 0 };
		std::atomic<bool> bGo{ false };
		std::array<bool, 2> arrOpened{};
		std::array<std::thread, 2> arrThreads;
		for (std::uint32_t nWriter = 0; nWriter < 2; ++nWriter)
		{
			arrThreads[nWriter] = std::thread([&stPath, &nReady, &bGo, &arrOpened, nWriter]()
											  {
				FrameTelemetry stWriter;
				EngineNext::Assets::Diagnostics arrDiagnostics;
				nReady.fetch_add(1);
				while (!bGo.load())
				{
					std::this_thread::yield();
				}
				arrOpened[nWriter] = stWriter.Open(stPath.u8string(), Header(), arrDiagnostics);
				if (arrOpened[nWriter])
				{
					(void)stWriter.Finish(true, 0, arrDiagnostics);
				} });
		}
		while (nReady.load() != 2)
		{
			std::this_thread::yield();
		}
		bGo.store(true);
		for (std::thread &stThread : arrThreads)
		{
			stThread.join();
		}
		ENGINE_NEXT_CHECK(arrOpened[0] != arrOpened[1]);
		ENGINE_NEXT_CHECK(Read(stPath).find("\"complete\":true") != std::string::npos);
	}
	FrameTelemetry stUnicode;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stUnicode.Open((stFixture.stRoot / fs::u8path(u8"褰曞埗.jsonl")).u8string(), Header(), arrDiagnostics));
	ENGINE_NEXT_CHECK(stUnicode.Finish(true, 0, arrDiagnostics));
}
