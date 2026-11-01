namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This class contains the intersection information produced by <see cref="Godot.PhysicsDirectSpaceState3D.IntersectPointInto(PhysicsPointQueryParameters3D, PhysicsIntersectPointResult3D)"/>.</para>
/// <para>It stores up to a user-defined number of overlapping shapes.</para>
/// <para><b>Note:</b> For optimal performance results, it is recommended to create this object in advance, store it, and reuse it for every subsequent query.</para>
/// </summary>
public partial class PhysicsIntersectPointResult3D : RefCounted
{
    /// <summary>
    /// <para>The maximum number of intersections this result object can store.</para>
    /// </summary>
    public int MaxIntersections
    {
        get
        {
            return GetMaxIntersections();
        }
        set
        {
            SetMaxIntersections(value);
        }
    }

    private static readonly System.Type CachedType = typeof(PhysicsIntersectPointResult3D);

    private static readonly StringName NativeName = "PhysicsIntersectPointResult3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public PhysicsIntersectPointResult3D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsIntersectPointResult3D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsIntersectPointResult3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxIntersections, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMaxIntersections()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxIntersections, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxIntersections(int maxIntersections)
    {
        NativeCalls.godot_icall_1_38(MethodBind1, GodotObject.GetPtr(this), maxIntersections);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetIntersectionCount, 3905245786ul);

    /// <summary>
    /// <para>Returns the number of shapes that intersect the queried point.</para>
    /// </summary>
    public int GetIntersectionCount()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderId, 923996154ul);

    /// <summary>
    /// <para>The colliding object's ID.</para>
    /// </summary>
    public ulong GetColliderId(int intersectionIndex)
    {
        ulong ret = NativeCalls.godot_icall_1_269(MethodBind3, GodotObject.GetPtr(this), intersectionIndex);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderRid, 495598643ul);

    /// <summary>
    /// <para>The intersecting object's <see cref="Godot.Rid"/>.</para>
    /// </summary>
    public Rid GetColliderRid(int intersectionIndex)
    {
        Rid ret = NativeCalls.godot_icall_1_68(MethodBind4, GodotObject.GetPtr(this), intersectionIndex);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCollider, 3332903315ul);

    /// <summary>
    /// <para>The colliding object.</para>
    /// </summary>
    public GodotObject GetCollider(int intersectionIndex)
    {
        GodotObject ret = (GodotObject)NativeCalls.godot_icall_1_365(MethodBind5, GodotObject.GetPtr(this), intersectionIndex);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderShape, 923996154ul);

    /// <summary>
    /// <para>The shape index of the colliding shape.</para>
    /// </summary>
    public int GetColliderShape(int intersectionIndex)
    {
        int ret = NativeCalls.godot_icall_1_85(MethodBind6, GodotObject.GetPtr(this), intersectionIndex);
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
        /// Cached name for the 'max_intersections' property.
        /// </summary>
        public static readonly StringName MaxIntersections = "max_intersections";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'get_max_intersections' method.
        /// </summary>
        public static readonly StringName GetMaxIntersections = "get_max_intersections";
        /// <summary>
        /// Cached name for the 'set_max_intersections' method.
        /// </summary>
        public static readonly StringName SetMaxIntersections = "set_max_intersections";
        /// <summary>
        /// Cached name for the 'get_intersection_count' method.
        /// </summary>
        public static readonly StringName GetIntersectionCount = "get_intersection_count";
        /// <summary>
        /// Cached name for the 'get_collider_id' method.
        /// </summary>
        public static readonly StringName GetColliderId = "get_collider_id";
        /// <summary>
        /// Cached name for the 'get_collider_rid' method.
        /// </summary>
        public static readonly StringName GetColliderRid = "get_collider_rid";
        /// <summary>
        /// Cached name for the 'get_collider' method.
        /// </summary>
        public static readonly StringName GetCollider = "get_collider";
        /// <summary>
        /// Cached name for the 'get_collider_shape' method.
        /// </summary>
        public static readonly StringName GetColliderShape = "get_collider_shape";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
