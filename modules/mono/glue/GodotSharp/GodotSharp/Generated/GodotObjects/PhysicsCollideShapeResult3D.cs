namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This class contains the contact points computed by <see cref="Godot.PhysicsDirectSpaceState3D.CollideShapeInto(PhysicsShapeQueryParameters3D, PhysicsCollideShapeResult3D)"/>.</para>
/// <para>Each collision is represented as a pair of points: one on the query shape and one on the colliding shape.</para>
/// <para><b>Note:</b> For optimal performance results, it is recommended to create this object in advance, store it, and reuse it for every subsequent query.</para>
/// </summary>
public partial class PhysicsCollideShapeResult3D : RefCounted
{
    /// <summary>
    /// <para>The maximum number of collisions this object can store.</para>
    /// </summary>
    public int MaxCollisions
    {
        get
        {
            return GetMaxCollisions();
        }
        set
        {
            SetMaxCollisions(value);
        }
    }

    private static readonly System.Type CachedType = typeof(PhysicsCollideShapeResult3D);

    private static readonly StringName NativeName = "PhysicsCollideShapeResult3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public PhysicsCollideShapeResult3D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsCollideShapeResult3D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsCollideShapeResult3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxCollisions, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMaxCollisions()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxCollisions, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxCollisions(int maxCollisions)
    {
        NativeCalls.godot_icall_1_38(MethodBind1, GodotObject.GetPtr(this), maxCollisions);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCollisionCount, 3905245786ul);

    /// <summary>
    /// <para>Returns the number of point pairs detected by the query.</para>
    /// </summary>
    public int GetCollisionCount()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPointOnQueriedShape, 711720468ul);

    /// <summary>
    /// <para>Returns the collision point on the query shape for the collision at the given index.</para>
    /// </summary>
    public Vector3 GetPointOnQueriedShape(int collisionIndex)
    {
        Vector3 ret = NativeCalls.godot_icall_1_248(MethodBind3, GodotObject.GetPtr(this), collisionIndex);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPointOnCollidingShape, 711720468ul);

    /// <summary>
    /// <para>Returns the collision point on the colliding shape for the collision at the given index.</para>
    /// </summary>
    public Vector3 GetPointOnCollidingShape(int collisionIndex)
    {
        Vector3 ret = NativeCalls.godot_icall_1_248(MethodBind4, GodotObject.GetPtr(this), collisionIndex);
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
        /// Cached name for the 'max_collisions' property.
        /// </summary>
        public static readonly StringName MaxCollisions = "max_collisions";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'get_max_collisions' method.
        /// </summary>
        public static readonly StringName GetMaxCollisions = "get_max_collisions";
        /// <summary>
        /// Cached name for the 'set_max_collisions' method.
        /// </summary>
        public static readonly StringName SetMaxCollisions = "set_max_collisions";
        /// <summary>
        /// Cached name for the 'get_collision_count' method.
        /// </summary>
        public static readonly StringName GetCollisionCount = "get_collision_count";
        /// <summary>
        /// Cached name for the 'get_point_on_queried_shape' method.
        /// </summary>
        public static readonly StringName GetPointOnQueriedShape = "get_point_on_queried_shape";
        /// <summary>
        /// Cached name for the 'get_point_on_colliding_shape' method.
        /// </summary>
        public static readonly StringName GetPointOnCollidingShape = "get_point_on_colliding_shape";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
