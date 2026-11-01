namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Inputs a scale and converts it to the position of a child bone. Intended for use in combination with <see cref="Godot.Skeleton3D.SetBoneSkinScale(int, Vector3)"/>.</para>
/// <para>This modifier repositions child bones to follow the skin transformation by <see cref="Godot.Skeleton3D.SetBoneSkinScale(int, Vector3)"/> in cases when you want to adjust bone length using <see cref="Godot.Skeleton3D.SetBoneSkinScale(int, Vector3)"/> or when the bone has multiple child bones.</para>
/// </summary>
public partial class BoneSpaceAdjuster3D : SkeletonModifier3D
{
    /// <summary>
    /// <para>If <see langword="true"/>, this modifier processes all bones for which <see cref="Godot.Skeleton3D.GetBoneSkinScale(int)"/> is not <c>Vector3(1, 1, 1)</c>.</para>
    /// <para>If <see langword="false"/>, this modifier allows you to configure whether to process bone skin scaling individually in the settings.</para>
    /// </summary>
    public bool UseBoneSkinScaleForAllBones
    {
        get
        {
            return AreAllBonesUsingBoneSkinScale();
        }
        set
        {
            SetUseBoneSkinScaleForAllBones(value);
        }
    }

    /// <summary>
    /// <para>The number of settings in the modifier.</para>
    /// </summary>
    public int SettingSize
    {
        get
        {
            return GetSettingSize();
        }
        set
        {
            SetSettingSize(value);
        }
    }

    private static readonly System.Type CachedType = typeof(BoneSpaceAdjuster3D);

    private static readonly StringName NativeName = "BoneSpaceAdjuster3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public BoneSpaceAdjuster3D() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal BoneSpaceAdjuster3D(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal BoneSpaceAdjuster3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetUseBoneSkinScaleForAllBones, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetUseBoneSkinScaleForAllBones(bool enabled)
    {
        NativeCalls.godot_icall_1_14(MethodBind0, GodotObject.GetPtr(this), enabled.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AreAllBonesUsingBoneSkinScale, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool AreAllBonesUsingBoneSkinScale()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind1, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBoneName, 3780747571ul);

    /// <summary>
    /// <para>Sets the scaled bone name of the setting at <paramref name="index"/>.</para>
    /// </summary>
    public void SetBoneName(int index, StringName boneName)
    {
        NativeCalls.godot_icall_2_170(MethodBind2, GodotObject.GetPtr(this), index, (godot_string_name)(boneName?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBoneName, 659327637ul);

    /// <summary>
    /// <para>Returns the scaled bone name of the setting at <paramref name="index"/>.</para>
    /// </summary>
    public StringName GetBoneName(int index)
    {
        StringName ret = NativeCalls.godot_icall_1_171(MethodBind3, GodotObject.GetPtr(this), index);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBone, 3937882851ul);

    /// <summary>
    /// <para>Sets the scaled bone of the setting at <paramref name="index"/>.</para>
    /// </summary>
    public void SetBone(int index, int bone)
    {
        NativeCalls.godot_icall_2_84(MethodBind4, GodotObject.GetPtr(this), index, bone);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBone, 923996154ul);

    /// <summary>
    /// <para>Returns the scaled bone of the setting at <paramref name="index"/>.</para>
    /// </summary>
    public int GetBone(int index)
    {
        int ret = NativeCalls.godot_icall_1_85(MethodBind5, GodotObject.GetPtr(this), index);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetUseBoneSkinScale, 300928843ul);

    /// <summary>
    /// <para>Sets whether to use the <c>skin_scale</c> property of a <see cref="Godot.Skeleton3D"/>'s bone of the setting at <paramref name="index"/>.</para>
    /// </summary>
    public void SetUseBoneSkinScale(int index, bool enabled)
    {
        NativeCalls.godot_icall_2_67(MethodBind6, GodotObject.GetPtr(this), index, enabled.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsUsingBoneSkinScale, 1116898809ul);

    /// <summary>
    /// <para>Returns whether to use the <c>skin_scale</c> property of a <see cref="Godot.Skeleton3D"/>'s bone of the setting at <paramref name="index"/>.</para>
    /// </summary>
    public bool IsUsingBoneSkinScale(int index)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind7, GodotObject.GetPtr(this), index).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBoneScale, 1530502735ul);

    /// <summary>
    /// <para>When <see cref="Godot.BoneSpaceAdjuster3D.IsUsingBoneSkinScale(int)"/> returns <see langword="false"/>, sets the scale of the setting at <paramref name="index"/>.</para>
    /// <para><b>Note:</b> The <paramref name="scale"/> value is recommended to be non-zero.</para>
    /// </summary>
    public unsafe void SetBoneScale(int index, Vector3 scale)
    {
        NativeCalls.godot_icall_2_247(MethodBind8, GodotObject.GetPtr(this), index, &scale);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBoneScale, 711720468ul);

    /// <summary>
    /// <para>Returns the scale of the setting at <paramref name="index"/>.</para>
    /// </summary>
    public Vector3 GetBoneScale(int index)
    {
        Vector3 ret = NativeCalls.godot_icall_1_248(MethodBind9, GodotObject.GetPtr(this), index);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSettingSize, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSettingSize(int size)
    {
        NativeCalls.godot_icall_1_38(MethodBind10, GodotObject.GetPtr(this), size);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSettingSize, 2455072627ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetSettingSize()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind11, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ClearSetting, 3218959716ul);

    /// <summary>
    /// <para>Clears all settings.</para>
    /// </summary>
    public void ClearSetting()
    {
        NativeCalls.godot_icall_0_3(MethodBind12, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
    }

    /// <summary>
    /// Invokes the method with the given name, using the given arguments.
    /// This method is used by Godot to invoke methods from the engine side.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to invoke.</param>
    /// <param name="args">Arguments to use with the invoked method.</param>
    /// <param name="ret">Value returned by the invoked method.</param>
#pragma warning disable CS0618 // Member is obsolete
    protected internal override bool InvokeGodotClassMethod(in godot_string_name method, NativeVariantPtrArgs args, out godot_variant ret)
    {
        return base.InvokeGodotClassMethod(method, args, out ret);
    }
#pragma warning restore CS0618

    /// <summary>
    /// Check if the type contains a method with the given name.
    /// This method is used by Godot to check if a method exists before invoking it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to check for.</param>

    protected internal override bool HasGodotClassMethod(in godot_string_name method)
    {
        return base.HasGodotClassMethod(method);
    }

    /// <summary>
    /// Check if the type contains a signal with the given name.
    /// This method is used by Godot to check if a signal exists before raising it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="signal">Name of the signal to check for.</param>

    protected internal override bool HasGodotClassSignal(in godot_string_name signal)
    {
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : SkeletonModifier3D.PropertyName
    {
        /// <summary>
        /// Cached name for the 'use_bone_skin_scale_for_all_bones' property.
        /// </summary>
        public static readonly StringName UseBoneSkinScaleForAllBones = "use_bone_skin_scale_for_all_bones";
        /// <summary>
        /// Cached name for the 'setting_size' property.
        /// </summary>
        public static readonly StringName SettingSize = "setting_size";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : SkeletonModifier3D.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_use_bone_skin_scale_for_all_bones' method.
        /// </summary>
        public static readonly StringName SetUseBoneSkinScaleForAllBones = "set_use_bone_skin_scale_for_all_bones";
        /// <summary>
        /// Cached name for the 'are_all_bones_using_bone_skin_scale' method.
        /// </summary>
        public static readonly StringName AreAllBonesUsingBoneSkinScale = "are_all_bones_using_bone_skin_scale";
        /// <summary>
        /// Cached name for the 'set_bone_name' method.
        /// </summary>
        public static readonly StringName SetBoneName = "set_bone_name";
        /// <summary>
        /// Cached name for the 'get_bone_name' method.
        /// </summary>
        public static readonly StringName GetBoneName = "get_bone_name";
        /// <summary>
        /// Cached name for the 'set_bone' method.
        /// </summary>
        public static readonly StringName SetBone = "set_bone";
        /// <summary>
        /// Cached name for the 'get_bone' method.
        /// </summary>
        public static readonly StringName GetBone = "get_bone";
        /// <summary>
        /// Cached name for the 'set_use_bone_skin_scale' method.
        /// </summary>
        public static readonly StringName SetUseBoneSkinScale = "set_use_bone_skin_scale";
        /// <summary>
        /// Cached name for the 'is_using_bone_skin_scale' method.
        /// </summary>
        public static readonly StringName IsUsingBoneSkinScale = "is_using_bone_skin_scale";
        /// <summary>
        /// Cached name for the 'set_bone_scale' method.
        /// </summary>
        public static readonly StringName SetBoneScale = "set_bone_scale";
        /// <summary>
        /// Cached name for the 'get_bone_scale' method.
        /// </summary>
        public static readonly StringName GetBoneScale = "get_bone_scale";
        /// <summary>
        /// Cached name for the 'set_setting_size' method.
        /// </summary>
        public static readonly StringName SetSettingSize = "set_setting_size";
        /// <summary>
        /// Cached name for the 'get_setting_size' method.
        /// </summary>
        public static readonly StringName GetSettingSize = "get_setting_size";
        /// <summary>
        /// Cached name for the 'clear_setting' method.
        /// </summary>
        public static readonly StringName ClearSetting = "clear_setting";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : SkeletonModifier3D.SignalName
    {
    }
}
