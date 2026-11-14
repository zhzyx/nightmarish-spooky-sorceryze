/**************************************************************************/
/*  ProcessTransport.cpp                                                  */
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

#include "engine_next/include/EngineNext/AI/ProcessTransport.h"

#include <atomic>
#include <chrono>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#else
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <poll.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;
#endif

namespace EngineNext::AI
{
namespace
{

#ifdef _WIN32
std::wstring Wide(const std::string &in_strValue)
{
	const int nLength = MultiByteToWideChar(CP_UTF8, 0, in_strValue.data(), static_cast<int>(in_strValue.size()), nullptr, 0);
	std::wstring strResult(static_cast<std::size_t>(nLength), L'\0');
	if (nLength > 0)
	{
		(void)MultiByteToWideChar(CP_UTF8, 0, in_strValue.data(), static_cast<int>(in_strValue.size()), strResult.data(), nLength);
	}
	return strResult;
}

std::string QuoteArgument(const std::string &in_strValue)
{
	std::string strResult = "\"";
	std::size_t nBackslashes = 0;
	for (const char nCharacter : in_strValue)
	{
		if (nCharacter == '\\')
		{
			++nBackslashes;
			continue;
		}
		if (nCharacter == '"')
		{
			strResult.append(nBackslashes * 2 + 1, '\\');
			strResult.push_back('"');
			nBackslashes = 0;
			continue;
		}
		strResult.append(nBackslashes, '\\');
		nBackslashes = 0;
		strResult.push_back(nCharacter);
	}
	strResult.append(nBackslashes * 2, '\\');
	strResult.push_back('"');
	return strResult;
}

void ReadWindowsPipe(HANDLE in_pPipe, std::string &out_strText, std::size_t in_nLimit, std::atomic<bool> &out_bOverflow, std::atomic<bool> &out_bDone, HANDLE in_pJob)
{
	char arrBuffer[8192];
	DWORD nRead = 0;
	while (ReadFile(in_pPipe, arrBuffer, sizeof(arrBuffer), &nRead, nullptr) && nRead != 0)
	{
		if (out_strText.size() + nRead > in_nLimit)
		{
			out_bOverflow = true;
			(void)TerminateJobObject(in_pJob, 126);
			break;
		}
		out_strText.append(arrBuffer, nRead);
	}
	out_bDone = true;
}
#endif

} // namespace

bool ProcessTransport::Run(const ProcessSpec &in_stSpec, ProcessResult &out_stResult)
{
	out_stResult = ProcessResult{};
	bCancelRequested = false;
	if (in_stSpec.strExecutable.empty() || in_stSpec.nTimeoutMsec == 0 || in_stSpec.nOutputLimit == 0)
	{
		return false;
	}
#ifdef _WIN32
	SECURITY_ATTRIBUTES stSecurity{ sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE };
	HANDLE pInputRead = nullptr;
	HANDLE pInputWrite = nullptr;
	HANDLE pOutputRead = nullptr;
	HANDLE pOutputWrite = nullptr;
	HANDLE pErrorRead = nullptr;
	HANDLE pErrorWrite = nullptr;
	if (!CreatePipe(&pInputRead, &pInputWrite, &stSecurity, 0) || !CreatePipe(&pOutputRead, &pOutputWrite, &stSecurity, 0) ||
			!CreatePipe(&pErrorRead, &pErrorWrite, &stSecurity, 0))
	{
		return false;
	}
	(void)SetHandleInformation(pInputWrite, HANDLE_FLAG_INHERIT, 0);
	(void)SetHandleInformation(pOutputRead, HANDLE_FLAG_INHERIT, 0);
	(void)SetHandleInformation(pErrorRead, HANDLE_FLAG_INHERIT, 0);
	std::string strCommand = QuoteArgument(in_stSpec.strExecutable);
	for (const std::string &strArgument : in_stSpec.arrArguments)
	{
		strCommand += " " + QuoteArgument(strArgument);
	}
	STARTUPINFOW stStartup{};
	stStartup.cb = sizeof(STARTUPINFOW);
	stStartup.dwFlags = STARTF_USESTDHANDLES;
	stStartup.hStdInput = pInputRead;
	stStartup.hStdOutput = pOutputWrite;
	stStartup.hStdError = pErrorWrite;
	PROCESS_INFORMATION stProcess{};
	const BOOL bCreated = CreateProcessW(Wide(in_stSpec.strExecutable).c_str(), Wide(strCommand).data(), nullptr, nullptr, TRUE, CREATE_SUSPENDED, nullptr, nullptr, &stStartup, &stProcess);
	CloseHandle(pInputRead);
	CloseHandle(pOutputWrite);
	CloseHandle(pErrorWrite);
	if (!bCreated)
	{
		CloseHandle(pInputWrite);
		CloseHandle(pOutputRead);
		CloseHandle(pErrorRead);
		return false;
	}
	HANDLE pJob = CreateJobObjectW(nullptr, nullptr);
	if (pJob == nullptr || !AssignProcessToJobObject(pJob, stProcess.hProcess))
	{
		(void)TerminateProcess(stProcess.hProcess, 126);
		CloseHandle(pInputWrite);
		CloseHandle(pOutputRead);
		CloseHandle(pErrorRead);
		CloseHandle(stProcess.hThread);
		CloseHandle(stProcess.hProcess);
		if (pJob != nullptr)
		{
			CloseHandle(pJob);
		}
		return false;
	}
	JOBOBJECT_EXTENDED_LIMIT_INFORMATION stLimits{};
	stLimits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
	(void)SetInformationJobObject(pJob, JobObjectExtendedLimitInformation, &stLimits, sizeof(stLimits));
	(void)ResumeThread(stProcess.hThread);
	out_stResult.bStarted = true;
	std::atomic<bool> bInputDone{ false };
	std::thread stInput([&]()
			{
		std::size_t nWritten = 0;
		while (nWritten < in_stSpec.strInput.size())
		{
			DWORD nCount = 0;
			if (!WriteFile(pInputWrite, in_stSpec.strInput.data() + nWritten, static_cast<DWORD>(in_stSpec.strInput.size() - nWritten), &nCount, nullptr) || nCount == 0)
			{
				break;
			}
			nWritten += nCount;
		}
		CloseHandle(pInputWrite);
		bInputDone = true; });
	std::atomic<bool> bOverflow{ false };
	std::atomic<bool> bOutputDone{ false };
	std::atomic<bool> bErrorDone{ false };
	std::thread stOutput([&]()
			{ ReadWindowsPipe(pOutputRead, out_stResult.strOutput, in_stSpec.nOutputLimit, bOverflow, bOutputDone, pJob); });
	std::thread stError([&]()
			{ ReadWindowsPipe(pErrorRead, out_stResult.strError, in_stSpec.nOutputLimit, bOverflow, bErrorDone, pJob); });
	const std::uint64_t nStarted = GetTickCount64();
	bool bExited = false;
	for (;;)
	{
		if (WaitForSingleObject(stProcess.hProcess, 0) == WAIT_OBJECT_0)
		{
			bExited = true;
		}
		if (bExited && bInputDone && bOutputDone && bErrorDone)
		{
			break;
		}
		const bool bTimeout = GetTickCount64() - nStarted > in_stSpec.nTimeoutMsec;
		if (bCancelRequested || bTimeout || bOverflow)
		{
			out_stResult.bTimedOut = bTimeout && !bOverflow;
			(void)TerminateJobObject(pJob, 126);
		}
		if (!bExited)
		{
			(void)WaitForSingleObject(stProcess.hProcess, 25);
		}
		else
		{
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		}
	}
	DWORD nExit = 1;
	(void)GetExitCodeProcess(stProcess.hProcess, &nExit);
	out_stResult.nExitCode = static_cast<int>(nExit);
	out_stResult.bExited = true;
	out_stResult.bOutputOverflow = bOverflow;
	stInput.join();
	stOutput.join();
	stError.join();
	CloseHandle(pJob);
	CloseHandle(stProcess.hThread);
	CloseHandle(stProcess.hProcess);
	return true;
#else
	int arrInput[2] = { -1, -1 };
	int arrOutput[2] = { -1, -1 };
	int arrError[2] = { -1, -1 };
	if (pipe(arrInput) != 0 || pipe(arrOutput) != 0 || pipe(arrError) != 0)
	{
		return false;
	}
	std::vector<std::string> arrStrings = { in_stSpec.strExecutable };
	arrStrings.insert(arrStrings.end(), in_stSpec.arrArguments.begin(), in_stSpec.arrArguments.end());
	std::vector<char *> arrArguments;
	for (std::string &strValue : arrStrings)
	{
		arrArguments.push_back(strValue.data());
	}
	arrArguments.push_back(nullptr);
	posix_spawn_file_actions_t stActions;
	posix_spawnattr_t stAttributes;
	(void)posix_spawn_file_actions_init(&stActions);
	(void)posix_spawnattr_init(&stAttributes);
	(void)posix_spawnattr_setpgroup(&stAttributes, 0);
	(void)posix_spawnattr_setflags(&stAttributes, POSIX_SPAWN_SETPGROUP);
	(void)posix_spawn_file_actions_adddup2(&stActions, arrInput[0], STDIN_FILENO);
	(void)posix_spawn_file_actions_adddup2(&stActions, arrOutput[1], STDOUT_FILENO);
	(void)posix_spawn_file_actions_adddup2(&stActions, arrError[1], STDERR_FILENO);
	(void)posix_spawn_file_actions_addclose(&stActions, arrInput[1]);
	(void)posix_spawn_file_actions_addclose(&stActions, arrOutput[0]);
	(void)posix_spawn_file_actions_addclose(&stActions, arrError[0]);
	pid_t nProcess = -1;
	const int nSpawn = posix_spawn(&nProcess, in_stSpec.strExecutable.c_str(), &stActions, &stAttributes, arrArguments.data(), environ);
	(void)posix_spawn_file_actions_destroy(&stActions);
	(void)posix_spawnattr_destroy(&stAttributes);
	if (nSpawn != 0)
	{
		close(arrInput[0]);
		close(arrInput[1]);
		close(arrOutput[0]);
		close(arrOutput[1]);
		close(arrError[0]);
		close(arrError[1]);
		return false;
	}
	out_stResult.bStarted = true;
	close(arrInput[0]);
	close(arrOutput[1]);
	close(arrError[1]);
	(void)fcntl(arrOutput[0], F_SETFL, O_NONBLOCK);
	(void)fcntl(arrError[0], F_SETFL, O_NONBLOCK);
	std::thread stInput([&]()
			{
		sigset_t stBlocked;
		(void)sigemptyset(&stBlocked);
		(void)sigaddset(&stBlocked, SIGPIPE);
		(void)sigprocmask(SIG_BLOCK, &stBlocked, nullptr);
		std::size_t nWritten = 0;
		while (nWritten < in_stSpec.strInput.size())
		{
			const ssize_t nCount = write(arrInput[1], in_stSpec.strInput.data() + nWritten, in_stSpec.strInput.size() - nWritten);
			if (nCount <= 0)
			{
				break;
			}
			nWritten += static_cast<std::size_t>(nCount);
		}
		close(arrInput[1]); });
	const std::chrono::steady_clock::time_point stStarted = std::chrono::steady_clock::now();
	bool bExited = false;
	bool bOutputOpen = true;
	bool bErrorOpen = true;
	int nStatus = 0;
	while (!bExited || bOutputOpen || bErrorOpen)
	{
		pollfd arrFds[2] = { { arrOutput[0], static_cast<short>(bOutputOpen ? POLLIN : 0), 0 }, { arrError[0], static_cast<short>(bErrorOpen ? POLLIN : 0), 0 } };
		(void)poll(arrFds, 2, 25);
		for (int nIndex = 0; nIndex < 2; ++nIndex)
		{
			bool &bOpen = nIndex == 0 ? bOutputOpen : bErrorOpen;
			if (!bOpen)
			{
				continue;
			}
			std::string *pText = nIndex == 0 ? &out_stResult.strOutput : &out_stResult.strError;
			char arrBuffer[8192];
			while (bOpen && !out_stResult.bOutputOverflow)
			{
				const ssize_t nRead = read(arrFds[nIndex].fd, arrBuffer, sizeof(arrBuffer));
				if (nRead > 0)
				{
					if (pText->size() + static_cast<std::size_t>(nRead) > in_stSpec.nOutputLimit)
					{
						out_stResult.bOutputOverflow = true;
						break;
					}
					pText->append(arrBuffer, static_cast<std::size_t>(nRead));
					continue;
				}
				if (nRead == 0)
				{
					bOpen = false;
				}
				if (errno == EAGAIN || errno == EWOULDBLOCK)
				{
					// Wait for the next poll.
				}
				break;
			}
		}
		if (!bExited)
		{
			bExited = waitpid(nProcess, &nStatus, WNOHANG) == nProcess;
		}
		const bool bTimeout = std::chrono::steady_clock::now() - stStarted > std::chrono::milliseconds(in_stSpec.nTimeoutMsec);
		if (bCancelRequested || bTimeout || out_stResult.bOutputOverflow)
		{
			out_stResult.bTimedOut = bTimeout && !out_stResult.bOutputOverflow;
			(void)kill(-nProcess, SIGKILL);
			(void)kill(nProcess, SIGKILL);
			if (!bExited)
			{
				(void)waitpid(nProcess, &nStatus, 0);
				bExited = true;
			}
			if (out_stResult.bOutputOverflow)
			{
				bOutputOpen = false;
				bErrorOpen = false;
			}
		}
	}
	// The process group is owned by this transport. Reap any descendants even
	// when the direct child exited normally after detaching its standard streams.
	(void)kill(-nProcess, SIGKILL);
	stInput.join();
	close(arrOutput[0]);
	close(arrError[0]);
	out_stResult.bExited = true;
	if (WIFEXITED(nStatus))
	{
		out_stResult.nExitCode = WEXITSTATUS(nStatus);
	}
	else if (WIFSIGNALED(nStatus))
	{
		out_stResult.nExitCode = 128 + WTERMSIG(nStatus);
	}
	if ((out_stResult.nExitCode == 126 || out_stResult.nExitCode == 127) && out_stResult.strOutput.empty() && out_stResult.strError.empty())
	{
		out_stResult.bStarted = false;
		return false;
	}
	return true;
#endif
}

void ProcessTransport::Cancel() noexcept
{
	bCancelRequested = true;
}

} // namespace EngineNext::AI
