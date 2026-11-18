/**************************************************************************/
/*  AnimationData.h                                                       */
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

#include "engine_next/include/EngineNext/Assets/SceneDocument.h"
#include "engine_next/include/EngineNext/Rendering/MeshData.h"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{
using AnimationMatrix = std::array<double, 16>;

struct AnimationPlayback
{
	bool bEnabled = false;
	bool bLoop = true;
	std::int32_t nClip = 0;
	double dSpeed = 1;
	double dStartSeconds = 0;
};

enum class AnimationInterpolation : std::uint8_t
{
	Step = 0,
	Linear = 1,
	CubicSpline = 2
};

enum class AnimationProperty : std::uint8_t
{
	Translation = 0,
	Rotation = 1,
	Scale = 2,
	Weights = 3
};

struct SkinInfluence
{
	std::array<std::uint16_t, 4> arrJoints{};
	std::array<float, 4> arrWeights{};
};

struct MorphTarget
{
	std::vector<std::array<float, 3>> arrPositions;
	std::vector<std::array<float, 3>> arrNormals;
	std::vector<std::array<float, 3>> arrTangents;
};

struct PrimitiveDeformation
{
	bool bGenerateNormals = false;
	bool bGenerateTangents = false;
	std::vector<SkinInfluence> arrInfluences;
	std::vector<MorphTarget> arrMorphTargets;
};

struct AnimationNode
{
	std::int32_t nParent = -1;
	std::int32_t nSkin = -1;
	Assets::Transform stTransform;
	bool bMatrix = false;
	AnimationMatrix arrMatrix{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	std::vector<double> arrWeights;
};

struct SkinData
{
	std::vector<std::uint32_t> arrJoints;
	std::vector<AnimationMatrix> arrInverseBindMatrices;
	std::int32_t nSkeleton = -1;
};

struct AnimationChannel
{
	std::uint32_t nNode = 0;
	AnimationProperty eProperty = AnimationProperty::Translation;
	AnimationInterpolation eInterpolation = AnimationInterpolation::Linear;
	std::uint32_t nComponents = 3;
	std::vector<double> arrTimes;
	// Key-major components. Cubic keys store incoming tangent, value, outgoing
	// tangent in that order; tangents are derivatives per second.
	std::vector<double> arrValues;
};

struct AnimationClip
{
	std::string strName;
	std::vector<AnimationChannel> arrChannels;
};

struct AnimationData
{
	// Nodes retain glTF indices, including nodes outside the selected scene.
	std::vector<AnimationNode> arrNodes;
	std::vector<SkinData> arrSkins;
	// Entries match DecodedMesh::arrPrimitives, including flat-normal expansion.
	std::vector<PrimitiveDeformation> arrPrimitives;
	std::vector<AnimationClip> arrClips;
};

struct AnimationPose
{
	std::vector<AnimationMatrix> arrWorldTransforms;
	std::vector<std::vector<double>> arrWeights;
};

struct DeformedInstance
{
	std::uint32_t nInstance = 0;
	// Vertices remain in the mesh-node local space. Apply arrTransform once.
	AnimationMatrix arrTransform{};
	std::vector<MeshVertex> arrVertices;
};

// Pure, thread-independent, immutable-input operations. Clip -1 selects the
// bind pose. Time is seconds; clamp samples endpoint keys, loop wraps the whole
// clip interval [first key,last key). Outputs are unchanged on any failure.
[[nodiscard]] bool EvaluateAnimation(const AnimationData &stAnimation, std::int32_t nClip, double dTimeSeconds, bool bLoop,
									 AnimationPose &out_stPose, Assets::Diagnostics &out_arrDiagnostics);

// Morph deltas are applied before linear blend skinning. A mesh-node inverse
// cancels the instance transform in each joint palette. Singular transforms,
// invalid public data and non-finite/overflowed results fail transactionally.
// This returns CPU vertices only; it does not upload or update GPU resources.
[[nodiscard]] bool DeformAnimation(const DecodedMesh &stMesh, const AnimationData &stAnimation, const AnimationPose &stPose,
								   std::vector<DeformedInstance> &out_arrInstances, Assets::Diagnostics &out_arrDiagnostics);
} // namespace EngineNext::Rendering
