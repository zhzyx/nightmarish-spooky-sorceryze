namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para><see cref="Godot.Skin"/> contains a list of bind pose matrices and a list of either bone names if bones are named, or bone indices if bones are not named. The bind pose matrix, also called offset matrix or inverse bind matrix, is a <see cref="Godot.Transform3D"/> offset that is multiplied with a bone's transform to get from vertex space to bone space.</para>
/// </summary>
public partial class Skin : Resource
{
    private static readonly System.Type CachedType = typeof(Skin);

    private static readonly StringName NativeName = "Skin";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public Skin() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal Skin(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal Skin(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBindCount, 1286410249ul);

    /// <summary>
    /// <para>Resizes the bind pose list to a length of <paramref name="bindCount"/>.</para>
    /// </summary>
    public void SetBindCount(int bindCount)
    {
        NativeCalls.godot_icall_1_38(MethodBind0, GodotObject.GetPtr(this), bindCount);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBindCount, 3905245786ul);

    /// <summary>
    /// <para>Returns the length of the bind pose list.</para>
    /// </summary>
    public int GetBindCount()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddBind, 3616898986ul);

    /// <summary>
    /// <para>Adds a bind pose matrix of <paramref name="pose"/> and associated bone index <paramref name="bone"/> to the bind pose list and increases the bind count by 1.</para>
    /// </summary>
    public unsafe void AddBind(int bone, Transform3D pose)
    {
        NativeCalls.godot_icall_2_839(MethodBind2, GodotObject.GetPtr(this), bone, &pose);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddNamedBind, 3154712474ul);

    /// <summary>
    /// <para>Like <see cref="Godot.Skin.AddBind(int, Transform3D)"/> but adds a bone <paramref name="name"/> instead of a bone index.</para>
    /// </summary>
    public unsafe void AddNamedBind(string name, Transform3D pose)
    {
        NativeCalls.godot_icall_2_1335(MethodBind3, GodotObject.GetPtr(this), name, &pose);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBindPose, 3616898986ul);

    /// <summary>
    /// <para>Sets the bind pose <paramref name="bindIndex"/> with the given offset matrix <paramref name="pose"/>.</para>
    /// </summary>
    public unsafe void SetBindPose(int bindIndex, Transform3D pose)
    {
        NativeCalls.godot_icall_2_839(MethodBind4, GodotObject.GetPtr(this), bindIndex, &pose);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBindPose, 1965739696ul);

    /// <summary>
    /// <para>Returns the bind pose matrix at <paramref name="bindIndex"/>.</para>
    /// </summary>
    public Transform3D GetBindPose(int bindIndex)
    {
        Transform3D ret = NativeCalls.godot_icall_1_842(MethodBind5, GodotObject.GetPtr(this), bindIndex);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBindName, 3780747571ul);

    /// <summary>
    /// <para>Sets the name of the bone in bind pose <paramref name="bindIndex"/> to <paramref name="name"/>.</para>
    /// </summary>
    public void SetBindName(int bindIndex, StringName name)
    {
        NativeCalls.godot_icall_2_170(MethodBind6, GodotObject.GetPtr(this), bindIndex, (godot_string_name)(name?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBindName, 659327637ul);

    /// <summary>
    /// <para>Returns the bone name associated with bind pose <paramref name="bindIndex"/>.</para>
    /// </summary>
    public StringName GetBindName(int bindIndex)
    {
        StringName ret = NativeCalls.godot_icall_1_171(MethodBind7, GodotObject.GetPtr(this), bindIndex);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBindBone, 3937882851ul);

    /// <summary>
    /// <para>Sets the bone index of bind pose <paramref name="bindIndex"/> to the given index <paramref name="bone"/>.</para>
    /// </summary>
    public void SetBindBone(int bindIndex, int bone)
    {
        NativeCalls.godot_icall_2_84(MethodBind8, GodotObject.GetPtr(this), bindIndex, bone);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBindBone, 923996154ul);

    /// <summary>
    /// <para>Returns the bone index associated with bind pose <paramref name="bindIndex"/>.</para>
    /// </summary>
    public int GetBindBone(int bindIndex)
    {
        int ret = NativeCalls.godot_icall_1_85(MethodBind9, GodotObject.GetPtr(this), bindIndex);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ClearBinds, 3218959716ul);

    /// <summary>
    /// <para>Clears the bind pose list.</para>
    /// </summary>
    public void ClearBinds()
    {
        NativeCalls.godot_icall_0_3(MethodBind10, GodotObject.GetPtr(this));
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
    public new class PropertyName : Resource.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Resource.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_bind_count' method.
        /// </summary>
        public static readonly StringName SetBindCount = "set_bind_count";
        /// <summary>
        /// Cached name for the 'get_bind_count' method.
        /// </summary>
        public static readonly StringName GetBindCount = "get_bind_count";
        /// <summary>
        /// Cached name for the 'add_bind' method.
        /// </summary>
        public static readonly StringName AddBind = "add_bind";
        /// <summary>
        /// Cached name for the 'add_named_bind' method.
        /// </summary>
        public static readonly StringName AddNamedBind = "add_named_bind";
        /// <summary>
        /// Cached name for the 'set_bind_pose' method.
        /// </summary>
        public static readonly StringName SetBindPose = "set_bind_pose";
        /// <summary>
        /// Cached name for the 'get_bind_pose' method.
        /// </summary>
        public static readonly StringName GetBindPose = "get_bind_pose";
        /// <summary>
        /// Cached name for the 'set_bind_name' method.
        /// </summary>
        public static readonly StringName SetBindName = "set_bind_name";
        /// <summary>
        /// Cached name for the 'get_bind_name' method.
        /// </summary>
        public static readonly StringName GetBindName = "get_bind_name";
        /// <summary>
        /// Cached name for the 'set_bind_bone' method.
        /// </summary>
        public static readonly StringName SetBindBone = "set_bind_bone";
        /// <summary>
        /// Cached name for the 'get_bind_bone' method.
        /// </summary>
        public static readonly StringName GetBindBone = "get_bind_bone";
        /// <summary>
        /// Cached name for the 'clear_binds' method.
        /// </summary>
        public static readonly StringName ClearBinds = "clear_binds";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Resource.SignalName
    {
    }
}
