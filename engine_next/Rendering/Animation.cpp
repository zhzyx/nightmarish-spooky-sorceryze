/**************************************************************************/
/*  Animation.cpp                                                         */
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

#include "engine_next/include/EngineNext/Rendering/AnimationData.h"
#include "engine_next/Rendering/MeshBasis.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <set>
#include <utility>
#include <vector>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::size_t MAX_ITEMS = 65536;
constexpr std::size_t MAX_BYTES = 256ULL * 1024ULL * 1024ULL;
constexpr double MAX_COMPONENT = std::numeric_limits<float>::max();

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "animation_semantics", "$", pMessage);
	return false;
}

bool Charge(std::size_t nCount, std::size_t nSize, std::size_t &out_nBytes)
{
	if (nSize == 0 || nCount > (MAX_BYTES - out_nBytes) / nSize)
	{
		return false;
	}
	out_nBytes += nCount * nSize;
	return true;
}

AnimationMatrix Identity()
{
	return { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
}

bool Finite(double dValue)
{
	return std::isfinite(dValue) && std::abs(dValue) <= MAX_COMPONENT;
}

bool MatrixFinite(const AnimationMatrix &arrMatrix)
{
	for (double dValue : arrMatrix)
	{
		if (!Finite(dValue))
		{
			return false;
		}
	}
	return arrMatrix[3] == 0 && arrMatrix[7] == 0 && arrMatrix[11] == 0 && arrMatrix[15] == 1;
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

double Determinant(const AnimationMatrix &arrMatrix)
{
	return arrMatrix[0] * (arrMatrix[5] * arrMatrix[10] - arrMatrix[9] * arrMatrix[6]) -
			arrMatrix[4] * (arrMatrix[1] * arrMatrix[10] - arrMatrix[9] * arrMatrix[2]) +
			arrMatrix[8] * (arrMatrix[1] * arrMatrix[6] - arrMatrix[5] * arrMatrix[2]);
}

bool Inverse(const AnimationMatrix &arrMatrix, AnimationMatrix &out_arrInverse)
{
	if (!MatrixFinite(arrMatrix))
	{
		return false;
	}
	const double dDeterminant = Determinant(arrMatrix);
	if (!std::isfinite(dDeterminant) || dDeterminant == 0)
	{
		return false;
	}
	out_arrInverse = Identity();
	for (std::size_t nColumn = 0; nColumn < 3; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < 3; ++nRow)
		{
			const std::size_t nRow1 = (nColumn + 1) % 3;
			const std::size_t nRow2 = (nColumn + 2) % 3;
			const std::size_t nColumn1 = (nRow + 1) % 3;
			const std::size_t nColumn2 = (nRow + 2) % 3;
			out_arrInverse[nColumn * 4 + nRow] =
					(arrMatrix[nColumn1 * 4 + nRow1] * arrMatrix[nColumn2 * 4 + nRow2] -
					 arrMatrix[nColumn2 * 4 + nRow1] * arrMatrix[nColumn1 * 4 + nRow2]) /
					dDeterminant;
		}
	}
	for (std::size_t nRow = 0; nRow < 3; ++nRow)
	{
		out_arrInverse[12 + nRow] = -(out_arrInverse[nRow] * arrMatrix[12] + out_arrInverse[4 + nRow] * arrMatrix[13] + out_arrInverse[8 + nRow] * arrMatrix[14]);
	}
	return MatrixFinite(out_arrInverse);
}

template <std::size_t N>
bool Normalize(std::array<double, N> &out_arrVector)
{
	double dScale = 0;
	for (double dValue : out_arrVector)
	{
		if (!std::isfinite(dValue))
		{
			return false;
		}
		dScale = (std::max)(dScale, std::abs(dValue));
	}
	if (dScale == 0)
	{
		return false;
	}
	double dLength = 0;
	for (double &dValue : out_arrVector)
	{
		dValue /= dScale;
		dLength += dValue * dValue;
	}
	dLength = std::sqrt(dLength);
	for (double &dValue : out_arrVector)
	{
		dValue /= dLength;
	}
	return true;
}

bool Compose(const Assets::Transform &stTransform, AnimationMatrix &out_arrMatrix)
{
	for (double dValue : stTransform.arrTranslation)
	{
		if (!Finite(dValue))
		{
			return false;
		}
	}
	for (double dValue : stTransform.arrScale)
	{
		if (!Finite(dValue))
		{
			return false;
		}
	}
	double dNorm = 0;
	for (double dValue : stTransform.arrRotation)
	{
		if (!Finite(dValue))
		{
			return false;
		}
		dNorm += dValue * dValue;
	}
	if (std::abs(dNorm - 1) > 1.0e-4)
	{
		return false;
	}
	const double dX = stTransform.arrRotation[0];
	const double dY = stTransform.arrRotation[1];
	const double dZ = stTransform.arrRotation[2];
	const double dW = stTransform.arrRotation[3];
	out_arrMatrix = { (1 - 2 * (dY * dY + dZ * dZ)) * stTransform.arrScale[0], 2 * (dX * dY + dZ * dW) * stTransform.arrScale[0], 2 * (dX * dZ - dY * dW) * stTransform.arrScale[0], 0,
					  2 * (dX * dY - dZ * dW) * stTransform.arrScale[1], (1 - 2 * (dX * dX + dZ * dZ)) * stTransform.arrScale[1], 2 * (dY * dZ + dX * dW) * stTransform.arrScale[1], 0,
					  2 * (dX * dZ + dY * dW) * stTransform.arrScale[2], 2 * (dY * dZ - dX * dW) * stTransform.arrScale[2], (1 - 2 * (dX * dX + dY * dY)) * stTransform.arrScale[2], 0,
					  stTransform.arrTranslation[0], stTransform.arrTranslation[1], stTransform.arrTranslation[2], 1 };
	return MatrixFinite(out_arrMatrix);
}

bool World(std::size_t nNode, std::size_t nDepth, const std::vector<AnimationNode> &arrNodes,
		   const std::vector<Assets::Transform> &arrTransforms, std::vector<std::uint8_t> &out_arrState, std::vector<std::size_t> &out_arrDepth, AnimationPose &out_stPose)
{
	if (nDepth > 128 || out_arrState[nNode] == 1)
	{
		return false;
	}
	if (out_arrState[nNode] == 2)
	{
		return nDepth + out_arrDepth[nNode] <= 128;
	}
	out_arrState[nNode] = 1;
	const AnimationNode &stNode = arrNodes[nNode];
	AnimationMatrix arrLocal = stNode.arrMatrix;
	if ((!stNode.bMatrix && !Compose(arrTransforms[nNode], arrLocal)) || !MatrixFinite(arrLocal))
	{
		return false;
	}
	if (stNode.nParent >= 0)
	{
		const std::size_t nParent = static_cast<std::size_t>(stNode.nParent);
		if (nParent >= arrNodes.size() || !World(nParent, nDepth + 1, arrNodes, arrTransforms, out_arrState, out_arrDepth, out_stPose))
		{
			return false;
		}
		out_arrDepth[nNode] = out_arrDepth[nParent] + 1;
		if (out_arrDepth[nNode] > 128)
		{
			return false;
		}
		arrLocal = Multiply(out_stPose.arrWorldTransforms[nParent], arrLocal);
	}
	else if (stNode.nParent != -1)
	{
		return false;
	}
	if (!MatrixFinite(arrLocal))
	{
		return false;
	}
	out_stPose.arrWorldTransforms[nNode] = arrLocal;
	out_arrState[nNode] = 2;
	return true;
}

bool ValidateChannel(const AnimationChannel &stChannel, const std::vector<AnimationNode> &arrNodes, std::size_t &out_nBytes)
{
	if (stChannel.nNode >= arrNodes.size() || (arrNodes[stChannel.nNode].bMatrix && stChannel.eProperty != AnimationProperty::Weights) || stChannel.arrTimes.empty() ||
		(stChannel.eInterpolation == AnimationInterpolation::CubicSpline && stChannel.arrTimes.size() < 2) || stChannel.arrTimes.size() > MAX_ITEMS || stChannel.eInterpolation > AnimationInterpolation::CubicSpline || stChannel.eProperty > AnimationProperty::Weights)
	{
		return false;
	}
	const std::size_t nComponents = stChannel.eProperty == AnimationProperty::Weights ? arrNodes[stChannel.nNode].arrWeights.size() : stChannel.eProperty == AnimationProperty::Rotation ? 4
																																														 : 3;
	const std::size_t nFactor = stChannel.eInterpolation == AnimationInterpolation::CubicSpline ? 3 : 1;
	if (nComponents == 0 || nComponents > MAX_ITEMS || nComponents != stChannel.nComponents ||
		stChannel.arrTimes.size() > MAX_BYTES / sizeof(double) / nFactor / nComponents ||
		stChannel.arrValues.size() != stChannel.arrTimes.size() * nFactor * nComponents ||
		!Charge(stChannel.arrValues.size(), sizeof(double), out_nBytes) || !Charge(stChannel.arrTimes.size(), sizeof(double), out_nBytes))
	{
		return false;
	}
	double dPrevious = -1;
	for (double dTime : stChannel.arrTimes)
	{
		if (!Finite(dTime) || dTime < 0 || dTime <= dPrevious)
		{
			return false;
		}
		dPrevious = dTime;
	}
	for (double dValue : stChannel.arrValues)
	{
		if (!Finite(dValue))
		{
			return false;
		}
	}
	if (stChannel.eProperty == AnimationProperty::Rotation)
	{
		for (std::size_t nKey = 0; nKey < stChannel.arrTimes.size(); ++nKey)
		{
			const std::size_t nOffset = (nKey * nFactor + (nFactor == 3 ? 1 : 0)) * 4;
			double dLength = 0;
			for (std::size_t nComponent = 0; nComponent < 4; ++nComponent)
			{
				dLength += stChannel.arrValues[nOffset + nComponent] * stChannel.arrValues[nOffset + nComponent];
			}
			if (std::abs(dLength - 1) > 1.0e-4)
			{
				return false;
			}
		}
	}
	return true;
}

bool Sample(const AnimationChannel &stChannel, double dTime, std::vector<double> &out_arrValue)
{
	const std::size_t nComponents = stChannel.nComponents;
	const std::size_t nFactor = stChannel.eInterpolation == AnimationInterpolation::CubicSpline ? 3 : 1;
	const std::vector<double>::const_iterator itUpper = std::upper_bound(stChannel.arrTimes.begin(), stChannel.arrTimes.end(), dTime);
	const std::size_t nRight = static_cast<std::size_t>(itUpper - stChannel.arrTimes.begin());
	const std::size_t nLeft = nRight == 0 ? 0 : nRight - 1;
	const bool bEndpoint = nRight == 0 || nRight == stChannel.arrTimes.size();
	const std::size_t nOffset = (nLeft * nFactor + (nFactor == 3 ? 1 : 0)) * nComponents;
	out_arrValue.assign(stChannel.arrValues.begin() + static_cast<std::ptrdiff_t>(nOffset), stChannel.arrValues.begin() + static_cast<std::ptrdiff_t>(nOffset + nComponents));
	if (bEndpoint || stChannel.eInterpolation == AnimationInterpolation::Step)
	{
		return true;
	}
	const double dSpan = stChannel.arrTimes[nRight] - stChannel.arrTimes[nLeft];
	const double dAlpha = (dTime - stChannel.arrTimes[nLeft]) / dSpan;
	const std::size_t nNext = (nRight * nFactor + (nFactor == 3 ? 1 : 0)) * nComponents;
	if (stChannel.eInterpolation == AnimationInterpolation::Linear && stChannel.eProperty == AnimationProperty::Rotation)
	{
		double dDot = 0;
		for (std::size_t nComponent = 0; nComponent < 4; ++nComponent)
		{
			dDot += out_arrValue[nComponent] * stChannel.arrValues[nNext + nComponent];
		}
		const double dSign = dDot < 0 ? -1 : 1;
		dDot = (std::min)(1.0, std::abs(dDot));
		const double dAngle = std::acos(dDot);
		const double dDenominator = std::sin(dAngle);
		const double dLeft = dDot > 0.9995 ? 1 - dAlpha : std::sin((1 - dAlpha) * dAngle) / dDenominator;
		const double dRight = dDot > 0.9995 ? dAlpha : std::sin(dAlpha * dAngle) / dDenominator;
		for (std::size_t nComponent = 0; nComponent < 4; ++nComponent)
		{
			out_arrValue[nComponent] = dLeft * out_arrValue[nComponent] + dRight * dSign * stChannel.arrValues[nNext + nComponent];
		}
	}
	else
	{
		for (std::size_t nComponent = 0; nComponent < nComponents; ++nComponent)
		{
			const double dStart = out_arrValue[nComponent];
			const double dEnd = stChannel.arrValues[nNext + nComponent];
			if (nFactor == 3)
			{
				const double dSquared = dAlpha * dAlpha;
				const double dCubed = dSquared * dAlpha;
				out_arrValue[nComponent] = (2 * dCubed - 3 * dSquared + 1) * dStart +
						(dCubed - 2 * dSquared + dAlpha) * dSpan * stChannel.arrValues[nOffset + nComponents + nComponent] +
						(-2 * dCubed + 3 * dSquared) * dEnd + (dCubed - dSquared) * dSpan * stChannel.arrValues[nNext - nComponents + nComponent];
			}
			else
			{
				out_arrValue[nComponent] = (1 - dAlpha) * dStart + dAlpha * dEnd;
			}
		}
	}
	if (stChannel.eProperty == AnimationProperty::Rotation)
	{
		std::array<double, 4> arrRotation{ out_arrValue[0], out_arrValue[1], out_arrValue[2], out_arrValue[3] };
		if (!Normalize(arrRotation))
		{
			return false;
		}
		std::copy(arrRotation.begin(), arrRotation.end(), out_arrValue.begin());
	}
	return std::all_of(out_arrValue.begin(), out_arrValue.end(), Finite);
}
} // namespace

bool EvaluateAnimation(const AnimationData &stAnimation, std::int32_t nClip, double dTimeSeconds, bool bLoop,
					   AnimationPose &out_stPose, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!std::isfinite(dTimeSeconds) || nClip < -1 || nClip >= static_cast<std::int64_t>(stAnimation.arrClips.size()) || stAnimation.arrNodes.size() > MAX_ITEMS || stAnimation.arrClips.size() > MAX_ITEMS)
	{
		return Fail(out_arrDiagnostics, "Invalid clip, time, or node budget.");
	}
	std::size_t nBytes = 0;
	if (!Charge(stAnimation.arrNodes.size(), sizeof(AnimationNode) + sizeof(Assets::Transform) + sizeof(AnimationMatrix), nBytes))
	{
		return Fail(out_arrDiagnostics, "Pose budget exceeded.");
	}
	AnimationPose stResult;
	stResult.arrWorldTransforms.resize(stAnimation.arrNodes.size());
	std::vector<Assets::Transform> arrTransforms;
	for (const AnimationNode &stNode : stAnimation.arrNodes)
	{
		if (stNode.arrWeights.size() > MAX_ITEMS || !Charge(stNode.arrWeights.size(), sizeof(double), nBytes) || !std::all_of(stNode.arrWeights.begin(), stNode.arrWeights.end(), Finite))
		{
			return Fail(out_arrDiagnostics, "Invalid morph weights or pose budget.");
		}
		arrTransforms.push_back(stNode.stTransform);
		stResult.arrWeights.push_back(stNode.arrWeights);
	}
	if (nClip >= 0)
	{
		const AnimationClip &stClip = stAnimation.arrClips[static_cast<std::size_t>(nClip)];
		if (stClip.arrChannels.empty() || stClip.arrChannels.size() > MAX_ITEMS)
		{
			return Fail(out_arrDiagnostics, "Channel budget exceeded.");
		}
		std::set<std::pair<std::uint32_t, AnimationProperty>> setTargets;
		double dFirst = std::numeric_limits<double>::max();
		double dLast = 0;
		for (const AnimationChannel &stChannel : stClip.arrChannels)
		{
			if (!ValidateChannel(stChannel, stAnimation.arrNodes, nBytes) || !setTargets.emplace(stChannel.nNode, stChannel.eProperty).second)
			{
				return Fail(out_arrDiagnostics, "Invalid animation channel or duplicate target.");
			}
			dFirst = (std::min)(dFirst, stChannel.arrTimes.front());
			dLast = (std::max)(dLast, stChannel.arrTimes.back());
		}
		if (bLoop && dLast > dFirst)
		{
			const double dDuration = dLast - dFirst;
			// Reduce before subtracting so a large playback time retains the
			// phase relative to a nonzero first key.
			dTimeSeconds = std::fmod(std::fmod(dTimeSeconds, dDuration) - std::fmod(dFirst, dDuration), dDuration);
			if (dTimeSeconds < 0)
			{
				dTimeSeconds += dDuration;
			}
			dTimeSeconds += dFirst;
		}
		for (const AnimationChannel &stChannel : stClip.arrChannels)
		{
			std::vector<double> arrValue;
			if (!Sample(stChannel, dTimeSeconds, arrValue))
			{
				return Fail(out_arrDiagnostics, "Animation sample is singular or exceeds numeric range.");
			}
			Assets::Transform &stTransform = arrTransforms[stChannel.nNode];
			switch (stChannel.eProperty)
			{
				case AnimationProperty::Translation:
					std::copy(arrValue.begin(), arrValue.end(), stTransform.arrTranslation.begin());
					break;
				case AnimationProperty::Rotation:
					std::copy(arrValue.begin(), arrValue.end(), stTransform.arrRotation.begin());
					break;
				case AnimationProperty::Scale:
					std::copy(arrValue.begin(), arrValue.end(), stTransform.arrScale.begin());
					break;
				case AnimationProperty::Weights:
					stResult.arrWeights[stChannel.nNode] = std::move(arrValue);
					break;
			}
		}
	}
	std::vector<std::uint8_t> arrState(stAnimation.arrNodes.size(), 0);
	std::vector<std::size_t> arrDepth(stAnimation.arrNodes.size(), 0);
	for (std::size_t nNode = 0; nNode < stAnimation.arrNodes.size(); ++nNode)
	{
		if (!World(nNode, 0, stAnimation.arrNodes, arrTransforms, arrState, arrDepth, stResult))
		{
			return Fail(out_arrDiagnostics, "Invalid transform or node hierarchy.");
		}
	}
	out_stPose = std::move(stResult);
	return true;
}

bool DeformAnimation(const DecodedMesh &stMesh, const AnimationData &stAnimation, const AnimationPose &stPose,
					 std::vector<DeformedInstance> &out_arrInstances, Assets::Diagnostics &out_arrDiagnostics)
{
	if (stAnimation.arrPrimitives.size() != stMesh.arrPrimitives.size() || stPose.arrWorldTransforms.size() != stAnimation.arrNodes.size() ||
		stPose.arrWeights.size() != stAnimation.arrNodes.size() || stMesh.arrInstances.size() > MAX_ITEMS)
	{
		return Fail(out_arrDiagnostics, "Mesh, deformation and pose dimensions differ.");
	}
	std::size_t nBytes = 0;
	if (!Charge(stMesh.arrInstances.size(), sizeof(DeformedInstance), nBytes))
	{
		return Fail(out_arrDiagnostics, "Instance output budget exceeded.");
	}
	std::vector<DeformedInstance> arrResult;
	arrResult.reserve(stMesh.arrInstances.size());
	for (std::size_t nInstance = 0; nInstance < stMesh.arrInstances.size(); ++nInstance)
	{
		const MeshInstance &stInstance = stMesh.arrInstances[nInstance];
		if (stInstance.nPrimitive >= stMesh.arrPrimitives.size() || stInstance.nNode >= stAnimation.arrNodes.size() || !MatrixFinite(stPose.arrWorldTransforms[stInstance.nNode]))
		{
			return Fail(out_arrDiagnostics, "Instance references invalid primitive, node or transform.");
		}
		const MeshPrimitive &stPrimitive = stMesh.arrPrimitives[stInstance.nPrimitive];
		const PrimitiveDeformation &stDeformation = stAnimation.arrPrimitives[stInstance.nPrimitive];
		const AnimationNode &stNode = stAnimation.arrNodes[stInstance.nNode];
		const std::vector<double> &arrWeights = stPose.arrWeights[stInstance.nNode];
		if (arrWeights.size() != stDeformation.arrMorphTargets.size() ||
			(!stDeformation.arrInfluences.empty() && stDeformation.arrInfluences.size() != stPrimitive.arrVertices.size()) ||
			!Charge(stPrimitive.arrVertices.size(), sizeof(MeshVertex), nBytes))
		{
			return Fail(out_arrDiagnostics, "Invalid morph, influence or output budget.");
		}
		for (const MorphTarget &stTarget : stDeformation.arrMorphTargets)
		{
			for (const std::vector<std::array<float, 3>> *pValues : { &stTarget.arrPositions, &stTarget.arrNormals, &stTarget.arrTangents })
			{
				if (!pValues->empty() && pValues->size() != stPrimitive.arrVertices.size())
				{
					return Fail(out_arrDiagnostics, "Morph target vertex count differs.");
				}
			}
		}
		std::vector<AnimationMatrix> arrPalette;
		if (stNode.nSkin >= 0)
		{
			AnimationMatrix arrInverse;
			if (stNode.nSkin >= static_cast<std::int64_t>(stAnimation.arrSkins.size()) || stDeformation.arrInfluences.empty() || !Inverse(stPose.arrWorldTransforms[stInstance.nNode], arrInverse))
			{
				return Fail(out_arrDiagnostics, "Invalid skin binding or singular mesh transform.");
			}
			const SkinData &stSkin = stAnimation.arrSkins[static_cast<std::size_t>(stNode.nSkin)];
			if (stSkin.arrJoints.empty() || stSkin.arrJoints.size() > MAX_ITEMS || stSkin.arrJoints.size() != stSkin.arrInverseBindMatrices.size())
			{
				return Fail(out_arrDiagnostics, "Invalid skin palette dimensions.");
			}
			arrPalette.reserve(stSkin.arrJoints.size());
			for (std::size_t nJoint = 0; nJoint < stSkin.arrJoints.size(); ++nJoint)
			{
				const std::uint32_t nNode = stSkin.arrJoints[nJoint];
				if (nNode >= stPose.arrWorldTransforms.size() || !MatrixFinite(stSkin.arrInverseBindMatrices[nJoint]))
				{
					return Fail(out_arrDiagnostics, "Invalid joint or inverse bind matrix.");
				}
				const AnimationMatrix arrMatrix = Multiply(Multiply(arrInverse, stPose.arrWorldTransforms[nNode]), stSkin.arrInverseBindMatrices[nJoint]);
				if (!MatrixFinite(arrMatrix))
				{
					return Fail(out_arrDiagnostics, "Joint palette exceeds numeric range.");
				}
				arrPalette.push_back(arrMatrix);
			}
		}
		else if (stNode.nSkin != -1)
		{
			return Fail(out_arrDiagnostics, "Invalid skin index.");
		}
		DeformedInstance stOutput;
		stOutput.nInstance = static_cast<std::uint32_t>(nInstance);
		stOutput.arrTransform = stPose.arrWorldTransforms[stInstance.nNode];
		stOutput.arrVertices = stPrimitive.arrVertices;
		for (std::size_t nVertex = 0; nVertex < stOutput.arrVertices.size(); ++nVertex)
		{
			MeshVertex &stVertex = stOutput.arrVertices[nVertex];
			std::array<double, 3> arrPosition{ stVertex.arrPosition[0], stVertex.arrPosition[1], stVertex.arrPosition[2] };
			std::array<double, 3> arrNormal{ stVertex.arrNormal[0], stVertex.arrNormal[1], stVertex.arrNormal[2] };
			std::array<double, 3> arrTangent{ stVertex.arrTangent[0], stVertex.arrTangent[1], stVertex.arrTangent[2] };
			for (std::size_t nTarget = 0; nTarget < arrWeights.size(); ++nTarget)
			{
				const MorphTarget &stTarget = stDeformation.arrMorphTargets[nTarget];
				if (!Finite(arrWeights[nTarget]))
				{
					return Fail(out_arrDiagnostics, "Invalid morph weight.");
				}
				for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
				{
					arrPosition[nAxis] += stTarget.arrPositions.empty() ? 0 : arrWeights[nTarget] * stTarget.arrPositions[nVertex][nAxis];
					arrNormal[nAxis] += stTarget.arrNormals.empty() ? 0 : arrWeights[nTarget] * stTarget.arrNormals[nVertex][nAxis];
					arrTangent[nAxis] += stTarget.arrTangents.empty() ? 0 : arrWeights[nTarget] * stTarget.arrTangents[nVertex][nAxis];
				}
			}
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				if (!Finite(arrPosition[nAxis]) || !Finite(arrNormal[nAxis]) || !Finite(arrTangent[nAxis]))
				{
					return Fail(out_arrDiagnostics, "Morph output exceeds numeric range.");
				}
				stVertex.arrPosition[nAxis] = static_cast<float>(arrPosition[nAxis]);
				stVertex.arrNormal[nAxis] = static_cast<float>(arrNormal[nAxis]);
				stVertex.arrTangent[nAxis] = static_cast<float>(arrTangent[nAxis]);
			}
		}
		if (stDeformation.bGenerateNormals || stDeformation.bGenerateTangents)
		{
			if (!Charge(stOutput.arrVertices.size(), 3 * sizeof(std::array<double, 3>), nBytes))
			{
				return Fail(out_arrDiagnostics, "Basis scratch budget exceeded.");
			}
			if (stPrimitive.arrIndices.empty() || stPrimitive.arrIndices.size() % 3 != 0 || !Charge(stPrimitive.arrIndices.size(), sizeof(std::uint32_t), nBytes))
			{
				return Fail(out_arrDiagnostics, "Invalid basis index data or budget.");
			}
			for (std::uint32_t nIndex : stPrimitive.arrIndices)
			{
				if (nIndex >= stOutput.arrVertices.size())
				{
					return Fail(out_arrDiagnostics, "Basis index exceeds vertex data.");
				}
			}
			MeshPrimitive stMorphed;
			stMorphed.arrVertices = std::move(stOutput.arrVertices);
			stMorphed.arrIndices = stPrimitive.arrIndices;
			if (!BuildMeshBasis(stMorphed, stDeformation.bGenerateNormals, true, true, out_arrDiagnostics, "$.deformed_basis"))
			{
				return false;
			}
			stOutput.arrVertices = std::move(stMorphed.arrVertices);
		}

		for (std::size_t nVertex = 0; nVertex < stPrimitive.arrVertices.size(); ++nVertex)
		{
			MeshVertex &stVertex = stOutput.arrVertices[nVertex];
			if (!Finite(stVertex.arrTexcoord[0]) || !Finite(stVertex.arrTexcoord[1]))
			{
				return Fail(out_arrDiagnostics, "Invalid vertex texture coordinate.");
			}
			std::array<double, 3> arrPosition{ stVertex.arrPosition[0], stVertex.arrPosition[1], stVertex.arrPosition[2] };
			std::array<double, 3> arrNormal{ stVertex.arrNormal[0], stVertex.arrNormal[1], stVertex.arrNormal[2] };
			std::array<double, 3> arrTangent{ stVertex.arrTangent[0], stVertex.arrTangent[1], stVertex.arrTangent[2] };

			AnimationMatrix arrSkin = Identity();
			if (!arrPalette.empty())
			{
				arrSkin.fill(0);
				const SkinInfluence &stInfluence = stDeformation.arrInfluences[nVertex];
				double dTotal = 0;
				for (std::size_t nWeight = 0; nWeight < 4; ++nWeight)
				{
					const double dWeight = stInfluence.arrWeights[nWeight];
					if (!Finite(dWeight) || dWeight < 0 || stInfluence.arrJoints[nWeight] >= arrPalette.size())
					{
						return Fail(out_arrDiagnostics, "Invalid vertex joint or weight.");
					}
					dTotal += dWeight;
					for (std::size_t nElement = 0; nElement < 16; ++nElement)
					{
						arrSkin[nElement] += dWeight * arrPalette[stInfluence.arrJoints[nWeight]][nElement];
					}
				}
				if (dTotal <= 0)
				{
					return Fail(out_arrDiagnostics, "Skin weights have no positive sum.");
				}
				for (double &dElement : arrSkin)
				{
					dElement /= dTotal;
				}
				arrSkin[3] = arrSkin[7] = arrSkin[11] = 0;
				arrSkin[15] = 1;
			}
			AnimationMatrix arrInverse;
			if (!Inverse(arrSkin, arrInverse))
			{
				return Fail(out_arrDiagnostics, "Blended skin matrix is singular.");
			}
			std::array<double, 3> arrDeformedNormal{};
			std::array<double, 3> arrDeformedTangent{};
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				const double dValue = arrSkin[nAxis] * arrPosition[0] + arrSkin[4 + nAxis] * arrPosition[1] + arrSkin[8 + nAxis] * arrPosition[2] + arrSkin[12 + nAxis];
				if (!Finite(dValue))
				{
					return Fail(out_arrDiagnostics, "Deformed position exceeds numeric range.");
				}
				stVertex.arrPosition[nAxis] = static_cast<float>(dValue);
				for (std::size_t nInner = 0; nInner < 3; ++nInner)
				{
					arrDeformedNormal[nAxis] += arrInverse[nAxis * 4 + nInner] * arrNormal[nInner];
					arrDeformedTangent[nAxis] += arrSkin[nInner * 4 + nAxis] * arrTangent[nInner];
				}
			}
			if (!Normalize(arrDeformedNormal))
			{
				return Fail(out_arrDiagnostics, "Deformed normal is singular.");
			}
			double dDot = 0;
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				dDot += arrDeformedNormal[nAxis] * arrDeformedTangent[nAxis];
			}
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrDeformedTangent[nAxis] -= arrDeformedNormal[nAxis] * dDot;
			}
			if (!Normalize(arrDeformedTangent) || (stVertex.arrTangent[3] != -1 && stVertex.arrTangent[3] != 1))
			{
				return Fail(out_arrDiagnostics, "Deformed tangent is singular.");
			}
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				stVertex.arrNormal[nAxis] = static_cast<float>(arrDeformedNormal[nAxis]);
				stVertex.arrTangent[nAxis] = static_cast<float>(arrDeformedTangent[nAxis]);
			}
			stVertex.arrTangent[3] *= Determinant(arrSkin) < 0 ? -1.0F : 1.0F;
		}
		arrResult.push_back(std::move(stOutput));
	}
	out_arrInstances = std::move(arrResult);
	return true;
}
} // namespace EngineNext::Rendering
