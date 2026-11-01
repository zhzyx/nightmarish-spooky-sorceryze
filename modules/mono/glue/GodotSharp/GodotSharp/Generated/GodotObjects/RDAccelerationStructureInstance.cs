namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para><see cref="Godot.RDAccelerationStructureInstance"/> describes an instance of a Bottom-Level Acceleration Structure (BLAS) used in the <see cref="Godot.RenderingDevice.TlasBuild(Rid, Godot.Collections.Array{RDAccelerationStructureInstance})"/> method.</para>
/// </summary>
public partial class RDAccelerationStructureInstance : RefCounted
{
    /// <summary>
    /// <para>Transform applied to the referenced BLAS for this instance.</para>
    /// </summary>
    public Transform3D Transform
    {
        get
        {
            return GetTransform();
        }
        set
        {
            SetTransform(value);
        }
    }

    /// <summary>
    /// <para>Custom instance ID that can be accessed in GLSL using <c>gl_InstanceCustomIndexEXT</c>.</para>
    /// </summary>
    public uint Id
    {
        get
        {
            return GetId();
        }
        set
        {
            SetId(value);
        }
    }

    /// <summary>
    /// <para>Visibility mask used to control which rays can intersect this instance.</para>
    /// </summary>
    public byte Mask
    {
        get
        {
            return GetMask();
        }
        set
        {
            SetMask(value);
        }
    }

    /// <summary>
    /// <para>Hit shader binding table range used for this instance, allocated using the <see cref="Godot.RenderingDevice.HitSbtRangeAlloc(Rid, uint)"/> method.</para>
    /// </summary>
    public long HitSbtRange
    {
        get
        {
            return GetHitSbtRange();
        }
        set
        {
            SetHitSbtRange(value);
        }
    }

    /// <summary>
    /// <para>Flags for the instance.</para>
    /// </summary>
    public RenderingDevice.AccelerationStructureInstanceFlagBits Flags
    {
        get
        {
            return GetFlags();
        }
        set
        {
            SetFlags(value);
        }
    }

    /// <summary>
    /// <para>The BLAS referenced by this instance. If <see langword="null"/>, the instance is treated as a placeholder but still contributes to <c>gl_InstanceIndex</c> in GLSL.</para>
    /// </summary>
    public Rid Blas
    {
        get
        {
            return GetBlas();
        }
        set
        {
            SetBlas(value);
        }
    }

    private static readonly System.Type CachedType = typeof(RDAccelerationStructureInstance);

    private static readonly StringName NativeName = "RDAccelerationStructureInstance";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public RDAccelerationStructureInstance() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDAccelerationStructureInstance(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDAccelerationStructureInstance(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetTransform, 2952846383ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public unsafe void SetTransform(Transform3D pMember)
    {
        NativeCalls.godot_icall_1_678(MethodBind0, GodotObject.GetPtr(this), &pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTransform, 3229777777ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Transform3D GetTransform()
    {
        Transform3D ret = NativeCalls.godot_icall_0_218(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetId, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetId(uint pMember)
    {
        NativeCalls.godot_icall_1_234(MethodBind2, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetId, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public uint GetId()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMask, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMask(byte pMember)
    {
        NativeCalls.godot_icall_1_312(MethodBind4, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMask, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public byte GetMask()
    {
        byte ret = NativeCalls.godot_icall_0_311(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetHitSbtRange, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetHitSbtRange(long pMember)
    {
        NativeCalls.godot_icall_1_10(MethodBind6, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetHitSbtRange, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public long GetHitSbtRange()
    {
        long ret = NativeCalls.godot_icall_0_4(MethodBind7, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetFlags, 2971840141ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetFlags(RenderingDevice.AccelerationStructureInstanceFlagBits pMember)
    {
        NativeCalls.godot_icall_1_38(MethodBind8, GodotObject.GetPtr(this), (int)pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFlags, 2410182637ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public RenderingDevice.AccelerationStructureInstanceFlagBits GetFlags()
    {
        RenderingDevice.AccelerationStructureInstanceFlagBits ret = (RenderingDevice.AccelerationStructureInstanceFlagBits)NativeCalls.godot_icall_0_39(MethodBind9, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBlas, 2722037293ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetBlas(Rid pMember)
    {
        NativeCalls.godot_icall_1_63(MethodBind10, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBlas, 2944877500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Rid GetBlas()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind11, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
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
    public new class PropertyName : RefCounted.PropertyName
    {
        /// <summary>
        /// Cached name for the 'transform' property.
        /// </summary>
        public static readonly StringName Transform = "transform";
        /// <summary>
        /// Cached name for the 'id' property.
        /// </summary>
        public static readonly StringName Id = "id";
        /// <summary>
        /// Cached name for the 'mask' property.
        /// </summary>
        public static readonly StringName Mask = "mask";
        /// <summary>
        /// Cached name for the 'hit_sbt_range' property.
        /// </summary>
        public static readonly StringName HitSbtRange = "hit_sbt_range";
        /// <summary>
        /// Cached name for the 'flags' property.
        /// </summary>
        public static readonly StringName Flags = "flags";
        /// <summary>
        /// Cached name for the 'blas' property.
        /// </summary>
        public static readonly StringName Blas = "blas";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_transform' method.
        /// </summary>
        public static readonly StringName SetTransform = "set_transform";
        /// <summary>
        /// Cached name for the 'get_transform' method.
        /// </summary>
        public static readonly StringName GetTransform = "get_transform";
        /// <summary>
        /// Cached name for the 'set_id' method.
        /// </summary>
        public static readonly StringName SetId = "set_id";
        /// <summary>
        /// Cached name for the 'get_id' method.
        /// </summary>
        public static readonly StringName GetId = "get_id";
        /// <summary>
        /// Cached name for the 'set_mask' method.
        /// </summary>
        public static readonly StringName SetMask = "set_mask";
        /// <summary>
        /// Cached name for the 'get_mask' method.
        /// </summary>
        public static readonly StringName GetMask = "get_mask";
        /// <summary>
        /// Cached name for the 'set_hit_sbt_range' method.
        /// </summary>
        public static readonly StringName SetHitSbtRange = "set_hit_sbt_range";
        /// <summary>
        /// Cached name for the 'get_hit_sbt_range' method.
        /// </summary>
        public static readonly StringName GetHitSbtRange = "get_hit_sbt_range";
        /// <summary>
        /// Cached name for the 'set_flags' method.
        /// </summary>
        public static readonly StringName SetFlags = "set_flags";
        /// <summary>
        /// Cached name for the 'get_flags' method.
        /// </summary>
        public static readonly StringName GetFlags = "get_flags";
        /// <summary>
        /// Cached name for the 'set_blas' method.
        /// </summary>
        public static readonly StringName SetBlas = "set_blas";
        /// <summary>
        /// Cached name for the 'get_blas' method.
        /// </summary>
        public static readonly StringName GetBlas = "get_blas";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
