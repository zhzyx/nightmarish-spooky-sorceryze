/**************************************************************************/
/*  EnvironmentLighting.cpp                                               */
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

#include "engine_next/Rendering/Cook/EnvironmentLighting.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

using Vector = std::array<float, 3>;
constexpr float PI = 3.14159265358979323846F;
constexpr std::uint32_t MAX_SIZE = 256;
constexpr std::uint32_t MAX_SAMPLES = 1024;
constexpr std::uint64_t MAX_INTEGRATION_SAMPLES = 64000000;
constexpr double DOUBLE_PI = 3.14159265358979323846;
// Gauss-Legendre nodes and weights mapped to [0,1]. The procedural sky and
// soft sun are axisymmetric, so their azimuth integrals are analytic.
constexpr std::array<std::array<double, 2>, 32> IRRADIANCE_QUADRATURE{ {
		{ 0.0013680690752592151, 0.0035093050047352529 },
		{ 0.0071942442273658092, 0.0081371973654528716 },
		{ 0.017618872206246805, 0.012696032654631012 },
		{ 0.032546962031130167, 0.017136931456510882 },
		{ 0.051839422116973954, 0.021417949011113418 },
		{ 0.075316193133715015, 0.025499029631188046 },
		{ 0.10275810201602881, 0.029342046739267783 },
		{ 0.13390894062985514, 0.032911111388180841 },
		{ 0.16847786653489238, 0.036172897054424169 },
		{ 0.20614212137961885, 0.039096947893535114 },
		{ 0.24655004553388532, 0.041655962113473353 },
		{ 0.28932436193468236, 0.043826046502201892 },
		{ 0.33406569885893617, 0.04558693934788189 },
		{ 0.38035631887393145, 0.046922199540402255 },
		{ 0.42776401920860174, 0.047819360039637354 },
		{ 0.47584616715613082, 0.04827004425736383 },
		{ 0.52415383284386918, 0.04827004425736383 },
		{ 0.57223598079139826, 0.047819360039637354 },
		{ 0.61964368112606849, 0.046922199540402255 },
		{ 0.66593430114106389, 0.04558693934788189 },
		{ 0.71067563806531764, 0.043826046502201892 },
		{ 0.75344995446611462, 0.041655962113473353 },
		{ 0.79385787862038115, 0.039096947893535114 },
		{ 0.83152213346510762, 0.036172897054424169 },
		{ 0.86609105937014486, 0.032911111388180841 },
		{ 0.89724189798397114, 0.029342046739267783 },
		{ 0.92468380686628504, 0.025499029631188046 },
		{ 0.94816057788302599, 0.021417949011113418 },
		{ 0.96745303796886983, 0.017136931456510882 },
		{ 0.98238112779375319, 0.012696032654631012 },
		{ 0.99280575577263419, 0.0081371973654528716 },
		{ 0.99863193092474078, 0.0035093050047352529 },
} };

Vector Add(const Vector &arrA, const Vector &arrB)
{
	return Vector{ arrA[0] + arrB[0], arrA[1] + arrB[1], arrA[2] + arrB[2] };
}

Vector Scale(const Vector &arrValue, float fScale)
{
	return Vector{ arrValue[0] * fScale, arrValue[1] * fScale, arrValue[2] * fScale };
}

float Dot(const Vector &arrA, const Vector &arrB)
{
	return arrA[0] * arrB[0] + arrA[1] * arrB[1] + arrA[2] * arrB[2];
}

Vector Cross(const Vector &arrA, const Vector &arrB)
{
	return Vector{ arrA[1] * arrB[2] - arrA[2] * arrB[1], arrA[2] * arrB[0] - arrA[0] * arrB[2], arrA[0] * arrB[1] - arrA[1] * arrB[0] };
}

Vector Normalize(const Vector &arrValue)
{
	return Scale(arrValue, 1.0F / std::sqrt(Dot(arrValue, arrValue)));
}

Vector LocalToWorld(const Vector &arrSample, const Vector &arrNormal)
{
	const Vector arrUp = std::abs(arrNormal[2]) < 0.999F ? Vector{ 0, 0, 1 } : Vector{ 1, 0, 0 };
	const Vector arrTangent = Normalize(Cross(arrUp, arrNormal));
	const Vector arrBitangent = Cross(arrNormal, arrTangent);
	return Normalize(Add(Add(Scale(arrTangent, arrSample[0]), Scale(arrBitangent, arrSample[1])), Scale(arrNormal, arrSample[2])));
}

Vector CubeDirection(std::uint32_t nFace, std::uint32_t nX, std::uint32_t nY, std::uint32_t nSize)
{
	const float fU = 2.0F * (static_cast<float>(nX) + 0.5F) / static_cast<float>(nSize) - 1.0F;
	const float fV = 2.0F * (static_cast<float>(nY) + 0.5F) / static_cast<float>(nSize) - 1.0F;
	Vector arrDirection{};
	switch (nFace)
	{
		case 0:
			arrDirection = { 1, -fV, -fU };
			break;
		case 1:
			arrDirection = { -1, -fV, fU };
			break;
		case 2:
			arrDirection = { fU, 1, fV };
			break;
		case 3:
			arrDirection = { fU, -1, -fV };
			break;
		case 4:
			arrDirection = { fU, -fV, 1 };
			break;
		default:
			arrDirection = { -fU, -fV, -1 };
			break;
	}
	return Normalize(arrDirection);
}

float RadicalInverse(std::uint32_t nBits)
{
	nBits = (nBits << 16U) | (nBits >> 16U);
	nBits = ((nBits & 0x55555555U) << 1U) | ((nBits & 0xAAAAAAAAU) >> 1U);
	nBits = ((nBits & 0x33333333U) << 2U) | ((nBits & 0xCCCCCCCCU) >> 2U);
	nBits = ((nBits & 0x0F0F0F0FU) << 4U) | ((nBits & 0xF0F0F0F0U) >> 4U);
	nBits = ((nBits & 0x00FF00FFU) << 8U) | ((nBits & 0xFF00FF00U) >> 8U);
	return static_cast<float>(static_cast<double>(nBits) * 2.3283064365386962890625e-10);
}

Vector GgxHalfVector(std::uint32_t nIndex, std::uint32_t nSamples, float fRoughness)
{
	const float fXiX = (static_cast<float>(nIndex) + 0.5F) / static_cast<float>(nSamples);
	const float fXiY = RadicalInverse(nIndex);
	const float fAlpha = fRoughness * fRoughness;
	const float fCosTheta = std::sqrt((1.0F - fXiY) / (1.0F + (fAlpha * fAlpha - 1.0F) * fXiY));
	const float fSinTheta = std::sqrt((std::max)(0.0F, 1.0F - fCosTheta * fCosTheta));
	const float fPhi = 2.0F * PI * fXiX;
	return Vector{ std::cos(fPhi) * fSinTheta, std::sin(fPhi) * fSinTheta, fCosTheta };
}

Vector Radiance(const EnvironmentConfig &stConfig, const Vector &arrDirection)
{
	const float fHeight = (std::max)(0.0F, arrDirection[1]);
	const float fBlend = std::sqrt(fHeight);
	const float fSunCos = Dot(arrDirection, stConfig.arrSunDirection);
	const float fSunEdge = std::cos(stConfig.fSunAngularRadius);
	const float fSun = std::clamp((fSunCos - fSunEdge) / (1.0F - fSunEdge), 0.0F, 1.0F);
	Vector arrResult{};
	for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
	{
		arrResult[nChannel] = arrDirection[1] < 0 ? stConfig.arrGround[nChannel] : stConfig.arrSkyHorizon[nChannel] * (1.0F - fBlend) + stConfig.arrSkyZenith[nChannel] * fBlend;
		arrResult[nChannel] += stConfig.arrSunRadiance[nChannel] * fSun;
	}
	return arrResult;
}

double IntegrateAzimuthCosine(double dNormalCosine, double dHeight)
{
	const double dCenter = dNormalCosine * dHeight;
	const double dRadius = std::sqrt((std::max)(0.0, (1.0 - dNormalCosine * dNormalCosine) * (1.0 - dHeight * dHeight)));
	if (dCenter >= dRadius)
	{
		return 2.0 * DOUBLE_PI * dCenter;
	}
	if (dCenter <= -dRadius)
	{
		return 0.0;
	}
	const double dRatio = std::clamp(dCenter / dRadius, -1.0, 1.0);
	return 2.0 * (dCenter * std::acos(-dRatio) + dRadius * std::sqrt((std::max)(0.0, 1.0 - dRatio * dRatio)));
}

double IntegrateSkyGradient(double dNormalY)
{
	const double dBoundary = std::sqrt((std::max)(0.0, 1.0 - dNormalY * dNormalY));
	// y=t*t removes the sky's square-root endpoint. A sine substitution also
	// smooths the latitude circle's tangent to the receiver horizon.
	const double dLimit = std::sqrt(dBoundary);
	double dIntegral = 0.0;
	for (const std::array<double, 2> &arrSample : IRRADIANCE_QUADRATURE)
	{
		const double dAngle = DOUBLE_PI * 0.5 * arrSample[0];
		const double dT = dLimit * std::sin(dAngle);
		const double dDerivative = dLimit * std::cos(dAngle) * DOUBLE_PI * 0.5;
		dIntegral += arrSample[1] * 2.0 * dT * dT * IntegrateAzimuthCosine(dNormalY, dT * dT) * dDerivative;
	}
	if (dNormalY > 0.0)
	{
		dIntegral += 4.0 * DOUBLE_PI * dNormalY / 5.0 * (1.0 - std::pow(dBoundary, 2.5));
	}
	return dIntegral;
}

double IntegrateSun(const EnvironmentConfig &stConfig, double dNormalCosine)
{
	// Match the finite-precision cap edge used by Radiance. Integrating this
	// narrow cap directly avoids missed sun samples at adjacent cube texels.
	const double dEdge = std::cos(stConfig.fSunAngularRadius);
	const double dWidth = 1.0 - dEdge;
	const double dBoundary = std::sqrt((std::max)(0.0, 1.0 - dNormalCosine * dNormalCosine));
	const double dTop = std::clamp(dBoundary, dEdge, 1.0);
	const double dExtent = dTop - dEdge;
	double dIntegral = 0.0;
	for (const std::array<double, 2> &arrSample : IRRADIANCE_QUADRATURE)
	{
		const double dHeight = dEdge + dExtent * arrSample[0];
		dIntegral += arrSample[1] * (dHeight - dEdge) / dWidth * IntegrateAzimuthCosine(dNormalCosine, dHeight) * dExtent;
	}
	if (dNormalCosine > 0.0)
	{
		const double dCapHeight = 1.0 - dTop;
		dIntegral += 2.0 * DOUBLE_PI * dNormalCosine * dCapHeight *
				(1.0 - dCapHeight * 0.5 - dCapHeight / dWidth * (0.5 - dCapHeight / 3.0));
	}
	return dIntegral;
}

Vector Irradiance(const EnvironmentConfig &stConfig, const Vector &arrNormal)
{
	const double dNormalY = std::clamp(static_cast<double>(arrNormal[1]), -1.0, 1.0);
	const double dSkyGradient = IntegrateSkyGradient(dNormalY);
	const double dSun = IntegrateSun(stConfig, std::clamp(static_cast<double>(Dot(arrNormal, stConfig.arrSunDirection)), -1.0, 1.0));
	Vector arrResult{};
	for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
	{
		const double dSky = DOUBLE_PI * 0.5 * ((1.0 - dNormalY) * stConfig.arrGround[nChannel] + (1.0 + dNormalY) * stConfig.arrSkyHorizon[nChannel]);
		arrResult[nChannel] = static_cast<float>(dSky + dSkyGradient * (stConfig.arrSkyZenith[nChannel] - stConfig.arrSkyHorizon[nChannel]) + dSun * stConfig.arrSunRadiance[nChannel]);
	}
	return arrResult;
}

Vector Prefilter(const EnvironmentConfig &stConfig, const Vector &arrNormal, float fRoughness)
{
	if (fRoughness == 0)
	{
		return Radiance(stConfig, arrNormal);
	}
	Vector arrSum{};
	float fWeight = 0;
	for (std::uint32_t nSample = 0; nSample < stConfig.nSampleCount; ++nSample)
	{
		const Vector arrHalf = LocalToWorld(GgxHalfVector(nSample, stConfig.nSampleCount, fRoughness), arrNormal);
		const Vector arrLight = Normalize(Add(Scale(arrHalf, 2.0F * Dot(arrNormal, arrHalf)), Scale(arrNormal, -1.0F)));
		const float fNdotL = (std::max)(0.0F, Dot(arrNormal, arrLight));
		arrSum = Add(arrSum, Scale(Radiance(stConfig, arrLight), fNdotL));
		fWeight += fNdotL;
	}
	return fWeight > 0 ? Scale(arrSum, 1.0F / fWeight) : Radiance(stConfig, arrNormal);
}

float SmithMask(float fNdotDirection, float fAlpha)
{
	return 2.0F * fNdotDirection / (fNdotDirection + std::sqrt(fAlpha * fAlpha + (1.0F - fAlpha * fAlpha) * fNdotDirection * fNdotDirection));
}

std::array<float, 4> IntegrateBrdf(std::uint32_t nSamples, float fNdotV, float fRoughness)
{
	const Vector arrView{ std::sqrt((std::max)(0.0F, 1.0F - fNdotV * fNdotV)), 0, fNdotV };
	float fA = 0;
	float fB = 0;
	for (std::uint32_t nSample = 0; nSample < nSamples; ++nSample)
	{
		const Vector arrHalf = GgxHalfVector(nSample, nSamples, fRoughness);
		const float fVdotH = (std::max)(0.0F, Dot(arrView, arrHalf));
		const Vector arrLight = Add(Scale(arrHalf, 2.0F * fVdotH), Scale(arrView, -1.0F));
		const float fNdotL = (std::max)(0.0F, arrLight[2]);
		if (fNdotL > 0)
		{
			const float fVisibility = SmithMask(fNdotV, fRoughness * fRoughness) * SmithMask(fNdotL, fRoughness * fRoughness) * fVdotH / (arrHalf[2] * fNdotV);
			const float fFresnel = std::pow(1.0F - fVdotH, 5.0F);
			fA += (1.0F - fFresnel) * fVisibility;
			fB += fFresnel * fVisibility;
		}
	}
	return { fA / static_cast<float>(nSamples), fB / static_cast<float>(nSamples), 0, 1 };
}

bool IsPowerOfTwo(std::uint32_t nValue)
{
	return nValue != 0 && (nValue & (nValue - 1)) == 0;
}

bool Validate(EnvironmentConfig &out_stConfig, std::string &out_strError)
{
	if (!IsPowerOfTwo(out_stConfig.nEnvironmentSize) || out_stConfig.nEnvironmentSize < 2 || out_stConfig.nEnvironmentSize > MAX_SIZE ||
		!IsPowerOfTwo(out_stConfig.nIrradianceSize) || out_stConfig.nIrradianceSize > MAX_SIZE ||
		!IsPowerOfTwo(out_stConfig.nBrdfSize) || out_stConfig.nBrdfSize < 2 || out_stConfig.nBrdfSize > MAX_SIZE ||
		out_stConfig.nSampleCount == 0 || out_stConfig.nSampleCount > MAX_SAMPLES)
	{
		out_strError = "Environment sizes require bounded powers of two and sample count in [1,1024].";
		return false;
	}
	std::uint64_t nFilteredPixels = 0;
	for (std::uint32_t nSize = out_stConfig.nEnvironmentSize / 2; nSize > 0; nSize /= 2)
	{
		nFilteredPixels += static_cast<std::uint64_t>(nSize) * nSize * 6;
	}
	const std::uint64_t nIrradianceSamples = static_cast<std::uint64_t>(out_stConfig.nIrradianceSize) * out_stConfig.nIrradianceSize * 6 * IRRADIANCE_QUADRATURE.size() * 2;
	const std::uint64_t nTotalSamples = (nFilteredPixels + static_cast<std::uint64_t>(out_stConfig.nBrdfSize) * out_stConfig.nBrdfSize) * out_stConfig.nSampleCount + nIrradianceSamples;
	if (nTotalSamples > MAX_INTEGRATION_SAMPLES)
	{
		out_strError = "Environment convolution exceeds its integration budget.";
		return false;
	}
	for (const Vector &arrColor : { out_stConfig.arrSkyZenith, out_stConfig.arrSkyHorizon, out_stConfig.arrGround, out_stConfig.arrSunRadiance })
	{
		for (float fValue : arrColor)
		{
			if (!std::isfinite(fValue) || fValue < 0 || fValue > 65504)
			{
				out_strError = "Environment radiance must be finite, nonnegative and within half-float range.";
				return false;
			}
		}
	}
	for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
	{
		const float fSkyMaximum = (std::max)(out_stConfig.arrGround[nChannel], (std::max)(out_stConfig.arrSkyZenith[nChannel], out_stConfig.arrSkyHorizon[nChannel]));
		if (fSkyMaximum + out_stConfig.arrSunRadiance[nChannel] > 65504.0F / PI)
		{
			out_strError = "Integrated environment irradiance would exceed half-float range.";
			return false;
		}
	}
	const float fDirectionLength = Dot(out_stConfig.arrSunDirection, out_stConfig.arrSunDirection);
	if (!std::isfinite(fDirectionLength) || fDirectionLength < 1.0e-10F || !std::isfinite(out_stConfig.fSunAngularRadius) || out_stConfig.fSunAngularRadius < 0.001F || out_stConfig.fSunAngularRadius > PI / 2)
	{
		out_strError = "Sun direction and angular radius are invalid.";
		return false;
	}
	out_stConfig.arrSunDirection = Normalize(out_stConfig.arrSunDirection);
	return true;
}

FloatImage CreateImage(std::uint32_t nSize)
{
	return FloatImage{ nSize, nSize, std::vector<std::array<float, 4>>(static_cast<std::size_t>(nSize) * nSize) };
}

void StorePixel(FloatImage &out_stImage, std::uint32_t nX, std::uint32_t nY, const Vector &arrValue)
{
	out_stImage.arrPixels[static_cast<std::size_t>(nY) * out_stImage.nWidth + nX] = { arrValue[0], arrValue[1], arrValue[2], 1 };
}

} // namespace

bool GenerateEnvironmentLighting(const EnvironmentConfig &stConfig, EnvironmentLighting &out_stLighting, std::string &out_strError)
{
	out_strError.clear();
	EnvironmentConfig stValidated = stConfig;
	if (!Validate(stValidated, out_strError))
	{
		return false;
	}
	EnvironmentLighting stLighting;
	for (std::uint32_t nFace = 0; nFace < 6; ++nFace)
	{
		stLighting.arrEnvironment[nFace] = CreateImage(stValidated.nEnvironmentSize);
		for (std::uint32_t nY = 0; nY < stValidated.nEnvironmentSize; ++nY)
		{
			for (std::uint32_t nX = 0; nX < stValidated.nEnvironmentSize; ++nX)
			{
				StorePixel(stLighting.arrEnvironment[nFace], nX, nY, Radiance(stValidated, CubeDirection(nFace, nX, nY, stValidated.nEnvironmentSize)));
			}
		}
		stLighting.arrIrradiance[nFace] = CreateImage(stValidated.nIrradianceSize);
		for (std::uint32_t nY = 0; nY < stValidated.nIrradianceSize; ++nY)
		{
			for (std::uint32_t nX = 0; nX < stValidated.nIrradianceSize; ++nX)
			{
				StorePixel(stLighting.arrIrradiance[nFace], nX, nY, Irradiance(stValidated, CubeDirection(nFace, nX, nY, stValidated.nIrradianceSize)));
			}
		}
	}
	std::uint32_t nMipCount = 0;
	for (std::uint32_t nSize = stValidated.nEnvironmentSize; nSize > 0; nSize /= 2)
	{
		++nMipCount;
	}
	for (std::uint32_t nMip = 0, nSize = stValidated.nEnvironmentSize; nSize > 0; ++nMip, nSize /= 2)
	{
		std::array<FloatImage, 6> arrFaces;
		const float fRoughness = static_cast<float>(nMip) / static_cast<float>(nMipCount - 1);
		for (std::uint32_t nFace = 0; nFace < 6; ++nFace)
		{
			arrFaces[nFace] = CreateImage(nSize);
			for (std::uint32_t nY = 0; nY < nSize; ++nY)
			{
				for (std::uint32_t nX = 0; nX < nSize; ++nX)
				{
					StorePixel(arrFaces[nFace], nX, nY, Prefilter(stValidated, CubeDirection(nFace, nX, nY, nSize), fRoughness));
				}
			}
		}
		stLighting.arrPrefilteredMips.push_back(std::move(arrFaces));
	}
	stLighting.stBrdfLut = CreateImage(stValidated.nBrdfSize);
	for (std::uint32_t nY = 0; nY < stValidated.nBrdfSize; ++nY)
	{
		for (std::uint32_t nX = 0; nX < stValidated.nBrdfSize; ++nX)
		{
			const float fNdotV = (static_cast<float>(nX) + 0.5F) / static_cast<float>(stValidated.nBrdfSize);
			const float fRoughness = (static_cast<float>(nY) + 0.5F) / static_cast<float>(stValidated.nBrdfSize);
			stLighting.stBrdfLut.arrPixels[static_cast<std::size_t>(nY) * stValidated.nBrdfSize + nX] = IntegrateBrdf(stValidated.nSampleCount, fNdotV, fRoughness);
		}
	}
	out_stLighting = std::move(stLighting);
	return true;
}

} // namespace EngineNext::Rendering
