namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This class contains the safe and unsafe fractions computed by <see cref="Godot.PhysicsDirectSpaceState3D.CastMotionInto(PhysicsShapeQueryParameters3D, PhysicsCastMotionResult3D)"/>.</para>
/// <para><b>Note:</b> For optimal performance results, it is recommended to create this object in advance, store it, and reuse it for every subsequent query.</para>
/// </summary>
public partial class PhysicsCastMotionResult3D : RefCounted
{
    /// <summary>
    /// <para>The maximum fraction of the motion that can be made without a collision.</para>
    /// </summary>
    public float SafeFraction
    {
        get
        {
            return GetSafeFraction();
        }
    }

    /// <summary>
    /// <para>The minimum fraction of the distance that must be moved for a collision.</para>
    /// </summary>
    public float UnsafeFraction
    {
        get
        {
            return GetUnsafeFraction();
        }
    }

    private static readonly System.Type CachedType = typeof(PhysicsCastMotionResult3D);

    private static readonly StringName NativeName = "PhysicsCastMotionResult3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public PhysicsCastMotionResult3D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsCastMotionResult3D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsCastMotionResult3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSafeFraction, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetSafeFraction()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetUnsafeFraction, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetUnsafeFraction()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind1, GodotObject.GetPtr(this));
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
        /// Cached name for the 'safe_fraction' property.
        /// </summary>
        public static readonly StringName SafeFraction = "safe_fraction";
        /// <summary>
        /// Cached name for the 'unsafe_fraction' property.
        /// </summary>
        public static readonly StringName UnsafeFraction = "unsafe_fraction";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'get_safe_fraction' method.
        /// </summary>
        public static readonly StringName GetSafeFraction = "get_safe_fraction";
        /// <summary>
        /// Cached name for the 'get_unsafe_fraction' method.
        /// </summary>
        public static readonly StringName GetUnsafeFraction = "get_unsafe_fraction";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
