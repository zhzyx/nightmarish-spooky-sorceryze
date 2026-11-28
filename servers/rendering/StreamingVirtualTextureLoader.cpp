/**************************************************************************/
/*  StreamingVirtualTextureLoader.cpp                                    */
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

#include "StreamingVirtualTextureLoader.h"

#pragma region Engine ZXB
// [ZXB] Asynchronous Streaming Virtual Texture tile loader.
#pragma endregion

#include "StreamingVirtualTextureFile.h"

#include "core/io/file_access.h"

void StreamingVirtualTextureLoader::Configure(const String &in_strPath)
{
	Flush();
	MutexLock lockStream(mtxMutex);
	strPath = in_strPath;
	// Parse the header and index once; workers only read tile bytes afterwards.
	stIndexFile = StreamingVirtualTextureFile();
	if (!strPath.is_empty())
	{
		if (stIndexFile.Open(strPath) != OK)
		{
			stIndexFile = StreamingVirtualTextureFile();
		}
	}
	arrPending.clear();
	arrDone.clear();
}

bool StreamingVirtualTextureLoader::IsBusy() const
{
	MutexLock lockStream(mtxMutex);
	return nTask != WorkerThreadPool::INVALID_TASK_ID;
}

void StreamingVirtualTextureLoader::RequestPage(uint32_t in_nId, uint32_t in_nLevel, uint32_t in_nX, uint32_t in_nY, const TerrainHeightPageSource &in_eGrid)
{
	MutexLock lockStream(mtxMutex);
	Request stR;
	stR.eGrid = in_eGrid;
	stR.nId = in_nId;
	stR.nLevel = in_nLevel;
	stR.nX = in_nX;
	stR.nY = in_nY;
	arrPending.push_back(stR);
}

bool StreamingVirtualTextureLoader::HasPending() const
{
	MutexLock lockStream(mtxMutex);
	return !arrPending.is_empty();
}

void StreamingVirtualTextureLoader::Submit()
{
	{
		MutexLock lockStream(mtxMutex);
		if (arrPending.is_empty() || nTask != WorkerThreadPool::INVALID_TASK_ID)
		{
			return;
		}
	}
	nTask = WorkerThreadPool::get_singleton()->add_native_task(&StreamingVirtualTextureLoader::RunStatic, this, false, "RVT Stream Tiles");
}

void StreamingVirtualTextureLoader::Run()
{
	LocalVector<Request> arrBatch;
	{
		MutexLock lockStream(mtxMutex);
		arrBatch = arrPending;
		arrPending.clear();
	}

	Ref<FileAccess> refReader;
	if (stIndexFile.IsOpen())
	{
		refReader = FileAccess::open(strPath, FileAccess::READ);
	}

	LocalVector<Result> arrResults;
	for (const Request &stR : arrBatch)
	{
		Result stOut;
		stOut.nId = stR.nId;
		stOut.bFromGrid = stR.eGrid.nExtent > 0;
		if (stOut.bFromGrid)
		{
			stOut.arrData = stR.eGrid.Produce(stR.nLevel, stR.nX, stR.nY);
		}
		else if (refReader.is_valid())
		{
			if (stIndexFile.ReadTile(stR.nLevel, stR.nX, stR.nY, stOut.arrData, refReader.ptr()) != OK)
			{
				stOut.arrData.clear();
			}
		}
		arrResults.push_back(stOut);
	}

	{
		MutexLock lockStream(mtxMutex);
		for (const Result &stR : arrResults)
		{
			arrDone.push_back(stR);
		}
	}
}

bool StreamingVirtualTextureLoader::Poll(LocalVector<Result> &out_arrDone)
{
	// The render thread owns the task handle. Reap it before accepting the next batch.
	if (nTask != WorkerThreadPool::INVALID_TASK_ID && WorkerThreadPool::get_singleton()->is_task_completed(nTask))
	{
		WorkerThreadPool::get_singleton()->wait_for_task_completion(nTask);
		nTask = WorkerThreadPool::INVALID_TASK_ID;
	}
	MutexLock lockStream(mtxMutex);
	if (arrDone.is_empty())
	{
		return false;
	}
	out_arrDone = arrDone;
	arrDone.clear();
	return true;
}

void StreamingVirtualTextureLoader::Flush()
{
	WorkerThreadPool::TaskID nId = WorkerThreadPool::INVALID_TASK_ID;
	{
		MutexLock lockStream(mtxMutex);
		nId = nTask;
	}
	if (nId != WorkerThreadPool::INVALID_TASK_ID)
	{
		WorkerThreadPool::get_singleton()->wait_for_task_completion(nId);
		MutexLock lockStream(mtxMutex);
		nTask = WorkerThreadPool::INVALID_TASK_ID;
	}
}

StreamingVirtualTextureLoader::~StreamingVirtualTextureLoader()
{
	Flush();
}
