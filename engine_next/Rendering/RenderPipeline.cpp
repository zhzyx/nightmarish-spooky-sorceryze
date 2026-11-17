/**************************************************************************/
/*  RenderPipeline.cpp                                                    */
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

#include "engine_next/Rendering/RenderPipeline.h"

#include <cstddef>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{

namespace
{

bool AddPipelinePass(FrameGraph &stGraph, RenderPipeline &stPipeline, const PassDesc &stDescription, PassWork eWork, GraphDiagnostic &out_stDiagnostic,
					 std::uint32_t nMipIndex = INVALID_RESOURCE)
{
	const PassId nPass = stGraph.AddPass(stDescription);
	if (nPass == INVALID_PASS)
	{
		out_stDiagnostic = { GraphError::InvalidPass, INVALID_PASS, INVALID_RESOURCE, "Render pipeline pass declaration failed." };
		return false;
	}
	stPipeline.arrWorkByPass.resize(static_cast<std::size_t>(nPass) + 1);
	stPipeline.arrWorkByPass[nPass] = eWork;
	stPipeline.arrPassMipIndex.resize(static_cast<std::size_t>(nPass) + 1, INVALID_RESOURCE);
	stPipeline.arrPassMipIndex[nPass] = nMipIndex;
	return true;
}

} // namespace

bool BuildRenderPipeline(bool bSceneMode, RenderPipeline &out_stPipeline, GraphDiagnostic &out_stDiagnostic, std::uint32_t nLocalShadowViews, bool bTemporal,
						 bool bExposure, std::uint32_t nBloomMips, std::uint32_t nReflectionMips, ForwardEffects stForwardEffects, bool bMaterialExtensions)
{
	if (nLocalShadowViews > 28)
	{
		out_stDiagnostic = { GraphError::CapacityExceeded, INVALID_PASS, INVALID_RESOURCE, "Local shadow view budget exceeded." };
		return false;
	}
	if (nBloomMips > 6 || (bSceneMode && nBloomMips != 0 && !bExposure))
	{
		out_stDiagnostic = { GraphError::InvalidAccess, INVALID_PASS, INVALID_RESOURCE, "Bloom requires exposure and at most six mips." };
		return false;
	}
	if (nReflectionMips > 6)
	{
		out_stDiagnostic = { GraphError::CapacityExceeded, INVALID_PASS, INVALID_RESOURCE, "Reflection color-mip budget exceeded." };
		return false;
	}
	FrameGraph stGraph;
	RenderPipeline stPipeline;
	stPipeline.nTint = stGraph.AddResource({ "Tint", ResourceState::Common, true });
	stPipeline.nColor = stGraph.AddResource({ "Color", ResourceState::Common, false });
	stPipeline.nDepth = stGraph.AddResource({ "Depth", ResourceState::DepthWrite, true });
	stPipeline.nBackbuffer = stGraph.AddResource({ "Backbuffer", ResourceState::Present, true });
	if (!AddPipelinePass(stGraph, stPipeline, { "ComputeTint", QueueType::Compute, { { stPipeline.nTint, ResourceState::UnorderedAccess, true } }, {} },
						 PassWork::ComputeTint, out_stDiagnostic))
	{
		return false;
	}
	if (bSceneMode)
	{
		stPipeline.nDirectionalShadow = stGraph.AddResource({ "DirectionalShadow", ResourceState::DepthWrite, true, 4 });
		if (!AddPipelinePass(stGraph, stPipeline,
							 { "DirectionalShadow", QueueType::Graphics, { { stPipeline.nDirectionalShadow, ResourceState::DepthWrite, true } }, {} },
							 PassWork::DirectionalShadow, out_stDiagnostic))
		{
			return false;
		}
		stPipeline.nLocalShadow = stGraph.AddResource({ "LocalShadow", ResourceState::DepthWrite, true, nLocalShadowViews == 0 ? 1U : nLocalShadowViews });
		if (!AddPipelinePass(stGraph, stPipeline, { "LocalShadow", QueueType::Graphics, { { stPipeline.nLocalShadow, ResourceState::DepthWrite, true } }, {} },
							 PassWork::LocalShadow, out_stDiagnostic))
		{
			return false;
		}
		stPipeline.arrGbuffer[0] = stGraph.AddResource({ "GBufferBase", ResourceState::Common, false });
		stPipeline.arrGbuffer[1] = stGraph.AddResource({ "GBufferNormal", ResourceState::Common, false });
		stPipeline.arrGbuffer[2] = stGraph.AddResource({ "GBufferSurface", ResourceState::Common, false });
		stPipeline.arrGbuffer[3] = stGraph.AddResource({ "GBufferEmissive", ResourceState::Common, false });
		stPipeline.nHdr = stGraph.AddResource({ "HdrColor", ResourceState::Common, false });
		PassDesc stGbuffer{ "GBuffer", QueueType::Graphics, {}, {} };
		PassDesc stLighting{ "DeferredLighting", QueueType::Graphics, { { stPipeline.nTint, ResourceState::ShaderRead, false } }, {} };
		if (bExposure)
		{
			stPipeline.nHistogram = stGraph.AddResource({ "ExposureHistogram", ResourceState::Common, true });
			stPipeline.nExposureRead = stGraph.AddResource({ "ExposureRead", ResourceState::Common, true });
			stPipeline.nExposureWrite = stGraph.AddResource({ "ExposureWrite", ResourceState::Common, true });
			stPipeline.nPostReadback = stGraph.AddResource({ "PostProcessReadback", ResourceState::CopyDestination, true });
			if (!AddPipelinePass(stGraph, stPipeline,
								 { "PrepareExposure",
								   QueueType::Graphics,
								   { { stPipeline.nExposureRead, ResourceState::UnorderedAccess, true, 0, ALL_SUBRESOURCES, true },
									 { stPipeline.nHistogram, ResourceState::UnorderedAccess, true } },
								   {} },
								 PassWork::PrepareExposure, out_stDiagnostic))
			{
				return false;
			}
			stGbuffer.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::ShaderRead, false });
			stLighting.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::ShaderRead, false });
		}
		for (ResourceId nResource : stPipeline.arrGbuffer)
		{
			stGbuffer.arrAccesses.push_back({ nResource, ResourceState::RenderTarget, true });
			stLighting.arrAccesses.push_back({ nResource, ResourceState::ShaderRead, false });
		}
		if (bMaterialExtensions)
		{
			stPipeline.arrMaterialBuffers[0] = stGraph.AddResource({ "MaterialLobes", ResourceState::Common, false });
			stPipeline.arrMaterialBuffers[1] = stGraph.AddResource({ "MaterialTangent", ResourceState::Common, false });
			for (ResourceId nResource : stPipeline.arrMaterialBuffers)
			{
				stGbuffer.arrAccesses.push_back({ nResource, ResourceState::RenderTarget, true });
				stLighting.arrAccesses.push_back({ nResource, ResourceState::ShaderRead, false });
			}
		}
		stPipeline.nMotion = stGraph.AddResource({ "Motion", ResourceState::Common, false });
		stPipeline.nObjectId = stGraph.AddResource({ "ObjectId", ResourceState::Common, false });
		stGbuffer.arrAccesses.push_back({ stPipeline.nMotion, ResourceState::RenderTarget, true });
		stGbuffer.arrAccesses.push_back({ stPipeline.nObjectId, ResourceState::RenderTarget, true });
		stGbuffer.arrAccesses.push_back({ stPipeline.nDepth, ResourceState::DepthWrite, true });
		stLighting.arrAccesses.push_back({ stPipeline.nDepth, ResourceState::DepthRead, false });
		stLighting.arrAccesses.push_back({ stPipeline.nHdr, ResourceState::RenderTarget, true });
		stLighting.arrAccesses.push_back({ stPipeline.nDirectionalShadow, ResourceState::ShaderRead, false });
		stLighting.arrAccesses.push_back({ stPipeline.nLocalShadow, ResourceState::ShaderRead, false });
		if (nReflectionMips != 0)
		{
			stPipeline.nEnvironmentSpecular = stGraph.AddResource({ "EnvironmentSpecular", ResourceState::Common, false });
			stPipeline.nReflection = stGraph.AddResource({ "Reflection", ResourceState::Common, false });
			stPipeline.nReflectedHdr = stGraph.AddResource({ "ReflectedHdr", ResourceState::Common, false });
			stLighting.arrAccesses.push_back({ stPipeline.nEnvironmentSpecular, ResourceState::RenderTarget, true });
		}
		if (!AddPipelinePass(stGraph, stPipeline, stGbuffer, PassWork::GBuffer, out_stDiagnostic) ||
			!AddPipelinePass(stGraph, stPipeline, stLighting, PassWork::DeferredLighting, out_stDiagnostic))
		{
			return false;
		}
		ResourceId nToneMapSource = stPipeline.nHdr;
		if (nReflectionMips != 0)
		{
			if (!AddPipelinePass(stGraph, stPipeline,
								 { "ReflectionRadiance",
								   QueueType::Graphics,
								   { { stPipeline.nHdr, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nEnvironmentSpecular, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nReflectedHdr, ResourceState::UnorderedAccess, true } },
								   {} },
								 PassWork::ReflectionRadiance, out_stDiagnostic))
			{
				return false;
			}
			ResourceId nMipSource = stPipeline.nReflectedHdr;
			for (std::uint32_t nLevel = 1; nLevel < nReflectionMips; ++nLevel)
			{
				const ResourceId nMip = stGraph.AddResource({ "ReflectionColorMip" + std::to_string(nLevel), ResourceState::Common, false });
				stPipeline.arrReflectionMips.push_back(nMip);
				if (!AddPipelinePass(stGraph, stPipeline,
									 { "ReflectionColorMip" + std::to_string(nLevel),
									   QueueType::Graphics,
									   { { nMipSource, ResourceState::NonPixelShaderRead, false }, { nMip, ResourceState::UnorderedAccess, true } },
									   {} },
									 PassWork::ReflectionColorMip, out_stDiagnostic, nLevel))
				{
					return false;
				}
				nMipSource = nMip;
			}
			PassDesc stTrace{ "ReflectionTrace",
							  QueueType::Graphics,
							  { { stPipeline.arrGbuffer[0], ResourceState::NonPixelShaderRead, false },
								{ stPipeline.arrGbuffer[1], ResourceState::NonPixelShaderRead, false },
								{ stPipeline.arrGbuffer[2], ResourceState::NonPixelShaderRead, false },
								{ stPipeline.nDepth, ResourceState::DepthRead, false },
								{ stPipeline.nReflectedHdr, ResourceState::NonPixelShaderRead, false },
								{ stPipeline.nReflection, ResourceState::UnorderedAccess, true } },
							  {} };
			for (ResourceId nMip : stPipeline.arrReflectionMips)
			{
				stTrace.arrAccesses.push_back({ nMip, ResourceState::NonPixelShaderRead, false });
			}
			if (bMaterialExtensions)
			{
				for (ResourceId nResource : stPipeline.arrMaterialBuffers)
				{
					stTrace.arrAccesses.push_back({ nResource, ResourceState::NonPixelShaderRead, false });
				}
				if (bExposure)
				{
					stTrace.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false });
				}
			}
			if (!AddPipelinePass(stGraph, stPipeline, stTrace, PassWork::ReflectionTrace, out_stDiagnostic) ||
				!AddPipelinePass(stGraph, stPipeline,
								 { "ReflectionComposite",
								   QueueType::Graphics,
								   { { stPipeline.nHdr, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nEnvironmentSpecular, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nReflection, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nReflectedHdr, ResourceState::UnorderedAccess, true } },
								   {} },
								 PassWork::ReflectionComposite, out_stDiagnostic))
			{
				return false;
			}
			nToneMapSource = stPipeline.nReflectedHdr;
		}
		if (stForwardEffects.bVolume || stForwardEffects.bTransparency)
		{
			stPipeline.nForwardHdr = stGraph.AddResource({ "ForwardHdr", ResourceState::Common, false });
		}
		if (stForwardEffects.bVolume)
		{
			stPipeline.nVolumeMedium = stGraph.AddResource({ "VolumeMedium", ResourceState::Common, false });
			stPipeline.nVolumeEmission = stGraph.AddResource({ "VolumeEmission", ResourceState::Common, false });
			stPipeline.nVolumeSource = stGraph.AddResource({ "VolumeSource", ResourceState::Common, false });
			stPipeline.nVolumeHistoryRead = stGraph.AddResource({ "VolumeHistoryRead", ResourceState::Common, true });
			stPipeline.nVolumeHistoryWrite = stGraph.AddResource({ "VolumeHistoryWrite", ResourceState::Common, true });
			stPipeline.nVolumeIntegral = stGraph.AddResource({ "VolumeIntegral", ResourceState::Common, false });
			if (!AddPipelinePass(stGraph, stPipeline,
								 { "VolumePrepare",
								   QueueType::Graphics,
								   { { stPipeline.nVolumeHistoryRead, ResourceState::UnorderedAccess, true, 0, ALL_SUBRESOURCES, true } },
								   {} },
								 PassWork::VolumePrepare, out_stDiagnostic) ||
				!AddPipelinePass(
						stGraph, stPipeline,
						{ "VolumeInject",
						  QueueType::Graphics,
						  { { stPipeline.nVolumeMedium, ResourceState::UnorderedAccess, true }, { stPipeline.nVolumeEmission, ResourceState::UnorderedAccess, true } },
						  {} },
						PassWork::VolumeInject, out_stDiagnostic))
			{
				return false;
			}
			PassDesc stVolumeLight{ "VolumeLight",
									QueueType::Graphics,
									{ { stPipeline.nVolumeMedium, ResourceState::NonPixelShaderRead, false },
									  { stPipeline.nVolumeEmission, ResourceState::NonPixelShaderRead, false },
									  { stPipeline.nDirectionalShadow, ResourceState::ShaderRead, false },
									  { stPipeline.nLocalShadow, ResourceState::ShaderRead, false },
									  { stPipeline.nVolumeSource, ResourceState::UnorderedAccess, true } },
									{} };
			PassDesc stVolumeTemporal{ "VolumeTemporal",
									   QueueType::Graphics,
									   { { stPipeline.nVolumeSource, ResourceState::NonPixelShaderRead, false },
										 { stPipeline.nVolumeHistoryRead, ResourceState::NonPixelShaderRead, false },
										 { stPipeline.nVolumeHistoryWrite, ResourceState::UnorderedAccess, true } },
									   {} };
			if (bExposure)
			{
				stVolumeLight.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false });
				stVolumeTemporal.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false });
			}
			if (!AddPipelinePass(stGraph, stPipeline, stVolumeLight, PassWork::VolumeLight, out_stDiagnostic) ||
				!AddPipelinePass(stGraph, stPipeline, stVolumeTemporal, PassWork::VolumeTemporal, out_stDiagnostic) ||
				!AddPipelinePass(stGraph, stPipeline,
								 { "VolumeIntegrate",
								   QueueType::Graphics,
								   { { stPipeline.nVolumeHistoryWrite, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nVolumeIntegral, ResourceState::UnorderedAccess, true } },
								   {} },
								 PassWork::VolumeIntegrate, out_stDiagnostic) ||
				!AddPipelinePass(stGraph, stPipeline,
								 { "VolumeComposite",
								   QueueType::Graphics,
								   { { nToneMapSource, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nDepth, ResourceState::DepthRead, false },
									 { stPipeline.nVolumeIntegral, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nVolumeHistoryWrite, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nForwardHdr, ResourceState::UnorderedAccess, true } },
								   {} },
								 PassWork::VolumeComposite, out_stDiagnostic))
			{
				return false;
			}
			nToneMapSource = stPipeline.nForwardHdr;
		}
		else if (stForwardEffects.bTransparency)
		{
			if (!AddPipelinePass(stGraph, stPipeline,
								 { "ForwardCopy",
								   QueueType::Graphics,
								   { { nToneMapSource, ResourceState::CopySource, false }, { stPipeline.nForwardHdr, ResourceState::CopyDestination, true } },
								   {} },
								 PassWork::ForwardCopy, out_stDiagnostic))
			{
				return false;
			}
			nToneMapSource = stPipeline.nForwardHdr;
		}
		if (stForwardEffects.bTransparency)
		{
			stPipeline.nReactiveMask = stGraph.AddResource({ "ReactiveMask", ResourceState::Common, false });
			PassDesc stTransparency{ "Transparency",
									 QueueType::Graphics,
									 { { stPipeline.nForwardHdr, ResourceState::RenderTarget, true, 0, ALL_SUBRESOURCES, true },
									   { stPipeline.nReactiveMask, ResourceState::RenderTarget, true },
									   { stPipeline.nDepth, ResourceState::DepthRead, false },
									   { stPipeline.nDirectionalShadow, ResourceState::ShaderRead, false },
									   { stPipeline.nLocalShadow, ResourceState::ShaderRead, false },
									   { stPipeline.nTint, ResourceState::ShaderRead, false } },
									 {} };
			if (bExposure)
			{
				stTransparency.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::ShaderRead, false });
			}
			if (stForwardEffects.bVolume)
			{
				stTransparency.arrAccesses.push_back({ stPipeline.nVolumeIntegral, ResourceState::ShaderRead, false });
				stTransparency.arrAccesses.push_back({ stPipeline.nVolumeHistoryWrite, ResourceState::ShaderRead, false });
			}
			if (!AddPipelinePass(stGraph, stPipeline, stTransparency, PassWork::Transparency, out_stDiagnostic))
			{
				return false;
			}
		}
		if (bTemporal)
		{
			const std::array<const char *, 4> arrReadNames{ "HistoryReadColor", "HistoryReadDepth", "HistoryReadNormal", "HistoryReadObjectId" };
			const std::array<const char *, 4> arrWriteNames{ "HistoryWriteColor", "HistoryWriteDepth", "HistoryWriteNormal", "HistoryWriteObjectId" };
			PassDesc stTemporal{ "TemporalResolve",
								 QueueType::Graphics,
								 { { nToneMapSource, ResourceState::NonPixelShaderRead, false },
								   { stPipeline.nDepth, ResourceState::DepthRead, false },
								   { stPipeline.arrGbuffer[1], ResourceState::NonPixelShaderRead, false },
								   { stPipeline.nMotion, ResourceState::NonPixelShaderRead, false },
								   { stPipeline.nObjectId, ResourceState::NonPixelShaderRead, false } },
								 {} };
			for (std::size_t nHistory = 0; nHistory < stPipeline.arrHistoryRead.size(); ++nHistory)
			{
				stPipeline.arrHistoryRead[nHistory] = stGraph.AddResource({ arrReadNames[nHistory], ResourceState::Common, true });
				stPipeline.arrHistoryWrite[nHistory] = stGraph.AddResource({ arrWriteNames[nHistory], ResourceState::Common, true });
				stTemporal.arrAccesses.push_back({ stPipeline.arrHistoryRead[nHistory], ResourceState::NonPixelShaderRead, false });
				stTemporal.arrAccesses.push_back({ stPipeline.arrHistoryWrite[nHistory], ResourceState::UnorderedAccess, true });
			}
			if (bExposure)
			{
				stTemporal.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false });
			}
			if (stForwardEffects.bTransparency)
			{
				stTemporal.arrAccesses.push_back({ stPipeline.nReactiveMask, ResourceState::NonPixelShaderRead, false });
			}
			if (!AddPipelinePass(stGraph, stPipeline, stTemporal, PassWork::TemporalResolve, out_stDiagnostic))
			{
				return false;
			}
			nToneMapSource = stPipeline.arrHistoryWrite[0];
		}
		PassDesc stToneMap{
			"ToneMap", QueueType::Graphics, { { nToneMapSource, ResourceState::ShaderRead, false }, { stPipeline.nColor, ResourceState::RenderTarget, true } }, {}
		};
		if (bExposure)
		{
			if (!AddPipelinePass(stGraph, stPipeline,
								 { "HistogramBuild",
								   QueueType::Graphics,
								   { { nToneMapSource, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nHistogram, ResourceState::UnorderedAccess, true, 0, ALL_SUBRESOURCES, true } },
								   {} },
								 PassWork::HistogramBuild, out_stDiagnostic) ||
				!AddPipelinePass(stGraph, stPipeline,
								 { "ExposureAdapt",
								   QueueType::Graphics,
								   { { stPipeline.nHistogram, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false },
									 { stPipeline.nExposureWrite, ResourceState::UnorderedAccess, true } },
								   {} },
								 PassWork::ExposureAdapt, out_stDiagnostic))
			{
				return false;
			}
			stToneMap.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::ShaderRead, false });
			stToneMap.arrAccesses.push_back({ stPipeline.nExposureWrite, ResourceState::ShaderRead, false });
		}
		for (std::uint32_t nMip = 0; nMip < nBloomMips; ++nMip)
		{
			const ResourceId nDown = stGraph.AddResource({ "BloomDown" + std::to_string(nMip), ResourceState::Common, true });
			stPipeline.arrBloomDown.push_back(nDown);
			const ResourceId nSource = nMip == 0 ? nToneMapSource : stPipeline.arrBloomDown[nMip - 1];
			PassDesc stDown{ "BloomDownsample" + std::to_string(nMip),
							 QueueType::Graphics,
							 { { nSource, ResourceState::NonPixelShaderRead, false }, { nDown, ResourceState::UnorderedAccess, true } },
							 {} };
			if (nMip == 0)
			{
				stDown.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::NonPixelShaderRead, false });
				stDown.arrAccesses.push_back({ stPipeline.nExposureWrite, ResourceState::NonPixelShaderRead, false });
			}
			if (!AddPipelinePass(stGraph, stPipeline, stDown, PassWork::BloomDownsample, out_stDiagnostic, nMip))
			{
				return false;
			}
		}
		if (nBloomMips != 0)
		{
			stPipeline.arrBloomUp.resize(nBloomMips - 1, INVALID_RESOURCE);
			ResourceId nLower = stPipeline.arrBloomDown.back();
			for (std::uint32_t nRemaining = nBloomMips - 1; nRemaining > 0; --nRemaining)
			{
				const std::uint32_t nMip = nRemaining - 1;
				const ResourceId nUp = stGraph.AddResource({ "BloomUp" + std::to_string(nMip), ResourceState::Common, true });
				stPipeline.arrBloomUp[nMip] = nUp;
				if (!AddPipelinePass(stGraph, stPipeline,
									 { "BloomUpsample" + std::to_string(nMip),
									   QueueType::Graphics,
									   { { stPipeline.arrBloomDown[nMip], ResourceState::NonPixelShaderRead, false },
										 { nLower, ResourceState::NonPixelShaderRead, false },
										 { nUp, ResourceState::UnorderedAccess, true } },
									   {} },
									 PassWork::BloomUpsample, out_stDiagnostic, nMip))
				{
					return false;
				}
				nLower = nUp;
			}
			stToneMap.arrAccesses.push_back({ nLower, ResourceState::ShaderRead, false });
		}
		if (!AddPipelinePass(stGraph, stPipeline, stToneMap, PassWork::ToneMap, out_stDiagnostic))
		{
			return false;
		}
		if (bExposure && !AddPipelinePass(stGraph, stPipeline, { "PostProcessReadback", QueueType::Graphics, { { stPipeline.nHistogram, ResourceState::CopySource, false }, { stPipeline.nExposureWrite, ResourceState::CopySource, false }, { stPipeline.nPostReadback, ResourceState::CopyDestination, true } }, {} }, PassWork::PostProcessReadback, out_stDiagnostic))
		{
			return false;
		}
	}
	else if (!AddPipelinePass(stGraph, stPipeline,
							  { "FixedMesh",
								QueueType::Graphics,
								{ { stPipeline.nTint, ResourceState::ShaderRead, false },
								  { stPipeline.nColor, ResourceState::RenderTarget, true },
								  { stPipeline.nDepth, ResourceState::DepthWrite, true } },
								{} },
							  PassWork::FixedMesh, out_stDiagnostic))
	{
		return false;
	}
	if (!AddPipelinePass(stGraph, stPipeline,
						 { "CopyToBackbuffer",
						   QueueType::Graphics,
						   { { stPipeline.nColor, ResourceState::CopySource, false }, { stPipeline.nBackbuffer, ResourceState::CopyDestination, true } },
						   {} },
						 PassWork::CopyToBackbuffer, out_stDiagnostic))
	{
		return false;
	}
	PassDesc stPresent{ "Present",
						QueueType::Graphics,
						{ { stPipeline.nTint, ResourceState::Common, false },
						  { stPipeline.nColor, ResourceState::Common, false },
						  { stPipeline.nBackbuffer, ResourceState::Present, false } },
						{} };
	if (bSceneMode)
	{
		stPresent.arrAccesses.push_back({ stPipeline.nDepth, ResourceState::DepthWrite, true, 0, ALL_SUBRESOURCES, true });
		stPresent.arrAccesses.push_back({ stPipeline.nHdr, ResourceState::Common, false });
		stPresent.arrAccesses.push_back({ stPipeline.nDirectionalShadow, ResourceState::DepthWrite, true, 0, ALL_SUBRESOURCES, true });
		stPresent.arrAccesses.push_back({ stPipeline.nLocalShadow, ResourceState::DepthWrite, true, 0, ALL_SUBRESOURCES, true });
		for (ResourceId nResource : stPipeline.arrGbuffer)
		{
			stPresent.arrAccesses.push_back({ nResource, ResourceState::Common, false });
		}
		if (bMaterialExtensions)
		{
			for (ResourceId nResource : stPipeline.arrMaterialBuffers)
			{
				stPresent.arrAccesses.push_back({ nResource, ResourceState::Common, false });
			}
		}
		stPresent.arrAccesses.push_back({ stPipeline.nMotion, ResourceState::Common, false });
		stPresent.arrAccesses.push_back({ stPipeline.nObjectId, ResourceState::Common, false });
		if (bTemporal)
		{
			for (std::size_t nHistory = 0; nHistory < stPipeline.arrHistoryRead.size(); ++nHistory)
			{
				stPresent.arrAccesses.push_back({ stPipeline.arrHistoryRead[nHistory], ResourceState::Common, false });
				stPresent.arrAccesses.push_back({ stPipeline.arrHistoryWrite[nHistory], ResourceState::Common, false });
			}
		}
		if (bExposure)
		{
			stPresent.arrAccesses.push_back({ stPipeline.nHistogram, ResourceState::Common, false });
			stPresent.arrAccesses.push_back({ stPipeline.nExposureRead, ResourceState::Common, false });
			stPresent.arrAccesses.push_back({ stPipeline.nExposureWrite, ResourceState::Common, false });
		}
		if (nReflectionMips != 0)
		{
			stPresent.arrAccesses.push_back({ stPipeline.nEnvironmentSpecular, ResourceState::Common, false });
			stPresent.arrAccesses.push_back({ stPipeline.nReflection, ResourceState::Common, false });
			stPresent.arrAccesses.push_back({ stPipeline.nReflectedHdr, ResourceState::Common, false });
			for (ResourceId nMip : stPipeline.arrReflectionMips)
			{
				stPresent.arrAccesses.push_back({ nMip, ResourceState::Common, false });
			}
		}
		if (stForwardEffects.bVolume)
		{
			for (ResourceId nResource : { stPipeline.nVolumeMedium, stPipeline.nVolumeEmission, stPipeline.nVolumeSource, stPipeline.nVolumeHistoryRead,
										  stPipeline.nVolumeHistoryWrite, stPipeline.nVolumeIntegral })
			{
				stPresent.arrAccesses.push_back({ nResource, ResourceState::Common, false });
			}
		}
		if (stForwardEffects.bVolume || stForwardEffects.bTransparency)
		{
			stPresent.arrAccesses.push_back({ stPipeline.nForwardHdr, ResourceState::Common, false });
		}
		if (stForwardEffects.bTransparency)
		{
			stPresent.arrAccesses.push_back({ stPipeline.nReactiveMask, ResourceState::Common, false });
		}
		for (ResourceId nResource : stPipeline.arrBloomDown)
		{
			stPresent.arrAccesses.push_back({ nResource, ResourceState::Common, false });
		}
		for (ResourceId nResource : stPipeline.arrBloomUp)
		{
			stPresent.arrAccesses.push_back({ nResource, ResourceState::Common, false });
		}
	}
	if (!AddPipelinePass(stGraph, stPipeline, stPresent, PassWork::Present, out_stDiagnostic) || !stGraph.Compile(stPipeline.stGraph, out_stDiagnostic))
	{
		return false;
	}
	for (const CompiledPass &stPass : stPipeline.stGraph.arrPasses)
	{
		stPipeline.nGraphicsPassCount += stPass.eQueue == QueueType::Graphics ? 1U : 0U;
		stPipeline.nComputePassCount += stPass.eQueue == QueueType::Compute ? 1U : 0U;
	}
	out_stPipeline = std::move(stPipeline);
	return true;
}

} // namespace EngineNext::Rendering
