/**************************************************************************/
/*  MacWorkerGroup.h                                                      */
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

#include <libproc.h>
#include <signal.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include <cerrno>
#include <cstdint>

// Success leaves the direct child waitable so the engine can record its exit
// code. EAGAIN means a live worker on an ordinary poll. ECHILD forbids signaling.
static inline int32_t AwaitMacWorkerGroup(pid_t nLeader, bool bClosing, uint32_t nTimeoutMillis = 2000)
{
	// create_process starts this runner in a private session. Keep the direct
	// child waitable until its group has been signaled, even if it exited first.
	if (nLeader <= 1)
	{
		return EINVAL;
	}
	const uint64_t nDeadline = clock_gettime_nsec_np(CLOCK_UPTIME_RAW) + uint64_t(nTimeoutMillis) * 1000000;
	bool bStopSent = false;
	while (true)
	{
		siginfo_t tInfo = {};
		if (::waitid(P_PID, nLeader, &tInfo, WEXITED | WNOHANG | WNOWAIT) < 0)
		{
			if (errno != EINTR)
			{
				return errno;
			}
		}
		else if (tInfo.si_pid == nLeader)
		{
			break;
		}
		else if (!bClosing)
		{
			return EAGAIN;
		}
		else if (!bStopSent)
		{
			// Stop the leader before checking its group, also covering exit
			// immediately after fork, before the child's setsid().
			if (::kill(nLeader, SIGKILL) < 0 && errno != ESRCH)
			{
				return errno;
			}
			bStopSent = true;
		}
		if (clock_gettime_nsec_np(CLOCK_UPTIME_RAW) >= nDeadline)
		{
			return ETIMEDOUT;
		}
		usleep(1000);
	}
	// Hold the zombie leader as an identity pin through the last observation.
	// Two PID slots suffice to distinguish "only our leader" from a larger
	// group without truncating a positive result into a success.
	while (true)
	{
		if (::kill(-nLeader, SIGKILL) < 0)
		{
			if (errno == ESRCH)
			{
				break; // The leader may have exited before setsid.
			}
			if (errno != EPERM)
			{
				return errno;
			}
		}
		pid_t arrMembers[2] = {};
		const int32_t nBytes = proc_listpids(PROC_PGRP_ONLY, nLeader, arrMembers, sizeof(arrMembers));
		if (nBytes == sizeof(pid_t) && arrMembers[0] == nLeader)
		{
			break;
		}
		if (clock_gettime_nsec_np(CLOCK_UPTIME_RAW) >= nDeadline)
		{
			return ETIMEDOUT;
		}
		usleep(1000);
	}
	return 0;
}
