namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This class contains the collision data computed by <see cref="Godot.PhysicsDirectSpaceState2D.GetRestInfoInto(PhysicsShapeQueryParameters2D, PhysicsGetRestInfoResult2D)"/>.</para>
/// <para>If the shape collides with multiple objects, only the nearest collision is stored.</para>
/// <para><b>Note:</b> For optimal performance results, it is recommended to create this object in advance, store it, and reuse it for every subsequent query.</para>
/// </summary>
public partial class PhysicsGetRestInfoResult2D : RefCounted
{
    /// <summary>
    /// <para>The intersection point.</para>
    /// </summary>
    public Vector2 Point
    {
        get
        {
            return GetPoint();
        }
    }

    /// <summary>
    /// <para>The collision normal of the query shape at the intersection point, pointing away from the intersecting object.</para>
    /// </summary>
    public Vector2 Normal
    {
        get
        {
            return GetNormal();
        }
    }

    /// <summary>
    /// <para>The intersecting object's <see cref="Godot.Rid"/>.</para>
    /// </summary>
    public Rid ColliderRid
    {
        get
        {
            return GetColliderRid();
        }
    }

    /// <summary>
    /// <para>The colliding object's ID.</para>
    /// </summary>
    public ulong ColliderId
    {
        get
        {
            return GetColliderId();
        }
    }

    /// <summary>
    /// <para>The shape index of the colliding shape.</para>
    /// </summary>
    public int ColliderShape
    {
        get
        {
            return GetColliderShape();
        }
    }

    /// <summary>
    /// <para>The colliding object's velocity <see cref="Godot.Vector2"/>. If the object is an <see cref="Godot.Area2D"/>, the result is <c>(0, 0)</c>.</para>
    /// </summary>
    public Vector2 ColliderVelocity
    {
        get
        {
            return GetColliderVelocity();
        }
    }

    private static readonly System.Type CachedType = typeof(PhysicsGetRestInfoResult2D);

    private static readonly StringName NativeName = "PhysicsGetRestInfoResult2D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public PhysicsGetRestInfoResult2D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsGetRestInfoResult2D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsGetRestInfoResult2D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPoint, 3341600327ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Vector2 GetPoint()
    {
        Vector2 ret = NativeCalls.godot_icall_0_37(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetNormal, 3341600327ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Vector2 GetNormal()
    {
        Vector2 ret = NativeCalls.godot_icall_0_37(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderRid, 2944877500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Rid GetColliderRid()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderId, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public ulong GetColliderId()
    {
        ulong ret = NativeCalls.godot_icall_0_162(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderShape, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetColliderShape()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind4, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderVelocity, 3341600327ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Vector2 GetColliderVelocity()
    {
        Vector2 ret = NativeCalls.godot_icall_0_37(MethodBind5, GodotObject.GetPtr(this));
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
        /// Cached name for the 'point' property.
        /// </summary>
        public static readonly StringName Point = "point";
        /// <summary>
        /// Cached name for the 'normal' property.
        /// </summary>
        public static readonly StringName Normal = "normal";
        /// <summary>
        /// Cached name for the 'collider_rid' property.
        /// </summary>
        public static readonly StringName ColliderRid = "collider_rid";
        /// <summary>
        /// Cached name for the 'collider_id' property.
        /// </summary>
        public static readonly StringName ColliderId = "collider_id";
        /// <summary>
        /// Cached name for the 'collider_shape' property.
        /// </summary>
        public static readonly StringName ColliderShape = "collider_shape";
        /// <summary>
        /// Cached name for the 'collider_velocity' property.
        /// </summary>
        public static readonly StringName ColliderVelocity = "collider_velocity";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'get_point' method.
        /// </summary>
        public static readonly StringName GetPoint = "get_point";
        /// <summary>
        /// Cached name for the 'get_normal' method.
        /// </summary>
        public static readonly StringName GetNormal = "get_normal";
        /// <summary>
        /// Cached name for the 'get_collider_rid' method.
        /// </summary>
        public static readonly StringName GetColliderRid = "get_collider_rid";
        /// <summary>
        /// Cached name for the 'get_collider_id' method.
        /// </summary>
        public static readonly StringName GetColliderId = "get_collider_id";
        /// <summary>
        /// Cached name for the 'get_collider_shape' method.
        /// </summary>
        public static readonly StringName GetColliderShape = "get_collider_shape";
        /// <summary>
        /// Cached name for the 'get_collider_velocity' method.
        /// </summary>
        public static readonly StringName GetColliderVelocity = "get_collider_velocity";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
