/**************************************************************************/
/*  JpegValidation.c                                                      */
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

#include "engine_next/Rendering/Cook/JpegValidation.h"

#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "engine_next/thirdparty/libjpeg-turbo/src/jpeglib.h"

typedef struct JpegValidationContext
{
	struct jpeg_error_mgr stError;
	struct jpeg_decompress_struct stDecoder;
	struct jpeg_progress_mgr stProgress;
	jmp_buf *pRecovery;
	char arrMessage[JMSG_LENGTH_MAX];
	unsigned int nLastScan;
	uint64_t nBlockVisits;
} JpegValidationContext;

static void OnJpegError(j_common_ptr pDecoder)
{
	JpegValidationContext *pContext = (JpegValidationContext *)pDecoder->err;
	pContext->stError.format_message(pDecoder, pContext->arrMessage);
	longjmp(*pContext->pRecovery, 1);
}

static void OnJpegMessage(j_common_ptr pDecoder, int nLevel)
{
	if (nLevel < 0)
	{
		OnJpegError(pDecoder);
	}
}

static void CopyMessage(char *pDestination, size_t nSize, const char *pSource)
{
	if (pDestination != NULL && nSize > 0)
	{
		const size_t nLength = strlen(pSource);
		const size_t nCopied = nLength < nSize - 1 ? nLength : nSize - 1;
		memcpy(pDestination, pSource, nCopied);
		pDestination[nCopied] = '\0';
	}
}

static void OnJpegProgress(j_common_ptr pDecoder)
{
	JpegValidationContext *pContext = (JpegValidationContext *)pDecoder->err;
	const struct jpeg_decompress_struct *pImage = &pContext->stDecoder;
	const unsigned int nScan = (unsigned int)pImage->input_scan_number;
	if (nScan != pContext->nLastScan)
	{
		const uint64_t nScanBlocks = (uint64_t)pImage->MCUs_per_row * pImage->MCU_rows_in_scan * (unsigned int)pImage->blocks_in_MCU;
		pContext->nLastScan = nScan;
		pContext->nBlockVisits += nScanBlocks;
		if (nScan > 256U || pContext->nBlockVisits > 64ULL * 1024ULL * 1024ULL)
		{
			CopyMessage(pContext->arrMessage, sizeof(pContext->arrMessage), "JPEG exceeds the scan or coefficient-work budget.");
			longjmp(*pContext->pRecovery, 1);
		}
	}
}

int EngineNextValidateJpeg(const unsigned char *pBytes, size_t nSize, unsigned int nWidth, unsigned int nHeight, char *pMessage, size_t nMessageSize)
{
	JpegValidationContext *pContext;
	jmp_buf stRecovery;
	int bValid;
	if (pBytes == NULL || nSize == 0 || nSize > 16U * 1024U * 1024U || nWidth == 0 || nHeight == 0 || nWidth > 8192U || nHeight > 8192U)
	{
		CopyMessage(pMessage, nMessageSize, "JPEG validation input exceeds its bounds.");
		return 0;
	}
	pContext = (JpegValidationContext *)calloc(1, sizeof(JpegValidationContext));
	if (pContext == NULL)
	{
		CopyMessage(pMessage, nMessageSize, "JPEG validation allocation failed.");
		return 0;
	}
	pContext->stDecoder.err = jpeg_std_error(&pContext->stError);
	pContext->stError.error_exit = OnJpegError;
	pContext->stError.emit_message = OnJpegMessage;
	pContext->pRecovery = &stRecovery;
	// Mutable decoder and error state live on the heap so recovery does not read
	// indeterminate automatic variables after longjmp. No C++ objects are active.
	if (setjmp(stRecovery) != 0)
	{
		CopyMessage(pMessage, nMessageSize, pContext->arrMessage);
		jpeg_destroy_decompress(&pContext->stDecoder);
		free(pContext);
		return 0;
	}
	jpeg_create_decompress(&pContext->stDecoder);
	pContext->stProgress.progress_monitor = OnJpegProgress;
	pContext->stDecoder.progress = &pContext->stProgress;
	// The no-backing-store memory manager rejects coefficient arrays exceeding
	// this budget. Its other bounded allocations add overhead to this value.
	pContext->stDecoder.mem->max_memory_to_use = 512L * 1024L * 1024L;
	jpeg_mem_src(&pContext->stDecoder, pBytes, (unsigned long)nSize);
	bValid = jpeg_read_header(&pContext->stDecoder, TRUE) == JPEG_HEADER_OK;
	bValid = bValid && pContext->stDecoder.image_width == nWidth && pContext->stDecoder.image_height == nHeight;
	bValid = bValid && pContext->stDecoder.data_precision == 8;
	bValid = bValid && (pContext->stDecoder.num_components == 1 || pContext->stDecoder.num_components == 3 || pContext->stDecoder.num_components == 4);
	if (bValid)
	{
		bValid = jpeg_read_coefficients(&pContext->stDecoder) != NULL && jpeg_finish_decompress(&pContext->stDecoder);
	}
	if (!bValid)
	{
		CopyMessage(pMessage, nMessageSize, "JPEG header or coefficient stream is unsupported or incomplete.");
	}
	jpeg_destroy_decompress(&pContext->stDecoder);
	free(pContext);
	return bValid;
}
