/**************************************************************************/
/*  TestAnimation.cpp                                                     */
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
#include "engine_next/Rendering/Cook/GltfDecoder.h"
#include "engine_next/Rendering/DeformationChanges.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/include/EngineNext/Rendering/DeformationFrame.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace
{
using EngineNext::Rendering::AnimationData;
using EngineNext::Rendering::AnimationPose;
using EngineNext::Rendering::DecodedMesh;
using EngineNext::Rendering::DeformedInstance;
using EngineNext::Serialization::JsonValue;

void Append32(std::vector<std::uint8_t> &out_arrBytes, std::uint32_t nValue)
{
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> (nByte * 8U)));
	}
}

struct Fixture
{
	JsonValue::Object mapRoot;
	std::vector<std::uint8_t> arrBinary;

	std::int64_t Floats(const char *pType, std::uint32_t nComponents, const std::vector<float> &arrValues)
	{
		while (arrBinary.size() % 4 != 0)
		{
			arrBinary.push_back(0);
		}
		const std::size_t nOffset = arrBinary.size();
		for (float fValue : arrValues)
		{
			std::uint32_t nBits = 0;
			std::memcpy(&nBits, &fValue, sizeof(nBits));
			Append32(arrBinary, nBits);
		}
		const std::int64_t nAccessor = Accessor(pType, arrValues.size() / nComponents, nOffset, arrBinary.size() - nOffset, 5126, false);
		JsonValue::List arrMinimum;
		JsonValue::List arrMaximum;
		for (std::size_t nComponent = 0; nComponent < nComponents; ++nComponent)
		{
			float fMinimum = arrValues[nComponent];
			float fMaximum = arrValues[nComponent];
			for (std::size_t nValue = nComponent; nValue < arrValues.size(); nValue += nComponents)
			{
				fMinimum = (std::min)(fMinimum, arrValues[nValue]);
				fMaximum = (std::max)(fMaximum, arrValues[nValue]);
			}
			arrMinimum.emplace_back(static_cast<double>(fMinimum));
			arrMaximum.emplace_back(static_cast<double>(fMaximum));
		}
		mapRoot["accessors"].GetList()->at(static_cast<std::size_t>(nAccessor)).GetObject()->emplace("min", arrMinimum);
		mapRoot["accessors"].GetList()->at(static_cast<std::size_t>(nAccessor)).GetObject()->emplace("max", arrMaximum);
		return nAccessor;
	}

	std::int64_t Accessor(const char *pType, std::size_t nCount, std::size_t nOffset, std::size_t nBytes, std::int64_t nComponent, bool bNormalized)
	{
		JsonValue::List &arrViews = *mapRoot["bufferViews"].GetList();
		JsonValue::List &arrAccessors = *mapRoot["accessors"].GetList();
		const std::int64_t nView = static_cast<std::int64_t>(arrViews.size());
		arrViews.emplace_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", static_cast<std::int64_t>(nOffset) }, { "byteLength", static_cast<std::int64_t>(nBytes) } });
		arrAccessors.emplace_back(JsonValue::Object{ { "bufferView", nView }, { "count", static_cast<std::int64_t>(nCount) }, { "componentType", nComponent }, { "type", pType }, { "normalized", bNormalized } });
		return static_cast<std::int64_t>(arrAccessors.size() - 1);
	}

	Fixture()
	{
		mapRoot = {
			{ "asset", JsonValue::Object{ { "version", "2.0" } } },
			{ "buffers", JsonValue::List{ JsonValue::Object{ { "byteLength", std::int64_t{ 1 } } } } },
			{ "bufferViews", JsonValue::List{} },
			{ "accessors", JsonValue::List{} },
		};
		const std::int64_t nPosition = Floats("VEC3", 3, { 0, 0, 0, 1, 0, 0, 0, 1, 0 });
		const std::int64_t nNormal = Floats("VEC3", 3, { 0, 0, 1, 0, 0, 1, 0, 0, 1 });
		const std::int64_t nTangent = Floats("VEC4", 4, { 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1 });
		const std::size_t nOffset = arrBinary.size();
		arrBinary.insert(arrBinary.end(), 12, 0);
		const std::int64_t nJoints = Accessor("VEC4", 3, nOffset, 12, 5121, false);
		const std::int64_t nWeights = Floats("VEC4", 4, { 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0 });
		const std::int64_t nMorph = Floats("VEC3", 3, { 2, 0, 0, 2, 0, 0, 2, 0, 0 });
		mapRoot["meshes"] = JsonValue::List{ JsonValue::Object{
				{ "weights", JsonValue::List{ 0.25 } },
				{ "primitives", JsonValue::List{ JsonValue::Object{
										{ "attributes", JsonValue::Object{ { "POSITION", nPosition }, { "NORMAL", nNormal }, { "TANGENT", nTangent }, { "JOINTS_0", nJoints }, { "WEIGHTS_0", nWeights } } },
										{ "targets", JsonValue::List{ JsonValue::Object{ { "POSITION", nMorph } } } },
								} } },
		} };
		mapRoot["nodes"] = JsonValue::List{
			JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "skin", std::int64_t{ 0 } }, { "translation", JsonValue::List{ 5.0, 0.0, 0.0 } }, { "children", JsonValue::List{ std::int64_t{ 1 } } }, { "weights", JsonValue::List{ 0.5 } } },
			JsonValue::Object{ { "translation", JsonValue::List{ 0.0, 1.0, 0.0 } } },
		};
		mapRoot["skins"] = JsonValue::List{ JsonValue::Object{ { "joints", JsonValue::List{ std::int64_t{ 1 } } }, { "skeleton", std::int64_t{ 1 } } } };
	}

	JsonValue::Object &Primitive()
	{
		return *(*mapRoot["meshes"].GetList())[0].GetObject()->at("primitives").GetList()->at(0).GetObject();
	}

	void Animate(const char *pPath, const char *pInterpolation, std::uint32_t nComponents, const std::vector<float> &arrValues, std::int64_t nNode = 1)
	{
		const std::int64_t nInput = Floats("SCALAR", 1, { 0, 2 });
		const std::int64_t nOutput = Floats(nComponents == 4 ? "VEC4" : nComponents == 3 ? "VEC3"
																						 : "SCALAR",
											nComponents, arrValues);
		mapRoot["animations"] = JsonValue::List{ JsonValue::Object{
				{ "samplers", JsonValue::List{ JsonValue::Object{ { "input", nInput }, { "output", nOutput }, { "interpolation", pInterpolation } } } },
				{ "channels", JsonValue::List{ JsonValue::Object{ { "sampler", std::int64_t{ 0 } }, { "target", JsonValue::Object{ { "node", nNode }, { "path", pPath } } } } } },
		} };
	}

	std::vector<std::uint8_t> Bytes()
	{
		mapRoot["buffers"].GetList()->at(0).GetObject()->at("byteLength") = static_cast<std::int64_t>(arrBinary.size());
		std::string strJson;
		ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(JsonValue(mapRoot), strJson));
		while (strJson.size() % 4 != 0)
		{
			strJson.push_back(' ');
		}
		std::vector<std::uint8_t> arrPadded = arrBinary;
		while (arrPadded.size() % 4 != 0)
		{
			arrPadded.push_back(0);
		}
		std::vector<std::uint8_t> arrBytes;
		Append32(arrBytes, 0x46546C67);
		Append32(arrBytes, 2);
		Append32(arrBytes, static_cast<std::uint32_t>(28 + strJson.size() + arrPadded.size()));
		Append32(arrBytes, static_cast<std::uint32_t>(strJson.size()));
		Append32(arrBytes, 0x4E4F534A);
		arrBytes.insert(arrBytes.end(), strJson.begin(), strJson.end());
		Append32(arrBytes, static_cast<std::uint32_t>(arrPadded.size()));
		Append32(arrBytes, 0x004E4942);
		arrBytes.insert(arrBytes.end(), arrPadded.begin(), arrPadded.end());
		return arrBytes;
	}
};

bool Decode(Fixture &stFixture, DecodedMesh &out_stMesh, AnimationData &out_stAnimation)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return EngineNext::Rendering::DecodeAnimatedGlb(stFixture.Bytes(), out_stMesh, out_stAnimation, arrDiagnostics);
}

bool Evaluate(const AnimationData &stAnimation, double dTime, AnimationPose &out_stPose, std::int32_t nClip = 0, bool bLoop = false)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return EngineNext::Rendering::EvaluateAnimation(stAnimation, nClip, dTime, bLoop, out_stPose, arrDiagnostics);
}

bool Deform(const DecodedMesh &stMesh, const AnimationData &stAnimation, const AnimationPose &stPose, std::vector<DeformedInstance> &out_arrInstances)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return EngineNext::Rendering::DeformAnimation(stMesh, stAnimation, stPose, out_arrInstances, arrDiagnostics);
}

bool Near(double dLeft, double dRight)
{
	return std::abs(dLeft - dRight) < 1.0e-5;
}
} // namespace

ENGINE_NEXT_TEST("Animation: explicit decode preserves static rejection and source bytes")
{
	Fixture stFixture;
	const std::vector<std::uint8_t> arrBytes = stFixture.Bytes();
	DecodedMesh stMesh;
	AnimationData stAnimation;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::DecodeGlb(arrBytes, stMesh, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeAnimatedGlb(arrBytes, stMesh, stAnimation, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.Bytes(), arrBytes);
	ENGINE_NEXT_CHECK_EQ(stAnimation.arrNodes.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stAnimation.arrSkins[0].arrInverseBindMatrices[0][0], 1);
}

ENGINE_NEXT_TEST("Animation: linear skin palette and morph order cancel mesh transform")
{
	Fixture stFixture;
	stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0, 0, 3, 0 });
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 1, stPose));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[0], 1));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[1], 2));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrTransform[12], 5));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrPrimitives[0].arrVertices[0].arrPosition[0], 0);
}

ENGINE_NEXT_TEST("Animation: step clamps and looping has explicit endpoint semantics")
{
	Fixture stFixture;
	stFixture.Animate("translation", "STEP", 3, { 0, 1, 0, 0, 3, 0 });
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	for (double dTime : { -1.0, 0.0, 1.0, std::nextafter(2.0, 0.0) })
	{
		ENGINE_NEXT_CHECK(Evaluate(stAnimation, dTime, stPose));
		ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][13], 1));
	}
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 2, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][13], 3));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 2, stPose, 0, true));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][13], 1));
}

ENGINE_NEXT_TEST("Animation: cubic tangents scale by key duration")
{
	Fixture stFixture;
	stFixture.Animate("weights", "CUBICSPLINE", 1, { 0, 0, 1, 0, 2, 0 }, 0);
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 1, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWeights[0][0], 1.25));
}

ENGINE_NEXT_TEST("Animation: quaternion linear interpolation uses shortest arc")
{
	Fixture stFixture;
	stFixture.Animate("rotation", "LINEAR", 4, { 0, 0, 0, 1, 0, 0, 0, -1 });
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 1, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][0], 1));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][5], 1));
	stFixture.Animate("rotation", "LINEAR", 4, { 0, 0, 0, 1, 0, 0, 1, 0 });
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 1, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][0], 0));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][1], 1));
}

ENGINE_NEXT_TEST("Animation: cubic quaternion result is normalized")
{
	Fixture stFixture;
	stFixture.Animate("rotation", "CUBICSPLINE", 4, { 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0 });
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 1, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][0], 0));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][1], 1));
}

ENGINE_NEXT_TEST("Animation: deformation failure and evaluation failure preserve outputs")
{
	Fixture stFixture;
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances(1);
	arrInstances[0].nInstance = 77;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	const AnimationPose stBefore = stPose;
	ENGINE_NEXT_CHECK(!Evaluate(stAnimation, std::numeric_limits<double>::infinity(), stPose, -1));
	ENGINE_NEXT_CHECK_EQ(stPose.arrWorldTransforms, stBefore.arrWorldTransforms);
	stAnimation.arrPrimitives[0].arrInfluences[0].arrJoints[0] = 100;
	ENGINE_NEXT_CHECK(!Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK_EQ(arrInstances[0].nInstance, 77U);
}

ENGINE_NEXT_TEST("Animation: malformed GLB skin and morph data fail transactionally")
{
	for (int nCase = 0; nCase < 7; ++nCase)
	{
		Fixture stFixture;
		if (nCase == 0)
		{
			stFixture.Primitive().at("attributes").GetObject()->erase("WEIGHTS_0");
		}
		if (nCase == 1)
		{
			stFixture.mapRoot["skins"].GetList()->at(0).GetObject()->at("joints") = JsonValue::List{ std::int64_t{ 1 }, std::int64_t{ 1 } };
		}
		if (nCase == 2)
		{
			stFixture.mapRoot["nodes"].GetList()->at(0).GetObject()->at("weights") = JsonValue::List{};
		}
		if (nCase == 3)
		{
			stFixture.Primitive().at("targets").GetList()->at(0).GetObject()->at("POSITION") = std::int64_t{ 4 };
		}
		if (nCase == 4)
		{
			stFixture.mapRoot["accessors"].GetList()->at(3).GetObject()->at("normalized") = true;
		}
		if (nCase == 5)
		{
			stFixture.mapRoot["nodes"].GetList()->at(1).GetObject()->emplace("children", JsonValue::List{ std::int64_t{ 0 } });
		}
		if (nCase == 6)
		{
			stFixture.mapRoot["skins"].GetList()->at(0).GetObject()->emplace("inverseBindMatrices", std::int64_t{ 0 });
		}
		DecodedMesh stMesh;
		stMesh.arrPrimitives.resize(2);
		AnimationData stAnimation;
		stAnimation.arrNodes.resize(3);
		ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh, stAnimation));
		ENGINE_NEXT_CHECK_EQ(stMesh.arrPrimitives.size(), 2U);
		ENGINE_NEXT_CHECK_EQ(stAnimation.arrNodes.size(), 3U);
	}
}

ENGINE_NEXT_TEST("Animation: static input retains static results and flat vertex mapping")
{
	Fixture stFixture;
	stFixture.mapRoot.erase("skins");
	stFixture.mapRoot["nodes"].GetList()->at(0).GetObject()->erase("skin");
	stFixture.mapRoot["nodes"].GetList()->at(0).GetObject()->erase("weights");
	stFixture.mapRoot["meshes"].GetList()->at(0).GetObject()->erase("weights");
	stFixture.Primitive().erase("targets");
	stFixture.Primitive().at("attributes").GetObject()->erase("JOINTS_0");
	stFixture.Primitive().at("attributes").GetObject()->erase("WEIGHTS_0");
	stFixture.Primitive().at("attributes").GetObject()->erase("NORMAL");
	stFixture.Primitive().at("attributes").GetObject()->erase("TANGENT");
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	EngineNext::Assets::Diagnostics arrDiagnostics;
	DecodedMesh stStatic;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::DecodeGlb(stFixture.Bytes(), stStatic, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stStatic.arrPrimitives[0].arrVertices[0].arrPosition, arrInstances[0].arrVertices[0].arrPosition);
	ENGINE_NEXT_CHECK_EQ(stStatic.arrInstances[0].arrTransform, arrInstances[0].arrTransform);
}

ENGINE_NEXT_TEST("Animation: quaternion sweep matches analytic rotation")
{
	Fixture stFixture;
	stFixture.Animate("rotation", "LINEAR", 4, { 0, 0, 0, 1, 0, 0, 1, 0 });
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	for (std::size_t nStep = 0; nStep <= 1000; ++nStep)
	{
		const double dTime = static_cast<double>(nStep) / 500;
		ENGINE_NEXT_CHECK(Evaluate(stAnimation, dTime, stPose));
		ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][0], std::cos(dTime * 1.5707963267948966)));
		ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][1], std::sin(dTime * 1.5707963267948966)));
		ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
		ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[0], std::cos(dTime * 1.5707963267948966)));
		ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[1], 1 + std::sin(dTime * 1.5707963267948966)));
	}
}

ENGINE_NEXT_TEST("Animation: generated flat normal follows the morphed triangle")
{
	Fixture stFixture;
	stFixture.Primitive().at("attributes").GetObject()->erase("NORMAL");
	stFixture.Primitive().at("attributes").GetObject()->erase("TANGENT");
	const std::int64_t nDelta = stFixture.Floats("VEC3", 3, { 0, 0, 0, 0, 0, 0, 0, 0, 2 });
	stFixture.Primitive().at("targets").GetList()->at(0).GetObject()->at("POSITION") = nDelta;
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	const std::array<float, 3> &arrNormal = arrInstances[0].arrVertices[0].arrNormal;
	ENGINE_NEXT_CHECK(Near(arrNormal[1], -std::sqrt(0.5)));
	ENGINE_NEXT_CHECK(Near(arrNormal[2], std::sqrt(0.5)));
}

ENGINE_NEXT_TEST("Animation: position normal and tangent deltas precede skinning")
{
	Fixture stFixture;
	const std::int64_t nNormal = stFixture.Floats("VEC3", 3, { 2, 0, 0, 2, 0, 0, 2, 0, 0 });
	const std::int64_t nTangent = stFixture.Floats("VEC3", 3, { 0, 2, 0, 0, 2, 0, 0, 2, 0 });
	JsonValue::Object &mapTarget = *stFixture.Primitive().at("targets").GetList()->at(0).GetObject();
	mapTarget["NORMAL"] = nNormal;
	mapTarget["TANGENT"] = nTangent;
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	const EngineNext::Rendering::MeshVertex &stVertex = arrInstances[0].arrVertices[0];
	ENGINE_NEXT_CHECK(Near(stVertex.arrNormal[0], std::sqrt(0.5)));
	double dDot = 0;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		dDot += stVertex.arrNormal[nAxis] * stVertex.arrTangent[nAxis];
	}
	ENGINE_NEXT_CHECK(Near(dDot, 0));
	ENGINE_NEXT_CHECK_EQ(stVertex.arrTangent[3], 1);
}

ENGINE_NEXT_TEST("Animation: node transform outside the joint hierarchy cancels for skinning")
{
	Fixture stFixture;
	stFixture.mapRoot["nodes"].GetList()->at(0).GetObject()->erase("children");
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[0] + arrInstances[0].arrTransform[12], 1));
}

ENGINE_NEXT_TEST("Animation: normalized integer weights and animation values")
{
	Fixture stFixture;
	stFixture.Animate("weights", "LINEAR", 1, { 0, 1 }, 0);
	const std::size_t nOffset = stFixture.arrBinary.size();
	stFixture.arrBinary.insert(stFixture.arrBinary.end(), { 0, 255 });
	const std::int64_t nOutput = stFixture.Accessor("SCALAR", 2, nOffset, 2, 5121, true);
	stFixture.mapRoot["animations"].GetList()->at(0).GetObject()->at("samplers").GetList()->at(0).GetObject()->at("output") = nOutput;
	while (stFixture.arrBinary.size() % 4 != 0)
	{
		stFixture.arrBinary.push_back(0);
	}
	const std::size_t nWeightsOffset = stFixture.arrBinary.size();
	stFixture.arrBinary.insert(stFixture.arrBinary.end(), { 255, 0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0 });
	const std::int64_t nWeights = stFixture.Accessor("VEC4", 3, nWeightsOffset, 12, 5121, true);
	stFixture.Primitive().at("attributes").GetObject()->at("WEIGHTS_0") = nWeights;
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 1, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWeights[0][0], 0.5));
	ENGINE_NEXT_CHECK_EQ(stAnimation.arrPrimitives[0].arrInfluences[0].arrWeights[0], 1);
	stFixture.arrBinary[nWeightsOffset] = 254;
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh, stAnimation));
}

ENGINE_NEXT_TEST("Animation: malformed samplers and duplicate targets reject")
{
	for (int nCase = 0; nCase < 5; ++nCase)
	{
		Fixture stFixture;
		stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0, 0, 3, 0 });
		JsonValue::Object &mapClip = *stFixture.mapRoot["animations"].GetList()->at(0).GetObject();
		if (nCase == 0)
		{
			mapClip.at("channels").GetList()->push_back(mapClip.at("channels").GetList()->at(0));
		}
		if (nCase == 1)
		{
			mapClip.at("samplers").GetList()->at(0).GetObject()->at("interpolation") = "BEZIER";
		}
		if (nCase == 2)
		{
			mapClip.at("channels").GetList()->at(0).GetObject()->at("target").GetObject()->at("node") = std::int64_t{ 99 };
		}
		if (nCase == 3)
		{
			mapClip.at("samplers").GetList()->at(0).GetObject()->at("output") = std::int64_t{ 0 };
		}
		if (nCase == 4)
		{
			mapClip.at("channels").GetList()->at(0).GetObject()->at("target").GetObject()->at("path") = "camera";
		}
		DecodedMesh stMesh;
		AnimationData stAnimation;
		ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh, stAnimation));
	}
}

ENGINE_NEXT_TEST("Animation: singular skin and invalid public hierarchy fail without writes")
{
	Fixture stFixture;
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances(1);
	arrInstances[0].nInstance = 17;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	stAnimation.arrNodes[1].stTransform.arrScale = { 0, 1, 1 };
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(!Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK_EQ(arrInstances[0].nInstance, 17U);
	const AnimationPose stBefore = stPose;
	stAnimation.arrNodes[0].nParent = 1;
	ENGINE_NEXT_CHECK(!Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK_EQ(stPose.arrWorldTransforms, stBefore.arrWorldTransforms);
}

ENGINE_NEXT_TEST("Animation: mirrored joint preserves normal and flips tangent handedness")
{
	Fixture stFixture;
	stFixture.mapRoot["nodes"].GetList()->at(1).GetObject()->emplace("scale", JsonValue::List{ -2.0, 3.0, 0.5 });
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrNormal[2], 1));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrTangent[0], -1));
	ENGINE_NEXT_CHECK_EQ(arrInstances[0].arrVertices[0].arrTangent[3], -1);
}

ENGINE_NEXT_TEST("Animation: quantized quaternion keys are normalized after decoding")
{
	Fixture stFixture;
	stFixture.Animate("rotation", "LINEAR", 4, { 0, 0, 0, 1, 0, 0, 1, 0 });
	const std::size_t nOffset = stFixture.arrBinary.size();
	stFixture.arrBinary.insert(stFixture.arrBinary.end(), { 0, 0, 0, 127, 0, 0, 90, 90 });
	const std::int64_t nOutput = stFixture.Accessor("VEC4", 2, nOffset, 8, 5120, true);
	stFixture.mapRoot["animations"].GetList()->at(0).GetObject()->at("samplers").GetList()->at(0).GetObject()->at("output") = nOutput;
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 2, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][0], 0));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[1][1], 1));
}

ENGINE_NEXT_TEST("Animation: inverse bind accessor permits unused trailing matrices")
{
	Fixture stFixture;
	const std::int64_t nInverse = stFixture.Floats("MAT4", 16, { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -1, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 });
	stFixture.mapRoot["skins"].GetList()->at(0).GetObject()->emplace("inverseBindMatrices", nInverse);
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK_EQ(stAnimation.arrSkins[0].arrInverseBindMatrices.size(), 1U);
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[1], 0));
}

ENGINE_NEXT_TEST("Animation: morph-only mesh without nodes uses deterministic implicit instance")
{
	Fixture stFixture;
	stFixture.mapRoot.erase("nodes");
	stFixture.mapRoot.erase("skins");
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[0], 0.5));
}

ENGINE_NEXT_TEST("Animation: cubic weights use key-major packed target components")
{
	Fixture stFixture;
	const std::int64_t nDelta = stFixture.Floats("VEC3", 3, { 0, 1, 0, 0, 1, 0, 0, 1, 0 });
	stFixture.Primitive().at("targets").GetList()->emplace_back(JsonValue::Object{ { "POSITION", nDelta } });
	stFixture.mapRoot["meshes"].GetList()->at(0).GetObject()->at("weights") = JsonValue::List{ 0.0, 0.0 };
	stFixture.mapRoot["nodes"].GetList()->at(0).GetObject()->at("weights") = JsonValue::List{ 0.0, 0.0 };
	stFixture.Animate("weights", "CUBICSPLINE", 1, { 0, 0, 0, 0, 1, -1, 0, 0, 2, 4, 0, 0 }, 0);
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 1, stPose));
	ENGINE_NEXT_CHECK(Near(stPose.arrWeights[0][0], 1.25));
	ENGINE_NEXT_CHECK(Near(stPose.arrWeights[0][1], 1.75));
}

ENGINE_NEXT_TEST("Animation: affine shear inverse cancels the mesh frame")
{
	Fixture stFixture;
	JsonValue::Object &mapNode = *stFixture.mapRoot["nodes"].GetList()->at(0).GetObject();
	mapNode.erase("translation");
	mapNode["matrix"] = JsonValue::List{ 2.0, 0.0, 0.0, 0.0, 0.5, 3.0, 0.0, 0.0, 0.25, 0.5, 4.0, 0.0, 5.0, 6.0, 7.0, 1.0 };
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[0], 1));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[1], 1));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrNormal[2], 1));
}

ENGINE_NEXT_TEST("Animation: cached ancestors do not bypass hierarchy depth budget")
{
	AnimationData stAnimation;
	stAnimation.arrNodes.resize(130);
	for (std::size_t nNode = 1; nNode < stAnimation.arrNodes.size(); ++nNode)
	{
		stAnimation.arrNodes[nNode].nParent = static_cast<std::int32_t>(nNode - 1);
	}
	AnimationPose stPose;
	stPose.arrWeights.resize(1);
	ENGINE_NEXT_CHECK(!Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK_EQ(stPose.arrWeights.size(), 1U);
	stAnimation.arrNodes.pop_back();
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK_EQ(stPose.arrWorldTransforms.size(), 129U);
}

ENGINE_NEXT_TEST("Animation: multiple joint weights blend the skin transforms")
{
	Fixture stFixture;
	stFixture.mapRoot["nodes"].GetList()->at(0).GetObject()->at("children") = JsonValue::List{ std::int64_t{ 1 }, std::int64_t{ 2 } };
	stFixture.mapRoot["nodes"].GetList()->at(1).GetObject()->at("translation") = JsonValue::List{ 0.0, 0.0, 0.0 };
	stFixture.mapRoot["nodes"].GetList()->emplace_back(JsonValue::Object{ { "translation", JsonValue::List{ 2.0, 0.0, 0.0 } } });
	stFixture.mapRoot["skins"].GetList()->at(0).GetObject()->at("joints") = JsonValue::List{ std::int64_t{ 1 }, std::int64_t{ 2 } };
	stFixture.mapRoot["skins"].GetList()->at(0).GetObject()->at("skeleton") = std::int64_t{ 0 };
	const std::size_t nOffset = stFixture.arrBinary.size();
	stFixture.arrBinary.insert(stFixture.arrBinary.end(), { 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0 });
	const std::int64_t nJoints = stFixture.Accessor("VEC4", 3, nOffset, 12, 5121, false);
	const std::int64_t nWeights = stFixture.Floats("VEC4", 4, { 0.25F, 0.75F, 0, 0, 0.25F, 0.75F, 0, 0, 0.25F, 0.75F, 0, 0 });
	stFixture.Primitive().at("attributes").GetObject()->at("JOINTS_0") = nJoints;
	stFixture.Primitive().at("attributes").GetObject()->at("WEIGHTS_0") = nWeights;
	DecodedMesh stMesh;
	AnimationData stAnimation;
	AnimationPose stPose;
	std::vector<DeformedInstance> arrInstances;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, 0, stPose, -1));
	ENGINE_NEXT_CHECK(Deform(stMesh, stAnimation, stPose, arrInstances));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[0], 2.5));
	ENGINE_NEXT_CHECK(Near(arrInstances[0].arrVertices[0].arrPosition[1], 0));
}

ENGINE_NEXT_TEST("Animation: sampler input requires min and max")
{
	for (const char *pField : { "min", "max" })
	{
		Fixture stFixture;
		stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0, 0, 3, 0 });
		const JsonValue::Object &mapSampler = *stFixture.mapRoot["animations"].GetList()->at(0).GetObject()->at("samplers").GetList()->at(0).GetObject();
		std::int64_t nInput = -1;
		ENGINE_NEXT_CHECK(mapSampler.at("input").GetInteger(nInput));
		stFixture.mapRoot["accessors"].GetList()->at(static_cast<std::size_t>(nInput)).GetObject()->erase(pField);
		DecodedMesh stMesh;
		AnimationData stAnimation;
		stMesh.arrPrimitives.resize(2);
		stAnimation.arrNodes.resize(3);
		ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh, stAnimation));
		ENGINE_NEXT_CHECK_EQ(stMesh.arrPrimitives.size(), 2U);
		ENGINE_NEXT_CHECK_EQ(stAnimation.arrNodes.size(), 3U);
	}
}

ENGINE_NEXT_TEST("Animation: sampler bounds match decoded float keys")
{
	const std::vector<std::pair<JsonValue, JsonValue>> arrInvalidBounds{
		{ JsonValue::List{}, JsonValue::List{ 2.0 } },
		{ JsonValue::List{ 0.0, 0.0 }, JsonValue::List{ 2.0 } },
		{ JsonValue::List{ "0" }, JsonValue::List{ 2.0 } },
		{ JsonValue::List{ 1.0 }, JsonValue::List{ 2.0 } },
		{ JsonValue::List{ 0.0 }, JsonValue::List{ 3.0 } },
		{ JsonValue::List{ 2.0 }, JsonValue::List{ 1.0 } },
		{ JsonValue::List{ -1.0 }, JsonValue::List{ 2.0 } },
		{ JsonValue::List{ 0.0 }, JsonValue::List{ std::numeric_limits<double>::max() } },
	};
	for (const std::pair<JsonValue, JsonValue> &stBounds : arrInvalidBounds)
	{
		Fixture stFixture;
		stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0, 0, 3, 0 });
		const JsonValue::Object &mapSampler = *stFixture.mapRoot["animations"].GetList()->at(0).GetObject()->at("samplers").GetList()->at(0).GetObject();
		std::int64_t nInput = -1;
		ENGINE_NEXT_CHECK(mapSampler.at("input").GetInteger(nInput));
		JsonValue::Object &mapInput = *stFixture.mapRoot["accessors"].GetList()->at(static_cast<std::size_t>(nInput)).GetObject();
		mapInput["min"] = stBounds.first;
		mapInput["max"] = stBounds.second;
		DecodedMesh stMesh;
		AnimationData stAnimation;
		ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh, stAnimation));
	}
	Fixture stFixture;
	stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0, 0, 3, 0 });
	std::int64_t nInput = -1;
	ENGINE_NEXT_CHECK(stFixture.mapRoot["animations"].GetList()->at(0).GetObject()->at("samplers").GetList()->at(0).GetObject()->at("input").GetInteger(nInput));
	stFixture.mapRoot["accessors"].GetList()->at(static_cast<std::size_t>(nInput)).GetObject()->at("max") = JsonValue::List{ 2.00000001 };
	DecodedMesh stMesh;
	AnimationData stAnimation;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
}

ENGINE_NEXT_TEST("Animation: looping retains phase for large and negative playback times")
{
	AnimationData stAnimation;
	stAnimation.arrNodes.resize(1);
	stAnimation.arrClips.resize(1);
	EngineNext::Rendering::AnimationChannel stChannel;
	stChannel.arrTimes = { 1, 3 };
	stChannel.arrValues = { 10, 0, 0, 30, 0, 0 };
	stAnimation.arrClips[0].arrChannels.push_back(stChannel);
	AnimationPose stPose;
	for (double dTime : { 18014398509481984.0, -18014398509481984.0, std::numeric_limits<double>::max(), -std::numeric_limits<double>::max(), 0.0, 2.0 })
	{
		ENGINE_NEXT_CHECK(Evaluate(stAnimation, dTime, stPose, 0, true));
		ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[0][12], 20));
	}
	for (double dTime : { 1.0, 3.0, -1.0 })
	{
		ENGINE_NEXT_CHECK(Evaluate(stAnimation, dTime, stPose, 0, true));
		ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[0][12], 10));
	}
	stAnimation.arrClips[0].arrChannels[0].arrTimes = { 1 };
	stAnimation.arrClips[0].arrChannels[0].arrValues = { 10, 0, 0 };
	ENGINE_NEXT_CHECK(Evaluate(stAnimation, std::numeric_limits<double>::max(), stPose, 0, true));
	ENGINE_NEXT_CHECK(Near(stPose.arrWorldTransforms[0][12], 10));
}

ENGINE_NEXT_TEST("Animation: JSON input bounds use float component rounding")
{
	for (float fTime : { 0.0F, 0.1F, std::numeric_limits<float>::max() })
	{
		Fixture stFixture;
		stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0 });
		const std::int64_t nInput = stFixture.Floats("SCALAR", 1, { fTime });
		stFixture.mapRoot["animations"].GetList()->at(0).GetObject()->at("samplers").GetList()->at(0).GetObject()->at("input") = nInput;
		JsonValue::Object &mapInput = *stFixture.mapRoot["accessors"].GetList()->at(static_cast<std::size_t>(nInput)).GetObject();
		if (fTime == 0)
		{
			mapInput["min"] = JsonValue::List{ 1.0e-50 };
			mapInput["max"] = JsonValue::List{ -1.0e-50 };
		}
		else if (fTime == 0.1F)
		{
			mapInput["min"] = JsonValue::List{ 0.100000004 };
			mapInput["max"] = JsonValue::List{ 0.100000001 };
		}
		else
		{
			mapInput["min"] = JsonValue::List{ 3.4028235e38 };
			mapInput["max"] = JsonValue::List{ 3.4028235e38 };
		}
		DecodedMesh stMesh;
		AnimationData stAnimation;
		ENGINE_NEXT_CHECK(Decode(stFixture, stMesh, stAnimation));
		mapInput["max"] = JsonValue::List{ 3.4028236e38 };
		ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh, stAnimation));
	}
}

ENGINE_NEXT_TEST("Animation frame maps independent nodes skins and M3 entities exactly once")
{
	Fixture stFixture;
	stFixture.mapRoot["nodes"].GetList()->emplace_back(JsonValue::Object{
			{ "mesh", std::int64_t{ 0 } }, { "skin", std::int64_t{ 1 } }, { "translation", JsonValue::List{ 9.0, 0.0, 0.0 } }, { "children", JsonValue::List{ std::int64_t{ 3 } } }, { "weights", JsonValue::List{ 0.25 } } });
	stFixture.mapRoot["nodes"].GetList()->emplace_back(JsonValue::Object{ { "translation", JsonValue::List{ 0.0, 4.0, 0.0 } } });
	stFixture.mapRoot["skins"].GetList()->emplace_back(JsonValue::Object{ { "joints", JsonValue::List{ std::int64_t{ 3 } } } });
	stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0, 0, 3, 0 });
	EngineNext::Rendering::RenderScene stScene;
	EngineNext::Rendering::RenderAsset stAsset;
	ENGINE_NEXT_CHECK(Decode(stFixture, stAsset.stMesh, stAsset.stAnimation));
	stAsset.bAnimated = true;
	stScene.arrAssets.push_back(std::move(stAsset));
	for (std::uint32_t nEntity = 0; nEntity < 2; ++nEntity)
	{
		for (std::uint32_t nInstance = 0; nInstance < 2; ++nInstance)
		{
			EngineNext::Rendering::RenderInstance stInstance;
			stInstance.nEntityId = nEntity + 1;
			stInstance.nNode = nInstance == 0 ? 0 : 2;
			stInstance.nMeshInstance = nInstance;
			stInstance.arrEntityTransform[12] = 100.0 * (nEntity + 1);
			stScene.arrInstances.push_back(stInstance);
		}
	}
	EngineNext::Rendering::AnimationPlayback stPlayback;
	stPlayback.bEnabled = true;
	EngineNext::Rendering::DeformationFrame stFrame;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildDeformationFrame(stScene, stPlayback, 1, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws.size(), std::size_t{ 4 });
	ENGINE_NEXT_CHECK_EQ(stFrame.nVertexCount, std::uint64_t{ 12 });
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[0].arrVertices[0].arrPosition[0], 1));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[0].arrVertices[0].arrPosition[1], 2));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[1].arrVertices[0].arrPosition[0], 0.5));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[1].arrVertices[0].arrPosition[1], 4));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[0].arrWorld[12], 105));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[1].arrWorld[12], 109));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[2].arrWorld[12], 205));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[3].arrWorld[12], 209));
	ENGINE_NEXT_CHECK(Near(stFrame.arrDraws[0].arrMinimum[1], 2));
	stScene.arrInstances[0].nMeshInstance = 99;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildDeformationFrame(stScene, stPlayback, 1.5, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK(Near(stFrame.dSeconds, 1));
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws.size(), std::size_t{ 4 });
}

ENGINE_NEXT_TEST("Animation playback rejects malformed fields without changing prior settings")
{
	using EngineNext::Rendering::AnimationPlayback;
	using EngineNext::Rendering::ParseAnimationPlayback;
	AnimationPlayback stPlayback;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(ParseAnimationPlayback(JsonValue::Object{ { "enabled", true }, { "clip", std::int64_t{ -1 } }, { "speed", -2.0 } }, stPlayback, arrDiagnostics));
	ENGINE_NEXT_CHECK(stPlayback.bEnabled && stPlayback.nClip == -1 && stPlayback.dSpeed == -2);
	for (const JsonValue &stInvalid : { JsonValue{ JsonValue::Object{ { "enabled", std::int64_t{ 1 } } } },
										JsonValue{ JsonValue::Object{ { "clip", std::int64_t{ -2 } } } }, JsonValue{ JsonValue::Object{ { "speed", "fast" } } },
										JsonValue{ JsonValue::Object{ { "unrecognized", true } } } })
	{
		ENGINE_NEXT_CHECK(!ParseAnimationPlayback(stInvalid, stPlayback, arrDiagnostics));
		ENGINE_NEXT_CHECK(stPlayback.bEnabled && stPlayback.nClip == -1 && stPlayback.dSpeed == -2);
	}
}

ENGINE_NEXT_TEST("Animated scene loader preserves source instances and rejects corrupted package transactionally")
{
	Fixture stFixture;
	stFixture.mapRoot["nodes"].GetList()->emplace_back(JsonValue::Object{
			{ "mesh", std::int64_t{ 0 } }, { "skin", std::int64_t{ 0 } }, { "translation", JsonValue::List{ 9.0, 0.0, 0.0 } } });
	stFixture.Animate("translation", "LINEAR", 3, { 0, 1, 0, 0, 3, 0 });
	const std::vector<std::uint8_t> arrBytes = stFixture.Bytes();
	const std::string strDigest = EngineNext::Serialization::Sha256Hex(arrBytes.data(), arrBytes.size());
	EngineNext::Assets::PackageData stPackage;
	stPackage.stScene.strSceneId = "animation.scene";
	stPackage.stScene.strSceneRevision = "r1";
	for (std::int64_t nEntity = 1; nEntity <= 2; ++nEntity)
	{
		EngineNext::Assets::SceneEntity stEntity;
		stEntity.nEntityId = nEntity;
		stEntity.strName = "Character" + std::to_string(nEntity);
		stEntity.strNodeType = "MeshInstance3D";
		stEntity.strGameplayKind = "static";
		stEntity.stTransform.arrTranslation[0] = 100.0 * nEntity;
		stEntity.arrAssets.push_back({ "mesh", { "animation.mesh", "r1", strDigest } });
		stPackage.stScene.arrEntities.push_back(stEntity);
	}
	std::string strSceneJson;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stPackage.stScene), strSceneJson));
	stPackage.stManifest.strSceneId = stPackage.stScene.strSceneId;
	stPackage.stManifest.strSceneRevision = stPackage.stScene.strSceneRevision;
	stPackage.stManifest.strSceneContentSha256 = EngineNext::Serialization::Sha256Hex(strSceneJson);
	EngineNext::Assets::AssetEntry stEntry;
	stEntry.strAssetId = "animation.mesh";
	stEntry.strRevision = "r1";
	stEntry.strType = "mesh";
	stEntry.strMediaType = "model/gltf-binary";
	stEntry.strContentSha256 = strDigest;
	stEntry.nByteSize = arrBytes.size();
	stEntry.stSource = { "executor_artifact", "animation.fixture", "r1", "" };
	stPackage.stManifest.arrAssets.push_back(stEntry);
	stPackage.mapBlobs[strDigest] = arrBytes;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ComputePackageDigest(stPackage, arrDiagnostics));
	EngineNext::Rendering::RenderScene stScene;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildAnimatedRenderScene(stPackage, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stScene.arrAssets.size(), std::size_t{ 1 });
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances.size(), std::size_t{ 4 });
	if (stScene.arrAssets.size() != 1 || stScene.arrInstances.size() != 4)
	{
		return;
	}
	ENGINE_NEXT_CHECK(stScene.arrAssets[0].bAnimated);
	ENGINE_NEXT_CHECK_EQ(stScene.arrAssets[0].stIdentity.strContentSha256, strDigest);
	for (std::size_t nInstance = 0; nInstance < stScene.arrInstances.size(); ++nInstance)
	{
		const EngineNext::Rendering::RenderInstance &stInstance = stScene.arrInstances[nInstance];
		ENGINE_NEXT_CHECK_EQ(stInstance.nMeshInstance, static_cast<std::uint32_t>(nInstance % 2));
		ENGINE_NEXT_CHECK_EQ(stInstance.arrEntityTransform[12], 100.0 * (nInstance / 2 + 1));
		ENGINE_NEXT_CHECK_EQ(stInstance.arrTransform[12], stInstance.arrEntityTransform[12] + (nInstance % 2 == 0 ? 5.0 : 9.0));
	}
	stPackage.mapBlobs[strDigest][0] ^= 1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildAnimatedRenderScene(stPackage, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances.size(), std::size_t{ 4 });
	ENGINE_NEXT_CHECK_EQ(stScene.arrAssets[0].stIdentity.strContentSha256, strDigest);
	ENGINE_NEXT_CHECK_EQ(stScene.strPackageDigest, stPackage.strPackageDigest);
}

ENGINE_NEXT_TEST("Deformation GI changes include old and new poses and skip paused geometry")
{
	using EngineNext::Rendering::BuildDeformationGeometryChanges;
	using EngineNext::Rendering::DeformationFrame;
	using EngineNext::Rendering::GiGeometryChange;
	EngineNext::Rendering::AnimationMatrix arrIdentity{};
	for (std::size_t nAxis = 0; nAxis < 4; ++nAxis)
	{
		arrIdentity[nAxis * 5] = 1;
	}
	std::vector<EngineNext::Rendering::AnimationMatrix> arrWorlds(2, arrIdentity);
	arrWorlds[1][0] = -2;
	arrWorlds[1][12] = 10;
	DeformationFrame stBefore;
	stBefore.arrDraws.resize(1);
	stBefore.arrDraws[0].nDraw = 1;
	stBefore.arrDraws[0].arrVertices.resize(1);
	stBefore.arrDraws[0].arrVertices[0].arrPosition = { 1, 2, 3 };
	DeformationFrame stAfter = stBefore;
	stAfter.arrDraws[0].arrVertices[0].arrPosition[0] = 2;
	std::vector<GiGeometryChange> arrChanges;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildDeformationGeometryChanges(stBefore, stAfter, arrWorlds, arrWorlds, arrChanges, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrChanges.size(), std::size_t{ 1 });
	ENGINE_NEXT_CHECK(arrChanges[0].stPreviousWorldBounds.arrMinimum[0] <= 8 && arrChanges[0].stPreviousWorldBounds.arrMaximum[0] >= 8);
	ENGINE_NEXT_CHECK(arrChanges[0].stCurrentWorldBounds.arrMinimum[0] <= 6 && arrChanges[0].stCurrentWorldBounds.arrMaximum[0] >= 6);
	ENGINE_NEXT_CHECK(BuildDeformationGeometryChanges(stBefore, stBefore, arrWorlds, arrWorlds, arrChanges, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrChanges.empty());
	std::vector<EngineNext::Rendering::AnimationMatrix> arrMoved = arrWorlds;
	arrMoved[1][12] = 11;
	ENGINE_NEXT_CHECK(BuildDeformationGeometryChanges(stAfter, stAfter, arrWorlds, arrMoved, arrChanges, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrChanges.size(), std::size_t{ 1 });
	ENGINE_NEXT_CHECK(arrChanges[0].stPreviousWorldBounds.arrMinimum[0] <= 6 && arrChanges[0].stPreviousWorldBounds.arrMaximum[0] >= 6);
	ENGINE_NEXT_CHECK(arrChanges[0].stCurrentWorldBounds.arrMinimum[0] <= 7 && arrChanges[0].stCurrentWorldBounds.arrMaximum[0] >= 7);
	stAfter.arrDraws[0].arrVertices[0].arrPosition[0] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(!BuildDeformationGeometryChanges(stBefore, stAfter, arrWorlds, arrWorlds, arrChanges, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrChanges.size(), std::size_t{ 1 });
	ENGINE_NEXT_CHECK(arrChanges[0].stCurrentWorldBounds.arrMinimum[0] <= 7 && arrChanges[0].stCurrentWorldBounds.arrMaximum[0] >= 7);
	stAfter = stBefore;
	stAfter.arrDraws[0].nDraw = 0;
	ENGINE_NEXT_CHECK(!BuildDeformationGeometryChanges(stBefore, stAfter, arrWorlds, arrWorlds, arrChanges, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrChanges.size(), std::size_t{ 1 });
}
