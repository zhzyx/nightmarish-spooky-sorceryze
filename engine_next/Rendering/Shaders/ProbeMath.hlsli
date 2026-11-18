// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_PROBE_MATH
#define ENGINE_NEXT_PROBE_MATH

static const float GI_FLOAT_MAX = 3.402823466e38f;
static const float GI_PI = 3.14159265358979323846f;
struct GiBasis9
{
    float Values[9];
};
struct GiSh9
{
    float3 Coefficients[9];
};

bool GiFinite(float3 Value)
{
    return isfinite(Value.x) && isfinite(Value.y) && isfinite(Value.z);
}
float3 GiDirection(float3 Value)
{
    float Maximum = max(abs(Value.x), max(abs(Value.y), abs(Value.z)));
    if (!GiFinite(Value) || Maximum <= 0)
    {
        return float3(0, 0, 1);
    }
    float3 Scaled = Value / Maximum;
    return Scaled * rsqrt(dot(Scaled, Scaled));
}

float GiFiniteProduct(float A, float B)
{
    float Product = A * B;
    return isfinite(Product) ? Product : ((A < 0) != (B < 0) ? -GI_FLOAT_MAX : GI_FLOAT_MAX);
}
float GiFiniteSum(float A, float B)
{
    if (B > 0 && A > GI_FLOAT_MAX - B)
    {
        return GI_FLOAT_MAX;
    }
    if (B < 0 && A < -GI_FLOAT_MAX - B)
    {
        return -GI_FLOAT_MAX;
    }
    return A + B;
}
float GiBlendScalar(float Previous, float Current, float Weight)
{
    float Scale = max(abs(Previous), abs(Current));
    if (Scale == 0)
    {
        return 0;
    }
    return clamp((Previous / Scale) * Weight + (Current / Scale) * (1 - Weight), -1, 1) * Scale;
}

GiBasis9 GiBasis(float3 Direction)
{
    float3 D = GiDirection(Direction);
    GiBasis9 Basis;
    Basis.Values[0] = 0.2820947918f;
    Basis.Values[1] = 0.4886025119f * D.y;
    Basis.Values[2] = 0.4886025119f * D.z;
    Basis.Values[3] = 0.4886025119f * D.x;
    Basis.Values[4] = 1.0925484306f * D.x * D.y;
    Basis.Values[5] = 1.0925484306f * D.y * D.z;
    Basis.Values[6] = 0.3153915653f * (3 * D.z * D.z - 1);
    Basis.Values[7] = 1.0925484306f * D.x * D.z;
    Basis.Values[8] = 0.5462742153f * (D.x * D.x - D.y * D.y);
    return Basis;
}
GiSh9 GiZeroSh()
{
    GiSh9 Value;
    for (uint Index = 0; Index < 9; ++Index)
    {
        Value.Coefficients[Index] = float3(0, 0, 0);
    }
    return Value;
}
GiSh9 GiAccumulateRay(GiSh9 Current, float3 Direction, float3 Radiance, float SolidAngle)
{
    if (!GiFinite(Direction) || max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z))) == 0 ||
        !GiFinite(Radiance) || !isfinite(SolidAngle) || SolidAngle <= 0)
    {
        return Current;
    }
    GiBasis9 Basis = GiBasis(Direction);
    Radiance = max(Radiance, float3(0, 0, 0));
    for (uint Index = 0; Index < 9; ++Index)
    {
        float Weight = GiFiniteProduct(Basis.Values[Index], SolidAngle);
        float3 Old = GiFinite(Current.Coefficients[Index]) ? Current.Coefficients[Index] : float3(0, 0, 0);
        Current.Coefficients[Index] = float3(GiFiniteSum(Old.x, GiFiniteProduct(Radiance.x, Weight)),
            GiFiniteSum(Old.y, GiFiniteProduct(Radiance.y, Weight)), GiFiniteSum(Old.z, GiFiniteProduct(Radiance.z, Weight)));
    }
    return Current;
}
float3 GiIrradiance(GiSh9 Radiance, float3 Normal)
{
    GiBasis9 Basis = GiBasis(Normal);
    float3 Result = float3(0, 0, 0);
    for (uint Index = 0; Index < 9; ++Index)
    {
        float Convolution = Index == 0 ? GI_PI : (Index < 4 ? 2 * GI_PI / 3 : GI_PI / 4);
        float Weight = Basis.Values[Index] * Convolution;
        float3 Coefficient = Radiance.Coefficients[Index];
        if (!GiFinite(Coefficient))
        {
            return float3(0, 0, 0);
        }
        Result = float3(GiFiniteSum(Result.x, GiFiniteProduct(Coefficient.x, Weight)),
            GiFiniteSum(Result.y, GiFiniteProduct(Coefficient.y, Weight)), GiFiniteSum(Result.z, GiFiniteProduct(Coefficient.z, Weight)));
    }
    return GiFinite(Result) ? max(Result, float3(0, 0, 0)) : float3(0, 0, 0);
}
float GiVisibility(float Distance, float2 Moments, float Bias, float MinimumVariance)
{
    if (!isfinite(Distance) || !isfinite(Moments.x) || !isfinite(Moments.y) || !isfinite(Bias) || !isfinite(MinimumVariance) ||
        Distance < 0 || Moments.x < 0 || Moments.y < 0 || Bias < 0 || MinimumVariance < 0)
    {
        return 0;
    }
    float Target = max(Distance - Bias, 0);
    if (Target <= Moments.x)
    {
        return 1;
    }
    // Normalize before subtracting or squaring. Ratios keep the probability
    // stable across world-unit scales and avoid both squared overflow and a
    // fixed epsilon that would erase weak but meaningful distance differences.
    float Scale = max(Target, max(Moments.x, max(sqrt(Moments.y), sqrt(MinimumVariance))));
    float Mean = Moments.x / Scale;
    float Delta = Target / Scale - Mean;
    float Variance = max((Moments.y / Scale) / Scale - Mean * Mean, (MinimumVariance / Scale) / Scale);
    if (Variance <= 0)
    {
        return 0;
    }
    float RootVariance = sqrt(Variance);
    float DenominatorScale = max(RootVariance, Delta);
    float A = RootVariance / DenominatorScale;
    float B = Delta / DenominatorScale;
    float Probability = (A * A) / (A * A + B * B);
    return Probability * Probability * Probability;
}
float2 GiUpdateMoments(float2 Previous, float Distance, float HistoryWeight, bool HistoryValid)
{
    if (!isfinite(Distance) || Distance < 0 || (Distance > 0 && Distance > GI_FLOAT_MAX / Distance))
    {
        return float2(0, 0);
    }
    float2 Current = float2(Distance, Distance * Distance);
    if (!HistoryValid || !isfinite(Previous.x) || !isfinite(Previous.y) || Previous.x < 0 || Previous.y < 0)
    {
        return Current;
    }
    float Weight = isfinite(HistoryWeight) ? clamp(HistoryWeight, 0, 0.99f) : 0;
    return float2(GiBlendScalar(Previous.x, Current.x, Weight), GiBlendScalar(Previous.y, Current.y, Weight));
}
float GiHistoryWeight(float OldLuminance, float NewLuminance, float Hysteresis, float RelativeThreshold, bool Valid)
{
    if (!Valid || !isfinite(OldLuminance) || !isfinite(NewLuminance) || !isfinite(Hysteresis) ||
        !isfinite(RelativeThreshold) || RelativeThreshold < 0 || OldLuminance < 0 || NewLuminance < 0)
    {
        return 0;
    }
    float Weight = clamp(Hysteresis, 0, 0.99f);
    float Scale = max(OldLuminance, NewLuminance);
    if (Scale == 0)
    {
        return Weight;
    }
    float RelativeChange = abs(NewLuminance / Scale - OldLuminance / Scale);
    if (RelativeChange == 0)
    {
        return Weight;
    }
    if (RelativeThreshold == 0 || RelativeChange >= RelativeThreshold)
    {
        return 0;
    }
    return Weight * (1 - RelativeChange / RelativeThreshold);
}
GiSh9 GiBlendSh(GiSh9 Previous, GiSh9 Current, float Weight)
{
    float HistoryWeight = isfinite(Weight) ? clamp(Weight, 0, 0.99f) : 0;
    for (uint Index = 0; Index < 9; ++Index)
    {
        float3 New = GiFinite(Current.Coefficients[Index]) ? Current.Coefficients[Index] : float3(0, 0, 0);
        float3 Old = GiFinite(Previous.Coefficients[Index]) ? Previous.Coefficients[Index] : New;
        Current.Coefficients[Index] = float3(GiBlendScalar(Old.x, New.x, HistoryWeight),
            GiBlendScalar(Old.y, New.y, HistoryWeight), GiBlendScalar(Old.z, New.z, HistoryWeight));
    }
    return Current;
}
float GiTrilinearWeight(float3 Fraction, uint Corner)
{
    if (!GiFinite(Fraction) || Corner >= 8)
    {
        return 0;
    }
    Fraction = saturate(Fraction);
    return ((Corner & 1) != 0 ? Fraction.x : 1 - Fraction.x) *
        ((Corner & 2) != 0 ? Fraction.y : 1 - Fraction.y) *
        ((Corner & 4) != 0 ? Fraction.z : 1 - Fraction.z);
}
float3 GiBounceRadiance(float3 DirectRadiance, float3 PreviousIrradiance, float3 Albedo, float BounceStrength)
{
    if (!GiFinite(DirectRadiance) || !GiFinite(PreviousIrradiance) || !GiFinite(Albedo) || !isfinite(BounceStrength))
    {
        return float3(0, 0, 0);
    }
    float3 Direct = max(DirectRadiance, float3(0, 0, 0));
    float3 Bounce = max(PreviousIrradiance, float3(0, 0, 0)) * saturate(Albedo) * (saturate(BounceStrength) / GI_PI);
    return float3(GiFiniteSum(Direct.x, Bounce.x), GiFiniteSum(Direct.y, Bounce.y), GiFiniteSum(Direct.z, Bounce.z));
}

#endif
