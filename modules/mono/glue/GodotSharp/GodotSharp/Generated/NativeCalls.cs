namespace Godot;

using System;
using System.Diagnostics.CodeAnalysis;
using System.Runtime.InteropServices;
using Godot.NativeInterop;

[SuppressMessage("ReSharper", "InconsistentNaming")]
[SuppressMessage("ReSharper", "RedundantUnsafeContext")]
[SuppressMessage("ReSharper", "RedundantNameQualifier")]
[System.Runtime.CompilerServices.SkipLocalsInit]
internal static class NativeCalls
{
    internal static ulong godot_api_hash = 13639695;

    private const int VarArgsSpanThreshold = 10;

    internal static unsafe int godot_icall_3_0(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2, ReadOnlySpan<byte> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_1_1(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe byte[] godot_icall_0_2(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_0_3(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, null);
    }

    internal static unsafe long godot_icall_0_4(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_5(IntPtr method, IntPtr ptr, long arg1, Vector2* arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_1_6(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_7(IntPtr method, IntPtr ptr, long arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_1_8(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_2_9(IntPtr method, IntPtr ptr, long arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_10(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_1_11(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long[] godot_icall_1_12(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe long[] godot_icall_0_13(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_1_14(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_0_15(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_16(IntPtr method, IntPtr ptr, long arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_17(IntPtr method, IntPtr ptr, long arg1, long arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_3_18(IntPtr method, IntPtr ptr, long arg1, long arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_2_19(IntPtr method, IntPtr ptr, Vector2* arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2 godot_icall_1_20(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2[] godot_icall_3_21(IntPtr method, IntPtr ptr, long arg1, long arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe long[] godot_icall_3_22(IntPtr method, IntPtr ptr, long arg1, long arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2[] godot_icall_2_23(IntPtr method, IntPtr ptr, long arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe long[] godot_icall_2_24(IntPtr method, IntPtr ptr, long arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_3_25(IntPtr method, IntPtr ptr, long arg1, Vector3* arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3 godot_icall_1_26(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_27(IntPtr method, IntPtr ptr, long arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe long godot_icall_2_28(IntPtr method, IntPtr ptr, Vector3* arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_1_29(IntPtr method, IntPtr ptr, Vector3* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3[] godot_icall_3_30(IntPtr method, IntPtr ptr, long arg1, long arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_2_31(IntPtr method, IntPtr ptr, long arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_1_32(IntPtr method, IntPtr ptr, Rect2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rect2I godot_icall_0_33(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2I ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_34(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2I godot_icall_0_35(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_36(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_0_37(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_38(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_0_39(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_2_40(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_41(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_42(IntPtr method, IntPtr ptr, Vector2I* arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_43(IntPtr method, IntPtr ptr, Vector2I* arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_1_44(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_2_45(IntPtr method, IntPtr ptr, Rect2I* arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_46(IntPtr method, IntPtr ptr, Rect2I* arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_1_47(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_48(IntPtr method, IntPtr ptr, Rect2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector2[] godot_icall_3_49(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[3] { arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_3_50(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[3] { arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector2[] godot_icall_2_51(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_52(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_0_53(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_3_54(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_1_55(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe void godot_icall_1_56(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_57(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string godot_icall_0_58(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Rid godot_icall_2_59(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_60(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_5_61(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, float arg3, int arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        double arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_62(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_63(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_64(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_1_65(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_66(IntPtr method, IntPtr ptr, int arg1, Rect2* arg2, Rect2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_67(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_1_68(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_69(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_70(IntPtr method, IntPtr ptr, Rid arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_71(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_72(IntPtr method, IntPtr ptr, Rid arg1, Transform2D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_73(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_74(IntPtr method, IntPtr ptr, Rid arg1, int arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_75(IntPtr method, IntPtr ptr, Rid arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_76(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_77(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_78(IntPtr method, IntPtr ptr, Rid arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_79(IntPtr method, IntPtr ptr, Rid arg1, double arg2, double arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_80(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, godot_bool arg3, godot_bool arg4, Color* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3, &arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_81(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, int arg3, Rid arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3_in, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_82(IntPtr method, IntPtr ptr, Rid arg1, int arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_83(IntPtr method, IntPtr ptr, Rid arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_84(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_1_85(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_1_86(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_0_87(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_1_88(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe StringName godot_icall_0_89(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_90(IntPtr method, IntPtr ptr, godot_string_name arg1, float arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_91(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_0_92(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_2_93(IntPtr method, IntPtr ptr, int arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_94(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_95(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe float godot_icall_1_96(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe int godot_icall_2_97(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe NodePath godot_icall_1_98(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_node_path ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return NodePath.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_2_99(IntPtr method, IntPtr ptr, int arg1, godot_node_path arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_100(IntPtr method, IntPtr ptr, godot_node_path arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_101(IntPtr method, IntPtr ptr, int arg1, double arg2, Vector3* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_102(IntPtr method, IntPtr ptr, int arg1, double arg2, Quaternion* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_103(IntPtr method, IntPtr ptr, int arg1, double arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Vector3 godot_icall_3_104(IntPtr method, IntPtr ptr, int arg1, double arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Quaternion godot_icall_3_105(IntPtr method, IntPtr ptr, int arg1, double arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Quaternion ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe float godot_icall_3_106(IntPtr method, IntPtr ptr, int arg1, double arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe int godot_icall_4_107(IntPtr method, IntPtr ptr, int arg1, double arg2, Variant arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_108(IntPtr method, IntPtr ptr, int arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_109(IntPtr method, IntPtr ptr, int arg1, int arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_110(IntPtr method, IntPtr ptr, int arg1, int arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_111(IntPtr method, IntPtr ptr, int arg1, int arg2, double arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_2_112(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe Variant godot_icall_2_113(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe double godot_icall_2_114(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_5_115(IntPtr method, IntPtr ptr, int arg1, double arg2, int arg3, godot_bool arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3_in, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Variant godot_icall_3_116(IntPtr method, IntPtr ptr, int arg1, double arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe StringName godot_icall_2_117(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_118(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe int godot_icall_5_119(IntPtr method, IntPtr ptr, int arg1, double arg2, float arg3, Vector2* arg4, Vector2* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3_in, arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_4_120(IntPtr method, IntPtr ptr, int arg1, int arg2, Vector2* arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_2_121(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe float godot_icall_2_122(IntPtr method, IntPtr ptr, int arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe int godot_icall_5_123(IntPtr method, IntPtr ptr, int arg1, double arg2, IntPtr arg3, float arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        double arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_124(IntPtr method, IntPtr ptr, int arg1, int arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_2_125(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_3_126(IntPtr method, IntPtr ptr, int arg1, double arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_127(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_128(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_1_129(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe StringName godot_icall_1_130(IntPtr method, IntPtr ptr, double arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe double godot_icall_1_131(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string[] godot_icall_0_132(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe Color godot_icall_1_133(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_134(IntPtr method, IntPtr ptr, godot_string_name arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_135(IntPtr method, IntPtr ptr, double arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe double godot_icall_0_136(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_137(IntPtr method, IntPtr ptr, float arg1, float arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        double arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_138(IntPtr method, IntPtr ptr, uint arg1, uint arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_3_139(IntPtr method, IntPtr ptr, int arg1, double arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Variant godot_icall_2_140(IntPtr method, IntPtr ptr, int arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector3 godot_icall_2_141(IntPtr method, IntPtr ptr, int arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Quaternion godot_icall_2_142(IntPtr method, IntPtr ptr, int arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Quaternion ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_143(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_144(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_145(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Godot.Collections.Array godot_icall_0_146(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_1_147(IntPtr method, IntPtr ptr, godot_dictionary arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_0_148(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_1_149(IntPtr method, IntPtr ptr, godot_node_path arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe NodePath godot_icall_0_150(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_node_path ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return NodePath.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector3 godot_icall_0_151(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe Quaternion godot_icall_0_152(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Quaternion ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_153(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe StringName godot_icall_1_154(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_5_155(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, Variant arg3, IntPtr arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg2_in = arg2;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3_in, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_1_156(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_157(IntPtr method, IntPtr ptr, int arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_1_158(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_1_159(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_160(IntPtr method, IntPtr ptr, godot_node_path arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_1_161(IntPtr method, IntPtr ptr, godot_node_path arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe ulong godot_icall_0_162(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_163(IntPtr method, IntPtr ptr, godot_array arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_164(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2, double arg3, godot_bool arg4, godot_bool arg5, float arg6, int arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3, &arg4, &arg5, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe double godot_icall_9_165(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2, double arg3, godot_bool arg4, godot_bool arg5, float arg6, int arg7, godot_bool arg8, godot_bool arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        double arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[9] { &arg1, &arg2, &arg3, &arg4, &arg5, &arg6_in, &arg7_in, &arg8, &arg9 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe double godot_icall_8_166(IntPtr method, IntPtr ptr, int arg1, double arg2, godot_bool arg3, godot_bool arg4, float arg5, int arg6, godot_bool arg7, godot_bool arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        double arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[8] { &arg1_in, &arg2, &arg3, &arg4, &arg5_in, &arg6_in, &arg7, &arg8 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_167(IntPtr method, IntPtr ptr, godot_string_name arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_1_168(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_4_169(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2, int arg3, godot_string_name arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_170(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe StringName godot_icall_1_171(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe int godot_icall_1_172(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_173(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_174(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, int arg3, godot_string_name arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_175(IntPtr method, IntPtr ptr, int arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_1_176(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_177(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_178(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_179(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2, Vector2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_180(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_181(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_182(IntPtr method, IntPtr ptr, godot_string_name arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_1_183(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_184(IntPtr method, ReadOnlySpan<float> arg1)
    {
        godot_bool ret;
        using godot_packed_float32_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe double godot_icall_2_185(IntPtr method, ReadOnlySpan<float> arg1, godot_bool arg2)
    {
        double ret;
        using godot_packed_float32_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_186(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_2_187(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_188(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_189(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe StringName godot_icall_1_190(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_191(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, double arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe double godot_icall_2_192(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_193(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_194(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_string_name arg3, double arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3, &arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_195(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2, double arg3, double arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3, &arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_196(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_string_name arg3, double arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_197(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2, double arg3, double arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_198(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2, double arg3, float arg4, godot_bool arg5, int arg6, int arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        long arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3, &arg4_in, &arg5, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_199(IntPtr method, IntPtr ptr, double arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_200(IntPtr method, IntPtr ptr, double arg1, godot_bool arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_201(IntPtr method, IntPtr ptr, double arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_1_202(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_203(IntPtr method, IntPtr ptr, Vector3* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_204(IntPtr method, IntPtr ptr, int arg1, godot_array arg2, godot_array arg3, godot_dictionary arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_205(IntPtr method, IntPtr ptr, int arg1, int arg2, ReadOnlySpan<byte> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_206(IntPtr method, IntPtr ptr, int arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_207(IntPtr method, IntPtr ptr, Transform3D* arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_1_208(IntPtr method, IntPtr ptr, Aabb* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Aabb godot_icall_0_209(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Aabb ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_210(IntPtr method, IntPtr ptr, ReadOnlySpan<string> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_211(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1, ReadOnlySpan<int> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        using godot_packed_int32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_212(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_213(IntPtr method, IntPtr ptr, ReadOnlySpan<int> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_214(IntPtr method, IntPtr ptr, Rect2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rect2 godot_icall_0_215(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe Vector2[] godot_icall_1_216(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2 godot_icall_3_217(IntPtr method, IntPtr ptr, float arg1, float arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        double arg1_in = arg1;
        double arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Transform3D godot_icall_0_218(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_219(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_3_220(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_221(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_222(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_1_223(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_1_224(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_225(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_9_226(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, int arg5, float arg6, godot_bool arg7, int arg8, godot_bool arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        double arg6_in = arg6;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[9] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7, &arg8_in, &arg9 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int[] godot_icall_0_227(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe GodotObject godot_icall_1_228(IntPtr method, ReadOnlySpan<byte> arg1)
    {
        using godot_ref ret = default;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_1_229(IntPtr method, string arg1)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_1_230(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2[] godot_icall_2_231(IntPtr method, IntPtr ptr, float arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        double arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe long godot_icall_6_232(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2, float arg3, float arg4, int arg5, godot_string_name arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_4_233(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2, float arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_234(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe uint godot_icall_0_235(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return (uint)(ret);
    }

    internal static unsafe void godot_icall_3_236(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_2_237(IntPtr method, ReadOnlySpan<byte> arg1, godot_dictionary arg2)
    {
        using godot_ref ret = default;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_2_238(IntPtr method, string arg1, godot_dictionary arg2)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_1_239(IntPtr method, IntPtr ptr, double arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_1_240(IntPtr method, IntPtr ptr, Color* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Color godot_icall_0_241(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_242(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_243(IntPtr method, IntPtr ptr, int arg1, Rect2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_244(IntPtr method, IntPtr ptr, Rect2I* arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_1_245(IntPtr method, IntPtr ptr, Transform2D* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform2D godot_icall_0_246(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform2D ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_247(IntPtr method, IntPtr ptr, int arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3 godot_icall_1_248(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_249(IntPtr method, IntPtr ptr, int arg1, Quaternion* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Quaternion godot_icall_1_250(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Quaternion ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_2_251(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_1_252(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe void godot_icall_2_253(IntPtr method, IntPtr ptr, float arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_254(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2[] godot_icall_0_255(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_1_256(IntPtr method, IntPtr ptr, ReadOnlySpan<Color> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_color_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Color[] godot_icall_0_257(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_color_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedColorArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_0_258(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Variant godot_icall_1_259(IntPtr method, IntPtr ptr, ReadOnlySpan<Variant> arg1, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        int vararg_length = arg1.Length;
        int total_length = 0 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg1[i].NativeVar;
                call_args[0 + i] = new IntPtr(&varargs[i]);
            }
            godot_variant ret = NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
            return Variant.CreateTakingOwnershipOfDisposableValue(ret);
        }
    }

    internal static unsafe Vector3 godot_icall_1_260(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2 godot_icall_1_261(IntPtr method, IntPtr ptr, Vector3* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_262(IntPtr method, IntPtr ptr, Vector3* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_2_263(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_264(IntPtr method, IntPtr ptr, float arg1, float arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_265(IntPtr method, IntPtr ptr, float arg1, Vector2* arg2, float arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Projection godot_icall_0_266(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Projection ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_0_267(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_268(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe ulong godot_icall_1_269(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_270(IntPtr method, IntPtr ptr, int arg1, godot_dictionary arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_5_271(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Color* arg3, float arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        void** call_args = stackalloc void*[5] { arg1, arg2, arg3, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_272(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Color* arg3, float arg4, float arg5, godot_bool arg6, godot_bool arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[7] { arg1, arg2, arg3, &arg4_in, &arg5_in, &arg6, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_273(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, Color* arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_274(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, ReadOnlySpan<Color> arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        using godot_packed_color_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg2);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_9_275(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2, float arg3, float arg4, float arg5, int arg6, Color* arg7, float arg8, godot_bool arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        double arg8_in = arg8;
        void** call_args = stackalloc void*[9] { arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, arg7, &arg8_in, &arg9 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_8_276(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2, float arg3, float arg4, int arg5, Color* arg6, float arg7, godot_bool arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        long arg5_in = arg5;
        double arg7_in = arg7;
        void** call_args = stackalloc void*[8] { arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, arg6, &arg7_in, &arg8 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_277(IntPtr method, IntPtr ptr, Rect2* arg1, Color* arg2, godot_bool arg3, float arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        void** call_args = stackalloc void*[5] { arg1, arg2, &arg3, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_278(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2, Color* arg3, godot_bool arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { arg1, &arg2_in, arg3, &arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_279(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2, float arg3, Color* arg4, godot_bool arg5, float arg6, godot_bool arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[7] { arg1, &arg2_in, &arg3_in, arg4, &arg5, &arg6_in, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_280(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, Color* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_281(IntPtr method, IntPtr ptr, IntPtr arg1, Rect2* arg2, godot_bool arg3, Color* arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3, arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_282(IntPtr method, IntPtr ptr, IntPtr arg1, Rect2* arg2, Rect2* arg3, Color* arg4, godot_bool arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[6] { &arg1, arg2, arg3, arg4, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_283(IntPtr method, IntPtr ptr, IntPtr arg1, Rect2* arg2, Rect2* arg3, Color* arg4, double arg5, double arg6, double arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[7] { &arg1, arg2, arg3, arg4, &arg5, &arg6, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_284(IntPtr method, IntPtr ptr, IntPtr arg1, Rect2* arg2, Rect2* arg3, Color* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_285(IntPtr method, IntPtr ptr, IntPtr arg1, Rect2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_286(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, ReadOnlySpan<Color> arg2, ReadOnlySpan<Vector2> arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        using godot_packed_color_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg2);
        using godot_packed_vector2_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg3);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_287(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, Color* arg2, ReadOnlySpan<Vector2> arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        using godot_packed_vector2_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg3);
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_11_288(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, Color* arg7, int arg8, int arg9, int arg10, float arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg8_in = arg8;
        long arg9_in = arg9;
        long arg10_in = arg10;
        double arg11_in = arg11;
        void** call_args = stackalloc void*[11] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, arg7, &arg8_in, &arg9_in, &arg10_in, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_13_289(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11, int arg12, float arg13)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        double arg13_in = arg13;
        void** call_args = stackalloc void*[13] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in, &arg12_in, &arg13_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_12_290(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11, float arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        double arg12_in = arg12;
        void** call_args = stackalloc void*[12] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in, &arg12_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_14_291(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, int arg8, Color* arg9, int arg10, int arg11, int arg12, int arg13, float arg14)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        long arg13_in = arg13;
        double arg14_in = arg14;
        void** call_args = stackalloc void*[14] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, arg9, &arg10_in, &arg11_in, &arg12_in, &arg13_in, &arg14_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_292(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, Color* arg5, float arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3_in, &arg4_in, arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_293(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, int arg5, Color* arg6, float arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        long arg5_in = arg5;
        double arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, arg6, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_294(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, Transform2D* arg3, Color* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_295(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2, Vector2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[3] { arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_296(IntPtr method, IntPtr ptr, double arg1, double arg2, double arg3, double arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_297(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_2_298(IntPtr method, IntPtr ptr, uint arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_1_299(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_300(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, ReadOnlySpan<Color> arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        using godot_packed_color_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg2);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_301(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, Color* arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_302(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Color* arg3, float arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { arg1, arg2, arg3, &arg4_in, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_303(IntPtr method, IntPtr ptr, Rect2* arg1, Color* arg2, godot_bool arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { arg1, arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_304(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2, Color* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[3] { arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_305(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, int arg5, Color* arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_306(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, Color* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3_in, &arg4_in, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_13_307(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, int arg8, Color* arg9, int arg10, int arg11, int arg12, int arg13)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        long arg13_in = arg13;
        void** call_args = stackalloc void*[13] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, arg9, &arg10_in, &arg11_in, &arg12_in, &arg13_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_11_308(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        void** call_args = stackalloc void*[11] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_12_309(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11, int arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        void** call_args = stackalloc void*[12] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in, &arg12_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_10_310(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, Color* arg7, int arg8, int arg9, int arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg8_in = arg8;
        long arg9_in = arg9;
        long arg10_in = arg10;
        void** call_args = stackalloc void*[10] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, arg7, &arg8_in, &arg9_in, &arg10_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe byte godot_icall_0_311(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return (byte)(ret);
    }

    internal static unsafe void godot_icall_1_312(IntPtr method, IntPtr ptr, byte arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe ushort godot_icall_0_313(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return (ushort)(ret);
    }

    internal static unsafe void godot_icall_1_314(IntPtr method, IntPtr ptr, ushort arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_1_315(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe float godot_icall_1_316(IntPtr method, IntPtr ptr, Vector3* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe string[] godot_icall_1_317(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_318(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_319(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe StringName godot_icall_2_320(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_2_321(IntPtr method, IntPtr ptr, IntPtr arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe int godot_icall_3_322(IntPtr method, IntPtr ptr, IntPtr arg1, godot_string_name arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Variant godot_icall_2_323(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_3_324(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_325(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Variant godot_icall_3_326(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, ReadOnlySpan<Variant> arg3, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        int vararg_length = arg3.Length;
        int total_length = 2 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromStringName(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            using godot_variant arg2_in = VariantUtils.CreateFromStringName(arg2);
            call_args[1] = new IntPtr(&arg2_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg3[i].NativeVar;
                call_args[2 + i] = new IntPtr(&varargs[i]);
            }
            godot_variant ret = NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
            return Variant.CreateTakingOwnershipOfDisposableValue(ret);
        }
    }

    internal static unsafe string[] godot_icall_2_327(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe long godot_icall_2_328(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string[] godot_icall_3_329(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe StringName godot_icall_3_330(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_2_331(IntPtr method, IntPtr ptr, string arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string godot_icall_1_332(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe void godot_icall_3_333(IntPtr method, IntPtr ptr, string arg1, string arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_334(IntPtr method, IntPtr ptr, int arg1, string arg2, string arg3, Color* arg4, IntPtr arg5, Variant arg6, int arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        godot_variant arg6_in = (godot_variant)arg6.NativeVar;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2_in, &arg3_in, arg4, &arg5, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_1_335(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_2_336(IntPtr method, IntPtr ptr, string arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Color godot_icall_1_337(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_338(IntPtr method, IntPtr ptr, string arg1, string arg2, Color* arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe uint godot_icall_1_339(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (uint)(ret);
    }

    internal static unsafe void godot_icall_2_340(IntPtr method, IntPtr ptr, uint arg1, Transform2D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform2D godot_icall_1_341(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform2D ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_1_342(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe void godot_icall_2_343(IntPtr method, IntPtr ptr, uint arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_1_344(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe Vector2 godot_icall_1_345(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_346(IntPtr method, IntPtr ptr, uint arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_347(IntPtr method, IntPtr ptr, uint arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_1_348(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_2_349(IntPtr method, IntPtr ptr, uint arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_2_350(IntPtr method, IntPtr ptr, uint arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_351(IntPtr method, IntPtr ptr, uint arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe uint godot_icall_1_352(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (uint)(ret);
    }

    internal static unsafe void godot_icall_2_353(IntPtr method, IntPtr ptr, uint arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform3D godot_icall_1_354(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_355(IntPtr method, IntPtr ptr, string arg1, string arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_3_356(IntPtr method, IntPtr ptr, string arg1, string arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_2_357(IntPtr method, IntPtr ptr, string arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string[] godot_icall_1_358(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_2_359(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<byte> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_360(IntPtr method, IntPtr ptr, string arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_4_361(IntPtr method, IntPtr ptr, int arg1, float arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_362(IntPtr method, IntPtr ptr, int arg1, float arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_363(IntPtr method, IntPtr ptr, Vector2* arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_1_364(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_1_365(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_2_366(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_2_367(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Color godot_icall_2_368(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_1_369(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_1_370(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_371(IntPtr method, IntPtr ptr, Variant arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_372(IntPtr method, IntPtr ptr, in Callable arg1, in Callable arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe byte[] godot_icall_1_373(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe GodotObject godot_icall_4_374(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2, string arg3, string arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe byte[] godot_icall_3_375(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe godot_bool godot_icall_4_376(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2, ReadOnlySpan<byte> arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe byte[] godot_icall_2_377(IntPtr method, IntPtr ptr, IntPtr arg1, ReadOnlySpan<byte> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe byte[] godot_icall_3_378(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2, ReadOnlySpan<byte> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe godot_bool godot_icall_2_379(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, ReadOnlySpan<byte> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_380(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe string godot_icall_1_381(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_5_382(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2, float arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        double arg2_in = arg2;
        double arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_383(IntPtr method, IntPtr ptr, int arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe float godot_icall_1_384(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_4_385(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Vector2* arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_2_386(IntPtr method, IntPtr ptr, int arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2 godot_icall_1_387(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2 godot_icall_2_388(IntPtr method, IntPtr ptr, float arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Transform2D godot_icall_2_389(IntPtr method, IntPtr ptr, float arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform2D ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2[] godot_icall_2_390(IntPtr method, IntPtr ptr, int arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_4_391(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Vector3* arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3 godot_icall_2_392(IntPtr method, IntPtr ptr, int arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_1_393(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_2_394(IntPtr method, IntPtr ptr, float arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Transform3D godot_icall_3_395(IntPtr method, IntPtr ptr, float arg1, godot_bool arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe float[] godot_icall_0_396(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedFloat32ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_2_397(IntPtr method, IntPtr ptr, int arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        long arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe GodotObject godot_icall_4_398(IntPtr method, string arg1, float arg2, float arg3, godot_dictionary arg4)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_1_399(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_0_400(IntPtr method)
    {
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_2_401(IntPtr method, string arg1, godot_bool arg2)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe string[] godot_icall_1_402(IntPtr method, string arg1)
    {
        using godot_packed_string_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe string godot_icall_1_403(IntPtr method, int arg1)
    {
        using godot_string ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_1_404(IntPtr method, string arg1)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_1_405(IntPtr method, string arg1)
    {
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_406(IntPtr method, IntPtr ptr, string arg1, string arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_407(IntPtr method, string arg1, string arg2, int arg3)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_408(IntPtr method, string arg1, string arg2)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_409(IntPtr method, IntPtr ptr, in Callable arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_410(IntPtr method, IntPtr ptr, string arg1, in Callable arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_4_411(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_7_412(IntPtr method, IntPtr ptr, string arg1, string arg2, in Callable arg3, in Callable arg4, Variant arg5, int arg6, int arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        godot_variant arg5_in = (godot_variant)arg5.NativeVar;
        long arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_8_413(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2, string arg3, in Callable arg4, in Callable arg5, Variant arg6, int arg7, int arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        using godot_callable arg5_in = Marshaling.ConvertCallableToNative(in arg5);
        godot_variant arg6_in = (godot_variant)arg6.NativeVar;
        long arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1_in, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_9_414(IntPtr method, IntPtr ptr, string arg1, string arg2, int arg3, int arg4, in Callable arg5, in Callable arg6, Variant arg7, int arg8, int arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        long arg4_in = arg4;
        using godot_callable arg5_in = Marshaling.ConvertCallableToNative(in arg5);
        using godot_callable arg6_in = Marshaling.ConvertCallableToNative(in arg6);
        godot_variant arg7_in = (godot_variant)arg7.NativeVar;
        long arg8_in = arg8;
        long arg9_in = arg9;
        void** call_args = stackalloc void*[9] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_415(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_416(IntPtr method, IntPtr ptr, string arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_2_417(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Callable godot_icall_2_418(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertCallableToManaged(in ret);
    }

    internal static unsafe Variant godot_icall_2_419(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_2_420(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_2_421(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_422(IntPtr method, IntPtr ptr, string arg1, int arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_423(IntPtr method, IntPtr ptr, string arg1, int arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_424(IntPtr method, IntPtr ptr, string arg1, int arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_425(IntPtr method, IntPtr ptr, string arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_426(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_427(IntPtr method, IntPtr ptr, string arg1, int arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_428(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_429(IntPtr method, IntPtr ptr, string arg1, string arg2, int arg3, float arg4, float arg5, long arg6, godot_bool arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_430(IntPtr method, IntPtr ptr, int arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_431(IntPtr method, IntPtr ptr, in Callable arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_432(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Rect2I godot_icall_1_433(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2I ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_1_434(IntPtr method, IntPtr ptr, Rect2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Vector2I godot_icall_1_435(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Color godot_icall_1_436(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_1_437(IntPtr method, IntPtr ptr, Rect2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_1_438(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe long godot_icall_2_439(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_2_440(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_441(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_442(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_443(IntPtr method, IntPtr ptr, in Callable arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_444(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_445(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3I godot_icall_1_446(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3I ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_447(IntPtr method, IntPtr ptr, float arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_448(IntPtr method, IntPtr ptr, godot_bool arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_449(IntPtr method, IntPtr ptr, Rect2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_450(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_451(IntPtr method, IntPtr ptr, string arg1, Rect2* arg2, int arg3, int arg4, int arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1_in, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_452(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, Vector2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_4_453(IntPtr method, IntPtr ptr, string arg1, string arg2, IntPtr arg3, in Callable arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_454(IntPtr method, IntPtr ptr, string arg1, string arg2, ReadOnlySpan<string> arg3, in Callable arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_packed_string_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg3);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_455(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, in Callable arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_8_456(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, godot_bool arg4, int arg5, ReadOnlySpan<string> arg6, in Callable arg7, int arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg5_in = arg5;
        using godot_packed_string_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg6);
        using godot_callable arg7_in = Marshaling.ConvertCallableToNative(in arg7);
        long arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1_in, &arg2_in, &arg3_in, &arg4, &arg5_in, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_10_457(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, string arg4, godot_bool arg5, int arg6, ReadOnlySpan<string> arg7, godot_array arg8, in Callable arg9, int arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        long arg6_in = arg6;
        using godot_packed_string_array arg7_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg7);
        using godot_callable arg9_in = Marshaling.ConvertCallableToNative(in arg9);
        long arg10_in = arg10;
        void** call_args = stackalloc void*[10] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5, &arg6_in, &arg7_in, &arg8, &arg9_in, &arg10_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_1_458(IntPtr method, IntPtr ptr, in Callable arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_459(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_460(IntPtr method, IntPtr ptr, int arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rect2 godot_icall_1_461(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_462(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, float arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        double arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_9_463(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, string arg4, godot_bool arg5, int arg6, ReadOnlySpan<string> arg7, godot_array arg8, in Callable arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        long arg6_in = arg6;
        using godot_packed_string_array arg7_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg7);
        using godot_callable arg9_in = Marshaling.ConvertCallableToNative(in arg9);
        void** call_args = stackalloc void*[9] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5, &arg6_in, &arg7_in, &arg8, &arg9_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_7_464(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, godot_bool arg4, int arg5, ReadOnlySpan<string> arg6, in Callable arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg5_in = arg5;
        using godot_packed_string_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg6);
        using godot_callable arg7_in = Marshaling.ConvertCallableToNative(in arg7);
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2_in, &arg3_in, &arg4, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_5_465(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, Color* arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_466(IntPtr method, IntPtr ptr, Rect2I* arg1, IntPtr arg2, Color* arg3, int arg4, IntPtr arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { arg1, &arg2, arg3, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_467(IntPtr method, IntPtr ptr, Rect2I* arg1, godot_array arg2, godot_array arg3, Color* arg4, int arg5, IntPtr arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[6] { arg1, &arg2, &arg3, arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_6_468(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3, int arg4, int arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_469(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_4_470(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_471(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_472(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe double godot_icall_1_473(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_474(IntPtr method, IntPtr ptr, string arg1, int arg2, ReadOnlySpan<byte> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_5_475(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_476(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_477(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_482(IntPtr method, IntPtr ptr, string arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string[] godot_icall_1_487(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_496(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string[] godot_icall_0_498(IntPtr method)
    {
        using godot_packed_string_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_515(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_516(IntPtr method, IntPtr ptr, IntPtr arg1, Rect2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_517(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_518(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2I* arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_526(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_535(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_537(IntPtr method, IntPtr ptr, string arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_542(IntPtr method, IntPtr ptr, IntPtr arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_546(IntPtr method, IntPtr ptr, string arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_1_548(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_1_551(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_554(IntPtr method, IntPtr ptr, IntPtr arg1, godot_string_name arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_562(IntPtr method, IntPtr ptr, ulong arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_563(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_564(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_2_565(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_566(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_bool arg2, godot_array arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_567(IntPtr method, IntPtr ptr, godot_string_name arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_568(IntPtr method, IntPtr ptr, godot_bool arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_569(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_2_570(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_571(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Variant godot_icall_4_572(IntPtr method, IntPtr ptr, godot_array arg1, IntPtr arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_2_573(IntPtr method, string arg1, int arg2)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_4_574(IntPtr method, string arg1, int arg2, ReadOnlySpan<byte> arg3, ReadOnlySpan<byte> arg4)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        using godot_packed_byte_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_3_575(IntPtr method, string arg1, int arg2, string arg3)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_3_576(IntPtr method, string arg1, int arg2, int arg3)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_4_577(IntPtr method, int arg1, string arg2, string arg3, godot_bool arg4)
    {
        using godot_ref ret = default;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe byte[] godot_icall_1_578(IntPtr method, string arg1)
    {
        using godot_packed_byte_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe string godot_icall_1_579(IntPtr method, string arg1)
    {
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_1_580(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_1_581(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe Variant godot_icall_1_582(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_1_583(IntPtr method, IntPtr ptr, byte arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_584(IntPtr method, IntPtr ptr, ushort arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_585(IntPtr method, IntPtr ptr, ulong arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_586(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_587(IntPtr method, IntPtr ptr, double arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_588(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_589(IntPtr method, IntPtr ptr, ReadOnlySpan<string> arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_packed_string_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_590(IntPtr method, IntPtr ptr, Variant arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe ulong godot_icall_1_591(IntPtr method, string arg1)
    {
        ulong ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_1_592(IntPtr method, string arg1)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_593(IntPtr method, string arg1, int arg2)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_594(IntPtr method, string arg1, godot_bool arg2)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_2_595(IntPtr method, string arg1, string arg2)
    {
        using godot_packed_byte_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe string godot_icall_2_596(IntPtr method, string arg1, string arg2)
    {
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_3_597(IntPtr method, string arg1, string arg2, ReadOnlySpan<byte> arg3)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_598(IntPtr method, string arg1, string arg2, string arg3)
    {
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_3_599(IntPtr method, string arg1, int arg2, ReadOnlySpan<byte> arg3)
    {
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_600(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_601(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_602(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_603(IntPtr method, ReadOnlySpan<string> arg1)
    {
        using godot_packed_string_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, null);
    }

    internal static unsafe void godot_icall_1_604(IntPtr method, in Callable arg1)
    {
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_605(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe Rid godot_icall_11_606(IntPtr method, IntPtr ptr, godot_dictionary arg1, int arg2, float arg3, Transform2D* arg4, int arg5, int arg6, int arg7, int arg8, float arg9, long arg10, ReadOnlySpan<Color> arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        double arg3_in = arg3;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        double arg9_in = arg9;
        using godot_packed_color_array arg11_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg11);
        void** call_args = stackalloc void*[11] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in, &arg10, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_1_607(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Color[] godot_icall_1_608(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_color_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedColorArrayToSystemArray(ret);
    }

    internal static unsafe Vector2 godot_icall_7_609(IntPtr method, IntPtr ptr, string arg1, int arg2, float arg3, int arg4, int arg5, int arg6, int arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        double arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2 godot_icall_9_610(IntPtr method, IntPtr ptr, string arg1, int arg2, float arg3, int arg4, int arg5, int arg6, int arg7, int arg8, int arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        double arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        long arg9_in = arg9;
        void** call_args = stackalloc void*[9] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_11_611(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, Color* arg7, int arg8, int arg9, int arg10, float arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg8_in = arg8;
        long arg9_in = arg9;
        long arg10_in = arg10;
        double arg11_in = arg11;
        void** call_args = stackalloc void*[11] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, arg7, &arg8_in, &arg9_in, &arg10_in, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_13_612(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11, int arg12, float arg13)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        double arg13_in = arg13;
        void** call_args = stackalloc void*[13] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in, &arg12_in, &arg13_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_12_613(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11, float arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        double arg12_in = arg12;
        void** call_args = stackalloc void*[12] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in, &arg12_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_14_614(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, int arg8, Color* arg9, int arg10, int arg11, int arg12, int arg13, float arg14)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        long arg13_in = arg13;
        double arg14_in = arg14;
        void** call_args = stackalloc void*[14] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, arg9, &arg10_in, &arg11_in, &arg12_in, &arg13_in, &arg14_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_2_615(IntPtr method, IntPtr ptr, long arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe float godot_icall_6_616(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, long arg3, int arg4, Color* arg5, float arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg4_in = arg4;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3, &arg4_in, arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe float godot_icall_7_617(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, long arg3, int arg4, int arg5, Color* arg6, float arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg4_in = arg4;
        long arg5_in = arg5;
        double arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, arg2, &arg3, &arg4_in, &arg5_in, arg6, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe Rid godot_icall_9_618(IntPtr method, IntPtr ptr, godot_dictionary arg1, int arg2, float arg3, Transform2D* arg4, int arg5, int arg6, int arg7, int arg8, float arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        double arg3_in = arg3;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        double arg9_in = arg9;
        void** call_args = stackalloc void*[9] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_8_619(IntPtr method, IntPtr ptr, godot_dictionary arg1, int arg2, float arg3, Transform2D* arg4, int arg5, int arg6, int arg7, int arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        double arg3_in = arg3;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_620(IntPtr method, IntPtr ptr, godot_dictionary arg1, int arg2, float arg3, Transform2D* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe float godot_icall_6_621(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, long arg3, int arg4, int arg5, Color* arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3, &arg4_in, &arg5_in, arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe float godot_icall_5_622(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, long arg3, int arg4, Color* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3, &arg4_in, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_13_623(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, int arg8, Color* arg9, int arg10, int arg11, int arg12, int arg13)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        long arg13_in = arg13;
        void** call_args = stackalloc void*[13] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, arg9, &arg10_in, &arg11_in, &arg12_in, &arg13_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_11_624(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        void** call_args = stackalloc void*[11] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_12_625(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, int arg7, Color* arg8, int arg9, int arg10, int arg11, int arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg9_in = arg9;
        long arg10_in = arg10;
        long arg11_in = arg11;
        long arg12_in = arg12;
        void** call_args = stackalloc void*[12] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, arg8, &arg9_in, &arg10_in, &arg11_in, &arg12_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_10_626(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, string arg3, int arg4, float arg5, int arg6, Color* arg7, int arg8, int arg9, int arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        long arg8_in = arg8;
        long arg9_in = arg9;
        long arg10_in = arg10;
        void** call_args = stackalloc void*[10] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, arg7, &arg8_in, &arg9_in, &arg10_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_627(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_628(IntPtr method, IntPtr ptr, int arg1, godot_dictionary arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_629(IntPtr method, IntPtr ptr, int arg1, Transform2D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform2D godot_icall_1_630(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform2D ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_631(IntPtr method, IntPtr ptr, int arg1, int arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_632(IntPtr method, IntPtr ptr, int arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe long godot_icall_1_633(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_634(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_635(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_636(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_3_637(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_4_638(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, ReadOnlySpan<int> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        using godot_packed_int32_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int[] godot_icall_3_639(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_2_640(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_4_641(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_3_642(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_643(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_3_644(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_645(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, Rect2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rect2 godot_icall_3_646(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_647(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_3_648(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_649(IntPtr method, IntPtr ptr, int arg1, int arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_650(IntPtr method, IntPtr ptr, int arg1, int arg2, Vector2I* arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_3_651(IntPtr method, IntPtr ptr, int arg1, int arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_652(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, long arg3, long arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_3_653(IntPtr method, IntPtr ptr, int arg1, long arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Rid godot_icall_3_654(IntPtr method, godot_array arg1, godot_array arg2, uint arg3)
    {
        Rid ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_2_655(IntPtr method, IntPtr ptr, string arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_656(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_1_658(IntPtr method, IntPtr ptr, Variant arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_663(IntPtr method, godot_dictionary arg1)
    {
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe double[] godot_icall_0_664(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float64_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertNativePackedFloat64ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_1_665(IntPtr method, IntPtr ptr, ReadOnlySpan<double> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float64_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedFloat64Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe byte[] godot_icall_1_666(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe GodotObject godot_icall_1_667(IntPtr method, IntPtr arg1)
    {
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_4_668(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2, uint arg3, string arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_669(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, string arg2, IntPtr arg3, uint arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_670(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_4_671(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe int godot_icall_2_672(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_2_673(IntPtr method, IntPtr arg1, string arg2)
    {
        using godot_ref ret = default;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_4_674(IntPtr method, IntPtr arg1, godot_node_path arg2, IntPtr arg3, int arg4)
    {
        using godot_ref ret = default;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_2_675(IntPtr method, IntPtr arg1, godot_bool arg2)
    {
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, null);
    }

    internal static unsafe void godot_icall_1_676(IntPtr method, IntPtr arg1)
    {
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, null);
    }

    internal static unsafe void godot_icall_1_677(IntPtr method, IntPtr ptr, ReadOnlySpan<float> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_678(IntPtr method, IntPtr ptr, Transform3D* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_679(IntPtr method, IntPtr ptr, Quaternion* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe NodePath godot_icall_2_680(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_node_path ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return NodePath.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_2_681(IntPtr method, IntPtr ptr, godot_node_path arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Basis godot_icall_0_682(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Basis ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_683(IntPtr method, IntPtr ptr, Basis* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_684(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_2_685(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_686(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_5_687(IntPtr method, IntPtr ptr, Transform2D* arg1, Vector2* arg2, Color* arg3, Color* arg4, uint arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { arg1, arg2, arg3, arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_688(IntPtr method, IntPtr ptr, Transform3D* arg1, Vector3* arg2, Color* arg3, Color* arg4, uint arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { arg1, arg2, arg3, arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_3_689(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe float godot_icall_4_690(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Vector2* arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe Variant godot_icall_4_691(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Vector2* arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector2[] godot_icall_4_692(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Vector2* arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2 godot_icall_3_693(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Vector2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[3] { arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_4_694(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2, Vector2* arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_695(IntPtr method, IntPtr ptr, Vector2* arg1, ReadOnlySpan<Vector2> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int[] godot_icall_1_696(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2[] godot_icall_1_697(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_698(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_699(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, ReadOnlySpan<Vector2> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_3_700(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, float arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        double arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_4_701(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, float arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        double arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_1_702(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector3[] godot_icall_1_703(IntPtr method, IntPtr ptr, godot_array arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_704(IntPtr method, IntPtr ptr, Vector3* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_4_705(IntPtr method, IntPtr ptr, float arg1, float arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        double arg1_in = arg1;
        double arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_5_706(IntPtr method, IntPtr ptr, float arg1, float arg2, int arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        double arg1_in = arg1;
        double arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector3[] godot_icall_4_707(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Vector3* arg3, Vector3* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3 godot_icall_3_708(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Vector3* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[3] { arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_4_709(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Vector3* arg3, Vector3* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Variant godot_icall_5_710(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Vector3* arg3, Vector3* arg4, Vector3* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[5] { arg1, arg2, arg3, arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector3[] godot_icall_4_711(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Vector3* arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_4_712(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, float arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { arg1, arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_3_713(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, godot_array arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        void** call_args = stackalloc void*[3] { arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_2_714(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1, Plane* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_1_715(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_716(IntPtr method, IntPtr ptr, float arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_717(IntPtr method, IntPtr ptr, int arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Color godot_icall_1_718(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Color godot_icall_1_719(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_5_720(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, godot_string_name arg3, int arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_4_721(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, godot_string_name arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_722(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, godot_string_name arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_723(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, godot_string_name arg3, int arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_724(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_725(IntPtr method, IntPtr ptr, Vector2* arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_726(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_727(IntPtr method, IntPtr ptr, Rect2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector2[] godot_icall_2_728(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_4_729(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, godot_string_name arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_10_730(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, int arg3, Color* arg4, godot_bool arg5, int arg6, Color* arg7, IntPtr arg8, IntPtr arg9, godot_bool arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[10] { &arg1_in, &arg2, &arg3_in, arg4, &arg5, &arg6_in, arg7, &arg8, &arg9, &arg10 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_731(IntPtr method, IntPtr ptr, int arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_1_732(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_733(IntPtr method, IntPtr ptr, Vector3I* arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_1_734(IntPtr method, IntPtr ptr, Vector3I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Basis godot_icall_1_735(IntPtr method, IntPtr ptr, Vector3I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Basis ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Basis godot_icall_1_736(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Basis ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_1_737(IntPtr method, IntPtr ptr, Basis* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Vector3I godot_icall_1_738(IntPtr method, IntPtr ptr, Vector3* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3I ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_1_739(IntPtr method, IntPtr ptr, Vector3I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_740(IntPtr method, IntPtr ptr, Vector3I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_741(IntPtr method, IntPtr ptr, Vector3I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_742(IntPtr method, IntPtr ptr, Aabb* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector3I godot_icall_1_743(IntPtr method, IntPtr ptr, Vector3I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3I ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_744(IntPtr method, IntPtr ptr, godot_bool arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_746(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_1_747(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_748(IntPtr method, IntPtr ptr, string arg1, int arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_749(IntPtr method, IntPtr ptr, int arg1, string arg2, ReadOnlySpan<string> arg3, ReadOnlySpan<byte> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_packed_string_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg3);
        using godot_packed_byte_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_750(IntPtr method, IntPtr ptr, int arg1, string arg2, ReadOnlySpan<string> arg3, string arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_packed_string_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg3);
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe string godot_icall_1_751(IntPtr method, IntPtr ptr, godot_dictionary arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_4_752(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2, int arg3, string arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        long arg3_in = arg3;
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_753(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2, int arg3, ReadOnlySpan<byte> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        long arg3_in = arg3;
        using godot_packed_byte_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_754(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string[] godot_icall_2_755(IntPtr method, IntPtr ptr, string arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_3_756(IntPtr method, IntPtr ptr, godot_bool arg1, godot_bool arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_4_757(IntPtr method, int arg1, int arg2, godot_bool arg3, int arg4)
    {
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_5_758(IntPtr method, int arg1, int arg2, godot_bool arg3, int arg4, ReadOnlySpan<byte> arg5)
    {
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg4_in = arg4;
        using godot_packed_byte_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg5);
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_5_759(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_bool arg3, int arg4, ReadOnlySpan<byte> arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg4_in = arg4;
        using godot_packed_byte_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg5);
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_760(IntPtr method, IntPtr ptr, string arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_1_761(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_4_762(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2, godot_bool arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_3_763(IntPtr method, IntPtr ptr, godot_bool arg1, godot_bool arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_3_764(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_2_765(IntPtr method, IntPtr ptr, godot_bool arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_3_766(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_767(IntPtr method, IntPtr ptr, IntPtr arg1, Rect2I* arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_768(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, Rect2I* arg3, Vector2I* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_769(IntPtr method, IntPtr ptr, Rect2I* arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Color godot_icall_2_770(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_771(IntPtr method, IntPtr ptr, Vector2I* arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_772(IntPtr method, IntPtr ptr, int arg1, int arg2, Color* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_773(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_1_774(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_6_775(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, godot_bool arg5, godot_array arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_1_776(IntPtr method, IntPtr ptr, godot_array arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_1_777(IntPtr method, IntPtr ptr, Plane* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_3_778(IntPtr method, godot_array arg1, godot_array arg2, godot_bool arg3)
    {
        using godot_ref ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_7_779(IntPtr method, IntPtr ptr, int arg1, godot_array arg2, godot_array arg3, godot_dictionary arg4, IntPtr arg5, string arg6, ulong arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_string arg6_in = Marshaling.ConvertStringToNative(arg6);
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2, &arg3, &arg4, &arg5, &arg6_in, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int[] godot_icall_2_780(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_3_781(IntPtr method, IntPtr ptr, float arg1, float arg2, godot_array arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_2_782(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_3_783(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe float godot_icall_2_784(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe float godot_icall_2_785(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe Vector2 godot_icall_5_786(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_string_name arg3, godot_string_name arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_787(IntPtr method, IntPtr ptr, int arg1, float arg2, float arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_3_788(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_2_789(IntPtr method, IntPtr ptr, godot_string_name arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_3_790(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_bool arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_791(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_2_792(IntPtr method, IntPtr ptr, Transform2D* arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe string godot_icall_1_793(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe float godot_icall_1_794(IntPtr method, IntPtr ptr, godot_string_name arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe godot_bool godot_icall_2_795(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_3_796(IntPtr method, IntPtr ptr, IntPtr arg1, godot_string_name arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_1_797(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_2_798(IntPtr method, IntPtr ptr, godot_bool arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe int godot_icall_3_799(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_800(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_801(IntPtr method, IntPtr ptr, int arg1, Rect2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rect2 godot_icall_2_802(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_803(IntPtr method, IntPtr ptr, Vector2* arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_804(IntPtr method, IntPtr ptr, int arg1, int arg2, Vector3* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3 godot_icall_2_805(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_806(IntPtr method, IntPtr ptr, int arg1, int arg2, Quaternion* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Quaternion godot_icall_2_807(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Quaternion ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_4_808(IntPtr method, Variant arg1, string arg2, godot_bool arg3, godot_bool arg4)
    {
        using godot_string ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Variant godot_icall_1_809(IntPtr method, string arg1)
    {
        godot_variant ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_0_810(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_2_811(IntPtr method, Variant arg1, godot_bool arg2)
    {
        godot_variant ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_2_812(IntPtr method, IntPtr ptr, Variant arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_3_813(IntPtr method, IntPtr ptr, string arg1, Variant arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_814(IntPtr method, IntPtr ptr, Variant arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_815(IntPtr method, IntPtr ptr, string arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_3_816(IntPtr method, IntPtr ptr, int arg1, string arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_2_817(IntPtr method, IntPtr ptr, string arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_2_818(IntPtr method, IntPtr ptr, IntPtr arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Variant godot_icall_2_819(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_1_820(IntPtr method, IntPtr ptr, in Callable arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Variant godot_icall_2_821(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<Variant> arg2, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        int vararg_length = arg2.Length;
        int total_length = 1 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromString(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg2[i].NativeVar;
                call_args[1 + i] = new IntPtr(&varargs[i]);
            }
            godot_variant ret = NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
            return Variant.CreateTakingOwnershipOfDisposableValue(ret);
        }
    }

    internal static unsafe void godot_icall_3_822(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, string arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_2_823(IntPtr method, IntPtr ptr, int arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_4_824(IntPtr method, IntPtr ptr, godot_node_path arg1, Rect2* arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_825(IntPtr method, IntPtr ptr, Vector2* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string godot_icall_2_826(IntPtr method, IntPtr ptr, Variant arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe string godot_icall_1_827(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe byte[] godot_icall_1_828(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe GodotObject godot_icall_1_829(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_2_830(IntPtr method, IntPtr ptr, godot_bool arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_2_831(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_832(IntPtr method, IntPtr ptr, IntPtr arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_833(IntPtr method, IntPtr ptr, int arg1, Plane* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Plane godot_icall_1_834(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Plane ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_835(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<int> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_packed_int32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int[] godot_icall_1_836(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_837(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<float> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float[] godot_icall_1_838(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedFloat32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_839(IntPtr method, IntPtr ptr, int arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_840(IntPtr method, IntPtr ptr, int arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_841(IntPtr method, IntPtr ptr, int arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform3D godot_icall_1_842(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_843(IntPtr method, IntPtr ptr, ReadOnlySpan<float> arg1, ReadOnlySpan<float> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg1);
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_4_844(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, godot_string_name arg3, godot_array arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_845(IntPtr method, IntPtr ptr, IntPtr arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_1_846(IntPtr method, godot_string_name arg1)
    {
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, null);
    }

    internal static unsafe StringName godot_icall_0_847(IntPtr method)
    {
        godot_string_name ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_0_848(IntPtr method)
    {
        using godot_ref ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_1_849(IntPtr method, IntPtr ptr, Variant arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe Callable godot_icall_0_850(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return Marshaling.ConvertCallableToManaged(in ret);
    }

    internal static unsafe Vector2 godot_icall_1_851(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_852(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_853(IntPtr method, IntPtr ptr, Rid arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Callable godot_icall_1_854(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertCallableToManaged(in ret);
    }

    internal static unsafe void godot_icall_2_855(IntPtr method, IntPtr ptr, Rid arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_1_856(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe int godot_icall_5_857(IntPtr method, IntPtr ptr, Rid arg1, string arg2, Rid arg3, Variant arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        godot_variant arg4_in = (godot_variant)arg4.NativeVar;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_7_858(IntPtr method, IntPtr ptr, Rid arg1, string arg2, in Callable arg3, in Callable arg4, Variant arg5, int arg6, int arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        godot_variant arg5_in = (godot_variant)arg5.NativeVar;
        long arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_8_859(IntPtr method, IntPtr ptr, Rid arg1, IntPtr arg2, string arg3, in Callable arg4, in Callable arg5, Variant arg6, int arg7, int arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        using godot_callable arg5_in = Marshaling.ConvertCallableToNative(in arg5);
        godot_variant arg6_in = (godot_variant)arg6.NativeVar;
        long arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_9_860(IntPtr method, IntPtr ptr, Rid arg1, string arg2, int arg3, int arg4, in Callable arg5, in Callable arg6, Variant arg7, int arg8, int arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        long arg4_in = arg4;
        using godot_callable arg5_in = Marshaling.ConvertCallableToNative(in arg5);
        using godot_callable arg6_in = Marshaling.ConvertCallableToNative(in arg6);
        godot_variant arg7_in = (godot_variant)arg7.NativeVar;
        long arg8_in = arg8;
        long arg9_in = arg9;
        void** call_args = stackalloc void*[9] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_861(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_862(IntPtr method, IntPtr ptr, Rid arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_863(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_864(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_2_865(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Callable godot_icall_2_866(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertCallableToManaged(in ret);
    }

    internal static unsafe Variant godot_icall_2_867(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_2_868(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Rid godot_icall_2_869(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_2_870(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_871(IntPtr method, IntPtr ptr, Rid arg1, int arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_872(IntPtr method, IntPtr ptr, Rid arg1, int arg2, Rid arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_873(IntPtr method, IntPtr ptr, Rid arg1, int arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_3_874(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_1_875(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_4_876(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, IntPtr arg3, in Callable arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_877(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_878(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_879(IntPtr method, IntPtr ptr, ReadOnlySpan<float> arg1, ReadOnlySpan<int> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg1);
        using godot_packed_int32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_880(IntPtr method, IntPtr ptr, IntPtr arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_881(IntPtr method, IntPtr ptr, godot_array arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_882(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_883(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1, float arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_884(IntPtr method, IntPtr ptr, ReadOnlySpan<long> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedInt64Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_885(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<Vector2> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2[] godot_icall_5_886(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Vector2* arg3, godot_bool arg4, uint arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, arg2, arg3, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2 godot_icall_2_887(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_888(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_889(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe uint godot_icall_1_890(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (uint)(ret);
    }

    internal static unsafe Vector2 godot_icall_3_891(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_892(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe ulong godot_icall_1_893(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_894(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_1_895(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_896(IntPtr method, IntPtr ptr, Rid arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform2D godot_icall_1_897(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform2D ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_898(IntPtr method, IntPtr ptr, Rid arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_2_899(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rect2 godot_icall_1_900(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_901(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_902(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector2> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2[] godot_icall_1_903(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2[] godot_icall_2_904(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_905(IntPtr method, IntPtr ptr, Rid arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3 godot_icall_1_906(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3[] godot_icall_5_907(IntPtr method, IntPtr ptr, Rid arg1, Vector3* arg2, Vector3* arg3, godot_bool arg4, uint arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, arg2, arg3, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3 godot_icall_4_908(IntPtr method, IntPtr ptr, Rid arg1, Vector3* arg2, Vector3* arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[4] { &arg1, arg2, arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_2_909(IntPtr method, IntPtr ptr, Rid arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_910(IntPtr method, IntPtr ptr, Rid arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_3_911(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_912(IntPtr method, IntPtr ptr, Rid arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_913(IntPtr method, IntPtr ptr, Rid arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform3D godot_icall_1_914(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_2_915(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Aabb godot_icall_1_916(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Aabb ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_917(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector3> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3[] godot_icall_1_918(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_2_919(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_0_920(IntPtr method)
    {
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, null);
    }

    internal static unsafe Godot.Collections.Array godot_icall_0_921(IntPtr method)
    {
        godot_array ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_922(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_2_923(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_1_924(IntPtr method, IntPtr ptr, godot_node_path arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_3_925(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_4_926(IntPtr method, IntPtr ptr, string arg1, string arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_927(IntPtr method, IntPtr ptr, godot_node_path arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_928(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_array arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string godot_icall_2_929(IntPtr method, IntPtr ptr, string arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe string godot_icall_4_930(IntPtr method, IntPtr ptr, string arg1, godot_string_name arg2, int arg3, godot_string_name arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_2_931(IntPtr method, IntPtr ptr, godot_string_name arg1, ReadOnlySpan<Variant> arg2, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        int vararg_length = arg2.Length;
        int total_length = 1 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromStringName(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg2[i].NativeVar;
                call_args[1 + i] = new IntPtr(&varargs[i]);
            }
            using godot_variant vararg_ret = NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
            ret = VariantUtils.ConvertToInt64(vararg_ret);
            return (int)(ret);
        }
    }

    internal static unsafe int godot_icall_3_932(IntPtr method, IntPtr ptr, long arg1, godot_string_name arg2, ReadOnlySpan<Variant> arg3, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        int vararg_length = arg3.Length;
        int total_length = 2 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromInt(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            using godot_variant arg2_in = VariantUtils.CreateFromStringName(arg2);
            call_args[1] = new IntPtr(&arg2_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg3[i].NativeVar;
                call_args[2 + i] = new IntPtr(&varargs[i]);
            }
            using godot_variant vararg_ret = NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
            ret = VariantUtils.ConvertToInt64(vararg_ret);
            return (int)(ret);
        }
    }

    internal static unsafe Variant godot_icall_2_933(IntPtr method, IntPtr ptr, godot_string_name arg1, ReadOnlySpan<Variant> arg2, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        int vararg_length = arg2.Length;
        int total_length = 1 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromStringName(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg2[i].NativeVar;
                call_args[1 + i] = new IntPtr(&varargs[i]);
            }
            godot_variant ret = NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
            return Variant.CreateTakingOwnershipOfDisposableValue(ret);
        }
    }

    internal static unsafe void godot_icall_2_934(IntPtr method, IntPtr ptr, float arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform2D godot_icall_1_935(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform2D ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_936(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, Transform3D* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_937(IntPtr method, IntPtr ptr, Vector3* arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_938(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_939(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Vector3* arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { arg1, arg2, arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_2_940(IntPtr method, IntPtr ptr, float arg1, float arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        double arg1_in = arg1;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe float godot_icall_3_941(IntPtr method, IntPtr ptr, float arg1, float arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        double arg1_in = arg1;
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe GodotObject godot_icall_5_942(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_bool arg3, godot_bool arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_6_943(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_bool arg3, godot_bool arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3, &arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Godot.Collections.Array godot_icall_5_944(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, godot_bool arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_6_945(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, godot_bool arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3_in, &arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_4_946(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe string[] godot_icall_7_947(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, string arg4, int arg5, int arg6, godot_bool arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_5_948(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2, godot_array arg3, godot_bool arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_3_949(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe int godot_icall_3_950(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_1_951(IntPtr method, IntPtr ptr, ReadOnlySpan<string> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_string_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_952(IntPtr method, IntPtr ptr, godot_bool arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string godot_icall_2_953(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_954(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_2_955(IntPtr method, IntPtr ptr, godot_node_path arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_1_956(IntPtr method, IntPtr ptr, godot_node_path arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_2_957(IntPtr method, IntPtr ptr, godot_string_name arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_2_958(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe int godot_icall_3_959(IntPtr method, IntPtr ptr, godot_string_name arg1, in Callable arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_2_960(IntPtr method, IntPtr ptr, godot_string_name arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_2_961(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe string godot_icall_4_962(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, int arg3, godot_string_name arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe godot_bool godot_icall_3_963(IntPtr method, IntPtr ptr, ulong arg1, string arg2, godot_array arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_964(IntPtr method, godot_bool arg1)
    {
        godot_bool ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe ulong godot_icall_1_965(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_1_966(IntPtr method, IntPtr ptr, ulong arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe void godot_icall_3_967(IntPtr method, IntPtr ptr, long arg1, ulong arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_2_968(IntPtr method, IntPtr ptr, string arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe ulong godot_icall_7_969(IntPtr method, IntPtr ptr, ulong arg1, ulong arg2, long arg3, uint arg4, uint arg5, uint arg6, uint arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3, &arg4_in, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe ulong godot_icall_1_970(IntPtr method, IntPtr ptr, ulong arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_1_971(IntPtr method, IntPtr ptr, ulong arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_972(IntPtr method, IntPtr ptr, int arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2 godot_icall_2_973(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_2_974(IntPtr method, IntPtr ptr, ulong arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_6_975(IntPtr method, IntPtr ptr, string arg1, string arg2, string arg3, string arg4, string arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        using godot_string arg5_in = Marshaling.ConvertStringToNative(arg5);
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_976(IntPtr method, IntPtr ptr, Transform3D* arg1, ReadOnlySpan<Vector2> arg2, ReadOnlySpan<int> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        using godot_packed_int32_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg3);
        void** call_args = stackalloc void*[3] { arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_977(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe string[] godot_icall_1_978(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe string godot_icall_1_979(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe string godot_icall_2_980(IntPtr method, IntPtr ptr, Rid arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe godot_bool godot_icall_2_981(IntPtr method, IntPtr ptr, Rid arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Transform3D godot_icall_2_982(IntPtr method, IntPtr ptr, Rid arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_2_983(IntPtr method, IntPtr ptr, int arg1, in Callable arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_3_984(IntPtr method, IntPtr ptr, Transform3D* arg1, Rid arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[3] { arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_3_985(IntPtr method, IntPtr ptr, IntPtr arg1, Rid arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_5_986(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2, IntPtr arg3, IntPtr arg4, in Callable arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg5_in = Marshaling.ConvertCallableToNative(in arg5);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_4_987(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2, IntPtr arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_2_988(IntPtr method, IntPtr ptr, Transform3D* arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Transform3D godot_icall_1_989(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe uint godot_icall_1_990(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (uint)(ret);
    }

    internal static unsafe Variant godot_icall_2_991(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector2[] godot_icall_2_992(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_2_993(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe GodotObject godot_icall_1_994(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Rid godot_icall_1_995(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe ulong godot_icall_1_996(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_4_997(IntPtr method, IntPtr ptr, godot_array arg1, IntPtr arg2, in Callable arg3, in Callable arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_4_998(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2, IntPtr arg3, in Callable arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_4_999(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<long> arg2, IntPtr arg3, in Callable arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_packed_int64_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedInt64Array(arg2);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Rid godot_icall_4_1000(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2, ReadOnlySpan<long> arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        using godot_packed_int64_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedInt64Array(arg3);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_3_1001(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_2_1002(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe byte[] godot_icall_2_1003(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_2_1004(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe float[] godot_icall_2_1005(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedFloat32ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2[] godot_icall_2_1006(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Vector3[] godot_icall_2_1007(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector3ArrayToSystemArray(ret);
    }

    internal static unsafe Rid godot_icall_3_1008(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2, ulong arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1009(IntPtr method, IntPtr ptr, Rid arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_3_1010(IntPtr method, IntPtr ptr, godot_array arg1, IntPtr arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_1011(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_4_1012(IntPtr method, IntPtr ptr, string arg1, int arg2, string arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_1013(IntPtr method, IntPtr ptr, string arg1, string arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_1014(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<byte> arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_1_1015(IntPtr method, IntPtr ptr, Variant arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_1016(IntPtr method, IntPtr ptr, Variant arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_1017(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_1018(IntPtr method, IntPtr ptr, int arg1, string arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Transform3D godot_icall_2_1019(IntPtr method, Transform3D* arg1, int arg2)
    {
        Transform3D ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1020(IntPtr method, IntPtr ptr, godot_string_name arg1, in Callable arg2, godot_array arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1021(IntPtr method, IntPtr ptr, godot_string_name arg1, in Callable arg2, godot_array arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1022(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_4_1023(IntPtr method, IntPtr ptr, Vector2* arg1, godot_bool arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { arg1, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe godot_bool godot_icall_5_1024(IntPtr method, IntPtr ptr, Transform2D* arg1, Vector2* arg2, IntPtr arg3, float arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[5] { arg1, arg2, &arg3, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_5_1025(IntPtr method, IntPtr ptr, Vector3* arg1, godot_bool arg2, float arg3, godot_bool arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        double arg3_in = arg3;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { arg1, &arg2, &arg3_in, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe godot_bool godot_icall_6_1026(IntPtr method, IntPtr ptr, Transform3D* arg1, Vector3* arg2, IntPtr arg3, float arg4, godot_bool arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        double arg4_in = arg4;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { arg1, arg2, &arg3, &arg4_in, &arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_1027(IntPtr method, IntPtr ptr, Vector2* arg1, Vector2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_1_1028(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_1029(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe float[] godot_icall_1_1030(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedFloat32ArrayToSystemArray(ret);
    }

    internal static unsafe godot_bool godot_icall_2_1031(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_4_1032(IntPtr method, Vector2* arg1, Vector2* arg2, uint arg3, godot_array arg4)
    {
        using godot_ref ret = default;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { arg1, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_4_1033(IntPtr method, Vector3* arg1, Vector3* arg2, uint arg3, godot_array arg4)
    {
        using godot_ref ret = default;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { arg1, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_1034(IntPtr method, IntPtr ptr, Rid arg1, int arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_2_1035(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_4_1036(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Transform2D* arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1037(IntPtr method, IntPtr ptr, Rid arg1, int arg2, Transform2D* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform2D godot_icall_2_1038(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform2D ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_5_1039(IntPtr method, IntPtr ptr, Rid arg1, int arg2, godot_bool arg3, float arg4, Vector2* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3, &arg4_in, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1040(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Vector2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1041(IntPtr method, IntPtr ptr, Rid arg1, in Callable arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_3_1042(IntPtr method, IntPtr ptr, Rid arg1, IntPtr arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1043(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Rid arg3, Rid arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1044(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Vector2* arg3, Vector2* arg4, Rid arg5, Rid arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[6] { &arg1, arg2, arg3, arg4, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1045(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Vector2* arg3, Rid arg4, Rid arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, arg2, arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1046(IntPtr method, IntPtr ptr, Rid arg1, int arg2, godot_bool arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1047(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Transform3D* arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1048(IntPtr method, IntPtr ptr, Rid arg1, int arg2, Transform3D* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Transform3D godot_icall_2_1049(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1050(IntPtr method, IntPtr ptr, Rid arg1, Vector3* arg2, Vector3* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1051(IntPtr method, IntPtr ptr, Rid arg1, int arg2, Vector3* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1052(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector3* arg3, Rid arg4, Vector3* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, arg3, &arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1053(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Transform3D* arg3, Rid arg4, Transform3D* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, arg3, &arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1054(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_3_1055(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_4_1056(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_3_1057(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_1058(IntPtr method, IntPtr ptr, Rid arg1, Quaternion* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Quaternion godot_icall_1_1059(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Quaternion ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_1_1060(IntPtr method, IntPtr ptr, Vector3I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3I godot_icall_0_1061(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3I ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_1062(IntPtr method, IntPtr ptr, godot_node_path arg1, ReadOnlySpan<float> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1063(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector2> arg1, ReadOnlySpan<int> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg1);
        using godot_packed_int32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1064(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1065(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1066(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1067(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, int arg3, godot_bool arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3_in, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1068(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1069(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, int arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1070(IntPtr method, IntPtr ptr, string arg1, string arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1071(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1072(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1073(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, godot_bool arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_1074(IntPtr method, godot_bool arg1)
    {
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_0_1075(IntPtr method)
    {
        godot_bool ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return ret;
    }

    internal static unsafe Variant godot_icall_2_1076(IntPtr method, IntPtr ptr, string arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Variant godot_icall_2_1077(IntPtr method, IntPtr ptr, godot_string_name arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_3_1078(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_1_1079(IntPtr method, IntPtr ptr, Variant arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_2_1080(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<byte> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe long godot_icall_1_1081(IntPtr method, IntPtr ptr, ReadOnlySpan<float> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_float32_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_3_1082(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Godot.Collections.Array godot_icall_3_1083(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_5_1084(IntPtr method, IntPtr ptr, string arg1, string arg2, godot_bool arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe string godot_icall_1_1085(IntPtr method, IntPtr ptr, Variant arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Rid godot_icall_10_1086(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, int arg3, uint arg4, int arg5, Vector2I* arg6, uint arg7, uint arg8, godot_bool arg9, godot_bool arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[10] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, arg6, &arg7_in, &arg8_in, &arg9, &arg10 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_5_1087(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, IntPtr arg3, IntPtr arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_1088(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_string_name arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1089(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_6_1090(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, uint arg3, uint arg4, uint arg5, uint arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_7_1091(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, uint arg3, uint arg4, uint arg5, uint arg6, IntPtr arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_3_1092(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_1_1093(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1094(IntPtr method, IntPtr ptr, uint arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_9_1095(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, int arg3, uint arg4, int arg5, Vector2I* arg6, uint arg7, uint arg8, godot_bool arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[9] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, arg6, &arg7_in, &arg8_in, &arg9 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_1_1096(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector3 godot_icall_1_1097(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3 ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Projection godot_icall_1_1098(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Projection ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1099(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2, godot_array arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1100(IntPtr method, IntPtr ptr, IntPtr arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_7_1101(IntPtr method, IntPtr ptr, IntPtr arg1, Rid arg2, uint arg3, uint arg4, uint arg5, int arg6, uint arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_10_1102(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, ulong arg5, ulong arg6, ulong arg7, ulong arg8, ulong arg9, ulong arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[10] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5, &arg6, &arg7, &arg8, &arg9, &arg10 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_1103(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, ReadOnlySpan<byte> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_2_1104(IntPtr method, IntPtr ptr, Rid arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_3_1105(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_9_1106(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector3* arg3, Vector3* arg4, Vector3* arg5, uint arg6, uint arg7, uint arg8, uint arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        long arg9_in = arg9;
        void** call_args = stackalloc void*[9] { &arg1, &arg2, arg3, arg4, arg5, &arg6_in, &arg7_in, &arg8_in, &arg9_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_6_1107(IntPtr method, IntPtr ptr, Rid arg1, Color* arg2, uint arg3, uint arg4, uint arg5, uint arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_1_1108(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe long godot_icall_2_1109(IntPtr method, IntPtr ptr, godot_array arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_3_1110(IntPtr method, IntPtr ptr, godot_array arg1, godot_array arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_1111(IntPtr method, IntPtr ptr, long arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Rid godot_icall_3_1112(IntPtr method, IntPtr ptr, godot_array arg1, long arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_1113(IntPtr method, IntPtr ptr, godot_array arg1, godot_array arg2, long arg3, uint arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1114(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_1_1115(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_1_1116(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1117(IntPtr method, IntPtr ptr, uint arg1, ReadOnlySpan<byte> arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_1_1118(IntPtr method, IntPtr ptr, godot_array arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_1119(IntPtr method, IntPtr ptr, uint arg1, long arg2, godot_array arg3, ReadOnlySpan<long> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        using godot_packed_int64_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedInt64Array(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_5_1120(IntPtr method, IntPtr ptr, uint arg1, int arg2, ReadOnlySpan<byte> arg3, godot_bool arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1121(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_2_1122(IntPtr method, IntPtr ptr, IntPtr arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe byte[] godot_icall_2_1123(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe Rid godot_icall_2_1124(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1125(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_1126(IntPtr method, IntPtr ptr, uint arg1, ReadOnlySpan<byte> arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1127(IntPtr method, IntPtr ptr, uint arg1, int arg2, ReadOnlySpan<byte> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1128(IntPtr method, IntPtr ptr, godot_array arg1, Rid arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_5_1129(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, uint arg3, uint arg4, uint arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_1130(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, uint arg3, ReadOnlySpan<byte> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        using godot_packed_byte_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_1131(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_3_1132(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_4_1133(IntPtr method, IntPtr ptr, Rid arg1, in Callable arg2, uint arg3, uint arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Rid godot_icall_11_1134(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3, int arg4, IntPtr arg5, IntPtr arg6, IntPtr arg7, IntPtr arg8, int arg9, uint arg10, godot_array arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg4_in = arg4;
        long arg9_in = arg9;
        long arg10_in = arg10;
        void** call_args = stackalloc void*[11] { &arg1, &arg2, &arg3, &arg4_in, &arg5, &arg6, &arg7, &arg8, &arg9_in, &arg10_in, &arg11 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1135(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_1136(IntPtr method, IntPtr ptr, godot_array arg1, godot_array arg2, godot_array arg3, uint arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1137(IntPtr method, IntPtr ptr, godot_array arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1138(IntPtr method, IntPtr ptr, uint arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_1139(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Rid godot_icall_2_1140(IntPtr method, IntPtr ptr, Rid arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_2_1141(IntPtr method, IntPtr ptr, Rid arg1, uint arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_2_1142(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_1143(IntPtr method, IntPtr ptr, Rid arg1, long arg2, uint arg3, ReadOnlySpan<int> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        using godot_packed_int32_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe long godot_icall_2_1144(IntPtr method, IntPtr ptr, int arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_7_1145(IntPtr method, IntPtr ptr, Rid arg1, int arg2, ReadOnlySpan<Color> arg3, float arg4, uint arg5, Rect2* arg6, uint arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        using godot_packed_color_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg3);
        double arg4_in = arg4;
        long arg5_in = arg5;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, arg6, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long[] godot_icall_11_1146(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, int arg3, int arg4, int arg5, int arg6, ReadOnlySpan<Color> arg7, float arg8, uint arg9, Rect2* arg10, godot_array arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        using godot_packed_color_array arg7_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg7);
        double arg8_in = arg8;
        long arg9_in = arg9;
        void** call_args = stackalloc void*[11] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in, arg10, &arg11 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_1147(IntPtr method, IntPtr ptr, long arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1148(IntPtr method, IntPtr ptr, long arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1149(IntPtr method, IntPtr ptr, long arg1, Rid arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1150(IntPtr method, IntPtr ptr, long arg1, long arg2, uint arg3, godot_array arg4, ReadOnlySpan<long> arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        using godot_packed_int64_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedInt64Array(arg5);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3_in, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1151(IntPtr method, IntPtr ptr, long arg1, ReadOnlySpan<byte> arg2, uint arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1152(IntPtr method, IntPtr ptr, long arg1, godot_bool arg2, uint arg3, uint arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1153(IntPtr method, IntPtr ptr, long arg1, godot_bool arg2, Rid arg3, uint arg4, uint arg5, uint arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1154(IntPtr method, IntPtr ptr, long arg1, Rect2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe long[] godot_icall_1_1155(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_4_1156(IntPtr method, IntPtr ptr, long arg1, uint arg2, uint arg3, uint arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1157(IntPtr method, IntPtr ptr, long arg1, uint arg2, Rid arg3, uint arg4, uint arg5, uint arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, &arg3, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe ulong godot_icall_1_1158(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_1_1159(IntPtr method, IntPtr ptr, uint arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe ulong godot_icall_3_1160(IntPtr method, IntPtr ptr, int arg1, Rid arg2, ulong arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_9_1161(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, ulong arg5, ulong arg6, ulong arg7, ulong arg8, ulong arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[9] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5, &arg6, &arg7, &arg8, &arg9 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_6_1162(IntPtr method, IntPtr ptr, IntPtr arg1, Rid arg2, uint arg3, uint arg4, uint arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_4_1163(IntPtr method, IntPtr ptr, uint arg1, int arg2, ReadOnlySpan<byte> arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1164(IntPtr method, IntPtr ptr, uint arg1, ReadOnlySpan<byte> arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1165(IntPtr method, IntPtr ptr, uint arg1, ReadOnlySpan<byte> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_10_1166(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, int arg4, int arg5, ReadOnlySpan<Color> arg6, float arg7, uint arg8, Rect2* arg9, uint arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        using godot_packed_color_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg6);
        double arg7_in = arg7;
        long arg8_in = arg8;
        long arg10_in = arg10;
        void** call_args = stackalloc void*[10] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, arg9, &arg10_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_9_1167(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, int arg4, int arg5, ReadOnlySpan<Color> arg6, float arg7, uint arg8, Rect2* arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        using godot_packed_color_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg6);
        double arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[9] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, arg9 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_1168(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_7_1169(IntPtr method, IntPtr ptr, Rid arg1, Color* arg2, uint arg3, uint arg4, uint arg5, uint arg6, int arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_10_1170(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector3* arg3, Vector3* arg4, Vector3* arg5, uint arg6, uint arg7, uint arg8, uint arg9, int arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        long arg9_in = arg9;
        long arg10_in = arg10;
        void** call_args = stackalloc void*[10] { &arg1, &arg2, arg3, arg4, arg5, &arg6_in, &arg7_in, &arg8_in, &arg9_in, &arg10_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_1171(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, ReadOnlySpan<byte> arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        using godot_packed_byte_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg3);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_4_1172(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, uint arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_5_1173(IntPtr method, IntPtr ptr, Rid arg1, uint arg2, uint arg3, ReadOnlySpan<byte> arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        using godot_packed_byte_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg4);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe long godot_icall_1_1174(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_10_1175(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, int arg4, int arg5, ReadOnlySpan<Color> arg6, float arg7, uint arg8, Rect2* arg9, godot_array arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        using godot_packed_color_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg6);
        double arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[10] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, arg9, &arg10 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_1_1176(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_6_1177(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, godot_bool arg5, godot_array arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_8_1178(IntPtr method, IntPtr ptr, int arg1, int arg2, ulong arg3, int arg4, int arg5, int arg6, int arg7, int arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg6_in = arg6;
        long arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1_in, &arg2_in, &arg3, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_5_1179(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, Color* arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1180(IntPtr method, IntPtr ptr, Rid arg1, IntPtr arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1181(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1182(IntPtr method, IntPtr ptr, godot_array arg1, Rect2I* arg2, Rid arg3, Color* arg4, godot_array arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3, arg4, &arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_2_1183(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe ulong godot_icall_2_1184(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        ulong ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Variant godot_icall_2_1185(IntPtr method, IntPtr ptr, Rid arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_4_1186(IntPtr method, IntPtr ptr, Rid arg1, godot_string_name arg2, Rid arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_3_1187(IntPtr method, IntPtr ptr, Rid arg1, godot_string_name arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1188(IntPtr method, IntPtr ptr, Rid arg1, godot_string_name arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe uint godot_icall_3_1189(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (uint)(ret);
    }

    internal static unsafe uint godot_icall_2_1190(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (uint)(ret);
    }

    internal static unsafe void godot_icall_2_1191(IntPtr method, IntPtr ptr, Rid arg1, godot_dictionary arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1192(IntPtr method, IntPtr ptr, Rid arg1, int arg2, godot_array arg3, godot_array arg4, godot_dictionary arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, &arg3, &arg4, &arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_1193(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_1194(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_2_1195(IntPtr method, IntPtr ptr, Rid arg1, Aabb* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1196(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, ReadOnlySpan<byte> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        using godot_packed_byte_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg4);
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1197(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, godot_bool arg4, godot_bool arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, &arg3_in, &arg4, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1198(IntPtr method, IntPtr ptr, Rid arg1, int arg2, Color* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Color godot_icall_2_1199(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Color ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_1200(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<float> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float[] godot_icall_1_1201(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedFloat32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_3_1202(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<float> arg2, ReadOnlySpan<float> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        using godot_packed_float32_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1203(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3, float arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1204(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1205(IntPtr method, IntPtr ptr, Rid arg1, float arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_8_1206(IntPtr method, IntPtr ptr, Rid arg1, Transform3D* arg2, Aabb* arg3, Vector3I* arg4, ReadOnlySpan<byte> arg5, ReadOnlySpan<byte> arg6, ReadOnlySpan<byte> arg7, ReadOnlySpan<int> arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg5);
        using godot_packed_byte_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg6);
        using godot_packed_byte_array arg7_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg7);
        using godot_packed_int32_array arg8_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg8);
        void** call_args = stackalloc void*[8] { &arg1, arg2, arg3, arg4, &arg5_in, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector3I godot_icall_1_1207(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector3I ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe byte[] godot_icall_1_1208(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_1_1209(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_3_1210(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1211(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector3> arg2, ReadOnlySpan<Color> arg3, ReadOnlySpan<int> arg4, ReadOnlySpan<int> arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg2);
        using godot_packed_color_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg3);
        using godot_packed_int32_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg4);
        using godot_packed_int32_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg5);
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Color[] godot_icall_1_1212(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_color_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedColorArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_3_1213(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1214(IntPtr method, IntPtr ptr, Rid arg1, Transform3D* arg2, Vector3* arg3, Color* arg4, Color* arg5, uint arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, arg3, arg4, arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1215(IntPtr method, IntPtr ptr, Rid arg1, in Callable arg2, in Callable arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg2_in = Marshaling.ConvertCallableToNative(in arg2);
        using godot_callable arg3_in = Marshaling.ConvertCallableToNative(in arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1216(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector3> arg2, ReadOnlySpan<int> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg2);
        using godot_packed_int32_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1217(IntPtr method, IntPtr ptr, Rid arg1, float arg2, float arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1218(IntPtr method, IntPtr ptr, Rid arg1, float arg2, Vector2* arg3, float arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1219(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2, godot_array arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1220(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1221(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1222(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Transform2D* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1223(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe double godot_icall_1_1224(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_4_1225(IntPtr method, IntPtr ptr, Rid arg1, float arg2, godot_bool arg3, Vector2I* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        double arg2_in = arg2;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_2_1226(IntPtr method, IntPtr ptr, Rid arg1, Basis* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1227(IntPtr method, IntPtr ptr, Rid arg1, Color* arg2, int arg3, float arg4, float arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_13_1228(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, ReadOnlySpan<float> arg3, float arg4, float arg5, float arg6, float arg7, int arg8, float arg9, float arg10, float arg11, float arg12, Rid arg13)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_float32_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg3);
        double arg4_in = arg4;
        double arg5_in = arg5;
        double arg6_in = arg6;
        double arg7_in = arg7;
        long arg8_in = arg8;
        double arg9_in = arg9;
        double arg10_in = arg10;
        double arg11_in = arg11;
        double arg12_in = arg12;
        void** call_args = stackalloc void*[13] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in, &arg10_in, &arg11_in, &arg12_in, &arg13 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1229(IntPtr method, IntPtr ptr, Rid arg1, int arg2, float arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_1230(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3, float arg4, float arg5, godot_bool arg6, Rid arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1231(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, int arg3, float arg4, float arg5, float arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_10_1232(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3, float arg4, float arg5, float arg6, float arg7, float arg8, float arg9, float arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        double arg6_in = arg6;
        double arg7_in = arg7;
        double arg8_in = arg8;
        double arg9_in = arg9;
        double arg10_in = arg10;
        void** call_args = stackalloc void*[10] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in, &arg10_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_11_1233(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, Color* arg3, float arg4, float arg5, float arg6, float arg7, float arg8, float arg9, float arg10, int arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        double arg5_in = arg5;
        double arg6_in = arg6;
        double arg7_in = arg7;
        double arg8_in = arg8;
        double arg9_in = arg9;
        double arg10_in = arg10;
        long arg11_in = arg11;
        void** call_args = stackalloc void*[11] { &arg1, &arg2, arg3, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in, &arg10_in, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_11_1234(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, int arg3, float arg4, int arg5, godot_bool arg6, float arg7, godot_bool arg8, float arg9, float arg10, float arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        double arg4_in = arg4;
        long arg5_in = arg5;
        double arg7_in = arg7;
        double arg9_in = arg9;
        double arg10_in = arg10;
        double arg11_in = arg11;
        void** call_args = stackalloc void*[11] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6, &arg7_in, &arg8, &arg9_in, &arg10_in, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_14_1235(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3, Color* arg4, Color* arg5, float arg6, float arg7, float arg8, float arg9, float arg10, godot_bool arg11, float arg12, float arg13, float arg14)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg6_in = arg6;
        double arg7_in = arg7;
        double arg8_in = arg8;
        double arg9_in = arg9;
        double arg10_in = arg10;
        double arg12_in = arg12;
        double arg13_in = arg13;
        double arg14_in = arg14;
        void** call_args = stackalloc void*[14] { &arg1, &arg2, &arg3_in, arg4, arg5, &arg6_in, &arg7_in, &arg8_in, &arg9_in, &arg10_in, &arg11, &arg12_in, &arg13_in, &arg14_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1236(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, float arg3, int arg4, float arg5, float arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg3_in = arg3;
        long arg4_in = arg4;
        double arg5_in = arg5;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_3_1237(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_1238(IntPtr method, IntPtr ptr, godot_bool arg1, float arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_8_1239(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3, float arg4, godot_bool arg5, float arg6, float arg7, float arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg4_in = arg4;
        double arg6_in = arg6;
        double arg7_in = arg7;
        double arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1240(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, float arg3, float arg4, float arg5, float arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_2_1241(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1242(IntPtr method, IntPtr ptr, Rid arg1, float arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1243(IntPtr method, IntPtr ptr, Rid arg1, float arg2, float arg3, float arg4, float arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        double arg4_in = arg4;
        double arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1244(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Rect2* arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe long[] godot_icall_2_1245(IntPtr method, IntPtr ptr, Aabb* arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe long[] godot_icall_3_1246(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2, Rid arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        void** call_args = stackalloc void*[3] { arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe long[] godot_icall_2_1247(IntPtr method, IntPtr ptr, godot_array arg1, Rid arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int64_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt64ArrayToSystemArray(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_3_1248(IntPtr method, IntPtr ptr, Rid arg1, godot_array arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_1249(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1250(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1251(IntPtr method, IntPtr ptr, Rid arg1, Color* arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1252(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, Rect2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1253(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Vector2* arg3, Color* arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, arg2, arg3, arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1254(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector2> arg2, ReadOnlySpan<Color> arg3, float arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        using godot_packed_color_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg3);
        double arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1255(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Color* arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1256(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, float arg3, Color* arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3_in, arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1257(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, float arg3, float arg4, Color* arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3_in, &arg4_in, arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1258(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Rid arg3, godot_bool arg4, Color* arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3, &arg4, arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_8_1259(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Rid arg3, Rect2* arg4, Color* arg5, int arg6, float arg7, float arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg6_in = arg6;
        double arg7_in = arg7;
        double arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1, arg2, &arg3, arg4, arg5, &arg6_in, &arg7_in, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1260(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Rid arg3, Rect2* arg4, Color* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3, arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_1261(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Rid arg3, Rect2* arg4, Color* arg5, godot_bool arg6, godot_bool arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[7] { &arg1, arg2, &arg3, arg4, arg5, &arg6, &arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_10_1262(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Rect2* arg3, Rid arg4, Vector2* arg5, Vector2* arg6, int arg7, int arg8, godot_bool arg9, Color* arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg7_in = arg7;
        long arg8_in = arg8;
        void** call_args = stackalloc void*[10] { &arg1, arg2, arg3, &arg4, arg5, arg6, &arg7_in, &arg8_in, &arg9, arg10 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1263(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector2> arg2, ReadOnlySpan<Color> arg3, ReadOnlySpan<Vector2> arg4, Rid arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        using godot_packed_color_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg3);
        using godot_packed_vector2_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg4);
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_9_1264(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<int> arg2, ReadOnlySpan<Vector2> arg3, ReadOnlySpan<Color> arg4, ReadOnlySpan<Vector2> arg5, ReadOnlySpan<int> arg6, ReadOnlySpan<float> arg7, Rid arg8, int arg9)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg2);
        using godot_packed_vector2_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg3);
        using godot_packed_color_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg4);
        using godot_packed_vector2_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg5);
        using godot_packed_int32_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg6);
        using godot_packed_float32_array arg7_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg7);
        long arg9_in = arg9;
        void** call_args = stackalloc void*[9] { &arg1, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8, &arg9_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1265(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Transform2D* arg3, Color* arg4, Rid arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, arg3, arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1266(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Rid arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1267(IntPtr method, IntPtr ptr, Rid arg1, double arg2, double arg3, double arg4, double arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1268(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, Rect2* arg3, in Callable arg4, in Callable arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable arg4_in = Marshaling.ConvertCallableToNative(in arg4);
        using godot_callable arg5_in = Marshaling.ConvertCallableToNative(in arg5);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1269(IntPtr method, IntPtr ptr, Rid arg1, int arg2, float arg3, godot_bool arg4, float arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg3_in = arg3;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, &arg3_in, &arg4, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1270(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector2> arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1271(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_3_1272(IntPtr method, IntPtr ptr, int arg1, int arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1273(IntPtr method, IntPtr ptr, IntPtr arg1, Color* arg2, int arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1274(IntPtr method, IntPtr ptr, IntPtr arg1, Color* arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1275(IntPtr method, IntPtr ptr, godot_bool arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1276(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, float arg3, Color* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3_in, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1277(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Color* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1278(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Vector2> arg2, ReadOnlySpan<Color> arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        using godot_packed_color_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg3);
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_10_1279(IntPtr method, IntPtr ptr, Rid arg1, godot_bool arg2, Color* arg3, float arg4, float arg5, float arg6, float arg7, float arg8, float arg9, float arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        double arg5_in = arg5;
        double arg6_in = arg6;
        double arg7_in = arg7;
        double arg8_in = arg8;
        double arg9_in = arg9;
        double arg10_in = arg10;
        void** call_args = stackalloc void*[10] { &arg1, &arg2, arg3, &arg4_in, &arg5_in, &arg6_in, &arg7_in, &arg8_in, &arg9_in, &arg10_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1280(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3, godot_bool arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3_in, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string godot_icall_0_1281(IntPtr method)
    {
        using godot_string ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int godot_icall_4_1282(IntPtr method, IntPtr ptr, string arg1, string arg2, godot_bool arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_1283(IntPtr method, IntPtr ptr, string arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_3_1284(IntPtr method, IntPtr ptr, string arg1, string arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe long godot_icall_1_1285(IntPtr method, IntPtr ptr, string arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_1286(IntPtr method, IntPtr ptr, IntPtr arg1, string arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_1287(IntPtr method, IntPtr ptr, string arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe string[] godot_icall_1_1288(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe long godot_icall_2_1289(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_1290(IntPtr method, IntPtr ptr, long arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1291(IntPtr method, IntPtr ptr, int arg1, int arg2, Color* arg3, int arg4, godot_bool arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, arg3, &arg4_in, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_12_1292(IntPtr method, IntPtr ptr, IntPtr arg1, float arg2, float arg3, Color* arg4, int arg5, Rect2* arg6, Variant arg7, godot_bool arg8, string arg9, int arg10, int arg11, string arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg2_in = arg2;
        double arg3_in = arg3;
        long arg5_in = arg5;
        godot_variant arg7_in = (godot_variant)arg7.NativeVar;
        using godot_string arg9_in = Marshaling.ConvertStringToNative(arg9);
        long arg10_in = arg10;
        long arg11_in = arg11;
        using godot_string arg12_in = Marshaling.ConvertStringToNative(arg12);
        void** call_args = stackalloc void*[12] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, arg6, &arg7_in, &arg8, &arg9_in, &arg10_in, &arg11_in, &arg12_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_12_1293(IntPtr method, IntPtr ptr, Variant arg1, int arg2, IntPtr arg3, float arg4, float arg5, Color* arg6, int arg7, Rect2* arg8, godot_bool arg9, string arg10, int arg11, int arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        long arg2_in = arg2;
        double arg4_in = arg4;
        double arg5_in = arg5;
        long arg7_in = arg7;
        using godot_string arg10_in = Marshaling.ConvertStringToNative(arg10);
        long arg11_in = arg11;
        long arg12_in = arg12;
        void** call_args = stackalloc void*[12] { &arg1_in, &arg2_in, &arg3, &arg4_in, &arg5_in, arg6, &arg7_in, arg8, &arg9, &arg10_in, &arg11_in, &arg12_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_2_1294(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_6_1295(IntPtr method, IntPtr ptr, int arg1, int arg2, string arg3, int arg4, int arg5, ReadOnlySpan<float> arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        long arg4_in = arg4;
        long arg5_in = arg5;
        using godot_packed_float32_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg6);
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1296(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_bool arg3, string arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1297(IntPtr method, IntPtr ptr, Variant arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1298(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, string arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_1299(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2, int arg3, Rect2* arg4, Color* arg5, int arg6, Color* arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[7] { &arg1_in, &arg2, &arg3_in, arg4, arg5, &arg6_in, arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1300(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, int arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1301(IntPtr method, IntPtr ptr, Color* arg1, Color* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1302(IntPtr method, IntPtr ptr, IntPtr arg1, godot_dictionary arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_1_1303(IntPtr method, IntPtr ptr, ReadOnlySpan<string> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        using godot_packed_string_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_12_1304(IntPtr method, IntPtr ptr, Variant arg1, int arg2, IntPtr arg3, int arg4, int arg5, Color* arg6, int arg7, Rect2* arg8, godot_bool arg9, string arg10, godot_bool arg11, godot_bool arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        long arg2_in = arg2;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg7_in = arg7;
        using godot_string arg10_in = Marshaling.ConvertStringToNative(arg10);
        void** call_args = stackalloc void*[12] { &arg1_in, &arg2_in, &arg3, &arg4_in, &arg5_in, arg6, &arg7_in, arg8, &arg9, &arg10_in, &arg11, &arg12 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_12_1305(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, int arg3, Color* arg4, int arg5, Rect2* arg6, Variant arg7, godot_bool arg8, string arg9, godot_bool arg10, godot_bool arg11, string arg12)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg5_in = arg5;
        godot_variant arg7_in = (godot_variant)arg7.NativeVar;
        using godot_string arg9_in = Marshaling.ConvertStringToNative(arg9);
        using godot_string arg12_in = Marshaling.ConvertStringToNative(arg12);
        void** call_args = stackalloc void*[12] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, arg6, &arg7_in, &arg8, &arg9_in, &arg10, &arg11, &arg12_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_11_1306(IntPtr method, IntPtr ptr, Variant arg1, int arg2, IntPtr arg3, int arg4, int arg5, Color* arg6, int arg7, Rect2* arg8, godot_bool arg9, string arg10, godot_bool arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        long arg2_in = arg2;
        long arg4_in = arg4;
        long arg5_in = arg5;
        long arg7_in = arg7;
        using godot_string arg10_in = Marshaling.ConvertStringToNative(arg10);
        void** call_args = stackalloc void*[11] { &arg1_in, &arg2_in, &arg3, &arg4_in, &arg5_in, arg6, &arg7_in, arg8, &arg9, &arg10_in, &arg11 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_11_1307(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, int arg3, Color* arg4, int arg5, Rect2* arg6, Variant arg7, godot_bool arg8, string arg9, godot_bool arg10, string arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg5_in = arg5;
        godot_variant arg7_in = (godot_variant)arg7.NativeVar;
        using godot_string arg9_in = Marshaling.ConvertStringToNative(arg9);
        using godot_string arg11_in = Marshaling.ConvertStringToNative(arg11);
        void** call_args = stackalloc void*[11] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, arg6, &arg7_in, &arg8, &arg9_in, &arg10, &arg11_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_10_1308(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, int arg3, Color* arg4, int arg5, Rect2* arg6, Variant arg7, godot_bool arg8, string arg9, godot_bool arg10)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg5_in = arg5;
        godot_variant arg7_in = (godot_variant)arg7.NativeVar;
        using godot_string arg9_in = Marshaling.ConvertStringToNative(arg9);
        void** call_args = stackalloc void*[10] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, arg6, &arg7_in, &arg8, &arg9_in, &arg10 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1309(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, int arg3, Color* arg4, int arg5, Rect2* arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, &arg3_in, arg4, &arg5_in, arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1310(IntPtr method, IntPtr ptr, Variant arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_4_1311(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, int arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_2_1312(IntPtr method, IntPtr ptr, godot_node_path arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_1_1313(IntPtr method, IntPtr ptr, godot_node_path arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe NodePath godot_icall_2_1314(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_node_path ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return NodePath.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_4_1315(IntPtr method, IntPtr ptr, double arg1, godot_bool arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_4_1316(IntPtr method, IntPtr ptr, long arg1, godot_string_name arg2, godot_string_name arg3, ReadOnlySpan<Variant> arg4, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        int vararg_length = arg4.Length;
        int total_length = 3 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromInt(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            using godot_variant arg2_in = VariantUtils.CreateFromStringName(arg2);
            call_args[1] = new IntPtr(&arg2_in);
            using godot_variant arg3_in = VariantUtils.CreateFromStringName(arg3);
            call_args[2] = new IntPtr(&arg3_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg4[i].NativeVar;
                call_args[3 + i] = new IntPtr(&varargs[i]);
            }
            NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
        }
    }

    internal static unsafe void godot_icall_3_1317(IntPtr method, IntPtr ptr, uint arg1, godot_string_name arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1318(IntPtr method, IntPtr ptr, uint arg1, godot_string_name arg2, string arg3, Variant arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        godot_variant arg4_in = (godot_variant)arg4.NativeVar;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1319(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, ReadOnlySpan<Variant> arg3, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        int vararg_length = arg3.Length;
        int total_length = 2 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromStringName(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            using godot_variant arg2_in = VariantUtils.CreateFromStringName(arg2);
            call_args[1] = new IntPtr(&arg2_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg3[i].NativeVar;
                call_args[2 + i] = new IntPtr(&varargs[i]);
            }
            NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
        }
    }

    internal static unsafe void godot_icall_3_1320(IntPtr method, IntPtr ptr, godot_string_name arg1, string arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1321(IntPtr method, IntPtr ptr, IntPtr arg1, godot_node_path arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_1_1322(IntPtr method, IntPtr ptr, godot_node_path arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_1324(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_2_1325(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe godot_bool godot_icall_3_1326(IntPtr method, IntPtr ptr, Transform2D* arg1, IntPtr arg2, Transform2D* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[3] { arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_5_1327(IntPtr method, IntPtr ptr, Transform2D* arg1, Vector2* arg2, IntPtr arg3, Transform2D* arg4, Vector2* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[5] { arg1, arg2, &arg3, arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2[] godot_icall_3_1328(IntPtr method, IntPtr ptr, Transform2D* arg1, IntPtr arg2, Transform2D* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[3] { arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2[] godot_icall_5_1329(IntPtr method, IntPtr ptr, Transform2D* arg1, Vector2* arg2, IntPtr arg3, Transform2D* arg4, Vector2* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[5] { arg1, arg2, &arg3, arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_4_1330(IntPtr method, IntPtr ptr, int arg1, Transform2D* arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_2_1331(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_1332(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1333(IntPtr method, IntPtr ptr, int arg1, Transform3D* arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_4_1334(IntPtr method, IntPtr ptr, float arg1, float arg2, float arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        double arg1_in = arg1;
        double arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe void godot_icall_2_1335(IntPtr method, IntPtr ptr, string arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1336(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, godot_node_path arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1337(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, godot_node_path arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1338(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_node_path arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe NodePath godot_icall_2_1339(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_node_path ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return NodePath.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_4_1340(IntPtr method, IntPtr ptr, godot_string_name arg1, IntPtr arg2, float arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1341(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2, IntPtr arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_2_1342(IntPtr method, IntPtr ptr, godot_string_name arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_1343(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_1_1344(IntPtr method, IntPtr ptr, sbyte arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_1345(IntPtr method, IntPtr ptr, short arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1346(IntPtr method, IntPtr ptr, Variant arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe sbyte godot_icall_0_1347(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return (sbyte)(ret);
    }

    internal static unsafe short godot_icall_0_1348(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return (short)(ret);
    }

    internal static unsafe int godot_icall_2_1349(IntPtr method, IntPtr ptr, godot_bool arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_1350(IntPtr method, IntPtr ptr, int arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_1351(IntPtr method, IntPtr ptr, IntPtr arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe godot_bool godot_icall_2_1352(IntPtr method, IntPtr ptr, Vector2* arg1, Rect2* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_6_1353(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1, ReadOnlySpan<Vector2> arg2, ReadOnlySpan<Color> arg3, ReadOnlySpan<Vector2> arg4, ReadOnlySpan<Vector3> arg5, godot_array arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        using godot_packed_color_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg3);
        using godot_packed_vector2_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg4);
        using godot_packed_vector3_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg5);
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int[] godot_icall_2_1354(IntPtr method, IntPtr ptr, float arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        double arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_1355(IntPtr method, IntPtr ptr, godot_array arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1356(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_2_1357(IntPtr method, IntPtr ptr, IntPtr arg1, ulong arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_2_1358(IntPtr method, IntPtr ptr, ushort arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_2_1359(IntPtr method, IntPtr arg1, IntPtr arg2)
    {
        using godot_ref ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_5_1360(IntPtr method, IntPtr ptr, string arg1, int arg2, int arg3, godot_bool arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2I godot_icall_3_1361(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_4_1362(IntPtr method, IntPtr ptr, string arg1, uint arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_3_1363(IntPtr method, IntPtr ptr, Vector2I* arg1, godot_bool arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        void** call_args = stackalloc void*[3] { arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_2_1364(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rect2I godot_icall_2_1365(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2I ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_1366(IntPtr method, IntPtr ptr, godot_bool arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int[] godot_icall_1_1367(IntPtr method, IntPtr ptr, godot_bool arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_5_1368(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1369(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, godot_bool arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1370(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_4_1371(IntPtr method, IntPtr ptr, int arg1, int arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_1372(IntPtr method, IntPtr ptr, godot_bool arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_4_1373(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1374(IntPtr method, IntPtr ptr, int arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2I godot_icall_2_1375(IntPtr method, IntPtr ptr, Vector2I* arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_5_1376(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2, int arg3, string arg4, Variant arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        godot_variant arg5_in = (godot_variant)arg5.NativeVar;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_5_1377(IntPtr method, IntPtr ptr, Variant arg1, Vector2* arg2, int arg3, int arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        long arg3_in = arg3;
        long arg4_in = arg4;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, arg2, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_4_1378(IntPtr method, IntPtr ptr, Variant arg1, Vector2* arg2, int arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        long arg3_in = arg3;
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_1_1379(IntPtr method, IntPtr ptr, Variant arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rect2 godot_icall_1_1380(IntPtr method, IntPtr ptr, Variant arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1381(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Color* arg3, float arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, arg2, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1382(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, int arg3, Color* arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3_in, arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_1_1383(IntPtr method, IntPtr ptr, float arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        double arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_4_1384(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, int arg3, Color* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3_in, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1385(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Color* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_5_1386(IntPtr method, IntPtr ptr, string arg1, IntPtr arg2, int arg3, Rect2* arg4, string arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg3_in = arg3;
        using godot_string arg5_in = Marshaling.ConvertStringToNative(arg5);
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3_in, arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rect2 godot_icall_2_1387(IntPtr method, IntPtr ptr, int arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        long arg1_in = arg1;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_5_1388(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Color* arg3, Color* arg4, float arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, arg2, arg3, arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1389(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, int arg3, Color* arg4, Color* arg5, float arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3_in, arg4, arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1390(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, int arg3, int arg4, Color* arg5, float arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        long arg4_in = arg4;
        double arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1, arg2, &arg3_in, &arg4_in, arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1391(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, int arg3, int arg4, Color* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3_in, &arg4_in, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1392(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, int arg3, Color* arg4, Color* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3_in, arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1393(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Color* arg3, Color* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1394(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<byte> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1395(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_1_1396(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_2_1397(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Color[] godot_icall_2_1398(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_color_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedColorArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_2_1399(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<Color> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_color_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedColorArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1400(IntPtr method, IntPtr ptr, Rid arg1, int arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe long godot_icall_2_1401(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1402(IntPtr method, IntPtr ptr, Rid arg1, long arg2, double arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe double godot_icall_2_1403(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_2_1404(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1405(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1406(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3, IntPtr arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_3_1407(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_4_1408(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3, ReadOnlySpan<int> arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg4);
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int[] godot_icall_3_1409(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_2_1410(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe Vector2 godot_icall_3_1411(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1412(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_3_1413(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1414(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rect2 godot_icall_3_1415(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1416(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3, Rect2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe long godot_icall_3_1417(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1418(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3, long arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_3_1419(IntPtr method, IntPtr ptr, Rid arg1, Vector2I* arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[3] { &arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_3_1420(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_1421(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe void godot_icall_3_1422(IntPtr method, IntPtr ptr, Rid arg1, long arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1423(IntPtr method, IntPtr ptr, Rid arg1, long arg2, Vector2I* arg3, Vector2* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, &arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_3_1424(IntPtr method, IntPtr ptr, Rid arg1, long arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_4_1425(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3, long arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_3_1426(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_1427(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_7_1428(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, long arg3, Vector2* arg4, long arg5, Color* arg6, float arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3, arg4, &arg5, arg6, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_8_1429(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, long arg3, long arg4, Vector2* arg5, long arg6, Color* arg7, float arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1, &arg2, &arg3, &arg4, arg5, &arg6, arg7, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_2_1430(IntPtr method, IntPtr ptr, Rid arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1431(IntPtr method, IntPtr ptr, Rid arg1, string arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2 godot_icall_2_1432(IntPtr method, IntPtr ptr, long arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_5_1433(IntPtr method, IntPtr ptr, Rid arg1, long arg2, Vector2* arg3, long arg4, Color* arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, arg3, &arg4, arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_7_1434(IntPtr method, IntPtr ptr, Rid arg1, string arg2, godot_array arg3, long arg4, godot_dictionary arg5, string arg6, Variant arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        using godot_string arg6_in = Marshaling.ConvertStringToNative(arg6);
        godot_variant arg7_in = (godot_variant)arg7.NativeVar;
        void** call_args = stackalloc void*[7] { &arg1, &arg2_in, &arg3, &arg4, &arg5, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_6_1435(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2, Vector2* arg3, int arg4, long arg5, double arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[6] { &arg1, &arg2_in, arg3, &arg4_in, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_5_1436(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2, Vector2* arg3, int arg4, double arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, arg3, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_1437(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_5_1438(IntPtr method, IntPtr ptr, Rid arg1, long arg2, godot_array arg3, long arg4, godot_dictionary arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, &arg2, &arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2I godot_icall_2_1439(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_2_1440(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Rid godot_icall_3_1441(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe double godot_icall_3_1442(IntPtr method, IntPtr ptr, Rid arg1, double arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe double godot_icall_2_1443(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<float> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_1_1444(IntPtr method, IntPtr ptr, Rid arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int[] godot_icall_5_1445(IntPtr method, IntPtr ptr, Rid arg1, ReadOnlySpan<float> arg2, long arg3, godot_bool arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, &arg2_in, &arg3, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_4_1446(IntPtr method, IntPtr ptr, Rid arg1, double arg2, long arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_3_1447(IntPtr method, IntPtr ptr, Rid arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_3_1448(IntPtr method, IntPtr ptr, Rid arg1, double arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rect2 godot_icall_2_1449(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_2_1450(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_2_1451(IntPtr method, IntPtr ptr, Rid arg1, Variant arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_1452(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector2[] godot_icall_3_1453(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe long godot_icall_2_1454(IntPtr method, IntPtr ptr, Rid arg1, double arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2 godot_icall_2_1455(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2 ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_2_1456(IntPtr method, IntPtr ptr, Rid arg1, long arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_7_1457(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector2* arg3, double arg4, double arg5, Color* arg6, float arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg7_in = arg7;
        void** call_args = stackalloc void*[7] { &arg1, &arg2, arg3, &arg4, &arg5, arg6, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_8_1458(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector2* arg3, double arg4, double arg5, long arg6, Color* arg7, float arg8)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double arg8_in = arg8;
        void** call_args = stackalloc void*[8] { &arg1, &arg2, arg3, &arg4, &arg5, &arg6, arg7, &arg8_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_3_1459(IntPtr method, IntPtr ptr, Rid arg1, long arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe string godot_icall_2_1460(IntPtr method, IntPtr ptr, string arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe int[] godot_icall_3_1461(IntPtr method, IntPtr ptr, string arg1, string arg2, long arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe int[] godot_icall_2_1462(IntPtr method, IntPtr ptr, string arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe long godot_icall_2_1463(IntPtr method, IntPtr ptr, string arg1, ReadOnlySpan<string> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Array godot_icall_3_1464(IntPtr method, IntPtr ptr, int arg1, godot_array arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe int[] godot_icall_2_1465(IntPtr method, IntPtr ptr, Rid arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_int32_array ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedInt32ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_7_1466(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector2* arg3, double arg4, double arg5, long arg6, Color* arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[7] { &arg1, &arg2, arg3, &arg4, &arg5, &arg6, arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1467(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, Vector2* arg3, double arg4, double arg5, Color* arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[6] { &arg1, &arg2, arg3, &arg4, &arg5, arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_7_1468(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, long arg3, long arg4, Vector2* arg5, long arg6, Color* arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[7] { &arg1, &arg2, &arg3, &arg4, arg5, &arg6, arg7 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1469(IntPtr method, IntPtr ptr, Rid arg1, Rid arg2, long arg3, Vector2* arg4, long arg5, Color* arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[6] { &arg1, &arg2, &arg3, arg4, &arg5, arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1470(IntPtr method, IntPtr ptr, Rid arg1, Vector2* arg2, Color* arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[4] { &arg1, arg2, arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1471(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, godot_bool arg3, Color* arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[5] { &arg1, arg2, &arg3, arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1472(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Rect2* arg3, Color* arg4, godot_bool arg5, godot_bool arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[6] { &arg1, arg2, arg3, arg4, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1473(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1474(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1475(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, Color* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { &arg1, &arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1476(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2, godot_string_name arg3, Variant arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        godot_variant arg4_in = (godot_variant)arg4.NativeVar;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Variant godot_icall_3_1477(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_variant ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_3_1478(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1479(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2, godot_string_name arg3, godot_string_name arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1480(IntPtr method, IntPtr ptr, int arg1, godot_string_name arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe string[] godot_icall_2_1481(IntPtr method, IntPtr ptr, int arg1, string arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array ret = default;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedStringArrayToSystemArray(ret);
    }

    internal static unsafe int godot_icall_2_1482(IntPtr method, IntPtr ptr, in Callable arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_4_1483(IntPtr method, IntPtr ptr, int arg1, godot_bool arg2, godot_bool arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_3_1484(IntPtr method, IntPtr ptr, int arg1, int arg2, ReadOnlySpan<Vector2> arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_packed_vector2_array arg3_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2[] godot_icall_2_1485(IntPtr method, IntPtr ptr, int arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_5_1486(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, Vector2I* arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, arg2, &arg3_in, arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_3_1487(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Vector2I godot_icall_3_1488(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_3_1489(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe godot_bool godot_icall_3_1490(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_2_1491(IntPtr method, IntPtr ptr, int arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Vector2I godot_icall_3_1492(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        void** call_args = stackalloc void*[3] { arg1, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1493(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1494(IntPtr method, IntPtr ptr, int arg1, godot_array arg2, int arg3, int arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3_in, &arg4_in, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Array godot_icall_1_1495(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_4_1496(IntPtr method, IntPtr ptr, int arg1, int arg2, Vector2I* arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Vector2I godot_icall_1_1497(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2I godot_icall_2_1498(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_4_1499(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2, Vector2I* arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { arg1, &arg2_in, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector2I godot_icall_1_1500(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector2I ret;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_1_1501(IntPtr method, IntPtr ptr, Vector2I* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe Godot.Collections.Array godot_icall_3_1502(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_1_1503(IntPtr method, IntPtr ptr, godot_array arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe void godot_icall_2_1504(IntPtr method, IntPtr ptr, Vector2I* arg1, IntPtr arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1505(IntPtr method, IntPtr ptr, godot_array arg1, int arg2, int arg3, godot_bool arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_4_1506(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, Vector2I* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1_in, arg2, &arg3_in, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_1507(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_2_1508(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_6_1509(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3, int arg4, Vector2I* arg5, int arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1_in, arg2, &arg3_in, &arg4_in, arg5, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_3_1510(IntPtr method, IntPtr ptr, int arg1, Vector2I* arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_2_1511(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1512(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2, Vector2I* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[3] { arg1, arg2, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_6_1513(IntPtr method, IntPtr ptr, Vector2I* arg1, Vector2I* arg2, int arg3, Vector2I* arg4, int arg5, Vector2I* arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg3_in = arg3;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[6] { arg1, arg2, &arg3_in, arg4, &arg5_in, arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Vector2[] godot_icall_4_1514(IntPtr method, IntPtr ptr, IntPtr arg1, Vector2I* arg2, Vector2I* arg3, Vector2I* arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_vector2_array ret = default;
        void** call_args = stackalloc void*[4] { &arg1, arg2, arg3, arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedVector2ArrayToSystemArray(ret);
    }

    internal static unsafe void godot_icall_3_1515(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2, float arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        double arg3_in = arg3;
        void** call_args = stackalloc void*[3] { arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe float godot_icall_2_1516(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        double ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (float)ret;
    }

    internal static unsafe int godot_icall_2_1517(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_3_1518(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe GodotObject godot_icall_2_1519(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe Rect2I godot_icall_2_1520(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2I ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe godot_bool godot_icall_2_1521(IntPtr method, IntPtr ptr, Vector2I* arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_1_1522(IntPtr method, IntPtr ptr, long arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_2_1523(IntPtr method, IntPtr ptr, long arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_1524(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_2_1525(IntPtr method, IntPtr ptr, godot_dictionary arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe long godot_icall_1_1526(IntPtr method, IntPtr ptr, godot_dictionary arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_2_1527(IntPtr method, IntPtr ptr, godot_bool arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        void** call_args = stackalloc void*[2] { &arg1, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe void godot_icall_3_1528(IntPtr method, IntPtr ptr, godot_string_name arg1, ReadOnlySpan<string> arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_string_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedStringArray(arg2);
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe StringName godot_icall_4_1529(IntPtr method, IntPtr ptr, godot_string_name arg1, godot_string_name arg2, int arg3, godot_string_name arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_string_name ret = default;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return StringName.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe godot_bool godot_icall_2_1530(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Array godot_icall_2_1531(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe string godot_icall_2_1532(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_2_1533(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe GodotObject godot_icall_1_1534(IntPtr method, IntPtr ptr, IntPtr arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe Rect2 godot_icall_3_1535(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rect2 ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe GodotObject godot_icall_1_1536(IntPtr method, IntPtr ptr, Vector2* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        IntPtr ret = default;
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe void godot_icall_5_1537(IntPtr method, IntPtr ptr, int arg1, double arg2, double arg3, double arg4, godot_bool arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1538(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, godot_string_name arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Callable godot_icall_1_1539(IntPtr method, IntPtr ptr, int arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_callable ret = default;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertCallableToManaged(in ret);
    }

    internal static unsafe void godot_icall_3_1540(IntPtr method, IntPtr ptr, int arg1, Color* arg2, godot_bool arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        void** call_args = stackalloc void*[3] { &arg1_in, arg2, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_6_1541(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, int arg3, godot_bool arg4, string arg5, string arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        using godot_string arg5_in = Marshaling.ConvertStringToNative(arg5);
        using godot_string arg6_in = Marshaling.ConvertStringToNative(arg6);
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2, &arg3_in, &arg4, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_2_1542(IntPtr method, IntPtr ptr, godot_string_name arg1, ReadOnlySpan<Variant> arg2, godot_string_name caller)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        int vararg_length = arg2.Length;
        int total_length = 1 + vararg_length;
        Span<godot_variant.movable> varargs_span = vararg_length <= VarArgsSpanThreshold ?
            stackalloc godot_variant.movable[VarArgsSpanThreshold] :
            new godot_variant.movable[vararg_length];
        Span<IntPtr> call_args_span = total_length <= VarArgsSpanThreshold ?
            stackalloc IntPtr[VarArgsSpanThreshold] :
            new IntPtr[total_length];
        fixed (godot_variant.movable* varargs = &MemoryMarshal.GetReference(varargs_span))
        fixed (IntPtr* call_args = &MemoryMarshal.GetReference(call_args_span))
        {
            using godot_variant arg1_in = VariantUtils.CreateFromStringName(arg1);
            call_args[0] = new IntPtr(&arg1_in);
            for (int i = 0; i < vararg_length; i++)
            {
                varargs[i] = arg2[i].NativeVar;
                call_args[1 + i] = new IntPtr(&varargs[i]);
            }
            NativeFuncs.godotsharp_method_bind_call(method, ptr, (godot_variant**)call_args, total_length, out godot_variant_call_error vcall_error);
            ExceptionUtils.DebugCheckCallError(caller, ptr, (godot_variant**)call_args, total_length, vcall_error);
        }
    }

    internal static unsafe void godot_icall_5_1543(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, int arg3, godot_bool arg4, string arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg3_in = arg3;
        using godot_string arg5_in = Marshaling.ConvertStringToNative(arg5);
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3_in, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_1_1544(IntPtr method, IntPtr ptr, ReadOnlySpan<Vector3> arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        using godot_packed_vector3_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedVector3Array(arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Godot.Collections.Dictionary godot_icall_2_1545(IntPtr method, IntPtr ptr, Vector3* arg1, Vector3* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_dictionary ret = default;
        void** call_args = stackalloc void*[2] { arg1, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Dictionary.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe GodotObject godot_icall_4_1546(IntPtr method, IntPtr ptr, IntPtr arg1, godot_node_path arg2, Variant arg3, double arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_4_1547(IntPtr method, IntPtr ptr, in Callable arg1, Variant arg2, Variant arg3, double arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe GodotObject godot_icall_1_1548(IntPtr method, IntPtr ptr, in Signal arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_signal arg1_in = Marshaling.ConvertSignalToNative(in arg1);
        void** call_args = stackalloc void*[1] { &arg1_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe Variant godot_icall_6_1549(IntPtr method, Variant arg1, Variant arg2, double arg3, double arg4, int arg5, int arg6)
    {
        godot_variant ret = default;
        godot_variant arg1_in = (godot_variant)arg1.NativeVar;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        long arg5_in = arg5;
        long arg6_in = arg6;
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2_in, &arg3, &arg4, &arg5_in, &arg6_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return Variant.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe int godot_icall_3_1550(IntPtr method, IntPtr ptr, int arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_5_1551(IntPtr method, IntPtr ptr, int arg1, int arg2, string arg3, string arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        using godot_string arg4_in = Marshaling.ConvertStringToNative(arg4);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe Rid godot_icall_3_1552(IntPtr method, Rid arg1, uint arg2, godot_array arg3)
    {
        Rid ret;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_1553(IntPtr method, IntPtr ptr, int arg1, ReadOnlySpan<float> arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_packed_float32_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedFloat32Array(arg2);
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_4_1554(IntPtr method, IntPtr ptr, int arg1, IntPtr arg2, Vector2* arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, arg3, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_3_1555(IntPtr method, IntPtr ptr, int arg1, int arg2, Vector2* arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe godot_bool godot_icall_5_1556(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4_in, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe string godot_icall_3_1557(IntPtr method, IntPtr ptr, int arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string ret = default;
        long arg1_in = arg1;
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertStringToManaged(ret);
    }

    internal static unsafe godot_bool godot_icall_4_1558(IntPtr method, IntPtr ptr, int arg1, int arg2, int arg3, int arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_bool ret;
        long arg1_in = arg1;
        long arg2_in = arg2;
        long arg3_in = arg3;
        long arg4_in = arg4;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2_in, &arg3_in, &arg4_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_3_1559(IntPtr method, IntPtr ptr, int arg1, Variant arg2, Variant arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg1_in = arg1;
        godot_variant arg2_in = (godot_variant)arg2.NativeVar;
        godot_variant arg3_in = (godot_variant)arg3.NativeVar;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_1_1560(IntPtr method, IntPtr ptr, Vector4* arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        void** call_args = stackalloc void*[1] { arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Vector4 godot_icall_0_1561(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Vector4 ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_7_1562(IntPtr method, IntPtr ptr, Transform3D* arg1, Aabb* arg2, Vector3* arg3, ReadOnlySpan<byte> arg4, ReadOnlySpan<byte> arg5, ReadOnlySpan<byte> arg6, ReadOnlySpan<int> arg7)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array arg4_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg4);
        using godot_packed_byte_array arg5_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg5);
        using godot_packed_byte_array arg6_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg6);
        using godot_packed_int32_array arg7_in = Marshaling.ConvertSystemArrayToNativePackedInt32Array(arg7);
        void** call_args = stackalloc void*[7] { arg1, arg2, arg3, &arg4_in, &arg5_in, &arg6_in, &arg7_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe int godot_icall_2_1563(IntPtr method, IntPtr ptr, int arg1, godot_array arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_1564(IntPtr method, IntPtr ptr, IntPtr arg1, int arg2, int arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg2_in = arg2;
        long arg3_in = arg3;
        void** call_args = stackalloc void*[3] { &arg1, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_1_1565(IntPtr method, IntPtr ptr, godot_dictionary arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_2_1566(IntPtr method, IntPtr ptr, string arg1, godot_dictionary arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_ref ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return InteropUtils.UnmanagedGetManaged(ret.Reference);
    }

    internal static unsafe int godot_icall_3_1567(IntPtr method, IntPtr ptr, string arg1, int arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_3_1568(IntPtr method, IntPtr ptr, int arg1, string arg2, IntPtr arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        long arg1_in = arg1;
        using godot_string arg2_in = Marshaling.ConvertStringToNative(arg2);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe int godot_icall_2_1569(IntPtr method, IntPtr ptr, ReadOnlySpan<byte> arg1, int arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_packed_byte_array arg1_in = Marshaling.ConvertSystemArrayToNativePackedByteArray(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe GodotObject godot_icall_0_1570(IntPtr method)
    {
        IntPtr ret = default;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, IntPtr.Zero, null, &ret);
        return InteropUtils.UnmanagedGetManaged(ret);
    }

    internal static unsafe long godot_icall_3_1571(IntPtr method, IntPtr ptr, in Callable arg1, godot_bool arg2, string arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        using godot_string arg3_in = Marshaling.ConvertStringToNative(arg3);
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2, &arg3_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe long godot_icall_5_1572(IntPtr method, IntPtr ptr, in Callable arg1, int arg2, int arg3, godot_bool arg4, string arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_callable arg1_in = Marshaling.ConvertCallableToNative(in arg1);
        long arg2_in = arg2;
        long arg3_in = arg3;
        using godot_string arg5_in = Marshaling.ConvertStringToNative(arg5);
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2_in, &arg3_in, &arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Plane godot_icall_0_1573(IntPtr method, IntPtr ptr)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Plane ret;
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, null, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_1_1574(IntPtr method, IntPtr ptr, ulong arg1)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        void** call_args = stackalloc void*[1] { &arg1 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe void godot_icall_6_1575(IntPtr method, IntPtr ptr, string arg1, godot_string_name arg2, double arg3, double arg4, double arg5, double arg6)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[6] { &arg1_in, &arg2, &arg3, &arg4, &arg5, &arg6 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Godot.Collections.Array godot_icall_4_1576(IntPtr method, IntPtr ptr, godot_string_name arg1, double arg2, double arg3, double arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        godot_array ret = default;
        void** call_args = stackalloc void*[4] { &arg1, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Godot.Collections.Array.CreateTakingOwnershipOfDisposableValue(ret);
    }

    internal static unsafe Transform3D godot_icall_2_1577(IntPtr method, IntPtr ptr, uint arg1, Transform3D* arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Transform3D ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[2] { &arg1_in, arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe Projection godot_icall_4_1578(IntPtr method, IntPtr ptr, uint arg1, double arg2, double arg3, double arg4)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Projection ret;
        long arg1_in = arg1;
        void** call_args = stackalloc void*[4] { &arg1_in, &arg2, &arg3, &arg4 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe void godot_icall_11_1579(IntPtr method, IntPtr ptr, Rid arg1, Rect2* arg2, Rect2I* arg3, godot_bool arg4, uint arg5, godot_bool arg6, Vector2* arg7, double arg8, double arg9, double arg10, double arg11)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[11] { &arg1, arg2, arg3, &arg4, &arg5_in, &arg6, arg7, &arg8, &arg9, &arg10, &arg11 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1580(IntPtr method, IntPtr ptr, string arg1, double arg2, double arg3, double arg4, double arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[5] { &arg1_in, &arg2, &arg3, &arg4, &arg5 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe void godot_icall_5_1581(IntPtr method, IntPtr ptr, godot_string_name arg1, Transform3D* arg2, Vector3* arg3, Vector3* arg4, int arg5)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long arg5_in = arg5;
        void** call_args = stackalloc void*[5] { &arg1, arg2, arg3, arg4, &arg5_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, null);
    }

    internal static unsafe Rid godot_icall_2_1582(IntPtr method, IntPtr ptr, Vector2* arg1, ReadOnlySpan<Vector2> arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        Rid ret;
        using godot_packed_vector2_array arg2_in = Marshaling.ConvertSystemArrayToNativePackedVector2Array(arg2);
        void** call_args = stackalloc void*[2] { arg1, &arg2_in };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return ret;
    }

    internal static unsafe int godot_icall_3_1583(IntPtr method, IntPtr ptr, string arg1, int arg2, ulong arg3)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        long ret;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        long arg2_in = arg2;
        void** call_args = stackalloc void*[3] { &arg1_in, &arg2_in, &arg3 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return (int)(ret);
    }

    internal static unsafe byte[] godot_icall_2_1584(IntPtr method, IntPtr ptr, string arg1, godot_bool arg2)
    {
        ExceptionUtils.ThrowIfNullPtr(ptr);
        using godot_packed_byte_array ret = default;
        using godot_string arg1_in = Marshaling.ConvertStringToNative(arg1);
        void** call_args = stackalloc void*[2] { &arg1_in, &arg2 };
        NativeFuncs.godotsharp_method_bind_ptrcall(method, ptr, call_args, &ret);
        return Marshaling.ConvertNativePackedByteArrayToSystemArray(ret);
    }
}
