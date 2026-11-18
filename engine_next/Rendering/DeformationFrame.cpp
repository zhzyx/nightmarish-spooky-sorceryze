/**************************************************************************/
/*  DeformationFrame.cpp                                                  */
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

#include "engine_next/include/EngineNext/Rendering/DeformationFrame.h"
#include "engine_next/Assets/AssetValidation.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <string>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "deformation_frame", "$.animation", pMessage);
	return false;
}

AnimationMatrix Multiply(const AnimationMatrix &arrLeft, const AnimationMatrix &arrRight)
{
	AnimationMatrix arrResult{};
	for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < 4; ++nRow)
		{
			for (std::size_t nInner = 0; nInner < 4; ++nInner)
			{
				arrResult[nColumn * 4 + nRow] += arrLeft[nInner * 4 + nRow] * arrRight[nColumn * 4 + nInner];
			}
		}
	}
	return arrResult;
}
} // namespace

bool ParseAnimationPlayback(const Serialization::JsonValue &stValue, AnimationPlayback &out_stPlayback, Assets::Diagnostics &out_arrDiagnostics)
{
	const Serialization::JsonValue::Object *pObject = Assets::Object(stValue, "$.animation", out_arrDiagnostics);
	if (pObject == nullptr)
	{
		return false;
	}
	Serialization::JsonValue::Object mapFields = *pObject;
	for (const char *pField : { "enabled", "loop", "clip", "speed", "start_seconds" })
	{
		mapFields.emplace(pField, Serialization::JsonValue{});
	}
	if (!Assets::Fields(mapFields, { "enabled", "loop", "clip", "speed", "start_seconds" }, "$.animation", out_arrDiagnostics))
	{
		return false;
	}
	AnimationPlayback stCandidate;
	for (const std::pair<const std::string, Serialization::JsonValue> &stField : *pObject)
	{
		if (stField.first == "enabled" || stField.first == "loop")
		{
			bool bValue = false;
			if (!stField.second.GetBool(bValue))
			{
				return Fail(out_arrDiagnostics, "Animation enabled and loop fields must be booleans.");
			}
			if (stField.first == "enabled")
			{
				stCandidate.bEnabled = bValue;
			}
			else
			{
				stCandidate.bLoop = bValue;
			}
		}
		else if (stField.first == "clip")
		{
			std::int64_t nValue = 0;
			if (!stField.second.GetInteger(nValue) || nValue < -1 || nValue > INT32_MAX)
			{
				return Fail(out_arrDiagnostics, "Animation clip must be -1 or a nonnegative int32 index.");
			}
			stCandidate.nClip = static_cast<std::int32_t>(nValue);
		}
		else
		{
			double dValue = 0;
			if (!stField.second.GetNumber(dValue) || !std::isfinite(dValue))
			{
				return Fail(out_arrDiagnostics, "Animation time parameters must be finite numbers.");
			}
			if (stField.first == "speed")
			{
				stCandidate.dSpeed = dValue;
			}
			else
			{
				stCandidate.dStartSeconds = dValue;
			}
		}
	}
	out_stPlayback = stCandidate;
	return true;
}

bool BuildDeformationFrame(const RenderScene &stScene, const AnimationPlayback &stPlayback, double dSeconds,
						   DeformationFrame &out_stFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	const double dSampleTime = stPlayback.dStartSeconds + dSeconds * stPlayback.dSpeed;
	if (!std::isfinite(dSeconds) || !std::isfinite(dSampleTime) || stPlayback.nClip < -1)
	{
		return Fail(out_arrDiagnostics, "Animation sample time or clip is invalid.");
	}
	DeformationFrame stResult;
	stResult.dSeconds = dSampleTime;
	if (!stPlayback.bEnabled)
	{
		out_stFrame = std::move(stResult);
		return true;
	}
	constexpr std::uint64_t MAX_FRAME_BYTES = 256ULL * 1024 * 1024;
	std::uint64_t nBytes = 0;
	for (const RenderInstance &stInstance : stScene.arrInstances)
	{
		if (stInstance.nAsset >= stScene.arrAssets.size())
		{
			return Fail(out_arrDiagnostics, "Render instance refers to a missing asset.");
		}
	}
	for (std::size_t nAsset = 0; nAsset < stScene.arrAssets.size(); ++nAsset)
	{
		const RenderAsset &stAsset = stScene.arrAssets[nAsset];
		if (!stAsset.bAnimated)
		{
			continue;
		}
		AnimationPose stPose;
		std::vector<DeformedInstance> arrInstances;
		const std::int32_t nClip = stAsset.stAnimation.arrClips.empty() ? -1 : stPlayback.nClip;
		if (!EvaluateAnimation(stAsset.stAnimation, nClip, dSampleTime, stPlayback.bLoop, stPose, out_arrDiagnostics) ||
			!DeformAnimation(stAsset.stMesh, stAsset.stAnimation, stPose, arrInstances, out_arrDiagnostics))
		{
			return false;
		}
		for (std::size_t nDraw = 0; nDraw < stScene.arrInstances.size(); ++nDraw)
		{
			const RenderInstance &stInstance = stScene.arrInstances[nDraw];
			if (stInstance.nAsset != nAsset)
			{
				continue;
			}
			if (stInstance.nMeshInstance >= arrInstances.size() || nDraw > UINT32_MAX)
			{
				return Fail(out_arrDiagnostics, "Animated render instance has no matching glTF instance.");
			}
			const DeformedInstance &stDeformed = arrInstances[stInstance.nMeshInstance];
			const MeshInstance &stMeshInstance = stAsset.stMesh.arrInstances[stInstance.nMeshInstance];
			if (stDeformed.nInstance != stInstance.nMeshInstance || stMeshInstance.nNode != stInstance.nNode ||
				stMeshInstance.nPrimitive != stInstance.nPrimitive || stDeformed.arrVertices.empty() ||
				stDeformed.arrVertices.size() > (MAX_FRAME_BYTES - nBytes) / sizeof(MeshVertex))
			{
				return Fail(out_arrDiagnostics, "Deformed instance identity or frame byte budget is invalid.");
			}
			nBytes += stDeformed.arrVertices.size() * sizeof(MeshVertex);
			DeformedDraw stDraw;
			stDraw.nDraw = static_cast<std::uint32_t>(nDraw);
			stDraw.arrWorld = Multiply(stInstance.arrEntityTransform, stDeformed.arrTransform);
			for (double dValue : stDraw.arrWorld)
			{
				if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
				{
					return Fail(out_arrDiagnostics, "Animated world transform exceeds binary32 range.");
				}
			}
			stDraw.arrVertices = stDeformed.arrVertices;
			stDraw.arrMinimum.fill(std::numeric_limits<double>::max());
			stDraw.arrMaximum.fill(std::numeric_limits<double>::lowest());
			for (const MeshVertex &stVertex : stDraw.arrVertices)
			{
				for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
				{
					stDraw.arrMinimum[nAxis] = (std::min)(stDraw.arrMinimum[nAxis], static_cast<double>(stVertex.arrPosition[nAxis]));
					stDraw.arrMaximum[nAxis] = (std::max)(stDraw.arrMaximum[nAxis], static_cast<double>(stVertex.arrPosition[nAxis]));
				}
			}
			stResult.nVertexCount += stDraw.arrVertices.size();
			stResult.arrDraws.push_back(std::move(stDraw));
		}
	}
	std::sort(stResult.arrDraws.begin(), stResult.arrDraws.end(), [](const DeformedDraw &stLeft, const DeformedDraw &stRight)
			  { return stLeft.nDraw < stRight.nDraw; });
	out_stFrame = std::move(stResult);
	return true;
}
} // namespace EngineNext::Rendering
