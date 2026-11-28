/**************************************************************************/
/*  StreamingVirtualTextureLoader.h                                      */
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

#pragma region Engine ZXB
// [ZXB] Asynchronous tile reader for Streaming Virtual Textures. Requests are drained by a
// WorkerThreadPool task; completed tiles are polled on the render thread and uploaded there.
#pragma endregion

#include "core/object/worker_thread_pool.h"
#include "core/os/mutex.h"
#include "core/templates/local_vector.h"
#include "core/variant/variant.h"
#include "servers/rendering/TerrainHeightPageSource.h"
#include "servers/rendering/StreamingVirtualTextureFile.h"

class StreamingVirtualTextureLoader
{
public:
	struct Request
	{
		uint32_t nId = 0; // Page key, opaque to the loader.
		TerrainHeightPageSource eGrid;
		uint32_t nLevel = 0;
		uint32_t nX = 0;
		uint32_t nY = 0;
	};

	struct Result
	{
		uint32_t nId = 0;
		bool bFromGrid = false;
		Vector<uint8_t> arrData;
	};

private:
	mutable Mutex mtxMutex;
	String strPath;
	StreamingVirtualTextureFile stIndexFile; // Parsed once, read only from workers.
	LocalVector<Request> arrPending;
	LocalVector<Result> arrDone;
	WorkerThreadPool::TaskID nTask = WorkerThreadPool::INVALID_TASK_ID;
	bool bFailing = false;

	void Run();
	static void RunStatic(void *pSelf)
	{
		static_cast<StreamingVirtualTextureLoader *>(pSelf)->Run();
	}

public:
	void Configure(const String &in_strPath);
	const String &GetPath() const
	{
		return strPath;
	}
	bool IsBusy() const;

	void RequestPage(uint32_t in_nId, uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, const TerrainHeightPageSource &in_eGrid = {});
	void Submit();
	// Moves finished tiles out. Returns false when nothing finished (or a task is still running).
	bool Poll(LocalVector<Result> &out_arrDone);
	void Flush();
	bool HasPending() const;

	~StreamingVirtualTextureLoader();
};
