/**************************************************************************/
/*  MeshBasis.cpp                                                         */
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

#include "engine_next/Rendering/MeshBasis.h"
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>
namespace EngineNext::Rendering
{
namespace
{
bool BasisError(Assets::Diagnostics &out_arrDiagnostics, const std::string &strContext, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "gltf_render_semantics", strContext, pMessage);
	return false;
}
bool Normalize(std::array<float, 3> &out_arrVector)
{
	const double dLength = std::sqrt(static_cast<double>(out_arrVector[0]) * out_arrVector[0] +
									 static_cast<double>(out_arrVector[1]) * out_arrVector[1] + static_cast<double>(out_arrVector[2]) * out_arrVector[2]);
	if (!std::isfinite(dLength) || dLength < 1.0e-20)
	{
		return false;
	}
	for (float &fValue : out_arrVector)
	{
		fValue = static_cast<float>(fValue / dLength);
	}
	return true;
}

} //namespace
bool BuildMeshBasis(MeshPrimitive &out_stPrimitive, bool bNormals, bool bTangents, bool bTexcoord, Assets::Diagnostics &out_arrDiagnostics, const std::string &strContext)
{
	std::vector<std::array<double, 3>> arrNormals(out_stPrimitive.arrVertices.size());
	std::vector<std::array<double, 3>> arrTangents(out_stPrimitive.arrVertices.size());
	std::vector<std::array<double, 3>> arrBitangents(out_stPrimitive.arrVertices.size());
	for (std::size_t nIndex = 0; nIndex < out_stPrimitive.arrIndices.size(); nIndex += 3)
	{
		const MeshVertex &stA = out_stPrimitive.arrVertices[out_stPrimitive.arrIndices[nIndex]];
		const MeshVertex &stB = out_stPrimitive.arrVertices[out_stPrimitive.arrIndices[nIndex + 1]];
		const MeshVertex &stC = out_stPrimitive.arrVertices[out_stPrimitive.arrIndices[nIndex + 2]];
		std::array<double, 3> arrEdge1{};
		std::array<double, 3> arrEdge2{};
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrEdge1[nAxis] = static_cast<double>(stB.arrPosition[nAxis]) - stA.arrPosition[nAxis];
			arrEdge2[nAxis] = static_cast<double>(stC.arrPosition[nAxis]) - stA.arrPosition[nAxis];
		}
		const std::array<double, 3> arrNormal{ arrEdge1[1] * arrEdge2[2] - arrEdge1[2] * arrEdge2[1], arrEdge1[2] * arrEdge2[0] - arrEdge1[0] * arrEdge2[2], arrEdge1[0] * arrEdge2[1] - arrEdge1[1] * arrEdge2[0] };
		const double dU1 = static_cast<double>(stB.arrTexcoord[0]) - stA.arrTexcoord[0];
		const double dV1 = static_cast<double>(stB.arrTexcoord[1]) - stA.arrTexcoord[1];
		const double dU2 = static_cast<double>(stC.arrTexcoord[0]) - stA.arrTexcoord[0];
		const double dV2 = static_cast<double>(stC.arrTexcoord[1]) - stA.arrTexcoord[1];
		const double dDeterminant = dU1 * dV2 - dU2 * dV1;
		for (std::size_t nCorner = 0; nCorner < 3; ++nCorner)
		{
			const std::uint32_t nVertex = out_stPrimitive.arrIndices[nIndex + nCorner];
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrNormals[nVertex][nAxis] += arrNormal[nAxis];
				if (bTexcoord && std::abs(dDeterminant) > 1.0e-20)
				{
					arrTangents[nVertex][nAxis] += (arrEdge1[nAxis] * dV2 - arrEdge2[nAxis] * dV1) / dDeterminant;
					arrBitangents[nVertex][nAxis] += (arrEdge2[nAxis] * dU1 - arrEdge1[nAxis] * dU2) / dDeterminant;
				}
			}
		}
	}
	for (std::size_t nIndex = 0; nIndex < out_stPrimitive.arrVertices.size(); ++nIndex)
	{
		MeshVertex &stVertex = out_stPrimitive.arrVertices[nIndex];
		if (bNormals)
		{
			const double dLength = std::sqrt(arrNormals[nIndex][0] * arrNormals[nIndex][0] + arrNormals[nIndex][1] * arrNormals[nIndex][1] + arrNormals[nIndex][2] * arrNormals[nIndex][2]);
			if (dLength > 1.0e-20 && std::isfinite(dLength))
			{
				for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
				{
					stVertex.arrNormal[nAxis] = static_cast<float>(arrNormals[nIndex][nAxis] / dLength);
				}
			}
		}
		if (!Normalize(stVertex.arrNormal))
		{
			return BasisError(out_arrDiagnostics, strContext, "Normal has zero length.");
		}
		std::array<float, 3> arrTangent{ stVertex.arrTangent[0], stVertex.arrTangent[1], stVertex.arrTangent[2] };
		if (bTangents)
		{
			const double dLength = std::sqrt(arrTangents[nIndex][0] * arrTangents[nIndex][0] + arrTangents[nIndex][1] * arrTangents[nIndex][1] + arrTangents[nIndex][2] * arrTangents[nIndex][2]);
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrTangent[nAxis] = dLength > 1.0e-20 && std::isfinite(dLength) ? static_cast<float>(arrTangents[nIndex][nAxis] / dLength) : 0.0F;
			}
		}
		const float fDot = arrTangent[0] * stVertex.arrNormal[0] + arrTangent[1] * stVertex.arrNormal[1] + arrTangent[2] * stVertex.arrNormal[2];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrTangent[nAxis] -= fDot * stVertex.arrNormal[nAxis];
		}
		if (!Normalize(arrTangent))
		{
			if (!bTangents)
			{
				return BasisError(out_arrDiagnostics, strContext, "Tangent is parallel to the normal or has zero length.");
			}
			arrTangent = std::abs(stVertex.arrNormal[0]) < 0.9F ? std::array<float, 3>{ 1, 0, 0 } : std::array<float, 3>{ 0, 1, 0 };
			const float fProjection = arrTangent[0] * stVertex.arrNormal[0] + arrTangent[1] * stVertex.arrNormal[1] + arrTangent[2] * stVertex.arrNormal[2];
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrTangent[nAxis] -= fProjection * stVertex.arrNormal[nAxis];
			}
			(void)Normalize(arrTangent);
		}
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			stVertex.arrTangent[nAxis] = arrTangent[nAxis];
		}
		if (bTangents)
		{
			const std::array<float, 3> &arrNormal = stVertex.arrNormal;
			const double dHandedness = (arrNormal[1] * arrTangent[2] - arrNormal[2] * arrTangent[1]) * arrBitangents[nIndex][0] +
					(arrNormal[2] * arrTangent[0] - arrNormal[0] * arrTangent[2]) * arrBitangents[nIndex][1] + (arrNormal[0] * arrTangent[1] - arrNormal[1] * arrTangent[0]) * arrBitangents[nIndex][2];
			stVertex.arrTangent[3] = dHandedness < 0 ? -1.0F : 1.0F;
		}
	}
	return true;
}
} //namespace EngineNext::Rendering
